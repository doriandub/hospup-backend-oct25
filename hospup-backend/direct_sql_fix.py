#!/usr/bin/env python3
"""
🔧 CRITICAL FIX: Apply database migration using simple psycopg2

This bypasses complex dependencies and directly executes the SQL fix.
Based on log analysis: null value in column "file_url" violates not-null constraint

SOLUTION: ALTER TABLE videos ALTER COLUMN file_url DROP NOT NULL;
"""

import os
import sys

# Try psycopg2 (common PostgreSQL driver)
try:
    import psycopg2
    from urllib.parse import urlparse
except ImportError:
    print("❌ Missing psycopg2: pip install psycopg2-binary")
    sys.exit(1)

def apply_fix():
    """Apply the NOT NULL constraint fix directly"""
    
    print("🔧 CRITICAL DATABASE FIX")
    print("Problem: videos.file_url has NOT NULL constraint")
    print("Solution: Make it nullable for generated videos")
    print("=" * 50)
    
    # Get DATABASE_URL from environment or manual input
    DATABASE_URL = os.getenv('DATABASE_URL')
    
    if not DATABASE_URL:
        print("⚠️  DATABASE_URL not found in environment")
        print("Based on logs, your DB is: aws-1-eu-west-1.pooler.supabase.com")
        DATABASE_URL = input("Enter complete DATABASE_URL: ").strip()
    
    if not DATABASE_URL:
        print("❌ DATABASE_URL is required")
        return False
    
    try:
        # Parse URL components
        parsed = urlparse(DATABASE_URL)
        print(f"🔌 Connecting to: {parsed.hostname}")
        
        # Connect to database
        conn = psycopg2.connect(DATABASE_URL)
        cur = conn.cursor()
        
        print("✅ Connected to database")
        
        # Check current constraint
        cur.execute("""
            SELECT column_name, is_nullable 
            FROM information_schema.columns 
            WHERE table_name = 'videos' AND column_name = 'file_url'
        """)
        
        result = cur.fetchone()
        
        if result:
            column_name, is_nullable = result
            print(f"📋 Current file_url constraint: nullable={is_nullable}")
            
            if is_nullable == 'NO':
                print("🔧 Applying fix: ALTER TABLE videos ALTER COLUMN file_url DROP NOT NULL")
                
                # Apply the fix
                cur.execute("ALTER TABLE videos ALTER COLUMN file_url DROP NOT NULL")
                
                # Clean up existing empty strings
                cur.execute("UPDATE videos SET file_url = NULL WHERE file_url = ''")
                updated_rows = cur.rowcount
                
                # Commit changes
                conn.commit()
                
                print(f"✅ SUCCESS: Constraint removed!")
                print(f"✅ Updated {updated_rows} empty file_url records to NULL")
                
                # Verify the change
                cur.execute("""
                    SELECT column_name, is_nullable 
                    FROM information_schema.columns 
                    WHERE table_name = 'videos' AND column_name = 'file_url'
                """)
                
                new_result = cur.fetchone()
                if new_result:
                    _, new_nullable = new_result
                    print(f"✅ Verified: file_url nullable={new_nullable}")
                
                return True
            else:
                print("✅ Fix already applied: file_url is already nullable")
                return True
        else:
            print("❌ Cannot find videos.file_url column")
            return False
            
    except Exception as e:
        print(f"❌ Error: {e}")
        return False
    finally:
        if 'conn' in locals():
            conn.close()
            print("🔌 Database connection closed")

if __name__ == "__main__":
    success = apply_fix()
    
    if success:
        print("🎉 MISSION ACCOMPLISHED!")
        print("💡 Video generation should now work without HTTP 500 errors")
    else:
        print("❌ Fix failed - manual intervention may be required")
    
    sys.exit(0 if success else 1)