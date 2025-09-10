#!/usr/bin/env python3
"""
Environment variables checker for Railway deployment
"""
import os
import secrets

required_vars = [
    "DATABASE_URL",
    "REDIS_URL", 
    "JWT_SECRET",
    "JWT_REFRESH_SECRET",
    "S3_BUCKET",
    "S3_ACCESS_KEY_ID", 
    "S3_SECRET_ACCESS_KEY",
    "STORAGE_PUBLIC_BASE",
    "OPENAI_API_KEY"
]

def check_environment():
    print("🔍 Checking Railway Environment Variables...")
    print("=" * 50)
    
    missing_vars = []
    for var in required_vars:
        value = os.getenv(var)
        if value:
            # Don't expose secrets in logs, just show first/last chars
            if "SECRET" in var or "KEY" in var:
                display_value = f"{value[:4]}...{value[-4:]}" if len(value) > 8 else "***"
            elif "URL" in var:
                display_value = value[:50] + "..." if len(value) > 50 else value
            else:
                display_value = value[:30] + "..." if len(value) > 30 else value
            
            print(f"✅ {var}: {display_value}")
        else:
            print(f"❌ {var}: MISSING!")
            missing_vars.append(var)
    
    print("=" * 50)
    
    if missing_vars:
        print(f"🚨 {len(missing_vars)} MISSING variables:")
        for var in missing_vars:
            if var == "JWT_SECRET":
                suggestion = secrets.token_urlsafe(64)
                print(f"   {var}={suggestion}")
            elif var == "JWT_REFRESH_SECRET": 
                suggestion = secrets.token_urlsafe(64)
                print(f"   {var}={suggestion}")
            else:
                print(f"   {var}=<YOUR_VALUE_HERE>")
        print("\n🔧 Add these to Railway environment variables!")
        return False
    else:
        print("✅ All environment variables are present!")
        return True

if __name__ == "__main__":
    check_environment()