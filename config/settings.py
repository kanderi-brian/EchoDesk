"""Global configuration settings for EchoDesk."""

from dataclasses import dataclass


@dataclass
class Settings:
    """Application-wide settings for EchoDesk."""

    app_name: str = "EchoDesk"
    version: str = "2.0.1"
    debug: bool = False
