# Changelog

All notable changes to fablize are documented here.
Format follows [Keep a Changelog](https://keepachangelog.com/); versioning is [SemVer](https://semver.org/).

## [2.1.0] — 2026-06-18

측정 우선(measure-first). 검증되지 않은 성능 기능은 켜지 않고, 게이트의 노이즈를 줄이고, 효과를 실제 작업에서 잴 out-of-band 측정 인프라를 추가했다.

### Added
- **관측 게이트(observation gate)** — Stop 훅이 `deep + 파일변경 + 검증 미관찰` 턴의 완료를 차단한다(quick/normal/docs/변경0은 통과). 모델의 주장이 아니라 관측된 ledger 증거로만 판단(언어 무관). MAX 2회까지 막고 그 뒤 통과(무한 트랩 방지).
- **작업 분류기** — 프롬프트를 quick/normal/deep로 분류 + risk flags(production/database/secret-or-auth/remote-write) 추출.
- **out-of-band 측정 인프라(shadow)** — `events.jsonl` 로거/수집기, env-gated holdout 토글(`FABLIZE_HOLDOUT`, 기본 OFF), 결과신호 수집기(revert/rework/재지시), 층화 분석 + sunset. **기본 OFF, 모델 컨텍스트 밖**에서만 기록(관측자 효과 차단). 설계는 `docs/MEASUREMENT_PROTOCOL.md`.
- **reactive effort-delegation rung** (`SKILL.md §4`) — 막힌 *bounded slice*만 백그라운드 Workflow(`effort:max`)로 위임 후 결과로 재개. 일반 세션의 유일한 per-task effort 노브. **opt-in·효과 미입증**, risk/deep만으로는 발화 금지(false-escalate 가드).
- **silent-recovery 가드** — 일회성 실패는 조용히 복구, 같은 계열 실패가 2회+ 반복되면 짧게 공개(정규화 signature로 같은 계열 판정).
- **테스트** — 게이트(6) + robustness(12) + shadow/M3/M4/recovery.

### Changed
- **게이트 deep-only + 변경 있을 때만** — normal 모드 hard-block 제거, deep도 *변경 없는* 턴(분석/문서/리딩)엔 발화 안 함. 실측상 발화 노이즈 ~2/3 감소. 진짜 위험("deep에서 코드 바꾸고 검증 안 함")만 차단.
- **deep 프롬프트 넛지** — 증거/gap 노트는 *실체가 있을 때만*(검증했거나 주장이 tool result에 근거) 한 줄, 사소한 턴엔 생략. 의례용 보일러플레이트 제거.
- **setup** — setup 흐름 정리(단일 up-front 질문, 내부 헬퍼를 setup.sh에 인라인).

### Removed
- 내부 setup 헬퍼 스크립트 — setup.sh에 인라인.
- `has_any_verification()` — 게이트 축소 후 미사용.

### Notes (정직성)
- **효과는 미입증.** 새로 켠 성능 기능은 없다. shadow 측정기로 실작업에서 게이트·effort 위임의 효과를 사후에 측정하기 위한 릴리스다. 토이 A/B 3라운드는 천장으로 무력했다(자세한 분석은 내부 문서).
- 내부 R&D 문서(개인경로·PII 포함)는 `.gitignore`로 배포 제외.

## [2.0.0] — 2026-05

- 초기 fablize 하네스 — Opus를 Fable처럼(완결·증거·검증을 절차로 강제) 동작하게 하는 스킬 + setup.

[2.1.0]: https://github.com/fivetaku/fablize/compare/v2.0.0...v2.1.0
[2.0.0]: https://github.com/fivetaku/fablize/releases/tag/v2.0.0
