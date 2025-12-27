from dotenv import dotenv_values
from azure.identity import ClientSecretCredential
from PowerPlatform.Dataverse.client import DataverseClient

class ConnectToDataverse:
    def __init__(self):
        credentialdetails=dotenv_values('.env')
        self.dataverse_envurl=credentialdetails.get('env_url')
        clientid = credentialdetails.get('client_id')
        tenantid = credentialdetails.get('tenant_id')
        clientsecret = credentialdetails.get('client_secret')
        credential=ClientSecretCredential(tenantid, clientid, clientsecret)
        client = DataverseClient(self.dataverse_envurl, credential) 
        self.token = client.auth._acquire_token(f'{self.dataverse_envurl}.default').access_token


