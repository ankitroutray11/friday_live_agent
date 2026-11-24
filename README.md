# F.R.I.D.A.Y. Native Gemini 3.8 Live Voice Agent

A real-time, bidirectional voice-driven AI pair programmer and desktop assistant powered by the official **Gemini 3.8 Live API** (`gemini-3.8-live`).

---

## What Makes This Different From Chat
- **No Typing / No Waiting**: You speak naturally into your microphone. Friday speaks back through your speakers/headphones with sub-second latency.
- **Natural Voice Interruption**: If Friday is speaking and you interrupt her (*"Wait Friday, stop that and check main.py instead"*), she cuts audio playback immediately and listens to your new directive.
- **Full Autonomous Agent Tools**: Whatever can be done in an AI chat can be done hands-free by speaking:
  - `run_command`: Runs PowerShell commands (`git status`, `python test.py`, `npm run build`, etc.)
  - `read_file`: Inspects files and code ranges on disk.
  - `write_file` / `edit_file`: Generates or edits code files.
  - `list_directory` / `search_files`: Explores project files and greps code patterns.
  - `system_diagnostics`: Reads live CPU, RAM, and battery metrics.
  - `open_app_or_url`: Launches VS Code, Chrome, Terminal, Calculator, etc.

---

## Quick Start

### 1. Launch with One Click
Double-click `friday.bat` in the project root directory.

Or run from any terminal:
```bash
python friday_agent.py
```

### 2. Audio Configuration
- **Microphone**: 16,000 Hz, 16-bit Mono PCM
- **Speaker**: 24,000 Hz, 16-bit Mono PCM
- **Persona Voice**: `Aoede` (Crisp, tactical feminine AI)

*(Tip: For optimal voice recognition without acoustic feedback, using headphones or a headset is recommended).*

---

## Example Conversational Voice Commands

- *"Friday, give me a status report on the suit and system diagnostics."*
- *"Friday, check the git status in this repository."*
- *"Friday, read lines 1 to 50 of main.py and tell me what the entrypoint does."*
- *"Friday, search for where the ai_router is initialized."*
- *"Friday, open VS Code."*
- *"Friday, run python tests and tell me if everything passes."*
