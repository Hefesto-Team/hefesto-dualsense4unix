# FRASES-E-DICAS-03 — a razão do nascimento, o chip de dois donos e o sufixo do Steam Input (IMPLEMENTA, opus)

Sprint: [FRASES-E-DICAS-03](../../sprints/2026-09-13-FRASES-E-DICAS-03-a-razao-do-nascimento-o-chip-de-dois-donos-e-o-sufixo-do-steam-input.md)
· branch `voo/FRASES-E-DICAS-03-opus` · base `e1c7d96b` (conferida igual a `onda/1309`).
Não houve estudo separado: os três achados vieram medidos das entregas
[FRASES-E-DICAS-02](FRASES-E-DICAS-02-opus.md) (achado 6 da validação) e
[VAO-DO-ESQUELETO-01](VAO-DO-ESQUELETO-01-opus.md) («O que sobrou», item 1).
`bancada: false`: nenhum gesto foi mandado ao daemon, nada escrito no aparelho.

## O que mudou

Medido no piloto oculto (`hefesto_vivo.Piloto`, Xvfb da guarda, `sem_cor`,
`HEFESTO_DUALSENSE4UNIX_SKIP_PRESET_SEED=1`, vista 1918x840), com o daemon vivo
dela e um DualSense pelo rádio. O ANTES rodou sobre a árvore intocada, antes da
primeira edição. Os cliques foram no `a.aba` da tira (as dez abas, em ordem) e no
rótulo «Gestão de Controles» da 08; o ponteiro passou sobre o «A luz não acende»
e o `#hef-dica` foi lido. Nenhum `data-gesto` clicado.

| onde | antes | depois |
| --- | --- | --- |
| 08, hover do «A luz não acende», seção aberta | o que o botão faz, e depois «▲ nasceu com 1 processo(s) segurando o nó do controle — nesta condição a barra não obedece, e só a reconexão devolve» | só o que o botão faz: «Derruba este controle do rádio. … o botão PS é seu.» |
| chip «Perfil ativo», 03 e 04 | «—», com o nome nas outras oito | o mesmo nome nas dez |
| 07, linha do Steam Input com uma exceção | «Desligado — tudo certo · Exceção por jogo: 1 jogo(s) — controle liberado agora» | «Desligado — tudo certo · Exceção por jogo: 1 jogo(s)» |

A linha da 07 foi medida com a leitura da lista de exceções dublada
(`_steam_input_excecao_status` devolvendo uma exceção efetiva): a máquina dela
não tem nenhuma, e sem dublê as fotos antes e depois seriam iguais. O ANTES dessa
linha é o `emulation_actions.py` do HEAD posto na árvore e devolvido, com o
`git diff` conferido idêntico.

Fotos, recortadas das corridas do piloto: `FRASES-E-DICAS-03-ANTES-03-chip.png`,
`FRASES-E-DICAS-03-DEPOIS-03-chip.png`, `FRASES-E-DICAS-03-ANTES-04-chip.png`,
`FRASES-E-DICAS-03-DEPOIS-04-chip.png`, `FRASES-E-DICAS-03-ANTES-08-dica-da-luz.png`,
`FRASES-E-DICAS-03-DEPOIS-08-dica-da-luz.png`, `FRASES-E-DICAS-03-ANTES-07-sufixo.png`
e `FRASES-E-DICAS-03-DEPOIS-07-sufixo.png`, nesta pasta.

**NENHUM BOTÃO NOVO, NENHUMA PÁGINA MUDOU.** No DOM do piloto, `button` e
`data-gesto` por aba são os mesmos antes e depois: 5/21, 40/45, 12/27, 23/28,
32/0, 12/92, 16/22, 34/59, 19/16 e 11/0, da 01 à 10. O `git diff` não traz HTML:
nenhum gerador foi tocado, e nada foi regerado nem publicado. Perfis: iguais por
md5 (159 arquivos) depois de cada uma das quatro corridas do piloto.

### O código

* **`interface/pacotes/a08_conexoes.py`** — `dica_da_luz(via)` devolve só
  `dica_do_botao(...)`; o parâmetro `nascimento` saiu, e a chamada no `pacote()`
  também. O item 3 da docstring virou nota datada. O arquivo manteve as 5307
  linhas: `a09_sistema.py`, que é `nao_toca:`, cita a 08 por número.
* **`app/actions/config/secao_controles.py`** — saíram `FRASE_NASCEU_CONDENADO`,
  `frase_do_nascimento`, a linha da razão do `_BlocoDaLuz` (com o parâmetro
  `nascimento`) e o `_nascimentos` do `_PainelDosControles`, que só a alimentava.
  **Os leitores, medidos por `git grep` antes de apagar:** a dica da 08 (vivo, e
  saiu nesta cura), o `_BlocoDaLuz` da janela GTK, que saiu em 06/09
  (`D-0609-GTK-LEVA-INTEIRA`) e está fora dos pontos de entrada do produto (a nota
  em `tests/unit/portao_a_casa_sabe_e_o_produto_nao_faz.py`), e réguas. No lugar
  das duas ficou uma nota datada com as três regras do silêncio — sem carimbo,
  `limpa` e `nao_sei` calavam —, que são decisão medida caducando junto.
* **`interface/pacotes/a03_gatilhos.py` e `a04_iluminacao.py`** — a chave
  `perfil` saiu do retorno de `pacote()`, trocada por um comentário de uma linha.
  O chip fica com um dono só, `pacotes.topo()`.
* **`app/actions/emulation_actions.py`** — `markup_status_steam_input`: o sufixo
  perde o travessão e o estado narrado. **A contagem fica, pela §D:** a 07 não
  mostra a lista das exceções em outro lugar. Medido na página publicada (a
  palavra só aparece em comentário de CSS) e no fonte: as listas que a 07 mostra
  são os recusados (`jogos_sem_wrapper.txt`) e os dispensados
  (`launch_dialog_dismissed.json`); a das exceções (`steam_input_apps.txt`) só é
  lida por `_steam_input_excecao_status`. O `efetiva` segue na assinatura e não
  vai mais à tela. O comentário R-06 ganhou nota datada; o arquivo manteve as
  2253 linhas.

### As réguas

* **nova** `tests/unit/test_o_chip_do_perfil_tem_um_dono_so.py` — as três linhas
  do piloto (`pacote_da_pagina`, `normalizar`, `topo` com `setdefault`) nas dez
  abas, com o daemon respondendo `active_profile: null` e um perfil no disco do
  lar de mentira (conferido contra o `passwd`). Cobra o mesmo nome nas dez, e tem
  a metade que recusa: um pacote dublado que emite `perfil` chega ao chip.
* `tests/unit/test_nenhuma_frase_de_aviso_chega_a_tela.py` — duas âncoras novas,
  como FRASE QUE SAIU, porque nenhuma tem constante de dono: «a barra não
  obedece» (comum à frase que o daemon monta em `sinal_da_barra` e à reserva que
  saiu) e «jogo(s) —» (qualquer narração depois da contagem). Dois testes pelo
  caminho do produto: o `pacote()` da 08 com os dois controles condenados, e
  `a07_lancadores._o_que_a_steam_poe_no_meio` nos três estados da exceção.
* `tests/unit/test_a_luz_nao_acende_o_botao_do_card.py` — as três classes da razão
  deram lugar a nota datada e a `TestARazaoSaiuDoCard` (o bloco só com o botão e
  a espera; o nascimento condenado do payload não chega ao card).
* `tests/unit/test_steam_input_d33_nomeia_o_jogo.py` — nota datada; os três
  valores de `efetiva` dão a mesma linha, sem travessão depois da contagem.

**DOIS ARQUIVOS DE TESTE FORA DA POSSE MUDARAM DE CONTRATO**, com nota datada:

* `tests/unit/test_a08_o_veredito_e_a_mesa_de_radio_dela.py` —
  `test_a_razao_do_nascimento_nao_chega_a_dica` passa pelo tique com os dois
  controles condenados; a linha 8 da tabela de mordidas diz que caducou.
* `tests/unit/test_r06_status_honesto.py` — os três casos cobram a ausência da
  narração e a LEITURA (`_steam_input_excecao_status`), que continua distinguindo
  configurada de efetiva.

pytest pontual: réguas do chip, do sufixo e da 08 — 142 passed; a luz, as frases,
a espera do PS, o painel GTK e as vizinhas da 08 — 190 passed.
`scripts/validar-citacoes-de-linha.py --all`: OK, 3291 citações.
`tests/unit/test_portao_o_par_com_metade_ligada.py`: 16 passed. `ruff check` nos
onze arquivos tocados: limpo.

## Qual mordida prova

**A régua nova sobre o HEAD, antes de qualquer cura:** `1 failed, 2 passed`, com
`{'03-gatilhos.html': '', '04-iluminacao.html': ''}`.

Cada mordida abaixo guardou o `git diff`, arrancou a cura, conferiu que a
sabotagem entrou, rodou a régua, devolveu os bytes guardados e conferiu o
`git diff` idêntico (script no rascunho, fora do repositório).

| | cura arrancada | com a cura fora | de volta |
| --- | --- | --- | --- |
| M1 | a razão na `dica_da_luz`: a 08 e o `secao_controles.py` do HEAD | `4 failed` — `test_a_dica_da_luz_nao_traz_a_razao_do_nascimento`, `test_a_razao_do_nascimento_nao_chega_a_dica` e os dois de `TestARazaoSaiuDoCard` | `4 passed`, diff IDÊNTICO |
| M2 | `"perfil": ctx.state.get("active_profile") or ""` de volta só na 03 | `1 failed, 2 passed` — `{'03-gatilhos.html': ''}` | `3 passed`, diff IDÊNTICO |
| M3 | a mesma linha de volta só na 04 | `1 failed, 2 passed` — `{'04-iluminacao.html': ''}` | `3 passed`, diff IDÊNTICO |
| M4 | a narração no sufixo: `emulation_actions.py` do HEAD | `5 failed, 1 passed` — a régua do sufixo (`['a narração do sufixo']`), a da D-33 (`assert 3 == 1`) e os três de `TestStatusDaAba` | `6 passed`, diff IDÊNTICO |

O caso que fica verde na M4 é `test_sem_allowlist_a_linha_nao_muda`, e é o
desenho: sem exceção não há sufixo.

**A MORDIDA NA TELA:** a M4 também rodou no piloto, com a exceção dublada. A 07
voltou a dizer «· Exceção por jogo: 1 jogo(s) — controle liberado agora»; devolvido
o arquivo, o `git diff` saiu idêntico e a linha voltou a terminar na contagem.

## O que NÃO verifiquei

* **Uma exceção de verdade no Steam Input.** A máquina dela não tem
  `steam_input_apps.txt`. A 07 foi medida na tela com a leitura dublada no estado
  efetivo; os estados escondido e sem controle físico, só no unitário.
* **A dica da luz por cabo.** Só havia um DualSense, pelo rádio. Por cabo a razão
  já não entrava (`no_radio`), e isso não foi remedido na tela.
* **O `active_profile` que o daemon respondia.** Não perguntei ao daemon. O ANTES
  («—» na 03 e na 04, o nome nas outras oito) só se explica com ele nulo e o dono
  achando o perfil no disco — é inferência, e a régua reproduz exatamente esse
  estado.
* **A janela GTK.** `TestARazaoSaiuDoCard` roda num `Gtk.OffscreenWindow`, e a
  janela não é produto desde 06/09.
* **Aparelho, bancada, quatro controles, cabo e rádio juntos, a janela instalada,
  a suíte inteira e o olho dela** (PROVA-DE-TELA-01).

## O que sobrou para o próximo

1. **A PLANILHA DE PARIDADE, e é de quem coordena** — `docs/data/paridade-gtk-html.csv`
   é `nao_toca:`. A linha 297 («A luz não acende» — a RAZÃO de a cura ser
   oferecida, `DIFERENTE`, sinal `frase_do_nascimento` `PRESENTE` no escopo da 08)
   descreve uma feature que saiu dos dois lados; o sinal continua aparecendo
   porque a nota datada da docstring da 08 o nomeia, e o `PRESENTE` aceita prosa
   por desenho do `scripts/check_paridade_gtk_html.py`. A linha 299 diz, no lado
   HTML, que `dica_da_luz` acrescenta a razão quando o daemon condena. As duas
   pedem a forma «SAIU DOS DOIS LADOS» que a FRASES-E-DICAS-02 deu à 299.
2. **Citações por número para `secao_controles.py`.** O arquivo encolheu 50 linhas,
   32 delas antes das citações. A de
   `src/hefesto_dualsense4unix/interface/pacotes/a02_controles.py:1942` era a
   única certa no HEAD (a linha 956, do `_mic_declarado`), e hoje o alvo está na
   924; a 02 é `nao_toca:`. As outras quatro já apontavam para linha errada no
   HEAD: `a02_controles.py` nas linhas 2871 e 4122, `aba09.py` na 706 (que vai
   também para a 09 publicada) e `app/widgets/campo_de_busca.py` na 28. Os dois
   oráculos ficaram verdes: nenhuma promete símbolo colado. Reapontar pelo
   símbolo é de quem tem a posse.
3. **O `efetiva` ficou sem uso na tela.** `a07_lancadores._o_que_a_steam_poe_no_meio`
   (fora da posse) segue chamando `_steam_input_excecao_status`, que varre os
   hidraw a cada leitura por um valor que não chega mais à 07. Tirar o parâmetro
   pede mexer na 07.
4. **Vermelho anterior, não desta sprint:**
   `tests/unit/test_a_aba_03_gatilhos_fecha_as_linhas.py::test_o_piloto_le_a_chave_recado_e_a_tira_da_pintura`
   procura o trecho `"recado" in resposta` no `hefesto_vivo.py`, e o HEAD
   `e1c7d96b` não o tem (o `git show` dá zero ocorrências). O piloto é `nao_toca:`.
5. **O resto da seção GTK.** `_BlocoDaLuz` e `_PainelDosControles` são da janela
   aposentada; a sprint mandou tirar só a razão, e o resto ficou.

**PORTÕES:** a corrida completa roda com esta entrega no índice, depois do
`git add -A`, e o resultado vai na mensagem do commit.
