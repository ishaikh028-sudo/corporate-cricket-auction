import os
import csv
import sqlite3

# CONFIGURATION DEFINITIONS
CSV_FILE_NAME = 'registration_responses.csv'  # Your downloaded Google Sheet CSV
DB_PATH = os.path.join('instance', 'auction.db')
UPLOAD_FOLDER = os.path.join('app', 'static', 'uploads')

# AUCTION SETTINGS
DEFAULT_BASE_PRICE = 1000   # Default starting bid for imported players
DEFAULT_TEAM_PURSE = 100000  # Default budget reset for your teams (e.g., 1 Lakh)

def clean_and_import_data():
    # 1. Validation Checks
    if not os.path.exists(CSV_FILE_NAME):
        print(f"❌ Error: Could not find '{CSV_FILE_NAME}'. Please download your Google Sheet as a CSV and place it in this directory.")
        return

    if not os.path.exists(DB_PATH):
        print(f"❌ Error: Database not found at '{DB_PATH}'. Please run your Flask app once ('python run.py') to generate the structure first.")
        return

    print("🚀 Initializing anti-duplicate data bridge migration from Google Forms...")
    
    # 2. Database Connection
    conn = sqlite3.connect(DB_PATH)
    cursor = conn.cursor()

    # Verify if the structural tables actually exist before trying to run operations
    cursor.execute("SELECT name FROM sqlite_master WHERE type='table' AND name='player';")
    if not cursor.fetchone():
        print("❌ Error: The 'player' table structure does not exist inside the database yet.")
        print("💡 Quick Fix: Run your Flask application ('python run.py') so SQLAlchemy creates the tables, close it, and retry this script.")
        conn.close()
        return

    # 3. Clear Previous State (Clean Slate)
    print("🧹 Scrubbing old database data...")
    cursor.execute("DELETE FROM player")
    cursor.execute("UPDATE team SET purse = ?", (DEFAULT_TEAM_PURSE,))
    
    # 4. Process Photo Directory Pool
    uploaded_photos_pool = []
    if os.path.exists(UPLOAD_FOLDER):
        # Read files, ignoring system artifacts and default avatar icons
        uploaded_photos_pool = [f for f in os.listdir(UPLOAD_FOLDER) if f != "default_avatar.png"]
    else:
        print(f"⚠️ Warning: '{UPLOAD_FOLDER}' directory missing. Creating it now...")
        os.makedirs(UPLOAD_FOLDER, exist_ok=True)

    success_count = 0

    # 5. Core Data Extraction & Matching Loop
    with open(CSV_FILE_NAME, mode='r', encoding='utf-8') as file:
        reader = csv.DictReader(file)
        
        for row in reader:
            full_name = row['Name'].strip()
            department = row['Department'].strip()
            role = row['Category'].strip()
            
            if not full_name:
                continue

            matched_photo_name = "default_avatar.png"
            
            # Anti-Duplicate Matching Engine
            for file_name in uploaded_photos_pool:
                if full_name.lower() in file_name.lower():
                    matched_photo_name = file_name
                    # Pull this specific file out of the pool so the next person cannot claim it
                    uploaded_photos_pool.remove(file_name)
                    break
            
            # Database Injection mapped exactly to your SQLAlchemy structural schema attributes
            try:
                cursor.execute("""
                    INSERT INTO player (full_name, department, role, photo, base_price, sold_price, status, team_id)
                    VALUES (?, ?, ?, ?, ?, NULL, 'Available', NULL)
                """, (full_name, department, role, matched_photo_name, DEFAULT_BASE_PRICE))
                success_count += 1
                print(f"🎯 Unique Assigned: {full_name} ({department}) -> Photo: {matched_photo_name}")
            except sqlite3.Error as e:
                print(f"❌ Failed to insert player {full_name}: {e}")

    # 6. Secure Commit and Connection Termination
    conn.commit()
    conn.close()
    
    print("---")
    print(f"🎉 Migration Complete! Successfully injected {success_count} unique entries with clean team resets.")

if __name__ == '__main__':
    clean_and_import_data()