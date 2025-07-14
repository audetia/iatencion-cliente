"""
Modelos de datos para el sistema de fairness en procesamiento de emails.

Este módulo define las estructuras de datos necesarias para implementar
un sistema justo de procesamiento que evite que cuentas de alto volumen
monopolicen los recursos del sistema.
"""

from dataclasses import dataclass, field
from datetime import datetime
from typing import Optional, Dict, List
from enum import Enum


class AccountPriority(Enum):
    """Niveles de prioridad para cuentas basados en su volumen de emails."""
    HIGH_VOLUME = 1    # >100 emails/min - Menor prioridad
    NORMAL = 2         # 10-100 emails/min
    LOW_VOLUME = 3     # <10 emails/min - Mayor prioridad
    
    @classmethod
    def from_volume(cls, emails_per_minute: float) -> 'AccountPriority':
        """
        Determina la prioridad basada en el volumen de emails.
        
        Args:
            emails_per_minute: Promedio de emails por minuto
            
        Returns:
            AccountPriority: Nivel de prioridad correspondiente
        """
        if emails_per_minute > 100:
            return cls.HIGH_VOLUME
        elif emails_per_minute > 10:
            return cls.NORMAL
        else:
            return cls.LOW_VOLUME


@dataclass
class AccountQuota:
    """
    Define las cuotas de procesamiento para una cuenta específica.
    
    Attributes:
        account_id: ID único de la cuenta
        max_emails_per_minute: Máximo de emails a procesar por minuto
        max_concurrent_processing: Máximo de emails procesándose simultáneamente
        priority: Nivel de prioridad de la cuenta
        created_at: Timestamp de creación de la cuota
        updated_at: Timestamp de última actualización
    """
    account_id: int
    max_emails_per_minute: int = 10
    max_concurrent_processing: int = 2
    priority: AccountPriority = AccountPriority.NORMAL
    created_at: datetime = field(default_factory=datetime.now)
    updated_at: datetime = field(default_factory=datetime.now)
    
    def update_priority(self, new_priority: AccountPriority) -> None:
        """
        Actualiza la prioridad de la cuenta.
        
        Args:
            new_priority: Nueva prioridad a asignar
        """
        self.priority = new_priority
        self.updated_at = datetime.now()


@dataclass
class ProcessingMetrics:
    """
    Métricas de procesamiento para una cuenta.
    
    Attributes:
        account_id: ID de la cuenta
        emails_processed_last_minute: Emails procesados en el último minuto
        current_concurrent: Número actual de emails procesándose
        last_processed_at: Timestamp del último email procesado
        average_processing_time_ms: Tiempo promedio de procesamiento
    """
    account_id: int
    emails_processed_last_minute: int = 0
    current_concurrent: int = 0
    last_processed_at: Optional[datetime] = None
    average_processing_time_ms: float = 0.0
    
    def can_process_more(self, quota: AccountQuota) -> bool:
        """
        Verifica si la cuenta puede procesar más emails según su cuota.
        
        Args:
            quota: Cuota asignada a la cuenta
            
        Returns:
            bool: True si puede procesar más emails
        """
        return (self.current_concurrent < quota.max_concurrent_processing and
                self.emails_processed_last_minute < quota.max_emails_per_minute)


@dataclass
class EmailQueueItem:
    """
    Representa un email en la cola de procesamiento.
    
    Attributes:
        account_id: ID de la cuenta propietaria
        email_id: ID único del email
        email_data: Datos del email a procesar
        priority_score: Score de prioridad (menor = mayor prioridad)
        enqueued_at: Timestamp cuando se encoló
        retry_count: Número de reintentos
    """
    account_id: int
    email_id: str
    email_data: Dict
    priority_score: float
    enqueued_at: datetime = field(default_factory=datetime.now)
    retry_count: int = 0
    
    def __lt__(self, other: 'EmailQueueItem') -> bool:
        """Comparación para PriorityQueue (menor score = mayor prioridad)."""
        return self.priority_score < other.priority_score


@dataclass
class FairnessConfig:
    """
    Configuración del sistema de fairness.
    
    Attributes:
        default_max_emails_per_minute: Límite por defecto por cuenta
        default_max_concurrent: Concurrencia por defecto por cuenta
        high_volume_threshold: Umbral para considerar alto volumen
        normal_volume_threshold: Umbral para volumen normal
        priority_weight: Peso del factor de prioridad en el score
        wait_time_weight: Peso del tiempo de espera en el score
        max_retry_count: Máximo de reintentos por email
    """
    default_max_emails_per_minute: int = 10
    default_max_concurrent: int = 2
    high_volume_threshold: int = 100
    normal_volume_threshold: int = 10
    priority_weight: float = 0.6
    wait_time_weight: float = 0.4
    max_retry_count: int = 3 