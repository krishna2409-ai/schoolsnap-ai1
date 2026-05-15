"""Input validation and sanitization utilities"""
import os
import re
from typing import Optional, List
from fastapi import HTTPException, status

# File validation
ALLOWED_IMAGE_EXTENSIONS = {".jpg", ".jpeg", ".png", ".gif", ".webp"}
ALLOWED_IMAGE_MIMETYPES = {"image/jpeg", "image/png", "image/gif", "image/webp"}
MAX_FILE_SIZE_BYTES = int(os.getenv("MAX_UPLOAD_SIZE_MB", "100")) * 1024 * 1024


class ValidationError(HTTPException):
    """Custom validation error"""
    def __init__(self, message: str):
        super().__init__(
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
            detail={"error": "validation_error", "message": message}
        )


def validate_registration_number(reg_number: str) -> str:
    """Validate and sanitize registration number"""
    if not reg_number or not isinstance(reg_number, str):
        raise ValidationError("Registration number is required and must be a string")
    
    reg_number = reg_number.strip()
    if len(reg_number) < 3 or len(reg_number) > 50:
        raise ValidationError("Registration number must be between 3 and 50 characters")
    
    if not re.match(r"^[A-Za-z0-9_-]+$", reg_number):
        raise ValidationError("Registration number can only contain alphanumeric characters, dashes, and underscores")
    
    return reg_number


def validate_date_of_birth(dob: str) -> str:
    """Validate date of birth format (YYYY-MM-DD)"""
    if not dob or not isinstance(dob, str):
        raise ValidationError("Date of birth is required")
    
    dob = dob.strip()
    if not re.match(r"^\d{4}-\d{2}-\d{2}$", dob):
        raise ValidationError("Date of birth must be in YYYY-MM-DD format")
    
    # Basic sanity check
    try:
        year, month, day = map(int, dob.split("-"))
        if not (1900 <= year <= 2025) or not (1 <= month <= 12) or not (1 <= day <= 31):
            raise ValueError
    except (ValueError, IndexError):
        raise ValidationError("Invalid date of birth")
    
    return dob


def validate_email(email: str) -> str:
    """Validate email format"""
    if not email or not isinstance(email, str):
        raise ValidationError("Email is required")
    
    email = email.strip().lower()
    if len(email) > 255 or len(email) < 5:
        raise ValidationError("Email must be between 5 and 255 characters")
    
    if not re.match(r"^[a-zA-Z0-9._%+-]+@[a-zA-Z0-9.-]+\.[a-zA-Z]{2,}$", email):
        raise ValidationError("Invalid email format")
    
    return email


def validate_child_name(name: str) -> str:
    """Validate child name"""
    if not name or not isinstance(name, str):
        raise ValidationError("Child name is required")
    
    name = name.strip()
    if len(name) < 2 or len(name) > 100:
        raise ValidationError("Child name must be between 2 and 100 characters")
    
    if not re.match(r"^[a-zA-Z\s'-]+$", name):
        raise ValidationError("Child name can only contain letters, spaces, hyphens, and apostrophes")
    
    return name


def validate_password(password: str) -> str:
    """Validate password strength"""
    if not password or not isinstance(password, str):
        raise ValidationError("Password is required")
    
    if len(password) < 6 or len(password) > 128:
        raise ValidationError("Password must be between 6 and 128 characters")
    
    return password


def validate_file_upload(filename: str, file_size: int, mimetype: str) -> None:
    """Validate file upload"""
    if not filename:
        raise ValidationError("Filename is required")
    
    if file_size > MAX_FILE_SIZE_BYTES:
        raise ValidationError(f"File size exceeds maximum allowed ({MAX_FILE_SIZE_BYTES // 1024 // 1024}MB)")
    
    if file_size == 0:
        raise ValidationError("File is empty")
    
    # Check file extension
    file_ext = os.path.splitext(filename)[1].lower()
    if file_ext not in ALLOWED_IMAGE_EXTENSIONS:
        raise ValidationError(f"File type not allowed. Allowed types: {', '.join(ALLOWED_IMAGE_EXTENSIONS)}")
    
    # Check MIME type
    if mimetype not in ALLOWED_IMAGE_MIMETYPES:
        raise ValidationError(f"Invalid MIME type. Allowed types: {', '.join(ALLOWED_IMAGE_MIMETYPES)}")


def validate_token(token: Optional[str]) -> str:
    """Validate JWT token format"""
    if not token or not isinstance(token, str):
        raise ValidationError("Token is required")
    
    token = token.strip()
    if len(token) < 10 or len(token) > 2000:
        raise ValidationError("Invalid token format")
    
    # JWT tokens have 3 parts separated by dots
    if token.count(".") != 2:
        raise ValidationError("Invalid token format")
    
    return token


def sanitize_filename(filename: str) -> str:
    """Sanitize filename to prevent directory traversal attacks"""
    # Remove any path components
    filename = os.path.basename(filename)
    
    # Remove potentially dangerous characters
    filename = re.sub(r'[^\w\s.-]', '', filename)
    
    # Limit length
    if len(filename) > 255:
        name, ext = os.path.splitext(filename)
        filename = name[:250] + ext
    
    return filename
