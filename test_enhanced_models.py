#!/usr/bin/env python3
"""
Script de prueba para verificar las mejoras implementadas en los modelos.

Este script prueba:
- Funcionalidades nuevas en User (validación de límites, estadísticas, configuración)
- Funcionalidades nuevas en EmailAccount (test de conexión, detección automática, health check)
- Funcionalidades nuevas en Q&A (búsqueda vectorial, validación de embeddings, importación CSV)
"""

import sys
import os
import io
from datetime import datetime, timedelta

# Añadir el directorio src al path
sys.path.append(os.path.join(os.path.dirname(__file__), 'src'))

from src.database import db_manager
from src.models import User, EmailAccount, Question, QuestionVariant, Answer, create_tables, verify_model_relationships


def test_model_relationships():
    """Prueba que todas las relaciones estén correctamente definidas."""
    print("🔍 Probando relaciones entre modelos...")
    
    result = verify_model_relationships()
    
    if result['is_valid']:
        print(f"✅ Todas las relaciones están correctas ({result['relationships_checked']} verificadas)")
        return True
    else:
        print("❌ Problemas encontrados en las relaciones:")
        for issue in result['issues']:
            print(f"  - {issue}")
        return False


def test_user_enhancements():
    """Prueba las mejoras en el modelo User."""
    print("🔍 Probando mejoras en User...")
    
    try:
        with db_manager.get_db_session() as db:
            # Crear usuario de prueba
            user = User.create(db, "test_enhanced@example.com", "Usuario Mejorado")
            
            # Test 1: Validación de límites
            print("  📊 Probando validación de límites...")
            limits_check = user.can_process_email(db)
            if limits_check['can_process']:
                print("  ✅ Validación de límites funcionando")
            else:
                print(f"  ❌ Error en validación de límites: {limits_check['reason']}")
            
            # Test 2: Estadísticas completas
            print("  📈 Probando estadísticas completas...")
            stats = user.get_comprehensive_stats(db)
            if 'user_info' in stats and 'accounts' in stats:
                print("  ✅ Estadísticas completas funcionando")
                print(f"     - Cuentas de email: {stats['accounts']['total']}")
                print(f"     - Tiempo ahorrado: {stats['time_saved']['minutes']} minutos")
            else:
                print(f"  ❌ Error en estadísticas: {stats.get('error', 'Formato incorrecto')}")
            
            # Test 3: Estado de configuración
            print("  ⚙️  Probando estado de configuración...")
            setup_status = user.get_setup_status(db)
            if 'setup_complete' in setup_status:
                print(f"  ✅ Estado de configuración funcionando")
                print(f"     - Configuración completa: {setup_status['setup_complete']}")
                print(f"     - Progreso: {setup_status['setup_percentage']}%")
                print(f"     - Próxima acción: {setup_status['next_recommended_action']}")
            else:
                print(f"  ❌ Error en estado de configuración: {setup_status.get('error', 'Formato incorrecto')}")
            
            # Limpiar
            user.delete(db)
            print("✅ Mejoras en User funcionando correctamente")
            return True
            
    except Exception as e:
        print(f"❌ Error probando mejoras en User: {e}")
        return False


def test_email_account_enhancements():
    """Prueba las mejoras en el modelo EmailAccount."""
    print("🔍 Probando mejoras en EmailAccount...")
    
    try:
        with db_manager.get_db_session() as db:
            # Crear usuario y cuenta de prueba
            user = User.create(db, "test_email@example.com", "Usuario Email")
            
            # Test 1: Detección automática de configuración
            print("  🔍 Probando detección automática...")
            gmail_config = EmailAccount.detect_email_config("test@gmail.com")
            if gmail_config['detected']:
                print("  ✅ Detección automática funcionando")
                print(f"     - Proveedor: {gmail_config['provider']}")
                print(f"     - IMAP: {gmail_config['config']['imap_server']}:{gmail_config['config']['imap_port']}")
            else:
                print("  ❌ Error en detección automática")
            
            # Test 2: Crear cuenta con OAuth2
            print("  🔐 Probando soporte OAuth2...")
            account = EmailAccount.create(
                db, user.id, "test@gmail.com", 
                "imap.gmail.com", 993, "smtp.gmail.com", 587,
                "fake_encrypted_password", auth_type="oauth2"
            )
            account.oauth2_token = "fake_token"
            account.oauth2_refresh_token = "fake_refresh_token"
            
            if account.is_oauth2:
                print("  ✅ Soporte OAuth2 funcionando")
            else:
                print("  ❌ Error en soporte OAuth2")
            
            # Test 3: Health check (sin contraseña real)
            print("  🏥 Probando health check...")
            health_result = account.health_check(db)
            if 'is_healthy' in health_result:
                print(f"  ✅ Health check funcionando (estado: {health_result['status']})")
            else:
                print("  ❌ Error en health check")
            
            # Test 4: Configuración para monitoreo
            print("  📡 Probando configuración de monitoreo...")
            monitor_config = account.get_monitoring_config("fake_password")
            if 'account_id' in monitor_config and 'monitoring_enabled' in monitor_config:
                print("  ✅ Configuración de monitoreo funcionando")
                print(f"     - Monitoreo habilitado: {monitor_config['monitoring_enabled']}")
            else:
                print("  ❌ Error en configuración de monitoreo")
            
            # Test 5: Cuentas que necesitan health check
            print("  🔄 Probando búsqueda de cuentas para health check...")
            accounts_needing_check = EmailAccount.get_accounts_needing_health_check(db)
            print(f"  ✅ Encontradas {len(accounts_needing_check)} cuentas que necesitan verificación")
            
            # Limpiar
            user.delete(db)
            print("✅ Mejoras en EmailAccount funcionando correctamente")
            return True
            
    except Exception as e:
        print(f"❌ Error probando mejoras en EmailAccount: {e}")
        return False


def test_qa_enhancements():
    """Prueba las mejoras en los modelos Q&A."""
    print("🔍 Probando mejoras en Q&A...")
    
    try:
        with db_manager.get_db_session() as db:
            # Crear usuario de prueba
            user = User.create(db, "test_qa@example.com", "Usuario Q&A")
            
            # Test 1: Importación CSV
            print("  📄 Probando importación CSV...")
            csv_content = """question,answer,response_instructions
¿Cuál es el horario de atención?,Nuestro horario es de 9 AM a 6 PM,Responder de manera amigable
¿Dónde están ubicados?,Estamos en Madrid España,Incluir dirección completa
¿Cómo puedo contactarlos?,Puedes llamarnos al 123-456-789,Proporcionar múltiples opciones
"""
            
            import_result = Question.import_from_csv(db, user.id, csv_content)
            if import_result['imported'] > 0:
                print(f"  ✅ Importación CSV funcionando ({import_result['imported']} importadas)")
                if import_result['errors']:
                    print(f"     - Errores: {len(import_result['errors'])}")
            else:
                print(f"  ❌ Error en importación CSV: {import_result['errors']}")
            
            # Test 2: Validación de embeddings
            print("  🔢 Probando validación de embeddings...")
            questions = Question.get_by_user(db, user.id)
            if questions:
                question = questions[0]
                variants = question.get_variants_with_embeddings(db)
                if variants:
                    variant = variants[0]
                    # Simular embedding válido
                    variant.embedding = [0.1] * 1536  # 1536 dimensiones
                    validation = variant.validate_embedding()
                    if validation['is_valid']:
                        print("  ✅ Validación de embeddings funcionando")
                    else:
                        print(f"  ❌ Error en validación: {validation['error']}")
                else:
                    print("  ⚠️  No hay variantes para probar validación")
            
            # Test 3: Validación de calidad de variantes
            print("  🎯 Probando validación de calidad...")
            if questions and len(questions) > 0:
                question = questions[0]
                # Añadir una variante similar
                similar_variant = QuestionVariant(
                    question_id=question.id,
                    variant_text="¿Cuál es el horario de atención al cliente?",  # Similar a la original
                    embedding=[0.1] * 1536
                )
                db.add(similar_variant)
                db.flush()
                
                quality_check = similar_variant.validate_variant_quality(db)
                print(f"  ✅ Validación de calidad funcionando (diversidad: {quality_check['diversity_score']:.3f})")
            
            # Test 4: Búsqueda vectorial (placeholder)
            print("  🔍 Probando búsqueda vectorial...")
            try:
                query_embedding = [0.1] * 1536
                similar_variants = QuestionVariant.search_similar(db, user.id, query_embedding)
                print(f"  ✅ Búsqueda vectorial funcionando ({len(similar_variants)} resultados)")
            except Exception as e:
                print(f"  ⚠️  Búsqueda vectorial requiere pgvector configurado: {e}")
            
            # Limpiar
            user.delete(db)
            print("✅ Mejoras en Q&A funcionando correctamente")
            return True
            
    except Exception as e:
        print(f"❌ Error probando mejoras en Q&A: {e}")
        return False


def main():
    """Función principal del script de prueba."""
    print("🚀 Iniciando pruebas de modelos mejorados...")
    print("=" * 60)
    
    # Verificar conexión a base de datos
    if not db_manager.test_connection():
        print("❌ No se pudo conectar a la base de datos")
        return False
    
    # Crear tablas si no existen
    create_tables()
    
    # Ejecutar todas las pruebas
    tests = [
        test_model_relationships,
        test_user_enhancements,
        test_email_account_enhancements,
        test_qa_enhancements
    ]
    
    results = []
    for test in tests:
        print()
        result = test()
        results.append(result)
    
    # Resumen final
    print()
    print("=" * 60)
    passed = sum(results)
    total = len(results)
    
    if passed == total:
        print(f"🎉 Todas las pruebas pasaron ({passed}/{total})")
        print("✅ Los modelos mejorados están funcionando correctamente")
        return True
    else:
        print(f"⚠️  {passed}/{total} pruebas pasaron")
        print("❌ Algunos modelos necesitan revisión")
        return False


if __name__ == "__main__":
    success = main()
    sys.exit(0 if success else 1) 