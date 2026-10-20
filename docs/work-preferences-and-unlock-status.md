# 작업 선호도와 잠금 사유

2026-10-19. 본 플레이 재시작 전까지 게임 측 새 필드는 적용 대기.
소스·수신부·플레이어 지침 수정, 배포 DLL은 `.robotomy/patches/preferences-20261019/`.
진행 중인 본 게임을 종료하거나 입력하지 않았다.

## 빠른 관찰

`console.hazards.creature_management.details` 예:

```json
{"kind":"work_preference","work":"본능 작업","I":"보통","II":"보통","III":"낮음","IV":"낮음","V":"낮음"}
```

작업별 최대 다섯 개의 보이는 등급만 전달한다. 미개방 표는 빈 행을 생성하지 않는다.
퍼센트나 숨은 모델 테이블로 바꾸지 않고 화면의 높음/보통/낮음 등 표현을 유지한다.

`costs`의 unlock 항목에는 두 가지를 독립적으로 추가한다:

- `funds`: 표시 잔고와 표시 비용만 비교한 sufficient / insufficient / unknown.
- `prerequisite`: 실제 선행 안내가 보이면 required, 아니면 not_indicated.

둘 다 막힐 수도 있다. sufficient는 전체 구매 가능 판정이 아니다.
not_indicated는 선행 조건 충족의 증거가 아니다. 필요하면 잠금 영역에 포인터를
올려 안내를 읽는다. 메뉴를 열 때 모든 잠금 상태를 내부에서 미리 조회하지 않는다.

## 게임 근거와 구현

캐시된 Assembly-CSharp ILSpy 소스의 CreatureInfoWorkSlot.SetWorkSuccess는
levelSuccessPercentage[i]에 직원 등급 i+1의 현지화 문자열을 넣는다.
직접 연결된 WorkName과 해당 Text 배열만 읽고 ConsoleDisclosure/화면 가시성 판정을 거친다.
런타임에서 4개 작업, 20개 셀을 실제 화면과 대조했다.

CreatureInfoOpenArea.OnOverlayEnter는 선행 관리법이 미개방이면 AreaText를
CreatureInfo_PrevNeed 문구로 바꾸고, TooltipMouseOver는 0.5초 뒤
Tooltip_CreatureInfo@NeedPreviousManagement 문구를 OverlayManager.OverlayText에 표시한다.
코드는 표시된 문구를 대조할 뿐 IsOpenable, PrevSlot, 구매 가능 모델을 읽지 않는다.
두 줄짜리 AreaText가 스크롤 마스크에서 잘릴 수 있어 별도로 보이는 툴팁도 확인한다.
툴팁은 현재 가상 포인터가 해당 잠금 영역 안에 있을 때만 그 항목과 연결한다.
툴팁 원문은 기존 UI 텍스트에도 계속 전달된다.

## 검증

Lab `.robotomy/verification/preferences-open`에서 작업별 I~V 20칸 일치.
잠긴 환상체에서 선호도 행 없음, 잔고 0/비용 2·4·12는 insufficient.
잔고 미표시·비숫자 비용은 unknown, 선행 조건과 자금 조건 독립성은 단위 테스트.
전체 회귀 테스트 204개 통과. 최초 선택 실행은 테스트 모듈 경로 문제로 실패했고,
정식 discover 방식으로 전체 실행하여 통과했다.

본 게임 DLL 적용은 안전하게 종료 가능한 시점에 기존 DLL/세이브를 백업한 뒤
공식 prepare_live.py --finish-build 및 launch_live.py로 수행한다.

최종 Lab 재실행 검증: `pref2-hover`에서 포인터가 올라간 관리법 항목 하나만
prerequisite=required 및 funds=insufficient로 구분됐다. `pref2-unhover`에서
포인터를 옮기자 required가 제거됐고, 미개방 작업 선호도는 계속 제외됐다.
구매 클릭 없이 검증했다. 검증용 게임은 종료했고 본 플레이 PID 40820은 유지했다.


## 본 플레이 적용 완료 — 2026-10-19 19:03 KST

사용자 승인으로 백업·정상 종료·빌드·재실행 완료(PID 33916). DAY 8 준비 화면으로 복귀.
본 관리창에서 네 작업 I~V 20칸, 잠긴 관리법 hover 시 required와 insufficient 동시 표시를
확인했다. 구매·작업·날짜 진행 없이 창을 닫았다. 본 게임은 live 상태로 유지한다.
원본 세이브 변경 없음. AI 저장 폴더는 Unity Analytics 실행 통계 세 파일만 추가됐으며
실제 게임 세이브 파일 집합과 해시는 동일하다. 기존 적용 대기 기록은 이 완료 기록으로 대체한다.
증거·백업 위치는 `.robotomy/patches/preferences-20261019/`에 기록했다.
