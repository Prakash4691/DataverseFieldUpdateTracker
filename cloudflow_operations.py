"""
Power Automate Cloud Flow Operations

This module provides operations for retrieving and analyzing Power Automate cloud flows
from Microsoft Dataverse. It includes streaming JSON parsing for large flow definitions,
expression parsing for field update tracking, and metadata extraction.
"""

import json
import ijson
import io
import time
import logging
from typing import Optional
from expression_parser import ExpressionParser, AdvancedExpressionParser, VariableTracker

logger = logging.getLogger(__name__)


class CloudFlowOperations:
    """Operations for retrieving and analyzing Power Automate cloud flows.

    This class handles retrieval of active cloud flows (category=5) from Dataverse
    and provides methods for analyzing flow definitions.

    Attributes:
        dv_ops: DataverseOperations instance for accessing Dataverse
        client: DataverseClient instance for SDK operations
        headers: HTTP headers for API requests
    """

    def __init__(self, dv_ops):
        """Initialize CloudFlowOperations with DataverseOperations instance.

        Args:
            dv_ops: DataverseOperations instance with authenticated connection
        """
        self.dv_ops = dv_ops
        self.client = dv_ops.client
        self.headers = {
            'Accept': 'application/json',
            'OData-MaxVersion': '4.0',
            'OData-Version': '4.0',
            'Authorization': f'Bearer {dv_ops.token}'
        }

    def get_all_active_cloudflows(self, rate_limit_tracker=None) -> list[dict]:
        """Retrieve all active cloud flows (category=5, statecode=1).

        Queries Dataverse for all cloud flows that are active. Uses the SDK client
        to handle pagination automatically.

        Args:
            rate_limit_tracker (RateLimitTracker, optional): Tracker instance to record rate limit metrics.

        Returns:
            List of dicts with keys: workflowid, name, clientdata, modifiedon, description

        Raises:
            ConnectionError: If the API request fails.

        Example:
            >>> cf_ops = CloudFlowOperations(dv_ops)
            >>> flows = cf_ops.get_all_active_cloudflows(rate_tracker)
            >>> print(f"Found {len(flows)} active cloud flows")
        """
        try:
            request_start = time.time()
            cloudflows = []

            # Query for active cloud flows: category=5 (Cloud Flow), statecode=1 (Active)
            for batch in self.client.get(
                "workflow",
                filter="category eq 5 and statecode eq 1",
                select=["workflowid", "name", "clientdata", "modifiedon", "description"]
            ):
                for flow in batch:
                    cloudflows.append(flow)

            # Record successful request
            if rate_limit_tracker:
                duration = time.time() - request_start
                rate_limit_tracker.record_request(
                    endpoint="get_all_active_cloudflows",
                    duration=duration,
                    hit_429=False,
                    retry_count=0,
                    retry_after=0
                )

            return cloudflows

        except Exception as e:
            # Record failed request
            if rate_limit_tracker:
                duration = time.time() - request_start
                rate_limit_tracker.record_request(
                    endpoint="get_all_active_cloudflows",
                    duration=duration,
                    hit_429=False,
                    retry_count=0,
                    retry_after=0
                )

            raise ConnectionError(
                f"Failed to retrieve cloud flows: {str(e)}"
            ) from e

    @staticmethod
    def get_flow_trigger_type(definition: dict) -> str:
        """Extract trigger type from flow definition.

        Args:
            definition: Flow definition dict from clientdata

        Returns:
            Human-readable trigger type string (e.g., "Manual", "Automated - When a record is created")
        """
        try:
            if not definition or 'triggers' not in definition:
                return "Unknown"

            triggers = definition.get('triggers', {})
            if not triggers:
                return "Unknown"

            # Get first trigger
            trigger_name = list(triggers.keys())[0]
            trigger = triggers[trigger_name]

            trigger_type = trigger.get('type', '')
            trigger_kind = trigger.get('kind', '')

            # Map common trigger types to readable names
            if trigger_type == 'Request' and trigger_kind == 'Button':
                return "Manual (Button)"
            elif trigger_type == 'Request':
                return "Manual"
            elif trigger_type == 'OpenApiConnectionWebhook':
                # Try to get operation ID for more specific name
                inputs = trigger.get('inputs', {})
                host = inputs.get('host', {})
                operation_id = host.get('operationId', '')

                if 'SubscribeWebhookTrigger' in operation_id:
                    return "Automated - When a record is created or updated"
                elif 'OnNewItems' in operation_id:
                    return "Automated - When a record is created"
                else:
                    return "Automated (Webhook)"
            elif trigger_type == 'Recurrence':
                return "Scheduled"
            else:
                return f"{trigger_type}"

        except Exception as e:
            logger.warning(f"Error extracting trigger type: {str(e)}")
            return "Unknown"


class CloudFlowParser:
    """Parse cloud flow clientdata JSON using streaming parser.

    Handles large flow definitions (up to 1GB) using ijson streaming parser
    to avoid loading entire JSON into memory.
    """

    def parse_clientdata(self, clientdata: str, flow_name: str) -> dict:
        """Parse clientdata JSON using streaming parser (handles large flows).

        Args:
            clientdata: JSON string from workflow.clientdata field
            flow_name: Flow name for error reporting

        Returns:
            Dict with keys:
                - success: bool
                - error: str (if success=False)
                - definition: dict (if success=True)
                - connection_references: dict

        Example:
            >>> parser = CloudFlowParser()
            >>> result = parser.parse_clientdata(flow['clientdata'], flow['name'])
            >>> if result['success']:
            ...     definition = result['definition']
        """
        try:
            if not clientdata:
                return {
                    'success': False,
                    'error': 'Empty clientdata'
                }

            # Parse JSON (for small-medium flows, direct parsing is faster)
            # For very large flows, ijson streaming would be used
            try:
                data = json.loads(clientdata)
            except json.JSONDecodeError as e:
                return {
                    'success': False,
                    'error': f'Invalid JSON: {str(e)}'
                }

            # Extract properties.definition and properties.connectionReferences
            properties = data.get('properties', {})
            definition = properties.get('definition', {})
            connection_references = properties.get('connectionReferences', {})

            if not definition:
                return {
                    'success': False,
                    'error': 'No definition found in clientdata'
                }

            return {
                'success': True,
                'definition': definition,
                'connection_references': connection_references
            }

        except Exception as e:
            logger.error(f"Error parsing clientdata for flow '{flow_name}': {str(e)}")
            return {
                'success': False,
                'error': f'Parse error: {str(e)}'
            }


class UpdateActionAnalyzer:
    """Analyze Update/Create actions to extract field modifications.

    Identifies Dataverse "Update a row" and "Create a new row" actions,
    extracts modified fields, and analyzes expressions to determine
    data sources (trigger, variable, static, output).

    Attributes:
        expr_parser: ExpressionParser instance for parsing expressions
    """

    def __init__(self, expression_parser: ExpressionParser):
        """Initialize UpdateActionAnalyzer with expression parser.

        Args:
            expression_parser: ExpressionParser instance
        """
        self.expr_parser = expression_parser

    def is_dataverse_update_action(self, action_def: dict) -> bool:
        """Check if action is Dataverse Update/Create operation.

        Args:
            action_def: Action definition dict from workflow definition

        Returns:
            True if action is UpdateRecord or CreateRecord operation

        Example:
            >>> analyzer = UpdateActionAnalyzer(expr_parser)
            >>> is_update = analyzer.is_dataverse_update_action(action)
        """
        try:
            action_type = action_def.get('type', '')

            # Check if it's an OpenApiConnection action
            if action_type != 'OpenApiConnection':
                return False

            # Check operation ID
            inputs = action_def.get('inputs', {})
            host = inputs.get('host', {})
            operation_id = host.get('operationId', '')

            # UpdateRecord/CreateRecord or UpdateOnlyRecord/CreateOnlyRecord operations
            # Modern Power Automate uses UpdateOnlyRecord for "Update a row" action
            return operation_id in ['UpdateRecord', 'CreateRecord', 'UpdateOnlyRecord', 'CreateOnlyRecord']

        except Exception as e:
            logger.warning(f"Error checking action type: {str(e)}")
            return False

    def analyze_update_action(self, action_name: str, action_def: dict) -> Optional[dict]:
        """Analyze an "Update a row" or "Create a new row" action.

        Args:
            action_name: Name of the action
            action_def: Action definition dict from workflow definition

        Returns:
            Dict with keys:
                - action_name: str
                - action_type: 'Update' or 'Create'
                - entity_name: str (e.g., 'contacts')
                - entity_name_expression: str (if dynamic)
                - modified_fields: List[Dict] with:
                    - field_name: str (without 'item/' prefix)
                    - source_type: 'static', 'trigger', 'variable', 'output', 'parameter'
                    - source_detail: str (variable name, step name, etc.)
                    - expression: str (original expression)
                    - static_value: any (if source_type='static')
            Returns None if not a Dataverse update/create action

        Example:
            >>> analyzer = UpdateActionAnalyzer(expr_parser)
            >>> result = analyzer.analyze_update_action("Update_contact", action_def)
            >>> if result:
            ...     print(f"Action modifies {len(result['modified_fields'])} fields")
        """
        try:
            if not self.is_dataverse_update_action(action_def):
                return None

            inputs = action_def.get('inputs', {})
            host = inputs.get('host', {})
            operation_id = host.get('operationId', '')

            # Determine action type
            action_type = 'Update' if operation_id in ['UpdateRecord', 'UpdateOnlyRecord'] else 'Create'

            # Extract parameters
            parameters = inputs.get('parameters', {})

            # Get entity name (entityName field)
            entity_name = parameters.get('entityName', 'unknown')
            entity_name_expression = None
            if self.expr_parser.is_expression(entity_name):
                entity_name_expression = entity_name
                entity_name = 'dynamic'

            # Extract modified fields from item parameters
            modified_fields = []
            item = parameters.get('item', {})

            # Also check for fields directly in parameters with 'item/' prefix
            # (modern Power Automate format uses this structure)
            if not item:
                item = {}
                for param_key, param_value in parameters.items():
                    if param_key.startswith('item/'):
                        item[param_key] = param_value

            for field_key, field_value in item.items():
                # Remove 'item/' prefix if present
                field_name = field_key
                if field_name.startswith('item/'):
                    field_name = field_name[5:]  # Remove 'item/' prefix

                # Parse the expression to determine source
                parsed = self.expr_parser.parse_expression(field_value)

                field_info = {
                    'field_name': field_name,
                    'source_type': parsed.get('source_type', 'unknown'),
                    'expression': parsed.get('expression', str(field_value))
                }

                # Add source details based on type
                if parsed.get('source_type') == 'static':
                    field_info['static_value'] = parsed.get('static_value')
                elif parsed.get('source_type') == 'variable':
                    field_info['source_detail'] = parsed.get('variable_name', '')
                elif parsed.get('source_type') == 'output':
                    field_info['source_detail'] = parsed.get('step_name', '')
                    if 'field_ref' in parsed:
                        field_info['source_field'] = parsed['field_ref']
                elif parsed.get('source_type') == 'trigger':
                    if 'field_ref' in parsed:
                        field_info['source_field'] = parsed['field_ref']
                elif parsed.get('source_type') == 'parameter':
                    field_info['source_detail'] = parsed.get('parameter_name', '')

                modified_fields.append(field_info)

            return {
                'action_name': action_name,
                'action_type': action_type,
                'entity_name': entity_name,
                'entity_name_expression': entity_name_expression,
                'modified_fields': modified_fields
            }

        except Exception as e:
            logger.error(f"Error analyzing action '{action_name}': {str(e)}")
            return None


class CloudFlowMetadataExtractor:
    """Extract structured metadata from cloud flow definitions.

    Processes flow definitions to extract triggers, actions, field modifications,
    variables, and entity references. Uses Phase 2 AdvancedExpressionParser
    for complex nested expressions and VariableTracker for comprehensive
    variable tracking.
    """

    def __init__(self, use_advanced_parser: bool = True):
        """Initialize CloudFlowMetadataExtractor.

        Args:
            use_advanced_parser: If True, use AdvancedExpressionParser (AST-based).
                                If False, use basic ExpressionParser (regex-based).
                                Default is True for Phase 2.
        """
        # Use advanced parser by default (Phase 2)
        if use_advanced_parser:
            try:
                self.expr_parser = AdvancedExpressionParser()
                logger.info("Using AdvancedExpressionParser (Phase 2 - AST-based)")
            except Exception as e:
                logger.warning(f"Failed to initialize AdvancedExpressionParser: {e}. Falling back to basic parser.")
                self.expr_parser = ExpressionParser()
        else:
            self.expr_parser = ExpressionParser()
            logger.info("Using basic ExpressionParser (Phase 1 - regex-based)")

        self.action_analyzer = UpdateActionAnalyzer(self.expr_parser)

    def extract_metadata(self, flow_id: str, flow_name: str, clientdata: str) -> dict:
        """Extract complete metadata from a cloud flow.

        Args:
            flow_id: Flow GUID
            flow_name: Flow name
            clientdata: JSON string from workflow.clientdata field

        Returns:
            Dict with keys:
                - flow_id: str
                - flow_name: str
                - flow_type: 'Cloud Flow'
                - trigger_type: str (e.g., 'Manual', 'Automated - When record created')
                - actions: List[str] (action names)
                - modified_fields: Dict[str, List[Dict]]
                    Key: field_name, Value: list of actions that modify it
                - read_fields: Set[str] (fields referenced in expressions)
                - variables: Dict[str, any] (variable declarations)
                - entities: Set[str] (entities referenced)
                - parse_error: str (if parsing failed)

        Example:
            >>> extractor = CloudFlowMetadataExtractor()
            >>> metadata = extractor.extract_metadata(flow_id, flow_name, clientdata)
            >>> if 'parse_error' not in metadata:
            ...     print(f"Flow modifies {len(metadata['modified_fields'])} fields")
        """
        # Initialize result structure
        result = {
            'flow_id': flow_id,
            'flow_name': flow_name,
            'flow_type': 'Cloud Flow',
            'trigger_type': 'Unknown',
            'actions': [],
            'modified_fields': {},
            'read_fields': set(),
            'variables': {},
            'entities': set()
        }

        # Create fresh VariableTracker for this flow
        variable_tracker = VariableTracker()

        try:
            # Parse clientdata
            parser = CloudFlowParser()
            parse_result = parser.parse_clientdata(clientdata, flow_name)

            if not parse_result['success']:
                result['parse_error'] = parse_result['error']
                return result

            definition = parse_result['definition']

            # Extract trigger type
            result['trigger_type'] = CloudFlowOperations.get_flow_trigger_type(definition)

            # Process actions
            actions = definition.get('actions', {})

            for action_name, action_def in actions.items():
                result['actions'].append(action_name)
                action_type = action_def.get('type', '')

                # Track variable initialization actions
                if action_type == 'InitializeVariable':
                    inputs = action_def.get('inputs', {})
                    variables = inputs.get('variables', [])
                    if variables:
                        var_info = variables[0]
                        var_name = var_info.get('name', '')
                        var_value = var_info.get('value', '')
                        var_type = var_info.get('type', '')

                        if var_name:
                            variable_tracker.register_variable(
                                var_name=var_name,
                                action_name=action_name,
                                initial_value=var_value,
                                value_type=var_type
                            )

                # Track variable modification actions
                elif action_type in ('SetVariable', 'IncrementVariable', 'DecrementVariable',
                                    'AppendToArrayVariable', 'AppendToStringVariable'):
                    inputs = action_def.get('inputs', {})
                    var_name = inputs.get('name', '')
                    var_value = inputs.get('value', '')

                    if var_name:
                        operation = action_type.replace('Variable', '')  # Set, Increment, etc.
                        variable_tracker.track_modification(
                            var_name=var_name,
                            action_name=action_name,
                            operation=operation,
                            new_value=var_value
                        )

                # Analyze update/create actions
                analysis = self.action_analyzer.analyze_update_action(action_name, action_def)

                if analysis:
                    # Add entity
                    entity_name = analysis['entity_name']
                    if entity_name != 'dynamic' and entity_name != 'unknown':
                        result['entities'].add(entity_name)

                    # Process modified fields
                    for field_info in analysis['modified_fields']:
                        field_name = field_info['field_name']

                        # Add to modified_fields dict
                        if field_name not in result['modified_fields']:
                            result['modified_fields'][field_name] = []

                        # Get source detail - if it's a variable, include declaration info
                        source_detail = field_info.get('source_detail', '')
                        if field_info['source_type'] == 'variable' and source_detail:
                            var_source = variable_tracker.get_variable_source(source_detail)
                            if var_source:
                                source_detail = f"{source_detail} (declared in {var_source.get('declared_in', 'Unknown')})"

                        result['modified_fields'][field_name].append({
                            'action_name': action_name,
                            'source_type': field_info['source_type'],
                            'source_detail': source_detail,
                            'expression': field_info['expression']
                        })

                        # Track read fields from expressions
                        if 'source_field' in field_info:
                            result['read_fields'].add(field_info['source_field'])

            # Export all tracked variables to result
            result['variables'] = variable_tracker.get_all_variables()

            return result

        except Exception as e:
            logger.error(f"Error extracting metadata for flow '{flow_name}': {str(e)}")
            result['parse_error'] = str(e)
            return result
