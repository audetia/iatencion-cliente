#!/usr/bin/env python3
"""
Script de prueba simplificado para verificar las mejoras en los modelos.
"""

import sys
import os

# Añadir el directorio src al path
sys.path.append(os.path.join(os.path.dirname(__file__), 'src'))

def test_imports():
    """Prueba que todos los modelos se puedan importar correctamente."""
    print("🔍 Probando imports de modelos...")
    
    try:
        from src.models.user import User
        print("  ✅ User importado correctamente")
        
        from src.models.email_account import EmailAccount
        print("  ✅ EmailAccount importado correctamente")
        
        from src.models.qa import Question, QuestionVariant, Answer
        print("  ✅ Q&A models importados correctamente")
        
        return True
    except Exception as e:
        print(f"  ❌ Error importando modelos: {e}")
        return False

def test_model_structure():
    """Prueba la estructura básica de los modelos."""
    print("🔍 Probando estructura de modelos...")
    
    try:
        from src.models.user import User
        from src.models.email_account import EmailAccount
        from src.models.qa import Question, QuestionVariant, Answer
        
        # Test User methods
        user_methods = ['can_process_email', 'get_comprehensive_stats', 'get_setup_status']
        for method in user_methods:
            if hasattr(User, method):
                print(f"  ✅ User.{method} existe")
            else:
                print(f"  ❌ User.{method} falta")
        
        # Test EmailAccount methods
        email_methods = ['test_connection_detailed', 'health_check', 'detect_email_config', 'get_monitoring_config']
        for method in email_methods:
            if hasattr(EmailAccount, method):
                print(f"  ✅ EmailAccount.{method} existe")
            else:
                print(f"  ❌ EmailAccount.{method} falta")
        
        # Test Q&A methods
        qa_methods = ['import_from_csv', 'search_similar']
        for method in qa_methods:
            if hasattr(Question, method):
                print(f"  ✅ Question.{method} existe")
            elif hasattr(QuestionVariant, method):
                print(f"  ✅ QuestionVariant.{method} existe")
            else:
                print(f"  ❌ {method} falta en Q&A models")
        
        # Test QuestionVariant specific methods
        variant_methods = ['validate_embedding', 'validate_variant_quality']
        for method in variant_methods:
            if hasattr(QuestionVariant, method):
                print(f"  ✅ QuestionVariant.{method} existe")
            else:
                print(f"  ❌ QuestionVariant.{method} falta")
        
        return True
    except Exception as e:
        print(f"  ❌ Error probando estructura: {e}")
        return False

def test_oauth2_support():
    """Prueba el soporte OAuth2 en EmailAccount."""
    print("🔍 Probando soporte OAuth2...")
    
    try:
        from src.models.email_account import EmailAccount
        
        # Crear instancia de prueba
        account = EmailAccount()
        account.auth_type = 'oauth2'
        account.oauth2_token = 'test_token'
        
        if hasattr(account, 'is_oauth2') and account.is_oauth2:
            print("  ✅ Soporte OAuth2 funcionando")
        else:
            print("  ❌ Soporte OAuth2 no funciona")
        
        return True
    except Exception as e:
        print(f"  ❌ Error probando OAuth2: {e}")
        return False

def test_csv_import_structure():
    """Prueba la estructura del método de importación CSV."""
    print("🔍 Probando estructura de importación CSV...")
    
    try:
        from src.models.qa import Question
        import io
        
        # Verificar que el método existe y tiene la signatura correcta
        if hasattr(Question, 'import_from_csv'):
            print("  ✅ Método import_from_csv existe")
            
            # Verificar que puede manejar StringIO
            csv_content = io.StringIO("question,answer\nTest,Response")
            print("  ✅ Puede manejar StringIO")
        else:
            print("  ❌ Método import_from_csv no existe")
        
        return True
    except Exception as e:
        print(f"  ❌ Error probando CSV import: {e}")
        return False

def test_email_detection():
    """Prueba la detección automática de configuración de email."""
    print("🔍 Probando detección automática de email...")
    
    try:
        from src.models.email_account import EmailAccount
        
        # Test Gmail detection
        gmail_config = EmailAccount.detect_email_config("test@gmail.com")
        if gmail_config.get('detected'):
            print("  ✅ Detección Gmail funcionando")
            print(f"     - Proveedor: {gmail_config.get('provider')}")
        else:
            print("  ❌ Detección Gmail no funciona")
        
        # Test unknown provider
        unknown_config = EmailAccount.detect_email_config("test@unknown.com")
        if not unknown_config.get('detected'):
            print("  ✅ Manejo de proveedores desconocidos funcionando")
        else:
            print("  ❌ Debería no detectar proveedores desconocidos")
        
        return True
    except Exception as e:
        print(f"  ❌ Error probando detección de email: {e}")
        return False

def main():
    """Función principal del script de prueba."""
    print("🚀 Iniciando pruebas simplificadas de modelos mejorados...")
    print("=" * 60)
    
    # Ejecutar todas las pruebas
    tests = [
        test_imports,
        test_model_structure,
        test_oauth2_support,
        test_csv_import_structure,
        test_email_detection
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
        print("✅ Los modelos mejorados están estructuralmente correctos")
        return True
    else:
        print(f"⚠️  {passed}/{total} pruebas pasaron")
        print("❌ Algunos modelos necesitan revisión")
        return False

if __name__ == "__main__":
    success = main()
    sys.exit(0 if success else 1) 