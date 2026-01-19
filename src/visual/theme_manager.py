import os
from typing import Any

import yaml


class ThemeManager:
    """主题管理器，负责加载和切换渲染主题"""

    def __init__(self, plugin_root: str):
        self.plugin_root = plugin_root
        self.themes_dir = os.path.join(plugin_root, "assets", "themes")
        self.current_theme = "galgame"
        self._cache = {}

    def get_theme_config(self, theme_name: str = None) -> dict[str, Any]:
        """获取指定主题的配置信息 (从 config.yaml 读取)"""
        theme = theme_name or self.current_theme
        if theme in self._cache:
            return self._cache[theme]

        config_path = os.path.join(self.themes_dir, theme, "config.yaml")
        if not os.path.exists(config_path):
            raise ValueError(f"在 {config_path} 未找到主题 {theme}")

        with open(config_path, encoding="utf-8") as f:
            config = yaml.safe_load(f)

        self._cache[theme] = config
        return config

    def get_template_path(self, theme_name: str = None) -> str:
        """获取模板文件路径"""
        theme = theme_name or self.current_theme
        return os.path.join(self.themes_dir, theme, "template.html")

    def get_asset_dir(self, theme_name: str = None) -> str:
        """获取资源目录路径"""
        theme = theme_name or self.current_theme
        return os.path.join(self.themes_dir, theme, "assets")
