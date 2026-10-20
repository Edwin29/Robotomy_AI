# 환상체 기록 본문·E.G.O 목록 빠른 관찰 검증

2026-10-19. 검증용 Robotomy_Lab에 구현·실행했고, 실제 플레이용 게임에는 미적용이다.
누적 패치: `.robotomy/patches/reading-20261019/files.json` (18개 파일).
이전 hazards-20261019 패치의 벡터·직원 행·예약 입력·배속·시련/폭주 변경도 포함한다.
적용 전 manifest의 before_sha256을 확인해야 한다. Lab의 Observer/진단 코드는 배포하지 않는다.

## 추가된 응답

- `creature_record`: 열린 기록 화면에 현재 보이는 본문 줄을 문단별로 묶음. 줄바꿈과 `<데이터 말소>` 등의 원문을 유지한다.
- `equipment_rows`: 보이는 E.G.O 이름·등급, 무기의 피해 유형/피해/공격 속도/거리, 슈트의 네 유형별 저항 문구·배율, 표시된 장착 직원 이름과 조작 좌표.
- `equipment_controls`: 실제 클릭 핸들러가 확인된 무기/슈트 탭과 직원 선택 좌표. 장비 행 `actions`는 슬롯/세부설명 좌표.
- 기존 compact diff로 변경된 섹션만 재전송한다. 닫힌 창의 목록은 빈 배열로 교체한다. 과거 관찰을 현재 상태로 유지하지 않는다.

별도 모델 호출이나 OCR, 고정 대기 추가 없이 기존 UI 캡처 주기를 사용한다. 이미지 관찰은 그대로 사용할 수 있다.
플레이어 안내는 패치 내 `config/player/AGENTS.md`에 포함했다.

## 게임 구조 근거

기존 ILSpy 산출물 `Assembly-CSharp.decompiled.cs`의 InventoryUI/InventorySlot/InventoryWeaponSlot/InventoryArmorSlot/InventoryAgentSlot과 CreatureInfoWindow.SetDesc를 확인했다.
실행 중 실제 Text·클릭 핸들러·TextGenerator 줄 배치와 화면을 대조했다.

장비 모델이나 미개방 설명 원본을 조회하지 않는다. 게임이 이미 표시 위젯에 넣은 문자열을 읽으므로 무기 유형이 `???`이면 그대로 전달한다.
슈트 필드 배열 순서는 UIUtil.DefenseSetOnlyText/DefenseSetFactor가 사용하는 RED/WHITE/BLACK/PALE 순서를 따른다.
기록은 게임이 해금 상태에 따라 만든 descList만 대상으로 하고, TextGenerator의 줄별 화면 영역과 실제 마스크를 적용한다.
직원 초상화 내부의 머리카락·눈썹 이미지는 같은 표시 위젯의 구성 요소로 취급하여 이름을 잘못 가리지 않게 했다.
외부 UI 가림과 스크롤 경계 검사는 유지했다. 내부 식별자는 노출하지 않으며 row_id/target_id는 현재 UI 인스턴스 토큰이다.

## 실제 검증

Lab 6일차 준비 화면에서 진행했다. 작업 시작이나 장비 배정 변경은 하지 않았다.

| 항목 | 결과 |
|---|---|
| 참회 무기 | ZAYIN, WHITE, 5-7, 보통, 근거리 일치 |
| 참회 슈트 | RED 견딤(0.9), WHITE 견딤(0.8), BLACK 견딤(0.9), PALE 취약(2.0) 일치 |
| 장착 직원 | 무기 에덴·빅토르, 슈트 에덴·빅토르·아스터로이드 표시와 일치 |
| 조작 | 반환 좌표로 슈트 탭 전환 성공. 장비 슬롯은 클릭 대상 확인만 수행하여 장비를 바꾸지 않음 |
| 환상체 기록 | 단 한번의 악과 수백 가지의 선행 본문, 말소 문구 보존 |
| 스크롤 | 세 위치의 화면과 대조. 이전 상단 본문이 빠지고 새로 보이는 하단 본문이 전달됨 |
| 창 닫기 | 본문/장비 목록 빈 배열 확인 |
| 반복 관찰 | 변경 없는 본문/장비 섹션은 compact diff에 재전송되지 않음 |

실제 캡처 7개를 임시 reader에 재생하여 응답 변환·diff까지 확인했다. 타임스탬프만 테스트 시각으로 바꿨고 내용은 캡처 원문을 사용했다.
응답 처리 6.1~17.3ms는 Python reader 로컬 측정값이며 Unity 캡처 비용·MCP 왕복·모델 추론 시간을 포함하지 않는다.
기존 검사 포함 192개 통과, MCP stdio smoke 40 tools 통과, 생산용 식별자로 구성한 C# 누적 패치 컴파일 통과.

## 확인 범위와 남은 한계

이번 실제 장비 검증은 보유 중인 무기/슈트 각 한 종류다. 모든 장비·특수 보스 효과를 검증한 것은 아니다.
본문은 줄 전체가 관찰 가능한 경우에 전달한다. 스크롤 경계나 다른 컨트롤에 걸친 줄은 생략될 수 있다.
실제 Unity rich-text 서식 태그를 포함하는 문단은 현재 제외한다. 한국어 `<데이터 말소>` 같은 서사 표기는 제외하지 않는다.
반환된 슬롯 좌표는 현재 클릭 핸들러 존재를 뜻하며 장착 조건 충족을 보장하지 않는다. 모든 슬롯 클릭을 실제 실행해보지는 않았다.

증거: `D:/Projects/Robotomy_Lab/.robotomy/verification/reading-*.png/json`, `reading/reader-roundtrip.json`, `reading/tests-staged.txt`, `reading/mcp-smoke.txt`, `reading/production-integrity.json`.
원본 플레이 프로세스 PID 10260 유지, 보호 세이브 6개 해시 일치, manifest 대상 생산용 소스 변경 없음. 녹화 조작 없음.
검증용 게임은 준비 화면에서 입력을 차단하고 남겨두었다.
