"""Bespoken Toolbox."""

from typing import List
import inspect
from langchain_core.tools import BaseTool, StructuredTool, tool


class Toolbox:
    """Base class for all toolboxes.
    
    A toolbox is a class whose methods may be decorated with @tool. This base
    class provides a way to collect those tools and, when necessary, bind the
    instance (self) to the underlying function so LangChain can invoke them.
    """

    def __init__(self):
        pass

    @staticmethod
    def _bind_tool(tool_obj: BaseTool, self: any) -> BaseTool:
        """Bind the instance (self) to the underlying function so LangChain can invoke them."""
        func = tool_obj.func
        def inner(*args, **kwargs):
            return func(self, *args, **kwargs)
        inner.__name__ = f"{self.__class__.__name__}__{tool_obj.name}"
        sig = inspect.signature(func)
        params = list(sig.parameters.values())[1:]  # Skip 'self'
        new_sig = sig.replace(parameters=params)
        inner.__signature__ = new_sig
        if hasattr(func, '__annotations__'):
            inner.__annotations__ = {
                k: v for k, v in func.__annotations__.items() 
                if k != 'self'
            }

        return tool(
            inner,
            description=tool_obj.description,
        )


    def collect_tools(self) -> List[BaseTool]:
        """Collect all tools from the toolbox instance.

        - Finds attributes on the class that are LangChain tools (BaseTool).
        - If a tool wraps a method whose first parameter is named 'self',
          returns a new StructuredTool with the instance bound so it can be
          called by the agent without providing 'self'.
        """
        collected: List[BaseTool] = []

        for attr_name, attr_value in self.__class__.__dict__.items():
            if isinstance(attr_value, BaseTool):
                tool_obj: BaseTool = attr_value

                # Only StructuredTool exposes .func; other BaseTool variants may differ
                if isinstance(tool_obj, StructuredTool) and hasattr(tool_obj, "func"):
                    try:
                        sig = inspect.signature(tool_obj.func)
                    except (TypeError, ValueError):
                        sig = None

                    if sig is not None:
                        params = list(sig.parameters.values())
                        # If the underlying function expects 'self' as the first parameter,
                        # bind this instance so the tool can be called without it.
                        if params and params[0].name == "self":
                            rebound_tool = self._bind_tool(tool_obj, self)
                            collected.append(rebound_tool)
                            continue

                # Default: use the tool as-is
                collected.append(tool_obj)

        return collected
    