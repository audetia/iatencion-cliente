"""
Test file to validate that fixtures are working correctly.

This file tests that all fixtures create data properly and maintain
referential integrity in the test database.
"""

import pytest
from datetime import datetime
from sqlalchemy import func


class TestFixturesValidation:
    """Test suite to validate fixture data creation and integrity."""
    
    def test_users_created(self, sample_users):
        """Test that users are created correctly."""
        assert len(sample_users) == 4
        
        # Check specific users
        maria = next(u for u in sample_users if u.email == "maria.garcia@empresa.com")
        assert maria.name == "María García"
        assert maria.is_verified is True
        
        # Check inactive user
        test_user = next(u for u in sample_users if u.email == "test.user@example.com")
        assert test_user.is_verified is False
    
    def test_email_accounts_created(self, sample_email_accounts, sample_users):
        """Test that email accounts are created correctly."""
        assert len(sample_email_accounts) == 5
        
        # Check relationships
        maria = sample_users[0]
        maria_accounts = [acc for acc in sample_email_accounts if acc.user_id == maria.id]
        assert len(maria_accounts) == 2
        
        # Check inactive account
        inactive_accounts = [acc for acc in sample_email_accounts if not acc.is_active]
        assert len(inactive_accounts) == 1
        assert inactive_accounts[0].email == "soporte@consultoria.com"
    
    def test_qa_data_created(self, sample_qa_data, sample_users):
        """Test that Q&A data is created correctly."""
        questions = sample_qa_data["questions"]
        variants = sample_qa_data["variants"]
        answers = sample_qa_data["answers"]
        
        assert len(questions) == 6
        assert len(answers) == 6
        assert len(variants) >= 15  # At least 15 variants
        
        # Check that each question has variants
        for question in questions:
            question_variants = [v for v in variants if v.question_id == question.id]
            assert len(question_variants) >= 3  # Each question should have at least 3 variants
        
        # Check embeddings
        for variant in variants:
            assert variant.embedding is not None
            assert len(variant.embedding) == 1536  # Correct dimension
    
    def test_automations_created(self, sample_automations, sample_email_accounts):
        """Test that automations are created correctly."""
        automations = sample_automations["automations"]
        response_autos = sample_automations["response_automations"]
        forward_autos = sample_automations["forward_automations"]
        
        assert len(automations) == 5
        assert len(response_autos) == 3
        assert len(forward_autos) == 2
        
        # Check active automations
        active_automations = [a for a in automations if a.is_active]
        assert len(active_automations) == 4  # One is inactive
        
        # Check draft mode
        draft_automations = [a for a in automations if a.is_draft_mode]
        assert len(draft_automations) == 1
    
    def test_statistics_created(self, sample_statistics, db_session):
        """Test that statistics are created correctly."""
        email_processed = sample_statistics["email_processed"]
        monthly_usage = sample_statistics["monthly_usage"]
        
        # Should have many processed emails (roughly 60 days of data)
        assert len(email_processed) > 500
        
        # Should have monthly usage records
        assert len(monthly_usage) >= 4  # At least 4 users with some data
        
        # Verify distribution of email actions
        responded_count = len([e for e in email_processed if e.email_responded])
        forwarded_count = len([e for e in email_processed if e.email_forwarded])
        
        # Roughly 35% responded, 15% forwarded
        total = len(email_processed)
        assert 0.25 < responded_count / total < 0.45
        assert 0.05 < forwarded_count / total < 0.25
    
    def test_statistics_consistency(self, complete_test_data, db_session):
        """Test that statistics are internally consistent."""
        from tests.conftest import assert_statistics_consistency
        
        users = complete_test_data["users"]
        
        # Check consistency for each user
        for user in users[:3]:  # Skip unverified user
            assert_statistics_consistency(db_session, user.id)
    
    def test_referential_integrity(self, complete_test_data, db_session):
        """Test that all foreign key relationships are valid."""
        from src.models import EmailAccount, Question, Automation
        
        # Test email accounts point to valid users
        accounts = db_session.query(EmailAccount).all()
        user_ids = [u.id for u in complete_test_data["users"]]
        for account in accounts:
            assert account.user_id in user_ids
        
        # Test automations point to valid email accounts
        automations = db_session.query(Automation).all()
        account_ids = [a.id for a in accounts]
        for automation in automations:
            assert automation.email_account_id in account_ids
    
    def test_active_user_fixture(self, active_user_with_data):
        """Test the convenience fixture for active user."""
        data = active_user_with_data
        
        assert data["user"].email == "maria.garcia@empresa.com"
        assert len(data["email_accounts"]) == 2
        assert len(data["questions"]) == 3
        assert len(data["automations"]) >= 2
    
    def test_complete_data_fixture(self, complete_test_data):
        """Test that complete_test_data fixture includes all data."""
        assert "users" in complete_test_data
        assert "email_accounts" in complete_test_data
        assert "qa_data" in complete_test_data
        assert "automations" in complete_test_data
        assert "statistics" in complete_test_data
        
        # Verify data is loaded
        assert len(complete_test_data["users"]) == 4
        assert len(complete_test_data["email_accounts"]) == 5


class TestDatabaseOperations:
    """Test database operations with fixture data."""
    
    def test_query_user_statistics(self, complete_test_data, db_session):
        """Test querying user statistics."""
        from src.models import EmailProcessed, EmailAccount
        
        maria = complete_test_data["users"][0]
        
        # Query emails processed for María
        maria_emails = db_session.query(EmailProcessed).join(
            EmailAccount
        ).filter(
            EmailAccount.user_id == maria.id
        ).count()
        
        assert maria_emails > 0
    
    def test_search_similar_questions(self, sample_qa_data, db_session):
        """Test vector similarity search."""
        from tests.conftest import generate_mock_embedding
        
        # Generate embedding for a test query
        test_query = "¿Cuánto cuestan sus servicios?"
        test_embedding = generate_mock_embedding(test_query)
        
        # This would normally use pgvector similarity search
        # For now, just verify embeddings exist
        variants = sample_qa_data["variants"]
        assert all(v.embedding is not None for v in variants)
    
    def test_get_active_automations(self, sample_automations, sample_email_accounts, db_session):
        """Test querying active automations for an account."""
        from src.models import Automation
        
        account = sample_email_accounts[0]  # María's main account
        
        active_autos = db_session.query(Automation).filter(
            Automation.email_account_id == account.id,
            Automation.is_active == True
        ).all()
        
        assert len(active_autos) >= 1
        
        # Check types
        response_autos = [a for a in active_autos if a.type.value == "response"]
        assert len(response_autos) >= 1


if __name__ == "__main__":
    pytest.main([__file__, "-v"]) 