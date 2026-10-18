# 화면 관찰 판정과 이동 벡터의 파일 근거

2026-10-17 KST. 읽기 전용 정적 조사. 게임기 구현·게임 입력·저장 파일은 변경하지 않았다.
이 문서는 개발 자료이며 플레이어 경험 Vault에 넣지 않는다.

후속 구현(2026-10-18)은 [이동 벡터 구현·검증](motion-verification.md)에 있다.
아래의 ‘아직 미구현’은 이 정적 조사 당시 상태이며, 후속 실제 시험과 혼동하지 않는다.

## 결론

게임에는 관찰 기믹에 쓰는 전용 카메라 판정이 실제로 있다. 이를 화면 안 후보 선정에
재사용하면 범용 시각 추적보다 간단한 장치를 만들 수 있다. 다만 관찰 기믹의 판정과
최종 픽셀 가시성은 다르다. 내부 이동 능력치 또한 실제 화면 속도 벡터와 같지 않다.

권장 입력원은 게임의 최종 표시 Transform과 렌더 카메라다. 최종 표시가 허용된 대상에
대해 연속한 화면 위치의 차이를 시간으로 나눠 벡터를 제공한다. 픽셀 추적을 필수로
요구할 필요는 없다. 가림/효과 검증은 여전히 필요하다.

## 조사 대상 식별

- 원본 설치 `D:/SteamLibrary/steamapps/common/LobotomyCorp/LobotomyCorp_Data/Managed/Assembly-CSharp.dll`
  SHA256을 재확인: `fb31a592f29a6d8a08e3884cf21d94bc8bd167c9aeefc2eef81a774c70b294bd`.
- 기존 REA 근거를 조회해 동일 대상으로 확인:
  `ev_35afbc5c11602824c0664b2c8596eef4f02281d37c2db18f6eaeca9d5ff25736`.
  이 근거는 어셈블리 식별이며 메타데이터 예산 제한으로 partial이다. 메서드 실행 증거가 아니다.
- 보관된 디컴파일 `.robotomy/analysis/Assembly-CSharp.decompiled.cs` SHA256도 재확인:
  `3f5b8d807af9b2f416a0499455014ac601f62dcc121ca07cec88d20b39f828af`.
- 아래는 이 디컴파일의 메서드 본문에 근거한 정적 결론. 관찰 기믹을 실행해 시험하거나
  실제 px/s와 내부 값의 오차를 측정하지는 않았다.

## 관찰 판정의 종류

| 코드 | 하는 일 | 장치에서의 의미 |
|---|---|---|
| `CreatureCameraUtil.CheckCamera` | MainCamera를 Inspector.Check에 전달 | 관찰 기믹 공통 진입점 |
| `CreatureCameraUtil_Inspector.Check` | Sprite 크기·lossyScale로 만든 감지 사각형과 카메라의 위치·orthographicSize·aspect 사각형을 비교 | 카메라 영역과 감지 영역의 겹침 |
| `CheckIgnoreOrtho` | 카메라 중심점이 감지 사각형 안에 있는지 비교 | 확대 범위를 고려하지 않는 별도 기믹 기준 |
| `WorkerUnit.UpdateCheckInCamera` | 직원 x/y ±1.5 범위와 카메라 사각형 비교 | 표시 최적화용 대략적인 범위 검사 |
| `SpineOptimizerModule.UpdateCheckInCamera` | 위와 유사하나 카메라 영역에 여유6 추가 | 화면 밖도 포함하는 애니메이션 최적화 기준 |
| 여러 `CanRangeInCamera` | 카메라 중심과 대상의 거리 제곱을 상수와 비교 | 개별 근접 효과용이며 공통 가시성 기준 아님 |

실제 관찰 기믹 연결은 `LookAtMe.IsInCamera`와 `BloodyTree`의 작업/탈출 갱신 경로에서
확인했다. 게임은 해당 경로에서 카메라 상태를 검사한다. 외부 AI가 캡처를 요청하거나
이미지를 해석했는지를 검사하는 구조가 아니다. 개별 기믹의 수치·공략은 이 문서의 범위 밖이다.

`CreatureCameraUtil_Inspector.Check` 본문에는 UI 가림, 화면 후처리, 렌더러 활성·알파,
깊이/가시 픽셀 확인이 없다. 감지 사각형은 별도 센서일 수 있어 실제 스프라이트 윤곽과
동일하다고 가정할 수도 없다. 따라서 이 값만으로 `visible=true`를 플레이어에게 보내면 안 된다.

직원 코드에는 더 직접적인 반례가 있다. `WorkerUnit.UpdateViewPosition`은 문 edge에서
표시 위치의 z를100000으로 보낸 다음 `UpdateCheckInCamera`를 호출한다. 후자는 x/y만
검사하므로 이 표시 제어를 반영하지 못한다. 실제 문 이동 때의 픽셀은 별도 런타임 검증 대상이다.

근거: [공통 관찰 판정](../.robotomy/analysis/Assembly-CSharp.decompiled.cs:163790),
[감지 사각형 검사](../.robotomy/analysis/Assembly-CSharp.decompiled.cs:163877),
[별도 중심점 검사](../.robotomy/analysis/Assembly-CSharp.decompiled.cs:163893),
[기믹 호출](../.robotomy/analysis/Assembly-CSharp.decompiled.cs:135426),
[다른 기믹 호출](../.robotomy/analysis/Assembly-CSharp.decompiled.cs:115429),
[직원 표시와 범위 검사](../.robotomy/analysis/Assembly-CSharp.decompiled.cs:300961),
[애니메이션 최적화](../.robotomy/analysis/Assembly-CSharp.decompiled.cs:105515).

## 이동 능력치에서 화면까지

1. `AgentModel.movement`는 기본값·장비·버프·칭호·부서·패닉 등의 보정을 받은 능력치다.
2. `GetMovementValue`는 이를 `4 + 연구 보너스 + movement/25`로 변환한다.
3. 이동 갱신은 기절·halt·무기 지연·이동 지연이면 정지할 수 있다. 실제 이동 인자에는
   `movementMul`과 버프 배율이 추가된다.
4. `ProcessMoveNode`는 `Time.deltaTime * GameToUnity(movement) * currentScale`을 사용한다.
   경로 edge 비용과 진행률을 거쳐 좌표가 계산된다. 닫힌 문·노드와 엘리베이터 대기도 존재한다.
5. `WorkerUnit.UpdateViewPosition`은 표시 중지, recoil, 별도 표시 위치와 z를 반영한다.
6. 카메라 이동·줌·회전·recoil이 투영 결과를 바꾼다. 게임 배속/일시정지도 현실 시간당 이동량을 바꾼다.

따라서 능력치가 같은 순간에도 표시 속도는0이거나 달라질 수 있고, 능력치에는 방향이 없다.
내부 이동속도에 좌우 방향만 곱해도 전체 화면 속도 벡터가 되지 않는다.

근거: [이동 처리와 변환](../.robotomy/analysis/Assembly-CSharp.decompiled.cs:189729),
[시간·단위·크기 반영](../.robotomy/analysis/Assembly-CSharp.decompiled.cs:103819),
[경로 진행](../.robotomy/analysis/Assembly-CSharp.decompiled.cs:104007),
[문·엘리베이터](../.robotomy/analysis/Assembly-CSharp.decompiled.cs:103952),
[카메라 변경](../.robotomy/analysis/Assembly-CSharp.decompiled.cs:102998),
[시간 배속](../.robotomy/analysis/Assembly-CSharp.decompiled.cs:179978),
[게임 단위 변환](../.robotomy/analysis/Assembly-CSharp.decompiled.cs:316719).

## 수정할 설계 방향 — 아직 미구현

`렌더 객체 참조 → 화면 안 후보 → 표시/가림 검증 → 최종 표시 Transform 투영 → 벡터 계산`

`v_screen = (screen_position_now - screen_position_previous) / elapsed_real_seconds`

- 카메라 LateUpdate가 끝난 표시 시점에서 수집한다. 원래 게임 기믹의 카메라 판정은 변경하지 않는다.
- 벡터는 px/s 또는 화면 크기 대비 단위/s로 전달한다. 픽셀 수준으로 정밀도를 제한할 수 있다.
- 화면 속도는 카메라 이동을 포함한다. 카메라 보정 이동은 별도 값으로 구분한다.
- 대상이 두 표본 모두 보였을 때만 속도를 제공한다. 처음 등장/가림/화면 이탈/불연속 전환은
  `unknown` 또는 `discontinuity`로 기록한다. 가려진 구간을0속도라고 표현하지 않는다.
- 내부 객체 참조는 장치의 추적에 활용할 수 있지만 플레이어에는 임시 트랙ID만 준다.
  숨은 개체의 식별·경로·목적지·미공개 상태를 대신 알려주지 않는다.
- 미검증 왜곡/가림 효과 중에는 벡터 제공을 보류한다. 전후 화면과 일치하는지 별도 검증한다.
- 다음 검증 장면: 로비 배회, 작업 명령 후 이동/정지, 줌·카메라 이동, 일시정지·배속,
  문·엘리베이터 통과, 다른 창 가림, 화면 이탈/재등장. 같은 시각의 실제 픽셀 변위와 대조한다.

파일 접근 제한과 관측 계약은 별개다. 완성된 플레이어에 게임기 API만 주는 구성은 가능하지만,
현재 개발 Codex는 원래 파일을 읽을 수 있다. 복사본 저장 분리는 OS 접근 격리가 아니다.
파일을 차단하더라도 API가 미공개 값을 내보내면 그 값은 플레이어에게 전달된다.
내부 데이터를 사용하는 것 자체를 금지할 이유는 없으며, 무엇을 어떤 조건·정밀도로
내보낼지를 장치 계약으로 정하는 것이 핵심이다.
