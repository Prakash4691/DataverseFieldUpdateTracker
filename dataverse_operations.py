import requests
from connect_to_dataverse import ConnectToDataverse 

class DataverseOperations:

    def __init__(self):
        client = ConnectToDataverse()
        self.dataverse_envurl = client.dataverse_envurl
        self.token = client.token

    def get_attibuteid(self, entityname:str, attributename:str):
        try:
            attributemetadata = requests.get(
            f"{self.dataverse_envurl}api/data/v9.2/EntityDefinitions(LogicalName='{entityname}')/Attributes?$filter=LogicalName eq '{attributename}'",
            headers={
            'Accept': 'application/json',
            'OData-MaxVersion': '4.0',
            'OData-Version': '4.0',
            'Authorization': f'Bearer {self.token}'})
            
            attributemetadata.raise_for_status()
            
            response_data = attributemetadata.json()
            
            if not response_data.get('value'):
                raise ValueError(
                    f"Attribute '{attributename}' not found for entity '{entityname}'. "
                    f"Please verify the entity and attribute names."
                )
            
            attributeid = response_data['value'][0].get('MetadataId')
            
            if not attributeid:
                raise ValueError(
                    f"MetadataId not found for attribute '{attributename}' in entity '{entityname}'."
                )
            
            return attributeid
            
        except requests.exceptions.RequestException as e:
            raise ConnectionError(
                f"Failed to retrieve attribute ID for '{entityname}.{attributename}': {str(e)}"
            ) from e
        except (KeyError, IndexError) as e:
            raise ValueError(
                f"Unexpected response format when retrieving attribute '{attributename}' for entity '{entityname}': {str(e)}"
            ) from e
    
    def get_dependencylist_for_attribute(self, attributeid:str):
        try:
            dependency = requests.get(f"{self.dataverse_envurl}api/data/v9.2/RetrieveDependenciesForDelete(ObjectId={attributeid},ComponentType=2)",
                               headers={
                                   'Accept': 'application/json',
                                   'OData-MaxVersion': '4.0',
                                   'OData-Version': '4.0',
                                   'Authorization': f'Bearer {self.token}'
                               })
            
            dependency.raise_for_status()
            dependencylist = dependency.json()
            
            if 'value' not in dependencylist:
                raise ValueError(
                    f"Unexpected response format for dependencies of attribute '{attributeid}'. "
                    f"Expected 'value' key in response."
                )
            
            return dependencylist
            
        except requests.exceptions.RequestException as e:
            raise ConnectionError(
                f"Failed to retrieve dependencies for attribute '{attributeid}': {str(e)}"
            ) from e
        except ValueError as e:
            if "Unexpected response format" in str(e):
                raise
            raise ValueError(
                f"Invalid JSON response when retrieving dependencies for attribute '{attributeid}': {str(e)}"
            ) from e
    
    def retrieve_only_workflowdependency(self, dependencylist):
        try:
            if not dependencylist or 'value' not in dependencylist:
                raise ValueError("Invalid dependency list: missing 'value' key")
            
            filerforrequiredtype = (depen for depen in dependencylist.get('value') if depen.get('dependentcomponenttype')==29 and depen.get('dependencytype')==2)
            workflowids = []
            workflowlist = []
            
            for dep in filerforrequiredtype:
                id = dep.get('dependentcomponentobjectid')
                if id:
                    workflowids.append(id)

            for workflowid in workflowids:
                try:
                    workflow = requests.get(f"{self.dataverse_envurl}api/data/v9.2/workflows({workflowid})?$select=category,xaml,name,statecode",
                                   headers={
                                       'Accept': 'application/json',
                                       'OData-MaxVersion': '4.0',
                                       'OData-Version': '4.0',
                                       'Authorization': f'Bearer {self.token}'
                                   })
                    
                    workflow.raise_for_status()
                    workflow_data = workflow.json()

                    if workflow_data.get('statecode') == 1 and (workflow_data.get('category')==0 or workflow_data.get('category')==2):
                        workflowlist.append(workflow_data)
                        
                except requests.exceptions.RequestException as e:
                    print(f"Warning: Failed to retrieve workflow {workflowid}: {str(e)}")
                    continue
                except ValueError as e:
                    print(f"Warning: Invalid JSON response for workflow {workflowid}: {str(e)}")
                    continue

            return workflowlist
            
        except (KeyError, TypeError) as e:
            raise ValueError(
                f"Error processing workflow dependencies: {str(e)}"
            ) from e
    
    def get_forms_for_entity(self, entityname:str):
        try:
            forms = requests.get(f"{self.dataverse_envurl}api/data/v9.2/systemforms?$filter=objecttypecode eq '{entityname}' and (type eq 2 or type eq 6)&$select=formid",
                           headers={
                               'Accept': 'application/json',
                               'OData-MaxVersion': '4.0',
                               'OData-Version': '4.0',
                               'Authorization': f'Bearer {self.token}'
                           })
            
            forms.raise_for_status()
            response_data = forms.json()
            
            if 'value' not in response_data:
                raise ValueError(
                    f"Unexpected response format for forms of entity '{entityname}'. "
                    f"Expected 'value' key in response."
                )
            
            formslist = [form.get('formid') for form in response_data.get('value') if form.get('formid')]
            
            return formslist
            
        except requests.exceptions.RequestException as e:
            raise ConnectionError(
                f"Failed to retrieve forms for entity '{entityname}': {str(e)}"
            ) from e
        except ValueError as e:
            if "Unexpected response format" in str(e):
                raise
            raise ValueError(
                f"Invalid JSON response when retrieving forms for entity '{entityname}': {str(e)}"
            ) from e
    
    def get_dependencylist_for_form(self, formids:list):
        """
        Parse FormXML directly to find web resource references
        This is more reliable than querying the dependency table
        """
        webresource_references = []
        
        if not formids:
            return webresource_references
        
        for formid in formids:
            try:
                # Get the form with its FormXML
                form = requests.get(
                    f"{self.dataverse_envurl}api/data/v9.2/systemforms({formid})?$select=formxml,name",
                    headers={
                        'Accept': 'application/json',
                        'OData-MaxVersion': '4.0',
                        'OData-Version': '4.0',
                        'Authorization': f'Bearer {self.token}'
                    })
                
                form.raise_for_status()
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
                    
            except requests.exceptions.RequestException as e:
                print(f"Warning: Failed to retrieve form {formid}: {str(e)}")
                continue
            except ValueError as e:
                print(f"Warning: Invalid JSON response for form {formid}: {str(e)}")
                continue
            except Exception as e:
                print(f"Warning: Error processing form {formid}: {str(e)}")
                continue
        
        return webresource_references
    
    def retrieve_webresources_from_dependency(self, webresource_references):
        """
        Now accepts web resource references parsed from FormXML
        Decodes base64 content to get actual web resource content
        """
        import base64
        
        webresourcelist = []
        
        if not webresource_references:
            return webresourcelist
        
        for ref in webresource_references:
            try:
                webresource_name = ref.get('webresourcename')
                
                if not webresource_name:
                    continue
                
                # Query web resource by name
                webresource_query = requests.get(
                    f"{self.dataverse_envurl}api/data/v9.2/webresourceset?$filter=name eq '{webresource_name}'&$select=name,webresourcetype,content,webresourceid",
                    headers={
                        'Accept': 'application/json',
                        'OData-MaxVersion': '4.0',
                        'OData-Version': '4.0',
                        'Authorization': f'Bearer {self.token}'
                    })
                
                webresource_query.raise_for_status()
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
                        
            except requests.exceptions.RequestException as e:
                print(f"Warning: Failed to retrieve web resource '{ref.get('webresourcename', 'unknown')}': {str(e)}")
                continue
            except ValueError as e:
                print(f"Warning: Invalid JSON response for web resource '{ref.get('webresourcename', 'unknown')}': {str(e)}")
                continue
            except Exception as e:
                print(f"Warning: Error processing web resource '{ref.get('webresourcename', 'unknown')}': {str(e)}")
                continue
        
        return webresourcelist