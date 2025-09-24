from typing import Union
from dotenv import load_dotenv
from fastapi import FastAPI, Request, Form
from fastapi.responses import HTMLResponse
from fastapi.staticfiles import StaticFiles
from fastapi.templating import Jinja2Templates

import requests
import os
import re
app = FastAPI()

GITHUB_REPO = "https://github.com/strawberrymusicplayer/strawberry/issues"
load_dotenv()
# could just copy the link i guess
GITHUB_ISSUE = "https://api.github.com/repos/strawberrymusicplayer/strawberry/issues?per_page=100"
GITHUB_TOKEN = os.getenv("GITHUB_TOKEN")
YOUTRACK_TOKEN = os.getenv("YOUTRACK_TOKEN")
# needs a link or something
# YOUTRACK_REPO = "https://quan.youtrack.cloud/api/users/me"
YOUTRACK_REPO = "https://quan.youtrack.cloud/api/admin/projects?fields=id,name,shortName"
YOUTRACK_REPO_GET_FIELDS= "https://quan.youtrack.cloud/api/admin/projects?fields=assignee"
def github_req():
    global GITHUB_ISSUE, GITHUB_TOKEN

#curl -X GET \
#'https://quan.youtrack.cloud/api/users/me' \                                                                            -H 'Authorization: Bearer perm-YWRtaW4=.NDQtMQ==.bEVtcOJ9b8462q7wtiRukDPu7bIasd' \
#-H 'Accept: application/json' \
#-H 'Cache-Control: no-cache' \
#-H 'Content-Type: application/json'            

# curl -X GET 'https://example.youtrack.cloud/api/issues?query=in:SP&fields=id,idReadable,summary,customFields(id,projectCustomField(field(name)))' \
# -H 'Accept: application/json' \
# -H 'Authorization: Bearer perm:amFuZS5kb2U=.UkVTVCBBUEk=.wcKuAok8cHmAtzjA6xlc4BrB4hleaX'

# curl -X POST \
# https://quan.youtrack.cloud/api/issues \
# -H 'Accept: application/json' \
# -H 'Authorization: Bearer perm-YWRtaW4=.NDQtMQ==.bEVtcOJ9b8462q7wtiRukDPu7bIasd' \
# -H 'Content-Type: application/json' \
# -d '{
# "project":{ "name": "Sample Project","id": "0-0","$type": "Project"},
# "summary":"REST API lets you create issues!",
# "description":"Let'\''s create a new issue using YouTrack'\''s REST API."
# }' 
# -> needs more fields

# Project
# Priority
# Type
# State
# Assignee
# Subsystem
# Fix versions
# Affected versions
# Fixed in build
# Estimation


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
    github = github.strip()
    GITHUB_ISSUE_REGEX = re.compile(
    r"^https:\/\/github\.com\/[A-Za-z0-9_.-]+\/[A-Za-z0-9_.-]+\/issues\/?$"    
    )    
    if not github:
        error_msg = "URL cannot be empty."
        return templates.TemplateResponse(
            "index.html", {"request": request, "error": error_msg, "github": None, "submitted": True}
        )

    elif not GITHUB_ISSUE_REGEX.match(github):
        error_msg = "Invalid GitHub issues URL. Must be like: https://github.com/user/repo/issues"
        return templates.TemplateResponse(
            "index.html", {"request": request, "error": error_msg, "github": None, "submitted": True}
        )       
    else:
        request1 = {    "url": github, 
                   "headers": {
            "header": "Accept: application/vnd.github+json" ,
            "header": f'Authorization:{GITHUB_TOKEN}' 
                   }
        }
        response = requests.get(url=request["url"], headers=request["headers"])
        data = response.json()
        return templates.TemplateResponse("index.html", {"request": request, "github": github, "submitted": True})


