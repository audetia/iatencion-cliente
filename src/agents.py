from langchain_core.prompts import ChatPromptTemplate, PromptTemplate
from langchain_google_genai import ChatGoogleGenerativeAI, GoogleGenerativeAIEmbeddings
from langchain_groq import ChatGroq
from langchain_chroma import Chroma
from langchain_core.runnables import RunnablePassthrough
from langchain_core.output_parsers import StrOutputParser
from langchain_core.prompts import ChatPromptTemplate, MessagesPlaceholder
from .structure_outputs import *
from .prompts import *
import logging

logger = logging.getLogger(__name__)

class TokenTracker:
    """
    Simple token usage tracker for LangChain models.
    Tracks tokens across multiple model calls in a session.
    """
    def __init__(self):
        self.total_tokens = 0
        self.prompt_tokens = 0
        self.completion_tokens = 0
        self.total_cost = 0.0
        self.request_count = 0
        
    def reset(self):
        """Reset all counters for a new session."""
        self.total_tokens = 0
        self.prompt_tokens = 0
        self.completion_tokens = 0
        self.total_cost = 0.0
        self.request_count = 0
        
    def add_usage(self, usage_metadata: dict):
        """
        Add usage from AIMessage.usage_metadata or response_metadata.
        
        Args:
            usage_metadata: Dict with token usage info
        """
        if not usage_metadata:
            return
            
        # Handle different formats from different providers
        input_tokens = usage_metadata.get('input_tokens', 0) or usage_metadata.get('prompt_tokens', 0)
        output_tokens = usage_metadata.get('output_tokens', 0) or usage_metadata.get('completion_tokens', 0)
        total = usage_metadata.get('total_tokens', 0) or (input_tokens + output_tokens)
        
        self.prompt_tokens += input_tokens
        self.completion_tokens += output_tokens
        self.total_tokens += total
        self.request_count += 1
        
        # Simple cost estimation (approximate)
        # Groq LLAMA3 is typically free/very cheap, Gemini has different pricing
        # This is a rough estimate - adjust based on actual pricing
        cost_per_1k_input = 0.001  # $0.0001 per 1K input tokens (rough estimate)
        cost_per_1k_output = 0.002  # $0.0002 per 1K output tokens (rough estimate)
        
        session_cost = (input_tokens / 1000 * cost_per_1k_input) + (output_tokens / 1000 * cost_per_1k_output)
        self.total_cost += session_cost
        
        logger.debug(f"Token usage added - Input: {input_tokens}, Output: {output_tokens}, "
                    f"Total session: {self.total_tokens}, Cost: ${self.total_cost:.6f}")
    
    def get_stats(self) -> dict:
        """Get current token usage statistics."""
        return {
            'total_tokens': self.total_tokens,
            'prompt_tokens': self.prompt_tokens,
            'completion_tokens': self.completion_tokens,
            'total_cost': self.total_cost,
            'request_count': self.request_count
        }


class Agents():
    def __init__(self):
        # Initialize token tracker
        self.token_tracker = TokenTracker()
        # Choose which LLMs to use for each agent (GPT-4o, Gemini, LLAMA3,...)
        llama = ChatGroq(model_name="llama-3.3-70b-versatile", temperature=0.1)
        gemini = ChatGoogleGenerativeAI(model="gemini-2.5-flash", temperature=0.1)
        # Output dimensionality se aplica al momento de hacer el embedding, no cuando se crea el modelo de embeddings. Migrar de Quora al codigo que hay aqui abajo, ya que dejaremos de usar Quora y pasaremos a Postgres y pgvector.
        """
            from langchain_google_genai import GoogleGenerativeAIEmbeddings

            emb = GoogleGenerativeAIEmbeddings(
                model="models/gemini-embedding-exp-03-07"   # full 3 072‑D by default
            )

            # 1‑off: 768‑dimension query vector
            vec_768 = emb.embed_query(
                "¿Cómo funciona LangChain?",
                output_dimensionality=768
            )

            # Batch with 512‑D vectors
            docs = ["doc A …", "doc B …"]
            vecs_512 = emb.embed_documents(
                docs,
                output_dimensionality=512
            )

        """
        # QA assistant chat
        self.embeddings = GoogleGenerativeAIEmbeddings(model="models/gemini-embedding-exp-03-07", task_type="semantic_similarity")

        vectorstore = Chroma(persist_directory="db", embedding_function=self.embeddings)
        retriever = vectorstore.as_retriever(search_kwargs={"k": 3})

        # Categorize email chain
        email_category_prompt = PromptTemplate(
            template=CATEGORIZE_EMAIL_PROMPT, 
            input_variables=["email"]
        )
        self.categorize_email = (
            email_category_prompt | 
            llama.with_structured_output(CategorizeEmailOutput)
        )

        # Used to design queries for RAG retrieval
        generate_query_prompt = PromptTemplate(
            template=GENERATE_RAG_QUERIES_PROMPT, 
            input_variables=["email"]
        )
        self.design_rag_queries = (
            generate_query_prompt | 
            llama.with_structured_output(RAGQueriesOutput)
        )
        
        # Generate answer to queries using RAG
        qa_prompt = ChatPromptTemplate.from_template(GENERATE_RAG_ANSWER_PROMPT)
        self.generate_rag_answer = (
            {"context": retriever, "question": RunnablePassthrough()}
            | qa_prompt
            | llama
            | StrOutputParser()
        )
        

        # Used to write a draft email based on category and related informations
        writer_prompt = ChatPromptTemplate.from_messages(
            [
                ("system", EMAIL_WRITER_PROMPT),
                MessagesPlaceholder("history"),
                ("human", "{email_information}")
            ]
        )
        self.email_writer = (
            writer_prompt | 
            llama.with_structured_output(WriterOutput)
        )

        # Verify the generated email
        proofreader_prompt = PromptTemplate(
            template=EMAIL_PROOFREADER_PROMPT, 
            input_variables=["initial_email", "generated_email"]
        )
        self.email_proofreader = (
            proofreader_prompt | 
            llama.with_structured_output(ProofReaderOutput) 
        )

        # Check forward rules for email routing
        forward_decision_prompt = PromptTemplate(
            template=FORWARD_DECISION_PROMPT,
            input_variables=["email_content", "qa_topics", "forward_rules"]
        )
        self.check_forward_rules = (
            forward_decision_prompt |
            llama.with_structured_output(ForwardDecisionOutput)
        )
        
    def invoke_with_token_tracking(self, chain, input_data: dict, operation_name: str = "unknown"):
        """
        Wrapper method to invoke chains while tracking token usage.
        
        Args:
            chain: The LangChain chain to invoke
            input_data: Input data for the chain
            operation_name: Name of the operation for logging
            
        Returns:
            Tuple of (result, token_count)
        """
        try:
            logger.debug(f"🔄 Starting {operation_name} with token tracking...")
            
            # Invoke the chain
            result = chain.invoke(input_data)
            
            # Extract token usage from result if available
            token_count = 0
            if hasattr(result, 'usage_metadata') and result.usage_metadata:
                self.token_tracker.add_usage(result.usage_metadata)
                token_count = result.usage_metadata.get('total_tokens', 0)
                logger.debug(f"📊 {operation_name} used {token_count} tokens")
            elif hasattr(result, 'response_metadata') and result.response_metadata:
                # Try to get usage from response_metadata
                usage_data = result.response_metadata.get('usage') or result.response_metadata.get('token_usage')
                if usage_data:
                    self.token_tracker.add_usage(usage_data)
                    token_count = usage_data.get('total_tokens', 0) or (
                        usage_data.get('input_tokens', 0) + usage_data.get('output_tokens', 0)
                    )
                    logger.debug(f"📊 {operation_name} used {token_count} tokens")
            else:
                logger.debug(f"⚠️ No token usage metadata available for {operation_name}")
            
            return result, token_count
            
        except Exception as e:
            logger.error(f"Error in {operation_name} with token tracking: {e}")
            raise
    
    def reset_token_tracking(self):
        """Reset token tracking for a new email processing session."""
        self.token_tracker.reset()
        logger.debug("🔄 Token tracking reset for new session")
    
    def get_session_token_usage(self) -> dict:
        """Get current session token usage statistics."""
        stats = self.token_tracker.get_stats()
        logger.info(f"📊 Session token usage - Total: {stats['total_tokens']}, "
                   f"Requests: {stats['request_count']}, Cost: ${stats['total_cost']:.6f}")
        return stats