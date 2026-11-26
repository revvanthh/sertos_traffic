"""
Agent Tool Registry and Central Executor for SERTOS AI Emergency Agent.

Enforces:
1. Mandatory authentication for all tool invocations.
2. Strict role-based permissions (active, verified AMBULANCE_DRIVER only).
3. Parameter validation and error isolation.
4. Consistent JSON response envelope:
   {
       "success": bool,
       "data": Any,
       "error": Optional[{"code": str, "message": str}]
   }
5. Zero direct database writes by AI agents.
"""

from dataclasses import dataclass
from typing import Any, Callable, Dict, List, Optional
from apps.accounts.models import UserRole


@dataclass
class ToolDefinition:
    name: str
    description: str
    parameters_schema: Dict[str, Any]
    handler: Callable


class AgentToolRegistry:
    """Central registry and executor for Voice AI agent tools."""

    def __init__(self):
        self._tools: Dict[str, ToolDefinition] = {}

    def register(
        self,
        name: str,
        description: str,
        parameters_schema: Dict[str, Any],
    ) -> Callable:
        """Decorator to register a tool function with its metadata and schema."""
        def decorator(func: Callable) -> Callable:
            self._tools[name] = ToolDefinition(
                name=name,
                description=description,
                parameters_schema=parameters_schema,
                handler=func,
            )
            return func
        return decorator

    def get_tool(self, name: str) -> Optional[ToolDefinition]:
        """Lookup a registered tool by name."""
        return self._tools.get(name)

    def list_tools(self) -> List[Dict[str, Any]]:
        """Return public tool schemas for LLM / Gemini function calling."""
        return [
            {
                "name": tool.name,
                "description": tool.description,
                "parameters": tool.parameters_schema,
            }
            for tool in self._tools.values()
        ]

    def execute(
        self,
        tool_name: str,
        arguments: Optional[Dict[str, Any]],
        user: Any,
    ) -> Dict[str, Any]:
        """
        Centrally executes an agent tool with complete security guards:
        1. Authentication verification
        2. Role and verification status verification
        3. Tool lookup
        4. Parameter validation and execution
        5. Consistent JSON envelope return
        """
        # 1. Require authenticated user
        if not user or not getattr(user, "is_authenticated", False):
            return {
                "success": False,
                "data": None,
                "error": {
                    "code": "AUTH_REQUIRED",
                    "message": "Authentication required to invoke emergency agent tools.",
                },
            }

        # 2. Enforce active, verified ambulance driver permissions
        if getattr(user, "role", None) != UserRole.AMBULANCE_DRIVER:
            return {
                "success": False,
                "data": None,
                "error": {
                    "code": "PERMISSION_DENIED",
                    "message": "Only verified ambulance drivers may invoke emergency agent tools.",
                },
            }

        if not getattr(user, "is_active", False) or not getattr(user, "is_verified", False):
            return {
                "success": False,
                "data": None,
                "error": {
                    "code": "PERMISSION_DENIED",
                    "message": "Driver account is inactive or not verified.",
                },
            }

        # 3. Lookup tool
        tool = self.get_tool(tool_name)
        if not tool:
            return {
                "success": False,
                "data": None,
                "error": {
                    "code": "TOOL_NOT_FOUND",
                    "message": f"Agent tool '{tool_name}' is not recognized.",
                },
            }

        # 4. Validate arguments format
        args = arguments if arguments is not None else {}
        if not isinstance(args, dict):
            return {
                "success": False,
                "data": None,
                "error": {
                    "code": "VALIDATION_ERROR",
                    "message": "Tool arguments must be a dictionary/object.",
                },
            }

        # 5. Execute handler safely
        try:
            result = tool.handler(user=user, **args)
            return {
                "success": True,
                "data": result,
                "error": None,
            }
        except ValueError as exc:
            return {
                "success": False,
                "data": None,
                "error": {
                    "code": "VALIDATION_ERROR",
                    "message": str(exc),
                },
            }
        except PermissionError as exc:
            return {
                "success": False,
                "data": None,
                "error": {
                    "code": "PERMISSION_DENIED",
                    "message": str(exc),
                },
            }
        except Exception as exc:
            return {
                "success": False,
                "data": None,
                "error": {
                    "code": "EXECUTION_ERROR",
                    "message": str(exc),
                },
            }


# Canonical registry instance
registry = AgentToolRegistry()
