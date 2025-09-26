import json
from collections import defaultdict

# Load JSON file
with open("trading/example-game.json", "r", encoding="utf-8") as f:
    data = json.load(f)

# Dictionary where keys = field names, values = sets of unique values
unique_values = defaultdict(set)

# Go through each record
for record in data:
    for key, value in record.items():
        unique_values[key].add(value)

# Convert sets to sorted lists (optional, easier to read)
unique_values = {k: sorted(v, key=lambda x: (x is None, x)) for k, v in unique_values.items()}

# Print results
for field, values in unique_values.items():
    print(f"{field}: {values}")
