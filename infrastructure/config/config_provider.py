from configparser import ConfigParser


class ConfigProvider:
    """統一管理應用設定，避免重複載入。"""

    def __init__(self, config_path: str):
        self._config_path = config_path
        self._config: ConfigParser | None = None

    @property
    def config_path(self) -> str:
        return self._config_path

    def get_config(self) -> ConfigParser:
        """惰性載入設定，避免重複讀檔。"""
        if self._config is None:
            config = ConfigParser()
            config.read(self._config_path, encoding='utf-8')
            if not config.sections():
                raise FileNotFoundError(f'找不到設定檔：{self._config_path}')
            self._config = config
        return self._config
