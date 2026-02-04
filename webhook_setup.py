#!/usr/bin/env python3
"""
أداة إعداد Webhook للبوت على Railway
"""

import requests
import sys
import os
from config import BOT_TOKEN, BASE_URL

def set_webhook():
    """تعيين Webhook للبوت"""
    webhook_url = f"{BASE_URL}/webhook"
    
    response = requests.post(
        f"https://api.telegram.org/bot{BOT_TOKEN}/setWebhook",
        json={
            "url": webhook_url,
            "max_connections": 40,
            "allowed_updates": ["message", "callback_query", "inline_query"]
        }
    )
    
    if response.status_code == 200:
        result = response.json()
        if result.get("ok"):
            print(f"✅ تم تعيين Webhook بنجاح!")
            print(f"📎 الرابط: {webhook_url}")
            print(f"📊 النتيجة: {result.get('description')}")
            
            # الحصول على معلومات Webhook
            info = requests.get(
                f"https://api.telegram.org/bot{BOT_TOKEN}/getWebhookInfo"
            ).json()
            
            print(f"\n📋 معلومات Webhook:")
            print(f"✅ الحالة: {info.get('result', {}).get('url')}")
            print(f"📞 الأخطاء: {info.get('result', {}).get('last_error_message', 'لا توجد')}")
            print(f"⏰ آخر تحديث: {info.get('result', {}).get('last_synchronization_error_date', 'غير متاح')}")
            
            return True
        else:
            print(f"❌ فشل تعيين Webhook: {result.get('description')}")
            return False
    else:
        print(f"❌ خطأ في الاتصال: {response.status_code}")
        return False

def delete_webhook():
    """حذف Webhook"""
    response = requests.post(
        f"https://api.telegram.org/bot{BOT_TOKEN}/deleteWebhook"
    )
    
    if response.status_code == 200:
        result = response.json()
        if result.get("ok"):
            print("✅ تم حذف Webhook بنجاح")
            return True
        else:
            print(f"❌ فشل حذف Webhook: {result.get('description')}")
            return False
    else:
        print(f"❌ خطأ في الاتصال: {response.status_code}")
        return False

def get_webhook_info():
    """الحصول على معلومات Webhook"""
    response = requests.get(
        f"https://api.telegram.org/bot{BOT_TOKEN}/getWebhookInfo"
    )
    
    if response.status_code == 200:
        result = response.json()
        if result.get("ok"):
            info = result.get("result", {})
            
            print("📋 معلومات Webhook الحالية:")
            print(f"🔗 الرابط: {info.get('url', 'غير معين')}")
            print(f"✅ لديه شهادة SSL: {info.get('has_custom_certificate', 'غير معروف')}")
            print(f"📊 عدد الاتصالات: {info.get('max_connections', 'غير معروف')}")
            print(f"📞 آخر رسالة خطأ: {info.get('last_error_message', 'لا توجد')}")
            print(f"⏰ وقت آخر خطأ: {info.get('last_error_date', 'غير متاح')}")
            
            return info
        else:
            print(f"❌ فشل الحصول على المعلومات: {result.get('description')}")
            return None
    else:
        print(f"❌ خطأ في الاتصال: {response.status_code}")
        return None

if __name__ == "__main__":
    if len(sys.argv) < 2:
        print("""
🎮 أداة إعداد Webhook للعبة Aviator

الاستخدام:
    python webhook_setup.py [command]

الأوامر:
    set      - تعيين Webhook جديد
    delete   - حذف Webhook
    info     - عرض معلومات Webhook الحالية
    help     - عرض هذه المساعدة
        """)
        sys.exit(1)
    
    command = sys.argv[1].lower()
    
    if command == "set":
        set_webhook()
    elif command == "delete":
        delete_webhook()
    elif command == "info":
        get_webhook_info()
    elif command == "help":
        print("""
🎮 أداة إعداد Webhook للعبة Aviator

هذه الأداة تساعد في إعداد Webhook للبوت على Railway.

متطلبات:
1. BOT_TOKEN - توكن البوت
2. BASE_URL - رابط التطبيق على Railway

الاستخدام:
1. تشغيل التطبيق أولاً على Railway
2. الحصول على الرابط
3. تعيين Webhook:
   python webhook_setup.py set

للمساعدة:
   python webhook_setup.py help
        """)
    else:
        print(f"❌ أمر غير معروف: {command}")
        print("استخدم 'help' لعرض الأوامر المتاحة")