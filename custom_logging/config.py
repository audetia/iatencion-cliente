"""
Sistema de Logging SOTA (State-of-the-Art) para iatencion-cliente

Este módulo proporciona un sistema de logging avanzado con:
- Logs estructurados en formato JSON
- IDs de correlación para trazabilidad
- Diferentes niveles de logging
- Configuración centralizada
- Integración con FastAPI y LangGraph
- Filtrado de información sensible
- Sampling para alto tráfico
"""

import os
import sys
import uuid
import time
import json
from typing import Any, Dict, Optional, Union
from contextvars import ContextVar
from pathlib import Path
from datetime import datetime

import structlog
from loguru import logger as loguru_logger
from pythonjsonlogger import jsonlogger

# Context variables para tracking de correlación
correlation_id: ContextVar[Optional[str]] = ContextVar('correlation_id', default=None)
user_id: ContextVar[Optional[str]] = ContextVar('user_id', default=None)
session_id: ContextVar[Optional[str]] = ContextVar('session_id', default=None)

class CorrelationIdProcessor:
    """Procesador para agregar IDs de correlación a todos los logs"""
    
    def __call__(self, logger, method_name, event_dict):
        # Agregar correlation_id si existe
        if correlation_id.get():
            event_dict['correlation_id'] = correlation_id.get()
        
        # Agregar user_id si existe
        if user_id.get():
            event_dict['user_id'] = user_id.get()
            
        # Agregar session_id si existe
        if session_id.get():
            event_dict['session_id'] = session_id.get()
            
        return event_dict

class SensitiveDataFilter:
    """Filtro para remover información sensible de los logs"""
    
    SENSITIVE_KEYS = {
        'password', 'token', 'api_key', 'secret', 'auth', 'authorization',
        'cookie', 'session', 'private_key', 'access_token', 'refresh_token',
        'gmail_credentials', 'email_password', 'smtp_password'
    }
    
    def __call__(self, logger, method_name, event_dict):
        return self._filter_sensitive_data(event_dict)
    
    def _filter_sensitive_data(self, data):
        """Recursivamente filtra datos sensibles"""
        if isinstance(data, dict):
            filtered = {}
            for key, value in data.items():
                if any(sensitive in key.lower() for sensitive in self.SENSITIVE_KEYS):
                    filtered[key] = '[REDACTED]'
                else:
                    filtered[key] = self._filter_sensitive_data(value)
            return filtered
        elif isinstance(data, list):
            return [self._filter_sensitive_data(item) for item in data]
        else:
            return data

class PerformanceProcessor:
    """Procesador para agregar métricas de rendimiento"""
    
    def __call__(self, logger, method_name, event_dict):
        event_dict['timestamp'] = datetime.utcnow().isoformat()
        event_dict['level'] = method_name.upper()
        return event_dict

class SamplingFilter:
    """Filtro de sampling para reducir logs repetitivos en alto tráfico"""
    
    def __init__(self, sample_rate: float = 0.1):
        self.sample_rate = sample_rate
        self.last_logged = {}
        self.sample_counter = {}
    
    def __call__(self, logger, method_name, event_dict):
        # Si es un error crítico, siempre logear
        if method_name in ['error', 'critical', 'exception']:
            return event_dict
            
        # Para eventos repetitivos, aplicar sampling
        event_key = self._get_event_key(event_dict)
        
        if event_key in self.sample_counter:
            self.sample_counter[event_key] += 1
            if self.sample_counter[event_key] % int(1/self.sample_rate) != 0:
                raise structlog.DropEvent
        else:
            self.sample_counter[event_key] = 1
            
        return event_dict
    
    def _get_event_key(self, event_dict):
        """Genera una clave única para el evento basada en el mensaje y contexto"""
        return f"{event_dict.get('event', '')}-{event_dict.get('module', '')}"

class LoggingConfig:
    """Configuración centralizada del sistema de logging"""
    
    def __init__(self):
        self.log_level = os.getenv('LOG_LEVEL', 'INFO').upper()
        self.log_format = os.getenv('LOG_FORMAT', 'JSON')  # JSON o CONSOLE
        self.log_file = os.getenv('LOG_FILE', 'logs/app.log')
        self.enable_sampling = os.getenv('ENABLE_LOG_SAMPLING', 'false').lower() == 'true'
        self.sample_rate = float(os.getenv('LOG_SAMPLE_RATE', '0.1'))
        self.max_log_size = os.getenv('MAX_LOG_SIZE', '100MB')
        self.backup_count = int(os.getenv('LOG_BACKUP_COUNT', '5'))
        
        # Crear directorio de logs si no existe
        Path(self.log_file).parent.mkdir(parents=True, exist_ok=True)
        
        self._setup_structlog()
        self._setup_loguru()
    
    def _setup_structlog(self):
        """Configurar structlog para logs estructurados"""
        processors = [
            SensitiveDataFilter(),
            CorrelationIdProcessor(),
            PerformanceProcessor(),
            structlog.stdlib.add_log_level,
            structlog.processors.TimeStamper(fmt="ISO"),
        ]
        
        # Agregar sampling si está habilitado
        if self.enable_sampling:
            processors.insert(0, SamplingFilter(self.sample_rate))
        
        if self.log_format == 'JSON':
            processors.append(structlog.processors.JSONRenderer())
        else:
            processors.extend([
                structlog.dev.ConsoleRenderer(colors=True),
            ])
        
        structlog.configure(
            processors=processors,
            wrapper_class=structlog.stdlib.BoundLogger,
            logger_factory=structlog.stdlib.LoggerFactory(),
            cache_logger_on_first_use=True,
        )
    
    def _setup_loguru(self):
        """Configurar loguru para logging avanzado con rotación"""
        # Remover handler por defecto
        loguru_logger.remove()
        
        # Configurar formato
        if self.log_format == 'JSON':
            log_format = self._get_json_format()
        else:
            log_format = (
                "<green>{time:YYYY-MM-DD HH:mm:ss.SSS}</green> | "
                "<level>{level: <8}</level> | "
                "<cyan>{name}</cyan>:<cyan>{function}</cyan>:<cyan>{line}</cyan> | "
                "<level>{message}</level>"
            )
        
        # Handler para consola
        loguru_logger.add(
            sys.stdout,
            format=log_format,
            level=self.log_level,
            colorize=self.log_format != 'JSON',
            serialize=self.log_format == 'JSON'
        )
        
        # Handler para archivo con rotación
        loguru_logger.add(
            self.log_file,
            format=log_format,
            level=self.log_level,
            rotation=self.max_log_size,
            retention=f"{self.backup_count} files",
            compression="zip",
            serialize=self.log_format == 'JSON',
            enqueue=True  # Thread-safe
        )
    
    def _get_json_format(self):
        """Formato JSON personalizado para loguru"""
        def json_formatter(record):
            log_entry = {
                "timestamp": record["time"].isoformat(),
                "level": record["level"].name,
                "logger": record["name"],
                "module": record["module"],
                "function": record["function"],
                "line": record["line"],
                "message": record["message"],
                "process_id": record["process"].id,
                "thread_id": record["thread"].id,
            }
            
            # Agregar contexto de correlación si existe
            if correlation_id.get():
                log_entry["correlation_id"] = correlation_id.get()
            if user_id.get():
                log_entry["user_id"] = user_id.get()
            if session_id.get():
                log_entry["session_id"] = session_id.get()
            
            # Agregar extra data si existe
            if record.get("extra"):
                log_entry.update(record["extra"])
            
            return json.dumps(log_entry)
        
        return json_formatter

# Instancia global de configuración
_config = None

def setup_logging():
    """Inicializar el sistema de logging"""
    global _config
    if _config is None:
        _config = LoggingConfig()
    return _config

def get_logger(name: str = None):
    """
    Obtener un logger configurado
    
    Args:
        name: Nombre del logger (opcional)
    
    Returns:
        Logger configurado con structlog
    """
    if _config is None:
        setup_logging()
    
    return structlog.get_logger(name or __name__)

def get_loguru_logger():
    """
    Obtener el logger de loguru configurado
    
    Returns:
        Logger de loguru configurado
    """
    if _config is None:
        setup_logging()
    
    return loguru_logger

# Context managers para tracking
class CorrelationContext:
    """Context manager para tracking de correlación"""
    
    def __init__(self, correlation_id_value: str = None, user_id_value: str = None, session_id_value: str = None):
        self.correlation_id_value = correlation_id_value or str(uuid.uuid4())
        self.user_id_value = user_id_value
        self.session_id_value = session_id_value
        self.correlation_token = None
        self.user_token = None
        self.session_token = None
    
    def __enter__(self):
        self.correlation_token = correlation_id.set(self.correlation_id_value)
        if self.user_id_value:
            self.user_token = user_id.set(self.user_id_value)
        if self.session_id_value:
            self.session_token = session_id.set(self.session_id_value)
        return self
    
    def __exit__(self, exc_type, exc_val, exc_tb):
        if self.correlation_token:
            correlation_id.reset(self.correlation_token)
        if self.user_token:
            user_id.reset(self.user_token)
        if self.session_token:
            session_id.reset(self.session_token)

# Decoradores útiles
def log_execution_time(logger=None):
    """Decorador para logear tiempo de ejecución de funciones"""
    def decorator(func):
        def wrapper(*args, **kwargs):
            _logger = logger or get_logger(func.__module__)
            start_time = time.time()
            
            try:
                result = func(*args, **kwargs)
                execution_time = time.time() - start_time
                _logger.info(
                    "Function executed successfully",
                    function=func.__name__,
                    execution_time=f"{execution_time:.4f}s",
                    args_count=len(args),
                    kwargs_keys=list(kwargs.keys())
                )
                return result
            except Exception as e:
                execution_time = time.time() - start_time
                _logger.error(
                    "Function execution failed",
                    function=func.__name__,
                    execution_time=f"{execution_time:.4f}s",
                    error=str(e),
                    error_type=type(e).__name__
                )
                raise
        
        return wrapper
    return decorator

def log_method_calls(logger=None):
    """Decorador para logear llamadas a métodos de clase"""
    def decorator(func):
        def wrapper(self, *args, **kwargs):
            _logger = logger or get_logger(self.__class__.__module__)
            
            _logger.debug(
                "Method called",
                class_name=self.__class__.__name__,
                method=func.__name__,
                args_count=len(args),
                kwargs_keys=list(kwargs.keys())
            )
            
            try:
                result = func(self, *args, **kwargs)
                _logger.debug(
                    "Method completed successfully",
                    class_name=self.__class__.__name__,
                    method=func.__name__
                )
                return result
            except Exception as e:
                _logger.error(
                    "Method execution failed",
                    class_name=self.__class__.__name__,
                    method=func.__name__,
                    error=str(e),
                    error_type=type(e).__name__
                )
                raise
        
        return wrapper
    return decorator 