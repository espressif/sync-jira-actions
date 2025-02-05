# This Justfile contains rules/targets/scripts/commands that are used when
# developing. Unlike a Makefile, running `just <cmd>` will always invoke
# that command. For more information, see https://github.com/casey/just

# This setting will allow passing arguments through to recipes
set positional-arguments

# Custom git log format
gitstyle := '%C(bold blue)%h%C(reset) - %C(bold green)(%ar)%C(reset) %C(white)%s%C(reset) %C(dim white)- %an%C(reset)%C(bold yellow)%d%C(reset)'


# Helper function for quick menu
[private]
@default:
    just --list

# .Edit this Justfile
@edit-just:
    $EDITOR ./Justfile

# Install development environment
@install:
    pip install --require-virtualenv -e '.[dev,test]'
    pip install --require-virtualenv --upgrade pip


# Install and autoupdate pre-commit hooks
@install-pre-commit:
    pre-commit install
    git add .pre-commit-config.yaml
    pre-commit autoupdate
    git reset HEAD --

# Re-compile requirements.txt
@lock-requirements:
    pip-compile --strip-extras --output-file=requirements.txt pyproject.toml > /dev/null


# Run local tests with pytest (config in pyproject.toml)
@test:
    python -m pytest

# Remove caches, builds, reports and other generated files
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
