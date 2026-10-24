import hashlib
import hmac
import json
import time
import unittest
from urllib.parse import urlencode

from auth import AuthError, validate_init_data

TOKEN = "123456:TEST_TOKEN"


def sign(fields: dict, token: str = TOKEN) -> str:
    check = "\n".join(f"{k}={v}" for k, v in sorted(fields.items()))
    secret = hmac.new(b"WebAppData", token.encode(), hashlib.sha256).digest()
    h = hmac.new(secret, check.encode(), hashlib.sha256).hexdigest()
    return urlencode({**fields, "hash": h})


def fields(user_id=42, age=0):
    return {
        "auth_date": str(int(time.time()) - age),
        "query_id": "AAA",
        "user": json.dumps({"id": user_id, "first_name": "Tester", "username": "tester"}),
    }


class TestAuth(unittest.TestCase):
    def test_valid(self):
        user = validate_init_data(sign(fields()), TOKEN)
        self.assertEqual(user["id"], 42)

    def test_wrong_token(self):
        with self.assertRaises(AuthError):
            validate_init_data(sign(fields(), "999:OTHER"), TOKEN)

    def test_tampered_user(self):
        data = sign(fields(user_id=42))
        tampered = data.replace("%22id%22%3A+42", "%22id%22%3A+7")
        self.assertNotEqual(data, tampered)
        with self.assertRaises(AuthError):
            validate_init_data(tampered, TOKEN)

    def test_expired(self):
        with self.assertRaises(AuthError):
            validate_init_data(sign(fields(age=100000)), TOKEN)

    def test_missing_hash_and_empty(self):
        with self.assertRaises(AuthError):
            validate_init_data(urlencode(fields()), TOKEN)
        with self.assertRaises(AuthError):
            validate_init_data("", TOKEN)


if __name__ == "__main__":
    unittest.main()
