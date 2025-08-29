from datetime import datetime
from typing import Any, Dict, List

from rich import print
from langchain_core.tools import tool

from .. import config

# Global todo storage
_todos: List[Dict[str, Any]] = []


def _debug_return(value: str) -> str:
    """Helper to show what the LLM receives from tools"""
    config.tool_debug(f"\n>>> Tool returning to LLM: {repr(value)}\n")
    return value


@tool
def add_todo(task: str) -> str:
    """Add a new todo item."""
    config.tool_debug(f">>> LLM calling tool: add_todo(task={repr(task)})")
    config.tool_status(f"Adding todo: {task}")
    
    _todos.append({
        "task": task,
        "done": False,
        "created": datetime.now().isoformat()
    })
    
    return _debug_return(f"Added todo: '{task}'")


@tool
def list_todos() -> str:
    """List all todos with their status."""
    config.tool_debug(">>> LLM calling tool: list_todos()")
    config.tool_status("Listing todos...")
    
    if not _todos:
        return _debug_return("No todos found. Add one with add_todo()")
        
    lines = ["Todo List:"]
    for i, todo in enumerate(_todos):
        status = "✓" if todo.get("done", False) else "○"
        lines.append(f"{i + 1}. [{status}] {todo['task']}")
        
    return _debug_return("\n".join(lines))


@tool
def mark_todo_done(index: int) -> str:
    """Mark a todo as completed."""
    config.tool_debug(f">>> LLM calling tool: mark_todo_done(index={repr(index)})")
    config.tool_status(f"Marking todo #{index} as done...")
    
    todo = _todos[index - 1]
    todo["done"] = True
    todo["completed"] = datetime.now().isoformat()
    
    return _debug_return(f"Marked as done: '{todo['task']}'")


@tool
def flush_todos() -> str:
    """Flush all todos."""
    config.tool_debug(">>> LLM calling tool: flush_todos()")
    config.tool_status("Flushing all todos...")
    
    _todos.clear()
    return _debug_return("Flushed todos. All todos have been deleted.")


def TodoTools() -> list:
    """Create a list of todo tools."""
    return [add_todo, list_todos, mark_todo_done, flush_todos]


# Legacy class for backward compatibility
class TodoToolsClass:
    """Todo management toolbox."""
    
    def __init__(self):
        self._todos: List[Dict[str, Any]] = []
    
    def _debug_return(self, value: str) -> str:
        """Helper to show what the LLM receives from tools"""
        config.tool_debug(f"\n>>> Tool returning to LLM: {repr(value)}\n")
        return value
    
    def add_todo(self, task: str) -> str:
        return add_todo(task)
    
    def list_todos(self) -> str:
        return list_todos()
    
    def mark_todo_done(self, index: int) -> str:
        return mark_todo_done(index)
    
    def flush_todos(self) -> str:
        return flush_todos()