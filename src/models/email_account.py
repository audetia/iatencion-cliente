"""
Modelo EmailAccount para el sistema de automatización de emails.

Este módulo define el modelo de cuenta de email que representa las cuentas
IMAP/SMTP configuradas por los usuarios para automatizar sus emails.
"""

from sqlalchemy import Column, Integer, String, Boolean, ForeignKey
from sqlalchemy.orm import relationship
from datetime import datetime, timedelta
from typing import Optional, Dict, List, Union
from .base import Base, TimestampMixin

class EmailAccount(Base, TimestampMixin):
    """
    Modelo de Cuenta de Email.
    
    Representa una cuenta de email IMAP/SMTP configurada por un usuario
    para automatizar el procesamiento de emails.
    
    Attributes:
        id (int): Identificador único de la cuenta (clave primaria)
        user_id (int): ID del usuario propietario (clave foránea)
        email (str): Dirección de email de la cuenta
        imap_server (str): Servidor IMAP (ej: imap.gmail.com)
        imap_port (int): Puerto IMAP (ej: 993)
        smtp_server (str): Servidor SMTP (ej: smtp.gmail.com)
        smtp_port (int): Puerto SMTP (ej: 587)
        encrypted_password (str): Contraseña encriptada para IMAP/SMTP
        oauth2_token (str): Token OAuth2 (opcional)
        oauth2_refresh_token (str): Token de refresh OAuth2 (opcional)
        auth_type (str): Tipo de autenticación ('password' o 'oauth2')
        is_active (bool): Estado activo de la cuenta
        last_health_check (datetime): Última verificación de salud
        health_status (str): Estado de salud ('healthy', 'warning', 'error')
        created_at (datetime): Fecha de creación (automática)
        updated_at (datetime): Fecha de última actualización (automática)
    
    Relationships:
        user: Usuario propietario de la cuenta
        automations: Lista de automatizaciones configuradas para esta cuenta
        email_processed: Lista de emails procesados en esta cuenta
    """
    
    __tablename__ = 'email_account'

    # Campos principales
    id = Column(Integer, primary_key=True, index=True)
    user_id = Column(Integer, ForeignKey('users.id'), nullable=False, index=True)
    email = Column(String(255), nullable=False, index=True)
    imap_server = Column(String(255), nullable=False)
    imap_port = Column(Integer, nullable=False)
    smtp_server = Column(String(255), nullable=False)
    smtp_port = Column(Integer, nullable=False)
    encrypted_password = Column(String(500), nullable=False)  # Espacio extra para encriptación
    
    # Campos OAuth2
    oauth2_token = Column(String(1000))
    oauth2_refresh_token = Column(String(1000))
    auth_type = Column(String(20), default='password')  # 'password' o 'oauth2'
    
    # Campos de salud y monitoreo
    is_active = Column(Boolean, default=True, nullable=False)
    last_health_check = Column('last_health_check', None)
    health_status = Column(String(20), default='unknown')  # 'healthy', 'warning', 'error', 'unknown'

    # Relaciones
    user = relationship("User", back_populates="email_accounts")
    email_processed = relationship("EmailProcessed", back_populates="email_account", cascade="all, delete-orphan")
    
    # Relaciones futuras (se activarán cuando se implementen los otros modelos)
    # automations = relationship("Automation", back_populates="email_account")

    def __repr__(self):
        """
        Representación string de la cuenta de email.
        
        Returns:
            str: Representación legible de la cuenta
        """
        return f"<EmailAccount(id={self.id}, email='{self.email}', user_id={self.user_id}, active={self.is_active})>"
    
    def __str__(self):
        """
        String representation para uso general.
        
        Returns:
            str: Email y estado de la cuenta
        """
        status = "Activa" if self.is_active else "Inactiva"
        return f"{self.email} ({status})"
    
    @property
    def imap_config(self) -> dict:
        """
        Configuración IMAP como diccionario.
        
        Returns:
            dict: Configuración IMAP lista para usar
        """
        return {
            'server': self.imap_server,
            'port': self.imap_port,
            'email': self.email
        }
    
    @property
    def smtp_config(self) -> dict:
        """
        Configuración SMTP como diccionario.
        
        Returns:
            dict: Configuración SMTP lista para usar
        """
        return {
            'server': self.smtp_server,
            'port': self.smtp_port,
            'email': self.email
        }
    
    @property
    def display_name(self) -> str:
        """
        Nombre para mostrar de la cuenta.
        
        Returns:
            str: Email con indicador de estado
        """
        health_icon = {
            'healthy': '✅',
            'warning': '⚠️',
            'error': '❌',
            'unknown': '❔'
        }.get(self.health_status, '❔')
        
        active_icon = '✓' if self.is_active else '✗'
        return f"{self.email} {health_icon}{active_icon}"
    
    @property
    def is_oauth2(self) -> bool:
        """
        Verifica si la cuenta usa OAuth2.
        
        Returns:
            bool: True si usa OAuth2
        """
        return self.auth_type == 'oauth2'
    
    def activate(self) -> None:
        """
        Activa la cuenta de email.
        
        Permite que la cuenta sea monitoreada y procese emails.
        """
        self.is_active = True
    
    def deactivate(self) -> None:
        """
        Desactiva la cuenta de email.
        
        Detiene el monitoreo y procesamiento de emails para esta cuenta.
        """
        self.is_active = False
    
    def toggle_active(self) -> bool:
        """
        Alterna el estado activo de la cuenta.
        
        Returns:
            bool: Nuevo estado de la cuenta
        """
        self.is_active = not self.is_active
        return self.is_active
    
    def test_connection_detailed(self, decrypted_password: str) -> Dict[str, Union[bool, str, float, dict]]:
        """
        Realiza un test detallado de conexión IMAP y SMTP.
        
        Delega la lógica de conexión a EmailTools siguiendo el principio DRY.
        
        Args:
            decrypted_password (str): Contraseña desencriptada
            
        Returns:
            dict: Resultado detallado del test de conexión
        """
        # Importar EmailTools aquí para evitar dependencias circulares
        from ..tools.EmailTools import EmailToolsClass
        
        # Preparar configuración para EmailTools
        account_config = {
            'email': self.email,
            'imap_server': self.imap_server,
            'imap_port': self.imap_port,
            'smtp_server': self.smtp_server,
            'smtp_port': self.smtp_port,
            'auth_type': self.auth_type,
            'oauth2_token': self.oauth2_token if self.is_oauth2 else None
        }
        
        # Usar EmailTools para realizar el test
        return EmailToolsClass.test_email_account_connection(account_config, decrypted_password)
    
    def health_check(self, db_session, decrypted_password: str = None) -> Dict[str, Union[bool, str, datetime]]:
        """
        Realiza verificación de salud de la conexión y actualiza el estado.
        
        NOTA: Para monitoreo automático, usar EmailMonitoringService.
        Este método está pensado para verificaciones manuales con credenciales.
        
        Args:
            db_session: Sesión de base de datos
            decrypted_password (str, optional): Contraseña desencriptada
            
        Returns:
            dict: Resultado del health check
        """
        if not decrypted_password:
            return {
                'is_healthy': False,
                'status': 'error',
                'message': 'Contraseña requerida para health check con conexión real',
                'last_check': self.last_health_check
            }
        
        try:
            # Usar el método que delega a EmailTools
            connection_test = self.test_connection_detailed(decrypted_password)
            
            # Actualizar estado basado en el resultado
            if connection_test['overall_status'] == 'success':
                self.health_status = 'healthy'
                self.is_active = True
                is_healthy = True
                message = 'Conexión saludable'
            elif connection_test['overall_status'] == 'partial':
                self.health_status = 'warning'
                is_healthy = False
                message = 'Conexión parcial - revisar configuración'
            else:
                self.health_status = 'error'
                self.is_active = False
                is_healthy = False
                message = 'Error de conexión - cuenta desactivada'
            
            # Actualizar timestamp
            self.last_health_check = datetime.now()
            db_session.flush()
            
            return {
                'is_healthy': is_healthy,
                'status': self.health_status,
                'message': message,
                'last_check': self.last_health_check,
                'connection_details': connection_test
            }
            
        except Exception as e:
            self.health_status = 'error'
            self.last_health_check = datetime.now()
            db_session.flush()
            
            return {
                'is_healthy': False,
                'status': 'error',
                'message': f'Error en health check: {str(e)}',
                'last_check': self.last_health_check
            }
    
    def refresh_oauth2_token(self) -> bool:
        """
        Renueva el token OAuth2 usando el refresh token.
        
        Returns:
            bool: True si el token se renovó exitosamente
        """
        if not self.is_oauth2 or not self.oauth2_refresh_token:
            return False
        
        # TODO: Implementar renovación de tokens OAuth2
        # Esto dependerá del proveedor (Gmail, Outlook, etc.)
        # Por ahora, retornar False como placeholder
        return False
    
    def to_dict(self, include_password: bool = False, include_tokens: bool = False) -> dict:
        """
        Convierte la cuenta de email a diccionario.
        
        Args:
            include_password (bool): Si incluir la contraseña encriptada
            include_tokens (bool): Si incluir tokens OAuth2
            
        Returns:
            dict: Representación de la cuenta como diccionario
        """
        data = {
            'id': self.id,
            'user_id': self.user_id,
            'email': self.email,
            'imap_server': self.imap_server,
            'imap_port': self.imap_port,
            'smtp_server': self.smtp_server,
            'smtp_port': self.smtp_port,
            'auth_type': self.auth_type,
            'is_active': self.is_active,
            'health_status': self.health_status,
            'last_health_check': self.last_health_check.isoformat() if self.last_health_check else None,
            'created_at': self.created_at.isoformat() if self.created_at else None,
            'updated_at': self.updated_at.isoformat() if self.updated_at else None
        }
        
        if include_password:
            data['encrypted_password'] = self.encrypted_password
        
        if include_tokens and self.is_oauth2:
            data['oauth2_token'] = self.oauth2_token
            data['oauth2_refresh_token'] = self.oauth2_refresh_token
            
        return data
    
    @classmethod
    def from_dict(cls, data: dict) -> 'EmailAccount':
        """
        Crea una cuenta de email desde un diccionario.
        
        Args:
            data (dict): Datos de la cuenta
            
        Returns:
            EmailAccount: Nueva instancia de cuenta de email
        """
        return cls(
            user_id=data.get('user_id'),
            email=data.get('email'),
            imap_server=data.get('imap_server'),
            imap_port=data.get('imap_port'),
            smtp_server=data.get('smtp_server'),
            smtp_port=data.get('smtp_port'),
            encrypted_password=data.get('encrypted_password'),
            oauth2_token=data.get('oauth2_token'),
            oauth2_refresh_token=data.get('oauth2_refresh_token'),
            auth_type=data.get('auth_type', 'password'),
            is_active=data.get('is_active', True)
        )
    
    @classmethod
    def detect_email_config(cls, email: str) -> Dict[str, Union[dict, bool]]:
        """
        Detecta configuración automática para proveedores comunes.
        
        Args:
            email (str): Dirección de email
            
        Returns:
            dict: Configuración detectada o información de error
        """
        domain = email.split('@')[-1].lower()
        
        # Configuraciones conocidas para proveedores populares
        provider_configs = {
            'gmail.com': {
                'name': 'Gmail',
                'imap_server': 'imap.gmail.com',
                'imap_port': 993,
                'smtp_server': 'smtp.gmail.com',
                'smtp_port': 587,
                'supports_oauth2': True,
                'requires_app_password': True,
                'setup_instructions': 'Habilitar autenticación de 2 factores y generar contraseña de aplicación'
            },
            'outlook.com': {
                'name': 'Outlook.com',
                'imap_server': 'outlook.office365.com',
                'imap_port': 993,
                'smtp_server': 'smtp-mail.outlook.com',
                'smtp_port': 587,
                'supports_oauth2': True,
                'requires_app_password': False,
                'setup_instructions': 'Usar contraseña normal o configurar OAuth2'
            },
            'hotmail.com': {
                'name': 'Hotmail',
                'imap_server': 'outlook.office365.com',
                'imap_port': 993,
                'smtp_server': 'smtp-mail.outlook.com',
                'smtp_port': 587,
                'supports_oauth2': True,
                'requires_app_password': False,
                'setup_instructions': 'Usar contraseña normal o configurar OAuth2'
            },
            'yahoo.com': {
                'name': 'Yahoo Mail',
                'imap_server': 'imap.mail.yahoo.com',
                'imap_port': 993,
                'smtp_server': 'smtp.mail.yahoo.com',
                'smtp_port': 587,
                'supports_oauth2': False,
                'requires_app_password': True,
                'setup_instructions': 'Generar contraseña de aplicación en configuración de seguridad'
            },
            'icloud.com': {
                'name': 'iCloud Mail',
                'imap_server': 'imap.mail.me.com',
                'imap_port': 993,
                'smtp_server': 'smtp.mail.me.com',
                'smtp_port': 587,
                'supports_oauth2': False,
                'requires_app_password': True,
                'setup_instructions': 'Generar contraseña específica de app en configuración de Apple ID'
            }
        }
        
        if domain in provider_configs:
            config = provider_configs[domain]
            return {
                'detected': True,
                'provider': config['name'],
                'config': config,
                'recommendation': f"Configuración detectada para {config['name']}"
            }
        else:
            return {
                'detected': False,
                'provider': 'Desconocido',
                'config': None,
                'recommendation': 'Configuración manual requerida - contactar con proveedor de email'
            }
    
    def validate_config(self) -> dict:
        """
        Valida la configuración de la cuenta.
        
        Returns:
            dict: Resultado de validación con errores si los hay
        """
        errors = []
        
        # Validar email
        if not self.email or '@' not in self.email:
            errors.append("Email inválido")
        
        # Validar servidores
        if not self.imap_server:
            errors.append("Servidor IMAP requerido")
        if not self.smtp_server:
            errors.append("Servidor SMTP requerido")
            
        # Validar puertos
        if not (1 <= self.imap_port <= 65535):
            errors.append("Puerto IMAP inválido (1-65535)")
        if not (1 <= self.smtp_port <= 65535):
            errors.append("Puerto SMTP inválido (1-65535)")
            
        # Validar autenticación
        if self.auth_type == 'password':
            if not self.encrypted_password:
                errors.append("Contraseña requerida")
        elif self.auth_type == 'oauth2':
            if not self.oauth2_token:
                errors.append("Token OAuth2 requerido")
        else:
            errors.append("Tipo de autenticación inválido")
        
        return {
            'is_valid': len(errors) == 0,
            'errors': errors
        }
    
    @property
    def is_valid(self) -> bool:
        """
        Verifica si la configuración de la cuenta es válida.
        
        Returns:
            bool: True si la configuración es válida
        """
        return self.validate_config()['is_valid']
    
    def get_monitoring_config(self, decrypted_password: str) -> Dict[str, Union[str, int, bool]]:
        """
        Obtiene configuración específica para el servicio de monitoreo.
        
        Args:
            decrypted_password (str): Contraseña desencriptada
            
        Returns:
            dict: Configuración para InboxMonitor
        """
        return {
            'account_id': self.id,
            'email': self.email,
            'imap_server': self.imap_server,
            'imap_port': self.imap_port,
            'password': decrypted_password,
            'auth_type': self.auth_type,
            'oauth2_token': self.oauth2_token if self.is_oauth2 else None,
            'is_active': self.is_active,
            'health_status': self.health_status,
            'monitoring_enabled': self.is_active and self.health_status in ['healthy', 'unknown']
        }
    
    # =============================================================================
    # MÉTODOS DE CONSULTA (CLASS METHODS)
    # =============================================================================
    
    @classmethod
    def create(cls, db_session, user_id: int, email: str, imap_server: str, 
               imap_port: int, smtp_server: str, smtp_port: int, 
               encrypted_password: str, auth_type: str = 'password') -> 'EmailAccount':
        """
        Crea una nueva cuenta de email en la base de datos.
        
        Args:
            db_session: Sesión de base de datos
            user_id (int): ID del usuario propietario
            email (str): Email de la cuenta
            imap_server (str): Servidor IMAP
            imap_port (int): Puerto IMAP
            smtp_server (str): Servidor SMTP
            smtp_port (int): Puerto SMTP
            encrypted_password (str): Contraseña encriptada
            auth_type (str): Tipo de autenticación
            
        Returns:
            EmailAccount: Cuenta creada
            
        Raises:
            ValueError: Si ya existe una cuenta con ese email para el usuario
        """
        # Verificar si ya existe la cuenta
        existing_account = cls.get_by_user_and_email(db_session, user_id, email)
        if existing_account:
            raise ValueError(f"El usuario ya tiene una cuenta configurada para: {email}")
        
        account = cls(
            user_id=user_id,
            email=email,
            imap_server=imap_server,
            imap_port=imap_port,
            smtp_server=smtp_server,
            smtp_port=smtp_port,
            encrypted_password=encrypted_password,
            auth_type=auth_type
        )
        
        db_session.add(account)
        db_session.flush()
        return account
    
    @classmethod
    def get_by_id(cls, db_session, account_id: int) -> Optional['EmailAccount']:
        """
        Obtiene una cuenta por su ID.
        
        Args:
            db_session: Sesión de base de datos
            account_id (int): ID de la cuenta
            
        Returns:
            EmailAccount | None: Cuenta encontrada o None
        """
        return db_session.query(cls).filter(cls.id == account_id).first()
    
    @classmethod
    def get_by_user_and_email(cls, db_session, user_id: int, email: str) -> Optional['EmailAccount']:
        """
        Obtiene una cuenta por usuario y email.
        
        Args:
            db_session: Sesión de base de datos
            user_id (int): ID del usuario
            email (str): Email de la cuenta
            
        Returns:
            EmailAccount | None: Cuenta encontrada o None
        """
        return db_session.query(cls).filter(
            cls.user_id == user_id,
            cls.email == email
        ).first()
    
    @classmethod
    def get_by_user(cls, db_session, user_id: int) -> list['EmailAccount']:
        """
        Obtiene todas las cuentas de un usuario.
        
        Args:
            db_session: Sesión de base de datos
            user_id (int): ID del usuario
            
        Returns:
            list[EmailAccount]: Lista de cuentas del usuario
        """
        return db_session.query(cls).filter(cls.user_id == user_id).all()
    
    @classmethod
    def get_active_by_user(cls, db_session, user_id: int) -> list['EmailAccount']:
        """
        Obtiene todas las cuentas activas de un usuario.
        
        Args:
            db_session: Sesión de base de datos
            user_id (int): ID del usuario
            
        Returns:
            list[EmailAccount]: Lista de cuentas activas del usuario
        """
        return db_session.query(cls).filter(
            cls.user_id == user_id,
            cls.is_active == True
        ).all()
    
    @classmethod
    def get_all_active(cls, db_session) -> list['EmailAccount']:
        """
        Obtiene todas las cuentas activas del sistema.
        
        Args:
            db_session: Sesión de base de datos
            
        Returns:
            list[EmailAccount]: Lista de todas las cuentas activas
        """
        return db_session.query(cls).filter(cls.is_active == True).all()
    
    @classmethod
    def get_accounts_needing_health_check(cls, db_session, hours_threshold: int = 24) -> list['EmailAccount']:
        """
        Obtiene cuentas que necesitan verificación de salud.
        
        Args:
            db_session: Sesión de base de datos
            hours_threshold (int): Horas desde último check
            
        Returns:
            list[EmailAccount]: Lista de cuentas que necesitan verificación
        """
        threshold_time = datetime.now() - timedelta(hours=hours_threshold)
        
        return db_session.query(cls).filter(
            cls.is_active == True,
            (cls.last_health_check.is_(None) | (cls.last_health_check < threshold_time))
        ).all()
    
    @classmethod
    def count_by_user(cls, db_session, user_id: int) -> int:
        """
        Cuenta las cuentas de un usuario.
        
        Args:
            db_session: Sesión de base de datos
            user_id (int): ID del usuario
            
        Returns:
            int: Total de cuentas del usuario
        """
        return db_session.query(cls).filter(cls.user_id == user_id).count()
    
    @classmethod
    def count_active_by_user(cls, db_session, user_id: int) -> int:
        """
        Cuenta las cuentas activas de un usuario.
        
        Args:
            db_session: Sesión de base de datos
            user_id (int): ID del usuario
            
        Returns:
            int: Total de cuentas activas del usuario
        """
        return db_session.query(cls).filter(
            cls.user_id == user_id,
            cls.is_active == True
        ).count()
    
    # =============================================================================
    # MÉTODOS DE INSTANCIA
    # =============================================================================
    
    def update(self, db_session, **kwargs) -> None:
        """
        Actualiza los campos de la cuenta.
        
        Args:
            db_session: Sesión de base de datos
            **kwargs: Campos a actualizar
        """
        allowed_fields = {
            'email', 'imap_server', 'imap_port', 'smtp_server', 
            'smtp_port', 'encrypted_password', 'is_active',
            'oauth2_token', 'oauth2_refresh_token', 'auth_type'
        }
        
        for field, value in kwargs.items():
            if field in allowed_fields and hasattr(self, field):
                setattr(self, field, value)
        
        db_session.flush()
    
    def delete(self, db_session) -> None:
        """
        Elimina la cuenta de email de la base de datos.
        
        Args:
            db_session: Sesión de base de datos
        """
        db_session.delete(self)
        db_session.flush()
    
    def refresh_credentials(self, db_session, new_encrypted_password: str) -> None:
        """
        Actualiza las credenciales de la cuenta.
        
        Args:
            db_session: Sesión de base de datos
            new_encrypted_password (str): Nueva contraseña encriptada
        """
        self.encrypted_password = new_encrypted_password
        # Reset health status para forzar nueva verificación
        self.health_status = 'unknown'
        self.last_health_check = None
        db_session.flush()
    
    def get_config_for_connection(self) -> dict:
        """
        Obtiene la configuración completa para conexión.
        
        Returns:
            dict: Configuración completa IMAP/SMTP
        """
        return {
            'email': self.email,
            'imap': {
                'server': self.imap_server,
                'port': self.imap_port,
                'email': self.email
            },
            'smtp': {
                'server': self.smtp_server,
                'port': self.smtp_port,
                'email': self.email
            },
            'auth_type': self.auth_type,
            'is_oauth2': self.is_oauth2
            # Nota: No incluimos credenciales por seguridad
            # Debe obtenerse por separado cuando sea necesaria
        }
    
    def mark_as_tested(self, db_session, connection_successful: bool) -> None:
        """
        Marca la cuenta como probada y actualiza su estado.
        
        Args:
            db_session: Sesión de base de datos
            connection_successful (bool): Si la conexión fue exitosa
        """
        # Actualizar estado basado en resultado
        if connection_successful:
            self.activate()
            self.health_status = 'healthy'
        else:
            self.deactivate()
            self.health_status = 'error'
        
        self.last_health_check = datetime.now()
        db_session.flush()
    
    def get_user_info(self, db_session) -> dict:
        """
        Obtiene información del usuario propietario.
        
        Args:
            db_session: Sesión de base de datos
            
        Returns:
            dict: Información del usuario
        """
        if self.user:
            return {
                'user_id': self.user.id,
                'user_name': self.user.name,
                'user_email': self.user.email,
                'user_verified': self.user.is_verified
            }
        return {}