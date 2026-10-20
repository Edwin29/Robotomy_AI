# E.G.O 입력·방 클릭 좌표 수정 검증

2026-10-19. 본 플레이 PID 33916은 유지하고 Robotomy_Lab에서만 입력·재실행했다.

## 변경

- InventoryAgentController의 실제 표시 Text에서 선택 직원 이름, 현재 무기/슈트, 등급, 피해 유형/범위, 내성 표현/배율을 selected_equipment로 제공한다. 장비 모델을 직접 공개하지 않는다.
- 장비 슬롯의 전체 사각형 대신 클릭 지점의 가시성과 EventSystem의 최상위 클릭 핸들러를 확인한다. 인접 초상화의 사각 영역 때문에 앞쪽 슬롯이 누락되던 문제를 해결했다.
- 무기 탭은 E.G.O 창의 Title 장식 사각형에 의해 front_graphic으로 거절되었으나 실제 Raycast는 WeaponButton이었다. 탭은 E.G.O 복합 UI를 한 표시 영역으로 취급하되 실제 최상위 클릭 핸들러·활성 상태·마스크·외부 UI 검사를 유지한다.
- 게임기 자체 가상 포인터는 UI 정보 가림으로 취급하지 않는다. 모션 전용 가림 로직은 이번 변경 범위에 포함하지 않았다.
- 방의 기존 x/y는 CounterText 등 마지막으로 읽힌 표시 위치였다. 별도 click.x/y는 IsolateRoom.OnClick에 실제 연결된 EventTrigger 영역을 투영하고, 그 지점의 최상위 클릭 핸들러가 동일한지 확인한 좌표다. 좌상단 원점의 화면 픽셀 단위이며, 확인할 수 없으면 null이다. 작업 가능한 상태인지까지 보장하는 값은 아니다.

## 실제 검증

Lab의 DAY 6 준비 화면에서 빠른 관찰 좌표로 직원 선택, 무기 이전/복구, 무기→슈트→무기 전환 성공. 무기 슬롯 2개·슈트 슬롯 3개가 모두 제공되었다. 선택 카드의 제압봉→참회 갱신과 포인터가 슬롯 위에 남아 있는 상태의 이름 유지 확인. 창 닫기 후 selected_equipment=null.

실제 E.G.O 스냅샷 7개를 diff로 재생해 전체 섹션이 동일하게 복원됨을 확인했다. 회귀 테스트 207개 통과.

Lab 본편 운영 화면에서 방 5개의 click 좌표 제공. 요정의 축제 click=(569.54,230.71)로 해당 작업 메뉴 열림. 메뉴가 가린 해당 방은 room_status에서 제외됨. 옵션 메뉴에서는 room_status가 비었다.

카메라 D 이동 후 방 좌표가 새 위치로 갱신됐고 화면 밖의 방 1개는 제외됨. 새 웰치어스 click=(616.37,179.28)로 정확한 작업 메뉴 열림. 확대 입력은 이번 실행에서 확대 변화가 확인되지 않아 확대 배율별 실증으로 계산하지 않는다.

근거: Lab `.robotomy/verification/ego-final-*.json`, `room-paused.json`, `room-click-fairy.json`, `room-close-menu.json`, `room-camera.json`, `room-click-moved.json` 및 대응 PNG. 엔지니어링 자료이며 플레이어 경험에 주입하지 않았다.

## 배포 상태

본 플레이 DLL은 교체하지 않았다. 배포 후보는 `.robotomy/patches/ego-room-controls-20261019/RobotomyObserver.dll` 및 manifest.json. Python 소비부는 구버전 출력도 수용한다. 플레이어 지침은 config/player/AGENTS.md 및 별도 Robotomy_Player 폴더에 반영했다. 게임 DLL 변경은 안전한 재시작 때 적용해야 한다.
