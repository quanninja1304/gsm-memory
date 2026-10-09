---
name: sci-paper-review
description: >
  Review, critique, and edit CS/AI academic papers, theses, and reports against
  59 common academic writing errors across 7 groups. Use this skill whenever the
  user wants to: review/check/edit a paper, thesis, or report; find errors in
  writing style, citations, figures, or equations; critique a section for academic
  quality; or asks "what's wrong with this paper / section".
---

# CS/AI Scientific Paper Review

Reviews papers against 59 common errors across 7 groups. For full papers, check all 7 groups sequentially. For a single section, focus on the relevant group(s).

## General principles

- Be specific: quote the problematic passage, don't give vague feedback.
- For each error found: state **what** the error is, **why** it's wrong, **how** to fix it.
- Mark critical errors ★★★ (academic integrity / plagiarism issues) - flag these first.
- End every review with a summary table: error count by group + fix priority.

---

## Group 1 - Structure & Overview (errors 1–10)

| # | Error | Signal | Fix |
|---|-------|--------|-----|
| 1 | Introduction too short | < 1 page; missing context/motivation | Expand; final paragraph must outline paper structure |
| 2 | Paper structure listed as bullets | "Outline" section uses bullet points | Rewrite as continuous prose |
| 3 | Problem Statement placed after Related Work | Problem section appears after RW | Move it *before* Related Work |
| 4 | Problem Statement incomplete | Missing: What is the problem? Where does it come from? Has it been solved? Where do challenges arise? | Add argumentation answering all 4 questions |
| 5 | Subsections over-fragmented | A section has ≤ 2 paragraphs | Merge small subsections |
| 6 | Chapter intro paragraphs inconsistent | Some chapters have opening paragraphs, others don't | Add/remove to make all chapters consistent |
| 7 | Per-chapter conclusions present | "Chapter X Conclusion" appears repeatedly | Remove; fold into one global conclusion |
| 8 | Wrong section order | Objectives/method out of order | Correct order: Scope → Subject → Method → Objectives → Significance |
| 9 | Significance stated before results | Contribution claims appear before any results | Present content/expected results first, then significance |
| 10 | Sub-items a/b broken into separate sections | "a. ...", "b. ..." become their own subsections | Inline as prose: "a and b"; "a, b, and c" |

---

## Group 2 - Related Work & Literature Review (errors 11–17)

| # | Error | Signal | Fix |
|---|-------|--------|-----|
| 11 | RW only describes prior work, no critique | No gap identified, no weaknesses noted | Add critical analysis + explicit research gap |
| 12 | RW structured as flat list of papers | Each paper gets its own disconnected paragraph | Reorganize by theme or research direction |
| 13 | Challenges not grounded in literature | Challenges appear without broad survey support | Expand survey scope; cite specific evidence for each challenge |
| 14 | Purpose of background section unclear | Reader can't tell why this section exists | Clarify role: foundational knowledge needed to understand contributions |
| 15 ★★★ | Background claims uncited → plagiarism | Statements from other sources have no citation | Cite every claim derived from external sources |
| 16 | Citation without content, or content without citation | "[1]" with no explanation; or claim with no "[x]" | Citation and content always paired together |
| 17 | RW has no synthesis / gap summary | Section ends without answering: who did what, where is the gap? | Add synthesis paragraph at end of RW |

---

## Group 3 - Figures & Tables (errors 18–29)

| # | Error | Signal | Fix |
|---|-------|--------|-----|
| 18 | Figure not original / low resolution | Pixelated, copied from another paper | Redraw at ~4K; original design required |
| 19 | Figure not referenced in text | Figure appears but no "Figure x.x shows..." in body | Add in-text reference before the figure |
| 20 | Section opens with a figure/table/bullet | First element in section is a figure | Add introductory prose before the figure |
| 21 ★★★ | Borrowed figure has no source credit | Caption lacks "(Source: ...)" | Add source attribution to every non-original figure |
| 22 | Incorrect figure reference style | "(Figure x.x)" instead of "Figure x.x illustrates..." | Rewrite as full sentence; capitalize "Figure" |
| 23 | Inconsistent figure styles | Each figure uses different fonts/colors | Unify visual style across all figures |
| 24 | Garish colors / no color legend | Neon colors; chart has no legend | Use muted professional palette + add legend |
| 25 | Table not referenced in text | Table x.x never mentioned in body | Add in-text reference to table |
| 26 | Table caption ends with period | "Table 3.1. Performance comparison." | Remove trailing period from caption |
| 27 | Screenshot used instead of real table | Table is an image/screenshot | Typeset a real table in Word/LaTeX |
| 28 | Bold text used as highlight inside table | Cell content is bolded for emphasis | Remove bold; use light background shading if needed |
| 29 | Figures/tables lack explanatory captions | Caption only names the figure, no explanation | Write a caption that explains meaning, not just lists components |

---

## Group 4 - Equations & Algorithms (errors 30–37)

| # | Error | Signal | Fix |
|---|-------|--------|-----|
| 30 | Equations not numbered | Equations appear without (x.x) labels | Number all equations |
| 31 | Notation not explained | Equation copied without defining variables | Define every symbol immediately after the equation |
| 32 | Equation purpose not stated | Equation given without explanation of what it computes or why | Add: "Equation x.x computes ... because ..." |
| 33 | Punctuation errors in equation annotations | Missing commas, "and"; "equation" not capitalized when cited | Proofread all equation annotation syntax |
| 34 | Equations not properly formalized | Equations written in plain text | Use standard LaTeX mathematical notation |
| 35 | Algorithm described in prose, no pseudocode | Algorithm explained in running text | Rewrite as formal pseudocode |
| 36 | Functions/methods used without citation | Third-party function/method used with no cite | Cite the source of every borrowed function |
| 37 | Inconsistent equation reference style | Mixed forms when citing equations | Use consistently: "as defined in Equation x.x" |

---

## Group 5 - Citations & References (errors 38–44)

| # | Error | Signal | Fix |
|---|-------|--------|-----|
| 38 ★★★ | External content not cited → plagiarism | Claims from other sources have no [x] | Add citations immediately |
| 39 | Inconsistent citation style | Mix of APA, IEEE, and ad-hoc styles | Pick one style, apply it uniformly |
| 40 | Reference formatting errors | Missing `~` before `\cite{}` in LaTeX; missing required fields | Normalize to template requirements |
| 41 | Abbreviation list not alphabetical | BERT listed before AE, etc. | Sort A → Z |
| 42 | Web references missing access date | URL has no "Accessed: DD/MM/YYYY" | Add access date to every web reference |
| 43 | Supervisor name missing title/degree | "Nguyen Van A" instead of "Dr. Nguyen Van A" | Add full academic title with correct punctuation |
| 44 ★★★ | Benchmark/baseline uncited or unjustified | Baseline has no [x]; no rationale for why it's SOTA | Cite + explicitly justify baseline selection |

---

## Group 6 - Writing Style (errors 45–54)

| # | Error | Signal | Fix |
|---|-------|--------|-----|
| 45 | First-person pronouns used | "we", "I", "our" in body text | Rewrite as passive or impersonal constructions |
| 46 | Mixed languages within sentences | "Chúng tôi sử dụng attention mechanism để..." | Use consistent terminology; define once if mixing is unavoidable |
| 47 | Abbreviations used before definition | BERT, CRS, KG introduced without expansion | Define on first use: "Knowledge Graph (KG)" |
| 48 ★★★ | Near-verbatim paraphrase → plagiarism | Source changed by only a few words | Rewrite entirely in own words + cite |
| 49 | Single-sentence paragraphs | Paragraph = one lone sentence | Expand or merge with adjacent paragraph |
| 50 | Bullet lists instead of paragraphs | Explanatory content presented as bullets | Rewrite as top-down prose: main point first, then detail |
| 51 | Digits instead of words for small numbers | "3 methods", "2 datasets" in prose | Write out: "three methods", "two datasets" |
| 52 | Section headings end with period or contain parentheses | "3.2. Proposed Method." | Remove trailing period; no parenthetical notes in headings |
| 53 | Excessive commas | Comma overuse (common in AI-generated text) | Re-read and remove unnecessary commas |
| 54 | Incorrect section numbering / bold highlights | Major sections use 1, 2 instead of I, II; random bold in body | Use Roman numerals for top-level; remove arbitrary bold |

---

## Group 7 - Dataset & Experiments (errors 55–59)

| # | Error | Signal | Fix |
|---|-------|--------|-----|
| 55 | Dataset undescribed and unjustified | Only dataset name given, no description or reason | Describe characteristics + explain why this dataset over alternatives |
| 56 | Dataset fairness not demonstrated | No mention of representativeness or community adoption | Add: is it widely used in the community? Is it balanced? |
| 57 | Experiments have no stated purpose | "Experiment 1: ..." with no explanation of what it tests | State the goal of each experiment; confirm dataset suitability |
| 58 | Advantages listed without disadvantages | Only positive aspects of method discussed | Add balanced Discussion section covering limitations |
| 59 | Design choices not justified | Hyperparameters, loss functions, configs chosen without explanation | Explain the "why" behind every design decision |

---

## Review workflow

**Step 1 - Determine scope**
- Full paper → check all 7 groups in order
- Single section → identify relevant group(s), focus there
- Specific question → look up error number, answer directly

**Step 2 - Report each error found**

```
**[Error #XX] Error name** [★★★ if critical]
> Location: "quoted passage..."
Problem: [why this is wrong]
Fix: [specific suggestion or rewritten version]
```

**Step 3 - Summary table**

```
| Group               | Errors | Critical (★★★) | Priority |
|---------------------|--------|----------------|----------|
| 1. Structure        | x      | x              | High/Med/Low |
| ...                 |        |                |          |
| TOTAL               | xx     | xx             |          |
```

---

## Critical errors - flag immediately (★★★)

- **#15, #38, #48** - Plagiarism (missing citations, near-verbatim paraphrase)
- **#21** - Uncredited borrowed figures
- **#44** - Baseline/benchmark without scientific justification

---

See `references/error-checklist.md` for a compact quick-reference of all 59 errors.