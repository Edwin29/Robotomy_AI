# 간단 카메라 줌 입력

`game_input(command=["Z", 1], include_frame=True)`는 짧게 확대,
`["Z", -1]`은 축소다. 정수 절댓값 1~5를 사용하며 1단위는 기존 F/G 키 300ms 입력이다.
2는 두 배 배율이 아니라 600ms의 입력 강도다. 현재 카메라 중심을 유지하고 게임의 제한을 따른다.
`include_frame=True`이면 입력 이후 전체 화면을 같은 호출에서 반환한다. 별도 이미지 호출이 필요 없다.
직원이나 방으로 카메라를 자동 이동시키거나, 관심 대상/전략을 선택하지 않는다.
플레이어 AGENTS/페르소나/관찰 습관 지침은 변경하지 않았다.

## 게임 코드 근거

기존 해시 검증된 Assembly-CSharp decompile의 `CameraMover.Update`를 확인했다.
- movable=false일 때 리턴한다.
- 휠은 `_target`이 없을 때 부호로 줌한다. 목록 스크롤 대상과 경합할 수 있다.
- F/G는 카메라 확대/축소 키다. 실제 CameraOrthographicSize setter는 카메라 크기를 갱신하고 OnChangeCameraSize 통지를 보낸다.
- 최소5, 최대는 확장된 부서에 대응한 currentRange.ortho로 게임이 제한한다. 장치에서 카메라 수치를 직접 덮어쓰지 않는다.
- 이 오래된 게임의 F/G 변화량은 프레임마다 적용되므로 같은 입력 길이가 정확한 배율을 보장하지 않는다.

Python QuickInput 별칭만 추가해 기존 가상 키 입력·입력 잠금·중단·장면 변경·해제 경로를 재사용한다.
게임 DLL, 저장 파일, 운영 지침은 변경하지 않는다. 새 MCP 도구/스키마도 추가하지 않아 기존 연결의 코드 자동 재로딩으로 반영된다.

## 검증

- unit/storage/executor 268개 테스트 통과. 잘못된 줌 값(0, 범위 초과, bool, 실수, 문자열)을 입력 전에 거절하고, intent 묶음 전체 사전검증도 확인.
- MCP stdio smoke와 코드 재로딩 smoke 통과. 도구 스키마는 유지.
- 검증용 11일차 0/170 일시정지 상태에서 실제 MCP game_input `[Z,2]`, `[Z,-2]`를 실행. 확대/축소 화면과 PNG 반환을 직접 확인. 키 입력 영수증은 각각813ms,969ms(관찰/이미지 전체 왕복 시간은 아님).
- 이미지 증거 `.robotomy/player-feedback-work/evidence/zoom-before.png`, `zoom-in.png`, `zoom-out.png`; 입력 영수증도 같은 폴더에 보관.
- 본게임 PID39488 유지, 재시작/입력 없음. 원본29개 및 플레이 저장6개 해시 불변 확인. 플레이어 AGENTS도 기존 바이트와 일치.
