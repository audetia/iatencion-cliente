# InboxMonitor Service

El servicio InboxMonitor proporciona funcionalidad para monitorear buzones de email de forma continua o individual, procesando emails nuevos a través del workflow de LangGraph.

## Características Principales

### 1. Monitoreo Individual de Buzones

El método `monitor_single_inbox(email_account_id)` permite monitorear un buzón específico con las siguientes características:

- **Reintentos exponenciales**: Maneja errores de conexión con backoff exponencial
- **Integración con LangGraph**: Ejecuta el workflow completo para cada email
- **Rate limiting**: Respeta límites de conexión IMAP
- **Logging detallado**: Seguimiento completo con correlation IDs
- **Estadísticas detalladas**: Retorna métricas de procesamiento

### 2. Monitoreo Continuo

El servicio también soporta monitoreo continuo de múltiples cuentas con:

- **Procesamiento concurrente**: Thread pool para múltiples cuentas
- **Gestión de estado**: Tracking de errores y reintentos por cuenta
- **Shutdown graceful**: Manejo de señales para detener el servicio

### 3. Nuevas Funcionalidades v2.0

- **Sistema de heartbeat**: Detecta threads muertos automáticamente
- **Métricas de rendimiento**: Emails/minuto, latencia, tasa de éxito
- **Alertas por Telegram**: Notificaciones automáticas de errores críticos
