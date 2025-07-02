"""
Email Automation Workflow Graph Module
======================================

This module defines the LangGraph workflow structure for automating email processing.
It creates a directed graph that orchestrates the execution of processing nodes
(defined in nodes.py) to handle incoming emails intelligently.

The Workflow class builds a state machine that:
1. Defines the complete email processing pipeline as a directed graph
2. Establishes conditional branching based on email categorization and AI analysis
3. Configures email handling based on environment settings (human review vs. automatic)
4. Connects all processing nodes in a logical sequence with appropriate transitions

Core workflow capabilities:
- Loading and checking new emails from the inbox
- Categorizing emails into different types (product inquiries, feedback, spam, etc.)
- Retrieving relevant information from knowledge base using RAG for product inquiries
- Generating appropriate responses with AI assistance
- Quality control through proofreading and revision cycles
- Creating drafts or sending emails based on configuration
- Handling special cases (spam, unrelated emails, complex inquiries)

The graph configuration adapts based on the HUMAN_INTERACTION environment variable,
which determines whether emails are sent automatically or saved as drafts for human review.
"""

from langgraph.graph import END, StateGraph
from .state import GraphState
from .nodes import Nodes
import os
import logging

# Configure logging
logger = logging.getLogger(__name__)
logger.setLevel(logging.INFO)

# Add console handler if no handlers exist
if not logger.handlers:
    console_handler = logging.StreamHandler()
    formatter = logging.Formatter('%(asctime)s - %(name)s - %(levelname)s - %(message)s')
    console_handler.setFormatter(formatter)
    logger.addHandler(console_handler)

class Workflow():
    def __init__(self):
        # Check environment configuration for email handling
        human_interaction = os.getenv("HUMAN_INTERACTION", "False").lower() in ("true", "1", "t")
        
        if human_interaction:
            logger.info("🧑‍💼 HUMAN_INTERACTION=True: Creating drafts for human review before sending")
            logger.info("    Emails will be saved as drafts for manual review and sending")
        else:
            logger.info("🤖 HUMAN_INTERACTION=False: Sending emails automatically without review")
            logger.info("    Approved emails will be sent immediately without human intervention")
        
        # Note: The system always checks for existing drafts to avoid duplicate processing,
        # regardless of the HUMAN_INTERACTION setting
        
        # initiate graph state & nodes
        workflow = StateGraph(GraphState)
        nodes = Nodes()

        # define all graph nodes
        workflow.add_node("load_inbox_emails", nodes.load_new_emails)
        workflow.add_node("is_email_inbox_empty", nodes.is_email_inbox_empty)
        workflow.add_node("categorize_email", nodes.categorize_email)
        workflow.add_node("evaluate_forward_rules", nodes.evaluate_forward_rules)
        workflow.add_node("forward_email", nodes.forward_email)
        workflow.add_node("construct_rag_queries", nodes.construct_rag_queries)
        workflow.add_node("retrieve_from_rag", nodes.retrieve_from_rag)
        workflow.add_node("email_writer", nodes.write_draft_email)
        workflow.add_node("email_proofreader", nodes.verify_generated_email)
        workflow.add_node("create_draft", nodes.create_draft_response)
        workflow.add_node("send_email", nodes.send_email_response)
        workflow.add_node("skip_unrelated_email", nodes.skip_unrelated_email)
        workflow.add_node("mark_for_human_attention", nodes.mark_for_human_attention)
        workflow.add_node("skip_spam_email", nodes.skip_spam_email)

        # load inbox emails
        workflow.set_entry_point("load_inbox_emails")

        # check if there are emails to process
        workflow.add_edge("load_inbox_emails", "is_email_inbox_empty")
        workflow.add_conditional_edges(
            "is_email_inbox_empty",
            nodes.check_new_emails,
            {
                "process": "categorize_email",
                "empty": END
            }
        )

        # Add forward evaluation after categorization (except for spam and unrelated)
        def route_after_categorization(state: GraphState) -> str:
            """Routes email after categorization - evaluates forward rules or handles special cases."""
            category = state["email_category"]
            if category == "unrelated":
                return "unrelated"
            elif category == "spam":
                return "spam"
            else:
                # For all other categories (product_enquiry, lead_enquiry, customer_complaint, customer_feedback)
                # evaluate forward rules first
                return "evaluate_forward"

        workflow.add_conditional_edges(
            "categorize_email", 
            route_after_categorization,
            {
                "evaluate_forward": "evaluate_forward_rules",
                "unrelated": "skip_unrelated_email",
                "spam": "skip_spam_email"
            }
        )

        # Add routing after forward evaluation
        def route_after_forward_evaluation(state: GraphState) -> str:
            """Routes email after forward evaluation - either forward or continue normal flow."""
            forward_decision = state.get("forward_decision")
            
            if forward_decision and forward_decision.get("should_forward"):
                return "forward_email"
            else:
                # Continue with normal flow based on original category
                category = state["email_category"]
                if category in ["product_enquiry", "lead_enquiry"]:
                    return "product_related"
                else:
                    # customer_complaint, customer_feedback
                    return "not_product_related"

        workflow.add_conditional_edges(
            "evaluate_forward_rules",
            route_after_forward_evaluation,
            {
                "forward_email": "forward_email",  # Use actual forward node
                "product_related": "construct_rag_queries", 
                "not_product_related": "email_writer"
            }
        )

        # Add edge from forward_email back to check for more emails
        workflow.add_edge("forward_email", "is_email_inbox_empty")

        # pass constructed queries to RAG chain to retrieve information
        workflow.add_edge("construct_rag_queries", "retrieve_from_rag")

        # Check if email needs human attention or can be handled by AI
        workflow.add_conditional_edges(
            "retrieve_from_rag",
            lambda state: "human_attention" if state["needs_human_attention"] else "ai_handle",
            {
                "human_attention": "mark_for_human_attention",
                "ai_handle": "email_writer"
            }
        )

        # Edge from retrieve_from_rag to email_writer is now handled by conditional logic above
        workflow.add_edge("email_writer", "email_proofreader")
        
        # Based on configuration, either create drafts or send emails directly
        email_action = "create_draft" if human_interaction else "send_email"
        
        # check if email is sendable or not, if not rewrite the email
        workflow.add_conditional_edges(
            "email_proofreader",
            nodes.must_rewrite,
            {
                "send": email_action,  # Configurable based on HUMAN_INTERACTION
                "rewrite": "email_writer",
                "stop": "categorize_email"
            }
        )

        # check if there are still emails to be processed
        workflow.add_edge("create_draft", "is_email_inbox_empty")
        workflow.add_edge("send_email", "is_email_inbox_empty")
        workflow.add_edge("skip_unrelated_email", "is_email_inbox_empty")
        workflow.add_edge("skip_spam_email", "is_email_inbox_empty")
        workflow.add_edge("mark_for_human_attention", "is_email_inbox_empty")

        # Compile
        self.app = workflow.compile()