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

from database import db_manager
from models import User, create_tables


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
    print("🔍 Probando restricciones del modelo...")
    
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
            
        print("✅ Restricciones funcionando correctamente")
        return True
        
    except Exception as e:
        print(f"❌ Error probando restricciones: {e}")
        return False


def main():
    """Función principal que ejecuta todas las pruebas."""
    print("=" * 60)
    print("🧪 PRUEBAS DEL MODELO USER")
    print("=" * 60)
    
    tests = [
        ("Conexión a base de datos", test_database_connection),
        ("Extensión pgvector", test_pgvector_extension),
        ("Creación de tablas", test_create_tables),
        ("Operaciones CRUD", test_user_crud),
        ("Restricciones del modelo", test_user_constraints)
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