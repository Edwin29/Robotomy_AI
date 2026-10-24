# Lobotomy AI — 2026-10-24 소스 게시 안내

이 저장소는 AI가 게임을 관찰·조작하고 출처가 연결된 경험을 기록하도록 하는 독립적인 게임기 프로젝트다. 판단과 감상은 플레이어가 담당한다. 연구 목적·배경은 [프로젝트 배경](project-context-for-claude.md)을 참고하되, 그 문서의 구현 상태는 2026-10-19 기준이다.

## 이번 게시

- 표시 이름 Lobotomy AI / Lobotomy Player / Lobotomy Local. 기존 Robotomy_AI 경로, robotomy_player MCP 식별자, 저장 경로와 GitHub 주소는 유지한다.
- 간단한 대상 입력·직원 이동·스크롤과 입력 후 관찰 반환, player_adapter/perception 구조.
- 직원 HP/SP·선택, 연구·스토리·화면 정보, 전투 표시, 기프트, 격리실 문구 및 외형·모션·표식과 플레이어 별칭.
- 늙은 여인의 실제 표시된 검은 안개 지원. 검증 범위는 oldlady-fog-20261023.md 참고.
- 원본 Steam 세이브/설정의 정상 변경은 진단으로 기록하고 AI 실행 차단 사유에서 제외. 저장 경로 분리와 실행본 무결성 확인은 유지한다.
- 최신 플레이어 사용 지침은 config/player와 config/player-workspace-snapshot 참조.

세부 구현/검증: [AI용 어댑터](ai-first-adapter-implementation-20261023.md), [외형·표식](appearance-patch-20261023.md), [늙은 여인 안개](oldlady-fog-20261023.md), [실게임 저장 분리](live-adapter.md).

## 자료 경계

main은 검토한 소스·문서의 게시본이다. 최신 경험 기록은 player-experience 브랜치가 담당한다. 이번 게시에서는 vault 경험 기록을 덮어쓰거나 해당 브랜치를 병합하지 않았다.
게임 바이너리/에셋/역컴파일 전체 산출물, 세이브, 영상, 인증 정보, 로컬 DB와 .robotomy 실행 데이터는 포함하지 않는다. config/player-workspace-snapshot은 문서 사본이며 실제 플레이어 환경이 아니다.
과거 날짜의 조사 보고서와 *.pending.patch는 당시 기록이다. 최신 소스에 무조건 재적용하지 말 것. README의 모의 실행 예제 및 과거 관찰 주기/도구 범위는 최신 실게임 명세로 취급하지 말 것.

## 게시 시 검증

2026-10-24 로컬 최신 코드: unittest 306개 통과, 격리 임시 폴더에서 MCP smoke 통과. 이번 게시 작업은 게임을 실행·조작·재시작하지 않았으며 과거 실기 검증을 새로 수행했다고 주장하지 않는다.
