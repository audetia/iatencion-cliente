"""
Servicio de Monitoreo de Cuentas de Email.

Este servicio se encarga de monitorear la salud de las cuentas de email
de forma periódica, siguiendo el principio de Single Responsibility.
"""

import logging
from datetime import datetime, timedelta
from typing import List, Dict, Optional
from sqlalchemy.orm import Session

from ..models.email_account import EmailAccount
from ..tools.EmailTools import EmailToolsClass

# Configurar logging específico para este servicio
logger = logging.getLogger(__name__)

class EmailMonitoringService:
    """
    Servicio para monitoreo de cuentas de email.
    
    Responsabilidades:
    - Verificar salud de cuentas de email periódicamente
    - Actualizar estados de conexión
    - Generar reportes de estado
    - Gestionar notificaciones de problemas
    """
    
    def __init__(self, db_session_factory):
        """
        Inicializa el servicio de monitoreo.
        
        Args:
            db_session_factory: Factory para crear sesiones de base de datos
        """
        self.db_session_factory = db_session_factory
        self.logger = logger
        
    def monitor_all_accounts(self, hours_threshold: int = 24) -> Dict[str, int]:
        """
        Monitorea todas las cuentas que necesitan verificación.
        
        Args:
            hours_threshold (int): Horas desde último check para considerar necesaria verificación
            
        Returns:
            dict: Estadísticas del monitoreo realizado
        """
        stats = {
            'total_checked': 0,
            'healthy': 0,
            'warnings': 0,
            'errors': 0,
            'deactivated': 0
        }
        
        try:
            with self.db_session_factory() as db:
                # Obtener cuentas que necesitan verificación
                accounts_to_check = EmailAccount.get_accounts_needing_health_check(
                    db, hours_threshold
                )
                
                self.logger.info(f"Iniciando monitoreo de {len(accounts_to_check)} cuentas")
                
                for account in accounts_to_check:
                    try:
                        result = self._monitor_single_account(db, account)
                        stats['total_checked'] += 1
                        stats[result['category']] += 1
                        
                        self.logger.debug(
                            f"Cuenta {account.email}: {result['status']} - {result['message']}"
                        )
                        
                    except Exception as e:
                        self.logger.error(f"Error monitoreando cuenta {account.email}: {str(e)}")
                        stats['errors'] += 1
                
                # Commit todos los cambios
                db.commit()
                
                self.logger.info(
                    f"Monitoreo completado: {stats['total_checked']} cuentas verificadas. "
                    f"Saludables: {stats['healthy']}, Advertencias: {stats['warnings']}, "
                    f"Errores: {stats['errors']}, Desactivadas: {stats['deactivated']}"
                )
                
        except Exception as e:
            self.logger.error(f"Error en monitoreo masivo: {str(e)}")
            
        return stats
    
    def _monitor_single_account(self, db: Session, account: EmailAccount) -> Dict[str, str]:
        """
        Monitorea una cuenta individual.
        
        Args:
            db (Session): Sesión de base de datos
            account (EmailAccount): Cuenta a monitorear
            
        Returns:
            dict: Resultado del monitoreo
        """
        # Para el monitoreo automático, necesitaríamos acceso a la contraseña desencriptada
        # Por ahora, implementamos un health check básico sin conexión real
        
        try:
            # Verificación básica de configuración
            validation = account.validate_config()
            
            if not validation['is_valid']:
                account.health_status = 'error'
                account.is_active = False
                account.last_health_check = datetime.now()
                db.flush()
                
                return {
                    'status': 'error',
                    'category': 'errors',
                    'message': f"Configuración inválida: {', '.join(validation['errors'])}"
                }
            
            # Si la cuenta estaba desactivada por errores previos, 
            # marcarla como "unknown" para que pueda ser reactivada manualmente
            if account.health_status == 'error':
                account.health_status = 'unknown'
                account.last_health_check = datetime.now()
                db.flush()
                
                return {
                    'status': 'unknown',
                    'category': 'warnings',
                    'message': 'Configuración válida, requiere verificación manual'
                }
            
            # Actualizar timestamp de verificación
            account.last_health_check = datetime.now()
            db.flush()
            
            return {
                'status': account.health_status,
                'category': 'healthy' if account.health_status == 'healthy' else 'warnings',
                'message': 'Verificación básica completada'
            }
            
        except Exception as e:
            account.health_status = 'error'
            account.last_health_check = datetime.now()
            db.flush()
            
            return {
                'status': 'error',
                'category': 'errors',
                'message': f'Error en verificación: {str(e)}'
            }
    
    def test_account_connection(self, account_id: int, decrypted_password: str) -> Dict[str, any]:
        """
        Prueba la conexión de una cuenta específica con credenciales.
        
        Args:
            account_id (int): ID de la cuenta
            decrypted_password (str): Contraseña desencriptada
            
        Returns:
            dict: Resultado detallado del test
        """
        try:
            with self.db_session_factory() as db:
                account = EmailAccount.get_by_id(db, account_id)
                
                if not account:
                    return {
                        'success': False,
                        'error': 'Cuenta no encontrada'
                    }
                
                # Usar el método del modelo que delega a EmailTools
                connection_result = account.test_connection_detailed(decrypted_password)
                
                # Actualizar estado basado en resultado
                if connection_result['overall_status'] == 'success':
                    account.health_status = 'healthy'
                    account.is_active = True
                    success = True
                    message = 'Conexión exitosa'
                elif connection_result['overall_status'] == 'partial':
                    account.health_status = 'warning'
                    success = False
                    message = 'Conexión parcial - revisar configuración'
                else:
                    account.health_status = 'error'
                    account.is_active = False
                    success = False
                    message = 'Error de conexión'
                
                account.last_health_check = datetime.now()
                db.commit()
                
                return {
                    'success': success,
                    'message': message,
                    'connection_details': connection_result,
                    'account_status': account.health_status
                }
                
        except Exception as e:
            self.logger.error(f"Error testing account {account_id}: {str(e)}")
            return {
                'success': False,
                'error': str(e)
            }
    
    def get_monitoring_report(self) -> Dict[str, any]:
        """
        Genera un reporte del estado actual de todas las cuentas.
        
        Returns:
            dict: Reporte de estado
        """
        try:
            with self.db_session_factory() as db:
                # Estadísticas generales
                total_accounts = db.query(EmailAccount).count()
                active_accounts = db.query(EmailAccount).filter(EmailAccount.is_active == True).count()
                
                # Estadísticas por estado de salud
                health_stats = {}
                for status in ['healthy', 'warning', 'error', 'unknown']:
                    count = db.query(EmailAccount).filter(EmailAccount.health_status == status).count()
                    health_stats[status] = count
                
                # Cuentas que necesitan atención
                threshold_time = datetime.now() - timedelta(hours=24)
                needs_check = db.query(EmailAccount).filter(
                    EmailAccount.is_active == True,
                    (EmailAccount.last_health_check.is_(None) | 
                     (EmailAccount.last_health_check < threshold_time))
                ).count()
                
                return {
                    'timestamp': datetime.now().isoformat(),
                    'total_accounts': total_accounts,
                    'active_accounts': active_accounts,
                    'inactive_accounts': total_accounts - active_accounts,
                    'health_status': health_stats,
                    'needs_health_check': needs_check,
                    'monitoring_enabled': True
                }
                
        except Exception as e:
            self.logger.error(f"Error generating monitoring report: {str(e)}")
            return {
                'timestamp': datetime.now().isoformat(),
                'error': str(e),
                'monitoring_enabled': False
            }
    
    def create_email_tools_for_account(self, account_id: int, decrypted_password: str) -> Optional[EmailToolsClass]:
        """
        Crea una instancia de EmailTools configurada para una cuenta específica.
        
        Args:
            account_id (int): ID de la cuenta
            decrypted_password (str): Contraseña desencriptada
            
        Returns:
            EmailToolsClass | None: Instancia configurada o None si hay error
        """
        try:
            with self.db_session_factory() as db:
                account = EmailAccount.get_by_id(db, account_id)
                
                if not account:
                    self.logger.error(f"Account {account_id} not found")
                    return None
                
                # Obtener configuración de la cuenta
                account_config = account.get_config_for_connection()
                account_config.update({
                    'imap_server': account.imap_server,
                    'imap_port': account.imap_port,
                    'smtp_server': account.smtp_server,
                    'smtp_port': account.smtp_port,
                    'auth_type': account.auth_type,
                    'oauth2_token': account.oauth2_token if account.is_oauth2 else None
                })
                
                # Crear instancia de EmailTools
                return EmailToolsClass.create_email_tools_for_account(account_config, decrypted_password)
                
        except Exception as e:
            self.logger.error(f"Error creating EmailTools for account {account_id}: {str(e)}")
            return None 