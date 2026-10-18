# 실제 게임 읽기 전용 연결

최신 최소 구성은 [구현·실행 검증 보고서](console-minimum-verification.md)를 따른다.
아래는 초기 연결과 저장 분리 절차다. 입력·표시 필터·소리 이벤트가 이후 추가됐으며
원본 설치와 기존 저장 파일 보호 원칙은 동일하다.

2026-10-17: 별도 게임 실행본에서 타이틀 화면 → UI JSON → 로컬 MCP → Obsidian 기록,
게임 PNG → MCP 이미지 응답을 확인했다. 이후 튜토리얼 기본 조작과 첫 작업 완료까지 검증했다.
입력 연결/판단 기록/검증 범위의 최신 안내는 [live-control.md](live-control.md)를 따른다.
직원/작업/전투 전체를 구조화하는 어댑터는 아직 없다.

## 저장 분리와 복구

- 원본 설치: `D:\SteamLibrary\steamapps\common\LobotomyCorp` — 변경하지 않는다.
- 테스트 실행본: `<repo>\.robotomy\runtime\LobotomyCorp` — 독립 파일 복사, 하드링크 아님.
- 원본 저장: `%USERPROFILE%\AppData\LocalLow\Project_Moon` 전체를 백업한다.
  게임은 `Lobotomy` 하위 폴더 밖의 `Lobotomy170808state.dat`도 쓰므로 부모 폴더를 포함한다.
- 테스트 저장: `%USERPROFILE%\AppData\LocalLow\Robotomy_AI\Lobotomy_Observer`.
  형제 파일 `Lobotomy_Observer170808state.dat`도 `Robotomy_AI` 아래에 생길 수 있다.
- 백업: `<repo>\.robotomy\backups\<UTC시각>\Project_Moon`, SHA-256 목록은 `manifest.json`.
- 원본 PlayerPrefs 값과 Steam Cloud 메타데이터도 백업에 기록한다. Steam Cloud 설정을 바꾸지 않는다.

복사본의 `globalgamemanagers` PlayerSettings에서 회사/제품명 두 값만 바꾸어 Unity의
저장 경로와 PlayerPrefs 이름을 분리했다. 실제 런타임이 보고한 경로까지 대조했다.
기존 인간 플레이 세이브를 가져오지 않은 새 프로필이다. 원본에서 쓰던 추가 모드는 제외하고,
기존 BaseMod 기반 로더와 직접 만든 관찰 모드만 사용한다. 따라서 순정 게임과 완전히 동일한 환경은 아니다.

복구는 `Lobotomy_Observer` 창을 닫고 평소 Steam에서 원본을 실행하면 된다.
원본 세이브를 이동하지 않았으므로 되돌려 복사할 작업도 없다. 이상이 발견되면 먼저 양쪽 게임을 닫고
`isolation.json`과 백업의 해시 목록을 비교한다. 기존 파일에 백업을 자동 덮어쓰지 않는다.
테스트 프로필을 초기화하려면 게임을 닫고 `Robotomy_AI` 저장 폴더를 별도 보관한 뒤 처리한다.

이 방식은 저장 위치 분리이며 OS 접근 차단이 아니다. 모드·Steam·게임 전체의 모든 부작용을 차단하는
보안 샌드박스로 설명하지 않는다. 현재 검증은 원본 저장 파일 29개, 원본 PlayerPrefs,
원본 PlayerSettings 파일의 실행 전후 동일성이다. 이후 원본 게임을 직접 플레이하면 기준 해시가 달라져
실행기가 중단할 수 있다. 이때 새 백업을 검토해서 기준을 갱신해야 하며 검사를 우회하지 않는다.

## 실행과 관찰

이 PC에는 준비가 끝나 있다. 레포 루트의 `Launch-Live.cmd`를 열거나 아래 명령을 사용한다.
게임이 이미 열렸으면 중복 실행을 거부한다.

```powershell
.\.venv\Scripts\python.exe scripts\launch_live.py
.\.venv\Scripts\python.exe -m robotomy live-status
.\.venv\Scripts\python.exe -m robotomy live-observe
.\.venv\Scripts\python.exe scripts\check_live_mcp.py
.\.venv\Scripts\python.exe scripts\launch_live.py --verify-only
```

`Lobotomy_Observer`는 1280×720 창 모드로 실행된다. 상단의 `SEPARATE SAVE | VIRTUAL INPUT` 표식으로
구분한다. 사용자에게 보이는 게임 창은 실제 프레임 속도로 표시되며, 모델용 JSON은 약 1초,
PNG는 약 2초 간격이다. 최소화나 렌더링 지연 때 관찰이 멈출 수 있으므로 창을 열어 둔다.
타이틀 첫 화면은 키/클릭 입력을 기다린다. 관찰기가 대신 입력하지 않는다.

`live_status`, `observe_live`, `view_live_frame`이 실제 관찰용 MCP 도구다.
JSON이 10초 이상 오래되거나 저장 identity가 틀리면 읽기를 거부한다. 이미지도 별도로 freshness를 검사한다.
이전 합성 세션 도구와 섞지 않는다. 실제 도구의 stdio 호출은 검증했지만, 이 개발 채팅에
프로젝트 MCP가 자동 등록되었다는 의미는 아니다. Codex 프로젝트 신뢰/재연결 후 도구 노출을 확인한다.

## 수집 범위와 한계

- UI.Text의 활성 상태, canvas alpha, cull, 화면 교차 영역을 확인한 텍스트 후보와 화면 좌표.
- 일부 Unity UI.Button의 텍스트·영역·interactable. 게임의 커스텀 메뉴는 누락된다.
- 게임 프레임 PNG. 화면에 이미지로 그려진 글씨는 JSON에 없을 수 있다.
- 프로세스 ID, 시각, 시퀀스, 씬, 해상도, 저장 위치의 식별 정보.

다른 불투명 패널에 가려진 텍스트까지 완벽하게 판별하는 occlusion 검사는 없다.
따라서 텍스트 후보를 현재 화면과 대조해야 하며, 텍스트 존재만으로 정보가 플레이어에게
보이거나 대상이 클릭 가능하다고 단정하지 않는다. 텍스트와 PNG는 별도 표본이므로 같은 프레임이라고
가정하지 않는다. 미해금 규칙, 성공률, 직원의 내부 모델, 숨은 타이머는 조회하지 않는다.

`observe_live` 호출 때마다 `.robotomy/live/observations.jsonl`과 `vault/Live/`에 관찰을 남긴다.
주기적으로 갱신되는 latest/frame 파일 자체는 전체 플레이 이력이 아니다.
실제 판단/입력/결과 기록은 별도 `control/events`에 추가했다. 회고·모델 이전 번들 통합은 아직 없다.

## 새 환경에서 준비하거나 모드 다시 빌드하기

현재 설치본의 BaseMod 로더를 대상으로 만든 스크립트다. 다른 게임 버전/모드 조합에서의 호환성은 미검증이다.
게임은 종료되어 있어야 하고, 대상 실행본/프로필이 이미 있으면 준비 스크립트는 덮어쓰지 않는다.

```powershell
.\.venv\Scripts\python.exe -m pip install -r requirements-live-dev.txt
.\.venv\Scripts\python.exe scripts\prepare_live.py --source 'D:\SteamLibrary\steamapps\common\LobotomyCorp'
# 기존 복사본에 관찰 모드만 다시 빌드할 때 (게임 종료 필요)
.\.venv\Scripts\python.exe scripts\prepare_live.py --finish-build
```

준비 순서: 원본 저장 백업/해시 검증 → 실행본 복사 → 회사/제품명만 수정/재읽기 검증 →
관찰 모드 빌드 → 원본 무변경 검증. 시작할 때 실행파일/메타데이터/관찰 DLL 해시를 확인하고,
실행한 PID의 관찰 및 실제 저장 경로를 대조한다. 잘못된 identity/연결 시간 초과는 새로 실행한
복사본만 종료한다. 권한 변경이나 원본 프로세스 강제 종료는 하지 않는다.

`steam_appid.txt`는 이 게임의 App ID로 복사본에서 직접 실행할 때 원본 설치본으로
재실행되는 것을 막는 Steam 개발용 관례다. Steam 인증을 우회하거나 다른 App ID를 사용하지 않는다.
게임 파일·세이브·분석 결과·이미지·개인 경로가 담긴 manifest는 모두 Git에서 제외한다.

근거: [Unity persistentDataPath](https://docs.unity3d.com/2018.4/Documentation/ScriptReference/Application-persistentDataPath.html),
[Steam 직접 실행 규칙](https://partner.steamgames.com/doc/sdk/api#SteamAPI_RestartAppIfNecessary),
[Steam Cloud](https://partner.steamgames.com/doc/features/cloud),
[UnityPy](https://github.com/K0lb3/UnityPy). 설치본의 ILSpy 정적 분석으로 저장 API 사용과
BaseMod 초기화 지점을 확인했다. 해당 분석은 개발자 자료이며 플레이어 경험에 넣지 않는다.

## 다음 개발 채팅 첫 지시문

> AGENTS.md, docs/live-adapter.md, docs/live-control.md를 읽어라. 튜토리얼 1은 이전 Win32 실행기로, 2·3은 게임 내부 가상 입력으로 완료했다. 현재 기본 입력은 virtual_input.py이며 AI 입력은 중지되어 있다.
> 원본 설치/저장 파일을 유지하고 tests 및 원본 무결성 검사를 먼저 확인하라.
> 사용자에게 보이는 튜토리얼/관리 화면에서 JSON과 PNG를 대조하여 관찰 누락/가림을 검증하라.
> 로컬 실행기의 capture_live_control과 중지 상태를 확인하라. Codex Windows 브리지는 필요 없다. 임의 게임 모델 호출이나 숨은 규칙 제공,
> 기존 세이브 초기화, 무제한 플레이는 하지 마라. 실제 기록을 합성 경험과 섞지 마라.
