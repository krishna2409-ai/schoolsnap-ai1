"""End-to-end test: takes a selfie from DB, re-scans it, and verifies matching works."""
import os, json, sqlite3, requests

BASE = "http://localhost:8000"
DB_PATH = r"D:\Projects\SNAP!\backend\schoolsnap.db"

# Step 1: Get a user with a child that has real selfies
conn = sqlite3.connect(DB_PATH)
conn.row_factory = sqlite3.Row

children = conn.execute("""
    SELECT c.id as child_id, c.name, c.user_id, u.email, COUNT(s.id) as selfie_count
    FROM children c 
    JOIN users u ON u.id = c.user_id
    JOIN selfies s ON s.child_id = c.id
    WHERE s.embedding_json IS NOT NULL
    GROUP BY c.id
    ORDER BY selfie_count DESC
""").fetchall()

print(f"Children with real selfies: {len(children)}")
for c in children:
    print(f"  {c['name']} ({c['selfie_count']} selfies) - user: {c['email']}")

if len(children) == 0:
    print("No children with selfies found!")
    exit(1)

# Pick first child
target = children[0]
print(f"\nTesting with: {target['name']} (user: {target['email']})")

# Step 2: Get one of their selfie files to use as the scan image
selfie = conn.execute(
    "SELECT file_path FROM selfies WHERE child_id = ? AND embedding_json IS NOT NULL LIMIT 1",
    (target["child_id"],)
).fetchone()
conn.close()

test_image = selfie["file_path"]
if not os.path.isabs(test_image):
    test_image = os.path.join("backend", test_image)
print(f"Using selfie as scan input: {test_image}")
print(f"File exists: {os.path.exists(test_image)}, size: {os.path.getsize(test_image)} bytes")

# Step 3: Login  
# First get credentials
creds_r = requests.get(f"{BASE}/demo/credentials")
creds = creds_r.json()
print(f"\nAvailable credentials: {len(creds)}")
for c in creds:
    print(f"  {c['registration_number']} / {c['dob']} / {c['child_name']}")

# Find matching credential
matching = [c for c in creds if c["child_name"] == target["name"]]
if not matching:
    print(f"No credential for {target['name']}! Using first available.")
    matching = [creds[0]]

cred = matching[0]
print(f"\nLogging in with: {cred['registration_number']} / {cred['dob']}")

login_r = requests.post(f"{BASE}/parent-login", data={
    "registration_number": cred["registration_number"],
    "dob": cred["dob"],
})
if login_r.status_code != 200:
    print(f"Login failed: {login_r.status_code} {login_r.text}")
    exit(1)

session = login_r.json()
token = session["token"]
print(f"Login OK! Token: {token[:20]}..., child: {session['child_name']}")

# Step 4: Scan the selfie (should match with high similarity!)
print(f"\nScanning selfie image for face match...")
with open(test_image, "rb") as f:
    scan_r = requests.post(
        f"{BASE}/parent/scan-and-match",
        data={"token": token},
        files={"file": ("scan.jpg", f, "image/jpeg")},
    )

result = scan_r.json()
print(f"\nScan result: {json.dumps(result, indent=2)}")
print(f"\n{'='*50}")
print(f"Status: {result['status']}")
print(f"Message: {result['message']}")
print(f"Matches: {len(result.get('matches', []))}")
if result.get("matches"):
    for m in result["matches"]:
        print(f"  Photo {m['id'][:8]}...: {m['confidence_pct']}% ({m['source']})")
