# 2026-10-17 기초 세팅 인계

## 구현

- Python 3.11 + MCP SDK 1.30.0, 로컬 stdio 도구 10개
- SQLite 원장, 결정과 결과 분리, 사람 질문/전략 개입 및 답변
- 모의 명령의 중복 방지·revision 검사·행동 예산·운영자 정지
- Obsidian Markdown checkpoint, JSON 경험 번들, 해시 검사, 명시적 기억 상속
- 개발 레포와 같은 위치의 Vault; 실행 원장/전체 세션/내보내기는 Git 제외
- 프로젝트 전용 `.codex/config.toml` 생성 스크립트

## 검증 범위

단위·통합 테스트는 합성 환경에서의 기록 일관성과 경험 파일 이전을 검증한다.
MCP 클라이언트 subprocess로 실제 initialize → list_tools → 관찰 → 판단 → 실행 → checkpoint 왕복을 검증한다.
이 검증에는 LLM 추론이나 실제 로보토미 플레이가 포함되지 않는다.

## 남은 일

1. 새 프로젝트를 Codex에서 열고 신뢰한 후 `robotomy` MCP 도구 로딩 확인
2. 원하면 모의 환경에서 실제 LLM 호출로 짧은 판단/대화 검증
3. `live-adapter.md`의 읽기 전용 게임 연결 작업
4. 테스트 세이브에서 단일 실제 명령 검증 후 플레이 범위 확대

## 의도적으로 아직 없는 것

게임 연결 모드, 게임 조작, 세이브 수정/복구, 실행 중 자동 모델 깨우기,
API 기반 장기 자율 루프, API 비용 제한, 의미 검색, 실제 게임 클리어 검증.

현재 일반 `codex mcp get robotomy`에서 프로젝트가 미신뢰 상태이면 서버가 보이지 않을 수 있다.
전역 설정이나 사용자 신뢰 목록을 자동 변경하지 않는다. 설정 파일 생성과 호스트 도구 노출은 다른 단계다.

## 간단한 사용자 시작 순서

1. `D:\Projects\Robotomy_AI`를 Codex 프로젝트로 연다.
2. `vault`를 Obsidian Vault로 연다.
3. `prompts/player-mock.md`를 새 플레이어 채팅의 첫 지시문으로 사용한다.
4. 터미널 `python -m robotomy watch SESSION_ID --follow`로 기록을 관찰한다(프로젝트 venv 사용).
5. 실제 로보토미 플레이는 live 연결을 검증한 뒤 시작한다.
