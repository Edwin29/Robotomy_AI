# 간단 대상 입력과 결과 관찰 — 본 플레이 적용 완료

2026-10-19. 플레이 종료 후 사용자 요청에 따라 본 플레이에 적용했다.

## 본 플레이 배포 확인

- 14개 패치 파일의 before/after 해시 대조 후 적용. private runtime의 production identity DLL과 isolation 해시 갱신.
- config/player/AGENTS.md와 D:/Projects/Robotomy_Player/AGENTS.md 동기화.
- 새 실제 player MCP 연결: 37개 도구, game_input/move_employee 노출, ready/live, 새 지침 반환 확인.
- 적용 코드에서 232개 테스트, MCP stdio smoke 46개 도구 통과.
- 기존 PID 29804를 정상 종료하고 공식 런처로 PID 38336 재실행. 9일차 준비 화면에서 종료했으며 이어하기만 실행했다.
- 원본·플레이 세이브 15개 파일의 적용 전후 SHA256 동일. 원본 설치와 저장 파일을 수정하거나 롤백하지 않았다.
- 백업: `.robotomy/backups/simple-input-20261019T135347Z`. 배포 기록: staging의 `deployment.json`, 연결 증거: `production-check.json`.
- 기존 Codex 플레이어 연결은 새 도구/상주 모듈 변경 때문에 MCP 재연결 필요. 새 연결 확인과 기존 채팅의 재연결은 별개다. 게임은 다시 종료할 필요 없다.

아래는 사전 lab 검증과 배포 절차 기록이다.

패치: `docs/simple-target-input.pending.patch`

빌드·manifest·검증 증거: `.robotomy/patches/simple-input-20261019/`

## 제공 기능

`game_input(command=["L", "containment:…"])`으로 현재 보이는 방을 클릭한다.
`["L", "work:통찰"]`, `["L", "row:현재 행 ID"]`, `["L", "2x"]`도 가능하다.
L/R/H는 좌클릭/우클릭/포인터 이동, K는 키 입력이다. 복잡한 입력과 짧은 예약은 기존 도구를 유지한다.

`move_employee(employee="아스터로이드", destination="corridor:-20.25:-30.41")`는 직원 선택 후 목적지를 우클릭한다. 게임 자체의 선택 표시를 확인한 다음 두 번째 입력을 보낸다. 도착이나 작업 성공을 자동 판정하지 않는다.

새 도구와 execute_live_action은 `current`를, click_facility와 예약 완료/취소 조회는 `after.current`를 함께 반환한다. 작업창, 직원 행, 현재 직원·엔티티, 위험 표시, 장비/기록 창과 다음 입력 대상이 들어간다. 내부 capture는 PNG를 쓰지 않는다. 화면이 필요한 이야기/새 연출은 기존 view_live_frame을 사용한다.

결과 대기는 최대 1.2초이며 새 표본 두 개에서 입력 대상이 안정되면 일찍 반환한다. ready는 관찰 준비 상태다. pending/unavailable 및 전송 불확실성을 게임 성공·실패로 바꾸지 않으며 재전송하지 않는다. current는 observe_live의 diff 기준을 갱신하지 않는 독립 관찰이다.

고정 지도는 facility_map_known, 현재 시야·상태는 facility_map으로 분리했다. compact에서 변하지 않은 고정 지도는 다시 보내지 않는다. 원시 console.audio_events 중복을 제거하고 입력 결과와 observe_live가 한 audio_delivery 커서를 공유한다. 새 MCP 연결에서는 커서가 초기화될 수 있다.

## 게임 구현 근거

AgentUnit.OnSelect/OnUnselect → AgentUI.SetSelectState의 실제 선택 색상을 확인했다. 선택된 직원의 현재 보이는 HUD Texture가 주황색인지 사용하며 내부 _selected나 숨겨진 직원 명단을 조회하지 않는다. selectedIcon은 작업/공격 상태에도 사용되므로 선택 근거로 쓰지 않았다.

직원·행·버튼·시설 클릭은 기존 표시 계층이 허용한 현재 클릭 지점만 사용한다. 이름이 중복되면 명시적인 ref가 필요하다. 시설 지도에 기억된 위치가 있어도 현재 클릭 지점이 없으면 조작하지 않는다. 새 자동 판단/반복 블록은 없다.

## 실제 lab 검증

격리된 Robotomy_LabPhysical / Lobotomy_Lab_Observer의 6일차를 공식 실행기로 열었다. 생산 게임/원본 설치/생산 세이브를 복사하거나 변경하지 않았다.

- 직원 이름 + 복도 ID 이동: 선택과 두 입력 완료. 재개 후 아스터로이드의 x가 약 703.5→658.3으로 변하고 이동 벡터 -37.42 px/s, 상태 이동 중을 확인. 화면상의 해당 직원과 대조했다.
- 방 선택 → 작업 종류 → 직원 행: 반환된 이름/HP/SP/성공률/작업 시간과 실제 표시가 일치. 직원 지정 후 작업창 닫힘도 응답에 반영.
- 실제 MCP 함수 dispatch: game_input 0.563초씩 두 번, click_facility 0.498초, execute_live_action 0.519초. 예약 제출 0.010초, 완료 조회에 current 포함.
- 가려진 다른 방 선택은 기존 시설 가시성 판정에서 입력 전 거부됐다. 선택된 작업 종류는 클릭 대상으로 제공되지 않을 수 있으므로 현재 work_types를 사용했다.
- 첫 compact 관찰 약 33.2KB, 바로 다음 변화 없는 관찰 약 1.6KB (json.dumps 기준). 이는 전체 플레이 속도 개선율이나 토큰 절감률 측정이 아니다.
- 고정 지도 재전송 억제 및 입력/관찰 사이 소리 커서 공유는 자동 회귀 테스트로 확인. 모든 보스 상황을 실행 검증한 것은 아니다.
- 232개 unittest 통과. 표준 MCP smoke 46개 도구, 재로딩 MCP smoke 37개 도구 통과. C# DLL 빌드 성공(기존 Point 필드 CS0649 경고 두 개).

내부 준비 함수 몇 개를 합쳤다는 이유로 모델 판단 시간이 같은 비율로 줄어든다고 주장하지 않는다. 주요 개선은 다음 판단에 필요한 직원 목록 등을 별도의 관찰 호출 없이 받는 것이다. 실제 플레이 소요 시간 비교는 배포 후 필요하다.

## 적용 대기

기존 생산 소스 전체 baseline 해시가 동일함을 manifest에 기록했다. 생산 PID 29804 유지, lab PID 28552만 정상 종료했다. 운영 중 바뀌는 세이브를 정적 파일처럼 취급하지 않았다.

플레이 종료 이후에만:

1. manifest의 before 해시와 현재 파일을 대조하고 다른 변경과 충돌하면 병합한다. staging 전체를 덮어쓰지 않는다.
2. pending.patch의 14개 소스/테스트/지침 파일을 적용한다. 생산 identity로 빌드한 RobotomyObserver.dll은 기존 private runtime 백업·무결성 갱신 절차로 배포한다. Lab.dll/identity/save는 배포하지 않는다.
3. 플레이어 workspace의 AGENTS를 갱신하고 MCP를 재연결한다. 새 도구 두 개와 pinned input_sequence 변경이 있어 단순 hot reload만으로 끝내지 않는다.
4. 시작 후 새 도구 목록, current 반환, compact 지도 섹션을 확인한다. 본편을 대신 진행하지 않는다.

증거 JSON/PNG는 로컬 staging에만 두며 게임 바이너리/세이브와 함께 Git에 넣지 않는다. 일반 hover 도구는 이미 결과 이미지를 제공하므로 그대로 두었다. 상태 조회나 전원 도구에는 불필요한 결과 관찰 대기를 추가하지 않았다.
