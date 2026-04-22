"""
玉山 SDK 的統一封裝，隔離外部依賴。
"""
from configparser import ConfigParser

from esun_marketdata import EsunMarketdata


def get_sdk(config: ConfigParser) -> EsunMarketdata:
    """建立並登入玉山 SDK 實例。"""
    sdk = EsunMarketdata(config)
    sdk.login()
    return sdk
