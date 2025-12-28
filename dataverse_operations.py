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

            if workflow_data.get('statecode') == 1 and (workflow_data.get('category')==0 or workflow_data.get('category')==2):
                workflowlist.append(workflow_data)

        return workflowlist
    
    def get_forms_for_entity(self, entityname:str):
        forms = requests.get(f"{self.dataverse_envurl}api/data/v9.2/systemforms?$filter=objecttypecode eq '{entityname}' and (type eq 2 or type eq 6)&$select=formid",
                           headers={
                               'Accept': 'application/json',
                               'OData-MaxVersion': '4.0',
                               'OData-Version': '4.0',
                               'Authorization': f'Bearer {self.token}'
                           })
        
        formslist = [form.get('formid') for form in forms.json().get('value')]
        
        return formslist
    
    def get_dependencylist_for_form(self, formids:list):
        dependencylist = []
        
        for formid in formids:
            dependency = requests.get(f"{self.dataverse_envurl}api/data/v9.2/RetrieveDependentComponents(ObjectId={formid},ComponentType=24)",
                               headers={
                                   'Accept': 'application/json',
                                   'OData-MaxVersion': '4.0',
                                   'OData-Version': '4.0',
                                   'Authorization': f'Bearer {self.token}'
                               })

            dependency_data = dependency.json()
            if 'value' in dependency_data:
                dependencylist.extend(dependency_data.get('value'))

        return dependencylist
    
    def retrieve_webresources_from_dependency(self, dependencylist):
        filter_for_webresource = (depen for depen in dependencylist.get('value') if depen.get('dependentcomponenttype')==61)
        webresourceids = []
        webresourcelist = []
        
        for dep in filter_for_webresource:
            id = dep.get('dependentcomponentobjectid')
            webresourceids.append(id)

        for webresourceid in webresourceids:
            webresource = requests.get(f"{self.dataverse_envurl}api/data/v9.2/webresourceset({webresourceid})?$select=name,webresourcetype,content",
                           headers={
                               'Accept': 'application/json',
                               'OData-MaxVersion': '4.0',
                               'OData-Version': '4.0',
                               'Authorization': f'Bearer {self.token}'
                           })
            
            webresource_data = webresource.json()
            webresourcelist.append(webresource_data)

        return webresourcelist