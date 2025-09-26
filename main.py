from urllib.parse import parse_qs, urlencode, urlparse
from dotenv import load_dotenv
from flask import Flask, Response, request, render_template,redirect,  jsonify, url_for
from flask_cors import CORS
from youtrack_client import YouTrackClient

import json
import os
import requests
import re
import time

session = {}
GITHUB_REPO = "https://github.com/strawberrymusicplayer/strawberry/"
load_dotenv()
GITHUB_ISSUE = "https://api.github.com/repos/strawberrymusicplayer/strawberry/issues?per_page=100"
GITHUB_TOKEN = os.getenv("GITHUB_TOKEN")
YOUTRACK_TOKEN = os.getenv("YOUTRACK_TOKEN")
YOUTRACK_REPO = "https://quan.youtrack.cloud/api/admin/projects?fields=id,name,shortName"
YOUTRACK_REPO_GET_FIELDS= "https://quan.youtrack.cloud/api/admin/projects?fields=assignee"

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
    # Clean the input
    url = raw_url.strip()
    if "api.github.com" in url:
        return url
    
    # Extract owner and repo from GitHub URL
    if "github.com" in url:
        # Remove protocol and domain, split by /
        parts = url.replace("https://", "").replace("http://", "").split("/")
        
        # Find github.com position and get next two parts (owner and repo)
        if "github.com" in parts:
            idx = parts.index("github.com")
            if len(parts) > idx + 2:
                owner = parts[idx + 1]
                repo = parts[idx + 2]
                return f"https://api.github.com/repos/{owner}/{repo}/issues?per_page=100"
    return ""

def import_one_issue_to_youtrack(youtrack_url, permanent_token, project_name, github_issue):
    youtrack_issue = convert_github_to_youtrack(
        project_name=project_name,
        issue_title=github_issue['title'],
        issue_body=github_issue['body'],
        issue_state=github_issue['state']
    )
    url = f"{youtrack_url.rstrip('/')}/issues"
    headers = {
        'Accept': 'application/json',
        'Authorization': f'Bearer {permanent_token}',
        'Content-Type': 'application/json'
    }
    
    try:
        response = requests.post(url, headers=headers, json=youtrack_issue)
        
        if response.status_code == 200:
            return {
                'success': True,
                'issue_id': github_issue['number'],
                'youtrack_id': response.json().get('id'),
                'message': f"Issue #{github_issue['number']} imported successfully"
            }
        else:
            return {
                'success': False,
                'issue_id': github_issue['number'],
                'error': f"YouTrack API error: {response.status_code} - {response.text}",
                'message': f"Failed to import issue #{github_issue['number']}"
            }
            
    except Exception as e:
        return {
            'success': False,
            'issue_id': github_issue['number'],
            'error': str(e),
            'message': f"Error importing issue #{github_issue['number']}"
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
    request = {    "url": YOUTRACK_REPO_GET_FIELDS, 
               "headers": {
		"Authorization": f'Bearer {YOUTRACK_TOKEN}',
        "Cache-Control": "no-cache", 
        "Accept": "application/json",
        "Content-Type": "application/json" 
        }
    }
    response = requests.get(url=request["url"], headers=request["headers"])
    data = response.json()
    return data

app = Flask(__name__)
CORS(app)
@app.route('/github', methods=['GET'])
def get_github_page():
    global session
    youtrack_url =session['youtrack_url']
    permanent_token = session['permanent_token'] 
    error = None
    issues = None
    github = ""
    submitted = False   
    return render_template(
    'github.html',
    youtrack_url = youtrack_url, 
    permanent_token = permanent_token,
    github=github,
    issues=issues,
    error=error,
    submitted=submitted
    )
@app.route('/github', methods=['POST'])
def github_page():
    global session
    youtrack_url =session['youtrack_url']
    permanent_token = session['permanent_token']  
    error = None
    issues = None
    github = ""
    submitted = False
    GITHUB_TOKEN = os.getenv("GITHUB_TOKEN")
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
        request1 = {    "url": github_issue_api, 
                "headers": {
            "header": "Accept: application/vnd.github+json" ,
            "header": f'Authorization:{GITHUB_TOKEN}' 
                }
        }
        response = requests.get(url=request1["url"], headers=request1["headers"])
        if response.status_code == 200:
            issues = response.json()
            submitted = True   
        else:
                issues =  []
                error=  f"Error fetching issues: {response.status_code}" , 
                submitted =  True      
    return render_template(
    'github.html',
    youtrack_url = youtrack_url, 
    permanent_token = permanent_token,
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
    global session
    youtrack_url = request.form.get('youtrack_url', '').strip()
    permanent_token = request.form.get('permanent_token', '').strip()
    # Validate inputs
    if not youtrack_url or not permanent_token:
        return render_template('youtrack.html', 
                            error='Please fill in all fields')
    
    if not youtrack_url.startswith('https://'):
        return render_template('youtrack.html',
                            error='URL must start with https://')
    
    if not permanent_token.startswith('perm'):
        return render_template('youtrack.html',
                            error='Token must start with "perm:"')
        
    session['youtrack_url'] = youtrack_url
    session['permanent_token'] = permanent_token
    session['youtrack_configured'] = True
    return redirect(url_for('get_github_page'))

if __name__ == '__main__':
    app.run(debug=True, host='0.0.0.0', port=5000)