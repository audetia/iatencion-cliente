"""
Utilidades adicionales para el sistema de logging

Este módulo proporciona:
- Herramientas de análisis de logs
- Formatters personalizados
- Helpers para debugging
- Utilidades de monitoreo
"""

import os
import json
import gzip
from datetime import datetime, timedelta
from typing import Dict, List, Optional, Any, Generator
from pathlib import Path
import re

from .config import get_logger

class LogAnalyzer:
    """Analizador de logs para generar métricas y reportes"""
    
    def __init__(self, log_file_path: str):
        self.log_file_path = Path(log_file_path)
        self.logger = get_logger(__name__)
    
    def analyze_performance(self, time_window_hours: int = 24) -> Dict[str, Any]:
        """Analizar métricas de rendimiento en una ventana de tiempo"""
        cutoff_time = datetime.now() - timedelta(hours=time_window_hours)
        
        metrics = {
            'total_requests': 0,
            'error_count': 0,
            'slow_requests': 0,
            'avg_response_time': 0,
            'max_response_time': 0,
            'endpoints': {},
            'error_types': {},
            'time_window_hours': time_window_hours
        }
        
        response_times = []
        
        for log_entry in self._read_log_entries(cutoff_time):
            if 'HTTP Request' in log_entry.get('message', ''):
                metrics['total_requests'] += 1
                
                # Analizar tiempo de respuesta
                if 'process_time' in log_entry:
                    try:
                        response_time = float(log_entry['process_time'].replace('s', ''))
                        response_times.append(response_time)
                        
                        if response_time > 1.0:
                            metrics['slow_requests'] += 1
                        
                        if response_time > metrics['max_response_time']:
                            metrics['max_response_time'] = response_time
                    except (ValueError, AttributeError):
                        pass
                
                # Analizar endpoints
                path = log_entry.get('path', 'unknown')
                if path not in metrics['endpoints']:
                    metrics['endpoints'][path] = {'count': 0, 'errors': 0}
                metrics['endpoints'][path]['count'] += 1
            
            # Analizar errores
            if log_entry.get('level') == 'ERROR':
                metrics['error_count'] += 1
                error_type = log_entry.get('error_type', 'Unknown')
                
                if error_type not in metrics['error_types']:
                    metrics['error_types'][error_type] = 0
                metrics['error_types'][error_type] += 1
                
                # Contar errores por endpoint
                path = log_entry.get('path', 'unknown')
                if path in metrics['endpoints']:
                    metrics['endpoints'][path]['errors'] += 1
        
        # Calcular promedio de tiempo de respuesta
        if response_times:
            metrics['avg_response_time'] = sum(response_times) / len(response_times)
        
        # Calcular tasa de error
        if metrics['total_requests'] > 0:
            metrics['error_rate'] = (metrics['error_count'] / metrics['total_requests']) * 100
        else:
            metrics['error_rate'] = 0
        
        return metrics
    
    def find_correlation_logs(self, correlation_id: str) -> List[Dict[str, Any]]:
        """Encontrar todos los logs relacionados con un correlation ID"""
        related_logs = []
        
        for log_entry in self._read_log_entries():
            if log_entry.get('correlation_id') == correlation_id:
                related_logs.append(log_entry)
        
        # Ordenar por timestamp
        related_logs.sort(key=lambda x: x.get('timestamp', ''))
        
        return related_logs
    
    def find_error_patterns(self, hours_back: int = 24) -> Dict[str, Any]:
        """Identificar patrones en los errores"""
        cutoff_time = datetime.now() - timedelta(hours=hours_back)
        
        patterns = {
            'frequent_errors': {},
            'error_trends': {},
            'affected_endpoints': {},
            'time_distribution': {}
        }
        
        for log_entry in self._read_log_entries(cutoff_time):
            if log_entry.get('level') == 'ERROR':
                error_msg = log_entry.get('error', 'Unknown error')
                timestamp = log_entry.get('timestamp', '')
                
                # Contar errores frecuentes
                if error_msg not in patterns['frequent_errors']:
                    patterns['frequent_errors'][error_msg] = 0
                patterns['frequent_errors'][error_msg] += 1
                
                # Distribución temporal (por hora)
                if timestamp:
                    try:
                        dt = datetime.fromisoformat(timestamp.replace('Z', '+00:00'))
                        hour_key = dt.strftime('%Y-%m-%d %H:00')
                        
                        if hour_key not in patterns['time_distribution']:
                            patterns['time_distribution'][hour_key] = 0
                        patterns['time_distribution'][hour_key] += 1
                    except ValueError:
                        pass
        
        return patterns
    
    def _read_log_entries(self, cutoff_time: Optional[datetime] = None) -> Generator[Dict[str, Any], None, None]:
        """Leer entradas de log desde el archivo"""
        if not self.log_file_path.exists():
            return
        
        try:
            with open(self.log_file_path, 'r', encoding='utf-8') as f:
                for line in f:
                    line = line.strip()
                    if not line:
                        continue
                    
                    try:
                        log_entry = json.loads(line)
                        
                        # Filtrar por tiempo si se especifica
                        if cutoff_time:
                            timestamp_str = log_entry.get('timestamp', '')
                            if timestamp_str:
                                try:
                                    log_time = datetime.fromisoformat(timestamp_str.replace('Z', '+00:00'))
                                    if log_time < cutoff_time:
                                        continue
                                except ValueError:
                                    continue
                        
                        yield log_entry
                        
                    except json.JSONDecodeError:
                        # Línea no es JSON válido, saltar
                        continue
                        
        except FileNotFoundError:
            self.logger.warning(f"Log file not found: {self.log_file_path}")

class LogRotator:
    """Utilidad para rotación manual de logs"""
    
    def __init__(self, log_file_path: str, max_size_mb: int = 100, keep_files: int = 5):
        self.log_file_path = Path(log_file_path)
        self.max_size_mb = max_size_mb
        self.keep_files = keep_files
        self.logger = get_logger(__name__)
    
    def should_rotate(self) -> bool:
        """Verificar si el archivo debe ser rotado"""
        if not self.log_file_path.exists():
            return False
        
        size_mb = self.log_file_path.stat().st_size / (1024 * 1024)
        return size_mb > self.max_size_mb
    
    def rotate(self):
        """Rotar el archivo de log"""
        if not self.should_rotate():
            return
        
        timestamp = datetime.now().strftime('%Y%m%d_%H%M%S')
        rotated_path = self.log_file_path.with_suffix(f'.{timestamp}.log')
        
        # Mover archivo actual
        self.log_file_path.rename(rotated_path)
        
        # Comprimir archivo rotado
        self._compress_file(rotated_path)
        
        # Limpiar archivos antiguos
        self._cleanup_old_files()
        
        self.logger.info(f"Log file rotated: {rotated_path}")
    
    def _compress_file(self, file_path: Path):
        """Comprimir archivo de log"""
        compressed_path = file_path.with_suffix('.log.gz')
        
        with open(file_path, 'rb') as f_in:
            with gzip.open(compressed_path, 'wb') as f_out:
                f_out.writelines(f_in)
        
        # Eliminar archivo original
        file_path.unlink()
    
    def _cleanup_old_files(self):
        """Limpiar archivos de log antiguos"""
        log_dir = self.log_file_path.parent
        pattern = f"{self.log_file_path.stem}.*.log.gz"
        
        log_files = list(log_dir.glob(pattern))
        log_files.sort(key=lambda x: x.stat().st_mtime, reverse=True)
        
        # Mantener solo los archivos más recientes
        for old_file in log_files[self.keep_files:]:
            old_file.unlink()
            self.logger.info(f"Deleted old log file: {old_file}")

class DebugHelper:
    """Utilidades para debugging con logs"""
    
    @staticmethod
    def create_debug_context(context_name: str, **kwargs):
        """Crear contexto de debug con información adicional"""
        from .config import CorrelationContext
        
        debug_id = f"debug_{context_name}_{datetime.now().strftime('%Y%m%d_%H%M%S')}"
        
        return CorrelationContext(
            correlation_id_value=debug_id,
            user_id_value=kwargs.get('user_id'),
            session_id_value=kwargs.get('session_id')
        )
    
    @staticmethod
    def log_variable_state(logger, variables: Dict[str, Any], context: str = ""):
        """Log del estado de variables para debugging"""
        logger.debug(
            f"Variable state {context}",
            variables={
                key: str(value)[:100] + "..." if len(str(value)) > 100 else str(value)
                for key, value in variables.items()
            }
        )
    
    @staticmethod
    def log_function_trace(logger, function_name: str, args: tuple, kwargs: dict):
        """Log de traza de función para debugging"""
        logger.debug(
            "Function trace",
            function=function_name,
            args_count=len(args),
            kwargs_keys=list(kwargs.keys()),
            args_preview=[str(arg)[:50] for arg in args[:3]],  # Solo primeros 3 args
        )

class LogFormatter:
    """Formatters personalizados para diferentes tipos de logs"""
    
    @staticmethod
    def format_performance_log(execution_time: float, function_name: str, **kwargs) -> str:
        """Formatear log de rendimiento"""
        status = "🟢" if execution_time < 1.0 else "🟡" if execution_time < 5.0 else "🔴"
        return f"{status} {function_name} executed in {execution_time:.4f}s"
    
    @staticmethod
    def format_error_log(error: Exception, context: str = "") -> Dict[str, Any]:
        """Formatear log de error con información detallada"""
        return {
            'error_type': type(error).__name__,
            'error_message': str(error),
            'context': context,
            'traceback_lines': len(str(error.__traceback__)) if error.__traceback__ else 0
        }
    
    @staticmethod
    def format_api_log(method: str, url: str, status_code: int, response_time: float) -> str:
        """Formatear log de API call"""
        status_emoji = "✅" if 200 <= status_code < 300 else "❌"
        return f"{status_emoji} {method} {url} → {status_code} ({response_time:.3f}s)"

class MonitoringUtils:
    """Utilidades para monitoreo y alertas"""
    
    @staticmethod
    def check_log_health(log_file_path: str) -> Dict[str, Any]:
        """Verificar salud del sistema de logging"""
        log_path = Path(log_file_path)
        
        health_status = {
            'log_file_exists': log_path.exists(),
            'log_file_writable': False,
            'log_file_size_mb': 0,
            'recent_entries': 0,
            'last_entry_age_minutes': None,
            'status': 'unknown'
        }
        
        if health_status['log_file_exists']:
            try:
                # Verificar si es escribible
                health_status['log_file_writable'] = os.access(log_path, os.W_OK)
                
                # Tamaño del archivo
                health_status['log_file_size_mb'] = log_path.stat().st_size / (1024 * 1024)
                
                # Contar entradas recientes (última hora)
                cutoff_time = datetime.now() - timedelta(hours=1)
                analyzer = LogAnalyzer(str(log_path))
                
                recent_count = 0
                last_entry_time = None
                
                for log_entry in analyzer._read_log_entries(cutoff_time):
                    recent_count += 1
                    timestamp_str = log_entry.get('timestamp')
                    if timestamp_str:
                        try:
                            entry_time = datetime.fromisoformat(timestamp_str.replace('Z', '+00:00'))
                            if last_entry_time is None or entry_time > last_entry_time:
                                last_entry_time = entry_time
                        except ValueError:
                            pass
                
                health_status['recent_entries'] = recent_count
                
                if last_entry_time:
                    age_minutes = (datetime.now() - last_entry_time.replace(tzinfo=None)).total_seconds() / 60
                    health_status['last_entry_age_minutes'] = age_minutes
                
                # Determinar estado general
                if (health_status['log_file_writable'] and 
                    health_status['recent_entries'] > 0 and 
                    (health_status['last_entry_age_minutes'] is None or health_status['last_entry_age_minutes'] < 30)):
                    health_status['status'] = 'healthy'
                else:
                    health_status['status'] = 'warning'
                    
            except Exception as e:
                health_status['status'] = 'error'
                health_status['error'] = str(e)
        else:
            health_status['status'] = 'error'
        
        return health_status
    
    @staticmethod
    def generate_alert_conditions() -> List[Dict[str, Any]]:
        """Generar condiciones de alerta predefinidas"""
        return [
            {
                'name': 'High Error Rate',
                'condition': 'error_rate > 5',
                'description': 'Error rate exceeds 5%',
                'severity': 'warning'
            },
            {
                'name': 'Critical Error Rate',
                'condition': 'error_rate > 15',
                'description': 'Error rate exceeds 15%',
                'severity': 'critical'
            },
            {
                'name': 'Slow Response Time',
                'condition': 'avg_response_time > 2.0',
                'description': 'Average response time exceeds 2 seconds',
                'severity': 'warning'
            },
            {
                'name': 'No Recent Activity',
                'condition': 'last_entry_age_minutes > 60',
                'description': 'No log entries in the last hour',
                'severity': 'warning'
            }
        ] 