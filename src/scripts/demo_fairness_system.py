#!/usr/bin/env python3
"""
Script de demostración del sistema de fairness para InboxMonitor.

Este script muestra cómo usar el sistema completo de fairness para evitar
que cuentas de alto volumen monopolicen el procesamiento de emails.
"""

import time
import threading
from datetime import datetime
from typing import Dict, List

from src.services.inbox_monitor import InboxMonitor, MonitoringConfig
from src.models.fairness import FairnessConfig, AccountQuota, AccountPriority
from custom_logging.config import get_logger

logger = get_logger(__name__)


def demo_fairness_system():
    """
    Demuestra el sistema de fairness en acción.
    
    Simula un escenario con:
    - Cuenta A: Alto volumen (500 emails/min) - debe ser limitada
    - Cuenta B: Volumen normal (50 emails/min) - procesamiento equilibrado
    - Cuenta C: Bajo volumen (5 emails/min) - debe tener prioridad
    """
    
    logger.info("🎯 Iniciando demostración del sistema de fairness")
    
    # Configuración con fairness habilitado
    config = MonitoringConfig(
        max_workers=5,
        enable_fairness=True,
        fairness_config=FairnessConfig(
            default_max_emails_per_minute=10,
            default_max_concurrent=2,
            high_volume_threshold=100,
            normal_volume_threshold=10
        )
    )
    
    # Crear instancia de InboxMonitor
    monitor = InboxMonitor(config=config)
    
    try:
        # Simular cuentas con diferentes volúmenes
        demo_accounts = [
            {'account_id': 1, 'email': 'high_volume@example.com', 'volume': 500},
            {'account_id': 2, 'email': 'normal_volume@example.com', 'volume': 50},
            {'account_id': 3, 'email': 'low_volume@example.com', 'volume': 5}
        ]
        
        logger.info("📊 Configurando cuentas de demostración")
        
        # Configurar cuotas específicas para demostración
        if monitor.fairness_manager:
            for account in demo_accounts:
                priority = AccountPriority.from_volume(account['volume'])
                quota = AccountQuota(
                    account_id=account['account_id'],
                    max_emails_per_minute=5 if priority == AccountPriority.HIGH_VOLUME else 10,
                    max_concurrent_processing=1 if priority == AccountPriority.HIGH_VOLUME else 2,
                    priority=priority
                )
                monitor.fairness_manager.set_account_quota(account['account_id'], quota)
                
                logger.info(f"Cuota configurada para {account['email']}", extra={
                    'account_id': account['account_id'],
                    'priority': priority.name,
                    'max_per_minute': quota.max_emails_per_minute,
                    'max_concurrent': quota.max_concurrent_processing
                })
        
        # Simular envío de emails a diferentes ritmos
        logger.info("📧 Simulando envío de emails...")
        
        # Thread para simular emails de alto volumen
        def simulate_high_volume():
            for i in range(20):  # 20 emails
                if monitor.fairness_manager:
                    email_data = {
                        'id': f'high_vol_{i}',
                        'subject': f'High Volume Email {i}',
                        'from': 'sender@example.com',
                        'to': 'high_volume@example.com',
                        'body': f'This is high volume email {i}'
                    }
                    monitor.fairness_manager.enqueue_email(1, f'high_vol_{i}', email_data)
                    time.sleep(0.1)  # 10 emails por segundo
        
        # Thread para simular emails de volumen normal
        def simulate_normal_volume():
            for i in range(10):  # 10 emails
                if monitor.fairness_manager:
                    email_data = {
                        'id': f'normal_vol_{i}',
                        'subject': f'Normal Volume Email {i}',
                        'from': 'sender@example.com',
                        'to': 'normal_volume@example.com',
                        'body': f'This is normal volume email {i}'
                    }
                    monitor.fairness_manager.enqueue_email(2, f'normal_vol_{i}', email_data)
                    time.sleep(0.5)  # 2 emails por segundo
        
        # Thread para simular emails de bajo volumen
        def simulate_low_volume():
            for i in range(5):  # 5 emails
                if monitor.fairness_manager:
                    email_data = {
                        'id': f'low_vol_{i}',
                        'subject': f'Low Volume Email {i}',
                        'from': 'sender@example.com',
                        'to': 'low_volume@example.com',
                        'body': f'This is low volume email {i}'
                    }
                    monitor.fairness_manager.enqueue_email(3, f'low_vol_{i}', email_data)
                    time.sleep(1.0)  # 1 email por segundo
        
        # Iniciar threads de simulación
        threads = []
        threads.append(threading.Thread(target=simulate_high_volume, name="high_volume_sim"))
        threads.append(threading.Thread(target=simulate_normal_volume, name="normal_volume_sim"))
        threads.append(threading.Thread(target=simulate_low_volume, name="low_volume_sim"))
        
        for thread in threads:
            thread.start()
        
        # Esperar a que terminen las simulaciones
        for thread in threads:
            thread.join()
        
        logger.info("✅ Simulación de emails completada")
        
        # Mostrar métricas de fairness
        if monitor.fairness_manager:
            fairness_metrics = monitor.fairness_manager.get_fairness_metrics()
            
            logger.info("📊 Métricas de Fairness:", extra={
                'fairness_score': fairness_metrics['fairness_score'],
                'queue_size': fairness_metrics['queue_stats']['queue_size'],
                'accounts_tracked': fairness_metrics['queue_stats']['accounts_tracked']
            })
            
            # Mostrar métricas por cuenta
            for account_id, metrics in fairness_metrics['queue_stats']['account_metrics'].items():
                logger.info(f"Cuenta {account_id}:", extra={
                    'emails_last_minute': metrics['emails_last_minute'],
                    'current_concurrent': metrics['current_concurrent'],
                    'quota_per_minute': metrics['quota_per_minute'],
                    'utilization': f"{(metrics['emails_last_minute'] / metrics['quota_per_minute'] * 100):.1f}%" if metrics['quota_per_minute'] > 0 else "0%"
                })
        
        # Mostrar métricas del procesador
        if monitor.email_processor_service:
            processor_metrics = monitor.email_processor_service.get_metrics()
            
            logger.info("📧 Métricas del Procesador:", extra={
                'total_processed': processor_metrics['total_processed'],
                'total_failed': processor_metrics['total_failed'],
                'success_rate': f"{processor_metrics['success_rate']:.1f}%",
                'emails_per_minute': f"{processor_metrics['emails_per_minute']:.1f}"
            })
        
        # Esperar un poco para que se procesen los emails restantes
        logger.info("⏳ Esperando procesamiento de emails restantes...")
        time.sleep(10)
        
        # Mostrar estado final
        status = monitor.get_monitoring_status()
        logger.info("🏁 Estado Final del Sistema:", extra={
            'fairness_enabled': status['service_info']['features_enabled']['fairness_system'],
            'fairness_score': status.get('fairness_metrics', {}).get('fairness_score', 'N/A'),
            'queue_size': status.get('fairness_metrics', {}).get('queue_stats', {}).get('queue_size', 0)
        })
        
    except KeyboardInterrupt:
        logger.info("🛑 Demostración interrumpida por el usuario")
    except Exception as e:
        logger.error(f"❌ Error en demostración: {str(e)}", exc_info=True)
    finally:
        # Limpiar
        if monitor.is_running:
            monitor.stop_monitoring()
        
        logger.info("🎯 Demostración completada")


def demo_without_fairness():
    """
    Demuestra el comportamiento sin fairness para comparación.
    """
    logger.info("🔴 Demostración SIN sistema de fairness")
    
    config = MonitoringConfig(
        max_workers=5,
        enable_fairness=False  # Deshabilitar fairness
    )
    
    monitor = InboxMonitor(config=config)
    
    logger.info("⚠️ Sin fairness, las cuentas de alto volumen pueden monopolizar el sistema")
    logger.info("💡 Habilitar fairness para evitar este problema")


if __name__ == "__main__":
    print("🎯 Sistema de Fairness - InboxMonitor")
    print("=" * 50)
    
    # Demostrar con fairness
    demo_fairness_system()
    
    print("\n" + "=" * 50)
    
    # Demostrar sin fairness
    demo_without_fairness()
    
    print("\n✅ Demostración completada")
    print("\n📋 Resumen:")
    print("- Con fairness: Cuentas de alto volumen son limitadas")
    print("- Sin fairness: Cuentas de alto volumen pueden monopolizar")
    print("- Fairness score: Mide la equidad del sistema (0-100)")
    print("- Cuotas dinámicas: Se ajustan automáticamente según el volumen") 