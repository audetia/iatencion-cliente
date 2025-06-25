# Sistema de Logging SOTA para iatencion-cliente

Este es un sistema de logging de última generación (State-of-the-Art) diseñado específicamente para el proyecto de automatización de atención al cliente con IA.

## 🚀 Características Principales

### ✨ Logging Estructurado

- **Formato JSON**: Logs estructurados para fácil parsing y análisis
- **Campos consistentes**: timestamp, level, correlation_id, user_id, session_id
- **Metadatos automáticos**: información de contexto, rendimiento y trazabilidad

### 🔍 Trazabilidad Completa

- **Correlation IDs**: Seguimiento de requests completos a través de todo el sistema
- **Context Variables**: Tracking automático de usuario y sesión
- **Distributed Tracing**: Trazabilidad entre diferentes componentes

### 🛡️ Seguridad y Privacidad

- **Filtrado automático**: Remoción de datos sensibles (passwords, tokens, etc.)
- **Configuración flexible**: Control granular sobre qué se logea
- **Compliance ready**: Preparado para regulaciones de privacidad

### ⚡ Alto Rendimiento

- **Sampling inteligente**: Reducción de logs repetitivos en alto tráfico
- **Logging asíncrono**: No bloquea el hilo principal
- **Rotación automática**: Gestión automática del tamaño de archivos

### 🔧 Integraciones Específicas

- **LangGraph**: Logging específico para workflows de IA
- **LangChain**: Tracking de agentes y llamadas a LLM
- **Database**: Logging de queries y operaciones de BD
- **Email Processing**: Tracking específico para procesamiento de emails
- **API Calls**: Monitoring de llamadas a APIs externas

## 📁 Estructura del Proyecto

```
logging/
├── __init__.py          # Exports principales
├── config.py            # Configuración central del sistema
├── middleware.py        # Middleware para FastAPI
├── integrations.py      # Integraciones específicas
├── utils.py            # Utilidades y herramientas
└── README.md           # Esta documentación
```

## 🚀 Instalación y Configuración

### 1. Instalar Dependencias

Las dependencias ya están incluidas en `requirements.txt`:

```bash
pip install -r requirements.txt
```

### 2. Variables de Entorno

Agregar las siguientes variables a tu archivo `.env`:

```bash
# Configuración de Logging
LOG_LEVEL=INFO                    # DEBUG, INFO, WARNING, ERROR, CRITICAL
LOG_FORMAT=JSON                   # JSON o CONSOLE
LOG_FILE=logs/app.log            # Ruta del archivo de log
ENABLE_LOG_SAMPLING=false        # Habilitar sampling para alto tráfico
LOG_SAMPLE_RATE=0.1              # Tasa de sampling (10%)
MAX_LOG_SIZE=100MB               # Tamaño máximo antes de rotación
LOG_BACKUP_COUNT=5               # Número de archivos de backup
```

### 3. Inicialización

```python
from logging import setup_logging, get_logger

# Inicializar el sistema (una sola vez al inicio de la app)
setup_logging()

# Obtener logger en cualquier módulo
logger = get_logger(__name__)
```

## 📖 Uso Básico

### Logging Simple

```python
from logging import get_logger

logger = get_logger(__name__)

# Diferentes niveles
logger.debug("Información de debugging")
logger.info("Información general", user_id="123", action="login")
logger.warning("Advertencia", slow_query=True, execution_time="2.5s")
logger.error("Error ocurrido", error="Connection failed", retry_count=3)
```

### Context de Correlación

```python
from logging import CorrelationContext, get_logger

logger = get_logger(__name__)

# Automático con middleware (recomendado)
# El middleware genera correlation_id automáticamente

# Manual para procesos background
with CorrelationContext(user_id="user123", session_id="session456"):
    logger.info("Procesando email", email_id="email789")
    # Todos los logs dentro del contexto tendrán los IDs
```

### Decoradores para Funciones

```python
from logging import log_execution_time, log_method_calls

@log_execution_time()
def process_email(email_data):
    # Automáticamente logea tiempo de ejecución
    return processed_data

class EmailProcessor:
    @log_method_calls()
    def categorize_email(self, email):
        # Automáticamente logea entrada y salida del método
        return category
```

## 🔧 Integraciones Específicas

### LangGraph Workflows

```python
from logging.integrations import LangGraphLogger, log_langgraph_node

# Logger específico para workflow
workflow_logger = LangGraphLogger("email_processing")

# Decorador para nodos
@log_langgraph_node("categorize_email", "email_processing")
def categorize_email_node(state):
    # Automáticamente logea entrada, salida y tiempo de ejecución
    return updated_state

# Logging manual
workflow_logger.log_workflow_start(initial_state)
workflow_logger.log_node_execution("process_node", input_data, output_data, 1.23)
workflow_logger.log_workflow_end(final_state, 5.67)
```

### LangChain Agents

```python
from logging.integrations import LangChainLogger

agent_logger = LangChainLogger("email_categorizer")

# Logging de llamadas LLM
agent_logger.log_llm_call(
    model_name="gpt-4",
    prompt="Categorize this email...",
    response="Category: Support",
    tokens_used=150,
    execution_time=2.3
)

# Logging de RAG retrieval
agent_logger.log_rag_retrieval(
    query="How to handle refunds?",
    retrieved_docs=["doc1", "doc2"],
    similarity_scores=[0.85, 0.72]
)
```

### Base de Datos

```python
from logging.integrations import DatabaseLogger, log_database_operation

db_logger = DatabaseLogger()

@log_database_operation("insert")
def create_user(user_data):
    # Automáticamente logea la operación
    return user_id

# Logging manual
db_logger.log_query_execution(
    query="SELECT * FROM users WHERE id = %s",
    params=(123,),
    execution_time=0.05,
    rows_affected=1
)
```

### Procesamiento de Emails

```python
from logging.integrations import EmailLogger

email_logger = EmailLogger()

# Email recibido
email_logger.log_email_received({
    'sender': 'customer@example.com',
    'subject': 'Need help with order',
    'body': 'I have a problem...',
    'attachments': [],
    'timestamp': '2024-01-01T10:00:00Z'
})

# Email procesado
email_logger.log_email_processed(
    email_id="email_123",
    processing_result={
        'category': 'support',
        'action': 'forward_to_agent',
        'confidence': 0.95
    },
    execution_time=1.2
)
```

## 📊 Análisis y Monitoreo

### Análisis de Rendimiento

```python
from logging.utils import LogAnalyzer

analyzer = LogAnalyzer('logs/app.log')

# Métricas de las últimas 24 horas
metrics = analyzer.analyze_performance(time_window_hours=24)
print(f"Total requests: {metrics['total_requests']}")
print(f"Error rate: {metrics['error_rate']:.2f}%")
print(f"Average response time: {metrics['avg_response_time']:.3f}s")
```

### Seguimiento de Correlación

```python
# Encontrar todos los logs de un request específico
correlation_logs = analyzer.find_correlation_logs("correlation_id_123")

for log in correlation_logs:
    print(f"{log['timestamp']}: {log['message']}")
```

### Patrones de Error

```python
# Identificar patrones en errores
error_patterns = analyzer.find_error_patterns(hours_back=24)
print("Errores más frecuentes:", error_patterns['frequent_errors'])
```

### Health Check

```python
from logging.utils import MonitoringUtils

# Verificar salud del sistema de logging
health = MonitoringUtils.check_log_health('logs/app.log')
print(f"Status: {health['status']}")
print(f"Recent entries: {health['recent_entries']}")
```

## 🛠️ Herramientas de Debugging

### Context de Debug

```python
from logging.utils import DebugHelper

# Crear contexto específico para debugging
with DebugHelper.create_debug_context("user_registration", user_id="123"):
    logger.info("Starting user registration process")
    # Todos los logs tendrán el debug correlation ID
```

### Estado de Variables

```python
# Logear estado de variables para debugging
variables = {'user_id': 123, 'email': 'test@example.com', 'status': 'active'}
DebugHelper.log_variable_state(logger, variables, "before_validation")
```

## ⚙️ Configuración Avanzada

### Sampling para Alto Tráfico

```bash
# En .env
ENABLE_LOG_SAMPLING=true
LOG_SAMPLE_RATE=0.1  # Solo logea 10% de eventos repetitivos
```

### Formateo Personalizado

```bash
# Para desarrollo local
LOG_FORMAT=CONSOLE

# Para producción
LOG_FORMAT=JSON
```

### Exclusión de Endpoints

```python
# En deploy_api.py
app.add_middleware(
    LoggingMiddleware,
    exclude_paths=['/health', '/metrics', '/docs', '/favicon.ico']
)
```

## 📈 Métricas y Alertas

### Métricas Automáticas

El sistema genera automáticamente:

- Tiempo de respuesta promedio
- Tasa de errores
- Requests por minuto
- Distribución de endpoints
- Tipos de errores más comunes

### Condiciones de Alerta

```python
from logging.utils import MonitoringUtils

# Obtener condiciones de alerta predefinidas
alerts = MonitoringUtils.generate_alert_conditions()

for alert in alerts:
    print(f"{alert['name']}: {alert['description']}")
```

## 🐳 Configuración para Docker

### Variables de Entorno en Docker

```dockerfile
ENV LOG_LEVEL=INFO
ENV LOG_FORMAT=JSON
ENV LOG_FILE=/app/logs/app.log
```

### Volúmenes para Logs

```yaml
# docker-compose.yml
volumes:
  - ./logs:/app/logs
```

## 🔍 Troubleshooting

### Problema: No se generan logs

1. Verificar que `setup_logging()` se llama al inicio
2. Revisar permisos del directorio `logs/`
3. Verificar variables de entorno

### Problema: Logs muy verbosos

1. Cambiar `LOG_LEVEL` a `WARNING` o `ERROR`
2. Habilitar sampling: `ENABLE_LOG_SAMPLING=true`
3. Ajustar `LOG_SAMPLE_RATE`

### Problema: Archivos de log muy grandes

1. Reducir `MAX_LOG_SIZE`
2. Aumentar frecuencia de rotación
3. Habilitar compresión automática

## 📚 Ejemplos Completos

### Ejemplo: Procesamiento de Email Completo

```python
from logging import get_logger, CorrelationContext
from logging.integrations import EmailLogger, LangChainLogger

logger = get_logger(__name__)
email_logger = EmailLogger()
agent_logger = LangChainLogger("email_processor")

def process_email_workflow(email_data):
    # Crear contexto de correlación
    with CorrelationContext(user_id=email_data.get('user_id')):

        # Log email recibido
        email_logger.log_email_received(email_data)

        try:
            # Categorizar email
            logger.info("Starting email categorization")
            category = categorize_email(email_data['content'])

            # Log decisión del agente
            agent_logger.log_agent_decision(
                input_data=email_data,
                decision=category,
                reasoning="Based on content analysis"
            )

            # Generar respuesta
            response = generate_response(category, email_data)

            # Log resultado final
            email_logger.log_email_processed(
                email_id=email_data['id'],
                processing_result={
                    'category': category,
                    'action': 'auto_response',
                    'confidence': 0.95
                },
                execution_time=2.3
            )

            logger.info("Email processing completed successfully")
            return response

        except Exception as e:
            logger.error(
                "Email processing failed",
                email_id=email_data['id'],
                error=str(e),
                error_type=type(e).__name__
            )
            raise
```

## 🎯 Mejores Prácticas

1. **Siempre usar correlation IDs** para requests HTTP
2. **Filtrar datos sensibles** automáticamente
3. **Logear tanto éxitos como errores** para trazabilidad completa
4. **Usar niveles apropiados**: DEBUG para desarrollo, INFO para operaciones normales
5. **Incluir contexto relevante** en cada log entry
6. **Monitorear métricas regularmente** para detectar problemas temprano
7. **Configurar alertas** para condiciones críticas
8. **Rotar logs automáticamente** para evitar problemas de espacio

## 🤝 Contribuir

Para agregar nuevas funcionalidades al sistema de logging:

1. Crear nuevos loggers específicos en `integrations.py`
2. Agregar utilidades en `utils.py`
3. Actualizar la documentación
4. Agregar tests apropiados

---

**¡El sistema de logging está listo para uso en producción!** 🚀
