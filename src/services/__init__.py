"""
Servicios de la aplicación.

Este paquete contiene los servicios de negocio que implementan la lógica
de la aplicación siguiendo el principio de Single Responsibility.
"""

from .email_monitoring_service import EmailMonitoringService

__all__ = ['EmailMonitoringService'] 