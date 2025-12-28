from dataverse_operations import *

class ImplementationDefinitionFileOperations:

    @staticmethod 
    def create_workflow_file(workflowlist):
        metadatalist=[]
        for wf in workflowlist:
            brmetadata = {k:v for k,v in wf.items() if '@' not in k}
            metadatalist.append(f'{brmetadata}\n')

        with open('wf.txt', 'w') as file:
            file.writelines(metadatalist)

    @staticmethod
    def create_webresourceflow_file(webresourcelist):
        metadatalist=[]
        for wr in webresourcelist:
            wrmetadata = {k:v for k,v in wr.items() if '@' not in k}
            metadatalist.append(f'{wrmetadata}\n')

        with open('webre.txt', 'w') as file:
            file.writelines(metadatalist)