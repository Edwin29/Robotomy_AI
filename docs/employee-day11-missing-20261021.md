# 11일차 직원 목록 누락 재현

본게임 PID30456, 11일차0/170 일시정지 화면에 직원이 존재하나 producer motion에 직원 트랙 없음. 전체 관찰/diff 전달 이전의 문제.

검증용에 11일차 세이브6개를 baseline으로 보관했다. 외부 파일 복사만으로 이전6일차를 읽는 현상이 있어 검증 전용 런타임에서 baseline 바이트를 persistentDataPath에 기록한 뒤 실제 교육팀과 직원7명이 로드됨을 확인했다. .robotomy/backups/day11-baseline-20261021 (Lab) 참조.

11일차1280x720에서도 직원7명 모두 UnitUI.Name 및 AgentUI.Name이 isActiveAndEnabled=false여서 inactive_or_faded로 거절됐다. 이름 텍스트 alpha1, renderer alpha1, cull=false, canvas active=true. 따라서 해상도만의 문제가 아니며 두 이름 참조를 추가한 이전 패치도 실제 활성 표시 대체 경로를 다루지 못했다. 텍스처 가장자리 실패는 이름 앵커 실패 뒤의 대체 경로에서 발생한다. 이름 비활성의 enabled/계층 구분과 화면에 실제 그려지는 대체 표시의 연결은 아직 확인되지 않았다.

본게임 입력/재시작/패치 없음. 검증 게임 종료 후 진단 없는 DLL 복구. 증거: .robotomy/player-feedback-work/evidence/employee-day11-label-probe.txt.


## 원인 확인과 수정

- 실제 11일차 직원 7명의 `Name`에는 `Optimization.AutoUIHider`가 붙어 있다. 게임 코드의 `OnChangeCameraSize`는 카메라 크기가 직렬화된 `_hidePoint` 이상이면 `targetGraphic.enabled=false`로 이름만 숨긴다. 대체 렌더러로 이름을 그리는 방식이 아니다.
- `AgentUnitUI.activateUI`는 `title`을 별도로 표시한다. 실제 런타임의 `TitleRoot/Text`는 7명 모두 enabled/active이며 화면에 그려진다. 이름 두 참조는 같은 표시를 가리켜 기존 fallback은 효과가 없었다.
- 이름표 또는 실제로 표시 중인 직함을 직원 관찰 앵커로 사용한다. 직원 이름 글자의 활성 여부를 직원 전체의 가시성으로 오인하지 않는다. 외부 UI 가림, 화면 범위, 카메라 효과 검사는 기존 `VisibleWorldLabel` 경로를 유지한다.
- 카메라에 확인된 직원의 신원 제공 정책에 따라, 이름 글자만 AutoUIHider로 꺼지고 직함은 실제로 보이는 경우 UI에 연결된 직원 이름을 식별자로 제공한다. 축소 화면에서 이름 글자가 읽힌다는 뜻은 아니다. 비활성 계층이나 임의로 숨겨진 Text를 일괄 허용하지 않는다. HP/SP 해금 판정도 변경하지 않는다.
- 예소드 처리 `DeactivateAllUI`와 직원 사망 처리에서 이름 및 직함을 모두 비활성화하는 코드를 확인했다. 카메라 밖 직원은 현재 목록에 넣지 않으며, 기존 별도 사망 목록 정책은 유지한다.

## 실제 11일차 검증

- 검증 전: 7명 존재, `employees={}`.
- 수정 후: 1280×720 및 1728×972에서 각각 7명. 에덴·빅토르·아처(지휘팀), 아스터로이드·배트워든맨·브룩(정보팀), 올가(교육팀)의 이름·상태·화면 좌표·시설 ID와 시설 내 상대 위치 확인.
- 일시정지 중에도 직원 상태는 이동 중/대기 중으로 유지되고, 실제 화면 속도 벡터는 0이다. 상태와 프레임 간 변위는 별개다.
- 카메라 이동·확대 후 직원이 화면 밖으로 나간 상황에서 `employees={}`로 바뀌는 것을 화면과 대조했다.
- 겹친 직원은 이름·위치·상태가 있어도 안전한 직접 클릭 좌표가 null일 수 있다. 이번 수정은 클릭 판정을 변경하지 않는다.
- 실제 증거: `.robotomy/player-feedback-work/evidence/day11-fixed-1280.{json,png}`, `day11-fixed-1728.{json,png}`, `day11-offcamera-zero.{json,png}`. 원본 게임의 전체 보스/투명 효과에 대한 포괄 검증을 뜻하지 않는다.
- 본게임용 DLL은 진단 probe를 포함하지 않는다. 백업: `.robotomy/backups/20261021-day11-employees/`. 원본29개·플레이 저장6개 SHA256 불변 확인 후 배포.


본게임 적용 완료: PID39488, live, 11일차 준비 화면(LOB2) 복귀. 관리 시작은 플레이어에게 남겨 두었다. 재접속 후 세이브 해시 재확인 통과. 실제 스냅샷 검증과 realtime_v2 15개 테스트 통과.
