"""
Integraciones específicas del sistema de logging para diferentes componentes

Este módulo proporciona integraciones específicas para:
- LangGraph workflows
- LangChain agents
- Database operations
- Email processing
- External API calls
"""

import time
import functools
from typing import Any, Dict, Optional, Callable
from .config import get_logger, CorrelationContext

class LangGraphLogger:
    """Logger específico para workflows de LangGraph"""
    
    def __init__(self, workflow_name: str):
        self.workflow_name = workflow_name
        self.logger = get_logger(f"langgraph.{workflow_name}")
    
    def log_node_execution(self, node_name: str, input_data: Dict[str, Any], output_data: Dict[str, Any], execution_time: float):
        """Log de ejecución de nodos en LangGraph"""
        self.logger.info(
            "LangGraph node executed",
            workflow=self.workflow_name,
            node=node_name,
            execution_time=f"{execution_time:.4f}s",
            input_keys=list(input_data.keys()) if input_data else [],
            output_keys=list(output_data.keys()) if output_data else [],
            input_size=len(str(input_data)) if input_data else 0,
            output_size=len(str(output_data)) if output_data else 0
        )
    
    def log_workflow_start(self, initial_state: Dict[str, Any]):
        """Log del inicio de workflow"""
        self.logger.info(
            "LangGraph workflow started",
            workflow=self.workflow_name,
            initial_state_keys=list(initial_state.keys()) if initial_state else [],
            state_size=len(str(initial_state)) if initial_state else 0
        )
    
    def log_workflow_end(self, final_state: Dict[str, Any], total_time: float):
        """Log del fin de workflow"""
        self.logger.info(
            "LangGraph workflow completed",
            workflow=self.workflow_name,
            total_execution_time=f"{total_time:.4f}s",
            final_state_keys=list(final_state.keys()) if final_state else [],
            state_size=len(str(final_state)) if final_state else 0
        )
    
    def log_workflow_error(self, error: Exception, current_node: str, state: Dict[str, Any]):
        """Log de errores en workflow"""
        self.logger.error(
            "LangGraph workflow failed",
            workflow=self.workflow_name,
            current_node=current_node,
            error=str(error),
            error_type=type(error).__name__,
            state_keys=list(state.keys()) if state else []
        )

class LangChainLogger:
    """Logger específico para agentes de LangChain"""
    
    def __init__(self, agent_name: str):
        self.agent_name = agent_name
        self.logger = get_logger(f"langchain.{agent_name}")
    
    def log_llm_call(self, model_name: str, prompt: str, response: str, tokens_used: int, execution_time: float):
        """Log de llamadas a LLM"""
        self.logger.info(
            "LLM call executed",
            agent=self.agent_name,
            model=model_name,
            prompt_length=len(prompt),
            response_length=len(response),
            tokens_used=tokens_used,
            execution_time=f"{execution_time:.4f}s",
            cost_estimate=self._estimate_cost(model_name, tokens_used)
        )
    
    def log_rag_retrieval(self, query: str, retrieved_docs: list, similarity_scores: list):
        """Log de retrieval RAG"""
        self.logger.info(
            "RAG retrieval executed",
            agent=self.agent_name,
            query_length=len(query),
            docs_retrieved=len(retrieved_docs),
            avg_similarity=sum(similarity_scores) / len(similarity_scores) if similarity_scores else 0,
            max_similarity=max(similarity_scores) if similarity_scores else 0
        )
    
    def log_agent_decision(self, input_data: Dict, decision: str, reasoning: str):
        """Log de decisiones del agente"""
        self.logger.info(
            "Agent decision made",
            agent=self.agent_name,
            decision=decision,
            reasoning_length=len(reasoning),
            input_keys=list(input_data.keys()) if input_data else []
        )
    
    def _estimate_cost(self, model_name: str, tokens: int) -> float:
        """Estimar costo aproximado de la llamada al LLM"""
        # Precios aproximados por 1K tokens (actualizar según pricing actual)
        pricing = {
            'gpt-4': 0.03,
            'gpt-3.5-turbo': 0.002,
            'gemini-pro': 0.001,
            'llama-3': 0.0005
        }
        
        base_model = model_name.lower()
        for model, price in pricing.items():
            if model in base_model:
                return (tokens / 1000) * price
        
        return 0.001 * (tokens / 1000)  # Default estimate

class DatabaseLogger:
    """Logger específico para operaciones de base de datos"""
    
    def __init__(self):
        self.logger = get_logger("database")
    
    def log_query_execution(self, query: str, params: tuple, execution_time: float, rows_affected: int):
        """Log de ejecución de queries"""
        self.logger.info(
            "Database query executed",
            query_type=self._get_query_type(query),
            execution_time=f"{execution_time:.4f}s",
            rows_affected=rows_affected,
            params_count=len(params) if params else 0,
            query_length=len(query)
        )
        
        # Log slow queries
        if execution_time > 1.0:
            self.logger.warning(
                "Slow database query detected",
                execution_time=f"{execution_time:.4f}s",
                query_preview=query[:100] + "..." if len(query) > 100 else query
            )
    
    def log_connection_event(self, event_type: str, connection_info: Dict):
        """Log de eventos de conexión"""
        self.logger.info(
            f"Database connection {event_type}",
            **connection_info
        )
    
    def log_migration_event(self, migration_name: str, direction: str, execution_time: float):
        """Log de migraciones"""
        self.logger.info(
            "Database migration executed",
            migration=migration_name,
            direction=direction,
            execution_time=f"{execution_time:.4f}s"
        )
    
    def _get_query_type(self, query: str) -> str:
        """Determinar el tipo de query"""
        query_lower = query.lower().strip()
        if query_lower.startswith('select'):
            return 'SELECT'
        elif query_lower.startswith('insert'):
            return 'INSERT'
        elif query_lower.startswith('update'):
            return 'UPDATE'
        elif query_lower.startswith('delete'):
            return 'DELETE'
        elif query_lower.startswith('create'):
            return 'CREATE'
        elif query_lower.startswith('alter'):
            return 'ALTER'
        else:
            return 'OTHER'

class EmailLogger:
    """Logger específico para procesamiento de emails"""
    
    def __init__(self):
        self.logger = get_logger("email")
    
    def log_email_received(self, email_info: Dict):
        """Log de emails recibidos"""
        self.logger.info(
            "Email received",
            sender=email_info.get('sender', 'unknown'),
            subject_length=len(email_info.get('subject', '')),
            body_length=len(email_info.get('body', '')),
            attachments_count=len(email_info.get('attachments', [])),
            timestamp=email_info.get('timestamp')
        )
    
    def log_email_processed(self, email_id: str, processing_result: Dict, execution_time: float):
        """Log de procesamiento de emails"""
        self.logger.info(
            "Email processed",
            email_id=email_id,
            category=processing_result.get('category'),
            action_taken=processing_result.get('action'),
            confidence=processing_result.get('confidence'),
            execution_time=f"{execution_time:.4f}s"
        )
    
    def log_email_sent(self, recipient: str, subject: str, success: bool):
        """Log de emails enviados"""
        if success:
            self.logger.info(
                "Email sent successfully",
                recipient=recipient,
                subject_length=len(subject)
            )
        else:
            self.logger.error(
                "Email sending failed",
                recipient=recipient,
                subject_length=len(subject)
            )

class APILogger:
    """Logger específico para llamadas a APIs externas"""
    
    def __init__(self):
        self.logger = get_logger("external_api")
    
    def log_api_call(self, api_name: str, endpoint: str, method: str, status_code: int, 
                     response_time: float, request_size: int = 0, response_size: int = 0):
        """Log de llamadas a APIs externas"""
        self.logger.info(
            "External API call",
            api=api_name,
            endpoint=endpoint,
            method=method,
            status_code=status_code,
            response_time=f"{response_time:.4f}s",
            request_size=request_size,
            response_size=response_size,
            success=200 <= status_code < 300
        )
        
        # Log slow API calls
        if response_time > 5.0:
            self.logger.warning(
                "Slow API call detected",
                api=api_name,
                endpoint=endpoint,
                response_time=f"{response_time:.4f}s"
            )
        
        # Log API errors
        if status_code >= 400:
            self.logger.error(
                "API call failed",
                api=api_name,
                endpoint=endpoint,
                status_code=status_code,
                response_time=f"{response_time:.4f}s"
            )

# Decoradores específicos para integraciones
def log_langgraph_node(node_name: str, workflow_name: str):
    """Decorador para logging automático de nodos LangGraph"""
    def decorator(func):
        @functools.wraps(func)
        def wrapper(*args, **kwargs):
            logger = LangGraphLogger(workflow_name)
            start_time = time.time()
            
            # Extraer input data del primer argumento (state)
            input_data = args[0] if args else {}
            
            try:
                result = func(*args, **kwargs)
                execution_time = time.time() - start_time
                
                logger.log_node_execution(
                    node_name=node_name,
                    input_data=input_data,
                    output_data=result,
                    execution_time=execution_time
                )
                
                return result
                
            except Exception as e:
                logger.log_workflow_error(e, node_name, input_data)
                raise
        
        return wrapper
    return decorator

def log_database_operation(operation_type: str = "query"):
    """Decorador para logging automático de operaciones de base de datos"""
    def decorator(func):
        @functools.wraps(func)
        def wrapper(*args, **kwargs):
            db_logger = DatabaseLogger()
            start_time = time.time()
            
            try:
                result = func(*args, **kwargs)
                execution_time = time.time() - start_time
                
                # Log básico de la operación
                db_logger.logger.info(
                    f"Database {operation_type} completed",
                    function=func.__name__,
                    execution_time=f"{execution_time:.4f}s"
                )
                
                return result
                
            except Exception as e:
                execution_time = time.time() - start_time
                db_logger.logger.error(
                    f"Database {operation_type} failed",
                    function=func.__name__,
                    execution_time=f"{execution_time:.4f}s",
                    error=str(e),
                    error_type=type(e).__name__
                )
                raise
        
        return wrapper
    return decorator

def log_api_call(api_name: str):
    """Decorador para logging automático de llamadas a APIs"""
    def decorator(func):
        @functools.wraps(func)
        def wrapper(*args, **kwargs):
            api_logger = APILogger()
            start_time = time.time()
            
            try:
                result = func(*args, **kwargs)
                execution_time = time.time() - start_time
                
                api_logger.logger.info(
                    "API function executed",
                    api=api_name,
                    function=func.__name__,
                    execution_time=f"{execution_time:.4f}s"
                )
                
                return result
                
            except Exception as e:
                execution_time = time.time() - start_time
                api_logger.logger.error(
                    "API function failed",
                    api=api_name,
                    function=func.__name__,
                    execution_time=f"{execution_time:.4f}s",
                    error=str(e),
                    error_type=type(e).__name__
                )
                raise
        
        return wrapper
    return decorator 