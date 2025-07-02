from pydantic import BaseModel, Field
from typing import List, Annotated, Optional, Dict, Any
from typing_extensions import TypedDict
from langgraph.graph.message import add_messages

class Email(BaseModel):
    id: str = Field(..., description="Unique identifier of the email")
    threadId: str = Field(..., description="Thread identifier of the email")
    messageId: str = Field(..., description="Message identifier of the email")
    references: str = Field(..., description="References of the email")
    sender: str = Field(..., description="Email address of the sender")
    subject: str = Field(..., description="Subject line of the email")
    body: str = Field(..., description="Body content of the email")
    
class GraphState(TypedDict):
    emails: List[Email]
    current_email: Email
    email_category: str
    generated_email: str
    rag_queries: List[str]
    retrieved_documents: str
    writer_messages: Annotated[list, add_messages]
    sendable: bool
    trials: int
    # Forward decision information
    email_account_id: Optional[int]
    forward_decision: Optional[Dict[str, Any]]
    forward_automations_available: Optional[int]
    qa_topics_available: Optional[int]
    forward_error: Optional[str]
    needs_human_attention: Optional[bool]
    # Forward result information
    forward_result: Optional[Dict[str, Any]]
    forward_completed: Optional[bool]
    # Token usage tracking
    session_tokens_used: Optional[int]
    qa_usage_stats: Optional[List[Dict[str, Any]]]