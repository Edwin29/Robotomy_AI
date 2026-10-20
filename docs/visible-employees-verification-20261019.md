# 화면에 보이는 직원 관찰

## 게임 구조 근거

분석 대상은 기존 Assembly-CSharp.decompiled.cs와 별도 Lab 런타임이다.
AgentUnit.ui.Name과 AgentUnit.agentUI.Name은 실제 같은 표시 Text를 가리켰다.
AgentUI.SetActive는 연구 미개방 시 BlackHide를 활성화하지만 이름 Text는 계속 렌더링된다.
따라서 기존 ConsoleDisclosure의 HUD 전체 차단을 이름과 BlackHide 자체에 한해 해제했다.
HP/SP 및 나머지 가려진 값은 차단을 유지한다. 52개 C# disclosure 검증에 이름 예외를 추가했다.

AgentUI.OnSetState와 SetSelectState는 상태색/선택 강조색을 Texture와 BlackHide에 반영한다.
관찰은 현재 보이는 그래픽의 색을 stateColor 배열과 대조한다. 모델 State/IsPanic 등은 읽지 않는다.
일치가 없거나 색이 중복되면 unknown이다. 죽음/패닉/통제불가의 실제 사건은 이번 Lab에서 만들지 않았다.

UnitMouseEventTarget.target은 실제 AgentUnit에 연결되어 있고 같은 오브젝트에 Collider2D가 있다.
EventSystem의 실제 최상위 클릭 이벤트는 UnitMouseEventManager.OnPointerClick으로 연결된다.
게임은 Physics2D.OverlapPointAll로 선택 대상을 찾는다. 방/통로 명령 대상은 직원 선택 대상과 다르므로
IMouseOnSelectListener를 가진 다른 대상과 겹칠 때만 단독 선택 지점을 보류한다.
후보 좌표는 보이는 추적 지점과 해당 직원 콜라이더 중심이다. 강제 선택이나 모델 명령 호출은 하지 않는다.
탄환 선택 모드와 DefaultClickBlocked에서는 click을 내보내지 않는다. 이 추가 분기는 소스/컴파일로 확인했으며 실제 탄환 실행 시험은 하지 않았다.

## 인터페이스

빠른 관찰 snapshot.visible_employees:

- track_id: 연속 관찰 구간 ID. 영구 직원 ID가 아니다.
- name: 현재 보이는 Text. 읽히지 않으면 null.
- position: 좌상단 기준 화면 픽셀. 이름표 중심을 우선 사용하고 기존 보이는 몸체 추적을 보조로 사용.
- object_velocity / camera_velocity / screen_velocity: 기존 화면 투영 벡터와 동일 단위.
- movement: moving/stationary/unknown. 카메라 이동을 뺀 속도가 1 px/s 초과하면 moving.
- condition: 표시색의 normal/panic/dead/uncontrollable/unknown. 작업 종류나 내부 AI 상태를 뜻하지 않는다.
- click: 별도의 선택 입력 좌표 또는 null. 현재 입력 경로의 일치 여부이며 성공 보장은 아니다.

작업 중/대기/제압이라는 내부 행동 상태를 추측해서 채우지 않는다. stationary는 일시정지에서도 나온다.
이름표가 보이면 직원 몸체가 시설 장식과 겹쳐도 위치 관찰을 유지한다. 이름표와 몸체가 모두 가려지면 제외한다.
기존 motion 만료(250ms) 시 visible_employees도 비워지며, diff는 /visible_employees 전체 교체를 제공한다.

## 실제 검증

Lab DAY6에서 아스터로이드/빅토르/에덴 3명 이름과 좌표 확인.
아스터로이드 보행은 object_velocity.x=38.16, 카메라는 0; 일시정지 후 0으로 관찰.
click=(668.59,447.02)로 아스터로이드 선택, 이후 직원 정보창의 같은 이름 확인.
카메라 이동 후 position과 click 갱신, 위쪽으로 이동한 캡처에서는 화면 밖 아스터로이드 제외.
옵션 메뉴가 화면을 덮으면 목록이 비어짐. 직원끼리 겹친 경우 이름/위치는 유지하고 click만 null.
선택 강조색에서는 condition=unknown으로 바뀌며 이전 normal을 계속 유지하지 않음.

실제 스냅샷 6개의 diff 전체 복원 확인. Python 회귀 테스트 209개 통과.
마지막 100회 전체 motion 처리 시간 중앙값 16.16ms, p95 45.53ms.
이는 기존 렌더링/벡터 검사까지 포함한 총시간이며 새 기능만의 비용이나 전후 개선률은 아니다.

근거는 Lab .robotomy/verification/employees-*.json 및 PNG, reading-audit.json, console-diagnostics.json이다.
실제 보스 효과·패닉·사망은 이번 검증 범위 밖이다.

## 배포

본 플레이 프로세스/세이브는 조작하지 않았다. Lab만 실행·조작했고 하루를 완료하거나 저장하지 않았다.
본 플레이 후보 DLL: .robotomy/patches/visible-employees-20261019/RobotomyObserver.dll.
앞선 E.G.O/방 클릭 수정도 포함하며 아직 본 플레이 DLL에는 적용하지 않았다.
config/player/AGENTS.md 및 Robotomy_Player/AGENTS.md에 사용법을 반영했다.
