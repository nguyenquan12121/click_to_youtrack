from flask import session
from dateutil import parser

import os
import requests
import time

from cache import load_issues_from_file
from mapping import *
from app import app


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
                return f"https://api.github.com/repos/{owner}/{repo}/issues?state=open&per_page=100"
    return ""

# YOUTRACK_DOMAINS = {
#     'cloud': {
#         'base_url': 'https://{tenant}.youtrack.cloud/api',
#         'auth_url': 'https://{tenant}.youtrack.cloud/hub/api/rest/oauth2/auth',
#         'token_url': 'https://{tenant}.youtrack.cloud/hub/api/rest/oauth2/token',
#     },
#     'selfhosted': {
#         'base_url': 'https://{domain}/api',
#         'auth_url': 'https://{domain}/hub/api/rest/oauth2/auth',
#         'token_url': 'https://{domain}/hub/api/rest/oauth2/token',
#     }
# }
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



