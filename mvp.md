# Plan de Desarrollo SaaS - Email Automation

## ARQUITECTURA OBJETIVO

**Stack Técnico:**

* **Backend** : Python 3.11+ con FastAPI y SQLAlchemy 2.0
* **Base de Datos** : PostgreSQL 15+ con pgvector
* **Autenticación** : JWT + OTP email (sin Firebase)
* **Async** : Celery + Redis
* **IA** : LangChain/LangGraph + OpenAI text-embedding-3-small
* **Deploy** : Docker (España MVP, Kubernetes futuro internacional)

**Estructura de Servicios:**

```
saas_email_automation/
├── services/
│   ├── auth_service/           # JWT + OTP + usuarios
│   ├── user_config_service/    # IMAP + FAQ management
│   ├── email_processor_service/ # LangGraph multi-tenant
│   ├── rag_service/            # Embeddings + search
│   └── analytics_service/      # Métricas + dashboard
├── shared/
│   ├── models/                 # SQLAlchemy models
│   ├── database/               # DB config + migrations
│   └── security/               # JWT + encryption
└── tests/
```

## SCHEMA DATABASE CORE

```sql
users (id, email, password_hash, created_at, subscription_tier, is_active)
email_configs (id, user_id, imap_server, email_address, encrypted_credentials)
questions (id, user_id, original_question, priority, is_active)
question_variants (id, question_id, variant_text, is_confirmed)
responses (id, question_id, response_text, response_type)
embeddings (id, question_id, embedding_vector, model_version)
email_logs (id, user_id, processed_at, action_taken, confidence_score)
```

---

## FASE 1: INFRAESTRUCTURA (Sprints 1-2)

### 1.1 Setup Base

**Subtareas:**

* Estructura modular con Docker compose (PostgreSQL + pgvector + Redis)
* Configurar bandit para security linting
* SQLAlchemy models con relaciones y UUID PKs
* Alembic migrations setup
* Logging structured con correlation IDs

### 1.2 Autenticación JWT

**Subtareas:**

* JWT tokens (access 15min + refresh 7days)
* OTP system via email (5min expiry)
* Rate limiting con Redis
* Endpoints: register, verify-email, login, refresh, logout
* Password hashing con bcrypt + audit logging

### 1.3 User Management

**Subtareas:**

* User CRUD con soft delete
* Session tracking en Redis
* Validation schemas con Pydantic
* User preferences storage

---

## FASE 2: CORE BUSINESS LOGIC (Sprints 3-4)

### 2.1 Configuración IMAP

**Subtareas:**

* EmailConfig service con validación real-time
* Credenciales encryption con Fernet + key rotation
* Endpoints: validate, create, update, delete configs
* Health checks periódicos con notifications
* Multi-provider support (Gmail OAuth2, generic IMAP)

### 2.2 Sistema FAQ

**Subtareas:**

* Question CRUD con user isolation
* IA variant generation usando LLM (5 variantes por pregunta)
* Endpoints: CRUD questions, generate/confirm variants
* Template system para onboarding rápido
* Priority ordering para matching

### 2.3 Response Management

**Subtareas:**

* Response CRUD (manual text + document-based)
* Document upload con content extraction (PDF, DOCX, TXT)
* Rich text support con HTML sanitization
* Preview system con sample data

### 2.4 Embeddings & RAG

**Subtareas:**

* Embedding service con text-embedding-3-small
* Batch processing asíncrono
* pgvector similarity search con HNSW indexes
* Hybrid search (vector + keyword)
* Context window management para RAG

---

## FASE 3: PROCESAMIENTO ASYNC (Sprints 5-6)

### 3.1 Multi-Tenant Workflow

**Subtareas:**

* Adaptar LangGraph para context switching dinámico
* State isolation entre users con Redis
* Resource limits per subscription tier
* User-specific prompts y model selection

### 3.2 Celery Queue System

**Subtareas:**

* Celery con Redis broker + multiple queues
* Task categorization (high priority, background, maintenance)
* Retry logic con exponential backoff
* Distributed email polling por usuario

### 3.3 Email Processing Engine

**Subtareas:**

* EmailToolsClass multi-user con connection pooling
* Batch processing con deduplication
* Classification routing (auto-send vs draft)
* Response generation con quality control

### 3.4 Delivery Management

**Subtareas:**

* Auto-send vs draft per user preferences
* Scheduled sending con business hours
* Delivery tracking y retry logic
* Send queue con rate limiting

---

## FASE 4: UI & ANALYTICS (Sprints 7-8)

### 4.1 Analytics Backend

**Subtareas:**

* Real-time metrics aggregation
* Time-series data en PostgreSQL
* Dashboard APIs: overview, emails, questions, trends
* Report generation (PDF, CSV export)

### 4.2 Configuration API

**Subtareas:**

* Unified config endpoints para profile, email, questions, responses
* Bulk operations (import/export questions)
* Configuration versioning con rollback
* Validation layers cross-settings

### 4.3 Monitoring

**Subtareas:**

* Health check endpoints (/health/database, /health/redis, etc.)
* Intelligent alerting con threshold tuning
* Performance monitoring básico
* Error tracking y notification channels

---

## FASE 5: PRODUCCIÓN (Sprints 9-10)

### 5.1 Performance

**Subtareas:**

* Database query optimization + indexes
* Redis caching strategy (sessions, frequent queries)
* API response optimization (compression, pagination)
* AI cost optimization (caching responses, batch calls)

### 5.2 Security

**Subtareas:**

* Input validation comprehensiva (SQL injection, XSS prevention)
* Security headers (HTTPS, HSTS, CSP)
* Encryption at rest para sensitive data
* Security event logging + monitoring

### 5.3 Production Deploy

**Subtareas:**

* Docker multi-stage builds para production
* Docker Compose orchestration (España MVP)
* CI/CD pipeline con automated testing
* Blue-green deployment con Docker Swarm
* Production monitoring (APM, logs, metrics)
* Kubernetes migration plan (futuro internacional)

---

## CONSIDERACIONES TÉCNICAS

### Seguridad Multi-Tenant

* Row-Level Security en PostgreSQL para isolation automático
* Fernet encryption para IMAP credentials con key rotation 90 días
* JWT sin vendor lock-in, OTP via email directo
* Audit logging completo de accesos cross-tenant

### Escalabilidad

* Stateless design para horizontal scaling
* pgvector con HNSW indexes para similarity search eficiente
* Connection pooling optimizado per tenant
* Celery workers escalables según load

### Cost Optimization

* text-embedding-3-small en lugar de ada-002 (más barato)
* Caching agresivo de responses similares
* Batch processing para optimize API calls
* Model selection basado en subscription tier

### Performance Targets

* Database queries <100ms (95th percentile)
* API responses <200ms
* Email processing <30s end-to-end
* Vector search <50ms
* 99.9% uptime SLA

---

## CRONOGRAMA

**20 semanas total (10 sprints de 2 semanas)**

**Hitos Críticos:**

* Week 4: Auth + DB foundation
* Week 8: Core business logic MVP
* Week 12: Multi-user async processing
* Week 16: Complete UI workflows
* Week 20: Production-ready

**MVP Target: 10 clientes iniciales**
**Escalabilidad: Arquitectura preparada para 1000+ usuarios**

---

## RECURSOS NECESARIOS

**Infraestructura:**

* PostgreSQL 15+ con pgvector (AWS RDS/Google Cloud SQL)
* Redis para cache + message broker
* Docker registry + Kubernetes cluster
* Domain + SSL certificates

**APIs Externas:**

* OpenAI API (text-embedding-3-small + LLM)
* Brevo para OTP y notifications
* File storage (AWS S3) para documents

**Desarrollo:**

* Cursor IDE + Claude integration
* Git + CI/CD pipeline
* Security scanning tools
* Performance monitoring stack
