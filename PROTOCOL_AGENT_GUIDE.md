# LiveKit Multi-Participant Protocol Agent Guide

**Complete guide for creating a speech-to-text protocol recorder for LiveKit rooms**

This guide will help you set up an automated agent that joins your LiveKit room, transcribes what each participant says, and creates a detailed meeting protocol showing who said what and when.

---

## 🚀 Quickstart (TL;DR)

Schnellstart in 5 Minuten:

```bash
# 1. In das Verzeichnis wechseln
cd /home/anton/livekit/agents

# 2. Virtual Environment aktivieren
source venv/bin/activate

# 3. Agent im Dev-Modus starten (Terminal 1)
python protocol_agent.py dev

# 4. Warten bis "registered worker" erscheint

# 5. In einem ZWEITEN Terminal: Agent zum Raum dispatchen
cd /home/anton/livekit/agents
source venv/bin/activate
python dispatch_agent.py --list                    # Zeigt aktive Räume
python dispatch_agent.py <ROOM_NAME>               # Agent zu Raum schicken

# 6. Sprechen! Transkripte erscheinen in:
#    - Terminal 1 (live)
#    - protocols/ Ordner (Dateien)

# 7. Agent beenden: Ctrl+C in Terminal 1
```

### Agent Starten

```bash
# Development Mode (mit Hot-Reload bei Code-Änderungen)
python protocol_agent.py dev

# Production Mode
python protocol_agent.py start

# Mit Debug-Logging (zeigt Audio-Track-Details)
DEBUG=true python protocol_agent.py dev
```

### Agent zu Raum dispatchen

Der Agent wartet nach dem Start auf Jobs. Bei existierenden Räumen muss der Agent **manuell dispatched** werden:

```bash
# Alle aktiven Räume anzeigen
python dispatch_agent.py --list

# Agent zu einem bestimmten Raum schicken
python dispatch_agent.py QPmsMhXT7HTnBgSYbJEHqyCyQtyTWjng
```

**Woher bekomme ich den Raumnamen?**

| Methode | Beschreibung |
|---------|--------------|
| `dispatch_agent.py --list` | Zeigt alle aktiven Räume |
| Browser-Console | Suche nach `room: 'XXXXX'` in LiveKit-Logs |
| LiveKit Dashboard | https://cloud.livekit.io → Rooms |

### Agent Beenden

```bash
# Option 1: Ctrl+C im Terminal
# -> Agent beendet sich graceful, speichert Statistiken

# Option 2: Bei mehreren laufenden Prozessen
pkill -f "protocol_agent.py"

# Option 3: Process-ID finden und beenden
ps aux | grep protocol_agent
kill <PID>
```

### Protokoll-Dateien anschauen

```bash
# Neueste Protokolle anzeigen
ls -lt protocols/

# Letztes Protokoll lesen
cat protocols/protocol_*.txt | tail -100

# Live-Protokoll verfolgen
tail -f protocols/protocol_*.txt
```

---

## Table of Contents

1. [Quickstart](#-quickstart-tldr)
2. [Overview](#overview)
3. [Features](#features)
4. [Prerequisites](#prerequisites)
5. [Setup Instructions](#setup-instructions)
6. [Configuration](#configuration)
7. [Running the Agent](#running-the-agent)
8. [Output Formats](#output-formats)
9. [How It Works](#how-it-works)
10. [Real-Time Text Output](#real-time-text-output)
11. [Troubleshooting](#troubleshooting)
12. [Advanced Features](#advanced-features)
13. [API Reference](#api-reference)

---

## Overview

### What This Agent Does

The Protocol Agent is a LiveKit agent that:
- Joins a LiveKit room automatically
- Listens to all participants (up to 20+)
- Transcribes speech to text in real-time using AI
- Records who said what with timestamps
- Saves everything to multiple output formats (TXT, JSON)
- Provides meeting statistics (word count, turns per participant)
- Supports real-time text output (live captions)
- Does NOT speak or interrupt (transcription-only mode)

### Use Cases

- Meeting transcription and minutes
- Interview recordings
- Conference call documentation
- Educational sessions
- Customer support call logging
- Legal depositions
- Medical consultations

---

## Features

### Core Features
- **Multi-participant transcription** - Handles multiple speakers simultaneously
- **Real-time processing** - Transcripts appear as people speak
- **Multiple STT providers** - Deepgram, Speechmatics, or OpenAI
- **Multi-language support** - German, English, or auto-detect
- **Dual output formats** - TXT for reading, JSONL for parsing

### Technical Features
- **Thread-safe writing** - Mutex locks prevent race conditions
- **Error handling** - Recoverable and unrecoverable error callbacks
- **Graceful shutdown** - All data saved on exit
- **Session management** - Per-participant session handling
- **Idle timeout** - Auto-pause when no speech (saves API credits)
- **Auto-resume** - Sessions restart when speech detected again

### Analytics Features
- **Conversation statistics** - Word count, turn count per participant
- **Participant tracking** - Join/leave times recorded
- **Statistics export** - Separate JSON stats file
- **Deepgram usage tracking** - Check API credits with included script

---

## Prerequisites

### Required Accounts & API Keys

1. **LiveKit Account**
   - Sign up at https://cloud.livekit.io
   - Create a new project
   - Get your API credentials (URL, API Key, API Secret)

2. **Speech-to-Text Provider** (choose one):

   | Provider | Sign Up | Free Tier |
   |----------|---------|-----------|
   | **Deepgram** (default) | https://console.deepgram.com/ | 12,000 minutes |
   | **Speechmatics** | https://portal.speechmatics.com/ | 8 hours |
   | **OpenAI** | https://platform.openai.com/ | Pay-as-you-go |

### System Requirements

- **Python**: 3.9 or higher
- **Operating System**: macOS, Linux, or Windows
- **RAM**: 2GB minimum (for VAD model)
- **Internet Connection**: Required for API calls

---

## Setup Instructions

### Step 1: Navigate to the Repository

```bash
cd /home/anton/livekit/agents
```

### Step 2: Create a Virtual Environment

```bash
# Create virtual environment
python3 -m venv venv

# Activate it
# On Linux/macOS:
source venv/bin/activate

# On Windows:
venv\Scripts\activate
```

### Step 3: Install Dependencies

```bash
# Core dependencies
pip install livekit-agents livekit-plugins-silero python-dotenv aiofiles

# STT Provider (choose one or more):
pip install livekit-plugins-deepgram      # Deepgram (recommended)
pip install livekit-plugins-speechmatics  # Speechmatics
pip install livekit-plugins-openai        # OpenAI Whisper

# Install all at once:
pip install livekit-agents livekit-plugins-deepgram livekit-plugins-silero python-dotenv aiofiles
```

### Step 4: Configure Environment Variables

Copy the template and edit with your credentials:

```bash
cp .env.protocol .env
nano .env  # or use your preferred editor
```

Your `.env` file should contain:

```bash
# LiveKit Configuration (required)
LIVEKIT_URL="wss://your-project.livekit.cloud"
LIVEKIT_API_KEY="APIxxxxxxxxxxxxx"
LIVEKIT_API_SECRET="your_secret_here"

# STT Provider API Key (based on your choice)
DEEPGRAM_API_KEY="your_deepgram_api_key"
# SPEECHMATICS_API_KEY="your_speechmatics_api_key"
# OPENAI_API_KEY="your_openai_api_key"

# Agent Configuration
STT_PROVIDER="deepgram"           # deepgram, speechmatics, or openai
STT_LANGUAGE="multi"              # de=Deutsch, en=English, multi=Auto-Detect
OUTPUT_FORMAT="both"              # txt, json, or both
PROTOCOLS_DIR="protocols"         # Output directory
ENABLE_STATISTICS="true"          # Enable statistics tracking
IDLE_TIMEOUT_MINUTES="5"          # Auto-pause after X minutes silence (0=disabled)
```

### Step 5: Download Model Files

```bash
python protocol_agent.py download-files
```

This downloads the Silero VAD model for voice activity detection.

---

## Configuration

### Environment Variables

| Variable | Default | Description |
|----------|---------|-------------|
| `LIVEKIT_URL` | (required) | LiveKit server WebSocket URL |
| `LIVEKIT_API_KEY` | (required) | LiveKit API key |
| `LIVEKIT_API_SECRET` | (required) | LiveKit API secret |
| `DEEPGRAM_API_KEY` | (required) | Deepgram API key |
| `STT_PROVIDER` | `deepgram` | Speech-to-text provider |
| `STT_LANGUAGE` | `de` | Language: `de`, `en`, or `multi` (auto-detect) |
| `OUTPUT_FORMAT` | `both` | Output format: `txt`, `json`, or `both` |
| `PROTOCOLS_DIR` | `protocols` | Directory for output files |
| `ENABLE_STATISTICS` | `true` | Enable statistics tracking |
| `IDLE_TIMEOUT_MINUTES` | `5` | Auto-pause after X minutes of silence (0=disabled) |
| `DEBUG` | `false` | Enable debug logging |

### Language Settings

| Wert | Sprache | Qualität | Empfohlen für |
|------|---------|----------|---------------|
| `de` | Nur Deutsch | ⭐⭐⭐⭐⭐ | Rein deutsche Sessions |
| `en` | Nur Englisch | ⭐⭐⭐⭐⭐ | Rein englische Sessions |
| `multi` | Auto-Erkennung | ⭐⭐⭐⭐ | Gemischte Sprachen |

```bash
# In .env
STT_LANGUAGE="multi"   # Für deutsch/englisch gemischt
```

### STT Provider Comparison

| Feature | Deepgram | Speechmatics | OpenAI |
|---------|----------|--------------|--------|
| **Languages** | 30+ | 55+ | 50+ |
| **Model Used** | Nova-3 | Enhanced | Whisper |
| **Accuracy** | Excellent | Excellent | Very Good |
| **Speed** | Very Fast | Very Fast | Fast |
| **Diarization** | Yes | Yes (built-in) | No |
| **Custom Vocab** | Yes | Yes | No |
| **Free Tier** | 12,000 min | 8 hours | None |
| **Best For** | General use | Multi-language | Simple setup |

### Switching STT Providers

Simply change the environment variable:

```bash
# Use Deepgram (default)
STT_PROVIDER="deepgram"

# Use Speechmatics
STT_PROVIDER="speechmatics"

# Use OpenAI
STT_PROVIDER="openai"
```

### Idle Timeout (Kostensparend)

Der Agent pausiert automatisch wenn niemand spricht, um API-Credits zu sparen:

```bash
# In .env
IDLE_TIMEOUT_MINUTES="5"    # Pause nach 5 Minuten Stille
IDLE_TIMEOUT_MINUTES="10"   # Pause nach 10 Minuten Stille
IDLE_TIMEOUT_MINUTES="0"    # Deaktiviert (immer aktiv)
```

**Wie es funktioniert:**
- Mindestens eine Person spricht → Alle Sessions bleiben aktiv
- ALLE Teilnehmer still für X Minuten → Sessions werden pausiert
- Jemand spricht wieder → Sessions starten automatisch neu

**Im Protokoll:**
```
[20:00:00] Anton: Hallo zusammen!
[20:05:00] ⏸️  Anton session paused (idle timeout)
[20:10:00] ▶️  Anton session resumed
[20:10:05] Anton: So, weiter geht's!
```

### Deepgram Usage prüfen

Überprüfe dein verbleibendes Kontingent:

```bash
python check_deepgram_usage.py
```

**Ausgabe:**
```
Deepgram Usage Report
============================================================
Project: your-project
  Total Hours Used: 0.52
  Total Requests: 23
  Total Minutes: 31.0
============================================================
Dashboard: https://console.deepgram.com/
```

**Free Tier:** 12.000 Minuten (200 Stunden)

---

## Running the Agent

### Console Mode (Testing)

Test locally with your microphone:

```bash
python protocol_agent.py console
```

### Development Mode (Hot Reload)

Auto-reload on code changes:

```bash
python protocol_agent.py dev
```

### Production Mode

For deployment:

```bash
python protocol_agent.py start
```

### Debug Mode

Enable detailed logging to diagnose audio/STT issues:

```bash
# Via environment variable
DEBUG=true python protocol_agent.py dev

# Or add to .env file
DEBUG="true"
```

Debug mode shows:
- Audio track subscriptions
- VAD (Voice Activity Detection) events
- STT processing details
- Participant track information

### Command Line Options

```bash
python protocol_agent.py --help
```

### Stopping the Agent

**Graceful Shutdown (recommended):**
```bash
# Press Ctrl+C once in the terminal
# The agent will:
# 1. Stop accepting new connections
# 2. Finish processing current audio
# 3. Write final statistics to files
# 4. Close all sessions cleanly
```

**Force Quit (if stuck):**
```bash
# Press Ctrl+C twice quickly
# Or use:
pkill -f "protocol_agent.py"
```

**Finding Running Agents:**
```bash
# List running agent processes
ps aux | grep protocol_agent

# Kill specific process
kill <PID>

# Kill all agent processes
pkill -9 -f "protocol_agent.py"
```

---

## Output Formats

### Output Files

When the agent runs, it creates files in the `protocols/` directory:

```
protocols/
├── protocol_my-room_20250104_143022.txt      # Human-readable transcript
├── protocol_my-room_20250104_143022.jsonl    # Machine-readable transcript
└── protocol_my-room_20250104_143022_stats.json  # Meeting statistics
```

### TXT Format (Human-Readable)

```
================================================================================
Meeting Protocol - 2025-01-04 14:30:22
Room: my-meeting-room
STT Provider: deepgram
================================================================================

[14:30:25] >>> Alice joined the meeting

[14:30:28] >>> Bob joined the meeting

[14:30:35] Alice: Hello everyone, thanks for joining today's meeting.

[14:30:42] Bob: Hi Alice, happy to be here.

[14:30:45] >>> Charlie joined the meeting

[14:30:50] Charlie: Hey guys, sorry I'm a bit late.

[14:30:55] Alice: No problem Charlie. Let's get started with the agenda.

[14:31:10] Bob: I wanted to discuss the new feature proposal for the mobile app.

[14:32:10] <<< Charlie left the meeting

[14:32:45] Alice: Thanks everyone, I'll send out the meeting notes.

================================================================================
Meeting ended - 2025-01-04 14:35:10

--- Statistics ---
Total participants: 3
Total turns: 6
Total words: 52

Per participant:
  Alice: 25 words, 3 turns
  Bob: 18 words, 2 turns
  Charlie: 9 words, 1 turns
================================================================================
```

### JSONL Format (Machine-Readable)

Each line is a valid JSON object:

```json
{"type": "header", "room": "my-meeting-room", "started_at": "14:30:22", "stt_provider": "deepgram"}
{"type": "event", "timestamp": "14:30:25", "participant": "Alice", "event": "joined"}
{"type": "event", "timestamp": "14:30:28", "participant": "Bob", "event": "joined"}
{"type": "transcript", "timestamp": "14:30:35", "participant": "Alice", "text": "Hello everyone, thanks for joining today's meeting.", "word_count": 8}
{"type": "transcript", "timestamp": "14:30:42", "participant": "Bob", "text": "Hi Alice, happy to be here.", "word_count": 6}
{"type": "event", "timestamp": "14:30:45", "participant": "Charlie", "event": "joined"}
{"type": "transcript", "timestamp": "14:30:50", "participant": "Charlie", "text": "Hey guys, sorry I'm a bit late.", "word_count": 7}
{"type": "event", "timestamp": "14:32:10", "participant": "Charlie", "event": "left"}
{"type": "footer", "ended_at": "14:35:10"}
```

### Statistics JSON Format

```json
{
  "room_name": "my-meeting-room",
  "started_at": "14:30:22",
  "ended_at": "14:35:10",
  "total_participants": 3,
  "total_turns": 6,
  "total_words": 52,
  "participants": {
    "Alice": {
      "identity": "Alice",
      "name": "Alice",
      "joined_at": "14:30:25",
      "left_at": "",
      "word_count": 25,
      "turn_count": 3,
      "characters": 142,
      "avg_words_per_turn": 8.3
    },
    "Bob": {
      "identity": "Bob",
      "name": "Bob",
      "joined_at": "14:30:28",
      "left_at": "",
      "word_count": 18,
      "turn_count": 2,
      "characters": 98,
      "avg_words_per_turn": 9.0
    },
    "Charlie": {
      "identity": "Charlie",
      "name": "Charlie",
      "joined_at": "14:30:45",
      "left_at": "14:32:10",
      "word_count": 9,
      "turn_count": 1,
      "characters": 31,
      "avg_words_per_turn": 9.0
    }
  }
}
```

---

## How It Works

### Architecture

```
┌─────────────────┐
│  Participant 1  │──┐
└─────────────────┘  │
                     │
┌─────────────────┐  │    ┌──────────────────┐
│  Participant 2  │──┼───→│  LiveKit Room    │
└─────────────────┘  │    └──────────────────┘
                     │            │
┌─────────────────┐  │            ↓
│  Participant 3  │──┤    ┌──────────────────────────────────┐
└─────────────────┘  │    │     Protocol Agent               │
                     │    │                                  │
┌─────────────────┐  │    │  ┌────────────────────────────┐  │
│  Participant 4  │──┘    │  │ MultiParticipantProtocol   │  │
└─────────────────┘       │  │                            │  │
                          │  │  Session 1 ←─ Participant 1│  │
                          │  │  Session 2 ←─ Participant 2│  │
                          │  │  Session 3 ←─ Participant 3│  │
                          │  │  Session 4 ←─ Participant 4│  │
                          │  └────────────────────────────┘  │
                          │              │                   │
                          │              ↓                   │
                          │  ┌────────────────────────────┐  │
                          │  │   Thread-Safe File Writer  │  │
                          │  │   (asyncio.Lock)           │  │
                          │  └────────────────────────────┘  │
                          └──────────────────────────────────┘
                                         │
                    ┌────────────────────┼────────────────────┐
                    ↓                    ↓                    ↓
            ┌──────────────┐    ┌──────────────┐    ┌──────────────┐
            │ protocol.txt │    │protocol.jsonl│    │  stats.json  │
            └──────────────┘    └──────────────┘    └──────────────┘
```

### Component Overview

#### 1. ProtocolConfig
Dataclass that loads configuration from environment variables:
- STT provider selection
- Output format preferences
- Directory paths
- Feature flags

#### 2. ProtocolRecorder (Agent)
Per-participant agent that:
- Receives audio from one participant
- Uses configured STT provider
- Calls `write_transcript()` on completion
- Raises `StopResponse()` to prevent replies

#### 3. MultiParticipantProtocol (Manager)
Central coordinator that:
- Tracks participant connections/disconnections
- Creates/destroys AgentSessions per participant
- Manages thread-safe file writing
- Tracks statistics
- Handles cleanup on shutdown

#### 4. Statistics Tracking
`ProtocolStats` and `ParticipantStats` dataclasses that track:
- Word count per participant
- Turn count per participant
- Join/leave timestamps
- Meeting totals

---

## Real-Time Text Output

The agent supports **live text output** while participants are speaking. This enables:

### 1. Console Output
Transcripts appear in your terminal in real-time:
```
2025-01-04 14:30:35 - protocol-agent - INFO - [14:30:35] Alice: Hello everyone
2025-01-04 14:30:42 - protocol-agent - INFO - [14:30:42] Bob: Hi Alice
```

### 2. LiveKit Room Text Stream
The configuration `text_output=True` sends transcriptions back to the room:
```python
room_options=room_io.RoomOptions(
    text_output=True,  # Enables real-time transcription to room
)
```

Client applications can subscribe to this text stream for:
- Live captions/subtitles
- Real-time translation displays
- Accessibility features

### 3. File Output
Transcripts are written to files immediately (with natural STT delay):
- TXT file: Append immediately
- JSONL file: Append immediately
- Statistics: Updated in memory, saved on close

### Latency Expectations

| Stage | Typical Delay |
|-------|---------------|
| Audio capture | ~50ms |
| STT processing | 200-500ms |
| File write | <10ms |
| **Total** | **250-560ms** |

---

## Troubleshooting

### Common Issues

#### 1. "No module named 'aiofiles'"

```bash
pip install aiofiles
```

#### 2. "No module named 'livekit'"

```bash
source venv/bin/activate
pip install livekit-agents
```

#### 3. "Authentication failed"

Check your `.env` file:
- Verify credentials are correct
- Ensure no extra spaces or quotes
- Check that `LIVEKIT_URL` starts with `wss://`

#### 4. No transcriptions appearing

- Check participant microphones are enabled
- Verify STT API key is valid
- Check logs for error messages
- Ensure VAD model loaded: look for "Prewarm complete" in logs

#### 5. "Unknown STT provider"

Valid options are: `deepgram`, `speechmatics`, `openai`

```bash
STT_PROVIDER="deepgram"  # Correct
STT_PROVIDER="Deepgram"  # Wrong (case-sensitive)
```

#### 6. Protocol files not created

- Check write permissions in the directory
- Verify `PROTOCOLS_DIR` path exists or is creatable
- Look for errors in console output

### Debug Mode

Enable detailed logging:

```python
import logging
logging.basicConfig(level=logging.DEBUG)
```

Or set environment variable:
```bash
export LIVEKIT_LOG_LEVEL=debug
```

### Log Messages to Watch

| Message | Meaning |
|---------|---------|
| "Prewarm complete" | VAD model loaded successfully |
| "Protocol files created" | Files initialized |
| "Participant connected" | New participant detected |
| "Starting transcription session" | STT session starting |
| "Recoverable error" | Temporary issue, will retry |
| "Unrecoverable error" | Serious issue, check config |

---

## Advanced Features

### 1. Custom STT Configuration

Modify `get_stt()` in `protocol_agent.py`:

```python
def get_stt(config: ProtocolConfig):
    if config.stt_provider == "deepgram":
        from livekit.plugins import deepgram
        return deepgram.STT(
            model="nova-3",
            language="en",
            punctuate=True,
            smart_format=True,
        )
    elif config.stt_provider == "speechmatics":
        from livekit.plugins import speechmatics
        return speechmatics.STT(
            language="en",
            operating_point="enhanced",
            enable_entities=True,
            enable_diarization=True,
            max_speakers=4,
            additional_vocab=[
                {"content": "LiveKit", "sounds_like": ["live kit"]}
            ],
        )
```

### 2. Webhook Integration

Send transcripts to an external service:

```python
import aiohttp

async def write_transcript(self, timestamp: str, participant: str, text: str):
    # ... existing file writes ...

    # Send to webhook
    async with aiohttp.ClientSession() as session:
        await session.post("https://your-api.com/transcripts", json={
            "room": self.ctx.room.name,
            "timestamp": timestamp,
            "speaker": participant,
            "text": text
        })
```

### 3. Database Storage

Store transcripts in a database:

```python
import asyncpg

class MultiParticipantProtocol:
    async def initialize(self):
        self.db = await asyncpg.connect(os.getenv("DATABASE_URL"))
        # ... rest of initialization

    async def write_transcript(self, timestamp, participant, text):
        await self.db.execute("""
            INSERT INTO transcripts (room, timestamp, participant, text)
            VALUES ($1, $2, $3, $4)
        """, self.ctx.room.name, timestamp, participant, text)
```

### 4. AI Summary Generation

Generate meeting summaries at the end:

```python
async def _finalize_protocol_files(self):
    # ... existing finalization ...

    # Generate AI summary
    if os.getenv("GENERATE_SUMMARY", "false").lower() == "true":
        from livekit.plugins import openai

        transcript = self._get_full_transcript()
        llm = openai.LLM()

        summary = await llm.chat(messages=[
            {"role": "system", "content": "Summarize this meeting with key points and action items."},
            {"role": "user", "content": transcript}
        ])

        async with aiofiles.open(self.stats_file.with_suffix('.summary.txt'), 'w') as f:
            await f.write(summary)
```

### 5. Filtering Participants

Only transcribe specific participants:

```python
ALLOWED_PARTICIPANTS = os.getenv("ALLOWED_PARTICIPANTS", "").split(",")

def _on_participant_connected(self, participant):
    if ALLOWED_PARTICIPANTS and participant.identity not in ALLOWED_PARTICIPANTS:
        logger.info(f"Ignoring participant: {participant.identity}")
        return
    # ... rest of method
```

### 6. Language Detection

Auto-detect language with Deepgram:

```python
def get_stt(config):
    if config.stt_provider == "deepgram":
        from livekit.plugins import deepgram
        return deepgram.STT(
            model="nova-3",
            language="multi",  # Auto-detect
            detect_language=True,
        )
```

### 7. Multiple Rooms / Breakout Sessions

Der Agent unterstützt automatisch mehrere Räume:

**Standard-Verhalten:**
- Im `dev`-Modus wird der Agent für **jeden** Raum dispatched
- Jeder Raum bekommt seine eigene Agent-Instanz
- Jeder Raum hat sein eigenes Protokoll-File

**Bei Breakout Sessions:**
```
Main Room (meeting_main)     → Agent Instance 1 → protocol_meeting_main_*.txt
├── Breakout 1 (breakout_1)  → Agent Instance 2 → protocol_breakout_1_*.txt
├── Breakout 2 (breakout_2)  → Agent Instance 3 → protocol_breakout_2_*.txt
└── Breakout 3 (breakout_3)  → Agent Instance 4 → protocol_breakout_3_*.txt
```

**Nur bestimmte Räume akzeptieren:**

```python
# In protocol_agent.py - vor dem server = AgentServer()

@agents.on_job_request()
async def on_job_request(job_request: agents.JobRequest):
    # Nur Räume mit bestimmtem Präfix akzeptieren
    if job_request.room.name.startswith("meeting_"):
        await job_request.accept(entrypoint)
    else:
        logger.info(f"Ignoring room: {job_request.room.name}")
        await job_request.reject()
```

**Bestimmte Räume ausschließen:**

```python
EXCLUDED_ROOMS = ["test", "debug", "staging"]

@agents.on_job_request()
async def on_job_request(job_request: agents.JobRequest):
    if job_request.room.name in EXCLUDED_ROOMS:
        await job_request.reject()
    else:
        await job_request.accept(entrypoint)
```

---

## API Reference

### ProtocolConfig

```python
@dataclass
class ProtocolConfig:
    stt_provider: str      # "deepgram", "speechmatics", "openai"
    output_format: str     # "txt", "json", "both"
    protocols_dir: Path    # Output directory
    enable_statistics: bool  # Track statistics
```

### ProtocolRecorder

```python
class ProtocolRecorder(Agent):
    def __init__(
        self,
        *,
        participant_identity: str,
        protocol_manager: MultiParticipantProtocol,
        config: ProtocolConfig,
    )

    async def on_user_turn_completed(
        self,
        chat_ctx: llm.ChatContext,
        new_message: llm.ChatMessage
    )
```

### MultiParticipantProtocol

```python
class MultiParticipantProtocol:
    def __init__(self, ctx: JobContext, config: ProtocolConfig)

    async def initialize(self)           # Create output files
    def start(self)                       # Start listening for participants
    async def aclose(self)                # Clean up and finalize

    async def write_transcript(           # Write a transcript entry
        self, timestamp: str, participant: str, text: str
    )
```

### ParticipantStats

```python
@dataclass
class ParticipantStats:
    identity: str
    name: str
    joined_at: str
    left_at: str
    word_count: int
    turn_count: int
    characters: int

    def to_dict(self) -> dict
```

### ProtocolStats

```python
@dataclass
class ProtocolStats:
    room_name: str
    started_at: str
    ended_at: str
    participants: dict[str, ParticipantStats]
    total_turns: int
    total_words: int

    def record_speech(self, participant_identity: str, text: str)
    def to_dict(self) -> dict
```

---

## Testing with LiveKit Playground

### 1. Start the Agent

```bash
python protocol_agent.py dev
```

### 2. Open Agents Playground

Go to: https://agents-playground.livekit.io/

### 3. Configure Connection

Enter your LiveKit credentials (same as in `.env`)

### 4. Connect and Speak

1. Click "Connect"
2. Allow microphone access
3. Start speaking
4. Watch transcripts appear in console
5. Check `protocols/` directory for output files

---

## Resources

### Documentation
- **LiveKit Agents**: https://docs.livekit.io/agents/
- **Deepgram**: https://developers.deepgram.com/
- **Speechmatics**: https://docs.speechmatics.com/
- **OpenAI Whisper**: https://platform.openai.com/docs/guides/speech-to-text

### Community
- **LiveKit Slack**: https://livekit.io/join-slack
- **GitHub Issues**: https://github.com/livekit/agents/issues

### Video Tutorial
- https://www.youtube.com/watch?v=-mXZmypu9Qw

---

## Quick Command Reference

```bash
# Setup
python3 -m venv venv
source venv/bin/activate
pip install livekit-agents livekit-plugins-deepgram livekit-plugins-silero python-dotenv aiofiles

# Configure
cp .env.protocol .env
nano .env

# Download models
python protocol_agent.py download-files

# Run (Terminal 1)
python protocol_agent.py dev         # Development
python protocol_agent.py start       # Production
DEBUG=true python protocol_agent.py dev  # Mit Debug-Logging

# Dispatch to room (Terminal 2)
python dispatch_agent.py --list      # Show active rooms
python dispatch_agent.py <ROOM_NAME> # Dispatch agent to room

# Check Deepgram usage
python check_deepgram_usage.py

# Check output
ls protocols/
cat protocols/protocol_*.txt
tail -f protocols/protocol_*.txt     # Live follow
```

---

## Included Scripts

| Script | Beschreibung |
|--------|--------------|
| `protocol_agent.py` | Haupt-Agent für Transkription |
| `dispatch_agent.py` | Agent zu Räumen dispatchen |
| `check_deepgram_usage.py` | Deepgram API-Verbrauch prüfen |

---

**Created**: 2025-01-04
**Updated**: 2026-01-04
**Version**: 3.0 (with idle timeout, multi-language, usage tracking)
**License**: Apache 2.0 (based on LiveKit Agents framework)
