# CHANGELOG

> All notable changes to this project are documented in this file.
> This list is not exhaustive - only important changes, fixes, and new features in the code are reflected here.

<sub>The format is based on [Keep a Changelog](https://keepachangelog.com/en/1.0.0/),     [Semantic Versioning](https://semver.org/spec/v2.0.0.html) and     [Conventional Commits](https://www.conventionalcommits.org/en/v1.0.0/)
</sub>

---

## Unreleased

### ✨ New features

- **action**: updated this action from Docker to Composite type *(Tomas Sebestik - d926676)*

### 🐛 Bug fixes

- add dynamic ref to action.yml file for development testing *(Tomas Sebestik - 39cd704)*

### 📖 Documentation

- **caller-workflow**: add caller workflow for easy copy to target repo *(Tomas Sebestik - d651127)*

---

## v0.1.1 (2024-02-14)


- docs: add CONTRIBUTING guide, update README
- ci(project-structure): package and tools config by pyproject.toml
- - add commitizen support to pyproject.toml
- add Danger for GitHub
- add pre-commit hook for codespell
- add pre-commit hook prettier - formatting Markdown files
- add pre-commit workflow to CI
- refactor: refactor to Python 3.11, refactor Dockerfile (Bookworm, node20)
- - refactor(tests): add tests and GH workflow for pytest
- refactor: move source code to src directory

## v0.1.0 (2024-02-07)


- feat(init): original code from github-actions repo
- Init
