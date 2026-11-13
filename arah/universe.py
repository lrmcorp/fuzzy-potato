from __future__ import annotations

from dataclasses import dataclass, asdict


@dataclass(frozen=True)
class Asset:
    key: str
    symbol: str  # Yahoo Finance symbol
    name: str
    klass: str  # fx | index | stock | commodity | crypto | gauge
    country: str  # ID | US | JP | SG | GLOBAL
    days_per_week: int = 5
    decimals: int = 2
    # What a rising price means for an Indonesian holder of rupiah assets:
    # +1 good, -1 bad, 0 neutral. USD/IDR rising is bad, IHSG rising is good.
    up_is: int = 0
    name_en: str = ""

    @property
    def unit(self) -> str:
        """Currency a price is quoted in, as shown before it. Index levels and gauges have none."""
        if self.klass == "fx":
            return {"USDJPY": "¥", "USDSGD": "S$", "USDCNY": "CN¥", "DXY": ""}.get(self.key, "Rp")
        if self.klass == "stock":
            return "Rp" if self.country == "ID" else "$"
        if self.klass in ("commodity", "crypto"):
            return "$"
        return ""

    def nm(self, lang: str = "id") -> str:
        return self.name_en if lang == "en" and self.name_en else self.name

    def to_dict(self) -> dict:
        return asdict(self)


FX = [
    Asset("USDIDR", "IDR=X", "USD/IDR", "fx", "ID", decimals=0, up_is=-1),
    Asset("JPYIDR", "JPYIDR=X", "JPY/IDR", "fx", "JP", decimals=2, up_is=-1),
    Asset("SGDIDR", "SGDIDR=X", "SGD/IDR", "fx", "SG", decimals=0, up_is=-1),
    Asset("EURIDR", "EURIDR=X", "EUR/IDR", "fx", "GLOBAL", decimals=0, up_is=-1),
    Asset("DXY", "DX-Y.NYB", "Indeks Dolar (DXY)", "fx", "US", decimals=2, name_en="Dollar Index (DXY)"),
    Asset("USDJPY", "JPY=X", "USD/JPY", "fx", "JP", decimals=2),
    Asset("USDSGD", "SGD=X", "USD/SGD", "fx", "SG", decimals=4),
    Asset("USDCNY", "CNY=X", "USD/CNY", "fx", "CN", decimals=4),
    # Yahoo's own CNY/IDR series is broken (one daily bar), so this one is built from USD/IDR and USD/CNY.
    Asset("CNYIDR", "SYN:CNYIDR", "Yuan (RMB)/IDR", "fx", "CN", decimals=0, up_is=-1),
]

INDICES = [
    Asset("IHSG", "^JKSE", "IHSG", "index", "ID", up_is=1),
    Asset("LQ45", "^JKLQ45", "LQ45", "index", "ID", up_is=1),
    Asset("SPX", "^GSPC", "S&P 500", "index", "US", up_is=1),
    Asset("NASDAQ", "^IXIC", "Nasdaq", "index", "US", up_is=1),
    Asset("N225", "^N225", "Nikkei 225", "index", "JP", up_is=1),
    Asset("STI", "^STI", "Straits Times", "index", "SG", up_is=1),
    Asset("SSE", "000001.SS", "Shanghai Composite", "index", "CN", up_is=1),
]

# Coal and nickel have no free futures feed on Yahoo, so they are left out
# instead of being approximated.
COMMODITIES = [
    Asset("GOLD", "GC=F", "Emas", "commodity", "GLOBAL", name_en="Gold"),
    Asset("BRENT", "BZ=F", "Minyak Brent", "commodity", "GLOBAL", name_en="Brent oil"),
    Asset("CPO", "CPO=F", "CPO (sawit)", "commodity", "GLOBAL", name_en="Palm oil (CPO)"),
    Asset("COPPER", "HG=F", "Tembaga", "commodity", "GLOBAL", decimals=3, name_en="Copper"),
]

CRYPTO = [
    Asset("BTC", "BTC-USD", "Bitcoin", "crypto", "GLOBAL", days_per_week=7, decimals=0),
    Asset("ETH", "ETH-USD", "Ethereum", "crypto", "GLOBAL", days_per_week=7, decimals=0),
]

# Context gauges: read for the "why", never forecast on their own.
GAUGES = [
    Asset("VIX", "^VIX", "VIX", "gauge", "US"),
    Asset("US10Y", "^TNX", "Yield US 10 tahun", "gauge", "US", decimals=3, name_en="US 10-year yield"),
]

ID_STOCKS = [
    ("BBCA", "Bank Central Asia"), ("BBRI", "Bank Rakyat Indonesia"), ("BMRI", "Bank Mandiri"),
    ("BBNI", "Bank Negara Indonesia"), ("TLKM", "Telkom Indonesia"), ("ASII", "Astra International"),
    ("ADRO", "Alamtri Resources"), ("ANTM", "Aneka Tambang"), ("GOTO", "GoTo Gojek Tokopedia"),
    ("UNVR", "Unilever Indonesia"), ("ICBP", "Indofood CBP"), ("INDF", "Indofood Sukses Makmur"),
    ("KLBF", "Kalbe Farma"), ("UNTR", "United Tractors"), ("PTBA", "Bukit Asam"),
    ("ITMG", "Indo Tambangraya Megah"), ("MDKA", "Merdeka Copper Gold"), ("INCO", "Vale Indonesia"),
    ("AMRT", "Sumber Alfaria Trijaya"), ("CPIN", "Charoen Pokphand Indonesia"), ("PGAS", "Perusahaan Gas Negara"),
    ("SMGR", "Semen Indonesia"), ("INKP", "Indah Kiat Pulp & Paper"), ("BRPT", "Barito Pacific"),
    ("AMMN", "Amman Mineral"), ("BRIS", "Bank Syariah Indonesia"), ("EXCL", "XL Axiata"),
    ("ISAT", "Indosat"), ("MEDC", "Medco Energi"), ("AKRA", "AKR Corporindo"),
]

US_STOCKS = [
    ("NVDA", "Nvidia"), ("AAPL", "Apple"), ("MSFT", "Microsoft"), ("GOOGL", "Alphabet"),
    ("AMZN", "Amazon"), ("META", "Meta Platforms"), ("TSLA", "Tesla"), ("AVGO", "Broadcom"),
    ("JPM", "JPMorgan Chase"), ("V", "Visa"), ("MA", "Mastercard"), ("UNH", "UnitedHealth"),
    ("XOM", "Exxon Mobil"), ("LLY", "Eli Lilly"), ("JNJ", "Johnson & Johnson"), ("PG", "Procter & Gamble"),
    ("COST", "Costco"), ("HD", "Home Depot"), ("NFLX", "Netflix"), ("AMD", "AMD"),
    ("CRM", "Salesforce"), ("ORCL", "Oracle"), ("KO", "Coca-Cola"), ("WMT", "Walmart"),
    ("BAC", "Bank of America"),
]

STOCKS = [Asset(c, f"{c}.JK", n, "stock", "ID", decimals=0, up_is=1) for c, n in ID_STOCKS] + [
    Asset(c, c, n, "stock", "US", up_is=1) for c, n in US_STOCKS
]

MACRO = FX + INDICES + COMMODITIES + CRYPTO
ALL = MACRO + GAUGES + STOCKS
BY_KEY = {a.key: a for a in ALL}

# Assets shown on the home page, in reading order.
HEADLINE_KEYS = ["IHSG", "USDIDR", "CNYIDR", "SPX", "N225", "STI", "SSE"]

# Synthetic cross rates: key -> (numerator key, denominator key).
SYNTHETIC = {"CNYIDR": ("USDIDR", "USDCNY")}

COUNTRIES = {
    "ID": {"name_id": "Indonesia", "name_en": "Indonesia", "index": "IHSG", "fx": "USDIDR"},
    "US": {"name_id": "Amerika Serikat", "name_en": "United States", "index": "SPX", "fx": "DXY"},
    "JP": {"name_id": "Jepang", "name_en": "Japan", "index": "N225", "fx": "USDJPY"},
    "SG": {"name_id": "Singapura", "name_en": "Singapore", "index": "STI", "fx": "USDSGD"},
    "CN": {"name_id": "China", "name_en": "China", "index": "SSE", "fx": "CNYIDR"},
}

# Benchmark index used for relative strength of a stock.
BENCHMARK = {"ID": "IHSG", "US": "SPX"}

DEFAULT_LEVELS = {"USDIDR": [18000, 18500, 19000]}


def resolve(text: str) -> Asset | None:
    """Find an asset from user input such as 'bbca', 'USD/IDR', 'usdidr' or 'BBCA.JK'."""
    t = text.strip().upper().replace("/", "").replace(" ", "")
    if t.endswith(".JK"):
        t = t[:-3]
    if t in BY_KEY:
        return BY_KEY[t]
    aliases = {"USD": "USDIDR", "DOLAR": "USDIDR", "DOLLAR": "USDIDR", "RUPIAH": "USDIDR", "IDR": "USDIDR",
               "JKSE": "IHSG", "SP500": "SPX", "S&P500": "SPX", "S&P": "SPX", "NIKKEI": "N225",
               "EMAS": "GOLD", "MINYAK": "BRENT", "OIL": "BRENT", "BITCOIN": "BTC", "JPY": "JPYIDR",
               "YEN": "JPYIDR", "SGD": "SGDIDR", "EUR": "EURIDR", "RMB": "CNYIDR", "YUAN": "CNYIDR",
               "CNY": "CNYIDR", "CHINA": "SSE", "SHANGHAI": "SSE"}
    return BY_KEY.get(aliases.get(t, ""))
