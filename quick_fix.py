import json

# Read the file
with open('questions.json', 'r') as f:
    content = f.read()

# Fix the triple comma issue
content = content.replace(',,,', ',')

# Write back
with open('questions.json', 'w') as f:
    f.write(content)

# Verify
try:
    with open('questions.json', 'r') as f:
        data = json.load(f)
    print(f"✅ SUCCESS! JSON is valid with {len(data)} questions")
    print("Run ./quiz500.sh to test!")
except json.JSONDecodeError as e:
    print(f"❌ Still has error: {e}")
