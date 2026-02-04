import os
import asyncpg
from typing import Dict, Any, List, Optional
from config import BET_OPTIONS

DATABASE_URL = os.environ.get('DATABASE_URL')

if DATABASE_URL and DATABASE_URL.startswith('postgresql://'):
    USE_POSTGRES = True
else:
    USE_POSTGRES = False
    import sqlite3

async def get_postgres_connection():
    """الحصول على اتصال PostgreSQL"""
    return await asyncpg.connect(DATABASE_URL)

async def init_db():
    """تهيئة قاعدة البيانات"""
    if USE_POSTGRES:
        try:
            conn = await get_postgres_connection()
            
            # جدول المستخدمين
            await conn.execute('''
                CREATE TABLE IF NOT EXISTS users (
                    user_id BIGINT PRIMARY KEY,
                    balance INTEGER DEFAULT 0,
                    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                    updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
                )
            ''')
            
            # جدول المعاملات
            await conn.execute('''
                CREATE TABLE IF NOT EXISTS transactions (
                    id SERIAL PRIMARY KEY,
                    from_user_id BIGINT NOT NULL,
                    to_user_id BIGINT NOT NULL,
                    amount INTEGER NOT NULL,
                    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
                )
            ''')
            
            # جدول الجولات
            await conn.execute('''
                CREATE TABLE IF NOT EXISTS rounds (
                    round_id SERIAL PRIMARY KEY,
                    result FLOAT,
                    status VARCHAR(20) DEFAULT 'waiting',
                    start_time TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                    end_time TIMESTAMP
                )
            ''')
            
            # جدول الرهانات
            await conn.execute('''
                CREATE TABLE IF NOT EXISTS bets (
                    bet_id SERIAL PRIMARY KEY,
                    user_id BIGINT NOT NULL,
                    round_id INTEGER NOT NULL,
                    amount INTEGER NOT NULL,
                    choice VARCHAR(10),
                    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
                )
            ''')
            
            await conn.close()
            print("✅ قاعدة بيانات PostgreSQL مهيأة")
            
        except Exception as e:
            print(f"❌ خطأ في PostgreSQL: {e}")
    else:
        try:
            conn = sqlite3.connect('game.db')
            cursor = conn.cursor()
            
            # جدول المستخدمين
            cursor.execute('''
                CREATE TABLE IF NOT EXISTS users (
                    user_id INTEGER PRIMARY KEY,
                    balance INTEGER DEFAULT 0,
                    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                    updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
                )
            ''')
            
            # جدول المعاملات
            cursor.execute('''
                CREATE TABLE IF NOT EXISTS transactions (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    from_user_id INTEGER NOT NULL,
                    to_user_id INTEGER NOT NULL,
                    amount INTEGER NOT NULL,
                    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
                )
            ''')
            
            # جدول الجولات
            cursor.execute('''
                CREATE TABLE IF NOT EXISTS rounds (
                    round_id INTEGER PRIMARY KEY AUTOINCREMENT,
                    result REAL,
                    status TEXT DEFAULT 'waiting',
                    start_time TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                    end_time TIMESTAMP
                )
            ''')
            
            # جدول الرهانات
            cursor.execute('''
                CREATE TABLE IF NOT EXISTS bets (
                    bet_id INTEGER PRIMARY KEY AUTOINCREMENT,
                    user_id INTEGER NOT NULL,
                    round_id INTEGER NOT NULL,
                    amount INTEGER NOT NULL,
                    choice TEXT,
                    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
                )
            ''')
            
            conn.commit()
            conn.close()
            print("✅ قاعدة بيانات SQLite مهيأة")
            
        except Exception as e:
            print(f"❌ خطأ في SQLite: {e}")

async def get_balance(user_id: int) -> int:
    """جلب رصيد المستخدم"""
    if USE_POSTGRES:
        try:
            conn = await get_postgres_connection()
            result = await conn.fetchrow(
                'SELECT balance FROM users WHERE user_id = $1',
                user_id
            )
            await conn.close()
            
            if result:
                return result['balance']
            else:
                return await create_user(user_id)
        except Exception as e:
            print(f"❌ خطأ في جلب الرصيد: {e}")
            return 0
    else:
        try:
            conn = sqlite3.connect('game.db')
            cursor = conn.cursor()
            cursor.execute(
                'SELECT balance FROM users WHERE user_id = ?',
                (user_id,)
            )
            result = cursor.fetchone()
            conn.close()
            
            if result:
                return result[0]
            else:
                return await create_user(user_id)
        except Exception as e:
            print(f"❌ خطأ في جلب الرصيد: {e}")
            return 0

async def create_user(user_id: int) -> int:
    """إنشاء مستخدم جديد"""
    if USE_POSTGRES:
        try:
            conn = await get_postgres_connection()
            await conn.execute(
                'INSERT INTO users (user_id, balance) VALUES ($1, $2) ON CONFLICT (user_id) DO NOTHING',
                user_id, 0
            )
            await conn.close()
            return 0
        except Exception as e:
            print(f"❌ خطأ في إنشاء مستخدم: {e}")
            return 0
    else:
        try:
            conn = sqlite3.connect('game.db')
            cursor = conn.cursor()
            cursor.execute(
                'INSERT OR IGNORE INTO users (user_id, balance) VALUES (?, ?)',
                (user_id, 0)
            )
            conn.commit()
            conn.close()
            return 0
        except Exception as e:
            print(f"❌ خطأ في إنشاء مستخدم: {e}")
            return 0

async def update_balance(user_id: int, amount: int) -> int:
    """تحديث رصيد المستخدم"""
    # التأكد من وجود المستخدم
    await get_balance(user_id)
    
    if USE_POSTGRES:
        try:
            conn = await get_postgres_connection()
            await conn.execute(
                'UPDATE users SET balance = balance + $1, updated_at = CURRENT_TIMESTAMP WHERE user_id = $2',
                amount, user_id
            )
            result = await conn.fetchrow(
                'SELECT balance FROM users WHERE user_id = $1',
                user_id
            )
            await conn.close()
            return result['balance'] if result else 0
        except Exception as e:
            print(f"❌ خطأ في تحديث الرصيد: {e}")
            return 0
    else:
        try:
            conn = sqlite3.connect('game.db')
            cursor = conn.cursor()
            cursor.execute(
                'UPDATE users SET balance = balance + ?, updated_at = CURRENT_TIMESTAMP WHERE user_id = ?',
                (amount, user_id)
            )
            cursor.execute(
                'SELECT balance FROM users WHERE user_id = ?',
                (user_id,)
            )
            result = cursor.fetchone()
            conn.commit()
            conn.close()
            return result[0] if result else 0
        except Exception as e:
            print(f"❌ خطأ في تحديث الرصيد: {e}")
            return 0

async def add_transaction(from_user_id: int, to_user_id: int, amount: int):
    """إضافة معاملة"""
    if USE_POSTGRES:
        try:
            conn = await get_postgres_connection()
            await conn.execute(
                'INSERT INTO transactions (from_user_id, to_user_id, amount) VALUES ($1, $2, $3)',
                from_user_id, to_user_id, amount
            )
            await conn.close()
        except Exception as e:
            print(f"❌ خطأ في إضافة معاملة: {e}")
    else:
        try:
            conn = sqlite3.connect('game.db')
            cursor = conn.cursor()
            cursor.execute(
                'INSERT INTO transactions (from_user_id, to_user_id, amount) VALUES (?, ?, ?)',
                (from_user_id, to_user_id, amount)
            )
            conn.commit()
            conn.close()
        except Exception as e:
            print(f"❌ خطأ في إضافة معاملة: {e}")

async def get_user_transactions(user_id: int, limit: int = 10):
    """الحصول على معاملات المستخدم"""
    if USE_POSTGRES:
        try:
            conn = await get_postgres_connection()
            transactions = await conn.fetch(
                'SELECT * FROM transactions WHERE from_user_id = $1 OR to_user_id = $1 ORDER BY created_at DESC LIMIT $2',
                user_id, limit
            )
            await conn.close()
            return transactions
        except Exception as e:
            print(f"❌ خطأ في جلب المعاملات: {e}")
            return []
    else:
        try:
            conn = sqlite3.connect('game.db')
            cursor = conn.cursor()
            cursor.execute(
                'SELECT * FROM transactions WHERE from_user_id = ? OR to_user_id = ? ORDER BY created_at DESC LIMIT ?',
                (user_id, user_id, limit)
            )
            transactions = cursor.fetchall()
            conn.close()
            return transactions
        except Exception as e:
            print(f"❌ خطأ في جلب المعاملات: {e}")
            return []

async def create_round() -> int:
    """إنشاء جولة جديدة"""
    if USE_POSTGRES:
        try:
            conn = await get_postgres_connection()
            result = await conn.fetchrow(
                'INSERT INTO rounds (status) VALUES ($1) RETURNING round_id',
                'betting'
            )
            await conn.close()
            return result['round_id']
        except Exception as e:
            print(f"❌ خطأ في إنشاء جولة: {e}")
            return 0
    else:
        try:
            conn = sqlite3.connect('game.db')
            cursor = conn.cursor()
            cursor.execute(
                'INSERT INTO rounds (status) VALUES (?)',
                ('betting',)
            )
            round_id = cursor.lastrowid
            conn.commit()
            conn.close()
            return round_id
        except Exception as e:
            print(f"❌ خطأ في إنشاء جولة: {e}")
            return 0

async def add_bet(user_id: int, round_id: int, amount: int, choice: str):
    """إضافة رهان"""
    if USE_POSTGRES:
        try:
            conn = await get_postgres_connection()
            await conn.execute(
                'INSERT INTO bets (user_id, round_id, amount, choice) VALUES ($1, $2, $3, $4)',
                user_id, round_id, amount, choice
            )
            await conn.close()
        except Exception as e:
            print(f"❌ خطأ في إضافة رهان: {e}")
    else:
        try:
            conn = sqlite3.connect('game.db')
            cursor = conn.cursor()
            cursor.execute(
                'INSERT INTO bets (user_id, round_id, amount, choice) VALUES (?, ?, ?, ?)',
                (user_id, round_id, amount, choice)
            )
            conn.commit()
            conn.close()
        except Exception as e:
            print(f"❌ خطأ في إضافة رهان: {e}")

async def get_current_round():
    """الحصول على الجولة الحالية"""
    if USE_POSTGRES:
        try:
            conn = await get_postgres_connection()
            result = await conn.fetchrow(
                'SELECT * FROM rounds WHERE status != $1 ORDER BY round_id DESC LIMIT 1',
                'finished'
            )
            await conn.close()
            return result
        except Exception as e:
            print(f"❌ خطأ في جلب الجولة: {e}")
            return None
    else:
        try:
            conn = sqlite3.connect('game.db')
            cursor = conn.cursor()
            cursor.execute(
                'SELECT * FROM rounds WHERE status != ? ORDER BY round_id DESC LIMIT 1',
                ('finished',)
            )
            result = cursor.fetchone()
            conn.close()
            return result
        except Exception as e:
            print(f"❌ خطأ في جلب الجولة: {e}")
            return None

async def get_round_bets(round_id: int):
    """الحصول على رهانات الجولة"""
    if USE_POSTGRES:
        try:
            conn = await get_postgres_connection()
            bets = await conn.fetch(
                'SELECT * FROM bets WHERE round_id = $1',
                round_id
            )
            await conn.close()
            return bets
        except Exception as e:
            print(f"❌ خطأ في جلب الرهانات: {e}")
            return []
    else:
        try:
            conn = sqlite3.connect('game.db')
            cursor = conn.cursor()
            cursor.execute(
                'SELECT * FROM bets WHERE round_id = ?',
                (round_id,)
            )
            bets = cursor.fetchall()
            conn.close()
            return bets
        except Exception as e:
            print(f"❌ خطأ في جلب الرهانات: {e}")
            return []

async def finish_round(round_id: int):
    """إنهاء الجولة"""
    if USE_POSTGRES:
        try:
            conn = await get_postgres_connection()
            await conn.execute(
                'UPDATE rounds SET status = $1, end_time = CURRENT_TIMESTAMP WHERE round_id = $2',
                'finished', round_id
            )
            await conn.close()
        except Exception as e:
            print(f"❌ خطأ في إنهاء الجولة: {e}")
    else:
        try:
            conn = sqlite3.connect('game.db')
            cursor = conn.cursor()
            cursor.execute(
                'UPDATE rounds SET status = ?, end_time = CURRENT_TIMESTAMP WHERE round_id = ?',
                ('finished', round_id)
            )
            conn.commit()
            conn.close()
        except Exception as e:
            print(f"❌ خطأ في إنهاء الجولة: {e}")

async def update_round_result(round_id: int, result: float):
    """تحديث نتيجة الجولة"""
    if USE_POSTGRES:
        try:
            conn = await get_postgres_connection()
            await conn.execute(
                'UPDATE rounds SET result = $1 WHERE round_id = $2',
                result, round_id
            )
            await conn.close()
        except Exception as e:
            print(f"❌ خطأ في تحديث النتيجة: {e}")
    else:
        try:
            conn = sqlite3.connect('game.db')
            cursor = conn.cursor()
            cursor.execute(
                'UPDATE rounds SET result = ? WHERE round_id = ?',
                (result, round_id)
            )
            conn.commit()
            conn.close()
        except Exception as e:
            print(f"❌ خطأ في تحديث النتيجة: {e}")