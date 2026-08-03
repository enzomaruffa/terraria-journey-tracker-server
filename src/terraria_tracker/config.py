from pathlib import Path

from pydantic import Field
from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    """Runtime configuration.

    Every field has a working default, so the tracker starts with no .env file at all.
    """

    model_config = SettingsConfigDict(
        env_prefix="TERRARIA_",
        env_file=".env",
        env_file_encoding="utf-8",
        extra="ignore",
    )

    player_file: Path | None = Field(
        default=None,
        description="Character file to watch. Auto-detected when unset.",
    )
    host: str = "127.0.0.1"
    port: int = 4777
    verbose: bool = False
    open_browser: bool = True

    # Terraria writes the character file in several bursts while saving; wait for it
    # to settle before re-reading so one save does not produce five broadcasts.
    debounce_seconds: float = 0.4

    cors_origins: list[str] = Field(
        default_factory=lambda: [
            "http://localhost:5173",
            "http://127.0.0.1:5173",
        ],
        description="Extra origins allowed to call the API, for running the Vite dev server separately.",
    )


settings = Settings()
