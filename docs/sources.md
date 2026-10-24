# 설계 참고 자료

확인일: 2026-10-17. 외부 자료는 개발 환경의 참고이며, 깨끗한 플레이어 세션에 제공할 공략이 아니다.

- [Codex MCP 공식 문서](https://learn.chatgpt.com/docs/extend/mcp?surface=cli):
  로컬 STDIO, 프로젝트 `.codex/config.toml`, 신뢰된 프로젝트의 설정 로딩.
- [MCP 공식 Python SDK](https://github.com/modelcontextprotocol/python-sdk):
  이 버전은 설치 및 왕복 검증한 1.30.0을 고정한다. 임의 최신 버전으로 자동 업그레이드하지 않는다.
- [Voyager](https://arxiv.org/abs/2305.16291): 경험에서 얻은 실행 기술을 외부 라이브러리로 재사용하는 선례.
- [Reflexion](https://arxiv.org/abs/2303.11366): 모델 가중치 갱신 없이 언어적 피드백을 기억하는 선례.
- [Reasoning Models Don't Always Say What They Think](https://arxiv.org/abs/2505.05410):
  자연어 설명과 실제 결정 원인의 충실성이 자동으로 같아지지 않는다는 근거.

이 자료들은 Lobotomy의 실제 게임 클리어·모델 간 동일 경험·인간 트윈 구현을 입증하지 않는다.
