"""
Modelo User para el sistema de automatización de emails.

Este módulo define el modelo de usuario que representa a los usuarios
registrados en el sistema con sus datos básicos y estado de verificación.
"""

from sqlalchemy import Column, Integer, String, Boolean
from sqlalchemy.orm import relationship
from datetime import datetime, timedelta
from typing import Optional, Dict, List, Union
from .base import Base, TimestampMixin


class User(Base, TimestampMixin):
    """
    Modelo de Usuario.
    
    Representa a un usuario registrado en el sistema de automatización
    de emails con sus datos básicos y estado de verificación.
    
    Attributes:
        id (int): Identificador único del usuario (clave primaria)
        email (str): Dirección de email del usuario (único)
        name (str): Nombre completo del usuario
        is_verified (bool): Estado de verificación del email
        created_at (datetime): Fecha de creación (automática)
        updated_at (datetime): Fecha de última actualización (automática)
    
    Relationships:
        email_accounts: Lista de cuentas de email asociadas al usuario
        questions: Lista de preguntas creadas por el usuario
        automations: Lista de automatizaciones configuradas por el usuario
        subscriptions: Lista de suscripciones del usuario
        email_processed: Lista de emails procesados para el usuario
        user_usage_monthly: Estadísticas de uso mensual del usuario
    """
    
    __tablename__ = 'users'
    
    # Campos principales
    id = Column(Integer, primary_key=True, index=True)
    email = Column(String(255), unique=True, index=True, nullable=False)
    name = Column(String(255), nullable=False)
    is_verified = Column(Boolean, default=False, nullable=False)
    
    # Relaciones
    email_accounts = relationship("EmailAccount", back_populates="user", cascade="all, delete-orphan")
    questions = relationship("Question", back_populates="user")
    # Relaciones futuras (se activarán cuando se implementen los otros modelos)
    # automations = relationship("Automation", back_populates="user")
    # subscriptions = relationship("Subscription", back_populates="user")
    # email_processed = relationship("EmailProcessed", back_populates="user")
    # user_usage_monthly = relationship("UserUsageMonthly", back_populates="user")
    
    def __repr__(self):
        """
        Representación string del usuario.
        
        Returns:
            str: Representación legible del usuario
        """
        return f"<User(id={self.id}, email='{self.email}', name='{self.name}', verified={self.is_verified})>"
    
    def __str__(self):
        """
        String representation para uso general.
        
        Returns:
            str: Nombre y email del usuario
        """
        return f"{self.name} ({self.email})"
    
    @property
    def is_active(self) -> bool:
        """
        Verifica si el usuario está activo.
        
        Un usuario está activo si está verificado.
        
        Returns:
            bool: True si el usuario está activo
        """
        return self.is_verified
    
    def verify(self) -> None:
        """
        Marca al usuario como verificado.
        
        Este método se llama después de que el usuario
        verifica su email durante el registro.
        """
        self.is_verified = True
    
    def to_dict(self) -> dict:
        """
        Convierte el usuario a diccionario.
        
        Útil para serialización JSON en la API.
        
        Returns:
            dict: Representación del usuario como diccionario
        """
        return {
            'id': self.id,
            'email': self.email,
            'name': self.name,
            'is_verified': self.is_verified,
            'created_at': self.created_at.isoformat() if self.created_at else None,
            'updated_at': self.updated_at.isoformat() if self.updated_at else None
        }
    
    @classmethod
    def from_dict(cls, data: dict) -> 'User':
        """
        Crea un usuario desde un diccionario.
        
        Args:
            data (dict): Datos del usuario
            
        Returns:
            User: Nueva instancia de usuario
        """
        return cls(
            email=data.get('email'),
            name=data.get('name'),
            is_verified=data.get('is_verified', False)
        )
    
    def can_process_email(self, db_session) -> Dict[str, Union[bool, str, dict]]:
        """
        Verifica si el usuario puede procesar más emails según sus límites de suscripción.
        
        Args:
            db_session: Sesión de base de datos
            
        Returns:
            dict: Información sobre si puede procesar y detalles de uso
        """
        try:
            # TODO: Implementar cuando existan los modelos de suscripción
            # Por ahora, usar límites por defecto para plan gratuito
            default_limits = {
                'emails_per_month': 100,
                'qa_pairs': 10,
                'email_accounts': 2
            }
            
            current_month = datetime.now().replace(day=1, hour=0, minute=0, second=0, microsecond=0)
            
            # Calcular uso actual (placeholder - implementar con modelos reales)
            current_usage = {
                'emails_processed': 0,  # TODO: Contar desde email_processed
                'qa_pairs': len(self.questions) if self.questions else 0,
                'email_accounts': len(self.email_accounts) if self.email_accounts else 0
            }
            
            # Verificar límites
            can_process_email = current_usage['emails_processed'] < default_limits['emails_per_month']
            can_add_qa = current_usage['qa_pairs'] < default_limits['qa_pairs']
            can_add_account = current_usage['email_accounts'] < default_limits['email_accounts']
            
            usage_percentage = (current_usage['emails_processed'] / default_limits['emails_per_month']) * 100
            
            reason = None
            if not can_process_email:
                reason = f"Límite mensual de {default_limits['emails_per_month']} emails alcanzado"
            
            return {
                'can_process': can_process_email,
                'reason': reason,
                'usage_info': {
                    'current_usage': current_usage,
                    'limits': default_limits,
                    'usage_percentage': usage_percentage,
                    'can_add_qa': can_add_qa,
                    'can_add_account': can_add_account
                }
            }
            
        except Exception as e:
            return {
                'can_process': False,
                'reason': f"Error verificando límites: {str(e)}",
                'usage_info': {}
            }
    
    def get_comprehensive_stats(self, db_session, date_range: tuple = None) -> Dict[str, Union[int, float, dict]]:
        """
        Obtiene estadísticas completas del usuario.
        
        Args:
            db_session: Sesión de base de datos
            date_range (tuple, optional): Tupla (fecha_inicio, fecha_fin)
            
        Returns:
            dict: Estadísticas completas del usuario
        """
        try:
            if not date_range:
                # Últimos 30 días por defecto
                end_date = datetime.now()
                start_date = end_date - timedelta(days=30)
                date_range = (start_date, end_date)
            
            start_date, end_date = date_range
            
            # Estadísticas básicas
            total_email_accounts = len(self.email_accounts) if self.email_accounts else 0
            active_email_accounts = len(self.get_active_email_accounts(db_session))
            total_qa_pairs = len(self.questions) if self.questions else 0
            qa_with_answers = len([q for q in (self.questions or []) if q.has_answer])
            
            # TODO: Implementar cuando existan los modelos de estadísticas
            emails_processed = 0
            emails_responded = 0
            emails_forwarded = 0
            emails_spam = 0
            
            # Calcular tiempo ahorrado (5 min por email procesado)
            time_saved_minutes = emails_processed * 5
            time_saved_hours = time_saved_minutes / 60
            
            # Tasa de automatización
            automation_rate = (emails_responded + emails_forwarded) / max(emails_processed, 1) * 100
            
            return {
                'user_info': {
                    'id': self.id,
                    'name': self.name,
                    'email': self.email,
                    'verified': self.is_verified,
                    'member_since': self.created_at.isoformat() if self.created_at else None
                },
                'accounts': {
                    'total': total_email_accounts,
                    'active': active_email_accounts,
                    'inactive': total_email_accounts - active_email_accounts
                },
                'qa_system': {
                    'total_questions': total_qa_pairs,
                    'questions_with_answers': qa_with_answers,
                    'completion_rate': (qa_with_answers / max(total_qa_pairs, 1)) * 100
                },
                'email_processing': {
                    'total_processed': emails_processed,
                    'responded': emails_responded,
                    'forwarded': emails_forwarded,
                    'spam_detected': emails_spam,
                    'automation_rate': automation_rate
                },
                'time_saved': {
                    'minutes': time_saved_minutes,
                    'hours': round(time_saved_hours, 2),
                    'days': round(time_saved_hours / 24, 2)
                },
                'date_range': {
                    'start': start_date.isoformat(),
                    'end': end_date.isoformat(),
                    'days': (end_date - start_date).days
                }
            }
            
        except Exception as e:
            return {
                'error': f"Error calculando estadísticas: {str(e)}",
                'user_info': {'id': self.id, 'name': self.name, 'email': self.email}
            }
    
    def get_setup_status(self, db_session) -> Dict[str, Union[bool, int, List[str]]]:
        """
        Obtiene el estado de configuración del usuario.
        
        Args:
            db_session: Sesión de base de datos
            
        Returns:
            dict: Estado de configuración completo
        """
        try:
            # Verificar componentes de configuración
            has_email_account = len(self.email_accounts) > 0 if self.email_accounts else False
            has_active_email_account = len(self.get_active_email_accounts(db_session)) > 0
            has_qa_pairs = len(self.questions) > 0 if self.questions else False
            has_qa_with_answers = any(q.has_answer for q in (self.questions or []))
            
            # TODO: Verificar automatizaciones cuando se implementen
            has_automations = False
            has_active_automations = False
            
            # Calcular progreso de configuración
            setup_steps = [
                has_email_account,
                has_active_email_account,
                has_qa_pairs,
                has_qa_with_answers,
                has_automations
            ]
            
            completed_steps = sum(setup_steps)
            total_steps = len(setup_steps)
            setup_percentage = (completed_steps / total_steps) * 100
            
            # Determinar si la configuración está completa
            setup_complete = all([
                has_active_email_account,
                has_qa_with_answers or has_automations  # Al menos Q&A o automatizaciones
            ])
            
            # Generar lista de pasos pendientes
            pending_steps = []
            if not has_email_account:
                pending_steps.append("Añadir cuenta de email")
            elif not has_active_email_account:
                pending_steps.append("Activar cuenta de email")
            
            if not has_qa_pairs:
                pending_steps.append("Crear preguntas y respuestas")
            elif not has_qa_with_answers:
                pending_steps.append("Completar respuestas para las preguntas")
            
            if not has_automations:
                pending_steps.append("Configurar automatizaciones")
            
            return {
                'setup_complete': setup_complete,
                'setup_percentage': round(setup_percentage, 1),
                'completed_steps': completed_steps,
                'total_steps': total_steps,
                'components': {
                    'email_account': has_email_account,
                    'active_email_account': has_active_email_account,
                    'qa_pairs': has_qa_pairs,
                    'qa_with_answers': has_qa_with_answers,
                    'automations': has_automations,
                    'active_automations': has_active_automations
                },
                'pending_steps': pending_steps,
                'next_recommended_action': pending_steps[0] if pending_steps else "Configuración completa"
            }
            
        except Exception as e:
            return {
                'setup_complete': False,
                'error': f"Error verificando configuración: {str(e)}",
                'setup_percentage': 0,
                'pending_steps': ["Error en verificación"]
            }
    
    # =============================================================================
    # MÉTODOS DE CONSULTA (CLASS METHODS)
    # =============================================================================
    
    @classmethod
    def create(cls, db_session, email: str, name: str) -> 'User':
        """
        Crea un nuevo usuario en la base de datos.
        
        Args:
            db_session: Sesión de base de datos
            email (str): Email del usuario
            name (str): Nombre del usuario
            
        Returns:
            User: Usuario creado
            
        Raises:
            ValueError: Si el email ya existe
        """
        # Verificar si el email ya existe
        existing_user = cls.get_by_email(db_session, email)
        if existing_user:
            raise ValueError(f"Ya existe un usuario con el email: {email}")
        
        user = cls(email=email, name=name)
        db_session.add(user)
        db_session.flush()  # Para obtener el ID
        return user
    
    @classmethod
    def get_by_id(cls, db_session, user_id: int) -> Optional['User']:
        """
        Obtiene un usuario por su ID.
        
        Args:
            db_session: Sesión de base de datos
            user_id (int): ID del usuario
            
        Returns:
            User | None: Usuario encontrado o None
        """
        return db_session.query(cls).filter(cls.id == user_id).first()
    
    @classmethod
    def get_by_email(cls, db_session, email: str) -> Optional['User']:
        """
        Obtiene un usuario por su email.
        
        Args:
            db_session: Sesión de base de datos
            email (str): Email del usuario
            
        Returns:
            User | None: Usuario encontrado o None
        """
        return db_session.query(cls).filter(cls.email == email).first()
    
    @classmethod
    def get_all_verified(cls, db_session) -> list['User']:
        """
        Obtiene todos los usuarios verificados.
        
        Args:
            db_session: Sesión de base de datos
            
        Returns:
            list[User]: Lista de usuarios verificados
        """
        return db_session.query(cls).filter(cls.is_verified == True).all()
    
    @classmethod
    def get_all_unverified(cls, db_session) -> list['User']:
        """
        Obtiene todos los usuarios no verificados.
        
        Args:
            db_session: Sesión de base de datos
            
        Returns:
            list[User]: Lista de usuarios no verificados
        """
        return db_session.query(cls).filter(cls.is_verified == False).all()
    
    @classmethod
    def count_total(cls, db_session) -> int:
        """
        Cuenta el total de usuarios.
        
        Args:
            db_session: Sesión de base de datos
            
        Returns:
            int: Total de usuarios
        """
        return db_session.query(cls).count()
    
    @classmethod
    def count_verified(cls, db_session) -> int:
        """
        Cuenta los usuarios verificados.
        
        Args:
            db_session: Sesión de base de datos
            
        Returns:
            int: Total de usuarios verificados
        """
        return db_session.query(cls).filter(cls.is_verified == True).count()
    
    # =============================================================================
    # MÉTODOS DE INSTANCIA
    # =============================================================================
    
    def update(self, db_session, **kwargs) -> None:
        """
        Actualiza los campos del usuario.
        
        Args:
            db_session: Sesión de base de datos
            **kwargs: Campos a actualizar (name, email, is_verified)
        """
        allowed_fields = {'name', 'email', 'is_verified'}
        
        for field, value in kwargs.items():
            if field in allowed_fields and hasattr(self, field):
                setattr(self, field, value)
        
        db_session.flush()
    
    def delete(self, db_session) -> None:
        """
        Elimina el usuario de la base de datos.
        
        Args:
            db_session: Sesión de base de datos
            
        Note:
            Esto también eliminará todas las cuentas de email asociadas
            debido al cascade="all, delete-orphan".
        """
        db_session.delete(self)
        db_session.flush()
    
    def get_active_email_accounts(self, db_session) -> list:
        """
        Obtiene todas las cuentas de email activas del usuario.
        
        Args:
            db_session: Sesión de base de datos
            
        Returns:
            list[EmailAccount]: Lista de cuentas activas
        """
        from .email_account import EmailAccount
        return db_session.query(EmailAccount).filter(
            EmailAccount.user_id == self.id,
            EmailAccount.is_active == True
        ).all()
    
    def has_email_account(self, db_session, email: str) -> bool:
        """
        Verifica si el usuario ya tiene una cuenta con ese email.
        
        Args:
            db_session: Sesión de base de datos
            email (str): Email a verificar
            
        Returns:
            bool: True si ya tiene esa cuenta
        """
        from .email_account import EmailAccount
        account = db_session.query(EmailAccount).filter(
            EmailAccount.user_id == self.id,
            EmailAccount.email == email
        ).first()
        return account is not None
    
    def get_stats_summary(self, db_session) -> dict:
        """
        Obtiene un resumen de estadísticas del usuario.
        
        Args:
            db_session: Sesión de base de datos
            
        Returns:
            dict: Resumen de estadísticas
        """
        from .email_account import EmailAccount
        
        total_accounts = len(self.email_accounts)
        active_accounts = len(self.get_active_email_accounts(db_session))
        
        return {
            'user_id': self.id,
            'email': self.email,
            'name': self.name,
            'is_verified': self.is_verified,
            'total_email_accounts': total_accounts,
            'active_email_accounts': active_accounts,
            'created_at': self.created_at,
            'updated_at': self.updated_at
        }