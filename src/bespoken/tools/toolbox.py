"""Bespoken Toolbox."""

from typing import List
import inspect
import functools
from langchain_core.tools import BaseTool, StructuredTool


class Toolbox:
    """Base class for all toolboxes.
    
    A toolbox is a class whose methods may be decorated with @tool. This base
    class provides a way to collect those tools and, when necessary, bind the
    instance (self) to the underlying function so LangChain can invoke them.
    """

    def __init__(self):
        pass

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
                            bound_func = functools.partial(tool_obj.func, self)
                            # Recreate the tool with the same metadata but a bound function
                            rebound_tool = StructuredTool(
                                name=tool_obj.name,
                                description=tool_obj.description,
                                func=bound_func,
                                args_schema=getattr(tool_obj, "args_schema", None),
                                return_direct=getattr(tool_obj, "return_direct", False),
                                infer_schema=False,
                            )
                            collected.append(rebound_tool)
                            continue

                # Default: use the tool as-is
                collected.append(tool_obj)

        return collected
    