# Dataverse Field Update Tracker

A Python-based tool for tracking field updates in Microsoft Dataverse by analyzing business rules, classic workflows, and web resources. Uses RAG (Retrieval-Augmented Generation) with Google Gemini AI to intelligently identify which business rules, workflows, and JavaScript web resources modify specific fields.

## Features

- **Automated Field Dependency Tracking** - Retrieves attribute dependencies from Dataverse
- **Business Rule Analysis** - Analyzes business rule XAML to identify field updates
- **Classic Workflow Analysis** - Supports classic workflows (category=0) in addition to business rules (category=2)
- **Web Resource JavaScript Analysis** - Detects setValue operations in form scripts and web resources
- **RAG-Powered Intelligence** - Uses LlamaIndex and Google Gemini to extract field update patterns
- **XAML Action Detection** - Identifies SET_VALUE, SET_DEFAULT, GET_VALUE, UPDATE_ENTITY, and more
- **JavaScript Pattern Detection** - Detects formContext.getAttribute().setValue(), variable assignments, and deprecated patterns
- **Metadata-Based Filtering** - Query specific workflow types or field modifications
- **OAuth2 Authentication** - Secure connection to Dataverse using Azure service principal

## Quick Start

### Prerequisites

- Python 3.8 or higher
- Microsoft Dataverse environment with admin access
- Azure AD application (service principal) with Dataverse API permissions
- Google Gemini API key

### Installation

1. Clone the repository

   ```bash
   git clone https://github.com/Prakash4691/DataverseFieldUpdateTracker.git
   cd dataverse-field-update-tracker
   ```

2. Create and activate a virtual environment

   ```bash
   python3 -m venv .venv
   source .venv/bin/activate  # On Windows: .venv\Scripts\activate
   ```

3. Install dependencies

   ```bash
   pip install -r requirements.txt
   ```

4. Environment setup

   ```bash
   cp .env.example .env  # If .env.example exists, otherwise create .env manually
   ```

   Create a `.env` file with the following variables:

   ```env
   # Azure Service Principal Credentials
   client_id=<your-azure-ad-app-client-id>
   tenant_id=<your-azure-ad-tenant-id>
   client_secret=<your-azure-ad-app-secret>

   # Dataverse Environment
   env_url=https://<your-org>.crm.dynamics.com/

   # Google Gemini API
   GOOGLE_API_KEY=<your-google-gemini-api-key>
   ```

   **How to get credentials:**

   - **Azure credentials**: [Create an Azure AD app registration](https://learn.microsoft.com/en-us/power-apps/developer/data-platform/walkthrough-register-app-azure-active-directory) with Dataverse API permissions
   - **Google API key**: [Get a Gemini API key](https://ai.google.dev/tutorials/setup) from Google AI Studio

5. Run the tool

   ```bash
   # Basic usage with hardcoded entity/field
   python3 main.py

   # Example usage with RAG analysis
   python3 example_usage.py
   ```

6. Expected output
   - Creates `wf.txt` with workflow metadata
   - Creates `./storage/` directory with vector index
   - Prints analysis results showing which workflows modify the specified field

## Tech Stack

- **Language**: Python 3.8+
- **LLM**: Google Gemini (gemini-2.5-flash)
- **RAG Framework**: LlamaIndex 0.10.0+
- **Embeddings**: Google Gemini text-embedding-004
- **Dataverse SDK**: PowerPlatform-Dataverse-Client 0.1.0b3
- **Authentication**: Azure Identity (ClientSecretCredential)
- **HTTP Client**: Requests 2.28.0+
- **Configuration**: python-dotenv 1.0.0+

## Repository Structure

```
dataverse-field-update-tracker/
├── connect_to_dataverse.py       # Handles Azure authentication and Dataverse connection
├── dataverse_operations.py       # Core Dataverse API operations (get attributes, dependencies, web resources)
├── file_operations.py            # File I/O for workflow and web resource metadata
├── workflow_rag.py               # RAG system for XAML analysis using LlamaIndex
├── webresource_rag.py            # RAG system for JavaScript web resource analysis
├── main.py                       # Main script for retrieving and saving workflow/webresource data
├── example_usage.py              # Example of RAG analysis usage (workflows + web resources)
├── requirements.txt              # Python dependencies
├── pyproject.toml               # Project metadata
├── AGENTS.md                    # Detailed coding agent instructions
├── README.md                    # This file
├── .env                         # Environment variables (NOT in git)
├── .gitignore                   # Git ignore rules
├── wf.txt                       # Generated workflow metadata (created at runtime)
└── webre.txt                    # Generated web resource metadata (created at runtime)
```

## Usage Examples

### Basic Workflow Retrieval

```python
from dataverse_operations import DataverseOperations
from file_operations import ImplementationDefinitionFileOperations

# Initialize Dataverse operations
dvoperation = DataverseOperations()

# Get attribute ID for a specific field
attributeid = dvoperation.get_attibuteid('cr5b9_test1', 'cr5b9_attribmeta')

# Retrieve all dependencies for the attribute
deplist = dvoperation.get_dependencylist_for_attribute(attributeid)

# Filter for workflow dependencies only
wflist = dvoperation.retrieve_only_workflowdependency(deplist)

# Save to file for RAG analysis
ImplementationDefinitionFileOperations.create_workflow_file(wflist)
```

### RAG Analysis of Workflows

```python
from workflow_rag import root_agent

# Find all workflows that SET/modify a specific field
result = root_agent.find_set_value_workflows('cr5b9_attribmeta')
print(result)

# Find workflows by type (Business Rules only)
result = root_agent.find_workflows_by_type('cr5b9_attribmeta', category=2)
print(result)

# Find workflows by type (Classic Workflows only)
result = root_agent.find_workflows_by_type('cr5b9_attribmeta', category=0)
print(result)

# General query about field updates
result = root_agent.query("Which workflows read the cr5b9_attribmeta field?")
print(result)
```

### RAG Analysis of Web Resources

```python
from webresource_rag import webresource_agent

# Find all web resources that use setValue() on a specific field
result = webresource_agent.find_setvalue_webresources('cr5b9_attribmeta')
print(result)
# Output: Name: cr5b9_Test, ID: 6638c539-760a-ec11-b6e6-6045bd72f201

# Analyze all field updates in web resources
result = webresource_agent.analyze_field_updates()
print(result)

# Get details about a specific web resource
result = webresource_agent.get_webresource_by_name('cr5b9_Test')
print(result)
```

### Refreshing the Index

```python
# After updating wf.txt, refresh the workflow vector index
# Note: Delete ./storage folder to force complete re-indexing
import shutil
shutil.rmtree('./storage')

# After updating webre.txt, refresh the web resource vector index
shutil.rmtree('./storage_webres')

# Then re-run the RAG analysis
from workflow_rag import root_agent
from webresource_rag import webresource_agent

workflow_result = root_agent.find_set_value_workflows('your_field_name')
webres_result = webresource_agent.find_setvalue_webresources('your_field_name')
```

## Configuration

### Environment Variables

| Variable       | Description                                                     | Required |
| -------------- | --------------------------------------------------------------- | -------- |
| client_id      | Azure AD application client ID                                  | Yes      |
| tenant_id      | Azure AD tenant ID                                              | Yes      |
| client_secret  | Azure AD application secret                                     | Yes      |
| env_url        | Dataverse environment URL (e.g., https://org.crm.dynamics.com/) | Yes      |
| GOOGLE_API_KEY | Google Gemini API key for LLM and embeddings                    | Yes      |

### Customization Options

**Change LLM model** (in `workflow_rag.py`):

```python
self.llm = GoogleGenAI(model="gemini-2.5-flash", temperature=0.1)
# Change to: gemini-pro, gemini-2.0-flash, etc.
```

**Change entity/field to analyze** (in `main.py`):

```python
attributeid = dvoperation.get_attibuteid('your_entity', 'your_field')
```

**Change persist directory** (in `workflow_rag.py`):

```python
custom_rag = DataverseWorkflowRAG(persist_dir="./custom_storage")
```

## How It Works

### Architecture Overview

1. **Authentication Layer** (`connect_to_dataverse.py`)

   - Authenticates to Azure AD using service principal credentials
   - Acquires OAuth2 access token for Dataverse API

2. **Data Retrieval Layer** (`dataverse_operations.py`)

   - Retrieves attribute metadata ID from Dataverse
   - Calls `RetrieveDependenciesForDelete` function to get all dependencies
   - Filters for workflow dependencies (component type 29, categories 0 and 2, state 1)

3. **Data Processing Layer** (`file_operations.py`)

   - Extracts workflow metadata including XAML definitions
   - Writes to `wf.txt` for RAG indexing

4. **RAG Analysis Layer** (`workflow_rag.py` and `webresource_rag.py`)
   - **Workflows**: Parses workflow XAML to extract actions and field references
   - **Web Resources**: Parses JavaScript code to detect setValue operations using regex patterns
   - Creates structured metadata: name, ID, actions, modified/read attributes
   - Detects multiple JavaScript patterns:
     - Direct chained calls: `formContext.getAttribute("field").setValue()`
     - Variable assignments: `let ctrl = formContext.getAttribute("field"); ctrl.setValue()`
     - Deprecated patterns: `Xrm.Page.getAttribute("field").setValue()`
     - Optional whitespace handling for formatting variations
   - Builds vector indices using Google embeddings (separate indices for workflows and web resources)
   - Enables natural language queries via LlamaIndex + Gemini LLM

### XAML Actions Detected

| Action Type      | XAML Elements Detected                          | Purpose                    |
| ---------------- | ----------------------------------------------- | -------------------------- |
| SET_VALUE        | mcwc:SetAttributeValue, mxswa:SetEntityProperty | Sets field value           |
| SET_DEFAULT      | mcwc:SetDefaultValue                            | Sets default value         |
| GET_VALUE        | mxswa:GetEntityProperty                         | Reads field value          |
| SET_DISPLAY_MODE | mcwc:SetDisplayMode                             | Changes field visibility   |
| SHOW_HIDE        | mcwc:SetVisibility                              | Shows/hides field          |
| LOCK_UNLOCK      | SetRequiredLevel, IsReadOnly                    | Locks/unlocks field        |
| UPDATE_ENTITY    | mxswa:UpdateEntity                              | Updates entity (workflows) |

### Metadata Structure

Each workflow is indexed with:

- **workflow_name**: Display name
- **workflow_id**: Unique GUID
- **category**: "0" (workflow) or "2" (business rule)
- **workflow_type**: "Classic Workflow" or "Business Rule"
- **actions**: Pipe-separated action types
- **modified_attributes**: Pipe-separated field names being SET
- **read_attributes**: Pipe-separated field names being GET
- **has_set_value**: "True" or "False"

## API Documentation

### DataverseOperations Class

#### `get_attibuteid(entityname: str, attributename: str) -> str`

Retrieves the MetadataId (GUID) of a specific attribute.

**Parameters:**

- `entityname`: Logical name of the entity (e.g., "account", "cr5b9_test1")
- `attributename`: Logical name of the attribute (e.g., "name", "cr5b9_attribmeta")

**Returns:** Attribute GUID as string

#### `get_dependencylist_for_attribute(attributeid: str) -> dict`

Retrieves all dependencies for an attribute using `RetrieveDependenciesForDelete`.

**Parameters:**

- `attributeid`: Attribute MetadataId (GUID)

**Returns:** Full dependency JSON response

#### `retrieve_only_workflowdependency(dependencylist: dict) -> list`

Filters dependencies to return only workflows and business rules.

**Parameters:**

- `dependencylist`: Dependency response from `get_dependencylist_for_attribute`

**Returns:** List of workflow metadata dictionaries

### DataverseWorkflowRAG Class

#### `find_set_value_workflows(fieldname: str) -> str`

**Most commonly used method** - Finds all business rules AND classic workflows that SET/modify a specific field.

**Parameters:**

- `fieldname`: Name of the field to search (e.g., "cr5b9_attribmeta")

**Returns:** LLM-generated list with workflow type, names, and IDs

### DataverseWebResourceRAG Class

#### `find_setvalue_webresources(fieldname: str) -> str`

**Primary method** - Finds all web resources that use setValue() to modify a specific field. Supports case-sensitive field name matching.

**Parameters:**

- `fieldname`: Name of the field to search (e.g., "cr5b9_attribmeta") - case-sensitive

**Returns:** LLM-generated response with web resource names and IDs, or "No webresources found"

**JavaScript Patterns Detected:**

- `formContext.getAttribute("field").setValue()`
- `formContext.getControl("field").setValue()`
- `Xrm.Page.getAttribute("field").setValue()` (deprecated)
- `let/var/const ctrl = formContext.getAttribute("field"); ctrl.setValue()`
- `executionContext.getFormContext().getAttribute("field").setValue()`
- Handles optional whitespace between method calls

#### `analyze_field_updates() -> str`

Identifies all field updates across all web resources.

**Returns:** LLM-generated summary of all fields modified with setValue()

#### `get_webresource_by_name(name: str) -> str`

Retrieve details about a specific web resource by name.

**Parameters:**

- `name`: Name of the web resource (e.g., "cr5b9_Test")

**Returns:** LLM-generated description with ID and all fields modified

#### `find_workflows_by_type(fieldname: str, category: int) -> str`

Finds workflows of a specific type that modify a field.

**Parameters:**

- `fieldname`: Name of the field to search
- `category`: 0 for Classic Workflows, 2 for Business Rules

**Returns:** LLM-generated list of workflow names and IDs for the specified type

#### `query(question: str) -> str`

General natural language query interface.

**Parameters:**

- `question`: Natural language question about workflows

**Returns:** LLM-generated answer

## Troubleshooting

### Authentication Errors

**Error:** `AADSTS7000215: Invalid client secret provided`

- **Solution:** Verify `client_secret` in `.env` is correct and hasn't expired

**Error:** `AADSTS700016: Application not found`

- **Solution:** Check `client_id` and ensure the app registration exists in your Azure AD tenant

### API Errors

**Error:** `401 Unauthorized`

- **Solution:** Ensure your service principal has appropriate permissions in Dataverse
- Required permissions: `user_impersonation` scope on Dynamics CRM API

**Error:** `AttributeMetadataNotFound`

- **Solution:** Verify entity and attribute names are correct (case-sensitive logical names)

### RAG/Index Errors

**Error:** `No index found at ./storage`

- **Solution:** Run `main.py` first to generate `wf.txt`, then run `example_usage.py`

**Error:** Google API quota exceeded

- **Solution:** Check your [Google Cloud quotas](https://console.cloud.google.com/iam-admin/quotas) and increase limits if needed

**Error:** Empty results from RAG queries

- **Solution:** Delete `./storage` folder and re-run to rebuild the index

### General Issues

**Port already in use** (if running a server in future versions):

```bash
lsof -ti:5000 | xargs kill -9
```

**Module not found errors:**

```bash
pip install -r requirements.txt --upgrade
```

## Known Limitations

- Access tokens expire after 1 hour (no automatic refresh implemented)
- Large XAML files (>1MB) may cause processing delays
- No pagination for large dependency lists
- Hardcoded component type filters (currently only type 29 for workflows)
- No support for cloud flows (modern Power Automate flows)
- Limited error handling and retry logic

## Roadmap

- [ ] Add automatic token refresh logic
- [ ] Support for modern Power Automate cloud flows
- [ ] Interactive CLI with prompts for entity/field input
- [ ] Export results to CSV/JSON formats
- [ ] Add unit tests and integration tests
- [ ] Performance optimization for large XAML files
- [ ] Web UI for non-technical users
- [ ] Ribbon command JavaScript analysis
- [ ] PCF control custom code analysis
- [x] Business rule analysis (completed)
- [x] Classic workflow support (completed)
- [x] RAG-based field update detection (completed)
- [x] Web resource JavaScript analysis (completed)

## Contributing

Contributions are welcome! Follow these steps:

1. Fork the repository
2. Create a feature branch (`git checkout -b feat/amazing-feature`)
3. Commit changes (`git commit -m 'feat: add amazing feature'`)
4. Push to branch (`git push origin feat/amazing-feature`)
5. Open a Pull Request

### Commit Message Convention

- `feat:` - New features
- `fix:` - Bug fixes
- `docs:` - Documentation updates
- `refactor:` - Code restructuring
- `test:` - Test additions/updates

### Code Style

- Follow PEP 8 naming conventions
- Use type hints for public methods
- Keep methods focused and single-purpose
- Add docstrings for classes and methods

## License

This project is licensed under the MIT License - see [LICENSE](LICENSE) for details.

## Authors

- [@Prakash4691](https://github.com/Prakash4691) - Initial work and development

## Acknowledgments

- Built with [LlamaIndex](https://www.llamaindex.ai/) RAG framework
- Powered by [Google Gemini AI](https://ai.google.dev/)
- Uses [Microsoft Dataverse Web API](https://learn.microsoft.com/en-us/power-apps/developer/data-platform/webapi/overview)
- Inspired by the need for better dependency tracking in Power Platform

## Support

- **GitHub Issues**: [Report bugs or request features](https://github.com/Prakash4691/DataverseFieldUpdateTracker/issues)
- **Documentation**: See [AGENTS.md](AGENTS.md) for detailed coding agent instructions
- **Microsoft Dataverse Docs**: [Official Web API Reference](https://learn.microsoft.com/en-us/power-apps/developer/data-platform/webapi/reference/about)

---

**Need help getting started?** Check out the [Quick Start](#quick-start) section above or run the example scripts to see the tool in action!
