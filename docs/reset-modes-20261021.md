# 재시작 기능 구분 — 플레이어 안내 근거

플레이어용 비교표는 config/player/AGENTS.md와 Robotomy_Player/AGENTS.md에 동일하게 반영했다. read_player_guide는 전자와 Recording-Rules.md를 파일에서 읽으므로 별도 MCP 스키마 변경/재시작은 없다. 기록 절차는 Recording-Rules.md에 모았다. 게임 입력과 파일 초기화는 실행하지 않았다.

## 확인한 현재 파일
Assembly-CSharp.dll SHA256 fb31a592f29a6d8a08e3884cf21d94bc8bd167c9aeefc2eef81a774c70b294bd. 기존 검증된 전체 디컴파일 및 현재 설치 모드 전체 디컴파일을 읽었다.

- GameManager.RestartGame: LoadGlobalData 후 LoadData(LASTDAY). 재도전 자체는 현재 전역 상태를 먼저 저장하지 않는다.
- GameManager.ReturnToCheckPoint: SaveGlobalData 후 LoadData(CHECK_POINT). 새 장비와 손실 모두 현재 전역 인벤토리에 따른다.
- GlobalGameManager.GetSaveDayData/LoadDay: day, money, agents, creatures, playerData, sefiras, saveState, agentName.
- SaveGlobalData/LoadGlobalData: observe, etcData, inventory, research, missions, sefiraCharactes.
- InventoryModel.GetGlobalSaveData는 보유 장비 목록을 저장한다. 직원 기프트는 직원 데이터의 gifts로 저장/복원된다.
- DeployUI.CheckPointCheck: 0-based day%5==0. 표시 날짜는 +1. 화면의 실제 각인 날짜를 우선하도록 안내했다.
- NewTitleScript.ClickAfterNewGame/AlterTitleController.CallNewgame: 저장된 전역 데이터 로드 후 InitStoryMode. 현재 정규직 모드는 마지막 저장의 직원을 추가 로드하고 부서 배치를 해제한다. 모드 세부 근거는 qol-mods-20261021.md.
- NewTitleScript.Reset/AlterTitleController.ResetData: 일반/전역/기타/무한 데이터와 부가 직원·스크립트 저장 삭제. 정규직 모드가 패치한 두 새게임 진입점과 다르다.

특수 효과의 예외나 아직 보지 않은 이야기·보상은 플레이어 표에 나열하지 않았다. 현재 설치의 정적 코드에서 확인한 일반 저장 동작 설명이며, 이번 작업에서 실제 재도전/회귀/삭제를 실행해 검증한 것은 아니다. 외부 경험 저장소와 Steam 계정의 업적까지 삭제한다고 설명하지 않는다.
