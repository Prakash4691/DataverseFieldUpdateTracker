"""
RAG system for analyzing Power Automate Cloud Flows using LlamaIndex.

This module provides a Retrieval-Augmented Generation system for querying
and analyzing cloud flow field updates in Microsoft Dataverse.
"""

import os
from llama_index.core import VectorStoreIndex, Document, Settings
from llama_index.core.node_parser import SentenceSplitter
from llama_index.core.vector_stores import MetadataFilters, MetadataFilter, FilterOperator
from llama_index.llms.google_genai import GoogleGenAI
from llama_index.embeddings.google_genai import GoogleGenAIEmbedding


class DataverseCloudFlowRAG:
    """
    RAG system for analyzing Power Automate cloud flows using LlamaIndex.

    Supports querying cloud flows by field modifications, trigger types,
    and general natural language questions about flow logic.
    """

    def __init__(self, cloudflow_file: str = "./cloudflows.txt", persist_dir: str = "./storage_cloudflows"):
        """
        Initialize the RAG system for cloud flow analysis.

        Args:
            cloudflow_file: Path to the cloudflows.txt file
            persist_dir: Directory to persist the index

        Raises:
            ValueError: If GOOGLE_API_KEY environment variable is not set.
            FileNotFoundError: If the cloudflow file does not exist.
            RuntimeError: If RAG system initialization fails.
        """
        self.cloudflow_file = cloudflow_file
        self.persist_dir = persist_dir

        # Validate Google API key is set
        if not os.environ.get('GOOGLE_API_KEY'):
            raise ValueError(
                "GOOGLE_API_KEY environment variable is not set. "
                "Please set it in your .env file or environment."
            )

        # Validate cloudflow file exists
        if not os.path.exists(cloudflow_file):
            raise FileNotFoundError(
                f"Cloud flow file not found: {cloudflow_file}. "
                f"Please run the data retrieval script first to generate this file."
            )

        try:
            # Configure Google Gemini LLM and embeddings
            self.setup_llm()

            # Load or create index
            self.index = self._load_or_create_index()
            self.query_engine = self.index.as_query_engine(
                llm=self.llm,
                similarity_top_k=5,
                response_mode="compact"
            )
        except Exception as e:
            raise RuntimeError(
                f"Failed to initialize cloud flow RAG system: {str(e)}. "
                f"Please verify your Google API key and network connection."
            ) from e

    def setup_llm(self) -> None:
        """Configure LLM and embeddings using Google Gemini.

        Sets up the Gemini 2.5 Flash model for LLM and text-embedding-004 for embeddings.
        Configures global LlamaIndex settings.
        """
        self.llm = GoogleGenAI(model="gemini-2.5-flash", temperature=0.1)
        self.embed_model = GoogleGenAIEmbedding(model="models/text-embedding-004")

        # Set global settings
        Settings.llm = self.llm
        Settings.embed_model = self.embed_model

    def _preprocess_cloudflows(self) -> list[Document]:
        """
        Preprocess cloudflows.txt into structured documents with metadata.

        Reads the cloudflows.txt file, parses each flow entry, extracts metadata
        about modified fields, trigger types, and source types, then creates
        enriched content for vector indexing.

        Returns:
            List of LlamaIndex Document objects with cloud flow data and metadata.

        Raises:
            IOError: If the cloudflow file cannot be read.
            ValueError: If no valid cloud flows are found in the file.
        """
        try:
            with open(self.cloudflow_file, 'r', encoding='utf-8') as f:
                content = f.read()
        except IOError as e:
            raise IOError(f"Failed to read cloudflow file '{self.cloudflow_file}': {str(e)}") from e

        # Split by separator (---)
        flow_entries = content.strip().split('---')
        documents = []

        for entry in flow_entries:
            if not entry.strip():
                continue

            try:
                # Parse flow entry
                flow_data = {}
                for line in entry.strip().split('\n'):
                    if ':' in line:
                        key, value = line.split(':', 1)
                        flow_data[key.strip()] = value.strip()

                # Skip flows with parse errors
                if 'parse_error' in flow_data:
                    print(f"⚠ Skipped flow with parse error: {flow_data.get('flow_name', 'Unknown')}")
                    continue

                # Extract required fields
                flow_name = flow_data.get('flow_name', 'Unknown')
                flow_id = flow_data.get('flow_id', 'Unknown')
                trigger_type = flow_data.get('trigger_type', 'Unknown')
                actions = flow_data.get('actions', '').split(' | ') if flow_data.get('actions') else []
                modified_attributes = flow_data.get('modified_attributes', '').split(' | ') if flow_data.get('modified_attributes') else []
                read_attributes = flow_data.get('read_attributes', '').split(' | ') if flow_data.get('read_attributes') else []
                source_types = flow_data.get('source_types', '').split(' | ') if flow_data.get('source_types') else []
                has_set_value = flow_data.get('has_set_value', 'False')
                entities = flow_data.get('entities', '').split(' | ') if flow_data.get('entities') else []

                # Create enriched content
                enriched_content = f"""FLOW TYPE: Cloud Flow
NAME: {flow_name}
FLOW ID: {flow_id}
TRIGGER TYPE: {trigger_type}

ACTIONS: {', '.join(actions) if actions else 'None'}
MODIFIED ATTRIBUTES: {', '.join(modified_attributes) if modified_attributes else 'None'}
READ ATTRIBUTES: {', '.join(read_attributes) if read_attributes else 'None'}
ENTITIES: {', '.join(entities) if entities else 'None'}

FIELD MODIFICATION DETAILS:
"""

                if modified_attributes:
                    enriched_content += "This flow modifies the following fields:\n"
                    for field in modified_attributes:
                        # Find source type for this field
                        source_info = next((st for st in source_types if st.startswith(f"{field}=")), None)
                        if source_info:
                            source_type = source_info.split('=')[1]
                            enriched_content += f"  - {field} (source: {source_type})\n"
                        else:
                            enriched_content += f"  - {field}\n"
                else:
                    enriched_content += "This flow does not modify any fields.\n"

                enriched_content += f"\nTRIGGER: {trigger_type}\n"
                enriched_content += f"ACTIONS COUNT: {len(actions)}\n"

                # Create metadata
                metadata = {
                    'flow_name': flow_name,
                    'flow_id': flow_id,
                    'flow_type': 'Cloud Flow',
                    'trigger_type': trigger_type,
                    'actions': '|'.join(actions),
                    'modified_attributes': '|'.join(modified_attributes),
                    'read_attributes': '|'.join(read_attributes),
                    'has_set_value': has_set_value,
                    'entities': '|'.join(entities),
                    'source_types': '|'.join(source_types)
                }

                doc = Document(text=enriched_content, metadata=metadata, id_=flow_id)
                documents.append(doc)

                print(f"✓ Processed [Cloud Flow]: {flow_name}")
                print(f"  Trigger: {trigger_type}")
                print(f"  Modified fields: {modified_attributes}")

            except Exception as e:
                print(f"✗ Error processing cloud flow entry: {e}")
                continue

        if not documents:
            raise ValueError(
                f"No valid cloud flows found in '{self.cloudflow_file}'. "
                f"The file may be empty or contain invalid data."
            )

        return documents

    def _load_or_create_index(self) -> VectorStoreIndex:
        """
        Load existing index or create new one from preprocessed cloud flow data.

        Creates a vector store index from cloud flow documents using LlamaIndex.
        Uses SentenceSplitter for chunking and Google embeddings for vectorization.

        Returns:
            The created vector store index.

        Raises:
            RuntimeError: If index creation fails.
        """
        try:
            print("Creating new cloud flow index...")
            documents = self._preprocess_cloudflows()

            node_parser = SentenceSplitter(chunk_size=512, chunk_overlap=100)

            index = VectorStoreIndex.from_documents(
                documents,
                embed_model=self.embed_model,
                transformations=[node_parser],
                show_progress=True
            )

            print(f"✓ Cloud flow index created with {len(documents)} flows")
            return index

        except Exception as e:
            raise RuntimeError(
                f"Failed to create cloud flow vector index: {str(e)}. "
                f"This may be due to invalid flow data or Google API issues."
            ) from e

    def query(self, question: str) -> str:
        """
        Query the cloud flows using natural language.

        Args:
            question: Natural language question about cloud flows

        Returns:
            Answer based on the indexed cloud flow data

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

    def find_set_value_flows(self, fieldname: str) -> str:
        """
        Find all cloud flows that SET/modify a specific field.

        Args:
            fieldname: Field name (e.g., "firstname", "emailaddress1")

        Returns:
            LLM-generated response with flow names and IDs
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
            similarity_top_k=5,
            response_mode="compact",
            filters=filters
        )

        response = filtered_engine.query(
            f"List all cloud flows that modify or update the field '{fieldname}'. "
            f"For each flow, provide: Flow Type: Cloud Flow, Name: <flow_name>, ID: <flow_id>. "
            f"If no flows found, return 'No cloud flows found that modify this field'."
        )
        return str(response)

    def find_flows_by_trigger_type(self, fieldname: str, trigger_type: str) -> str:
        """
        Find flows of specific trigger type that modify a field.

        Args:
            fieldname: The field/attribute name to search for
            trigger_type: Trigger type (e.g., "Manual", "Automated", "Scheduled")

        Returns:
            LLM-generated response with flow names and IDs
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
                    key="trigger_type",
                    value=trigger_type,
                    operator=FilterOperator.CONTAINS
                )
            ],
            condition="and"
        )

        filtered_engine = self.index.as_query_engine(
            llm=self.llm,
            similarity_top_k=5,
            response_mode="compact",
            filters=filters
        )

        response = filtered_engine.query(
            f"List all cloud flows with trigger type '{trigger_type}' that modify the field '{fieldname}'. "
            f"Return format: Name: <flow_name>, ID: <flow_id>, Trigger: <trigger_type>"
        )
        return str(response)

    def analyze_field_updates(self) -> str:
        """
        Identify all field updates across all cloud flows.

        Returns:
            LLM-generated response listing all modified attributes with flow details.
        """
        return self.query(
            "What field updates occur in these cloud flows? "
            "List all fields that are modified with flow name, ID, and trigger type."
        )

    def get_flow_by_name(self, name: str) -> str:
        """
        Get details about a specific flow by name.

        Args:
            name: The name of the cloud flow to search for

        Returns:
            LLM-generated response with flow details including ID, trigger type, and actions
        """
        return self.query(
            f"What actions are performed in the cloud flow named '{name}'? "
            f"Include the flow ID, trigger type, modified fields, and all actions."
        )

    def analyze_flow_triggers(self) -> str:
        """
        Analyze trigger types across all cloud flows.

        Returns:
            LLM-generated response describing trigger distribution and patterns
        """
        return self.query(
            "What trigger types are used in these cloud flows? "
            "Provide a summary of manual vs automated vs scheduled flows."
        )

    def analyze_source_types(self) -> str:
        """
        Analyze data source types used in field updates.

        Returns:
            LLM-generated response describing how fields get their values (trigger, variable, static, etc.)
        """
        return self.query(
            "What are the data sources for field updates in these flows? "
            "List whether fields are set from triggers, variables, static values, or other sources."
        )

    def refresh_index(self) -> None:
        """
        Refresh the index by re-preprocessing the cloudflows.txt file.

        Use this method after updating the cloudflow file to rebuild the vector store index
        with the latest data.
        """
        self.index = self._load_or_create_index()
        self.query_engine = self.index.as_query_engine(
            llm=self.llm,
            similarity_top_k=5,
            response_mode="compact"
        )
