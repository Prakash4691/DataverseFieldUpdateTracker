from dataverse_operations import DataverseOperations
from file_operations import ImplementationDefinitionFileOperations

dvoperation = DataverseOperations()
#entityname = input('Please provide entity name: ')
#attributename = input('Please provide attribute name: ')
attributeid = dvoperation.get_attibuteid('cr5b9_test1', 'cr5b9_attribmeta')
deplist = dvoperation.get_dependencylist_for_attribute(attributeid)
wflist = dvoperation.retrieve_only_workflowdependency(deplist)

ImplementationDefinitionFileOperations.create_workflow_file(wflist)

#cr5b9_test1
#cr5b9_attribmeta