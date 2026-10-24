# 직원·방 표시와 이름표 클릭

직원은 UnitUI 이름과 AgentUI.Name 양쪽의 표시된 이름을 앵커로 확인한다. 일반 pauseDefSprite/observeSprite의 일시정지 장식은 worldLabel 가림에서 제외한다. 화면 밖, 비활성, 해금 필터, 외부 메뉴와 카메라 효과 검사는 유지한다. 신체 텍스처 정밀 검사는 이름 앵커가 없는 경우의 기존 대체 경로다.

격리실 수치가 모두 미확인이더라도 활성 화면 방 스프라이트와 실제 OnClick 입력면이 확인되면 room_status 항목을 남긴다. 미확인 수치는 null이다. OnClickCollectionButton은 게임 코드상 왼쪽 클릭으로 OnClickCollectionFunc를 호출하므로 별도 info_click 및 room_info 대상을 제공한다. 좌표는 serialized EventTrigger 연결과 현재 raycast로 검증한다.

검증용 Day6 실제 운영·일시정지에서 직원3명의 이름/상태/좌표 유지, 이름표 대상5개 생성 및 첫 대상 클릭 후 creature 정보창 표시 확인. 교육팀이 없는 검증 세이브이므로 새 교육팀의 특정 장면은 이 검증에서 재현하지 않았다. Python 회귀266개 및 미확인 수치 보존/미검증 이름표 좌표 거절2개 검사 통과.

본게임 적용 백업: .robotomy/backups/20261021-visibility.
