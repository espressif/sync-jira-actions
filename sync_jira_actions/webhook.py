import os

from http import HTTPStatus

import requests


def send_webhook(action_type, github_issue, jira_issue=None):
    """Send webhook notification about the action performed.

    Args:
        action_type (str): The type of action performed (e.g., 'issue_opened', 'comment_created')
        github_issue (dict): GitHub issue/PR data
        jira_issue (object, optional): JIRA issue object
    """
    webhook_url = os.environ.get('WEBHOOK_URL')
    if not webhook_url:
        return  # No webhook configured, skip silently

    # Prepare webhook payload
    payload = {
        'action_type': action_type,
        'github_repository': os.environ.get('GITHUB_REPOSITORY'),
        'github_issue': {
            'number': github_issue.get('number'),
            'title': github_issue.get('title'),
            'state': github_issue.get('state'),
            'is_pull_request': 'pull_request' in github_issue,
        },
    }

    # Add JIRA issue information if available
    if jira_issue:
        payload['jira_issue'] = {
            'key': jira_issue.key,
            'summary': jira_issue.fields.summary,
            'status': jira_issue.fields.status.name if hasattr(jira_issue.fields, 'status') else None,
        }

    try:
        response = requests.post(
            webhook_url,
            json=payload,
            headers={'Content-Type': 'application/json'},
            timeout=30,  # 30 second timeout
        )
    except requests.exceptions.RequestException as e:
        print(f'⚠️ Webhook notification failed for {action_type}: {str(e)}')
    except Exception as e:
        print(f'⚠️ Unexpected error sending webhook for {action_type}: {str(e)}')
    else:
        if response.status_code in [HTTPStatus.OK, HTTPStatus.CREATED, HTTPStatus.ACCEPTED, HTTPStatus.NO_CONTENT]:
            print(f'✔️ Webhook notification sent successfully for {action_type}')
        else:
            print(f'⚠️ Webhook notification failed with status {response.status_code} for {action_type}')
