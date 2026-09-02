#!/usr/bin/env python3
"""A aba Iluminação não pode discordar de si mesma sobre QUEM é o controle.

D2, FOTOGRAFADO EM 02/09/2026 na tela dela: a coluna do controle do cabo dizia
``Modelo: P—`` no rótulo e deixava o botão ``2`` ACESO logo abaixo. A mesma aba,
dois lugares, duas respostas.

A CAUSA, medida contra o daemon vivo::

    uniq aabbcc000001 · bt  · player 1    · player_slot 1 · is_primary True
    uniq aabbcc000002 · usb · player None · player_slot 2 · is_primary False

``a04_iluminacao.py:89`` lia só ``player``, que é ``None`` para quem não é
jogador do co-op. E o motor tem UM dono para essa pergunta desde a COR-01/D6 —
``app/actions/base.numero_do_controle`` —, cujo próprio docstring conta por que
ele existe: *"Existia uma cópia dessa regra em cada tela (…) Duas verdades na
mesma janela sobre qual é o 'Controle 1'."* Esta aba tinha a terceira cópia no
rótulo e a quarta no gesto ``auto`` (``player_slot or player or 1``).

AS QUATRO RÉGUAS DAQUI, e cada uma nasceu de uma coisa que a tela fazia:

1. o número do rótulo é o do MOTOR, e sobrevive a ``player=None``;
2. o rótulo leva os TRÊS pedaços — o desenho escreve ``P1 • Cosmic Red • USB`` e
   a pintura escreve ``textContent``, então emitir só o ``P1`` APAGAVA o nome e
   o transporte da tela no primeiro tique;
3. o brilho chega com o ``%``, porque a caixa ao lado da barra é de texto;
4. a fileira dos quatro números é viva, e a dica não nomeia controle que não
   está na mesa.
"""
from __future__ import annotations

import pathlib
import sys

import pytest

RAIZ = pathlib.Path(__file__).resolve().parents[2]
for _p in (str(RAIZ / "src"), str(RAIZ / "src" / "hefesto_dualsense4unix" / "interface")):
    if _p not in sys.path:
        sys.path.insert(0, _p)


#: A MESA DE 02/09/2026, na forma que `mesa_viva.mesa_do_estado` devolve — e o
#: `jogador` dela JÁ É `numero_do_controle(entrada)` (`mesa_viva.py:324`).
#: MAC da faixa sintética da casa: há dois portões de anonimato nesta árvore.
MESA = [
    {"pref": "p1", "uniq": "aa:bb:cc:00:00:01", "jogador": 1, "cor": "cosmic-red",
     "nome": "Cosmic Red", "via": "BT", "transporte": "bt"},
    {"pref": "p2", "uniq": "aa:bb:cc:00:00:02", "jogador": 2, "cor": "starlight-blue",
     "nome": "Starlight Blue", "via": "USB", "transporte": "usb"},
]

#: O CONTROLE DO CABO COMO O DAEMON O PUBLICA: `player` é `None` porque ele não
#: é jogador do co-op — a condição está em `daemon/subsystems/coop.py:341-343`,
#: e NÃO é o transporte, como o mapa chegou a afirmar.
DO_CABO = {"uniq": "aa:bb:cc:00:00:02", "transport": "usb", "connected": True,
           "player": None, "player_slot": 2, "is_primary": False,
           "lightbar_rgb": [255, 0, 0], "lightbar_on": True,
           "lightbar_source": "sysfs", "battery_pct": 95}
DO_RADIO = {"uniq": "aa:bb:cc:00:00:01", "transport": "bt", "connected": True,
            "player": 1, "player_slot": 1, "is_primary": True,
            "lightbar_rgb": [0, 0, 255], "lightbar_on": True,
            "lightbar_source": "sysfs", "battery_pct": 85}


@pytest.fixture
def colunas():
    """As colunas do pacote, com a mesa e o estado de 02/09."""
    import pacotes

    def montar(conectados=None, estado=None):
        ctx = pacotes.Contexto(
            state=estado if estado is not None else {"active_profile": ""},
            mesa=MESA,
            conectados=list(conectados if conectados is not None else [DO_RADIO, DO_CABO]),
            estados={})
        return pacotes.pacote_da_pagina("04-iluminacao.html", ctx)["colunas"]

    return montar


# ---------------------------------------------------------------------------
# 1. o número — D2
# ---------------------------------------------------------------------------
def test_o_rotulo_nao_diz_travessao_com_o_botao_aceso(colunas):
    """O defeito, na forma exata em que foi fotografado.

    A MORDIDA: troque `_numero()` por `c.get("player")` e esta linha reprova com
    `P—`, que é o que a tela mostrava.
    """
    col = colunas()[DO_CABO["uniq"]]
    assert col["identidade"].startswith("P2 "), (
        f"o rótulo saiu {col['identidade']!r}. O controle do cabo tem "
        f"`player_slot=2` e `player=None`; ler só `player` escreve `P—` no "
        f"rótulo com o botão `2` aceso logo abaixo — a aba discordando de si "
        f"mesma, que é o defeito D2 de 02/09/2026.")
    assert "P—" not in col["identidade"]


def test_o_numero_e_o_do_motor_e_nao_uma_copia(colunas):
    """A ordem é a do `numero_do_controle`: `player_slot` primeiro.

    Um controle com os DOIS números e eles DISCORDANDO prova qual venceu — e é o
    único jeito de a régua distinguir "leu o certo" de "coincidiu".
    """
    from hefesto_dualsense4unix.app.actions.base import numero_do_controle

    discordantes = dict(DO_CABO, player=4, player_slot=2)
    col = colunas([discordantes])[DO_CABO["uniq"]]
    assert numero_do_controle(discordantes) == 2
    assert col["identidade"].startswith("P2 "), (
        f"saiu {col['identidade']!r}: com `player_slot=2` e `player=4` a aba "
        f"pintou o `player`. O dono da regra é "
        f"`app/actions/base.numero_do_controle`, e a MESA já o chama.")


# ---------------------------------------------------------------------------
# 2. o rótulo inteiro — os dois pedaços que a pintura comia
# ---------------------------------------------------------------------------
def test_o_rotulo_leva_o_nome_e_o_transporte(colunas):
    """`P1 • Cosmic Red • BT`, e não `P1`.

    O desenho escreve os três pedaços; `hefesto_vivo.escrever` faz
    `el.textContent = t`, que apaga os filhos. Emitir só o número fazia o
    primeiro tique tirar da tela o nome do controle e o transporte — medido em
    Chrome headless em 01/09 (`.ctrl-rot` de 2 filhos para 0).
    """
    col = colunas()[DO_RADIO["uniq"]]
    assert col["identidade"] == "P1 • Cosmic Red • BT", col["identidade"]


def test_o_transporte_vem_do_agora_e_nao_do_desenho(colunas):
    """O HTML publicado diz `USB` no P1; o daemon diz `bt`. Vence o daemon.

    É a oitava aparição nesta casa de *uma frase que nomeia um controle fora do
    que a mesa mostra* — e aqui ela estava congelada dentro do rótulo.
    """
    col = colunas()[DO_RADIO["uniq"]]
    assert col["identidade"].endswith("• BT"), col["identidade"]


def test_sem_nome_na_mesa_o_rotulo_nao_inventa(colunas):
    """Sem item de mesa, travessão — nunca um nome de modelo cravado.

    `Cosmic Red` e `Starlight Blue` estão cravados 54 vezes no gerador desta
    aba, e nenhum deles pode vazar para o produto: quem sabe o nome é a MESA,
    que o leu do plástico pelo broker.
    """
    import pacotes

    ctx = pacotes.Contexto(state={}, mesa=[], conectados=[DO_CABO], estados={})
    col = pacotes.pacote_da_pagina("04-iluminacao.html", ctx)["colunas"][DO_CABO["uniq"]]
    assert col["identidade"] == "P2 • — • USB", col["identidade"]


# ---------------------------------------------------------------------------
# 3. o brilho — D7, a metade do VALOR
# ---------------------------------------------------------------------------
def test_o_brilho_chega_com_o_por_cento(colunas):
    """A caixa ao lado da barra é de TEXTO, e o desenho escreve `82%`.

    Sem perfil o brilho é `None`, e o travessão é a resposta honesta.
    """
    col = colunas()[DO_RADIO["uniq"]]
    assert col["brilho"] == "—", col["brilho"]
    assert col["brilho-pct"] is None


def test_a_barra_recebe_numero_e_a_caixa_recebe_texto():
    """`brilho-pct` é NÚMERO (vira largura) e `brilho` é TEXTO. Nunca o mesmo.

    O D7 fotografado em 02/09 tem duas metades: a caixa dizia `1` (o `1.0` do
    disco escrito cru) e o `100` era impresso DENTRO do trilho, porque a página
    não trazia `data-hef-alvo="largura"`. Esta régua guarda a primeira metade; a
    segunda é o atributo, e ela mora na régua do desenho.
    """
    import pacotes

    ctx = pacotes.Contexto(state={"active_profile": ""}, mesa=MESA,
                           conectados=[DO_RADIO], estados={})
    col = pacotes.pacote_da_pagina("04-iluminacao.html", ctx)["colunas"][DO_RADIO["uniq"]]
    assert not isinstance(col["brilho-pct"], str), (
        "a largura da barra tem de ser número: o JS escreve `t + '%'`.")
    assert isinstance(col["brilho"], str), "a caixa é texto, e o `%` é dela."


# ---------------------------------------------------------------------------
# 4. a fileira dos quatro números
# ---------------------------------------------------------------------------
def test_a_fileira_marca_o_numero_de_quem_e(colunas):
    """O `on` é do número DESTE controle, e ele é vivo.

    Enquanto os quatro botões eram `data-campo="player-N"`, a pintura só sabia
    escrever TEXTO neles — e texto num `<button>` apaga o anel do dono. Nenhum
    dos quatro era pintado, e `casamento.py` os listava como VAZIOS.
    """
    cols = colunas()
    fileira = cols[DO_CABO["uniq"]]["players"]
    assert 'data-player="2" title="O Starlight Blue É o Player 2' in fileira
    assert cols[DO_CABO["uniq"]]["players"].count('class="on"') == 1
    assert 'class="on" data-gesto="player" data-player="1"' in cols[DO_RADIO["uniq"]]["players"]


def test_a_dica_nao_nomeia_controle_que_nao_esta_na_mesa(colunas):
    """Número sem dono na mesa é número LIVRE.

    31/08/2026: o `title` dizia *"o Galactic Purple, que tem o 3 hoje"* com o
    Galactic Purple desconectado. Com um controle só, os outros TRÊS números
    ficam livres.
    """
    fileira = colunas([DO_RADIO])[DO_RADIO["uniq"]]["players"]
    assert fileira.count("— livre.") == 3, fileira
    assert "Starlight Blue" not in fileira, (
        "a dica nomeou um controle que não está na mesa.")


def test_o_gerador_e_o_produto_desenham_o_mesmo_botao():
    """Um dono, dois chamadores — e a régua compara os dois lados.

    O `botao_player` do gerador foi apagado em 02/09; `aba04.py` passou a chamar
    `um_botao_de_player`. Se alguém reescrever um dos lados, este teste acusa
    antes de o desenho e o produto divergirem — que foi como a `novo-layout/`
    divergiu 25 KB sem ninguém ver.
    """
    from pacotes import a04_iluminacao as pac

    dono = {"nome": "Cosmic Red", "via": "USB", "cor": "cosmic-red"}
    botao = pac.um_botao_de_player("Cosmic Red", 1, 1, dono)
    assert botao.startswith('<button class="on" data-gesto="player" data-player="1"')
    assert '<i class="dono" style="--plastico:#ae335a"></i>1</button>' in botao, (
        f"o anel perdeu a cor do plástico: {botao!r}. O hex sai de "
        f"`monta.cor_da_zona`, que LÊ a folha que pinta o desenho.")
    assert 'data-campo=' not in botao, (
        "o botão voltou a ter endereço próprio — a fileira inteira é que tem, "
        "porque a pintura não sabe escrever CLASSE.")


def test_o_html_publicado_e_a_bancada_concordam_sobre_o_endereco():
    """Onde o `data-campo` da fileira está, em cada lado — e por que difere.

    A bancada JÁ TEM `data-campo="players"` no `.players`; o publicado ainda tem
    `player-1..4` nos botões, porque publicar é ATO DELA. Enquanto for assim, o
    produto simplesmente não acha o endereço e não escreve nada — o que é
    inócuo. Esta régua guarda o par: no dia em que ela publicar, os quatro
    endereços mortos têm de sumir junto.
    """
    import onde

    bancada = onde.pagina("04-iluminacao.html").read_text(encoding="utf-8")
    assert bancada.count('data-campo="players" data-hef-alvo="html"') == 2
    assert 'data-campo="player-1"' not in bancada, (
        "a bancada ficou com os dois endereços: o da fileira e os dos botões. "
        "Dois donos para o mesmo lugar é o que este projeto persegue.")
    assert bancada.count('data-campo="brilho-pct" data-hef-alvo="largura"') == 2, (
        "sem o alvo `largura` o `100` é impresso DENTRO do trilho — é a outra "
        "metade do D7 de 02/09/2026.")


# ---------------------------------------------------------------------------
# 5. a frase da disputa — o motor, não uma segunda verdade
# ---------------------------------------------------------------------------
def test_a_frase_da_disputa_e_a_do_motor(colunas):
    """`recado` vem de `controller_card.rotulo_lightbar`, e não da mão.

    O texto que estava aqui dizia *"A Steam tem este controle aberto: a cor
    publicada é a PEDIDA…"* — escrito à mão, quando o motor já tem a frase e ela
    é constante (`ROTULO_LIGHTBAR_SEGURADA`) justamente para que o teste possa
    cobrar a propriedade em vez de decorar o texto.
    """
    from hefesto_dualsense4unix.app.widgets.controller_card import (
        ROTULO_LIGHTBAR_SEGURADA,
    )

    disputado = dict(DO_RADIO, lightbar_disputada=True)
    col = colunas([disputado])[DO_RADIO["uniq"]]
    assert col["recado"] == ROTULO_LIGHTBAR_SEGURADA, col["recado"]


def test_o_recado_conhece_os_estados_que_a_mao_nao_conhecia(colunas):
    """Quatro estados onde havia um: Nativo, disputa, desconhecida, apagada."""
    apagado = dict(DO_RADIO, lightbar_on=False)
    assert colunas([apagado])[DO_RADIO["uniq"]]["recado"] == "Lightbar: apagada"

    sem_fonte = dict(DO_RADIO, lightbar_source="desconhecida")
    assert colunas([sem_fonte])[DO_RADIO["uniq"]]["recado"] == "Lightbar: cor desconhecida"

    nativo = colunas([DO_RADIO], estado={"active_profile": "", "native_mode": True})
    assert nativo[DO_RADIO["uniq"]]["recado"] == "Em Nativo o jogo é dono do LED"

    assert colunas()[DO_RADIO["uniq"]]["recado"] == "", (
        "aviso permanente vira paisagem, e paisagem ninguém lê.")


# ---------------------------------------------------------------------------
# 6. o gesto `auto` — a quarta cópia da regra do número
# ---------------------------------------------------------------------------
def test_o_automatico_pinta_a_cor_do_numero_do_motor():
    """Largar o claim e pintar a cor do slot — com o número que o motor dá.

    A linha era `player_slot or player or 1`: o `or 1` é a POSIÇÃO disfarçada de
    default, e um controle sem número nenhum ganharia a cor do P1.
    """
    import pacotes
    from hefesto_dualsense4unix.core.led_control import player_slot_color

    class PonteDeMentira:
        def __init__(self):
            self.chamadas = []

        def __getattr__(self, nome):
            def guardar(*a, **kw):
                self.chamadas.append((nome, a, kw))
                return (True, "")
            return guardar

    ctx = pacotes.Contexto(state={}, mesa=MESA, conectados=[DO_CABO], estados={})
    p = PonteDeMentira()
    pacotes.gesto_da_pagina("04-iluminacao.html", "auto")(
        ctx, {"uniq": DO_CABO["uniq"]}, p)

    assert p.chamadas[0][0] == "chamar" and p.chamadas[0][1] == ("lightbar.reset",)
    assert p.chamadas[1] == ("led_set", (tuple(player_slot_color(2)),),
                             {"uniq": DO_CABO["uniq"]}), (
        f"o automático pintou {p.chamadas[1]!r}. O controle do cabo é o 2 pelo "
        f"`player_slot`; cair em 1 é a posição disfarçada de default.")
