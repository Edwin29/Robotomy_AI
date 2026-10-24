# 환상체 외형·모션 확장 조사 — 2026-10-23

개발자용 정적 조사. 플레이어 공략/경험 기록으로 전달하지 않는다.
앞선 `appearance-state-audit-20261023.md`의 YES/NO·표정·역병의사·백야 조사에 추가한다.
이번 작업은 조사와 문서 작성뿐이며 게임 입력, 재시작, DLL/MCP 변경, 세이브 조작은 없다.

## 조사 범위와 결론

- private runtime Assembly-CSharp.dll 전체를 ILSpy로 역컴파일해 공통 기반과 외형 제어 경로를 검색했다.
- resources.assets의 `prefabs/unit/creatureanimator/` 아래 161개 리소스 참조에서 계층과
  AnimatorController 연결을 조사했다. 중복 제거 컨트롤러 185개. 구형/보조/시련 객체도 포함하며
  이는 환상체 개체 수가 아니다.
- BaseMod/BaseCreatures의 stat XML 116개에서 anim 프리팹 경로를 교차 확인했다.
  이 중 103개에서 컨트롤러를 찾았고 중복 제거 148개였다. 나머지 13개는 해당 경로에서
  컨트롤러가 발견되지 않았다는 뜻이지 외형 변화가 없다는 뜻이 아니다.
- 모든 환상체가 공유하는 완전한 의미 태그 집합은 없다. 여러 이름을 공유하는 제어 파라미터와
  일부 공통 메서드는 있으나, 표시 상태 판독에는 개별 컨트롤러/객체 구조를 결합해야 한다.
- 모션, 폼, 부착물, 작업 결과 UI를 한 가지 내부 enum으로 평탄화하면 정보가 잘못 합쳐진다.
  출력에서는 간단한 공통 형식을 유지하되 식별 키를 내부적으로 나누는 편이 적절하다.

## 실제 공통 부분

`AnimScript.animator` → `CreatureAnimScript` → `CreatureAnimEventCalled`가 공통 기반이다.
후자는 Move/Stop에서 Move 파라미터 존재를 확인하고, Attack/Kill/Attract 메서드도 제공한다.
다수 파생 클래스가 이를 재정의하며, Animator의 bool/int/trigger 사용법과 실행 시점이 다르다.

전체 역컴파일에서 CreatureAnimScript/CreatureAnimEventCalled를 직접 상속하는 전역 클래스의
문자열 리터럴 Set 호출을 검색하면 Dead 46, Attack 41, Move 35, AttackType 23개 클래스에서
사용된다. 보스/시련/보조 클래스가 포함된 검색 통계이며, 지원율이나 활성 환상체 수가 아니다.

실제 Unity Animator **Tag**는 다른 개념이다. 위 148개 컨트롤러에서 비어 있지 않은 태그는
BloodBath_CTRL의 Default 1개/Killing 2개와 AgentCtrl의 Attack 5개 상태뿐이었다.
전체 185개 표본에서도 같았다. 대부분 상태에는 태그가 없으므로 IsTag만으로 분류할 수 없다.
공통 이름이 있다는 이유로 Attack=true를 현재 공격 화면으로 즉시 전달해서도 안 된다.
예약된 전환/블렌딩/애니메이션 이벤트와 실제 표시 사이의 시차가 있다.

## 요청한 세 환상체

| 대상 | 코드에서 확인한 구조 | 에셋 교차 확인 | 설계상 의미 |
|---|---|---|---|
| 증오의 여왕 | MagicalGirlAnim: hero/villain 두 GameObject 및 Animator. Phase로 중간 동작을 시작하고 EndTransformToVillain 이벤트에서 표시 객체를 교대 | MagicalGirl_stat의 MagicalGirl 프리팹, Hero 9871/Villain 9872. 평상·Panic·transform 및 서로 다른 동작 상태 | 논리 Camp/Phase만 읽지 않고 활성 몸체와 현재 표시 동작을 확인. 변신 중을 변신 완료로 보고하지 않음 |
| 아무 것도 없는 | NothingAnim.ChangeForm: Lv1Node/Lv2Node/eggNode 교대. 직원형에서는 셋을 끄고 Nothing.TransformToWorker가 NothingWorker 표시 객체를 별도로 생성 | Nullthing_stat → Nothing 프리팹. Lv1 9982/Lv2 9674/egg 계열 컨트롤러와 직원 계열 연결 | 기본형·알·변형체뿐 아니라 별도 직원 표시 경로 필요. 부모 animTarget 한 개만 관찰하면 직원형을 놓침 |
| 웃는 시체들의 산 | DangoCreature.OnChangeDangoLevel → DangoCreatureAnim.SetLevel. Level 및 LevelChange/Reduce와 함께 위치 피벗·그림자 변경 | DangoCreature_stat → DangoCreature 프리팹, 9840에 Level0~3 및 Change/Walk/Attack 상태 | 외형 성장과 이동/공격 동작을 분리. 내부 먹은 수·다음 성장 조건은 노출하지 않음 |

아무 것도 없는의 직원형은 특히 주의: 내부 타입/복제 원본/추적 ID를 그대로 붙여
사람에게 구별되지 않은 위장 정체를 자동으로 판별하는 관찰 도구가 되어서는 안 된다.
보이는 외형의 대응과 플레이어가 실제 관찰한 변신의 연속성만 연결해야 한다.

## 추가로 확인한 후보

아래는 코드상 표시 변경과 stat 연결 컨트롤러를 확인한 사례다.
화면에서 구별 가능한 이름과 상태 경계는 아직 런타임 검증 전이다.

| 환상체 | 표시 변화 경로 | 근거 메서드/필드 |
|---|---|---|
| 공허한 꿈 | sheep/chicken 몸체 교대, 울음 시작·루프·종료 | BakuAnim.TransformToSheep/TransformToChicken, 컨트롤러 9812/9811 |
| 불새 | burnt/burning 표시 객체 교대, 회복·공격 준비/루프/종료 | FireBirdAnim, 9845/9846 |
| 뽀대 | NormalPpodae/FrenzyPpodae 교대 및 변신 효과 | PpodaeAnim.Transmute, 9889/9890 |
| 커다랗고 나쁠 늑대 | 일반형/다른 몸체 교대, 일반·배부른 모습 등 상태, 달 표시 | BigBadWolfAnim._normalWolf/_badassWolf, State, MoonAnimator; 9686/9815/9813/9814 |
| 풍운승려 | monk/ghoul 객체 교대와 변신 동작 | FengYunAnim.OnCalled, 9843/9844 |
| 미녀와 야수 | 기본·약화·특수 변화 및 전환 동작 | BeautyBeast.ChangeState/OnFinishWork, BeautyBeastAnim.SetState, 9950 |
| 흑조의 꿈 | 여러 형제 각각의 Transform/BrotherNum, 부위별 다른 모습 | BlackSwanAnim.TransformBrother, 9818. 서로 독립적인 부분 변화라 조합을 고려 |
| 징벌 새 | 빨간 색상/분노 효과 및 동작 변경 | SmallBirdAnim.OnMadStart/OnMadReteurn, coloredTarget/coloredMat, 9717 |
| 피의 욕조 | 손 표시 0~3개의 활성 조합, 별도 특수 동작 | BloodBathAnim.UpdateHandState, 9677 |
| 늙은 여인 | 격리실 효과 묶음 활성/비활성 | OldLadyAnim.SetEffect/DisableEffect, dust 9810. 내부 stack 수를 그대로 노출하지 않음 |
| 이름이 없는 태아 | 울음/평상/특수 동작 | NamelessFetusAnim.StartCrying/forcelyStopCrying의 Cry 파라미터, 9698 |
| 우주 속의 조각 | Change로 외형 전환, 서로 다른 이동/공격 동작 | CosmosAnim.ChangeForm/ReturnForm, 10118 |
| 벚꽃의 무덤 | Phase별 표시, Healing/Sacrificed 동작 | SakuraAnim.UpdateAnim/OnHealStart, 9897 |
| 어린 왕자 | Normal/Transformed 교대, 별도 Phase/Casting | YoungPrinceAnim.ChangeState/SetPhase, 9939/9940 |
| 고요한 오케스트라 | 무대·커튼·지휘자·합창단 개별 활성/등장/연주/피날레 | SilentOrchestraAnim.Singer/Effect 및 conductorAnim; 여러 Animator 결합 |
| 알리우네 | 꽃잎 세 개의 알파가 순차 증가하는 연속 변화 | AlriuneAnim.ProgressCasting/ResetPetals, 9675. 알파 매 프레임마다 새 상태를 만들면 안 됨 |

정확한 외형 의미를 컨트롤러 영어 이름만으로 단정하지 않는다. 예를 들어 내부 ghoul,
Frenzy, Phase 같은 이름을 플레이어 라벨로 그대로 노출하지 않는다.

## 작업 결과와 표정은 별개

- 공통 작업 결과: UseSkill 종료 → IsolateRoom.OnFeelingStateDisplayStart → SetResult.
  CurrentResultRoot 활성, CurrentResultIcon 스프라이트 및 CurrentResultFilter 색 지정,
  WorkResultUIController.Show. 종료 시 이 UI를 숨긴다.
  따라서 현재 보이는 결과 UI는 좋음/보통/나쁨으로 공통화할 근거가 있다.
- 이는 모든 환상체가 같은 표정 애니메이션을 가진다는 뜻이 아니다. feelingState는
  논리 결과 값이므로 UI가 숨겨진 뒤에도 현재 표정으로 둔갑시켜 제공하지 않는다.
- 개별 후속 반응: Fairy.OnFinishWork는 결과에 따라 OnSkill을 호출하고,
  BlackSwan.OnReleaseWork는 결과 조건에서 형제 변화 경로로 이어진다.
  이런 동작/외형과 작업 결과 UI는 서로 연결된 별개의 관찰이다.
- MagicalGirlAnim.ChangeDefaultType은 Random.Range(0,3)으로 평상 동작을 선택한다.
  평상 모션의 차이를 곧바로 작업 결과나 기분 변화로 해석하면 틀릴 수 있다.

## 권장 공통 형식

플레이어에게는 대상별로 `외형: 상태 2(별칭)` / `동작: 동작 3(별칭)`처럼 짧게 제공한다.
직원 표식·부착물·이펙트는 이전 합의대로 하나의 표식 목록으로 유지한다.
외형과 동작 ID를 내부에서 분리하면 걷기/공격 때문에 폼 별칭이 깨지지 않는다.
각 관찰은 안정적인 불투명 참조를 가지며 별칭/설명은 플레이어가 부여한다.
알려진 작업 결과 UI는 별도 `작업 결과` 필드로 표현해 외형과 혼동하지 않는다.

공통 읽기 계층은 활성 표시 루트·현재 Animator 상태·Spine 부착/색·표시 효과를 수집한다.
환상체별 작은 매핑이 이를 외형/동작의 안정적인 키로 정규화한다.
공통 Move/Attack 이름은 연결을 돕는 근거이지 모든 환상체에 대한 자동 의미 인증이 아니다.
평상 변형/입자 난수/재생 진행도는 매번 새 ID를 발급하지 않는다.
다중 부위 조합과 연속 변화는 필요한 경우 부분별 짧은 관찰을 남긴다.
새 모습이 실제 나타났을 때만 번호를 부여하고, 미관찰 폼 개수·전환 조건·타이머는 공개하지 않는다.

## 후속 검증과 로컬 근거

이번에는 코드와 직렬화된 Animator 상태를 조사했으며 실제 실행 화면과 픽셀 대응은 검증하지 않았다.
MonoBehaviour 커스텀 필드의 완전한 직렬화 해독도 아직 하지 않았다.
계층 탐색은 기본 GameObject/Transform/Animator/Controller 필드만 사용했다.
일부 에셋 이름의 한글 표시 인코딩도 도구 출력에서 깨지므로 별칭 사전으로 직접 쓰지 않는다.

- DLL SHA256: FB31A592F29A6D8A08E3884CF21D94BC8BD167C9AEEFC2EEF81A774C70B294BD
- 로컬 원자료: `.robotomy/appearance-audit/full/Assembly-CSharp.decompiled.cs`
- 연결 목록: `creature-controller-inventory.json`, `stat-linked-controller-inventory.json`
- 파라미터 검색 통계: `parameter-inventory.json`
- 원자료/게임 에셋은 Git 제외 경로에만 보존. 이 문서에는 분석 요약만 기록.

실제 구현 검증은 기본 폼→전환 중→새 폼, 작업 종료 UI, 화면 밖→다시 관찰,
재접속 별칭 유지, 위장 외형의 정체 누출 여부를 대표 사례로 확인하면 된다.
모든 클래스를 개별 런타임 검증했다는 의미가 아니며 게임 적용은 하지 않았다.
