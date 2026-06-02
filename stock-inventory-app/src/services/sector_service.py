"""
產業別 Dashboard 服務
- get_sector_summaries()：取得所有產業漲跌彙總
- get_stocks_in_sector(industry_code)：取得特定產業下各股交易量
"""
import time
from concurrent.futures import ThreadPoolExecutor, as_completed

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
    def __init__(self, rest_stock):
        self._rest = rest_stock
        self._cache = {}          # { key: (timestamp, data) }
        self._cache_ttl = 300     # 5 分鐘快取

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

    def get_sector_summaries(self):
        """取得所有產業漲跌彙總（產業漲跌圖）"""
        def fetch():
            tse = self._get_snapshot('TSE')
            otc = self._get_snapshot('OTC')
            all_quotes = tse + otc
            sym_map = self._build_symbol_industry_map()

            # 依產業分組
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
                })
            return sorted(result, key=lambda x: x['avgChangePercent'], reverse=True)

        return self._cached('sector_summaries', fetch)

    def get_stocks_in_sector(self, industry_code):
        """取得特定產業下各股交易量（類股交易量 Treemap）"""
        def fetch():
            twse = self._get_tickers_by_industry('TWSE', industry_code)
            tpex = self._get_tickers_by_industry('TPEx', industry_code)
            symbols = {t.get('symbol') for t in (twse + tpex) if t.get('symbol')}

            tse = self._get_snapshot('TSE')
            otc = self._get_snapshot('OTC')

            return [
                {
                    'symbol': q.get('symbol'),
                    'name': q.get('name'),
                    'changePercent': q.get('changePercent'),
                    'volume': q.get('tradeVolume'),
                }
                for q in (tse + otc)
                if q.get('symbol') in symbols
            ]

        return self._cached(f'sector_stocks_{industry_code}', fetch)
