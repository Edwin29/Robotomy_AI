# AI 게임기 통합 조작 안내


`observe_player()`와 `player_action()`은 같은 `player_view_v1` 응답을 준다.
`alerts`의 주요 사건을 먼저 보고, `combat`, `updated`, `action`으로 변화를 확인한다.
`updated`에는 바뀐 대상의 현재 행이 들어오므로 필드별 diff를 재조립할 필요가 없다.
생략된 항목은 변경 없음이다. `left_view`는 시야에서 빠졌다는 뜻이며 사망 판정이 아니다.
재연결·컨텍스트 압축 뒤에는 `observe_player(full=true)`로 현재 공개 화면을 다시 받는다.
스토리·표정·새 연출은 기존 전체 화면 도구로 직접 관람한다.

관찰에서 받은 `ref`를 다음 조작에 그대로 사용한다. 참조는 현재 게임 실행에 한정된다.
아래 `<직원 ref>` 등은 관찰에 나온 값으로 바꾼다.

```json
{"kind":"input","command":["L","<대상 ref>"]}
{"kind":"move","employee":"<직원 ref>","destination":"<시설 ref>"}
{"kind":"work","employee":"<직원 ref>","room":"<격리실 ref>","work":"본능"}
{"kind":"state","setting":"paused","value":true}
{"kind":"state","setting":"speed","value":2}
{"kind":"state","setting":"gift_locked","target":"<잠금 버튼 ref>","value":true}
```

이 객체를 `player_action(action=...)`에 전달한다. 클릭 대신 `H`로 올려두기,
`R`로 우클릭, `K`로 키 입력, `Z`로 기존 확대·축소 입력도 가능하다.
입력 후 응답이 이미 관찰을 포함하므로 이유 없이 전체 관찰을 한 번 더 요청하지 않는다.
`action.dispatch`는 전송 결과이고 `action.ui`는 UI 준비 여부다. 도착이나 작업 완료가 아니다.
`action.state.confirmed`는 요청한 상태가 화면에서 확인됐는지를 나타낸다.
이미 그 상태면 `already_set`으로 끝나며 입력하지 않는다.
중복 전송을 막으려면 동일 행동 재조회에 같은 `request_id`를 사용한다.
`not_repeated`는 추가 입력하지 않았다는 뜻이다. 다른 행동에는 새 ID를 사용한다.

`schedule_player_actions(actions=[...])`에는 같은 문법으로 1~5개를 예약한다.
10초 내의 명시된 순서만 실행하며 반복·조건부 전략은 없다.
`player_schedule_status(schedule_id=..., cancel=true)`로 나머지를 취소한다.
실행 중 한 입력은 끝날 수 있다. 장면 변경, 대상 소실, 실패, 일시정지 예약 발동 시 중단된다.
예약 결과는 `player_schedule_status`로 확인한다. 실행 중 다른 조작을 동시에 보내지 않는다.

`combat.damage`는 짧은 시간 동안 보인 피해 숫자의 묶음이다. `count`는 표시 개수,
`sum_displayed`는 표시 숫자의 합으로 실제 HP 감소량·공격 횟수와 같다고 단정하지 않는다.
보호막의 표시·균열·파괴 효과·사라짐 시작과 화면의 잔탄 수 변화도 별도로 온다.
효과가 보였다는 사실만으로 숨은 지속시간이나 남은 흡수량을 알 수는 없다.
`motion:N`은 보이는 모션을 구분하는 표식이며 공격명·패턴 정답이 아니다.
모션 표식은 `combat.scope` 안에서만 유효하다. 재실행 후 같은 번호를 같은 모션으로 간주하지 않는다.
투사체의 `visual:` 참조는 렌더링 단위 관측이며 공격자나 클릭 대상 참조가 아니다.
`read_combat_events(after=..., limit=...)`로 필요한 구간의 개별 시점을 확인한다.
가까운 모션·투사체와의 시간/위치 연결은 원인 확정이 아닌 관찰 단서다.
`view_target(target="<ref>",frames=1)`은 대상 확대 이미지,
`frames=2..6`은 보관된 시각별 이미지를 돌려준다. 과거 이미지로 현재 좌표를 정하지 않는다.

아래 기존 도구는 세부 조작·전체 화면·기존 호출 호환을 위해 계속 제공한다.
