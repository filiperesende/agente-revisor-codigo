# Evidência — Code review com IA (Fase F)

Cobre parte do critério 12: uso de IA para analisar alterações reais do projeto,
identificando problemas ou oportunidades de melhoria.

Usamos IA em code review de duas formas complementares: (A) o próprio agente
revisando código real do projeto (*dogfooding*) e (B) revisão assistida por IA
de alterações reais durante o desenvolvimento.

---

## A. Dogfooding — o agente revisando código do projeto

Rodamos o próprio Agente Revisor sobre um módulo real do repositório:

```
$ python run_review.py src/notificacao.py
🐛 Problemas encontrados: 1 (IA=0, estática=1)
   [BAIXA] linha 154: Linha com 102 caracteres excede o limite de 100.
📣 Notificação Discord: enviado (tentativas=1)
📊 run_id=546b1d3e9838 | latência total: 60935.02 ms (10 nós)
```

Leitura do resultado:

- A **análise estática** apontou uma linha acima de 100 caracteres — corrigida
  na sequência (quebra do dicionário de retorno em múltiplas linhas).
- O **Gemini** não encontrou problemas funcionais neste módulo (que já tem
  validação, timeout, retry e testes), o que é um resultado plausível para
  código maduro. A ausência de achados foi verificada criticamente, não aceita
  cegamente.
- A execução também evidenciou uma **latência anômala (~61 s)** dominada pela
  chamada ao LLM — insumo para a análise de anomalia da Fase G.

## B. Revisão assistida por IA de alterações reais

Durante o desenvolvimento, a revisão assistida por IA identificou problemas
reais em alterações do próprio projeto. Exemplos concretos (com correção):

### B.1. Métrica do nó de telemetria auto-excluída (Fase E)
- **Alteração revisada:** instrumentação de latência dos nós do grafo.
- **Problema identificado:** o nó `finalizar` fazia o *flush* das métricas e só
  então o decorator tentava registrar a própria latência — resultado: `finalizar`
  ficava de fora do resumo (contagem 11 em vez de 12) e o registro em memória
  vazava (nunca era removido).
- **Correção:** deixar o nó `finalizar` **sem** instrumentação (ele é o meta-nó
  de flush). Verificado: `total_nos` coerente e `_METRICAS` vazio ao final.

### B.2. Fallback silencioso do Gemini (Fase C)
- **Alteração revisada:** camada de LLM.
- **Problema identificado:** o agente caía sempre no mock. A investigação
  (capturando a exceção engolida) revelou duas causas: modelo `gemini-2.0-flash`
  descontinuado (404) e a resposta do modelo novo vindo como **lista de blocos**,
  incompatível com o parser que esperava string.
- **Correção:** modelo atualizado e configurável por `GEMINI_MODEL`; normalização
  do conteúdo (`_texto_da_resposta`). Resultado: análise real por IA funcionando.

### B.3. Caminho fixo impedia isolamento de testes (Fase F)
- **Alteração revisada:** módulo de memória persistente.
- **Problema identificado:** as funções usavam o caminho do histórico como
  *default argument*, fixado no import — impossível redirecionar para um diretório
  temporário nos testes.
- **Correção:** resolver o caminho em tempo de chamada (`caminho or ARQUIVO_HISTORICO`),
  permitindo a fixture `ambiente_isolado` isolar os artefatos de runtime.

---

## Conclusão

A IA foi usada tanto pela própria aplicação (dogfooding em código real) quanto
como apoio à revisão de alterações do projeto, com achados acionáveis e
efetivamente corrigidos. A priorização dos testes derivada desses riscos está
documentada em `docs/qa/priorizacao-risco.md`.
