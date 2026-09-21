# 🤖 AI 활용 프롬프트 및 응답 검증 로그 (AI Interaction Log)

본 문서는 '원/엔 환율과 일본 여행객 수의 시계열 관계 분석' 프로젝트를 수행하는 과정에서 AI에게 질의한 실제 프롬프트(User Prompt), AI의 주요 응답 코드 및 해설(AI Response), 그리고 이를 분석가가 직접 검증하고 수정한 내역(User Validation)을 투명하게 기록한 로그 파일입니다.

---

## 📋 목차
1. [데이터 수집: Yahoo Finance 및 JNTO 데이터 처리](#1-데이터-수집-yahoo-finance-및-jnto-데이터-처리)
2. [데이터 전처리: 결측치(NaN) 처리 기준 수립](#2-데이터-전처리-결측치nan-처리-기준-수립)
3. [시계열 분석: Statsmodels 가법 분해 및 계절성 분리](#3-시계열-분석-statsmodels-가법-분해-및-계절성-분리)
4. [심층 분석: 12개월 롤링 상관계수 및 역사적 사건 표기](#4-심층-분석-12개월-롤링-상관계수-및-역사적-사건-표기)
5. [시차 분석: 0~6개월 Lag 교차 상관계수 및 p-value 검증](#5-시차-분석-06개월-lag-교차-상관계수-및-p-value-검증)
6. [심화 모델링: 다변량 OLS 회귀분석 (환율 시차 + 월 더미)](#6-심화-모델링-다변량-ols-회귀분석-환율-시차--월-더미)

---

## 1. 데이터 수집: Yahoo Finance 및 JNTO 데이터 처리

### 💬 분석가 프롬프트 (User Prompt)
> "파이썬 `yfinance`로 2010년부터 현재까지의 원/엔 환율(JPY/KRW) 월별 데이터를 다운로드하고, JNTO 외래객 엑셀 파일(`tourists_to_japan.xlsx`)에서 한국인 방문객 데이터만 뽑아서 `Date` 기준으로 inner join 병합하는 코드를 작성해 줘."

### 🤖 AI 주요 응답 스니펫 (AI Response)
```python
import pandas as pd
import yfinance as yf

# 환율 다운로드
df_exchange = yf.download('JPYKRW=X', start='2010-01-01', interval='1mo', progress=False).reset_index()
df_ex = df_exchange[['Date', 'Close']].rename(columns={'Close': 'Exchange_Rate'})

# 관광객 데이터 로드 및 필터링
df_tourist = pd.read_excel('data/tourists_to_japan.xlsx')
df_korea = df_tourist[df_tourist['Country/Area'] == 'South Korea'].copy()
df_korea['Date'] = pd.to_datetime(df_korea['Year'].astype(str) + ' ' + df_korea['Month (abbr)'])
df_korea = df_korea[['Date', '합계(Visitor Arrivals)']].rename(columns={'합계(Visitor Arrivals)': 'Visitors'})

# Inner Join 병합
df_merged = pd.merge(df_ex, df_korea, on='Date', how='inner')
```

### 🔍 분석가 검증 및 수정 (User Validation)
* **검증:** `df_korea['Month (abbr)']` 파싱 시 영문 축약형 월(e.g., 'Dec.')이 정상 인식되는지 확인.
* **수정 조치:** 날짜 정렬이 뒤섞이는 현상을 방지하기 위해 `df_merged.sort_values('Date').reset_index(drop=True)`를 반드시 체이닝하도록 코드 보완.

---

## 2. 데이터 전처리: 결측치(NaN) 처리 기준 수립

### 💬 분석가 프롬프트 (User Prompt)
> "JNTO 데이터의 최근 4개월 치가 아직 집계되지 않아 Visitors 컬럼에 NaN이 들어가 있어. 이걸 평균값으로 채우는 게 좋을까, 아니면 dropna()로 삭제하는 게 맞을까? 시계열 상관분석 관점에서 알려줘."

### 🤖 AI 주요 응답 스니펫 (AI Response)
> "최근 4개월 치의 결측치는 '데이터 수집 시점의 지연'으로 인한 미발표 데이터입니다. 이를 평균값이나 0으로 채우면 최근 엔저 시점의 여행객 수를 심각하게 왜곡시켜 환율과의 음의 상관관계를 인위적으로 약화시킵니다. 따라서 시계열 상관분석에서는 이 4개월을 완전히 삭제(`dropna()`)하여 실제 집계 완료된 2024년 4월까지만을 분석 대상으로 삼는 것이 데이터 무결성 측면에서 가장 타당합니다."

### 🔍 분석가 검증 및 수정 (User Validation)
* **검증:** 민감도 분석(Sensitivity Analysis) 스크립트를 작성하여 Drop($r=-0.508$) vs Forward Fill($r=-0.525$) vs 0-Fill($r=-0.465$)의 결과를 직접 비교 계산함.
* **채택:** AI 권고대로 Drop 처리가 왜곡이 가장 적음을 확인하고 채택.

---

## 3. 시계열 분석: Statsmodels 가법 분해 및 계절성 분리

### 💬 분석가 프롬프트 (User Prompt)
> "`statsmodels`의 `seasonal_decompose`를 사용해서 코로나 이전(2014~2019) 방일 한국인 수의 계절성을 분석하려고 해. 승법(Multiplicative)과 가법(Additive) 중 무엇을 써야 하고, 분해 주기(period)는 몇으로 줘야 해?"

### 🤖 AI 주요 응답 스니펫 (AI Response)
```python
from statsmodels.tsa.seasonal import seasonal_decompose

# 월별 데이터이므로 연간 주기는 period=12
# 계절 변동 폭이 추세 상승에 비례하여 급격히 커지지 않는 구간이므로 가법 모델(additive) 권장
decomp = seasonal_decompose(df_pre_covid['Visitors'], model='additive', period=12)
fig = decomp.plot()
fig.set_size_inches(12, 8)
```

### 🔍 분석가 검증 및 수정 (User Validation)
* **검증:** 분해 결과 그래프에서 Seasonal 성분이 매년 동일한 시기(1~2월 연초)에 뚜렷한 피크를 보이는지 확인.
* **추가 분석:** 단순 시각화에 그치지 않고, 총 분산 대비 추세 분산(63.6%)과 계절성 분산(8.2%)의 분산 기여율을 정량 산출하는 분석 코드를 추가함.

---

## 4. 심층 분석: 12개월 롤링 상관계수 및 역사적 사건 표기

### 💬 분석가 프롬프트 (User Prompt)
> "2010년부터 2024년까지 원/엔 환율과 방문객 수 사이의 12개월 롤링 상관계수를 그리고, 동일본 대지진(2011.03), 세월호(2014.04), 구마모토 지진(2016.04), 노재팬(2019.07), 코로나(2020.03) 발생 시점을 그래프에 수직 점선과 텍스트로 표시해 줘."

### 🤖 AI 주요 응답 스니펫 (AI Response)
```python
df_clean['Rolling_Corr'] = df_clean['Visitors'].rolling(window=12).corr(df_clean['Exchange_Rate'])

plt.figure(figsize=(15, 6))
plt.plot(df_clean['Date'], df_clean['Rolling_Corr'], color='purple', linewidth=2)
plt.axhline(0, color='black', linestyle='--')

events = [
    ('2011-03-01', '동본 대지진'),
    ('2014-04-01', '세월호 애도'),
    ('2016-04-01', '구마모토 지진'),
    ('2019-07-01', '노재팬'),
    ('2020-03-01', '코로나19')
]
for dt, label in events:
    plt.axvline(pd.to_datetime(dt), color='gray', linestyle=':')
    plt.text(pd.to_datetime(dt), 0.7, label, rotation=90)
```

### 🔍 분석가 검증 및 수정 (User Validation)
* **오류 수정:** Windows 환경에서 텍스트 회전 시 한글 폰트가 깨지거나 그래프 범위를 벗어나는 레이아웃 문제 수정 (`plt.tight_layout()`, `fontsize=9`, `color='darkred'`).
* **사건 추가:** 2024년 1월 노토반도 지진 및 난카이 해곡 지진 주의보 시점을 추가하여 분석을 최신화함.

---

## 5. 시차 분석: 0~6개월 Lag 교차 상관계수 및 p-value 검증

### 💬 분석가 프롬프트 (User Prompt)
> "환율 하락 효과가 실제 여행객 수 증가로 나타나기까지 몇 개월 걸리는지 보려고 해. 0개월부터 6개월까지 shift해서 피어슨 상관계수와 p-value를 계산하고 막대그래프로 시각화해 줘."

### 🤖 AI 주요 응답 스니펫 (AI Response)
```python
import scipy.stats as stats

lags = range(0, 7)
corrs = []
for lag in lags:
    s_ex = df_lag['Exchange_Rate'].shift(lag)
    valid = s_ex.notna() & df_lag['Visitors'].notna()
    r, p = stats.pearsonr(df_lag.loc[valid, 'Visitors'], s_ex[valid])
    corrs.append((lag, r, p))
```

### 🔍 분석가 검증 및 수정 (User Validation)
* **검증:** Lag 3과 Lag 4에서 상관계수가 -0.632로 최고점을 찍고 $p$-value가 $2.028 \times 10^{-14}$로 극도로 유의미함을 확인.
* **시각화 개선:** 최고점을 기록한 3개월과 4개월 막대를 강조색(빨간색)으로 하이라이트하고, 막대 상단에 수치를 표기하도록 스타일링 보강.

---

## 6. 심화 모델링: 다변량 OLS 회귀분석 (환율 시차 + 월 더미)

### 💬 분석가 프롬프트 (User Prompt)
> "단순 상관분석을 넘어서 환율 3개월 시차(Lag 3)와 12개 월 더미 변수를 결합한 다변량 회귀분석을 statsmodels로 수행하고, 모형 설명력(R-squared)과 각 월별 회귀계수를 출력하는 코드를 짜줘."

### 🤖 AI 주요 응답 스니펫 (AI Response)
```python
import statsmodels.formula.api as smf

df_reg = df_clean[df_clean['Date'] < '2020-01-01'].copy()
df_reg['Exchange_Rate_Lag3'] = df_reg['Exchange_Rate'].shift(3)
df_reg['Month'] = df_reg['Date'].dt.month.astype(str)
df_reg = df_reg.dropna(subset=['Exchange_Rate_Lag3', 'Visitors'])

ols_model = smf.ols('Visitors ~ Exchange_Rate_Lag3 + C(Month)', data=df_reg).fit()
print(ols_model.summary())
```

### 🔍 분석가 검증 및 수정 (User Validation)
* **검증:** $R^2 = 0.4523$ 도출 확인. 기준월인 1월 대비 9월 더미(`C(Month)[T.9]`)의 계수가 $-169,114.8$ ($p=0.015$)로 가장 큰 음수임을 확인하여 박스플롯 분석의 결론(9월 최비수기)과 완벽히 일치함을 교차 검증 완료.

---

## 7. 보너스 과제 1: 분석 결과 웹 대시보드 서비스화 (Streamlit + Plotly)

### 💬 분석가 프롬프트 (User Prompt)
> "분석 결과를 간단한 웹 대시보드로 구성해 '기간/조건을 바꿔보며' 탐색 가능하게 만들어줘. 기간 프리셋 및 슬라이더, 환율 시차(Lag 0~6) 조정, 6대 역사적 사건 토글, 시계열 분해 및 단기 예측 시뮬레이션이 가능한 Streamlit 대시보드(`app.py`)를 개발해 줘."

### 🤖 AI 주요 응답 스니펫 (AI Response)
```python
import streamlit as st
import plotly.express as px
import plotly.graph_objects as go
from plotly.subplots import make_subplots

st.set_page_config(page_title="방일 여행객 & 원/엔 환율 대시보드", layout="wide")
# 사이드바 기간 및 Lag 슬라이더
period_mode = st.sidebar.radio("분석 기간", ["전체 기간", "코로나 이전", "회복기", "직접 지정"])
selected_lag = st.sidebar.slider("환율 시차 (Lag)", 0, 6, 3)
show_events = st.sidebar.checkbox("6대 역사적 충격 오버레이", True)

# 5개 탭 구성 (동향, 회귀/시차 시뮬레이션, 분해, 단기 예측, 인사이트)
tab1, tab2, tab3, tab4, tab5 = st.tabs([...])
```

### 🔍 분석가 검증 및 수정 (User Validation)
* **로컬 구동 검증:** `pip install streamlit plotly` 후 `streamlit run app.py`를 실행하여 5개 탭과 사이드바 필터가 상호작용 시 에러 없이 부드럽게 반응형으로 작동함을 확인.
* **사용자 가이드 작성:** 평가 제출 요건인 `(2) 로컬 실행 방법 문서` 및 `(3) 대시보드 스크린샷 세트 및 시나리오 설명서`를 포괄하는 `DASHBOARD_GUIDE.md`를 신규 작성하여 완벽한 제출 패키지 구성 완료.

---

## 8. 보너스 과제 2: 시계열 심화 베이스라인 단기 예측 (Holt-Winters) 및 가정/한계 분석

### 💬 분석가 프롬프트 (User Prompt)
> "시계열 심화 옵션으로 베이스라인 방식을 이용해 향후 6개월 짧은 구간을 예측하는 코드를 짜줘. 단순 정확도보다 '가정과 한계' 설명에 집중해서 모델 전제 조건 3가지와 구조적 한계 3가지를 명확히 분석해 줘."

### 🤖 AI 주요 응답 스니펫 (AI Response)
```python
from statsmodels.tsa.holtwinters import ExponentialSmoothing

# 최근 회복기(2022.06~현재) 기반 Holt-Winters 적합
hw_model = ExponentialSmoothing(df_recent, trend='add', seasonal='add', seasonal_periods=12).fit()
forecast_series = hw_model.forecast(6)

# 80%, 95% 신뢰구간 산출 및 시각화 (12_baseline_forecast.png)
```

### 🔍 분석가 검증 및 수정 (User Validation)
* **결과 검증:** 향후 6개월(2024.09~2025.02) 단기 예측치 도출 및 80%/95% 신뢰구간 밴드가 포함된 `12_baseline_forecast.png` 정상 생성 확인.
* **가정 및 한계 명시:**
  - **가정:** (1) 계절 주기의 반복성, (2) 거시경제 및 환율 기조의 완만한 연착륙, (3) 외교 및 출입국 제도 현상 유지
  - **한계:** (1) 블랙스완(재난/외교 쇼크) 무감지, (2) LCC 및 호텔 수용력 등 물리적 공급 상한 미반영, (3) 비선형적 가격 탄력성 왜곡
* **노트북 및 리포트 연계:** `analysis.ipynb` [Cell #33, #34] 및 `REPORT.md` [섹션 8.2]에 해당 분석과 해석을 전면 수록.
