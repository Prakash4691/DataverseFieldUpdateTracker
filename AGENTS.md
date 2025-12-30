# Coding Agent Instructions for Dataverse Field Update Tracker

## Project Overview

This is a Python-based tool for tracking field updates in Microsoft Dataverse by analyzing business rules, classic workflows, and JavaScript web resources. The tool retrieves attribute dependencies, extracts workflow XAML definitions and web resource JavaScript code, and uses RAG (Retrieval-Augmented Generation) with Google Gemini AI to analyze which business rules, workflows, and web resources modify specific fields. Supports Business Rules (category=2), Classic Workflows (category=0), and Form Script Web Resources.

## Tech Stack

- **Python**: 3.8+ (currently using 3.14 in development)
- **Microsoft Dataverse/Power Platform SDK**: PowerPlatform-Dataverse-Client for table operations
- **Azure Identity**: OAuth2 authentication using service principal (ClientSecretCredential)
- **LlamaIndex**: RAG framework for document indexing and querying
- **Google Gemini AI**: LLM (gemini-2.5-flash) and embeddings (text-embedding-004)
- **Requests**: HTTP library for metadata API and custom functions
- **python-dotenv**: Environment variable management

## Project Structure

```
dataverse-field-update-tracker/
├── connect_to_dataverse.py      # Dataverse authentication handler
├── dataverse_operations.py      # Core Dataverse API operations (workflows + web resources)
├── file_operations.py           # File I/O for workflow and web resource data
├── workflow_rag.py              # RAG system for XAML analysis (business rules + workflows)
├── webresource_rag.py           # RAG system for JavaScript web resource analysis
├── main.py                      # Main execution script
├── example_usage.py             # Example usage of RAG systems
├── requirements.txt             # Python dependencies
├── pyproject.toml              # Project metadata
├── .env                        # Environment variables (NOT in git)
├── .gitignore                  # Git ignore rules
├── README.md                   # Project documentation
├── AGENTS.md                   # This file
├── wf.txt                      # Generated workflow metadata
└── webre.txt                   # Generated web resource metadata
```

## Core Components

### 1. Authentication (`connect_to_dataverse.py`)

**Class**: `ConnectToDataverse`

**Purpose**: Authenticate to Microsoft Dataverse using Azure service principal credentials and initialize the DataverseClient SDK.

**Key Details**:

- Uses `ClientSecretCredential` from `azure.identity`
- Reads credentials from `.env` file: `client_id`, `tenant_id`, `client_secret`, `env_url`
- Creates `DataverseClient` instance from PowerPlatform SDK
- Acquires OAuth2 access token via `DataverseClient.auth._acquire_token()`
- Exposes `self.client`, `self.token`, and `self.dataverse_envurl` for use in API calls

**Environment Variables Required**:

```
client_id=<Azure AD application client ID>
tenant_id=<Azure AD tenant ID>
client_secret=<Azure AD application secret>
env_url=<Dataverse environment URL, e.g., https://org.crm.dynamics.com/>
```

### 2. Dataverse Operations (`dataverse_operations.py`)

**Class**: `DataverseOperations`

**Purpose**: Provides methods for interacting with Microsoft Dataverse using both PowerPlatform SDK and direct HTTP requests.

**Implementation Strategy**:
- **SDK Methods** (`client.get()`): Used for standard table operations (workflows, forms, web resources)
- **HTTP Requests**: Used for metadata API (`EntityDefinitions`) and custom functions (`RetrieveDependenciesForDelete`)

**Methods**:

- `get_attibuteid(entityname: str, attributename: str) -> str`

  - Retrieves the MetadataId of a specific attribute/field
  - **Implementation**: Direct HTTP request to EntityDefinitions metadata API (not supported by SDK)
  - Uses OData Web API: `EntityDefinitions(LogicalName='{entityname}')/Attributes`
  - Returns: attribute GUID

- `get_dependencylist_for_attribute(attributeid: str) -> dict`

  - Retrieves all dependencies for an attribute
  - **Implementation**: Direct HTTP request to `RetrieveDependenciesForDelete` custom function (not supported by SDK)
  - Returns: full dependency JSON response

- `retrieve_only_workflowdependency(dependencylist: dict) -> list`

  - Filters dependencies for workflows or business rules
  - **Implementation**: Uses SDK `client.get("workflow", record_id=..., select=[...])`
  - Filters: `dependentcomponenttype==29`, `category eq 0 or category eq 2` (workflow or businessrule), `statecode eq 1`
  - Returns: list of workflow metadata dicts

- `get_forms_for_entity(entityname: str) -> list`

  - Retrieves main and mobile forms for an entity
  - **Implementation**: Uses SDK `client.get("systemform", filter=..., select=[...])`
  - Handles pagination automatically via generator
  - Returns: list of form GUIDs

- `get_dependencylist_for_form(formids: list) -> list`

  - Parses FormXML to find web resource references
  - **Implementation**: Uses SDK `client.get("systemform", record_id=..., select=[...])`
  - Extracts web resource names using regex patterns
  - Returns: list of web resource reference dicts

- `retrieve_webresources_from_dependency(webresource_references: list) -> list`

  - Retrieves and decodes web resource JavaScript content
  - **Implementation**: Uses SDK `client.get("webresource", filter=..., select=[...])`
  - Decodes base64-encoded content
  - Returns: list of decoded web resource dicts

**Error Handling**:

- Imports `DataverseError` from `PowerPlatform.Dataverse.core.errors`
- SDK methods catch `DataverseError`, `KeyError`, `TypeError`
- HTTP methods catch `requests.exceptions.RequestException`

**API Patterns**:

- **SDK Calls**: Use `self.client.get(table_name, record_id=..., select=..., filter=...)`
- **HTTP Calls**: Use OData v4.0 protocol with manual URL construction
- Headers for HTTP: `Accept: application/json`, `OData-MaxVersion: 4.0`, `OData-Version: 4.0`, `Authorization: Bearer {token}`
- Base URL format: `{env_url}api/data/v9.2/`

### 3. File Operations (`file_operations.py`)

**Class**: `ImplementationDefinitionFileOperations`

**Method**:

- `create_businessrule_file(workflowlist: list) -> None`
  - Writes workflow metadata to `wf.txt`
  - Filters out OData metadata keys (keys containing '@')
  - Format: Each workflow dict on a new line as string representation

### 4. RAG System (`workflow_rag.py`)

**Class**: `DataverseWorkflowRAG`

**Purpose**: Analyze workflow XAML files using RAG to identify field updates and business logic. Supports both Business Rules (category=2) and Classic Workflows (category=0).

**Key Features**:

- **XAML Action Detection**: Identifies SET_VALUE, SET_DEFAULT, GET_VALUE, SET_DISPLAY_MODE, SHOW_HIDE, LOCK_UNLOCK, UPDATE_ENTITY actions
- **Attribute Extraction**:
  - Modified attributes: Fields being SET (SetEntityProperty, SetAttributeValue)
  - Read attributes: Fields being GET (GetEntityProperty)
- **Metadata Indexing**: Creates searchable index with structured metadata
- **Filtered Queries**: Supports metadata-based filtering for specific fields

**Methods**:

- `__init__(workflow_file='./wf.txt', persist_dir='./storage')`

  - Initializes LLM (Gemini 2.5 Flash) and embeddings (text-embedding-004)
  - Loads or creates vector index

- `_extract_xaml_actions(xaml: str) -> List[str]`

  - Detects action keywords in XAML

- `_extract_attributes_modified(xaml: str) -> List[str]`

  - Regex: `<mxswa:SetEntityProperty[^>]+Attribute="([^"]+)"`
  - Returns unique field names being modified

- `_extract_attributes_read(xaml: str) -> List[str]`

  - Regex: `<mxswa:GetEntityProperty[^>]+Attribute="([^"]+)"`
  - Returns unique field names being read

- `_get_workflow_type(category: int) -> str`

  - Maps category number to human-readable workflow type
  - Returns: "Business Rule" for category=2, "Classic Workflow" for category=0

- `find_set_value_workflows(fieldname: str) -> str`

  - **Most Important Method**: Finds all business rules AND classic workflows that SET/modify a specific field
  - Uses metadata filters: `modified_attributes` CONTAINS fieldname AND `has_set_value` EQ True
  - Returns: LLM-generated list with workflow type, names, and IDs

- `find_workflows_by_type(fieldname: str, category: int) -> str`

  - Finds workflows of a specific type that modify a field
  - category: 0 for Classic Workflows, 2 for Business Rules
  - Returns: LLM-generated list of workflow names and IDs for the specified type

- `analyze_field_updates() -> str`

  - Identifies all field updates across all workflows

- `query(question: str) -> str`
  - General natural language query interface

**Metadata Structure**:

```python
{
    'workflow_name': str,
    'workflow_id': str,
    'category': str,  # "2" = business rule, "0" = classic workflow
    'workflow_type': str,  # "Business Rule" or "Classic Workflow"
    'actions': str,  # pipe-separated action types (includes UPDATE_ENTITY for workflows)
    'modified_attributes': str,  # pipe-separated field names
    'read_attributes': str,  # pipe-separated field names
    'has_set_value': str  # "True" or "False"
}
```

### 5. Web Resource RAG System (`webresource_rag.py`)

**Class**: `DataverseWebResourceRAG`

**Purpose**: Analyze web resource JavaScript files using RAG to identify field setValue operations. Detects field modifications in form scripts through multiple JavaScript patterns.

**Key Features**:

- **JavaScript Pattern Detection**: Identifies setValue operations using regex
- **Multiple Pattern Support**: Direct calls, variable assignments, deprecated patterns
- **Whitespace Handling**: Flexible regex to handle formatting variations
- **Case-Sensitive Matching**: Field names matched case-sensitively
- **Metadata Indexing**: Creates searchable index with structured metadata
- **Filtered Queries**: Supports metadata-based filtering for specific fields

**Methods**:

- `__init__(webresource_file='./webre.txt', persist_dir='./storage_webres')`

  - Initializes LLM (Gemini 2.5 Flash) and embeddings (text-embedding-004)
  - Loads or creates vector index

- `_extract_javascript_actions(js_code: str) -> List[str]`

  - Detects action keywords in JavaScript code

- `_extract_fields_modified(js_code: str) -> List[str]`

  - Regex patterns:
    - `formContext\.\s*getAttribute\s*\(\s*["'](\w+)["']\s*\)\s*\.\s*setValue\s*\(`
    - `formContext\.\s*getControl\s*\(\s*["'](\w+)["']\s*\)\s*\.\s*setValue\s*\(`
    - `Xrm\.\s*Page\.\s*getAttribute\s*\(\s*["'](\w+)["']\s*\)\s*\.\s*setValue\s*\(`
    - Variable assignments: `(?:var|let|const)\s+(\w+)\s*=\s*(?:formContext|executionContext\.\s*getFormContext\s*\(\s*\))\.\.\s*getAttribute\s*\(\s*["'](\w+)["']\s*\)` followed by `\1\.\s*setValue\s*\(`
  - Returns unique field names being modified

- `find_setvalue_webresources(fieldname: str) -> str`

  - **Most Important Method**: Finds all web resources that use setValue() on a specific field
  - Uses metadata filters: `modified_fields` CONTAINS fieldname AND `has_set_value` EQ True
  - Returns: LLM-generated list with web resource names and IDs, or "No webresources found"

- `analyze_field_updates() -> str`

  - Identifies all field updates across all web resources

- `query(question: str) -> str`
  - General natural language query interface

**Metadata Structure**:

```python
{
    'webresource_name': str,
    'webresource_id': str,
    'actions': str,  # pipe-separated action types
    'modified_fields': str,  # pipe-separated field names
    'has_set_value': str  # "True" or "False"
}
```

**JavaScript Patterns Detected**:

1. **Direct chained calls**: `formContext.getAttribute("field").setValue(value)`
2. **Control setValue**: `formContext.getControl("field").setValue(value)`
3. **Deprecated Xrm.Page**: `Xrm.Page.getAttribute("field").setValue(value)`
4. **Variable assignments**:
   ```javascript
   let ctrl = formContext.getAttribute("field");
   ctrl.setValue(value);
   ```
5. **ExecutionContext chain**: `executionContext.getFormContext().getAttribute("field").setValue(value)`
6. **Whitespace variations**: `formContext. getAttribute("field"). setValue(value)`

## Typical Workflow

### Workflow Analysis

1. **Authenticate**: Create `ConnectToDataverse` instance
2. **Get Attribute ID**: Call `get_attibuteid(entity, field)`
3. **Get Dependencies**: Call `get_dependencylist_for_attribute(attributeid)`
4. **Filter Workflows**: Call `retrieve_only_workflowdependency(dependencylist)`
5. **Save to File**: Call `create_workflow_file(workflowlist)` → generates `wf.txt`
6. **Analyze with RAG**: Initialize `DataverseWorkflowRAG()` and call `find_set_value_workflows(fieldname)` or `find_workflows_by_type(fieldname, category)`

### Web Resource Analysis

1. **Authenticate**: Create `ConnectToDataverse` instance
2. **Get Entity Forms**: Call `get_forms_for_entity(entityname)`
3. **Get Form Dependencies**: Call `get_dependencylist_for_form(formslist)`
4. **Filter Web Resources**: Call `retrieve_webresources_from_dependency(deplistform)`
5. **Save to File**: Call `create_webresourceflow_file(webreslist)` → generates `webre.txt`
6. **Analyze with RAG**: Initialize `DataverseWebResourceRAG()` and call `find_setvalue_webresources(fieldname)`

## Coding Standards

### Code Style

- Use classes for logical grouping of related functionality
- Follow PEP 8 naming conventions (snake_case for functions/variables)
- Type hints are used sparingly but should be added for public methods
- Keep methods focused and single-purpose

### Error Handling

- Currently minimal error handling - improvements needed
- Consider adding try-except blocks for API calls
- Validate environment variables exist before use
- Handle missing keys in API responses gracefully

### Security

- Never commit `.env` file (already in `.gitignore`)
- Access tokens should not be logged or printed
- Client secrets must remain confidential

### Dependencies

- Install via: `pip install -r requirements.txt`
- Key packages:
  - `llama-index` - RAG framework core
  - `llama-index-llms-google-genai` - Google Gemini LLM integration
  - `llama-index-embeddings-google-genai` - Google embeddings
  - `azure-identity` - Azure authentication
  - `PowerPlatform-Dataverse-Client` - Dataverse SDK for table operations
  - `requests` - HTTP client for metadata API and custom functions
  - `python-dotenv` - Environment variable loading

### API Considerations

- **Rate Limiting**: Dataverse API has service protection limits
- **Token Expiration**: Access tokens expire after 1 hour - no refresh logic currently
- **SDK vs HTTP**: Use SDK for table operations, HTTP for metadata/custom functions
- **Pagination**: SDK handles pagination automatically via generators
- **OData Syntax**: Use `$select`, `$filter`, `$expand` carefully in HTTP calls
- **XAML Size**: Business rule XAML can be very large (>1MB) - handle accordingly
- **Error Types**: SDK raises `DataverseError`, HTTP raises `RequestException`

## Common Tasks for Agents

### Adding New Dataverse Operations

1. **Determine Implementation Method**:
   - Use SDK `client.get()` for standard table queries
   - Use HTTP requests for metadata API or custom functions

2. **For SDK-based operations**:
   - Use `self.client.get(table_name, record_id=..., select=..., filter=...)`
   - Handle pagination with generator: `for batch in self.client.get(...)`
   - Catch `DataverseError` from `PowerPlatform.Dataverse.core.errors`

3. **For HTTP-based operations**:
   - Construct URL with `self.dataverse_envurl`
   - Set OData headers and Authorization with `self.token`
   - Catch `requests.exceptions.RequestException`

**Example SDK Usage**:
```python
# Single record
workflow = self.client.get("workflow", record_id=workflow_id, select=["name", "xaml"])

# Multiple records with pagination
for batch in self.client.get("systemform", filter="type eq 2", select=["formid"]):
    for form in batch:
        process(form)
```

**Example HTTP Usage**:
```python
# For metadata or custom functions not in SDK
response = requests.get(
    f"{self.dataverse_envurl}api/data/v9.2/EntityDefinitions(...)",
    headers={
        'Accept': 'application/json',
        'Authorization': f'Bearer {self.token}'
    }
)
```

### Extending RAG Analysis

**For Workflows** (`workflow_rag.py`):

1. Add new action keywords to `ACTION_KEYWORDS` dict in `DataverseWorkflowRAG`
2. Create new extraction methods following `_extract_attributes_*` pattern
3. Add metadata fields to `_preprocess_workflows()` method
4. Create query methods like `find_set_value_workflows()` or `find_workflows_by_type()` for specific use cases
5. Use `_get_workflow_type()` to get human-readable workflow types from category numbers

**For Web Resources** (`webresource_rag.py`):

1. Add new action keywords to `ACTION_KEYWORDS` dict in `DataverseWebResourceRAG`
2. Create new JavaScript extraction methods following `_extract_fields_*` pattern
3. Add new regex patterns to `_extract_fields_modified()` for additional JavaScript patterns
4. Add metadata fields to `_preprocess_webresources()` method
5. Create query methods like `find_setvalue_webresources()` for specific use cases
6. Important: Use `\s*` in regex patterns to handle optional whitespace
7. Important: Support `var`, `let`, and `const` for variable declarations

### Adding New Entity Types

1. Update component type filters in `retrieve_only_*dependency` methods
2. Reference: Dataverse component types (29=workflow, 2=attribute, etc.)
3. See Microsoft docs for complete list

### Improving Error Handling

1. Add validation in `ConnectToDataverse.__init__()` for missing env vars
2. Add response status code checks in API calls
3. Add retry logic for transient failures
4. Log errors appropriately

## Known Issues & TODOs

1. **Token Refresh**: No logic to refresh expired tokens
2. **Error Handling**: Could be improved with better retry logic
3. **Logging**: No structured logging implemented
4. **Testing**: No unit tests present
5. **Documentation**: Could add more inline comments
6. **Type Hints**: Inconsistent usage of type hints
7. **Hard-coded Values**: File names like 'wf.txt' and 'storage/' are hard-coded

## Important Notes

- **SDK vs HTTP**: SDK used for table queries (workflows, forms, webresources); HTTP used for metadata API and custom functions
- **Pagination**: SDK handles pagination automatically via generators returning batches
- **Error Handling**: SDK operations catch `DataverseError`; HTTP operations catch `RequestException`
- **XAML Structure**: Microsoft Dataverse business rules use proprietary XAML schema
- **Component Types**: Type 29 = workflows (includes business rules, cloud flows, etc.), Type 61 = web resources
- **Categories**: Category 2 = business rule, Category 0 = workflow/cloud flow
- **State Codes**: 0 = draft, 1 = activated
- **Google API Key**: Required in environment for Gemini LLM - set `GOOGLE_API_KEY`
- **JavaScript Patterns**: Power Platform Client API uses formContext object (modern) and Xrm.Page (deprecated)
- **Case Sensitivity**: Field names in JavaScript are case-sensitive - regex patterns preserve this
- **Whitespace Handling**: Web resource RAG uses `\s*` in regex to handle formatting variations
- **Variable Declarations**: Support `var`, `let`, and `const` for JavaScript variable assignments
- **Separate Indices**: Workflows use `./storage/` directory, web resources use `./storage_webres/` directory

## References

- [Microsoft Dataverse Web API Reference](https://learn.microsoft.com/en-us/power-apps/developer/data-platform/webapi/reference/about)
- [OData v4.0 Protocol](https://www.odata.org/documentation/)
- [LlamaIndex Documentation](https://docs.llamaindex.ai/)
- [Google Gemini API](https://ai.google.dev/docs)
- [Azure Identity Library](https://learn.microsoft.com/en-us/python/api/azure-identity/)

## Questions or Issues?

When working on this codebase:

1. Check `.env` for correct Dataverse environment URL and credentials
2. Ensure all dependencies are installed: `pip install -r requirements.txt`
3. Verify Python version compatibility (3.8+)
4. Check Dataverse API service protection limits if requests fail
5. Ensure Google API key is set for RAG functionality
