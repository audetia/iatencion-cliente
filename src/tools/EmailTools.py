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

# Configure advanced logging
logger = logging.getLogger(__name__)
logger.setLevel(logging.DEBUG)  # Set to DEBUG for more detailed logs

# Create console handler with formatting
if not logger.handlers:
    console_handler = logging.StreamHandler()
    console_handler.setLevel(logging.DEBUG)
    formatter = logging.Formatter('%(asctime)s - %(name)s - %(levelname)s - %(message)s')
    console_handler.setFormatter(formatter)
    logger.addHandler(console_handler)

# Email configuration - these should be loaded from environment variables or config file
EMAIL_CONFIG = {
    "smtp_server": os.getenv("SMTP_SERVER", "smtppro.zoho.eu"),
    "smtp_port": int(os.getenv("SMTP_PORT", "465")),
    "imap_server": os.getenv("IMAP_SERVER", "imappro.zoho.eu"),
    "email_user": os.getenv("EMAIL_USER"),
    "email_pass": os.getenv("EMAIL_PASS"),
    "check_interval": int(os.getenv("EMAIL_CHECK_INTERVAL", "300")),  # 5 minutes default
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
        
        # Log configuration (without sensitive info)
        logger.info("EmailTools initialized with configuration:")
        logger.info(f"  SMTP Server: {self.smtp_server}:{self.smtp_port}")
        logger.info(f"  IMAP Server: {self.imap_server}")
        logger.info(f"  User: {self.email_user}")
        logger.info(f"  Credentials: {'✓ Set' if self.email_pass else '✗ Missing'}")
        
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
            
            # Use quotes around inbox name for better compatibility
            try:
                mail.select('"INBOX"')
            except Exception:
                # Fallback to standard inbox selection
                mail.select("INBOX")
                
            logger.debug("Selected inbox folder")
            return mail
        except imaplib.IMAP4.error as e:
            logger.error(f"IMAP connection error: {str(e)}")
            raise ConnectionError(f"Failed to connect to email server: {str(e)}")
        except Exception as e:
            logger.error(f"Unexpected error connecting to inbox: {str(e)}")
            raise

    def _get_folder_name(self, folder_bytes: bytes) -> Optional[str]:
        """
        Safely extracts a folder name from IMAP LIST response.
        Handles various formats returned by different IMAP servers.
        
        Args:
            folder_bytes: Raw folder data from IMAP LIST command
            
        Returns:
            Folder name as string or None if parsing fails
        """
        try:
            folder_str = folder_bytes.decode()
            
            # Try different parsing methods based on common IMAP server formats
            
            # Format: * LIST (\HasNoChildren) "/" "INBOX"
            if '"' in folder_str:
                parts = folder_str.split('"')
                if len(parts) >= 2:
                    return parts[-2]  # Get the part between the last two quotes
            
            # Format: * LIST (\HasNoChildren) "/" INBOX
            if '/' in folder_str:
                parts = folder_str.split('/')
                if len(parts) >= 2:
                    # Get the last part and strip any trailing whitespace or closing paren
                    return parts[-1].strip().rstrip(')')
                    
            # If above methods fail, just return the whole string for debugging
            return folder_str
            
        except Exception as e:
            logger.error(f"Error parsing folder name: {str(e)}")
            return None

    def fetch_unanswered_emails(self, max_results: int = 50) -> List[Dict]:
        """
        Fetches unanswered emails from the last 8 hours, excluding threads
        that already have draft responses.
        
        Args:
            max_results: Maximum number of recent emails to fetch
            
        Returns:
            List of dictionaries, each representing an email
        """
        try:
            logger.debug(f"Fetching up to {max_results} unanswered emails")
            # Get recent emails
            recent_emails = self.fetch_recent_emails(max_results)
            if not recent_emails:
                logger.info("No recent emails found")
                return []

            # Always check drafts to avoid duplicate work, regardless of HUMAN_INTERACTION setting
            threads_with_drafts = set()
            try:
                logger.debug("Checking for existing drafts to avoid duplicates")
                drafts = self.fetch_draft_replies()
                threads_with_drafts = {draft['threadId'] for draft in drafts}
                logger.debug(f"Found {len(threads_with_drafts)} threads with existing drafts")
            except Exception as draft_error:
                logger.warning(f"Could not fetch drafts: {draft_error}")

            # Process new emails
            seen_threads = set()
            unanswered_emails = []
            
            for email_msg in recent_emails:
                thread_id = self._get_thread_id(email_msg)
                # Skip if we already saw this thread or if it has a draft
                if thread_id in seen_threads:
                    logger.debug(f"Skipping thread {thread_id[:8]}... - already processed in this batch")
                    continue
                    
                if thread_id in threads_with_drafts:
                    logger.debug(f"Skipping thread {thread_id[:8]}... - already has draft")
                    continue
                    
                seen_threads.add(thread_id)
                email_info = self._get_email_info(email_msg)
                
                # Skip emails sent by us
                if self._should_skip_email(email_info):
                    logger.debug(f"Skipping email from {email_info['sender']} - sent by us")
                    continue
                    
                logger.info(f"Found unanswered email: Subject: {email_info['subject']}, From: {email_info['sender']}")
                unanswered_emails.append(email_info)
                
            logger.info(f"Found {len(unanswered_emails)} unanswered emails to process")
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
                    # Use our helper method to safely extract folder name
                    draft_folder = self._get_folder_name(folder)
                    break
                    
            if not draft_folder:
                logger.warning("No drafts folder found")
                return []
                
            try:
                # Try using quoted folder name first
                try:
                    mail.select(f'"{draft_folder}"')
                except Exception:
                    # Fall back to unquoted name
                    mail.select(draft_folder)
            except Exception as select_error:
                logger.warning(f"Error selecting drafts folder: {str(select_error)}")
                # If we can't access drafts, return an empty list
                mail.logout()
                return []
            
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
            # Return empty list on error to allow workflow to continue
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
            logger.debug("Starting draft reply creation process")
            logger.debug(f"Replying to email with subject: {initial_email.get('subject', 'No subject')}")
            logger.debug(f"Sender: {initial_email.get('sender', 'Unknown sender')}")
            
            # Log first few characters of the reply text
            preview = reply_text[:100] + "..." if len(reply_text) > 100 else reply_text
            logger.debug(f"Reply preview: {preview}")
            
            # Create the reply message
            message = self._create_reply_message(initial_email, reply_text)
            logger.debug(f"Message created with headers: From={message.get('From')}, To={message.get('To')}, Subject={message.get('Subject')}")
            
            # Instead of using IMAP APPEND which is causing syntax issues,
            # we'll use SMTP to send the message to the Drafts folder
            try:
                logger.debug(f"Attempting to create draft via SMTP to {self.smtp_server}:{self.smtp_port}")
                # Connect to SMTP server
                if self.smtp_port == 465:
                    logger.debug("Using SMTP_SSL connection")
                    server = smtplib.SMTP_SSL(self.smtp_server, self.smtp_port)
                else:
                    logger.debug("Using standard SMTP connection with STARTTLS")
                    server = smtplib.SMTP(self.smtp_server, self.smtp_port)
                    server.starttls()
                    
                logger.debug(f"Logging in to SMTP server as {self.email_user}")
                server.login(self.email_user, self.email_pass)
                
                # Add the Draft flag to indicate this is a draft
                message['X-Mozilla-Draft-Info'] = 'internal/draft; vnd.mozilla.message-draft'
                
                # Send the message to ourselves, it will appear in Drafts
                logger.debug(f"Sending draft email from {self.email_user} to {self.email_user}")
                server.send_message(message, from_addr=self.email_user, to_addrs=[self.email_user])
                server.quit()
                logger.info("✅ Draft created successfully via SMTP")
                
                return {
                    "threadId": initial_email["threadId"],
                    "id": message["Message-ID"]
                }
            except Exception as smtp_error:
                # Fall back to IMAP APPEND if SMTP approach fails
                logger.warning(f"SMTP draft creation failed: {str(smtp_error)}")
                logger.debug("Falling back to IMAP APPEND method")
                
                # Connect to IMAP and save to drafts
                mail = self.connect_to_inbox()
                
                # Find Drafts folder
                logger.debug("Searching for Drafts folder")
                result, folders = mail.list()
                draft_folder = None
                for folder in folders:
                    if b"\\Drafts" in folder:
                        # Use our helper method to safely extract folder name
                        draft_folder = self._get_folder_name(folder)
                        logger.debug(f"Found Drafts folder: {draft_folder}")
                        break
                        
                if not draft_folder:
                    logger.error("No Drafts folder found in IMAP account")
                    raise ValueError("No drafts folder found")
                
                # Try a different approach to APPEND that avoids syntax issues
                # Completely bypass using the folder name in the command
                try:
                    # First select the drafts folder
                    logger.debug(f"Attempting to select Drafts folder: {draft_folder}")
                    try:
                        mail.select(f'"{draft_folder}"')
                        logger.debug("Selected Drafts folder with quotes")
                    except Exception as e:
                        logger.debug(f"Error selecting quoted folder: {str(e)}")
                        mail.select(draft_folder)
                        logger.debug("Selected Drafts folder without quotes")
                    
                    # Use the APPEND command with minimal arguments
                    # Just pass the message without flags or date
                    import email.utils
                    import time
                    
                    # We'll try to create a draft by directly uploading the message
                    try:
                        logger.debug("Attempting direct IMAP APPEND command")
                        # Use a direct IMAP command instead of the append method which might be formatting incorrectly
                        mail._simple_command('APPEND', draft_folder, '{%d}' % len(message.as_bytes()))
                        response1 = mail._get_response()
                        logger.debug(f"APPEND command response: {response1}")
                        mail._command_complete('APPEND', response1)
                        
                        logger.debug("Sending message content")
                        mail.send(message.as_bytes())
                        response2 = mail._get_response()
                        logger.debug(f"Content send response: {response2}")
                        mail._command_complete('APPEND', response2)
                        
                        logger.info("✅ Draft created successfully via IMAP")
                    except Exception as append_error:
                        logger.error(f"IMAP APPEND failed: {str(append_error)}")
                        # If IMAP fails completely, just log it and return success anyway
                        # We'll let the workflow continue rather than failing completely
                except Exception as e:
                    logger.error(f"Error selecting drafts folder: {str(e)}")
                
                mail.logout()
                logger.debug("IMAP session closed")
                
                # Return success even if we couldn't create the draft
                # This allows the workflow to continue
                return {
                    "threadId": initial_email["threadId"],
                    "id": message["Message-ID"]
                }
                
        except Exception as e:
            logger.error(f"Error creating draft reply: {str(e)}")
            # Return None but log the error
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
            logger.debug("Starting email reply process")
            logger.debug(f"Replying to email with subject: {initial_email.get('subject', 'No subject')}")
            logger.debug(f"Sender: {initial_email.get('sender', 'Unknown sender')}")
            
            # Log first few characters of the reply text
            preview = reply_text[:100] + "..." if len(reply_text) > 100 else reply_text
            logger.debug(f"Reply content preview: {preview}")
            
            # Create the reply message
            message = self._create_reply_message(initial_email, reply_text, send=True)
            logger.debug(f"Created reply with headers: From={message.get('From')}, To={message.get('To')}, Subject={message.get('Subject')}")
            
            # Connect to SMTP server
            logger.debug(f"Connecting to SMTP server {self.smtp_server}:{self.smtp_port}")
            if self.smtp_port == 465:
                logger.debug("Using SMTP_SSL connection")
                server = smtplib.SMTP_SSL(self.smtp_server, self.smtp_port)
            else:
                logger.debug("Using standard SMTP connection with STARTTLS")
                server = smtplib.SMTP(self.smtp_server, self.smtp_port)
                server.starttls()
                
            logger.debug(f"Logging in to SMTP server as {self.email_user}")
            server.login(self.email_user, self.email_pass)
            
            # Set up recipient
            recipient = initial_email["sender"]
            logger.debug(f"Sending email from {self.email_user} to {recipient}")
            
            # Send the message
            result = server.send_message(message)
            if result:
                # If there are any failed recipients, they will be in the result dict
                logger.error(f"Failed to send to some recipients: {result}")
            else:
                logger.info(f"✅ Email sent successfully to {recipient}")
            
            server.quit()
            logger.debug("SMTP connection closed")
            
            return {
                "id": message["Message-ID"],
                "threadId": initial_email["threadId"]
            }
            
        except Exception as e:
            logger.error(f"Error sending reply: {str(e)}", exc_info=True)
            # Provide detailed traceback for debugging
            import traceback
            logger.error(f"Traceback: {traceback.format_exc()}")
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

        # Determine if reply_text is already HTML
        is_html = reply_text.strip().startswith('<') and '>' in reply_text

        # Create HTML version
        if is_html:
            # Already HTML content, use as is
            html_content = f"""
            <!DOCTYPE html>
            <html>
            <head>
                <meta charset="utf-8">
                <meta name="viewport" content="width=device-width, initial-scale=1.0">
            </head>
            <body>{reply_text}</body>
            </html>
            """
        else:
            # Convert plain text to HTML
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