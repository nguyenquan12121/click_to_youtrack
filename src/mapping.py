from pathlib import Path

import json

# mapping GH issue number -> YouTrack id
MAPPINGS_PATH = Path("mappings.json")
if not MAPPINGS_PATH.exists():
    MAPPINGS_PATH.write_text(json.dumps({}), encoding="utf-8")

def load_mappings():
    try:
        return json.loads(MAPPINGS_PATH.read_text(encoding="utf-8") or "{}")
    except Exception:
        return {}

def save_mappings(m):
    try:
        MAPPINGS_PATH.write_text(json.dumps(m, indent=2), encoding="utf-8")
    except Exception:
        pass

def add_mapping(github_number: int, youtrack_id: str):
    m = load_mappings()
    m[str(github_number)] = youtrack_id
    save_mappings(m)

def get_mapped_youtrack_id(github_number: int):
    return load_mappings().get(str(github_number))

def remove_mapping(github_number: int):
    m = load_mappings()
    if str(github_number) in m:
        m.pop(str(github_number))
        save_mappings(m)