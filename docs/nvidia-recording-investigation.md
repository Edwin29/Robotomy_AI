# NVIDIA 녹화 제어 읽기 전용 조사 — 2026-10-18

현재 플레이/녹화에 키 입력, IPC 요청, 프로세스 attach/restart, 설정 변경을 하지 않았다.
설치 파일·설정·파일 메타데이터만 읽었다. 큰 분석 엔진과 신규 상주 프로그램은 실행하지 않았다.

## 확인한 근거

- 설치 오버레이: `C:/Program Files/NVIDIA Corporation/NVIDIA App/CEF/NVIDIA Overlay.exe`, 파일 버전 128.4.13.14 (NVIDIA App 제품 버전과 구분).
- 배포 JS: `osc/main.b4319201cf95e5c5.js`.
- 명령 정의: CrimsonNative / ShareServer / GetRecordRunningStatus, GetRecordEnableStatus, GetCaptureState.
- 상태 구독: RegisterCaptureStateChangeNotifications. 수동 녹화와 DVR 모드를 구분하며 started/available 등을 처리한다.
- 시작 코드: `_startManualRecord` → EnableRecord `{enable:true}`.
- 저장·종료 코드: `_stopAndSaveManualRecord` → EnableRecord `{enable:false}`.
- 전달 경로: QUERY_IPC_EXTENSION_MESSAGE → bridgeService → window.cefQuery.
  내부 호출의 존재는 외부 프로세스에서 사용할 수 있다는 증거가 아니다.
- ShareSettings.json의 RecordToggle=[18,120], 즉 Alt+F9.
- 레지스트리 NVSPCAPS의 DefaultPathW=`D:/NVIDIA`, RecEnabled=1.
  RecEnabled는 현재 수동 녹화 중이라는 확정 신호로 사용하지 않는다.
- `D:/NVIDIA/Lobotomycorp`에 기존 완료 MP4와 새 16:22:57 MP4가 존재했다.
  최신 파일은 조사 당시 0바이트였다. 파일 증가/존재만으로 녹화 상태를 판정하면 안 된다.
- 일부 로컬 오버레이 로그는 0바이트 또는 이전 날짜였다. 현재 상태의 권위 있는 근거가 아니다.
- 조회 가능한 선택 프로세스의 TCP listen 조회에서는 엔드포인트를 확인하지 못했다.
  접근 제한 및 별도 프로세스/명명 파이프 가능성까지 배제한 것은 아니다.

## 결론과 다음 검증

정확한 내부 상태 조회와 분리된 시작/종료 명령은 존재한다. 현재 외부 API 호출 가능성과
현재 녹화 상태의 직접 조회는 미검증이다. 문서화된 외부 사용 방법으로 확인한 것은
Alt+F9 토글이며, 토글만으로 신뢰할 수 있는 자동화를 구성하지 않는다.

다음 단계는 녹화 중이 아닐 때 CEF/native 브리지에서 ShareServer까지의 IPC 운반 경로를
더 좁혀 조사하고, 읽기 전용 상태 조회를 먼저 검증하는 것이다. 알려지지 않은 IPC 요청을
현재 녹화에 보내거나 디버깅을 위해 프로세스를 재시작하지 않는다.

RAM 최소화 설계: 별도 OBS/Chromium 없이 기존 게임기 프로세스에서 작은 메시지만 조회;
시작/종료 시 필수 조회, 상태 표시는 수초 간격 또는 알림 방식. 메타데이터/로그는 증분 읽기,
영상 내용은 읽지 않는다. 외부 IPC가 확인되지 않으면 이 설계를 구현 가능하다고 단정하지 않는다.
예상 RAM 숫자는 아직 측정하지 않았다. 업로드는 향후 별도 구현이며 이번 조사 범위가 아니다.

공식 단축키 안내: https://www.nvidia.com/en-us/geforce/news/nvidia-app-download-and-features/
