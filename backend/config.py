"""Configuración del backend. Lee variables de entorno con pydantic-settings.

Nada de secretos en el código: todo viene de .env (ver .env.example).
"""
from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    model_config = SettingsConfigDict(env_file=".env", env_file_encoding="utf-8", extra="ignore")

    # IA: Gemma a través de la Gemini API (el modelo NO va fijo en el código)
    gemini_api_key: str = ""
    gemma_model: str = "gemma-4-31b-it"
    gemini_url: str = "https://generativelanguage.googleapis.com/v1beta"

    # Alertas externas
    telegram_token: str = ""
    telegram_chat_id: str = ""

    # Datos de ejemplo para que app y panel avancen sin backend real
    mock_mode: bool = False

    # Base de datos y archivos
    database_url: str = "sqlite:///./data/rutasegura.db"
    uploads_dir: str = "uploads"

    # Rate limiting básico (peticiones POST por minuto / IP / ruta)
    rate_limit_per_minute: int = 120
    rate_limit_alerts_per_minute: int = 20


def load_settings() -> Settings:
    """Se instancia por petición/app para que los tests puedan sobreescribir env."""
    return Settings()
