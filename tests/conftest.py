import os
import sys
import pytest
import logging
from pathlib import Path
from datetime import datetime, timedelta
from typing import List, Dict, Generator
import random
import numpy as np
from faker import Faker
from sqlalchemy import create_engine, text
from sqlalchemy.orm import sessionmaker, Session
from dotenv import load_dotenv

# Add the project root directory to the Python path
project_root = str(Path(__file__).parent.parent)
sys.path.insert(0, project_root)

# Import models and database utilities
from src.models import (
    Base, User, EmailAccount, Question, QuestionVariant, Answer,
    Automation, ResponseAutomation, ForwardAutomation, AutomationType,
    EmailProcessed, UserUsageMonthly
)
from src.database import DatabaseManager

# Load environment variables
load_dotenv()

# Configure logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

# Initialize Faker for generating realistic data
fake = Faker('es_ES')  # Spanish locale for more realistic data

# Test database URL
TEST_DATABASE_URL = os.getenv("POSTGRES_TEST_URL")
if not TEST_DATABASE_URL:
    raise ValueError("POSTGRES_TEST_URL not found in environment variables")

@pytest.fixture(scope="session")
def test_engine():
    """Create a test database engine."""
    engine = create_engine(
        TEST_DATABASE_URL,
        echo=False,  # Set to True for SQL debugging
        pool_pre_ping=True
    )
    
    # Ensure pgvector extension is enabled
    with engine.connect() as conn:
        conn.execute(text("CREATE EXTENSION IF NOT EXISTS vector"))
        conn.commit()
    
    # Create all tables from SQLAlchemy models
    Base.metadata.create_all(bind=engine)
    logger.info("✅ Test database tables created from SQLAlchemy models")
    
    yield engine
    
    # Cleanup after all tests - use CASCADE to handle dependencies
    with engine.connect() as conn:
        # Get all table names
        result = conn.execute(text("""
            SELECT tablename FROM pg_tables 
            WHERE schemaname = 'public'
        """))
        tables = [row[0] for row in result]
        
        # Drop all tables with CASCADE
        for table in tables:
            conn.execute(text(f"DROP TABLE IF EXISTS {table} CASCADE"))
        conn.commit()
    logger.info("✅ Test database tables dropped")

@pytest.fixture(scope="function")
def db_session(test_engine) -> Generator[Session, None, None]:
    """Create a new database session for each test."""
    TestSessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=test_engine)
    session = TestSessionLocal()
    
    yield session
    
    # Rollback and close after each test
    session.rollback()
    session.close()

@pytest.fixture
def db_manager(test_engine) -> DatabaseManager:
    """Create a DatabaseManager instance for testing."""
    manager = DatabaseManager()
    manager.engine = test_engine
    manager.SessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=test_engine)
    return manager 

# =============================================
# USER FIXTURES
# =============================================

@pytest.fixture
def sample_users(db_session) -> List[User]:
    """Create sample users with different profiles."""
    users = []
    
    # User 1: Active power user
    user1 = User(
        email="maria.garcia@empresa.com",
        name="María García",
        is_verified=True,
        created_at=datetime.now() - timedelta(days=180),
        updated_at=datetime.now() - timedelta(days=2)
    )
    db_session.add(user1)
    users.append(user1)
    
    # User 2: Moderate user
    user2 = User(
        email="juan.martinez@startup.es",
        name="Juan Martínez",
        is_verified=True,
        created_at=datetime.now() - timedelta(days=90),
        updated_at=datetime.now() - timedelta(days=7)
    )
    db_session.add(user2)
    users.append(user2)
    
    # User 3: New user
    user3 = User(
        email="ana.lopez@consultoria.com",
        name="Ana López",
        is_verified=True,
        created_at=datetime.now() - timedelta(days=15),
        updated_at=datetime.now() - timedelta(days=1)
    )
    db_session.add(user3)
    users.append(user3)
    
    # User 4: Inactive/test user
    user4 = User(
        email="test.user@example.com",
        name="Test User",
        is_verified=False,
        created_at=datetime.now() - timedelta(days=365),
        updated_at=datetime.now() - timedelta(days=300)
    )
    db_session.add(user4)
    users.append(user4)
    
    db_session.commit()
    logger.info(f"✅ Created {len(users)} sample users")
    return users 

# =============================================
# EMAIL ACCOUNT FIXTURES
# =============================================

@pytest.fixture
def sample_email_accounts(db_session, sample_users, db_manager) -> List[EmailAccount]:
    """Create sample email accounts for users."""
    accounts = []
    
    # User 1 (María) - 2 email accounts
    account1 = EmailAccount(
        user_id=sample_users[0].id,
        email="maria.garcia@empresa.com",
        imap_server="imap.gmail.com",
        imap_port=993,
        smtp_server="smtp.gmail.com",
        smtp_port=587,
        encrypted_password=db_manager.encrypt_password("test_password_123"),
        is_active=True,
        created_at=datetime.now() - timedelta(days=180),
        updated_at=datetime.now() - timedelta(days=5)
    )
    db_session.add(account1)
    accounts.append(account1)
    
    account2 = EmailAccount(
        user_id=sample_users[0].id,
        email="ventas@empresa.com",
        imap_server="imap.gmail.com",
        imap_port=993,
        smtp_server="smtp.gmail.com",
        smtp_port=587,
        encrypted_password=db_manager.encrypt_password("test_password_456"),
        is_active=True,
        created_at=datetime.now() - timedelta(days=120),
        updated_at=datetime.now() - timedelta(days=3)
    )
    db_session.add(account2)
    accounts.append(account2)
    
    # User 2 (Juan) - 1 email account
    account3 = EmailAccount(
        user_id=sample_users[1].id,
        email="juan@startup.es",
        imap_server="imap.ionos.es",
        imap_port=993,
        smtp_server="smtp.ionos.es",
        smtp_port=587,
        encrypted_password=db_manager.encrypt_password("test_password_789"),
        is_active=True,
        created_at=datetime.now() - timedelta(days=90),
        updated_at=datetime.now() - timedelta(days=10)
    )
    db_session.add(account3)
    accounts.append(account3)
    
    # User 3 (Ana) - 2 email accounts (1 inactive)
    account4 = EmailAccount(
        user_id=sample_users[2].id,
        email="ana@consultoria.com",
        imap_server="imap.gmail.com",
        imap_port=993,
        smtp_server="smtp.gmail.com",
        smtp_port=587,
        encrypted_password=db_manager.encrypt_password("test_password_abc"),
        is_active=True,
        created_at=datetime.now() - timedelta(days=15),
        updated_at=datetime.now() - timedelta(days=1)
    )
    db_session.add(account4)
    accounts.append(account4)
    
    account5 = EmailAccount(
        user_id=sample_users[2].id,
        email="soporte@consultoria.com",
        imap_server="imap.outlook.com",
        imap_port=993,
        smtp_server="smtp.outlook.com",
        smtp_port=587,
        encrypted_password=db_manager.encrypt_password("test_password_xyz"),
        is_active=False,  # Inactive account
        created_at=datetime.now() - timedelta(days=15),
        updated_at=datetime.now() - timedelta(days=8)
    )
    db_session.add(account5)
    accounts.append(account5)
    
    db_session.commit()
    logger.info(f"✅ Created {len(accounts)} sample email accounts")
    return accounts 

# =============================================
# Q&A FIXTURES
# =============================================

def generate_mock_embedding(text: str, dimension: int = 1536) -> List[float]:
    """Generate a deterministic mock embedding based on text."""
    # Use hash of text to generate consistent embeddings
    seed = hash(text) % 2**32
    np.random.seed(seed)
    # Generate normalized vector
    embedding = np.random.randn(dimension)
    embedding = embedding / np.linalg.norm(embedding)
    return embedding.tolist()

@pytest.fixture
def sample_qa_data(db_session, sample_users) -> Dict[str, List]:
    """Create sample questions, variants, and answers."""
    questions = []
    variants = []
    answers = []
    
    # Q&A for User 1 (María) - Business/Sales related
    qa_data_user1 = [
        {
            "question": "¿Cuáles son sus precios y tarifas?",
            "answer": "Nuestros precios varían según el plan elegido. El plan básico comienza en 49€/mes, el profesional en 99€/mes y el empresarial en 199€/mes. Todos incluyen soporte técnico y actualizaciones.",
            "variants": [
                "¿Cuánto cuesta su servicio?",
                "¿Qué precio tiene?",
                "¿Cuáles son las tarifas mensuales?",
                "¿Tienen algún plan de precios?",
                "Me gustaría saber los costos"
            ]
        },
        {
            "question": "¿Cómo puedo programar una demo?",
            "answer": "Puede programar una demo personalizada a través de nuestro calendario en línea: www.empresa.com/demo. Las demos duran aproximadamente 30 minutos y son completamente gratuitas.",
            "variants": [
                "¿Puedo ver una demostración?",
                "Quiero agendar una demo",
                "¿Hacen demostraciones del producto?",
                "Me interesa ver cómo funciona"
            ]
        },
        {
            "question": "¿Cuál es el tiempo de implementación?",
            "answer": "La implementación típica toma entre 2-4 semanas dependiendo de la complejidad. Nuestro equipo le acompañará durante todo el proceso con formación incluida.",
            "variants": [
                "¿Cuánto tardan en implementar?",
                "¿En cuánto tiempo estará funcionando?",
                "¿Cuál es el plazo de instalación?"
            ]
        }
    ]
    
    # Q&A for User 2 (Juan) - Technical/Startup related
    qa_data_user2 = [
        {
            "question": "¿Su API es compatible con Python?",
            "answer": "Sí, nuestra API es completamente compatible con Python. Ofrecemos una librería oficial en PyPI y documentación completa en docs.startup.es/python",
            "variants": [
                "¿Puedo usar Python con su API?",
                "¿Tienen SDK para Python?",
                "¿Funciona con Python?"
            ]
        },
        {
            "question": "¿Ofrecen descuentos para startups?",
            "answer": "¡Por supuesto! Tenemos un programa especial para startups con hasta 50% de descuento el primer año. Contacte a startups@startup.es para más información.",
            "variants": [
                "¿Tienen precios especiales para startups?",
                "¿Hay descuentos para empresas nuevas?",
                "Somos una startup, ¿tienen algún programa?"
            ]
        }
    ]
    
    # Q&A for User 3 (Ana) - Consulting/Support related
    qa_data_user3 = [
        {
            "question": "¿Qué incluye el soporte técnico?",
            "answer": "El soporte técnico incluye: atención por email/chat en horario laboral, actualizaciones de seguridad, base de conocimientos y sesiones mensuales de Q&A en grupo.",
            "variants": [
                "¿Qué cubre el soporte?",
                "¿El soporte técnico qué incluye?",
                "¿Qué servicios de soporte ofrecen?"
            ]
        }
    ]
    
    # Create all Q&A data
    all_qa_data = [
        (sample_users[0], qa_data_user1),
        (sample_users[1], qa_data_user2),
        (sample_users[2], qa_data_user3)
    ]
    
    for user, qa_list in all_qa_data:
        for qa in qa_list:
            # Create question
            question = Question(
                user_id=user.id,
                original_question=qa["question"],
                created_at=datetime.now() - timedelta(days=random.randint(30, 180))
            )
            db_session.add(question)
            db_session.flush()  # Get the ID
            questions.append(question)
            
            # Create answer
            answer = Answer(
                question_id=question.id,
                answer_text=qa["answer"],
                response_instructions="professional",
                created_at=question.created_at,
                updated_at=datetime.now() - timedelta(days=random.randint(1, 30))
            )
            db_session.add(answer)
            answers.append(answer)
            
            # Create variants with embeddings
            for variant_text in qa["variants"]:
                variant = QuestionVariant(
                    question_id=question.id,
                    variant_text=variant_text,
                    embedding=generate_mock_embedding(variant_text),
                    created_at=question.created_at + timedelta(hours=random.randint(1, 24))
                )
                db_session.add(variant)
                variants.append(variant)
    
    db_session.commit()
    logger.info(f"✅ Created {len(questions)} questions, {len(variants)} variants, {len(answers)} answers")
    
    return {
        "questions": questions,
        "variants": variants,
        "answers": answers
    }

# =============================================
# AUTOMATION FIXTURES
# =============================================

@pytest.fixture
def sample_automations(db_session, sample_email_accounts, sample_qa_data) -> Dict[str, List]:
    """Create sample automations (response and forward)."""
    automations = []
    response_automations = []
    forward_automations = []
    
    questions = sample_qa_data["questions"]
    
    # Response automations for User 1 (María)
    # Link first 2 questions to email account 1
    for i, question in enumerate([q for q in questions if q.user_id == sample_email_accounts[0].user_id][:2]):
        automation = Automation(
            email_account_id=sample_email_accounts[0].id,
            type=AutomationType.RESPONSE,
            is_active=True,
            is_draft_mode=False,
            created_at=datetime.now() - timedelta(days=random.randint(20, 100)),
            updated_at=datetime.now() - timedelta(days=random.randint(1, 20))
        )
        db_session.add(automation)
        db_session.flush()
        automations.append(automation)
        
        response_auto = ResponseAutomation(
            automation_id=automation.id,
            question_id=question.id,
            tone="professional" if i == 0 else "friendly",
            custom_instructions="Incluir información de contacto al final" if i == 0 else None
        )
        db_session.add(response_auto)
        response_automations.append(response_auto)
    
    # Forward automation for User 1 (María) - account 2
    forward_auto1 = Automation(
        email_account_id=sample_email_accounts[1].id,  # ventas@empresa.com
        type=AutomationType.FORWARD,
        is_active=True,
        is_draft_mode=False,
        created_at=datetime.now() - timedelta(days=60),
        updated_at=datetime.now() - timedelta(days=5)
    )
    db_session.add(forward_auto1)
    db_session.flush()
    automations.append(forward_auto1)
    
    forward_details1 = ForwardAutomation(
        automation_id=forward_auto1.id,
        forward_to_email="logistica@empresa.com",
        description="Reenviar consultas sobre envíos, entregas y logística"
    )
    db_session.add(forward_details1)
    forward_automations.append(forward_details1)
    
    # Response automation for User 2 (Juan)
    juan_questions = [q for q in questions if q.user_id == sample_email_accounts[2].user_id]
    if juan_questions:
        automation = Automation(
            email_account_id=sample_email_accounts[2].id,
            type=AutomationType.RESPONSE,
            is_active=True,
            is_draft_mode=True,  # Draft mode enabled
            created_at=datetime.now() - timedelta(days=45),
            updated_at=datetime.now() - timedelta(days=3)
        )
        db_session.add(automation)
        db_session.flush()
        automations.append(automation)
        
        response_auto = ResponseAutomation(
            automation_id=automation.id,
            question_id=juan_questions[0].id,
            tone="casual",
            custom_instructions=None
        )
        db_session.add(response_auto)
        response_automations.append(response_auto)
    
    # Forward automation for User 3 (Ana) - but inactive
    forward_auto2 = Automation(
        email_account_id=sample_email_accounts[3].id,  # ana@consultoria.com
        type=AutomationType.FORWARD,
        is_active=False,  # Inactive
        is_draft_mode=False,
        created_at=datetime.now() - timedelta(days=10),
        updated_at=datetime.now() - timedelta(days=2)
    )
    db_session.add(forward_auto2)
    db_session.flush()
    automations.append(forward_auto2)
    
    forward_details2 = ForwardAutomation(
        automation_id=forward_auto2.id,
        forward_to_email="comercial@consultoria.com",
        description="Reenviar consultas comerciales y de presupuestos"
    )
    db_session.add(forward_details2)
    forward_automations.append(forward_details2)
    
    db_session.commit()
    logger.info(f"✅ Created {len(automations)} automations ({len(response_automations)} response, {len(forward_automations)} forward)")
    
    return {
        "automations": automations,
        "response_automations": response_automations,
        "forward_automations": forward_automations
    }

# =============================================
# STATISTICS FIXTURES
# =============================================

@pytest.fixture
def sample_statistics(db_session, sample_email_accounts, sample_qa_data) -> Dict[str, List]:
    """Create sample email processing statistics with realistic patterns."""
    email_processed_records = []
    monthly_usage_records = []
    
    # Categories for emails
    categories = ["consulta_comercial", "soporte_tecnico", "spam", "informativo", "urgente"]
    
    # Generate processed emails for the last 60 days
    now = datetime.now()
    
    for account in sample_email_accounts[:4]:  # Skip inactive account
        # Determine activity level based on account
        if account.id == sample_email_accounts[0].id:  # María's main account
            daily_avg = random.randint(15, 25)  # High volume
        elif account.id == sample_email_accounts[1].id:  # María's sales account
            daily_avg = random.randint(8, 15)   # Medium volume
        elif account.id == sample_email_accounts[2].id:  # Juan's account
            daily_avg = random.randint(5, 10)   # Medium-low volume
        else:  # Ana's account
            daily_avg = random.randint(2, 5)    # Low volume (new user)
        
        # Generate daily records for the last 60 days
        for days_ago in range(60):
            process_date = now - timedelta(days=days_ago)
            
            # Weekend adjustment (lower volume)
            if process_date.weekday() in [5, 6]:  # Saturday, Sunday
                daily_count = max(1, int(daily_avg * 0.3))
            else:
                daily_count = random.randint(
                    max(1, daily_avg - 5),
                    daily_avg + 5
                )
            
            # Generate emails for this day
            for _ in range(daily_count):
                # Determine email action
                rand = random.random()
                if rand < 0.35:  # 35% responded
                    email_responded = True
                    email_forwarded = False
                    tokens_used = random.randint(150, 400)
                    # Pick a random question from the user's Q&A
                    user_questions = [q for q in sample_qa_data["questions"] 
                                    if q.user_id == account.user_id]
                    question_id = random.choice(user_questions).id if user_questions else None
                    similarity_score = random.uniform(0.75, 0.95) if question_id else None
                elif rand < 0.50:  # 15% forwarded
                    email_responded = False
                    email_forwarded = True
                    tokens_used = random.randint(50, 150)
                    question_id = None
                    similarity_score = None
                else:  # 50% just categorized
                    email_responded = False
                    email_forwarded = False
                    tokens_used = random.randint(20, 80)
                    question_id = None
                    similarity_score = None
                
                # Create processed email record
                record = EmailProcessed(
                    email_account_id=account.id,
                    processed_at=process_date - timedelta(
                        hours=random.randint(0, 23),
                        minutes=random.randint(0, 59)
                    ),
                    email_responded=email_responded,
                    answer="Respuesta automática generada..." if email_responded else None,
                    email_forwarded=email_forwarded,
                    forwarded_to="logistica@empresa.com" if email_forwarded else None,
                    category=random.choice(categories),
                    tokens_used=tokens_used,
                    question_id=question_id,
                    similarity_score=similarity_score
                )
                db_session.add(record)
                email_processed_records.append(record)
    
    # Create monthly usage records
    for user in sample_email_accounts[:4]:
        user_id = user.user_id
        
        # Current month
        current_month_records = [
            r for r in email_processed_records 
            if r.email_account.user_id == user_id 
            and r.processed_at.month == now.month
            and r.processed_at.year == now.year
        ]
        
        if current_month_records:
            monthly_usage = UserUsageMonthly(
                user_id=user_id,
                year=now.year,
                month=now.month,
                emails_processed=len(current_month_records),
                emails_responded=len([r for r in current_month_records if r.email_responded]),
                emails_forwarded=len([r for r in current_month_records if r.email_forwarded]),
                tokens_used=sum(r.tokens_used for r in current_month_records),
                last_updated=now
            )
            db_session.add(monthly_usage)
            monthly_usage_records.append(monthly_usage)
        
        # Previous month
        prev_month = now.month - 1 if now.month > 1 else 12
        prev_year = now.year if now.month > 1 else now.year - 1
        
        prev_month_records = [
            r for r in email_processed_records 
            if r.email_account.user_id == user_id 
            and r.processed_at.month == prev_month
            and r.processed_at.year == prev_year
        ]
        
        if prev_month_records:
            monthly_usage = UserUsageMonthly(
                user_id=user_id,
                year=prev_year,
                month=prev_month,
                emails_processed=len(prev_month_records),
                emails_responded=len([r for r in prev_month_records if r.email_responded]),
                emails_forwarded=len([r for r in prev_month_records if r.email_forwarded]),
                tokens_used=sum(r.tokens_used for r in prev_month_records),
                last_updated=now - timedelta(days=30)
            )
            db_session.add(monthly_usage)
            monthly_usage_records.append(monthly_usage)
    
    db_session.commit()
    logger.info(f"✅ Created {len(email_processed_records)} email processing records")
    logger.info(f"✅ Created {len(monthly_usage_records)} monthly usage records")
    
    return {
        "email_processed": email_processed_records,
        "monthly_usage": monthly_usage_records
    }

# =============================================
# CONVENIENCE FIXTURES
# =============================================

@pytest.fixture
def complete_test_data(db_session, sample_users, sample_email_accounts, 
                      sample_qa_data, sample_automations, sample_statistics):
    """Load all test data at once for integration tests."""
    return {
        "users": sample_users,
        "email_accounts": sample_email_accounts,
        "qa_data": sample_qa_data,
        "automations": sample_automations,
        "statistics": sample_statistics
    }

@pytest.fixture
def active_user_with_data(db_session, sample_users, sample_email_accounts, 
                         sample_qa_data, sample_automations):
    """Get the most active user (María) with all her data."""
    maria = sample_users[0]
    maria_accounts = [acc for acc in sample_email_accounts if acc.user_id == maria.id]
    maria_questions = [q for q in sample_qa_data["questions"] if q.user_id == maria.id]
    maria_automations = [
        auto for auto in sample_automations["automations"] 
        if auto.email_account_id in [acc.id for acc in maria_accounts]
    ]
    
    return {
        "user": maria,
        "email_accounts": maria_accounts,
        "questions": maria_questions,
        "automations": maria_automations
    }

# =============================================
# UTILITY FUNCTIONS FOR TESTS
# =============================================

def assert_statistics_consistency(db_session, user_id: int):
    """Verify that statistics are internally consistent."""
    from sqlalchemy import func
    
    # Get monthly stats
    monthly_stats = db_session.query(UserUsageMonthly).filter_by(
        user_id=user_id,
        year=datetime.now().year,
        month=datetime.now().month
    ).first()
    
    if not monthly_stats:
        return True
    
    # Get actual processed emails
    from src.models import EmailAccount, EmailProcessed
    
    actual_count = db_session.query(func.count(EmailProcessed.id)).join(
        EmailAccount
    ).filter(
        EmailAccount.user_id == user_id,
        func.extract('year', EmailProcessed.processed_at) == monthly_stats.year,
        func.extract('month', EmailProcessed.processed_at) == monthly_stats.month
    ).scalar()
    
    assert actual_count == monthly_stats.emails_processed, \
        f"Mismatch in email count: actual={actual_count}, recorded={monthly_stats.emails_processed}"
    
    return True

def get_test_email_content(category: str = "consulta_comercial") -> dict:
    """Generate test email content based on category."""
    email_templates = {
        "consulta_comercial": {
            "subject": "Consulta sobre precios",
            "content": "Hola, me gustaría saber cuáles son sus precios y si tienen descuentos por volumen.",
            "sender": "cliente@example.com"
        },
        "soporte_tecnico": {
            "subject": "Problema con la API",
            "content": "No puedo conectar con su API desde Python. ¿Pueden ayudarme?",
            "sender": "developer@startup.com"
        },
        "logistica": {
            "subject": "Estado de mi pedido",
            "content": "Necesito saber cuándo llegará mi pedido #12345. Es urgente.",
            "sender": "comprador@empresa.es"
        }
    }
    
    return email_templates.get(category, email_templates["consulta_comercial"])