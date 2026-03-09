import json
from unittest.mock import MagicMock
from unittest.mock import patch

import pytest
from github.GithubException import GithubException


@pytest.fixture
def mock_environment(tmp_path, monkeypatch):
    event_file = tmp_path / 'event.json'
    monkeypatch.setenv('GITHUB_REPOSITORY', 'espressif/esp-idf')
    monkeypatch.setenv('GITHUB_TOKEN', 'fake-token')
    monkeypatch.setenv('GITHUB_EVENT_PATH', str(event_file))
    monkeypatch.setenv('JIRA_URL', 'https://jira.example.com')
    monkeypatch.setenv('JIRA_USER', 'user')
    monkeypatch.setenv('JIRA_PASS', 'pass')
    return event_file


@pytest.fixture
def sync_to_jira_main(monkeypatch):
    monkeypatch.setattr('github.Github', MagicMock())
    monkeypatch.setattr('jira.JIRA', MagicMock())

    # Import the main function dynamically after applying mocks
    from sync_jira_actions.sync_to_jira import main as dynamically_imported_main

    return dynamically_imported_main


def test_not_running_in_github_action_context(capsys, sync_to_jira_main, monkeypatch):
    monkeypatch.delenv('GITHUB_REPOSITORY', raising=False)
    sync_to_jira_main()
    captured = capsys.readouterr()
    assert 'Not running in GitHub action context, nothing to do' in captured.out


def test_not_espressif_repo(capsys, sync_to_jira_main, monkeypatch):
    monkeypatch.setenv('GITHUB_REPOSITORY', 'other/repo')
    sync_to_jira_main()
    captured = capsys.readouterr()
    assert 'Not an Espressif repo, nothing to sync to JIRA' in captured.out


def test_handle_issue_opened_event(mock_environment, sync_to_jira_main, monkeypatch):
    event_data = {
        'action': 'opened',
        'issue': {
            'number': 1,
            'title': 'Test issue',
            'body': 'This is a test issue',
            'user': {'login': 'testuser'},
            'html_url': 'https://github.com/espressif/esp-idf/issues/1',
        },
    }
    mock_environment.write_text(json.dumps(event_data))
    monkeypatch.setenv('GITHUB_EVENT_NAME', 'issues')
    monkeypatch.setenv('JIRA_PROJECT', 'TEST_PROJECT')

    with patch('sync_jira_actions.sync_to_jira.handle_issue_opened') as mock_handle_issue_opened:
        sync_to_jira_main()
        mock_handle_issue_opened.assert_called_once()


def test_pr_opened_by_bot_account_does_not_crash(mock_environment, monkeypatch):
    """Test that PRs opened by bot accounts (e.g. copilot[bot]) don't crash the sync"""
    event_data = {
        'action': 'opened',
        'pull_request': {
            'number': 42,
            'title': 'Bot PR',
            'body': 'Automated PR',
            'user': {'login': 'copilot[bot]'},
            'html_url': 'https://github.com/espressif/esp-idf/pull/42',
            'state': 'open',
            'labels': [],
        },
    }
    mock_environment.write_text(json.dumps(event_data))
    monkeypatch.setenv('GITHUB_EVENT_NAME', 'pull_request')
    monkeypatch.setenv('JIRA_PROJECT', 'TEST_PROJECT')

    mock_repo = MagicMock()
    mock_repo.has_in_collaborators.return_value = False
    mock_repo.owner.type = 'Organization'
    mock_repo.owner.login = 'espressif'

    mock_github_instance = MagicMock()
    mock_github_instance.get_repo.return_value = mock_repo
    # Simulate get_user() raising GithubException for bot account
    mock_github_instance.get_user.side_effect = GithubException(404, 'Not Found', None)

    with (
        patch('sync_jira_actions.sync_to_jira.Github', return_value=mock_github_instance),
        patch('sync_jira_actions.sync_to_jira._JIRA'),
        patch('sync_jira_actions.sync_to_jira.handle_issue_opened') as mock_handle_issue_opened,
    ):
        from sync_jira_actions.sync_to_jira import main

        # This should not raise an exception
        main()
        mock_handle_issue_opened.assert_called_once()
