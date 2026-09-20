# `docs/method/` — o que as réguas LEEM

Nasceu em 20/09/2026, por ordem dela, escolhida entre três opções:

> *"Mover o que as réguas precisam"*

Ela recusou as outras duas com todas as letras, e as razões ficam aqui porque
elas são o contrato desta pasta:

| recusada | por quê |
| --- | --- |
| versionar `docs/process/` inteira | são 1.607 arquivos e **77 MB** de prosa; o repositório engordaria com texto que régua nenhuma lê |
| as réguas pularem sem a pasta | **régua que pula é régua que não mede** — a família de defeito que esta casa mais caçou em 2026 |

## A REGRA DE ENTRADA, e ela é uma só

**Um arquivo mora aqui quando código versionado o LÊ** — `open()`,
`read_text()`, um `Path` montado até ele. Ser citado em prosa não basta, e
citação não move arquivo: mover o que é só citado quebra a citação, que é o
defeito que esta pasta existe para não repetir.

O contrário também vale, e é o que a régua cobra: **nada que uma régua lê pode
morar em `docs/process/`**, porque aquela pasta é `.gitignore:178` — ela não
viaja no clone, não vem na worktree de agente, e some sem avisar.

## O QUE MEDIU A LISTA

Medido em 20/09/2026, num clone limpo feito com `git clone --local` (que, por
construção, não tem `docs/process/`):

| número | o que é |
| --- | --- |
| **136** | arquivos de teste que NOMEIAM `docs/process` |
| **28** | testes que REPROVAM num clone limpo |
| **7** | arquivos que esses 28 testes leem |

A distância entre 136 e 28 é o ponto inteiro: **quase toda menção é prosa**, e
prosa não quebra clone nenhum. Quem quebrava era um punhado de sete arquivos.

## OS SETE, e quem lê cada um

| arquivo | morava em | quem o lê |
| --- | --- | --- |
| `METODO-DE-ISOLAMENTO.md` | `docs/process/` | `scripts/check_paridade_transporte.py` (o caderno de ensaios) |
| `COMO-OLHAR-A-TELA.md` | `docs/process/` | `tests/unit/test_a_tabela_dos_scripts_de_tela.py` (a tabela dos scripts de tela) |
| `POLITICA-core-nunca-sai-da-maquina.md` | `docs/process/` | `tests/unit/test_radio_aberto_e7_e9.py` (E7) |
| `2026-08-29-A-REGUA-DE-TELA-como-se-prova-a-interface.md` | `docs/process/` | `scripts/regua_de_tela.py` e `scripts/check_regua_de_tela.py` |
| `2026-09-03-O-TERCEIRO-NUMERO-a-paridade-com-a-gtk.md` | `docs/process/` | `scripts/check_paridade_gtk_html.py` |
| `2026-09-07-O-COMO-DAS-21-o-gesto-exato-de-cada-linha.md` | `docs/process/sprints/arquivados/` | `scripts/mesa_de_medicao.py` (o gesto das 21) |
| `2026-09-07-O-COMO-DO-MAPA-o-gesto-das-178-celulas.md` | `docs/process/sprints/arquivados/` | `scripts/mesa_de_medicao.py` (o gesto das 178) |

Os dois últimos são a razão de a sprint existir. Eles foram arquivados junto
com 732 sprints fechadas, `_gesto_do_arquivo` devolveu `{}` **em silêncio**, e
as 199 células da mesa de medição voltaram a mostrar a procedência repetida —
o defeito que ela apontou em 07/09 olhando a linha 10: *"sinceramente não
entendi o que diabos é pra fazer aqui"*. Sete réguas ficaram vermelhas e
nenhuma sabia dizer por quê.

## O PONTEIRO no lugar antigo

`docs/process/` continua no disco dela e do André, e quem abrir o caminho
velho encontra uma folha de uma linha dizendo para onde o arquivo foi. Essa
folha **não viaja no git** — a pasta é ignorada —, então quem tem a pasta a
escreve com:

```bash
python3 scripts/apontar-o-dado-que-saiu-do-processo.py --escrever
```

Sem a pasta, o script diz que não há o que apontar e sai com `0`.

## AS RÉGUAS QUE SEGURAM ISTO

`tests/unit/test_o_dado_nao_mora_no_processo.py` cobra as três coisas:

1. os sete estão aqui e são **rastreados pelo git** — o `git ls-files` é o
   oráculo, não o disco;
2. esta página nomeia cada um, com o endereço velho e o leitor — um arquivo
   novo na pasta sem linha aqui reprova;
3. **nenhum módulo de `src/`, `scripts/` ou `tests/` lê a árvore real
   `docs/process/`**, salvo as ferramentas de processo declaradas com a razão
   (as que mexem nas sprints: o painel, o movedor, a colisão).
