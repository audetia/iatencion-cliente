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
        self._encryption_key = self._get_or_create_encryption_key()
        self._cipher_suite = Fernet(self._encryption_key)
        self._initialize_engine()
    
    def _get_or_create_encryption_key(self) -> bytes:
        """
        Obtiene o crea la clave de encriptación para contraseñas IMAP.
        
        Returns:
            bytes: Clave de encriptación Fernet
            
        Note:
            La clave se obtiene de la variable de entorno ENCRYPTION_KEY.
            Si no existe, se genera una nueva (solo para desarrollo).
        """
        encryption_key = os.getenv("ENCRYPTION_KEY")
        
        if encryption_key:
            try:
                # Decodificar la clave desde base64
                return base64.urlsafe_b64decode(encryption_key.encode())
            except Exception as e:
                logger.error(f"❌ Error decodificando ENCRYPTION_KEY: {e}")
                raise ValueError("ENCRYPTION_KEY no es válida")
        else:
            # En desarrollo, generar una clave nueva
            logger.warning("⚠️  ENCRYPTION_KEY no encontrada, generando una nueva")
            new_key = Fernet.generate_key()
            encoded_key = base64.urlsafe_b64encode(new_key).decode()
            logger.warning(f"🔑 Nueva clave generada: {encoded_key}")
            logger.warning("📝 Añade esta clave a tu archivo .env: ENCRYPTION_KEY=" + encoded_key)
            return new_key
    
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
        if "@" not in email or "." not in email.split("@")[-1]:
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