import os

from dotenv import load_dotenv

BASE_DIR = os.path.abspath(os.path.dirname(__file__))
load_dotenv(os.path.join(BASE_DIR, ".env"))


def _env_flag(name: str, default: bool = False) -> bool:
    value = os.getenv(name)
    if value is None:
        return default
    return value.strip().lower() in {"1", "true", "yes", "on"}


class Config:
    SECRET_KEY = os.getenv("SECRET_KEY", "change-me")
    MYSQL_HOST = os.getenv("MYSQL_HOST", "localhost")
    MYSQL_PORT = int(os.getenv("MYSQL_PORT", "3306"))
    MYSQL_USER = os.getenv("MYSQL_USER", "root")
    MYSQL_PASSWORD = os.getenv("MYSQL_PASSWORD", "")
    MYSQL_DB = os.getenv("MYSQL_DB", "sakhwaniya_gp")
    MYSQL_CHARSET = os.getenv("MYSQL_CHARSET", "utf8mb4")
    MAX_CONTENT_LENGTH = int(os.getenv("MAX_CONTENT_LENGTH_MB", "16")) * 1024 * 1024
    UPLOAD_FOLDER = os.getenv(
        "UPLOAD_FOLDER", os.path.join(BASE_DIR, "instance", "uploads")
    )
    ALLOWED_UPLOAD_EXTENSIONS = tuple(
        ext.strip().lower()
        for ext in os.getenv(
            "ALLOWED_UPLOAD_EXTENSIONS", "pdf,png,jpg,jpeg,doc,docx"
        ).split(",")
        if ext.strip()
    )
    SMTP_HOST = os.getenv("SMTP_HOST", "")
    SMTP_PORT = int(os.getenv("SMTP_PORT", "587"))
    SMTP_USERNAME = os.getenv("SMTP_USERNAME", "")
    SMTP_PASSWORD = os.getenv("SMTP_PASSWORD", "")
    SMTP_USE_TLS = _env_flag("SMTP_USE_TLS", True)
    SMTP_USE_SSL = _env_flag("SMTP_USE_SSL", False)
    ALERT_FROM_EMAIL = os.getenv("ALERT_FROM_EMAIL", "")
    ADMIN_ALERT_EMAIL = os.getenv("ADMIN_ALERT_EMAIL", "")
    ADMIN_ALERT_MOBILE = os.getenv("ADMIN_ALERT_MOBILE", "")
    SMS_WEBHOOK_URL = os.getenv("SMS_WEBHOOK_URL", "")
    SMS_WEBHOOK_TOKEN = os.getenv("SMS_WEBHOOK_TOKEN", "")
    TWILIO_ACCOUNT_SID = os.getenv("TWILIO_ACCOUNT_SID", "")
    TWILIO_AUTH_TOKEN = os.getenv("TWILIO_AUTH_TOKEN", "")
    TWILIO_FROM_NUMBER = os.getenv("TWILIO_FROM_NUMBER", "")
    SMS77_API_KEY = os.getenv("SMS77_API_KEY", "")
    OPENAI_API_KEY = os.getenv("OPENAI_API_KEY", "")
    OPENAI_CHAT_MODEL = os.getenv("OPENAI_CHAT_MODEL", "gpt-5")

