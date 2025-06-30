import sqlite3

conn = sqlite3.connect('send2290.db')
cursor = conn.cursor()

# Get all tables
cursor.execute("SELECT name FROM sqlite_master WHERE type='table'")
tables = cursor.fetchall()
print("Tables:", [t[0] for t in tables])

# If there's a submissions table, check it
try:
    cursor.execute("SELECT DISTINCT used_month FROM submission_data ORDER BY used_month")
    months = cursor.fetchall()
    print("Available months in submission_data:", [m[0] for m in months if m[0]])
except Exception as e:
    print("Error querying submission_data:", e)

# Check latest submissions
try:
    cursor.execute("SELECT id, user_uid, month, form_data FROM submissions ORDER BY id DESC LIMIT 5")
    recent = cursor.fetchall()
    print("Recent submissions:")
    for r in recent:
        print(f"  ID: {r[0]}, User: {r[1]}, Month: {r[2]}")
        if r[3]:
            import json
            try:
                form_data = json.loads(r[3])
                vehicles = form_data.get('vehicles', [])
                print(f"    Vehicles: {len(vehicles)}")
                for i, v in enumerate(vehicles[:3]):  # Show first 3 vehicles
                    print(f"      Vehicle {i+1}: month={v.get('used_month', 'N/A')}, vin={v.get('vin', 'N/A')[:8]}...")
            except Exception as e:
                print(f"    Error parsing form_data: {e}")
except Exception as e:
    print("Error querying recent submissions:", e)

conn.close()
