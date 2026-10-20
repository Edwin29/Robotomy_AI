# 표시 누락 원인 조사 — 2026-10-19

결론: 이번 주요 누락은 게임이 어려워서 생긴 불가피한 문제가 아니다. 게임 코드 일부를 읽은 뒤 일반적인 Unity 구성과 과도하게 강한 가시성 조건을 가정한 구현 오류다. 실제 scene 에셋의 연결·선택 애니메이션과 렌더 부품 구성을 충분히 확인하지 않은 것이 공통 원인이다.

운영 코드/실행 모듈은 수정하거나 재배포하지 않았다. 독립 검증본에만 일회성 진단을 추가하고 재시작해 같은 본편 6일차 UI를 다시 열었다. 실제 게임 입력은 검증본 PID 39516에만 보냈다. 기존 게임 PID 10260 유지, 녹화 제어 미사용, 기존 세이브 6개 해시 일치 및 설치 원본 29개/설정/메타데이터 무결성 통과. 검증본은 게임 일시정지 및 운영자 입력 차단으로 마쳤다.

## 근거와 조사 방법

- 검증 DLL SHA-256: `fb31a592f29a6d8a08e3884cf21d94bc8bd167c9aeefc2eef81a774c70b294bd`.
- REA `inspect_managed_artifact`: `ev_dc3cb50762cb5198e48d5fd2d396179f11e9d9c14743a57672c898939b2337a4`. 파일 식별만 사용. 메타데이터는 도구의 표현 예산 제한으로 부분 결과이며, 메서드 동작을 이 결과로 입증하지 않는다.
- 기존 게임 디컴파일과, 현재 검증 DLL에서 다시 추출한 `UnityEngine.UI.Selectable`, `Image`, `MaskableGraphic`, `Spine.Unity.Modules.SkeletonRenderSeparator`, `SkeletonPartsRenderer` 대조.
- `globalgamemanagers`의 BuildSettings에서 Main이 level2임을 확인하고, level2의 PlaySpeedSettingUI/ManagementSlot 연결을 읽었다. stripped MonoBehaviour의 일부 필드는 해당 클래스의 직렬화 순서에 맞춰 파싱했다. 게임 에셋에는 쓰지 않았다.
- 실행 중 일회성 진단은 실제 UI 경로, 그래픽 색, 깊이, 게임기가 계산한 사각형, Spine 렌더 부품의 화면 좌표를 읽는다. 게임 모델의 숨은 값을 플레이어에게 제공하는 기능은 추가하지 않았다.
- 재현 스크립트: `D:/Projects/Robotomy_Lab/audit_display_assets.py`.
- 증거 폴더: `D:/Projects/Robotomy_Lab/.robotomy/verification/root-cause/`.

## 1. 배속 상태와 입력 대상: 실제로는 Animation 버튼

게임 `PlaySpeedSettingUI.UpdateButton`은 선택 버튼의 interactable을 false로 바꾼다. 이 부분을 읽은 것까지는 맞았다. 하지만 게임기 `ConsoleUI.CapturePlayback`은 이후 `transition == ColorTint` 및 `targetGraphic`의 disabledColor를 요구했다.

Main scene의 네 버튼 모두 실제 transition 값은 **3 = Animation**이다. targetGraphic은 RGBA(1,1,0.631,0), 즉 투명하다. 별도 `PlaySpeedButtonAnimCTRL`이 자식 그래픽을 표시한다. 실행 중 Pause/InnerFill은 RGBA(1,0.580,0.255,1), Pause/Icon은 검정 불투명으로 확인했다. 입력용 부모와 보이는 자식이 별개다.

따라서:

1. CapturePlayback은 ColorTint 조건에서 확정적으로 탈락한다.
2. CaptureInputTargets는 투명한 targetGraphic을 Visible에 보내므로 inactive_or_faded로 탈락한다.
3. 같은 원인이 ‘메뉴가 닫힌 뒤에도 남아 있는 배속 버튼을 예약 입력 대상으로 이어 사용’하는 기능을 막는다.

`pauseImage`, `speed1Image`, `speed2Image`, `speed3Image` 필드는 이 scene에서 모두 null이다. 필드 이름만 보고 이것으로 대체하는 것 역시 틀린 수정이다.

수정 방향: 실제 선택 애니메이션이 바꾸는 자식 그래픽의 최종 표시와 버튼 연결을 읽고, 클릭 가능성은 실제 raycast/이벤트 수신자로 확인한다. 표시 대상과 입력 대상을 동일 객체라고 가정하지 않는다. 게임 속도 내부 값으로 대체하지 않는다.

근거: `resolved-ui.json`, `speed-animator.json`, `*-clip.json`, `runtime-display-audit.json`; 검증본 `ConsoleUI.cs:223` 및 `:243`.

## 2. HP 누락: 0.5픽셀 여백이 만든 약 0.06픽셀 겹침

게임 `CommandWindow.AgentSlot.UpdateUI`는 HealthText와 MentalText를 별도로 갱신한다. 실제 화면에 두 값 모두 표시되며, 게임기의 SP 전송도 정상이다.

실행 진단에서 에덴 HP 사각형은 y=516.81, 높이=9.00; SP 막대는 y=508.20, 높이=8.67이었다. 좌표는 화면 아래를 원점으로 한다. SP 막대 위끝 약 516.87이 HP 판정 경계 516.81과 **약 0.06픽셀** 겹친다. SP 그래픽 depth=76, HP depth=74이므로 front_graphic으로 HP 전체가 탈락한다. 빅토르 행에도 동일한 관계가 재현됐다.

그런데 HP 경계에는 게임기 `GraphicRect`가 글자 생성 좌표 바깥으로 붙인 0.5픽셀 여백이 포함된다. 이 여백을 제외한 원래 계산 글자 경계는 약 517.31로, SP 막대와 약 0.44픽셀 떨어져 있다. 즉 이 표본은 게임기가 붙인 여백 때문에 정상 글자를 가려졌다고 판단한 경우다. 화면 가림 기믹이나 HP 해금 제한이 아니다.

이전 조사에서 제시한 ‘투명 이미지의 큰 사각형’은 일반적인 구조 문제지만, 이 HP 표본의 직접 원인은 그것이 아니다. MentalFill은 실제 불투명 square32/Filled 이미지이고, 글자 경계 확대와 any-overlap 거절 조합이 직접 원인이다.

수정 방향: 입력·검색용 여유 사각형과 실제 표시 가림 판단용 기하를 분리한다. 글자의 실제 생성 메시/픽셀 정렬과 이미지의 실제 채움 영역을 반영한다. 모든 겹침을 허용하거나 HP/SP 인접 요소를 무조건 무시하는 방식은 쓰지 않는다.

근거: `runtime-display-audit.json`, `resolved-ui.json`; 검증본 `ConsoleUI.cs:90`의 경계 확장과 `:136` 이후 겹침 판정.

## 3. 본편 벡터: 캐릭터 전체와 작은 렌더 부품을 혼동

게임의 SkeletonRenderSeparator는 한 사람을 몸통·머리·입·눈·눈썹 등 여러 SkeletonPartsRenderer로 나눈다. 사용하지 않는 부품은 ClearMesh하고, 표시되는 각 부분에는 별도 메시가 들어간다. 이 구조는 실제 DLL의 HandleRender/RenderParts에서 확인했다.

실행 중 아스터로이드의 몸체 범위는 약 13×27픽셀이지만 입 `4_Mouth`는 (693.2,275.4)~(694.8,277.0), 약 1.6×1.6픽셀이다. 에덴·빅토르의 입도 같은 크기다. 이 부품은 active=true, visible=true이고 실제 정점 4개를 가진다. 사무직의 `7` 부품은 약 0.9×0.9픽셀인 표본이 있다.

게임기의 ProjectBounds는 각 부품이 가로·세로 2픽셀 이상이어야 통과한다. Surface는 **부품 하나라도 실패하면 캐릭터 전체를 즉시 거절**한다. 그래서 몸통이 충분히 보이는데 입/눈썹 때문에 벡터가 전부 사라진다. 화면 경계에서도 같은 구조가 부분 노출된 개체 전체를 거절할 수 있다.

수정 방향: 개체 단위로 후보를 묶되, 가시성 증거는 실제 보이는 몸체 부분에서 찾는다. 표시 기여가 없거나 작은 부품의 탈락을 전체 개체의 비가시성으로 확대하지 않는다. 가려진 부분에서 좌표를 가져와 대신 공개하지 않으며, 실제 보이는 표면과 안정적인 추적 기준의 관계를 검증한다.

근거: `SkeletonRenderSeparator.cs`, `SkeletonPartsRenderer.cs`, `runtime-display-audit.json`; 검증본 `ConsoleMotion.cs:56`, `:202`, `:215`.

## 4. 본편 효과 계약도 실제 설정과 불일치

게임기 MotionRenderPolicy는 glow의 기본 클래스 초기값(Threshold .5, Intensity 2.25, Precision .56)을 정상 조건으로 사용했다. 게임 코드와 실제 Main의 설정은 Threshold=1, Intensity=3, Precision=1이다. 따라서 기본 정상 화면도 처음에는 profile_unverified였다. 검증본에서 그 실제 프로필을 승인한 뒤에도 위 부품 오류가 남았다. scene allowlist를 없애는 것만으로 본편 지원이 되는 것은 아니다.

환상체의 추가 실패인 surface_patch_edge/surface_texture_alpha는 별도 남은 조사 항목이다. 현재 알고리즘은 2×2 화면 패치 전체가 한 삼각형 내부이고 확대된 텍스처 표본 전체의 알파가 255여야 한다. 이는 ‘개체가 화면에 보인다’보다 훨씬 강한 조건이다. 이번 조사로 그 조건이 존재함은 확인했지만, 각 환상체의 어떤 메시/픽셀이 실패했는지까지는 확정하지 않았다. 직원 수정만으로 모든 환상체가 해결된다고 주장하지 않는다.

## 왜 테스트가 통과했나

전송 테스트는 HP/SP가 이미 추출되어 있다는 가상의 JSON으로 시작한다. 알파 검사는 인공 배열, 렌더 계약 검사는 구현이 가정한 효과값을 검증한다. 실제 Animation 버튼, 투명 클릭 부모, 좁은 인접 HP/SP 배치, 2픽셀 미만 Spine 부품을 포함하지 않았다. 정보 누출을 막는 테스트에 비해 **보이는 정보가 빠짐없이 전달되는지 확인하는 테스트**가 부족했다.

앞으로 기능마다 게임 코드 → 직렬화된 참조/애니메이션/재질 → 실행 중 최종 표시를 먼저 확인한다. 입증하지 못한 연결은 기록하고 추정으로 구현하지 않는다. 가시 정보의 정상 전달과 실제 가림 시 차단을 함께 수용 기준으로 삼는다. 이 원칙을 프로젝트 AGENTS.md에도 반영했다.

이번 단계는 원인 조사이며 수정 완료 보고가 아니다. 프레임 세대 불일치와 일부 환상체 표면 판정은 별도 미확정 항목으로 남긴다.
