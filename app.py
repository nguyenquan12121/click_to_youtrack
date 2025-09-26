from pathlib import Path
from urllib.parse import parse_qs, urlencode, urlparse
import uuid
from dotenv import load_dotenv
from flask import Flask, Response, request, render_template, redirect, jsonify, url_for, session
from flask_cors import CORS
from dateutil import parser
from cache import *
from mapping import *
from sync import *
import json
import os
import requests
import re
import time
load_dotenv()

GITHUB_TOKEN = os.getenv("GITHUB_TOKEN")
# --- Flask app and secret key (required for session) ---
app = Flask(__name__)
app.secret_key = os.getenv("FLASK_SECRET_KEY") or os.urandom(24)

CORS(app)
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
