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