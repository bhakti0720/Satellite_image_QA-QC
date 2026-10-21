import json

with open("data/test/manifest.json") as f:
    manifest = json.load(f)

for path, info in manifest.items():
    print(path, "->", info)

print("\nDoes noisy_1 appear anywhere in the manifest?")
found = any("noisy_1" in k or info.get("defect") == "noisy_1" for k, info in manifest.items())
print(found)