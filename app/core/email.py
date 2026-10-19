import os
import smtplib
import socket
from email.mime.text import MIMEText
from email.mime.multipart import MIMEMultipart
import logging
import urllib.request
import json

logger = logging.getLogger(__name__)

def load_local_env_files():
    """Tự động đọc file .env ở thư mục gốc hoặc backend nếu có"""
    potential_paths = [
        os.path.join(os.getcwd(), ".env"),
        os.path.join(os.path.dirname(os.path.dirname(os.path.dirname(__file__))), ".env"),
        r"c:\Users\Admin\OneDrive\Desktop\quản lý khách hàng\.env",
        r"c:\Users\Admin\OneDrive\Desktop\quản lý khách hàng\quan-ly-khach-hang-backend-new\.env",
    ]
    for p in potential_paths:
        if os.path.exists(p):
            try:
                with open(p, "r", encoding="utf-8", errors="ignore") as f:
                    for line in f:
                        line = line.strip()
                        if line and not line.startswith("#") and "=" in line:
                            k, v = line.split("=", 1)
                            k = k.strip()
                            v = v.strip().strip("'\"")
                            if k not in os.environ or not os.environ[k]:
                                os.environ[k] = v
            except Exception:
                pass

load_local_env_files()

def get_smtp_config():
    load_local_env_files()

    host = (
        os.getenv("SMTP_SERVER")
        or os.getenv("SMTP_HOST")
        or os.getenv("EMAIL_HOST")
        or os.getenv("MAIL_HOST")
        or "smtp.gmail.com"
    )
    port_str = (
        os.getenv("SMTP_PORT")
        or os.getenv("EMAIL_PORT")
        or os.getenv("MAIL_PORT")
        or "587"
    )
    try:
        port = int(port_str)
    except Exception:
        port = 587

    user = (
        os.getenv("SMTP_USERNAME")
        or os.getenv("SMTP_USER")
        or os.getenv("EMAIL_HOST_USER")
        or os.getenv("MAIL_USERNAME")
        or os.getenv("MAIL_USER")
    )
    raw_password = (
        os.getenv("SMTP_PASSWORD")
        or os.getenv("SMTP_PASS")
        or os.getenv("EMAIL_HOST_PASSWORD")
        or os.getenv("MAIL_PASSWORD")
        or ""
    )
    password = raw_password.strip().replace(" ", "")

    sender = (
        os.getenv("MAIL_FROM")
        or os.getenv("SMTP_FROM")
        or os.getenv("EMAIL_FROM")
        or os.getenv("DEFAULT_FROM_EMAIL")
        or user
        or "no-reply@crm-system.com"
    )

    use_tls = os.getenv("SMTP_TLS", "true").lower() in ("true", "1", "yes")
    use_ssl = os.getenv("SMTP_SSL", "false").lower() in ("true", "1", "yes") or port == 465

    resend_key = os.getenv("RESEND_API_KEY", "").strip()
    brevo_key = os.getenv("BREVO_API_KEY", "").strip()

    return {
        "host": host,
        "port": port,
        "user": user,
        "password": password,
        "sender": sender,
        "use_tls": use_tls,
        "use_ssl": use_ssl,
        "resend_key": resend_key,
        "brevo_key": brevo_key,
        "is_configured": bool((user and password) or resend_key or brevo_key),
    }

def send_via_resend(api_key: str, to_email: str, subject: str, html_content: str, text_content: str) -> tuple[bool, str]:
    """Gửi email qua Resend REST API (cổng 443 HTTPS, không bao giờ bị Render chặn)"""
    url = "https://api.resend.com/emails"
    headers = {
        "Authorization": f"Bearer {api_key}",
        "Content-Type": "application/json",
        "User-Agent": "CRM-System/1.0",
    }
    sender = os.getenv("RESEND_FROM") or "CRM System <onboarding@resend.dev>"
    payload = {
        "from": sender,
        "to": [to_email],
        "subject": subject,
        "html": html_content,
        "text": text_content,
    }
    req = urllib.request.Request(url, data=json.dumps(payload).encode("utf-8"), headers=headers)
    try:
        with urllib.request.urlopen(req, timeout=15) as resp:
            data = resp.read().decode("utf-8")
            logger.info(f"Resend API gửi thành công đến {to_email}: {data}")
            return True, "Email gửi thành công qua Resend API"
    except Exception as e:
        err_msg = str(e)
        if hasattr(e, "read"):
            try:
                err_msg = e.read().decode(errors="ignore")
            except Exception:
                pass
        logger.error(f"Lỗi gửi email qua Resend API: {err_msg}")
        return False, f"Resend API error: {err_msg}"

def send_via_brevo(api_key: str, to_email: str, subject: str, html_content: str, text_content: str, sender_email: str) -> tuple[bool, str]:
    """Gửi email qua Brevo REST API (cổng 443 HTTPS, không bị Render chặn)"""
    url = "https://api.brevo.com/v3/smtp/email"
    headers = {
        "api-key": api_key,
        "Content-Type": "application/json",
        "User-Agent": "CRM-System/1.0",
    }
    payload = {
        "sender": {"email": sender_email or "vlong3217@gmail.com", "name": "Hệ thống CRM"},
        "to": [{"email": to_email}],
        "subject": subject,
        "htmlContent": html_content,
        "textContent": text_content,
    }
    req = urllib.request.Request(url, data=json.dumps(payload).encode("utf-8"), headers=headers)
    try:
        with urllib.request.urlopen(req, timeout=15) as resp:
            data = resp.read().decode("utf-8")
            logger.info(f"Brevo API gửi thành công đến {to_email}: {data}")
            return True, "Email gửi thành công qua Brevo API"
    except Exception as e:
        err_msg = str(e)
        if hasattr(e, "read"):
            try:
                err_msg = e.read().decode(errors="ignore")
            except Exception:
                pass
        logger.error(f"Lỗi gửi email qua Brevo API: {err_msg}")
        return False, f"Brevo API error: {err_msg}"

def send_password_reset_email(to_email: str, otp_code: str) -> tuple[bool, str]:
    config = get_smtp_config()
    if not config["is_configured"]:
        err = "Chưa cấu hình dịch vụ gửi email (cần SMTP hoặc RESEND_API_KEY/BREVO_API_KEY)"
        logger.warning(err)
        return False, err

    subject = f"[{otp_code}] Mã xác nhận đặt lại mật khẩu CRM"

    text_body = f"""Xin chào,

Chúng tôi nhận được yêu cầu đặt lại mật khẩu cho tài khoản {to_email}.
Mã xác nhận OTP của bạn là: {otp_code}

Mã xác nhận này có hiệu lực trong vòng 15 phút.
Nếu bạn không yêu cầu đặt lại mật khẩu, vui lòng bỏ qua email này.

Trân trọng,
Ban Quản trị CRM
"""

    html_body = f"""<!DOCTYPE html>
<html>
<head>
  <meta charset="utf-8">
  <style>
    body {{ font-family: -apple-system, BlinkMacSystemFont, 'Segoe UI', Roboto, Helvetica, Arial, sans-serif; background-color: #f8fafc; margin: 0; padding: 24px; color: #1e293b; }}
    .card {{ max-width: 500px; margin: 0 auto; background: #ffffff; border-radius: 12px; padding: 32px; box-shadow: 0 4px 12px rgba(0,0,0,0.05); border: 1px solid #e2e8f0; }}
    .badge {{ display: inline-block; background: #2563eb; color: #ffffff; padding: 4px 12px; border-radius: 20px; font-size: 12px; font-weight: 600; text-transform: uppercase; margin-bottom: 12px; }}
    h2 {{ margin: 0 0 10px; font-size: 22px; color: #0f172a; }}
    p {{ color: #475569; font-size: 14px; line-height: 1.6; margin: 8px 0; }}
    .otp-wrapper {{ background: #eff6ff; border: 2px dashed #3b82f6; border-radius: 10px; padding: 20px; text-align: center; margin: 24px 0; }}
    .otp-digits {{ font-size: 36px; font-weight: 800; letter-spacing: 8px; color: #1d4ed8; font-family: monospace; }}
    .timer {{ font-size: 13px; color: #64748b; margin-top: 6px; }}
    .warning {{ font-size: 13px; color: #dc2626; margin-top: 16px; padding: 10px; background: #fef2f2; border-radius: 6px; }}
    .footer {{ font-size: 12px; color: #94a3b8; text-align: center; margin-top: 30px; border-top: 1px solid #f1f5f9; padding-top: 16px; }}
  </style>
</head>
<body>
  <div class="card">
    <span class="badge">Bảo mật tài khoản</span>
    <h2>Mã xác nhận đặt lại mật khẩu</h2>
    <p>Bạn (hoặc ai đó) vừa yêu cầu cấp lại mật khẩu cho tài khoản <strong>{to_email}</strong> trên Hệ thống CRM.</p>
    
    <div class="otp-wrapper">
      <div class="otp-digits">{otp_code}</div>
      <div class="timer">Mã có hiệu lực trong vòng <strong>15 phút</strong></div>
    </div>

    <p>Vui lòng nhập mã OTP gồm 6 chữ số này vào trang <strong>Đặt lại mật khẩu</strong> để thiết lập mật khẩu mới.</p>
    
    <div class="warning">
      Lưu ý: Tuyệt đối không chia sẻ mã này cho bất kỳ ai. Nếu bạn không thực hiện yêu cầu này, vui lòng bỏ qua email.
    </div>

    <div class="footer">
      Email tự động được gửi từ Hệ thống Quản trị Khách hàng CRM
    </div>
  </div>
</body>
</html>"""

    # 1. Nếu có RESEND_API_KEY, ưu tiên gửi qua Resend HTTPS API (cổng 443, miễn phí, không bị chặn)
    if config["resend_key"]:
        return send_via_resend(config["resend_key"], to_email, subject, html_body, text_body)

    # 2. Nếu có BREVO_API_KEY, gửi qua Brevo HTTPS API (cổng 443)
    if config["brevo_key"]:
        return send_via_brevo(config["brevo_key"], to_email, subject, html_body, text_body, config["sender"])

    # 3. Gửi qua SMTP truyền thống (phù hợp localhost hoặc máy chủ mở port 587/465)
    msg = MIMEMultipart("alternative")
    msg["Subject"] = subject
    msg["From"] = f"Hệ thống CRM <{config['sender']}>"
    msg["To"] = to_email
    msg.attach(MIMEText(text_body, "plain", "utf-8"))
    msg.attach(MIMEText(html_body, "html", "utf-8"))

    errors = []

    # Thử gửi với cấu hình đã cho
    try:
        if config["use_ssl"]:
            server = smtplib.SMTP_SSL(config["host"], config["port"], timeout=8)
        else:
            server = smtplib.SMTP(config["host"], config["port"], timeout=8)
            if config["use_tls"]:
                server.starttls()

        server.login(config["user"], config["password"])
        server.sendmail(config["sender"], [to_email], msg.as_string())
        server.quit()
        logger.info(f"Đã gửi mã xác nhận OTP thành công đến {to_email}")
        return True, "Email gửi thành công"
    except Exception as e:
        logger.error(f"Lỗi gửi email lần 1 qua cổng {config['port']}: {e}")
        errors.append(f"Port {config['port']}: {e}")

    # Fallback sang port 465 SSL
    if config["port"] != 465 and "gmail" in config["host"].lower():
        try:
            server = smtplib.SMTP_SSL(config["host"], 465, timeout=8)
            server.login(config["user"], config["password"])
            server.sendmail(config["sender"], [to_email], msg.as_string())
            server.quit()
            logger.info(f"Gửi thành công qua cổng 465 (SSL) đến {to_email}")
            return True, "Email gửi thành công qua SSL 465"
        except Exception as e2:
            logger.error(f"Lỗi gửi email cổng 465: {e2}")
            errors.append(f"Port 465: {e2}")

    full_err = " | ".join(errors)
    if "Network is unreachable" in full_err or "101" in full_err:
        full_err += " (Lưu ý: Render Free Tier chặn toàn bộ kết nối gửi mail cổng SMTP 25, 465, 587. Cần cấu hình RESEND_API_KEY hoặc BREVO_API_KEY qua cổng HTTPS 443)."

    return False, full_err
