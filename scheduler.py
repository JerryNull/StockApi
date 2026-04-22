"""
scheduler.py — 盤前自動排程設定
每日 08:30 自動執行選股流程

使用方式：
    python scheduler.py                    # 前景執行（Ctrl+C 停止）
    python scheduler.py --run-now          # 立即執行一次後繼續排程
    python scheduler.py --config prod.ini  # 指定設定檔
"""
import logging
import subprocess
import sys
from pathlib import Path
from datetime import date

try:
    from apscheduler.schedulers.blocking import BlockingScheduler
    from apscheduler.triggers.cron import CronTrigger
except ImportError:
    print('請先安裝 APScheduler：pip install apscheduler')
    sys.exit(1)

import click

BASE_DIR = Path(__file__).parent
LOG_DIR = Path(r'D:\StockApiLog')
LOG_DIR.mkdir(exist_ok=True)

logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s [%(levelname)s] %(message)s',
    handlers=[
        logging.StreamHandler(sys.stdout),
        logging.FileHandler(LOG_DIR / 'scheduler.log', encoding='utf-8'),
    ],
)
logger = logging.getLogger('scheduler')


def run_scan_job(config_path: str, symbols_path: str):
    """排程任務：呼叫 main.py run 指令。"""
    logger.info('排程觸發：執行選股流程...')
    cmd = [
        sys.executable,
        str(BASE_DIR / 'main.py'),
        '--config', config_path,
        'run',
        '--symbols', symbols_path,
    ]
    try:
        result = subprocess.run(cmd, capture_output=True, text=True, encoding='utf-8', timeout=600)
        if result.stdout:
            logger.info(f'輸出：\n{result.stdout}')
        if result.stderr:
            logger.warning(f'錯誤：\n{result.stderr}')
        logger.info(f'選股流程完成，結束碼：{result.returncode}')
    except subprocess.TimeoutExpired:
        logger.error('選股流程超時（10 分鐘）')
    except Exception as e:
        logger.error(f'選股流程執行失敗：{e}')


@click.command()
@click.option('--config', default=str(BASE_DIR / 'config.simulation.ini'),
              show_default=True, help='設定檔路徑')
@click.option('--symbols', default=str(BASE_DIR / 'watchlist.production.txt'),
              show_default=True, help='自選股清單')
@click.option('--hour', default=8, show_default=True, help='排程執行小時（24h）')
@click.option('--minute', default=30, show_default=True, help='排程執行分鐘')
@click.option('--run-now', is_flag=True, help='立即執行一次後繼續排程')
def main(config, symbols, hour, minute, run_now):
    """台股波段策略 — 盤前自動排程（每日 08:30 執行選股）。"""
    scheduler = BlockingScheduler(timezone='Asia/Taipei')

    scheduler.add_job(
        run_scan_job,
        trigger=CronTrigger(
            day_of_week='mon-fri',
            hour=hour,
            minute=minute,
            timezone='Asia/Taipei',
        ),
        args=[config, symbols],
        id='daily_scan',
        name='每日選股',
        replace_existing=True,
    )

    logger.info(f'排程已設定：週一至週五 {hour:02d}:{minute:02d} 自動執行選股')

    if run_now:
        logger.info('立即執行一次...')
        run_scan_job(config, symbols)

    try:
        scheduler.start()
    except (KeyboardInterrupt, SystemExit):
        logger.info('排程已停止')


if __name__ == '__main__':
    main()
