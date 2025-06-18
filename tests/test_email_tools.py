import os
import uuid
import pytest
import email
import imaplib
import smtplib
from unittest.mock import patch, MagicMock
from email.mime.multipart import MIMEMultipart
from email.mime.text import MIMEText
from dotenv import load_dotenv
from pathlib import Path

# Import the module to test
from src.tools.EmailTools import EmailToolsClass, EMAIL_CONFIG

# Load environment variables for test configuration
load_dotenv()

class TestEmailTools:
    """Test suite for EmailTools module."""

    @pytest.fixture
    def email_tools(self):
        """Fixture to create an instance of EmailToolsClass with mocked config."""
        with patch.dict('src.tools.EmailTools.EMAIL_CONFIG', {
            'email_user': 'test@example.com',
            'email_pass': 'password123',
            'imap_server': 'imap.example.com',
            'smtp_server': 'smtp.example.com',
            'smtp_port': 587
        }):
            yield EmailToolsClass()

    def test_init_with_valid_config(self, email_tools):
        """Test initialization with valid configuration."""
        assert email_tools.email_user == 'test@example.com'
        assert email_tools.email_pass == 'password123'
        assert email_tools.imap_server == 'imap.example.com'
        assert email_tools.smtp_server == 'smtp.example.com'
        assert email_tools.smtp_port == 587

    def test_init_with_invalid_config(self):
        """Test initialization with missing required configuration."""
        with patch.dict('src.tools.EmailTools.EMAIL_CONFIG', {
            'email_user': '',  # Missing required field
            'email_pass': 'password123',
            'imap_server': 'imap.example.com',
            'smtp_server': 'smtp.example.com'
        }):
            with pytest.raises(ValueError) as excinfo:
                EmailToolsClass()
            assert "Missing required configuration" in str(excinfo.value)

    @patch('imaplib.IMAP4_SSL')
    def test_connect_to_inbox_success(self, mock_imap, email_tools):
        """Test successful connection to inbox."""
        # Configure the mock
        mock_conn = MagicMock()
        mock_imap.return_value = mock_conn
        
        # Call the method
        result = email_tools.connect_to_inbox()
        
        # Assertions
        mock_imap.assert_called_once_with('imap.example.com')
        mock_conn.login.assert_called_once_with('test@example.com', 'password123')
        mock_conn.select.assert_called_once_with('inbox')
        assert result == mock_conn

    @patch('imaplib.IMAP4_SSL')
    def test_connect_to_inbox_failure(self, mock_imap, email_tools):
        """Test failed connection to inbox."""
        # Configure the mock to raise an exception
        mock_conn = MagicMock()
        mock_imap.return_value = mock_conn
        mock_conn.login.side_effect = imaplib.IMAP4.error("Login failed")
        
        # Call the method and assert it raises the expected exception
        with pytest.raises(ConnectionError) as excinfo:
            email_tools.connect_to_inbox()
        assert "Failed to connect to email server" in str(excinfo.value)

# Simple script to test actual connections
def test_connections():
    """
    Standalone function to test actual email connections.
    This doesn't use pytest assertions but prints status like the reference script.
    
    Run this directly to test actual connections.
    """
    import logging
    logging.basicConfig(level=logging.INFO, format='%(message)s')
    
    # Load environment variables
    load_dotenv()
    
    # Get email settings
    smtp_server = os.getenv("SMTP_SERVER", EMAIL_CONFIG["smtp_server"])
    smtp_port = int(os.getenv("SMTP_PORT", str(EMAIL_CONFIG["smtp_port"])))
    imap_server = os.getenv("IMAP_SERVER", EMAIL_CONFIG["imap_server"])
    email_user = os.getenv("EMAIL_USER", EMAIL_CONFIG["email_user"])
    email_pass = os.getenv("EMAIL_PASS", EMAIL_CONFIG["email_pass"])
    
    print(f"\nTesting connection with:")
    print(f"IMAP Server: {imap_server}")
    print(f"SMTP Server: {smtp_server}")
    print(f"SMTP Port: {smtp_port}")
    print(f"Email User: {email_user}")
    
    # Test IMAP
    try:
        print("\nTesting IMAP connection...")
        mail = imaplib.IMAP4_SSL(imap_server)
        mail.login(email_user, email_pass)
        print("✅ IMAP connection successful")
        
        mail.select("inbox")
        print("✅ Inbox selected")
        mail.logout()
    except Exception as e:
        print(f"❌ Error connecting to IMAP server: {str(e)}")
        pytest.fail(f"IMAP connection failed: {str(e)}")
    
    # Test SMTP
    try:
        print("\nTesting SMTP connection...")
        
        if smtp_port == 465:
            print("Using SMTP_SSL for secure connection")
            server = smtplib.SMTP_SSL(smtp_server, smtp_port)
        else:
            print("Using SMTP with STARTTLS")
            server = smtplib.SMTP(smtp_server, smtp_port)
            server.starttls()
        
        server.login(email_user, email_pass)
        print("✅ SMTP connection successful")
        server.quit()
    except Exception as e:
        print(f"❌ Error connecting to SMTP server: {str(e)}")
        pytest.fail(f"SMTP connection failed: {str(e)}")
    
    print("\n✅ SUCCESS: Both IMAP and SMTP connections passed!")
    print("You can now use these settings in your application.")

if __name__ == "__main__":
    # When run directly, we want to return True/False for script usage
    try:
        test_connections()
        print("All tests passed!")
    except Exception as e:
        print(f"Tests failed: {str(e)}")
        exit(1) 