import os
from dataclasses import dataclass
import dotenv

dotenv.load_dotenv()


@dataclass
class EnvConfig:
    OPENAI_BASE_URL: str = os.environ.get("OPENAI_BASE_URL", "https://api.openai.com")
    OPENAI_API_KEY: str = os.environ.get("OPENAI_API_KEY", "")
    ADDITIONAL_BASE_URLS: str = os.environ.get("ADDITIONAL_BASE_URLS", "")
    VERBOSE: bool = os.environ.get("VERBOSE") == "true"
    LOG_MESSAGE: bool = os.environ.get("LOG_MESSAGE") == "true"
    LOG_REQUEST_BODY: bool = os.environ.get("LOG_REQUEST_BODY") == "true"
    NEW_RELIC_LICENSE_KEY: str = os.environ.get("NEW_RELIC_LICENSE_KEY", "")
    ENV: str = os.environ.get("ENV", "development")

    def get_additional_base_urls(self) -> list[str]:
        """
        Parse additional base URLs from environment variable.
        Format: ADDITIONAL_BASE_URLS=url1;url2;url3
        Example: ADDITIONAL_BASE_URLS=https://api.custom.com/v1;http://localhost:11434/v1
        """
        if not self.ADDITIONAL_BASE_URLS:
            return []

        return [url.strip() for url in self.ADDITIONAL_BASE_URLS.split(";") if url.strip()]


env_config = EnvConfig()

if not env_config.OPENAI_BASE_URL:
    env_config.OPENAI_BASE_URL = "https://api.openai.com"
    print("OPENAI_BASE_URL is not set, using default value: https://api.openai.com")
else:
    print("OPENAI_BASE_URL is set to: ", env_config.OPENAI_BASE_URL)

if not env_config.OPENAI_API_KEY:
    print("OPENAI_API_KEY is not set, using the value from request header")
else:
    print("OPENAI_API_KEY is set")

if env_config.VERBOSE:
    print("VERBOSE is set. The request content will be logged.")
