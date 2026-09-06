#!/usr/bin/env python3
"""O pacote da aba `06` Navegação.

O QUE TEM DONO: quem é o PRIMÁRIO (`is_primary`) — e é ele quem navega o PC.
O daemon marca um controle como primário, e a tela já dizia isso à mão: o
`NAVEGA` do gerador tirava o MENOR número da mesa, que acerta por coincidência
enquanto o P1 estiver na frente. Agora sai do daemon.

O QUE NÃO TEM: os cinco gestos (PS+Options, PS+↑…). Eles NÃO são configuráveis —
`daemon/subsystems/hotkey.py` monta um callback por combo, em código. A tabela da
tela oferece trocar o que cada combo faz; o produto não tem onde guardar essa
troca.

FATO SUBSTITUÍDO (06/09/2026): esta linha dizia que o `ps_button_action` da
config é *"o único pedaço ajustável"* e que *"método de IPC nenhum escreve"*.
As duas metades caíram. **Escreve** — `daemon.reload` aceita `config_overrides`
com qualquer campo do `DaemonConfig` (`ipc_handlers.py:5450`, a leitura dos
overrides) e aplica com `replace(config, **overrides)` + `reload_config`
(`:5462-5463`); o que ele NÃO faz é gravar em disco, então a escolha morre no
próximo start do daemon. E **deixou de ser o único ajustável**: desde a
ONDA5-06-01 o toque solo no PS tem dono no PERFIL
(`Profile.button_actions["ps"]`), que VENCE o degrau da máquina — a precedência
está em tabela em `hotkey._a_metade_da_maquina`. Os números antigos (`:4556` /
`:4567`) apontavam para o cache de órfãos HID quando foram remedidos.

O QUE O ESTADO AINDA NÃO TRAZ: o `ps_button_action`. Ele viaja só na resposta de
`daemon.reload` (`_config_que_viaja`), nunca no estado do tique — e é por isso
que a tira desta aba não NOMEIA o ato da máquina. Ver `_o_que_o_ps_faz`.

FATO SUBSTITUÍDO (01/09/2026, segunda leva): esta linha dizia que os cinco
gestos "moram no PERFIL". Não moram — o perfil guarda `key_bindings`, que são
os BOTÕES (options, create, l1, r1, l3, r3 e as três regiões do touchpad), e
combo nenhum. A frase sobre as velocidades de cursor e rolagem, que estava na
mesma linha, já tinha caído na primeira leva (ver o `SEM_DONO` logo abaixo).

OS VINTE E OITO INDECIDÍVEIS DESTA ABA ESTÃO DECIDIDOS — 02/09/2026, à tarde.
A `--prova-de-mockup` classificava 28 dos 29 campos como INDECIDÍVEL: o valor que
o produto pinta COINCIDE com o que o desenho cravou, e ler a tela não separa
"pintou igual" de "não pintou". Era a maior concentração da casa. A cura foi
fazer o valor MUDAR — um DUBLÊ no lugar do daemon (três controles sintéticos,
`speed=11`, `scroll_speed=4`, teclado desligado, e um `button_actions` que troca
as 21 linhas) — e ver se a tela acompanha:

    mesa dela (2 controles)   produto  1 · mockup 0 · indecidível 28
    DUBLÊ                     produto 29 · mockup 0 · indecidível  0

**Os 29 endereços desta aba estão vivos.** Nenhum é endereço morto, e nenhum
campo depende do desenho. A régua que reproduz isso sem abrir janela é
`tests/unit/test_a_06_o_duble_decide_o_indecidivel.py`.

A PINTURA DESFAZIA A ESCOLHA DE QUEM CLICA — CURADO EM 02/09/2026, por decisão
dela. O defeito estava medido com dublê, escolhendo uma opção como uma pessoa
escolheria (evento `change`):

    ANTES  (o que a pintura pôs) : Botão direito
    CLIQUE (a escolha dela)      : F11
    +100 ms                      : F11
    +1500 ms                     : Botão direito

Eram DUAS causas, e as duas eram desta aba: os 21 `<select>` não casavam com
nenhum endereço clicável do ouvinte (`hefesto_vivo.py:367`, o `closest` de
`manda_do_alvo`) — logo a escolha não chegava ao Python —, e o tique seguinte
reescrevia o valor do perfil por cima. Enquanto isso valeu, **o "Guardar" nunca
recebeu uma forma diferente do perfil**, e a recusa dele mandava trocar a linha
antes de clicar, um caminho que este mesmo arquivo declarava não existir.

A cura é a decisão dela: *"as 21 listas param de ser repintadas enquanto ela
está mexendo, até guardar ou sair"*. O gerador passou a marcar as 21 linhas com
`data-gesto` (`aba06.LINHA_DE_BOTAO`), o gesto `linha-de-botao` anota a escolha
em `_MEXENDO`, e a pintura passa a CONCORDAR com a tela em vez de reescrevê-la.
Ver `_o_que_a_tabela_mostra`.

O QUE SOBRA PARA O PILOTO, e continua relatado: a mesma forma de defeito vale
para TODA lista e TODO campo digitável das outras abas (o editor da Perfis, os
`<select>` da Conexões). A cura geral é o `escrever()` não sobrepor campo que a
pessoa está editando; a daqui resolve esta aba com o vocabulário que o piloto já
tem, sem tocar arquivo de fora.

FATO SUBSTITUÍDO — 02/09/2026, corretivo. Aqui estava escrito que **a frase de
recusa NÃO CHEGA À TELA DELA**, e que toda frase deste arquivo era escrita para
um dia futuro. **Isso caducou no mesmo dia:** o piloto ganhou
`_recusou_dizendo` (`hefesto_vivo.py:2618`), e o `except` de `trabalhar()` põe a
frase no cartão pelo `idle_add`, na hora do clique e não no tique seguinte.

O QUE CONTINUA VALENDO, e é o que separa os dois erros: **só o `RuntimeError`
fala com ela.** `_recusou_dizendo` devolve `False` para tudo o que não for
`RuntimeError`, e a razão é do contrato — `ValueError` é *clique inválido*, e as
frases que os pacotes escrevem nele citam nome de arquivo e de constante, que é
ruído no cartão de quem está com o controle na mão. Logo uma opção de VERDADE
que caia em `ValueError` é clique morto **e mudo**, e é exatamente o defeito que
este corretivo fechou.

OS DOIS `return` MUDOS MORRERAM — 02/09/2026, corretivo. O "Guardar" e o "Voltar
ao padrão" saíam sem gravar, sem chamar e **sem uma palavra** quando não havia o
que fazer. No "Guardar" isso era cruel: a trava contra o apagador manda *"espere
a tabela se preencher e clique de novo"*, e o segundo clique caía exatamente
nesse `return`. Uma recusa que instrui a repetir o gesto e depois não responde
nada promete que a segunda tentativa funciona. Os dois passaram a RECUSAR
DIZENDO — ver `guardar_definicoes` e `padrao_definicoes`.

A "FUNÇÃO DO TECLADO" TEM TRÊS OPÇÕES — decisão dela, 02/09/2026: *"`Só dentro
do jogo` · `Só fora do jogo` · `Desativado`. O padrão de um perfil novo é `Só
fora do jogo` — no jogo o L3 é o clique do analógico e o teclado atrapalha; no
desktop é onde ele serve."* Duas têm dono e uma recusa dizendo; **qual é qual
está invertido em tudo o que esta casa escreveu até hoje**, e a medição está no
corpo de `teclado()`. O padrão de PERFIL NOVO não é desta aba — é do esquema, e
está no relato.

E ELA FALA A LÍNGUA DA PÁGINA CARREGADA — 02/09/2026, corretivo, e é a
armadilha que esta casa paga toda vez que mexe na bancada. **Os geradores
escrevem em `mockup/`; o produto lê `interface/paginas/`, e só recebe quando ela
publica.** Trocar as três palavras na bancada e falar só elas fez duas coisas ao
mesmo tempo, medidas contra a página que o produto renderiza:

* das TRÊS opções que a tela dela oferece, DUAS viraram clique morto — e uma
  delas era a única forma de desligar o teclado por esta aba. Morto **e mudo,
  por contrato**: `_recusou_dizendo` (`hefesto_vivo.py:2618`) leva à tela a
  frase do `RuntimeError` e NÃO a do `ValueError`, porque clique-inválido fala
  com quem programa. Transformar uma opção de verdade em clique-inválido é
  justamente pedir esse silêncio para o clique dela;
* com o teclado desligado, a linha passou a AFIRMAR `Ligada — atalhos e teclado
  na tela`, porque o `escrever()` descarta em silêncio o texto que não casa com
  nenhuma `<option>` e o que fica é a que o desenho crava.

A cura foram duas linhas de vocabulário, e as duas tinham prazo: **ela publicou
a 06, e em 03/09/2026 os sinônimos saíram** — a régua da travessia
(`test_os_sinonimos_da_travessia_tem_prazo`) ficou vermelha nomeando o que
apagar, que é o único trabalho que ela tinha. Ficou `PALAVRAS_DO_TECLADO`, que
continua conferindo a palavra contra a página CARREGADA. **A regra que fica:
mudar rótulo, opção ou número de casas na bancada obriga a perguntar o que
acontece na tela dela HOJE.**

FATO SUBSTITUÍDO (02/09/2026): **"esta aba MENCIONA 7 campos e PINTA 3"** —
escrito a partir do `--passear`, que imprime `06-navegacao.html  1  3`. Ela
pinta os OITO elementos endereçados. O `3` é contagem de MUDANÇA: o `escrever()`
do piloto devolve `1` só quando o valor novo difere do que a tela já mostra, e
cinco dos oito já coincidiam com o daemon dela (`2 controles:`, `1 USB · 1 BT`,
`6`, `1`, `Ligada — atalhos e teclado na tela`). Ler "mudança" como "pintura" é
a mesma confusão entre a PALAVRA e o ATO que produziu o "77%" falso, com o sinal
trocado — e aqui ela escondia os defeitos REAIS da aba, que a medição achou:
metade da linha do cartão indo para a tela (`_linha_do_cartao`), 8 chaves de 14
emitidas para o vazio (`SEM_ENDERECO`) e um "Guardar" que apagava o perfil
(`guardar_definicoes`).
"""
from __future__ import annotations

import re
import time
from typing import Any

from hefesto_dualsense4unix.core import acoes_de_botao as acoes
from hefesto_dualsense4unix.core.keyboard_mappings import (
    PADRAO_QUE_A_TELA_PUBLICADA_NAO_DIZ,
)

from . import NOME_SEM_LEITURA, Contexto, identidade_de, jogador_de, perfil, registrar

#: CORRIGIDO EM 01/09/2026. Aqui estava escrito que a velocidade do cursor e da
#: rolagem "mora no perfil, não no state_full". **O daemon publica as duas**, em
#: `mouse_emulation`, junto com se a emulação está ligada e por que está
#: bloqueada — medido no daemon dela: `{"enabled": false, "speed": 6,
#: "scroll_speed": 1, "bloqueio": "desligada"}`.
#:
#: Os atalhos de BOTÃO vêm do perfil (`key_bindings`), que também tem dono.
#: Sobra nada.
SEM_DONO: dict[str, str] = {}

#: O QUE O PACOTE SABE E A PÁGINA NÃO TEM ONDE PÔR — medido em 02/09/2026, com
#: `casamento.py 06-navegacao.html`. É o INVERSO do `SEM_DONO`: lá o produto não
#: sabe responder; aqui ele sabe, e o desenho não tem lugar para a resposta.
#:
#: POR QUE ISTO PRECISOU EXISTIR: `casamento.py` já imprimia os órfãos e
#: **reprovava só o zero**. Esta aba emitia oito chaves para o vazio com o
#: portão verde — e uma delas, `via`, não era falta de lugar: era o pacote
#: mandando METADE de uma linha cujo endereço cobre a linha inteira. Órfão
#: silencioso e defeito real ficavam na mesma pilha, sem ninguém para separá-los.
#: `test_a_06_nao_manda_para_o_vazio.py` passou a cobrar que toda chave órfã
#: esteja AQUI, com a razão.
#:
#: `via` SAIU: virou parte do `navega` (ver `_linha_do_cartao`).
#: `teclado-ligado` SAIU: era o mesmo bit de `teclado-estado`, que tem endereço.
#:
#: QUATRO SAÍRAM EM 03/09/2026, e as quatro pelo mesmo motivo — **o desenho
#: ganhou o lugar que faltava**, e o que cai nele é a frase do PRODUTO, não uma
#: frase nova:
#:
#:   · `rato-ligado`   o "Status do Modo" perdeu o `<input checkbox>` e a
#:                     palavra de `content:` de CSS; agora é a classe `ligado`
#:                     (alvo `classe`) mais um nó de texto. Era a maior mentira
#:                     desta aba: com `mouse_emulation.enabled=false` a tela
#:                     dizia **Ligado**;
#:   · `rato-bloqueio` virou `rato-estado`, a linha de estado do mouse virtual,
#:                     traduzida por `BLOQUEIO_DO_MOUSE_EM_PORTUGUES`;
#:   · `teclado-osk`   ganhou linha, com a frase de
#:                     `input_actions.frase_do_teclado_na_tela`;
#:   · e nasceu `teclado-bloqueio`, de
#:                     `emulation_actions.descrever_teclado_emulado`.
SEM_ENDERECO: dict[str, str] = {
    # QUEM DESPACHA O CURSOR CONTINUA SEM LINHA, e agora por decisão e não por
    # falta de lugar: a GTK não tem frase para `despachando` — as quatro do
    # rótulo dela falam do DEVICE (`device_ativo`/`bloqueio`), que é o que a
    # linha `rato-estado` já leva. Escrever uma frase nova aqui seria inventar
    # texto de tela, e texto de tela é palavra dela.
    "rato-despachando": "a GTK não tem frase para 'o daemon está despachando' — "
                        "as quatro dela falam do device, que `rato-estado` já "
                        "diz. Inventar a frase é decisão dela",
    # OS ATALHOS DO PERFIL: a tabela da tela é a dos cinco COMBOS (PS+Options…),
    # que não são `key_bindings`. Não há onde mostrar a contagem, e mostrá-la na
    # tabela dos combos seria pôr um número ao lado de outra coisa.
    "gestos": "a tabela da tela é a dos cinco COMBOS, e `key_bindings` são os "
              "nove BOTÕES — não é o mesmo dado, e não há linha para ele",
    "gestos-lista": "idem; e a lista é estrutura, que o piloto pula",
}

#: AS DUAS FRASES DA LISTA "Função do teclado" QUE O DAEMON SABE DIZER, e elas
#: são o outro lado do contrato que `src/hefesto_dualsense4unix/interface/aba06.py:OPCOES_TECLADO`
#: desenha. A repetição é declarada, e os dois lados falham de jeitos diferentes
#: de propósito:
#:
#: * o GESTO casa pela palavra que DISTINGUE (`_ESCOLHA`), então reescrever o
#:   resto da frase não desliga o botão;
#: * a PINTURA usa a frase inteira, porque `escrever()` do piloto faz
#:   `el.value = texto` e o `<select>` só aceita o texto exato de uma `<option>`
#:   (as opções não têm `value` — ver a nota no gerador sobre o portão do
#:   desenho).
#:
#: AS TRÊS PALAVRAS SÃO DECISÃO DELA, 02/09/2026: *"`Só dentro do jogo` · `Só
#: fora do jogo` · `Desativado`. O padrão de um perfil novo é `Só fora do jogo`
#: — no jogo o L3 é o clique do analógico e o teclado atrapalha; no desktop é
#: onde ele serve."*
#:
#: DUAS TÊM DONO E UMA NÃO, e qual é qual foi MEDIDO — ver o `fato_derrubado`
#: no corpo de `teclado()`. O que o teclado emulado faz hoje **já é** "só fora
#: do jogo": o daemon cala a emulação de desktop quando um jogo assume
#: (`_jogo_no_controle_do_desktop`, `daemon/lifecycle.py:2270`, e o
#: `gamepad_dispatched` do laço em `:4780`), e o `suppress_desktop_emulation`
#: do perfil é a versão explícita e por perfil da MESMA coisa. Quem não tem
#: dono é o INVERSO — "só dentro do jogo".
TECLADO_SO_FORA = "Só fora do jogo"
TECLADO_DESATIVADO = "Desativado"
TECLADO_SO_DENTRO = "Só dentro do jogo"

#: A TRAVESSIA ACABOU — 03/09/2026, e quem mandou apagar foi a régua.
#:
#: Entre 02/09 e a publicação, a bancada tinha as três palavras dela e a página
#: que o produto renderiza ainda tinha as antigas (`Ligada — atalhos e teclado
#: na tela` · `Desligada`). Duas constantes e um dicionário de sinônimos
#: seguravam os dois mundos ao mesmo tempo, e o custo de não tê-los estava
#: medido: DUAS das três opções da tela viravam clique morto — inclusive a única
#: forma de desligar o teclado por esta aba — e a pintura emitia uma palavra que
#: a lista publicada não tinha, deixando na tela a `<option selected>` do
#: desenho: com o teclado DESLIGADO a linha afirmava o contrário.
#:
#: A 06 FOI PUBLICADA, `mockup/` e `interface/paginas/` voltaram a bater, e
#: `test_a_06_a_funcao_do_teclado_tem_tres.py::test_os_sinonimos_da_travessia_
#: tem_prazo` ficou VERMELHO nomeando o que apagar — que é o único trabalho que
#: aquela régua tinha. Declaração velha é a régua se desligando sozinha.
#:
#: O QUE FICA: `PALAVRAS_DO_TECLADO` continua sendo uma TUPLA de candidatas, e
#: não uma palavra só, porque é o que faz a próxima travessia custar uma linha
#: em vez de um defeito calado — e porque `_o_teclado_em_palavras` continua
#: conferindo contra a página CARREGADA, que é a regra que sobrou do episódio:
#: *mudar rótulo na bancada obriga a perguntar o que acontece na tela dela hoje*.
PALAVRAS_DO_TECLADO: dict[bool, tuple[str, ...]] = {
    True: (TECLADO_SO_FORA,),
    False: (TECLADO_DESATIVADO,),
}

#: O SEPARADOR DO CARTÃO — o mesmo `•` que o desenho põe entre o transporte e o
#: papel (`aba06.controle`: `{via} <span class="pt">•</span> {papel}`). Ele é
#: texto porque o endereço `data-campo="navega"` cobre a LINHA INTEIRA: o piloto
#: escreve `textContent`, e o que não vier na string some da tela.
PONTO = " • "

#: O PREFIXO DAS VINTE E UMA LINHAS de *o que cada botão faz*. Um por botão de
#: `core/acoes_de_botao.BOTOES` — a lista é do produto, e não se digita aqui.
PREFIXO_DA_ACAO = "acao-"  # (noqa-acento) prefixo de endereço, não é prosa

#: O PREFIXO DAS LINHAS DA TELA "Teclas do teclado" — 06/09/2026,
#: NAVEGACAO-TECLAS-01. Um por botão de `acoes.DOMINIO_DO_TECLADO`, e a lista
#: também é do produto.
#:
#: ELE É OUTRO PREFIXO DE PROPÓSITO, e a razão é medida: a `forma` que o piloto
#: recolhe usa `data-linha || data-campo` como chave
#: (`hefesto_vivo.py`, o bloco `forma:`), e as vinte e duas listas de *o que
#: cada botão faz* já ocupam a chave `<botão>` pelo `data-linha`. Um campo de
#: texto que reusasse aquela chave APAGARIA a escolha da lista dentro da mesma
#: forma, sem uma palavra — o "Guardar" leria o texto onde esperava um rótulo.
PREFIXO_DA_TECLA = "tecla-"  # (noqa-acento) prefixo de endereço, não é prosa

#: O `<select>` da "Função do teclado" e as suas `<option>`, lidos do HTML.
#: Duas expressões e não uma: recortar o bloco primeiro é o que impede casar
#: com as `<option>` das outras 21 listas da mesma página.
_SELECT_DO_TECLADO = re.compile(
    r'<select[^>]*data-campo="teclado-estado"[^>]*>(.*?)</select>', re.S)
_OPCAO = re.compile(r"<option[^>]*>(.*?)</option>", re.S)

#: O selo do arquivo lido e o que ele oferecia. O caminho é fixo; o que muda é
#: o arquivo, no dia em que ela publicar.
_OFERTAS: tuple[tuple[int, int], frozenset[str]] | None = None


def _o_que_a_pagina_oferece() -> frozenset[str]:
    """As `<option>` da "Função do teclado" NA PÁGINA QUE O PILOTO CARREGA.

    `publicado=True` É DELIBERADO, e é a mesma exceção que
    `a03_gatilhos._pagina_publicada` documenta: o padrão de `onde.pagina` é a
    BANCADA porque todo instrumento desta casa mede o desenho de hoje. Aqui
    não — quem pinta pinta no que está no `WebView`, e o piloto abre SEMPRE o
    publicado (`hefesto_vivo.py:913, 1418, 1458, 1646, 1818`).

    LÊ UMA VEZ POR VERSÃO DO ARQUIVO, e o selo é `(mtime_ns, tamanho)`: a
    página tem 385 KB e a pintura roda a cada 100 ms — reler a cada tique seria
    3,8 MB/s por uma resposta que só muda quando ela publica.

    `frozenset()` quando o arquivo não abre. Aí `_o_teclado_em_palavras` cai na
    profissão de fé — a palavra DELA —, que é o destino: um produto instalado
    sem a página é um produto que não tem tela nenhuma para mentir.

    A JANELA QUE ISTO NÃO FECHA, e ela é estreita: publicar com o aplicativo
    ABERTO e sem trocar de aba. O arquivo muda, o selo muda, o pacote passa a
    emitir a palavra nova — e o DOM carregado ainda é o antigo, então a escrita
    volta a ser descartada até o próximo carregamento. Trocar de aba já
    recarrega (`hefesto_vivo.py:1966`), e reabrir também. Ler o DOM em vez do
    arquivo exigiria uma pergunta ao piloto que o `Contexto` não tem.
    """
    global _OFERTAS
    from hefesto_dualsense4unix.interface import onde

    try:
        arquivo = onde.pagina(PAGINA, publicado=True)
        st = arquivo.stat()
        selo = (st.st_mtime_ns, st.st_size)
    except OSError:
        return frozenset()
    if _OFERTAS is not None and _OFERTAS[0] == selo:
        return _OFERTAS[1]
    try:
        doc = arquivo.read_text(encoding="utf-8")
    except OSError:
        return frozenset()
    bloco = _SELECT_DO_TECLADO.search(doc)
    ofertas = frozenset(_OPCAO.findall(bloco.group(1))) if bloco else frozenset()
    _OFERTAS = (selo, ofertas)
    return ofertas


def _o_teclado_em_palavras(ligado: bool) -> str:
    """A palavra daquele estado que a página CARREGADA sabe receber.

    A primeira candidata de `PALAVRAS_DO_TECLADO` é a decisão dela; a segunda é
    o rótulo que a página publicada ainda oferece. Escolher a primeira que
    EXISTE é o que faz a linha dizer a verdade nos dois mundos — e o que faz a
    publicação bastar, sem ninguém voltar aqui.

    Nenhuma das duas na página é o caso em que não há nada a acertar: devolve a
    palavra dela, o `escrever()` se cala, e a régua do dublê acusa.
    """
    candidatas = PALAVRAS_DO_TECLADO[ligado]
    ofertas = _o_que_a_pagina_oferece()
    for palavra in candidatas:
        if palavra in ofertas:
            return palavra
    return candidatas[0]


#: A PALAVRA DO INTERRUPTOR "Status do Modo", e ela é DUAS coisas ao mesmo
#: tempo: o texto que o `.txt` mostra e o gatilho da classe verde
#: (`data-hef-quando="Ligado"` no rótulo — ver `aba06.STATUS_MODO`). Por isso
#: elas são constantes e não literais espalhados: trocar uma sem a outra
#: acenderia a cor sem a palavra, ou o contrário.
LIGADO = "Ligado"
DESLIGADO = "Desligado"

#: "NÃO HÁ O QUE DIZER", dito de um jeito que a tela sabe APAGAR.
#:
#: Ele existe por um detalhe do piloto que custou uma foto: `escrever()` troca
#: valor vazio por um travessão (`hefesto_vivo.py:141`), de propósito — um lugar
#: VAZIO da mesa tem de apagar o que estava lá. Numa linha de estado isso vira
#: um `—` solto embaixo do interruptor, que é ruído com cara de dado.
#:
#: Então a linha sem conteúdo manda ESTE marcador, e o desenho a esconde inteira
#: (`.estado:has(.nada){display:none}`). A chave continua sendo emitida em todo
#: tique — é o que faz a linha SUMIR quando o bloqueio acaba. Omiti-la deixaria
#: a frase velha na tela para sempre, que é o defeito oposto e pior.
NADA_A_DIZER = '<i class="nada"></i>'

#: A ÚNICA FRASE DESTA ABA COPIADA DA GTK EM VEZ DE IMPORTADA, e a duplicação é
#: declarada porque não há como evitá-la sem tocar arquivo de outra frente: ela
#: é um literal DENTRO de `_refresh_mouse_view`
#: (`app/actions/mouse_actions.py:611`), que é método de mixin GTK e escreve num
#: widget. Extraí-la para uma constante é o certo, e é edição naquele arquivo.
#:
#: ELA NÃO PODE DIVERGIR CALADA: `test_a_06_as_frases_do_mouse_sao_as_da_gtk.py`
#: lê o fonte da GTK e reprova no dia em que a frase de lá mudar.
PRONTO_PARA_MOUSE = "Pronto para usar como mouse"


def _o_mouse_virtual_em_uma_linha(rato: dict[str, Any]) -> str:
    """A linha "o mouse virtual está pronto?" — a MESMA hierarquia da GTK.

    O DONO É `app/actions/mouse_actions._refresh_mouse_view`, e o que se copia
    dele é a ORDEM, não a frase: a frase do bloqueio vem inteira da tabela
    `BLOQUEIO_DO_MOUSE_EM_PORTUGUES`, que é importada. A hierarquia da GTK, no
    corpo dela, é: *device no ar segundo o daemon → pronto; senão, o motivo*.

    **A SONDA LOCAL NÃO VEM JUNTO, e é decisão medida.** A GTK ainda faz
    `import uinput` + `os.access("/dev/uinput")` dentro do processo da JANELA, e
    o próprio docstring dela diz que isso *"erra nos dois sentidos"* — num
    Flatpak a janela olha o sandbox e grita "sem permissão" sobre um nó que o
    daemon abre sem dificuldade. O primeiro ramo dela, o que o `_anotar_mouse_
    virtual` criou em 25/08, é justamente o que dispensa a sonda: **quem abre o
    device é o daemon, e a resposta vem de quem executa.** Aqui só existe esse
    ramo, o que torna esta linha mais confiável que a da GTK, não menos.

    Vazia quando o daemon não respondeu, ou quando ele diz `desligada` — que é
    escolha dela, não defeito, e é o que o `_anotar_mouse_virtual` classifica
    como "não sei" para não mandá-la consertar um interruptor que ela baixou.
    """
    from hefesto_dualsense4unix.app.actions.mouse_actions import (
        BLOQUEIO_DO_MOUSE_EM_PORTUGUES,
    )
    from hefesto_dualsense4unix.utils.repo_files import como_atualizar_esta_instalacao

    if not rato:
        return NADA_A_DIZER
    if rato.get("device_ativo") is True:
        return f'<span class="verde">{PRONTO_PARA_MOUSE}</span>'
    bloqueio = rato.get("bloqueio")
    if not isinstance(bloqueio, str) or not bloqueio or bloqueio == "desligada":
        return NADA_A_DIZER
    motivo = BLOQUEIO_DO_MOUSE_EM_PORTUGUES.get(bloqueio)
    if motivo is None:
        # Motivo NOVO, de um daemon mais novo que esta tela: dizer o código cru
        # é feio e é honesto — a GTK faz o mesmo em `frase_da_recusa_do_mouse`.
        motivo = f"o Hefesto está bloqueando o mouse (motivo: {bloqueio})"
    motivo = motivo.replace("{gesto}", como_atualizar_esta_instalacao())
    return f'<span class="laranja">O cursor não anda: {motivo}.</span>'


def _o_teclado_em_uma_linha(tecla: dict[str, Any]) -> str:
    """"Ligado, em pausa agora: …" — o ESTADO do teclado, e ele é do produto.

    Chamada direta de `app/actions/emulation_actions.descrever_teclado_emulado`,
    que é pura *"de propósito: é o miolo que decide o que ela vê"*. Ela devolve
    `(posição, frase)`; a posição já está na lista "Função do teclado", e o que
    faltava nesta tela era a FRASE.

    O que ela responde e a lista sozinha não: a diferença entre *desligado por
    você* e *ligado e calado agora porque um jogo assumiu*. Sem ela, com o
    teclado suspenso pelo modo jogo, a tela continua dizendo "Só fora do jogo" —
    verdade sobre a configuração, e não sobre o que está acontecendo.

    Sem o bloco a frase é a de "não sei" da própria GTK, e é a coisa certa a
    dizer: `TECLADO_SEM_ESTADO` fala do Hefesto, não do teclado.
    """
    from hefesto_dualsense4unix.app.actions.emulation_actions import (
        descrever_teclado_emulado,
    )

    _posicao, frase = descrever_teclado_emulado(tecla or None)
    return f'<span class="laranja">{frase}</span>' if frase else NADA_A_DIZER


def _o_teclado_na_tela_em_uma_linha(tecla: dict[str, Any]) -> str:
    """"Neste computador: o teclado na tela está instalado — o L3 abre."

    Chamada direta de `app/actions/input_actions.frase_do_teclado_na_tela`, que
    já é TRI-ESTADO: `None` devolve `""` — não afirma sobre uma máquina que
    ninguém olhou. É a frase que decide se existe ALGUM caminho para escrever
    texto com o controle, porque nenhum atalho de fábrica digita letra.

    A dica desta aba manda abrir o teclado na tela com o L3 e nunca disse se há
    um instalado; numa máquina sem `wvkbd-mobintl`/`onboard` a tela prometia o
    que não entrega, e a GTK avisava.
    """
    from hefesto_dualsense4unix.app.actions.input_actions import (
        frase_do_teclado_na_tela,
    )

    bruto = (tecla or {}).get("osk_disponivel")
    return frase_do_teclado_na_tela(
        bruto if isinstance(bruto, bool) else None) or NADA_A_DIZER


#: O CUSTO DE DESLIGAR O TECLADO, dito ENQUANTO ele estiver desligado — decisão
#: do PO em 04/09/2026 (`2026-09-04-O-PO-DECIDE` §2 `06[05]`): *"Uma frase
#: permanente enquanto estiver desativado."*
#:
#: POR QUE PERMANENTE, e a razão é a pergunta que chega tarde: a dica `?` da
#: "Função do teclado" já diz o custo ANTES do ato, e some com o ponteiro. A
#: pergunta *"por que o L3 parou de abrir o teclado na tela?"* chega dias
#: depois, e nesse dia a dica não está lá. A tira de estados está.
#:
#: A FRASE É COPIADA DA GTK, e a duplicação é declarada pelo mesmo motivo de
#: `PRONTO_PARA_MOUSE`: o original é um literal DENTRO de
#: `emulation_actions.on_keyboard_toggle_set` (`:1725`), método de mixin GTK que
#: escreve num toast. Extraí-lo para uma constante é o certo, e é edição naquele
#: arquivo — que não é desta frente. O que muda é só a moldura: lá o toast diz
#: *"Teclado emulado desligado — saem também …"*, e aqui a linha vive no
#: presente contínuo, porque ela fica.
#:
#: ELA NÃO PODE DIVERGIR CALADA: `test_a_aba_06_navegacao_fecha_as_linhas.py`
#: lê o fonte da GTK e reprova no dia em que a lista de lá mudar.
O_QUE_SAI_COM_O_TECLADO = ("o teclado na tela (L3/R3) e as três regiões do "
                           "touchpad")


def _o_custo_de_desligar_o_teclado(tecla: dict[str, Any]) -> str:
    """"Com o teclado desativado saem também …" — e só enquanto ele estiver.

    TRI-ESTADO como as outras três linhas: sem o bloco `keyboard_emulation` a
    linha não afirma nada, porque ninguém perguntou ao Hefesto. Ligado, também
    não há o que dizer — o custo é o de DESLIGAR.

    ELA NÃO SUBSTITUI O `teclado-bloqueio`, e as duas convivem de propósito:
    aquela diz *o teclado está ligado e calado agora porque um jogo assumiu*;
    esta diz *você o desligou, e isto saiu junto*. São o presente e a escolha.
    """
    ligado = (tecla or {}).get("enabled")
    if not isinstance(ligado, bool) or ligado:
        return NADA_A_DIZER
    return ('<span class="laranja">Com a “Função do teclado” em “'
            f'{TECLADO_DESATIVADO}” saem também {O_QUE_SAI_COM_O_TECLADO}.'
            "</span>")


#: O ENDEREÇO DA RESSALVA DA D3 — 05/09/2026, e ela nasceu de uma promessa que
#: esta aba fazia sem poder cumprir.
#:
#: A DECISÃO É D3 DO `2026-09-05-AS-TRES-DECISOES-DO-PERFIL`: `mouse`,
#: `key_bindings`, `button_actions`, `teclado_emulado` e
#: `suppress_desktop_emulation` ficam **globais por enquanto**, e a razão é
#: medida, não preguiça — o `Daemon` tem UM `_mouse_device` e UM
#: `_keyboard_device`, alimentados por um `read_state()` por tique, e o input vem
#: sempre do controle PRIMÁRIO. Guardar por controle antes de o caminho de
#: ENTRADA existir é o que a régua
#: `test_perfil_por_controle_o_campo_espera_o_caminho.py` proíbe.
#:
#: A DECISÃO PEDE A TELA JUNTO, com estas palavras: *"onde a aba oferece um
#: destes cinco, a linha de ressalva diz que o ajuste vale para a mesa inteira,
#: não só para o controle selecionado. Sem isso a tela promete por-controle e
#: entrega global — que é o mesmo defeito por outro caminho."*
#:
#: O `title` DA FITA NÃO BASTAVA, e é o que faz esta linha existir. Ele diz
#: *"Não se aplica: mouse, teclado e gestos saem de um controle só"* desde
#: 30/08 — mas é TOOLTIP: só aparece para quem passa o ponteiro, e some quando
#: ele sai. É a mesma medição que a Onda 2 fez para o `teclado-custo`: *"a dica
#: `?` já dizia o custo ANTES do ato e some com o ponteiro; a pergunta chega
#: dias depois, e nesse dia esta linha ainda está aqui."* E ele diz outra coisa:
#: de onde o comando SAI (o primário), não para onde o ajuste VAI (todos).
ENDERECO_DA_RESSALVA = "ativacao-ressalva"

#: A FRASE, e a palavra "mesa" está fora dela por ordem dela de 05/09 — *"não é
#: pra ter mesa em nada da interface"*. O que sobra é o que ela lê sem traduzir:
#: os três nomes que a tela mostra logo acima, e para quem o ajuste vale.
RESSALVA_DOS_GLOBAIS = (
    "O cursor, a rolagem e o teclado são um só para o computador inteiro: "
    "mudar aqui vale para <b>todos os controles ligados</b>, e não só para o "
    "que está escolhido em cima.")


def _a_ressalva_dos_globais(ctx: Contexto) -> str:
    """A linha da D3 — e só quando há mais de um controle a ressalvar (D-02).

    *"Linha fixa só quando HÁ ressalva."* Com UM controle ligado não há
    promessa quebrada: o ajuste global É o ajuste daquele controle, e a frase
    ocuparia uma linha da tela para dizer uma verdade sem consequência. Com
    DOIS, a fileira de cartões em cima passa a oferecer uma escolha que estas
    sete linhas não honram — e é aí que a ressalva tem o que ressalvar.

    O NÚMERO SAI DE `conectados`, NUNCA DA MESA DO DESENHO: a mesa tem quatro
    lugares sempre, dois deles vazios no mockup, e contá-la faria a frase nascer
    numa tela com um controle só. *"Toda frase que promete alcance conta os
    CONECTADOS"* — a regra é do `Contexto`, e o defeito de nomear um controle
    que não está apareceu quatro vezes em 31/08.
    """
    return RESSALVA_DOS_GLOBAIS if len(ctx.conectados) > 1 else NADA_A_DIZER


#: A RAZÃO DO PORTÃO DE MODO — UMA frase, e ela serve aos DOIS caminhos: a linha
#: permanente da tira de estados (antes do clique) e o `RuntimeError` do gesto
#: `modo` (depois dele, quando alguém clica assim mesmo).
#:
#: UMA SÓ, e não duas: a tela e a recusa dizendo a mesma coisa com palavras
#: diferentes é a doença que esta casa persegue. O gesto a levanta inteira.
#:
#: DECISÃO DO PO, 04/09/2026 (`2026-09-04-O-PO-DECIDE` §2 `06[01]`): *"Apaga o
#: interruptor e escreve ao lado, na tira de estados. É a D-03 com a D-02."* A
#: janela antiga já faz isso — `_sync_mouse_mode_gate`
#: (`app/actions/mouse_actions.py:299`) põe `blocked = mode != MODE_DESKTOP` e
#: apaga o switch ANTES de qualquer clique. O que faltava aqui era o MOMENTO:
#: a tela nova aceitava o clique e recusava por escrito, e ela gastava o clique
#: para descobrir.
#:
#: A FRASE É OUTRA QUE A DA GTK, e tem de ser: `MODE_GATE_HINT` manda ir à aba
#: **Início**, que não existe no desenho das dez — o degrau mudou para a aba
#: **Jogar**. Reusar o módulo também não dá: `mouse_actions.py` importa GTK no
#: topo, e os pacotes são puros de propósito.
RAZAO_DO_PORTAO = (
    "O mouse e o teclado só se ligam fora do jogo: jogando, o controle é do "
    "jogo, e ligar o mouse aqui derrubaria o controle virtual e os jogadores "
    "do co-op no meio da partida. O degrau se troca na aba Jogar.")


def _a_razao_do_portao(estado: dict[str, Any]) -> str:
    """Por que o "Status do Modo" vai recusar agora — ou nada a dizer.

    O ENDEREÇO É UM SÓ, e é ele que faz as duas metades da D-03 nunca
    discordarem: esta chave alimenta a LINHA da tira (alvo `html`) e, pela folha
    da aba, o CINZA do interruptor — que é uma regra `:has()` lendo a própria
    linha. Não há segundo campo a divergir porque não há segundo campo.

    SEM ESTADO, NÃO AFIRMA. O gesto recusa dizendo que não conseguiu falar com o
    Hefesto, e isso é resposta a um clique — não é fato sobre o portão. Apagar o
    interruptor por falta de resposta seria a tela afirmando um bloqueio que
    ninguém mediu, que é a regra dela de 30/08: *"se não tá mostrando agora, não
    tem info pra mostrar"*.
    """
    if not estado:
        return NADA_A_DIZER
    if mode_of_state(estado) == MODE_DESKTOP:
        return NADA_A_DIZER
    return f'<span class="laranja">{RAZAO_DO_PORTAO}</span>'


def _nome_do_botao(botao: str) -> str:
    """`"l2"` → `"L2 (gatilho esquerdo)"`. O nome que ELA lê, e é do MOTOR.

    NÃO SE ESCREVE A TABELA AQUI. `app/actions/input_actions.humanize_button`
    (`:181`) é dona dos vinte nomes desde o KBD-01, e a GTK que ela usa mostra
    exatamente estes. As duas frases de recusa do "Guardar" mandavam o id cru
    para a tela — ela lia *"estas linhas ficaram sem quem as atenda:
    touchpad_left_press"*, que é jargão de kernel na cara de quem clicou.

    FATO SUBSTITUÍDO — 02/09/2026, corretivo. Este parágrafo citava TRÊS ids
    como curados: `l2`, `touchpad_left_press` e `r3_direcao`. **Os dois eixos
    continuam crus**, e a medição é de um comando:

        _nome_do_botao('l2')                  → 'L2 (gatilho esquerdo)'
        _nome_do_botao('touchpad_left_press') → 'Touchpad — lado esquerdo'
        _nome_do_botao('r3_direcao')          → 'r3_direcao'
        _nome_do_botao('l3_direcao')          → 'l3_direcao'

    São 22 botões em `acoes.BOTOES` e 20 nomes em `_BUTTON_LABELS`, e os dois
    que faltam são a DIREÇÃO dos analógicos. A cura mora no MOTOR
    (`app/actions/input_actions.py:129`), não aqui — copiar duas linhas para
    dentro deste arquivo criaria a segunda tabela que o
    `test_o_nome_do_botao_e_o_do_motor_e_nao_uma_segunda_tabela` existe para
    impedir, e a tela passaria a chamar o mesmo botão por dois nomes.

    O DANO HOJE É DE FORMA, e por isso não se força a cura: `acoes.resolver()`
    (`core/acoes_de_botao.py:285`) pula os eixos, então eles nunca chegam ao
    `sem_dono` — medido, trocando o `cross`: `sem_dono == ['l2']`. O único
    caminho que ainda os exporia é o `nao_reconhecidas` do "Guardar", que exige
    a tela oferecer um rótulo que o produto não conhece.

    O IMPORT É TARDIO, E É POR ISSO: `input_actions` puxa GTK no topo (e
    `mouse_actions` junto). Os pacotes são puros de propósito — importáveis sem
    janela, testáveis sem display —, e um import no topo deste arquivo faria a
    aba inteira depender da camada da janela ANTIGA para escrever um rótulo.
    Aqui ele custa uma vez, no caminho da recusa, que não é o do tique.

    E ELE CAI DE PÉ: sem GTK no ambiente, o id cru volta. Um rótulo bonito não
    vale derrubar a aba — o cru é feio e é honesto, que é a mesma escolha do
    `acoes.rotulo()` para um token sem nome.
    """
    try:
        from hefesto_dualsense4unix.app.actions.input_actions import humanize_button
    except Exception:
        return botao
    return humanize_button(botao)


# ---------------------------------------------------------------------------
# A IDENTIDADE VEM DE CIMA — 03/09/2026, IDENTIDADE-VEM-DE-CIMA-01
#
# A lei é dela: *"se no topo tá mostrando controle white player 1, então cada
# aba vai usar os controles lá de cima. Não mistura com a info dos mockups."*
#
# Esta aba tinha DEZESSEIS valores de identidade cravados no HTML — dois nomes
# de plástico no cartão, dois no `title`, dois em cada uma das duas dicas das
# telas de botões, os dois `--plastico` das bordas e os chips da fita. Todos
# nomeavam o controle do DESENHO enquanto a mesa dela tinha outros dois.
#
# AS TRÊS FUNÇÕES ABAIXO TÊM DOIS CHAMADORES E UM DONO — o mesmo arranjo de
# `a04_iluminacao.um_botao_de_player`: o gerador `aba06.py` as chama para
# desenhar a bancada, e o pacote as chama a cada tique para pintar a tela viva.
# Enquanto fossem duas escritas, o desenho e o produto podiam divergir sem
# ninguém ver — a cicatriz de 25 KB da `novo-layout/`.
# ---------------------------------------------------------------------------

#: O que a tela escreve quando a leitura não veio. VAZIO, e é a regra dela:
#: *campo sem informação não mostra nada*. Nunca a cor do mockup — cair de volta
#: no desenho é o defeito que esta onda inteira existe para matar.
SEM_LEITURA = ""


def _monta() -> Any:
    """O `monta`, importado tarde. O `pacotes/__init__` põe `interface/` no path.

    TARDE E NÃO NO TOPO: `monta` lê o `topo.html`, o `fim.html` e o SVG de
    28 modelos no import. Um pacote é importado por teste sem janela nenhuma, e
    pagar 4,7 MB de leitura para responder "qual é o hex do plástico" seria o
    mesmo desperdício que `a04_iluminacao` já evita pelo mesmo caminho.
    """
    import monta

    return monta


def cor_do_plastico(slug: str) -> str:
    """O hex da casca daquele modelo, LIDO do mapa — ou `""` sem leitura.

    `monta.cor_da_zona` é o dono: ele lê a folha que
    `scripts/gerar_cores_do_dualsense.py` escreveu no SVG, em vez de digitar o
    hex. Digitá-lo aqui seria a segunda verdade que o portão
    `check_cores_do_dualsense.py` existe para matar.

    O `""` NÃO É DESISTÊNCIA: pelo rádio o mapa de canais diz que a cor **não**
    se lê (`identidade.cor_do_aparelho`, `radio_aciona = não`), e a mesa nasce
    sem cor até o leitor responder pelo cabo. Sem hex, o cartão fica no neutro
    do CSS — que é exatamente o que ela pediu para um campo sem informação.
    """
    if not slug:
        return SEM_LEITURA
    try:
        # `cor_de_css` E NÃO `cor_da_zona` — 03/09/2026. Oito dos 28 modelos
        # dela não têm hexa amostrado e devolvem `url(#hachura-sem-hex)`, que
        # o CSSOM RECUSA EM SILÊNCIO num campo de cor — e o que ficava na
        # tela era o Cosmic Red do MOCKUP, sob um desenho que dizia outro
        # modelo. Ver a razão inteira em `monta.cor_de_css`.
        return str(_monta().cor_de_css(slug))
    except Exception:
        # `cor_da_zona` levanta `SystemExit` (que não é `Exception`) para um
        # colorway que o SVG não tem — e `SystemExit` derrubaria a aba inteira
        # por causa de um modelo novo. `BaseException` seria largo demais; o
        # `SystemExit` entra pelo nome logo abaixo.
        return SEM_LEITURA
    except SystemExit:
        return SEM_LEITURA


#: As zonas do desenho que CARREGAM IDENTIDADE, calculadas do mapa e não
#: digitadas: uma zona é identidade quando o valor dela MUDA de um modelo para
#: outro. As que não mudam — o painel, o touchpad, os analógicos, os símbolos —
#: são pretas nos 28 e apagá-las transformaria o desenho num vulto.
_ZONAS_DE_IDENTIDADE: frozenset[str] | None = None
#: `colorway -> {zona: hex}`, lido uma vez da folha do SVG.
_FOLHA: dict[str, dict[str, str]] | None = None


def _ler_a_folha() -> dict[str, dict[str, str]]:
    """As zonas de cada modelo, lidas do `ds_limpo.svg` que o gerador pinta."""
    global _FOLHA, _ZONAS_DE_IDENTIDADE
    if _FOLHA is not None:
        return _FOLHA
    folha: dict[str, dict[str, str]] = {}
    for slug, corpo in re.findall(
            r'svg\[data-colorway="([^"]+)"\]\{([^}]*)\}', _monta().DS):
        zonas = {}
        for par in corpo.split(";"):
            chave, _, valor = par.partition(":")
            if chave.strip().startswith("--z-"):
                zonas[chave.strip()] = valor.strip()
        folha[slug] = zonas
    vistos: dict[str, set[str]] = {}
    for zonas in folha.values():
        for chave, valor in zonas.items():
            vistos.setdefault(chave, set()).add(valor)
    _ZONAS_DE_IDENTIDADE = frozenset(k for k, v in vistos.items() if len(v) > 1)
    _FOLHA = folha
    return folha


def colorway_do_aparelho(slug: str) -> str:
    """O `data-colorway` daquele lugar da mesa — o id do modelo, ou `""`.

    É O MESMO DADO DE `cor_do_plastico`, PELA OUTRA PORTA, e as duas portas
    existem porque a tela precisa das duas coisas: o cartão precisa do HEX (a
    borda é `currentColor`) e o desenho precisa do NOME (o SVG escolhe a cor por
    `svg[data-colorway="…"]`, e não por hex). Traduzir uma na outra aqui seria
    escrever a tabela dela de novo; ambas leem a folha que
    `scripts/gerar_cores_do_dualsense.py` pintou no SVG.

    O SLUG QUE O MAPA NÃO CONHECE VIRA `""`, e isso é a regra dela e não zelo:
    escrever um colorway sem regra na folha deixaria o desenho no cinza cru do
    `ds_limpo.svg` **parecendo** cor lida. `""` apaga o atributo, o que dá o
    mesmo cinza — mas dizendo a verdade: não há informação.
    """
    if not slug:
        return SEM_LEITURA
    return slug if slug in _ler_a_folha() else SEM_LEITURA


def folha_do_plastico(mesa: list[dict[str, Any]], caixa: str = ".nav-ctl") -> str:
    """A folha de estilo VIVA que pinta o casco de cada lugar da mesa.

    ELA É O CINTO, E O ALVO `atributo` É O SUSPENSÓRIO — 03/09/2026. Desde que
    o piloto ganhou o alvo `atributo`, o `data-colorway` de cada `<svg>` é um
    campo (ver `colorway_do_aparelho`) e a página publica os 28 modelos: com o
    alvo em voo, esta folha escreve as MESMAS variáveis que a regra já traz.
    Ela fica porque é o que pinta o casco numa árvore em que o alvo ainda não
    chegou — e sai no dia em que ele estiver no `dev` e provado na tela.

    POR QUE UMA FOLHA, e não um campo: o casco do desenho não é `style` de
    elemento — as peças do SVG leem `var(--z-casca)`, escrita por uma regra
    `svg[data-colorway="…"]`. O piloto escreve texto, valor, classe, cor,
    largura, fundo, `innerHTML` e atributo, e **nenhum deles alcança uma
    variável CSS de um elemento**. Reescrever o SVG inteiro pelo `innerHTML`
    custaria 370 linhas por cartão a cada meio segundo — e nunca sossegaria: o
    navegador NORMALIZA marcação, então a comparação do `escrever()` acusaria
    mudança em todo tique, para sempre. O `innerHTML` de um `<style>` é TEXTO,
    e texto volta como foi escrito.

    A especificidade é o que faz esta folha vencer a de dentro do SVG:
    `.nav-ctl[data-controle="p1"] .ds-svg` (0,3,0) contra
    `svg[data-colorway="cosmic-red"]` (0,1,1).

    SEM LEITURA, O CASCO FICA NEUTRO — e é a regra dela. Um controle no rádio
    hoje não entrega a cor; deixá-lo com o casco do mockup seria a tela
    afirmando um aparelho que não está na mesa. As zonas que não são identidade
    ficam como estão: pintá-las apagaria o desenho em vez de calar a cor.

    :param caixa: o seletor da CAIXA de um lugar da mesa, que muda de aba para
        aba — `.nav-ctl` aqui, `.ctrl` na Iluminação. Ele ganhou parâmetro em
        03/09/2026, quando a aba 04 precisou da mesma folha: o desenho GRANDE
        dela continuava com o Cosmic Red e o Starlight Blue do mockup embaixo de
        um rótulo que já dizia `P1 • White • USB` — medido nos pixels da tela
        dela, `rgb(174,51,90)` no corpo contra `rgb(228,224,216)` na moldura da
        MESMA célula. Duas cópias desta função divergiriam no primeiro modelo
        novo; um parâmetro não.

        **O seletor precisa vencer o `svg[data-colorway="…"]` de dentro do
        SVG** (0,1,1). `.nav-ctl[data-controle="p1"] .ds-svg` e
        `.ctrl[data-controle="p1"] .ds-svg` valem os dois (0,3,0).
    """
    folha = _ler_a_folha()
    identidade = _ZONAS_DE_IDENTIDADE or frozenset()
    regras = []
    ocupados: set[str] = set()
    for lugar in mesa:
        pref = str(lugar.get("pref") or "")
        if not pref:
            continue
        ocupados.add(pref)
        zonas = folha.get(str(lugar.get("cor") or ""))
        if zonas:
            corpo = ";".join(f"{k}:{v}" for k, v in zonas.items())
        else:
            corpo = ";".join(f"{k}:var(--border-forte)" for k in sorted(identidade))
        if corpo:
            regras.append(f'{caixa}[data-controle="{pref}"] .ds-svg{{{corpo}}}')
    regras.extend(_apagar_os_lugares_sem_dono(caixa, ocupados, identidade))
    return "".join(regras)


#: OS LUGARES QUE O DESENHO TEM. As duas páginas que chamam a
#: `folha_do_plastico` nomeiam `p1` e `p2` (medido em 03/09/2026:
#: `grep -o 'data-controle="p[0-9]"'` devolve os mesmos dois em
#: `06-navegacao.html` e em `04-iluminacao.html`). Vai até `p4` porque a mesa do
#: desenho tem quatro lugares e um dia os quatro podem ganhar nome — uma regra
#: para um `pref` que a página não tem não casa com nada e não custa nada.
LUGARES_DO_DESENHO = 4


def _apagar_os_lugares_sem_dono(
    caixa: str, ocupados: set[str], identidade: frozenset[str],
) -> list[str]:
    """As regras que APAGAM o aparelho do mockup nos lugares que ficaram vazios.

    O DEFEITO, MEDIDO NO PRODUTO EM 03/09/2026, com UM controle no cabo e a aba
    Navegação aberta no WebKit — os quatro cartões, lidos pelo DOM vivo::

        P1 • White         casco rgb(68, 71, 90)     lightbar rgb(0, 0, 255)
        P2 • —             casco rgb(126, 184, 212)  lightbar rgb(255, 0, 0)
        P3 • Desconectado  casco rgb(83, 87, 111)    lightbar rgb(83, 87, 111)
        P4 • Desconectado  casco rgb(83, 87, 111)    lightbar rgb(83, 87, 111)

    `rgb(126, 184, 212)` é `#7eb8d4`, o **Starlight Blue do mockup**, e
    `rgb(255, 0, 0)` é o `style="--luz:#ff0000"` que o `monta.svg()` cravou no
    `<g id="p2-lightbar">`. Num lugar onde NÃO HÁ CONTROLE, o cartão saía mais
    colorido — e mais aceso — que o do único controle de verdade na mesa.

    POR QUE O P3 E O P4 ESCAPARAM, e é o que nomeia a causa: eles nascem
    `class="nav-ctl vazia"` no HTML, e a folha do desenho já sabe desenhar um
    lugar vazio (`.nav-ctl.vazia .ds-svg …{fill:var(--linha)!important}`). O P2
    nasce OCUPADO e fica vazio em tempo de execução — e quem o esvazia
    (`pacotes.apagar_os_lugares_sem_dono` + o passo `vazios` do piloto) escreve
    a classe **`off`**, que folha de estilo nenhuma menciona. As duas palavras
    para o mesmo estado nunca se encontraram, e o desenho do mockup ficou.

    É A MESMA LEI DA `folha_do_plastico`, aplicada onde ela estava calada: um
    lugar SEM DONO é, com mais razão que um lugar sem leitura de cor, um lugar
    sobre o qual a tela não tem o que afirmar. O neutro é o `var(--linha)` do
    próprio desenho — o mesmo que o `.vazia` usa —, e não um cinza digitado
    aqui.

    O `!important` NÃO É ZELO: a `--luz` chega como `style="--luz:#ff0000"` no
    próprio elemento (`monta.py:1532`), e estilo de linha vence qualquer regra
    de folha que não o traga.
    """
    if not identidade:
        return []
    zonas = ";".join(f"{k}:var(--linha)" for k in sorted(identidade))
    regras = []
    for n in range(1, LUGARES_DO_DESENHO + 1):
        pref = f"p{n}"
        if pref in ocupados:
            continue
        regras.append(f'{caixa}[data-controle="{pref}"] .ds-svg{{{zonas}}}')
        regras.append(f'{caixa}[data-controle="{pref}"] [id$="-lightbar"]'
                      f'{{--luz:var(--linha) !important}}')
    return regras


def rotulo_de_quem_navega(numero: int | None, nome: str, via: str) -> str:
    """`"P1 White USB"` — quem navega o PC, como as duas dicas o dizem.

    É SÓ A FORMA, e é de propósito: quem responde *"qual número"* é
    `pacotes.jogador_de` e quem responde *"qual nome"* é
    `pacotes.identidade_de`, os dois donos que a ROTA-A deixou prontos. O
    gerador chama esta função com a mesa do desenho e o pacote com a mesa viva
    — uma escrita só para as duas, que é o que impede o desenho e o produto de
    divergirem calados.

    Cada pedaço que não se sabe simplesmente NÃO ENTRA: sem primário na mesa a
    frase da dica termina em "o **.**", que é feio e é verdadeiro. Inventar um
    número aqui seria repetir o defeito que a ROTA-A mediu — o mesmo controle
    mudando de nome quando o segundo entra na mesa.
    """
    if nome == NOME_SEM_LEITURA:
        nome = SEM_LEITURA
    partes = [f"P{numero}" if numero else "", nome, via]
    return " ".join(p for p in partes if p)


def chips_da_fita(mesa: list[dict[str, Any]]) -> str:
    """Os chips da fita do topo, para a `06`, com os controles da MESA.

    POR QUE ESTA ABA TEM OS SEUS, e não os de `monta.fita()`: a fita é de todas
    as dez e o piloto a troca INTEIRA (`hefesto_vivo._fita`) — mas `_fita`
    **desiste** quando um controle da mesa não tem cor (`if not mesa or any(not
    c.get("cor") …): return ""`), e pelo rádio a cor não se lê. Medido em
    03/09/2026, com os dois controles dela na mesa e o daemon no ar: a fita da
    `06` mostrava `P1 · Cosmic Red · USB` e `P2 · Starlight Blue · BT`, os dois
    do mockup, ao lado de um cabeçalho que já contava certo. Treze tiques, uma
    pintura.

    Este endereço é o que salva a fita **no caso em que o dono dela desiste**.
    Quando `_fita` responde, ele troca o bloco antes desta escrita (a fita é o
    primeiro passo do `pintar`), e o que fica na tela é o dele — que também é
    lido do aparelho. Os dois dizem a mesma coisa; um deles diz sempre.

    SEM `--plastico`, e o desenho não muda: nesta aba a fita nasce `inerte`
    (fora de `monta.ABAS_QUE_ESCOLHEM`), e `.fita.inerte .chip.plastico` já
    sobrepõe a borda com
    `var(--border-sutil)`. O hex do plástico ali nunca pintou um pixel — era só
    identidade congelada esperando alguém acreditar nela.
    """
    monta = _monta()
    # O `Todos` E QUEM ACENDE SAEM DE `monta.escolha_da_fita`, e não de um `if`
    # daqui. Esta aba é a segunda de TRÊS que escrevem o chip `Todos` — a régua
    # dele mora num lugar só, senão a 06 continuaria oferecendo, com um controle
    # na mesa, o botão que a 01 já não oferece. Ver a nota do bloco em `monta.py`.
    #
    # O `"todos"` É LITERAL AQUI PORQUE ELE É A ESCOLHA DESTA ABA: a fita nasce
    # `inerte` (fora de `monta.ABAS_QUE_ESCOLHEM`) e não há gesto que a mova. É por
    # CONSTANTE que a volta funciona sozinha — com o segundo controle de novo na
    # mesa, este mesmo `"todos"` reacende o `Todos`.
    mostra_todos, escolhido = monta.escolha_da_fita("todos", mesa)
    chips = [f"<span>{monta.ROTULO_DA_FITA}</span>"]
    if mostra_todos:
        chips.append('<label class="chip on">Todos</label>')
    for lugar in mesa:
        nome = str(lugar.get("nome") or "")
        if nome == NOME_SEM_LEITURA:
            nome = SEM_LEITURA
        partes = [f'P{lugar["jogador"]}' if lugar.get("jogador") else "",
                  nome, str(lugar.get("via") or "")]
        rotulo = monta.SEPARADOR.join(p for p in partes if p)
        # SEM O `Todos`, ALGUÉM TEM DE ACENDER. Com um controle na mesa ele é o
        # escolhido — uma fita com um chip e nenhum aceso diria "escolha" sobre
        # a única coisa que não se pode deixar de escolher.
        aceso = " on" if str(lugar.get("pref") or "") == escolhido else ""
        chips.append(f'<label class="chip plastico{aceso}"'
                     ' title="a borda é a cor do plástico">'
                     f"{rotulo}</label>")
    return "".join(chips)


def _linha_do_cartao(c: dict[str, Any], primario: bool) -> str:
    """A linha inteira do cartão: `"BT • Navega o PC"`.

    ELA ERA METADE, e a metade que faltava era o TRANSPORTE — medido em
    02/09/2026, com a foto ao lado. O desenho escreve
    `{via} <span class="pt">•</span> {papel}` e põe o `data-campo="navega"` na
    `<div>` que os contém; o pacote mandava só o papel. Como o piloto escreve
    `textContent`, o primeiro tique APAGAVA o "USB •" do cartão — a tela nascia
    dizendo por onde o controle está ligado e parava de dizer meio segundo
    depois, sem que nada acusasse.

    O `via` NÃO SE CALCULA AQUI. `mesa_viva` é o dono da regra
    (`"USB" if transporte == "usb" else "BT"`), e ela já vem mastigada na mesa
    que o piloto monta — repeti-la seria a segunda verdade que envelhece calada.
    O `ctx.conectados` é a resposta CRUA do daemon e traz `transport`; a mesa
    traz `via`. Quem entra na tela é o da mesa.
    """
    papel = "Navega o PC" if primario else "Só a janela"
    return PONTO.join(x for x in (str(c.get("via") or ""), papel) if x)


def _linhas_dos_botoes(p: dict[str, Any]) -> dict[str, str]:
    """As 21 linhas de *o que cada botão faz*, com o RÓTULO que o desenho mostra.

    O VOCABULÁRIO É O DO MOTOR, inteiro: `acoes.BOTOES` diz quais linhas
    existem, `acoes.padrao()` diz o que cada uma faz de fábrica e
    `acoes.rotulo()` traduz o token no texto da `<option>`. O gerador monta as
    mesmas listas do mesmo lugar (`aba06.ACOES_UNI = por_grupo()`), e é por isso
    que o valor emitido aqui SEMPRE existe como opção — condição do
    `escrever()` com `data-hef-alvo="valor"`, que se cala quando não casa.

    O PERFIL VENCE O DE FÁBRICA linha a linha, e não em bloco: `button_actions`
    guarda DIFERENÇA (`None` quer dizer "herda"), então uma linha ausente não é
    "nada" — é o de fábrica.

    SÃO TRÊS CAMADAS DESDE 06/09/2026, e não duas: esta função montava o de
    fábrica com `button_actions` por cima e **nunca olhava `key_bindings`** —
    a mesma cegueira que o `resolver()` tinha antes da ONDA3-MOTOR-01, e com o
    mesmo desfecho, um degrau adiante. Um perfil em que ela escreveu
    `Super` no Options pela janela antiga fazia a tabela mostrar o de fábrica,
    sobre um botão que digitava outra coisa. Agora quem responde é
    `acoes._tabela_efetiva`, pelo `resolver()` — a MESMA chamada que alimenta o
    device —, e as três camadas são o de fábrica, os atalhos da janela antiga e
    a escolha desta tela, nessa ordem.

    O QUE ELA NÃO TEM COMO DIZER continua sem ser dito AQUI, e é de propósito:
    uma combinação livre não é `<option>` de lista nenhuma, `acoes.rotulo()`
    devolve o token cru e o `escrever()` do piloto o recusa em silêncio. Quem
    nomeia essas linhas é a TIRA (`linhas_que_a_lista_nao_sabe_dizer`), porque
    o lugar de dizer o que a tabela não alcança é o texto ao lado dela, e não
    uma opção nova por tecla que ela invente.
    """
    perfil_ = p or {}
    # A MESMA TABELA QUE O DEVICE RECEBE — `resolver()` e este chamador leem
    # a mesma função. Ela é privada do motor, e usá-la daqui é declarado: a
    # alternativa seria montar as três camadas de novo aqui, que é a segunda
    # verdade que esta casa persegue. Ver o relato desta frente.
    tabela = acoes._tabela_efetiva(
        perfil_.get("button_actions") or None,
        perfil_.get("key_bindings") or None)
    return {
        f"{PREFIXO_DA_ACAO}{botao}": acoes.rotulo(str(tabela.get(botao) or ""))
        for botao in acoes.BOTOES
    }


# ---------------------------------------------------------------------------
# A TIRA DE AVISO SOB A TABELA — as três verdades que a tabela escondia.
#
# DECISÃO DO PO, 04/09/2026 (`2026-09-04-O-PO-DECIDE` §2 `06[04]`): *"Uma tira
# de aviso sob a tabela. O que vai ser APAGADO não mora num hover."* Ninguém
# passa o rato onde não sabe que há algo, e as duas linhas que esta tira fecha
# (`Nomear os botões que não digitam nada` e `Nomear os atalhos que o perfil
# guarda e a lista não mostra`) falam justamente do que se perde.
#
# ELA NÃO É A FRASE DA GTK, e a diferença é um FATO medido, não estilo. A
# `input_actions.frase_dos_atalhos_fora_da_lista` termina com *"nada nesta aba
# os apaga"* — verdade na janela antiga, porque lá a fusão de
# `_persist_key_bindings_to_draft` protege o que a lista não mostra. **Aqui é o
# contrário**: o "Voltar ao padrão" desta tela zera `key_bindings` inteiro, e o
# "Guardar" faz `apply_button_actions` reescrever o conjunto todo a partir do de
# fábrica (`profiles/manager.py:570`, `core/acoes_de_botao.resolver`, que nunca
# consulta `profile.key_bindings`). Copiar a frase de lá seria a tela afirmando
# o oposto do que este produto faz — e é a família de defeito que esta casa
# persegue acima de todas.
#
# O QUE ELA **NÃO** DUPLICA: nenhum nome de botão e nenhum rótulo de tecla é
# escrito aqui. Os nomes saem de `input_actions.humanize_button` e as teclas de
# `input_actions.humanize_binding` — os mesmos donos que a GTK usa —, e o que
# cada linha faz sai de `core/acoes_de_botao`.
# ---------------------------------------------------------------------------


def _colado(ligacao: Any) -> str:
    """A ligação do perfil na forma com `+`, que é a que o produto lê de volta.

    O perfil guarda combo como LISTA (`["KEY_LEFTCTRL", "KEY_W"]`) e tecla
    solta às vezes como string. `keyboard_mappings.parse_binding` lê a forma
    colada — um round-trip, e não uma segunda grafia.
    """
    if isinstance(ligacao, (list, tuple)):
        return "+".join(str(t) for t in ligacao)
    return str(ligacao)


def _atalho_em_palavras(colado: str) -> str:
    """`"KEY_LEFTCTRL+KEY_W"` → `"Ctrl + W"`, pelo dono do produto.

    O IMPORT É TARDIO pela mesma razão de `_nome_do_botao`: `input_actions` puxa
    GTK no topo, e os pacotes são puros de propósito. Sem GTK no ambiente volta
    o token cru, que é feio e é honesto.
    """
    try:
        from hefesto_dualsense4unix.app.actions.input_actions import humanize_binding
    except Exception:
        return colado
    return str(humanize_binding(colado))


def _dois_donos() -> list[tuple[str, str, str]]:
    """Os botões que o mouse E o teclado atendem ao mesmo tempo, DE FÁBRICA.

    `(botão, o que a tabela mostra, o que o teclado faz no mesmo botão)`.

    MEDIDO, NÃO DIGITADO: `acoes.padrao()` mostra o do MOUSE quando os dois têm
    opinião (o docstring dele diz por quê — é o que a pessoa vê acontecer com o
    cursor na frente dela), e `DEFAULT_BUTTON_BINDINGS` diz o do teclado. Onde
    os dois discordam, o produto faz OS DOIS e a tabela conta metade.

    Hoje isso dá um botão só — o R3, "Botão do meio" para o mouse e "Fechar o
    teclado na tela" para o teclado —, e a colisão já está escrita em
    `core/keyboard_mappings.py:47-52`. Derivar em vez de digitar é o que faz
    esta tira acompanhar o dia em que um segundo botão entrar na mesma situação.
    """
    from hefesto_dualsense4unix.core.keyboard_mappings import DEFAULT_BUTTON_BINDINGS

    de_fabrica = acoes.padrao()
    fora: list[tuple[str, str, str]] = []
    for botao in acoes.BOTOES:
        ligacao = DEFAULT_BUTTON_BINDINGS.get(botao)
        if not ligacao:
            continue
        colado = "+".join(ligacao)
        na_tabela = str(de_fabrica.get(botao) or "")
        if na_tabela and na_tabela != colado:
            fora.append((botao, acoes.rotulo(na_tabela), acoes.rotulo(colado)))
    return fora


#: OS DOIS MAPAS QUE O `set_button_actions` RECONSTRÓI DO DE FÁBRICA, e é deles
#: que sai o defeito medido em 04/09/2026 nesta frente:
#:
#:     self._mapa_dpad = {b: k for b, k in DPAD_TO_KEY.items() if b not in do_mouse}
#:     self._mapa_tap  = {b: k for b, k in EDGE_KEY_MAP.items() if b not in do_mouse}
#:                                        (`integrations/uinput_mouse.py:315-316`)
#:
#: Um botão em `— Nada —` **não entra em `do_mouse`** — o `resolver()` o pula de
#: propósito —, logo ele não é subtraído desses dois mapas e **continua
#: emitindo o de fábrica**. Medido, com o `resolver()` e os mapas do dono:
#:
#:     "— Nada —" no cross    -> calou de verdade
#:     "— Nada —" no options  -> calou de verdade
#:     "— Nada —" no dpad_up  -> AINDA emite KEY_UP
#:     "— Nada —" no circle   -> AINDA emite KEY_ENTER
#:
#: São SEIS das vinte e uma linhas: as quatro direções do d-pad, o Círculo e o
#: Quadrado. A cura é do MOTOR (`uinput_mouse.set_button_actions` precisa saber
#: quais botões foram calados de propósito, e hoje não sabe: `do_mouse` não
#: distingue "não é do mouse" de "foi calado") e está no relato desta frente.
#: Enquanto ela não vem, **a tela diz**, que é o contrário de um botão que
#: responde calado.
#:
#: A REGRA É COPIADA, e a duplicação é declarada — os MAPAS são importados do
#: dono, nunca digitados, e `test_a_aba_06_navegacao_fecha_as_linhas.py` chama o
#: `set_button_actions` DE VERDADE e compara com o que esta função responde.


def _mapas_que_sobrevivem_ao_nada() -> frozenset[str]:
    """Os botões cujo som de fábrica o `— Nada —` da tela não desliga."""
    from hefesto_dualsense4unix.integrations.uinput_mouse import (
        DPAD_TO_KEY,
        EDGE_KEY_MAP,
    )

    return frozenset(DPAD_TO_KEY) | frozenset(EDGE_KEY_MAP)


def _o_que_a_tabela_diz_de_cada_botao(p: dict[str, Any]) -> dict[str, str]:
    """Botão -> token que VALE agora: o de fábrica com o perfil por cima."""
    escolhas = (p.get("button_actions") or None) if p else None
    tabela = acoes.padrao()
    if escolhas:
        tabela.update({b: a for b, a in escolhas.items() if b in tabela})
    return tabela


def _linhas_que_nao_acendem(p: dict[str, Any]) -> tuple[list[str], list[str]]:
    """`(as que calaram de verdade, as que o "— Nada —" NÃO calou)`.

    A primeira lista tem DUAS origens, e as duas são do motor: a escolha
    `— Nada —` que o device realmente atende, e a terceira sacola do
    `resolver()` — os comandos sem atendente, os papéis de eixo pedidos a um
    botão e o gatilho cuja escolha diverge do espelho dele.

    A segunda é o defeito medido acima, e ela existe para a tela poder dizê-lo.
    """
    tabela = _o_que_a_tabela_diz_de_cada_botao(p)
    escolhas = (p.get("button_actions") or None) if p else None
    mudos = {b for b in acoes.BOTOES if tabela.get(b) == acoes.TOKEN_NADA}
    teimosos = mudos & _mapas_que_sobrevivem_ao_nada()
    _do_mouse, _do_teclado, sem_dono = acoes.resolver(escolhas)
    return sorted((mudos - teimosos) | set(sem_dono)), sorted(teimosos)


def atalhos_que_param_de_valer(p: dict[str, Any]) -> list[tuple[str, str]]:
    """Os `key_bindings` do perfil que o "Guardar" desta tela faz parar de valer.

    **É A METADE VISÍVEL DO DEFEITO §3-1**, e o defeito é do produto, não desta
    aba: `apply_button_actions` (`profiles/manager.py:570`) roda DEPOIS do
    `apply_keyboard` e chama `teclado.set_bindings(...)` com o conjunto INTEIRO
    que `acoes_de_botao.resolver()` deriva — e `resolver()` parte de
    `acoes.padrao()` e **nunca consulta `profile.key_bindings`**. Logo, um perfil com
    `button_actions` preenchido apaga o efeito do que ela escreveu à mão na
    janela antiga, em silêncio, na próxima ativação.

    A COMPARAÇÃO É CONTRA O QUE O DAEMON VAI APLICAR, e não contra a lista da
    tela: `resolver(button_actions)` é literalmente a chamada que o
    `apply_button_actions` faz. Um atalho que COINCIDA com o resultado sobrevive
    — por coincidência, e não por cuidado — e não entra aqui, porque nomear o
    que não se perde é ruído.

    A RESSALVA QUE A FRASE CARREGA, e ela é medida: sem device de mouse vivo o
    `apply_button_actions` sai antes (`manager.py:614`) e nada é reescrito. Por
    isso a tira diz *"quando o mouse virtual estiver de pé"* em vez de prometer
    o desastre em todo caso.

    ELA NÃO MORREU SOZINHA, e o fato estava errado AQUI — 06/09/2026. Esta
    linha dizia *"ela morre sozinha no dia em que `resolver()` passar a herdar
    `key_bindings`"*. O `resolver()` herdou (ONDA3-MOTOR-01) **e a função não
    morreu**: quem precisava passar o campo era o CHAMADOR, e ele continuava
    chamando `resolver(button_actions)` com um argumento só — a assinatura de
    antes, byte a byte, que é o contrato que aquela frente preservou de
    propósito. Com o campo passado, a lista deixa de nomear os oito botões do
    `DOMINIO_DO_TECLADO` (que agora sobrevivem) e passa a nomear **só os que
    ainda se perdem de verdade**: os que ela escreveu na janela antiga FORA
    daquele domínio — o `cross`, o `triangle`, o `r3` —, para os quais o
    `apply_button_actions` reescreve o teclado inteiro sem consultá-los.

    :returns: `[(botão, o binding colado), …]`, em ordem de botão.
    """
    atalhos = (p.get("key_bindings") or {}) if p else {}
    if not atalhos:
        return []
    _do_mouse, do_teclado, _sem = acoes.resolver(
        (p or {}).get("button_actions"), atalhos)
    fora: list[tuple[str, str]] = []
    for botao, ligacao in sorted(atalhos.items()):
        agora = (tuple(ligacao) if isinstance(ligacao, (list, tuple))
                 else (str(ligacao),))
        if do_teclado.get(botao) == agora:
            continue
        fora.append((botao, _colado(agora)))
    return fora


# ---------------------------------------------------------------------------
# A TELA "Teclas do teclado" — 06/09/2026, NAVEGACAO-TECLAS-01.
#
# O QUE ELA FECHA: a linha `FALTA_NO_HTML` de *Editar QUAL TECLA cada botão
# digita* (`docs/data/paridade-gtk-html.csv:208`). A janela antiga tem uma
# coluna EDITÁVEL EM TEXTO — ela digita `Alt + Tab`, `Ctrl + Shift + F`,
# `Super`, e `dehumanize_binding` traduz —, e a tela nova só oferecia uma LISTA
# FECHADA de 26 ações. Tudo o que estivesse fora dela — um F5, um Ctrl + W,
# qualquer combinação que ela invente — a GTK escrevia e o HTML não tinha como
# escrever, por nenhuma aba.
#
# NENHUMA TABELA DE NOMES DE TECLA NASCE AQUI, e é a exigência da sprint com
# todas as letras: *"uma segunda tabela de nomes de tecla é a segunda verdade
# mais previsível deste repositório"*. São TRÊS donos, cada um respondendo o que
# só ele sabe, e o import dos dois primeiros é TARDIO porque `input_actions`
# puxa GTK no topo e os pacotes são puros de propósito:
#
#   `input_actions.humanize_binding`   token cru  -> o que ela lê
#   `input_actions.dehumanize_binding` o que ela digita -> token cru
#   `keyboard_mappings.parse_binding`  a FORMA (`KEY_*` ou `__…__`), e recusa
#   `uinput_keyboard.SUPPORTED_KEYS`   o que o device virtual SABE EMITIR
#
# O QUARTO É O QUE FALTAVA, e sem ele a tela aceitaria calada. `parse_binding`
# só confere o PREFIXO — `KEY_BANANA` passa por ele —, e o device
# (`uinput_keyboard._emit_sequence_press`) faz `getattr(u, key_name, None)` e
# **pula em silêncio** o que o módulo não conhece. Uma tecla inventada seria
# gravada no perfil, apareceria na tela e não digitaria nada: o botão que
# responde calado, com o dado dela no disco.
#
# O DOMÍNIO É DE OITO BOTÕES, E ELE É PERGUNTADO — `acoes.DOMINIO_DO_TECLADO`,
# que o motor DERIVA dos quatro mapas do produto (hoje: `create`, `l1`, `l3`,
# `options`, `r1` e as três regiões do touchpad). São os botões sobre os quais
# `key_bindings` manda; nos outros catorze o que vale é o mapa fixo do
# `UinputMouseDevice`, e escrever `key_bindings` neles seria gravar no disco uma
# escolha que o `resolver()` não lê — a ausência de dado, que se lê como "a
# mudança não pegou". Ver `_tabela_efetiva` em `core/acoes_de_botao.py`.
# ---------------------------------------------------------------------------


def _traduzir(texto: str) -> str:
    """`"Ctrl + W"` → `"KEY_LEFTCTRL+KEY_W"`, PELO DONO DA JANELA ANTIGA.

    Sem GTK no ambiente o `input_actions` não importa, e aí o texto volta como
    veio: quem valida é a etapa seguinte, e ela recusa dizendo. Inventar uma
    tradução aqui seria a segunda tabela que este bloco existe para não ter.
    """
    try:
        from hefesto_dualsense4unix.app.actions.input_actions import (
            dehumanize_binding,
        )
    except Exception:
        return texto.strip()
    return str(dehumanize_binding(texto.strip()))


def _desfazer_o_humanize(cru: str) -> str:
    """O que sobrou do `dehumanize_binding` e é o `humanize_binding` ao contrário.

    **UM DEFEITO DE ROUND-TRIP NO DONO, medido em 06/09/2026, e ele é da JANELA
    ANTIGA também.** `humanize_binding` tem um ramo de FALLBACK — um `KEY_*` que
    não está em `_KEY_LABELS` vira `tok[4:]`, então `KEY_F5` aparece na tela
    como `F5`. `dehumanize_binding` **não desfaz esse ramo**: ele só converte
    caractere ÚNICO (`W` → `KEY_W`), e `F5` volta como `F5`, que o
    `parse_binding` recusa.

    Medido, com as duas funções do dono:

        humanize_binding("KEY_F5")     -> "F5"
        dehumanize_binding("F5")       -> "F5"        (não volta a ser tecla)
        parse_binding("F5")            -> ValueError

    Alcança **F1..F12, Home, End, Insert, PageUp, PageDown, Comma, Dot e as três
    de volume** — tudo o que o teclado virtual declara e o `_KEY_LABELS` não
    nomeia. Sem esta linha, a tela mostraria `F5` numa linha e RECUSARIA o
    "Guardar" da mesma tela, sem ela ter tocado em nada.

    ISTO NÃO É UMA SEGUNDA TABELA — é o ramo de fallback do dono, aplicado ao
    contrário, e **quem decide é o device**: só vira `KEY_<X>` o que
    `uinput_keyboard.SUPPORTED_KEYS` declara. O que não estiver lá segue como
    veio e cai na recusa da etapa seguinte, com a frase do dono.

    A CURA DE VERDADE É NO DONO (`input_actions.dehumanize_binding`), e está
    relatada: a janela antiga tem o mesmo buraco — ela mostra `F5` na coluna
    "Tecla do teclado" e recusa `F5` quando alguém o digita de volta.
    """
    sabe = _teclas_que_o_device_sabe()
    fora = []
    for tok in cru.split("+"):
        tok = tok.strip()
        if not tok:
            continue
        if not tok.startswith("KEY_") and not tok.startswith("__"):
            candidato = f"KEY_{tok.upper()}"
            if candidato in sabe:
                tok = candidato
        fora.append(tok)
    return "+".join(fora)


def _teclas_que_o_device_sabe() -> frozenset[str]:
    """O que o teclado virtual SABE EMITIR — perguntado ao dono.

    `uinput_keyboard.SUPPORTED_KEYS` é a lista de capacidades que o device
    declara ao `uinput` no `start()`. Uma tecla fora dela não é emitida: o
    `_emit_sequence_press` faz `getattr(u, key_name, None)` e segue em frente.
    """
    from hefesto_dualsense4unix.integrations.uinput_keyboard import SUPPORTED_KEYS

    return frozenset(SUPPORTED_KEYS)


def tokens_da_tecla(texto: str) -> tuple[str, ...]:
    """O que ela digitou, virado tokens do produto — ou `ValueError` DIZENDO.

    Vazio devolve `()`, e isso quer dizer **este botão não digita nada**: é o
    mesmo `— Nada —` da lista ao lado, dito pelo campo em branco. Não é erro, e
    tratá-lo como erro faria a tela recusar o gesto mais natural de todos —
    apagar o que está escrito.

    AS TRÊS RECUSAS SÃO DOS DONOS, e nenhuma frase de tecla é redigida aqui:

    1. a FORMA, de `keyboard_mappings.parse_binding` — ele levanta `ValueError`
       com o token que não entendeu;
    2. a CAPACIDADE, de `uinput_keyboard.SUPPORTED_KEYS` — a tecla existe no
       vocabulário e o device virtual não a declara;
    3. a MISTURA, de `uinput_keyboard._delegate_virtual_tokens` — um
       `__OPEN_OSK__` junto com um `KEY_*` é rejeitado LÁ com um `warning` e
       sem emitir nada. Recusar aqui é dizer na tela o que o daemon diria no
       journal.
    """
    cru = _desfazer_o_humanize(_traduzir(texto))
    if not cru:
        return ()
    from hefesto_dualsense4unix.core.keyboard_mappings import (
        is_virtual_token,
        parse_binding,
    )

    tokens = parse_binding(cru)  # ValueError com a frase do dono
    virtuais = [t for t in tokens if is_virtual_token(t)]
    if virtuais and len(virtuais) != len(tokens):
        raise ValueError(
            f"{texto.strip()!r} mistura um comando (“{virtuais[0]}”) com teclas "
            "comuns, e o teclado do Hefesto recusa a mistura sem digitar nada. "
            "Escolha um ou outro.")
    if not virtuais:
        sabe = _teclas_que_o_device_sabe()
        faltam = [t for t in tokens if t not in sabe]
        if faltam:
            raise ValueError(
                "o teclado do Hefesto não sabe digitar "
                + ", ".join(f"“{_atalho_em_palavras(t)}”" for t in faltam)
                + f" (de {texto.strip()!r}). Ele só emite as teclas que declara "
                  "ao sistema quando nasce, e essa não está entre elas.")
    return tokens


def _o_que_cada_botao_digita(p: dict[str, Any]) -> dict[str, tuple[str, ...]]:
    """Botão -> as teclas que ele digita AGORA, perguntado ao motor.

    É a segunda sacola do `resolver()`, com as TRÊS camadas já aplicadas na
    ordem do produto (de fábrica, `key_bindings`, `button_actions`) — a mesma
    chamada que `profiles/manager.apply_button_actions` faz para alimentar o
    device. Ler daqui é o que impede esta tela de mostrar uma coisa e o
    aparelho digitar outra.
    """
    perfil_ = p or {}
    _do_mouse, do_teclado, _sem = acoes.resolver(
        perfil_.get("button_actions") or None,
        perfil_.get("key_bindings") or None)
    return do_teclado


def teclas_dos_botoes(p: dict[str, Any]) -> dict[str, str]:
    """Os oito campos da tela "Teclas do teclado", com o texto que ela lê.

    Vazio quando o botão não digita nada — é a regra dela para toda a casa
    (*campo sem informação não mostra nada*), e é o que faz o campo em branco
    querer dizer a mesma coisa na leitura e na escrita.
    """
    digita = _o_que_cada_botao_digita(p)
    return {
        f"{PREFIXO_DA_TECLA}{botao}": _atalho_em_palavras(
            "+".join(digita.get(botao) or ()))
        for botao in sorted(acoes.DOMINIO_DO_TECLADO)
    }


def linhas_que_a_lista_nao_sabe_dizer(p: dict[str, Any]) -> list[tuple[str, str]]:
    """As linhas cuja tecla o `<select>` das 22 NÃO tem como mostrar.

    O DEFEITO QUE ELA NOMEIA, e ele é o preço de aceitar combinação livre: a
    lista da tabela oferece 26 ações, e uma combinação que ela escreveu não
    está entre elas. `acoes.rotulo()` devolve o token CRU nesse caso, o
    `escrever()` do piloto recusa em silêncio o texto que não casa com nenhuma
    `<option>` (`hefesto_vivo.py`, `if(!tem) return 0;`) — e o que fica na tela
    é o rótulo que o **desenho** cravou. A linha passa a AFIRMAR uma ação que o
    botão não faz.

    ELA É DITA NA TIRA, e não curada na lista: pôr a combinação como opção nova
    faria a lista crescer a cada tecla que ela inventasse, que é exatamente o
    que a tela de texto existe para não fazer.

    :returns: `[(botão, o que ele digita, em palavras), …]`.
    """
    digita = _o_que_cada_botao_digita(p)
    fora: list[tuple[str, str]] = []
    for botao in acoes.BOTOES:
        colado = "+".join(digita.get(botao) or ())
        if not colado or colado in acoes.ACOES:
            continue
        fora.append((botao, _atalho_em_palavras(colado)))
    return fora


def _o_ps_digita(token: str | None) -> bool | None:
    """O token escolhido é coisa que o PS sabe entregar? — PERGUNTADO AO DONO.

    `None` quer dizer *"não deu para perguntar"*, e é diferente de `False`: sem
    o dono, a tira NÃO INVENTA a resposta e não escreve linha nenhuma. É a regra
    dela de 30/08 — *"se não tá mostrando agora, não tem info pra mostrar"*.

    O DONO É `daemon/subsystems/hotkey._o_ps_digita`, e é ele que o toque no PS
    consulta de verdade (`_a_metade_da_maquina`). Copiar a regra para cá criaria
    a segunda tabela que esta casa persegue: no dia em que o PS aprender a
    disparar um programa, a tira continuaria dizendo que ele não sabe.

    O IMPORT É TARDIO pela mesma razão de `_nome_do_botao` e
    `_atalho_em_palavras`: os pacotes são puros de propósito — importáveis sem
    janela e sem daemon. Medido nesta árvore: 158 ms no primeiro tique, e o
    módulo NÃO arrasta `gi`.
    """
    try:
        from hefesto_dualsense4unix.daemon.subsystems.hotkey import (
            _o_ps_digita as do_dono,
        )
    except Exception:
        return None
    return bool(do_dono(token))


def _o_que_o_ps_faz(p: dict[str, Any]) -> str:
    """A quinta frase da tira: as DUAS coisas que o botão PS faz ao mesmo tempo.

    DECISÃO DELA, 06/09/2026 (06-Q3): *"O PS ganha a mesma lista das outras 21
    linhas; se você der uma tecla a ele, ele passa a digitar SEM parar de abrir
    a Steam, **e a tabela não avisa isso**."* Esta função é a última oração —
    ela existe para fazê-la deixar de ser verdade.

    ELA NASCE SÓ QUANDO HÁ O QUE DIZER, como as outras quatro. Sem escolha no
    perfil o PS é só o que sempre foi, e uma tira que fala sempre é uma tira que
    ninguém lê. Com `— Nada —` também não há duas coisas: o `__NADA__` é o
    espelho exato do `"none"` da máquina e cala as duas metades — está na tabela
    de precedência de `hotkey._a_metade_da_maquina`.

    A TIRA NÃO NOMEIA O ATO DA MÁQUINA, e a razão é medida: o estado que o
    daemon publica à tela **não traz `ps_button_action`** (`ipc_handlers` só o
    devolve na resposta de `daemon.reload`). Escrever "continua abrindo a
    Steam" seria afirmar o degrau de fábrica sobre uma máquina que ninguém
    perguntou — e ele é ajustável (`steam` · `none` · `custom`). O que a frase
    afirma é o que vale nos três casos: o PS **continua sendo a saída de
    emergência**, porque os gestos e o segurar-para-alternar não passam por
    aquele campo. RELATO: publicar `ps_button_action` no estado é o que deixa a
    tira nomear as duas metades, e é de quem for dono do IPC.

    O SEGUNDO RAMO É O SILÊNCIO QUE A 06-01 DEIXOU DECLARADO: o `resolver()`
    tira o PS das três sacolas, então uma escolha que ninguém atende (um
    `BTN_*`, um papel de eixo, "Abrir um programa") **não entra em `sem_dono`**
    e não aparece na frase "Não acendem nada hoje". O daemon a registra no
    journal como `ps_solo_escolha_sem_atendente`; sem esta linha, a tela seria o
    único lugar calado.

    :returns: a frase, ou `""` quando não há o que dizer.
    """
    escolha = acoes.acao_do_ps((p or {}).get("button_actions"))
    if not escolha or escolha == acoes.TOKEN_NADA:
        return ""
    digita = _o_ps_digita(escolha)
    if digita is None:
        return ""
    nome = _nome_do_botao(acoes.BOTAO_PS)
    rotulo = acoes.rotulo(escolha)
    if digita:
        return (f"<b>{nome}: duas coisas ao mesmo tempo.</b> Ele digita "
                f"“{rotulo}” <b>e</b> continua sendo a saída de emergência — os "
                "gestos desta aba saem dele, e segurá-lo alterna o modo jogo. "
                "Dentro de um jogo ele não faz nenhuma das duas.")
    if escolha == acoes.TOKEN_STEAM:
        return ""
    return (f"<b>O {nome} ainda não faz “{rotulo}”:</b> hoje ele só sabe digitar "
            "teclas e abrir o teclado na tela. A escolha fica guardada no "
            "perfil — é feature que falta, não erro seu.")


def _aviso_da_tabela(p: dict[str, Any]) -> str:
    """A tira sob a tabela de botões — vazia quando não há o que perder.

    CINCO FRASES, e nenhuma nasce se o fato dela não existir. A tira só ocupa
    espaço nos perfis em que há mesmo algo a dizer, que é o que a decisão do PO
    pede: *"a tira se esconde vazia, como a de estados já faz"*.

    A QUINTA É O BOTÃO PS — 06/09/2026, decisão dela na 06-Q3. Ela vem por
    último de propósito: as quatro primeiras falam da tabela inteira, e esta
    fala de UMA linha. Ver `_o_que_o_ps_faz`.
    """
    partes: list[str] = []
    donos = _dois_donos()
    if donos:
        quais = "; ".join(
            f"{_nome_do_botao(b)} faz “{do_mouse}” para o mouse e “{do_teclado}” "
            f"para o teclado"
            for b, do_mouse, do_teclado in donos)
        partes.append(
            f"<b>Dois donos:</b> {quais}. A tabela mostra só o do mouse, e "
            "guardar aqui deixa valendo só o que ela mostra.")
    mudos, teimosos = _linhas_que_nao_acendem(p)
    if mudos:
        partes.append(
            "<b>Não acendem nada hoje:</b> "
            + ", ".join(_nome_do_botao(b) for b in mudos)
            + ". A escolha fica guardada no perfil — é feature que falta, não "
              "erro seu.")
    if teimosos:
        partes.append(
            "<b>“— Nada —” ainda não cala estes:</b> "
            + ", ".join(_nome_do_botao(b) for b in teimosos)
            + ". Eles continuam digitando o de fábrica, porque o Hefesto ainda "
              "não sabe distinguir “este botão não é do mouse” de “este botão "
              "foi calado”.")
    perdidos = atalhos_que_param_de_valer(p)
    if perdidos:
        quais = ", ".join(f"{_nome_do_botao(b)} = {_atalho_em_palavras(t)}"
                          for b, t in perdidos)
        partes.append(
            f"<b>O perfil guarda atalhos que esta lista não diz:</b> {quais}. "
            "Guardar aqui substitui o conjunto inteiro de atalhos pelo que a "
            "tabela mostra, e esses param de valer assim que o mouse virtual "
            "estiver de pé.")
    # A SEXTA FRASE — 06/09/2026, NAVEGACAO-TECLAS-01. Ela nasce com a tela de
    # texto, e sem ela a tela de texto CRIARIA um defeito: uma combinação livre
    # não tem `<option>` na lista de 26, o `escrever()` recusa em silêncio, e a
    # linha fica AFIRMANDO o rótulo que o desenho cravou. Ver
    # `linhas_que_a_lista_nao_sabe_dizer`.
    mudas = linhas_que_a_lista_nao_sabe_dizer(p)
    if mudas:
        partes.append(
            "<b>A lista não sabe mostrar a tecla destas linhas:</b> "
            + ", ".join(f"{_nome_do_botao(b)} digita {t}" for b, t in mudas)
            + ". Elas valem assim mesmo; o que a lista mostra nelas não é o que "
              "o botão faz. Use <b>Teclas do teclado</b> para ver e trocar.")
    do_ps = _o_que_o_ps_faz(p)
    if do_ps:
        partes.append(do_ps)
    if not partes:
        return NADA_A_DIZER
    return "".join(f"<div>{x}</div>" for x in partes)


#: O QUE ELA JÁ ESCOLHEU E AINDA NÃO GUARDOU: `acao-<botão>` → o rótulo que
#: está no `<select>`. Só entram as linhas que DIFEREM do que o perfil guarda —
#: escolher de volta o valor do perfil tira a linha daqui, e com o dicionário
#: vazio a aba volta a ser exatamente o que era antes desta trava.
#:
#: DECISÃO DELA, 02/09/2026: *"o Guardar FICA. As 21 listas param de ser
#: repintadas enquanto ela está mexendo, até guardar ou sair. **Não** vira
#: gravação automática: ela quer escolher várias, conferir e aplicar de uma
#: vez."*
#:
#: O QUE ISSO CURA, e estava medido no próprio arquivo: a pintura desfazia a
#: escolha de quem clica em ≤1,5 s (quinze tiques de `hefesto_vivo.TIQUE_MS`),
#: e por isso o "Guardar" NUNCA recebia uma forma diferente do perfil —
#: ele caía sempre no ramo de "não havia o que guardar". A recusa daquele ramo
#: ainda mandava *"troque a linha antes de clicar"*, um caminho que o mesmo
#: arquivo declarava não existir. Agora existe.
#:
#: ELE É DE MÓDULO, e é de propósito: o pacote é chamado uma vez por tique e não
#: tem onde guardar estado entre tiques. O piloto é um processo por janela e uma
#: janela por vez — não há duas telas desta aba no mesmo processo.
_MEXENDO: dict[str, str] = {}

#: Quando a tabela foi pintada pela última vez (`time.monotonic`). É o que
#: distingue "ela continua na aba" de "ela saiu e voltou".
_ULTIMA_PINTURA = 0.0

#: A PAUSA QUE SIGNIFICA OUTRA ABA. O tique do piloto é de 100 ms
#: (`hefesto_vivo.TIQUE_MS`), e enquanto ela estiver nesta página o `pacote()`
#: é chamado a cada tique. Cinco segundos sem uma chamada só acontecem se a página
#: SAIU de cena — e voltar a ela é um documento NOVO, com os 21 `<select>` de
#: volta no que o gerador cravou. Aí a trava tem de estar solta, senão a tabela
#: ficaria mostrando o desenho com o perfil dizendo outra coisa.
#:
#: NÃO SE IMPORTA `TIQUE_MS` DAQUI: `hefesto_vivo` puxa GTK no topo, e os
#: pacotes são puros de propósito — importáveis sem janela, testáveis sem
#: display. O número está escrito com a conta ao lado, que é o que permite
#: conferir a divergência se o tique mudar.
#:
#: O CUSTO ESTÁ DECLARADO: um daemon mudo por mais de cinco segundos também
#: interrompe a pintura (o `_tique` do piloto volta antes de chamar o pacote), e
#: nesse caso as escolhas pendentes são largadas como se ela tivesse saído. É o
#: preço de não haver, hoje, um sinal de "a página recarregou" que chegue ao
#: pacote — e ele erra para o lado seguro: a tela volta a mostrar o perfil, que
#: é a verdade do disco, em vez de fingir uma escolha que ninguém mais está
#: fazendo.
PAUSA_DE_OUTRA_ABA = 5.0


def _largar_o_que_ela_mexeu() -> None:
    """Solta a trava. Chamado pelo "Guardar", pelo "Voltar ao padrão" e pelo sair."""
    _MEXENDO.clear()


def _o_que_a_tabela_mostra(p: dict[str, Any]) -> dict[str, str]:
    """As 21 linhas: o perfil, com as que ela está mexendo por cima.

    A PINTURA NÃO PARA — ela passa a CONCORDAR com a tela, que é a única forma
    estável de "não repintar". Um pacote que simplesmente OMITISSE as 21 chaves
    deixaria a tabela sem dono: a página recarregada mostraria o desenho para
    sempre, e o contador de pinturas do piloto perderia 21 endereços vivos. Aqui
    o valor emitido é o que o `<select>` já tem, então `escrever()` devolve 0 e
    nada pisca — e o que ela escolheu continua na tela até guardar ou sair.

    A JANELA DE SAÍDA é medida pelo relógio, e não por um sinal do piloto: ver
    `PAUSA_DE_OUTRA_ABA`.
    """
    global _ULTIMA_PINTURA

    agora = time.monotonic()
    if _MEXENDO and _ULTIMA_PINTURA and agora - _ULTIMA_PINTURA > PAUSA_DE_OUTRA_ABA:
        # ELA SAIU DA ABA. O documento que ela vê agora é outro, e nele os 21
        # `<select>` voltaram ao que o gerador cravou — segurar as escolhas
        # velhas por cima disso seria pintar uma decisão que ela abandonou.
        _largar_o_que_ela_mexeu()
    _ULTIMA_PINTURA = agora
    linhas = _linhas_dos_botoes(p)
    # OS OITO CAMPOS DE TEXTO ENTRAM NA MESMA TRAVA, e é a exigência da sprint:
    # *"um campo de texto sendo editado não pode ser reconstruído sob os dedos
    # dela"*. Sem isto o tique de 100 ms escreveria o valor do perfil por cima
    # da primeira letra que ela digitasse — o `escrever()` com alvo `valor` faz
    # `el.value = t` assim que os dois diferem, e um campo em edição SEMPRE
    # difere. O gesto `tecla-escrita` é quem anota; aqui a pintura CONCORDA.
    linhas.update(teclas_dos_botoes(p))
    # SÓ AS QUE AINDA DIFEREM. Se o perfil já passou a dizer o que ela escolheu
    # (o "Guardar" gravou, ou outro caminho mudou o perfil), a linha sai da
    # trava sozinha — e a trava se esvazia sem ninguém precisar lembrar.
    for campo in list(_MEXENDO):
        if campo not in linhas or linhas[campo] == _MEXENDO[campo]:
            del _MEXENDO[campo]
    linhas.update(_MEXENDO)
    return linhas


@registrar("06-navegacao.html")
def pacote(ctx: Contexto) -> dict[str, Any]:
    st = ctx.state
    rato = st.get("mouse_emulation") or {}
    tecla = st.get("keyboard_emulation") or {}
    p = perfil.ativo(st.get("active_profile"))
    atalhos = (p.get("key_bindings") or {}) if p else {}

    cards = {}
    for c in ctx.conectados:
        uniq = str(c.get("uniq") or "")
        # A MESA É QUEM TEM O `via`. `ctx.conectados` é a resposta crua do
        # daemon (`transport`), e a tradução para "USB"/"BT" tem dono em
        # `mesa_viva.mesa_do_estado`. Sem casa na mesa (um controle que entrou
        # entre a montagem da mesa e este tique), a linha sai só com o papel —
        # meia verdade, nunca um transporte inventado.
        na_mesa = next((m for m in ctx.mesa if str(m.get("uniq") or "") == uniq), {})
        cards[uniq] = {
            "navega": _linha_do_cartao(na_mesa, bool(c.get("is_primary"))),
            # O NOME DO APARELHO, do dono que a ROTA-A deixou pronto. Ele lê,
            # nesta ordem, o que ELA nomeou > o modelo decodificado > o nome da
            # mesa > o transporte sozinho — e NUNCA a posição, que foi o que
            # fazia o mesmo controle mudar de nome quando o segundo entrava.
            "identidade": identidade_de(c, ctx.mesa),
        }
    # A COR DA BORDA DE CADA LUGAR, na ORDEM DA MESA DO DESENHO. Vai em `mesa`
    # e não em `colunas` porque o elemento que a recebe É o `[data-controle]`:
    # o `achar()` do piloto varre os DESCENDENTES de um cartão, nunca o próprio
    # cartão. Uma lista se distribui pelos elementos de mesmo endereço, na
    # ordem — que aqui é a ordem dos quatro lugares no HTML.
    #
    # QUATRO ENTRADAS, SEMPRE: os dois lugares vazios recebem `""`, e `""`
    # apaga a cor de linha e devolve a borda ao neutro do CSS. Sem as duas
    # últimas, um lugar que ficasse vazio guardaria a cor do controle que saiu.
    plastico = [cor_do_plastico(str(m.get("cor") or "")) for m in ctx.mesa]
    # O DESENHO DE CADA LUGAR, PELO MESMO CAMINHO E PELA MESMA ORDEM —
    # 03/09/2026, A-COR-VEM-DO-APARELHO. O `<svg>` escolhe o modelo por
    # `data-colorway`, e até hoje esse atributo era o do MOCKUP: com o P1 dela
    # em White, o `<svg>` do cartão dizia `cosmic-red`.
    #
    # A TELA JÁ MOSTRAVA A COR CERTA, e é o fato que mais importa aqui: a
    # `folha_do_plastico` sobrescrevia as VARIÁVEIS do modelo e o casco saía
    # White (medido no WebKit em 03/09: `rgb(228, 224, 216)`). O que estava
    # errado não era o pixel — era o mecanismo: as REGRAS que leem essas
    # variáveis são `svg[data-colorway="cosmic-red"] …`, e só casavam porque o
    # atributo do mockup tinha ficado. Ligar o atributo, que é o que a lei
    # pede, teria QUEBRADO o desenho — e foi por isso que a página passou a
    # publicar os 28 modelos no mesmo movimento.
    #
    # OS QUATRO LUGARES, SEMPRE, e a razão é a mesma da linha de cima: o piloto
    # distribui a lista pelos elementos de mesmo `data-campo` NA ORDEM do HTML.
    # Uma lista mais curta deixaria o lugar vazio com o colorway do desenho.
    desenho = [colorway_do_aparelho(str(m.get("cor") or "")) for m in ctx.mesa]
    # QUEM NAVEGA O PC É O PRIMÁRIO, e quem o marca é o daemon (`is_primary`).
    # O gerador tirava o MENOR número da mesa, que acerta por coincidência
    # enquanto o P1 estiver na frente.
    chefe = next((c for c in ctx.conectados if c.get("is_primary")), None)
    do_chefe = next((m for m in ctx.mesa
                     if str(m.get("uniq") or "") == str((chefe or {}).get("uniq") or "")),
                    {}) if chefe else {}
    mesa = {
        # A FITA DO TOPO, quando o dono dela desiste — ver `chips_da_fita`.
        "fita-chips": chips_da_fita(ctx.mesa),
        "plastico": plastico + [""] * max(0, 4 - len(plastico)),
        "desenho": desenho + [""] * max(0, 4 - len(desenho)),
        # QUEM NAVEGA O PC, nas duas dicas das telas de botões.
        "quem-navega": rotulo_de_quem_navega(
            jogador_de(chefe) if chefe else None,
            identidade_de(chefe, ctx.mesa) if chefe else "",
            str(do_chefe.get("via") or "")),
        # AS DUAS VELOCIDADES, do daemon — não do perfil. O perfil guarda o
        # que ela SALVOU; o daemon diz o que está VALENDO agora, e é o
        # segundo que a tela mostra.
        "vel-cursor": rato.get("speed"),
        "vel-rolagem": rato.get("scroll_speed"),
        "rato-despachando": bool(rato.get("despachando")),
        "gestos": len(atalhos),
        "gestos-lista": {k: v for k, v in list(atalhos.items())[:12]},
    }
    # O "STATUS DO MODO" SÓ FALA QUANDO O DAEMON FALOU — 03/09/2026, e é a mesma
    # trava da lista "Função do teclado" logo abaixo. Sem o bloco
    # `mouse_emulation` a chave não é emitida, o `—` do desenho fica, e a tela
    # não afirma lado nenhum. Emitir `Desligado` porque ninguém respondeu
    # trocaria a mentira antiga ("Ligado" sempre) por outra.
    #
    # A PALAVRA SERVE AOS DOIS ELEMENTOS: o `.txt` a escreve como texto, e o
    # rótulo acende a classe `ligado` quando ela casa com o `data-hef-quando`.
    # É a mesma semântica dos quatro degraus da Vibração — um `data-campo`, cada
    # elemento decidindo por si.
    if isinstance(rato.get("enabled"), bool):
        mesa["rato-ligado"] = LIGADO if rato["enabled"] else DESLIGADO
    # AS TRÊS LINHAS DE ESTADO, e as três frases são do PRODUTO. Elas respondem
    # o que esta aba calava e a GTK responde: *por que o cursor não anda*, *o
    # teclado está ligado e calado agora?* e *há teclado na tela nesta máquina?*
    # Vazias quando não há o que dizer — o `:empty` do desenho as apaga.
    mesa["rato-estado"] = _o_mouse_virtual_em_uma_linha(rato)
    mesa["teclado-bloqueio"] = _o_teclado_em_uma_linha(tecla)
    mesa["teclado-osk"] = _o_teclado_na_tela_em_uma_linha(tecla)
    # AS TRÊS QUE A ONDA 2 ACRESCENTOU, e as três são "só quando há o que
    # dizer": a razão do portão de modo (que também é o que APAGA o interruptor,
    # pela folha desta aba), o custo de manter o teclado desligado, e a tira sob
    # a tabela de botões. Emitidas em TODO tique, como as três de cima — chave
    # ausente deixaria a frase velha na tela para sempre.
    mesa["modo-portao"] = _a_razao_do_portao(st)
    mesa["teclado-custo"] = _o_custo_de_desligar_o_teclado(tecla)
    mesa["aviso-da-tabela"] = _aviso_da_tabela(p)
    # A RESSALVA DA D3 — 05/09/2026. Emitida em TODO tique, como as outras: a
    # chave ausente deixaria a frase na tela depois de o segundo controle sair,
    # e a linha passaria a ressalvar uma escolha que não existe mais.
    mesa[ENDERECO_DA_RESSALVA] = _a_ressalva_dos_globais(ctx)
    # AS VINTE E UMA LINHAS DE *O QUE CADA BOTÃO FAZ*, do perfil dela — e elas
    # não existiam aqui até 02/09/2026. O botão "Guardar" LIA essas linhas
    # (`data-hef-forma`) e nada as ESCREVIA, então a tela mostrava para sempre o
    # que o desenho escolheu. Ver `guardar_definicoes` para o que isso custava.
    #
    # E ELAS PARAM DE SER REPINTADAS ENQUANTO ELA ESTÁ MEXENDO — decisão dela,
    # 02/09/2026. Ver `_o_que_a_tabela_mostra`.
    mesa.update(_o_que_a_tabela_mostra(p))
    # A LISTA "Função do teclado" SÓ É REESCRITA QUANDO O DAEMON FALOU, e a
    # ausência da chave é o que impede a mentira: sem o bloco
    # `keyboard_emulation` (daemon mudo, ou config inacessível — o `state_full`
    # OMITE o bloco nesse caso) escrever "Desligada" afirmaria um estado que
    # ninguém mediu. Chave ausente = a pintura não toca no `<select>`.
    #
    # E ela ACOMPANHA a recusa: desde 02/09/2026 a frase de um `RuntimeError`
    # chega ao cartão dela na hora (`hefesto_vivo._recusou_dizendo`, pelo
    # `idle_add`). Escolher "Só dentro do jogo", que não tem dono, mostra o
    # motivo E deixa a lista voltar sozinha para o que está valendo no tique
    # seguinte. A frase do `ValueError` continua sem chegar, por contrato — e é
    # por isso que uma opção que a tela OFERECE nunca pode cair nele.
    #
    # E A PALAVRA É A QUE A PÁGINA CARREGADA SABE RECEBER — 02/09/2026,
    # corretivo. Emitir a palavra da BANCADA numa lista que só tem as antigas é
    # escrita descartada em silêncio, e o que fica na tela é a `<option
    # selected>` do desenho: com o teclado DESLIGADO a linha afirmava `Ligada —
    # atalhos e teclado na tela`. Ver `PALAVRAS_DO_TECLADO`.
    if "keyboard_emulation" in st:
        mesa["teclado-estado"] = _o_teclado_em_palavras(bool(tecla.get("enabled")))
    return {
        "colunas": cards,
        "mesa": mesa,
        # A FOLHA VIVA DO PLÁSTICO. Ela vai por `blocos` e não por campo porque
        # o casco do desenho é `var(--z-…)` dentro do SVG, e o piloto não tem
        # alvo que escreva variável CSS — ver `folha_do_plastico`.
        #
        # SEMPRE PRESENTE, mesmo vazia: `normalizar` só deixa o `blocos`
        # atravessar quando o dicionário não é vazio, e uma folha que somisse
        # deixaria na tela a última cor escrita. Com a mesa vazia o valor é `""`
        # e o `innerHTML` do `<style>` é apagado.
        "blocos": {"#plastico-vivo": folha_do_plastico(ctx.mesa)},
        "sem_dono": {},
        # O NÚMERO SAI DOS DICIONÁRIOS, e não de uma constante escrita à mão:
        # foi uma soma digitada (`len(cards) * 2 + 9`) que deixou a curva da aba
        # Gatilhos fora da cobertura, e aqui ela erraria no tique em que a lista
        # do teclado entra — o valor é condicional.
        #
        # E ELE DESCONTA O QUE NÃO TEM ONDE CAIR — 02/09/2026. Contar chave
        # EMITIDA como "pintado" é a mesma confusão entre a PALAVRA e o ATO que
        # produziu o "77%" falso desta casa: medido no mesmo dia, esta aba
        # emitia 14 chaves e a página tinha endereço para 6. O instrumento dizia
        # 14. Um contador que mente é pior que um campo parado.
        "cobertura": {"pintados": (sum(len(v) for v in cards.values())
                                   + len(set(mesa) - set(SEM_ENDERECO))),
                      "sem_dono": len(SEM_DONO)},
    }


# ---------------------------------------------------------------------------
# OS GESTOS — ver o exemplo comentado em `a04_iluminacao.py`
#
# ESTA ABA NÃO ENDEREÇA POR CONTROLE, e é decisão do desenho: o `title` da fita
# diz, com todas as letras, *"Não se aplica: mouse, teclado e gestos saem de um
# controle só"* — o primário. Nenhum gesto daqui pede `uniq`, e nenhum dos três
# métodos do daemon aceita um: `mouse.emulation.set`, `mouse.emulation.restore`
# e `keyboard.emulation.set` valem para a MÁQUINA.
#
# DE ONDE VEM O NÚMERO DE QUEM DEPENDE DO ESTADO: do `ctx`, que é o do ÚLTIMO
# TIQUE (100 ms, `hefesto_vivo.TIQUE_MS`). Ler o daemon a cada clique custaria um
# `daemon.state_full` por clique (57 ms medidos, e HARM-15 já registra que ele
# passa dos 0,25 s sob carga), e ainda assim a tela só repinta no tique.
#
# O SEGUNDO CLIQUE DENTRO DO MESMO TIQUE PARAVA DE ANDAR — CURADO em 03/09/2026.
# Dois cliques dentro do mesmo tique liam o mesmo `atual` e mandavam o mesmo alvo:
# o segundo não movia nada. A cura é `_partir_de` — a memória do último alvo
# pedido, largada assim que o daemon fala.
#
# QUEM AINDA DEPENDE DELA É O INTERRUPTOR, e só ele: as duas velocidades
# deixaram de somar passos em 05/09/2026, quando os `-`/`+` viraram barra
# (decisão dela). Uma barra manda o número INTEIRO — não tem de onde partir, e
# por isso não passa por aqui. O "Status do Modo" tem UM gesto, e o segundo
# clique dele é *desfaça*: sem a memória ele volta a ser engolido.
# ---------------------------------------------------------------------------
from hefesto_dualsense4unix.app.actions.mode_transition import (  # noqa: E402
    MODE_DESKTOP,
    mode_of_state,
)
from hefesto_dualsense4unix.integrations.uinput_mouse import (  # noqa: E402
    MOUSE_SPEED_MAX,
    MOUSE_SPEED_MIN,
    SCROLL_SPEED_MAX,
    SCROLL_SPEED_MIN,
)

from . import gesto  # noqa: E402

#: A ORIGEM É `manual` PORQUE É A MÃO DELA. `origem_do_pedido`
#: (`daemon/ipc_handlers.py:132`) lê a AUSÊNCIA como `"profile"`, e a assimetria é
#: de propósito — foi um cliente que só reconciliava estado, promovido a gesto
#: humano, que devolveu o gamepad virtual com o grab pulado e pôs um "Jogador 3"
#: fantasma na tela dela (JOGADOR-3-FANTASMA-01). Aqui é clique, logo é manual.
MANUAL = "manual"


def _rato(ctx: Contexto) -> dict[str, Any]:
    """O bloco `mouse_emulation` do último tique — o que está VALENDO agora.

    Ele é o do DAEMON, e não o do perfil: o perfil guarda o que ela salvou, e a
    tela mexe no que está ligado. É a mesma escolha que a função de pintura
    acima já fazia.
    """
    return ctx.state.get("mouse_emulation") or {}


# ---------------------------------------------------------------------------
# O QUE ESTA ABA GUARDA NO PERFIL, E POR QUE NO CLIQUE
#
# DECISÃO D2, 05/09/2026 (`2026-09-05-AS-TRES-DECISOES-DO-PERFIL`):
# **persistência no clique em toda parte, com o rodapé como rede de segurança.**
# O requisito dela é durabilidade — *"salvar se lembra disso quando eu for jogar
# o jogo e no dia seguinte e por diante"* —, não o gesto de salvar; e só a
# gravação no clique sobrevive a fechar a janela sem clicar em nada.
#
# O QUE JÁ FUNCIONAVA, MEDIDO ANTES DE ESCREVER UMA LINHA (05/09/2026, em `HOME`
# de mentira, ciclo inteiro: disco → ela mexe na aba → Salvar → relê o disco):
#
#     mouse.speed         11 → 11   SOBREVIVE   (rodapé, commit ed91c687)
#     mouse.scroll_speed   4 →  4   SOBREVIVE
#     mouse.enabled     True → True SOBREVIVE
#     teclado_emulado  False → True PERDIDO
#
# **O `mouse` já ia ao perfil pelo Salvar e não se duplica aqui** — o que este
# bloco acrescenta às três linhas do rato é o caminho do CLIQUE, que é o que
# faltava. O `teclado_emulado` não tinha caminho NENHUM: `to_profile` o emite
# por passthrough do que veio do disco (`draft_config.py:856`), então desligar o
# teclado e clicar Salvar devolvia o valor VELHO.
#
# E O PRODUTO JÁ DIZIA DE QUEM ERA O TRABALHO. O comentário do passthrough, em
# `draft_config.py`, está escrito assim: *"POR QUE PASSTHROUGH E NÃO CAMPO
# EDITÁVEL: quem os escreve hoje é a aba 06, direto no disco, no clique."* Era
# uma afirmação sobre um escritor que não existia; agora existe.
#
# DISCO, E SÓ — NUNCA `perfil.gravar_e_reaplicar`. O preço está medido em 03/09
# no `a03_gatilhos._gravar_so_o_gatilho` e repetido em 04/09 no trilho de brilho
# da aba 04: aquele caminho termina em `profile_switch`, que manda o daemon
# reaplicar o perfil INTEIRO — e a barra de luz que ela DESLIGOU acende de novo,
# sem nada na tela dizer que ia acontecer. Aqui seria pior ainda: o gesto é uma
# BARRA, e arrastá-la desfaria, a cada passo, o que ela mexeu nas outras abas e
# ainda não salvou. O aparelho já recebeu a mudança pelo `mouse.emulation.set`
# logo acima; o que falta é durabilidade, e durabilidade é disco.
# ---------------------------------------------------------------------------

#: OS CAMPOS QUE ESTES GESTOS GRAVAM, e o nome de cada um dentro de
#: `ProfileMouseConfig`. O prefixo existe para o helper distinguir, numa
#: assinatura só, o que é do rato do que é do teclado.
_DO_RATO: dict[str, str] = {
    "mouse_enabled": "enabled",
    "mouse_speed": "speed",
    "mouse_scroll": "scroll_speed",
}


def _secao_do_mouse(prof: Any, ctx: Contexto, campos: dict[str, Any]) -> Any:
    """A seção `mouse` do perfil com o que este clique mudou — ou `None`.

    `None` quer dizer **não há o que gravar**, e ele tem dois donos: o perfil
    que já diz exatamente isto (gravar de novo seria escrever o mesmo arquivo a
    cada passagem do arraste), e o daemon que ainda não falou.

    A SEÇÃO NASCE COM O QUE ESTÁ VALENDO quando o perfil não a tinha, e é a
    mesma escolha do rodapé (`rodape._o_que_e_da_mesa_inteira`): `enabled` é
    campo OBRIGATÓRIO do `ProfileMouseConfig`, então uma seção que nasce por um
    arraste de velocidade precisa dizer alguma coisa sobre o liga/desliga — e a
    única coisa verdadeira que existe é o estado vivo. Inventar `False` faria o
    perfil, na próxima ativação, DESLIGAR uma emulação que estava ligada.

    SEM O BLOCO DO DAEMON A SEÇÃO NÃO NASCE. Um perfil sem `mouse` mais um
    daemon mudo não têm de onde tirar o `enabled`, e um valor chutado aqui vale
    para todo jogo que casar com este perfil, para sempre.
    """
    from hefesto_dualsense4unix.profiles.schema import ProfileMouseConfig

    atual = getattr(prof, "mouse", None)
    if atual is not None:
        base = {"enabled": atual.enabled, "speed": atual.speed,
                "scroll_speed": atual.scroll_speed}
    else:
        vivo = _rato(ctx)
        if vivo.get("speed") is None:
            return None
        base = {"enabled": bool(vivo.get("enabled")),
                "speed": int(vivo["speed"]),
                "scroll_speed": int(vivo.get("scroll_speed") or SCROLL_SPEED_MIN)}
    novo = {**base, **campos}
    if atual is not None and novo == base:
        return None
    return ProfileMouseConfig(**novo)


def _guardar_no_perfil(ctx: Contexto, **campos: Any) -> str:
    """Grava no perfil ATIVO o que ESTE clique mudou. Disco, e nada mais.

    Aceita `teclado_emulado=` e os três do rato (`mouse_enabled`, `mouse_speed`,
    `mouse_scroll`) — ver `_DO_RATO`.

    :return: `""` quando gravou, e também quando não havia o que gravar (o
        disco já dizia isso). A frase do que NÃO deu quando não há perfil ativo
        ou quando o arquivo não abre.

    POR QUE UMA FRASE E NÃO UM `RuntimeError`: o aparelho JÁ mudou quando esta
    função é chamada — a chamada ao daemon vem antes, e ela deu certo. Levantar
    aqui pintaria o cartão laranja da RECUSA sobre um gesto que fez metade do
    que prometeu, e ela leria *"não deu"* sobre um cursor que acabou de ficar
    mais rápido. Quem chama devolve a frase pelo canal de AVISO
    (`{"recado": …}`), que deposita no mesmo cartão com tom de sucesso.

    O ARRASTE CHEGA DUAS VEZES E GRAVA UMA. O ouvinte do piloto escuta `change`
    **e** `click`, e soltar o polegar de um `<input type=range>` dispara os dois
    com o MESMO valor. A segunda passagem encontra o disco já igual, `_secao_do_mouse`
    devolve `None` e nada é escrito — o guarda é a IGUALDADE, e não um relógio.
    É mais forte que o `_so_abriu_o_seletor` da aba 04, porque também cobre o
    caso de ela arrastar a barra e voltar ao valor de origem.
    """
    nome = str((ctx.state or {}).get("active_profile") or "").strip()
    if not nome:
        return ("mudei agora, e não guardei para amanhã: não há perfil ativo. "
                "Escolha um na aba Perfis e o Hefesto passa a lembrar disto.")
    loader = perfil._com_o_src()
    try:
        prof = loader.load_profile(nome)
    except Exception:
        return (f"mudei agora, e não guardei para amanhã: não consegui abrir o "
                f"perfil “{nome}” para gravar.")

    mudanca: dict[str, Any] = {}
    if "teclado_emulado" in campos:
        quer = bool(campos["teclado_emulado"])
        if getattr(prof, "teclado_emulado", None) is not quer:
            mudanca["teclado_emulado"] = quer
    do_rato = {_DO_RATO[k]: v for k, v in campos.items() if k in _DO_RATO}
    if do_rato:
        secao = _secao_do_mouse(prof, ctx, do_rato)
        if secao is not None:
            mudanca["mouse"] = secao
    if not mudanca:
        return ""
    loader.save_profile(prof.model_copy(update=mudanca), origem="interface-nova")
    return ""


def _numero_da_barra(o: dict[str, Any], oque: str) -> int:
    """O inteiro que a barra mandou, ou uma frase que chega ao cartão dela.

    O `data-hef-alvo="valor"` do `<input type=range>` faz o ouvinte do piloto
    mandar `valor: alvo.value` (`hefesto_vivo.py`, o ouvinte de `change`). Um
    `<div>` não teria `value` e o gesto chegaria com a chave vazia — foi o
    defeito que a aba Vibração nomeou em 03/09/2026 antes de o trilho dela
    virar `<input>`, e a frase abaixo é para ele.

    `RuntimeError` E NÃO `ValueError` porque é ELA quem tem de ler: o contrato
    do piloto leva a frase de um `RuntimeError` ao cartão e deixa o `ValueError`
    no `stderr` de quem lançou a janela (`hefesto_vivo._recusou_dizendo`).
    """
    bruto = str(o.get("valor") or "").strip()
    if not bruto:
        raise RuntimeError(
            f"a barra não mandou número nenhum, e {oque} ficou como estava. "
            "Arraste o cursor dela em vez de clicar no rótulo ao lado.")
    try:
        return round(float(bruto))
    except ValueError as erro:
        raise RuntimeError(
            f"a barra mandou {bruto!r}, que não é um número — {oque} ficou "
            "como estava") from erro


def _recusa_do_mouse(resposta: Any) -> str:
    """A frase da recusa, TRADUZIDA — ou `""` quando o daemon aceitou.

    A tradução é do produto: `app/actions/mouse_actions.frase_da_recusa_do_mouse`
    lê o `bloqueio` do corpo e cobre cinco motivos, com fallback honesto para
    motivo novo e para recusa sem motivo. Ela existe desde 25/08 e nunca tinha
    sido chamada por esta aba.

    FATO SUBSTITUÍDO — 03/09/2026. Aqui estava escrito que *"a ponte não expõe o
    `_call_checked_detalhado`, que é o único que entrega o corpo"*, e por isso
    um `{"status": "failed", "bloqueio": "sem_device"}` voltava como sucesso e a
    tela dela ficava sem uma palavra. A ponte entrega o corpo desde 01/09:
    `ponte.resultado` (`interface/pacotes/ponte.py:193`) devolve o `result` do
    daemon e levanta quando ninguém responde. Era um caminho que já existia e
    esta aba não chamava.

    `status` AUSENTE conta como aceito: o `set_mouse_speed` responde
    `{"status": "ok", "enabled": …}` e nenhum outro campo, e tratar a ausência
    como recusa faria toda troca de velocidade acusar um "não" que não houve.
    """
    from hefesto_dualsense4unix.app.actions.mouse_actions import (
        frase_da_recusa_do_mouse,
    )

    if not isinstance(resposta, dict) or resposta.get("status") != "failed":
        return ""
    return frase_da_recusa_do_mouse(resposta)


def _recusa_do_teclado(resposta: Any) -> str:
    """O motivo de o teclado não ter ligado, do bloco que o próprio daemon devolve.

    `keyboard.emulation.set` responde com o bloco `keyboard_emulation` inteiro —
    *"para a janela não precisar de uma segunda chamada só para saber se o
    device subiu"* (`daemon/ipc_handlers.py:5279`). Quem o traduz é
    `emulation_actions.descrever_teclado_emulado`, o mesmo dono da linha de
    estado desta aba.

    Sem bloco e sem frase, o que sobra de verdadeiro é que ele recusou — e é o
    que se diz, em vez de inventar um motivo. A frase de "não sei" da GTK
    (`TECLADO_SEM_ESTADO`, *"o Hefesto pode estar desligado"*) NÃO serve aqui e
    é por isso que o bloco é conferido antes: o Hefesto respondeu, ele é que
    disse não.
    """
    from hefesto_dualsense4unix.app.actions.emulation_actions import (
        descrever_teclado_emulado,
    )

    bloco = resposta.get("keyboard_emulation") if isinstance(resposta, dict) else None
    if isinstance(bloco, dict) and isinstance(bloco.get("enabled"), bool):
        _posicao, frase = descrever_teclado_emulado(bloco)
        if frase:
            return frase
    return "o Hefesto recusou e não disse por quê"


#: O QUE O HEFESTO JÁ CONFIRMOU E O TIQUE AINDA NÃO TROUXE, por campo:
#: `{"speed": (o número que o tique mostrava, o que ele confirmou, o sentido do
#: clique, o relógio da confirmação)}`.
#:
#: Ele existe por UM defeito medido, e some sozinho: o `ctx` é o estado do
#: último tique (100 ms), então dois cliques dentro do mesmo tique partiam do
#: MESMO número e pediam o MESMO alvo — o segundo clique não andava. Ver
#: `_partir_de`.
#:
#: O INTERRUPTOR VIAJA COMO 0/1, e é de propósito: "Status do Modo" tinha o
#: MESMO defeito e não tinha a cura (medido em 03/09/2026 — dois cliques no
#: mesmo tique mandavam `enabled=True` duas vezes, e o segundo era engolido).
#: Dois armazéns seriam dois relógios, duas expirações e duas regras de largar;
#: um bool É um número de dois valores, e uma trava só é uma trava só.
_PEDIDO: dict[str, tuple[int, int, int, float]] = {}

#: QUANTO TEMPO A MEMÓRIA DE UM CLIQUE VALE. Ela existe para atravessar a VIAGEM
#: INTEIRA do pedido — clicar, o daemon aplicar, e o tique seguinte LER de volta
#: o que mudou. O tique de pintura é só a última perna dela: 100 ms
#: (`hefesto_vivo.TIQUE_MS`). Um segundo é folga de sobra para um daemon lento
#: sem virar uma segunda verdade sobre o valor.
#:
#: SEM O RELÓGIO A MEMÓRIA ATRAVESSAVA UMA VOLTA INTEIRA, e o docstring de
#: `_partir_de` prometia o contrário (*"não há caminho em que ela sobreviva a
#: uma discordância"*). Havia um: ela clica `+` aqui (6 → 7), volta o número
#: para 6 pela janela GTK, e o `+` seguinte partia de 7 e pedia 8 — porque o
#: daemon dizia 6 de novo e o sentido era o mesmo. Concordar por acaso não é
#: concordar.
#:
#: NÃO SE IMPORTA `TIQUE_MS` DAQUI, pela mesma razão de `PAUSA_DE_OUTRA_ABA`:
#: `hefesto_vivo` puxa GTK no topo e os pacotes são puros de propósito. O número
#: está escrito com a conta ao lado, que é o que permite conferir a divergência
#: se o tique mudar.
MEMORIA_DE_UM_CLIQUE = 2.0


def _partir_de(chave: str, atual: int, sentido: int) -> int:
    """De onde o clique parte: o daemon, ou o último valor que ele CONFIRMOU.

    TRÊS CONDIÇÕES, e as três desligam a memória sozinhas:

    1. **o daemon ainda diz o mesmo número.** Se ele já publica outro — porque
       aplicou, porque aparou, ou porque ela mexeu pela janela GTK —, a memória
       é largada e a partida volta a ser ele;
    2. **o clique vai para o mesmo lado.** Dois `+` seguidos somam de verdade;
       um `+` seguido de um `-` parte do DAEMON, não do alvo pendente. A razão é
       que os dois gestos querem coisas diferentes: repetir é *ande mais*, e
       inverter dentro de meio segundo é ambíguo — a leitura conservadora é a de
       sempre, e é a que o `PROVAS` desta aba já cobrava. O interruptor manda
       `sentido=0` e cai sempre neste ramo: ele tem UM gesto, e o segundo
       clique é *desfaça*, nunca *ande mais*;
    3. **o relógio ainda está na janela do tique** — ver `MEMORIA_DE_UM_CLIQUE`.

    ELA SÓ FICA COM O QUE O HEFESTO NÃO RECUSOU — ver `_reservar`. Guardar o
    alvo e deixá-lo lá era o defeito medido em 03/09/2026: um clique RECUSADO
    (`sem_device`) deixava o alvo na memória, e o clique seguinte partia de um
    número que nunca existiu — pedia 8 tendo o daemon em 6, pulando o 7.
    """
    pendente = _PEDIDO.get(chave)
    if pendente is None:
        return atual
    visto, confirmado, sentido_antes, quando = pendente
    if visto != atual or sentido_antes != sentido:
        return atual
    if time.monotonic() - quando > MEMORIA_DE_UM_CLIQUE:
        del _PEDIDO[chave]
        return atual
    return confirmado


def _reservar(chave: str, atual: int, valor: int,
              sentido: int) -> tuple[int, int, int, float] | None:
    """Anota o alvo ANTES de mandar, e devolve o que estava lá para o desfazer.

    A RESERVA VEM ANTES DA CHAMADA, e isto é medido: os gestos rodam em THREAD
    (`hefesto_vivo.trabalhar`, `:1384` — *"um gesto síncrono congelaria a janela
    inteira por nove segundos e meio"*), então dois cliques rápidos são duas
    threads. Anotar só DEPOIS da resposta deixaria a segunda ler a memória vazia
    e repetir o pedido da primeira — o defeito que esta memória cura voltaria
    dentro do tempo de ida e volta do IPC, que é justamente a janela em que ela
    clica duas vezes.

    E ELA É DESFEITA NA FALHA, por `_largar_a_reserva`: reservar não é
    confirmar. Sem o desfazer, a reserva seria o mesmo defeito com outro nome.
    """
    antes = _PEDIDO.get(chave)
    _PEDIDO[chave] = (atual, valor, sentido, time.monotonic())
    return antes


def _largar_a_reserva(chave: str,
                      antes: tuple[int, int, int, float] | None) -> None:
    """O Hefesto recusou ou ficou mudo: a reserva volta ao que era.

    VOLTA AO QUE ERA, e não some: um `+` aceito seguido de um `+` recusado tem
    de deixar o primeiro alvo de pé, senão a recusa apagaria um pedido que
    aconteceu — e o clique seguinte pediria de novo o número que já está lá.
    """
    if antes is None:
        _PEDIDO.pop(chave, None)
    else:
        _PEDIDO[chave] = antes


def _velocidade(p: Any, o: dict[str, Any], campo: str,
                minimo: int, maximo: int, oque: str) -> int:
    """O corpo comum das duas barras de velocidade. `mouse.emulation.set`.

    SEM `enabled` DE PROPÓSITO, e é a rota que o produto criou para isto: o
    handler manda o pedido sem `enabled` para `set_mouse_speed`
    (`daemon/ipc_handlers.py:4970`), que atualiza a config e o device vivo **sem
    start/stop e sem gravar o flag**. É o que impede um ajuste de velocidade de
    RELIGAR a emulação e matar o gamepad virtual — a regressão que o
    BUG-MOUSE-GUI-SYNC-01 (A4) fechou. O `_send_mouse_param_async` da GUI
    estável (`app/actions/mouse_actions.py:559`) manda exatamente este payload.

    ELE NÃO LÊ O `ctx`, E É A DIFERENÇA QUE A BARRA TROUXE. Os `-`/`+` liam o
    estado do último tique porque um passo precisa saber de ONDE parte — e daí
    vinham `_partir_de`, a memória `_PEDIDO` e as três condições que a
    desligam. Uma barra manda o número inteiro: a partida é o polegar dela, e
    não há clique engolido a curar. A memória continua de pé, e continua com um
    cliente — o interruptor "Status do Modo", que tem UM gesto e por isso
    depende dela para o segundo clique ser *desfaça*.

    A FAIXA NÃO É DIGITADA AQUI: quem chama passa as constantes
    `MOUSE_SPEED_MIN`/`MOUSE_SPEED_MAX`
    (`integrations/uinput_mouse.py:78-79`), o mesmo módulo de onde
    `set_speed` (`:279`) tira a sua. A barra já nasce com esses `min`/`max`
    (`aba06.trilho`), então aparar aqui é a rede para o dia em que alguém
    publicar a página sem regerar o desenho — não é a segunda verdade que esta
    casa persegue. O daemon continua aparando por último.

    O ARRASTE CHEGA DUAS VEZES, e é inócuo de propósito — a mesma medição de
    `a05_vibracao.intensidade`: o ouvinte do piloto escuta `change` **e**
    `click`, e soltar o polegar de um `<input type=range>` dispara os dois com o
    MESMO valor. `set_mouse_speed` é idempotente — grava o mesmo número e
    reconfigura o mesmo device —, então a segunda passagem não muda nada.
    Filtrar por evento aqui seria escrever, neste arquivo, uma regra sobre o
    ouvinte que mora em outro.

    :return: o número que FOI ao daemon, já aparado. Quem chama o leva ao
        perfil (D2) — e o valor tem de ser este, nunca o do `ctx`: o `ctx` é o
        estado do tique ANTERIOR, e gravar dali guardaria a velocidade velha no
        disco enquanto a nova roda no aparelho.
    """
    alvo = max(minimo, min(maximo, _numero_da_barra(o, oque)))
    _mandar(p, origin=MANUAL, **{campo: alvo})
    return alvo


def _mandar(p: Any, **params: Any) -> None:
    """`mouse.emulation.set`, e diz POR QUE quando o daemon recusa.

    `p.chamar` devolve `bool` e joga fora o corpo — é ele que trazia a recusa de
    volta como sucesso. `p.resultado` traz o corpo e levanta quando ninguém
    responde, que são exatamente os dois desfechos que esta função precisa
    separar: *o Hefesto não falou* e *o Hefesto disse não, por isto*.
    """
    try:
        resposta = p.resultado("mouse.emulation.set", **params)
    except RuntimeError as erro:
        raise RuntimeError(
            "o Hefesto não respondeu — a velocidade não mudou") from erro
    recusa = _recusa_do_mouse(resposta)
    if recusa:
        raise RuntimeError(recusa)


@gesto("06-navegacao.html", "modo")
def modo(ctx: Contexto, o: dict[str, Any], p: Any) -> dict[str, Any] | None:
    """"Status do Modo": o interruptor que liga mouse E teclado.

    POR QUE OS DOIS, e não só o mouse: este interruptor é o que ela pediu em
    27/08 no lugar de dois botões — *"Suspender Mouse e Teclado, Sair do Modo
    Jogo, deixam de existir devido ao botão status na parte superior"* —, e a
    dica dele diz o alcance: *"nada desta aba chega ao PC"*. Teclado é desta
    aba. São duas chamadas porque o daemon tem dois interruptores separados
    (`mouse.emulation.set` e `keyboard.emulation.set`), e o segundo nasceu
    justamente porque desligar o mouse deixava o teclado emitindo Alt+Tab dentro
    da partida (`daemon/ipc_handlers.py:5032`).

    O MOUSE VAI PRIMEIRO de propósito: é ele que tem exclusão mútua com o
    gamepad virtual (`daemon/lifecycle.py:1359` — ligar o mouse PARA o vpad). Se
    a primeira falhar, a segunda não chega a rodar e o teclado não fica ligado
    sozinho num modo que não é dele.

    O LADO PARA ONDE IR SAI DO DAEMON, nunca da caixinha: o piloto não sabe
    escrever `checked` (o `escrever()` dele cobre texto, largura, fundo e
    `value`), então o desenho nasce `checked` e o daemon dela nasce
    `enabled=false` — ler a tela inverteria o gesto no primeiro clique.

    O PORTÃO DO MODO É DO PRODUTO, e está copiado dele: `_sync_mouse_mode_gate`
    (`app/actions/mouse_actions.py:299`) faz `blocked = mode != MODE_DESKTOP` e
    desliga o interruptor nos DOIS sentidos, inclusive com o modo desconhecido.
    A razão está escrita lá e é o que este gesto herda: *"Ligar o switch durante
    'Jogar pelo Hefesto' derrubava o vpad e os jogadores do co-op SEM AVISO (a
    exclusão mútua do daemon é silenciosa)"*.

    A FRASE É OUTRA, e tem de ser: a do produto (`MODE_GATE_HINT`) manda ir à
    **aba Início**, que não existe no desenho das dez abas — o modo mudou para a
    aba **Jogar**. Reusá-la mandaria ela a uma aba que não está lá. Reusar o
    módulo também não dá: `mouse_actions.py` importa GTK no topo, e os pacotes
    são puros de propósito.

    OS DOIS LADOS VÃO AO PERFIL JUNTOS — 05/09/2026, decisão D2. Este
    interruptor mexe em `mouse.enabled` **e** em `teclado_emulado`, e gravar só
    o primeiro deixaria o perfil dizendo *mouse desligado, teclado ligado* — um
    estado que este botão não sabe produzir e que a próxima ativação imporia.
    A gravação vem DEPOIS das duas chamadas: se o teclado recusar, o gesto já
    levantou, e o disco não guarda um meio-passo.
    """
    if not ctx.state:
        raise RuntimeError(
            "não consegui falar com o Hefesto agora, então não sei se ligar o "
            "mouse derrubaria um jogo em andamento. Tente de novo em instantes.")
    modo_agora = mode_of_state(ctx.state)
    if modo_agora != MODE_DESKTOP:
        # A MESMA FRASE QUE A TIRA JÁ MOSTRA — 04/09/2026. Desde que o portão
        # ganhou linha permanente (`_a_razao_do_portao`), a recusa e o aviso
        # passaram a ser o mesmo texto: duas grafias do mesmo fato divergiriam
        # na primeira correção, e quem clicasse leria uma coisa depois de ter
        # lido outra ao lado do interruptor.
        raise RuntimeError(RAZAO_DO_PORTAO)

    # O SEGUNDO CLIQUE DENTRO DO MESMO TIQUE DESFAZ O PRIMEIRO — 03/09/2026, e é
    # a cura que o `+`/`-` já tinha e este interruptor não. O `ctx` é o estado de
    # um tique atrás, então dois cliques seguidos liam o MESMO `enabled` e mandavam
    # `enabled=True` duas vezes: o segundo era engolido, e a tela — que desde
    # hoje só acende pelo daemon — ficava dizendo "Ligado" sem ela ter querido.
    # Ver `_partir_de`, com `sentido=0`: o interruptor tem um gesto só.
    ligado = bool(_rato(ctx).get("enabled"))
    novo = not bool(_partir_de("modo", int(ligado), 0))
    # A RESERVA COBRE SÓ O MOUSE, e é onde ela tem de estar: a memória espelha
    # `mouse_emulation.enabled`, que é o que `_rato` lê no clique seguinte. Se o
    # TECLADO falhar depois, o mouse já mudou — largar a reserva ali faria o
    # próximo clique repetir o pedido que o mouse já atendeu.
    reserva = _reservar("modo", int(ligado), int(novo), 0)
    try:
        try:
            resposta = p.resultado("mouse.emulation.set", enabled=novo,
                                   origin=MANUAL)
        except RuntimeError as erro:
            raise RuntimeError(
                "o Hefesto não respondeu — o mouse ficou como estava") from erro
        # O MOTIVO DA RECUSA CHEGA À TELA — 03/09/2026. Este `if` não existia: o
        # `chamar` devolvia `True` para um `{"status": "failed", "bloqueio":
        # "sem_device"}` e o gesto seguia adiante, mandando ligar o teclado como
        # se o mouse tivesse ligado. Agora ele PARA e diz o motivo, com a tabela
        # do produto — e o interruptor da tela não mente, porque desde hoje é o
        # daemon quem o acende (ver `pacote()`).
        recusa = _recusa_do_mouse(resposta)
        if recusa:
            raise RuntimeError(recusa)
    except Exception:
        _largar_a_reserva("modo", reserva)
        raise
    try:
        resposta = p.resultado("keyboard.emulation.set", enabled=novo)
    except RuntimeError as erro:
        raise RuntimeError(
            "o mouse mudou e o teclado não — o Hefesto não respondeu") from erro
    if isinstance(resposta, dict) and resposta.get("status") == "failed":
        raise RuntimeError(f"o mouse mudou e o teclado não: {_recusa_do_teclado(resposta)}")
    recado = _guardar_no_perfil(ctx, mouse_enabled=novo, teclado_emulado=novo)
    return {"recado": recado} if recado else None


#: O QUE CADA OPÇÃO DA LISTA MANDA FAZER. A chave é a palavra que DISTINGUE uma
#: das outras duas, e não mais a primeira: com as três palavras dela, duas
#: começam por "só" — casar pela primeira faria "Só dentro do jogo" e "Só fora
#: do jogo" virarem a mesma escolha, e viraria CALADO.
#:
#: A busca é por palavra INTEIRA no texto da opção, em minúsculas, o que deixa o
#: gesto sobreviver a uma reescrita do resto da frase. Casar a frase toda
#: quebraria no dia em que alguém melhorasse o texto da tela — e um `<select>`
#: cujo valor não casa com nada simplesmente não faz nada.
#:
#: `None` é a opção que a tela oferece e o produto NÃO tem. Ela não vira `False`
#: nem `True` por conveniência: ver `teclado()`.
_ESCOLHA_DELA: dict[str, bool | None] = {
    "fora": True, "desativado": False, "dentro": None}

#: OS SINÔNIMOS DA TRAVESSIA SAÍRAM — 03/09/2026, e foi a régua que mandou.
#:
#: Enquanto a bancada tinha as três palavras dela e a página publicada tinha as
#: antigas, este mapa acrescentava `ligada`/`desligada` ao `_ESCOLHA_DELA` para
#: as opções da tela DELA continuarem clicáveis. A 06 foi publicada, o
#: `test_os_sinonimos_da_travessia_tem_prazo` ficou vermelho nomeando o que
#: apagar, e é isto: `_ESCOLHA` volta a ser a decisão dela, sem tradução.
_ESCOLHA: dict[str, bool | None] = _ESCOLHA_DELA


@gesto("06-navegacao.html", "teclado")
def teclado(ctx: Contexto, o: dict[str, Any], p: Any) -> dict[str, Any] | None:
    """A lista "Função do teclado". `keyboard.emulation.set`.

    O VALOR VEM EM `valor`, E ISSO É O QUE MUDOU DESDE A PRIMEIRA LEVA: o
    ouvinte do piloto passou a escutar `change` além de `click` e a mandar o
    `value` do alvo (`hefesto_vivo.py:196` e `:230`). Antes só chegava `texto`,
    que num `<select>` é a lista INTEIRA de opções concatenada — foi por isso
    que esta lista ficou sem dono na primeira leva, e não por falta de método.

    O `rotulo` É O SEGUNDO CAMINHO, não um enfeite: as `<option>` desta lista
    não têm atributo `value` (`value` não está entre os que o portão do desenho
    ignora), então `select.value` **é** o texto — mas um `<option value=…>` que
    nasça amanhã mandaria a chave em `valor` e a frase em `rotulo`, e é o
    `rotulo` que continuaria casando com o desenho.

    DUAS DAS TRÊS OPÇÕES TÊM DONO, e a terceira RECUSA DIZENDO — que é a regra
    da casa, não uma falha desta ligação:

    * "Só fora do jogo" → `enabled=True`; "Desativado" → `enabled=False`. O
      handler (`daemon/ipc_handlers.py:5038`) só lê `enabled`, e ele é bool.
    * "Só dentro do jogo" **não existe do outro lado**, e nem poderia: ele é o
      INVERSO de tudo o que o produto faz hoje.

    FATO DERRUBADO — 02/09/2026, e ele estava escrito NESTE arquivo e no
    enunciado do trabalho: *"'Só fora do jogo' não existe do outro lado"* e
    *"'Só dentro do jogo' já existe, e é o `suppress_desktop_emulation`"*. **Os
    dois estão invertidos**, e a medição é de três leituras:

    1. `Profile.suppress_desktop_emulation` (`profiles/schema.py:1176`) diz, no
       próprio comentário: *"True = ativar o perfil suprime a emulação de
       mouse/teclado no desktop (jogos de GAMEPAD que leem o controle cru)"*.
       O perfil é ativado quando o jogo casa; logo a supressão vale **durante o
       jogo** — o teclado funciona FORA dele.
    2. `apply_profile_suppression` (`daemon/lifecycle.py:1951`) recebe esse
       campo a cada ativação de perfil e liga a supressão com `desired=True`.
    3. Sem perfil nenhum a dizer o contrário, o daemon **já** cala a emulação de
       desktop quando um jogo assume: `_jogo_no_controle_do_desktop`
       (`:2263`, a cura da queixa dela de 29/07 — *"aperto r1 e ele muda de app
       ao invés de funcionar no jogo"*) e o `gamepad_dispatched` do laço
       (`:4780`).

    Logo o teclado emulado ligado **é** "só fora do jogo", e a etiqueta velha
    ("Ligada — atalhos e teclado na tela") é que afirmava um alcance maior do
    que o produto tem. O que falta é o INVERSO: um teclado que só valha DENTRO
    do jogo. Ele exigiria um portão por perfil com o sinal trocado — campo novo
    no esquema, e ele **não existe**. Enquanto não existir, esta opção recusa
    dizendo, que é o contrário de um botão que aceita o clique e não faz nada.

    SEM PORTÃO DE MODO, ao contrário do gesto `modo` logo acima, e é medido: o
    portão de lá existe porque ligar o MOUSE derruba o gamepad virtual — o
    `set_mouse_emulation` (`daemon/lifecycle.py:1372`).

    Do outro lado, o teclado não mexe no gamepad virtual em momento nenhum.
    Quem o liga e desliga é o
    `set_keyboard_emulation` (`daemon/lifecycle.py:1505`): ele cria ou destrói o
    teclado virtual e nada mais.

    E COM O GAMEPAD DESPACHANDO, o teclado nem chega a ser consultado — a
    guarda está em `lifecycle.py:2240`, no `if not gamepad_dispatched`. Copiar o
    portão daqui bloquearia, dentro do jogo, o único interruptor que existe
    para calar o Alt+Tab do R1 — que é o defeito que este método nasceu para
    curar (queixa dela, 29/07).

    O QUE ESTE BOTÃO AINDA NÃO DIZ, e está no relato: desligar tira também o
    teclado na tela do L3/R3 e as três regiões do touchpad (o handler manda a
    interface repassar isso). O piloto não tem canal de aviso — um gesto só
    imprime no terminal —, então o recado não tem onde aparecer.

    ELE ENTENDE AS TRÊS PALAVRAS DELA, E VOLTOU A ENTENDER SÓ ELAS — 03/09/2026.
    Entre 02/09 e a publicação foram CINCO: as três da bancada mais os dois
    rótulos que a página publicada ainda oferecia, porque aceitar só as três
    transformou duas das três opções da tela dela em clique morto — e calado, por
    contrato. A 06 foi publicada, os dois rótulos velhos não existem mais em
    `<option>` nenhuma, e a régua da travessia mandou apagar os sinônimos.

    E DIZ POR QUE NÃO DEU, desde o mesmo dia: a chamada passou a ser
    `p.resultado`, que traz o corpo — o `p.chamar` devolvia `True` para um
    `{"status": "failed"}` e a lista voltava sozinha sem uma palavra.

    E ELE PASSOU A LEMBRAR — 05/09/2026, e este era o buraco INTEIRO desta aba.
    `keyboard.emulation.set` grava na flag GLOBAL da sessão
    (`utils/session.py:372`), nunca no perfil; e `DraftConfig.to_profile` emite
    `teclado_emulado` por PASSTHROUGH do que veio do disco. Medido no ciclo
    completo em `HOME` de mentira: com o perfil dizendo `True` e ela escolhendo
    a opção `TECLADO_DESATIVADO`, o Salvar do rodapé devolvia **`True`** — o
    valor velho, por cima da escolha dela, sem uma palavra. Ver
    `_guardar_no_perfil`.
    """
    escolhido = str(o.get("valor") or o.get("rotulo") or "").strip()
    palavras = {x.strip(".,;:—-").lower() for x in escolhido.split()}
    chaves = palavras & set(_ESCOLHA)
    if len(chaves) != 1:
        raise ValueError(
            f"teclado: não reconheci a opção escolhida ({escolhido!r}). As três "
            f"do desenho estão em `src/hefesto_dualsense4unix/interface/aba06.py:OPCOES_TECLADO`, "
            f"e cada uma tem de trazer exatamente uma destas palavras: "
            f"{', '.join(sorted(_ESCOLHA))}.")
    ligar = _ESCOLHA[chaves.pop()]
    if ligar is None:
        raise RuntimeError(
            f"“{TECLADO_SO_DENTRO}” ainda não tem dono, e é o INVERSO do que o "
            "Hefesto faz: ele cala o teclado emulado quando um jogo assume o "
            "controle, e o que sobra é justamente o “"
            f"{TECLADO_SO_FORA}”. Um teclado que valha SÓ dentro do jogo pede um "
            "campo novo no perfil — o portão com o sinal trocado —, e ele ainda "
            "não existe. A lista volta sozinha para o que está valendo.")
    try:
        resposta = p.resultado("keyboard.emulation.set", enabled=ligar)
    except RuntimeError as erro:
        raise RuntimeError(
            "o Hefesto não respondeu — o teclado ficou como estava") from erro
    # O MOTIVO CHEGA À TELA — 03/09/2026. O `chamar` devolvia `True` para um
    # `{"status": "failed"}` e a lista voltava sozinha no tique seguinte, sem
    # uma palavra: ela lia "não pegou" e não sabia por quê.
    if isinstance(resposta, dict) and resposta.get("status") == "failed":
        raise RuntimeError(
            f"o teclado ficou como estava: {_recusa_do_teclado(resposta)}")
    recado = _guardar_no_perfil(ctx, teclado_emulado=ligar)
    return {"recado": recado} if recado else None


@gesto("06-navegacao.html", "vel-cursor")
def vel_cursor(ctx: Contexto, o: dict[str, Any], p: Any) -> dict[str, Any] | None:
    """A barra da Velocidade de cursor, arrastada. `mouse_emulation.speed`.

    DECISÃO DELA, 05/09/2026: *"velocidade do cursor e da rolagem coloca um
    slicer pra cada"*. Até aqui a linha era um par de botões `-`/`+`, e os dois
    gestos que os atendiam (`vel-cursor-menos`/`-mais`) somavam ±1 ao número do
    ÚLTIMO TIQUE. Os dois saíram com os botões: uma barra manda o número
    INTEIRO, e não uma direção — não há de onde partir, e por isso não há passo
    engolido a curar.

    E A PARIDADE COM A JANELA GTK FECHOU NO MESMO MOVIMENTO: lá esta linha é um
    `Gtk.Scale` de `mouse_speed_adj` (`gui/main.glade:79`, 1..12, passo 1), que
    é a MESMA faixa que a barra oferece agora — porque as duas leem o dono
    (`integrations/uinput_mouse.py:78`). Ver `docs/data/paridade-gtk-html.csv`,
    linha "Velocidade do cursor".

    O ALCANCE É O DE UM NÚMERO SÓ, e a medição é de 01/09: `mouse_speed` move o
    analógico esquerdo **e** o cursor do touchpad — `emit_touchpad_move` escala
    por `TOUCHPAD_SENSITIVITY * (mouse_speed / DEFAULT_MOUSE_SPEED)`
    (`integrations/uinput_mouse.py:500`).

    E ELE PASSOU A DURAR ALÉM DA JANELA — 05/09/2026, decisão D2. Até aqui o
    número ia ao daemon e ao `session.json`, e o perfil só o recebia se ela
    clicasse "Salvar" no rodapé: fechar a janela depois de arrastar a barra
    perdia a escolha, calada. Ver `_guardar_no_perfil`.
    """
    alvo = _velocidade(p, o, "speed", MOUSE_SPEED_MIN, MOUSE_SPEED_MAX,
                       "a velocidade do cursor")
    recado = _guardar_no_perfil(ctx, mouse_speed=alvo)
    return {"recado": recado} if recado else None


@gesto("06-navegacao.html", "vel-rolagem")
def vel_rolagem(ctx: Contexto, o: dict[str, Any], p: Any) -> dict[str, Any] | None:
    """A barra da Velocidade da rolagem, arrastada. `scroll_speed`.

    Mesma rota speed-only do vizinho, e o mesmo motivo — ver :func:`_velocidade`.
    O que muda é o alcance: `scroll_speed` multiplica o passo do analógico
    DIREITO em `_emit_scroll` (`integrations/uinput_mouse.py:466`) e nada mais —
    o touchpad não rola.

    A FAIXA DELE É OUTRA, e o dono é o mesmo: `SCROLL_SPEED_MIN`/`MAX` (1..5,
    `uinput_mouse.py:79`), contra os 12 do cursor. O daemon apara com as mesmas
    constantes (`daemon/lifecycle.py:1404` e `:1452`), e o `GtkAdjustment` da
    janela estável publica os mesmos limites (`gui/main.glade:87`).

    FATO SUBSTITUÍDO — 03/09/2026. Esta frase estava truncada no meio e afirmava
    que a dica da tela dizia *"De 1 a 10"* nas duas linhas *"e nas duas está
    errada"*. Caducou: `aba06.D_VEL` e `aba06.D_ROL` LEEM a faixa do dono, e a
    página publicada diz "De 1 a 12" no cursor e "De 1 a 5" na rolagem.

    ELE TAMBÉM DURA ALÉM DA JANELA desde 05/09/2026 — mesma decisão D2 do
    vizinho, mesmo caminho (`_guardar_no_perfil`).
    """
    alvo = _velocidade(p, o, "scroll_speed", SCROLL_SPEED_MIN, SCROLL_SPEED_MAX,
                       "a velocidade da rolagem")
    recado = _guardar_no_perfil(ctx, mouse_scroll=alvo)
    return {"recado": recado} if recado else None


@gesto("06-navegacao.html", "linha-de-botao")
def linha_de_botao(ctx: Contexto, o: dict[str, Any], p: Any) -> dict[str, Any] | None:
    """Ela trocou UMA das 21 linhas de *o que cada botão faz*. NÃO grava nada.

    ELE EXISTE PARA A TELA PARAR DE DESFAZER A ESCOLHA DELA — decisão de
    02/09/2026: *"as 21 listas param de ser repintadas enquanto ela está
    mexendo, até guardar ou sair. Não vira gravação automática: ela quer
    escolher várias, conferir e aplicar de uma vez."*

    Por isso ele **não chama o daemon e não escreve em disco**. O ponto de
    gravação continua sendo o "Guardar" ao lado; o que este gesto faz é anotar
    a escolha em `_MEXENDO`, e é a anotação que faz a pintura do tique seguinte
    concordar com a tela em vez de reescrevê-la.

    SEM ELE A ESCOLHA NÃO CHEGAVA AQUI, e a medição é do mesmo dia: o ouvinte do
    piloto só olha um alvo que case com o `closest` de `manda_do_alvo`
    (`hefesto_vivo.py:367`), e os 21 `<select>` tinham só `data-campo`,
    `data-linha` e `data-hef-alvo`. O `change` morria no navegador:

        ANTES  (o que a pintura pôs) : Botão direito
        CLIQUE (a escolha dela)      : F11
        +1500 ms                     : Botão direito

    O `data-gesto` que o gerador passou a pôr (`aba06.LINHA_DE_BOTAO`) é o que
    abre este caminho.

    A RECUSA É DE CLIQUE INVÁLIDO (`ValueError`), e não do produto: um rótulo
    que o produto não conhece só chega aqui se o desenho andou sem o gerador —
    a lista da tela e a do produto saem do mesmo `core/acoes_de_botao`.

    O QUE ELE DEVOLVE é a própria linha, pelo endereço da pintura. Na tela isso
    é um no-op (o `<select>` já está nela), e é de propósito: um gesto que volta
    com `None` não toca o DOM (`hefesto_vivo._deu_certo`) e sai do relato como
    "aplicado" sem nada a mostrar. Devolvendo o endereço, o desfecho do gesto
    passa a ser verificável — e a linha volta ao lugar certo se a página tiver
    sido repintada entre o clique e a volta da thread.
    """
    botao = str(o.get("linha") or o.get("campo") or "").removeprefix(PREFIXO_DA_ACAO)
    if botao not in acoes.BOTOES:
        raise ValueError(
            f"linha-de-botao: o clique não disse qual botão (veio {botao!r}). O "
            "`data-linha` de cada `<select>` é o id do botão, e ele vem do "
            "gerador — sem ele não há o que anotar.")
    rotulo = str(o.get("valor") or o.get("rotulo") or "").strip()
    if acoes.token_do_rotulo(rotulo) is None:
        raise ValueError(
            f"{_nome_do_botao(botao)}: a opção {rotulo!r} não é do produto. A "
            "lista da tela e a do produto saem do mesmo lugar "
            "(`core/acoes_de_botao.ACOES`) — se divergiram, foi o desenho que "
            "andou sem o gerador.")
    campo = f"{PREFIXO_DA_ACAO}{botao}"
    do_perfil = _linhas_dos_botoes(perfil.ativo((ctx.state or {}).get("active_profile")))
    if do_perfil.get(campo) == rotulo:
        # ELA VOLTOU AO QUE O PERFIL JÁ GUARDA. Não há nada a segurar, e segurar
        # assim mesmo deixaria a trava presa por uma escolha que não é escolha.
        _MEXENDO.pop(campo, None)
    else:
        _MEXENDO[campo] = rotulo
    return {"mesa": {campo: rotulo}}


@gesto("06-navegacao.html", "fechar-definicoes")
def fechar_definicoes(ctx: Contexto, o: dict[str, Any], p: Any) -> dict[str, Any] | None:
    """O fechar e o "Cancelar" da tela de definições: LARGAM o que ela não guardou.

    Este é o "sair" da decisão dela — *"até guardar ou sair"*. Os dois botões
    fecham a pop-up sozinhos, pelo `:target` do CSS; o que faltava era o Python
    saber que ela desistiu. Sem isso a trava das 21 linhas ficaria presa depois
    do "Cancelar", e a tela continuaria mostrando escolhas que ninguém vai
    guardar.

    ELE DEVOLVE A TABELA DO PERFIL na hora, e não espera o tique: um "Cancelar"
    que só desfaz meio segundo depois deixa a pessoa vendo a própria escolha
    fantasma na reabertura da tela.

    SEM PERFIL ATIVO ele ainda solta a trava — largar não depende de haver o que
    ler — e devolve o de fábrica, que é o que `_linhas_dos_botoes({})` dá.
    """
    _largar_o_que_ela_mexeu()
    return {"mesa": _linhas_dos_botoes(
        perfil.ativo((ctx.state or {}).get("active_profile")))}


@gesto("06-navegacao.html", "tecla-escrita")
def tecla_escrita(ctx: Contexto, o: dict[str, Any], p: Any) -> dict[str, Any] | None:
    """Ela mexeu num dos oito campos de *Teclas do teclado*. NÃO grava nada.

    É O IRMÃO DO `linha-de-botao`, e existe pela mesma decisão dela de
    02/09/2026 — *"não vira gravação automática: ela quer escolher várias,
    conferir e aplicar de uma vez"*. Quem grava é o "Guardar" da tela.

    ELE TEM DE ATENDER O **CLIQUE**, e não só o `change`, e isso é o que faz o
    campo de texto ser editável de verdade. Medido no motor: o `escrever()` do
    piloto escreve `el.value = t` sempre que os dois diferem, e um campo em
    edição difere já na primeira letra — o tique de 100 ms apagaria o que ela
    está digitando. O `change` de um `<input>` só chega quando o campo PERDE o
    foco, tarde demais. O clique dentro do campo chega na hora
    (`hefesto_vivo`, o ouvinte de `click` no documento), e é ele que abre a
    trava; o `change` que vem depois a atualiza com o texto final.

    A RECUSA É `RuntimeError`, e não `ValueError`, de propósito: o
    `_recusou_dizendo` do piloto (`hefesto_vivo.py:2618`) leva à tela a frase do
    `RuntimeError` e cala a do `ValueError`, que é a linguagem de quem programa.
    Uma combinação que ela digitou e o produto não sabe digitar é conversa com
    ELA — tem de aparecer no cartão, em laranja.

    E A ANTERIOR SOBREVIVE À RECUSA, sem ninguém a devolver: este gesto não
    escreve em disco, e ao recusar ele LARGA a trava daquele campo — no tique
    seguinte (100 ms) a pintura devolve o que o perfil guarda, por cima do texto
    inválido. Segurar a trava faria a tela ficar mostrando o erro dela para
    sempre, e o "Guardar" recusaria a cada clique por causa dele.
    """
    campo = str(o.get("campo") or "")
    botao = campo.removeprefix(PREFIXO_DA_TECLA)
    if not campo.startswith(PREFIXO_DA_TECLA) or botao not in acoes.DOMINIO_DO_TECLADO:
        raise ValueError(
            f"tecla-escrita: o clique não disse qual botão (veio {campo!r}). O "
            f"`data-campo` de cada campo é `{PREFIXO_DA_TECLA}<botão>`, e ele "
            "vem do gerador.")
    # O TEXTO NÃO É APARADO AQUI, e a diferença é de um espaço que ELA está
    # digitando: com `Ctrl + ` no campo, guardar `Ctrl +` na trava faz a pintura
    # do tique seguinte reescrever o campo — e o cursor SALTA para antes do
    # espaço, no meio da combinação. Quem apara é `tokens_da_tecla`, na
    # tradução, que é onde aparar não mexe no que ela vê.
    texto = str(o.get("valor") or "")
    try:
        tokens = tokens_da_tecla(texto)
    except ValueError as erro:
        _MEXENDO.pop(campo, None)
        raise RuntimeError(
            f"{_nome_do_botao(botao)}: {erro} O que estava guardado continua "
            "valendo — nada foi gravado.") from erro
    # O TEXTO QUE FICA NA TRAVA É O **DELA**, e não a volta do round-trip: ela
    # pode escrever `ctrl+w` ou `KEY_LEFTCTRL+KEY_W`, e reescrever o campo com a
    # forma canônica no meio da digitação seria mexer no que ela está fazendo.
    # A canônica aparece no tique seguinte ao "Guardar", que é quando o perfil
    # passou a dizê-la.
    _MEXENDO[campo] = texto
    return {"mesa": {campo: texto}} if tokens or not texto else None


@gesto("06-navegacao.html", "fechar-teclas")
def fechar_teclas(ctx: Contexto, o: dict[str, Any], p: Any) -> dict[str, Any] | None:
    """O fechar e o "Cancelar" da tela de teclas: LARGAM o que ela não guardou.

    Mesmo papel do `fechar-definicoes`, e o mesmo motivo: sem ele a trava dos
    oito campos ficaria presa depois de ela desistir, e a tela continuaria
    mostrando um texto que ninguém vai gravar.
    """
    _largar_o_que_ela_mexeu()
    return {"mesa": teclas_dos_botoes(
        perfil.ativo((ctx.state or {}).get("active_profile")))}


def _atalhos_de_hoje(prof: Any) -> dict[str, list[str]]:
    """`Profile.key_bindings` MATERIALIZADO, com o mesmo alcance de hoje.

    `None` quer dizer *"herda `DEFAULT_BUTTON_BINDINGS` inteiro"*, e o produto o
    resolve assim (`profiles/manager.resolve_key_bindings`). Para trocar UMA
    linha é preciso um dicionário, e o dicionário que **não muda nada** é a
    cópia do de fábrica — medido, e não escolhido: `resolve_key_bindings(None)`
    devolve `dict(DEFAULT_BUTTON_BINDINGS)`, exatamente o mesmo objeto que
    `resolve_key_bindings(dict(DEFAULT_BUTTON_BINDINGS))` devolve.

    O CAMINHO DE VOLTA EXISTE: quando o dicionário terminar igual ao de fábrica,
    quem grava devolve `None` — senão o perfil dela congelaria o padrão de HOJE
    e deixaria de acompanhar uma troca no produto. É a mesma disciplina do
    `button_actions`, e a razão está escrita em `guardar_definicoes`.
    """
    from hefesto_dualsense4unix.core.keyboard_mappings import DEFAULT_BUTTON_BINDINGS

    atual = getattr(prof, "key_bindings", None)
    if atual is None:
        return {b: list(t) for b, t in DEFAULT_BUTTON_BINDINGS.items()}
    return {b: list(t) for b, t in atual.items()}


def _de_fabrica_vira_none(atalhos: dict[str, list[str]]) -> dict[str, list[str]] | None:
    """`None` quando o dicionário é o de fábrica — ver `_atalhos_de_hoje`."""
    from hefesto_dualsense4unix.core.keyboard_mappings import DEFAULT_BUTTON_BINDINGS

    de_fabrica = {b: list(t) for b, t in DEFAULT_BUTTON_BINDINGS.items()}
    return None if atalhos == de_fabrica else atalhos


@gesto("06-navegacao.html", "guardar-teclas")
def guardar_teclas(ctx: Contexto, o: dict[str, Any], p: Any) -> dict[str, Any] | None:
    """"Guardar" da tela *Teclas do teclado*. `Profile.key_bindings`.

    **É A METADE QUE FALTAVA DA PARIDADE** — `paridade-gtk-html.csv:208`. A
    janela antiga deixa ela digitar qualquer combinação de `KEY_*` na coluna
    "Tecla do teclado"; a tela nova só tinha a lista fechada de 26 ações, e
    `key_bindings` só era tocado **para ser zerado**.

    O QUE ELE GRAVA, e o alcance é o do produto: os oito botões de
    `acoes.DOMINIO_DO_TECLADO`. Os outros catorze não estão aqui porque
    `key_bindings` não manda neles — o que vale ali é o mapa fixo do
    `UinputMouseDevice`, e gravar seria pôr no disco uma escolha que o
    `resolver()` não lê.

    O QUE ELE **NÃO** APAGA, e é o Passo 2 da sprint: as chaves de
    `key_bindings` que estão FORA desses oito. Ela pode ter escrito `Ctrl + W`
    no Cross pela janela antiga, e nada nesta tela alcança essa linha — logo
    nada nesta tela tem o direito de apagá-la. O dicionário de partida é o do
    perfil (`_atalhos_de_hoje`), e só as oito chaves são reescritas.

    CAMPO EM BRANCO É `— Nada —`, e não "sem opinião": a chave sai do
    dicionário, e `_tabela_efetiva` lê a ausência dentro do domínio como
    silêncio, que é o que `resolve_key_bindings` entrega ao device. É a mesma
    palavra que a lista ao lado usa, dita pelo campo vazio.

    ELE RECUSA DIZENDO, uma linha por vez, e nada é gravado quando alguma
    recusa: gravar sete de oito e calar sobre a oitava é o botão que responde
    calado.
    """
    nome = _perfil_ativo_ou_recusa(ctx)
    forma = o.get("forma")
    if not isinstance(forma, dict) or not forma:
        raise RuntimeError(
            "não consegui ler os campos da tela. O botão precisa do "
            "`data-hef-forma` para o piloto recolher o que você escreveu — se "
            "ele sumiu do desenho, o Guardar não tem o que gravar.")

    escritos: dict[str, tuple[str, ...]] = {}
    recusas: list[str] = []
    for chave, texto in forma.items():
        if not str(chave).startswith(PREFIXO_DA_TECLA):
            continue
        botao = str(chave)[len(PREFIXO_DA_TECLA):]
        if botao not in acoes.DOMINIO_DO_TECLADO:
            continue
        try:
            escritos[botao] = tokens_da_tecla(str(texto))
        except ValueError as erro:
            recusas.append(f"{_nome_do_botao(botao)}: {erro}")
    if recusas:
        raise RuntimeError(
            "não gravei nada — " + " ".join(recusas)
            + " O que estava guardado continua valendo.")
    if not escritos:
        raise RuntimeError(
            "não achei nenhum campo de tecla na tela. Os oito campos vêm do "
            "gerador com `data-campo=\"tecla-<botão>\"`; sem eles não há o que "
            "gravar.")

    loader = perfil._com_o_src()
    prof = loader.load_profile(nome)
    atalhos = _atalhos_de_hoje(prof)
    for botao, tokens in escritos.items():
        if tokens:
            atalhos[botao] = list(tokens)
        else:
            atalhos.pop(botao, None)
    novo = _de_fabrica_vira_none(atalhos)
    # A COMPARAÇÃO É DIRETA, e é o Python que já separa os três estados: `None`
    # (herda), `{}` (ela esvaziou tudo) e um dicionário. `None == {}` é falso, e
    # é o que impede este ramo de confundir "herda" com "vazio" — a mesma
    # distinção do esquema e a mesma que `resolve_key_bindings` aplica.
    #
    # NADA A GRAVAR **É UM DESFECHO, E ELE FALA**, pela mesma correção de
    # 02/09/2026 que o `guardar_definicoes` carrega: um `return` seco aqui seria
    # o botão que responde calado. E gravar o idêntico não é de graça — trocaria
    # a data do arquivo e faria o daemon reaplicar um perfil igual, o que um
    # `profile.switch` no meio de uma partida cobra.
    if getattr(prof, "key_bindings", None) == novo:
        _largar_o_que_ela_mexeu()
        raise RuntimeError(
            f"não havia o que guardar — o perfil “{nome}” já digita exatamente "
            "o que estes campos mostram. Está guardado. Para mudar alguma "
            "coisa, escreva outra tecla e clique aqui de novo.")
    # A LISTA AO LADO PODE ESTAR MASCARANDO O QUE ELA ACABOU DE ESCREVER, e a
    # tela DIZ em vez de gravar por cima: `button_actions` é a camada de cima
    # (`acoes._tabela_efetiva`), então uma linha escolhida na tabela vence a
    # tecla escrita aqui. Apagar a escolha da tabela de carona seria desfazer,
    # em silêncio, um clique que ela deu na outra tela.
    escolhas = getattr(prof, "button_actions", None) or {}
    mascarados = sorted(b for b, t in escritos.items()
                        if b in escolhas and "+".join(t) != str(escolhas[b]))
    perfil.gravar_e_reaplicar(prof.model_copy(update={"key_bindings": novo}), ctx, p)
    _largar_o_que_ela_mexeu()
    if mascarados:
        raise RuntimeError(
            "guardei as teclas, e estas linhas continuam fazendo o que a lista "
            "de <b>Definições Controle e Mouse</b> diz, que vence: "
            + ", ".join(f"{_nome_do_botao(b)} = "
                        f"{acoes.rotulo(str(escolhas[b]))}" for b in mascarados)
            + ". Para a tecla que você escreveu valer, ponha essas linhas de "
              "volta no de fábrica lá.")
    return {"mesa": teclas_dos_botoes(
        perfil.ativo((ctx.state or {}).get("active_profile")))}


@gesto("06-navegacao.html", "padrao-da-tecla")
def padrao_da_tecla(ctx: Contexto, o: dict[str, Any], p: Any) -> dict[str, Any] | None:
    """"Voltar ao padrão" de **UMA** linha — o Passo 2 da sprint.

    A REGRA DELA, e é a razão de este gesto existir: *"'Voltar ao padrão'
    devolve a LINHA ao padrão; ele não é um apagador de tudo o que ela escreveu
    na janela antiga."* O botão da tela inteira continua existindo e continua
    zerando os dois campos — ele DIZ o que apaga, na confirmação e no recibo —,
    mas até hoje era o ÚNICO caminho: trocar uma linha de volta custava perder
    todas as outras.

    O QUE É "O PADRÃO DESTA LINHA", perguntado ao dono: `acoes.padrao()[botão]`,
    que dentro do `DOMINIO_DO_TECLADO` é por construção o que
    `DEFAULT_BUTTON_BINDINGS` diz. **ESCREVER É O CERTO, e APAGAR seria o
    errado** — e a diferença é medida: dentro de um `key_bindings` que já é
    dicionário, uma chave AUSENTE não é "de fábrica", é `— Nada —`
    (`acoes._tabela_efetiva`, e `resolve_key_bindings` não mescla com os
    defaults). Apagar a chave devolveria a linha ao SILÊNCIO com o botão
    dizendo "padrão".

    ELE TIRA A LINHA DAS DUAS CAMADAS, e tem de tirar: `button_actions` vence
    `key_bindings`, então devolver só a de baixo deixaria o botão fazendo o que
    a lista escolheu, com este gesto dizendo que voltou ao de fábrica.
    """
    botao = str(o.get("tecla") or o.get("linha") or "")
    if botao not in acoes.DOMINIO_DO_TECLADO:
        raise ValueError(
            f"padrao-da-tecla: o clique não disse qual linha (veio {botao!r}). "
            "O `data-tecla` de cada botão é o id do botão, e ele vem do gerador.")
    nome = _perfil_ativo_ou_recusa(ctx)
    loader = perfil._com_o_src()
    prof = loader.load_profile(nome)

    de_fabrica = acoes.padrao()[botao].split("+")
    atalhos = _atalhos_de_hoje(prof)
    antes = list(atalhos.get(botao) or ())
    atalhos[botao] = list(de_fabrica)
    novas_teclas = _de_fabrica_vira_none(atalhos)

    escolhas = dict(getattr(prof, "button_actions", None) or {})
    tirado = escolhas.pop(botao, None)
    novas_escolhas = escolhas or None

    mudou_tecla = (prof.key_bindings is None) != (novas_teclas is None) or (
        (prof.key_bindings or {}) != (novas_teclas or {}))
    if not mudou_tecla and tirado is None:
        # NADA A FAZER **É UM DESFECHO, E ELE FALA** — a mesma correção de
        # 02/09/2026 que o `padrao_definicoes` carrega: um `return` seco aqui
        # seria indistinguível de um botão que mentiu.
        _MEXENDO.pop(f"{PREFIXO_DA_TECLA}{botao}", None)
        raise RuntimeError(
            f"não havia o que voltar — {_nome_do_botao(botao)} já está no de "
            f"fábrica neste perfil (“{nome}”). Não gravei nada e não incomodei "
            "o serviço.")
    perfil.gravar_e_reaplicar(
        prof.model_copy(update={"key_bindings": novas_teclas,
                                "button_actions": novas_escolhas}), ctx, p)
    _MEXENDO.pop(f"{PREFIXO_DA_TECLA}{botao}", None)
    _MEXENDO.pop(f"{PREFIXO_DA_ACAO}{botao}", None)
    saiu = []
    if antes and antes != de_fabrica:
        saiu.append(f"a tecla “{_atalho_em_palavras('+'.join(antes))}”")
    if tirado is not None:
        saiu.append(f"a escolha “{acoes.rotulo(str(tirado))}” da lista")
    recado = (f"{_nome_do_botao(botao)} voltou ao de fábrica "
              f"(“{acoes.rotulo(acoes.padrao()[botao])}”)"
              + (", e com ele saiu " + " e ".join(saiu) if saiu else "")
              + ". As outras linhas não foram tocadas.")
    return {"recado": recado,
            "mesa": teclas_dos_botoes(
                perfil.ativo((ctx.state or {}).get("active_profile")))}


def _o_desenho_congelado(diferentes: dict[str, str]) -> dict[str, tuple[str, str]]:
    """As linhas de `diferentes` que são o DESENHO CONGELADO, e não escolha dela.

    O DEFEITO QUE ELA CURA, medido em 02/09/2026 e declarado em
    `core/keyboard_mappings.PADRAO_QUE_A_TELA_PUBLICADA_NAO_DIZ`: o L3 nasceu
    ALTERNADOR (`__TOGGLE_OSK__`, decisão 6 dela — *"aperta abre o teclado
    virtual, aperta de novo fecha"*), a página que o produto RENDERIZA foi
    congelada antes disso e não tem a `<option>` do rótulo novo, e por isso a
    pintura do `acao-l3` é RECUSADA EM SILÊNCIO (`hefesto_vivo.escrever`, alvo
    `valor`: um `<select>` só aceita o texto exato de uma opção que ele
    oferece). A linha fica mostrando *"Abrir o teclado na tela"*, que é
    `__OPEN_OSK__` — e o "Guardar" recolhia isso como se fosse escolha dela.

    O CUSTO, medido pelo fio do daemon (`acoes_de_botao.resolver` →
    `profiles.manager.resolve_key_bindings`): sem override o device recebe
    `['__TOGGLE_OSK__']`; com o que o "Guardar" gravava ele recebe
    `['__OPEN_OSK__']` — **o L3 para de alternar naquele perfil**, e no tique
    seguinte a pintura volta a casar e não sobra rastro em lugar nenhum.
    Bastava um clique para mudar qualquer OUTRA linha.

    O QUE SEPARA O CONGELADO DA ESCOLHA DELA É `_MEXENDO`, e não um literal:
    ele só tem linha que ELA trocou, pelo gesto `linha-de-botao`. Se o `acao-l3`
    está lá, ela escolheu *"Abrir o teclado na tela"* com o dedo dela — e isso
    o "Guardar" grava, como grava qualquer outra escolha. É a mesma distinção
    que a trava contra o apagador já usa logo abaixo.

    ELA MORRE SOZINHA NO DIA DA PUBLICAÇÃO: a tabela que a alimenta é a
    declaração, e `test_o_padrao_de_fabrica_cabe_na_tela_publicada` reprova a
    declaração que caducou. Publicada a `06`, a linha do L3 sai da tabela, esta
    função devolve `{}` e o "Guardar" volta a gravar as 21 sem exceção — sem
    ninguém precisar lembrar de apagar nada daqui.

    :returns: `{botão: (o token de fábrica, o token que a tela pôs no lugar)}`.
    """
    fora: dict[str, tuple[str, str]] = {}
    for botao, (de_fabrica, da_tela) in PADRAO_QUE_A_TELA_PUBLICADA_NAO_DIZ.items():
        if diferentes.get(botao) != da_tela:
            continue
        if f"{PREFIXO_DA_ACAO}{botao}" in _MEXENDO:
            continue
        fora[botao] = (de_fabrica, da_tela)
    return fora


def _frase_do_congelado(congelado: dict[str, tuple[str, str]]) -> str:
    """O que NÃO foi gravado e por quê — a frase vai para a tela dela.

    RECUSAR DIZENDO É OBRIGATÓRIO nesta casa, e aqui a recusa é PARCIAL: o resto
    da forma foi gravado. Engolir a linha em silêncio trocaria um defeito por
    outro — o produto deixaria de estragar o perfil e passaria a não contar o
    que ignorou.
    """
    partes = []
    for botao, (de_fabrica, da_tela) in sorted(congelado.items()):
        rotulo_certo = acoes.ACOES.get(de_fabrica, ("", de_fabrica))[1]
        rotulo_tela = acoes.ACOES.get(da_tela, ("", da_tela))[1]
        partes.append(
            f"{_nome_do_botao(botao)} (a tela mostra “{rotulo_tela}”; de fábrica "
            f"ele faz “{rotulo_certo}”)")
    return (
        "não guardei estas linhas, porque o que a tela mostra nelas não é a sua "
        "escolha: " + ", ".join(partes) + ". A lista desta versão da página não "
        "tem a opção do que o produto faz de fábrica, então ela abre no rótulo "
        "mais próximo — gravar isso trocaria o comportamento do controle sem "
        "você pedir. Se você QUER essa opção, escolha-a na linha e clique aqui "
        "de novo: aí é escolha sua e eu gravo.")


def _perfil_ativo_ou_recusa(ctx: Contexto) -> str:
    """O nome do perfil ativo, ou a recusa com o motivo.

    OS ATALHOS SÃO DO PERFIL, não da máquina (`profiles/schema.py`), e essa é a
    frase que a recusa precisa carregar: sem ela, "não deu" vira mistério.
    """
    nome = str((ctx.state or {}).get("active_profile") or "").strip()
    if not nome:
        raise RuntimeError(
            "não há perfil ativo agora, e o que cada botão faz é do perfil — não "
            "da máquina. Escolha um perfil na aba Perfis e tente de novo.")
    return nome


@gesto("06-navegacao.html", "guardar-definicoes")
def guardar_definicoes(ctx: Contexto, o: dict[str, Any], p: Any) -> None:
    """"Guardar" das 21 linhas de *o que cada botão faz*. `Profile.button_actions`.

    ELE PASSOU A TER DONO EM 01/09/2026, por decisão dela: *"ganha campo. essa é
    a parte das features que precisam ou serem ajustadas ou desenvolvidas."* O
    que o segurava era medido e verdadeiro — a tela deixava escolher 21 linhas e
    o perfil alcançava 9 —, e a cura foi o campo nascer, não o botão fingir.

    DE ONDE VEM O QUE ELE GRAVA: da `forma`, que o piloto recolhe quando o botão
    traz `data-hef-forma`. O ouvinte manda o valor do elemento CLICADO, e o
    Guardar é outro elemento — sem a forma, ele não teria como saber o que está
    escolhido em cada linha, e era por isso que só podia recusar.

    SÓ O QUE MUDOU VAI PARA O DISCO. Gravar as 21 sempre encheria o perfil de
    linhas iguais ao padrão, e no dia em que o padrão do produto mudasse o perfil
    congelaria o padrão VELHO sem ninguém ter escolhido isso. `button_actions`
    guarda diferença, e é o que o `None` do campo quer dizer: herda.

    O CAMPO ZERADO É `None`, e nunca `{}`: `None` é o mesmo estado de um perfil
    que nunca foi editado, e `{}` seria "nenhum botão faz nada". Depois das duas
    recusas abaixo, o único caminho que ainda grava `None` é o perfil que já
    tinha `{}` — a normalização de um estado que o esquema não pretende.

    FATO SUBSTITUÍDO (02/09/2026, corretivo): esta linha dizia *"e quando nada
    mudou, ele grava `None` — que apaga o campo"*. **Nada mudou deixou de gravar
    coisa alguma.** Com o perfil guardando escolhas, a trava recusa; com o perfil
    já igual à tela, a recusa nova diz que já está guardado. Nenhum dos dois
    chega ao disco.

    ELE ERA UM APAGADOR COM RÓTULO DE "GUARDAR", e isso foi medido em
    02/09/2026: as 21 opções que a tela mostrava eram **exatamente**
    `acoes.padrao()`, logo `diferentes` saía `{}` e o gesto gravava
    `button_actions = None` — apagando, em silêncio, qualquer escolha que o
    perfil dela guardasse. O botão dizia "Guardar" e fazia o contrário.

    FATO SUBSTITUÍDO, e ele estava escrito AQUI: *"as 21 `<select>` têm
    `data-linha` e nenhum `data-campo`, então nada nunca as pintou"*. Isso valia
    contra a página publicada da manhã. **Ela mandou publicar** no mesmo dia
    (commit `70b58116`), e a página publicada de agora traz `data-campo` e
    `data-hef-alvo="valor"` nas 21 — medido com dublê: os 21 campos saem
    PRODUTO, e o valor que a tela mostra é o do perfil.

    O QUE SOBRA DA TRAVA, e por que ela FICA: a forma toda no de fábrica com o
    perfil guardando escolhas deixou de ser o estado permanente e virou uma
    JANELA — os 100 ms entre a página carregar e o primeiro tique pintar
    (`hefesto_vivo.TIQUE_MS`). Um clique ali dentro ainda leria o desenho como
    se fosse a escolha dela, e ainda apagaria. Enquanto o piloto não marcar o
    que já foi pintado, esta trava é o que separa "ela zerou" de "a tela ainda
    não falou".

    O QUE A TELA OFERECE E O PRODUTO NÃO ATENDE **é dito, não engolido**: os
    comandos "Abrir a Steam", "Sair do modo jogo" e "Escolher um programa…", os
    dois papéis de eixo pedidos a um botão, e os gatilhos L2/R2, que são espelho
    do cross e do triangle (`uinput_mouse._resolve_emulated_set`). O gesto GRAVA
    o resto e LEVANTA nomeando o que não pousou — quem clicou fica sabendo, em
    vez de descobrir pelo botão que não responde.

    E O QUE A TELA **NÃO SABE** OFERECER TAMBÉM É DITO, e deixou de ser gravado
    — 02/09/2026. Ver `_o_desenho_congelado`: o L3 nasceu ALTERNADOR e a página
    publicada não tem a `<option>` desse rótulo, então a linha abre mostrando
    "Abrir o teclado na tela". Recolher isso gravava `{'l3': '__OPEN_OSK__'}` no
    perfil ATIVO — **o L3 parava de alternar** — em silêncio, bastando um clique
    para mudar qualquer OUTRA linha.
    """
    nome = _perfil_ativo_ou_recusa(ctx)
    forma = o.get("forma")
    if not isinstance(forma, dict) or not forma:
        raise RuntimeError(
            "não consegui ler as linhas da tela. O botão precisa do "
            "`data-hef-forma` para o piloto recolher os campos — se ele sumiu do "
            "desenho, o Guardar não tem o que gravar.")

    escolhas: dict[str, str] = {}
    nao_reconhecidas: list[str] = []
    for botao, rotulo in forma.items():
        if botao not in acoes.BOTOES:
            continue
        token = acoes.token_do_rotulo(str(rotulo))
        if token is None:
            nao_reconhecidas.append(f"{_nome_do_botao(botao)}={rotulo!r}")
            continue
        escolhas[botao] = token
    if nao_reconhecidas:
        raise ValueError(
            "estas linhas trazem uma opção que o produto não conhece: "
            + ", ".join(nao_reconhecidas)
            + ". A lista da tela e a do produto saem do mesmo lugar "
              "(`core/acoes_de_botao.ACOES`) — se divergiram, foi o desenho que "
              "andou sem o gerador.")

    de_fabrica = acoes.padrao()
    diferentes = {b: a for b, a in escolhas.items() if de_fabrica.get(b) != a}
    # O DESENHO CONGELADO NÃO É ESCOLHA DELA — 02/09/2026. Ver
    # `_o_desenho_congelado`: a linha cuja opção de fábrica a página PUBLICADA
    # não sabe dizer abre no rótulo mais próximo, e recolhê-la aqui gravava no
    # perfil ATIVO uma troca de comportamento que ela não pediu.
    congelado = _o_desenho_congelado(diferentes)
    for botao in congelado:
        del diferentes[botao]
    # A FRASE VIAJA COM TODOS OS DESFECHOS, e não só com o que grava: os dois
    # ramos de recusa abaixo também precisam dizê-la, senão a linha some do
    # relato exatamente nos casos em que nada mais é dito.
    aviso = _frase_do_congelado(congelado) if congelado else ""

    loader = perfil._com_o_src()
    prof = loader.load_profile(nome)
    novo = diferentes or None
    # NADA A GRAVAR **É UM DESFECHO, E ELE FALA** — 02/09/2026, corretivo. Aqui
    # havia um `return` seco, e ele era o outro lado da recusa logo abaixo: a
    # trava manda "espere a tabela se preencher e clique de novo", e o segundo
    # clique caía exatamente NESTE `return` — sem gravar, sem chamar e sem uma
    # palavra. Encenado com dublê de disco e ponte muda:
    #
    #     1º clique (tabela ainda no desenho)  → RuntimeError, com a frase
    #     2º clique (tabela cheia, = ao perfil) → voltou SEM levantar, gravou 0
    #
    # Uma recusa que INSTRUI a repetir o gesto e depois não responde nada é pior
    # que uma recusa seca: ela promete que a segunda tentativa funciona. E um
    # gesto que devolve `None` não toca o DOM (`hefesto_vivo._deu_certo`), logo
    # o segundo clique era o botão que responde calado — o defeito que esta casa
    # mais persegue.
    if prof.button_actions == novo:
        guardadas = (f"nenhuma escolha sua: as {len(acoes.BOTOES)} linhas estão "
                     "no de fábrica"
                     if not novo else
                     f"{len(novo)} escolha(s) sua(s)")
        # NADA PENDENTE: a tela e o disco dizem a mesma coisa, logo não há
        # escolha em curso a segurar. Soltar aqui é o que impede a trava de
        # ficar presa por uma linha que ela desfez à mão.
        _largar_o_que_ela_mexeu()
        raise RuntimeError(
            f"não havia o que guardar — o perfil “{nome}” já tem exatamente o "
            f"que a tabela mostra ({guardadas}). Está guardado. Para mudar "
            "alguma coisa, troque a linha e clique aqui de novo; para voltar "
            "tudo ao de fábrica, use o “Voltar ao padrão” ao lado."
            + (f" E {aviso}" if aviso else ""))
    # A TRAVA CONTRA O APAGADOR — 02/09/2026. "Nada diferente do de fábrica" só
    # quer dizer "ela zerou as 21 linhas" DEPOIS que as 21 linhas mostraram o
    # que o perfil guarda. Elas mostram desde que a página foi publicada, mas
    # não no primeiro instante: entre a carga e o primeiro tique há 100 ms
    # (`hefesto_vivo.TIQUE_MS`) em que a tela ainda é o desenho, e nessa janela
    # esta forma quer dizer outra coisa — *o piloto releu o desenho*.
    #
    # E ZERAR TEM BOTÃO PRÓPRIO, a dois centímetros: "Voltar ao padrão"
    # (`padrao-definicoes`), que zera dizendo e ainda pede confirmação. Um
    # "Guardar" que apaga em silêncio é o botão que responde calado — o defeito
    # que esta casa mais persegue.
    #
    # E ELA DEIXOU DE SER CEGA — 02/09/2026, segunda correção. A trava não tinha
    # como distinguir *"ela zerou as 21 linhas"* de *"o piloto releu o desenho"*,
    # e por isso recusava as duas. Com a decisão dela sobre o repinte, a
    # diferença passou a estar ESCRITA: `_MEXENDO` só tem linha que ELA trocou,
    # pelo gesto `linha-de-botao`. Vazio, a forma é o que a pintura pôs — e a
    # trava vale. Cheio, a forma é escolha dela — e zerar de propósito é um
    # pedido legítimo, que o "Guardar" atende.
    #
    # ISSO CURA A FRASE QUE ENSINAVA UM CAMINHO INEXISTENTE. A recusa mandava
    # *"espere a tabela se preencher e clique de novo"*, e trocar a linha nunca
    # chegava ao Guardar: o tique reescrevia a escolha em ≤1,5 s. Agora chega.
    if novo is None and prof.button_actions and not _MEXENDO:
        # A CONTA DIZ QUANTAS SOBRARAM, e não "as 21", quando o desenho
        # congelado tirou alguma da forma: dizer "as 21 estão no de fábrica"
        # logo ao lado de "não guardei a linha do L3" seria a mesma tela
        # afirmando duas coisas que não cabem juntas.
        quantas = (f"as {len(acoes.BOTOES) - len(congelado)} linhas restantes "
                   "da tela estão" if congelado
                   else f"as {len(acoes.BOTOES)} linhas da tela estão todas")
        raise RuntimeError(
            f"não guardei: {quantas} no de fábrica, e o "
            f"perfil “{nome}” guarda "
            f"{len(prof.button_actions)} escolha(s) sua(s). Gravar isto as "
            "apagaria. A tela leva meio segundo para mostrar o que o perfil "
            "guarda; se você clicou antes disso, o que estava na tela era o "
            "desenho, e não a sua escolha. Espere a tabela se preencher — para "
            "voltar tudo ao de fábrica de propósito, use o “Voltar ao padrão” "
            "ao lado."
            + (f" E {aviso}" if aviso else ""))
    # O QUE ESTE CLIQUE VAI FAZER PARAR DE VALER, contado ANTES da gravação —
    # 04/09/2026, e é a metade dita do defeito §3-1. Depois do
    # `gravar_e_reaplicar` o `prof` da memória continua sendo o de antes, mas
    # contar aqui deixa a ordem óbvia para quem ler: o recado fala do que ESTE
    # gesto trocou, e não do estado que sobrou.
    perdidos = atalhos_que_param_de_valer(
        {"key_bindings": getattr(prof, "key_bindings", None) or {},
         "button_actions": novo})
    perfil.gravar_e_reaplicar(prof.model_copy(update={"button_actions": novo}), ctx, p)
    # GUARDADO É O FIM DA EDIÇÃO. A partir daqui o perfil diz o que a tela diz,
    # e o tique volta a mandar na tabela — que é a outra metade de *"até guardar
    # ou sair"*.
    _largar_o_que_ela_mexeu()

    _, _, sem_dono = acoes.resolver(novo)
    recados = []
    if perdidos:
        # NOMEAR O QUE SE PERDE É O MÍNIMO, e o silêncio aqui era o defeito
        # inteiro: o perfil continua MOSTRANDO os dois campos, como se os dois
        # valessem, e o efeito de `key_bindings` morre na próxima ativação sem
        # uma palavra. A cura de verdade é `resolver()` herdar `key_bindings`, e
        # ela mora em `core/acoes_de_botao.py` — está no relato desta frente.
        recados.append(
            "guardei, e estes atalhos que você escreveu na janela antiga param "
            "de valer neste perfil: "
            + ", ".join(f"{_nome_do_botao(b)} = {_atalho_em_palavras(t)}"
                        for b, t in perdidos)
            + ". O perfil ainda os guarda no arquivo, mas o que passa a valer é "
              "o que esta tabela mostra — use o “Voltar ao padrão” para devolver "
              "tudo ao de fábrica.")
    if sem_dono:
        recados.append(
            "guardei o que o produto sabe fazer, e estas linhas ficaram sem "
            "quem as atenda: " + ", ".join(_nome_do_botao(b) for b in sem_dono)
            + ". Elas estão no perfil e não acendem nada hoje — é feature que "
              "falta, não erro seu.")
    if aviso:
        recados.append(aviso)
    if recados:
        raise RuntimeError(" ".join(recados))


@gesto("06-navegacao.html", "padrao-definicoes")
def padrao_definicoes(ctx: Contexto, o: dict[str, Any],
                      p: Any) -> dict[str, Any] | None:
    """"Voltar ao padrão" das 21 linhas de *o que cada botão faz*.

    O QUE ELE FAZ: grava `key_bindings = None` no perfil ATIVO e manda o daemon
    reaplicá-lo. `None` não é "vazio" — o esquema o define como *"herda
    `DEFAULT_BUTTON_BINDINGS` do core"* (`profiles/schema.py:1129`), e `{}` é
    outra coisa (teclado silencioso). Escrever `{}` aqui devolveria um controle
    MUDO com o botão dizendo "de fábrica".

    E ELE DEVOLVE AS VINTE E UMA, ao contrário do que parece. Contadas na tela e
    no fonte, em 01/09/2026:

        9 linhas   `key_bindings` as alcança — l1, r1, l3, r3, options, create
                   e as três regiões do touchpad (`core/keyboard_mappings.py:41`)
        12 linhas  mapas FIXOS do produto — `BUTTON_TO_UINPUT`, `DPAD_TO_KEY` e
                   `EDGE_KEY_MAP` (`integrations/uinput_mouse.py:93,99,105`),
                   mais o L2/R2 e a DIREÇÃO dos analógicos, que binding nenhum
                   alcança

    As 12 não têm onde ser mudadas — logo estão **sempre** de fábrica, e zerar as
    9 devolve a tabela inteira ao de fábrica. É por isso que este botão fecha
    inteiro, enquanto o "Guardar" ao lado dele não fecha: guardar 9 de 21
    escolhas e perder 12 caladas é o botão que responde calado.

    ELE ZERA OS DOIS CAMPOS desde 01/09/2026: o `key_bindings` (as nove teclas)
    e o `button_actions` (as vinte e uma linhas da tela, que nasceu no mesmo
    dia). Zerar só um deixaria a tabela metade de fábrica, com o botão dizendo
    o contrário.

    O ALVO É O PERFIL ATIVO, e ele é dito: os dois são campo de perfil
    (`profiles/schema.py`), não da máquina. Sem perfil ativo o botão RECUSA —
    devolver ao padrão "o perfil nenhum" não quer dizer nada.

    A GRAVAÇÃO É A DA CASA: `perfil.gravar_e_reaplicar`, a mesma que a aba
    Perfis usa. O `save_profile` grava em disco e o `profile.switch` reaplica se
    for o ativo.

    FATO SUBSTITUÍDO, e é o que destravou este botão: o `SEM_GESTO` abaixo dizia
    que "gravar perfil não tem método". Tem — `profiles/loader.save_profile`, e
    o `a10_perfis` já o usava desde a mesma leva que escreveu a frase.

    E ELE DÁ RECIBO DO QUE APAGOU — 04/09/2026, pelo canal de SUCESSO da D-01.
    Até hoje ele apagava os `key_bindings` que ela escreveu na janela antiga e
    voltava sem uma palavra: o piloto imprimia `aplicado` no terminal de quem
    lançou a janela, e quem clica não lê terminal. O `recado` que este gesto
    devolve nomeia quantos atalhos saíram, no cartão dela, em verde — o que
    apaga tem de dizer o que apagou.
    """
    nome = _perfil_ativo_ou_recusa(ctx)
    loader = perfil._com_o_src()
    prof = loader.load_profile(nome)
    # OS DOIS CAMPOS, e não só um — 01/09/2026, quando o `button_actions`
    # nasceu. O perfil passou a guardar o que cada botão faz em DOIS lugares:
    # o `key_bindings` (as nove teclas, da FEAT-KEYBOARD-PERSISTENCE-01) e o
    # `button_actions` (as vinte e uma linhas da tela). Um "Voltar ao padrão"
    # que zerasse só o primeiro deixaria a tabela metade de fábrica e metade
    # não — e o botão diria "de fábrica" sobre isso.
    if prof.key_bindings is None and prof.button_actions is None:
        # JÁ ESTÁ DE FÁBRICA. Gravar de novo trocaria a data do arquivo e faria
        # o daemon reaplicar um perfil idêntico — barulho sem efeito, e um
        # `profile.switch` no meio de uma partida não é de graça. **Mas não
        # fazer nada não é não dizer nada:** até 02/09/2026 este ramo era um
        # `return` seco, e a régua do aparelho o lia como "disse aplicado e
        # nada mudou" — indistinguível de um botão que mentiu. Agora ele
        # RECUSA DIZENDO, que é o desfecho verdadeiro: não havia o que voltar.
        # Nada é gravado e o daemon continua sem ser incomodado.
        _largar_o_que_ela_mexeu()
        raise RuntimeError(
            f"não havia o que voltar — o perfil “{nome}” já está no de fábrica "
            f"nas {len(acoes.BOTOES)} linhas de o que cada botão faz. Não gravei "
            "nada e não incomodei o daemon.")
    # O QUE ELE APAGA, contado ANTES de apagar: os atalhos que ela escreveu à
    # mão continuam sendo os do perfil até esta linha.
    atalhos = getattr(prof, "key_bindings", None) or {}
    perfil.gravar_e_reaplicar(
        prof.model_copy(update={"key_bindings": None, "button_actions": None}), ctx, p)
    # "VOLTAR AO PADRÃO" TAMBÉM É FIM DE EDIÇÃO: o perfil foi zerado, e segurar
    # escolhas pendentes por cima disso faria a tabela mostrar o contrário do
    # que o botão acabou de fazer.
    _largar_o_que_ela_mexeu()
    if not atalhos:
        return None
    quais = ", ".join(f"{_nome_do_botao(b)} = {_atalho_em_palavras(_colado(v))}"
                      for b, v in sorted(atalhos.items()))
    return {"recado": (
        f"Voltei as {len(acoes.BOTOES)} linhas ao de fábrica, e com elas saíram "
        f"{len(atalhos)} atalho(s) de teclado que este perfil guardava: "
        f"{quais}.")}


#: OS OITO QUE CONTINUAM SEM DONO, com o motivo MEDIDO de cada um — o
#: inventário honesto do que falta, no lugar de um botão que responde calado. O
#: piloto os recusa PELO NOME (`[gesto sem dono] 06-navegacao.html · <nome>`), e
#: por isso as chaves aqui são os nomes que ele vai imprimir, um por um: os dois
#: `bignum` sem dono viram quatro linhas (`-menos` e `-mais`), porque são quatro
#: botões.
#:
#: ERAM QUATORZE, depois TREZE. O `teclado` saiu na segunda leva — o que o
#: segurava não era falta de método, era o piloto não mandar o valor de um
#: `<select>`. O `padrao-definicoes` saiu na TERCEIRA, e o que o segurava era
#: um FATO ERRADO escrito aqui: que gravar perfil não tinha método. Tinha, e o
#: `a10_perfis` já o usava. As duas saídas têm a mesma forma — o que prendia o
#: botão não era o produto, era o que estava escrito sobre ele.
#:
#: -------------------------------------------------------------------------
#: `mouse.emulation.restore` NÃO virou botão, e a segunda leva reconfirmou a
#: recusa com uma razão MAIOR que a da primeira. Três coisas, e a terceira é a
#: que fecha a porta:
#:
#: 1. o handler diz o lugar dele com todas as letras — *"entra na transição de
#:    modo (`app/actions/mode_transition.py`), **nunca em um botão solto**"*
#:    (`daemon/ipc_handlers.py:5039`);
#: 2. ele devolve a preferência PERSISTIDA — não "o de fábrica" nem "o que a
#:    tela mostra" —, então pendurá-lo num "Voltar ao padrão" faria o botão
#:    prometer uma coisa e fazer outra;
#: 3. **ele LIGA o mouse.** `restore_mouse_preference`
#:    (`daemon/lifecycle.py:1438`) chama `set_mouse_emulation(pref, …)` e, com a
#:    preferência nunca gravada, `pref` vira `True` por default (`:1403`) — o
#:    cursor DELA passa a andar pelo controle, e o gamepad virtual cai junto
#:    (`:1359`). Isso o põe na mesma prateleira do gesto `modo`, que já está em
#:    `hefesto_vivo.PERIGOSOS` justamente para a prova botão a botão não o
#:    clicar. Ligá-lo aqui criaria um gesto perigoso NOVO **fora** daquela
#:    lista, e a lista mora num arquivo que esta aba não pode tocar.
SEM_GESTO = {
    "navegacao-interna": "navegar a janela do Hefesto com o controle não tem "
                         "método no daemon — nenhum dos 39, e o "
                         "`core/disputa_de_botao.py` que as sprints citam não "
                         "existe no disco",
    "modo-steam": "não há método de Modo Steam no daemon — nenhum dos 39",
    # OS QUATRO DE VELOCIDADE SAÍRAM DAQUI porque saíram da TELA — 01/09/2026,
    # decisão dela ao ler a medição: *"só ajustar o texto e deixar rolagem,
    # ajustar ali pra deixar um só se for o caso pra ambos"*.
    #
    # O que estava escrito aqui era: o cursor do touchpad sai do MESMO
    # `mouse_speed` (`uinput_mouse.py:446`), e rolagem por dois dedos não existe
    # (`_emit_scroll` lê só o analógico direito). As duas linhas do desenho
    # ofereciam DOIS números onde o produto tem UM — e a cura foi no desenho, não
    # num gesto que fingisse o segundo. As dicas passaram a ler a faixa do
    # produto, que também estava errada nas duas ("De 1 a 10", quando o cursor
    # vai a 12 e a rolagem a 5).
    # FATO SUBSTITUÍDO (segunda leva): dizia "os cinco combos moram em
    # `key_bindings` do perfil". Não moram — `key_bindings` são os nove BOTÕES
    # do `DEFAULT_BUTTON_BINDINGS`, e combo nenhum aparece lá.
    # FATO AFINADO (terceira leva, 01/09/2026): esta entrada dizia que "método
    # de IPC nenhum escreve" o `ps_button_action`. Escreve — `daemon.reload`
    # aceita `config_overrides` com qualquer campo do `DaemonConfig`
    # (`ipc_handlers.py:5450`). O que ele NÃO faz é gravar: o handler roda
    # `replace(config, **overrides)` e `reload_config(...)` e para aí
    # (`:5462-5463`), então a escolha morre no próximo start do daemon. E o
    # `ps_button_action` é do PS SOLO, não dos combos — a tabela desta tela é dos
    # cinco COMBOS.
    #
    # ENDEREÇOS REMEDIDOS EM 06/09/2026: eram `:4556` e `:4567`, que hoje são o
    # cache de órfãos HID. Medidos com `grep -n` no HEAD desta árvore, nunca
    # copiados de relatório.
    "acao-do-gesto": "os cinco combos são callbacks montados em código "
                     "(`daemon/subsystems/hotkey.py:86,414`), não dado. O "
                     "vizinho deles, o `config.ps_button_action` do PS solo, "
                     "tem escritor VIVO (`daemon.reload` com `config_overrides`) "
                     "e nenhum que grave em disco — e ele nem é o que esta "
                     "tabela oferece trocar",
    "padrao-da-aba": "a frase do botão promete a aba INTEIRA — as opções de "
                     "ativação, os 5 gestos e as 22 linhas das duas telas. Só as "
                     "duas velocidades têm rota (`mouse.emulation.set` "
                     "speed-only); as outras três promessas não têm nenhuma, e "
                     "um 'Voltar ao padrão' que devolve dois números de cinco "
                     "coisas é um botão que responde calado sobre as outras três",
    # `guardar-definicoes` SAIU DAQUI em 01/09/2026, e não porque a medição
    # estivesse errada: ela estava certa. A tela deixava escolher 21 linhas e o
    # perfil alcançava 9, e guardar 9 de 21 caladas seria o botão que responde
    # calado. O que mudou foi o PRODUTO — decisão dela ao ler a medição:
    # *"ganha campo. essa é a parte das features que precisam ou serem ajustadas
    # ou desenvolvidas."* `Profile.button_actions` nasceu, o
    # `core/acoes_de_botao` virou o dono do vocabulário e do padrão, e o device
    # de mouse passou a obedecer.
    #
    # O QUE AINDA NÃO PousA está DITO, não engolido: os três comandos
    # ("Abrir a Steam", "Sair do modo jogo", "Escolher um programa…"), os dois
    # papéis de eixo pedidos a um botão, e os gatilhos L2/R2, que são espelho do
    # cross e do triangle. O gesto grava o resto e LEVANTA nomeando esses.
    "guardar-remapeamento": "o remapeamento botão-por-botão não tem sequer campo "
                            "no perfil, quanto mais método de IPC",
    "padrao-remapeamento": "idem, ao contrário",
    "guardar-ponto": "'Estilo de Jogo' não existe em campo, widget ou preset "
                     "nenhum do produto — está escrito em "
                     "`app/actions/perfis_web.py`, que já mediu isto para a aba "
                     "Perfis. O `point_and_click` que existe é um PERFIL em "
                     "disco, não um estilo, e gravar perfil não tem método",
}


#: OS DOIS QUE GRAVAM PERFIL E NÃO TÊM ECO — 02/09/2026, à tarde, medido com
#: dublê da ponte e dublê do disco (`--prova-no-aparelho` NÃO foi usado: há
#: controles na mesa dela e a leva inteira está proibida de tocar o aparelho).
#:
#: O `state_full` do daemon publica `active_profile` — o NOME — e mais nada do
#: conteúdo do perfil. Nem `button_actions` nem `key_bindings` aparecem entre as
#: chaves do payload (`daemon/ipc_handlers.py:2493`). Logo a régua que compara o
#: estado do daemon antes e depois do clique não tem como ver o efeito destes
#: dois, por mais que eles funcionem — e eles funcionam:
#:
#:     gesto                               desfecho          chamou      gravou
#:     guardar-definicoes (linha trocada)  ACEITOU           switch      1 perfil
#:     guardar-definicoes (forma de fábr.) RECUSA dizendo    NADA        0
#:     guardar-definicoes (= ao perfil)    RECUSA dizendo    NADA        0
#:     padrao-definicoes                   ACEITOU           switch      1 perfil
#:     padrao-definicoes (já de fábrica)   RECUSA dizendo    NADA        0
#:
#: A PROVA DELES É O ARQUIVO — mesma forma do `teto-da-vibracao` da aba Conexões
#: (`a08_conexoes.SEM_ECO`), que também grava no perfil: efeito vivo pelo
#: `profile.switch` do `gravar_e_reaplicar`, e nenhum eco. Quem cobra são
#: `test_a_06_nao_manda_para_o_vazio.py` e
#: `test_o_padrao_dos_atalhos_volta_de_fabrica.py`, contra o disco.
#:
#: FATO SUBSTITUÍDO — 02/09/2026, corretivo. Aqui estava escrito que *"a última
#: linha da tabela é o que os pôs aqui"*: `padrao-definicoes` com o perfil já de
#: fábrica saindo pelo `return` de "nada a fazer", sem gravar, sem chamar e sem
#: levantar. **Isso caducou porque o `return` mudo morreu** — os dois ramos de
#: "nada a fazer" (aqui e no `guardar-definicoes`) passaram a RECUSAR DIZENDO, e
#: `recusou dizendo` vem ANTES de `aceito sem eco` na ordem de `classe()`
#: (`hefesto_vivo.py:1492`). Logo esta declaração NÃO cobre mais o caso do
#: não-fazer-nada calado: ele voltou a ser visível para a régua do aparelho, com
#: nome próprio. O que `SEM_ECO` cobre é só o que está escrito acima — o daemon
#: não publica conteúdo de perfil, e o efeito das linhas "ACEITOU" mora no disco.
#:
#: O `teclado` NÃO ENTRA, e a diferença é medida: ele chama
#: `keyboard.emulation.set`, e `keyboard_emulation.enabled` VOLTA no
#: `state_full` — é o que pinta o `teclado-estado`. Declará-lo aqui calaria a
#: régua sobre um caminho que ela consegue medir.
#:
#: OS DOIS QUE NÃO TÊM ASSUNTO NENHUM NO DAEMON — 02/09/2026, e eles são de
#: outra espécie que os dois acima. `linha-de-botao` e `fechar-definicoes` não
#: chamam a ponte, não escrevem em disco e não pretendem: os dois mexem no que a
#: PINTURA vai fazer no tique seguinte, e nada mais. Não é "o daemon não publica
#: este assunto" — é "não há assunto do daemon", que é mais forte.
#:
#: SEM ESTA LINHA a régua do aparelho os leria como *"disse aplicado e nada
#: mudou"* (`hefesto_vivo.py:3721`), que é o rótulo dos botões que mentem — e
#: aqui seria a régua acusando o comportamento CERTO. Declará-los sem prova
#: seria o inverso: lápide escondendo defeito. A prova deles não é o estado do
#: daemon, é o efeito na pintura, e ela roda no CI, sem janela:
#: `test_a_06_a_escolha_dela_sobrevive_ao_tique.py`, que arranca a trava e vê a
#: tabela voltar a desfazer a escolha em um tique.
#:
#: TUPLA, e não dicionário: o piloto faz `set(getattr(mod, "SEM_ECO", ()))` e as
#: seis abas que declaram usam tupla. O motivo mora no comentário, que é onde
#: ele cabe inteiro — `SEM_ECO` sem razão escrita é lápide para esconder defeito.
SEM_ECO = ("guardar-definicoes", "padrao-definicoes",
           "linha-de-botao", "fechar-definicoes")


PONTE = {"chamar"}
METODOS = {"mouse.emulation.set", "keyboard.emulation.set"}


PAGINA = "06-navegacao.html"
PISO_DA_ABA = 8


def _prova(nome: str, clique: dict[str, Any], chama: list[Any]) -> dict[str, Any]:
    """Uma linha do `PROVAS`, para a chave da régua ser escrita UMA vez.

    Cinco dicionários escritos por extenso repetiam a chave da página cinco
    vezes — e cada repetição custava um marcador `# (noqa-acento)` (a chave é do
    contrato da régua, não texto em português) e um aviso do ruff sobre ele. Um
    construtor paga o preço uma vez só.
    """
    # A primeira chave é o NOME do contrato da régua, não texto em português —
    # por isso a linha leva o marcador de isenção, e uma vez só. (Escrever a
    # palavra AQUI, no comentário, também acusava: a régua de acentuação não
    # distingue prosa de identificador nem quando o identificador é o assunto.)
    return {"pagina": PAGINA, "gesto": nome,  # (noqa-acento) chave do contrato
            "clique": clique, "chama": chama}


#: O `ctx` da régua não tem `mouse_emulation`, e é de propósito: o gesto que
#: depende do estado — o interruptor — tem de partir do mesmo chão que a tela
#: mostra enquanto o daemon ainda não falou.
#:
#: AS DUAS VELOCIDADES MANDAM O NÚMERO QUE A BARRA DEU, e não um passo — as
#: quatro provas de `-`/`+` saíram em 05/09/2026 com os botões (decisão dela,
#: *"velocidade do cursor e da rolagem coloca um slicer pra cada"*). O `clique`
#: leva `valor` porque é ele que o piloto manda de um `<input type=range>`
#: (`data-hef-alvo="valor"`), e as duas provas de EXTREMO são as que mordem: a
#: barra do cursor manda `99` e o pacote apara em `MOUSE_SPEED_MAX`; a da
#: rolagem manda `0` e ele apara em `SCROLL_SPEED_MIN`. A faixa continua com um
#: dono só — as constantes são IMPORTADAS de `integrations/uinput_mouse.py:78-79`,
#: não digitadas, e o daemon continua aparando por último.
#:
#: AS CHAMADAS VIRARAM `resultado` — 03/09/2026, e é o que faz a recusa do daemon
#: chegar à tela: `chamar` devolve `bool` e joga fora o corpo com o `bloqueio`.
_MOUSE = "mouse.emulation.set"
PROVAS = [
    _prova("modo", {},
           [("resultado", [_MOUSE], {"enabled": True, "origin": "manual"}),
            ("resultado", ["keyboard.emulation.set"], {"enabled": True})]),
    _prova("vel-cursor", {"valor": "9"},
           [("resultado", [_MOUSE], {"speed": 9, "origin": "manual"})]),
    _prova("vel-cursor", {"valor": "99"},
           [("resultado", [_MOUSE],
             {"speed": MOUSE_SPEED_MAX, "origin": "manual"})]),
    _prova("vel-rolagem", {"valor": "4"},
           [("resultado", [_MOUSE], {"scroll_speed": 4, "origin": "manual"})]),
    _prova("vel-rolagem", {"valor": "0"},
           [("resultado", [_MOUSE],
             {"scroll_speed": SCROLL_SPEED_MIN, "origin": "manual"})]),
    # AS DUAS PONTAS DA LISTA DO TECLADO, e as duas provam a mesma coisa por
    # lados opostos: que o `valor` do `<select>` decide o bool. O `clique` traz
    # `valor` porque é ele que o piloto manda desde 01/09 — `texto`, num
    # `<select>`, é a lista inteira concatenada, e foi essa confusão que deixou
    # esta lista sem dono na primeira leva.
    #
    # A OPÇÃO SEM DONO NÃO TEM PROVA AQUI de propósito: `PROVAS` só sabe cobrar
    # chamada, e o certo para "Só dentro do jogo" é NÃO chamar nada. Ela é
    # provada pela mordida, no relato, e pelo teste da recusa.
    _prova("teclado", {"valor": TECLADO_SO_FORA},
           [("resultado", ["keyboard.emulation.set"], {"enabled": True})]),
    _prova("teclado", {"valor": TECLADO_DESATIVADO},
           [("resultado", ["keyboard.emulation.set"], {"enabled": False})]),
]
