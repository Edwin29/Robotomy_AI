# 경험과 기억 기록 절차

역할과 태도는 Player-Persona.md, 정보 사용과 게임기 조작은 AGENTS.md를 따른다.
이 문서는 경험을 언제, 어떻게 저장하고 읽는지를 정한다.

## 시작과 재개

1. `player_experience_status`를 확인한다. 활성 시도가 있으면 기존 ID로 이어간다. 없으면
   `begin_player_attempt(day, player, reason, phase, versions)`로 시도를 연다. 실제 플레이
   관찰과 조작을 시작하기 전에 이 절차를 수행한다. 작성자/모델 표시는 자기 보고다.
2. 최초 튜토리얼은 day=1, phase=tutorial, reason=next_day를 사용한다. 이 날짜는 기록용이며
   정규 게임1일차를 완료했다는 뜻이 아니다. 기존 시도나 진도가 있으면 실제 상황을 따른다.
3. `read_player_memory`로 누적 기억을 읽는다. 원래 작성자의 경험과 자신의 직접 경험을
   구분한다. 사용자 실행 요청의 범위·중단 조건은 시도 시작에 짧은 메모로 남긴다.

**Run은 게임에서 '1일차로 돌아가기'를 사용한 횟수+1이다.** 그 전환에만
reason=return_to_day_one을 쓴다. 재도전은 같은 Run/Day의 Attempt를 늘리고, 기억 저장소
복귀와 모델/채팅 교체만으로 Run을 늘리지 않는다. 플레이어의 기억은 Run을 넘어 이어진다.

## 플레이 중

관찰과 입력 도구가 실제 제공한 응답과 실행 기록을 자동으로 남긴다. 기록 때문에 매번
스페이스를 누르거나 일기를 작성하지 않는다. 이유/예상(rationale/expected)은 선택이며
빈 문자열도 허용한다. 이미 표현한 이유만 당시 이유로 남긴다.

중요한 자발적 의견과 사용자 개입은 `record_player_note`로 남길 수 있다. 대화 전체를
게임기가 자동으로 읽지는 않는다. 사전 지식 개입을 알아차리면 같은 도구에 '사전 지식 개입
가능성', 영향을 받은 선택, 관찰 근거의 유무를 짧게 남긴다. 공략 내용을 장황하게 재현하거나
확인된 사실·교훈으로 승격하지 않는다. 정보 사용 판단 자체는 AGENTS.md를 따른다.

`view_live_frame`으로 제공된 PNG는 보존된다. `capture_live_control`의 경로 제공은
image_delivery=reference_only_not_proof_of_viewing으로 구분된다. 제공·관람·이해는 같은
사실이 아니다. 자동 기록이 모든 화면 프레임이나 내부 사고를 보존하는 것은 아니다.

## 시도 종료와 회고

1. 하루 종료·재도전·기억 저장소 복귀·1일차 복귀·지정 구간 종료의 안전한 경계에서
   `finish_player_attempt`로 시도를 닫는다. completed/failed/abandoned/interrupted 중
   실제 상태를 사용한다. 이 도구는 게임 입력이나 게임 시간 일시정지를 수행하지 않는다.
2. `read_experience_events(attempt_id, query='')`를 첫 페이지부터 has_more=false까지 읽는다.
   성공·실패·변화 없는 행동을 함께 검토한다. preview가 잘렸다면 `read_experience_event`로
   원문을, 필요한 장면은 `view_experience_frame`으로 확인한다.
3. Day-Review-Template.md를 참고하여 `complete_day_review`를 작성한다. 당시 미기록 이유를
   사후 설명으로 채우지 않는다. 다시 보며 새로 발견한 사실은 retrospective_discovery로
   구분한다. 근거 ID는 실제 조회한 사건을 사용한다.

계속할 수 없는 시도는 interrupted로 닫고 남은 근거만 회고한다. 즉시 중단 요청이 있으면
긴 회고 때문에 중단을 늦추지 않는다. 다음 시작에 미완료 시도/회고를 확인한다.

## 회고 필드와 누적 기억

- summary: 자유로운 회고. employee_notes: 선택적인 직원 평가.
- lessons: 실제로 남길 배움·가설·운영 방침이 있을 때 사용한다. 빈 목록도 가능하다.
  basis는 observed/hypothesis/policy/retrospective_discovery 중 하나다.
- experiences: 관심 interest, 취향 preference, 스토리 감상 story, 인상 impression,
  궁금증 question. 각 항목에 text와 evidence_ids를 넣는다. 근거는 감상의 계기이며
  그 감상이 옳다는 증명은 아니다. 행동 변화나 효율 개선은 요구하지 않는다.
- experiences의 remember=false(기본)는 하루 회고에만, true는 누적 기억에도 남긴다.
- 기억을 수정할 때 supersedes로 이전 mem_기억 ID를 참조한다. 감상 수정은 remember=true와
  함께 사용한다. 원래 작성자·기록·근거는 삭제하지 않는다.

```json
{"kind":"story","text":"관람한 장면에 대한 개인적인 감상",
 "evidence_ids":["실제로 조회한 exp_이벤트 ID"],"remember":true}
```

다음 시도는 시작 당시 기억 버전과 설정 문서 해시를 고정한다. 필요하면 플레이 중에도
과거 경험을 검색한다. 다른 모델은 출처 있는 상속 경험으로 읽으며 자신이 직접 플레이했다고
주장하지 않는다. 종료한 기록은 `export_player_experience`로 내보낸다. 자동 Git push는 없다.

## 저장 상태

한 플레이에는 하나의 MCP 기록 호스트를 사용한다. experience_recording.status=queued는
아직 디스크 확정이 아니다. 종료·회고·조회에서 대기 작업을 비우고 실패를 보고한다.
강제 종료 직전 대기 기록은 손실될 수 있다. 기록 오류가 있으면 누락 가능성을 알리고,
기억이나 게임 내부 정보로 빠진 사건을 만들어 채우지 않는다.
# 공개 채팅 발언의 별도 보존

운영자가 이 채팅을 등록한 경우, 공개적으로 출력한 중간 발언과 최종 답변은 별도 수집기가
원문과 시각을 보존한다. 기록만을 위해 같은 말을 매번 메모 도구에 중복 입력하거나
게임을 멈출 필요는 없다. 발언을 강제로 늘릴 필요도 없다. 사적인 내부 추론은 대상이 아니다.
오해와 이후 정정은 각각 보존하며 이전 발언을 지우지 않는다. 수집된 발언은 곧 확정된 지식이 아니다.
새 채팅은 운영자 등록이 필요하다. 기존 메모·종료·회고 절차는 유지한다.
내보내기 뒤에 출력한 최종 답변은 앞서 만든 묶음에 소급 포함되지 않으므로, 그 발언까지
전달할 때는 수집 이후 다시 내보낸 묶음을 사용한다.

