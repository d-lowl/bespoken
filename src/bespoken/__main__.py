from pathlib import Path
from typing import Optional, Callable
import json
import uuid

import typer
from dotenv import load_dotenv
from rich.console import Console
from rich.spinner import Spinner
from rich.live import Live
from rich.prompt import Prompt
from rich.columns import Columns
from rich.text import Text
from langchain_core.messages.human import HumanMessage
from langchain_core.messages.ai import AIMessage
from langchain_core.messages.system import SystemMessage
from langchain_core.messages import ToolMessage
from typing import Any, Dict, List, Tuple
from langchain_core.language_models.chat_models import BaseChatModel

from . import config
from . import ui


load_dotenv(".env")

# Command result constants
COMMAND_QUIT = "QUIT"
COMMAND_HANDLED = "HANDLED"


def handle_quit():
    """Handle /quit command"""
    return COMMAND_QUIT


def handle_help(user_commands):
    """Handle /help command"""
    ui.print("[cyan]Built-in commands:[/cyan]")
    ui.print("  /quit   - Exit the application")
    ui.print("  /help   - Show this help message")
    ui.print("  /tools  - Show available tools")
    ui.print("  /debug  - Toggle debug mode")
    
    if user_commands:
        ui.print("")
        ui.print("[cyan]Custom commands:[/cyan]")
        for cmd_name, cmd_handler in user_commands.items():
            if callable(cmd_handler):
                desc = cmd_handler.__doc__ or "Custom function"
                ui.print(f"  {cmd_name}   - {desc}")
            else:
                preview = str(cmd_handler)[:50] + "..." if len(str(cmd_handler)) > 50 else str(cmd_handler)
                ui.print(f"  {cmd_name}   - {preview}")
    
    ui.print("")
    return COMMAND_HANDLED


def handle_tools(tools):
    """Handle /tools command"""
    if tools:
        ui.print("[cyan]Available tools:[/cyan]")
        for tool in tools:
            tool_name = getattr(tool, 'tool_name', type(tool).__name__)
            ui.print(f"  {tool_name}")
    else:
        ui.print("[dim]No tools configured[/dim]")
    ui.print("")
    return COMMAND_HANDLED


def toggle_debug():
    """Toggle debug mode on/off"""
    config.DEBUG_MODE = not config.DEBUG_MODE
    status = "enabled" if config.DEBUG_MODE else "disabled"
    ui.print(f"[magenta]Debug mode {status}[/magenta]")
    ui.print("")
    return COMMAND_HANDLED


def handle_user_command(command, handler):
    """Handle user-defined command"""
    try:
        if callable(handler):
            result = handler()
            if result:
                if isinstance(result, str):
                    # If it looks like a message for the LLM, send it
                    if not result.startswith("[") and not result.endswith("]"):
                        return result  # Treat as LLM input
                    else:
                        # Treat as UI message
                        ui.print(result)
                        ui.print("")
                        return COMMAND_HANDLED
                else:
                    ui.print(str(result))
                    ui.print("")
                    return COMMAND_HANDLED
            else:
                return COMMAND_HANDLED
        else:
            # String - send directly to LLM
            return str(handler)
    except Exception as e:
        ui.print(f"[red]Error executing command {command}: {e}[/red]")
        ui.print("")
        return COMMAND_HANDLED


def dispatch_slash_command(command, user_commands, model, tools, conversation_history):
    """Dispatch slash command to appropriate handler"""
    if command == "/quit":
        return handle_quit(), conversation_history
    elif command == "/help":
        return handle_help(user_commands), conversation_history
    elif command == "/tools":
        return handle_tools(tools), conversation_history
    elif command == "/debug":
        return toggle_debug(), conversation_history
    elif command in user_commands:
        return handle_user_command(command, user_commands[command]), conversation_history
    else:
        ui.print(f"[red]Unknown command: {command}[/red]")
        ui.print("[dim]Type /help for available commands[/dim]")
        ui.print("")
        return COMMAND_HANDLED, conversation_history


def chat(
    debug: bool = typer.Option(False, "--debug", "-d", help="Enable debug mode to see LLM interactions"),
    model_name: str = typer.Option("anthropic/claude-3-5-sonnet-20240620", "--model", "-m", help="LLM model to use"),
    system_prompt: Optional[str] = typer.Option(None, "--system", "-s", help="System prompt for the assistant"),
    tools: list = None,
    slash_commands: dict = None,
    history_callback: Optional[Callable] = None,
    stream: bool = typer.Option(True, "--stream", "-s", help="Stream the response from the LLM"),
):
    """Run the bespoken chat assistant."""
    # Set debug mode globally
    config.DEBUG_MODE = debug
    
    # Initialize user slash commands
    user_commands = slash_commands or {}
    
    console = Console()

    # Show the banner
    ui.show_banner()
    
    if debug:
        ui.print("[magenta]Debug mode enabled[/magenta]")
        ui.print("")
    
    # Initialize the model - this should be passed in from the caller
    # For now, we'll expect it to be a BaseChatModel instance
    if not isinstance(model_name, BaseChatModel):
        ui.print(f"[red]Error: model_name should be a BaseChatModel instance, got {type(model_name)}[/red]")
        raise typer.Exit(1)
    
    model = model_name
    
    # Bind tools to the model if provided
    if tools:
        model = model.bind_tools(tools)
    
    print(model)
    conversation_history = []
    
    try:
        while True:
            # Define available commands for completion (builtin + user commands)
            builtin_commands = ["/quit", "/help", "/tools", "/debug"]
            user_command_names = list(user_commands.keys())
            completions = builtin_commands + user_command_names
            
            # Show completion hint on first prompt
            if not hasattr(chat, '_shown_completion_hint'):
                ui.print("[dim]Tips: TAB for completions • @file.py for file paths • ↑/↓ for history • Ctrl+U to clear[/dim]")
                chat._shown_completion_hint = True
            
            out = ui.input("> ", completions=completions).strip()
            
            # Handle slash commands (only if it's a known command)
            if out.startswith("/"):
                # Check if it's a known command
                builtin_commands = ["/quit", "/help", "/tools", "/debug"]
                if out in builtin_commands or out in user_commands:
                    result, conversation_history = dispatch_slash_command(out, user_commands, model, tools, conversation_history)
                    
                    if result == COMMAND_QUIT:
                        break
                    elif result == COMMAND_HANDLED:
                        continue
                    else:
                        # Command returned text for LLM
                        out = result
                # If it starts with / but isn't a known command, treat as regular text
            
            # Skip empty input
            if not out.strip():
                continue
            
            ui.print("")  # Add whitespace before thinking spinner
            # Show spinner while getting initial response
            # Create a padded spinner
            spinner_text = Text("Thinking...", style="dim")
            padded_spinner = Columns([Text(" " * ui.LEFT_PADDING), Spinner("dots"), spinner_text], expand=False)
            response_started = False

            with Live(padded_spinner, console=console, refresh_per_second=10) as live:
                # Prepare messages for the model
                messages = conversation_history.copy()
                
                # Add system message if provided
                if system_prompt:
                    messages.insert(0, SystemMessage(content=system_prompt))
                
                # Add user message
                messages.append(HumanMessage(content=out))
                
                # Stream the response
                if stream:
                    raise NotImplementedError("Streaming is not supported yet")
                else:
                    # Non-streaming response with tool loop
                    def _run_tools_until_done(
                        bound_model: BaseChatModel,
                        start_messages: List[Any],
                        available_tools: Optional[List[Any]] = None,
                    ) -> Tuple[AIMessage, List[Any]]:
                        """Invoke the model and execute any returned tool calls until completion.
                        Returns the final AIMessage and the list of new messages (AI/tool) produced in this turn.
                        """
                        tool_by_name: Dict[str, Any] = {}
                        if available_tools:
                            for t in available_tools:
                                name = getattr(t, "name", getattr(t, "tool_name", None))
                                if name:
                                    tool_by_name[name] = t

                        working_messages: List[Any] = list(start_messages)
                        produced_messages: List[Any] = []

                        while True:
                            result = bound_model.invoke(working_messages)
                            # Append the AI message to both trackers
                            produced_messages.append(result)
                            working_messages.append(result)

                            tool_calls = getattr(result, "tool_calls", None)
                            if not tool_calls:
                                # No tool calls -> final response
                                return result, produced_messages

                            # Execute each tool call and append ToolMessage
                            for call in tool_calls:
                                call_name = getattr(call, "name", None) or (call.get("name") if isinstance(call, dict) else None)
                                call_args = getattr(call, "args", None) or (call.get("args") if isinstance(call, dict) else None) or {}
                                call_id = getattr(call, "id", None) or (call.get("id") if isinstance(call, dict) else None)

                                tool = tool_by_name.get(call_name)
                                if tool is None:
                                    tool_output = f"Error: Tool '{call_name}' is not available."
                                else:
                                    try:
                                        # LangChain tools created via @tool support .invoke with dict args
                                        tool_output = tool.invoke(call_args)
                                    except Exception as e:
                                        tool_output = f"Error calling tool '{call_name}': {e}"

                                tool_message = ToolMessage(
                                    content=str(tool_output),
                                    tool_call_id=call_id or "",
                                )
                                produced_messages.append(tool_message)
                                working_messages.append(tool_message)

                    final_response, produced_messages = _run_tools_until_done(model, messages, tools)
                    print(final_response)
                    live.stop()
                    ui.print("")  # Add whitespace after spinner
                    ui.print(final_response.content)
                
                # Update conversation history
                conversation_history.append(HumanMessage(content=out))
                if stream:
                    # For streaming, we need to collect the full response
                    full_response = ""
                    for chunk in model.stream(messages):
                        if hasattr(chunk, 'content') and chunk.content:
                            full_response += chunk.content
                    conversation_history.append(AIMessage(content=full_response))
                else:
                    # Include AI/tool messages produced during this turn
                    conversation_history.extend(produced_messages)
                
                # Call history callback with new messages
                if history_callback:
                    # Find the last HumanMessage and the last AIMessage, ignoring tool messages
                    last_user = None
                    last_ai = None
                    for msg in reversed(conversation_history):
                        if last_ai is None and isinstance(msg, AIMessage):
                            last_ai = msg
                        elif last_user is None and isinstance(msg, HumanMessage):
                            last_user = msg
                        if last_user and last_ai:
                            break
                    new_responses = []
                    if last_user is not None:
                        new_responses.append({
                            "id": str(uuid.uuid4()).replace("-", "")[:24],
                            "role": "user",
                            "content": [{"text": last_user.content, "type": "text"}],
                        })
                    if last_ai is not None:
                        new_responses.append({
                            "id": str(uuid.uuid4()).replace("-", "")[:24],
                            "role": "assistant",
                            "content": [{"text": last_ai.content, "type": "text"}],
                        })
                    if new_responses:
                        history_callback(new_responses)

            ui.print("")  # Add extra newline after bot response
    except KeyboardInterrupt:
        ui.print("")  # Add newlines
        ui.print("[cyan]Thanks for using Bespoken. Goodbye![/cyan]")
        ui.print("")  # Add final newline


def main():
    """Main entry point for the bespoken CLI."""
    typer.run(chat)


if __name__ == "__main__":
    main()
