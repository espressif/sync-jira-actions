import os
from unittest.mock import MagicMock, patch

import pytest
from requests.exceptions import RequestException

from sync_jira_actions.webhook import send_webhook


@pytest.fixture(autouse=True)
def setup_env(monkeypatch):
    monkeypatch.setenv('GITHUB_REPOSITORY', 'fake/repo')

def test_send_webhook_success(capfd):
    """Test that send_webhook sends the correct payload and handles success."""
    with patch.dict(os.environ, {'WEBHOOK_URL': 'http://example.com/webhook'}):
        with patch('sync_jira_actions.webhook.requests.post') as mock_post:
            mock_response = MagicMock()
            mock_response.status_code = 200
            mock_post.return_value = mock_response

            github_issue = {
                'number': 123,
                'title': 'Test Issue',
                'state': 'open',
            }

            jira_issue = MagicMock()
            jira_issue.key = 'PROJ-123'
            jira_issue.fields.summary = 'Test Summary'
            jira_issue.fields.status.name = 'In Progress'

            send_webhook('issue_opened', github_issue, jira_issue)
            out, _ = capfd.readouterr()
            assert '✔️ Webhook notification sent successfully for issue_opened' in out

            # Verify the payload
            expected_payload = {
                'action_type': 'issue_opened',
                'github_repository': 'fake/repo',
                'github_issue': {
                    'number': 123,
                    'title': 'Test Issue',
                    'state': 'open',
                    'is_pull_request': False,
                },
                'jira_issue': {
                    'key': 'PROJ-123',
                    'summary': 'Test Summary',
                    'status': 'In Progress',
                },
            }
            mock_post.assert_called_once_with(
                'http://example.com/webhook',
                json=expected_payload,
                headers={'Content-Type': 'application/json'},
                timeout=30,
            )


def test_send_webhook_without_jira_issue(capfd):
    """Test that send_webhook works correctly without a JIRA issue."""
    with patch.dict(os.environ, {'WEBHOOK_URL': 'http://example.com/webhook'}):
        with patch('sync_jira_actions.webhook.requests.post') as mock_post:
            mock_response = MagicMock()
            mock_response.status_code = 200
            mock_post.return_value = mock_response

            github_issue = {
                'number': 123,
                'title': 'Test Issue',
                'state': 'open',
                'pull_request': {},  # This makes it a PR
            }

            send_webhook('pr_opened', github_issue)
            out, _ = capfd.readouterr()
            assert '✔️ Webhook notification sent successfully for pr_opened' in out

            # Verify the payload
            expected_payload = {
                'action_type': 'pr_opened',
                'github_repository': 'fake/repo',
                'github_issue': {
                    'number': 123,
                    'title': 'Test Issue',
                    'state': 'open',
                    'is_pull_request': True,
                },
            }
            mock_post.assert_called_once_with(
                'http://example.com/webhook',
                json=expected_payload,
                headers={'Content-Type': 'application/json'},
                timeout=30,
            )


def test_send_webhook_request_exception(capfd):
    """Test that send_webhook handles RequestException correctly."""
    with patch.dict(os.environ, {'WEBHOOK_URL': 'http://example.com/webhook'}):
        with patch('sync_jira_actions.webhook.requests.post', side_effect=RequestException('Connection error')):
            send_webhook('issue_opened', {'number': 123, 'title': 'Test Issue', 'state': 'open'})
            out, _ = capfd.readouterr()
            assert '⚠️ Webhook notification failed for issue_opened: Connection error' in out


def test_send_webhook_non_200_status(capfd):
    """Test that send_webhook handles non-200 status codes correctly."""
    with patch.dict(os.environ, {'WEBHOOK_URL': 'http://example.com/webhook'}):
        with patch('sync_jira_actions.webhook.requests.post') as mock_post:
            mock_response = MagicMock()
            mock_response.status_code = 500
            mock_post.return_value = mock_response

            send_webhook('issue_opened', {'number': 123, 'title': 'Test Issue', 'state': 'open'})
            out, _ = capfd.readouterr()
            assert '⚠️ Webhook notification failed with status 500 for issue_opened' in out
