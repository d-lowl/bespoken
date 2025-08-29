from pathlib import Path
import json

from bespoken import chat
from bespoken.tools.filesystem import FileTool
from bespoken.tools.todo import TodoTools
from bespoken.prompts import marimo_prompt
from bespoken import ui
from bespoken import config
from langchain_ollama import ChatOllama

def set_role():
    """Set a role for the assistant"""
    roles = ["developer", "teacher", "analyst", "creative writer", "code reviewer"]
    role = ui.choice("What role should I take?", roles)
    return f"You are now acting as a {role}. Please respond in character for this role."


def debug_reason():
    """Set a role for the assistant"""
    ui.tool_status("We are going to prompt the LLM to see if they can find the bug in the code on their own.")
    entrypoint = ui.input("What is the entrypoint for the user?")
    action = ui.input("What is the action the user is trying to take?")
    out = f"""You've introduced a new bug, but instead of me telling you what the bug is, let's see if you can find it for yourself. Imagine that you are a user and that you start by {entrypoint}. Go through all the steps that would happen if a user tries to {action}. Think through all the steps and see if you can spot something that could go wrong. Don't write any code, but let's see if we both find the same issue."""
    print("")
    ui.print_neutral(out)
    return out


# Initialize the Ollama chat model with the specified Qwen3-Coder model
model = ChatOllama(
    model="hf.co/unsloth/Qwen3-Coder-30B-A3B-Instruct-GGUF:UD-Q4_K_XL",
    temperature=0.7,
)

# Create tools list
tools = []
# Add file-specific tools
tools.append(FileTool("edit.py"))
# Add general file system tools
# tools.extend([list_files, read_file, write_file, replace_in_file])
# Add todo tools
tools.append(TodoTools())

chat(
    model=model,  # Pass the model instance instead of a string
    tools=tools,
    system_prompt=marimo_prompt,
    debug=True,
    stream=False,
    slash_commands={
        "/thinking": "Let me think through this step by step:",
        "/role": set_role,
        "/debug_prompt": debug_reason,
    },
)
