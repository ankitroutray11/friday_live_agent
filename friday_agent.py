import os
import sys
import time
import queue
import signal
import asyncio
import logging
import threading
import sounddevice as sd
from pathlib import Path
from dotenv import load_dotenv

# Force UTF-8 encoding on Windows console
if sys.platform == "win32":
    try:
        sys.stdout.reconfigure(encoding="utf-8", errors="replace")
        sys.stderr.reconfigure(encoding="utf-8", errors="replace")
    except Exception:
        pass

# Prioritize IPv4 resolution to prevent Windows dual-stack IPv6 socket stalls with Google APIs
import socket
_orig_getaddrinfo = socket.getaddrinfo
def _ipv4_getaddrinfo(*args, **kwargs):
    res = _orig_getaddrinfo(*args, **kwargs)
    ipv4 = [r for r in res if r[0] == socket.AF_INET]
    return ipv4 if ipv4 else res
socket.getaddrinfo = _ipv4_getaddrinfo

# Load environment credentials
ENV_PATHS = [
    Path(".env"),
    Path(__file__).parent / ".env",
]
for p in ENV_PATHS:
    if p.exists():
        load_dotenv(p, override=False)
        break

from google import genai
from google.genai import types

# Import Host Operating System & Workspace Tools
sys.path.insert(0, str(Path(__file__).parent))
from tools import ALL_TOOLS, TOOL_MAP

# Setup logging
logging.basicConfig(level=logging.WARNING, format="%(asctime)s [%(levelname)s] %(message)s")
logger = logging.getLogger("FridayLive")

# Banner
BANNER = r"""
  ______ _____  _____ _____            __     __
 |  ____|  __ \|_   _|  __ \   /\      \ \   / /
 | |__  | |__) | | | | |  | | /  \      \ \_/ / 
 |  __| |  _  /  | | | |  | |/ /\ \      \   /  
 | |    | | \ \ _| |_| |__| / ____ \      | |   
 |_|    |_|  \_\_____|_____/_/    \_\     |_|   
 ------------------------------------------------
    F.R.I.D.A.Y. MARK LXXXV // GEMINI 3.8 LIVE
    Autonomous Real-Time Voice Agent & Pair Programmer
 ------------------------------------------------
"""

class FridayLiveVoiceAgent:
    def __init__(self, api_key: str):
        self.api_key = api_key
        self.client = genai.Client(api_key=self.api_key)
        
        # Audio Streaming Queues
        self.audio_in_queue = asyncio.Queue()
        self.audio_out_queue = queue.Queue()
        
        # State & Events
        self.running = threading.Event()
        self.running.set()
        self.interrupt_event = threading.Event()
        self.loop = None
        self.is_speaking = False

    def _audio_playback_worker(self):
        """Dedicated thread playing incoming 24kHz PCM audio chunks to speakers with zero latency."""
        try:
            with sd.RawOutputStream(samplerate=24000, channels=1, dtype='int16') as stream:
                while self.running.is_set():
                    # If user interrupted, immediately discard remaining queued audio chunks
                    if self.interrupt_event.is_set():
                        while not self.audio_out_queue.empty():
                            try:
                                self.audio_out_queue.get_nowait()
                            except queue.Empty:
                                break
                        self.interrupt_event.clear()
                        self.is_speaking = False
                    
                    try:
                        chunk = self.audio_out_queue.get(timeout=0.03)
                        if chunk and not self.interrupt_event.is_set():
                            self.is_speaking = True
                            stream.write(chunk)
                        else:
                            self.is_speaking = False
                    except queue.Empty:
                        self.is_speaking = False
                        continue
        except Exception as e:
            logger.error(f"Audio output worker exception: {e}")

    def _mic_input_callback(self, indata, frames, time_info, status):
        """Captures 16kHz raw PCM microphone audio and enqueues to async sender."""
        if not self.running.is_set():
            return
        if self.loop and self.loop.is_running():
            try:
                self.loop.call_soon_threadsafe(self.audio_in_queue.put_nowait, bytes(indata))
            except Exception:
                pass

    async def _send_audio_loop(self, session):
        """Continuously streams raw microphone PCM audio to Gemini 3.8 Live."""
        while self.running.is_set():
            try:
                chunk = await self.audio_in_queue.get()
                await session.send_realtime_input(
                    audio=types.Blob(data=chunk, mime_type="audio/pcm;rate=16000")
                )
            except asyncio.CancelledError:
                break
            except Exception as e:
                logger.error(f"Error in send_audio_loop: {e}")
                await asyncio.sleep(0.01)

    async def _receive_loop(self, session):
        """Receives audio chunks, transcriptions, and executes autonomous tools."""
        try:
            async for response in session.receive():
                if not self.running.is_set():
                    break
                
                server_content = response.server_content
                if server_content:
                    # User interrupted mid-generation
                    if server_content.interrupted:
                        print("\n⚡ [F.R.I.D.A.Y.]: (Interrupted)")
                        self.interrupt_event.set()

                    # Spoken audio transcription from Friday
                    if server_content.output_transcription and server_content.output_transcription.text:
                        sys.stdout.write(f"\r✦ [F.R.I.D.A.Y.]: {server_content.output_transcription.text}\n")
                        sys.stdout.flush()

                    # Input transcription from Boss (User)
                    if server_content.input_transcription and server_content.input_transcription.text:
                        sys.stdout.write(f"\r🎤 [Boss]: {server_content.input_transcription.text}\n")
                        sys.stdout.flush()

                    # Queue audio playback to speakers
                    if server_content.model_turn:
                        for part in server_content.model_turn.parts:
                            if part.inline_data and part.inline_data.data:
                                self.audio_out_queue.put(part.inline_data.data)

                # Autonomous Agent Tool Calling
                if response.tool_call:
                    for fc in response.tool_call.function_calls:
                        tool_name = fc.name
                        tool_args = fc.args or {}
                        print(f"\n⚙️ [F.R.I.D.A.Y. Action]: Invoking {tool_name}({tool_args})")
                        
                        func = TOOL_MAP.get(tool_name)
                        if func:
                            try:
                                # Run tool in worker thread to prevent blocking async audio loop
                                result = await asyncio.to_thread(func, **tool_args)
                            except Exception as err:
                                result = f"Tool execution failed: {err}"
                        else:
                            result = f"Error: Tool '{tool_name}' is not recognized."

                        # Send tool output back to Gemini Live
                        await session.send_tool_response(
                            function_responses=[
                                types.FunctionResponse(
                                    id=fc.id,
                                    name=fc.name,
                                    response={"result": str(result)}
                                )
                            ]
                        )
                        print(f"✓ [Action Completed]: Results delivered to neural stream.")

        except asyncio.CancelledError:
            pass
        except Exception as e:
            logger.error(f"Error in receive_loop: {e}")

    async def start(self):
        self.loop = asyncio.get_running_loop()
        
        # Start background speaker playback thread
        playback_thread = threading.Thread(target=self._audio_playback_worker, daemon=True)
        playback_thread.start()

        # Friday System Instruction & Persona
        system_instruction = (
            "You are F.R.I.D.A.Y., Tony Stark's personal tactical AI assistant and expert pair programmer, running natively on this computer. "
            "You are speaking in real-time with the user ('Boss'). "
            "Keep your spoken answers crisp, natural, intelligent, and concise (typically 1-2 conversational sentences) "
            "so they sound like natural spoken dialogue without long pauses. "
            "You have full autonomous access to host tools: "
            "1. run_command: Executes PowerShell commands, scripts, builds, git, tests. "
            "2. read_file / write_file / edit_file: Inspects and modifies code on disk. "
            "3. list_directory / search_files: Explores workspace files and finds code symbols. "
            "4. system_diagnostics: Checks CPU, RAM, and hardware health. "
            "5. open_app_or_url: Launches apps (VS Code, Chrome, Terminal, etc.) or websites. "
            "When the user asks you to do a task (e.g., 'check git status', 'list files in src', 'run the tests', 'open VS Code', 'diagnostics'), "
            "call the appropriate tool immediately. "
            "After executing a tool, summarize the outcome in a brief, clear spoken sentence. "
            "If the user interrupts you mid-sentence, yield immediately and address their latest command."
        )

        config = types.LiveConnectConfig(
            response_modalities=[types.Modality.AUDIO],
            speech_config=types.SpeechConfig(
                voice_config=types.VoiceConfig(
                    prebuilt_voice_config=types.PrebuiltVoiceConfig(voice_name="Aoede")
                )
            ),
            system_instruction=types.Content(
                parts=[types.Part(text=system_instruction)]
            ),
            tools=ALL_TOOLS,
            input_audio_transcription=types.AudioTranscriptionConfig(),
            output_audio_transcription=types.AudioTranscriptionConfig(),
        )

        print(BANNER)
        print(" [SYSTEM] Initializing audio hardware...")
        print(" [SYSTEM] Mic Input: 16,000 Hz Raw PCM (Mono)")
        print(" [SYSTEM] Speaker Output: 24,000 Hz Raw PCM (Mono)")
        print(" [SYSTEM] Persona Voice: Aoede (F.R.I.D.A.Y. Tactical)")
        print(" [SYSTEM] Tool Suite: PowerShell Execution, Code Editor, File Reader, App Launcher")
        print(" [SYSTEM] Connecting to Gemini 3.8 Live Neural Stream...")

        # Open Microphone Hardware Stream
        with sd.RawInputStream(samplerate=16000, channels=1, dtype='int16', blocksize=1024, callback=self._mic_input_callback):
            while self.running.is_set():
                try:
                    async with self.client.aio.live.connect(model="gemini-3.8-live", config=config) as session:
                        print("\n========================================================")
                        print(" ✦ F.R.I.D.A.Y. IS ONLINE AND LISTENING")
                        print(" Speak naturally into your microphone.")
                        print(" Press Ctrl+C at any time to exit.")
                        print("========================================================\n")

                        # Send an initial conversational greeting prompt to initialize the voice link
                        await session.send_realtime_input(
                            text="Say a brief, one-sentence greeting to Boss stating that Friday is online and all systems are ready for directives."
                        )

                        send_task = asyncio.create_task(self._send_audio_loop(session))
                        receive_task = asyncio.create_task(self._receive_loop(session))

                        done, pending = await asyncio.wait(
                            [send_task, receive_task],
                            return_when=asyncio.FIRST_COMPLETED
                        )
                        for task in pending:
                            task.cancel()

                except (KeyboardInterrupt, asyncio.CancelledError):
                    print("\n[SYSTEM] Shutting down F.R.I.D.A.Y....")
                    break
                except Exception as e:
                    print(f"\n[SYSTEM] Connection notice: {e}")
                    print("[SYSTEM] Reconnecting in 3 seconds...")
                    await asyncio.sleep(3)

        self.running.clear()
        print(" [SYSTEM] F.R.I.D.A.Y. offline.")

def main():
    api_key = os.getenv("GEMINI_API_KEY")
    if not api_key:
        print("Error: GEMINI_API_KEY environment variable not found.")
        print("Please set your GEMINI_API_KEY in .env or your environment variables.")
        sys.exit(1)

    agent = FridayLiveVoiceAgent(api_key=api_key)
    
    # Graceful exit handler
    def handle_sigint(sig, frame):
        agent.running.clear()
        print("\nStopping agent...")
        sys.exit(0)

    signal.signal(signal.SIGINT, handle_sigint)

    try:
        asyncio.run(agent.start())
    except KeyboardInterrupt:
        pass

if __name__ == "__main__":
    main()
