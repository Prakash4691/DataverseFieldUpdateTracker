import os
import ast
import re
from llama_index.core import VectorStoreIndex, Document, StorageContext, load_index_from_storage, Settings
from llama_index.core.node_parser import SentenceSplitter
from llama_index.core.vector_stores import MetadataFilters, MetadataFilter, FilterOperator
from llama_index.llms.google_genai import GoogleGenAI
from llama_index.embeddings.google_genai import GoogleGenAIEmbedding


class DataverseWebResourceRAG:
    """
    RAG system for analyzing Microsoft Dataverse web resource JavaScript files using LlamaIndex.
    Enhanced with JavaScript preprocessing and metadata extraction.
    Detects setValue operations on fields through both direct method calls and variable assignments.
    """
    
    # JavaScript action keywords for Power Platform Client API
    ACTION_KEYWORDS = {
        'SET_VALUE': ['.setValue(', 'setAttribute'],
    }
    
    def __init__(self, webresource_file: str = "./webre.txt", persist_dir: str = "./storage_webres"):
        """
        Initialize the RAG system for Dataverse web resource analysis.
        
        Args:
            webresource_file: Path to the web resource JavaScript file
            persist_dir: Directory to persist the index
        
        Raises:
            ValueError: If GOOGLE_API_KEY environment variable is not set.
            FileNotFoundError: If the web resource file does not exist.
            RuntimeError: If RAG system initialization fails.
        """
        self.webresource_file = webresource_file
        self.persist_dir = persist_dir
        
        # Validate Google API key is set
        if not os.environ.get('GOOGLE_API_KEY'):
            raise ValueError(
                "GOOGLE_API_KEY environment variable is not set. "
                "Please set it in your .env file or environment."
            )
        
        # Validate web resource file exists
        if not os.path.exists(webresource_file):
            raise FileNotFoundError(
                f"Web resource file not found: {webresource_file}. "
                f"Please run the data retrieval script first to generate this file."
            )
        
        try:
            # Configure Google Gemini LLM and embeddings
            self.llm = GoogleGenAI(model="gemini-2.5-flash", temperature=0.1)
            self.embed_model = GoogleGenAIEmbedding(model="models/text-embedding-004")
            
            # Set global settings
            Settings.llm = self.llm
            Settings.embed_model = self.embed_model
            
            # Load or create index
            self.index = self._load_or_create_index()
            self.query_engine = self.index.as_query_engine(
                llm=self.llm,
                similarity_top_k=3,
                response_mode="compact"
            )
        except Exception as e:
            raise RuntimeError(
                f"Failed to initialize RAG system: {str(e)}. "
                f"Please verify your Google API key and network connection."
            ) from e
        
    def _extract_javascript_actions(self, js_code: str) -> list[str]:
        """
        Extract action types from JavaScript code by searching for action keywords.
        
        Args:
            js_code (str): The JavaScript code content to analyze.
        
        Returns:
            List[str]: List of action type names found (e.g., 'SET_VALUE').
        """
        actions = []
        for action_type, keywords in self.ACTION_KEYWORDS.items():
            for keyword in keywords:
                if keyword in js_code:
                    actions.append(action_type)
                    break
        return actions
    
    def _extract_fields_modified(self, js_code: str) -> list[str]:
        """
        Extract field names being modified with setValue operations.
        
        Detects setValue() calls on fields through multiple patterns including direct chained calls
        (formContext.getAttribute().setValue()), variable assignments, and deprecated Xrm.Page syntax.
        Uses case-sensitive matching.
        
        Args:
            js_code (str): The JavaScript code content to analyze.
        
        Returns:
            List[str]: Unique list of field names being modified via setValue() operations.
        """
        fields_modified = []
        
        # Pattern 1: Direct chained calls - formContext.getAttribute("fieldname").setValue(
        # Allow optional whitespace between method calls
        pattern1 = r'formContext\.\s*getAttribute\s*\(\s*["\']([\w]+)["\']\s*\)\s*\.\s*setValue\s*\('
        matches1 = re.findall(pattern1, js_code)
        fields_modified.extend(matches1)
        
        # Pattern 2: Direct chained calls - formContext.getControl("fieldname").setValue(
        pattern2 = r'formContext\.\s*getControl\s*\(\s*["\']([\w]+)["\']\s*\)\s*\.\s*setValue\s*\('
        matches2 = re.findall(pattern2, js_code)
        fields_modified.extend(matches2)
        
        # Pattern 3: Deprecated Xrm.Page.getAttribute("fieldname").setValue(
        pattern3 = r'Xrm\.\s*Page\.\s*getAttribute\s*\(\s*["\']([\w]+)["\']\s*\)\s*\.\s*setValue\s*\('
        matches3 = re.findall(pattern3, js_code)
        fields_modified.extend(matches3)
        
        # Pattern 4: Variable assignments with setValue
        # Step 4a: Find all variable assignments with getAttribute (var, let, const)
        var_pattern = r'(?:var|let|const)\s+(\w+)\s*=\s*(?:formContext|executionContext\.\s*getFormContext\s*\(\s*\))\.\s*getAttribute\s*\(\s*["\']([\w]+)["\']\s*\)'
        var_matches = re.findall(var_pattern, js_code)
        
        # Step 4b: For each variable, check if it's used with setValue
        for var_name, field_name in var_matches:
            set_value_pattern = rf'{var_name}\.\s*setValue\s*\('
            if re.search(set_value_pattern, js_code):
                fields_modified.append(field_name)
        
        # Pattern 5: executionContext.getFormContext().getAttribute("fieldname").setValue(
        pattern5 = r'executionContext\.\s*getFormContext\s*\(\s*\)\.\s*getAttribute\s*\(\s*["\']([\w]+)["\']\s*\)\s*\.\s*setValue\s*\('
        matches5 = re.findall(pattern5, js_code)
        fields_modified.extend(matches5)
        
        return list(set(fields_modified))
    
    def _preprocess_webresources(self) -> list[Document]:
        """
        Preprocess web resource file into structured documents with metadata.
        
        Reads the web resource file, parses each web resource dictionary, extracts JavaScript
        actions and modified fields, creates enriched content with metadata, and returns
        LlamaIndex Document objects ready for indexing.
        
        Returns:
            List[Document]: List of LlamaIndex Document objects with web resource data and metadata.
        
        Raises:
            IOError: If the web resource file cannot be read.
        
        Side Effects:
            Prints processing status messages for each web resource.
        """
        try:
            with open(self.webresource_file, 'r', encoding='utf-8') as f:
                content = f.read()
        except IOError as e:
            raise IOError(f"Failed to read web resource file '{self.webresource_file}': {str(e)}") from e
        
        webresource_dicts = content.strip().split('\n')
        documents = []
        
        for webres_str in webresource_dicts:
            if not webres_str.strip():
                continue
            
            try:
                webresource = ast.literal_eval(webres_str)
                name = webresource.get('name', 'Unknown')
                webres_id = webresource.get('id', 'Unknown')
                js_code = webresource.get('decoded_content', '')
                
                # Extract structured information
                actions = self._extract_javascript_actions(js_code)
                fields_modified = self._extract_fields_modified(js_code)
                
                # Create enriched content
                enriched_content = f"""WEB RESOURCE TYPE: JavaScript
NAME: {name}
WEB RESOURCE ID: {webres_id}

ACTIONS: {', '.join(actions) if actions else 'None detected'}
MODIFIED FIELDS (setValue): {', '.join(fields_modified) if fields_modified else 'None'}

ACTION DETAILS:
"""
                
                if 'SET_VALUE' in actions:
                    enriched_content += f"- Sets/updates field values using setValue()\n"
                    enriched_content += f"  Fields Modified: {', '.join(fields_modified)}\n"
                
                # Add JavaScript excerpt
                enriched_content += f"\nJavaScript Code (excerpt):\n{js_code[:1500]}\n"
                
                # Create metadata
                metadata = {
                    'webresource_name': name,
                    'webresource_id': webres_id,
                    'actions': '|'.join(actions),
                    'modified_fields': '|'.join(fields_modified),
                    'has_set_value': str('SET_VALUE' in actions),
                }
                
                doc = Document(text=enriched_content, metadata=metadata, id_=webres_id)
                documents.append(doc)
                
                print(f"✓ Processed [Web Resource]: {name}")
                print(f"  Modified fields: {fields_modified}")
                
            except (ValueError, SyntaxError) as e:
                print(f"✗ Error parsing web resource string: {e}")
                continue
            except Exception as e:
                print(f"✗ Error processing web resource: {e}")
                continue
        
        return documents
    
    def _load_or_create_index(self) -> VectorStoreIndex:
        """
        Load existing index or create new one from preprocessed web resource data.
        
        Creates a vector store index from web resource documents using LlamaIndex.
        Uses SentenceSplitter for chunking and Google embeddings for vectorization.
        If no web resources are found, creates a placeholder document to avoid errors.
        
        Returns:
            VectorStoreIndex: The created vector store index.
        
        Raises:
            RuntimeError: If index creation fails.
        
        Side Effects:
            Prints progress messages during index creation.
        """
        try:
            print("Creating new index with JavaScript preprocessing...")
            documents = self._preprocess_webresources()
            
            if not documents:
                print("⚠ No web resources found in file. Creating empty index.")
                # Create a placeholder document to avoid empty index error
                placeholder = Document(
                    text="No web resources available",
                    metadata={'webresource_name': 'None', 'webresource_id': 'None', 
                             'modified_fields': '', 'has_set_value': 'False'}
                )
                documents = [placeholder]
            
            node_parser = SentenceSplitter(chunk_size=512, chunk_overlap=100)
            
            index = VectorStoreIndex.from_documents(
                documents,
                embed_model=self.embed_model,
                transformations=[node_parser],
                show_progress=True
            )
            
            return index
        except Exception as e:
            raise RuntimeError(
                f"Failed to create vector index: {str(e)}. "
                f"This may be due to invalid web resource data or Google API issues."
            ) from e
    
    def query(self, question: str) -> str:
        """
        Query the web resource JavaScript using natural language.
        
        Args:
            question: Natural language question about the web resource
            
        Returns:
            Answer based on the indexed web resource JavaScript
        
        Raises:
            RuntimeError: If the query execution fails.
        """
        try:
            response = self.query_engine.query(question)
            return str(response)
        except Exception as e:
            raise RuntimeError(
                f"Failed to execute query '{question}': {str(e)}. "
                f"This may be due to Google API issues or an invalid query."
            ) from e
    
    def find_setvalue_webresources(self, fieldname: str) -> str:
        """
        Find all web resources with setValue operations for a specific field.
        Case-sensitive field name matching.
        
        Args:
            fieldname: The field/attribute name to search for (case-sensitive)
            
        Returns:
            LLM-generated response with web resource names and IDs, or "No webresources found"
        """
        # Create metadata filter for the specific field (case-sensitive)
        filters = MetadataFilters(
            filters=[
                MetadataFilter(
                    key="modified_fields",
                    value=fieldname,
                    operator=FilterOperator.CONTAINS
                ),
                MetadataFilter(
                    key="has_set_value",
                    value="True",
                    operator=FilterOperator.EQ
                )
            ],
            condition="and"
        )
        
        # Create filtered query engine
        filtered_engine = self.index.as_query_engine(
            llm=self.llm,
            similarity_top_k=3,
            response_mode="compact",
            filters=filters
        )
        
        response = filtered_engine.query(
            f"List all web resources that use setValue() to modify the field '{fieldname}'. "
            f"For each web resource, provide: name and ID. "
            f"Return format: Name: <webresource_name>, ID: <webresource_id>. "
            f"If no web resources are found, return 'No webresources found'."
        )
        
        result = str(response)
        
        # Check if the response indicates no results
        if not result or "no web resource" in result.lower() or "none" in result.lower():
            return "No webresources found"
        
        return result
    
    def analyze_field_updates(self) -> str:
        """
        Identify all field updates in the web resource JavaScript.
        
        Returns:
            str: LLM-generated response listing all fields modified with setValue().
        """
        return self.query(
            "What field updates occur in these web resources? List all fields that are modified with setValue()."
        )
    
    def get_webresource_by_name(self, name: str) -> str:
        """
        Get details about a specific web resource by name.
        
        Args:
            name (str): The name of the web resource to search for.
        
        Returns:
            str: LLM-generated response with web resource details including ID and modified fields.
        """
        return self.query(
            f"What actions are performed in the web resource named '{name}'? Include the ID and all fields modified."
        )
    
    def refresh_index(self):
        """
        Refresh the index by re-preprocessing the web resource file.
        
        Use this method after updating the web resource file to rebuild the vector store index
        with the latest data.
        
        Side Effects:
            Recreates self.index and self.query_engine with fresh data.
        """
        self.index = self._load_or_create_index()
        self.query_engine = self.index.as_query_engine(
            llm=self.llm,
            similarity_top_k=3,
            response_mode="compact"
        )
