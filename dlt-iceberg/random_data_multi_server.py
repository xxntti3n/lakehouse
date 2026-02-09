#!/usr/bin/env python3
"""
Random Data Generator for Multi-Server MySQL Setup
Inserts and updates random products and sales across 3 independent servers
"""

import pymysql
import random
from datetime import datetime
import sys

# MySQL connection configs for 3 independent servers
MYSQL_SERVERS = [
    {
        'name': 'Server 1',
        'host': 'mysql-server-1',
        'port': 3306,
        'user': 'root',
        'password': 'rootpw',
        'database': 'appdb'
    },
    {
        'name': 'Server 2',
        'host': 'mysql-server-2',
        'port': 3306,
        'user': 'root',
        'password': 'rootpw',
        'database': 'appdb'
    },
    {
        'name': 'Server 3',
        'host': 'mysql-server-3',
        'port': 3306,
        'user': 'root',
        'password': 'rootpw',
        'database': 'appdb'
    }
]

PRODUCT_NAMES = [
    'Gaming Laptop', 'Wireless Mouse', 'Mechanical Keyboard', '4K Monitor', 'Headphones',
    'Webcam HD', 'USB-C Hub', 'External SSD 1TB', 'Graphics Tablet', 'Smart Speaker',
    'Blu-ray Drive', 'Network Switch', 'Router WiFi 6', 'Power Bank', 'Laptop Stand'
]

def update_server(server_config):
    """Generate random data for a single server"""
    actions = []

    try:
        conn = pymysql.connect(
            host=server_config['host'],
            port=server_config['port'],
            user=server_config['user'],
            password=server_config['password'],
            database=server_config['database']
        )
        cursor = conn.cursor()

        # Insert 1 new product
        random_name = random.choice(PRODUCT_NAMES)
        random_price = round(random.uniform(20.0, 2000.0), 2)

        cursor.execute("SELECT id FROM products WHERE name = %s", (random_name,))
        if cursor.fetchone() is None:
            cursor.execute(
                "INSERT INTO products (name, price) VALUES (%s, %s)",
                (random_name, random_price)
            )
            actions.append(f"Inserted product: {random_name} (${random_price})")

        # Update 1 existing product
        cursor.execute("SELECT COUNT(*) FROM products")
        product_count = cursor.fetchone()[0]
        if product_count > 0:
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

        # Insert 1-2 new sales
        num_new_sales = random.randint(1, 2)
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

        conn.commit()
        cursor.close()
        conn.close()

        return actions

    except Exception as e:
        return [f"Error: {e}"]

def main():
    """Run data updates across all servers"""
    timestamp = datetime.now().strftime('%Y-%m-%d %H:%M:%S')
    print(f"[{timestamp}] Multi-Server Data Update Summary:")
    print("=" * 60)

    total_changes = 0

    # Update each server
    for server in MYSQL_SERVERS:
        print(f"\n📍 {server['name']} ({server['host']}:{server['port']})")
        actions = update_server(server)
        total_changes += len(actions)

        for action in actions:
            if action.startswith("Error"):
                print(f"  ✗ {action}")
            else:
                print(f"  ✓ {action}")

    print("\n" + "=" * 60)
    print(f"Total changes across all servers: {total_changes}")
    return 0

if __name__ == "__main__":
    sys.exit(main())
