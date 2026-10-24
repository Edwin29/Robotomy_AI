# Codex 압축 전 게임 정지

공식 계약: https://learn.chatgpt.com/docs/hooks

`PreCompact`는 manual/auto 압축 전에 동기 실행한다. JSON `continue:false`는
압축 중단을 요청한다. `PostCompact`는 알림만 반환하며 게임 입력을 보내지 않는다.

설치 위치: `D:\Projects\Robotomy_Player\.codex\hooks.json`.
배포 원본: `config/player/hooks.json`, 실행 파일: `scripts/compaction_hook.py`.
다른 작업 폴더에서는 작동하지 않는다. 신규/변경 훅은 Codex에서 사용자가
검토하고 신뢰해야 실행된다. CLI에서는 `/hooks`로 확인할 수 있다.
기존 앱 세션의 설정 갱신과 신뢰 상태는 실제 훅 목록에서 확인해야 한다.
신뢰 설정 파일을 직접 변조하거나 신뢰 검사를 우회하지 않는다.

게임 DLL 재시작이나 MCP 카탈로그 변경은 필요하지 않다.
기존 pause_only 입력은 실행 순간에 PLAYING일 때만 게임의 정상 Space 처리로
전달되며 이미 정지한 게임을 재개하지 않는다. 게임의 정지 금지는 우회하지 않는다.
진행 중 예약에는 pause-pending/pause-generation 및 입력 만료 기준을 적용한다.
새로운 자동 전략이나 기존 1회 정지 예약 슬롯을 생성하지 않는다.
압축 후 플레이어가 최신 상태, 미완료 입력, 예약을 확인하고 재개한다.

미확인 상태는 continue:false로 보고하지만, Codex 훅 자체의 오류·시간초과·
미신뢰 상태는 실행을 막지 못할 수 있다. OS 강제 정지나 숨은 상태 수정은 하지 않는다.
`.robotomy/live/compaction-last.json`은 운영 진단이며 플레이어 경험 원장이 아니다.

검증 (2026-10-20): 분기/실패/다른 폴더/자동 재개 없음 테스트 3개 통과.
본 게임 타이틀에서 stdin 훅 실행 통과, 입력 없음.
기존 pause_only 경로는 이전 v2 실기 검증을 재사용한다.
이번 훅을 신뢰한 Codex의 실제 압축 이벤트 및 운영 중 게임 정지는 아직 미검증이다.
활성화 후 게임이 이미 일시정지한 상태에서 수동 압축으로 최초 검증한다.
