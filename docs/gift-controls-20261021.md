# 직원 E.G.O GIFT 관리

## 구현과 사용
ConsoleGifts는 AgentInfoWindow의 현재 표시 이름과 AgentGiftWindow.slots를 읽는다. 표시 GiftName/RegionName/GiftDescription만 사용한다. 자물쇠 상태는 AgentGiftSlot.SetLockButton이 선택한 Lock_Close/Lock_Open 스프라이트로 매핑하며, 잠금 조작 가능 여부는 Button.IsInteractable에서 온다. 비활성·화면 밖·클리핑된 UI에는 기존 VisibleSurface 검사를 적용한다. 숨긴 슬롯의 예제 문자열이나 내부 기프트 목록은 제공하지 않는다.

빠른관찰 reading.gifts는 employee/open_click/slots로 구성한다. 슬롯은 직원 이름+현재 UI 슬롯 ID로 구별하여 다른 직원 전환 후 기존 대상 참조가 유효하지 않게 했다. 같은 직원에서 기프트가 바뀐 경우도 이름과 상태는 최신 관찰로 확인해야 한다. 잠금은 게임의 원래 버튼을 클릭하며 모델의 잠금 값을 직접 수정하지 않는다. 기존 game_input의 결과 observation과 keyed diff를 그대로 사용한다. 별도 MCP 도구는 추가하지 않았다.

## 확인한 게임 구조
AgentGiftWindow.SetAgent는 직원 level>=3에서 외형 표시, level>=4에서 잠금 조작을 허용하며 둘 다 GameState.STOP 조건을 요구한다. 준비 상태와 운영 중 일시정지는 같은 조건이 아니다. 특수 슬롯(region 210)은 두 버튼을 비활성화한다. 생산 코드는 이 규칙을 복제하지 않고 실제 버튼 상태를 따른다. AgentGiftSlot.SetLock은 UI 스프라이트와 기존 UnitEGOgiftSpace.SetLockState를 함께 갱신한다. IsLocked 필드나 내부 인벤토리의 잠금 값을 관찰로 사용하지 않는다.

실제 검증용 Day11 준비 화면에서 직원 선택→기프트 열기를 정상 입력으로 확인했다. 배트워든맨의 황홀한 꿈(머리 1/정신력 +4), 아처의 참회(머리 1/정신력 +2 및 해당 환상체 작업 성공률 설명)가 UI와 일치한다. 낮은 등급에서는 locked=false, lock_available=false이고 조작 대상은 없다. 직원 교체와 닫힌 창에서 이전 기프트가 현재 목록에 남지 않는 것을 확인한다.

본게임 적용 완료(2026-10-21). Python 해석부와 플레이어 안내도 반영되어 있다. 아래 배포 확인을 참고한다.


## 최종 검증
- 실제 기존 직원의 낮은 등급 잠금 불가, 기프트 이름/부위/효과 표시는 검증용 저장으로 확인했다.
- 긍정 입력 검증은 검증용 게임 메모리에서만 배트워든맨의 능력을 임시로 올려 기본 게임의 등급 조건을 충족시킨 실험이다. 자연 육성으로 획득한 결과로 기록하지 않았다. 잠금은 원래 화면 버튼으로 false→true→false 전환했고 반환 observation/diff의 locked 값도 일치했다.
- 아처로 전환 후 배트워든맨의 이전 gift 참조는 Target missing or ambiguous로 차단되었다. 잠금 툴팁이 효과 본문을 가린 경우 description이 제거되며 잠금 값은 보이는 자물쇠에서 계속 읽는다.
- 원본 화면/입력 반환 증거: 로컬 .robotomy/player-feedback-work/evidence/gift-unlocked.png, gift-locked-receipt.json, gift-unlocked-again-receipt.json. 진단용 Fixture는 검증용에서만 사용했고 테스트 종료 후 일반 DLL로 교체했다. 검증용 세이브 6개는 테스트 전 백업 해시와 동일하다.
- 전체 테스트 272개 통과. DLL 빌드 성공. 본게임은 현재 운영 중이므로 교체/재시작/입력 없이 유지했다. 본게임 적용에는 다음 안전한 경계에서 재시작이 필요하다.


## 본게임 적용 확인 (2026-10-21)
사용자 요청으로 13일차 준비 화면에서 백업 후 정상 종료, production DLL 교체 및 공식 독립 런처 재시작을 완료했다. PID 1052에서 배트워든맨의 황홀한 꿈/머리 1/정신력 +4, locked=false, lock_available=true와 lock_click 대상 수신을 확인했다. 본게임의 잠금 상태는 조작하지 않았다. 창을 닫고 DAY 13, LOB 7, 관리시작 이전 준비 화면에 대기했다. 원본과 본게임 세이브 14개 해시는 배포 전과 동일하다. 백업: `D:\Projects\Robotomy_AI\.robotomy\backups\gift-main-20261021-105402`. 증거: 로컬 `.robotomy/player-feedback-work/evidence/gift-main-reading.json`, `gift-main-current.png`.
