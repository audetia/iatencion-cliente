#!/usr/bin/env python3
"""
Demostración del método monitor_single_inbox del InboxMonitor.

Este script muestra cómo usar el método monitor_single_inbox para monitorear
un buzón específico con reintentos exponenciales y ejecución del workflow de LangGraph.

Uso:
    python src/scripts/demo_single_inbox.py <email_account_id>
    python src/scripts/demo_single_inbox.py 1
"""

import sys
import argparse
from pathlib import Path

# Agregar el directorio raíz al path
sys.path.append(str(Path(__file__).parent.parent.parent))

from src.services.inbox_monitor import InboxMonitor, MonitoringConfig
from custom_logging.config import setup_logging, get_logger

# Configurar logging
setup_logging()
logger = get_logger(__name__)


def demo_monitor_single_inbox(email_account_id: int) -> None:
    """
    Demostración completa del método monitor_single_inbox.
    
    Este ejemplo muestra:
    1. Configuración personalizada del monitor
    2. Ejecución del monitoreo individual
    3. Interpretación de resultados
    4. Manejo de errores
    
    Args:
        email_account_id (int): ID de la cuenta de email a monitorear
    """
    print("=" * 70)
    print("🎯 DEMOSTRACIÓN: monitor_single_inbox")
    print("=" * 70)
    print()
    
    print(f"📧 Cuenta a monitorear: {email_account_id}")
    print()
    
    # 1. Configuración personalizada
    print("🔧 PASO 1: Configuración del Monitor")
    print("-" * 40)
    
    config = MonitoringConfig(
        max_workers=1,              # Solo un worker para demo
        rate_limit_delay=1.0,       # Delay corto para demo
        batch_size=5,               # Procesar pocos emails
        check_interval=60,          # No relevante para single inbox
        connection_timeout=30,      # Timeout de conexión
        max_retries=3,              # Máximo 3 reintentos
        retry_delay=5.0             # Delay base de 5 segundos
    )
    
    print(f"   ✓ Max reintentos: {config.max_retries}")
    print(f"   ✓ Delay base: {config.retry_delay}s")
    print(f"   ✓ Batch size: {config.batch_size}")
    print(f"   ✓ Timeout: {config.connection_timeout}s")
    print()
    
    # 2. Crear instancia del monitor
    print("🏗️  PASO 2: Inicialización del Monitor")
    print("-" * 40)
    
    monitor = InboxMonitor(config=config)
    print("   ✓ InboxMonitor inicializado")
    print("   ✓ Configuración aplicada")
    print("   ✓ Rate limiter configurado")
    print()
    
    # 3. Ejecutar monitoreo
    print("🚀 PASO 3: Ejecución del Monitoreo")
    print("-" * 40)
    
    try:
        print(f"   🔍 Iniciando monitoreo de cuenta {email_account_id}...")
        
        # Ejecutar el monitoreo
        result = monitor.monitor_single_inbox(email_account_id)
        
        print("   ✅ Monitoreo completado exitosamente")
        print()
        
        # 4. Mostrar resultados principales
        print("📊 PASO 4: Resultados del Monitoreo")
        print("-" * 40)
        
        print(f"   🎯 Cuenta procesada: {result['email_account_id']}")
        print(f"   ✅ Éxito general: {result['success']}")
        print(f"   📧 Emails encontrados: {result['emails_found']}")
        print(f"   ✅ Emails procesados: {result['emails_processed']}")
        print(f"   ❌ Emails fallidos: {result['emails_failed']}")
        print(f"   🔄 Intentos de conexión: {result['connection_attempts']}")
        print(f"   ⏱️  Tiempo total: {result['processing_time']:.2f}s")
        print(f"   📅 Timestamp: {result['timestamp'].strftime('%Y-%m-%d %H:%M:%S')}")
        print()
        
        # 5. Mostrar errores si los hay
        if result['errors']:
            print("⚠️  ERRORES ENCONTRADOS")
            print("-" * 40)
            for i, error in enumerate(result['errors'], 1):
                print(f"   {i}. {error}")
            print()
        
        # 6. Mostrar detalles de procesamiento por email
        if result['workflow_results']:
            print("📋 DETALLES POR EMAIL")
            print("-" * 40)
            
            for i, workflow_result in enumerate(result['workflow_results'], 1):
                print(f"   📧 Email {i}:")
                print(f"      • ID: {workflow_result['email_id']}")
                print(f"      • Asunto: {workflow_result['email_subject']}")
                print(f"      • Éxito: {'✅' if workflow_result['success'] else '❌'}")
                print(f"      • Tiempo: {workflow_result['processing_time']:.2f}s")
                
                if not workflow_result['success']:
                    print(f"      • Error: {workflow_result.get('error', 'Error desconocido')}")
                
                if workflow_result.get('workflow_output'):
                    print(f"      • Workflow completado: ✅")
                
                print()
        
        # 7. Análisis de rendimiento
        print("📈 ANÁLISIS DE RENDIMIENTO")
        print("-" * 40)
        
        if result['emails_found'] > 0:
            avg_time = result['processing_time'] / result['emails_found']
            print(f"   ⏱️  Tiempo promedio por email: {avg_time:.2f}s")
            
            success_rate = (result['emails_processed'] / result['emails_found']) * 100
            print(f"   📊 Tasa de éxito: {success_rate:.1f}%")
            
            if result['connection_attempts'] > 1:
                print(f"   🔄 Reintentos necesarios: {result['connection_attempts'] - 1}")
        else:
            print("   📭 No se encontraron emails para procesar")
        
        print()
        
        # 8. Recomendaciones
        print("💡 RECOMENDACIONES")
        print("-" * 40)
        
        if result['connection_attempts'] > 1:
            print("   ⚠️  Se necesitaron reintentos - verificar conectividad")
        
        if result['emails_failed'] > 0:
            print("   ⚠️  Algunos emails fallaron - revisar logs detallados")
        
        if result['processing_time'] > 60:
            print("   ⚠️  Procesamiento lento - considerar reducir batch_size")
        
        if result['emails_found'] == 0:
            print("   ℹ️  No hay emails nuevos - el buzón está al día")
        
        if result['emails_processed'] > 0:
            print("   ✅ Emails procesados exitosamente")
        
        print()
        
    except ValueError as e:
        print("❌ ERROR DE VALIDACIÓN")
        print("-" * 40)
        print(f"   Error: {str(e)}")
        print("   Solución: Verificar que el email_account_id sea un entero positivo")
        print()
        
    except RuntimeError as e:
        print("❌ ERROR DE CONEXIÓN")
        print("-" * 40)
        print(f"   Error: {str(e)}")
        print("   Posibles causas:")
        print("   • Cuenta no existe en la base de datos")
        print("   • Credenciales incorrectas o expiradas")
        print("   • Problemas de conectividad de red")
        print("   • Servidor IMAP no disponible")
        print()
        
    except Exception as e:
        print("❌ ERROR INESPERADO")
        print("-" * 40)
        print(f"   Error: {str(e)}")
        print(f"   Tipo: {type(e).__name__}")
        print("   Solución: Revisar logs detallados para más información")
        print()
    
    print("🏁 Demostración completada")
    print("=" * 70)


def show_method_info():
    """Muestra información detallada sobre el método monitor_single_inbox."""
    print("=" * 70)
    print("📚 INFORMACIÓN DEL MÉTODO: monitor_single_inbox")
    print("=" * 70)
    print()
    
    print("📝 DESCRIPCIÓN")
    print("-" * 40)
    print("Monitorea un buzón específico de email con reintentos exponenciales.")
    print("Ejecuta el workflow de LangGraph para cada email encontrado.")
    print()
    
    print("📥 PARÁMETROS")
    print("-" * 40)
    print("• email_account_id (int): ID de la cuenta de email a monitorear")
    print("  - Debe ser un entero positivo")
    print("  - La cuenta debe existir en la base de datos")
    print("  - Debe tener credenciales válidas")
    print()
    
    print("📤 RETORNA")
    print("-" * 40)
    print("• Dict con las siguientes claves:")
    print("  - email_account_id: ID de la cuenta procesada")
    print("  - success: True si el monitoreo fue exitoso")
    print("  - emails_found: Número de emails encontrados")
    print("  - emails_processed: Número de emails procesados exitosamente")
    print("  - emails_failed: Número de emails que fallaron")
    print("  - connection_attempts: Número de intentos de conexión")
    print("  - errors: Lista de errores encontrados")
    print("  - processing_time: Tiempo total en segundos")
    print("  - timestamp: Timestamp del monitoreo")
    print("  - workflow_results: Resultados detallados por email")
    print()
    
    print("🔄 REINTENTOS EXPONENCIALES")
    print("-" * 40)
    print("• Algoritmo: delay = min(base_delay * (2 ** (attempt - 1)), 300)")
    print("• Delay máximo: 5 minutos")
    print("• Configurable en MonitoringConfig")
    print()
    
    print("⚠️  EXCEPCIONES")
    print("-" * 40)
    print("• ValueError: Si email_account_id es inválido")
    print("• RuntimeError: Error crítico después de todos los reintentos")
    print()
    
    print("🔧 CONFIGURACIÓN")
    print("-" * 40)
    print("• max_retries: Máximo número de reintentos (default: 3)")
    print("• retry_delay: Delay base en segundos (default: 60.0)")
    print("• batch_size: Máximo emails por lote (default: 10)")
    print("• connection_timeout: Timeout de conexión (default: 30)")
    print()


def main():
    """Función principal del script de demostración."""
    parser = argparse.ArgumentParser(
        description="Demostración del método monitor_single_inbox",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
Ejemplos de uso:
  # Monitorear cuenta específica
  python src/scripts/demo_single_inbox.py 1

  # Mostrar información del método
  python src/scripts/demo_single_inbox.py --info

  # Monitorear con logging detallado
  python src/scripts/demo_single_inbox.py 1 --verbose
        """
    )
    
    parser.add_argument(
        "email_account_id",
        type=int,
        nargs="?",
        help="ID de la cuenta de email a monitorear"
    )
    
    parser.add_argument(
        "--info",
        action="store_true",
        help="Mostrar información detallada del método"
    )
    
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
    
    try:
        if args.info:
            # Mostrar información del método
            show_method_info()
            
        elif args.email_account_id:
            # Ejecutar demostración
            demo_monitor_single_inbox(args.email_account_id)
            
        else:
            # Mostrar ayuda si no se proporciona argumento
            parser.print_help()
            print()
            print("💡 Sugerencia: Usar --info para ver información del método")
            
    except KeyboardInterrupt:
        print()
        print("⏹️  Demostración interrumpida por el usuario")
    except Exception as e:
        logger.error(f"💥 Error en la demostración: {str(e)}", exc_info=True)
        sys.exit(1)


if __name__ == "__main__":
    main() 