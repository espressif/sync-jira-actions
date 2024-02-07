import importlib
from unittest.mock import MagicMock
from unittest.mock import patch

import pytest


# Patch the GitHub client before importing modules that use it
@pytest.fixture(autouse=True)
def mock_env_vars(monkeypatch):
    monkeypatch.setenv('GITHUB_TOKEN', 'fake-token')
    monkeypatch.setenv('GITHUB_REPOSITORY', 'fake/repo')


@pytest.fixture
def mock_github():
    with patch('github.Github') as MockGithub:
        mock_repo = MagicMock()
        mock_pr = MagicMock()
        mock_pr.number = 1
        mock_pr.title = 'Test PR'
        mock_pr.html_url = 'http://example.com/testpr'
        mock_pr.user.login = 'testuser'
        mock_pr.labels = []
        mock_pr.state = 'open'
        mock_pr.body = 'Test body'
        mock_repo.get_pulls.return_value = [mock_pr]
        mock_repo.has_in_collaborators.return_value = False

        MockGithub.return_value.get_repo.return_value = mock_repo
        yield mock_repo


@pytest.fixture
def sync_pr_module(mock_github):
    # Import the module from the src directory
    import sys

    sys.path.insert(0, 'src')  # Add src directory to the Python path
    import sync_pr

    # Reload the module to ensure the mock is applied
    importlib.reload(sync_pr)
    # Return the reloaded module
    return sync_pr


@pytest.fixture
def mock_sync_issue():
    with patch('sync_pr._create_jira_issue') as mock_create_jira_issue, patch(
        'sync_pr._find_jira_issue', return_value=None
    ) as mock_find_jira_issue:
        yield mock_create_jira_issue, mock_find_jira_issue


def test_sync_remain_prs(sync_pr_module, mock_sync_issue, mock_github):
    mock_jira = MagicMock()
    mock_create_jira_issue, mock_find_jira_issue = mock_sync_issue

    # Use the function from the reloaded module
    sync_pr_module.sync_remain_prs(mock_jira)

    # Verify _find_jira_issue was called once with the mock_jira client and the PR data
    assert mock_find_jira_issue.call_count == 1

    # Verify _create_jira_issue was called once since no corresponding JIRA issue was found
    assert mock_create_jira_issue.call_count == 1

    # Example of verifying call arguments (simplified)
    call_args = mock_create_jira_issue.call_args
    assert 'Test PR' in call_args[0][1]['title'], 'PR title does not match expected value'
