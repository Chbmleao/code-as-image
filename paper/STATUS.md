# Paper status (UFM-14)

Second block, 2026-11-25. Related work, methods and results have prose and passed a fresh-context review. Spec:
`~/.claude/specs/paper.md`. Deadline 2026-11-30, body at most 8 pages (references and appendix
excluded), Portuguese, NeurIPS 2025 style with the `final` option.

## Sections

| Section | State |
|---|---|
| 2 Trabalhos relacionados, 3 Metodos | written; reviewed; fixes applied |
| 4 Resultados, captions of Fig. 1 to 3 and Tab. 1 | written; reviewed; fixes applied |
| Resumo, 1 Introducao, 5 Discussao, 6 Limitacoes, 7 Conclusao | written; reviewed; fixes applied |
| Appendix | floats numbered A1, A2, ...; A1, A3, A5 and the captions still todo |

Page budget: the body ends on page 8 with the todos still in. Done: Fig. 3 moved to the appendix,
Tab. 2 written as prose in 5.1, 4.6 trimmed (Claude intervals point to Tab. A4), repeats between
sections 1, 2 and 6 removed. Any sentence added later needs a cut elsewhere.

Open: the appendix (A1, A3, A5, captions) and the UFM todos. Planned order from the spec: 26/11 methods, data, related work, results; 27/11
discussion, limitations, conclusion, abstract; 28/11 the three issues below and the merge of
origin/main (ask first); 29/11 page limit, fresh-context review, final read; 30/11 delivery.

## Overleaf

`uv run python paper/build.py --overleaf` also fills `paper/out/overleaf/` (not versioned): the
sources plus the generated `numbers.tex`, `tables/` and `figures/`. Drag the folder's contents into
a new Overleaf project and set the compiler to XeLaTeX (Menu > Compiler): the folder compiles with
tectonic, which is XeTeX. pdfLaTeX has a branch in the preamble but was not tested, since no
pdfLaTeX is installed here. Overleaf cannot run the scripts: when results change, rerun the build
here and upload `numbers.tex`, `tables/` and `figures/` again.

## Inputs still coming

| Issue | Due | Fallback text if it does not arrive |
|---|---|---|
| UFM-33 (the DevEval harness items) | done, merged from main 2026-11-26 | The 13 items are excluded (DevEval 846 items); methods 3.5 reports it with its date |
| UFM-35 (Qwen3.5 9B revises its first code block in image) | 2026-11-28 | Main analysis unchanged; drop the sensitivity todo in 4.1 and keep the limitation on the extraction rule |
| UFM-36 (CoderUJB Jsoup 93 fails our extraction) | 2026-11-28 | If excluded, CoderUJB goes to 135 items: merge main again and rebuild; no text edit, numbers are macros |
| UFM-34 (bonus: hand-read labels checked by a person) | 2026-11-28 | The hand read covers only Sonnet, labels unchecked |
| UFM-28 (bonus: transcription, reading versus programming) | cutoff 2026-11-28 | "Planned and not concluded", citing the 2026-11-23 deviation |

When main is merged, rerun the build: numbers, tables and figures follow the new results. Text
changes by hand only where a todo is.

## Open questions

- The appendix follows the references (NeurIPS convention); the body stands without it.
- The four exercise statements are not in the repo; sections follow the UFM-14 description.
- The style needs `[main,final]`: `final` alone leaves the footer text undefined. `main.tex`
  replaces the NeurIPS acceptance line with "Trabalho final de disciplina, PPGCC, UFMG, 2026."
- Truong and Koyejo 2026 has no first names or publisher in the notes, so the entry carries surnames
  only.

## Todo list as printed by the build (2026-11-26, all sections drafted, body ends on page 8)

```
TODO (13):
  sections/appendix.tex:9  Tabela A1: todos os desvios com data (tabela escrita à mão)
  sections/appendix.tex:16  legenda da Tabela A2a: gap por tamanho, pp, IC 95\% agrupado
  sections/appendix.tex:22  legenda da Tabela A2b: diferenças entre tamanhos, pp, IC 95\% agrupado
  sections/appendix.tex:39  Tabela A3: análises secundárias do plano, uma linha cada
  sections/appendix.tex:46  legenda da Tabela A4: Claude, exploratório
  sections/appendix.tex:50  figura do Claude
  sections/appendix.tex:55  Tabela A5: contaminação
  sections/limitations.tex:12  UFM-34: rótulos da leitura manual checados por pessoa
  sections/limitations.tex:14  UFM-28: leitura contra programação medida pela transcrição
  sections/limitations.tex:16  UFM-35: limitação da regra de extração, que corrige o primeiro bloco de código; o Qwen3.5 9B em imagem costuma revisar esse bloco
  sections/methods.tex:29  UFM-34: leitura manual com rótulos checados. Fallback: a leitura manual cobre só o Sonnet
  sections/methods.tex:30  UFM-28: transcrição, leitura contra programação. Fallback: planejado e não concluído, citando o desvio de 2026-11-23
  sections/results.tex:7  UFM-35: uma frase de sensibilidade do Qwen3.5 9B regravado com o último bloco de código, se chegar até 28/11; a análise principal não muda
```
