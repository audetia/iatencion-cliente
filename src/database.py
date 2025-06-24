"""
Módulo de gestión centralizada de base de datos.

Este módulo centraliza toda la configuración y gestión de la conexión
a PostgreSQL con pgvector para el sistema de automatización de emails.
"""

import os
import logging
from typing import Generator, Optional
from contextlib import contextmanager
from sqlalchemy import create_engine, text
from sqlalchemy.orm import sessionmaker, Session
from sqlalchemy.exc import SQLAlchemyError
from dotenv import load_dotenv

# Cargar variables de entorno
load_dotenv()

# Configurar logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

class DatabaseConfig:
    """
    Configuración de la base de datos.
    
    Centraliza todas las configuraciones relacionadas con la conexión
    a PostgreSQL y pgvector.
    """
    
    def __init__(self):
        self.database_url = self._get_database_url()
        self.echo = os.getenv("DB_ECHO", "False").lower() == "true"
        self.pool_size = int(os.getenv("DB_POOL_SIZE", "5"))
        self.max_overflow = int(os.getenv("DB_MAX_OVERFLOW", "10"))
        self.pool_timeout = int(os.getenv("DB_POOL_TIMEOUT", "30"))
        self.pool_recycle = int(os.getenv("DB_POOL_RECYCLE", "3600"))
    
    def _get_database_url(self) -> str:
        """
        Construye la URL de conexión a la base de datos.
        
        Returns:
            str: URL de conexión a PostgreSQL
            
        Raises:
            ValueError: Si no se puede construir la URL
        """
        # Opción 1: URL completa
        database_url = os.getenv("POSTGRES_URL")
        if database_url:
            return database_url
        
        # Opción 2: Componentes individuales
        host = os.getenv("DB_HOST")
        port = os.getenv("DB_PORT")
        database = os.getenv("DB_NAME")
        username = os.getenv("DB_USER")
        password = os.getenv("DB_PASSWORD")
        
        if not password:
            raise ValueError(
                "Se requiere DATABASE_URL o DB_PASSWORD en las variables de entorno"
            )
        
        return f"postgresql://{username}:{password}@{host}:{port}/{database}"
    

class DatabaseManager:
    """
    Gestor centralizado de base de datos.
    
    Esta clase maneja la conexión, sesiones y operaciones básicas
    con la base de datos PostgreSQL.
    """
    
    def __init__(self):
        self.config = DatabaseConfig()
        self.engine = None
        self.SessionLocal = None
        self._initialize_engine()
    
    def _initialize_engine(self) -> None:
        """
        Inicializa el engine de SQLAlchemy con la configuración.
        """
        try:
            self.engine = create_engine(
                self.config.database_url,
                echo=self.config.echo,
                pool_size=self.config.pool_size,
                max_overflow=self.config.max_overflow,
                pool_timeout=self.config.pool_timeout,
                pool_recycle=self.config.pool_recycle,
                pool_pre_ping=True  # Verifica conexiones antes de usarlas
            )
            
            # Crear factory de sesiones
            self.SessionLocal = sessionmaker(
                autocommit=False,
                autoflush=False,
                bind=self.engine
            )
            
            logger.info("✅ Engine de base de datos inicializado correctamente")
            
        except Exception as e:
            logger.error(f"❌ Error inicializando engine de base de datos: {e}")
            raise

    def get_session(self) -> Session:
        """
        Crea una nueva sesión de base de datos.
        
        Returns:
            Session: Nueva sesión de SQLAlchemy
            
        Note:
            Recuerda cerrar la sesión después de usarla.
        """
        if not self.SessionLocal:
            raise RuntimeError("DatabaseManager no está inicializado")
        
        return self.SessionLocal()
    
    @contextmanager
    def get_db_session(self) -> Generator[Session, None, None]:
        """
        Context manager para manejo automático de sesiones.
        
        Yields:
            Session: Sesión de base de datos
            
        Example:
            with db_manager.get_db_session() as db:
                users = db.query(User).all()
        """
        session = self.get_session()
        try:
            yield session
            session.commit()
        except Exception as e:
            session.rollback()
            logger.error(f"Error en sesión de base de datos: {e}")
            raise
        finally:
            session.close()

    def test_connection(self) -> bool:
        """
        Prueba la conexión a la base de datos.
        
        Returns:
            bool: True si la conexión es exitosa, False en caso contrario
        """
        try:
            with self.engine.connect() as connection:
                result = connection.execute(text("SELECT 1"))
                result.fetchone()
            logger.info("✅ Conexión a base de datos exitosa")
            return True
        except Exception as e:
            logger.error(f"❌ Error conectando a base de datos: {e}")
            return False
    
    def check_pgvector_extension(self) -> bool:
        """
        Verifica si la extensión pgvector está instalada.
        
        Returns:
            bool: True si pgvector está disponible
        """
        try:
            with self.engine.connect() as connection:
                result = connection.execute(
                    text("SELECT 1 FROM pg_extension WHERE extname = 'vector'")
                )
                has_pgvector = result.fetchone() is not None
            
            if has_pgvector:
                logger.info("✅ Extensión pgvector está disponible")
            else:
                logger.warning("⚠️  Extensión pgvector no encontrada")
            
            return has_pgvector
        except Exception as e:
            logger.error(f"❌ Error verificando pgvector: {e}")
            return False
        
    def create_tables(self, base_metadata) -> bool:
        """
        Crea todas las tablas definidas en los modelos.
        
        Args:
            base_metadata: Metadata de SQLAlchemy Base
            
        Returns:
            bool: True si las tablas se crearon exitosamente
        """
        try:
            base_metadata.create_all(bind=self.engine)
            logger.info("✅ Tablas creadas exitosamente")
            return True
        except Exception as e:
            logger.error(f"❌ Error creando tablas: {e}")
            return False
    
    def drop_tables(self, base_metadata) -> bool:
        """
        Elimina todas las tablas (¡CUIDADO en producción!).
        
        Args:
            base_metadata: Metadata de SQLAlchemy Base
            
        Returns:
            bool: True si las tablas se eliminaron exitosamente
        """
        try:
            base_metadata.drop_all(bind=self.engine)
            logger.info("⚠️  Tablas eliminadas")
            return True
        except Exception as e:
            logger.error(f"❌ Error eliminando tablas: {e}")
            return False


# Instancia global del gestor de base de datos
db_manager = DatabaseManager()

# Funciones de conveniencia para mantener compatibilidad
def get_db() -> Generator[Session, None, None]:
    """
    Generador para obtener sesión de base de datos.
    
    Yields:
        Session: Sesión de SQLAlchemy
        
    Example:
        for db in get_db():
            users = db.query(User).all()
            break
    """
    with db_manager.get_db_session() as session:
        yield session

def test_database_connection() -> bool:
    """
    Función de conveniencia para probar la conexión.
    
    Returns:
        bool: True si la conexión es exitosa
    """
    return db_manager.test_connection()

def initialize_database():
    """
    Inicializa la base de datos y verifica extensiones.
    """
    logger.info("🚀 Inicializando base de datos...")
    
    if not db_manager.test_connection():
        raise RuntimeError("No se pudo conectar a la base de datos")
    
    if not db_manager.check_pgvector_extension():
        logger.warning("⚠️  pgvector no está disponible. Algunas funciones pueden no funcionar.")
    
    logger.info("✅ Base de datos inicializada correctamente")