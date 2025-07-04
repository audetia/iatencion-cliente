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
from .database import db_manager
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
        
        # Reset token tracking for new email processing session
        self.agents.reset_token_tracking()
        logger.debug("🔄 Starting new email processing session - token tracking reset")
        
        # Get the last email
        current_email = state["emails"][-1]
        
        # Use token tracking wrapper
        result, tokens_used = self.agents.invoke_with_token_tracking(
            self.agents.categorize_email, 
            {"email": current_email.body}, 
            "email_categorization"
        )
        
        print(Fore.MAGENTA + f"Email category: {result.category.value}" + Style.RESET_ALL)
        logger.debug(f"Email categorization used {tokens_used} tokens")
        
        return {
            "email_category": result.category.value,
            "current_email": current_email,
            "session_tokens_used": tokens_used
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
        
        # Use token tracking wrapper
        query_result, tokens_used = self.agents.invoke_with_token_tracking(
            self.agents.design_rag_queries,
            {"email": email_content},
            "rag_query_construction"
        )
        
        logger.debug(f"RAG query construction used {tokens_used} tokens")
        
        # Accumulate tokens from previous operations
        previous_tokens = state.get("session_tokens_used", 0)
        total_tokens = previous_tokens + tokens_used
        
        return {
            "rag_queries": query_result.queries,
            "session_tokens_used": total_tokens
        }

    def dynamic_rag_search(self, user_id: str, query: str) -> dict:
        """
        Performs dynamic RAG search using vector similarity on user's Q&A.
        
        Uses embedding cache to improve performance and reduce API calls.
        
        Args:
            user_id: The user ID to search Q&A for
            query: The search query text
            
        Returns:
            Dictionary with search results:
            {
                'success': bool,
                'answer': str or None,
                'similarity_score': float or None,
                'matched_question': str or None,
                'error': str or None,
                'cache_hit': bool  # Indicates if embedding came from cache
            }
        """
        try:
            from .services.embedding_cache import get_embedding_cache
            
            logger.debug(f"Generating embedding for query: {query[:100]}...")
            
            # Try to get embedding from cache first
            cache = get_embedding_cache()
            query_embedding = cache.get(query)
            cache_hit = query_embedding is not None
            
            if query_embedding is None:
                # Cache miss - generate embedding and store it
                query_embedding = self.agents.embeddings.embed_query(
                    query, 
                    output_dimensionality=1536
                )
                # Store in cache for future use
                cache.put(query, query_embedding)
                logger.debug(f"💾 Embedding generated and cached for query")
            else:
                logger.debug(f"🎯 Using cached embedding for query")
            
            # Search for similar questions using pgvector
            search_results = db_manager.search_similar_questions(
                user_id=user_id,
                query_embedding=query_embedding,
                threshold=0.7,  # Configurable threshold for similarity
                limit=3
            )
            
            if search_results['success'] and search_results['results']:
                # Get the best matching result
                best_match = search_results['results'][0]
                similarity_score = best_match['matched_variant']['similarity_score']
                
                logger.info(f"Found match with similarity {similarity_score:.4f}")
                logger.debug(f"Matched question: {best_match['original_question'][:100]}...")
                
                if best_match['answer']['has_answer']:
                    answer_text = best_match['answer']['text']
                    instructions = best_match['answer']['instructions']
                    
                    # Format the answer with instructions if available
                    formatted_answer = answer_text
                    if instructions:
                        formatted_answer += f"\n\nInstrucciones adicionales: {instructions}"
                    
                    return {
                        'success': True,
                        'answer': formatted_answer,
                        'similarity_score': similarity_score,
                        'matched_question': best_match['original_question'],
                        'question_id': best_match['question_id'],  # Include question_id for tracking
                        'error': None,
                        'cache_hit': cache_hit
                    }
                else:
                    logger.warning("Question found but no answer configured")
                    return {
                        'success': False,
                        'answer': None,
                        'similarity_score': similarity_score,
                        'matched_question': best_match['original_question'],
                        'error': 'Question found but no answer configured',
                        'cache_hit': cache_hit
                    }
            else:
                logger.info("No similar questions found")
                return {
                    'success': False,
                    'answer': None,
                    'similarity_score': None,
                    'matched_question': None,
                    'error': 'No similar questions found',
                    'cache_hit': cache_hit
                }
                
        except Exception as e:
            logger.error(f"Error in dynamic_rag_search: {e}")
            return {
                'success': False,
                'answer': None,
                'similarity_score': None,
                'matched_question': None,
                'error': str(e),
                'cache_hit': False
            }

    def retrieve_from_rag(self, state: GraphState) -> GraphState:
        """Retrieves information from user's personalized Q&A using vector search."""
        print(Fore.YELLOW + "Retrieving information from personalized Q&A...\n" + Style.RESET_ALL)
        final_answer = ""
        needs_human_attention = False
        qa_usage_stats = []  # Initialize here to ensure it's always available
        
        # Get email_account_id from state
        email_account_id = state.get("email_account_id")
        if not email_account_id:
            logger.warning("No email_account_id found in state, marking for human attention")
            return {
                "retrieved_documents": "",
                "needs_human_attention": True,
                "qa_usage_stats": qa_usage_stats
            }
        
        try:
            # Get email account information to extract user_id
            account_info_result = db_manager.get_email_account_info(email_account_id)
            if not account_info_result['success']:
                logger.error(f"Email account {email_account_id} not found")
                return {
                    "retrieved_documents": "",
                    "needs_human_attention": True,
                    "qa_usage_stats": qa_usage_stats
                }
            
            user_id = account_info_result['account_info']['user_id']
            logger.info(f"Processing Q&A search for user {user_id} (email account {email_account_id})")
            
            # Check if user has Q&A configured by trying to search with a test query
            # We'll use the first query to check if there are any Q&A entries
            if not state.get("rag_queries"):
                logger.warning("No RAG queries to process")
                return {
                    "retrieved_documents": "",
                    "needs_human_attention": True,
                    "qa_usage_stats": qa_usage_stats
                }
            
            # Process each RAG query using dynamic RAG search
            for query in state["rag_queries"]:
                logger.debug(f"Processing query: {query[:100]}...")
                
                # Use the new dynamic_rag_search method
                search_result = self.dynamic_rag_search(user_id, query)
                
                if search_result['success']:
                    final_answer += f"**Pregunta:** {query}\n**Respuesta:** {search_result['answer']}\n\n"
                    logger.debug(f"Added answer for query: {query[:50]}...")
                    
                    # Track Q&A usage for statistics
                    qa_usage_stats.append({
                        'query': query,
                        'question_id': search_result.get('question_id'),
                        'similarity_score': search_result.get('similarity_score'),
                        'matched_question': search_result.get('matched_question'),
                        'cache_hit': search_result.get('cache_hit', False)
                    })
                else:
                    logger.info(f"No answer found for query: {query[:50]}... - {search_result['error']}")
                    needs_human_attention = True
                    break
                    
        except Exception as e:
            logger.error(f"Error in retrieve_from_rag: {e}")
            needs_human_attention = True
        
        if needs_human_attention:
            logger.info("Marking email for human attention due to no matching Q&A or errors")
        else:
            logger.info(f"Successfully retrieved {len(state['rag_queries'])} Q&A responses")
            
            # Log cache statistics periodically
            try:
                from .services.embedding_cache import get_cache_stats
                cache_stats = get_cache_stats()
                if cache_stats['total_requests'] % 10 == 0:  # Log every 10 requests
                    logger.info(f"📊 Cache stats - Hit rate: {cache_stats['hit_rate_percentage']}% "
                               f"({cache_stats['hits']}/{cache_stats['total_requests']} requests)")
            except Exception:
                pass  # Don't fail if cache stats unavailable
        
        return {
            "retrieved_documents": final_answer,
            "needs_human_attention": needs_human_attention,
            "qa_usage_stats": qa_usage_stats  # Para tracking posterior
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
        
        # Write email with token tracking
        draft_result, tokens_used = self.agents.invoke_with_token_tracking(
            self.agents.email_writer,
            {
                "email_information": inputs,
                "history": writer_messages
            },
            "email_writing"
        )
        
        email = draft_result.email
        trials = state.get('trials', 0) + 1
        
        logger.debug(f"Email writing used {tokens_used} tokens")
        
        # Accumulate tokens from previous operations
        previous_tokens = state.get("session_tokens_used", 0)
        total_tokens = previous_tokens + tokens_used

        # Append writer's draft to the message list
        writer_messages.append(f"**Draft {trials}:**\n{email}")

        return {
            "generated_email": email, 
            "trials": trials,
            "writer_messages": writer_messages,
            "session_tokens_used": total_tokens
        }

    def verify_generated_email(self, state: GraphState) -> GraphState:
        """Verifies the generated email using the proofreader agent."""
        print(Fore.YELLOW + "Verifying generated email...\n" + Style.RESET_ALL)
        
        # Use token tracking wrapper
        review, tokens_used = self.agents.invoke_with_token_tracking(
            self.agents.email_proofreader,
            {
                "initial_email": state["current_email"].body,
                "generated_email": state["generated_email"],
            },
            "email_proofreading"
        )
        
        logger.debug(f"Email proofreading used {tokens_used} tokens")
        
        # Accumulate tokens from previous operations
        previous_tokens = state.get("session_tokens_used", 0)
        total_tokens = previous_tokens + tokens_used

        writer_messages = state.get('writer_messages', [])
        writer_messages.append(f"**Proofreader Feedback:**\n{review.feedback}")

        return {
            "sendable": review.send,
            "writer_messages": writer_messages,
            "session_tokens_used": total_tokens
        }

    def must_rewrite(self, state: GraphState) -> str:
        """Determines if the email needs to be rewritten based on the review and trial count."""
        email_sendable = state["sendable"]
        logger.debug(f"Email proofreader check - Sendable: {email_sendable}, Trial count: {state['trials']}")
        
        if email_sendable:
            logger.info("✅ Email approved by proofreader, ready to be sent")
            print(Fore.GREEN + "Email is good, ready to be sent!!!" + Style.RESET_ALL)
            # Pop the email to avoid reprocessing (only if there are emails)
            if state.get("emails"):
                email = state["emails"].pop()
                logger.debug(f"Removed email from processing queue - Subject: {email.subject}, From: {email.sender}")
            state["writer_messages"] = []
            return "send"
        elif state["trials"] >= 3:
            logger.warning("⚠️ Email not approved after maximum trials, stopping further attempts")
            print(Fore.RED + "Email is not good, we reached max trials must stop!!!" + Style.RESET_ALL)
            # Pop the email to avoid reprocessing (only if there are emails)
            if state.get("emails"):
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
            
            # Track Q&A usage in statistics
            self._track_qa_usage(state)
        else:
            logger.error(f"❌ Failed to send email to {sender}")
            print(Fore.RED + f"Failed to send email to {sender}!" + Style.RESET_ALL)
        
        return {"retrieved_documents": "", "trials": 0}
    
    def _track_qa_usage(self, state: GraphState) -> None:
        """
        Helper method to track Q&A usage in statistics.
        Logs each Q&A pair used in the email response.
        """
        try:
            # Import database manager
            from .database import db_manager
            
            qa_usage_stats = state.get("qa_usage_stats", [])
            email_account_id = state.get("email_account_id")
            
            if not qa_usage_stats or not email_account_id:
                logger.debug("No Q&A usage stats or email_account_id to track")
                return
            
            # Track each Q&A used (usually just one, but could be multiple)
            for qa_stat in qa_usage_stats:
                question_id = qa_stat.get('question_id')
                similarity_score = qa_stat.get('similarity_score')
                
                if question_id and similarity_score:
                    # Get total tokens used in this session
                    session_tokens = state.get("session_tokens_used", 0)
                    
                    # Log the email processing with Q&A tracking
                    result = db_manager.log_email_processed(
                        email_account_id=email_account_id,
                        category="question",  # Since we used Q&A, it's a question
                        action_taken="responded",
                        tokens_used=int(session_tokens),  # Track actual tokens used
                        question_id=question_id,
                        similarity_score=similarity_score
                    )
                    
                    if result['success']:
                        logger.info(f"📊 Tracked Q&A usage - Question ID: {question_id}, "
                                   f"Similarity: {similarity_score:.4f}, Tokens: {session_tokens}, "
                                   f"Cache hit: {qa_stat.get('cache_hit', False)}")
                    else:
                        logger.warning(f"Failed to track Q&A usage: {result.get('error')}")
                        
        except Exception as e:
            logger.error(f"Error tracking Q&A usage: {e}")
            # Don't fail the email sending if tracking fails
    
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

    def evaluate_forward_rules(self, state: GraphState) -> GraphState:
        """
        Evalúa las reglas de reenvío para determinar si el email debe ser reenviado.
        
        - Obtiene las automatizaciones activas de la cuenta
        - Ejecuta el agente de decisión de reenvío  
        - Registra la decisión en el estado
        """
        print(Fore.YELLOW + "Evaluating forward rules...\n" + Style.RESET_ALL)
        logger.info("Starting forward rules evaluation")
        
        try:
            # TODO: Obtener email_account_id del estado (pendiente actualizar GraphState)
            # Por ahora usamos un placeholder - esto se resolverá cuando se actualice state.py
            email_account_id = state.get("email_account_id", 1)  # Placeholder
            
            # 1. Obtener las automatizaciones activas de la cuenta
            logger.debug(f"Getting active automations for email_account_id: {email_account_id}")
            automations_result = db_manager.get_active_automations(email_account_id)
            
            if not automations_result['success']:
                logger.warning(f"Failed to get automations: {automations_result}")
                return {
                    "forward_decision": {
                        "should_forward": False,
                        "forward_automation_id": None,
                        "confidence_score": 0.0,
                        "reason": "Failed to get automations"
                    },
                    "forward_error": "Failed to get automations",
                    "session_tokens_used": state.get("session_tokens_used", 0)
                }
            
            # Separar automatizaciones de reenvío y obtener temas Q&A
            forward_automations = []
            qa_topics = []
            
            for automation in automations_result['automations']:
                if automation.get('type') == 'forward':
                    forward_description = automation.get('forward_details', {}).get('description', '')
                    forward_automations.append({
                        'id': automation['id'],
                        'description': forward_description
                    })
                elif automation.get('type') == 'response' and automation.get('question_details'):
                    qa_topics.append(automation['question_details']['original_question'])
            
            # Preparar datos para el prompt
            forward_rules = "\n".join([
                f"ID {rule['id']}: {rule['description']}" 
                for rule in forward_automations
            ]) if forward_automations else "No forwarding rules configured."
            
            qa_topics_text = "\n".join([
                f"- {topic}" 
                for topic in qa_topics
            ]) if qa_topics else "No Q&A topics configured."
            
            logger.debug(f"Found {len(forward_automations)} forward rules and {len(qa_topics)} Q&A topics")
            
            # 2. Ejecutar el agente de decisión de reenvío
            email_content = state["current_email"].body
            
            # 2. Ejecutar el agente de decisión de reenvío con token tracking
            forward_decision, tokens_used = self.agents.invoke_with_token_tracking(
                self.agents.check_forward_rules,
                {
                    "email_content": email_content,
                    "qa_topics": qa_topics_text,
                    "forward_rules": forward_rules
                },
                "forward_decision"
            )
            
            logger.debug(f"Forward decision used {tokens_used} tokens")
            
            # Accumulate tokens from previous operations
            previous_tokens = state.get("session_tokens_used", 0)
            total_tokens = previous_tokens + tokens_used
            
            logger.info(f"Forward decision: should_forward={forward_decision.should_forward}, "
                       f"automation_id={forward_decision.forward_automation_id}, "
                       f"confidence={forward_decision.confidence_score}")
            
            # 3. Registrar la decisión en el estado
            return {
                "forward_decision": {
                    "should_forward": forward_decision.should_forward,
                    "forward_automation_id": forward_decision.forward_automation_id,
                    "confidence_score": forward_decision.confidence_score,
                    "reason": forward_decision.reason
                },
                "forward_automations_available": len(forward_automations),
                "qa_topics_available": len(qa_topics),
                "session_tokens_used": total_tokens
            }
            
        except Exception as e:
            logger.error(f"Error evaluating forward rules: {str(e)}")
            print(Fore.RED + f"Error evaluating forward rules: {str(e)}\n" + Style.RESET_ALL)
            return {
                "forward_decision": {
                    "should_forward": False,
                    "forward_automation_id": None,
                    "confidence_score": 0.0,
                    "reason": f"Error: {str(e)}"
                },
                "forward_error": str(e),
                "session_tokens_used": state.get("session_tokens_used", 0)
            }

    def forward_email(self, state: GraphState) -> GraphState:
        """
        Reenvía el email según la automatización de reenvío que hizo match.
        
        Obtiene la dirección de destino de la base de datos y reenvía el email
        manteniendo la información del remitente original.
        """
        print(Fore.CYAN + "Forwarding email...\n" + Style.RESET_ALL)
        logger.info("Starting email forwarding")
        
        try:
            forward_decision = state.get("forward_decision")
            if not forward_decision or not forward_decision.get("should_forward"):
                logger.error("No forward decision found or should_forward is False")
                return {"forward_error": "No valid forward decision"}
            
            automation_id = forward_decision.get("forward_automation_id")
            if not automation_id:
                logger.error("No automation ID found in forward decision")
                return {"forward_error": "No automation ID in forward decision"}
            
            # Obtener detalles de la automatización de reenvío desde la base de datos
            logger.debug(f"Getting forward automation details for ID: {automation_id}")
            automation_details = db_manager.get_automation_details(automation_id)
            
            if not automation_details.get('success'):
                logger.error(f"Failed to get automation details: {automation_details}")
                return {"forward_error": "Failed to get automation details"}
            
            # Extraer información de reenvío
            forward_details = automation_details.get('forward_details')
            if not forward_details:
                logger.error("No forward details found in automation")
                return {"forward_error": "No forward details in automation"}
            
            forward_to_email = forward_details.get('forward_to_email')
            forward_description = forward_details.get('description', 'Automated forwarding rule')
            
            if not forward_to_email:
                logger.error("No forward_to_email found in automation details")
                return {"forward_error": "No destination email configured"}
            
            logger.info(f"Forwarding email to: {forward_to_email}")
            logger.debug(f"Forward rule description: {forward_description}")
            
            # Preparar información del email original para reenvío
            current_email = state["current_email"]
            original_email_dict = {
                "id": current_email.id,
                "threadId": current_email.threadId,
                "messageId": current_email.messageId,
                "references": current_email.references,
                "sender": current_email.sender,
                "subject": current_email.subject,
                "body": current_email.body
            }
            
            # Realizar el reenvío
            logger.debug("Calling email_tools.forward_email")
            result = self.email_tools.forward_email(
                original_email=original_email_dict,
                forward_to=forward_to_email,
                automation_description=forward_description
            )
            
            if result:
                logger.info(f"✅ Email forwarded successfully to {forward_to_email}")
                logger.info(f"   Original sender: {result.get('original_sender', 'Unknown')}")
                logger.info(f"   Forward message ID: {result.get('id', 'Unknown')}")
                print(Fore.GREEN + f"Email forwarded successfully to {forward_to_email}!" + Style.RESET_ALL)
                
                # Remover email del procesamiento (está procesado)
                state["emails"].pop()
                
                return {
                    "forward_result": result,
                    "forward_completed": True,
                    "retrieved_documents": "",  # Reset for next email
                    "trials": 0  # Reset for next email
                }
            else:
                logger.error(f"❌ Failed to forward email to {forward_to_email}")
                print(Fore.RED + f"Failed to forward email to {forward_to_email}!" + Style.RESET_ALL)
                return {"forward_error": "Email forwarding failed"}
                
        except Exception as e:
            logger.error(f"Error in forward_email node: {str(e)}")
            print(Fore.RED + f"Error forwarding email: {str(e)}\n" + Style.RESET_ALL)
            return {
                "forward_error": str(e),
                "forward_completed": False
            }