# Dataverse Field Update Tracker

A Python-based tool for tracking field updates in Microsoft Dataverse by analyzing business rules, classic workflows, Power Automate cloud flows, and web resources. Uses RAG (Retrieval-Augmented Generation) with Google Gemini AI to intelligently identify which business rules, workflows, cloud flows, and JavaScript web resources modify specific fields.

## Features

- **Automated Field Dependency Tracking** - Retrieves attribute dependencies from Dataverse
- **Business Rule Analysis** - Analyzes business rule XAML to identify field updates
- **Classic Workflow Analysis** - Supports classic workflows (category=0) in addition to business rules (category=2)
- **Power Automate Cloud Flow Analysis** - Analyzes modern cloud flows to detect field modifications with source tracking
- **Advanced Expression Parsing** - AST-based parser for complex cloud flow expressions with Lark grammar
- **Variable Tracking** - Comprehensive tracking of variable declarations and modifications in cloud flows
- **Web Resource JavaScript Analysis** - Detects setValue operations in form scripts and web resources
- **Production-Grade Rate Limit Tracking** - Monitors API usage against Dataverse service protection limits (6000 req/5 min)
- **RAG-Powered Intelligence** - Uses LlamaIndex and Google Gemini to extract field update patterns
- **XAML Action Detection** - Identifies SET_VALUE, SET_DEFAULT, GET_VALUE, UPDATE_ENTITY, and more
- **JavaScript Pattern Detection** - Detects formContext.getAttribute().setValue(), variable assignments, and deprecated patterns
- **Cloud Flow Source Analysis** - Tracks whether field values come from triggers, variables, static values, or other sources
- **Metadata-Based Filtering** - Query specific workflow types, trigger types, or field modifications
- **OAuth2 Authentication** - Secure connection to Dataverse using Azure service principal
- **Automatic Retry Logic** - Handles 429 rate limit errors with exponential backoff

## Quick Start

### Prerequisites

- Python 3.8 or higher
- Microsoft Dataverse environment with admin access
- Azure AD application (service principal) with Dataverse API permissions
- Google Gemini API key
- PowerPlatform Dataverse SDK (included in requirements.txt)

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
   macOS/Linux (Bash/Zsh): export GOOGLE_API_KEY=<your-google-gemini-api-key>
   Windows (Command Prompt): set GOOGLE_API_KEY=<your-google-gemini-api-key>
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
   # Interactive mode (prompts for entity and field names)
   python3 main.py

   # Command-line arguments
   python3 main.py --entity account --attribute name
   python3 main.py --entity your_entity --attribute your_field

   # Example usage with RAG analysis
   python3 example_usage.py
   ```

6. Expected output
   - Creates `wf.txt` with workflow metadata
   - Creates `webre.txt` with web resource metadata
   - Creates `cloudflows.txt` with cloud flow metadata
   - Prints analysis results showing which workflows, cloud flows, or web resources modify the specified field

## Tech Stack

- **Language**: Python 3.8+
- **LLM**: Google Gemini (gemini-2.5-flash)
- **RAG Framework**: LlamaIndex 0.10.0+
- **Embeddings**: Google Gemini text-embedding-004
- **Dataverse SDK**: PowerPlatform-Dataverse-Client 0.1.0b3 (used for table operations)
- **Authentication**: Azure Identity (ClientSecretCredential)
- **HTTP Client**: Requests 2.28.0+ (used for metadata API and custom functions)
- **Configuration**: python-dotenv 1.0.0+
- **Expression Parsing**: Lark 1.1.9+ (AST-based parser for cloud flow expressions)
- **JSON Streaming**: ijson 3.3.0+ (handles large cloud flow definitions up to 1GB)
- **JSON Path**: jsonpath-ng 1.7.0+ (JSON path navigation for nested expressions)
- **Rate Limiting**: Custom RateLimitTracker with 5-minute sliding window monitoring

## Repository Structure

```
dataverse-field-update-tracker/
├── connect_to_dataverse.py       # Handles Azure authentication and DataverseClient initialization
├── dataverse_operations.py       # Core Dataverse operations (uses SDK + HTTP for specialized ops)
├── file_operations.py            # File I/O for workflow, web resource, and cloud flow metadata
├── workflow_rag.py               # RAG system for XAML analysis using LlamaIndex
├── webresource_rag.py            # RAG system for JavaScript web resource analysis
├── cloudflow_operations.py       # Cloud flow retrieval and analysis operations
├── cloudflow_rag.py              # RAG system for Power Automate cloud flow analysis
├── expression_parser.py          # Expression parser for cloud flow expressions (regex + AST)
├── rate_limit_tracker.py         # Production-grade rate limit tracking with 5-min sliding window
├── main.py                       # Main CLI application with rate limit monitoring
├── example_usage.py              # Example of RAG analysis usage (workflows + web resources + cloud flows)
├── requirements.txt              # Python dependencies (includes ijson, lark, jsonpath-ng)
├── pyproject.toml                # Project metadata
├── AGENTS.md                     # Detailed coding agent instructions
├── ERROR_HANDLING.md             # Error handling guide and best practices
├── SPEC.md                       # Cloud flow implementation specification
├── README.md                     # This file
├── .env                          # Environment variables (NOT in git)
├── .env.example                  # Template for environment configuration
├── .gitignore                    # Git ignore rules
├── wf.txt                        # Generated workflow metadata (created at runtime)
├── webre.txt                     # Generated web resource metadata (created at runtime)
├── cloudflows.txt                # Generated cloud flow metadata (created at runtime)
├── storage/                      # Vector index for workflows and business rules
├── storage_webres/               # Vector index for web resources
└── storage_cloudflows/           # Vector index for cloud flows
```

## Usage Examples

### Using the CLI Application

The simplest way to use the tool is through the command-line interface:

```bash
# Interactive mode (prompts for input)
python3 main.py

# Command-line arguments
python3 main.py --entity account --attribute name
python3 main.py --entity contact --attribute emailaddress1
```

### Programmatic Usage with DataverseFieldUpdateTrackerApp

```python
from main import DataverseFieldUpdateTrackerApp

# Initialize and run the complete workflow
app = DataverseFieldUpdateTrackerApp()
app.run('account', 'name')

# This will:
# 1. Retrieve workflows and web resources for the specified field
# 2. Generate wf.txt and webre.txt files
# 3. Perform RAG analysis and print results
```

### Basic Workflow Retrieval

```python
from dataverse_operations import DataverseOperations
from file_operations import ImplementationDefinitionFileOperations

# Initialize Dataverse operations
dvoperation = DataverseOperations()

# Get attribute ID for a specific field
# Replace 'account' and 'name' with your entity and field logical names
attributeid = dvoperation.get_attibuteid('account', 'name')

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
result = root_agent.find_set_value_workflows('your_field_name')
print(result)

# Find workflows by type (Business Rules only)
result = root_agent.find_workflows_by_type('your_field_name', category=2)
print(result)

# Find workflows by type (Classic Workflows only)
result = root_agent.find_workflows_by_type('your_field_name', category=0)
print(result)

# General query about field updates
result = root_agent.query("Which workflows read the your_field_name field?")
print(result)
```

### RAG Analysis of Web Resources

```python
from webresource_rag import webresource_agent

# Find all web resources that use setValue() on a specific field
result = webresource_agent.find_setvalue_webresources('your_field_name')
print(result)
# Output example: Name: your_webresource, ID: 6638c539-760a-ec11-b6e6-6045bd72f201

# Analyze all field updates in web resources
result = webresource_agent.analyze_field_updates()
print(result)

# Get details about a specific web resource
result = webresource_agent.get_webresource_by_name('your_webresource_name')
print(result)
```

### RAG Analysis of Cloud Flows

```python
from cloudflow_rag import cloudflow_agent

# Find all cloud flows that modify a specific field
result = cloudflow_agent.find_set_value_flows('your_field_name')
print(result)
# Output example: Flow Type: Cloud Flow, Name: Update Contact Info, ID: a1b2c3...

# Find cloud flows by trigger type that modify a field
result = cloudflow_agent.find_flows_by_trigger_type('your_field_name', 'Manual')
print(result)

# Analyze all field updates across cloud flows
result = cloudflow_agent.analyze_field_updates()
print(result)

# Get details about a specific cloud flow
result = cloudflow_agent.get_flow_by_name('your_flow_name')
print(result)

# Analyze trigger types used in cloud flows
result = cloudflow_agent.analyze_flow_triggers()
print(result)

# Analyze data sources for field updates (trigger, variable, static, etc.)
result = cloudflow_agent.analyze_source_types()
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

# After updating cloudflows.txt, refresh the cloud flow vector index
shutil.rmtree('./storage_cloudflows')

# Then re-run the RAG analysis
from workflow_rag import root_agent
from webresource_rag import webresource_agent
from cloudflow_rag import cloudflow_agent

workflow_result = root_agent.find_set_value_workflows('your_field_name')
webres_result = webresource_agent.find_setvalue_webresources('your_field_name')
cloudflow_result = cloudflow_agent.find_set_value_flows('your_field_name')
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

**Change entity/field to analyze**:

```bash
# Use command-line arguments
python3 main.py --entity your_entity --attribute your_field

# Or in code (dataverse_operations.py)
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
   - Initializes PowerPlatform DataverseClient SDK instance
   - Acquires OAuth2 access token for Dataverse API

2. **Data Retrieval Layer** (`dataverse_operations.py`)

   - Uses PowerPlatform SDK `client.get()` for table operations (workflows, forms, web resources)
   - Uses direct HTTP requests for metadata API (`EntityDefinitions`) and custom functions (`RetrieveDependenciesForDelete`)
   - Filters for workflow dependencies (component type 29, categories 0 and 2, state 1)
   - Handles pagination automatically via SDK generators

3. **Data Processing Layer** (`file_operations.py`)

   - Extracts workflow metadata including XAML definitions
   - Extracts cloud flow metadata including trigger type, actions, and field modifications
   - Writes to `wf.txt`, `webre.txt`, and `cloudflows.txt` for RAG indexing

4. **Cloud Flow Analysis Layer** (`cloudflow_operations.py`, `expression_parser.py`)

   - Retrieves all active cloud flows (category=5, statecode=1) from Dataverse
   - Uses streaming JSON parser (ijson) to handle large flow definitions (up to 1GB)
   - Parses Azure Logic Apps Workflow Definition Language expressions
   - **Phase 1**: Regex-based expression parsing for common patterns
   - **Phase 2**: AST-based parsing with Lark for complex nested expressions
   - Tracks variable declarations and modifications throughout flow execution
   - Identifies "Update a row" and "Create a new row" Dataverse actions
   - Extracts field modifications with source type tracking (trigger, variable, static, output, parameter)
   - Creates structured metadata: flow name, ID, trigger type, actions, modified fields, source types

5. **RAG Analysis Layer** (`workflow_rag.py`, `webresource_rag.py`, `cloudflow_rag.py`)
   - **Workflows**: Parses workflow XAML to extract actions and field references
   - **Web Resources**: Parses JavaScript code to detect setValue operations using regex patterns
   - **Cloud Flows**: Analyzes flow definitions to detect field modifications and source types
   - Creates structured metadata: name, ID, actions, modified/read attributes
   - Detects multiple JavaScript patterns:
     - Direct chained calls: `formContext.getAttribute("field").setValue()`
     - Variable assignments: `let ctrl = formContext.getAttribute("field"); ctrl.setValue()`
     - Deprecated patterns: `Xrm.Page.getAttribute("field").setValue()`
     - Optional whitespace handling for formatting variations
   - Builds vector indices using Google embeddings (separate indices for workflows, web resources, and cloud flows)
   - Enables natural language queries via LlamaIndex + Gemini LLM

### Rate Limit Tracking

The tool includes production-grade rate limit monitoring based on Microsoft Dataverse service protection limits:

- **Limit**: 6000 requests per 5 minutes per user
- **Sliding Window**: Tracks requests in 5-minute rolling window
- **429 Handling**: Automatically respects Retry-After headers with exponential backoff
- **Metrics Tracked**:
  - Total API requests made
  - Requests in last 5 minutes
  - 429 errors encountered
  - Retry attempts and wait times
  - Estimated time to rate limit

**Example Output:**

```
================================================================================
RATE LIMIT TRACKING SUMMARY
================================================================================
Total Requests:              15
Requests (Last 5 min):       15 / 6000 (0.25%)
429 Errors Encountered:      0
Total Retry Attempts:        0
Total Wait Time:             0.0s
Elapsed Time:                34.52s
Avg Requests/Minute:         26.08
Est. Time to Limit:          >230 minutes
================================================================================
```

**Warnings:**

- ⚠️ Alerts when rate limit hit (429 errors)
- ⚠️ Warns when approaching 80% of limit
- Provides actionable suggestions for reducing load

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

#### Workflow Metadata (wf.txt)

Each workflow is indexed with:

- **workflow_name**: Display name
- **workflow_id**: Unique GUID
- **category**: "0" (workflow) or "2" (business rule)
- **workflow_type**: "Classic Workflow" or "Business Rule"
- **actions**: Pipe-separated action types
- **modified_attributes**: Pipe-separated field names being SET
- **read_attributes**: Pipe-separated field names being GET
- **has_set_value**: "True" or "False"

#### Cloud Flow Metadata (cloudflows.txt)

Each cloud flow is indexed with:

- **flow_name**: Display name of the cloud flow
- **flow_id**: Unique GUID
- **flow_type**: "Cloud Flow"
- **trigger_type**: Trigger type (e.g., "Manual (Button)", "Automated - When a record is created or updated", "Scheduled")
- **actions**: Pipe-separated list of action names
- **modified_attributes**: Pipe-separated field names being modified
- **read_attributes**: Pipe-separated field names being read from expressions
- **source_types**: Pipe-separated field-to-source mappings (e.g., "firstname=trigger | lastname=variable")
- **has_set_value**: "True" if flow modifies fields, "False" otherwise
- **entities**: Pipe-separated list of entities referenced (e.g., "contacts | accounts")
- **parse_error**: Error message if flow parsing failed (optional field)

**Example cloudflows.txt entry:**
```
flow_name: Auto-Update Contact Names
flow_id: a1b2c3d4-e5f6-7890-abcd-ef1234567890
flow_type: Cloud Flow
trigger_type: Automated - When a record is created or updated (accounts)
actions: Get_a_row | Condition | Update_a_row | Send_email
modified_attributes: firstname | lastname | emailaddress1
read_attributes: accountid | name
source_types: firstname=trigger | lastname=variable | emailaddress1=static
has_set_value: True
entities: contacts | accounts
---
```

## API Documentation

### RateLimitTracker Class

Production-grade rate limit tracking for Dataverse API operations.

#### `__init__()`

Initializes the tracker with default metrics.

**Attributes:**

- `total_requests`: Total API requests made
- `total_429_errors`: Number of 429 rate limit errors
- `total_retries`: Total retry attempts
- `total_wait_time`: Cumulative seconds waited for rate limits
- `request_history`: List of RequestMetrics (5-minute sliding window)
- `start_time`: Tracking start timestamp

#### `record_request(endpoint: str, duration: float, hit_429: bool = False, retry_count: int = 0, retry_after: int = 0) -> None`

Records metrics for a completed API request.

**Parameters:**

- `endpoint`: Description of the API endpoint called
- `duration`: Request duration in seconds
- `hit_429`: Whether a 429 error was encountered
- `retry_count`: Number of retry attempts made
- `retry_after`: Total seconds waited due to Retry-After headers

#### `get_requests_in_last_5_minutes() -> int`

Returns count of requests in the last 5-minute sliding window.

#### `get_summary() -> Dict[str, any]`

Returns comprehensive tracking summary with all metrics.

#### `print_summary() -> None`

Prints formatted summary to console with warnings if needed.

### DataverseFieldUpdateTrackerApp Class

Main application class that orchestrates the complete workflow with rate limit tracking.

#### `__init__(dv_ops: DataverseOperations | None = None)`

Initializes the application with automatic RateLimitTracker creation.

**Parameters:**

- `dv_ops`: Optional DataverseOperations instance (defaults to new instance)

**Attributes:**

- `rate_tracker`: RateLimitTracker instance for monitoring API usage

#### `run(entityname: str, attributename: str) -> None`

Executes the complete workflow: data retrieval, file generation, RAG analysis, and rate limit reporting.

**Parameters:**

- `entityname`: Logical name of the entity (e.g., "account", "contact")
- `attributename`: Logical name of the attribute (e.g., "name", "emailaddress1")

**Features:**

- Passes rate_tracker to all API operations
- Displays progress with checkmarks
- Always prints rate limit summary (even on errors/Ctrl+C)

**Example:**

```python
from main import DataverseFieldUpdateTrackerApp

app = DataverseFieldUpdateTrackerApp()
app.run('account', 'name')
```

### DataverseOperations Class

Uses PowerPlatform Dataverse SDK for standard table operations and direct HTTP requests for specialized operations (metadata API, custom functions).

#### `get_attibuteid(entityname: str, attributename: str, rate_limit_tracker=None) -> str`

Retrieves the MetadataId (GUID) of a specific attribute using EntityDefinitions metadata API (HTTP request).

**Parameters:**

- `entityname`: Logical name of the entity (e.g., "account", "contact", "your_custom_entity")
- `attributename`: Logical name of the attribute (e.g., "name", "emailaddress1", "your_custom_field")
- `rate_limit_tracker`: Optional RateLimitTracker instance for monitoring

**Returns:** Attribute GUID as string

**Rate Limit Handling:**

- Tracks request duration
- Records 429 errors and retry attempts
- Respects Retry-After header (up to 3 retries)

#### `get_dependencylist_for_attribute(attributeid: str, rate_limit_tracker=None) -> dict`

Retrieves all dependencies for an attribute using `RetrieveDependenciesForDelete` custom function (HTTP request).

**Parameters:**

- `attributeid`: Attribute MetadataId (GUID)
- `rate_limit_tracker`: Optional RateLimitTracker instance for monitoring

**Returns:** Full dependency JSON response

**Rate Limit Handling:**

- Tracks request duration
- Records 429 errors and retry attempts
- Respects Retry-After header (up to 3 retries)

#### `retrieve_only_workflowdependency(dependencylist: dict) -> list`

Filters dependencies and retrieves workflow records using SDK `client.get()`.

**Parameters:**

- `dependencylist`: Dependency response from `get_dependencylist_for_attribute`

**Returns:** List of workflow metadata dictionaries

#### `get_forms_for_entity(entityname: str) -> list`

Retrieves form IDs for an entity using SDK `client.get("systemform")` with automatic pagination.

**Parameters:**

- `entityname`: Logical name of the entity

**Returns:** List of form GUIDs

#### `get_dependencylist_for_form(formids: list) -> list`

Retrieves form XML and parses web resource references using SDK `client.get("systemform")`.

**Parameters:**

- `formids`: List of form GUIDs

**Returns:** List of web resource references

#### `retrieve_webresources_from_dependency(webresource_references: list) -> list`

Retrieves and decodes web resource content using SDK `client.get("webresource")`.

**Parameters:**

- `webresource_references`: List of web resource reference dictionaries

**Returns:** List of decoded JavaScript web resources

### DataverseWorkflowRAG Class

#### `find_set_value_workflows(fieldname: str) -> str`

**Most commonly used method** - Finds all business rules AND classic workflows that SET/modify a specific field.

**Parameters:**

- `fieldname`: Name of the field to search (e.g., "name", "emailaddress1", "your_custom_field")

**Returns:** LLM-generated list with workflow type, names, and IDs

### DataverseWebResourceRAG Class

#### `find_setvalue_webresources(fieldname: str) -> str`

**Primary method** - Finds all web resources that use setValue() to modify a specific field. Supports case-sensitive field name matching.

**Parameters:**

- `fieldname`: Name of the field to search (e.g., "name", "emailaddress1", "your_custom_field") - case-sensitive

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

- `name`: Name of the web resource (e.g., "prefix_WebResourceName")

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

### DataverseCloudFlowRAG Class

#### `find_set_value_flows(fieldname: str) -> str`

**Primary method** - Finds all cloud flows that modify a specific field.

**Parameters:**

- `fieldname`: Name of the field to search (e.g., "firstname", "emailaddress1")

**Returns:** LLM-generated response with flow names and IDs, or "No cloud flows found that modify this field"

**Example:**
```python
from cloudflow_rag import cloudflow_agent

result = cloudflow_agent.find_set_value_flows('emailaddress1')
print(result)
# Output: Flow Type: Cloud Flow, Name: Update Contact Email, ID: abc123...
```

#### `find_flows_by_trigger_type(fieldname: str, trigger_type: str) -> str`

Finds cloud flows of a specific trigger type that modify a field.

**Parameters:**

- `fieldname`: Name of the field to search
- `trigger_type`: Trigger type to filter by (e.g., "Manual", "Automated", "Scheduled")

**Returns:** LLM-generated list of flow names, IDs, and trigger types

**Example:**
```python
result = cloudflow_agent.find_flows_by_trigger_type('firstname', 'Manual')
```

#### `analyze_field_updates() -> str`

Identifies all field updates across all cloud flows.

**Returns:** LLM-generated summary of all fields modified with flow details

#### `get_flow_by_name(name: str) -> str`

Get details about a specific cloud flow by name.

**Parameters:**

- `name`: Name of the cloud flow

**Returns:** LLM-generated description with flow ID, trigger type, modified fields, and actions

#### `analyze_flow_triggers() -> str`

Analyzes trigger types across all cloud flows.

**Returns:** LLM-generated summary of trigger distribution (manual vs automated vs scheduled)

#### `analyze_source_types() -> str`

Analyzes data source types used in field updates.

**Returns:** LLM-generated description of how fields get their values (trigger, variable, static, output, parameter)

#### `query(question: str) -> str`

General natural language query interface for cloud flows.

**Parameters:**

- `question`: Natural language question about cloud flows

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
- Hardcoded component type filters (currently only type 29 for workflows)
- Cloud flow expression parser may not handle all edge cases (complex nested expressions)
- Rate limit tracking is informational only (does not throttle requests proactively)
- Cloud flow parsing errors are logged but flows with errors are skipped

## Roadmap

- [ ] Add automatic token refresh logic
- [ ] Export results to CSV/JSON formats
- [ ] Add unit tests and integration tests
- [ ] Performance optimization for large XAML files
- [ ] Web UI for non-technical users
- [ ] Ribbon command JavaScript analysis
- [ ] PCF control custom code analysis
- [ ] Proactive request throttling before hitting limits
- [ ] Enhanced cloud flow expression parsing (handle more edge cases)
- [x] Power Automate cloud flow support (completed)
- [x] AST-based expression parser with Lark (completed)
- [x] Variable tracking in cloud flows (completed)
- [x] Cloud flow source type analysis (completed)
- [x] Production-grade rate limit tracking (completed)
- [x] Automatic retry logic with exponential backoff (completed)
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
