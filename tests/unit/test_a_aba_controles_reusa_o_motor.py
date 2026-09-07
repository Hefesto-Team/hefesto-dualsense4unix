#!/usr/bin/env python3
"""A RÉGUA DO REUSO NA ABA CONTROLES — e das três regras que ela reescrevia errado.

POR QUE ELA EXISTE. LEI 0 da migração, palavra dela em 02/09/2026:

    *"no gtk eu já deixei praticamente tudo pronto, estamos adaptando e migrando
    o que fizemos na versão estável pra ela funcionar no html. Não temos que
    recriar nada."*

`app/widgets/controller_card.py` tem **26 funções públicas de módulo** — 5.951
linhas de texto de tela que a GTK já provou. Medido em 02/09/2026, a interface
nova alcançava DUAS (`rotulo_lightbar`, pela aba Iluminação, e
`texto_degradacao`, pelo `pacotes/__init__.py`), e **esta aba, a mais servida
das dez, chamava ZERO**. Ela reescrevia à mão o que o motor já sabia — e três
das reescritas estavam ERRADAS.

O QUE CADA UMA CUSTAVA, medido com os DOIS controles dela na mesa (um `usb`, um
`bt`) em 02/09/2026 às 16h:

1. **"102%"**. `speaker.volume` é o registrador do protocolo, **0-255**
   (`ipc_handlers.py:3584`), e a aba EMITIA o número CRU com um `%` colado. O
   valor vivo era 102, e o pacote emitia uma porcentagem acima de cem; no talo
   ele emitiria "255%". E a conta certa não é `bruto / 255`: `core/speaker_scale.py`
   existe por causa da curva MEDIDA no hardware — abaixo de 38 tudo é mudo,
   acima de 102 tudo é o mesmo volume.
   **EMITIA, e não MOSTRAVA** (medido em 02/09/2026, contra a primeira redação
   deste arquivo): o `alto-estado` é `hidden` na página publicada e o `escrever`
   do piloto não toca esse atributo — o número ia para um vão invisível. O
   defeito é real e latente; dizer que chegou aos olhos dela é a afirmação
   forte que esta casa cobra prova.
2. **"0%" sobre um alto-falante que ninguém mediu.** `sp.get('volume', 0)`
   transformava AUSÊNCIA em zero. O daemon só publica `speaker` depois do
   primeiro `speaker.set` (`ipc_handlers.py:4600`).
3. **`#000000` sobre uma cor desconhecida.** O motor diz por que é mentira, com
   todas as letras: *"o 0,0,0 do sysfs sem escrita nossa pode ser o azul-kernel
   brilhando neste exato momento"* (`controller_card.rotulo_lightbar`).
4. **um ramo inteiro que só sabia devolver `—`.** A máscara caía em
   `NOME_DA_MASCARA.get(vpad_backend, "—")`, e `NOME_DA_MASCARA` é indexada por
   MÁSCARA (`dualsense`, `xbox`) enquanto `vpad_backend` vale `uhid`/`uinput`/
   `None`. Um `.get` com padrão não estoura, e por isso o defeito era mudo.
5. **uma leitura cega à segunda posição do bloco.** `speaker_do_entry` aceita
   `entry["speaker"]` **e** `entry["inputs"]["speaker"]` porque *"quem publica é
   o daemon, e o widget não pode quebrar por causa de onde o dado mora"*. Este
   arquivo lia só a primeira, em TRÊS lugares — a pintura, o gesto do ♪ e o
   `_volume_conhecido`.

A MORDIDA de cada caso está escrita no teste que a cobra.

O QUE ESTA RÉGUA **NÃO** MEDE, e é declarado para não virar verde por vacuidade:
ela não mede TEXTO de código. A auditoria do selo do microfone (02/09/2026)
mostrou o preço de medir fonte com `inspect.getsource`: *"trocar `mic_sabemos`
por `True` deixa o controle caído voltando a pintar ATIVO com a régua VERDE"*.
A asserção estrutural é de IDENTIDADE de objeto
(`a02.speaker_do_entry is controller_card.speaker_do_entry`) — reimplementar a
função localmente quebra a identidade, e nenhuma reescrita de comentário a
afeta. **Ela cobre os CINCO nomes desde 02/09/2026**: cobria dois, e a
auditoria mediu o buraco — clonar `texto_volume` dentro do pacote passava nos
15 testes e no `ruff`.
"""
from __future__ import annotations

import pathlib
import re
import sys
from typing import Any

import pytest

RAIZ = pathlib.Path(__file__).resolve().parents[2]
sys.path.insert(0, str(RAIZ / "src/hefesto_dualsense4unix/interface"))

#: MAC da faixa sintética da casa — há dois portões de anonimato nesta árvore.
UNIQ = "aa:bb:cc:00:00:01"

#: O REGISTRADOR VIVO DA MESA DELA em 02/09/2026, 16h: `speaker.volume` = 102
#: nos dois controles. É o número que o pacote emitia como "102%".
VOLUME_VIVO = 102


@pytest.fixture(scope="module")
def pac():
    import pacotes

    return pacotes


@pytest.fixture(scope="module")
def a02():
    from pacotes import a02_controles

    return a02_controles


@pytest.fixture(scope="module")
def motor():
    from hefesto_dualsense4unix.app.widgets import controller_card

    return controller_card


class PonteDeMentira:
    """Dublê da `pacotes/ponte.py` que guarda o que foi chamado.

    Mesma forma do dublê de `test_os_botoes_tem_dono.py`: `__getattr__` responde
    por qualquer nome, de propósito, para não virar uma segunda lista das
    funções da ponte.
    """

    def __init__(self) -> None:
        self.chamadas: list[tuple[str, tuple, dict]] = []

    def __getattr__(self, nome: str):
        def registrar(*args: Any, **kwargs: Any):
            self.chamadas.append((nome, args, kwargs))
            return (True, None) if nome.endswith("_set") and "identity" in nome else True

        return registrar


def _card(pac, a02, entrada: dict, state: dict | None = None) -> dict:
    """O dicionário de UM card, do pacote real, sem janela e sem daemon."""
    ctx = pac.Contexto(state=state or {}, mesa=[], conectados=[entrada], estados={})
    return next(iter(a02.pacote(ctx)["cards"].values()))


#: O controle da régua. Sem `speaker` e sem `lightbar_*` de propósito: cada
#: teste monta o que a sua pergunta precisa, em vez de herdar um estado que
#: ninguém leu.
BASE: dict[str, Any] = {
    "uniq": UNIQ, "player": 1, "connected": True, "transport": "usb",
    "battery_pct": 95, "is_primary": True, "inputs": {}, "audio": {},
}


# ---------------------------------------------------------------------------
# O ENDEREÇO MUDOU EM 04/09/2026, e esta régua mudou com ele.
#
# O `alto-estado` era um `<span class="mudo" data-campo="alto-estado" hidden>` —
# valor vivo, escrito a cada tique, dentro de um vão que o piloto NUNCA
# desesconde. Foi assim que o "102%" viveu meses sem ninguém ver, e é a decisão
# [09] dela (*"onde a tela mostra que o alto-falante está mudo?"*).
#
# O vão saiu do desenho e a informação virou DOIS campos, cada um no lugar em
# que ela olha:
#
#     alto-num    o número, pela curva medida  (102 -> 100, 255 -> 100)
#     alto-mudo   a palavra, do MESMO dono que o selo do microfone usa
#                 (`mesa_viva.selo_do_mic`): MUDO / ATIVO / travessão
#
# O `alto-estado` some sozinho do pacote quando a página publicada deixa de
# tê-lo (`_so_se_a_pagina_tiver`) — foi o que aconteceu ao publicar a aba 02.
# **O que esta régua cobra não mudou:** a curva medida, o talo que não vira
# 255%, o mudo que vence a porcentagem, e a ausência que não vira zero.
# ---------------------------------------------------------------------------


# --------------------------------------------------------------------------
# 1. O VOLUME — o registrador cru com um sinal de porcentagem
# --------------------------------------------------------------------------
def test_o_volume_nao_e_o_registrador_cru_com_por_cento(pac, a02):
    """102 no registrador é **100 %** no campo, e nunca "102%".

    O rótulo é o do produto (`sensor_widgets.texto_volume`), que passa pela
    curva medida de `core/speaker_scale.py`. Os dois lados são cobrados: o que
    a tela TEM de dizer e o que ela NÃO pode dizer.

    MORDE: devolver `f"{sp.get('volume', 0)}%"` a esta linha reprova aqui com
    `'102%' != '100 %'` — que é exatamente o que o pacote emitia com a
    mesa dela cheia.
    """
    d = _card(pac, a02, {**BASE, "speaker": {"volume": VOLUME_VIVO, "muted": False}})
    assert d["alto-num"] == 100
    assert d["alto-num"] != VOLUME_VIVO, (
        "a tela escreveu o registrador cru do protocolo como se fosse por cento")


def test_o_talo_do_registrador_nao_vira_duzentos_e_cinquenta_e_cinco_por_cento(pac, a02):
    """255 é o talo da escala do protocolo, e o talo da tela é 100 %.

    MORDE: qualquer conta linear (`volume * 100 // 255`) devolve 100 aqui e
    passa — por isso o caso do 128 vem junto: ele SOA igual ao 255 (a curva
    satura em 102), e a linear diria "50 %" sobre o volume máximo. É o defeito
    nomeado em `core/speaker_scale.fracao_do_volume`.
    """
    talo = _card(pac, a02, {**BASE, "speaker": {"volume": 255, "muted": False}})
    meio = _card(pac, a02, {**BASE, "speaker": {"volume": 128, "muted": False}})
    assert talo["alto-num"] == 100
    assert meio["alto-num"] == 100, (
        "128 soa igual a 255 no alto-falante do DualSense (curva medida em "
        "01/08/2026) — uma conta linear diria 50 % sobre o volume máximo")


def test_o_mudo_vence_a_porcentagem(pac, a02):
    """Calado, o campo diz "Mudo" — a régua não pode virar "sempre por cento".

    MORDE: trocar `texto_volume(*sp_lido)` por `f"{percentual}...%"` reprova
    aqui, porque a palavra some.
    """
    d = _card(pac, a02, {**BASE, "speaker": {"volume": VOLUME_VIVO, "muted": True}})
    assert d["alto-mudo"] == "MUDO"
    aceso = _card(pac, a02, {**BASE, "speaker": {"volume": VOLUME_VIVO, "muted": False}})
    assert aceso["alto-mudo"] == "ATIVO", (
        "sem o par, a régua passaria com um campo que diz MUDO para sempre")


def test_sem_alto_falante_a_tela_nao_diz_zero(pac, a02):
    """Ausência não é zero. O daemon só publica `speaker` depois do primeiro set.

    MORDE: devolver o `sp.get('volume', 0)` faz este teste reprovar com
    `'0%' != '—'` — a tela afirmando "o volume está no mínimo" sobre um
    alto-falante que ninguém mediu. É o gêmeo exato do "Sem toque" que a régua
    do analógico já trancou.
    """
    import mesa_viva

    d = _card(pac, a02, BASE)
    assert d["alto-num"] == mesa_viva.SEM_LEITOR
    assert d["alto-mudo"] == mesa_viva.SEM_LEITOR
    assert "0" not in str(d["alto-num"])


def test_o_bloco_do_alto_falante_e_lido_nas_duas_posicoes(pac, a02):
    """`inputs.speaker` vale tanto quanto `entry.speaker` — o motor aceita as duas.

    A razão é do daemon, e está escrita em `controller_card.speaker_do_entry`:
    *"quem publica é o daemon, e o widget não pode quebrar por causa de onde o
    dado mora"*. Medido na mesa dela em 02/09/2026, o daemon publica nas DUAS;
    esta régua tranca o dia em que ele publicar só na de dentro.

    MORDE: voltar a `c.get("speaker") or {}` reprova aqui com `'—'`, e o
    defeito seria INVISÍVEL enquanto o daemon mandasse as duas.
    """
    dentro = {k: v for k, v in BASE.items() if k != "speaker"}
    dentro["inputs"] = {"speaker": {"volume": 60, "muted": False}}
    assert _card(pac, a02, dentro)["alto-num"] == 34


# --------------------------------------------------------------------------
# 2. O GESTO DO ♪ — a mesma leitura, do outro lado do clique
# --------------------------------------------------------------------------
def test_o_mudo_do_alto_falante_le_a_segunda_posicao(pac, a02):
    """Clicar no ♪ com o volume só em `inputs.speaker` manda o volume junto.

    O daemon RECUSA `speaker.set {muted}` sem volume conhecido de propósito
    (`ipc_handlers.py:4682`): calar como primeira escrita tranca o alto-falante
    em zero e o próprio mudo não o solta. Com a leitura cega à segunda posição,
    o botão mandava o pedido SEM volume — e o daemon o recusava sobre um volume
    que estava no payload, duas chaves ao lado.

    MORDE: devolver `(dele.get("speaker") or {}).get("volume")` ao
    `_volume_conhecido` reprova aqui — o `volume` some do payload.
    """
    entrada = {k: v for k, v in BASE.items() if k != "speaker"}
    entrada["inputs"] = {"speaker": {"volume": 60, "muted": True}}
    ctx = pac.Contexto(state={}, mesa=[], conectados=[entrada], estados={})
    p = PonteDeMentira()
    a02.mudo(ctx, {"uniq": UNIQ, "mudo": "alto-falante"}, p)
    assert p.chamadas == [
        ("speaker_set", (), {"muted": False, "uniq": UNIQ, "volume": 60})
    ], "o gesto não leu o bloco que o daemon publicou dentro de `inputs`"


def test_sem_volume_conhecido_o_botao_do_alto_falante_recusa_aqui(pac, a02):
    """Sem volume conhecido o ♪ não manda nada — e diz por quê.

    **ISTO SUBSTITUI UM CONTRATO, e a substituição é a entrega.** O teste
    anterior (`..._o_pedido_vai_sem_volume`) cobrava que o clique CHAMASSE
    `speaker_set(muted=True)` sem volume, e contava com a recusa do
    `ipc_handlers.py:4682` do outro lado do soquete. Recusa de longe é recusa
    que depende do outro lado continuar recusando — e o que está do outro lado
    é o alto-falante dela: `acao_speaker_mudo` diz que o par `muted=True` +
    `muted=False` sem volume *"tranca o alto-falante em `{'volume': 0, 'muted':
    True}` e o próprio botão não tem como soltá-lo (armadilha 2 da SOM-02,
    executada contra o backend real)"*.

    A REGRA É DO MOTOR (`acao_speaker_mudo(...).sensivel`), e é o mesmo estado
    em que a GTK deixa o botão CINZA. A FRASE é desta janela, e a diferença
    está medida: a do motor manda *"use o controle deslizante primeiro"*, e
    aqui não há deslizante — `type="range"` aparece zero vez nas dez páginas.

    MORDE: apagar a guarda faz a chamada voltar, e a asserção de `chamadas ==
    []` reprova.
    """
    ctx = pac.Contexto(state={}, mesa=[], conectados=[BASE], estados={})
    p = PonteDeMentira()
    with pytest.raises(RuntimeError) as erro:
        a02.mudo(ctx, {"uniq": UNIQ, "mudo": "alto-falante"}, p)
    assert p.chamadas == [], "o clique chegou ao daemon com o volume desconhecido"
    assert "volume" in str(erro.value)


def test_com_volume_conhecido_o_pedido_leva_o_numero(pac, a02):
    """A metade que prova que a guarda não é "o botão nunca mais funciona"."""
    dele = {**BASE, "speaker": {"volume": VOLUME_VIVO, "muted": False}}
    ctx = pac.Contexto(state={}, mesa=[], conectados=[dele], estados={})
    p = PonteDeMentira()
    a02.mudo(ctx, {"uniq": UNIQ, "mudo": "alto-falante"}, p)
    assert p.chamadas == [
        ("speaker_set", (), {"muted": True, "uniq": UNIQ, "volume": VOLUME_VIVO})]


def test_sem_leitura_de_audio_o_microfone_nao_chuta(pac, a02):
    """Sem a chave `audio`, o 🎙 recusa DIZENDO em vez de adivinhar o oposto.

    O ESTADO É REAL: o byte de áudio é atributo de INSTÂNCIA do handle, e no
    instante seguinte a um hotplug-out o handle novo ainda não leu um report
    íntegro — `audio` SOME do `state_full`. A linha do gesto fazia
    `bool(None)` → `False` → `mic_set(True)`: o clique CALAVA um microfone que
    ninguém sabia se estava calado.

    A regra é a do motor, palavra por palavra: *"mandar um pedido sem saber o
    estado atual seria chutar qual é o oposto"* (`controller_card.acao_mic`), e
    a frase que sobe à tela é a dele (`DICA_MIC_SEM_LEITURA`).

    MORDE: apagar a guarda faz `chamadas` virar `[("mic_set", (True,), ...)]`.
    """
    from hefesto_dualsense4unix.app.widgets.controller_card import DICA_MIC_SEM_LEITURA

    sem_audio = {k: v for k, v in BASE.items() if k != "audio"}
    ctx = pac.Contexto(state={}, mesa=[], conectados=[sem_audio], estados={})
    p = PonteDeMentira()
    with pytest.raises(RuntimeError) as erro:
        a02.mudo(ctx, {"uniq": UNIQ, "mudo": "microfone"}, p)
    assert p.chamadas == [], "o clique calou um microfone que ninguém mediu"
    assert str(erro.value) == DICA_MIC_SEM_LEITURA


def test_com_leitura_de_audio_o_microfone_continua_alternando(pac, a02):
    """A metade que prova que a guarda não apagou o botão.

    **A FUNÇÃO MUDOU EM 04/09/2026 — S-05, a D-12 dela:** *"o botão é pra ligar
    o microfone e ele ser ouvido no canal específico dele"*. O 🎙 chama o ATO
    inteiro (`mic_canal_set_detalhado`) em vez do mudo do firmware sozinho.

    **O QUE O APARELHO FAZ NÃO MUDOU COM ESTA TROCA**, e é por isso que a
    substituição é segura: `ipc_bridge.mic_set_detalhado` já DELEGAVA ao ato
    desde a ONDA1-D1. O que a variante direta traz é o `status` honesto — o
    embrulho do `mic_set` reescreve `status` para `"ok"` assim que o firmware
    foi pedido, e com isso a metade do CANAL sumia da resposta, que é
    justamente a metade que falha no Modo Nativo e no rádio sem ponte.

    E O ARGUMENTO INVERTEU DE SENTIDO, não de valor: `mic_set` recebia
    `muted=True` (*"cale"*) e o ato recebe `ligado=False`. `mic_mudo` era
    `False` — o microfone está no ar —, então o clique o CALA nos dois
    vocabulários.
    """
    dele = {**BASE, "audio": {"mic_mudo": False}}
    ctx = pac.Contexto(state={}, mesa=[], conectados=[dele], estados={})
    p = PonteDeMentira()
    a02.mudo(ctx, {"uniq": UNIQ, "mudo": "microfone"}, p)
    assert p.chamadas == [("mic_canal_set_detalhado", (False,), {"uniq": UNIQ})]


# --------------------------------------------------------------------------
# 3. A COR DA BARRA — `#000000` sobre o que ninguém mediu
# --------------------------------------------------------------------------
def test_a_cor_de_fonte_desconhecida_nao_vira_preto(pac, a02):
    """`lightbar_source == "desconhecida"` é "não sei", e não "apagada".

    O dono da regra é `controller_card.rotulo_lightbar`, e ele devolve `None`
    como cor-base exatamente aqui. A frase dele: *"NUNCA 'apagada': o 0,0,0 do
    sysfs sem escrita nossa pode ser o azul-kernel brilhando neste exato
    momento"*.

    **A PALAVRA MUDOU EM 04/09/2026 — decisão [02] dela**, e o que esta régua
    mede não: *"palavra curta no lugar do travessão, frase inteira no hover"*.
    Os três "não sei" dividiam um `—` só e diziam coisas diferentes; agora cada
    um tem a sua palavra, e a frase inteira vai no `luz-porque`. O que continua
    valendo, letra por letra, é o que este teste sempre cobrou: **a cor crua
    NÃO aparece**.

    A palavra é PERGUNTADA à tabela, e não digitada — a tabela é asked ao motor
    (`a02.PALAVRA_DA_LUZ`, com as chaves vindas de `rotulo_lightbar`).

    MORDE: voltar ao `"#{:02X}{:02X}{:02X}".format(*rgb[:3])` cru reprova aqui.
    """
    d = _card(pac, a02, {**BASE, "lightbar_rgb": [0, 0, 0],
                         "lightbar_source": "desconhecida"})
    assert d["luz-hex"] == a02.PALAVRA_DA_LUZ[a02.ROTULO_DA_LUZ_DESCONHECIDA]
    assert "000000" not in d["luz-hex"]


def test_a_cor_conhecida_continua_saindo(pac, a02):
    """A metade que prova que a cura não é "nunca mais mostra cor nenhuma".

    MORDE: devolver `mesa_viva.SEM_LEITOR` em todos os casos reprova aqui.
    """
    d = _card(pac, a02, {**BASE, "lightbar_rgb": [0, 0, 255],
                         "lightbar_source": "sysfs", "lightbar_on": True})
    assert d["luz-hex"] == "#0000FF"


def test_a_barra_apagada_nao_diz_nao_sei(pac, a02):
    """Apagada é um FATO, e "não sei" é outra coisa — o campo tem de separá-los.

    ESTA RÉGUA COBRAVA O DEFEITO ATÉ 02/09/2026. Ela dizia *"barra apagada não
    tem código de cor a mostrar — o motor devolve o neutro"* e exigia
    `SEM_LEITOR`; o `None` do motor ali é a base do ACCENT (*"None = usar o
    neutro"*, `controller_card.py:1178`), não a resposta "não sei". Com o mesmo
    travessão que o piloto usa para null (`hefesto_vivo.py:118`), a tela dizia
    "não medi" sobre a única coisa que se mediu.

    **O CAMPO PASSOU A DIZER A PALAVRA — 04/09/2026, decisão [02] dela**, e o
    que esta régua cobra continua sendo o mesmo: apagada e "não sei" são dois
    estados que o motor SEPARA, e a tela tem de separá-los também. Antes o que
    os separava era `#000000` contra `—`; hoje é `Apagada` contra `Não sei`.

    **O `#000000` NÃO SUMIU — ele foi para onde quer dizer alguma coisa.** Uma
    barra sem corrente emite zero nos três canais, e é isso que o RETÂNGULO
    mostra (`luz-cor`, que continua saindo do `luz_hex`). O que mudou é o
    CAMPO, que agora responde à pergunta que a pessoa faz olhando ali — *"por
    que não vejo a cor?"* — em vez de mostrar um código de cor que ela não tem
    como distinguir de uma cor de verdade.

    MORDE: voltar a decidir pela base (`base is not None`) reprova aqui,
    porque o motor devolve `None` como base nos DOIS casos.
    """
    apagada = _card(pac, a02, {**BASE, "lightbar_rgb": [0, 0, 255],
                               "lightbar_source": "sysfs", "lightbar_on": False})
    naosei = _card(pac, a02, {**BASE, "lightbar_rgb": [0, 0, 0],
                              "lightbar_source": "desconhecida"})
    assert apagada["luz-hex"] == a02.PALAVRA_DA_LUZ[a02.ROTULO_DA_LUZ_APAGADA]
    assert apagada["luz-cor"] == a02.HEX_DA_LUZ_APAGADA, (
        "o retângulo deixou de mostrar o preto de uma barra sem corrente — o "
        "fato saiu do campo E do desenho, e aí ele sumiu de vez")
    assert apagada["luz-hex"] != naosei["luz-hex"], (
        "dois estados que o motor SEPARA voltaram a mostrar a mesma coisa")


def test_o_zero_de_uma_barra_desligada_tambem_e_apagada(pac, a02):
    """O outro ramo do "apagada": `rgb == (0,0,0)` com a fonte NOSSA.

    O motor manda os dois para a mesma frase (`controller_card.py:1189`), e a
    tela tem de mandá-los para o mesmo lugar — senão a cura separa três estados
    onde o dono separa dois.

    MORDE: cravar a palavra só no ramo `lightbar_on is False` reprova aqui.
    """
    d = _card(pac, a02, {**BASE, "lightbar_rgb": [0, 0, 0],
                         "lightbar_source": "sysfs", "lightbar_on": True})
    assert d["luz-hex"] == a02.PALAVRA_DA_LUZ[a02.ROTULO_DA_LUZ_APAGADA]
    assert d["luz-cor"] == a02.HEX_DA_LUZ_APAGADA


def test_em_nativo_a_tela_nao_afirma_a_cor_crua(pac, a02):
    """Modo Nativo: o jogo é dono do LED, e o `rgb` que sobra é CRU.

    O RAMO NÃO TINHA UM ÚNICO CASO até 02/09/2026 — os três testes de `luz-hex`
    passavam `state=None`, então `native_mode` era sempre falso, e a cura que
    dizia curar "o `#000000` sobre cor desconhecida" **não alcançava este
    ramo**: medido com sonda, `nativo + fonte desconhecida + rgb 0,0,0` dava
    `#000000` antes e depois dela.

    `rotulo_lightbar` decide `native_mode` PRIMEIRO (`controller_card.py:1182`)
    e devolve o `rgb` CRU — o teste de fonte desconhecida nem é alcançado. A
    GTK mostra essa cor COM a frase que a explica ao lado; aqui a frase não tem
    endereço, e cor sem ressalva é afirmar o que ninguém mediu.

    A PALAVRA É `Jogo` DESDE 04/09/2026 (decisão [02] dela), e ela diz o que o
    travessão calava: quem está com o LED é o JOGO. O que a régua cobra
    continua sendo o mesmo — a cor crua não aparece.

    MORDE: decidir pela base (`base is not None`) reprova aqui com `'#000000'`.
    """
    d = _card(pac, a02, {**BASE, "lightbar_rgb": [0, 0, 0],
                         "lightbar_source": "desconhecida", "lightbar_on": True},
              state={"native_mode": True})
    assert d["luz-hex"] == a02.PALAVRA_DA_LUZ[a02.ROTULO_DA_LUZ_EM_NATIVO]
    assert "000000" not in d["luz-hex"]


def test_com_a_steam_segurando_o_fd_a_tela_nao_afirma_a_cor_crua(pac, a02):
    """`lightbar_disputada`: o segundo ramo que a cura de 02/09 não alcançava.

    O motor explica por que a cor não vale: com a Steam segurando o `fd`, *"o
    que a classe LED devolve é o que o Hefesto PEDIU — a madrugada de 16/08 leu
    `[0 255 0]` com a barra apagada e `[0 255 0]` com ela verde"*.

    A PALAVRA É `Steam` DESDE 04/09/2026 (decisão [02] dela) — e é ela que
    manda a pessoa olhar para o lugar certo, que um travessão não fazia.

    MORDE: decidir pela base reprova aqui com `'#000000'`.
    """
    d = _card(pac, a02, {**BASE, "lightbar_rgb": [0, 0, 0],
                         "lightbar_source": "desconhecida", "lightbar_on": True,
                         "lightbar_disputada": True})
    assert d["luz-hex"] == a02.PALAVRA_DA_LUZ[a02.ROTULO_DA_LUZ_SEGURADA]


def test_o_rotulo_da_apagada_e_perguntado_ao_motor(a02, motor):
    """A frase da barra apagada não é digitada nesta aba — ela é PERGUNTADA.

    Das quatro frases de `rotulo_lightbar`, só `ROTULO_LIGHTBAR_SEGURADA` é
    constante exportada. Digitar as outras aqui seria a cópia muda que a LEI 0
    proíbe: no dia em que o motor trocasse o texto, a aba voltaria a colapsar
    "apagada" e "não sei" com a régua verde.

    ESTE TESTE É O QUE TRANCA A PERGUNTA. Ele cobra que a resposta seja uma
    frase de verdade e que ela seja DIFERENTE das outras três — se a ordem dos
    ramos do motor mudar e a sondagem cair no ramo errado, a igualdade acusa.

    MORDE: digitar `ROTULO_DA_LUZ_APAGADA = "Lightbar: apagada"` continua
    passando (a string é a mesma nos dois mundos) — quem pega essa é o dia em
    que o motor mudar. O que ESTE teste pega é a sondagem cair no ramo errado,
    e a mordida é trocar o `lightbar_on` da sondagem para `True`: a resposta
    vira `None` e a primeira asserção reprova.
    """
    naosei = motor.rotulo_lightbar({"lightbar_source": "desconhecida"}, {})[0]
    nativo = motor.rotulo_lightbar({}, {"native_mode": True})[0]
    acesa = motor.rotulo_lightbar(
        {"lightbar_rgb": [0, 0, 255], "lightbar_source": "sysfs",
         "lightbar_on": True}, {})[0]

    assert isinstance(a02.ROTULO_DA_LUZ_APAGADA, str) and a02.ROTULO_DA_LUZ_APAGADA
    assert acesa is None, "o ramo da cor conhecida deixou de ser o sem-rótulo"
    for outro in (naosei, nativo, motor.ROTULO_LIGHTBAR_SEGURADA):
        assert outro != a02.ROTULO_DA_LUZ_APAGADA, (
            f"a sondagem da barra apagada caiu no ramo de {outro!r}")


# --------------------------------------------------------------------------
# 4. A MÁSCARA — o ramo que só sabia devolver travessão
# --------------------------------------------------------------------------
def test_o_backend_uhid_diz_dualsense(pac, a02):
    """`uhid` implica máscara DualSense, e a regra é do produto.

    `virtual_pad._try_uhid` recusa o uhid para saída Xbox — *"Xbox não é
    trabalho do uhid"*, o `hid_playstation` só faz bind em produto Sony —, e é
    por isso que `home_actions.mascara_viva` pode afirmar a máscara a partir do
    backend. A aba não podia: ela procurava `uhid` numa tabela cujas chaves são
    `dualsense` e `xbox`, e o `.get` com padrão devolvia `—` calado.

    MORDE: devolver `NOME_DA_MASCARA.get(c.get("vpad_backend") or "", "—")`
    reprova aqui com `'—' != 'DualSense'`.
    """
    d = _card(pac, a02, {**BASE, "vpad_backend": "uhid"})
    assert d["mascara"] == "DualSense"


def test_o_backend_uinput_e_ambiguo_e_diz_nao_sei(pac, a02):
    """`uinput` é Xbox normal OU DualSense degradado — dizer "não sei" é honesto.

    MORDE: mapear `uinput` para qualquer nome de máscara reprova aqui. A régua
    existe porque a cura ÓBVIA do teste acima é um segundo dicionário
    `{"uhid": "DualSense", "uinput": "Xbox 360"}`, e ele estaria ERRADO — é a
    afirmação que `mascara_viva` se recusa a fazer.
    """
    assert _card(pac, a02, {**BASE, "vpad_backend": "uinput"})["mascara"] == "—"
    assert _card(pac, a02, {**BASE, "vpad_backend": None})["mascara"] == "—"


# --------------------------------------------------------------------------
# 5. O TOQUE — um dono só, e ele é o do produto
# --------------------------------------------------------------------------
#: O bloco `touchpad` COMO O DAEMON O PUBLICA. As cinco chaves saem de UM
#: literal em `daemon/sensor_hub.py:155-161` — não há caminho no código que
#: escreva `touching` sem escrever `x`. Medido em 02/09/2026, 60 leituras de
#: `daemon.state_full` com os dois controles dela na mesa: 36 blocos, todos com
#: `height,touching,width,x,y`.
TOUCHPAD_COMO_O_DAEMON_PUBLICA = {
    "touching": False, "x": 960, "y": 540, "width": 1920, "height": 1080,
}


def test_inputs_com_leitura_e_sem_touchpad_nao_e_sem_toque(pac, a02):
    """Ler os botões e não ler o touchpad é "não sei", não "ninguém encostou".

    Este estado o daemon PUBLICA, e com frequência: o reader do touchpad nasce
    sob demanda (`sensor_hub.leitura:113`), então nas primeiras leituras depois
    de o `state_full` ser pedido a chave ainda não existe — 24 das 60 amostras
    de 02/09/2026.

    MORDE: voltar ao `e.get("touchpad") or {}` reprova aqui com `'Sem toque'`.
    """
    import mesa_viva

    d = _card(pac, a02, {**BASE, "inputs": {"buttons": ["cross"]}})
    assert d["touch-estado"] == mesa_viva.SEM_LEITOR


def test_a_palavra_do_touchpad_e_a_do_produto(pac, a02):
    """`Sem toque` / `1 toque` — a conta é a MESMA linha que a GTK escreve.

    DECISÃO DELA, 02/09/2026 (item 15): *"o touchpad usa a palavra do produto:
    '1 toque', '2 toques', 'Sem toque', que é o que o motor já conta"*. A GTK
    faz `texto_toques(1 if tocando else 0)` (`controller_card.py:5079`), e é
    isso que esta aba passou a fazer — no lugar do `COM_TOQUE = "Tocando"`, que
    era palavra do DESENHO redigitada no pacote.

    "2 TOQUES" NÃO APARECE, e a razão é de DADO: o `state_full` publica
    `touchpad.touching`, um booleano, e não uma contagem de dedos. No dia em
    que ele publicar o segundo, a palavra sai do motor sem ninguém tocar aqui.

    MORDE: redigitar `"Tocando"` no pacote reprova nas duas linhas.
    """
    from hefesto_dualsense4unix.app.widgets.sensor_widgets import texto_toques

    solto = _card(pac, a02, {**BASE, "inputs": {
        "touchpad": TOUCHPAD_COMO_O_DAEMON_PUBLICA}})
    tocando = _card(pac, a02, {**BASE, "inputs": {
        "touchpad": {**TOUCHPAD_COMO_O_DAEMON_PUBLICA, "touching": True}}})
    assert solto["touch-estado"] == texto_toques(0) == "Sem toque"
    assert tocando["touch-estado"] == texto_toques(1) == "1 toque"


def test_o_bloco_que_a_recusa_protegia_o_daemon_nao_publica():
    """A recusa de `touchpad_do_inputs` era sobre um estado que não existe.

    O QUE ESTAVA ESCRITO NO PACOTE, e caiu: *"ele exige `bloco['x']` e
    `bloco['y']`: um bloco com `{"touching": True}` e sem coordenada cai no
    `except KeyError` e volta `None`"*. É verdade sobre a função e falso sobre
    o produto — quem monta a chave é `daemon/sensor_hub.py`, num literal com as
    CINCO chaves juntas.

    ESTA RÉGUA MEDE O DAEMON, e não o pacote: ela lê o fonte do dono da chave e
    exige que as cinco nasçam no mesmo dicionário. Se alguém partir aquele
    literal em dois — que é o único jeito de o estado passar a existir —, ela
    reprova e manda reabrir a discussão, em vez de deixar a tela dizer "não
    sei" sobre um dedo que o daemon está vendo.

    MORDE: apagar `"x"` do literal do `sensor_hub` reprova aqui.
    """
    import inspect

    from hefesto_dualsense4unix.daemon import sensor_hub

    fonte = inspect.getsource(sensor_hub.SensorHub.leitura)
    bloco = fonte.split('out["touchpad"] = {', 1)[1].split("}", 1)[0]
    faltando = [c for c in ("touching", "x", "y", "width", "height")
                if f'"{c}":' not in bloco]
    assert not faltando, (
        f"o `sensor_hub` deixou de publicar {faltando} junto com as outras — o "
        f"estado que a recusa de `touchpad_do_inputs` protegia passou a existir")


def test_o_pontinho_so_acende_com_toque(a02):
    """Decisão dela (item 15): o ponto só aparece quando há toque.

    Fotografado em 02/09/2026 às 19h, antes desta cura: `touch-estado` dizia
    **Sem toque** e o pontinho ciano estava ACESO no card do P1, parado em
    `left:62%;top:44%` — o desenho contradizendo o campo ao lado dele, na mesma
    moldura. **A régua do mockup é cega a isso**: ela conta `data-campo`, e o
    ponto não tinha nenhum. `02-controles` dava `23 campos · 23 PRODUTO · 0
    MOCKUP` com o ponto mentindo.

    O VALOR É LIDO PELO ALVO `classe` do piloto, e o vocabulário dele é o
    `ligado()` do BOOTSTRAP: `''` e `'—'` apagam, o resto acende.

    MORDE: mandar `"sim"` sempre (ou voltar o `style` do gerador) reprova nas
    duas primeiras linhas.
    """
    solto = a02.toque_do_controle({"touchpad": TOUCHPAD_COMO_O_DAEMON_PUBLICA})[1]
    tocando = a02.toque_do_controle(
        {"touchpad": {**TOUCHPAD_COMO_O_DAEMON_PUBLICA, "touching": True}})[1]
    sem_leitor = a02.toque_do_controle({})[1]
    assert solto == "", "o ponto fica aceso com o dedo fora do pad"
    assert tocando, "o ponto não acende com o dedo no pad"
    assert sem_leitor == "", "o ponto acende sem leitura nenhuma"


def test_o_rotulo_do_sem_toque_nao_e_digitado_aqui(a02):
    """"Sem toque" tem UM dono, e é `sensor_widgets.texto_toques`.

    A constante desta aba já dizia, em comentário, que a palavra era "a do
    produto" — e ainda assim era uma segunda cópia das mesmas cinco letras. Um
    comentário não é um dono.

    ESTA RÉGUA NASCEU CEGA E FOI CONSERTADA NA MORDIDA (02/09/2026). A primeira
    versão tinha só a segunda linha, e ela **não mordia**: redigitar
    `SEM_TOQUE = "Sem toque"` continuava passando, porque a igualdade de string
    é verdadeira nos dois mundos. Uma régua que passa com a cura arrancada não
    mede nada — foi a mordida que a pegou, e é por isso que ela é obrigatória.

    A PRIMEIRA LINHA É QUE MORDE, e é de IDENTIDADE: apagar o import e redigitar
    o literal derruba `a02.texto_toques` com `AttributeError`. E se alguém
    apagar só o USO, mantendo o import, quem pega é o `ruff` — `texto_toques`
    não tem outro uso neste arquivo, então ele vira `F401`, e o lint é portão.
    """
    from hefesto_dualsense4unix.app.widgets.sensor_widgets import texto_toques

    assert a02.texto_toques is texto_toques, (
        "a aba deixou de importar o dono da palavra e voltou a digitá-la")
    assert a02.toque_do_controle(
        {"touchpad": TOUCHPAD_COMO_O_DAEMON_PUBLICA})[0] == texto_toques(0)


# --------------------------------------------------------------------------
# 6. A ASSERÇÃO ESTRUTURAL — e ela é de IDENTIDADE, não de texto
# --------------------------------------------------------------------------
def test_a_aba_chama_o_motor_em_vez_de_reescreve_lo(a02, motor):
    """Os nomes do motor estão LIGADOS neste módulo, e são os mesmos objetos.

    POR QUE ISTO NÃO É MEDIR TEXTO: a auditoria do selo do microfone
    (02/09/2026) mostrou o preço de conferir fonte com `inspect.getsource` —
    *"trocar `mic_sabemos` por `True` deixa o controle caído voltando a pintar
    ATIVO com a régua VERDE"*. Identidade de objeto não tem esse buraco:
    reimplementar `speaker_do_entry` dentro deste arquivo faz o `is` falhar, e
    nenhuma reescrita de comentário o afeta.

    ELA PROMETIA CINCO E TRANCAVA DOIS — auditoria de 02/09/2026. O docstring
    dizia *"reprova aqui nomeando qual"* e as asserções eram duas
    (`speaker_do_entry` e `rotulo_lightbar`); `texto_volume` e `mascara_viva`
    ficavam de fora, e são justamente as duas cujo COMPORTAMENTO um clone local
    reproduz de graça. Medido: reescrever `texto_volume` dentro do pacote e
    apagar o import passava nos 15 testes e no `ruff`.

    MORDE: copiar qualquer um dos cinco para dentro do pacote (que é
    exatamente o que a LEI 0 proíbe) reprova aqui nomeando qual.
    """
    from hefesto_dualsense4unix.app.actions.home_actions import mascara_viva
    from hefesto_dualsense4unix.app.widgets.sensor_widgets import (
        texto_toques,
        texto_volume,
    )

    from hefesto_dualsense4unix.core.speaker_scale import percentual_do_volume

    donos = {
        "speaker_do_entry": motor.speaker_do_entry,
        "rotulo_lightbar": motor.rotulo_lightbar,
        "texto_volume": texto_volume,
        "texto_toques": texto_toques,
        "mascara_viva": mascara_viva,
        # OS QUATRO DE 02/09/2026 À NOITE. `touchpad_do_inputs` tinha sido
        # RECUSADO aqui por causa de um bloco que o daemon não publica;
        # `acao_mic` e `acao_speaker_mudo` são as regras dos dois botões de
        # calar, que este arquivo decidia sozinho; `percentual_do_volume` é a
        # curva medida no hardware, e sem ela o número e a barra do volume
        # seriam uma segunda conta ao lado da do `texto_volume`.
        "touchpad_do_inputs": motor.touchpad_do_inputs,
        "acao_mic": motor.acao_mic,
        "acao_speaker_mudo": motor.acao_speaker_mudo,
        "percentual_do_volume": percentual_do_volume,
    }
    reescritos = [
        nome for nome, dono in donos.items() if getattr(a02, nome, None) is not dono
    ]
    assert not reescritos, (
        f"a aba deixou de chamar o motor e reescreveu: {', '.join(reescritos)}")


# --------------------------------------------------------------------------
# 7. OS QUATRO DA BANCADA — endereço novo, emissão CONDICIONAL
# --------------------------------------------------------------------------
def _campos_do_arquivo(caminho: pathlib.Path) -> frozenset[str]:
    """Todo `data-campo` de um HTML — LIDO do arquivo, nunca digitado aqui."""
    return frozenset(
        re.findall(r'data-campo="([^"]+)"', caminho.read_text(encoding="utf-8")))


BANCADA = RAIZ / "mockup/02-controles.html"
PUBLICADA = RAIZ / "src/hefesto_dualsense4unix/interface/paginas/02-controles.html"

#: Os endereços que ESTÃO na bancada e AINDA NÃO na página publicada. Três são
#: decisão dela (itens 15 e 16); o quarto é o defeito que a foto de 02/09 pegou
#: — o retângulo da barra de luz contradizendo o campo ao lado.
#:
#: ELE É LIDO DOS DOIS ARQUIVOS, e a razão é um defeito medido nesta mesma aba
#: em 02/09/2026: a lista era uma TUPLA ESCRITA À MÃO, e ela nomeava um
#: `luz-cor` que a bancada não tinha — o gerador fora editado e nunca rodado.
#: A simulação de publicação olhava a tupla, dava "16 casam", e o arquivo que
#: ela iria publicar tinha 15. **Uma lista digitada não descobre que o arquivo
#: ao lado dela ficou para trás.** Quem descobre é
#: `test_os_dez_geradores_rodam::test_o_gerador_reproduz_a_bancada`, e esta
#: leitura é a segunda trava.
#:
#: E ELE ESVAZIA SOZINHO no dia em que ela publicar, que é o desfecho que este
#: trabalho espera: a fixture vira um no-op e as réguas abaixo passam a medir a
#: página de verdade, sem ninguém tocar em teste.
DA_BANCADA = tuple(sorted(_campos_do_arquivo(BANCADA) - _campos_do_arquivo(PUBLICADA)))


@pytest.fixture()
def com_a_pagina_publicada(a02):
    """Finge que ela já publicou: a página passa a ter os quatro endereços.

    O estado de módulo é o mesmo cache que o produto usa, e ele é devolvido no
    fim — deixá-lo sujo faria a próxima régua medir uma página que não existe.
    """
    antes = a02._ENDERECOS
    a02._ENDERECOS = frozenset(antes or ()) | frozenset(DA_BANCADA)
    yield
    a02._ENDERECOS = antes


def test_o_pacote_so_emite_endereco_que_a_pagina_tem(pac, a02):
    """Toda chave emitida tem onde pousar na página que o piloto ABRE.

    A BANCADA É DELA. O gerador escreve em `mockup/`, e o produto só recebe
    pelo `--publicar 02`, que é ato dela. Emitir antes põe as chaves em
    `casamento.medir(...)["orfaos"]`, e quem reprova é
    `test_o_clique_do_analogico_tem_dono::test_a_aba_controles_nao_emite_para_
    endereco_que_a_pagina_nao_tem` — **não** o `test_o_casamento_das_dez`, que
    só cobra `casam >= piso` e passou verde com os quatro órfãos na mordida de
    02/09/2026. E, pior que a régua, o pacote contaria em `cobertura.pintados`
    uma pintura que não acontece, que é o defeito que o casamento nasceu para
    pegar.

    A PERGUNTA É `emitido ⊆ página`, e não *"os quatro nomes de hoje estão
    fora?"* — auditoria de 02/09/2026. A redação anterior afirmava um NEGATIVO
    sobre quatro endereços NOMEADOS, e por isso ficava verde só enquanto ela
    **não** publicasse: simulada a publicação (um `data-campo="alto-num"`
    acrescentado à página publicada), ela reprovava com a frase *"o pacote
    emitiu ['alto-num'] para uma página que não os tem"* — que afirma o
    contrário do que aconteceu, e manda quem herdar procurar um órfão que não
    existe. **O contrato é o mesmo nos dois mundos**, e esta forma o diz.

    MORDE: trocar `_so_se_a_pagina_tiver(...)` por `**{...}` direto reprova
    aqui nomeando o que sobrou sem endereço.
    """
    d = _card(pac, a02, {**BASE, "speaker": {"volume": VOLUME_VIVO, "muted": False}})
    tem = a02._enderecos_da_pagina()
    assert tem, "a página publicada não abriu — a régua ficaria verde sobre nada"
    orfaos = sorted(k for k in d if k not in tem)
    assert not orfaos, (
        f"o pacote emitiu {orfaos} e a página publicada não tem onde pô-los — "
        f"órfãos. Se ela acabou de publicar, o gerador é que ficou para trás.")


def test_publicada_a_pagina_o_volume_e_a_curva_medida(pac, a02,
                                                      com_a_pagina_publicada):
    """Decisão dela (item 16): o número E a barra do volume ganham endereço.

    Ela disse o defeito com número: *"hoje os dois estão congelados: com o
    volume em 40, a tela mostra 100"*. `40` no registrador é **3 %** pela curva
    medida no hardware (`core/speaker_scale.py`: abaixo de 38 tudo é mudo), e
    era isso que a tela escondia atrás de um `100` cravado.

    A CONTA É A MESMA do `alto-barra` — os dois campos do mesmo bloco saem de
    `percentual_do_volume`, e divergirem por dois arredondamentos é o defeito
    que aquele módulo existe para não cometer.

    MORDE: escrever `sp[0]` cru (o registrador 0-255) reprova nas duas linhas.
    """
    from hefesto_dualsense4unix.core.speaker_scale import percentual_do_volume

    d = _card(pac, a02, {**BASE, "speaker": {"volume": 40, "muted": False}})
    assert d["alto-num"] == percentual_do_volume(40) == 3
    assert d["alto-barra"] == 3


def test_publicada_a_pagina_o_volume_desconhecido_nao_vira_cem(
        pac, a02, com_a_pagina_publicada):
    """Sem `speaker`, o número diz `—` e a barra vai a ZERO — nunca ao desenho.

    A barra não pode dizer "não sei": `largura` é um dos
    `ALVOS_QUE_O_TRAVESSAO_NAO_ATENDE` (`width: "—%"` o CSSOM recusa, e o
    contador de pintura mente para sempre). Zero é o mesmo desfecho que a
    `bateria-barra` já tem, e quem separa "zero" de "não sei" é o número ao
    lado.

    MORDE: deixar de emitir a barra devolve a tela ao `width:100%` do desenho.
    """
    import mesa_viva

    d = _card(pac, a02, BASE)
    assert d["alto-num"] == mesa_viva.SEM_LEITOR
    assert d["alto-barra"] == 0


def test_publicada_a_pagina_o_retangulo_da_luz_diz_o_que_o_campo_diz(
        pac, a02, com_a_pagina_publicada):
    """O desenho ao lado do campo para de contradizer o campo.

    FOTOGRAFADO em 02/09/2026 às 19h, com os dois controles dela: o `luz-hex`
    dizia `#0000FF` (o `lightbar_rgb` vivo do P1) e o retângulo logo abaixo
    estava no `#7EB8D4` que o mockup cravou. **A régua do mockup não vê** — ela
    conta `data-campo`, e o retângulo não tinha nenhum: `02-controles` deu
    `23 campos · 23 PRODUTO · 0 MOCKUP` nessa mesma foto.

    OS TRÊS "NÃO SEI" MANDAM VAZIO, e o vazio apaga a cor de linha
    (`hefesto_vivo.py:246-250`) — o retângulo volta ao `--panel` da folha de
    estilo, que é o "nada" que ela decidiu para campo sem informação.

    MORDE: fazer `_cor_da_barra` devolver o hex sempre reprova na terceira
    linha, com o travessão virando `background` inválido.
    """
    acesa = _card(pac, a02, {**BASE, "lightbar_rgb": [0, 0, 255],
                             "lightbar_source": "sysfs", "lightbar_on": True})
    apagada = _card(pac, a02, {**BASE, "lightbar_rgb": [0, 0, 255],
                               "lightbar_source": "sysfs", "lightbar_on": False})
    nao_sei = _card(pac, a02, {**BASE, "lightbar_rgb": [0, 0, 0],
                               "lightbar_source": "desconhecida"})
    assert acesa["luz-cor"] == acesa["luz-hex"] == "#0000FF"
    # A APAGADA DEIXOU DE DIZER A MESMA COISA NOS DOIS, e é decisão dela ([02],
    # 04/09/2026): o RETÂNGULO continua no preto que uma barra sem corrente
    # emite, e o CAMPO passou a dizer a palavra. São duas perguntas diferentes
    # no mesmo bloco — *"que cor?"* e *"por que não vejo cor?"* —, e é
    # justamente por o campo responder a segunda que a palavra entrou.
    assert apagada["luz-cor"] == "#000000"
    assert apagada["luz-hex"] == a02.PALAVRA_DA_LUZ[a02.ROTULO_DA_LUZ_APAGADA]
    assert nao_sei["luz-cor"] == "", "o retângulo afirma uma cor que ninguém mediu"


def test_publicada_a_pagina_o_ponto_do_touchpad_segue_o_campo(
        pac, a02, com_a_pagina_publicada):
    """O par completo: a palavra e o ponto saem da MESMA leitura.

    MORDE: separar as duas decisões (uma lendo `touching`, outra não) deixa a
    tela dizer "Sem toque" com o ponto aceso — que é exatamente a foto do
    antes.
    """
    solto = _card(pac, a02, {**BASE, "inputs": {
        "touchpad": TOUCHPAD_COMO_O_DAEMON_PUBLICA}})
    tocando = _card(pac, a02, {**BASE, "inputs": {
        "touchpad": {**TOUCHPAD_COMO_O_DAEMON_PUBLICA, "touching": True}}})
    assert (solto["touch-estado"], solto["touch-ponto"]) == ("Sem toque", "")
    assert tocando["touch-estado"] == "1 toque" and tocando["touch-ponto"]


# --------------------------------------------------------------------------
# 8. A OUTRA METADE DA DECISÃO 15 — medida NA TELA, e não no texto do CSS
# --------------------------------------------------------------------------
# A decisão dela (item 15, segunda metade) tem DUAS metades, e elas moram em
# arquivos diferentes: o pacote emite `""`/`"sim"` (as duas réguas acima), e o
# HTML tem de deixar a CLASSE decidir — senão `on` acende algo que já estava
# aceso, e o ponto fica visível com `touching: false`, que é a foto do defeito.
#
# A SEGUNDA METADE NÃO TINHA RÉGUA, e a auditoria de 02/09/2026 mediu o preço:
# apagado o `opacity:0` do CSS do gerador e regerada a bancada, o `_conferir`
# do gerador não reclamou (`02-controles: OK, 122 divs`, rc=0) e os 40 testes
# desta aba passaram VERDES — com o pontinho visível sem toque nos dois cards.
#
# O QUE ELA COBRA SÃO DUAS COISAS, e a segunda a primeira redação desta régua
# errou: (a) SEM a classe o navegador desenha `opacity: 0` e COM ela `1` — é o
# que dá poder ao alvo `classe`; (b) na cena FIXA do desenho, o ponto concorda
# com a palavra do card ao lado. Nem todo card nasce apagado, e nem devia: o
# P1 do mockup diz "1 toque" e mostra o ponto de propósito. Exigir "apagado em
# todos" reprovava o desenho aprovado — medido nesta bancada, `['1', '0']`.
#
# POR QUE O CHROME, e não uma leitura do texto do CSS: o `_conferir` do gerador
# já cobra a PALAVRA (que o `data-campo="touch-ponto"` carregue o seu
# `data-hef-alvo="classe"`), e foi exatamente por medir palavra que ele passou
# sobre o defeito. Aqui a pergunta é o ATO — *quanto o navegador desenha* —, e
# quem responde é o `getComputedStyle`, que já viu a cascata inteira: folha,
# `style` inline e especificidade. Mesmo motor e mesma forma do
# `test_a_tela_entrega_as_vinte_e_uma_linhas.py`, e o Chrome roda headless.
CHROME = pathlib.Path("/usr/bin/google-chrome")

#: AS PÁGINAS QUE JÁ TÊM O ENDEREÇO — a régua SEGUE O ENDEREÇO, em vez de uma
#: lista de caminhos digitada. Hoje é só a bancada; no dia em que ela publicar,
#: as duas, sem ninguém tocar em teste.
PAGINAS_COM_O_PONTO = [
    (rotulo, caminho)
    for rotulo, caminho in (("bancada", BANCADA), ("publicada", PUBLICADA))
    if 'data-campo="touch-ponto"' in caminho.read_text(encoding="utf-8")
]

O_QUE_O_NAVEGADOR_DESENHA = r"""
(() => {
  const saida = [];
  for (const el of document.querySelectorAll('[data-campo="touch-ponto"]')) {
    const cartao = el.closest('[data-controle],[data-uniq]');
    const rotulo = cartao ? cartao.querySelector('[data-campo="touch-estado"]') : null;
    const aceso_na_cena = el.classList.contains('on');
    // A CLASSE É A DO PRODUTO: `data-hef-alvo="classe"` faz o piloto pôr `on`
    // no elemento (o ramo `classe` do `escrever`, em `hefesto_vivo.py`). Aqui
    // ela é posta e tirada à mão, porque o que se mede é a FOLHA, não o piloto
    // — e a cena volta como estava, para a leitura seguinte não herdar isto.
    el.classList.remove('on');
    const sem_a_classe = getComputedStyle(el).opacity;
    el.classList.add('on');
    const com_a_classe = getComputedStyle(el).opacity;
    if (!aceso_na_cena) el.classList.remove('on');
    saida.push({
      cartao: cartao ? (cartao.dataset.controle || cartao.dataset.uniq || '?') : '?',
      // QUEM ESTÁ NA MESA E QUEM É ASSENTO VAZIO — 07/09/2026. Desde
      // CONTROLES-O-LUGAR-VAZIO-TEM-ENDERECO-01 o lugar vazio é o MESMO cartão
      // do cheio, e por isso ELE TAMBÉM TEM `touch-ponto`. Sem esta chave a
      // régua abaixo não teria como separar os dois — e a separação é o ponto:
      // um assento sem controle não tem dedo NEM palavra sobre o dedo.
      conectado: cartao ? (cartao.dataset.conectado || '') : '',
      estado: rotulo ? (rotulo.textContent || '').trim() : '',
      aceso_na_cena: aceso_na_cena,
      sem_a_classe: sem_a_classe,
      com_a_classe: com_a_classe,
    });
  }
  return saida;
})()
"""


def test_ha_pagina_com_o_ponto_para_medir():
    """Sem esta linha, a régua abaixo some inteira e ninguém percebe.

    `parametrize` sobre lista vazia coleta ZERO testes e o pytest não reclama —
    é a forma mais silenciosa de uma régua deixar de medir, e esta casa já a
    pagou (é a razão do `assert saiu` em `test_os_dez_geradores_rodam`).
    """
    assert PAGINAS_COM_O_PONTO, (
        'nenhuma das duas páginas tem `data-campo="touch-ponto"` — ou o '
        "gerador perdeu o endereço, ou a bancada ficou para trás. Rode "
        "`python3 src/hefesto_dualsense4unix/interface/aba02.py`.")


@pytest.mark.skipif(not CHROME.exists(),
                    reason="sem o Chrome do sistema — a régua não tem motor")
@pytest.mark.parametrize(
    "arquivo", [c for _, c in PAGINAS_COM_O_PONTO],
    ids=[r for r, _ in PAGINAS_COM_O_PONTO])
def test_o_ponto_do_touchpad_obedece_a_classe_na_tela(arquivo: pathlib.Path):
    """A classe DECIDE (0 sem ela, 1 com ela) e a cena fixa não se contradiz.

    EM TODOS OS CARDS, e não no primeiro: a mordida da auditoria deixou o ponto
    visível no card do P2, e uma régua que olhasse só o P1 daria verde sobre
    ele.

    A PALAVRA DO "SEM TOQUE" VEM DO MOTOR, não é digitada aqui — é o mesmo
    `texto_toques` que o pacote chama, e uma régua que redigitasse a frase
    passaria a medir a si mesma no dia em que o motor a mudasse.

    MORDE: tirar o `opacity:0` de `.touch .ponto` no `aba02.py` e rodar o
    gerador reprova aqui, com o `sem_a_classe` vindo `1`.
    """
    from hefesto_dualsense4unix.app.widgets.sensor_widgets import texto_toques

    from playwright.sync_api import sync_playwright

    sem_toque = texto_toques(0)

    with sync_playwright() as pw:
        navegador = pw.chromium.launch(
            executable_path=str(CHROME), args=["--no-sandbox"])
        try:
            pg = navegador.new_page(viewport={"width": 1180, "height": 900})
            pg.goto(arquivo.as_uri())
            medido = pg.evaluate(O_QUE_O_NAVEGADOR_DESENHA)
        finally:
            navegador.close()

    # OS DOIS GRUPOS, e a separação é de 07/09/2026: o assento SEM controle
    # passou a ter `touch-ponto` como todo mundo (o cartão é um só), e a
    # pergunta que se faz a ele é OUTRA.
    cheios = [d for d in medido if d["conectado"] != "nao"]  # noqa-acento: `nao` é o VALOR do atributo
    vazios = [d for d in medido if d["conectado"] == "nao"]  # noqa-acento: `nao` é o VALOR do atributo

    assert len(cheios) >= 2, (
        f"achei {len(cheios)} ponto(s) de controle conectado em {arquivo.name} — "
        f"a página tem dois cards conectados, e medir um só é medir metade")

    mudos = [d for d in medido if d["sem_a_classe"] != "0"]
    assert not mudos, (
        f"em {arquivo.name} o ponto do touchpad continua desenhado SEM a classe "
        f"`on`: {mudos}. Decisão dela, item 15: *\"o pontinho do touchpad só "
        f"aparece quando há toque\"* — com o CSS já aceso, a classe não acende "
        f"nada e a tela diz \"{sem_toque}\" com o ponto na superfície")

    apagados = [d for d in medido if d["com_a_classe"] != "1"]
    assert not apagados, (
        f"em {arquivo.name} a classe `on` não acende o ponto: {apagados} — o "
        f"pacote emitiria 'sim' e a tela ficaria muda")

    # A CENA FIXA NÃO PODE SE CONTRADIZER: era o defeito de 02/09 na página
    # publicada, onde `touch-estado` dizia "Sem toque" com o ponto aceso.
    #
    # SÓ NOS CONECTADOS, E POR UMA RAZÃO DE CONTRATO — 07/09/2026. Esta linha
    # conhecia DOIS estados (há dedo · não há dedo) e a mesa tem TRÊS desde que
    # o lugar vazio virou o mesmo cartão: *não sei*, que é o travessão. Com
    # `estado == "—"` a conta lia *"a palavra não é 'Sem toque', logo o ponto
    # devia estar aceso"* e reprovava um assento que estava CERTO — a régua
    # medindo o mundo de ontem. O terceiro estado ganhou a asserção própria
    # logo abaixo, que é mais dura, não mais frouxa.
    discordam = [d for d in cheios
                 if (d["estado"] == sem_toque) == d["aceso_na_cena"]]
    assert not discordam, (
        f"em {arquivo.name} o desenho contradiz a palavra do card ao lado: "
        f"{discordam}. O ponto marca ONDE o dedo está; sem toque não há ponto")

    # E O ASSENTO VAZIO NÃO AFIRMA DEDO NENHUM — nem o ponto, nem a palavra.
    # O travessão vem do DONO (`monta.TRAVESSAO`), nunca digitado aqui: é o
    # mesmo caractere que `pacotes.apagar_os_lugares_sem_dono` escreve na tela
    # viva, e uma régua que o redigitasse passaria a medir a si mesma.
    #
    # MORDE: tire o `_so_o_travessao` do `bloco()` no `aba02.py` e rode o
    # gerador — o assento vazio volta com "1 toque" e o pontinho do mockup em
    # cima do touchpad, e esta linha reprova nomeando o cartão.
    import monta

    afirmam = [d for d in vazios
               if d["aceso_na_cena"] or d["estado"] != monta.TRAVESSAO]
    assert not afirmam, (
        f"em {arquivo.name} um assento SEM controle afirma toque: {afirmam}. "
        f"O ponto marca onde o dedo está, e num lugar vazio não há dedo — a "
        f"palavra é `{monta.TRAVESSAO}` e o ponto fica apagado")
