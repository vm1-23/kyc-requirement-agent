# Evaluation results (offline rule-based mode)

Generated with `kyc-re --llm offline evaluate <case>`; the raw JSON reports are in this folder.

**How to read this.** Gold labels were written by the project team, not an independent expert panel. The NeoBank case was used to develop the rules, so its scores are optimistic. PayFlow run 1 was held out. Its failures led to general v2 changes (wider control vocabulary, control-based conflict topics), so after v2 it no longer counts as held-out. Summit was written after v2 and run once with no tuning, which makes it the most honest estimate of rule-only performance on unseen input.

| Case | Extraction F1 | Classif. acc | Ambiguity F1 | Conflict P / R | Control-map F1 | Gap-detect F1 | Citation validity | Halluc. rate | SDLC top-1 acceptable | Trace cov. | Time (s) |
|---|---|---|---|---|---|---|---|---|---|---|---|
| NeoBank (IN) – dev set, v1 | 0.976 | 0.976 | 0.667 | 1.0 / 1.0 | 0.814 | 1.0 | 1.0 | 0.0 | yes (Hybrid Agile-DevSecOps) | 1.0 | 0.08 |
| NeoBank (IN) – dev set, v2 | 0.976 | 0.976 | 0.667 | 0.75 / 1.0 | 0.833 | 1.0 | 1.0 | 0.0 | yes (Hybrid Agile-DevSecOps) | 1.0 | 0.156 |
| PayFlow (EU) – held-out run 1, v1 | 0.976 | 0.85 | 1.0 | 0.0 / 0.0 | 0.667 | 0.5 | 1.0 | 0.0 | yes (Hybrid Agile-DevSecOps) | 1.0 | 0.034 |
| PayFlow (EU) – after v2 fixes (no longer held-out) | 0.976 | 0.85 | 1.0 | 0.5 / 1.0 | 0.889 | 0.857 | 1.0 | 0.0 | yes (Hybrid Agile-V-Model) | 1.0 | 0.051 |
| Summit (US) – held-out run 1, v2 | 1.0 | 0.786 | 0.667 | 0.0 / 0.0 | 0.7 | 0.9 | 1.0 | 0.0 | no (Spiral) | 0.939 | 0.039 |

## Observations

- **Extraction** of explicit need statements works well with rules alone (F1 0.98–1.0), because stakeholders state needs with modal verbs.
- **Implicit conflicts** need semantic understanding. Example from Summit: "open instantly without repeating identity checks" vs "verify identity within 5 business days". Rule mode misses these (Summit conflict recall 0). This is where the Claude mode is meant to add value. Its LLM output still passes through the same grounding checks.
- **Gap detection** recall is high, but precision depends on vocabulary. A control phrased in unfamiliar words is reported as a gap, which is the safe failure: a human reviews it, and nothing is silently dropped.
- **SDLC**: two of three cases match an acceptable expert choice. On Summit the engine picked Spiral, influenced by the novel-technology and legacy-mainframe factors, while the gold expects a regulated hybrid. Factor weights should be calibrated against a larger set of architect decisions.
- **Hallucination rate** is 0 by construction in offline mode, because no generative output is produced. In Claude mode the same metric counts ungrounded extractions and out-of-evidence citations that the guards dropped.
- **Time**: the pipeline runs in under 0.1 s offline. The manual baseline in each report is an assumption, not a measurement, so it is not presented as a finding.

## Not yet evaluated

- Claude (LLM-augmented) mode: no API credentials were available in the build environment. Run `KYC_RE_LLM=claude kyc-re evaluate samples/<case>` to produce the comparison.
- Stakeholder satisfaction, and human correction rate in live use. These need a user study.
