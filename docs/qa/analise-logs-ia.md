# Evidência — Análise de logs de CI com IA (Fase G)

Cobre parte do critério 13: usar IA para explicar logs de pelo menos duas
etapas do pipeline.

A CLI `run_devops_analysis.py` executa as etapas de **lint** e **testes**,
captura os logs e usa o Gemini para explicá-los (com fallback heurístico se o
LLM não estiver disponível).

## Como reproduzir

```
python run_devops_analysis.py
```

## Saída real (explicações geradas pela IA)

### Etapa 1 — lint (ruff), exit=0, explicado por: gemini
> A etapa de **lint (ruff)** **PASSOU** com sucesso, confirmado pelo código de
> saída (exit code = 0). O log "All checks passed!" indica que a análise
> estática executada pelo Ruff foi concluída sem identificar erros de sintaxe,
> violações de boas práticas ou problemas de formatação. A base de código está
> em conformidade com os padrões definidos, liberando o pipeline para avançar.

### Etapa 2 — testes (pytest), exit=0, explicado por: gemini
> A etapa de 'testes (pytest)' foi concluída com **sucesso (passou)**, com
> **exit code = 0**. O log indica que 100% da suíte foi executada, resultando em
> 35 testes aprovados e nenhuma falha. A execução levou ~0,36 s. Com a validação
> aprovada, o pipeline está liberado para prosseguir.

## Observações

- Foram explicadas **duas etapas** distintas do pipeline (lint e testes).
- A explicação é gerada pelo Gemini; se o LLM falhar, a CLI cai para uma
  explicação heurística determinística (o motor usado é impresso em cada etapa).
- O pipeline correspondente está em `.github/workflows/ci.yml` (lint + testes +
  validação de build).
