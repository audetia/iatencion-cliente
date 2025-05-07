import os
import re
import uuid
import base64
import logging
import imaplib
import smtplib
import email
from bs4 import BeautifulSoup
from datetime import datetime, timedelta
from email.mime.text import MIMEText
from email.mime.multipart import MIMEMultipart
from email.mime.base import MIMEBase
from email import encoders
from typing import List, Optional, Tuple, Dict
from pathlib import Path

# Configure logging
logger = logging.getLogger(__name__)
logger.setLevel(logging.INFO)

# Email configuration - these should be loaded from environment variables or config file
EMAIL_CONFIG = {
    "smtp_server": os.getenv("SMTP_SERVER", "smtp.gmail.com"),
    "smtp_port": int(os.getenv("SMTP_PORT", "587")),
    "imap_server": os.getenv("IMAP_SERVER", "imap.gmail.com"),
    "email_user": os.getenv("EMAIL_USER"),
    "email_pass": os.getenv("EMAIL_PASS"),
    "check_interval": int(os.getenv("EMAIL_CHECK_INTERVAL", "300")),  # 5 minutes default
    "allowed_domains": os.getenv("EMAIL_ALLOWED_DOMAINS", "").split(","),
    "monitor_address": os.getenv("EMAIL_MONITOR_ADDRESS", "")
}

class EmailToolsClass:
    def __init__(self):
        """Initialize email tools with IMAP and SMTP connections."""
        self._validate_config()
        self.email_user = EMAIL_CONFIG["email_user"]
        self.email_pass = EMAIL_CONFIG["email_pass"]
        self.imap_server = EMAIL_CONFIG["imap_server"]
        self.smtp_server = EMAIL_CONFIG["smtp_server"]
        self.smtp_port = EMAIL_CONFIG["smtp_port"]
        
    def _validate_config(self) -> None:
        """Validate that all required configuration is present."""
        required_fields = ["email_user", "email_pass", "imap_server", "smtp_server"]
        missing = [field for field in required_fields if not EMAIL_CONFIG.get(field)]
        if missing:
            raise ValueError(f"Missing required configuration: {', '.join(missing)}")

    def connect_to_inbox(self) -> imaplib.IMAP4_SSL:
        """
        Establishes a connection to the IMAP server and selects the inbox folder.
        
        Returns:
            imaplib.IMAP4_SSL: The authenticated IMAP connection
            
        Raises:
            ConnectionError: When unable to connect to the server
        """
        try:
            logger.info(f"Connecting to IMAP server {self.imap_server}")
            mail = imaplib.IMAP4_SSL(self.imap_server)
            mail.login(self.email_user, self.email_pass)
            logger.debug("Successfully logged in to email account")
            mail.select("inbox")
            logger.debug("Selected inbox folder")
            return mail
        except imaplib.IMAP4.error as e:
            logger.error(f"IMAP connection error: {str(e)}")
            raise ConnectionError(f"Failed to connect to email server: {str(e)}")
        except Exception as e:
            logger.error(f"Unexpected error connecting to inbox: {str(e)}")
            raise

    def fetch_unanswered_emails(self, max_results: int = 50) -> List[Dict]:
        """
        Fetches all emails included in unanswered threads from the last 8 hours.
        
        Args:
            max_results: Maximum number of recent emails to fetch
            
        Returns:
            List of dictionaries, each representing a thread with its emails
        """
        try:
            # Get recent emails
            recent_emails = self.fetch_recent_emails(max_results)
            if not recent_emails:
                return []

            # Get all draft replies to exclude them
            drafts = self.fetch_draft_replies()
            threads_with_drafts = {draft['threadId'] for draft in drafts}

            # Process new emails
            seen_threads = set()
            unanswered_emails = []
            
            for email_msg in recent_emails:
                thread_id = self._get_thread_id(email_msg)
                if thread_id not in seen_threads and thread_id not in threads_with_drafts:
                    seen_threads.add(thread_id)
                    email_info = self._get_email_info(email_msg)
                    if self._should_skip_email(email_info):
                        continue
                    unanswered_emails.append(email_info)
                    
            return unanswered_emails

        except Exception as e:
            logger.error(f"Error fetching unanswered emails: {str(e)}")
            return []

    def fetch_recent_emails(self, max_results: int = 50) -> List[email.message.Message]:
        """
        Fetches recent unread emails from the last 8 hours.
        
        Args:
            max_results: Maximum number of emails to fetch
            
        Returns:
            List of email.message.Message objects
        """
        try:
            mail = self.connect_to_inbox()
            
            # Calculate time range (8 hours ago)
            time_ago = datetime.now() - timedelta(hours=8)
            date_string = time_ago.strftime("%d-%b-%Y")
            
            # Search for unread emails from the last 8 hours
            search_query = f'(UNSEEN SINCE "{date_string}")'
            result, data = mail.search(None, search_query)
            
            if result != "OK":
                logger.warning(f"Email search failed: {result}")
                return []
                
            email_ids = data[0].split()[:max_results]  # Limit to max_results
            
            emails = []
            for e_id in email_ids:
                try:
                    result, msg_data = mail.fetch(e_id, "(RFC822)")
                    if result != "OK":
                        continue
                        
                    email_msg = email.message_from_bytes(msg_data[0][1])
                    emails.append(email_msg)
                    
                    # Mark as read
                    mail.store(e_id, '+FLAGS', '\\Seen')
                except Exception as e:
                    logger.error(f"Error fetching email {e_id}: {str(e)}")
                    
            mail.logout()
            return emails
            
        except Exception as e:
            logger.error(f"Error in fetch_recent_emails: {str(e)}")
            return []

    def fetch_draft_replies(self) -> List[Dict]:
        """
        Fetches all draft email replies.
        
        Returns:
            List of dictionaries containing draft information
        """
        try:
            mail = self.connect_to_inbox()
            
            # Search for drafts folder
            result, folders = mail.list()
            draft_folder = None
            for folder in folders:
                if b"\\Drafts" in folder:
                    draft_folder = folder.decode().split('"/"')[-1].strip('"')
                    break
                    
            if not draft_folder:
                logger.warning("No drafts folder found")
                return []
                
            # Select drafts folder and get messages
            mail.select(draft_folder)
            result, data = mail.search(None, "ALL")
            
            if result != "OK":
                return []
                
            draft_ids = data[0].split()
            drafts = []
            
            for d_id in draft_ids:
                try:
                    result, msg_data = mail.fetch(d_id, "(RFC822)")
                    if result != "OK":
                        continue
                        
                    msg = email.message_from_bytes(msg_data[0][1])
                    thread_id = self._get_thread_id(msg)
                    
                    drafts.append({
                        "draft_id": d_id.decode(),
                        "threadId": thread_id,
                        "id": msg.get("Message-ID", "")
                    })
                except Exception as e:
                    logger.error(f"Error fetching draft {d_id}: {str(e)}")
                    
            mail.logout()
            return drafts
            
        except Exception as e:
            logger.error(f"Error fetching drafts: {str(e)}")
            return []

    def create_draft_reply(self, initial_email: Dict, reply_text: str) -> Optional[Dict]:
        """
        Creates a draft reply to an email.
        
        Args:
            initial_email: Dictionary containing original email information
            reply_text: Text content for the reply
            
        Returns:
            Dictionary containing draft information or None if creation fails
        """
        try:
            # Create the reply message
            message = self._create_reply_message(initial_email, reply_text)
            
            # Connect to IMAP and save to drafts
            mail = self.connect_to_inbox()
            
            # Find Drafts folder
            result, folders = mail.list()
            draft_folder = None
            for folder in folders:
                if b"\\Drafts" in folder:
                    draft_folder = folder.decode().split('"/"')[-1].strip('"')
                    break
                    
            if not draft_folder:
                raise ValueError("No drafts folder found")
                
            # Save message to drafts folder
            mail.append(draft_folder, '\\Draft', None, message.as_bytes())
            
            # Get the saved draft ID
            result, data = mail.search(None, "(SUBJECT %s)" % message["subject"])
            if result != "OK":
                raise Exception("Failed to find saved draft")
                
            draft_id = data[0].split()[-1]  # Get the last message with matching subject
            
            mail.logout()
            
            return {
                "draft_id": draft_id.decode(),
                "threadId": initial_email["threadId"],
                "id": message["Message-ID"]
            }
            
        except Exception as e:
            logger.error(f"Error creating draft reply: {str(e)}")
            return None

    def send_reply(self, initial_email: Dict, reply_text: str) -> Optional[Dict]:
        """
        Sends a reply to an email.
        
        Args:
            initial_email: Dictionary containing original email information
            reply_text: Text content for the reply
            
        Returns:
            Dictionary containing sent message information or None if sending fails
        """
        try:
            # Create the reply message
            message = self._create_reply_message(initial_email, reply_text, send=True)
            
            # Connect to SMTP server
            if self.smtp_port == 465:
                server = smtplib.SMTP_SSL(self.smtp_server, self.smtp_port)
            else:
                server = smtplib.SMTP(self.smtp_server, self.smtp_port)
                server.starttls()
                
            server.login(self.email_user, self.email_pass)
            
            # Send the message
            server.send_message(message)
            server.quit()
            
            return {
                "id": message["Message-ID"],
                "threadId": initial_email["threadId"]
            }
            
        except Exception as e:
            logger.error(f"Error sending reply: {str(e)}")
            return None

    def _create_reply_message(self, email_info: Dict, reply_text: str, send: bool = False) -> MIMEMultipart:
        """Creates a reply message with proper headers and formatting."""
        message = self._create_html_email_message(
            recipient=email_info["sender"],
            subject=email_info["subject"],
            reply_text=reply_text
        )

        # Set threading headers
        if email_info["messageId"]:
            message["In-Reply-To"] = email_info["messageId"]
            message["References"] = f"{email_info['references']} {email_info['messageId']}".strip()
            
            if send:
                message["Message-ID"] = f"<{uuid.uuid4()}@{self.smtp_server}>"
                
        return message

    def _get_thread_id(self, msg: email.message.Message) -> str:
        """
        Extracts or generates a thread ID from an email message.
        Uses References and In-Reply-To headers to maintain threading.
        """
        references = msg.get("References", "").split()
        in_reply_to = msg.get("In-Reply-To", "")
        message_id = msg.get("Message-ID", "")
        
        # Try to get thread ID from existing headers
        if references:
            return references[0].strip("<>")  # First reference is usually thread root
        elif in_reply_to:
            return in_reply_to.strip("<>")
        elif message_id:
            return message_id.strip("<>")
        else:
            # Generate a new thread ID if none exists
            return f"{uuid.uuid4()}@{self.smtp_server}"

    def _get_email_info(self, msg: email.message.Message) -> Dict:
        """
        Extracts relevant information from an email message.
        
        Args:
            msg: email.message.Message object
            
        Returns:
            Dictionary containing email information
        """
        # Extract headers
        headers = {}
        for key in ["message-id", "references", "in-reply-to", "from", "to", "subject"]:
            headers[key] = msg.get(key, "")
            
        # Get sender email address
        from_name, from_addr = email.utils.parseaddr(headers["from"])
        
        return {
            "id": headers["message-id"].strip("<>"),
            "threadId": self._get_thread_id(msg),
            "messageId": headers["message-id"],
            "references": headers["references"],
            "sender": from_addr,
            "subject": headers["subject"],
            "body": self._get_email_body(msg),
        }

    def _get_email_body(self, msg: email.message.Message) -> str:
        """
        Extracts the email body, prioritizing text/plain over text/html.
        Handles multipart messages and strips HTML if necessary.
        """
        body = ""
        if msg.is_multipart():
            # Get the first text/plain part, or fall back to first text/html
            for part in msg.walk():
                if part.get_content_type() == "text/plain":
                    body = part.get_payload(decode=True).decode()
                    break
                elif part.get_content_type() == "text/html" and not body:
                    html_content = part.get_payload(decode=True).decode()
                    body = self._extract_main_content_from_html(html_content)
        else:
            # Handle single part messages
            if msg.get_content_type() == "text/plain":
                body = msg.get_payload(decode=True).decode()
            elif msg.get_content_type() == "text/html":
                html_content = msg.get_payload(decode=True).decode()
                body = self._extract_main_content_from_html(html_content)
                
        return self._clean_body_text(body)

    def _extract_main_content_from_html(self, html_content: str) -> str:
        """Extracts main visible content from HTML."""
        soup = BeautifulSoup(html_content, 'html.parser')
        for tag in soup(['script', 'style', 'head', 'meta', 'title']):
            tag.decompose()
        return soup.get_text(separator='\n', strip=True)

    def _clean_body_text(self, text: str) -> str:
        """Cleans up the email body text by removing extra spaces and newlines."""
        return re.sub(r'\s+', ' ', text.replace('\r', '').replace('\n', '')).strip()

    def _create_html_email_message(self, recipient: str, subject: str, reply_text: str) -> MIMEMultipart:
        """Creates an HTML email message with proper formatting."""
        message = MIMEMultipart("alternative")
        message["From"] = self.email_user
        message["To"] = recipient
        message["Subject"] = f"Re: {subject}" if not subject.startswith("Re: ") else subject

        # Create HTML version
        html_text = reply_text.replace("\n", "<br>").replace("\\n", "<br>")
        html_content = f"""
        <!DOCTYPE html>
        <html>
        <head>
            <meta charset="utf-8">
            <meta name="viewport" content="width=device-width, initial-scale=1.0">
        </head>
        <body>{html_text}</body>
        </html>
        """

        html_part = MIMEText(html_content, "html")
        message.attach(html_part)

        return message

    def _should_skip_email(self, email_info: Dict) -> bool:
        """Determines if an email should be skipped based on sender."""
        return self.email_user in email_info["sender"] 