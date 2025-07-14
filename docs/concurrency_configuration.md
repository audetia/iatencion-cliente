# Configuración de Concurrencia y Límites - InboxMonitor

## Índice

1. [Configuración General](#configuración-general)
2. [Thread Pool y Concurrencia](#thread-pool-y-concurrencia)
3. [Rate Limiting](#rate-limiting)
4. [Timeouts y Reintentos](#timeouts-y-reintentos)
5. [Sistema de Heartbeat](#sistema-de-heartbeat)
6. [Métricas y Monitoreo](#métricas-y-monitoreo)
7. [Sistema de Alertas](#sistema-de-alertas)
8. [Graceful Shutdown](#graceful-shutdown)
9. [Ejemplos de Configuración](#ejemplos-de-configuración)

## Configuración General

La clase `MonitoringConfig` centraliza toda la configuración del sistema InboxMonitor:

```python
@dataclass
class MonitoringConfig:
    # Concurrencia
    max_workers: int = 5
    rate_limit_delay: float = 2.0
    batch_size: int = 10
    check_interval: int = 300

    # Conexiones
    connection_timeout: int = 30
    max_retries: int = 3
    retry_delay: float = 60.0

    # Alertas
    enable_telegram_alerts: bool = True
    alert_cooldown_minutes: int = 15

    # Heartbeat y métricas
    heartbeat_config: HeartbeatConfig = field(default_factory=HeartbeatConfig)
    metrics_reset_interval_hours: int = 24

    # Graceful shutdown
    shutdown_timeout_seconds: int = 30
    thread_pool_shutdown_timeout: int = 15
```

## Thread Pool y Concurrencia

### Configuración de Workers

**max_workers**: Número máximo de threads concurrentes

- **Valor por defecto**: 5
- **Rango recomendado**: 3-10
- **Consideraciones**:
  - Más workers = mayor throughput pero mayor uso de recursos
  - Servidores IMAP tienen límites de conexiones concurrentes
  - Considerar la capacidad del servidor y red

```python
# Configuración conservadora (servidores lentos)
config = MonitoringConfig(max_workers=3)

# Configuración agresiva (servidores rápidos)
config = MonitoringConfig(max_workers=10)
```

### Utilización de Threads

El sistema monitorea la utilización de threads:

- **Alerta de advertencia**: >90% de utilización
- **Métrica**: `thread_utilization` en porcentaje
- **Cálculo**: `(threads_activos / max_workers) * 100`

### Thread Pool Shutdown

**thread_pool_shutdown_timeout**: Tiempo máximo para cerrar el thread pool

- **Valor por defecto**: 15 segundos
- **Propósito**: Evitar threads colgados durante shutdown

## Rate Limiting

### Configuración de Rate Limiting

**rate_limit_delay**: Delay entre conexiones IMAP por cuenta

- **Valor por defecto**: 2.0 segundos
- **Propósito**: Respetar límites de servidores IMAP
- **Cálculo**: Requests por minuto = 60 / rate_limit_delay

```python
# Configuración por tipo de servidor
gmail_config = MonitoringConfig(rate_limit_delay=1.0)      # 60 req/min
outlook_config = MonitoringConfig(rate_limit_delay=2.0)    # 30 req/min
exchange_config = MonitoringConfig(rate_limit_delay=3.0)   # 20 req/min
```

### Rate Limiter Interno

La clase `RateLimiter` controla:

- **requests_per_minute**: 30 por defecto
- **Ventana deslizante**: 1 minuto
- **Por cuenta**: Cada cuenta tiene su propio límite

## Timeouts y Reintentos

### Configuración de Timeouts

**connection_timeout**: Timeout para conexiones IMAP

- **Valor por defecto**: 30 segundos
- **Aplicación**: Conexiones IMAP/SMTP individuales

**check_interval**: Intervalo entre verificaciones de buzones

- **Valor por defecto**: 300 segundos (5 minutos)
- **Recomendación**: No menos de 60 segundos

### Sistema de Reintentos

**max_retries**: Máximo de reintentos por cuenta

- **Valor por defecto**: 3
- **Comportamiento**: Reintentos exponenciales

**retry_delay**: Delay base entre reintentos

- **Valor por defecto**: 60.0 segundos
- **Fórmula**: `delay = min(retry_delay * (2 ** (attempt - 1)), 3600)`

```python
# Ejemplo de delays de reintento
# Intento 1: 60s
# Intento 2: 120s
# Intento 3: 240s
# Intento 4: 480s (máximo 3600s)
```

### Batch Processing

**batch_size**: Máximo de emails por lote

- **Valor por defecto**: 10
- **Propósito**: Limitar memoria y tiempo de procesamiento
- **Recomendación**: 5-20 según capacidad del servidor

## Sistema de Heartbeat

### Configuración de Heartbeat

```python
@dataclass
class HeartbeatConfig:
    interval_seconds: int = 30      # Intervalo entre heartbeats
    timeout_seconds: int = 120      # Timeout para thread muerto
    max_missed_beats: int = 3       # Máximo heartbeats perdidos
```

### Parámetros Detallados

**interval_seconds**: Frecuencia de verificación de threads

- **Valor por defecto**: 30 segundos
- **Rango recomendado**: 15-60 segundos
- **Consideraciones**: Menor intervalo = detección más rápida pero más overhead

**timeout_seconds**: Tiempo sin heartbeat para considerar thread muerto

- **Valor por defecto**: 120 segundos
- **Recomendación**: 2-4 veces el interval_seconds
- **Cálculo**: Debe permitir operaciones IMAP lentas

**max_missed_beats**: Heartbeats perdidos antes de alerta crítica

- **Valor por defecto**: 3
- **Comportamiento**: Alerta crítica + cancelación de Future

### Estados de Thread

El sistema rastrea:

- **active**: Thread funcionando normalmente
- **dead**: Thread no responde, se envía alerta crítica
- **missed_beats**: Contador de heartbeats perdidos

## Métricas y Monitoreo

### Configuración de Métricas

**metrics_reset_interval_hours**: Intervalo para resetear métricas

- **Valor por defecto**: 24 horas
- **Propósito**: Evitar overflow y mantener datos relevantes

### Métricas Recopiladas

**Rendimiento**:

- `emails_per_minute`: Emails procesados por minuto
- `average_latency_ms`: Latencia promedio en milisegundos
- `peak_latency_ms`: Latencia máxima registrada
- `throughput_per_hour`: Emails por hora

**Conexiones**:

- `connection_success_rate`: Porcentaje de conexiones exitosas
- `successful_connections`: Contador de conexiones exitosas
- `failed_connections`: Contador de conexiones fallidas

**Threads**:

- `thread_utilization`: Porcentaje de utilización del thread pool
- `active_threads`: Número de threads activos

### Ventanas Deslizantes

**latency_window**: Últimas 100 mediciones de latencia
**emails_window**: Últimos 60 minutos de actividad

## Sistema de Alertas

### Configuración de Alertas

**enable_telegram_alerts**: Habilitar alertas por Telegram

- **Valor por defecto**: True
- **Variables de entorno**: `TG_BOT_TOKEN_STATUS`, `TG_CHAT_ID_STATUS`

**alert_cooldown_minutes**: Cooldown entre alertas del mismo tipo

- **Valor por defecto**: 15 minutos
- **Propósito**: Evitar spam de alertas

### Niveles de Alerta

**INFO**: Eventos informativos

- Inicio/parada del servicio
- Reportes de métricas
- Reset de métricas

**WARNING**: Situaciones que requieren atención

- Alta latencia (>10 segundos)
- Baja tasa de éxito (<80%)
- Alta utilización de threads (>90%)

**ERROR**: Errores que afectan el funcionamiento

- Errores recurrentes en cuentas
- Fallos de conexión repetidos

**CRITICAL**: Situaciones críticas

- Threads muertos detectados
- Errores de startup
- Fallos del sistema

### Umbrales de Alerta

```python
# Configuración de umbrales
ALERT_THRESHOLDS = {
    'high_latency_ms': 10000,           # 10 segundos
    'low_success_rate': 80,             # 80%
    'high_thread_utilization': 90,      # 90%
    'max_consecutive_errors': 3,        # 3 errores
    'heartbeat_max_missed': 3           # 3 heartbeats
}
```

## Graceful Shutdown

### Configuración de Shutdown

**shutdown_timeout_seconds**: Tiempo máximo para esperar tareas activas

- **Valor por defecto**: 30 segundos
- **Comportamiento**: Espera a que terminen tareas en progreso

**thread_pool_shutdown_timeout**: Timeout específico para thread pool

- **Valor por defecto**: 15 segundos
- **Propósito**: Evitar bloqueo indefinido

### Proceso de Shutdown

1. **Esperar tareas activas** (shutdown_timeout_seconds)
2. **Cerrar conexiones IMAP/SMTP** registradas
3. **Cerrar thread pool** (thread_pool_shutdown_timeout)
4. **Limpiar queue** de emails pendientes
5. **Enviar alerta final** de shutdown completado

## Ejemplos de Configuración

### Configuración para Desarrollo

```python
dev_config = MonitoringConfig(
    max_workers=2,
    rate_limit_delay=1.0,
    batch_size=5,
    check_interval=60,
    connection_timeout=15,
    max_retries=2,
    retry_delay=30.0,
    enable_telegram_alerts=False,
    heartbeat_config=HeartbeatConfig(
        interval_seconds=15,
        timeout_seconds=60,
        max_missed_beats=2
    ),
    metrics_reset_interval_hours=1,
    shutdown_timeout_seconds=15
)
```

### Configuración para Producción

```python
prod_config = MonitoringConfig(
    max_workers=8,
    rate_limit_delay=2.0,
    batch_size=15,
    check_interval=300,
    connection_timeout=45,
    max_retries=5,
    retry_delay=120.0,
    enable_telegram_alerts=True,
    telegram_bot_token=os.getenv("TG_BOT_TOKEN_STATUS"),
    telegram_chat_id=os.getenv("TG_CHAT_ID_STATUS"),
    alert_cooldown_minutes=30,
    heartbeat_config=HeartbeatConfig(
        interval_seconds=30,
        timeout_seconds=180,
        max_missed_beats=3
    ),
    metrics_reset_interval_hours=24,
    shutdown_timeout_seconds=60,
    thread_pool_shutdown_timeout=30
)
```

### Configuración para Servidores Lentos

```python
slow_server_config = MonitoringConfig(
    max_workers=3,
    rate_limit_delay=5.0,
    batch_size=5,
    check_interval=600,
    connection_timeout=60,
    max_retries=3,
    retry_delay=180.0,
    heartbeat_config=HeartbeatConfig(
        interval_seconds=60,
        timeout_seconds=300,
        max_missed_beats=2
    )
)
```

### Configuración para Alto Volumen

```python
high_volume_config = MonitoringConfig(
    max_workers=12,
    rate_limit_delay=1.0,
    batch_size=25,
    check_interval=120,
    connection_timeout=30,
    max_retries=3,
    retry_delay=60.0,
    heartbeat_config=HeartbeatConfig(
        interval_seconds=20,
        timeout_seconds=90,
        max_missed_beats=3
    ),
    metrics_reset_interval_hours=12
)
```

## Monitoreo y Optimización

### Métricas Clave para Optimización

1. **thread_utilization**: Si >85% consistentemente, aumentar max_workers
2. **average_latency_ms**: Si >5000ms, revisar connection_timeout y batch_size
3. **connection_success_rate**: Si <90%, ajustar retry_delay y max_retries
4. **emails_per_minute**: Benchmark de throughput del sistema

### Señales de Alerta

**Necesitas más workers**:

- thread_utilization >90% frecuentemente
- Queue de emails creciendo
- Latencia aumentando

**Necesitas menos workers**:

- thread_utilization <30% consistentemente
- Muchas conexiones fallidas
- Alertas de rate limiting

**Problemas de red/servidor**:

- connection_success_rate <80%
- average_latency_ms >10000
- Muchos threads muertos

### Recomendaciones de Tuning

1. **Empezar conservador**: max_workers=3, rate_limit_delay=3.0
2. **Monitorear métricas** durante 24 horas
3. **Ajustar gradualmente**: Incrementar workers de 1 en 1
4. **Validar alertas**: Asegurar que no hay threads muertos
5. **Optimizar por tipo de servidor**: Gmail vs Exchange vs otros

## Variables de Entorno

```bash
# Alertas Telegram
TG_BOT_TOKEN_STATUS=your_bot_token_here
TG_CHAT_ID_STATUS=your_chat_id_here

# Configuración opcional
INBOX_MONITOR_MAX_WORKERS=5
INBOX_MONITOR_RATE_LIMIT_DELAY=2.0
INBOX_MONITOR_BATCH_SIZE=10
INBOX_MONITOR_CHECK_INTERVAL=300
```

## Troubleshooting

### Problemas Comunes

**Threads muertos frecuentes**:

- Aumentar heartbeat timeout_seconds
- Reducir max_workers
- Verificar estabilidad de red

**Baja tasa de éxito**:

- Aumentar connection_timeout
- Aumentar retry_delay
- Verificar credenciales de cuentas

**Alta latencia**:

- Reducir batch_size
- Aumentar connection_timeout
- Verificar capacidad del servidor IMAP

**Alertas de spam**:

- Aumentar alert_cooldown_minutes
- Ajustar umbrales de alerta
- Verificar configuración de Telegram
