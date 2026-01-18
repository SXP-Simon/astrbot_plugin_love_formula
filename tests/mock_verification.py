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

# Mock AstrBot modules BEFORE importing plugin
from unittest.mock import MagicMock

# 1. Mock LogManager
mock_log = MagicMock()
sys.modules["astrbot.core.log"] = mock_log
mock_log.LogManager.GetLogger.return_value = MagicMock()

# 2. Mock Context and Star
mock_star_module = MagicMock()
sys.modules["astrbot.core.star"] = mock_star_module
sys.modules["astrbot.core.star.context"] = mock_star_module


class MockStar:
    def __init__(self, context):
        self.context = context


mock_star_module.Star = MockStar
mock_star_module.Context = MagicMock

# 3. Mock AstrBotConfig
mock_config_module = MagicMock()
sys.modules["astrbot.core.config"] = mock_config_module
mock_config_module.AstrBotConfig = MagicMock

# 4. Mock API Event and Filters
mock_event_module = MagicMock()
sys.modules["astrbot.api.event"] = mock_event_module
sys.modules["astrbot.api.event.filter"] = mock_event_module


# Mock decorators to just return the function
def mock_decorator(*args, **kwargs):
    def decorator(func):
        return func

    return decorator


# Handle @filter.event_message_type etc
mock_event_module.filter.event_message_type = mock_decorator
mock_event_module.filter.command = mock_decorator
mock_event_module.filter.custom_filter = mock_decorator
mock_event_module.filter.CustomFilter = object  # Base class
mock_event_module.EventMessageType = MagicMock()
mock_event_module.AstrMessageEvent = MagicMock

# Now safe to import plugin
try:
    from astrbot_plugin_love_formula.main import LoveFormulaPlugin
except ImportError as e:
    print(f"Package import failed: {e}, trying direct...")
    sys.path.insert(0, plugin_dir)
    from main import LoveFormulaPlugin

# Re-assign for use in test
Context = mock_star_module.Context
AstrMessageEvent = mock_event_module.AstrMessageEvent


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
    mock_msg_event = MagicMock()
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
    mock_notice_event = MagicMock()
    mock_notice_event.message_obj.raw_message = (
        poke_event  # Fix: raw_message not raw_data based on main.py check
    )
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
    mock_cmd_event = MagicMock()
    mock_cmd_event.message_obj.group_id = "456"
    mock_cmd_event.message_obj.sender.user_id = "123"

    # Verify generator output
    generators = plugin.cmd_love_profile(mock_cmd_event)
    async for result in generators:
        print(f"[Result] Cmd Output: {result}")

    print("=== Verification Completed Successfully ===")


if __name__ == "__main__":
    asyncio.run(run_verification())
