"""
Sistema de Logging SOTA (State-of-the-Art) para iatencion-cliente

Este paquete proporciona un sistema de logging avanzado con:
- Logs estructurados en formato JSON
- IDs de correlación para trazabilidad
- Diferentes niveles de logging
- Configuración centralizada
- Integración con FastAPI y LangGraph
- Filtrado de información sensible
- Sampling para alto tráfico
"""

from .config import (
    setup_logging,
    get_logger,
    get_loguru_logger,
    CorrelationContext,
    log_execution_time,
    log_method_calls
)

from .middleware import (
    LoggingMiddleware,
    MetricsMiddleware
)

__all__ = [
    'setup_logging',
    'get_logger', 
    'get_loguru_logger',
    'CorrelationContext',
    'log_execution_time',
    'log_method_calls',
    'LoggingMiddleware',
    'MetricsMiddleware'
]

__version__ = '1.0.0' 