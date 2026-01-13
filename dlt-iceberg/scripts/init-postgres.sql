-- Initialize PostgreSQL for replication
-- This script is used by docker-compose for local development

-- Create replication user
CREATE ROLE replication_user WITH LOGIN REPLICATION PASSWORD 'replication123';

-- Grant permissions
GRANT CREATE ON DATABASE dlt_data TO replication_user;
GRANT CONNECT ON DATABASE dlt_data TO replication_user;
\c dlt_data
GRANT USAGE ON SCHEMA public TO replication_user;

-- Create sample tables
CREATE TABLE IF NOT EXISTS users (
    id SERIAL PRIMARY KEY,
    username VARCHAR(255) NOT NULL,
    email VARCHAR(255) NOT NULL,
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);

CREATE TABLE IF NOT EXISTS orders (
    id SERIAL PRIMARY KEY,
    user_id INTEGER REFERENCES users(id),
    amount DECIMAL(10, 2),
    status VARCHAR(50),
    order_date DATE DEFAULT CURRENT_DATE
);

-- Insert sample data
INSERT INTO users (username, email) VALUES
    ('john_doe', 'john@example.com'),
    ('jane_smith', 'jane@example.com'),
    ('bob_wilson', 'bob@example.com')
ON CONFLICT DO NOTHING;

INSERT INTO orders (user_id, amount, status) VALUES
    (1, 100.50, 'completed'),
    (2, 250.00, 'pending'),
    (3, 75.25, 'shipped')
ON CONFLICT DO NOTHING;

-- Grant permissions on tables
GRANT SELECT ON ALL TABLES IN SCHEMA public TO replication_user;
ALTER DEFAULT PRIVILEGES IN SCHEMA public GRANT SELECT ON TABLES TO replication_user;

-- Create publication (will be created by DLT init_replication)
-- This is here for reference
-- CREATE PUBLICATION dlt_publication FOR TABLE users, orders;
