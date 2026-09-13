---
sprint: FRASES-E-DICAS-03
estado: feita
onda: A-TERCEIRA-LISTA-DELA
posse:
  FRASES-E-DICAS-03:
    - src/hefesto_dualsense4unix/interface/pacotes/a08_conexoes.py
    - src/hefesto_dualsense4unix/app/actions/config/secao_controles.py
    - src/hefesto_dualsense4unix/interface/pacotes/a03_gatilhos.py
    - src/hefesto_dualsense4unix/interface/pacotes/a04_iluminacao.py
    - src/hefesto_dualsense4unix/app/actions/emulation_actions.py
    - tests/unit/test_a_luz_nao_acende_o_botao_do_card.py
    - tests/unit/test_steam_input_d33_nomeia_o_jogo.py
    - tests/unit/test_nenhuma_frase_de_aviso_chega_a_tela.py
    - docs/process/sprints/2026-09-13-FRASES-E-DICAS-03-a-razao-do-nascimento-o-chip-de-dois-donos-e-o-sufixo-do-steam-input.md
cria:
  - tests/unit/test_o_chip_do_perfil_tem_um_dono_so.py
bancada: false
depois_de: []
nao_toca:
  - src/hefesto_dualsense4unix/interface/hefesto_vivo.py
  - src/hefesto_dualsense4unix/interface/topo.html
  - src/hefesto_dualsense4unix/interface/aba04.py
  - src/hefesto_dualsense4unix/interface/pacotes/a02_controles.py
  - src/hefesto_dualsense4unix/interface/pacotes/a09_sistema.py
  - docs/data/paridade-gtk-html.csv
---

# FRASES-E-DICAS-03 — a razão do nascimento, o chip de dois donos e o sufixo do Steam Input

> **ESTADO 2026-09-13: feita** — a dica do «A luz não acende» diz só o que o botão faz, o chip «Perfil ativo» tem um dono só e diz o mesmo nome nas dez abas, e o sufixo das exceções do Steam Input conta sem narrar. Sem página regerada e sem botão novo. [A entrega](../agentes/2026-09-13/FRASES-E-DICAS-03-opus.md)

Nasceu na costura da onda 1 (13/09/2026). São três achados que as validações
deixaram abertos só por posse. A palavra dela e a regra estão na
[FRASES-E-DICAS-01](2026-09-13-FRASES-E-DICAS-01-toda-frase-de-aviso-que-ainda-chega-a-tela.md)
e no [índice](2026-09-13-A-TERCEIRA-LISTA-DELA-INDICE.md).

## §E — O que ainda chega à tela

| onde | o que chega | quem escreve | quem achou |
| --- | --- | --- | --- |
| 08, a dica do «A luz não acende» | depois do que o botão faz: «▲ nasceu com 1 processo(s) segurando o nó do controle — nesta condição a barra não obedece, e só a reconexão devolve» | `secao_controles.frase_do_nascimento`, colada por `a08_conexoes.dica_da_luz` | a validação da FRASES-E-DICAS-02 ([entrega](../agentes/2026-09-13/FRASES-E-DICAS-02-opus.md)) |
| 03 e 04, o chip «Perfil ativo» | «—» com um perfil valendo, enquanto as outras oito abas dizem o nome | `a03_gatilhos.pacote` e `a04_iluminacao.pacote` emitem `"perfil"` cru; o piloto só completa o topo com `setdefault` | a VAO-DO-ESQUELETO-01 ([entrega](../agentes/2026-09-13/VAO-DO-ESQUELETO-01-opus.md), «O que sobrou», item 1), confirmado nas duas pontas |
| 07, o cartão da Steam | «· Exceção por jogo: N jogo(s) — controle liberado agora», ou «só valendo durante o jogo», ou «sem controle físico visível» | `emulation_actions.markup_status_steam_input`, lido por `a07_lancadores` | ficou em «não verifiquei» na FRASES-E-DICAS-02 |

## §D — Decisões (quem coordena, por delegação)

| decisão | base |
| --- | --- |
| A razão do nascimento sai da dica; a dica fica com o que o botão faz. O carimbo `nascimento` continua no `state_full` para o diagnóstico | a ordem dela de 13/09 (a citação no topo do índice) e o critério da §D da FRASES-E-DICAS-02: saem as dicas que avisam, confessam ou instruem sobre um estado |
| `frase_do_nascimento` e `FRASE_NASCEU_CONDENADO` saem se, depois da cura, só réguas as lerem | a regra da casa para constante sem leitor, que a FRASES-E-DICAS-02 aplicou ao `AVISO_DA_MESA_SUJA` |
| O chip «Perfil ativo» tem um dono só, `pacotes.topo()`: a 03 e a 04 param de emitir `perfil` | a regra que `a09_sistema.py` já escreveu: um pacote de aba só emite endereço daquela página |
| O sufixo perde a narração depois do travessão. A contagem fica só se a 07 não mostrar a lista das exceções em outro lugar | a mesma ordem de 13/09. A razão antiga (R-06, «ver se o opt-in está valendo», no comentário da função) ganha nota datada: a ordem mais nova vence |

## §I — IMPLEMENTA

1. `a08_conexoes.dica_da_luz` devolve só `dica_do_botao(...)`. O item 3 da
   docstring («a RAZÃO de a cura ser oferecida») vira nota datada.
2. Medir quem ainda lê `frase_do_nascimento` e `FRASE_NASCEU_CONDENADO`,
   inclusive o bloco `_tem_razao` de `secao_controles.py` (a janela GTK saiu em
   06/09, `D-0609-GTK-LEVA-INTEIRA`). Sem leitor vivo, saem, e
   `test_a_luz_nao_acende_o_botao_do_card.py` ganha nota datada.
3. Tirar a chave `"perfil"` de `a03_gatilhos.pacote` e de
   `a04_iluminacao.pacote`. A régua nova passa pelo caminho do piloto
   (`pacote_da_pagina` → `normalizar` → `topo`), com o daemon respondendo
   `active_profile` nulo e um perfil no disco: as dez abas pintam o mesmo nome
   no chip.
4. `markup_status_steam_input`: sai a narração depois do travessão. Medir na 07
   publicada se a lista das exceções já aparece, e decidir a contagem pela §D.
   Nota datada no comentário R-06 e em `test_steam_input_d33_nomeia_o_jogo.py`.
5. `test_nenhuma_frase_de_aviso_chega_a_tela.py` ganha as duas âncoras novas (o
   «▲» do nascimento e a narração do sufixo), lidas do dono quando houver
   constante.
6. Nenhuma página gerada deve mudar: a sprint não toca gerador. Se mudar, regere
   e publique na própria árvore.

## §V — Prova

* Piloto oculto, com `HEFESTO_DUALSENSE4UNIX_SKIP_PRESET_SEED=1` e os perfis
  copiados antes: foto do chip na 03 e na 04, antes e depois; a dica do «A luz
  não acende» lida no `#hef-dica`, com o mouse sobre o botão e a seção «Gestão
  de Controles» aberta.
* Mordidas: a razão de volta na `dica_da_luz`; o `"perfil"` de volta só na 03,
  e depois só na 04; a narração de volta no sufixo. Cada uma reprova a sua
  régua, e a devolução sai idêntica no `git diff`.

## §R — O preço

A dica deixa de dizer por que a cura da reconexão está sendo oferecida. O botão
continua lá e diz o que faz, e o carimbo continua no diagnóstico.

## Critério de pronto — por cabo · por BT · no perfil · por controle

| pergunta | resposta |
| --- | --- |
| **por cabo** / **por BT** | a razão só aparecia no rádio (`no_radio`); por cabo a dica não muda |
| **no perfil** | o chip nomeia o perfil que vale nas dez abas |
| **por controle** | a dica é por cartão; o sufixo do Steam Input é da máquina |
