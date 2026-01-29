"""
LiveKit Multi-Participant Protocol Agent

A speech-to-text transcription agent that records meeting protocols
with timestamps showing who said what.

Features:
- Multi-participant transcription
- Async file I/O with thread-safe writing
- Configurable STT provider (Deepgram, Speechmatics, OpenAI)
- JSON/JSONL and TXT output formats
- Conversation statistics
- Error handling and recovery
- Graceful shutdown

Environment Variables:
- LIVEKIT_URL: LiveKit server URL
- LIVEKIT_API_KEY: LiveKit API key
- LIVEKIT_API_SECRET: LiveKit API secret
- DEEPGRAM_API_KEY: Deepgram API key (if using Deepgram)
- SPEECHMATICS_API_KEY: Speechmatics API key (if using Speechmatics)
- OPENAI_API_KEY: OpenAI API key (if using OpenAI)
- STT_PROVIDER: Speech-to-text provider (deepgram, speechmatics, openai) - default: deepgram
- OUTPUT_FORMAT: Output format (txt, json, both) - default: both
"""

import asyncio
import json
import logging
import os
import threading
from dataclasses import dataclass, field
from datetime import datetime, timezone
from pathlib import Path
from typing import IO, Any

from dotenv import load_dotenv

from livekit import rtc
from livekit.agents import (
    Agent,
    AgentServer,
    AgentSession,
    AutoSubscribe,
    JobContext,
    JobProcess,
    StopResponse,
    cli,
    llm,
    room_io,
    utils,
)
from livekit.agents.voice.events import CloseEvent, ErrorEvent
from livekit.plugins import silero

load_dotenv()

# Configure logging
# Set to DEBUG to see audio track info and STT events
log_level = logging.DEBUG if os.getenv("DEBUG", "false").lower() == "true" else logging.INFO
logging.basicConfig(
    level=log_level,
    format="%(asctime)s - %(name)s - %(levelname)s - %(message)s"
)
logger = logging.getLogger("protocol-agent")
logger.setLevel(log_level)


# =============================================================================
# Configuration
# =============================================================================

@dataclass
class ProtocolConfig:
    """Configuration for the protocol agent."""
    stt_provider: str = field(default_factory=lambda: os.getenv("STT_PROVIDER", "deepgram").lower())
    output_format: str = field(default_factory=lambda: os.getenv("OUTPUT_FORMAT", "both").lower())
    protocols_dir: Path = field(default_factory=lambda: Path(os.getenv("PROTOCOLS_DIR", "protocols")))
    enable_statistics: bool = field(default_factory=lambda: os.getenv("ENABLE_STATISTICS", "true").lower() == "true")
    idle_timeout_minutes: int = field(default_factory=lambda: int(os.getenv("IDLE_TIMEOUT_MINUTES", "5")))  # Auto-disconnect after X minutes of silence

    def __post_init__(self):
        if self.stt_provider not in ["deepgram", "speechmatics", "openai"]:
            logger.warning(f"Unknown STT provider '{self.stt_provider}', defaulting to 'deepgram'")
            self.stt_provider = "deepgram"
        if self.output_format not in ["txt", "json", "both"]:
            logger.warning(f"Unknown output format '{self.output_format}', defaulting to 'both'")
            self.output_format = "both"


def get_stt(config: ProtocolConfig):
    """Get the configured STT provider."""
    provider = config.stt_provider
    language = os.getenv("STT_LANGUAGE", "de")  # Default: German

    if provider == "deepgram":
        from livekit.plugins import deepgram
        return deepgram.STT(
            model="nova-3",
            language=language,  # "de" für Deutsch, "en" für Englisch, "multi" für Auto-Detect
            smart_format=True,  # Bessere Formatierung
            no_delay=True,      # Schnellere Ergebnisse
            endpointing_ms=500, # Kürzere Pausen = schnellere Turns
        )

    elif provider == "speechmatics":
        from livekit.plugins import speechmatics
        return speechmatics.STT(
            language=language,
            operating_point="enhanced",
            enable_entities=True,
        )

    elif provider == "openai":
        from livekit.plugins import openai
        return openai.STT()

    else:
        # Fallback to deepgram
        from livekit.plugins import deepgram
        return deepgram.STT()


# =============================================================================
# Statistics Tracking
# =============================================================================

@dataclass
class ParticipantStats:
    """Statistics for a single participant."""
    identity: str
    name: str = ""
    joined_at: str = ""
    left_at: str = ""
    word_count: int = 0
    turn_count: int = 0
    characters: int = 0

    def to_dict(self) -> dict:
        return {
            "identity": self.identity,
            "name": self.name,
            "joined_at": self.joined_at,
            "left_at": self.left_at,
            "word_count": self.word_count,
            "turn_count": self.turn_count,
            "characters": self.characters,
            "avg_words_per_turn": round(self.word_count / max(self.turn_count, 1), 1)
        }


@dataclass
class ProtocolStats:
    """Statistics for the entire protocol/meeting."""
    room_name: str = ""
    started_at: str = ""
    ended_at: str = ""
    participants: dict[str, ParticipantStats] = field(default_factory=dict)
    total_turns: int = 0
    total_words: int = 0

    def record_speech(self, participant_identity: str, text: str):
        """Record a speech turn for statistics."""
        if participant_identity not in self.participants:
            self.participants[participant_identity] = ParticipantStats(identity=participant_identity)

        stats = self.participants[participant_identity]
        word_count = len(text.split())
        stats.word_count += word_count
        stats.turn_count += 1
        stats.characters += len(text)

        self.total_turns += 1
        self.total_words += word_count

    def to_dict(self) -> dict:
        return {
            "room_name": self.room_name,
            "started_at": self.started_at,
            "ended_at": self.ended_at,
            "duration_info": "See timestamps for duration",
            "total_participants": len(self.participants),
            "total_turns": self.total_turns,
            "total_words": self.total_words,
            "participants": {k: v.to_dict() for k, v in self.participants.items()}
        }


# =============================================================================
# Protocol Recorder Agent
# =============================================================================

class ProtocolRecorder(Agent):
    """
    Agent that transcribes speech from a participant and saves it to a protocol file.
    This agent only transcribes - it does not respond with voice.
    """

    def __init__(
        self,
        *,
        participant_identity: str,
        protocol_manager: "MultiParticipantProtocol",
        config: ProtocolConfig,
        stt,  # STT instance must be passed to Agent
    ):
        super().__init__(
            instructions="not-needed",
            stt=stt,  # STT is passed to Agent, not AgentSession
        )
        self.participant_identity = participant_identity
        self.protocol_manager = protocol_manager
        self.config = config

    async def on_user_turn_completed(
        self,
        chat_ctx: llm.ChatContext,
        new_message: llm.ChatMessage
    ):
        """Called when the user finishes speaking."""
        try:
            logger.debug(f"on_user_turn_completed called for {self.participant_identity}")
            user_transcript = new_message.text_content
            if not user_transcript or not user_transcript.strip():
                logger.debug(f"Empty transcript for {self.participant_identity}, ignoring")
                raise StopResponse()

            timestamp = get_timestamp()

            # Log to console
            logger.info(f"[{timestamp}] {self.participant_identity}: {user_transcript}")

            # Save to protocol (synchronous, thread-safe)
            self.protocol_manager.write_transcript(
                timestamp=timestamp,
                participant=self.participant_identity,
                text=user_transcript
            )

        except StopResponse:
            raise  # Re-raise StopResponse without logging as error
        except Exception as e:
            logger.error(f"Error processing transcript for {self.participant_identity}: {e}")

        # Stop the agent from generating a response
        raise StopResponse()


# =============================================================================
# Multi-Participant Protocol Manager
# =============================================================================

class MultiParticipantProtocol:
    """
    Manages protocol recording for multiple participants in a LiveKit room.
    Creates separate transcription sessions for each participant.
    Features thread-safe async file writing and multiple output formats.
    """

    def __init__(self, ctx: JobContext, config: ProtocolConfig):
        self.ctx = ctx
        self.config = config
        self._sessions: dict[str, AgentSession] = {}
        self._tasks: set[asyncio.Task] = set()
        self._write_lock = threading.Lock()  # Thread-safe lock for file writes
        self._last_speech_time: dict[str, datetime] = {}  # Track last speech per participant
        self._idle_check_task: asyncio.Task | None = None
        self._all_idle = False  # Flag to track if all sessions were closed due to idle

        # Statistics tracking
        self.stats = ProtocolStats(
            room_name=ctx.room.name,
            started_at=get_timestamp()
        )

        # Setup file paths
        config.protocols_dir.mkdir(exist_ok=True)
        file_timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
        base_name = f"protocol_{ctx.room.name}_{file_timestamp}"

        self.txt_file = config.protocols_dir / f"{base_name}.txt"
        self.json_file = config.protocols_dir / f"{base_name}.jsonl"
        self.stats_file = config.protocols_dir / f"{base_name}_stats.json"

        # File handles - kept open to avoid "Too many open files" error
        self._txt_handle: IO | None = None
        self._json_handle: IO | None = None

        self._initialized = False

    def initialize(self):
        """Initialize protocol files with headers and keep file handles open."""
        if self._initialized:
            return
        self._initialized = True

        with self._write_lock:
            if self.config.output_format in ["txt", "both"]:
                self._write_txt_header()
                # Keep file handle open for subsequent writes
                self._txt_handle = open(self.txt_file, "a", encoding="utf-8")

            if self.config.output_format in ["json", "both"]:
                self._write_json_header()
                # Keep file handle open for subsequent writes
                self._json_handle = open(self.json_file, "a", encoding="utf-8")

        logger.info(f"Protocol files created: {self.txt_file.stem}")

    def _write_txt_header(self):
        """Write header to TXT file (synchronous)."""
        header = (
            "=" * 80 + "\n" +
            f"Meeting Protocol - {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}\n" +
            f"Room: {self.ctx.room.name}\n" +
            f"STT Provider: {self.config.stt_provider}\n" +
            "=" * 80 + "\n\n"
        )
        with open(self.txt_file, "w", encoding="utf-8") as f:
            f.write(header)

    def _write_json_header(self):
        """Write header entry to JSONL file (synchronous)."""
        header_entry = {
            "type": "header",
            "room": self.ctx.room.name,
            "started_at": get_timestamp(),
            "stt_provider": self.config.stt_provider
        }
        with open(self.json_file, "w", encoding="utf-8") as f:
            f.write(json.dumps(header_entry) + "\n")

    def start(self):
        """Start listening for participant events."""
        self.ctx.room.on("participant_connected", self._on_participant_connected)
        self.ctx.room.on("participant_disconnected", self._on_participant_disconnected)
        self.ctx.room.on("track_subscribed", self._on_track_subscribed)
        self.ctx.room.on("track_unsubscribed", self._on_track_unsubscribed)

        # Start idle check task
        if self.config.idle_timeout_minutes > 0:
            self._idle_check_task = asyncio.create_task(self._idle_check_loop())
            logger.info(f"Idle timeout enabled: {self.config.idle_timeout_minutes} minutes")

        logger.info("Protocol manager started, listening for participants")

    def _on_track_subscribed(self, track: rtc.Track, publication: rtc.RemoteTrackPublication, participant: rtc.RemoteParticipant):
        """Debug handler for track subscription."""
        logger.debug(f"Track subscribed: {participant.identity} -> {track.kind}, source={publication.source}, sid={track.sid}")
        if track.kind == rtc.TrackKind.KIND_AUDIO:
            logger.info(f"🎤 Audio track subscribed from {participant.identity}")

            # Restart session if we were in idle state
            if self._all_idle and participant.identity not in self._sessions:
                logger.info(f"Restarting session for {participant.identity} after idle timeout")
                self._all_idle = False
                self._restart_sessions_after_idle()

    def _on_track_unsubscribed(self, track: rtc.Track, publication: rtc.RemoteTrackPublication, participant: rtc.RemoteParticipant):
        """Debug handler for track unsubscription."""
        logger.debug(f"Track unsubscribed: {participant.identity} -> {track.kind}")

    def _restart_sessions_after_idle(self):
        """Restart transcription sessions for all participants after idle timeout."""
        logger.info("Restarting transcription sessions after idle...")

        # Restart sessions for all current participants in the room
        for participant in self.ctx.room.remote_participants.values():
            if participant.identity not in self._sessions:
                # Reset last speech time
                self._last_speech_time[participant.identity] = datetime.now()

                # Write resume event
                self._write_participant_event(
                    timestamp=get_timestamp(),
                    participant=participant.identity,
                    event_type="resumed"
                )

                # Start new session
                session_task = asyncio.create_task(self._start_session(participant))
                self._tasks.add(session_task)

                def on_session_started(t: asyncio.Task, identity=participant.identity):
                    try:
                        if not t.cancelled() and t.exception() is None:
                            self._sessions[identity] = t.result()
                            logger.info(f"Session restarted for {identity}")
                    except Exception as e:
                        logger.error(f"Failed to restart session for {identity}: {e}")
                    finally:
                        self._tasks.discard(t)

                session_task.add_done_callback(on_session_started)

    async def _idle_check_loop(self):
        """Periodically check for idle sessions and disconnect them.

        Logic:
        - Only close sessions when ALL participants are idle
        - If at least one person is speaking, keep all sessions active
        - Sessions can be restarted if participant speaks again
        """
        check_interval = 60  # Check every 60 seconds
        timeout_seconds = self.config.idle_timeout_minutes * 60

        while True:
            try:
                await asyncio.sleep(check_interval)

                if not self._sessions:
                    continue  # No active sessions

                now = datetime.now()
                all_idle = True
                idle_info = []

                # Check if ALL participants are idle
                for identity, last_speech in self._last_speech_time.items():
                    if identity not in self._sessions:
                        continue  # Skip participants without active session

                    idle_seconds = (now - last_speech).total_seconds()
                    if idle_seconds < timeout_seconds:
                        all_idle = False  # At least one person is active
                        break
                    else:
                        idle_info.append((identity, idle_seconds))

                # Only close if ALL are idle
                if all_idle and idle_info:
                    logger.warning(f"All participants idle for {self.config.idle_timeout_minutes}+ min - pausing transcription")

                    for identity, idle_seconds in idle_info:
                        if identity in self._sessions:
                            logger.info(f"Closing session for {identity} (idle {idle_seconds/60:.1f} min)")
                            session = self._sessions.pop(identity)

                            # Write pause event
                            self._write_participant_event(
                                timestamp=get_timestamp(),
                                participant=identity,
                                event_type="idle_timeout"
                            )

                            await self._close_session(session)

                    # Mark that we're in idle state (for potential restart)
                    self._all_idle = True

            except asyncio.CancelledError:
                break
            except Exception as e:
                logger.error(f"Error in idle check loop: {e}")

    async def aclose(self):
        """Clean up all sessions and finalize protocol files."""
        logger.info("Closing protocol manager...")

        # Cancel idle check task
        if self._idle_check_task:
            self._idle_check_task.cancel()
            try:
                await self._idle_check_task
            except asyncio.CancelledError:
                pass

        # Cancel all pending tasks
        if self._tasks:
            await utils.aio.cancel_and_wait(*self._tasks)

        # Close all sessions
        if self._sessions:
            await asyncio.gather(
                *[self._close_session(session) for session in self._sessions.values()],
                return_exceptions=True
            )

        # Remove event listeners
        self.ctx.room.off("participant_connected", self._on_participant_connected)
        self.ctx.room.off("participant_disconnected", self._on_participant_disconnected)

        # Finalize files
        self.stats.ended_at = get_timestamp()
        self._finalize_protocol_files()

        logger.info("Protocol manager closed")

    def _finalize_protocol_files(self):
        """Add footer to protocol files, save statistics, and close file handles."""
        with self._write_lock:
            # Write TXT footer and close handle
            if self._txt_handle:
                footer = (
                    "\n" + "=" * 80 + "\n" +
                    f"Meeting ended - {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}\n"
                )

                if self.config.enable_statistics:
                    footer += "\n--- Statistics ---\n"
                    footer += f"Total participants: {len(self.stats.participants)}\n"
                    footer += f"Total turns: {self.stats.total_turns}\n"
                    footer += f"Total words: {self.stats.total_words}\n"
                    footer += "\nPer participant:\n"
                    for identity, pstats in self.stats.participants.items():
                        footer += f"  {identity}: {pstats.word_count} words, {pstats.turn_count} turns\n"

                footer += "=" * 80 + "\n"

                self._txt_handle.write(footer)
                self._txt_handle.close()
                self._txt_handle = None

            # Write JSON footer and close handle
            if self._json_handle:
                footer_entry = {
                    "type": "footer",
                    "ended_at": get_timestamp()
                }
                self._json_handle.write(json.dumps(footer_entry) + "\n")
                self._json_handle.close()
                self._json_handle = None

            # Save statistics file
            if self.config.enable_statistics:
                with open(self.stats_file, "w", encoding="utf-8") as f:
                    f.write(json.dumps(self.stats.to_dict(), indent=2))
                logger.info(f"Statistics saved to: {self.stats_file}")

    def _on_participant_connected(self, participant: rtc.RemoteParticipant):
        """Handle when a participant joins the room."""
        if participant.identity in self._sessions:
            return

        logger.info(f"Participant connected: {participant.identity}")

        # Initialize last speech time for idle tracking
        self._last_speech_time[participant.identity] = datetime.now()

        # Update statistics
        timestamp = get_timestamp()
        if participant.identity not in self.stats.participants:
            self.stats.participants[participant.identity] = ParticipantStats(
                identity=participant.identity,
                name=participant.name or participant.identity,
                joined_at=timestamp
            )

        # Write join event (synchronous, thread-safe)
        self._write_participant_event(
            timestamp=timestamp,
            participant=participant.identity,
            event_type="joined"
        )

        # Start transcription session
        session_task = asyncio.create_task(self._start_session(participant))
        self._tasks.add(session_task)

        def on_session_started(t: asyncio.Task):
            try:
                if not t.cancelled() and t.exception() is None:
                    self._sessions[participant.identity] = t.result()
            except Exception as e:
                logger.error(f"Failed to start session for {participant.identity}: {e}")
            finally:
                self._tasks.discard(t)

        session_task.add_done_callback(on_session_started)

    def _on_participant_disconnected(self, participant: rtc.RemoteParticipant):
        """Handle when a participant leaves the room."""
        session = self._sessions.pop(participant.identity, None)
        if session is None:
            return

        logger.info(f"Participant disconnected: {participant.identity}")

        # Update statistics
        timestamp = get_timestamp()
        if participant.identity in self.stats.participants:
            self.stats.participants[participant.identity].left_at = timestamp

        # Write leave event (synchronous, thread-safe)
        self._write_participant_event(
            timestamp=timestamp,
            participant=participant.identity,
            event_type="left"
        )

        # Close session
        close_task = asyncio.create_task(self._close_session(session))
        self._tasks.add(close_task)
        close_task.add_done_callback(lambda t: self._tasks.discard(t))

    async def _start_session(self, participant: rtc.RemoteParticipant) -> AgentSession:
        """Start a transcription session for a specific participant."""
        if participant.identity in self._sessions:
            return self._sessions[participant.identity]

        logger.info(f"Starting transcription session for: {participant.identity}")

        # Debug: Log participant's audio tracks
        for track_pub in participant.track_publications.values():
            logger.debug(f"  Track: {track_pub.sid}, kind={track_pub.kind}, source={track_pub.source}, subscribed={track_pub.subscribed}")
            if track_pub.track:
                logger.debug(f"    Track state: muted={track_pub.track.muted}")

        # Create STT instance for this participant
        stt_instance = get_stt(self.config)
        logger.info(f"Creating session with STT: {type(stt_instance).__name__}")

        # AgentSession only gets VAD - STT is passed to the Agent
        session = AgentSession(
            vad=self.ctx.proc.userdata["vad"],
        )

        # Add error handler
        @session.on("error")
        def on_error(ev: ErrorEvent):
            if ev.error.recoverable:
                logger.warning(f"Recoverable error for {participant.identity}: {ev.error}")
            else:
                logger.error(f"Unrecoverable error for {participant.identity}: {ev.error}")

        # Add close handler
        @session.on("close")
        def on_close(ev: CloseEvent):
            logger.info(f"Session closed for {participant.identity}, reason: {ev.reason}")

        await session.start(
            agent=ProtocolRecorder(
                participant_identity=participant.identity,
                protocol_manager=self,
                config=self.config,
                stt=stt_instance,  # STT is passed to Agent
            ),
            room=self.ctx.room,
            room_options=room_io.RoomOptions(
                audio_input=True,
                text_output=True,
                audio_output=False,
                text_input=False,
                participant_identity=participant.identity,
            ),
        )

        return session

    async def _close_session(self, sess: AgentSession) -> None:
        """Close a transcription session gracefully."""
        try:
            await sess.drain()
            await sess.aclose()
        except Exception as e:
            logger.error(f"Error closing session: {e}")

    def write_transcript(self, timestamp: str, participant: str, text: str):
        """Write a transcript entry to the protocol files (thread-safe, synchronous)."""
        # Update last speech time for idle tracking
        self._last_speech_time[participant] = datetime.now()

        # Update statistics
        if self.config.enable_statistics:
            self.stats.record_speech(participant, text)

        with self._write_lock:
            # Write to TXT file
            if self._txt_handle:
                txt_line = f"[{timestamp}] {participant}: {text}\n"
                self._txt_handle.write(txt_line)
                self._txt_handle.flush()

            # Write to JSONL file
            if self._json_handle:
                json_entry = {
                    "type": "transcript",
                    "timestamp": timestamp,
                    "participant": participant,
                    "text": text,
                    "word_count": len(text.split())
                }
                self._json_handle.write(json.dumps(json_entry) + "\n")
                self._json_handle.flush()

    def _write_participant_event(self, timestamp: str, participant: str, event_type: str):
        """Write a participant join/leave event to the protocol files (synchronous)."""
        with self._write_lock:
            # Write to TXT file
            if self._txt_handle:
                if event_type == "joined":
                    txt_line = f"[{timestamp}] >>> {participant} joined the meeting\n\n"
                elif event_type == "idle_timeout":
                    txt_line = f"\n[{timestamp}] ⏸️  {participant} session paused (idle timeout)\n\n"
                elif event_type == "resumed":
                    txt_line = f"[{timestamp}] ▶️  {participant} session resumed\n\n"
                else:
                    txt_line = f"\n[{timestamp}] <<< {participant} left the meeting\n\n"

                self._txt_handle.write(txt_line)
                self._txt_handle.flush()

            # Write to JSONL file
            if self._json_handle:
                json_entry = {
                    "type": "event",
                    "timestamp": timestamp,
                    "participant": participant,
                    "event": event_type
                }
                self._json_handle.write(json.dumps(json_entry) + "\n")
                self._json_handle.flush()


# =============================================================================
# Utility Functions
# =============================================================================

def get_timestamp() -> str:
    """Get current timestamp in a consistent format."""
    return datetime.now().strftime("%H:%M:%S")


def get_iso_timestamp() -> str:
    """Get current timestamp in ISO format with timezone."""
    return datetime.now(timezone.utc).isoformat()


# =============================================================================
# Server Setup
# =============================================================================

server = AgentServer()


@server.rtc_session()
async def entrypoint(ctx: JobContext):
    """
    Main entry point for the protocol agent.
    This is called when the agent joins a LiveKit room.
    """
    # Load configuration
    config = ProtocolConfig()
    logger.info(f"Starting protocol agent with config: STT={config.stt_provider}, Format={config.output_format}")

    # Initialize the protocol manager
    protocol = MultiParticipantProtocol(ctx, config)
    protocol.initialize()
    protocol.start()

    # Connect to the room (subscribe to audio only)
    await ctx.connect(auto_subscribe=AutoSubscribe.AUDIO_ONLY)
    logger.info(f"Connected to room: {ctx.room.name}")

    # Handle participants already in the room
    for participant in ctx.room.remote_participants.values():
        protocol._on_participant_connected(participant)

    # Register cleanup callback for graceful shutdown
    async def cleanup():
        logger.info("Shutdown requested, cleaning up...")
        await protocol.aclose()
        logger.info("Cleanup complete")

    ctx.add_shutdown_callback(cleanup)


def prewarm(proc: JobProcess):
    """
    Prewarm function to load models before handling requests.
    This improves performance by loading VAD model once.
    """
    logger.info("Prewarming: Loading VAD model...")
    proc.userdata["vad"] = silero.VAD.load()
    logger.info("Prewarm complete")


# Set the prewarm function
server.setup_fnc = prewarm


if __name__ == "__main__":
    cli.run_app(server)
