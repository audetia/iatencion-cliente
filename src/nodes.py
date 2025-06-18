"""
Email Processing Nodes Module
=============================

This module defines the core processing nodes for the email automation workflow. 
Each node represents a discrete step in processing incoming emails, from inbox retrieval 
to sending responses.

The Nodes class encapsulates all workflow operations, serving as the foundation for the 
LangGraph workflow defined in graph.py. Each method corresponds to a specific graph node
that handles a distinct part of the email processing pipeline:

1. Email Retrieval: Loading and checking new emails from inbox
2. Classification: Categorizing emails by type (product inquiries, feedback, spam, etc.)
3. RAG Operations: Constructing queries and retrieving information from knowledge base
4. Email Generation: Writing, proofreading and refining email responses
5. Action Execution: Creating drafts or sending replies based on configuration
6. Special Cases: Handling spam, unrelated emails, or escalating to human attention

This node-based architecture enables a flexible, maintainable workflow where each step
has clear responsibilities and can be modified independently.
"""


from colorama import Fore, Style
from .agents import Agents
from .tools.EmailTools import EmailToolsClass
from .state import GraphState, Email
import logging

# Configure logging for nodes
logger = logging.getLogger(__name__)
logger.setLevel(logging.DEBUG)

# Create console handler with formatting if no handlers exist
if not logger.handlers:
    console_handler = logging.StreamHandler()
    console_handler.setLevel(logging.DEBUG)
    formatter = logging.Formatter('%(asctime)s - %(name)s - %(levelname)s - %(message)s')
    console_handler.setFormatter(formatter)
    logger.addHandler(console_handler)


class Nodes:
    def __init__(self):
        self.agents = Agents()
        self.email_tools = EmailToolsClass()
        logger.debug("Nodes initialized with Agents and EmailTools")

    def load_new_emails(self, state: GraphState) -> GraphState:
        """Loads new emails and updates the state."""
        print(Fore.YELLOW + "Loading new emails...\n" + Style.RESET_ALL)
        recent_emails = self.email_tools.fetch_unanswered_emails()
        emails = [Email(**email) for email in recent_emails]
        return {"emails": emails}

    def check_new_emails(self, state: GraphState) -> str:
        """Checks if there are new emails to process."""
        if len(state['emails']) == 0:
            print(Fore.RED + "No new emails" + Style.RESET_ALL)
            return "empty"
        else:
            print(Fore.GREEN + "New emails to process" + Style.RESET_ALL)
            return "process"
        
    def is_email_inbox_empty(self, state: GraphState) -> GraphState:
        return state

    def categorize_email(self, state: GraphState) -> GraphState:
        """Categorizes the current email using the categorize_email agent."""
        print(Fore.YELLOW + "Checking email category...\n" + Style.RESET_ALL)
        
        # Get the last email
        current_email = state["emails"][-1]
        result = self.agents.categorize_email.invoke({"email": current_email.body})
        print(Fore.MAGENTA + f"Email category: {result.category.value}" + Style.RESET_ALL)
        
        return {
            "email_category": result.category.value,
            "current_email": current_email
        }

    def route_email_based_on_category(self, state: GraphState) -> str:
        """Routes the email based on its category."""
        print(Fore.YELLOW + "Routing email based on category...\n" + Style.RESET_ALL)
        category = state["email_category"]
        if category == "product_enquiry" or category == "lead_enquiry":
            return "product related"
        elif category == "unrelated":
            return "unrelated"
        elif category == "spam":
            return "spam"
        else:
            return "not product related"

    def construct_rag_queries(self, state: GraphState) -> GraphState:
        """Constructs RAG queries based on the email content."""
        print(Fore.YELLOW + "Designing RAG query...\n" + Style.RESET_ALL)
        email_content = state["current_email"].body
        query_result = self.agents.design_rag_queries.invoke({"email": email_content})
        
        return {"rag_queries": query_result.queries}

    def retrieve_from_rag(self, state: GraphState) -> GraphState:
        """Retrieves information from internal knowledge based on RAG questions."""
        print(Fore.YELLOW + "Retrieving information from internal knowledge...\n" + Style.RESET_ALL)
        final_answer = ""
        needs_human_attention = False
        
        for query in state["rag_queries"]:
            rag_result = self.agents.generate_rag_answer.invoke(query)
            # Check if the result is "null" indicating human attention needed
            if rag_result == "null":
                needs_human_attention = True
                break
            final_answer += query + "\n" + rag_result + "\n\n"
        
        return {
            "retrieved_documents": final_answer,
            "needs_human_attention": needs_human_attention
        }

    def write_draft_email(self, state: GraphState) -> GraphState:
        """Writes a draft email based on the current email and retrieved information."""
        print(Fore.YELLOW + "Writing draft email...\n" + Style.RESET_ALL)
        
        # Format input to the writer agent
        inputs = (
            f'# **EMAIL CATEGORY:** {state["email_category"]}\n\n'
            f'# **EMAIL CONTENT:**\n{state["current_email"].body}\n\n'
            f'# **INFORMATION:**\n{state["retrieved_documents"]}' # Empty for feedback or complaint
        )
        
        # Get messages history for current email
        writer_messages = state.get('writer_messages', [])
        
        # Write email
        draft_result = self.agents.email_writer.invoke({
            "email_information": inputs,
            "history": writer_messages
        })
        email = draft_result.email
        trials = state.get('trials', 0) + 1

        # Append writer's draft to the message list
        writer_messages.append(f"**Draft {trials}:**\n{email}")

        return {
            "generated_email": email, 
            "trials": trials,
            "writer_messages": writer_messages
        }

    def verify_generated_email(self, state: GraphState) -> GraphState:
        """Verifies the generated email using the proofreader agent."""
        print(Fore.YELLOW + "Verifying generated email...\n" + Style.RESET_ALL)
        review = self.agents.email_proofreader.invoke({
            "initial_email": state["current_email"].body,
            "generated_email": state["generated_email"],
        })

        writer_messages = state.get('writer_messages', [])
        writer_messages.append(f"**Proofreader Feedback:**\n{review.feedback}")

        return {
            "sendable": review.send,
            "writer_messages": writer_messages
        }

    def must_rewrite(self, state: GraphState) -> str:
        """Determines if the email needs to be rewritten based on the review and trial count."""
        email_sendable = state["sendable"]
        logger.debug(f"Email proofreader check - Sendable: {email_sendable}, Trial count: {state['trials']}")
        
        if email_sendable:
            logger.info("✅ Email approved by proofreader, ready to be sent")
            print(Fore.GREEN + "Email is good, ready to be sent!!!" + Style.RESET_ALL)
            # Pop the email to avoid reprocessing
            email = state["emails"].pop()
            logger.debug(f"Removed email from processing queue - Subject: {email.subject}, From: {email.sender}")
            state["writer_messages"] = []
            return "send"
        elif state["trials"] >= 3:
            logger.warning("⚠️ Email not approved after maximum trials, stopping further attempts")
            print(Fore.RED + "Email is not good, we reached max trials must stop!!!" + Style.RESET_ALL)
            # Pop the email to avoid reprocessing
            email = state["emails"].pop()
            logger.debug(f"Removed email from processing queue - Subject: {email.subject}, From: {email.sender}")
            state["writer_messages"] = []
            return "stop"
        else:
            logger.info(f"📝 Email needs improvement (Trial {state['trials']}), requesting rewrite")
            print(Fore.RED + "Email is not good, must rewrite it..." + Style.RESET_ALL)
            return "rewrite"

    def create_draft_response(self, state: GraphState) -> GraphState:
        """Creates a draft response in Gmail."""
        print(Fore.YELLOW + "Creating draft email...\n" + Style.RESET_ALL)
        logger.info("Creating draft response")
        
        # Get information about the email
        sender = state["current_email"].sender
        subject = state["current_email"].subject
        logger.debug(f"Creating draft reply to: {sender}, Subject: {subject}")
        
        # Log generated email preview
        email_preview = state["generated_email"][:100] + "..." if len(state["generated_email"]) > 100 else state["generated_email"]
        logger.debug(f"Generated email preview: {email_preview}")
        
        # Convert Email object to dictionary
        email_dict = {
            "id": state["current_email"].id,
            "threadId": state["current_email"].threadId,
            "messageId": state["current_email"].messageId,
            "references": state["current_email"].references,
            "sender": state["current_email"].sender,
            "subject": state["current_email"].subject,
            "body": state["current_email"].body
        }
        
        # Create draft reply
        logger.debug("Calling email_tools.create_draft_reply")
        result = self.email_tools.create_draft_reply(email_dict, state["generated_email"])
        
        if result:
            logger.info(f"✅ Draft reply created successfully for thread: {result.get('threadId', 'unknown')}")
            print(Fore.GREEN + "Draft email created successfully!" + Style.RESET_ALL)
        else:
            logger.error("❌ Failed to create draft reply")
            print(Fore.RED + "Failed to create draft email!" + Style.RESET_ALL)
        
        return {"retrieved_documents": "", "trials": 0}

    def send_email_response(self, state: GraphState) -> GraphState:
        """Sends the email response directly using Gmail."""
        print(Fore.YELLOW + "Sending email...\n" + Style.RESET_ALL)
        logger.info("Sending email response")
        
        # Get information about the email
        sender = state["current_email"].sender
        subject = state["current_email"].subject
        logger.debug(f"Sending email to: {sender}, Subject: {subject}")
        
        # Log generated email preview
        email_preview = state["generated_email"][:100] + "..." if len(state["generated_email"]) > 100 else state["generated_email"]
        logger.debug(f"Generated email preview: {email_preview}")
        
        # Convert Email object to dictionary
        email_dict = {
            "id": state["current_email"].id,
            "threadId": state["current_email"].threadId,
            "messageId": state["current_email"].messageId,
            "references": state["current_email"].references,
            "sender": state["current_email"].sender,
            "subject": state["current_email"].subject,
            "body": state["current_email"].body
        }
        
        # Send reply
        logger.debug("Calling email_tools.send_reply")
        result = self.email_tools.send_reply(email_dict, state["generated_email"])
        
        if result:
            logger.info(f"✅ Email sent successfully to {sender} for thread: {result.get('threadId', 'unknown')}")
            print(Fore.GREEN + f"Email sent successfully to {sender}!" + Style.RESET_ALL)
        else:
            logger.error(f"❌ Failed to send email to {sender}")
            print(Fore.RED + f"Failed to send email to {sender}!" + Style.RESET_ALL)
        
        return {"retrieved_documents": "", "trials": 0}
    
    def skip_unrelated_email(self, state):
        """Skip unrelated email and remove from emails list."""
        print("Skipping unrelated email...\n")
        state["emails"].pop()
        return state

    def skip_spam_email(self, state):
        """Skip spam email, mark as read, and remove from emails list."""
        print(Fore.YELLOW + "Marking spam email as read and skipping it...\n" + Style.RESET_ALL)
        # Just remove from our processing queue - it's already marked as read when fetched
        state["emails"].pop()
        return state

    def mark_for_human_attention(self, state: GraphState) -> GraphState:
        """Marks the email as needing human attention and leaves it unread in the inbox."""
        print(Fore.RED + "Email requires human attention, leaving in inbox...\n" + Style.RESET_ALL)
        # Skip marking as read by not using email_tools.create_draft_reply
        # Just remove from our processing queue
        state["emails"].pop()
        return state