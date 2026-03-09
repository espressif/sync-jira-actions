import importlib
from unittest.mock import MagicMock
from unittest.mock import patch

import pytest
from github.GithubException import GithubException


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
        mock_repo.owner.type = 'Organization'
        mock_repo.owner.login = 'fake'
        mock_repo.has_in_collaborators.return_value = False

        mock_org = MagicMock()
        mock_org.has_in_members.return_value = False
        MockGithub.return_value.get_organization.return_value = mock_org

        MockGithub.return_value.get_repo.return_value = mock_repo
        yield mock_repo


@pytest.fixture
def sync_pr_module(mock_github):
    # Import the module from the sync_jira_actions directory
    import sys

    sys.path.insert(0, 'sync_jira_actions')  # Add sync_jira_actions directory to the Python path
    import sync_pr

    # Reload the module to ensure the mock is applied
    importlib.reload(sync_pr)
    # Return the reloaded module
    return sync_pr


@pytest.fixture
def mock_sync_issue():
    with (
        patch('sync_pr._create_jira_issue') as mock_create_jira_issue,
        patch('sync_pr._find_jira_issue', return_value=None) as mock_find_jira_issue,
    ):
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


def test_sync_remain_prs_skips_org_members(sync_pr_module, mock_sync_issue, mock_github):
    """Test that PRs from org members are skipped"""
    mock_jira = MagicMock()
    mock_create_jira_issue, mock_find_jira_issue = mock_sync_issue

    # Patch the internal function to return 'organization member'
    with patch.object(sync_pr_module, '_is_collaborator_or_org_member', return_value='organization member'):
        sync_pr_module.sync_remain_prs(mock_jira)

    # Verify no JIRA issue was created for org member PR
    assert mock_create_jira_issue.call_count == 0
    assert mock_find_jira_issue.call_count == 0


def test_sync_remain_prs_skips_collaborators(sync_pr_module, mock_sync_issue, mock_github):
    """Test that PRs from collaborators are skipped"""
    mock_jira = MagicMock()
    mock_create_jira_issue, mock_find_jira_issue = mock_sync_issue

    # Patch the internal function to return 'collaborator'
    with patch.object(sync_pr_module, '_is_collaborator_or_org_member', return_value='collaborator'):
        sync_pr_module.sync_remain_prs(mock_jira)

    # Verify no JIRA issue was created for collaborator PR
    assert mock_create_jira_issue.call_count == 0
    assert mock_find_jira_issue.call_count == 0


def test_sync_remain_prs_handles_bot_accounts(sync_pr_module, mock_sync_issue, mock_github):
    """Test that PRs from bot accounts (e.g. copilot[bot]) don't crash the sync"""
    mock_jira = MagicMock()
    mock_create_jira_issue, mock_find_jira_issue = mock_sync_issue

    # Set the PR author to a bot account
    mock_github.get_pulls.return_value[0].user.login = 'copilot[bot]'

    # Patch the internal function to return None (bot is not recognized as collaborator/org member)
    with patch.object(sync_pr_module, '_is_collaborator_or_org_member', return_value=None):
        sync_pr_module.sync_remain_prs(mock_jira)

    # The PR should still be synced (bot is not a collaborator/org member)
    assert mock_find_jira_issue.call_count == 1
    assert mock_create_jira_issue.call_count == 1


def test_is_collaborator_or_org_member_handles_bot_accounts(sync_pr_module):
    """Test that _is_collaborator_or_org_member returns None for bot accounts"""
    mock_github_instance = MagicMock()
    mock_repo = MagicMock()
    mock_repo.has_in_collaborators.return_value = False
    mock_repo.owner.type = 'Organization'
    mock_repo.owner.login = 'fake-org'

    # Simulate get_user() raising GithubException for bot account
    mock_github_instance.get_user.side_effect = GithubException(404, 'Not Found', None)

    result = sync_pr_module._is_collaborator_or_org_member(mock_github_instance, mock_repo, 'copilot[bot]')

    # Should return None (not recognized as collaborator or org member) instead of crashing
    assert result is None
