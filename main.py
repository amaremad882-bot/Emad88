import os
import asyncio
import random
import aiohttp
from datetime import datetime, timedelta
from contextlib import asynccontextmanager
from fastapi import FastAPI, Request
from fastapi.responses import HTMLResponse, JSONResponse
from fastapi.middleware.cors import CORSMiddleware
import uvicorn
from aiogram import Bot, Dispatcher, types
from aiogram.types import InlineKeyboardMarkup, InlineKeyboardButton
from aiogram.contrib.fsm_storage.memory import MemoryStorage

# استيراد الإعدادات
from config import (
    BOT_TOKEN, ADMIN_ID, BASE_URL, PORT, validate_config,
    ROUND_DURATION, BETTING_DURATION, BET_OPTIONS
)

# ==================== التحقق من الإعدادات ====================
print("🔧 جاري التحقق من الإعدادات...")
if not validate_config():
    print("❌ تم إيقاف التشغيل بسبب أخطاء في الإعدادات")
    exit(1)

# ==================== إعداد البوت ====================
bot = Bot(token=BOT_TOKEN)
storage = MemoryStorage()
dp = Dispatcher(bot, storage=storage)

# ==================== قاعدة البيانات ====================
from database import (
    init_db, get_balance, update_balance, create_user,
    add_transaction, get_user_transactions,
    create_round, add_bet, get_current_round,
    get_round_bets, finish_round, update_round_result
)

# ==================== حالة الجولة ====================
class GameRound:
    def __init__(self):
        self.round_id = None
        self.start_time = None
        self.betting_end = None
        self.round_end = None
        self.result = None
        self.status = "waiting"  # waiting, betting, finished
        self.bets = {}

game_round = GameRound()

# ==================== إدارة الجولات ====================
async def start_new_round():
    """بدء جولة جديدة"""
    global game_round
    
    # إنشاء جولة جديدة في قاعدة البيانات
    game_round.round_id = await create_round()
    game_round.start_time = datetime.now()
    game_round.betting_end = game_round.start_time + timedelta(seconds=BETTING_DURATION)
    game_round.round_end = game_round.start_time + timedelta(seconds=ROUND_DURATION)
    game_round.result = None
    game_round.status = "betting"
    game_round.bets = {}
    
    print(f"🔄 بدأت الجولة #{game_round.round_id}")
    print(f"⏰ وقت الرهان حتى: {game_round.betting_end}")
    print(f"⏰ نهاية الجولة: {game_round.round_end}")

async def process_round():
    """معالجة الجولة الحالية"""
    while True:
        now = datetime.now()
        
        if game_round.status == "betting" and now >= game_round.betting_end:
            # انتهى وقت الرهان
            game_round.status = "counting"
            
            # توليد النتيجة العشوائية
            game_round.result = round(random.uniform(1.0, 10.0), 2)
            
            # تحديث النتيجة في قاعدة البيانات
            await update_round_result(game_round.round_id, game_round.result)
            
            # معالجة الرهانات
            await process_all_bets()
            
            print(f"🎯 نتيجة الجولة #{game_round.round_id}: {game_round.result}x")
            
            # الانتقال للجولة التالية بعد انتهاء الوقت
            await asyncio.sleep(ROUND_DURATION - BETTING_DURATION)
            await finish_round(game_round.round_id)
            await start_new_round()
        
        elif game_round.status == "waiting":
            # إذا لم تكن هناك جولة نشطة، نبدأ واحدة
            await start_new_round()
        
        await asyncio.sleep(1)

async def process_all_bets():
    """معالجة جميع الرهانات في الجولة"""
    bets = await get_round_bets(game_round.round_id)
    
    for bet in bets:
        try:
            user_id = bet['user_id'] if isinstance(bet, dict) else bet[1]
            amount = bet['amount'] if isinstance(bet, dict) else bet[3]
            choice = bet['choice'] if isinstance(bet, dict) else bet[4]
            
            # حساب الربح
            if game_round.result > 1.0:  # نفترض أن 1.0 هو الحد الأدنى للفوز
                win_amount = int(amount * game_round.result)
                await update_balance(user_id, win_amount)
                
                # إرسال إشعار للمستخدم
                try:
                    await bot.send_message(
                        user_id,
                        f"🎉 **ربحت!**\n\n"
                        f"🎯 النتيجة: {game_round.result}x\n"
                        f"💰 الرهان: {amount}\n"
                        f"🏆 الربح: {win_amount}\n"
                        f"📈 رصيدك الجديد: {await get_balance(user_id)}"
                    )
                except:
                    pass
        except Exception as e:
            print(f"❌ خطأ في معالجة الرهان: {e}")

# ==================== إعداد Webhook ====================
async def setup_webhook():
    """تعيين Webhook تلقائياً"""
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
                    return True
                else:
                    print(f"⚠️  لم يتم تعيين Webhook: {data.get('description')}")
                    return False
    except Exception as e:
        print(f"⚠️  خطأ في تعيين Webhook: {str(e)}")
        return False

# ==================== أوامر البوت ====================
@dp.message_handler(commands=["start"])
async def cmd_start(message: types.Message):
    """بدء البوت"""
    user_id = message.from_user.id
    username = message.from_user.first_name or "اللاعب"
    
    # إنشاء مستخدم إذا لم يكن موجوداً
    await create_user(user_id)
    
    # جلب الرصيد
    balance = await get_balance(user_id)
    
    # إنشاء رابط اللعبة
    game_url = f"{BASE_URL}/game?user_id={user_id}"
    
    # إنشاء لوحة المفاتيح
    keyboard = InlineKeyboardMarkup(row_width=2)
    keyboard.add(InlineKeyboardButton("🎮 ابدأ اللعب الآن", url=game_url))
    
    keyboard.row(
        InlineKeyboardButton("💰 معرفة الرصيد", callback_data="check_balance"),
        InlineKeyboardButton("📊 إرسال رصيد", callback_data="send_balance")
    )
    
    # رسالة الترحيب
    welcome_text = f"""
🎉 **مرحباً {username}!** 

🎮 **لعبة Aviator - الرهان الحقيقي!**

💰 **رصيدك الحالي:** `{balance}` نقطة

📊 **معلومات النظام:**
• الجولة: 60 ثانية
• وقت الرهان: 30 ثانية
• خيارات الرهان: {', '.join(map(str, BET_OPTIONS))}

🎯 **كيف تلعب:**
1. اضغط على زر 'ابدأ اللعب'
2. اختر مبلغ الرهان
3. شاهد الطائرة تصعد
4. اربح حسب المضاعف!

🔗 **[اضغط هنا للعب]({game_url})**
    """
    
    await message.answer(welcome_text, reply_markup=keyboard, parse_mode="Markdown")

@dp.message_handler(commands=["balance", "رصيدي"])
async def cmd_balance(message: types.Message):
    """عرض الرصيد"""
    user_id = message.from_user.id
    balance = await get_balance(user_id)
    
    # عرض تاريخ المعاملات
    transactions = await get_user_transactions(user_id, limit=5)
    
    transactions_text = ""
    if transactions:
        transactions_text = "\n\n📜 **آخر المعاملات:**\n"
        for trans in transactions:
            trans_type = "⬆️ أرسلت" if trans[1] == user_id else "⬇️ استلمت"
            amount = trans[3]
            time = trans[4][:16] if len(trans) > 4 else ""
            transactions_text += f"• {trans_type}: {amount} نقطة ({time})\n"
    
    await message.answer(
        f"💰 **رصيدك الحالي:** `{balance}` نقطة{transactions_text}",
        parse_mode="Markdown"
    )

@dp.message_handler(commands=["send", "ارسال"])
async def cmd_send(message: types.Message):
    """إرسال رصيد لمستخدم آخر"""
    user_id = message.from_user.id
    sender_balance = await get_balance(user_id)
    
    try:
        parts = message.text.split()
        if len(parts) != 3:
            await message.answer(
                "📝 **استخدام:**\n`/send <معرف_المستخدم> <المبلغ>`\n\n"
                "مثال: `/send 123456789 100`",
                parse_mode="Markdown"
            )
            return
        
        to_user_id = int(parts[1])
        amount = int(parts[2])
        
        # التحقق من المبلغ
        if amount <= 0:
            await message.answer("❌ **المبلغ يجب أن يكون أكبر من صفر**", parse_mode="Markdown")
            return
        
        if sender_balance < amount:
            await message.answer("❌ **رصيدك غير كافي**", parse_mode="Markdown")
            return
        
        if user_id == to_user_id:
            await message.answer("❌ **لا يمكنك إرسال الرصيد لنفسك**", parse_mode="Markdown")
            return
        
        # خصم من المرسل وإضافة للمستقبل
        await update_balance(user_id, -amount)
        await update_balance(to_user_id, amount)
        
        # تسجيل المعاملة
        await add_transaction(user_id, to_user_id, amount)
        
        # إرسال تأكيد للمرسل
        await message.answer(
            f"✅ **تم إرسال الرصيد بنجاح**\n\n"
            f"👤 **إلى:** `{to_user_id}`\n"
            f"💰 **المبلغ:** `{amount}` نقطة\n"
            f"💳 **رصيدك الآن:** `{sender_balance - amount}` نقطة",
            parse_mode="Markdown"
        )
        
        # إرسال إشعار للمستقبل
        try:
            await bot.send_message(
                to_user_id,
                f"🎁 **استلمت رصيداً جديداً!**\n\n"
                f"👤 **من:** `{user_id}`\n"
                f"💰 **المبلغ:** `{amount}` نقطة\n"
                f"📈 **رصيدك الجديد:** `{await get_balance(to_user_id)}` نقطة"
            )
        except:
            pass
        
    except ValueError:
        await message.answer("❌ **خطأ في البيانات. تأكد من إدخال أرقام صحيحة**", parse_mode="Markdown")
    except Exception as e:
        await message.answer(f"❌ **خطأ:** `{str(e)}`", parse_mode="Markdown")

@dp.message_handler(commands=["add", "اضافة"])
async def cmd_add_balance(message: types.Message):
    """إضافة رصيد (للأدمن فقط)"""
    if message.from_user.id != ADMIN_ID:
        await message.answer("⛔ **غير مصرح لك بهذا الأمر**", parse_mode="Markdown")
        return
    
    try:
        parts = message.text.split()
        if len(parts) != 3:
            await message.answer(
                "📝 **استخدام:**\n`/add <معرف_المستخدم> <المبلغ>`\n\n"
                "مثال: `/add 123456789 1000`",
                parse_mode="Markdown"
            )
            return
        
        user_id = int(parts[1])
        amount = int(parts[2])
        
        if amount <= 0:
            await message.answer("❌ **المبلغ يجب أن يكون أكبر من صفر**", parse_mode="Markdown")
            return
        
        current = await get_balance(user_id)
        new_balance = await update_balance(user_id, amount)
        
        await message.answer(
            f"✅ **تم إضافة الرصيد**\n\n"
            f"👤 **المستخدم:** `{user_id}`\n"
            f"➕ **المضاف:** `{amount}` نقطة\n"
            f"📊 **السابق:** `{current}` نقطة\n"
            f"💰 **الجديد:** `{new_balance}` نقطة",
            parse_mode="Markdown"
        )
        
    except Exception as e:
        await message.answer(f"❌ **خطأ:** `{str(e)}`", parse_mode="Markdown")

@dp.message_handler(commands=["help", "مساعدة"])
async def cmd_help(message: types.Message):
    """قائمة المساعدة"""
    help_text = """
🎮 **أوامر لعبة Aviator**

📋 **الأوامر الأساسية:**
/start - بدء البوت وعرض رابط اللعبة
/balance - عرض رصيدك ومعاملاتك
/send <id> <مبلغ> - إرسال رصيد لمستخدم
/help - عرض هذه القائمة

🎯 **لعبة الرهان:**
• كل جولة 60 ثانية
• وقت الرهان 30 ثانية
• اختر مبلغ الرهان من القائمة
• شاهد الطائرة تصعد وتحدد الربح

💰 **نظام الرصيد:**
• ابدأ برصيد 0
• إرسال واستقبال من الآخرين
• الأدمن يمكنه إضافة رصيد

⚙️ **أوامر الأدمن:**
/add <id> <مبلغ> - إضافة رصيد لمستخدم

📞 **الدعم:**
تواصل مع الأدمن للمساعدة
    """
    
    await message.answer(help_text, parse_mode="Markdown")

@dp.message_handler(commands=["round", "جولة"])
async def cmd_round_info(message: types.Message):
    """معلومات الجولة الحالية"""
    now = datetime.now()
    
    if game_round.status == "waiting":
        await message.answer("⏳ **لا توجد جولة نشطة حالياً**", parse_mode="Markdown")
        return
    
    if game_round.status == "betting":
        time_left = (game_round.betting_end - now).seconds
        status_text = f"🔄 **الجولة #{game_round.round_id} - وقت الرهان**\n⏰ وقت متبقي: {time_left} ثانية"
    else:
        time_left = (game_round.round_end - now).seconds
        status_text = f"🎯 **الجولة #{game_round.round_id} - جارية**\n🎲 النتيجة: {game_round.result}x\n⏰ وقت متبقي: {time_left} ثانية"
    
    await message.answer(status_text, parse_mode="Markdown")

# ==================== معالجة Callback ====================
@dp.callback_query_handler(lambda c: c.data in ["check_balance", "send_balance", "play_now"])
async def process_callback(callback_query: types.CallbackQuery):
    """معالجة أزرار Callback"""
    user_id = callback_query.from_user.id
    
    if callback_query.data == "check_balance":
        balance = await get_balance(user_id)
        await bot.answer_callback_query(
            callback_query.id,
            f"💰 رصيدك: {balance} نقطة",
            show_alert=True
        )
    
    elif callback_query.data == "send_balance":
        await bot.send_message(
            user_id,
            "📤 **لإرسال رصيد:**\n\n"
            "استخدم الأمر:\n`/send <معرف_المستخدم> <المبلغ>`\n\n"
            "مثال:\n`/send 123456789 500`\n\n"
            "⚠️ تأكد من:\n1. معرف المستخدم صحيح\n2. لديك رصيد كافي\n3. المبلغ أكبر من صفر",
            parse_mode="Markdown"
        )
        await bot.answer_callback_query(callback_query.id)
    
    elif callback_query.data == "play_now":
        game_url = f"{BASE_URL}/game?user_id={user_id}"
        await bot.send_message(
            user_id,
            f"🎮 **اضغط على الرابط للعب:**\n{game_url}",
            parse_mode="Markdown"
        )
        await bot.answer_callback_query(callback_query.id)

# ==================== FastAPI Application ====================
@asynccontextmanager
async def lifespan(app: FastAPI):
    """إدارة دورة حياة التطبيق"""
    # عند البدء
    print("=" * 50)
    print("🚀 بدء تشغيل لعبة Aviator...")
    print("=" * 50)
    
    # تهيئة قاعدة البيانات
    await init_db()
    print("✅ قاعدة البيانات جاهزة")
    
    # إعداد Webhook
    await setup_webhook()
    
    # بدء نظام الجولات
    asyncio.create_task(process_round())
    
    # معلومات التشغيل
    print(f"\n📊 معلومات التشغيل:")
    print(f"🌐 الرابط: {BASE_URL}")
    print(f"🤖 البوت: {BOT_TOKEN[:10]}...")
    print(f"👑 الأدمن: {ADMIN_ID}")
    print(f"⏳ مدة الجولة: {ROUND_DURATION} ثانية")
    print(f"⏰ وقت الرهان: {BETTING_DURATION} ثانية")
    print(f"💰 خيارات الرهان: {BET_OPTIONS}")
    print("=" * 50)
    print("✅ التطبيق يعمل بنجاح!")
    print("=" * 50)
    
    yield
    
    # عند الإيقاف
    print("\n🛑 إيقاف التطبيق...")

app = FastAPI(
    title="Aviator Game",
    description="لعبة رهان Aviator مع نظام جولات متكامل",
    version="2.0.0",
    lifespan=lifespan
)

# CORS middleware
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

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

# ==================== API Endpoints ====================
@app.get("/")
async def home():
    """الصفحة الرئيسية"""
    return {
        "app": "Aviator Game v2.0",
        "status": "running",
        "round": game_round.round_id,
        "round_status": game_round.status,
        "result": game_round.result,
        "admin": ADMIN_ID
    }

@app.get("/game")
async def game_page(request: Request):
    """صفحة اللعبة"""
    user_id = request.query_params.get("user_id", "0")
    
    try:
        with open("index.html", "r", encoding="utf-8") as f:
            html_content = f.read()
    except FileNotFoundError:
        return HTMLResponse("<h1>❌ ملف اللعبة غير موجود</h1>")
    
    # استبدال المتغيرات
    html_content = html_content.replace("{BASE_URL}", BASE_URL)
    html_content = html_content.replace("{USER_ID}", str(user_id))
    html_content = html_content.replace("{BET_OPTIONS}", str(BET_OPTIONS))
    
    return HTMLResponse(content=html_content)

@app.get("/api/balance/{user_id}")
async def api_balance(user_id: int):
    """API لجلب الرصيد"""
    try:
        balance = await get_balance(user_id)
        return JSONResponse({"balance": balance})
    except Exception as e:
        return JSONResponse({"error": str(e)}, status_code=500)

@app.get("/api/round")
async def api_round_info():
    """API لمعلومات الجولة الحالية"""
    now = datetime.now()
    
    response = {
        "round_id": game_round.round_id,
        "status": game_round.status,
        "result": game_round.result
    }
    
    if game_round.status == "betting":
        time_left = max(0, (game_round.betting_end - now).seconds)
        response.update({
            "betting_time_left": time_left,
            "total_time_left": (game_round.round_end - now).seconds
        })
    elif game_round.status == "counting":
        response["time_left"] = (game_round.round_end - now).seconds
    
    return JSONResponse(response)

@app.post("/api/bet")
async def api_place_bet(request: Request):
    """API لوضع الرهان"""
    try:
        data = await request.json()
        user_id = int(data.get("user_id", 0))
        amount = int(data.get("amount", 0))
        
        if not user_id:
            return JSONResponse({"error": "معرف المستخدم مطلوب"}, status_code=400)
        
        if amount <= 0:
            return JSONResponse({"error": "المبلغ يجب أن يكون أكبر من صفر"}, status_code=400)
        
        if amount not in BET_OPTIONS:
            return JSONResponse({"error": "مبلغ الرهان غير صالح"}, status_code=400)
        
        # التحقق من حالة الجولة
        if game_round.status != "betting":
            return JSONResponse({"error": "ليس وقت الرهان الآن"}, status_code=400)
        
        now = datetime.now()
        if now >= game_round.betting_end:
            return JSONResponse({"error": "انتهى وقت الرهان"}, status_code=400)
        
        # التحقق من الرصيد
        balance = await get_balance(user_id)
        if balance < amount:
            return JSONResponse(
                {"error": "رصيد غير كافي", "balance": balance, "required": amount},
                status_code=400
            )
        
        # خصم المبلغ
        new_balance = await update_balance(user_id, -amount)
        
        # تسجيل الرهان
        await add_bet(user_id, game_round.round_id, amount, "auto")
        
        return JSONResponse({
            "success": True,
            "message": f"✅ تم وضع رهان بقيمة {amount}",
            "balance": new_balance,
            "round_id": game_round.round_id
        })
        
    except Exception as e:
        return JSONResponse({"error": str(e)}, status_code=500)

@app.post("/api/send")
async def api_send_balance(request: Request):
    """API لإرسال الرصيد"""
    try:
        data = await request.json()
        from_user = int(data.get("from_user", 0))
        to_user = int(data.get("to_user", 0))
        amount = int(data.get("amount", 0))
        
        if not from_user or not to_user:
            return JSONResponse({"error": "معرفات المستخدمين مطلوبة"}, status_code=400)
        
        if amount <= 0:
            return JSONResponse({"error": "المبلغ يجب أن يكون أكبر من صفر"}, status_code=400)
        
        # التحقق من الرصيد
        balance = await get_balance(from_user)
        if balance < amount:
            return JSONResponse(
                {"error": "رصيد غير كافي", "balance": balance},
                status_code=400
            )
        
        # تنفيذ التحويل
        await update_balance(from_user, -amount)
        await update_balance(to_user, amount)
        await add_transaction(from_user, to_user, amount)
        
        return JSONResponse({
            "success": True,
            "message": f"✅ تم إرسال {amount} إلى {to_user}",
            "new_balance": balance - amount
        })
        
    except Exception as e:
        return JSONResponse({"error": str(e)}, status_code=500)

# ==================== نقطة الدخول ====================
if __name__ == "__main__":
    uvicorn.run(
        app,
        host="0.0.0.0",
        port=PORT,
        log_level="info"
    )