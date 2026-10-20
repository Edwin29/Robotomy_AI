# 검증 누적 패치 본 플레이용 적용

2026-10-19, 사용자 승인에 따라 reading-20261019 누적 패치 18개 파일을 적용했다.
직원 행 HP/SP·작업 정보, 본편 이동 벡터, 배속 표시·대상 검증 예약 입력,
시련/폭주 표시, 환상체 기록 본문 및 E.G.O 목록을 포함한다.

## 적용과 검증

- 적용 전 모든 파일의 before_sha256/patch_sha256을 확인했다.
- 본 게임과 검증용 게임을 정상 창 닫기로 종료한 후 본 플레이용 DLL을 빌드했다.
- 공식 독립 실행 런처로 본 게임을 재실행했다. 새 프로세스 PID 23460에서 live 관찰 확인.
- 적용된 소스에서 192개 검사 통과, MCP smoke 통과.
- 새 player MCP 연결에서 ready, live와 새 지침 항목 반환을 확인했다.
- `config/player/AGENTS.md`와 `D:/Projects/Robotomy_Player/AGENTS.md`를 동기화했다.
  추가로 이동 벡터·일시정지/배속 항목의 활용법을 명시했다.

## 보존과 복구

백업: `D:/Projects/Robotomy_AI/.robotomy/backups/production-patch-20261019T085619Z`.
여기에 적용 전 소스, DLL, isolation.json, 플레이어 지침, 원본 및 AI 플레이 세이브를 보존했다.
종료 시 추가된 Unity/Analytics 파일은 저장 진도가 아니다. 게임 저장 파일은 별도로 해시 대조한다.
복구가 필요하면 게임 종료 후 이 백업의 source/DLL/isolation.json을 함께 복원한다.
세이브를 덮어쓰거나 되돌리지 않는다. 설치된 원본 게임은 변경하지 않았다.

## 기존 플레이어 연결에서 필요한 조치

input_sequence는 실행 중 예약과 잠금을 소유하는 상주 모듈이므로 기존 MCP 호스트는
`Resident component changed; MCP reconnection required.`로 차단된다.
이번 배포는 단순 reload_player_code 호출로 해결할 수 없다.
Robotomy Player 연결을 완전히 다시 연 다음 `player_runtime_status`, `read_player_guide`,
`live_status` 순서로 확인한다. 새 연결 검증은 성공했지만 기존 에이전트 연결의 재생성은 별개다.
게임을 다시 재시작할 필요는 없다.
