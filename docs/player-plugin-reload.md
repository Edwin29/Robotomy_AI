# 로컬 플러그인과 코드 재로딩

## 현재 등록

- 마켓플레이스: `Robotomy Local` (`robotomy-local`)
- 설치 플러그인: `Robotomy Player` (`robotomy-player@robotomy-local`)
- 로컬 MCP 서버: `robotomy_player`, 26개 도구
- 프로젝트별 활성화 고정 없음. 설정 화면의 전역 스위치로 켜고 끈다. 직접 MCP 등록 블록은 제거했다.
- 전역에서 켜면 다른 프로젝트에도 게임 도구가 보일 수 있으며, 사용자가 이를 허용했다.
- 게임 실행 파일/세이브/로그/경험 DB는 플러그인 패키지에 포함하지 않는다.

플러그인 목록에서 로컬 소스 `Robotomy Local`을 선택해 `Robotomy Player`를 찾는다.
최초 설치가 기존 앱/채팅 목록에 아직 보이지 않으면 앱 재시작이 한 번 필요할 수 있다.
현재 실행 중인 오래된 MCP 프로세스에 새 호스트 코드를 주입하지 않는다.
게임 창은 그대로 둔다. 직접 등록과 플러그인을 동시에 활성화하지 않는다.

게임 실행은 현재 Windows가 독립적으로 소유한다. Codex/MCP를 종료해도 게임 종료나
게임 내 일시정지를 요청하지 않는다. 종료는 `close_game`, 재연결 후 확인은 `game_power_status`를
사용한다. 실행 수명 검증과 한계는 [게임 프로세스 수명](game-process-lifetime.md)을 참고한다.

## 이후 수정 반영

관찰·입력·기록 조회용 도구 구현(`live.py`, `live_control.py`, `virtual_input.py`,
`history.py`, `mcp_server.py`)은 다음 도구 호출 전에 파일 내용 해시로 변경을 검사한다.
변경이 있으면 진행 중 호출 종료와 현재 호스트의 기록 큐 저장을 기다린 뒤 새 코드 세대로 교체한다.
평상시에는 입력 대기 중에도 관찰 호출이 가능하다. 재로딩 때만 새 호출을 기다리게 한다.
수동 확인은 `reload_player_code`, 반영 버전/오류 확인은 `player_runtime_status`를 사용한다.
둘 다 게임을 재시작하거나 일시정지를 해제하지 않는다.

문법/로드 오류 시 변경된 코드를 적용하지 않고 일반 도구 호출을 차단한다.
이전 코드로 게임 입력을 조용히 계속하지 않는다. 파일을 고치거나 이전 내용으로 되돌리면 복구된다.
미해결 입력 명령이 있으면 재로딩을 보류하며 `live_action_receipt`는 기존 코드로 조회 가능하다.
문서 파일은 read_player_guide가 항상 현재 파일을 읽는다.

### 범위와 한계

- 저장 계층/DB 구조(`experience`, `store`, `mock`), 전원/창 관리, 재로딩 호스트 자체 변경:
  MCP 재연결 필요. 기록 큐와 실행 프로세스 소유권을 메모리에서 유지하기 위한 경계다.
- 도구 이름/인자/출력 스키마 변경: MCP 재연결 필요. 기존 Codex 도구 목록과의 불일치를 막는다.
- Unity DLL/게임 모드 변경: 별도 유지보수와 게임 재실행 필요. 일시정지 중 DLL을 바꾸지 않는다.
- 이 기능은 동일 호스트 연결의 코드 교체다. 여러 플레이어 호스트 간 입력 직렬화/단일 소유권을
  새로 제공하지 않는다. 실제 플레이는 한 플레이어 채팅만 사용한다.
- 첫 연결 전환 및 위 범위 밖 변경까지 무조건 앱 재시작 없이 된다고 보장하지 않는다.

## 개발자 재생성/검증

`python scripts/setup_player_plugin.py`가 `.robotomy/plugin-marketplace`에 로컬 설치용 패키지를 만든다.
`codex plugin marketplace add <생성된 경로>` 및 `codex plugin add robotomy-player@robotomy-local`로 등록한다.
플러그인에는 저장소의 `scripts/run_player_mcp.py`를 실행하는 연결만 포함한다.
따라서 설치 캐시에 복사된 낡은 구현을 실행하지 않고 원본 프로젝트의 새 코드를 로드한다.
새 PC에서는 해당 PC 경로로 패키지를 재생성해야 한다.

- `python -m unittest discover -s tests -p 'test_*.py' -q`
- `python tests/mcp_smoke.py`
- `python tests/reload_mcp_smoke.py` (임시 소스/DB, 같은 stdio 연결에서 변경·오류·복구 검증)

현재 전환 전 설정 백업은 `.robotomy/live/verification/plugin-reload/`에 있다.
전환을 되돌릴 때는 플레이어 설정에서 플러그인을 false로 바꾸고, 백업의 직접 MCP 블록을 복원하여 true로 설정한다.
전역 설정 전체를 과거 백업으로 덮어쓰지 않는다. 백업 이후 다른 설정 변경이 있을 수 있다.

근거: https://developers.openai.com/plugins/build/plugins

## 2026-10-18 도구 미노출 수정 (1.0.2)

이 PC의 Codex 0.155.1은 이전 portable 패키지를 설치/활성화로 표시했지만 MCP 서버는
발견하지 않았다. 설정 파일을 직접 읽어 Python MCP에 접속한 이전 검증은 이 결함을 놓쳤다.
`.codex-plugin/plugin.json`의 `mcpServers: "./.mcp.json"` 선언을 쓰는 Codex 호환 형식으로
변경했다. 공식 문서가 지원하는 호환 형식이며 내장 플러그인과 같은 구조다.
플레이어 프로젝트에서 disabled 직접 서버 블록을 제거하고 플러그인만 사용한다.
전역 플러그인은 계속 disabled다.

검증: 플레이어 cwd에서 `codex mcp list --json`이 enabled=true 서버를 반환하고,
새 Codex app-server의 `mcpServerStatus/list`가 전원/상태/재로딩을 포함한 26개 도구를 반환했다.
증거는 `.robotomy/live/verification/plugin-exposure/app-server-status.json`.
이 검증은 실행 중인 기존 플레이어 채팅의 도구 목록 갱신까지 확인한 것은 아니다.
기존 채팅에 도구가 여전히 없으면 클라이언트의 MCP 구성 재로딩 또는 앱 재시작이 필요하다.
관찰/입력 구현 코드만 바뀌는 이후 작업은 기존 hot reload를 계속 사용한다.

## 2026-10-18 설정 화면 스위치 사용

사용자 요청으로 Robotomy_Player/.codex/config.toml의 플러그인 enabled=true 고정을 제거했다.
전역 값을 그대로 따르며 변경 당시 전역 값은 false였다. UI에서 켜면 전역 활성화된다.
이전 절의 프로젝트 한정 활성화 설명은 당시 기록이며 현재 운영 방식은 이 절을 따른다.
게임 시작/종료/입력 및 세이브 수정은 수행하지 않았다.
