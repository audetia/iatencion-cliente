-- PostgreSQL Database Schema Initialization Script
-- Project: automateyourinbox.com
-- Version: 1.0
-- Description: Complete schema for AI-powered customer support automation

-- Enable pgvector extension for embeddings
CREATE EXTENSION IF NOT EXISTS vector;

-- Create ENUM types
CREATE TYPE automation_type AS ENUM ('response', 'forward');

-- =============================================
-- CORE TABLES
-- =============================================

-- Users table (plural to avoid PostgreSQL reserved word)
CREATE TABLE users (
    id SERIAL PRIMARY KEY,
    email VARCHAR(255) UNIQUE NOT NULL,
    name VARCHAR(255) NOT NULL,
    created_at TIMESTAMP WITH TIME ZONE DEFAULT CURRENT_TIMESTAMP,
    updated_at TIMESTAMP WITH TIME ZONE DEFAULT CURRENT_TIMESTAMP,
    is_verified BOOLEAN DEFAULT FALSE
);

-- Email account table (singular)
CREATE TABLE email_account (
    id SERIAL PRIMARY KEY,
    user_id INTEGER NOT NULL REFERENCES users(id) ON DELETE CASCADE,
    email VARCHAR(255) NOT NULL,
    imap_server VARCHAR(255) NOT NULL,
    imap_port INTEGER NOT NULL DEFAULT 993,
    smtp_server VARCHAR(255) NOT NULL,
    smtp_port INTEGER NOT NULL DEFAULT 587,
    encrypted_password TEXT NOT NULL,
    is_active BOOLEAN DEFAULT TRUE,
    created_at TIMESTAMP WITH TIME ZONE DEFAULT CURRENT_TIMESTAMP,
    updated_at TIMESTAMP WITH TIME ZONE DEFAULT CURRENT_TIMESTAMP,
    UNIQUE(user_id, email)
);

-- Question table (singular)
CREATE TABLE question (
    id SERIAL PRIMARY KEY,
    user_id INTEGER NOT NULL REFERENCES users(id) ON DELETE CASCADE,
    original_question TEXT NOT NULL,
    created_at TIMESTAMP WITH TIME ZONE DEFAULT CURRENT_TIMESTAMP
);

-- Question variant table (singular, with pgvector embeddings)
CREATE TABLE question_variant (
    id SERIAL PRIMARY KEY,
    question_id INTEGER NOT NULL REFERENCES question(id) ON DELETE CASCADE,
    variant_text TEXT NOT NULL,
    embedding VECTOR(1536) NOT NULL,
    created_at TIMESTAMP WITH TIME ZONE DEFAULT CURRENT_TIMESTAMP
);

-- Answer table (singular)
CREATE TABLE answer (
    id SERIAL PRIMARY KEY,
    question_id INTEGER NOT NULL REFERENCES question(id) ON DELETE CASCADE,
    answer_text TEXT NOT NULL,
    response_instructions VARCHAR(255),
    created_at TIMESTAMP WITH TIME ZONE DEFAULT CURRENT_TIMESTAMP,
    updated_at TIMESTAMP WITH TIME ZONE DEFAULT CURRENT_TIMESTAMP
);

-- =============================================
-- AUTOMATION TABLES
-- =============================================

-- Automation table (singular, removed user_id redundancy)
CREATE TABLE automation (
    id SERIAL PRIMARY KEY,
    email_account_id INTEGER NOT NULL REFERENCES email_account(id) ON DELETE CASCADE,
    type automation_type NOT NULL,
    is_active BOOLEAN DEFAULT TRUE,
    is_draft_mode BOOLEAN DEFAULT FALSE,
    created_at TIMESTAMP WITH TIME ZONE DEFAULT CURRENT_TIMESTAMP,
    updated_at TIMESTAMP WITH TIME ZONE DEFAULT CURRENT_TIMESTAMP
);

-- Response automation table (singular)
CREATE TABLE response_automation (
    id SERIAL PRIMARY KEY,
    automation_id INTEGER NOT NULL REFERENCES automation(id) ON DELETE CASCADE UNIQUE,
    question_id INTEGER NOT NULL REFERENCES question(id) ON DELETE RESTRICT,
    tone VARCHAR(50) DEFAULT 'professional',
    custom_instructions TEXT,
    UNIQUE(question_id)  -- Asegura que una pregunta solo puede estar en una automatización
);

-- Forward automation table (singular)
CREATE TABLE forward_automation (
    id SERIAL PRIMARY KEY,
    automation_id INTEGER NOT NULL REFERENCES automation(id) ON DELETE CASCADE UNIQUE,
    forward_to_email VARCHAR(255) NOT NULL,
    description VARCHAR(255)
);

-- =============================================
-- USAGE TRACKING TABLES
-- =============================================

-- Email processed table (singular, removed user_id redundancy)
CREATE TABLE email_processed (
    id SERIAL PRIMARY KEY,
    email_account_id INTEGER NOT NULL REFERENCES email_account(id) ON DELETE CASCADE,
    processed_at TIMESTAMP WITH TIME ZONE DEFAULT CURRENT_TIMESTAMP,
    email_responded BOOLEAN DEFAULT FALSE,
    answer TEXT,
    email_forwarded BOOLEAN DEFAULT FALSE,
    forwarded_to VARCHAR(255),
    category VARCHAR(100),
    tokens_used INTEGER DEFAULT 0
);

-- User usage monthly aggregation table (singular)
CREATE TABLE user_usage_monthly (
    id SERIAL PRIMARY KEY,
    user_id INTEGER NOT NULL REFERENCES users(id) ON DELETE CASCADE,
    year INTEGER NOT NULL,
    month INTEGER NOT NULL CHECK (month >= 1 AND month <= 12),
    emails_processed INTEGER DEFAULT 0,
    emails_responded INTEGER DEFAULT 0,
    emails_forwarded INTEGER DEFAULT 0,
    tokens_used INTEGER DEFAULT 0,
    last_updated TIMESTAMP WITH TIME ZONE DEFAULT CURRENT_TIMESTAMP,
    UNIQUE(user_id, year, month)
);

-- =============================================
-- SUBSCRIPTION TABLES
-- =============================================

-- Tier table (singular)
CREATE TABLE tier (
    id SERIAL PRIMARY KEY,
    name VARCHAR(100) UNIQUE NOT NULL,
    cost_cents INTEGER NOT NULL DEFAULT 0,
    email_process_limit INTEGER NOT NULL DEFAULT 0,
    email_action_limit INTEGER NOT NULL DEFAULT 0,
    tokens_limit INTEGER NOT NULL DEFAULT 0
);

-- Subscription table (singular)
CREATE TABLE subscription (
    id SERIAL PRIMARY KEY,
    user_id INTEGER NOT NULL REFERENCES users(id) ON DELETE CASCADE,
    tier_id INTEGER NOT NULL REFERENCES tier(id),
    stripe_subscription_id VARCHAR(255) UNIQUE,
    start_date TIMESTAMP WITH TIME ZONE NOT NULL,
    end_date TIMESTAMP WITH TIME ZONE,
    is_active BOOLEAN DEFAULT TRUE
);

-- =============================================
-- INDEXES FOR PERFORMANCE (OPTIMIZED FOR MVP)
-- =============================================

-- Users indexes (essential only)
CREATE INDEX idx_users_email ON users(email);

-- Email account indexes (essential only)
CREATE INDEX idx_email_account_user_id ON email_account(user_id);
CREATE INDEX idx_email_account_is_active ON email_account(is_active);

-- Question indexes (essential only)
CREATE INDEX idx_question_user_id ON question(user_id);

-- Question variant indexes (essential for vector search)
CREATE INDEX idx_question_variant_question_id ON question_variant(question_id);
-- Vector similarity search index (HNSW for better performance with embeddings)
CREATE INDEX idx_question_variant_embedding ON question_variant USING hnsw (embedding vector_cosine_ops);

-- Answer indexes (essential only)
CREATE INDEX idx_answer_question_id ON answer(question_id);

-- Response automation indexes (essential only)
CREATE INDEX idx_response_automation_automation_id ON response_automation(automation_id);
CREATE INDEX idx_response_automation_question_id ON response_automation(question_id);

-- Forward automation indexes (essential only)
CREATE INDEX idx_forward_automation_automation_id ON forward_automation(automation_id);

-- Automation indexes (updated, removed user_id)
CREATE INDEX idx_automation_email_account_id ON automation(email_account_id);
CREATE INDEX idx_automation_is_active ON automation(is_active);

-- Email processed indexes (essential only, removed user_id)
CREATE INDEX idx_email_processed_email_account_id ON email_processed(email_account_id);
CREATE INDEX idx_email_processed_processed_at ON email_processed(processed_at);

-- User usage monthly indexes (essential only)
CREATE INDEX idx_user_usage_monthly_user_year_month ON user_usage_monthly(user_id, year, month);

-- Subscription indexes (essential only)
CREATE INDEX idx_subscription_user_id ON subscription(user_id);
CREATE INDEX idx_subscription_is_active ON subscription(is_active);

-- =============================================
-- BUSINESS LOGIC MOVED TO APPLICATION LAYER
-- =============================================

-- Note: Usage tracking and timestamp updates are handled in the application layer
-- for better observability, testing, and scalability. See services/usage_service.py
-- and the respective model update methods for implementation details.

-- =============================================
-- INITIAL DATA (DEFAULT TIERS)
-- =============================================

-- Insert default tiers
INSERT INTO tier (name, cost_cents, email_process_limit, email_action_limit, tokens_limit) VALUES
    ('Free', 0, 50, 25, 10000),
    ('Low volume', 999, 400, 200, 200000),
    ('Medium volume', 2999, 2000, 1000, 1000000),
    ('High volume', 29999, 10000, 5000, 5000000);

-- =============================================
-- COMMENTS FOR DOCUMENTATION
-- =============================================

COMMENT ON TABLE users IS 'User accounts in the system';
COMMENT ON TABLE email_account IS 'Email accounts configured by users for automation';
COMMENT ON TABLE question IS 'Original questions created by users';
COMMENT ON TABLE question_variant IS 'Different variants of questions with embeddings for similarity search';
COMMENT ON TABLE answer IS 'Answers associated with questions';
COMMENT ON TABLE automation IS 'Automation configurations for email processing (user_id removed - get via email_account)';
COMMENT ON TABLE response_automation IS 'Configuration for response-type automations (each has one question)';
COMMENT ON TABLE forward_automation IS 'Configuration for forward-type automations (uses description, not questions)';
COMMENT ON TABLE email_processed IS 'Log of processed emails with actions taken (user_id removed - get via email_account)';
COMMENT ON TABLE user_usage_monthly IS 'Monthly usage aggregation for billing and limits';
COMMENT ON TABLE tier IS 'Subscription tiers with limits and pricing';
COMMENT ON TABLE subscription IS 'User subscriptions to tiers';

COMMENT ON COLUMN question_variant.embedding IS 'Vector embedding (1536 dimensions) for similarity search using pgvector';
COMMENT ON COLUMN automation.type IS 'Type of automation: response or forward';
COMMENT ON COLUMN automation.is_draft_mode IS 'Draft mode saves emails to drafts folder instead of sending';
COMMENT ON COLUMN response_automation.tone IS 'Response tone: professional, casual, or friendly';
COMMENT ON COLUMN forward_automation.description IS 'Criteria description for when to forward emails';
COMMENT ON COLUMN email_processed.tokens_used IS 'Number of AI tokens consumed for processing this email';
COMMENT ON COLUMN email_processed.processed_at IS 'Timestamp when the email was processed (serves as creation time)';
COMMENT ON COLUMN user_usage_monthly.last_updated IS 'Timestamp when the usage record was last updated';

-- =============================================
-- SCHEMA VALIDATION
-- =============================================

-- Verify all tables were created successfully
DO $$
DECLARE
    table_count INTEGER;
BEGIN
    SELECT COUNT(*) INTO table_count 
    FROM information_schema.tables 
    WHERE table_schema = 'public' 
    AND table_type = 'BASE TABLE'
    AND table_name IN (
        'users', 'email_account', 'question', 'question_variant', 
        'answer', 'automation', 'response_automation', 
        'forward_automation', 'email_processed', 
        'user_usage_monthly', 'tier', 'subscription'
    );
    
    IF table_count = 12 THEN
        RAISE NOTICE 'Schema initialization completed successfully. All % tables created.', table_count;
    ELSE
        RAISE EXCEPTION 'Schema initialization failed. Expected 12 tables, found %', table_count;
    END IF;
END $$;
