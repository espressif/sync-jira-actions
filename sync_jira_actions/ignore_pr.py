# Copyright 2019-2026 Espressif Systems (Shanghai) CO LTD
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
"""Decide whether a PR should be ignored for JIRA syncing based on title prefix or author login.

Defaults are always applied; callers can extend them via the
``INPUT_IGNORE_TITLE_PREFIXES`` and ``INPUT_IGNORE_AUTHORS`` environment
variables (comma-separated, case-insensitive).
"""

import os

DEFAULT_IGNORE_TITLE_PREFIXES = (
    'build(deps):',
    'build(deps-dev):',
    '[pre-commit.ci]',
)

DEFAULT_IGNORE_AUTHORS = (
    'dependabot[bot]',
    'pre-commit-ci[bot]',
)


def _parse_csv_env(var_name: str) -> list[str]:
    raw = os.environ.get(var_name, '')
    if not raw:
        return []
    return [entry.strip() for entry in raw.split(',') if entry.strip()]


def get_ignore_title_prefixes() -> list[str]:
    """Return the effective list of title prefixes, lowercased, defaults first."""
    extras = _parse_csv_env('INPUT_IGNORE_TITLE_PREFIXES')
    combined = list(DEFAULT_IGNORE_TITLE_PREFIXES) + extras
    # Lowercase for case-insensitive comparison, preserve order, drop duplicates.
    seen: set[str] = set()
    result: list[str] = []
    for prefix in combined:
        low = prefix.lower()
        if low not in seen:
            seen.add(low)
            result.append(low)
    return result


def get_ignore_authors() -> list[str]:
    """Return the effective list of author logins, lowercased, defaults first."""
    extras = _parse_csv_env('INPUT_IGNORE_AUTHORS')
    combined = list(DEFAULT_IGNORE_AUTHORS) + extras
    seen: set[str] = set()
    result: list[str] = []
    for author in combined:
        low = author.lower()
        if low not in seen:
            seen.add(low)
            result.append(low)
    return result


def should_ignore_pr(title: str | None, author_login: str | None) -> tuple[bool, str | None]:
    """Check whether a PR should be ignored.

    Returns ``(True, reason)`` describing which rule matched, or ``(False, None)``.
    Author match takes precedence over title match because bot authorship is the
    more reliable signal (the same human can easily use any title).
    """
    if author_login:
        author_low = author_login.lower()
        for ignored in get_ignore_authors():
            if author_low == ignored:
                return True, f"author '{author_login}' matches ignored authors list"

    if title:
        title_low = title.lower()
        for prefix in get_ignore_title_prefixes():
            if title_low.startswith(prefix):
                return True, f"title starts with ignored prefix '{prefix}'"

    return False, None
