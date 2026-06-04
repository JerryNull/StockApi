"""
產業別 Dashboard 服務
- get_sector_summaries()：取得所有產業漲跌彙總
- get_stocks_in_sector(industry_code)：取得特定產業下各股交易量
"""
import csv
import glob
import os
import time
from concurrent.futures import ThreadPoolExecutor, as_completed
from datetime import datetime

INDUSTRY_CODE_MAP = {
    "01": "水泥工業", "02": "食品工業", "03": "塑膠工業",
    "04": "紡織纖維", "05": "電機機械", "06": "電器電纜",
    "07": "化學生技醫療", "08": "玻璃陶瓷", "09": "造紙工業",
    "10": "鋼鐵工業", "11": "橡膠工業", "12": "汽車工業",
    "13": "電子工業", "14": "建材營造", "15": "航運業",
    "16": "觀光餐旅", "17": "金融保險", "18": "貿易百貨",
    "19": "綜合", "20": "其他", "21": "化學工業",
    "22": "生技醫療業", "23": "油電燃氣業", "24": "半導體業",
    "25": "電腦及週邊設備業", "26": "光電業", "27": "通信網路業",
    "28": "電子零組件業", "29": "電子通路業", "30": "資訊服務業",
    "31": "其他電子業", "32": "文化創意業", "33": "農業科技業",
    "34": "電子商務", "36": "存託憑證", "38": "運動休閒業",
    "80": "管理股票",
}


class SectorService:
    def __init__(self, rest_stock, data_dir=None):
        self._rest = rest_stock
        self._cache = {}          # { key: (timestamp, data) }
        self._cache_ttl = 300     # 5 分鐘快取
        base_dir = os.path.dirname(os.path.abspath(__file__))
        self._data_dir = data_dir or os.path.abspath(os.path.join(base_dir, '..', '..', '..', 'data'))
        self._symbol_industry_map = None
        self._history_cache = {}

    def _now_text(self):
        return datetime.now().strftime('%Y-%m-%d %H:%M:%S')

    def _cached(self, key, fn):
        now = time.time()
        if key in self._cache:
            ts, data = self._cache[key]
            if now - ts < self._cache_ttl:
                return data
        data = fn()
        self._cache[key] = (now, data)
        return data

    def _get_snapshot(self, market):
        try:
            result = self._rest.snapshot.quotes(market=market)
            return result.get('data', []) if isinstance(result, dict) else []
        except Exception:
            return []

    def _get_tickers_by_industry(self, exchange, code):
        try:
            result = self._rest.intraday.tickers(
                type='EQUITY', exchange=exchange, industry=code
            )
            return result.get('data', []) if isinstance(result, dict) else []
        except Exception:
            return []

    def _load_csv_rows(self, file_path):
        rows = []
        try:
            with open(file_path, 'r', encoding='utf-8-sig', newline='') as handle:
                reader = csv.DictReader(handle)
                for row in reader:
                    trade_date = row.get('date')
                    if not trade_date:
                        continue
                    try:
                        close = float(row.get('close') or 0)
                        volume = float(row.get('volume') or 0)
                    except (TypeError, ValueError):
                        continue
                    rows.append({
                        'date': trade_date,
                        'close': close,
                        'volume': volume,
                    })
        except Exception:
            return []
        return rows

    def _load_stock_history(self, symbol):
        if symbol in self._history_cache:
            return self._history_cache[symbol]

        pattern = os.path.join(self._data_dir, f'{symbol}_*.csv')
        combined = {}
        for file_path in sorted(glob.glob(pattern)):
            for row in self._load_csv_rows(file_path):
                combined[row['date']] = row

        history = sorted(combined.values(), key=lambda row: row['date'])
        self._history_cache[symbol] = history
        return history

    def _get_symbol_industry_map(self):
        if self._symbol_industry_map is None:
            self._symbol_industry_map = self._build_symbol_industry_map()
        return self._symbol_industry_map

    def _build_snapshot_sector_summaries(self):
        tse = self._get_snapshot('TSE')
        otc = self._get_snapshot('OTC')
        all_quotes = tse + otc
        sym_map = self._get_symbol_industry_map()

        groups = {}
        for q in all_quotes:
            sym = q.get('symbol', '')
            code = sym_map.get(sym)
            if not code:
                continue
            pct = q.get('changePercent')
            vol = q.get('tradeVolume', 0) or 0
            if pct is None:
                continue
            if code not in groups:
                groups[code] = {'pcts': [], 'volume': 0, 'count': 0}
            groups[code]['pcts'].append(float(pct))
            groups[code]['volume'] += int(vol)
            groups[code]['count'] += 1

        result = []
        for code, g in groups.items():
            avg = round(sum(g['pcts']) / len(g['pcts']), 2) if g['pcts'] else 0
            result.append({
                'industryCode': code,
                'industryName': INDUSTRY_CODE_MAP.get(code, code),
                'avgChangePercent': avg,
                'totalVolume': g['volume'],
                'stockCount': g['count'],
                'periodStart': None,
                'periodEnd': None,
            })

        return {
            'meta': {
                'source': 'snapshot',
                'periodDays': 1,
                'updatedAt': self._now_text(),
                'asOfDate': None,
                'historyStartDate': None,
                'historyEndDate': None,
            },
            'data': sorted(result, key=lambda x: x['avgChangePercent'], reverse=True),
        }

    def _build_historical_sector_summaries(self, days):
        sym_map = self._get_symbol_industry_map()
        groups = {}
        date_ranges = []

        for sym, code in sym_map.items():
            history = self._load_stock_history(sym)
            if len(history) < 2:
                continue

            recent = history[-days:] if len(history) > days else history[:]
            if len(recent) < 2:
                continue

            first_close = recent[0]['close']
            last_close = recent[-1]['close']
            if not first_close:
                continue

            period_change = round(((last_close - first_close) / first_close) * 100, 2)
            period_volume = int(sum(item['volume'] for item in recent))

            if code not in groups:
                groups[code] = {
                    'pcts': [],
                    'volume': 0,
                    'count': 0,
                    'start_dates': [],
                    'end_dates': [],
                }

            groups[code]['pcts'].append(period_change)
            groups[code]['volume'] += period_volume
            groups[code]['count'] += 1
            groups[code]['start_dates'].append(recent[0]['date'])
            groups[code]['end_dates'].append(recent[-1]['date'])
            date_ranges.append(recent[-1]['date'])

        result = []
        for code, g in groups.items():
            avg = round(sum(g['pcts']) / len(g['pcts']), 2) if g['pcts'] else 0
            result.append({
                'industryCode': code,
                'industryName': INDUSTRY_CODE_MAP.get(code, code),
                'avgChangePercent': avg,
                'totalVolume': g['volume'],
                'stockCount': g['count'],
                'periodStart': min(g['start_dates']) if g['start_dates'] else None,
                'periodEnd': max(g['end_dates']) if g['end_dates'] else None,
            })

        latest_date = max(date_ranges) if date_ranges else None
        earliest_date = min(date_ranges) if date_ranges else None

        return {
            'meta': {
                'source': 'historical',
                'periodDays': days,
                'updatedAt': self._now_text(),
                'asOfDate': latest_date,
                'historyStartDate': earliest_date,
                'historyEndDate': latest_date,
            },
            'data': sorted(result, key=lambda x: x['avgChangePercent'], reverse=True),
        }

    def _build_symbol_industry_map(self):
        """非同步取得所有產業代碼對照表 symbol → industry_code"""
        sym_map = {}
        tasks = []
        for code in INDUSTRY_CODE_MAP:
            for exchange in ('TWSE', 'TPEx'):
                tasks.append((exchange, code))

        with ThreadPoolExecutor(max_workers=10) as pool:
            futures = {
                pool.submit(self._get_tickers_by_industry, ex, code): code
                for ex, code in tasks
            }
            for future in as_completed(futures):
                code = futures[future]
                try:
                    tickers = future.result()
                    for t in tickers:
                        sym = t.get('symbol', '')
                        if sym:
                            sym_map[sym] = code
                except Exception:
                    pass
        return sym_map

    def get_sector_summaries(self, days=1):
        """取得所有產業漲跌彙總（產業漲跌圖）"""
        days = int(days or 1)
        if days > 1:
            return self._cached(f'sector_summaries_{days}', lambda: self._build_historical_sector_summaries(days))
        return self._cached('sector_summaries_1d', self._build_snapshot_sector_summaries)

    def get_stocks_in_sector(self, industry_code, days=1):
        """取得特定產業下各股交易量（類股交易量 Treemap）"""
        days = int(days or 1)
        
        def fetch_snapshot():
            twse = self._get_tickers_by_industry('TWSE', industry_code)
            tpex = self._get_tickers_by_industry('TPEx', industry_code)
            symbols = {t.get('symbol') for t in (twse + tpex) if t.get('symbol')}

            tse = self._get_snapshot('TSE')
            otc = self._get_snapshot('OTC')

            stocks = [
                {
                    'symbol': q.get('symbol'),
                    'name': q.get('name'),
                    'changePercent': q.get('changePercent'),
                    'volume': q.get('tradeVolume'),
                }
                for q in (tse + otc)
                if q.get('symbol') in symbols
            ]

            return {
                'meta': {
                    'source': 'snapshot',
                    'periodDays': 1,
                    'updatedAt': self._now_text(),
                    'asOfDate': None,
                    'historyStartDate': None,
                    'historyEndDate': None,
                },
                'data': stocks,
            }
        
        def fetch_historical():
            twse = self._get_tickers_by_industry('TWSE', industry_code)
            tpex = self._get_tickers_by_industry('TPEx', industry_code)
            symbols = [t.get('symbol') for t in (twse + tpex) if t.get('symbol')]
            
            stocks = []
            dates_all = []
            
            for sym in symbols:
                history = self._load_stock_history(sym)
                if len(history) < 2:
                    continue
                
                recent = history[-days:] if len(history) > days else history[:]
                if len(recent) < 2:
                    continue
                
                first_close = recent[0]['close']
                last_close = recent[-1]['close']
                if not first_close:
                    continue
                
                period_change = round(((last_close - first_close) / first_close) * 100, 2)
                total_volume = int(sum(item['volume'] for item in recent))
                
                # 從產業list中取得股票名稱
                sym_map = self._get_symbol_industry_map()
                name = sym  # fallback 到 symbol
                for t in (twse + tpex):
                    if t.get('symbol') == sym:
                        name = t.get('name', sym)
                        break
                
                stocks.append({
                    'symbol': sym,
                    'name': name,
                    'changePercent': period_change,
                    'volume': total_volume,
                })
                dates_all.append(recent[-1]['date'])
            
            latest_date = max(dates_all) if dates_all else None
            earliest_date = min(dates_all) if dates_all else None
            
            return {
                'meta': {
                    'source': 'historical',
                    'periodDays': days,
                    'updatedAt': self._now_text(),
                    'asOfDate': latest_date,
                    'historyStartDate': earliest_date,
                    'historyEndDate': latest_date,
                },
                'data': stocks,
            }
        
        if days > 1:
            return self._cached(f'sector_stocks_{industry_code}_{days}d', fetch_historical)
        return self._cached(f'sector_stocks_{industry_code}_1d', fetch_snapshot)
