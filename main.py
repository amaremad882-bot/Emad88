import os
import asyncio
import random
import aiohttp
import logging
from datetime import datetime, timedelta
from contextlib import asynccontextmanager
from fastapi import FastAPI, Request
from fastapi.responses import HTMLResponse, JSONResponse
from fastapi.middleware.cors import CORSMiddleware
import uvicorn
from aiogram import Bot, Dispatcher, types
from aiogram.types import InlineKeyboardMarkup, InlineKeyboardButton
from aiogram.contrib.fsm_storage.memory import MemoryStorage

# ==================== إعداد التسجيل ====================
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

# ==================== استيراد الإعدادات ====================
from config import (
    BOT_TOKEN, ADMIN_ID, BASE_URL, PORT, validate_config,
    ROUND_DURATION, BETTING_DURATION, BET_OPTIONS
)

# ==================== التحقق من الإعدادات ====================
logger.info("🔧 جاري التحقق من الإعدادات...")
if not validate_config():
    logger.error("❌ تم إيقاف التشغيل بسبب أخطاء في الإعدادات")
    exit(1)

# ==================== إعداد البوت ====================
bot = Bot(token=BOT_TOKEN, parse_mode="HTML")
Bot.set_current(bot)
storage = MemoryStorage()
dp = Dispatcher(bot, storage=storage)

# ==================== قاعدة البيانات ====================
try:
    from database import (
        init_db, get_balance, update_balance, create_user,
        add_transaction, get_user_transactions,
        create_round, add_bet, get_current_round,
        get_round_bets, finish_round, update_round_result,
        set_admin_unlimited_balance  # ⬅️ جديد
    )
    logger.info("✅ تم تحميل قاعدة البيانات بنجاح")
except ImportError as e:
    logger.error(f"❌ خطأ في تحميل قاعدة البيانات: {e}")
    exit(1)

# ==================== حالة الجولة ====================
class GameRound:
    def __init__(self):
        self.round_id = None
        self.start_time = None
        self.betting_end = None
        self.round_end = None
        self.result = None
        self.status = "waiting"
        self.bets = {}
        self.remaining_time = 0

game_round = GameRound()

# ==================== إدارة الجولات ====================
async def start_new_round():
    """بدء جولة جديدة"""
    global game_round
    try:
        game_round.round_id = await create_round()
        game_round.start_time = datetime.now()
        game_round.betting_end = game_round.start_time + timedelta(seconds=BETTING_DURATION)
        game_round.round_end = game_round.start_time + timedelta(seconds=ROUND_DURATION)
        game_round.result = None
        game_round.status = "betting"
        game_round.bets = {}
        game_round.remaining_time = ROUND_DURATION
        
        logger.info(f"🔄 بدأت الجولة #{game_round.round_id}")
        return True
    except Exception as e:
        logger.error(f"❌ خطأ في بدء الجولة: {e}")
        return False

async def process_round():
    """معالجة الجولة الحالية"""
    logger.info("🎮 بدء نظام الجولات...")
    while True:
        try:
            now = datetime.now()
            game_round.remaining_time = max(0, int((game_round.round_end - now).total_seconds())) if game_round.round_end else 0
            
            if game_round.status == "betting" and now >= game_round.betting_end:
                game_round.status = "counting"
                game_round.result = round(random.uniform(1.0, 10.0), 2)
                
                await update_round_result(game_round.round_id, game_round.result)
                await process_all_bets()
                
                logger.info(f"🎯 نتيجة الجولة #{game_round.round_id}: {game_round.result}x")
                
                await asyncio.sleep(ROUND_DURATION - BETTING_DURATION)
                await finish_round(game_round.round_id)
                await start_new_round()
            
            elif game_round.status == "waiting":
                await start_new_round()
            
            await asyncio.sleep(1)
        except Exception as e:
            logger.error(f"❌ خطأ في معالجة الجولة: {e}")
            await asyncio.sleep(5)

async def process_all_bets():
    """معالجة جميع الرهانات"""
    try:
        bets = await get_round_bets(game_round.round_id)
        
        for bet in bets:
            try:
                if isinstance(bet, dict):
                    user_id = bet.get('user_id')
                    amount = bet.get('amount')
                else:
                    user_id = bet[1] if len(bet) > 1 else None
                    amount = bet[3] if len(bet) > 3 else 0
                
                if user_id and amount and game_round.result:
                    if game_round.result > 1.0:
                        win_amount = int(amount * game_round.result)
                        await update_balance(user_id, win_amount)
                        
                        try:
                            await bot.send_message(
                                user_id,
                                f"🎉 <b>ربحت!</b>\n\n"
                                f"🎯 النتيجة: {game_round.result}x\n"
                                f"💰 الرهان: {amount}\n"
                                f"🏆 الربح: {win_amount}\n"
                                f"📈 رصيدك الجديد: {await get_balance(user_id)}"
                            )
                        except Exception as e:
                            logger.error(f"❌ خطأ في إرسال رسالة للمستخدم {user_id}: {e}")
            except Exception as e:
                logger.error(f"❌ خطأ في معالجة الرهان: {e}")
    except Exception as e:
        logger.error(f"❌ خطأ عام في معالجة الرهانات: {e}")

# ==================== إعداد Webhook ====================
async def setup_webhook():
    """تعيين Webhook للبوت"""
    try:
        webhook_url = f"{BASE_URL}/webhook"
        logger.info(f"🔗 محاولة تعيين Webhook على: {webhook_url}")
        
        await bot.delete_webhook()
        await bot.set_webhook(
            webhook_url,
            max_connections=100,
            allowed_updates=["message", "callback_query"]
        )
        
        logger.info(f"✅ تم تعيين Webhook بنجاح!")
        
        try:
            await bot.send_message(
                ADMIN_ID,
                f"🤖 <b>البوت يعمل بنجاح!</b>\n\n"
                f"🔗 الرابط: {BASE_URL}\n"
                f"🕐 الوقت: {datetime.now().strftime('%Y-%m-%d %H:%M')}"
            )
        except Exception as e:
            logger.warning(f"⚠️  لم يتم إرسال رسالة للأدمن: {e}")
        
        return True
        
    except Exception as e:
        logger.error(f"❌ خطأ في تعيين Webhook: {str(e)}")
        return False

# ==================== أوامر البوت ====================
@dp.message_handler(commands=["start", "play", "ابدأ"])
async def cmd_start(message: types.Message):
    """بدء البوت"""
    try:
        user_id = message.from_user.id
        username = message.from_user.first_name or "اللاعب"
        
        await create_user(user_id)
        
        # إذا كان الأدمن، نعطيه رصيد غير محدود
        if user_id == ADMIN_ID:
            await set_admin_unlimited_balance(ADMIN_ID)
        
        balance = await get_balance(user_id)
        
        game_url = f"{BASE_URL}/game?user_id={user_id}"
        
        keyboard = InlineKeyboardMarkup(row_width=2)
        keyboard.add(InlineKeyboardButton("🎮 ابدأ اللعب الآن", url=game_url))
        
        keyboard.row(
            InlineKeyboardButton("💰 معرفة الرصيد", callback_data="check_balance"),
            InlineKeyboardButton("📤 إرسال رصيد", callback_data="send_balance_menu")
        )
        
        welcome_text = f"""
🎉 <b>مرحباً {username}!</b> 

🎮 <b>لعبة Aviator - الرهان الحقيقي!</b>

💰 <b>رصيدك الحالي:</b> <code>{balance if user_id != ADMIN_ID else '∞ (غير محدود)'}</code> نقطة

📊 <b>معلومات النظام:</b>
• الجولة: {ROUND_DURATION} ثانية
• وقت الرهان: {BETTING_DURATION} ثانية
• خيارات الرهان: {', '.join(map(str, BET_OPTIONS))}

🎯 <b>كيف تلعب:</b>
1. اضغط على زر 'ابدأ اللعب'
2. اختر مبلغ الرهان
3. شاهد الطائرة تصعد
4. اربح حسب المضاعف!

<a href="{game_url}">🔗 اضغط هنا للعب</a>
        """
        
        await message.answer(welcome_text, reply_markup=keyboard)
        logger.info(f"📨 تم إرسال رسالة start للمستخدم {user_id}")
        
    except Exception as e:
        logger.error(f"❌ خطأ في أمر start: {e}")

@dp.message_handler(commands=["balance", "رصيدي", "رصيد"])
async def cmd_balance(message: types.Message):
    """عرض الرصيد"""
    try:
        user_id = message.from_user.id
        balance = await get_balance(user_id)
        
        balance_text = f"💰 <b>رصيدك الحالي:</b> <code>{balance if user_id != ADMIN_ID else '∞ (غير محدود)'}</code> نقطة"
        
        if user_id == ADMIN_ID:
            balance_text += "\n\n👑 <b>أنت الأدمن - رصيدك غير محدود</b>"
        
        await message.answer(balance_text)
        logger.info(f"💰 تم عرض الرصيد للمستخدم {user_id}")
        
    except Exception as e:
        logger.error(f"❌ خطأ في أمر balance: {e}")

@dp.message_handler(commands=["send", "ارسال", "تحويل"])
async def cmd_send(message: types.Message):
    """إرسال رصيد (نسخة جديدة)"""
    try:
        user_id = message.from_user.id
        parts = message.text.split()
        
        if len(parts) < 3:
            await message.answer(
                "📝 <b>طريقة الاستخدام:</b>\n"
                "<code>/send معرف_المستخدم المبلغ</code>\n\n"
                "📌 <b>مثال:</b>\n"
                "<code>/send 123456789 100</code>\n\n"
                "💡 <b>ملاحظة:</b>\n"
                "1. أدخل المعرف أولاً\n"
                "2. ثم أدخل المبلغ"
            )
            return
        
        try:
            to_user_id = int(parts[1])
            amount = int(parts[2])
        except (ValueError, IndexError):
            await message.answer("❌ خطأ في البيانات. تأكد من إدخال المعرف أولاً ثم المبلغ")
            return
        
        if amount <= 0:
            await message.answer("❌ المبلغ يجب أن يكون أكبر من صفر")
            return
        
        # الأدمن يمكنه الإرسال دائماً
        if user_id != ADMIN_ID:
            sender_balance = await get_balance(user_id)
            if sender_balance < amount:
                await message.answer(f"❌ رصيدك غير كافي. رصيدك: {sender_balance}")
                return
        
        if user_id == to_user_id:
            await message.answer("❌ لا يمكنك إرسال الرصيد لنفسك")
            return
        
        # الأدمن لا يخصم منه
        if user_id != ADMIN_ID:
            await update_balance(user_id, -amount)
        await update_balance(to_user_id, amount)
        
        await add_transaction(user_id, to_user_id, amount)
        
        await message.answer(
            f"✅ <b>تم إرسال الرصيد بنجاح</b>\n\n"
            f"👤 <b>إلى:</b> <code>{to_user_id}</code>\n"
            f"💰 <b>المبلغ:</b> <code>{amount}</code> نقطة\n"
            f"💳 <b>حالة الرصيد:</b> تمت العملية"
        )
        
        logger.info(f"📤 المستخدم {user_id} أرسل {amount} إلى {to_user_id}")
        
    except Exception as e:
        logger.error(f"❌ خطأ في أمر send: {e}")
        await message.answer("❌ حدث خطأ في إرسال الرصيد")

@dp.message_handler(commands=["add", "اضافة", "اعطاء"])
async def cmd_add(message: types.Message):
    """إضافة رصيد (للأدمن فقط)"""
    try:
        if message.from_user.id != ADMIN_ID:
            await message.answer("⛔ غير مصرح لك بهذا الأمر")
            return
        
        parts = message.text.split()
        if len(parts) < 3:
            await message.answer(
                "📝 <b>طريقة الاستخدام:</b>\n"
                "<code>/add معرف_المستخدم المبلغ</code>"
            )
            return
        
        try:
            user_id = int(parts[1])
            amount = int(parts[2])
        except (ValueError, IndexError):
            await message.answer("❌ خطأ في البيانات. تأكد من إدخال المعرف أولاً ثم المبلغ")
            return
        
        if amount <= 0:
            await message.answer("❌ المبلغ يجب أن يكون أكبر من صفر")
            return
        
        old_balance = await get_balance(user_id)
        new_balance = await update_balance(user_id, amount)
        
        await message.answer(
            f"✅ <b>تم إضافة الرصيد</b>\n\n"
            f"👤 <b>المستخدم:</b> <code>{user_id}</code>\n"
            f"➕ <b>المضاف:</b> <code>{amount}</code> نقطة\n"
            f"📊 <b>السابق:</b> <code>{old_balance}</code> نقطة\n"
            f"💰 <b>الجديد:</b> <code>{new_balance}</code> نقطة"
        )
        
        logger.info(f"➕ الأدمن أضف {amount} للمستخدم {user_id}")
        
    except Exception as e:
        logger.error(f"❌ خطأ في أمر add: {e}")
        await message.answer("❌ حدث خطأ في إضافة الرصيد")

@dp.message_handler(commands=["round", "جولة"])
async def cmd_round(message: types.Message):
    """معلومات الجولة الحالية"""
    try:
        now = datetime.now()
        
        if game_round.status == "waiting" or not game_round.round_id:
            await message.answer("⏳ <b>جاري إعداد الجولة القادمة...</b>")
            return
        
        time_left = game_round.remaining_time
        
        if game_round.status == "betting":
            betting_left = max(0, int((game_round.betting_end - now).total_seconds()))
            status_text = f"""
🔄 <b>الجولة #{game_round.round_id}</b>

⏰ <b>الحالة:</b> وقت الرهان
🕐 <b>متبقي للرهان:</b> {betting_left} ثانية
⏳ <b>متبقي للجولة:</b> {time_left} ثانية

🎯 <b>قواعد:</b>
• الرهان: خلال أول {BETTING_DURATION} ثانية
• النتيجة: بعد انتهاء وقت الرهان
• الرهانات: {', '.join(map(str, BET_OPTIONS))}
            """
        else:
            status_text = f"""
🎯 <b>الجولة #{game_round.round_id}</b>

⏰ <b>الحالة:</b> جارية
🎲 <b>النتيجة:</b> {game_round.result if game_round.result else 'قيد التحديد'}x
⏳ <b>متبقي:</b> {time_left} ثانية

📊 <b>المضاعف الحالي:</b> {game_round.result if game_round.result else '1.00'}x
            """
        
        await message.answer(status_text)
        
    except Exception as e:
        logger.error(f"❌ خطأ في أمر round: {e}")

@dp.message_handler(commands=["help", "مساعدة", "الاوامر"])
async def cmd_help(message: types.Message):
    """عرض المساعدة"""
    try:
        help_text = f"""
🎮 <b>أوامر لعبة Aviator</b>

📋 <b>الأوامر الأساسية:</b>
/start - بدء البوت وعرض رابط اللعبة
/balance - عرض رصيدك
/send معرف مبلغ - إرسال رصيد لمستخدم
/round - حالة الجولة الحالية
/help - عرض هذه القائمة

🎯 <b>لعبة الرهان:</b>
• اضغط /start للحصول على رابط اللعبة
• الجولة: {ROUND_DURATION} ثانية
• وقت الرهان: {BETTING_DURATION} ثانية
• خيارات الرهان: {', '.join(map(str, BET_OPTIONS))}

💰 <b>نظام الرصيد:</b>
• ابدأ برصيد 0
• إرسال واستقبال من الآخرين
• الأدمن رصيده غير محدود

⚙️ <b>أوامر الأدمن:</b>
/add معرف مبلغ - إضافة رصيد لمستخدم

📞 <b>الدعم:</b>
تواصل مع الأدمن للمساعدة
        """
        
        await message.answer(help_text)
        
    except Exception as e:
        logger.error(f"❌ خطأ في أمر help: {e}")

# ==================== معالجة Callback ====================
@dp.callback_query_handler(lambda c: c.data in ["check_balance", "send_balance_menu"])
async def process_callback(callback_query: types.CallbackQuery):
    """معالجة Callback"""
    try:
        user_id = callback_query.from_user.id
        
        if callback_query.data == "check_balance":
            balance = await get_balance(user_id)
            await bot.answer_callback_query(
                callback_query.id,
                f"💰 رصيدك: {balance if user_id != ADMIN_ID else '∞ (غير محدود)'} نقطة",
                show_alert=True
            )
            
        elif callback_query.data == "send_balance_menu":
            await bot.send_message(
                user_id,
                "📤 <b>لإرسال رصيد:</b>\n\n"
                "استخدم الأمر:\n<code>/send معرف_المستخدم المبلغ</code>\n\n"
                "<b>مثال:</b>\n<code>/send 123456789 500</code>\n\n"
                "⚠️ <b>ملاحظات:</b>\n"
                "1. أدخل المعرف أولاً\n"
                "2. ثم أدخل المبلغ\n"
                "3. تأكد من أن لديك رصيد كافي"
            )
            await bot.answer_callback_query(callback_query.id)
            
    except Exception as e:
        logger.error(f"❌ خطأ في معالجة callback: {e}")

# ==================== FastAPI Application ====================
@asynccontextmanager
async def lifespan(app: FastAPI):
    """إدارة دورة حياة التطبيق"""
    print("=" * 60)
    print("🚀 بدء تشغيل لعبة Aviator...")
    print("=" * 60)
    
    try:
        await init_db()
        
        # تعيين رصيد غير محدود للأدمن
        await set_admin_unlimited_balance(ADMIN_ID)
        
        await setup_webhook()
        
        # بدء نظام الجولات
        asyncio.create_task(process_round())
        
        print(f"\n📊 معلومات التشغيل:")
        print(f"🔗 الرابط: {BASE_URL}")
        print(f"🤖 البوت: {BOT_TOKEN[:15]}...")
        print(f"👑 الأدمن: {ADMIN_ID} (رصيد غير محدود)")
        print(f"⏳ مدة الجولة: {ROUND_DURATION} ثانية")
        print(f"⏰ وقت الرهان: {BETTING_DURATION} ثانية")
        print(f"💰 خيارات الرهان: {BET_OPTIONS}")
        print("=" * 60)
        print("✅ التطبيق يعمل بنجاح وجاهز للاستخدام!")
        print("=" * 60)
        
        yield
        
    except Exception as e:
        logger.error(f"❌ خطأ فادح في التشغيل: {e}")
        raise
    
    finally:
        print("\n🛑 إيقاف التطبيق...")

app = FastAPI(
    title="Aviator Game",
    description="لعبة رهان Aviator مع نظام جولات متكامل",
    version="3.0.0",
    lifespan=lifespan
)

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
        Bot.set_current(bot)
        update_data = await request.json()
        await dp.process_update(types.Update(**update_data))
        return {"ok": True}
    except Exception as e:
        logger.error(f"❌ خطأ في Webhook: {e}")
        return {"ok": False, "error": str(e)}, 500

# ==================== API Endpoints ====================
@app.get("/")
async def home():
    """الصفحة الرئيسية"""
    return {
        "app": "Aviator Game v3.0",
        "status": "running",
        "round": game_round.round_id,
        "round_status": game_round.status,
        "result": game_round.result,
        "admin_id": ADMIN_ID
    }

@app.get("/game")
async def game_page(request: Request):
    """صفحة اللعبة"""
    user_id = request.query_params.get("user_id", "0")
    
    try:
        with open("index.html", "r", encoding="utf-8") as f:
            html_content = f.read()
    except FileNotFoundError:
        return HTMLResponse("<h1>🎮 Aviator Game</h1><p>ملف اللعبة غير موجود</p>")
    
    html_content = html_content.replace("{BASE_URL}", BASE_URL)
    html_content = html_content.replace("{USER_ID}", str(user_id))
    html_content = html_content.replace("{BET_OPTIONS}", str(BET_OPTIONS))
    html_content = html_content.replace("{ROUND_DURATION}", str(ROUND_DURATION))
    html_content = html_content.replace("{BETTING_DURATION}", str(BETTING_DURATION))
    
    return HTMLResponse(content=html_content)

@app.get("/api/round")
async def api_round():
    """معلومات الجولة الحالية"""
    now = datetime.now()
    
    response = {
        "round_id": game_round.round_id,
        "status": game_round.status,
        "result": game_round.result,
        "remaining_time": game_round.remaining_time,
        "betting_time_left": max(0, int((game_round.betting_end - now).total_seconds())) if game_round.betting_end else 0,
        "can_bet": game_round.status == "betting" and game_round.betting_end and now < game_round.betting_end
    }
    
    return response

@app.get("/api/balance/{user_id}")
async def api_balance(user_id: int):
    """جلب الرصيد"""
    try:
        balance = await get_balance(user_id)
        return {"balance": balance, "is_admin": user_id == ADMIN_ID}
    except Exception as e:
        return {"balance": 0, "error": str(e)}

@app.post("/api/bet")
async def api_bet(request: Request):
    """وضع رهان"""
    try:
        data = await request.json()
        user_id = int(data.get("user_id", 0))
        amount = int(data.get("amount", 0))
        
        if not user_id or not amount:
            return {"error": "بيانات ناقصة"}, 400
        
        if amount not in BET_OPTIONS:
            return {"error": "مبلغ رهان غير صالح"}, 400
        
        # الأدمن يمكنه الرهان دائماً
        if user_id != ADMIN_ID:
            balance = await get_balance(user_id)
            if balance < amount:
                return {"error": "رصيد غير كافي", "balance": balance}, 400
        
        # التحقق من وقت الرهان
        now = datetime.now()
        if game_round.status != "betting" or not game_round.betting_end or now >= game_round.betting_end:
            return {"error": "ليس وقت الرهان الآن"}, 400
        
        if user_id != ADMIN_ID:
            await update_balance(user_id, -amount)
        
        await add_bet(user_id, game_round.round_id, amount, "auto")
        
        return {
            "success": True,
            "message": f"تم وضع رهان {amount}",
            "round_id": game_round.round_id
        }
        
    except Exception as e:
        return {"error": str(e)}, 500

# ==================== نقطة الدخول ====================
if __name__ == "__main__":
    uvicorn.run(app, host="0.0.0.0", port=PORT)