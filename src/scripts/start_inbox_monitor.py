#!/usr/bin/env python3
"""
Script de ejemplo para ejecutar el servicio InboxMonitor.

Este script demuestra cómo inicializar y ejecutar el servicio de monitoreo
de buzones de email de forma práctica.

Uso:
    python src/scripts/start_inbox_monitor.py [--workers 5] [--interval 300] [--verbose]
    python src/scripts/start_inbox_monitor.py --single-inbox 1  # Monitorear solo cuenta ID 1
"""

import sys
import argparse
import time
from pathlib import Path

# Agregar el directorio raíz al path
sys.path.append(str(Path(__file__).parent.parent.parent))

from src.services.inbox_monitor import InboxMonitor, MonitoringConfig
from custom_logging.config import setup_logging, get_logger

# Configurar logging
setup_logging()
logger = get_logger(__name__)


def example_email_processor(email_data: dict) -> None:
    """
    Función de ejemplo para procesar emails encontrados.
    
    En una implementación real, esto llamaría al workflow de LangGraph
    para procesar el email completamente.
    
    Args:
        email_data (dict): Datos del email a procesar
    """
    logger.info(f"Procesando email: {email_data.get('subject', 'Sin asunto')}")
    logger.info(f"De: {email_data.get('sender', 'Desconocido')}")
    logger.info(f"Cuenta: {email_data.get('account_email', 'Desconocida')}")
    
    # Aquí iría la lógica real de procesamiento
    # Por ejemplo: llamar al workflow de LangGraph
    # workflow_result = run_email_workflow(email_data)
    
    # Simular procesamiento
    time.sleep(0.1)
    
    logger.info(f"Email procesado exitosamente: {email_data.get('id', 'Sin ID')}")


def monitor_single_inbox_example(email_account_id: int) -> None:
    """
    Ejemplo de uso del método monitor_single_inbox.
    
    Este método demuestra cómo monitorear un buzón específico
    con reintentos exponenciales y ejecución del workflow de LangGraph.
    
    Args:
        email_account_id (int): ID de la cuenta de email a monitorear
    """
    logger.info(f"🎯 Iniciando monitoreo de buzón individual para cuenta {email_account_id}")
    
    # Configurar el monitor con configuración personalizada
    config = MonitoringConfig(
        max_workers=1,  # Solo un worker para monitoreo individual
        rate_limit_delay=1.0,  # Delay más corto para testing
        batch_size=5,  # Procesar pocos emails por vez
        check_interval=60,  # Verificar cada minuto
        connection_timeout=30,  # Timeout de 30 segundos
        max_retries=3,  # Máximo 3 reintentos
        retry_delay=10.0  # Delay base de 10 segundos
    )
    
    # Crear instancia del monitor (sin email_processor para usar workflow interno)
    monitor = InboxMonitor(email_processor=None, config=config)
    
    try:
        # Ejecutar monitoreo de buzón individual
        result = monitor.monitor_single_inbox(email_account_id)
        
        # Mostrar resultados
        logger.info("📊 Resultados del monitoreo:")
        logger.info(f"   ✅ Éxito: {result['success']}")
        logger.info(f"   📧 Emails encontrados: {result['emails_found']}")
        logger.info(f"   ✅ Emails procesados: {result['emails_processed']}")
        logger.info(f"   ❌ Emails fallidos: {result['emails_failed']}")
        logger.info(f"   🔄 Intentos de conexión: {result['connection_attempts']}")
        logger.info(f"   ⏱️ Tiempo de procesamiento: {result['processing_time']:.2f}s")
        
        if result['errors']:
            logger.warning(f"   ⚠️ Errores encontrados: {len(result['errors'])}")
            for error in result['errors']:
                logger.warning(f"      - {error}")
        
        # Mostrar detalles de cada email procesado
        if result['workflow_results']:
            logger.info("📋 Detalles de procesamiento por email:")
            for i, workflow_result in enumerate(result['workflow_results'], 1):
                logger.info(f"   Email {i}:")
                logger.info(f"      📧 Asunto: {workflow_result['email_subject']}")
                logger.info(f"      ✅ Éxito: {workflow_result['success']}")
                logger.info(f"      ⏱️ Tiempo: {workflow_result['processing_time']:.2f}s")
                if not workflow_result['success']:
                    logger.info(f"      ❌ Error: {workflow_result.get('error', 'Error desconocido')}")
        
    except Exception as e:
        logger.error(f"💥 Error en monitoreo de buzón individual: {str(e)}", exc_info=True)
        raise


def main():
    """Función principal del script."""
    parser = argparse.ArgumentParser(
        description="Servicio de monitoreo de buzones de email",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
Ejemplos de uso:
  # Monitoreo continuo de todas las cuentas activas
  python src/scripts/start_inbox_monitor.py --workers 5 --interval 300

  # Monitoreo de un buzón específico (una sola vez)
  python src/scripts/start_inbox_monitor.py --single-inbox 1

  # Monitoreo continuo con logging detallado
  python src/scripts/start_inbox_monitor.py --verbose
        """
    )
    
    # Argumentos para monitoreo continuo
    parser.add_argument(
        "--workers", 
        type=int, 
        default=5,
        help="Número de workers concurrentes (default: 5)"
    )
    
    parser.add_argument(
        "--interval", 
        type=int, 
        default=300,
        help="Intervalo entre verificaciones en segundos (default: 300)"
    )
    
    parser.add_argument(
        "--batch-size", 
        type=int, 
        default=10,
        help="Máximo de emails a procesar por lote (default: 10)"
    )
    
    parser.add_argument(
        "--max-retries", 
        type=int, 
        default=3,
        help="Máximo de reintentos por cuenta (default: 3)"
    )
    
    # Argumentos para monitoreo individual
    parser.add_argument(
        "--single-inbox", 
        type=int, 
        metavar="ACCOUNT_ID",
        help="Monitorear solo un buzón específico (por ID de cuenta)"
    )
    
    # Argumentos generales
    parser.add_argument(
        "--verbose", 
        action="store_true",
        help="Activar logging detallado"
    )
    
    args = parser.parse_args()
    
    # Configurar nivel de logging
    if args.verbose:
        import logging
        logging.getLogger().setLevel(logging.DEBUG)
        logger.info("🔍 Logging detallado activado")
    
    # Crear configuración personalizada
    config = MonitoringConfig(
        max_workers=args.workers,
        rate_limit_delay=2.0,
        batch_size=args.batch_size,
        check_interval=args.interval,
        connection_timeout=30,
        max_retries=args.max_retries,
        retry_delay=60.0
    )
    
    logger.info("🚀 Iniciando servicio de monitoreo de buzones")
    logger.info(f"   👥 Workers: {config.max_workers}")
    logger.info(f"   ⏱️ Intervalo: {config.check_interval}s")
    logger.info(f"   📦 Lote máximo: {config.batch_size}")
    logger.info(f"   🔄 Reintentos máximos: {config.max_retries}")
    
    try:
        if args.single_inbox:
            # Modo de monitoreo individual
            logger.info(f"🎯 Modo: Monitoreo individual de cuenta {args.single_inbox}")
            monitor_single_inbox_example(args.single_inbox)
            
        else:
            # Modo de monitoreo continuo
            logger.info("🔄 Modo: Monitoreo continuo de todas las cuentas activas")
            
            # Crear instancia del monitor
            monitor = InboxMonitor(
                email_processor=example_email_processor,
                config=config
            )
            
            # Iniciar monitoreo continuo
            monitor.start_monitoring()
            
    except KeyboardInterrupt:
        logger.info("⏹️ Deteniendo servicio por interrupción del usuario")
    except Exception as e:
        logger.error(f"💥 Error fatal en el servicio: {str(e)}", exc_info=True)
        sys.exit(1)
    finally:
        logger.info("🏁 Servicio de monitoreo finalizado")


if __name__ == "__main__":
    main() 