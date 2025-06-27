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
from cryptography.fernet import Fernet
import base64

# Cargar variables de entorno
load_dotenv()

# Importar modelos (lazy loading para evitar dependencias circulares)
def get_models():
    """Importación lazy de modelos para evitar dependencias circulares."""
    from .models.user import User
    from .models.email_account import EmailAccount
    return User, EmailAccount

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
        self._encryption_key = self._get_encryption_key()
        self._cipher_suite = Fernet(self._encryption_key)
        self._initialize_engine()
    
    def _get_encryption_key(self) -> bytes:
        """
        Obtiene la clave de encriptación para contraseñas IMAP.
        
        Returns:
            bytes: Clave de encriptación Fernet
            
        Raises:
            RuntimeError: Si ENCRYPTION_KEY no está configurada o es inválida
            
        Note:
            La clave DEBE estar configurada en la variable de entorno ENCRYPTION_KEY.
            Para generar una nueva clave, usa: python -c "from cryptography.fernet import Fernet; print(Fernet.generate_key().decode())"
        """
        encryption_key = os.getenv("ENCRYPTION_KEY")
        
        if not encryption_key:
            logger.error("❌ ENCRYPTION_KEY no está configurada")
            logger.error("🔑 Para generar una nueva clave, ejecuta:")
            logger.error("   python -c \"from cryptography.fernet import Fernet; print('ENCRYPTION_KEY=' + Fernet.generate_key().decode())\"")
            logger.error("📝 Luego añade la clave generada a tu archivo .env")
            raise RuntimeError(
                "ENCRYPTION_KEY es requerida. "
                "Configura esta variable de entorno antes de ejecutar la aplicación. "
                "Usa el comando mostrado arriba para generar una clave válida."
            )
        
        try:
            # Validar que la clave es válida para Fernet
            from cryptography.fernet import Fernet
            test_cipher = Fernet(encryption_key.encode('utf-8'))
            logger.info("✅ ENCRYPTION_KEY validada correctamente")
            return encryption_key.encode('utf-8')
        except Exception as e:
            logger.error(f"❌ ENCRYPTION_KEY no es válida: {e}")
            logger.error("🔑 Para generar una nueva clave válida, ejecuta:")
            logger.error("   python -c \"from cryptography.fernet import Fernet; print('ENCRYPTION_KEY=' + Fernet.generate_key().decode())\"")
            raise RuntimeError(f"ENCRYPTION_KEY inválida: {str(e)}")
    
    def encrypt_password(self, password: str) -> str:
        """
        Encripta una contraseña IMAP/SMTP.
        
        Args:
            password (str): Contraseña en texto plano
            
        Returns:
            str: Contraseña encriptada en base64
            
        Raises:
            ValueError: Si la contraseña está vacía
            RuntimeError: Si hay error en la encriptación
        """
        if not password or not password.strip():
            raise ValueError("La contraseña no puede estar vacía")
        
        try:
            encrypted_bytes = self._cipher_suite.encrypt(password.encode('utf-8'))
            return base64.urlsafe_b64encode(encrypted_bytes).decode('utf-8')
        except Exception as e:
            logger.error(f"❌ Error encriptando contraseña: {e}")
            raise RuntimeError("Error en la encriptación de la contraseña")
    
    def decrypt_password(self, encrypted_password: str) -> str:
        """
        Desencripta una contraseña IMAP/SMTP.
        
        Args:
            encrypted_password (str): Contraseña encriptada en base64
            
        Returns:
            str: Contraseña en texto plano
            
        Raises:
            ValueError: Si la contraseña encriptada está vacía o es inválida
            RuntimeError: Si hay error en la desencriptación
        """
        if not encrypted_password or not encrypted_password.strip():
            raise ValueError("La contraseña encriptada no puede estar vacía")
        
        try:
            encrypted_bytes = base64.urlsafe_b64decode(encrypted_password.encode('utf-8'))
            decrypted_bytes = self._cipher_suite.decrypt(encrypted_bytes)
            return decrypted_bytes.decode('utf-8')
        except Exception as e:
            logger.error(f"❌ Error desencriptando contraseña: {e}")
            raise RuntimeError("Error en la desencriptación de la contraseña")
    
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

    # =============================================================================
    # MÉTODOS DE GESTIÓN DE USUARIOS
    # =============================================================================

    def create_user(self, email: str, name: str) -> dict:
        """
        Crea un nuevo usuario en la base de datos.
        
        Args:
            email (str): Dirección de email del usuario (debe ser única)
            name (str): Nombre completo del usuario
            
        Returns:
            dict: Información del usuario creado con éxito/error
            
        Raises:
            ValueError: Si el email ya existe o los parámetros son inválidos
            RuntimeError: Si hay error en la base de datos
        """
        if not email or not email.strip():
            raise ValueError("El email no puede estar vacío")
        
        if not name or not name.strip():
            raise ValueError("El nombre no puede estar vacío")
        
        # Validar formato básico de email
        email_parts = email.split("@")
        if len(email_parts) != 2 or not email_parts[0] or not email_parts[1] or "." not in email_parts[1]:
            raise ValueError("Formato de email inválido")
        
        try:
            with self.get_db_session() as db:
                from .models.user import User
                
                # Usar el método del modelo para crear usuario
                new_user = User.create(db, email.lower().strip(), name.strip())
                
                user_data = new_user.to_dict()
                
                logger.info(f"✅ Usuario creado exitosamente: {email} (ID: {new_user.id})")
                return {
                    'success': True,
                    'user': user_data,
                    'message': 'Usuario creado exitosamente'
                }
                
        except ValueError:
            raise  # Re-lanzar errores de validación del modelo
        except Exception as e:
            logger.error(f"❌ Error creando usuario {email}: {e}")
            raise RuntimeError(f"Error en la base de datos: {str(e)}")

    def get_user_by_email(self, email: str) -> Optional[dict]:
        """
        Busca un usuario por su dirección de email.
        
        Args:
            email (str): Dirección de email a buscar
            
        Returns:
            dict | None: Información del usuario encontrado o None si no existe
            
        Raises:
            ValueError: Si el email es inválido
            RuntimeError: Si hay error en la base de datos
        """
        if not email or not email.strip():
            raise ValueError("El email no puede estar vacío")
        
        try:
            with self.get_db_session() as db:
                from .models.user import User
                
                # Usar el método del modelo para buscar usuario
                user = User.get_by_email(db, email.lower().strip())
                
                if user:
                    logger.info(f"✅ Usuario encontrado: {email} (ID: {user.id})")
                    return user.to_dict()
                else:
                    logger.info(f"ℹ️  Usuario no encontrado: {email}")
                    return None
                    
        except ValueError:
            raise  # Re-lanzar errores de validación
        except Exception as e:
            logger.error(f"❌ Error buscando usuario por email {email}: {e}")
            raise RuntimeError(f"Error en la base de datos: {str(e)}")

    def get_user_by_id(self, user_id: int) -> Optional[dict]:
        """
        Busca un usuario por su ID.
        
        Args:
            user_id (int): ID del usuario a buscar
            
        Returns:
            dict | None: Información del usuario encontrado o None si no existe
            
        Raises:
            ValueError: Si el user_id es inválido
            RuntimeError: Si hay error en la base de datos
        """
        if not isinstance(user_id, int) or user_id <= 0:
            raise ValueError("El ID del usuario debe ser un entero positivo")
        
        try:
            with self.get_db_session() as db:
                from .models.user import User
                
                # Usar el método del modelo para buscar usuario
                user = User.get_by_id(db, user_id)
                
                if user:
                    logger.info(f"✅ Usuario encontrado: ID {user_id} ({user.email})")
                    return user.to_dict()
                else:
                    logger.info(f"ℹ️  Usuario no encontrado: ID {user_id}")
                    return None
                    
        except ValueError:
            raise  # Re-lanzar errores de validación
        except Exception as e:
            logger.error(f"❌ Error buscando usuario por ID {user_id}: {e}")
            raise RuntimeError(f"Error en la base de datos: {str(e)}")

    def update_user(self, user_id: int, **kwargs) -> dict:
        """
        Actualiza los datos de un usuario existente.
        
        Args:
            user_id (int): ID del usuario a actualizar
            **kwargs: Campos a actualizar (name, email, is_verified)
            
        Returns:
            dict: Información del usuario actualizado con éxito/error
            
        Raises:
            ValueError: Si el user_id es inválido o los campos no son válidos
            RuntimeError: Si hay error en la base de datos o el usuario no existe
        """
        if not isinstance(user_id, int) or user_id <= 0:
            raise ValueError("El ID del usuario debe ser un entero positivo")
        
        # Campos permitidos para actualización
        allowed_fields = {'name', 'email', 'is_verified'}
        
        # Filtrar campos válidos
        update_data = {k: v for k, v in kwargs.items() if k in allowed_fields}
        
        if not update_data:
            raise ValueError(f"No se proporcionaron campos válidos para actualizar. Campos permitidos: {allowed_fields}")
        
        # Validar campos específicos
        if 'email' in update_data:
            email = update_data['email']
            if not email or not email.strip():
                raise ValueError("El email no puede estar vacío")
            if "@" not in email or "." not in email.split("@")[-1]:
                raise ValueError("Formato de email inválido")
            update_data['email'] = email.lower().strip()
        
        if 'name' in update_data:
            name = update_data['name']
            if not name or not name.strip():
                raise ValueError("El nombre no puede estar vacío")
            update_data['name'] = name.strip()
        
        try:
            with self.get_db_session() as db:
                from .models.user import User
                
                # Usar el método del modelo para buscar usuario
                user = User.get_by_id(db, user_id)
                
                if not user:
                    raise RuntimeError(f"Usuario con ID {user_id} no encontrado")
                
                # Verificar email duplicado si se está actualizando
                if 'email' in update_data and update_data['email'] != user.email:
                    existing_user = User.get_by_email(db, update_data['email'])
                    if existing_user:
                        raise ValueError(f"Ya existe un usuario con el email: {update_data['email']}")
                
                # Usar el método del modelo para actualizar
                user.update(db, **update_data)
                
                logger.info(f"✅ Usuario actualizado exitosamente: ID {user_id}")
                logger.info(f"   Cambios: {update_data}")
                
                return {
                    'success': True,
                    'user': user.to_dict(),
                    'updated_fields': list(update_data.keys()),
                    'message': 'Usuario actualizado exitosamente'
                }
                
        except ValueError:
            raise  # Re-lanzar errores de validación
        except RuntimeError:
            raise  # Re-lanzar errores de usuario no encontrado
        except Exception as e:
            logger.error(f"❌ Error actualizando usuario ID {user_id}: {e}")
            raise RuntimeError(f"Error en la base de datos: {str(e)}")

    def verify_user(self, user_id: int) -> dict:
        """
        Marca un usuario como verificado.
        
        Este método se utiliza después de que el usuario verifica
        su email durante el proceso de registro.
        
        Args:
            user_id (int): ID del usuario a verificar
            
        Returns:
            dict: Información del usuario verificado con éxito/error
            
        Raises:
            ValueError: Si el user_id es inválido
            RuntimeError: Si hay error en la base de datos o el usuario no existe
        """
        if not isinstance(user_id, int) or user_id <= 0:
            raise ValueError("El ID del usuario debe ser un entero positivo")
        
        try:
            with self.get_db_session() as db:
                from .models.user import User
                
                # Usar el método del modelo para buscar usuario
                user = User.get_by_id(db, user_id)
                
                if not user:
                    raise RuntimeError(f"Usuario con ID {user_id} no encontrado")
                
                # Verificar si ya estaba verificado
                was_already_verified = user.is_verified
                
                # Usar el método del modelo para verificar
                user.verify()
                db.flush()
                
                if was_already_verified:
                    logger.info(f"ℹ️  Usuario ya estaba verificado: ID {user_id} ({user.email})")
                    message = 'Usuario ya estaba verificado'
                else:
                    logger.info(f"✅ Usuario verificado exitosamente: ID {user_id} ({user.email})")
                    message = 'Usuario verificado exitosamente'
                
                return {
                    'success': True,
                    'user': user.to_dict(),
                    'was_already_verified': was_already_verified,
                    'message': message
                }
                
        except ValueError:
            raise  # Re-lanzar errores de validación
        except RuntimeError:
            raise  # Re-lanzar errores de usuario no encontrado
        except Exception as e:
            logger.error(f"❌ Error verificando usuario ID {user_id}: {e}")
            raise RuntimeError(f"Error en la base de datos: {str(e)}")

    # =============================================================================
    # MÉTODOS DE GESTIÓN DE CUENTAS DE EMAIL
    # =============================================================================

    def add_email_account(self, user_id: int, email: str, imap_config: dict, smtp_config: dict, password: str) -> dict:
        """
        Añade una nueva cuenta de email para un usuario.
        
        Args:
            user_id (int): ID del usuario propietario
            email (str): Dirección de email de la cuenta
            imap_config (dict): Configuración IMAP {'server': str, 'port': int}
            smtp_config (dict): Configuración SMTP {'server': str, 'port': int}
            password (str): Contraseña en texto plano (se encriptará)
            
        Returns:
            dict: Información de la cuenta creada con éxito/error
            
        Raises:
            ValueError: Si los parámetros son inválidos o el usuario no existe
            RuntimeError: Si hay error en la base de datos
        """
        # Validaciones de entrada
        if not isinstance(user_id, int) or user_id <= 0:
            raise ValueError("El ID del usuario debe ser un entero positivo")
        
        if not email or not email.strip():
            raise ValueError("El email no puede estar vacío")
        
        if "@" not in email or "." not in email.split("@")[-1]:
            raise ValueError("Formato de email inválido")
        
        if not password or not password.strip():
            raise ValueError("La contraseña no puede estar vacía")
        
        # Validar configuración IMAP
        if not isinstance(imap_config, dict):
            raise ValueError("imap_config debe ser un diccionario")
        
        required_imap_fields = {'server', 'port'}
        if not all(field in imap_config for field in required_imap_fields):
            raise ValueError(f"imap_config debe contener: {required_imap_fields}")
        
        if not isinstance(imap_config['port'], int) or not (1 <= imap_config['port'] <= 65535):
            raise ValueError("Puerto IMAP debe ser un entero entre 1 y 65535")
        
        # Validar configuración SMTP
        if not isinstance(smtp_config, dict):
            raise ValueError("smtp_config debe ser un diccionario")
        
        required_smtp_fields = {'server', 'port'}
        if not all(field in smtp_config for field in required_smtp_fields):
            raise ValueError(f"smtp_config debe contener: {required_smtp_fields}")
        
        if not isinstance(smtp_config['port'], int) or not (1 <= smtp_config['port'] <= 65535):
            raise ValueError("Puerto SMTP debe ser un entero entre 1 y 65535")
        
        try:
            with self.get_db_session() as db:
                from .models.user import User
                from .models.email_account import EmailAccount
                
                # Verificar que el usuario existe
                user = User.get_by_id(db, user_id)
                if not user:
                    raise ValueError(f"Usuario con ID {user_id} no encontrado")
                
                # Encriptar contraseña
                encrypted_password = self.encrypt_password(password)
                
                # Usar el método del modelo para crear la cuenta
                new_account = EmailAccount.create(
                    db_session=db,
                    user_id=user_id,
                    email=email.lower().strip(),
                    imap_server=imap_config['server'].strip(),
                    imap_port=imap_config['port'],
                    smtp_server=smtp_config['server'].strip(),
                    smtp_port=smtp_config['port'],
                    encrypted_password=encrypted_password
                )
                
                account_data = new_account.to_dict()
                
                logger.info(f"✅ Cuenta de email añadida exitosamente: {email} para usuario {user_id} (ID: {new_account.id})")
                return {
                    'success': True,
                    'account': account_data,
                    'message': 'Cuenta de email añadida exitosamente'
                }
                
        except ValueError:
            raise  # Re-lanzar errores de validación
        except Exception as e:
            logger.error(f"❌ Error añadiendo cuenta de email {email} para usuario {user_id}: {e}")
            raise RuntimeError(f"Error en la base de datos: {str(e)}")

    def get_user_email_accounts(self, user_id: int) -> dict:
        """
        Obtiene todas las cuentas de email de un usuario.
        
        Args:
            user_id (int): ID del usuario
            
        Returns:
            dict: Lista de cuentas del usuario con información adicional
            
        Raises:
            ValueError: Si el user_id es inválido
            RuntimeError: Si hay error en la base de datos
        """
        if not isinstance(user_id, int) or user_id <= 0:
            raise ValueError("El ID del usuario debe ser un entero positivo")
        
        try:
            with self.get_db_session() as db:
                from .models.user import User
                from .models.email_account import EmailAccount
                
                # Verificar que el usuario existe
                user = User.get_by_id(db, user_id)
                if not user:
                    raise ValueError(f"Usuario con ID {user_id} no encontrado")
                
                # Usar el método del modelo para obtener cuentas
                accounts = EmailAccount.get_by_user(db, user_id)
                active_accounts = EmailAccount.get_active_by_user(db, user_id)
                
                accounts_data = [account.to_dict() for account in accounts]
                
                logger.info(f"✅ Obtenidas {len(accounts)} cuentas para usuario {user_id}")
                return {
                    'success': True,
                    'user_id': user_id,
                    'user_name': user.name,
                    'user_email': user.email,
                    'accounts': accounts_data,
                    'summary': {
                        'total_accounts': len(accounts),
                        'active_accounts': len(active_accounts),
                        'inactive_accounts': len(accounts) - len(active_accounts)
                    },
                    'message': f'Se encontraron {len(accounts)} cuentas de email'
                }
                
        except ValueError:
            raise  # Re-lanzar errores de validación
        except Exception as e:
            logger.error(f"❌ Error obteniendo cuentas de email para usuario {user_id}: {e}")
            raise RuntimeError(f"Error en la base de datos: {str(e)}")

    def update_email_account(self, account_id: int, **kwargs) -> dict:
        """
        Actualiza la configuración de una cuenta de email.
        
        Args:
            account_id (int): ID de la cuenta a actualizar
            **kwargs: Campos a actualizar (email, imap_server, imap_port, smtp_server, smtp_port, is_active, password)
            
        Returns:
            dict: Información de la cuenta actualizada con éxito/error
            
        Raises:
            ValueError: Si el account_id es inválido o los campos no son válidos
            RuntimeError: Si hay error en la base de datos o la cuenta no existe
        """
        if not isinstance(account_id, int) or account_id <= 0:
            raise ValueError("El ID de la cuenta debe ser un entero positivo")
        
        # Campos permitidos para actualización
        allowed_fields = {
            'email', 'imap_server', 'imap_port', 'smtp_server', 
            'smtp_port', 'is_active', 'password'
        }
        
        # Filtrar campos válidos (excluyendo password que se maneja especialmente)
        update_data = {k: v for k, v in kwargs.items() if k in allowed_fields and k != 'password'}
        
        if not update_data and 'password' not in kwargs:
            raise ValueError(f"No se proporcionaron campos válidos para actualizar. Campos permitidos: {allowed_fields}")
        
        # Validar campos específicos
        if 'email' in update_data:
            email = update_data['email']
            if not email or not email.strip():
                raise ValueError("El email no puede estar vacío")
            if "@" not in email or "." not in email.split("@")[-1]:
                raise ValueError("Formato de email inválido")
            update_data['email'] = email.lower().strip()
        
        if 'imap_port' in update_data:
            if not isinstance(update_data['imap_port'], int) or not (1 <= update_data['imap_port'] <= 65535):
                raise ValueError("Puerto IMAP debe ser un entero entre 1 y 65535")
        
        if 'smtp_port' in update_data:
            if not isinstance(update_data['smtp_port'], int) or not (1 <= update_data['smtp_port'] <= 65535):
                raise ValueError("Puerto SMTP debe ser un entero entre 1 y 65535")
        
        if 'imap_server' in update_data and not update_data['imap_server'].strip():
            raise ValueError("El servidor IMAP no puede estar vacío")
        
        if 'smtp_server' in update_data and not update_data['smtp_server'].strip():
            raise ValueError("El servidor SMTP no puede estar vacío")
        
        try:
            with self.get_db_session() as db:
                from .models.email_account import EmailAccount
                
                # Usar el método del modelo para buscar la cuenta
                account = EmailAccount.get_by_id(db, account_id)
                
                if not account:
                    raise RuntimeError(f"Cuenta de email con ID {account_id} no encontrada")
                
                # Manejar actualización de contraseña por separado
                if 'password' in kwargs:
                    password = kwargs['password']
                    if not password or not password.strip():
                        raise ValueError("La contraseña no puede estar vacía")
                    
                    # Encriptar nueva contraseña
                    encrypted_password = self.encrypt_password(password)
                    account.refresh_credentials(db, encrypted_password)
                    logger.info(f"🔐 Contraseña actualizada para cuenta ID {account_id}")
                
                # Actualizar otros campos si existen
                if update_data:
                    # Usar el método del modelo para actualizar
                    account.update(db, **update_data)
                
                updated_fields = list(update_data.keys())
                if 'password' in kwargs:
                    updated_fields.append('password')
                
                logger.info(f"✅ Cuenta de email actualizada exitosamente: ID {account_id}")
                logger.info(f"   Cambios: {updated_fields}")
                
                return {
                    'success': True,
                    'account': account.to_dict(),
                    'updated_fields': updated_fields,
                    'message': 'Cuenta de email actualizada exitosamente'
                }
                
        except ValueError:
            raise  # Re-lanzar errores de validación
        except RuntimeError:
            raise  # Re-lanzar errores de cuenta no encontrada
        except Exception as e:
            logger.error(f"❌ Error actualizando cuenta de email ID {account_id}: {e}")
            raise RuntimeError(f"Error en la base de datos: {str(e)}")

    def delete_email_account(self, account_id: int) -> dict:
        """
        Elimina una cuenta de email de la base de datos.
        
        Args:
            account_id (int): ID de la cuenta a eliminar
            
        Returns:
            dict: Información de la eliminación con éxito/error
            
        Raises:
            ValueError: Si el account_id es inválido
            RuntimeError: Si hay error en la base de datos o la cuenta no existe
        """
        if not isinstance(account_id, int) or account_id <= 0:
            raise ValueError("El ID de la cuenta debe ser un entero positivo")
        
        try:
            with self.get_db_session() as db:
                from .models.email_account import EmailAccount
                
                # Usar el método del modelo para buscar la cuenta
                account = EmailAccount.get_by_id(db, account_id)
                
                if not account:
                    raise RuntimeError(f"Cuenta de email con ID {account_id} no encontrada")
                
                # Guardar información para el log
                account_email = account.email
                user_id = account.user_id
                
                # Usar el método del modelo para eliminar
                account.delete(db)
                
                logger.info(f"✅ Cuenta de email eliminada exitosamente: {account_email} (ID: {account_id}, Usuario: {user_id})")
                return {
                    'success': True,
                    'deleted_account': {
                        'id': account_id,
                        'email': account_email,
                        'user_id': user_id
                    },
                    'message': 'Cuenta de email eliminada exitosamente'
                }
                
        except ValueError:
            raise  # Re-lanzar errores de validación
        except RuntimeError:
            raise  # Re-lanzar errores de cuenta no encontrada
        except Exception as e:
            logger.error(f"❌ Error eliminando cuenta de email ID {account_id}: {e}")
            raise RuntimeError(f"Error en la base de datos: {str(e)}")

    def get_email_account_credentials(self, account_id: int) -> dict:
        """
        Obtiene las credenciales desencriptadas de una cuenta de email.
        
        IMPORTANTE: Este método retorna credenciales sensibles.
        Solo debe usarse cuando sea absolutamente necesario para conexiones.
        
        Args:
            account_id (int): ID de la cuenta
            
        Returns:
            dict: Credenciales desencriptadas y configuración completa
            
        Raises:
            ValueError: Si el account_id es inválido
            RuntimeError: Si hay error en la base de datos o la cuenta no existe
        """
        if not isinstance(account_id, int) or account_id <= 0:
            raise ValueError("El ID de la cuenta debe ser un entero positivo")
        
        try:
            with self.get_db_session() as db:
                from .models.email_account import EmailAccount
                
                # Usar el método del modelo para buscar la cuenta
                account = EmailAccount.get_by_id(db, account_id)
                
                if not account:
                    raise RuntimeError(f"Cuenta de email con ID {account_id} no encontrada")
                
                # Desencriptar contraseña
                decrypted_password = self.decrypt_password(account.encrypted_password)
                
                # Preparar configuración completa para conexión
                credentials = {
                    'account_id': account.id,
                    'email': account.email,
                    'password': decrypted_password,
                    'imap_config': {
                        'server': account.imap_server,
                        'port': account.imap_port,
                        'email': account.email
                    },
                    'smtp_config': {
                        'server': account.smtp_server,
                        'port': account.smtp_port,
                        'email': account.email
                    },
                    'auth_type': account.auth_type,
                    'is_oauth2': account.is_oauth2,
                    'is_active': account.is_active,
                    'health_status': account.health_status
                }
                
                # Añadir tokens OAuth2 si aplica
                if account.is_oauth2:
                    credentials['oauth2_token'] = account.oauth2_token
                    credentials['oauth2_refresh_token'] = account.oauth2_refresh_token
                
                logger.info(f"🔐 Credenciales obtenidas para cuenta ID {account_id} ({account.email})")
                return {
                    'success': True,
                    'credentials': credentials,
                    'message': 'Credenciales obtenidas exitosamente'
                }
                
        except ValueError:
            raise  # Re-lanzar errores de validación
        except RuntimeError:
            raise  # Re-lanzar errores de cuenta no encontrada
        except Exception as e:
            logger.error(f"❌ Error obteniendo credenciales para cuenta ID {account_id}: {e}")
            raise RuntimeError(f"Error en la base de datos: {str(e)}")

    # =============================================================================
    # MÉTODOS DE GESTIÓN DE Q&A (PREGUNTAS Y RESPUESTAS)
    # =============================================================================

    def create_question(self, user_id: int, original_question: str) -> dict:
        """
        Crea una nueva pregunta original en la base de datos.
        
        Automáticamente añade la pregunta original como una variante con embedding
        para facilitar las búsquedas semánticas.
        
        Args:
            user_id (int): ID del usuario que crea la pregunta
            original_question (str): Texto de la pregunta original
            
        Returns:
            dict: Información de la pregunta creada con éxito/error
            
        Raises:
            ValueError: Si los parámetros son inválidos o el usuario no existe
            RuntimeError: Si hay error en la base de datos o generación de embeddings
        """
        # Validaciones de entrada
        if not isinstance(user_id, int) or user_id <= 0:
            raise ValueError("El ID del usuario debe ser un entero positivo")
        
        if not original_question or not original_question.strip():
            raise ValueError("La pregunta original no puede estar vacía")
        
        # Validar longitud razonable
        question_text = original_question.strip()
        if len(question_text) > 1000:
            raise ValueError("La pregunta no puede exceder 1000 caracteres")
        
        if len(question_text) < 5:
            raise ValueError("La pregunta debe tener al menos 5 caracteres")
        
        try:
            with self.get_db_session() as db:
                from .models.user import User
                from .models.qa import Question
                
                # Verificar que el usuario existe
                user = User.get_by_id(db, user_id)
                if not user:
                    raise ValueError(f"Usuario con ID {user_id} no encontrado")
                
                # Usar el método del modelo para crear la pregunta
                # Esto automáticamente crea la variante original con embedding
                new_question = Question.create(db, user_id, question_text)
                
                question_data = new_question.to_dict()
                
                logger.info(f"✅ Pregunta creada exitosamente: ID {new_question.id} para usuario {user_id}")
                logger.info(f"   Pregunta: '{question_text[:100]}{'...' if len(question_text) > 100 else ''}'")
                
                return {
                    'success': True,
                    'question': question_data,
                    'message': 'Pregunta creada exitosamente'
                }
                
        except ValueError:
            raise  # Re-lanzar errores de validación
        except Exception as e:
            logger.error(f"❌ Error creando pregunta para usuario {user_id}: {e}")
            raise RuntimeError(f"Error en la base de datos: {str(e)}")

    def create_question_with_variants(self, user_id: int, original_question: str, 
                                    generate_variants: bool = True, variant_count: int = 5) -> dict:
        """
        Crea una nueva pregunta con variantes generadas automáticamente.
        
        Este método está diseñado para el flujo de frontend donde el usuario
        quiere ver variantes sugeridas para aprobar, editar o eliminar.
        
        Args:
            user_id (int): ID del usuario que crea la pregunta
            original_question (str): Texto de la pregunta original
            generate_variants (bool): Si generar variantes automáticamente
            variant_count (int): Número de variantes a generar (máximo 10)
            
        Returns:
            dict: Información de la pregunta creada con variantes y estadísticas
            
        Raises:
            ValueError: Si los parámetros son inválidos o el usuario no existe
            RuntimeError: Si hay error en la base de datos o generación de embeddings
        """
        # Validaciones de entrada
        if not isinstance(user_id, int) or user_id <= 0:
            raise ValueError("El ID del usuario debe ser un entero positivo")
        
        if not original_question or not original_question.strip():
            raise ValueError("La pregunta original no puede estar vacía")
        
        # Validar longitud razonable
        question_text = original_question.strip()
        if len(question_text) > 1000:
            raise ValueError("La pregunta no puede exceder 1000 caracteres")
        
        if len(question_text) < 5:
            raise ValueError("La pregunta debe tener al menos 5 caracteres")
        
        if variant_count < 0 or variant_count > 10:
            raise ValueError("El número de variantes debe estar entre 0 y 10")
        
        try:
            with self.get_db_session() as db:
                from .models.user import User
                from .models.qa import Question
                
                # Verificar que el usuario existe
                user = User.get_by_id(db, user_id)
                if not user:
                    raise ValueError(f"Usuario con ID {user_id} no encontrado")
                
                # Usar el método del modelo para crear la pregunta con variantes
                result = Question.create_with_variants(
                    db, user_id, question_text, generate_variants, variant_count
                )
                
                # Preparar respuesta para el frontend
                question_data = result['question'].to_dict()
                original_variant_data = result['original_variant'].to_dict() if result['original_variant'] else None
                generated_variants_data = [v.to_dict() for v in result['generated_variants']]
                
                logger.info(f"✅ Pregunta con variantes creada exitosamente: ID {result['question'].id} para usuario {user_id}")
                logger.info(f"   Pregunta: '{question_text[:100]}{'...' if len(question_text) > 100 else ''}'")
                logger.info(f"   Variantes generadas: {result['generation_stats']['successful']}/{result['generation_stats']['requested']}")
                
                return {
                    'success': True,
                    'question': question_data,
                    'original_variant': original_variant_data,
                    'generated_variants': generated_variants_data,
                    'total_variants': result['total_variants'],
                    'generation_stats': result['generation_stats'],
                    'message': f'Pregunta creada con {result["total_variants"]} variantes'
                }
                
        except ValueError:
            raise  # Re-lanzar errores de validación
        except Exception as e:
            logger.error(f"❌ Error creando pregunta con variantes para usuario {user_id}: {e}")
            raise RuntimeError(f"Error en la base de datos: {str(e)}")

    def add_question_variant(self, question_id: int, variant_text: str, embedding: list = None) -> dict:
        """
        Añade una variante a una pregunta existente con su embedding.
        
        Si no se proporciona embedding, se genera automáticamente.
        
        Args:
            question_id (int): ID de la pregunta original
            variant_text (str): Texto de la variante
            embedding (list, optional): Embedding pre-calculado, si no se proporciona se genera
            
        Returns:
            dict: Información de la variante creada con éxito/error
            
        Raises:
            ValueError: Si los parámetros son inválidos o la pregunta no existe
            RuntimeError: Si hay error en la base de datos o generación de embeddings
        """
        # Validaciones de entrada
        if not isinstance(question_id, int) or question_id <= 0:
            raise ValueError("El ID de la pregunta debe ser un entero positivo")
        
        if not variant_text or not variant_text.strip():
            raise ValueError("El texto de la variante no puede estar vacío")
        
        # Validar longitud razonable
        variant_text = variant_text.strip()
        if len(variant_text) > 1000:
            raise ValueError("La variante no puede exceder 1000 caracteres")
        
        if len(variant_text) < 5:
            raise ValueError("La variante debe tener al menos 5 caracteres")
        
        # Validar embedding si se proporciona
        if embedding is not None:
            if not isinstance(embedding, list):
                raise ValueError("El embedding debe ser una lista de números")
            
            if len(embedding) != 1536:  # Dimensionalidad esperada para Google embeddings
                raise ValueError(f"El embedding debe tener 1536 dimensiones, recibido: {len(embedding)}")
            
            if not all(isinstance(x, (int, float)) for x in embedding):
                raise ValueError("Todos los valores del embedding deben ser números")
        
        try:
            with self.get_db_session() as db:
                from .models.qa import Question, QuestionVariant
                
                # Verificar que la pregunta existe
                question = Question.get_by_id(db, question_id)
                if not question:
                    raise ValueError(f"Pregunta con ID {question_id} no encontrada")
                
                # Crear la variante
                if embedding is not None:
                    # Crear variante con embedding proporcionado
                    new_variant = QuestionVariant(
                        question_id=question_id,
                        variant_text=variant_text,
                        embedding=embedding
                    )
                    db.add(new_variant)
                    db.flush()
                else:
                    # Usar el método del modelo que genera embedding automáticamente
                    new_variant = QuestionVariant.create(db, question_id, variant_text)
                
                # Validar calidad de la variante (diversidad)
                quality_check = new_variant.validate_variant_quality(db, min_diversity=0.15)
                if not quality_check['is_valid']:
                    logger.warning(f"⚠️  Variante con baja diversidad: {quality_check['error']}")
                    # No fallar, pero advertir
                
                variant_data = new_variant.to_dict()
                
                logger.info(f"✅ Variante añadida exitosamente: ID {new_variant.id} para pregunta {question_id}")
                logger.info(f"   Variante: '{variant_text[:100]}{'...' if len(variant_text) > 100 else ''}'")
                logger.info(f"   Diversidad: {quality_check.get('diversity_score', 'N/A'):.3f}")
                
                return {
                    'success': True,
                    'variant': variant_data,
                    'quality_check': quality_check,
                    'message': 'Variante añadida exitosamente'
                }
                
        except ValueError:
            raise  # Re-lanzar errores de validación
        except Exception as e:
            logger.error(f"❌ Error añadiendo variante a pregunta {question_id}: {e}")
            raise RuntimeError(f"Error en la base de datos: {str(e)}")

    def create_answer(self, question_id: int, response_text: str, response_instructions: str = None) -> dict:
        """
        Crea una respuesta para una pregunta existente.
        
        Args:
            question_id (int): ID de la pregunta
            response_text (str): Texto de la respuesta
            response_instructions (str, optional): Instrucciones adicionales para la respuesta
            
        Returns:
            dict: Información de la respuesta creada con éxito/error
            
        Raises:
            ValueError: Si los parámetros son inválidos, la pregunta no existe, o ya tiene respuesta
            RuntimeError: Si hay error en la base de datos
        """
        # Validaciones de entrada
        if not isinstance(question_id, int) or question_id <= 0:
            raise ValueError("El ID de la pregunta debe ser un entero positivo")
        
        if not response_text or not response_text.strip():
            raise ValueError("El texto de la respuesta no puede estar vacío")
        
        # Validar longitud razonable
        response_text = response_text.strip()
        if len(response_text) > 5000:
            raise ValueError("La respuesta no puede exceder 5000 caracteres")
        
        if len(response_text) < 10:
            raise ValueError("La respuesta debe tener al menos 10 caracteres")
        
        # Validar instrucciones si se proporcionan
        if response_instructions is not None:
            response_instructions = response_instructions.strip()
            if len(response_instructions) > 255:
                raise ValueError("Las instrucciones no pueden exceder 255 caracteres")
            
            if not response_instructions:
                response_instructions = None
        
        try:
            with self.get_db_session() as db:
                from .models.qa import Question, Answer
                
                # Verificar que la pregunta existe
                question = Question.get_by_id(db, question_id)
                if not question:
                    raise ValueError(f"Pregunta con ID {question_id} no encontrada")
                
                # Usar el método del modelo para crear la respuesta
                new_answer = Answer.create(db, question_id, response_text, response_instructions)
                
                answer_data = new_answer.to_dict()
                
                logger.info(f"✅ Respuesta creada exitosamente: ID {new_answer.id} para pregunta {question_id}")
                logger.info(f"   Respuesta: '{response_text[:100]}{'...' if len(response_text) > 100 else ''}'")
                if response_instructions:
                    logger.info(f"   Instrucciones: '{response_instructions[:50]}{'...' if len(response_instructions) > 50 else ''}'")
                
                return {
                    'success': True,
                    'answer': answer_data,
                    'question_info': {
                        'id': question.id,
                        'original_question': question.original_question,
                        'user_id': question.user_id
                    },
                    'message': 'Respuesta creada exitosamente'
                }
                
        except ValueError:
            raise  # Re-lanzar errores de validación (incluye "ya existe respuesta")
        except Exception as e:
            logger.error(f"❌ Error creando respuesta para pregunta {question_id}: {e}")
            raise RuntimeError(f"Error en la base de datos: {str(e)}")

    def update_answer(self, answer_id: int, **kwargs) -> dict:
        """
        Actualiza una respuesta existente.
        
        Args:
            answer_id (int): ID de la respuesta a actualizar
            **kwargs: Campos a actualizar (answer_text, response_instructions)
            
        Returns:
            dict: Información de la respuesta actualizada con éxito/error
            
        Raises:
            ValueError: Si el answer_id es inválido o los campos no son válidos
            RuntimeError: Si hay error en la base de datos o la respuesta no existe
        """
        if not isinstance(answer_id, int) or answer_id <= 0:
            raise ValueError("El ID de la respuesta debe ser un entero positivo")
        
        # Campos permitidos para actualización
        allowed_fields = {'answer_text', 'response_instructions'}
        
        # Filtrar campos válidos
        update_data = {k: v for k, v in kwargs.items() if k in allowed_fields}
        
        if not update_data:
            raise ValueError(f"No se proporcionaron campos válidos para actualizar. Campos permitidos: {allowed_fields}")
        
        # Validar campos específicos
        if 'answer_text' in update_data:
            answer_text = update_data['answer_text']
            if not answer_text or not answer_text.strip():
                raise ValueError("El texto de la respuesta no puede estar vacío")
            
            answer_text = answer_text.strip()
            if len(answer_text) > 5000:
                raise ValueError("La respuesta no puede exceder 5000 caracteres")
            
            if len(answer_text) < 10:
                raise ValueError("La respuesta debe tener al menos 10 caracteres")
            
            update_data['answer_text'] = answer_text
        
        if 'response_instructions' in update_data:
            instructions = update_data['response_instructions']
            if instructions is not None:
                instructions = instructions.strip()
                if len(instructions) > 255:
                    raise ValueError("Las instrucciones no pueden exceder 255 caracteres")
                
                if not instructions:
                    instructions = None
            
            update_data['response_instructions'] = instructions
        
        try:
            with self.get_db_session() as db:
                from .models.qa import Answer
                
                # Usar el método del modelo para buscar la respuesta
                answer = Answer.get_by_id(db, answer_id)
                
                if not answer:
                    raise RuntimeError(f"Respuesta con ID {answer_id} no encontrada")
                
                # Guardar valores anteriores para el log
                old_values = {
                    field: getattr(answer, field) 
                    for field in update_data.keys() 
                    if hasattr(answer, field)
                }
                
                # Usar el método del modelo para actualizar
                answer.update(db, **update_data)
                
                updated_fields = list(update_data.keys())
                
                logger.info(f"✅ Respuesta actualizada exitosamente: ID {answer_id}")
                logger.info(f"   Campos actualizados: {updated_fields}")
                for field in updated_fields:
                    old_val = old_values.get(field, 'N/A')
                    new_val = update_data[field]
                    if field == 'answer_text':
                        old_preview = f"'{old_val[:50]}...'" if len(str(old_val)) > 50 else f"'{old_val}'"
                        new_preview = f"'{new_val[:50]}...'" if len(str(new_val)) > 50 else f"'{new_val}'"
                        logger.info(f"   {field}: {old_preview} → {new_preview}")
                    else:
                        logger.info(f"   {field}: '{old_val}' → '{new_val}'")
                
                return {
                    'success': True,
                    'answer': answer.to_dict(),
                    'updated_fields': updated_fields,
                    'old_values': old_values,
                    'message': 'Respuesta actualizada exitosamente'
                }
                
        except ValueError:
            raise  # Re-lanzar errores de validación
        except RuntimeError:
            raise  # Re-lanzar errores de respuesta no encontrada
        except Exception as e:
            logger.error(f"❌ Error actualizando respuesta ID {answer_id}: {e}")
            raise RuntimeError(f"Error en la base de datos: {str(e)}")

    def get_question_with_variants(self, question_id: int) -> dict:
        """
        Obtiene una pregunta con todas sus variantes y respuesta asociada.
        
        Args:
            question_id (int): ID de la pregunta
            
        Returns:
            dict: Información completa de la pregunta con variantes y respuesta
            
        Raises:
            ValueError: Si el question_id es inválido
            RuntimeError: Si hay error en la base de datos o la pregunta no existe
        """
        if not isinstance(question_id, int) or question_id <= 0:
            raise ValueError("El ID de la pregunta debe ser un entero positivo")
        
        try:
            with self.get_db_session() as db:
                from .models.qa import Question, QuestionVariant, Answer
                
                # Usar el método del modelo para buscar la pregunta
                question = Question.get_by_id(db, question_id)
                
                if not question:
                    raise RuntimeError(f"Pregunta con ID {question_id} no encontrada")
                
                # Obtener todas las variantes con embeddings
                variants = question.get_variants_with_embeddings(db)
                variants_data = []
                
                for variant in variants:
                    variant_dict = variant.to_dict()
                    
                    # Añadir información de validación del embedding
                    embedding_validation = variant.validate_embedding()
                    variant_dict['embedding_validation'] = embedding_validation
                    
                    variants_data.append(variant_dict)
                
                # Obtener la respuesta si existe
                answer_data = None
                if question.answer:
                    answer_data = question.answer.to_dict()
                
                # Información del usuario propietario
                user_info = {
                    'user_id': question.user_id,
                    'user_name': question.user.name if question.user else 'Desconocido',
                    'user_email': question.user.email if question.user else 'Desconocido'
                }
                
                question_data = question.to_dict()
                
                logger.info(f"✅ Pregunta obtenida exitosamente: ID {question_id}")
                logger.info(f"   Variantes: {len(variants_data)}")
                logger.info(f"   Tiene respuesta: {'Sí' if answer_data else 'No'}")
                
                return {
                    'success': True,
                    'question': question_data,
                    'variants': variants_data,
                    'answer': answer_data,
                    'user_info': user_info,
                    'summary': {
                        'total_variants': len(variants_data),
                        'has_answer': answer_data is not None,
                        'valid_embeddings': sum(1 for v in variants_data if v.get('embedding_validation', {}).get('is_valid', False))
                    },
                    'message': f'Pregunta obtenida con {len(variants_data)} variantes'
                }
                
        except ValueError:
            raise  # Re-lanzar errores de validación
        except RuntimeError:
            raise  # Re-lanzar errores de pregunta no encontrada
        except Exception as e:
            logger.error(f"❌ Error obteniendo pregunta ID {question_id}: {e}")
            raise RuntimeError(f"Error en la base de datos: {str(e)}")

    def search_similar_questions(self, user_id: int, query_embedding: list, threshold: float = 0.8, limit: int = 5) -> dict:
        """
        Busca preguntas similares usando búsqueda vectorial con pgvector.
        
        Utiliza similitud coseno para encontrar las variantes más similares
        al embedding de consulta proporcionado.
        
        Args:
            user_id (int): ID del usuario para filtrar resultados
            query_embedding (list): Embedding de la consulta (1536 dimensiones)
            threshold (float): Umbral de similitud mínima (0.0-1.0, default: 0.8)
            limit (int): Número máximo de resultados (default: 5)
            
        Returns:
            dict: Resultados de búsqueda con preguntas similares y scores
            
        Raises:
            ValueError: Si los parámetros son inválidos o el usuario no existe
            RuntimeError: Si hay error en la base de datos o búsqueda vectorial
        """
        # Validaciones de entrada
        if not isinstance(user_id, int) or user_id <= 0:
            raise ValueError("El ID del usuario debe ser un entero positivo")
        
        if not isinstance(query_embedding, list):
            raise ValueError("El embedding de consulta debe ser una lista")
        
        if len(query_embedding) != 1536:
            raise ValueError(f"El embedding debe tener 1536 dimensiones, recibido: {len(query_embedding)}")
        
        if not all(isinstance(x, (int, float)) for x in query_embedding):
            raise ValueError("Todos los valores del embedding deben ser números")
        
        if not isinstance(threshold, (int, float)) or not (0.0 <= threshold <= 1.0):
            raise ValueError("El umbral debe ser un número entre 0.0 y 1.0")
        
        if not isinstance(limit, int) or limit <= 0 or limit > 50:
            raise ValueError("El límite debe ser un entero entre 1 y 50")
        
        try:
            with self.get_db_session() as db:
                from .models.user import User
                from .models.qa import QuestionVariant, Question, Answer
                
                # Verificar que el usuario existe
                user = User.get_by_id(db, user_id)
                if not user:
                    raise ValueError(f"Usuario con ID {user_id} no encontrado")
                
                # Usar el método del modelo para búsqueda vectorial
                similar_variants = QuestionVariant.search_similar(
                    db, user_id, query_embedding, threshold, limit
                )
                
                # Procesar resultados para incluir información completa
                results = []
                seen_questions = set()  # Evitar duplicados de la misma pregunta
                
                for variant, similarity_score in similar_variants:
                    # Evitar mostrar múltiples variantes de la misma pregunta
                    if variant.question_id in seen_questions:
                        continue
                    
                    seen_questions.add(variant.question_id)
                    
                    # Obtener información completa de la pregunta
                    question = Question.get_by_id(db, variant.question_id)
                    if not question:
                        continue
                    
                    # Obtener respuesta si existe
                    answer = Answer.get_by_question(db, question.id)
                    
                    result_item = {
                        'question_id': question.id,
                        'original_question': question.original_question,
                        'matched_variant': {
                            'id': variant.id,
                            'text': variant.variant_text,
                            'similarity_score': round(similarity_score, 4)
                        },
                        'answer': {
                            'id': answer.id if answer else None,
                            'text': answer.answer_text if answer else None,
                            'instructions': answer.response_instructions if answer else None,
                            'has_answer': answer is not None
                        },
                        'created_at': question.created_at.isoformat() if question.created_at else None,
                        'updated_at': question.updated_at.isoformat() if question.updated_at else None
                    }
                    
                    results.append(result_item)
                
                # Ordenar por score de similitud descendente
                results.sort(key=lambda x: x['matched_variant']['similarity_score'], reverse=True)
                
                logger.info(f"✅ Búsqueda vectorial completada para usuario {user_id}")
                logger.info(f"   Resultados encontrados: {len(results)}")
                logger.info(f"   Umbral utilizado: {threshold}")
                logger.info(f"   Límite aplicado: {limit}")
                
                if results:
                    best_match = results[0]
                    logger.info(f"   Mejor coincidencia: Score {best_match['matched_variant']['similarity_score']:.4f}")
                    logger.info(f"   Pregunta: '{best_match['original_question'][:100]}{'...' if len(best_match['original_question']) > 100 else ''}'")
                
                return {
                    'success': True,
                    'user_id': user_id,
                    'query_info': {
                        'threshold': threshold,
                        'limit': limit,
                        'embedding_dimensions': len(query_embedding)
                    },
                    'results': results,
                    'summary': {
                        'total_found': len(results),
                        'has_results': len(results) > 0,
                        'best_score': results[0]['matched_variant']['similarity_score'] if results else 0.0,
                        'answered_questions': sum(1 for r in results if r['answer']['has_answer']),
                        'unanswered_questions': sum(1 for r in results if not r['answer']['has_answer'])
                    },
                    'message': f'Encontradas {len(results)} preguntas similares'
                }
                
        except ValueError:
            raise  # Re-lanzar errores de validación
        except Exception as e:
            logger.error(f"❌ Error en búsqueda vectorial para usuario {user_id}: {e}")
            raise RuntimeError(f"Error en la búsqueda vectorial: {str(e)}")

    # =============================================================================
    # MÉTODOS DE GESTIÓN DE AUTOMATIZACIONES
    # =============================================================================

    def create_response_automation(self, user_id: int, email_account_id: int, 
                                 question_ids: list, tone: str = 'professional',
                                 is_draft_mode: bool = False, custom_instructions: str = None) -> dict:
        """
        Crea una nueva automatización de respuesta.
        
        NOTA: Según la nueva arquitectura, ResponseAutomation solo puede tener UNA pregunta,
        por lo que si se proporcionan múltiples question_ids, se tomará solo el primero.
        
        Args:
            user_id (int): ID del usuario propietario
            email_account_id (int): ID de la cuenta de email
            question_ids (list): Lista de IDs de preguntas (solo se usará el primero)
            tone (str): Tono de respuesta ('professional', 'casual', 'friendly')
            is_draft_mode (bool): Modo borrador
            custom_instructions (str): Instrucciones personalizadas
            
        Returns:
            dict: Información de la automatización creada con éxito/error
            
        Raises:
            ValueError: Si los parámetros son inválidos o el usuario/cuenta no existen
            RuntimeError: Si hay error en la base de datos
        """
        # Validaciones de entrada
        if not isinstance(user_id, int) or user_id <= 0:
            raise ValueError("El ID del usuario debe ser un entero positivo")
        
        if not isinstance(email_account_id, int) or email_account_id <= 0:
            raise ValueError("El ID de la cuenta de email debe ser un entero positivo")
        
        if not isinstance(question_ids, list) or len(question_ids) == 0:
            raise ValueError("Se debe proporcionar al menos un ID de pregunta")
        
        if not all(isinstance(qid, int) and qid > 0 for qid in question_ids):
            raise ValueError("Todos los IDs de pregunta deben ser enteros positivos")
        
        # Tomar solo el primer question_id según la nueva arquitectura
        question_id = question_ids[0]
        
        if len(question_ids) > 1:
            logger.warning(f"⚠️  Se proporcionaron {len(question_ids)} preguntas, pero ResponseAutomation solo soporta una. Usando pregunta ID {question_id}")
        
        # Validar tono
        valid_tones = ['professional', 'casual', 'friendly']
        if tone not in valid_tones:
            raise ValueError(f"Tono inválido. Debe ser uno de: {valid_tones}")
        
        # Validar custom_instructions si se proporciona
        if custom_instructions is not None:
            if not isinstance(custom_instructions, str):
                raise ValueError("Las instrucciones personalizadas deben ser una cadena de texto")
            
            custom_instructions = custom_instructions.strip()
            if len(custom_instructions) > 1000:
                raise ValueError("Las instrucciones personalizadas no pueden exceder 1000 caracteres")
            
            if not custom_instructions:
                custom_instructions = None
        
        try:
            with self.get_db_session() as db:
                from .models.user import User
                from .models.email_account import EmailAccount
                from .models.automation import Automation
                from .models.qa import Question
                
                # Verificar que el usuario existe
                user = User.get_by_id(db, user_id)
                if not user:
                    raise ValueError(f"Usuario con ID {user_id} no encontrado")
                
                # Verificar que la cuenta de email existe y pertenece al usuario
                email_account = EmailAccount.get_by_id(db, email_account_id)
                if not email_account:
                    raise ValueError(f"Cuenta de email con ID {email_account_id} no encontrada")
                
                if email_account.user_id != user_id:
                    raise ValueError(f"La cuenta de email {email_account_id} no pertenece al usuario {user_id}")
                
                # Verificar que la pregunta existe y pertenece al usuario
                question = Question.get_by_id(db, question_id)
                if not question:
                    raise ValueError(f"Pregunta con ID {question_id} no encontrada")
                
                if question.user_id != user_id:
                    raise ValueError(f"La pregunta {question_id} no pertenece al usuario {user_id}")
                
                # Verificar que la pregunta tiene respuesta
                if not question.answer:
                    raise ValueError(f"La pregunta {question_id} debe tener una respuesta antes de crear una automatización")
                
                # Usar el método del modelo para crear la automatización
                automation = Automation.create_response_automation(
                    db, email_account_id, question_id, tone, custom_instructions, is_draft_mode
                )
                
                # Obtener información completa para la respuesta
                automation_data = automation.get_detailed_info(db)
                
                logger.info(f"✅ Automatización de respuesta creada exitosamente: ID {automation.id}")
                logger.info(f"   Usuario: {user_id} ({user.email})")
                logger.info(f"   Cuenta de email: {email_account.email}")
                logger.info(f"   Pregunta: ID {question_id}")
                logger.info(f"   Tono: {tone}")
                logger.info(f"   Modo borrador: {'Sí' if is_draft_mode else 'No'}")
                if custom_instructions:
                    logger.info(f"   Instrucciones personalizadas: '{custom_instructions[:100]}{'...' if len(custom_instructions) > 100 else ''}'")
                
                return {
                    'success': True,
                    'automation': automation_data,
                    'type': 'response',
                    'question_info': {
                        'id': question.id,
                        'original_question': question.original_question,
                        'has_answer': question.answer is not None
                    },
                    'ignored_questions': question_ids[1:] if len(question_ids) > 1 else [],
                    'message': 'Automatización de respuesta creada exitosamente'
                }
                
        except ValueError:
            raise  # Re-lanzar errores de validación
        except Exception as e:
            logger.error(f"❌ Error creando automatización de respuesta para usuario {user_id}: {e}")
            raise RuntimeError(f"Error en la base de datos: {str(e)}")

    def create_forward_automation(self, user_id: int, email_account_id: int, 
                                forward_to: str, description: str = None) -> dict:
        """
        Crea una nueva automatización de reenvío.
        
        Args:
            user_id (int): ID del usuario propietario
            email_account_id (int): ID de la cuenta de email
            forward_to (str): Email de destino para el reenvío
            description (str): Descripción del criterio de reenvío (máximo 255 caracteres)
            
        Returns:
            dict: Información de la automatización creada con éxito/error
            
        Raises:
            ValueError: Si los parámetros son inválidos o el usuario/cuenta no existen
            RuntimeError: Si hay error en la base de datos
        """
        # Validaciones de entrada
        if not isinstance(user_id, int) or user_id <= 0:
            raise ValueError("El ID del usuario debe ser un entero positivo")
        
        if not isinstance(email_account_id, int) or email_account_id <= 0:
            raise ValueError("El ID de la cuenta de email debe ser un entero positivo")
        
        if not forward_to or not forward_to.strip():
            raise ValueError("El email de destino no puede estar vacío")
        
        # Validar formato básico de email
        forward_to = forward_to.strip().lower()
        if "@" not in forward_to or "." not in forward_to.split("@")[-1]:
            raise ValueError("Formato de email de destino inválido")
        
        # Validar descripción si se proporciona
        if description is not None:
            if not isinstance(description, str):
                raise ValueError("La descripción debe ser una cadena de texto")
            
            description = description.strip()
            if len(description) > 255:
                raise ValueError("La descripción no puede exceder 255 caracteres")
            
            if not description:
                description = None
        
        try:
            with self.get_db_session() as db:
                from .models.user import User
                from .models.email_account import EmailAccount
                from .models.automation import Automation
                
                # Verificar que el usuario existe
                user = User.get_by_id(db, user_id)
                if not user:
                    raise ValueError(f"Usuario con ID {user_id} no encontrado")
                
                # Verificar que la cuenta de email existe y pertenece al usuario
                email_account = EmailAccount.get_by_id(db, email_account_id)
                if not email_account:
                    raise ValueError(f"Cuenta de email con ID {email_account_id} no encontrada")
                
                if email_account.user_id != user_id:
                    raise ValueError(f"La cuenta de email {email_account_id} no pertenece al usuario {user_id}")
                
                # Verificar que no esté reenviando a la misma cuenta
                if forward_to == email_account.email:
                    raise ValueError("No se puede reenviar emails a la misma cuenta de origen")
                
                # Usar el método del modelo para crear la automatización
                automation = Automation.create_forward_automation(
                    db, email_account_id, forward_to, description
                )
                
                # Obtener información completa para la respuesta
                automation_data = automation.get_detailed_info(db)
                
                logger.info(f"✅ Automatización de reenvío creada exitosamente: ID {automation.id}")
                logger.info(f"   Usuario: {user_id} ({user.email})")
                logger.info(f"   Cuenta de email: {email_account.email}")
                logger.info(f"   Reenviar a: {forward_to}")
                if description:
                    logger.info(f"   Descripción: '{description}'")
                
                return {
                    'success': True,
                    'automation': automation_data,
                    'type': 'forward',
                    'forward_info': {
                        'forward_to_email': forward_to,
                        'description': description,
                        'has_description': description is not None
                    },
                    'message': 'Automatización de reenvío creada exitosamente'
                }
                
        except ValueError:
            raise  # Re-lanzar errores de validación
        except Exception as e:
            logger.error(f"❌ Error creando automatización de reenvío para usuario {user_id}: {e}")
            raise RuntimeError(f"Error en la base de datos: {str(e)}")

    def get_active_automations(self, email_account_id: int) -> dict:
        """
        Obtiene todas las automatizaciones activas de una cuenta de email.
        
        Args:
            email_account_id (int): ID de la cuenta de email
            
        Returns:
            dict: Lista de automatizaciones activas con información detallada
            
        Raises:
            ValueError: Si el email_account_id es inválido
            RuntimeError: Si hay error en la base de datos o la cuenta no existe
        """
        if not isinstance(email_account_id, int) or email_account_id <= 0:
            raise ValueError("El ID de la cuenta de email debe ser un entero positivo")
        
        try:
            with self.get_db_session() as db:
                from .models.email_account import EmailAccount
                from .models.automation import Automation
                
                # Verificar que la cuenta de email existe
                email_account = EmailAccount.get_by_id(db, email_account_id)
                if not email_account:
                    raise ValueError(f"Cuenta de email con ID {email_account_id} no encontrada")
                
                # Usar el método del modelo para obtener automatizaciones activas
                active_automations = Automation.get_active_by_email_account(db, email_account_id)
                
                # Procesar cada automatización para obtener información detallada
                automations_data = []
                response_count = 0
                forward_count = 0
                draft_count = 0
                
                for automation in active_automations:
                    try:
                        automation_info = automation.get_detailed_info(db)
                        automations_data.append(automation_info)
                        
                        # Contar tipos
                        if automation.is_response_type:
                            response_count += 1
                        elif automation.is_forward_type:
                            forward_count += 1
                        
                        if automation.is_draft_mode:
                            draft_count += 1
                            
                    except Exception as e:
                        logger.warning(f"⚠️  Error obteniendo detalles de automatización {automation.id}: {e}")
                        # Incluir información básica en caso de error
                        automations_data.append({
                            'id': automation.id,
                            'type': automation.type.value if automation.type else 'unknown',
                            'is_active': automation.is_active,
                            'is_draft_mode': automation.is_draft_mode,
                            'error': f"Error obteniendo detalles: {str(e)}"
                        })
                
                logger.info(f"✅ Obtenidas {len(active_automations)} automatizaciones activas para cuenta {email_account_id}")
                logger.info(f"   Respuestas: {response_count}, Reenvíos: {forward_count}, Borradores: {draft_count}")
                
                return {
                    'success': True,
                    'email_account_id': email_account_id,
                    'email_account_info': {
                        'email': email_account.email,
                        'user_id': email_account.user_id,
                        'is_active': email_account.is_active
                    },
                    'automations': automations_data,
                    'summary': {
                        'total_active': len(active_automations),
                        'response_automations': response_count,
                        'forward_automations': forward_count,
                        'draft_mode_automations': draft_count,
                        'production_mode_automations': len(active_automations) - draft_count
                    },
                    'message': f'Encontradas {len(active_automations)} automatizaciones activas'
                }
                
        except ValueError:
            raise  # Re-lanzar errores de validación
        except Exception as e:
            logger.error(f"❌ Error obteniendo automatizaciones activas para cuenta {email_account_id}: {e}")
            raise RuntimeError(f"Error en la base de datos: {str(e)}")

    def toggle_automation(self, automation_id: int) -> dict:
        """
        Activa o desactiva una automatización.
        
        Args:
            automation_id (int): ID de la automatización
            
        Returns:
            dict: Información del nuevo estado de la automatización
            
        Raises:
            ValueError: Si el automation_id es inválido
            RuntimeError: Si hay error en la base de datos o la automatización no existe
        """
        if not isinstance(automation_id, int) or automation_id <= 0:
            raise ValueError("El ID de la automatización debe ser un entero positivo")
        
        try:
            with self.get_db_session() as db:
                from .models.automation import Automation
                
                # Usar el método del modelo para buscar la automatización
                automation = Automation.get_by_id(db, automation_id)
                
                if not automation:
                    raise RuntimeError(f"Automatización con ID {automation_id} no encontrada")
                
                # Guardar estado anterior para el log
                previous_state = automation.is_active
                
                # Usar el método del modelo para alternar estado
                new_state = automation.toggle_active()
                db.flush()
                
                # Obtener información completa para la respuesta
                automation_data = automation.get_detailed_info(db)
                
                action = "activada" if new_state else "desactivada"
                logger.info(f"✅ Automatización {action} exitosamente: ID {automation_id}")
                logger.info(f"   Estado anterior: {'Activa' if previous_state else 'Inactiva'}")
                logger.info(f"   Estado nuevo: {'Activa' if new_state else 'Inactiva'}")
                logger.info(f"   Tipo: {automation.type.value if automation.type else 'unknown'}")
                if automation.user:
                    logger.info(f"   Usuario: {automation.user.email}")
                
                return {
                    'success': True,
                    'automation': automation_data,
                    'state_change': {
                        'previous_state': previous_state,
                        'new_state': new_state,
                        'action': action
                    },
                    'message': f'Automatización {action} exitosamente'
                }
                
        except ValueError:
            raise  # Re-lanzar errores de validación
        except RuntimeError:
            raise  # Re-lanzar errores de automatización no encontrada
        except Exception as e:
            logger.error(f"❌ Error alternando estado de automatización ID {automation_id}: {e}")
            raise RuntimeError(f"Error en la base de datos: {str(e)}")

    def update_automation_questions(self, automation_id: int, question_ids: list) -> dict:
        """
        Actualiza las preguntas asociadas a una automatización de respuesta.
        
        NOTA: Según la nueva arquitectura, ResponseAutomation solo puede tener UNA pregunta,
        por lo que si se proporcionan múltiples question_ids, se tomará solo el primero.
        
        Args:
            automation_id (int): ID de la automatización
            question_ids (list): Lista de IDs de preguntas (solo se usará el primero)
            
        Returns:
            dict: Información de la actualización con éxito/error
            
        Raises:
            ValueError: Si los parámetros son inválidos o la automatización no es de respuesta
            RuntimeError: Si hay error en la base de datos o la automatización no existe
        """
        if not isinstance(automation_id, int) or automation_id <= 0:
            raise ValueError("El ID de la automatización debe ser un entero positivo")
        
        if not isinstance(question_ids, list) or len(question_ids) == 0:
            raise ValueError("Se debe proporcionar al menos un ID de pregunta")
        
        if not all(isinstance(qid, int) and qid > 0 for qid in question_ids):
            raise ValueError("Todos los IDs de pregunta deben ser enteros positivos")
        
        # Tomar solo el primer question_id según la nueva arquitectura
        question_id = question_ids[0]
        
        if len(question_ids) > 1:
            logger.warning(f"⚠️  Se proporcionaron {len(question_ids)} preguntas, pero ResponseAutomation solo soporta una. Usando pregunta ID {question_id}")
        
        try:
            with self.get_db_session() as db:
                from .models.automation import Automation
                from .models.qa import Question
                
                # Usar el método del modelo para buscar la automatización
                automation = Automation.get_by_id(db, automation_id)
                
                if not automation:
                    raise RuntimeError(f"Automatización con ID {automation_id} no encontrada")
                
                # Verificar que es una automatización de respuesta
                if not automation.is_response_type:
                    raise ValueError("Solo las automatizaciones de respuesta pueden tener preguntas asociadas")
                
                if not automation.response_automation:
                    raise RuntimeError("La automatización de respuesta no tiene detalles configurados")
                
                # Verificar que la pregunta existe y pertenece al usuario
                question = Question.get_by_id(db, question_id)
                if not question:
                    raise ValueError(f"Pregunta con ID {question_id} no encontrada")
                
                user_id = automation.user_id
                if question.user_id != user_id:
                    raise ValueError(f"La pregunta {question_id} no pertenece al usuario {user_id}")
                
                # Verificar que la pregunta tiene respuesta
                if not question.answer:
                    raise ValueError(f"La pregunta {question_id} debe tener una respuesta antes de asociarla a una automatización")
                
                # Guardar pregunta anterior para el log
                previous_question_id = automation.response_automation.question_id
                previous_question = Question.get_by_id(db, previous_question_id) if previous_question_id else None
                
                # Usar el método del modelo para establecer la pregunta
                automation.set_question(db, question_id)
                
                # Obtener información completa para la respuesta
                automation_data = automation.get_detailed_info(db)
                
                logger.info(f"✅ Pregunta actualizada exitosamente en automatización ID {automation_id}")
                logger.info(f"   Pregunta anterior: ID {previous_question_id} - '{previous_question.original_question[:50] if previous_question else 'N/A'}...'")
                logger.info(f"   Pregunta nueva: ID {question_id} - '{question.original_question[:50]}...'")
                logger.info(f"   Usuario: {user_id}")
                
                return {
                    'success': True,
                    'automation': automation_data,
                    'question_change': {
                        'previous_question_id': previous_question_id,
                        'new_question_id': question_id,
                        'previous_question_text': previous_question.original_question if previous_question else None,
                        'new_question_text': question.original_question
                    },
                    'ignored_questions': question_ids[1:] if len(question_ids) > 1 else [],
                    'message': 'Pregunta de automatización actualizada exitosamente'
                }
                
        except ValueError:
            raise  # Re-lanzar errores de validación
        except RuntimeError:
            raise  # Re-lanzar errores de automatización no encontrada
        except Exception as e:
            logger.error(f"❌ Error actualizando preguntas de automatización ID {automation_id}: {e}")
            raise RuntimeError(f"Error en la base de datos: {str(e)}")

    def get_automation_details(self, automation_id: int) -> dict:
        """
        Obtiene los detalles completos de una automatización.
        
        Args:
            automation_id (int): ID de la automatización
            
        Returns:
            dict: Información completa de la automatización con todos sus detalles
            
        Raises:
            ValueError: Si el automation_id es inválido
            RuntimeError: Si hay error en la base de datos o la automatización no existe
        """
        if not isinstance(automation_id, int) or automation_id <= 0:
            raise ValueError("El ID de la automatización debe ser un entero positivo")
        
        try:
            with self.get_db_session() as db:
                from .models.automation import Automation
                
                # Usar el método del modelo para buscar la automatización
                automation = Automation.get_by_id(db, automation_id)
                
                if not automation:
                    raise RuntimeError(f"Automatización con ID {automation_id} no encontrada")
                
                # Obtener información completa usando el método del modelo
                automation_data = automation.get_detailed_info(db)
                
                # Añadir información adicional específica según el tipo
                additional_info = {}
                
                if automation.is_response_type and automation.response_automation:
                    # Información adicional para automatizaciones de respuesta
                    response_auto = automation.response_automation
                    additional_info['response_details'] = {
                        'tone': response_auto.tone,
                        'has_custom_instructions': response_auto.has_custom_instructions,
                        'custom_instructions': response_auto.custom_instructions
                    }
                    
                    # Información de la pregunta y respuesta asociada
                    if response_auto.question:
                        question = response_auto.question
                        additional_info['question_details'] = {
                            'id': question.id,
                            'original_question': question.original_question,
                            'created_at': question.created_at.isoformat() if question.created_at else None,
                            'has_answer': question.answer is not None
                        }
                        
                        if question.answer:
                            additional_info['answer_details'] = {
                                'id': question.answer.id,
                                'answer_text': question.answer.answer_text,
                                'response_instructions': question.answer.response_instructions,
                                'created_at': question.answer.created_at.isoformat() if question.answer.created_at else None,
                                'updated_at': question.answer.updated_at.isoformat() if question.answer.updated_at else None
                            }
                
                elif automation.is_forward_type and automation.forward_automation:
                    # Información adicional para automatizaciones de reenvío
                    forward_auto = automation.forward_automation
                    additional_info['forward_details'] = {
                        'forward_to_email': forward_auto.forward_to_email,
                        'description': forward_auto.description,
                        'has_description': forward_auto.has_description
                    }
                
                # Validar configuración
                validation_result = automation.validate_configuration()
                additional_info['configuration_validation'] = validation_result
                
                # Combinar toda la información
                complete_data = {
                    **automation_data,
                    **additional_info
                }
                
                logger.info(f"✅ Detalles obtenidos exitosamente para automatización ID {automation_id}")
                logger.info(f"   Tipo: {automation.type.value if automation.type else 'unknown'}")
                logger.info(f"   Estado: {'Activa' if automation.is_active else 'Inactiva'}")
                logger.info(f"   Modo: {'Borrador' if automation.is_draft_mode else 'Producción'}")
                logger.info(f"   Configuración válida: {'Sí' if validation_result['is_valid'] else 'No'}")
                
                return {
                    'success': True,
                    'automation': complete_data,
                    'metadata': {
                        'automation_id': automation_id,
                        'type': automation.type.value if automation.type else None,
                        'is_valid_configuration': validation_result['is_valid'],
                        'has_errors': len(validation_result.get('errors', [])) > 0
                    },
                    'message': 'Detalles de automatización obtenidos exitosamente'
                }
                
        except ValueError:
            raise  # Re-lanzar errores de validación
        except RuntimeError:
            raise  # Re-lanzar errores de automatización no encontrada
        except Exception as e:
            logger.error(f"❌ Error obteniendo detalles de automatización ID {automation_id}: {e}")
            raise RuntimeError(f"Error en la base de datos: {str(e)}")


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