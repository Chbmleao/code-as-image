# Paper status (UFM-14)

Skeleton block, 2026-11-25. The paper compiles; no section has prose yet. Spec:
`~/.claude/specs/paper.md`. Deadline 2026-11-30, body at most 8 pages (references and appendix
excluded), Portuguese, NeurIPS 2025 style with the `final` option.

## Sections

| Section | State |
|---|---|
| Resumo, 1 Introducao, 2 Trabalhos relacionados, 3 Metodos, 4 Resultados, 5 Discussao, 6 Limitacoes, 7 Conclusao | skeleton: headings, outline lines as comments, one todo each |
| Appendix A1 to A5 | skeleton; A2 (sizes, size differences) and A4 (Claude) tables are generated |
| Figures 1 to 3, Table 1 | generated (`figures/`, `tables/tab_gaps.tex`), captions are todos |
| Table 2 (validity evidence), Table A1 (deviations), A3, A5 | written by hand later, todos in the section files |

Open: all prose. Planned order from the spec: 26/11 methods, data, related work, results; 27/11
discussion, limitations, conclusion, abstract; 28/11 the three issues below and the merge of
origin/main (ask first); 29/11 page limit, fresh-context review, final read; 30/11 delivery.

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

## Todo list as printed by the build (2026-11-25)

```
TODO (60):
  sections/abstract.tex:3  pergunta do estudo
  sections/abstract.tex:5  desenho: modelos, itens e condições
  sections/abstract.tex:7  gap médio com IC nos dois benchmarks
  sections/abstract.tex:9  faixa do gap por modelo e faixa da razão de tokens
  sections/abstract.tex:11  DP item:condição
  sections/abstract.tex:13  frase sobre o Claude, marcado como exploratório
  sections/appendix.tex:4  Tabela A1: todos os desvios com data (tabela escrita à mão)
  sections/appendix.tex:11  legenda da Tabela A2a: gap por tamanho, pp, IC 95\% agrupado
  sections/appendix.tex:17  legenda da Tabela A2b: diferenças entre tamanhos, pp, IC 95\% agrupado
  sections/appendix.tex:25  Tabela A3: análises secundárias do plano, uma linha cada
  sections/appendix.tex:32  legenda da Tabela A4: Claude, exploratório
  sections/appendix.tex:36  figura do Claude
  sections/appendix.tex:41  Tabela A5: contaminação
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
  sections/methods.tex:5  CoderUJB, DevEval, filtros e licenças
  sections/methods.tex:9  modelos, renderização e execuções
  sections/methods.tex:13  construto e estimando
  sections/methods.tex:17  intervalos, Holm e média dos modelos
  sections/methods.tex:19  GLMM, checagens de uma habilidade, contaminação e confiabilidade
  sections/methods.tex:23  desvios principais com data, e remissão à Tabela A1
  sections/methods.tex:24  UFM-33: decisão sobre os 12 itens do DevEval. Fallback: os 12 ficam e contam como falha, com efeito de cerca de 1,4 por cento
  sections/methods.tex:25  UFM-34: leitura manual com rótulos checados. Fallback: a leitura manual cobre só o Sonnet
  sections/methods.tex:26  UFM-28: transcrição, leitura contra programação. Fallback: planejado e não concluído, citando o desvio de 2026-11-23
  sections/related.tex:3  texto renderizado em VLMs
  sections/related.tex:5  compressão por imagem e código
  sections/related.tex:7  estatística de avaliação
  sections/results.tex:5  gaps por modelo, IC e maior p de Holm
  sections/results.tex:7  leitura da Tabela 1
  sections/results.tex:9  piso e leave-one-project-out
  sections/results.tex:14  legenda da Figura 1: gap imagem menos texto por modelo aberto e média dos modelos, IC 95\% agrupado por projeto
  sections/results.tex:20  legenda da Tabela 1
  sections/results.tex:27  efeito do tamanho da fonte e economia de tokens
  sections/results.tex:32  legenda da Figura 2: gap por tamanho contra a razão de tokens por tamanho, uma linha por modelo
  sections/results.tex:38  Wald, DP item:condição, LRT e fora da amostra
  sections/results.tex:40  correlações, inclinação comum, probit, BH e limite de 5 modelos
  sections/results.tex:45  legenda da Figura 3: correlação texto x imagem por tamanho contra a faixa de referência
  sections/results.tex:51  confiabilidade, G finito e troca de ordem
  sections/results.tex:55  contaminação: cópias, encolhimento, controle, itens marcados e flags
  sections/results.tex:59  Claude, exploratório
  sections/results.tex:61  bloco 1, exploratório
```

## Build

```
uv run python paper/build.py           # numbers, figures, tectonic, checks
uv run python paper/build.py --final   # also fails on any todo, undefined ref, body past page 8
uv run pytest tests/test_paper.py
```

`build.py` runs `build_numbers.py` (`numbers.tex`, `tables/*.tex`) and `build_figures.py`
(`figures/*.pdf`), compiles with `/opt/homebrew/bin/tectonic` into `paper/out/` (the PDF is
`paper/out/paper.pdf`, not in git) and prints the todo list, undefined references and the page where
`\label{body-end}` falls. The first tectonic run downloads its bundle and needs the network. Each
generator takes `--out DIR` (default `paper/`). A macro that cannot be read from its source, or a
prose predicate that stopped holding, stops `build_numbers.py` and names it. Macros are used as
`\gapQwenTwentySevenDev{}` (they end in `\xspace`); intervals are `\ci{\gapXLo}{\gapXHi}`.
