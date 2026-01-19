import asyncio
import os
import sys
from unittest.mock import AsyncMock, MagicMock

# Add project root to path
sys.path.append(os.path.abspath(os.path.join(os.path.dirname(__file__), "..")))

# Mock astrbot package before importing MessageHandler
mock_astrbot = MagicMock()
sys.modules["astrbot"] = mock_astrbot
sys.modules["astrbot.api"] = mock_astrbot.api
sys.modules["astrbot.api.event"] = mock_astrbot.api.event
sys.modules["astrbot.core"] = mock_astrbot.core
sys.modules["astrbot.core.message"] = mock_astrbot.core.message
sys.modules["astrbot.core.message.components"] = mock_astrbot.core.message.components

from src.handlers.message_handler import MessageHandler  # noqa: E402


async def test_repeat_fix():
    print("--- Starting Repeat Fix Verification ---")

    # Mock Repo
    repo = MagicMock()
    repo.get_message_owner = AsyncMock(side_effect=lambda mid: mid == "duplicate_id")
    repo.save_message_index = AsyncMock()
    repo.update_msg_stats = AsyncMock()
    repo.update_behavior_stats = AsyncMock()
    repo.get_today_data = AsyncMock(return_value=None)

    handler = MessageHandler(repo)

    # 1. Test Real-time De-duplication
    print("\n1. Testing Real-time De-duplication...")
    event = MagicMock()
    event.message_obj = MagicMock()
    event.message_obj.group_id = "123456"
    event.message_obj.sender.user_id = "654321"
    event.message_obj.message_id = "duplicate_id"
    event.message_str = "hello"

    await handler.handle_message(event)

    if repo.save_message_index.called:
        print("FAIL: Duplicate message was not skipped!")
    else:
        print("PASS: Duplicate message was skipped.")

    # 2. Test History Repeat Detection
    print("\n2. Testing History Repeat Detection...")
    repo.get_message_owner.side_effect = lambda mid: None  # Reset for backfill
    history = [
        {
            "time": 1000,
            "message_id": "m1",
            "sender": {"user_id": "u1"},
            "message": "repeat me",
        },
        {
            "time": 1005,
            "message_id": "m2",
            "sender": {"user_id": "u1"},
            "message": "repeat me",
        },  # Repeat
        {
            "time": 1010,
            "message_id": "m3",
            "sender": {"user_id": "u2"},
            "message": "different",
        },
        {
            "time": 1015,
            "message_id": "m4",
            "sender": {"user_id": "u1"},
            "message": "new text",
        },
    ]

    # Mock date to today
    import time

    now_ts = int(time.time())
    for msg in history:
        msg["time"] = now_ts - (2000 - msg.get("time", 0))  # Ensure it's today

    stats = await handler.backfill_from_history("123456", history)
    print(f"Backfill stats: {stats}")

    if stats.get("repeat_count") == 1:
        print("PASS: Historical repeat detected.")
    else:
        print(
            f"FAIL: Historical repeat NOT detected correctly. Expected 1, got {stats.get('repeat_count')}"
        )

    # 3. Test Context Synchronization
    print("\n3. Testing Context Synchronization...")
    # Clear mocks
    repo.update_behavior_stats.reset_mock()
    repo.get_message_owner.side_effect = lambda mid: None

    last_text = MessageHandler._user_last_msg_text.get("123456", {}).get("u1")
    print(f"Last text in cache for u1: '{last_text}'")

    if last_text == "new text":
        print("PASS: Cache synchronized from history.")
    else:
        print(f"FAIL: Cache NOT synchronized. Got '{last_text}'")

    # Now send another real-time message that repeats the last history message
    event.message_obj.message_id = "m5"
    event.message_obj.sender.user_id = "u1"
    event.message_str = "new text"  # This should be a repeat of m4

    await handler.handle_message(event)

    # Check if repeat_inc was 1
    found_repeat = False
    for call in repo.update_behavior_stats.call_args_list:
        if call[1].get("repeat_inc") == 1:
            found_repeat = True
            break

    if found_repeat:
        print("PASS: Real-time repeat detected using synchronized cache.")
    else:
        print("FAIL: Real-time repeat NOT detected after backfill.")


if __name__ == "__main__":
    asyncio.run(test_repeat_fix())
