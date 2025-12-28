from dataverse_operations import *

class ImplementationDefinitionFileOperations:

    @staticmethod 
    def create_workflow_file(workflowlist):
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