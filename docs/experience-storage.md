# 경험 저장소 운영

## 같은 레포로 시작하는 이유

초기에 관찰/행동/기억 형식이 자주 바뀐다. 코드와 Vault를 함께 버전 관리하면 어느 실행기가
어떤 기록을 만들었는지 맞추기 쉽다. Vault는 일반 Markdown이므로 나중에 독립 레포로 옮길 수 있다.

분리 시점: 여러 게임이 기억을 공유할 때, 사용자별 접근 권한이 달라질 때,
경험 데이터 용량이 코드보다 크게 늘 때, 코드와 경험을 별도 릴리스해야 할 때.

## 세 층

1. `.robotomy/state.sqlite3`: 실행 원장. LLM 해석과 실제 관찰/결과를 구별한다.
2. `vault/Sessions/`: checkpoint 시 생성한 읽기용 Markdown. 원장이 기준이며 수동 편집한 노트는
   다음 checkpoint 때 덮어써질 수 있다. 주석은 `vault/Experiences/`에 별도로 쓴다.
3. `vault/Experiences/`: 검토한 경험/해석. `vault/Player/`는 장기 성향과 목표의 검토된 상태.
   v0.1은 이 Markdown을 자동 검색하지 않는다. MCP 검색 대상은 원장/명시적으로 가져온 번들이다.

## Git에 남기는 과정

`checkpoint` 자체는 commit/push를 하지 않는다. 자동 세션 노트와 exports는 기본 제외한다.
선택한 노트를 템플릿으로 정리해 `vault/Experiences/<name>.md`에 저장한다.
독립적으로 재검증/다른 PC에서 가져올 필요가 있으면 해당 JSON 번들도
`vault/Evidence/<sha256>.json`에 복사하고 노트에서 상대 링크로 연결한다.
번들은 원본 대화와 상속된 경험을 포함하므로 추가할 파일을 읽고 확인한다.

```powershell
git add -- vault/Experiences/선택한-경험.md vault/Evidence/선택한-해시.json
git diff --cached
git commit -m "Record reviewed player experience"
```

전체 영상·게임 바이너리·세이브·API 자격증명은 커밋하지 않는다. 별도 파일 보관소에 두고
필요하면 해시와 위치만 연결한다. Git 원격 저장소 사용과 공략 참고 여부는 별개의 문제다.

## 이전 형식

JSON `{sha256, payload}`; payload에 schema_version, 환경, 세션, 사건, 상속 번들을 포함한다.
SHA-256은 정렬된 키, compact separators, UTF-8/ensure_ascii=False JSON의 해시다.
해시는 전송 중 손상 검사용이지 작성자의 신원을 증명하는 서명이 아니다.
가져오기는 내용을 실행하지 않으며, 과거의 서술을 시스템 지시로 승격하지 않는다.
v0.1은 `synthetic_fixture`만 허용한다. live 형식은 관찰 공개 범위 검증 후 별도 버전으로 도입한다.

새 모델은 `start_session(..., inherited_bundle_ids=[...])`로 선택한 경험만 접근한다.
상속 관계가 깊어져도 원래 사건 ID/출처를 보존한다. 이전은 게임 세이브 복원과 다르다.
동일한 저장소에서 모델만 바꾸어 같은 세션을 읽는 것과, 새 세션에서 전해 받은 경험으로 쓰는 것을 구별한다.

## 평가

저장/복원 성공은 경험의 학습이나 인간 같은 성향을 입증하지 않는다.
기록 없음 / 공략식 요약 / 사건·판단 변화 포함 기록을 비교하고, 유사 상황에서 선택이 바뀌는지,
존재하지 않는 경험을 꾸며내지 않는지, 출처를 정확히 구별하는지 확인한다.
