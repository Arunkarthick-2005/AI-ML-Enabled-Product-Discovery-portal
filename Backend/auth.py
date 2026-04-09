from passlib.context import CryptContext
from jose import jwt
from datetime import datetime, timedelta

# -----------------------------
# PASSWORD CONTEXT (Argon2)
# -----------------------------
pwd_context = CryptContext(
    schemes=["argon2"],
    deprecated="auto"
)

# -----------------------------
# JWT CONFIG
# -----------------------------
SECRET_KEY = "SUPER_SECRET_KEY_CHANGE_THIS"
ALGORITHM = "HS256"
ACCESS_TOKEN_EXPIRE_MINUTES = 60

# -----------------------------
# PASSWORD FUNCTIONS
# -----------------------------
def hash_password(password: str) -> str:
    return pwd_context.hash(password)

def verify_password(password: str, hashed: str) -> bool:
    return pwd_context.verify(password, hashed)

# -----------------------------
# JWT TOKEN
# -----------------------------
def create_access_token(data: dict):
    to_encode = data.copy()
    expire = datetime.utcnow() + timedelta(
        minutes=ACCESS_TOKEN_EXPIRE_MINUTES
    )
    to_encode.update({"exp": expire})
    return jwt.encode(to_encode, SECRET_KEY, algorithm=ALGORITHM)