# Lobotomy × AI_Persona_Pre 결합 검토 — Claude 의견 (2026-10-21)

작성: Claude (조언 역할). 코드·설정·게임은 건드리지 않았다. 두 저장소는 읽기 전용으로 받아서 읽었다.

- `Edwin29/AI_Persona_Pre` main `5a69403` (2026-08-29): README, `docs/status.yaml`, 로드맵, 아키텍처 개요, `AGENTS.md`, 일부 소스
- `Edwin29/History` main `75568bd` (2026-10-20): `AI/아이디어/` 전체. 특히 「인격과 의식, 사회적인 합의에 대하여」, 「전체 구조 맵 v5」, 「경험과 성장에 대하여」, 「트리거」, 「Draft」, 「context 관련」, 「도메인 확장」. 「기억」, 「ES-Mem」, 「ReAct Cognition」, 「추상적 목표」는 목차와 요지만 읽었다.

앞 문서: [로컬 플레이어 도입 방법](claude-local-player-adoption-20261021.md). 거기서 제안한 "얇은 전용 실행기"는 이 문서의 결론에 따라 바뀐다.

## 결론 먼저

1. **게임기는 Lobotomy, 플레이어는 Persona Foundation으로 나누는 것이 맞다.**
   v5 구조 맵의 말로 하면, Lobotomy Corporation은 External World의 Game Room 활동이고, Lobotomy는 그 환경의 Port·Adapter와 외부 활동 실행 상태다.
   판단·기억·자기 해석은 Persona의 Agent Plane이 가진다. 두 프로젝트가 이미 각자 이렇게 선언하고 있다.
   Lobotomy는 "게임기는 관찰·입력·기록, 판단은 플레이어"라고 하고, v5는 "Foundation은 실행과 사실, Agent Plane은 의미와 기억"이라고 한다.
2. **앞 문서의 "얇은 전용 실행기"는 새로 만들지 말고 Persona Foundation을 그 자리에 쓴다.**
   필요한 것(OpenAI 호환 로컬 모델 연결, 호출 전 최종 요청 저장, 취소·복구, SQLite 사건 기록, 추론 스케줄러, Research Inspector, 휴대폰으로 개입하는 Chat Web)이 이미 검증되어 있다.
   Lobotomy 안에 실행기를 따로 만들면 같은 기반을 두 번 만들게 된다.
3. **다만 지금의 Persona Foundation은 대화 프로그램이라 게임을 바로 플레이할 수 없다.** 빠진 것이 다섯 가지 있다(3절). 그중 둘은 Persona의 정식 계약과 충돌하므로 사용자 결정이 필요하다.
4. **플레이어 정체성의 기준을 다시 정해야 한다.** History 문서의 정의(인격 = 모델 + 기억 + 자기모델 + 역사 + 환경)를 따르면, 정체성은 모델이 아니라 Persona에 붙는다. 그러면 "판단 모델 하나" 조건의 의미가 바뀐다(5절).

## 1. 두 프로젝트의 현재 위치

| | Robotomy_AI | AI_Persona_Pre |
|---|---|---|
| 성격 | 게임 관찰·입력·기록 장치 + 경험 기록 | 로컬 LLM 대화 기반 프로그램 (인격 연구의 기반) |
| 완료된 것 | 실제 게임 관찰·가상 입력·경험 기록 (Codex 플레이어 기준) | V0 코어, Host(HTTP/SSE·복구·스케줄러), Chat Web/PWA, Research Inspector (`status.yaml` 기준 1~4단계) |
| 없는 것 | 플레이어 모델 호스팅 | 도구 호출, 이미지 입력, 환경이 시작하는 실행, 기억, 문맥 길이 관리 |
| 설계 단계 | 실사용 중 | Agent Plane(v5)은 아이디어 문서. 정식 로드맵에서는 1~5단계 이후 연구 |

`context 관련.md`가 적은 대로, Persona는 지금 같은 세션의 이전 턴을 매 요청마다 전부 다시 넣는다. 길이 제한·요약·장기 기억이 없다. 100시간 플레이에는 이 방식을 그대로 쓸 수 없다.

## 2. 개념 대응표

두 프로젝트의 용어가 거의 1:1로 맞는다. 결합 계약은 이 표에서 시작하면 된다.

| Lobotomy (현재) | v5 구조 맵 | 비고 |
|---|---|---|
| 게임 + RobotomyObserver + MCP 서버 | External Environment + Port·Adapter | Lobotomy는 판단하지 않는다. 지금 원칙 그대로 |
| 관찰(observe, delta, 사건) | Agent Event / 외부 Observation | 어떤 관찰이 Agent Event가 되는지는 4절 |
| 의도 묶음·입력 실행 | Cognition Result의 행동 Proposal → Authorization·Execution | 공개 범위 검사가 Authorization 역할을 한다 |
| 입력 영수증(queued, input_sent) | Execution 결과 | "전송은 성공의 증명이 아님" 원칙이 v5의 실행 사실과 해석 분리에 맞는다 |
| 원본 사건 보존, 정정은 새 기록 | System History, KEEP/REVISE 이력 | 같은 원칙 |
| 엔지니어링 점검은 플레이어 기억이 안 됨 | System History → Memory 자동 연결 금지 | 같은 원칙 |
| 비공개 추론 원문 수집 금지 | Hidden CoT를 Experience에서 제외 | 같은 원칙 |
| 사람 개입 기록 | 사용자 승인·거부·피드백 = External Event | Chat Web/PWA가 운영자 개입 창구가 될 수 있다 |
| 일차 회고 | Session·Activity의 기계적 전이로 Memory Formation 깨우기 | 일차 종료가 형성 시점으로 적합하다 |
| 플레이북 | Activity Context State (에이전트가 해석한 활동 상태) | Memory가 아니라 활동 해석 상태로 보는 편이 v5에 맞다 |
| 직원 평가·환상체 인상 | Relation Context 후보 (게임 속 인물에 대한 관계) | 게임 속 인물을 Relation의 대상으로 둘지는 열린 질문 |
| Run / 일차 / 시도 | Environment Time (`경험과 성장` 10절) | Real / Persona / Environment 시간축을 따로 기록 |
| 시설 관리자 역할 | Activity Context 안의 역할 | Self Context에 섞지 않는다. Lobotomy의 "플레이어는 게임을 하고 있음을 안다" 원칙과 같다 |

이 표에서 보이는 위험: Lobotomy의 경험 vault(`vault/Lobotomy-Experience`)와 Persona의 Memory Context가 둘 다 "기억"을 가지려 한다. **기억의 주인은 하나여야 한다.** 결합 후 Lobotomy 쪽 기록은 외부 활동의 원본 사실(System History 쪽)이고, 플레이어의 기억은 Persona가 형성한다. 이 경계를 먼저 정하지 않으면 같은 경험이 두 번 기억되거나 서로 다르게 요약된다.

## 3. Persona Foundation에 빠진 것

| 빠진 것 | 왜 필요한가 | Persona 쪽 근거 |
|---|---|---|
| A. 도구 호출 | 게임 관찰·입력이 전부 도구다 | 지금 `TOOL_CALL`은 종료 사유 값뿐이다. 「도메인 확장」이 ToolCall·ToolExecution·ApprovalDecision 도메인을 이미 예상했다 |
| B. 이미지 입력 | 스토리·외형을 플레이어가 직접 봐야 한다 | 「도메인 확장」의 Multimodal Domain 후보 |
| C. 환경이 시작하는 실행 | 게임 사건은 사용자 턴이 아니다 | 지금의 Turn은 사용자 입력 → 응답 구조. v5는 External Event → Agent Event로 예상만 했다 |
| D. 문맥 조립 | 전체 턴 재생을 할 수 없다 | v5의 Cognition Bootstrap Input + Recall 구조. 아직 구현 계약 없음 |
| E. 게임 우선 스케줄링 | 게임과 GPU를 나눠 쓴다. 다른 대화가 게임 판단을 밀어내면 안 된다 | 2-E InferenceScheduler의 우선순위 확장 |

**정식 계약과 맞춰 볼 두 가지:**

- **세션당 활성 실행 1개, 초과 입력 자동 대기 없음** (정본 아키텍처 8.4.2, Overview 6절). *2026-10-21 정정:* 처음에는 충돌이라고 적었으나 과장이었다.
  이 규칙은 실행 중 같은 세션에 새 입력이 들어오면 `SessionBusy`로 거절하고, `ConversationRuntime` 안에 암묵적 대기열을 만들지 않는다는 뜻이다.
  게임 사건을 하나씩 세션 입력으로 넣으면 거절되거나 대기열이 필요해져 충돌한다. 하지만 **합치는 일을 Runtime 밖의 Lobotomy 어댑터가 하면 충돌하지 않는다.**
  어댑터는 판단 중에 생긴 사건을 시간순으로 모아 두었다가, 실행이 끝난 뒤 하나의 Agent Event로 제출한다. Lobotomy의 사건 기록과 `wait_for_event(after=…)`가 이미 이 형태다.
  남는 조건은 둘이다. (a) 합치기는 시간순 기계적 처리여야 하고 중요도로 거르면 안 된다(Host는 의미를 해석하지 않는다). (b) 판단 중 급한 사건으로 현재 판단을 자동 취소하는 것은 V0의 "인터럽트는 명시적 명령" 원칙과 실제로 충돌한다. 판단 중에는 게임이 정지해 있으므로 자동 취소는 처음부터 두지 않는 것을 기본으로 한다.
- **로드맵의 범위.** 5단계 "외부 프로그램 제어 경계"는 외부 프로그램이 Host를 조작하는 방향이다. 게임 플레이는 반대 방향, 즉 Agent가 외부 환경을 조작하는 것이다. 이것은 로드맵 7절의 "1~5단계 이후: 도구 호출·자율 행동"에 해당한다. 순서를 앞당길지 정해야 한다.

## 4. 실시간 게임과 v5 Cognition의 비용 문제

v5는 Agent Event마다 Cognition Execution 하나를 열고, 고정 Bootstrap Recall + 추론과 인지 행동의 반복 + 필요할 때 Context Access를 한다. 이 PC에서 게임과 함께 돌리면 한 판단에 모델 호출이 여러 번 생긴다.
게임 관찰을 전부 Agent Event로 만들면 감당할 수 없다. 해결 방향은 다음과 같다.

1. **Agent Event는 "정지한 판단 시점"에만 만든다.** 판단 중에는 게임이 정지해 있으므로 Cognition 반복 횟수가 게임 진행을 해치지 않는다. 앞 문서의 정지 중심 진행과 같다.
2. **깨어날 조건은 에이전트가 고르고, Foundation은 기계적으로 적용한다.** Lobotomy의 `wait_for_event`와 `arm_pause`가 이미 이 형태다. "무엇이 중요한 사건인가"를 Foundation이 판단하면 v5의 "Host는 의미를 해석하지 않는다" 원칙과 충돌한다. 에이전트가 직전 Cognition Result에서 "이런 일이 생기면 깨워라"를 정하면 충돌이 없다.
3. **무거운 일은 게임 밖으로 미룬다.** Memory Formation, Self·Person 해석, 철학적 관점 앙상블은 일차 종료 뒤 게임을 닫은 상태에서 돌린다. 「트리거」의 "미해결 상태로 남겼다가 다음 관련 실행에서 회수"하는 방식이 이 시간 분리와 잘 맞는다. 플레이 중에는 관찰만 미해결로 남긴다.
4. **Bootstrap Recall은 가볍게 한다.** 매 판단의 필수 Recall은 같은 일차의 최근 경험 Buffer와 현재 활동 상태 정도로 제한한다. Episodic 검색은 추가 Recall로 요청할 때만 한다. 정확한 비용은 측정 전에는 모른다.

## 5. 정체성: 모델인가 Persona인가

History 문서는 인격을 모델 하나에 귀속하지 않는다. "LLM은 Self Model 그 자체가 아니라 Self Model을 갱신하는 추론기"라고 한다. 이 정의를 따르면 다음이 바뀐다.

- **플레이어 = Persona 하나.** 모델 ID는 그 Persona의 Structural Fact로 기록된다. 모델을 바꾸면 Persona가 "내 추론기가 바뀌었다"는 사실을 알게 되는 사건이 된다. Lobotomy의 "모델 간 경험 이전"은 같은 Persona가 추론기를 바꾸고 계속하는 경우와, Persona를 복제해 다른 경험을 주는 경우(「인격과 의식」 8절의 개체 분화)로 나뉜다.
- **"판단 모델 하나" 조건.** v5에는 Cognition 외에 Formation과 철학적 관점처럼 모델을 쓰는 곳이 더 있다. 이것들도 Persona의 일부로 볼지, 아니면 Cognition의 Decision만 한 모델로 고정할지 정해야 한다. 현실적으로 게임 중에는 한 모델만 GPU에 올릴 수 있으므로, 플레이 중에는 한 모델이고 게임 밖 작업에서는 다른 모델을 쓸 여지가 있다.
- **해석이 쉬우려면** 한 실험 구간 동안은 모델을 고정하는 편이 낫다. 어떤 변화가 경험 때문인지 모델 교체 때문인지 가리기 어려워지기 때문이다.

## 6. 결합 방식 선택지

| 안 | 구조 | 판단 |
|---|---|---|
| ① Persona가 Lobotomy MCP를 부른다 | Persona에 MCP 클라이언트 어댑터와 ToolCall 도메인을 추가. Lobotomy는 지금의 `run_player_mcp.py` stdio 서버를 그대로 제공 | **추천.** 각자 원칙이 그대로 유지되고, Lobotomy는 다른 플레이어(Codex 등)에게도 같은 게임기로 남는다 |
| ② Lobotomy 안에 실행기, Persona는 모델 호출만 | Lobotomy가 Persona Host를 모델처럼 부름 | 비추천. Persona가 부품이 되고 기억·자기모델이 게임 쪽에 생긴다 |
| ③ 저장소 통합 | 하나로 합침 | 비추천. 거버넌스·문서 권위 체계가 다르고 게임 자산 경계가 섞인다 |

①에서 Lobotomy 쪽 변경은 작다. 플레이용 도구 묶음을 8~10개로 줄인 프로필, 공개 채팅 수집을 Codex rollout 대신 Persona의 사건 기록에서 받는 경로, 압축 전 정지 훅을 대체하는 Persona 쪽 정지 규칙 정도다.

## 7. 단계 제안

어느 단계도 상대 저장소의 완성을 기다리지 않게 나눈다. 구현은 Codex 몫이고, Persona 쪽 변경은 그 저장소의 제안·수용 절차를 따른다.

| 단계 | 내용 | 결과 |
|---|---|---|
| 0 | **결합 계약 문서**: 2절 표를 기반으로 Agent Event, 행동 Proposal, Execution 결과, Experience 기록, 사람 개입의 형식과 기억 소유권을 정한다. 두 저장소에 같은 문서를 둔다 | 코드 없음 |
| 1 | Persona에 A(도구 호출)·C(환경 실행)·D(최소 문맥 조립)를 넣고, Lobotomy 전용 세션 하나로 플레이한다. 기억은 임시로 Lobotomy vault를 도구로 읽는다(임시라고 기록) | 로컬 플레이 시작. 비용 문제 해결 |
| 2 | B(이미지), E(스케줄링 우선순위) | 스토리 관람, 다른 대화와 공존 |
| 3 | v5 Memory Context 최소형: 일차 단위 Experience Buffer와 일차 종료 Formation. Lobotomy vault의 플레이북을 Activity Context로 옮김 | 기억 소유권 이전 |
| 4 | Self·Relation·Activity Context 연결. 일차 종료 후 자기 해석 | Become a person 연구와 연결 |

1단계가 앞 문서의 0~4단계(자원 측정, 기록 재생 시험)를 대체하지는 않는다. 모델 선택과 자원 측정은 그대로 필요하다.

## 8. 연구 측면에서 이 결합이 주는 것

- Lobotomy는 「경험과 성장」이 말한 Game Room의 첫 실제 환경이 된다. 명확한 목표(Mission)와 자유로운 관람·감상(Activity)이 한 게임 안에 섞여 있다.
- 선택의 기원을 기록할 수 있다. 지금은 사용자가 정해 준 활동이다(「경험과 성장」 3절의 "일과 통보" 단계).
- 실패와 재시도가 일차·시도 단위로 기록되어 있어, 경험이 이후 판단을 바꾸는지(역사 의존성) 관찰하기 좋다.
- 같은 초기 Persona를 복제해 다른 Run을 주면 개체 분화 실험이 된다. 지금 당장 할 일은 아니다.

주의: 게임의 스토리와 주제를 Person·Self 해석의 근거로 쓰는 것은 흥미롭지만, 시설 관리자라는 게임 속 역할과 Persona 자신을 섞지 않는 경계를 계약에 명시해야 한다.

## 9. 사용자 결정 (2026-10-21)

1. 결합 방향: Persona가 Lobotomy MCP를 호출한다.
2. 정체성: 플레이어는 Persona다.
3. Persona 로드맵은 구현용 임시 순서다. History의 설계가 더 넓으며, 순서는 크게 중요하지 않다. 7절 단계를 로드맵 단계 번호에 맞출 필요가 없다.
4. 판단 중 사건 합치기: 위 3절 정정 참고. 어댑터에서 합치면 충돌하지 않는다.
5. 기억 소유권: 플레이어 기억의 주인은 Persona Memory Context, Lobotomy 기록은 원본이다.

6. 판단 주체 원칙: 과거의 "판단 모델 하나"는 Codex 기준이었다. 결합 후에는 **"판단 Persona 하나"** 원칙을 쓴다. Persona 시스템 내부의 별도 모듈(Formation, 관점 모델 등)은 따로 세지 않는다.
7. Persona 저장소의 현재 기능 범위: 에이전트 모듈(v5 Agent Plane 등)은 계획만 있고 미구현이다. 지금 가능한 것은 Persona와 자연어로 1:1 대화하는 채팅 기능뿐이다.

7번에 따른 해석: 3절의 A~E에 더해 Cognition Execution 자체(추론 → 인지 행동 → 결과 → 결정의 반복)가 처음 만들어져야 한다. Lobotomy 플레이가 Agent Plane을 실제로 처음 요구하는 활동이 된다.
채팅은 같은 Persona에게 오는 또 다른 Agent Event다. 플레이 중 사용자와의 대화·개입을 같은 Persona가 어떻게 받을지(게임 판단과 같은 실행 흐름인지, 별도 세션인지)는 다음에 정할 질문이다.

## 9-1. 결정 전 원래 질문 목록

1. 결합 방향: ① Persona가 Lobotomy MCP를 부르는 구조로 갈지. (추천)
2. 정체성 기준: 플레이어를 모델이 아니라 Persona로 볼지. 그렇다면 "판단 모델 하나"를 Cognition의 Decision에만 적용할지, Formation·관점 모델까지 포함할지.
3. Persona 로드맵: 도구 호출·자율 행동(로드맵 7절)을 5단계보다 앞당길지.
4. 실행 정책: Lobotomy 세션에 한해 "판단 중 생긴 사건을 다음 Agent Event로 합치는" 규칙을 추가할지.
5. 기억 소유권: 결합 후 플레이어 기억의 주인을 Persona Memory Context로 하고, Lobotomy vault는 원본 기록으로 둘지.
