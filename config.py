import os
from dotenv import load_dotenv

# تحميل متغيرات البيئة من ملف .env
load_dotenv()

# ==================== إعدادات البوت (مطلوبة) ====================
BOT_TOKEN = os.getenv('BOT_TOKEN', '7995442033:AAFQjpNNl-PgFWim393RPUNxDBsJQSLQVlY')
ADMIN_ID = int(os.getenv('ADMIN_ID', '8327957313'))  # ضع معرفك هنا

# ==================== إعدادات Railway (تلقائية) ====================
# Railway يعطي هذه المتغيرات تلقائياً
RAILWAY_ENVIRONMENT = os.getenv('RAILWAY_ENVIRONMENT', 'production')
RAILWAY_PUBLIC_DOMAIN = os.getenv('RAILWAY_PUBLIC_DOMAIN', '')
RAILWAY_STATIC_URL = os.getenv('RAILWAY_STATIC_URL', '')

# تحديد الرابط الأساسي
if RAILWAY_STATIC_URL:
    BASE_URL = RAILWAY_STATIC_URL
elif RAILWAY_PUBLIC_DOMAIN:
    BASE_URL = f"https://{RAILWAY_PUBLIC_DOMAIN}"
else:
    BASE_URL = "http://localhost:8000"

# ==================== إعدادات اللعبة ====================
DEFAULT_BALANCE = int(os.getenv('DEFAULT_BALANCE', '1000'))
BET_AMOUNT = int(os.getenv('BET_AMOUNT', '100'))
WELCOME_BONUS = int(os.getenv('WELCOME_BONUS', '500'))

# ==================== إعدادات السيرفر ====================
PORT = int(os.getenv('PORT', '8000'))

# ==================== التحقق من الإعدادات ====================
def validate_config():
    """التحقق من صحة الإعدادات"""
    print("=" * 50)
    print("🎮 التحقق من إعدادات لعبة Aviator")
    print("=" * 50)
    
    errors = []
    warnings = []
    
    # التحقق من BOT_TOKEN
    if not BOT_TOKEN or BOT_TOKEN == 'ضع_توكن_البوت_هنا':
        errors.append("❌ BOT_TOKEN: غير معين أو لا يزال بالقيمة الافتراضية")
    elif len(BOT_TOKEN) < 30:
        warnings.append("⚠️  BOT_TOKEN: قد يكون غير صالح (قصير جداً)")
    else:
        print(f"✅ BOT_TOKEN: {BOT_TOKEN[:10]}...")
    
    # التحقق من ADMIN_ID
    if ADMIN_ID == 123456789:
        warnings.append("⚠️  ADMIN_ID: لا يزال بالقيمة الافتراضية")
    else:
        print(f"✅ ADMIN_ID: {ADMIN_ID}")
    
    # التحقق من BASE_URL
    print(f"✅ BASE_URL: {BASE_URL}")
    
    # التحقق من Railway Environment
    if RAILWAY_ENVIRONMENT:
        print(f"✅ RAILWAY_ENVIRONMENT: {RAILWAY_ENVIRONMENT}")
    else:
        print("ℹ️  RAILWAY_ENVIRONMENT: غير مضبوط (يعمل محلياً)")
    
    # إعدادات اللعبة
    print(f"🎮 DEFAULT_BALANCE: {DEFAULT_BALANCE}")
    print(f"🎮 BET_AMOUNT: {BET_AMOUNT}")
    print(f"🎮 WELCOME_BONUS: {WELCOME_BONUS}")
    print(f"🌐 PORT: {PORT}")
    
    # عرض التحذيرات
    if warnings:
        print("\n⚠️  التحذيرات:")
        for warning in warnings:
            print(f"   {warning}")
    
    # عرض الأخطاء
    if errors:
        print("\n❌ الأخطاء:")
        for error in errors:
            print(f"   {error}")
        print("\n🔧 يجب إصلاح هذه الأخطاء قبل التشغيل!")
        return False
    
    print("\n✅ جميع الإعدادات صالحة للتشغيل!")
    print("=" * 50)
    return True

# التحقق التلقائي عند الاستيراد
if __name__ == "__main__":
    validate_config()