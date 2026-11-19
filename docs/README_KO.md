<div align="center">

# AI 주식 분석 시스템

[![Upstream stars](https://img.shields.io/github/stars/ZhuLinsen/daily_stock_analysis?style=social&label=Upstream%20stars)](https://github.com/ZhuLinsen/daily_stock_analysis/stargazers)
[![arXiv](https://img.shields.io/badge/arXiv-2608.26990-b31b1b.svg)](https://arxiv.org/abs/2608.26990)
[![License: MIT](https://img.shields.io/badge/License-MIT-yellow.svg)](https://opensource.org/licenses/MIT)
[![Python 3.10+](https://img.shields.io/badge/python-3.10+-blue.svg)](https://www.python.org/downloads/)
[![GitHub Actions](https://img.shields.io/badge/GitHub%20Actions-Ready-2088FF?logo=github-actions&logoColor=white)](https://github.com/features/actions)

**중국 A주 / 홍콩 / 미국 / 일본 / 한국 / 대만 주식을 위한 AI 기반 주식 분석 시스템**

관심종목을 매일 분석 -> 의사결정 대시보드 생성 -> Telegram / Discord / Slack / 이메일 / WeChat Work / Feishu로 전송합니다.

[**이 Fork의 변경 사항**](#-이-fork의-변경-사항) · [**화면 미리보기**](#-화면-미리보기) · [**주요 기능**](#-주요-기능) · [**빠른 시작**](#-빠른-시작) · [**문서 색인 (영문)**](INDEX_EN.md) · [**전체 가이드 (영문)**](full-guide_EN.md)

[English](../README.md) | 한국어 | [简体中文](README_CHS.md) | [繁體中文](README_CHT.md)

</div>

> 이 저장소는 [ZhuLinsen/daily_stock_analysis](https://github.com/ZhuLinsen/daily_stock_analysis)의 fork로, 한국어 UI와 몇 가지 사용성 개선을 추가했습니다. 공식 프로젝트가 아니므로 원본 릴리스와 지원은 원본 저장소를 참고하세요.

## 🆕 이 Fork의 변경 사항

| 영역 | 변경 내용 |
|------|-----------|
| 한국어 UI | 웹 UI, 백엔드 메시지, Agent 채팅, 시장 리뷰 리포트를 한국어로 제공 (중국어 / 영어 / 한국어 전환) |
| 시장 대시보드 | 홈 화면에 시장별 시계와 장 시작·마감 카운트다운, 주요 지수, 환율, 프리마켓/애프터마켓 가격이 포함된 관심 종목 표시. 분석은 별도 탭으로 이동 |
| 공시 | 선택 기능(`DISCLOSURE_ENABLED`). 최근 공식 공시(OpenDART, SEC EDGAR, cninfo)를 요약해 분석에 반영하고, 공시 예정일(KIND, JPX, 동방재부, HKEXnews, Yahoo)을 리포트에 표시 |
| 한국·일본 종목 | 자동완성에 KOSPI/KOSDAQ와 도쿄증권거래소 전체 상장 종목을 현지 공식 이름으로 수록하고, 영어 UI에서는 공식 영문명 표시 |
| 호가단위 | 한국·일본 종목의 매수·손절·목표가를 원·엔 정수와 거래소 호가단위에 맞춰 제시 |
| 작업 제어 | 대기 중인 작업은 즉시, 실행 중인 종목 분석은 다음 체크포인트에서 취소 |
| 호출 제한 알림 | LLM, 시세 데이터, 뉴스 공급자가 최근 rate limit이나 할당량에 걸리거나 공시 소스 수집이 실패하면 앱 전체에 배지로 표시 |
| Agent 채팅 | 분석 대상 종목을 직접 지정하고, 선택한 전략마다 별도 전문가로 실행 |
| 데이터 센터 | 설정되지 않은 공급자를 화면에서 바로 설정하고, 공급자별 마지막 성공 호출 시각 표시 |
| 시장 리뷰 | 리뷰한 시장마다 기록 행을 따로 두고, 홈 화면에 서버 기본 시장을 표시. 미국·홍콩·일본·한국·대만 업종 등락 순위를 추가하고 업종명을 리포트 언어로 표시 |
| 토큰 사용량 | 최근 LLM 호출을 대화 단위로 묶어 보고, 같은 모델의 사용량이 호출 경로에 따라 나뉘지 않음 |
| 설정 | 모든 분류에 걸쳐 이름, 키, 설명으로 설정 검색 |
| 안전한 기본값 | 데스크톱 자동 업데이트와 종목 인덱스 원격 갱신을 기본으로 꺼서 업스트림 저장소에서 아무것도 자동으로 받지 않음 |
| 개발 환경 | 백엔드 자동 재시작과 Vite HMR을 지원하는 `docker/docker-compose.dev.yml` |

## 🖥️ 화면 미리보기

<p align="center">
  <a href="assets/readme_workspace_tour_20260510.gif"><img src="assets/readme_workspace_preview.gif" alt="DSA 웹 작업공간 데모" width="640"></a><br>
  <sub>GIF를 클릭하면 전체 데모를 볼 수 있습니다</sub>
</p>

## ✨ 주요 기능

| 기능 | 내용 |
|------|------|
| AI 의사결정 리포트 | 핵심 결론, 점수, 추세, 매수/매도 가격대, 위험 경보, 호재, 실행 체크리스트 |
| 다중 시장 데이터 | 중국 A주, 홍콩, 미국, 일본, 한국, 대만 주식과 ETF의 시세, K선, 기술 지표, 뉴스, 공시, 펀더멘털, 리포트 컨텍스트. 데이터 소스 범위와 시장별 한계는 [시장 지원 범위](market-support.md) 참고 |
| 웹 / 데스크톱 작업공간 | 수동 분석, 작업 진행 상황, 기록, 전체 Markdown 리포트, 백테스트, 포트폴리오, 설정, 라이트/다크 테마 |
| Agent 전략 채팅 | 웹/봇/API에서 15가지 내장 전략으로 여러 차례 질의응답 |
| 스마트 가져오기 & 자동완성 | 이미지, CSV/Excel, 클립보드 가져오기; 종목 코드/이름/병음/별칭 자동완성 |
| 자동화 & 알림 | GitHub Actions, Docker, 로컬 스케줄러, FastAPI 서비스, WeChat Work / Feishu / Telegram / Discord / Slack / 이메일 전송 |

> 상세 필드, 펀더멘털 P0 타임아웃 규칙, 매매 원칙, 데이터 소스 우선순위, 웹/API 동작, 문제 해결은 [전체 가이드 (영문)](full-guide_EN.md)에 있습니다.

### 기술 스택 & 데이터 소스

| 유형 | 지원 |
|------|------|
| AI 모델 | Modelflare, x6.ai, AIHubMix, Gemini, OpenAI 호환 공급자, DeepSeek, Qwen, Claude, Ollama |
| 시세 데이터 | TickPlus, AkShare, Tushare, Pytdx, Baostock, YFinance, Longbridge, Finnhub, Alpha Vantage |
| 뉴스 검색 | SerpAPI, Anspire, Tavily, Bocha, Brave, MiniMax, SearXNG |
| 소셜 심리 | Reddit / X / Polymarket 기반 Stock Sentiment API (미국 주식만) |

> AkShare, Baostock, YFinance 같은 무료 시세 소스가 기본 포함되어 있어 추가 인증 정보 없이도 실행됩니다. 다만 무료 소스는 호출 제한, 상위 API 변경, 네트워크 상태에 따라 불안정할 수 있습니다. 정기 실행, 대량 분석, 안정적인 시세가 필요하면 Tushare나 Longbridge 같은 토큰 기반 소스를 설정하세요. 시장별 범위, Actions 매핑, 대체 규칙은 [데이터 소스 설정 (영문)](full-guide_EN.md#data-source-configuration)에 있습니다.

## 🚀 빠른 시작

### 방법 1: GitHub Actions (권장)

> 서버나 인프라 비용 없이 약 5분 만에 배포할 수 있습니다.

#### 1. 이 저장소 Fork

오른쪽 위의 `Fork`를 클릭합니다.

#### 2. Secrets 설정

Fork한 저장소에서 `Settings` -> `Secrets and variables` -> `Actions` -> `New repository secret`으로 이동합니다.

**AI 모델 설정 (최소 1개)**

공급자 하나와 API 키 하나로 시작하세요. 다중 모델 라우팅, 이미지 인식, 로컬 모델, 고급 라우팅은 [LLM 설정 가이드 (영문)](LLM_CONFIG_GUIDE_EN.md)를 참고하세요.

| Secret 이름 | 설명 | 필수 |
|-------------|------|:----:|
| `GEMINI_API_KEY` | Google Gemini API 키 | 선택 |
| `ANTHROPIC_API_KEY` | Anthropic Claude API 키 | 선택 |
| `OPENAI_API_KEY` | OpenAI 호환 API 키 (DeepSeek, Qwen 호환 서비스 포함) | 선택 |
| `OPENAI_BASE_URL` / `OPENAI_MODEL` | OpenAI 호환 공급자를 쓸 때 입력 | 선택 |
| `MODELFLARE_KEY` | Modelflare API 키 | 선택 |
| `LLM_X6AI_API_KEY` | x6.ai API 키 | 선택 |
| `AIHUBMIX_KEY` | AIHubMix API 키 (하나의 키로 여러 모델 계열 사용) | 선택 |

> Ollama는 로컬이나 Docker 배포에 더 적합합니다. GitHub Actions에서는 클라우드 API가 보통 더 원활합니다.

**알림 채널 (최소 1개)**

| Secret 이름 | 설명 |
|-------------|------|
| `WECHAT_WEBHOOK_URL` | WeChat Work 봇 |
| `FEISHU_WEBHOOK_URL` | Feishu 봇 |
| `TELEGRAM_BOT_TOKEN` + `TELEGRAM_CHAT_ID` | Telegram |
| `DISCORD_WEBHOOK_URL` | Discord 웹훅 |
| `SLACK_BOT_TOKEN` + `SLACK_CHANNEL_ID` | Slack 봇 |
| `EMAIL_SENDER` + `EMAIL_PASSWORD` | 이메일 전송 |

추가 채널, 서명 검증, 이메일 그룹, Markdown 이미지 변환 설정은 [알림 설정 (영문)](full-guide_EN.md#notification-channel-configuration)에 있습니다.

**관심종목 (필수)**

| Secret 이름 | 설명 | 필수 |
|-------------|------|:----:|
| `STOCK_LIST` | 관심종목 코드. 예: `600519,hk00700,AAPL,7203.T,005930.KS,2330.TW`. 등록된 지수 코드(예: `sh000016`, `930606.CSI`)는 일회성 `--stocks` 인자나 GitHub Actions 입력으로 지원 — [지수 관심종목 설정 (영문)](full-guide_EN.md#index-watchlist-configuration) 참고 | ✅ |

**뉴스 소스 (권장)**

뉴스 검색은 심리, 공시, 이벤트, 호재 분석의 질을 크게 높입니다. 가능하면 검색 공급자를 하나 이상 설정하세요.

| Secret 이름 | 설명 | 필수 |
|-------------|------|:----:|
| `SERPAPI_API_KEYS` | SerpAPI, 실시간 금융 뉴스용 검색 엔진 결과 | 선택 |
| `ANSPIRE_API_KEYS` | Anspire 검색 API 키 (LLM 게이트웨이와 공유 가능) | 선택 |
| `TAVILY_API_KEYS` | Tavily, 범용 뉴스 검색 API | 선택 |
| `BOCHA_API_KEYS` | Bocha, AI 요약을 지원하는 중국어 검색 | 선택 |
| `BRAVE_API_KEYS` | Brave Search, 개인정보 중심 검색과 미국 주식 뉴스 보강 | 선택 |
| `MINIMAX_API_KEYS` | MiniMax, 구조화된 검색 결과 | 선택 |
| `SEARXNG_BASE_URLS` | 할당량 없는 대체용 자체 호스팅 SearXNG 인스턴스 | 선택 |

추가 검색 공급자, 소셜 심리, 대체 동작은 [검색 설정 (영문)](full-guide_EN.md#search-service-configuration)에 있습니다.

**시세 데이터 소스 (선택)**

> 기본으로 AkShare, Baostock, YFinance 같은 무료 소스를 사용합니다. 로그의 "Not configured" 메시지는 안내일 뿐 실행에 영향을 주지 않습니다.
> 더 안정적인 데이터가 필요하면 시장별로 다음 Secret을 설정하세요.

| Secret 이름 | 시장 | 설명 |
|-------------|:----:|------|
| `TICKPLUS_API_KEY` | A주 / ETF | TickPlus: 일봉, 실시간 지표, 종목명 |
| `TUSHARE_TOKEN` | A주 | 과거 데이터 안정성 향상 |
| `LONGBRIDGE_OAUTH_CLIENT_ID` + `LONGBRIDGE_OAUTH_TOKEN_CACHE_B64` | 홍콩/미국 | 거래량 비율, 회전율, PER 등 보강 |
| `FINNHUB_API_KEY` / `ALPHAVANTAGE_API_KEY` | 미국 | 추가 미국 일봉 소스 |

> [데이터 소스 설정 (영문)](full-guide_EN.md#data-source-configuration)을 참고하세요.

#### 3. Actions 활성화

`Actions` 탭에서 `I understand my workflows, go ahead and enable them`을 클릭합니다.

#### 4. 수동 테스트

`Actions` -> `Daily Stock Analysis` -> `Run workflow` -> `Run workflow`.

#### 완료

기본적으로 매 평일 베이징 시간 18:00(한국 시간 19:00)에 실행되며 휴장일은 건너뜁니다. 강제 실행, 거래일 확인, 재개 규칙은 [전체 가이드 (영문)](full-guide_EN.md#scheduled-task-configuration)에 있습니다.

### 방법 2: 로컬 / Docker 배포

```bash
# 프로젝트 복제
git clone https://github.com/mangddung/daily_stock_analysis.git && cd daily_stock_analysis

# 의존성 설치
pip install -r requirements.txt

# 환경 변수 설정
cp .env.example .env && vim .env

# 분석 실행
python main.py
```

자주 쓰는 명령:

```bash
python main.py --debug
python main.py --dry-run
python main.py --stocks 600519,hk00700,AAPL,005930.KS
python main.py --market-review
python main.py --schedule
python main.py --serve-only
```

개발용 Docker 스택은 소스를 마운트하고 변경 시 자동으로 다시 불러옵니다(백엔드 `http://127.0.0.1:15300`, 웹 `http://127.0.0.1:15301`).

```bash
docker compose -f docker/docker-compose.dev.yml up --build
```

> 운영용 Docker 배포, 스케줄링, 클라우드 서버에서 WebUI 접속은 [전체 가이드 (영문)](full-guide_EN.md)에 있습니다.

## 📱 출력 예시

### 의사결정 대시보드

```markdown
🎯 2026-02-08 의사결정 대시보드
3개 종목 분석 | 🟢 매수:0 🟡 관망:2 🔴 매도:1

📊 요약
🟡 000657: 관망 | 점수 65 | 강세
🟡 600105: 관망 | 점수 48 | 박스권
🔴 300260: 매도 | 점수 35 | 약세

🚨 위험 경보:
위험 1: 주력 자금의 뚜렷한 유출이 나타났습니다.
위험 2: 매물 집중도로 보아 단기 저항이 예상됩니다.

✨ 호재:
호재 1: AI 서버 공급망 노출이 계속 시장의 관심을 받고 있습니다.
호재 2: 최근 실적 성장이 펀더멘털을 뒷받침합니다.
```

### 시장 리뷰

```markdown
🎯 2026-01-10 시장 리뷰

📊 주요 지수
- 상하이종합지수: 3250.12 (🟢+0.85%)
- 선전성분지수: 10521.36 (🟢+1.02%)
- 창업판지수: 2156.78 (🟢+1.35%)

📈 시장 폭
상승: 3920 | 하락: 1349 | 상한가: 155 | 하한가: 3

🔥 업종 동향
강세: 인터넷 서비스, 미디어·엔터테인먼트, 희소금속
약세: 보험, 항공·공항, 태양광 장비
```

## ⚙️ 설정

전체 환경 변수, 모델 라우팅, 알림 채널, 데이터 소스 우선순위, 매매 원칙, 펀더멘털 P0 규칙, 배포 세부 사항은 [전체 가이드 (영문)](full-guide_EN.md)에 있습니다.

## 🖥️ 웹 UI

웹 작업공간에서 설정, 작업 모니터링, 수동 분석, 기록 리포트, 전체 Markdown 리포트, Agent 전략 채팅, 백테스트, 포트폴리오 관리, 스마트 가져오기, 라이트/다크 테마를 사용할 수 있습니다. 사이드바 하단의 언어 버튼으로 한국어를 선택하세요.

```bash
python main.py --webui
python main.py --webui-only
```

`http://127.0.0.1:8000`에 접속합니다. 인증, 스마트 가져오기, 자동완성, 리포트 복사, 클라우드 서버 접속은 [로컬 WebUI 관리 (영문)](full-guide_EN.md#local-webui-management-interface)에 있습니다.

## 🤖 Agent 전략 채팅

사용 가능한 AI API 키를 하나라도 설정하면 웹 `/chat` 페이지에서 전략 채팅을 쓸 수 있습니다. 명시적으로 끄려면 `AGENT_MODE=false`로 설정하세요.

- 이동평균 교차, 전론(缠论), 엘리엇 파동, 상승 추세, 테마주, 이벤트 드리븐, 성장 품질, 기대 재평가 등 내장 전략
- 실시간 시세, K선, 기술 지표, 뉴스, 위험 정보 호출
- 후속 질문, 대화 내보내기, 알림 전송, 백그라운드 실행
- 사용자 정의 전략 파일과 실험적 다중 Agent 오케스트레이션
- 종목 검색으로 분석 대상을 직접 지정 (이 fork에서 추가)

> Agent 파라미터, `skill` 이름 호환성, 다중 Agent 모드, 예산 제한은 [전체 가이드 (영문)](full-guide_EN.md#local-webui-management-interface)와 [LLM 설정 가이드 (영문)](LLM_CONFIG_GUIDE_EN.md)에 있습니다.

## 🧩 관련 프로젝트

> DSA는 일일 분석 리포트에 집중합니다. 종목 스크리닝 구현은 AlphaSift를 참고했고, AlphaEvo는 전략 검증과 진화를 다룹니다.

| 프로젝트 | 초점 |
|----------|------|
| [AlphaSift](https://github.com/ZhuLinsen/alphasift) | DSA 스크리닝 구현의 참고 프로젝트 |
| [AlphaEvo](https://github.com/ZhuLinsen/alphaevo) | 규칙 검증과 전략 파라미터·조합의 반복 탐색을 위한 백테스트 및 자기 진화 실험 |

## 📄 라이선스

[MIT License](../LICENSE) © 2026 ZhuLinsen

[ZhuLinsen/daily_stock_analysis](https://github.com/ZhuLinsen/daily_stock_analysis)를 기반으로 합니다. 이 fork의 변경 사항도 같은 라이선스를 따릅니다.

## ⚠️ 면책 조항

이 프로젝트는 정보 제공 및 학습 목적으로만 제공됩니다. AI가 생성한 분석은 투자 조언이 아닙니다. 주식 투자에는 위험이 따르므로 스스로 조사하고, 필요하면 공인 금융 전문가와 상담하세요.
