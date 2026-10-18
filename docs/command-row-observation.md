# 직원 선택창 행별 관찰 — 구현, 배포 및 실제 대조 대기

## 근거와 변경

기존 command 패널은 일반 Text/Button 목록만 제공했고 ConsoleDisclosure가 AgentSlot
HealthText/MentalText를 명시적으로 차단했다. 이름/상태의 누락은 개별 렌더 거부 사유도
있을 수 있으며 이 변경만으로 모든 누락을 해결했다고 주장하지 않는다.

로컬 Assembly-CSharp 분석 AgentSlot(253722 부근)에서 AgentName, HealthText,
MentalText, FilterText, WorkFilterText, WorkFilterSubText의 표시 참조를 확인했다.
SetFilter/OnOverlayEnter/OnClick을 확인한 결과 명령 가능 여부는 단순 Button 상태가
아니며 MOVING에서도 조건이 갈린다. IsOrderable/State/CurrentAgent는 수집하지 않는다.

저장된 실제 PNG c9b23e27b7eebeb4d14a8033d101b7f341aa194bce0975c1588ea4a6ebe04bfd에서
에덴33/33·39/39, 빅토르39/39·29/29, 아스터로이드35/35·34/34의 선택창 표시를 확인했다.
파일은 경험 저장소 Media에만 있고 Git에 넣지 않는다. 이는 해당 화면에서 숫자가 보인다는
근거이며 모든 진도/보스 효과 검증은 아니다.

숫자는 화면의 Text가 활성·마스크·가림·투명도·효과·문자 표시 완전성 검사를 모두
통과할 때만 전달한다. 원시 체력, 최대체력, 연구 플래그, 숨은 툴팁을 읽지 않는다.
HealthFill/MentalFill 원시 게이지 값의 제한은 유지한다.

## 응답

snapshot.command_rows (diff에서는 /command_rows)에는 현재 제공한 텍스트/버튼만
행 ID로 묶는다. name/hp/sp/status/action/action_detail은 보이는 문자열 그대로,
누락은 null이다. hp/sp의 문자열을 내부 값으로 보충하거나 이전 행으로 복원하지 않는다.
행 ID는 UI 인스턴스 ID이며 직원의 영구 식별자가 아니다. UI가 재사용될 수 있으므로
이전 이름을 ID만으로 연결하면 안 된다.

click은 허용된 이름/행위 텍스트 중심에서 EventSystem의 최상위 PointerClick 수신자가
AgentSlot.OnClick을 연결한 EventTrigger인지 읽기 전용으로 확인한 좌표다.
정보 버튼 OnClickInfo는 배정 좌표로 제공하지 않는다. 실제 입력이나 이벤트 호출은 없다.
클릭 수신 가능성을 작업 배정 가능성으로 해석하지 않는다. selectable은 현재 null이며
status/action의 표시를 플레이어가 판단하거나 hover 후 확인한다.
이 커스텀 행 좌표를 앞서 만든 일반 Button의 input_verified 예약 대상으로 위장하지 않는다.

## 적용과 검증

소스는 별도 게시 checkout에만 변경했다. 실행 중 게임·MCP·세이브·녹화는 변경하지 않았다.
적용에는 격리 Observer 갱신과 게임/MCP 재시작이 필요하다.
컴파일·Python 행 그룹화/숨은 값 배제/누락과 가림 이후 행 삭제 테스트를 수행했다.
배포 후 직원창을 열고 동일 화면에서 이름/HP/SP/상태/좌표를 대조해야 한다.
스크롤 잘림, 다른 패널 겹침, 비활성 직원, 이동/작업 중, hover 전후도 별도 검증한다.
그 전에는 실제 누락 해소율이나 속도 향상을 주장하지 않는다.
