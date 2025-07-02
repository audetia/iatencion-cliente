from pydantic import BaseModel, Field
from typing import List, Optional
from enum import Enum

# **Categorize Email Output**
class EmailCategory(str, Enum):
    product_enquiry = "product_enquiry"
    customer_complaint = "customer_complaint"
    customer_feedback = "customer_feedback"
    unrelated = "unrelated"

class CategorizeEmailOutput(BaseModel):
    category: EmailCategory = Field(
        ..., 
        description="The category assigned to the email, indicating its type based on predefined rules."
    )

# **RAG Query Output**
class RAGQueriesOutput(BaseModel):
    queries: List[str] = Field(
        ..., 
        description="A list of up to three questions representing the customer's intent, based on their email."
    )

# **Email Writer Output**
class WriterOutput(BaseModel):
    email: str = Field(
        ..., 
        description="The draft email written in response to the customer's inquiry, adhering to company tone and standards."
    )

# **Proofreader Email Output**
class ProofReaderOutput(BaseModel):
    feedback: str = Field(
        ..., 
        description="Detailed feedback explaining why the email is or is not sendable."
    )
    send: bool = Field(
        ..., 
        description="Indicates whether the email is ready to be sent (true) or requires rewriting (false)."
    )

# **Question Variants Output**
class QuestionVariantsOutput(BaseModel):
    variants: List[str] = Field(
        ..., 
        description="A list of semantically diverse question variations that maintain the original intent and meaning."
    )

# **Forward Decision Output**
class ForwardDecisionOutput(BaseModel):
    should_forward: bool = Field(
        ..., 
        description="Indicates whether the email should be forwarded based on the forwarding rules and Q&A topics analysis."
    )
    forward_automation_id: Optional[int] = Field(
        default=None, 
        description="The ID of the forward automation rule that matched, or null if no specific rule matched or if should_forward is False."
    )
    confidence_score: float = Field(
        ..., 
        ge=0, 
        le=100,
        description="Confidence level (0-100) in the forwarding decision. Higher values indicate more certainty."
    )
    reason: str = Field(
        ..., 
        description="Brief explanation of why the decision was made, referencing either Q&A topics or forwarding rules."
    )
