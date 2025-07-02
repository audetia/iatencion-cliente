#!/usr/bin/env python3
"""
Script de prueba para verificar la funcionalidad del modelo User.

Este script prueba:
- Conexión a la base de datos
- Creación de tablas
- Operaciones CRUD básicas con el modelo User
"""

import sys
import os
from datetime import datetime

# Añadir el directorio src al path para poder importar los módulos
sys.path.append(os.path.join(os.path.dirname(__file__), 'src'))

from src.database import db_manager
from src.models import User, EmailAccount, create_tables


def test_database_connection():
    """Prueba la conexión básica a la base de datos."""
    print("🔍 Probando conexión a la base de datos...")
    
    if db_manager.test_connection():
        print("✅ Conexión exitosa")
        return True
    else:
        print("❌ Error de conexión")
        return False


def test_pgvector_extension():
    """Verifica que la extensión pgvector esté disponible."""
    print("🔍 Verificando extensión pgvector...")
    
    if db_manager.check_pgvector_extension():
        print("✅ pgvector disponible")
        return True
    else:
        print("⚠️  pgvector no encontrado (no crítico para User)")
        return True  # No es crítico para el modelo User


def test_create_tables():
    """Prueba la creación de tablas."""
    print("🔍 Creando tablas...")
    
    try:
        if create_tables():
            print("✅ Tablas creadas exitosamente")
            return True
        else:
            print("❌ Error creando tablas")
            return False
    except Exception as e:
        print(f"❌ Error creando tablas: {e}")
        return False


def test_user_crud():
    """Prueba operaciones CRUD básicas con el modelo User."""
    print("🔍 Probando operaciones CRUD con User...")
    
    try:
        # CREATE - Crear un usuario de prueba usando DatabaseManager
        print("  📝 Creando usuario...")
        create_result = db_manager.create_user(
            email="test@example.com",
            name="Usuario de Prueba"
        )
        
        if not create_result['success']:
            print(f"  ❌ Error creando usuario: {create_result}")
            return False
        
        user_id = create_result['user']['id']
        print(f"  ✅ Usuario creado con ID: {user_id}")
        
        # READ - Leer el usuario usando DatabaseManager
        print("  📖 Leyendo usuario...")
        found_user = db_manager.get_user_by_id(user_id)
        if found_user:
            print(f"  ✅ Usuario encontrado: {found_user['email']}")
            print(f"     - Email: {found_user['email']}")
            print(f"     - Nombre: {found_user['name']}")
            print(f"     - Verificado: {found_user['is_verified']}")
            print(f"     - Activo: {found_user['is_active']}")
            print(f"     - Creado: {found_user['created_at']}")
        else:
            print("  ❌ Usuario no encontrado")
            return False
        
        # UPDATE - Verificar usuario usando DatabaseManager
        print("  ✏️  Verificando usuario...")
        verify_result = db_manager.verify_user(user_id)
        if verify_result['success']:
            print(f"  ✅ Usuario verificado: {verify_result['user']['is_verified']}")
            print(f"  ✅ Usuario activo: {verify_result['user']['is_active']}")
        else:
            print(f"  ❌ Error verificando usuario: {verify_result}")
            return False
        
        # Test de métodos adicionales - actualizar nombre
        print("  🧪 Probando actualización de datos...")
        update_result = db_manager.update_user(user_id, name="Usuario Actualizado")
        if update_result['success']:
            print(f"  ✅ Usuario actualizado: {update_result['user']['name']}")
        else:
            print(f"  ❌ Error actualizando usuario: {update_result}")
            return False
        
        # READ final para verificar cambios
        print("  📖 Verificando cambios...")
        final_user = db_manager.get_user_by_id(user_id)
        if final_user and final_user['name'] == "Usuario Actualizado":
            print("  ✅ Cambios persistidos correctamente")
        else:
            print("  ❌ Los cambios no se persistieron")
            return False
        
        print("✅ Todas las operaciones CRUD exitosas")
        return True
        
    except Exception as e:
        print(f"❌ Error en operaciones CRUD: {e}")
        return False


def test_user_constraints():
    """Prueba las restricciones del modelo User."""
    print("🔍 Probando restricciones del modelo User...")
    
    try:
        # Crear primer usuario usando DatabaseManager
        print("  📝 Creando primer usuario...")
        create_result1 = db_manager.create_user(
            email="unique@example.com",
            name="Usuario 1"
        )
        
        if not create_result1['success']:
            print(f"  ❌ Error creando primer usuario: {create_result1}")
            return False
        
        print("  ✅ Primer usuario creado")
        
        # Intentar crear usuario con email duplicado
        print("  🚫 Intentando crear usuario con email duplicado...")
        try:
            create_result2 = db_manager.create_user(
                email="unique@example.com",  # Email duplicado
                name="Usuario 2"
            )
            
            if create_result2['success']:
                print("  ❌ No se detectó email duplicado")
                return False
            else:
                print("  ✅ Restricción de email único funcionando")
                
        except ValueError as e:
            if "ya existe" in str(e).lower():
                print("  ✅ Restricción de email único funcionando")
            else:
                print(f"  ❌ Error inesperado: {e}")
                return False
        except Exception as e:
            print(f"  ❌ Error inesperado: {e}")
            return False
        
        print("✅ Restricciones User funcionando correctamente")
        return True
        
    except Exception as e:
        print(f"❌ Error probando restricciones User: {e}")
        return False


def test_email_account_crud():
    """Prueba operaciones CRUD básicas con el modelo EmailAccount."""
    print("🔍 Probando operaciones CRUD con EmailAccount...")
    
    try:
        # Primero crear un usuario de prueba usando DatabaseManager
        print("  📝 Creando usuario de prueba...")
        user_result = db_manager.create_user(
            email="test@example.com",
            name="Usuario de Prueba"
        )
        
        if not user_result['success']:
            print(f"  ❌ Error creando usuario: {user_result}")
            return False
        
        user_id = user_result['user']['id']
        print(f"  ✅ Usuario creado con ID: {user_id}")
        
        # CREATE - Crear una cuenta de email usando DatabaseManager
        print("  📝 Creando cuenta de email...")
        account_result = db_manager.add_email_account(
            user_id=user_id,
            email="cuenta@gmail.com",
            imap_config={
                'server': "imap.gmail.com",
                'port': 993
            },
            smtp_config={
                'server': "smtp.gmail.com",
                'port': 587
            },
            password="contraseña_de_prueba"
        )
        
        if not account_result['success']:
            print(f"  ❌ Error creando cuenta: {account_result}")
            return False
        
        account_id = account_result['account']['id']
        print(f"  ✅ Cuenta de email creada con ID: {account_id}")
        
        # READ - Leer la cuenta usando DatabaseManager
        print("  📖 Leyendo cuenta de email...")
        accounts_result = db_manager.get_user_email_accounts(user_id)
        
        if not accounts_result['success'] or not accounts_result['accounts']:
            print(f"  ❌ Error obteniendo cuentas: {accounts_result}")
            return False
        
        found_account = accounts_result['accounts'][0]
        print(f"  ✅ Cuenta encontrada: {found_account['email']}")
        print(f"     - Email: {found_account['email']}")
        print(f"     - Servidor IMAP: {found_account['imap_server']}:{found_account['imap_port']}")
        print(f"     - Estado: {found_account['is_active']}")
        
        # Test de información básica
        print("  🔗 Probando información de cuenta...")
        account_info_result = db_manager.get_email_account_info(account_id)
        if account_info_result['success']:
            account_info = account_info_result['account_info']
            print(f"  ✅ Información obtenida: {account_info['email']}")
            print(f"     - User ID: {account_info['user_id']}")
            print(f"     - Estado activo: {account_info['is_active']}")
        else:
            print(f"  ❌ Error obteniendo información: {account_info_result}")
            return False
        
        # UPDATE - Desactivar cuenta usando DatabaseManager
        print("  ✏️  Desactivando cuenta...")
        update_result = db_manager.update_email_account(
            account_id, 
            is_active=False
        )
        
        if update_result['success']:
            print(f"  ✅ Cuenta desactivada: {update_result['account']['is_active']}")
        else:
            print(f"  ❌ Error desactivando cuenta: {update_result}")
            return False
        
        # Test de actualización de email
        print("  🔄 Probando actualización de email...")
        update_email_result = db_manager.update_email_account(
            account_id,
            email="nuevo_email@gmail.com"
        )
        
        if update_email_result['success']:
            print(f"  ✅ Email actualizado: {update_email_result['account']['email']}")
        else:
            print(f"  ❌ Error actualizando email: {update_email_result}")
            return False
        
        # Test de credenciales
        print("  🔐 Probando obtención de credenciales...")
        creds_result = db_manager.get_email_account_credentials(account_id)
        if creds_result['success']:
            creds = creds_result['credentials']
            print(f"  ✅ Credenciales obtenidas para: {creds['email']}")
            print(f"     - IMAP: {creds['imap_config']['server']}")
            print(f"     - SMTP: {creds['smtp_config']['server']}")
        else:
            print(f"  ❌ Error obteniendo credenciales: {creds_result}")
            return False
        
        # DELETE - Eliminar cuenta usando DatabaseManager
        print("  🗑️  Eliminando cuenta de prueba...")
        delete_result = db_manager.delete_email_account(account_id)
        
        if delete_result['success']:
            print(f"  ✅ Cuenta eliminada: {delete_result['deleted_account']['email']}")
        else:
            print(f"  ❌ Error eliminando cuenta: {delete_result}")
            return False
        
        print("✅ Todas las operaciones CRUD EmailAccount exitosas")
        return True
        
    except Exception as e:
        print(f"❌ Error en operaciones CRUD EmailAccount: {e}")
        return False


def test_email_account_validation():
    """Prueba las validaciones del modelo EmailAccount."""
    print("🔍 Probando validaciones de EmailAccount...")
    
    try:
        # Crear usuario de prueba
        print("  📝 Creando usuario de prueba...")
        user_result = db_manager.create_user(
            email="validation@test.com", 
            name="Test User"
        )
        
        if not user_result['success']:
            print(f"  ❌ Error creando usuario: {user_result}")
            return False
        
        user_id = user_result['user']['id']
        
        # Test cuenta válida
        print("  ✅ Probando cuenta válida...")
        try:
            valid_result = db_manager.add_email_account(
                user_id=user_id,
                email="valid@gmail.com",
                imap_config={'server': "imap.gmail.com", 'port': 993},
                smtp_config={'server': "smtp.gmail.com", 'port': 587},
                password="valid_password"
            )
            
            if valid_result['success']:
                print("  ✅ Cuenta válida creada correctamente")
                # Limpiar la cuenta válida
                db_manager.delete_email_account(valid_result['account']['id'])
            else:
                print(f"  ❌ Cuenta válida rechazada: {valid_result}")
                return False
        except Exception as e:
            print(f"  ❌ Error con cuenta válida: {e}")
            return False
        
        # Test email inválido
        print("  🚫 Probando email inválido...")
        try:
            invalid_email_result = db_manager.add_email_account(
                user_id=user_id,
                email="email_sin_arroba",  # Email inválido
                imap_config={'server': "imap.gmail.com", 'port': 993},
                smtp_config={'server': "smtp.gmail.com", 'port': 587},
                password="password"
            )
            
            if invalid_email_result['success']:
                print("  ❌ Email inválido no detectado")
                return False
            else:
                print("  ✅ Email inválido detectado correctamente")
        except ValueError as e:
            if "email" in str(e).lower():
                print("  ✅ Email inválido detectado correctamente")
            else:
                print(f"  ❌ Error inesperado: {e}")
                return False
        
        # Test puerto inválido
        print("  🚫 Probando puerto inválido...")
        try:
            invalid_port_result = db_manager.add_email_account(
                user_id=user_id,
                email="test@example.com",
                imap_config={'server': "imap.example.com", 'port': 99999},  # Puerto inválido
                smtp_config={'server': "smtp.example.com", 'port': 587},
                password="password"
            )
            
            if invalid_port_result['success']:
                print("  ❌ Puerto inválido no detectado")
                return False
            else:
                print("  ✅ Puerto inválido detectado correctamente")
        except ValueError as e:
            if "puerto" in str(e).lower():
                print("  ✅ Puerto inválido detectado correctamente")
            else:
                print(f"  ❌ Error inesperado: {e}")
                return False
        
        print("✅ Validaciones EmailAccount funcionando correctamente")
        return True
        
    except Exception as e:
        print(f"❌ Error probando validaciones EmailAccount: {e}")
        return False


def test_user_email_account_relationship():
    """Prueba la relación entre User y EmailAccount."""
    print("🔍 Probando relación User <-> EmailAccount...")
    
    try:
        # Crear usuario usando DatabaseManager
        print("  📝 Creando usuario...")
        user_result = db_manager.create_user(
            email="relation@test.com", 
            name="Usuario Relacion"
        )
        
        if not user_result['success']:
            print(f"  ❌ Error creando usuario: {user_result}")
            return False
        
        user_id = user_result['user']['id']
        
        # Crear múltiples cuentas de email usando DatabaseManager
        print("  📝 Creando múltiples cuentas...")
        created_accounts = []
        for i in range(3):
            account_result = db_manager.add_email_account(
                user_id=user_id,
                email=f"cuenta{i}@example.com",
                imap_config={'server': "imap.example.com", 'port': 993},
                smtp_config={'server': "smtp.example.com", 'port': 587},
                password=f"password{i}"
            )
            
            if not account_result['success']:
                print(f"  ❌ Error creando cuenta {i}: {account_result}")
                return False
            
            created_accounts.append(account_result['account'])
        
        print(f"  ✅ {len(created_accounts)} cuentas creadas")
        
        # Probar relación User -> EmailAccounts usando DatabaseManager
        print("  🔗 Probando User -> EmailAccounts...")
        accounts_result = db_manager.get_user_email_accounts(user_id)
        
        if not accounts_result['success']:
            print(f"  ❌ Error obteniendo cuentas: {accounts_result}")
            return False
        
        user_accounts = accounts_result['accounts']
        if len(user_accounts) == 3:
            print(f"  ✅ Usuario tiene {len(user_accounts)} cuentas")
            for account in user_accounts:
                print(f"     - {account['email']}")
        else:
            print(f"  ❌ Usuario debería tener 3 cuentas, tiene {len(user_accounts)}")
            return False
        
        # Probar relación EmailAccount -> User usando información de cuenta
        print("  🔗 Probando EmailAccount -> User...")
        first_account_id = created_accounts[0]['id']
        account_info_result = db_manager.get_email_account_info(first_account_id)
        
        if not account_info_result['success']:
            print(f"  ❌ Error obteniendo info de cuenta: {account_info_result}")
            return False
        
        account_info = account_info_result['account_info']
        if account_info['user_id'] == user_id:
            print(f"  ✅ Cuenta pertenece al usuario: {user_id}")
        else:
            print(f"  ❌ Relación EmailAccount -> User no funciona")
            return False
        
        # Verificar información del usuario desde la cuenta
        user_info = db_manager.get_user_by_id(account_info['user_id'])
        if user_info and user_info['email'] == "relation@test.com":
            print(f"  ✅ Usuario encontrado desde cuenta: {user_info['name']}")
        else:
            print("  ❌ No se pudo obtener usuario desde cuenta")
            return False
        
        # Limpiar - eliminar cuentas primero, luego usuario
        print("  🗑️  Limpiando datos de prueba...")
        for account in created_accounts:
            delete_result = db_manager.delete_email_account(account['id'])
            if not delete_result['success']:
                print(f"  ⚠️  Error eliminando cuenta {account['id']}: {delete_result}")
        
        print("  ✅ Cuentas eliminadas")
        
        print("✅ Relaciones funcionando correctamente")
        return True
        
    except Exception as e:
        print(f"❌ Error probando relaciones: {e}")
        return False


def main():
    """Función principal que ejecuta todas las pruebas."""
    print("=" * 60)
    print("🧪 PRUEBAS DE LOS MODELOS USER Y EMAILACCOUNT")
    print("=" * 60)
    
    tests = [
        ("Conexión a base de datos", test_database_connection),
        ("Extensión pgvector", test_pgvector_extension),
        ("Creación de tablas", test_create_tables),
        ("Operaciones CRUD User", test_user_crud),
        ("Restricciones User", test_user_constraints),
        ("Operaciones CRUD EmailAccount", test_email_account_crud),
        ("Validaciones EmailAccount", test_email_account_validation),
        ("Relación User <-> EmailAccount", test_user_email_account_relationship)
    ]
    
    results = []
    
    for test_name, test_func in tests:
        print(f"\n{'='*20} {test_name} {'='*20}")
        result = test_func()
        results.append((test_name, result))
        
        if not result:
            print(f"\n❌ Prueba '{test_name}' falló. Deteniendo...")
            break
    
    # Resumen
    print(f"\n{'='*60}")
    print("📊 RESUMEN DE PRUEBAS")
    print(f"{'='*60}")
    
    passed = sum(1 for _, result in results if result)
    total = len(results)
    
    for test_name, result in results:
        status = "✅ PASS" if result else "❌ FAIL"
        print(f"{status} - {test_name}")
    
    print(f"\n🏆 Resultado: {passed}/{total} pruebas exitosas")
    
    if passed == total:
        print("🎉 ¡Todas las pruebas pasaron! El modelo User está funcionando correctamente.")
    else:
        print("⚠️  Algunas pruebas fallaron. Revisa la configuración.")


if __name__ == "__main__":
    main()