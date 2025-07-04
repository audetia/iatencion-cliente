#!/usr/bin/env python3
"""
Database Migration Runner
Executes the initial schema migration for the AI Email Automation system.
"""

import os
import sys
import logging
import re
from pathlib import Path
from dotenv import load_dotenv

# Load environment variables
load_dotenv()

# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)

def split_sql_statements(sql_content):
    """
    Properly split SQL statements, handling semicolons within blocks.
    """
    statements = []
    current_statement = ""
    in_block = False
    block_depth = 0
    
    lines = sql_content.split('\n')
    
    for line in lines:
        stripped_line = line.strip()
        
        # Skip comments and empty lines
        if stripped_line.startswith('--') or not stripped_line:
            continue
            
        # Check for block start/end
        if 'DO $$' in stripped_line:
            in_block = True
            block_depth = 1
        elif '$$;' in stripped_line and in_block:
            block_depth -= 1
            if block_depth == 0:
                in_block = False
                current_statement += line + '\n'
                if current_statement.strip():
                    statements.append(current_statement.strip())
                current_statement = ""
                continue
        
        current_statement += line + '\n'
        
        # If we're not in a block and see a semicolon, end the statement
        if not in_block and stripped_line.endswith(';'):
            if current_statement.strip():
                statements.append(current_statement.strip())
            current_statement = ""
    
    # Add any remaining statement
    if current_statement.strip():
        statements.append(current_statement.strip())
    
    return statements

def run_migration():
    """Execute the database migration."""
    
    # Get database URL from environment
    postgres_url = os.getenv('POSTGRES_URL')
    if not postgres_url:
        logger.error("POSTGRES_URL environment variable not found!")
        sys.exit(1)
    
    # Define migration files in order
    migration_files = [
        "migrations/001_initial_schema.sql",
        "migrations/002_qa_tracking.sql"
    ]
    
    # Check all migration files exist
    for migration_file in migration_files:
        if not Path(migration_file).exists():
            logger.error(f"Migration file not found: {migration_file}")
            sys.exit(1)
    
    try:
        # Import psycopg2 for database connection
        import psycopg2
        from psycopg2.extensions import ISOLATION_LEVEL_AUTOCOMMIT
        
        logger.info("Connecting to PostgreSQL database...")
        
        # Connect using the URL directly
        conn = psycopg2.connect(postgres_url)
        conn.set_isolation_level(ISOLATION_LEVEL_AUTOCOMMIT)
        
        logger.info("✅ Successfully connected to PostgreSQL database")
        
        # Execute each migration file
        total_statements = 0
        for migration_file in migration_files:
            logger.info(f"🔄 Executing migration: {migration_file}")
            
            # Read the migration file
            with open(migration_file, 'r', encoding='utf-8') as f:
                migration_sql = f.read()
            
            # Split into proper statements
            statements = split_sql_statements(migration_sql)
            
            logger.info(f"Found {len(statements)} SQL statements in {migration_file}")
            total_statements += len(statements)
            
            # Execute each statement
            with conn.cursor() as cursor:
                for i, statement in enumerate(statements, 1):
                    statement = statement.strip()
                    if not statement:
                        continue
                        
                    try:
                        logger.debug(f"Executing statement {i}: {statement[:50]}...")
                        cursor.execute(statement)
                        logger.debug(f"✅ Statement {i} executed successfully")
                    except Exception as e:
                        # Handle specific cases
                        if "already exists" in str(e).lower():
                            logger.warning(f"⚠️  Statement {i} skipped (already exists): {str(e)}")
                        elif "does not exist" in str(e).lower():
                            logger.warning(f"⚠️  Statement {i} skipped (does not exist): {str(e)}")
                        else:
                            logger.error(f"❌ Error executing statement {i}: {str(e)}")
                            logger.error(f"Statement: {statement}")
                            raise
            
            logger.info(f"✅ Migration {migration_file} completed successfully!")
        
        logger.info(f"✅ All migrations completed successfully! Total statements: {total_statements}")
        logger.info("Database schema initialized with all tables, indexes, and initial data.")
        
        # Verify the migration
        with conn.cursor() as cursor:
            cursor.execute("""
                SELECT COUNT(*) 
                FROM information_schema.tables 
                WHERE table_schema = 'public' 
                AND table_type = 'BASE TABLE'
            """)
            table_count = cursor.fetchone()[0]
            logger.info(f"Total tables created: {table_count}")
            
            # Check for specific tables
            expected_tables = [
                'users', 'email_account', 'question', 'question_variant', 
                'answer', 'automation', 'response_automation', 
                'forward_automation', 'email_processed', 
                'user_usage_monthly', 'tier', 'subscription'
            ]
            
            for table in expected_tables:
                cursor.execute(f"SELECT EXISTS (SELECT FROM information_schema.tables WHERE table_name = '{table}')")
                exists = cursor.fetchone()[0]
                status = "✅" if exists else "❌"
                logger.info(f"{status} Table '{table}': {'exists' if exists else 'missing'}")
        
        conn.close()
        logger.info("Database connection closed.")
        
    except ImportError:
        logger.error("psycopg2 not installed. Please install it with: pip install psycopg2-binary")
        sys.exit(1)
    except Exception as e:
        logger.error(f"Migration failed: {str(e)}")
        sys.exit(1)

if __name__ == "__main__":
    print("🚀 Starting Database Migration...")
    print("=" * 50)
    run_migration()
    print("=" * 50)
    print("✅ Migration completed successfully!") 