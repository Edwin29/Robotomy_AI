# 작업 중 격리실 문구

## 구현
- 실제 Assembly-CSharp의 IsolateRoom.ProcessNarration → WorkNarration(Text) → NarrationFadeEffect 경로를 확인했다. 기본 FadeEffecter 수명은 7초이며 페이드 인/아웃이 있다.
- 실제 프리팹 경로는 IsolateRoom/Canvas/RootArea/Narration/WorkNarration/CurrentNarration이다. 런타임에서 FadeEffecter.textTarget과 WorkNarration의 동일성을 확인했다.
- 최종 표시 Text만 읽는다. 활성 상태, 카메라, 기존 공개 범위 검사, 완전 출력/불투명 구간을 만족할 때 제공한다. 내레이션 원본 테이블, 미래 문구, 비표시 로그는 제공하지 않는다.
- 현재 문구: hazards.room_status[room_id].work_narration. 기존 keyed diff 적용.
- 이력: room_narration 신호 → Realtime event_delivery.events. 방 ID, 표시 이름, 문구, 시각을 보존하고 같은 표시를 중복 전송하지 않는다. 기존 제한된 이벤트 버퍼를 사용하며 영구 전체 문구 아카이브가 아니다. 화면 밖으로 나간 뒤 남은 이벤트는 과거 관찰이지 현재 정보가 아니다.
- 일시정지 조건이나 전략 판단은 추가하지 않았다.

## 검증
검증용 Day11 게임에서 에덴에게 본능 작업을 지시해 자연 발생한 문구를 확인했다. ‘단 한번의 악과 수백 가지의 선행은 상황에 따라선 직원들에게 긍정적인 효과를 줄 수도 있습니다.’가 실제 Text와 동일하게 전달되었다. 캡처 화면에서 해당 방 아래에 작은 문구가 표시되며, 런타임 active=true, alpha=1, visible=true였다. 숨겨진 다른 방의 기본 WorkNarration 문자열은 전달되지 않았다.

일시정지 상태에서 카메라를 오른쪽으로 이동하자 해당 방은 현재 목록에서 제거됐고 기존 관찰 이벤트 1건만 남았다. 실측 증거는 로컬 .robotomy/player-feedback-work/evidence/narration-live 및 narration-offscreen JSON/PNG에 있다. 테스트 전체 270개 통과, 배포용/검증용 DLL 빌드 성공. 모든 환상체와 보스 연출을 검증한 것은 아니며 페이드 구간이나 버퍼 초과에 대한 완전 무누락 보장은 없다.

## 적용 상태
Python 처리와 플레이어 안내는 수정했다. 게임 DLL은 검증용에서 확인했고 본게임용 빌드를 준비했다. 본게임은 진행 중이므로 재시작하거나 DLL을 교체하지 않았다. 본게임 적용에는 저장 가능한 안전한 경계에서 게임 재시작이 필요하다. 원본 게임과 본게임 세이브는 변경하지 않았다.


## 본게임 적용 완료 (2026-10-21)
사용자의 플레이 종료 및 적용 요청 후 준비 화면을 확인하고 정상 종료했다. 최신 원본 세이브 8개와 본게임 세이브 6개를 백업한 뒤 검증된 production DLL을 교체했다. SHA256: 9012872fa109f57a07704e4dc2d8193f4087607008ec1e7f6328b036e6bf0f12. 공식 격리 런처로 재실행했고 관찰 live 연결을 확인했다. 재실행 후 14개 세이브 해시 동일. 원본 설치/설정 무결성 검사도 통과했다. 새 작업이나 플레이는 시작하지 않았다. 백업: D:\Projects\Robotomy_AI\.robotomy\backups\room-narration-20261021-092025
