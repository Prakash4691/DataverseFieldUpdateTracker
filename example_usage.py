"""
Example usage of the Dataverse Workflow RAG system.
This demonstrates how to use LlamaIndex to analyze workflow XAML files.
"""

from businessrule_rag_cp import root_agent1

# Note: Delete the ./storage folder to force re-indexing with new preprocessing

print("=" * 80)
print("TESTING IMPROVED DATAVERSE WORKFLOW RAG")
print("=" * 80)

# Test 1: Find workflows with SET VALUE actions
print("\n1. Finding workflows with SET VALUE/SET DEFAULT actions:")
print("-" * 80)
result = root_agent1.find_set_value_workflows('cr5b9_att')
print(result)


# Example 3: Refreshing the index after file changes
# custom_rag.refresh_index()
