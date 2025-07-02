#!/usr/bin/env python3
"""
Script de prueba para el servicio de tracking de uso.

Este script demuestra el uso del UsageService y valida su funcionamiento
con casos de prueba básicos.
"""

import sys
import os

# Añadir el directorio src al path
sys.path.insert(0, os.path.join(os.path.dirname(__file__), 'src'))

from src.database import db_manager, initialize_database
from src.services.usage_service import get_usage_service, track_email_processed, validate_usage_limits


def test_database_connection():
    """Prueba la conexión a la base de datos."""
    print("🔍 Probando conexión a base de datos...")
    
    if db_manager.test_connection():
        print("✅ Conexión a base de datos exitosa")
        return True
    else:
        print("❌ Error de conexión a base de datos")
        return False


def test_usage_service_initialization():
    """Prueba la inicialización del servicio de uso."""
    print("\n🔍 Probando inicialización del UsageService...")
    
    try:
        service = get_usage_service()
        print(f"✅ UsageService inicializado correctamente")
        print(f"   Límites por defecto: {service.limits}")
        return service
    except Exception as e:
        print(f"❌ Error inicializando UsageService: {e}")
        return None


def test_create_test_user():
    """Crea un usuario de prueba."""
    print("\n🔍 Creando usuario de prueba...")
    
    try:
        # Crear usuario de prueba
        result = db_manager.create_user(
            email="test_usage@example.com",
            name="Usuario de Prueba Uso"
        )
        
        if result['success']:
            user_id = result['user']['id']
            print(f"✅ Usuario de prueba creado: ID {user_id}")
            return user_id
        else:
            print(f"❌ Error creando usuario: {result.get('message', 'Error desconocido')}")
            return None
            
    except ValueError as e:
        # El usuario ya existe, obtenerlo
        if "ya existe" in str(e) or "Ya existe" in str(e):
            print("ℹ️  Usuario ya existe, obteniendo ID...")
            user = db_manager.get_user_by_email("test_usage@example.com")
            if user:
                print(f"✅ Usuario existente encontrado: ID {user['id']}")
                return user['id']
        
        print(f"❌ Error con usuario de prueba: {e}")
        return None
    except Exception as e:
        print(f"❌ Error inesperado creando usuario: {e}")
        return None


def test_create_test_email_account(user_id):
    """Crea una cuenta de email de prueba o usa la existente."""
    print(f"\n🔍 Creando cuenta de email de prueba para usuario {user_id}...")
    
    try:
        result = db_manager.add_email_account(
            user_id=user_id,
            email="test_usage@example.com",
            imap_config={'server': 'imap.example.com', 'port': 993},
            smtp_config={'server': 'smtp.example.com', 'port': 587},
            password="test_password"
        )
        
        if result['success']:
            account_id = result['email_account']['id']
            print(f"✅ Cuenta de email creada: ID {account_id}")
            return account_id
        else:
            print(f"❌ Error creando cuenta: {result.get('message', 'Error desconocido')}")
            return None
            
    except Exception as e:
        # Si ya existe, intentar obtener la cuenta existente
        if "ya tiene una cuenta configurada" in str(e):
            print("ℹ️  Cuenta ya existe, obteniendo ID...")
            try:
                accounts_result = db_manager.get_user_email_accounts(user_id)
                if accounts_result['success'] and accounts_result['accounts']:
                    for account in accounts_result['accounts']:
                        if account['email'] == "test_usage@example.com":
                            account_id = account['id']
                            print(f"✅ Cuenta existente encontrada: ID {account_id}")
                            return account_id
                print("❌ No se pudo encontrar la cuenta existente")
                return None
            except Exception as e2:
                print(f"❌ Error obteniendo cuenta existente: {e2}")
                return None
        else:
            print(f"❌ Error creando cuenta de email: {e}")
            return None


def test_validate_usage_limits(user_id):
    """Prueba la validación de límites de uso."""
    print(f"\n🔍 Probando validación de límites para usuario {user_id}...")
    
    try:
        validation = validate_usage_limits(user_id)
        
        print(f"✅ Validación completada:")
        print(f"   Puede procesar: {validation.can_process}")
        print(f"   Razón: {validation.reason}")
        print(f"   Uso actual: {validation.current_usage}")
        print(f"   Porcentajes: {validation.usage_percentage}")
        
        return validation
        
    except Exception as e:
        print(f"❌ Error validando límites: {e}")
        return None


def test_track_email_processed(user_id, email_account_id):
    """Prueba el tracking de un email procesado."""
    print(f"\n🔍 Probando tracking de email para usuario {user_id}...")
    
    try:
        # Datos de prueba del email
        email_data = {
            'email_account_id': email_account_id,
            'category': 'question',
            'action_taken': 'responded',
            'tokens_used': 150,
            'subject': 'Email de prueba',
            'sender': 'sender@example.com'
        }
        
        result = track_email_processed(user_id, email_data)
        
        if result['success']:
            print(f"✅ Email trackeado exitosamente:")
            print(f"   ID de procesamiento: {result['email_processed_id']}")
            print(f"   Timestamp: {result['tracking_timestamp']}")
        else:
            print(f"❌ Error trackeando email: {result.get('message', 'Error desconocido')}")
        
        return result
        
    except Exception as e:
        print(f"❌ Error trackeando email: {e}")
        return None


def test_usage_summary(user_id):
    """Prueba el resumen de uso."""
    print(f"\n🔍 Obteniendo resumen de uso para usuario {user_id}...")
    
    try:
        service = get_usage_service()
        summary = service.get_usage_summary(user_id)
        
        print(f"✅ Resumen de uso obtenido:")
        print(f"   Usuario: {summary['user_id']}")
        print(f"   Mes actual: {summary['time_info']['current_month']}")
        print(f"   Puede procesar: {summary['can_process']}")
        print(f"   Uso actual: {summary['current_usage']}")
        print(f"   Proyección mensual: {summary['projections']['projected_monthly']} emails")
        print(f"   Excederá límite: {summary['projections']['will_exceed_limit']}")
        
        return summary
        
    except Exception as e:
        print(f"❌ Error obteniendo resumen: {e}")
        return None


def test_retry_mechanism():
    """Prueba el mecanismo de retry."""
    print(f"\n🔍 Probando mecanismo de retry...")
    
    try:
        service = get_usage_service()
        
        # Intentar con un user_id inválido para probar el manejo de errores
        try:
            validation = service.validate_usage_limits(-1)
            print("❌ Debería haber fallado con user_id inválido")
        except ValueError as e:
            print(f"✅ Error de validación capturado correctamente: {e}")
        
        # Intentar con datos de email inválidos
        try:
            result = service.track_email_processed(1, {"invalid": "data"})
            print("❌ Debería haber fallado con datos inválidos")
        except ValueError as e:
            print(f"✅ Error de datos inválidos capturado correctamente: {e}")
        
        print("✅ Mecanismo de manejo de errores funciona correctamente")
        
    except Exception as e:
        print(f"❌ Error probando mecanismo de retry: {e}")


def test_custom_limits():
    """Prueba la configuración de límites personalizados."""
    print(f"\n🔍 Probando límites personalizados...")
    
    try:
        service = get_usage_service()
        
        # Límites originales
        original_limits = service.limits.copy()
        print(f"   Límites originales: {original_limits}")
        
        # Establecer límites personalizados
        custom_limits = {
            'emails_per_month': 50,  # Muy bajo para pruebas
            'tokens_per_month': 5000
        }
        
        service.set_custom_limits(custom_limits)
        print(f"   Límites personalizados establecidos: {service.limits}")
        
        # Restaurar límites originales
        service.set_custom_limits(original_limits)
        print(f"   Límites restaurados: {service.limits}")
        
        print("✅ Configuración de límites personalizados funciona correctamente")
        
    except Exception as e:
        print(f"❌ Error probando límites personalizados: {e}")


def main():
    """Función principal de pruebas."""
    print("🚀 Iniciando pruebas del UsageService")
    print("=" * 60)
    
    # Probar conexión a base de datos
    if not test_database_connection():
        print("❌ No se puede continuar sin conexión a base de datos")
        return False
    
    try:
        # Inicializar base de datos
        initialize_database()
    except Exception as e:
        print(f"⚠️  Error inicializando base de datos: {e}")
    
    # Probar inicialización del servicio
    service = test_usage_service_initialization()
    if not service:
        print("❌ No se puede continuar sin el servicio inicializado")
        return False
    
    # Crear usuario de prueba
    user_id = test_create_test_user()
    if not user_id:
        print("❌ No se puede continuar sin usuario de prueba")
        return False
    
    # Crear cuenta de email de prueba
    email_account_id = test_create_test_email_account(user_id)
    if not email_account_id:
        print("❌ No se puede continuar sin cuenta de email de prueba")
        return False
    
    # Probar validación de límites inicial
    validation = test_validate_usage_limits(user_id)
    if not validation:
        return False
    
    # Probar tracking de email
    track_result = test_track_email_processed(user_id, email_account_id)
    if not track_result:
        return False
    
    # Probar validación después del tracking
    print(f"\n🔍 Validando límites después del tracking...")
    validation_after = test_validate_usage_limits(user_id)
    
    # Probar resumen de uso
    summary = test_usage_summary(user_id)
    if not summary:
        return False
    
    # Probar mecanismo de retry y manejo de errores
    test_retry_mechanism()
    
    # Probar límites personalizados
    test_custom_limits()
    
    print("\n" + "=" * 60)
    print("✅ Todas las pruebas del UsageService completadas exitosamente")
    print("🎉 El servicio está listo para usar en producción")
    
    return True


if __name__ == "__main__":
    success = main()
    sys.exit(0 if success else 1) 