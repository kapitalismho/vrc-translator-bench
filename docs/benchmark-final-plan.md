# 글로벌 대화 번역 벤치마크 최종 계획

- 상태: **로컬 reset, R1 episode-native 구현·대표 앱 소규모 실측, R2 오프라인 소스 준비·근사 ASCEND 재구성을 마쳤다.** R2는 본평가 소스 51개·개발 12개·C1 2개와 영중 T1 본 9개·개발 4개 부모를 제공한다. 현재 구현·근거 범위는 [구현 기록](benchmark-implementation-plan.md)을 따른다. 일한 T1 생성·검수, 새 judge 통합·R6 최종 진입 판정·본 평가는 완료되지 않았다.
- 우선순위: 이 문서가 평가 계약의 기준이다. [구현 계획·보존/폐기 분류·이슈별 계약](benchmark-implementation-plan.md)은 실제 코드에서 출발하는 구현 순서와 GPT/Claude 분담을 정한다. [기존 개편 논의](benchmark-redesign.md)는 선택 이력으로만 보존한다.
- 최신 사용자 결정: **낭독 10%, 짧은 말 10%, T1 주고받기 30%, IngCrowd 채택, 일한 T1의 영중 T1 기반 Gemini 3.8 Flash TTS 재구성, 최소 커스텀 GEMBA-ESA, 화면 캡처 없는 ‘앱의 번역 출력’ 평가, VRCLT와 Kikitan은 전부 self로 측정하고 T1의 양방향은 별도 self 실행**.
- 계획 승인과 실행 승인은 구분한다. 오너는 새 이슈 게시와 기존 이슈 삭제를 별도로 승인했다. 이 승인은 유료 TTS 호출, 계정·앱 설정 변경, 본 실험이나 원격 코드 push까지 허용하지 않는다.
- 검증 운영 개정: **R1–R5는 자기 산출물의 최소 확인, R6는 최종 프로필 진입 판정과 통합 검증, R7은 본 실행·결과 확인**을 맡는다. 이슈가 바뀌었다는 이유만으로 파일럿·judge·전체 검증을 반복하지 않는다(§6.5, §14).
- 2026-10-26 R1 실행 중 오너 승인 개정: **KIKI1·KIKI2도 §4.7 self 예외에 포함한다. VRChat은 실행하지 않는다.** 실제 desktop/peer 입력과 동시 T1 의무는 self·역할별 두 pass로 대체하며, peer 지원 검증 완료로 처리하지 않는다. 다른 앱의 peer/동시 T1, 모델·자료·가중치·wave는 유지한다.
- 후속 오너 승인: **Kikitan 주 수집을 설치 앱의 `--no-ui` WebSocket `recognition`으로 전환한다.** 성공한 KIKI2 소규모 실험 뒤의 시행·재개 지시에 따른다. Kikitan GUI-only 및 UDP 7272 user-data 고정 의무만 대체하며, self/split 조건·14개 프로필·모델·wave·가중치·+15초 관찰은 유지한다. 이후 오너가 R1 게시·`main` 병합·#15 종료를 별도로 승인했으며, [공개 개정 및 완료 범위](https://github.com/kapitalismho/vrc-translator-bench/issues/15#issuecomment-6431325473)에 변경 근거와 미검증 범위를 기록했다. 이 승인은 추가 유료 실행이나 R6 최종 진입 승인이 아니다.
- R2 후속 오너 승인 **`ascend-reconstruction-v1`**: 오너는 원본의 엄밀한 복원이 아니어도 된다고 밝힌 뒤, **P2/T1은 화자 간 시간차 추정 우선·불명확하면 명시적 간격 재구성, P3는 같은 화자의 연속 설명**이라는 제안에 “네 제안대로 가자”로 실행을 승인했다. 아래 §3.1·§4.2의 개정이 이전 원본 공통 시계·누락 구간 원음 필수 조건을 대체한다. 대체된 의무는 검증 완료가 아니라 **superseded**다. 원본 음성·내용·화자·혼용 문맥·표본 분리·수량·가중치는 유지한다. 영중 TTS, 대체 데이터셋, 유료 호출, 원격 게시 승인은 포함하지 않는다.

## 1. 평가 질문과 확정 범위

평가 질문은 **“실제 대화의 의미를 앱이 얼마나 정확하게 번역해 내보내며, 필요한 의미가 출력되기까지 얼마나 기다려야 하는가?”**다. 원문 문장과 출력 패킷의 1:1 대응이나 옛 도달률을 대표 지표로 사용하지 않는다.

1. 전세계 커뮤니티를 위한 비교다. 두 언어쌍 **영중·일한**을 같은 비중으로 평가하며, 일반 peer 케이스의 주 방향은 **영→중·일→한**이다.
2. 기본 프로토콜은 일반 케이스 peer, T1은 동일 앱 인스턴스의 self/peer 동시 활성이다. **사용자 승인 예외인 VRCLT1–VRCLT2와 KIKI1–KIKI2는 일반 케이스도 self, T1도 양방향 self 분리 실행**으로 측정한다(§4.7). T1 자료·30% 비중은 유지하지만 두 실행 조건을 같은 동시 양방향 시험이라고 부르지 않는다.
3. 영중 회화의 사람 원음은 **ASCEND**, 일한 자연 회화는 사용자 승인 자료인 **IngCrowd Japanese Themed Casual Conversation Corpus**를 사용한다. ASCEND P2/P3/T1은 공개된 실제 발화를 사용한 **근사 시간축 재구성 조건**으로 표시한다.
4. **일한 T1만** 선정한 영중 T1의 의미·화자 역할을 일본어·한국어 대본으로 옮겨 TTS로 만든다. IngCrowd 일반 회화를 TTS로 대체하지 않는다.
5. 품질은 **GEMBA-ESA의 오류 구간 판정 → 0–100 직접 채점**으로 평가한다. 지연 p50·p90과 비용은 별도 축이다.
6. 사용자가 선택한 새 관측 종점은 **앱의 번역 출력**이다. 앱의 기존 OSC·로그·공개 이벤트를 읽으며 앱 코드·바이너리를 개조하지 않는다. **자막의 실제 화면 표시·렌더링·읽기/이해·응답 시간은 측정하지 않는다.** 이 결정은 이전의 사용자 자막 surface 종점을 명시적으로 대체한다.
7. 기존 14개 프로필 인벤토리·실험 이력은 유지한다. 새 채널·언어·네이티브 출력 지원과 수집 가능성을 구분하며, 미검증을 미지원으로 단정하거나 프로필을 조용히 제거하지 않는다.

T1에는 중→영·한→일도 포함된다. 따라서 통합 결과는 **‘영중·일한 통합, peer 중심 + T1 양방향; VRCLT·Kikitan self 대체 조건 별도 표시’**로 표기한다. 두 언어쌍이 전세계 모든 언어·억양을 대표한다는 주장도 하지 않는다.

## 2. 케이스와 가중치

두 언어쌍의 비중은 각각 **50%**다. 각 언어쌍 안에서 아래 비중을 적용한다. 같은 구성의 두 언어쌍을 합쳐도 전체 유형 비중은 동일하다.

아래 채널 열은 기본 프로토콜이다. VRCLT·Kikitan의 self-only 예외는 §4.7을 적용하며 유형·자료·비중은 바꾸지 않는다.

| ID | 유형 | 채널 | 언어쌍 내 비중 | 언어쌍별 본 평가 목표 | 시험하는 것 |
|---|---|---|---:|---:|---|
| P1 | 짧은 말 | peer | **10%** | 3개 | 짧고 완결된 질문·답변·요청의 의미 보존 |
| P2 | 대화 따라듣기 | 두 화자의 음성을 하나의 peer 입력으로 | **30%** | 9개 | 문맥·지시 대상·질문과 답의 관계 |
| P3 | 긴 설명 | peer | **20%** | 6개 | 중간 뜸·이어 말하기·조건과 결론·점진적 제시 |
| T1 | self/peer 주고받기 | 두 경로 동시 활성, 화자별 고정 라우팅 | **30%** | 9개 | 번갈아 이어지는 대화와 두 번역 경로의 동작 |
| P4 | 사람 낭독 | peer | **10%** | 3개 | 정돈된 발화에서의 기본 의미 품질·대기 |
| 합계 |  |  | **100%** | **30개** | 대화 유형 90%, 낭독 10% |

- 본 평가 설계 목표는 **언어쌍당 30개, 총 60개 에피소드**다. 확보·검수를 마쳤다는 뜻은 아니다. 자료 적격성 확인 후 정확한 파일·구간·원본 집단을 manifest에 동결한다.
- 비중은 사용 빈도 추정치가 아니라 **대화 중심의 평가 설계**다. P2와 T1을 주축으로 두고 긴 설명을 별도로 확보한다.
- 각 칸 안 에피소드는 균등 가중한다. 파일 수·말 수·패킷 수·체크포인트 수가 유형 비중을 바꾸지 않는다.
- T1은 하나의 에피소드 안에서 **역할 A 50% + 역할 B 50%**로 계산한다. 기본 프로토콜은 A=peer/B=self, VRCLT·Kikitan은 A/B 모두 self이되 별도 실행이다. 물리적 경로/실행 수를 이유로 T1 비중을 60%로 만들지 않는다.
- 원음 재료 기준 예정 비중은 사람 회화 원음 75%, 일한 합성 대화 15%, 사람 낭독 10%다. 사람 회화 75% 중 ASCEND P2/P3/T1의 **전체 점수 40%는 근사 시간축 재구성 조건**, 나머지 35%는 원래 구간 안의 시간표를 유지하는 조건이다. 사람 원음과 원래 대화 간격 보존을 혼동하지 않는다. 이것은 설계상 점수 비중이지 확보 완료나 녹음 시간 비율이 아니다.
- C1 무음·비언어 대조도 같은 실행·보고서에 남긴다. 번역할 의미가 없으므로 품질 100점이나 지연 0초를 주어 주 점수를 올리지 않는다.
- 일반/난조건, 혼용, 자기 정정, 맞장구, 겹침 등은 태그다. 같은 에피소드에 태그가 여러 개 있어도 중복 표본이나 가중치를 만들지 않는다.

필수 칸의 적격 자료를 확보하지 못하면 본 평가 동결을 보류한다. 낭독이나 쉬운 짧은 말로 채우거나 비중을 재분배하지 않는다. 수량·자료·비중을 바꿔야 한다면 본 결과를 보기 전에 설계 변경을 명시한다.

## 3. 데이터셋과 자료별 역할

| 자료 | 적용 범위 | 보존할 출처·제약 |
|---|---|---|
| [ASCEND](https://huggingface.co/datasets/CAiRE/ASCEND) | 영중 P1–P3 및 T1의 원본 | 사람 전사·화자·세션·분할 음성. 중국어/영어 혼용 자료이며 한 화자=한 언어가 아님. 데이터 라이선스 CC BY-SA 4.0 |
| [IngCrowd](https://huggingface.co/datasets/IngCrowd/japanese-themed-dialogue) | 일한 P1–P3 | 일본어 테마 잡담 10개, 약 121분. 혼합/화자별 WAV와 사람 시간 연결 전사 EAF. CC BY-NC 4.0 |
| [FLEURS](https://huggingface.co/datasets/google/fleurs) | 영중·일한 P4 | 영어·일본어 사람 낭독과 원문. 선택한 배포 revision·출처·라이선스·파일 해시 보존 |
| 영중 T1에서 파생한 일한 TTS | 일한 T1만 | 원본 사례 → 양언어 대본 → 실제 생성 음성 → 새 타임라인의 파생 관계. 합성임을 공개 |

### 3.1 ASCEND

- P1–P3는 영어 의미를 중국어로 번역하는 범위다. 중국어 문맥이 필요한 구간은 원래 순서로 보존하고 혼용 태그를 붙인다.
- 이미 목표 언어인 중국어 부분을 번역 성공으로 가산하거나, 번역하지 않았다는 이유만으로 누락 처리하지 않는다. 번역해야 할 영어 의미와 문맥 범위를 결과 전에 구분한다.
- 영어 행만 골라 사이의 중국어 턴을 삭제한 뒤 자연 대화로 이어 붙이지 않는다.
- `session_id`나 행 번호 하나로 서로 다른 split·화자의 대화를 조인하지 않는다. 원본 key는 revision·upstream split·id를 포함한다. 화자쌍·전사 문맥·파일명 시각·주석 순서를 함께 검토하고, 녹음 시각 역전·part 변화·문맥 단절에서 구간을 나눈다. `L` 순서는 후보 순서이지 검증된 전역 시계가 아니다.
- P2/T1은 짧고 연결된 구간별 화자 시차 추정을 우선한다. 추정이 불명확한 구간은 실제 발화의 검토된 순서와 고정 역할을 유지하고 사전에 정한 간격으로 재구성할 수 있다. P3는 같은 화자의 연속 설명과 필요한 혼용 문맥을 사용한다. 원래 마이크 공통 시계나 미배포 중간 음성을 확보하는 것은 더 이상 이 조건의 필수 전제가 아니다.
- 원본 클립 PCM·발화 내부 간격은 유지한다. 재생 시간표에는 원본 클립 구간, 파일명에서 추정한 위치·간격, 실험자가 정한 간격을 구분한다. 빈 구간에 넣은 무음은 원래 무음의 복원이 아니며 삭제된 발화가 없었다는 뜻도 아니다. 누락된 의미를 생성하거나 서로 무관한 발화를 연결하지 않는다.
- 시차의 비겹침 가정은 실제 겹침을 입증하거나 부정하지 않는다. 재구성 정책·예외·실제 샘플 위치·참조문·의미 체크포인트를 앱 결과 전에 고정하고 모든 프로필에 같은 입력을 사용한다. 공개 명칭은 **“ASCEND 사람 음성 기반 근사 재구성 대화”**다. 재생 입력 기준 대기는 측정하지만 원래 자연 대화 간격에서의 성능이라고 주장하지 않는다.
- 먼저 기존 개발 화자 집단의 대화 한 편을 실제 조립해 내용·접합부·역할 버퍼·샘플 대응을 확인한 뒤 전체 수량으로 확장한다. 같은 구간을 P2와 T1로 중복 계산하지 않으며, 미확인 참조·역할 누설을 시간축 완화로 통과시키지 않는다. R2의 자동 검수 수준은 공개하고, R6의 앱 입력·출력 검증은 별도다.

### 3.2 IngCrowd

- **채택은 확정**이다. 자연 회화 후보 탐색이나 일반 회화의 조건부 TTS 대체 단계로 되돌리지 않는다.
- P2는 mixed 음원으로 두 상대의 대화를 듣는다. P1/P3도 동일 자료에서 의미가 완결된 실제 구간을 선택한다.
- 공개 배포와 샘플 EAF/WAV 형식은 확인했지만, 전체 음성·전사 정확성·화자 독립성·유형별 분량 검수는 아직 하지 않았다.
- CC BY-NC 조건은 유지된다. 사용자의 자료 채택 승인을 권리자의 상업 이용 허락으로 해석하지 않는다. 실제 프로젝트 이용 목적과 외부 번역 서비스 입력, 공개 클립·영상·재배포 범위를 확인하고 필요한 경우 별도 허락을 확보한다.
- 권리 확인이 안 된 원음·전사를 공개 예시에 자동 포함하지 않는다. 목적 자체가 허용되지 않는 경우에는 실행 전에 해결하며, 임의로 다른 자료로 바꾸지 않는다.

### 3.3 낭독

- 사람이 읽은 영어·일본어 입력을 각각 중국어·한국어로 번역한다. 일본어 TTS T1을 낭독 P4로 다시 세지 않는다.
- 같은 문장의 다른 언어 녹음을 쓴다면 원본 문장 ID로 연결한다. 행 순서로 병렬 문장을 조인하지 않는다.
- 낭독도 동일 GEMBA-ESA·의미 대기·실패·비용 계약을 사용한다. 별도 벤치마크나 별도 주 순위를 만들지 않는다.

## 4. T1: 영중 원본과 일한 TTS 재구성

### 4.1 역할과 번역 방향

self는 내 음성을 상대에게 전달하는 경로, peer는 상대 음성을 받아 내가 읽는 경로다. 다른 벤치마크 앱을 뜻하는 `peer profiles`와 혼동하지 않는다.

아래 표와 동시 라우팅 규칙은 기본 T1 계약이다. VRCLT·Kikitan은 같은 화자·번역 방향을 유지하면서 §4.7의 self 분리 실행을 적용한다.

| 언어쌍 | peer: 화자 A | self: 화자 B |
|---|---|---|
| 영중 T1 | 영어 중심 원음 → 중국어 번역 출력 | 중국어 중심 원음 → 영어 번역 출력 |
| 일한 T1 | 일본어 TTS → 한국어 번역 출력 | 한국어 TTS → 일본어 번역 출력 |

- 화자 A/B와 self/peer는 에피소드 동안 고정한다. 발화 언어나 행 홀짝에 따라 라우팅을 바꾸지 않는다.
- 영중 원본에 코드 스위칭이 있으면 보존한다. 표의 ‘중심’은 한 화자가 항상 한 언어만 쓴다는 뜻이 아니다. 언어 혼용·목표 언어 문맥·실제 번역 대상 범위를 기록한다.
- 양 역할 모두에 번역해야 할 실질적인 의미가 있는 실제 주고받기 구간을 고른다. 서로 무관한 발화를 이어 붙이거나, 한쪽이 맞장구만 하는 구간으로 두 방향 번역을 검증했다고 하지 않는다.
- 한 화자의 연속 발화는 같은 역할이다. 질문과 후속 응답이 연결되는 두 사람의 근거 있는 순서를 유지하고, ASCEND는 §3.1의 근사 재구성 여부를 표시한다. 기본 표본은 거의 턴을 나눠 말하는 구간을 선택한다.
- 기본 T1은 한 앱 인스턴스에서 두 경로를 에피소드 시작 전에 켜고 끝까지 유지한다. 턴마다 켜고 끄거나 앱을 재시작하지 않는다.
- 영중과 일한의 T1 관계는 같은 이야기·역할의 파생 관계이지 음향·길이·언어 난도가 동일한 실험 대조군은 아니다.

### 4.2 영중 T1 적격성

선정 순서는 **출처와 대화 연결 근거 확인 → 역할 배정 → 양쪽 번역 대상 확인 → 근사 재생 시간표·접합부 검수 → 소스 동결**이다.

1. 양쪽 실제 원음·원래 화자·문맥에 맞는 발화 순서와 하나의 재생 시간축을 확인한다. 원래 녹음기의 공통 원점 증명 의무는 `ascend-reconstruction-v1`으로 대체됐다. 원본 대화 관계와 시차에 사용한 근거·추정·미확인을 각각 기록한다.
2. 입력에 실제 들리는 다른 화자·누설음도 참조 범위에 반영한다. 같은 mixed 음원을 두 입력에 넣고 화자 분리가 됐다고 주장하지 않는다.
3. §3.1에 따라 추정 시차 또는 명시적으로 설계한 간격을 사용할 수 있다. 고정된 두 역할 버퍼는 같은 길이·샘플 시계를 사용하고 원본 발화 PCM을 보존한다. 삽입 간격을 원래 자연 대화 간격이라고 부르지 않는다.
4. 개정 기준으로 선정·검수한 영중 T1을 먼저 소스 동결하고 그 사례만 일한 T1의 부모로 사용한다. 원본 ASCEND → 영중 재구성 → 일한 합성의 파생 관계와 각 시간표를 분리해 보존한다. 부모의 내용·역할·검수가 미완료인데 일한 합성본부터 만들어 완성된 쌍으로 세지 않는다.
5. 적격 T1을 목표 수만큼 확보하지 못하면 원본 검수 단계에서 중단한다. 영중까지 TTS로 바꾸거나 T1을 빼는 것은 이 계획에 포함되지 않는다.

### 4.3 일한 대본과 TTS 제작

TTS는 **Gemini 3.8 Flash TTS — `gemini-3.8-flash-tts`로 확정**한다. 기본 제작 단위는 **대화 스크립트 한 편 전체를 한 요청으로 생성**하는 것이다. 짧은 발화마다 생성해 붙이는 것을 전제로 하지 않는다. 실제 음성·역할 경계를 검수해 두 입력 스트림으로 만들고, 전체 생성에서 분리·품질 조건을 충족하지 못하는 경우의 턴 단위 제작은 4.5절에 따른다. 품질·비용·검수 보고는 모델 확정 후에도 유지한다.

**2026-10-27 오너 승인 실행 경로:** 같은 Gemini 3.8 Flash TTS를 **OpenRouter**의 `google/gemini-3.8-flash-tts`로 요청한다. 직접 Google API 키·과금 프로젝트 설정 의무는 이 선택으로 대체됐다. 오너가 지정한 `main` worktree의 `.env.local`에서 `VRC_BENCH_GEMINI_API_KEY` 항목을 명시적으로 읽는다. 변수 이름은 유지하지만 값은 오너가 준비한 OpenRouter 키다. 키를 출력·복사·커밋하거나 다른 앱 설정을 탐색하지 않는다. 첫 실행 승인은 **개발 4개 + 개발 1·3번 추가 take, 최대 6회 클라이언트 생성 요청·세전 API 사용료 US$1**, 생성 ID별 비생성 사용량 조회까지다. 자동 재시도·턴별 대체·본평가 생성·충전·계정 변경은 포함하지 않는다. 실제 준비된 요청과 승인 기록을 결합한 뒤에만 호출한다.

**파일럿 이후 오너의 추가 승인:** 오너는 일본어·한국어를 실제로 청취 검수한 뒤 내용·발음·자연스러움을 승인했다고 명시했다. 개별 검수자 숙련도·소요시간·take별 판정은 별도 제공되지 않았으므로 추정해 채우지 않는다. 역할 경계 검증은 이 승인과 별도로 남는다. 본평가 9개 대화를 각 1회씩 생성하는 **추가 최대 9회 클라이언트 POST·세전 API 사용료 US$1.50**와 비생성 사용량 조회도 승인했다. 현재 요율의 보수적 예약 합계는 $1.363968이며 요율·한도가 바뀌면 중단한다. 기존 파일럿 6회 한도를 충전하지 않으며 재시도·추가 take·턴별 대체·충전·계정 변경을 허용하지 않는다. 남은 파일럿 역할 경계 검증과 제작 방식 채택이 끝난 뒤 실행하는 승인이지, 검수 전 본편 생성이나 아직 없는 본편 음성의 품질 승인으로 간주하지 않는다.

1. **원문 기반 각색:** A의 원래 발화 의미를 일본어로, B의 원래 발화 의미를 한국어로 옮긴다. 원문이 혼용이어도 역할별 내용을 기준으로 옮기며, 측정 앱이 출력한 번역을 중간 대본으로 사용하지 않는다.
2. **대화 보존:** 부정·수치·조건·지시 대상·말투·질문과 답·자기 정정·의미 있는 망설임을 보존한다. 모호함을 과잉 설명하거나 어려운 부분을 다듬어 쉬운 시험으로 바꾸지 않는다. 불가피한 언어별 변화는 기록한다.
3. **두 언어 모두 생성:** 일본어 음성만 만들고 한국어를 텍스트로 대신하지 않는다. 역할별 고정된 기본 제공 음색으로 일본어·한국어 음성을 모두 만든다. 실제 참가자·유명인의 음성 복제는 하지 않는다.
4. **스크립트 단위 생성과 역할별 입력:** OpenRouter `POST /api/v1/audio/speech`의 `input` 배열에 전체 대화의 턴을 원래 순서로 넣고, A=일본어/Puck·B=한국어/Kore를 각 항목의 `voice`에 고정한다. `instructions`는 발화문과 분리된 연기 지시이며 upstream의 `speech_metadata.style`로 전달된다. 자연스러운 동료 간 대화·적당한 억양을 지향하되 과장된 낭독·추가 단어/감탄사·겹침을 유도하지 않고 원문의 망설임·자기 정정을 보존한다. 기본 공통 지시를 사용하며 턴별 지시는 기본값을 덧붙이는 것이 아니라 대체한다는 API 의미를 따른다. 반환 PCM을 정상 WAV로 감싼 뒤 실제 화자·턴 경계를 검수한다. 입력의 음색/역할 라벨을 출력 타임스탬프나 분리 트랙으로 간주하지 않는다.
5. **실제 음성 검수:** 대본 대비 누락·추가·숫자·고유명사·발음·화자·멈춤을 확인한다. 독립 ASR은 보조 수단일 뿐 정답 인증이 아니다. 음성이 대본과 다르면 입력을 수정·재생성하거나 부적격으로 제외하고 앱 오역으로 넘기지 않는다. 자동 검수만 했다면 그 수준을 공개한다.
6. **새 시간표:** 전체 생성에서는 실제 발화 경계·길이·턴 사이 간격을 그대로 사용하고 ‘합성 대화의 간격’으로 기록한다. 영중의 절대 타임스탬프를 복사하거나 일본어·한국어를 가속하지 않는다. 턴별 생성으로 전환한 에피소드는 실제 턴 길이와 채택한 영중 부모 재생 시간표의 간격으로 조립하며 ‘실험자가 삽입한 간격’으로 구분한다. 그 부모 간격도 근사·설계된 것이라면 원래 ASCEND 간격이라고 표시하지 않는다. 방식·예외 이유·시간표를 본 평가 전에 고정하고 선행·후행 무음 처리도 남긴다.
7. **한 번 동결:** 최종 역할별 WAV·재생 PCM·실제 음성 기준 전사·타임라인·해시를 고정하고 모든 프로필에 동일하게 재생한다. seed만으로 재현성을 주장하지 않으며 결과를 본 뒤 발음·간격을 바꾸지 않는다.
8. **의존성과 권리:** 영중 부모와 일한 파생본은 같은 `source_case_id`로 묶는다. 개발/본 평가 분리와 불확실성 계산에서도 함께 다룬다. ASCEND 파생 조건과 TTS 제공자의 입력·출력·음색 조건을 함께 보존한다.

**원문 불확실성·기록 복구에 관한 오너 결정:** 알아들을 수 없어 원전 전사에 `[UNK]`로 표시된 개발 4곳·본평가 6곳은 **그 불명 단어만 생략하고 위치·이유를 기록**한다. 알려진 앞뒤 내용·수치·부정·자기 정정을 삭제하거나 모르는 단어를 추측하지 않는다. 알려진 모호한 표현과 기존의 표시된 문맥 해석은 그 불확실성을 유지하며 완전한 원문 복원이라고 주장하지 않는다. 부모 manifest는 원래 `c52dcae…13556` 해시와 일치하게 복구했으나 상세 원본 참조 JSON·curation의 일부 검수 기록은 현재 없다. 오너는 이 과거 기록의 바이트 단위 복구를 실행 전제에 추가하지 말고 확보한 원문·부모 정보로 진행하도록 했다. 원래 CSV·화자·출처·전체 내용 연결을 확인하고 결손을 공개하되, 새 추론으로 옛 ASR/정렬 기록을 만들어 채우지 않는다. 이 결정은 새 JA/KO 대본·실제 음성 검수를 면제하지 않는다.

이 자료는 **‘영중 대화 기반 일한 합성 재구성 대화’**다. 자연 일본어·한국어 상호 대화 녹음으로 표시하지 않는다. 깨끗한 발음·번역체·합성 운율·특정 ASR 계열 친화성은 한계로 공개한다. 제작비는 앱 번역 비용과 분리한다.

### 4.4 재생과 평가의 공정성

- 두 역할은 공통 단조 시계에 맞춰 별도 입력 경로로 재생한다. 한 역할이 쉬는 동안 다른 역할의 음성은 그 역할에만 들어간다.
- 다음 턴을 시작하는 시각은 앱의 번역 출력 속도와 무관하다. 빠른 앱에는 빠른 대화, 느린 앱에는 긴 쉼을 주지 않는다.
- 이 시험은 고정 입력의 주고받기다. 사람이 번역을 읽고 답변을 바꾸는 상호작용 실험이나 실제 대화 성공률로 부르지 않는다.
- 같은 앱에서 self/peer의 입력 경로와 네이티브 출력 채널 귀속을 확인한다. 양쪽을 섞어 어느 방향 번역인지 모르는 텍스트를 정상 T1 결과로 채점하지 않는다.
- 기본 T1의 양쪽 경로를 관측할 수 없는 프로필은 T1 미지원/미측정 상태를 남긴다. 승인된 VRCLT·Kikitan self 분리 실행은 별도 조건이지 동시 경로 통과 증거가 아니다. 어느 조건이든 한쪽만의 좋은 점수를 T1 전체나 완전한 통합 점수로 대체하지 않는다.

### 4.5 스크립트 전체 생성과 턴 단위 생성

#### 공식 지원 범위

**검토 기준일: 2026-10-27, 승인된 OpenRouter 경로.** 공식 TTS 가이드와 두 화자 예제는 `input: [{text, voice, instructions?}, …]`를 한 요청으로 보내는 Gemini Flash TTS 대화를 지원한다. **입력을 턴별 항목으로 구성하는 것은 턴마다 API를 호출한다는 뜻이 아니다.** 직접 Google Interactions의 요청/응답 구조를 이 경로에 그대로 전달하지 않는다.

- 일본어와 한국어는 지원 언어다. 이번 일한 교대 대본의 실제 발음·화자 유지·언어 전환 품질은 pilot에서 확인한다.
- 모델 페이지의 입력 한도는 **8,192 tokens**, 출력 serving 한도는 **16,384 tokens**다. 계획한 30–90초 에피소드를 짧은 문장으로 잘라야 한다는 API 형식상 요구는 없다. 요청별 실제 입력 크기와 출력 종료·누락 여부는 별도 확인한다.
- 이 OpenRouter 경로는 `response_format: "pcm"`을 사용하며 **24kHz·mono·PCM16 little-endian 원시 바이트**를 반환한다. 원본 PCM을 보존하고 로컬에서 정상 WAV 헤더를 한 번 붙인다. 직접 Google 경로의 WAV/base64 응답과 혼동하지 않는다. 화자별 독립 파일이나 확정된 턴 타임스탬프는 제공되지 않는다.
- 두 기본 제공 음색을 사용한다. 이 구성에 필요한 모델 ID·음색·대본·메타데이터·API/SDK 버전·생성일을 동결한다. 음색 복제·맞춤 음색 제작은 기본 범위에 넣지 않는다.

근거: [OpenRouter TTS](https://openrouter.ai/docs/guides/overview/multimodal/tts), [speech API](https://openrouter.ai/docs/api/api-reference/tts/create-speech), [두 화자 예제](https://openrouter.ai/docs/cookbook/audio/two-voice-podcast), [Gemini 3.8 Flash TTS 모델·한도](https://ai.google.dev/gemini-api/docs/models/gemini-3.8-flash-tts). `provider.data_collection="deny"`·`zdr=true`를 사용한다. 이는 데이터 정책 필터이지 제공 경로 고정이나 내부 재시도 차단 증명이 아니다. speech API는 일반 Chat Completions의 `only`·`order`·`allow_fallbacks` 적용을 보장하지 않는다. 같은 모델의 실제 제공 경로와 비용을 생성 ID의 사용량 메타데이터로 남기며 클라이언트는 자동 재시도하지 않는다.

#### 결정: 에피소드별 전체 생성 우선

| 생성 단위 | 특성 | 이 계획의 선택 |
|---|---|---|
| **대화 스크립트 한 편 전체** | 모델이 질문·답변 순서를 한 요청에서 받음. 결과는 혼합된 한 음원이라 역할 경계 검수가 필요 | **기본.** 각 T1을 독립 요청으로 생성하고 자연스러운 연결감이 실제로 유지되는지 확인 |
| **완전한 화자 턴** | 생성 시점부터 역할이 확실하고 실패한 턴만 교정하기 쉬움. 호출 사이의 억양·음색·연결감은 흔들릴 수 있음 | 전체 생성이 정확한 역할 분리·대본 충실도 조건을 충족하지 못할 때의 제한된 제작 방식 |
| 짧은 문장·구절 조각 | 접합 지점이 늘고 발화 내부의 억양·멈춤을 재조립해야 함 | 기본 제작에서 사용하지 않음 |

전체 생성이 대화 연결감을 보존하기에 유리할 가능성은 **설계상 기대**이지 청취 검증 결과가 아니다. 실제 판단은 원음과 분리된 재생 음성을 함께 검수한 뒤 한다. 아홉 에피소드를 하나의 거대한 요청으로 합치지 않고, 각 에피소드의 문맥·실패·비용을 독립적으로 관리한다.

#### 전체 음원을 self/peer로 만드는 절차

1. 생성된 원본 WAV를 보존한다. 대본의 역할 순서와 실제 발화를 대조해 화자·발음·누락·추가·겹침을 확인한다. 대본 줄 순서만 보고 실제 화자 교대가 정확했다고 가정하지 않는다.
2. 실제 턴 시작·끝과 안전한 절단 지점을 표시한다. ASR/forced alignment는 경계 제안에 사용할 수 있지만 실제 청취·파형 검수 없이 정답 시간으로 채택하지 않는다. 무음 검출만으로 턴과 발화 내부의 쉼을 구별하지 않는다.
3. 원본과 **길이·샘플 시계가 같은** 두 재생 버퍼를 만든다. A의 구간은 peer에, B의 구간은 self에 배치하고 상대 역할 구간은 무음으로 둔다. 자기 역할의 음성만 모아 앞으로 당겨 붙이지 않는다. 생성된 질문·답 사이 간격과 두 경로의 동기화를 유지한다.
4. 검수한 비중첩 경계로 PCM을 배정한다. 의미 있는 소리가 누락·중복되거나 잘리지 않아야 하며, 무음·배경음의 배치/편집 정책도 기록한다. 수정하지 않은 재생 원음은 두 역할 버퍼를 합쳤을 때 복원돼야 한다. 이는 배정 산술의 검사이지 화자 판정이 맞다는 증명은 아니다.
5. 두 목소리가 실제로 겹친 구간은 시간으로 잘라도 분리되지 않는다. mono에서 한 목소리만 남길 수 있다고 가정하거나 음원 분리 모델로 검수 문제를 숨기지 않는다. 기본 T1은 비중첩 턴 교대이므로 겹침을 유도하는 `|reaction|` 문법을 사용하지 않고, 뜻이 있는 맞장구는 별도 역할 턴으로 적는다.
6. 잘림·목소리 혼입·대본 변경·불명확 경계가 있으면 원인을 기록해 같은 모델에서 교정한다. 전체 생성으로 해결되지 않아 턴 단위로 전환하면 해당 에피소드의 방식·이유·삽입 간격·접합부 검수 결과를 명시한다. 단순 비용 절약이나 번역 앱 결과를 근거로 방식·원음을 바꾸지 않는다.

턴 단위 전환에서도 **한 사람이 발언권을 유지하는 연속 발화는 한 턴**으로 생성한다. 한 턴 안의 문장·자기 정정·의미 있는 멈춤을 임의로 분할하지 않는다. 같은 기본 음색·말투 설정을 유지하고 WAV를 정상 디코딩한 PCM으로 조립한다. WAV 파일 바이트를 그대로 이어 붙이거나 RIFF 헤더 길이가 항상 같다고 가정하지 않는다.

ASCEND 파생 조건, Gemini 입력·출력 이용 조건과 선택 음색의 공개 범위를 확인한다. 유료 사용을 원음 공개 데이터셋 재배포의 포괄 허가로 해석하지 않는다. 모델 선택은 실제 생성·결제·계정 설정 변경의 실행 승인을 뜻하지 않는다.

### 4.6 TTS 품질 검산·제작 방식 확인·보고

**좋은 목소리와 올바른 벤치마크 입력은 다르다.** TTS가 대본의 부정·숫자·말끝을 바꾸면 번역 앱이 아니라 입력 제작이 실패한 것이다. 번역 점수용 GEMBA-ESA를 TTS 자연스러움 점수로 재사용하지 않는다.

#### 품질 항목

| 항목 | 확인할 것 | 보고 방법 |
|---|---|---|
| 대본 충실도 | 누락·추가·반복·의역·부정/숫자/조건 변경 | 언어별 첫 생성의 오류 사례 수/전체 수, 오류 구간, 수정·재생성 이유 |
| 일본어 발음 | 한자 읽기, 인명·지명, 수사·조수사, 장단음, 문맥에 맞는 억양 | 실제 발음과 사전 정한 허용 읽기, 불명확 판정 |
| 한국어 발음 | 고유어/한자어 수사·단위, 이름, 연음, 외래어, 종결어미 보존 | 같은 방식의 언어별 근거. 일본어 결과와 평균해 결함을 숨기지 않음 |
| 대화 자연스러움 | 질문/답의 억양, 맞장구, 망설임·자기 정정, 말투·반응 연결, 과도한 연기·낭독조 | 전체 생성 원음과 역할별 재생 음성의 청취 근거. 제작 방식을 비교하면 동일 대본·음색으로 판단하며 작은 pilot을 일반적 품질 증명으로 부르지 않음 |
| 역할·음향 무결성 | 목소리 일관성, 화자 귀속, 잘림·잡음·누설·겹침, 타임스탬프 | 구간별 통과/실패/미확정과 원음 증거 |
| 제작 안정성 | 첫 생성 사용 가능성, 재생성 횟수, 수정 작업량 | 최초 결과와 폐기 결과도 보존. 채택본만 보고해 실패율을 숨기지 않음 |

독립 ASR의 CER/WER는 전사 불일치의 선별 도구다. 일본어 한자/가나·한국어 띄어쓰기 차이를 발음 오류로 단정하지 않으며, ASR가 잘 알아들었다고 자연스러움이 검증됐다고 하지 않는다. 대본을 아는 텍스트 judge만으로 실제 발음·억양을 인증하지 않는다.

#### 작게 시범 생성하고 제작 방식을 동결

1. 본 평가와 분리된 **개발 대화 4개**를 먼저 동결한다. 각 6턴 정도로 양언어를 포함하고, 일반 주고받기·부정/수치/고유명사·맞장구/자기 정정·긴 턴 뒤 짧은 응답을 다룬다. 길이는 장면당 약 30–45초를 목표로 하되 실제 길이를 기록한다.
2. Gemini 3.8 Flash TTS와 권리 확인된 기본 음색 두 개를 고정한다. 각 개발 스크립트를 전체 대화 한 요청으로 생성한다. 특정 앱의 ASR가 잘 알아듣는 음색을 앱 결과를 보고 고르지 않는다.
3. 네 장면 중 사전 선택한 두 장면은 전체 생성 한 번을 추가해 변동성을 확인한다. 두 take는 독립 원문이 아니다. 전체 생성에서 경계·연결감·내용 문제가 드러난 장면만 같은 음색의 완전한 턴 단위 생성과 비교하고 원인·호출·비용을 남긴다. 음색·설정의 무제한 탐색은 하지 않는다.
4. 최종 비교 청취의 재생 형식·음량 조건을 맞추되 시간 압축이나 의미를 바꾸는 편집은 하지 않는다. 양언어 각각 청취 가능한 검수자가 대본·음성을 대조한다. 가능하면 언어별 두 명의 독립 판단을 받되 확보 인원·숙련도·불일치를 그대로 보고한다. 청취 검수 미확보 상태를 ‘자연스러움 검증 완료’로 만들지 않는다.
5. **권리·양쪽 언어의 의미 충실도·정확한 역할 분리**를 먼저 확인한다. 최종 채택 음성에 해결되지 않은 의미 변경·잘림·다른 역할 누설을 남기지 않는다. 전체 원음뿐 아니라 두 입력을 공통 시간표로 재생했을 때의 대화 연결감과 접합부도 검수한다.
6. 모델과 두 역할 음색을 고정하고 전체 생성 우선 규칙 및 턴별 전환 조건을 본 평가 전에 명시한다. 각 에피소드의 생성 단위·전환 이유를 보존한다. 문장마다 잘 나온 take를 골라 붙이는 방식은 사용하지 않는다.
7. 생산 단계의 재생성은 실패 원인에 근거한 교정으로 한정한다. 초기 생성과 교정 결과·비용을 모두 남긴다. 무한 재생성 대신 사전 합의한 횟수·금액 상한에서 멈추고, 대본을 쉽게 바꿔 통과시키지 않는다.
8. **제작 방식·품질 검수 보고가 끝난 뒤** 본 평가용 9개 T1을 제작·검수·동결한다. 실패·변경 근거까지 보존하며 본 번역 결과를 보고 원음을 다시 선택하지 않는다. 파일은 14개 프로필과 반복 실행에 재사용한다.

#### 현재 확인 범위

오너가 선택한 OpenRouter의 Gemini 3.8 Flash TTS로 승인된 개발 pilot 6회(4개 대화와 사전 선택한 두 대화의 추가 take)를 실제 생성했다. 반환된 24kHz mono PCM16LE 원본을 보존하고 WAV로 감쌌으며, 6개 모두 디코딩한 WAV와 원본 PCM의 바이트 일치를 확인했다. [현재 R3 기록](../corpus/r3/status.json)에 음원 hash·실제 길이·확인 범위를 남겼다. 오너는 이후 양언어 실제 청취 후 내용·발음·자연스러움을 승인했다고 명시했다. **품질 승인과 실제 역할 경계·입력 스트림 검증은 별개**다. 남은 역할 검증과 제작 방식 채택 후 새로 승인된 본평가 9회/$1.50 범위에서 생성한다.

### 4.7 승인된 VRCLT·Kikitan self-only 예외

적용 프로필은 VRCLT1·VRCLT2·KIKI1·KIKI2다. Kikitan은 오너가 VRChat 없는 실행을 선택하여 추가한 예외다. 원래 desktop 입력의 VRChat 프로세스 제약은 그대로이며 우회·패치·가짜 프로세스로 해결했다고 주장하지 않는다.

- **일반 케이스:** P1/P2/P3/P4와 C1을 모두 실제 microphone/self 경로로 재생한다. 영어 원음은 영→중, 일본어 원음은 일→한이다. ‘self’로 바꿨다고 일반 케이스의 번역 방향까지 중→영·한→일로 뒤집지 않는다.
- **T1:** 같은 에피소드의 A·B 역할 음원을 각각 고정 방향의 별도 self 세션으로 실행한다. 영중은 A=영→중/B=중→영, 일한은 A=일→한/B=한→일이다. VRCLT `inbound`와 Kikitan `desktop_translation`은 OFF로 유지하며 턴마다 목표 언어를 바꾸거나 두 언어를 한 고정 목표 세션에 섞지 않는다.
- **시간표:** §4.5의 역할별 WAV와 무음·발화 위치·전체 길이를 그대로 사용한다. 두 pass를 한 세션에 이어 붙이거나 자기 발화만 앞으로 당기지 않는다. 각 pass의 재생 원점을 기록하고 원래 에피소드 상대 시각에 연결한다. pass 사이 준비 시간은 번역 지연이 아니다.
- **세션:** A와 B 사이에 정상적인 세션 종료/새 세션 및 고정 source/target 설정을 적용한다. 한 pass 안에서는 턴별 reset하지 않는다. 각 pass는 원래 전체 에피소드 시간축과 마지막 공통 음성 종료 후 15초 관측 구간을 확보한다.
- **귀속:** `episode_id`는 하나, `pass_id`는 A/B 별도, 실제 `input_channel=self`, 논리적 `role=A/B`를 남긴다. 수집된 self 텍스트를 peer 출력으로 이름만 바꾸지 않는다.
- **평가:** A/B 각각 같은 GEMBA-ESA·의미 체크포인트를 적용하고 50:50으로 합친다. T1 비중 30%, 두 언어쌍 50:50, 원래 논리 에피소드 수는 유지한다. 양쪽 중 하나가 미측정이면 완전한 T1/통합 점수를 만들지 않는다.
- **비교 한계:** 같은 자료·비중의 self 대체 결과이지 동시 self/peer 동작·경로 간 간섭을 시험한 결과는 아니다. 통합 공개표에는 `self / T1 양방향 분리`를 같은 행에 표시하고, 그래프도 조건을 구분한다. 기본 peer/동시 T1과 같은 조건의 우열로 해석하지 않는다.
- **비용:** 두 pass의 실제 비용을 모두 더한다. 표준 입력 1시간 비용의 분모는 원래 에피소드 시간축 한 번이며, 분리 재생 시간을 두 번 더해 비용을 인위적으로 반으로 낮추지 않는다. 실제 두 pass의 재생/운영 시간은 별도 원장에 남긴다(§11).

## 5. 코퍼스 준비와 표본 독립성

1. 준비 단위는 원본 대화 → 화자 턴 → 의미가 이어지는 에피소드다. 자연 회화는 대략 30–90초를 작업 목표로 삼되 의미를 시간에 맞춰 자르지 않는다. P1은 더 짧고 P3는 더 길 수 있다.
2. 같은 원음 구간을 P1/P2/P3/T1에 반복 배치하지 않는다. 원본 대화가 같아도 실제 사용 구간은 겹치지 않게 선정하고 공통 대화 집단은 보존한다.
3. 개발 pilot은 두 언어쌍·다섯 유형에서 적어도 한 사례씩 확보한다. 개발 부모와 그 TTS 파생본은 모두 본 평가에서 제외한다.
4. 개발/본 평가는 원본 대화·확인 가능한 연결 화자 집단으로 분리한다. 낭독은 공통 원문 ID를 포함한다. 확인할 수 없는 화자 재참여를 독립으로 인증하지 않는다.
5. 에피소드별 실제 가청 원문, 역할·언어, 번역 대상/문맥 구분, 핵심 의미·의미 체크포인트·허용 의역을 결과 전에 고정한다. 제품 ASR을 참조 원문으로 바꾸지 않는다.
6. 유일한 모범 번역문과 문자열 일치를 요구하지 않는다. 참고 번역은 활용할 수 있지만 다른 정확한 표현을 오역으로 만들지 않는다.
7. 본 평가의 앱 재생은 기본 한 번이다. VRCLT·Kikitan T1은 역할별 한 번씩의 두 pass가 하나의 논리 에피소드이며 재시도나 표본 추가가 아니다. 사전 선정한 각 언어쌍×유형 한 사례는 별도 반복 실행으로 변동성을 확인하되 본 점수의 표본 수·비중을 늘리지 않는다. 실패 뒤 임의로 좋은 재실행을 골라 본 결과와 바꾸지 않는다.
8. 불확실성은 원본 대화·연결 화자/원문 집단 단위로 다룬다. TTS 음색 수, 턴 수, 체크포인트 수를 독립 원본 수로 세지 않는다. 집단이 적으면 집단별 결과와 제한을 우선 공개한다.

표본 수를 맞추려고 불명확한 전사를 확정하거나, 비슷한 녹음을 복제하거나, 데이터셋의 upstream test 이름만으로 학습 미노출을 주장하지 않는다.

## 6. 실제 관측과 기존 분석 결함의 차단

[발견된 분석 이슈](../.data/issue8/batch-analysis-v1/discovered-analysis-issues.md)는 기존 문제의 근거다. 아래 문제는 해결됐다고 가정하지 않고 새 수집·평가의 완료 조건으로 삼는다.

| 발견된 문제 | 새 계약 |
|---|---|
| 다른 원문에 번역을 붙여 추가·누락을 중복 감점 | 완결 에피소드와 실제 문맥을 입력으로 사용. 문장↔패킷 1:1 확정 연결에 주 품질을 의존시키지 않음 |
| 누적 출력을 이어 붙여 반복으로 감점 | 실제 지원되는 append/replace/clear와 수정 관계를 보존해 최종 의미 이력을 재구성. 화면 scroll을 관측했다고 가정하지 않음 |
| 마지막 결과만 남겨 앞선 출력·페이지를 잃음 | 실제 네이티브 출력 이력을 보존. 마지막 패킷 하나를 전체 번역으로 사용하지 않음 |
| 실제 들린 다른 화자를 환각으로 취급 | 입력의 가청 범위·전체 화자·문맥을 포함하고 역할별 채점 대상은 명시 |
| 하네스가 기한 전에 앱을 중지했는데 무출력 0점 | 앱의 번역 기회·입력 재생·관측 연속성을 확인. 하네스 개입은 invalid/N/A |
| 출력 해석 방식에 따라 좋은 일부만 남는 평균 | 예정된 전체 manifest와 가중 범위 보존. 미확보를 정상 표본에 재분배하지 않음 |

- 원본 음성·앱 로그·OSC·공개 이벤트를 보존한다. 기본은 **일반 케이스 실제 peer 입력→앱 번역 출력, T1 self/peer 두 경로**다. 승인된 VRCLT·Kikitan은 §4.7의 self-only 조건으로 구분하며, self 입력에 상대 음원을 넣고 이름만 peer로 바꾸지 않는다.
- 공통 이벤트에는 출력 경로·채널·번역문·원시 레코드·수정 관계·발생/수집 시각과 불확실성을 남긴다. 프레임·OCR·렌더링 시각을 이들 값에서 추정하지 않는다.
- `A → A+B → A+B+C`를 독립 번역 세 개로 만들지 않는다. 실제로 다시 말한 같은 문장을 문자열 중복이라는 이유로 삭제하지 않으며, 원래 ID가 없는데 수집 순번을 발화 ID라고 부르지 않는다.
- 최종 품질용 텍스트는 관측된 **번역 출력**에서 재구성한다. 각 부분은 원시 출력 근거로 돌아갈 수 있어야 한다. 내부 provider 응답·ASR 원문·디버그 preview를 완전한 번역 결과와 바꿔 쓰지 않는다.
- 수정된 중간 오역은 최종 영구 오류로 세지 않지만 출력 이력도 삭제하지 않는다. 중간 오역 후 정정은 출력 과정 진단이며 실제 사람이 그 오역을 읽었다는 뜻이 아니다.
- 역할·수정 관계·텍스트 완전성이 불명확하면 해당 품질/시간은 N/A와 이유를 남긴다. 제품의 실제 무출력과 수집기의 누락을 구별한다.

### 6.1 공통화할 것은 수집 계약이지 앱의 프로토콜이 아니다

결정은 **앱별 읽기 전용 어댑터 → 하나의 `native_output_event` 계약 → 공통 재구성·GEMBA-ESA·대기 집계**다. 모든 앱에 `/chatbox/input`이 있다고 가정하지 않는다. 기존에 노출된 기능을 지원 설정으로 켤 수는 있지만, 패치·DLL 주입·함수 후킹·TLS 중간자·비공개 메모리 덤프는 수집 전제로 삼지 않는다. 공통 수집기를 구현하는 것과 제품을 개조하는 것은 별개다.

- **우선순위:** 역할과 번역문이 있는 기존 구조화 이벤트/네이티브 출력 → 온전한 역할별 로그 → 해당 peer 출력이 입증된 OSC. 단순히 포맷이 편하다는 이유로 다른 처리 단계의 이벤트로 바꾸지 않는다.
- **주 종점 단계:** 앱이 받아들여 결과 소비자에게 내보내는 `translation_output`. provider 응답 원문, ASR 완료, 출력 큐 입장, chatbox 전송 완료, 수집기 수신은 다른 단계다. 같은 JSON으로 정규화해도 단계 차이가 없어지지 않는다.
- **텍스트 동등성:** 주 품질에는 목표 언어 번역문을 내용 손실 없이 확보한다. 길이 제한으로 잘린 chatbox·일부 preview·원문/번역 경계가 모호한 로그만 확보했다면 완전한 native 번역문과 같은 조건으로 채점하지 않는다. 이 경우 수집 한계와 관측 가능한 별도 결과를 남긴다.
- **시간 동등성:** 같은 native 출력 단계의 발생 시각, 또는 그 시각의 검증된 관측 구간을 사용한다. UI/OSC 전송 큐의 대기까지 포함한 값과 큐 전 번역 출력 값을 한 지연 순위에 섞지 않는다. 적합한 시간을 얻지 못한 앱도 품질·비용·프로필 행을 유지하며 시간만 미측정으로 둘 수 있다.
- **출력 이력:** 앱이 중간 결과를 내보내는데 로그가 최종본만 보존한다면 최종 품질과 중간 출력 대기 측정의 가능 여부를 분리한다. 수집하지 못한 중간 결과를 없었던 것으로 간주하지 않는다.
- **권한·부하:** 공개 로컬 API의 기존 인증을 사용하고 승인되지 않은 제어 요청은 보내지 않는다. 파일은 읽기 전용으로 수집하며 로테이션·줄 경계·로그 수준·큐 손실을 확인한다. 추론·출력 방식이 달라지는 설정은 계측 설정으로 위장하지 않는다.

현재 `bench/osc.py`의 수신기는 `/chatbox/input`·`/chatbox/typing`만 저장한다. 새 peer 주소나 로그를 자동 수집하지 않으므로 이 하네스에 어댑터와 채널 계약을 추가해야 한다. 기존 self 캡처와 해석 규칙은 역사적 결과로 보존하고 새 실행에 그대로 적용하지 않는다.

### 6.2 시계·역할·원시 증거 계약

| 필드 | 의미 |
|---|---|
| `profile / app_version / instance / clock_session` | 어떤 빌드·모델 프로필·실행에서 수집했는지 |
| `input_channel / role / pass_id / source_language / target_language` | 실제 self/peer 입력과 논리 역할 A/B를 분리. VRCLT·Kikitan T1은 두 pass 모두 self이며 역할은 동결 입력 manifest에서 귀속 |
| `transport / native_endpoint / endpoint_stage` | OSC 주소, 이벤트 종류, 로그 종류 및 앱 내부의 정확한 발생 단계 |
| `translated_text / source_text / native_id / revision / update_kind` | 실제 제공 필드만 보존. 미제공 ID·final·수정 관계는 unknown이며 임의로 채우지 않음 |
| `producer_time_raw / producer_clock / collector_received_monotonic` | 앱이 남긴 원래 시각과 하네스의 단조 수신 시각을 별도 보존 |
| `event_time_interval / resolution / clock_mapping / uncertainty` | 공통 재생 시계에 연결한 사건 시각 범위와 근거. 근거 없는 정확한 시각은 만들지 않음 |
| `raw_evidence / stream_sequence / loss_or_gap` | 원시 패킷·이벤트·파일 offset/hash, 수집 순서, 관측 공백·손실 |

로그 행을 읽은 시각은 번역 발생 시각이 아니다. 원래 로그 시각이 있으면 그 생성 지점·시간대·해상도·시계 변화를 확인하고 재생 시계와 대응시킨다. source timestamp 없는 OSC는 수신 시각을 사실 그대로 보존하며, 전송/수집 지연을 검증하지 않은 채 번역 발생 시각으로 등치하지 않는다. 원래 timestamp가 발화 시작이나 메시지 생성 시각인 경우에도 번역 완료 시각으로 재사용하지 않는다.

15초 관측 종료 때 파일·이벤트의 늦은 배달을 안전하게 회수할 수는 있지만, 유효한 발생 시각 근거 없이 늦게 읽힌 결과를 과거 관측점에 소급하지 않는다. 반대로 파일 flush가 늦다는 이유만으로 원래 시각이 입증된 출력을 제품의 늦은 번역으로 바꾸지 않는다. 경계 불확실성이 +2/+5/+10/+15초를 가로지르면 범위/판정 불가로 보존한다.

T1은 역할별 endpoint·명시적 source 필드가 우선이다. 같은 주소로 두 역할이 합쳐지고 구분 근거가 없으면 일반 peer-only 수집 가능성과 T1 수집 가능성을 분리한다. 원시 로그에는 키·계정·압축 config snapshot이 포함될 수 있으므로 공개 자료는 허용 필드만 추출하고 전체 원장을 그대로 배포하지 않는다.

### 6.3 전수조사 범위: 6개 앱·14개 프로필

아래 표는 **현재 승인된 수집 계약**이다. 정적 경로 조사와 실제 확인을 구분하고, 확인된 범위는 [catalog](../profiles/catalog.json)와 [R1 실측 기록](benchmark-implementation-plan.md#r1-implementation-and-actual-feasibility)에 따른다. 대표 일반 EN→ZH 성공은 다른 모델·언어·T1이나 최종 품질·시간 진입으로 승계하지 않는다. 이전 self/OSC 기록도 역사적 근거로 보존한다.

프로필 인벤토리는 [catalog](../profiles/catalog.json)의 14개를 모두 유지한다. 모델 열은 기존 비교 의도이며 실제 peer 모델·설정·사용량은 새 manifest에 명시한다. 특히 PuriPuly의 peer ASR은 self ASR와 별도 설정이다.

| 프로필 | 유지할 모델 비교 구성 | 우선 수집 경로 | 새 측정의 핵심 선행조건 |
|---|---|---|---|
| PP1 | Gemini Transcribe + Gemma 혼합 OpenRouter 경로 | PuriPuly CLI `translation` 이벤트 | peer ASR를 별도로 Gemini 경로에 맞추고 실제 모델 확인 |
| PP2 | Gemini Transcribe + GPT 6 Luna 연결 | 같은 CLI 이벤트 | peer ASR·기존 연결·양방향 요청 귀속 확인 |
| PP3 | Gemini Transcribe + Index | 같은 CLI 이벤트 | peer ASR 명시, PP4와 실제 peer 설정 차이 확인 |
| PP4 | CPU-auto local ASR + Index | 같은 CLI 이벤트 | **peer도** `local_cpu_auto`로 계획하고 언어별 실제 local 모델·CPU 실행 확인 |
| VRCT1 | Google Web Speech + m2m100 CPU | 인증된 WebSocket `RECEIVED`/`SENT` | speaker 입력과 역방향 언어 설정, WebSocket 활성화 |
| VRCT2 | Whisper base CPU + Google web 번역 | 같은 WebSocket | 누적 ASR 재인식·중복 억제와 출력 수정 관계 검수 |
| VRCT3 | Google Web Speech + OpenRouter Gemma | 같은 WebSocket | speaker 요청의 실제 모델/접근과 출력 단계 확인 |
| VRCS1 | Qwen3-ASR CPU + OpenRouter Gemma | External API `/v1/events` | speaker target, 공유 ASR 언어 설정과 T1 auto 감지 검수 |
| VRCS2 | Gemini Transcribe + OpenRouter Gemma | 같은 External API | 양쪽 세션의 auto 감지·언어 필드 누락·중간 결과 검수 |
| VRCLT1 | Gemini Live Translate | self `/chatbox/input` OSC + `FINAL` 로그 대조 | self-only; 일반 영→중·일→한, T1 양방향 별도 self 세션; 누적/잘림 검수 |
| VRCLT2 | Qwen LiveTranslate / 기존 Beijing 경로 | 같은 self OSC와 파일 로그 | 같은 self-only 조건; 기존 workspace·모델 유지 |
| KIKI1 | Bing ASR + Google 번역 | headless WebSocket `recognition` | self-only; 정확한 가상 케이블 마이크, desktop/user-data/chatbox OFF, 고정 방향 및 T1 별도 self 세션; 과거 headless 캡처 충돌은 미해결 이력 |
| KIKI2 | Gemini Live Translate | 같은 headless WebSocket | ordinary EN→ZH 소규모 실측 근거 재사용; 다른 범위와 누적 출력·`final` 의미는 별도 검수 |
| VRCLS1 | 기존 remote ASR + Developer 번역 | 설치 1015의 역할별 파일 로그 | named loopback/마이크 분리, 로그 경계·번역문 완전성 확인 |

설정 변경은 허용된 파일럿의 명시적 준비 작업이다. 실제 입력·앱·설정·출력 경로를 해당 실행의 revision으로 동결하며 과거 실행 기록을 수정하지 않는다. 자격·과금·지원 조건을 모르는 provider로 자동 전환하지 않는다.

### 6.4 앱별 수집 세부 계약

#### PuriPuly — PP1–PP4

- **버전 근거:** 설치 기록은 2.9.1이며 이번 검토 소스는 `55377ed15768faa42ff6fa15b6a83df570e696bd`다. 과거 문서의 2.9.0 소스를 그대로 적용하지 않았다. 설치 2.9.1의 공개 commit과 실제 바이너리 간 정확한 빌드 대응은 아직 별도 확인 대상이다.
- **입력:** 지원하는 peer target은 기본/지정 출력 장치 또는 process이며, process 유형은 일반 실행 파일·VRChat·Discord다. 지원 CLI의 peer 시작에는 `capture set peer on --accept-peer-terms`가 있다. 약관 동의·장치/프로세스·peer 언어·번역 활성 상태를 실제로 확인한 뒤 사용한다.
- **모델·언어:** `stt.provider`와 `peer_stt.provider`는 별개다. 기존 비교 의도를 유지할 **계획값**은 PP1–PP3의 peer `gemini_transcribe`, PP4의 peer `local_cpu_auto`이며 현재 적용값을 관측했다는 뜻은 아니다. CPU-auto는 source 언어에 따라 서로 다른 local 모델을 고를 수 있다. 번역기는 app-level request owner를 두 채널이 공유한다. `languages.peer_source_language`, `peer_target_language`, `peer_source_mode`, `peer_expected_languages`도 별도로 설정·보존한다.
- **주 수집:** peer는 `puripuly.exe events follow --topic translation --channel peer --include-translations`, T1 self는 같은 명령의 `--channel self`다. 필요한 ASR 근거는 `--topic transcript --include-transcripts`로 별도 확보한다. 기존 정상 GUI host에 연결하는 공개 CLI를 사용하며 대체 host를 몰래 시작하지 않는다.
- **필드:** `topic/channel/source/text/utterance_id/sequence/instance_id`. `sequence`는 시간이나 revision이 아니다. 공개 projection은 `origin_wall_clock_ms`, `update_id`, `is_final`, 언어 필드를 전달하지 않는다. transcript partial/final도 같은 topic이므로 topic만 보고 final을 만들지 않는다. 이벤트 history 256개·subscriber queue 32개의 경계와 gap 통지를 보존하고 재시작 시 새 instance/session으로 구분한다.
- **시간:** CLI 수신 시각을 기록할 수 있지만 원래 이벤트 발생 시각은 없다. peer는 overlay projection 뒤, self는 이후 overlay/chatbox 출력 전에 `translation` 이벤트를 내므로 두 채널의 처리 단계도 검수한다. 별도 `last_speech_to_overlay_applied_ms`와 self `chatbox_send` 진단을 공통 번역 출력 p50/p90에 섞지 않는다.
- **보조 로그:** `%LOCALAPPDATA%\puripuly-heart\puripuly_heart.log`의 `[Conversation] Peer · Listen` 원문/번역 레코드는 ms 표기 wall clock을 제공한다. 그러나 원문/번역이 별도 레코드이고 결합할 utterance ID가 없으며 secret redaction이 텍스트를 바꿀 수 있다. 같은 문장·인접 시각만으로 CLI 이벤트에 시간을 강제로 붙이지 않는다. 회전은 20 MiB·backup 1개이며 `logs follow`를 이 main-file 내용의 완전한 대체로 가정하지 않는다.
- **OSC 판정:** 검토 소스의 chatbox 자격은 self만이다. peer 번역문 OSC를 주 경로로 계획하지 않는다. PuriPuly 제어용 OSC 파라미터도 번역문이 아니다.
- **진입 조건:** 두 역할의 전체 번역문·실제 peer 모델은 CLI 경로로 검증한다. 원래 시각/전달 지연의 범위를 입증하지 못하면 품질과 시간의 진입 상태를 분리한다. 같은 출력 내용이더라도 peer ASR가 다른 모델이면 프로필·비용 설명을 고쳐 동결해야 한다.

근거: [공개 CLI](https://github.com/kapitalismho/PuriPuly-heart/blob/55377ed15768faa42ff6fa15b6a83df570e696bd/docs/cli.md#L680-L715), [이벤트 projection](https://github.com/kapitalismho/PuriPuly-heart/blob/55377ed15768faa42ff6fa15b6a83df570e696bd/src/puripuly_heart/app/services/application_control_events.py#L15-L120), [peer STT resolver](https://github.com/kapitalismho/PuriPuly-heart/blob/55377ed15768faa42ff6fa15b6a83df570e696bd/src/puripuly_heart/app/wiring/wiring_stt_factory.py#L1240-L1351), [공유 번역기](https://github.com/kapitalismho/PuriPuly-heart/blob/55377ed15768faa42ff6fa15b6a83df570e696bd/src/puripuly_heart/app/wiring/wiring_runtime_pipeline.py#L940-L1010), [언어 설정](https://github.com/kapitalismho/PuriPuly-heart/blob/55377ed15768faa42ff6fa15b6a83df570e696bd/src/puripuly_heart/config/settings_vnext/schema.py#L394-L410), [출력 순서](https://github.com/kapitalismho/PuriPuly-heart/blob/55377ed15768faa42ff6fa15b6a83df570e696bd/src/puripuly_heart/core/orchestrator/translation_output_projection.py#L2600-L2691), [로그 기록](https://github.com/kapitalismho/PuriPuly-heart/blob/55377ed15768faa42ff6fa15b6a83df570e696bd/src/puripuly_heart/core/runtime_logging.py#L1493-L1548), [설치 2.9.1 기록](../profiles/evidence/issue8/pp291-installed-build-amendment.json).

#### VRCT — VRCT1–VRCT3

- **버전 근거:** 설치 관측 3.6.0, 검토 릴리스 commit `7ad46876e60d7b6e053489090797e2228f320da5`. 기존 speaker/WebSocket OFF 관측을 peer 미지원이라고 해석하지 않는다.
- **입력·언어:** 선택한 speaker 출력 장치의 loopback을 사용한다. peer는 `SELECTED_TARGET_LANGUAGES`를 source, `SELECTED_YOUR_LANGUAGES`를 destination으로 사용하며 self는 반대다. 영중은 YOUR=중국어/TARGET=영어, 일한은 YOUR=한국어/TARGET=일본어의 관계를 확인한다. 각 역할 목표는 하나로 고정한다.
- **주 수집:** 기존 인증 WebSocket 서버를 지원 설정으로 활성화하고 수집기를 입력 재생 전에 연결한다. 기본 loopback port는 2231이며 실제 port/token은 해당 실행 설정을 사용한다. collector는 인증 이후 수신 전용이며 번역/제어 메시지를 보내지 않는다.
- **T1 구분:** microphone/self는 `SENT`, speaker/peer는 `RECEIVED`. payload의 `src_languages/dst_languages/message/translation[]/transliteration[]`를 보존한다. **R1 소스 확인 정정:** OCR도 `RECEIVED`를 사용하지만 `source:"ocr"`는 별도 UI payload에만 추가되고 주 WebSocket payload에는 없다. 따라서 source 필터로 OCR을 제외했다고 주장하지 않는다. 불필요한 OCR/외부 텍스트 입력을 끄고 독립된 설정·실행 근거를 동결한 경우에만 `RECEIVED`를 peer 음성으로 귀속한다. 그 근거가 없으면 역할/입력 귀속은 미확정이다. 언어 문자열만으로 역할을 추측하지 않는다.
- **시간·수정:** 앱 timestamp·event/utterance/revision ID·final marker가 없다. WebSocket 전송은 `_processMessage`의 OSC 시도와 UI dispatch 이후다. 이 수신값을 번역 함수 반환 시각으로 부르지 않는다. Google/Whisper의 누적 오디오 재인식과 연속 동일 텍스트 억제를 고려하며 한 메시지를 한 원문 발화로 단정하지 않는다.
- **대안:** peer OSC는 별도 `SEND_RECEIVED_MESSAGE_TO_VRC` 설정으로 가능하지만 `/chatbox/input` 자체에는 역할·시각·ID가 없다. T1에서 양쪽을 같은 주소로 섞는 경로는 기본으로 사용하지 않는다. `LOGGER_FEATURE`의 `[RECEIVED] original (translations)` 로그는 출력 처리 뒤 기록되며 괄호 경계가 모호할 수 있고 10 MiB 경계에서 과거 내용이 사라질 수 있어 주 WebSocket의 손실 없는 대체로 쓰지 않는다.
- **진입 조건:** 수집 중단/재연결의 replay가 없으므로 공백을 보존한다. native 전체 텍스트는 주 품질 후보지만 타임스탬프 부재·post-dispatch 단계는 별도 시간 검수 대상이다. 세 모델 프로필에서 speaker 경로와 동일한 수집 규칙을 각각 확인한다.

근거: [speaker 방향](https://github.com/misyaguziya/VRCT/blob/7ad46876e60d7b6e053489090797e2228f320da5/src-python/model.py#L817-L875), [SENT/RECEIVED 및 OCR 구분](https://github.com/misyaguziya/VRCT/blob/7ad46876e60d7b6e053489090797e2228f320da5/src-python/models/message_pipeline.py#L79-L153), [출력 순서·payload·로그](https://github.com/misyaguziya/VRCT/blob/7ad46876e60d7b6e053489090797e2228f320da5/src-python/controller.py#L1128-L1230), [WebSocket/auth](https://github.com/misyaguziya/VRCT/blob/7ad46876e60d7b6e053489090797e2228f320da5/src-python/models/websocket/websocket_server.py#L20-L105), [설치·기존 실행 근거](profiles/vrct-vrcs.md).

#### VRCS — VRCS1–VRCS2

- **버전 근거:** 기존 실행의 설치 관측은 0.2.8, 검토 commit은 `b9cd2189f12afbefbaae3e70a2c361f7303fdb54`다. 최초 설치 조사 JSON의 0.2.2를 새 실행 버전으로 재사용하지 않는다.
- **입력·언어:** `audio.output.mode`의 system loopback 또는 VRChat process 경로가 `source:"speaker"`를 만든다. `translation.speaker_targets`와 `microphone_targets`는 별도다. 반면 **`asr.language`는 공유**라서 두 경로에 고정 JA/KO 또는 EN/ZH를 각각 지정할 수 없다. T1은 기존 엔진의 `auto`를 계획하고 두 언어의 실제 동작을 확인한다. Qwen의 감지 언어 추출과 Gemini의 auto/언어 필드 누락을 구별하며 기대 언어를 실제 감지값으로 채워 넣지 않는다.
- **주 수집:** External API의 **WebSocket** `/v1/events`를 사용한다. SSE가 아니다. 기본 설정은 `enabled=false`, `127.0.0.1:8767`, `require_token=false`다. 향후 실행에서는 loopback 범위를 유지하고 지원되는 인증 설정·기존 token을 명시해 동결한다. 연결 후 허용하는 클라이언트 명령은 구독이다.
- **필드·단계:** `api_version/event_id/type/timestamp/message_id/source/payload`; peer는 `source:"speaker"`, self는 `microphone`이다. `translation.completed`는 full translation과 subtitle/message 연결을 제공하고 OSC 처리 큐에 넣기 전에 발행된다. event UUID는 revision 번호가 아니다. `translation.partial/live_updated`와 ASR interim/final도 원시 상태로 남기되 완료 이벤트와 혼동하지 않는다. 한 번역이 여러 subtitle에 연결되는 `source_group`도 보존한다.
- **완전성:** broadcast capacity 256의 지연/손실과 연결 종료를 감시한다. replay가 없으므로 재연결만으로 누락을 복원했다고 하지 않는다. DB는 subtitle/target 단위 upsert라서 전체 revision archive가 아니다.
- **대안:** 기본 DB는 desktop config root 기준 `data/vrcs.db`이며 read-only SQLite 또는 정식 GET history로 최종 상태를 대조할 수 있다. DB `created_at`은 외부 완료 이벤트와 생성 시점이 다르다. live DB/WAL 읽기와 앱 부하를 먼저 확인하고, 동적 core port/token을 임의로 추출하거나 DB 조회로 사라진 중간 이벤트의 시간을 복원하지 않는다.
- **OSC 판정:** 자동 OSC는 `source=="microphone"`만 처리한다. `chatbox.sent`의 `sent_at`은 grace/전송 간격 뒤 실제 send 단계이며 144자 제한·truncation도 있다. 이를 speaker 번역문이나 주 번역 완료 시각으로 대체하지 않는다.
- **진입 조건:** 두 프로필의 speaker 입력과 auto-ASR 기반 T1, 번역 이벤트의 발생 시계·전달 완전성을 각각 확인한다. 실제 provider가 잘못 인식/번역한 것과 collector가 언어 필드를 얻지 못한 것을 구분한다.

근거: [입력 경로·공유 ASR](https://github.com/Dreaminko/VRCS/blob/b9cd2189f12afbefbaae3e70a2c361f7303fdb54/core/src/server/capture.rs#L297-L365), [External API](https://github.com/Dreaminko/VRCS/blob/b9cd2189f12afbefbaae3e70a2c361f7303fdb54/core/src/external_api.rs#L84-L117), [구독·손실](https://github.com/Dreaminko/VRCS/blob/b9cd2189f12afbefbaae3e70a2c361f7303fdb54/core/src/external_api.rs#L271-L365), [기본 설정](https://github.com/Dreaminko/VRCS/blob/b9cd2189f12afbefbaae3e70a2c361f7303fdb54/core/src/config/runtime.rs#L20-L30), [이벤트 schema](https://github.com/Dreaminko/VRCS/blob/b9cd2189f12afbefbaae3e70a2c361f7303fdb54/core/src/domain_events.rs#L1-L178), [번역 완료와 OSC 순서](https://github.com/Dreaminko/VRCS/blob/b9cd2189f12afbefbaae3e70a2c361f7303fdb54/core/src/subtitle_output.rs#L264-L290), [speaker OSC 제외](https://github.com/Dreaminko/VRCS/blob/b9cd2189f12afbefbaae3e70a2c361f7303fdb54/core/src/osc/mod.rs#L226-L240), [기존 실행 근거](profiles/vrct-vrcs.md).

#### VRCLT — VRCLT1–VRCLT2

- **버전 근거:** 1.0.1, commit `d97574fd451f1e5af8d0c68bd13c488fab54eaae`. 기존 실행 파일 두 개가 공개 릴리스 SHA-256과 일치한 기록이 있다.
- **사용자 결정:** VRCLT1·VRCLT2 모두 **self-only**, T1은 **양방향 별도 self 세션**으로 측정한다(§4.7). 더 이상 inbound/process capture·peer 자막 활성화를 VRCLT의 준비 조건으로 요구하지 않는다.
- **입력·언어:** `outbound.enabled`, `outbound.mic_device`, `outbound.source_language/target_language`, 번역 활성 상태를 동결한다. 일반은 영→중·일→한, T1 B pass만 중→영·한→일이다. inbound는 OFF로 유지한다. 세션 하나의 목표 언어는 하나이며 같은 pass 안에서 바꾸지 않는다.
- **주 수집:** self의 기존 `/chatbox/input`을 원시 순서·수신 단조 시각과 함께 저장하고 `%LOCALAPPDATA%/vrclt/logs/vrclt.log`의 `FINAL [lang] source -> translation`을 대조한다. `OutboundPipeline._on_partial`도 OSC로 보내므로 **self가 final-only라는 설명은 틀리다**. final-only 제약은 INFO 로그에만 해당한다.
- **출력 조건:** `outbound.chatbox`와 실제 `osc` 설정을 동결한다. 원문 표시, rolling tail, `stream_sentences`, 중복 억제, 길이 제한, throttle/chunk 대기는 실제 수집 텍스트·시각에 영향을 준다. `FINAL` 로그의 긴 번역문을 이전 OSC 시점에 이미 도착한 내용으로 채우지 않는다. 마지막 OSC 패킷 하나를 전체 번역으로 쓰지 않는다.
- **품질·시간:** 기본 품질 후보는 실제 OSC 이력에서 재구성한 번역문이며 로그는 누락·truncation·경계 검수용이다. OSC 이력으로 온전한 native 번역문을 확보하지 못하면 full final-log 품질을 별도 관측 조건으로 명시하고 주 결과와 몰래 바꾸지 않는다. 시간은 self chatbox 출력 경로이며 큐 전 native 이벤트 시간과 같은 단계라고 부르지 않는다. source timestamp/발화 ID가 없다는 사실만으로 수집 불가를 선언하지 않되 관측 범위를 벗어난 정밀도도 주장하지 않는다.
- **로그 제약:** full final segment만 기록하며 한 provider turn이 여러 segment로 나뉠 수 있다. `lang`은 원문 감지값/auto이지 target이나 역할 ID가 아니다. `->`·여러 줄·5 MiB/backup 2개 회전을 검수한다. Qwen DEBUG 첫 30개·500자 preview를 전체 출력 archive로 쓰지 않는다.
- **진입 조건:** 두 언어쌍·두 T1 pass의 self 입력과 고정 방향, OSC partial/final 이력, 긴 출력의 보존, 로그 대조·시간 단계 차이를 확인한다. 기존 self 하네스를 재사용할 수 있는 부분과 새 의미 재구성이 필요한 부분을 구분한다. peer 미관측을 해결하려고 새 내부 API나 메모리 후킹을 만들지 않는다.

근거: [self 설정](https://github.com/VRCLT/VRCLT/blob/d97574fd451f1e5af8d0c68bd13c488fab54eaae/config.example.yaml), [self partial/final과 rolling 출력](https://github.com/VRCLT/VRCLT/blob/d97574fd451f1e5af8d0c68bd13c488fab54eaae/vrclt/pipeline.py#L515-L590), [OSC 분할·최소 1.5초 간격·대기 결과 교체](https://github.com/VRCLT/VRCLT/blob/d97574fd451f1e5af8d0c68bd13c488fab54eaae/vrclt/out/osc_chatbox.py), [파일 로그](https://github.com/VRCLT/VRCLT/blob/d97574fd451f1e5af8d0c68bd13c488fab54eaae/vrclt/logging_setup.py#L14-L24), [설치/기존 self 실행·Beijing 경로](profiles/vrclt.md).

#### Kikitan — KIKI1–KIKI2

- **버전 근거:** 2.0.2이며 설치 product version에 commit `175fb87f95d7b6592965fe3f099883ee2f830316`가 포함된 기록과 해당 소스를 확인했다.
- **승인된 입력·실행 조건:** KIKI1·KIKI2는 §4.7의 실제 microphone/self 입력을 설치 앱의 `--no-ui` 모드로 실행한다. `desktop_translation=false`, `send_user_data=false`, `send_to_chatbox=false`와 정확한 가상 케이블 입력 이름을 확인한다. 일반은 영→중·일→한, T1 A/B는 각각 정방향/역방향 별도 self 세션이다. 기존 GUI-only·UDP 7272 주 수집 의무는 대체되었으며 해당 결함이 수정됐다는 뜻이 아니다.
- **대체된 desktop 의무:** 이 버전의 `Loopback.FindVRChat()`는 같은 Windows 세션의 `VRChat.exe` process tree 오디오만 선택한다. 오너는 VRChat 없이 수행하기 위해 self 예외를 승인했다. 실제 desktop/동시 self+peer 검증은 이번 비교 의무에서 대체되었으며 완료된 것이 아니다. VRChat 실행, 가짜 `VRChat.exe`, 앱 개조나 self→peer 이름 변경은 하지 않는다.
- **주 수집:** `ws://127.0.0.1:18378/`의 `recognition` 메시지다. 외부 JSON의 `data` 문자열을 다시 JSON으로 해석하여 `transcription`, `translation`, boolean `final`을 보존한다. 정상 GUI의 Photino bridge에 연결하거나 provider 응답을 직접 수집하는 경로가 아니다. 읽기 전용 수집기는 제어·설정 변경·구독 요청을 보내지 않고, 연결 후 제어기가 capture를 시작한다.
- **필드·단계:** 일반 마이크 출력 `Custom(SendRecognitionData, false)`의 즉시 콜백이다. 원문·번역·final은 같은 native 메시지에 있으나 앱 timestamp·message/revision/utterance ID는 없다. 수신 순번을 native ID로 만들지 않는다. WebSocket은 UTF-8/JSON을 사용하며 손실된 UDP 바이트를 복원하는 방식이 아니다. 연결 성공은 내부 입력·provider 연속성이나 누락 없는 갱신 이력의 보증이 아니다.
- **언어·모델:** self는 `source_language→target_language`다. 일반과 T1 A는 en→zh/ja→ko, T1 B는 zh→en/ko→ja를 고정한다. KIKI1 Bing+Google 및 KIKI2 Gemini 구성은 유지하며 실제 선택·감지 언어를 별도로 보존한다. desktop의 역방향 규칙을 self에 적용하지 않는다.
- **프로필별 한계:** KIKI1은 일반 ASR hypothesis의 번역이 비어 있을 수 있다. KIKI2는 누적 input/output transcription을 내보내며 기존 소스의 gap-reset/final 처리 한계가 있다. `final`을 모든 엔진에 공통인 발화 종료·의미 완료 표지로 쓰지 않고 원시 출력과 세션 경계를 보존한다.
- **수집·제어 안전:** 같은 고정 포트와 공유 설정을 사용하는 새 소유 인스턴스만 제어한다. 설정·상태 메시지는 키를 포함할 수 있으므로 원시 번역 기록에 섞지 않는다. 제어기는 정지 상태에서 설정을 적용·재확인하고, 독립 episode/pass에는 실제 새 세션을 만든다. 종료 후 소유 프로세스 퇴장을 확인하고 동시 사용자 변경을 덮어쓰지 않는 범위에서 설정을 복원한다. 시작 전 업데이트 검사·장치 열거·discovery 등은 별도 부수 효과로 남는다.
- **근거와 남은 범위:** KIKI2의 기존 40초 EN→ZH 소규모 실행은 실제 중국어·누적 갱신과 전체 +15초 관찰을 확보했다. KIKI1의 과거 headless 마이크 충돌은 수정된 것으로 처리하지 않으며 이 성공을 KIKI1·다른 언어·T1에 복사하지 않는다. user-data Unicode 결함과 원래 무효 시도는 역사적 근거로 보존한다. T1 두 pass의 별도 원점·고정 방향·공통 관찰 종료와 R6의 최종 텍스트·시간 판정은 유지한다.

근거: [마이크 출력·JSON 필드](https://github.com/YusufOzmen01/kikitan-translator/blob/175fb87f95d7b6592965fe3f099883ee2f830316/KikitanTranslator.Photino/Manager.cs), [headless WebSocket](https://github.com/YusufOzmen01/kikitan-translator/blob/175fb87f95d7b6592965fe3f099883ee2f830316/KikitanTranslator.Photino/Connector.cs), [GUI/headless 구분](https://github.com/YusufOzmen01/kikitan-translator/blob/175fb87f95d7b6592965fe3f099883ee2f830316/KikitanTranslator.Photino/Program.cs), [역방향·지연 큐](https://github.com/YusufOzmen01/kikitan-translator/blob/175fb87f95d7b6592965fe3f099883ee2f830316/KikitanTranslator.Base/Kikitan.cs), [Gemini 누적 출력](https://github.com/YusufOzmen01/kikitan-translator/blob/175fb87f95d7b6592965fe3f099883ee2f830316/KikitanTranslator.Base/Recognizers/Gemini.cs), [기존 UDP 결함](../profiles/evidence/r1/kikitan-unicode-blocker.json), [설치 기록](../profiles/evidence/installed-apps.json).

#### VRCLS — VRCLS1

- **버전 근거:** 설치 `0.7.0-20260913 / 0.7.0.1015`의 `VRCLS.dll` SHA-256 `98e0046265557ac62154624886203df5a370be9b29af2c8b66e67fa281573a41`를 이번에 PEReader로 정적 조사했다. 최신 C# 참조 소스와 설치 빌드가 같다고 가정하지 않고 실제 DLL의 관련 IL을 확인했다. 대상 assembly를 로드/실행하거나 앱·오디오·provider를 시작하지 않았다.
- **입력:** microphone과 desktop loopback을 별도 경로로 구성한다. 기존 named-device 복구 기록은 정확한 Cable 이름과 실제 hardware capture 선택의 근거이지 desktop 번역 실측 성공의 근거는 아니다. 기본 장치 fallback을 허용하지 않고 역할별 source/target 설정을 확인한다.
- **주 수집:** `%APPDATA%\VRCLS\logs\vrcls-*.log`의 `[Desktop]`와 `[Mic]` 결과 레코드를 읽는다. 설치 DLL의 `GetLogDirectoryPath`(`0x06000008`)와 `OnStartup`(`0x06000005`)에서 경로와 `yyyy-MM-dd HH:mm:ss.fff` 형식의 파일 logger를 확인했다.
- **내용·단계:** `HandleRecognitionResultAsync`의 상태 기계(`MoveNext`, `0x0600095D`)는 정리한 `original -> joinedTranslation`과 역할을 `AddLog`(`0x0600022A`)에 전달한다. 같은 처리에서 UI 갱신을 예약하지만 이것은 rendering 완료가 아니다. `[Desktop]`는 이후 chatbox OSC 분기에서 명시적으로 제외된다.
- **T1:** 같은 파일의 역할 필드로 self/peer를 구분한다. `ResolveTranslationLanguages`는 result의 언어 또는 source별 config resolver를 사용한다. 로그에는 원래 발화/revision ID가 보장되지 않으며 `->`·여러 줄·여러 목표 언어의 파싱을 검수한다. 번역 목표 하나를 동결하고 원문/번역 경계를 추측으로 복구하지 않는다.
- **대안과 정밀도:** GUI 로그 내보내기는 `HH:mm:ss`만 남겨 파일 로그의 ms 표기를 잃으므로 주 시간 경로로 쓰지 않는다. ms 문자열이 있다는 사실 자체가 ms 정확도를 뜻하지 않는다. 파일 기록 시계와 flush/읽기 지연을 분리한다.
- **보안·진입 조건:** 같은 로그에는 전체 config를 압축한 `CONFIG_SNAPSHOT_V1` 등이 들어갈 수 있다. 원시 로그를 공개하지 않고 번역 출력·역할·시간·근거 offset만 허용 목록으로 추출한다. 설치 바이너리에서 경로는 확인했지만 실제 peer 번역·동시 T1·로그 완전성은 아직 실행하지 않았다.

근거: [기존 설치 바이너리·정적 경계](../profiles/evidence/issue8/vrcls-installed-routing-findings.json), [원래 1015 named-route 복구](../profiles/evidence/issue8/vrcls-exact-name-routing-repair.json), [비교용 공개 C# 소스](https://github.com/VoiceLinkVR/VRCLS/blob/5b489c4504a9a9b14460a609a9799df8e6eda1c0/03.VRCLS.UI/ViewModels/MainViewModel.cs#L3634-L3695). 이번 설치 DLL 검산은 위 hash와 method token에 한정되며 공개 소스 전체와의 동일성 인증은 아니다.

### 6.5 R1 조기 가능성 확인과 R6 최종 진입 판정

**R1 — 수집 구현과 조기 확인**

1. **입력/기능 차단 조건부터:** PuriPuly의 별도 peer ASR, VRCS의 공유 ASR 언어와 auto 기반 T1, VRCT의 역방향 설정을 먼저 확인한다. VRCLT·Kikitan은 §4.7의 self-only·T1 분리 실행을 적용하며 Kikitan에는 VRChat을 요구하지 않는다. 권한·입력 경로·설정 문제를 R6까지 숨기지 않으며, 출력 부재가 collector 문제인지 실제 입력/모델 미설정인지 구분한다.
2. **대표 실제 경로의 최소 확인:** 앱 계열별 주 수집기와 입력·역할/pass·시계 계약을 구현하고, 작은 허용 음원으로 의도한 입력에서 나온 번역문·역할·수신 시각을 실제로 수집한다. 별도 경로/설정 차이가 있는 경우에만 필요한 확인을 추가한다. 연결 성공이나 패킷 한 건만으로 통과시키지 않는다. 수집 확인을 위해 본 코퍼스나 TTS 전체를 먼저 제작하지 않는다.
3. **조기 확인의 한계:** 실제 입력 경계와 공통 재생 시계의 근거를 남기며 재생 명령 시각을 음성 시작 시각으로 대신하지 않는다. 14개 프로필 모두의 확인 범위·차단 사유·남은 미검증 항목을 기록하되, 대표 모델의 통과를 다른 프로필에 복사하거나 R1 종료를 전 프로필 최종 준입 완료라고 부르지 않는다. 이 근거로 입력 제작의 가능성을 먼저 판단하며, R2/R3는 최종 14개 프로필 검증을 기다리지는 않는다. 알려진 입력·권한 문제를 무시한 제작비 집행은 허용하지 않는다.

**R6 — 보존된 증거를 활용한 통합 검증과 최종 판정**

4. **누락된 수집 조건을 통합 실행에서 확인:** 두 언어쌍·필요한 역방향과 T1 역할/pass, 짧은 말·긴 출력·수정·같은 문장 재등장·무음·15초 후속 관측을 다룬다. 채널 혼입, truncation, 누적 중복, final 오인, gap·로그 회전·잔여 출력과 중단/재개를 구분한다. 이미 해당 버전·입력·설정에서 확인한 것은 재사용하고, 미확인 또는 변경 영향이 있는 부분만 실행한다.
5. **품질과 시간의 별도 진입:** 온전한 번역문 확보와 단계/시계가 비교 가능한 대기시간 확보를 각 프로필의 실제 근거로 판정한다. native timestamp가 없으면 수신 단조 시각과 관측 구간의 사용 가능성을 확인하며 숨은 시각 복원을 필수 개발로 만들지 않는다. VRCLT OSC/log, VRCS event/DB 등 서로 다른 단계를 섞거나 오래된 latency로 빈칸을 메우지 않는다.
6. **최종 준입 보고:** 14개 프로필 각각에 `빌드·모델·실제 경로/조건·역할별 언어/장치 | native 경로 | 텍스트/수정 이력 완전성 | 종점 단계·시계 근거 | 유형/pass 결과 | 품질 진입 | 시간 진입 | 비용·제약`을 남긴다. 실제 관측이 없는 프로필/경로는 미검증·차단으로 남긴다. 실제 VRChat 경로의 전송 지연·압축 조건과 일반 local replay 조건도 구분한다.

R6는 **어떤 프로필의 어떤 지표를 비교할 수 있는지 최종 확정하는 단계**다. 대표 경로의 조기 통과를 전 프로필 통과로 확대하지 않으며, 쉬운 앱만 남기거나 비중을 재분배하지 않는다. 필수 미확인 항목·권한 문제를 성공으로 기록하지 않고 필요한 범위 변경은 별도로 결정한다. 기존 개발 사례를 사용하며 모든 프로필×언어×유형을 본 실험처럼 전수 예행연습하는 별도 캠페인을 추가하지 않는다.

### 6.6 실행 가능성 평가와 과도한 계측 방지

**판정: 번역문 수집의 구현 경로는 있지만, 전 프로필의 품질·p50·p90을 무리 없이 같은 조건으로 채울 준비가 끝난 것은 아니다.** 앱별 어댑터 자체는 필요한 수집 작업이다. 반면 내부 단계·숨은 timestamp·원래 발화 ID까지 완벽하게 맞추려는 복원 작업은 첫 실험의 필수 조건으로 늘리지 않는다.

- 먼저 **주 수집 경로 하나 + 원시 텍스트/역할/수신 시각 + 작은 실제 입력**으로 동작을 확인한다. 보조 로그/DB는 필요한 누락·내용 대조에만 사용하고 앱마다 여러 우회 경로를 동시에 개발하지 않는다.
- 에피소드 단위 품질은 원래 발화 ID나 패킷↔발화 1:1 대응 없이 평가할 수 있다. 입력 역할·내용·수정 관계의 실제 불명확성과 단순 ID 부재를 구분한다.
- 기다림은 이미 0/2/5/10/15초 관측 구간이다. ms 단위 내부 시각 복원을 새 목표로 삼지 않는다. 수집 지연·출력 단계 차이로 구간 판정이 달라질 수 있으면 범위/미확정으로 표시하며 차이를 없는 것으로 만들지도 않는다.
- 실제 입력 경로의 부재, 번역문 잘림, 중간 출력 손실은 단순 계측 정밀도 문제가 아니다. 가짜 peer 입력이나 잘린 결과 복원으로 넘기지 않는다. Kikitan의 desktop은 여전히 VRChat 전용이며, 승인된 self 예외가 desktop 지원을 입증하지 않는다.
- VRCLT·Kikitan의 self-only 및 T1 분리 실행은 승인된 실용적 범위 변경이다. 같은 음원·목표 의미·가중치는 유지하되 동시 peer 사용성을 측정했다고 주장하지 않는 선에서 단순화한다.



## 7. 품질: 최소 커스텀 GEMBA-ESA

### 7.1 그대로 유지할 방법론

[공식 GEMBA-ESA 구현](https://github.com/MicrosoftTranslator/GEMBA/blob/main/gemba/gemba_esa.py)의 두 단계를 사용한다. 실행에 사용할 upstream commit과 실제 프롬프트 해시를 동결한다.

1. **오류 구간 판정:** 원문과 번역에서 accuracy, fluency, style, terminology, non-translation 등의 오류를 찾고 **minor/major**로 분류한다.
2. **직접 품질 채점:** 동일 원문·번역과 1단계 오류 근거를 별도 새 호출에 넣어 **0–100 연속 점수**를 받는다.

공식 기준점은 `0=의미 보존 없음`, `33=일부 의미 보존`, `66=대부분의 의미 보존과 소수 문법 오류`, `100=완전한 의미·문법`이다. 네 등급 중 하나만 고르는 방식이 아니다. 오류 taxonomy·심각도 정의·기준점·기존 few-shot 예시는 기본 유지한다.

`100 − major×5 − minor×1` 같은 감점 산식, 임의 점수 상한, 번역 양호 비율로 바꾸지 않는다. MQM 감점 합계와 GEMBA-ESA 직접 점수를 섞지 않는다.

### 7.2 허용하는 최소 커스텀

| 변경 | 필요한 이유 | 경계 |
|---|---|---|
| 에피소드·대화 문맥 입력 | 구어체·지시 대상·질문과 답 이해 | 실제 원문을 문어체로 고쳐 쓰거나 미래 문맥을 시간 판정에 넣지 않음 |
| 역할·목표 언어·채점/문맥 범위 표시 | T1 양방향과 ASCEND 혼용 처리 | 한 호출의 목표 언어는 하나. 문맥만인 다른 역할을 누락으로 감점하지 않음 |
| 네이티브 출력 이력의 근거 있는 재구성 | 누적·수정·출력 분할 때문에 생긴 가짜 오류 제거 | 원문/출력 1:1 정렬이나 의미 요약으로 대체하지 않음 |
| 구조화된 오류 인용·결과 형식 | 저장·검산·감사·재개 | 정확한 인용과 occurrence를 검증. 모델이 잘못 낸 좌표·인용을 조용히 고치지 않음 |
| 블라인딩·비신뢰 데이터 경계 | 제품 편향·프롬프트 주입 방지 | 앱·모델·가격·속도·실험 결과 메타데이터는 숨김 |

구어체·원문의 자연스러운 반복·정확한 의역은 그 자체로 오류가 아니다. 부정·수치·행위자·의도 반전은 기존 accuracy/major 판단으로 다루며 별도의 취향 점수를 추가하지 않는다.

### 7.3 평가 단위와 실행

- P1–P4: 에피소드 전체 원문·문맥과 관측 종료까지의 재구성된 최종 의미를 비교한다.
- T1: 역할 A/B를 **목표 언어별로 각각** 평가한다. 기본은 같은 실행의 peer/self, VRCLT는 같은 에피소드의 두 self pass다. 양쪽 대화 문맥은 제공하되 채점 범위는 분리하며 에피소드 품질은 두 점수의 산술평균이다.
- 오류 판정과 점수 판정은 독립 대화로 실행한다. 2단계는 1단계 결과를 입력받지만 이전 평가의 대화 상태를 이어받지 않는다.
- 기존 **GPT 6 Astra / Sign in with ChatGPT** judge와 블라인드 큐·캐시·재개 기반을 유지한다. GEMBA-ESA는 방법론 선택이지 새 평가 모델·유료 API 도입 지시가 아니다.
- 입력/출력 관계·native 종점 단계·프롬프트·단계·judge 실제 식별이 바뀌면 캐시를 분리한다. 오류 판정 실패를 무오류 결과로 간주하거나 점수 단계만으로 성공 처리하지 않는다.
- 본 앱 측정과 TTS 제작·judge 실행을 동시에 돌려 성능에 간섭시키지 않는다.
- 실제 번역 대상이 있고 완전한 관측이 입증된 전체 무출력은 ‘의미 보존 없음’인 0과 무출력 상태다. 프로토콜로 확정한 값과 실제 judge 응답은 구별해 저장한다. 관측 불가·참조 불명확·judge 실패는 0이 아니라 N/A다.
- 부분 누락·잘못된 목표 언어 등 비어 있지 않은 결과는 오류 근거와 공식 척도로 평가한다. 모든 실패 유형을 일괄 0으로 덮지 않는다.

공개 명칭은 **‘번역 품질 — GEMBA-ESA 기반 자동 평가, 0–100’**이다. 87점은 정확한 단어 87%나 인간 이해 성공률 87%가 아니다. 원 논문의 검증이 현재 모델·대화 입력·일한 방향에 그대로 성립한다고 주장하지 않는다.

### 7.4 본 측정 전 변별력 확인

본 평가와 분리된 작은 원문 집합에 정확한 의역, minor 오류, 중요 누락, 부정·숫자·행위자 반전, 무출력, 잘못된 언어·무관한 내용을 준비한다. 오류 인용·심각도와 점수 순서가 명백한 반례를 구분하는지 확인한다.

동일 의미의 분할/병합/누적 표현, 이전 페이지, 다른 화자 문맥, 중간 오역 후 정정, 하네스 조기 중단도 점검한다. 사전 선택한 소량의 같은 입력을 독립 재채점해 변동성을 기록한다. 앱 결과에 맞춰 프롬프트를 조정하거나 숫자를 더 벌리기 위해 척도를 왜곡하지 않는다.

R4에서는 계산·재구성 반례와 선택한 judge의 두 단계 실제 호출을 최소 확인한다. **R6가 통합 경로와 이 절의 남은 변별력·사전 선택 반복 확인을 맡는다.** 같은 입력·프롬프트·실제 모델에서 이미 얻은 유효한 판정은 재사용하며, 앞 이슈의 종료나 R6 진입만을 이유로 다시 채점하지 않는다.

작은 차이가 judge 변동성보다 작으면 확정 우열로 발표하지 않는다. 이 검산은 대규모 인간 타당화 연구가 아니며, 하지 않은 사람 검수를 했다고 표시하지 않는다. 별도 tone30·Korean100·MetricX를 주 점수나 필수 평가로 자동 복원하지 않는다.

## 8. 번역 출력의 의미 대기시간: p50과 p90

### 8.1 체크포인트

- 결과를 보기 전에 질문·요청·조건·짧은 설명의 핵심 의미와 근거 발화 종료 시각을 정한다. 앱의 문장 분할·출력 패킷 수를 기준으로 만들지 않는다.
- 기본 관측점은 **앱에 들어간 근거 발화 종료 시점, 이후 +2/+5/+10/+15초**다. 원문 인용·필요 의미·네이티브 출력 근거를 보존한다. 앱 앞단의 네트워크·플레이어 지연을 포함하려면 모든 비교 대상의 입력 경계부터 별도로 통일해야 한다.
- 각 시점에는 그때까지 실제로 입력된 원문과 앱이 내보낸 번역 이력만 사용한다. 미래 답변이나 늦은 수정을 과거에 이미 출력된 것처럼 판정하지 않는다.
- 단어가 일부 나왔다는 이유가 아니라 필요한 의미가 올바르게 **번역 출력에 포함됐는지** 판정한다. 품질 점수나 마지막 패킷 시각으로 이 판정을 대체하지 않는다. 화면을 봤을 때의 기다림으로 부르지 않는다.
- 상태는 `말끝까지 이미 출력`, `2초 이내`, `2–5초`, `5–10초`, `10–15초`, `15초 내 미충족`, `판정 불가`다. 첫 상태는 말끝 이후 추가 대기가 없다는 뜻이지 발화 시작부터 지연 0이라는 뜻이 아니다.
- 한번 올바르게 출력된 뒤 잘못 수정되면 첫 출력과 이후 정정을 둘 다 기록한다. 단순 clear나 출력 항목 삭제를 의미 번복으로 취급하지 않는다.

### 8.2 분위수와 불확실성

품질과 같은 언어쌍→유형→에피소드 가중치를 사용한다. 에피소드 안 체크포인트가 많아도 그 에피소드의 총 비중은 같다. T1은 역할 A/B에 각각 절반을 배정한 뒤 역할 안 체크포인트에 균등 분배한다. VRCLT·Kikitan도 동일하되 각 self pass의 실제 입력 시각을 사용하며 pass 사이 준비 시간을 대기에 더하지 않는다.

가중 누적 분포 `F(t)`에서 `p50 = 처음 F(t) >= 0.5`, `p90 = 처음 F(t) >= 0.9`인 관측 시각/구간을 구한다. **언어별 p90 또는 에피소드별 p90을 평균하지 않는다.**

- 고정 관측점으로만 판정한 값은 구간으로 공개한다. 구간의 중점이나 소수점 초를 정확한 완료 시각처럼 만들지 않는다.
- 실제 제품 무출력·지속 오역은 분모에서 빼지 않고 미충족으로 남긴다. 필요한 비율이 기한까지 충족되지 않으면 해당 분위수는 `15초 내 미충족`이다. 가짜 15초 값이나 성공 사례만의 분위수로 바꾸지 않는다.
- p50이 있어도 p90은 미충족일 수 있다. 두 필드·표 열을 분리한다.
- 관측 불가·미채점은 미충족과 다르다. 필수 가중 범위가 불명확하면 완전한 통합 분위수는 N/A/불완전이며 부분 결과를 명시한다.
- 15초 한도와 관측 해상도는 설계상의 한계다. 인간이 15초까지 기다릴 수 있다는 실험 결과가 아니다. pilot에서 문제가 드러나면 본 결과를 보기 전에 프로토콜 revision을 바꿔 전체에 동일 적용한다.

## 9. 통합 점수와 누락 처리

언어쌍을 `l`, 유형을 `c`, 그 칸의 에피소드를 `e`라 한다.

- `L_l = 0.5`
- `C_c = {P1: 0.10, P2: 0.30, P3: 0.20, T1: 0.30, P4: 0.10}`
- 일반 에피소드: `q_e = q_primary` — 기본은 peer, 승인된 VRCLT·Kikitan은 self.
- T1 에피소드: `q_e = (q_A + q_B) / 2` — 기본은 동시 peer/self, VRCLT·Kikitan은 양방향 self 분리 실행.
- 통합 품질: `Q = Σ_l Σ_c L_l × C_c × mean_e(q_e)`

T1의 한 언어쌍·한 역할이 전체에 기여하는 비중은 `0.5 × 0.30 × 0.5 = 0.075`다. 역할별 문장 길이·말 수가 달라도 이 비중을 바꾸지 않는다.

VRCLT·Kikitan의 두 self pass가 모두 유효하면 같은 자료·가중치의 **self 대체 통합 값**을 낼 수 있다. 이것을 기본 peer/동시 T1 통합 값과 동일 조건이라고 표시하지 않으며 공개표의 조건 열·그래프 구분을 유지한다.

1. 정상 관측된 무출력은 품질 0·시간 미충족으로 포함한다.
2. 미지원·하네스 invalid·참조/출력 귀속 불명확·미채점은 원인과 예정 가중치를 유지한다. 다른 사례에 비중을 나누어 주지 않는다.
3. 필수 평가 범위가 빠지면 해당 통합 지표는 N/A/불완전이다. 유효한 방향·유형·역할 상세 값은 계속 공개하되 완전한 통합 순위와 섞지 않는다.
4. 품질 완료 여부·시간 완료 여부·비용 정산 여부는 별개다. 비용 대기 때문에 이미 완료된 품질·시간을 숨기지 않는다.
5. 품질·시간·비용을 더하거나 나눠 단일 종합 점수·가성비 순위를 만들지 않는다.

## 10. 실행 경계·관측 종료·실패

- 에피소드 마지막 실제 입력 음성 종료 후 **15초까지** 네이티브 번역 출력을 관측한다. 기본 T1은 두 입력 경로의 마지막 음성 중 늦은 시각을 기준으로 한다. VRCLT·Kikitan T1의 각 self pass도 원래 공통 시간축의 마지막 음성 시각 +15초까지 관측한다.
- 독립된 다음 에피소드는 이 한도를 보장한 뒤 시작한다. 기한 뒤 출력은 별도 늦은 출력으로 보존하며 영구 누락이라고 단정하지 않는다.
- 앱이 실제 입력을 받고 번역할 기회가 있었는지 확인한다. 수집 프로세스가 살아 있었다는 사실만으로 앱 관측이 완전했다고 하지 않는다.
- 독립 에피소드 시작 상태는 제품의 새 대화/reset 또는 검증된 재시작 절차로 맞춘다. 화면 clear가 서버 문맥 reset이라는 가정은 하지 않는다.
- startup 확인 음성·준비용 문맥·잔여 출력을 본 측정에 섞지 않는다. T1 턴마다 reset하지 않는다.
- 하네스/장치가 기한 전에 입력·앱을 끊으면 영향받은 범위는 invalid/N/A다. 실제 제품 연결 실패·종료와 구분한다.
- 제품 자체 실패로 입력이 모두 재생·관측됐는데 번역이 없으면 실제 제품 결과로 남긴다. 아직 재생하지 않은 뒤 에피소드까지 임의 0점으로 채우지 않는다.
- 복구·재시도는 새 attempt다. 원래 실패를 성공 결과로 덮어쓰지 않는다. 운영 invalid의 대체 실행도 원인·원본 attempt를 연결한다.
- C1은 이전 출력이 정리된 상태에서 실행한다. 준비가 확인되지 않으면 잔여 번역인지 새 무입력 생성인지 미확정으로 남긴다.
- 기존 동시 wave 일정을 자동 폐기하거나 단독 순차 방식으로 바꾸지 않는다. 새 peer/T1 라우팅·장치 격리·자원 간섭을 pilot에서 확인해 실행 조건을 동결한다.

## 11. 실제 로그 기반 비용 정산

사용자가 나중에 제공하는 허용된 실험 로그·사용량 export·청구 근거를 [기존 비용 처리 기반](costs.md)에 연결한다. 지금 임의 계정 조회나 예상 요금을 실청구처럼 작성하지 않는다.

### 11.1 실행 때 반드시 남길 것

- protocol/dataset/profile/episode/attempt ID, 역할, 실제 앱·모델·라우트.
- UTC와 단조 시계 연결, 실제 재생 구간, 관측 tail, 실행 완료·실패 상태.
- 제공자 요청 ID, 비밀이 아닌 계정 별칭, ASR 제출 시간 또는 audio tokens.
- 입력·캐시·출력·reasoning 사용량, 청구된 재시도·취소, all-in-one 경로.
- 별도 원장으로 남기는 대본·TTS·judge 제작/평가비.

### 11.2 공개 비용

`입력 1시간 비용 = 귀속된 본 평가 앱 비용 × 3600 / 동결 에피소드 재생 시간의 합(초)`

- 분모는 동일한 동결 입력의 **논리 에피소드 재생 시간축**이다. 자연/삽입 간격을 포함하고 준비·관측 tail은 제외한다. 기본 T1 동시 두 스트림과 VRCLT·Kikitan T1 분리 두 pass 모두 원래 대화 시간축을 한 번만 센다. 실제 물리적 재생/운영 시간은 별도 저장하며, pass가 늘었다고 동일 과제 비용의 분모를 두 배로 늘리지 않는다.
- 분자에는 ASR와 번역/all-in-one의 실제 귀속 비용, 본 실행에서 제품이 발생시킨 청구 재시도·tail 중 요청도 포함한다. 서버 제출 음성량은 비용 근거이며 재생 시간 분모와 같다고 가정하지 않는다.
- 성공 번역만 분모로 세지 않는다. 중도 중단으로 다른 입력 범위를 실행한 부분 비용을 완전 실행 프로필과 같은 순위로 비교하지 않는다.
- 실제 총 청구/귀속액을 우선 보존한다. `사용량 × 당시 요율`은 계산값으로 구분하고 통화·세금·할인·최소 청구 단위·빠진 컴포넌트를 표시한다.
- 이 비용은 고정된 전체 입력의 실제 시간당 비용이다. 품질의 유형 가중치를 요금에 다시 곱한 임의 가격 지수를 만들지 않는다. 유형·역할별 비용은 상세 원장에 남긴다.
- 요청 ID·시간·모델·계정 근거가 맞는 부분만 배정한다. 공유 계정의 거친 시간 bucket이나 잔액을 가장 가까운 앱에 밀어 넣지 않는다. 중복 로그·포함 캐시 토큰을 이중 청구하지 않는다.
- 구독료는 사용 조건과 별도 표시하며 임의 건당 비용으로 바꾸지 않는다. 미상은 0이 아니고, 무료는 실제 적용 근거가 있어야 한다.
- 개발·준비·사전 선택 반복·하네스 재실행·TTS·judge는 분리한다. 본 실행 중 제품 자체의 청구된 재시도는 숨기지 않는다.
- 비용 로그가 오기 전 상태는 `정산 대기`다. 이후 비용 근거 revision을 추가하며 품질·시간 원본은 바꾸지 않는다. 원본 비공개 로그·계정·키는 공개하지 않는다.

### 11.3 Gemini 3.8 Flash TTS 제작비·품질 보고

TTS는 입력 제작비이며 번역 앱의 입력 1시간 비용 축과 분리한다. **14개 프로필에 재생한다고 TTS를 14번 생성·과금하는 계산을 하지 않는다.** 생성 음성 길이와 역할별 무음을 채운 최종 재생 WAV 길이도 구분한다.

#### 공식 요율과 진입 비용

아래는 직접 Google Standard의 날짜별 공식 요율이며 USD·세금 제외다. **2026-10-27 조회한 OpenRouter의 현재 해당 모델 요율도 입력 $0.50/100만·출력 $9/100만 tokens다.** OpenRouter 향후 요율을 아래 표만으로 보장하지 않고 변경 시 다시 확인한다.

| 항목 | 2026-12-31까지 | 2027-01-01부터 |
|---|---:|---:|
| 입력 텍스트 100만 tokens | $0.50 | $1.00 |
| 출력 음성 100만 tokens | $9.00 | $18.00 |
| 출력 음성 1분 환산, 초당 25 tokens | $0.0135 | $0.0270 |

현재 승인 경로는 오너의 기존 OpenRouter 키·credit이다. 계정 잔액을 추정하거나 직접 Google 선결제를 요구하지 않는다. OpenRouter 신규 credit 구매의 최소액·수수료·세금은 API 소모액과 별도이며 자동 충전/구매를 하지 않는다. 승인된 6회 요청은 입력 8,192·출력 16,384 tokens 한도로 회당 $0.151552, 합계 **$0.909312**를 사전 예약한다. 실패·불확실 응답도 요청 슬롯을 소모하며 저렴하게 끝났다고 추가 요청 권한이 생기지 않는다. 이는 현재 공식 한도·요율에 따른 클라이언트 요청 예산이지 실제 청구나 OpenRouter 내부 호출 수의 측정값이 아니다. 생성 응답의 `X-Generation-Id`로 별도 사용량 조회를 남기며 누락된 비용·credit·현금·검수 비용은 미상으로 둔다.

#### 전체 생성과 턴별 생성의 비용 차이

- 같은 총 발화 길이라면 음성 출력 비용은 대체로 비슷할 수 있다. 호출 수만으로 턴별 생성이 더 싸거나 비싸다고 계산하지 않는다. 실제 출력 길이·무음·반복 지시문의 입력 tokens·재생성이 비용을 결정한다.
- 전체 생성의 주 비용 위험은 한 턴의 오류 때문에 **에피소드 전체를 재생성**할 수 있다는 점이다. 대신 호출·접합 작업이 적고, 문맥을 한 요청 안에 전달한다.
- 턴별 생성은 잘못된 턴만 다시 만들기 쉽지만 지시문 반복, 접합부·음색 일관성 검수와 시간표 조립 작업이 늘 수 있다.
- 전체 생성 후 두 역할 버퍼로 나누는 로컬 처리는 **새 TTS 호출이 아니며 음성 사용료를 두 배로 만들지 않는다.** 정렬·청취·편집 시간과 별도 ASR 검산 비용은 제작 원장에 남긴다.
- 짧은 단위로 쪼개는 것 자체를 비용 최적화 목표로 삼지 않는다. 대화 품질과 역할 정확성을 먼저 충족시키고 실제 제작비를 보고한다.

#### 예산 민감도 예시

다음은 실제 대본·청구가 아닌 예시다. 두 언어를 합친 채택 생성 음성 **9분**, 전체 요청의 지시문 등을 포함한 누적 입력 **10,000 tokens**를 가정한다. 9분 전체를 한 API 요청으로 생성한다는 뜻이 아니며, 요청별 입력 한도는 별도로 검사한다.

| 조건 | 현 Standard 요율의 API 사용료 |
|---|---:|
| 한 번에 채택 | **$0.1265** |
| 재생성 등으로 누적 음성·입력이 세 배 | **$0.3795** |

pilot·대본 각색·정렬/ASR 검산·사람 검수·편집·세금·신규 선결제는 포함하지 않았다. 세 배는 민감도 계산이지 통과 보장이나 실행 지시가 아니다. 최종 지출이 위 사용료만큼 작다고 단정하지 않으며 실제 요청 사용량으로 정산한다.

#### 계산·보고 계약

1. **실행 전 견적:** 스크립트별 전체/턴 단위 요청 수, 입력 tokens·예상 음성 길이, pilot·재생성 가정, 요율 적용 기간, 신규 결제액, 정렬·청취·편집 범위를 제시한다. 실제 계정 상태를 확인하지 않은 채 기존 credit을 가정하지 않는다.
2. **원장 구분:** `pilot / production / rejected-regeneration / script-adaptation / alignment-editing / ASR-review / human-review / setup`을 구분한다. 요청별 모델·음색·생성 단위·설정·seed(지원·사용한 경우)·일시·사용량·금액·대본/음원 hash·채택 여부·탈락 이유를 연결한다.
3. **중복 계산 금지:** 선결제 현금 지출, 실제 API 소모액, 남은 credit을 분리한다. 동일 생성물의 두 역할 파일·반복 재생을 별도 생성비나 중복 채택 분량으로 세지 않는다.
4. **채택 가능한 음성 기준 비용:** `pilot API 소모액 / pilot의 중복 없는 채택 음성 분`과 `본 제작 API 소모액 / 최종 채택 음성 분`을 구분한다. 폐기·재생성 비용은 분자에 남긴다. 채택 0분이면 산출 불가이지 $0/분이 아니다.
5. **검수·작업 비용:** 청취 인원·언어 능력·정렬/편집/검수 시간·실제 지급액을 보고한다. 금액을 모르면 미정으로 남기고 임의 시급이나 무료 노동으로 총액을 확정하지 않는다.
6. **제작 방식·품질 보고서:** `스크립트·모델·음색 | 전체/턴 단위·전환 이유 | JA 충실도/발음 | KO 충실도/발음 | 대화 연결감 | 턴 경계·채널 검증 | 최초 채택/재생성 | API 소모액·현금 지출·작업 시간 | 권리·결론`을 남긴다. 자동 정렬·ASR 검산과 사람 청취의 확인 범위를 구별한다.
7. **동결 코퍼스 보고서:** 최종 방식과 교정 이유, 실제 총 제작비·폐기비·검수 범위, 9개 T1의 길이·실제 턴 경계·공통 시간표·파생 관계·역할별 해시를 공개 가능한 범위에서 남긴다. 원음 공개 권리가 없는 항목을 보고서 링크만으로 배포하지 않는다.
8. **현 단계 상태:** 승인된 개발 pilot 6회는 실제 생성했다. 5건의 generation-ID 사용량 조회에서 확인된 API 소모액 부분합은 $0.1151360이며, 첫 take 조회는 HTTP 404여서 해당 비용과 6건 전체 소모액은 미확인이다. 예약 견적을 실청구액으로 대체하지 않는다. 오너가 양언어 실제 청취 품질을 승인했으나 역할 경계 정확성·현금/credit·수수료·세금·청취 검수비는 미확인이고 최종 채택 음성은 아직 없다. 새 본평가 9회/$1.50 승인은 남은 파일럿 역할 검증 후 실행하는 별도 한도다. 요청별 근거와 미확인 항목은 [현재 R3 기록](../corpus/r3/status.json)을 따른다.

근거: [Gemini 요율](https://ai.google.dev/gemini-api/docs/pricing), [선결제](https://ai.google.dev/gemini-api/docs/billing), [음성 생성 가이드](https://ai.google.dev/gemini-api/docs/speech-generation), [이용 약관](https://ai.google.dev/gemini-api/terms).

## 12. 최종 공개 표·상세 감사 표·두 축 그래프

### 12.1 통합 공개 표

한 행은 앱·모델·설정·버전·측정일이 특정된 **프로필**이다. 기본 열은 다음과 같다.

`프로필 | 측정 경로·T1 조건 | 통합 번역 품질 ↑ | 출력 대기 p50 ↓ | 출력 대기 p90 ↓ | 입력 1시간 비용 ↓ | 오류·실패·관측/비용 상태`

- 두 언어쌍과 다섯 유형을 같은 행에 합친다. 기본 행은 `peer / T1 동시 self+peer`, VRCLT·Kikitan 행은 `self / T1 양방향 분리`로 표시한다. T1의 역방향·합성 재구성·실제 출력 종점 차이를 숨기지 않는다. 통합 표를 유지하되 조건 차이를 무시한 단일 동일조건 순위로 발표하지 않는다.
- 품질과 시간에 전체/평가 가능/완료/미확정 건수 및 가중 범위를 연결한다.
- 중대한 최종 의미 오류, 중간 오역 후 정정, 무출력, 제품 실패, 하네스 invalid를 구분한다. T1의 두 역할에서 오류가 나도 ‘오류가 있는 에피소드 수’에서는 한 에피소드로 센다.
- 자동 평가임, 제작자의 이해관계, 자료·합성 비중, **네이티브 번역 출력 종점이며 화면 렌더링 평가는 아니라는 점**, 날짜·버전·정정 경로를 첫 화면에 표시한다. 작은 점수 차이를 검증된 순위 차이로 과장하지 않는다. 앱별 수집 경로·발생 단계·시계 오차와 주 비교 진입 여부를 상세 근거로 연결한다.

### 12.2 기존 상세 표 유지

같은 저장 결과에서 `측정 경로/T1 조건 → 언어쌍 → 유형 → 역할/실제 번역 방향 → 자연/합성/낭독 → 에피소드 → pass → attempt`를 내려다본다. 원문·대본·네이티브 출력 이력·오류 인용·시각 범위·수집 경로/단계·실패·원본 로그 근거까지 연결한다.

통합 표와 상세 표에 서로 다른 수작업 점수를 사용하지 않는다. 필터가 바뀌면 부분집합임을 제목과 분모에 표시한다. 방향·유형별 표는 내부 감사와 공개 상세 확인용으로 남긴다.

### 12.3 AA 방식 두 축 그래프

[AA-Omniscience Index vs. Cost per Task](https://artificialanalysis.ai/evaluations/omniscience)의 프로필별 점·필터·독립 두 축 구조를 참고한다. AA의 지식 점수나 거절 보상 산식을 번역 점수에 가져오지 않는다.

- **Y축:** 통합 GEMBA-ESA 품질. 높을수록 좋다.
- **X축 기본:** p90 번역 출력 의미 대기시간. 짧을수록 좋다. p50 / p90 / 입력 1시간 비용을 선택할 수 있으며 자막 표시 지연으로 표기하지 않는다.
- 점 하나는 조건을 동결한 한 프로필이다. 기본 화면은 통합이며 방향·유형·역할 필터의 범위를 표시한다. `peer / T1 동시`와 `self / T1 분리`는 마커·범례로 구분하고, 다른 출력 종점 단계도 명시한다. 서로 다른 조건을 하나의 Pareto 우열로 연결하지 않는다.
- 고품질·저지연은 왼쪽 위다. 관측 구간은 가로 범위로 그리고 중점을 정밀 좌표처럼 표시하지 않는다. 통계 불확실성과 관측 해상도는 구별한다.
- p90 미충족·관측 불가·비용 미상/구독은 별도 상태 목록에 남긴다. 0·15초·$0의 가짜 점을 만들거나 프로필을 조용히 숨기지 않는다.
- Pareto 표시는 같은 범위의 비교 가능한 관측에만 적용한다. 불확실성이 겹치면 확정 우열을 선언하지 않으며 정밀도가 부족하면 선을 생략한다.

## 13. 구현 계약과 변경 범위

새 계약은 runner → metrics → quality → costs/report 전 구간에서 일관되게 사용한다. 기존 필드명에 새로운 의미를 몰래 끼워 넣지 않는다.

| 계약 | 필요한 내용 |
|---|---|
| episode | 원본/파생 ID, 언어쌍·유형, 자료 방식, 원문·문맥·논리 역할별 번역 대상, 채널별 음원·공통 시간표, 출처·권리·해시; 실제 측정 조건과 pass별 경로·방향·시계 |
| native_output_event | 실제 수집 경로·종점 단계·입력 채널·논리 역할/pass·번역문·native ID/수정 관계, 앱 발생 시각과 수집 시각, 공통 시계의 관측 구간·원시 증거·손실 |
| semantic_checkpoint | 에피소드·역할·원문 근거·의미·앱 입력 기준 시각·관측점별 판정·네이티브 출력 근거 |
| outcome | 입력/앱/관측 기회, 제품 실패·하네스 invalid·미지원·미확정, attempt 관계 |
| judgment | 역할별 오류/점수 두 단계, 실제 모델·프롬프트·입력/결과 해시, 원본 응답·인용·실패 |
| report/cost binding | 동결 manifest·가중치·완료 범위·측정 조건/모집단, 논리 에피소드와 물리 pass별 시간·비용 귀속·가격 근거 revision |

정리 전 `fbab10a`의 `bench/quality_prompts.py`는 단일 ESA-style 호출과 약 30초 품질 구간을 사용했다. 이것은 새 계약의 구현이 아니므로 옛 metrics·품질 orchestration·코퍼스 제작 경로와 함께 현재 실행 코드에서 제거한다. 실행 원장·오디오·무결성·judge 전송/호출 저장·비용 기반은 보존하고, 새 입력 재구성·두 단계 평가·소비자는 해당 구현 이슈에서 함께 전환한다. 과거 코드·원본·점수는 역사적 revision과 증거로 남기며 호환 실행 경로를 만들지 않는다.

새 활성 경로에서는 문장별 SimAlign/대응 캐시·옛 도달률을 주 품질·시간의 필수 경로나 새 지표의 별칭으로 남기지 않는다. 역사적 원본·코드 이력 보존과 실행용 호환 shim 유지는 별개다. 불필요한 범용 코퍼스 프레임워크나 새 지표 묶음을 만들지 않는다.

## 14. 실행 순서와 완료 조건

개발 작업의 의존성·완료 조건은 [구현 계획 R1–R10](benchmark-implementation-plan.md)이 구체화한다. **R1–R5는 구현과 자기 산출물의 최소 확인, R6는 공통 통합 검증, R7은 본 실험과 그 결과 확인**으로 나눈다. R1의 실제 대표 입력·수집 근거와 조기 차단 사유를 확보한 뒤 자료·TTS를 제작하며, R6의 최종 전 프로필 판정을 R2/R3의 선행 조건으로 되돌려 순환 의존성을 만들지 않는다. 권리·원본 적격성·TTS 품질 검수와 첫 API 호출 전 오너 키 설정·사용 승인은 제작 전에 유지한다.

| 단계 | 작업 | 해당 단계의 확인 범위 |
|---|---|---|
| R1 | 수집 구현·조기 가능성 확인 | 대표 실제 입력→native 수집·역할·시계와 차단 사유. 자체 변경 경로만 최소 확인하며 전 프로필 최종 진입 판정은 R6에 남김 |
| R2 | 자료·권리·원본 관계 검수 | 실제 WAV/EAF·전사·시간표·출처·권리·개발/본 분리. 앱별 반복 재생을 완료 조건으로 요구하지 않음 |
| R3 | 일한 T1 대본·Gemini 3.8 Flash TTS 제작 | 오너 키 설정·사용 승인 후 기존 개발 대화의 품질·역할 경계를 검수하고 본 제작. 음원·검수·제작비 근거를 R6에 전달하며 앱 시험용 재생성을 하지 않음 |
| R4/R5 | 품질·대기·비용 구현 | 계산 반례, 보존 로그의 로컬 처리, 실제 judge 두 단계의 최소 확인, 비용 분모·미상 처리. 이를 위해 앱을 다시 실행하지 않음 |
| R6 | **공통 통합 검증·최종 준입·동결** | 실제 입력→앱→native 이력→품질·대기·비용→결과 패키지. 14개 프로필 상태, 두 언어쌍·다섯 유형·T1 조건, 남은 judge 확인과 중단/재개를 기존 증거와 필요한 추가 실행으로 판정 |
| R7 | 본 평가·사전 선택 반복 | 본 실행의 누락·제품 실패·설정 변화와 저장 결과 반영을 확인. R6 파일럿·하네스 검증은 반복하지 않으며 계획된 본 측정 반복은 유지 |
| R8/R9 | 공개표·그래프·영상 | 실제 공개 화면·값·링크와 영상의 내용·시각 동기화 확인. 백엔드 재검증을 위해 원음을 재생하거나 judge를 재호출하지 않음 |

**증거 재사용 규칙**

- 같은 개발 입력·수집 로그·judge 결과를 단계 간 전달한다. 새 이슈·담당자·검토 단계라는 이유만으로 이미 성립한 검증을 다시 실행하지 않는다.
- 재실행은 관련 코드·입력·앱 버전/설정·모델/프롬프트의 변경 영향, 새 실패나 상충하는 증거, 또는 기존 증거로 입증하지 못한 항목이 있을 때만 한다. 원인·영향 범위를 짧게 남기고 해당 부분만 다시 확인한다. 근거 없는 옛 self/OSC 결과를 새 peer 검증으로 재사용하지 않는다.
- 이슈마다 전체 테스트·실앱 파일럿·전 범위 검토를 일괄 반복하지 않는다. 구현 중에는 변경 경로를 확인하고, 통합 관계는 R6에서 검증한다. 필요한 회귀 테스트·적용되는 저장소 검토 절차를 없애는 뜻은 아니다.
- R6는 공통 개발 증거를 한 번 연결해 판정한다. 결함 수리 후에는 영향 범위만 재확인하며, 매번 전체 조합을 처음부터 돌리지 않는다. 추가 대규모 검증 장치나 별도 인증 캠페인을 만들지 않는다.
- R7의 본 측정·사전 선택 반복과 R8/R9의 실제 공개물 확인은 새 산출물에 대한 확인이므로 남긴다. R10의 별도 재측정 목적도 유지한다. 모듈 이슈 완료는 통합 측정이나 공개 준비 완료를 뜻하지 않는다.

동결 묶음에는 protocol, corpus revision, 실제 사례/split/부모 집단, TTS 모델·음색·전체 생성/턴별 전환 규칙·실제 경계·품질/제작비 보고, 역할·언어·입력 경계·시간표, 체크포인트, 가중치, 관측 한도, 앱·모델·설정·wave, native 수집 경로·종점 단계·시계 대응·수집 완전성, GEMBA-ESA upstream/프롬프트/judge, 반복 부분집합, 보고서·비용 단위를 포함한다.

구현 시 영향을 받는 `docs/corpus.md`, `cli.md`, `profiles.md`, `metrics.md`, `quality.md`, `architecture.md`, `costs.md` 및 관련 소비자·행동 테스트를 함께 갱신한다. 실제 승인된 입력 경로→native 출력의 작은 종단간 실행 없이 새 벤치마크 완료를 선언하지 않는다. 현재 정리는 옛 실행 경로의 제거와 기반 보존이며, 남은 runner·costs가 새 episode/T1 계약을 이미 지원한다는 뜻이 아니다.

## 15. 기존 이슈·결과와의 경계

- 기존 총괄 이슈 1번의 글로벌 비교 목적을 유지한다. **새 구현 로드맵은 두 언어쌍·다섯 유형을 범위로 삼고 여섯 방향 누적 의무를 승계하지 않는다.** 이전 미측정 방향을 완료했다고 기록하는 것은 아니다. 오너가 기존 이슈 전체 삭제와 R0–R10 게시를 승인했으며, 실제 번호·관계·교체 결과는 구현 계획의 게시 기록으로 확인한다.
- 기존 이슈 2번의 일본어 자동 참조·출처 보류 자료를 IngCrowd 대신 몰래 승계하지 않는다.
- 기존 이슈 6번의 블라인드 judge 기반은 재사용하되 새 입력·두 단계 GEMBA-ESA로 별도 버전 처리한다.
- 기존 이슈 8번의 실행·14개 프로필·실패 이력을 보존한다. 새 peer/T1 수집·언어·종점·가중치는 새 동결 대상으로 분리한다.
- 기존 이슈 9번의 품질×지연·비용과 실패 공개 요구를 통합 표·상세 표·그래프로 충족한다.
- 기존 이슈 10번의 공개 비교 영상은 Claude 작업으로 유지하되 실제 native 출력 이력의 재생으로 바꾼다. 앱 화면 캡처나 화면 가독성 시험으로 부르지 않는다.
- 기존 이슈 11번의 PuriPuly 재측정·재채점·별도 개발 입력·ASR/분절 2×2와 제한된 sweep은 GPT 후속 작업으로 유지한다. 첫 공개의 선행 조건이나 타 저장소 수정 권한이 아니다.
- 과거 D1/D3 원본·점수·무결성 보류를 덮어쓰지 않는다. 언어·음원·종점·평가 단위가 바뀌므로 기존 점수와 직접 증감률을 발표하지 않는다.
- 이 문서로 이전의 T1 비필수, P1–P4 균등 비중, 일본어 일반 회화의 조건부 TTS 대체, 5등급/양호 비율 제안은 실행안에서 제외한다. 기존 논의 문서는 선택 이력으로 남긴다.
- 사용자 승인으로 이전의 실제 자막 표시 종점을 **앱의 번역 출력**으로 전환했다. 기존 표시 지연 지표에 새 이름만 붙인 것이 아니며, 공개 문구·이벤트 계약·시계·품질 입력·캐시·비교 가능성을 새 protocol revision으로 동결한다.

## 16. 계획 작성 시 확인 범위와 근거

### 실제 확인한 범위

- 기존 분석 이슈·개편 논의·현재 judge 계약을 읽고 이번 설계에 반영했다. 기존에 보고된 결함을 다시 실행해 확인하지 않았다.
- 선행 조사에서 IngCrowd의 공개 접근·샘플 EAF/WAV 구조를 확인했다. 전체 corpus 청취·전사 검수·본 평가 사례 선정은 아직 아니다.
- 공식 GEMBA-ESA의 오류 판정·직접 점수 프롬프트와 Gemini TTS의 일본어·한국어 지원을 문서에서 확인했다. 실제 생성·청취 비교·새 judge 호출은 하지 않았다.
- 인메모리 산술로 최신 유형 비중의 합 100%, 언어쌍별 표본 목표 30개, T1 합계 30% 및 한 언어쌍·한 T1 역할의 전체 기여 7.5%를 확인했다. 실측 앱 결과가 아니다.
- 2026-10-26 Gemini 3.8 Flash TTS의 공식 다중 화자 요청·mono 출력·한도·요율을 확인하고, 채택 음성 9분/누적 입력 10,000 tokens 가정의 1회·3배 생성 사용료를 인메모리 검산했다. 실제 일한 음성·화자 경계·계정 권한·최종 제작비 검증은 아니다.
- 스크립트 전체 생성 후 역할별 시간축 배정은 임시 인메모리 PCM 예제로 검산했다. 길이·원래 샘플 위치·무음 간격 유지와 합산 복원, 연속된 같은 역할 턴의 배정, 겹친 경계/미배정 음성의 거부를 확인했다. 실제 TTS·정렬·화자 판정의 검증은 아니다.
- 6개 앱·14개 프로필의 기존 OSC·CLI·WebSocket·로그/DB 경로와 역할·타임스탬프·수정 이력 제약을 핀 소스로 조사했다. PuriPuly의 별도 peer ASR, Kikitan의 실제 VRChat process 입력, VRCS의 공유 ASR 언어, VRCLT의 final-only 로그를 파일럿 선행 조건에 반영했다.
- 기존 `bench.osc.Sink`를 임시 loopback UDP로 실제 실행했다. 합성 `/desktop/translated`와 `/chatbox/input` 제어 패킷을 보냈을 때 기존 수신기는 chatbox 한 건만 저장했다. 이는 새 주소 어댑터가 필요하다는 하네스 검산이지 번역 앱의 peer 출력 실측이 아니다.
- 설치 VRCLS 1015의 DLL을 PEReader/IL로 읽어 역할별 로그·파일 timestamp 형식·Desktop OSC 제외를 확인했다. 대상 앱을 실행하지 않았으며 이 조사를 peer/T1 파일럿 통과로 기록하지 않는다.
- VRCLT self의 `_on_partial`과 `_on_final`이 모두 OSC 출력에 연결되는 소스를 확인했다. INFO 로그만 final-only라는 범위를 명시하고, 사용자 승인에 따라 self-only·T1 양방향 분리 실행 및 공개 조건 표기를 반영했다.
- self 분리 T1의 역할별 샘플 위치·무음·합산 복원, pass 사이 준비 시간의 지연 제외, 역할별 7.5%/T1 총 30%, 논리 에피소드 60개와 물리 pass 78개, 두 pass 비용 합산/원래 에피소드 시간 분모를 인메모리 예제로 검산했다. 실제 앱·음원·청구액 측정은 아니다.

### 주요 근거

- [발견된 분석 이슈](../.data/issue8/batch-analysis-v1/discovered-analysis-issues.md) — ignored 로컬 조사 기록. 외부 배포 시 비공개 원본 경로·개인정보는 공개하지 않음.
- [기존 개편 논의와 데이터 조사](benchmark-redesign.md)
- [ASCEND 공식 저장소](https://github.com/HLTCHKUST/ASCEND), [데이터카드](https://huggingface.co/datasets/CAiRE/ASCEND), [논문](https://aclanthology.org/2022.lrec-1.788/)
- [IngCrowd 데이터카드](https://huggingface.co/datasets/IngCrowd/japanese-themed-dialogue), [FLEURS](https://huggingface.co/datasets/google/fleurs)
- [ESA 논문](https://aclanthology.org/2024.wmt-1.131/), [공식 GEMBA-ESA 코드](https://github.com/MicrosoftTranslator/GEMBA/blob/main/gemba/gemba_esa.py)
- [Gemini 3.8 Flash TTS](https://ai.google.dev/gemini-api/docs/models/gemini-3.8-flash-tts), [TTS 가이드](https://ai.google.dev/gemini-api/docs/speech-generation), [이용 약관](https://ai.google.dev/gemini-api/terms)
- [보존된 judge 기반과 역사적 품질 계약](quality.md), [현재 비용 처리와 새 분모의 경계](costs.md), [구현 계획](benchmark-implementation-plan.md)
