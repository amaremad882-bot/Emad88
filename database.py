import os
import asyncpg
from typing import Dict, Any, Optional
from config import DEFAULT_BALANCE

# الحصول على رابط قاعدة البيانات
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
            await conn.execute('''
                CREATE TABLE IF NOT EXISTS users (
                    user_id BIGINT PRIMARY KEY,
                    points INTEGER DEFAULT $1,
                    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                    updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
                )
            ''', DEFAULT_BALANCE)
            print("✅ قاعدة بيانات PostgreSQL مهيأة")
            await conn.close()
        except Exception as e:
            print(f"❌ خطأ في تهيئة PostgreSQL: {e}")
    else:
        try:
            conn = sqlite3.connect('game.db')
            cursor = conn.cursor()
            cursor.execute(f'''
                CREATE TABLE IF NOT EXISTS users (
                    user_id INTEGER PRIMARY KEY,
                    points INTEGER DEFAULT {DEFAULT_BALANCE},
                    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                    updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
                )
            ''')
            conn.commit()
            conn.close()
            print("✅ قاعدة بيانات SQLite مهيأة")
        except Exception as e:
            print(f"❌ خطأ في تهيئة SQLite: {e}")

async def get_balance(user_id: int) -> int:
    """جلب رصيد المستخدم"""
    if USE_POSTGRES:
        try:
            conn = await get_postgres_connection()
            result = await conn.fetchrow(
                'SELECT points FROM users WHERE user_id = $1',
                user_id
            )
            await conn.close()
            
            if result:
                return result['points']
            else:
                return await create_user(user_id)
        except Exception as e:
            print(f"❌ خطأ في جلب الرصيد: {e}")
            return DEFAULT_BALANCE
    else:
        try:
            conn = sqlite3.connect('game.db')
            cursor = conn.cursor()
            cursor.execute(
                'SELECT points FROM users WHERE user_id = ?',
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
            return DEFAULT_BALANCE

async def create_user(user_id: int) -> int:
    """إنشاء مستخدم جديد"""
    if USE_POSTGRES:
        try:
            conn = await get_postgres_connection()
            await conn.execute(
                'INSERT INTO users (user_id, points) VALUES ($1, $2) ON CONFLICT (user_id) DO NOTHING',
                user_id, DEFAULT_BALANCE
            )
            await conn.close()
            return DEFAULT_BALANCE
        except Exception as e:
            print(f"❌ خطأ في إنشاء مستخدم: {e}")
            return DEFAULT_BALANCE
    else:
        try:
            conn = sqlite3.connect('game.db')
            cursor = conn.cursor()
            cursor.execute(
                'INSERT OR IGNORE INTO users (user_id, points) VALUES (?, ?)',
                (user_id, DEFAULT_BALANCE)
            )
            conn.commit()
            conn.close()
            return DEFAULT_BALANCE
        except Exception as e:
            print(f"❌ خطأ في إنشاء مستخدم: {e}")
            return DEFAULT_BALANCE

async def update_balance(user_id: int, amount: int) -> int:
    """تحديث رصيد المستخدم"""
    # التأكد من وجود المستخدم
    await get_balance(user_id)
    
    if USE_POSTGRES:
        try:
            conn = await get_postgres_connection()
            await conn.execute(
                'UPDATE users SET points = points + $1, updated_at = CURRENT_TIMESTAMP WHERE user_id = $2',
                amount, user_id
            )
            result = await conn.fetchrow(
                'SELECT points FROM users WHERE user_id = $1',
                user_id
            )
            await conn.close()
            return result['points'] if result else DEFAULT_BALANCE
        except Exception as e:
            print(f"❌ خطأ في تحديث الرصيد: {e}")
            return DEFAULT_BALANCE
    else:
        try:
            conn = sqlite3.connect('game.db')
            cursor = conn.cursor()
            cursor.execute(
                'UPDATE users SET points = points + ?, updated_at = CURRENT_TIMESTAMP WHERE user_id = ?',
                (amount, user_id)
            )
            cursor.execute(
                'SELECT points FROM users WHERE user_id = ?',
                (user_id,)
            )
            result = cursor.fetchone()
            conn.commit()
            conn.close()
            return result[0] if result else DEFAULT_BALANCE
        except Exception as e:
            print(f"❌ خطأ في تحديث الرصيد: {e}")
            return DEFAULT_BALANCE

async def get_stats() -> Dict[str, Any]:
    """الحصول على إحصائيات اللعبة"""
    if USE_POSTGRES:
        try:
            conn = await get_postgres_connection()
            total_users = await conn.fetchval('SELECT COUNT(*) FROM users')
            total_points = await conn.fetchval('SELECT SUM(points) FROM users')
            max_balance = await conn.fetchval('SELECT MAX(points) FROM users')
            min_balance = await conn.fetchval('SELECT MIN(points) FROM users')
            await conn.close()
            
            return {
                'total_users': total_users or 0,
                'total_points': total_points or 0,
                'max_balance': max_balance or 0,
                'min_balance': min_balance or 0
            }
        except Exception as e:
            print(f"❌ خطأ في جلب الإحصائيات: {e}")
            return {
                'total_users': 0,
                'total_points': 0,
                'max_balance': 0,
                'min_balance': 0
            }
    else:
        try:
            conn = sqlite3.connect('game.db')
            cursor = conn.cursor()
            
            cursor.execute('SELECT COUNT(*) FROM users')
            total_users = cursor.fetchone()[0] or 0
            
            cursor.execute('SELECT SUM(points) FROM users')
            total_points = cursor.fetchone()[0] or 0
            
            cursor.execute('SELECT MAX(points) FROM users')
            max_balance = cursor.fetchone()[0] or 0
            
            cursor.execute('SELECT MIN(points) FROM users')
            min_balance = cursor.fetchone()[0] or 0
            
            conn.close()
            
            return {
                'total_users': total_users,
                'total_points': total_points,
                'max_balance': max_balance,
                'min_balance': min_balance
            }
        except Exception as e:
            print(f"❌ خطأ في جلب الإحصائيات: {e}")
            return {
                'total_users': 0,
                'total_points': 0,
                'max_balance': 0,
                'min_balance': 0
            }