import os
from dotenv import load_dotenv

load_dotenv()

OMNIROUTE_BASE_URL = os.getenv("OMNIROUTE_BASE_URL")
OMNIROUTE_MODEL = os.getenv("OMNIROUTE_MODEL")
OMNIROUTE_API_KEY = os.getenv("OMNIROUTE_API_KEY")
GITHUB_USER_URL = os.getenv("GITHUB_USER_URL")