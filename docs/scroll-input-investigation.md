# 관리법 목록 스크롤 조사 — 2026-10-18

진행 중인 게임에 입력·중지·재시작을 하지 않고 최근 기록과 기존 게임 디컴파일을 대조했다. 실화면에서 큰 휠 델타를 직접 보내는 검증은 하지 않았다.

## 확인된 사실

- 입력 `f9954018419e4e9794226b4ba7a0c585`: Main, PID 35676, `(986,225)`, `scroll_y=-2`, duration 80ms. 영수증은 input_sent. 전달 성공은 UI 이동 성공을 뜻하지 않는다.
- 대응 화면 `126794c02a994fe2998c624dfb79b2c3`에는 관리법 3~5가 보인다.
- `VirtualInput.cs`는 `wheel.y = -scroll_y / 120f`로 한 프레임 전달한다. 따라서 -2는 위로 약 0.0167칸이며, -240이 위 두 칸이다. duration은 휠 반복 횟수가 아니다.
- `PointerInputModule`은 BaseInput.mouseScrollDelta를 전달하고, `StandaloneInputModule.ProcessMouseEvent`는 현재 raycast 대상의 IScrollHandler로 보낸다.
- 게임 `CreatureInfoCaretakingSlot.OnScroll` (기존 Assembly-CSharp 디컴파일 288643 부근)은 본문 내부 스크롤이 필요하면 본문 ScrollRect로, 그 외에는 caretakingRoot.scroll로 전달한다. 잠긴 목록에서 휠 자체를 무조건 무시하는 구조가 아니다.

## 판단과 변경

현재 증거에서 먼저 확인된 문제는 델타 단위를 칸 수처럼 쓰게 만든 안내 부족이다. 이 한 입력만으로 다른 스크롤 문제까지 없다고 단정하지 않는다. 같은 좌표의 -240 또는 -600 입력 후 실제 이동 여부는 플레이어가 최신 화면을 기준으로 확인해야 한다.

가상 입력의 기존 단위·방향·크기 제한은 유지했다. `prepare_live_action` 결과의 scroll_info에 units_per_notch, notches, direction과 사용 예를 추가했다. 입력 준비 자체는 입력을 보내지 않는다. 작은 값도 미세 조작을 위해 여전히 허용하며 자동 확대·재시도하지 않는다.

플레이어 AGENTS 소스와 배포본, live-control 문서에 120=한 칸, 음수=위, -240=위 두 칸, 포인터를 목록 안에 둘 것, duration으로 반복되지 않는다는 내용을 반영했다. MCP 도구 스키마와 게임 DLL은 변경하지 않았다. live_control은 기존 idle-boundary hot reload 대상이다.

단위 표시와 전송 원값 보존 회귀 테스트를 추가했다. 게임 속 목록 이동에 대한 실시간 검증은 이번 변경의 테스트 결과에 포함하지 않는다.
