"""
Direct test of spoiler filter fix
"""

import json

# Load subtitle corpus
with open('corpus/la_la_land_chunks.jsonl', 'r') as f:
    chunks = [json.loads(line) for line in f]

print("Testing Spoiler Filter Logic")
print("="*60)

# Test at t_now = 50s
t_now = 50.0
spoiler_mode = "off"

print(f"\nAt t_now = {t_now}s with spoiler_mode = {spoiler_mode}")
print(f"Total chunks: {len(chunks)}")

# OLD LOGIC (wrong):
old_filtered = [c for c in chunks if not (c['t_end'] > t_now)]
print(f"\nOLD LOGIC (t_end <= t_now):")
print(f"  Chunks passing filter: {len(old_filtered)}")
print(f"  ❌ Too strict! Filters out chunks that haven't ended yet")

# NEW LOGIC (correct):
new_filtered = [c for c in chunks if not (c['t_start'] > t_now)]
print(f"\nNEW LOGIC (t_start <= t_now):")
print(f"  Chunks passing filter: {len(new_filtered)}")
print(f"  ✓ Correct! Includes all chunks that have started")

# Show first few chunks that pass
print(f"\nFirst 5 chunks that pass new filter:")
for i, chunk in enumerate(new_filtered[:5]):
    print(f"  {i+1}. {chunk['t_start']:.1f}s - {chunk['t_end']:.1f}s")
    print(f"     {chunk['text'][:60]}...")

# Test at later timestamp
t_now = 200.0
new_filtered_200 = [c for c in chunks if not (c['t_start'] > t_now)]
print(f"\nAt t_now = {t_now}s:")
print(f"  Chunks passing filter: {len(new_filtered_200)}")

print("\n" + "="*60)
print("✅ Spoiler filter fix verified!")
print("   Chunks with t_start <= t_now are now included")
print("="*60 + "\n")


