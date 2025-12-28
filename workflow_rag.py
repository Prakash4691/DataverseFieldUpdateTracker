import os
import ast
import re
from typing import List, Dict
from llama_index.core import VectorStoreIndex, Document, StorageContext, load_index_from_storage, Settings
from llama_index.core.node_parser import SentenceSplitter
from llama_index.core.vector_stores import MetadataFilters, MetadataFilter, FilterOperator
from llama_index.llms.google_genai import GoogleGenAI
from llama_index.embeddings.google_genai import GoogleGenAIEmbedding


class DataverseWorkflowRAG:
    """
    RAG system for analyzing Microsoft Dataverse workflow XAML files using LlamaIndex.
    Enhanced with XAML preprocessing and metadata extraction.
    Supports both Business Rules (category=2) and Classic Workflows (category=0).
    """
    
    # XAML action keywords based on Microsoft Dataverse business rule and workflow structure
    ACTION_KEYWORDS = {
        'SET_VALUE': ['mcwc:SetAttributeValue', 'mxswa:SetEntityProperty', 'SetAttributeValueStep'],
        'SET_DEFAULT': ['mcwc:SetDefaultValue', 'SetDefaultValue'],
        'GET_VALUE': ['mxswa:GetEntityProperty', 'GetEntityProperty'],
        'SET_DISPLAY_MODE': ['mcwc:SetDisplayMode', 'SetDisplayMode'],
        'SHOW_HIDE': ['mcwc:SetVisibility', 'SetVisibility'],
        'LOCK_UNLOCK': ['SetRequiredLevel', 'IsReadOnly'],
        'UPDATE_ENTITY': ['mxswa:UpdateEntity'],  # Classic workflow update action
    }
    
    # Category mapping
    CATEGORY_NAMES = {
        0: "Classic Workflow",
        2: "Business Rule",
    }
    
    def __init__(self, workflow_file: str = "./wf.txt", persist_dir: str = "./storage"):
        """
        Initialize the RAG system for Dataverse workflow analysis.
        
        Args:
            workflow_file: Path to the workflow XAML file
            persist_dir: Directory to persist the index
        """
        self.workflow_file = workflow_file
        self.persist_dir = persist_dir
        
        # Validate Google API key is set
        if not os.environ.get('GOOGLE_API_KEY'):
            raise ValueError(
                "GOOGLE_API_KEY environment variable is not set. "
                "Please set it in your .env file or environment."
            )
        
        # Validate workflow file exists
        if not os.path.exists(workflow_file):
            raise FileNotFoundError(
                f"Workflow file not found: {workflow_file}. "
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
        
    def _extract_xaml_actions(self, xaml: str) -> List[str]:
        """Extract action types from XAML content."""
        actions = []
        for action_type, keywords in self.ACTION_KEYWORDS.items():
            for keyword in keywords:
                if keyword in xaml:
                    actions.append(action_type)
                    break
        return actions
    
    def _extract_attributes_modified(self, xaml: str) -> List[str]:
        """Extract attribute names being WRITTEN (SET operations only)."""
        # Only match SetEntityProperty, not GetEntityProperty
        set_pattern = r'<mxswa:SetEntityProperty[^>]+Attribute="([^"]+)"'
        matches = re.findall(set_pattern, xaml)
        return list(set(matches))
    
    def _extract_attributes_read(self, xaml: str) -> List[str]:
        """Extract attribute names being READ (GET operations only)."""
        # Only match GetEntityProperty
        get_pattern = r'<mxswa:GetEntityProperty[^>]+Attribute="([^"]+)"'
        matches = re.findall(get_pattern, xaml)
        return list(set(matches))
    
    def _get_workflow_type(self, category: int) -> str:
        """Get human-readable workflow type from category number."""
        return self.CATEGORY_NAMES.get(category, f"Unknown Type (Category {category})")
    
    def _preprocess_workflows(self) -> List[Document]:
        """Preprocess workflow file into structured documents with metadata."""
        try:
            with open(self.workflow_file, 'r', encoding='utf-8') as f:
                content = f.read()
        except IOError as e:
            raise IOError(f"Failed to read workflow file '{self.workflow_file}': {str(e)}") from e
        
        workflow_dicts = content.strip().split('\n')
        documents = []
        
        for workflow_str in workflow_dicts:
            if not workflow_str.strip():
                continue
            
            try:
                workflow = ast.literal_eval(workflow_str)
                name = workflow.get('name', 'Unknown')
                workflow_id = workflow.get('workflowid', 'Unknown')
                category = workflow.get('category', 0)
                xaml = workflow.get('xaml', '')
                
                # Extract structured information
                actions = self._extract_xaml_actions(xaml)
                attributes_modified = self._extract_attributes_modified(xaml)
                attributes_read = self._extract_attributes_read(xaml)
                
                # Determine workflow type
                workflow_type = self._get_workflow_type(category)
                
                # Create enriched content with proper type labeling
                enriched_content = f"""WORKFLOW TYPE: {workflow_type}
NAME: {name}
WORKFLOW ID: {workflow_id}
CATEGORY: {category}

ACTIONS: {', '.join(actions) if actions else 'None detected'}
MODIFIED ATTRIBUTES (SET): {', '.join(attributes_modified) if attributes_modified else 'None'}
READ ATTRIBUTES (GET): {', '.join(attributes_read) if attributes_read else 'None'}

ACTION DETAILS:
"""
                
                if 'SET_VALUE' in actions or 'SET_DEFAULT' in actions:
                    enriched_content += f"- Sets/updates field values (SetAttributeValue/SetEntityProperty/SetDefaultValue)\n"
                    enriched_content += f"  Fields Modified: {', '.join(attributes_modified)}\n"
                
                if 'UPDATE_ENTITY' in actions:
                    enriched_content += f"- Executes UpdateEntity operation (Classic Workflow)\n"
                
                if 'GET_VALUE' in actions:
                    enriched_content += f"- Reads field values (GetEntityProperty)\n"
                    enriched_content += f"  Fields Read: {', '.join(attributes_read)}\n"
                
                if 'SET_DISPLAY_MODE' in actions:
                    enriched_content += "- Changes field display modes\n"
                
                # Add XAML excerpt
                enriched_content += f"\nXAML (excerpt):\n{xaml[:1500]}\n"
                
                # Create metadata
                metadata = {
                    'workflow_name': name,
                    'workflow_id': workflow_id,
                    'category': str(category),
                    'workflow_type': workflow_type,
                    'actions': '|'.join(actions),
                    'modified_attributes': '|'.join(attributes_modified),
                    'read_attributes': '|'.join(attributes_read),
                    'has_set_value': str('SET_VALUE' in actions or 'SET_DEFAULT' in actions),
                }
                
                doc = Document(text=enriched_content, metadata=metadata, id_=workflow_id)
                documents.append(doc)
                
                print(f"✓ Processed [{workflow_type}]: {name}")
                print(f"  Modified fields: {attributes_modified}")
                print(f"  Read fields: {attributes_read}")
                
            except (ValueError, SyntaxError) as e:
                print(f"✗ Error parsing workflow string: {e}")
                continue
            except Exception as e:
                print(f"✗ Error processing workflow: {e}")
                continue
        
        if not documents:
            raise ValueError(
                f"No valid workflows found in '{self.workflow_file}'. "
                f"The file may be empty or contain invalid data."
            )
        
        return documents
    
    def _load_or_create_index(self) -> VectorStoreIndex:
        """Load existing index or create new one from preprocessed workflow data."""
        try:
            print("Creating new index with XAML preprocessing...")
            documents = self._preprocess_workflows()
            
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
                f"This may be due to invalid workflow data or Google API issues."
            ) from e
    
    def query(self, question: str) -> str:
        """
        Query the workflow XAML using natural language.
        
        Args:
            question: Natural language question about the workflow
            
        Returns:
            Answer based on the indexed workflow XAML
        """
        try:
            response = self.query_engine.query(question)
            return str(response)
        except Exception as e:
            raise RuntimeError(
                f"Failed to execute query '{question}': {str(e)}. "
                f"This may be due to Google API issues or an invalid query."
            ) from e
    
    def find_set_value_workflows(self, fieldname: str) -> str:
        """
        Find all workflows (business rules and classic workflows) with SET VALUE or 
        SET DEFAULT actions for a specific field.
        
        Args:
            fieldname: The field/attribute name to search for
            
        Returns:
            LLM-generated response with workflow names, IDs, and types
        """
        # Create metadata filter for the specific field
        filters = MetadataFilters(
            filters=[
                MetadataFilter(
                    key="modified_attributes",
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
            f"List all workflows (business rules and classic workflows) that set or modify the field '{fieldname}'. "
            f"For each workflow, provide: workflow type, name, and ID. "
            f"Return format: Type: <workflow_type>, Name: <workflow_name>, ID: <workflow_id>"
        )
        return str(response)
    
    def find_workflows_by_type(self, fieldname: str, category: int) -> str:
        """
        Find workflows of a specific type that modify a field.
        
        Args:
            fieldname: The field/attribute name to search for
            category: 0 for Classic Workflows, 2 for Business Rules
            
        Returns:
            LLM-generated response with workflow names and IDs
        """
        filters = MetadataFilters(
            filters=[
                MetadataFilter(
                    key="modified_attributes",
                    value=fieldname,
                    operator=FilterOperator.CONTAINS
                ),
                MetadataFilter(
                    key="has_set_value",
                    value="True",
                    operator=FilterOperator.EQ
                ),
                MetadataFilter(
                    key="category",
                    value=str(category),
                    operator=FilterOperator.EQ
                )
            ],
            condition="and"
        )
        
        filtered_engine = self.index.as_query_engine(
            llm=self.llm,
            similarity_top_k=3,
            response_mode="compact",
            filters=filters
        )
        
        workflow_type = self._get_workflow_type(category)
        response = filtered_engine.query(
            f"List all {workflow_type}s that set or modify the field '{fieldname}'. "
            f"Return format: Name: <workflow_name>, ID: <workflow_id>"
        )
        return str(response)
    
    def analyze_field_updates(self) -> str:
        """Identify all field updates in the workflow XAML."""
        return self.query(
            "What field updates occur in these workflows? List all record attributes that are modified with workflow type, name, and ID."
        )
    
    def analyze_business_rules(self) -> str:
        """Analyze business rule actions and their impact."""
        return self.query(
            "What business rule actions are defined? How do they impact form behavior or data integrity?"
        )
    
    def analyze_workflow_logic(self) -> str:
        """Analyze the overall workflow logic and conditional behavior."""
        return self.query(
            "Describe the workflow logic, including any conditional branches and their conditions."
        )
    
    def get_workflow_by_name(self, name: str) -> str:
        """Get details about a specific workflow by name."""
        return self.query(
            f"What actions are performed in the workflow named '{name}'? Include the workflow type, ID, and all actions."
        )
    
    def refresh_index(self):
        """Refresh the index by re-preprocessing the workflow file."""
        self.index = self._load_or_create_index()
        self.query_engine = self.index.as_query_engine(
            llm=self.llm,
            similarity_top_k=3,
            response_mode="compact"
        )


# Create default RAG instance
try:
    root_agent = DataverseWorkflowRAG()
except Exception as e:
    print(f"Warning: Failed to initialize default workflow RAG agent: {str(e)}")
    print("You will need to initialize DataverseWorkflowRAG() manually after resolving the issue.")
    root_agent = None
