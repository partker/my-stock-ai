import streamlit as st
import pandas as pd
import numpy as np
import requests
from bs4 import BeautifulSoup
import yfinance as yf
import plotly.graph_objects as go
from datetime import datetime, timedelta, date
from google import genai
import re
import os

st.set_page_config(page_title="AI 글로벌 월가 트레이딩 & 매도 시그널", page_icon="🌍", layout="wide")

HEADERS = {
    "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/122.0.0.0 Safari/537.36",
    "Referer": "https://finance.naver.com/"
}

PORTFOLIO_FILE = "my_portfolio.csv"

def load_portfolio():
    if os.path.exists(PORTFOLIO_FILE):
        try:
            return pd.read_csv(PORTFOLIO_FILE).to_dict("records")
        except Exception:
            return []
    return []

def save_portfolio(data_list):
    df = pd.DataFrame(data_list)
    df.to_csv(PORTFOLIO_FILE, index=False, encoding="utf-8-sig")

if "main_mode" not in st.session_state:
    st.session_state.main_mode = "💼 내 보유 종목 & 매도 시그널"
if "target_stock" not in st.session_state:
    st.session_state.target_stock = "삼성전자"
if "auto_run_detail" not in st.session_state:
    st.session_state.auto_run_detail = False
if "scan_df" not in st.session_state:
    st.session_state.scan_df = pd.DataFrame()
if "scan_ai_report" not in st.session_state:
    st.session_state.scan_ai_report = ""
if "portfolio" not in st.session_state:
    st.session_state.portfolio = load_portfolio()

KR_SCAN_UNIVERSE = [
    ("005930", "삼성전자"), ("000660", "SK하이닉스"), ("373220", "LG에너지솔루션"), ("207940", "삼성바이오로직스"),
    ("005380", "현대차"), ("000270", "기아"), ("068270", "셀트리온"), ("035420", "NAVER"),
    ("035720", "카카오"), ("012450", "한화에어로스페이스"), ("042700", "한미반도체"), ("196170", "알테오젠"),
    ("086520", "에코프로"), ("247540", "에코프로비엠"), ("028300", "HLB"), ("005490", "POSCO홀딩스"),
    ("105560", "KB금융"), ("055550", "신한지주"), ("329180", "HD현대중공업"), ("034020", "두산에너빌리티"),
    ("267260", "HD현대일렉트릭"), ("010120", "LS ELECTRIC"), ("277810", "레인보우로보틱스"), ("006400", "삼성SDI")
]

US_SCAN_UNIVERSE = [
    ("NVDA", "엔비디아 (NVIDIA)"), ("AAPL", "애플 (Apple)"), ("MSFT", "마이크로소프트 (Microsoft)"), ("GOOGL", "구글 (Alphabet)"),
    ("AMZN", "아마존 (Amazon)"), ("META", "메타 (Meta)"), ("TSLA", "테슬라 (Tesla)"), ("AVGO", "브로드컴 (Broadcom)"),
    ("TSM", "TSMC"), ("AMD", "AMD"), ("PLTR", "팔란티어 (Palantir)"), ("NFLX", "넷플릭스 (Netflix)"),
    ("ASML", "ASML"), ("ARM", "ARM 홀딩스"), ("MU", "마이크론 (Micron)"), ("LLY", "일라이릴리 (Eli Lilly)"),
    ("COST", "코스트코 (Costco)"), ("WMT", "월마트 (Walmart)"), ("JPM", "JP모건 (JPMorgan)"), ("V", "비자 (Visa)"),
    ("COIN", "코인베이스 (Coinbase)"), ("IONQ", "아이온큐 (IonQ)"), ("UBER", "우버 (Uber)"), ("ORCL", "오라클 (Oracle)")
]

GLOBAL_KOR_MAP = {
    "애플": "AAPL", "마이크로소프트": "MSFT", "엔비디아": "NVDA", "구글": "GOOGL", "알파벳": "GOOGL",
    "아마존": "AMZN", "메타": "META", "테슬라": "TSLA", "브로드컴": "AVGO", "넷플릭스": "NFLX",
    "AMD": "AMD", "인텔": "INTC", "팔란티어": "PLTR", "아이온큐": "IONQ", "코스트코": "COST",
    "월마트": "WMT", "코카콜라": "KO", "펩시": "PEP", "일라이릴리": "LLY", "노보노디스크": "NVO",
    "버크셔해서웨이": "BRK-B", "제이피모건": "JPM", "비자": "V", "마스터카드": "MA", "디즈니": "DIS",
    "보잉": "BA", "스타벅스": "SBUX", "나이키": "NKE", "맥도날드": "MCD", "TSMC": "TSM",
    "아스믈": "ASML", "ASML": "ASML", "암홀딩스": "ARM", "ARM": "ARM", "마이크론": "MU",
    "퀄컴": "QCOM", "오라클": "ORCL", "세일즈포스": "CRM", "어도비": "ADBE", "우버": "UBER",
    "에어비앤비": "ABNB", "코인베이스": "COIN", "마이크로스트래티지": "MSTR", "로빈후드": "HOOD",
    "리비안": "RIVN", "루시드": "LCID", "소파이": "SOFI", "유니티": "U", "로블록스": "RBLX",
    "쿠팡": "CPNG", "알리바바": "BABA", "텐센트": "TCEHY", "샤오미": "XIACY", "비야디": "BYDDY",
    "도요타": "TM", "소니": "SONY", "닌텐도": "NTDOY"
}

def search_naver_stock(query):
    try:
        url = f"https://ac.stock.naver.com/ac?q={requests.utils.quote(query)}&target=stock"
        r = requests.get(url, headers=HEADERS, timeout=4)
        if r.status_code == 200:
            items = r.json().get("items", [])
            for item in items:
                code = item.get("code", "")
                name = item.get("name", "")
                nation = item.get("nationCode", "")
                if nation == "KOR" and re.match(r'^\d{6}$', code):
                    return code, name
    except Exception:
        pass
    return None, None

@st.cache_data(ttl=3600)
def resolve_stock_query(query):
    q = str(query).strip()
    q_upper = q.upper()

    if q in GLOBAL_KOR_MAP:
        ticker = GLOBAL_KOR_MAP[q]
        return ticker, f"{q} ({ticker})", "GLOBAL"

    if re.match(r'^\d{6}$', q):
        code, name = search_naver_stock(q)
        return q, (name or q), "KR"

    if re.search(r'[가-힣]', q):
        code, name = search_naver_stock(q)
        if code:
            return code, name, "KR"

    if re.match(r'^[A-Za-z.\-]{1,10}$', q):
        try:
            t = yf.Ticker(q_upper)
            hist = t.history(period="5d")
            if not hist.empty:
                info = t.info
                long_name = info.get('shortName') or info.get('longName') or q_upper
                return q_upper, long_name, "GLOBAL"
        except Exception:
            pass

    try:
        search_url = f"https://query2.finance.yahoo.com/v1/finance/search?q={requests.utils.quote(q)}"
        r = requests.get(search_url, headers=HEADERS, timeout=4)
        if r.status_code == 200:
            quotes = r.json().get("quotes", [])
            for item in quotes:
                symbol = item.get("symbol", "")
                name = item.get("shortname") or item.get("longname") or symbol
                if symbol.endswith(".KS") or symbol.endswith(".KQ"):
                    kr_code = symbol.split(".")[0]
                    return kr_code, name, "KR"
                elif symbol:
                    return symbol, name, "GLOBAL"
    except Exception:
        pass

    return None, None, None

@st.cache_data(ttl=1800)
def get_fear_indices():
    result = {"vix_val": None, "vix_status": "데이터 없음", "fg_val": None, "fg_status": "데이터 없음"}
    try:
        vix_df = yf.Ticker("^VIX").history(period="5d")
        if not vix_df.empty:
            vix = round(float(vix_df['Close'].iloc[-1]), 2)
            result["vix_val"] = vix
            if vix >= 30: result["vix_status"] = "극도의 공포 (시장 패닉)"
            elif vix >= 20: result["vix_status"] = "공포/경계 (변동성 확대)"
            else: result["vix_status"] = "안정/평온 (정상 장세)"
    except Exception:
        pass

    try:
        url = "https://production.dataviz.cnn.io/index/fearandgreed/graphdata"
        r = requests.get(url, headers=HEADERS, timeout=4)
        if r.status_code == 200:
            data = r.json()
            fg_score = round(float(data['fear_and_greed']['score']), 1)
            fg_rating = data['fear_and_greed']['rating']
            kor_map = {"extreme fear": "극도의 공포", "fear": "공포", "neutral": "중립", "greed": "탐욕", "extreme greed": "극도의 탐욕"}
            result["fg_val"] = fg_score
            result["fg_status"] = kor_map.get(fg_rating.lower(), fg_rating)
    except Exception:
        pass
    return result

def call_gemini_ai(api_key, prompt):
    clean_key = api_key.strip()
    client = genai.Client(api_key=clean_key)

    available_models = []
    try:
        for m in client.models.list():
            name = m.name.replace("models/", "")
            if ("flash" in name or "gemini" in name) and "embedding" not in name and "imagen" not in name and "vision" not in name:
                available_models.append(name)
    except Exception as e:
        return f"❌ API 키 인증 또는 모델 목록 조회 실패 (API 키를 다시 확인해 주세요): {e}"

    preferred_order = [
        "gemini-3.8-flash",
        "models/gemini-3.8-flash",
        "gemini-3.8-flash-preview",
        "gemini-3-flash",
        "gemini-3.0-flash",
    ]
    for m in sorted(available_models, reverse=True):
        if m not in preferred_order:
            preferred_order.append(m)

    errors = {}
    for model_name in preferred_order:
        try:
            res = client.models.generate_content(model=model_name, contents=prompt)
            if res and res.text:
                return res.text
        except Exception as e:
            errors[model_name] = str(e)
            continue

    first_err = errors.get("gemini-3.8-flash") or next(iter(errors.values()), "알 수 없는 오류")
    return f"❌ AI 호출 오류 (내 키에서 감지된 모델: {available_models[:5]}): {first_err}"

@st.cache_data(ttl=600)
def fetch_cached_price(code, market_type, days=150):
    if market_type == "KR":
        for suffix in [".KS", ".KQ"]:
            try:
                df = yf.Ticker(f"{code}{suffix}").history(period="6mo")
                if df is not None and not df.empty:
                    return df
            except Exception:
                continue
        return pd.DataFrame()
    else:
        return yf.Ticker(code).history(period="6mo")

@st.cache_data(ttl=600)
def get_kr_data(code):
    price_df = fetch_cached_price(code, "KR", 120)

    info = {"현재가": "확인불가", "PER": "N/A", "PBR": "N/A", "시가총액": "N/A", "통화": "원"}
    cur_price_num = 0
    if not price_df.empty:
        cur_price_num = int(price_df['Close'].iloc[-1])
        info["현재가"] = f"{cur_price_num:,}원"

    url = f"https://finance.naver.com/item/main.naver?code={code}"
    fin_df = pd.DataFrame()
    try:
        res = requests.get(url, headers=HEADERS, timeout=4)
        res.encoding = "euc-kr"
        soup = BeautifulSoup(res.text, 'html.parser')

        today_area = soup.select_one('.no_today .blind')
        if today_area:
            info["현재가"] = today_area.text.strip() + "원"
        per = soup.select_one('#_per')
        cns_per = soup.select_one('#_cns_per')
        pbr = soup.select_one('#_pbr')
        mcap = soup.select_one('#_market_sum')

        if per and per.text.strip() and per.text.strip() != "N/A":
            info["PER"] = per.text.strip() + "배"
        elif cns_per and cns_per.text.strip() and cns_per.text.strip() != "N/A":
            info["PER"] = cns_per.text.strip() + "배 (추정)"

        if pbr and pbr.text.strip() and pbr.text.strip() != "N/A":
            info["PBR"] = pbr.text.strip() + "배"
        if mcap and mcap.text.strip():
            info["시가총액"] = re.sub(r'\s+', ' ', mcap.text.strip()) + "억"

        tables = pd.read_html(res.text)
        for t in tables:
            if '매출액' in str(t.values) and '영업이익' in str(t.values):
                fin_df = t
                if isinstance(fin_df.columns, pd.MultiIndex):
                    fin_df.columns = ['_'.join([str(c) for c in col if 'Unnamed' not in str(c)]).strip() for col in fin_df.columns.values]
                fin_df = fin_df.dropna(how='all')
                break
    except Exception:
        pass

    if (info["PER"] == "N/A" or info["PBR"] == "N/A") and not fin_df.empty:
        try:
            first_col = fin_df.columns[0]
            for _, r in fin_df.iterrows():
                row_name = str(r[first_col])
                valid_nums = []
                for val in r.iloc[1:]:
                    try:
                        v = float(str(val).replace(',', ''))
                        if not np.isnan(v) and v != 0:
                            valid_nums.append(v)
                    except Exception:
                        continue
                if not valid_nums:
                    continue
                latest_val = valid_nums[-1]

                if "PER" in row_name and info["PER"] == "N/A":
                    info["PER"] = f"{latest_val:.2f}배" if latest_val > 0 else "적자/성장주 (PER 미산출)"
                elif "PBR" in row_name and info["PBR"] == "N/A" and latest_val > 0:
                    info["PBR"] = f"{latest_val:.2f}배"
                elif "BPS" in row_name and info["PBR"] == "N/A" and cur_price_num > 0 and latest_val > 0:
                    info["PBR"] = f"{(cur_price_num / latest_val):.2f}배"
        except Exception:
            pass

    if info["PER"] == "N/A" or info["PBR"] == "N/A" or info["시가총액"] == "N/A":
        for suffix in [".KS", ".KQ"]:
            try:
                yf_kr = yf.Ticker(f"{code}{suffix}").info
                if yf_kr and yf_kr.get("marketCap"):
                    if info["시가총액"] == "N/A":
                        info["시가총액"] = f"{int(yf_kr['marketCap'] // 100000000):,}억"
                    if info["PER"] == "N/A":
                        yf_per = yf_kr.get("trailingPE") or yf_kr.get("forwardPE")
                        if yf_per and yf_per > 0:
                            info["PER"] = f"{yf_per:.2f}배"
                    if info["PBR"] == "N/A":
                        yf_pbr = yf_kr.get("priceToBook")
                        if yf_pbr and yf_pbr > 0:
                            info["PBR"] = f"{yf_pbr:.2f}배"
                    break
            except Exception:
                continue

    if info["PER"] == "N/A":
        info["PER"] = "적자/성장주 (PER 미산출)"

    supply_df = pd.DataFrame()
    try:
        s_url = f"https://finance.naver.com/item/frgn.naver?code={code}"
        s_res = requests.get(s_url, headers=HEADERS, timeout=4)
        s_res.encoding = "euc-kr"
        tables = pd.read_html(s_res.text)
        for t in tables:
            if '기관' in str(t.columns) and '외국인' in str(t.columns):
                if isinstance(t.columns, pd.MultiIndex):
                    t.columns = ['_'.join([str(c) for c in col]).strip() for col in t.columns.values]
                t = t.dropna(how='all')
                first_col = t.columns[0]
                t = t[t[first_col].astype(str).str.match(r'^\d{4}\.\d{2}\.\d{2}$')]
                supply_df = t.head(20).reset_index(drop=True)
                break
    except Exception:
        pass

    news_list = []
    try:
        n_url = f"https://finance.naver.com/item/news_news.naver?code={code}&page=1"
        n_res = requests.get(n_url, headers=HEADERS, timeout=4)
        n_res.encoding = "euc-kr"
        n_soup = BeautifulSoup(n_res.text, 'html.parser')
        for row in n_soup.select('table.type5 tbody tr'):
            title_tag = row.select_one('td.title a')
            date_tag = row.select_one('td.date')
            if title_tag and date_tag:
                news_list.append({
                    "날짜": date_tag.text.strip(),
                    "제목": title_tag.text.strip(),
                    "링크": "https://finance.naver.com" + title_tag['href']
                })
            if len(news_list) >= 10: break
    except Exception:
        pass

    return info, fin_df, supply_df, news_list, price_df

@st.cache_data(ttl=600)
def get_global_data(ticker):
    t = yf.Ticker(ticker)
    yf_info = {}
    try:
        yf_info = t.info
    except Exception:
        pass

    price_df = fetch_cached_price(ticker, "GLOBAL", 150)
    currency = yf_info.get("currency", "USD")
    cur_p = yf_info.get("currentPrice") or yf_info.get("regularMarketPrice")
    if not cur_p and not price_df.empty:
        cur_p = float(price_df['Close'].iloc[-1])

    mcap = yf_info.get("marketCap")
    per = yf_info.get("trailingPE") or yf_info.get("forwardPE")
    pbr = yf_info.get("priceToBook")

    info = {
        "현재가": f"{cur_p:,.2f} {currency}" if cur_p else "확인불가",
        "시가총액": f"{mcap / 1e9:,.1f}B {currency}" if mcap else "N/A",
        "PER": f"{per:.2f}배" if per else "적자/성장주 (미산출)",
        "PBR": f"{pbr:.2f}배" if pbr else "N/A",
        "통화": currency,
        "ROE": f"{yf_info.get('returnOnEquity', 0)*100:.1f}%" if yf_info.get('returnOnEquity') else "N/A",
        "부채비율(D/E)": f"{yf_info.get('debtToEquity', 'N/A')}%",
        "월가목표주가(평균)": f"{yf_info.get('targetMeanPrice', 'N/A')} {currency}",
        "월가투자의견": yf_info.get("recommendationKey", "N/A").upper()
    }

    fin_df = pd.DataFrame()
    try:
        inc = t.income_stmt
        bal = t.balance_sheet
        if inc is not None and not inc.empty:
            keep_rows = [r for r in ['Total Revenue', 'Operating Income', 'Net Income', 'Diluted EPS'] if r in inc.index]
            sub_inc = inc.loc[keep_rows]
            if bal is not None and not bal.empty:
                bal_rows = [r for r in ['Total Assets', 'Total Debt', 'Stockholders Equity'] if r in bal.index]
                sub_bal = bal.loc[bal_rows]
                fin_df = pd.concat([sub_inc, sub_bal])
            else:
                fin_df = sub_inc
            fin_df.columns = [str(c)[:10] for c in fin_df.columns]
    except Exception:
        pass

    supply_df = pd.DataFrame()
    try:
        inst_pct = yf_info.get("heldPercentInstitutions")
        ins_pct = yf_info.get("heldPercentInsiders")
        short_ratio = yf_info.get("shortRatio")
        summary_rows = [
            {"항목": "글로벌 기관투자자 보유 비중", "수치": f"{inst_pct*100:.2f}%" if inst_pct else "N/A"},
            {"항목": "내부자(경영진) 보유 비중", "수치": f"{ins_pct*100:.2f}%" if ins_pct else "N/A"},
            {"항목": "공매도 커버 비율 (Short Ratio)", "수치": f"{short_ratio}" if short_ratio else "N/A"},
            {"항목": "월가 애널리스트 평균 목표가", "수치": info["월가목표주가(평균)"]},
            {"항목": "월가 컨센서스 의견", "수치": info["월가투자의견"]}
        ]
        supply_df = pd.DataFrame(summary_rows)
    except Exception:
        pass

    news_list = []
    try:
        raw_news = t.news or []
        for n in raw_news[:10]:
            content = n.get("content", {})
            title = content.get("title") or n.get("title", "제목 없음")
            link = content.get("canonicalUrl", {}).get("url") or n.get("link", "#")
            pub = content.get("pubDate", "")[:10]
            news_list.append({"날짜": pub, "제목": title, "링크": link})
    except Exception:
        pass

    return info, fin_df, supply_df, news_list, price_df

def evaluate_sell_signals(item):
    code = item["code"]
    market_type = item["market_type"]
    buy_price = float(item["buy_price"])
    buy_date_str = str(item["buy_date"])
    trail_pct = float(item.get("trail_pct", -5.0))

    try:
        df = fetch_cached_price(code, market_type, 150)
        unit = "원" if market_type == "KR" else "USD"
    except Exception:
        return None

    if df is None or df.empty or len(df) < 22:
        return None

    df_clean = df.copy()
    df_clean.index = pd.to_datetime(df_clean.index).tz_localize(None)
    buy_dt = pd.to_datetime(buy_date_str)

    close = df_clean['Close']
    high = df_clean['High']
    low = df_clean['Low']
    open_p = df_clean['Open']
    vol = df_clean['Volume']

    cur_price = float(close.iloc[-1])
    cur_open = float(open_p.iloc[-1])
    is_bearish_candle = cur_price < cur_open

    since_buy = df_clean[df_clean.index >= buy_dt]
    if not since_buy.empty:
        peak_price = float(since_buy['High'].max())
    else:
        peak_price = float(high.tail(20).max())
    peak_price = max(peak_price, buy_price, cur_price)

    delta = close.diff()
    gain = (delta.where(delta > 0, 0)).rolling(14).mean()
    loss = (-delta.where(delta < 0, 0)).rolling(14).mean()
    rs = gain / loss
    rsi_val = float(100 - (100 / (1 + rs.iloc[-1])))
    rsi = round(rsi_val, 1) if not np.isnan(rsi_val) else 50.0

    ma20_series = close.rolling(20).mean()
    std20_series = close.rolling(20).std()
    bb_upper_series = ma20_series + 2 * std20_series

    ma20 = float(ma20_series.iloc[-1])
    bb_upper = float(bb_upper_series.iloc[-1])

    recent3_high = high.tail(3)
    recent3_bb = bb_upper_series.tail(3)
    touched_bb_upper = bool((recent3_high >= recent3_bb * 0.995).any())

    support_20 = float(low.iloc[-21:-1].min()) if len(low) >= 21 else float(low.tail(20).min())

    prev_close = close.shift(1)
    tr = pd.concat([
        high - low,
        (high - prev_close).abs(),
        (low - prev_close).abs()
    ], axis=1).max(axis=1)
    atr14 = float(tr.rolling(14).mean().iloc[-1]) if len(tr) >= 14 else (cur_price * 0.025)

    trail_line_pct = peak_price * (1.0 + trail_pct / 100.0)
    trail_line_atr = peak_price - (2.0 * atr14)
    drawdown_from_peak = round(((cur_price - peak_price) / peak_price) * 100, 2)
    profit_pct = round(((cur_price - buy_price) / buy_price) * 100, 2)

    avg_vol20 = float(vol.tail(20).mean())
    vol_ratio = round((float(vol.iloc[-1]) / avg_vol20) * 100, 1) if avg_vol20 > 0 else 100.0

    signals = []
    badge_level = "GREEN"

    if cur_price <= trail_line_pct or (profit_pct > 3.0 and cur_price <= trail_line_atr):
        badge_level = "RED"
        signals.append(
            f"🔴 **[고점 대비 하락 - 익절 매도 신호]** 매수 후 최고가({peak_price:,.0f}) 대비 **{drawdown_from_peak}%** 밀리며 트레일링 스탑 방어선({trail_line_pct:,.0f})을 이탈했습니다. 수익 보존을 위해 익절/매도를 권장합니다."
        )

    if cur_price < ma20 or cur_price < support_20:
        badge_level = "RED"
        vol_msg = f"(거래량 평균 대비 {vol_ratio}% 동반)" if vol_ratio >= 110 else ""
        broken_name = "20일 생명선 및 박스권 지지선" if (cur_price < ma20 and cur_price < support_20) else ("20일 이동평균선(생명선)" if cur_price < ma20 else "최근 20일 지지선")
        signals.append(
            f"🔴 **[추세 붕괴 - 전량 매도/손절 신호]** 현재 종가가 핵심 방어선인 **{broken_name}**을 하향 이탈했습니다 {vol_msg}. 추세가 꺾였으므로 리스크 관리를 권장합니다."
        )

    if rsi >= 70.0 or (touched_bb_upper and is_bearish_candle):
        if badge_level != "RED":
            badge_level = "YELLOW"
        reason_str = f"RSI({rsi}) 과열 구간 진입" if rsi >= 70.0 else "볼린저밴드 상단 돌파 후 단기 차익실현 음봉 발생"
        signals.append(
            f"🟡 **[단기 고점 과열 - 50% 분할 익절 추천]** {reason_str} 상태입니다. 보유 물량의 절반(50%)을 분할 익절하여 수익을 확정하고 나머지는 추세를 따라가세요."
        )

    if not signals:
        signals.append(
            f"🟢 **[추세 양호 - 보유 유지(Hold)]** 현재가가 20일 생명선({ma20:,.0f})과 트레일링 스탑 방어선({trail_line_pct:,.0f}) 위에서 안정적으로 움직이고 있습니다."
        )

    return {
        "df": df_clean,
        "unit": unit,
        "cur_price": round(cur_price, 2),
        "buy_price": round(buy_price, 2),
        "profit_pct": profit_pct,
        "peak_price": round(peak_price, 2),
        "drawdown_from_peak": drawdown_from_peak,
        "trail_line_pct": round(trail_line_pct, 2),
        "trail_line_atr": round(trail_line_atr, 2),
        "ma20": round(ma20, 2),
        "bb_upper": round(bb_upper, 2),
        "support_20": round(support_20, 2),
        "rsi": rsi,
        "vol_ratio": vol_ratio,
        "badge_level": badge_level,
        "signals": signals
    }

@st.cache_data(ttl=600)
def scan_market_universe_cached(market_choice):
    universe = KR_SCAN_UNIVERSE if "한국" in market_choice else US_SCAN_UNIVERSE
    is_kr = "한국" in market_choice
    m_type = "KR" if is_kr else "GLOBAL"
    rows = []

    for code, name in universe:
        try:
            df = fetch_cached_price(code, m_type, 95)
            if df is None or df.empty or len(df) < 22:
                continue

            close = df['Close']
            vol = df['Volume']
            cur_p = float(close.iloc[-1])
            ret_5d = round((cur_p / float(close.iloc[-6]) - 1) * 100, 2) if len(close) >= 6 else 0.0

            delta = close.diff()
            gain = (delta.where(delta > 0, 0)).rolling(14).mean()
            loss = (-delta.where(delta < 0, 0)).rolling(14).mean()
            rs = gain / loss
            rsi_val = float(100 - (100 / (1 + rs.iloc[-1])))
            rsi = round(rsi_val, 1) if not np.isnan(rsi_val) else 50.0

            avg_vol20 = float(vol.tail(20).mean())
            cur_vol = float(vol.iloc[-1])
            vol_ratio = round((cur_vol / avg_vol20) * 100, 1) if avg_vol20 > 0 else 100.0

            ma20 = float(close.rolling(20).mean().iloc[-1])
            ma60 = float(close.rolling(60).mean().iloc[-1]) if len(close) >= 60 else ma20
            recent_20 = df.tail(20)
            support_20 = float(recent_20['Low'].min())
            resist_20 = float(recent_20['High'].max())

            near_resist_pct = round((cur_p / resist_20) * 100, 1) if resist_20 > 0 else 0.0
            from_support_pct = round(((cur_p - support_20) / support_20) * 100, 1) if support_20 > 0 else 0.0

            if cur_p >= ma20 and (near_resist_pct >= 96.5 or vol_ratio >= 130):
                category = "🚀 돌파/수급 주도주"
                score = 85 + min(15, (vol_ratio - 100) * 0.1)
            elif rsi <= 42 or from_support_pct <= 4.5:
                category = "🟢 과매도 눌림목 반등주"
                score = 80 + max(0, (45 - rsi) * 0.5)
            elif cur_p >= ma20 and ma20 >= ma60:
                category = "🚩 추세 지속 우량주"
                score = 75 + min(15, max(0, ret_5d))
            else:
                category = "⚖️ 박스권 관망"
                score = 60

            rows.append({
                "종목명": name,
                "코드/티커": code,
                "전략 분류": category,
                "현재가": f"{int(cur_p):,}원" if is_kr else f"${cur_p:,.2f}",
                "5일 등락률(%)": ret_5d,
                "거래량 비율(20일대비%)": vol_ratio,
                "RSI(14일)": rsi,
                "20일 지지선(손절/타점)": f"{int(support_20):,}" if is_kr else f"${support_20:,.2f}",
                "20일 저항선(1차목표)": f"{int(resist_20):,}" if is_kr else f"${resist_20:,.2f}",
                "고점근접도(%)": near_resist_pct,
                "퀀트점수": round(score, 1)
            })
        except Exception:
            continue

    res_df = pd.DataFrame(rows)
    if not res_df.empty:
        res_df = res_df.sort_values(by="퀀트점수", ascending=False).reset_index(drop=True)
    return res_df

@st.cache_data(ttl=600)
def run_day_trader_simulation(price_df, target_pct=10.0, stop_pct=-5.0, days=20, n_sims=2000):
    if price_df is None or price_df.empty or len(price_df) < 20:
        return None
    
    close = price_df['Close']
    cur_price = float(close.iloc[-1])
    
    delta = close.diff()
    gain = (delta.where(delta > 0, 0)).rolling(window=14).mean()
    loss = (-delta.where(delta < 0, 0)).rolling(window=14).mean()
    rs = gain / loss
    rsi = round(float(100 - (100 / (1 + rs.iloc[-1]))), 1)
    
    ma20 = round(float(close.rolling(20).mean().iloc[-1]), 2)
    ma60 = round(float(close.rolling(60).mean().iloc[-1]), 2) if len(close) >= 60 else ma20
    
    recent_20 = price_df.tail(20)
    support_line = round(float(recent_20['Low'].min()), 2)
    resist_line = round(float(recent_20['High'].max()), 2)
    
    patterns = []
    if rsi <= 35:
        patterns.append("🟢 과매도 반등 자리 (RSI 35 이하 침체 구간)")
    if cur_price >= resist_line * 0.98:
        patterns.append("🚀 박스권 상단 돌파 임박/시도 자리")
    if cur_price > ma20 and ma20 > ma60 and abs(cur_price - ma20)/ma20 < 0.03:
        patterns.append("🚩 상승 추세 눌림목(깃발 패턴) 자리")
    if not patterns:
        patterns.append("⚖️ 중립 박스권 횡보 구간 (추세 확인 필요)")

    log_returns = np.log(close / close.shift(1)).dropna()
    mu = float(log_returns.mean())
    sigma = float(log_returns.std())
    
    np.random.seed(42)
    rand_shocks = np.random.normal(mu - 0.5 * sigma**2, sigma, (days, n_sims))
    price_paths = cur_price * np.exp(np.cumsum(rand_shocks, axis=0))
    
    target_price = round(cur_price * (1 + target_pct / 100.0), 2)
    stop_price = round(cur_price * (1 + stop_pct / 100.0), 2)
    
    hit_target = (price_paths.max(axis=0) >= target_price).mean() * 100
    hit_stop = (price_paths.min(axis=0) <= stop_price).mean() * 100
    median_end = round(float(np.median(price_paths[-1])), 2)
    
    return {
        "cur_price": round(cur_price, 2),
        "rsi": rsi,
        "ma20": ma20,
        "ma60": ma60,
        "support": support_line,
        "resist": resist_line,
        "patterns": patterns,
        "target_price": target_price,
        "stop_price": stop_price,
        "hit_target_prob": round(hit_target, 1),
        "hit_stop_prob": round(hit_stop, 1),
        "median_end": median_end,
        "sample_paths": price_paths[:, :40]
    }

# ================= 사이드바 UI (Streamlit Secrets 자동 연동) =================
with st.sidebar:
    st.header("🔑 AI 설정")
    default_key = ""
    try:
        if "GEMINI_API_KEY" in st.secrets:
            default_key = st.secrets["GEMINI_API_KEY"]
    except Exception:
        pass

    if default_key:
        api_key = default_key
        st.success("✅ 서버에 저장된 API Key가 자동 연결되었습니다!")
    else:
        api_key = st.text_input("Gemini API Key 입력", type="password", help="Google AI Studio에서 무료 발급받은 키 입력")
        st.markdown("[👉 무료 API 키 발급받기](https://aistudio.google.com/app/apikey)")

    st.divider()
    st.subheader("🎯 시뮬레이션 목표 설정")
    target_pct = st.slider("목표 수익률 (%)", 3.0, 30.0, 10.0, 1.0)
    stop_pct = st.slider("손절 기준선 (%)", -20.0, -2.0, -5.0, 1.0)
    sim_days = st.slider("보유 기간 (거래일)", 5, 60, 20, 5)
    st.divider()
    st.caption("⚡ 터보 모드: 2,000회 고속 연산 & 10분 스냅샷 캐싱")

st.title("🌍 AI 글로벌 월가 트레이딩 & 매도 타이밍 알리미")
st.caption("내 보유 종목 매도 시그널(트레일링 스탑·과열·생명선 이탈) · 오늘의 주목 종목 스캐너 · 2,000회 고속 시뮬레이션")

fear_data = get_fear_indices()
f_col1, f_col2 = st.columns(2)
with f_col1:
    vix_str = f"{fear_data['vix_val']}" if fear_data['vix_val'] else "집계중"
    st.info(f"🌡️ **미국 VIX 공포지수:** `{vix_str}` — **{fear_data['vix_status']}**")
with f_col2:
    fg_str = f"{fear_data['fg_val']} / 100" if fear_data['fg_val'] else "집계중"
    st.warning(f"🧭 **CNN 공포·탐욕 지수:** `{fg_str}` — **{fear_data['fg_status']}**")

MENU_OPTIONS = [
    "💼 내 보유 종목 & 매도 시그널",
    "🔥 AI 주목 종목 스캐너 & 추천",
    "🔍 개별 종목 정밀 분석기"
]
mode = st.radio(
    "원하는 기능을 선택하세요",
    MENU_OPTIONS,
    index=MENU_OPTIONS.index(st.session_state.main_mode) if st.session_state.main_mode in MENU_OPTIONS else 0,
    horizontal=True
)
st.session_state.main_mode = mode
st.divider()

if st.session_state.main_mode == "💼 내 보유 종목 & 매도 시그널":
    st.subheader("💼 내 보유 종목 기억 & 실시간 매도 타이밍 판별기")
    st.caption("종목과 매수 평단가를 등록해 두면 ① 트레일링 스탑(고점 대비 하락 방어선) ② 단기 고점 과열(50% 분할 익절) ③ 20일 생명선·지지선 이탈(전량 매도) 신호를 자동 감시합니다.")

    with st.expander("➕ 새 보유 종목 등록하기 (국내·해외 주식 모두 가능)", expanded=len(st.session_state.portfolio) == 0):
        p_c1, p_c2, p_c3, p_c4, p_c5 = st.columns([2, 1.5, 1.5, 1.5, 1])
        with p_c1:
            in_stock = st.text_input("보유 종목명 또는 티커", placeholder="예: 삼성전자, 레인보우로보틱스, 테슬라")
        with p_c2:
            in_buy_price = st.number_input("내 매수 평단가 (원 또는 $)", min_value=0.01, value=50000.0, step=100.0)
        with p_c3:
            in_buy_date = st.date_input("매수 시작일", value=date.today() - timedelta(days=14))
        with p_c4:
            in_trail_pct = st.slider("트레일링 스탑 기준(%)", -15.0, -3.0, -5.0, 0.5)
        with p_c5:
            st.write("")
            st.write("")
            add_p_btn = st.button("➕ 종목 저장", use_container_width=True, type="primary")

        if add_p_btn:
            if not in_stock.strip():
                st.warning("종목명을 입력해 주세요.")
            else:
                p_code, p_name, p_mtype = resolve_stock_query(in_stock)
                if not p_code:
                    st.error(f"'{in_stock}' 종목을 찾을 수 없습니다.")
                else:
                    new_item = {
                        "code": p_code,
                        "name": p_name,
                        "market_type": p_mtype,
                        "buy_price": float(in_buy_price),
                        "buy_date": str(in_buy_date),
                        "trail_pct": float(in_trail_pct)
                    }
                    st.session_state.portfolio = [x for x in st.session_state.portfolio if x["code"] != p_code]
                    st.session_state.portfolio.append(new_item)
                    save_portfolio(st.session_state.portfolio)
                    st.success(f"[{p_name} ({p_code})] 보유 종목이 등록되었습니다!")
                    st.rerun()

    if not st.session_state.portfolio:
        st.info("👆 위 입력창에서 현재 보유 중인 종목과 매수 평단가를 등록해 보세요! (한 번 등록하면 자동 기억됩니다)")
    else:
        for idx, item in enumerate(st.session_state.portfolio):
            with st.container(border=True):
                eval_res = evaluate_sell_signals(item)
                if not eval_res:
                    st.warning(f"{item['name']} ({item['code']}) 주가 데이터를 불러오지 못했습니다.")
                    continue

                unit = eval_res["unit"]
                badge_map = {
                    "RED": "🔴 [매도/손절 경보] 즉시 대응 필요",
                    "YELLOW": "🟡 [분할 익절 구간] 단기 고점 과열",
                    "GREEN": "🟢 [보유 유지 (Hold)] 추세 순항 중"
                }
                header_badge = badge_map[eval_res["badge_level"]]

                top_c1, top_c2 = st.columns([4, 1])
                with top_c1:
                    st.markdown(f"### {item['name']} (`{item['code']}`) — {header_badge}")
                with top_c2:
                    if st.button("🗑️ 종목 삭제", key=f"del_{item['code']}_{idx}", use_container_width=True):
                        st.session_state.portfolio.pop(idx)
                        save_portfolio(st.session_state.portfolio)
                        st.rerun()

                mc1, mc2, mc3, mc4, mc5 = st.columns(5)
                fmt_str = "{:,.0f}" if item["market_type"] == "KR" else "{:,.2f}"
                mc1.metric("현재가 / 내 평단가", f"{fmt_str.format(eval_res['cur_price'])} {unit}", f"평단: {fmt_str.format(eval_res['buy_price'])} {unit}")
                mc2.metric("현재 수익률", f"{eval_res['profit_pct']:+.2f}%", delta=f"{eval_res['profit_pct']:+.2f}%")
                mc3.metric("매수 후 최고가 (고점대비)", f"{fmt_str.format(eval_res['peak_price'])} {unit}", f"{eval_res['drawdown_from_peak']:.2f}%", delta_color="normal")
                mc4.metric(f"① 트레일링 방어선 ({item['trail_pct']}%)", f"{fmt_str.format(eval_res['trail_line_pct'])} {unit}", f"ATR방어: {fmt_str.format(eval_res['trail_line_atr'])}")
                mc5.metric("② 20일 생명선 / RSI(14)", f"{fmt_str.format(eval_res['ma20'])} {unit}", f"RSI: {eval_res['rsi']} (70↑ 과열)", delta_color="off")

                for sig in eval_res["signals"]:
                    if sig.startswith("🔴"):
                        st.error(sig)
                    elif sig.startswith("🟡"):
                        st.warning(sig)
                    else:
                        st.success(sig)

                with st.expander("📊 매도 방어선(트레일링 스탑 · 20일 생명선 · 볼린저 상단) 차트 & AI 매도 타점 진단 보기"):
                    df_p = eval_res["df"].tail(60)
                    fig_p = go.Figure()
                    fig_p.add_trace(go.Candlestick(
                        x=df_p.index, open=df_p['Open'], high=df_p['High'],
                        low=df_p['Low'], close=df_p['Close'], name="일봉"
                    ))
                    fig_p.add_trace(go.Scatter(
                        x=df_p.index, y=df_p['Close'].rolling(20).mean(),
                        line=dict(color='purple', width=2), name="20일 생명선"
                    ))
                    bb_up = df_p['Close'].rolling(20).mean() + 2 * df_p['Close'].rolling(20).std()
                    fig_p.add_trace(go.Scatter(
                        x=df_p.index, y=bb_up,
                        line=dict(color='rgba(255, 165, 0, 0.7)', width=1.5, dash='dot'), name="볼린저 상단(과열선)"
                    ))
                    fig_p.add_hline(y=eval_res["buy_price"], line_dash="dash", line_color="green", annotation_text=f"내 평단가 ({fmt_str.format(eval_res['buy_price'])})")
                    fig_p.add_hline(y=eval_res["trail_line_pct"], line_dash="dash", line_color="red", annotation_text=f"트레일링 스탑 방어선 ({fmt_str.format(eval_res['trail_line_pct'])})")

                    fig_p.update_layout(xaxis_rangeslider_visible=False, height=380, title=f"{item['name']} 매도 방어선 실시간 추적 차트")
                    st.plotly_chart(fig_p, use_container_width=True)

                    if st.button(f"🤖 {item['name']} AI 매도/홀딩 3줄 결론 듣기", key=f"ai_sell_{item['code']}_{idx}"):
                        if not api_key:
                            st.error("👈 왼쪽 사이드바에 Gemini API Key를 먼저 입력해 주세요!")
                        else:
                            with st.spinner("AI 트레이딩 매니저가 매도 타점을 계산 중입니다..."):
                                sell_prompt = f"""
너는 월가 프로 트레이더야. 아래 사용자의 보유 종목 실시간 데이터를 보고 지금 당장 [전량 매도 / 50% 분할 익절 / 보유 유지(홀딩)] 중 무엇을 해야 할지 정확히 3줄 이내로 명쾌하게 코칭해줘.

- 종목: {item['name']} ({item['code']})
- 매수 평단가: {eval_res['buy_price']} {unit} / 현재가: {eval_res['cur_price']} {unit} (수익률: {eval_res['profit_pct']:+.2f}%)
- 매수 후 최고가: {eval_res['peak_price']} {unit} (고점 대비 하락률: {eval_res['drawdown_from_peak']}%)
- 트레일링 스탑 방어선({item['trail_pct']}%): {eval_res['trail_line_pct']} {unit}
- 20일 생명선: {eval_res['ma20']} {unit} / 최근 20일 지지선: {eval_res['support_20']} {unit}
- 현재 RSI(14): {eval_res['rsi']} / 볼린저밴드 상단: {eval_res['bb_upper']} {unit}
- 시스템 판정 시그널: {eval_res['signals']}
"""
                                st.info(call_gemini_ai(api_key, sell_prompt))

elif st.session_state.main_mode == "🔥 AI 주목 종목 스캐너 & 추천":
    st.subheader("🔥 오늘의 주목할 만한 종목 추천 (AI 실시간 퀀트 스캐너)")
    st.caption("국내·미국 대표 주도주 유니버스의 실시간 거래량 급증률, RSI(14), 20일 지지/저항선 돌파 여부를 스캔하여 TOP 3 종목을 발굴합니다.")

    sc_col1, sc_col2 = st.columns([2, 1])
    with sc_col1:
        market_choice = st.selectbox(
            "스캔할 시장을 선택하세요",
            ["🇰🇷 한국 증시 주요 주도주 (코스피·코스닥 핵심 24선)", "🌎 미국 나스닥/S&P 핵심 빅테크·성장주 24선"]
        )
    with sc_col2:
        st.write("")
        st.write("")
        scan_btn = st.button("📡 실시간 유망 종목 스캔 시작", use_container_width=True, type="primary")

    if scan_btn:
        if not api_key:
            st.error("👈 왼쪽 사이드바에 Gemini API Key를 먼저 입력해 주세요!")
            st.stop()

        with st.spinner("⚡ 24개 핵심 종목 실시간 데이터 고속 스캔 중..."):
            df_scanned = scan_market_universe_cached(market_choice)
            st.session_state.scan_df = df_scanned

        if not df_scanned.empty:
            with st.spinner("🤖 월가 AI 헤지펀드 위원회가 TOP 3 종목을 선정 중입니다..."):
                scan_prompt = f"""
너는 월가 퀀트 헤지펀드의 수석 포트폴리오 매니저야.
절대 너의 예전 기억으로 주가를 추측하지 말고, 방금 파이썬 스캐너가 실시간으로 수집한 [종목별 기술적 지표·거래량·RSI 요약 표]와 [현재 시장 공포지수]만을 근거로 오늘 가장 주목해야 할 **핵심 종목 TOP 3**를 선정해줘.

=== [현재 시장 공포지수] ===
- 미국 VIX 지수: {fear_data['vix_val']} ({fear_data['vix_status']})
- CNN 공포·탐욕 지수: {fear_data['fg_val']} ({fear_data['fg_status']})

=== [실시간 퀀트 스캐너 수집 결과 표] ===
{df_scanned.to_string(index=False)}

=== [출력 양식] ===
### 🏆 1. 선정 종목명 (코드/티커) - [전략 유형: 돌파 주도주 / 과매도 반등주 / 추세 지속 우량주 중 택1]
- **선정 핵심 근거:** 스캔된 실제 수치(현재가, 5일 등락률, RSI, 거래량 비율, 고점근접도 등)를 정확히 인용해 설명
- **실전 매매 타점 가이드:** 스캔된 최근 20일 지지선(손절/매수 타점)과 20일 저항선(1차 목표가) 수치를 기반으로 한 손익비 전략 제시
- **주의할 리스크:** 현재 시장 공포지수(VIX)나 단기 과열/하락 측면에서 체크해야 할 점 1줄 요약

(동일한 양식으로 2위, 3위 종목도 이어서 작성해줘.)
"""
                st.session_state.scan_ai_report = call_gemini_ai(api_key, scan_prompt)

    if not st.session_state.scan_df.empty:
        df_show = st.session_state.scan_df
        st.markdown("### 🤖 AI 헤지펀드 위원회 선정 오늘의 TOP 3 브리핑")
        st.markdown(st.session_state.scan_ai_report)
        st.divider()

        st.markdown("### 📊 실시간 퀀트 스캐너 분류표 (전 종목)")
        cat_tabs = st.tabs(["📋 전체 스캔 순위", "🚀 돌파/수급 주도주", "🟢 과매도 눌림목 반등주", "🚩 추세 지속 우량주"])
        with cat_tabs[0]:
            st.dataframe(df_show, use_container_width=True)
        with cat_tabs[1]:
            st.dataframe(df_show[df_show["전략 분류"].str.contains("돌파")], use_container_width=True)
        with cat_tabs[2]:
            st.dataframe(df_show[df_show["전략 분류"].str.contains("과매도")], use_container_width=True)
        with cat_tabs[3]:
            st.dataframe(df_show[df_show["전략 분류"].str.contains("추세")], use_container_width=True)

        st.divider()
        st.markdown("### 🔗 원클릭 정밀 분석 연동")
        link_col1, link_col2 = st.columns([3, 1])
        with link_col1:
            options_list = [f"{r['종목명']} ({r['코드/티커']}) - {r['전략 분류']}" for _, r in df_show.iterrows()]
            selected_option = st.selectbox("정밀 분석할 추천 종목을 선택하세요", options_list)
        with link_col2:
            st.write("")
            st.write("")
            if st.button("🔍 선택한 종목 정밀 분석하기", use_container_width=True, type="primary"):
                picked_code = selected_option.split("(")[1].split(")")[0].strip()
                st.session_state.target_stock = picked_code
                st.session_state.main_mode = "🔍 개별 종목 정밀 분석기"
                st.session_state.auto_run_detail = True
                st.rerun()

else:
    col_in, col_btn = st.columns([3, 1])
    with col_in:
        user_input = st.text_input("국내·해외 기업명(한글/영문) 또는 종목코드/티커를 입력하세요", value=st.session_state.target_stock)
    with col_btn:
        st.write("")
        st.write("")
        run_btn = st.button("🚀 글로벌 AI 정밀 분석 실행", use_container_width=True, type="primary")

    if run_btn or st.session_state.auto_run_detail:
        st.session_state.auto_run_detail = False
        st.session_state.target_stock = user_input

        if not api_key:
            st.error("👈 왼쪽 사이드바에 Gemini API Key를 먼저 입력해 주세요!")
            st.stop()

        code, name, market_type = resolve_stock_query(user_input)
        if not code:
            st.error(f"'{user_input}' 종목을 찾을 수 없습니다. 한글 기업명(예: 애플, 삼성전자) 또는 영문 티커(예: AAPL, NVDA)를 입력해 주세요.")
            st.stop()

        badge = "🇰🇷 한국 증시" if market_type == "KR" else "🌎 글로벌 증시"
        with st.spinner(f"⚡ [{badge}] {name} ({code}) 데이터 스냅샷 로드 및 2,000회 고속 시뮬레이션 중..."):
            if market_type == "KR":
                basic_info, fin_df, supply_df, news_list, price_df = get_kr_data(code)
            else:
                basic_info, fin_df, supply_df, news_list, price_df = get_global_data(code)

            unit = basic_info.get("통화", "")
            sim_res = run_day_trader_simulation(price_df, target_pct, stop_pct, sim_days, 2000)

        st.subheader(f"🏢 [{badge}] {name} ({code}) 실시간 핵심 요약")
        m1, m2, m3, m4 = st.columns(4)
        m1.metric("현재가", basic_info["현재가"])
        m2.metric("시가총액", basic_info["시가총액"])
        m3.metric("PER", basic_info["PER"])
        m4.metric("PBR", basic_info["PBR"])

        chart_summary = "주가 데이터 없음"
        if sim_res:
            chart_summary = (
                f"현재가 {sim_res['cur_price']:,} {unit} | 20일선 {sim_res['ma20']:,} | 60일선 {sim_res['ma60']:,} | "
                f"RSI(14): {sim_res['rsi']} | 최근 20일 지지선 {sim_res['support']:,} / 저항선 {sim_res['resist']:,} | "
                f"포착 패턴: {', '.join(sim_res['patterns'])} | "
                f"2,000회 시뮬레이션({sim_days}일 기준): 목표가(+{target_pct}%, {sim_res['target_price']:,}) 도달확률 {sim_res['hit_target_prob']}%, "
                f"손절선({stop_pct}%, {sim_res['stop_price']:,}) 터치확률 {sim_res['hit_stop_prob']}%"
            )

        tab1, tab2, tab3, tab4 = st.tabs([
            "🏛️ 월가 5대 AI 에이전트 브리핑",
            "🎲 데이트레이더 2,000회 고속 시뮬레이션",
            "📐 자동 추세선/박스 차트 & 뉴스",
            "📊 재무제표 & 기관/수급 원본"
        ])

        with tab2:
            st.markdown("#### 🎲 데이 트레이더 스킬: 차트 자리 포착 & 2,000회 고속 모의 시뮬레이션")
            if sim_res:
                for p in sim_res["patterns"]:
                    st.success(f"**포착된 차트 시그널:** {p}")
                
                s1, s2, s3, s4 = st.columns(4)
                s1.metric(f"목표가 (+{target_pct}%) 도달 확률", f"{sim_res['hit_target_prob']}%", f"목표: {sim_res['target_price']:,} {unit}")
                s2.metric(f"손절선 ({stop_pct}%) 터치 확률", f"{sim_res['hit_stop_prob']}%", f"손절: {sim_res['stop_price']:,} {unit}", delta_color="inverse")
                s3.metric(f"{sim_days}일 후 예상 중앙값", f"{sim_res['median_end']:,} {unit}")
                s4.metric("현재 RSI (14일)", f"{sim_res['rsi']}", "30 이하 과매도 / 70 이상 과열")

                fig_sim = go.Figure()
                for i in range(sim_res["sample_paths"].shape[1]):
                    fig_sim.add_trace(go.Scatter(
                        y=sim_res["sample_paths"][:, i],
                        mode='lines',
                        line=dict(width=1, color='rgba(100, 149, 237, 0.2)'),
                        showlegend=False
                    ))
                fig_sim.add_hline(y=sim_res["target_price"], line_dash="dash", line_color="green", annotation_text=f"목표가 ({sim_res['target_price']:,})")
                fig_sim.add_hline(y=sim_res["stop_price"], line_dash="dash", line_color="red", annotation_text=f"손절선 ({sim_res['stop_price']:,})")
                fig_sim.update_layout(title=f"향후 {sim_days}거래일 주가 시뮬레이션 경로 분포 (2,000회 연산)", xaxis_title="경과 거래일", yaxis_title=f"예상 주가 ({unit})", height=400)
                st.plotly_chart(fig_sim, use_container_width=True)

        with tab3:
            st.markdown("#### 📐 자동 지지/저항 박스 및 이동평균 추세선 차트")
            if price_df is not None and not price_df.empty and sim_res:
                fig_candle = go.Figure()
                fig_candle.add_trace(go.Candlestick(
                    x=price_df.index, open=price_df['Open'], high=price_df['High'],
                    low=price_df['Low'], close=price_df['Close'], name="일봉"
                ))
                fig_candle.add_trace(go.Scatter(x=price_df.index, y=price_df['Close'].rolling(20).mean(), line=dict(color='orange', width=1.5), name="20일 추세선"))
                fig_candle.add_trace(go.Scatter(x=price_df.index, y=price_df['Close'].rolling(60).mean(), line=dict(color='purple', width=1.5), name="60일 추세선"))
                fig_candle.add_hrect(
                    y0=sim_res["support"], y1=sim_res["resist"],
                    fillcolor="rgba(0, 176, 246, 0.1)", line_width=1, line_dash="dot", line_color="blue",
                    annotation_text="최근 20일 매물대 박스 (지지~저항)"
                )
                fig_candle.update_layout(xaxis_rangeslider_visible=False, height=450, title=f"{name} 자동 추세선 & 지지/저항 박스 차트")
                st.plotly_chart(fig_candle, use_container_width=True)

            st.markdown("#### 📰 최신 주요 뉴스")
            for n in news_list:
                st.markdown(f"- `{n['날짜']}` [{n['제목']}]({n['링크']})")

        with tab4:
            st.markdown("#### 🤝 수급 / 글로벌 기관 보유 비중 & 월가 컨센서스")
            st.dataframe(supply_df, use_container_width=True) if not supply_df.empty else st.warning("데이터 없음")
            st.markdown("#### 📊 재무제표 원본")
            st.dataframe(fin_df, use_container_width=True) if not fin_df.empty else st.warning("데이터 없음")

        with tab1:
            with st.spinner("🤖 월가 5대 AI 에이전트 팀 브리핑 생성 중..."):
                prompt = f"""
너는 월가 헤지펀드의 최고 투자 책임자(CIO)이자 5개 전문 팀(펀더멘털 분석팀, 기술적 트레이딩팀, 수급·리서치팀, 리스크 관리팀, 포트폴리오 매니저)을 총괄하는 AI 시스템이야.
절대 추측으로 숫자를 지어내지 말고, 오직 아래 [실시간 수집 데이터 및 시뮬레이션 결과]만을 근거로 한국어로 명확하게 분석해.

=== [실시간 수집 데이터] ===
1. 종목명: {name} ({code}) / 시장: {badge}
2. 기본 지표: {basic_info}
3. 차트 패턴 & 2,000회 시뮬레이션 결과: {chart_summary}
4. 시장 공포지수: VIX {fear_data['vix_val']} ({fear_data['vix_status']}), CNN {fear_data['fg_val']} ({fear_data['fg_status']})
5. 최근 재무제표:
{fin_df.to_string() if not fin_df.empty else "재무제표 추출 실패 (기본 지표 참조)"}
6. 수급 / 기관 보유 및 월가 컨센서스:
{supply_df.to_string() if not supply_df.empty else "수급 데이터 없음"}
7. 최신 뉴스:
{[f"{n['날짜']}: {n['제목']}" for n in news_list]}

=== [출력 양식] ===
### 🎯 최종 판정: [근거 있는 투자] 또는 [감에 의존한 도박]
- **종합 총점:** 60점 만점 중 **OO점** (평균 O.O점)
- **한 줄 핵심 결론:** (재무·수급·시뮬레이션·공포지수를 종합한 결정적 이유)

---
### 🏛️ 월가 5대 AI 에이전트 팀 교차 분석 브리핑
1. **📊 펀더멘털 분석팀 (수익성 OO/10점 · 안정성 OO/10점 · 가치 OO/10점):**
   - 실제 매출, 영업이익, 부채비율, PER/PBR 숫자를 인용해 기업 내재가치 평가
2. **📈 기술적 데이트레이딩팀 (추세 & 시뮬레이션 평가):**
   - 포착된 차트 패턴, 20/60일선 위치, RSI 및 2,000회 시뮬레이션(목표 도달 확률 vs 손절 확률)의 손익비 평가
3. **📰 리서치·수급팀 (성장성 OO/10점 · 수급/기관 OO/10점):**
   - 최신 뉴스 모멘텀과 외국인/기관 수급(해외주식은 글로벌 기관 보유비중 및 월가 목표주가) 수치 인용 평가
4. **🛡️ 리스크 관리팀 (리스크 환경 OO/10점):**
   - VIX/공포지수 현황, 공매도/고점 대비 낙폭 위험, 악재 요인 경고
5. **💼 포트폴리오 매니저 (최종 매매 전략 제시):**
   - 위 4개 팀 의견을 종합한 분할 매수 여부, 핵심 지지선({sim_res['support'] if sim_res else 'N/A'}) 및 저항선({sim_res['resist'] if sim_res else 'N/A'}) 대응 전략
"""
                ai_report = call_gemini_ai(api_key, prompt)
                st.markdown(ai_report)
