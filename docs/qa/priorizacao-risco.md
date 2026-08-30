# Priorização de testes por risco (Fase F)

Cobre parte do critério 12: selecionar e justificar pelo menos um teste ou
cenário prioritário com base em risco, impacto ou criticidade.

## Matriz de risco

| Cenário | Probabilidade de falha | Impacto se falhar | Risco |
|---------|------------------------|-------------------|-------|
| Defesa contra prompt injection / vazamento de segredo | Média | **Crítico** (segurança) | **Alto** |
| Gate de autonomia bloqueia envio externo sem aprovação | Baixa | Alto (ação indevida) | Médio-Alto |
| Fluxo do grafo (paralelização + consolidação) | Média | Alto (saída incorreta) | Médio-Alto |
| Recuperação de memória (comparação entre execuções) | Baixa | Médio | Médio |
| Formatação do relatório / estilo | Baixa | Baixo | Baixo |

## Teste prioritário escolhido

**`TestSeguranca` em `tests/test_agent_integration.py`** — especificamente:

- `test_prompt_injection_detectado_como_seguranca`
- `test_segredo_nao_vaza_no_relatorio`

### Justificativa

É o cenário de **maior impacto**: uma falha aqui significaria o agente obedecer
a instruções maliciosas embutidas no código ou expor um segredo no relatório —
uma violação de segurança direta. Diferente de um erro de formatação (impacto
baixo, facilmente percebido), uma falha de segurança é silenciosa e grave.

Por isso esse cenário é coberto em **duas camadas** e testado explicitamente:

1. Detecção determinística garante que a tentativa de injeção vire um achado de
   `seguranca`/`alta` mesmo se o LLM falhar ou cair em fallback.
2. Verificação de que o segredo (`admin123`) **não aparece** no relatório.

### Segundo cenário priorizado

`TestGovernanca.test_notificacao_pulada_sem_webhook` e o gate de aprovação:
garantem que uma **ação externa** (envio ao Discord) não ocorra sem condição
atendida. Impacto alto (ação indevida/irreversível), por isso testado logo
abaixo do bloco de segurança.

## Tipos de teste adicionados nesta fase

- **Integração** (`tests/test_agent_integration.py`): exercita o grafo completo
  com o motor mock, cobrindo os cenários acima.
- **E2E** (`tests/test_e2e.py`): executa o agente de ponta a ponta e valida os
  artefatos em disco (relatório, métricas, histórico, logs).

Ambos rodam de forma hermética (fixture `ambiente_isolado`), sem rede e sem
efeitos colaterais, adequados para o pipeline de CI (Fase G).
