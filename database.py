import os
import asyncpg
import json
from datetime import datetime
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
                username VARCHAR(255),
                balance INTEGER DEFAULT 0,
                is_admin BOOLEAN DEFAULT FALSE,
                created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
            )
        ''')
        await conn.execute('''
            CREATE TABLE IF NOT EXISTS transactions (
                id SERIAL PRIMARY KEY,
                user_id BIGINT,
                amount INTEGER,
                type VARCHAR(50),
                description TEXT,
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
                id SERIAL PRIMARY KEY,
                user_id BIGINT,
                round_id INTEGER,
                amount INTEGER,
                multiplier FLOAT DEFAULT 0,
                win_amount INTEGER DEFAULT 0,
                status VARCHAR(20) DEFAULT 'pending',
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
                username TEXT,
                balance INTEGER DEFAULT 0,
                is_admin BOOLEAN DEFAULT 0,
                created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
            )
        ''')
        cursor.execute('''
            CREATE TABLE IF NOT EXISTS transactions (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                user_id INTEGER,
                amount INTEGER,
                type TEXT,
                description TEXT,
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
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                user_id INTEGER,
                round_id INTEGER,
                amount INTEGER,
                multiplier REAL DEFAULT 0,
                win_amount INTEGER DEFAULT 0,
                status TEXT DEFAULT 'pending',
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
            '''INSERT INTO users (user_id, balance, is_admin) 
               VALUES ($1, $2, $3) 
               ON CONFLICT (user_id) 
               DO UPDATE SET balance = $2, is_admin = $3''',
            admin_id, 999999999, True
        )
        await conn.close()
    else:
        conn = sqlite3.connect('game.db')
        cursor = conn.cursor()
        cursor.execute(
            '''INSERT OR REPLACE INTO users (user_id, balance, is_admin) 
               VALUES (?, ?, ?)''',
            (admin_id, 999999999, True)
        )
        conn.commit()
        conn.close()

async def get_balance(user_id: int) -> int:
    """جلب رصيد المستخدم"""
    # إذا كان الأدمن، رجع رصيد غير محدود مباشرة
    if user_id == ADMIN_ID:
        return 999999999
    
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

async def create_user(user_id: int, username: str = None):
    """إنشاء مستخدم جديد"""
    if USE_POSTGRES:
        conn = await get_postgres_connection()
        await conn.execute(
            '''INSERT INTO users (user_id, username, balance, is_admin) 
               VALUES ($1, $2, $3, $4) 
               ON CONFLICT (user_id) DO NOTHING''',
            user_id, username, 0, (user_id == ADMIN_ID)
        )
        await conn.close()
    else:
        conn = sqlite3.connect('game.db')
        cursor = conn.cursor()
        cursor.execute(
            '''INSERT OR IGNORE INTO users (user_id, username, balance, is_admin) 
               VALUES (?, ?, ?, ?)''',
            (user_id, username, 0, (user_id == ADMIN_ID))
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

async def add_transaction(user_id: int, amount: int, type: str, description: str = ""):
    """إضافة معاملة"""
    if USE_POSTGRES:
        conn = await get_postgres_connection()
        await conn.execute(
            'INSERT INTO transactions (user_id, amount, type, description) VALUES ($1, $2, $3, $4)',
            user_id, amount, type, description
        )
        await conn.close()
    else:
        conn = sqlite3.connect('game.db')
        cursor = conn.cursor()
        cursor.execute(
            'INSERT INTO transactions (user_id, amount, type, description) VALUES (?, ?, ?, ?)',
            (user_id, amount, type, description)
        )
        conn.commit()
        conn.close()

async def get_user_transactions(user_id: int, limit: int = 10):
    """جلب معاملات المستخدم"""
    if USE_POSTGRES:
        conn = await get_postgres_connection()
        result = await conn.fetch(
            'SELECT * FROM transactions WHERE user_id = $1 ORDER BY created_at DESC LIMIT $2',
            user_id, limit
        )
        await conn.close()
        return result
    else:
        conn = sqlite3.connect('game.db')
        cursor = conn.cursor()
        cursor.execute(
            'SELECT * FROM transactions WHERE user_id = ? ORDER BY created_at DESC LIMIT ?',
            (user_id, limit)
        )
        result = cursor.fetchall()
        conn.close()
        return result

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

async def get_current_round():
    """جلب الجولة الحالية"""
    if USE_POSTGRES:
        conn = await get_postgres_connection()
        result = await conn.fetchrow(
            "SELECT * FROM rounds WHERE status IN ('betting', 'counting') ORDER BY round_id DESC LIMIT 1"
        )
        await conn.close()
        return result
    else:
        conn = sqlite3.connect('game.db')
        cursor = conn.cursor()
        cursor.execute(
            "SELECT * FROM rounds WHERE status IN ('betting', 'counting') ORDER BY round_id DESC LIMIT 1"
        )
        result = cursor.fetchone()
        conn.close()
        return result

async def add_bet(user_id: int, round_id: int, amount: int):
    """إضافة رهان"""
    if USE_POSTGRES:
        conn = await get_postgres_connection()
        await conn.execute(
            'INSERT INTO bets (user_id, round_id, amount, status) VALUES ($1, $2, $3, $4)',
            user_id, round_id, amount, 'active'
        )
        await conn.close()
    else:
        conn = sqlite3.connect('game.db')
        cursor = conn.cursor()
        cursor.execute(
            'INSERT INTO bets (user_id, round_id, amount, status) VALUES (?, ?, ?, ?)',
            (user_id, round_id, amount, 'active')
        )
        conn.commit()
        conn.close()

async def get_round_bets(round_id: int):
    """جلب رهانات الجولة"""
    if USE_POSTGRES:
        conn = await get_postgres_connection()
        result = await conn.fetch(
            'SELECT * FROM bets WHERE round_id = $1',
            round_id
        )
        await conn.close()
        return result
    else:
        conn = sqlite3.connect('game.db')
        cursor = conn.cursor()
        cursor.execute(
            'SELECT * FROM bets WHERE round_id = ?',
            (round_id,)
        )
        result = cursor.fetchall()
        conn.close()
        return result

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

async def update_bet_result(bet_id: int, multiplier: float, win_amount: int):
    """تحديث نتيجة الرهان"""
    if USE_POSTGRES:
        conn = await get_postgres_connection()
        await conn.execute(
            'UPDATE bets SET multiplier = $1, win_amount = $2, status = $3 WHERE id = $4',
            multiplier, win_amount, 'completed', bet_id
        )
        await conn.close()
    else:
        conn = sqlite3.connect('game.db')
        cursor = conn.cursor()
        cursor.execute(
            'UPDATE bets SET multiplier = ?, win_amount = ?, status = ? WHERE id = ?',
            (multiplier, win_amount, 'completed', bet_id)
        )
        conn.commit()
        conn.close()

async def get_user_active_bet(user_id: int, round_id: int):
    """جلب الرهان النشط للمستخدم"""
    if USE_POSTGRES:
        conn = await get_postgres_connection()
        result = await conn.fetchrow(
            'SELECT * FROM bets WHERE user_id = $1 AND round_id = $2 AND status = $3',
            user_id, round_id, 'active'
        )
        await conn.close()
        return result
    else:
        conn = sqlite3.connect('game.db')
        cursor = conn.cursor()
        cursor.execute(
            'SELECT * FROM bets WHERE user_id = ? AND round_id = ? AND status = ?',
            (user_id, round_id, 'active')
        )
        result = cursor.fetchone()
        conn.close()
        return result

async def get_all_users():
    """جلب جميع المستخدمين"""
    if USE_POSTGRES:
        conn = await get_postgres_connection()
        result = await conn.fetch('SELECT * FROM users ORDER BY created_at DESC')
        await conn.close()
        return result
    else:
        conn = sqlite3.connect('game.db')
        cursor = conn.cursor()
        cursor.execute('SELECT * FROM users ORDER BY created_at DESC')
        result = cursor.fetchall()
        conn.close()
        return result