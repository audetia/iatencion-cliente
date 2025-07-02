"""
Modelos EmailProcessed y UserUsageMonthly para el sistema de automatización de emails.

Este módulo define los modelos relacionados con las estadísticas y tracking de uso
que permiten registrar emails procesados y agregar estadísticas mensuales por usuario.
"""

from sqlalchemy import Column, Integer, String, Boolean, ForeignKey, DateTime, Text, CheckConstraint, UniqueConstraint
from sqlalchemy.orm import relationship
from datetime import datetime, timedelta
from typing import Optional, Dict, List, Union, Tuple
from enum import Enum

from .base import Base


class EmailActionType(Enum):
    """
    Enum para tipos de acciones realizadas en emails.
    
    Values:
        RESPONDED: Email fue respondido automáticamente
        FORWARDED: Email fue reenviado
        CATEGORIZED: Email fue categorizado solamente
        IGNORED: Email fue marcado como spam/ignorado
    """
    RESPONDED = "responded"
    FORWARDED = "forwarded"
    CATEGORIZED = "categorized"
    IGNORED = "ignored"


class EmailProcessed(Base):
    """
    Modelo para registro de emails procesados.
    
    Registra cada email que ha sido procesado por el sistema, incluyendo
    las acciones tomadas y estadísticas asociadas.
    
    Attributes:
        id (int): Identificador único del registro (clave primaria)
        email_account_id (int): ID de la cuenta de email que procesó el email (clave foránea)
        processed_at (datetime): Fecha y hora de procesamiento del email
        email_responded (bool): Si se envió una respuesta automática
        answer (str): Texto de la respuesta enviada (si aplica)
        email_forwarded (bool): Si el email fue reenviado
        forwarded_to (str): Email de destino del reenvío (si aplica)
        category (str): Categoría asignada al email
        tokens_used (int): Número de tokens AI consumidos en el procesamiento
    
    Relationships:
        email_account: Cuenta de email que procesó este email
    
    Properties:
        user_id: Obtiene el user_id a través de email_account
        action_type: Determina el tipo de acción principal realizada
        has_action: Verifica si se realizó alguna acción sobre el email
        processing_summary: Resumen del procesamiento realizado
    
    Methods:
        to_dict(): Convierte el registro a diccionario
        update(): Actualiza los campos del registro
        delete(): Elimina el registro de la base de datos
    
    Class Methods:
        create(): Crea un nuevo registro de email procesado
        get_by_id(): Obtiene un registro por su ID
        get_by_email_account(): Obtiene registros de una cuenta de email específica
        get_by_user(): Obtiene registros de un usuario específico
        get_stats_by_user(): Obtiene estadísticas agregadas de un usuario
        get_category_distribution(): Obtiene distribución de emails por categoría
        count_by_user(): Cuenta emails procesados de un usuario

    """
    
    __tablename__ = 'email_processed'
    
    # Campos principales
    id = Column(Integer, primary_key=True, index=True)
    email_account_id = Column(Integer, ForeignKey('email_account.id'), nullable=False, index=True)
    processed_at = Column(DateTime, default=datetime.utcnow, nullable=False, index=True)
    email_responded = Column(Boolean, default=False, nullable=False)
    answer = Column(Text)
    email_forwarded = Column(Boolean, default=False, nullable=False)
    forwarded_to = Column(String(255))
    category = Column(String(100), index=True)
    tokens_used = Column(Integer, default=0, nullable=False)
    # Q&A tracking fields
    question_id = Column(Integer, ForeignKey('questions.id'), nullable=True, index=True)
    similarity_score = Column('similarity_score', None, nullable=True)  # Float with CHECK constraint
    
    # Relaciones
    email_account = relationship("EmailAccount", back_populates="email_processed")
    question = relationship("Question", foreign_keys=[question_id])
    
    def __repr__(self):
        """
        Representación string del email procesado.
        
        Returns:
            str: Representación legible del registro
        """
        if self.email_responded:
            action_str = "responded"
        elif self.email_forwarded:
            action_str = "forwarded"
        else:
            action_str = "categorized"
        return f"<EmailProcessed(id={self.id}, account_id={self.email_account_id}, actions=[{action_str}], category='{self.category}')>"
    
    def __str__(self):
        """
        String representation para uso general.
        
        Returns:
            str: Descripción del procesamiento
        """
        date_str = self.processed_at.strftime("%Y-%m-%d %H:%M") if self.processed_at else "N/A"
        
        if self.email_responded:
            action = "Respondido"
        elif self.email_forwarded:
            action = "Reenviado"
        else:
            action = "Categorizado"
        
        return f"{action} - {self.category or 'Sin categoría'} ({date_str})"
    
    @property
    def user_id(self) -> Optional[int]:
        """
        Obtiene el user_id a través de email_account.
        
        Returns:
            int | None: ID del usuario propietario
        """
        return self.email_account.user_id if self.email_account else None
    
    @property
    def action_type(self) -> EmailActionType:
        """
        Determina el tipo de acción principal realizada.
        
        Returns:
            EmailActionType: Tipo de acción realizada
        """
        if self.email_responded:
            return EmailActionType.RESPONDED
        elif self.email_forwarded:
            return EmailActionType.FORWARDED
        elif self.category and self.category.lower() in ['spam', 'unrelated', 'ignored']:
            return EmailActionType.IGNORED
        else:
            return EmailActionType.CATEGORIZED
    
    @property
    def has_action(self) -> bool:
        """
        Verifica si se realizó alguna acción sobre el email.
        
        Returns:
            bool: True si se respondió o reenvió
        """
        return self.email_responded or self.email_forwarded
    
    @property
    def processing_summary(self) -> dict:
        """
        Resumen del procesamiento realizado.
        
        Returns:
            dict: Resumen con acciones y estadísticas
        """
        return {
            'email_account_id': self.email_account_id,
            'processed_at': self.processed_at.isoformat() if self.processed_at else None,
            'category': self.category,
            'actions': {
                'responded': self.email_responded,
                'forwarded': self.email_forwarded,
                'has_action': self.has_action
            },
            'tokens_used': self.tokens_used,
            'action_type': self.action_type.value
        }
    
    def to_dict(self) -> dict:
        """
        Convierte el registro a diccionario.
        
        Returns:
            dict: Representación como diccionario
        """
        return {
            'id': self.id,
            'email_account_id': self.email_account_id,
            'processed_at': self.processed_at.isoformat() if self.processed_at else None,
            'email_responded': self.email_responded,
            'answer': self.answer,
            'email_forwarded': self.email_forwarded,
            'forwarded_to': self.forwarded_to,
            'category': self.category,
            'tokens_used': self.tokens_used,
            'action_type': self.action_type.value,
            'has_action': self.has_action,
            # Q&A tracking
            'question_id': self.question_id,
            'similarity_score': float(self.similarity_score) if self.similarity_score else None
        }
    
    # =============================================================================
    # MÉTODOS DE CONSULTA (CLASS METHODS)
    # =============================================================================
    
    @classmethod
    def create(cls, db_session, email_account_id: int, category: str = None,
               email_responded: bool = False, answer: str = None,
               email_forwarded: bool = False, forwarded_to: str = None,
               tokens_used: int = 0, question_id: int = None, 
               similarity_score: float = None) -> 'EmailProcessed':
        """
        Crea un nuevo registro de email procesado.
        
        Args:
            db_session: Sesión de base de datos
            email_account_id (int): ID de la cuenta de email
            category (str): Categoría asignada al email
            email_responded (bool): Si se envió respuesta
            answer (str): Texto de la respuesta
            email_forwarded (bool): Si se reenvió
            forwarded_to (str): Email de destino del reenvío
            tokens_used (int): Tokens AI consumidos
            question_id (int, optional): ID de la pregunta Q&A utilizada
            similarity_score (float, optional): Score de similitud (0.0-1.0)
            
        Returns:
            EmailProcessed: Registro creado
        """
        email_processed = cls(
            email_account_id=email_account_id,
            category=category,
            email_responded=email_responded,
            answer=answer,
            email_forwarded=email_forwarded,
            forwarded_to=forwarded_to,
            tokens_used=tokens_used,
            question_id=question_id,
            similarity_score=similarity_score
        )
        
        db_session.add(email_processed)
        db_session.flush()
        return email_processed
    
    @classmethod
    def get_by_id(cls, db_session, record_id: int) -> Optional['EmailProcessed']:
        """
        Obtiene un registro por su ID.
        
        Args:
            db_session: Sesión de base de datos
            record_id (int): ID del registro
            
        Returns:
            EmailProcessed | None: Registro encontrado o None
        """
        return db_session.query(cls).filter(cls.id == record_id).first()
    
    @classmethod
    def get_by_email_account(cls, db_session, email_account_id: int, 
                           limit: int = None) -> List['EmailProcessed']:
        """
        Obtiene registros de una cuenta de email específica.
        
        Args:
            db_session: Sesión de base de datos
            email_account_id (int): ID de la cuenta de email
            limit (int, optional): Límite de registros
            
        Returns:
            List[EmailProcessed]: Lista de registros
        """
        query = db_session.query(cls).filter(cls.email_account_id == email_account_id)
        query = query.order_by(cls.processed_at.desc())
        
        if limit:
            query = query.limit(limit)
        
        return query.all()
    
    @classmethod
    def get_by_user(cls, db_session, user_id: int, 
                   date_range: Tuple[datetime, datetime] = None,
                   limit: int = None) -> List['EmailProcessed']:
        """
        Obtiene registros de un usuario específico.
        
        Args:
            db_session: Sesión de base de datos
            user_id (int): ID del usuario
            date_range (tuple, optional): Rango de fechas (inicio, fin)
            limit (int, optional): Límite de registros
            
        Returns:
            List[EmailProcessed]: Lista de registros del usuario
        """
        from .email_account import EmailAccount
        
        query = db_session.query(cls).join(EmailAccount).filter(
            EmailAccount.user_id == user_id
        )
        
        if date_range:
            start_date, end_date = date_range
            query = query.filter(cls.processed_at.between(start_date, end_date))
        
        query = query.order_by(cls.processed_at.desc())
        
        if limit:
            query = query.limit(limit)
        
        return query.all()
    
    @classmethod
    def get_stats_by_user(cls, db_session, user_id: int,
                         date_range: Tuple[datetime, datetime] = None) -> Dict[str, Union[int, float]]:
        """
        Obtiene estadísticas agregadas de un usuario.
        
        Args:
            db_session: Sesión de base de datos
            user_id (int): ID del usuario
            date_range (tuple, optional): Rango de fechas
            
        Returns:
            dict: Estadísticas agregadas
        """
        from .email_account import EmailAccount
        from sqlalchemy import func, Integer
        
        query = db_session.query(
            func.count(cls.id).label('total_processed'),
            func.sum(cls.email_responded.cast(Integer)).label('total_responded'),
            func.sum(cls.email_forwarded.cast(Integer)).label('total_forwarded'),
            func.sum(cls.tokens_used).label('total_tokens')
        ).join(EmailAccount).filter(EmailAccount.user_id == user_id)
        
        if date_range:
            start_date, end_date = date_range
            query = query.filter(cls.processed_at.between(start_date, end_date))
        
        result = query.first()
        
        total_processed = result.total_processed or 0
        total_responded = result.total_responded or 0
        total_forwarded = result.total_forwarded or 0
        total_tokens = result.total_tokens or 0
        
        # Calcular métricas derivadas
        total_actions = total_responded + total_forwarded
        automation_rate = (total_actions / max(total_processed, 1)) * 100
        time_saved_minutes = total_processed * 5  # 5 min por email
        
        return {
            'total_processed': total_processed,
            'total_responded': total_responded,
            'total_forwarded': total_forwarded,
            'total_actions': total_actions,
            'total_tokens': total_tokens,
            'automation_rate': round(automation_rate, 2),
            'time_saved_minutes': time_saved_minutes,
            'time_saved_hours': round(time_saved_minutes / 60, 2)
        }
    
    @classmethod
    def get_category_distribution(cls, db_session, user_id: int,
                                date_range: Tuple[datetime, datetime] = None) -> List[Dict[str, Union[str, int]]]:
        """
        Obtiene distribución de emails por categoría.
        
        Args:
            db_session: Sesión de base de datos
            user_id (int): ID del usuario
            date_range (tuple, optional): Rango de fechas
            
        Returns:
            List[dict]: Lista con categorías y conteos
        """
        from .email_account import EmailAccount
        from sqlalchemy import func
        
        query = db_session.query(
            cls.category,
            func.count(cls.id).label('count')
        ).join(EmailAccount).filter(
            EmailAccount.user_id == user_id
        ).group_by(cls.category)
        
        if date_range:
            start_date, end_date = date_range
            query = query.filter(cls.processed_at.between(start_date, end_date))
        
        results = query.order_by(func.count(cls.id).desc()).all()
        
        return [
            {
                'category': result.category or 'Sin categoría',
                'count': result.count,
                'percentage': 0  # Se calculará en el servicio si es necesario
            }
            for result in results
        ]
    
    @classmethod
    def count_by_user(cls, db_session, user_id: int,
                     date_range: Tuple[datetime, datetime] = None) -> int:
        """
        Cuenta el número total de emails procesados por un usuario.
        
        Args:
            db_session: Sesión de base de datos
            user_id (int): ID del usuario
            date_range (Tuple[datetime, datetime], optional): Rango de fechas (inicio, fin)
            
        Returns:
            int: Total de emails procesados
        """
        from sqlalchemy import func
        from .email_account import EmailAccount
        
        query = db_session.query(func.count(cls.id)).join(
            EmailAccount, cls.email_account_id == EmailAccount.id
        ).filter(EmailAccount.user_id == user_id)
        
        if date_range:
            start_date, end_date = date_range
            query = query.filter(cls.processed_at.between(start_date, end_date))
        
        return query.scalar() or 0
    
    # =============================================================================
    # MÉTODOS DE AGREGACIÓN SQL OPTIMIZADOS
    # =============================================================================

    @classmethod
    def get_daily_statistics(cls, db_session, email_account_id: int, date_range: int = 30) -> List[Dict[str, Union[str, int]]]:
        """
        Obtiene estadísticas diarias agregadas usando SQL optimizado.
        
        Args:
            db_session: Sesión de base de datos
            email_account_id (int): ID de la cuenta de email
            date_range (int): Número de días hacia atrás
            
        Returns:
            List[Dict]: Estadísticas diarias agregadas
        """
        from sqlalchemy import func, Date, case, desc
        from datetime import datetime, timedelta
        
        # Calcular fecha de inicio
        start_date = datetime.now() - timedelta(days=date_range)
        
        # Query SQL agregada optimizada
        query = db_session.query(
            func.date(cls.processed_at).label('date'),
            func.count().label('total_emails'),
            func.sum(case((cls.email_responded == True, 1), else_=0)).label('responded_count'),
            func.sum(case((cls.email_forwarded == True, 1), else_=0)).label('forwarded_count'),
            func.sum(case((cls.email_responded == False, cls.email_forwarded == False, 1), else_=0)).label('ignored_count'),
            func.sum(case((cls.category == 'spam', 1), else_=0)).label('spam_count'),
            func.sum(cls.tokens_used).label('total_tokens'),
            func.string_agg(cls.category, ',').label('categories_raw')
        ).filter(
            cls.email_account_id == email_account_id,
            cls.processed_at >= start_date
        ).group_by(
            func.date(cls.processed_at)
        ).order_by(
            desc(func.date(cls.processed_at))
        )
        
        # Procesar resultados
        results = []
        for row in query.all():
            # Procesar categorías únicas
            categories = []
            if row.categories_raw:
                unique_categories = list(set(row.categories_raw.split(',')))
                categories = [cat.strip() for cat in unique_categories if cat.strip()]
            
            results.append({
                'date': row.date.isoformat() if row.date else None,
                'total_emails': row.total_emails or 0,
                'responded_count': row.responded_count or 0,
                'forwarded_count': row.forwarded_count or 0,
                'ignored_count': row.ignored_count or 0,
                'spam_count': row.spam_count or 0,
                'total_tokens': row.total_tokens or 0,
                'categories': categories
            })
        
        return results

    @classmethod
    def get_category_distribution(cls, db_session, email_account_id: int, date_range: int = 30) -> List[Dict[str, Union[str, int, float]]]:
        """
        Obtiene distribución por categorías usando SQL agregado optimizado.
        
        Args:
            db_session: Sesión de base de datos
            email_account_id (int): ID de la cuenta de email
            date_range (int): Número de días hacia atrás
            
        Returns:
            List[Dict]: Distribución por categorías con estadísticas
        """
        from sqlalchemy import func, desc
        from datetime import datetime, timedelta
        
        # Calcular fecha de inicio
        start_date = datetime.now() - timedelta(days=date_range)
        
        # Query SQL agregada optimizada
        query = db_session.query(
            cls.category.label('category'),
            func.count().label('count'),
            func.avg(cls.tokens_used).label('avg_tokens'),
            func.sum(cls.tokens_used).label('total_tokens')
        ).filter(
            cls.email_account_id == email_account_id,
            cls.processed_at >= start_date,
            cls.category.isnot(None)  # Excluir categorías nulas
        ).group_by(
            cls.category
        ).order_by(
            desc(func.count())
        )
        
        # Procesar resultados
        results = []
        for row in query.all():
            results.append({
                'category': row.category or 'unknown',
                'count': row.count or 0,
                'avg_tokens': float(row.avg_tokens) if row.avg_tokens else 0.0,
                'total_tokens': row.total_tokens or 0
            })
        
        return results

    @classmethod
    def get_automated_email_count(cls, db_session, email_account_id: int, date_range: int = 30) -> Dict[str, int]:
        """
        Obtiene conteo de emails automatizados (respondidos + reenviados) usando SQL optimizado.
        
        Args:
            db_session: Sesión de base de datos
            email_account_id (int): ID de la cuenta de email
            date_range (int): Número de días hacia atrás
            
        Returns:
            Dict[str, int]: Conteos de emails automatizados
        """
        from sqlalchemy import func, case
        from datetime import datetime, timedelta
        
        # Calcular fecha de inicio
        start_date = datetime.now() - timedelta(days=date_range)
        
        # Query SQL agregada optimizada
        result = db_session.query(
            func.sum(case((cls.email_responded == True, 1), else_=0)).label('responded_count'),
            func.sum(case((cls.email_forwarded == True, 1), else_=0)).label('forwarded_count'),
            func.count().label('total_processed')
        ).filter(
            cls.email_account_id == email_account_id,
            cls.processed_at >= start_date
        ).first()
        
        return {
            'responded_count': result.responded_count or 0,
            'forwarded_count': result.forwarded_count or 0,
            'total_processed': result.total_processed or 0
        }

    @classmethod
    def count_old_records(cls, db_session, cutoff_date: datetime) -> int:
        """
        Cuenta registros antiguos para limpieza usando SQL optimizado.
        
        Args:
            db_session: Sesión de base de datos
            cutoff_date (datetime): Fecha límite
            
        Returns:
            int: Número de registros antiguos
        """
        from sqlalchemy import func
        
        return db_session.query(func.count(cls.id)).filter(
            cls.processed_at < cutoff_date
        ).scalar() or 0

    @classmethod
    def cleanup_old_records(cls, db_session, cutoff_date: datetime) -> int:
        """
        Elimina registros antiguos usando SQL optimizado.
        
        Args:
            db_session: Sesión de base de datos
            cutoff_date (datetime): Fecha límite
            
        Returns:
            int: Número de registros eliminados
        """
        deleted_count = db_session.query(cls).filter(
            cls.processed_at < cutoff_date
        ).delete(synchronize_session=False)
        
        return deleted_count

    # =============================================================================
    # MÉTODOS DE INSTANCIA
    # =============================================================================

    def update(self, db_session, **kwargs) -> None:
        """
        Actualiza los campos del registro.
        
        Args:
            db_session: Sesión de base de datos
            **kwargs: Campos a actualizar
        """
        allowed_fields = {
            'category', 'email_responded', 'answer', 
            'email_forwarded', 'forwarded_to', 'tokens_used'
        }
        
        for field, value in kwargs.items():
            if field in allowed_fields and hasattr(self, field):
                setattr(self, field, value)
        
        db_session.flush()
    
    def delete(self, db_session) -> None:
        """
        Elimina el registro de la base de datos.
        
        Args:
            db_session: Sesión de base de datos
        """
        db_session.delete(self)
        db_session.flush()


class UserUsageMonthly(Base):
    """
    Modelo para estadísticas mensuales de uso por usuario.
    
    Almacena datos agregados mensuales de uso para cada usuario,
    incluyendo emails procesados, acciones realizadas y tokens consumidos.
    
    Attributes:
        id (int): Identificador único del registro (clave primaria)
        user_id (int): ID del usuario (clave foránea)
        year (int): Año del registro
        month (int): Mes del registro (1-12)
        emails_processed (int): Total de emails procesados en el mes
        emails_responded (int): Total de emails respondidos en el mes
        emails_forwarded (int): Total de emails reenviados en el mes
        tokens_used (int): Total de tokens AI consumidos en el mes
        last_updated (datetime): Última actualización del registro
    
    Relationships:
        user: Usuario al que pertenecen estas estadísticas
    
    Properties:
        period_key: Clave única del período (año-mes)
        total_actions: Total de acciones realizadas (respuestas + reenvíos)
        automation_rate: Tasa de automatización (acciones / emails procesados)
        time_saved_minutes: Tiempo ahorrado en minutos (5 min por email procesado)
        is_current_month: Verifica si este registro corresponde al mes actual
    
    Methods:
        to_dict(): Convierte el registro a diccionario
        update(): Actualiza los campos del registro
        increment_usage(): Incrementa los contadores de uso
        delete(): Elimina el registro de la base de datos
        get_comparison_with_previous_month(): Compara las estadísticas con el mes anterior
    
    Class Methods:
        create_or_update(): Crea o actualiza un registro de uso mensual (UPSERT)
        get_by_id(): Obtiene un registro por su ID
        get_by_user_and_period(): Obtiene un registro específico por usuario y período
        get_current_month(): Obtiene el registro del mes actual para un usuario
        get_by_user(): Obtiene registros de un usuario para los últimos N meses
        get_user_totals(): Obtiene totales agregados de un usuario
        cleanup_old_records(): Limpia registros antiguos más allá del período especificado
        get_or_create_current(): Obtiene o crea el registro del mes actual (método faltante)

    """
    
    __tablename__ = 'user_usage_monthly'
    
    # Campos principales
    id = Column(Integer, primary_key=True, index=True)
    user_id = Column(Integer, ForeignKey('users.id'), nullable=False, index=True)
    year = Column(Integer, nullable=False)
    month = Column(Integer, nullable=False)
    emails_processed = Column(Integer, default=0, nullable=False)
    emails_responded = Column(Integer, default=0, nullable=False)
    emails_forwarded = Column(Integer, default=0, nullable=False)
    tokens_used = Column(Integer, default=0, nullable=False)
    last_updated = Column(DateTime, default=datetime.utcnow, nullable=False)
    
    # Constraints
    __table_args__ = (
        CheckConstraint('month >= 1 AND month <= 12', name='check_month_range'),
        UniqueConstraint('user_id', 'year', 'month', name='unique_user_year_month'),
    )
    
    # Relaciones
    user = relationship("User", back_populates="user_usage_monthly")

    def __repr__(self):
        """
        Representación string del registro de uso mensual.
        
        Returns:
            str: Representación legible del registro
        """
        return f"<UserUsageMonthly(user_id={self.user_id}, {self.year}-{self.month:02d}, processed={self.emails_processed})>"
    
    def __str__(self):
        """
        String representation para uso general.
        
        Returns:
            str: Descripción del mes y estadísticas principales
        """
        month_names = [
            '', 'Enero', 'Febrero', 'Marzo', 'Abril', 'Mayo', 'Junio',
            'Julio', 'Agosto', 'Septiembre', 'Octubre', 'Noviembre', 'Diciembre'
        ]
        
        month_name = month_names[self.month] if 1 <= self.month <= 12 else f"Mes {self.month}"
        actions = self.emails_responded + self.emails_forwarded
        
        return f"{month_name} {self.year}: {self.emails_processed} procesados, {actions} acciones"
    
    @property
    def period_key(self) -> str:
        """
        Clave única del período (año-mes).
        
        Returns:
            str: Clave en formato YYYY-MM
        """
        return f"{self.year}-{self.month:02d}"
    
    @property
    def total_actions(self) -> int:
        """
        Total de acciones realizadas (respuestas + reenvíos).
        
        Returns:
            int: Total de acciones
        """
        return self.emails_responded + self.emails_forwarded
    
    @property
    def automation_rate(self) -> float:
        """
        Tasa de automatización (acciones / emails procesados).
        
        Returns:
            float: Porcentaje de automatización (0-100)
        """
        if self.emails_processed == 0:
            return 0.0
        return (self.total_actions / self.emails_processed) * 100
    
    @property
    def time_saved_minutes(self) -> int:
        """
        Tiempo ahorrado en minutos (5 min por email procesado).
        
        Returns:
            int: Minutos ahorrados
        """
        return self.emails_processed * 5
    
    @property
    def is_current_month(self) -> bool:
        """
        Verifica si este registro corresponde al mes actual.
        
        Returns:
            bool: True si es el mes actual
        """
        now = datetime.now()
        return self.year == now.year and self.month == now.month
    
    def to_dict(self) -> dict:
        """
        Convierte el registro a diccionario.
        
        Returns:
            dict: Representación como diccionario
        """
        return {
            'id': self.id,
            'user_id': self.user_id,
            'year': self.year,
            'month': self.month,
            'period_key': self.period_key,
            'emails_processed': self.emails_processed,
            'emails_responded': self.emails_responded,
            'emails_forwarded': self.emails_forwarded,
            'total_actions': self.total_actions,
            'tokens_used': self.tokens_used,
            'automation_rate': round(self.automation_rate, 2),
            'time_saved_minutes': self.time_saved_minutes,
            'time_saved_hours': round(self.time_saved_minutes / 60, 2),
            'is_current_month': self.is_current_month,
            'last_updated': self.last_updated.isoformat() if self.last_updated else None
        }

    # =============================================================================
    # MÉTODOS DE AGREGACIÓN SQL OPTIMIZADOS PARA UserUsageMonthly
    # =============================================================================

    @classmethod
    def get_or_create_current(cls, db_session, user_id: int, year: int, month: int) -> 'UserUsageMonthly':
        """
        Obtiene o crea el registro de uso mensual actual usando UPSERT optimizado.
        
        Args:
            db_session: Sesión de base de datos
            user_id (int): ID del usuario
            year (int): Año
            month (int): Mes
            
        Returns:
            UserUsageMonthly: Registro existente o recién creado
        """
        # Intentar obtener el registro existente
        existing = db_session.query(cls).filter(
            cls.user_id == user_id,
            cls.year == year,
            cls.month == month
        ).first()
        
        if existing:
            return existing
        
        # Crear nuevo registro si no existe
        new_record = cls(
            user_id=user_id,
            year=year,
            month=month,
            emails_processed=0,
            emails_responded=0,
            emails_forwarded=0,
            tokens_used=0
        )
        
        db_session.add(new_record)
        db_session.flush()
        return new_record

    def increment_tokens(self, tokens: int) -> None:
        """
        Incrementa el contador de tokens de forma optimizada.
        
        Args:
            tokens (int): Número de tokens a incrementar
        """
        self.tokens_used += tokens
        self.last_updated = datetime.utcnow()

    def increment_usage(self, db_session, emails_processed: int = 0,
                       emails_responded: int = 0, emails_forwarded: int = 0,
                       tokens_used: int = 0) -> None:
        """
        Incrementa los contadores de uso.
        
        Args:
            db_session: Sesión de base de datos
            emails_processed (int): Emails procesados a sumar
            emails_responded (int): Emails respondidos a sumar
            emails_forwarded (int): Emails reenviados a sumar
            tokens_used (int): Tokens a sumar
        """
        self.emails_processed += emails_processed
        self.emails_responded += emails_responded
        self.emails_forwarded += emails_forwarded
        self.tokens_used += tokens_used
        self.last_updated = datetime.utcnow()
        db_session.flush()

    def delete(self, db_session) -> None:
        """
        Elimina el registro de la base de datos.
        
        Args:
            db_session: Sesión de base de datos
        """
        db_session.delete(self)
        db_session.flush()

    def get_comparison_with_previous_month(self, db_session) -> Dict[str, Union[int, float, str]]:
        """
        Compara las estadísticas con el mes anterior.
        
        Args:
            db_session: Sesión de base de datos
            
        Returns:
            dict: Comparación con el mes anterior
        """
        from datetime import datetime, timedelta
        
        # Calcular mes anterior
        if self.month == 1:
            prev_year = self.year - 1
            prev_month = 12
        else:
            prev_year = self.year
            prev_month = self.month - 1
        
        # Obtener registro del mes anterior
        previous = self.get_by_user_and_period(db_session, self.user_id, prev_year, prev_month)
        
        def calc_percentage_change(current: int, previous: int) -> float:
            """Calcula el cambio porcentual."""
            if previous == 0:
                return 100.0 if current > 0 else 0.0
            return ((current - previous) / previous) * 100
        
        if not previous:
            return {
                'has_previous_month': False,
                'previous_month': f"{prev_year}-{prev_month:02d}",
                'message': 'No hay datos del mes anterior para comparar'
            }
        
        return {
            'has_previous_month': True,
            'previous_month': f"{prev_year}-{prev_month:02d}",
            'current_month': self.period_key,
            'emails_processed': {
                'current': self.emails_processed,
                'previous': previous.emails_processed,
                'change': self.emails_processed - previous.emails_processed,
                'percentage_change': calc_percentage_change(self.emails_processed, previous.emails_processed)
            },
            'emails_responded': {
                'current': self.emails_responded,
                'previous': previous.emails_responded,
                'change': self.emails_responded - previous.emails_responded,
                'percentage_change': calc_percentage_change(self.emails_responded, previous.emails_responded)
            },
            'emails_forwarded': {
                'current': self.emails_forwarded,
                'previous': previous.emails_forwarded,
                'change': self.emails_forwarded - previous.emails_forwarded,
                'percentage_change': calc_percentage_change(self.emails_forwarded, previous.emails_forwarded)
            },
            'tokens_used': {
                'current': self.tokens_used,
                'previous': previous.tokens_used,
                'change': self.tokens_used - previous.tokens_used,
                'percentage_change': calc_percentage_change(self.tokens_used, previous.tokens_used)
            },
            'automation_rate': {
                'current': self.automation_rate,
                'previous': previous.automation_rate,
                'change': self.automation_rate - previous.automation_rate
            }
        }

    # =============================================================================
    # MÉTODOS DE CONSULTA ADICIONALES
    # =============================================================================

    @classmethod
    def get_by_id(cls, db_session, record_id: int) -> Optional['UserUsageMonthly']:
        """
        Obtiene un registro por su ID.
        
        Args:
            db_session: Sesión de base de datos
            record_id (int): ID del registro
            
        Returns:
            UserUsageMonthly | None: Registro encontrado o None
        """
        return db_session.query(cls).filter(cls.id == record_id).first()
    
    @classmethod
    def get_by_user_and_period(cls, db_session, user_id: int, year: int, month: int) -> Optional['UserUsageMonthly']:
        """
        Obtiene un registro específico por usuario y período.
        
        Args:
            db_session: Sesión de base de datos
            user_id (int): ID del usuario
            year (int): Año
            month (int): Mes
            
        Returns:
            UserUsageMonthly | None: Registro encontrado o None
        """
        return db_session.query(cls).filter(
            cls.user_id == user_id,
            cls.year == year,
            cls.month == month
        ).first()
    
    @classmethod
    def get_current_month(cls, db_session, user_id: int) -> Optional['UserUsageMonthly']:
        """
        Obtiene el registro del mes actual para un usuario.
        
        Args:
            db_session: Sesión de base de datos
            user_id (int): ID del usuario
            
        Returns:
            UserUsageMonthly | None: Registro del mes actual o None
        """
        now = datetime.now()
        return cls.get_by_user_and_period(db_session, user_id, now.year, now.month)

    # =============================================================================
    # MÉTODOS DE INSTANCIA
    # =============================================================================

    def update(self, db_session, **kwargs) -> None:
        """
        Actualiza los campos del registro.
        
        Args:
            db_session: Sesión de base de datos
            **kwargs: Campos a actualizar
        """
        allowed_fields = {
            'emails_processed', 'emails_responded', 
            'emails_forwarded', 'tokens_used'
        }
        
        for field, value in kwargs.items():
            if field in allowed_fields and hasattr(self, field):
                setattr(self, field, value)
        
        self.last_updated = datetime.utcnow()
        db_session.flush()

    def increment_usage(self, db_session, emails_processed: int = 0,
                       emails_responded: int = 0, emails_forwarded: int = 0,
                       tokens_used: int = 0) -> None:
        """
        Incrementa los contadores de uso.
        
        Args:
            db_session: Sesión de base de datos
            emails_processed (int): Emails procesados a sumar
            emails_responded (int): Emails respondidos a sumar
            emails_forwarded (int): Emails reenviados a sumar
            tokens_used (int): Tokens a sumar
        """
        self.emails_processed += emails_processed
        self.emails_responded += emails_responded
        self.emails_forwarded += emails_forwarded
        self.tokens_used += tokens_used
        self.last_updated = datetime.utcnow()
        db_session.flush()
