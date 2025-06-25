#!/usr/bin/env python3
"""
Script de Monitoreo Periódico de Cuentas de Email.

Este script puede ejecutarse como un cron job o servicio para monitorear
la salud de las cuentas de email de forma automática.

Uso:
    python src/scripts/monitor_email_accounts.py [--hours-threshold 24] [--verbose]
"""

import sys
import argparse
import logging
from pathlib import Path

# Agregar el directorio raíz al path
sys.path.append(str(Path(__file__).parent.parent.parent))

from src.database import DatabaseManager
from src.services.email_monitoring_service import EmailMonitoringService

def setup_logging(verbose: bool = False):
    """Configura el logging para el script."""
    level = logging.DEBUG if verbose else logging.INFO
    logging.basicConfig(
        level=level,
        format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
        handlers=[
            logging.StreamHandler(),
            logging.FileHandler('logs/email_monitoring.log', mode='a')
        ]
    )

def main():
    """Función principal del script."""
    parser = argparse.ArgumentParser(description='Monitoreo de cuentas de email')
    parser.add_argument(
        '--hours-threshold', 
        type=int, 
        default=24,
        help='Horas desde último check para considerar necesaria verificación (default: 24)'
    )
    parser.add_argument(
        '--verbose', 
        action='store_true',
        help='Habilitar logging detallado'
    )
    parser.add_argument(
        '--report-only',
        action='store_true',
        help='Solo generar reporte sin realizar monitoreo'
    )
    
    args = parser.parse_args()
    
    # Configurar logging
    setup_logging(args.verbose)
    logger = logging.getLogger(__name__)
    
    try:
        # Inicializar base de datos
        db_manager = DatabaseManager()
        
        # Crear servicio de monitoreo
        monitoring_service = EmailMonitoringService(db_manager.get_db_session)
        
        if args.report_only:
            # Solo generar reporte
            logger.info("Generando reporte de estado...")
            report = monitoring_service.get_monitoring_report()
            
            print("\n" + "="*50)
            print("REPORTE DE CUENTAS DE EMAIL")
            print("="*50)
            print(f"Timestamp: {report['timestamp']}")
            print(f"Total de cuentas: {report['total_accounts']}")
            print(f"Cuentas activas: {report['active_accounts']}")
            print(f"Cuentas inactivas: {report['inactive_accounts']}")
            print(f"Necesitan verificación: {report['needs_health_check']}")
            print("\nEstado de salud:")
            for status, count in report['health_status'].items():
                print(f"  {status.capitalize()}: {count}")
            print("="*50)
            
        else:
            # Realizar monitoreo completo
            logger.info(f"Iniciando monitoreo de cuentas de email (threshold: {args.hours_threshold}h)")
            
            stats = monitoring_service.monitor_all_accounts(args.hours_threshold)
            
            # Mostrar resultados
            print("\n" + "="*50)
            print("RESULTADO DEL MONITOREO")
            print("="*50)
            print(f"Cuentas verificadas: {stats['total_checked']}")
            print(f"Saludables: {stats['healthy']}")
            print(f"Con advertencias: {stats['warnings']}")
            print(f"Con errores: {stats['errors']}")
            print(f"Desactivadas: {stats['deactivated']}")
            print("="*50)
            
            # Generar reporte final
            report = monitoring_service.get_monitoring_report()
            logger.info(f"Estado final: {report['active_accounts']} activas de {report['total_accounts']} total")
        
        logger.info("Monitoreo completado exitosamente")
        return 0
        
    except Exception as e:
        logger.error(f"Error en monitoreo: {str(e)}")
        return 1

if __name__ == "__main__":
    exit_code = main()
    sys.exit(exit_code) 