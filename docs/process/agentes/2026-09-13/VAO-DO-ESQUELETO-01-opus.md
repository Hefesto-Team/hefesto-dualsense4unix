# VAO-DO-ESQUELETO-01 — entrega (opus, agente IMPLEMENTA)

Árvore `hefesto-voo/VAO-DO-ESQUELETO-01-opus`, branch
`voo/VAO-DO-ESQUELETO-01-opus`, nascida de `onda/1309` = `249af1f6` (conferido).
Absorve o §4.1 da PERFIS-TIRA-BUSCA-ATIVO-01. `bancada: false`: nenhum gesto foi
mandado ao daemon; o piloto só leu estado. Toda janela nasceu no Xvfb da guarda,
e os perfis dela foram copiados antes e conferidos por md5 depois de cada uma
das três corridas do piloto (159 arquivos, intactos nas três).

A rota corrigida da sprint vale: **o layout do vão não mudou** (caminho c).
O que se executou é o resíduo, e ele tem dois itens no `topo.html`.

## O que mudou

### 1. A fita não salta mais ao trocar de aba — `interface/topo.html`

**Remedido antes de curar, e o número mudou.** Depois da ALTURA-DA-VISTA-01 a
faixa de cabeçalho saiu e o salto é de **1 px**, não de 2:

| instrumento | antes | depois |
| --- | --- | --- |
| Chrome, dez publicadas, 1918x840 e 1212x809 | linha 52 (01, 02, 08) / 51 (sete) · `.miolo` y 111 / 110 | **52 nas dez · y 111 nas dez** |
| piloto oculto, daemon vivo, 11 cliques na tira | linha 52 / 51 · y 111 / 110 | **52 nos 11 cliques · y 111** |

**A causa:** a linha do alvo mede o filho mais alto. O chip tinha 28 px com
borda de 1 e 30 com borda de 2; o «Perfil ativo» mede 29. Nas abas que
escolhem, o chip do plástico (borda 2) manda e a linha dá 52; nas de fita
inerte a borda cai para 1, o «Perfil ativo» passa a mandar e a linha dá 51.

**A cura escrita na sprint caiu ao medir.** Medido com CSS injetado nas dez
páginas publicadas, sem tocar arquivo, em quatro estados que o produto pinta:

| folha | como publicado | sem cor lida (rádio) | só «Todos» | com cor lida (cabo) |
| --- | --- | --- | --- | --- |
| hoje | 51 / 52 | 51 | 51 | 51 / 52 |
| 2 px no chip inerte (a da sprint) | **07 em 51**, nove em 52 · **seis fitas inertes com duas caras** | 51 | 51 | 07 em 51 · seis com duas caras |
| borda + ar = 7 px (a desta entrega) | **52** | **52** | **52** | **52** |

A da sprint devolve ao chip inerte a espessura própria que ela mandou tirar em
08/09 (*«cinza como os demais»*, régua `test_a_fita_inerte_nao_acende_ninguem.py`),
não alcança a 07 — cuja fita nasce só com o «Todos» — e mantém a aba mudando
de altura no primeiro tique, quando a pintura troca a fita.

**A cura foi na causa.** A espessura ganhou um dono, `--borda-do-chip`, e o ar
de cima e de baixo do chip da fita lê dele:

```css
.chip{--borda-do-chip:1px; … border:var(--borda-do-chip) solid var(--linha); …}
.chip.plastico{--borda-do-chip:2px}
.fita.inerte .chip.plastico{border-color:var(--border-sutil);--borda-do-chip:1px}
.fita .chip{padding-top:calc(7px - var(--borda-do-chip));
            padding-bottom:calc(7px - var(--borda-do-chip))}
```

Os 7 px são o chip vivo do plástico (2 + 5): **a linha das abas que escolhem não
muda um pixel**; todo chip de borda 1 — inclusive o «Todos» das dez abas, que
passa de 28 a 30 — ganha 1 px de ar em cima e embaixo. O ar horizontal
não mudou. O `padding` é só da `.fita`: o `.mascara .chip` da 01 e o chip das
colunas da 03 não foram tocados. O comentário da regra de 08/09 que dizia
«a largura vem de `.fita.inerte .chip.plastico` (1px)» foi corrigido para a
variável.

`gui/ponte_da_tela.CROMO_DA_JANELA = 143` era o caso apertado (linha de 52) e
passou a ser o único caso: o número continua exato.

### 2. O chip «Perfil ativo» nasce «—» — `interface/topo.html`

O literal do exemplo do desenho saiu das **vinte** páginas (dez da bancada, dez
publicadas). O «—» é o que `pacotes.topo()` escreve quando nada está valendo.
O endereço `data-campo="perfil"` continua no chip — medido nas vinte.

### 3. Regeradas e publicadas as dez

`interface/regerar.py` (3,5 s) e `scripts/check_o_desenho_aprovado.py
--publicar` → `10 mudou/mudaram de fato`; o portão do desenho aprovado fica em
`o produto está atrás . 0`. O diff de cada página é só o bloco do `topo.html`.

### 4. As réguas

* **nova** `tests/unit/test_a_fita_nao_salta_ao_trocar_de_aba.py` — Chrome
  headless, as dez publicadas nos quatro estados; cobra a causa (todo chip da
  fita com a mesma altura), a queixa (mesma linha e mesmo `y` do `.miolo` nas
  dez) e a pintura (uma altura em qualquer estado), e que a fita inerte siga com
  uma espessura só. Nenhum número digitado: as abas são comparadas entre si.
* **nova** `tests/unit/test_a_aba_perfis_segue_o_perfil_que_vale.py` — pergunta
  a `pacotes.topo()` o que ele escreve sem perfil e cobra esse valor nas vinte
  páginas, com o endereço; a metade positiva cobra que o pintor nomeia o perfil
  ativo.
* **ajustada** `tests/unit/test_regua_de_tela_a_aba_controles.py` — a cena fixa
  exigia o nome do exemplo no chip; passa a perguntar o mesmo dono. Sem isso ela
  mediria o desenho de ontem.

### O clique

O piloto (`hefesto_vivo.Piloto`, oculto, vista 1918x840) clicou o `a.aba` da
tira pela ponte JS, na ordem 01 → 03 → 08 → 04 → 02 → 07 → 05 → 06 → 09 → 10 →
01, esperou a carga e o tique, e leu o DOM. A mesa tinha um DualSense (a
contagem dizia `1 controle: 0 USB · 1 BT`), com a cor lida, e a fita pintou um
chip do plástico em cada aba:

```
antes    01 52/111 · 03 51/110 · 08 52/111 · 04 51/110 · 02 52/111 · 07 51/110 · … · 01 52/111
         RESUMO linhas distintas=[51, 52] miolo.y distintos=[110, 111] medidas=11 de 11
depois   RESUMO linhas distintas=[52] miolo.y distintos=[111] medidas=11 de 11
         chips: plastico on:2px:30 (01, 08, 02) · plastico on:1px:30 (as sete)
```

### As fotos

| | Chrome, publicado (recorte do topo, escala 2) | piloto oculto, daemon vivo |
| --- | --- | --- |
| antes | `VAO-DO-ESQUELETO-01-antes-topo-03-gatilhos.png` | `VAO-DO-ESQUELETO-01-antes-piloto-03-gatilhos.png` |
| depois | `VAO-DO-ESQUELETO-01-depois-topo-03-gatilhos.png` | `VAO-DO-ESQUELETO-01-depois-piloto-03-gatilhos.png` |

No recorte do topo o chip passa de «Mortal Kombat» a «—». O pixel da linha não
se lê a olho; o número acima é a prova.

## Qual mordida prova

Cada mordida arrancou a cura do `topo.html`, regerou e publicou as dez, rodou a
régua, devolveu a cura, regerou e publicou de novo, e comparou `git diff` com o
da cura: **idêntico nas duas**.

**Mordida 1 — sem o ar que lê a borda** (a regra `.fita .chip{padding-top/bottom}`
arrancada):

```
E  com-cor-lida · linha: {52: ['01', '02', '08'], 51: ['03', '04', '05', '06', '07', '09', '10']}
E  com-cor-lida · miolo: {111: ['01', '02', '08'], 110: ['03', '04', '05', '06', '07', '09', '10']}
E  AssertionError: a linha do alvo mede [51, 52] conforme o estado da fita:
   como-publicado=[51, 52]; sem-cor-lida=[51]; so-todos=[51]; com-cor-lida=[51, 52]
FAILED …::test_todo_chip_da_fita_tem_a_mesma_altura
FAILED …::test_a_linha_do_alvo_mede_o_mesmo_nas_dez
FAILED …::test_a_pintura_nao_move_a_linha_do_alvo
3 failed, 1 passed in 22.64s
```

E no produto, o piloto na mesma árvore quebrada:
`RESUMO linhas distintas=[51, 52] miolo.y distintos=[110, 111] medidas=11 de 11`.
O caso que passa com a cura arrancada é o da espessura única na fita inerte — é
de propósito: ele reprova a cura da sprint, não a falta desta.

**Mordida 2 — o nome do exemplo de volta ao chip:**

```
E  AssertionError: bancada/10-perfis.html: o chip nasce dizendo 'Mortal Kombat' — um perfil
   que o produto não afirmou. Sem pintura ele tem de dizer '—', que é o que
   `pacotes.topo()` escreve quando nada está valendo.
FAILED …::test_as_dez_paginas_nascem_sem_nome_de_perfil[publicado/01-jogar.html]
… (as vinte)
20 failed, 1 passed in 0.60s
```

**Com a cura devolvida:** `25 passed in 23.06s` nas duas réguas novas. Com as
vizinhas (`test_a_fita_inerte_nao_acende_ninguem.py`,
`test_o_rodape_nao_nomeia_o_perfil_errado.py`,
`test_a_aba_perfis_manda_para_um_endereco_que_existe.py`,
`test_regua_de_tela_a_aba_controles.py`): `62 passed in 37.49s`.
`ruff check src/ tests/`: `All checks passed!`.

**Portões:** `bash scripts/portoes.sh` completo, depois do `git add -A`. A
primeira corrida deu 59 de 60 e reprovou `acentuacao`: a régua nova usava o
verbo *medir* no imperfeito, que o portão lê como «média» — a mesma armadilha
do `678b8964`. Trocado o verbo, a segunda corrida é a que fecha esta entrega.

## O que NÃO verifiquei

* **Os estados «sem cor lida», «só Todos» e «cabo» foram simulados no Chrome**,
  trocando a classe dos chips no DOM das páginas publicadas. No aparelho só
  existiu um estado: um DualSense pelo rádio com a cor lida. Quatro controles,
  controle sem cor e mesa vazia no piloto: não medidos.
* **O olho dela** (PROVA-DE-TELA-01). A mudança visível é 1 px de ar no chip
  da fita inerte e o «—» no chip do perfil antes da pintura.
* **A suíte inteira** — é de quem coordena.
* **A régua com teto do vão** — a rota diz que não nasce aqui. Remedi o vão
  para quem a escrever (fundo útil do `.miolo` menos o fim do último filho
  visível, dez publicadas):

  | vista | 01 | 02 | 03 | 04 | 05 | 06 | 07 | 08 | 09 | 10 |
  | --- | ---: | ---: | ---: | ---: | ---: | ---: | ---: | ---: | ---: | ---: |
  | 1918x840 | 245 | 0 | 262 | 105 | 125 | 124 | 0 | 266 | 101 | 0 |
  | 1212x809 | 214 | 0 | 231 | 74 | 94 | 93 | 0 | 204 | 70 | 0 |

  Os números da §2 (163 / 161 / 142) eram de antes de a faixa de cabeçalho sair
  e de a 01 perder a faixa; não valem mais.

## O que sobrou para o próximo

1. **O CHIP «PERFIL ATIVO» TEM UM SEGUNDO DONO NA 03 E NA 04, e ele está vivo.**
   Nas três corridas do piloto, com um perfil valendo, a 03 e a 04 pintaram
   «—» e as outras oito pintaram o nome — medido pelo DOM e visível na foto do
   piloto da 03. A causa está no fonte: `pacotes/a03_gatilhos.py` e
   `pacotes/a04_iluminacao.py` emitem `"perfil": ctx.state.get("active_profile") or ""`
   no pacote da aba, e o piloto só completa o cabeçalho com
   `carga["mesa"].setdefault(chave, valor)` (`hefesto_vivo.py`, no laço de
   `pacotes.topo(ctx)`). Com o daemon respondendo `active_profile` nulo, o
   valor cru e vazio da aba vence o nome que `perfil.nome_do_ativo` acha no
   disco. É a mesma doença que `a09_sistema.pacote` já curou («um pacote de aba
   só emite endereço DAQUELA página»). **Não toquei: os dois arquivos não são
   da posse desta sprint.** A cura provável é tirar a chave dos dois pacotes, e
   a régua é a do piloto: nenhuma aba pinta «—» enquanto outra pinta um nome.
2. **Três citações apontam o chip por número de linha que já não é o dele**:
   `pacotes/a10_perfis.py` (duas, «linha 1035») e o cabeçalho de
   `tests/unit/test_a_aba_perfis_manda_para_um_endereco_que_existe.py`. Antes
   desta entrega o chip já estava em outra linha da `10-perfis.html`. Reapontar
   por símbolo (`topo.html`, o chip «Perfil ativo»), não por aritmética.
3. **A PERFIS-TIRA-BUSCA-ATIVO-01 continua dizendo, no §4.1, que o chip nasce
   com o nome do exemplo** — fechou aqui. O arquivo dela não é desta posse.
4. **O vão das três abas (01, 03, 08)** segue de pé por decisão; ele só se cura
   com conteúdo, que é outra fila.

## O que a validação refez e corrigiu

Agente VALIDA/CORRIGE, mesma árvore e mesma branch, a partir de `54063e23`. O
python é o da venv dela com o `PYTHONPATH` desta árvore (import conferido em
`…-opus/src`). Os perfis foram copiados antes, e o md5 conferido depois de cada
corrida do piloto: 159 arquivos, intactos nas três.

### O que se confirmou, remedido do zero

* **As vinte páginas são as do gerador:** regerar e publicar sobre `54063e23`
  deixou a árvore limpa.
* **O salto, no Chrome**, com as páginas de `249af1f6` e da branch extraídas por
  `git archive` (vista 1918x840; a branch também em 1212x809):

  | estado da fita | base: linha / `y` do `.miolo` | branch |
  | --- | --- | --- |
  | como publicado | 52 e 111 (01, 02, 08) · 51 e 110 (sete) | 52 e 111 nas dez |
  | sem cor lida | 51 e 110 nas dez | 52 e 111 |
  | só «Todos» | 51 e 110 nas dez | 52 e 111 |
  | com cor lida | 52 (01, 02, 08) · 51 (sete) | 52 e 111 |

* **A cura escrita na sprint caiu mesmo:** injetada na base, a 07 fica em 51,
  «sem cor» e «só Todos» seguem em 51, e seis fitas inertes ficam com bordas de
  1 e de 2 px.
* **O clique, no piloto oculto:** 11 cliques no `a.aba` da tira, daemon vivo,
  um DualSense pelo rádio. Base (a árvore inteira de `249af1f6`): linhas
  `[51, 52]`, `y` `[110, 111]`, chip inerte `1px:28`. Branch: linhas `[52]`,
  `y` `[111]`, chip inerte `1px:30`. As fotos da 03 foram lidas nas duas pontas,
  e as duas estão pintadas.
* **Nenhum botão novo:** 254 `<button>` e 337 `data-gesto` nas dez publicadas,
  antes e depois, página a página; a contagem de `title` também não mudou. O diff
  das páginas é CSS, comentário e o «—»: nenhuma frase nova chega à tela.

### As mordidas, refeitas

Cada mordida confere na página publicada que a sabotagem entrou, roda a régua e
devolve por `git checkout`, regerando e publicando. Nas quatro a árvore voltou
limpa, idêntica ao commit.

| mordida | régua | resultado |
| --- | --- | --- |
| M1 · sem `.fita .chip{padding-top/bottom}` | `test_a_fita_nao_salta_ao_trocar_de_aba.py` | 3 failed, 1 passed · 52 em 01/02/08, 51 nas sete |
| M2 · o nome do exemplo de volta ao chip | `test_a_aba_perfis_segue_o_perfil_que_vale.py` + `test_regua_de_tela_a_aba_controles.py` | 21 failed · as vinte páginas e a cena fixa |
| M3 · `pacotes.topo` sem o nome do ativo | `test_a_aba_perfis_segue_o_perfil_que_vale.py` | 1 failed · `test_o_pintor_nomeia_o_perfil_que_vale` |
| M4 · a cura da sprint (2 px no chip inerte) | `test_a_fita_nao_salta_ao_trocar_de_aba.py` + `test_a_fita_inerte_nao_acende_ninguem.py` | 3 failed · a espessura única e as duas da regra de 08/09 |

### O que corrigi

1. **«Nenhuma aba que escolhe muda um pixel» era falso, e estava em dois
   lugares.** A linha não muda, mas o «Todos» das abas que escolhem passa de 28
   a 30 px (Chrome, chip a chip). Substituído no comentário do `topo.html`,
   com as dez regeradas e publicadas, e no §1 desta entrega.
2. **`gui/ponte_da_tela.py`, comentário do `CROMO_DA_JANELA`.** Dizia que a
   linha do alvo tem 51 px em sete abas e 52 em três, e esta cura tornou isso
   falso. Reescrito com o mesmo número de linhas, para nenhuma citação por
   linha se deslocar. O 143 não muda.

### Arquivos fora da posse, e a razão

* `tests/unit/test_regua_de_tela_a_aba_controles.py` (do implementador): a cena
  fixa cobrava o literal que a cura tirou. A M2 prova que a régua segue
  mordendo: com o literal de volta ela reprova.
* `src/hefesto_dualsense4unix/gui/ponte_da_tela.py` (desta validação): só
  comentário, com um fato que esta cura derrubou. Nenhuma sprint do lote
  1309-onda1 tem o arquivo na posse — conferido no frontmatter da F1-REMAPEAR,
  FRASES-E-DICAS-01, FRASES-E-DICAS-02, JOGO-SEM-EXCLUSIVIDADE-01 e
  LIGHTBAR-NA-STEAM-01.
* os quatro PNG desta pasta: as fotos da entrega.

### O que não corrigi, e por quê

**O «—» da 03 e da 04 com um perfil valendo** (item 1 acima) está confirmado
nas duas pontas: em `249af1f6` a 03 e a 04 já pintavam «—» enquanto as outras
oito pintavam o nome. É anterior a esta sprint. Os dois arquivos da cura têm dono
na mesma onda: `pacotes/a03_gatilhos.py` é da FRASES-E-DICAS-02 e
`pacotes/a04_iluminacao.py`, da FRASES-E-DICAS-01. Curar aqui obrigaria a costura
a escolher entre duas escritas no mesmo arquivo.

### A armadilha que custou uma corrida

A primeira corrida do piloto «antes» extraiu da base só o `src/` e o
`docs/data/`. A leitura voltou com 11 medidas de 11, mas a foto da 03 mostrou a
cena fixa do desenho: a pintura tinha caído num arquivo de `docs/process/` que
faltava, e a medida não acusou nada. Refeita com a árvore inteira. **Medida de
piloto só vale com a foto lida.**

### Réguas e portões

Sete réguas pontuais (as duas novas, a ajustada e quatro vizinhas): 81 passed.
`ruff check src/ tests/`: limpo. `check_o_desenho_aprovado.py`: OK.
