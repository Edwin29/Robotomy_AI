# 환상체 선택 화면 hover 조사 — 2026-10-18

## 결론과 검증 범위

실제 선택 화면에서 **상자 그림의 가장자리에서는 반응하지 않고 중앙에서는 클릭 없이 확대·설명이 표시됨**을 재현했다. 기존 Unity 가상 입력 DLL을 변경하지 않고 확인했다. 이동 기능이 끝날 때 포인터가 사라지거나 클릭 중에만 hover를 처리하는 문제가 아니다.

아래의 최초 조사는 읽기 전용으로 수행했다. 이후 사용자가 게임 종료·1일차 재시도를 허용하여, 분리된 저장 폴더를 백업하고 정상 조작으로 1일차를 진행해 선택 화면을 재현했다. 검증 진행은 플레이어 경험에 포함하지 않았다. 마지막에는 검증 전 본편 저장 파일을 복원하고 이전 선택 캐시만 별도 보관하여, 플레이어가 1일차부터 재경험하도록 준비했다.

## 실제 입력 증거

모든 좌표는 해당 캡처의 1728×972 클라이언트 좌표다. 시각은 KST.

| 시각 | 입력 | 좌표 | 기록 |
|---|---|---|---|
| 17:50:39 | move, 80ms | (970,545) | decision dca963d18e49408399a31830ebeb4534, input_sent |
| 17:51:38 | click, 80ms | (878,477) | decision fd23b42ccf8f4ba1980de951d0c5c028, input_sent |

이 두 입력 사이에 다른 포인터 입력은 없다. 클릭 직전 보존 화면에는 청록색 AI 포인터가 (970,545), 가운데 그림 오른쪽 테두리 부근에 남아 있고 설명은 없다.

- 캡처: `.robotomy/live/control/views/dfd340336030494699b8666562361723.png`
- 이동 전 view: `907eea3814a34313a34a044cbfae0599`
- 클릭 전 view: `dfd340336030494699b8666562361723`
- 원본 decision/receipt: `.robotomy/live/control/{decisions,receipts}/<decision-id>.json`

## 게임 코드와 직렬화 에셋 근거

대상은 private runtime의 Assembly-CSharp.dll, UnityEngine.UI.dll, StoryV2 scene `level6`이다. 기존 C# 디컴파일과 UnityPy 읽기 전용 파싱을 사용했다.

1. `CreatureSelectUnit.OnPointerEnter()`는 `OnEnter()`로 확대 애니메이션을 시작하고 `CreatureSelectUI.OnEnterUnit()`을 호출한다. 후자가 설명 문자열을 설정하고 설명창을 표시한다. 클릭은 필요 없다.
2. `OnPointerClick()` → `CreatureSelectUI.OnClickUnit()`은 선택을 확정하고 설명창을 숨긴다. 포인터가 처음 유효 영역에 들어오는 입력이 click이면, 진입 후 선택 확정 전 짧은 시간만 설명이 나타날 수 있다.
3. 가운데 `Door (1)`(GameObject path ID 421, RectTransform 3418)은 크기 250×400의 입력 영역이다. 루트 Image 5226의 raycastTarget은 true, 색상 alpha는 0이다. EventTrigger 5225에는 OnPointerEnter/Exit/Click 연결이 있다.
4. 하위 FrameControl은 879×1135, scale 0.5이다. 그 안의 장식 Image들과 ID Text는 raycastTarget=false다. 따라서 **보이는 상자 전체와 입력 사각형의 크기가 다르다.** Graphic의 직렬화 필드 순서(material, color, raycastTarget)는 실제 UnityEngine.UI.dll 디컴파일과 대조했다.
5. DoorRootCTRL의 `Exit_Normal` 애니메이션은 루트 scale을 약 0.833333으로 둔다. CanvasScaler의 기준 해상도는 1920×1080, 화면 크기 비례 모드다. 1728×972에서 정상 축척으로 계산한 가운데 입력 영역 오른쪽은 대략 x=958 부근이다. 부모 축척/실제 애니메이션을 포함한 정확한 런타임 경계는 미측정이지만, x=970의 이동과 x=878의 클릭은 각각 가장자리 바깥/중앙 안쪽이라는 설명에 부합한다.

## 가상 입력 경로 확인

- `mods/RobotomyObserver/VirtualInput.cs`: move와 click 모두 동일한 영구 pointer 위치를 갱신한다. Release는 키/버튼만 놓으며 위치를 초기화하지 않는다. 80ms는 포인터 수명이 아니다.
- UnityEngine.UI의 BaseInput을 포함한 Input 호출은 가상 상태로 교체하는 구조다.
- 실제 `StandaloneInputModule.ProcessMouseEvent()`는 클릭 여부와 관계없이 `ProcessMove()`를 호출한다. `PointerInputModule.ProcessMove()`가 진입/이탈 이벤트를 처리한다.
- 물리 마우스 위치와 AI 포인터 위치는 별개다.

## 실행 검증과 개선

- 1728×972 선택 화면에서 기존 `move (970,545)`는 설명이 없었고, 기존 `move (878,477)`는 가운데 상자를 확대하고 설명을 유지했다. 클릭하지 않았다.
- 증거: `.robotomy/live/verification/hover/original-edge-move.{png,json}` 및 `original-center-move.{png,json}`.
- 새 `hover_live_control`은 플레이어가 지정한 좌표로 한 번 이동한 뒤 짧게 기다려 새 화면을 돌려준다. 위치 자동 탐색·자동 클릭·숨겨진 설명 추출은 없다. 결과 `frame_returned`는 새 프레임 수신만 뜻한다.
- 실제 FastMCP 호출로 왼쪽과 오른쪽 상자의 hover 프레임 반환을 확인했다. `mcp-left`/`mcp-right` 증거에 텍스트 응답과 네이티브 image content가 함께 남았다. 왼쪽 호출은 약 1.25초였으며 기본 500ms 대기를 포함한다. 후반 게임 성능 보장은 아니다.
- 전체 단위 테스트 151개, main MCP 39개 도구 smoke, reload MCP 30개 도구 smoke 통과.
- 화면 중앙에서 hover를 시도하고 결과를 확인하라는 지침을 소스와 배포된 플레이어 AGENTS.md에 반영했다. 새 도구와 저장 모듈 변경 때문에 기존 MCP는 재연결이 필요하다.

## 플레이어 재경험 준비

- 원본 백업: `.robotomy/backups/hover-20261018T180321/private-save` (검증 전 10개 파일).
- 검사 후 진행 파일은 `after-hover-verification`에 별도 보관했다.
- 기본 세이브와 전역 세이브 및 각각의 backup 파일 4개를 검증 전 해시 그대로 복원했다.
- 기존 `etc170808.dat`/backup에 이미 선택된 대기 항목이 있으면 선택 화면을 건너뛰는 게임 로직이 있으므로, 두 파일만 `replay-selection-cache`로 보관했다. 바이너리 내용을 편집하거나 선택을 대신하지 않았다.
- Codex MSIX 경로 가상화와 독립 게임 프로세스의 실제 경로 차이를 확인했으므로, 물리 LocalLow 경로를 UNC로 접근해 복원·대조했다. 일반 경로 읽기도 일치하는지 확인했다.
- 재실행 후 Continue로 DAY 1 준비 화면까지 열었다. 관리시작은 누르지 않았다. 기존 운영자 입력 허용 상태를 유지했다.
- 이전 활성 시도는 운영자 개입 메모를 근거로 interrupted로 종료했다. 기존 발언과 기억은 보존했다. 다음 시도는 `operator_restore`로 기록하여 게임 내 새 회차 시작으로 세지 않는다.
- 재경험 후보 목록은 무작위 생성에 따라 최초 플레이와 달라질 수 있다.
