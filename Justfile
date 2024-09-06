# This Justfile contains rules/targets/scripts/commands that are used when
# developing. Unlike a Makefile, running `just <cmd>` will always invoke
# that command. For more information, see https://github.com/casey/just

# This setting will allow passing arguments through to recipes
set positional-arguments

# Parse current version from pyproject.toml
current_version := `grep -Po 'version\s*=\s*"\K[^"]*' pyproject.toml | grep -Eo '[0-9]+\.[0-9]+\.[0-9]+'`

# Custom git log format
gitstyle := '%C(bold blue)%h%C(reset) - %C(bold green)(%ar)%C(reset) %C(white)%s%C(reset) %C(dim white)- %an%C(reset)%C(bold yellow)%d%C(reset)'


# Helper function for quick menu
[private]
@default:
    just --list


# .Edit this Justfile
@edit-just:
    $EDITOR ./Justfile


# PROJECT: Install development environment
@install:
    pip install --require-virtualenv -e '.[dev,test]'
    pip install --require-virtualenv --upgrade pip


# PROJECT: Install and autoupdate pre-commit hooks
@install-pre-commit:
    pre-commit install
    git add .pre-commit-config.yaml
    pre-commit autoupdate
    git reset HEAD --

# PROJECT: Re-compile requirements.txt
@lock-requirements:
    pip-compile --strip-extras --output-file=requirements.txt pyproject.toml > /dev/null


# PROJECT: Release version info, commits since last release)
@version:
    cz bump --dry-run | grep -E 'change\(bump\)|tag to create|increment detected'; \
    echo "\nCommits since last release:"; \
    git log -n 30 --graph --pretty="{{gitstyle}}" v{{current_version}}..HEAD


# TESTS: Run local tests with pytest (config in pyproject.toml)
@test:
    python -m pytest


# DOCKER: Build Docker image
docker-build:
    docker build -t espressif/sample-project:latest .


# DOCKER: Run in Docker container
docker-run:
    docker run espressif/sample-project


# Build and run Docker
docker:
    just docker-build
    just docker-run

# PROJECT: Remove caches, builds, reports and other generated files
@clean:
    rm -rf \
        dist \
        build \
        *.egg-info \
        **/__pycache__/ \
        .pytest_cache \
        .mypy_cache \
        .coverage* \
        .ruff_cache \
        :


# GIT: Revert the last commit - keeping changes staged
@uncommit:
    git reset --soft HEAD~1


# GIT: Fix failed commit message
@recommit:
    git commit --edit --file=$(git rev-parse --git-dir)/COMMIT_EDITMSG


# GIT: Show commits only on current branch
@branch-commits base="v1":
    if git rev-parse --verify "{{base}}" > /dev/null 2>&1; then \
        git log --first-parent --no-merges --graph --pretty="{{gitstyle}}" {{base}}..HEAD; \
    else \
        echo 'E: Provide base (target) branch as argument to `just branch-commits <base-branch>`' >&2; \
        exit 128; \
    fi
