from dataclasses import dataclass

from infrastructure.config.config_provider import ConfigProvider
from infrastructure.marketdata.repository import MarketDataRepository
from application.services.price_data_service import PriceDataService


@dataclass
class AppContainer:
    """應用程式的依賴注入容器。"""
    config_provider: ConfigProvider
    price_data_service: PriceDataService


def build_container(config_path: str) -> AppContainer:
    """建立並配置應用程式容器。"""
    config_provider = ConfigProvider(config_path)
    repository = MarketDataRepository(config_provider)
    price_data_service = PriceDataService(repository)

    return AppContainer(
        config_provider=config_provider,
        price_data_service=price_data_service,
    )
