import importlib
import sys

import pytest


@pytest.fixture
def ignore_pr_module(monkeypatch):
    """Reload the module for each test so env var reads are re-evaluated."""
    sys.path.insert(0, 'sync_jira_actions')
    import ignore_pr

    importlib.reload(ignore_pr)
    return ignore_pr


@pytest.fixture(autouse=True)
def clean_env(monkeypatch):
    monkeypatch.delenv('INPUT_IGNORE_TITLE_PREFIXES', raising=False)
    monkeypatch.delenv('INPUT_IGNORE_AUTHORS', raising=False)


class TestDefaults:
    def test_default_title_prefix_build_deps(self, ignore_pr_module):
        ignore, reason = ignore_pr_module.should_ignore_pr(
            'build(deps): bump actions/download-artifact from 6 to 7', 'somebody'
        )
        assert ignore is True
        assert 'title' in reason.lower()

    def test_default_title_prefix_build_deps_dev(self, ignore_pr_module):
        ignore, reason = ignore_pr_module.should_ignore_pr('build(deps-dev): bump pytest from 8 to 9', 'somebody')
        assert ignore is True
        assert 'title' in reason.lower()

    def test_default_title_prefix_pre_commit_ci(self, ignore_pr_module):
        ignore, reason = ignore_pr_module.should_ignore_pr('[pre-commit.ci] pre-commit autoupdate', 'somebody')
        assert ignore is True
        assert 'title' in reason.lower()

    def test_default_title_prefix_is_case_insensitive(self, ignore_pr_module):
        ignore, _ = ignore_pr_module.should_ignore_pr('BUILD(DEPS): bump x', 'somebody')
        assert ignore is True

        ignore, _ = ignore_pr_module.should_ignore_pr('[Pre-Commit.CI] pre-commit autoupdate', 'somebody')
        assert ignore is True

    def test_default_author_dependabot(self, ignore_pr_module):
        ignore, reason = ignore_pr_module.should_ignore_pr('Some normal title', 'dependabot[bot]')
        assert ignore is True
        assert 'author' in reason.lower()

    def test_default_author_pre_commit_ci(self, ignore_pr_module):
        ignore, reason = ignore_pr_module.should_ignore_pr('Some normal title', 'pre-commit-ci[bot]')
        assert ignore is True
        assert 'author' in reason.lower()

    def test_default_author_is_case_insensitive(self, ignore_pr_module):
        ignore, _ = ignore_pr_module.should_ignore_pr('Some normal title', 'Dependabot[Bot]')
        assert ignore is True


class TestNotIgnored:
    def test_regular_pr_is_not_ignored(self, ignore_pr_module):
        ignore, reason = ignore_pr_module.should_ignore_pr('Fix memory leak in WiFi driver', 'alice')
        assert ignore is False
        assert reason is None

    def test_title_containing_but_not_starting_with_prefix(self, ignore_pr_module):
        """Prefix match only: 'build(deps):' in the middle should not match."""
        ignore, _ = ignore_pr_module.should_ignore_pr('Refactor build(deps): handling', 'alice')
        assert ignore is False


class TestExtendingDefaults:
    def test_custom_title_prefix_extends_defaults(self, ignore_pr_module, monkeypatch):
        monkeypatch.setenv('INPUT_IGNORE_TITLE_PREFIXES', 'chore(deps):, [custom]')
        importlib.reload(ignore_pr_module)

        ignore, reason = ignore_pr_module.should_ignore_pr('chore(deps): bump thing', 'alice')
        assert ignore is True
        assert 'title' in reason.lower()

        ignore, _ = ignore_pr_module.should_ignore_pr('[custom] some pr', 'alice')
        assert ignore is True

        ignore, _ = ignore_pr_module.should_ignore_pr('build(deps): bump x', 'alice')
        assert ignore is True

    def test_custom_authors_extends_defaults(self, ignore_pr_module, monkeypatch):
        monkeypatch.setenv('INPUT_IGNORE_AUTHORS', 'myorg-bot[bot]')
        importlib.reload(ignore_pr_module)

        ignore, reason = ignore_pr_module.should_ignore_pr('Some PR', 'myorg-bot[bot]')
        assert ignore is True
        assert 'author' in reason.lower()

        ignore, _ = ignore_pr_module.should_ignore_pr('Some PR', 'dependabot[bot]')
        assert ignore is True

    def test_empty_env_var_keeps_defaults(self, ignore_pr_module, monkeypatch):
        monkeypatch.setenv('INPUT_IGNORE_TITLE_PREFIXES', '')
        monkeypatch.setenv('INPUT_IGNORE_AUTHORS', '')
        importlib.reload(ignore_pr_module)

        ignore, _ = ignore_pr_module.should_ignore_pr('build(deps): bump x', 'alice')
        assert ignore is True

        ignore, _ = ignore_pr_module.should_ignore_pr('Some PR', 'dependabot[bot]')
        assert ignore is True

    def test_whitespace_and_blank_entries_tolerated(self, ignore_pr_module, monkeypatch):
        monkeypatch.setenv('INPUT_IGNORE_TITLE_PREFIXES', '  chore(deps): ,  , [custom]  ,')
        monkeypatch.setenv('INPUT_IGNORE_AUTHORS', ' , my-bot[bot] , ,  ')
        importlib.reload(ignore_pr_module)

        ignore, _ = ignore_pr_module.should_ignore_pr('chore(deps): bump', 'alice')
        assert ignore is True

        ignore, _ = ignore_pr_module.should_ignore_pr('[custom] foo', 'alice')
        assert ignore is True

        ignore, _ = ignore_pr_module.should_ignore_pr('Some PR', 'my-bot[bot]')
        assert ignore is True


class TestNoneInputs:
    def test_none_title_is_handled(self, ignore_pr_module):
        ignore, reason = ignore_pr_module.should_ignore_pr(None, 'alice')
        assert ignore is False
        assert reason is None

    def test_none_author_is_handled(self, ignore_pr_module):
        ignore, reason = ignore_pr_module.should_ignore_pr('Fix bug', None)
        assert ignore is False
        assert reason is None

    def test_both_none(self, ignore_pr_module):
        ignore, reason = ignore_pr_module.should_ignore_pr(None, None)
        assert ignore is False
        assert reason is None

    def test_none_title_with_ignored_author(self, ignore_pr_module):
        ignore, reason = ignore_pr_module.should_ignore_pr(None, 'dependabot[bot]')
        assert ignore is True
        assert 'author' in reason.lower()

    def test_none_author_with_ignored_title(self, ignore_pr_module):
        ignore, reason = ignore_pr_module.should_ignore_pr('build(deps): bump x', None)
        assert ignore is True
        assert 'title' in reason.lower()


class TestGetters:
    def test_get_ignore_title_prefixes_returns_defaults(self, ignore_pr_module):
        prefixes = ignore_pr_module.get_ignore_title_prefixes()
        assert 'build(deps):' in prefixes
        assert 'build(deps-dev):' in prefixes
        assert '[pre-commit.ci]' in prefixes

    def test_get_ignore_authors_returns_defaults(self, ignore_pr_module):
        authors = ignore_pr_module.get_ignore_authors()
        assert 'dependabot[bot]' in authors
        assert 'pre-commit-ci[bot]' in authors

    def test_get_ignore_title_prefixes_appends_custom(self, ignore_pr_module, monkeypatch):
        monkeypatch.setenv('INPUT_IGNORE_TITLE_PREFIXES', 'chore(deps):')
        importlib.reload(ignore_pr_module)
        prefixes = ignore_pr_module.get_ignore_title_prefixes()
        assert 'build(deps):' in prefixes
        assert 'chore(deps):' in prefixes

    def test_get_ignore_authors_appends_custom(self, ignore_pr_module, monkeypatch):
        monkeypatch.setenv('INPUT_IGNORE_AUTHORS', 'my-bot[bot]')
        importlib.reload(ignore_pr_module)
        authors = ignore_pr_module.get_ignore_authors()
        assert 'dependabot[bot]' in authors
        assert 'my-bot[bot]' in authors
