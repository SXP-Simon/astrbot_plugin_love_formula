from astrbot.core import html_renderer
from astrbot.core.log import LogManager
from jinja2 import Environment, FileSystemLoader
from astrbot.core.star.context import Context
from .theme_manager import ThemeManager

logger = LogManager.GetLogger("astrbot_plugin_love_formula.renderer")


class LoveRenderer:
    def __init__(self, context: Context, theme_manager: ThemeManager):
        self.context = context
        self.theme_manager = theme_manager
        # Initialize Jinja2 Env
        self.env = Environment(loader=FileSystemLoader(theme_manager.themes_dir))

    async def render(self, data: dict, theme_name: str = "galgame") -> str:
        """
        Render the analysis result to an image.
        Returns: absolute path to the generated image file.
        """
        logger.info(f"开始渲染图片，主题: {theme_name}")

        # 1. Load Template
        template_name = f"{theme_name}/template.html"
        try:
            template = self.env.get_template(template_name)
        except Exception as e:
            logger.error(f"模板加载失败: {e}")
            raise

        # 2. Inject Data & KaTeX CDN (or local)
        # We ensure KaTeX is enabled in the template

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

        # 3. Use AstrBot's HTML Renderer
        # 使用 astrbot.core.html_renderer 全局实例

        try:
            logger.debug("调用 AstrBot html_renderer...")
            # 将生成的 HTML 作为模板字符串传递，数据为空（因为已经渲染过了）
            # 注意：这要求 html_renderer 能够处理已经是 HTML 的内容
            path = await html_renderer.render_custom_template(
                tmpl_str=html_content,
                tmpl_data={},
                return_url=False,
                options={"type": "jpeg", "quality": 95},
            )
            logger.info(f"图片生成完成: {path}")
            return path
        except Exception as e:
            logger.error(f"AstrBot 渲染引擎调用失败: {e}")
            raise
