# pythonStock - Stock Chart Web

Streamlit 기반 주식 분석 웹앱입니다.
- 미국/한국 주식 조회
- 회사명/티커 검색 + 자동완성 후보
- 캔들차트, SMA20/60, RSI
- RSI 기반 매수/매도 신호 + 간단 백테스트
- 모바일 최적화 모드

## 1) 로컬 실행

```powershell
cd C:\Users\ad\Documents\GitHub\pythonStock\pythonStock
.\.venv\Scripts\Activate.ps1
pip install -r requirements.txt
streamlit run app.py
```

## 2) Streamlit Community Cloud 배포

1. 이 폴더를 GitHub 리포지토리에 push
2. https://share.streamlit.io 접속
3. `New app` 선택
4. Repository/Branch/Main file 지정
   - Main file path: `app.py`
5. Deploy 클릭

배포 후 생성된 `https://...streamlit.app` 링크를 공유하면
휴대폰 포함 누구나 접속할 수 있습니다.

## 3) 휴대폰 테스트(같은 와이파이에서 로컬)

```powershell
streamlit run app.py --server.address 0.0.0.0 --server.port 8501
```

PC의 로컬 IP(예: `192.168.0.10`)를 확인한 뒤,
휴대폰 브라우저에서 `http://192.168.0.10:8501` 접속.

## 4) 주의사항

- API 키를 쓰게 되면 코드에 직접 넣지 말고 `secrets.toml`/환경변수를 사용
- Streamlit 무료 플랜은 장시간 미접속 시 슬립될 수 있음
