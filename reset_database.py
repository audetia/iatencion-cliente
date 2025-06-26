#!/usr/bin/env python3
"""
Database Reset Script
Drops all tables from the database to allow for a clean migration.
Use with caution - this will delete ALL data!
"""

import os
import sys
import logging
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

def confirm_reset():
    """
    Ask for user confirmation before proceeding with database reset.
    """
    print("⚠️  WARNING: This will DELETE ALL TABLES and DATA from the database!")
    print("This action cannot be undone.")
    print()
    
    response = input("Are you sure you want to proceed? Type 'YES' to confirm: ")
    
    if response != 'YES':
        print("❌ Database reset cancelled.")
        sys.exit(0)
    
    print("✅ Confirmation received. Proceeding with database reset...")

def reset_database():
    """Drop all tables from the database."""
    
    # Get database URL from environment
    postgres_url = os.getenv('POSTGRES_URL')
    if not postgres_url:
        logger.error("POSTGRES_URL environment variable not found!")
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
        
        with conn.cursor() as cursor:
            # First, get all table names
            cursor.execute("""
                SELECT tablename 
                FROM pg_tables 
                WHERE schemaname = 'public'
            """)
            tables = cursor.fetchall()
            
            if not tables:
                logger.info("No tables found in the database.")
                return
            
            table_names = [table[0] for table in tables]
            logger.info(f"Found {len(table_names)} tables to drop: {', '.join(table_names)}")
            
            # Drop all tables with CASCADE to handle foreign key constraints
            for table_name in table_names:
                try:
                    cursor.execute(f"DROP TABLE IF EXISTS {table_name} CASCADE")
                    logger.info(f"✅ Dropped table: {table_name}")
                except Exception as e:
                    logger.error(f"❌ Error dropping table {table_name}: {str(e)}")
                    raise
            
            # Also drop any sequences that might be left behind
            cursor.execute("""
                SELECT sequence_name 
                FROM information_schema.sequences 
                WHERE sequence_schema = 'public'
            """)
            sequences = cursor.fetchall()
            
            for seq in sequences:
                seq_name = seq[0]
                try:
                    cursor.execute(f"DROP SEQUENCE IF EXISTS {seq_name} CASCADE")
                    logger.info(f"✅ Dropped sequence: {seq_name}")
                except Exception as e:
                    logger.warning(f"⚠️  Could not drop sequence {seq_name}: {str(e)}")
            
            # Drop any custom types/enums that might exist
            cursor.execute("""
                SELECT typname 
                FROM pg_type 
                WHERE typnamespace = (SELECT oid FROM pg_namespace WHERE nspname = 'public')
                AND typtype = 'e'
            """)
            enums = cursor.fetchall()
            
            for enum in enums:
                enum_name = enum[0]
                try:
                    cursor.execute(f"DROP TYPE IF EXISTS {enum_name} CASCADE")
                    logger.info(f"✅ Dropped enum type: {enum_name}")
                except Exception as e:
                    logger.warning(f"⚠️  Could not drop enum {enum_name}: {str(e)}")
        
        # Verify the reset
        with conn.cursor() as cursor:
            cursor.execute("""
                SELECT COUNT(*) 
                FROM information_schema.tables 
                WHERE table_schema = 'public' 
                AND table_type = 'BASE TABLE'
            """)
            remaining_tables = cursor.fetchone()[0]
            
            if remaining_tables == 0:
                logger.info("✅ Database reset completed successfully!")
                logger.info("All tables, sequences, and custom types have been removed.")
            else:
                logger.warning(f"⚠️  {remaining_tables} tables still remain in the database.")
        
        conn.close()
        logger.info("Database connection closed.")
        
    except ImportError:
        logger.error("psycopg2 not installed. Please install it with: pip install psycopg2-binary")
        sys.exit(1)
    except Exception as e:
        logger.error(f"Database reset failed: {str(e)}")
        sys.exit(1)

if __name__ == "__main__":
    print("🗑️  Database Reset Script")
    print("=" * 50)
    
    # Ask for confirmation
    confirm_reset()
    
    # Proceed with reset
    reset_database()
    
    print("=" * 50)
    print("✅ Database reset completed!")
    print("You can now run 'python run_migration.py' to create the schema from scratch.") 