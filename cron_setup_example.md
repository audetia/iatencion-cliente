# Configuración de Monitoreo Automático de Cuentas de Email

Este documento explica cómo configurar el monitoreo automático de cuentas de email usando el `EmailMonitoringService`.

## Arquitectura Refactorizada

### Antes (Problemas):

- ❌ El modelo `EmailAccount` tenía lógica de conexión IMAP/SMTP
- ❌ Violación del principio Single Responsibility
- ❌ Duplicación de código con `EmailTools`
- ❌ Difícil de testear y mantener

### Después (Solución):

- ✅ **Modelo EmailAccount**: Solo datos y validaciones básicas
- ✅ **EmailTools**: Toda la lógica de conexión centralizada
- ✅ **EmailMonitoringService**: Servicio dedicado para monitoreo
- ✅ **Script de monitoreo**: Ejecución periódica automatizada

## Uso del Servicio de Monitoreo

### 1. Monitoreo Manual

```python
from src.database import DatabaseManager
from src.services.email_monitoring_service import EmailMonitoringService

# Inicializar
db_manager = DatabaseManager()
monitoring_service = EmailMonitoringService(db_manager.get_db_session)

# Generar reporte
report = monitoring_service.get_monitoring_report()
print(f"Cuentas activas: {report['active_accounts']}")

# Monitorear todas las cuentas
stats = monitoring_service.monitor_all_accounts(hours_threshold=24)
print(f"Verificadas: {stats['total_checked']}")

# Probar una cuenta específica
result = monitoring_service.test_account_connection(
    account_id=1,
    decrypted_password="password123"
)
print(f"Conexión exitosa: {result['success']}")
```

### 2. Script de Línea de Comandos

```bash
# Monitoreo completo
python src/scripts/monitor_email_accounts.py

# Solo reporte
python src/scripts/monitor_email_accounts.py --report-only

# Con logging detallado
python src/scripts/monitor_email_accounts.py --verbose

# Threshold personalizado (48 horas)
python src/scripts/monitor_email_accounts.py --hours-threshold 48
```

## Configuración de Cron Jobs

### Linux/macOS

Agregar al crontab (`crontab -e`):

```bash
# Monitoreo cada 6 horas
0 */6 * * * cd /path/to/project && python src/scripts/monitor_email_accounts.py >> logs/cron_monitoring.log 2>&1

# Reporte diario a las 9 AM
0 9 * * * cd /path/to/project && python src/scripts/monitor_email_accounts.py --report-only >> logs/daily_reports.log 2>&1

# Monitoreo con threshold de 12 horas cada 4 horas
0 */4 * * * cd /path/to/project && python src/scripts/monitor_email_accounts.py --hours-threshold 12 >> logs/frequent_monitoring.log 2>&1
```

### Windows (Task Scheduler)

1. Abrir Task Scheduler
2. Crear tarea básica
3. Configurar trigger (cada 6 horas)
4. Acción: Iniciar programa
   - Programa: `python.exe`
   - Argumentos: `src/scripts/monitor_email_accounts.py`
   - Directorio: `C:\path\to\project`

### Docker/Kubernetes

```yaml
# kubernetes-cronjob.yaml
apiVersion: batch/v1
kind: CronJob
metadata:
  name: email-monitoring
spec:
  schedule: "0 */6 * * *" # Cada 6 horas
  jobTemplate:
    spec:
      template:
        spec:
          containers:
            - name: email-monitor
              image: your-app:latest
              command: ["python", "src/scripts/monitor_email_accounts.py"]
          restartPolicy: OnFailure
```

## Integración con Aplicación Web

### Flask/FastAPI Endpoint

```python
from flask import Flask, jsonify
from src.services.email_monitoring_service import EmailMonitoringService

app = Flask(__name__)

@app.route('/api/monitoring/report')
def get_monitoring_report():
    monitoring_service = EmailMonitoringService(db_manager.get_db_session)
    report = monitoring_service.get_monitoring_report()
    return jsonify(report)

@app.route('/api/monitoring/run')
def run_monitoring():
    monitoring_service = EmailMonitoringService(db_manager.get_db_session)
    stats = monitoring_service.monitor_all_accounts()
    return jsonify(stats)

@app.route('/api/accounts/<int:account_id>/test', methods=['POST'])
def test_account_connection(account_id):
    data = request.get_json()
    decrypted_password = data.get('password')

    monitoring_service = EmailMonitoringService(db_manager.get_db_session)
    result = monitoring_service.test_account_connection(account_id, decrypted_password)

    return jsonify(result)
```

## Logging y Monitoreo

### Configuración de Logs

```python
# logging_config.py
import logging.config

LOGGING_CONFIG = {
    'version': 1,
    'disable_existing_loggers': False,
    'formatters': {
        'detailed': {
            'format': '%(asctime)s - %(name)s - %(levelname)s - %(message)s'
        },
    },
    'handlers': {
        'file': {
            'class': 'logging.handlers.RotatingFileHandler',
            'filename': 'logs/email_monitoring.log',
            'maxBytes': 10485760,  # 10MB
            'backupCount': 5,
            'formatter': 'detailed',
        },
        'console': {
            'class': 'logging.StreamHandler',
            'formatter': 'detailed',
        },
    },
    'loggers': {
        'src.services.email_monitoring_service': {
            'handlers': ['file', 'console'],
            'level': 'INFO',
            'propagate': False,
        },
    },
}

logging.config.dictConfig(LOGGING_CONFIG)
```

### Métricas y Alertas

```python
# metrics_example.py
def send_alert_if_needed(stats):
    """Envía alertas si hay demasiados errores."""
    error_threshold = 0.2  # 20% de cuentas con error

    if stats['total_checked'] > 0:
        error_rate = stats['errors'] / stats['total_checked']

        if error_rate > error_threshold:
            send_slack_alert(f"🚨 {error_rate:.1%} de cuentas con errores")
            send_email_alert(f"Alto número de errores en monitoreo: {stats}")

def send_slack_alert(message):
    # Implementar integración con Slack
    pass

def send_email_alert(stats):
    # Enviar email de alerta al administrador
    pass
```

## Beneficios de la Refactorización

1. **Separación de Responsabilidades**: Cada clase tiene una función específica
2. **Reutilización**: EmailTools puede usarse desde cualquier parte
3. **Testabilidad**: Cada componente se puede testear independientemente
4. **Mantenibilidad**: Cambios en lógica de email solo afectan EmailTools
5. **Escalabilidad**: Fácil agregar nuevos tipos de monitoreo
6. **Logging Centralizado**: Mejor observabilidad del sistema

## Próximos Pasos

1. Implementar OAuth2 en EmailTools
2. Agregar métricas con Prometheus
3. Crear dashboard de monitoreo
4. Implementar alertas automáticas
5. Agregar tests unitarios para el servicio
