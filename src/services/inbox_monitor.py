"""
Servicio de Monitoreo de Buzones de Email.

Este servicio se encarga de monitorear continuamente los buzones de email activos,
procesando emails nuevos y gestionando múltiples cuentas de forma concurrente.

Responsabilidades:
- Monitorear múltiples cuentas de email de forma concurrente
- Respetar límites de rate limiting para conexiones IMAP
- Gestionar thread pools para procesamiento paralelo
- Manejar errores de conexión con reintentos
- Procesar emails nuevos a través del workflow de LangGraph
- Sistema de heartbeat para detectar threads muertos
- Métricas de rendimiento en tiempo real
- Sistema de alertas críticas por Telegram
"""

import time
import threading
import os
from datetime import datetime, timedelta
from typing import List, Dict, Optional, Callable
from concurrent.futures import ThreadPoolExecutor, as_completed, Future
import concurrent.futures
from dataclasses import dataclass, field
from queue import Queue, Empty
from collections import defaultdict, deque
import signal
import sys
import statistics
import asyncio
from enum import Enum

# Importaciones locales
from src.database import db_manager
from src.tools.EmailTools import EmailToolsClass
from src.tools.telegram import send_text_telegram
from custom_logging.config import get_logger, CorrelationContext
from src.services.fairness_manager import FairnessManager
from src.services.email_queue_service import EmailQueueProcessor
from src.models.fairness import FairnessConfig, AccountQuota, AccountPriority

# Configurar logging específico para este servicio
logger = get_logger(__name__)


class AlertLevel(Enum):
    """Niveles de alerta para el sistema de notificaciones."""
    INFO = "INFO"
    WARNING = "WARNING" 
    ERROR = "ERROR"
    CRITICAL = "CRITICAL"


@dataclass
class PerformanceMetrics:
    """Métricas de rendimiento del sistema de monitoreo."""
    emails_processed_total: int = 0
    emails_per_minute: float = 0.0
    average_latency_ms: float = 0.0
    peak_latency_ms: float = 0.0
    successful_connections: int = 0
    failed_connections: int = 0
    active_threads: int = 0
    thread_utilization: float = 0.0
    start_time: datetime = field(default_factory=datetime.now)
    last_reset: datetime = field(default_factory=datetime.now)
    
    # Ventanas deslizantes para cálculos en tiempo real
    latency_window: deque = field(default_factory=lambda: deque(maxlen=100))
    emails_window: deque = field(default_factory=lambda: deque(maxlen=60))  # 60 minutos
    
    def add_email_processed(self, latency_ms: float) -> None:
        """Registra un email procesado con su latencia."""
        self.emails_processed_total += 1
        self.latency_window.append(latency_ms)
        self.emails_window.append((datetime.now(), 1))
        
        # Actualizar métricas
        if self.latency_window:
            self.average_latency_ms = statistics.mean(self.latency_window)
            self.peak_latency_ms = max(self.latency_window)
        
        # Calcular emails por minuto
        now = datetime.now()
        minute_ago = now - timedelta(minutes=1)
        recent_emails = sum(count for timestamp, count in self.emails_window 
                          if timestamp > minute_ago)
        self.emails_per_minute = recent_emails
    
    def add_connection_attempt(self, success: bool) -> None:
        """Registra un intento de conexión."""
        if success:
            self.successful_connections += 1
        else:
            self.failed_connections += 1
    
    def update_thread_metrics(self, active_threads: int, max_threads: int) -> None:
        """Actualiza métricas de threads."""
        self.active_threads = active_threads
        self.thread_utilization = (active_threads / max_threads) * 100 if max_threads > 0 else 0
    
    def get_summary(self) -> Dict:
        """Obtiene un resumen de las métricas."""
        uptime = (datetime.now() - self.start_time).total_seconds()
        total_connections = self.successful_connections + self.failed_connections
        success_rate = (self.successful_connections / total_connections * 100) if total_connections > 0 else 0
        
        return {
            'emails_processed_total': self.emails_processed_total,
            'emails_per_minute': round(self.emails_per_minute, 2),
            'average_latency_ms': round(self.average_latency_ms, 2),
            'peak_latency_ms': round(self.peak_latency_ms, 2),
            'connection_success_rate': round(success_rate, 2),
            'thread_utilization': round(self.thread_utilization, 2),
            'uptime_hours': round(uptime / 3600, 2),
            'throughput_per_hour': round((self.emails_processed_total / uptime * 3600), 2) if uptime > 0 else 0
        }


@dataclass
class HeartbeatConfig:
    """Configuración del sistema de heartbeat."""
    interval_seconds: int = 30  # Intervalo entre heartbeats
    timeout_seconds: int = 120  # Timeout para considerar thread muerto
    max_missed_beats: int = 3   # Máximo de heartbeats perdidos antes de alerta


@dataclass
class ThreadInfo:
    """Información de tracking para threads."""
    thread_id: str
    account_id: int
    last_heartbeat: datetime
    status: str = "active"
    missed_beats: int = 0
    future: Optional[Future] = None


@dataclass
class MonitoringConfig:
    """Configuración para el monitoreo de buzones."""
    max_workers: int = 5  # Máximo de threads concurrentes
    rate_limit_delay: float = 2.0  # Segundos entre conexiones IMAP por cuenta
    batch_size: int = 10  # Máximo de emails a procesar por lote
    check_interval: int = 300  # Intervalo entre verificaciones (5 minutos)
    connection_timeout: int = 30  # Timeout para conexiones IMAP en segundos
    max_retries: int = 3  # Máximo de reintentos por cuenta en caso de error
    retry_delay: float = 60.0  # Delay entre reintentos en segundos
    
    # Configuración de alertas
    enable_telegram_alerts: bool = True
    telegram_bot_token: str = field(default_factory=lambda: os.getenv("TG_BOT_TOKEN_STATUS", ""))
    telegram_chat_id: str = field(default_factory=lambda: os.getenv("TG_CHAT_ID_STATUS", ""))
    alert_cooldown_minutes: int = 15  # Cooldown entre alertas del mismo tipo
    
    # Configuración de heartbeat y métricas
    heartbeat_config: HeartbeatConfig = field(default_factory=HeartbeatConfig)
    metrics_reset_interval_hours: int = 24  # Resetear métricas cada 24 horas
    
    # Configuración de graceful shutdown
    shutdown_timeout_seconds: int = 30  # Timeout para esperar finalización de tareas
    thread_pool_shutdown_timeout: int = 15  # Timeout para cerrar thread pool
    
    # Configuración de fairness
    enable_fairness: bool = True  # Habilitar sistema de fairness
    fairness_config: FairnessConfig = field(default_factory=FairnessConfig)


@dataclass
class AccountMonitoringState:
    """Estado de monitoreo para una cuenta específica."""
    account_id: int
    email: str
    last_check: Optional[datetime] = None
    consecutive_errors: int = 0
    last_error: Optional[str] = None
    is_active: bool = True
    retry_after: Optional[datetime] = None


class AlertManager:
    """
    Gestor de alertas para el sistema de monitoreo.
    
    Maneja el envío de alertas por Telegram con cooldowns y formateo apropiado.
    """
    
    def __init__(self, config: MonitoringConfig):
        """
        Inicializa el gestor de alertas.
        
        Args:
            config (MonitoringConfig): Configuración del monitoreo
        """
        self.config = config
        self.last_alerts: Dict[str, datetime] = {}
        self.alert_lock = threading.Lock()
        
    def should_send_alert(self, alert_type: str) -> bool:
        """
        Verifica si se debe enviar una alerta basado en el cooldown.
        
        Args:
            alert_type (str): Tipo de alerta
            
        Returns:
            bool: True si se debe enviar la alerta
        """
        with self.alert_lock:
            now = datetime.now()
            last_sent = self.last_alerts.get(alert_type)
            
            if not last_sent:
                return True
            
            cooldown = timedelta(minutes=self.config.alert_cooldown_minutes)
            return (now - last_sent) > cooldown
    
    def send_alert(self, level: AlertLevel, title: str, message: str, 
                   alert_type: str = None) -> bool:
        """
        Envía una alerta por Telegram si está habilitado y cumple condiciones.
        
        Args:
            level (AlertLevel): Nivel de alerta
            title (str): Título de la alerta
            message (str): Mensaje de la alerta
            alert_type (str, optional): Tipo de alerta para cooldown
            
        Returns:
            bool: True si la alerta fue enviada exitosamente
        """
        if not self.config.enable_telegram_alerts:
            logger.debug("Alertas de Telegram deshabilitadas")
            return False
            
        if not self.config.telegram_bot_token or not self.config.telegram_chat_id:
            logger.warning("Token o Chat ID de Telegram no configurados")
            return False
        
        # Verificar cooldown si se especifica tipo de alerta
        if alert_type and not self.should_send_alert(alert_type):
            logger.debug(f"Alerta {alert_type} en cooldown, no enviando")
            return False
        
        try:
            # Formatear mensaje con emojis según el nivel
            emoji_map = {
                AlertLevel.INFO: "ℹ️",
                AlertLevel.WARNING: "⚠️", 
                AlertLevel.ERROR: "❌",
                AlertLevel.CRITICAL: "🚨"
            }
            
            emoji = emoji_map.get(level, "📬")
            timestamp = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
            
            formatted_message = f"""
{emoji} *{level.value}: {title}*

{message}

🕐 {timestamp}
🖥️ InboxMonitor Service
            """.strip()
            
            # Enviar alerta
            send_text_telegram(
                txt=formatted_message,
                chat_id=self.config.telegram_chat_id,
                token=self.config.telegram_bot_token,
                parse_mode='Markdown'
            )
            
            # Actualizar timestamp de última alerta
            if alert_type:
                with self.alert_lock:
                    self.last_alerts[alert_type] = datetime.now()
            
            logger.info(f"Alerta enviada por Telegram: {title}")
            return True
            
        except Exception as e:
            logger.error(f"Error enviando alerta por Telegram: {str(e)}", exc_info=True)
            return False


class HeartbeatMonitor:
    """
    Monitor de heartbeat para detectar threads muertos.
    
    Rastrea la actividad de todos los threads de monitoreo y detecta
    cuando alguno deja de responder.
    """
    
    def __init__(self, config: HeartbeatConfig, alert_manager: AlertManager):
        """
        Inicializa el monitor de heartbeat.
        
        Args:
            config (HeartbeatConfig): Configuración del heartbeat
            alert_manager (AlertManager): Gestor de alertas
        """
        self.config = config
        self.alert_manager = alert_manager
        self.threads: Dict[str, ThreadInfo] = {}
        self.monitor_thread: Optional[threading.Thread] = None
        self.shutdown_event = threading.Event()
        self.lock = threading.Lock()
        
    def register_thread(self, thread_id: str, account_id: int, future: Future = None) -> None:
        """
        Registra un nuevo thread para monitoreo.
        
        Args:
            thread_id (str): ID único del thread
            account_id (int): ID de la cuenta asociada
            future (Future, optional): Future object del thread
        """
        with self.lock:
            self.threads[thread_id] = ThreadInfo(
                thread_id=thread_id,
                account_id=account_id,
                last_heartbeat=datetime.now(),
                future=future
            )
            logger.debug(f"Thread {thread_id} registrado para cuenta {account_id}")
    
    def update_heartbeat(self, thread_id: str) -> None:
        """
        Actualiza el heartbeat de un thread.
        
        Args:
            thread_id (str): ID del thread
        """
        with self.lock:
            if thread_id in self.threads:
                self.threads[thread_id].last_heartbeat = datetime.now()
                self.threads[thread_id].missed_beats = 0
                self.threads[thread_id].status = "active"
    
    def unregister_thread(self, thread_id: str) -> None:
        """
        Desregistra un thread del monitoreo.
        
        Args:
            thread_id (str): ID del thread
        """
        with self.lock:
            if thread_id in self.threads:
                del self.threads[thread_id]
                logger.debug(f"Thread {thread_id} desregistrado")
    
    def start_monitoring(self) -> None:
        """Inicia el monitoreo de heartbeats en un thread separado."""
        if self.monitor_thread and self.monitor_thread.is_alive():
            logger.warning("Monitor de heartbeat ya está ejecutándose")
            return
            
        self.shutdown_event.clear()
        self.monitor_thread = threading.Thread(
            target=self._monitor_loop,
            name="heartbeat_monitor",
            daemon=True
        )
        self.monitor_thread.start()
        logger.info("Monitor de heartbeat iniciado")
    
    def stop_monitoring(self) -> None:
        """Detiene el monitoreo de heartbeats."""
        self.shutdown_event.set()
        if self.monitor_thread and self.monitor_thread.is_alive():
            self.monitor_thread.join(timeout=5)
        logger.info("Monitor de heartbeat detenido")
    
    def _monitor_loop(self) -> None:
        """Loop principal del monitor de heartbeat."""
        while not self.shutdown_event.wait(self.config.interval_seconds):
            try:
                self._check_thread_health()
            except Exception as e:
                logger.error(f"Error en monitor de heartbeat: {str(e)}", exc_info=True)
    
    def _check_thread_health(self) -> None:
        """Verifica la salud de todos los threads registrados."""
        now = datetime.now()
        timeout_threshold = timedelta(seconds=self.config.timeout_seconds)
        dead_threads = []
        
        with self.lock:
            for thread_id, thread_info in list(self.threads.items()):
                time_since_heartbeat = now - thread_info.last_heartbeat
                
                if time_since_heartbeat > timeout_threshold:
                    thread_info.missed_beats += 1
                    
                    if thread_info.missed_beats >= self.config.max_missed_beats:
                        thread_info.status = "dead"
                        dead_threads.append(thread_info)
                        
                        logger.error(f"Thread muerto detectado: {thread_id} (cuenta {thread_info.account_id})")
                        
                        # Enviar alerta crítica
                        self.alert_manager.send_alert(
                            level=AlertLevel.CRITICAL,
                            title="Thread Muerto Detectado",
                            message=f"Thread {thread_id} para cuenta {thread_info.account_id} no responde desde hace {time_since_heartbeat}",
                            alert_type="dead_thread"
                        )
                        
                        # Intentar cancelar el future si está disponible
                        if thread_info.future and not thread_info.future.done():
                            thread_info.future.cancel()
                            logger.info(f"Future cancelado para thread muerto {thread_id}")
        
        # Limpiar threads muertos
        for dead_thread in dead_threads:
            self.unregister_thread(dead_thread.thread_id)
    
    def get_status(self) -> Dict:
        """
        Obtiene el estado actual del monitor de heartbeat.
        
        Returns:
            Dict: Estado detallado del monitor
        """
        with self.lock:
            now = datetime.now()
            return {
                'total_threads': len(self.threads),
                'active_threads': sum(1 for t in self.threads.values() if t.status == "active"),
                'threads_with_issues': sum(1 for t in self.threads.values() if t.missed_beats > 0),
                'monitor_running': self.monitor_thread and self.monitor_thread.is_alive(),
                'threads_detail': {
                    tid: {
                        'account_id': info.account_id,
                        'status': info.status,
                        'last_heartbeat': info.last_heartbeat.isoformat(),
                        'seconds_since_heartbeat': (now - info.last_heartbeat).total_seconds(),
                        'missed_beats': info.missed_beats
                    }
                    for tid, info in self.threads.items()
                }
            }


class RateLimiter:
    """
    Rate limiter para controlar la frecuencia de conexiones IMAP.
    
    Asegura que no se exceda la frecuencia permitida de conexiones
    por cuenta para respetar los límites de los servidores IMAP.
    """
    
    def __init__(self, requests_per_minute: int = 30):
        """
        Inicializa el rate limiter.
        
        Args:
            requests_per_minute (int): Máximo de requests por minuto por cuenta
        """
        self.requests_per_minute = requests_per_minute
        self.request_times: Dict[int, List[datetime]] = {}
        self.lock = threading.Lock()
    
    def wait_if_needed(self, account_id: int) -> None:
        """
        Aplica rate limiting para una cuenta específica.
        
        Args:
            account_id (int): ID de la cuenta de email
        """
        with self.lock:
            now = datetime.now()
            
            # Inicializar si es la primera vez
            if account_id not in self.request_times:
                self.request_times[account_id] = []
            
            # Limpiar requests antiguos (más de 1 minuto)
            cutoff_time = now - timedelta(minutes=1)
            self.request_times[account_id] = [
                req_time for req_time in self.request_times[account_id]
                if req_time > cutoff_time
            ]
            
            # Verificar si necesitamos esperar
            if len(self.request_times[account_id]) >= self.requests_per_minute:
                oldest_request = min(self.request_times[account_id])
                wait_time = 60 - (now - oldest_request).total_seconds()
                
                if wait_time > 0:
                    logger.warning(
                        f"Rate limit alcanzado para cuenta {account_id}. "
                        f"Esperando {wait_time:.1f} segundos"
                    )
                    time.sleep(wait_time)
            
            # Registrar este request
            self.request_times[account_id].append(now)


class InboxMonitor:
    """
    Servicio principal de monitoreo de buzones de email.
    
    Gestiona el monitoreo concurrente de múltiples cuentas de email,
    respetando límites de rate limiting y manejando errores de conexión.
    
    Nuevas funcionalidades:
    - Sistema de heartbeat para detectar threads muertos
    - Métricas de rendimiento en tiempo real 
    - Sistema de alertas críticas por Telegram
    - Sistema de fairness para evitar monopolización
    """
    
    def __init__(self, email_processor: Optional[Callable] = None,
                 config: Optional[MonitoringConfig] = None):
        """
        Inicializa el servicio de monitoreo.
        
        Args:
            email_processor (Callable, optional): Función para procesar emails nuevos
            config (MonitoringConfig, optional): Configuración personalizada
        """
        self.email_processor = email_processor
        self.config = config or MonitoringConfig()
        
        # Estado interno
        self.is_running = False
        self.shutdown_event = threading.Event()
        self.account_states: Dict[int, AccountMonitoringState] = {}
        self.rate_limiter = RateLimiter(requests_per_minute=30)
        
        # Thread pool para procesamiento concurrente
        self.executor: Optional[ThreadPoolExecutor] = None
        
        # Queue para emails pendientes de procesamiento
        self.email_queue = Queue()
        
        # Nuevos componentes
        self.alert_manager = AlertManager(self.config)
        self.heartbeat_monitor = HeartbeatMonitor(self.config.heartbeat_config, self.alert_manager)
        self.metrics = PerformanceMetrics()
        
        # Thread para métricas periódicas
        self.metrics_thread: Optional[threading.Thread] = None
        
        # Tracking de conexiones activas para graceful shutdown
        self.active_connections: Dict[str, object] = {}  # thread_id -> connection_object
        self.connections_lock = threading.Lock()
        
        # Sistema de fairness
        self.fairness_manager: Optional[FairnessManager] = None
        self.email_processor_service: Optional[EmailQueueProcessor] = None
        if self.config.enable_fairness:
            self.fairness_manager = FairnessManager(self.config.fairness_config)
            self.email_processor_service = EmailQueueProcessor(
                fairness_manager=self.fairness_manager,
                workflow_processor=self.email_processor,
                max_workers=self.config.max_workers
            )
            logger.info("⚖️ Sistema de fairness habilitado")
        
        # Configurar manejo de señales para shutdown graceful
        signal.signal(signal.SIGINT, self._signal_handler)
        signal.signal(signal.SIGTERM, self._signal_handler)
        
        logger.info("InboxMonitor inicializado con nuevas funcionalidades", extra={
            "max_workers": self.config.max_workers,
            "rate_limit_delay": self.config.rate_limit_delay,
            "check_interval": self.config.check_interval,
            "telegram_alerts_enabled": self.config.enable_telegram_alerts,
            "heartbeat_enabled": True,
            "fairness_enabled": self.config.enable_fairness
        })
        
        # Enviar alerta de inicio
        self.alert_manager.send_alert(
            level=AlertLevel.INFO,
            title="Servicio InboxMonitor Iniciado",
            message=f"InboxMonitor configurado con {self.config.max_workers} workers",
            alert_type="service_start"
        )
    
    def start_monitoring(self) -> None:
        """
        Inicia el monitoreo de todas las cuentas de email activas.
        
        Este método:
        1. Carga todas las cuentas de email activas desde la base de datos
        2. Crea un thread pool para monitorear múltiples cuentas concurrentemente
        3. Implementa rate limiting para respetar límites IMAP
        4. Inicia sistemas de heartbeat y métricas
        5. Inicia sistema de fairness si está habilitado
        6. Inicia procesador de cola si está habilitado
        7. Ejecuta el loop principal de monitoreo
        
        Raises:
            RuntimeError: Si el servicio ya está ejecutándose
            Exception: Si hay error al cargar las cuentas o inicializar el servicio
        """
        if self.is_running:
            raise RuntimeError("El servicio de monitoreo ya está ejecutándose")
        
        logger.info("🚀 Iniciando servicio de monitoreo de buzones")
        
        try:
            # Cargar cuentas de email activas
            active_accounts = self._load_active_email_accounts()
            logger.info(f"📧 Cargadas {len(active_accounts)} cuentas activas para monitoreo")
            
            if not active_accounts:
                logger.warning("⚠️ No se encontraron cuentas activas para monitorear")
                self.alert_manager.send_alert(
                    level=AlertLevel.WARNING,
                    title="No hay cuentas activas",
                    message="No se encontraron cuentas de email activas para monitorear",
                    alert_type="no_accounts"
                )
                return
            
            # Inicializar estados de monitoreo
            self._initialize_account_states(active_accounts)
            
            # Inicializar cuotas de fairness si está habilitado
            if self.fairness_manager:
                self._initialize_fairness_quotas(active_accounts)
                self.fairness_manager.start()
                
                # Iniciar procesador de cola
                if self.email_processor_service:
                    self.email_processor_service.start_processing()
                    logger.info("📧 Procesador de cola iniciado")
            
            # Crear thread pool
            self.executor = ThreadPoolExecutor(
                max_workers=self.config.max_workers,
                thread_name_prefix="inbox_monitor"
            )
            logger.info(f"🧵 Thread pool creado con {self.config.max_workers} workers")
            
            # Iniciar monitor de heartbeat
            self.heartbeat_monitor.start_monitoring()
            
            # Iniciar thread de métricas periódicas
            self._start_metrics_thread()
            
            # Marcar como ejecutándose
            self.is_running = True
            
            # Enviar alerta de inicio exitoso
            self.alert_manager.send_alert(
                level=AlertLevel.INFO,
                title="Monitoreo Iniciado Exitosamente",
                message=f"Monitoreando {len(active_accounts)} cuentas con {self.config.max_workers} workers",
                alert_type="monitoring_started"
            )
            
            # Iniciar loop principal de monitoreo
            self._run_monitoring_loop()
            
        except Exception as e:
            error_msg = f"Error iniciando servicio de monitoreo: {str(e)}"
            logger.error(error_msg, exc_info=True)
            
            # Enviar alerta crítica
            self.alert_manager.send_alert(
                level=AlertLevel.CRITICAL,
                title="Error Crítico al Iniciar Monitoreo",
                message=error_msg,
                alert_type="startup_error"
            )
            
            self._cleanup()
            raise
    
    def stop_monitoring(self) -> None:
        """
        Detiene el monitoreo de forma segura.
        
        Realiza un shutdown graceful, esperando a que terminen
        las tareas en progreso antes de cerrar.
        """
        if not self.is_running:
            logger.warning("⚠️ El servicio de monitoreo no está ejecutándose")
            return
        
        logger.info("🛑 Iniciando shutdown del servicio de monitoreo")
        
        # Señalizar shutdown
        self.shutdown_event.set()
        self.is_running = False
        
        # Detener monitor de heartbeat
        self.heartbeat_monitor.stop_monitoring()
        
        # Detener fairness manager si está activo
        if self.fairness_manager:
            self.fairness_manager.stop()
        
        # Detener procesador de cola si está activo
        if self.email_processor_service:
            self.email_processor_service.stop_processing()
        
        # Detener thread de métricas
        self._stop_metrics_thread()
        
        # Enviar alerta de parada
        self.alert_manager.send_alert(
            level=AlertLevel.INFO,
            title="Servicio de Monitoreo Detenido",
            message="El servicio de monitoreo se ha detenido correctamente",
            alert_type="service_stop"
        )
        
        # Cleanup
        self._cleanup()
        
        logger.info("✅ Servicio de monitoreo detenido correctamente")
    
    def _load_active_email_accounts(self) -> List[Dict]:
        """
        Carga todas las cuentas de email activas desde la base de datos.
        
        Returns:
            List[Dict]: Lista de información de cuentas activas
            
        Raises:
            RuntimeError: Si hay error accediendo a la base de datos
        """
        try:
            # Obtener todas las cuentas activas usando el DatabaseManager
            accounts_result = db_manager.get_all_active_email_accounts()
            
            if not accounts_result['success']:
                raise RuntimeError(f"Error obteniendo cuentas: {accounts_result.get('message', 'Error desconocido')}")
            
            accounts = accounts_result['accounts']
            logger.info(f"Cargadas {len(accounts)} cuentas activas desde la base de datos")
            
            # Log de cuentas cargadas (sin información sensible)
            for account in accounts:
                logger.debug(f"Cuenta cargada: {account['email']} (ID: {account['account_id']})")
            
            return accounts
                
        except Exception as e:
            logger.error(f"Error cargando cuentas activas: {str(e)}", exc_info=True)
            raise RuntimeError(f"No se pudieron cargar las cuentas activas: {str(e)}")
    
    def _initialize_account_states(self, accounts: List[Dict]) -> None:
        """
        Inicializa el estado de monitoreo para cada cuenta.
        
        Args:
            accounts (List[Dict]): Lista de información de cuentas a monitorear
        """
        self.account_states.clear()
        
        for account in accounts:
            state = AccountMonitoringState(
                account_id=account['account_id'],
                email=account['email'],
                last_check=None,
                consecutive_errors=0,
                last_error=None,
                is_active=True,
                retry_after=None
            )
            self.account_states[account['account_id']] = state
            
            logger.debug(f"Estado inicializado para cuenta {account['email']} (ID: {account['account_id']})")
    
    def _initialize_fairness_quotas(self, accounts: List[Dict]) -> None:
        """
        Inicializa las cuotas de fairness para las cuentas.
        
        Args:
            accounts (List[Dict]): Lista de información de cuentas
        """
        if not self.fairness_manager:
            return
        
        logger.info("⚖️ Inicializando cuotas de fairness")
        
        for account in accounts:
            # Establecer cuota inicial por defecto
            quota = AccountQuota(
                account_id=account['account_id'],
                max_emails_per_minute=self.config.fairness_config.default_max_emails_per_minute,
                max_concurrent_processing=self.config.fairness_config.default_max_concurrent,
                priority=AccountPriority.NORMAL
            )
            
            self.fairness_manager.set_account_quota(account['account_id'], quota)
            
            logger.debug(f"Cuota inicial establecida para cuenta {account['email']}", extra={
                "account_id": account['account_id'],
                "max_per_minute": quota.max_emails_per_minute
            })
    
    def _run_monitoring_loop(self) -> None:
        """
        Ejecuta el loop principal de monitoreo.
        
        Programa y ejecuta el monitoreo de cuentas de forma periódica,
        gestionando la concurrencia y los errores.
        """
        logger.info("Iniciando loop principal de monitoreo")
        
        while not self.shutdown_event.is_set():
            try:
                start_time = time.time()
                
                # Obtener cuentas que necesitan verificación
                accounts_to_check = self._get_accounts_ready_for_check()
                
                if accounts_to_check:
                    logger.info(f"Iniciando verificación de {len(accounts_to_check)} cuentas")
                    
                    # Procesar cuentas concurrentemente
                    self._process_accounts_concurrently(accounts_to_check)
                else:
                    logger.debug("No hay cuentas listas para verificación en este ciclo")
                
                # Calcular tiempo transcurrido y ajustar delay
                elapsed_time = time.time() - start_time
                sleep_time = max(0, self.config.check_interval - elapsed_time)
                
                if sleep_time > 0:
                    logger.debug(f"Esperando {sleep_time:.1f} segundos hasta el próximo ciclo")
                    if self.shutdown_event.wait(timeout=sleep_time):
                        break  # Shutdown solicitado
                
            except Exception as e:
                logger.error(f"Error en loop principal de monitoreo: {str(e)}", exc_info=True)
                # Esperar antes de reintentar en caso de error
                if not self.shutdown_event.wait(timeout=30):
                    continue
                else:
                    break
        
        logger.info("Loop principal de monitoreo terminado")
    
    def _get_accounts_ready_for_check(self) -> List[int]:
        """
        Obtiene las cuentas que están listas para verificación.
        
        Returns:
            List[int]: Lista de IDs de cuentas listas para verificar
        """
        ready_accounts = []
        now = datetime.now()
        
        for account_id, state in self.account_states.items():
            # Verificar si la cuenta está activa
            if not state.is_active:
                continue
            
            # Verificar si está en período de retry
            if state.retry_after and now < state.retry_after:
                continue
            
            # Verificar si necesita verificación (primera vez o intervalo cumplido)
            if (state.last_check is None or 
                (now - state.last_check).total_seconds() >= self.config.check_interval):
                ready_accounts.append(account_id)
        
        return ready_accounts
    
    def _process_accounts_concurrently(self, account_ids: List[int]) -> None:
        """
        Procesa múltiples cuentas de forma concurrente usando el thread pool.
        
        Args:
            account_ids (List[int]): Lista de IDs de cuentas a procesar
        """
        # Crear tareas futuras para cada cuenta
        future_to_account = {}
        future_to_thread_id = {}
        
        for account_id in account_ids:
            # Aplicar rate limiting antes de crear la tarea
            self.rate_limiter.wait_if_needed(account_id)
            
            # Crear ID único para el thread
            thread_id = f"account_{account_id}_{int(time.time())}"
            
            # Crear tarea en el thread pool
            future = self.executor.submit(self._monitor_single_account_with_heartbeat, account_id, thread_id)
            future_to_account[future] = account_id
            future_to_thread_id[future] = thread_id
            
            # Registrar thread en el monitor de heartbeat
            self.heartbeat_monitor.register_thread(thread_id, account_id, future)
        
        # Actualizar métricas de threads
        self.metrics.update_thread_metrics(len(future_to_account), self.config.max_workers)
        
        # Procesar resultados conforme van completándose
        completed_count = 0
        for future in as_completed(future_to_account, timeout=self.config.connection_timeout * 2):
            account_id = future_to_account[future]
            thread_id = future_to_thread_id[future]
            completed_count += 1
            
            try:
                result = future.result()
                self._handle_monitoring_result(account_id, result)
                
                # Registrar métricas de rendimiento
                if result.get('success', False):
                    processing_time_ms = result.get('processing_time', 0) * 1000
                    self.metrics.add_email_processed(processing_time_ms)
                    self.metrics.add_connection_attempt(True)
                else:
                    self.metrics.add_connection_attempt(False)
                
            except Exception as e:
                error_msg = f"Error procesando cuenta {account_id}: {str(e)}"
                logger.error(
                    error_msg, 
                    exc_info=True,
                    extra={"account_id": account_id, "thread_id": thread_id}
                )
                self._handle_monitoring_error(account_id, str(e))
                self.metrics.add_connection_attempt(False)
                
                # Enviar alerta si es un error crítico recurrente
                if account_id in self.account_states:
                    state = self.account_states[account_id]
                    if state.consecutive_errors >= 2:  # Después del segundo error
                        self.alert_manager.send_alert(
                            level=AlertLevel.ERROR,
                            title=f"Errores Recurrentes en Cuenta {account_id}",
                            message=f"La cuenta {state.email} ha fallado {state.consecutive_errors} veces consecutivas: {error_msg}",
                            alert_type=f"account_errors_{account_id}"
                        )
            finally:
                # Desregistrar thread del monitor de heartbeat
                self.heartbeat_monitor.unregister_thread(thread_id)
        
        # Actualizar métricas finales
        self.metrics.update_thread_metrics(0, self.config.max_workers)
    
    def _monitor_single_account_with_heartbeat(self, account_id: int, thread_id: str) -> Dict:
        """
        Wrapper para _monitor_single_account que incluye heartbeat y tracking de conexiones.
        
        Args:
            account_id (int): ID de la cuenta a monitorear
            thread_id (str): ID único del thread
            
        Returns:
            Dict: Resultado del monitoreo
        """
        try:
            # Enviar heartbeat inicial
            self.heartbeat_monitor.update_heartbeat(thread_id)
            
            # Ejecutar monitoreo normal con tracking de conexiones
            result = self._monitor_single_account(account_id, thread_id)
            
            # Enviar heartbeat final
            self.heartbeat_monitor.update_heartbeat(thread_id)
            
            return result
            
        except Exception as e:
            # Asegurar que el error se propaga pero también se registra el heartbeat
            self.heartbeat_monitor.update_heartbeat(thread_id)
            raise
    
    def _monitor_single_account(self, account_id: int, thread_id: str = None) -> Dict:
        """
        Monitorea una cuenta individual de email con registro de conexiones y fairness.
        
        Args:
            account_id (int): ID de la cuenta a monitorear
            thread_id (str, optional): ID único del thread para tracking de conexiones
            
        Returns:
            Dict: Resultado del monitoreo con estadísticas y emails encontrados
            
        Raises:
            Exception: Si hay error en la conexión o procesamiento
        """
        with CorrelationContext(correlation_id_value=f"monitor_{account_id}_{int(time.time())}"):
            logger.info(f"Iniciando monitoreo de cuenta {account_id}")
            
            start_time = time.time()
            result = {
                'account_id': account_id,
                'success': False,
                'emails_found': 0,
                'emails_processed': 0,
                'errors': [],
                'processing_time': 0,
                'timestamp': datetime.now()
            }
            
            email_tools = None
            
            try:
                # Obtener credenciales de la cuenta
                credentials_result = db_manager.get_email_account_credentials(account_id)
                if not credentials_result['success']:
                    raise RuntimeError(f"No se pudieron obtener credenciales: {credentials_result.get('message', 'Error desconocido')}")
                
                credentials = credentials_result['credentials']
                
                # Crear herramientas de email para esta cuenta
                email_tools = EmailToolsClass.create_email_tools_for_account(
                    account_config={
                        'email': credentials['email'],
                        'imap_server': credentials['imap_config']['server'],
                        'imap_port': credentials['imap_config']['port'],
                        'smtp_server': credentials['smtp_config']['server'],
                        'smtp_port': credentials['smtp_config']['port']
                    },
                    decrypted_password=credentials['password']
                )
                
                # Registrar conexión para graceful shutdown
                if thread_id and email_tools:
                    self._register_connection(thread_id, email_tools)
                
                # Buscar emails nuevos sin respuesta
                logger.debug(f"Buscando emails nuevos para cuenta {credentials['email']}")
                unanswered_emails = email_tools.fetch_unanswered_emails(
                    max_results=self.config.batch_size
                )
                
                result['emails_found'] = len(unanswered_emails)
                
                if unanswered_emails:
                    logger.info(f"Encontrados {len(unanswered_emails)} emails sin respuesta en cuenta {credentials['email']}")
                    
                    # Si fairness está habilitado, encolar emails
                    if self.fairness_manager:
                        for email_data in unanswered_emails:
                            email_id = email_data.get('id', f"email_{int(time.time() * 1000)}")
                            self.fairness_manager.enqueue_email(account_id, email_id, email_data)
                        
                        logger.info(f"⚖️ {len(unanswered_emails)} emails encolados con fairness para cuenta {account_id}")
                        result['emails_processed'] = len(unanswered_emails)
                    else:
                        # Procesar emails si hay un procesador configurado (modo legacy)
                        if self.email_processor:
                            processed_count = self._process_new_emails(
                                account_id, unanswered_emails, credentials
                            )
                            result['emails_processed'] = processed_count
                else:
                    logger.debug(f"No se encontraron emails nuevos en cuenta {credentials['email']}")
                
                result['success'] = True
                
            except Exception as e:
                logger.error(
                    f"Error monitoreando cuenta {account_id}: {str(e)}", 
                    exc_info=True,
                    extra={"account_id": account_id}
                )
                result['errors'].append(str(e))
                raise
            
            finally:
                # Cerrar conexión gracefully y desregistrar
                if email_tools:
                    try:
                        if hasattr(email_tools, 'close_connections'):
                            email_tools.close_connections()
                        elif hasattr(email_tools, 'close'):
                            email_tools.close()
                    except Exception as e:
                        logger.warning(f"Error cerrando conexión para cuenta {account_id}: {str(e)}")
                
                # Desregistrar conexión del tracking
                if thread_id:
                    self._unregister_connection(thread_id)
                
                result['processing_time'] = time.time() - start_time
                logger.debug(f"Monitoreo de cuenta {account_id} completado en {result['processing_time']:.2f}s")
            
            return result

    def monitor_single_inbox(self, email_account_id: int) -> Dict:
        """
        Monitorea un buzón específico de email con reintentos exponenciales.
        
        Este método:
        - Se conecta al buzón usando las credenciales
        - Busca emails nuevos desde la última verificación
        - Lanza el workflow de LangGraph para cada email nuevo
        - Maneja errores de conexión con reintentos exponenciales
        
        Args:
            email_account_id (int): ID de la cuenta de email a monitorear
            
        Returns:
            Dict: Resultado del monitoreo con estadísticas y detalles de procesamiento
            
        Raises:
            ValueError: Si el email_account_id es inválido
            RuntimeError: Si hay error crítico después de todos los reintentos
        """
        if not isinstance(email_account_id, int) or email_account_id <= 0:
            raise ValueError("El ID de la cuenta de email debe ser un entero positivo")
        
        with CorrelationContext(correlation_id_value=f"single_inbox_{email_account_id}_{int(time.time())}"):
            logger.info(f"🔍 Iniciando monitoreo de buzón para cuenta {email_account_id}")
            
            start_time = time.time()
            result = {
                'email_account_id': email_account_id,
                'success': False,
                'emails_found': 0,
                'emails_processed': 0,
                'emails_failed': 0,
                'connection_attempts': 0,
                'errors': [],
                'processing_time': 0,
                'timestamp': datetime.now(),
                'workflow_results': []
            }
            
            # Configuración de reintentos exponenciales
            max_retries = self.config.max_retries
            base_delay = self.config.retry_delay
            
            for attempt in range(max_retries + 1):  # +1 para incluir intento inicial
                try:
                    result['connection_attempts'] = attempt + 1
                    
                    if attempt > 0:
                        # Calcular delay exponencial: base_delay * (2 ^ (attempt - 1))
                        delay = min(base_delay * (2 ** (attempt - 1)), 300)  # Máximo 5 minutos
                        logger.info(f"🔄 Reintento {attempt}/{max_retries} para cuenta {email_account_id} en {delay}s")
                        time.sleep(delay)
                    
                    # Obtener credenciales de la cuenta
                    logger.debug(f"Obteniendo credenciales para cuenta {email_account_id}")
                    credentials_result = db_manager.get_email_account_credentials(email_account_id)
                    
                    if not credentials_result['success']:
                        raise RuntimeError(f"No se pudieron obtener credenciales: {credentials_result.get('message', 'Error desconocido')}")
                    
                    credentials = credentials_result['credentials']
                    account_email = credentials['email']
                    
                    # Crear herramientas de email para esta cuenta específica
                    logger.debug(f"Creando herramientas de email para {account_email}")
                    email_tools = EmailToolsClass.create_email_tools_for_account(
                        account_config={
                            'email': account_email,
                            'imap_server': credentials['imap_config']['server'],
                            'imap_port': credentials['imap_config']['port'],
                            'smtp_server': credentials['smtp_config']['server'],
                            'smtp_port': credentials['smtp_config']['port']
                        },
                        decrypted_password=credentials['password']
                    )
                    
                    # Buscar emails nuevos sin respuesta
                    logger.debug(f"🔍 Buscando emails nuevos para cuenta {account_email}")
                    unanswered_emails = email_tools.fetch_unanswered_emails(
                        max_results=self.config.batch_size
                    )
                    
                    result['emails_found'] = len(unanswered_emails)
                    
                    if not unanswered_emails:
                        logger.info(f"📭 No se encontraron emails nuevos en cuenta {account_email}")
                        result['success'] = True
                        break
                    
                    logger.info(f"📧 Encontrados {len(unanswered_emails)} emails sin respuesta en cuenta {account_email}")
                    
                    # Procesar cada email a través del workflow de LangGraph
                    emails_processed = 0
                    emails_failed = 0
                    
                    for email_data in unanswered_emails:
                        try:
                            # Añadir información de contexto al email
                            email_data['account_id'] = email_account_id
                            email_data['account_email'] = account_email
                            
                            # Ejecutar workflow de LangGraph para este email
                            workflow_result = self._execute_email_workflow(email_data)
                            
                            if workflow_result['success']:
                                emails_processed += 1
                                logger.debug(f"✅ Email procesado exitosamente: {email_data.get('subject', 'Sin asunto')}")
                            else:
                                emails_failed += 1
                                logger.warning(f"⚠️ Error procesando email: {workflow_result.get('error', 'Error desconocido')}")
                            
                            result['workflow_results'].append(workflow_result)
                            
                        except Exception as email_error:
                            emails_failed += 1
                            error_msg = f"Error procesando email individual: {str(email_error)}"
                            logger.error(error_msg, exc_info=True, extra={
                                "email_account_id": email_account_id,
                                "email_subject": email_data.get('subject', 'Sin asunto')
                            })
                            
                            result['workflow_results'].append({
                                'success': False,
                                'email_id': email_data.get('id', 'unknown'),
                                'error': error_msg
                            })
                    
                    result['emails_processed'] = emails_processed
                    result['emails_failed'] = emails_failed
                    result['success'] = True
                    
                    logger.info(f"✅ Monitoreo completado para cuenta {email_account_id}: "
                               f"{emails_processed} procesados, {emails_failed} fallidos")
                    break
                    
                except Exception as e:
                    error_msg = f"Error en intento {attempt + 1}: {str(e)}"
                    result['errors'].append(error_msg)
                    
                    logger.error(f"❌ {error_msg}", exc_info=True, extra={
                        "email_account_id": email_account_id,
                        "attempt": attempt + 1,
                        "max_retries": max_retries
                    })
                    
                    # Si es el último intento, lanzar la excepción
                    if attempt == max_retries:
                        logger.error(f"💥 Falló el monitoreo de cuenta {email_account_id} después de {max_retries + 1} intentos")
                        raise RuntimeError(f"Monitoreo falló después de {max_retries + 1} intentos: {error_msg}")
                    
                    # Continuar con el siguiente intento
                    continue
            
            # Calcular tiempo total de procesamiento
            result['processing_time'] = time.time() - start_time
            
            logger.info(f"🏁 Monitoreo de buzón completado para cuenta {email_account_id} en {result['processing_time']:.2f}s")
            return result

    def _execute_email_workflow(self, email_data: Dict) -> Dict:
        """
        Ejecuta el workflow de LangGraph para procesar un email individual.
        
        Args:
            email_data (Dict): Datos del email a procesar
            
        Returns:
            Dict: Resultado del procesamiento del workflow
        """
        workflow_result = {
            'success': False,
            'email_id': email_data.get('id', 'unknown'),
            'email_subject': email_data.get('subject', 'Sin asunto'),
            'processing_time': 0,
            'error': None,
            'workflow_output': None
        }
        
        start_time = time.time()
        
        try:
            # Importar el workflow de LangGraph
            from src.graph import Workflow
            from src.state import Email
            
            # Crear instancia del workflow
            workflow = Workflow()
            app = workflow.app
            
            # Configuración del workflow
            config = {'recursion_limit': 100}
            
            # Convertir email_data a objeto Email
            email_obj = Email(**email_data)
            
            # Preparar estado inicial con el email a procesar
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
                "email_account_id": email_data.get('account_id'),  # Importante para automatizaciones
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
            
            # Ejecutar el workflow
            logger.debug(f"🚀 Ejecutando workflow para email: {email_data.get('subject', 'Sin asunto')}")
            
            workflow_output = None
            for output in app.stream(initial_state, config):
                workflow_output = output
                # Log del progreso del workflow
                for key, value in output.items():
                    logger.debug(f"📋 Workflow step completed: {key}")
            
            workflow_result['success'] = True
            workflow_result['workflow_output'] = workflow_output
            
            logger.info(f"✅ Workflow completado exitosamente para email: {email_data.get('subject', 'Sin asunto')}")
            
        except Exception as e:
            error_msg = f"Error ejecutando workflow: {str(e)}"
            workflow_result['error'] = error_msg
            
            logger.error(error_msg, exc_info=True, extra={
                "email_id": email_data.get('id', 'unknown'),
                "email_subject": email_data.get('subject', 'Sin asunto')
            })
        
        finally:
            workflow_result['processing_time'] = time.time() - start_time
        
        return workflow_result
    
    def _process_new_emails(self, account_id: int, emails: List[Dict], 
                          credentials: Dict) -> int:
        """
        Procesa emails nuevos usando el procesador configurado.
        
        Args:
            account_id (int): ID de la cuenta
            emails (List[Dict]): Lista de emails a procesar
            credentials (Dict): Credenciales de la cuenta
            
        Returns:
            int: Número de emails procesados exitosamente
        """
        processed_count = 0
        
        for email_data in emails:
            try:
                if self.email_processor:
                    # Añadir información de contexto al email
                    email_data['account_id'] = account_id
                    email_data['account_email'] = credentials['email']
                    
                    # Procesar email (por ejemplo, a través de LangGraph)
                    self.email_processor(email_data)
                    processed_count += 1
                    
                    logger.debug(f"Email procesado: {email_data.get('subject', 'Sin asunto')}")
                    
                else:
                    logger.warning("No hay procesador de emails configurado, emails encontrados pero no procesados")
                    
            except Exception as e:
                logger.error(
                    f"Error procesando email individual: {str(e)}", 
                    exc_info=True,
                    extra={
                        "account_id": account_id,
                        "email_subject": email_data.get('subject', 'Sin asunto')
                    }
                )
        
        return processed_count
    
    def _handle_monitoring_result(self, account_id: int, result: Dict) -> None:
        """
        Maneja el resultado exitoso del monitoreo de una cuenta.
        
        Args:
            account_id (int): ID de la cuenta
            result (Dict): Resultado del monitoreo
        """
        if account_id not in self.account_states:
            return
        
        state = self.account_states[account_id]
        state.last_check = datetime.now()
        state.consecutive_errors = 0  # Reset contador de errores
        state.last_error = None
        state.retry_after = None
        
        logger.info(
            f"Monitoreo exitoso para cuenta {account_id}",
            extra={
                "account_id": account_id,
                "emails_found": result.get('emails_found', 0),
                "emails_processed": result.get('emails_processed', 0),
                "processing_time": result.get('processing_time', 0)
            }
        )
    
    def _handle_monitoring_error(self, account_id: int, error_message: str) -> None:
        """
        Maneja errores de monitoreo para una cuenta.
        
        Args:
            account_id (int): ID de la cuenta
            error_message (str): Mensaje de error
        """
        if account_id not in self.account_states:
            return
        
        state = self.account_states[account_id]
        state.consecutive_errors += 1
        state.last_error = error_message
        state.last_check = datetime.now()
        
        # Calcular delay de retry exponencial
        retry_delay = min(
            self.config.retry_delay * (2 ** (state.consecutive_errors - 1)),
            3600  # Máximo 1 hora
        )
        state.retry_after = datetime.now() + timedelta(seconds=retry_delay)
        
        # Desactivar cuenta si hay demasiados errores consecutivos
        if state.consecutive_errors >= self.config.max_retries:
            state.is_active = False
            logger.error(
                f"Cuenta {account_id} desactivada después de {state.consecutive_errors} errores consecutivos",
                extra={
                    "account_id": account_id,
                    "last_error": error_message,
                    "consecutive_errors": state.consecutive_errors
                }
            )
        else:
            logger.warning(
                f"Error en cuenta {account_id} (intento {state.consecutive_errors}/{self.config.max_retries}). "
                f"Retry en {retry_delay:.0f} segundos",
                extra={
                    "account_id": account_id,
                    "error": error_message,
                    "retry_after": state.retry_after.isoformat()
                }
            )
    
    def _signal_handler(self, signum, frame):
        """Maneja señales del sistema para shutdown graceful."""
        logger.info(f"Señal {signum} recibida, iniciando shutdown graceful")
        self.stop_monitoring()
    
    def _start_metrics_thread(self) -> None:
        """Inicia el thread para reportar métricas periódicamente."""
        if self.metrics_thread and self.metrics_thread.is_alive():
            logger.warning("Thread de métricas ya está ejecutándose")
            return
            
        self.metrics_thread = threading.Thread(
            target=self._metrics_loop,
            name="metrics_reporter",
            daemon=True
        )
        self.metrics_thread.start()
        logger.info("📊 Thread de métricas iniciado")
    
    def _stop_metrics_thread(self) -> None:
        """Detiene el thread de métricas."""
        if self.metrics_thread and self.metrics_thread.is_alive():
            # El thread se detendrá cuando shutdown_event esté set
            self.metrics_thread.join(timeout=5)
        logger.info("📊 Thread de métricas detenido")
    
    def _metrics_loop(self) -> None:
        """Loop principal para reportar métricas periódicamente."""
        metrics_interval = 300  # 5 minutos
        last_metrics_report = datetime.now()
        
        while not self.shutdown_event.wait(60):  # Verificar cada minuto
            try:
                now = datetime.now()
                
                # Reportar métricas cada 5 minutos
                if (now - last_metrics_report).total_seconds() >= metrics_interval:
                    self._report_metrics()
                    last_metrics_report = now
                
                # Resetear métricas si es necesario
                if (now - self.metrics.last_reset).total_seconds() >= (self.config.metrics_reset_interval_hours * 3600):
                    self._reset_metrics()
                
                # Verificar alertas basadas en métricas
                self._check_performance_alerts()
                
            except Exception as e:
                logger.error(f"Error en loop de métricas: {str(e)}", exc_info=True)
    
    def _report_metrics(self) -> None:
        """Reporta métricas de rendimiento al log y opcionalmente por Telegram."""
        summary = self.metrics.get_summary()
        heartbeat_status = self.heartbeat_monitor.get_status()
        
        metrics_msg = f"""
📊 **Reporte de Rendimiento**

**Emails Procesados:**
• Total: {summary['emails_processed_total']}
• Por minuto: {summary['emails_per_minute']}
• Por hora: {summary['throughput_per_hour']}

**Latencia:**
• Promedio: {summary['average_latency_ms']}ms
• Pico: {summary['peak_latency_ms']}ms

**Conexiones:**
• Tasa de éxito: {summary['connection_success_rate']}%

**Threads:**
• Utilización: {summary['thread_utilization']}%
• Activos: {heartbeat_status['active_threads']}/{heartbeat_status['total_threads']}

**Sistema:**
• Uptime: {summary['uptime_hours']}h
        """.strip()
        
        logger.info("📊 Reporte de métricas", extra=summary)
        
        # Enviar por Telegram si las métricas son significativas
        if summary['emails_processed_total'] > 0:
            self.alert_manager.send_alert(
                level=AlertLevel.INFO,
                title="Reporte de Rendimiento",
                message=metrics_msg,
                alert_type="metrics_report"
            )
    
    def _reset_metrics(self) -> None:
        """Resetea las métricas de rendimiento."""
        logger.info("🔄 Reseteando métricas de rendimiento")
        self.metrics = PerformanceMetrics()
        
        self.alert_manager.send_alert(
            level=AlertLevel.INFO,
            title="Métricas Reseteadas",
            message="Las métricas de rendimiento han sido reseteadas para un nuevo período",
            alert_type="metrics_reset"
        )
    
    def _check_performance_alerts(self) -> None:
        """Verifica si hay condiciones que requieren alertas de rendimiento."""
        summary = self.metrics.get_summary()
        
        # Alerta por alta latencia
        if summary['average_latency_ms'] > 10000:  # > 10 segundos
            self.alert_manager.send_alert(
                level=AlertLevel.WARNING,
                title="Alta Latencia Detectada",
                message=f"Latencia promedio: {summary['average_latency_ms']}ms (umbral: 10000ms)",
                alert_type="high_latency"
            )
        
        # Alerta por baja tasa de éxito
        if summary['connection_success_rate'] < 80 and summary['emails_processed_total'] > 10:
            self.alert_manager.send_alert(
                level=AlertLevel.WARNING,
                title="Baja Tasa de Éxito",
                message=f"Tasa de éxito: {summary['connection_success_rate']}% (umbral: 80%)",
                alert_type="low_success_rate"
            )
        
        # Alerta por alta utilización de threads
        if summary['thread_utilization'] > 90:
            self.alert_manager.send_alert(
                level=AlertLevel.WARNING,
                title="Alta Utilización de Threads",
                message=f"Utilización: {summary['thread_utilization']}% (umbral: 90%)",
                alert_type="high_thread_utilization"
            )
    
    def _register_connection(self, thread_id: str, connection_object: object) -> None:
        """
        Registra una conexión activa para tracking durante shutdown.
        
        Args:
            thread_id (str): ID único del thread
            connection_object (object): Objeto de conexión IMAP/SMTP
        """
        with self.connections_lock:
            self.active_connections[thread_id] = connection_object
            logger.debug(f"Conexión registrada para thread {thread_id}")
    
    def _unregister_connection(self, thread_id: str) -> None:
        """
        Desregistra una conexión del tracking.
        
        Args:
            thread_id (str): ID único del thread
        """
        with self.connections_lock:
            if thread_id in self.active_connections:
                del self.active_connections[thread_id]
                logger.debug(f"Conexión desregistrada para thread {thread_id}")
    
    def _close_active_connections(self) -> None:
        """
        Cierra todas las conexiones activas de forma graceful.
        
        Itera sobre todas las conexiones registradas e intenta cerrarlas
        adecuadamente para evitar conexiones colgadas.
        """
        logger.info("🔌 Cerrando conexiones activas...")
        
        with self.connections_lock:
            connections_to_close = list(self.active_connections.items())
        
        if not connections_to_close:
            logger.info("No hay conexiones activas para cerrar")
            return
        
        closed_count = 0
        error_count = 0
        
        for thread_id, connection_obj in connections_to_close:
            try:
                # Intentar cerrar la conexión si tiene método close
                if hasattr(connection_obj, 'close'):
                    connection_obj.close()
                    closed_count += 1
                    logger.debug(f"Conexión cerrada para thread {thread_id}")
                elif hasattr(connection_obj, 'logout'):
                    # Para conexiones IMAP que usan logout
                    connection_obj.logout()
                    closed_count += 1
                    logger.debug(f"Conexión IMAP cerrada para thread {thread_id}")
                elif hasattr(connection_obj, 'quit'):
                    # Para conexiones SMTP que usan quit
                    connection_obj.quit()
                    closed_count += 1
                    logger.debug(f"Conexión SMTP cerrada para thread {thread_id}")
                else:
                    logger.warning(f"Conexión {thread_id} no tiene método de cierre conocido")
                    
            except Exception as e:
                error_count += 1
                logger.warning(f"Error cerrando conexión {thread_id}: {str(e)}")
        
        # Limpiar el registro de conexiones
        with self.connections_lock:
            self.active_connections.clear()
        
        logger.info(f"🔌 Conexiones cerradas: {closed_count}, errores: {error_count}")
    
    def _wait_for_active_tasks(self, timeout_seconds: int = 30) -> bool:
        """
        Espera a que terminen las tareas activas con timeout.
        
        Args:
            timeout_seconds (int): Tiempo máximo a esperar
            
        Returns:
            bool: True si todas las tareas terminaron, False si timeout
        """
        logger.info(f"⏳ Esperando finalización de tareas activas (timeout: {timeout_seconds}s)...")
        
        start_time = time.time()
        
        while time.time() - start_time < timeout_seconds:
            # Verificar si hay threads activos en el heartbeat monitor
            heartbeat_status = self.heartbeat_monitor.get_status()
            active_threads = heartbeat_status.get('active_threads', 0)
            
            # Verificar si hay conexiones activas
            with self.connections_lock:
                active_connections = len(self.active_connections)
            
            if active_threads == 0 and active_connections == 0:
                logger.info("✅ Todas las tareas han terminado")
                return True
            
            logger.debug(f"Threads activos: {active_threads}, conexiones activas: {active_connections}")
            time.sleep(1)
        
        logger.warning(f"⚠️ Timeout esperando finalización de tareas")
        return False
    
    def _cleanup(self) -> None:
        """
        Limpia recursos y cierra conexiones de forma graceful.
        
        Implementa un shutdown graceful que:
        1. Espera a que terminen las tareas activas (con timeout)
        2. Cierra todas las conexiones IMAP/SMTP registradas
        3. Cierra el thread pool
        4. Limpia recursos restantes
        """
        logger.info("🧹 Iniciando graceful shutdown...")
        
        # Paso 1: Esperar a que terminen las tareas activas
        tasks_finished = self._wait_for_active_tasks(timeout_seconds=self.config.shutdown_timeout_seconds)
        
        if not tasks_finished:
            logger.warning("⚠️ Algunas tareas no terminaron en el tiempo esperado, forzando cierre...")
        
        # Paso 2: Cerrar conexiones activas
        self._close_active_connections()
        
        # Paso 3: Cerrar thread pool con timeout
        if self.executor:
            logger.info("🧵 Cerrando thread pool...")
            try:
                # Intentar shutdown graceful con timeout
                self.executor.shutdown(wait=True, timeout=self.config.thread_pool_shutdown_timeout)
                logger.info("✅ Thread pool cerrado gracefully")
            except Exception as e:
                logger.warning(f"⚠️ Error en shutdown del thread pool: {str(e)}")
                # Forzar cancelación de tareas pendientes
                try:
                    self.executor._threads.clear()
                    concurrent.futures.thread._threads_queues.clear()
                except:
                    pass
            finally:
                self.executor = None
        
        # Paso 4: Limpiar queue de emails pendientes
        logger.debug("📧 Limpiando queue de emails pendientes...")
        emails_cleared = 0
        while not self.email_queue.empty():
            try:
                self.email_queue.get_nowait()
                emails_cleared += 1
            except Empty:
                break
        
        if emails_cleared > 0:
            logger.info(f"📧 {emails_cleared} emails pendientes eliminados del queue")
        
        # Paso 5: Enviar alerta final de shutdown
        try:
            self.alert_manager.send_alert(
                level=AlertLevel.INFO,
                title="Graceful Shutdown Completado",
                message="El servicio de monitoreo se ha detenido correctamente con cierre graceful de todas las conexiones",
                alert_type="graceful_shutdown"
            )
        except:
            # No fallar el shutdown por error en alertas
            pass
        
        logger.info("✅ Graceful shutdown completado")
    
    def get_monitoring_status(self) -> Dict:
        """
        Obtiene el estado actual del monitoreo.
        
        Returns:
            Dict: Estado detallado del monitoreo con estadísticas, métricas, heartbeat y fairness
        """
        metrics_summary = self.metrics.get_summary()
        heartbeat_status = self.heartbeat_monitor.get_status()
        
        status = {
            'service_info': {
                'is_running': self.is_running,
                'uptime_hours': metrics_summary.get('uptime_hours', 0),
                'version': '2.1.0',  # Versión con fairness
                'features_enabled': {
                    'heartbeat_monitoring': True,
                    'performance_metrics': True,
                    'telegram_alerts': self.config.enable_telegram_alerts,
                    'fairness_system': self.config.enable_fairness
                }
            },
            'accounts': {
                'total_accounts': len(self.account_states),
                'active_accounts': sum(1 for state in self.account_states.values() if state.is_active),
                'accounts_with_errors': sum(1 for state in self.account_states.values() if state.consecutive_errors > 0),
                'account_states': {
                    account_id: {
                        'email': state.email,
                        'last_check': state.last_check.isoformat() if state.last_check else None,
                        'consecutive_errors': state.consecutive_errors,
                        'is_active': state.is_active,
                        'retry_after': state.retry_after.isoformat() if state.retry_after else None
                    }
                    for account_id, state in self.account_states.items()
                }
            },
            'threading': {
                'thread_pool_active': self.executor is not None,
                'max_workers': self.config.max_workers if self.executor else 0,
                'current_utilization': metrics_summary.get('thread_utilization', 0),
                'heartbeat_monitor': heartbeat_status
            },
            'connections': {
                'active_connections': len(self.active_connections),
                'connection_details': list(self.active_connections.keys()) if len(self.active_connections) < 10 else f"{len(self.active_connections)} conexiones activas"
            },
            'performance_metrics': metrics_summary,
            'alert_system': {
                'telegram_enabled': self.config.enable_telegram_alerts,
                'telegram_configured': bool(self.config.telegram_bot_token and self.config.telegram_chat_id),
                'cooldown_minutes': self.config.alert_cooldown_minutes,
                'last_alerts': {
                    alert_type: timestamp.isoformat() 
                    for alert_type, timestamp in self.alert_manager.last_alerts.items()
                }
            },
            'configuration': {
                'max_workers': self.config.max_workers,
                'rate_limit_delay': self.config.rate_limit_delay,
                'check_interval': self.config.check_interval,
                'batch_size': self.config.batch_size,
                'max_retries': self.config.max_retries,
                'heartbeat_interval': self.config.heartbeat_config.interval_seconds,
                'heartbeat_timeout': self.config.heartbeat_config.timeout_seconds,
                'metrics_reset_interval_hours': self.config.metrics_reset_interval_hours
            },
            'health_status': self._get_health_status()
        }
        
        # Añadir métricas de fairness si está habilitado
        if self.fairness_manager:
            status['fairness_metrics'] = self.fairness_manager.get_fairness_metrics()
        
        # Añadir métricas del procesador de cola si está activo
        if self.email_processor_service:
            status['queue_processor_metrics'] = self.email_processor_service.get_metrics()
        
        return status
    
    def _get_health_status(self) -> str:
        """
        Determina el estado general de salud del servicio.
        
        Returns:
            str: Estado de salud ('healthy', 'warning', 'critical')
        """
        if not self.is_running:
            return 'stopped'
        
        metrics = self.metrics.get_summary()
        heartbeat = self.heartbeat_monitor.get_status()
        
        # Verificar condiciones críticas
        if heartbeat['threads_with_issues'] > 0:
            return 'critical'
        
        if metrics['connection_success_rate'] < 50 and metrics['emails_processed_total'] > 5:
            return 'critical'
        
        # Verificar condiciones de advertencia
        active_accounts = sum(1 for state in self.account_states.values() if state.is_active)
        error_accounts = sum(1 for state in self.account_states.values() if state.consecutive_errors > 0)
        
        if error_accounts > (active_accounts * 0.3):  # Más del 30% con errores
            return 'warning'
        
        if metrics['thread_utilization'] > 85:
            return 'warning'
        
        if metrics['average_latency_ms'] > 5000:  # > 5 segundos
            return 'warning'
        
        return 'healthy' 