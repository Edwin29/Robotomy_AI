# 직원 상태명과 화면 밖 사망 예외

사용자가 2026-10-19에 승인한 기준: 일반 행동 상태는 카메라에 보이는 직원에게만,
사망 상태는 카메라 밖에서도 제공한다. 기존 색상 기반 condition을 status/status_label로 대체한다.

## 게임 코드 대응

Assembly-CSharp의 CommandWindow.AgentSlot.CheckAgentState/SetFilter는
IsDead → IsPanic → IsCrazy → IsSuppressing → MANAGE/currentSkill 유무 → IDLE 순서로
사망·패닉·통제불가·제압·이동·작업 상태 및 그 표시를 정한다.
AgentUnit.SetSelectIconColor는 작업/제압 표시색을, StartWork/EndWork는 Work 애니메이션을 설정한다.
WorkerUnit.LateUpdate는 GetMovableNode().IsMoving을 Move 애니메이션에 연결한다.
SetPanic은 Panic 애니메이션/얼굴 표시와 연결된다.
현재 구현은 위 상태 분류를 사용하며 IDLE의 실제 보행도 이동 중으로 구분한다.
일시정지해서 화면 벡터가 0이 되어도 작업/이동 명령 상태는 보존한다.
그 외 검증하지 않은 특수 AI 상태는 미확인이다. 숨겨진 목적지·시간·작업 대상은 전달하지 않는다.

일반 상태 조회는 기존 ConsoleMotion의 현재 화면 가시성 판정 이후에만 실행한다.
화면 왜곡/가림 판정을 통과하지 못하는 살아 있는 직원 상태를 별도로 가져오지 않는다.

## 사망 판정

WorkerModel.OnDie는 _isDead를 설정한다. AgentModel.OnDie는 OnAgentDead 알림과
Angela 사망 메시지를 만들고, AgentUnit.OnDie는 사망 애니메이션과 이름표 숨김을 실행한다.
시체의 렌더러가 남아 있는지는 사망 여부의 기준이 아니다.

console.dead_employees와 빠른 관찰 dead_employees는 현재 AgentManager 직원 명단에서
IsDead인 직원의 식별자/이름/status=dead/status_label=사망만 제공한다.
시체 위치·원인·내부 체력은 공개하지 않는다. 이는 현재 명단의 상태 목록이며 영구 사망 이력이 아니다.
로드/재시도 후 살아 있는 상태라면 사망 목록에서 제외된다. 역사 기록은 플레이 경험 저장소가 담당한다.

## 검증과 배포

Lab 본편 DAY6에서 자연 보행/대기 상태와 화면상 벡터 대응 확인.
화면 밖으로 아스터로이드를 이동시킨 카메라에서 Lab 전용 테스트로 AgentModel.Die를 호출했다.
이는 자연 플레이 사망이 아닌 통합 검증 fixture다. 일반 visible_employees에는 나오지 않고
dead_employees에만 사망이 추가됐으며 diff /dead_employees도 확인했다.
실제 작업/제압/패닉 사건은 이번 테스트에서 발생시키지 않았고 해당 분기는 게임 코드 대응을 확인했다.
211개 회귀 테스트 통과. 사망 출력 허용 목록에서 위치/체력/원인이 제거되는 테스트 포함.

증거: Robotomy_Lab/.robotomy/verification/state-*.json 및 PNG.
본 플레이 PID33916은 재시작/조작하지 않았다. Lab 테스트는 하루 완료·저장 없이 종료했다.
본 플레이 적용 후보: .robotomy/patches/employee-states-20261019/RobotomyObserver.dll 및 manifest.json.
이 DLL에는 Lab 사망 테스트 트리거가 들어 있지 않으며, 아직 본 플레이 DLL을 교체하지 않았다.


## 본 플레이 배포 완료 (2026-10-19)

검증 후보 DLL을 본 플레이 런타임에 적용하고 공식 launch_live.py로 재실행했다.
SHA256: `0bc824be8dd5c16ed4d68bf110cb29b2d17354b1ddc8699303b9d1ba72842c22`.
8일차 준비 화면에서 종료했으며, 재실행 후 타이틀 화면에서 대기한다. 새 프로세스 PID32852의 live 연결과 console.dead_employees 출력을 확인했다.
직원 상태/사망 목록/방 click 지침은 config/player/AGENTS.md 및 Robotomy_Player/AGENTS.md에 동일하게 반영했고, 실제 read_player_guide 응답에도 포함됨을 확인했다. MCP runtime ready, reload_error=null.
백업: `.robotomy/backups/production-employee-states-20261019T200513`. 원본 전체 파일과 본 플레이 세이브 해시 일치. 종료 중 Unity Analytics 로그만 일시적으로 변경됐고 최종 비교에서는 전체 파일 해시도 일치했다.
본 플레이에서 하루를 시작하거나 사망 테스트를 수행하지 않았다. 동작 검증 범위는 위 Lab 결과와 동일하다. 이전 EGO/방 클릭/직원 벡터 패치를 포함한다.
