"""
Azure Logic Apps Workflow Definition Language Expression Parser

This module provides parsing capabilities for expressions used in Power Automate cloud flows.
Phase 1 implements regex-based parsing for common expression patterns.
Phase 2 implements AST-based parsing using Lark for complex nested expressions.
"""

import re
import logging
from typing import Any, Optional
from lark import Lark, Transformer, Token, Tree
from lark.exceptions import LarkError

logger = logging.getLogger(__name__)


# Phase 2: Lark grammar for Azure Logic Apps expression language
# Restructured to eliminate Reduce/Reduce conflicts
EXPRESSION_GRAMMAR = r"""
    ?start: expression

    expression: "@" primary
             | primary
             | literal

    primary: IDENTIFIER "(" argument_list? ")" accessor*  -> function_call_with_accessors
           | IDENTIFIER accessor+                         -> identifier_with_accessors
           | IDENTIFIER                                   -> identifier_only
           | "(" expression ")" accessor*                 -> parenthesized_expression

    accessor: "." IDENTIFIER                              -> dot_accessor
           | "?" "[" selector "]"                         -> optional_bracket_accessor
           | "[" selector "]"                             -> bracket_accessor

    argument_list: expression ("," expression)*

    selector: STRING | NUMBER | IDENTIFIER

    literal: STRING
           | NUMBER
           | BOOLEAN
           | NULL

    IDENTIFIER: /[a-zA-Z_][a-zA-Z0-9_]*/
    STRING: /'[^']*'/ | /"[^"]*"/
    NUMBER: /-?\d+(\.\d+)?/
    BOOLEAN: "true" | "false"
    NULL: "null"

    %import common.WS
    %ignore WS
"""


class ExpressionTransformer(Transformer):
    """Transform parsed expression AST into structured data.

    Converts Lark parse tree into a dictionary with metadata about the expression.
    """

    def expression(self, items):
        """Transform expression node."""
        if len(items) == 1:
            return items[0]
        # Handle @ prefix (items[0] is the primary after @)
        return {'at_prefix': True, 'value': items[0]}

    def function_call_with_accessors(self, items):
        """Transform function call with optional accessors.

        Args:
            items: [func_name, arg_list (optional), *accessors]
        """
        func_name = str(items[0])

        # Check if second item is argument list or accessor
        args = []
        accessor_start_idx = 1

        if len(items) > 1 and isinstance(items[1], list):
            args = items[1]
            accessor_start_idx = 2

        accessors = items[accessor_start_idx:] if len(items) > accessor_start_idx else []

        result = {
            'type': 'function_call',
            'function': func_name,
            'arguments': args
        }

        if accessors:
            result['accessors'] = accessors

        return result

    def identifier_with_accessors(self, items):
        """Transform identifier with accessors (property access).

        Args:
            items: [identifier, *accessors]
        """
        identifier = str(items[0])
        accessors = items[1:] if len(items) > 1 else []

        return {
            'type': 'property_access',
            'base': identifier,
            'accessors': accessors
        }

    def identifier_only(self, items):
        """Transform standalone identifier."""
        return str(items[0])

    def parenthesized_expression(self, items):
        """Transform parenthesized expression with optional accessors.

        Args:
            items: [expression, *accessors]
        """
        expr = items[0]
        accessors = items[1:] if len(items) > 1 else []

        if accessors:
            return {
                'type': 'property_access',
                'base': expr,
                'accessors': accessors
            }
        return expr

    def dot_accessor(self, items):
        """Transform dot accessor (.field)."""
        return {'accessor_type': 'dot', 'value': str(items[0])}

    def bracket_accessor(self, items):
        """Transform bracket accessor ([selector])."""
        return {'accessor_type': 'bracket', 'value': items[0]}

    def optional_bracket_accessor(self, items):
        """Transform optional bracket accessor (?[selector])."""
        return {'accessor_type': 'optional_bracket', 'value': items[0]}

    def argument_list(self, items):
        """Transform argument list."""
        return list(items)

    def selector(self, items):
        """Transform selector (string, number, or identifier)."""
        item = items[0]
        if isinstance(item, Token):
            value = str(item)
            # Remove quotes from strings
            if value.startswith(("'", '"')) and value.endswith(("'", '"')):
                return value[1:-1]
            return value
        return item

    def literal(self, items):
        """Transform literal value."""
        return items[0]

    def IDENTIFIER(self, token):
        """Transform identifier token."""
        return str(token)

    def STRING(self, token):
        """Transform string token."""
        value = str(token)
        # Remove quotes
        if value.startswith(("'", '"')) and value.endswith(("'", '"')):
            return value[1:-1]
        return value

    def NUMBER(self, token):
        """Transform number token."""
        value = str(token)
        return float(value) if '.' in value else int(value)

    def BOOLEAN(self, token):
        """Transform boolean token."""
        return str(token).lower() == 'true'

    def NULL(self, token):
        """Transform null token."""
        return None


class ExpressionParser:
    """Parse Azure Logic Apps Workflow Definition Language expressions.

    Phase 1: Regex-based patterns for common expressions.
    Supports parsing of trigger references, variables, outputs, and parameters.
    """

    # Regex patterns for common expression types
    PATTERNS = {
        # @triggerBody()?['fieldname'] or @triggerBody()['fieldname']
        'trigger_body': re.compile(r"@triggerBody\(\)\s*\??\s*\[\s*['\"]([^'\"]+)['\"]\s*\]"),

        # @triggerOutputs()?['body/fieldname']
        'trigger_outputs': re.compile(r"@triggerOutputs\(\)\s*\??\s*\[\s*['\"]body/([^'\"]+)['\"]\s*\]"),

        # @variables('varname')
        'variables': re.compile(r"@variables\(\s*['\"]([^'\"]+)['\"]\s*\)"),

        # @outputs('stepname') or @outputs('stepname')?['body/fieldname']
        'outputs': re.compile(r"@outputs\(\s*['\"]([^'\"]+)['\"]\s*\)"),

        # @outputs('stepname')?['body/fieldname']
        'outputs_field': re.compile(r"@outputs\(\s*['\"]([^'\"]+)['\"]\s*\)\s*\??\s*\[\s*['\"]body/([^'\"]+)['\"]\s*\]"),

        # @parameters('paramname')
        'parameters': re.compile(r"@parameters\(\s*['\"]([^'\"]+)['\"]\s*\)"),

        # @body('stepname')?['fieldname']
        'body_field': re.compile(r"@body\(\s*['\"]([^'\"]+)['\"]\s*\)\s*\??\s*\[\s*['\"]([^'\"]+)['\"]\s*\]"),

        # @item()?['fieldname'] - used in Apply to each loops
        'item_field': re.compile(r"@item\(\)\s*\??\s*\[\s*['\"]([^'\"]+)['\"]\s*\]"),
    }

    def parse_expression(self, expression: str) -> dict[str, any]:
        """Parse an expression string and extract metadata.

        Args:
            expression: Expression string (e.g., "@triggerBody()?['field']")

        Returns:
            Dict with keys:
                - source_type: 'trigger', 'variable', 'output', 'parameter', 'static', 'unknown'
                - field_ref: Field name if applicable
                - variable_name: Variable name if source_type='variable'
                - step_name: Step name if source_type='output'
                - expression: Original expression string
                - static_value: Value if source_type='static'
        """
        if not expression:
            return {
                'source_type': 'static',
                'static_value': None,
                'expression': ''
            }

        # Convert to string if not already
        expression_str = str(expression)

        # Check if it's an expression (starts with @)
        if not expression_str.strip().startswith('@'):
            # Static value
            return {
                'source_type': 'static',
                'static_value': expression,
                'expression': expression_str
            }

        # Try to match trigger body patterns
        match = self.PATTERNS['trigger_body'].search(expression_str)
        if match:
            return {
                'source_type': 'trigger',
                'field_ref': match.group(1),
                'expression': expression_str
            }

        # Try trigger outputs pattern
        match = self.PATTERNS['trigger_outputs'].search(expression_str)
        if match:
            return {
                'source_type': 'trigger',
                'field_ref': match.group(1),
                'expression': expression_str
            }

        # Try variables pattern
        match = self.PATTERNS['variables'].search(expression_str)
        if match:
            return {
                'source_type': 'variable',
                'variable_name': match.group(1),
                'expression': expression_str
            }

        # Try outputs with field pattern
        match = self.PATTERNS['outputs_field'].search(expression_str)
        if match:
            return {
                'source_type': 'output',
                'step_name': match.group(1),
                'field_ref': match.group(2),
                'expression': expression_str
            }

        # Try outputs pattern (without field)
        match = self.PATTERNS['outputs'].search(expression_str)
        if match:
            return {
                'source_type': 'output',
                'step_name': match.group(1),
                'expression': expression_str
            }

        # Try body field pattern
        match = self.PATTERNS['body_field'].search(expression_str)
        if match:
            return {
                'source_type': 'output',
                'step_name': match.group(1),
                'field_ref': match.group(2),
                'expression': expression_str
            }

        # Try item field pattern (Apply to each)
        match = self.PATTERNS['item_field'].search(expression_str)
        if match:
            return {
                'source_type': 'item',
                'field_ref': match.group(1),
                'expression': expression_str
            }

        # Try parameters pattern
        match = self.PATTERNS['parameters'].search(expression_str)
        if match:
            return {
                'source_type': 'parameter',
                'parameter_name': match.group(1),
                'expression': expression_str
            }

        # Unknown expression type
        logger.warning(f"Could not parse expression: {expression_str}")
        return {
            'source_type': 'unknown',
            'expression': expression_str
        }

    def extract_field_references(self, value: any) -> set[str]:
        """Extract all field references from a value (string, dict, list).

        Args:
            value: Action parameter value (can be expression string or nested structure)

        Returns:
            Set of field names referenced
        """
        field_refs = set()

        if value is None:
            return field_refs

        # If it's a string, parse it
        if isinstance(value, str):
            parsed = self.parse_expression(value)
            if 'field_ref' in parsed:
                field_refs.add(parsed['field_ref'])

        # If it's a dict, recursively process values
        elif isinstance(value, dict):
            for v in value.values():
                field_refs.update(self.extract_field_references(v))

        # If it's a list, recursively process items
        elif isinstance(value, list):
            for item in value:
                field_refs.update(self.extract_field_references(item))

        return field_refs

    def is_expression(self, value: any) -> bool:
        """Check if a value is an expression (starts with @).

        Args:
            value: Value to check

        Returns:
            True if value is an expression string
        """
        if not isinstance(value, str):
            return False
        return value.strip().startswith('@')

    def get_source_type(self, expression: str) -> str:
        """Determine source type from expression.

        Args:
            expression: Expression string

        Returns:
            Source type: 'trigger', 'variable', 'output', 'parameter', 'static', 'unknown'
        """
        parsed = self.parse_expression(expression)
        return parsed.get('source_type', 'unknown')


class AdvancedExpressionParser(ExpressionParser):
    """AST-based expression parser using Lark.

    Phase 2: Enhanced parser that builds an Abstract Syntax Tree for complex nested expressions.
    Falls back to regex patterns from Phase 1 for compatibility.
    """

    def __init__(self):
        """Initialize the AST parser with Lark grammar."""
        super().__init__()
        try:
            self.parser = Lark(EXPRESSION_GRAMMAR, parser='lalr')
            self.transformer = ExpressionTransformer()
            self.ast_enabled = True
        except Exception as e:
            logger.warning(f"Failed to initialize AST parser: {e}. Falling back to regex-only parsing.")
            self.ast_enabled = False

    def parse_expression(self, expression: str) -> dict[str, Any]:
        """Parse expression using AST parser with fallback to regex.

        Args:
            expression: Expression string (e.g., "@triggerBody()?['field']")

        Returns:
            Dict with keys:
                - source_type: 'trigger', 'variable', 'output', 'parameter', 'static', 'unknown'
                - field_ref: Field name if applicable
                - variable_name: Variable name if source_type='variable'
                - step_name: Step name if source_type='output'
                - expression: Original expression string
                - static_value: Value if source_type='static'
                - ast: Abstract syntax tree (if AST parsing succeeded)
        """
        if not self.ast_enabled:
            # Fallback to Phase 1 regex parsing
            return super().parse_expression(expression)

        # First try AST parsing for complex expressions
        if isinstance(expression, str) and expression.strip().startswith('@'):
            try:
                tree = self.parser.parse(expression)
                ast_result = self.transformer.transform(tree)

                # Extract semantic information from AST
                semantic_info = self._extract_semantic_info(ast_result)
                semantic_info['expression'] = expression
                semantic_info['ast'] = ast_result

                return semantic_info

            except LarkError as e:
                logger.debug(f"AST parsing failed for: {expression}, error: {e}. Falling back to regex.")
            except Exception as e:
                logger.debug(f"Unexpected error in AST parsing: {e}. Falling back to regex.")

        # Fallback to Phase 1 regex patterns
        return super().parse_expression(expression)

    def _extract_semantic_info(self, ast: Any) -> dict[str, Any]:
        """Extract semantic information from parsed AST.

        Args:
            ast: Parsed AST from transformer

        Returns:
            Dict with source_type and related metadata
        """
        if not isinstance(ast, dict):
            # Simple string or literal value
            if isinstance(ast, str):
                return {'source_type': 'identifier', 'identifier': ast}
            return {'source_type': 'static', 'static_value': ast}

        # Handle function calls (with or without accessors)
        if ast.get('type') == 'function_call':
            func_name = ast.get('function', '')
            args = ast.get('arguments', [])
            accessors = ast.get('accessors', [])

            # Build base result for function call
            result = {}

            # triggerBody(), triggerOutputs()
            if func_name in ('triggerBody', 'triggerOutputs'):
                result = {
                    'source_type': 'trigger',
                    'function': func_name
                }

            # variables('varname')
            elif func_name == 'variables':
                var_name = args[0] if args else None
                result = {
                    'source_type': 'variable',
                    'variable_name': var_name
                }

            # outputs('stepname'), body('stepname')
            elif func_name in ('outputs', 'body'):
                step_name = args[0] if args else None
                result = {
                    'source_type': 'output',
                    'step_name': step_name,
                    'function': func_name
                }

            # parameters('paramname')
            elif func_name == 'parameters':
                param_name = args[0] if args else None
                result = {
                    'source_type': 'parameter',
                    'parameter_name': param_name
                }

            # item() - used in Apply to each
            elif func_name == 'item':
                result = {
                    'source_type': 'item',
                    'function': func_name
                }

            # Other functions
            else:
                result = {
                    'source_type': 'function',
                    'function': func_name,
                    'arguments': args
                }

            # Extract field references from accessors if present
            if accessors:
                field_refs = self._extract_field_refs_from_accessors(accessors)
                if field_refs:
                    result['field_ref'] = field_refs[0]
                    if len(field_refs) > 1:
                        result['field_path'] = field_refs

            return result

        # Handle property access
        if ast.get('type') == 'property_access':
            base = ast.get('base', {})
            accessors = ast.get('accessors', [])

            # Extract base information
            # Base can be a string (identifier_only) or a dict (complex expression)
            if isinstance(base, str):
                base_info = {'source_type': 'identifier', 'identifier': base}
            elif isinstance(base, dict):
                base_info = self._extract_semantic_info(base)
            else:
                base_info = {'source_type': 'unknown'}

            # Extract field references from accessors
            field_refs = self._extract_field_refs_from_accessors(accessors)

            result = base_info.copy()
            if field_refs:
                result['field_ref'] = field_refs[0]  # Primary field reference
                if len(field_refs) > 1:
                    result['field_path'] = field_refs  # Full path for nested access

            return result

        # Handle @ prefix
        if ast.get('at_prefix'):
            value = ast.get('value')
            return self._extract_semantic_info(value) if value else {'source_type': 'unknown'}

        # Unknown structure
        return {'source_type': 'unknown', 'ast_data': ast}

    def _extract_field_refs_from_accessors(self, accessors: list) -> list[str]:
        """Extract field references from a list of accessor dicts.

        Args:
            accessors: List of accessor dicts from AST

        Returns:
            List of field reference strings
        """
        field_refs = []
        for accessor in accessors:
            if isinstance(accessor, dict):
                value = accessor.get('value')
                if value:
                    # Remove 'body/' prefix if present
                    if isinstance(value, str) and value.startswith('body/'):
                        value = value[5:]
                    field_refs.append(value)
        return field_refs


class VariableTracker:
    """Track variable declarations and modifications throughout flow execution.

    Maintains a registry of all variables declared in a flow and tracks how they
    are modified by various actions.
    """

    def __init__(self):
        """Initialize the variable tracker."""
        self.variables: dict[str, dict[str, Any]] = {}

    def register_variable(
        self,
        var_name: str,
        action_name: str,
        initial_value: Any,
        value_type: str
    ) -> None:
        """Register a new variable from Initialize variable action.

        Args:
            var_name: Name of the variable
            action_name: Name of the action that declares the variable
            initial_value: Initial value assigned to the variable
            value_type: Type of the variable (String, Integer, Boolean, Array, Object, etc.)
        """
        self.variables[var_name] = {
            'declared_in': action_name,
            'initial_value': initial_value,
            'value_type': value_type,
            'modifications': []
        }
        logger.debug(f"Registered variable '{var_name}' in action '{action_name}'")

    def track_modification(
        self,
        var_name: str,
        action_name: str,
        operation: str,
        new_value: Any
    ) -> None:
        """Track variable modification (Set, Increment, Append, etc.).

        Args:
            var_name: Name of the variable being modified
            action_name: Name of the action performing the modification
            operation: Type of operation (Set, Increment, Append, etc.)
            new_value: New value or value being added/appended
        """
        if var_name not in self.variables:
            # Variable used but not declared - log warning and create entry
            logger.warning(f"Variable '{var_name}' modified in '{action_name}' but not declared")
            self.variables[var_name] = {
                'declared_in': None,
                'initial_value': None,
                'value_type': 'Unknown',
                'modifications': []
            }

        self.variables[var_name]['modifications'].append({
            'action': action_name,
            'operation': operation,
            'value': new_value
        })
        logger.debug(f"Tracked modification of '{var_name}' in action '{action_name}' ({operation})")

    def get_variable_source(self, var_name: str) -> dict[str, Any]:
        """Get variable declaration info (ignoring modifications).

        Args:
            var_name: Name of the variable

        Returns:
            Dict with declaration info (declared_in, initial_value, value_type)
            or empty dict if variable not found
        """
        if var_name not in self.variables:
            return {}

        var_info = self.variables[var_name]
        return {
            'declared_in': var_info['declared_in'],
            'initial_value': var_info['initial_value'],
            'value_type': var_info['value_type']
        }

    def get_all_variables(self) -> dict[str, dict[str, Any]]:
        """Get complete information about all tracked variables.

        Returns:
            Dict mapping variable names to their full metadata
        """
        return self.variables.copy()

    def is_variable_declared(self, var_name: str) -> bool:
        """Check if a variable has been declared.

        Args:
            var_name: Name of the variable

        Returns:
            True if variable is registered, False otherwise
        """
        return var_name in self.variables

    def get_modification_count(self, var_name: str) -> int:
        """Get number of times a variable has been modified.

        Args:
            var_name: Name of the variable

        Returns:
            Number of modifications, or 0 if variable not found
        """
        if var_name not in self.variables:
            return 0
        return len(self.variables[var_name]['modifications'])
