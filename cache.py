from pathlib import Path
from urllib.parse import parse_qs, urlencode, urlparse
import uuid
from dotenv import load_dotenv
from flask import Flask, Response, request, render_template, redirect, jsonify, url_for, session
from flask_cors import CORS
from dateutil import parser

import json
import os
import requests
import re
import time



CACHE_DIR = Path("issues_cache")
CACHE_DIR.mkdir(parents=True, exist_ok=True)
# Save issues to a JSON file and return the filename (cache key)
def save_issues_to_file(issues, repo_url=None):

    key = f"{uuid.uuid4().hex}.json"
    file_path = CACHE_DIR / key
    with open(file_path, "w", encoding="utf-8") as f:
        json.dump(issues, f, indent=2)
    return str(file_path)
#Load issues back from the JSON file.
def load_issues_from_file(path):
    try:
        with open(path, "r", encoding="utf-8") as f:
            return json.load(f)
    except Exception:
        return []