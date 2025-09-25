from urllib.parse import parse_qs, urlencode, urlparse
from dotenv import load_dotenv
from flask import Flask, Response, request, render_template,redirect,  jsonify
from flask_cors import CORS

import json
import os
import requests
import re

GITHUB_REPO = "https://github.com/strawberrymusicplayer/strawberry/"
load_dotenv()
GITHUB_ISSUE = "https://api.github.com/repos/strawberrymusicplayer/strawberry/issues?per_page=100"
GITHUB_TOKEN = os.getenv("GITHUB_TOKEN")
YOUTRACK_TOKEN = os.getenv("YOUTRACK_TOKEN")
YOUTRACK_REPO = "https://quan.youtrack.cloud/api/admin/projects?fields=id,name,shortName"
YOUTRACK_REPO_GET_FIELDS= "https://quan.youtrack.cloud/api/admin/projects?fields=assignee"

def convert_github_to_youtrack(project_name,issue_title, issue_body , issue_state):
    body = {
        "project": {
            "name": project_name,
            "id": "0-0", 
            "$type": "Project"
        },
        "summary": issue_title, 
        "description": issue_body,
        "customFields": [
    {
      "value": {
        "name": "Normal",
        "$type": "EnumBundleElement",
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
        "name": issue_state,
        "$type": "StateBundleElement"
        },
        "name": "State",
        "$type": "StateIssueCustomField"
        }
        ]
        
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
    return "-1"



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

@app.route('/', methods=['GET', 'POST'])
def index():
    error = None
    issues = None
    github = ""
    submitted = False
    if request.method == "POST":
        GITHUB_TOKEN = os.getenv("GITHUB_TOKEN")
        github = request.form.get('github', '').strip()
        GITHUB_REPO_REGEX = re.compile(
            r"^https://github\.com/[A-Za-z0-9_.-]+/[A-Za-z0-9_.-]+/?$"
        )

        if not github:
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
    'index.html',
    github=github,
    issues=issues,
    error=error,
    submitted=submitted
    )
    
if __name__ == '__main__':
    app.run(debug=True, host='0.0.0.0', port=5000)