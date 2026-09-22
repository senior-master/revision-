import json

# Read the file
with open('questions.json', 'r') as f:
    content = f.read()

# Find where Paper 1 ends (after question 250)
# Look for the pattern "}]" followed by "[" 
content = content.replace('}]', '}],', 1)

# Write back
with open('questions.json', 'w') as f:
    f.write(content)

# Verify
try:
    with open('questions.json', 'r') as f:
        data = json.load(f)
    print(f"✅ JSON fixed! Total questions: {len(data)}")
except json.JSONDecodeError as e:
    print(f"❌ Still error: {e}")
