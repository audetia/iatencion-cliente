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

-- Users table
CREATE TABLE users (
    id SERIAL PRIMARY KEY,
    email VARCHAR(255) UNIQUE NOT NULL,
    name VARCHAR(255) NOT NULL,
    created_at TIMESTAMP WITH TIME ZONE DEFAULT CURRENT_TIMESTAMP,
    updated_at TIMESTAMP WITH TIME ZONE DEFAULT CURRENT_TIMESTAMP,
    is_verified BOOLEAN DEFAULT FALSE
);

-- Email accounts table
CREATE TABLE email_accounts (
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

-- Questions table
CREATE TABLE questions (
    id SERIAL PRIMARY KEY,
    user_id INTEGER NOT NULL REFERENCES users(id) ON DELETE CASCADE,
    original_question TEXT NOT NULL,
    created_at TIMESTAMP WITH TIME ZONE DEFAULT CURRENT_TIMESTAMP
);

-- Question variants table (with pgvector embeddings)
CREATE TABLE question_variants (
    id SERIAL PRIMARY KEY,
    question_id INTEGER NOT NULL REFERENCES questions(id) ON DELETE CASCADE,
    variant_text TEXT NOT NULL,
    embedding VECTOR(1536) NOT NULL,
    created_at TIMESTAMP WITH TIME ZONE DEFAULT CURRENT_TIMESTAMP
);

-- Answers table
CREATE TABLE answers (
    id SERIAL PRIMARY KEY,
    question_id INTEGER NOT NULL REFERENCES questions(id) ON DELETE CASCADE,
    answer_text TEXT NOT NULL,
    response_instructions VARCHAR(255),
    created_at TIMESTAMP WITH TIME ZONE DEFAULT CURRENT_TIMESTAMP,
    updated_at TIMESTAMP WITH TIME ZONE DEFAULT CURRENT_TIMESTAMP
);

-- =============================================
-- AUTOMATION TABLES
-- =============================================

-- Automations table
CREATE TABLE automations (
    id SERIAL PRIMARY KEY,
    user_id INTEGER NOT NULL REFERENCES users(id) ON DELETE CASCADE,
    email_account_id INTEGER NOT NULL REFERENCES email_accounts(id) ON DELETE CASCADE,
    type automation_type NOT NULL,
    is_active BOOLEAN DEFAULT TRUE,
    is_draft_mode BOOLEAN DEFAULT FALSE,
    created_at TIMESTAMP WITH TIME ZONE DEFAULT CURRENT_TIMESTAMP,
    updated_at TIMESTAMP WITH TIME ZONE DEFAULT CURRENT_TIMESTAMP
);

-- Response automations table
CREATE TABLE response_automations (
    id SERIAL PRIMARY KEY,
    automation_id INTEGER NOT NULL REFERENCES automations(id) ON DELETE CASCADE UNIQUE,
    response_instructions VARCHAR(255),
    custom_instructions TEXT
);

-- Forward automations table
CREATE TABLE forward_automations (
    id SERIAL PRIMARY KEY,
    automation_id INTEGER NOT NULL REFERENCES automations(id) ON DELETE CASCADE UNIQUE,
    forward_to_email VARCHAR(255) NOT NULL,
    description VARCHAR(255)
);

-- Automation questions junction table
CREATE TABLE automation_questions (
    automation_id INTEGER NOT NULL REFERENCES automations(id) ON DELETE CASCADE,
    question_id INTEGER NOT NULL REFERENCES questions(id) ON DELETE CASCADE,
    PRIMARY KEY (automation_id, question_id)
);

-- =============================================
-- USAGE TRACKING TABLES
-- =============================================

-- Email processed table
CREATE TABLE email_processed (
    id SERIAL PRIMARY KEY,
    email_account_id INTEGER NOT NULL REFERENCES email_accounts(id) ON DELETE CASCADE,
    user_id INTEGER NOT NULL REFERENCES users(id) ON DELETE CASCADE,
    processed_at TIMESTAMP WITH TIME ZONE DEFAULT CURRENT_TIMESTAMP,
    email_responded BOOLEAN DEFAULT FALSE,
    answer TEXT,
    email_forwarded BOOLEAN DEFAULT FALSE,
    forwarded_to VARCHAR(255),
    category VARCHAR(100),
    tokens_used INTEGER DEFAULT 0
);

-- User usage monthly aggregation table
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

-- Tiers table
CREATE TABLE tiers (
    id SERIAL PRIMARY KEY,
    name VARCHAR(100) UNIQUE NOT NULL,
    cost_cents INTEGER NOT NULL DEFAULT 0,
    email_process_limit INTEGER NOT NULL DEFAULT 0,
    email_action_limit INTEGER NOT NULL DEFAULT 0,
    tokens_limit INTEGER NOT NULL DEFAULT 0
);

-- Subscriptions table
CREATE TABLE subscriptions (
    id SERIAL PRIMARY KEY,
    user_id INTEGER NOT NULL REFERENCES users(id) ON DELETE CASCADE,
    tier_id INTEGER NOT NULL REFERENCES tiers(id),
    stripe_subscription_id VARCHAR(255) UNIQUE,
    start_date TIMESTAMP WITH TIME ZONE NOT NULL,
    end_date TIMESTAMP WITH TIME ZONE,
    is_active BOOLEAN DEFAULT TRUE
);

-- =============================================
-- INDEXES FOR PERFORMANCE
-- =============================================

-- Users indexes
CREATE INDEX idx_users_email ON users(email);
CREATE INDEX idx_users_created_at ON users(created_at);

-- Email accounts indexes
CREATE INDEX idx_email_accounts_user_id ON email_accounts(user_id);
CREATE INDEX idx_email_accounts_email ON email_accounts(email);
CREATE INDEX idx_email_accounts_is_active ON email_accounts(is_active);

-- Questions indexes
CREATE INDEX idx_questions_user_id ON questions(user_id);
CREATE INDEX idx_questions_created_at ON questions(created_at);

-- Question variants indexes
CREATE INDEX idx_question_variants_question_id ON question_variants(question_id);
-- Vector similarity search index (HNSW for better performance with embeddings)
CREATE INDEX idx_question_variants_embedding ON question_variants USING hnsw (embedding vector_cosine_ops);

-- Answers indexes
CREATE INDEX idx_answers_question_id ON answers(question_id);
CREATE INDEX idx_answers_response_instructions ON answers(response_instructions);

-- Automations indexes
CREATE INDEX idx_automations_user_id ON automations(user_id);
CREATE INDEX idx_automations_email_account_id ON automations(email_account_id);
CREATE INDEX idx_automations_type ON automations(type);
CREATE INDEX idx_automations_is_active ON automations(is_active);

-- Email processed indexes
CREATE INDEX idx_email_processed_user_id ON email_processed(user_id);
CREATE INDEX idx_email_processed_email_account_id ON email_processed(email_account_id);
CREATE INDEX idx_email_processed_processed_at ON email_processed(processed_at);
CREATE INDEX idx_email_processed_user_processed_at ON email_processed(user_id, processed_at);

-- User usage monthly indexes
CREATE INDEX idx_user_usage_monthly_user_year_month ON user_usage_monthly(user_id, year, month);

-- Subscriptions indexes
CREATE INDEX idx_subscriptions_user_id ON subscriptions(user_id);
CREATE INDEX idx_subscriptions_tier_id ON subscriptions(tier_id);
CREATE INDEX idx_subscriptions_is_active ON subscriptions(is_active);
CREATE INDEX idx_subscriptions_stripe_id ON subscriptions(stripe_subscription_id);

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
INSERT INTO tiers (name, cost_cents, email_process_limit, email_action_limit, tokens_limit) VALUES
    ('Free', 0, 50, 25, 10000),
    ('Low volume', 999, 400, 200, 200000),
    ('Medium volume', 2999, 2000, 1000, 1000000),
    ('High volume', 29999, 10000, 5000, 5000000);

-- =============================================
-- COMMENTS FOR DOCUMENTATION
-- =============================================

COMMENT ON TABLE users IS 'User accounts in the system';
COMMENT ON TABLE email_accounts IS 'Email accounts configured by users for automation';
COMMENT ON TABLE questions IS 'Original questions created by users';
COMMENT ON TABLE question_variants IS 'Different variants of questions with embeddings for similarity search';
COMMENT ON TABLE answers IS 'Answers associated with questions';
COMMENT ON TABLE automations IS 'Automation configurations for email processing';
COMMENT ON TABLE response_automations IS 'Configuration for response-type automations';
COMMENT ON TABLE forward_automations IS 'Configuration for forward-type automations';
COMMENT ON TABLE automation_questions IS 'Junction table linking automations to questions';
COMMENT ON TABLE email_processed IS 'Log of processed emails with actions taken';
COMMENT ON TABLE user_usage_monthly IS 'Monthly usage aggregation for billing and limits';
COMMENT ON TABLE tiers IS 'Subscription tiers with limits and pricing';
COMMENT ON TABLE subscriptions IS 'User subscriptions to tiers';

COMMENT ON COLUMN question_variants.embedding IS 'Vector embedding (1536 dimensions) for similarity search using pgvector';
COMMENT ON COLUMN automations.type IS 'Type of automation: response or forward';
COMMENT ON COLUMN email_processed.tokens_used IS 'Number of AI tokens consumed for processing this email';

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
        'users', 'email_accounts', 'questions', 'question_variants', 
        'answers', 'automations', 'response_automations', 
        'forward_automations', 'automation_questions', 'email_processed', 
        'user_usage_monthly', 'tiers', 'subscriptions'
    );
    
    IF table_count = 13 THEN
        RAISE NOTICE 'Schema initialization completed successfully. All % tables created.', table_count;
    ELSE
        RAISE EXCEPTION 'Schema initialization failed. Expected 13 tables, found %', table_count;
    END IF;
END $$;
