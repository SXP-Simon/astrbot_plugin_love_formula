import asyncio
import os
import shutil
import time
from unittest.mock import MagicMock, AsyncMock
import sys

# Setup paths
current_file = os.path.abspath(__file__)
plugin_dir = os.path.dirname(
    os.path.dirname(current_file)
)  # astrbot_plugin_love_formula
plugins_dir = os.path.dirname(plugin_dir)  # plugins
data_dir = os.path.dirname(plugins_dir)
project_root = os.path.dirname(data_dir)  # AstrBot-master

# Add plugins dir to allow specific package import
if plugins_dir not in sys.path:
    sys.path.insert(0, plugins_dir)

# Add project root for astrbot module
if project_root not in sys.path:
    sys.path.insert(0, project_root)

# Robustly add /app for Docker environment
if os.path.exists("/app") and "/app" not in sys.path:
    sys.path.insert(0, "/app")

print(f"Paths added:\nPlugins: {plugins_dir}\nProject: {project_root}")

# Import as package to support relative imports in main.py
try:
    from astrbot_plugin_love_formula.main import LoveFormulaPlugin
except ImportError as e:
    print(f"Package import failed: {e}, trying direct...")
    sys.path.insert(0, plugin_dir)
    from main import LoveFormulaPlugin

from astrbot.core.star.context import Context
from astrbot.core.event.model.event import AstrMessageEvent


async def run_verification():
    print("=== Starting Mock Verification ===")

    # 0. Clean old DB
    if os.path.exists("data_mock"):
        shutil.rmtree("data_mock")
    os.makedirs("data_mock", exist_ok=True)

    # 1. Mock Context
    mock_context = MagicMock(spec=Context)
    mock_context.plugin_data_dir = "data_mock"

    # Mock LLM
    mock_completion = MagicMock()
    mock_completion.completion_text = (
        "Mock LLM Commentary: You are a simp because E > 80!"
    )
    mock_context.llm_generate = AsyncMock(return_value=mock_completion)

    # Mock Image Renderer
    mock_context.image_renderer = MagicMock()
    mock_context.image_renderer.render = AsyncMock(return_value="mock_image_path.png")

    # 2. Initialize Plugin
    mock_config = {
        "theme": "galgame",
        "enable_llm_commentary": True,
        "llm_provider_id": "",
        "min_msg_threshold": 1,
    }
    plugin = LoveFormulaPlugin(mock_context, config=mock_config)
    await plugin.init()
    print("[Pass] Plugin Initialized")

    # 3. Simulate Data Ingestion (Message)
    # User 123 sends message in Group 456
    mock_msg_event = MagicMock(spec=AstrMessageEvent)
    mock_msg_event.message_obj.group_id = "456"
    mock_msg_event.message_obj.sender.user_id = "123"
    mock_msg_event.message_obj.message_id = "msg_1"
    mock_msg_event.message_str = "Hello world! This is a test message."
    mock_msg_event.message_obj.message = [
        {"type": "text", "text": "Hello world!"}
    ]  # Simple mock

    await plugin.on_group_message(mock_msg_event)
    print("[Pass] Message Handled")

    # 4. Simulate Data Ingestion (Poke Notice)
    # RAW OneBot Notice Event
    poke_event = {
        "post_type": "notice",
        "notice_type": "notify",
        "sub_type": "poke",
        "group_id": "456",
        "user_id": "123",  # Sender
        "target_id": "789",  # Receiver
    }

    # Mock wrapper for notice
    mock_notice_event = MagicMock(spec=AstrMessageEvent)
    mock_notice_event.message_obj.raw_data = poke_event
    await plugin.on_notice(mock_notice_event)
    print("[Pass] Notice Handled")

    # 5. Verify DB State manually
    daily_data = await plugin.repo.get_today_data("456", "123")
    assert daily_data is not None
    assert daily_data.msg_sent == 1
    assert daily_data.poke_sent == 1
    print(f"[Pass] DB Verification Data: {daily_data}")

    # 6. Simulate Command /今日人设
    # Mock event for command
    mock_cmd_event = MagicMock(spec=AstrMessageEvent)
    mock_cmd_event.message_obj.group_id = "456"
    mock_cmd_event.message_obj.sender.user_id = "123"

    # Verify generator output
    generators = plugin.cmd_love_profile(mock_cmd_event)
    async for result in generators:
        print(f"[Result] Cmd Output: {result}")

    print("=== Verification Completed Successfully ===")


if __name__ == "__main__":
    asyncio.run(run_verification())
