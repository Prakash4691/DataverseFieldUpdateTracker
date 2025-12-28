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
        
        Side Effects:
            Creates/overwrites 'wf.txt' in the current directory.
        """
        metadatalist=[]
        for wf in workflowlist:
            brmetadata = {k:v for k,v in wf.items() if '@' not in k}
            metadatalist.append(f'{brmetadata}\n')

        with open('wf.txt', 'w') as file:
            file.writelines(metadatalist)

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
        
        Side Effects:
            Creates/overwrites 'webre.txt' in the current directory.
        """
        metadatalist=[]
        for wr in webresourcelist:
            wrmetadata = {k:v for k,v in wr.items() if '@' not in k}
            metadatalist.append(f'{wrmetadata}\n')

        with open('webre.txt', 'w') as file:
            file.writelines(metadatalist)