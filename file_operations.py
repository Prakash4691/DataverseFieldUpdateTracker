from dataverse_operations import *

class ImplementationDefinitionFileOperations:

    @staticmethod 
    def create_businessrule_file(workflowlist, filename:str):
        metadatalist=[]
        for wf in workflowlist:
            brmetadata = {k:v for k,v in wf.items() if '@' not in k}
            metadatalist.append(f'{brmetadata}\n')

        with open(filename, 'w') as file:
            file.writelines(metadatalist)