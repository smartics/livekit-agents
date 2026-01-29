import re
import json
import os
from datetime import datetime

# Configuration
BASE_DIR = r"c:\p\livekit-agents\protocols"
LOG_FILE = os.path.join(BASE_DIR, "transcribe.txt")
JSONL_FILE = os.path.join(BASE_DIR, "protocol_QPmsMhXT7HTnBgSYbJEHqyCyQtyTWjng_20260129_195222.jsonl")
REPAIRED_JSONL_FILE = os.path.join(BASE_DIR, "protocol_QPmsMhXT7HTnBgSYbJEHqyCyQtyTWjng_20260129_195222_REPAIRED.jsonl")
REPAIRED_TXT_FILE = os.path.join(BASE_DIR, "protocol_QPmsMhXT7HTnBgSYbJEHqyCyQtyTWjng_20260129_195222_REPAIRED.txt")

SESSION_START_STR = "2026-01-29 19:52:22"
SESSION_END_STR = "2026-01-29 23:15:00" # Buffer end time
ROOM_ID = "QPmsMhXT7HTnBgSYbJEHqyCyQtyTWjng"

def parse_log_line(line):
    # Regex for Transcripts
    # Example: 2026-01-29 23:12:04,794 - protocol-agent - INFO - [23:12:04] Stefan: So I'll stop.
    transcript_pattern = re.compile(r"(\d{4}-\d{2}-\d{2}) (\d{2}:\d{2}:\d{2}),\d+ - protocol-agent - INFO - \[(\d{2}:\d{2}:\d{2})\] ([^:]+): (.*)")
    
    # Regex for Events
    # Example: 2026-01-29 23:12:04,564 - protocol-agent - INFO - Participant disconnected: Michael
    event_pattern = re.compile(r"(\d{4}-\d{2}-\d{2}) (\d{2}:\d{2}:\d{2}),\d+ - protocol-agent - INFO - Participant (connected|disconnected): (.*)")

    t_match = transcript_pattern.search(line)
    if t_match:
        date_str, full_time_str, short_time_str, participant, text = t_match.groups()
        return {
            "type": "transcript",
            "datetime": f"{date_str} {full_time_str}",
            "timestamp": short_time_str,
            "participant": participant.strip(),
            "text": text.strip(),
            "word_count": len(text.strip().split())
        }
    
    e_match = event_pattern.search(line)
    if e_match:
        date_str, full_time_str, action, participant = e_match.groups()
        event_type = "joined" if action == "connected" else "left"
        return {
            "type": "event",
            "datetime": f"{date_str} {full_time_str}",
            "timestamp": full_time_str,
            "participant": participant.strip(),
            "event": event_type
        }
    
    return None

def load_jsonl(filepath):
    events = []
    with open(filepath, 'r', encoding='utf-8') as f:
        for line in f:
            if line.strip():
                try:
                    data = json.loads(line)
                    # Use a rough datetime for sorting if not present (log extraction will be better source of truth for sorting)
                    # We will trust existing JSONL order mostly, but we need to merge.
                    # Let's just store specific identifying keys to avoid duplicates
                    events.append(data)
                except json.JSONDecodeError:
                    pass
    return events

def main():
    print("Loading existing JSONL...")
    try:
        existing_events = load_jsonl(JSONL_FILE)
    except FileNotFoundError:
        print(f"Error: Could not find {JSONL_FILE}")
        return

    # Create a set of signatures for existing events to avoid duplicates
    # Signature: timestamp + type + participant + normalized_text
    existing_signatures = set()
    header = None
    footer = None
    
    core_existing_events = []

    def get_signature(evt):
        ts = evt.get('timestamp', '')
        etype = evt.get('type', '')
        participant = evt.get('participant', '')
        
        parts = [ts, etype, participant]
        
        if etype == 'transcript':
            # Normalize text: remove ALL whitespace to catch "dri n" vs "drin" mismatches
            raw_text = evt.get('text', '')
            norm_text = "".join(raw_text.split())
            parts.append(norm_text)
        else:
            parts.append(evt.get('event', ''))
            
        return "_".join(parts)

    for evt in existing_events:
        if evt.get("type") == "header":
            header = evt
            continue
        if evt.get("type") == "footer":
            footer = evt
            continue
            
        sig = get_signature(evt)
        existing_signatures.add(sig)
        core_existing_events.append(evt)

    print(f"Loaded {len(core_existing_events)} existing events.")

    # Sort existing events by timestamp to find gaps
    sorted_existing = []
    base_date = datetime.strptime("2026-01-29", "%Y-%m-%d").date()
    
    for evt in core_existing_events:
        ts_str = evt.get('timestamp')
        if ts_str:
            try:
                t = datetime.strptime(ts_str, "%H:%M:%S").time()
                dt = datetime.combine(base_date, t)
                sorted_existing.append((dt, evt))
            except ValueError:
                pass
    
    sorted_existing.sort(key=lambda x: x[0])
    
    # Identify Gaps > 60 seconds
    gaps = []
    if sorted_existing:
        for i in range(len(sorted_existing) - 1):
            curr_dt, _ = sorted_existing[i]
            next_dt, _ = sorted_existing[i+1]
            diff = (next_dt - curr_dt).total_seconds()
            
            if diff > 60:
                print(f"Detected gap: {curr_dt.time()} -> {next_dt.time()} ({diff}s)")
                gaps.append((curr_dt, next_dt))

    # Parse Log File
    print("Parsing Log file...")
    start_dt = datetime.strptime(SESSION_START_STR, "%Y-%m-%d %H:%M:%S")
    end_dt = datetime.strptime(SESSION_END_STR, "%Y-%m-%d %H:%M:%S")

    restored_events = []
    restored_signatures = set()
    
    with open(LOG_FILE, 'r', encoding='utf-8') as f:
        for line in f:
            # Pre-filter for date to speed up
            if not line.startswith("2026-01-29"):
                continue
                
            parsed = parse_log_line(line)
            if parsed:
                # Check time range in context of session
                evt_full_dt = datetime.strptime(parsed['datetime'], "%Y-%m-%d %H:%M:%S")
                if not (start_dt <= evt_full_dt <= end_dt):
                    continue

                # Check if this event falls into any gap
                in_gap = False
                for g_start, g_end in gaps:
                    # Strict inequality to avoid edge duplicates with existing events at boundaries
                    if g_start < evt_full_dt < g_end:
                        in_gap = True
                        break
                
                if not in_gap:
                    continue

                sig = get_signature(parsed)
                
                # Check duplication
                if sig not in existing_signatures and sig not in restored_signatures:
                    # Clean up text if it's a transcript (optional but good for consistency)
                    if parsed.get('type') == 'transcript':
                        parsed['text'] = ' '.join(parsed['text'].split())
                        parsed['word_count'] = len(parsed['text'].split()) # Re-calc word count
                    
                    # Remove helper key 'datetime' for final output if we want to match exact schema
                    # But keep it for sorting now
                    restored_events.append(parsed)
                    restored_signatures.add(sig)

    print(f"Found {len(restored_events)} missing events from logs within gaps.")
    
    # Merge and Sort
    # We assign a dummy datetime to existing events for sorting based on their timestampString
    # Provided timestamp string is HH:MM:SS. We assume date is 2026-01-29
    
    all_events = []
    
    # Add existing
    for evt in core_existing_events:
        # Add a datetime object for sorting
        ts = evt.get("timestamp")
        if ts:
            try:
                dt_obj = datetime.strptime(f"2026-01-29 {ts}", "%Y-%m-%d %H:%M:%S")
                evt['_sort_dt'] = dt_obj
                all_events.append(evt)
            except ValueError:
                pass # Should not happen with valid data
    
    # Add restored
    for evt in restored_events:
        dt_obj = datetime.strptime(evt['datetime'], "%Y-%m-%d %H:%M:%S")
        evt['_sort_dt'] = dt_obj
        # remove temporary key
        del evt['datetime']
        all_events.append(evt)

    # Sort
    all_events.sort(key=lambda x: x['_sort_dt'])
    
    # Cleanup sort key
    for evt in all_events:
        del evt['_sort_dt']

    # Write JSONL
    print(f"Writing {REPAIRED_JSONL_FILE}...")
    with open(REPAIRED_JSONL_FILE, 'w', encoding='utf-8') as f:
        if header:
            f.write(json.dumps(header) + "\n")
        
        for evt in all_events:
            f.write(json.dumps(evt) + "\n")
            
        # We might want to construct a footer if missing, or use existing
        if footer:
             f.write(json.dumps(footer) + "\n")
        else:
            # Construct a footer if we reached end time
            f.write(json.dumps({"type": "footer", "ended_at": "23:13:30"}) + "\n")

    # Write TXT
    print(f"Writing {REPAIRED_TXT_FILE}...")
    with open(REPAIRED_TXT_FILE, 'w', encoding='utf-8') as f:
        f.write("="*80 + "\n")
        f.write(f"Meeting Protocol - 2026-01-29 {header['started_at'] if header else '19:52:22'}\n")
        f.write(f"Room: {ROOM_ID}\n")
        f.write(f"STT Provider: {header['stt_provider'] if header else 'deepgram'}\n")
        f.write("="*80 + "\n\n")
        
        for evt in all_events:
            ts = evt.get('timestamp')
            participant = evt.get('participant')
            
            if evt.get('type') == 'event':
                action = evt.get('event')
                if action == 'joined':
                     f.write(f"[{ts}] >>> {participant} joined the meeting\n\n")
                elif action == 'left':
                     f.write(f"[{ts}] <<< {participant} left the meeting\n\n")
            
            elif evt.get('type') == 'transcript':
                text = evt.get('text', '').strip()
                f.write(f"[{ts}] {participant}: {text}\n")
        
        f.write("\n" + "="*80 + "\n")
        f.write("Meeting ended - 2026-01-29 23:13:30\n\n") # Hardcoded end based on log
        
        # Calculate stats
        stats = {}
        total_turns = 0
        total_words = 0
        
        for evt in all_events:
            if evt.get('type') == 'transcript':
                p = evt.get('participant')
                w = evt.get('word_count', 0)
                if p not in stats:
                    stats[p] = {'words': 0, 'turns': 0}
                stats[p]['words'] += w
                stats[p]['turns'] += 1
                total_turns += 1
                total_words += w
        
        f.write("--- Statistics ---\n")
        f.write(f"Total participants: {len(stats)}\n")
        f.write(f"Total turns: {total_turns}\n")
        f.write(f"Total words: {total_words}\n\n")
        f.write("Per participant:\n")
        for p, data in stats.items():
            f.write(f"  {p}: {data['words']} words, {data['turns']} turns\n")
        
        f.write("="*80 + "\n")

    print("Done.")

if __name__ == "__main__":
    main()
