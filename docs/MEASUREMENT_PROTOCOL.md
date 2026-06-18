# fablize 측정 프로토콜 (out-of-band)

> 목적: fablize의 HOLD 컴포넌트(effort 위임·pack-router·silent-recovery·shadow)와 Stop-hook 게이트의 **효과를 실제 작업에서 측정**한다. 토이 seeded-trap A/B 3라운드(~3.3M 토큰)가 천장으로 무력했으므로, 측정은 longitudinal·out-of-band로만 한다.
> 근거: 내부 측정 골(`measurement-goal/`, 배포 제외), 5-voice 설계 토론, `HANDOFF-dynamic-effort-delegation.md §10-3`.

## 0. 원칙 — 효과 입증 전 always-on 금지
측정 안 된 그럴듯한 메커니즘은 후보(HOLD)일 뿐이다. 이 프로토콜은 **무엇을, 어디에, 어떻게 기록해 어떤 가설을 기각/입증하는지**만 정의한다. 측정 결과가 park-until-proven 게이트(표본·효과크기·층화 비교)를 통과하기 전에는 어떤 HOLD 컴포넌트도 활성화하지 않는다.

## 1. 1순위 질문 — 하네스 역설 (가장 먼저 답한다)
gemini 적대검토가 제기: 게이트의 강제 검증 발화·반복이 컨텍스트를 노이즈로 채워 장기 세션 주의력을 분산 → **하네스가 오히려 마이너스 수익률**일 수 있다. lift=0.0은 성공이 아니라 본전치기 경고일 수 있다.
- **측정**: 게이트 ON 세션 vs OFF holdout 세션의 실작업 결과신호(revert/재지시/재작업률) 차이.
- **기각조건**: ON군이 OFF군보다 결과신호가 유의하게 나쁘면(역효과) → 게이트를 deep-only로 축소하거나 재설계.
- **이게 다른 모든 측정보다 우선**. 게이트 자체가 손해면 그 위에 얹는 모든 것이 무의미.

## 2. 로깅 대상 (event 종류)
append-only `events.jsonl` 한 줄당 한 이벤트. 각 이벤트: `{ts, session_id, holdout_arm, event_type, payload}`.
- `gate_fire` — Stop-hook 차단 발화 (mode, changed, verified, stop_blocks)
- `classify` — quick/normal/deep + risk_flags
- `effort_candidate` — "이 슬라이스는 effort:max 위임 후보였다" **라벨만**(실제 위임 안 함)
- `recovery_repeat` — 같은 계열 실패 반복 횟수(silent-recovery 카운터, 개입 없음)
- `outcome` — 사후 수집된 결과신호(§5)

## 3. out-of-band 위치 — 관측자 효과 차단 (금지선)
설계가·측정가·codex가 독립 지적: **in-context 로깅은 측정 대상을 바꾼다**(통제군이 헌법 §3을 자발 인용한 게 증거). 따라서:
- 모든 라벨링·로깅은 **모델 컨텍스트 밖**에서 한다 — Stop/PostToolUse hook이 종료 후 ledger·트랜스크립트를 **사후 파싱**해 `events.jsonl`에 쓴다.
- shadow 라벨을 모델 프롬프트·`additionalContext`·system 메시지에 **절대 주입하지 않는다**(검증: in-context 로깅 0건 grep).
- 진짜 baseline은 shadow조차 끈 **holdout 세션군**(§4).

## 4. holdout 설계
- 세션 시작 시 결정론적 해시(session_id)로 **게이트 OFF holdout 20%** vs ON 80% 분기.
- holdout 세션: Stop-hook 게이트 비활성(차단 안 함) + 라벨링도 최소화 → 순수 baseline.
- `holdout_arm` ∈ {`on`, `off`}를 모든 이벤트에 기록. **이 분기는 모델에 노출하지 않는다**(out-of-band).

## 5. 결과 신호 (사후 수집, 측정의 종속변수)
세션 종료 후 git·트랜스크립트에서 수집(모델 개입 없음):
- `reverted_edits` — revert/되돌린 커밋 수
- `user_reinstructions` — 사용자 재지시·정정 발화 수
- `rework_commits` — 같은 파일 재수정 빈도
- `wall_time`, `tool_calls`, `failed_verifications`
- `final_defect_found` — 사후 발견된 결함(있으면)
- 생존편향 방어: 성공뿐 아니라 **faking-pass·포기 케이스도 기록**.

## 6. 분석 (층화 비교)
- task 유형·세션 규모로 **층화** 후 ON vs OFF(holdout) 결과신호 비교.
- effort_candidate 라벨 슬라이스: 라벨 vs 비라벨을 사용자·과제유형으로 **매칭**해 재작업률 비교(실제 위임 안 했으므로 counterfactual).
- 단일 지표 금지 — §5 다지표를 함께 본다. 표본·효과크기 명시 없는 결론 금지.

## 7. sunset 조건
비용가 지적: shadow도 유지보수 부채. **기본 sunset = 50세션 누적 후** §1 하네스 역설에 유의 신호(효과크기 임계 초과)가 없으면 계측을 제거한다. sunset 기준·현재 카운트를 `events.jsonl` 헤더 또는 별도 메타에 기록.

## 8. 측정 대상별 가설·기각조건
| 컴포넌트 | 가설 | 입증 신호 | 기각 신호 |
|---|---|---|---|
| Stop-hook 게이트 | 누락을 줄여 결과신호 개선 | ON군 revert/재지시 ↓ (holdout 대비) | ON군이 같거나 악화(하네스 역설) |
| effort 위임 | 위임 후보 슬라이스가 위임 시 품질↑ | 라벨 슬라이스 재작업률이 높고, 실제 위임 시 ↓(후속 실험) | 라벨↔비라벨 재작업률 차 없음 |
| silent-recovery | 반복실패 공개가 사용자 신뢰↑ | 반복 카운트↑ 세션의 재지시↓ | 상관 없음/보고 스팸 부작용 |
| pack-router | 맞는 팩만 선택 | 라우팅 정확도(confusion matrix) | 과선택/누락 다수 |

## 9. 불변 제약 (PRD — 불가침)
1. out-of-band 필수 (in-context 로깅 금지)
2. holdout 설계 (ON vs OFF)
3. 1순위 = 하네스 역설
4. 행동 불변·발화 0
5. deep/stop_blocks → effort/위임 배선 금지(false-escalate)
6. sunset 조건 명시
7. effort 위임은 라벨만(실제 위임 금지)
