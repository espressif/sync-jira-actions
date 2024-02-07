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
    from src import sync_issue

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

    with patch('src.sync_issue._find_jira_issue', return_value=None) as mock_find_jira_issue, patch(
        'src.sync_issue._create_jira_issue'
    ) as mock_create_jira_issue:
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

    with patch('src.sync_issue._find_jira_issue', return_value=mock_jira_issue), patch(
        'src.sync_issue._get_jira_label', side_effect=lambda x: x['name']
    ):
        sync_issue_module.handle_issue_labeled(mock_jira_client, mock_event)

    assert 'bug' in labels_list, "Label 'bug' was not added to the JIRA issue labels"
