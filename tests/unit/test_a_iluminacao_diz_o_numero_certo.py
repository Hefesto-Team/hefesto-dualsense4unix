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

AS RÉGUAS DAQUI, e cada uma nasceu de uma coisa que a tela fazia:

1. o número do rótulo é o do MOTOR, e sobrevive a ``player=None``;
2. o rótulo leva os TRÊS pedaços — o desenho escreve ``P1 • Cosmic Red • USB`` e
   a pintura escreve ``textContent``, então emitir só o ``P1`` APAGAVA o nome e
   o transporte da tela no primeiro tique;
3. o brilho chega com o ``%``, porque a caixa ao lado da barra é de texto;
4. a fileira dos quatro números é viva, e a dica não nomeia controle que não
   está na mesa;
5. a célula LEDs é um DESENHO — a palavra ``Aceso`` escrita nela apagava as duas
   tiras e as cinco lâmpadas, e foi fotografado na tela dela em 02/09/2026;
6. a tira APAGADA não acende: um ``color:`` vazio deixava o halo
   ``currentColor`` herdar o ``--fg`` e a barra desligada saía BRANCA, mais
   forte que a acesa;
7. ABRIR o seletor livre não é APLICAR: um ``<input type="color">`` dispara
   ``click`` ao abrir, com o valor VELHO, e o gesto mandava essa cor ao
   aparelho antes de ela escolher.
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
    # O `data-hef` do anel entrou em 03/09/2026 (IDENTIDADE-VEM-DE-CIMA-01): sem
    # ele a régua da identidade acusa o `--plastico` do `<i>`, porque ela julga
    # a cor no elemento que a carrega. Ver `a04_iluminacao.ANEL_DO_DONO`.
    assert (f'<i class="dono" data-hef="{pac.ANEL_DO_DONO}"'
            f' style="--plastico:#ae335a"></i>1</button>') in botao, (
        f"o anel perdeu a cor do plástico ou o endereço: {botao!r}. O hex sai de "
        f"`monta.cor_da_zona`, que LÊ a folha que pinta o desenho.")
    assert 'data-campo=' not in botao, (
        "o botão voltou a ter endereço próprio — a fileira inteira é que tem, "
        "porque a pintura não sabe escrever CLASSE.")


def test_o_html_publicado_e_a_bancada_concordam_sobre_o_endereco():
    """Onde cada `data-campo` está, nos DOIS lados — e o par que ainda difere.

    FATO CORRIGIDO EM 02/09/2026: este teste dizia *"o publicado ainda tem
    `player-1..4` nos botões"*, e olhava só a bancada. Não tem mais — a
    publicação do commit `70b58116` levou `data-campo="players"` e o alvo
    `largura` ao produto. Medido: `grep -c` no HTML publicado dá `2`, `2` e `0`.
    Uma régua que olha um lado só não podia ver isso.
    """
    import onde

    bancada = onde.pagina("04-iluminacao.html").read_text(encoding="utf-8")
    publicado = onde.pagina("04-iluminacao.html", publicado=True).read_text(
        encoding="utf-8")
    for lado, texto in (("bancada", bancada), ("publicado", publicado)):
        assert texto.count('data-campo="players" data-hef-alvo="html"') == 2, lado
        assert 'data-campo="player-1"' not in texto, (
            f"o {lado} ficou com os dois endereços: o da fileira e os dos "
            f"botões. Dois donos para o mesmo lugar é o que este projeto "
            f"persegue.")
        assert texto.count('data-campo="brilho-pct" data-hef-alvo="largura"') == 2, (
            f"sem o alvo `largura` o `100` é impresso DENTRO do trilho — é a "
            f"outra metade do D7 de 02/09/2026 ({lado}).")


# ---------------------------------------------------------------------------
# 5. o DESENHO da luz — e a palavra que o apagava
# ---------------------------------------------------------------------------
def test_a_luz_e_desenho_e_nao_palavra(colunas):
    """O `.aceso` é um DESENHO; escrever nele uma palavra o APAGA.

    FOTOGRAFADO na tela dela em 02/09/2026, com dois controles na mesa: a célula
    LEDs das colunas P1 e P2 mostrando a palavra `Aceso`, sem as duas tiras de
    luz e sem as cinco lâmpadas. A causa é uma linha do pacote — `"aceso":
    "Aceso" if …` num `data-campo` de alvo `texto` —, e `escrever()` faz
    `el.textContent = t`, que apaga os filhos. A régua do mockup contava isso
    como PRODUTO, porque o valor MUDOU: é a mesma família do `balanceado`
    escrito dentro dos quatro botões da Vibração.

    A MORDIDA: devolva `"aceso": "Aceso"` ao pacote e a primeira linha reprova.
    """
    col = colunas()[DO_RADIO["uniq"]]
    assert "aceso" not in col, (
        "a palavra voltou ao lugar do desenho: `textContent` num `.aceso` "
        "apaga as duas tiras e as cinco lâmpadas.")
    assert col["luz"].count('class="tira-luz') == 2, col["luz"]
    assert '<span class="luzinhas">' in col["luz"], (
        "as cinco lâmpadas do indicador não saíram no desenho vivo.")
    assert '<span class="pad"' in col["luz"], (
        "a moldura do touchpad sumiu do desenho vivo.")


def test_o_endereco_da_luz_so_existe_na_bancada():
    """`luz` na bancada, `aceso` no publicado — e o descasamento é a CURA.

    Publicar é ato DELA. Enquanto o produto disser `data-campo="aceso"`, o
    pacote NÃO PODE emitir `aceso`: qualquer valor que ele emita ali vira
    `textContent` e apaga o desenho. Com o nome novo, o produto de hoje não acha
    onde escrever e o desenho fica INTEIRO; no dia em que ela publicar, o mesmo
    valor passa a pintar.
    """
    import onde

    bancada = onde.pagina("04-iluminacao.html").read_text(encoding="utf-8")
    publicado = onde.pagina("04-iluminacao.html", publicado=True).read_text(
        encoding="utf-8")
    assert bancada.count('data-campo="luz" data-hef-alvo="html"') == 2
    assert 'data-campo="aceso"' not in bancada
    assert 'data-campo="luz"' not in publicado, (
        "o produto ganhou o endereço novo: apague este par de asserções e o "
        "`aceso` do publicado junto — a espera acabou.")


def test_o_anel_da_cor_escolhida_tem_endereco_e_e_o_mesmo_do_hex():
    """O `.tom.on` deixou de ser pintura cravada — o alvo `classe` existe.

    O anel dizia qual dos oito tons está valendo, e o `on` era o que o GERADOR
    soube: a cor do mockup. Quem escolhe uma cor fora da guia — o seletor livre
    existe para isso — ou muda a cor pelo aparelho via o anel parado no tom
    velho **para sempre**, porque a pintura da casa sabia texto, largura, fundo,
    valor e HTML, e o estado desta guia é uma CLASSE. Estava parado como
    `espera_o_pintor`; o alvo chegou.

    O ENDEREÇO É `hex`, o MESMO da caixa `#RRGGBB` da mesma coluna, e isso é
    deliberado: é UM valor em duas renderizações. Um endereço novo faria o
    pacote emitir a mesma cor duas vezes, e duas emissões do mesmo valor é
    exatamente por onde as duas metades de uma tela divergem.

    A MORDIDA: tire o `data-campo="hex" data-hef-alvo="classe"` do gerador,
    rode-o, e a primeira asserção reprova.
    """
    import onde
    from pacotes import a04_iluminacao as pac

    bancada = onde.pagina("04-iluminacao.html").read_text(encoding="utf-8")
    #: OITO TONS nos DOIS controles conectados da bancada.
    assert bancada.count('data-campo="hex" data-hef-alvo="classe"') == 16, (
        "os botões da guia de cores voltaram a não ter endereço de estado.")

    #: O `data-hef-quando` LEVA O HEX DO PRODUTO, que é o que o pacote emite —
    #: e não o tom da casa, que é só o que a tela desenha. Foi essa mesma
    #: confusão que fez o `.tom.on` do desenho casar ZERO botões em 31/08.
    from hefesto_dualsense4unix.core.led_control import player_slot_color

    for n in (1, 2):
        assert f'data-hef-quando="{pac._hex(player_slot_color(n))}"' in bancada


def test_a_bancada_perdeu_a_dica_congelada_da_celula_de_leds():
    """A dica do `.aceso` saiu do ATRIBUTO da célula e entrou no desenho.

    Ela dizia, cravada pelo gerador nos dois controles conectados::

        title="O Cosmic Red aceso: as duas tiras na cor escolhida, e as cinco
               lâmpadas no padrão do Player 1."

    Um `title` na célula não tem como ser repintado: o piloto só sabe escrever
    `texto`, `largura`, `fundo`, `valor`, `html`, `classe` e `cor` — atributo
    não está na lista. Congelada, ela nomeava o controle do MOCKUP na coluna de
    um controle que está na mesa (decisão 8 dela) e dizia `aceso` (decisão 7).

    A MORDIDA: devolva o `title=` ao `<div class="aceso">` do gerador, rode-o, e
    a primeira asserção reprova.
    """
    import onde

    bancada = onde.pagina("04-iluminacao.html").read_text(encoding="utf-8")
    assert '<div class="aceso" data-campo="luz" data-hef-alvo="html">' in bancada, (
        "a célula de LEDs voltou a carregar atributo cravado pelo gerador.")
    assert " aceso:" not in bancada, (
        "a palavra que ela mandou tirar voltou ao desenho.")
    #: A DICA VIVA ESTÁ NAS TRÊS PEÇAS de cada coluna conectada: 2 tiras + o
    #: `.pad`. A frase esperada NÃO é digitada aqui — sai do mesmo dono que o
    #: gerador chama, senão a régua mediria a palavra e não o ato.
    #:
    #: ELA CONTAVA `"Desenho que mandamos:" == 6` ATÉ 02/09/2026, e isso cravava
    #: uma afirmação que esta aba não pode fazer — ver
    #: `test_a_dica_nao_afirma_o_desenho_das_cinco_luzes_que_o_pacote_nao_ve`.
    import monta
    from pacotes import a04_iluminacao as pac

    for c in monta.CONECTADOS:
        esperada = pac.dica_da_luz(c["nome"], c["via"], "")
        assert bancada.count(f'title="{esperada}"') == 3, (
            f"as três peças da coluna de {c['nome']} perderam a dica viva "
            f"({esperada!r}).")
    assert "Desenho que mandamos" not in bancada, (
        "a afirmação sobre o desenho das 5 luzes voltou ao desenho: este pacote "
        "não vê o override por-uniq que decide qual desenho está em vigor.")


def test_o_gerador_e_o_produto_desenham_a_mesma_luz():
    """Um dono, dois chamadores — o mesmo par da fileira de players.

    O gerador desenhava as três linhas do `.aceso` à mão; agora chama
    `desenho_da_luz`. Enquanto fossem duas escritas, a tira do desenho e a do
    produto podiam divergir sem ninguém ver — que é como a `novo-layout/`
    divergiu 25 KB calada.
    """
    from pacotes import a04_iluminacao as pac

    miolo = pac.desenho_da_luz("#7EB8D4", 0.82, 1)
    assert 'class="tira-luz esq" style="background:#7EB8D4;color:#7EB8D4' in miolo
    assert 'class="tira-luz dir" style="background:#7EB8D4;color:#7EB8D4' in miolo
    assert "opacity:0.82" in miolo
    assert "title=" not in miolo, (
        "sem recado não há dica: aviso permanente vira paisagem.")


def test_um_numero_que_a_bancada_nunca_teve_nao_congela_a_aba():
    """`monta.luzinhas(9)` levanta `KeyError`, e agora quem a chama é o PRODUTO.

    `core/led_control.player_led_pattern` — o dono — devolve padrão para
    qualquer número, e o docstring dele diz que *"um DualSense pode
    legitimamente cair no slot 5+"* e que *"≥9 cai no padrão de overflow"*. Mas
    `monta.PADRAO_JOGADOR` só precomputa 1..8 e `monta.luzinhas` INDEXA o
    dicionário: medido em 02/09/2026, `monta.luzinhas(9)` → `KeyError: 9`.

    Enquanto só o gerador a chamava o número era 1..4 e ninguém via. Uma
    exceção aqui não deixaria de pintar UM campo: ela derrubaria a pintura da
    aba inteira. Sem padrão conhecido o indicador sai VAZIO, que é o honesto.
    """
    import monta
    import pytest as _pytest

    from pacotes import a04_iluminacao as pac

    with _pytest.raises(KeyError):
        monta.luzinhas(9)

    miolo = pac.desenho_da_luz("#7EB8D4", 1.0, 9)
    assert miolo.count('class="tira-luz') == 2, miolo
    assert '<span class="pad"></span>' in miolo, (
        f"o indicador inventou um padrão para o número 9: {miolo!r}. Mostrar o "
        f"do Player 1 diria um número que não é o dele.")


def test_a_tira_apagada_nao_acende_branco(colunas):
    """A barra APAGADA não pode virar um halo BRANCO — e o halo é `currentColor`.

    MEDIDO EM CHROME HEADLESS, dentro da página publicada, em 02/09/2026::

        com `background:;color:;opacity:1.0`  box-shadow rgb(248,248,242) · opacity 1
        a tira ACESA do P1, no mesmo arquivo  box-shadow rgb(126,184,212) · opacity 0.82

    Um `color:` VAZIO não desliga cor nenhuma: ele deixa valer o HERDADO, que
    nesta página é o `--fg` (`#f8f8f2`). A tira que o produto dizia estar
    apagada acendia BRANCA — e mais forte que a acesa a 82%.

    ESTA RÉGUA LÊ O CSS em vez de decorar a regra: se um dia o halo deixar de
    ser `currentColor`, é a primeira linha que reprova, e não uma asserção
    escrita à mão que continuaria verde sobre outra realidade.

    A MORDIDA: devolva `""` ao lugar de `TIRA_APAGADA` e a asserção do
    `color:transparent` reprova.
    """
    import onde

    publicado = onde.pagina("04-iluminacao.html", publicado=True).read_text(
        encoding="utf-8")
    assert "box-shadow:-3px 0 12px 1px currentColor" in publicado, (
        "o halo da tira deixou de ser `currentColor`: reescreva esta régua "
        "contra o que o CSS faz agora.")

    luz = colunas([dict(DO_RADIO, lightbar_on=False)])[DO_RADIO["uniq"]]["luz"]
    assert "color:transparent" in luz, luz
    assert "color:;" not in luz, (
        "a tira apagada voltou a sair com `color` VAZIO — e vazio herda o "
        "`--fg`, que é branco.")
    assert "Apagado" not in luz, "a palavra voltou ao lugar do desenho."


def test_a_luz_pergunta_ao_motor_se_ha_cor_a_afirmar(colunas):
    """Quem decide "há cor?" é `rotulo_lightbar`, e não uma leitura daqui.

    A linha era `c.get("lightbar_on", True)` — uma segunda verdade sobre a mesma
    pergunta, e com o default AFIRMANDO aceso na ausência do campo, que é o
    estado de partida de um controle no rádio antes do primeiro report.

    O motor devolve base `None` em DOIS estados, e os dois têm de sair
    apagados: "apagada" e "cor desconhecida".
    """
    sem_cor = dict(DO_RADIO, lightbar_rgb=None)
    assert "color:transparent" in colunas([sem_cor])[DO_RADIO["uniq"]]["luz"]

    #: Sem o campo `lightbar_on`, a leitura antiga dizia ACESA por default.
    sem_campo = {k: v for k, v in DO_RADIO.items() if k != "lightbar_on"}
    luz = colunas([sem_campo])[DO_RADIO["uniq"]]["luz"]
    assert "color:transparent" in luz, (
        f"a tira saiu {luz!r}: sem `lightbar_on` o motor diz 'apagada', e um "
        f"default `True` escrito aqui afirmaria uma barra acesa que ninguém "
        f"mediu.")


def test_a_tira_nao_acende_sob_steam_nem_sob_nativo(colunas):
    """A pergunta da TIRA não é a que o segundo retorno do motor responde.

    `rotulo_lightbar` devolve `(ressalva, COR BASE DO ACCENT)`, e a base é a
    ÚLTIMA COR CONHECIDA — devolvida **também** nos dois estados em que o
    próprio motor avisa que ela pode não estar no plástico::

        native_mode         → ("Em Nativo o jogo é dono do LED", rgb)
        lightbar_disputada  → ("a Steam tem este controle aberto", rgb)

    Nos dois a base volta preenchida COM `lightbar_on` falso — o pacote lia
    isso como "está acesa" e a tira acendia. Medido em 02/09/2026, com o dublê
    de estado, ANTES da cura (saída literal da mesma sonda)::

        NATIVO + lightbar_on falso   background:#7EB8D4;color:#7EB8D4;opacity:1.0
        STEAM  + lightbar_on falso   background:#7EB8D4;color:#7EB8D4;opacity:1.0

    A MORDIDA: troque `base if recado is None else None` por `base` e as duas
    primeiras linhas reprovam — a tira volta a acender azul com a barra
    apagada, sob os dois estados.
    """
    apagado = dict(DO_RADIO, lightbar_on=False)
    sob_nativo = colunas([apagado], {"active_profile": "", "native_mode": True})
    assert "color:transparent" in sob_nativo[DO_RADIO["uniq"]]["luz"], (
        "em Nativo a tira acendeu com a barra apagada: o jogo é dono do LED e "
        "a última cor NOSSA não diz o que está no plástico.")

    sob_steam = colunas([dict(apagado, lightbar_disputada=True)])
    assert "color:transparent" in sob_steam[DO_RADIO["uniq"]]["luz"], (
        "com a Steam segurando o `fd` a tira acendeu com a barra apagada.")

    #: E A RESSALVA CONTINUA SENDO DITA — apagar sem explicar seria trocar uma
    #: afirmação falsa por um silêncio.
    assert "Em Nativo" in sob_nativo[DO_RADIO["uniq"]]["luz"]

    #: O CAMINHO QUE NÃO PODE FECHAR JUNTO: acesa, cor conhecida, sem ressalva.
    acesa = colunas([DO_RADIO])[DO_RADIO["uniq"]]["luz"]
    assert "color:transparent" not in acesa, (
        "a cura apagou a tira que o motor diz estar ACESA — uma régua que "
        "apaga tudo passa por qualquer defeito.")


def test_a_dica_da_luz_nao_diz_aceso_e_nomeia_quem_esta_conectado(colunas):
    """As duas decisões dela de 02/09/2026, na mesma frase.

    7. *"a palavra ACESO sai do texto"* — ela já tinha mandado tirar, a GTK
       obedeceu em 25/08 (`lightbar_actions._PREFIXO_DESENHO` diz *"Desenho que
       mandamos"*) e o mockup a reintroduziu.
    8. *"a interface mostra o que tá conectado e não o controle do mockup"*.

    O QUE ESTAVA NA TELA DELA, cravado no `title` da célula::

        "O Cosmic Red aceso: as duas tiras na cor escolhida, e as cinco
         lâmpadas no padrão do Player 1."

    A MORDIDA: devolva essa frase ao gerador e as duas primeiras linhas
    reprovam.
    """
    luz = colunas()[DO_RADIO["uniq"]]["luz"]
    assert "aceso" not in luz.lower(), (
        f"a palavra voltou à dica: {luz!r}. Não há canal de leitura de LED de "
        f"jogador em transporte nenhum — a frase afirma o que ninguém confere.")
    assert "Cosmic Red" in luz and "Starlight Blue" not in luz, (
        "a dica nomeia o controle do desenho, e não o que está na mesa.")


def test_a_dica_nao_afirma_o_desenho_das_cinco_luzes_que_o_pacote_nao_ve(
    colunas,
):
    """A tela não afirma sobre uma camada do merge que este pacote não enxerga.

    ESTE TESTE SUBSTITUI UM QUE CRAVAVA O DEFEITO. O antecessor —
    `test_a_dica_manda_o_rascunho_vazio_porque_o_automatico_esta_acima` — exigia
    `"automático, do número deste controle" in dica`, isto é, gravava a
    afirmação como se fosse o certo. Um teste assim impede a próxima pessoa de
    consertar.

    A ACUSAÇÃO, REPRODUZIDA AQUI COM O MERGE REAL DO BACKEND (e nenhum
    aparelho): a precedência de `_merged_desired_for_key` é

        default global do perfil < camada AUTOMÁTICA < override por-uniq
                                                     < co-op < jogo

    e o override por-uniq é onde a janela GTK escreve quando ela aplica um
    desenho (`lightbar_actions._enviar_player_leds` → `player_leds_set_
    detalhado(…, uniq=…)` → `ipc_handlers._apply_por_uniq` → `apply_output_for`,
    *"que registra o override por-uniq"*). Com ele preenchido, o produto manda
    um desenho e a frase antiga anunciava outro.

    E O PACOTE NÃO PODE SABER: `_enrich_controllers_per_controller` não publica
    nenhum campo do desejado por controle — `interface/aba02.py:809` já dizia
    *"publica o ``player_slot`` e NÃO publica ``player_leds``"*.

    A REGRA DELA, 02/09/2026: *"se não tá mostrando agora, não tem info pra
    mostrar no produto"*. Campo sem informação não mostra nada.
    """
    from hefesto_dualsense4unix.core.backend_pydualsense import (
        PyDualSenseController,
        _DesiredOutput,
    )
    from hefesto_dualsense4unix.core.led_control import player_led_pattern
    import pacotes.a04_iluminacao as a04

    uniq = "aabbcc000002"
    escolha_dela = (True, False, False, False, True)

    #: O MERGE REAL, com os colaboradores dublados — o mesmo arranjo de
    #: `tests/unit/test_troca_de_player_01_a_escolha_sobrepoe.py:534`.
    backend = object.__new__(PyDualSenseController)
    backend._key_to_uniq = lambda k: k
    backend._desired_default = _DesiredOutput(
        player_leds=tuple(player_led_pattern(1)))   # o default global do perfil
    backend._assentar_mesa_locked = lambda: None
    backend._auto_output_provider = lambda u: _DesiredOutput(
        player_leds=tuple(player_led_pattern(2)))   # a camada AUTOMÁTICA
    backend._desired_coop_by_uniq = {}
    backend._scaled_led = lambda u, resolvido: resolvido
    backend._game_output_by_uniq = {}
    backend._game_wins = lambda: False
    backend._desired_by_uniq = {uniq: _DesiredOutput(player_leds=escolha_dela)}

    em_vigor = backend._merged_desired_for_key(uniq).player_leds
    assert em_vigor == escolha_dela, (
        "o override por-uniq deixou de vencer a camada automática — se o merge "
        "mudou, esta aba precisa saber antes de decidir o que pode afirmar.")
    assert em_vigor != tuple(player_led_pattern(2)), (
        "o dublê não separa as duas camadas: escolha um desenho diferente do "
        "automático, senão o teste passa sem medir nada.")

    #: E A TELA NÃO DIZ NADA SOBRE ISSO — nem o certo, nem o errado. As frases
    #: proibidas NÃO são digitadas aqui: são os três ramos SEM co-op do próprio
    #: motor, para a régua acompanhar se ele reescrever o texto.
    from hefesto_dualsense4unix.app.actions.lightbar_actions import (
        texto_do_desenho_aceso,
    )
    dica = a04.dica_da_luz("Cosmic Red", "BT", "")
    proibidas = [
        texto_do_desenho_aceso((False,) * 5, 1),            # automático com nº
        texto_do_desenho_aceso((False,) * 5, None),         # automático sem nº
        texto_do_desenho_aceso(tuple(player_led_pattern(2)), 1),  # escolha dela
    ]
    for afirmacao in proibidas:
        assert afirmacao not in dica, (
            f"a dica afirma {afirmacao!r} sobre o desenho em vigor, e o pacote "
            f"não vê o override por-uniq que o decide: {dica!r}")

    assert dica == "Cosmic Red (BT)", (
        f"sobrou algo além do que o pacote mede: {dica!r}")

    #: NEM PELO CAMINHO DE VERDADE — a coluna inteira, com a mesa de 02/09.
    luz = colunas()[DO_RADIO["uniq"]]["luz"]
    assert "automático" not in luz and "escolha sua" not in luz, luz


def test_o_coop_so_manda_quando_ha_mais_de_um_jogador():
    """`coop.enabled` NÃO responde "o co-op está ligado", e isso está medido.

    `app/actions/status_actions.texto_do_coop_derrubado` diz: *"``CoopManager.
    disable()`` não zera ``coop_enabled``, então o ``state_full`` segue
    publicando ``coop.enabled=True`` com ``coop.players=1`` — de fora,
    indistinguível de 'ela desligou o co-op'"*. É o estado da mesa dela HOJE.

    A MORDIDA: troque a leitura por `bool(coop.get("enabled"))` e a primeira
    linha reprova — a dica passaria a dizer, na mesa parada, que quem manda nas
    cinco luzes é o co-op.
    """
    import pacotes.a04_iluminacao as a04

    parado = {"coop": {"enabled": True, "players": 1, "mesa": [{"player": 1}]}}
    assert a04.o_coop_manda(parado) is False, (
        "`enabled=True` com um jogador é a mesa parada — ler o booleano faria "
        "a dica afirmar um co-op que ninguém ligou.")
    assert a04.o_coop_manda({"coop": {"enabled": True, "players": 3}}) is True
    assert a04.o_coop_manda({}) is False
    assert a04.o_coop_manda({"coop": None}) is False

    dica = a04.dica_da_luz("Cosmic Red", "BT", "", coop_manda=True)
    assert "co-op" in dica, dica


def test_a_frase_do_coop_e_a_do_motor_chamada_e_nao_uma_copia(monkeypatch):
    """A régua do reuso mede o ATO, e não a palavra.

    O DEFEITO QUE ELA FECHA, achado pela auditoria de 02/09/2026: a régua
    anterior era `assert _PREFIXO_DESENHO in luz` mais comparações contra
    strings digitadas no próprio teste. Arrancar a chamada ao motor e escrever
    a frase À MÃO no pacote deixava **os 31 testes verdes** — e a LEI 0 da casa
    (*"não temos que recriar nada"*) é justamente o que essa régua deveria
    proteger.

    Duas medições, e nenhuma é uma string digitada aqui:

    1. a frase que o pacote emite é, literalmente, o retorno de
       `texto_do_desenho_aceso`;
    2. o pacote CHAMOU a função — um espião no módulo do motor. Como
       `dica_da_luz` importa dentro do corpo, trocar o atributo do módulo pega
       a chamada de verdade.
    """
    from hefesto_dualsense4unix.app.actions import lightbar_actions
    import pacotes.a04_iluminacao as a04

    do_motor = lightbar_actions.texto_do_desenho_aceso((False,) * 5, None,
                                                       coop_ligado=True)
    assert do_motor in a04.dica_da_luz("Cosmic Red", "BT", "",
                                       coop_manda=True), (
        "a frase do co-op não é a do motor — escrever outra criaria a segunda "
        "verdade que a GTK já matou.")

    chamadas: list[tuple] = []

    def espiao(*args, **kw):
        chamadas.append((args, kw))
        return "ESPIÃO"

    monkeypatch.setattr(lightbar_actions, "texto_do_desenho_aceso", espiao)
    dica = a04.dica_da_luz("Cosmic Red", "BT", "", coop_manda=True)
    assert chamadas, (
        "o pacote não chamou `texto_do_desenho_aceso` — a frase foi copiada à "
        "mão, e é o defeito que esta régua existe para pegar.")
    assert "ESPIÃO" in dica, dica


def test_o_ramo_do_coop_do_motor_ignora_o_rascunho_e_o_numero():
    """Por que `dica_da_luz` pode passar sentinelas nos dois primeiros args.

    O pacote não sabe o rascunho (não vê o override por-uniq) nem precisa do
    número neste ramo, e passa `(False,) * 5` e `None`. Isso só é honesto
    enquanto o ramo 1 de `texto_do_desenho_aceso` devolver ANTES de olhar
    qualquer um dos dois.

    SE O MOTOR MUDAR, ESTE TESTE ACUSA — e o chamador em
    `a04_iluminacao.dica_da_luz` passa a estar mentindo sobre um rascunho
    vazio que ele nunca mediu.
    """
    from hefesto_dualsense4unix.app.actions.lightbar_actions import (
        texto_do_desenho_aceso,
    )

    sentinela = texto_do_desenho_aceso((False,) * 5, None, coop_ligado=True)
    for rascunho in ((False,) * 5, (True, False, True, False, True)):
        for slot in (None, 1, 4):
            assert texto_do_desenho_aceso(
                rascunho, slot, coop_ligado=True) == sentinela, (
                "o ramo do co-op passou a ler o rascunho ou o número — a aba "
                "04 não sabe nenhum dos dois e precisa parar de passá-los.")


def test_o_hex_e_o_do_dono_e_nao_um_guarda_copiado(colunas):
    """`cor_do_swatch` é o dono da leitura crua do `lightbar_rgb`.

    O guarda que estava em `_hex` (`len(rgb) < 3`) é o `_rgb3` do
    `controller_card`, cujo docstring pede para não ser repetido: *"com duas
    leituras do ``lightbar_rgb``, as duas abas divergiriam no primeiro caso de
    borda"*. E divergiam: uma lista de QUATRO canais passava na cópia e é
    recusada pelo dono.
    """
    from hefesto_dualsense4unix.app.widgets.controller_card import cor_do_swatch

    quatro = dict(DO_RADIO, lightbar_rgb=[0, 0, 255, 7])
    assert cor_do_swatch(quatro) is None
    assert colunas([quatro])[DO_RADIO["uniq"]]["hex"] == "—", (
        "a aba aceitou um `lightbar_rgb` fora do contrato do IPC e pintou uma "
        "cor a partir dele.")
    assert "rgb" not in colunas()[DO_RADIO["uniq"]], (
        "o `rgb` voltou: ele é uma LISTA, e o pintor pula lista em coluna "
        "(`if(v !== null && typeof v === 'object') continue`) — endereço morto "
        "que nem o `casamento.py` enxerga, porque ele filtra list e dict.")


# ---------------------------------------------------------------------------
# 6. a frase da disputa — o motor, não uma segunda verdade
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
    assert ROTULO_LIGHTBAR_SEGURADA in col["luz"], col["luz"]


def test_o_recado_conhece_os_estados_que_a_mao_nao_conhecia(colunas):
    """Quatro estados onde havia um: Nativo, disputa, desconhecida, apagada.

    ONDE A FRASE MORA, desde 02/09/2026: no `title` das TRÊS peças do desenho,
    dentro do `luz`. Ela era emitida num `data-campo="recado"` que NENHUMA das
    duas páginas tem — o único órfão que o `casamento.py` acusava nesta aba, e
    invisível à régua do mockup, que varre os endereços do ARQUIVO.

    A RESSALVA SÓ APARECE QUANDO EXISTE, e é isso que a última linha cobra:
    com a barra acesa numa cor conhecida o motor não tem o que ressalvar, e a
    dica fica só com o nome vivo e o desenho das lâmpadas. Aviso permanente
    vira paisagem, e paisagem ninguém lê.
    """
    def dica(conectados=None, estado=None):
        cols = colunas(conectados, estado) if estado is not None else colunas(conectados)
        return cols[DO_RADIO["uniq"]]["luz"]

    assert "Lightbar: apagada" in dica([dict(DO_RADIO, lightbar_on=False)])
    assert "Lightbar: cor desconhecida" in dica(
        [dict(DO_RADIO, lightbar_source="desconhecida")])
    assert "Em Nativo o jogo é dono do LED" in dica(
        [DO_RADIO], {"active_profile": "", "native_mode": True})
    limpa = dica()
    assert "Lightbar:" not in limpa and "Nativo" not in limpa, limpa


# ---------------------------------------------------------------------------
# 7. os gestos — a ponte com dublê, cobrando QUAL função e com quê
# ---------------------------------------------------------------------------
class PonteDeMentira:
    """A ponte com dublê: guarda o que foi chamado e com quê."""

    def __init__(self):
        self.chamadas: list = []

    def __getattr__(self, nome):
        def guardar(*a, **kw):
            self.chamadas.append((nome, a, kw))
            return (True, "")
        return guardar


def _clicar(gesto, clique, conectados=None):
    import pacotes

    ctx = pacotes.Contexto(state={}, mesa=MESA,
                          conectados=list(conectados or [DO_CABO]), estados={})
    p = PonteDeMentira()
    pacotes.gesto_da_pagina("04-iluminacao.html", gesto)(ctx, clique, p)
    return p


def test_o_automatico_pinta_a_cor_do_numero_do_motor():
    """Largar o claim e pintar a cor do slot — com o número que o motor dá.

    A linha era `player_slot or player or 1`: o `or 1` é a POSIÇÃO disfarçada de
    default, e um controle sem número nenhum ganharia a cor do P1.
    """
    from hefesto_dualsense4unix.core.led_control import player_slot_color

    p = _clicar("auto", {"uniq": DO_CABO["uniq"]})
    assert p.chamadas[0][0] == "chamar" and p.chamadas[0][1] == ("lightbar.reset",)
    assert p.chamadas[1] == ("led_set", (tuple(player_slot_color(2)),),
                             {"uniq": DO_CABO["uniq"]}), (
        f"o automático pintou {p.chamadas[1]!r}. O controle do cabo é o 2 pelo "
        f"`player_slot`; cair em 1 é a posição disfarçada de default.")


def test_a_conversao_do_hex_e_a_do_motor():
    """`core/led_control.hex_to_rgb` é o dono — a cópia daqui morreu em 02/09.

    A linha era `tuple(int(hexa[i:i+2], 16) for i in (0, 2, 4))`, escrita neste
    arquivo, que já importava o módulo dono ao lado (`player_slot_color`).
    """
    import inspect

    from pacotes import a04_iluminacao as pac

    p = _clicar("cor", {"uniq": DO_CABO["uniq"], "hex": "#FF8000"})
    assert p.chamadas == [("led_set", ((255, 128, 0),), {"uniq": DO_CABO["uniq"]})]
    # SEM O DOCSTRING: ele CITA a linha morta, para quem ler saber o que caiu, e
    # procurar no texto inteiro faria a régua reprovar quem documenta bem — o
    # defeito de forma que esta casa já nomeou cinco vezes.
    corpo = inspect.getsource(pac.cor).replace(pac.cor.__doc__ or "", "")
    assert "int(hexa" not in corpo, (
        "a conversão voltou a ser escrita à mão ao lado do dono que a faz.")
    assert "hex_to_rgb" in corpo


def test_o_hex_torto_recusa_com_a_razao_do_motor():
    """Recusar DIZENDO, e a frase é a do dono — não uma reescrita mais pobre."""
    with pytest.raises(ValueError) as caiu:
        _clicar("cor", {"uniq": DO_CABO["uniq"], "hex": "#F80"})
    assert "hex_to_rgb" in str(caiu.value), str(caiu.value)

    with pytest.raises(ValueError) as sem_dono:
        _clicar("cor", {"hex": "#FF8000"})
    assert "controle" in str(sem_dono.value)


def test_o_seletor_livre_manda_a_cor_pelo_valor():
    """O `<input type="color">` traz a cor em `value`, não em `data-hex`.

    Ele estava na página desde o desenho SEM endereço de gesto nenhum: ela
    escolhia uma cor fora da guia de oito e o clique nem chegava ao Python. O
    endereço (`data-gesto="cor"`) é atributo invisível ao
    `check_o_desenho_aprovado`, e o ouvinte do BOOTSTRAP já manda `valor`.
    """
    import onde

    p = _clicar("cor", {"uniq": DO_CABO["uniq"], "hex": "", "valor": "#00ff80",
                        "tipo": "input", "evento": "change"})
    assert p.chamadas == [("led_set", ((0, 255, 128),), {"uniq": DO_CABO["uniq"]})]

    bancada = onde.pagina("04-iluminacao.html").read_text(encoding="utf-8")
    assert bancada.count('class="livre" value="#0000ff" data-gesto="cor"') == 1


def test_abrir_o_seletor_livre_nao_manda_cor_nenhuma():
    """ABRIR não é APLICAR — e sem esta régua o gesto muda o aparelho dela.

    MEDIDO em 02/09/2026 com o BOOTSTRAP REAL avaliado dentro de um Chrome, com
    `window.webkit.messageHandlers` dublado::

        ela ABRE     {gesto:'cor', hex:'', valor:'#0000ff', tipo:'input', evento:'click'}
        ela ESCOLHE  {gesto:'cor', hex:'', valor:'#12ab34', tipo:'input', evento:'change'}

    O ouvinte escuta `click` E `change`, e um `<input type="color">` dispara
    `click` no instante da ABERTURA, carregando o valor VELHO — a cor cravada no
    arquivo pelo gerador. Ler o `valor` nesse clique mandava a barra dela para
    `#0000FF` antes de ela escolher; se ela cancelasse, a barra ficava numa cor
    que ela nunca pediu.

    E SAI CALADO, de propósito: recusar dizendo poria uma frase de erro na tela
    dela só por ela ter aberto um seletor. O ato é o `change`, e ele age.

    A MORDIDA: tire o `_so_abriu_o_seletor` do gesto e a primeira asserção
    reprova com `led_set((0, 0, 255))`.
    """
    p = _clicar("cor", {"uniq": DO_CABO["uniq"], "hex": "", "valor": "#0000ff",
                        "tipo": "input", "evento": "click"})
    assert p.chamadas == [], (
        f"abrir o seletor mandou {p.chamadas!r} ao aparelho. A cor é a CRAVADA "
        f"no arquivo pelo gerador, e a tela não a mostra em lugar nenhum.")

    # O BOTÃO DA GUIA NÃO É AFETADO: ele é um `<button>` com `data-hex`, e o
    # `click` dele é o gesto inteiro.
    p = _clicar("cor", {"uniq": DO_CABO["uniq"], "hex": "#FF8000",
                        "tipo": "button", "evento": "click"})
    assert p.chamadas == [("led_set", ((255, 128, 0),), {"uniq": DO_CABO["uniq"]})]


# ---------------------------------------------------------------------------
# 10. o botão que aceita o clique, não faz nada — e não diz
# ---------------------------------------------------------------------------
class PonteMuda:
    """A ponte com o daemon SEM RESPONDER: tudo devolve o `False` do bridge.

    `ipc_bridge._safe_call` devolve `(False, None)` para daemon offline, socket
    ausente, timeout de conexão e erro JSON-RPC do servidor — e `led_set` e
    `ponte.chamar` traduzem isso no `False` que este dublê imita. É o estado da
    máquina dela toda vez que o Hefesto não está de pé.
    """

    def __init__(self) -> None:
        self.chamadas: list = []

    def __getattr__(self, nome):
        def guardar(*a, **kw):
            self.chamadas.append((nome, a, kw))
            return False
        return guardar


def _clicar_mudo(gesto, clique, conectados=None):
    """O mesmo clique, com o daemon calado — e a ponte volta mesmo se levantar.

    Ela volta SEMPRE porque a metade que importa em dois destes testes é o que
    o gesto deixou de chamar depois da recusa; um `pytest.raises` em volta
    engoliria o objeto junto com a exceção.
    """
    import pacotes

    ctx = pacotes.Contexto(state={}, mesa=MESA,
                           conectados=list(conectados or [DO_CABO]), estados={})
    p = PonteMuda()
    p.erro = None
    try:
        pacotes.gesto_da_pagina("04-iluminacao.html", gesto)(ctx, clique, p)
    except RuntimeError as e:
        p.erro = e
    return p


#: OS TRÊS QUE ESCREVEM NO APARELHO. O quarto (`player`) já lia a resposta.
QUE_ESCREVEM = [("cor", {"hex": "#FF8000"}),  # (noqa-acento) chave do contrato
                ("apagar", {}), ("auto", {})]  # (noqa-acento) idem


@pytest.mark.parametrize("gesto,clique", QUE_ESCREVEM)
def test_o_botao_da_luz_recusa_dizendo_quando_o_daemon_nao_responde(gesto, clique):
    """Os três botões que ESCREVEM no aparelho leem a resposta — e falam.

    O DEFEITO, medido em 02/09/2026 com este mesmo dublê: `cor`, `apagar` e
    `auto` chamavam `p.led_set(...)` e `p.chamar(...)` **jogando fora o
    booleano**. Com o Hefesto desligado, o clique dela sumia: a barra não
    mudava, a tela não dizia nada, e o segundo clique parecia o primeiro.

    O contrato desta casa é explícito — *"o que o produto não faz não vira botão
    que finge: vira botão que RECUSA DIZENDO"* —, e o quarto gesto desta mesma
    aba (`player`) já o cumpria: ele lê `(ok, motivo)` e levanta `RuntimeError`.
    Os outros três eram os únicos calados.

    A MORDIDA: tire o `if not ok: raise` de qualquer um dos três e o caso dele
    reprova aqui, porque o gesto volta a sair sem exceção nenhuma.
    """
    p = _clicar_mudo(gesto, {"uniq": DO_CABO["uniq"], **clique})
    assert isinstance(p.erro, RuntimeError), (
        f"o gesto {gesto!r} saiu calado com o daemon mudo — chamou "
        f"{[c[0] for c in p.chamadas]!r} e não disse nada.")
    assert str(p.erro), "recusou com frase VAZIA, que é o mesmo silêncio"


def test_a_frase_da_recusa_e_a_do_motor_e_nao_uma_reescrita(monkeypatch):
    """A frase é `lightbar_actions._AVISO_HEFESTO_DESLIGADO`, LIDA do motor.

    LEI 0 desta casa: *"não temos que recriar nada"*. A janela GTK diz esta
    frase neste MESMO evento (`lightbar_actions.py:950-951` —
    `mensagem_de_secao_fora(resposta) or _AVISO_HEFESTO_DESLIGADO`, no ramo em
    que o `led.set` por `uniq` volta sem corpo). Escrever outra aqui criaria a
    segunda verdade que esta casa persegue: as duas telas diriam coisas
    diferentes sobre o mesmo daemon desligado.

    ESTA RÉGUA NASCEU MEDINDO A PALAVRA, e eu a peguei com a minha própria
    mordida em 02/09/2026. Ela era `assert do_motor in str(p.erro)` com
    `do_motor` lido do motor — o que parece reuso e não é: copiei a frase à mão
    para dentro do pacote, palavra por palavra, e os **38 testes ficaram
    verdes**. É o defeito exato que a auditoria deste mesmo dia nomeou noutro
    ponto desta aba: *a régua confunde a PALAVRA com o ATO*.

    O QUE MEDE O ATO é trocar o valor NO MOTOR e cobrar que a tela acompanhe:
    uma cópia à mão continua dizendo a frase velha, e aí a régua acusa.
    """
    from hefesto_dualsense4unix.app.actions import lightbar_actions

    do_motor = lightbar_actions._AVISO_HEFESTO_DESLIGADO
    for gesto, clique in QUE_ESCREVEM:
        p = _clicar_mudo(gesto, {"uniq": DO_CABO["uniq"], **clique})
        assert do_motor in str(p.erro), (
            f"o gesto {gesto!r} recusou com {str(p.erro)!r}, e a frase do "
            f"motor para este evento é {do_motor!r}.")

    #: A MEDIDA DO ATO: o motor troca a frase, e a tela tem de trocar junto.
    outra = "\x00o motor mudou de frase"
    monkeypatch.setattr(lightbar_actions, "_AVISO_HEFESTO_DESLIGADO", outra)
    for gesto, clique in QUE_ESCREVEM:
        p = _clicar_mudo(gesto, {"uniq": DO_CABO["uniq"], **clique})
        assert outra in str(p.erro), (
            f"o gesto {gesto!r} disse {str(p.erro)!r} com o motor dizendo "
            f"outra coisa — a frase foi COPIADA para dentro do pacote, e no "
            f"dia em que a GTK mudar a dela as duas telas divergem.")


def test_o_automatico_nao_pinta_a_cor_se_o_claim_nao_foi_largado():
    """Duas chamadas, dois desfechos — e a segunda não corre no escuro.

    O gesto `auto` é composto: LARGA o claim (`lightbar.reset`) e SÓ ENTÃO pinta
    a cor do slot. Se a primeira não passou, pintar depois deixaria a barra numa
    cor nova com o claim ainda no Hefesto — o oposto do que o botão promete
    (*"deixar o jogo escolher"*), e sem ninguém saber.
    """
    p = _clicar_mudo("auto", {"uniq": DO_CABO["uniq"]})
    assert [c[0] for c in p.chamadas] == ["chamar"], (
        f"o automático seguiu para a segunda chamada depois de a primeira "
        f"falhar: {p.chamadas!r}")
