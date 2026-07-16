# Agente Revisor de Código (LangGraph + Gemini)

Agente de IA que automatiza a **revisão de código-fonte**. Ele recebe um
arquivo de código, analisa em busca de problemas (bugs, segurança, performance
e estilo) e gera um **relatório estruturado em Markdown** com severidade,
localização e sugestão de correção para cada problema.

Projeto do Mini-Projeto Avaliativo — Módulo 2, disciplina *IA para DEVs*.

---

## Problema que resolve

Revisar código manualmente é lento e sujeito a esquecimentos. Este agente
automatiza uma primeira triagem: lê o arquivo, aplica uma análise consistente e
entrega um relatório pronto para o desenvolvedor, destacando o que é mais
crítico primeiro.

## Objetivo do agente

- **Entrada:** o caminho de um arquivo de código (ex.: `.py`, `.js`, `.java`).
- **Processo:** validação → leitura → montagem de contexto → análise por IA →
  geração e escrita do relatório.
- **Saída:** um relatório Markdown em `reports/` e um resumo no terminal.

## Por que é um agente

A solução tem **objetivo definido**, mantém **estado/memória** durante a
execução, **decide o fluxo** (segue ou aborta conforme a validação), usa
**ferramentas** (ler arquivo e escrever relatório) e produz uma **saída
estruturada** — as características de um agente.

---

## Fluxo com LangGraph

O agente é um `StateGraph` (grafo de estados). Cada nó é uma etapa; as arestas
ligam as etapas; e uma **aresta condicional** decide se o fluxo continua após a
validação.

```
        START
          │
          ▼
   validar_entrada ──(entrada inválida)──► END
          │
     (entrada válida)
          ▼
   preparar_contexto        (calcula linguagem, nº de linhas → memória)
          ▼
   analisar_codigo          (chama Gemini ou mock → achados estruturados)
          ▼
   gerar_relatorio          (monta o Markdown)
          ▼
   escrever_relatorio       (grava o arquivo em reports/)
          ▼
         END
```

| Nó | Responsabilidade | Ferramenta |
|----|------------------|-----------|
| `validar_entrada` | valida o caminho e lê o arquivo | leitura de arquivo |
| `preparar_contexto` | calcula metadados (memória da execução) | — |
| `analisar_codigo` | envia código ao LLM e normaliza a saída | LLM (Gemini/mock) |
| `gerar_relatorio` | monta o relatório em Markdown | — |
| `escrever_relatorio` | grava o relatório em disco | escrita de arquivo |

## Ferramenta utilizada

Duas ferramentas controladas (em `src/tools.py`):

1. **Leitura de arquivo de código** — valida extensão permitida, tamanho máximo
   (100 KB) e se o arquivo não está vazio antes de ler.
2. **Escrita de relatório** — grava o Markdown apenas dentro de `reports/`, com
   proteção contra *path traversal* (usa somente o nome base do arquivo).

## Contexto / memória

O estado compartilhado (`src/state.py`) funciona como memória da execução: ele
acumula o código lido, os metadados calculados (linguagem, nº de linhas), o
motor de análise usado e os achados. Cada nó lê e enriquece esse estado, que é
passado adiante até a geração do relatório.

## Validações

- **Entrada:** caminho não vazio, arquivo existente, extensão permitida,
  tamanho dentro do limite, conteúdo não vazio e UTF-8 válido.
- **Saída do LLM:** a resposta é normalizada (`src/validation.py`) — itens fora
  do formato são descartados e severidades inválidas viram `baixa`, evitando
  que um retorno malformado quebre o relatório.

---

## Como executar

Pré-requisitos: **Python 3.10+** (o projeto foi construído com 3.12).

```bash
# 1. Criar e ativar o ambiente virtual
python3 -m venv .venv
source .venv/bin/activate          # Windows: .venv\Scripts\activate

# 2. Instalar as dependências
pip install -r requirements.txt

# 3. (Opcional) Configurar a chave do Gemini
cp .env.example .env
# edite o .env e coloque sua GOOGLE_API_KEY

# 4. Rodar o agente sobre um arquivo
python run_review.py examples/exemplo_com_bugs.py
```

> Sem a chave do Gemini, o agente roda em **modo mock** (análise por
> heurísticas), então funciona mesmo offline. Com a chave, usa o Gemini real.

## Testes

Os testes cobrem as validações (`src/validation.py`) e as ferramentas
(`src/tools.py`), incluindo os limites de segurança (extensão, tamanho e
proteção contra *path traversal*). Não dependem de chave de API nem de rede.

```bash
# com o ambiente virtual ativo e as dependências instaladas
pytest
```

## Exemplo de entrada

`examples/exemplo_com_bugs.py` (trecho):

```python
API_KEY = "sk-1234567890abcdef"   # credencial fixa

def processar(entrada):
    try:
        resultado = eval(entrada)  # uso perigoso de eval
        print(resultado)
        return resultado
    except:                        # except genérico
        pass
```

## Exemplo de saída

Resumo no terminal:

```
🔎 Revisando: examples/exemplo_com_bugs.py
⚙️  Motor de análise: Mock (heurístico, sem chave)
📄 Linguagem: Python
📏 Linhas: 29
🐛 Problemas encontrados: 6
   [ALTA] linha 3: Possível credencial fixa no código (hardcoded).
   [ALTA] linha 19: Uso de eval() pode executar código arbitrário.
   [MEDIA] linha 22: Bloco except genérico captura todos os erros silenciosamente.
   ...
✅ Relatório salvo em: reports/review-exemplo_com_bugs-AAAAMMDD-HHMMSS.md
```

O relatório em Markdown lista cada problema com severidade, categoria, linha,
descrição e sugestão, ordenado da maior para a menor severidade.

---

## Estrutura do projeto

```
agente-revisor-codigo/
├── run_review.py            # CLI: ponto de entrada
├── requirements.txt
├── conftest.py              # permite os testes importarem o pacote src
├── .env.example             # nomes das variáveis (sem valores)
├── .gitignore               # ignora .env, .venv, reports/
├── README.md
├── src/
│   ├── state.py             # estado compartilhado (memória)
│   ├── tools.py             # ferramentas: ler arquivo / escrever relatório
│   ├── llm.py               # Gemini + fallback mock
│   ├── validation.py        # validação de entrada e saída
│   ├── nodes.py             # nós do grafo
│   ├── agent.py             # montagem do StateGraph
│   └── prompts/
│       └── revisao_codigo.md
├── examples/
│   └── exemplo_com_bugs.py  # entrada de demonstração
├── tests/
│   ├── test_validation.py   # testes das validações
│   └── test_tools.py        # testes das ferramentas
├── docs/
│   ├── prompts.md           # prompts usados no desenvolvimento
│   └── apresentacao.md      # roteiro dos 2 slides
└── reports/                 # relatórios gerados (não versionado)
```

## Decisões principais

- **LangGraph com aresta condicional** para separar validação do processamento
  e permitir abortar cedo em entradas inválidas.
- **Fallback mock** para o LLM: garante que o agente seja demonstrável sem
  chave de API e torna os testes determinísticos.
- **Ferramentas com sandbox:** leitura restrita por extensão/tamanho e escrita
  restrita ao diretório `reports/`.
- **Segredos fora do código:** a chave é lida apenas de variáveis de ambiente;
  `.env` está no `.gitignore` e só o `.env.example` é versionado.

## Segurança

- Nenhuma chave, token ou segredo é versionado.
- `.gitignore` cobre `.env`, `.venv/` e `reports/`.
- `.env.example` contém apenas os **nomes** das variáveis, sem valores.
- As ferramentas limitam as ações possíveis (extensões, tamanho, diretório).

## Limitações

- O modo mock detecta apenas padrões simples via regex; a análise profunda
  depende do Gemini.
- Revisa um arquivo por vez (não percorre diretórios).
- Não executa o código analisado — a revisão é estática.
