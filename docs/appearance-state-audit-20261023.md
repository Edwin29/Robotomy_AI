# 환상체 외형 상태 조사 — 2026-10-23

개발자용 조사 기록. 플레이어 지침/Playnote에 자동 전달하지 않는다.
구현·런타임 주입·게임 조작·세이브 수정 없이 로컬 DLL과 직렬화된 에셋을 분석했다.

## 결과

공통 외형 상태 출력은 가능하다. 다만 모든 환상체의 내부 상태 enum을 그대로
내보내는 방식은 부적절하다. SpriteRenderer 활성 상태, Animator의 실제 표시 상태,
Spine attachment 색/부착 상태, 표시 객체 교체 등 여러 표현 경로를 지원해야 한다.

| 대상 | 확인한 표시 경로 | 추출 후보와 주의점 |
|---|---|---|
| 당신은 행복해야 합니다 | YouMustHappyAnim.SetYesNo가 spriteYes/spriteNo.enabled를 반대로 설정. 프리팹 자식 yes/no에 서로 다른 Sprite 연결 | 화면에 보이는 YES/NO. 내부 성공 판정, 사용 횟수, 미래 전환 시간은 제외. 비활성/미사용 때 남은 Sprite 값이 현재 유효한 표시인지 실제 화면 대조 필요 |
| 오늘의 표정 | ShyThingAnim.SetFaceType → Animator FeelingState. 실제 ShyThing_Controller에 다섯 표정 상태 존재 | 현재 재생되는 표정 상태를 불투명한 고정 ID로 변환. 파라미터 설정 시점과 실제 전환 시점의 차이를 확인해야 함. 내부 성공률/피해 배율은 외형 상태에 포함하지 않음 |
| 역병의사 | PlagueDoctorSkeletonAnim.SetState가 부위 활성, Spine Region/Mesh attachment 색을 변경 | 표시된 외형 조합을 식별. 단순 날개 색뿐 아니라 날개 추가, 의복/머리 색, 광채/고리/몸체 변경. ApostleLevel 또는 내부 _currentState를 플레이어 상태 번호로 노출하지 않음 |
| 백야 | PlagueDoctor.GenDeathAngel → CreatureManager.ReplaceCreature. 이후 별도 DeathAngelAnim/Animator 사용 | 교체로 인한 ID 변화와 격리실 위치의 연속성을 함께 다뤄야 함. DeathAngel 컨트롤러의 내부/외부/특수 동작 등은 실제 보이는 동작으로 검증한 뒤만 매핑 |

## 타이밍

- ShyThing.OnEnterRoom에서 표정 변경 타이머 중지, OnReleaseWork에서 재개.
  작업 명령을 보낸 순간과 실제 입장 순간은 다르다.
- YouMustHappy.OnEnterRoom에서 표시/변경 타이머 시작. OnReleaseWork에서 타이머를
  멈추고 현재 값으로 결과를 처리한다.
- UseSkill.CancelWork → CloseWork → creature.script.OnReleaseWork 경로 확인.
  물리적인 퇴장 애니메이션 완료까지 기다렸다 판정한다고 가정하면 안 된다.
- YouMustHappy.OnNotice에는 PAUSE 감지 시 CancelWork 호출이 있다.
  따라서 타이밍 관찰을 위해 무조건 일시정지하면 작업 자체가 끝날 수 있다.
  이는 개발상 고려사항이며 미경험 플레이어에게 공략으로 자동 전달하지 않는다.
- 로컬 실행 순서와 렌더 완료 시점까지는 이번 정적 조사로 검증하지 않았다.

## 공통 출력 제안 (아직 미구현)

격리실의 appearance에 state_ref, label, alias, observed_at을 제공한다.
상태 번호는 최초 관찰 순서에 따라 부여하며, 사전에 총 개수나 미래 상태를 공개하지 않는다.
동일 외형에는 안정적인 참조를 유지하고 플레이어 별칭/설명을 연결한다.
YES/NO처럼 명시적인 표시 글자는 그대로 label로 활용한다.
서로 다른 환상체의 '상태 1'이 같은 의미가 되지 않도록 ID 이름공간은 구분한다.

직원 표식과 동일한 별칭 저장 체계를 쓰되, 출력에서는 대상 직원/격리실에 붙인다.
표시 의미·안전성·작업 추천은 플레이어가 경험으로 기록한다.
상태가 바뀐 경우에만 diff에 넣고, 화면 밖은 사라짐/소멸로 처리하지 않는다.
idle의 매 프레임 자세나 입자별 난수를 새 상태로 만들지 않는다.

## 증거와 한계

- 분석 DLL: private main runtime의 Assembly-CSharp.dll.
  SHA256: FB31A592F29A6D8A08E3884CF21D94BC8BD167C9AEEFC2EEF81A774C70B294BD.
- ILSpy CLI로 관련 10개 클래스 및 UseSkill을 역컴파일했다.
  로컬 원자료: `.robotomy/appearance-audit/` (Git 제외).
- resources.assets 프리팹 root path IDs:
  ShyThing 41582, YouMustHappyAnim 28906, PlagueDoctorAnim 24968, DeathAngelAnim 29391.
- 프리팹 Animator 참조: ShyThing 9916, YouMustHappy 9937,
  PlagueDoctor 9802, DeathAngel 9804. 컨트롤러 이름/상태 데이터도 확인했다.
- YES/NO Sprite path IDs: 12722/12490.
- MonoBehaviour의 기본 typetree에는 커스텀 필드가 완전히 포함되지 않아
  전체 역직렬화가 실패했다. 부분 읽기는 계층/기본 참조 확인에만 사용했다.
  역병의사 changeData/activateParts의 실제 모든 직렬화 부위 매핑은 미확인이다.
- 실제 화면 픽셀, 전환 중 혼합 상태, 카메라/마스킹, 재접속 후 ID 안정성은
  검증용 실행에서 후속 확인이 필요하다. 현재 결과는 구현 가능성의 정적 근거이며
  플레이어 전달 기능이 이미 동작한다는 의미는 아니다.
- 게임/런타임 코드 및 플레이어 기록은 변경하지 않았다. 기존 스크롤 패치는 별도 보류 상태.
