import json

with open("data/test/manifest.json") as f:
    manifest = json.load(f)

print(json.dumps(manifest, indent=2)[:2000])  # first chunk, to see the structure