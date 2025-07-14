"""
Servicio de gestión de fairness para procesamiento equitativo de emails.

Este servicio coordina el sistema de fairness, gestionando cuotas,
métricas y asegurando que ninguna cuenta monopolice los recursos.
"""

import threading
from datetime import datetime, timedelta
from typing import Dict, Optional, List, Tuple
from collections import defaultdict

from src.database import db_manager
from src.models.fairness import (
    AccountQuota,
    AccountPriority,
    FairnessConfig,
    ProcessingMetrics
)
from src.infra.queue import FairPriorityQueue
from custom_logging.config import get_logger

logger = get_logger(__name__)


class FairnessManager:
    """
    Gestor central del sistema de fairness.
    
    Responsabilidades:
    - Gestionar cuotas dinámicas por cuenta
    - Analizar patrones de uso y ajustar prioridades
    - Coordinar la cola de prioridad justa
    - Proporcionar métricas de fairness
    """
    
    def __init__(self, config: Optional[FairnessConfig] = None):
        """
        Inicializa el gestor de fairness.
        
        Args:
            config: Configuración del sistema de fairness
        """
        self.config = config or FairnessConfig()
        self.fair_queue = FairPriorityQueue(self.config)
        self.lock = threading.Lock()
        
        # Tracking de volumen histórico
        self.volume_history: Dict[int, List[Tuple[datetime, int]]] = defaultdict(list)
        
        # Thread para análisis periódico
        self.analysis_thread: Optional[threading.Thread] = None
        self.shutdown_event = threading.Event()
        
        logger.info("⚖️ FairnessManager inicializado", extra={
            "default_quota": self.config.default_max_emails_per_minute,
            "high_volume_threshold": self.config.high_volume_threshold
        })
    
    def start(self) -> None:
        """Inicia el servicio de gestión de fairness."""
        if self.analysis_thread and self.analysis_thread.is_alive():
            logger.warning("FairnessManager ya está ejecutándose")
            return
        
        self.shutdown_event.clear()
        self.analysis_thread = threading.Thread(
            target=self._analysis_loop,
            name="fairness_analysis",
            daemon=True
        )
        self.analysis_thread.start()
        logger.info("⚖️ FairnessManager iniciado")
    
    def stop(self) -> None:
        """Detiene el servicio de gestión de fairness."""
        self.shutdown_event.set()
        if self.analysis_thread and self.analysis_thread.is_alive():
            self.analysis_thread.join(timeout=5)
        logger.info("⚖️ FairnessManager detenido")
    
    def enqueue_email(self, account_id: int, email_id: str, email_data: Dict) -> None:
        """
        Encola un email para procesamiento justo.
        
        Args:
            account_id: ID de la cuenta
            email_id: ID único del email
            email_data: Datos del email
        """
        # Registrar volumen
        self._record_volume(account_id)
        
        # Encolar con prioridad justa
        self.fair_queue.put(account_id, email_id, email_data)
    
    def get_next_email(self, timeout: float = 1.0) -> Optional[Tuple[int, str, Dict]]:
        """
        Obtiene el siguiente email a procesar respetando fairness.
        
        Args:
            timeout: Timeout en segundos
            
        Returns:
            Tupla (account_id, email_id, email_data) si hay email disponible
        """
        item = self.fair_queue.get(timeout=timeout)
        if item:
            return item.account_id, item.email_id, item.email_data
        return None
    
    def complete_processing(self, account_id: int, processing_time_ms: float) -> None:
        """
        Marca un email como procesado.
        
        Args:
            account_id: ID de la cuenta
            processing_time_ms: Tiempo de procesamiento en ms
        """
        self.fair_queue.complete_processing(account_id, processing_time_ms)
    
    def set_account_quota(self, account_id: int, quota: AccountQuota) -> None:
        """
        Establece una cuota específica para una cuenta.
        
        Args:
            account_id: ID de la cuenta
            quota: Cuota a aplicar
        """
        self.fair_queue.set_quota(account_id, quota)
        
        # Persistir en base de datos si es necesario
        self._persist_quota(account_id, quota)
    
    def get_fairness_metrics(self) -> Dict:
        """
        Obtiene métricas del sistema de fairness.
        
        Returns:
            Dict: Métricas detalladas de fairness
        """
        queue_stats = self.fair_queue.get_queue_stats()
        
        # Calcular métricas de equidad
        fairness_score = self._calculate_fairness_score(queue_stats)
        
        return {
            'fairness_score': fairness_score,
            'queue_stats': queue_stats,
            'volume_analysis': self._get_volume_analysis(),
            'recommendations': self._get_optimization_recommendations()
        }
    
    def _record_volume(self, account_id: int) -> None:
        """
        Registra el volumen de emails de una cuenta.
        
        Args:
            account_id: ID de la cuenta
        """
        with self.lock:
            now = datetime.now()
            if account_id not in self.volume_history:
                self.volume_history[account_id] = []
            
            # Mantener solo últimas 24 horas
            cutoff = now - timedelta(hours=24)
            self.volume_history[account_id] = [
                (ts, count) for ts, count in self.volume_history[account_id]
                if ts > cutoff
            ]
            
            # Añadir nuevo registro
            self.volume_history[account_id].append((now, 1))
    
    def _analysis_loop(self) -> None:
        """Loop de análisis periódico de patrones de uso."""
        analysis_interval = 300  # 5 minutos
        
        while not self.shutdown_event.wait(analysis_interval):
            try:
                self._analyze_and_adjust_quotas()
            except Exception as e:
                logger.error(f"Error en análisis de fairness: {str(e)}", exc_info=True)
    
    def _analyze_and_adjust_quotas(self) -> None:
        """Analiza patrones de uso y ajusta cuotas dinámicamente."""
        with self.lock:
            for account_id, history in self.volume_history.items():
                if not history:
                    continue
                
                # Calcular volumen promedio por minuto
                now = datetime.now()
                minute_ago = now - timedelta(minutes=1)
                hour_ago = now - timedelta(hours=1)
                
                # Emails en último minuto
                emails_last_minute = sum(
                    1 for ts, _ in history if ts > minute_ago
                )
                
                # Emails en última hora
                emails_last_hour = sum(
                    1 for ts, _ in history if ts > hour_ago
                )
                
                # Promedio por minuto
                avg_per_minute = emails_last_hour / 60 if emails_last_hour > 0 else 0
                
                # Determinar prioridad basada en volumen
                priority = AccountPriority.from_volume(avg_per_minute)
                
                # Obtener cuota actual
                current_quota = self.fair_queue.quotas.get(account_id)
                
                # Ajustar si es necesario
                if not current_quota or current_quota.priority != priority:
                    new_quota = AccountQuota(
                        account_id=account_id,
                        max_emails_per_minute=self._calculate_dynamic_quota(priority, avg_per_minute),
                        max_concurrent_processing=self._calculate_concurrent_limit(priority),
                        priority=priority
                    )
                    
                    self.set_account_quota(account_id, new_quota)
                    
                    logger.info(f"📊 Cuota ajustada dinámicamente", extra={
                        "account_id": account_id,
                        "old_priority": current_quota.priority.name if current_quota else "NONE",
                        "new_priority": priority.name,
                        "avg_per_minute": round(avg_per_minute, 2),
                        "new_quota": new_quota.max_emails_per_minute
                    })
    
    def _calculate_dynamic_quota(self, priority: AccountPriority, avg_volume: float) -> int:
        """
        Calcula cuota dinámica basada en prioridad y volumen.
        
        Args:
            priority: Prioridad de la cuenta
            avg_volume: Volumen promedio por minuto
            
        Returns:
            int: Cuota de emails por minuto
        """
        base_quotas = {
            AccountPriority.HIGH_VOLUME: 5,
            AccountPriority.NORMAL: 10,
            AccountPriority.LOW_VOLUME: 20
        }
        
        base_quota = base_quotas.get(priority, self.config.default_max_emails_per_minute)
        
        # Ajustar basado en volumen real
        if priority == AccountPriority.HIGH_VOLUME and avg_volume > 200:
            # Casos extremos necesitan límites más estrictos
            return max(3, base_quota // 2)
        
        return base_quota
    
    def _calculate_concurrent_limit(self, priority: AccountPriority) -> int:
        """
        Calcula límite de concurrencia basado en prioridad.
        
        Args:
            priority: Prioridad de la cuenta
            
        Returns:
            int: Límite de procesamiento concurrente
        """
        concurrent_limits = {
            AccountPriority.HIGH_VOLUME: 1,
            AccountPriority.NORMAL: 2,
            AccountPriority.LOW_VOLUME: 3
        }
        
        return concurrent_limits.get(priority, self.config.default_max_concurrent)
    
    def _calculate_fairness_score(self, queue_stats: Dict) -> float:
        """
        Calcula un score de equidad del sistema (0-100).
        
        Args:
            queue_stats: Estadísticas de la cola
            
        Returns:
            float: Score de fairness (100 = perfectamente justo)
        """
        if not queue_stats['account_metrics']:
            return 100.0
        
        # Calcular varianza en utilización de cuotas
        utilizations = []
        for account_id, metrics in queue_stats['account_metrics'].items():
            if metrics['quota_per_minute'] > 0:
                utilization = metrics['emails_last_minute'] / metrics['quota_per_minute']
                utilizations.append(min(utilization, 1.0))
        
        if not utilizations:
            return 100.0
        
        # Menor varianza = más justo
        avg_utilization = sum(utilizations) / len(utilizations)
        variance = sum((u - avg_utilization) ** 2 for u in utilizations) / len(utilizations)
        
        # Convertir a score 0-100 (menor varianza = mayor score)
        fairness_score = max(0, 100 - (variance * 200))
        
        return round(fairness_score, 2)
    
    def _get_volume_analysis(self) -> Dict:
        """
        Obtiene análisis de volumen por cuenta.
        
        Returns:
            Dict: Análisis detallado de volúmenes
        """
        analysis = {}
        
        with self.lock:
            now = datetime.now()
            hour_ago = now - timedelta(hours=1)
            
            for account_id, history in self.volume_history.items():
                emails_last_hour = sum(1 for ts, _ in history if ts > hour_ago)
                
                if emails_last_hour > 0:
                    analysis[account_id] = {
                        'emails_last_hour': emails_last_hour,
                        'avg_per_minute': round(emails_last_hour / 60, 2),
                        'priority': self._get_account_priority(account_id)
                    }
        
        return analysis
    
    def _get_account_priority(self, account_id: int) -> str:
        """Obtiene la prioridad actual de una cuenta."""
        quota = self.fair_queue.quotas.get(account_id)
        if quota:
            return quota.priority.name
        return "UNKNOWN"
    
    def _get_optimization_recommendations(self) -> List[str]:
        """
        Genera recomendaciones de optimización.
        
        Returns:
            List[str]: Lista de recomendaciones
        """
        recommendations = []
        queue_stats = self.fair_queue.get_queue_stats()
        
        # Verificar si hay cuentas cerca del límite
        for account_id, metrics in queue_stats['account_metrics'].items():
            utilization = metrics['emails_last_minute'] / metrics['quota_per_minute'] if metrics['quota_per_minute'] > 0 else 0
            
            if utilization > 0.9:
                recommendations.append(
                    f"Cuenta {account_id} está al {int(utilization * 100)}% de su cuota. "
                    f"Considerar ajustar límites o añadir más workers."
                )
        
        # Verificar fairness score
        fairness_score = self._calculate_fairness_score(queue_stats)
        if fairness_score < 70:
            recommendations.append(
                f"Fairness score bajo ({fairness_score}%). "
                "Revisar distribución de cuotas entre cuentas."
            )
        
        # Verificar tamaño de cola
        if queue_stats['queue_size'] > 100:
            recommendations.append(
                f"Cola con {queue_stats['queue_size']} emails pendientes. "
                "Considerar aumentar capacidad de procesamiento."
            )
        
        return recommendations
    
    def _persist_quota(self, account_id: int, quota: AccountQuota) -> None:
        """
        Persiste la cuota en base de datos.
        
        Args:
            account_id: ID de la cuenta
            quota: Cuota a persistir
        """
        try:
            # Aquí se podría guardar en una tabla de cuotas
            # Por ahora solo log
            logger.debug(f"Cuota persistida para cuenta {account_id}", extra={
                "max_per_minute": quota.max_emails_per_minute,
                "max_concurrent": quota.max_concurrent_processing,
                "priority": quota.priority.name
            })
        except Exception as e:
            logger.error(f"Error persistiendo cuota: {str(e)}", exc_info=True) 