import os

# 强力清除代理，确保在对方电脑上也是直连
os.environ['http_proxy'] = ''
os.environ['https_proxy'] = ''
os.environ['HTTP_PROXY'] = ''
os.environ['HTTPS_PROXY'] = ''
os.environ['all_proxy'] = ''
os.environ['ALL_PROXY'] = ''

import pandas as pd
import streamlit as st
import akshare as ak
import datetime

st.set_page_config(page_title="尾盘量化雷达 (完整版)", page_icon="🎯", layout="wide")

# ==========================================
# 1. 侧边栏：核心参数设置 (完全对应纸上要求)
# ==========================================
st.sidebar.header("⚙️ 选股参数设置")
st.sidebar.markdown("**尾盘收盘前30分钟执行 (14:30)**")

st.sidebar.subheader("一、 量价与基本面")
price_min, price_max = st.sidebar.slider("涨幅设置 (%)", -10.0, 10.0, (2.0, 5.0))
min_vol_ratio = st.sidebar.number_input("最低量比 (<1的删除)", value=1.0, step=0.1)
turnover_min, turnover_max = st.sidebar.slider("换手率范围 (%)", 0.0, 20.0, (5.0, 10.0))
mcap_min, mcap_max = st.sidebar.slider("市值范围 (亿元)", 0, 500, (50, 200))

st.sidebar.subheader("二、 趋势与形态")
st.sidebar.markdown("✅ 股价在均线之上\n✅ 5日或30日线趋势向上\n✅ 首阴信号 (昨阳今阴)")


# ==========================================
# 2. 核心数据获取与处理逻辑
# ==========================================
@st.cache_data(ttl=60)
def get_market_spot():
    """获取全市场实时行情并做量价初筛"""
    df = ak.stock_zh_a_spot_em()  # 使用东方财富全量接口
    df = df[['代码', '名称', '最新价', '今开', '涨跌幅', '换手率', '量比', '总市值', '成交额']].dropna()
    df['总市值(亿)'] = df['总市值'] / 1e8
    df['成交额(亿)'] = df['成交额'] / 1e8

    # 基础过滤：严格执行纸上的硬性指标
    cond = (
            (df['涨跌幅'] >= price_min) & (df['涨跌幅'] <= price_max) &
            (df['量比'] >= min_vol_ratio) &
            (df['换手率'] >= turnover_min) & (df['换手率'] <= turnover_max) &
            (df['总市值(亿)'] >= mcap_min) & (df['总市值(亿)'] <= mcap_max)
    )
    return df[cond].copy()


def check_technical_indicators(symbol, current_price, current_open):
    """验证均线、趋势和首阴"""
    try:
        hist = ak.stock_zh_a_hist(symbol=symbol, period="daily", adjust="qfq")
        if len(hist) < 30: return False

        hist['MA5'] = hist['收盘'].rolling(window=5).mean()
        hist['MA30'] = hist['收盘'].rolling(window=30).mean()

        latest = hist.iloc[-1]
        prev = hist.iloc[-2]

        # 1. 在均线之上
        above_ma = (current_price > latest['MA5']) and (current_price > latest['MA30'])
        # 2. 均线趋势向上
        trend_up = (latest['MA5'] > prev['MA5']) or (latest['MA30'] > prev['MA30'])
        # 3. 首阴信号：昨日收阳，今日收阴
        prev_is_yang = prev['收盘'] > prev['开盘']
        is_yin_today = current_price < current_open
        first_yin = prev_is_yang and is_yin_today

        return above_ma and trend_up and first_yin
    except:
        return False


# ==========================================
# 3. 页面主渲染与交互
# ==========================================
st.title("🎯 A股尾盘 (14:30) 全量化雷达")
st.markdown("已接入东方财富实时数据：包含全量价过滤、均线趋势与首阴提醒。")

if st.button("🚀 获取今日 14:30 选股结果", type="primary"):
    with st.spinner("正在获取全市场实时数据并进行量价初筛..."):
        spot_df = get_market_spot()

    st.info(
        f"第一阶段完成：基础量价筛选后，剩余 {len(spot_df)} 只股票。开始逐个计算历史K线与形态，请耐心等待 (约1-3分钟)...")

    final_pool = []
    progress_bar = st.progress(0)

    for i, (index, row) in enumerate(spot_df.iterrows()):
        symbol = row['代码']
        if check_technical_indicators(symbol, row['最新价'], row['今开']):
            stock_info = {
                "代码": symbol, "名称": row['名称'], "最新价": row['最新价'],
                "涨跌幅(%)": row['涨跌幅'], "换手率(%)": row['换手率'], "量比": row['量比'],
                "成交额(亿)": round(row['成交额(亿)'], 2), "市值(亿)": round(row['总市值(亿)'], 2),
                "信号": "首阴+均线向上"
            }
            final_pool.append(stock_info)

        # 更新进度条
        progress_bar.progress((i + 1) / len(spot_df))

    if final_pool:
        st.success(f"🎯 策略执行完毕！共筛选出 {len(final_pool)} 只完全符合纸上所有条件的股票。")
        final_df = pd.DataFrame(final_pool)
        final_df = final_df.sort_values(by="成交额(亿)", ascending=False)
        st.dataframe(final_df, use_container_width=True, hide_index=True)
    else:
        st.warning("今日市场暂无完全符合所有硬性指标的股票。建议在左侧稍微放宽参数范围。")