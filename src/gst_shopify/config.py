import json
import os
from pathlib import Path
from typing import Any, Dict


def load_seller_details(
    config_path: Path = Path("config/seller_details.json"),
) -> Dict[str, Any]:
    """Load seller details from configuration file"""
    if not config_path.exists():
        print(f"Working directory: {Path.cwd()}")
        print(f"Attempted config path: {config_path.absolute()}")
        raise FileNotFoundError(f"Configuration file not found: {config_path}")

    with open(config_path) as f:
        return json.load(f)


def get_shopify_credentials() -> tuple[str, str]:
    """Get Shopify store and API token from environment"""
    store = os.getenv("SHOPIFY_STORE")
    token = os.getenv("API_TOKEN")

    if not store or not token:
        raise ValueError(
            "SHOPIFY_STORE and API_TOKEN environment variables must be set"
        )

    return store, token
