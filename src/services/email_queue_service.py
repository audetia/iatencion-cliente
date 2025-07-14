"""
Servicio de procesamiento de emails desde cola con fairness.

Este servicio consume emails de la cola de prioridad justa y los procesa
a través del workflow de LangGraph, respetando las cuotas por cuenta.
"""

import threading
import time
from datetime import datetime
from typing import Optional, Callable, Dict
from concurrent.futures import ThreadPoolExecutor, Future

from src.services.fairness_manager import FairnessManager
from src.models.fairness import FairnessConfig
from custom_logging.config import get_logger, CorrelationContext

logger = get_logger(__name__)


class EmailQueueProcessor:
    """
    Procesador de emails que consume de la cola con fairness.
    
    Responsabilidades:
    - Consumir emails de la cola respetando cuotas
    - Procesar emails a través del workflow
    - Reportar métricas de procesamiento
    - Manejar errores y reintentos
    """
    
    def __init__(self, 
                 fairness_manager: FairnessManager,
                 workflow_processor: Optional[Callable] = None,
                 max_workers: int = 5):
        """
        Inicializa el procesador de cola.
        
        Args:
            fairness_manager: Gestor de fairness con la cola
            workflow_processor: Función para procesar emails (workflow)
            max_workers: Número máximo de workers concurrentes
        """
        self.fairness_manager = fairness_manager
        self.workflow_processor = workflow_processor or self._default_processor
        self.max_workers = max_workers
        
        # Estado interno
        self.is_running = False
        self.shutdown_event = threading.Event()
        self.executor: Optional[ThreadPoolExecutor] = None
        
        # Métricas
        self.total_processed = 0
        self.total_failed = 0
        self.start_time = datetime.now()
        
        logger.info(f"📧 EmailQueueProcessor inicializado con {max_workers} workers")
    
    def start_processing(self) -> None:
        """Inicia el procesamiento de emails desde la cola."""
        if self.is_running:
            logger.warning("El procesador ya está ejecutándose")
            return
        
        logger.info("🚀 Iniciando procesamiento de cola de emails")
        
        # Crear thread pool
        self.executor = ThreadPoolExecutor(
            max_workers=self.max_workers,
            thread_name_prefix="email_processor"
        )
        
        self.is_running = True
        self.shutdown_event.clear()
        
        # Iniciar workers
        for i in range(self.max_workers):
            self.executor.submit(self._worker_loop, worker_id=i)
        
        logger.info(f"✅ {self.max_workers} workers iniciados para procesamiento")
    
    def stop_processing(self) -> None:
        """Detiene el procesamiento de forma graceful."""
        if not self.is_running:
            logger.warning("El procesador no está ejecutándose")
            return
        
        logger.info("🛑 Deteniendo procesamiento de emails")
        
        # Señalizar shutdown
        self.shutdown_event.set()
        self.is_running = False
        
        # Esperar a que terminen los workers
        if self.executor:
            self.executor.shutdown(wait=True, timeout=30)
            self.executor = None
        
        logger.info("✅ Procesamiento detenido correctamente")
    
    def _worker_loop(self, worker_id: int) -> None:
        """
        Loop principal del worker que consume emails de la cola.
        
        Args:
            worker_id: ID único del worker
        """
        logger.info(f"🔄 Worker {worker_id} iniciado")
        
        while not self.shutdown_event.is_set():
            try:
                # Obtener siguiente email con fairness
                email_tuple = self.fairness_manager.get_next_email(timeout=1.0)
                
                if not email_tuple:
                    # No hay emails, esperar un poco
                    continue
                
                account_id, email_id, email_data = email_tuple
                
                # Procesar email
                self._process_single_email(
                    worker_id=worker_id,
                    account_id=account_id,
                    email_id=email_id,
                    email_data=email_data
                )
                
            except Exception as e:
                logger.error(f"Error en worker {worker_id}: {str(e)}", exc_info=True)
                time.sleep(1)  # Evitar loops rápidos en caso de error
        
        logger.info(f"🛑 Worker {worker_id} detenido")
    
    def _process_single_email(self, worker_id: int, account_id: int, 
                            email_id: str, email_data: Dict) -> None:
        """
        Procesa un email individual.
        
        Args:
            worker_id: ID del worker procesando
            account_id: ID de la cuenta
            email_id: ID único del email
            email_data: Datos del email
        """
        with CorrelationContext(correlation_id_value=f"process_{email_id}_{int(time.time())}"):
            start_time = time.time()
            
            logger.info(f"📨 Worker {worker_id} procesando email", extra={
                "account_id": account_id,
                "email_id": email_id,
                "subject": email_data.get('subject', 'Sin asunto')
            })
            
            try:
                # Ejecutar workflow
                result = self.workflow_processor(email_data)
                
                # Calcular tiempo de procesamiento
                processing_time_ms = (time.time() - start_time) * 1000
                
                # Notificar completación a fairness manager
                self.fairness_manager.complete_processing(account_id, processing_time_ms)
                
                # Actualizar métricas
                self.total_processed += 1
                
                logger.info(f"✅ Email procesado exitosamente", extra={
                    "worker_id": worker_id,
                    "account_id": account_id,
                    "email_id": email_id,
                    "processing_time_ms": round(processing_time_ms, 2)
                })
                
            except Exception as e:
                self.total_failed += 1
                
                logger.error(f"❌ Error procesando email", exc_info=True, extra={
                    "worker_id": worker_id,
                    "account_id": account_id,
                    "email_id": email_id,
                    "error": str(e)
                })
                
                # Notificar fallo (tiempo alto como penalización)
                self.fairness_manager.complete_processing(account_id, 60000)  # 60s penalty
    
    def _default_processor(self, email_data: Dict) -> Dict:
        """
        Procesador por defecto que ejecuta el workflow de LangGraph.
        
        Args:
            email_data: Datos del email a procesar
            
        Returns:
            Dict: Resultado del procesamiento
        """
        try:
            # Importar el workflow
            from src.graph import Workflow
            from src.state import Email
            
            # Crear instancia del workflow
            workflow = Workflow()
            app = workflow.app
            
            # Configuración
            config = {'recursion_limit': 100}
            
            # Convertir a objeto Email
            email_obj = Email(**email_data)
            
            # Estado inicial
            initial_state = {
                "emails": [email_obj],
                "current_email": email_obj,
                "email_category": "",
                "generated_email": "",
                "rag_queries": [],
                "retrieved_documents": "",
                "writer_messages": [],
                "sendable": False,
                "trials": 0,
                "email_account_id": email_data.get('account_id'),
                "forward_decision": None,
                "forward_automations_available": None,
                "qa_topics_available": None,
                "forward_error": None,
                "needs_human_attention": None,
                "forward_result": None,
                "forward_completed": None,
                "session_tokens_used": 0,
                "qa_usage_stats": []
            }
            
            # Ejecutar workflow
            logger.debug(f"🚀 Ejecutando workflow para email: {email_data.get('subject', 'Sin asunto')}")
            
            result = None
            for output in app.stream(initial_state, config):
                result = output
            
            return {
                'success': True,
                'output': result
            }
            
        except Exception as e:
            logger.error(f"Error en procesador por defecto: {str(e)}", exc_info=True)
            return {
                'success': False,
                'error': str(e)
            }
    
    def get_metrics(self) -> Dict:
        """
        Obtiene métricas del procesador.
        
        Returns:
            Dict: Métricas de procesamiento
        """
        uptime = (datetime.now() - self.start_time).total_seconds()
        
        return {
            'total_processed': self.total_processed,
            'total_failed': self.total_failed,
            'success_rate': (self.total_processed / (self.total_processed + self.total_failed) * 100) 
                           if (self.total_processed + self.total_failed) > 0 else 0,
            'uptime_seconds': uptime,
            'emails_per_minute': (self.total_processed / uptime * 60) if uptime > 0 else 0,
            'active_workers': self.max_workers if self.is_running else 0,
            'is_running': self.is_running
        } 