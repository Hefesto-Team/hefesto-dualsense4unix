# FRASES-E-DICAS-01 — a recusa sai da tela, e o número fora diz só o número

Agente: opus · árvore `voo/FRASES-E-DICAS-01-opus`, nascida de `onda/1309` (`249af1f6`).
Sprint: `docs/process/sprints/2026-09-13-FRASES-E-DICAS-01-toda-frase-de-aviso-que-ainda-chega-a-tela.md`.

**Os dois nomes que a SISTEMA-BOTOES-01 usa, exatos:**

| o quê | nome | onde |
| --- | --- | --- |
| a chave da carga do clique que só ARMA | **`armou`** | `CHAVE_DO_CLIQUE_QUE_SO_ARMOU = "armou"`, em `src/hefesto_dualsense4unix/interface/hefesto_vivo.py`. O gesto devolve um `dict` com `armou` verdadeiro (`{"armou": True}`); o botão sai do voo sem piscar, e a chave sai da carga antes da pintura, junto com `recado`. |
| a classe da piscada de recusa | **`hef-recusou`** | `FOLHA_DA_CASA`, em `src/hefesto_dualsense4unix/interface/folha_da_casa.py`, ao lado de `hef-deu-certo`: borda e contorno `var(--orange,#ffb86c)`, a cor de aviso de `topo.html`. Dura `MS_DA_PISCADA` (1500 ms), o mesmo relógio do verde. |

## O que mudou

| arquivo | o que mudou |
| --- | --- |
| `src/hefesto_dualsense4unix/interface/hefesto_vivo.py` | `_recusou_dizendo` só escreve `[gesto falhou] <página> · <gesto>: <frase>` no diário e devolve `False`. Saíram, cada um com nota datada no lugar: `SEGUNDOS_DO_RECADO`, `SEGUNDOS_DO_RECADO_DE_SUCESSO`, `FRASE_DA_PAGINA_QUE_MORREU`, o `pintar_recados` do BOOTSTRAP com os quatro estilos, o passo da pintura que o chamava, `self._recados`, `_depositar`, `_recados_para_a_tela` e `carga["recados"]` no `_tique`. `_a_pagina_morreu` passa ao diário. `voltouDoVoo(n, certo)` ganhou três pousos: `true` pisca `hef-deu-certo`, `false` pisca `hef-recusou`, `null` não pisca. `_gesto` pousa `None` quando a carga traz `armou`, e o caminho sem dono pousa `False`. |
| `src/hefesto_dualsense4unix/interface/folha_da_casa.py` | a classe `hef-recusou`. |
| `src/hefesto_dualsense4unix/interface/pacotes/a04_iluminacao.py` | `fora_da_mesa()` saiu; a dica do número fora é `Player N`; a dica do tom tomado é só o nome do tom (`titulo_da_casa(i)`). `_MOTIVOS_NUMERO` fica na ponte: é a recusa, e vai ao diário. |
| `src/hefesto_dualsense4unix/interface/aba05.py` | a faixa `#vib-estado` perde `data-hef-recados` e `data-hef-recado-classe`; a autoconferência e a régua 17 do gerador cobram a faixa sem lugar de recado. |
| `mockup/04-iluminacao.html`, `mockup/05-vibracao.html` e as duas em `src/hefesto_dualsense4unix/interface/paginas/` | regeradas e publicadas (`--publicar 04`, `--publicar 05`). Diff da 04: só os `title` de «Player 3» e «Player 4». Diff da 05: dois comentários e a `div` da faixa sem os dois atributos. `check_o_desenho_aprovado.py` rc=0. |
| `tests/unit/test_a_recusa_pisca_no_botao.py` | **novo** (o `cria:`), 19 casos. Piloto oculto com um controle sintético, recusa dublada no `player` da 04 e no `mudo` da 02 (com coluna) e no cadeado da 01 (sem coluna): zero `.hef-recado`; a frase ausente do texto visível, de todo `data-hef-dica` e de todo `title`; o botão veste `hef-recusou` e a perde na piscada; `[gesto falhou]` no diário; mouse no `.fora` da 04 e `#hef-dica` diz exatamente «Player 2»; carga com `armou` não pisca; a 05 (bancada e publicada) sem `data-hef-recado`; a folha veste a recusa sem `display:none`. Esperas por condição com vigia `MutationObserver`, nunca marco de tempo fixo. |
| réguas da posse que cobravam o canal | mudaram de contrato **com data e a citação dela** — o índice da leva, `docs/process/sprints/2026-09-13-A-TERCEIRA-LISTA-DELA-INDICE.md`, linha 19: *"esse tipo tambem tem que parar de aparecer"*, com a foto da caixa laranja. Nenhum teste apagado; os que viraram o avesso levam `ERA <nome antigo>` no docstring: `test_a_recusa_chega_ao_cartao.py` (10 de 12), `test_a_tela_nao_narra_o_gesto_que_deu_certo.py` (3), `test_o_piloto_tem_o_terceiro_lugar_e_a_quarta_porta.py` (as 3 da peça 1; o `change` do campo passou a ser separado pelo carimbo de voo, e o pouso de cada botão também cobra `recusou`), `test_o_recado_de_sucesso_pousa_no_cartao.py` (5, e a leitura do botão ganhou `recusou`), `test_a_iluminacao_diz_o_numero_certo.py` (3), `test_a_iluminacao_avisa_quantos_receberam_o_desenho.py` (1), `test_a_aba_05_vibracao_fecha_as_linhas.py` (2). |
| `scripts/ensaios/o_recado_nao_desloca_a_coluna.py` | o veredito verde passou a ser *nenhum recado no cartão e o desenho no mesmo lugar*. Rodado: `VERDE — o desenho ficou em 329 px`. |
| **FORA DA POSSE**, e a cura os derrubava | `tests/unit/test_a_tela_nao_confessa_divida_nossa.py` (a premissa do canal: lê o `print` do diário e exige a ausência de `self._depositar(`), `tests/unit/test_a_vibracao_diz_o_que_esta_acontecendo.py` (a faixa sem atributos) e `tests/unit/test_a_aba_01_jogar_fecha_as_linhas.py` (a recusa do cadeado é lida no desfecho, não no depósito). Os três com nota datada. |
| **FORA DA POSSE**, e os portões reprovavam | `docs/data/paridade-gtk-html.csv:323` (a linha do recibo da 09: o sinal `classList.add('hef-deu-certo')` virou `certo === true ? 'hef-deu-certo'`, lido no `voltouDoVoo` — a piscada verde continua lá) e `tests/unit/test_portao_o_par_com_metade_ligada.py` (três chaves em `_CITACOES_PENDENTES`, com o número certo medido por símbolo: o piloto encolheu e três citações de outra posse, já fora do símbolo antes desta sprint, caíram em linha vazia). |

Da posse, não mudaram: `scripts/regua_de_tela.py` (o `Recado` dele são as mensagens da ponte, outro conceito), `tests/unit/test_regua_de_tela_a_aba_controles.py` e `tests/unit/test_a_aba_09_sistema_fecha_as_linhas.py` — verdes sem mudança.

**No piloto oculto, o que ela vê (foto e clique).** Driver do rascunho, fora do git: lar de mentira (`XDG_*` desviados), `HEFESTO_DUALSENSE4UNIX_SKIP_PRESET_SEED=1`, um controle sintético, a ponte dublada para recusar; os perfis dela copiados antes e o md5 conferido depois de cada corrida — idêntico em todas.

| gesto | ANTES (base `249af1f6`) | DEPOIS |
| --- | --- | --- |
| 04 · clique no «2» `.fora` | 1 recado em grade no cartão do P1, «Esse número é maior…»; a frase em 3 `data-hef-dica`; o botão `fora → fora hef-em-voo → fora`, sem sinal | 0 recado; a frase em 0 dica, 0 `title`, fora do texto; o botão `fora → fora hef-em-voo → fora hef-recusou` (3343 ms) `→ fora` (4843 ms) |
| 04 · mouse no «2» | `#hef-dica`: «Player 2 — Esse número é maior do que a quantidade de controles ligados.» | `#hef-dica`: «Player 2» |
| 02 · microfone do P1, recusa | recado no cartão do P1 | 0 recado; `mudo-i hef-recusou` (2007 ms) `→ mudo-i` (3507 ms) |
| 02 · microfone com `{"armou": True}` | `mudo-i hef-deu-certo` (4653 ms), apaga aos 6154 ms | `mudo-i hef-em-voo → mudo-i`, sem piscar |
| 01 · cadeado (sem coluna) | recado no cartão do P1 | 0 recado; `hef-recusou` (2003 ms) `→` sem classe (3504 ms) |
| 05 publicada | 1 faixa `data-hef-recados` | 0 faixa |

O diário da corrida de depois tem as quatro linhas `[gesto falhou]`. Fotos:
`ANTES-04-o-clique-no-2.png` (a caixa laranja sobre o desenho do P1) e
`DEPOIS-04-o-clique-no-2.png` (sem caixa; o «2» com a borda laranja da piscada).
`ANTES-05-publicado.png` e `DEPOIS-05-publicado.png` têm o **mesmo md5**
(`aa54a5f2…`): a faixa estava vazia em repouso, e o que saiu dela são atributos.

**Réguas pontuais, na árvore curada:** `test_a_recusa_pisca_no_botao` 19 ·
`test_a_recusa_chega_ao_cartao` 12 · `test_a_tela_nao_narra_o_gesto_que_deu_certo` 10 ·
`test_o_piloto_tem_o_terceiro_lugar_e_a_quarta_porta` 14 ·
`test_o_recado_de_sucesso_pousa_no_cartao` 19 · `test_a_iluminacao_diz_o_numero_certo` 41 ·
`test_a_aba_01_jogar_fecha_as_linhas` 29 · `test_a_aba_05_vibracao_fecha_as_linhas` 27 ·
`test_a_iluminacao_avisa_quantos_receberam_o_desenho` 13 · e os consumidores
`test_a_aba_09_sistema_fecha_as_linhas` 32 · `test_regua_de_tela_a_aba_controles` 13 ·
`test_a_vibracao_diz_o_que_esta_acontecendo` 21 · `test_a_tela_nao_confessa_divida_nossa` 27 ·
`test_o_reconectar_nao_muda_de_lugar` 12 · `test_a_tela_nao_samba` 14 ·
`test_os_quatro_gestos_da_aba_sistema_que_faltavam` 27 · `test_a_regua_da_palavra_ve_o_produto` 9 ·
`test_a_janela_estreita_nao_engole_o_desenho` 158 (+4 xfailed) ·
`test_a_04_iluminacao_o_gesto_esta_onde_deve` 8 — todos passaram.

**Portões:** `bash scripts/portoes.sh` depois do `git add -A` — **TODOS VERDES, 60 portões**.
A primeira corrida reprovou quatro, e os quatro eram desta cura: duas conjugações de
«medir» que o portão de acento lê como «média», o glifo do microfone nesta entrega, o
sinal da linha 323 da paridade e as três citações de linha deslocadas (ver acima).

## Qual mordida prova

Seis mordidas na árvore curada, cada uma devolvida por `cp` da cópia guardada antes,
com md5 e `git diff` do arquivo conferidos contra o de antes da mordida:

```
== a · hefesto_vivo.py de 249af1f6 (o depósito e a pintura do recado de volta)
   test_a_recusa_pisca_no_botao.py      9 failed, 10 passed
      test_a_recusa_nao_poe_frase_na_tela[04] [02] [01]
      test_o_botao_veste_a_recusa_e_a_perde_na_piscada[04] [02] [01]
      test_o_clique_que_so_arma_nao_pisca
      test_a_recusa_so_escreve_no_diario
      test_a_chave_do_clique_que_so_arma_e_armou
   test_a_recusa_chega_ao_cartao.py     10 failed, 2 passed (as dez do avesso)
   devolvida: md5 6e3a9afd… IGUAL; git diff IGUAL
== b · voltouDoVoo com (certo === false ? '' : '')
   test_a_recusa_pisca_no_botao.py      3 failed, 16 passed
      test_o_botao_veste_a_recusa_e_a_perde_na_piscada[04] [02] [01]
   devolvida: md5 6e3a9afd… IGUAL; git diff IGUAL
== c · _gesto sem so_armou: certo = (desta_vez[0] == "aplicou")
   test_a_recusa_pisca_no_botao.py      1 failed, 18 passed
      test_o_clique_que_so_arma_nao_pisca
   devolvida: md5 6e3a9afd… IGUAL; git diff IGUAL
== d · pacotes/a04_iluminacao.py de 249af1f6 (a frase de volta à dica)
   test_a_recusa_pisca_no_botao.py      2 failed, 17 passed
      test_a_recusa_nao_poe_frase_na_tela[04]
      test_o_numero_fora_diz_so_o_numero
   test_a_iluminacao_diz_o_numero_certo.py  3 failed, 38 passed
   devolvida: md5 00e138b1… IGUAL; git diff IGUAL
== e · folha_da_casa.py sem a regra .hef-recusou
   test_a_recusa_pisca_no_botao.py      1 failed, 18 passed
      test_a_folha_veste_a_recusa_sem_esconder_nada
   devolvida: md5 70c08f2e… IGUAL; git diff IGUAL
== f · paginas/05-vibracao.html de 249af1f6 (a faixa declarando o recado)
   test_a_recusa_pisca_no_botao.py      1 failed, 18 passed
      test_a_aba_05_nao_declara_lugar_de_recado[publicado]
   devolvida: md5 cb573d8a… IGUAL; git diff IGUAL
```

A mordida **a** é o §V inteiro — *devolver o `_depositar` → reprova* — e a **d** é o
*devolver a frase → reprova* da dica. Na **a**, `test_o_botao_recusou_dizendo` e
`test_a_frase_da_recusa_vai_ao_diario` passam, e têm de passar: a base também recusava
e também escrevia no diário; o que mudou é a tela.

## O que NÃO verifiquei

* **O aparelho e a tela instalada.** Tudo foi medido no piloto oculto com um controle
  sintético e a ponte dublada. Nenhuma recusa real do daemon, e o olho dela não viu.
* **Os outros gestos que levantam `RuntimeError`.** O caminho é um só
  (`_recusou_dizendo`), mas cliquei três: o `player` da 04, o `mudo` da 02 e o cadeado
  da 01.
* **A dica do tom tomado** («Cor» com dois controles, a mesma cor no vizinho): a
  mudança está no pacote, e não passei o mouse nela no piloto.
* **Os ensaios que liam o recado e não rodei:** `scripts/ensaios/a_forca_por_controle_no_webkit.py`
  (da posse; só imprime recados) e, fora da posse, `scripts/ensaios/a_tecla_livre_no_webkit.py`,
  `scripts/ensaios/o_clique_da_coluna_que_esvaziou.py` e
  `scripts/ensaios/o_botao_copiar_a_linha_no_webkit.py` — vão reportar diferente.
* **A suíte inteira** (regra do despacho: só pytest pontual).

## O que sobrou para o próximo

* **Prosa fora da posse que ainda descreve o canal que saiu** — nenhuma chega à tela;
  todas afirmam comportamento velho: `pacotes/a02_controles.py:3103,3460`,
  `pacotes/a03_gatilhos.py:2409,2840` (FRASES-E-DICAS-02), `pacotes/a05_vibracao.py:267,1165,1543,1777`,
  `pacotes/a06_navegacao.py:82,86,117,603,1818,2065,2733`, `pacotes/a08_conexoes.py:501`,
  `pacotes/a10_perfis.py:51,66,470,481,617,1854,1857,1897,3430,3923` (nao_toca),
  `aba04.py:424` e o comentário de CSS em `aba04.py:971` («quem insistir ouve a recusa»,
  que viaja para a página 04; posse da DICA-DA-COR-01), `app/telas/vibracao.py:425`,
  `docs/data/paridade-gtk-html.csv:92,185` (as linhas que dizem que a recusa chega à tela)
  e `docs/data/decisoes-dela.csv:202`.
* **As três citações de linha do piloto em outra posse**, declaradas pendentes com o número certo: `aba02.py:1185` (`hefesto_vivo.py:202` → `:1373`), `a10_perfis.py:967` (`:256` → `:587`) e `a10_perfis.py:3009` (`:228` → `:1501`). Quem for dono reaponta por símbolo e apaga a pendência.
* **`scripts/check_a_tela_nao_confessa.py`** (nao_toca) lê o canal do `RuntimeError`, que
  desde esta sprint vai só ao diário. O §R manda anotar: a régua de língua continua
  valendo para o diário, mas o nome promete tela.
* **A §1.2 e a §1.3 da TELA-CALADA-04 caducam** por esta sprint (a §D), e o arquivo dela não
  é desta posse — quem coordena anota.
* **O glossário** (`docs/A-LINGUA-DESTA-CASA-o-glossario-que-a-tela-e-o-codigo-falam.md`) não
  tem verbete para a piscada de recusa.
* **A SISTEMA-BOTOES-01** põe `armou` na carga dos «Confirma?»; o lado do piloto está aqui.
* **Na costura:** `hefesto_vivo.py` é de muitas sprints desta leva, e as páginas 04 e 05
  mudam em outras — regerar, nunca mesclar à mão.

## O que a validação refez e corrigiu

Agente valida/corrige, na mesma árvore e na mesma branch, sobre `81007827`.

**Os dois nomes para a SISTEMA-BOTOES-01, conferidos no código:** a chave da carga é
**`armou`** (`hefesto_vivo.CHAVE_DO_CLIQUE_QUE_SO_ARMOU`), e a classe da piscada de
recusa é **`hef-recusou`** (`folha_da_casa.FOLHA_DA_CASA`). Um gesto que devolve
`{"armou": True}` pousa sem piscada nenhuma.

### O que foi refeito

| o quê | como | resultado |
| --- | --- | --- |
| posse | `git diff --name-only 249af1f6..HEAD` contra o frontmatter | 23 arquivos na posse, nas páginas geradas, na entrega e na sprint; os 5 de fora têm a razão escrita acima, e as três citações pendentes batem por símbolo nas linhas 587, 1373 e 1501 do piloto |
| nenhum botão novo | `<button` e `data-gesto=` nas dez páginas publicadas e nas dez do `mockup/`, base contra branch | idênticos nas vinte (04: 60 botões e 66 gestos; 05: 32 e 0) |
| réguas | 48 arquivos, um processo por arquivo: os 17 da entrega e mais 31 que leem o que a sprint mudou (os símbolos que saíram, `a04_iluminacao`, a guia de tons) | um vermelho, o achado 1; depois da correção, os 48 verdes |
| tela | driver próprio no rascunho: piloto `--oculta` com Xvfb próprio, lar de mentira e um controle sintético; a base, extraída por `git archive 249af1f6` | a tabela da tela, abaixo |
| mordidas | doze, cada uma por substituição exata, devolvida por cópia, com o md5 do arquivo e o do `git diff` inteiro conferidos | as doze reprovaram, e as doze voltaram iguais |
| disco dela | md5 de `~/.config/hefesto-dualsense4unix/profiles/` antes e depois de cada corrida | igual em todas |

### Os achados

1. **CORRIGIDO — a casa tomada da aba 04 perdeu o nome do dono.** A cura trocou a dica
   do tom tomado por `titulo_da_casa(i)`, e a casa com X passou a dizer «Cor do Player 2.
   Pinta a barra, não muda o número.» — falso numa casa que não pinta nada.
   `test_fecha_iluminacao_01_duas_pecas_nunca_tem_a_mesma_cor.py::TestOGestoDaAba::test_a_guia_desenha_o_x_exatamente_no_que_o_gesto_recusa`
   reprovou; ela não estava entre as réguas rodadas. A nota do código dizia «o nome do
   dono continua no X, pela cor», e caiu: o X é preto com borda branca desde 09/09
   (`test_o_x_e_preto_com_borda_branca_e_nao_a_cor_do_dono`). A cura: a dica da casa
   tomada diz só o nome do dono, que é estado, sem a regra colada. As páginas não mudam,
   porque o gerador desenha a guia sem casa tomada. Régua nova:
   `test_a_casa_tomada_diz_de_quem_e_sem_a_regra`.
2. **CORRIGIDO (faltava régua) — o clique sem dono passou a piscar a recusa, e nada o
   cobria.** O `_pousou(voo, False)` no ramo sem dono é mudança da cura, fora da letra do
   §I. No piloto, o «Guardar» do remapeamento da 06, declarado sem dono em
   `a06_navegacao`: na base `btn roxo → btn roxo hef-em-voo → btn roxo`; na branch
   `… → btn roxo hef-recusou → btn roxo`, 1500 ms depois. Fica: o piloto já o conta como
   recusa (`self.recusados`), e o §0 manda responder pelo sinal do botão. Régua nova:
   `test_o_clique_sem_dono_pisca_a_recusa`. **O alcance, para o olho dela:** lendo o
   seletor do ouvinte contra os donos registrados, os botões declarados sem dono são dez
   na 06, um na 08 (`novo-hub`) e um na 01 (o degrau `modo-steam`) — os doze passam a
   piscar laranja quando clicados.
3. **ANOTADO, não corrigido — `docs/data/paridade-gtk-html.csv:323`.** A entrega trocou o
   `sinal` dessa linha, e a coluna do que o HTML faz continua dizendo «O que traz notícia
   fala no cartão; a recusa vira recado», que caducou com a TELA-CALADA-01 e com esta
   sprint. Fora da posse; soma-se às linhas 92 e 185 já listadas para quem coordena.

### A tela, antes e depois (piloto oculto, clique pelo ouvinte de verdade)

| gesto | base `249af1f6` | branch |
| --- | --- | --- |
| 04 · ponteiro no «2» `.fora` | `#hef-dica`: «Player 2 — Esse número é maior do que a quantidade de controles ligados.» | `#hef-dica`: «Player 2» |
| 04 · clique no «2» | 1 recado em grade, laranja, sobre o desenho do P1; a frase no texto visível; o botão volta do voo sem sinal | 0 recado; a frase fora do texto, das dicas e dos `title`; `fora hef-recusou`, contorno `rgb(255, 184, 108)`, apagado 1500 ms depois |
| 01 · o cadeado recusando | recado sobre o cartão do P1 | 0 recado; `hef-recusou` por 1500 ms |
| 05 · repouso | 1 `data-hef-recados` | 0 |

Fotos, nesta pasta: o clique no «2» refeito pelo driver da validação saiu **igual byte a
byte** às duas da entrega (mesmo md5), então elas ficam como estão —
`ANTES-04-o-clique-no-2.png` e `DEPOIS-04-o-clique-no-2.png`; e as novas,
`VALIDA-ANTES-04-a-dica-do-2.png` e `VALIDA-DEPOIS-04-a-dica-do-2.png`,
`VALIDA-ANTES-01-o-cadeado.png` e `VALIDA-DEPOIS-01-o-cadeado.png`.

### As doze mordidas

| mordida | reprovou |
| --- | --- |
| a · `_recusou_dizendo` volta a pôr a frase num `.hef-recado`, depois do diário | 12: `test_a_recusa_nao_poe_frase_na_tela[04]`, `[02]`, `[01]`, `test_a_recusa_so_escreve_no_diario` e oito de `test_a_recusa_chega_ao_cartao` |
| b · `voltouDoVoo` sem `'hef-recusou'` | 5: a piscada nas três abas e duas de `test_o_recado_de_sucesso_pousa_no_cartao` |
| c · a piscada não se apaga | 4: a piscada nas três abas e `test_o_clique_que_so_arma_nao_pisca` |
| d · a frase de volta à dica do `.fora` | 5: a frase na tela da 04, `test_o_numero_fora_diz_so_o_numero` e três de `test_a_iluminacao_diz_o_numero_certo` |
| e · a 05 publicada declara `data-hef-recados` | `test_a_aba_05_nao_declara_lugar_de_recado[publicado]` |
| f · `aba05.MIOLO` declara `data-hef-recados`, e o gerador roda | o gerador recusa, rc=1: «a faixa voltou a declarar lugar de recado» |
| g · `so_armou = False` | `test_o_clique_que_so_arma_nao_pisca` |
| h · o sem dono pousa com `_pousou(voo)` | `test_o_clique_sem_dono_pisca_a_recusa` |
| i · o diário sem o prefixo `[gesto falhou]` | 5: o diário nas três abas, `test_a_recusa_so_escreve_no_diario` e a premissa de `test_a_tela_nao_confessa_divida_nossa` |
| j · a folha sem `.hef-recusou` | `test_a_folha_veste_a_recusa_sem_esconder_nada` |
| k · a regra colada de volta à casa tomada | `test_a_casa_tomada_diz_de_quem_e_sem_a_regra` |
| l · a casa tomada sem o nome, como estava na entrega | a régua nova e a régua do X |

**Portões:** `bash scripts/portoes.sh` depois do `git add -A`, com esta seção e a
correção dentro — TODOS VERDES.

### O que a validação não verificou

* O aparelho, a tela instalada e o olho dela: tudo no piloto oculto, com controle
  sintético e ponte dublada.
* Os ensaios que liam o recado, o da posse e os três de fora: não rodados.
* A suíte inteira.
* A dica da casa tomada no piloto com dois controles na mesa: lida só no pacote.
