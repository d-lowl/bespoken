"""File tools for the bespoken assistant."""

from typing import Optional
from pathlib import Path
import difflib
import re
from rich import get_console
from rich.prompt import Confirm, Prompt
from langchain_core.tools import tool

from .. import ui


def _debug_return(value: str) -> str:
    """Helper to show what the LLM receives from tools"""
    ui.tool_debug(f"\n>>> Tool returning to LLM: {repr(value)}\n")
    return value


def _resolve_path(file_path: str, working_directory: str = ".") -> Path:
    working_dir = Path(working_directory).resolve()
    if Path(file_path).is_absolute():
        return Path(file_path).resolve()
    return (working_dir / file_path).resolve()


@tool
def list_files(directory: Optional[str] = None, working_directory: str = ".") -> str:
    """List files and directories."""
    ui.tool_debug(f">>> LLM calling tool: list_files(directory={repr(directory)})")
    ui.tool_status(f"Listing files in {directory or 'current directory'}...")
    target_dir = _resolve_path(directory, working_directory) if directory else Path(working_directory).resolve()
    
    items = []
    for item in sorted(target_dir.iterdir()):
        if item.is_dir():
            items.append(f"{item.name}/ [DIR]")
        else:
            items.append(f"{item.name} ({item.stat().st_size} bytes)")
            
    return _debug_return(f"Files in {target_dir}:\n" + "\n".join(items) if items else "No files found")


@tool
def read_file(file_path: str, working_directory: str = ".") -> str:
    """Read content from a file."""
    ui.tool_debug(f">>> LLM calling tool: read_file(file_path={repr(file_path)})")
    ui.tool_status(f"Reading file: {file_path}")
    full_path = _resolve_path(file_path, working_directory)
    content = full_path.read_text(encoding='utf-8', errors='replace')
    
    if len(content) > 50_000:
        content = content[:50_000] + "\n... (truncated)"
        
    return _debug_return(content)


@tool
def write_file(file_path: str, content: str, working_directory: str = ".") -> str:
    """Write content to a file."""
    ui.tool_debug(f">>> LLM calling tool: write_file(file_path={repr(file_path)}, content=<{len(content)} chars>)")
    ui.tool_status(f"Writing {len(content):,} characters to: {file_path}")
    full_path = _resolve_path(file_path, working_directory)
    full_path.parent.mkdir(parents=True, exist_ok=True)
    full_path.write_text(content, encoding='utf-8')
    
    return _debug_return(f"Wrote {len(content):,} characters to '{file_path}'")


@tool
def replace_in_file(file_path: str, old_string: str, new_string: str, working_directory: str = ".") -> str:
    """Replace string in file and show diff. The user may deny the change, in which case you should wait for new instructions."""
    ui.tool_debug(f">>> LLM calling tool: replace_in_file(file_path={repr(file_path)}, old_string=<{len(old_string)} chars>, new_string=<{len(new_string)} chars>)")
    ui.tool_status(f"Preparing to replace text in: {file_path}")
    full_path = _resolve_path(file_path, working_directory)
    original_content = full_path.read_text(encoding='utf-8')
    new_content = original_content.replace(old_string, new_string)
    
    diff_lines = list(difflib.unified_diff(
        original_content.splitlines(keepends=True),
        new_content.splitlines(keepends=True),
        fromfile=f"{file_path} (before)",
        tofile=f"{file_path} (after)",
        n=3
    ))
    
    if diff_lines:
        # Show the diff with custom formatting
        ui.tool_warning("Proposed changes:")
        ui.print("")
        
        # Parse the diff to add line numbers and colors
        line_num_old = 0
        line_num_new = 0
        
        for line in diff_lines:
            if line.startswith('---') or line.startswith('+++'):
                # File headers
                ui.print(f"[dim]{line.rstrip()}[/dim]")
            elif line.startswith('@@'):
                # Hunk header - extract line numbers
                match = re.search(r'-(\d+)(?:,\d+)? \+(\d+)(?:,\d+)?', line)
                if match:
                    line_num_old = int(match.group(1))
                    line_num_new = int(match.group(2))
                ui.print(f"[dim]{line.rstrip()}[/dim]")
            elif line.startswith(' '):
                # Context line
                line_num_old += 1
                line_num_new += 1
                ui.print(f"[dim]{line_num_old:4d} {line_num_new:4d}[/dim] {line.rstrip()}")
            elif line.startswith('-'):
                # Deleted line
                line_num_old += 1
                ui.print(f"[red]{line_num_old:4d}     -[/red] {line[1:].rstrip()}")
            elif line.startswith('+'):
                # Added line
                line_num_new += 1
                ui.print(f"[green]     {line_num_new:4d} +[/green] {line[1:].rstrip()}")
        
        ui.print("")
        
        # Ask for confirmation
        if Confirm.ask("Apply these changes?"):
            full_path.write_text(new_content, encoding='utf-8')
            return _debug_return(f"Applied changes to '{file_path}'")
        else:
            return _debug_return("Changes were not applied")
    else:
        return _debug_return("No changes found - the strings are identical")


def FileTool(file_path: str) -> list:
    """Create a file-specific tool that can only work with one file."""
    file_path_obj = Path(file_path).resolve()
    
    if not file_path_obj.exists():
        raise FileNotFoundError(f"File does not exist: {file_path}")
    
    @tool
    def get_file_path() -> str:
        """Return the path to the file that this tool is allowed to edit."""
        ui.tool_debug(">>> LLM calling tool: get_file_path()")
        ui.tool_status(f"Getting file path for: {file_path_obj.name}")
        return _debug_return(f"This tool can only access one file: {file_path_obj}. Other files exist but are not accessible through this tool.")
    
    @tool(description=f"Read the content of {file_path_obj.name}. This tool cannot be used to open or edit other files.")
    def read_file() -> str:
        """Read the content of the provided file. This tool cannot be used to open or edit other files."""
        ui.tool_debug(">>> LLM calling tool: read_file()")
        ui.tool_status(f"Reading file: {file_path_obj.name}")
        
        content = file_path_obj.read_text(encoding='utf-8', errors='replace')
        
        if len(content) > 50_000:
            content = content[:50_000] + "\n... (truncated)"
            
        return _debug_return(content)
    
    @tool(description=f"Replace string in {file_path_obj.name} and show diff. The user may deny the change, in which case you should wait for new instructions. This tool cannot be used to open or edit other files.")
    def replace_in_file(old_string: str, new_string: str) -> str:
        """Replace string in the provided file and show diff. The user may deny the change, in which case you should wait for new instructions. This tool cannot be used to open or edit other files."""
        ui.tool_debug(f">>> LLM calling tool: replace_in_file(old_string=<{len(old_string)} chars>, new_string=<{len(new_string)} chars>)")
        ui.tool_status(f"Preparing to replace text in: {file_path_obj.name}")
        
        original_content = file_path_obj.read_text(encoding='utf-8')
        new_content = original_content.replace(old_string, new_string)
        
        diff_lines = list(difflib.unified_diff(
            original_content.splitlines(keepends=True),
            new_content.splitlines(keepends=True),
            fromfile=f"{file_path_obj.name} (before)",
            tofile=f"{file_path_obj.name} (after)",
            n=3
        ))
        
        if diff_lines:
            # Show the diff with custom formatting
            ui.tool_warning("Proposed changes:")
            ui.print("")
            
            # Parse the diff to add line numbers and colors
            line_num_old = 0
            line_num_new = 0
            
            for line in diff_lines:
                if line.startswith('---') or line.startswith('+++'):
                    # File headers
                    ui.print(f"[dim]{line.rstrip()}[/dim]")
                elif line.startswith('@@'):
                    # Hunk header - extract line numbers
                    match = re.search(r'-(\d+)(?:,\d+)? \+(\d+)(?:,\d+)?', line)
                    if match:
                        line_num_old = int(match.group(1))
                        line_num_new = int(match.group(2))
                    ui.print(f"[dim]{line.rstrip()}[/dim]")
                elif line.startswith(' '):
                    # Context line
                    line_num_old += 1
                    line_num_new += 1
                    ui.print(f"[dim]{line_num_old:4d} {line_num_new:4d}[/dim] {line.rstrip()}")
                elif line.startswith('-'):
                    # Deleted line
                    line_num_old += 1
                    ui.print(f"[red]{line_num_old:4d}     -[/red] {line[1:].rstrip()}")
                elif line.startswith('+'):
                    # Added line
                    line_num_new += 1
                    ui.print(f"[green]     {line_num_new:4d} +[/green] {line[1:].rstrip()}")
            
            ui.print("")
            
            # Ask for confirmation
            if Confirm.ask("Apply these changes?"):
                file_path_obj.write_text(new_content, encoding='utf-8')
                return _debug_return(f"Applied changes to '{file_path_obj.name}'")
            else:
                return _debug_return("Changes were not applied")
        else:
            return _debug_return("No changes found - the strings are identical")
    
    return [get_file_path, read_file, replace_in_file]


# Legacy class for backward compatibility
class FileSystem:
    """File system operations toolbox - can work with multiple files and directories."""
    
    def __init__(self, working_directory: str = "."):
        self.working_directory = working_directory
    
    def list_files(self, directory: Optional[str] = None) -> str:
        return list_files(directory, self.working_directory)
    
    def read_file(self, file_path: str) -> str:
        return read_file(file_path, self.working_directory)
    
    def write_file(self, file_path: str, content: str) -> str:
        return write_file(file_path, content, self.working_directory)
    
    def replace_in_file(self, file_path: str, old_string: str, new_string: str) -> str:
        return replace_in_file(file_path, old_string, new_string, self.working_directory)