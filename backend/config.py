import os
import sys
from dotenv import load_dotenv

load_dotenv()

OMNIROUTE_BASE_URL = os.getenv("OMNIROUTE_BASE_URL")
OMNIROUTE_MODEL = os.getenv("OMNIROUTE_MODEL")
OMNIROUTE_API_KEY = os.getenv("OMNIROUTE_API_KEY")
GITHUB_USER_URL = os.getenv("GITHUB_USER_URL")
ADMIN_PASSWORD = os.getenv("ADMIN_PASSWORD")

WEAK_PASSWORDS = {"test", "password", "admin", "123456", "secret", "changeme"}
if ADMIN_PASSWORD and ADMIN_PASSWORD.lower() in WEAK_PASSWORDS:
    print("SECURITY WARNING: ADMIN_PASSWORD is weak. Change it in backend/.env", file=sys.stderr)