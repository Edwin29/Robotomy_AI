# 경험 기록 자동 Git 동기화

MCP 시작 시 별도 수집 프로세스와 Git 게시 프로세스를 시작한다. 플레이어는 MCP를 한 번
연결하면 되며 별도 커밋/푸시 도구를 호출하지 않는다. 이미 실행 중인 MCP에는 운영자가
게시 프로세스를 한 번 시작할 수 있다. 게임 조작·일시정지·재시작은 하지 않는다.

동의한 원격 저장소는 `.robotomy/experience/git-sync.json`의 remote와 비교한다.
enabled=false로 바꾸면 다음 주기부터 게시하지 않는다. 주기는 60초이며 실패 시 다음
주기에 재시도한다. 상태/오류/마지막 커밋은 git-sync-status.json에 남긴다.

같은 원격의 player-experience 브랜치에 vault/Lobotomy-Experience 아래 UTF-8 Markdown,
JSON, JSONL만 게시한다. Media, 이미지, 게임 파일, 세이브, 원장 DB는 제외한다.
개발 코드의 자동 커밋은 하지 않는다. 공개 채팅 원문과 회고는 원격 저장소의 접근 권한을 따른다.

별도 git-publisher 작업 폴더를 사용하므로 개발 checkout의 index/branch/변경은 건드리지
않는다. force push/reset/rebase를 하지 않고 원격 분기 충돌은 오류로 남긴다. 로컬에서
기록을 삭제해도 원격의 기록은 자동 삭제하지 않는다. 실패한 푸시는 커밋을 보존해 재시도한다.
한 PC 내 중복 게시 프로세스는 mutex로 막는다. 인증 창은 띄우지 않으며 인증 실패는 운영자가 해결한다.

동기화 대상은 이미 파일로 투영된 기록이다. 플레이 중 공개 채팅은 자동 갱신되고, 일반
관찰·입력 로그/회고는 기존 종료·회고·내보내기 시점에 투영된다. 이 기능은 아직 SQLite에만
있는 진행 중 기록이나 스크린샷까지 원격 백업한다는 뜻이 아니다. 프레임 성능 보장은 아니며
Git 작업은 게임/MCP 호출과 별도 프로세스에서 진행된다.

## 실제 날짜에 맞는 읽기용 문서

자동 게시 전 `reading_index.project_reading_views`가 Manifest와 기존 Markdown에서
`Playthroughs/Run-XXX/README.md`, `Tutorials/Tutorial-NN-Attempt-NN.md`,
`Main/Day-NN-Attempt-NN.md` 및 대응 채팅 문서를 생성합니다.
본편은 game_day, 튜토리얼은 tutorial_segment를 우선하며 각 종류·날짜별로 시도를 셉니다.
이는 읽기용 투영입니다. SQLite 원장·사건·기억·증거 ID와 기존 Days/Logs는 바꾸지 않습니다.
진행 중 기록은 기존 투영 시점 및 Git 게시 주기에 따라 갱신되며 매 입력마다 전체 재생성하지 않습니다.
과거 파일명의 Day는 날짜로 해석하지 말고 새 README 목차에서 읽습니다.
