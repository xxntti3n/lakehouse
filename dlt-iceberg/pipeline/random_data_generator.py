#!/usr/bin/env python3
"""
Random Data Generator for MySQL CDC Pipeline - Single Run
Inserts and updates random products and sales
"""

import pymysql
import random
from datetime import datetime, timedelta
import sys

# MySQL connection config
MYSQL_CONFIG = {
    'host': 'mysql-source',
    'user': 'root',
    'password': 'rootpw',
    'database': 'appdb',
    'port': 3306
}

PRODUCT_NAMES = [
    'Gaming Laptop', 'Wireless Mouse', 'Mechanical Keyboard', '4K Monitor', 'Headphones',
    'Webcam HD', 'USB-C Hub', 'External SSD 1TB', 'Graphics Tablet', 'Smart Speaker',
    'Blu-ray Drive', 'Network Switch', 'Router WiFi 6', 'Power Bank', 'Laptop Stand'
]

def main():
    """Run data updates once"""
    conn = pymysql.connect(**MYSQL_CONFIG)
    cursor = conn.cursor()

    try:
        # Ensure tables exist (without stock/updated_at for existing table)
        cursor.execute("""
            CREATE TABLE IF NOT EXISTS products (
                id INT AUTO_INCREMENT PRIMARY KEY,
                name VARCHAR(255) NOT NULL,
                price DECIMAL(10, 2) NOT NULL,
                created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
            )
        """)

        cursor.execute("""
            CREATE TABLE IF NOT EXISTS sales (
                id INT AUTO_INCREMENT PRIMARY KEY,
                product_id INT NOT NULL,
                quantity INT NOT NULL,
                total DECIMAL(10, 2) NOT NULL,
                sale_date TIMESTAMP DEFAULT CURRENT_TIMESTAMP
            )
        """)

        actions = []

        # Insert 1-2 new products
        num_new_products = random.randint(1, 2)
        for _ in range(num_new_products):
            random_name = random.choice(PRODUCT_NAMES)
            random_price = round(random.uniform(20.0, 2000.0), 2)

            cursor.execute("SELECT id FROM products WHERE name = %s", (random_name,))
            if cursor.fetchone() is None:
                cursor.execute(
                    "INSERT INTO products (name, price) VALUES (%s, %s)",
                    (random_name, random_price)
                )
                actions.append(f"Inserted product: {random_name} (${random_price})")

        # Update 1-2 existing products (price only)
        cursor.execute("SELECT COUNT(*) FROM products")
        product_count = cursor.fetchone()[0]
        if product_count > 0:
            num_updates = min(random.randint(1, 2), product_count)
            for _ in range(num_updates):
                cursor.execute("SELECT id, name FROM products ORDER BY RAND() LIMIT 1")
                result = cursor.fetchone()
                if result:
                    product_id, product_name = result
                    new_price = round(random.uniform(20.0, 2000.0), 2)
                    cursor.execute(
                        "UPDATE products SET price = %s WHERE id = %s",
                        (new_price, product_id)
                    )
                    actions.append(f"Updated {product_name} price to ${new_price}")

        # Insert 2-4 new sales
        num_new_sales = random.randint(2, 4)
        for _ in range(num_new_sales):
            cursor.execute("SELECT id, name, price FROM products ORDER BY RAND() LIMIT 1")
            result = cursor.fetchone()
            if result:
                product_id, product_name, price = result
                quantity = random.randint(1, 5)
                total = round(price * quantity, 2)

                cursor.execute(
                    "INSERT INTO sales (product_id, quantity, total) VALUES (%s, %s, %s)",
                    (product_id, quantity, total)
                )
                actions.append(f"Sale: {quantity}x {product_name} for ${total}")

        # Update 1-2 existing sales
        cursor.execute("SELECT COUNT(*) FROM sales")
        sales_count = cursor.fetchone()[0]
        if sales_count > 0:
            num_sale_updates = min(random.randint(1, 2), sales_count)
            for _ in range(num_sale_updates):
                cursor.execute("SELECT id, product_id, quantity, total FROM sales ORDER BY RAND() LIMIT 1")
                result = cursor.fetchone()
                if result:
                    sale_id, product_id, old_quantity, old_total = result
                    cursor.execute("SELECT price FROM products WHERE id = %s", (product_id,))
                    price_result = cursor.fetchone()
                    if price_result:
                        unit_price = price_result[0]
                        additional_qty = random.randint(1, 3)
                        new_quantity = old_quantity + additional_qty
                        additional_total = round(unit_price * additional_qty, 2)
                        new_total = old_total + additional_total

                        cursor.execute(
                            "UPDATE sales SET quantity = %s, total = %s WHERE id = %s",
                            (new_quantity, new_total, sale_id)
                        )
                        actions.append(f"Updated sale #{sale_id}: +{additional_qty} units (+${additional_total})")

        conn.commit()

        # Print summary
        timestamp = datetime.now().strftime('%Y-%m-%d %H:%M:%S')
        print(f"[{timestamp}] Database Update Summary:")
        print(f"  Total changes: {len(actions)}")
        for action in actions:
            print(f"  ✓ {action}")

        return 0

    except Exception as e:
        conn.rollback()
        print(f"✗ Error: {e}")
        return 1
    finally:
        cursor.close()
        conn.close()

if __name__ == "__main__":
    sys.exit(main())
