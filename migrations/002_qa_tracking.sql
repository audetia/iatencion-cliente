-- Migration 002: Add Q&A tracking to email_processed table
-- Adds fields to track which Q&A pairs are used in email responses

-- Add columns to track Q&A usage
ALTER TABLE email_processed 
ADD COLUMN question_id INTEGER REFERENCES questions(id) ON DELETE SET NULL,
ADD COLUMN similarity_score FLOAT CHECK (similarity_score >= 0.0 AND similarity_score <= 1.0);

-- Add index for Q&A usage queries
CREATE INDEX idx_email_processed_question_id ON email_processed(question_id);
CREATE INDEX idx_email_processed_similarity ON email_processed(similarity_score DESC);

-- Add composite index for Q&A analytics
CREATE INDEX idx_email_processed_qa_analytics ON email_processed(question_id, processed_at) WHERE question_id IS NOT NULL;

-- Add comment for documentation
COMMENT ON COLUMN email_processed.question_id IS 'ID of the Q&A question used to generate the response (if any)';
COMMENT ON COLUMN email_processed.similarity_score IS 'Similarity score (0.0-1.0) between query and matched Q&A variant'; 