# Evidência — Detecção de anomalia e estimativa de risco (Fase G)

Cobre parte do critério 13: detectar e explicar uma anomalia e produzir uma
estimativa simples de tendência ou risco de falha, com evidências e justificativa.

Os dados vêm dos sinais já produzidos pelo agente: métricas de latência
(`logs/metricas.jsonl`) e histórico de revisões (`data/historico.jsonl`).

## 1. Anomalia detectada — latência do nó `analisar_com_ia`

Saída real de `run_devops_analysis.py` (3 execuções analisadas):

```
── Detecção de anomalias (latência) ──
Execuções analisadas: 3
  analisar_com_ia: média=40070.67 ms, máx=60446.09 ms (3 exec.)
  notificar: média=161.49 ms, máx=484.36 ms (3 exec.)
  analisar_estatico: média=1.0 ms, máx=1.33 ms (3 exec.)
⚠️  2 anomalia(s) de latência (>= 10000 ms):
  run=9022698251b0 nó=analisar_com_ia latência=59105.61 ms
  run=546b1d3e9838 nó=analisar_com_ia latência=60446.09 ms
```

### Interpretação e justificativa
- O nó `analisar_com_ia` (chamada externa ao Gemini) tem latência média de
  **~40 s** e máxima de **~60 s**, contra **< 2 ms** dos nós determinísticos.
- Duas execuções ultrapassaram o limiar de anomalia (10 s), com ~59 s e ~60 s.
- **Causa provável:** a chamada ao modelo `gemini-3.6-flash` neste endpoint está
  consistentemente lenta (~1 min), dominando >99% do tempo total de execução.
- **Evidência correlacionada:** os `run_id` das anomalias permitem cruzar com
  `logs/agent.jsonl` para ver o evento do nó e eventuais fallbacks.
- **Mitigações já existentes:** `timeout=30s` e `max_retries=2` na chamada, com
  fallback para o motor mock — ver `docs/evidencias/observabilidade.md`.
- **Recomendação:** avaliar um modelo mais rápido, cache de resultados por
  hash do arquivo, ou execução assíncrona; monitorar via o limiar já definido.

## 2. Estimativa de tendência / risco

Saída real (arquivo `examples/exemplo_com_bugs.py`, 4 execuções no histórico):

```
── Estimativa de risco: examples/exemplo_com_bugs.py ──
Execuções no histórico: 4
Probabilidade de risco alto: 1.0
Tendência de achados: melhora
Risco estimado: ALTO
```

### Método (determinístico, documentado)
- **Probabilidade de risco alto** = (execuções com `nivel_risco == "alto"`) / total.
  Aqui: 4/4 = **1.0**.
- **Tendência de achados** = compara a média do nº de achados da primeira metade
  das execuções com a da segunda metade (`piora` / `melhora` / `estável`).
- **Classificação:** risco `alto` se `prob_risco_alto >= 0,5` ou tendência de
  `piora`; `medio` se houve algum risco alto; senão `baixo`.

### Interpretação
O arquivo é consistentemente de **risco alto** (contém credencial fixa e uso de
`eval`), por isso `prob_risco_alto = 1.0` e classificação **ALTO** — mesmo com a
tendência do nº de achados apontando leve `melhora`. A decisão prioriza a
severidade recorrente sobre a mera contagem.

## 3. Reprodução

```
# gera métricas/histórico executando o agente algumas vezes
python run_review.py examples/exemplo_com_bugs.py

# roda a análise (explica logs de 2 etapas, detecta anomalia, estima risco)
python run_devops_analysis.py examples/exemplo_com_bugs.py
```
