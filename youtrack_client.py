# This is actually the CORRECT approach for your server-side app
import os
from flask import session, redirect, url_for

class YouTrackManager:
    def __init__(self):
        # Store tokens securely (environment variables, database, etc.)
        self.tokens = {
            'tenant1': os.getenv('YOUTRACK_TOKEN_TENANT1'),
            'tenant2': os.getenv('YOUTRACK_TOKEN_TENANT2'),
        }
    
    def get_client(self, tenant_name):
        token = self.tokens.get(tenant_name)
        if not token:
            return None
        return YouTrackClient(f"https://{tenant_name}.youtrack.cloud/api", token)

# Simple token-based client
class YouTrackClient:
    def __init__(self, base_url, permanent_token):
        self.base_url = base_url
        self.token = permanent_token
    
    def get_headers(self):
        return {
            'Authorization': f'Bearer {self.token}',
            'Content-Type': 'application/json'
        }
    
    def create_issue(self, issue_data):
        # Your API call logic
        pass