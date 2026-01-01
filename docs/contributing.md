# Contributing

Any and all contributions and involvement with the project is welcome. The easiest way to begin contributing is to check out the open issues on GitHub.

## Documentation

The documentation is built using [mkdocs](https://www.mkdocs.org/). All documentation is in markdown format, and can be found in `./docs/`

To preview documentation locally:

```shell
mkdocs serve
```

Then visit `http://127.0.0.1:8000` in your browser.

## Contributing Code

### Step 1: Prerequisites

`fastapi-tasks` uses [uv](https://docs.astral.sh/uv/) for dependency management.
Please install uv before continuing.

Minimum supported Python version is `3.10`.

### Step 2: Clone the Repository

```shell
git clone https://github.com/uriyyo/fastapi-tasks
cd fastapi-tasks
```

### Step 3: Install Dependencies

To install all dependencies, run:

```shell
uv sync --dev
```

To install docs requirements, run:

```shell
uv pip install -r docs_requirements.txt
```

### Step 4: Make Your Changes

If you want to add a new feature, please create an issue first and describe your idea.

For bug fixes, please include:
- A description of the bug
- Steps to reproduce
- Expected behavior
- Actual behavior

### Step 5: Run Pre-commit Hooks

Before creating a commit, run pre-commit hooks:

```shell
uv run pre-commit run --all-files
```

You can also install pre-commit hooks to run automatically before each commit:

```shell
uv run pre-commit install
```

### Step 6: Run Tests

To run tests:

```shell
uv run pytest tests
```

To run tests with coverage:

```shell
uv run pytest tests --cov=fastapi_tasks
```

### Step 7: Update Documentation

If you added new features or changed behavior:

1. Update relevant documentation in `docs/`
2. Add examples if appropriate
3. Preview changes with `mkdocs serve`

### Step 8: Create a Pull Request

After you have done all changes, create a pull request:

1. Push your changes to a fork
2. Open a pull request against the `main` branch
3. Describe your changes
4. Link any related issues
5. Wait for review

## Code Style

We use:
- **Black** for code formatting
- **isort** for import sorting
- **mypy** for type checking
- **ruff** for linting

Pre-commit hooks will enforce these automatically.

## Writing Tests

All new features should include tests:

```python
import pytest
from fastapi import FastAPI
from httpx import AsyncClient
from fastapi_tasks import Tasks, add_tasks

pytestmark = pytest.mark.asyncio


async def test_my_feature(app: FastAPI, client: AsyncClient) -> None:
    """Test description"""
    
    # Define task
    async def my_task() -> None:
        pass
    
    # Define endpoint
    @app.post("/test")
    async def test_endpoint(tasks: Tasks) -> dict:
        tasks.schedule(my_task)
        return {"status": "ok"}
    
    # Make request
    response = await client.post("/test")
    
    # Assert
    assert response.status_code == 200
    assert response.json() == {"status": "ok"}
```

## Documentation Standards

When writing documentation:

1. **Be clear and concise** - Short sentences, simple words
2. **Provide examples** - Show code, not just descriptions
3. **Use proper formatting** - Code blocks, tables, lists
4. **Add warnings/tips** - Use admonitions for important info
5. **Link related pages** - Help users navigate
6. **Test your examples** - Make sure code actually works

Example documentation structure:

```markdown
# Feature Name

Brief description of the feature.

## Basic Usage

```python
# Simple example
from fastapi_tasks import Tasks

tasks.schedule(my_function)
```

## Advanced Usage

More complex examples...

## Reporting Bugs

If you find a bug:

1. Check if it's already reported in [GitHub Issues](https://github.com/uriyyo/fastapi-tasks/issues)
2. If not, create a new issue with:
   - Python version
   - `fastapi-tasks` version
   - Minimal code to reproduce
   - Expected vs actual behavior
   - Full error traceback

## Feature Requests

For feature requests:

1. Open an issue describing the feature
2. Explain the use case
3. Provide examples if possible
4. Discuss before implementing

## Questions?

If you have questions:

- Check the [FAQ](faq/faq.md)
- Read the [documentation](index.md)
- Ask in [GitHub Discussions](https://github.com/uriyyo/fastapi-tasks/discussions)

Thank you for contributing! 🎉
