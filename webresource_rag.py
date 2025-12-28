import os
import ast
import re
from typing import List, Dict
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
        """
        self.webresource_file = webresource_file
        self.persist_dir = persist_dir
        
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
        
    def _extract_javascript_actions(self, js_code: str) -> List[str]:
        """Extract action types from JavaScript code."""
        actions = []
        for action_type, keywords in self.ACTION_KEYWORDS.items():
            for keyword in keywords:
                if keyword in js_code:
                    actions.append(action_type)
                    break
        return actions
    
    def _extract_fields_modified(self, js_code: str) -> List[str]:
        """
        Extract field names being modified with setValue operations.
        Detects both direct chained calls and variable assignments.
        Case-sensitive matching.
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
    
    def _preprocess_webresources(self) -> List[Document]:
        """Preprocess web resource file into structured documents with metadata."""
        with open(self.webresource_file, 'r', encoding='utf-8') as f:
            content = f.read()
        
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
                
            except Exception as e:
                print(f"✗ Error processing web resource: {e}")
                continue
        
        return documents
    
    def _load_or_create_index(self) -> VectorStoreIndex:
        """Load existing index or create new one from preprocessed web resource data."""
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
    
    def query(self, question: str) -> str:
        """
        Query the web resource JavaScript using natural language.
        
        Args:
            question: Natural language question about the web resource
            
        Returns:
            Answer based on the indexed web resource JavaScript
        """
        response = self.query_engine.query(question)
        return str(response)
    
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
        """Identify all field updates in the web resource JavaScript."""
        return self.query(
            "What field updates occur in these web resources? List all fields that are modified with setValue()."
        )
    
    def get_webresource_by_name(self, name: str) -> str:
        """Get details about a specific web resource by name."""
        return self.query(
            f"What actions are performed in the web resource named '{name}'? Include the ID and all fields modified."
        )
    
    def refresh_index(self):
        """Refresh the index by re-preprocessing the web resource file."""
        self.index = self._load_or_create_index()
        self.query_engine = self.index.as_query_engine(
            llm=self.llm,
            similarity_top_k=3,
            response_mode="compact"
        )


# Create default RAG instance
webresource_agent = DataverseWebResourceRAG()
