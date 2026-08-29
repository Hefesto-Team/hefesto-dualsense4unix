# Curvas próprias — registro de proveniência

Este arquivo é o registro de origem de **cada valor de curva de gatilho criado
pelo Hefesto**. Ele existe por causa do processo de sala limpa
([CLEAN-ROOM.md](../process/CLEAN-ROOM.md), regra R3): o dado e a origem nunca
se separam.

> **Vazio, e agora vazio de vez — nota datada de 29/08/2026, grau: DECISÃO DELA.**
> Esta tabela seria preenchida pela corrente `CR-03 → CR-04 → CR-06`, e a corrente
> **saiu do disco** (`docs/data/decisoes-dela.csv`, `D-A-CORRENTE-DO-CLEAN-ROOM-SAI`):
> sem a bancada de medir não há efeitos da casa, e sem eles não há o que devolver ao
> ecossistema. O Hefesto vive com o catálogo de efeitos que já tem. Para onde foram
> as três, veja
> [o manifesto do corte](../process/sprints/2026-08-29-O-CORTE-DO-CLEAN-ROOM-o-que-saiu-e-por-que.md).
>
> **O arquivo fica, e não é por respeito ao passado.** Ele é a entrega da regra **R3**
> do [processo de sala limpa](../process/CLEAN-ROOM.md) — *o dado e a origem nunca se
> separam* —, e essa regra segue normativa: a posição jurídica e o formato que recusa
> foram entregues, e `profiles/curva_propria.py` continua reprovando efeito sem
> `medido_por`, `controle` ou `nota`. No dia em que alguém medir uma curva própria —
> por bancada, por script ou à mão —, o registro dela é aqui, e o portão que mantém a
> tabela honesta já está de pé.

**Atualização de 2026-07-31 — o formato já existe, e ele recusa.** A
[CR-02](../process/sprints/2026-07-25-CR-02-formato-e-proveniencia.md) foi
entregue: `profiles/curva_propria.py` define `CurvaPropria`, e um efeito com
`medido_por`, `controle` ou `nota` vazios **não instancia** — levanta erro, não
aviso. A tabela da seção "Efeitos" sai da função `gerar_tabela_markdown`, a
partir do catálogo, e não da mão de ninguém.

Quem **preenche**, agora que a bancada não vem: ninguém, por enquanto — e a ausência
de atalho continua sendo o produto. A R3 proíbe valor sem quem sentiu; um número sem
mão e sem sensação entraria com `Medido por`, `Controle` e `Nota` preenchidos com
ficção, contaminando a defesa da tabela inteira. Quem medir a primeira curva escreve
no catálogo (`docs/data/curvas-proprias.json`) e roda o gerador: a tabela sai sozinha.

## Como ler esta tabela

| Campo | O que significa |
|---|---|
| **Nome** | o nome do efeito, em português (regra R2 — nunca os nomes do DSX) |
| **Medido por / em** | quem sentou com o controle e quando |
| **Controle** | modelo e transporte — a resposta varia entre aparelhos |
| **Nota** | o que a pessoa sentiu e por que parou naqueles valores |
| **Curva** | os bytes efetivamente enviados |

## Efeitos

A tabela abaixo é **gerada** do catálogo (`docs/data/curvas-proprias.json`) por
`scripts/gerar-tabela-de-curvas.py`, que chama `gerar_tabela_markdown` — a
função que a CR-02 escreveu para este fim e que, MEDIDO em 12/08/2026, ninguém
chamava. O `--check` do gerador reprova quando o publicado deixa de ser o que o
catálogo produz. Não a edite à mão: essa foi a proibição da CR-02, e ela só
passou a valer no dia em que este chamador nasceu.

<!-- BLOCO GERADO por scripts/gerar-tabela-de-curvas.py — não edite à mão -->

_(nenhum ainda — ver CR-04)_

<!-- FIM DO BLOCO GERADO -->

## Sob que licença estas curvas saem

**CC0-1.0** — domínio público, sem exigência de crédito.

**Grau: DECISÃO DELA**, 07/08/2026. A pergunta estava aberta desde 25/07 na CR-06 —
a sprint de publicação, cortada em 29/08 —, e a resposta separa as duas coisas de
propósito: o **código** é MIT, os **dados medidos** são CC0.

O motivo é o objetivo declarado da própria CR-06 — que a curva seja **adotada**.
Exigir crédito num número medido cria uma dúvida ("dado factual tem autoria?")
que só serve para fazer o outro projeto reescrever a medição em vez de usar a
nossa. O registro de procedência continua aqui, e é ele que responde a pergunta
de onde o número veio; a licença não precisa carregar esse peso.

Ver o `NOTICE`, seção "A LICENÇA DAS CURVAS PRÓPRIAS".

## O que NÃO está aqui

As curvas dos doze modos "prontos" do DSX. Elas não foram copiadas, e a razão
está no `NOTICE`, seção "O que este projeto deliberadamente NÃO incorporou".

Se algum dia um valor desta tabela coincidir com um deles, será coincidência de
um espaço pequeno de possibilidades — o formato do report tem sete bytes e o
firmware do DualSense aceita uma faixa limitada. A defesa contra essa leitura
não é a diferença dos números: é o registro de que estes nasceram de medição
datada, com nome e nota de quem mediu.
