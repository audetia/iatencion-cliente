# src/__init__.py
"""
Email Automation System

Sistema de automatización de emails para agencias de IA.
"""

# Import general de módulos - acceso via src.database.db_manager, etc.
from . import database
from . import agents
from . import nodes
from . import graph
from . import state

# Version info
__version__ = "1.0.0"
__author__ = "automateyourinbox.com Team"