from astrbot.core import html_renderer
from astrbot.core.log import LogManager
from jinja2 import Environment, FileSystemLoader
from astrbot.core.star.context import Context
from .theme_manager import ThemeManager

logger = LogManager.GetLogger("astrbot_plugin_love_formula.renderer")


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

        # 1. 加载模板
        template_name = f"{theme_name}/template.html"
        try:
            template = self.env.get_template(template_name)
        except Exception as e:
            logger.error(f"模板加载失败: {e}")
            raise

        # 2. 渲染内容
        try:
            html_content = template.render(
                data=data,
                theme_config=self.theme_manager.get_theme_config(theme_name),
                asset_dir=f"file://{self.theme_manager.get_asset_dir(theme_name)}",
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
                    "clip": {"x": 0, "y": 0, "width": 540, "height": 850},
                },
            )
            logger.info(f"图片生成完成: {path}")
            return path
        except Exception as e:
            logger.error(f"AstrBot 渲染引擎调用失败: {e}")
            raise
