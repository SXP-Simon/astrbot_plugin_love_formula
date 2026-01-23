import asyncio
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

            async def _fetch_avatar(url: str) -> str:
                try:
                    async with session.get(url, timeout=5) as resp:
                        if resp.status == 200:
                            content = await resp.read()
                            return f"data:image/jpeg;base64,{base64.b64encode(content).decode()}"
                except Exception as e:
                    logger.warning(f"Failed to fetch avatar {url}: {e}")
                return DEFAULT_AVATAR

            # ---------- 1. 主头像处理 ----------
            avatar_url = data.get("avatar_url")
            if avatar_url and avatar_url.startswith("http"):
                data["avatar_url"] = await _fetch_avatar(avatar_url)
            elif not avatar_url:
                data["avatar_url"] = DEFAULT_AVATAR

            # ---------- 2. Deep Dive 证据头像并行下载 ----------
            # 原顺序循环下载改为收集所有待下载任务，然后 asyncio.gather 并行下载
            tasks = []
            dialogues_to_update = []
            if data.get("deep_dive") and data["deep_dive"].get("evidence"):
                for scene in data["deep_dive"]["evidence"]:
                    for dialog in scene.get("dialogue", []):
                        uid = dialog.get("user_id")
                        # 跳过已经是 base64 或无 uid 的
                        if dialog.get("avatar_url", "").startswith("data:") or not uid:
                            continue
                        url = f"https://q1.qlogo.cn/g?b=qq&nk={uid}&s=100"
                        # 每个任务返回 base64 头像
                        tasks.append(_fetch_avatar(url))
                        dialogues_to_update.append(dialog)

                if tasks:
                    # 并行下载所有头像
                    results = await asyncio.gather(*tasks)
                    # 将下载结果回填到对应 dialogue
                    for dialog, avatar_b64 in zip(dialogues_to_update, results):
                        dialog["avatar_url"] = avatar_b64

            # ---------- 3. 模板资源（header_bg.png） ----------
            asset_dir = self.theme_manager.get_asset_dir(theme_name)
            header_bg_path = os.path.join(asset_dir, "header_bg.png")
            header_bg_b64 = ""
            if os.path.exists(header_bg_path):
                with open(header_bg_path, "rb") as f:
                    header_bg_b64 = (
                        f"data:image/png;base64,{base64.b64encode(f.read()).decode()}"
                    )

        # ---------- 后续模板加载、渲染逻辑保持不变 ----------
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
        render_strategies = [
            # 1. 第一策略: PNG, Ultra, quality, Device scale
            {
                "type": "png",
                "full_page": True,
                "scale": "device",
                "device_scale_factor_level": "ultra",
            },
            # 2. 第二策略: JPEG, Ultra, quality 100%, Device scale
            {
                "type": "jpeg",
                "quality": 100,
                "full_page": True,
                "scale": "device",
                "device_scale_factor_level": "ultra",
            },
            # 3. 第三策略: JPEG, Normal quality 95%, Device scale
            {
                "type": "jpeg",
                "quality": 95,
                "full_page": True,
                "scale": "device",
                "device_scale_factor_level": "high",
            },
            # 4. 第四策略: JPEG, normal quality, Device scale (后备)
            {
                "full_page": True,
                "type": "jpeg",
                "quality": 80,
                "scale": "device",
                # normal quality
            },
        ]

        last_exception = None
        for options in render_strategies:
            try:
                # Cleanse options
                if options.get("type") == "png":
                    options["quality"] = None

                logger.debug(f"调用 AstrBot html_renderer (options={options})...")
                path = await html_renderer.render_custom_template(
                    tmpl_str=html_content,
                    tmpl_data={},
                    return_url=False,
                    options=options,
                )
                logger.info(f"图片生成完成: {path}")

                # 验证: 检查文件是否为图片或错误文本
                if os.path.exists(path):
                    file_size = os.path.getsize(path)
                    if file_size < 1024:  # 小于1KB可疑
                        with open(path, "rb") as f:
                            content = f.read(100)

                        try:
                            text_content = content.decode("utf-8")
                            if "Error" in text_content or "Exception" in text_content:
                                logger.warning(f"渲染策略失败: {text_content}")
                                raise RuntimeError(f"渲染文件错误: {text_content}")
                        except UnicodeDecodeError:
                            # 二进制内容是好的
                            pass

                return path  # 成功，立即返回

            except Exception as e:
                logger.warning(f"渲染策略失败 ({options}): {e}")
                last_exception = e
                logger.warning("尝试下一个策略")
                continue  # 尝试下一个策略

        # 如果所有策略都失败
        logger.error(f"所有渲染策略均失败. 最后错误: {last_exception}")
        raise last_exception or RuntimeError("所有渲染策略均失败")
