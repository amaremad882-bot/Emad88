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
from aiogram.utils.exceptions import TelegramAPIError

# ==================== إعداد التسجيل (Logging) ====================
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
storage = MemoryStorage()
dp = Dispatcher(bot, storage=storage)

# ==================== قاعدة البيانات ====================
try:
    from database import (
        init_db, get_balance, update_balance, create_user,
        add_transaction, get_user_transactions,
        create_round, add_bet, get_current_round,
        get_round_bets, finish_round, update_round_result
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
        
        logger.info(f"🔄 بدأت الجولة #{game_round.round_id}")
        logger.info(f"⏰ وقت الرهان حتى: {game_round.betting_end}")
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
                
                if user_id and amount:
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
        
        # أولاً، حذف أي Webhook سابق
        delete_url = f"https://api.telegram.org/bot{BOT_TOKEN}/deleteWebhook"
        async with aiohttp.ClientSession() as session:
            async with session.get(delete_url) as response:
                delete_data = await response.json()
                if delete_data.get("ok"):
                    logger.info("✅ تم حذف Webhook السابق")
                else:
                    logger.warning("⚠️  لم يتم حذف Webhook سابق")
        
        # ثانياً، تعيين Webhook جديد
        async with aiohttp.ClientSession() as session:
            async with session.post(
                f"https://api.telegram.org/bot{BOT_TOKEN}/setWebhook",
                json={
                    "url": webhook_url,
                    "max_connections": 100,
                    "allowed_updates": ["message", "callback_query", "inline_query"]
                }
            ) as response:
                data = await response.json()
                if data.get("ok"):
                    logger.info(f"✅ تم تعيين Webhook بنجاح!")
                    
                    # التحقق من معلومات Webhook
                    info_url = f"https://api.telegram.org/bot{BOT_TOKEN}/getWebhookInfo"
                    async with session.get(info_url) as info_resp:
                        info_data = await info_resp.json()
                        if info_data.get("ok"):
                            webhook_info = info_data.get("result", {})
                            logger.info(f"📊 معلومات Webhook: {webhook_info.get('url')}")
                    
                    # إرسال رسالة تأكيد للأدمن
                    try:
                        await bot.send_message(
                            ADMIN_ID,
                            f"🤖 <b>البوت يعمل بنجاح!</b>\n\n"
                            f"🔗 الرابط: {BASE_URL}\n"
                            f"🕐 الوقت: {datetime.now().strftime('%Y-%m-%d %H:%M')}\n"
                            f"🎮 الجولة الحالية: #{game_round.round_id or 'لا يوجد'}"
                        )
                        logger.info(f"✅ تم إرسال رسالة تأكيد للأدمن {ADMIN_ID}")
                    except Exception as e:
                        logger.warning(f"⚠️  لم يتم إرسال رسالة للأدمن: {e}")
                    
                    return True
                else:
                    logger.error(f"❌ فشل تعيين Webhook: {data.get('description')}")
                    return False
    except Exception as e:
        logger.error(f"❌ خطأ في تعيين Webhook: {str(e)}")
        return False

# ==================== اختبار البوت ====================
async def test_bot_connection():
    """اختبار اتصال البوت"""
    try:
        me = await bot.get_me()
        logger.info(f"✅ البوت متصل: @{me.username} (ID: {me.id})")
        return True
    except Exception as e:
        logger.error(f"❌ فشل اتصال البوت: {e}")
        return False

# ==================== أوامر البوت ====================
@dp.message_handler(commands=["start", "play", "ابدأ"])
async def cmd_start(message: types.Message):
    """بدء البوت"""
    try:
        user_id = message.from_user.id
        username = message.from_user.first_name or "اللاعب"
        
        await create_user(user_id)
        balance = await get_balance(user_id)
        
        game_url = f"{BASE_URL}/game?user_id={user_id}"
        
        keyboard = InlineKeyboardMarkup(row_width=2)
        keyboard.add(InlineKeyboardButton("🎮 ابدأ اللعب الآن", url=game_url))
        
        keyboard.row(
            InlineKeyboardButton("💰 معرفة الرصيد", callback_data="check_balance"),
            InlineKeyboardButton("📤 إرسال رصيد", callback_data="send_balance")
        )
        
        welcome_text = f"""
🎉 <b>مرحباً {username}!</b> 

🎮 <b>لعبة Aviator - الرهان الحقيقي!</b>

💰 <b>رصيدك الحالي:</b> <code>{balance}</code> نقطة

📊 <b>معلومات النظام:</b>
• الجولة: 60 ثانية
• وقت الرهان: 30 ثانية
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
        
        await message.answer(f"💰 <b>رصيدك الحالي:</b> <code>{balance}</code> نقطة")
        logger.info(f"💰 تم عرض الرصيد للمستخدم {user_id}: {balance}")
        
    except Exception as e:
        logger.error(f"❌ خطأ في أمر balance: {e}")
        await message.answer("❌ حدث خطأ في جلب الرصيد")

@dp.message_handler(commands=["send", "ارسال", "تحويل"])
async def cmd_send(message: types.Message):
    """إرسال رصيد"""
    try:
        user_id = message.from_user.id
        parts = message.text.split()
        
        if len(parts) != 3:
            await message.answer(
                "📝 <b>طريقة الاستخدام:</b>\n"
                "<code>/send معرف_المستخدم المبلغ</code>\n\n"
                "📌 <b>مثال:</b>\n"
                "<code>/send 123456789 100</code>"
            )
            return
        
        to_user_id = int(parts[1])
        amount = int(parts[2])
        
        if amount <= 0:
            await message.answer("❌ المبلغ يجب أن يكون أكبر من صفر")
            return
        
        sender_balance = await get_balance(user_id)
        if sender_balance < amount:
            await message.answer(f"❌ رصيدك غير كافي. رصيدك: {sender_balance}")
            return
        
        if user_id == to_user_id:
            await message.answer("❌ لا يمكنك إرسال الرصيد لنفسك")
            return
        
        await update_balance(user_id, -amount)
        await update_balance(to_user_id, amount)
        await add_transaction(user_id, to_user_id, amount)
        
        new_balance = await get_balance(user_id)
        
        await message.answer(
            f"✅ <b>تم إرسال الرصيد بنجاح</b>\n\n"
            f"👤 <b>إلى:</b> <code>{to_user_id}</code>\n"
            f"💰 <b>المبلغ:</b> <code>{amount}</code> نقطة\n"
            f"💳 <b>رصيدك الآن:</b> <code>{new_balance}</code> نقطة"
        )
        
        logger.info(f"📤 المستخدم {user_id} أرسل {amount} إلى {to_user_id}")
        
    except ValueError:
        await message.answer("❌ خطأ في البيانات. تأكد من إدخال أرقام صحيحة")
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
        if len(parts) != 3:
            await message.answer(
                "📝 <b>طريقة الاستخدام:</b>\n"
                "<code>/add معرف_المستخدم المبلغ</code>"
            )
            return
        
        user_id = int(parts[1])
        amount = int(parts[2])
        
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

@dp.message_handler(commands=["help", "مساعدة", "الاوامر"])
async def cmd_help(message: types.Message):
    """عرض المساعدة"""
    try:
        help_text = """
🎮 <b>أوامر لعبة Aviator</b>

📋 <b>الأوامر الأساسية:</b>
/start - بدء البوت وعرض رابط اللعبة
/balance - عرض رصيدك
/send معرف مبلغ - إرسال رصيد لمستخدم
/help - عرض هذه القائمة

🎯 <b>لعبة الرهان:</b>
• اضغط /start للحصول على رابط اللعبة
• اختر مبلغ الرهان من القائمة
• شاهد الطائرة تصعد
• اربح حسب المضاعف

💰 <b>نظام الرصيد:</b>
• ابدأ برصيد 0
• إرسال واستقبال من الآخرين
• الأدمن يمكنه إضافة رصيد

⚙️ <b>أوامر الأدمن:</b>
/add معرف مبلغ - إضافة رصيد لمستخدم

📞 <b>الدعم:</b>
تواصل مع الأدمن للمساعدة
        """
        
        await message.answer(help_text)
        logger.info(f"📖 تم عرض المساعدة للمستخدم {message.from_user.id}")
        
    except Exception as e:
        logger.error(f"❌ خطأ في أمر help: {e}")

# ==================== معالجة Callback ====================
@dp.callback_query_handler(lambda c: c.data in ["check_balance", "send_balance"])
async def process_callback(callback_query: types.CallbackQuery):
    """معالجة Callback"""
    try:
        user_id = callback_query.from_user.id
        
        if callback_query.data == "check_balance":
            balance = await get_balance(user_id)
            await bot.answer_callback_query(
                callback_query.id,
                f"💰 رصيدك: {balance} نقطة",
                show_alert=True
            )
            logger.info(f"💰 تحقق من الرصيد للمستخدم {user_id}: {balance}")
            
        elif callback_query.data == "send_balance":
            await bot.send_message(
                user_id,
                "📤 <b>لإرسال رصيد:</b>\n\n"
                "استخدم الأمر:\n<code>/send معرف_المستخدم المبلغ</code>\n\n"
                "<b>مثال:</b>\n<code>/send 123456789 500</code>\n\n"
                "⚠️ <b>تأكد من:</b>\n"
                "1. معرف المستخدم صحيح\n"
                "2. لديك رصيد كافي\n"
                "3. المبلغ أكبر من صفر"
            )
            await bot.answer_callback_query(callback_query.id)
            logger.info(f"📤 طلب إرسال رصيد من المستخدم {user_id}")
            
    except Exception as e:
        logger.error(f"❌ خطأ في معالجة callback: {e}")

# ==================== معالجة الرسائل العامة ====================
@dp.message_handler()
async def handle_all_messages(message: types.Message):
    """معالجة جميع الرسائل الأخرى"""
    try:
        if message.text:
            user_id = message.from_user.id
            text = message.text
            
            # تجاهل الرسائل الطويلة أو الروابط
            if len(text) < 100 and not text.startswith("http"):
                # إذا كانت رسالة نصية عادية، نرد برسالة ترحيب
                if not text.startswith("/"):
                    await message.answer(
                        f"👋 مرحباً!\n\n"
                        f"أرسل /start لبدء اللعبة\n"
                        f"أو /help لعرض الأوامر"
                    )
                    logger.info(f"📨 رد على رسالة عادية من {user_id}")
                    
    except Exception as e:
        logger.error(f"❌ خطأ في معالجة الرسالة: {e}")

# ==================== FastAPI Application ====================
@asynccontextmanager
async def lifespan(app: FastAPI):
    """إدارة دورة حياة التطبيق"""
    # عند البدء
    print("=" * 60)
    print("🚀 بدء تشغيل لعبة Aviator...")
    print("=" * 60)
    
    try:
        # اختبار اتصال البوت
        logger.info("🤖 اختبار اتصال البوت...")
        if not await test_bot_connection():
            logger.error("❌ فشل اتصال البوت!")
            raise Exception("فشل اتصال البوت")
        
        # تهيئة قاعدة البيانات
        logger.info("🗄️ تهيئة قاعدة البيانات...")
        await init_db()
        logger.info("✅ قاعدة البيانات جاهزة")
        
        # إعداد Webhook
        logger.info("🔧 إعداد Webhook...")
        if not await setup_webhook():
            logger.error("❌ فشل إعداد Webhook!")
            raise Exception("فشل إعداد Webhook")
        
        # بدء نظام الجولات
        logger.info("🎮 بدء نظام الجولات...")
        asyncio.create_task(process_round())
        
        # معلومات التشغيل
        print(f"\n📊 معلومات التشغيل:")
        print(f"🔗 الرابط: {BASE_URL}")
        print(f"🤖 البوت: {BOT_TOKEN[:15]}...")
        print(f"👑 الأدمن: {ADMIN_ID}")
        print(f"⏳ مدة الجولة: {ROUND_DURATION} ثانية")
        print(f"⏰ وقت الرهان: {BETTING_DURATION} ثانية")
        print(f"💰 خيارات الرهان: {BET_OPTIONS}")
        print("=" * 60)
        print("✅ التطبيق يعمل بنجاح وجاهز للاستخدام!")
        print("=" * 60)
        
        yield
        
    except Exception as e:
        logger.error(f"❌ خطأ فادح في التشغيل: {e}")
        print(f"\n❌ خطأ فادح: {e}")
        raise
    
    finally:
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
        update_data = await request.json()
        logger.info(f"📨 استقبال Webhook: {update_data.keys()}")
        
        update = types.Update(**update_data)
        await dp.process_update(update)
        
        return {"ok": True, "message": "تم استلام التحديث بنجاح"}
        
    except Exception as e:
        logger.error(f"❌ خطأ في Webhook: {str(e)}")
        return {"ok": False, "error": str(e)}, 500

# ==================== API Endpoints ====================
@app.get("/")
async def home():
    """الصفحة الرئيسية"""
    return {
        "app": "Aviator Game v2.0",
        "status": "running",
        "bot": "active" if bot else "inactive",
        "round": game_round.round_id,
        "admin": ADMIN_ID,
        "timestamp": datetime.now().isoformat()
    }

@app.get("/health")
async def health_check():
    """فحص صحة الخادم"""
    try:
        # اختبار اتصال البوت
        me = await bot.get_me()
        
        return {
            "status": "healthy",
            "bot": me.username,
            "webhook": "active",
            "database": "connected",
            "timestamp": datetime.now().isoformat()
        }
    except Exception as e:
        return {
            "status": "unhealthy",
            "error": str(e),
            "timestamp": datetime.now().isoformat()
        }, 500

@app.get("/game")
async def game_page(request: Request):
    """صفحة اللعبة"""
    try:
        user_id = request.query_params.get("user_id", "0")
        
        with open("index.html", "r", encoding="utf-8") as f:
            html_content = f.read()
        
        html_content = html_content.replace("{BASE_URL}", BASE_URL)
        html_content = html_content.replace("{USER_ID}", str(user_id))
        html_content = html_content.replace("{BET_OPTIONS}", str(BET_OPTIONS))
        
        logger.info(f"🎮 تحميل صفحة اللعبة للمستخدم {user_id}")
        
        return HTMLResponse(content=html_content)
        
    except FileNotFoundError:
        return HTMLResponse("<h1>❌ ملف اللعبة غير موجود</h1>")
    except Exception as e:
        logger.error(f"❌ خطأ في صفحة اللعبة: {e}")
        return HTMLResponse(f"<h1>❌ خطأ في تحميل اللعبة: {e}</h1>")

# ==================== نقطة الدخول ====================
if __name__ == "__main__":
    logger.info(f"🌍 تشغيل السيرفر على المنفذ {PORT}")
    
    uvicorn.run(
        app,
        host="0.0.0.0",
        port=PORT,
        log_level="info"
    )