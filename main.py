"""
CLI runner for Dataverse field update tracking.

Steps performed:
1) Pulls workflows and web resources for a given entity/attribute.
2) Writes metadata to wf.txt and webre.txt.
3) Runs workflow and web resource RAG to find setValue/setDefault usage.
"""

import argparse
from dataverse_operations import DataverseOperations
from file_operations import ImplementationDefinitionFileOperations
from workflow_rag import DataverseWorkflowRAG
from webresource_rag import DataverseWebResourceRAG


class DataverseFieldUpdateTrackerApp:
	"""Encapsulates the data pull and RAG analysis workflow."""

	def __init__(self, dv_ops: DataverseOperations | None = None):
		self.dv_ops = dv_ops or DataverseOperations()

	def _generate_metadata_files(self, entityname: str, attributename: str) -> None:
		"""Pull dependencies, then write wf.txt and webre.txt."""
		attributeid = self.dv_ops.get_attibuteid(entityname, attributename)

		deplist = self.dv_ops.get_dependencylist_for_attribute(attributeid)
		wflist = self.dv_ops.retrieve_only_workflowdependency(deplist)
		ImplementationDefinitionFileOperations.create_workflow_file(wflist)

		formslist = self.dv_ops.get_forms_for_entity(entityname)
		deplistform = self.dv_ops.get_dependencylist_for_form(formslist)
		webreslist = self.dv_ops.retrieve_webresources_from_dependency(deplistform)
		ImplementationDefinitionFileOperations.create_webresourceflow_file(webreslist)

	def _run_rag_analysis(self, attributename: str) -> None:
		"""Instantiate RAG agents and print findings for the attribute."""
		workflow_agent = DataverseWorkflowRAG()
		webresource_agent = DataverseWebResourceRAG()

		print("=" * 80)
		print("IMPROVED DATAVERSE WORKFLOW RAG")
		print("=" * 80)

		print("\n1. Finding workflows with SET VALUE/SET DEFAULT actions:")
		print("-" * 80)
		wf_result = workflow_agent.find_set_value_workflows(attributename)
		print(wf_result)
		print("=" * 80)

		print("\n\n2. Finding web resources with SET VALUE actions:")
		print("-" * 80)
		webres_result = webresource_agent.find_setvalue_webresources(attributename)
		print(webres_result)

	def run(self, entityname: str, attributename: str) -> None:
		"""Full pipeline: fetch data, generate files, and analyze."""
		self._generate_metadata_files(entityname, attributename)
		self._run_rag_analysis(attributename)


def _parse_args() -> argparse.Namespace:
	parser = argparse.ArgumentParser(description="Dataverse field update tracker")
	parser.add_argument("--entity", dest="entityname", help="Logical entity name (e.g., account)")
	parser.add_argument("--attribute", dest="attributename", help="Logical attribute/field name")
	return parser.parse_args()


def main() -> None:
	args = _parse_args()
	entity = args.entityname or input("Please provide entity name: ").strip()
	attribute = args.attributename or input("Please provide attribute name: ").strip()

	app = DataverseFieldUpdateTrackerApp()
	try:
		app.run(entity, attribute)
	except Exception as exc:
		print(f"Error: {exc}")


if __name__ == "__main__":
	main()