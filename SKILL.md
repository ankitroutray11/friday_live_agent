---
name: friday-live-agent
description: Launch and configure F.R.I.D.A.Y., a real-time bidirectional Gemini 3.8 Live API voice pair programmer with mid-speech interruption and local workspace tools. Use when the user wants to start, set up, or pair-program by voice using friday_live_agent.
---

# F.R.I.D.A.Y. Live Voice Pair Programmer

Launches the local `friday_agent.py` real-time voice runtime powered by `gemini-3.8-live` so the user can speak naturally to inspect files, edit code, and run commands hands-free.

## Prerequisites

- **Python 3.10+**
- **Microphone & Speakers/Headset** (headset recommended to avoid acoustic echo)
- **`GEMINI_API_KEY`** environment variable (or `.env` file)

## Setup & Launch Workflow

1. **Locate the skill directory** (the directory containing this `SKILL.md` and `friday_agent.py`).
2. **Check Python and dependencies**:
   - Check if `google-genai`, `sounddevice`, `python-dotenv`, and `psutil` are installed in the active Python environment (or create a `.venv` inside the skill directory).
   - If missing, install them:
     ```bash
     pip install -r requirements.txt
     ```
     *(On Linux, `sounddevice` may also require `libportaudio2` via the system package manager.)*
3. **Verify `GEMINI_API_KEY`**:
   - Check if `GEMINI_API_KEY` is set in the environment or in `<workspace>/.env` / `<skill-dir>/.env`.
   - If not set, ask the user to provide or export `GEMINI_API_KEY` before launching. Never hardcode or commit API keys.
4. **Launch `friday_agent.py` targeting the user's workspace**:
   - Set `FRIDAY_WORKSPACE` to the user's current project directory so voice file tools stay scoped to their active repo.
   - Start `friday_agent.py` in an interactive terminal window (it requires live microphone/speaker access and `Ctrl+C` to stop):
     - **Windows (PowerShell):**
       ```powershell
       $env:FRIDAY_WORKSPACE = (Get-Location).Path
       python "<skill-dir>/friday_agent.py"
       ```
     - **macOS / Linux:**
       ```bash
       FRIDAY_WORKSPACE="$(pwd)" python "<skill-dir>/friday_agent.py"
       ```

## Built-in Voice Tools

Once online (`✦ F.R.I.D.A.Y. IS ONLINE AND LISTENING`), the user can speak naturally and interrupt mid-sentence:
- **Code & Files:** `read_file`, `write_file`, `edit_file`, `list_directory`, `search_files` (scoped to `FRIDAY_WORKSPACE` unless `FRIDAY_ALLOW_OUTSIDE_WORKSPACE=1`)
- **Shell & System:** `run_command` (blocks destructive patterns), `system_diagnostics`, `open_app_or_url`
