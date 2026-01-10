"""
Bash-based exact search for Dataverse metadata files.

Uses subprocess to execute grep commands for fast, deterministic pattern matching.
"""

import subprocess
import re
from typing import Optional


class BashSearch:
    """
    Bash-based search for metadata files using grep.

    Provides fast, exact pattern matching without LLM costs.
    Use for field name lookups; use RAG for semantic queries.
    """

    def __init__(
        self,
        cloudflow_file: str = "./cloudflows.txt",
        webresource_file: str = "./webre.txt",
        workflow_file: str = "./wf.txt"
    ):
        """
        Initialize BashSearch with file paths.

        Args:
            cloudflow_file: Path to cloudflows.txt
            webresource_file: Path to webre.txt
            workflow_file: Path to wf.txt
        """
        self.cloudflow_file = cloudflow_file
        self.webresource_file = webresource_file
        self.workflow_file = workflow_file

    def search_cloudflows(self, fieldname: str) -> list[dict]:
        """
        Find cloud flows that modify a specific field.

        Uses grep to search modified_attributes in cloudflows.txt.

        Args:
            fieldname: The field name to search for (e.g., "firstname")

        Returns:
            List of dicts with flow_name, flow_id, trigger_type, modified_attributes
        """
        # Grep pattern: find lines with modified_attributes containing fieldname
        # Then get context (previous lines) to capture full flow block
        pattern = f"modified_attributes:.*{re.escape(fieldname)}"

        # Get 10 lines before match to capture flow_name, flow_id, etc.
        output = self._run_grep(pattern, self.cloudflow_file, before_context=10)

        if not output:
            return []

        return self._parse_cloudflow_blocks(output, fieldname)

    def search_webresources(self, fieldname: str) -> list[dict]:
        """
        Find web resources that use setValue on a specific field.

        Searches for JavaScript patterns like:
        - formContext.getAttribute("fieldname").setValue()
        - Xrm.Page.getAttribute("fieldname").setValue()

        Args:
            fieldname: The field name to search for

        Returns:
            List of dicts with name and matching code snippet
        """
        # Pattern for setValue calls with the field name
        patterns = [
            f"getAttribute.*{re.escape(fieldname)}.*setValue",
            f"getControl.*{re.escape(fieldname)}.*setValue",
            f"setValue.*{re.escape(fieldname)}"
        ]

        results = []
        for pattern in patterns:
            output = self._run_grep(pattern, self.webresource_file, ignore_case=True)
            if output:
                results.extend(self._parse_webresource_lines(output))

        # Deduplicate by name
        seen = set()
        unique_results = []
        for r in results:
            if r.get('name') not in seen:
                seen.add(r.get('name'))
                unique_results.append(r)

        return unique_results

    def search_workflows(self, fieldname: str) -> list[dict]:
        """
        Find workflows/business rules that SET_VALUE on a specific field.

        Searches XAML content for SetEntityProperty and SetAttributeValue elements.

        Args:
            fieldname: The field name to search for

        Returns:
            List of dicts with workflow name and category
        """
        # Pattern matches SetEntityProperty or SetAttributeValue with the field in Attribute attribute
        # This captures both classic workflow SetEntityProperty and business rule SetAttributeValue
        pattern = f'Set(?:Entity|Attribute).*Attribute="{re.escape(fieldname)}"'

        output = self._run_grep(pattern, self.workflow_file, ignore_case=True)

        if not output:
            return []

        return self._parse_workflow_lines(output)

    def _run_grep(
        self,
        pattern: str,
        file_path: str,
        before_context: int = 0,
        after_context: int = 0,
        ignore_case: bool = False
    ) -> Optional[str]:
        """
        Execute grep command and return output.

        Args:
            pattern: Regex pattern to search
            file_path: File to search in
            before_context: Lines before match (-B)
            after_context: Lines after match (-A)
            ignore_case: Case insensitive search (-i)

        Returns:
            Grep output as string, or None if no matches
        """
        cmd = ["grep", "-E"]

        if ignore_case:
            cmd.append("-i")
        if before_context > 0:
            cmd.extend(["-B", str(before_context)])
        if after_context > 0:
            cmd.extend(["-A", str(after_context)])

        cmd.extend([pattern, file_path])

        try:
            result = subprocess.run(
                cmd,
                capture_output=True,
                text=True,
                timeout=30
            )

            if result.returncode == 0:
                return result.stdout
            return None

        except subprocess.TimeoutExpired:
            print(f"Warning: grep timed out searching {file_path}")
            return None
        except FileNotFoundError:
            print(f"Warning: grep not found, ensure it's installed")
            return None

    def _parse_cloudflow_blocks(self, output: str, fieldname: str) -> list[dict]:
        """
        Parse grep output into cloud flow dictionaries.

        Args:
            output: Raw grep output with context lines
            fieldname: The field being searched (for filtering)

        Returns:
            List of flow dicts
        """
        results = []

        # Split by grep's block separator (--)
        blocks = output.split("--")

        for block in blocks:
            if not block.strip():
                continue

            flow = {}
            for line in block.strip().split("\n"):
                if ":" in line:
                    # Handle grep line number prefix if present
                    line = re.sub(r"^\d+-", "", line)
                    line = re.sub(r"^\d+:", "", line)

                    if ":" in line:
                        key, value = line.split(":", 1)
                        flow[key.strip()] = value.strip()

            # Only include if it has the field in modified_attributes
            if flow.get("modified_attributes") and fieldname.lower() in flow["modified_attributes"].lower():
                results.append(flow)

        return results

    def _parse_webresource_lines(self, output: str) -> list[dict]:
        """
        Parse grep output from webre.txt (dict strings per line).

        Args:
            output: Raw grep output

        Returns:
            List of web resource dicts
        """
        results = []

        for line in output.strip().split("\n"):
            if not line.strip():
                continue

            try:
                # webre.txt contains Python dict strings
                # Extract name from the dict string
                name_match = re.search(r"'name':\s*'([^']+)'", line)
                if name_match:
                    results.append({
                        "name": name_match.group(1),
                        "raw_line": line[:200] + "..." if len(line) > 200 else line
                    })
            except Exception:
                continue

        return results

    def _parse_workflow_lines(self, output: str) -> list[dict]:
        """
        Parse grep output from wf.txt (dict strings per line).

        Args:
            output: Raw grep output

        Returns:
            List of workflow dicts
        """
        results = []

        for line in output.strip().split("\n"):
            if not line.strip():
                continue

            try:
                # Extract name and category from dict string
                name_match = re.search(r"'name':\s*'([^']+)'", line)
                category_match = re.search(r"'category':\s*(\d+)", line)
                workflowid_match = re.search(r"'workflowid':\s*'([^']+)'", line)

                if name_match:
                    workflow = {"name": name_match.group(1)}

                    if category_match:
                        cat = int(category_match.group(1))
                        workflow["category"] = cat
                        workflow["type"] = "Business Rule" if cat == 2 else "Classic Workflow"

                    if workflowid_match:
                        workflow["workflowid"] = workflowid_match.group(1)

                    results.append(workflow)
            except Exception:
                continue

        return results

    def format_cloudflow_results(self, flows: list[dict]) -> str:
        """
        Format cloud flow search results for display.

        Args:
            flows: List of flow dicts from search_cloudflows()

        Returns:
            Formatted string for display
        """
        if not flows:
            return "No cloud flows found modifying this field."

        lines = [f"Found {len(flows)} cloud flow(s) modifying this field:\n"]

        for flow in flows:
            lines.append(f"Flow Type: Cloud Flow")
            lines.append(f"Name: {flow.get('flow_name', 'Unknown')}")
            lines.append(f"ID: {flow.get('flow_id', 'Unknown')}")
            lines.append(f"Trigger: {flow.get('trigger_type', 'Unknown')}")
            lines.append(f"Modified Fields: {flow.get('modified_attributes', '')}")
            lines.append("")

        return "\n".join(lines)

    def format_webresource_results(self, resources: list[dict]) -> str:
        """
        Format web resource search results for display.

        Args:
            resources: List of resource dicts from search_webresources()

        Returns:
            Formatted string for display
        """
        if not resources:
            return "No web resources found using setValue on this field."

        lines = [f"Found {len(resources)} web resource(s) using setValue on this field:\n"]

        for wr in resources:
            lines.append(f"Name: {wr.get('name', 'Unknown')}")
            lines.append("")

        return "\n".join(lines)

    def format_workflow_results(self, workflows: list[dict]) -> str:
        """
        Format workflow search results for display.

        Args:
            workflows: List of workflow dicts from search_workflows()

        Returns:
            Formatted string for display
        """
        if not workflows:
            return "No workflows/business rules found modifying this field."

        lines = [f"Found {len(workflows)} workflow(s)/business rule(s) modifying this field:\n"]

        for wf in workflows:
            lines.append(f"Type: {wf.get('type', 'Unknown')}")
            lines.append(f"Name: {wf.get('name', 'Unknown')}")
            if wf.get('workflowid'):
                lines.append(f"ID: {wf['workflowid']}")
            lines.append("")

        return "\n".join(lines)
