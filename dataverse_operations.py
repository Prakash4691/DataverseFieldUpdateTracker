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
        """
        Parse FormXML directly to find web resource references
        This is more reliable than querying the dependency table
        """
        webresource_references = []
        
        for formid in formids:
            # Get the form with its FormXML
            form = requests.get(
                f"{self.dataverse_envurl}api/data/v9.2/systemforms({formid})?$select=formxml,name",
                headers={
                    'Accept': 'application/json',
                    'OData-MaxVersion': '4.0',
                    'OData-Version': '4.0',
                    'Authorization': f'Bearer {self.token}'
                })
            
            form_data = form.json()
            
            if 'formxml' in form_data:
                formxml = form_data['formxml']
                # Find web resource references in FormXML
                # Patterns: <Library name="webresourcename" or <WebResource id="webresourcename"
                import re
                
                # Pattern 1: <Library name="webresource_name"
                library_pattern = r'<Library\s+name="([^"]+)"'
                libraries = re.findall(library_pattern, formxml, re.IGNORECASE)
                
                # Pattern 2: <WebResource id="webresource_name"
                webresource_pattern = r'<WebResource[^>]+id="([^"]+)"'
                webresources = re.findall(webresource_pattern, formxml, re.IGNORECASE)
                
                # Pattern 3: src attribute with .js, .css, etc.
                src_pattern = r'src="([^"]+\.(js|css|html))"'
                src_files = re.findall(src_pattern, formxml, re.IGNORECASE)
                
                all_refs = set(libraries + webresources + [src[0] for src in src_files])
                
                webresource_references.extend([{'formid': formid, 'webresourcename': ref} for ref in all_refs])
        
        return webresource_references
    
    def retrieve_webresources_from_dependency(self, webresource_references):
        """
        Now accepts web resource references parsed from FormXML
        Decodes base64 content to get actual web resource content
        """
        import base64
        
        webresourcelist = []
        
        for ref in webresource_references:
            webresource_name = ref['webresourcename']
            
            # Query web resource by name
            webresource_query = requests.get(
                f"{self.dataverse_envurl}api/data/v9.2/webresourceset?$filter=name eq '{webresource_name}'&$select=name,webresourcetype,content,webresourceid",
                headers={
                    'Accept': 'application/json',
                    'OData-MaxVersion': '4.0',
                    'OData-Version': '4.0',
                    'Authorization': f'Bearer {self.token}'
                })
            
            webresource_data = webresource_query.json()
            
            if 'value' in webresource_data and len(webresource_data['value']) > 0:
                webresource = webresource_data['value'][0]
                
                # Only process JavaScript files (webresourcetype = 3)
                if webresource.get('webresourcetype') == 3:
                    # Decode base64 content if present
                    decoded_content = ""
                    if 'content' in webresource and webresource['content']:
                        try:
                            decoded_content = base64.b64decode(webresource['content']).decode('utf-8')
                        except Exception as e:
                            decoded_content = f"Error decoding content: {str(e)}"
                    
                    # Only include name, id, and decoded_content
                    webresourcelist.append({
                        'name': webresource.get('name'),
                        'id': webresource.get('webresourceid'),
                        'decoded_content': decoded_content
                    })
        
        return webresourcelist