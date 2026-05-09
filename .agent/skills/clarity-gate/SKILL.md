---
name: clarity-gate
description: "Pre-ingestion quality gate that verifies epistemic integrity of documents before adding them to RAG systems or knowledge bases. Runs 9-point verification (source authority, factual accuracy, internal consistency, temporal validity, bias detection, completeness, clarity, relevance, contradiction checks) with Two-Round HITL workflow for human review of flags. Use when validating documents for RAG ingestion, checking knowledge base quality before vectorization, auditing content for retrieval-augmented generation pipelines, verifying document epistemic quality, or building reliable AI knowledge bases."
type: feature
source: "https://github.com/frmoretto/clarity-gate"
risk: safe
user-invocable: true
---

# Clarity Gate

Quality assurance layer for RAG systems that prevents contaminated or low-quality documents from poisoning your knowledge base.

## The 9-Point Epistemic Verification

Documents entering your RAG system must pass all 9 checks:

1. **Source Authority**: Is the source credible? Are credentials verifiable? Is authorship clear?
2. **Factual Accuracy**: Are claims verifiable through primary sources? Any suspicious statistics?
3. **Internal Consistency**: Do statements contradict each other? Are definitions consistent throughout?
4. **Temporal Validity**: Is the information still current? Are dates specified for time-sensitive claims?
5. **Bias Detection**: Does the document lean heavily one direction? Are counterarguments presented fairly?
6. **Completeness**: Are claims fully developed? Are edge cases acknowledged? Limitations stated?
7. **Clarity & Precision**: Is language precise or vague? Are technical terms defined? Ambiguity present?
8. **Relevance**: Does this serve your knowledge base purpose? Will it improve search quality?
9. **Contradiction Checks**: Does it contradict existing documents? If so, which version is authoritative?

## Two-Round HITL Workflow

### Round 1: Automated Verification
Run document through all 9 checks, flag any items that:
- Fail hard rules (missing source, non-verifiable claims)
- Score below threshold on soft rules (bias, clarity)
- Contradict existing knowledge base entries
- Have time-sensitive info without dates

### Round 2: Human Review
Human reviewer addresses all flags:
- For each flag, decide: **Accept** (confident in document), **Reject** (remove document), or **Quarantine** (expert-only access)
- Document reasons for each decision
- Update temporal validity markers for periodic re-verification

## Implementation Checklist

- [ ] Define verification thresholds for soft rules (bias score, clarity score)
- [ ] Establish source authority whitelist/blacklist
- [ ] Set up contradiction detection against existing docs
- [ ] Create human review dashboard for flagged documents
- [ ] Implement automated Round 1 scoring pipeline
- [ ] Configure notification system for Round 2 human reviewers
- [ ] Schedule periodic re-verification of time-sensitive documents

## Quality Metrics

Track these to measure knowledge base health:

| Metric | Target | Action if below |
|--------|--------|-----------------|
| Pass rate (% docs clearing all 9 checks) | 75%+ | Review verification thresholds |
| Human agreement rate (Round 2 decisions) | 85%+ | Retrain automated checks |
| False positive rate (rejected docs that were fine) | <5% | Loosen thresholds |
| Contradiction rate (vs. existing docs) | <2% | Audit knowledge base conflicts |

See [source repository](https://github.com/frmoretto/clarity-gate) for implementation examples and evaluation datasets.
