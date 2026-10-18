# 플레이 경험 저장 구조와 운영 — 2026-10-18

사용자가 제공한 `Lobotomy_Player_Experience_Dataset_Structure.md`와 후속 합의를 반영한
구현 기준이다. 원본 첨부는 보존한다. 게임기 장치와 플레이어의 판단 역할을 유지한다.

## 회차와 기억

- **Run = '1일차로 돌아가기' 사용 횟수 + 1**. 게임 회차이며 모델/채팅 정체성이 아니다.
- 재도전은 같은 Run/Day에서 Attempt 증가. 기억 저장소 복귀도 Run은 유지한다.
- 모델·세션 교체는 작성자/버전 기록이며 Run을 증가시키지 않는다.
- Run에 관계없이 관리자 기억은 이어진다. 시작 기억 버전을 각 Attempt에 고정한다.
- 전환은 플레이어가 선언한다. 게임 내부 세이브나 숨은 초기화 상태를 읽어 판정하지 않는다.

```text
vault/Lobotomy-Experience/
├── Config/
│   ├── Player-Persona.md
│   ├── Recording-Rules.md
│   └── Day-Review-Template.md
├── Manifest.json
├── Manager-Memory.md
└── Playthroughs/
    ├── Run-001/
    │   ├── Overview.md
    │   ├── Starting-Memory.md
    │   ├── Employees.md
    │   ├── Days/Day-01-Attempt-01.md
    │   ├── Logs/Day-01-Attempt-01.jsonl
    │   └── Media/<sha256>.png
    └── Run-002/...
```

처음 설정할 때 가짜 Run이나 플레이 경험을 만들지 않는다. 첫 시도 시작 때 폴더를 생성한다.
현재 구현에서 게임 날짜는1..99이며 스토리·배치·튜토리얼 등의 구분은 phase 및 phase_change
메모로 남긴다. 날짜 없는 독립 에피소드 ID는 아직 지원하지 않는다.

## 두 단계 기록

**플레이 중:** 실제 API 응답으로 제공한 관찰, 선택된 과거 자료, 입력 준비/전달/결과,
제공된 화면과 명시된 말만 기록한다. 입력 이유는 선택이며 생략하면 미기록이다.
LLM 요약이나 Markdown 재생성 때문에 게임을 정지하지 않는다. 매 호출별 노트 생성은 제거했다.

**하루 종료 후:** 게임기가 기록을 확정하고 JSONL/Markdown을 만든다. 플레이어가 사건을
시간순 페이지로 검토하고 필요한 원문·화면을 다시 열어 회고를 작성한다. 회고 도구가
LLM을 자동 호출하지 않는다. 연구·일과 결과처럼 안전한 화면에서 플레이어가 수행한다.
실패·중단·되돌리기도 시도를 닫고 회고할 수 있다.

관찰 수집은 플레이어의 주의/이해와 다르다. `*_offered`는 호출자에게 반환할 응답을 만들었다는
뜻이며 네트워크 전달 완료나 모델의 실제 이해를 입증하지 않는다. 스크린샷 경로만 전달한
control_view는 `reference_only_not_proof_of_viewing`으로 표시한다. 판단 근거는 당시 명시한
이유에 한정한다. 회고 시 처음 발견한 단서는 별도 basis로 남긴다.

입력 전달 성공은 작업 성공이 아니다. `input_receipt`와 플레이어의 `outcome` 평가를 분리한다.
화면에서 사라진 개체를 사망으로 자동 변환하지 않는다. 숨은 사망 판정·도구 누적 카운터·
내부 게임 타이머를 경험에 보충하지 않는다. 시각은 벽시계/캡처 시각/프레임을 기록하며,
현재 장치가 제공하지 않는 게임 시간·배속·정지 원인은 추정해 채우지 않는다.

## 저장과 조회

- 원본 원장은 `.robotomy/experience/ledger.sqlite3`. event ID와 전역 seq로 연결한다.
- 플레이 중 원장 쓰기·이미지 해시/저장은 별도 스레드의128개/32MiB 제한 큐에서 수행한다.
  반환값 queued/durable=false는 대기 상태다. 종료·회고·조회에서 flush한다.
- 과부하·디스크 실패는 not_recorded 또는 상태의 recording_errors로 드러내고 오류 파일에
  남긴다. 정상 프로세스 종료는 대기 작업을 비운다. 강제 종료 시 마지막 대기 기록은
  손실될 수 있다. 무손실 실시간 녹화나 모든 프레임 저장을 보장하지 않는다.
- 기존 입력 결과 연결용 observations.jsonl/입력 영수증은 호환용으로 유지한다. 관측은
  max_items/motion_only 적용 후 실제 반환한 선택만 기록한다. 전체 센서 자료를 플레이어가
  본 것으로 간주하지 않는다. 과거 개발 기록은 새 경험 원장으로 자동 이관하지 않는다.
- 기존 짧은 순환 버퍼는 계속 별개다. 게임 정지 중에도 요청된 스토리 화면·메뉴 정보는
  경험 원장에 남으며 자동 버퍼의 정지 정책을 변경하지 않는다.
- 영구 PNG는 내용 해시로 중복 제거하고, 조회·내보내기에서 해시를 검사한다. 화면과 최신
  숫자는 서로 다른 프레임일 수 있으므로 각각 메타데이터를 보존한다.
- Markdown/JSONL은 원장의 출력물이다. 직접 고친 메모를 자동으로 원장에 역수입하지 않는다.
  새 기억은 회고 도구로 쓰고 이전 기억은 supersedes로 연결한다. 원문은 지우지 않는다.
- 한 플레이는 하나의 MCP 기록 프로세스로 운영한다. 동시에 여러 기록 호스트가 시도 경계를
  변경하는 경우의 전역 flush는 제공하지 않는다. SQLite는 개별 트랜잭션을 보호한다.

## MCP 사용 순서

1. `player_experience_status` → 활성 시도가 있으면 이어가기.
2. 새 시도는 `begin_player_attempt(day, player, reason, phase, versions)`.
3. `read_player_memory`. 평소 관찰·입력 도구는 기존대로 사용한다.
4. 선택적으로 `record_player_note(text, author, kind, evidence_ids)`.
5. 종료 화면에서 `finish_player_attempt(attempt_id, status, evidence_ids)`.
6. `read_experience_events(attempt_id, after_seq, limit)`로 전 페이지 검토.
7. `read_experience_event(event_id)` / `view_experience_frame(event_id)`로 근거 재확인.
8. `complete_day_review(attempt_id, author, summary, evidence_ids, lessons, employee_notes, experiences)`.
9. 다음 시도를 시작하거나 `export_player_experience`로 독립 묶음 생성.

lessons의 항목 예시(설명용이며 실제 게임 지식 아님):

```json
{
  "text": "앞선 가설은 아직 확정할 수 없다.",
  "basis": "hypothesis",
  "evidence_ids": ["실제 조회한 exp_이벤트ID"],
  "supersedes": "수정할 기존 mem_기억ID 또는 생략"
}
```

basis는 observed/hypothesis/policy/retrospective_discovery 중 하나다. 없는 근거 ID는
거부한다. 근거와 문장의 의미가 실제로 일치하는지는 플레이어/검토자가 판단해야 한다.
자동 사실 검증·학습 증명은 아니다. 직원 평가도 작성자·근거와 함께 회차별로 유지한다.

## 이전과 Git

### 행동 변화가 없는 경험

`Config/Player-Persona.md`는 게임임을 아는 AI 플레이어와 게임 안의 관리자 역할을 구분한다.
낯선 게임을 알아가는 최초 태도는 이후 기억을 덮어쓰지 않는다. 관심·취향·관람 경험과
조작감·규칙·난이도에 대한 감상도 허용하며 감정·실패·교훈을 강제로 만들지 않는다.
`Config/Day-Review-Template.md`의 모든 감상 항목은 선택이다. lessons=[]여도 회고 가능하다.

experiences 항목: `kind`(interest/preference/story/impression/question), `text`,
`evidence_ids`, `remember`(기본 false), 선택적 `supersedes`(기존 memory ID).
각 감상은 subjective_experience로 표시하고 작성자·시도·시점을 남긴다. evidence는 감상을
유발한 관찰의 출처이며 감정의 참/거짓 판정이 아니다. 효율·교훈·다음 행동은 요구하지 않는다.
remember=false는 해당 하루 회고에, true는 누적 기억에도 남긴다. 감상을 바꿀 때는
remember=true와 supersedes를 사용하며 원래 감상을 삭제하지 않는다. 잘못된 근거나
기억 ID가 하나라도 있으면 회고 전체 트랜잭션을 취소한다. 기존 경험 파일은 호환된다.

### 별도 플레이어 입구

문서 책임은 다음과 같다. 플레이어에게 개발 보고서를 읽게 하지 않는다.

| 원본 문서 | 담당 내용 |
|---|---|
| config/player/AGENTS.md | 프로젝트 목적, 사전 지식/공략 제한, 게임기 사용, 중단 규칙 |
| vault/Lobotomy-Experience/Config/Player-Persona.md | 관점·최초 성향·경험 태도 |
| vault/Lobotomy-Experience/Config/Recording-Rules.md | 시작/종료·Run·기록·회고 필드·기억 이전 |
| vault/Lobotomy-Experience/Config/Day-Review-Template.md | 선택적 회고 질문 |
| config/player/RUN-PROMPT.md | 이번 플레이 범위와 종료 조건 |
| config/player/START-HERE.md | 운영자의 시작·관찰·중지 안내와 실행 프롬프트 링크 |

개발 저장소 루트 AGENTS.md는 엔지니어 전용이며 플레이어 규칙과 별개다. 배포 폴더의
AGENTS/START-HERE/RUN-PROMPT는 위 원본의 사본이다. 변경 시 비교 후 동기화하고 임의의
사용자 변경은 덮어쓰지 않는다. 나머지 문서는 MCP에서 원본을 반환한다. 지침 전문을 서버
instructions나 실행 프롬프트에 반복하지 않고 문서 읽기로 연결한다.

운영자는 `scripts/setup_player_workspace.py D:\Projects\Robotomy_Player`로 개발 저장소 밖에
새 폴더를 만들 수 있다. 기존 폴더를 덮어쓰지 않는다. 실제 이 PC에는 해당 폴더를 구성했다.
그 폴더의 START-HERE.md와 AGENTS.md에는 게임 공략 대신 도구·기록 사용 절차만 있다.
`scripts/run_player_mcp.py`는 실제 게임/기억용 도구21개를 노출하고 모의 세션·개발 타임라인은
제외한다. read_player_guide로 AGENTS를 포함한 네 문서를 제공한다. 전체 개발 MCP는32개다.
시도 시작 config_versions에는 네 문서 해시가 들어가며 내보내기 Config/에도 네 문서를
포함한다. 내보낸 AGENTS는 역사적 설정 자료이며 받는 모델의 호스트 지침을 대체하지 않는다.

Ready-Player.cmd는 운영자용이며 무결성·실행본·최신 화면·미해결 입력을 점검하고 입력을
허용한다. 게임이 없으면 scripts/launch_live.py를 통해서만 실행한다. Stop-Player.cmd는
입력을 차단하며 게임 시간 정지는 아니다. 실제 플레이어 MCP에는 운영자 중지 해제 도구가 없다.
폴더/프롬프트 분리는 OS 파일 접근을 강제 차단하지 않는다. 다른 MCP/터미널 사용 제한은
플레이어 지침이며 완전한 보안 샌드박스로 주장하지 않는다. 플레이는 한 MCP 호스트만 사용한다.

### 내보내기

내보내기는 시도를 닫고 실행한다. 원장 출력물·설정 문서·참조된 PNG만 선별해 복사하고
Bundle.json에 파일 해시를 남긴다. 원본 게임·세이브·SQLite는 포함하지 않는다. 다른 모델은
같은 게임기의 기억 조회 도구를 쓰거나 이 묶음을 읽을 수 있다. 외부 묶음을 현재 SQLite로
자동 병합하는 도구는 아직 없으며, 출처를 보존한 자료 열람이 현재 이전 방식이다.

Markdown/JSONL/Manifest는 일반 Git 대상, 미디어·DB·내보내기 사본은 기본 제외다.
자동 커밋/push나 LFS 업로드는 하지 않는다. Git 없이도 원장과 시도 시작 스냅샷으로 기억
변화를 보존한다. 해시는 변조 검출용이며 작성자의 신원 인증 수단이 아니다.

## 검증 경계

임시 루트에서 회차/재도전, 선택된 관측만 보존, 비동기 저장, 큐 포화/쓰기 실패,
기억 정정/근거 검증, 페이지 조회, PNG 중복/해시, 내보내기와 MCP 왕복을 검사한다.
합성 시험을 실제 하루 플레이나 경험 학습으로 주장하지 않는다. 이번 설정은 게임 입력,
원본 세이브 변경, 게임 DLL 재배포 또는 유료 모델 호출이 필요하지 않다.
