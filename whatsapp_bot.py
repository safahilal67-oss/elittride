import requests
import json
from flask import Flask, request, jsonify

#⚙️ الإعدادات الخاصة بك (يجب أن تكون مطابقة للقيم التي زودتني بها)
API_TOKEN_INSTANCE = "ed2e660836a1444ca6d1cf751b864c526ca0473b94084ec4b7"
ID_INSTANCE = "7107345224"
SHEET_API_URL = "https://sheetdb.io/api/v1/iy3ydzy2o8c1g"

# URL لإرسال رسالة عبر Green-API (تأكد أن هذا هو الـ URL الصحيح لـ API الذي تستخدمه)
WHATSAPP_SEND_URL = f"https://api.greenapi.com/waInstance{ID_INSTANCE}/sendMessage/{API_TOKEN_INSTANCE}"

# ----------------------------------------------------------------------
# الدوال المساعدة (Helper Functions)
# ----------------------------------------------------------------------

def search_customer_by_phone(phone_number):
    """
    تبحث عن بيانات العميل في شيت Google (sheetdb.io) باستخدام رقم الهاتف.
    
    ملاحظة: نفترض هنا أن لديك عمود اسمه 'phone' في الشيت
    يحتوي على رقم العميل بنفس الصيغة التي يرسلها Green-API (بدون +).
    """
    # البحث في sheetdb يتم بإضافة /search?sheetdb-query={"key":"value"}
    # سنبحث عن رقم الهاتف (phone)
    search_url = f"{SHEET_API_URL}/search?sheetdb-query={{\"phone\":\"{phone_number}\"}}"
    
    try:
        response = requests.get(search_url)
        response.raise_for_status()  # يرفع خطأ إذا كان الرد غير ناجح
        data = response.json()
        
        # نعود بأول نتيجة مطابقة فقط
        if data and isinstance(data, list):
            return data[0]
        return None
    except requests.RequestException as e:
        print(f"❌ خطأ في البحث عن الشيت: {e}")
        return None

def send_whatsapp_message(chat_id, message_text):
    """
    ترسل رسالة إلى رقم معين عبر Green-API.
    """
    # يجب أن يكون الـ chat_id بالصيغة: 9665xxxxxxxx@c.us
    payload = {
        "chatId": chat_id,
        "message": message_text
    }
    
    try:
        response = requests.post(WHATSAPP_SEND_URL, json=payload)
        response.raise_for_status()
        print(f"✅ تم إرسال الرسالة بنجاح إلى {chat_id}")
        return response.json()
    except requests.RequestException as e:
        print(f"❌ خطأ في إرسال رسالة واتساب: {e}")
        return None

# ----------------------------------------------------------------------
# خادم Flask ومنطق الرد الرئيسي
# ----------------------------------------------------------------------

app = Flask(__name__)

@app.route('/', methods=['POST'])
def whatsapp_webhook():
    """
    يستقبل رسائل الويب هوك الواردة من واتساب (Green-API).
    """
    try:
        # 1. استلام البيانات
        data = request.json
        print("Received WhatsApp Data:", json.dumps(data, indent=2, ensure_ascii=False))

        # تحليل هيكل بيانات Green-API للحصول على الرسالة والمرسل
        # هذا الجزء يعتمد على هيكل الـ Webhook الخاص بـ Green-API
        if 'typeWebhook' in data and data['typeWebhook'] == 'incomingMessageReceived':
            
            # استخراج نص الرسالة
            try:
                message_body = data['messageData']['textMessageData']['textMessage'].strip().lower()
            except (KeyError, TypeError):
                # إذا لم يكن النص رسالة نصية (مثل صورة أو فيديو)، نتجاهلها
                return jsonify({"status": "ignored", "reason": "Not a text message"}), 200

            sender_id = data['senderData']['chatId'] # مثال: 9665xxxxxxxx@c.us
            
            # استخراج رقم الهاتف للبحث في الشيت (مثال: 9665xxxxxxxx)
            sender_phone = sender_id.split('@')[0] 

            # 2. فحص نية المستخدم (الكلمات المفتاحية)
            if "مبلغي" in message_body or "رصيدي" in message_body or "كم علي" in message_body:
                
                # 3. البحث عن العميل في الشيت
                customer_data = search_customer_by_phone(sender_phone)
                
                if customer_data:
                    # استخراج البيانات المطلوبة (A=contract_id, B=name, E=amount)
                    # **تأكد من أن أسماء الأعمدة في الشيت تطابق ما هو مكتوب هنا**
                    name = customer_data.get('name', 'عميلنا العزيز')
                    contract_id = customer_data.get('contract_id', 'غير متوفر')
                    amount = customer_data.get('amount', 'غير متوفر')
                    
                    # 4. تنسيق الرد وإرساله
                    reply_message = (
                        f"مرحباً بك يا *{name}* 👋\n"
                        f"صاحب رقم العقد *(A)*: *{contract_id}*\n"
                        f"مبلغك الحالي *(E)* هو: *{amount}* ريال.\n"
                        "نتمنى لك يوماً سعيداً!"
                    )
                    send_whatsapp_message(sender_id, reply_message)
                
                else:
                    # العميل غير موجود
                    error_message = "عذراً، لم نتمكن من العثور على بياناتك في سجلاتنا. يرجى التأكد من أنك ترسل الرسالة من الرقم المسجل لدينا."
                    send_whatsapp_message(sender_id, error_message)

            else:
                # رسالة رد عامة
                default_message = "أهلاً بك! أنا نظام آلي. يمكنك أن تسألني عن *مبلغك* أو *رصيدك* فقط حالياً. 💬"
                send_whatsapp_message(sender_id, default_message)
        
        return jsonify({"status": "received_and_processed"}), 200

    except Exception as e:
        print(f"❌ خطأ عام في معالجة الـ Webhook: {e}")
        # الرد برمز 200 لمنع WhatsApp API من إعادة إرسال نفس الـ Webhook
        return jsonify({"status": "error", "message": str(e)}), 200 

# ----------------------------------------------------------------------
# تشغيل التطبيق (للنشر على الخادم)
# ----------------------------------------------------------------------

if __name__ == '__main__':
    # عند النشر، يجب أن يتم تشغيل هذا عبر Gunicorn أو أي WSGI Server
    # للتجربة المحلية: app.run(host='0.0.0.0', port=5000) 
    print("Application starting...")
    # *ملاحظة*: في بيئة الإنتاج على استضافة مثل Heroku، سيتم استخدام أمر تشغيل مختلف
    # (مثل gunicorn) ولا داعي لتضمين app.run هنا عادةً.
    app.run(host='0.0.0.0', port=5000)