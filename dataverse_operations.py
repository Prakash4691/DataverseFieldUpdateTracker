import requests
import time
from connect_to_dataverse import ConnectToDataverse 
from PowerPlatform.Dataverse.core.errors import DataverseError 

class DataverseOperations:
    """
    Provides methods for interacting with Microsoft Dataverse.
    
    This class handles various Dataverse operations including retrieving attribute metadata,
    dependency lists, workflows, business rules, forms, and web resources. Uses the 
    PowerPlatform Dataverse SDK for standard operations and HTTP requests for specialized
    operations like metadata queries and custom functions.
    
    Attributes:
        dataverse_envurl (str): The Dataverse environment URL from ConnectToDataverse.
        token (str): The OAuth2 access token for API authentication from ConnectToDataverse.
        client (DataverseClient): The authenticated DataverseClient instance for SDK operations.
    """

    def __init__(self):
        """
        Initialize DataverseOperations with authenticated connection.
        
        Creates a ConnectToDataverse instance to obtain the environment URL, access token,
        and DataverseClient instance for making authenticated API requests.
        """
        conn = ConnectToDataverse()
        self.dataverse_envurl = conn.dataverse_envurl
        self.token = conn.token
        self.client = conn.client

    def get_attibuteid(self, entityname:str, attributename:str, rate_limit_tracker=None):
        """
        Retrieve the MetadataId (GUID) of a specific entity attribute.
        
        Args:
            entityname (str): The logical name of the entity (e.g., 'account', 'contact').
            attributename (str): The logical name of the attribute/field (e.g., 'name', 'emailaddress1').
            rate_limit_tracker (RateLimitTracker, optional): Tracker instance to record rate limit metrics.
        
        Returns:
            str: The MetadataId (GUID) of the attribute.
        
        Raises:
            ConnectionError: If the API request fails.
            ValueError: If the attribute is not found in the entity or response format is invalid.
        
        Example:
            >>> ops = DataverseOperations()
            >>> tracker = RateLimitTracker()
            >>> attr_id = ops.get_attibuteid('account', 'name', rate_limit_tracker=tracker)
        """
        max_retries = 3
        url = f"{self.dataverse_envurl}api/data/v9.2/EntityDefinitions(LogicalName='{entityname}')/Attributes?$filter=LogicalName eq '{attributename}'"
        headers = {
            'Accept': 'application/json',
            'OData-MaxVersion': '4.0',
            'OData-Version': '4.0',
            'Authorization': f'Bearer {self.token}'
        }
        
        hit_429 = False
        retry_count = 0
        total_retry_after = 0
        request_start = time.time()
        
        for attempt in range(max_retries):
            try:
                attributemetadata = requests.get(url, headers=headers)
                
                # Handle 429 Too Many Requests with Retry-After
                if attributemetadata.status_code == 429:
                    hit_429 = True
                    retry_count += 1
                    
                    if attempt < max_retries - 1:
                        retry_after = int(attributemetadata.headers.get('Retry-After', 60))
                        total_retry_after += retry_after
                        print(f"Rate limit exceeded. Waiting {retry_after} seconds before retry (attempt {attempt + 1}/{max_retries})...")
                        time.sleep(retry_after)
                        continue
                
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
                
                # Record successful request
                if rate_limit_tracker:
                    duration = time.time() - request_start
                    rate_limit_tracker.record_request(
                        endpoint=f"get_attibuteid({entityname}.{attributename})",
                        duration=duration,
                        hit_429=hit_429,
                        retry_count=retry_count,
                        retry_after=total_retry_after
                    )
                
                return attributeid
                
            except requests.exceptions.RequestException as e:
                if attempt < max_retries - 1 and attributemetadata.status_code != 429:
                    continue
                
                # Record failed request
                if rate_limit_tracker:
                    duration = time.time() - request_start
                    rate_limit_tracker.record_request(
                        endpoint=f"get_attibuteid({entityname}.{attributename})",
                        duration=duration,
                        hit_429=hit_429,
                        retry_count=retry_count,
                        retry_after=total_retry_after
                    )
                
                raise ConnectionError(
                    f"Failed to retrieve attribute ID for '{entityname}.{attributename}': {str(e)}"
                ) from e
            except (KeyError, IndexError) as e:
                raise ValueError(
                    f"Unexpected response format when retrieving attribute '{attributename}' for entity '{entityname}': {str(e)}"
                ) from e
    
    def get_dependencylist_for_attribute(self, attributeid:str, rate_limit_tracker=None):
        """
        Retrieve all dependencies for a specific attribute.
        
        Uses the RetrieveDependenciesForDelete function to get all components that depend
        on the specified attribute.
        
        Args:
            attributeid (str): The MetadataId (GUID) of the attribute.
            rate_limit_tracker (RateLimitTracker, optional): Tracker instance to record rate limit metrics.
        
        Returns:
            dict: Full dependency JSON response containing a 'value' list with dependency objects.
                Each dependency object includes keys like 'dependentcomponenttype', 
                'dependentcomponentobjectid', 'dependencytype', etc.
        
        Raises:
            ConnectionError: If the API request fails.
            ValueError: If the response format is invalid.
        
        Example:
            >>> ops = DataverseOperations()
            >>> tracker = RateLimitTracker()
            >>> dependencies = ops.get_dependencylist_for_attribute(attr_id, rate_limit_tracker=tracker)
        """
        max_retries = 3
        url = f"{self.dataverse_envurl}api/data/v9.2/RetrieveDependenciesForDelete(ObjectId={attributeid},ComponentType=2)"
        headers = {
            'Accept': 'application/json',
            'OData-MaxVersion': '4.0',
            'OData-Version': '4.0',
            'Authorization': f'Bearer {self.token}'
        }
        
        hit_429 = False
        retry_count = 0
        total_retry_after = 0
        request_start = time.time()
        
        for attempt in range(max_retries):
            try:
                dependency = requests.get(url, headers=headers)
                
                # Handle 429 Too Many Requests with Retry-After
                if dependency.status_code == 429:
                    hit_429 = True
                    retry_count += 1
                    
                    if attempt < max_retries - 1:
                        retry_after = int(dependency.headers.get('Retry-After', 60))
                        total_retry_after += retry_after
                        print(f"Rate limit exceeded. Waiting {retry_after} seconds before retry (attempt {attempt + 1}/{max_retries})...")
                        time.sleep(retry_after)
                        continue
                
                dependency.raise_for_status()
                dependencylist = dependency.json()
                
                if 'value' not in dependencylist:
                    raise ValueError(
                        f"Unexpected response format for dependencies of attribute '{attributeid}'. "
                        f"Expected 'value' key in response."
                    )
                
                # Record successful request
                if rate_limit_tracker:
                    duration = time.time() - request_start
                    rate_limit_tracker.record_request(
                        endpoint=f"get_dependencylist_for_attribute({attributeid[:8]}...)",
                        duration=duration,
                        hit_429=hit_429,
                        retry_count=retry_count,
                        retry_after=total_retry_after
                    )
                
                return dependencylist
                
            except requests.exceptions.RequestException as e:
                if attempt < max_retries - 1 and dependency.status_code != 429:
                    continue
                
                # Record failed request
                if rate_limit_tracker:
                    duration = time.time() - request_start
                    rate_limit_tracker.record_request(
                        endpoint=f"get_dependencylist_for_attribute({attributeid[:8]}...)",
                        duration=duration,
                        hit_429=hit_429,
                        retry_count=retry_count,
                        retry_after=total_retry_after
                    )
                
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
        """
        Filter dependencies to retrieve only activated workflows and business rules.
        
        Filters for component type 29 (workflows), dependency type 2, and state code 1 (activated).
        Only includes workflows with category 0 (Classic Workflows) or category 2 (Business Rules).
        
        Args:
            dependencylist (dict): Dependency list returned from get_dependencylist_for_attribute.
                Expected to have a 'value' key containing a list of dependency objects.
        
        Returns:
            list: List of workflow metadata dictionaries, each containing:
                - name: Workflow name
                - workflowid: Workflow GUID
                - category: 0 for Classic Workflow, 2 for Business Rule
                - xaml: The workflow definition in XAML format
                - statecode: Should be 1 (activated)
        
        Raises:
            ValueError: If the dependency list structure is invalid.
        
        Example:
            >>> ops = DataverseOperations()
            >>> workflows = ops.retrieve_only_workflowdependency(dependencies)
        """
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
                    # Use SDK client.get() method to retrieve workflow
                    workflow_data = self.client.get(
                        "workflow",
                        record_id=workflowid,
                        select=["category", "xaml", "name", "statecode"]
                    )

                    if workflow_data.get('statecode') == 1 and (workflow_data.get('category')==0 or workflow_data.get('category')==2):
                        workflowlist.append(workflow_data)
                        
                except (DataverseError, KeyError, TypeError) as e:
                    print(f"Warning: Failed to retrieve workflow {workflowid}: {str(e)}")
                    continue

            return workflowlist
            
        except (KeyError, TypeError) as e:
            raise ValueError(
                f"Error processing workflow dependencies: {str(e)}"
            ) from e
    
    def get_forms_for_entity(self, entityname:str):
        """
        Retrieve all main and mobile forms for a specific entity.
        
        Queries for forms of type 2 (Main form) or type 6 (Mobile form).
        
        Args:
            entityname (str): The logical name of the entity (e.g., 'account', 'contact').
        
        Returns:
            list: List of form IDs (GUIDs) for the entity.
        
        Raises:
            ConnectionError: If the API request fails.
            ValueError: If the response format is invalid.
        
        Example:
            >>> ops = DataverseOperations()
            >>> form_ids = ops.get_forms_for_entity('account')
        """
        try:
            # Use SDK client.get() method to retrieve forms
            formslist = []
            for batch in self.client.get(
                "systemform",
                filter=f"objecttypecode eq '{entityname}' and (type eq 2 or type eq 6)",
                select=["formid"]
            ):
                for form in batch:
                    if form.get('formid'):
                        formslist.append(form.get('formid'))
            
            return formslist
            
        except DataverseError as e:
            raise ConnectionError(
                f"Failed to retrieve forms for entity '{entityname}': {str(e)}"
            ) from e
    
    def get_dependencylist_for_form(self, formids:list):
        """
        Parse FormXML directly to find web resource references.
        
        This method retrieves form metadata and extracts web resource references from FormXML
        by searching for Library, WebResource, and src attributes. This approach is more reliable
        than querying the dependency table.
        
        Args:
            formids (list): List of form GUIDs to analyze.
        
        Returns:
            list: List of dictionaries, each containing:
                - formid: The form GUID
                - webresourcename: The name of the referenced web resource
        
        Example:
            >>> ops = DataverseOperations()
            >>> form_ids = ops.get_forms_for_entity('account')
            >>> web_refs = ops.get_dependencylist_for_form(form_ids)
        """
        webresource_references = []
        
        if not formids:
            return webresource_references
        
        for formid in formids:
            try:
                # Use SDK client.get() method to retrieve form with FormXML
                form_data = self.client.get(
                    "systemform",
                    record_id=formid,
                    select=["formxml", "name"]
                )
                
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
                    
            except (DataverseError, KeyError) as e:
                print(f"Warning: Error processing form {formid}: {str(e)}")
                continue
        
        return webresource_references
    
    def retrieve_webresources_from_dependency(self, webresource_references):
        """
        Retrieve and decode web resource content from references parsed from FormXML.
        
        Accepts web resource references, queries Dataverse for each web resource by name,
        and decodes base64-encoded content. Only processes JavaScript files (webresourcetype = 3).
        
        Args:
            webresource_references (list): List of dictionaries containing:
                - formid: The form GUID
                - webresourcename: The name of the web resource to retrieve
        
        Returns:
            list: List of dictionaries, each containing:
                - name: Web resource name
                - id: Web resource GUID
                - decoded_content: Decoded JavaScript content (UTF-8 string)
        
        Example:
            >>> ops = DataverseOperations()
            >>> web_refs = ops.get_dependencylist_for_form(form_ids)
            >>> web_resources = ops.retrieve_webresources_from_dependency(web_refs)
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
                
                # Use SDK client.get() method to query web resource by name
                webresource_found = False
                for batch in self.client.get(
                    "webresource",
                    filter=f"name eq '{webresource_name}'",
                    select=["name", "webresourcetype", "content", "webresourceid"]
                ):
                    for webresource in batch:
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
                            webresource_found = True
                            break
                    
                    if webresource_found:
                        break
                        
            except (DataverseError, KeyError) as e:
                print(f"Warning: Error processing web resource '{ref.get('webresourcename', 'unknown')}': {str(e)}")
                continue
        
        return webresourcelist