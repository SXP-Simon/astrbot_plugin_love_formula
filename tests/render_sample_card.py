import asyncio
import os
import sys
from unittest.mock import AsyncMock, MagicMock

# Setup Paths
current_file = os.path.abspath(__file__)
plugin_dir = os.path.dirname(os.path.dirname(current_file))
sys.path.insert(0, plugin_dir)
# Add AstrBot root
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.dirname(plugin_dir))))

# Mock AstrBot modules BEFORE importing renderer which imports Context
# 1. Mock Context and Star
mock_star_module = MagicMock()
sys.modules["astrbot.core.star"] = mock_star_module
sys.modules["astrbot.core.star.context"] = mock_star_module


class MockStar:
    def __init__(self, context):
        self.context = context


mock_star_module.Star = MockStar
mock_star_module.Context = MagicMock

# 2. Mock LogManager (renderer imports it usually indirectly or if modified)
mock_log = MagicMock()
sys.modules["astrbot.core.log"] = mock_log
mock_log.LogManager.GetLogger.return_value = MagicMock()

# 3. Mock AstrBotConfig
mock_config_module = MagicMock()
sys.modules["astrbot.core.config"] = mock_config_module

# Now import renderer
from src.visual.renderer import LoveRenderer
from src.visual.theme_manager import ThemeManager


# Mock Context for our use
class MockContext:
    def __init__(self):
        self.image_renderer = MagicMock()
        # Mock render to return the HTML content directly for us to use (AsyncMock for await)
        self.image_renderer.render = AsyncMock(side_effect=lambda html: html)


async def main():
    print("=== Generating Sample Card ===")

    # Init
    context = MockContext()
    themes_dir = os.path.join(plugin_dir, "assets", "themes")
    print(f"Themes Dir: {themes_dir}")
    if os.path.exists(themes_dir):
        print(f"Themes content: {os.listdir(themes_dir)}")
        galgame_dir = os.path.join(themes_dir, "galgame")
        if os.path.exists(galgame_dir):
            print(f"Galgame content: {os.listdir(galgame_dir)}")
        else:
            print("Galgame dir missing!")
    else:
        print("Themes dir missing!")

    theme_mgr = ThemeManager(plugin_dir)
    print(f"ThemeManager initialized with root: {plugin_dir}")
    print(f"ThemeManager resolved themes_dir: {theme_mgr.themes_dir}")
    renderer = LoveRenderer(context, theme_mgr)

    # Mock Data
    data = {
        "user_name": "TestUser",
        "user_id": "123456",
        "avatar_url": "https://api.multiavatar.com/TestUser.png",  # Placeholder
        "score": 88,
        "title": "Cyber-Simp",
        "metrics": {
            "interaction": 50,
            "active": 30,
            "sweet": 20,
            "resilience": 80,
            "random": 10,
        },
        "comment": "This is a generated test comment to verify the layout and style of the Love Formula card.",
        "generated_time": "2026-01-18 16:00:00",
    }

    # Render HTML
    print("Rendering HTML template...")
    html_content = await renderer.render(data, theme_name="galgame")

    # Save HTML
    html_path = os.path.join(plugin_dir, "tests", "test_output.html")
    with open(html_path, "w", encoding="utf-8") as f:
        f.write(html_content)
    print(f"Saved HTML to {html_path}")

    # Render to Image using Pyppeteer
    try:
        from pyppeteer import launch

        print("Launching browser for screenshot...")
        browser = await launch(args=["--no-sandbox", "--disable-setuid-sandbox"])
        page = await browser.newPage()

        # Load the HTML content
        # Note: We need to handle local asset paths if they are file://
        # The template uses {{ asset_dir }}/style.css etc.
        # Ensure asset_dir in render is correct for local file access.

        await page.setContent(html_content)

        # Determine size - assume mobile-ish or card width
        # The card usually has a fixed width or max-width
        await page.setViewport({"width": 600, "height": 1000})

        # Wait for fonts/images?
        await asyncio.sleep(1)

        png_path = os.path.join(plugin_dir, "tests", "test_output.png")

        # Try to clip to body or specific container
        # await page.screenshot({'path': png_path, 'fullPage': True})

        # Better: clip to the card element
        # We need to know the class. Usually 'container' or 'card'.
        # Let's try fullPage first.
        await page.screenshot({"path": png_path, "fullPage": True})

        await browser.close()
        print(f"Saved PNG to {png_path}")

    except Exception as e:
        print(f"Failed to render PNG: {e}")
        import traceback

        traceback.print_exc()


if __name__ == "__main__":
    asyncio.run(main())
