"""
web_app.py — 台股波段策略 Web 介面入口
使用方式：python web_app.py
"""
from datetime import date, timedelta
import time
from pathlib import Path

from flask import Flask, request, render_template_string

from app_container import build_container
from domain.backtest.backtest import run_backtest_batch
from domain.indicators.indicators import add_all
from domain.scanner.scanner import scan as run_scan
from domain.signal.signal import generate_signals_batch

BASE_DIR = Path(__file__).parent


def _load_watchlist(watchlist: str) -> list[str]:
    p = Path(watchlist)
    if p.exists():
        return [s.strip() for s in p.read_text(encoding='utf-8').split(',') if s.strip()]
    return [s.strip() for s in watchlist.split(',') if s.strip()]


def _to_bool(value: str | None, default: bool = False) -> bool:
    if value is None:
        return default
    return value.lower() in {'1', 'true', 'on', 'yes'}


def _to_float(value: str | None, default: float) -> float:
  try:
    return float(value) if value not in (None, '') else default
  except ValueError:
    return default


def _to_int(value: str | None, default: int) -> int:
  try:
    return int(value) if value not in (None, '') else default
  except ValueError:
    return default


HTML = """
<!doctype html>
<html lang="zh-Hant">
<head>
  <meta charset="utf-8" />
  <meta name="viewport" content="width=device-width, initial-scale=1" />
  <title>台股波段策略 Web 操作台</title>
  <style>
    :root {
      --bg: #f3f6fb;
      --card: #ffffff;
      --text: #182230;
      --muted: #607086;
      --line: #dde5f1;
      --pri: #2f6feb;
      --pri-d: #2459bd;
      --ok: #0f9d58;
      --err: #d93025;
    }
    body { font-family: "Segoe UI", Arial, sans-serif; margin: 24px; background: var(--bg); color: var(--text); }
    .wrap { max-width: 1200px; margin: 0 auto; }
    .card { background: var(--card); border-radius: 12px; padding: 18px; margin-bottom: 16px; box-shadow: 0 4px 16px rgba(12, 37, 76, .08); }
    h1 { margin: 0 0 8px 0; }
    .subtitle { color: var(--muted); margin: 0; }
    .grid { display: grid; grid-template-columns: repeat(2, minmax(260px, 1fr)); gap: 12px; }
    .section-title { font-size: 13px; color: var(--muted); margin: 4px 0 2px 0; }
    label { display: block; font-size: 13px; margin-bottom: 4px; color: #3a4a5f; }
    input, select, textarea { width: 100%; padding: 8px 10px; border: 1px solid #ccd7e6; border-radius: 8px; font-size: 14px; box-sizing: border-box; }
    input:focus, select:focus, textarea:focus { outline: none; border-color: var(--pri); box-shadow: 0 0 0 3px rgba(47,111,235,.15); }
    textarea { min-height: 88px; resize: vertical; }
    .full { grid-column: 1 / -1; }
    .toolbar { display: flex; gap: 8px; flex-wrap: wrap; margin-top: 10px; }
    .btn { border: none; padding: 10px 14px; border-radius: 9px; cursor: pointer; font-weight: 600; }
    .btn-primary { background: var(--pri); color: #fff; }
    .btn-primary:hover { background: var(--pri-d); }
    .btn-soft { background: #edf3ff; color: #2c4f94; }
    .btn-soft:hover { background: #dce9ff; }
    .switch { display: flex; align-items: center; gap: 8px; margin-top: 2px; }
    .switch input { width: auto; transform: scale(1.1); }
    .badge { display: inline-block; padding: 3px 8px; border-radius: 999px; font-size: 12px; background: #eef3ff; color: #345ba8; }
    table { border-collapse: collapse; width: 100%; font-size: 13px; }
    th, td { border: 1px solid var(--line); padding: 6px 8px; text-align: right; }
    th:first-child, td:first-child { text-align: left; }
    .msg { white-space: pre-wrap; background: #0f1730; color: #d8e6ff; padding: 12px; border-radius: 8px; }
    .note { color: var(--muted); font-size: 13px; }
    .ok { color: var(--ok); }
    .err { color: var(--err); }
    .meta { display: flex; gap: 12px; flex-wrap: wrap; font-size: 13px; color: var(--muted); margin-top: 8px; }
    #loading { display:none; margin-top: 8px; color: #2f6feb; font-weight: 600; }
    @media (max-width: 860px) {
      .grid { grid-template-columns: 1fr; }
    }
  </style>
</head>
<body>
  <div class="wrap">
  <div class="card">
    <h1>台股波段策略 Web 操作台</h1>
    <p class="subtitle">支援：fetch / indicators / scan / signal / backtest / run</p>
    <div class="toolbar">
      <button type="button" class="btn btn-soft" onclick="setSymbols('2330,2454,3105')">快速填入：大型股</button>
      <button type="button" class="btn btn-soft" onclick="setSymbols('{{ defaults.symbols }}')">還原預設清單</button>
      <span class="badge" id="actionHint">目前：{{ defaults.action }}</span>
    </div>
    <form method="post" action="/execute" id="mainForm">
      <div class="grid">
        <div class="full section-title">基本設定</div>
        <div>
          <label>設定檔路徑</label>
          <input name="config" value="{{ defaults.config }}" />
        </div>
        <div>
          <label>操作項目</label>
          <select name="action" id="actionSelect" onchange="updateActionHint()">
            {% for a in ['fetch','indicators','scan','signal','backtest','run'] %}
            <option value="{{ a }}" {% if defaults.action == a %}selected{% endif %}>{{ a }}</option>
            {% endfor %}
          </select>
        </div>

        <div class="full section-title">股票與時間範圍</div>
        <div class="full">
          <label>股票清單（逗號分隔或 .txt 路徑）</label>
          <textarea id="symbolsInput" name="symbols" placeholder="例如：2330,2454 或 watchlist.txt">{{ defaults.symbols }}</textarea>
        </div>

        <div>
          <label>單一股票代號（indicators 用）</label>
          <input name="symbol" value="{{ defaults.symbol }}" />
        </div>
        <div>
          <label>起始日期（YYYY-MM-DD）</label>
          <input name="date_from" value="{{ defaults.date_from }}" />
        </div>
        <div>
          <label>結束日期（YYYY-MM-DD）</label>
          <input name="date_to" value="{{ defaults.date_to }}" />
        </div>

        <div class="full section-title">策略參數</div>
        <div>
          <label>RSI 閾值（scan）</label>
          <input name="rsi_threshold" value="{{ defaults.rsi_threshold }}" />
        </div>
        <div>
          <label>量能倍數（scan）</label>
          <input name="vol_ratio" value="{{ defaults.vol_ratio }}" />
        </div>
        <div>
          <label>最少命中條件（scan）</label>
          <input name="min_hits" value="{{ defaults.min_hits }}" />
        </div>
        <div>
          <label>停損比例（signal/backtest）</label>
          <input name="stop_loss" value="{{ defaults.stop_loss }}" />
        </div>
        <div>
          <label>停利比例（signal/backtest）</label>
          <input name="take_profit" value="{{ defaults.take_profit }}" />
        </div>
        <div>
          <label>儲存輸出</label>
          <div class="switch"><input type="checkbox" name="save" value="1" {% if defaults.save == '1' %}checked{% endif %} /> <span>啟用</span></div>
        </div>
        <div>
          <label>產生圖表（backtest）</label>
          <div class="switch"><input type="checkbox" name="plot" value="1" {% if defaults.plot == '1' %}checked{% endif %} /> <span>啟用</span></div>
        </div>
      </div>
      <div class="toolbar">
        <button type="submit" class="btn btn-primary">執行</button>
        <button type="button" class="btn btn-soft" onclick="document.getElementById('mainForm').reset(); updateActionHint();">重設</button>
      </div>
      <div id="loading">執行中，請稍候...</div>
    </form>
  </div>

  {% if message %}
  <div class="card">
    <h3>執行結果</h3>
    <div class="msg">{{ message }}</div>
    <div class="meta">
      {% if elapsed_ms is not none %}<div>耗時：{{ elapsed_ms }} ms</div>{% endif %}
      {% if action_name %}<div>操作：{{ action_name }}</div>{% endif %}
      {% if result_rows is not none %}<div>筆數：{{ result_rows }}</div>{% endif %}
    </div>
  </div>
  {% endif %}

  {% if table_html %}
  <div class="card">
    <h3>資料表</h3>
    {{ table_html | safe }}
  </div>
  {% endif %}
  </div>

  <script>
    function setSymbols(v) {
      document.getElementById('symbolsInput').value = v;
    }

    function updateActionHint() {
      const action = document.getElementById('actionSelect').value;
      document.getElementById('actionHint').textContent = `目前：${action}`;
    }

    document.getElementById('mainForm').addEventListener('submit', function() {
      document.getElementById('loading').style.display = 'block';
    });
  </script>
</body>
</html>
"""


def create_app() -> Flask:
    app = Flask(__name__)

    @app.get('/')
    def index():
        defaults = {
            'config': str(BASE_DIR / 'config.simulation.ini'),
            'action': 'scan',
            'symbols': str(BASE_DIR / 'watchlist.txt'),
            'symbol': '2330',
            'date_from': (date.today() - timedelta(days=400)).strftime('%Y-%m-%d'),
            'date_to': date.today().strftime('%Y-%m-%d'),
            'rsi_threshold': '30',
            'vol_ratio': '1.5',
            'min_hits': '2',
            'stop_loss': '0.07',
            'take_profit': '0.15',
            'save': '1',
            'plot': '0',
        }
        return render_template_string(
          HTML,
          defaults=defaults,
          message='',
          table_html='',
          elapsed_ms=None,
          action_name='',
          result_rows=None,
        )

    @app.post('/execute')
    def execute():
        form = request.form
        config_path = form.get('config', str(BASE_DIR / 'config.simulation.ini'))
        action = form.get('action', 'scan')
        symbols = form.get('symbols', str(BASE_DIR / 'watchlist.txt'))
        symbol = form.get('symbol', '2330')
        date_from = form.get('date_from', (date.today() - timedelta(days=400)).strftime('%Y-%m-%d'))
        date_to = form.get('date_to', date.today().strftime('%Y-%m-%d'))
        rsi_threshold = _to_float(form.get('rsi_threshold', '30'), default=30.0)
        vol_ratio = _to_float(form.get('vol_ratio', '1.5'), default=1.5)
        min_hits = _to_int(form.get('min_hits', '2'), default=2)
        stop_loss = _to_float(form.get('stop_loss', '0.07'), default=0.07)
        take_profit = _to_float(form.get('take_profit', '0.15'), default=0.15)
        save = _to_bool(form.get('save'), default=False)
        plot = _to_bool(form.get('plot'), default=False)

        defaults = {
            'config': config_path,
            'action': action,
            'symbols': symbols,
            'symbol': symbol,
            'date_from': date_from,
            'date_to': date_to,
            'rsi_threshold': str(rsi_threshold),
            'vol_ratio': str(vol_ratio),
            'min_hits': str(min_hits),
            'stop_loss': str(stop_loss),
            'take_profit': str(take_profit),
            'save': '1' if save else '0',
            'plot': '1' if plot else '0',
        }

        container = build_container(config_path)
        table_html = ''
        start = time.perf_counter()
        result_rows = None

        try:
            if action == 'fetch':
                symbol_list = _load_watchlist(symbols)
                data_map = container.price_data_service.fetch_history(symbol_list, date_from, date_to, save=save)
                message = f'完成！取得 {len(data_map)} 支股票資料。'
                result_rows = len(data_map)

            elif action == 'indicators':
                df = container.price_data_service.load_local_data(symbol, date_from, date_to)
                if df.empty:
                    df = container.price_data_service.get_symbol_data(symbol, date_from, date_to, save=save)
                if df.empty:
                    message = f'無法取得 {symbol} 資料。'
                else:
                    view_df = add_all(df)
                    cols = ['close', 'ma5', 'ma20', 'ma60', 'rsi', 'macd_hist', 'k', 'd', 'vol_ma20']
                    table_html = view_df[cols].tail(10).to_html(classes='table', border=0)
                    message = f'{symbol} 指標計算完成。'
                    result_rows = min(10, len(view_df))

            elif action == 'scan':
                symbol_list = _load_watchlist(symbols)
                data_map = container.price_data_service.load_data_map(symbol_list, date_from, date_to, save=save)
                conditions = {
                    'rsi_threshold': rsi_threshold,
                    'vol_ratio': vol_ratio,
                    'min_hits': min_hits,
                }
                result = run_scan(data_map, conditions=conditions, save=save)
                if result.empty:
                    message = '今日無符合條件的股票。'
                    result_rows = 0
                else:
                    table_html = result.to_html(index=False, classes='table', border=0)
                    message = f'選股完成，共 {len(result)} 筆。'
                    result_rows = len(result)

            elif action == 'signal':
                symbol_list = _load_watchlist(symbols)
                data_map = container.price_data_service.load_data_map(symbol_list, date_from, date_to, save=save)
                results = generate_signals_batch(data_map, stop_loss=stop_loss, take_profit=take_profit, save=save)
                rows = []
                for sym, sig_df in results.items():
                    rows.append({'symbol': sym, 'entries': int((sig_df['signal'] == 1).sum())})
                if rows:
                    import pandas as pd
                    table_html = pd.DataFrame(rows).to_html(index=False, classes='table', border=0)
                message = f'訊號產生完成，共處理 {len(results)} 支股票。'
                result_rows = len(rows)

            elif action == 'backtest':
                symbol_list = _load_watchlist(symbols)
                data_map = container.price_data_service.load_data_map(symbol_list, date_from, date_to, save=True)
                summary = run_backtest_batch(data_map, stop_loss=stop_loss, take_profit=take_profit, plot=plot)
                if summary.empty:
                    message = '無足夠資料進行回測。'
                    result_rows = 0
                else:
                    table_html = summary.to_html(index=False, classes='table', border=0)
                    message = '回測完成。'
                    result_rows = len(summary)

            elif action == 'run':
                symbol_list = _load_watchlist(symbols)
                run_from = (date.today() - timedelta(days=400)).strftime('%Y-%m-%d')
                run_to = date.today().strftime('%Y-%m-%d')
                data_map = container.price_data_service.fetch_history(symbol_list, run_from, run_to)
                result = run_scan(data_map)
                if result.empty:
                    message = '今日無符合條件的股票。'
                    result_rows = 0
                else:
                    table_html = result.to_html(index=False, classes='table', border=0)
                    message = f'完整流程完成，共 {len(result)} 筆。'
                    result_rows = len(result)
            else:
                message = f'未知操作：{action}'

        except Exception as e:
            message = f'執行失敗：{e}'

        elapsed_ms = int((time.perf_counter() - start) * 1000)
        return render_template_string(
            HTML,
            defaults=defaults,
            message=message,
            table_html=table_html,
            elapsed_ms=elapsed_ms,
            action_name=action,
            result_rows=result_rows,
        )

    return app


if __name__ == '__main__':
    app = create_app()
    app.run(host='127.0.0.1', port=5000, debug=True)
