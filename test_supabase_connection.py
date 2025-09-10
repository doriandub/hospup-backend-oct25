#!/usr/bin/env python3
"""
Quick test to verify Supabase connection and templates data.
"""

import os
from sqlalchemy import create_engine, text
from sqlalchemy.orm import sessionmaker

def test_supabase():
    """Test Supabase connection and templates data."""
    
    # Supabase URL (direct connection, no pgbouncer param)
    DATABASE_URL = "postgresql://postgres.vvyhkjwymytnowsiwajm:.mvR66vs7YGQXJ#@aws-1-eu-west-1.pooler.supabase.com:6543/postgres"
    
    try:
        print("🔗 Testing Supabase connection...")
        
        # Create engine
        engine = create_engine(DATABASE_URL, echo=False)
        SessionLocal = sessionmaker(bind=engine)
        
        with SessionLocal() as session:
            # Test basic connection
            result = session.execute(text("SELECT 1 as test"))
            print("✅ Database connection successful")
            
            # Check templates table exists
            result = session.execute(text("SELECT COUNT(*) as count FROM templates"))
            count = result.fetchone()[0]
            print(f"📊 Templates table has {count} records")
            
            # Get sample template data
            result = session.execute(text("""
                SELECT id, hotel_name, country, views, script 
                FROM templates 
                WHERE is_active = true 
                ORDER BY views DESC 
                LIMIT 3
            """))
            
            templates = result.fetchall()
            print(f"\n🎯 Sample templates:")
            for template in templates:
                print(f"  - {template.hotel_name} ({template.country}) - {template.views:,} views")
                print(f"    ID: {template.id}")
                print(f"    Script type: {type(template.script)}")
                if template.script:
                    print(f"    Script keys: {list(template.script.keys()) if isinstance(template.script, dict) else 'Not a dict'}")
                print()
            
            return True
            
    except Exception as e:
        print(f"❌ Database connection failed: {str(e)}")
        return False

if __name__ == "__main__":
    test_supabase()