<div align="center">
  <h1>GitHub to JIRA Sync (GitHub Action)</h1>
  <img src="docs/sync-jira-actions.png" alt="GitHub to JIRA Sync logo" width="400">
  <br>
  <br>
  <!-- GitHub Badges -->
   <img alt="release" src="https://img.shields.io/github/v/release/espressif/sync-jira-actions" />
   <img alt="tests" src="https://github.com/espressif/sync-jira-actions/actions/workflows/python-test.yml/badge.svg" />
   <img alt="codeql" src="https://github.com/espressif/sync-jira-actions/actions/workflows/github-code-scanning/codeql/badge.svg?branch=v1" />
</div>
GitHub to JIRA Sync GitHub Action is a solution for one-way synchronization of GitHub issues into Espressif JIRA projects.
<br>
<br>
This action automates the integration of your GitHub repositories with JIRA projects by automatically creating corresponding JIRA tickets for new GitHub issues and pull requests, as well as managing comments within these issues and pull requests from external contributors.

<hr>

- [Features](#features)
- ['Synced From' Link Details](#synced-from-link-details)
  - [Key Features and Considerations](#key-features-and-considerations)
- [Manually Linking a GitHub Issue to JIRA](#manually-linking-a-github-issue-to-jira)
  - [Step-by-Step Guide](#step-by-step-guide)
  - [Automation Trigger](#automation-trigger)
  - [Important Note](#important-note)
- [Issue Type Synchronization](#issue-type-synchronization)
  - [How It Works](#how-it-works)
- [Limitations](#limitations)
  - [What's Not Synced](#whats-not-synced)
- [Usage Instructions for GitHub to JIRA Issue Sync Action](#usage-instructions-for-github-to-jira-issue-sync-action)
  - [Syncing New Issues to JIRA](#syncing-new-issues-to-jira)
  - [Syncing New Issue Comments to JIRA](#syncing-new-issue-comments-to-jira)
  - [Syncing New Pull Requests to JIRA](#syncing-new-pull-requests-to-jira)
- [Manually Syncing Issues and Pull Requests to JIRA](#manually-syncing-issues-and-pull-requests-to-jira)
  - [Configuration for Manual Sync](#configuration-for-manual-sync)
  - [Workflow Setup](#workflow-setup)
- [Environment Variables and Secrets Configuration](#environment-variables-and-secrets-configuration)
  - [Important Consideration:](#important-consideration)
- [Project Issues](#project-issues)
- [Contributing](#contributing)

## Features

- **Automatic Issue Creation**: When a new GitHub issue is opened, a matching JIRA issue is created within the specified project.
- **Markdown Conversion**: The body of the GitHub issue is converted to JIRA Wiki format using [markdown2confluence](http://chunpu.github.io/markdown2confluence/browser/).
- **Custom Field Mapping**: A JIRA custom field named "GitHub Reference" is populated with the URL of the GitHub issue.
- **Issue Title Sync**: The title of the GitHub issue is updated to include the JIRA issue key.
- **Bi-directional Comment Sync**: Comments added to a GitHub issue are mirrored in the corresponding JIRA issue. Edits and deletions are also reflected.
- **Label Synchronization**: Labels added or removed from the GitHub issue are similarly updated in the JIRA issue.
- **Remote Issue Link**: After syncing, a [Remote Issue Link](https://developer.atlassian.com/server/jira/platform/creating-remote-issue-links/) is created on the JIRA issue for easy reference back to the GitHub issue.

## 'Synced From' Link Details

Once a JIRA issue is created and synced from GitHub, a [Remote Issue Link](https://developer.atlassian.com/server/jira/platform/creating-remote-issue-links/) is automatically generated for the JIRA issue. This link includes a "globalID" that corresponds to the URL of the GitHub issue. This mechanism ensures that any future changes to the GitHub issue are tracked and reflected in the JIRA issue, maintaining a consistent link between the two platforms.

### Key Features and Considerations

- **Persistent Synchronization**: The Remote Issue Link facilitates ongoing updates to JIRA issues that are moved to other JIRA projects, assuming the remote issue link is also transferred and the GitHub Action's JIRA user has access to the new project.
- **Link Management**: To sever the connection between a GitHub issue and a JIRA issue, simply remove the Remote Issue Link. Be aware, however, that subsequent updates to the GitHub issue may trigger the creation of a new JIRA issue to ensure continuity of tracking.
- **Manual Links**: It's important to note that Remote Issue Links created manually for GitHub issues won't contain the necessary globalID. Since JIRA's search functionality for Remote Issue Links relies exclusively on globalID and not the URL, such manually created links cannot facilitate automated syncing.

This design ensures that the integration between GitHub and JIRA remains dynamic and adaptable to changes, providing a robust solution for tracking issues across both platforms.

## Manually Linking a GitHub Issue to JIRA

Creating a Remote Issue Link with the appropriate `globalID` directly through the JIRA Web UI is not feasible without leveraging the JIRA API. However, you can manually establish a connection between an existing GitHub issue and a JIRA issue by following these steps:

### Step-by-Step Guide

1. **Verify Unique Linking**: Ensure that the GitHub issue is not already linked to another JIRA issue. Use JIRA's advanced search with the query `issue in issuesWithRemoteLinksByGlobalId("GitHub Issue URL")` to check for existing links.
2. **Update JIRA Issue Description**: Include the URL of the GitHub issue in the description field of the JIRA issue. This step is crucial for the GitHub action to recognize and link the issues.
3. **Amend GitHub Issue Title**: Append the JIRA issue key to the end of the GitHub issue title within parentheses, e.g., `GitHub Issue title (JIRAKEY-123)`. This modification helps in identifying the linked issues easily.

### Automation Trigger

Upon the next update to the GitHub issue (which might occur immediately if you follow the steps sequentially), the GitHub action will automatically generate the "Synced from" link, establishing a manual link between the issues.

### Important Note

If the GitHub issue URL is not present in the JIRA issue description, the GitHub action will not create a link. This safeguard is designed to prevent unauthorized or unintended updates to JIRA issues from external sources.

## Issue Type Synchronization

The GitHub to JIRA Issue Sync Action intelligently creates JIRA issues with specific types based on the labels attached to the GitHub issue. This feature ensures that the issue types in JIRA accurately reflect the nature or category of the issue as determined in GitHub.

### How It Works

- **Label Matching**: When a new GitHub issue is created, the action checks for labels that either directly match the name of a JIRA issue type or follow the format `Type: <issue type>`. The search for matching labels is case insensitive, ensuring flexibility in label naming conventions.
- **Environment Variable Fallback**: In cases where no labels match any issue type, the action refers to the `JIRA_ISSUE_TYPE` environment variable to determine the issue type for the new JIRA issue. If this environment variable is not defined, the default issue type used is "Task".
- **Handling Label Changes**: If the labels on a GitHub issue are modified after creation, these changes will not alter the issue type of the already created JIRA issue. This limitation arises from the [inability of the JIRA REST API to safely change an issue type](https://jira.atlassian.com/browse/JRACLOUD-68207) when the new type is associated with a different workflow. In such scenarios, the action will leave a comment in the JIRA issue to inform about the label change in GitHub.

## Limitations

There are certain limitations to the data and events that can be synchronized:

### What's Not Synced

- **Labels**: The action does not sync labels between GitHub and JIRA, with the exception of labels that match JIRA issue types. This means that general labels used for categorization or prioritization in GitHub won't automatically reflect in JIRA.
- **Transitions**: Changes in the status of a GitHub issue, such as closing, reopening, or deleting, do not automatically result in the corresponding transition of the JIRA issue's status. Instead, these actions result in a comment being added to the linked JIRA issue to record the event. This design choice accounts for scenarios where a GitHub issue might be closed by its reporter, but the underlying problem it documents still requires attention and resolution within the JIRA project.

## Usage Instructions for GitHub to JIRA Issue Sync Action

This GitHub Action provides a comprehensive solution for integrating GitHub with JIRA, ensuring that issues, comments, and pull requests in GitHub are seamlessly synced to JIRA. Below are the setups to synchronize different types of activities from GitHub to JIRA.

### Syncing New Issues to JIRA

Automatically creates a corresponding JIRA issue when a new issue is opened in GitHub.

```yaml
---
# This GitHub Actions workflow synchronizes GitHub issues, comments, and pull requests with Jira.
# It triggers on new issues, issue comments, and on a scheduled basis.
# The workflow uses a custom action to perform the synchronization with Jira (espressif/sync-jira-actions).

name: 🔷 Sync to Jira.

on: issues
concurrency: jira_issues

jobs:
  sync_issues_to_jira:
    runs-on: ubuntu-latest
    steps:
      - uses: actions/checkout@v4

      - name: Sync GitHub issues to Jira project
        uses: espressif/sync-jira-actions@v1
        with:
          cron_job: ${{ github.event_name == 'schedule' && 'true' || '' }}
        env:
          GITHUB_TOKEN: ${{ secrets.GITHUB_TOKEN }}
          JIRA_PASS: ${{ secrets.JIRA_PASS }}
          JIRA_PROJECT: SOMEPROJECT # define the JIRA project here
          JIRA_COMPONENT: SOMECOMPONENT # define (optional) JIRA component here
          JIRA_URL: ${{ secrets.JIRA_URL }}
          JIRA_USER: ${{ secrets.JIRA_USER }}
          JIRA_PROJECT: IDFSYNTEST # <------Update for Jira key of your project
          JIRA_COMPONENT: GitHub
```

### Syncing New Issue Comments to JIRA

Ensures that comments made on GitHub issues are also reflected in the corresponding JIRA issue.

```yaml
name: Sync issue comments to JIRA
on: issue_comment
```

### Syncing New Pull Requests to JIRA

Due to security reasons related to the privileges of PR submitter's repositories, syncing pull requests requires a different approach, using a cron job to regularly check for and sync new pull requests.

```yaml
name: Sync remaining PRs to Jira

on:
  schedule:
    - cron: "0 * * * *"
concurrency: jira_issues

jobs:
  sync_prs_to_jira:
    runs-on: ubuntu-latest
    steps:
      - uses: actions/checkout@v4

      - name: Sync PRs to Jira project
        uses: espressif/sync-jira-actions@v1
        with:
          cron_job: true
        env:
          GITHUB_TOKEN: ${{ secrets.GITHUB_TOKEN }}
          JIRA_PASS: ${{ secrets.JIRA_PASS }}
          JIRA_PROJECT: SOMEPROJECT # define the JIRA project here
          JIRA_COMPONENT: SOMECOMPONENT # define (optional) JIRA component here
          JIRA_URL: ${{ secrets.JIRA_URL }}
          JIRA_USER: ${{ secrets.JIRA_USER }}
```

## Manually Syncing Issues and Pull Requests to JIRA

For cases where you need to manually sync issues and pull requests that were not automatically captured by the [Sync a new issue to Jira](#sync-a-new-issue-to-jira) and [Sync a new pull request to Jira](#sync-a-new-pull-request-to-jira) workflows, this GitHub Action provides a solution. It allows for the manual synchronization of both new and old issues and pull requests directly to your JIRA project.

### Configuration for Manual Sync

This action introduces two parameters for manual triggering:

- `action`: Specifies the action to be performed, with a default value of `mirror-issues`.
- `issue-numbers`: Lists the numbers of the issues and pull requests that you wish to sync to JIRA.

### Workflow Setup

To set up the manual sync action, include the following workflow in your GitHub repository:

```yaml
name: Manually trigger sync issue to Jira

on:
  workflow_dispatch:
    inputs:
      action:
        description: "Action to be performed"
        required: true
        default: "mirror-issues"
      issue-numbers:
        description: "Issue numbers"
        required: true
concurrency: jira_issues

jobs:
  sync_issues_to_jira:
    name: Sync issues to Jira
    runs-on: ubuntu-latest
    steps:
      - uses: actions/checkout@v4

      - name: Sync GitHub issues to Jira project
        uses: espressif/sync-jira-actions@v1
        env:
          GITHUB_TOKEN: ${{ secrets.GITHUB_TOKEN }}
          JIRA_PASS: ${{ secrets.JIRA_PASS }}
          JIRA_PROJECT: SOMEPROJECT # define the JIRA project here
          JIRA_COMPONENT: SOMECOMPONENT # define (optional) JIRA component here
          JIRA_URL: ${{ secrets.JIRA_URL }}
          JIRA_USER: ${{ secrets.JIRA_USER }}
```

This workflow can be triggered manually from the GitHub Actions tab in your repository, allowing you to specify the issues or pull requests to be synced by entering their numbers.

This ensures that even items not caught by the automatic sync process can still be integrated into your JIRA project for tracking and management.

## Environment Variables and Secrets Configuration

The GitHub to JIRA Issue Sync workflow requires the configuration of specific environment variables and secrets to operate effectively. These settings ensure the correct creation and updating of issues within your JIRA project based on activities in your GitHub repository.

Below is a detailed table outlining the necessary configurations:

| Variable/Secret   | Description                                                                                  | Requirement |
| ----------------- | -------------------------------------------------------------------------------------------- | ----------- |
| `JIRA_PROJECT`    | Specifies the Jira project to synchronize with.                                              | Mandatory   |
| `JIRA_ISSUE_TYPE` | Specifies the JIRA issue type for new issues. Defaults to "Task" if not set.                 | Optional    |
| `JIRA_COMPONENT`  | The name of a JIRA component to add to every synced issue. The component must exist in JIRA. | Optional    |
| `JIRA_URL`        | The main URL of your JIRA instance.                                                          | Inherited   |
| `JIRA_USER`       | The username used for logging into JIRA (basic auth).                                        | Inherited   |
| `JIRA_PASS`       | The JIRA token (for token auth) or password (for basic auth) used for logging in.            | Inherited   |

### Important Consideration:

- **GitHub Organizational Secrets**: `JIRA_URL`, `JIRA_USER`, `JIRA_PASS` - These secrets are **inherited from the GitHub organizational secrets, as they are common to all projects within the organization**. It is advised not to set these secrets at the individual repository level to avoid conflicts and ensure a unified configuration across all projects.

- **Token as JIRA_PASS**: When using a token for `JIRA_PASS`, prefix the token value with `token:` (e.g., `token:Xyz123**************ABC`). This prefix helps distinguish between password and token types, and it will be removed by the script before making the API call.

---

## Project Issues

If you encounter any issues, feel free to report them in the project's issues or create Pull Request with your suggestion.

## Contributing

📘 If you are interested in contributing to this project, see the [project Contributing Guide](CONTRIBUTING.md).
