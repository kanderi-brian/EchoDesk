"""Global configuration settings for EchoDesk."""

from dataclasses import dataclass


@dataclass
class Settings:
    """Application-wide settings for EchoDesk."""

    app_name: str = "EchoDesk"
    version: str = "0.1.0"
    debug: bool = False
