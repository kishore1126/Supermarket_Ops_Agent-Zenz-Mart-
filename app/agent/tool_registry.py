"""Tool Registry for Supermarket Ops Agent."""

from typing import Any, Callable, Coroutine, Type
from pydantic import BaseModel
from sqlalchemy.ext.asyncio import AsyncSession


class Tool:
    def __init__(
        self,
        name: str,
        description: str,
        schema: Type[BaseModel],
        handler: Callable[..., Coroutine[Any, Any, dict[str, Any]]],
    ):
        self.name = name
        self.description = description
        self.schema = schema
        self.handler = handler

    def to_anthropic_tool(self) -> dict[str, Any]:
        """Convert Pydantic schema to Anthropic tool definition."""
        json_schema = self.schema.model_json_schema()
        # Clean up title and metadata for clean LLM prompt
        json_schema.pop("title", None)
        return {
            "name": self.name,
            "description": self.description,
            "input_schema": json_schema,
        }


class ToolRegistry:
    def __init__(self):
        self._tools: dict[str, Tool] = {}

    def register(self, name: str, description: str, schema: Type[BaseModel]):
        """Decorator to register an async tool handler."""
        def decorator(func: Callable[..., Coroutine[Any, Any, dict[str, Any]]]):
            tool = Tool(
                name=name,
                description=description,
                schema=schema,
                handler=func,
            )
            self._tools[name] = tool
            return func
        return decorator

    def get_tool(self, name: str) -> Tool | None:
        return self._tools.get(name)

    def get_all_tools(self) -> list[Tool]:
        return list(self._tools.values())

    def get_anthropic_tools(self) -> list[dict[str, Any]]:
        """Return list of all registered tool schemas for Anthropic API."""
        return [tool.to_anthropic_tool() for tool in self._tools.values()]

    async def execute(
        self,
        name: str,
        session: AsyncSession,
        arguments: dict[str, Any],
        **extra_context: Any
    ) -> dict[str, Any]:
        """Validate input arguments and execute the registered tool handler."""
        tool = self._tools.get(name)
        if not tool:
            return {"error": f"Tool '{name}' not found."}

        try:
            # Validate through Pydantic
            validated_args = tool.schema(**arguments)
            # Call handler passing session and validated model fields
            args_dict = validated_args.model_dump()
            return await tool.handler(session=session, **args_dict, **extra_context)
        except Exception as e:
            return {"error": f"Error executing {name}: {str(e)}"}


# Global Tool Registry Singleton
registry = ToolRegistry()
