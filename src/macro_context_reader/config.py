import os

from dotenv import load_dotenv

load_dotenv()

FRED_API_KEY = os.environ.get("FRED_API_KEY")
