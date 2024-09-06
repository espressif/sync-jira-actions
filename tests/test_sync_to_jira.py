import json
from unittest.mock import MagicMock
from unittest.mock import patch

import pytest


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
