# Test Fixtures Documentation

## Overview

This document describes the test fixtures available for creating realistic test data in the email automation system. These fixtures use a real test database (`POSTGRES_TEST_URL`) to provide comprehensive test scenarios.

## Setup

1. **Environment Variable**: Ensure `POSTGRES_TEST_URL` is set in your `.env` file:

   ```
   POSTGRES_TEST_URL=postgresql://user:pass@host:port/test_db
   ```

2. **Install Dependencies**:
   ```bash
   pip install pytest-postgresql pytest-factoryboy faker
   ```

## Available Fixtures

### Database Fixtures

#### `test_engine`

- **Scope**: Session
- **Purpose**: Creates a test database engine with pgvector extension
- **Cleanup**: Drops all tables after test session

#### `db_session`

- **Scope**: Function
- **Purpose**: Provides a clean database session for each test
- **Cleanup**: Rolls back after each test

#### `db_manager`

- **Scope**: Function
- **Purpose**: Provides a configured DatabaseManager instance

### Data Fixtures

#### `sample_users`

Creates 4 test users with different profiles:

- **María García** (maria.garcia@empresa.com): Power user, 180 days old
- **Juan Martínez** (juan.martinez@startup.es): Moderate user, 90 days old
- **Ana López** (ana.lopez@consultoria.com): New user, 15 days old
- **Test User** (test.user@example.com): Unverified/inactive user

#### `sample_email_accounts`

Creates 5 email accounts distributed among users:

- María: 2 accounts (main + sales)
- Juan: 1 account
- Ana: 2 accounts (1 inactive)

#### `sample_qa_data`

Creates questions, answers, and variants with embeddings:

- 6 questions total
- ~18 variants with mock embeddings
- Different topics per user (business, technical, support)

#### `sample_automations`

Creates 5 automations:

- 3 response automations
- 2 forward automations
- Mix of active/inactive and draft modes

#### `sample_statistics`

Creates ~2000 email processing records over 60 days:

- Realistic daily patterns (weekends have less activity)
- 35% responded, 15% forwarded, 50% categorized
- Monthly usage aggregations

### Convenience Fixtures

#### `complete_test_data`

Loads all test data at once:

```python
def test_with_all_data(complete_test_data):
    users = complete_test_data["users"]
    accounts = complete_test_data["email_accounts"]
    # ... etc
```

#### `active_user_with_data`

Gets María (most active user) with all her related data:

```python
def test_active_user(active_user_with_data):
    user = active_user_with_data["user"]
    accounts = active_user_with_data["email_accounts"]
    questions = active_user_with_data["questions"]
```

## Usage Examples

### Basic Test with Users

```python
def test_user_creation(sample_users):
    assert len(sample_users) == 4
    maria = sample_users[0]
    assert maria.email == "maria.garcia@empresa.com"
```

### Testing Statistics

```python
def test_statistics(sample_statistics, db_session):
    email_records = sample_statistics["email_processed"]
    assert len(email_records) > 500

    # Query specific data
    from src.models import EmailProcessed
    recent_emails = db_session.query(EmailProcessed).filter(
        EmailProcessed.processed_at >= datetime.now() - timedelta(days=7)
    ).all()
```

### Testing with Complete Data

```python
def test_integration(complete_test_data, db_manager):
    # Access all data
    users = complete_test_data["users"]
    accounts = complete_test_data["email_accounts"]

    # Test real functionality
    result = db_manager.get_daily_statistics(
        email_account_id=accounts[0].id,
        date_range=(start_date, end_date)
    )
```

## Data Characteristics

### Volume

- **Users**: 4 (3 active, 1 inactive)
- **Email Accounts**: 5 (4 active, 1 inactive)
- **Questions**: 6 with ~18 variants
- **Automations**: 5 (4 active, 1 inactive)
- **Email Records**: ~2000 over 60 days
- **Monthly Usage**: 8 records (current + previous month)

### Patterns

- **Activity**: María > Juan > Ana > Test User
- **Email Volume**: 2-25 emails/day depending on user
- **Weekend Pattern**: 30% of weekday volume
- **Response Rate**: ~35% of emails
- **Forward Rate**: ~15% of emails

### Relationships

All data maintains referential integrity:

- EmailAccount → User
- Question → User
- Automation → EmailAccount
- EmailProcessed → EmailAccount
- ResponseAutomation → Question

## Utility Functions

### `assert_statistics_consistency(db_session, user_id)`

Verifies that monthly aggregations match actual email counts.

### `get_test_email_content(category)`

Generates test email content for different categories:

- "consulta_comercial"
- "soporte_tecnico"
- "logistica"

### `generate_mock_embedding(text)`

Creates deterministic mock embeddings (1536 dimensions) based on text hash.

## Best Practices

1. **Use appropriate fixtures**: Don't load all data if you only need users
2. **Check relationships**: Fixtures maintain proper foreign keys
3. **Respect data patterns**: Test data follows realistic usage patterns
4. **Clean sessions**: Each test gets a clean session, changes don't persist

## Running Tests

```bash
# Run all fixture validation tests
pytest tests/test_fixtures_validation.py -v

# Run tests with fixtures
pytest tests/test_statistics_with_fixtures.py -v

# Run specific test
pytest tests/test_statistics_with_fixtures.py::TestStatisticsWithRealData::test_get_daily_statistics -v
```

## Troubleshooting

### Database Connection Issues

- Verify `POSTGRES_TEST_URL` is correct
- Ensure test database exists
- Check pgvector extension is installed

### Fixture Loading Issues

- Check all dependencies are installed
- Verify no circular dependencies in fixtures
- Use `-vv` flag for detailed output

### Performance

- First run creates all data (slower)
- Subsequent tests in same session reuse data
- Use function-scoped fixtures for isolation
