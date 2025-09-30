"""
project/config_validator.py

Validate configuration on startup
"""

import os
import sys
from project.config import settings


class ConfigValidator:
    def __init__(self):
        self.errors = []
        self.warnings = []

    def validate_database(self):
        """Validate database configuration"""
        if not settings.DATABASE_URL:
            self.errors.append("DATABASE_URL not set")

        if settings.DATABASE_URL and settings.DATABASE_URL.startswith(
            "sqlite"
        ):
            self.warnings.append(
                "Using SQLite - not recommended for production"
            )

    def validate_security(self):
        """Validate security settings"""
        if settings.SECRET_KEY == "dev-only-key-change-in-production":
            self.errors.append(
                "Using default SECRET_KEY - must change for production"
            )

        if len(settings.SECRET_KEY) < 32:
            self.errors.append("SECRET_KEY too short - minimum 32 characters")

        if settings.ACCESS_TOKEN_EXPIRE_MINUTES > 600000:
            self.warnings.append(
                "Access token expiry > 60 minutes may be insecure"
            )

    def validate_celery(self):
        """Validate Celery configuration"""
        if not settings.CELERY_BROKER_URL:
            self.errors.append("CELERY_BROKER_URL not set")

        if not settings.CELERY_RESULT_BACKEND:
            self.errors.append("CELERY_RESULT_BACKEND not set")

    def validate_environment(self):
        """Validate environment-specific settings"""
        if settings.FASTAPI_CONFIG == "production":
            if settings.DEBUG:
                self.errors.append("DEBUG=True in production")

        required_env_vars = ["DATABASE_URL", "CELERY_BROKER_URL", "SECRET_KEY"]

        for var in required_env_vars:
            if not os.environ.get(var):
                self.errors.append(
                    f"Required environment variable {var} not set"
                )

    def validate_all(self):
        """Run all validations"""
        self.validate_database()
        self.validate_security()
        self.validate_celery()
        self.validate_environment()

        return self.errors, self.warnings

    def check_and_exit_on_errors(self):
        """Validate and exit if critical errors found"""
        errors, warnings = self.validate_all()

        if warnings:
            print("⚠️  Configuration Warnings:")
            for warning in warnings:
                print(f"   - {warning}")
            print()

        if errors:
            print("❌ Configuration Errors:")
            for error in errors:
                print(f"   - {error}")
            print("\n💡 Fix these errors before starting the application")
            sys.exit(1)

        print("✅ Configuration validation passed")


# Run validation on import
config_validator = ConfigValidator()
