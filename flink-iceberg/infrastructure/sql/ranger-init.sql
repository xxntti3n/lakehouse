-- Apache Ranger Database Initialization for MySQL
-- Creates the ranger_db database and necessary schema

CREATE DATABASE IF NOT EXISTS ranger_db CHARACTER SET utf8mb4 COLLATE utf8mb4_unicode_ci;
USE ranger_db;

-- Ranger will create its own tables on first run via setup.sh
-- This file ensures the database exists
