# Tests for IA Atención Cliente

This directory contains tests for the components of the IA Atención Cliente project.

## Setup

Make sure you have the required dependencies:

```bash
pip install -r requirements.txt
```

## Running Tests

### Run all tests

```bash
pytest
```

### Run specific test file

```bash
pytest tests/test_email_tools.py
```

### Run with verbose output

```bash
pytest -v
```

### Run with coverage report

```bash
pytest --cov=src
```

Note: You need to install `pytest-cov` for coverage reporting:

```bash
pip install pytest-cov
```

## Email Connection Testing

The `test_email_tools.py` file includes two ways to test email connections:

1. **Unit tests with mocks**: These don't require actual email credentials and test the code logic.

2. **Connection testing script**: Similar to the reference script, this can be run directly to test actual connections:

```bash
python -c "from tests.test_email_tools import test_connections; test_connections()"
```

### Environment Variables

For the connection test, you need to set these environment variables:

```
EMAIL_USER=your-email@example.com
EMAIL_PASS=your-password
SMTP_SERVER=smtp.example.com  # Optional, falls back to config
SMTP_PORT=587                # Optional, falls back to config
IMAP_SERVER=imap.example.com  # Optional, falls back to config
```

You can set these in a `.env` file in the project root.
