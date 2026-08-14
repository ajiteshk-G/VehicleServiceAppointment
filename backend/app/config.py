"""Application Configuration and Environment Settings."""

import logging
import os

# Prevent 60s GCE metadata server network hang when running outside of GCP
if not os.getenv("K_SERVICE") and not os.getenv("GOOGLE_APPLICATION_CREDENTIALS"):
    os.environ.setdefault("NO_GCE_CHECK", "True")

from typing import Any, List, Optional

logger = logging.getLogger(__name__)


def fetch_secret_from_gcp(secret_id_or_path: str, project_id: str = "1047195478355") -> Optional[str]:
    """
    Fetches secret payload from Google Cloud Secret Manager.
    Accepts full resource path (e.g. projects/1047195478355/secrets/TWILIO_ACCOUNT_SID) or secret ID.
    Gracefully falls back to None if Secret Manager is unreachable or credentials are not available.
    """
    if not secret_id_or_path:
        return None
    try:
        from google.cloud import secretmanager
        import google.auth
        try:
            creds, _ = google.auth.default(scopes=["https://www.googleapis.com/auth/cloud-platform"])
        except Exception:
            creds = None

        if creds is not None:
            client = secretmanager.SecretManagerServiceClient(credentials=creds)
        elif hasattr(secretmanager, "SecretManagerServiceClient") and ("mock" in type(secretmanager.SecretManagerServiceClient).__name__.lower() or "mock" in str(secretmanager.SecretManagerServiceClient).lower()):
            client = secretmanager.SecretManagerServiceClient()
        elif os.getenv("K_SERVICE"):
            client = secretmanager.SecretManagerServiceClient()
        else:
            return None

        if secret_id_or_path.startswith("projects/"):
            name = secret_id_or_path
            if "/versions/" not in name:
                name = f"{name}/versions/latest"
        else:
            name = f"projects/{project_id}/secrets/{secret_id_or_path}/versions/latest"

        response = client.access_secret_version(name=name, timeout=1.0)
        val = response.payload.data.decode("utf-8").strip()
        logger.info(f"Successfully loaded secret '{secret_id_or_path}' from GCP Secret Manager.")
        return val
    except Exception as e:
        logger.debug(f"GCP Secret Manager lookup skipped/failed for '{secret_id_or_path}': {e}")
        return None


try:
    from pydantic_settings import BaseSettings

    class _BaseSettings(BaseSettings):
        class Config:
            env_file = ".env"
            extra = "allow"
except ImportError:
    class _BaseSettings:  # type: ignore
        def __init__(self, **kwargs):
            for k, v in kwargs.items():
                setattr(self, k, v)


class Settings(_BaseSettings):
    # App General
    APP_NAME: str = "AI-Powered Voice Service Reminder System"
    APP_VERSION: str = "1.0.0"
    DEBUG: bool = True
    ENVIRONMENT: str = os.getenv("ENVIRONMENT", "development")
    LOG_LEVEL: str = os.getenv("LOG_LEVEL", "INFO")

    # Google Cloud Platform & Vertex AI
    GCP_PROJECT_ID: str = os.getenv("GCP_PROJECT_ID", "1047195478355")
    GCP_LOCATION: str = os.getenv("GCP_LOCATION", os.getenv("GCP_REGION", "us-central1"))
    GCP_REGION: str = os.getenv("GCP_REGION", "us-central1")

    # Vertex AI / Gemini Live API (Native Audio)
    GEMINI_MODEL: str = os.getenv("GEMINI_MODEL", "gemini-live-2.5-flash-native-audio")
    VERTEX_MODEL_NAME: str = os.getenv("VERTEX_MODEL_NAME", "gemini-live-2.5-flash-native-audio")
    GEMINI_VOICE_NAME: str = os.getenv("GEMINI_VOICE_NAME", "Aoede")  # Indic warm female voice profile

    # Database Configuration (Supports PostgreSQL asyncpg & SQLite aiosqlite)
    DATABASE_URL: str = os.getenv("DATABASE_URL", "sqlite+aiosqlite:///./service_reminder.db")

    # Twilio Telephony Integration via GCP Secret Manager
    TWILIO_ACCOUNT_SID_SECRET: str = os.getenv(
        "TWILIO_ACCOUNT_SID_SECRET", "projects/1047195478355/secrets/TWILIO_ACCOUNT_SID"
    )
    TWILIO_AUTH_TOKEN_SECRET: str = os.getenv(
        "TWILIO_AUTH_TOKEN_SECRET", "projects/1047195478355/secrets/TWILIO_AUTH_TOKEN"
    )
    TWILIO_ACCOUNT_SID: str = os.getenv("TWILIO_ACCOUNT_SID", "")
    TWILIO_AUTH_TOKEN: str = os.getenv("TWILIO_AUTH_TOKEN", "")
    TWILIO_PHONE_NUMBER: str = os.getenv("TWILIO_PHONE_NUMBER", "+13369154920")
    TWILIO_WHATSAPP_NUMBER: str = os.getenv("TWILIO_WHATSAPP_NUMBER", "+14155238886")

    # Public Host for Twilio Webhooks & WebSockets (Cloud Run Service URL)
    PUBLIC_BASE_URL: str = os.getenv("PUBLIC_BASE_URL", "")

    # CORS
    CORS_ORIGINS: List[str] = ["*"]

    # PubSub Topics
    PUBSUB_TOPIC_BOOKING_CONFIRMED: str = "booking-confirmed"
    PUBSUB_TOPIC_CALL_DISPOSITIONS: str = "call-dispositions"

    def __init__(self, **data: Any):
        super().__init__(**data)
        self._resolve_secrets()

    def model_post_init(self, __context: Any) -> None:
        self._resolve_secrets()

    def _resolve_secrets(self) -> None:
        """Auto-fetches Twilio credentials from GCP Secret Manager if running on Cloud Run or explicitly configured."""
        if not os.getenv("K_SERVICE") and not os.getenv("GOOGLE_APPLICATION_CREDENTIALS") and not os.getenv("ENABLE_SECRET_MANAGER_LOOKUP"):
            return

        if not self.TWILIO_ACCOUNT_SID and self.TWILIO_ACCOUNT_SID_SECRET:
            sid = fetch_secret_from_gcp(self.TWILIO_ACCOUNT_SID_SECRET, self.GCP_PROJECT_ID)
            if sid:
                self.TWILIO_ACCOUNT_SID = sid

        if not self.TWILIO_AUTH_TOKEN and self.TWILIO_AUTH_TOKEN_SECRET:
            token = fetch_secret_from_gcp(self.TWILIO_AUTH_TOKEN_SECRET, self.GCP_PROJECT_ID)
            if token:
                self.TWILIO_AUTH_TOKEN = token

    @property
    def is_twilio_configured(self) -> bool:
        return bool(
            self.TWILIO_ACCOUNT_SID
            and self.TWILIO_AUTH_TOKEN
            and not self.TWILIO_ACCOUNT_SID.startswith("mock_")
        )

    @property
    def is_vertex_configured(self) -> bool:
        """Checks if Vertex AI ADC / Google Auth is available or project ID is configured."""
        try:
            import google.auth
            credentials, _ = google.auth.default(scopes=["https://www.googleapis.com/auth/cloud-platform"])
            return credentials is not None
        except Exception:
            return bool(os.getenv("K_SERVICE") or os.getenv("GOOGLE_APPLICATION_CREDENTIALS"))

    @property
    def is_gemini_configured(self) -> bool:
        """Backwards-compatible alias for Vertex AI Live API configuration."""
        return self.is_vertex_configured

    @property
    def ws_base_url(self) -> str:
        url = self.PUBLIC_BASE_URL.rstrip("/") if self.PUBLIC_BASE_URL else ""
        if not url and os.getenv("K_SERVICE"):
            k_svc = os.getenv("K_SERVICE")
            url = f"https://{k_svc}-{self.GCP_PROJECT_ID}.{self.GCP_LOCATION}.run.app"
        if not url:
            return "ws://localhost:8000"
        if url.startswith("https://"):
            return "wss://" + url[8:]
        elif url.startswith("http://"):
            return "ws://" + url[7:]
        elif url.startswith("wss://") or url.startswith("ws://"):
            return url
        return f"wss://{url}"


settings = Settings()
