# Prompts utilizados

Este arquivo registra os principais prompts usados no projeto — tanto o prompt
que o **agente envia ao LLM** em tempo de execução quanto os prompts usados
para **planejar, implementar e refinar** a solução com apoio de IA.

---

## 1. Prompt de execução do agente (enviado ao Gemini)

Fica em `src/prompts/revisao_codigo.md` e é carregado em tempo de execução.
Os campos entre chaves são preenchidos com o contexto da execução.

```
Você é um revisor de código sênior. Analise o código-fonte fornecido e
identifique problemas objetivos.

Linguagem do arquivo: {linguagem}
Arquivo: {caminho}
Total de linhas: {total_linhas}

Considere as seguintes categorias de problemas:
- "bug": erros de lógica, exceções não tratadas, valores incorretos
- "seguranca": exposição de segredos, injeção, validação ausente
- "performance": operações ineficientes, laços desnecessários
- "estilo": nomes ruins, código morto, falta de clareza

Regras de resposta:
- Responda SOMENTE com um array JSON válido, sem texto antes ou depois.
- Cada item do array deve ter exatamente as chaves:
  "severidade" (alta|media|baixa), "categoria", "linha", "descricao", "sugestao".
- Se não houver problemas, responda com um array vazio: []
- Seja específico e acionável na "sugestao".

Código a revisar:
​```
{codigo}
​```
```

**Por que assim:** pedir JSON estruturado com chaves fixas permite validar e
transformar a resposta em relatório de forma confiável, em vez de depender de
texto livre.

---

## 2. Prompts de planejamento e implementação (desenvolvimento)

Prompts usados durante a construção do projeto com apoio de IA.

### 2.1. Definição da arquitetura

```
Quero um agente em LangGraph que revise um arquivo de código e gere um
relatório. Sugira uma divisão em nós (StateGraph) com estado compartilhado,
pelo menos uma ferramenta integrada, uso de contexto/memória e uma aresta
condicional para validação de entrada.
```

### 2.2. Implementação das ferramentas

```
Implemente duas ferramentas em Python: uma para ler um arquivo de código com
validação de extensão e tamanho máximo, e outra para escrever um relatório
Markdown apenas dentro de uma pasta reports/, com proteção contra path
traversal. Levante um erro controlado em condições inválidas.
```

### 2.3. Integração do LLM com fallback

```
Implemente uma camada de LLM que use o Google Gemini via langchain-google-genai
quando houver GOOGLE_API_KEY no ambiente, e caia para um cliente mock baseado
em regex quando não houver chave. A resposta do modelo deve ser um array JSON;
faça uma extração tolerante a texto extra e a cercas de código markdown.
```

### 2.4. Validação e robustez

```
Adicione validação da entrada (caminho, existência, extensão, tamanho) e
normalização da saída do LLM (descartar itens malformados e corrigir
severidades inválidas) para o agente não quebrar com dados inesperados.
```

### 2.5. Refino do relatório

```
Gere o relatório em Markdown com um resumo (contagem por severidade) e a lista
de problemas ordenada da maior para a menor severidade, cada um com linha,
descrição e sugestão.
```
