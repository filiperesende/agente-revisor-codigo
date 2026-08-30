# Ciclos de refinamento (critério 15)

Registro de refinamentos relevantes feitos durante o desenvolvimento, no
formato **problema observado → alteração realizada → resultado obtido**, com as
evidências relacionadas.

---

## Refinamento 1 — Gemini caindo sempre no fallback (mock)

**Problema observado.**
Mesmo com `GOOGLE_API_KEY` configurada, o relatório sempre indicava
`motor de análise: mock (fallback após erro no Gemini)`. A análise por IA nunca
acontecia de verdade — os achados vinham só das heurísticas do mock, mais pobres
(descrições genéricas, sem entender o código).

**Investigação.**
A exceção da chamada ao Gemini estava sendo engolida pelo `try/except` do
fallback. Ao capturar e imprimir o erro real, apareceram **duas causas**:
1. O modelo `gemini-2.0-flash` foi **descontinuado** (HTTP 404 — a própria API
   sugeriu migrar para `gemini-3.6-flash`).
2. Mesmo trocando o modelo, o parser quebrava: o modelo novo retorna o conteúdo
   como **lista de blocos** (`[{"type": "text", "text": ...}]`) e o código
   esperava uma `str`, então `_extrair_json` falhava e caía no fallback.

**Alteração realizada.**
- Atualizei o modelo padrão para `gemini-3.6-flash` e o tornei **configurável
  por variável de ambiente** (`GEMINI_MODEL`) — também atende ao requisito 4.10.
- Adicionei `_texto_da_resposta`, que normaliza a resposta tanto para `str`
  quanto para lista de blocos.
- Passei a **registrar o fallback** como log estruturado (`fallback_llm`), para
  não voltar a falhar silenciosamente.

**Resultado obtido.**
A análise real por IA passou a funcionar (`motor de análise: gemini`), com
achados muito mais ricos (ex.: "o parâmetro `id` sobrescreve a função built-in
`id`"). Como efeito colateral positivo, a defesa contra **prompt injection**
ficou mais forte: o próprio Gemini passou a **reportar** as tentativas de injeção
como problema de segurança em vez de obedecê-las.

**Evidências.** `docs/evidencias/prompt-injection.md` (comportamento com o Gemini
real), `src/llm.py` (modelo configurável + normalização), commits da Fase C.

---

## Refinamento 2 — Métrica do nó de telemetria auto-excluída

**Problema observado.**
Ao instrumentar os nós do grafo para medir latência, o resumo de métricas
mostrava **11 nós** quando o esperado eram 12, e o registro em memória
(`_METRICAS`) **vazava** (o `run_id` nunca era removido).

**Investigação.**
O nó `finalizar` fazia o *flush* das métricas e **só depois** o decorator de
instrumentação tentava registrar a própria latência. Ou seja, o `finalizar`
media a si mesmo após já ter descarregado tudo — ficava de fora do resumo e
recriava a entrada em memória sem nunca liberá-la.

**Alteração realizada.**
Deixei o nó `finalizar` **sem instrumentação** (ele é o meta-nó de telemetria,
não deve se medir).

**Resultado obtido.**
Contagem de nós coerente e sem vazamento em memória (`_METRICAS` vazio ao final
da execução), confirmado por verificação direta.

**Evidências.** `docs/qa/code-review-ia.md` (seção B.1), `src/agent.py`.

---

## Como esses refinamentos foram encontrados

Ambos surgiram de **observabilidade e revisão crítica**: o refinamento 1 veio de
investigar por que o motor indicava fallback; o 2, de conferir criticamente o
resumo de métricas em vez de aceitá-lo. Isso reforça o valor dos sinais de
observabilidade (Fase E) como apoio ao próprio desenvolvimento.
