#!/usr/bin/env python3
#
# Copyright 2019-2024 Espressif Systems (Shanghai) CO LTD
#
# Licensed under the Apache License, Version 2.0 (the "License");
# you may not use this file except in compliance with the License.
# You may obtain a copy of the License at
#
#     http://www.apache.org/licenses/LICENSE-2.0
#
# Unless required by applicable law or agreed to in writing, software
# distributed under the License is distributed on an "AS IS" BASIS,
# WITHOUT WARRANTIES OR CONDITIONS OF ANY KIND, either express or implied.
# See the License for the specific language governing permissions and
# limitations under the License.
#
import os

from github import Github
from github import GithubException
from sync_issue import _create_jira_issue
from sync_issue import _find_jira_issue


def _is_collaborator_or_org_member(github, repo, username):
    """
    Check if user is a collaborator or organization member.
    Returns the user type string if the user has direct access to the repo, None otherwise.
    """
    if repo.has_in_collaborators(username):
        return 'collaborator'
    if repo.owner.type == 'Organization':
        org = github.get_organization(repo.owner.login)
        try:
            if org.has_in_members(github.get_user(username)):
                return 'organization member'
        except GithubException:
            print(f'WARNING ⚠️ Could not check org membership for @{username}, treating as external contributor')
    return None


def sync_remain_prs(jira, issue_callback=None):
    """
    Sync remain PRs (i.e. PRs without any comments) to Jira
    """
    github = Github(os.environ['GITHUB_TOKEN'])
    repo = github.get_repo(os.environ['GITHUB_REPOSITORY'])
    prs = repo.get_pulls(state='open', sort='created', direction='desc')
    for pr in prs:
        user_type = _is_collaborator_or_org_member(github, repo, pr.user.login)
        if user_type:
            print(f'⏭️ Skipping PR #{pr.number} - author @{pr.user.login} is a {user_type}')
            continue
        # mock a github issue using current PR
        gh_issue = {
            'pull_request': True,
            'labels': [{'name': lbl.name} for lbl in pr.labels],
            'number': pr.number,
            'title': pr.title,
            'html_url': pr.html_url,
            'user': {'login': pr.user.login},
            'state': pr.state,
            'body': pr.body,
        }
        issue = _find_jira_issue(jira, gh_issue)
        if issue is None:
            _create_jira_issue(jira, gh_issue)
            print(f'✔️ Successfully synchronized PR #{pr.number}')

        if issue_callback:
            issue_callback(github_issue=gh_issue, jira_issue=issue)
