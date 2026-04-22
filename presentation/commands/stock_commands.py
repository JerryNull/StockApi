"""
CLI 指令層 — 所有使用者介面邏輯集中在此
透過 DI 容器獲取服務，不應直接呼叫業務層細節
"""
from datetime import date, timedelta
from pathlib import Path

import click


BASE_DIR = Path(__file__).parent.parent.parent


def _load_watchlist(watchlist: str) -> list:
    """解析逗號分隔的股票代號或讀取 .txt 檔案。"""
    p = Path(watchlist)
    if p.exists():
        symbols = [s.strip() for s in p.read_text(encoding='utf-8').split(',') if s.strip()]
    else:
        symbols = [s.strip() for s in watchlist.split(',') if s.strip()]
    return symbols


@click.group()
@click.option('--config', default=str(BASE_DIR / 'config.simulation.ini'),
              show_default=True, help='設定檔路徑')
@click.pass_context
def cli(ctx, config):
    """台股波段策略 CLI — 資料擷取、指標計算、選股、回測一站式工具。"""
    from app_container import build_container

    ctx.ensure_object(dict)
    ctx.obj['container'] = build_container(config)


@cli.command()
@click.option('--symbols', default=str(BASE_DIR / 'watchlist.production.txt'),
              show_default=True, help='股票代號（逗號分隔）或 .txt 檔路徑')
@click.option('--from', 'date_from', default=(date.today() - timedelta(days=365)).strftime('%Y-%m-%d'),
              show_default=True, help='起始日期 YYYY-MM-DD')
@click.option('--to', 'date_to', default=date.today().strftime('%Y-%m-%d'),
              show_default=True, help='結束日期 YYYY-MM-DD')
@click.option('--no-save', is_flag=True, help='不儲存 CSV')
@click.pass_context
def fetch(ctx, symbols, date_from, date_to, no_save):
    """擷取歷史 K 線資料並存至 data/ 目錄。"""
    container = ctx.obj['container']
    symbol_list = _load_watchlist(symbols)
    click.echo(f'擷取股票：{symbol_list}，期間：{date_from} ~ {date_to}')
    data_map = container.price_data_service.fetch_history(
        symbol_list,
        date_from,
        date_to,
        save=not no_save,
    )
    click.echo(f'完成！取得 {len(data_map)} 支股票資料。')


@cli.command()
@click.option('--symbol', required=True, help='股票代號，如 2330')
@click.option('--from', 'date_from', default=(date.today() - timedelta(days=365)).strftime('%Y-%m-%d'),
              show_default=True, help='起始日期')
@click.option('--to', 'date_to', default=date.today().strftime('%Y-%m-%d'),
              show_default=True, help='結束日期')
@click.pass_context
def indicators(ctx, symbol, date_from, date_to):
    """計算技術指標並顯示最新 10 列。"""
    import pandas as pd

    from domain.indicators.indicators import add_all

    container = ctx.obj['container']

    df = container.price_data_service.load_local_data(symbol, date_from, date_to)
    if df.empty:
        click.echo('本地無資料，從 API 擷取...')
        df = container.price_data_service.get_symbol_data(symbol, date_from, date_to)

    if df.empty:
        click.echo(f'無法取得 {symbol} 資料。')
        return

    df = add_all(df)
    pd.set_option('display.float_format', '{:.2f}'.format)
    click.echo(df[['close', 'ma5', 'ma20', 'ma60', 'rsi', 'macd_hist', 'k', 'd', 'vol_ma20']].tail(10).to_string())


@cli.command()
@click.option('--symbols', default=str(BASE_DIR / 'watchlist.production.txt'),
              show_default=True, help='股票代號或 .txt 檔路徑')
@click.option('--from', 'date_from', default=(date.today() - timedelta(days=400)).strftime('%Y-%m-%d'),
              show_default=True, help='歷史資料起始日期')
@click.option('--rsi-threshold', default=30.0, show_default=True, help='RSI 超賣閾值')
@click.option('--vol-ratio', default=1.5, show_default=True, help='成交量放大倍數')
@click.option('--min-hits', default=2, show_default=True, help='最少符合幾個條件')
@click.option('--no-save', is_flag=True, help='不儲存 CSV')
@click.pass_context
def scan(ctx, symbols, date_from, rsi_threshold, vol_ratio, min_hits, no_save):
    """對監控股票執行每日選股篩選。"""
    from domain.scanner.scanner import scan as run_scan

    container = ctx.obj['container']
    symbol_list = _load_watchlist(symbols)
    date_to = date.today().strftime('%Y-%m-%d')

    click.echo(f'載入 {len(symbol_list)} 支股票資料...')
    data_map = container.price_data_service.load_data_map(
        symbol_list,
        date_from,
        date_to,
        save=not no_save,
    )

    conditions = {
        'rsi_threshold': rsi_threshold,
        'vol_ratio': vol_ratio,
        'min_hits': min_hits,
    }
    result = run_scan(data_map, conditions=conditions, save=not no_save)

    if result.empty:
        click.echo('今日無符合條件的股票。')
    else:
        click.echo(f'\n=== 選股結果（共 {len(result)} 筆）===')
        click.echo(result.to_string(index=False))


@cli.command()
@click.option('--symbols', default=str(BASE_DIR / 'watchlist.production.txt'),
              show_default=True, help='股票代號或 .txt 檔路徑')
@click.option('--from', 'date_from', default=(date.today() - timedelta(days=400)).strftime('%Y-%m-%d'),
              show_default=True, help='歷史資料起始日期')
@click.option('--stop-loss', default=0.07, show_default=True, help='停損比例（如 0.07 = 7%）')
@click.option('--take-profit', default=0.15, show_default=True, help='停利比例（如 0.15 = 15%）')
@click.pass_context
def signal(ctx, symbols, date_from, stop_loss, take_profit):
    """產生個股進出場訊號。"""
    from domain.signal.signal import generate_signals_batch

    container = ctx.obj['container']
    symbol_list = _load_watchlist(symbols)
    date_to = date.today().strftime('%Y-%m-%d')

    data_map = container.price_data_service.load_data_map(symbol_list, date_from, date_to)

    results = generate_signals_batch(data_map, stop_loss=stop_loss, take_profit=take_profit)
    click.echo(f'訊號產生完成，共處理 {len(results)} 支股票。')


@cli.command()
@click.option('--symbols', default=str(BASE_DIR / 'watchlist.production.txt'),
              show_default=True, help='股票代號或 .txt 檔路徑')
@click.option('--from', 'date_from', default=(date.today() - timedelta(days=730)).strftime('%Y-%m-%d'),
              show_default=True, help='回測起始日期')
@click.option('--to', 'date_to', default=date.today().strftime('%Y-%m-%d'),
              show_default=True, help='回測結束日期')
@click.option('--stop-loss', default=0.07, show_default=True)
@click.option('--take-profit', default=0.15, show_default=True)
@click.option('--no-plot', is_flag=True, help='不產生圖表')
@click.pass_context
def backtest(ctx, symbols, date_from, date_to, stop_loss, take_profit, no_plot):
    """執行歷史回測並輸出績效報告。"""
    from domain.backtest.backtest import run_backtest_batch

    container = ctx.obj['container']
    symbol_list = _load_watchlist(symbols)

    data_map = container.price_data_service.load_data_map(
        symbol_list,
        date_from,
        date_to,
        save=True,
    )

    summary = run_backtest_batch(data_map, stop_loss=stop_loss, take_profit=take_profit, plot=not no_plot)

    if summary.empty:
        click.echo('無足夠資料進行回測。')
    else:
        click.echo(f'\n=== 回測績效彙整 ===')
        click.echo(summary.to_string(index=False))


@cli.command()
@click.option('--symbols', default=str(BASE_DIR / 'watchlist.production.txt'),
              show_default=True)
@click.pass_context
def run(ctx, symbols):
    """執行完整流程：擷取 → 指標 → 選股（今日）。"""
    from domain.scanner.scanner import scan as run_scan

    container = ctx.obj['container']
    symbol_list = _load_watchlist(symbols)
    date_to = date.today().strftime('%Y-%m-%d')
    date_from = (date.today() - timedelta(days=400)).strftime('%Y-%m-%d')

    click.echo(f'[1/2] 擷取 {len(symbol_list)} 支股票資料...')
    data_map = container.price_data_service.fetch_history(symbol_list, date_from, date_to)

    click.echo('[2/2] 執行選股篩選...')
    result = run_scan(data_map)

    if result.empty:
        click.echo('今日無符合條件的股票。')
    else:
        click.echo(f'\n=== 今日選股結果（共 {len(result)} 筆）===')
        click.echo(result.to_string(index=False))
