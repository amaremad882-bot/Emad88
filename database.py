import os
import asyncpg
from config import ADMIN_ID

DATABASE_URL = os.environ.get('DATABASE_URL')

if DATABASE_URL and DATABASE_URL.startswith('postgresql://'):
    USE_POSTGRES = True
else:
    USE_POSTGRES = False
    import sqlite3

async def get_postgres_connection():
    return await asyncpg.connect(DATABASE_URL)

async def init_db():
    """تهيئة قاعدة البيانات"""
    if USE_POSTGRES:
        conn = await get_postgres_connection()
        await conn.execute('''
            CREATE TABLE IF NOT EXISTS users (
                user_id BIGINT PRIMARY KEY,
                balance INTEGER DEFAULT 0,
                created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
            )
        ''')
        await conn.execute('''
            CREATE TABLE IF NOT EXISTS transactions (
                id SERIAL PRIMARY KEY,
                from_user_id BIGINT,
                to_user_id BIGINT,
                amount INTEGER,
                created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
            )
        ''')
        await conn.execute('''
            CREATE TABLE IF NOT EXISTS rounds (
                round_id SERIAL PRIMARY KEY,
                result FLOAT,
                status VARCHAR(20) DEFAULT 'waiting',
                start_time TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                end_time TIMESTAMP
            )
        ''')
        await conn.execute('''
            CREATE TABLE IF NOT EXISTS bets (
                bet_id SERIAL PRIMARY KEY,
                user_id BIGINT,
                round_id INTEGER,
                amount INTEGER,
                created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
            )
        ''')
        await conn.close()
    else:
        conn = sqlite3.connect('game.db')
        cursor = conn.cursor()
        cursor.execute('''
            CREATE TABLE IF NOT EXISTS users (
                user_id INTEGER PRIMARY KEY,
                balance INTEGER DEFAULT 0,
                created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
            )
        ''')
        cursor.execute('''
            CREATE TABLE IF NOT EXISTS transactions (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                from_user_id INTEGER,
                to_user_id INTEGER,
                amount INTEGER,
                created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
            )
        ''')
        cursor.execute('''
            CREATE TABLE IF NOT EXISTS rounds (
                round_id INTEGER PRIMARY KEY AUTOINCREMENT,
                result REAL,
                status TEXT DEFAULT 'waiting',
                start_time TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                end_time TIMESTAMP
            )
        ''')
        cursor.execute('''
            CREATE TABLE IF NOT EXISTS bets (
                bet_id INTEGER PRIMARY KEY AUTOINCREMENT,
                user_id INTEGER,
                round_id INTEGER,
                amount INTEGER,
                created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
            )
        ''')
        conn.commit()
        conn.close()

async def set_admin_unlimited_balance(admin_id: int):
    """تعيين رصيد غير محدود للأدمن"""
    if USE_POSTGRES:
        conn = await get_postgres_connection()
        await conn.execute(
            'INSERT INTO users (user_id, balance) VALUES ($1, $2) '
            'ON CONFLICT (user_id) DO UPDATE SET balance = $2',
            admin_id, 999999999
        )
        await conn.close()
    else:
        conn = sqlite3.connect('game.db')
        cursor = conn.cursor()
        cursor.execute(
            'INSERT OR REPLACE INTO users (user_id, balance) VALUES (?, ?)',
            (admin_id, 999999999)
        )
        conn.commit()
        conn.close()

async def get_balance(user_id: int) -> int:
    """جلب رصيد المستخدم"""
    if user_id == ADMIN_ID:
        return 999999999  # رصيد غير محدود للأدمن
    
    if USE_POSTGRES:
        conn = await get_postgres_connection()
        result = await conn.fetchrow(
            'SELECT balance FROM users WHERE user_id = $1', user_id
        )
        await conn.close()
        return result['balance'] if result else 0
    else:
        conn = sqlite3.connect('game.db')
        cursor = conn.cursor()
        cursor.execute('SELECT balance FROM users WHERE user_id = ?', (user_id,))
        result = cursor.fetchone()
        conn.close()
        return result[0] if result else 0

async def create_user(user_id: int):
    """إنشاء مستخدم جديد"""
    if USE_POSTGRES:
        conn = await get_postgres_connection()
        await conn.execute(
            'INSERT INTO users (user_id, balance) VALUES ($1, $2) ON CONFLICT DO NOTHING',
            user_id, 0
        )
        await conn.close()
    else:
        conn = sqlite3.connect('game.db')
        cursor = conn.cursor()
        cursor.execute(
            'INSERT OR IGNORE INTO users (user_id, balance) VALUES (?, ?)',
            (user_id, 0)
        )
        conn.commit()
        conn.close()

async def update_balance(user_id: int, amount: int) -> int:
    """تحديث رصيد المستخدم"""
    # الأدمن لا يتغير رصيده
    if user_id == ADMIN_ID:
        return 999999999
    
    if USE_POSTGRES:
        conn = await get_postgres_connection()
        await conn.execute(
            'UPDATE users SET balance = balance + $1 WHERE user_id = $2',
            amount, user_id
        )
        result = await conn.fetchrow(
            'SELECT balance FROM users WHERE user_id = $1', user_id
        )
        await conn.close()
        return result['balance'] if result else 0
    else:
        conn = sqlite3.connect('game.db')
        cursor = conn.cursor()
        cursor.execute(
            'UPDATE users SET balance = balance + ? WHERE user_id = ?',
            (amount, user_id)
        )
        cursor.execute('SELECT balance FROM users WHERE user_id = ?', (user_id,))
        result = cursor.fetchone()
        conn.commit()
        conn.close()
        return result[0] if result else 0

async def add_transaction(from_user: int, to_user: int, amount: int):
    """إضافة معاملة"""
    if USE_POSTGRES:
        conn = await get_postgres_connection()
        await conn.execute(
            'INSERT INTO transactions (from_user_id, to_user_id, amount) VALUES ($1, $2, $3)',
            from_user, to_user, amount
        )
        await conn.close()
    else:
        conn = sqlite3.connect('game.db')
        cursor = conn.cursor()
        cursor.execute(
            'INSERT INTO transactions (from_user_id, to_user_id, amount) VALUES (?, ?, ?)',
            (from_user, to_user, amount)
        )
        conn.commit()
        conn.close()

async def create_round() -> int:
    """إنشاء جولة جديدة"""
    if USE_POSTGRES:
        conn = await get_postgres_connection()
        result = await conn.fetchrow(
            'INSERT INTO rounds (status) VALUES ($1) RETURNING round_id',
            'betting'
        )
        await conn.close()
        return result['round_id']
    else:
        conn = sqlite3.connect('game.db')
        cursor = conn.cursor()
        cursor.execute('INSERT INTO rounds (status) VALUES (?)', ('betting',))
        round_id = cursor.lastrowid
        conn.commit()
        conn.close()
        return round_id

async def add_bet(user_id: int, round_id: int, amount: int, choice: str):
    """إضافة رهان"""
    if USE_POSTGRES:
        conn = await get_postgres_connection()
        await conn.execute(
            'INSERT INTO bets (user_id, round_id, amount) VALUES ($1, $2, $3)',
            user_id, round_id, amount
        )
        await conn.close()
    else:
        conn = sqlite3.connect('game.db')
        cursor = conn.cursor()
        cursor.execute(
            'INSERT INTO bets (user_id, round_id, amount) VALUES (?, ?, ?)',
            (user_id, round_id, amount)
        )
        conn.commit()
        conn.close()

async def update_round_result(round_id: int, result: float):
    """تحديث نتيجة الجولة"""
    if USE_POSTGRES:
        conn = await get_postgres_connection()
        await conn.execute(
            'UPDATE rounds SET result = $1, status = $2 WHERE round_id = $3',
            result, 'counting', round_id
        )
        await conn.close()
    else:
        conn = sqlite3.connect('game.db')
        cursor = conn.cursor()
        cursor.execute(
            'UPDATE rounds SET result = ?, status = ? WHERE round_id = ?',
            (result, 'counting', round_id)
        )
        conn.commit()
        conn.close()

async def finish_round(round_id: int):
    """إنهاء الجولة"""
    if USE_POSTGRES:
        conn = await get_postgres_connection()
        await conn.execute(
            'UPDATE rounds SET status = $1, end_time = CURRENT_TIMESTAMP WHERE round_id = $2',
            'finished', round_id
        )
        await conn.close()
    else:
        conn = sqlite3.connect('game.db')
        cursor = conn.cursor()
        cursor.execute(
            'UPDATE rounds SET status = ?, end_time = CURRENT_TIMESTAMP WHERE round_id = ?',
            ('finished', round_id)
        )
        conn.commit()
        conn.close()