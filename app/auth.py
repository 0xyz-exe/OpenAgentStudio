"""Password, session-token and CSRF helpers for the local single-owner bootstrap."""

import base64
import hashlib
import hmac
import os

_PBKDF2_ROUNDS = 600_000
_DUMMY_SALT = b"open-agent-studio-dummy"
_DUMMY_HASH = hashlib.pbkdf2_hmac("sha256", b"unusable", _DUMMY_SALT, _PBKDF2_ROUNDS)


def hash_password(password: str) -> str:
    salt = os.urandom(16)
    digest = hashlib.pbkdf2_hmac("sha256", password.encode("utf-8"), salt, _PBKDF2_ROUNDS)
    return "pbkdf2_sha256${}${}${}".format(
        _PBKDF2_ROUNDS,
        base64.urlsafe_b64encode(salt).decode("ascii"),
        base64.urlsafe_b64encode(digest).decode("ascii"),
    )


def verify_password(password: str, stored_hash: str | None) -> bool:
    if stored_hash is None:
        expected = _DUMMY_HASH
        salt = _DUMMY_SALT
        rounds = _PBKDF2_ROUNDS
    else:
        try:
            algorithm, round_text, salt_text, digest_text = stored_hash.split("$", 3)
            if algorithm != "pbkdf2_sha256":
                return False
            rounds = int(round_text)
            if not 100_000 <= rounds <= 2_000_000:
                return False
            salt = base64.urlsafe_b64decode(salt_text.encode("ascii"))
            expected = base64.urlsafe_b64decode(digest_text.encode("ascii"))
        except (ValueError, TypeError):
            return False
    actual = hashlib.pbkdf2_hmac("sha256", password.encode("utf-8"), salt, rounds)
    return hmac.compare_digest(actual, expected)


def new_secret() -> str:
    return base64.urlsafe_b64encode(os.urandom(32)).rstrip(b"=").decode("ascii")


def hash_secret(secret: str) -> str:
    return hashlib.sha256(secret.encode("ascii")).hexdigest()
