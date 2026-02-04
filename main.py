import os
import asyncio
import random
import asyncpg
from fastapi import FastAPI, Request, HTTPException
from fastapi.responses import HTMLResponse, JSONResponse
from fastapi.staticfiles import StaticFiles
from fastapi.middleware.cors import CORSMiddleware
import uvicorn
from aiogram import Bot, Dispatcher, types
from aiogram.types import InlineKeyboardMarkup, InlineKeyboardButton
from aiogram.utils import executor
from aiogram.contrib.fsm_storage.memory import MemoryStorage
from contextlib import asynccontextmanager

# ==================== الإعدادات ====================
from config import BOT_TOKEN, ADMIN_ID, DEFAULT_BALANCE, BET_AMOUNT, PORT

# ==================== إعداد FastAPI ====================
app = FastAPI(title="Aviator Game API")

# إعدادات CORS
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# ==================== إعداد البوت ====================
bot = Bot(token=BOT_TOKEN)
storage = MemoryStorage()
dp = Dispatcher(bot, storage=storage)

# ==================== قاعدة البيانات ====================
from database import init_db, get_balance, update_balance, create_user

# ==================== إعدادات Railway ====================
# الحصول على الرابط التلقائي من Railway
RAILWAY_PUBLIC_DOMAIN = os.environ.get('RAILWAY_PUBLIC_DOMAIN', '')
RAILWAY_STATIC_URL = os.environ.get('RAILWAY_STATIC_URL', '')

if RAILWAY_STATIC_URL:
    BASE_URL = RAILWAY_STATIC_URL
elif RAILWAY_PUBLIC_DOMAIN:
    BASE_URL = f"https://{RAILWAY_PUBLIC_DOMAIN}"
else:
    BASE_URL = f"http://localhost:{PORT}"

# ==================== أوامر البوت ====================
@dp.message_handler(commands=["start", "help"])
async def cmd_start(message: types.Message):
    user_id = message.from_user.id
    balance = await get_balance(user_id)
    
    # إنشاء زر اللعبة
    game_url = f"{BASE_URL}/game?user_id={user_id}"
    keyboard = InlineKeyboardMarkup()
    keyboard.add(InlineKeyboardButton("🎮 ابدأ اللعبة 🎮", url=game_url))
    
    await message.answer(
        f"🎉 **مرحباً بك في لعبة Aviator!**\n\n"
        f"💰 **رصيدك الحالي:** {balance} نقطة\n\n"
        f"📖 **قواعد اللعبة:**\n"
        f"• اختر 'فوق' إذا كنت تعتقد أن الرقم سيكون أكبر من 50\n"
        f"• اختر 'تحت' إذا كنت تعتقد أن الرقم سيكون أقل من 50\n"
        f"• الرهان: {BET_AMOUNT} نقطة\n"
        f"• الفوز: تحصل على {BET_AMOUNT * 2} نقطة\n\n"
        f"اضغط على الزر أدناه للعب!",
        reply_markup=keyboard,
        parse_mode="Markdown"
    )

@dp.message_handler(commands=["balance"])
async def cmd_balance(message: types.Message):
    user_id = message.from_user.id
    balance = await get_balance(user_id)
    await message.answer(f"💰 **رصيدك الحالي:** {balance} نقطة", parse_mode="Markdown")

@dp.message_handler(commands=["add_points"])
async def cmd_add_points(message: types.Message):
    if message.from_user.id != ADMIN_ID:
        await message.answer("⛔ **غير مصرح لك بهذا الأمر**", parse_mode="Markdown")
        return
    
    try:
        parts = message.text.split()
        if len(parts) != 3:
            await message.answer("📝 **استخدام:** `/add_points <user_id> <points>`", parse_mode="Markdown")
            return
        
        user_id = int(parts[1])
        points = int(parts[2])
        
        current = await get_balance(user_id)
        new_balance = await update_balance(user_id, points)
        
        await message.answer(
            f"✅ **تم تحديث الرصيد**\n"
            f"👤 المستخدم: `{user_id}`\n"
            f"➕ النقاط المضافة: `{points}`\n"
            f"💰 الرصيد السابق: `{current}`\n"
            f"💰 الرصيد الجديد: `{new_balance}`",
            parse_mode="Markdown"
        )
    except Exception as e:
        await message.answer(f"❌ **خطأ:** `{str(e)}`", parse_mode="Markdown")

@dp.message_handler(commands=["stats"])
async def cmd_stats(message: types.Message):
    if message.from_user.id != ADMIN_ID:
        await message.answer("⛔ **غير مصرح لك بهذا الأمر**", parse_mode="Markdown")
        return
    
    try:
        from database import get_stats
        stats = await get_stats()
        await message.answer(
            f"📊 **إحصائيات اللعبة**\n\n"
            f"👥 عدد اللاعبين: `{stats['total_users']}`\n"
            f"💰 مجموع النقاط: `{stats['total_points']}`\n"
            f"📈 أعلى رصيد: `{stats['max_balance']}`\n"
            f"📉 أقل رصيد: `{stats['min_balance']}`",
            parse_mode="Markdown"
        )
    except Exception as e:
        await message.answer(f"❌ **خطأ:** `{str(e)}`", parse_mode="Markdown")

# ==================== واجهات FastAPI ====================
# الصفحة الرئيسية
@app.get("/")
async def home():
    return {"message": "Aviator Game API", "status": "running", "docs": "/docs"}

# صفحة اللعبة
@app.get("/game", response_class=HTMLResponse)
async def game_page(request: Request):
    user_id = request.query_params.get("user_id", "0")
    
    html_content = f"""
    <!DOCTYPE html>
    <html lang="ar" dir="rtl">
    <head>
        <meta charset="UTF-8">
        <meta name="viewport" content="width=device-width, initial-scale=1.0">
        <title>لعبة Aviator</title>
        <script>
            const USER_ID = {user_id};
            const BASE_URL = "{BASE_URL}";
        </script>
        <style>
            body {{
                margin: 0;
                padding: 20px;
                font-family: 'Segoe UI', Tahoma, Geneva, Verdana, sans-serif;
                background: linear-gradient(135deg, #667eea 0%, #764ba2 100%);
                min-height: 100vh;
                color: white;
            }}
            
            .container {{
                max-width: 500px;
                margin: 0 auto;
                background: rgba(255, 255, 255, 0.1);
                backdrop-filter: blur(10px);
                border-radius: 20px;
                padding: 20px;
                box-shadow: 0 10px 30px rgba(0,0,0,0.3);
            }}
            
            .header {{
                display: flex;
                justify-content: space-between;
                align-items: center;
                margin-bottom: 30px;
                padding-bottom: 15px;
                border-bottom: 2px solid rgba(255,255,255,0.2);
            }}
            
            .balance {{
                background: linear-gradient(45deg, #FFD700, #FFA500);
                padding: 10px 20px;
                border-radius: 25px;
                font-weight: bold;
                color: #333;
                font-size: 18px;
            }}
            
            .game-area {{
                position: relative;
                height: 300px;
                background: rgba(0, 0, 0, 0.3);
                border-radius: 15px;
                margin: 20px 0;
                overflow: hidden;
            }}
            
            .line {{
                position: absolute;
                top: 50%;
                left: 0;
                right: 0;
                height: 3px;
                background: #FFD700;
                transform: translateY(-50%);
                z-index: 1;
            }}
            
            #plane {{
                position: absolute;
                top: 50%;
                left: 20px;
                font-size: 40px;
                transition: all 1.5s ease-in-out;
                transform: translateY(-50%);
                z-index: 2;
            }}
            
            #result {{
                position: absolute;
                top: 50%;
                left: 50%;
                transform: translate(-50%, -50%);
                font-size: 48px;
                font-weight: bold;
                opacity: 0;
                transition: opacity 0.5s;
                z-index: 3;
            }}
            
            .controls {{
                display: grid;
                grid-template-columns: 1fr 1fr;
                gap: 15px;
                margin: 20px 0;
            }}
            
            .btn {{
                padding: 20px;
                border: none;
                border-radius: 15px;
                font-size: 18px;
                font-weight: bold;
                cursor: pointer;
                transition: all 0.3s;
                color: white;
                text-align: center;
            }}
            
            .btn-up {{
                background: linear-gradient(45deg, #00b09b, #96c93d);
            }}
            
            .btn-down {{
                background: linear-gradient(45deg, #FF416C, #FF4B2B);
            }}
            
            .btn:disabled {{
                opacity: 0.5;
                cursor: not-allowed;
            }}
            
            .btn:hover:not(:disabled) {{
                transform: translateY(-3px);
                box-shadow: 0 5px 15px rgba(0,0,0,0.3);
            }}
            
            .message {{
                text-align: center;
                margin: 15px 0;
                font-size: 18px;
                min-height: 27px;
                font-weight: bold;
            }}
            
            .win {{ color: #00ff88; }}
            .lose {{ color: #ff4444; }}
            
            .loading {{
                display: none;
                text-align: center;
                margin: 20px 0;
                font-size: 18px;
            }}
            
            .instructions {{
                background: rgba(255,255,255,0.1);
                padding: 15px;
                border-radius: 10px;
                margin-top: 20px;
                font-size: 14px;
                line-height: 1.6;
            }}
        </style>
    </head>
    <body>
        <div class="container">
            <div class="header">
                <div>
                    <h2 style="margin:0;">✈️ لعبة Aviator</h2>
                    <small>ID: {user_id}</small>
                </div>
                <div class="balance" id="balance">جاري التحميل...</div>
            </div>
            
            <div class="game-area">
                <div class="line"></div>
                <div id="plane">✈️</div>
                <div id="result"></div>
            </div>
            
            <div class="message" id="message"></div>
            
            <div class="controls">
                <button class="btn btn-up" onclick="playGame('UP')" id="btn-up">
                    فوق ⬆️<br><small>أكبر من 50</small>
                </button>
                <button class="btn btn-down" onclick="playGame('DOWN')" id="btn-down">
                    تحت ⬇️<br><small>أقل من 50</small>
                </button>
            </div>
            
            <div class="loading" id="loading">جاري المعالجة...</div>
            
            <div class="instructions">
                <strong>📖 التعليمات:</strong>
                <ul style="margin:10px 0; padding-right:20px;">
                    <li>اختر "فوق" إذا كنت تعتقد أن الرقم سيكون أكبر من 50</li>
                    <li>اختر "تحت" إذا كنت تعتقد أن الرقم سيكون أقل من 50</li>
                    <li>الرهان: {BET_AMOUNT} نقطة</li>
                    <li>عند الفوز: تحصل على {BET_AMOUNT * 2} نقطة</li>
                    <li>عند الخسارة: تخسر {BET_AMOUNT} نقطة</li>
                </ul>
            </div>
        </div>
        
        <script>
            let isPlaying = false;
            let userBalance = 0;
            
            // جلب الرصيد
            async function loadBalance() {{
                try {{
                    const response = await fetch(`${{BASE_URL}}/api/balance/${{USER_ID}}`);
                    const data = await response.json();
                    userBalance = data.balance;
                    document.getElementById('balance').textContent = userBalance + ' 💰';
                }} catch (error) {{
                    console.error('خطأ في جلب الرصيد:', error);
                    document.getElementById('balance').textContent = 'خطأ في الاتصال';
                }}
            }}
            
            // تشغيل اللعبة
            async function playGame(choice) {{
                if (isPlaying) return;
                
                // تعطيل الأزرار
                isPlaying = true;
                document.getElementById('btn-up').disabled = true;
                document.getElementById('btn-down').disabled = true;
                document.getElementById('message').textContent = '';
                document.getElementById('loading').style.display = 'block';
                
                const plane = document.getElementById('plane');
                const resultDiv = document.getElementById('result');
                
                // إعادة تعيين الطائرة
                plane.style.top = '50%';
                plane.style.transform = 'translateY(-50%) rotate(0deg)';
                resultDiv.style.opacity = '0';
                
                try {{
                    // إرسال طلب اللعب
                    const response = await fetch(`${{BASE_URL}}/api/play`, {{
                        method: 'POST',
                        headers: {{ 'Content-Type': 'application/json' }},
                        body: JSON.stringify({{
                            user_id: USER_ID,
                            choice: choice
                        }})
                    }});
                    
                    const data = await response.json();
                    
                    if (data.error) {{
                        document.getElementById('message').textContent = '❌ ' + data.error;
                        document.getElementById('message').className = 'message lose';
                        isPlaying = false;
                        document.getElementById('btn-up').disabled = false;
                        document.getElementById('btn-down').disabled = false;
                        document.getElementById('loading').style.display = 'none';
                        return;
                    }}
                    
                    // حركة الطائرة
                    const visualPosition = 90 - (data.result * 0.8);
                    plane.style.top = visualPosition + '%';
                    
                    if (data.result > 50) {{
                        plane.style.transform = 'translateY(-50%) rotate(-20deg)';
                    }} else {{
                        plane.style.transform = 'translateY(-50%) rotate(20deg)';
                    }}
                    
                    // عرض النتيجة بعد التأخير
                    setTimeout(() => {{
                        // تحديث الرصيد
                        loadBalance();
                        
                        // عرض النتيجة
                        resultDiv.textContent = data.result.toFixed(2);
                        resultDiv.style.color = data.win ? '#00ff88' : '#ff4444';
                        resultDiv.style.opacity = '1';
                        
                        // عرض الرسالة
                        document.getElementById('message').textContent = data.win ? '🎉 ربحت!' : '😢 خسرت';
                        document.getElementById('message').className = 'message ' + (data.win ? 'win' : 'lose');
                        
                        // إعادة تمكين الأزرار
                        isPlaying = false;
                        document.getElementById('btn-up').disabled = false;
                        document.getElementById('btn-down').disabled = false;
                        document.getElementById('loading').style.display = 'none';
                        
                        // تأثير اهتزاز
                        if (data.win) {{
                            document.querySelector('.game-area').style.animation = 'winShake 0.5s';
                        }} else {{
                            document.querySelector('.game-area').style.animation = 'loseShake 0.5s';
                        }}
                        
                        setTimeout(() => {{
                            document.querySelector('.game-area').style.animation = '';
                        }}, 500);
                        
                    }}, 1500);
                    
                }} catch (error) {{
                    console.error('خطأ:', error);
                    document.getElementById('message').textContent = '❌ خطأ في الاتصال بالخادم';
                    document.getElementById('message').className = 'message lose';
                    isPlaying = false;
                    document.getElementById('btn-up').disabled = false;
                    document.getElementById('btn-down').disabled = false;
                    document.getElementById('loading').style.display = 'none';
                }}
            }}
            
            // تحميل الرصيد عند البدء
            window.onload = loadBalance;
            
            // تأثيرات CSS
            const style = document.createElement('style');
            style.textContent = `
                @keyframes winShake {{
                    0% {{ transform: translateX(0); }}
                    25% {{ transform: translateX(-5px); }}
                    50% {{ transform: translateX(5px); }}
                    75% {{ transform: translateX(-5px); }}
                    100% {{ transform: translateX(0); }}
                }}
                
                @keyframes loseShake {{
                    0% {{ transform: translateY(0); }}
                    25% {{ transform: translateY(-5px); }}
                    50% {{ transform: translateY(5px); }}
                    75% {{ transform: translateY(-5px); }}
                    100% {{ transform: translateY(0); }}
                }}
            `;
            document.head.appendChild(style);
        </script>
    </body>
    </html>
    """
    
    return HTMLResponse(content=html_content)

# API لجلب الرصيد
@app.get("/api/balance/{user_id}")
async def api_balance(user_id: int):
    try:
        balance = await get_balance(user_id)
        return JSONResponse(content={"balance": balance})
    except Exception as e:
        return JSONResponse(content={"error": str(e)}, status_code=500)

# API للعب
@app.post("/api/play")
async def api_play(request: Request):
    try:
        data = await request.json()
        user_id = int(data.get("user_id", 0))
        choice = data.get("choice", "").upper()
        
        if not user_id:
            return JSONResponse(content={"error": "معرف المستخدم مطلوب"}, status_code=400)
        
        if choice not in ["UP", "DOWN"]:
            return JSONResponse(content={"error": "الاختيار يجب أن يكون UP أو DOWN"}, status_code=400)
        
        # التحقق من الرصيد
        current_balance = await get_balance(user_id)
        if current_balance < BET_AMOUNT:
            return JSONResponse(content={
                "error": f"رصيدك غير كافٍ. الرصيد الحالي: {current_balance}، المطلوب: {BET_AMOUNT}"
            }, status_code=400)
        
        # توليد النتيجة
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
        return JSONResponse(content={"error": str(e)}, status_code=500)

# ==================== تشغيل البوت ====================
async def start_bot():
    """تشغيل البوت في الخلفية"""
    print("🤖 بدء تشغيل البوت...")
    await dp.skip_updates()
    await dp.start_polling()

# ==================== حدث بدء التشغيل ====================
@app.on_event("startup")
async def startup_event():
    """تهيئة التطبيق عند البدء"""
    print("🚀 بدء تشغيل تطبيق Aviator Game...")
    
    # تهيئة قاعدة البيانات
    await init_db()
    
    # بدء البوت في الخلفية
    import threading
    bot_thread = threading.Thread(target=lambda: asyncio.run(start_bot()))
    bot_thread.daemon = True
    bot_thread.start()
    
    print(f"✅ التطبيق يعمل على: {BASE_URL}")
    print(f"🤖 البوت يعمل مع التوكن: {BOT_TOKEN[:10]}...")

# ==================== نقطة الدخول الرئيسية ====================
if __name__ == "__main__":
    port = int(os.environ.get("PORT", PORT))
    print(f"🌐 تشغيل السيرفر على المنفذ: {port}")
    uvicorn.run(
        "main:app",
        host="0.0.0.0",
        port=port,
        reload=False
    )