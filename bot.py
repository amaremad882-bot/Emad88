import random
import asyncio
from aiogram import Bot, Dispatcher, types
from aiogram.types import InlineKeyboardButton, InlineKeyboardMarkup
from aiogram.utils import executor
from config import BOT_TOKEN, ADMIN_ID, DEFAULT_BALANCE, BET_AMOUNT
from database import get_balance, update_balance, init_db

# إعدادات البوت
bot = Bot(token=BOT_TOKEN)
dp = Dispatcher(bot)

# بدء التفاعل مع البوت
@dp.message_handler(commands="start")
async def start(message: types.Message):
    user_id = message.from_user.id
    balance = get_balance(user_id)  # جلب رصيد المستخدم من قاعدة البيانات
    
    # رابط صفحة اللعبة (تغيير إلى عنوان سيرفرك)
    # إذا كنت تعمل محلياً: "http://localhost:8000"
    # إذا كان على استضافة: "https://your-domain.com"
    game_url = f"http://localhost:8000?user_id={user_id}"
    
    await message.answer(f"مرحبًا بك في لعبة الرهان! 🎮\nرصيدك الحالي: {balance} 💰\n\nاضغط على الزر أدناه للانتقال إلى اللعبة:")
    
    keyboard = types.InlineKeyboardMarkup()
    button = types.InlineKeyboardButton("🎮 ابدأ اللعبة 🎮", url=game_url)
    keyboard.add(button)
    
    await message.answer("العب الآن!", reply_markup=keyboard)

# إضافة النقاط للمستخدمين (الأدمن فقط)
@dp.message_handler(commands="add_points")
async def add_points(message: types.Message):
    if str(message.from_user.id) == str(ADMIN_ID):
        try:
            parts = message.text.split()
            if len(parts) < 3:
                await message.reply("استخدم: /add_points <user_id> <points>")
                return
                
            user_id = int(parts[1])
            points = int(parts[2])
            
            current_balance = get_balance(user_id)
            new_balance = update_balance(user_id, points)
            
            await message.reply(f"✅ تم إضافة {points} نقطة للمستخدم {user_id}\nالرصيد السابق: {current_balance}\nالرصيد الجديد: {new_balance}")
        except ValueError:
            await message.reply("❌ تأكد من إدخال المعرف والنقاط بشكل صحيح (أرقام فقط)")
        except Exception as e:
            await message.reply(f"❌ حدث خطأ: {e}")
    else:
        await message.reply("⛔ ليس لديك صلاحية لإضافة النقاط.")

# عرض الرصيد
@dp.message_handler(commands="balance")
async def show_balance(message: types.Message):
    user_id = message.from_user.id
    balance = get_balance(user_id)
    await message.reply(f"💰 رصيدك الحالي: {balance} نقطة")

# إعادة تعيين قاعدة البيانات (للأدمن فقط)
@dp.message_handler(commands="reset_db")
async def reset_db(message: types.Message):
    if str(message.from_user.id) == str(ADMIN_ID):
        init_db()
        await message.reply("✅ تم إعادة تعيين قاعدة البيانات بنجاح")
    else:
        await message.reply("⛔ ليس لديك صلاحية لإعادة تعيين قاعدة البيانات")

# تشغيل البوت
if __name__ == '__main__':
    # تهيئة قاعدة البيانات
    init_db()
    print("✅ البوت يعمل...")
    executor.start_polling(dp, skip_updates=True)