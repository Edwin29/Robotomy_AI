# 방별 상태·환상체 관리창 표시 확장

상태: 2026-10-19 본 플레이 적용 및 검증 완료.
본 플레이 PID 23460은 종료/조작하지 않았다. 게임 측 DLL은 적용 대기다.
스테이지: `.robotomy/patches/room-display-20261019/RobotomyObserver.dll` 및 `manifest.json`.
원래 소스 백업: `.robotomy/backups/room-display-source-20261019/`.

## 제공 항목

`console.hazards.room_status`:
- 현재 표시된 클리포트 카운터(number/unknown/not_applicable)
- 작업 중 표시된 PE/NE 막대 개수와 합계
- 저장된 고유 PE 박스 표시
- 작업 성공률 감소 표시 원문. 특정 원인으로 단정하지 않는다.

`console.hazards.creature_management`:
- 현재 고유 PE 잔고, 보이는 해제 비용
- 제조 버튼의 현재 표시: 보통 보유/한도, hover 시 PE 비용
- 작업 중 공격 유형·범위
- 좋음/보통/나쁨 PE 구간(피해량 아님)
- E.G.O 무기 등급·피해 유형/범위·속도·거리, 슈트 내성 유형/배율/표현
- 보이는 관리법 본문(작업 결과에 따른 특수 효과 포함)

기존 hazard diff에 함께 포함된다. 빈 값은 미표시이며 0으로 대체하지 않는다.
좌표는 표시 위치다. 클릭 가능 대상 ID와 같지 않다.

## 게임 구조 근거

로컬 ILSpy 산출물의 IsolateRoom, WorkProgress, CreatureInfoWindow,
CreatureInfoStatRoot, CreatureInfoStatFeelingStateSlot, EquipSlot/WeaponSlot/ArmorSlot,
CreatureInfoOpenArea를 실제 런타임 참조 및 화면과 대조했다.
게임 모델의 숨은 수치, private 작업 성공/실패 인덱스, E.G.O의 내부 Cost는 읽지 않는다.
도구형 환상체 사용 횟수·시간도 읽지 않는다.

작업 결과 색상은 게임의 기본 팔레트 alpha 200/255다. 기존 0.99 임계값이
실제 보이는 글자를 제외했던 문제를 해당 위젯에만 수정했다.
고유 PE 숫자의 Count/Cube/Textures/CurrentCube 구조는 자체 그림과 숫자가
하나의 표시이므로 CurrentCube 내부 장식만 가림 판정에서 제외한다.
외부 패널, 마스크, 화면 경계, 해금·효과 판정은 유지한다.

## 실행 검증

Lab `.robotomy/verification/rooms-final-details.{json,png}`:
고유 PE 41, 작업 WHITE 1–2, 좋음 8–10/보통 4–7/나쁨 0–3,
참회 WHITE 5–7, RED 0.9/WHITE 0.8/BLACK 0.9/PALE 2.0과 화면 일치.
`rooms-final-cost`: 무기 제조 hover 시 PE-Box 15.
`rooms-final-locked`: 미개방 T-02-99의 비용만 표시, details 빈 목록.
`rooms-final-closed`: 관리창 null.
`rooms-work-bars`: 자연 발생 작업 PE 2, NE 2, 합계 4, 저장 PE 41.

Lab 전용 `room-probe`는 실제 UI 위젯을 잠시 변경하고 원복하는 공학 fixture다.
숫자 2/페널티 -12% 판독, 숫자 숨김 후 unknown/null, 전체 가림 후 빈 목록,
원복 후 페널티 제거를 확인했다. 자연 발생 WAW 연속 작업이나 보스전을 검증한 것은 아니다.
이 fixture는 본 배포 소스/DLL과 플레이어 경험 기록에 포함하지 않았다.

202개 회귀 테스트 통과, MCP smoke 42개 도구 통과.
Lab 본편 일시정지 관찰 100개 표본: 전체 UI 수집 중앙값 6.08ms/P95 12.13ms,
publish 중앙값 7.32ms/P95 9.25ms. 패치 단독 비용이나 전후 개선율 측정은 아니다.

## 본 게임 적용

본 게임을 정상 종료할 수 있는 시점에 기존 DLL·manifest와 세이브 해시를 보존하고
`scripts/prepare_live.py --finish-build`, `scripts/launch_live.py`로 적용한다.
현재는 실행 중 DLL을 교체하거나 게임을 재시작하지 않았다.
Lab 게임도 종료돼 있어야 본 프로젝트의 빌드/실행 안전 검사를 통과한다.
적용 후 해당 관리창에서 빠른 관찰과 화면을 다시 대조한다.


### 적용 완료 (2026-10-19 18:34 KST)

사용자 승인 후 정상 종료·재빌드·독립 실행 완료(PID 40820). DAY 8 준비 화면으로 복귀했다.
관리 시작·작업·구매 없이 관리창만 열어 저장 PE 21, 작업 WHITE 1–2, 무기 WHITE 5–7,
네 가지 슈트 내성과 결과 PE 구간을 실제 화면 및 빠른 관찰과 대조한 뒤 닫았다.
원본·AI 세이브 모두 적용 전후 파일 집합과 SHA-256이 동일하다.
백업과 실행 증거는 패치 폴더의 deployment-backup.txt / production-verification.json /
production-management.json / production-management.png에 있다.
앞선 적용 대기 설명은 이 완료 기록으로 대체한다.
