# A-MARCA-DA-DEGRADACAO-01 — o asterisco que nunca acende e o gerador que escreve antes de conferir (IMPLEMENTA, opus)

Sprint: [A-MARCA-DA-DEGRADACAO-01](../../sprints/2026-09-13-A-MARCA-DA-DEGRADACAO-01-o-asterisco-que-nunca-acende-e-o-gerador-que-escreve-antes-de-conferir.md)
· lote `1309-onda5` · branch `voo/A-MARCA-DA-DEGRADACAO-01-opus` · base `9639f1df`
(conferida com `git log -1` antes de tocar em nada).

Os achados vieram da validação da RESTOS-DA-ONDA-DOIS-01
(`docs/process/agentes/2026-09-13/RESTOS-DA-ONDA-DOIS-01-opus.md`, item 3 de
«o que sobrou» e a V2a). A entrega da RESTOS-DA-ONDA-TRES-01 não fala da marca
nem da autoconferência.

## O que mudou

### §I.1 — a marca saiu inteira, dos dois lados

| arquivo | o que mudou |
| --- | --- |
| `interface/aba01.py` | O `<sup class="degradou" data-campo="degradou-cartao" …>` saiu do cartão (a mesma linha, sem mudar a contagem). As duas regras `.cartao .degradou` e `.cartao .degradou[title]` deram lugar a uma nota datada de **12 linhas, as mesmas 12**, porque `docs/data/paridade-gtk-html.csv` cita `aba01.py:1087` e cinco linhas abaixo. A docstring do cartão deixou de citar o `degradou` entre os elementos `display:none`. O item 13 do `_conferir` foi INVERTIDO: reprova o `<sup>` e o endereço no miolo, e `.degradou` ou `[title` em qualquer `<style>` da página (sem os comentários de CSS). |
| `interface/aba02.py` | O `<sup>` de `mascara-degradou` saiu do `.leia`. O bloco CSS (15 linhas) e o comentário HTML do card (18 linhas, repetido quatro vezes na página) viraram notas datadas de mesmo tamanho. Os dois comentários que citavam `.degradou[title]` (a docstring de `linha_de_volume` e a nota do botão de som em duas cores) foram reescritos no lugar. O `_conferir` ganhou a mesma verificação de dois lados da 01. |
| `interface/pacotes/a01_jogar.py` | `degradou-cartao` saiu do `POR_CARTAO` e do `pacote`, e `degradacao_de` saiu do import. As duas notas no lugar têm as mesmas 13 e 6 linhas: o arquivo segue com **2952 linhas**, e as 46 citações da paridade continuam no símbolo certo. |
| `interface/pacotes/a02_controles.py` | `mascara-degradou` saiu do card e `degradacao_de` do import. A linha a menos do import foi devolvida no comentário de 02/09 que contava o `texto_degradacao` entre os dois donos alcançados (agora diz que ele deixou de ser). O arquivo segue com **4412 linhas**. |
| `interface/pacotes/__init__.py` | `degradacao_de` saiu (nenhum leitor sobrou), e a linha `vpad_motivo` da tabela de 02/09 diz que a HTML não lê a chave de propósito. As 24 linhas a menos ficam depois de toda citação da paridade neste arquivo. |

A queda para `uinput` que ninguém escolheu não sumiu do produto: o daemon
continua publicando `vpad_backend` e `vpad_motivo` no estado e diz a queda no
diário (`vpad_degradado`, em `daemon/subsystems/gamepad.py`). A regra de não
narrar defeito na tela é a palavra dela de 07/09, *«o layout não informa os
nossos defeitos»*, citada no comentário «A RAZÃO DEIXOU DE CONFESSAR» de
`interface/aba01.py`; e a ordem de tirar da tela o que avisa é a mensagem dela
no topo de `docs/process/sprints/2026-09-13-A-TERCEIRA-LISTA-DELA-INDICE.md`
(*«esse tipo de info segue aparecendo nas abas»*, *«esse tipo tambem tem que
parar de aparecer»*). A marca tinha nascido da decisão [07] do PO, registrada em
`docs/process/2026-09-04-O-PO-DECIDE-as-54-e-os-sete-conflitos.md`.

### §I.2 — o inventário dos seletores `[title]`

`grep -n "\[title"` nos dez geradores, no `topo.html` e no resto de `interface/`:

| onde | seletor | destino |
| --- | --- | --- |
| `aba01.py` (CSS) | `.cartao .degradou[title]{display:inline-block}` | **saiu** com a marca (§D.1) |
| `aba02.py` (CSS) | `.degradou[title]{display:inline-block}` | **saiu** com a marca (§D.1) |
| `aba03.py` a `aba10.py` | nenhum | — |
| `topo.html` (`nao_toca`) | nenhum | só listado |
| `hefesto_vivo.py` (`nao_toca`) | `raiz.querySelectorAll('[title]')` e `document.querySelector('[title]')` | só listado: é JavaScript da camada de dicas, que LÊ o `title` para levá-lo ao `data-hef-dica`; não é regra de pintura |

Os `[title]` que sobram em `aba02.py` são prosa sobre a cura da guarda do
alto-falante (RESTOS-DA-ONDA-DOIS-01), dentro de comentário. A régua nova
cobra, nas dez páginas da bancada e do publicado, que nenhuma folha decida
pintura por `[title]`.

### §I.3 — os dez geradores conferem antes de escrever

Os dez tinham a forma do §E.3: `monta()` grava a página e só depois a
autoconferência a lê (a 07 e a 08 fazem a régua sobre o HTML já gravado; a 09
confere o miolo no import, mas a conta da fita vem depois de `monta()`; a 04
tinha uma guarda de 07/09 que RESTAURAVA depois da recusa, só nela).

O `__main__` de cada um passou a: guardar a bancada de verdade
(`onde.saida()`), criar uma bancada provisória em `$TMPDIR/hefesto-prova-NN-*`
com as páginas vizinhas copiadas (a tira de abas e algumas réguas perguntam se
elas existem), apontar o desvio `HEFESTO_BANCADA` para ela, gerar e conferir
ali, e só então copiar a página para a bancada de verdade e apagar o
provisório. Recusada, a página fica no provisório para quem quiser olhar, e a
bancada não muda um byte. A razão inteira mora no fim do `aba04.py`, que
substituiu a guarda antiga; os outros nove apontam para lá.

O lugar certo deste bloco é `onde.py`, dono único da escrita, que não é desta
posse — ele ficou repetido nos dez `__main__` (ver «o que sobrou»). Os blocos
foram postos só no fim de cada arquivo, depois de toda citação por número.

### §I.4 — regeração e publicação

Os dez geradores rodaram na árvore da sprint (lar desviado, guarda no `.sh`):
**rc=0 nos dez**, só `mockup/01-jogar.html` e `mockup/02-controles.html`
mudaram, as outras oito saíram byte a byte iguais, e nenhum provisório sobrou.
`scripts/check_o_desenho_aprovado.py --publicar 01 02`: «2 mudou/mudaram de fato».

| página | `data-gesto` em `9639f1df` → agora | `<button` em `9639f1df` → agora | `class="degradou"` em `9639f1df` → agora |
| --- | --- | --- | --- |
| `01-jogar.html` (bancada e publicado) | 23 → 23 | 5 → 5 | 4 → 0 |
| `02-controles.html` (bancada e publicado) | 55 → 55 | 43 → 43 | 4 → 0 |

(Contado com `git show 9639f1df:<página>` e com o arquivo do disco. Os
`.degradou` e `mascara-degradou` que ainda aparecem no texto das páginas estão
só dentro das notas datadas, em comentário.)

As fotos, pelo Playwright headless (`interface/olhar.py --publicado`, sem
`--doc`): `A-MARCA-DA-DEGRADACAO-01-ANTES-01-publicado.png`,
`…-DEPOIS-01-publicado.png`, `…-ANTES-02-publicado.png`,
`…-DEPOIS-02-publicado.png`, nesta pasta. **ANTES e DEPOIS saíram com o mesmo
md5** nas duas abas: o asterisco nascia `display:none` e nunca acendeu, então
tirá-lo não move um pixel.

### As réguas que exigiam a marca

| régua | o que conferia antes | o que confere agora |
| --- | --- | --- |
| `test_os_donos_de_fato.py::TestDegradacaoDe` (4 casos) | a frase de `degradacao_de` para três entradas e a delegação a `texto_degradacao` | saiu com a função; a frase segue com dono e régua na GTK (`test_status_cards.py`, não tocado), e uma nota datada ficou no lugar |
| `test_a_aba_01_jogar_fecha_as_linhas.py::test_a_marca_da_degradacao_tem_as_duas_condicoes` | o cartão emitia `degradou-cartao` só com backend `uinput` E motivo, com a frase do dono | saiu; a AUSÊNCIA é `test_o_cartao_da_01_nao_emite_a_marca` |
| `test_a_aba_02_controles_fecha_as_linhas.py::test_o_motivo_da_degradacao_chega_ao_card` e `::test_sem_degradacao_o_campo_vai_vazio_e_a_marca_some` | `mascara-degradou` igual a `degradacao_de(entry)`, e vazio sem motivo | saíram; a AUSÊNCIA é `test_o_card_da_02_nao_emite_a_marca` |
| `test_a_aba_02_controles_fecha_as_linhas.py::test_a_marca_da_degradacao_so_aparece_com_motivo` e o trecho do `sup` no JS da fixture `desenhado` | no Chrome headless, `.degradou` com `display:none` sem `title` e visível com `title` | saíram; `test_a_pagina_nao_tem_a_marca` e `test_nenhuma_folha_das_dez_decide_pintura_por_title` |

**Régua nova, fora do `cria:` da sprint** (o despacho pede a mordida da escrita
antes da conferência, e não havia régua onde ela coubesse):
`tests/unit/test_a_marca_que_nunca_acende_e_o_gerador_que_confere.py` — o
controle de prova degrada de verdade; o cartão da 01 e o card da 02 não emitem a
marca (o endereço entra à força na lista da 02, senão o filtro
`_so_se_a_pagina_tiver` a esconderia); a 01 e a 02 sem o `<sup>`, sem o endereço
e sem `.degradou`, na bancada e no publicado; nenhuma folha das dez com
`[title`; e, para cada um dos dez geradores, a primeira escrita sabotada
(grava um documento diferente e recusa) deixa a bancada com o mesmo md5 e a
saída recusada no provisório, e sem sabotagem a página chega a uma bancada
envenenada e o provisório é apagado.

## Qual mordida prova

As quatro rodaram em série num `.sh` com o lar desviado e `git checkout` da
`interface/` e do `mockup/` no `trap`, e a árvore voltou limpa.

| # | mordida | o que se viu | devolvida |
| --- | --- | --- | --- |
| M1 | o `<sup>` de volta ao gerador da 01 | gerador **rc=1**: «a marca da emulação degradada voltou ao cartão…»; `mockup/01` md5 `4ec4af057614` antes e depois | gerador rc=0 |
| M2a | a autoconferência da 06 levantando e a página alterada, **com a cura** | gerador **rc=1**; `mockup/06` md5 `9d24477dd502` antes e depois; a página com a mordida ficou em `hefesto-prova-06-*`; o `--publicar 06` seguinte: «**0** mudou de fato» | — |
| M2b | a MESMA mordida com o `__main__` da base `9639f1df` | gerador **rc=1**; `mockup/06` md5 `9d24477dd502` → `b777ad9d4513`; o `--publicar 06` seguinte: «**1** mudou de fato» — é o defeito da V2a, reproduzido | — |
| M2c | só o `__main__` da base na 06 | **1 failed**: `test_a_recusa_nao_chega_a_bancada[aba06.py]` | 1 passed |
| M3 | `"degradou-cartao"` de volta ao `a01_jogar.pacote` | **1 failed**: `test_o_cartao_da_01_nao_emite_a_marca` | 1 passed |
| M4 | o `<sup>` e `.degradou[title]` de volta à 02, autoconferência calada, regerada e publicada | **4 failed**: `test_a_pagina_nao_tem_a_marca[02-controles.html-bancada/publicado]` e `test_nenhuma_folha_das_dez_decide_pintura_por_title[bancada/publicado]` | 6 passed |

Réguas pontuais na árvore curada:

* a régua nova e as três editadas: **155 passed**;
* `tests/unit/portao_a_casa_sabe_e_o_produto_nao_faz.py`: **42 passed** (tirar
  `degradacao_de` não deixou o `texto_degradacao` sem caminho: a GTK o chama);
* `scripts/validar-citacoes-de-linha.py --all`: **OK, 3288 citações** — nenhuma
  citação de planilha deslocada;
* `scripts/check_o_desenho_aprovado.py`: OK, 13 páginas, nenhuma atrás;
* `ruff check` nos arquivos tocados: verde (o aviso de `# noqa` inválido em
  `a02_controles.py` na linha do «tá carregando tambem» já existia na base);
* as réguas que regeram páginas pelo desvio `HEFESTO_BANCADA`, porque os dez
  `__main__` mudaram: `test_os_dez_geradores_rodam.py`,
  `test_a_palavra_do_transporte_tem_um_dono_so.py` e a régua nova, **65
  passed**; mais nove vizinhas (`test_a_01_jogar_nao_oferece_gesto_em_lugar_vazio`,
  `test_a_04_iluminacao_o_gesto_esta_onde_deve`,
  `test_a_linha_de_ressalva_so_nasce_quando_ha`,
  `test_a_vibracao_nao_tem_clique_que_nao_responde`,
  `test_o_botao_cinza_diz_a_razao`, `test_os_leitores_do_glade_tem_dono`,
  `test_o_teto_da_vibracao_e_por_controle`,
  `test_o_pacote_cabe_na_pagina_publicada`,
  `test_nenhuma_frase_de_aviso_chega_a_tela`), **119 passed e 10 skipped**;
* **`bash scripts/portoes.sh`: 59 de 60 verdes.** O único vermelho é
  `paridade-gtk-html`, pelos dois `sinal-sumiu` das linhas 32 e 54 da
  planilha, que é `nao_toca` (item 1 de «o que sobrou»). A primeira corrida
  tinha mais dois vermelhos meus, curados antes desta: o glifo de nota musical
  nesta entrega (`saida-de-agente`) e a variável `modulo` sem acento no código
  da sabotagem (`acentuacao`).

## O que NÃO verifiquei

* **O WebKit do produto.** Não abri o piloto. Que a camada de dicas tira o
  `title` e o seletor nunca casava é medição da validação da
  RESTOS-DA-ONDA-DOIS-01, não minha. O que eu medi foi a página estática, as
  réguas e a foto do Chrome headless.
* **O evento `vpad_degradado` no diário do daemon.** Citado pelo código, não
  observado ao vivo; o daemon dela não foi tocado.
* **O ensaio `scripts/ensaios/a_jogar_diz_quem_e_o_primario.py`** (fora da
  posse), que ainda procura `[data-campo="degradou-cartao"]`: não rodei. Ele tem
  guarda para elemento ausente e deve ler `null`.
* **A suíte inteira**, por ordem do despacho: só as réguas pontuais listadas
  em «Qual mordida prova», e os portões.

## O que sobrou para o próximo

1. **`docs/data/paridade-gtk-html.csv`, linhas 32 e 54** (`nao_toca`). O portão
   `paridade-gtk-html` reprova com dois `sinal-sumiu`: a linha 32 espera
   `degradacao_de` em `pacotes/a01_jogar.py` (veredito IGUAL) e a 54 espera
   `"mascara-degradou": degradacao_de` em `pacotes/a02_controles.py` (veredito
   DIFERENTE). Não é deslocamento: a feature saiu da tela por esta sprint. Quem é
   dono da planilha muda o veredito das duas linhas; o portão diz com todas as
   letras que o sinal não se troca por outro que só passe.
2. **O registro da decisão da marca.** `docs/data/decisoes-dela.csv`
   (`D-02C-DEGRADACAO-VPAD`, `nao_toca`) e
   `docs/process/2026-09-05-AS-QUARENTA-E-UMA-DECISOES-DELA.md` (02-Q7, «FEITA»)
   ainda descrevem a marca como viva. A nota datada de que ela saiu é de quem
   cuida do registro.
3. **O bloco da bancada provisória está repetido nos dez `__main__`.** O dono
   natural é `interface/onde.py` (um gerenciador de contexto que devolva a
   bancada provisória e copie no fim), e com ele cada gerador volta a ter uma
   linha. `onde.py` não era desta posse.
4. **O ensaio `a_jogar_diz_quem_e_o_primario.py`**: o item 2 da docstring
   promete medir a marca, e a medida virou ausência. É de quem cuidar dos
   ensaios da Jogar.
5. **O que caiu da sprint:** o §D.1 diz que a palavra dela de 07/09 está
   «citada em `a01_jogar.py`»; na base ela estava citada em `aba01.py` (e em
   `a02_controles.py`), não no pacote da 01. Agora a nota do `POR_CARTAO` também
   a cita.

## O que a validação refez e corrigiu

VALIDA/CORRIGE, 13/09/2026, na mesma branch, sem confiar no relato. Nada foi
aberto na tela dela: os geradores, a publicação e as mordidas rodaram em `.sh`
com `set -uo pipefail`, um `export` por variável, o lar desviado (`HOME` e os
cinco `XDG_*` no rascunho), `HEFESTO_DUALSENSE4UNIX_SKIP_PRESET_SEED=1`, o
`TMPDIR` no rascunho e uma guarda que sai com `exit 1` se o `HOME` não for o
lar ou se o `XDG_RUNTIME_DIR` for o da sessão dela. O piloto não foi aberto.

### Refeito

**A posse.** O diff contra `9639f1df` cabe no `posse:` mais as quatro páginas
geradas, as três réguas que exigiam a marca, a entrega e a sprint. Ficam fora
dois arquivos, cada um com a razão medida: a régua nova (a mordida da escrita
antes da conferência não cabia em régua nenhuma, e as dez sabotagens dela
reprovam, ver abaixo) e o ensaio da Jogar, que esta validação corrigiu.

**Os botões e os gestos**, contados fora de comentário HTML nas dez páginas
publicadas e nas dez da bancada, na base e na branch:

| | base `9639f1df` | branch |
| --- | --- | --- |
| `<button` (vinte páginas, dez por pasta) | 253 por pasta | 253 por pasta |
| `data-gesto` | 346 por pasta | 346 por pasta |
| nomes de gesto perdidos ou novos, aba a aba | — | nenhum |
| `class="degradou"` | 8 por pasta (4 na 01, 4 na 02) | 0 |

A contagem da entrega dizia 55 `data-gesto` na 02: é a conta bruta, com os
comentários. Fora deles são 47 antes e 47 depois.

**As mordidas**, todas com a âncora exigida exatamente uma vez (sabotagem que
não acha onde morder aborta, em vez de passar calada), e cada uma devolvida com
`git checkout` e conferida com `git diff` limpo:

| # | mordida | o que se viu |
| --- | --- | --- |
| M1a | o `<sup>` de volta ao gerador da 01 | gerador **rc=1** («a marca da emulação degradada voltou ao cartão…»); `mockup/01` com o mesmo md5 antes e depois |
| M1b | o `<sup>` de volta e o item 13 do `_conferir` calado, regerada e publicada | **2 failed**: `test_a_pagina_nao_tem_a_marca[01-jogar.html-bancada]` e `[01-jogar.html-publicado]` |
| M2 | o `<sup>` de volta ao gerador da 02 | gerador **rc=1**; `mockup/02` com o mesmo md5 |
| M3a | a 06 grava a página alterada e recusa, **com a cura** | gerador **rc=1**; `mockup/06` com o mesmo md5; a recusada ficou no provisório com a marca da mordida; o `--publicar 06` seguinte: «0 mudou de fato» |
| M3b | a mesma recusa com o `aba06.py` inteiro da base | gerador **rc=1**; o md5 de `mockup/06` **mudou**; o `--publicar 06` seguinte: «1 mudou de fato» — o defeito da V2a reproduzido |
| M3c | só o `aba06.py` da base | `test_a_recusa_nao_chega_a_bancada[aba06.py]` **1 failed**, pela asserção do md5; devolvido, 1 passed |
| M3d | só o `aba02.py` da base (a forma do `SAIDA`, que grava duas vezes) | `test_a_recusa_nao_chega_a_bancada[aba02.py]` **1 failed**, pela asserção do md5 |
| M4a | `"degradou-cartao"` de volta ao `a01_jogar.pacote` | `test_o_cartao_da_01_nao_emite_a_marca` **1 failed** |
| M4b | `"mascara-degradou"` de volta ao card da 02 | `test_o_card_da_02_nao_emite_a_marca` **1 failed** |
| M5 | `.mordida-da-validacao[title]` na folha da **05**, regerada e publicada | `test_nenhuma_folha_das_dez_decide_pintura_por_title` **2 failed** (bancada e publicado), apontando a `05-vibracao.html` |

**O inventário dos `[title]`, reconferido.** Nenhuma folha `<style>` das vinte
páginas tem `[title`. O que sobra nas páginas é prosa dentro de comentário (2
na 01, 13 na 02). No resto de `interface/`, os dois `[title]` de
`hefesto_vivo.py` (`nao_toca`) são JavaScript da camada de dicas — `colher()`
lê o atributo e o leva para `data-hef-dica`, e `varrer()` só pergunta se ainda
há algum a colher —, e nenhum decide pintura. Nenhum seletor de pintura por
`[title]` ficou.

**Os dez geradores, lidos um a um.** Toda escrita de página passa por
`onde.pagina()` ou `onde.gravar()`, que resolvem o desvio na chamada, e o
`SAIDA` da 02 é calculado dentro do `__main__`, depois do desvio: nenhuma
escrita escapa da bancada provisória.

**As réguas.** As quatro da sprint: 155 passed. As vizinhas — os 127 arquivos
de `tests/unit` que citam `aba01`, `aba02`, `a01_jogar`, `a02_controles`,
`_conferir`, `desenho_aprovado`, `autoconfer`, `degradou`, `degradacao_de`,
`texto_degradacao` ou `vpad_motivo` —, em nove lotes de quinze, em série:
**2283 passed e 1 failed**. O vermelho é
`test_as_fotos_acompanham_a_versao.py::test_as_fotos_nao_ficam_atras_do_codigo_da_tela`,
e **ele já existe na base**: numa árvore destacada de `9639f1df` (removida
depois) a mesma régua dá 1 failed com «a interface mudou em f903d2b e as fotos
de `docs/usage/assets` são de cd6a836». As fotos da documentação são de quem
coordena, no fecho.

**As fotos**, pelo Playwright headless, sem `--doc`: a base (o `mockup/` de
`9639f1df`, que é byte a byte o publicado da base nas duas abas) e o publicado
da branch. As duas abas saíram com o **mesmo md5** antes e depois, e lidas elas
mostram os quatro cartões da 01 e os cards da 02 sem asterisco nenhum: sem
`title` o `<sup>` nascia `display:none`.

### Corrigido

Commit `2e500dd0`:

1. **O último leitor da marca.** `scripts/ensaios/a_jogar_diz_quem_e_o_primario.py`
   (fora da posse) ainda procurava `[data-campo="degradou-cartao"]`, prometia na
   docstring medir a marca e imprimia `degradou=` em toda cena — com a marca fora
   do cartão, o ensaio responderia `None` sobre um endereço que não existe mais.
   A leitura, as duas chaves do JavaScript e a coluna do relato saíram; a
   docstring e a cena 3 dizem que a marca saiu. O `§D.1` manda tirar as réguas
   que exigem a marca, e esta era uma delas. Conferido com `py_compile` e com
   `node --check` sobre o JavaScript do ensaio; o ensaio não foi rodado.
2. **Um `[title]` morto em prosa.** O comentário de `giro-no-jogo` em
   `interface/pacotes/a02_controles.py` dizia que a folha apaga a linha por
   `:not([title])`. O interruptor é o `aria-label` desde 11/09 (a regra
   `.faixa .no-jogo[aria-label]` de `aba02.py`), e o bloco que ele nomeava não
   existe com aquele nome. Reescrito no lugar, com o mesmo número de linhas.

### O que a validação não verificou, ou deixou

* **O WebKit do produto** e o evento `vpad_degradado` do daemon: não abri o
  piloto nem toquei no daemon dela.
* **Duas menções históricas à marca ficaram**, porque são registro datado e não
  leitor: o parágrafo da docstring do `cartao()` em `aba01.py` que conta os sete
  campos que nasceram só no ramo de cima, e o comentário de 04/09 em
  `tests/unit/portao_a_casa_sabe_e_o_produto_nao_faz.py` sobre a saída de
  `degradacao_de` da lista.
* **As citações da planilha.** Além do `sinal-sumiu`, as colunas de endereço
  das linhas 32 e 54 de `docs/data/paridade-gtk-html.csv` apontam para onde a
  marca estava: a de `pacotes/__init__.py` apontava `def degradacao_de` e hoje
  cai em `def normalizar`; as de `a01_jogar.py` e `a02_controles.py` caem nas
  notas datadas; a de `aba02.py` cai no `.leia` já sem o `<sup>`. O validador de
  citações não reprova, porque as linhas existem. É de quem é dono da planilha.
