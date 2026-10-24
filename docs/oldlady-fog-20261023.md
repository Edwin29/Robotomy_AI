# 늙은 여인 검은 안개 표시

2026-10-23. 기존 외형 어댑터에 `OldLadyAnim.stackEffect` 항목은 있었지만 실제 수집은 빠졌다.
몸체가 Spine이 아닌 Puppet2D여서 후보에 등록되지 않았고, stackEffect의 실제 렌더러는
ParticleSystemRenderer라 일반 Sprite/Mesh 가시성 검사도 통과하지 못했다.
프리팹 안의 `dust` Animator 장식과 stackEffect가 가리키는 안개 효과는 별개다.

## 변경

- MotionTargets의 명시적 표시 루트에 OldLadyAnim을 추가했다. 현재 몸체와 모션은
  실제 `OldLadyCenter` Animator에서 읽는다.
- 안개는 격리실 `appearance.marks`에 `검은 안개` 하나로 묶는다. 3개 파티클 그룹을
  3개 표식이나 내부 누적량으로 제공하지 않는다. 안개 유무로 몸체의 form ID는 바뀌지 않는다.
- 활성 그룹의 실제 살아 있는 입자의 색/크기/위치, 렌더러, 카메라, UI 가림을 확인한다.
  빈 파티클 시스템의 활성 플래그만으로 표식을 만들지 않는다. 내부 카운터/효과/미래 시간은 읽지 않는다.
- `name_visual`로 별칭과 메모를 붙일 수 있다. 기본 명칭은 외형 설명이고 기믹의 원인을 설명하지 않는다.

## 검증

최신 본 저장의 복사본으로 Lab 14일차 교육팀을 구성했다. 본 세이브에 쓰지 않았다.
최초 외부 파일 복사 후에는 Lab 프로세스가 실제로 읽은 바이트가 이전 11일차와 달랐다.
이 차이를 파일 복사 성공으로 덮지 않고, Lab 전용 실행 코드로 백업한 본 저장을 Lab 저장 경로에
전달한 뒤 프로세스 내부 SHA-256과 `lastDay=13`(화면 DAY14)을 재확인했다.
실제 시설에 생성된 OldLadyAnim에서 검증했다. 이 테스트 보조 코드는 일반 DLL에 포함하지 않았다.

- 게임의 SetEffect/DisableEffect 표시 경로를 Lab에서만 호출하고, 정지 중에는 파티클을
  표시 테스트용으로 Simulate했다. 작업으로 고독을 발동시킨 플레이 성공 테스트는 아니다.
- 실제 3개 그룹: Local simulation, 각 maxParticles=300, Particles/Alpha Blended 셰이더.
- 화면에서 검은 안개가 나온 때 일반 `observe_player`의 늙은 여인 방에 표식 1개 전달.
  ref는 `mark:8c0f00ed110d68f31bfe`. 비활성화하면 빈 목록, 같은 form ID 유지.
- 카메라 확대 후 해당 방이 화면 밖으로 나가면 크리쳐 외형 행도 사라짐을 확인했다.
- 별칭 저장/조회, 표식 제거, 임의의 숨은 효과 라벨 거부를 테스트했다.
- 생산 소스 전체 테스트 303개 통과. MCP stdio smoke 61개 도구 통과.

본 플레이 준비 화면에서 정상 종료 후 소스와 DLL에 반영했다. 새 도구나 스키마는 추가되지 않는다.
일반 Lab DLL도 fixture 없이 다시 빌드했다. 로컬 증거/백업은 `.robotomy/oldlady-work/`,
프레임과 표시 결과는 `.robotomy/appearance-work/evidence/oldlady-*`에 있다.
원본 및 본 세이브 해시는 적용 전후 대조하며, 테스트용 별칭은 본 경험 저장소에 넣지 않았다.

최종 확인: 본게임 PID 107508, 14일차 준비 화면 live. 원본 5개/본 저장 3개 해시 모두 동일.
