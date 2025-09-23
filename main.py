from typing import Union
import os
GITHUB_REPO = "https://github.com/strawberrymusicplayer/strawberry/issues"
import requests

# could just copy the link i guess
GITHUB_ISSUE = "https://api.github.com/repos/strawberrymusicplayer/strawberry/issues?per_page=100"
GITHUB_TOKEN = os.getenv("GITHUB_TOKEN")

YOUTRACK_TOKEN = os.getenv("YOUTRACK_TOKEN")
# needs a link or something
YOUTRACK_REPO = "https://quan.youtrack.cloud/projects/DEMO"

def github_req():
    request = {    "url": GITHUB_ISSUE, 
               "headers": {
        "header": "Accept: application/vnd.github+json" ,
        "header": f'Authorization:{GITHUB_TOKEN}' 
               }
    }
    response = requests.get(url=request["url"], headers=request["headers"])
    data = response.json()
    with open("test.json", "w") as file:
        for d in data:
            file.write(f'{d['url']}\n')
def youtrack_req():
    request = {    "url": YOUTRACK_REPO, 
               "headers": {
		"Authorization": f'Bearer {YOUTRACK_TOKEN}',
        "Accept": "Accept: application/json",
        "Content-Type": "application/json" 
               }
    }
    response = requests.get(url=request["url"], headers=request["headers"])
    data = response.text
    with open("test_youtrack.html", "w", encoding="utf-8") as file:
        file.write(data)	

if __name__ == "__main__":		
    github_req()
    youtrack_req()
