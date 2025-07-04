"""
Example tests using the new fixtures to test statistics functionality.

This demonstrates how the fixtures can be used to test real functionality
with realistic data.
"""

import pytest
from datetime import datetime, timedelta
from sqlalchemy import func


class TestStatisticsWithRealData:
    """Test statistics functionality with realistic fixture data."""
    
    def test_get_daily_statistics(self, complete_test_data, db_manager, db_session):
        """Test getting daily statistics for a user."""
        maria = complete_test_data["users"][0]
        
        # Get statistics for the last 7 days
        end_date = datetime.now()
        start_date = end_date - timedelta(days=7)
        
        result = db_manager.get_daily_statistics(
            email_account_id=complete_test_data["email_accounts"][0].id,
            date_range=(start_date, end_date)
        )
        
        assert result["success"] is True
        assert len(result["daily_stats"]) == 7
        
        # Verify each day has data
        for day_stat in result["daily_stats"]:
            assert "date" in day_stat
            assert "emails_processed" in day_stat
            assert "emails_responded" in day_stat
            assert "emails_forwarded" in day_stat
            assert day_stat["emails_processed"] >= 0
    
    def test_get_category_distribution(self, complete_test_data, db_manager):
        """Test getting category distribution."""
        account = complete_test_data["email_accounts"][0]
        
        # Get category distribution for the last 30 days
        end_date = datetime.now()
        start_date = end_date - timedelta(days=30)
        
        result = db_manager.get_category_distribution(
            email_account_id=account.id,
            date_range=(start_date, end_date)
        )
        
        assert result["success"] is True
        assert "category_distribution" in result
        
        # Should have multiple categories
        categories = result["category_distribution"]
        assert len(categories) > 0
        
        # Verify category structure
        for category in categories:
            assert "category" in category
            assert "count" in category
            assert "percentage" in category
            assert category["count"] > 0
            assert 0 <= category["percentage"] <= 100
    
    def test_calculate_time_saved(self, complete_test_data, db_manager):
        """Test time saved calculation."""
        # María should have significant time saved
        maria_account = complete_test_data["email_accounts"][0]
        
        result = db_manager.calculate_time_saved(maria_account.id)
        
        assert result["success"] is True
        assert result["time_saved"]["total_minutes"] > 0
        assert result["time_saved"]["total_hours"] > 0
        assert result["time_saved"]["emails_processed"] > 0
        
        # Verify calculation (5 minutes per email)
        expected_minutes = result["time_saved"]["emails_processed"] * 5
        assert result["time_saved"]["total_minutes"] == expected_minutes
    
    def test_monthly_usage_aggregation(self, complete_test_data, db_session):
        """Test that monthly usage is correctly aggregated."""
        from src.models import UserUsageMonthly
        
        # Get María's monthly usage
        maria = complete_test_data["users"][0]
        current_month = datetime.now().month
        current_year = datetime.now().year
        
        monthly_usage = db_session.query(UserUsageMonthly).filter_by(
            user_id=maria.id,
            year=current_year,
            month=current_month
        ).first()
        
        assert monthly_usage is not None
        assert monthly_usage.emails_processed > 0
        assert monthly_usage.emails_responded > 0
        assert monthly_usage.tokens_used > 0
        
        # Verify proportions make sense
        response_rate = monthly_usage.emails_responded / monthly_usage.emails_processed
        assert 0.1 < response_rate < 0.6  # Between 10% and 60%
    
    def test_qa_usage_tracking(self, complete_test_data, db_session):
        """Test tracking which Q&A pairs are used."""
        from src.models import EmailProcessed
        
        # Find emails that used Q&A
        emails_with_qa = db_session.query(EmailProcessed).filter(
            EmailProcessed.question_id.isnot(None)
        ).all()
        
        assert len(emails_with_qa) > 0
        
        # Verify Q&A tracking fields
        for email in emails_with_qa[:10]:  # Check first 10
            assert email.question_id is not None
            assert email.similarity_score is not None
            assert 0.0 <= email.similarity_score <= 1.0
            assert email.email_responded is True  # Should have responded if Q&A used
    
    def test_automation_effectiveness(self, complete_test_data, db_session):
        """Test measuring automation effectiveness."""
        from src.models import EmailProcessed, Automation
        
        # Get active automations
        active_automations = db_session.query(Automation).filter_by(
            is_active=True
        ).all()
        
        for automation in active_automations:
            # Count emails processed by this automation's account
            email_count = db_session.query(func.count(EmailProcessed.id)).filter_by(
                email_account_id=automation.email_account_id
            ).scalar()
            
            if email_count > 0:
                # Count automated actions
                automated_count = db_session.query(func.count(EmailProcessed.id)).filter(
                    EmailProcessed.email_account_id == automation.email_account_id,
                    (EmailProcessed.email_responded == True) | (EmailProcessed.email_forwarded == True)
                ).scalar()
                
                automation_rate = automated_count / email_count
                assert 0.0 <= automation_rate <= 1.0


class TestUsageServiceIntegration:
    """Test usage service with fixture data."""
    
    def test_track_email_processed(self, complete_test_data, db_manager, db_session):
        """Test tracking a new processed email."""
        from src.services.usage_service import UsageService
        from tests.conftest import get_test_email_content
        
        usage_service = UsageService(db_manager)
        maria = complete_test_data["users"][0]
        maria_account = complete_test_data["email_accounts"][0]
        
        # Get current counts
        from src.models import EmailProcessed
        before_count = db_session.query(EmailProcessed).filter_by(
            email_account_id=maria_account.id
        ).count()
        
        # Track new email
        email_data = {
            "email_account_id": maria_account.id,
            "action": "responded",
            "category": "consulta_comercial",
            "tokens_used": 250,
            "question_id": complete_test_data["qa_data"]["questions"][0].id,
            "similarity_score": 0.89
        }
        
        result = usage_service.track_email_processed(
            user_id=maria.id,
            email_data=email_data
        )
        
        assert result["success"] is True
        
        # Verify record was created
        db_session.expire_all()  # Refresh from DB
        after_count = db_session.query(EmailProcessed).filter_by(
            email_account_id=maria_account.id
        ).count()
        
        assert after_count == before_count + 1
    
    def test_validate_usage_limits(self, complete_test_data, db_manager):
        """Test usage limit validation."""
        from src.services.usage_service import UsageService
        
        usage_service = UsageService(db_manager)
        
        # Test with active user (should have usage but within limits)
        maria = complete_test_data["users"][0]
        
        result = usage_service.validate_usage_limits(maria.id)
        
        assert "can_process" in result
        assert "current_usage" in result
        assert "limits" in result
        
        # María should be able to process more emails (using Free tier limits)
        assert result["can_process"] is True
        assert result["current_usage"]["emails_processed"] > 0
        assert result["current_usage"]["emails_processed"] < result["limits"]["email_process_limit"]


if __name__ == "__main__":
    pytest.main([__file__, "-v"]) 