import os
import sys
from dotenv import load_dotenv

load_dotenv()

OPENROUTER_BASE_URL = os.getenv("OPENROUTER_BASE_URL", "https://openrouter.ai/api/v1")
OPENROUTER_MODEL = os.getenv("OPENROUTER_MODEL")
OPENROUTER_API_KEY = os.getenv("OPENROUTER_API_KEY")
GITHUB_USER_URL = os.getenv("GITHUB_USER_URL")
ADMIN_PASSWORD = os.getenv("ADMIN_PASSWORD")

WEAK_PASSWORDS = {"test", "password", "admin", "123456", "secret", "changeme"}
if ADMIN_PASSWORD and ADMIN_PASSWORD.lower() in WEAK_PASSWORDS:
    print("SECURITY WARNING: ADMIN_PASSWORD is weak. Change it in backend/.env", file=sys.stderr)