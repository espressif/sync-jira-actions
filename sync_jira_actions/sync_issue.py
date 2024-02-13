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
import random
import re
import subprocess
import tempfile
import time

from github import Github
from github.GithubException import GithubException
from jira import JIRAError

# 10101 is ID for New Feature issue type in Jira.
JIRA_NEW_FEATURE_TYPE_ID = 10101
# 10004 is ID for Bug issue type in Jira.
JIRA_BUG_TYPE_ID = 10004
# Initialize GitHub instance
GITHUB = Github(os.environ['GITHUB_TOKEN'])
# Initialize GitHub repository
REPO = GITHUB.get_repo(os.environ['GITHUB_REPOSITORY'])


def handle_issue_opened(jira, event):
    gh_issue = event['issue']
    issue = _find_jira_issue(jira, gh_issue, False)

    if issue is not None:
        print('Issue already exists (another event was dispatched first?)')
        return

    print('Creating new JIRA issue for new GitHub issue')
    _create_jira_issue(jira, event['issue'])


def handle_issue_edited(jira, event):
    gh_issue = event['issue']
    issue = _find_jira_issue(jira, gh_issue, True)

    fields = {
        'description': _get_description(gh_issue),
        'summary': _get_summary(gh_issue),
    }

    _update_components_field(jira, fields, issue)

    issue.update(fields=fields)

    _update_link_resolved(jira, gh_issue, issue)

    _leave_jira_issue_comment(jira, event, 'edited', True, jira_issue=issue)


def handle_issue_closed(jira, event):
    # note: Not auto-closing the synced JIRA issue because GitHub
    # issues often get closed for the wrong reasons - ie the user
    # found a workaround but the root cause still exists.
    issue = _leave_jira_issue_comment(jira, event, 'closed', False)
    try:
        # Sets value of custom GitHub Issue field to Closed
        issue.update(fields={'customfield_12100': {'value': 'Closed'}})
    except JIRAError as error:
        print(f'Could not set GitHub Issue field to Closed when closing issue with error: {error}')
    if issue is not None:
        _update_link_resolved(jira, event['issue'], issue)


def handle_issue_labeled(jira, event):
    gh_issue = event['issue']
    jira_issue = _find_jira_issue(jira, gh_issue, gh_issue['state'] == 'open')
    if jira_issue is None:
        return

    labels = list(jira_issue.fields.labels)
    new_label = _get_jira_label(event['label'])

    if _check_issue_label(new_label) is None:
        return

    if new_label not in labels:
        labels.append(new_label)
        jira_issue.update(fields={'labels': labels})


def handle_issue_unlabeled(jira, event):
    gh_issue = event['issue']
    jira_issue = _find_jira_issue(jira, gh_issue, gh_issue['state'] == 'open')
    if jira_issue is None:
        return

    labels = list(jira_issue.fields.labels)
    removed_label = _get_jira_label(event['label'])

    if _check_issue_label(removed_label) is None:
        return

    try:
        labels.remove(removed_label)
        jira_issue.update(fields={'labels': labels})
    except ValueError:
        pass  # not in labels list


def handle_issue_deleted(jira, event):
    _leave_jira_issue_comment(jira, event, 'deleted', False)


def handle_issue_reopened(jira, event):
    issue = _leave_jira_issue_comment(jira, event, 'reopened', True)
    try:
        # Sets value of custom GitHub Issue field to Open
        issue.update(fields={'customfield_12100': {'value': 'Open'}})
    except JIRAError as error:
        print(f'Could not set GitHub Issue field to Open when reopening issue with error: {error}')
    _update_link_resolved(jira, event['issue'], issue)


def handle_comment_created(jira, event):
    gh_comment = event['comment']

    jira_issue = _find_jira_issue(jira, event['issue'], True)
    jira.add_comment(jira_issue.id, _get_jira_comment_body(gh_comment))


def handle_comment_edited(jira, event):
    gh_comment = event['comment']
    old_gh_body = _markdown2wiki(event['changes']['body']['from'])

    jira_issue = _find_jira_issue(jira, event['issue'], True)

    # Look for the old comment and update it if we find it
    old_jira_body = _get_jira_comment_body(gh_comment, old_gh_body)
    found = False
    for comment in jira.comments(jira_issue.key):
        if comment.body == old_jira_body:
            comment.update(body=_get_jira_comment_body(gh_comment))
            found = True
            break

    if not found:  # if we didn't find the old comment, make a new comment about the edit
        jira.add_comment(jira_issue.id, _get_jira_comment_body(gh_comment))


def handle_comment_deleted(jira, event):
    gh_comment = event['comment']
    jira_issue = _find_jira_issue(jira, event['issue'], True)
    jira.add_comment(
        jira_issue.id, f"@{gh_comment['user']['login']} deleted [GitHub issue comment|{gh_comment['html_url']}]"
    )


# Works both for issues and pull requests
def sync_issues_manually(jira, event):
    # Get issue numbers that were entered manually when triggering workflow
    issue_numbers = event['inputs']['issue-numbers']
    issues = re.split(r'\W+', issue_numbers)
    # Process every issue
    for issue_number in issues:
        if not issue_number.isnumeric():
            print(f'Wrong issue number entered: {issue_number} Skipping...')
            continue
        gh_issue = REPO.get_issue(number=int(issue_number))
        event['issue'] = gh_issue.raw_data
        print(f'Mirroring issue: #{issue_number} to Jira')
        handle_issue_opened(jira, event)


def _check_issue_label(label):
    """
    Ignore labels that start with "Status:" and "Resolution:". These labels are
    mirrored from Jira issue and should not be mirrored back as labels
    """
    ignore_prefix = ('status:', 'resolution:')
    if label.lower().startswith(ignore_prefix):
        return None

    return label


def _update_link_resolved(jira, gh_issue, jira_issue):
    """
    Update the 'resolved' status of the remote "synced from" link, based on the
    GitHub issue open/closed status.

    (A 'resolved' link is shown in strikethrough format in JIRA interface.)

    Also updates the link title, if GitHub issue title has changed.
    """
    resolved = gh_issue['state'] != 'open'
    for link in jira.remote_links(jira_issue):
        if hasattr(link, 'globalId') and link.globalId == gh_issue['html_url']:
            new_link = dict(link.raw['object'])  # RemoteLink update() requires all fields as a JSON object, it seems
            new_link['title'] = gh_issue['title']
            new_link['status']['resolved'] = resolved
            link.update(new_link, globalId=link.globalId, relationship=link.relationship)


def _markdown2wiki(markdown):
    """
    Convert markdown to JIRA wiki format. Uses https://github.com/Shogobg/markdown2confluence
    """
    if markdown is None:
        return '\n'  # Allow empty/blank input
    with tempfile.TemporaryDirectory() as tmp_dir:
        md_path = os.path.join(tmp_dir, 'markdown.md')
        conf_path = os.path.join(tmp_dir, 'confluence.txt')
        with open(md_path, 'w', encoding='utf-8') as mdf:
            mdf.write(markdown)
            if not markdown.endswith('\n'):
                mdf.write('\n')

        try:
            subprocess.check_call(['markdown2confluence', md_path, conf_path])
            with open(conf_path, 'r', encoding='utf-8') as file:
                result = file.read()
            if len(result) > 16384:  # limit any single body of text to 16KB (JIRA API limits total text to 32KB)
                result = result[:16376] + '\n\n[...]'  # add newlines to encourage end of any formatting blocks
            return result
        except subprocess.CalledProcessError as error:
            print(f'Failed to run markdown2confluence: {error}. JIRA issue will have raw Markdown contents.')
            return markdown


def _get_description(gh_issue):
    """
    Return the JIRA description text that corresponds to the provided GitHub issue.
    """
    is_pr = 'pull_request' in gh_issue

    description_format = """
[GitHub %(type)s|%(github_url)s] from user @%(github_user)s:

    %(github_description)s

    ---

    Notes:

    * Do not edit this description text, it may be updated automatically.
    * Please interact on GitHub where possible, changes will sync to here.
    """
    description_format = description_format.lstrip('\n')

    if not is_pr:
        # additional dot point only shown for issues not PRs
        description_format += """
    * If closing this issue from a commit, please add
      {code}
      Closes %(github_url)s
      {code}
      in the commit message so the commit is closed on GitHub automatically.
"""

    return description_format % {
        'type': 'Pull Request' if is_pr else 'Issue',
        'github_url': gh_issue['html_url'],
        'github_user': gh_issue['user']['login'],
        'github_description': _markdown2wiki(gh_issue['body']),
    }


def _get_summary(gh_issue):
    """
    Return the JIRA summary corresponding to a given GitHub issue

    Format is: GH/PR #<gh issue number>: <github title without any JIRA slug>
    """
    is_pr = 'pull_request' in gh_issue
    result = f"{'PR' if is_pr else 'GH'} #{gh_issue['number']}: {gh_issue['title']}"

    # don't mirror any existing JIRA slug-like pattern from GH title to JIRA summary
    # (note we don't look for a particular pattern as the JIRA issue may have moved)
    result = re.sub(r' \([\w]+-[\d]+\)', '', result)

    return result


def _create_jira_issue(jira, gh_issue):
    """
    Create a new JIRA issue from the provided GitHub issue, then return the JIRA issue.
    """
    issuetype = _get_jira_issue_type(jira, gh_issue)
    if issuetype is None:
        issuetype = os.environ.get('JIRA_ISSUE_TYPE', 'Task')

    fields = {
        'summary': _get_summary(gh_issue),
        'project': os.environ['JIRA_PROJECT'],
        'description': _get_description(gh_issue),
        'issuetype': issuetype,
        'labels': [_get_jira_label(lbl) for lbl in gh_issue['labels']],
    }
    _update_components_field(jira, fields, None)

    issue = jira.create_issue(fields)

    try:
        # Sets value of custom GitHub Issue field to Open
        issue.update(fields={'customfield_12100': {'value': 'Open'}})
    except JIRAError as error:
        print(f'Could not set GitHub Issue field to Open when creating new issue with error: {error}')

    _add_remote_link(jira, issue, gh_issue)
    _update_github_with_jira_key(gh_issue, issue)
    if gh_issue['state'] != 'open':
        # mark the link to GitHub as resolved
        _update_link_resolved(jira, gh_issue, issue)

    return issue


def _add_remote_link(jira, issue, gh_issue):
    """
    Add the JIRA "remote link" field that points to the issue
    """
    gh_url = gh_issue['html_url']
    jira.add_remote_link(
        issue=issue,
        destination={
            'url': gh_url,
            'title': gh_issue['title'],
        },
        globalId=gh_url,  # globalId is always the GitHub URL
        relationship='synced from',
    )


def _update_github_with_jira_key(gh_issue, jira_issue):
    """Append the new JIRA issue key to the GitHub issue
    (updates made by github actions don't trigger new actions)
    """

    api_gh_issue = REPO.get_issue(gh_issue['number'])

    retries = 5
    while True:
        try:
            api_gh_issue.edit(title=f'{api_gh_issue.title} ({jira_issue.key})')
            break
        except GithubException as error:
            if retries == 0:
                raise
            print(f'GitHub edit failed: {error} ({retries} retries)')
            time.sleep(random.randrange(1, 5))
            retries -= 1


def _update_components_field(jira, fields, existing_issue=None):
    """
    Add a 'components' field to the supplied issue fields dictionary if
    the JIRA_COMPONENT environment variable is set.

    If existing_issue is not None, any existing components are also copied over.

    If existing_issue is None, JIRA_PROJECT environment variable must be set.

    Check the component exists in the issue's JIRA project before adding it, to prevent
    fatal errors (especially likely if the JIRA issue has been moved between projects) .
    """
    component = os.environ.get('JIRA_COMPONENT', '')
    if not component:
        print('No JIRA_COMPONENT variable set, not updating components field')
        return

    if existing_issue:
        # may be a different project if the issue was moved
        project = jira.project(existing_issue.fields.project.key)
    else:
        project = jira.project(os.environ['JIRA_PROJECT'])
    project_components = jira.project_components(project)

    if component not in [c.name for c in project_components]:
        print("JIRA project doesn't contain the configured component, not updating components field")
        return

    print('Setting components field')

    fields['components'] = [{'name': component}]
    # keep any existing components as well
    if existing_issue:
        for component in existing_issue.fields.components:
            if component.name != component:
                fields['components'].append({'name': component.name})


def _get_jira_issue_type(jira, gh_issue):
    """
    Try to map a GitHub label to a JIRA issue type. Matches will happen when the label
    matches the issue type (case insensitive) or when the label has the form "Type: <issuetype>"

    NOTE: This is only suitable for setting on new issues. Changing issue type is unsafe.
    See https://jira.atlassian.com/browse/JRACLOUD-68207
    """
    gh_labels = [lbl['name'] for lbl in gh_issue['labels']]

    issue_types = jira.issue_types()

    for gh_label in gh_labels:
        # Type: Feature Request label should match New Feature issue type in Jira
        if gh_label == 'Type: Feature Request':
            print('GitHub label is \'Type: Feature Request\'. Mapping to New Feature Jira issue type')
            return {'id': JIRA_NEW_FEATURE_TYPE_ID}  # JIRA API needs JSON here
        # Some projects use Label with bug icon represented by ":bug:" in label name.
        # This if matches those to Bug Jira issue type
        if gh_label == 'Type: Bug :bug:':
            print('GitHub label is \'Type: Bug :bug:\'. Mapping to Bug Jira issue type')
            return {'id': JIRA_BUG_TYPE_ID}  # JIRA API needs JSON here
        for issue_type in issue_types:
            type_name = issue_type.name.lower()
            if gh_label.lower() in [type_name, f'type: {type_name}']:
                # a match!
                print(f"Mapping GitHub label '{gh_label}' to JIRA issue type '{issue_type.name}'")
                return {'id': issue_type.id}  # JIRA API needs JSON here

    return None  # updating a field to None seems to cause 'no change' for JIRA


def _find_jira_issue(jira, gh_issue, make_new=False, retries=5):
    """Look for a JIRA issue which has a remote link to the provided GitHub issue.

    Will also find "manually synced" issues that point to each other by name
    (see README), and create the remote link.

    If make_new is True, a new issue will be created if one is not found.

    retries is an internal parameter used when make_new is set, to try and
    avoid races when creating issues (wait a random amount of time and then look
    again). This is useful because often events on a GitHub issue come in a
    flurry (for example if someone creates and then edits or labels an issue),
    # and they're not always processed in order.
    """
    url = gh_issue['html_url']
    jql_query = f'issue in issuesWithRemoteLinksByGlobalId("{url}") order by updated desc'
    print(f'JQL query: {jql_query}')
    res = jira.search_issues(jql_query)
    if not res:
        print(f"WARNING: No JIRA issues have a remote link with globalID '{url}'")

        # Check if the github title ends in (JIRA-KEY). If we can find that JIRA issue and
        # the JIRA issue description contains the
        # GitHub URL, assume this item was manually synced over.
        match = re.search(r'\(([A-Z]+-\d+)\)\s*$', gh_issue['title'])
        if match is not None:
            try:
                issue = jira.issue(match.group(1))
                if gh_issue['html_url'] in issue.fields.description:
                    print(
                        f'Looks like this JIRA issue {issue.key} was manually synced.'
                        'Adding a remote link for future lookups.'
                    )
                    _add_remote_link(jira, issue, gh_issue)
                    return issue
            except jira.exceptions.JIRAError:
                pass  # issue doesn't exist or unauthorized

            # note: not logging anything on failure to avoid
            # potential information leak about other JIRA IDs

        if not make_new:
            return None

        if retries > 0:
            # Wait a random amount of time to see if this JIRA issue is still being created by another
            # GitHub Action. This is a hacky way to try and avoid the case where a GitHub issue is created
            # and edited in a short window of time, and the two GitHub Actions race each other and produce
            # two JIRA issues.
            #
            # The 'create' event will always create the issue, so it should be processed first unless it's
            # delayed by more than (retries * min(range)) seconds. This does mean that it can take up to 5
            # minutes for an old issue (created before the sync was installed), or an issue where the created
            # event sync failed, to sync in.
            print(f'Waiting to see if issue is created by another Action... (retries={retries})')
            time.sleep(random.randrange(30, 60))
            return _find_jira_issue(jira, gh_issue, True, retries - 1)

        print('Creating missing issue in JIRA')
        return _create_jira_issue(jira, gh_issue)

    if len(res) > 1:
        print(f"WARNING: Remote Link globalID '{url}' returns multiple JIRA issues. Using last-updated only.")
    return res[0]


def _leave_jira_issue_comment(jira, event, verb, should_create, jira_issue=None):
    """
    Leave a simple comment that the GitHub issue corresponding to this event was 'verb' by the GitHub user in question.

    If jira_issue is set then this JIRA issue will be updated,
    otherwise the function will find the corresponding synced issue.

    If should_create is set then a new JIRA issue will be opened if one can't be found.
    """
    gh_issue = event['issue']
    is_pr = 'pull_request' in gh_issue

    if jira_issue is None:
        jira_issue = _find_jira_issue(jira, event['issue'], should_create)
        if jira_issue is None:
            return None
    try:
        user = event['sender']['login']
    except KeyError:
        user = gh_issue['user']['login']

    jira.add_comment(
        jira_issue.id,
        f"The [GitHub {'PR' if is_pr else 'issue'}|{gh_issue['html_url']}] has been {verb} by @{user}",
    )

    return jira_issue


def _get_jira_comment_body(gh_comment, body=None):
    """
    Return a JIRA-formatted comment body that corresponds to the provided github comment's text
    or on an existing comment body message (if set).
    """
    if body is None:
        body = _markdown2wiki(gh_comment['body'])
    return f"[GitHub issue comment|{gh_comment['html_url']}] by @{gh_comment['user']['login']}:\n\n{body}"


def _get_jira_label(gh_label):
    """Reformat a github API label item as something suitable for JIRA"""
    return gh_label['name'].replace(' ', '-')
