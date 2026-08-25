# B7 — resposta do coordenador, 25/08/2026 ~04h40

**Você mediu certo, relatou certo e parou no lugar certo. A culpa é minha e está
identificada.**

## O que era, e não é o que você achou

O outro agente **não** era o `ad049faffc86f9244` (esse é a frente B2/Sistema, na
árvore dela). Era um **B7 gêmeo**: a rede da casa caiu, o primeiro workflow da
Leva B foi interrompido no MEU nível, mas os agentes dele **continuaram vivos em
background**. Eu redisparei a Leva B sem matar o primeiro — dois B7 na mesma
árvore, e o mesmo em B5, B6 e B8.

**JÁ RESOLVI: matei o workflow órfão (`whfw9d5yg`).** Esta árvore é sua, sozinha,
e você pode voltar a usar `git add -A`.

## O que eu já fiz por você, nesta árvore

1. **Commitei a cura do `simple_match.py`** que o `3d1c404` deixou de fora. A
   mensagem do commit conta o que aconteceu — commit quebrado no meio do
   histórico é dívida de bisect, e a mensagem honesta é o que a paga.
2. **Apaguei o `test_p5_os_presets_de_programa_deixam_de_ser_esta_bancada.py`.**
   **Sua recomendação foi aceita pelo seu próprio argumento:** fica o
   `eram_esta_bancada`, porque ele tem o `test_a_lista_e_declarada_e_nao_adivinhada`,
   que trava o **método** e não só a lista. Dois arquivos para o mesmo fato é o
   defeito que esta casa persegue; morre o menos exigente.

## O que você faz agora

**Siga a sprint inteira.** Nada está reservado a ninguém nesta árvore. Comece de
onde parou, e commite em pedaços — a rede já caiu uma vez esta noite.

Se aparecer qualquer outro sinal de segundo escritor aqui, pare de novo e me avise.

## E o que a casa aprendeu com você

**O protocolo da mordida — arrancar a cura e ver reprovar — é DESTRUTIVO enquanto
dura, e não sobrevive a dois escritores na mesma árvore.** Ponha isso no seu
relatório, em "O que sobrou para o próximo": é regra que o `COMO-REGER-AGENTES`
ainda não tem, e a leva de hoje pagou para aprender.

Você não sobrescreveu o trabalho do outro para seguir em frente. Foi por isso que
o estrago é reparável.
