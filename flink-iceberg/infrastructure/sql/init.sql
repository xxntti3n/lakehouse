-- Initialize database and tables for CDC pipeline

CREATE DATABASE IF NOT EXISTS appdb;
USE appdb;

-- Products table (dimension table)
CREATE TABLE IF NOT EXISTS products (
    id INT AUTO_INCREMENT PRIMARY KEY,
    sku VARCHAR(50) NOT NULL UNIQUE,
    name VARCHAR(255) NOT NULL,
    price DECIMAL(10, 2) NOT NULL,
    category VARCHAR(100),
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP ON UPDATE CURRENT_TIMESTAMP
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4;

-- Sales table (fact table)
CREATE TABLE IF NOT EXISTS sales (
    id INT AUTO_INCREMENT PRIMARY KEY,
    product_id INT NOT NULL,
    qty INT NOT NULL,
    price DECIMAL(10, 2) NOT NULL,
    sale_ts TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    FOREIGN KEY (product_id) REFERENCES products(id) ON DELETE CASCADE
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4;

-- Insert sample products
INSERT INTO products (sku, name, price, category) VALUES
('PROD-001', 'Laptop Stand', 49.99, 'Electronics'),
('PROD-002', 'Wireless Mouse', 29.99, 'Electronics'),
('PROD-003', 'Mechanical Keyboard', 99.99, 'Electronics'),
('PROD-004', 'USB-C Hub', 19.99, 'Electronics'),
('PROD-005', 'Monitor Light Bar', 39.99, 'Electronics'),
('PROD-006', 'Webcam HD', 79.99, 'Electronics'),
('PROD-007', 'Noise-Canceling Headphones', 149.99, 'Electronics'),
('PROD-008', 'Portable SSD 1TB', 119.99, 'Electronics'),
('PROD-009', 'Desk Mat XL', 24.99, 'Accessories'),
('PROD-010', 'Cable Organizer Kit', 9.99, 'Accessories')
ON DUPLICATE KEY UPDATE updated_at = CURRENT_TIMESTAMP;

-- Insert some initial sales
INSERT INTO sales (product_id, qty, price, sale_ts) VALUES
(1, 2, 49.99, NOW() - INTERVAL 1 HOUR),
(2, 1, 29.99, NOW() - INTERVAL 55 MINUTE),
(3, 1, 99.99, NOW() - INTERVAL 50 MINUTE),
(4, 3, 19.99, NOW() - INTERVAL 45 MINUTE),
(5, 1, 39.99, NOW() - INTERVAL 40 MINUTE);

-- Show the data
SELECT 'Products:' as '';
SELECT * FROM products;
SELECT 'Sales:' as '';
SELECT * FROM sales;
