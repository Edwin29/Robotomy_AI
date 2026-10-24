# 플레이어 피드백 패치 — 2026-10-20

## 변경

- `ConsoleEmployee`: 가시성 검사를 통과한 직원의 실제 UI 선택 목록(`UnitMouseEventManager.seletedtargets`)을 사용한다. 호버/고정 정보창은 `selection.info_panel`로 분리한다. 운영 정보창 이름은 `inGameModeComponent.AgentName`, 준비 정보창은 `UIComponents.AgentName`이다.
- 정상 pauseFilter가 운영 정보창을 가렸다고 오판하던 경우를 수정했다. 두 기존 pause sprite와 해당 정보창 surface만 예외로 두며 외부 메뉴/보스 효과 검사는 유지한다.
- 기존 화면 HP/SP 바를 유지하고, 같은 이름이 유일한 화면 직원에 한해 현재 작업·제압 목록의 표시 문자열을 `displayed_vitals`로 연결한다. 내부 vitals/최대 능력치를 현재 값으로 대체하지 않는다.
- `ConsoleScreen`: 준비/결과/확장 화면의 실제 Text와 클릭 처리 대상을 수집한다. ResultScreen.ReportButton은 일반 Button이 아니며 자식 Click의 EventTrigger가 `OnPointerClicK`로 연결된다. 동작 의미는 공개 ReportButton index 분기로, 좌표는 현재 그래픽과 raycast로 확인한다.
- `screen_context`에 base/modal/actions를 제공하고 선택/화면/이야기 변화는 priority_changes로 전달한다. 연구창은 기존 본문·드래그 처리와 병행한다.
- 제압창의 적 이름/위험도/공격 속성 아이콘/내성을 `selected_enemy`로 묶는다. 적 정보는 직원 행으로 오인하지 않는다. 화면 속 명명된 개체의 실제 collider와 UI 입력면을 검사해 entity:track_id 선택을 제공한다. 별도의 게임 목표/상태 쓰기는 없다.
- 적의 display_bar는 현재 UI slider 비율/색이다. 일부 스크립트가 bar를 재활용하므로 정확한 HP/내부 타이머라고 단정하지 않는다. 관찰에서 사라짐은 `no_longer_observed`, 결과는 unconfirmed다. 일반적인 사라짐/보상만으로 처치나 자폭을 자동 분류하지 않는다.
- `player_orders`는 플레이어의 move_employee 명령을 세션별 최대128개 기억한다. 모델 목적지를 읽지 않는다. 현재 관찰과 대조한 이동 여부/목적 시설 내부 여부만 표시한다. UI ready는 행동 완료가 아님을 응답에 명시한다.
- 대사의 `DialogueDisplay.nowProcessing`/`StoryDialogueUI.dialogueNowProcessing`을 현재 보이는 대사와 함께 제공한다. 미래 스크립트는 읽지 않는다. revealing/ready/choice/transition을 전달하고 기존 화면 변화 중심 캡처에도 상태 변경이 반영된다.
- 새 MCP 도구나 스키마 변경은 없다. 기존 hot reload 대상 파일 안에 구현해 추가 MCP 재연결을 요구하지 않는다.

## 실제 구조와 검증

게임 DLL SHA256: `fb31a592f29a6d8a08e3884cf21d94bc8bd167c9aeefc2eef81a774c70b294bd`.
기존 REA managed 증거와 동일한 대상임을 해시로 확인하고 디컴파일 전체 관련 클래스와 런타임의 serialized EventTrigger 수신 객체/메서드를 대조했다. REA 도구는 이번 세션에 연결되지 않아 새 REA 실행 결과로 표현하지 않는다.

검증용 게임에서:

- 준비 화면의 날짜/LOB/최대 시련과 관리시작·매뉴얼·E.G.O LIST·고용·직원 버튼을 읽었다. 실제 관리시작 버튼으로 운영에 진입했다.
- 아스터로이드 선택과 일시정지 중 정보창 이름을 분리해 확인했다. 이동 지시 후 즉시 idle인 표본은 실패가 아닌 not_yet_confirmed로 기록됐다.
- 게임의 실제 제압창을 진단용 코드로 열어 WHITE 공격 속성, 4종 내성 `(1.0)`, 직원 현재 HP/SP 문자열을 화면과 대조했다. 자연 탈출/시련 전투 재현은 아니다.
- 실제 ResultScreen을 진단용으로 열어 결과 텍스트/랭크/보상/직원 수를 읽고, next_day→confirmation→cancel을 가상 입력으로 실행했다. 확인창에서 원래 버튼들은 빠지고 confirm/cancel만 제공됐다. 정상 하루 클리어 검증과 구별한다.
- StoryViewer 1일차의 실제 대사에서 revealing→ready, 현재 표시된 부분 문자열을 관찰했다. 스크립트 전체를 미리 반환하지 않았다.
- 결과창이 덮인 상태에서 직원/적/준비창 정보가 관찰에서 빠졌다. 기존 HUD 해금/가림/화면 밖 검증은 `employee-hud-bars-20261020.md` 참조.
- 부서 확장 어댑터는 ExpandUI의 표시 root와 이벤트를 연결했으나 Main 장면에는 해당 컴포넌트가 없어 이번 진단 호출로는 화면을 재현하지 못했다. StoryV2의 실제 확장 단계 및 선택지 클릭, 각 보스/시련의 특수 종료 연출은 이번 실게임 검증 범위에 포함하지 않는다. 숨겨진 타이머나 죽음 원인 추정으로 대체하지 않는다.

Python 회귀266개, 일반 MCP stdio53개 도구 smoke, reload host44개 도구의 같은 연결 코드교체/오류차단/복구 smoke 통과. reload smoke의 오래된 고정 도구 수37 검사는 필수 도구 집합 검사로 바꿨다.

증거: `.robotomy/player-feedback-work/evidence/` 및 같은 폴더의 테스트 로그. 게임 자료는 Git에서 제외한다.
배포 백업: `.robotomy/backups/20261020-player-feedback/`.
진단용 FeedbackProbe는 배포 DLL에 포함하지 않는다. 검증 게임도 종료한 뒤 진단 코드 없는 DLL로 복구했다.

## 본게임 적용

본 플레이 런타임에 배포하고 저장된 10일차 준비 화면으로 복귀했다. 최신 캡처에서 직원·환상체 카드와 UI가 정상 표시되며 빠른 관찰의 preparation 분류와 현재 버튼을 확인했다. 원본 저장 파일29개와 플레이용 저장 파일6개의 해시는 적용 전후 동일하다. 실제 플레이어 폴더의 AGENTS.md에도 새 필드 사용법을 반영했다. 새 MCP 스키마가 없어 기존 연결의 코드 재로딩으로 사용한다.
