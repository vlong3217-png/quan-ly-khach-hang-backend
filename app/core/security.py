import os
import uuid
from datetime import datetime, timedelta, timezone
from jose import jwt, JWTError
import bcrypt

SECRET_KEY = os.getenv("SECRET_KEY", "change-this-secret-key")
ALGORITHM = os.getenv("ALGORITHM", "HS256")
ACCESS_TOKEN_EXPIRE_MINUTES = int(os.getenv("ACCESS_TOKEN_EXPIRE_MINUTES", "60"))


def verify_password(
    plain_password: str,
    hashed_password: str
) -> bool:
    try:
        return bcrypt.checkpw(
            plain_password.encode("utf-8")[:72],
            hashed_password.encode("utf-8")
        )
    except Exception:
        return False


def hash_password(password: str) -> str:
    pwd_bytes = password.encode("utf-8")[:72]
    salt = bcrypt.gensalt()
    return bcrypt.hashpw(pwd_bytes, salt).decode("utf-8")


class PwdContext:
    @staticmethod
    def verify(secret: str, hashed: str) -> bool:
        return verify_password(secret, hashed)

    @staticmethod
    def hash(secret: str) -> str:
        return hash_password(secret)


pwd_context = PwdContext()


def create_access_token(data: dict) -> str:
    payload = data.copy()
    expire = datetime.now(timezone.utc) + timedelta(
        minutes=ACCESS_TOKEN_EXPIRE_MINUTES
    )
    payload.update({
        "exp": expire,
        "jti": str(uuid.uuid4()),
    })
    return jwt.encode(
        payload,
        SECRET_KEY,
        algorithm=ALGORITHM
    )


def decode_access_token(token: str) -> dict | None:
    try:
        return jwt.decode(
            token,
            SECRET_KEY,
            algorithms=[ALGORITHM]
        )
    except JWTError:
        return None
