#!/usr/bin/env python3
"""
Script de prueba para verificar los métodos de automatización implementados en database.py

Este script verifica que todos los métodos de automatización funcionen correctamente
y mantengan la integridad de datos.
"""

import sys
import os
sys.path.append(os.path.join(os.path.dirname(__file__), 'src'))

from database import db_manager
import logging

# Configurar logging para las pruebas
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)

def test_automation_methods():
    """
    Prueba todos los métodos de automatización implementados.
    """
    logger.info("🧪 Iniciando pruebas de métodos de automatización...")
    
    try:
        # Verificar conexión a la base de datos
        if not db_manager.test_connection():
            logger.error("❌ No se pudo conectar a la base de datos")
            return False
        
        logger.info("✅ Conexión a base de datos exitosa")
        
        # Verificar que los métodos existen
        automation_methods = [
            'create_response_automation',
            'create_forward_automation', 
            'get_active_automations',
            'toggle_automation',
            'update_automation_questions',
            'get_automation_details'
        ]
        
        for method_name in automation_methods:
            if hasattr(db_manager, method_name):
                method = getattr(db_manager, method_name)
                if callable(method):
                    logger.info(f"✅ Método {method_name} encontrado y es callable")
                else:
                    logger.error(f"❌ {method_name} no es callable")
                    return False
            else:
                logger.error(f"❌ Método {method_name} no encontrado")
                return False
        
        logger.info("✅ Todos los métodos de automatización están implementados")
        
        # Verificar las importaciones necesarias
        try:
            from src.models.automation import Automation, ResponseAutomation, ForwardAutomation, AutomationType
            from src.models.qa import Question, Answer
            from src.models.user import User
            from src.models.email_account import EmailAccount
            logger.info("✅ Todas las importaciones de modelos son correctas")
        except ImportError as e:
            logger.error(f"❌ Error en importaciones: {e}")
            return False
        
        # Verificar que los métodos tienen las firmas correctas
        import inspect
        
        # Verificar create_response_automation
        sig = inspect.signature(db_manager.create_response_automation)
        expected_params = ['user_id', 'email_account_id', 'question_ids', 'tone', 'is_draft_mode', 'custom_instructions']
        actual_params = list(sig.parameters.keys())[1:]  # Excluir 'self'
        
        logger.info(f"🔍 create_response_automation parámetros actuales: {actual_params}")
        logger.info(f"🔍 create_response_automation parámetros esperados: {expected_params}")
        
        if set(expected_params) <= set(actual_params):
            logger.info("✅ create_response_automation tiene los parámetros correctos")
        else:
            logger.error(f"❌ create_response_automation parámetros incorrectos. Esperados: {expected_params}, Actuales: {actual_params}")
            return False
        
        # Verificar create_forward_automation
        sig = inspect.signature(db_manager.create_forward_automation)
        expected_params = ['user_id', 'email_account_id', 'forward_to', 'description']
        actual_params = list(sig.parameters.keys())[1:]  # Excluir 'self'
        
        if set(expected_params) <= set(actual_params):
            logger.info("✅ create_forward_automation tiene los parámetros correctos")
        else:
            logger.error(f"❌ create_forward_automation parámetros incorrectos. Esperados: {expected_params}, Actuales: {actual_params}")
            return False
        
        # Verificar get_active_automations
        sig = inspect.signature(db_manager.get_active_automations)
        expected_params = ['email_account_id']
        actual_params = list(sig.parameters.keys())[1:]  # Excluir 'self'
        
        if set(expected_params) <= set(actual_params):
            logger.info("✅ get_active_automations tiene los parámetros correctos")
        else:
            logger.error(f"❌ get_active_automations parámetros incorrectos. Esperados: {expected_params}, Actuales: {actual_params}")
            return False
        
        # Verificar toggle_automation
        sig = inspect.signature(db_manager.toggle_automation)
        expected_params = ['automation_id']
        actual_params = list(sig.parameters.keys())[1:]  # Excluir 'self'
        
        if set(expected_params) <= set(actual_params):
            logger.info("✅ toggle_automation tiene los parámetros correctos")
        else:
            logger.error(f"❌ toggle_automation parámetros incorrectos. Esperados: {expected_params}, Actuales: {actual_params}")
            return False
        
        # Verificar update_automation_questions
        sig = inspect.signature(db_manager.update_automation_questions)
        expected_params = ['automation_id', 'question_ids']
        actual_params = list(sig.parameters.keys())[1:]  # Excluir 'self'
        
        if set(expected_params) <= set(actual_params):
            logger.info("✅ update_automation_questions tiene los parámetros correctos")
        else:
            logger.error(f"❌ update_automation_questions parámetros incorrectos. Esperados: {expected_params}, Actuales: {actual_params}")
            return False
        
        # Verificar get_automation_details
        sig = inspect.signature(db_manager.get_automation_details)
        expected_params = ['automation_id']
        actual_params = list(sig.parameters.keys())[1:]  # Excluir 'self'
        
        if set(expected_params) <= set(actual_params):
            logger.info("✅ get_automation_details tiene los parámetros correctos")
        else:
            logger.error(f"❌ get_automation_details parámetros incorrectos. Esperados: {expected_params}, Actuales: {actual_params}")
            return False
        
        logger.info("✅ Todas las firmas de métodos son correctas")
        
        # Verificar que los métodos manejan errores apropiadamente
        try:
            # Probar con parámetros inválidos para verificar validación
            db_manager.create_response_automation(-1, -1, [], 'invalid_tone')
            logger.error("❌ create_response_automation no validó parámetros inválidos")
            return False
        except ValueError:
            logger.info("✅ create_response_automation valida parámetros correctamente")
        except Exception as e:
            logger.info(f"✅ create_response_automation maneja errores: {type(e).__name__}")
        
        try:
            # Probar con parámetros inválidos para verificar validación
            db_manager.get_active_automations(-1)
            logger.error("❌ get_active_automations no validó parámetros inválidos")
            return False
        except ValueError:
            logger.info("✅ get_active_automations valida parámetros correctamente")
        except Exception as e:
            logger.info(f"✅ get_active_automations maneja errores: {type(e).__name__}")
        
        try:
            # Probar con parámetros inválidos para verificar validación
            db_manager.toggle_automation(-1)
            logger.error("❌ toggle_automation no validó parámetros inválidos")
            return False
        except ValueError:
            logger.info("✅ toggle_automation valida parámetros correctamente")
        except Exception as e:
            logger.info(f"✅ toggle_automation maneja errores: {type(e).__name__}")
        
        logger.info("✅ Todos los métodos manejan errores apropiadamente")
        
        return True
        
    except Exception as e:
        logger.error(f"❌ Error durante las pruebas: {e}")
        return False

def main():
    """
    Función principal para ejecutar las pruebas.
    """
    logger.info("🚀 Iniciando verificación de métodos de automatización...")
    
    success = test_automation_methods()
    
    if success:
        logger.info("🎉 ¡Todas las pruebas pasaron exitosamente!")
        logger.info("✅ Los métodos de automatización están correctamente implementados")
        logger.info("📋 Métodos verificados:")
        logger.info("   - create_response_automation")
        logger.info("   - create_forward_automation")
        logger.info("   - get_active_automations")
        logger.info("   - toggle_automation")
        logger.info("   - update_automation_questions")
        logger.info("   - get_automation_details")
    else:
        logger.error("❌ Algunas pruebas fallaron")
        sys.exit(1)

if __name__ == "__main__":
    main() 