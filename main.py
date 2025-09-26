from pathlib import Path
from urllib.parse import parse_qs, urlencode, urlparse
import uuid
from dotenv import load_dotenv
from flask import Flask, Response, request, render_template, redirect, jsonify, url_for, session
from flask_cors import CORS
from youtrack_client import YouTrackClient
from dateutil import parser

import json
import os
import requests
import re
import time

load_dotenv()

GITHUB_TOKEN = os.getenv("GITHUB_TOKEN")
YOUTRACK_TOKEN = os.getenv("YOUTRACK_TOKEN")

# --- Flask app and secret key (required for session) ---
app = Flask(__name__)
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


# I kept these fields since other fields needs to be added first on youtrack's server to properly work
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

def sync_github_to_youtrack():
    """
    For every mapping in mappings.json, query both GitHub and YouTrack issues
    and update YouTrack if the GitHub issue is newer.
    """
    mappings = load_mappings()
    if not mappings:
        app.logger.info("No mappings found to sync")
        return {"synced": 0, "errors": 0, "results": []}
    
    results = []
    synced_count = 0
    error_count = 0
    
    # Get session data for YouTrack connection
    youtrack_url = session.get('youtrack_url')
    permanent_token = session.get('permanent_token')
    
    if not youtrack_url or not permanent_token:
        app.logger.error("YouTrack credentials not found in session")
        return {"error": "YouTrack credentials not configured", "synced": 0, "errors": 1}
    
    # Get GitHub token
    github_token = os.getenv("GITHUB_TOKEN")
    github_headers = {
        "Accept": "application/vnd.github+json",
        "X-GitHub-Api-Version": "2022-11-28"
    }
    if github_token:
        github_headers["Authorization"] = f"token {github_token}"
    
    # YouTrack headers
    youtrack_headers = {
        'Accept': 'application/json',
        'Authorization': f'Bearer {permanent_token}',
        'Content-Type': 'application/json'
    }
    
    for github_number_str, youtrack_id in mappings.items():
        try:
            github_number = int(github_number_str)
            
            # Get cached issues to find the repository info
            cache_file = session.get('issues_file')
            cached_issues = load_issues_from_file(cache_file) if cache_file else []
            
            # Find the cached issue to get repository info
            cached_issue = next((issue for issue in cached_issues if issue.get('number') == github_number), None)
            if not cached_issue:
                app.logger.warning(f"No cached issue found for GitHub #{github_number}")
                continue
            
            # Extract repository info from the cached issue URL
            repo_url = cached_issue.get('repository_url', '')
            if not repo_url:
                app.logger.warning(f"No repository URL found for GitHub #{github_number}")
                continue
            
            # Query GitHub API for current issue state
            github_api_url = f"{repo_url}/issues/{github_number}"
            github_response = requests.get(github_api_url, headers=github_headers, timeout=10)
            
            if github_response.status_code != 200:
                app.logger.error(f"Failed to fetch GitHub issue #{github_number}: {github_response.status_code}")
                error_count += 1
                results.append({
                    "github_number": github_number,
                    "youtrack_id": youtrack_id,
                    "status": "error",
                    "message": f"Failed to fetch GitHub issue: {github_response.status_code}"
                })
                continue
            
            github_issue = github_response.json()
            
            # Query YouTrack API for current issue state
            youtrack_api_url = f"{youtrack_url.rstrip('/')}/api/issues/{youtrack_id}"
            youtrack_params = {
                "fields": "id,summary,description,updated,customFields(name,value(name))"
            }
            youtrack_response = requests.get(
                youtrack_api_url, 
                headers=youtrack_headers, 
                params=youtrack_params,
                timeout=10
            )
            
            if youtrack_response.status_code != 200:
                app.logger.error(f"Failed to fetch YouTrack issue {youtrack_id}: {youtrack_response.status_code}")
                error_count += 1
                results.append({
                    "github_number": github_number,
                    "youtrack_id": youtrack_id,
                    "status": "error",
                    "message": f"Failed to fetch YouTrack issue: {youtrack_response.status_code}"
                })
                continue
            
            youtrack_issue = youtrack_response.json()
            
            # Compare timestamps
            github_updated_str = github_issue.get('updated_at')
            youtrack_updated = youtrack_issue.get('updated')  # Unix timestamp in milliseconds
            
            if not github_updated_str or not youtrack_updated:
                app.logger.warning(f"Missing timestamp data for GitHub #{github_number} or YouTrack {youtrack_id}")
                continue
            
            # Parse GitHub timestamp (ISO 8601 format)
            github_updated = parser.parse(github_updated_str)
            github_updated_timestamp = int(github_updated.timestamp() * 1000)  # Convert to milliseconds
            
            # Compare timestamps
            if github_updated_timestamp > youtrack_updated:
                app.logger.info(f"GitHub issue #{github_number} is newer, updating YouTrack {youtrack_id}")
                
                # Update YouTrack issue
                update_result = update_youtrack_issue_from_github(
                    youtrack_url, 
                    permanent_token, 
                    youtrack_id, 
                    github_issue,
                    youtrack_issue
                )
                
                if update_result['success']:
                    synced_count += 1
                    results.append({
                        "github_number": github_number,
                        "youtrack_id": youtrack_id,
                        "status": "updated",
                        "message": "Successfully updated from GitHub",
                        "github_updated": github_updated_str,
                        "youtrack_updated": youtrack_updated
                    })
                else:
                    error_count += 1
                    results.append({
                        "github_number": github_number,
                        "youtrack_id": youtrack_id,
                        "status": "error",
                        "message": f"Failed to update: {update_result.get('error', 'Unknown error')}"
                    })
            else:
                results.append({
                    "github_number": github_number,
                    "youtrack_id": youtrack_id,
                    "status": "up_to_date",
                    "message": "YouTrack issue is up to date"
                })
                
        except Exception as e:
            app.logger.exception(f"Error syncing GitHub #{github_number_str} -> YouTrack {youtrack_id}")
            error_count += 1
            results.append({
                "github_number": github_number_str,
                "youtrack_id": youtrack_id,
                "status": "error", 
                "message": f"Exception: {str(e)}"
            })
        
        # Add delay to respect API rate limits
        time.sleep(0.5)
    
    return {
        "synced": synced_count,
        "errors": error_count,
        "total_checked": len(mappings),
        "results": results
    }


def update_youtrack_issue_from_github(youtrack_url, permanent_token, youtrack_id, github_issue, youtrack_issue):
    """
    Update a YouTrack issue with data from a GitHub issue.
    Only updates fields that have actually changed.
    """
    try:
        updates = {}
        
        # Check if summary needs updating
        github_title = github_issue.get('title', '')
        youtrack_summary = youtrack_issue.get('summary', '')
        if github_title != youtrack_summary:
            updates['summary'] = github_title
        
        # Check if description needs updating
        github_body = github_issue.get('body') or "No description provided"
        youtrack_description = youtrack_issue.get('description', '')
        if github_body != youtrack_description:
            updates['description'] = github_body
        
        # Check if state needs updating
        github_state = github_issue.get('state', 'open')
        youtrack_state_name = None
        
        # Find current state in YouTrack custom fields
        custom_fields = youtrack_issue.get('customFields', [])
        state_field = next((cf for cf in custom_fields if cf.get('name') == 'State'), None)
        if state_field and state_field.get('value'):
            youtrack_state_name = state_field['value'].get('name', '').lower()
        
        # Map GitHub states to YouTrack states
        state_mapping = {
            'open': 'Open',
            'closed': 'Fixed'  # You might want to adjust this mapping
        }
        
        expected_state = state_mapping.get(github_state.lower(), 'Open')
        if youtrack_state_name != expected_state.lower():
            if 'customFields' not in updates:
                updates['customFields'] = []
            
            updates['customFields'].append({
                "value": {
                    "name": expected_state,
                    "$type": "StateBundleElement"
                },
                "name": "State",
                "$type": "StateIssueCustomField"
            })
        
        # If no updates needed, return success
        if not updates:
            return {
                'success': True,
                'message': 'No updates needed',
                'updated_fields': []
            }
        
        # Perform the update
        headers = {
            'Accept': 'application/json',
            'Authorization': f'Bearer {permanent_token}',
            'Content-Type': 'application/json'
        }
        
        url = f"{youtrack_url.rstrip('/')}/api/issues/{youtrack_id}"
        response = requests.post(url, headers=headers, json=updates, timeout=15)
        
        if response.status_code in (200, 201):
            return {
                'success': True,
                'message': f"Updated fields: {', '.join(updates.keys())}",
                'updated_fields': list(updates.keys())
            }
        else:
            return {
                'success': False,
                'error': f"YouTrack API error: {response.status_code} - {response.text}"
            }
            
    except Exception as e:
        return {
            'success': False,
            'error': f"Exception during update: {str(e)}"
        }




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
                return f"https://api.github.com/repos/{owner}/{repo}/issues?per_page=5"
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
    try:
        response = requests.post(url, headers=headers, json=youtrack_issue)
        if response.status_code in (200, 201):
            yt_id = None
            try:
                yt_id = response.json().get('id')
            except Exception:
                pass

            # save mapping (if we got an id)
            gh_number = github_issue.get('number')
            if gh_number and yt_id:
                try:
                    add_mapping(gh_number, yt_id)
                except Exception:
                    app.logger.exception("Failed to add mapping for GH %s -> YT %s", gh_number, yt_id)            
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


@app.route('/github', methods=['GET', 'POST'])
def github_page():
    youtrack_url = session.get('youtrack_url')
    permanent_token = session.get('permanent_token')
    error = None
    issues = None
    github = ""
    submitted = False
    
    # Load mappings
    mappings = load_mappings()
    
    if request.method == 'POST':
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
                session['issues_file'] = cache_file  # only store file path in session
                submitted = True
            else:
                issues = []
                error = f"Error fetching issues: {response.status_code} - {response.text}"
                submitted = True
    else:
        # GET request - load existing issues from session if available
        cache_file = session.get('issues_file')
        if cache_file:
            issues = load_issues_from_file(cache_file)
            submitted = True
            github = session.get('last_github_url', '')
    
    return render_template(
        'github.html',
        youtrack_url=youtrack_url,
        permanent_token=permanent_token,
        github=github,
        issues=issues,
        error=error,
        submitted=submitted,
        mappings=mappings  # Pass mappings to template
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

@app.route('/sync-issues', methods=['POST'])
def sync_issues_endpoint():
    """
    API endpoint to trigger synchronization of all mapped issues.
    """
    try:
        result = sync_github_to_youtrack()
        return jsonify(result)
    except Exception as e:
        app.logger.exception("Error in sync_issues_endpoint")
        return jsonify({
            "error": f"Sync failed: {str(e)}",
            "synced": 0,
            "errors": 1
        }), 500


@app.route('/sync-issue/<int:github_number>', methods=['POST'])
def sync_single_issue_endpoint(github_number):
    """
    API endpoint to sync a single issue by GitHub number.
    """
    try:
        mappings = load_mappings()
        youtrack_id = mappings.get(str(github_number))
        
        if not youtrack_id:
            return jsonify({
                "error": f"No mapping found for GitHub issue #{github_number}",
                "success": False
            }), 404
        
        # Temporarily modify mappings to sync just this one issue
        temp_mappings = {str(github_number): youtrack_id}
        
        # Store original mappings
        original_load_mappings = globals()['load_mappings']
        globals()['load_mappings'] = lambda: temp_mappings
        
        try:
            result = sync_github_to_youtrack()
            return jsonify(result)
        finally:
            # Restore original mappings function
            globals()['load_mappings'] = original_load_mappings
            
    except Exception as e:
        app.logger.exception(f"Error syncing single issue #{github_number}")
        return jsonify({
            "error": f"Sync failed: {str(e)}",
            "success": False
        }), 500

if __name__ == '__main__':
    app.run(debug=True, host='0.0.0.0', port=5000)
