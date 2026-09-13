---
sprint: FRASES-E-DICAS-02
estado: aberta
onda: A-TERCEIRA-LISTA-DELA
posse:
  FRASES-E-DICAS-02:
    - src/hefesto_dualsense4unix/app/actions/config/secao_controles.py
    - src/hefesto_dualsense4unix/interface/pacotes/a08_conexoes.py
    - src/hefesto_dualsense4unix/interface/aba08.py
    - src/hefesto_dualsense4unix/interface/monta.py
    - src/hefesto_dualsense4unix/interface/pacotes/a03_gatilhos.py
    - src/hefesto_dualsense4unix/interface/pacotes/a02_controles.py
    - src/hefesto_dualsense4unix/interface/desenho_dos_lancadores.py
    - src/hefesto_dualsense4unix/app/actions/emulation_actions.py
    - tests/unit/test_a08_o_veredito_e_a_mesa_de_radio_dela.py
    - tests/unit/test_a_luz_nao_acende_o_botao_do_card.py
    - tests/unit/test_o_cartao_da_steam_nao_narra.py
    - docs/process/sprints/2026-09-13-FRASES-E-DICAS-02-as-dicas-e-as-linhas-que-avisam-viram-estado.md
cria:
  - tests/unit/test_nenhuma_frase_de_aviso_chega_a_tela.py
bancada: false
depois_de: []
nao_toca:
  - src/hefesto_dualsense4unix/interface/hefesto_vivo.py
  - src/hefesto_dualsense4unix/interface/pacotes/a09_sistema.py
  - src/hefesto_dualsense4unix/interface/pacotes/a07_lancadores.py
  - src/hefesto_dualsense4unix/integrations/storm_doctor.py
  - src/hefesto_dualsense4unix/integrations/ordens_da_mesa.py
  - src/hefesto_dualsense4unix/integrations/sentinela_do_wrapper.py
  - src/hefesto_dualsense4unix/interface/frases_que_ela_baniu.py
---

# FRASES-E-DICAS-02 — as dicas e as linhas que avisam viram estado

Nasceu em 13/09/2026 da partição da
[FRASES-E-DICAS-01](2026-09-13-FRASES-E-DICAS-01-toda-frase-de-aviso-que-ainda-chega-a-tela.md),
depois do estudo. A palavra dela e a regra (§0) estão lá. **Esta é a metade das
DICAS e das LINHAS visíveis nas abas 02, 03, 07 e 08**; a aba Sistema é da
[SISTEMA-BOTOES-01](2026-09-13-SISTEMA-BOTOES-01-cada-botao-da-aba-sistema-faz-o-que-diz.md),
e o canal de recado do piloto é da 01.

## §E — O que o estudo mediu (13/09, piloto oculto sobre `e7d1dac2`)

| onde | o que chega à tela | quem escreve |
| --- | --- | --- |
| 08, a dica da luz | «Atenção: outro programa está segurando controle agora… Feche-o antes para o gesto valer.» | `secao_controles.py` (`dica_da_luz` + `AVISO_DA_MESA_SUJA`) |
| 08, a contagem do desenho | «O que eu não consegui conferir neste desenho: …» (`confissao-dica`) | `a08_conexoes.py` + `CONFISSAO_ABERTURA` |
| 08, a ordem do exame | «Não medi o ganho nesta máquina.» e «O que fazer: Abra…», visíveis sem clique — o `?` ao lado já tem o mesmo conteúdo | `html_da_ordem` (`div.faca`, `div.ganho`) e o segundo card em `a08_conexoes.py`; cravado em `aba08.py` |
| 02, o canal do alto-falante | «O canal de áudio deste controle está SUSPENSO no PipeWire. … medido: …» | `alto-canal-porque`, vindo de `app/widgets/controller_card.py` |
| fita e 03, cor não lida | «a cor do plástico deste controle não foi lida» | `monta.py` (a fita) e `chip_do_controle` em `a03_gatilhos.py`; cravado em `aba08.py` |
| 07, os ramos do cartão da Steam | não achei · erro de leitura · Steam Input ligado | `desenho_dos_lancadores.py` (`DIZ_NAO_ACHEI`) e `markup_status_steam_input` em `emulation_actions.py` |

Fica, por ser ajuda ou estado: o `?`, as dicas que dizem o que o controle faz, as
contagens. O estudo inteiro fica na pasta do lote `1309-terceira`.

## §D — Decisões (quem coordena, por delegação)

| decisão | base |
| --- | --- |
| O `?` e as dicas que dizem o que o controle faz ficam; saem as que avisam, confessam ou instruem sobre um estado | a ordem dela de 07/09, «o layout não informa os nossos defeitos» (`tests/unit/test_a_tela_nao_confessa_divida_nossa.py`), e a de 13/09 no índice |
| Na ordem do exame, `faca` e `ganho` saem da coluna visível; o `?` que os contém fica | índice, §0 item 4 («tirar e enxugar pode»); a docstring contrária de `html_da_ordem` vira nota datada |
| A cor não lida diz o nome da cor, ou nada | a mesma ordem de 07/09 |

## §I — IMPLEMENTA

1. `dica_da_luz` para de colar `AVISO_DA_MESA_SUJA`; a constante sai se ninguém
   mais a ler.
2. A 08 para de emitir `confissao-dica` (fica a contagem); `html_da_ordem` e o
   segundo card tiram `div.faca` e `div.ganho` da vista. Regerar `aba08.py` e
   `--publicar 08`.
3. As dicas de cor não lida — a fita em `monta.py`, o chip da 03, o cravado de
   `aba08.py` — dizem só o nome.
4. O `alto-canal-porque` da 02 vira rótulo curto de estado, sem PipeWire e sem
   «medido».
5. Os três ramos do cartão da 07 viram rótulo curto e passam pela régua
   `_e_rotulo_de_estado` de `tests/unit/test_o_cartao_da_steam_nao_narra.py`.
6. A régua nova passeia pelas dez abas no piloto oculto.

## §V — VALIDA/CORRIGE — o que morde

* Piloto `--oculta` nas dez abas, com `sem_cor=True` e o estado dublado de
  controle segurado por outro programa: nenhum texto visível nem dica contém as
  âncoras **lidas dos donos** — `AVISO_DA_MESA_SUJA`, `CONFISSAO_ABERTURA`, o
  trecho de cor não lida, a frase do canal suspenso, `NAO_MEDI`. **Devolver
  qualquer uma → reprova.**
* O `.ajuda` do exame continua com «O que fazer».
* Unitário do cartão da 07 com os três ramos dublados.
* Fotos da 02, 03, 07 e 08 antes e depois; `scripts/check_o_desenho_aprovado.py`
  e portões verdes; perfis por md5.

## §R — Riscos declarados

* As seções fechadas da 06 e da 08 não foram abertas no estudo: abrir antes de
  medir.
* A página 08 muda em outras sprints desta leva: regerar, nunca mesclar à mão.
* A ordem do exame é o miolo de uma seção: tirar `faca` e `ganho` deixa a
  recomendação só no `?`. É a ordem dela; a nota datada diz isso.

## Critério de pronto — por cabo · por BT · no perfil · por controle

| pergunta | resposta |
| --- | --- |
| **por cabo** / **por BT** | não se aplica: é a tela |
| **no perfil** | nada vai ao disco |
| **por controle** | as dicas do cartão de cada controle seguem a mesma regra |
