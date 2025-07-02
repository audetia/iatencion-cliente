from langchain_core.prompts import ChatPromptTemplate, PromptTemplate
from langchain_google_genai import ChatGoogleGenerativeAI, GoogleGenerativeAIEmbeddings
from langchain_groq import ChatGroq
from langchain_chroma import Chroma
from langchain_core.runnables import RunnablePassthrough
from langchain_core.output_parsers import StrOutputParser
from langchain_core.prompts import ChatPromptTemplate, MessagesPlaceholder
from .structure_outputs import *
from .prompts import *

class Agents():
    def __init__(self):
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