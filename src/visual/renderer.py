import base64
import os
import re

import aiohttp
from jinja2 import Environment, FileSystemLoader

from astrbot.api import logger
from astrbot.core import html_renderer
from astrbot.core.star.context import Context

from .theme_manager import ThemeManager

DEFAULT_AVATAR = "data:image/svg+xml;base64,PHN2ZyB4bWxucz0iaHR0cDovL3d3dy53My5vcmcvMjAwMC9zdmciIHZpZXdCb3g9IjAgMCAxMDAgMTAwIj48Y2lyY2xlIGN4PSI1MCIgY3k9IjUwIiByPSI1MCIgZmlsbD0iI2VlZSIvPjwvc3ZnPg=="


class LoveRenderer:
    """恋爱分析渲染器，负责将数据转化为视觉图片"""

    def __init__(self, context: Context, theme_manager: ThemeManager):
        self.context = context
        self.theme_manager = theme_manager
        # 初始化 Jinja2 环境
        self.env = Environment(loader=FileSystemLoader(theme_manager.themes_dir))

    async def render(self, data: dict, theme_name: str = "galgame") -> str:
        """
        将分析结果渲染为图片。
        返回：生成的图片文件的绝对路径。
        """
        logger.info(f"开始渲染图片，主题: {theme_name}")

        async with aiohttp.ClientSession() as session:
            # 1. Process Main Avatar
            if data.get("avatar_url") and data["avatar_url"].startswith("http"):
                try:
                    async with session.get(data["avatar_url"], timeout=5) as resp:
                        if resp.status == 200:
                            content = await resp.read()
                            b64 = base64.b64encode(content).decode()
                            data["avatar_url"] = f"data:image/jpeg;base64,{b64}"
                        else:
                            data["avatar_url"] = DEFAULT_AVATAR
                except Exception as e:
                    logger.warning(f"Failed to fetch main avatar: {e}")
                    data["avatar_url"] = DEFAULT_AVATAR
            elif not data.get("avatar_url"):
                data["avatar_url"] = DEFAULT_AVATAR

            # 2. Process Evidence Avatars
            if data.get("deep_dive") and data["deep_dive"].get("evidence"):
                for scene in data["deep_dive"]["evidence"]:
                    for dialog in scene.get("dialogue", []):
                        uid = dialog.get("user_id")
                        # Already base64 check
                        if dialog.get("avatar_url") and dialog["avatar_url"].startswith(
                            "data:"
                        ):
                            continue

                        if uid:
                            try:
                                url = f"https://q1.qlogo.cn/g?b=qq&nk={uid}&s=100"
                                async with session.get(url, timeout=5) as resp:
                                    if resp.status == 200:
                                        content = await resp.read()
                                        b64 = base64.b64encode(content).decode()
                                        dialog["avatar_url"] = (
                                            f"data:image/jpeg;base64,{b64}"
                                        )
                                    else:
                                        dialog["avatar_url"] = DEFAULT_AVATAR
                            except Exception as e:
                                logger.warning(f"Failed to fetch avatar for {uid}: {e}")
                                dialog["avatar_url"] = DEFAULT_AVATAR
                        else:
                            dialog["avatar_url"] = DEFAULT_AVATAR

            # 3. Process Theme Assets (e.g., header_bg.png)
            asset_dir = self.theme_manager.get_asset_dir(theme_name)
            header_bg_path = os.path.join(asset_dir, "header_bg.png")
            header_bg_b64 = ""
            if os.path.exists(header_bg_path):
                with open(header_bg_path, "rb") as f:
                    header_bg_b64 = (
                        f"data:image/png;base64,{base64.b64encode(f.read()).decode()}"
                    )

        # 1. 加载模板
        template_name = f"{theme_name}/template.html"
        try:
            template = self.env.get_template(template_name)
        except Exception as e:
            logger.error(f"模板加载失败: {e}")
            raise

        # Pre-rendering simple markdown for logic_insights and deep_dive
        # To avoid external scripts in template
        def simple_md(text):
            if not text:
                return ""
            # Simple bold and tags
            text = re.sub(r"\*\*(.*?)\*\*", r"<b>\1</b>", text)
            text = re.sub(r"#(.*?)(\s|$)", r'<span class="tag">#\1</span> ', text)
            return text

        def simple_math(text):
            if not text:
                return ""
            # Specific replacements for the love formula
            text = text.replace(r"J_{love}", "J<sub>love</sub>")
            text = text.replace(r"\int_{today}", "∫<sub>today</sub>")
            text = text.replace(r"e^{-rt}", "e<sup>-rt</sup>")
            text = text.replace(r"\cdot", "⋅")
            text = text.replace(r"\beta", "β")
            text = text.replace(r"\lambda", "λ")
            text = text.replace(r"\,", " ")
            text = text.replace(r"\Rightarrow", "⇒")
            text = text.replace(r"\%", "%")
            text = text.strip("$")
            return text

        if data.get("logic_insights"):
            data["logic_insights"] = [simple_md(i) for i in data["logic_insights"]]
        if data.get("comment"):
            data["comment"] = simple_md(data["comment"])
        if data.get("deep_dive") and data["deep_dive"].get("content"):
            data["deep_dive"]["content"] = simple_md(data["deep_dive"]["content"])
        if data.get("equation"):
            data["equation"] = simple_math(data["equation"])

        # 2. 渲染内容
        try:
            html_content = template.render(
                data=data,
                theme_config=self.theme_manager.get_theme_config(theme_name),
                header_bg=header_bg_b64,
            )
            logger.debug(f"HTML 生成成功，长度: {len(html_content)}")
        except Exception as e:
            logger.error(f"Jinja2 渲染失败: {e}")
            raise

        # 3. 使用 AstrBot 的 HTML 渲染引擎
        try:
            logger.debug("调用 AstrBot html_renderer...")
            path = await html_renderer.render_custom_template(
                tmpl_str=html_content,
                tmpl_data={},
                return_url=False,
                options={
                    "type": "jpeg",
                    "quality": 100,
                    "full_page": True,
                },
            )
            logger.info(f"图片生成完成: {path}")

            # Validation: Check if the file is actually an image or an error text

            if os.path.exists(path):
                file_size = os.path.getsize(path)
                if (
                    file_size < 1024
                ):  # Less than 1KB is suspicious for a full page screenshot
                    with open(path, "rb") as f:
                        content = f.read(100)  # Read first 100 bytes

                    try:
                        text_content = content.decode("utf-8")
                        if "Error" in text_content or "Exception" in text_content:
                            logger.error(
                                f"Rendered file seems to be an error message: {text_content}"
                            )
                            raise RuntimeError(
                                f"Browser rendering failed: {text_content}"
                            )
                    except UnicodeDecodeError:
                        # Binary content is good (likely image)
                        pass

            return path
        except Exception as e:
            logger.error(f"AstrBot 渲染引擎调用失败: {e}")
            raise
