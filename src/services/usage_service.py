"""
Servicio de gestión de uso y límites de usuarios.

Este módulo proporciona funcionalidad para rastrear el uso de emails procesados
por usuario y validar límites antes del procesamiento.

Principios aplicados:
- KISS: Implementación simple y directa
- SOLID: Separación de responsabilidades
- DRY: Reutilización de código existente
- YAGNI: Solo funcionalidad necesaria para el MVP
"""

import logging
import time
from datetime import datetime, timedelta
from typing import Dict, Any, Optional, Tuple
from functools import wraps
from dataclasses import dataclass

# Configurar logging
logger = logging.getLogger(__name__)

# Límites por defecto (hardcodeados para MVP)
DEFAULT_LIMITS = {
    'emails_per_month': 1000,
    'tokens_per_month': 50000,
    'automations_per_user': 10
}


@dataclass
class UsageValidation:
    """Resultado de validación de límites de uso."""
    can_process: bool
    reason: str
    current_usage: Dict[str, int]
    limits: Dict[str, int]
    usage_percentage: Dict[str, float]


def retry_on_db_error(max_attempts: int = 3, delay: float = 1.0):
    """
    Decorator para reintentar operaciones de base de datos en caso de error.
    
    Args:
        max_attempts (int): Número máximo de intentos
        delay (float): Delay entre intentos en segundos
    """
    def decorator(func):
        @wraps(func)
        def wrapper(*args, **kwargs):
            last_exception = None
            
            for attempt in range(max_attempts):
                try:
                    return func(*args, **kwargs)
                except Exception as e:
                    last_exception = e
                    
                    # Solo reintentar en errores de conexión/transacción
                    error_msg = str(e).lower()
                    if any(keyword in error_msg for keyword in [
                        'connection', 'timeout', 'deadlock', 'lock', 'transaction'
                    ]):
                        if attempt < max_attempts - 1:
                            logger.warning(
                                f"Error en {func.__name__} (intento {attempt + 1}/{max_attempts}): {e}. "
                                f"Reintentando en {delay}s..."
                            )
                            time.sleep(delay)
                            continue
                    
                    # No reintentar en errores de validación o lógica
                    logger.error(f"Error no recuperable en {func.__name__}: {e}")
                    raise
            
            # Si llegamos aquí, se agotaron los intentos
            logger.error(f"Se agotaron los intentos para {func.__name__}. Último error: {last_exception}")
            raise last_exception
        
        return wrapper
    return decorator


class UsageService:
    """
    Servicio para gestión de uso y límites de usuarios.
    
    Este servicio proporciona funcionalidad para:
    - Rastrear emails procesados por usuario
    - Validar límites antes del procesamiento
    - Obtener estadísticas de uso actual
    """
    
    def __init__(self, db_manager):
        """
        Inicializa el servicio de uso.
        
        Args:
            db_manager: Instancia del DatabaseManager
        """
        self.db_manager = db_manager
        self.limits = DEFAULT_LIMITS.copy()
        logger.info("✅ UsageService inicializado")
    
    @retry_on_db_error(max_attempts=3, delay=1.0)
    def track_email_processed(self, user_id: int, email_data: Dict[str, Any]) -> Dict[str, Any]:
        """
        Rastrea un email procesado con transacciones atómicas.
        
        Args:
            user_id (int): ID del usuario
            email_data (dict): Datos del email procesado
            
        Returns:
            dict: Resultado del tracking con información de éxito/error
            
        Raises:
            ValueError: Si los parámetros son inválidos
            RuntimeError: Si hay error en la base de datos
        """
        # Validar entrada
        if not isinstance(user_id, int) or user_id <= 0:
            raise ValueError("El ID del usuario debe ser un entero positivo")
        
        if not isinstance(email_data, dict):
            raise ValueError("email_data debe ser un diccionario")
        
        # Validar estructura mínima de email_data
        required_fields = ['email_account_id', 'category', 'action_taken']
        missing_fields = [field for field in required_fields if field not in email_data]
        if missing_fields:
            raise ValueError(f"Faltan campos requeridos en email_data: {missing_fields}")
        
        # Extraer datos del email
        email_account_id = email_data['email_account_id']
        category = email_data['category']
        action_taken = email_data['action_taken']
        tokens_used = email_data.get('tokens_used', 0)
        
        logger.info(f"🔄 Iniciando tracking de email para usuario {user_id}")
        logger.info(f"   Cuenta: {email_account_id}, Categoría: {category}, Acción: {action_taken}")
        logger.info(f"   Tokens utilizados: {tokens_used}")
        
        try:
            # Usar el método existente del DatabaseManager que ya maneja transacciones
            result = self.db_manager.log_email_processed(
                email_account_id=email_account_id,
                category=category,
                action_taken=action_taken,
                tokens_used=tokens_used,
                email_data=email_data
            )
            
            # Verificar que el tracking fue exitoso
            if not result.get('success', False):
                raise RuntimeError(f"Error en tracking: {result.get('message', 'Error desconocido')}")
            
            logger.info(f"✅ Email trackeado exitosamente para usuario {user_id}")
            logger.info(f"   ID de procesamiento: {result['email_processed']['id']}")
            
            return {
                'success': True,
                'user_id': user_id,
                'email_processed_id': result['email_processed']['id'],
                'tracking_timestamp': datetime.now().isoformat(),
                'message': 'Email trackeado exitosamente'
            }
            
        except Exception as e:
            logger.error(f"❌ Error trackeando email para usuario {user_id}: {e}")
            raise RuntimeError(f"Error en tracking de uso: {str(e)}")
    
    def validate_usage_limits(self, user_id: int) -> UsageValidation:
        """
        Valida si el usuario puede procesar más emails según sus límites.
        
        Args:
            user_id (int): ID del usuario a validar
            
        Returns:
            UsageValidation: Resultado de la validación con detalles
            
        Raises:
            ValueError: Si el user_id es inválido
            RuntimeError: Si hay error consultando la base de datos
        """
        if not isinstance(user_id, int) or user_id <= 0:
            raise ValueError("El ID del usuario debe ser un entero positivo")
        
        logger.info(f"🔍 Validando límites de uso para usuario {user_id}")
        
        try:
            # Obtener uso actual del mes
            current_usage = self.get_current_usage(user_id)
            
            # Calcular porcentajes de uso
            usage_percentage = {}
            for key, limit in self.limits.items():
                current_value = current_usage.get(key, 0)
                usage_percentage[key] = (current_value / limit) * 100 if limit > 0 else 0
            
            # Determinar si puede procesar más emails
            emails_used = current_usage.get('emails_per_month', 0)
            emails_limit = self.limits['emails_per_month']
            
            can_process = emails_used < emails_limit
            
            if can_process:
                reason = f"Uso actual: {emails_used}/{emails_limit} emails ({usage_percentage['emails_per_month']:.1f}%)"
            else:
                reason = f"Límite mensual alcanzado: {emails_used}/{emails_limit} emails"
            
            # Log de resultado
            if can_process:
                logger.info(f"✅ Usuario {user_id} puede procesar emails: {reason}")
            else:
                logger.warning(f"⚠️  Usuario {user_id} ha alcanzado límites: {reason}")
            
            # Alertas cuando se acerca a límites
            email_percentage = usage_percentage['emails_per_month']
            if email_percentage >= 95:
                logger.warning(f"🚨 Usuario {user_id} al 95% del límite de emails")
            elif email_percentage >= 80:
                logger.info(f"📊 Usuario {user_id} al {email_percentage:.1f}% del límite de emails")
            
            return UsageValidation(
                can_process=can_process,
                reason=reason,
                current_usage=current_usage,
                limits=self.limits.copy(),
                usage_percentage=usage_percentage
            )
            
        except Exception as e:
            logger.error(f"❌ Error validando límites para usuario {user_id}: {e}")
            raise RuntimeError(f"Error validando límites: {str(e)}")
    
    def get_current_usage(self, user_id: int) -> Dict[str, int]:
        """
        Obtiene el uso actual del usuario para el mes corriente.
        
        Args:
            user_id (int): ID del usuario
            
        Returns:
            dict: Uso actual con claves como 'emails_per_month', 'tokens_per_month'
            
        Raises:
            ValueError: Si el user_id es inválido
            RuntimeError: Si hay error consultando la base de datos
        """
        if not isinstance(user_id, int) or user_id <= 0:
            raise ValueError("El ID del usuario debe ser un entero positivo")
        
        try:
            with self.db_manager.get_db_session() as db:
                from ..models.statistics import UserUsageMonthly
                
                # Obtener fecha actual
                now = datetime.now()
                
                # Buscar registro del mes actual
                monthly_usage = UserUsageMonthly.get_or_create_current(
                    db, user_id, now.year, now.month
                )
                
                # Mapear a formato esperado
                current_usage = {
                    'emails_per_month': monthly_usage.emails_processed,
                    'tokens_per_month': monthly_usage.tokens_used,
                    'emails_responded': monthly_usage.emails_responded,
                    'emails_forwarded': monthly_usage.emails_forwarded
                }
                
                logger.debug(f"📊 Uso actual para usuario {user_id}: {current_usage}")
                
                return current_usage
                
        except Exception as e:
            logger.error(f"❌ Error obteniendo uso actual para usuario {user_id}: {e}")
            raise RuntimeError(f"Error consultando uso actual: {str(e)}")
    
    def update_monthly_usage(self, user_id: int, email_account_id: int, 
                           action_taken: str, tokens_used: int = 0) -> Dict[str, Any]:
        """
        Actualiza el uso mensual con operación UPSERT optimizada.
        
        Args:
            user_id (int): ID del usuario
            email_account_id (int): ID de la cuenta de email
            action_taken (str): Acción realizada
            tokens_used (int): Tokens utilizados
            
        Returns:
            dict: Resultado de la actualización
            
        Raises:
            ValueError: Si los parámetros son inválidos
            RuntimeError: Si hay error en la base de datos
        """
        if not isinstance(user_id, int) or user_id <= 0:
            raise ValueError("El ID del usuario debe ser un entero positivo")
        
        if not isinstance(email_account_id, int) or email_account_id <= 0:
            raise ValueError("El ID de la cuenta de email debe ser un entero positivo")
        
        if not action_taken or not action_taken.strip():
            raise ValueError("La acción realizada no puede estar vacía")
        
        if not isinstance(tokens_used, int) or tokens_used < 0:
            raise ValueError("Los tokens utilizados deben ser un entero no negativo")
        
        logger.info(f"🔄 Actualizando uso mensual para usuario {user_id}")
        logger.info(f"   Acción: {action_taken}, Tokens: {tokens_used}")
        
        try:
            with self.db_manager.get_db_session() as db:
                from ..models.statistics import UserUsageMonthly
                from sqlalchemy import text
                
                now = datetime.now()
                
                # UPSERT usando PostgreSQL ON CONFLICT
                upsert_query = text("""
                    INSERT INTO user_usage_monthly 
                    (user_id, year, month, emails_processed, emails_responded, 
                     emails_forwarded, tokens_used, created_at, last_updated)
                    VALUES 
                    (:user_id, :year, :month, 1, 
                     CASE WHEN :action_taken = 'responded' THEN 1 ELSE 0 END,
                     CASE WHEN :action_taken = 'forwarded' THEN 1 ELSE 0 END,
                     :tokens_used, :now, :now)
                    ON CONFLICT (user_id, year, month) 
                    DO UPDATE SET
                        emails_processed = user_usage_monthly.emails_processed + 1,
                        emails_responded = user_usage_monthly.emails_responded + 
                            CASE WHEN :action_taken = 'responded' THEN 1 ELSE 0 END,
                        emails_forwarded = user_usage_monthly.emails_forwarded + 
                            CASE WHEN :action_taken = 'forwarded' THEN 1 ELSE 0 END,
                        tokens_used = user_usage_monthly.tokens_used + :tokens_used,
                        last_updated = :now
                    RETURNING emails_processed, emails_responded, emails_forwarded, tokens_used;
                """)
                
                # Ejecutar UPSERT
                result = db.execute(upsert_query, {
                    'user_id': user_id,
                    'year': now.year,
                    'month': now.month,
                    'action_taken': action_taken,
                    'tokens_used': tokens_used,
                    'now': now
                })
                
                # Obtener valores actualizados
                row = result.fetchone()
                if row:
                    updated_values = {
                        'emails_processed': row[0],
                        'emails_responded': row[1],
                        'emails_forwarded': row[2],
                        'tokens_used': row[3]
                    }
                else:
                    # Fallback: consultar el registro
                    monthly_usage = UserUsageMonthly.get_or_create_current(
                        db, user_id, now.year, now.month
                    )
                    updated_values = {
                        'emails_processed': monthly_usage.emails_processed,
                        'emails_responded': monthly_usage.emails_responded,
                        'emails_forwarded': monthly_usage.emails_forwarded,
                        'tokens_used': monthly_usage.tokens_used
                    }
                
                logger.info(f"✅ Uso mensual actualizado para usuario {user_id}")
                logger.info(f"   Nuevos totales: {updated_values}")
                
                return {
                    'success': True,
                    'user_id': user_id,
                    'month': f"{now.year}-{now.month:02d}",
                    'updated_values': updated_values,
                    'increment': {
                        'emails': 1,
                        'tokens': tokens_used
                    },
                    'message': 'Uso mensual actualizado exitosamente'
                }
                
        except Exception as e:
            logger.error(f"❌ Error actualizando uso mensual para usuario {user_id}: {e}")
            raise RuntimeError(f"Error actualizando uso mensual: {str(e)}")
    
    def get_usage_summary(self, user_id: int) -> Dict[str, Any]:
        """
        Obtiene un resumen completo del uso del usuario.
        
        Args:
            user_id (int): ID del usuario
            
        Returns:
            dict: Resumen completo con uso actual, límites y proyecciones
        """
        if not isinstance(user_id, int) or user_id <= 0:
            raise ValueError("El ID del usuario debe ser un entero positivo")
        
        try:
            # Obtener validación de límites (incluye uso actual)
            validation = self.validate_usage_limits(user_id)
            
            # Calcular días restantes del mes
            now = datetime.now()
            next_month = (now.replace(day=1) + timedelta(days=32)).replace(day=1)
            days_remaining = (next_month - now).days
            
            # Calcular proyecciones simples
            emails_used = validation.current_usage['emails_per_month']
            days_elapsed = now.day
            
            if days_elapsed > 0:
                daily_average = emails_used / days_elapsed
                projected_monthly = daily_average * 30
            else:
                daily_average = 0
                projected_monthly = 0
            
            return {
                'user_id': user_id,
                'current_usage': validation.current_usage,
                'limits': validation.limits,
                'usage_percentage': validation.usage_percentage,
                'can_process': validation.can_process,
                'status_reason': validation.reason,
                'time_info': {
                    'current_month': f"{now.year}-{now.month:02d}",
                    'days_elapsed': days_elapsed,
                    'days_remaining': days_remaining,
                    'reset_date': next_month.strftime('%Y-%m-%d')
                },
                'projections': {
                    'daily_average': round(daily_average, 2),
                    'projected_monthly': round(projected_monthly, 0),
                    'will_exceed_limit': projected_monthly > validation.limits['emails_per_month']
                }
            }
            
        except Exception as e:
            logger.error(f"❌ Error obteniendo resumen de uso para usuario {user_id}: {e}")
            raise RuntimeError(f"Error obteniendo resumen de uso: {str(e)}")
    
    def set_custom_limits(self, limits: Dict[str, int]) -> None:
        """
        Establece límites personalizados (para testing o configuración futura).
        
        Args:
            limits (dict): Diccionario con límites personalizados
        """
        if not isinstance(limits, dict):
            raise ValueError("Los límites deben ser un diccionario")
        
        # Validar que los límites sean positivos
        for key, value in limits.items():
            if not isinstance(value, int) or value <= 0:
                raise ValueError(f"El límite '{key}' debe ser un entero positivo")
        
        # Actualizar límites
        self.limits.update(limits)
        logger.info(f"📊 Límites actualizados: {self.limits}")


# Instancia global del servicio de uso
# Se inicializará cuando se importe el módulo
usage_service = None

def get_usage_service():
    """
    Obtiene la instancia global del servicio de uso.
    
    Returns:
        UsageService: Instancia del servicio de uso
    """
    global usage_service
    if usage_service is None:
        from ..database import db_manager
        usage_service = UsageService(db_manager)
    return usage_service


def track_email_processed(user_id: int, email_data: Dict[str, Any]) -> Dict[str, Any]:
    """
    Función de conveniencia para trackear un email procesado.
    
    Args:
        user_id (int): ID del usuario
        email_data (dict): Datos del email procesado
        
    Returns:
        dict: Resultado del tracking
    """
    service = get_usage_service()
    return service.track_email_processed(user_id, email_data)


def validate_usage_limits(user_id: int) -> UsageValidation:
    """
    Función de conveniencia para validar límites de uso.
    
    Args:
        user_id (int): ID del usuario
        
    Returns:
        UsageValidation: Resultado de la validación
    """
    service = get_usage_service()
    return service.validate_usage_limits(user_id) 