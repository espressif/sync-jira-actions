from unittest.mock import MagicMock
from unittest.mock import patch

import pytest


@pytest.fixture(autouse=True)
def setup_env(monkeypatch):
    monkeypatch.setenv('GITHUB_TOKEN', 'fake-token')
    monkeypatch.setenv('GITHUB_REPOSITORY', 'fake/repo')


@pytest.fixture(scope='module')
def github_client_mock():
    with patch('github.Github') as MockGithub:
        mock_github = MockGithub.return_value
        mock_repo = MagicMock()
        mock_github.get_repo.return_value = mock_repo
        yield mock_github, mock_repo


# Correct fixture to mock JIRA client
@pytest.fixture(scope='module')
def mock_jira_client():
    with patch('jira.JIRA') as MockJIRA:
        mock_jira = MockJIRA.return_value
        yield mock_jira


@pytest.fixture
def sync_issue_module(github_client_mock):
    from importlib import reload
    from sync_jira_actions import sync_issue

    reload(sync_issue)  # Reload to apply the mocked Github client
    return sync_issue


# Example test function
def test_handle_issue_opened_creates_jira_issue(sync_issue_module, github_client_mock):
    _, mock_repo = github_client_mock
    mock_jira_client = MagicMock()
    mock_event = {
        'issue': {
            'number': 123,
            'title': 'New Issue',
            'body': 'Issue description here.',
            'user': {'login': 'user123'},
            'labels': [],
            'html_url': 'https://github.com/user/repo/issues/123',
            'state': 'open',
        }
    }

    with (
        patch('sync_jira_actions.sync_issue._find_jira_issue', return_value=None) as mock_find_jira_issue,
        patch('sync_jira_actions.sync_issue._create_jira_issue') as mock_create_jira_issue,
    ):
        sync_issue_module.handle_issue_opened(mock_jira_client, mock_event)

        mock_find_jira_issue.assert_called_once()
        mock_create_jira_issue.assert_called_once()


def test_handle_issue_labeled_adds_label(sync_issue_module, github_client_mock, mock_jira_client):
    # Setup
    mock_github, mock_repo = github_client_mock

    mock_event = {
        'issue': {
            'number': 123,
            'title': 'Issue for Labeling',
            'body': 'Label me!',
            'user': {'login': 'user456'},
            'labels': [{'name': 'bug'}],
            'html_url': 'https://github.com/user/repo/issues/123',
            'state': 'open',
        },
        'label': {'name': 'bug'},
    }

    # Adjusting the mock to behave more like a list that can be appended to
    mock_jira_issue = MagicMock()
    labels_list = ['existing-label']  # Starting with an existing label for demonstration
    mock_jira_issue.fields.labels = labels_list

    def update_labels(fields=None):
        if fields and 'labels' in fields:
            labels_list.extend(fields['labels'])  # Simulate adding new labels

    mock_jira_issue.update = MagicMock(side_effect=update_labels)

    with (
        patch('sync_jira_actions.sync_issue._find_jira_issue', return_value=mock_jira_issue),
        patch('sync_jira_actions.sync_issue._get_jira_label', side_effect=lambda x: x['name']),
    ):
        sync_issue_module.handle_issue_labeled(mock_jira_client, mock_event)

    assert 'bug' in labels_list, "Label 'bug' was not added to the JIRA issue labels"


def test_handle_issue_transferred_updates_remote_link(sync_issue_module, github_client_mock):
    """Test that handle_issue_transferred updates the remote link and Jira issue fields."""
    _, mock_repo = github_client_mock
    mock_jira = MagicMock()

    old_url = 'https://github.com/espressif/idf-eclipse-plugin/issues/123'
    new_url = 'https://github.com/espressif/esp-idf/issues/14141'

    mock_event = {
        'issue': {
            'number': 123,
            'title': 'Some Issue (IEP-99)',
            'body': 'Issue body.',
            'user': {'login': 'author'},
            'labels': [],
            'html_url': old_url,
            'state': 'open',
        },
        'changes': {
            'new_issue': {
                'number': 14141,
                'title': 'Some Issue (IEP-99)',
                'body': 'Issue body.',
                'user': {'login': 'author'},
                'labels': [],
                'html_url': new_url,
                'state': 'open',
            },
            'new_repository': {
                'full_name': 'espressif/esp-idf',
            },
        },
        'sender': {'login': 'project-manager'},
        'repository': {'full_name': 'espressif/idf-eclipse-plugin'},
    }

    mock_jira_issue = MagicMock()
    mock_jira_issue.key = 'IEP-99'

    # Create a mock remote link that matches the old URL
    mock_link = MagicMock()
    mock_link.globalId = old_url
    mock_link.relationship = 'synced from'
    mock_link.raw = {'object': {'url': old_url, 'title': 'Some Issue'}}
    mock_jira.remote_links.return_value = [mock_link]

    with (
        patch('sync_jira_actions.sync_issue._find_jira_issue', return_value=mock_jira_issue),
        patch('sync_jira_actions.sync_issue._get_summary', return_value='GH #14141: Some Issue'),
        patch('sync_jira_actions.sync_issue._get_description', return_value='desc'),
    ):
        result = sync_issue_module.handle_issue_transferred(mock_jira, mock_event)

    assert result == mock_jira_issue
    # Verify the remote link was updated to the new URL
    mock_link.update.assert_called_once()
    call_kwargs = mock_link.update.call_args
    assert call_kwargs[1]['globalId'] == new_url
    # Verify a comment was left about the transfer
    mock_jira.add_comment.assert_called_once()
    comment_body = mock_jira.add_comment.call_args[0][1]
    assert 'espressif/idf-eclipse-plugin' in comment_body
    assert 'espressif/esp-idf' in comment_body
    assert new_url in comment_body
    assert 'project-manager' in comment_body
    # Verify the Jira issue fields were updated
    mock_jira_issue.update.assert_called_once()


def test_handle_issue_transferred_no_existing_jira_issue(sync_issue_module, github_client_mock):
    """Test that handle_issue_transferred does nothing when no Jira issue is found."""
    mock_jira = MagicMock()

    mock_event = {
        'issue': {
            'number': 1,
            'title': 'Unsynced Issue',
            'body': 'No Jira issue yet.',
            'user': {'login': 'author'},
            'labels': [],
            'html_url': 'https://github.com/espressif/idf-eclipse-plugin/issues/1',
            'state': 'open',
        },
        'changes': {
            'new_issue': {'html_url': 'https://github.com/espressif/esp-idf/issues/999'},
            'new_repository': {'full_name': 'espressif/esp-idf'},
        },
        'sender': {'login': 'user'},
    }

    with patch('sync_jira_actions.sync_issue._find_jira_issue', return_value=None):
        result = sync_issue_module.handle_issue_transferred(mock_jira, mock_event)

    assert result is None
    mock_jira.remote_links.assert_not_called()
    mock_jira.add_comment.assert_not_called()


def test_handle_issue_transferred_missing_new_issue(sync_issue_module, github_client_mock):
    """Test that handle_issue_transferred handles missing new_issue gracefully."""
    mock_jira = MagicMock()

    mock_jira_issue = MagicMock()
    mock_jira_issue.key = 'IEP-99'

    mock_event = {
        'issue': {
            'number': 123,
            'title': 'Some Issue (IEP-99)',
            'body': 'Body.',
            'user': {'login': 'author'},
            'labels': [],
            'html_url': 'https://github.com/espressif/idf-eclipse-plugin/issues/123',
            'state': 'open',
        },
        'changes': {},  # no new_issue
        'sender': {'login': 'user'},
    }

    with patch('sync_jira_actions.sync_issue._find_jira_issue', return_value=mock_jira_issue):
        result = sync_issue_module.handle_issue_transferred(mock_jira, mock_event)

    assert result == mock_jira_issue
    mock_jira.remote_links.assert_not_called()
    mock_jira.add_comment.assert_not_called()


def test_find_jira_issue_detects_transferred_issue(sync_issue_module, github_client_mock):
    """
    Test that _find_jira_issue detects a transferred GitHub issue via the Jira key in the
    title and an existing GitHub remote link, and updates the remote link URL.
    """
    mock_jira = MagicMock()

    old_url = 'https://github.com/espressif/idf-eclipse-plugin/issues/123'
    new_url = 'https://github.com/espressif/esp-idf/issues/14141'

    gh_issue = {
        'number': 14141,
        'title': 'Some Issue (IEP-99)',  # title has old Jira key
        'body': 'Issue body.',
        'user': {'login': 'author'},
        'labels': [],
        'html_url': new_url,
        'state': 'open',
    }

    mock_jira_issue = MagicMock()
    mock_jira_issue.key = 'IEP-99'
    mock_jira_issue.fields.description = f'[GitHub Issue|{old_url}] from user @author:'

    # JQL search returns no results (new URL not yet linked)
    mock_jira.search_issues.return_value = []

    # jira.issue() returns the old Jira issue found by key
    mock_jira.issue.return_value = mock_jira_issue

    # Remote link with the old GitHub URL (simulating a transferred issue)
    mock_link = MagicMock()
    mock_link.globalId = old_url
    mock_link.relationship = 'synced from'
    mock_link.raw = {'object': {'url': old_url, 'title': 'Some Issue'}}
    mock_jira.remote_links.return_value = [mock_link]

    result = sync_issue_module._find_jira_issue(mock_jira, gh_issue, make_new=False)

    assert result == mock_jira_issue
    # Verify the remote link was updated to the new URL
    mock_link.update.assert_called_once()
    call_kwargs = mock_link.update.call_args
    assert call_kwargs[1]['globalId'] == new_url


def test_handle_issue_opened_does_not_create_duplicate_for_transferred_issue(
    sync_issue_module, github_client_mock
):
    """
    Test that handle_issue_opened does not create a duplicate Jira issue when the GitHub
    issue was transferred from another repo and the existing Jira issue is detected.
    """
    mock_jira = MagicMock()
    mock_jira_issue = MagicMock()
    mock_jira_issue.key = 'IEP-99'

    new_url = 'https://github.com/espressif/esp-idf/issues/14141'

    mock_event = {
        'issue': {
            'number': 14141,
            'title': 'Transferred Issue (IEP-99)',
            'body': 'Issue body.',
            'user': {'login': 'author'},
            'labels': [],
            'html_url': new_url,
            'state': 'open',
        }
    }

    with (
        patch('sync_jira_actions.sync_issue._find_jira_issue', return_value=mock_jira_issue) as mock_find,
        patch('sync_jira_actions.sync_issue._create_jira_issue') as mock_create,
    ):
        result = sync_issue_module.handle_issue_opened(mock_jira, mock_event)

    assert result == mock_jira_issue
    mock_find.assert_called_once()
    # No new Jira issue should be created
    mock_create.assert_not_called()

