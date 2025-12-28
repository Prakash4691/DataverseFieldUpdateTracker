# Coding Agent Instructions for Dataverse Field Update Tracker

## Project Overview

This is a Python-based tool for tracking field updates in Microsoft Dataverse by analyzing business rules and classic workflows. The tool retrieves attribute dependencies, extracts workflow XAML definitions, and uses RAG (Retrieval-Augmented Generation) with Google Gemini AI to analyze which business rules and workflows modify specific fields. Supports both Business Rules (category=2) and Classic Workflows (category=0).

## Tech Stack

- **Python**: 3.8+ (currently using 3.14 in development)
- **Microsoft Dataverse/Power Platform SDK**: For Dataverse API interactions
- **Azure Identity**: OAuth2 authentication using service principal (ClientSecretCredential)
- **LlamaIndex**: RAG framework for document indexing and querying
- **Google Gemini AI**: LLM (gemini-2.5-flash) and embeddings (text-embedding-004)
- **Requests**: HTTP library for Dataverse Web API calls
- **python-dotenv**: Environment variable management

## Project Structure

```
dataverse-field-update-tracker/
├── connect_to_dataverse.py      # Dataverse authentication handler
├── dataverse_operations.py      # Core Dataverse API operations
├── file_operations.py           # File I/O for business rule data
├── businessrule_rag_cp.py       # RAG system for XAML analysis (business rules + workflows)
├── requirements.txt             # Python dependencies
├── pyproject.toml              # Project metadata
├── .env                        # Environment variables (NOT in git)
├── .gitignore                  # Git ignore rules
└── README.md                   # Project documentation
```

## Core Components

### 1. Authentication (`connect_to_dataverse.py`)

**Class**: `ConnectToDataverse`

**Purpose**: Authenticate to Microsoft Dataverse using Azure service principal credentials.

**Key Details**:

- Uses `ClientSecretCredential` from `azure.identity`
- Reads credentials from `.env` file: `client_id`, `tenant_id`, `client_secret`, `env_url`
- Acquires OAuth2 access token via `DataverseClient.auth._acquire_token()`
- Exposes `self.token` and `self.dataverse_envurl` for use in API calls

**Environment Variables Required**:

```
client_id=<Azure AD application client ID>
tenant_id=<Azure AD tenant ID>
client_secret=<Azure AD application secret>
env_url=<Dataverse environment URL, e.g., https://org.crm.dynamics.com/>
```

### 2. Dataverse Operations (`dataverse_operations.py`)

**Class**: `DataverseOperations`

**Methods**:

- `get_attibuteid(entityname: str, attributename: str) -> str`

  - Retrieves the MetadataId of a specific attribute/field
  - Uses OData Web API: `EntityDefinitions(LogicalName='{entityname}')/Attributes`
  - Returns: attribute GUID

- `get_dependencylist_for_attribute(attributeid: str) -> dict`

  - Retrieves all dependencies for an attribute
  - Uses: `RetrieveDependenciesForDelete` function
  - Returns: full dependency JSON response

- `retrieve_only_workflowdependency(dependencylist: dict) -> list`

  - Filters dependencies for workflows or business rules
  - Filters: `dependentcomponenttype==29`, `category eq 0 or category eq 2` (workflow or businessrule), `statecode eq 1`
  - Returns: list of workflow metadata dicts

**API Patterns**:

- All requests use OData v4.0 protocol
- Headers required: `Accept: application/json`, `OData-MaxVersion: 4.0`, `OData-Version: 4.0`, `Authorization: Bearer {token}`
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

## Typical Workflow

1. **Authenticate**: Create `ConnectToDataverse` instance
2. **Get Attribute ID**: Call `get_attibuteid(entity, field)`
3. **Get Dependencies**: Call `get_dependencylist_for_attribute(attributeid)`
4. **Filter Workflows**: Call `retrieve_only_workflowdependency(dependencylist)`
5. **Save to File**: Call `create_businessrule_file(workflowlist)`
6. **Analyze with RAG**: Initialize `DataverseWorkflowRAG()` and call `find_set_value_workflows(fieldname)` or `find_workflows_by_type(fieldname, category)`

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
  - `requests` - HTTP client
  - `python-dotenv` - Environment variable loading
- Additional dependencies required (should be added to requirements.txt):
  - `azure-identity` - Azure authentication
  - `PowerPlatform-Dataverse` - Dataverse client SDK

### API Considerations

- **Rate Limiting**: Dataverse API has service protection limits
- **Token Expiration**: Access tokens expire after 1 hour - no refresh logic currently
- **OData Syntax**: Use `$select`, `$filter`, `$expand` carefully
- **XAML Size**: Business rule XAML can be very large (>1MB) - handle accordingly

## Common Tasks for Agents

### Adding New Dataverse Operations

1. Add method to `DataverseOperations` class
2. Follow existing pattern: construct URL, set headers, make request, parse JSON
3. Use `self.dataverse_envurl` and `self.token` from parent class

### Extending RAG Analysis

1. Add new action keywords to `ACTION_KEYWORDS` dict in `DataverseWorkflowRAG`
2. Create new extraction methods following `_extract_attributes_*` pattern
3. Add metadata fields to `_preprocess_workflows()` method
4. Create query methods like `find_set_value_workflows()` or `find_workflows_by_type()` for specific use cases
5. Use `_get_workflow_type()` to get human-readable workflow types from category numbers

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
2. **Error Handling**: Minimal error handling throughout
3. **Logging**: No structured logging implemented
4. **Testing**: No unit tests present
5. **Documentation**: Missing docstrings in many methods
6. **Type Hints**: Inconsistent usage of type hints
7. **Missing Dependencies**: `azure-identity` and `PowerPlatform-Dataverse` not in requirements.txt
8. **Hard-coded Values**: File names like 'wf.txt' and 'storage/' are hard-coded

## Important Notes

- **XAML Structure**: Microsoft Dataverse business rules use proprietary XAML schema
- **Component Types**: Type 29 = workflows (includes business rules, cloud flows, etc.)
- **Categories**: Category 2 = business rule, Category 0 = workflow/cloud flow
- **State Codes**: 0 = draft, 1 = activated
- **Google API Key**: Required in environment for Gemini LLM - set `GOOGLE_API_KEY`

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
