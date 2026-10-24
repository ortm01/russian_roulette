import hashlib, hmac, json, os, sys, time
from urllib.parse import urlencode

ROOT = os.path.join(os.path.dirname(os.path.abspath(__file__)), "..")
from dotenv import load_dotenv
load_dotenv(os.path.join(ROOT, "src", ".env"))
load_dotenv(os.path.join(ROOT, ".env"))

token = os.environ["BOT_TOKEN"]
user_id = int(sys.argv[1]) if len(sys.argv) > 1 else 999000222
fields = {
    "auth_date": str(int(time.time())),
    "user": json.dumps({"id": user_id, "first_name": "Dev", "username": "dev_user"}),
}
check = "\n".join(f"{k}={v}" for k, v in sorted(fields.items()))
secret = hmac.new(b"WebAppData", token.encode(), hashlib.sha256).digest()
fields["hash"] = hmac.new(secret, check.encode(), hashlib.sha256).hexdigest()
print(urlencode(fields))
