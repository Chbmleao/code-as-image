# Literature review notes (UFM-5)

Notes per source, with claim, method and how each relates to the project.

| File | Covers |
| -- | -- |
| book-validity-and-response-matrices.md | Book 1.2, 1.3, 2.1, 2.5 |
| book-ch3-rasch-irt.md | Book ch. 3, mainly 3.3, 3.5, 3.6 |
| book-ch5-reliability-gtheory.md | Book 5.1 to 5.4, 5.6, 5.7 |
| book-dif-design-efficiency.md | Book 5.11, 5.12, 5.13, 6.1, 6.2 |
| book-intervention-and-design.md | Book 9.1 to 9.3, 11.4, 11.6, 11.8, 11.9 |
| papers-visual-text-compression.md | DeepSeek-OCR, Glyph, VTCBench, CodeOCR, LongCodeOCR, CodeShrink, Text or Pixels |
| papers-long-context-code-benchmarks.md | CodeFlowBench, RepoBench, LongCodeBench, CrossCodeEval, EvoCodeBench, MINT, SWE-bench Lite |
| papers-modality-gap-and-psychometrics.md | IsoBench, SEAM, Text or Pixels, VTCBench, Sclar et al., Messing |
| pxpipe.md | pxpipe README, render profiles, legibility audit, Qwen and SWE-bench evals |

Numbers marked "(check)" or UNVERIFIED in these files came from abstracts or summaries and must be
checked against the PDFs before they go into the proposal.

## Gap statement

Rendering text as images is an established way to cut context cost. DeepSeek-OCR and Glyph show
that vision-language models can read rendered prose back at several times compression, with
accuracy falling as compression rises, and pxpipe applies the idea to coding-agent sessions.
Work on the modality gap (IsoBench, SEAM) finds that the same task given as an image is solved
less often than as text, and recent papers (CodeOCR, LongCodeOCR, CodeShrink) look at code in
images specifically. What is missing is a measurement of the cost. None of the three code-image
papers scores answers by running unit tests: they use exact match, edit similarity, an LLM judge,
clone-detection F1 or QA accuracy. Their open-weight models are either above 100B (CodeOCR) or one
or two 8B to 27B models (LongCodeOCR, CodeShrink), so no study compares several small local
vision-language models on the same code. CodeOCR has a code reconstruction probe, but it is not
linked per item to execution-scored tasks. pxpipe's own evals use small samples without
uncertainty and test coding tasks on one model. No study we found uses psychometric methods;
the code-image papers report averages over five runs and Wilcoxon tests. This project fills that
gap: it treats rendering as an intervention on the input, measures its effect on test-verified
pass rates for several small local vision-language models against the tokens it saves, separates
reading errors from coding errors per item with a transcription probe on unit-test tasks, and uses
paired response matrices, many-facet Rasch, G-theory and DIF to ask whether coding from image
context is the same ability as coding from text.

Caveat: CodeOCR, LongCodeOCR and CodeShrink were read in full. The search for other work, including
2026 papers that cite these three, was a first pass by search engine and was not exhaustive.
