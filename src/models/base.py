from datetime import datetime
from sqlalchemy import Column, DateTime, event
from sqlalchemy.ext.declarative import declarative_base

# Importar el gestor de base de datos
from ..database import db_manager

# Base declarativa
Base = declarative_base()

class TimestampMixin:
    """
    Mixin para agregar timestamps automáticos a los modelos.
    
    Proporciona:
    - created_at: Fecha de creación automática
    - updated_at: Fecha de actualización automática
    """
    
    created_at = Column(DateTime, default=datetime.utcnow, nullable=False)
    updated_at = Column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow, nullable=False)
    
    def __repr__(self):
        return f"<{self.__class__.__name__} created_at={self.created_at}>"

# Evento para actualizar automáticamente updated_at
@event.listens_for(Base, 'before_update', propagate=True)
def timestamp_before_update(mapper, connection, target):
    """Actualiza automáticamente updated_at antes de cada update"""
    if hasattr(target, 'updated_at'):
        target.updated_at = datetime.utcnow()

# Funciones de conveniencia
def create_tables():
    """Crea todas las tablas definidas en los modelos"""
    return db_manager.create_tables(Base.metadata)

def drop_tables():
    """Elimina todas las tablas (¡CUIDADO en producción!)"""
    return db_manager.drop_tables(Base.metadata)