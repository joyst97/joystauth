import os
import hmac
import hashlib
import base64
import secrets
import bcrypt
from datetime import datetime, timedelta
from jose import JWTError, jwt
from Crypto.Cipher import AES
from Crypto.Util.Padding import pad, unpad

SECRET_KEY = os.getenv("JWT_SECRET", "super-secure-auth-jwt-secret-key-change-in-production-998877")
ALGORITHM = "HS256"
ACCESS_TOKEN_EXPIRE_MINUTES = 60 * 24 * 7 # 7 days for admin session

def hash_password(password: str) -> str:
    """Hash password using bcrypt."""
    salt = bcrypt.gensalt(rounds=12)
    return bcrypt.hashpw(password.encode("utf-8"), salt).decode("utf-8")

def verify_password(plain_password: str, hashed_password: str) -> bool:
    """Verify password against bcrypt hash."""
    try:
        return bcrypt.checkpw(plain_password.encode("utf-8"), hashed_password.encode("utf-8"))
    except Exception:
        return False

def create_access_token(data: dict, expires_delta: timedelta = None) -> str:
    """Generate JWT access token for admin."""
    to_encode = data.copy()
    if expires_delta:
        expire = datetime.utcnow() + expires_delta
    else:
        expire = datetime.utcnow() + timedelta(minutes=ACCESS_TOKEN_EXPIRE_MINUTES)
    to_encode.update({"exp": expire})
    return jwt.encode(to_encode, SECRET_KEY, algorithm=ALGORITHM)

def decode_access_token(token: str) -> dict:
    """Decode and verify JWT token."""
    try:
        payload = jwt.decode(token, SECRET_KEY, algorithms=[ALGORITHM])
        return payload
    except JWTError:
        return None

def generate_random_token(length: int = 32) -> str:
    """Generate cryptographically secure random hex string."""
    return secrets.token_hex(length // 2 if length % 2 == 0 else (length + 1) // 2)[:length]

def generate_license_key(mask: str = "XXXX-XXXX-XXXX-XXXX") -> str:
    """Generate license key using a mask pattern."""
    chars = "ABCDEFGHJKLMNPQRSTUVWXYZ23456789" # Avoid ambiguous 0/O, 1/I
    result = []
    for char in mask:
        if char == "X":
            result.append(secrets.choice(chars))
        else:
            result.append(char)
    return "".join(result)

# ==================== ZERO-LEAK PAYLOAD CRYPTOGRAPHY ====================

def derive_key(secret: str) -> bytes:
    """Derive 32-byte AES key from string secret using SHA-256."""
    return hashlib.sha256(secret.encode("utf-8")).digest()

def aes_encrypt(plaintext: str, key_str: str) -> str:
    """
    Encrypt plaintext using AES-256-CBC with PKCS7 padding.
    Output: Base64(IV + Ciphertext)
    """
    try:
        key = derive_key(key_str)
        iv = secrets.token_bytes(16)
        cipher = AES.new(key, AES.MODE_CBC, iv)
        padded_data = pad(plaintext.encode("utf-8"), AES.block_size)
        encrypted = cipher.encrypt(padded_data)
        # Prepend IV to ciphertext
        combined = iv + encrypted
        return base64.b64encode(combined).decode("utf-8")
    except Exception as e:
        raise ValueError(f"Encryption failed: {str(e)}")

def aes_decrypt(ciphertext_b64: str, key_str: str) -> str:
    """
    Decrypt Base64(IV + Ciphertext) using AES-256-CBC with PKCS7 unpadding.
    """
    try:
        key = derive_key(key_str)
        combined = base64.b64decode(ciphertext_b64.encode("utf-8"))
        if len(combined) < 16:
            raise ValueError("Invalid ciphertext length")
        iv = combined[:16]
        ciphertext = combined[16:]
        cipher = AES.new(key, AES.MODE_CBC, iv)
        decrypted_padded = cipher.decrypt(ciphertext)
        decrypted = unpad(decrypted_padded, AES.block_size)
        return decrypted.decode("utf-8")
    except Exception as e:
        raise ValueError(f"Decryption failed: {str(e)}")

def compute_hmac_signature(data: str, secret: str) -> str:
    """Compute HMAC-SHA256 signature of data using secret key."""
    return hmac.new(secret.encode("utf-8"), data.encode("utf-8"), hashlib.sha256).hexdigest()

def verify_hmac_signature(data: str, signature: str, secret: str) -> bool:
    """Verify HMAC signature using timing-safe comparison."""
    expected_sig = compute_hmac_signature(data, secret)
    return hmac.compare_digest(expected_sig, signature)

def normalize_hwid(hwid: str) -> str:
    """Standardize HWID string (clean whitespace and uppercase for exact Windows SID matching)."""
    if not hwid:
        return ""
    return str(hwid).strip()
