# 작업 선택창 표시 누락 수정 — 2026-10-19

## 상태

소스 수정 및 별도 출력 경로 컴파일 완료. 실행 중인 게임 모듈은 교체하지 않았다.
현재 플레이/녹화 보존 요청에 따라 실제 화면 재현 검증과 Unity 배포는 다음 유지보수에 남긴다.
MCP의 새 행 필드는 이전 생산자와도 호환되며, 새 생산자가 제공하기 전에는 null이다.

## 근거와 수정

기존 캡처 event 6338의 화면에는 세 직원 이름/HP/SP/측정불가가 보이지만
동일 snapshot의 command 텍스트와 버튼은 비어 있었다. 현재 진단에는 직원 정보가
PauseFilter와 겹쳐 front_graphic으로 거절되는 사례가 있다.
원래 구현은 전면 Graphic의 RectTransform 전체를 불투명한 가림으로 취급했다.

게임의 PlaySpeedSettingUI.pauseFilter는 pauseDefSprite 또는 observeSprite를 표시한다.
이 정확한 UI 참조와 두 sprite에 한해서 실제 texture alpha를 확인한다. 이름 문자열에
따라 예외를 허용하지 않으며 다른 패널, 진행도 잠금, 특수 material/effect는 우회하지 않는다.

일반 Simple Image의 UV를 화면 교차 영역에 대응시키고 보간 경계를 한 texel 넓힌다.
해당 영역에 alpha > 63/255인 texel이 하나라도 있으면 계속 차단한다.
이 값은 옅은 일시정지 장식용 허용 기준이지, 모든 반투명 UI의 가독성 판정이 아니다.
읽기 실패, 회전, preserveAspect, 미지원 Image 유형은 기존 차단을 유지한다.
텍스처별 최초 1회 GPU 복사/alpha 누적합 생성 후 사각형 쿼리는 O(1).
최대 2개 텍스처를 캐시한다. 첫 사용의 복사 지연/메모리는 실제 실행에서 측정 필요.

ManagementSlot.workData.WorkSuccess/WorkSpeed의 최종 Text만 각각 success_rate/work_time으로
연결한다. 측정불가, 등급 문구, 숫자는 표시 원문대로 전달하며 내부 계산값으로 대체하지 않는다.
클릭 좌표는 기존 최신 표시 행과 실제 UI raycast 검증을 그대로 사용한다.
이전 프레임 직원 행은 새 관찰에 합치지 않는다.

## 검증 범위

- 실제 생산 CoverAlphaMap을 C#으로 실행: 옅은 영역 허용, 불투명 아이콘/부분 가림/짙은 영역 거절.
- Python 전송: 이름/HP/SP/성공률/작업시간/좌표 보존, 빈 새 관찰에 과거 직원 미잔류.
- Unity 게임 참조 DLL을 사용하여 별도 .robotomy/verification/command-rows-patch로 컴파일.
- 이전 HP/SP 정책을 기대하던 오래된 disclosure fixture를 현재 렌더링 Text 정책과 일치시킴.

## 다음 안전한 적용 시점

게임 종료를 확인한 뒤 기존 scripts/prepare_live.py --finish-build 절차로 배포한다.
작업 선택창에서 일시정지 유무, 장식의 중앙 아이콘과 직원 행 겹침, 화면 가장자리,
다른 패널 가림, 잠금/측정불가, 스크롤 및 클릭 좌표를 실제 화면과 대조한다.
실제 검증 전에는 이 패치가 모든 가림/보스 연출을 처리한다고 주장하지 않는다.
