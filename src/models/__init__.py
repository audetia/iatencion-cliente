"""
Módulo de modelos para el sistema de automatización de emails.

Este módulo centraliza la importación de todos los modelos de SQLAlchemy
y proporciona funciones de conveniencia para la gestión de la base de datos.
"""

# Importar base y funciones de utilidad
from .base import Base, TimestampMixin, create_tables, drop_tables

# Importar todos los modelos
from .user import User
from .email_account import EmailAccount
from .qa import Question, QuestionVariant, Answer

# Exportar todos los modelos y utilidades
__all__ = [
    # Base y utilidades
    'Base',
    'TimestampMixin', 
    'create_tables',
    'drop_tables',
    
    # Modelos
    'User',
    'EmailAccount',
    'Question',
    'QuestionVariant',
    'Answer'
]

# Función de conveniencia para verificar que todos los modelos están importados
def get_all_models():
    """
    Retorna lista de todas las clases de modelo disponibles.
    
    Returns:
        list: Lista de clases de modelo
    """
    return [User, EmailAccount, Question, QuestionVariant, Answer]

# Función para verificar integridad de relaciones
def verify_model_relationships():
    """
    Verifica que todas las relaciones entre modelos estén correctamente definidas.
    
    Returns:
        dict: Resultado de la verificación
    """
    issues = []
    
    # Verificar relaciones User
    if not hasattr(User, 'email_accounts'):
        issues.append("User.email_accounts relationship missing")
    if not hasattr(User, 'questions'):
        issues.append("User.questions relationship missing")
    
    # Verificar relaciones EmailAccount
    if not hasattr(EmailAccount, 'user'):
        issues.append("EmailAccount.user relationship missing")
    
    # Verificar relaciones Question
    if not hasattr(Question, 'user'):
        issues.append("Question.user relationship missing")
    if not hasattr(Question, 'variants'):
        issues.append("Question.variants relationship missing")
    if not hasattr(Question, 'answer'):
        issues.append("Question.answer relationship missing")
    
    # Verificar relaciones QuestionVariant
    if not hasattr(QuestionVariant, 'question'):
        issues.append("QuestionVariant.question relationship missing")
    
    # Verificar relaciones Answer
    if not hasattr(Answer, 'question'):
        issues.append("Answer.question relationship missing")
    
    return {
        'is_valid': len(issues) == 0,
        'issues': issues,
        'total_models': len(get_all_models()),
        'relationships_checked': 8
    } 