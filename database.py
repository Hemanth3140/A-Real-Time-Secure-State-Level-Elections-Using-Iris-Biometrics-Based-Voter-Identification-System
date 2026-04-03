import sqlite3
import os
from datetime import datetime

DB_NAME = 'database.db'

def get_db_connection():
    conn = sqlite3.connect(DB_NAME)
    conn.row_factory = sqlite3.Row
    return conn

def init_db():
    conn = get_db_connection()
    c = conn.cursor()
    
    # Users table
    c.execute('''
        CREATE TABLE IF NOT EXISTS users (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            name TEXT NOT NULL,
            email TEXT UNIQUE NOT NULL,
            phone TEXT NOT NULL,
            address TEXT NOT NULL,
            dob TEXT NOT NULL,
            aadhaar_id TEXT UNIQUE NOT NULL,
            password TEXT NOT NULL,
            role TEXT NOT NULL DEFAULT 'User',
            has_voted INTEGER DEFAULT 0
        )
    ''')

    # Parties table
    c.execute('''
        CREATE TABLE IF NOT EXISTS parties (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            name TEXT NOT NULL,
            symbol_path TEXT NOT NULL,
            description TEXT
        )
    ''')

    # Votes table
    c.execute('''
        CREATE TABLE IF NOT EXISTS votes (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            user_id INTEGER NOT NULL,
            party_id INTEGER NOT NULL,
            timestamp DATETIME DEFAULT CURRENT_TIMESTAMP,
            FOREIGN KEY (user_id) REFERENCES users (id),
            FOREIGN KEY (party_id) REFERENCES parties (id)
        )
    ''')
    
    # Performance logs table
    c.execute('''
        CREATE TABLE IF NOT EXISTS performance (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            accuracy REAL,
            loss REAL,
            epoch INTEGER,
            timestamp DATETIME DEFAULT CURRENT_TIMESTAMP
        )
    ''')

    # Create default admin if not exists
    c.execute("SELECT * FROM users WHERE role = 'Admin'")
    admin = c.fetchone()
    if not admin:
        # Simple default admin
        c.execute('''
            INSERT INTO users (name, email, phone, address, dob, aadhaar_id, password, role)
            VALUES (?, ?, ?, ?, ?, ?, ?, ?)
        ''', ('Admin', 'admin@gmail.com', '9999999999', 'Admin HQ', '1990-01-01', 'ADMIN123', 'admin', 'Admin'))
        print("Default Admin created: admin@gmail.com / admin")

    conn.commit()
    conn.close()
    print("Database initialized.")

if __name__ == '__main__':
    init_db()
