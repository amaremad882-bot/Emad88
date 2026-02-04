import os
import sys
from dotenv import load_dotenv

# تحميل متغيرات البيئة
load_dotenv()

# ==================== إعدادات البوت (مطلوبة) ====================
BOT_TOKEN = os.getenv('7995442033:AAFQjpNNl-PgFWim393RPUNxDBsJQSLQVlY', '').strip()
ADMIN_ID = os.getenv('8327957313', '').strip()

# ==================== إعدادات Railway ====================
RAILWAY_PUBLIC_DOMAIN = os.getenv('web-production-10885.up.railway.app', '').strip()
RAILWAY_STATIC_URL = os.getenv('RAILWAY_STATIC_URL', '').strip()
RAILWAY_ENVIRONMENT = os.getenv('RAILWAY_ENVIRONMENT', 'production').strip()

# تحديد الرابط الأساسي
BASE_URL = ""
if RAILWAY_STATIC_URL:
    BASE_URL = RAILWAY_STATIC_URL
elif RAILWAY_PUBLIC_DOMAIN:
    BASE_URL = f"https://{RAILWAY_PUBLIC_DOMAIN}"
else:
    BASE_URL = os.getenv('BASE_URL', 'http://localhost:8000').strip()

# ==================== إعدادات اللعبة ====================
PORT = int(os.getenv('PORT', '8000'))
ROUND_DURATION = 60  # 60 ثانية للجولة
BETTING_DURATION = 30  # 30 ثانية للرهان
BET_OPTIONS = [10, 50, 100, 500, 1000, 5000]  # خيارات الرهان

# ==================== التحقق من الإعدادات ====================
def validate_config():
    """التحقق من صحة الإعدادات"""
    print("🎮 التحقق من إعدادات لعبة Aviator")
    print("=" * 50)
    
    errors = []
    warnings = []
    
    # التحقق من BOT_TOKEN
    if not BOT_TOKEN:
        errors.append("❌ BOT_TOKEN غير معين")
        print("❌ خطأ: BOT_TOKEN غير موجود")
        print("🔧 أضف BOT_TOKEN في Railway → Variables")
    elif len(BOT_TOKEN) < 30:
        warnings.append("⚠️ BOT_TOKEN قد يكون غير صالح (قصير جداً)")
        print(f"⚠️ تحذير: BOT_TOKEN قصير ({len(BOT_TOKEN)} حرف)")
    else:
        print(f"✅ BOT_TOKEN: {BOT_TOKEN[:15]}...")
    
    # التحقق من ADMIN_ID
    if not ADMIN_ID:
        errors.append("❌ ADMIN_ID غير معين")
        print("❌ خطأ: ADMIN_ID غير موجود")
    elif not ADMIN_ID.isdigit():
        errors.append("❌ ADMIN_ID يجب أن يكون رقم")
        print("❌ خطأ: ADMIN_ID يجب أن يكون رقم")
    else:
        ADMIN_ID_INT = int(ADMIN_ID)
        if ADMIN_ID_INT == 123456789:
            warnings.append("⚠️ ADMIN_ID لا يزال بالقيمة الافتراضية")
            print(f"⚠️ تحذير: ADMIN_ID: {ADMIN_ID_INT} (القيمة الافتراضية)")
        else:
            print(f"✅ ADMIN_ID: {ADMIN_ID_INT}")
    
    # التحقق من BASE_URL
    if not BASE_URL:
        errors.append("❌ BASE_URL غير معين")
        print("❌ خطأ: BASE_URL غير موجود")
    elif not BASE_URL.startswith(('http://', 'https://')):
        errors.append("❌ BASE_URL يجب أن يبدأ بـ http:// أو https://")
        print(f"❌ خطأ: BASE_URL غير صالح: {BASE_URL}")
    else:
        print(f"✅ BASE_URL: {BASE_URL}")
    
    # إعدادات اللعبة
    print(f"🎮 ROUND_DURATION: {ROUND_DURATION} ثانية")
    print(f"🎮 BETTING_DURATION: {BETTING_DURATION} ثانية")
    print(f"🎮 BET_OPTIONS: {BET_OPTIONS}")
    print(f"🌐 PORT: {PORT}")
    print(f"🌍 ENVIRONMENT: {RAILWAY_ENVIRONMENT}")
    
    # عرض التحذيرات
    if warnings:
        print("\n⚠️ التحذيرات:")
        for warning in warnings:
            print(f"   {warning}")
    
    # عرض الأخطاء
    if errors:
        print("\n❌ الأخطاء:")
        for error in errors:
            print(f"   {error}")
        print("\n🔧 يجب إصلاح هذه الأخطاء قبل التشغيل!")
        print("=" * 50)
        return False
    
    print("\n✅ جميع الإعدادات صالحة")
    print("=" * 50)
    return True

# تعديل ADMIN_ID ليكون رقم
try:
    ADMIN_ID = int(ADMIN_ID) if ADMIN_ID else 0
except ValueError:
    ADMIN_ID = 0

if __name__ == "__main__":
    validate_config()