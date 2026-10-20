# 작업 선택창 구조화 (2026-10-19)

게임 분석 근거: Assembly-CSharp CommandWindow.WorkAllocateRegion (254149 부근)의 Name/CodeNo/RiskLevel/MaximumCubeGenerate/WorkDamageType/WorkDamageRange 및 slots. OnObserved/NonObserved가 표시 Text를 교체하므로 모델 값이 아닌 최종 Text만 읽는다. CreatureInfoStatFeelingStateSlot.SetData (290302 부근)의 0=bad,1=normal,2=good 대응으로 표시된 RangeText를 묶는다.

CommandWindow.WorkButton은 선택하면 interactable=false가 된다(255560 부근). null click은 선택됨을 단정하지 않는다. 특수 작업에서 Icon이 바뀌므로 실제 Work_R/W/B/P/S 스프라이트 일치로 종류를 읽고, 화면상 아이콘과 최상위 클릭 핸들러를 확인한다. 숨긴 WorkName이나 CurrentSkill은 읽지 않는다. 직원 행은 기존 OnClick 핸들러 검증을 사용한다.

빠른관찰 `command_window`: summary, work_results, work_types(name/click), employees, text_groups. 모든 승인된 command Text는 그룹/필드/원문으로 보존한다. 별도 필드로 매핑된 값도 원문을 유지한다. 도구형 누적 사용 횟수 제외 정책은 유지한다. 아이콘 직원 능력 등급은 이번 모든 Text 처리 범위와 별개다.

좌표는 화면 왼쪽 위 픽셀, target_id 포함. 기존 command_rows 유지. diff는 /command_window 전체 교체로 창 닫힘과 값 변경을 처리한다.

## 실제 검증 결과

Lab DAY6: 단 한번의 악과 수백 가지의 선행의 good 8–10 / normal 4–7 / bad 0–3, WHITE 1–2, 최대 PE 10이 화면과 일치. 네 작업 아이콘에 클릭 좌표/target_id가 제공됨. 통찰 클릭으로 직원 에덴·빅토르의 HP/SP/성공률/시간/클릭 좌표 확인. 직원 클릭 후 실제 에덴 통찰 배정 메시지 확인.

처음 발견한 누락은 반투명 색상 및 일반 PauseFilter 테두리 판정이었다. CommandWindow root 내부의 승인된 표시 Graphic에 한해 렌더링된 alpha>0.05를 허용하며 CanvasGroup/활성/마스크/화면 밖/외부 메뉴/효과 검사는 유지한다. 일반 pauseDefSprite/observeSprite의 화면 장식은 이 패널을 읽지 못하게 가리지 않으므로 해당 패널에서만 예외 처리했다. 실제 ESC 메뉴로 덮으면 command_window=null 확인.

게임의 일부 결과 슬롯은 Label과 RangeText가 같은 Text 참조다. RangeText를 우선 매핑해 pe_range가 되도록 했다. T-02-99 미해금 창에서 이름 코드/등급 ?/PE와 피해 및 세 결과 범위 Unknown 유지 확인. 숨겨진 값으로 보충하지 않는다.

214개 회귀 테스트 통과. 실제 open→직원창→ESC 가림→미해금 창 3회 diff 교체 확인. 증거: Robotomy_Lab/.robotomy/verification/command-final-*.json/png, command-assign.png. 본 플레이 PID32852는 재시작/입력하지 않음. 배포 후보 .robotomy/patches/command-window-20261019/RobotomyObserver.dll; 본 플레이 DLL 교체는 진행 중 플레이를 보존하기 위해 아직 하지 않았다. Python 소비자와 플레이어 지침은 업데이트 완료.
