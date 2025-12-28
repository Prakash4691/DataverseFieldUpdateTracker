# Error Handling Improvements

This document describes the error handling improvements made to the Dataverse Field Update Tracker project.

## Overview

Comprehensive error handling has been added across all modules to provide clear, actionable error messages and gracefully handle common failure scenarios.

## Changes by Module

### 1. connect_to_dataverse.py

**Environment Variable Validation**

The module now validates that all required environment variables are present before attempting authentication:

```python
# Missing variables are detected and reported clearly
try:
    client = ConnectToDataverse()
except ValueError as e:
    # Error message: "Missing required environment variables: client_id, tenant_id. 
    #                 Please ensure these are set in your .env file."
    print(f"Configuration error: {e}")
```

**Authentication Error Handling**

Authentication failures are now caught and wrapped with helpful context:

```python
try:
    client = ConnectToDataverse()
except ConnectionError as e:
    # Error message: "Failed to authenticate to Dataverse: [original error]. 
    #                 Please verify your Azure credentials and Dataverse environment URL."
    print(f"Authentication failed: {e}")
```

**Required Environment Variables:**
- `client_id` - Azure AD application client ID
- `tenant_id` - Azure AD tenant ID
- `client_secret` - Azure AD application secret
- `env_url` - Dataverse environment URL

### 2. dataverse_operations.py

**API Request Error Handling**

All HTTP requests now include comprehensive error handling:

```python
try:
    attributeid = dvops.get_attibuteid('account', 'name')
except ConnectionError as e:
    # Handles: Network errors, timeouts, HTTP errors (401, 403, 404, 500, etc.)
    print(f"API request failed: {e}")
except ValueError as e:
    # Handles: Invalid responses, missing data, JSON parsing errors
    print(f"Invalid response: {e}")
```

**Methods with Error Handling:**

#### `get_attibuteid(entityname, attributename)`

Errors handled:
- HTTP request failures (ConnectionError)
- Empty/missing attribute data (ValueError)
- Invalid response format (ValueError)

Example error messages:
```
"Attribute 'fieldname' not found for entity 'entityname'. Please verify the entity and attribute names."
"MetadataId not found for attribute 'fieldname' in entity 'entityname'."
"Failed to retrieve attribute ID for 'entity.attribute': [details]"
```

#### `get_dependencylist_for_attribute(attributeid)`

Errors handled:
- HTTP request failures (ConnectionError)
- Invalid JSON responses (ValueError)
- Missing 'value' key in response (ValueError)

Example error messages:
```
"Unexpected response format for dependencies of attribute '[guid]'. Expected 'value' key in response."
"Failed to retrieve dependencies for attribute '[guid]': [details]"
```

#### `retrieve_only_workflowdependency(dependencylist)`

Errors handled:
- Invalid dependency list structure (ValueError)
- Individual workflow retrieval failures (printed as warnings, continues processing)
- Missing workflow data fields (continues processing)

Behavior:
- Continues processing even if some workflows fail to retrieve
- Prints warnings for failed workflows instead of stopping
- Returns list of successfully retrieved workflows

Example warning:
```
"Warning: Failed to retrieve workflow [guid]: [details]"
```

#### `get_forms_for_entity(entityname)`

Errors handled:
- HTTP request failures (ConnectionError)
- Invalid response format (ValueError)
- Missing form IDs (skips invalid entries)

#### `get_dependencylist_for_form(formids)`

Errors handled:
- Empty form ID list (returns empty list)
- Individual form retrieval failures (printed as warnings, continues)
- FormXML parsing errors (continues processing)

#### `retrieve_webresources_from_dependency(webresource_references)`

Errors handled:
- Empty reference list (returns empty list)
- Individual web resource retrieval failures (printed as warnings, continues)
- Base64 decoding errors (stores error message in content)

### 3. file_operations.py

**File I/O Error Handling**

Both file creation methods now include validation and error handling:

```python
try:
    ImplementationDefinitionFileOperations.create_workflow_file(workflowlist)
except TypeError as e:
    # Handles: Non-list input types
    print(f"Invalid input type: {e}")
except IOError as e:
    # Handles: File write failures, permission errors
    print(f"File write failed: {e}")
```

**Input Validation:**

- Validates input is a list
- Checks for empty lists (prints warning, succeeds)
- Validates individual items are dictionaries (skips invalid items with warning)
- Adds UTF-8 encoding for proper character handling

**Methods with Error Handling:**

#### `create_workflow_file(workflowlist)`

Validations:
- Input must be a list (raises TypeError)
- Empty list prints warning and returns
- Non-dict items are skipped with warning
- Successful write prints confirmation

Example output:
```
"Warning: No workflows to write to file"
"Warning: Skipping invalid workflow entry (not a dict): str"
"Successfully wrote 5 workflow(s) to wf.txt"
```

#### `create_webresourceflow_file(webresourcelist)`

Same error handling as `create_workflow_file`, but for web resources.

### 4. workflow_rag.py

**RAG Initialization Error Handling**

The RAG system now validates prerequisites before initialization:

```python
try:
    rag = DataverseWorkflowRAG()
except ValueError as e:
    # Missing GOOGLE_API_KEY
    print(f"Configuration error: {e}")
except FileNotFoundError as e:
    # Missing workflow file (wf.txt)
    print(f"File not found: {e}")
except RuntimeError as e:
    # Google API connection issues
    print(f"Initialization failed: {e}")
```

**Validation Checks:**

1. **GOOGLE_API_KEY Environment Variable**
   ```python
   # Checked before attempting to initialize LLM
   if not os.environ.get('GOOGLE_API_KEY'):
       raise ValueError("GOOGLE_API_KEY environment variable is not set...")
   ```

2. **Workflow File Existence**
   ```python
   # Checked before attempting to read/parse
   if not os.path.exists(workflow_file):
       raise FileNotFoundError(f"Workflow file not found: {workflow_file}...")
   ```

3. **LLM/Embeddings Initialization**
   ```python
   # Wrapped in try-except to catch Google API issues
   try:
       self.llm = GoogleGenAI(...)
       self.embed_model = GoogleGenAIEmbedding(...)
   except Exception as e:
       raise RuntimeError(f"Failed to initialize RAG system: {str(e)}...")
   ```

**XAML Processing Error Handling**

The workflow preprocessing now handles parsing errors gracefully:

```python
# Invalid workflow entries are skipped with error messages
try:
    workflow = ast.literal_eval(workflow_str)
    # ... process workflow ...
except (ValueError, SyntaxError) as e:
    print(f"✗ Error parsing workflow string: {e}")
    continue  # Skip this workflow, continue with others
```

**Query Error Handling**

Query operations now catch and report Google API issues:

```python
try:
    result = rag.query("Which workflows modify field X?")
except RuntimeError as e:
    # Google API errors, invalid queries
    print(f"Query failed: {e}")
```

**Empty Workflow File Handling**

If no valid workflows are found after parsing:
```python
if not documents:
    raise ValueError(
        f"No valid workflows found in '{self.workflow_file}'. "
        f"The file may be empty or contain invalid data."
    )
```

**Module-Level Initialization**

The default `root_agent` initialization is now protected:

```python
try:
    root_agent = DataverseWorkflowRAG()
except Exception as e:
    print(f"Warning: Failed to initialize default workflow RAG agent: {str(e)}")
    print("You will need to initialize DataverseWorkflowRAG() manually...")
    root_agent = None
```

This allows the module to be imported even if initialization fails.

### 5. webresource_rag.py

**Similar Error Handling to workflow_rag.py**

All improvements made to `workflow_rag.py` have been applied to `webresource_rag.py`:

- GOOGLE_API_KEY validation
- Web resource file existence check
- LLM/embeddings initialization error handling
- JavaScript parsing error handling (continues on individual failures)
- Query error handling
- Module-level initialization protection

**Differences:**

- Validates `webre.txt` instead of `wf.txt`
- Handles empty web resource lists by creating placeholder document
- Parses JavaScript code instead of XAML

## Usage Examples

### Example 1: Handling Missing Environment Variables

```python
from connect_to_dataverse import ConnectToDataverse

try:
    client = ConnectToDataverse()
    print("✓ Successfully authenticated")
except ValueError as e:
    print(f"✗ Configuration error: {e}")
    # Action: Check .env file, ensure all required variables are set
except ConnectionError as e:
    print(f"✗ Authentication failed: {e}")
    # Action: Verify credentials are correct, check network connectivity
```

### Example 2: Handling API Errors

```python
from dataverse_operations import DataverseOperations

try:
    dvops = DataverseOperations()
    attributeid = dvops.get_attibuteid('account', 'accountnumber')
    print(f"✓ Retrieved attribute ID: {attributeid}")
except ConnectionError as e:
    print(f"✗ API request failed: {e}")
    # Action: Check network, verify Dataverse URL, check token expiration
except ValueError as e:
    print(f"✗ Invalid data: {e}")
    # Action: Verify entity and attribute names are correct
```

### Example 3: Handling File Operations

```python
from file_operations import ImplementationDefinitionFileOperations

try:
    ImplementationDefinitionFileOperations.create_workflow_file(workflow_list)
    print("✓ Workflow file created successfully")
except TypeError as e:
    print(f"✗ Invalid input: {e}")
    # Action: Ensure workflow_list is a list, not None or other type
except IOError as e:
    print(f"✗ File write failed: {e}")
    # Action: Check file permissions, disk space, path validity
```

### Example 4: Handling RAG Initialization

```python
from workflow_rag import DataverseWorkflowRAG

try:
    rag = DataverseWorkflowRAG()
    result = rag.find_set_value_workflows('fieldname')
    print(f"✓ Query result: {result}")
except ValueError as e:
    print(f"✗ Configuration error: {e}")
    # Action: Set GOOGLE_API_KEY in .env file
except FileNotFoundError as e:
    print(f"✗ File not found: {e}")
    # Action: Run data retrieval script first to generate wf.txt
except RuntimeError as e:
    print(f"✗ Initialization/query failed: {e}")
    # Action: Check Google API key validity, network connection, API quotas
```

### Example 5: Graceful Degradation

The improved error handling allows partial success:

```python
# Even if some workflows fail to retrieve, processing continues
dvops = DataverseOperations()
deplist = dvops.get_dependencylist_for_attribute(attributeid)
wflist = dvops.retrieve_only_workflowdependency(deplist)

# Output might show:
# Warning: Failed to retrieve workflow abc-123: 404 Not Found
# Warning: Failed to retrieve workflow def-456: Invalid JSON
# Successfully retrieved 8 out of 10 workflows

print(f"Retrieved {len(wflist)} workflows")  # Returns the 8 successful ones
```

## Testing

To verify error handling works correctly:

1. **Test Missing Environment Variables:**
   ```bash
   # Temporarily rename .env
   mv .env .env.backup
   python3 -c "from connect_to_dataverse import ConnectToDataverse; ConnectToDataverse()"
   # Should see: ValueError with clear message about missing variables
   mv .env.backup .env
   ```

2. **Test Missing Files:**
   ```bash
   python3 -c "from workflow_rag import DataverseWorkflowRAG; DataverseWorkflowRAG(workflow_file='missing.txt')"
   # Should see: FileNotFoundError with clear message
   ```

3. **Test Invalid Input:**
   ```bash
   python3 -c "from file_operations import ImplementationDefinitionFileOperations; ImplementationDefinitionFileOperations.create_workflow_file(None)"
   # Should see: TypeError about expecting list
   ```

## Benefits

1. **Clear Error Messages**: Users get actionable information about what went wrong
2. **Graceful Degradation**: Partial failures don't stop entire operations
3. **Easier Debugging**: Stack traces include context about what operation failed
4. **Better User Experience**: Users know what to fix instead of seeing cryptic errors
5. **Robustness**: System handles edge cases and unexpected conditions

## Migration Notes

For existing code using this library:

- **No breaking changes**: All function signatures remain the same
- **New exceptions**: Code may now raise specific exceptions (ValueError, ConnectionError, etc.) instead of crashing
- **Recommendation**: Add try-except blocks around calls to handle specific error types
- **Module imports**: RAG modules can now be imported even if initialization fails (root_agent/webresource_agent may be None)

## Future Improvements

Potential enhancements for error handling:

1. Add retry logic for transient API failures
2. Add structured logging instead of print statements
3. Add timeout configuration for long-running operations
4. Add automatic token refresh for expired credentials
5. Add connection pooling and request rate limiting
6. Add metrics/monitoring for error rates
