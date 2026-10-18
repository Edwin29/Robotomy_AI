# NVIDIA 녹화 → YouTube 비공개 자동 업로드

게임, 세이브, NVIDIA 녹화, 플레이어 MCP를 조작하지 않는 독립 업로더다. 플레이어가 업로드 도구를 반복 호출할 필요가 없다. Windows 작업 스케줄러가 실행하며 Codex 종료와 분리된다. 해당 Windows 사용자 로그인 때 다시 실행한다.

## 이번 설정

- 대상: `D:\NVIDIA\Lobotomycorp` 바로 아래의 MP4. 하위 폴더와 링크는 탐색하지 않는다.
- 기존 완료 영상 4개는 제외했다. 사용자 요청 당시 녹화 `Lobotomycorp 2026.10.18 - 18.36.55.07.mp4`와 앞으로 생기는 파일만 포함한다.
- 공개 범위는 코드에서 `private`로 고정한다. 알림 전송도 끈다. 제목은 파일명이며 본문은 `Robotomy AI gameplay recording.`이다.
- 계정 연결 전에는 파일 상태 확인만 한다. Google API에 영상이나 메타데이터를 전송하지 않는다.
- 원본 영상은 이동·삭제·변환하지 않는다. 업로드가 끝나도 PC에 남는다.

## 처음 한 번 할 계정 연결

1. [Google Cloud Console](https://console.cloud.google.com/)에서 개인 프로젝트를 만든다. 이 구현에는 유료 모델, 별도 서버, OBS가 필요하지 않다. 결제 계정이나 유료 서비스 연결은 이 설정에 포함하지 않는다.
2. [YouTube Data API v3](https://console.cloud.google.com/apis/library/youtube.googleapis.com)를 선택하여 사용 설정한다.
3. Google Auth Platform에서 앱 이름(예: Robotomy Upload), 지원 이메일/연락 이메일을 설정한다. 개인 Google 계정이면 대상은 External이며, Testing 상태에서는 자신의 계정을 테스트 사용자에 추가한다.
4. Clients에서 **Desktop app** 유형 OAuth 클라이언트를 만든다. API 키 또는 서비스 계정으로 대체하지 않는다.
5. 내려받은 JSON을 아래 위치에 `oauth-client.json`이라는 이름으로 저장한다. 채팅에 내용을 붙여넣거나 Git에 추가하지 않는다.

   `D:\Projects\Robotomy_AI\.robotomy\youtube\oauth-client.json`

6. 프로젝트의 `YouTube-Upload.cmd`를 실행하고 **1**을 선택한다. 시스템 브라우저에서 업로드할 채널의 Google 계정을 선택하고 권한에 동의한다. 계정/브랜드 채널이 여러 개면 목적 채널인지 확인한다. 이 프로그램은 업로드 scope만 요청하며 별도 채널 목록 조회 권한을 요청하지 않는다.
7. 연결이 완료되면 업로더가 자동으로 재개된다. 이후에는 녹화가 완료될 때마다 자동 처리된다. 첫 업로드 후 [YouTube Studio](https://studio.youtube.com/)에서 대상 채널·비공개 여부·처리 완료를 직접 확인한다.

OAuth Testing 상태의 refresh token은 이 scope에서 일반적으로 7일 후 만료되므로 재로그인이 필요하다. 장기 자동화를 위해서는 Google의 앱 게시 상태와 검증 요건을 확인한다. 앱을 Production으로 바꾸는 것과 영상 공개는 다른 설정이며 영상은 계속 private로 요청한다. API 할당량과 채널의 업로드 제한이 적용된다. 15분 이상 영상은 채널 기능 자격 확인이 필요할 수 있다.

## 저부하 동작

30초 간격으로 파일 메타데이터를 확인한다. 크기/수정 시각이 120초 동안 변하지 않은 파일에 대해 Windows 읽기 핸들을 열어 **기존 쓰기 핸들이 없는지** 확인한다. 녹화 중이면 핸들 열기가 실패하여 그대로 건너뛴다. MP4의 `ftyp`·`mdat`·`moov` 최상위 박스 및 파일 경계를 확인한다. 이는 녹화 상태 API나 전체 영상 재생 검증은 아니다. 미완성/손상 파일은 자동 전송하지 않고 대기한다.

업로드는 한 번에 하나, 4MiB 조각으로 전송한다. 기본 전송 평균은 최대 약 2MiB/s이며 순간 네트워크 속도를 일정하게 고정하는 방식은 아니다. 인코딩, 전체 파일 해시, 영상 디코딩을 하지 않는다. 설정은 `.robotomy/youtube/config.json`에 저장한다. RAM은 실제 대기 프로세스 측정 결과를 참고하며 전송 중 최대 메모리 측정은 계정 연결 후 필요하다.

## 중단·재시도·중복 방지

`YouTube-Upload.cmd`에서 2=상태, 3=일시 중단, 4=재개다. 중단은 현재 HTTP 요청(최대 30초의 소켓 timeout)을 마무리한 뒤 적용한다. 프로그램 전체의 엄격한 30초 종료 보장은 아니다. 녹화와 게임은 계속된다. STOP 파일은 Windows 재로그인 뒤에도 중단 상태를 유지한다.

전송 중 네트워크가 끊기거나 프로세스가 재시작되면 저장한 세션의 서버 수신 위치를 조회한 뒤 이어 보낸다. 서버 오류/할당량은 간격을 늘려 재시도한다. 로그인 만료는 `awaiting_auth`로 대기한다. `review` 상태는 새 업로드를 자동 생성하지 않는다. 생성 응답 유실, 세션 만료, 업로드 중 파일 변경은 Studio에서 확인 후 운영자가 처리해야 한다. 파일 경로별 장부이므로 이름을 바꾸거나 복사한 같은 영상의 내용 중복까지 탐지하지는 않는다.

`uploaded`는 YouTube가 업로드를 수락하고 영상 ID·private 응답을 반환했다는 뜻이다. 인코딩 완료, 콘텐츠 검사 통과, 재생 가능 여부까지 보장하지 않는다. 영상 ID로 `https://www.youtube.com/watch?v=<video_id>`에서 확인한다.

## 저장 위치와 진단

- 실행 코드: `robotomy/youtube_upload.py`, `scripts/youtube_upload.py`
- 작업 등록: `scripts/start_youtube_task.ps1` (`RobotomyAI-YouTube-<프로젝트 해시>`)
- 장부: `.robotomy/youtube/uploads.sqlite3`
- 상태/마지막 활동: `.robotomy/youtube/status.json`, `worker-exit.json`
- 로그인 자격: `.robotomy/youtube/credentials.dpapi` (현재 Windows 사용자 DPAPI 암호화)
- 업로드 세션 URL도 장부 안에서 DPAPI 암호화한다. 모든 비공개 파일은 기존 `.robotomy/` Git 제외 규칙을 따른다.

운영 명령(프로젝트 폴더에서 실행):

```powershell
.venv\Scripts\python.exe -X utf8 scripts\youtube_upload.py status
.venv\Scripts\python.exe -X utf8 scripts\youtube_upload.py stop
.venv\Scripts\python.exe -X utf8 scripts\youtube_upload.py start
```

## 검증 경계

실제 녹화 파일을 수정하지 않고 이전 영상 제외/현재 영상 포함을 확인했다. 임시 MP4와 모의 HTTP로 쓰기 잠금, 완료 판정, 제한된 조각 읽기, 비공개 요청, 끊김 복구, 성공 응답 유실, 세션 만료, 중복 방지, DPAPI를 검증한다. 실제 Google 로그인·업로드·채널 처리 검증은 사용자 계정 연결 전에는 수행할 수 없다.

2026-10-18 로컬 검증: 전체 164개 테스트 통과(업로더 전용 13개 포함). 대기 프로세스 working set 약 22.40MiB, private memory 약 13.12MiB였다. 실제 전송 중 최대치는 미측정이다. 중복 시작 요청은 기존 PID를 유지했고, 게임 PID 35676은 그대로였다. 녹화 중 파일이 증가하는 것을 확인했으며 전송하지 않았다. 결과는 `.robotomy/youtube/verification.json`과 `unit-tests.txt`에 있다.

공식 근거: [resumable 업로드](https://developers.google.com/youtube/data/guides/using_resumable_upload_protocol), [데스크톱 OAuth](https://developers.google.com/youtube/data/guides/auth/installed-apps), [videos.insert](https://developers.google.com/youtube/data/reference/rest/v3/videos/insert), [토큰 수명](https://developers.google.com/identity/protocols/oauth2/).
