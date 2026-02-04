import os
import asyncio
import random
import aiohttp
from datetime import datetime
from fastapi import FastAPI, Request
from fastapi.responses import HTMLResponse, JSONResponse
from fastapi.middleware.cors import CORSMiddleware
import uvicorn
from aiogram import Bot, Dispatcher, types
from aiogram.types import InlineKeyboardMarkup, InlineKeyboardButton
from aiogram.contrib.fsm_storage.memory import MemoryStorage

# استيراد الإعدادات من config.py
from config import (
    BOT_TOKEN, ADMIN_ID, BASE_URL, DEFAULT_BALANCE, 
    BET_AMOUNT, PORT, validate_config
)

# ==================== التحقق من الإعدادات أولاً ====================
print("🔧 جاري التحقق من الإعدادات...")
if not validate_config():
    print("❌ تم إيقاف التشغيل بسبب أخطاء في الإعدادات")
    exit(1)

# ==================== إعداد البوت ====================
bot = Bot(token=BOT_TOKEN)
storage = MemoryStorage()
dp = Dispatcher(bot, storage=storage)

# ==================== إعداد FastAPI ====================
app = FastAPI(
    title="Aviator Game Bot",
    description="لعبة الرهان Aviator على Telegram",
    version="1.0.0",
    docs_url="/docs",
    redoc_url="/redoc"
)

# إعدادات CORS
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# ==================== قاعدة البيانات ====================
from database import init_db, get_balance, update_balance, create_user

# ==================== إعداد Webhook تلقائياً ====================
async def setup_webhook():
    """تعيين Webhook تلقائياً عند البدء"""
    try:
        webhook_url = f"{BASE_URL}/webhook"
        
        async with aiohttp.ClientSession() as session:
            async with session.post(
                f"https://api.telegram.org/bot{BOT_TOKEN}/setWebhook",
                json={
                    "url": webhook_url,
                    "max_connections": 40,
                    "allowed_updates": ["message", "callback_query"]
                }
            ) as response:
                data = await response.json()
                if data.get("ok"):
                    print(f"✅ تم تعيين Webhook بنجاح: {webhook_url}")
                    
                    # إرسال رسالة للأدمن
                    try:
                        await bot.send_message(
                            chat_id=ADMIN_ID,
                            text=f"✅ البوت يعمل!\n📊 الرابط: {BASE_URL}\n⏰ الوقت: {datetime.now().strftime('%Y-%m-%d %H:%M')}"
                        )
                    except:
                        pass
                    
                    return True
                else:
                    print(f"⚠️  لم يتم تعيين Webhook: {data.get('description')}")
                    return False
    except Exception as e:
        print(f"⚠️  خطأ في تعيين Webhook: {str(e)}")
        return False

# ==================== Webhook Endpoint ====================
@app.post("/webhook")
async def telegram_webhook(request: Request):
    """استقبال تحديثات Telegram"""
    try:
        update = types.Update(**await request.json())
        await dp.process_update(update)
        return {"ok": True}
    except Exception as e:
        print(f"❌ خطأ في Webhook: {str(e)}")
        return {"ok": False, "error": str(e)}

# ==================== أوامر البوت ====================
@dp.message_handler(commands=["start", "play"])
async def cmd_start(message: types.Message):
    """بدء اللعبة"""
    user_id = message.from_user.id
    username = message.from_user.first_name or "اللاعب"
    balance = await get_balance(user_id)
    
    # إنشاء رابط اللعبة
    game_url = f"{BASE_URL}/game?user_id={user_id}"
    
    # إنشاء لوحة المفاتيح
    keyboard = InlineKeyboardMarkup(row_width=2)
    keyboard.add(InlineKeyboardButton("🎮 ابدأ اللعب الآن", url=game_url))
    
    keyboard.row(
        InlineKeyboardButton("💰 رصيدي", callback_data="balance"),
        InlineKeyboardButton("📖 التعليمات", callback_data="help")
    )
    
    # رسالة الترحيب
    welcome_text = f"""
🎉 **مرحباً {username}!** 

🎮 **لعبة Aviator - العب واربح النقاط!**

💰 **رصيدك الحالي:** `{balance}` نقطة

🎯 **كيف تلعب:**
1. اضغط على زر 'ابدأ اللعب'
2. اختر 'فوق' أو 'تحت'
3. انتظر النتيجة
4. اربح نقاط مضاعفة!

📊 **معلومات الرهان:**
• قيمة الرهان: `{BET_AMOUNT}` نقطة
• الفوز: تحصل على `{BET_AMOUNT * 2}` نقطة
• الرصيد الابتدائي: `{DEFAULT_BALANCE}` نقطة

🔗 **[اضغط هنا للعب]({game_url})**
    """
    
    await message.answer(welcome_text, reply_markup=keyboard, parse_mode="Markdown")

@dp.message_handler(commands=["balance"])
async def cmd_balance(message: types.Message):
    """عرض الرصيد"""
    user_id = message.from_user.id
    balance = await get_balance(user_id)
    await message.answer(f"💰 **رصيدك الحالي:** `{balance}` نقطة", parse_mode="Markdown")

@dp.message_handler(commands=["help", "menu"])
async def cmd_help(message: types.Message):
    """قائمة المساعدة"""
    help_text = """
🎮 **قائمة أوامر لعبة Aviator**

📋 **الأوامر الأساسية:**
/start - بدء اللعبة والحصول على رابط اللعب
/balance - عرض رصيدك الحالي
/help - عرض هذه القائمة

🎯 **لعبة الرهان:**
• اضغط على /start للحصول على رابط اللعبة
• اختر "فوق" أو "تحت"
• اربح نقاط مضاعفة عند الفوز

💰 **نظام النقاط:**
• الرصيد الابتدائي: 1000 نقطة
• قيمة الرهان: 100 نقطة
• الفوز: تحصل على 200 نقطة (ضعف الرهان)

📞 **الدعم:**
للإبلاغ عن مشاكل، تواصل مع الأدمن
    """
    
    await message.answer(help_text, parse_mode="Markdown")

@dp.message_handler(commands=["addpoints"])
async def cmd_addpoints(message: types.Message):
    """إضافة نقاط (للأدمن فقط)"""
    if message.from_user.id != ADMIN_ID:
        await message.answer("⛔ **غير مصرح لك بهذا الأمر**", parse_mode="Markdown")
        return
    
    try:
        parts = message.text.split()
        if len(parts) != 3:
            await message.answer("📝 **استخدام:** `/addpoints <user_id> <points>`", parse_mode="Markdown")
            return
        
        user_id = int(parts[1])
        points = int(parts[2])
        
        current = await get_balance(user_id)
        new_balance = await update_balance(user_id, points)
        
        await message.answer(
            f"✅ **تم تحديث الرصيد**\n\n"
            f"👤 **المستخدم:** `{user_id}`\n"
            f"➕ **النقاط المضافة:** `{points}`\n"
            f"💰 **الرصيد السابق:** `{current}`\n"
            f"💰 **الرصيد الجديد:** `{new_balance}`",
            parse_mode="Markdown"
        )
    except Exception as e:
        await message.answer(f"❌ **خطأ:** `{str(e)}`", parse_mode="Markdown")

@dp.message_handler(commands=["stats"])
async def cmd_stats(message: types.Message):
    """إحصائيات اللعبة (للأدمن فقط)"""
    if message.from_user.id != ADMIN_ID:
        await message.answer("⛔ **غير مصرح لك بهذا الأمر**", parse_mode="Markdown")
        return
    
    try:
        from database import get_stats
        stats = await get_stats()
        
        stats_text = f"""
📊 **إحصائيات اللعبة**

👥 **عدد اللاعبين:** `{stats['total_users']}`
💰 **مجموع النقاط:** `{stats['total_points']}`
📈 **أعلى رصيد:** `{stats['max_balance']}`
📉 **أقل رصيد:** `{stats['min_balance']}`

⚙️ **الإعدادات:**
• الرابط: {BASE_URL}
• التوكن: {BOT_TOKEN[:10]}...
• الأدمن: {ADMIN_ID}
• الوقت: {datetime.now().strftime('%Y-%m-%d %H:%M')}
        """
        
        await message.answer(stats_text, parse_mode="Markdown")
    except Exception as e:
        await message.answer(f"❌ **خطأ:** `{str(e)}`", parse_mode="Markdown")

# ==================== معالجة الـ Callback ====================
@dp.callback_query_handler(lambda c: c.data in ["balance", "help", "play_again"])
async def process_callback(callback_query: types.CallbackQuery):
    """معالجة الأزرار"""
    user_id = callback_query.from_user.id
    
    if callback_query.data == "balance":
        balance = await get_balance(user_id)
        await bot.answer_callback_query(
            callback_query.id,
            f"💰 رصيدك: {balance} نقطة",
            show_alert=True
        )
    
    elif callback_query.data == "help":
        await cmd_help(callback_query.message)
        await bot.answer_callback_query(callback_query.id)
    
    elif callback_query.data == "play_again":
        game_url = f"{BASE_URL}/game?user_id={user_id}"
        keyboard = InlineKeyboardMarkup()
        keyboard.add(InlineKeyboardButton("🎮 العب مرة أخرى", url=game_url))
        
        await bot.send_message(
            user_id,
            "🔄 **لعبة جديدة!**\n\nاضغط على الزر للعب مرة أخرى:",
            reply_markup=keyboard,
            parse_mode="Markdown"
        )
        await bot.answer_callback_query(callback_query.id)

# ==================== واجهات FastAPI ====================
@app.get("/")
async def home():
    """الصفحة الرئيسية"""
    return {
        "app": "Aviator Game Bot",
        "version": "1.0.0",
        "status": "running",
        "docs": "/docs",
        "game": "/game?user_id=YOUR_ID",
        "admin": ADMIN_ID,
        "bot": f"@{bot.me.username}" if bot.me else "Not connected"
    }

@app.get("/game", response_class=HTMLResponse)
async def game_page(request: Request):
    """صفحة اللعبة"""
    user_id = request.query_params.get("user_id", "0")
    
    # قراءة ملف HTML
    with open("index.html", "r", encoding="utf-8") as f:
        html_content = f.read()
    
    # استبدال المتغيرات
    html_content = html_content.replace("{BASE_URL}", BASE_URL)
    html_content = html_content.replace("{BET_AMOUNT}", str(BET_AMOUNT))
    html_content = html_content.replace("{DEFAULT_BALANCE}", str(DEFAULT_BALANCE))
    html_content = html_content.replace("{USER_ID}", str(user_id))
    
    return HTMLResponse(content=html_content)

@app.get("/api/balance/{user_id}")
async def api_balance(user_id: int):
    """API لجلب الرصيد"""
    try:
        balance = await get_balance(user_id)
        return JSONResponse(content={"balance": balance})
    except Exception as e:
        return JSONResponse(content={"error": str(e)}, status_code=500)

@app.post("/api/play")
async def api_play(request: Request):
    """API للعب"""
    try:
        data = await request.json()
        user_id = int(data.get("user_id", 0))
        choice = data.get("choice", "").upper()
        
        if not user_id:
            return JSONResponse(
                content={"error": "معرف المستخدم مطلوب"},
                status_code=400
            )
        
        if choice not in ["UP", "DOWN"]:
            return JSONResponse(
                content={"error": "الاختيار يجب أن يكون UP أو DOWN"},
                status_code=400
            )
        
        # التحقق من الرصيد
        current_balance = await get_balance(user_id)
        if current_balance < BET_AMOUNT:
            return JSONResponse(
                content={
                    "error": f"رصيدك غير كافٍ",
                    "current_balance": current_balance,
                    "required": BET_AMOUNT
                },
                status_code=400
            )
        
        # توليد النتيجة العشوائية
        result_val = round(random.uniform(0, 100), 2)
        target_line = 50.00
        
        # تحديد الفوز
        is_win = False
        if choice == "UP" and result_val > target_line:
            is_win = True
        elif choice == "DOWN" and result_val < target_line:
            is_win = True
        
        # تحديث الرصيد
        change = BET_AMOUNT if is_win else -BET_AMOUNT
        new_balance = await update_balance(user_id, change)
        
        return JSONResponse(content={
            "success": True,
            "win": is_win,
            "result": result_val,
            "balance": new_balance,
            "bet_amount": BET_AMOUNT,
            "message": "🎉 فوز! +" + str(BET_AMOUNT * 2) if is_win else "😢 خسارة! -" + str(BET_AMOUNT)
        })
        
    except Exception as e:
        return JSONResponse(
            content={"error": str(e)},
            status_code=500
        )

# ==================== حدث بدء التشغيل ====================
@app.on_event("startup")
async def startup_event():
    """تشغيل الأحداث عند البدء"""
    print("=" * 50)
    print("🚀 بدء تشغيل تطبيق Aviator Game...")
    print("=" * 50)
    
    # تهيئة قاعدة البيانات
    await init_db()
    print("✅ قاعدة البيانات مهيأة")
    
    # تعيين Webhook
    await setup_webhook()
    
    # معلومات التشغيل
    print(f"\n📊 معلومات التشغيل:")
    print(f"🌐 الرابط: {BASE_URL}")
    print(f"🤖 البوت: {BOT_TOKEN[:10]}...")
    print(f"👑 الأدمن: {ADMIN_ID}")
    print(f"💰 الرهان: {BET_AMOUNT} نقطة")
    print(f"⏰ الوقت: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")
    print("=" * 50)
    print("✅ التطبيق يعمل وجاهز للاستخدام!")
    print("=" * 50)

# ==================== نقطة الدخول الرئيسية ====================
if __name__ == "__main__":
    uvicorn.run(
        app,
        host="0.0.0.0",
        port=PORT,
        log_level="info"
    )
