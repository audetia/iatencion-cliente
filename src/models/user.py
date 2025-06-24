"""
Modelo User para el sistema de automatización de emails.

Este módulo define el modelo de usuario que representa a los usuarios
registrados en el sistema con sus datos básicos y estado de verificación.
"""

from sqlalchemy import Column, Integer, String, Boolean
from sqlalchemy.orm import relationship
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
    
    # Relaciones (se definirán cuando se implementen los otros modelos)
    # email_accounts = relationship("EmailAccount", back_populates="user")
    # questions = relationship("Question", back_populates="user")
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