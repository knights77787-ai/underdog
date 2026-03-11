# 오늘 작업해야 할 것

> 작성일: 2026-03-12  
> 기준: REMAINING_TASKS_GUIDE + 코드베이스 실제 상태

---

## ✅ 완료된 것 (참고)

- POST/GET /custom-sounds (new_sound)
- 로그인 (게스트, 구글, 카카오)
- 라이브: WS, caption/alert, 피드백, 설정, 마이크
- `/new-sound` 라우트 추가 (main.py)

---

## 1. GET /logs (라이브 페이지)

**목표:** 과거 로그를 API로 불러와 테이블에 채우고, "더 불러오기" 버튼으로 이어서 조회.

### 해야 할 것

- [ ] `live.js` 상단에 상태 변수 추가: `logsNextUntilTs`, `logsHasMore`, `logsLoading`, `LOGS_LIMIT`
- [ ] `fetchLogs(append)` 함수 구현 (GET /logs 호출)
- [ ] `appendLogRowFromApi(item)` 함수 구현 (API 항목 → 테이블 행)
- [ ] Connect 성공 직후 `fetchLogs(false)` 호출
- [ ] `index.html` 로그 카드 footer에 "과거 로그 더 불러오기" 버튼 추가 (`#btnLoadMoreLogs`)
- [ ] 버튼 클릭 시 `fetchLogs(true)` 호출, `logsHasMore === false`이면 버튼 비활성화/숨김

**참고:** `Shared/api_contract.md` – GET /logs (type, limit, session_id, until_ts_ms)

---

## 2. 관리자 페이지 (admin.html + admin.js)

**목표:** `/admin`에서 summary, health, 데모 emit, reload 버튼 연동.

### 해야 할 것

- [ ] `main.py`에 `GET /admin` 라우트 추가 → `admin.html` 서빙
- [ ] `admin.html` 골격 작성 (Bootstrap, 영역 구분)
- [ ] `admin.js` 작성:
  - GET /admin/summary → total_captions, total_alerts 등 표시
  - GET /admin/health → db_ok, tasks 등 표시
  - "데모 알림 1건 발생" 버튼 → POST /admin/demo/emit
  - "키워드 룰 리로드" 버튼 → POST /admin/reload-keywords
  - "오디오 룰 리로드" 버튼 → POST /admin/reload-audio-rules

**참고:** 백엔드 API는 이미 존재. `DEV=1`이면 admin 토큰 없이 호출 가능.

---

## 3. (선택) 관리자 추가 기능

- [ ] GET /admin/alerts – 알림 목록 테이블, 무한 스크롤
- [ ] GET /admin/feedback-summary, GET /admin/feedback-suspects – 피드백 집계 표시

---

## 4. (나중에) 커스텀 구문 오디오

- [ ] POST/GET /custom-phrase-audio 연동
- [ ] new_sound에 탭 추가 또는 별도 페이지

---

## 체크리스트 요약

| 항목 | 우선순위 | 완료 |
|------|----------|------|
| GET /logs (첫 로딩 + 더 불러오기) | 1 | [ ] |
| 관리자: /admin 라우트 + admin.html/js | 1 | [ ] |
| 관리자: summary, health, demo, reload | 1 | [ ] |
| 관리자: alerts 목록 | 2 (선택) | [ ] |
| 관리자: feedback-summary, feedback-suspects | 2 (선택) | [ ] |
| 커스텀 구문 오디오 | 3 (나중에) | [ ] |
