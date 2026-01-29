#!/usr/bin/env python3
"""
Dispatch the Protocol Agent to a specific LiveKit room.

Usage:
    python dispatch_agent.py <room_name>
    python dispatch_agent.py QPmsMhXT7HTnBgSYbJEHqyCyQtyTWjng

You can find the room name in:
    - Browser console: Look for "room: 'ROOM_NAME'" in LiveKit logs
    - LiveKit Cloud Dashboard: https://cloud.livekit.io
    - Foundry VTT: Check the avclient-livekit module settings
"""

import asyncio
import os
import sys

from dotenv import load_dotenv
from livekit import api

load_dotenv()


async def dispatch_agent(room_name: str, agent_name: str = ""):
    """Dispatch an agent to the specified room."""

    # Get credentials from environment
    url = os.getenv("LIVEKIT_URL", "").replace("wss://", "https://")
    api_key = os.getenv("LIVEKIT_API_KEY")
    api_secret = os.getenv("LIVEKIT_API_SECRET")

    if not all([url, api_key, api_secret]):
        print("Error: Missing LIVEKIT_URL, LIVEKIT_API_KEY, or LIVEKIT_API_SECRET in .env")
        sys.exit(1)

    print(f"Dispatching agent to room: {room_name}")
    print(f"LiveKit URL: {url}")

    try:
        lk = api.LiveKitAPI(
            url=url,
            api_key=api_key,
            api_secret=api_secret
        )

        request = api.CreateAgentDispatchRequest(
            room=room_name,
            agent_name=agent_name
        )
        dispatch = await lk.agent_dispatch.create_dispatch(request)

        print(f"✅ Agent dispatched successfully!")
        print(f"   Dispatch ID: {dispatch.id}")
        print(f"   Room: {dispatch.room}")
        print(f"   State: {dispatch.state}")

        await lk.aclose()

    except Exception as e:
        print(f"❌ Error dispatching agent: {e}")
        sys.exit(1)


async def list_rooms():
    """List all active rooms."""

    url = os.getenv("LIVEKIT_URL", "").replace("wss://", "https://")
    api_key = os.getenv("LIVEKIT_API_KEY")
    api_secret = os.getenv("LIVEKIT_API_SECRET")

    if not all([url, api_key, api_secret]):
        print("Error: Missing credentials in .env")
        sys.exit(1)

    try:
        lk = api.LiveKitAPI(
            url=url,
            api_key=api_key,
            api_secret=api_secret
        )

        request = api.ListRoomsRequest()
        rooms = await lk.room.list_rooms(request)

        if not rooms.rooms:
            print("No active rooms found.")
        else:
            print(f"Active rooms ({len(rooms.rooms)}):")
            print("-" * 60)
            for room in rooms.rooms:
                print(f"  Room: {room.name}")
                print(f"    SID: {room.sid}")
                print(f"    Participants: {room.num_participants}")
                print()

        await lk.aclose()

    except Exception as e:
        print(f"Error listing rooms: {e}")
        sys.exit(1)


def main():
    if len(sys.argv) < 2:
        print(__doc__)
        print("\nCommands:")
        print("  python dispatch_agent.py <room_name>   - Dispatch agent to room")
        print("  python dispatch_agent.py --list        - List all active rooms")
        print()
        sys.exit(0)

    arg = sys.argv[1]

    if arg == "--list" or arg == "-l":
        asyncio.run(list_rooms())
    else:
        room_name = arg
        asyncio.run(dispatch_agent(room_name))


if __name__ == "__main__":
    main()
