"""CORS and security configuration for production"""
import os
from typing import List

# Load from environment
ENVIRONMENT = os.getenv("ENVIRONMENT", "development")
DEBUG = os.getenv("DEBUG", "False").lower() == "true"

# Parse CORS origins from environment
CORS_ORIGINS_STRING = os.getenv("CORS_ORIGINS", "http://localhost:3000,http://localhost:5173")
CORS_ORIGINS: List[str] = [origin.strip() for origin in CORS_ORIGINS_STRING.split(",")]

# CORS configuration
CORS_CONFIG = {
    "allow_origins": CORS_ORIGINS if not DEBUG else ["*"],
    "allow_credentials": os.getenv("CORS_ALLOW_CREDENTIALS", "true").lower() == "true",
    "allow_methods": ["GET", "POST", "PUT", "DELETE", "PATCH", "OPTIONS"],
    "allow_headers": ["*"],
    "expose_headers": ["Content-Length", "Content-Range"],
    "max_age": 600 if ENVIRONMENT == "production" else 3600,
}

# Security headers
SECURITY_HEADERS = {
    "X-Content-Type-Options": "nosniff",
    "X-Frame-Options": "DENY",
    "X-XSS-Protection": "1; mode=block",
    "Strict-Transport-Security": "max-age=31536000; includeSubDomains" if ENVIRONMENT == "production" else None,
    "Content-Security-Policy": "default-src 'self'" if ENVIRONMENT == "production" else None,
}

# Remove None values
SECURITY_HEADERS = {k: v for k, v in SECURITY_HEADERS.items() if v}

# Log configuration
if ENVIRONMENT == "production" and DEBUG:
    raise ValueError("⚠️ Cannot have DEBUG=true in production environment")

if ENVIRONMENT == "production" and "*" in CORS_ORIGINS:
    raise ValueError("⚠️ Cannot use wildcard CORS origins in production")
