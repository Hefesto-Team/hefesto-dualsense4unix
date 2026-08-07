# Curvas próprias — registro de proveniência

Este arquivo é o registro de origem de **cada valor de curva de gatilho criado
pelo Hefesto**. Ele existe por causa do processo de sala limpa
([CLEAN-ROOM.md](../process/CLEAN-ROOM.md), regra R3): o dado e a origem nunca
se separam.

> **Ainda vazio, e isso é proposital.** A tabela abaixo será preenchida a partir
> da sprint [CR-04](../process/sprints/2026-07-25-CR-04-os-efeitos-da-casa.md),
> e será **gerada dos perfis**, não escrita à mão (CR-02). Um registro mantido
> manualmente desatualiza, e um registro desatualizado não defende ninguém.
>
> Este arquivo nascer antes dos dados é parte do ponto: a estrutura de
> proveniência precede o primeiro valor.

**Atualização de 2026-07-31 — o formato já existe, e ele recusa.** A
[CR-02](../process/sprints/2026-07-25-CR-02-formato-e-proveniencia.md) foi
entregue: `profiles/curva_propria.py` define `CurvaPropria`, e um efeito com
`medido_por`, `controle` ou `nota` vazios **não instancia** — levanta erro, não
aviso. A tabela da seção "Efeitos" sai da função `gerar_tabela_markdown`, a
partir do catálogo, e não da mão de ninguém.

Quem vai **preencher** esta tabela é a bancada de medição
([CR-03](../process/sprints/2026-07-25-CR-03-bancada-de-medicao.md)), com a
mantenedora sentindo o gatilho e nomeando o efeito
([CR-04](../process/sprints/2026-07-25-CR-04-os-efeitos-da-casa.md)). Não há
atalho por aqui, e a ausência de atalho é o produto: a regra R3 proíbe valor sem
quem sentiu, e um número que não tem mão nem sensação entraria com os campos
`Medido por`, `Controle` e `Nota` preenchidos com ficção — contaminando a defesa
da tabela inteira, pela regra que o próprio processo escreveu.

## Como ler esta tabela

| Campo | O que significa |
|---|---|
| **Nome** | o nome do efeito, em português (regra R2 — nunca os nomes do DSX) |
| **Medido por / em** | quem sentou com o controle e quando |
| **Controle** | modelo e transporte — a resposta varia entre aparelhos |
| **Nota** | o que a pessoa sentiu e por que parou naqueles valores |
| **Curva** | os bytes efetivamente enviados |

## Efeitos

_(nenhum ainda — ver CR-04)_

## Sob que licença estas curvas saem

**CC0-1.0** — domínio público, sem exigência de crédito.

**Grau: DECISÃO DELA**, 07/08/2026. A pergunta estava aberta desde 25/07 na
[CR-06](../process/sprints/2026-07-25-CR-06-devolver-ao-ecossistema.md), e a
resposta separa as duas coisas de propósito: o **código** é MIT, os **dados
medidos** são CC0.

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
