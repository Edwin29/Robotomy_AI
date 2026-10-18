# 로보토미 게임 파일과 설계 적합성 점검

점검일: 2026-10-17 KST. 범위: 실행 파일·관리 어셈블리·직렬화된 씬의 읽기 전용 정적 분석. 게임 입력, 게임 재실행, 게임 코드 패치, 모델 실험은 수행하지 않았다.

**기존 설계의 역할 분리는 유지할 수 있지만, 구현 방식은 로보토미 전용 UI 참조와 표시 제어를 활용해 더 단순하게 만들 수 있다.** 이전 문서는 일부 입력·렌더링·소리 경로 확인을 바탕으로 한 일반 설계였다. 최종 표시 추출·후처리·실시간 성능을 게임 전체에서 검증한 설계는 아니었다.

이번 점검은 [게임기 설계](ai-console-design.md)의 구현 우선순위를 구체화한다. 결론은 정적 구조에 대한 것이며, 실제 화면과의 일치·지연 수치는 별도 수용 시험이 필요하다.

## 질문별 결론

| 질문 | 결과 | 판단 |
| --- | --- | --- |
| 게임 안에 직접 연결할 수 있는가 | 기존 BaseMod/Harmony 경로와 관리 C# 코드가 있음 | 현재 방식 유지 |
| OCR 없이 표시 값을 읽을 수 있는가 | 대표 UI에 창 참조와 최종 Text/Image 필드가 있음 | 좁은 전용 어댑터가 적합 |
| 활성 Text만 읽으면 되는가 | 직원 HUD와 환상체 창에 별도 덮개가 있음 | 현재 범용 검사는 부족 |
| 최종 표시를 한 관리자에서 얻을 수 있는가 | 여러 창 관리자·UIController·이벤트 버스가 분담 | 단일 관리자 가정은 기각 |
| 모든 소리가 한 매니저를 지나는가 | AudioSource 호출이 여러 클래스에 분산 | 출력 호출 계층과 상태 재확인 필요 |
| 입력을 한 게임 함수로 줄일 수 있는가 | Unity Input 사용이 분산됨 | 기존 게임 내부 가상 입력 방식 유지 |
| 최신 Unity 영상 최적화를 그대로 쓸 수 있는가 | Unity 2017.4.7f1, 현재 관리 DLL에서 AsyncGPUReadback 타입 미발견 | 지원 API와 실측부터 확인 |
| 영상·기억·모델 비교 목표가 검증됐는가 | 파일 구조만으로 처리 속도와 판단 품질을 증명할 수 없음 | 실험 전 상태 유지 |

## 대상과 증거 식별

원본 설치와 분리 실행본의 `Assembly-CSharp.dll` SHA-256은 모두 `fb31a592f29a6d8a08e3884cf21d94bc8bd167c9aeefc2eef81a774c70b294bd`로 일치했다. 관리 어셈블리 MVID는 `103aee0d-61e4-4daa-a9c0-54ffd10e51a9`다. 설치 전체가 무수정 배포본이라는 뜻은 아니며, 이 빌드의 게임 어셈블리를 조사 대상으로 고정했다는 뜻이다.

| 증거 | 식별과 범위 |
| --- | --- |
| REA 게임 어셈블리 식별 | `ev_35afbc5c11602824c0664b2c8596eef4f02281d37c2db18f6eaeca9d5ff25736` |
| REA 제한 | CLI PE 식별은 관측됨. 64MiB 메타데이터 표현 예산 때문에 전체 메타데이터 결과는 partial. 이것만으로 아래 메서드 동작을 입증하지 않음 |
| 재사용한 C# 디컴파일 | `.robotomy/analysis/Assembly-CSharp.decompiled.cs`, SHA-256 `3f5b8d807af9b2f416a0499455014ac601f62dcc121ca07cec88d20b39f828af` |
| 관리 IL과 타입 검사 | 기존 dnfile/dncil로 파일 메타데이터·메서드 본문을 정적으로 읽음. CLR에 게임 코드를 적재·실행하지 않음 |
| 씬·설정 검사 | 기존 UnityPy 1.25.4, `globalgamemanagers`, `globalgamemanagers.assets`, `level2`, `level11`~`level13` |
| 씬 근거 목록 | [로컬 JSON](../.robotomy/analysis/console-compatibility-20261017.json). 파일 해시, 객체 수, Canvas·Camera·Mask 연결 보존. Git 제외 |
| 캡처 모듈 REA | `ev_e8de10304007cbc5dc8a958bf9adb6551206b28fe173a46012eebc8fb1e736b9`, `UnityEngine.ScreenCaptureModule.dll`, SHA-256 `8cd9fa41e26eaa65ec69f0408bd648f7c273683c76fc36c7802eb53b3d5665f2`, metadata complete |

이하 코드 줄 번호는 위 디컴파일 파일 기준이다. 디컴파일은 원본 소스가 아니라 정적 재구성이다. 씬의 MonoBehaviour는 일부 사용자 필드 타입 정보가 부족해 전체 읽기가 실패했다. 이후 공통 헤더의 GameObject·MonoScript 참조만 읽어 타입과 계층을 연결했으며, 사용자 필드를 완전 해석한 것으로 간주하지 않았다. 텍스처·음원·스토리 원문은 내보내지 않았다.

## 씬 구조에서 확인한 제약

BuildSettings의 씬 목록에서 `level2`는 Main, `level11`~`level13`은 각 튜토리얼이다. 이 파일들의 엔진 버전은 Unity 2017.4.7f1이다.

| 직렬화된 구성 | Main | 튜토리얼 1·2·3 각각 |
| --- | --- | --- |
| Camera | 3 | 3 |
| Canvas | 40 | 94 |
| Canvas 모드 | Overlay 19, Camera 16, World 5 | Overlay 67, Camera 18, World 9 |

이 수는 비활성·내장 객체를 포함하며 현재 실행 중 활성 인스턴스 수가 아니다. Main에서는 Text 2,425개, Image 6,598개, Mask 79개, RectMask2D 2개, ScrollRect 35개, UIController 22개가 직렬화된 참조로 식별되었다. 따라서 전체 Text 검색을 단순히 20Hz로 올리기보다 알려진 패널을 캐시하는 방식을 먼저 측정할 근거가 있다. 이 개수만으로 실제 검색 비용을 단정하지 않는다.

Main에는 `MainCamera`, `UICam`, `MainCamera/SefiraBossUICamera`가 있다. 초기 culling mask는 서로 다르며, 직원 창·환상체 창·상태 HUD의 Canvas는 UICam을 참조한다. 여러 Overlay Canvas는 별도 카메라 없이 그려진다. 초기 Camera depth는 모두 0이어서 파일 값만으로 실제 합성 순서를 확정하지 않는다.

MainCamera에는 활성 Glow·RgbClamp 컴포넌트가, UICam에는 비활성 TV 필터 컴포넌트가 직렬화되어 있다. **효과 컴포넌트가 하나라도 있으면 모든 정보가 가려졌다고 처리하는 방식도 맞지 않는다.** 알려진 기본 효과와 가독성에 영향을 주는 경로를 구별하고, 동적으로 바뀌는 효과와 카메라 연결은 런타임에서 검증해야 한다. 효과의 게임 내 원인·이름은 플레이어에게 제공하지 않는다.

환상체 설명 영역 `.../CreatureInfoArea/DescriptionArea/ListArea`에는 Mask와 ScrollRect가 함께 있다. 상태 로그와 직원 창에도 마스크·스크롤이 있다. 설명 문자열 목록 전체를 반환하면 화면 밖 내용을 전달할 수 있다는 우려가 실제 씬 구조로 뒷받침된다.

## UI 추출은 세 경로부터 시작

### 에너지와 시간 패널

`GameStatusUI.Window.energyContorller`에 직접 접근하는 좁은 경로가 있다. 표시 활성화도 해당 패널의 ActiveControl로 관리한다. [클래스와 활성화 경로](../.robotomy/analysis/Assembly-CSharp.decompiled.cs:293229)

`EnergyController.Update`는 내부 값을 Image의 fillAmount와 **정수 표시 문자열**로 바꾼다. `CheckGameStatus`는 시간 표시를 분·초 문자열로 만들고 특정 범위에서는 표시를 제한한다. 내부 값을 새로 계산하는 것보다 완료된 `InnerText`와 `PlayTime`을 읽는 것이 화면 표현에 가깝다. [표시 갱신](../.robotomy/analysis/Assembly-CSharp.decompiled.cs:292716), [시간 문자열](../.robotomy/analysis/Assembly-CSharp.decompiled.cs:292816)

첫 어댑터는 이 패널 참조를 캐시하고 UI 갱신 뒤 최종 표시 필드·활성 상태·앞쪽 가림을 함께 검사한다. 전역 오브젝트 스캔이나 OCR가 필요하지 않은 대표 경로다.

### 직원 창과 머리 위 HUD

`AgentInfoWindow.currentWindow`는 배치용·진행용 표시 branch를 전환한다. `SetData/SetUI` 뒤 실제 활성 branch를 읽으면 표시용 보정·리치텍스트와 `???` 같은 감춤 표현을 그대로 유지할 수 있다. [창 생성](../.robotomy/analysis/Assembly-CSharp.decompiled.cs:272025), [표시 변환](../.robotomy/analysis/Assembly-CSharp.decompiled.cs:271634)

직원 머리 위 `AgentUI.SetActive`는 본체를 끄는 대신 `BlackHide` 덮개를 켜고 끈다. 아래 막대는 계속 갱신될 수 있다. 따라서 active/alpha 검사만 통과한 HpFill·MentalFill을 보내면 안 된다. [덮개 제어](../.robotomy/analysis/Assembly-CSharp.decompiled.cs:266799), [갱신과 fillAmount](../.robotomy/analysis/Assembly-CSharp.decompiled.cs:266842)

AgentUI 인스턴스 등록·캐시 + BlackHide 검사 + 카메라/화면 영역 검사를 사용하고 막대의 정밀도를 화면 픽셀에 맞춘다. 개발자가 내부 HP를 읽어 다시 막대처럼 가공하는 우회 경로는 사용하지 않는다.

### 환상체 정보 창

`CreatureInfoWindow.CurrentWindow`에는 영역별 root와 설명 목록 `descList`가 있다. 하지만 `CreatureInfoStatRoot.Initialize`는 잠긴 상태에도 문자열·그림을 채우고 별도 `CreatureInfoOpenArea`가 앞을 덮는다. `SetEnabled/SetDisabled`라는 이름만 보고 공개 상태를 판단할 수도 없다. 조사한 구현에서 이 메서드 본문은 비어 있고, 실제 덮개는 다른 객체가 관리한다. [값 작성](../.robotomy/analysis/Assembly-CSharp.decompiled.cs:290387), [덮개](../.robotomy/analysis/Assembly-CSharp.decompiled.cs:290198), [빈 메서드](../.robotomy/analysis/Assembly-CSharp.decompiled.cs:290544)

`SetDesc`는 공개 단계에 맞춰 문자열 목록을 구성하므로 좋은 후보지만, 활성 탭과 실제 Mask/ScrollRect 안에 보이는 범위까지 확인해야 한다. 전체 목록을 자동으로 읽으면 안 된다. [설명 목록](../.robotomy/analysis/Assembly-CSharp.decompiled.cs:291056)

## 공통 기능은 가시성 증명보다 변경 감지에 사용

`UIActivateManager`는 위치별 활성 창을 관리하지만, 배경 클릭 시 직원·환상체 창을 별도로 닫는 코드도 있다. 전체 UI를 한 목록으로 제공하는 최종 화면 관리자는 아니다. [등록과 닫기](../.robotomy/analysis/Assembly-CSharp.decompiled.cs:287412)

`UIController`의 Hide 요청과 실제 숨김 완료는 다를 수 있다. UI 애니메이션 종료 후 프레임 종료에 OnShow/OnHide를 보내는 경로가 있으므로, 요청 시점에 곧바로 보임/숨김을 확정하면 전환 중 표시를 오판할 수 있다. [표시 제어](../.robotomy/analysis/Assembly-CSharp.decompiled.cs:344648), [완료 알림](../.robotomy/analysis/Assembly-CSharp.decompiled.cs:344799)

공통 `Notice` 이벤트 버스, UIController 알림, Unity UI의 GraphicRegistry·dirty callback을 변경 감지 후보로 사용할 수 있다. 현재 배포된 UnityEngine.UI.dll에 `GraphicRegistry.GetGraphicsForCanvas`와 `Graphic.RegisterDirtyVerticesCallback`이 실제 존재함을 메타데이터로 확인했다. 그러나 dirty callback이 모든 가림·상위 transform·후처리 변화를 알리는 것은 아니다. [Notice 송신](../.robotomy/analysis/Assembly-CSharp.decompiled.cs:105378)

첫 구현은 패널 참조 캐시와 제한된 주기 검사로 시작하는 편이 간단하다. hook과 dirty 알림은 비용·철회 지연 측정 후 추가한다. 이벤트 인자와 게임 모델 데이터는 플레이어 관측으로 전달하지 않는다.

## 소리는 공통 호출 계층에서 수집

SoundEffectPlayer의 여러 생성 경로는 공통 함수로 모이지만, UI·BGM·개별 클래스가 AudioSource를 직접 사용하는 경로도 있다. Assembly-CSharp.dll의 관리 IL에서 확인한 호출 지점은 다음과 같다. 이 숫자는 실행 횟수가 아니다.

| AudioSource 호출 | 정적 호출 지점 |
| --- | --- |
| Play | 11 |
| PlayOneShot | 33 |
| Stop | 31 |
| Pause | 9 |
| UnPause | 9 |

위 제어 호출은 39개 타입에 분산된다. SoundEffectPlayer·BgmManager·GlobalAudioManager만 제외해도 36개 타입이 남는다. 따라서 단일 매니저 hook으로 소리 전체를 관찰한다는 안은 부족하다.

집계 방법은 dnfile의 TypeDef/MethodList에서 RVA가 있는 본문을 dncil로 읽고, `call/callvirt`의 MemberRef 대상이 `UnityEngine.AudioSource/Input/AudioListener`인 지점을 세는 방식이다. 메서드별 최대 100,000바이트 읽기 범위에서 본문 파싱 예외는 0건이었다. 같은 이름의 오버로드는 합산했으며 타입 수는 namespace를 제외한 TypeName 기준이다. MethodSpec·reflection·native·다른 assembly의 경로는 집계하지 않았다. 이 집계는 별도 정적 판독 결과이며 REA 어셈블리 식별 Evidence의 직접 출력은 아니다.

구체적인 함정도 있다. GlobalAudioManager는 AudioSource 세 개의 풀에서 빈 소스가 없으면 상위 재생 요청을 실제 재생하지 않는다. 상위 요청만 기록하면 들리지 않은 소리를 생성하게 된다. SoundEffectPlayer의 Stop은 AudioSource.Stop 대신 오브젝트 파괴를 사용하며, 자연 종료·연속 재생도 Update에서 처리한다. [풀과 재생](../.robotomy/analysis/Assembly-CSharp.decompiled.cs:182079), [수명과 종료](../.robotomy/analysis/Assembly-CSharp.decompiled.cs:176091), [중지](../.robotomy/analysis/Assembly-CSharp.decompiled.cs:176200)

추천안은 현재 가상 Input 치환과 유사하게 **관리 코드의 AudioSource 호출 지점을 원래 호출을 유지하는 공통 관찰 wrapper로 연결**하는 것이다. PlayOneShot의 clip 인자를 읽고, source와 재생 인스턴스를 분리한다. 상태 registry를 주기적으로 재확인해 자연 종료·pause·파괴·장면 전환을 조정한다.

이 경로도 최종 음향 신호를 보증하지 않는다. 초기 계약은 `playback_state_approximation`으로 유지한다. prefab playOnAwake, 다른 어셈블리·네이티브 경유 재생, one-shot 중첩의 개별 종료는 잔여 확인 사항이다. 의미 있는 자산 이름은 익명 토큰으로 바꾸고 공개하지 않는다.

## 입력과 영상

관리 IL에서 UnityEngine.Input 호출은 58개 타입·176개 지점에 분산되어 있다. UnitMouseEventManager는 유닛 포인터 영역의 연결점이지 카메라·시간 UI·메뉴 입력 전체의 관리자라고 볼 수 없다. 기존 game-local 가상 Input 상태를 확장하는 방향이 더 일관된다. [유닛 포인터 처리](../.robotomy/analysis/Assembly-CSharp.decompiled.cs:315797)

영상은 최종 합성 뒤에 받아야 한다. 다중 카메라와 Overlay Canvas가 있으므로 MainCamera의 OnRenderImage 한 지점만 캡처하면 전체 화면이 아닐 수 있다. 실제 왜곡은 OnRenderImage의 Graphics.Blit 재질 경로로 구현되어 있어 원문 Text와 출력 픽셀이 달라질 수 있다. [이미지 효과 경로](../.robotomy/analysis/Assembly-CSharp.decompiled.cs:66477)

설치된 52개 `UnityEngine*.dll`의 TypeDef를 검사한 결과 AsyncGPUReadback·AsyncGPUReadbackRequest 타입은 발견되지 않았다. `UnityEngine.ScreenCaptureModule.dll`에는 CaptureScreenshot과 CaptureScreenshotAsTexture가 존재한다. 따라서 최신 API를 전제로 한 비동기 readback 설계는 이 빌드의 기본안이 될 수 없다. 이는 조사한 관리 API 범위의 결론이며 가능한 모든 네이티브 캡처 방식을 부정하지 않는다.

기존 WaitForEndOfFrame/ReadPixels와 배포된 CaptureScreenshotAsTexture 경로를 후보로 두고, 같은 화면이 잡히는지와 할당·GPU 동기화·게임 프레임 영향을 먼저 측정한다. 연속 PNG 압축·디스크 쓰기를 빠른 경로에서 줄이는 것이 우선 최적화 후보다. 15/30fps, 영상 인코더·공유 메모리·외부 캡처의 필요성은 그 결과로 정한다.

## 설계 수정안과 다음 검증

1. **범용 UI 해석기보다 전용 어댑터 우선:** 에너지·직원·환상체 세 경로와 기존 창 참조를 사용한다. UI 스캔 주기부터 높이지 않는다.
2. **가림 계약을 게임에 맞게 명시:** BlackHide·OpenArea·활성 branch·Mask/ScrollRect·표시 애니메이션·카메라 경로를 검증한다. 내부 공개 플래그만으로 최종 화면을 대체하지 않는다.
3. **이벤트 인프라의 역할 축소:** Notice·UIController·Graphic dirty는 재검사 신호로만 사용하고, 전체 상태 원장으로 쓰지 않는다.
4. **오디오는 매니저 한 개가 아닌 출력 호출 계층:** manager로 초기 경로를 확인하되 전체 커버리지는 IL callsite와 registry로 관리한다.
5. **Unity 버전에 맞춘 영상 경로:** 지원되는 동기 캡처의 실제 비용을 먼저 재고 최신 Unity API·고속 인코더를 선결 조건으로 두지 않는다.
6. **모델 비교보다 관측 품질 먼저:** 위 표시 어댑터에서 확보한 관측으로 Open-Jev/AnyJev를 비교한다. 구조 오류를 모델의 판단 오류로 평가하지 않는다.

정적으로 답한 것은 파일 구조와 연결 후보다. 아직 답하지 못한 것은 덮개/스크롤 전환 중 실제 가시성, 동적으로 추가되는 후처리, 커서 포함 최종 캡처의 일치, 실제 오디오 출력과 이벤트의 차이, 15/30fps 비용, 본편 부하에서의 반응 시간이다. 다음 단계는 새 기능을 대량 구현하는 것이 아니라 대표 UI별 화면 대조와 작은 캡처·관측 비용 측정으로 이 항목들을 좁히는 것이다.
