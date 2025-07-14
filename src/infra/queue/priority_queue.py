"""
Implementación de cola de prioridad thread-safe para procesamiento justo de emails.

Este módulo proporciona una cola de prioridad especializada que garantiza
fairness entre cuentas, evitando que cuentas de alto volumen monopolicen
el sistema.
"""

import threading
import time
from queue import PriorityQueue, Empty
from datetime import datetime, timedelta
from typing import Dict, Optional, Tuple, List
from collections import defaultdict

from src.models.fairness import (
    EmailQueueItem, 
    ProcessingMetrics, 
    AccountQuota,
    FairnessConfig
)
from custom_logging.config import get_logger

logger = get_logger(__name__)


class FairPriorityQueue:
    """
    Cola de prioridad que implementa fairness entre cuentas.
    
    Garantiza que ninguna cuenta pueda monopolizar el procesamiento
    mediante un sistema de scoring dinámico basado en:
    - Prioridad de la cuenta (volumen)
    - Tiempo de espera del email
    - Métricas de procesamiento reciente
    """
    
    def __init__(self, config: FairnessConfig):
        """
        Inicializa la cola con configuración de fairness.
        
        Args:
            config: Configuración del sistema de fairness
        """
        self.config = config
        self.queue = PriorityQueue()
        self.metrics: Dict[int, ProcessingMetrics] = {}
        self.quotas: Dict[int, AccountQuota] = {}
        self.lock = threading.Lock()
        
        # Tracking de procesamiento para ventana deslizante
        self.processing_history: Dict[int, List[datetime]] = defaultdict(list)
        
        logger.info("📦 FairPriorityQueue inicializada", extra={
            "default_quota": config.default_max_emails_per_minute,
            "default_concurrent": config.default_max_concurrent
        })
    
    def put(self, account_id: int, email_id: str, email_data: Dict) -> None:
        """
        Añade un email a la cola con prioridad calculada.
        
        Args:
            account_id: ID de la cuenta
            email_id: ID único del email
            email_data: Datos del email
        """
        with self.lock:
            # Obtener o crear métricas para la cuenta
            if account_id not in self.metrics:
                self.metrics[account_id] = ProcessingMetrics(account_id=account_id)
            
            # Calcular score de prioridad
            priority_score = self._calculate_priority_score(account_id)
            
            # Crear item de cola
            item = EmailQueueItem(
                account_id=account_id,
                email_id=email_id,
                email_data=email_data,
                priority_score=priority_score
            )
            
            # Añadir a la cola
            self.queue.put(item)
            
            logger.debug(f"📥 Email encolado", extra={
                "account_id": account_id,
                "email_id": email_id,
                "priority_score": round(priority_score, 3),
                "queue_size": self.queue.qsize()
            })
    
    def get(self, timeout: Optional[float] = None) -> Optional[EmailQueueItem]:
        """
        Obtiene el siguiente email a procesar respetando fairness.
        
        Args:
            timeout: Timeout en segundos para esperar
            
        Returns:
            EmailQueueItem si hay uno disponible y cumple cuotas, None si no
        """
        end_time = time.time() + timeout if timeout else None
        
        while True:
            try:
                # Intentar obtener item de la cola
                remaining_timeout = None
                if end_time:
                    remaining_timeout = end_time - time.time()
                    if remaining_timeout <= 0:
                        return None
                
                item = self.queue.get(timeout=remaining_timeout)
                
                # Verificar si puede procesarse según cuotas
                with self.lock:
                    if self._can_process_item(item):
                        self._record_processing_start(item.account_id)
                        return item
                    else:
                        # Re-encolar con nuevo score (penalización por cuota)
                        item.priority_score += 1.0  # Penalización
                        self.queue.put(item)
                        
                        logger.debug(f"🚫 Email re-encolado por cuota", extra={
                            "account_id": item.account_id,
                            "email_id": item.email_id,
                            "new_priority": round(item.priority_score, 3)
                        })
                
            except Empty:
                return None
    
    def complete_processing(self, account_id: int, processing_time_ms: float) -> None:
        """
        Marca un email como procesado y actualiza métricas.
        
        Args:
            account_id: ID de la cuenta
            processing_time_ms: Tiempo de procesamiento en milisegundos
        """
        with self.lock:
            if account_id in self.metrics:
                metrics = self.metrics[account_id]
                metrics.current_concurrent = max(0, metrics.current_concurrent - 1)
                metrics.last_processed_at = datetime.now()
                
                # Actualizar promedio de tiempo de procesamiento
                if metrics.average_processing_time_ms == 0:
                    metrics.average_processing_time_ms = processing_time_ms
                else:
                    # Media móvil exponencial
                    alpha = 0.3
                    metrics.average_processing_time_ms = (
                        alpha * processing_time_ms + 
                        (1 - alpha) * metrics.average_processing_time_ms
                    )
                
                logger.debug(f"✅ Procesamiento completado", extra={
                    "account_id": account_id,
                    "processing_time_ms": round(processing_time_ms, 2),
                    "current_concurrent": metrics.current_concurrent
                })
    
    def set_quota(self, account_id: int, quota: AccountQuota) -> None:
        """
        Establece la cuota para una cuenta específica.
        
        Args:
            account_id: ID de la cuenta
            quota: Cuota a aplicar
        """
        with self.lock:
            self.quotas[account_id] = quota
            logger.info(f"📊 Cuota establecida", extra={
                "account_id": account_id,
                "max_per_minute": quota.max_emails_per_minute,
                "max_concurrent": quota.max_concurrent_processing,
                "priority": quota.priority.name
            })
    
    def get_metrics(self, account_id: int) -> Optional[ProcessingMetrics]:
        """
        Obtiene las métricas de procesamiento de una cuenta.
        
        Args:
            account_id: ID de la cuenta
            
        Returns:
            ProcessingMetrics si existe, None si no
        """
        with self.lock:
            return self.metrics.get(account_id)
    
    def _calculate_priority_score(self, account_id: int) -> float:
        """
        Calcula el score de prioridad para un email.
        
        Score menor = mayor prioridad
        
        Args:
            account_id: ID de la cuenta
            
        Returns:
            float: Score de prioridad calculado
        """
        # Obtener cuota de la cuenta
        quota = self.quotas.get(account_id)
        if not quota:
            quota = AccountQuota(
                account_id=account_id,
                max_emails_per_minute=self.config.default_max_emails_per_minute,
                max_concurrent_processing=self.config.default_max_concurrent
            )
        
        # Factor de prioridad base (1-3, donde 3 es mayor prioridad)
        priority_factor = 4 - quota.priority.value  # Invertir para que LOW_VOLUME tenga mayor prioridad
        
        # Factor de utilización reciente (0-1, donde 0 es menos utilizado)
        metrics = self.metrics.get(account_id, ProcessingMetrics(account_id=account_id))
        utilization_factor = min(1.0, metrics.emails_processed_last_minute / quota.max_emails_per_minute)
        
        # Calcular score final (menor = mayor prioridad)
        score = (
            (1 - self.config.priority_weight) * utilization_factor +
            self.config.priority_weight * (1 / priority_factor)
        )
        
        return score
    
    def _can_process_item(self, item: EmailQueueItem) -> bool:
        """
        Verifica si un item puede procesarse según las cuotas.
        
        Args:
            item: Item a verificar
            
        Returns:
            bool: True si puede procesarse
        """
        account_id = item.account_id
        
        # Obtener métricas actualizadas
        self._update_processing_metrics(account_id)
        
        metrics = self.metrics.get(account_id)
        if not metrics:
            return True
        
        quota = self.quotas.get(account_id)
        if not quota:
            quota = AccountQuota(
                account_id=account_id,
                max_emails_per_minute=self.config.default_max_emails_per_minute,
                max_concurrent_processing=self.config.default_max_concurrent
            )
        
        return metrics.can_process_more(quota)
    
    def _update_processing_metrics(self, account_id: int) -> None:
        """
        Actualiza las métricas de procesamiento basadas en ventana deslizante.
        
        Args:
            account_id: ID de la cuenta
        """
        now = datetime.now()
        one_minute_ago = now - timedelta(minutes=1)
        
        # Limpiar historial antiguo
        if account_id in self.processing_history:
            self.processing_history[account_id] = [
                ts for ts in self.processing_history[account_id]
                if ts > one_minute_ago
            ]
        
        # Actualizar métrica
        if account_id in self.metrics:
            self.metrics[account_id].emails_processed_last_minute = len(
                self.processing_history.get(account_id, [])
            )
    
    def _record_processing_start(self, account_id: int) -> None:
        """
        Registra el inicio de procesamiento de un email.
        
        Args:
            account_id: ID de la cuenta
        """
        now = datetime.now()
        
        # Registrar en historial
        if account_id not in self.processing_history:
            self.processing_history[account_id] = []
        self.processing_history[account_id].append(now)
        
        # Actualizar métricas
        if account_id not in self.metrics:
            self.metrics[account_id] = ProcessingMetrics(account_id=account_id)
        
        self.metrics[account_id].current_concurrent += 1
        self.metrics[account_id].emails_processed_last_minute = len(
            self.processing_history[account_id]
        )
    
    def get_queue_stats(self) -> Dict:
        """
        Obtiene estadísticas de la cola.
        
        Returns:
            Dict: Estadísticas detalladas de la cola
        """
        with self.lock:
            stats = {
                'queue_size': self.queue.qsize(),
                'accounts_tracked': len(self.metrics),
                'accounts_with_quotas': len(self.quotas),
                'account_metrics': {}
            }
            
            for account_id, metrics in self.metrics.items():
                quota = self.quotas.get(account_id)
                stats['account_metrics'][account_id] = {
                    'emails_last_minute': metrics.emails_processed_last_minute,
                    'current_concurrent': metrics.current_concurrent,
                    'avg_processing_ms': round(metrics.average_processing_time_ms, 2),
                    'quota_per_minute': quota.max_emails_per_minute if quota else self.config.default_max_emails_per_minute,
                    'quota_concurrent': quota.max_concurrent_processing if quota else self.config.default_max_concurrent
                }
            
            return stats 