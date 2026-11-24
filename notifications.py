import os, smtplib
from email.message import EmailMessage

STAFF_EMAIL = os.environ.get("STAFF_EMAIL", "")
SENDER = os.environ.get("SENDER_EMAIL", "")
SENDER_PASS = os.environ.get("GMAIL_APP_PASSWORD", "")


def notify_staff(customer_id, reason, last_message):
    """يطرش إيميل للموظفة. إذا فشل ما يوقف البوت."""
    if not (STAFF_EMAIL and SENDER and SENDER_PASS):
        print("⚠️ إعدادات الإيميل ناقصة، ما انرسل إشعار")
        return False
    try:
        msg = EmailMessage()
        msg["Subject"] = f"طلب تحويل من زبونة: {customer_id}"
        msg["From"] = SENDER
        msg["To"] = STAFF_EMAIL
        msg.set_content(
            f"رقم الزبونة: {customer_id}\n"
            f"السبب: {reason}\n"
            f"آخر رسالة: {last_message}\n"
        )
        with smtplib.SMTP_SSL("smtp.gmail.com", 465, timeout=20) as s:
            s.login(SENDER, SENDER_PASS)
            s.send_message(msg)
        return True
    except Exception as e:
        print("⚠️ فشل إرسال الإيميل:", e)
        return False
