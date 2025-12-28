from dotenv import dotenv_values
from azure.identity import ClientSecretCredential
from PowerPlatform.Dataverse.client import DataverseClient

class ConnectToDataverse:
    """
    Handles authentication to Microsoft Dataverse using Azure service principal credentials.
    
    This class reads credentials from a .env file and acquires an OAuth2 access token
    for authenticating to the Dataverse Web API.
    
    Attributes:
        dataverse_envurl (str): The Dataverse environment URL (e.g., https://org.crm.dynamics.com/).
        token (str): The OAuth2 access token for API authentication.
    
    Required Environment Variables:
        client_id: Azure AD application client ID
        tenant_id: Azure AD tenant ID
        client_secret: Azure AD application secret
        env_url: Dataverse environment URL
    """
    
    def __init__(self):
        """
        Initialize the Dataverse connection by reading credentials and acquiring an access token.
        
        Reads credentials from .env file, creates a ClientSecretCredential, and acquires
        an OAuth2 access token using the DataverseClient.
        
        Raises:
            KeyError: If required environment variables are missing from .env file.
            Exception: If authentication fails or token acquisition fails.
        """
        credentialdetails=dotenv_values('.env')
        self.dataverse_envurl=credentialdetails.get('env_url')
        clientid = credentialdetails.get('client_id')
        tenantid = credentialdetails.get('tenant_id')
        clientsecret = credentialdetails.get('client_secret')
        credential=ClientSecretCredential(tenantid, clientid, clientsecret)
        client = DataverseClient(self.dataverse_envurl, credential) 
        self.token = client.auth._acquire_token(f'{self.dataverse_envurl}.default').access_token


