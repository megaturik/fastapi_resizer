from pathlib import Path
from typing import Literal, Optional

from pydantic import Field, HttpUrl, ValidationError
from pydantic_settings import BaseSettings


class Settings(BaseSettings):
    """
    Image service configuration, loaded from environment variables.
    """

    RESIZE_DIR: Optional[Path] = Field(default=None, env="RESIZE_DIR")
    MAX_IMAGE_SIZE: int = Field(..., env="MAX_IMAGE_SIZE")
    QUALITY: int = Field(..., env="QUALITY")
    ORIGIN_URL: HttpUrl = Field(..., env="ORIGIN")
    MODE: Literal["stream", "cache"]

    class Config:
        env_file = ".env"


try:
    settings = Settings()
except ValidationError as e:
    print("Missing or invalid environment variables:")
    print(e)
    raise
