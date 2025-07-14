# Plan de Desarrollo: Transformación a SaaS del Sistema de Automatización de Email

## Fase 1: Infraestructura de Base de Datos (5 días)

### Día 1: Diseño y Configuración de PostgreSQL con pgvector

**Objetivo:** Diseñar el esquema completo de la base de datos y configurar PostgreSQL con la extensión pgvector para almacenar embeddings.

**Subtareas:**

- [X] Crear BBDD Postgres
- [X] Instalar y configurar la extensión pgvector siguiendo la documentación oficial
- [X] Crear el diseño del esquema de base de datos en un archivo `docs/database_schema.md` con las siguientes tablas:
  - `users`: id, email, name, created_at, updated_at, is_verified
  - `email_accounts`: id, user_id, email, imap_server, imap_port, smtp_server, smtp_port, encrypted_password, is_active, created_at, updated_at
  - `questions`: id, user_id, original_question, created_at
  - `question_variants`: id, question_id, variant_text, embedding (vector), created_at
  - `answers`: id, question_id, response_text, tone, created_at, updated_at
  - `automations`: id, user_id, email_account_id, type (enum: 'response', 'forward'), is_active, is_draft_mode, created_at, updated_at
  - `response_automations`: id, automation_id, response_instructions, custom_instructions
  - `forward_automations`: id, automation_id, forward_to_email, description (255 chars)
  - `automation_questions`: automation_id, question_id (tabla intermedia)
  - `email_statistics`: id, email_account_id, date, emails_processed, emails_responded, emails_forwarded, emails_spam, tokens_used
  - `email_categories`: id, email_account_id, category, count, date
- [X] Crear el script SQL de inicialización en `migrations/001_initial_schema.sql`
- [X] Documentar índices necesarios para optimización (especialmente para búsquedas vectoriales)
- [X] Crear archivo `.env.template` con las variables de entorno necesarias para la conexión a la base de datos

### Día 2: Implementación de Modelos SQLAlchemy

**Objetivo:** Crear los modelos de SQLAlchemy que representen las tablas de la base de datos con sus relaciones.

**Subtareas:**

- [X] Instalar dependencias: `sqlalchemy`, `psycopg2-binary`, `pgvector`, `python-dotenv`
- [X] Crear archivo `src/models/base.py` con la configuración base de SQLAlchemy
- [X] Implementar modelo `User` en `src/models/user.py`
- [X] Implementar modelo `EmailAccount` en `src/models/email_account.py`
- [X] Implementar modelos `Question`, `QuestionVariant`, y `Answer` en `src/models/qa.py`
- [X] Implementar modelos de automatización en `src/models/automation.py`:

  - `Automation` (tabla base)
  - `ResponseAutomation`
  - `ForwardAutomation`
  - `AutomationQuestion` (tabla intermedia)
- [X] Implementar modelos de estadísticas en `src/models/statistics.py`
- [X] Crear archivo `src/models/__init__.py` que exporte todos los modelos
- [X] Verificar que todos los modelos incluyan timestamps y relaciones correctas
- [X] Implementar métodos de actualización automática de timestamps en modelos base:

  - Crear mixin `TimestampMixin` con métodos `before_update()`
  - Aplicar el mixin a User, EmailAccount, Answer, Automation
  - Configurar SQLAlchemy events para auto-actualizar `updated_at`
  - Crear tests unitarios para verificar funcionamiento

### Día 3: Capa de Acceso a Datos - Parte 1 (Usuarios y Cuentas)

**Objetivo:** Implementar la capa de acceso a datos para gestión de usuarios y cuentas de email.

**Subtareas:**

- [X] Crear `src/database.py` con la clase principal `DatabaseManager` y configuración de conexión
- [X] Implementar método de encriptación/desencriptación para contraseñas IMAP usando `cryptography`
- [X] Implementar métodos de usuario:
  - `create_user(email, name)`: Crear usuario nuevo
  - `get_user_by_email(email)`: Buscar usuario por email
  - `get_user_by_id(user_id)`: Buscar usuario por ID
  - `update_user(user_id, **kwargs)`: Actualizar datos de usuario
  - `verify_user(user_id)`: Marcar usuario como verificado
- [X] Implementar métodos de cuentas de email:
  - `add_email_account(user_id, email, imap_config, smtp_config)`: Añadir cuenta
  - `get_user_email_accounts(user_id)`: Listar cuentas de un usuario
  - `update_email_account(account_id, **kwargs)`: Actualizar configuración
  - `delete_email_account(account_id)`: Eliminar cuenta
  - `get_email_account_credentials(account_id)`: Obtener credenciales desencriptadas
- [X] Crear tests unitarios básicos para verificar funcionalidad
- [X] Documentar todos los métodos con docstrings detallados

### Día 4: Capa de Acceso a Datos - Parte 2 (Q&A y Embeddings)

**Objetivo:** Implementar la gestión de preguntas, respuestas y búsquedas vectoriales.

**Subtareas:**

- [X] Instalar `langchain_google_genai` para generación de embeddings
- [X] Implementar métodos de Q&A en `DatabaseManager`:
  - `create_question(user_id, original_question)`: Crear pregunta original
  - `add_question_variant(question_id, variant_text, embedding)`: Añadir variante con embedding
  - `create_answer(question_id, response_text, response_instructions)`: Crear respuesta
  - `update_answer(answer_id, **kwargs)`: Actualizar respuesta
  - `get_question_with_variants(question_id)`: Obtener pregunta con todas sus variantes
  - `search_similar_questions(user_id, query_embedding, threshold=0.8, limit=5)`: Búsqueda vectorial
- [X] Implementar método helper `generate_embedding(text)` que use el modelo de embeddings de Google
- [X] Implementar método adicional `create_question_with_variants()` para UX del frontend
- [X] Implementar caché de embeddings para evitar regenerar embeddings idénticos
- [X] Crear función de utilidad para calcular similitud coseno entre embeddings
- [X] Documentar el flujo de búsqueda semántica
- [X] **Índice vectorial HNSW ya implementado** (superior a IVFFlat para nuestro caso de uso)

### Día 5: Capa de Acceso a Datos - Parte 3 (Automatizaciones y Estadísticas)

**Objetivo:** Completar la capa de datos con gestión de automatizaciones y estadísticas.

**Subtareas:**

- [X] Implementar métodos de automatización:

  - `create_response_automation(user_id, email_account_id, question_ids, tone, is_draft_mode)`: Crear automatización de respuesta
  - `create_forward_automation(user_id, email_account_id, forward_to, description)`: Crear automatización de reenvío
  - `get_active_automations(email_account_id)`: Obtener automatizaciones activas
  - `toggle_automation(automation_id)`: Activar/desactivar automatización
  - `update_automation_questions(automation_id, question_ids)`: Actualizar preguntas asociadas
  - `get_automation_details(automation_id)`: Obtener detalles completos
- [X] Implementar métodos de estadísticas:

  - `log_email_processed(email_account_id, category, action_taken)`: Registrar procesamiento
  - `increment_tokens_used(email_account_id, tokens)`: Actualizar uso de tokens
  - `get_daily_statistics(email_account_id, date_range)`: Obtener estadísticas diarias
  - `get_category_distribution(email_account_id, date_range)`: Distribución por categorías
  - `calculate_time_saved(email_account_id)`: Calcular tiempo ahorrado (5 min/email)
- [X] Implementar agregaciones eficientes usando queries SQL optimizadas
- [X] Añadir logging detallado para debugging
- [X] Crear servicio de tracking de uso manual en `src/services/usage_service.py`:

  - Implementar `track_email_processed(user_id, email_data)` con transacciones atómicas
  - Método `update_monthly_usage()` con UPSERT optimizado
  - Implementar retry logic con backoff exponencial
  - Añadir logging detallado para debugging
  - Crear método `validate_usage_limits(user_id)` antes de procesar
  - Implementar caché Redis para consultas frecuentes de límites

## Fase 2: Modificación del Flujo de LangGraph (3 días)

### Día 6: Integración de Automatizaciones de Reenvío en el Flujo

**Objetivo:** Modificar el árbol de decisión de LangGraph para incluir la lógica de reenvío tras la clasificación.

**Subtareas:**

- [X] Crear nuevo prompt `FORWARD_DECISION_PROMPT` en `src/prompts.py` que:
  - Reciba el contenido del email
  - Reciba lista de descripciones de reenvíos configurados
  - Reciba lista de temas de Q&A (para evitar reenviar preguntas respondibles)
  - Determine si el email coincide con algún criterio de reenvío
- [X] Crear estructura de salida `ForwardDecisionOutput` en `src/structure_outputs.py`:
  - `should_forward`: bool
  - `forward_automation_id`: Optional[int]
  - `confidence_score`: float
- [X] Añadir nuevo agente `check_forward_rules` en `src/agents.py`
- [X] Crear nuevo nodo `evaluate_forward_rules` en `src/nodes.py` que:
  - Obtenga las automatizaciones activas de la cuenta
  - Ejecute el agente de decisión de reenvío
  - Registre la decisión en el estado
- [X] Modificar `src/graph.py` para incluir el nuevo nodo después de `categorize_email`
- [X] Añadir edge condicional que dirija a reenvío o continúe con el flujo normal
- [X] Actualizar `GraphState` en `src/state.py` para incluir información de reenvío
- [X] Crear la lógica de reenvio de correo

### Día 7: Implementación de Q&A Personalizado con RAG

**Objetivo:** Reemplazar el sistema de RAG estático por uno dinámico basado en las Q&A del usuario.

**Subtareas:**

- [X] Modificar `src/nodes.py` en el método `retrieve_from_rag`:
  - Obtener el `email_account_id` del estado
  - Recuperar las Q&A activas del usuario desde la base de datos
  - Para cada query RAG, buscar en las variantes de preguntas usando búsqueda vectorial
- [X] Crear nuevo método `dynamic_rag_search` que:
  - Genere embedding de la query
  - Busque en `question_variants` usando pgvector
  - Retorne las respuestas asociadas ordenadas por relevancia
- [X] Modificar el prompt `GENERATE_RAG_ANSWER_PROMPT` para trabajar con respuestas personalizadas
- [X] Añadir logging detallado de qué preguntas se matchean
- [X] Crear método de caché para embeddings de queries frecuentes
- [X] Actualizar las estadísticas para registrar qué Q&A se utilizan

### Día 8: Testing e Integración del Flujo Modificado ✅ COMPLETADO

**Objetivo:** Asegurar que todas las modificaciones funcionan correctamente juntas.

**Subtareas:**

- [X] Crear script `tests/test_modified_flow.py` con casos de prueba:

  - Email que debe ser reenviado
  - Email con pregunta que tiene respuesta en Q&A
  - Email que debe usar el RAG original
  - Email spam que debe ser ignorado
- [X] Implementar fixtures de prueba con datos de ejemplo en la base de datos
- [X] Verificar que las estadísticas se actualizan correctamente
- [X] Probar edge cases:

  - Usuario sin automatizaciones configuradas
  - Q&A con embeddings corruptos
  - Múltiples automatizaciones que podrían aplicar
- [X] Verificar compatibilidad con el sistema existente
- [ ] Documentar el nuevo flujo en `docs/modified_workflow.md` (OPCIONAL - puede hacerse en Día 21)
- [ ] Crear diagrama actualizado del flujo usando Mermaid (OPCIONAL - puede hacerse en Día 21)
- [ ] Integrar tracking de uso en el flujo de LangGraph (MOVIDO a Día 15 - Servicio de Gestión de Uso):

  - Modificar todos los nodos que procesan emails para llamar `usage_service.track_email_processed()`
  - Implementar verificación de límites antes de procesar (`validate_usage_limits()`)
  - Añadir manejo de errores para casos donde se exceden límites
  - Crear logs específicos para tracking de uso vs procesamiento de emails
  - Implementar fallback cuando el tracking falla (no debe parar el procesamiento)

## Fase 3: Servicios Backend (7 días)

### Día 9: Servicio de Monitoreo de Buzón

**Objetivo:** Crear el servicio que monitorea continuamente los buzones activos.

**Subtareas:**

- [X] Crear `src/services/inbox_monitor.py` con clase `InboxMonitor`
- [X] Implementar método `start_monitoring()` que:
  - Cargue todas las cuentas de email activas
  - Cree un thread pool para monitorear múltiples cuentas
  - Implemente rate limiting para respetar límites IMAP
- [X] Crear método `monitor_single_inbox(email_account_id)` que:
  - Se conecte al buzón usando las credenciales
  - Busque emails nuevos desde la última verificación
  - Lance el workflow de LangGraph para cada email nuevo
  - Maneje errores de conexión con reintentos exponenciales
- [X] Implementar sistema de heartbeat para detectar threads muertos
- [X] Añadir métricas de rendimiento (emails/minuto, latencia)
- [X] Crear sistema de alertas para errores críticos usando telegram
- [X] Implementar graceful shutdown para cerrar conexiones correctamente
- [ ] Documentar configuración de concurrencia y límites

### Día 10: Servicio de Registro de Q&A

**Objetivo:** Implementar el sistema de registro de preguntas y respuestas con generación de variantes.

**Subtareas:**

- [ ] Crear `src/services/qa_register.py` con clase `QARegistrationService`
- [ ] Implementar prompt `GENERATE_QUESTION_VARIANTS_PROMPT` que genere 10 variantes
- [ ] Crear método `register_qa(user_id, question, answer, tone='professional')`:
  - Valide entrada (longitud, caracteres permitidos)
  - Cree la pregunta original en la base de datos
  - Genere 10 variantes usando LLM
  - Calcule embeddings para cada variante
  - Guarde todo en una transacción
- [ ] Implementar detección de duplicados comparando embeddings
- [ ] Crear método `update_qa(question_id, new_answer=None, new_tone=None)`
- [ ] Añadir método `delete_qa(question_id)` con cascade a automatizaciones
- [ ] Implementar validación de calidad de variantes (evitar repeticiones)
- [ ] Crear método batch para importar múltiples Q&A desde CSV
- [ ] Añadir rate limiting para evitar abuso del LLM

### Día 11: Sistema de Autenticación - Registro

**Objetivo:** Implementar el sistema de registro de usuarios con verificación OTP.

**Subtareas:**

- [ ] Instalar dependencias: `pyotp`, `qrcode`, `python-jose[cryptography]`
- [ ] Crear `src/services/auth/signup.py` con clase `SignupService`
- [ ] Implementar generación y envío de OTP por email:
  - Generar código de 6 dígitos válido por 10 minutos
  - Crear template HTML para el email de verificación
  - Integrar con el sistema de envío de emails existente
- [ ] Crear método `initiate_signup(email, name)`:
  - Validar formato de email
  - Verificar que el email no esté registrado
  - Crear usuario en estado no verificado
  - Generar y enviar OTP
- [ ] Implementar `verify_otp(email, otp_code)`:
  - Validar OTP y expiración
  - Marcar usuario como verificado
  - Limpiar OTPs antiguos
- [ ] Añadir protección contra fuerza bruta (max 5 intentos)
- [ ] Implementar reenvío de OTP con cooldown de 60 segundos
- [ ] Crear logs de auditoría para intentos de registro

### Día 12: Sistema de Autenticación - Login

**Objetivo:** Implementar el sistema de login con OTP y gestión de sesiones JWT.

**Subtareas:**

- [ ] Crear `src/services/auth/login.py` con clase `LoginService`
- [ ] Implementar `initiate_login(email)`:
  - Verificar que el usuario existe y está verificado
  - Generar y enviar OTP de login
  - Registrar intento de login
- [ ] Crear `complete_login(email, otp_code)`:
  - Validar OTP
  - Generar JWT con claims apropiados
  - Crear refresh token
  - Registrar sesión activa
- [ ] Implementar middleware de autenticación para validar JWT
- [ ] Crear sistema de refresh tokens:
  - Token de acceso: 15 minutos
  - Refresh token: 7 días
  - Endpoint para renovar tokens
- [ ] Añadir blacklist de tokens para logout
- [ ] Implementar detección de sesiones concurrentes
- [ ] Crear endpoint de logout que invalide tokens
- [ ] Documentar flujo de autenticación completo

### Día 13: Servicio de Conexión IMAP

**Objetivo:** Crear servicio robusto para verificar y almacenar credenciales IMAP/SMTP.

**Subtareas:**

- [ ] Crear `src/services/inbox_connection.py` basándose en `EmailTools.py`
- [ ] Implementar `test_connection(imap_config, smtp_config)`:
  - Probar conexión IMAP con timeout de 10 segundos
  - Verificar permisos de lectura/escritura
  - Probar conexión SMTP
  - Retornar diagnóstico detallado
- [ ] Crear método `save_email_account(user_id, email, imap_config, smtp_config)`:
  - Validar que el email coincide con las credenciales
  - Encriptar credenciales antes de guardar
  - Asociar con el usuario
  - Activar monitoreo automáticamente
- [ ] Implementar detección automática de configuración para proveedores comunes
- [ ] Añadir soporte para OAuth2 (Gmail, Outlook)
- [ ] Crear método de verificación periódica de conexiones
- [ ] Implementar notificación al usuario si las credenciales fallan
- [ ] Documentar configuraciones para los 10 proveedores más comunes

### Día 14: API REST Principal

**Objetivo:** Crear la API que exponga toda la funcionalidad a través de endpoints REST.

**Subtareas:**

- [ ] Crear `src/api.py` usando FastAPI
- [ ] Implementar endpoints de autenticación:
  - `POST /auth/signup`: Iniciar registro
  - `POST /auth/verify`: Verificar OTP de registro
  - `POST /auth/login`: Iniciar login
  - `POST /auth/login/verify`: Completar login con OTP
  - `POST /auth/refresh`: Renovar tokens
  - `POST /auth/logout`: Cerrar sesión
- [ ] Implementar endpoints de gestión de cuentas:
  - `POST /accounts/email`: Añadir cuenta de email
  - `GET /accounts/email`: Listar cuentas
  - `DELETE /accounts/email/{id}`: Eliminar cuenta
  - `POST /accounts/email/test`: Probar conexión
- [ ] Implementar endpoints de Q&A:
  - `POST /qa`: Crear pregunta/respuesta
  - `GET /qa`: Listar Q&A del usuario
  - `PUT /qa/{id}`: Actualizar Q&A
  - `DELETE /qa/{id}`: Eliminar Q&A
- [ ] Implementar endpoints de automatizaciones:
  - `POST /automations/response`: Crear automatización de respuesta
  - `POST /automations/forward`: Crear automatización de reenvío
  - `GET /automations`: Listar automatizaciones
  - `PATCH /automations/{id}/toggle`: Activar/desactivar
- [ ] Implementar endpoints de estadísticas:
  - `GET /stats/summary`: Resumen general
  - `GET /stats/daily`: Estadísticas diarias
  - `GET /stats/categories`: Distribución por categorías
- [ ] Añadir documentación Swagger automática
- [ ] Implementar rate limiting global
- [ ] Crear middleware de logging y manejo de errores

### Día 15: Servicio de Gestión de Uso y Límites

**Objetivo:** Implementar el servicio completo de tracking de uso y validación de límites de suscripción.

**Subtareas:**

- [ ] Crear `src/services/usage_service.py` con clase `UsageService`:

  - Método `track_email_processed(user_id, email_account_id, action_data)`
  - Implementar UPSERT atómico para `user_usage_monthly`
  - Manejo de concurrencia con locks optimistas
  - Logging estructurado de todas las operaciones
- [ ] Implementar `src/services/limits_service.py` con clase `LimitsService`:

  - `check_can_process_email(user_id)` -> bool con detalles del límite
  - `get_current_usage(user_id, year, month)` con caché
  - `get_user_limits(user_id)` consultando suscripción activa
  - Implementar alertas cuando se acerca a límites (80%, 90%, 95%)
- [ ] Crear middleware de límites para la API:

  - Decorador `@check_usage_limits` para endpoints críticos
  - Respuestas HTTP 429 con headers informativos
  - Rate limiting diferenciado por tier de suscripción
- [ ] Implementar sistema de notificaciones:

  - Email cuando se alcanza 80% del límite mensual
  - Notificación in-app cuando se excede límite
  - Sugerencias de upgrade de plan
- [ ] Crear jobs de mantenimiento:

  - Limpieza de datos de uso antiguos (>12 meses)
  - Recálculo de estadísticas en caso de inconsistencias
  - Reportes mensuales de uso por usuario
- [ ] Implementar métricas y monitoreo:

  - Contador de emails procesados por segundo
  - Latencia de operaciones de tracking
  - Alertas para fallos en tracking de uso

## Fase 4: Frontend (5 días)

### Día 16: Setup y Estructura Base del Frontend

**Objetivo:** Configurar el proyecto frontend con React y establecer la arquitectura base.

**Subtareas:**

- [ ] Crear directorio `frontend/` en la raíz del proyecto
- [ ] Inicializar proyecto React con Vite: `npm create vite@latest . -- --template react`
- [ ] Instalar dependencias esenciales:
  - `axios` para llamadas API
  - `react-router-dom` para navegación
  - `@tanstack/react-query` para gestión de estado servidor
  - `tailwindcss` para estilos
  - `react-hook-form` para formularios
  - `sonner` para notificaciones toast
- [ ] Configurar estructura de carpetas:
  ```
  frontend/├── src/│   ├── components/│   ├── pages/│   ├── services/│   ├── hooks/│   ├── utils/│   └── contexts/
  ```
- [ ] Crear servicio base de API en `services/api.js` con interceptores para tokens
- [ ] Configurar contexto de autenticación global
- [ ] Implementar rutas protegidas con `PrivateRoute` component
- [ ] Crear layout base con navegación condicional

### Día 17: Páginas de Autenticación

**Objetivo:** Implementar las páginas de registro y login con verificación OTP.

**Subtareas:**

- [ ] Crear página de registro (`pages/Signup.jsx`):
  - Formulario con email y nombre
  - Validación en tiempo real
  - Transición a verificación OTP tras envío
  - Componente de entrada OTP con 6 campos
  - Botón de reenvío con countdown
- [ ] Crear página de login (`pages/Login.jsx`):
  - Formulario solo con email
  - Flujo similar de OTP
  - Redirección automática tras éxito
- [ ] Implementar `AuthContext` con métodos:
  - `signup(email, name)`
  - `verifySignup(email, otp)`
  - `login(email)`
  - `verifyLogin(email, otp)`
  - `logout()`
  - `refreshToken()`
- [ ] Crear hook `useAuth()` para acceder al contexto
- [ ] Añadir persistencia de sesión en localStorage
- [ ] Implementar auto-refresh de tokens
- [ ] Crear componente de loading global durante verificación

### Día 18: Configuración IMAP y Dashboard Principal

**Objetivo:** Crear la página de configuración IMAP y el dashboard con estadísticas.

**Subtareas:**

- [ ] Crear página de configuración IMAP (`pages/IMAPSetup.jsx`):

  - Detectar si el usuario ya tiene cuenta configurada
  - Formulario con campos para IMAP/SMTP
  - Botón de "Detectar configuración" para proveedores comunes
  - Test de conexión con feedback visual
  - Guardar y redirigir a dashboard
- [ ] Crear componente `Dashboard.jsx` con 4 secciones:

  - Header con estadísticas resumidas en cards:
    - Tiempo ahorrado (con animación de contador)
    - Emails respondidos
    - Emails descartados
    - Tasa de automatización
  - Gráfico de barras con emails por día (últimos 7 días)
  - Lista de automatizaciones activas
  - Botón flotante para añadir automatización
- [ ] Implementar hooks para datos:

  - `useStatistics()` con polling cada 60 segundos
  - `useAutomations()` con refetch en cambios
- [ ] Crear componentes reutilizables:

  - `StatCard` para mostrar métricas
  - `AutomationCard` con toggle y preview
- [ ] Añadir skeleton loaders mientras cargan datos
- [ ] Integrar indicadores de límites en el dashboard:

  - Crear componente `UsageMeter` con progress bars para cada límite
  - Mostrar alertas visuales cuando se acerca a límites
  - Añadir tooltips explicativos sobre cada métrica
  - Implementar notificaciones push para límites excedidos
  - Crear link directo a upgrade de plan cuando sea necesario

### Día 19: Gestión de Automatizaciones

**Objetivo:** Implementar la creación y gestión de automatizaciones de respuesta y reenvío.

**Subtareas:**

- [ ] Crear modal/página para nueva automatización (`components/NewAutomation.jsx`):
  - Selector de tipo (Respuesta/Reenvío)
  - Para respuestas:
    - Campo de pregunta principal
    - Editor de texto para respuesta
    - Selector de tono (profesional/casual/amigable)
    - Checkbox para modo borrador
    - Preview en tiempo real
  - Para reenvíos:
    - Campo email destino
    - Textarea para descripción (max 256 chars)
    - Ejemplos de uso
- [ ] Crear página de gestión de Q&A (`pages/QAManagement.jsx`):
  - Lista searchable de Q&A existentes
  - Posibilidad de editar respuestas inline
  - Bulk delete con confirmación
  - Importación desde CSV
- [ ] Implementar componente `AutomationList`:
  - Cards expandibles con detalles completos
  - Toggle switch para activar/desactivar
  - Botones de editar y eliminar
  - Indicador visual de actividad
- [ ] Crear hooks específicos:
  - `useCreateAutomation()`
  - `useToggleAutomation()`
  - `useDeleteAutomation()`
- [ ] Añadir confirmaciones para acciones destructivas

### Día 20: Perfil de Usuario y Finalización

**Objetivo:** Completar el frontend con la página de perfil y pulir la experiencia de usuario.

**Subtareas:**

- [ ] Crear página de perfil (`pages/Profile.jsx`):

  - Mostrar información del usuario
  - Sección de cuentas de email conectadas
  - Posibilidad de añadir/eliminar cuentas
  - Botón de cerrar sesión
  - Zona de peligro para eliminar cuenta
- [ ] Implementar tema oscuro/claro con toggle
- [ ] Añadir animaciones y transiciones:

  - Fade in/out en cambios de página
  - Slide in para modales
  - Pulse en elementos loading
  - Success animations en acciones completadas
- [ ] Crear página 404 y manejo de errores global
- [ ] Implementar PWA básico:

  - Service worker para caché
  - Manifest.json
  - Iconos para diferentes tamaños
- [ ] Optimizar bundle:

  - Code splitting por rutas
  - Lazy loading de componentes pesados
  - Compresión de assets
- [ ] Crear script `start_frontend.py` que:

  - Instale dependencias si no existen
  - Compile en modo desarrollo
  - Abra el navegador automáticamente
- [ ] Añadir sección de uso y facturación en perfil:

  - Mostrar uso actual vs límites del plan
  - Historial de uso de últimos 6 meses
  - Botón de upgrade/downgrade de plan
  - Descarga de reportes de uso en PDF
  - Configuración de alertas de límites personalizadas

## Fase 5: Integración y Despliegue (1 día)

### Día 21: Docker, Testing de Integración y Documentación

**Objetivo:** Preparar el proyecto para desarrollo local fácil y futuro despliegue.

**Subtareas:**

- [ ] Crear `docker-compose.yml` para desarrollo local:

  - Servicio PostgreSQL con pgvector
  - Servicio backend (FastAPI)
  - Servicio frontend (Vite dev server)
  - Servicio de monitoreo (inbox_monitor)
  - Redis para caché (futuro)
- [ ] Crear scripts de desarrollo:

  - `scripts/setup_dev.py`: Configurar entorno completo
  - `scripts/reset_db.py`: Limpiar y recrear base de datos
  - `scripts/seed_data.py`: Datos de prueba
- [ ] Escribir suite de tests de integración:

  - Flujo completo de registro → configuración → automatización
  - Test de procesamiento de email end-to-end
  - Test de concurrencia en monitoreo
- [ ] Actualizar `README.md` con:

  - Arquitectura del sistema
  - Instrucciones de instalación paso a paso
  - Variables de entorno necesarias
  - Guía de contribución
- [ ] Crear `docs/API.md` con documentación de endpoints
- [ ] Generar requerimientos actualizados
- [ ] Crear checklist de pre-producción
- [ ] Tests específicos para el sistema de uso:

  - Test de concurrencia: múltiples emails procesándose simultáneamente
  - Test de límites: verificar que se respetan correctamente
  - Test de failover: qué pasa si el tracking falla
  - Test de performance: 1000 emails procesados en paralelo
  - Test de consistencia: verificar que los datos agregados coinciden
  - Load testing del sistema de límites bajo alta carga

## Consideraciones Técnicas Transversales

### Seguridad

- Encriptación AES-256 para credenciales IMAP
- Rate limiting en todos los endpoints
- Validación exhaustiva de inputs
- Protección CSRF en formularios
- Headers de seguridad (CORS, CSP)

### Performance

- Índices de base de datos optimizados
- Caché de embeddings frecuentes
- Paginación en listados largos
- Lazy loading en frontend
- Connection pooling para IMAP

### Monitoreo

- Logs estructurados con niveles apropiados
- Métricas de latencia y throughput
- Alertas para fallos críticos
- Dashboard de salud del sistema

### Escalabilidad

- Arquitectura stateless
- Trabajos asíncronos con queue (futuro)
- Separación de lectura/escritura (futuro)
- CDN para assets estáticos (futuro)
