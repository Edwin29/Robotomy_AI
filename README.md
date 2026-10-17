# Robotomy AI

LLM이 주요 판단을 내리고 실행기가 조작하며, 판단과 경험을 관찰·대화·이전할 수 있는
Lobotomy Corporation 플레이어 프로젝트.

**현재 버전: v0.1 기초 환경. 실제 게임 연결은 아직 구현하지 않았습니다.**
MCP와 기록·대화·기억 이전은 실행 가능하며, `mock`은 실제 게임 규칙과 무관한 합성 테스트입니다.
게임 클리어, 실제 모델의 학습, GPT↔Claude 행동 동일성을 검증한 버전이 아닙니다.

## 지금 되는 것

- 로컬 stdio MCP: 모델 서비스 API 키 없이 Codex 등 MCP 클라이언트에 도구 제공
- 관찰 → 실행 전 판단 → 실행 결과 → 회고의 분리된 기록
- 사람의 질문/방침 변경, 근거를 연결한 답변, 운영자 일시정지/재개
- 행동 횟수 제한, 오래된 판단 거부, 모의 명령 중복 실행 방지
- Obsidian에서 읽는 세션 기록, SHA-256 검사 가능한 모델 독립 JSON 내보내기/가져오기
- 선택한 이전 경험만 조회: 자신의 경험과 전해 받은 경험을 구분
- 게임 설치 파일 존재 여부만 확인하는 읽기 전용 진단

## 빠른 시작 — Windows PowerShell

Python 3.11 이상. 저장소 루트에서 실행합니다.

```powershell
python -m venv .venv
.\.venv\Scripts\python.exe -m pip install -r requirements.lock.txt
.\.venv\Scripts\python.exe -m robotomy doctor
.\.venv\Scripts\python.exe -m robotomy demo
.\.venv\Scripts\python.exe scripts\configure_local.py
```

`demo`는 미리 작성된 모의 행동 두 번을 실행합니다. LLM 호출이나 실제 게임 실행이 아닙니다.
출력의 `vault_note`를 열면 판단과 대화 예시를 볼 수 있습니다.

`configure_local.py`는 **이 프로젝트의** `.codex/config.toml`만 생성합니다.
기존 파일이 있으면 덮어쓰지 않습니다. 경로 변경/다른 PC에서는 내용을 확인해 다시 설정하세요.
설정 파일은 절대 경로를 포함하므로 Git에서 제외됩니다. 전역 MCP 설정은 변경하지 않습니다.

Codex에서 이 폴더를 프로젝트로 열고 신뢰한 뒤 새 채팅 또는 클라이언트 재연결로
`robotomy` MCP의 도구 노출을 확인하세요. 현재 대화에 자동으로 추가됐다고 가정하지 않습니다.
클라이언트별 STDIO 지원은 다르며, ChatGPT 웹용 공개 플러그인은 아직 제공하지 않습니다.

모의 플레이 시작 지시문: [prompts/player-mock.md](prompts/player-mock.md)

## 판단 관찰과 대화

```powershell
.\.venv\Scripts\python.exe -m robotomy sessions
.\.venv\Scripts\python.exe -m robotomy watch SESSION_ID --follow
```

다른 터미널에서 질문 또는 전략 변경을 보낼 수 있습니다.

```powershell
.\.venv\Scripts\python.exe -m robotomy message SESSION_ID "왜 그 행동을 선택했어?"
.\.venv\Scripts\python.exe -m robotomy message SESSION_ID "진행 속도보다 손실 방지를 우선해줘" --kind steer
.\.venv\Scripts\python.exe -m robotomy pause SESSION_ID
.\.venv\Scripts\python.exe -m robotomy resume SESSION_ID
.\.venv\Scripts\python.exe -m robotomy checkpoint SESSION_ID
```

메시지는 다음 관찰/타임라인 조회 때 전달됩니다. MCP 서버 자체가 모델을 깨우거나 자동 답변하지는 않습니다.
모델이 실행 중이면 다음 판단 경계에서 읽고 `reply_to_human`으로 답합니다.
모델이 멈췄다면 같은 채팅에 “대기 중인 질문을 읽고 답해줘”라고 알려 주세요.
`question`은 실행 대기 중인 판단을 취소하지 않으며, `steer`와 pause/resume은 취소합니다.
일시정지 중에도 기록 조회와 답변은 가능합니다. 이미 완료된 행동을 되돌리지는 않습니다.

## Obsidian과 Git

Obsidian의 **Open folder as vault**로 이 저장소의 `vault` 폴더를 엽니다.

| 경로 | 역할 | Git |
|---|---|---|
| `robotomy/`, `tests/`, `docs/`, `prompts/` | 코드와 프로토콜, 지시문 | 추적 |
| `vault/Player/`, `vault/Experiences/`, `vault/Templates/` | 플레이어 상태 양식·검토된 경험 | 추적 |
| `vault/Sessions/` | 자동 생성되는 전체 세션 노트 | 기본 제외 |
| `.robotomy/` | SQLite 실행 원장과 가져온 경험 | 제외 |
| `exports/` | 모델 간 전달할 JSON 스냅샷 | 기본 제외 |
| `media/`, `saves/` | 향후 영상·이미지·세이브 백업 | 제외 |

처음에는 **같은 레포 안의 별도 Vault**를 권합니다. 코드/관찰 형식/기억 형식의 버전을 같이 맞출 수 있습니다.
여러 게임·여러 플레이어로 확대되거나 저장소 접근 권한/용량이 달라질 때 Vault를 분리하세요.
전체 로그를 매번 Git에 넣지는 않습니다. 검토 후 경험 노트와 필요한 근거를 명시적으로 추가합니다.
절차와 분리 기준: [docs/experience-storage.md](docs/experience-storage.md).

## 다른 모델로 경험 전달

```powershell
.\.venv\Scripts\python.exe -m robotomy checkpoint SESSION_ID
.\.venv\Scripts\python.exe -m robotomy import 'C:\path\to\BUNDLE.json'
```

새 모델의 `start_session`에 반환된 `bundle_id`를 `inherited_bundle_ids`로 전달합니다.
그 모델은 `search_memory`로 원래 모델의 판단·회고를 검색할 수 있습니다.
파일 전송은 자동 모델 학습이나 동일 행동 보장을 뜻하지 않습니다.
현재는 모의 경험 형식만 허용하며, 실제 게임 경험 형식은 실게임 연결 단계에서 확장합니다.
절차: [prompts/recipient.md](prompts/recipient.md).

## 검증

```powershell
.\.venv\Scripts\python.exe -m unittest discover -s tests -p 'test_*.py' -v
.\.venv\Scripts\python.exe tests\mcp_smoke.py
```

## 다음 단계

1. [기초 설계](docs/architecture.md)와 [실험 설계](docs/experiments.md) 검토
2. [실제 게임 연결 계획](docs/live-adapter.md)에 따라 먼저 플레이어에게 보이는 상태 읽기 검증
3. 테스트 세이브에서 단일 명령 → 결과 연결 검증
4. 짧은 실제 플레이 후 경험 전달 효과 비교
5. 그 뒤 장기 클리어 시도

“클리어하라”만 주는 실험은 탐색 기준선으로 가치가 있습니다. 다만 최소 조작 수단과 기록 장치가
없으면 도구를 만드는 능력과 게임을 플레이하는 능력이 뒤섞입니다.
[제약을 최소화한 플레이 지시문 초안](prompts/player-baseline.md)은 실제 연결 검증 후 사용합니다.

현재는 유료 모델 요청, 게임 실행, 모드 설치, 세이브 수정, 장기 goal 실행을 하지 않습니다.
