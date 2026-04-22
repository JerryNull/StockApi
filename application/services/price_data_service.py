"""
應用層服務 - 協調基礎設施與業務邏輯。
"""
import logging
from typing import Dict, Iterable

import pandas as pd

from infrastructure.marketdata.repository import MarketDataRepository

logger = logging.getLogger(__name__)


class PriceDataService:
    """股票價格資料服務 - 對外的統一入口。"""

    def __init__(self, repository: MarketDataRepository):
        self._repository = repository
        self._remote_fetch_enabled = True

    def load_local_data(
        self,
        symbol: str,
        date_from: str,
        date_to: str,
    ) -> pd.DataFrame:
        """僅載入本地 CSV，不觸發遠端抓取。"""
        return self._repository.load_local(symbol, date_from, date_to)

    def fetch_history(
        self,
        symbols: list[str],
        date_from: str,
        date_to: str,
        save: bool = True,
    ) -> dict[str, pd.DataFrame]:
        """批次擷取股票歷史資料。"""
        return self._repository.fetch_batch(symbols, date_from, date_to, save=save)

    def get_symbol_data(
        self,
        symbol: str,
        date_from: str,
        date_to: str,
        save: bool = True,
    ) -> pd.DataFrame:
        """取得單支股票資料，優先查本地，不足才從 API 抓。"""
        dataframe = self._repository.load_local(symbol, date_from, date_to)
        if dataframe.empty and self._remote_fetch_enabled:
            try:
                dataframe = self._repository.fetch_candles(
                    symbol,
                    date_from,
                    date_to,
                    save=save,
                )
            except (ModuleNotFoundError, RuntimeError) as e:
                self._remote_fetch_enabled = False
                logger.warning(
                    '遠端資料抓取已停用：%s。後續將僅使用本地 CSV。',
                    e,
                )
        return dataframe

    def load_data_map(
        self,
        symbols: Iterable[str],
        date_from: str,
        date_to: str,
        save: bool = True,
    ) -> Dict[str, pd.DataFrame]:
        """載入多支股票的完整資料對映表。"""
        data_map: Dict[str, pd.DataFrame] = {}
        for symbol in symbols:
            dataframe = self.get_symbol_data(symbol, date_from, date_to, save=save)
            if not dataframe.empty:
                data_map[symbol] = dataframe
        return data_map
