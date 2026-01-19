import asyncio
import os
import sys
from unittest.mock import MagicMock

# Add plugin root to path
sys.path.append(os.path.dirname(os.path.abspath(__file__)))
# Add AstrBot root to path
sys.path.append(r"c:\Helianthus\astrpro\AstrBot-master")

# Mock astrbot modules BEFORE importing anything else
sys.modules["astrbot"] = MagicMock()
sys.modules["astrbot.api"] = MagicMock()
sys.modules["astrbot.api.logger"] = MagicMock()
sys.modules["astrbot.core"] = MagicMock()
sys.modules["astrbot.core.star"] = MagicMock()
sys.modules["astrbot.core.star.context"] = MagicMock()

# Mock html_renderer specifically
mock_html_renderer = MagicMock()


async def mock_render_template(tmpl_str, **kwargs):
    # Save the HTML to a file for inspection
    with open("verify_output.html", "w", encoding="utf-8") as f:
        f.write(tmpl_str)
    return "verify_output.html"


mock_html_renderer.render_custom_template = mock_render_template

# CRITICAL: Ensure 'astrbot.core' module has 'html_renderer' attribute pointing to our mock
# because 'from astrbot.core import html_renderer' uses getattr on the module object.
sys.modules["astrbot.core"].html_renderer = mock_html_renderer
sys.modules["astrbot.core.html_renderer"] = mock_html_renderer

# Now import the local modules
from src.visual.renderer import LoveRenderer
from src.visual.theme_manager import ThemeManager


# Mock classes
class MockContext:
    pass


async def main():
    # Setup
    plugin_dir = os.path.dirname(os.path.abspath(__file__))
    theme_mgr = ThemeManager(plugin_dir)
    context = MockContext()

    # We need to manually set the env for renderer because we mocked the import
    renderer = LoveRenderer(context, theme_mgr)

    # Mock Data
    render_data = {
        "user_name": "纯爱战神",
        "user_id": "123456",
        "avatar_url": "https://api.multiavatar.com/target.png",
        "title": "THE_SIMP",
        "score": 88,
        "metrics": {
            "纯爱值": "90%",
            "存在感": "20%",
            "败犬值": "10%",
            "旧情指数": "5%",
            "营业频率": "50条/日",
            "小作文功率": "100字/条",
        },
        "logic_insights": [
            "【投入判定】该成员今日的表现尚算理智，没在群里表现出那种令人掩面的‘舔狗’狂热。",
            "【空气系处分】本席几乎无法在数据流中捕捉该受众的波长。",
        ],
        "comment": "你的深情在群友眼中不过是每日定时的骚扰表演。",
        "equation": "J_{love} = ...",
        "generated_time": "2023-10-27 12:00:00",
        "deep_dive": {
            "keywords": ["#自我感动", "#独角戏", "#空气人"],
            "content": "深度侧写内容......该用户表现出强烈的自我感动倾向。",
            "evidence": [
                {
                    "title": "证言一：无效打招呼",
                    "reason": "连续发送早安却无人回应，体现了极致的空气感。",
                    "dialogue": [
                        {
                            "role": "Target",
                            "content": "大家早安！今天也是充满希望的一天捏~",
                            "user_id": "123456",
                            "avatar_url": "https://api.multiavatar.com/target.png",
                        },
                        {
                            "role": "UserA",
                            "content": "早。",
                            "user_id": "654321",
                            "avatar_url": "https://api.multiavatar.com/usera.png",
                        },
                        {
                            "role": "Target",
                            "content": "UserA 居然回我了！感道流泪！",
                            "user_id": "123456",
                            "avatar_url": "https://api.multiavatar.com/target.png",
                        },
                    ],
                },
                {
                    "title": "证言二：强行接梗",
                    "reason": "在群友讨论 Galgame 时强行插入无关话题。",
                    "dialogue": [
                        {
                            "role": "UserB",
                            "content": "ATRI 真的太好哭了。",
                            "user_id": "999999",
                            "avatar_url": "https://api.multiavatar.com/userb.png",
                        },
                        {
                            "role": "Target",
                            "content": "确实，不过我觉得原神也不错...",
                            "user_id": "123456",
                            "avatar_url": "https://api.multiavatar.com/target.png",
                        },
                        {
                            "role": "UserB",
                            "content": "？",
                            "user_id": "999999",
                            "avatar_url": "https://api.multiavatar.com/userb.png",
                        },
                    ],
                },
            ],
        },
    }

    try:
        image_path = await renderer.render(render_data, theme_name="galgame")
        print(f"VERIFICATION SUCCESS: Image generated at {image_path}")
    except Exception as e:
        print(f"VERIFICATION FAILED: {e}")
        import traceback

        traceback.print_exc()


if __name__ == "__main__":
    asyncio.run(main())
