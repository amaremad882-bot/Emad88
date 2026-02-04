import os
from dotenv import load_dotenv

# تحميل متغيرات البيئة
load_dotenv()

# ==================== إعدادات البوت ====================
BOT_TOKEN = os.getenv('BOT_TOKEN', 'ضع_توكن_البوت_هنا')
ADMIN_ID = int(os.getenv('ADMIN_ID', '123456789'))

# ==================== إعدادات Railway ====================
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
    if not BOT_TOKEN or BOT_TOKEN == 'ضع_توكن_البوت_هنا':
        errors.append("❌ BOT_TOKEN غير معين")
    else:
        print(f"✅ BOT_TOKEN: {BOT_TOKEN[:10]}...")
    
    # التحقق من ADMIN_ID
    if ADMIN_ID == 123456789:
        warnings.append("⚠️ ADMIN_ID لا يزال بالقيمة الافتراضية")
    else:
        print(f"✅ ADMIN_ID: {ADMIN_ID}")
    
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
        return False
    
    print("\n✅ جميع الإعدادات صالحة")
    print("=" * 50)
    return True

if __name__ == "__main__":
    validate_config()