# Lobotomy AI — 새 협업자를 위한 프로젝트 배경

기준일: 2026-10-19. 기존 Codex와 함께 프로젝트에 참여할 Claude Code에게 전달하는 사전지식이다. 작업 분담, 협업 규칙, 첫 과제는 이 문서에서 정하지 않는다. 구현 상태와 PID 등은 아래 확인 시점의 정보다.

## 프로젝트의 목적

Lobotomy Corporation을 AI가 직접 관찰하고 조작할 수 있는 로컬 ‘AI 전용 게임기’를 만들고 있다. 단순히 게임을 빨리 클리어하는 자동화가 최종 목적은 아니다. AI가 공략 없이 게임을 배우고, 판단·실수·오해와 정정·취향·스토리 감상을 쌓는 과정을 관찰하고 싶다는 사용자 의도에서 시작했다.

장기적으로는 숙련 플레이어의 경험과 성향을 기록하고 다른 모델에도 전달하는 일종의 디지털 트윈을 지향한다. 현재 모델 간 이전 대상은 모델 내부 가중치나 주관적 경험 자체가 아니라, 출처가 연결된 관찰·행동·감상·기억이다. 이런 기록 이전이 실제로 얼마나 효과적인지는 별도 검증 과제다.

사용자는 기존 게임의 헤비유저이며, 실제 플레이 난이도·연출·관찰 기믹을 잘 알고 있다. 개발자 역할의 Codex와 실제 게임을 하는 플레이어 AI는 구분되어 있다. Claude Code는 개발 협업자로 합류하는 맥락이다. 프로젝트 전체를 넘기는 것은 아니다.

## 지금까지 정한 제품 방향

**게임기는 장치, 판단은 플레이어가 담당한다.** 게임기는 영상·소리·최종 표시 정보·입력·기억 장치를 제공한다. 플레이어가 전략과 선택, 해석과 감상을 맡는다.

- Computer Use를 매번 호출하는 방식은 비용과 지연 때문에 피하려고 했다. 현재 입력은 게임 내부 가상 키보드·마우스로 연결하며, 사용자 OS 마우스와 분리된 가상 포인터가 있다.
- 화면에 표시되는 Text/Graphic과 렌더링 정보를 직접 읽는 방식을 사용한다. OCR이나 비전 모델로 모든 화면을 매번 다시 해석할 필요는 없다는 방향이다. 다만 이미지가 중요한 장면, 스토리, 애니메이션·연출에는 실제 화면이 필요하다.
- 영상, 수치, 소리의 전달 주기를 같게 맞출 필요는 없다. 운영 중에는 diff 중심으로 읽고 필요할 때 이미지를 확인하는 방식으로 지연을 줄이고 있다.
- 소리는 사람이 듣는 방식과 완전히 같을 필요는 없으며, 출력된 소리 이벤트와 의미를 전달하는 절충을 택했다. 트럼펫과 클리포트 폭주, 기타 주요 소리 매칭을 다루고 있다.
- 화면 속도 벡터는 개체 이동과 카메라 이동을 구분해서 제공하려는 기능이다. 개체의 내부 목표나 이동 경로를 알려주는 기능은 아니다.
- 최근 관찰을 개수 제한 버퍼로 보관하는 방향을 택했다. 사용자는 일정 주기 캡처라면 개수로 보존 분량을 관리하면 된다고 판단했다. 일시정지 중 동일 화면이 과거 버퍼를 밀어내지 않는 것도 요구사항이다.
- 초 단위 반응과 멀티태스킹이 중요하다. 일반 구간에서는 게임 내 일시정지를 활용할 수 있지만, 일부 상황은 정지가 제한된다.
- 짧은 비동기 입력 예약은 구현되어 있다. 플레이어가 정한 순서를 실행하며 취소·대상 유효성 확인을 지원하는 방향이다. 상황 판단을 대신하는 범용 자동 전략과는 구분된다.
- 별도로 논의했던 스크래치형 제한 자동화 블록은 **보류** 상태다.
- 게임은 CPU 병목이 크다는 사용자 경험이 있다. GPU 활용과 캡처·계산·출판의 병렬화를 선호하지만, 실제 구현의 메인 스레드 작업과 성능은 각각 확인해야 한다.
- 무료 도구·모델을 선호한다. 사용자는 Codex Pro 5x를 구독하고 있고, 추가 지출 가능액으로 약 3만원을 언급했다.

## 정보 공개와 플레이 경험에 관한 배경

플레이어에게 인간 플레이어와 같은 범위의 정보를 주는 것이 중요한 설계 목표다. 게임 화면이 시설 CCTV라는 설정이고, 화면을 가리거나 왜곡하는 기믹도 게임 경험에 포함된다. 내부 데이터를 그대로 전달하면 이런 기믹을 무력화할 수 있다.

반대로 내부 자료를 활용하는 행위 자체를 금지한 것은 아니다. 실제 표시된 정보나 보이는 물체의 기하를 활용해 계산 부담을 줄이는 것은 환영한다. 문제는 화면에 보이지 않는 사실을 추가하거나, 표시된 정보를 과도한 판정으로 누락하는 것이다.

예를 들어 HP/SP 표시에는 진행·해금 맥락이 있고, 도구형 환상체의 누적 사용 횟수는 플레이어가 직접 세거나 정보 해금 조건으로 짐작하는 요소다. 내부에 카운터가 있다는 이유로 이를 별도 표시하면 의도된 경험이 달라진다. 공격의 정확한 내부 타이머·숨은 목표 등도 같은 문제가 있다.

플레이어에게 공략·위키·개발 분석을 주지 않고 관찰과 경험으로 배우게 하려는 의도다. ‘인터넷 차단’은 처음에는 공략을 보지 않는 플레이어의 비유였으며, 현재 프롬프트만으로 사전학습 지식이나 OS 접근이 완전히 차단된다고 주장하지 않는다.

플레이어는 자신이 게임을 한다는 것을 안다. 시설 관리자 역할에 몰입할 수 있지만 반드시 관리자 말투로 업무 보고를 해야 하는 것은 아니다. 효율·교훈뿐 아니라 관심, 취향, 애착, 이야기 감상처럼 행동 변화로 이어지지 않는 경험도 남기길 원한다. 감정이나 실패를 일부러 연출하는 것은 목적이 아니다.

기록은 공개 채팅의 판단·감상·정정 원문과 자동 관찰/입력 기록을 모으고, 하루나 시도 종료 시 회고로 정리하는 구조다. 매번 정지하고 장문을 기록하는 방식은 플레이를 늦추므로 원하지 않는다. 과거 오해는 삭제하지 않고 이후 정정과 연결한다.

기록 용어에서 **Run은 게임의 ‘1일차로 돌아가기’ 횟수 + 1**이다. 모델이나 세션 교체 횟수가 아니다. 튜토리얼과 본편 Day를 구분하고, 같은 날의 재시도는 Attempt로 남긴다. 기록 저장소는 Obsidian 호환 Markdown과 구조화 기록을 사용하며 Git 자동 동기화 기능도 있다.

## 로컬 구성과 주요 경로

| 위치 | 용도 |
|---|---|
| `D:\Projects\Robotomy_AI` | 메인 개발 저장소. GitHub: `https://github.com/Edwin29/Robotomy_AI` |
| `D:\Projects\Robotomy_Player` | 실제 플레이어 AI의 시작 공간과 지침 |
| `D:\Projects\Robotomy_Lab` | 별도 검증 게임과 소스 사본 |
| `D:\SteamLibrary\steamapps\common\LobotomyCorp` | 원래 설치 게임 |
| 메인 `.robotomy/runtime/LobotomyCorp` | 실제 플레이용 분리 실행본 |
| Lab `.robotomy/runtime/LobotomyCorp` | 검증용 분리 실행본 |
| `D:\NVIDIA\Lobotomycorp` | 사용자가 녹화 영상을 저장하는 위치 |
| 메인 `vault/Lobotomy-Experience` | 경험 기록과 페르소나·회고 설정 |
| 메인 `.robotomy/analysis` | 게임 디컴파일과 기존 분석 자료 |

이 Codex 대화의 원래 cwd인 `D:\Projects\PM_Simul`은 대상 프로젝트가 아니다.

Python 3.11 이상과 Unity C# 모드가 중심이다. 메인 `.venv`에 MCP/UnityPy 등 개발 의존성이 있다. Lab `.venv`는 런처용 최소 환경으로, 분석 때에는 메인 Python을 사용해 왔다. 실제 게임 자료와 런타임 DB 등은 Git에 포함되지 않으므로 GitHub 내용만으로 로컬 상태를 모두 재현할 수 없다.

작성 시 Git은 `main`, HEAD `285bbd8`이며 미커밋 수정과 untracked 파일이 많다. 현재 작업 상태는 HEAD나 GitHub만으로 설명되지 않는다.

## 주요 코드의 역할

| 파일/영역 | 책임 |
|---|---|
| `mods/RobotomyObserver/Observer.cs` | Unity 관찰 수집과 출판의 진입점 |
| `ConsoleUI.cs`, `ConsolePanels.cs`, `ConsoleDisclosure.cs` | UI 표시 정보 추출, 패널 연결, 공개 정보 범위 |
| `ConsoleMotion.cs`, `MotionTargets.cs`, `MotionSurface.cs`, `MotionStencil.cs`, `MotionCanvasGeometry.cs` | 표시 개체 후보와 표면/가림 판정, 화면 속도 벡터 |
| `VirtualInput.cs`, `VirtualCursor.cs` | 게임 내부 가상 입력과 포인터 |
| `ConsoleAudio.cs`, `ConsoleSoundCatalog.cs` | 소리 이벤트와 의미 매칭 |
| `ConsoleHistory.cs`, `ConsolePublisher.cs` | 관찰 버퍼와 파일 출판 |
| `robotomy/live.py`, `history.py`, `virtual_input.py`, `input_sequence.py` | 관찰 읽기, 입력 검증·실행, 비동기 예약 |
| `robotomy/reload_host.py`, `scripts/run_player_mcp.py` | 플레이어 MCP 호스트와 코드 재로딩 |
| `robotomy/experience.py`, `chat_capture.py`, `git_sync.py` | 경험 기록, 공개 채팅 원문, Git 동기화 |
| `scripts/prepare_live.py`, `launch_live.py`, `start_game_task.ps1` | 실행본 준비·무결성·독립 프로세스 수명 |

현재 게임은 Windows 예약 작업을 통해 Codex/MCP와 별도 수명으로 실행된다. Codex를 종료해도 게임이 유지되도록 이전에 변경했다. Python 일부 모듈은 MCP에서 자동 재로딩되므로 운영 경로의 소스 변경이 실행 중 플레이에도 영향을 줄 수 있다. 게임 모드 DLL 변경은 별도 빌드/게임 재실행 영역이다.

`Lobotomy_Observer`는 실제 플레이용 게임 창이며 사용자가 관람·녹화한다. `127.0.0.1:8765` 관찰 웹페이지와 혼동되었던 이력이 있다. 사용자는 게임 창의 비율은 고정하되 크기를 조절하길 원했다. 운영자 입력 차단 상태 `PAUSED`와 게임 내 시간 일시정지는 별개다.

## 현재 후보 패치와 검증 환경

운영 소스, 후보 패치, Lab은 동일한 내용이 아니다.

- 메인 `mods/`, `robotomy/`: 운영 경로와 연결된 작업본. 후보 변경이 전부 반영된 것은 아니다.
- 메인 `.robotomy/patches/display-controls-20261019/`: 본편 벡터·예약 대상·일시정지/배속 후보 패치. **실기 수용 실패, 미배포** 상태다.
- Lab 소스: 후보 패치 외에 검증용 identity·저장 경로·가드·진단 변경도 포함한다. 운영본으로 그대로 복사할 수 있는 배포본이 아니다.

Lab은 이전의 5일차 완료/6일차 준비 백업으로 검증했다. 마지막에는 본편 6일차 작업 선택창을 연 상태에서 게임 일시정지와 입력 차단을 해두었다. 작성 시 운영 PID는 10260, Lab PID는 39516으로 확인됐다. 이는 해당 시점의 식별값이다.

Lab 게임 파일 약 5GB와 분석 자료는 D에 있다. 실제 검증 저장 경로는 `C:\Users\왕원철\AppData\LocalLow\Robotomy_LabPhysical\Lobotomy_Lab_Observer`다. 옛 LocalLow/Robotomy_Lab junction은 남아 있지만 현재 사용하지 않는다.

외부에서 복사한 저장 파일을 Python은 읽지만 Unity Mono는 찾지 못한 문제가 있었다. 정확한 원인은 미확정이다. 검증 전용 `LabDiagnostics`가 초기 백업 dat 3개를 자기 persistentDataPath에 한 번 복사한 후 정상 로딩됐다. `lab-seeded.txt` marker가 재복사를 막는다. 이 진단/초기화는 검증본에만 있다.

최근 검증에서 기존 세이브 6개 파일 해시가 같았고, 원래 설치 파일 29개 및 설정·메타데이터 무결성 검사도 통과했다. 기존 플레이와 NVIDIA 녹화 제어에는 개입하지 않았다.

## 최근 발견한 버그와 조사 결과

자세한 근거는 [원인 조사 보고서](display-root-cause-audit-20261019.md)에 있다. 아래는 Codex의 기존 조사 결과이며 새 협업자가 독립적으로 검토할 수 있는 주장들이다. 수정 완료 상태가 아니다.

| 항목 | 확인된 현상·원인 | 아직 남은 부분 |
|---|---|---|
| 배속 표시·예약 대상 누락 | 실제 네 버튼은 Animation 방식, targetGraphic은 투명한 부모. 보이는 InnerFill/Icon은 자식. 게임기는 ColorTint와 불투명 targetGraphic을 요구했음 | 선택·hover·blocked 상태를 실제 표시와 연결하는 수정 |
| 직원 HP 누락 | 글자 경계에 붙인 0.5px 여백이 SP 막대와 약 0.06px 겹치자 HP 전체를 가려졌다고 판정 | 실제 표시 기하와 여유 경계를 구분하는 수정 |
| 직원 벡터 누락 | 몸통은 보여도 약 1.6px인 입 부품이 2px 기준에 미달하면 캐릭터 전체 탈락 | 개체 일부 부품의 탈락을 전체 비가시성으로 확대하지 않는 구조 |
| 본편 정상 화면 거절 | Glow 클래스 기본값과 게임이 실제 Main에서 설정하는 값이 달랐음 | 실제 정상값 및 변형 효과 경계 반영 |
| 환상체 벡터 | surface_patch_edge/texture_alpha로 탈락. 현재 표면 조건이 매우 강함 | 각 환상체의 구체적인 실패 메시/픽셀은 미확정 |
| 예약 입력 | 순서 실행, 현재 제스처 종료 후 취소, 사라진 직원 행 중단은 실기 성공 | 메뉴 종료→배속 버튼 계속 실행은 버튼 누락으로 미검증 |
| 가림 | Escape 메뉴 뒤 직원 행은 차단되고 닫으면 복귀 | Escape 메뉴 자체 정보 누락, 보스/부분 가림 전체 범위 미검증 |
| 화면 동기화 | 입력 직후 프레임/메타데이터 세대 불일치 표본 존재 | 직접 원인과 수정은 미확정 |

HP의 원인을 처음에는 ‘투명 이미지의 큰 사각형’으로 의심했으나, 실제 재현 표본에서는 **게임기가 추가한 글자 여백의 미세 겹침**으로 좁혀졌다. 이전 추정과 최신 확인 결과가 다르다.

단위 테스트는 HP/SP가 이미 추출된 가상 JSON, 인공 알파 배열, 구현이 가정한 렌더 값 등을 검증했다. 실제 Animation 버튼, 투명 입력 부모, 좁은 HP/SP 배치, 작은 Spine 부품을 충분히 포함하지 못했다. 테스트 통과와 실기 정상 작동 사이에 간극이 있었다.

사용자의 가장 최근 강조점은 ‘게임 구조를 충분히 확인하고 구현할 것’이다. 코드 일부를 읽고 일반적인 Unity 동작일 것이라고 추정하면 오래된 게임의 실제 구성과 어긋날 수 있다는 지적이었다. 이 내용은 기존 프로젝트 AGENTS.md에도 반영되어 있다.

## 분석 자료와 읽을거리

현재 문제의 자료:

- 메인 [docs/display-root-cause-audit-20261019.md](display-root-cause-audit-20261019.md)
- `D:\Projects\Robotomy_Lab\VALIDATION-REPORT.md`, `LAB-README.md`
- Lab `.robotomy/verification/root-cause/resolved-ui.json`: Main scene의 실제 UI 참조·설정
- 같은 폴더의 `speed-animator.json`, `*-clip.json`: 배속 애니메이션
- `runtime-display-audit.json`, `runtime-diagnostics.json`: 실행 중 경계·색·부품 좌표·거절 원인
- Lab `.robotomy/verification/`의 PNG/동명 JSON: rows, covered, uncovered, speed1, speed15, speed2, speedpause, audit-rows
- 같은 폴더의 ordered-sequence.json, cancel-sequence.json, row-sequence.json
- Lab `audit_display_assets.py`, `mods/RobotomyObserver/LabDisplayAudit.cs`: 에셋 추출·실행 진단 코드
- 메인 `.robotomy/analysis/Assembly-CSharp.decompiled.cs`, `Assembly-CSharp-firstpass.decompiled.cs`: 기존 게임 분석

관련 설명 문서:

- [게임기 설계](ai-console-design.md)
- [실제 입력](live-control.md)
- [MCP 재로딩](player-plugin-reload.md)
- [게임 프로세스 수명](game-process-lifetime.md)
- [공개 정보 경계](disclosure-implementation.md)
- [비동기 입력](async-input-sequence.md)
- [경험 기록](player-experience-dataset.md)

기존 `docs/handoff.md`와 `architecture.md`에는 과거 단계의 PID·도구 개수·미구현 설명이 섞여 있다. 최신 상태 전체를 나타내는 단일 명세는 아니다. 특히 ‘준비 완료’였던 후보 패치가 후속 실기에서 실패한 이력이 있다.
