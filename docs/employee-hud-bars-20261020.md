# 직원 HP/SP 바 — 검증 완료, 본 플레이 미배포

작업 사본: `.robotomy/hud-vitals-work`.
본 플레이의 Python/DLL/플레이어 지침은 변경하지 않았다.

## 게임 구조 근거

- 실제 Assembly-CSharp SHA256:
  `fb31a592f29a6d8a08e3884cf21d94bc8bd167c9aeefc2eef81a774c70b294bd`.
  REA identity evidence: `ev_dda6edcac12d4301638e2f5dff6574a8e912b83a53608563ee14aafd88f9e5c2`.
  원문: `.robotomy/analysis/hud-managed-evidence.json`.
- 기존 전체 디컴파일의 `InGameUI.AgentUI.ValidateUIActiate`, `Update`, `SetActive`,
  `UpdateHp`, `UpdateMental` 경로 확인.
- `show_agent_ui` 연구 또는 튜토리얼 단계 조건이 바 표시를 허용한다.
  잠금은 `BlackHide` 활성화로 표현된다. 잠금 중에도 fillAmount는 갱신되므로
  ActiveControl만 확인하면 정보가 유출된다.
- `resources.assets`의 AgentUI 4개 prefab(113630, 114953, 122314, 122631)의
  HpFill/MentalFill 참조를 해석했다. 모두 Image.Type=Filled(3),
  FillMethod=Horizontal(0). 원문 및 참조 분석은 작업 사본의
  `agentui-prefab.json`, `agentui-bindings.json`.
- 기존 전역 Gauge 수집은 월드 공간 UI를 제외하고 직원 식별도 없었다.
  이제 이미 카메라 가시성을 통과한 직원의 `unit.agentUI`에 연결한다.

## 변경

`ConsoleEmployee.cs`: 표시 중인 HP/SP Image의 fillAmount만 읽는다.
BlackHide 비활성, ActiveControl 활성, 실제 화면/카메라/마스크/효과 검사를 적용한다.
내부 HP/maxHP, 정신력, 연구 모델을 직접 읽지 않는다.
화면 바 너비로 반올림하여 `ratio`, `filled_pixels`, `total_pixels`를 반환한다.
값을 확인할 수 없으면 null, 실제 빈 바는 ratio=0이다.

`robotomy/live.py`: 직원별 hp_bar/sp_bar를 검증·보존한다.
`robotomy/perception.py`: 해당 필드 변경은 priority_changes에 둔다.
직원이 화면 밖으로 나가면 직원 항목 전체가 제거된다.
후퇴나 회복은 자동으로 수행하지 않는다.

## 검증 및 한계

- 별도 검증 게임 6일차, 자연 미해금 상태: bar=null.
- **실제 prefab의 표시만 임시 변경한 실기 실험**:
  50%/25% → 8/16, 4/16 픽셀; 0%/100% → 0/16, 16/16 픽셀.
  실제 직원 체력·연구·저장 값을 변경한 실험이 아니다.
- 잠금 덮개 재활성: 두 bar 모두 null, diff에서도 삭제 효과 확인.
- 실제 W 카메라 이동: 기존 직원의 ID가 목록에서 제거됨.
- HUD transform만 이동하는 실험은 게임의 위치 갱신이 덮어써 화면 밖 조건을
  만들지 못했다. `hud-offscreen-bars`라는 파일명과 달리 가시성 테스트의 성공
  근거가 아니며 실제 카메라 이동 결과를 채택했다.
- 실제 UI 표본을 소비자 검증/공통 diff로 통과시켜 변경과 null 전환 확인.
  해당 5개 표본의 Python projection+diff 처리 시간 0.61~1.21ms.
  캡처/통신/LLM 지연 및 전투 성능 측정은 아니다.
- 전체 회귀 테스트 257개 통과. 초회 작업 사본에는 .venv 링크가 없어
  workspace setup 테스트 하나가 실패했으며 링크 구성 후 통과했다.
- 해금 연구를 실제 플레이로 완료하는 전 과정과 예소드 보스전 실기는
  이번에 재현하지 않았다. 기존 효과 차단 경로는 유지했다.
- 검증용 게임은 정상 종료. 진단 probe를 제외한 lab DLL로 정리했다.
  production DLL은 빌드만 했으며 본 플레이에 설치하지 않았다.

## 다음 배포 시

현재 본 플레이의 추가 수정 여부를 비교하고 다음 파일만 병합한다:
`mods/RobotomyObserver/ConsoleEmployee.cs`, `robotomy/live.py`,
`robotomy/perception.py`, `tests/test_employee_bars.py`,
`config/player/AGENTS.md`의 새 HP/SP 절.
게임이 안전하게 종료된 뒤 production DLL 배포 및 manifest 해시 갱신.
플레이어 실제 폴더 지침도 그때 갱신한다. Lab 파일이나 세이브는 복사하지 않는다.
