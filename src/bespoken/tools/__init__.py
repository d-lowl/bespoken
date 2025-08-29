"""Tools for the bespoken assistant."""

from .filesystem import FileSystem, FileTool, list_files, read_file, write_file, replace_in_file
from .todo import TodoTools, add_todo, list_todos, mark_todo_done, flush_todos
from .webfetch import WebFetchTool, fetch_url
from ..not_installed import NotInstalled

try:
    from .playwright_browser import PlaywrightTool
except ImportError:
    # Replace with NotInstalled proxy
    PlaywrightTool = NotInstalled("PlaywrightTool", "browser")



__all__ = [
    "FileSystem", "FileTool", "list_files", "read_file", "write_file", "replace_in_file",
    "TodoTools", "add_todo", "list_todos", "mark_todo_done", "flush_todos",
    "WebFetchTool", "fetch_url", "PlaywrightTool"
]