"""
main.py — 台股波段策略 CLI 入口點
使用方式：python main.py --help
"""
import logging
import sys
from datetime import date
from pathlib import Path

BASE_DIR = Path(__file__).parent

# ── 日誌設定 ──────────────────────────────────────────────────────────────────
LOG_DIR = Path(r'D:\StockApiLog')
LOG_DIR.mkdir(exist_ok=True)

logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s [%(levelname)s] %(name)s: %(message)s',
    handlers=[
        logging.StreamHandler(sys.stdout),
        logging.FileHandler(
            LOG_DIR / f'strategy_{date.today().strftime("%Y%m%d")}.log',
            encoding='utf-8'
        ),
    ],
)
logger = logging.getLogger('main')


if __name__ == '__main__':
    try:
        import click
    except ImportError:
        print('請先安裝 click：pip install click')
        sys.exit(1)

    from presentation.commands.stock_commands import cli

    cli()
