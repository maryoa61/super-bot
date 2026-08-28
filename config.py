from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    """
    All secrets/config come from environment variables (or a .env file).
    Never hardcode BOT_TOKEN or gateway keys in source.
    """

    model_config = SettingsConfigDict(env_file=".env", env_file_encoding="utf-8")

    # --- core bot ---
    BOT_TOKEN: str
    DATABASE_URL: str = "sqlite+aiosqlite:///./vpn_bot.db"

    # --- admin / ops ---
    ADMIN_IDS: str = ""  # comma-separated telegram_ids, e.g. "123456,789012"

    # --- gateways (leave blank until wired up) ---
    OXAPAY_MERCHANT_KEY: str = ""
    ZARINPAL_MERCHANT_ID: str = ""

    @property
    def admin_id_list(self) -> list[int]:
        return [int(x) for x in self.ADMIN_IDS.split(",") if x.strip()]


settings = Settings()
