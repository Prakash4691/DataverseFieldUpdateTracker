from dataverse_operations import DataverseOperations
from file_operations import ImplementationDefinitionFileOperations

dvoperation = DataverseOperations()
#entityname = input('Please provide entity name: ')
#attributename = input('Please provide attribute name: ')
attributeid = dvoperation.get_attibuteid('cr5b9_test1', 'cr5b9_attribmeta')
deplist = dvoperation.get_dependencylist_for_attribute(attributeid)
wflist = dvoperation.retrieve_only_workflowdependency(deplist)

formslist = dvoperation.get_forms_for_entity('cr5b9_test1')
deplistform = dvoperation.get_dependencylist_for_form(formslist)
webreslist = dvoperation.retrieve_webresources_from_dependency(deplistform)

print(webreslist)


#ImplementationDefinitionFileOperations.create_workflow_file(wflist)

#cr5b9_test1
#cr5b9_attribmeta

#'9420519e-88d6-476a-a267-f43d1e96ece9'
#'c84c2825-f607-4ef4-8fe2-f8cb7a2e20d4'