import requests
from connect_to_dataverse import ConnectToDataverse 

class DataverseOperations:

    def __init__(self):
        client = ConnectToDataverse()
        self.dataverse_envurl = client.dataverse_envurl
        self.token = client.token

    def get_attibuteid(self, entityname:str, attributename:str):
        attributemetadata = requests.get(
        f"{self.dataverse_envurl}api/data/v9.2/EntityDefinitions(LogicalName='{entityname}')/Attributes?$filter=LogicalName eq '{attributename}'",
        headers={
        'Accept': 'application/json',
        'OData-MaxVersion': '4.0',
        'OData-Version': '4.0',
        'Authorization': f'Bearer {self.token}'})
        attributeid = attributemetadata.json().get('value')[0].get('MetadataId')

        return attributeid
    
    def get_dependencylist_for_attribute(self, attributeid:str):
        dependency = requests.get(f"{self.dataverse_envurl}api/data/v9.2/RetrieveDependenciesForDelete(ObjectId={attributeid},ComponentType=2)",
                           headers={
                               'Accept': 'application/json',
                               'OData-MaxVersion': '4.0',
                               'OData-Version': '4.0',
                               'Authorization': f'Bearer {self.token}'
                           })

        dependencylist = dependency.json()

        return dependencylist
    
    def retrieve_only_businessruledependency(self, dependencylist):
        filerforrequiredtype = (depen for depen in dependencylist.get('value') if depen.get('dependentcomponenttype')==29 and depen.get('dependencytype')==2)
        workflowids = []
        workflowlist = []
        for dep in filerforrequiredtype:
            id = dep.get('dependentcomponentobjectid')
            workflowids.append(id)

        for workflowid in workflowids:
            workflow = requests.get(f"{self.dataverse_envurl}api/data/v9.2/workflows({workflowid})?$select=category,xaml,name,statecode",
                           headers={
                               'Accept': 'application/json',
                               'OData-MaxVersion': '4.0',
                               'OData-Version': '4.0',
                               'Authorization': f'Bearer {self.token}'
                           })
            
            workflow_data = workflow.json()

            if workflow_data.get('statecode') == 1 and workflow_data.get('category') ==2:
                workflowlist.append(workflow_data)

        return workflowlist
    
    def retrieve_only_workflowdependency(self, dependencylist):
        filerforrequiredtype = (depen for depen in dependencylist.get('value') if depen.get('dependentcomponenttype')==29 and depen.get('dependencytype')==2)
        workflowids = []
        workflowlist = []
        for dep in filerforrequiredtype:
            id = dep.get('dependentcomponentobjectid')
            workflowids.append(id)

        for workflowid in workflowids:
            workflow = requests.get(f"{self.dataverse_envurl}api/data/v9.2/workflows({workflowid})?$select=category,xaml,name,statecode",
                           headers={
                               'Accept': 'application/json',
                               'OData-MaxVersion': '4.0',
                               'OData-Version': '4.0',
                               'Authorization': f'Bearer {self.token}'
                           })
            
            workflow_data = workflow.json()

            cat = workflow_data.get('category')

            if workflow_data.get('statecode') == 1 and workflow_data.get('category') ==0:
                workflowlist.append(workflow_data)

        return workflowlist