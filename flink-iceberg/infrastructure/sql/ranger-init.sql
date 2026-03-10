-- Ranger Admin Database Setup
-- IMPORTANT: Run this script as a MySQL user with CREATE USER privileges (e.g., root)
-- For production: Replace password with environment variable and restrict host access
CREATE DATABASE IF NOT EXISTS ranger_db DEFAULT CHARACTER SET utf8mb4 COLLATE utf8mb4_general_ci;
CREATE USER IF NOT EXISTS 'ranger'@'%' IDENTIFIED BY 'ranger123';
GRANT ALL PRIVILEGES ON ranger_db.* TO 'ranger'@'%';
FLUSH PRIVILEGES;

-- Use Ranger database
USE ranger_db;

-- Create base tables (Ranger will create remaining tables on first startup)
-- This ensures the database exists and is properly configured
SELECT 'Ranger database initialized' AS status;
