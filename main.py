from typing import Union
from urllib.parse import parse_qs, urlencode, urlparse
from dotenv import load_dotenv
from fastapi import FastAPI, Request, Form
from fastapi.responses import HTMLResponse
from fastapi.staticfiles import StaticFiles
from fastapi.templating import Jinja2Templates

import json
import os
import requests
import re
app = FastAPI()

GITHUB_REPO = "https://github.com/strawberrymusicplayer/strawberry/"
load_dotenv()
GITHUB_ISSUE = "https://api.github.com/repos/strawberrymusicplayer/strawberry/issues?per_page=100"
GITHUB_TOKEN = os.getenv("GITHUB_TOKEN")
YOUTRACK_TOKEN = os.getenv("YOUTRACK_TOKEN")
YOUTRACK_REPO = "https://quan.youtrack.cloud/api/admin/projects?fields=id,name,shortName"
YOUTRACK_REPO_GET_FIELDS= "https://quan.youtrack.cloud/api/admin/projects?fields=assignee"

def convert_github_to_youtrack(project_name,issue_title, issue_body , issue_label, issue_state):
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
        "name": issue_label,
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
                return f"https://api.github.com/repos/{owner}/{repo}/issues?per_page=1"
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

app.mount("/static", StaticFiles(directory="static"), name="static")
templates = Jinja2Templates(directory="templates")

@app.get("/", response_class=HTMLResponse)
async def read_root(request: Request):
    return templates.TemplateResponse("index.html", {"request": request, "github": None, "submitted": False, "error": False})


@app.post("/", response_class=HTMLResponse)
async def handle_form(request: Request, github: str = Form(...)):
    GITHUB_TOKEN = os.getenv("GITHUB_TOKEN")
    github = github.strip()
    GITHUB_REPO_REGEX = re.compile(
        r"^https://github\.com/[A-Za-z0-9_.-]+/[A-Za-z0-9_.-]+/?$"
    )

    if not github:
        error_msg = "URL cannot be empty."
        return templates.TemplateResponse(
            "index.html", {"request": request, "error": error_msg, "github": None, "submitted": True}
        )

    elif not GITHUB_REPO_REGEX.match(github):
        error_msg = "Invalid GitHub URL. Must be like: https://github.com/user/repo/"
        return templates.TemplateResponse(
            "index.html", {"request": request, "error": error_msg, "github": None, "submitted": True}
        )       
    else:
        github_issue_api = build_api_url_from_input(github)
        request1 = {    "url": github_issue_api, 
                   "headers": {
            "header": "Accept: application/vnd.github+json" ,
            "header": f'Authorization:{GITHUB_TOKEN}' 
                   }
        }
        response = requests.get(url=request1["url"], headers=request1["headers"])
        data = response.json()
        with open("data.json", "w") as file:
            json.dump(data, file, indent=4, ensure_ascii=False)
        return templates.TemplateResponse("index.html", {"request": request, "github": github, "submitted": True})


