# config.py
YOUTRACK_DOMAINS = {
    'cloud': {
        'base_url': 'https://{tenant}.youtrack.cloud/api',
        'auth_url': 'https://{tenant}.youtrack.cloud/hub/api/rest/oauth2/auth',
        'token_url': 'https://{tenant}.youtrack.cloud/hub/api/rest/oauth2/token',
    },
    'selfhosted': {
        'base_url': 'https://{domain}/api',
        'auth_url': 'https://{domain}/hub/api/rest/oauth2/auth',
        'token_url': 'https://{domain}/hub/api/rest/oauth2/token',
    }
}

class YouTrackConfig:
    def __init__(self, domain_type, identifier):
        self.domain_type = domain_type
        self.identifier = identifier  # tenant name or domain
    
    @property
    def base_url(self):
        template = YOUTRACK_DOMAINS[self.domain_type]['base_url']
        return template.format(tenant=self.identifier, domain=self.identifier)
    
    @property
    def auth_url(self):
        template = YOUTRACK_DOMAINS[self.domain_type]['auth_url']
        return template.format(tenant=self.identifier, domain=self.identifier)