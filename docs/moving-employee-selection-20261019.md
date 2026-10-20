# 이동 중 직원 선택: 실행 시점 대상 해석

2026-10-19. lab 검증 후 사용자 승인으로 본 플레이 적용 완료.

## 본 플레이 배포

7개 파일의 before/after 해시 대조, private runtime DLL 및 isolation 해시 갱신 완료. 9일차 에너지 10/140에서 일시정지 중이어서 당일 미저장 진행이 사라짐을 설명했고, 사용자가 9일차 재시작을 승인했다. PID 38336 정상 종료 후 공식 런처로 PID 5552 재실행했다. 원본·플레이 세이브 15개 파일 SHA256 동일. 백업은 `.robotomy/backups/moving-selection-20261019T141235Z`.

적용 코드에서 234개 테스트와 MCP smoke 통과. 새 MCP 연결 및 현재 연결 모두 ready/새 코드 revision 확인. 새 도구 스키마나 상주 모듈 변경이 없어 현재 연결은 재연결 없이 반영됐다. 플레이어 지침은 두 위치에 동기화했고, 별도 `Day-09-Maintenance-20261019.md`에 재시작 사유를 남겼다. 활성 시도가 없어 ledger 자동 기록은 하지 못했으며 그 사실도 문서에 명시했다.

## 변경

기존 Python 경로는 좌표를 정한 후 별도 무결성 확인 프로세스와 파일 전달, Unity의 누름/뗌 프레임을 거쳤다. 최신 snapshot으로 좌표를 다시 정해도 이 뒤 지연은 남는다.

새 employee 좌클릭은 관찰에서 얻은 임시 track token을 v2 가상 입력에 붙인다. Unity가 처리하는 프레임에 관찰된 직원 레지스트리에서 대상을 찾고 현재 카메라·HUD 가시성·실제 collider·UI 클릭 경로를 다시 확인한다. 현재 좌표를 구한 같은 스레드에서 PointerEventData를 만들고 UnitMouseEventManager.OnPointerClick을 호출한다. 포인터도 그 위치로 옮긴다. 숨겨진 직원 목록 검색이나 목표 위치/작업 필드 쓰기는 없다.

이 방식은 일반 좌클릭 선택에만 적용한다. 드래그·우클릭·작업창 행·키 입력은 기존 경로다. game_input의 employee ref/이름 좌클릭과 move_employee의 첫 선택에서 자동으로 사용하며 플레이어 사용법은 동일하다. 명령 토큰이 없으면 기존 16필드 v1 프로토콜을 유지한다.

## 확인한 게임 경로

기존 `.robotomy/analysis/Assembly-CSharp.decompiled.cs`:
- 316209: OnPointerClick → UIActivateManager.OnClickBackGround → 총알 모드 / DefaultClickBlocked → 기본 클릭 처리.
- 316000: 기본 좌클릭은 현재 좌표의 OverlapPointAll, IsSelectable, 튜토리얼 조건, 겹친 대상 선택을 처리한다. 드래그 상태이면 선택하지 않는다.
- 315736: SelectTarget은 이전 선택 해제와 게임의 선택 처리를 수행한다.

따라서 목표 노드·작업을 직접 바꾸는 대신 정상 클릭 진입점을 재사용한다. 이건 물리 마우스의 누름/뗌을 완전히 재현하는 기능은 아니며, 일반 클릭 선택의 게임 처리를 호출하는 기능이다. 선택 확인 후 목적지 우클릭을 보내는 기존 절차도 유지한다.

## 실제 검증과 한계

- 격리 lab DAY6, 2x 표시에서 직원 재선택→방향 변경 8회: 7회 선택과 명령 완료, 1회 실행 순간의 가시성/클릭 가능성 검사에서 거부. 이 1회의 세부 하위 조건은 현재 응답으로 확정할 수 없다. 거부 후 목적지 명령은 보내지 않았다.
- 별도 핵심 실험: 의도적으로 좌표를 (1,1)로 준비하고 350ms 지연 후 실행. 이동 중 직원 5/5 현재 위치 선택 확인. 관찰 속도 약 10~89 px/s. 이로써 옛 좌표를 사용하지 않는 경로를 확인했으며, 모든 속도/겹침 상황 무실패를 의미하지 않는다.
- 정지 직원 동일 실험 5/5 선택. 존재하지 않는 token은 rejected, 임의 좌표 클릭으로 대체하지 않음.
- C# build 성공. MCP smoke 46개 도구 통과. 신규 검사: employee token 전달, v1 호환, v2 좌클릭 제한.
- 시야 밖/겹침/불가능한 클릭의 자동 재시도나 보이지 않는 직원 직접 선택은 하지 않는다. 선택 실패 이유의 세분화는 별도 개선 여지가 있다.

## 적용

패치: `docs/moving-selection.pending.patch`.
소스·production DLL·manifest·증거: `.robotomy/patches/moving-selection-20261019/`.
본 플레이 종료 후 소스 before 해시를 대조해 7개 변경 파일만 적용하고 private runtime DLL과 isolation 해시를 함께 갱신한다. Lab.dll/identity/save는 복사하지 않는다. 새 DLL 없이 Python v2 송신 부분만 먼저 적용하지 않는다. 게임 재실행과 새 MCP 연결로 확인한다. 플레이어 저장 데이터 변경은 필요 없다.
