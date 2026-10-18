# 관찰 변경 요약과 compact 모드

`observe_live(max_items=100, motion_only=false, compact=false)`의 응답 첫 필드는
`change_summary`다. 기본 호출은 기존 snapshot도 유지한다. `compact=true`는 유효한
비교 기준이 있을 때 snapshot을 생략하고 변경된 섹션의 현재 값만 반환한다.
최초 호출이나 맥락 변화는 `payload_mode=full`, `mode=reset`으로 전체 기준을 준다.

비교 기준은 이 LiveReader/MCP 연결이 직전에 반환한 observe_live 관찰이다. 게임기가
그 사이 수집한 모든 프레임을 비교하지 않으며 status/frame/control 조회는 기준을 옮기지 않는다.
MCP 재연결/코드 재로딩, stale/invalid, 프로세스·장면·해상도·생산 세션 변경,
max_items/motion_only 변경, 생산 시퀀스 역행 후에는 전체 기준을 다시 제공한다.
동시 observe_live 호출은 잠금으로 직렬화한다. 수신 순서/기준이 불분명하면 compact=false를 사용한다.
서버 반환은 사용자가 읽고 이해했다는 증명이 아니며 클라이언트 전송 유실은 감지하지 못한다.

## 적용

- base_observation_id가 가진 기준과 같은지 확인한다.
- replacements의 JSON 경로는 해당 섹션 전체 교체다. 목록은 인덱스별 병합하지 않는다.
- removed_sections는 제거한다. 제거된 이전 값/위치/이름은 응답에 재출력하지 않는다.
- 새 observation_id를 다음 기준으로 삼는다. 영상·움직임의 유효시간 제한은 그대로다.
- no_structured_changes는 선택된 구조화 필드의 차이가 없다는 뜻뿐이다.
- truncated는 관찰 범위 제한이다. 숨겨짐·범위 밖·선택 제한을 사망이나 파괴로 추론하지 않는다.
- captured_at_utc/sequence/unity_frame 같은 표본 메타데이터만 바뀌는 경우는 변경으로 세지 않는다.
  응답 최상위에는 현재 캡처 시각과 sequence가 계속 제공된다.

역할·정보 경계는 기존 공개 정보 필터 이후에 적용된다. 내부 게임 상태를 새로 읽거나
이전 비가시 정보를 보충하지 않는다. 텍스트/버튼/게이지/오디오/벡터는 섹션 단위로 비교한다.
하나의 벡터가 바뀌면 현재 벡터 섹션 전체가 반환된다. 초단위 화면 인식을 대체하지 않는다.

## 기록과 비용

observations.jsonl과 경험 원장에는 실제 반환한 diff, 기준 ID, 모드를 기록한다.
compact 응답에서 생략한 snapshot을 기록에 몰래 포함하지 않는다. 전체 기준과 그 뒤
섹션 교체를 따라가면 당시 제공된 구조화 상태를 재구성할 수 있다. 큐 실패/원본 누락 시
재구성을 보장하지 않는다. 기준은 연결당 하나만 메모리에 보관하며 별도 상주 프로세스는 없다.

정지 화면의 동일 관찰 10회 읽기 실측: full 24,033 bytes, compact 중앙값1,196 bytes,
호출 처리 중앙값1.33ms/최대1.59ms. 실제 생산 데이터에 임시 기록 폴더를 사용해 플레이
경험에 검증 사건을 섞지 않았다. 동일한 생산 프레임의 반복 조회 측정이며 전투 상황의
절감률이나 LLM 응답 속도를 보장하지 않는다. 추가 모델 호출/게임 입력 없음.
검증 자료: .robotomy/live/verification/observation-diff/measurement.json.

새 compact 인자로 MCP 스키마가 변경되므로 기존 연결은 한 번 재연결해야 한다.
게임 재시작은 필요 없다. UI 우상단에 이미지를 합성하지 않으며 MCP 텍스트 응답 상단에 표시한다.
