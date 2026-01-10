from dataverse_operations import *

class ImplementationDefinitionFileOperations:
    """
    File operations for exporting Dataverse workflow and web resource metadata to text files.
    
    This class provides static methods to write workflow and web resource metadata
    to text files for further analysis by RAG systems.
    """

    @staticmethod 
    def create_workflow_file(workflowlist):
        """
        Write workflow metadata to a text file.
        
        Filters out OData metadata keys (keys containing '@') and writes each workflow
        as a dictionary string on a new line in 'wf.txt'.
        
        Args:
            workflowlist (list): List of workflow metadata dictionaries containing keys like
                'name', 'workflowid', 'category', 'xaml', 'statecode', etc.
        
        Returns:
            None
        
        Raises:
            TypeError: If workflowlist is not a list.
            IOError: If file write fails.
        
        Side Effects:
            Creates/overwrites 'wf.txt' in the current directory.
        """
        try:
            if not workflowlist:
                print("Warning: No workflows to write to file")
                return
            
            if not isinstance(workflowlist, list):
                raise TypeError(f"workflowlist must be a list, got {type(workflowlist).__name__}")
            
            metadatalist=[]
            for wf in workflowlist:
                if not isinstance(wf, dict):
                    print(f"Warning: Skipping invalid workflow entry (not a dict): {type(wf).__name__}")
                    continue
                
                brmetadata = {k:v for k,v in wf.items() if '@' not in k}
                metadatalist.append(f'{brmetadata}\n')

            with open('wf.txt', 'w', encoding='utf-8') as file:
                file.writelines(metadatalist)
                
            print(f"Successfully wrote {len(metadatalist)} workflow(s) to wf.txt")
                
        except IOError as e:
            raise IOError(f"Failed to write workflow file: {str(e)}") from e
        except Exception as e:
            raise Exception(f"Unexpected error while creating workflow file: {str(e)}") from e

    @staticmethod
    def create_webresourceflow_file(webresourcelist):
        """
        Write web resource metadata to a text file.
        
        Filters out OData metadata keys (keys containing '@') and writes each web resource
        as a dictionary string on a new line in 'webre.txt'.
        
        Args:
            webresourcelist (list): List of web resource metadata dictionaries containing keys like
                'name', 'id', 'decoded_content', etc.
        
        Returns:
            None
        
        Raises:
            TypeError: If webresourcelist is not a list.
            IOError: If file write fails.
        
        Side Effects:
            Creates/overwrites 'webre.txt' in the current directory.
        """
        try:
            if not webresourcelist:
                print("Warning: No web resources to write to file")
                return
            
            if not isinstance(webresourcelist, list):
                raise TypeError(f"webresourcelist must be a list, got {type(webresourcelist).__name__}")
            
            metadatalist=[]
            for wr in webresourcelist:
                if not isinstance(wr, dict):
                    print(f"Warning: Skipping invalid web resource entry (not a dict): {type(wr).__name__}")
                    continue
                
                wrmetadata = {k:v for k,v in wr.items() if '@' not in k}
                metadatalist.append(f'{wrmetadata}\n')

            with open('webre.txt', 'w', encoding='utf-8') as file:
                file.writelines(metadatalist)
                
            print(f"Successfully wrote {len(metadatalist)} web resource(s) to webre.txt")

        except IOError as e:
            raise IOError(f"Failed to write web resource file: {str(e)}") from e
        except Exception as e:
            raise Exception(f"Unexpected error while creating web resource file: {str(e)}") from e

    @staticmethod
    def create_cloudflow_file(cloudflows):
        """
        Write cloud flow metadata to a text file in structured format.

        Creates cloudflows.txt with structured format matching wf.txt pattern.
        Each flow includes flow name, ID, type, trigger, actions, modified fields,
        read fields, source types, and entities.

        Args:
            cloudflows (list): List of cloud flow metadata dictionaries from CloudFlowMetadataExtractor.
                Each dict should contain keys: flow_id, flow_name, flow_type, trigger_type,
                actions, modified_fields, read_fields, entities, and optionally parse_error.

        Returns:
            None

        Raises:
            TypeError: If cloudflows is not a list.
            IOError: If file write fails.

        Side Effects:
            Creates/overwrites 'cloudflows.txt' in the current directory.

        Format:
            flow_name: [name]
            flow_id: [guid]
            flow_type: Cloud Flow
            trigger_type: [trigger type]
            actions: ACTION1 | ACTION2 | ACTION3
            modified_attributes: field1 | field2 | field3
            read_attributes: field4 | field5
            source_types: field1=trigger | field2=variable | field3=static
            has_set_value: True/False
            entities: entity1 | entity2
            ---
        """
        try:
            if not cloudflows:
                print("Warning: No cloud flows to write to file")
                # Create empty file
                with open('cloudflows.txt', 'w', encoding='utf-8') as f:
                    f.write("")
                return

            if not isinstance(cloudflows, list):
                raise TypeError(f"cloudflows must be a list, got {type(cloudflows).__name__}")

            with open('cloudflows.txt', 'w', encoding='utf-8') as f:
                flows_written = 0

                for flow in cloudflows:
                    if not isinstance(flow, dict):
                        print(f"Warning: Skipping invalid cloud flow entry (not a dict): {type(flow).__name__}")
                        continue

                    # Check if parsing failed
                    if flow.get('parse_error'):
                        # Write error entry
                        f.write(f"flow_name: {flow.get('flow_name', 'Unknown')}\n")
                        f.write(f"flow_id: {flow.get('flow_id', 'Unknown')}\n")
                        f.write(f"parse_error: {flow['parse_error']}\n")
                        f.write("---\n\n")
                        flows_written += 1
                        continue

                    # Write successful parse
                    f.write(f"flow_name: {flow.get('flow_name', 'Unknown')}\n")
                    f.write(f"flow_id: {flow.get('flow_id', 'Unknown')}\n")
                    f.write(f"flow_type: {flow.get('flow_type', 'Cloud Flow')}\n")
                    f.write(f"trigger_type: {flow.get('trigger_type', 'Unknown')}\n")

                    # Actions
                    actions = flow.get('actions', [])
                    actions_str = ' | '.join(actions) if actions else ''
                    f.write(f"actions: {actions_str}\n")

                    # Modified fields and source types
                    modified_fields_dict = flow.get('modified_fields', {})
                    modified = []
                    source_types = []

                    for field_name, field_actions in modified_fields_dict.items():
                        modified.append(field_name)

                        # Get primary source type (most common)
                        if field_actions:
                            sources = [action.get('source_type', 'unknown') for action in field_actions]
                            # Find most common source type
                            primary = max(set(sources), key=sources.count) if sources else 'unknown'
                            source_types.append(f"{field_name}={primary}")

                    modified_str = ' | '.join(modified) if modified else ''
                    f.write(f"modified_attributes: {modified_str}\n")

                    # Read fields
                    read_fields = flow.get('read_fields', set())
                    read_str = ' | '.join(sorted(read_fields)) if read_fields else ''
                    f.write(f"read_attributes: {read_str}\n")

                    # Source types
                    source_types_str = ' | '.join(source_types) if source_types else ''
                    f.write(f"source_types: {source_types_str}\n")

                    # Has set value
                    has_set_value = len(modified) > 0
                    f.write(f"has_set_value: {has_set_value}\n")

                    # Entities
                    entities = flow.get('entities', set())
                    entities_str = ' | '.join(sorted(entities)) if entities else ''
                    f.write(f"entities: {entities_str}\n")

                    f.write("---\n\n")
                    flows_written += 1

            print(f"Successfully wrote {flows_written} cloud flow(s) to cloudflows.txt")

        except IOError as e:
            raise IOError(f"Failed to write cloud flow file: {str(e)}") from e
        except Exception as e:
            raise Exception(f"Unexpected error while creating cloud flow file: {str(e)}") from e