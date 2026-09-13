---
sprint: F1-REMAPEAR-02
estado: aberta
onda: A-TERCEIRA-LISTA-DELA
posse:
  F1-REMAPEAR-02:
    - src/hefesto_dualsense4unix/interface/aba06.py
    - src/hefesto_dualsense4unix/interface/pacotes/a06_navegacao.py
    - src/hefesto_dualsense4unix/daemon/connection.py
    - tests/unit/test_migra_navegacao_13_o_remapeamento_botao_a_botao.py
    - tests/unit/test_a_recusa_pisca_no_botao.py
    - docs/process/sprints/2026-09-13-F1-REMAPEAR-02-as-seis-linhas-que-a-troca-nao-alcanca-e-o-ps-do-boot.md
cria:
  - tests/unit/test_as_seis_linhas_fora_da_troca_ficam_apagadas.py
  - tests/unit/test_o_boot_entrega_o_ps_do_perfil.py
bancada: false
depois_de: []
nao_toca:
  - src/hefesto_dualsense4unix/interface/hefesto_vivo.py
  - src/hefesto_dualsense4unix/core/remapeamento_de_botao.py
  - docs/data/paridade-gtk-html.csv
  - scripts/check_cabo_bt_perfil_controle.py
---

# F1-REMAPEAR-02 — as seis linhas que a troca não alcança e o PS do boot

Nasceu na costura da onda 1 (13/09/2026). São os dois achados que a
[F1-REMAPEAR](2026-09-11-F1-REMAPEAR-as-vinte-e-duas-linhas-e-o-motor-que-nao-existe.md)
deixou para quem coordena ([a entrega](../agentes/2026-09-13/F1-REMAPEAR-opus.md),
«O que fica, sem cura aqui» e «O que sobrou para o próximo»).

## §E — O que a entrega mediu

1. **As seis linhas que o motor recusa têm lista clicável.** São a direção do L3
   e do R3, o PS e as três regiões do touchpad
   (`remapeamento_de_botao.FORA_DO_ALCANCE` e `BOTAO_PS`). Escolher algo nelas é
   recusado na hora, mas a lista continua mostrando a escolha recusada, e ela
   vai na `forma` (medido: `forma["ps"]` saiu `"Cruz"`). Todo «Guardar» seguinte
   é recusado até ela devolver a linha a «— Sem troca —». Depois da
   FRASES-E-DICAS-01 a recusa não tem texto: o botão pisca laranja, e nada diz
   qual linha segura o Guardar.
2. **As frases de recusa dos quatro gestos da troca** pousavam no cartão na base
   da sprint: colisão, PS, fora do alcance, desconhecido, forma ilegível, igual
   ao perfil, apagador e padrão já sem troca. A costura juntou a
   FRASES-E-DICAS-01, e ninguém mediu na 06.
3. **Lido, não medido:** `restore_last_profile`, em
   `src/hefesto_dualsense4unix/daemon/connection.py`, monta o `ProfileManager` à
   mão e sem o `ps_action_sink`. Então a escolha que o perfil dá ao PS só
   chegaria ao `ps_solo` na primeira troca de perfil, e não no boot. As outras
   rotas usam `gerente_do_daemon`, em `src/hefesto_dualsense4unix/profiles/manager.py`.

## §D — Decisões (quem coordena, por delegação)

| decisão | base |
| --- | --- |
| As seis listas ficam APAGADAS: mostram «— Sem troca —» e não são clicáveis. A linha e a lista ficam onde estão, sem frase | a palavra dela na 06-Q1, citada em `aba06.py` («o switch fica apagado (não clicável) MAS mostra o estado real»), e o §0 do índice (nada de botão novo; tirar e enxugar pode) |
| O motor continua recusando as seis | a guarda do Python fica mesmo com a folha protegendo o ponteiro, pela razão que `aba06.py` dá para o gesto `modo` |
| O boot entrega o PS pelo mesmo caminho das outras ativações, sem ligar o `mouse_applier` nem o `mode_applier`, que o boot desliga de propósito (`BUG-BOOT-RESTORE-FLIPS-EMULATION-01`) | «quando a cura conhece a causa, ela cobre TODOS os chamadores» ([ONDE PARAMOS de 05/09](../2026-09-05-ONDE-PARAMOS-as-treze-queixas-e-os-instrumentos-que-mentiam.md)) |

## §I — IMPLEMENTA

1. `aba06.py`: as seis listas da troca nascem apagadas pela regra de apagado da
   casa (não clicáveis, mostrando o estado real), sem o `data-gesto` da troca e
   com só a opção «— Sem troca —». A autoconferência do gerador confere 16 listas
   com gesto e 6 apagadas. Regere e publique a 06.
2. `a06_navegacao.py`: se a `forma` do «Guardar» ainda trouxer as seis chaves,
   elas só passam com «— Sem troca —». A recusa do motor fica.
3. `test_a_recusa_pisca_no_botao.py` ganha o caso da 06: um gesto de troca
   recusado (a colisão) não põe frase na tela e pisca o botão.
4. Medir com dublê se `restore_last_profile` entrega a ação do PS ao sink.
   Confirmado, a cura fica em `connection.py`, passando o mesmo sink que
   `gerente_do_daemon` passa, e a régua nova prova pelo dublê do sink. Se a
   medição derrubar o achado, a régua fica como prova e a entrega diz.

## §V — Prova

* Foto da tela «Trocar os botões» da 06, antes e depois. Piloto oculto, perfis
  copiados antes, `--prova-clique linha-de-troca,fechar-troca`. Nunca clicar o
  «Guardar» no WebKit, porque ele grava no perfil dela.
* Mordidas:
  * uma das seis volta a ser clicável: a régua das seis reprova;
  * o `ps_action_sink` sai do boot: a régua do boot reprova;
  * a frase da colisão volta à tela da 06: a régua da recusa reprova.
* Contagem de `<button`, `<select` e `data-gesto` na 06, antes e depois. Nenhum
  botão novo.

## §R — O preço

Uma lista apagada não diz por que não troca. É o preço da ordem de 13/09: sem
frase.

## Critério de pronto — por cabo · por BT · no perfil · por controle

| pergunta | resposta |
| --- | --- |
| **por cabo** / **por BT** | a troca é de software, depois da leitura; o transporte não muda nada |
| **no perfil** | a troca e a ação do PS são do perfil; o boot passa a entregar as duas |
| **por controle** | a troca vale nos quatro controles, pelos dois `forward_buttons` |
