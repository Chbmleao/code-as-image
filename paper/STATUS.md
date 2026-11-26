# Paper status (UFM-14)

Second block, 2026-11-25. Related work, methods and results have prose and passed a fresh-context review. Spec:
`~/.claude/specs/paper.md`. Deadline 2026-11-30, body at most 8 pages (references and appendix
excluded), Portuguese, NeurIPS 2025 style with the `final` option.

## Sections

| Section | State |
|---|---|
| 2 Trabalhos relacionados, 3 Metodos | written; reviewed; fixes applied |
| 4 Resultados, captions of Fig. 1 to 3 and Tab. 1 | written; reviewed; fixes applied |
| Resumo, 1 Introducao, 5 Discussao, 6 Limitacoes, 7 Conclusao | skeleton only |
| Appendix | floats numbered A1, A2, ...; A1, A3, A5 and the captions still todo |

Page budget: the body already ends on page 7 with discussion, limitations and conclusion still
empty. The planned cuts (Fig. 3 to the appendix, Tab. 2 as prose, 4.6 to one paragraph, section 2
to one paragraph) will be needed.

Open: introduction, discussion, limitations, conclusion, abstract. Planned order from the spec: 26/11 methods, data, related work, results; 27/11
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
| UFM-33 (decision on the 12 DevEval harness items) | 2026-11-28 | The 12 items stay and count as failures, with an effect of about 1.4% of each DevEval gap |
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

## Todo list as printed by the build (2026-11-25, second block)

```
TODO (37):
  sections/abstract.tex:3  pergunta do estudo
  sections/abstract.tex:5  desenho: modelos, itens e condições
  sections/abstract.tex:7  gap médio com IC nos dois benchmarks
  sections/abstract.tex:9  faixa do gap por modelo e faixa da razão de tokens
  sections/abstract.tex:11  DP item:condição
  sections/abstract.tex:13  frase sobre o Claude, marcado como exploratório
  sections/appendix.tex:9  Tabela A1: todos os desvios com data (tabela escrita à mão)
  sections/appendix.tex:16  legenda da Tabela A2a: gap por tamanho, pp, IC 95\% agrupado
  sections/appendix.tex:22  legenda da Tabela A2b: diferenças entre tamanhos, pp, IC 95\% agrupado
  sections/appendix.tex:30  Tabela A3: análises secundárias do plano, uma linha cada
  sections/appendix.tex:37  legenda da Tabela A4: Claude, exploratório
  sections/appendix.tex:41  figura do Claude
  sections/appendix.tex:46  Tabela A5: contaminação
  sections/conclusion.tex:3  resposta em duas frases
  sections/conclusion.tex:5  trabalhos futuros
  sections/discussion.tex:5  evidências de validade e leitura causal
  sections/discussion.tex:7  Tabela 2: as 5 evidências de validade
  sections/discussion.tex:11  fonte como ameaça à validade
  sections/discussion.tex:15  contaminação e contraste pareado
  sections/discussion.tex:19  DIF: corrigir ou reportar
  sections/discussion.tex:23  previsões do teste de transferência
  sections/intro.tex:3  motivação e pergunta aberta
  sections/intro.tex:5  lacuna
  sections/intro.tex:7  o que fazemos
  sections/intro.tex:9  contribuições
  sections/limitations.tex:3  limitação 1: modelos
  sections/limitations.tex:5  limitação 2: um renderizador e a indentação
  sections/limitations.tex:7  limitação 3: sem baseline sem contexto
  sections/limitations.tex:9  limitação 4: contaminação e teto
  sections/limitations.tex:11  limitação 5: evidência por item e leitura contra programação
  sections/limitations.tex:12  UFM-34: rótulos da leitura manual checados por pessoa
  sections/limitations.tex:13  UFM-28: leitura contra programação medida pela transcrição
  sections/limitations.tex:15  limitação 6: itens e construto
  sections/limitations.tex:16  UFM-33: efeito dos 12 itens do DevEval
  sections/methods.tex:28  UFM-34: leitura manual com rótulos checados. Fallback: a leitura manual cobre só o Sonnet
  sections/methods.tex:29  UFM-28: transcrição, leitura contra programação. Fallback: planejado e não concluído, citando o desvio de 2026-11-23
  sections/methods.tex:31  UFM-33: decisão sobre os 12 itens do DevEval. Fallback: os 12 ficam e contam como falha, com efeito de cerca de 1,4 por cento
```
