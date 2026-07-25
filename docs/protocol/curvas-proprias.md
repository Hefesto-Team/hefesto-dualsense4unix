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

## O que NÃO está aqui

As curvas dos doze modos "prontos" do DSX. Elas não foram copiadas, e a razão
está no `NOTICE`, seção "O que este projeto deliberadamente NÃO incorporou".

Se algum dia um valor desta tabela coincidir com um deles, será coincidência de
um espaço pequeno de possibilidades — o formato do report tem sete bytes e o
firmware do DualSense aceita uma faixa limitada. A defesa contra essa leitura
não é a diferença dos números: é o registro de que estes nasceram de medição
datada, com nome e nota de quem mediu.
