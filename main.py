from pathlib import Path
from urllib.parse import parse_qs, urlencode, urlparse
import uuid
from dotenv import load_dotenv
from flask import Flask, Response, request, render_template, redirect, jsonify, url_for, session
from flask_cors import CORS
from youtrack_client import YouTrackClient

import json
import os
import requests
import re
import time

load_dotenv()

GITHUB_REPO = "https://github.com/strawberrymusicplayer/strawberry/"
GITHUB_ISSUE = "https://api.github.com/repos/strawberrymusicplayer/strawberry/issues?per_page=100"
GITHUB_TOKEN = os.getenv("GITHUB_TOKEN")
YOUTRACK_TOKEN = os.getenv("YOUTRACK_TOKEN")
YOUTRACK_REPO = "https://quan.youtrack.cloud/api/admin/projects?fields=id,name,shortName"
YOUTRACK_REPO_GET_FIELDS = "https://quan.youtrack.cloud/api/admin/projects?fields=assignee"

# --- Flask app and secret key (required for session) ---
app = Flask(__name__)
# Use an env var in production. Fallback to random key for dev only.
app.secret_key = os.getenv("FLASK_SECRET_KEY") or os.urandom(24)

CORS(app)

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
def convert_github_to_youtrack(project_name, issue_title, issue_body, issue_state):
    body = {
        "project": {
            "name": project_name,
            "id": "0-0",
            "$type": "Project"
        },
        "summary": issue_title,
        "description": issue_body or "No description provided",
        "customFields": [
            {
                "value": {
                    "name": "Normal",
                    "$type": "EnumBundleElement"
                },
                "name": "Priority",
                "$type": "SingleEnumIssueCustomField"
            },
            {
                "value": {
                    "name": "Bug",
                    "$type": "EnumBundleElement"
                },
                "name": "Type",
                "$type": "SingleEnumIssueCustomField"
            },
            {
                "value": {
                    "name": issue_state.capitalize() if issue_state else "Open",
                    "$type": "StateBundleElement"
                },
                "name": "State",
                "$type": "StateIssueCustomField"
            }
        ]
    }
    return body


def build_api_url_from_input(raw_url: str) -> str:
    """
    Simple GitHub URL to API URL converter
    Accepts:
      - https://github.com/owner/repo
      - https://github.com/owner/repo/issues
      - https://github.com/owner/repo/issues/123
    Returns:
      - https://api.github.com/repos/owner/repo/issues?per_page=100
    """
    url = raw_url.strip()
    if "api.github.com" in url:
        return url

    if "github.com" in url:
        parts = url.replace("https://", "").replace("http://", "").split("/")
        if "github.com" in parts:
            idx = parts.index("github.com")
            if len(parts) > idx + 2:
                owner = parts[idx + 1]
                repo = parts[idx + 2]
                return f"https://api.github.com/repos/{owner}/{repo}/issues?per_page=2"
    return ""


def import_one_issue_to_youtrack(youtrack_url, permanent_token, project_name, github_issue):
    youtrack_issue = convert_github_to_youtrack(
        project_name=project_name,
        issue_title=github_issue.get('title'),
        issue_body=github_issue.get('body'),
        issue_state=github_issue.get('state')
    )
    headers = {
        'Accept': 'application/json',
        'Authorization': f'Bearer {permanent_token}',
        'Content-Type': 'application/json'
    }
    url = youtrack_url.rstrip("/") + "/api/issues"
    print(url)
    print("\n\n\n")
    print(youtrack_issue)
    print("\n\n\n")

    try:
        response = requests.post(url, headers=headers, json=youtrack_issue)
        if response.status_code in (200, 201):
            return {
                'success': True,
                'issue_id': github_issue.get('number'),
                'youtrack_id': response.json().get('id'),
                'message': f"Issue #{github_issue.get('number')} imported successfully"
            }
        else:
            return {
                'success': False,
                'issue_id': github_issue.get('number'),
                'error': f"YouTrack API error: {response.status_code} - {response.text}",
                'message': f"Failed to import issue #{github_issue.get('number')}"
            }

    except Exception as e:
        return {
            'success': False,
            'issue_id': github_issue.get('number'),
            'error': str(e),
            'message': f"Error importing issue #{github_issue.get('number')}"
        }


def import_bulk_issues_to_youtrack(youtrack_url, permanent_token, project_name, github_issues):
    results = []
    for issue in github_issues:
        result = import_one_issue_to_youtrack(youtrack_url, permanent_token, project_name, issue)
        results.append(result)
        time.sleep(0.5)
    return results


def youtrack_req():
    global YOUTRACK_TOKEN, YOUTRACK_REPO_GET_FIELDS
    req = {
        "url": YOUTRACK_REPO_GET_FIELDS,
        "headers": {
            "Authorization": f'Bearer {YOUTRACK_TOKEN}',
            "Cache-Control": "no-cache",
            "Accept": "application/json",
            "Content-Type": "application/json"
        }
    }
    response = requests.get(url=req["url"], headers=req["headers"])
    response.raise_for_status()
    return response.json()


@app.route('/github', methods=['GET'])
def get_github_page():
    youtrack_url = session.get('youtrack_url')
    permanent_token = session.get('permanent_token')
    error = None
    issues = session.get('issues', None)
    github = ""
    submitted = False
    return render_template(
        'github.html',
        youtrack_url=youtrack_url,
        permanent_token=permanent_token,
        github=github,
        issues=issues,
        error=error,
        submitted=submitted
    )


@app.route('/github', methods=['POST'])
def github_page():
    youtrack_url = session.get('youtrack_url')
    permanent_token = session.get('permanent_token')
    error = None
    issues = None
    github = ""
    submitted = False

    # refresh local GITHUB_TOKEN from env (if changed)
    GITHUB_TOKEN_LOCAL = os.getenv("GITHUB_TOKEN", GITHUB_TOKEN)

    github = request.form.get('github', '').strip()
    GITHUB_REPO_REGEX = re.compile(
        r"^https://github\.com/[A-Za-z0-9_.-]+/[A-Za-z0-9_.-]+/?$"
    )
    if len(github) < 1:
        error = "URL cannot be empty."
        submitted = True
    elif not GITHUB_REPO_REGEX.match(github):
        error = "Invalid GitHub URL. Must be like: https://github.com/user/repo/"
        submitted = True
    else:
        github_issue_api = build_api_url_from_input(github)
        headers = {
            "Accept": "application/vnd.github+json"
        }
        # attach token if present
        if GITHUB_TOKEN_LOCAL:
            headers["Authorization"] = f"token {GITHUB_TOKEN_LOCAL}"

        response = requests.get(url=github_issue_api, headers=headers)
        if response.status_code == 200:
            issues = response.json()
            cache_file = save_issues_to_file(issues, repo_url=github)
            session['issues_file'] = cache_file   # only store file path in session
            submitted = True
        else:
            issues = [] 
            error = f"Error fetching issues: {response.status_code} - {response.text}"
            submitted = True

    return render_template(
        'github.html',
        youtrack_url=youtrack_url,
        permanent_token=permanent_token,
        github=github,
        issues=issues,
        error=error,
        submitted=submitted
    )


@app.route('/', methods=['GET'])
def get_youtrack():
    return render_template('youtrack.html')


@app.route('/', methods=['POST'])
def input_youtrack():
    youtrack_url = request.form.get('youtrack_url', '').strip()
    permanent_token = request.form.get('permanent_token', '').strip()

    # Validate inputs
    if not youtrack_url or not permanent_token:
        return render_template('youtrack.html', error='Please fill in all fields')

    if not youtrack_url.startswith('https://'):
        return render_template('youtrack.html', error='URL must start with https://')

    if not permanent_token.startswith('perm-'):
        return render_template('youtrack.html', error='Token must start with "perm:"')
    session['youtrack_url'] = youtrack_url
    session['permanent_token'] = permanent_token
    session['youtrack_configured'] = True
    return redirect(url_for('get_github_page'))


@app.route('/import-issue/<int:issue_id>', methods=['POST'])
def import_single_issue(issue_id):
    youtrack_url = session.get('youtrack_url')
    permanent_token = session.get('permanent_token')
    cache_file = session.get('issues_file')
    issues = load_issues_from_file(cache_file) if cache_file else []
    github_issue = next((issue for issue in issues if issue.get('number') == issue_id), None)
    if github_issue:
        result = import_one_issue_to_youtrack(youtrack_url, permanent_token, "Imported Issues", github_issue)
        return jsonify(result)
    else:
        return jsonify({'success': False, 'error': 'Issue not found'}), 404


@app.route('/import-bulk-issues', methods=['POST'])
def import_bulk_issues():
    data = request.get_json() or {}
    issue_ids = data.get('issue_ids', [])

    youtrack_url = session.get('youtrack_url')
    permanent_token = session.get('permanent_token')
    cache_file = session.get('issues_file')
    issues = load_issues_from_file(cache_file) if cache_file else []

    selected_issues = [issue for issue in issues if str(issue.get('number')) in issue_ids]

    results = []
    for issue in selected_issues:
        result = import_one_issue_to_youtrack(youtrack_url, permanent_token, "Imported Issues", issue)
        results.append(result)

    successful_imports = [r for r in results if r.get('success')]

    return jsonify({
        'imported_count': len(successful_imports),
        'total_count': len(selected_issues),
        'results': results
    })
@app.route('/session-data')
def session_data():
    return jsonify(dict(session))

if __name__ == '__main__':
    app.run(debug=True, host='0.0.0.0', port=5000)
