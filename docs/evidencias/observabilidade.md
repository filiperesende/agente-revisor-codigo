# Evidência — Observabilidade e resiliência (Fase E)

Cobre o critério 11: dois sinais de observabilidade correlacionados e tratamento
de falhas nas integrações.

## 1. Os dois sinais (correlacionados por `run_id`)

Cada execução recebe um `run_id` único, propagado pelo estado do grafo. Os dois
sinais compartilham esse identificador, permitindo reconstruir a execução:

1. **Logs estruturados (JSON)** — `logs/agent.jsonl`. Um evento por linha, com
   `timestamp`, `run_id`, `nivel`, `no`, `evento` e campos extras (`latencia_ms`,
   `erro`, etc.). Emitidos por um decorator que instrumenta cada nó (eventos
   `inicio`/`fim`/`erro`).
2. **Métricas de latência** — `logs/metricas.jsonl`. Uma linha por execução, com
   a latência de cada nó e o total.

Ambos são gerados em `src/observability.py` e ligados ao grafo em `src/agent.py`.

## 2. Como investigar uma execução

O `run_id` aparece no fim da saída da CLI:

```
📊 run_id=9022698251b0 | latência total: 59108.42 ms (11 nós) | logs: logs/agent.jsonl
```

Com ele, filtra-se tudo o que aconteceu naquela execução:

```
grep 9022698251b0 logs/agent.jsonl      # sequência de nós, decisões e erros
grep 9022698251b0 logs/metricas.jsonl   # latência por nó
```

## 3. Execução investigada (run_id 9022698251b0)

Arquivo: `examples/exemplo_com_bugs.py`. Latência por nó (resumo de métricas):

| Nó | Latência (ms) |
|----|---------------|
| validar_entrada | 0.49 |
| preparar_contexto | 0.07 |
| recuperar_memoria | 0.21 |
| analisar_estatico | 0.87 |
| **analisar_com_ia** | **59105.61** |
| consolidar_achados | 0.28 |
| ... (demais nós) | < 1 cada |
| **total** | **59108.42** |

Leitura: o fluxo executou de ponta a ponta, com decisão de priorização (risco
alto) registrada nos logs. **A latência é totalmente dominada pelo nó
`analisar_com_ia`** (a chamada externa ao Gemini): ~59 s de ~59,1 s totais. Os
nós determinísticos custam menos de 1 ms cada.

Essa latência de ~59 s é **anômala** para uma análise de arquivo pequeno e será
tratada na Fase G (detecção de anomalia + estimativa de risco), usando o
histórico de métricas como base.

## 4. Tratamento de falhas (resiliência)

- **LLM (`src/llm.py`)**: a chamada ao Gemini usa `timeout=30s` e `max_retries=2`.
  Se ainda assim falhar, há **fallback** automático para o motor mock (heurístico),
  e o evento é registrado como log estruturado:

  ```json
  {"run_id":"...","nivel":"WARNING","no":"analisar_com_ia","evento":"fallback_llm",
   "erro":"...","motor":"mock"}
  ```

  Assim, uma falha do provedor externo não interrompe o agente e fica rastreável.
- **Notificação externa (`src/notificacao.py`)**: `timeout` por requisição e
  `retry` limitado com backoff, re-tentando apenas em erros transitórios (429/5xx).
- **Escrita de histórico/relatório**: falhas de I/O são capturadas e logadas sem
  derrubar o fluxo.

## 5. Observação

Os arquivos em `logs/` e `data/` são dados de runtime e não são versionados
(estão no `.gitignore`). Para reproduzir, basta executar o agente uma vez:
`python run_review.py examples/exemplo_com_bugs.py`.
