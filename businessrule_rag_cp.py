import os
import ast
import re
from typing import List, Dict
from llama_index.core import VectorStoreIndex, Document, StorageContext, load_index_from_storage, Settings
from llama_index.core.node_parser import SentenceSplitter
from llama_index.core.vector_stores import MetadataFilters, MetadataFilter, FilterOperator
from llama_index.llms.google_genai import GoogleGenAI
from llama_index.embeddings.google_genai import GoogleGenAIEmbedding


class DataverseWorkflowRAGCP:
    """
    RAG system for analyzing Microsoft Dataverse workflow XAML files using LlamaIndex.
    Enhanced with XAML preprocessing and metadata extraction.
    Fixed version with proper field-specific filtering.
    """
    
    # XAML action keywords based on Microsoft Dataverse business rule structure
    ACTION_KEYWORDS = {
        'SET_VALUE': ['mcwc:SetAttributeValue', 'mxswa:SetEntityProperty', 'SetAttributeValueStep'],
        'SET_DEFAULT': ['mcwc:SetDefaultValue', 'SetDefaultValue'],
        'GET_VALUE': ['mxswa:GetEntityProperty', 'GetEntityProperty'],
        'SET_DISPLAY_MODE': ['mcwc:SetDisplayMode', 'SetDisplayMode'],
        'SHOW_HIDE': ['mcwc:SetVisibility', 'SetVisibility'],
        'LOCK_UNLOCK': ['SetRequiredLevel', 'IsReadOnly'],
    }
    
    def __init__(self, workflow_file: str = "./br.txt", persist_dir: str = "./storage"):
        """
        Initialize the RAG system for Dataverse workflow analysis.
        
        Args:
            workflow_file: Path to the workflow XAML file
            persist_dir: Directory to persist the index
        """
        self.workflow_file = workflow_file
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
    
    def _preprocess_workflows(self) -> List[Document]:
        """Preprocess workflow file into structured documents with metadata."""
        with open(self.workflow_file, 'r', encoding='utf-8') as f:
            content = f.read()
        
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
                
                # Create enriched content
                enriched_content = f"""BUSINESS RULE: {name}
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
                    'actions': '|'.join(actions),
                    'modified_attributes': '|'.join(attributes_modified),
                    'read_attributes': '|'.join(attributes_read),
                    'has_set_value': str('SET_VALUE' in actions or 'SET_DEFAULT' in actions),
                }
                
                doc = Document(text=enriched_content, metadata=metadata, id_=workflow_id)
                documents.append(doc)
                
                print(f"✓ Processed: {name}")
                print(f"  Modified fields: {attributes_modified}")
                print(f"  Read fields: {attributes_read}")
                
            except Exception as e:
                print(f"✗ Error processing workflow: {e}")
                continue
        
        return documents
    
    def _load_or_create_index(self) -> VectorStoreIndex:
        """Load existing index or create new one from preprocessed workflow data."""
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
    
    def query(self, question: str) -> str:
        """
        Query the workflow XAML using natural language.
        
        Args:
            question: Natural language question about the workflow
            
        Returns:
            Answer based on the indexed workflow XAML
        """
        response = self.query_engine.query(question)
        return str(response)
    
    def find_set_value_workflows(self, fieldname: str) -> str:
        """Find all workflows with SET VALUE or SET DEFAULT actions for a specific field."""
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
            f"List the business rule names and IDs that set or modify the field '{fieldname}'. "
            f"Return format: Name: <workflow_name>, ID: <workflow_id>"
        )
        return str(response)
    
    def analyze_field_updates(self) -> str:
        """Identify all field updates in the workflow XAML."""
        return self.query(
            "What field updates occur in these workflows? List all record attributes that are modified with workflow name and ID."
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
            f"What actions are performed in the workflow named '{name}'? Include the workflow ID and all actions."
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
root_agent1 = DataverseWorkflowRAGCP()
