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
        with db_manager.get_db_session() as db:
            # CREATE - Crear un usuario de prueba
            print("  📝 Creando usuario...")
            test_user = User(
                email="test@example.com",
                name="Usuario de Prueba",
                is_verified=False
            )
            db.add(test_user)
            db.flush()  # Para obtener el ID sin hacer commit
            user_id = test_user.id
            print(f"  ✅ Usuario creado con ID: {user_id}")
            
            # READ - Leer el usuario
            print("  📖 Leyendo usuario...")
            found_user = db.query(User).filter(User.id == user_id).first()
            if found_user:
                print(f"  ✅ Usuario encontrado: {found_user}")
                print(f"     - Email: {found_user.email}")
                print(f"     - Nombre: {found_user.name}")
                print(f"     - Verificado: {found_user.is_verified}")
                print(f"     - Activo: {found_user.is_active}")
                print(f"     - Creado: {found_user.created_at}")
            else:
                print("  ❌ Usuario no encontrado")
                return False
            
            # UPDATE - Verificar usuario
            print("  ✏️  Verificando usuario...")
            found_user.verify()
            db.flush()
            print(f"  ✅ Usuario verificado: {found_user.is_verified}")
            print(f"  ✅ Usuario activo: {found_user.is_active}")
            
            # Test de métodos adicionales
            print("  🧪 Probando métodos adicionales...")
            user_dict = found_user.to_dict()
            print(f"  ✅ to_dict(): {user_dict}")
            
            # DELETE - Eliminar usuario de prueba
            print("  🗑️  Eliminando usuario de prueba...")
            db.delete(found_user)
            print("  ✅ Usuario eliminado")
            
        print("✅ Todas las operaciones CRUD exitosas")
        return True
        
    except Exception as e:
        print(f"❌ Error en operaciones CRUD: {e}")
        return False


def test_user_constraints():
    """Prueba las restricciones del modelo User."""
    print("🔍 Probando restricciones del modelo User...")
    
    try:
        with db_manager.get_db_session() as db:
            # Crear primer usuario
            user1 = User(
                email="unique@example.com",
                name="Usuario 1"
            )
            db.add(user1)
            db.flush()
            print("  ✅ Primer usuario creado")
            
            # Intentar crear usuario con email duplicado
            user2 = User(
                email="unique@example.com",  # Email duplicado
                name="Usuario 2"
            )
            db.add(user2)
            
            try:
                db.flush()
                print("  ❌ No se detectó email duplicado")
                return False
            except Exception as e:
                print("  ✅ Restricción de email único funcionando")
                db.rollback()
                
            # Limpiar
            db.delete(user1)
            
        print("✅ Restricciones User funcionando correctamente")
        return True
        
    except Exception as e:
        print(f"❌ Error probando restricciones User: {e}")
        return False


def test_email_account_crud():
    """Prueba operaciones CRUD básicas con el modelo EmailAccount."""
    print("🔍 Probando operaciones CRUD con EmailAccount...")
    
    try:
        with db_manager.get_db_session() as db:
            # Primero crear un usuario de prueba
            test_user = User(
                email="test@example.com",
                name="Usuario de Prueba"
            )
            db.add(test_user)
            db.flush()
            user_id = test_user.id
            print(f"  📝 Usuario creado con ID: {user_id}")
            
            # CREATE - Crear una cuenta de email
            print("  📝 Creando cuenta de email...")
            test_account = EmailAccount(
                user_id=user_id,
                email="cuenta@gmail.com",
                imap_server="imap.gmail.com",
                imap_port=993,
                smtp_server="smtp.gmail.com",
                smtp_port=587,
                encrypted_password="contraseña_encriptada_fake",
                is_active=True
            )
            db.add(test_account)
            db.flush()
            account_id = test_account.id
            print(f"  ✅ Cuenta de email creada con ID: {account_id}")
            
            # READ - Leer la cuenta
            print("  📖 Leyendo cuenta de email...")
            found_account = db.query(EmailAccount).filter(EmailAccount.id == account_id).first()
            if found_account:
                print(f"  ✅ Cuenta encontrada: {found_account}")
                print(f"     - Email: {found_account.email}")
                print(f"     - Servidor IMAP: {found_account.imap_server}:{found_account.imap_port}")
                print(f"     - Estado: {found_account.is_active}")
                print(f"     - Display name: {found_account.display_name}")
            else:
                print("  ❌ Cuenta no encontrada")
                return False
            
            # Test de relación
            print("  🔗 Probando relación con User...")
            if found_account.user:
                print(f"  ✅ Relación funcionando: {found_account.user.name}")
            else:
                print("  ❌ Relación no funcionando")
                return False
            
            # Test de propiedades
            print("  🧪 Probando propiedades...")
            imap_config = found_account.imap_config
            smtp_config = found_account.smtp_config
            print(f"  ✅ IMAP config: {imap_config}")
            print(f"  ✅ SMTP config: {smtp_config}")
            
            # UPDATE - Desactivar cuenta
            print("  ✏️  Desactivando cuenta...")
            found_account.deactivate()
            db.flush()
            print(f"  ✅ Cuenta desactivada: {found_account.is_active}")
            
            # Test toggle
            print("  🔄 Probando toggle...")
            new_state = found_account.toggle_active()
            print(f"  ✅ Estado después de toggle: {new_state}")
            
            # Test de serialización
            print("  📄 Probando serialización...")
            account_dict = found_account.to_dict()
            print(f"  ✅ to_dict() (sin password): {len(account_dict)} campos")
            
            account_dict_with_pass = found_account.to_dict(include_password=True)
            print(f"  ✅ to_dict() (con password): {len(account_dict_with_pass)} campos")
            
            # DELETE - Eliminar datos de prueba
            print("  🗑️  Eliminando datos de prueba...")
            db.delete(found_account)
            db.delete(test_user)
            print("  ✅ Datos eliminados")
            
        print("✅ Todas las operaciones CRUD EmailAccount exitosas")
        return True
        
    except Exception as e:
        print(f"❌ Error en operaciones CRUD EmailAccount: {e}")
        return False


def test_email_account_validation():
    """Prueba las validaciones del modelo EmailAccount."""
    print("🔍 Probando validaciones de EmailAccount...")
    
    try:
        with db_manager.get_db_session() as db:
            # Crear usuario de prueba
            test_user = User(email="validation@test.com", name="Test User")
            db.add(test_user)
            db.flush()
            
            # Test cuenta válida
            print("  ✅ Probando cuenta válida...")
            valid_account = EmailAccount(
                user_id=test_user.id,
                email="valid@gmail.com",
                imap_server="imap.gmail.com",
                imap_port=993,
                smtp_server="smtp.gmail.com",
                smtp_port=587,
                encrypted_password="valid_password"
            )
            
            validation = valid_account.validate_config()
            if validation['is_valid']:
                print("  ✅ Cuenta válida correctamente validada")
            else:
                print(f"  ❌ Cuenta válida marcada como inválida: {validation['errors']}")
                return False
            
            # Test email inválido
            print("  🚫 Probando email inválido...")
            invalid_account = EmailAccount(
                user_id=test_user.id,
                email="email_sin_arroba",  # Email inválido
                imap_server="imap.gmail.com",
                imap_port=993,
                smtp_server="smtp.gmail.com",
                smtp_port=587,
                encrypted_password="password"
            )
            
            validation = invalid_account.validate_config()
            if not validation['is_valid'] and 'Email inválido' in validation['errors']:
                print("  ✅ Email inválido detectado correctamente")
            else:
                print("  ❌ Email inválido no detectado")
                return False
            
            # Test puerto inválido
            print("  🚫 Probando puerto inválido...")
            invalid_port_account = EmailAccount(
                user_id=test_user.id,
                email="test@example.com",
                imap_server="imap.example.com",
                imap_port=99999,  # Puerto inválido
                smtp_server="smtp.example.com",
                smtp_port=587,
                encrypted_password="password"
            )
            
            validation = invalid_port_account.validate_config()
            if not validation['is_valid'] and any('Puerto IMAP inválido' in error for error in validation['errors']):
                print("  ✅ Puerto inválido detectado correctamente")
            else:
                    print("  ❌ Puerto inválido no detectado")
                    return False
            
            # Limpiar
            db.delete(test_user)
            
        print("✅ Validaciones EmailAccount funcionando correctamente")
        return True
        
    except Exception as e:
        print(f"❌ Error probando validaciones EmailAccount: {e}")
        return False


def test_user_email_account_relationship():
    """Prueba la relación entre User y EmailAccount."""
    print("🔍 Probando relación User <-> EmailAccount...")
    
    try:
        with db_manager.get_db_session() as db:
            # Crear usuario
            user = User(email="relation@test.com", name="Usuario Relacion")
            db.add(user)
            db.flush()
            
            # Crear múltiples cuentas de email
            accounts = []
            for i in range(3):
                account = EmailAccount(
                    user_id=user.id,
                    email=f"cuenta{i}@example.com",
                    imap_server="imap.example.com",
                    imap_port=993,
                    smtp_server="smtp.example.com",
                    smtp_port=587,
                    encrypted_password=f"password{i}"
                )
                accounts.append(account)
                db.add(account)
            
            db.flush()
            
            # Probar relación User -> EmailAccounts
            print("  🔗 Probando User -> EmailAccounts...")
            user_accounts = user.email_accounts
            if len(user_accounts) == 3:
                print(f"  ✅ Usuario tiene {len(user_accounts)} cuentas")
                for account in user_accounts:
                    print(f"     - {account.email}")
            else:
                print(f"  ❌ Usuario debería tener 3 cuentas, tiene {len(user_accounts)}")
                return False
            
            # Probar relación EmailAccount -> User
            print("  🔗 Probando EmailAccount -> User...")
            first_account = accounts[0]
            if first_account.user and first_account.user.email == user.email:
                print(f"  ✅ Cuenta pertenece a: {first_account.user.name}")
            else:
                print("  ❌ Relación EmailAccount -> User no funciona")
                return False
            
            # Limpiar (cascade debería eliminar las cuentas automáticamente)
            db.delete(user)
            
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