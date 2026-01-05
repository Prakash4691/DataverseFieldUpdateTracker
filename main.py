"""
CLI runner for Dataverse field update tracking with production-grade rate limit monitoring.

Steps performed:
1) Pulls workflows and web resources for a given entity/attribute.
2) Writes metadata to wf.txt and webre.txt.
3) Runs workflow and web resource RAG to find setValue/setDefault usage.
4) Reports rate limit tracking statistics.
"""

import argparse
from dataverse_operations import DataverseOperations
from file_operations import ImplementationDefinitionFileOperations
from workflow_rag import DataverseWorkflowRAG
from webresource_rag import DataverseWebResourceRAG
from rate_limit_tracker import RateLimitTracker


class DataverseFieldUpdateTrackerApp:
	"""Encapsulates the data pull and RAG analysis workflow with rate limit tracking."""

	def __init__(self, dv_ops: DataverseOperations | None = None):
		self.dv_ops = dv_ops or DataverseOperations()
		self.rate_tracker = RateLimitTracker()

	def _generate_metadata_files(self, entityname: str, attributename: str) -> None:
		"""Pull dependencies, then write wf.txt and webre.txt with rate limit tracking."""
		print(f"\n🔍 Retrieving metadata for {entityname}.{attributename}...")
		
		# Get attribute ID with tracking
		attributeid = self.dv_ops.get_attibuteid(
			entityname, 
			attributename, 
			rate_limit_tracker=self.rate_tracker
		)
		print(f"✓ Attribute ID: {attributeid}")
		
		# Get dependencies with tracking
		deplist = self.dv_ops.get_dependencylist_for_attribute(
			attributeid,
			rate_limit_tracker=self.rate_tracker
		)
		print(f"✓ Found {len(deplist.get('value', []))} total dependencies")
		
		# Filter and save workflows
		wflist = self.dv_ops.retrieve_only_workflowdependency(deplist)
		print(f"✓ Found {len(wflist)} workflows/business rules")
		ImplementationDefinitionFileOperations.create_workflow_file(wflist)
		print(f"✓ Saved workflow metadata to wf.txt")
		
		# Get forms with tracking
		formslist = self.dv_ops.get_forms_for_entity(entityname)
		print(f"✓ Found {len(formslist)} forms")
		
		# Get form dependencies and web resources
		deplistform = self.dv_ops.get_dependencylist_for_form(formslist)
		print(f"✓ Found {len(deplistform)} web resource references")
		
		webreslist = self.dv_ops.retrieve_webresources_from_dependency(deplistform)
		print(f"✓ Found {len(webreslist)} JavaScript web resources")
		ImplementationDefinitionFileOperations.create_webresourceflow_file(webreslist)
		print(f"✓ Saved web resource metadata to webre.txt")

	def _run_rag_analysis(self, attributename: str) -> None:
		"""Instantiate RAG agents and print findings for the attribute."""
		workflow_agent = DataverseWorkflowRAG()
		webresource_agent = DataverseWebResourceRAG()

		print("\n" + "=" * 80)
		print("DATAVERSE FIELD UPDATE ANALYSIS")
		print("=" * 80)

		print("\n1. Workflows & Business Rules that SET/modify this field:")
		print("-" * 80)
		wf_result = workflow_agent.find_set_value_workflows(attributename)
		print(wf_result)
		print("=" * 80)

		print("\n2. Web Resources (JavaScript) that use setValue() on this field:")
		print("-" * 80)
		webres_result = webresource_agent.find_setvalue_webresources(attributename)
		print(webres_result)

	def run(self, entityname: str, attributename: str) -> None:
		"""Full pipeline: fetch data, generate files, analyze, and show rate limit stats."""
		try:
			self._generate_metadata_files(entityname, attributename)
			self._run_rag_analysis(attributename)
		finally:
			# Always print rate limit summary, even if there was an error
			self.rate_tracker.print_summary()


def _parse_args() -> argparse.Namespace:
	parser = argparse.ArgumentParser(
		description="Dataverse field update tracker with rate limit monitoring"
	)
	parser.add_argument(
		"--entity", 
		dest="entityname", 
		help="Logical entity name (e.g., account)"
	)
	parser.add_argument(
		"--attribute", 
		dest="attributename", 
		help="Logical attribute/field name"
	)
	return parser.parse_args()


def main() -> None:
	args = _parse_args()
	entity = args.entityname or input("Please provide entity name: ").strip()
	attribute = args.attributename or input("Please provide attribute name: ").strip()

	app = DataverseFieldUpdateTrackerApp()
	try:
		app.run(entity, attribute)
	except KeyboardInterrupt:
		print("\n\n⚠️  Operation cancelled by user")
		app.rate_tracker.print_summary()
	except Exception as exc:
		print(f"\n❌ Error: {exc}")
		app.rate_tracker.print_summary()


if __name__ == "__main__":
	main()