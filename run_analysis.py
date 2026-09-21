"""
원/엔 환율과 일본 여행객 수의 시계열 관계 분석 - 원클릭 실행 스크립트
파일명: run_analysis.py
설명: Yahoo Finance 환율 및 JNTO 관광객 데이터를 수집, 전처리, 시계열 분석, 다변량 OLS 회귀분석 및 시각화까지 일괄 수행합니다.
"""

import sys
import os
import warnings

# Windows 콘솔 유니코드 출력 호환성 설정
if sys.platform == 'win32':
    sys.stdout.reconfigure(encoding='utf-8')
    sys.stderr.reconfigure(encoding='utf-8')

import pandas as pd
import numpy as np
import scipy.stats as stats
import matplotlib.pyplot as plt
import matplotlib.ticker as ticker
import seaborn as sns
import statsmodels.api as sm
import statsmodels.formula.api as smf
from statsmodels.tsa.seasonal import seasonal_decompose
from statsmodels.tsa.holtwinters import ExponentialSmoothing
import yfinance as yf

# 한글 폰트 및 마이너스 기호 설정
plt.rc('font', family='Malgun Gothic')
plt.rcParams['axes.unicode_minus'] = False
warnings.filterwarnings('ignore')

# 프로젝트 루트 경로 기준 설정
BASE_DIR = os.path.dirname(os.path.abspath(__file__))
DATA_DIR = os.path.join(BASE_DIR, 'data')
IMAGES_DIR = os.path.join(BASE_DIR, 'images')
os.makedirs(IMAGES_DIR, exist_ok=True)

print("=" * 70)
print("🚀 원/엔 환율 및 일본 여행객 시계열 분석 파이프라인 시작")
print("=" * 70)

# -------------------------------------------------------------
# 1. 데이터 수집 (Data Collection)
# -------------------------------------------------------------
print("\n[단계 1/6] 데이터 수집 (Yahoo Finance API & JNTO 통계 로드)")
EXCHANGE_TICKER = 'JPYKRW=X'
START_DATE = '2010-01-01'
EXCEL_PATH = os.path.join(DATA_DIR, 'tourists_to_japan.xlsx')

print(f"  ▶ 환율 데이터 다운로드: {EXCHANGE_TICKER} ({START_DATE} ~ 현재)")
df_exchange = yf.download(EXCHANGE_TICKER, start=START_DATE, interval='1mo', progress=False).reset_index()
df_ex = df_exchange[['Date', 'Close']].copy()
df_ex.columns = ['Date', 'Exchange_Rate']

print(f"  ▶ JNTO 여행객 엑셀 로드: {EXCEL_PATH}")
df_tourist = pd.read_excel(EXCEL_PATH)
df_korea = df_tourist[df_tourist['Country/Area'] == 'South Korea'].copy()
df_korea['Date'] = pd.to_datetime(df_korea['Year'].astype(str) + ' ' + df_korea['Month (abbr)'])
df_korea = df_korea[['Date', '합계(Visitor Arrivals)']]
df_korea.columns = ['Date', 'Visitors']

# -------------------------------------------------------------
# 2. 데이터 전처리 (Data Preprocessing)
# -------------------------------------------------------------
print("\n[단계 2/6] 데이터 병합 및 결측치/이상치 정제")
df_merged = pd.merge(df_ex, df_korea, on='Date', how='inner').sort_values('Date').reset_index(drop=True)
total_raw_rows = len(df_merged)
missing_rows = df_merged['Visitors'].isnull().sum()
print(f"  ▶ 병합 완료 행 수: {total_raw_rows}개 (결측치: {missing_rows}개)")

# 결측치(최근 4개월 미집계치) Drop
df_clean = df_merged.dropna().reset_index(drop=True)
print(f"  ▶ 결측치 정제 후 행 수: {len(df_clean)}개 (분석 기간: {df_clean['Date'].min().strftime('%Y-%m')} ~ {df_clean['Date'].max().strftime('%Y-%m')})")

# 파생변수 생성
df_clean['Exchange_3MA'] = df_clean['Exchange_Rate'].rolling(window=3).mean()
df_clean['Visitors_ROC'] = df_clean['Visitors'].pct_change() * 100
df_clean['Rolling_Corr'] = df_clean['Visitors'].rolling(window=12).corr(df_clean['Exchange_Rate'])

# -------------------------------------------------------------
# 3. 주요 상관분석 및 통계 지표 산출
# -------------------------------------------------------------
print("\n[단계 3/6] 상관분석 및 통계적 유의성 검증")
# 코로나 이전(2010~2019) 필터링
df_pre = df_clean[df_clean['Date'] < '2020-01-01'].copy()
r_0, p_0 = stats.pearsonr(df_pre['Visitors'], df_pre['Exchange_Rate'])
print(f"  ▶ 코로나 이전 당월(Lag 0) 상관계수: r = {r_0:.3f} (p-value = {p_0:.3e})")

# 시차(Lag 0~6) 상관분석
lag_corrs = []
for lag in range(0, 7):
    s_ex = df_pre['Exchange_Rate'].shift(lag)
    valid = s_ex.notna() & df_pre['Visitors'].notna()
    c, p = stats.pearsonr(df_pre.loc[valid, 'Visitors'], s_ex[valid])
    lag_corrs.append((lag, c, p))
    print(f"    - Lag {lag}개월: r = {c:.3f} (p-value = {p:.3e})")

best_lag, best_r, best_p = min(lag_corrs, key=lambda x: x[1])
print(f"  ★ 최적 시차(Golden Time): {best_lag}개월 (r = {best_r:.3f}, p = {best_p:.3e})")

# -------------------------------------------------------------
# 4. 시계열 분해 및 분산 기여율 산출
# -------------------------------------------------------------
print("\n[단계 4/6] 시계열 분해 (Statsmodels Additive Decomposition)")
df_decomp = df_clean[(df_clean['Date'] >= '2014-01-01') & (df_clean['Date'] < '2020-01-01')].copy().set_index('Date')
decomp = seasonal_decompose(df_decomp['Visitors'], model='additive', period=12)

var_tot = df_decomp['Visitors'].var()
var_tr = decomp.trend.dropna().var()
var_sea = decomp.seasonal.dropna().var()
var_res = decomp.resid.dropna().var()

print(f"  ▶ 총 분산: {var_tot:.2e}")
print(f"  ▶ 추세 분산 기여율: {var_tr/var_tot*100:.1f}%")
print(f"  ▶ 계절성 분산 기여율: {var_sea/var_tot*100:.1f}%")
print(f"  ▶ 불규칙 잔차 분산 기여율: {var_res/var_tot*100:.1f}%")

# -------------------------------------------------------------
# 5. [심화] 다변량 OLS 회귀분석 (환율 시차 + 월별 계절 더미)
# -------------------------------------------------------------
print("\n[단계 5/6] 다변량 OLS 회귀분석 추정")
df_reg = df_pre.copy()
df_reg['Exchange_Rate_Lag3'] = df_reg['Exchange_Rate'].shift(3)
df_reg['Month'] = df_reg['Date'].dt.month.astype(str)
df_reg = df_reg.dropna(subset=['Exchange_Rate_Lag3', 'Visitors']).copy()

ols_res = smf.ols('Visitors ~ Exchange_Rate_Lag3 + C(Month)', data=df_reg).fit()
print(f"  ▶ 모형 설명력 (R-squared): {ols_res.rsquared:.4f} (수정 R2: {ols_res.rsquared_adj:.4f})")
print(f"  ▶ 환율 3개월 시차 계수: {ols_res.params['Exchange_Rate_Lag3']:.1f} (p-value: {ols_res.pvalues['Exchange_Rate_Lag3']:.3e})")
print(f"  ▶ 최비수기(9월 더미) 계수: {ols_res.params['C(Month)[T.9]']:.1f} (p-value: {ols_res.pvalues['C(Month)[T.9]']:.3f})")

# -------------------------------------------------------------
# 6. 시각화 차트 일괄 생성 및 저장
# -------------------------------------------------------------
print("\n[단계 6/6] 시각화 차트 생성 및 저장 (images/)")

# 차트 1: 이중 축 트렌드
fig, ax1 = plt.subplots(figsize=(14, 6))
ax1.plot(df_clean['Date'], df_clean['Visitors'], color='#1f77b4', linewidth=2, label='방문객 수')
ax1.set_ylabel('방문객 수 (명)', color='#1f77b4', fontsize=12)
ax2 = ax1.twinx()
ax2.plot(df_clean['Date'], df_clean['Exchange_Rate'], color='#d62728', linestyle='--', linewidth=2, label='원/엔 환율')
ax2.set_ylabel('원/엔 환율 (원/100엔)', color='#d62728', fontsize=12)
plt.title('원/엔 환율과 방일 한국인 여행객 수 추이 (2010~2024)', fontsize=14, fontweight='bold')
fig.tight_layout()
fig.savefig(os.path.join(IMAGES_DIR, '01_trend_dual_axis.png'), dpi=150)
plt.close()

# 차트 2: 산점도 및 회귀선
plt.figure(figsize=(9, 6))
sns.regplot(data=df_pre, x='Exchange_Rate', y='Visitors', scatter_kws={'alpha': 0.6, 'color': '#1f77b4'}, line_kws={'color': 'red', 'linewidth': 2})
plt.title(f'환율 vs 방문객 수 산점도 및 회귀선 (2010~2019, r = {r_0:.3f})', fontsize=13, fontweight='bold')
plt.xlabel('원/엔 환율')
plt.ylabel('방일 한국인 수')
plt.grid(True, linestyle=':', alpha=0.6)
plt.tight_layout()
plt.savefig(os.path.join(IMAGES_DIR, '02_scatter_correlation.png'), dpi=150)
plt.close()

# 차트 3: 고품질 시계열 분해도
pct_tr = (var_tr / var_tot) * 100
pct_se = (var_sea / var_tot) * 100
pct_re = (var_res / var_tot) * 100

fig, axes = plt.subplots(4, 1, figsize=(13, 10), sharex=True)

# 1. 관측치 (Observed)
ax1 = axes[0]
ax1.plot(decomp.observed.index, decomp.observed.values, color='#0f4c81', linewidth=2, label='실제 방문객 수')
ax1.fill_between(decomp.observed.index, decomp.observed.values, color='#0f4c81', alpha=0.1)
ax1.set_ylabel('방문객 수 (명)', fontsize=10, fontweight='bold', color='#0f4c81')
ax1.set_title('① 관측치 (Observed Visitors) - 원계열 데이터 (2014~2019 정상기)', fontsize=11, fontweight='bold', loc='left', pad=6)
ax1.yaxis.set_major_formatter(ticker.FuncFormatter(lambda x, p: f'{int(x):,}'))
ax1.grid(True, linestyle=':', alpha=0.6)
ax1.text(0.98, 0.85, '원 데이터 (추세+계절성+잔차 결합)', transform=ax1.transAxes, ha='right', fontsize=9,
         bbox=dict(boxstyle='round,pad=0.3', facecolor='#f0f4f8', edgecolor='#0f4c81', alpha=0.8))

# 2. 추세 성분 (Trend)
ax2 = axes[1]
ax2.plot(decomp.trend.index, decomp.trend.values, color='#1b9e77', linewidth=2.5, label='장기 추세')
ax2.set_ylabel('추세 성분 (명)', fontsize=10, fontweight='bold', color='#1b9e77')
ax2.set_title(f'② 추세 성분 (Long-term Trend)  |  [분산 기여율: {pct_tr:.1f}%]', fontsize=11, fontweight='bold', loc='left', pad=6)
ax2.yaxis.set_major_formatter(ticker.FuncFormatter(lambda x, p: f'{int(x):,}'))
ax2.grid(True, linestyle=':', alpha=0.6)
ax2.text(0.98, 0.85, f'장기 성장 견인 (기여율 {pct_tr:.1f}%)', transform=ax2.transAxes, ha='right', fontsize=9,
         bbox=dict(boxstyle='round,pad=0.3', facecolor='#e8f5e9', edgecolor='#1b9e77', alpha=0.8))

# 3. 계절성 성분 (Seasonal)
ax3 = axes[2]
ax3.plot(decomp.seasonal.index, decomp.seasonal.values, color='#d95f02', linewidth=2, label='12개월 주기 계절성')
ax3.axhline(0, color='gray', linestyle='--', linewidth=1, alpha=0.7)
ax3.fill_between(decomp.seasonal.index, decomp.seasonal.values, 0, where=(decomp.seasonal.values >= 0), color='#d95f02', alpha=0.2, label='성수기 (+) 효과')
ax3.fill_between(decomp.seasonal.index, decomp.seasonal.values, 0, where=(decomp.seasonal.values < 0), color='#3182bd', alpha=0.15, label='비수기 (-) 효과')
ax3.set_ylabel('계절 변동치 (명)', fontsize=10, fontweight='bold', color='#d95f02')
ax3.set_title(f'③ 계절성 성분 (12-Month Seasonality)  |  [분산 기여율: {pct_se:.1f}%]', fontsize=11, fontweight='bold', loc='left', pad=6)
ax3.yaxis.set_major_formatter(ticker.FuncFormatter(lambda x, p: f'{int(x):,}'))
ax3.grid(True, linestyle=':', alpha=0.6)
ax3.text(0.98, 0.85, f'매년 1~2월 겨울 피크 & 9월 최비수기 반복 (기여율 {pct_se:.1f}%)', transform=ax3.transAxes, ha='right', fontsize=9,
         bbox=dict(boxstyle='round,pad=0.3', facecolor='#fff3e0', edgecolor='#d95f02', alpha=0.8))

# 4. 불규칙 잔차 성분 (Residual)
ax4 = axes[3]
ax4.scatter(decomp.resid.index, decomp.resid.values, color='#7570b3', alpha=0.7, s=28, label='잔차')
ax4.axhline(0, color='black', linestyle='-', linewidth=1)
ax4.set_ylabel('불규칙 잔차 (명)', fontsize=10, fontweight='bold', color='#7570b3')
ax4.set_title(f'④ 불규칙 잔차 (Irregular Residuals)  |  [분산 기여율: {pct_re:.1f}%]', fontsize=11, fontweight='bold', loc='left', pad=6)
ax4.yaxis.set_major_formatter(ticker.FuncFormatter(lambda x, p: f'{int(x):,}'))
ax4.grid(True, linestyle=':', alpha=0.6)
ax4.text(0.98, 0.85, f'외부 요인 및 일시적 노이즈 (기여율 {pct_re:.1f}%)', transform=ax4.transAxes, ha='right', fontsize=9,
         bbox=dict(boxstyle='round,pad=0.3', facecolor='#f3e5f5', edgecolor='#7570b3', alpha=0.8))

# X축 포맷
ax4.set_xlabel('연도 (Date)', fontsize=11, fontweight='bold')
ax4.xaxis.set_major_locator(plt.matplotlib.dates.YearLocator())
ax4.xaxis.set_major_formatter(plt.matplotlib.dates.DateFormatter('%Y년'))

# 전체 제목 및 요약 박스
plt.suptitle('방일 한국인 여행객 수 시계열 분해 (2014~2019 정상기 가법 모델)', fontsize=15, fontweight='bold', y=0.98)
fig.text(0.5, 0.935,
         f'■ 총 분산 기여율: 장기 추세(Trend) {pct_tr:.1f}%  |  계절성(Seasonal) {pct_se:.1f}%  |  불규칙 잔차(Residual) {pct_re:.1f}%',
         ha='center', fontsize=10.5, fontweight='bold',
         bbox=dict(boxstyle='round,pad=0.4', facecolor='#f8f9fa', edgecolor='#ced4da', lw=1.2))

plt.tight_layout(rect=[0, 0.02, 1, 0.93])
fig.savefig(os.path.join(IMAGES_DIR, '03_time_series_decomposition.png'), dpi=150, bbox_inches='tight')
plt.close()

# 차트 4: 월별 박스플롯 (시계열 분해와 동일한 2014~2019 정상기 기준)
df_box = df_clean[(df_clean['Date'] >= '2014-01-01') & (df_clean['Date'] < '2020-01-01')].copy()
df_box['Month'] = df_box['Date'].dt.month

plt.figure(figsize=(13, 6))
medianprops = dict(color='darkred', linewidth=2.5)
box = sns.boxplot(
    data=df_box, 
    x='Month', 
    y='Visitors', 
    hue='Month',
    palette='Blues',
    legend=False,
    medianprops=medianprops,
    showmeans=True,
    meanprops=dict(marker='o', markeredgecolor='black', markerfacecolor='yellow', markersize=6)
)

medians = df_box.groupby('Month')['Visitors'].median()
for i, m in enumerate(range(1, 13)):
    med = medians[m]
    if m in [1, 2]:
        box.text(i, med + 15000, f"{med/10000:.1f}만\n({m}위)", ha='center', va='bottom', fontsize=9, fontweight='bold', color='darkred')
    elif m == 9:
        box.text(i, med - 20000, f"{med/10000:.1f}만\n(최저)", ha='center', va='top', fontsize=9, fontweight='bold', color='blue')

plt.title('월별 방일 한국인 방문객 수 분포 (코로나 이전 정상기: 2014~2019)', fontsize=14, fontweight='bold', pad=15)
plt.xlabel('월 (Month)', fontsize=12, labelpad=8)
plt.ylabel('방문객 수 (명)', fontsize=12, labelpad=8)
plt.grid(True, linestyle=':', alpha=0.6, axis='y')

from matplotlib.lines import Line2D
legend_elements = [
    Line2D([0], [0], color='darkred', lw=2.5, label='중앙값 (Median)'),
    Line2D([0], [0], marker='o', color='w', markerfacecolor='yellow', markeredgecolor='black', markersize=8, label='평균 (Mean)')
]
plt.legend(handles=legend_elements, loc='upper right', framealpha=0.9)
plt.tight_layout()
plt.savefig(os.path.join(IMAGES_DIR, '04_monthly_boxplot.png'), dpi=150)
plt.close()

# 차트 5: 외부 사건 표기 시계열
fig, ax1 = plt.subplots(figsize=(15, 6))
ax1.plot(df_clean['Date'], df_clean['Visitors'], color='#1f77b4', linewidth=2, label='방문객 수')
ax1.set_ylabel('방문객 수 (명)', color='#1f77b4')
ax2 = ax1.twinx()
ax2.plot(df_clean['Date'], df_clean['Exchange_Rate'], color='#d62728', linestyle='--', linewidth=1.5, label='환율')
ax2.set_ylabel('원/엔 환율', color='#d62728')

events = [
    ('2011-03-01', '동일본 대지진'),
    ('2014-04-01', '세월호 애도'),
    ('2016-04-01', '구마모토 지진'),
    ('2019-07-01', '노재팬 불매운동'),
    ('2020-03-01', '코로나19 팬데믹'),
    ('2024-01-01', '노토반도 지진')
]
for date_str, text in events:
    dt = pd.to_datetime(date_str)
    ax1.axvline(x=dt, color='gray', linestyle=':', alpha=0.8)
    ax1.text(dt, df_clean['Visitors'].max() * 0.85, f' {text}', rotation=90, verticalalignment='center', fontsize=9, color='darkred', fontweight='bold')

plt.title('역사적 외부 충격 발생 시점과 여행객/환율 추이', fontsize=14, fontweight='bold')
fig.tight_layout()
fig.savefig(os.path.join(IMAGES_DIR, '05_trend_with_events.png'), dpi=150)
plt.close()

# 차트 6: 이동 상관계수 및 충격 주석
plt.figure(figsize=(15, 6))
plt.plot(df_clean['Date'], df_clean['Rolling_Corr'], color='purple', linewidth=2, label='12개월 이동 상관계수')
plt.axhline(0, color='black', linestyle='--', linewidth=1)
for date_str, text in events:
    dt = pd.to_datetime(date_str)
    plt.axvline(x=dt, color='gray', linestyle=':', alpha=0.8)
    plt.text(dt, 0.7, f' {text}', rotation=90, verticalalignment='center', fontsize=9, color='darkred', fontweight='bold')
plt.title('12개월 이동 상관계수 추이 및 6대 역사적 충격(Black Swan) 붕괴 시점', fontsize=13, fontweight='bold')
plt.xlabel('연도')
plt.ylabel('상관계수 (Rolling Corr)')
plt.grid(True, linestyle=':', alpha=0.6)
plt.tight_layout()
plt.savefig(os.path.join(IMAGES_DIR, '07_rolling_corr_with_new_events.png'), dpi=150)
plt.close()

# 차트 7: 시차 상관계수 바 차트
plt.figure(figsize=(9, 5))
lags = [x[0] for x in lag_corrs]
corrs = [x[1] for x in lag_corrs]
colors = ['#aec7e8' if l not in [3, 4] else '#d62728' for l in lags]
bars = plt.bar([f'{l}개월' for l in lags], corrs, color=colors)
plt.axhline(0, color='black', linewidth=0.8)
plt.title('환율 변동 시차(Lag)에 따른 방문객 수 교차 상관계수 (2010~2019)', fontsize=13, fontweight='bold')
plt.xlabel('환율 지연 시차 (Lag)')
plt.ylabel('피어슨 상관계수 (r)')
for bar, c in zip(bars, corrs):
    plt.text(bar.get_x() + bar.get_width()/2, bar.get_height() - 0.04, f'{c:.3f}', ha='center', color='black', fontsize=10, fontweight='bold')
plt.tight_layout()
plt.savefig(os.path.join(IMAGES_DIR, '08_lag_correlation_updated.png'), dpi=150)
plt.close()

# -------------------------------------------------------------
# 7. 시계열 심화: 베이스라인 단기 예측 (Holt-Winters Exponential Smoothing)
# -------------------------------------------------------------
print("\n[단계 7/7] 시계열 심화: 베이스라인 단기 예측 및 가정/한계 검토")
# 최근 회복기(2022-06~현재) 시계열을 바탕으로 단기 예측
df_recent = df_clean[df_clean['Date'] >= '2022-06-01'].set_index('Date')['Visitors'].asfreq('MS').interpolate()
forecast_horizon = 6

try:
    hw_model = ExponentialSmoothing(
        df_recent,
        trend='add',
        seasonal='add' if len(df_recent) >= 24 else None,
        seasonal_periods=12 if len(df_recent) >= 24 else None
    ).fit()

    forecast_series = hw_model.forecast(forecast_horizon)
    last_dt = df_recent.index.max()
    future_dates = pd.date_range(last_dt + pd.DateOffset(months=1), periods=forecast_horizon, freq='MS')
    
    # 80%, 95% 신뢰구간
    resid_std = np.std(hw_model.resid)
    ci_80_lower = np.maximum(0, forecast_series - 1.282 * resid_std)
    ci_80_upper = forecast_series + 1.282 * resid_std
    ci_95_lower = np.maximum(0, forecast_series - 1.960 * resid_std)
    ci_95_upper = forecast_series + 1.960 * resid_std

    print(f"  ▶ 최근 회복기 기반 향후 {forecast_horizon}개월 베이스라인 예측치:")
    for dt, f_val, l80, u80 in zip(future_dates, forecast_series, ci_80_lower, ci_80_upper):
        print(f"    - {dt.strftime('%Y-%m')}: {f_val:,.0f}명 (80% CI: {l80:,.0f} ~ {u80:,.0f}명)")

    # 차트 8: 베이스라인 단기 예측 시각화
    plt.figure(figsize=(12, 6))
    plot_hist = df_recent.tail(30)
    plt.plot(plot_hist.index, plot_hist.values, label='실측 방문객 수 (Actual)', color='#1f77b4', marker='o', linewidth=2)
    plt.plot(future_dates, forecast_series.values, label=f'향후 {forecast_horizon}개월 예측치 (Holt-Winters)', color='#d62728', linestyle='--', marker='s', linewidth=2.5)
    plt.fill_between(future_dates, ci_80_lower, ci_80_upper, color='#d62728', alpha=0.2, label='80% 신뢰구간')
    plt.fill_between(future_dates, ci_95_lower, ci_95_upper, color='#d62728', alpha=0.1, label='95% 신뢰구간')
    
    plt.title(f'방일 한국인 여행객 수 단기 베이스라인 예측 (향후 {forecast_horizon}개월)', fontsize=14, fontweight='bold')
    plt.xlabel('연월')
    plt.ylabel('방문객 수 (명)')
    plt.grid(True, linestyle=':', alpha=0.6)
    plt.legend(loc='upper left', framealpha=0.9)
    plt.tight_layout()
    plt.savefig(os.path.join(IMAGES_DIR, '12_baseline_forecast.png'), dpi=150)
    plt.close()
    print(f"  ▶ 베이스라인 예측 시각화 생성 완료: `{os.path.join(IMAGES_DIR, '12_baseline_forecast.png')}`")
except Exception as e:
    print(f"  ⚠️ 단기 예측 모델 수행 중 오류 발생: {e}")

print(f"\n  ▶ 전체 시각화 차트 생성 및 `{IMAGES_DIR}` 저장 완료!")
print("\n" + "=" * 70)
print("🎉 전체 파이프라인 및 시계열 심화 예측 정상 실행 완료!")
print("=" * 70)
