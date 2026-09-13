# MIC-SEM-FONTE-01 — o cinza do microfone chega antes do arrasto (IMPLEMENTA, opus)

Sprint: [MIC-SEM-FONTE-01](../../sprints/2026-09-09-MIC-SEM-FONTE-01-a-razao-chega-depois-do-arrasto-e-a-tarja-cobre-a-linha-de-cima.md)
· branch `voo/MIC-SEM-FONTE-01-opus` · base `e1c7d96b` (= `onda/1309`, conferido)
· `bancada: false`: nenhum aparelho tocado, tudo com dublê.

O despacho mandava seguir as seções §D, §I e §V da sprint. **A sprint não tem
essas seções**: valeu a nota ROTA CORRIGIDA do topo, que manda só a metade do
cinza, com endereço próprio na moldura do microfone e nenhuma frase nova. A
metade da tarja morreu com a FRASES-E-DICAS-01, que está na base.

## O que mudou

| arquivo | o que mudou |
| --- | --- |
| `src/hefesto_dualsense4unix/interface/pacotes/a02_controles.py` | `MIC_SEM_ALVO`, `MIC_SEM_FONTE` e `microfone_apagado(entry)`, logo abaixo de `no_do_microfone`. O card ganha `"mic-apagado"`. Há três respostas: sem endereço dá `sem-alvo`; o daemon disse `canal_fonte` e ela é nula dá `sem-fonte`; há fonte, ou a chave não veio («não sei»), dá `""`. A regra do `som-sem-endereco` não mudou, e o comentário dele passou a dizer que ele veste só a moldura do alto-falante. |
| `src/hefesto_dualsense4unix/interface/aba02.py` | A moldura do microfone troca `data-campo="som-sem-endereco" … data-hef-atributo="title"` por `data-campo="mic-apagado" … data-hef-atributo="data-apagado"`. Na folha, `[data-apagado="sem-alvo"]` repete a guarda sem endereço de antes (linha, modos e os três cursores). `[data-apagado="sem-fonte"]` apaga só `.vol .trilho` e `.vol .n` e põe `not-allowed` no deslizante. O botão do microfone e os modos ficam acesos, porque o botão é o ato que pede o canal (`mic.canal.set`) e apagá-lo trancaria a única saída. |
| `mockup/02-controles.html` e `src/hefesto_dualsense4unix/interface/paginas/02-controles.html` | Regeradas por `aba02.py` e publicadas com `scripts/check_o_desenho_aprovado.py --publicar 02` (rc=0). O diff é o CSS acima e as quatro molduras do microfone. Nas duas páginas, antes e depois: 43 `<button>`, 55 `data-gesto`, 70 `title`, 23 `.ajuda`. |
| `tests/unit/test_o_cartao_diz_se_o_som_tem_para_onde_ir.py` | `_card` passa por `_cards`, para a mesa de quatro. Entra a seção 8, `TestOMicrofoneSemFonte`, com 8 casos: a fonte nula apaga o microfone e não o alto-falante; com fonte acende; sem a chave não há cinza; sem endereço apaga inteiro; a mesa mista apaga só os dois do rádio; a moldura do microfone tem endereço próprio na bancada e no publicado; e sem fonte só o deslizante apaga. |
| a sprint | `estado: feita`, com a linha de ESTADO. |
| **FORA DA POSSE**, porque o `citacoes-de-linha` reprovava | `docs/data/mapa-controles.csv`, linha 23 (`audio.microfone@dualsense`, `radio_detalhe`): `a02_controles.py:4102` (`mic_modo`) passou a `:4141`, e o docstring citado ao lado passou de `:4147` a `:4186`. Os dois foram achados pelo símbolo e pelo texto na árvore curada (`def mic_modo`; «A palavra dela sobre esta recusa»), e nenhuma célula medida mudou. `html/specs.html` foi regerado por `scripts/gerar-mapa.py`; o diff são os dois números e o carimbo. |

Nenhum botão novo. Nenhum texto novo chega à tela: o valor de `data-apagado` é
atributo, não texto visível.

**A TELA, NO PILOTO OCULTO.** O driver fica no rascunho, fora do git:
`driver_mic.py`. Ele roda com lar de mentira (`HOME`, `XDG_*` e
`XDG_RUNTIME_DIR` desviados, então o piloto nem alcança o socket do daemon dela
nem o servidor de som), `HEFESTO_DUALSENSE4UNIX_SKIP_PRESET_SEED=1`,
`sem_cor` e `sem_ondas`. `mesa_viva.estado_do_daemon` é dublado com a mesa
mista da §1: dois no cabo com a fonte publicada e dois no rádio com
`canal_fonte` nulo, na faixa `aa:bb:cc`. `ponte.mic_volume_set_detalhado`
também é dublado: devolve `sem_fonte` para os do rádio e `None` para os outros.
O ANTES é a base posta por `cp` das quatro cópias guardadas antes da primeira
edição, devolvida por `cp` com md5 conferido. Os perfis dela (159 arquivos)
ficaram iguais por md5 depois de cada corrida.

| medido no DOM, cartão do P2 (rádio) aberto | ANTES | DEPOIS |
| --- | --- | --- |
| `data-apagado` da moldura do microfone | ausente | `sem-fonte` |
| trilho e número do microfone (opacidade) | 1 e 1 | 0,45 e 0,45 |
| cursor do deslizante do microfone | `pointer` | `not-allowed` |
| botão do microfone (opacidade, cursor) | 1, `pointer` | 1, `pointer` |
| modos Virtual e Nativo (opacidade) | 1 | 1 |
| alto-falante (linha, cursor do deslizante) | 1, `pointer` | 1, `pointer` |
| P4, o outro do rádio | aceso | igual ao P2 |
| P1 e P3, no cabo | acesos | acesos |
| arrasto no deslizante do P2 (valor 37, `input` e `change`) | o dublê recebe o `uniq` do rádio e responde `sem_fonte`; `puxa-vol → hef-em-voo → hef-recusou → puxa-vol` (~1500 ms) | igual |
| a tela depois do arrasto | 0 `.hef-recado`; a frase fora do texto visível, de `title` e de `data-hef-dica` | igual |
| diário | `[gesto falhou] 02-controles.html · volume: …` | igual |

Fotos nesta pasta: `MIC-SEM-FONTE-01-ANTES-o-microfone-do-radio.png` e
`MIC-SEM-FONTE-01-DEPOIS-o-microfone-do-radio.png`. No DEPOIS, o trilho e o
número do microfone do P2 aparecem apagados, e o botão do microfone, os modos e
o bloco do alto-falante continuam iguais aos do ANTES.

**A CORRIDA CONTINUA COBERTA (§4.5).** O arrasto no cinza ainda chama o daemon,
e o `sem_fonte` ainda levanta `TEXTO_MIC_SEM_FONTE`, que agora vai ao diário e à
piscada da recusa. A régua é `tests/unit/test_o_volume_do_mic_nao_cai_no_vizinho.py`,
verde.

**RÉGUAS PONTUAIS, na árvore curada:** o arquivo da posse,
`test_o_volume_do_mic_nao_cai_no_vizinho`,
`test_nenhuma_frase_de_aviso_chega_a_tela`, `test_a02_as_ondas_sonoras_sao_reais`
e `test_portao_o_par_com_metade_ligada` deram 121 passed. O lote dos 136
arquivos de `tests/unit/` com `a02`, `aba02`, `controles`, `som`, `mic`,
`microfone`, `frase`, `lingua`, `palavra`, `casamento` ou `endereco` no nome deu
2172 passed e 2 xfailed. `ruff check` nos três arquivos: limpo.

## Qual mordida prova

Cada mordida arrancou a cura, rodou a régua, devolveu os quatro arquivos da 02
por `cp` das cópias da cura e conferiu o md5 (roteiro `mordidas.py` no
rascunho). Com a cura inteira de volta, o arquivo da posse deu 48 passed.

| | cura arrancada | com a cura fora |
| --- | --- | --- |
| M1 | `microfone_apagado` deixa de perguntar a fonte | `test_a_fonte_nula_apaga_o_microfone_e_nao_o_alto_falante` e `test_a_mesa_mista_apaga_so_os_dois_do_radio`: 2 failed, 6 passed |
| M2 | **a da ROTA**: a moldura do microfone volta ao `som-sem-endereco` (o `aba02.py` da base) e a fonte vai para dentro dele; página regerada e publicada | 8 failed, 40 passed, entre eles os dois do endereço próprio (bancada e publicado), a fonte nula e a regra do `sem-fonte` |
| M3 | o botão do microfone entra num seletor do `sem-fonte`; página regerada e publicada | `test_sem_fonte_so_o_deslizante_apaga`: 1 failed |
| M4 | a chave ausente passa a apagar | `test_sem_a_chave_nao_ha_cinza`: 1 failed, 7 passed |
| M5 | a página publicada volta à base, com a bancada curada | 6 failed, 2 passed. Sem o endereço publicado, `_so_se_a_pagina_tiver` nem emite o campo |

**A M2 NO DOM NÃO DEU «OS DOIS CINZAS», e o motivo foi medido.** Com a M2
aplicada, o piloto oculto viu o P2 e o P4 com a frase de endereço em
`data-hef-dica` nas **duas** molduras, sem `title` e sem cinza nenhum:
opacidade 1 no microfone e no alto-falante. A camada da dica da casa
(`hefesto_vivo.DICA_DA_CASA`, TOOLTIP-C1) tira todo `title` do DOM vivo para
`data-hef-dica`, e o alvo `atributo` passa a escrever lá. Então um seletor
`[title]` não casa no WebKit. A mordida da ROTA morde nas réguas do pacote e da
página; na tela, o que ela produz é outro defeito, a dica de «sem endereço»
sobre um controle que tem endereço. A cura por `data-apagado` não depende do
`title`, e é por isso que o DEPOIS apaga.

## O que NÃO verifiquei

* **O aparelho e o daemon vivo.** O `canal_fonte` nulo é dublado a partir das
  tabelas da §1 e da §2 da sprint (medidas em 09/09). Não remedi se o daemon de
  hoje ainda publica a chave com `null` nos dois do rádio.
* **A dica com o ponteiro sobre a moldura cinza.** Não passei o mouse. A moldura
  do microfone não tem mais `title` nem valor de dica nesse estado, e a leitura
  da tela deu a frase do gesto ausente de todo `data-hef-dica`.
* **O `sem-alvo` no DOM.** Só no unitário. Pelo achado da M2, ele deve acender no
  WebKit, onde o `[title]` antigo não acendia, mas isso não foi visto na tela.
* **O cabo sem placa de som** (`canal_fonte` nulo num controle no cabo): só o
  caso do rádio foi pilotado; o do cabo é a mesma função, no unitário.
* **A suíte inteira:** não rodada, só os arquivos pontuais acima.

## O que sobrou para o próximo

* **A GUARDA SEM ENDEREÇO DO ALTO-FALANTE ESTÁ MORTA NO WEBKIT.**
  `.moldura[data-bloco="alto-falante"][title]` nunca casa no DOM vivo pelo mesmo
  motivo da M2 (TOOLTIP-C1 leva o `title` para `data-hef-dica`). Até esta
  sprint a do microfone estava igual. A cura é a mesma forma do `mic-apagado`,
  mas a ROTA manda mexer só no microfone, então fica para quem coordena.
  Qualquer outro cinza por `[title]` na casa merece a mesma pergunta.
* **Duas citações da linha 23 do mapa já estavam fora do lugar antes desta
  sprint**, e o `citacoes-de-linha` não as cobra: `interface/aba02.py:2378` e
  `interface/aba02.py:2458` prometem o `title` do «Virtual», que hoje fica em
  `interface/aba02.py:2494`. Quem for dono do mapa reaponta pelo símbolo.
* **A prova no aparelho**, com dois DualSense no rádio sem ponte, é da
  MESA-DE-QUATRO-01: o bloco do microfone cinza e o do alto-falante aceso, na
  mesma foto.
* **O fato da §3 que já era da MESA-DE-QUATRO-01** continua: o número do volume
  escolhido no nó ALSA não viaja para o `hefesto_mic_<hex6>` quando o canal do
  cabo sobe.
* **As fotos de `docs/usage/assets/`** não foram regeradas: é da costura.

## O que a validação refez e corrigiu

Validação de 13/09/2026, na mesma branch e sem confiar no relato. Os roteiros
ficam no rascunho, fora do git: `v_mordidas.py` e `v_piloto.py`.

**POSSE.** `git diff --name-only e1c7d96b..HEAD` lista os três arquivos da
posse, as duas páginas 02, a sprint, a entrega com as fotos e dois arquivos
fora da posse: `docs/data/mapa-controles.csv` e `html/specs.html`. A razão foi
remedida. Com o mapa da base e o `a02_controles.py` curado,
`scripts/validar-citacoes-de-linha.py --all` reprova («a faixa não contém
`mic_modo`»). Com o `specs.html` da base e o mapa curado,
`scripts/gerar-mapa.py --check` reprova. No `specs.html`, o diff por palavra é
só o carimbo e os mesmos dois números.

**AS REGRAS DELA.** Regerar e publicar a 02 sobre o HEAD não muda um byte. Nas
duas páginas, na base e na branch: 43 `<button>`, 55 `data-gesto`, 70 `title`,
15 `<input>` e 525 `data-campo`. No DOM, depois do arrasto e do clique, não há
nenhum `.hef-recado`, e `TEXTO_MIC_SEM_FONTE` não está no texto visível, nem no
`title`, nem no `data-hef-dica`. A frase só vai ao diário `[gesto falhou]`.

**AS MORDIDAS, REFEITAS.** Em cada uma, a contagem do trecho trocado foi
conferida, o arquivo foi devolvido por `git checkout HEAD` e a árvore voltou
limpa.

| | cura arrancada | régua |
| --- | --- | --- |
| V1 | `microfone_apagado` não pergunta a fonte | 2 failed |
| V2 | a da ROTA: o gerador da base e a fonte dentro do `som-sem-endereco`, com a 02 regerada e publicada | 8 failed |
| V2b | só a tag da moldura do microfone volta ao `som-sem-endereco` | 7 failed |
| V3 | a fonte vai para o `som-sem-endereco` (o alto-falante do rádio apagaria) | 2 failed |
| V4 | com a fonte publicada, o microfone apaga igual | 2 failed |
| V5 | a chave ausente apaga | 1 failed |
| V6 | o cinza de todos sai da primeira entrada do estado | 1 failed (a mesa mista) |
| V7 | o 🎙 entra no seletor do `sem-fonte` | 1 failed |
| **V7b** | `[data-apagado] .vol`: apaga a linha onde o 🎙 mora | **1 passed**, achado |
| **V7c** | `[data-apagado^="sem"] .mudo-i` | **1 passed**, achado |
| V8 | o `.trilho` sai da regra de opacidade | 1 failed |
| V9 | a página publicada volta à base | 6 failed |
| V10 | §4.5: o `raise` de `TEXTO_MIC_SEM_FONTE` sai do gesto | 1 failed em `test_o_volume_do_mic_nao_cai_no_vizinho.py` |
| V11 | fora da posse: o mapa volta à base | `validar-citacoes-de-linha` com rc=1 |

**O ACHADO, CORRIGIDO EM `98f7cd59`.** `test_sem_fonte_so_o_deslizante_apaga`
procurava `.mudo-i` e `.rota` no texto do alvo e só casava duas grafias do
atributo. A V7b passava verde, e no piloto oculto deixava o 🎙 do P2 com
opacidade efetiva de 0,45 (o trilho ficava a 0,2): o botão que pede o canal
aparecia cinza com a régua verde. Agora a régua exige que toda regra que casa
um `data-apagado` diferente de só `sem-alvo` termine em `.trilho`, `.n` ou
`.puxa-vol`. Contra ela, V7, V7b, V7c e V8 reprovam, e com a cura dá 48 passed.

**A TELA, NO PILOTO OCULTO.** O `v_piloto.py` usa o mesmo lar de mentira, o
`SKIP_PRESET_SEED=1` e o estado e a ponte dublados. Ele mede a opacidade
EFETIVA, que é o produto dos ancestrais, porque `getComputedStyle(filho).opacity`
não enxerga a linha. Os perfis dela ficaram iguais por md5 depois de cada uma
das cinco corridas.

| cartão P2 (rádio, aberto) | ANTES (base) | DEPOIS | V7b | ROTA arrancada |
| --- | --- | --- | --- | --- |
| `data-apagado` da moldura do microfone | ausente | `sem-fonte` | `sem-fonte` | ausente |
| trilho e número (efetiva) | 1 | 0,45 | 0,2 | 1 |
| cursor do deslizante | `pointer` | `not-allowed` | `not-allowed` | `pointer` |
| 🎙 (efetiva e cursor) | 1, `pointer` | 1, `pointer` | **0,45**, `pointer` | 1, `pointer` |
| Virtual e Nativo (efetiva) | 1 | 1 | 1 | 1 |
| alto-falante (trilho e ♪) | 1 | 1 | 1 | 1 |
| P1 e P3, no cabo | acesos | acesos | acesos | acesos |

* **O CLIQUE NO 🎙 DO P2, COM O DESLIZANTE CINZA, CHEGA AO GESTO.** O
  `mic_canal_set_detalhado` dublado recebeu o `uniq` do rádio, e o botão fez
  `hef-em-voo`, depois `hef-recusou`, e voltou. O cinza não tranca a saída.
* **O CABO SEM PLACA** (`canal_fonte` nulo no P3, no cabo): o P3 apaga igual ao
  rádio, e o P1 fica aceso.
* **A ROTA ARRANCADA NO DOM** confirma o que foi medido acima: nenhuma das duas
  molduras apaga, e a frase de endereço vai para o `data-hef-dica` das duas.

Recorte do bloco do microfone do P2: `MIC-SEM-FONTE-01-VALIDACAO-antes-depois-v7b.png`
(da esquerda para a direita: ANTES, DEPOIS, V7b).

**RÉGUAS VIZINHAS.** Rodei 137 arquivos de `tests/unit` que citam os arquivos ou
os símbolos mudados, em três partes: 2313 passed, 1 xfailed, 1 skipped e 2
vermelhos. Nenhum dos dois vem da branch:

* `test_leia_primeiro_nao_digita_numero_a_mao.py::test_o_documento_confere_com_a_medicao_de_agora`
  reprova também com os arquivos da base. O `docs/data/LEIA-PRIMEIRO.md` diz
  2.259.564 bytes para o `specs.html`, a base mede 2.259.563 e a branch mede
  2.259.578, por causa do carimbo regerado. O número se regrava na costura,
  depois do último `specs.html`, com
  `check_paridade_transporte.py --leia-primeiro --escrever`.
* `test_o_lexico_da_aba_configuracoes.py::test_nenhum_paragrafo_de_apoio_novo_na_pagina`
  é intermitente dos dois lados. Em quatro pares alternados, o HEAD deu 3 passed
  e 1 failed, e a base também. As frases são da topologia USB viva (adaptadores
  e hub), e nada desta branch chega ao que a régua importa.

**O QUE FICOU SEM CURA.** A guarda sem endereço do ALTO-FALANTE continua morta
no WebKit (`[title]` com a TOOLTIP-C1), como está na seção anterior. A ROTA
manda mexer só no microfone.
