import json

# Read the file
with open('questions.json', 'r') as f:
    content = f.read()

# Find where the array ends with "]"
# We need to merge everything into one array

# Remove the stray "]" and the stray "," between 250 and 251
# Pattern: "answer":"D"}] , {"id":251
# Replace with: "answer":"D"}, {"id":251

content = content.replace('"answer":"D"}] , {"id":251', '"answer":"D"}, {"id":251')

# Also fix the triple comma from earlier
content = content.replace(',,,', ',')

# Find the last "]" and remove it (we'll add it back)
# Actually, we need to find where the array ends
# Remove the final "]" and then add it back at the end

# Write back
with open('questions_fixed.json', 'w') as f:
    f.write(content)

# Try to parse
try:
    with open('questions_fixed.json', 'r') as f:
        data = json.load(f)
    print(f"✅ SUCCESS! Found {len(data)} questions")
    # Replace original
    import shutil
    shutil.move('questions_fixed.json', 'questions.json')
    print("✅ Fixed! Run ./quiz500.sh")
except json.JSONDecodeError as e:
    print(f"❌ Still has error: {e}")
    print("Line:", e.lineno, "Column:", e.colno)
