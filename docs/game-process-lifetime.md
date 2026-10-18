# Codex와 게임의 실행 수명 분리

## 2026-10-18 진단

- 확인 시작 시 게임 프로세스는 없었다. 마지막 관찰은 PID 22880, Tutorial_1,
  05:24:58 UTC였다. 오래된 latest.json은 프로세스 생존 증거가 아니다.
- Windows Application 로그에 14:27:39 KST Codex 패키지의 ChatGPT.exe 응답 없음/종료,
  14:27:41 Windows Error Reporting 기록이 있었다. 해당 조회 구간에 게임 충돌 기록은 없었다.
- 기존 경로는 Codex → MCP → Python launcher → game이었다.
  CREATE_NEW_PROCESS_GROUP은 Windows Job 종료로부터의 독립을 보장하지 않는다.
  이 PC의 시험에서는 CREATE_BREAKAWAY_FROM_JOB까지 넣어도 자식이 Job에 속했다.
- 과거 게임의 정확한 종료 원인은 기록 부족으로 확정하지 않는다. Codex 종료와 연결된
  프로세스 수명 문제가 유력하며, 확인된 구조적 결함은 게임 소유권이 클라이언트에 종속된 것이다.

## 수정된 실행 경로

`start_game` / `Launch-Live.cmd` → `scripts/launch_live.py`의 원본 검사 →
`scripts/start_game_task.ps1` → Windows Task Scheduler → 독립 Python worker →
원본·복사본 해시 재검사 → 보호된 게임 복사본 + 창 비율 보조 프로세스.

작업 이름은 프로젝트 절대 경로 해시로 정하며 이 PC에서는
`RobotomyAI-Game-41982F5C937C`이다. 현재 로그인 사용자/최소 권한으로 실행하며 비밀번호,
관리자 권한, 로그인·시간 트리거, 반복 실행, 실패 시 자동 재시작을 설정하지 않는다.
실행 시간 제한은 없고 배터리 전환 때문에 종료하지 않는다. 게임 창은 기존처럼 표시된다.
동일 작업의 중복 요청은 무시하고 이미 실행 중인 작업의 소유자와 실행 경로를 검증한다.

독립 worker는 게임이 종료될 때까지 기다린다. MCP 종료나 호출 측 시간 초과로 게임을
종료하지 않는다. 게임 준비 단계에서 무결성/저장 경로/연결 검증이 실패하면 기존과 같이
그 worker가 새로 실행한 게임만 정리한다. 분리 실행 등록 실패 시 종속 실행으로 우회하지 않는다.

`close_game`의 명시적 정상 종료는 그대로다. Codex 종료는 게임의 일시정지가 아니므로
자리를 비울 때 게임을 멈추려면 먼저 게임 안에서 일시정지해야 한다.
Windows 로그아웃/PC 종료/게임 자체 충돌까지 진행 상태를 보존하는 기능은 아니다.

`launch-state.json`: 시작/준비/종료/실패, worker PID, game PID, 종료 코드.
`independent-startup.log`: 분리된 실행기의 검증·오류 로그.
`process.json`: 준비 완료한 게임의 Windows 소유권과 PID.
모두 `.robotomy/live/` 아래이며 Git에 넣지 않는다.

## 검증 결과

- 전체 단위 회귀 테스트 124개, MCP 35개 도구 왕복, 동일 연결 코드 재로딩 시험 통과.
- `tests/independent_launch_smoke.py`: 임시 프로그램/임시 작업만 사용. 실행 요청자의
  Windows Job 전체를 강제 종료한 뒤 독립 worker 및 자식 heartbeat 계속 갱신. 중복 요청 무시 확인.
- `tests/game_disconnect_smoke.py`: 실행 중인 복사본에 시험 MCP를 연결해 전원 상태만
  읽고 시험 MCP 프로세스 묶음을 강제 종료. 같은 게임 PID 37320 유지,
  화면 sequence 1255→1259 및 창 비율 보조 heartbeat 갱신 확인. 게임 입력/경험 관찰 기록 없음.
- 실제 Codex 앱 자체의 추가 재시작은 수행하지 않았다. 이 결과를 앱 재시작 E2E와 혼동하지 않는다.
- 현재 게임은 NewTitleScene에 다시 실행됐다. 이미 종료된 튜토리얼의 메모리 상태 복원은 하지 않았다.
- 원본 세이브 29개, 원본 설정 및 메타데이터 무변경 확인. 별도 프로필도 실행 전에
  `.robotomy/backups/before-independent-launch-20261018T053520Z`에 백업했다.
- 증거: `.robotomy/live/verification/independent-launch/`, `integrity-latest.json`.

실행 스크립트는 매 시작 시 디스크에서 읽으므로 이번 수정에 MCP 재설치/재연결은 필요 없다.
게임을 정상 종료한 뒤 등록 해제하려면 작업 스케줄러에서 위 이름의 작업만 삭제한다.
실행 중인 작업을 중지/삭제하는 것을 게임 종료 수단으로 사용하지 않는다.

Windows 동작 근거:
[Job Objects](https://learn.microsoft.com/en-us/windows/win32/procthread/job-objects),
[Interactive token](https://learn.microsoft.com/en-us/windows/win32/taskschd/principal-logontype),
[ExecutionTimeLimit](https://learn.microsoft.com/en-us/windows/win32/taskschd/tasksettings-executiontimelimit).
