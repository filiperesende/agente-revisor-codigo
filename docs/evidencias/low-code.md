# Evidência — Automação low-code/no-code com n8n (Fase H)

Cobre o critério 14: automação low-code integrada à solução, com gatilho,
integração com a aplicação, saída observável e instruções de reprodução.

## Visão geral

Fluxo visual no **n8n** que executa uma revisão agendada e alerta no Discord
quando o risco é alto. A **lógica principal permanece na aplicação** (o agente
LangGraph); o n8n apenas **orquestra**: dispara a execução, interpreta a saída e
roteia o alerta.

```
[Agenda diária 09h]  →  [Execute Command: run_review --json]
        →  [Parse JSON]  →  [IF risco == "alto"]  →  [HTTP POST no Discord]
   (gatilho)              (integração com a app)      (decisão)   (saída observável)
```

- **Gatilho:** Schedule Trigger (diário). Pode ser executado manualmente no n8n
  para demonstração.
- **Integração com a aplicação:** nó *Execute Command* roda
  `python run_review.py examples/exemplo_com_bugs.py --json`, ou seja, executa o
  próprio agente e captura a saída JSON.
- **Saída observável:** o n8n publica uma mensagem no canal do Discord quando o
  nível de risco é alto.

O arquivo do workflow está em `automacao/n8n-workflow-revisao.json` (importável).

## Pré-requisitos

O nó *Execute Command* roda no ambiente onde o n8n está instalado. Para que ele
enxergue este projeto e o `.venv`, a forma mais simples é rodar o n8n
**localmente na mesma máquina** (não em contêiner isolado):

```bash
npx n8n            # sobe o n8n em http://localhost:5678
```

> Observação sobre Docker: se rodar o n8n em contêiner, o *Execute Command* roda
> DENTRO do contêiner e não terá acesso ao projeto/venv do host. Nesse caso é
> preciso montar o projeto como volume e ter Python no contêiner. Por
> simplicidade, recomenda-se `npx n8n` no host para esta automação.

## Como reproduzir

1. Suba o n8n: `npx n8n` e abra `http://localhost:5678`.
2. Importe o workflow: menu **⋮ → Import from File** e selecione
   `automacao/n8n-workflow-revisao.json`.
3. Ajuste dois valores:
   - No nó **Rodar Agente Revisor**, troque `/CAMINHO/ABSOLUTO/DO/PROJETO` pelo
     caminho real deste repositório.
   - No nó **Alerta no Discord**, cole a URL do seu webhook do Discord no campo
     `url`.
4. Clique em **Execute Workflow** (ou aguarde o horário agendado).
5. Resultado esperado: como `exemplo_com_bugs.py` é de risco alto, o n8n publica
   um alerta no canal do Discord com o arquivo, o total de achados e o caminho
   do relatório.

## Construção manual (caso o import apresente incompatibilidade de versão)

O n8n muda o schema entre versões; se o import falhar, recrie o fluxo com 5 nós:

1. **Schedule Trigger** — intervalo diário.
2. **Execute Command** — comando:
   `cd /CAMINHO/DO/PROJETO && .venv/bin/python run_review.py examples/exemplo_com_bugs.py --json`
3. **Code** (JavaScript):
   `return [{ json: JSON.parse($input.first().json.stdout) }];`
4. **IF** — condição: `{{ $json.nivel_risco }}` **equals** `alto`.
5. **HTTP Request** — POST para a URL do webhook do Discord, corpo JSON:
   `{{ JSON.stringify({ content: '🔔 [n8n] RISCO ALTO em ' + $json.arquivo }) }}`
   Ligue a saída **true** do IF a este nó.

## Evidência da execução

> Substituir pelos artefatos após executar:
> - Print do canvas do workflow no n8n (execução verde).
> - Print da mensagem recebida no canal do Discord.

## Relação com a governança

Neste fluxo o agente roda sem `--aprovar`; como o arquivo é de risco alto, o
próprio agente **não** envia a notificação (gate de aprovação humana — Fase C).
Quem publica o alerta é o n8n, deixando claro que a decisão de notificar partiu
da automação, e não da execução autônoma do agente.
