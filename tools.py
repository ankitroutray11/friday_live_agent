import os
import sys
import glob
import psutil
import subprocess
import webbrowser
from typing import Optional, List, Dict, Any

import re

# Current working directory default (configurable via FRIDAY_WORKSPACE)
DEFAULT_WORKSPACE = os.path.abspath(os.getenv("FRIDAY_WORKSPACE") or os.getcwd())

_BLOCKED_CMD_PATTERNS = [
    re.compile(r"\bformat\s+[a-z]:", re.I),
    re.compile(r"\brm\s+-rf\s+/", re.I),
    re.compile(r"\bdel\s+/[sqf]+\s+[a-z]:\\", re.I),
    re.compile(r"\bshutdown\b", re.I),
    re.compile(r"\breg\s+delete\b", re.I),
]

def _resolve_safe_path(path: str) -> str:
    """Resolves a path and enforces workspace boundary unless FRIDAY_ALLOW_OUTSIDE_WORKSPACE=1."""
    base = os.path.abspath(DEFAULT_WORKSPACE)
    candidate = path if os.path.isabs(path) else os.path.join(base, path)
    resolved = os.path.abspath(candidate)
    if os.getenv("FRIDAY_ALLOW_OUTSIDE_WORKSPACE") != "1":
        if os.path.commonpath([base, resolved]) != base:
            raise PermissionError(f"Access denied: '{path}' is outside workspace '{base}'.")
    return resolved

def run_command(command: str) -> str:
    """Executes a PowerShell or shell command on the host Windows machine and returns terminal output.
    
    Args:
        command: The shell command line to execute (e.g. 'git status', 'python --version', 'dir', 'npm test').
    """
    for pat in _BLOCKED_CMD_PATTERNS:
        if pat.search(command):
            return f"Error: Command blocked by safety policy: '{command}'."
    print(f"\n⚡ [Tool Execution] Executing: {command}")
    try:
        shell_cmd = (
            ["powershell", "-NoProfile", "-Command", command]
            if sys.platform == "win32"
            else ["sh", "-c", command]
        )
        res = subprocess.run(
            shell_cmd,
            capture_output=True,
            text=True,
            timeout=30.0
        )
        stdout = res.stdout.strip()
        stderr = res.stderr.strip()
        out = []
        if stdout:
            out.append(f"STDOUT:\n{stdout[:2000]}")
        if stderr:
            out.append(f"STDERR:\n{stderr[:1000]}")
        if not out:
            out.append("(Command executed successfully with no output)")
        out.append(f"[Exit code: {res.returncode}]")
        summary = "\n".join(out)
        print(f"✓ [Result]: {stdout[:200] if stdout else 'Success'}")
        return summary
    except subprocess.TimeoutExpired:
        return f"Error: Command '{command}' timed out after 30 seconds."
    except Exception as e:
        return f"Error executing command '{command}': {e}"

def read_file(path: str, start_line: Optional[int] = None, end_line: Optional[int] = None) -> str:
    """Reads file contents from disk within the workspace or file system.
    
    Args:
        path: Path to the file to inspect.
        start_line: Optional 1-based start line number.
        end_line: Optional 1-based end line number.
    """
    print(f"\n📖 [Tool Execution] Reading file: {path}")
    try:
        p = _resolve_safe_path(path)
        if not os.path.exists(p):
            return f"Error: File '{path}' does not exist on disk."
        with open(p, "r", encoding="utf-8", errors="replace") as f:
            lines = f.readlines()
        
        s = max(1, start_line or 1) - 1
        e = min(len(lines), end_line or len(lines))
        selected = lines[s:e]
        if len(selected) > 200:
            content = "".join(selected[:200]) + f"\n... [Truncated {len(selected)-200} lines]"
        else:
            content = "".join(selected)
        return f"=== File: {path} (lines {s+1}-{e} of {len(lines)}) ===\n{content}"
    except Exception as e:
        return f"Error reading file '{path}': {e}"

def write_file(path: str, content: str) -> str:
    """Creates a new file or overwrites an existing file with the given content.
    
    Args:
        path: Path to the file to write.
        content: The text content to write into the file.
    """
    print(f"\n✏️ [Tool Execution] Writing file: {path} ({len(content)} chars)")
    try:
        p = _resolve_safe_path(path)
        parent = os.path.dirname(p)
        if parent:
            os.makedirs(parent, exist_ok=True)
        with open(p, "w", encoding="utf-8") as f:
            f.write(content)
        return f"Successfully saved {len(content)} characters to '{path}'."
    except Exception as e:
        return f"Error writing file '{path}': {e}"

def edit_file(path: str, target: str, replacement: str) -> str:
    """Performs an exact string replacement inside an existing file.
    
    Args:
        path: Path to the file to modify.
        target: The exact text sequence to be replaced.
        replacement: The replacement text.
    """
    print(f"\n🔧 [Tool Execution] Editing file: {path}")
    try:
        p = _resolve_safe_path(path)
        if not os.path.exists(p):
            return f"Error: File '{path}' does not exist."
        with open(p, "r", encoding="utf-8", errors="replace") as f:
            content = f.read()
        if target not in content:
            return f"Error: Target text not found in '{path}'."
        updated = content.replace(target, replacement, 1)
        with open(p, "w", encoding="utf-8") as f:
            f.write(updated)
        return f"Successfully updated '{path}'."
    except Exception as e:
        return f"Error editing file '{path}': {e}"

def list_directory(path: Optional[str] = ".") -> str:
    """Lists files and folders inside the specified directory.
    
    Args:
        path: Directory path to list (defaults to current directory).
    """
    target = path or "."
    print(f"\n📁 [Tool Execution] Listing directory: {target}")
    try:
        p = _resolve_safe_path(target)
        if not os.path.exists(p):
            return f"Error: Directory '{target}' does not exist."
        entries = sorted(os.listdir(p))
        items = []
        for item in entries[:50]:
            fp = os.path.join(p, item)
            is_d = os.path.isdir(fp)
            size = os.path.getsize(fp) if not is_d else 0
            items.append(f"  [{'DIR ' if is_d else 'FILE'}] {item:<30} {'<DIR>' if is_d else f'{size}B'}")
        return f"Directory listing of '{target}' ({len(entries)} items total):\n" + "\n".join(items)
    except Exception as e:
        return f"Error listing directory '{target}': {e}"

def search_files(query: str, path: Optional[str] = ".") -> str:
    """Searches for a text pattern inside files within the specified directory.
    
    Args:
        query: Text substring to find.
        path: Root directory to search within.
    """
    root = os.path.abspath(path or ".")
    print(f"\n🔍 [Tool Execution] Searching for '{query}' in {root}")
    matches = []
    try:
        for dirpath, _, filenames in os.walk(root):
            if any(skip in dirpath for skip in [".git", "__pycache__", "node_modules", ".venv"]):
                continue
            for f in filenames:
                fp = os.path.join(dirpath, f)
                try:
                    with open(fp, "r", encoding="utf-8", errors="ignore") as file:
                        for idx, line in enumerate(file, 1):
                            if query.lower() in line.lower():
                                rel = os.path.relpath(fp, root)
                                matches.append(f"{rel}:{idx}: {line.strip()[:120]}")
                                if len(matches) >= 25:
                                    break
                except Exception:
                    pass
                if len(matches) >= 25:
                    break
        if not matches:
            return f"No matches found for '{query}' in '{root}'."
        return f"Found {len(matches)} match(es):\n" + "\n".join(matches)
    except Exception as e:
        return f"Error searching files: {e}"

def system_diagnostics() -> str:
    """Returns current host hardware diagnostics (CPU, RAM, Battery, OS)."""
    print("\n📊 [Tool Execution] Querying system diagnostics")
    try:
        cpu_pct = psutil.cpu_percent(interval=0.2)
        ram = psutil.virtual_memory()
        battery = psutil.sensors_battery()
        bat_str = f"{battery.percent}% ({'Charging' if battery.power_plugged else 'Discharging'})" if battery else "Desktop (AC)"
        return (
            f"System Hardware Diagnostics:\n"
            f"- CPU Utilization: {cpu_pct}%\n"
            f"- RAM Usage: {ram.percent}% ({ram.used // (1024**2)} MB / {ram.total // (1024**2)} MB)\n"
            f"- Power Status: {bat_str}\n"
            f"- OS: Windows ({sys.platform})"
        )
    except Exception as e:
        return f"Error getting diagnostics: {e}"

def open_app_or_url(target: str) -> str:
    """Launches a desktop application or opens a website URL in the default browser.
    
    Args:
        target: Application alias ('chrome', 'vscode', 'terminal', 'calculator', 'notepad', 'spotify') or URL ('https://...').
    """
    print(f"\n🚀 [Tool Execution] Opening: {target}")
    target_lower = target.lower().strip()
    apps = {
        "chrome": "start chrome",
        "browser": "start chrome",
        "vscode": "code",
        "code": "code",
        "terminal": "start powershell",
        "calculator": "calc",
        "calc": "calc",
        "notepad": "notepad",
        "spotify": "start spotify",
        "explorer": "explorer ."
    }
    try:
        if target_lower.startswith("http://") or target_lower.startswith("https://"):
            webbrowser.open(target)
            return f"Opened URL '{target}' in default browser."
        elif target_lower in apps:
            subprocess.Popen(apps[target_lower], shell=True)
            return f"Launched application: {target}."
        else:
            # Try generic start
            subprocess.Popen(f"start {target}", shell=True)
            return f"Executed launch for: {target}."
    except Exception as e:
        return f"Error opening '{target}': {e}"

ALL_TOOLS = [
    run_command,
    read_file,
    write_file,
    edit_file,
    list_directory,
    search_files,
    system_diagnostics,
    open_app_or_url,
]

TOOL_MAP = {func.__name__: func for func in ALL_TOOLS}
