import os
import smtplib
from email.mime.text import MIMEText
from email.mime.multipart import MIMEMultipart
import logging

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

    # Hỗ trợ đầy đủ các biến môi trường người dùng đã cấu hình trên Render:
    # SMTP_SERVER, SMTP_PORT, SMTP_USERNAME, SMTP_PASSWORD, MAIL_FROM, SMTP_TLS
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
    # Loại bỏ khoảng trắng nếu người dùng copy mật khẩu ứng dụng có dấu cách (vd: uryo ciou xctf uugf)
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

    return {
        "host": host,
        "port": port,
        "user": user,
        "password": password,
        "sender": sender,
        "use_tls": use_tls,
        "use_ssl": use_ssl,
        "is_configured": bool(user and password),
    }

def send_password_reset_email(to_email: str, otp_code: str) -> tuple[bool, str]:
    config = get_smtp_config()
    if not config["is_configured"]:
        logger.warning("SMTP chưa được cấu hình (thiếu SMTP_USERNAME/SMTP_USER hoặc SMTP_PASSWORD)")
        return False, "Chưa cấu hình thông tin SMTP gửi thư."

    msg = MIMEMultipart("alternative")
    msg["Subject"] = f"[{otp_code}] Mã xác nhận đặt lại mật khẩu CRM"
    msg["From"] = f"Hệ thống CRM <{config['sender']}>"
    msg["To"] = to_email

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

    msg.attach(MIMEText(text_body, "plain", "utf-8"))
    msg.attach(MIMEText(html_body, "html", "utf-8"))

    try:
        if config["use_ssl"]:
            server = smtplib.SMTP_SSL(config["host"], config["port"], timeout=15)
        else:
            server = smtplib.SMTP(config["host"], config["port"], timeout=15)
            if config["use_tls"]:
                server.starttls()

        server.login(config["user"], config["password"])
        server.sendmail(config["sender"], [to_email], msg.as_string())
        server.quit()
        logger.info(f"Đã gửi mã xác nhận OTP thành công đến {to_email}")
        return True, "Email gửi thành công"
    except Exception as e:
        logger.error(f"Lỗi gửi email tới {to_email}: {e}")
        return False, str(e)
