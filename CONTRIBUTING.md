# Contributing to Competitive Intelligence Pipeline

Thank you for your interest in contributing! This document provides guidelines for contributing to the project.

## Development Setup

### Prerequisites

- Python 3.11+
- Docker & Docker Compose
- Git

### Local Development

```bash
# 1. Fork and clone the repository
git clone https://github.com/yourusername/mcp-copilot-a2a.git
cd mcp-copilot-a2a

# 2. Create a virtual environment
python -m venv venv
source venv/bin/activate  # On Windows: venv\Scripts\activate

# 3. Install dependencies
pip install -r requirements.txt

# 4. Configure environment
cp .env.example .env
# Add your API keys to .env

# 5. Start ChromaDB (required for tests)
docker run -d -p 8001:8000 --name chromadb chromadb/chroma:latest

# 6. Run tests
pytest -v
```

## Running Tests Locally

### Quick Test Suite

```bash
# All tests
pytest -v

# Specific test file
pytest tests/test_schemas.py -v
pytest tests/test_pipeline.py -v

# With coverage report
pytest --cov=. --cov-report=html
open htmlcov/index.html  # View coverage report
```

### Test Categories

- **Schema Tests** (`tests/test_schemas.py`): Pydantic model validation
- **Pipeline Tests** (`tests/test_pipeline.py`): Business logic and integration
- **Edge Case Tests** (`tests/test_pipeline.py::TestEdgeCases`): Error handling

### Running Individual Tests

```bash
# Single test
pytest tests/test_pipeline.py::TestValidateInput::test_empty_company_rejected -v

# Test class
pytest tests/test_pipeline.py::TestEdgeCases -v
```

## Code Quality Standards

### Before Submitting a PR

Run these checks locally:

```bash
# 1. All tests pass
pytest -v

# 2. Code compiles
python -m py_compile api.py orchestrator.py schemas/messages.py

# 3. No print statements (use structlog instead)
grep -r "print(" . --include="*.py" --exclude-dir=tests

# 4. Type hints present (if mypy installed)
mypy . --ignore-missing-imports

# 5. Format code (optional but recommended)
black .
```

### Code Standards

✅ **Required**:
- All tests pass
- No bare `except:` clauses (use specific exceptions)
- No `print()` statements in production code (use `structlog`)
- Docstrings on all public functions and classes
- Type hints on all function signatures
- No hardcoded strings (use `constants.py` or `os.getenv()`)

⚠️ **Recommended**:
- Follow PEP 8 style guide
- Keep functions under 50 lines
- Maximum line length: 100 characters
- Use descriptive variable names

## Branch Naming

Use descriptive branch names with prefixes:

- `feature/` - New features
  - Example: `feature/add-pricing-agent`
- `fix/` - Bug fixes
  - Example: `fix/rate-limit-retry`
- `chore/` - Maintenance tasks
  - Example: `chore/update-dependencies`
- `docs/` - Documentation only
  - Example: `docs/improve-readme`
- `test/` - Test improvements
  - Example: `test/add-edge-cases`

## Pull Request Process

### Before Creating a PR

1. **Update from main**:
   ```bash
   git checkout main
   git pull origin main
   git checkout your-branch
   git rebase main
   ```

2. **Run full test suite**:
   ```bash
   pytest -v
   ```

3. **Check code quality**:
   ```bash
   # No bare excepts
   grep -r "except:" . --include="*.py"
   
   # No print statements
   grep -r "print(" . --include="*.py" --exclude-dir=tests
   ```

### PR Checklist

Copy this checklist into your PR description:

```markdown
## PR Checklist

- [ ] All tests pass locally (`pytest -v`)
- [ ] No bare `except:` clauses
- [ ] No `print()` statements in production code
- [ ] Docstrings added for new functions/classes
- [ ] Type hints on all new function signatures
- [ ] No hardcoded strings (used `constants.py` or env vars)
- [ ] Updated `README.md` if adding user-facing features
- [ ] Updated `.env.example` if adding new environment variables
- [ ] Added tests for new functionality
- [ ] Branch is rebased on latest main
```

### PR Description Template

```markdown
## Description
Brief description of what this PR does.

## Type of Change
- [ ] Bug fix (non-breaking change which fixes an issue)
- [ ] New feature (non-breaking change which adds functionality)
- [ ] Breaking change (fix or feature that would cause existing functionality to not work as expected)
- [ ] Documentation update

## How Has This Been Tested?
Describe the tests you ran and how to reproduce them.

## Screenshots (if applicable)
Add screenshots for UI changes.

## Related Issues
Closes #123
```

### Review Process

1. Automated checks run (GitHub Actions, if configured)
2. At least one maintainer reviews the code
3. Reviewer may request changes
4. Once approved, maintainer will merge

## Adding New Features

### Adding a New Agent

See the **Extending the Project** section in README.md for detailed instructions on adding agents to the pipeline.

### Adding a New Tool

1. Create tool in `mcp_server/tools/your_tool.py`
2. Implement with retry logic using `tenacity`
3. Add comprehensive error handling
4. Register in MCP server
5. Add tests in `tests/`
6. Update documentation

### Adding New Environment Variables

1. Add to `constants.py` if it's a default value
2. Add to `.env.example` with description
3. Document in README.md configuration table
4. Use `os.getenv()` with sensible defaults

## Testing Guidelines

### Writing Good Tests

```python
def test_descriptive_name():
    """Clear docstring explaining what this tests."""
    # Arrange: Set up test data
    input_data = {"company": "TestCorp"}
    
    # Act: Execute the code under test
    result = validate_input(input_data)
    
    # Assert: Verify the results
    assert result["error"] is None
    assert result["company"] == "TestCorp"
```

### Test Naming Convention

- `test_<function>_<scenario>_<expected_behavior>`
- Example: `test_validate_input_empty_company_rejected`

### Mocking External Services

Always mock external API calls in tests:

```python
@patch("mcp_server.tools.search._tavily_search")
def test_search_with_mock(mock_search):
    mock_search.return_value = [{"url": "...", "title": "..."}]
    result = search_competitors("TestCorp")
    assert len(result) > 0
```

## Commit Message Guidelines

### Format

```
<type>(<scope>): <subject>

<body>

<footer>
```

### Types

- `feat`: New feature
- `fix`: Bug fix
- `docs`: Documentation only
- `style`: Code style changes (formatting, etc.)
- `refactor`: Code refactoring
- `test`: Adding or updating tests
- `chore`: Maintenance tasks

### Examples

```bash
# Good commits
feat(api): add /compare endpoint for head-to-head analysis
fix(orchestrator): handle rate limit errors gracefully
docs(readme): add extending section with agent example
test(edge-cases): add tests for ChromaDB unavailable scenario

# Bad commits
fix: bug
update: changes
feat: new stuff
```

## Getting Help

- **Questions**: Open a GitHub Discussion
- **Bugs**: Open a GitHub Issue with reproduction steps
- **Security**: Email security@yourdomain.com (do not open public issues)

## Code of Conduct

### Our Standards

- Be respectful and inclusive
- Welcome newcomers
- Focus on constructive feedback
- Accept criticism gracefully
- Prioritize community well-being

### Unacceptable Behavior

- Harassment or discrimination
- Trolling or insulting comments
- Personal or political attacks
- Publishing private information
- Unprofessional conduct

## Recognition

Contributors will be recognized in:
- README.md Contributors section
- Release notes for significant contributions
- GitHub's contributor graph

## Questions?

If you have questions about contributing, please:
1. Check existing documentation
2. Search closed issues
3. Open a new discussion

Thank you for contributing to making competitive intelligence accessible to everyone! 🚀
