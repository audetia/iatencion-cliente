"""
Modelos Automation, ResponseAutomation y ForwardAutomation para el sistema de automatización de emails.

Este módulo define los modelos relacionados con las automatizaciones que
permiten a los usuarios configurar respuestas automáticas y reenvíos.
"""

from sqlalchemy import Column, Integer, String, Text, Boolean, ForeignKey, Enum as SQLEnum, Table
from sqlalchemy.orm import relationship
from datetime import datetime
from typing import List, Optional, Dict, Union
from enum import Enum

from .base import Base, TimestampMixin


class AutomationType(Enum):
    """
    Enum para tipos de automatización.
    
    Values:
        RESPONSE: Automatización de respuesta automática
        FORWARD: Automatización de reenvío de emails
    """
    RESPONSE = "response"
    FORWARD = "forward"


# NOTA: Ya no se usa tabla intermedia
# ResponseAutomation tiene question_id directamente, ForwardAutomation usa su campo description


class Automation(Base, TimestampMixin):
    """
    Modelo base para automatizaciones de email.
    
    Representa una automatización configurada por un usuario para procesar
    emails automáticamente, ya sea respondiendo o reenviando.
    
    Attributes:
        id (int): Identificador único de la automatización (clave primaria)
        user_id (int): ID del usuario propietario (clave foránea)
        email_account_id (int): ID de la cuenta de email asociada (clave foránea)
        type (AutomationType): Tipo de automatización ('response' o 'forward')
        is_active (bool): Estado activo de la automatización
        is_draft_mode (bool): Modo borrador (guarda los emails en la carpeta de borradores)
        created_at (datetime): Fecha de creación (automática)
        updated_at (datetime): Fecha de última actualización (automática)
    
    Relationships:
        user: Usuario propietario de la automatización
        email_account: Cuenta de email asociada
        response_automation: Detalles de automatización de respuesta (si aplica)
        forward_automation: Detalles de automatización de reenvío (si aplica)
        questions: Lista de preguntas asociadas a esta automatización
    """
    
    __tablename__ = 'automation'
    
    # Campos principales
    id = Column(Integer, primary_key=True, index=True)
    email_account_id = Column(Integer, ForeignKey('email_account.id'), nullable=False, index=True)
    type = Column(SQLEnum(AutomationType), nullable=False, index=True)
    is_active = Column(Boolean, default=True, nullable=False, index=True)
    is_draft_mode = Column(Boolean, default=False, nullable=False)
    
    # Relaciones
    email_account = relationship("EmailAccount")  # No back_populates por ahora
    response_automation = relationship("ResponseAutomation", back_populates="automation", uselist=False, cascade="all, delete-orphan")
    forward_automation = relationship("ForwardAutomation", back_populates="automation", uselist=False, cascade="all, delete-orphan")
    
    # Propiedad para acceder al usuario a través de email_account
    @property
    def user(self):
        """
        Obtiene el usuario a través de email_account.
        
        Returns:
            User | None: Usuario propietario de la automatización
        """
        return self.email_account.user if self.email_account else None
    
    def __repr__(self):
        """
        Representación string de la automatización.
        
        Returns:
            str: Representación legible de la automatización
        """
        if self.is_response_type and self.response_automation and self.response_automation.question:
            detail = f"question={self.response_automation.question.id}"
        elif self.is_forward_type and self.forward_automation:
            detail = f"forward_to={self.forward_automation.forward_to_email}"
        else:
            detail = "no_config"
        
        return f"<Automation({detail}, id={self.id}, type={self.type.value}, email_account_id={self.email_account_id}, active={self.is_active})>"
    
    def __str__(self):
        """
        String representation para uso general.
        
        Returns:
            str: Descripción de la automatización
        """
        type_name = "Respuesta" if self.type == AutomationType.RESPONSE else "Reenvío"
        status = "Activa" if self.is_active else "Inactiva"
        draft = " (Borrador)" if self.is_draft_mode else ""
        
        if self.is_response_type and self.response_automation and self.response_automation.question:
            detail = f"Q{self.response_automation.question.id}"
        elif self.is_forward_type and self.forward_automation:
            detail = f"→{self.forward_automation.forward_to_email}"
        else:
            detail = "Sin configurar"
        
        return f"{type_name} - {detail} - {status}{draft}"
    
    @property
    def is_response_type(self) -> bool:
        """
        Verifica si es una automatización de respuesta.
        
        Returns:
            bool: True si es de tipo respuesta
        """
        return self.type == AutomationType.RESPONSE
    
    @property
    def is_forward_type(self) -> bool:
        """
        Verifica si es una automatización de reenvío.
        
        Returns:
            bool: True si es de tipo reenvío
        """
        return self.type == AutomationType.FORWARD
    
    @property
    def user_id(self) -> Optional[int]:
        """
        Obtiene el user_id a través de email_account.
        
        Returns:
            int | None: ID del usuario propietario
        """
        return self.email_account.user_id if self.email_account else None
    
    @property
    def questions_count(self) -> int:
        """
        Cuenta el número de preguntas asociadas.
        Solo ResponseAutomation debería tener 1 pregunta, ForwardAutomation 0.
        
        Returns:
            int: Número de preguntas asociadas (0 o 1)
        """
        if self.is_response_type and self.response_automation:
            return 1 if self.response_automation.question else 0
        else:  # ForwardAutomation
            return 0
    
    @property
    def question(self):
        """
        Obtiene la pregunta asociada (solo para ResponseAutomation).
        
        Returns:
            Question | None: La pregunta asociada o None
        """
        if self.is_response_type and self.response_automation:
            return self.response_automation.question
        return None
    
    @property
    def display_name(self) -> str:
        """
        Nombre para mostrar de la automatización.
        
        Returns:
            str: Nombre descriptivo con iconos de estado
        """
        type_icon = "💬" if self.is_response_type else "📤"
        status_icon = "✅" if self.is_active else "⏸️"
        draft_icon = "📝" if self.is_draft_mode else ""
        
        return f"{type_icon} {self.type.value.title()} {status_icon}{draft_icon}"
    
    def activate(self) -> None:
        """
        Activa la automatización.
        
        Permite que la automatización procese emails automáticamente.
        """
        self.is_active = True
    
    def deactivate(self) -> None:
        """
        Desactiva la automatización.
        
        Detiene el procesamiento automático de emails para esta automatización.
        """
        self.is_active = False
    
    def toggle_active(self) -> bool:
        """
        Alterna el estado activo de la automatización.
        
        Returns:
            bool: Nuevo estado de la automatización
        """
        self.is_active = not self.is_active
        return self.is_active
    
    def enable_draft_mode(self) -> None:
        """
        Habilita el modo borrador.
        
        En modo borrador, la automatización procesa emails pero no envía respuestas reales.
        """
        self.is_draft_mode = True
    
    def disable_draft_mode(self) -> None:
        """
        Deshabilita el modo borrador.
        
        La automatización enviará emails reales cuando procese mensajes.
        """
        self.is_draft_mode = False
    
    def toggle_draft_mode(self) -> bool:
        """
        Alterna el modo borrador.
        
        Returns:
            bool: Nuevo estado del modo borrador
        """
        self.is_draft_mode = not self.is_draft_mode
        return self.is_draft_mode
    
    def to_dict(self, include_details: bool = False) -> dict:
        """
        Convierte la automatización a diccionario.
        
        Args:
            include_details (bool): Si incluir detalles específicos del tipo
        
        Returns:
            dict: Representación de la automatización como diccionario
        """
        result = {
            'id': self.id,
            'email_account_id': self.email_account_id,
            'type': self.type.value,
            'is_active': self.is_active,
            'is_draft_mode': self.is_draft_mode,
            'has_question': self.question is not None,
            'created_at': self.created_at.isoformat() if self.created_at else None,
            'updated_at': self.updated_at.isoformat() if self.updated_at else None
        }
        
        if include_details:
            if self.is_response_type and self.response_automation:
                result['response_details'] = self.response_automation.to_dict()
            elif self.is_forward_type and self.forward_automation:
                result['forward_details'] = self.forward_automation.to_dict()
        
        return result
    
    def get_detailed_info(self, db_session) -> dict:
        """
        Obtiene información detallada de la automatización.
        
        Args:
            db_session: Sesión de base de datos
            
        Returns:
            dict: Información completa de la automatización
        """
        try:
            info = self.to_dict(include_details=True)
            
            # Añadir información del usuario y cuenta de email
            if self.user:
                info['user_info'] = {
                    'name': self.user.name,
                    'email': self.user.email
                }
            
            if self.email_account:
                info['email_account_info'] = {
                    'email': self.email_account.email,
                    'is_active': self.email_account.is_active
                }
            
            return info
            
        except Exception as e:
            return {
                'id': self.id,
                'error': f"Error obteniendo información detallada: {str(e)}"
            }
    
    # =============================================================================
    # MÉTODOS DE CONSULTA (CLASS METHODS)
    # =============================================================================
    
    @classmethod
    def create_response_automation(cls, db_session, email_account_id: int, 
                                 question_id: int, tone: str = 'professional',
                                 custom_instructions: str = None, is_draft_mode: bool = False) -> 'Automation':
        """
        Crea una nueva automatización de respuesta.
        
        Args:
            db_session: Sesión de base de datos
            email_account_id (int): ID de la cuenta de email
            question_id (int): ID de la pregunta asociada (solo una)
            tone (str): Tono de respuesta ('professional', 'casual', 'friendly')
            custom_instructions (str): Instrucciones personalizadas
            is_draft_mode (bool): Modo borrador
            
        Returns:
            Automation: Automatización de respuesta creada
        """
        # Obtener email_account para validar usuario
        from .email_account import EmailAccount
        email_account = db_session.query(EmailAccount).filter(
            EmailAccount.id == email_account_id
        ).first()
        
        if not email_account:
            raise ValueError(f"Cuenta de email {email_account_id} no encontrada")
        
        # Validar que la pregunta pertenece al usuario
        from .qa import Question
        question = db_session.query(Question).filter(
            Question.id == question_id,
            Question.user_id == email_account.user_id
        ).first()
        
        if not question:
            raise ValueError(f"Pregunta {question_id} no encontrada o no pertenece al usuario {email_account.user_id}")
        
        # Crear automatización base
        automation = cls(
            email_account_id=email_account_id,
            type=AutomationType.RESPONSE,
            is_draft_mode=is_draft_mode
        )
        db_session.add(automation)
        db_session.flush()  # Necesario para obtener el ID
        
        # Crear detalles de respuesta con la pregunta asociada
        response_automation = ResponseAutomation.create(
            db_session, automation.id, question_id, tone, custom_instructions
        )
        
        return automation
    
    @classmethod
    def create_forward_automation(cls, db_session, email_account_id: int,
                                forward_to_email: str, description: str = None) -> 'Automation':
        """
        Crea una nueva automatización de reenvío.
        
        Args:
            db_session: Sesión de base de datos
            email_account_id (int): ID de la cuenta de email
            forward_to_email (str): Email de destino para reenvío
            description (str): Descripción del criterio de reenvío
            
        Returns:
            Automation: Automatización de reenvío creada
        """
        # Crear automatización base
        automation = cls(
            email_account_id=email_account_id,
            type=AutomationType.FORWARD
        )
        db_session.add(automation)
        db_session.flush()  # Necesario para obtener el ID
        
        # Crear detalles de reenvío
        forward_automation = ForwardAutomation.create(
            db_session, automation.id, forward_to_email, description
        )
        
        return automation
    
    @classmethod
    def get_by_id(cls, db_session, automation_id: int) -> Optional['Automation']:
        """
        Obtiene una automatización por su ID.
        
        Args:
            db_session: Sesión de base de datos
            automation_id (int): ID de la automatización
            
        Returns:
            Automation | None: Automatización encontrada o None
        """
        return db_session.query(cls).filter(cls.id == automation_id).first()
    
    @classmethod
    def get_by_user(cls, db_session, user_id: int) -> List['Automation']:
        """
        Obtiene todas las automatizaciones de un usuario.
        
        Args:
            db_session: Sesión de base de datos
            user_id (int): ID del usuario
            
        Returns:
            List[Automation]: Lista de automatizaciones del usuario
        """
        from .email_account import EmailAccount
        return db_session.query(cls).join(EmailAccount).filter(
            EmailAccount.user_id == user_id
        ).all()
    
    @classmethod
    def get_active_by_user(cls, db_session, user_id: int) -> List['Automation']:
        """
        Obtiene las automatizaciones activas de un usuario.
        
        Args:
            db_session: Sesión de base de datos
            user_id (int): ID del usuario
            
        Returns:
            List[Automation]: Lista de automatizaciones activas
        """
        from .email_account import EmailAccount
        return db_session.query(cls).join(EmailAccount).filter(
            EmailAccount.user_id == user_id,
            cls.is_active == True
        ).all()
    
    @classmethod
    def get_by_email_account(cls, db_session, email_account_id: int) -> List['Automation']:
        """
        Obtiene todas las automatizaciones de una cuenta de email.
        
        Args:
            db_session: Sesión de base de datos
            email_account_id (int): ID de la cuenta de email
            
        Returns:
            List[Automation]: Lista de automatizaciones de la cuenta
        """
        return db_session.query(cls).filter(cls.email_account_id == email_account_id).all()
    
    @classmethod
    def get_active_by_email_account(cls, db_session, email_account_id: int) -> List['Automation']:
        """
        Obtiene las automatizaciones activas de una cuenta de email.
        
        Args:
            db_session: Sesión de base de datos
            email_account_id (int): ID de la cuenta de email
            
        Returns:
            List[Automation]: Lista de automatizaciones activas de la cuenta
        """
        return db_session.query(cls).filter(
            cls.email_account_id == email_account_id,
            cls.is_active == True
        ).all()
    
    @classmethod
    def get_by_type(cls, db_session, automation_type: AutomationType, user_id: int = None) -> List['Automation']:
        """
        Obtiene automatizaciones por tipo.
        
        Args:
            db_session: Sesión de base de datos
            automation_type (AutomationType): Tipo de automatización
            user_id (int, optional): ID del usuario para filtrar
            
        Returns:
            List[Automation]: Lista de automatizaciones del tipo especificado
        """
        query = db_session.query(cls).filter(cls.type == automation_type)
        
        if user_id:
            from .email_account import EmailAccount
            query = query.join(EmailAccount).filter(EmailAccount.user_id == user_id)
        
        return query.all()
    
    @classmethod
    def count_by_user(cls, db_session, user_id: int) -> int:
        """
        Cuenta las automatizaciones de un usuario.
        
        Args:
            db_session: Sesión de base de datos
            user_id (int): ID del usuario
            
        Returns:
            int: Número de automatizaciones del usuario
        """
        from .email_account import EmailAccount
        return db_session.query(cls).join(EmailAccount).filter(
            EmailAccount.user_id == user_id
        ).count()
    
    @classmethod
    def count_active_by_user(cls, db_session, user_id: int) -> int:
        """
        Cuenta las automatizaciones activas de un usuario.
        
        Args:
            db_session: Sesión de base de datos
            user_id (int): ID del usuario
            
        Returns:
            int: Número de automatizaciones activas del usuario
        """
        from .email_account import EmailAccount
        return db_session.query(cls).join(EmailAccount).filter(
            EmailAccount.user_id == user_id,
            cls.is_active == True
        ).count()
    
    # =============================================================================
    # MÉTODOS DE INSTANCIA
    # =============================================================================
    
    def update(self, db_session, **kwargs) -> None:
        """
        Actualiza los campos de la automatización.
        
        Args:
            db_session: Sesión de base de datos
            **kwargs: Campos a actualizar
        """
        allowed_fields = {'is_active', 'is_draft_mode'}
        
        for field, value in kwargs.items():
            if field in allowed_fields and hasattr(self, field):
                setattr(self, field, value)
        
        db_session.flush()
    
    def delete(self, db_session) -> None:
        """
        Elimina la automatización de la base de datos.
        
        Args:
            db_session: Sesión de base de datos
            
        Note:
            Esto también eliminará los detalles específicos (response/forward)
            debido al cascade="all, delete-orphan".
        """
        db_session.delete(self)
        db_session.flush()
    
    def set_question(self, db_session, question_id: int) -> bool:
        """
        Establece la pregunta para una automatización de respuesta.
        Solo válido para ResponseAutomation.
        
        Args:
            db_session: Sesión de base de datos
            question_id (int): ID de la pregunta a asociar
            
        Returns:
            bool: True si se estableció correctamente
            
        Raises:
            ValueError: Si no es ResponseAutomation o la pregunta no es válida
        """
        if not self.is_response_type or not self.response_automation:
            raise ValueError("Solo las automatizaciones de respuesta pueden tener preguntas asociadas")
        
        from .qa import Question
        
        # Validar que la pregunta pertenece al usuario
        question = db_session.query(Question).filter(
            Question.id == question_id,
            Question.user_id == self.user_id
        ).first()
        
        if not question:
            raise ValueError(f"Pregunta {question_id} no encontrada o no pertenece al usuario {self.user_id}")
        
        # Establecer la pregunta en response_automation
        self.response_automation.question_id = question_id
        db_session.flush()
        
        return True
    
    def remove_question(self, db_session) -> bool:
        """
        Remueve la pregunta asociada de una automatización de respuesta.
        
        Args:
            db_session: Sesión de base de datos
            
        Returns:
            bool: True si se removió correctamente
        """
        if not self.is_response_type or not self.response_automation:
            return False
        
        self.response_automation.question_id = None
        db_session.flush()
        
        return True
    
    def validate_configuration(self) -> Dict[str, Union[bool, str, List[str]]]:
        """
        Valida que la configuración de la automatización sea consistente.
        
        Returns:
            dict: Resultado de la validación con errores si los hay
        """
        errors = []
        
        # Validaciones para ResponseAutomation
        if self.is_response_type:
            if not self.response_automation:
                errors.append("ResponseAutomation debe tener detalles de respuesta")
            elif not self.response_automation.question_id:
                errors.append("ResponseAutomation debe tener una pregunta asociada")
            
            if self.forward_automation:
                errors.append("ResponseAutomation no debe tener detalles de reenvío")
        
        # Validaciones para ForwardAutomation
        elif self.is_forward_type:
            if not self.forward_automation:
                errors.append("ForwardAutomation debe tener detalles de reenvío")
            
            if self.response_automation:
                errors.append("ForwardAutomation no debe tener detalles de respuesta")
        
        return {
            'is_valid': len(errors) == 0,
            'errors': errors,
            'automation_id': self.id,
            'automation_type': self.type.value if self.type else None
        }


class ResponseAutomation(Base):
    """
    Modelo para detalles de automatización de respuesta.
    
    Contiene la configuración específica para automatizaciones que
    responden automáticamente a emails basándose en preguntas y respuestas.
    
    Attributes:
        id (int): Identificador único (clave primaria)
        automation_id (int): ID de la automatización base (clave foránea única)
        tone (str): Tono de respuesta ('professional', 'casual', 'friendly')
        custom_instructions (str): Instrucciones personalizadas para la respuesta
    
    Relationships:
        automation: Automatización base asociada
    """
    
    __tablename__ = 'response_automation'
    
    # Campos principales
    id = Column(Integer, primary_key=True, index=True)
    automation_id = Column(Integer, ForeignKey('automation.id'), nullable=False, unique=True)
    question_id = Column(Integer, ForeignKey('question.id'), nullable=False, unique=True)
    tone = Column(String(50), default='professional')
    custom_instructions = Column(Text)
    
    # Relaciones
    automation = relationship("Automation", back_populates="response_automation")
    question = relationship("Question")
    
    def __repr__(self):
        """
        Representación string de la automatización de respuesta.
        
        Returns:
            str: Representación legible
        """
        return f"<ResponseAutomation(id={self.id}, automation_id={self.automation_id}, tone='{self.tone}')>"
    
    def __str__(self):
        """
        String representation para uso general.
        
        Returns:
            str: Descripción del tono y instrucciones
        """
        tone_display = self.tone.title()
        has_instructions = " (con instrucciones)" if self.custom_instructions else ""
        return f"Tono: {tone_display}{has_instructions}"
    
    @property
    def has_custom_instructions(self) -> bool:
        """
        Verifica si tiene instrucciones personalizadas.
        
        Returns:
            bool: True si tiene instrucciones personalizadas
        """
        return bool(self.custom_instructions and self.custom_instructions.strip())
    
    def to_dict(self) -> dict:
        """
        Convierte a diccionario.
        
        Returns:
            dict: Representación como diccionario
        """
        return {
            'id': self.id,
            'automation_id': self.automation_id,
            'question_id': self.question_id,
            'tone': self.tone,
            'custom_instructions': self.custom_instructions,
            'has_custom_instructions': self.has_custom_instructions,
            'question': self.question.to_dict() if self.question else None
        }
    
    # =============================================================================
    # MÉTODOS DE CONSULTA (CLASS METHODS)
    # =============================================================================
    
    @classmethod
    def create(cls, db_session, automation_id: int, question_id: int, 
               tone: str = 'professional', custom_instructions: str = None) -> 'ResponseAutomation':
        """
        Crea una nueva automatización de respuesta.
        
        Args:
            db_session: Sesión de base de datos
            automation_id (int): ID de la automatización base
            question_id (int): ID de la pregunta asociada
            tone (str): Tono de respuesta
            custom_instructions (str): Instrucciones personalizadas
            
        Returns:
            ResponseAutomation: Automatización de respuesta creada
        """
        response_automation = cls(
            automation_id=automation_id,
            question_id=question_id,
            tone=tone,
            custom_instructions=custom_instructions
        )
        db_session.add(response_automation)
        db_session.flush()
        return response_automation
    
    @classmethod
    def get_by_automation_id(cls, db_session, automation_id: int) -> Optional['ResponseAutomation']:
        """
        Obtiene automatización de respuesta por ID de automatización.
        
        Args:
            db_session: Sesión de base de datos
            automation_id (int): ID de la automatización
            
        Returns:
            ResponseAutomation | None: Automatización encontrada o None
        """
        return db_session.query(cls).filter(cls.automation_id == automation_id).first()
    
    # =============================================================================
    # MÉTODOS DE INSTANCIA
    # =============================================================================
    
    def update(self, db_session, **kwargs) -> None:
        """
        Actualiza los campos de la automatización de respuesta.
        
        Args:
            db_session: Sesión de base de datos
            **kwargs: Campos a actualizar (tone, custom_instructions)
        """
        allowed_fields = {'question_id', 'tone', 'custom_instructions'}
        
        for field, value in kwargs.items():
            if field in allowed_fields and hasattr(self, field):
                setattr(self, field, value)
        
        db_session.flush()


class ForwardAutomation(Base):
    """
    Modelo para detalles de automatización de reenvío.
    
    Contiene la configuración específica para automatizaciones que
    reenvían emails a otras direcciones basándose en criterios específicos.
    
    Attributes:
        id (int): Identificador único (clave primaria)
        automation_id (int): ID de la automatización base (clave foránea única)
        forward_to_email (str): Email de destino para el reenvío
        description (str): Descripción del criterio de reenvío (máximo 255 caracteres)
    
    Relationships:
        automation: Automatización base asociada
    """
    
    __tablename__ = 'forward_automation'
    
    # Campos principales
    id = Column(Integer, primary_key=True, index=True)
    automation_id = Column(Integer, ForeignKey('automation.id'), nullable=False, unique=True)
    forward_to_email = Column(String(255), nullable=False)
    description = Column(String(255))
    
    # Relaciones
    automation = relationship("Automation", back_populates="forward_automation")
    
    def __repr__(self):
        """
        Representación string de la automatización de reenvío.
        
        Returns:
            str: Representación legible
        """
        return f"<ForwardAutomation(id={self.id}, automation_id={self.automation_id}, forward_to='{self.forward_to_email}')>"
    
    def __str__(self):
        """
        String representation para uso general.
        
        Returns:
            str: Descripción del reenvío
        """
        desc = f" - {self.description}" if self.description else ""
        return f"Reenviar a: {self.forward_to_email}{desc}"
    
    @property
    def has_description(self) -> bool:
        """
        Verifica si tiene descripción.
        
        Returns:
            bool: True si tiene descripción
        """
        return bool(self.description and self.description.strip())
    
    def to_dict(self) -> dict:
        """
        Convierte a diccionario.
        
        Returns:
            dict: Representación como diccionario
        """
        return {
            'id': self.id,
            'automation_id': self.automation_id,
            'forward_to_email': self.forward_to_email,
            'description': self.description,
            'has_description': self.has_description
        }
    
    # =============================================================================
    # MÉTODOS DE CONSULTA (CLASS METHODS)
    # =============================================================================
    
    @classmethod
    def create(cls, db_session, automation_id: int, forward_to_email: str,
               description: str = None) -> 'ForwardAutomation':
        """
        Crea una nueva automatización de reenvío.
        
        Args:
            db_session: Sesión de base de datos
            automation_id (int): ID de la automatización base
            forward_to_email (str): Email de destino
            description (str): Descripción del criterio
            
        Returns:
            ForwardAutomation: Automatización de reenvío creada
        """
        # Validar longitud de descripción
        if description and len(description) > 255:
            description = description[:255]
        
        forward_automation = cls(
            automation_id=automation_id,
            forward_to_email=forward_to_email,
            description=description
        )
        db_session.add(forward_automation)
        db_session.flush()
        return forward_automation
    
    @classmethod
    def get_by_automation_id(cls, db_session, automation_id: int) -> Optional['ForwardAutomation']:
        """
        Obtiene automatización de reenvío por ID de automatización.
        
        Args:
            db_session: Sesión de base de datos
            automation_id (int): ID de la automatización
            
        Returns:
            ForwardAutomation | None: Automatización encontrada o None
        """
        return db_session.query(cls).filter(cls.automation_id == automation_id).first()
    
    # =============================================================================
    # MÉTODOS DE INSTANCIA
    # =============================================================================
    
    def update(self, db_session, **kwargs) -> None:
        """
        Actualiza los campos de la automatización de reenvío.
        
        Args:
            db_session: Sesión de base de datos
            **kwargs: Campos a actualizar (forward_to_email, description)
        """
        allowed_fields = {'forward_to_email', 'description'}
        
        for field, value in kwargs.items():
            if field in allowed_fields and hasattr(self, field):
                # Validar longitud de descripción
                if field == 'description' and value and len(value) > 255:
                    value = value[:255]
                setattr(self, field, value)
        
        db_session.flush()
