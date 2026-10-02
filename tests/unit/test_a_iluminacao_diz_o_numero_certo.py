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
7. a fileira tem ONZE casas e nenhuma porta de cor fora dela — 11/09/2026,
   ordem dela. O que morava aqui era a régua do seletor de cores do sistema
   (*ABRIR não é APLICAR*): ele saiu da guia, e com ele a segunda porta do
   gesto ``cor``. A medição que o justificava não se perdeu — mora na docstring
   de ``a04_iluminacao._so_abriu_o_seletor``, que continua guardando o trilho e
   o interruptor pelo mesmo motivo com o tempo invertido.
"""
from __future__ import annotations

import pathlib
import re
import sys

import pytest

RAIZ = pathlib.Path(__file__).resolve().parents[2]
for _p in (str(RAIZ / "src"), str(RAIZ / "src" / "hefesto_dualsense4unix" / "interface")):
    if _p not in sys.path:
        sys.path.insert(0, _p)


#: A MESA DE 02/09/2026, na forma que `mesa_viva.mesa_do_estado` devolve — e o
MESA = [
    {"pref": "p1", "uniq": "aa:bb:cc:00:00:01", "jogador": 1, "cor": "cosmic-red",
     "nome": "Cosmic Red", "via": "BT", "transporte": "bt"},
    {"pref": "p2", "uniq": "aa:bb:cc:00:00:02", "jogador": 2, "cor": "starlight-blue",
     "nome": "Starlight Blue", "via": "USB", "transporte": "usb"},
]

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


def test_o_rotulo_nao_diz_travessao_com_o_botao_aceso(colunas):
    """O defeito, na forma exata em que foi fotografado."""
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


def test_o_rotulo_leva_o_nome_e_o_transporte(colunas):
    """`P1 • Cosmic Red • BT`, e não `P1`."""
    col = colunas()[DO_RADIO["uniq"]]
    assert col["identidade"] == "P1 • Cosmic Red • BT", col["identidade"]


def test_o_transporte_vem_do_agora_e_nao_do_desenho(colunas):
    """O HTML publicado diz `USB` no P1; o daemon diz `bt`. Vence o daemon."""
    col = colunas()[DO_RADIO["uniq"]]
    assert col["identidade"].endswith("• BT"), col["identidade"]


def test_sem_nome_na_mesa_o_rotulo_nao_inventa(colunas):
    """Sem item de mesa, travessão — nunca um nome de modelo cravado."""
    import pacotes

    ctx = pacotes.Contexto(state={}, mesa=[], conectados=[DO_CABO], estados={})
    col = pacotes.pacote_da_pagina("04-iluminacao.html", ctx)["colunas"][DO_CABO["uniq"]]
    assert col["identidade"] == "P2 • — • USB", col["identidade"]


def test_o_brilho_chega_com_o_por_cento(colunas):
    """A caixa ao lado da barra é de TEXTO, e o desenho escreve `82%`."""
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


def _dica_do_botao(fileira: str, n: int) -> str:
    """O `title` do botão daquele número, sem digitar a frase inteira."""
    achado = re.search(rf'data-player="{n}" title="([^"]*)"', fileira)
    assert achado, f"o botão {n} não saiu na fileira: {fileira}"
    return achado.group(1)


def _nome_na_mesa(controle: dict) -> str:
    """O nome com que a MESA chama aquele controle — não se digita aqui."""
    return next(c["nome"] for c in MESA if c["uniq"] == controle["uniq"])


def test_a_fileira_marca_o_numero_de_quem_e(colunas):
    """O `on` é do número DESTE controle, e ele é vivo."""
    cols = colunas()
    fileira = cols[DO_CABO["uniq"]]["players"]
    dois = _dica_do_botao(fileira, 2)
    assert _nome_na_mesa(DO_CABO) in dois and "Os dois trocam" not in dois, (
        f"o botão do número DESTE controle recebeu a dica da troca: {dois!r}")
    assert cols[DO_CABO["uniq"]]["players"].count('class="on"') == 1
    assert 'class="on" data-gesto="player" data-player="1"' in cols[DO_RADIO["uniq"]]["players"]


def test_a_dica_nao_nomeia_controle_que_nao_esta_na_mesa(colunas):
    """A dica não pode nomear quem não está na mesa."""
    fileira = colunas([DO_RADIO])[DO_RADIO["uniq"]]["players"]
    assert "Starlight Blue" not in fileira, (
        "a dica nomeou um controle que não está na mesa.")
    assert "— livre." not in fileira, (
        "com UM controle na mesa nenhum outro número está livre — os três "
        "seriam recusados pelo daemon.")


def test_um_numero_acima_da_mesa_nao_se_diz_livre(colunas):
    """O DEFEITO DE 03/09/2026, na forma em que foi clicado.

    Medido no produto INSTALADO, com UM DualSense no cabo e o daemon vivo. Os
    botões 2, 3 e 4 da fileira eram indistinguíveis do 1 — `disabled:false`,
    `aria-disabled:null`, `cursor:pointer` — e a dica dizia **"Player 3 —
    livre."**. O clique, medido::

        [data-controle="p1"] [data-gesto="player"][data-player="3"]
        desfecho: recusou dizendo RuntimeError: Esse número é maior do que a
                  quantidade de controles ligados

    *Livre* quer dizer disponível. A tela AFIRMAVA o contrário do que o produto
    faria, e com um controle na mesa isso valia para TRÊS dos quatro botões.

    A MORDIDA: troque `n > quantos` por `False` em `um_botao_de_player` e as
    três linhas abaixo reprovam com a dica "— livre." de volta.

    A DICA DIZ SÓ O NÚMERO DESDE 13/09/2026 (FRASES-E-DICAS-01). Até ali ela
    colava a frase da recusa, e a mesma frase chegava à tela como dica flutuante
    e como a caixa laranja da foto dela no índice da leva
    (`2026-09-13-A-TERCEIRA-LISTA-DELA-INDICE.md`, linha 19). O cinza e o
    `aria-disabled` dizem que o número não cabe.
    """
    from hefesto_dualsense4unix.app.ipc_bridge import _MOTIVOS_NUMERO

    fileira = colunas([DO_RADIO])[DO_RADIO["uniq"]]["players"]
    for n in (2, 3, 4):
        assert f'data-player="{n}" title="Player {n}">' in fileira, (
            f"o botão {n} fora da mesa não diz só o número: {fileira}")
    assert _MOTIVOS_NUMERO["numero_fora_da_mesa"] not in fileira, (
        "a frase da recusa voltou à dica do número fora — ela chegaria à tela "
        "como dica flutuante")
    assert fileira.count('class="fora" aria-disabled="true"') == 3, (
        "os três botões fora da mesa têm de se LER apagados, e não só na dica: "
        "até 03/09 eles eram pixel a pixel iguais ao número aceso.")
    assert 'class="on" data-gesto="player" data-player="1"' in fileira, (
        "o número DESTE controle continua aceso e clicável.")


def test_com_a_mesa_cheia_nenhum_numero_fica_fora(colunas):
    """A GUARDA da cura acima — sem ela, apagar botões seria a correção EXCESSIVA."""
    from hefesto_dualsense4unix.app.ipc_bridge import _MOTIVOS_NUMERO

    fileira = colunas()[DO_RADIO["uniq"]]["players"]
    dois = _dica_do_botao(fileira, 2)
    assert "Os dois trocam" in dois and _nome_na_mesa(DO_CABO) in dois, (
        f"com DOIS na mesa o número 2 tem dono e a dica é a da troca: {dois!r}")
    assert fileira.count("fora") == 2, (
        f"só o 3 e o 4 passam de uma mesa de dois: {fileira}")
    assert _MOTIVOS_NUMERO["numero_fora_da_mesa"] not in fileira, (
        "os números 1 e 2 não podem carregar a frase da recusa.")


def test_a_frase_da_recusa_nao_tem_copia_na_dica(colunas):
    """ERA `test_a_frase_da_recusa_tem_um_dono_so` — o contrato mudou em 13/09/2026.

    A dica CITAVA o produto: a frase com que `identity_number_set` recusa era
    lida da ponte, para não virar uma segunda cópia de texto de tela. Desde a
    FRASES-E-DICAS-01 a frase não chega à tela em forma nenhuma — nem como dica
    —, e a função que a colava saiu do pacote. O dono continua sendo um só, a
    ponte, e a frase vai ao diário quando o clique recusa.
    """
    from hefesto_dualsense4unix.app.ipc_bridge import _MOTIVOS_NUMERO
    from pacotes import a04_iluminacao as pac

    assert not hasattr(pac, "fora_da_mesa"), (
        "voltou ao pacote a função que colava a frase da recusa na dica")
    fileira = colunas([DO_RADIO])[DO_RADIO["uniq"]]["players"]
    assert _MOTIVOS_NUMERO["numero_fora_da_mesa"] not in fileira


def test_o_gerador_e_o_produto_desenham_o_mesmo_botao():
    """Um dono, dois chamadores — e a régua compara os dois lados.

    O `botao_player` do gerador foi apagado em 02/09; `aba04.py` passou a chamar
    `um_botao_de_player`. Se alguém reescrever um dos lados, este teste acusa
    antes de o desenho e o produto divergirem — que foi como a `novo-layout/`
    divergiu 25 KB sem ninguém ver.
    """
    from pacotes import a04_iluminacao as pac

    dono = {"nome": "Cosmic Red", "via": "USB", "cor": "cosmic-red"}
    botao = pac.um_botao_de_player("Cosmic Red", 1, 1, dono, quantos=2)
    assert botao.startswith('<button class="on" data-gesto="player" data-player="1"')
    # ele a régua da identidade acusa o `--plastico` do `<i>`, porque ela julga
    assert (f'<i class="dono" data-hef="{pac.endereco_do_anel(1)}"'
            f' data-hef-alvo="{pac.ALVO_DO_PLASTICO}"'
            f' style="--plastico:#ae335a"></i>1</button>') in botao, (
        f"o anel perdeu a cor do plástico ou o endereço: {botao!r}. O hex sai de "
        f"`monta.cor_da_zona`, que LÊ a folha que pinta o desenho.")
    assert 'data-campo=' not in botao, (
        "o botão voltou a ter endereço próprio — a fileira inteira é que tem, "
        "porque a pintura não sabe escrever CLASSE.")


def test_o_html_publicado_e_a_bancada_concordam_sobre_o_endereco():
    """Onde cada `data-campo` está, nos DOIS lados — e o par que ainda difere."""
    import monta
    import onde

    bancada = onde.pagina("04-iluminacao.html").read_text(encoding="utf-8")
    publicado = onde.pagina("04-iluminacao.html", publicado=True).read_text(
        encoding="utf-8")
    piso, teto = len(monta.CONECTADOS), len(monta.MESA)
    for lado, texto in (("bancada", bancada), ("publicado", publicado)):
        for quem, agulha in (
                ("a fileira de jogador", 'data-campo="players" data-hef-alvo="html"'),
                ("a barra de brilho", 'data-campo="brilho-pct" data-hef-alvo="largura"')):
            n = texto.count(agulha)
            assert piso <= n <= teto, (
                f"o {lado} tem {quem} endereçada em {n} lugar(es); a mesa tem "
                f"{piso} conectado(s) e {teto} lugares. Abaixo do piso, o dado "
                f"dela chega e não tem onde pousar; acima do teto, há endereço "
                f"repetido.")
        assert 'data-campo="player-1"' not in texto, (
            f"o {lado} ficou com os dois endereços: o da fileira e os dos "
            f"botões. Dois donos para o mesmo lugar é o que este projeto "
            f"persegue.")
    assert bancada.count('data-campo="brilho-pct" data-hef-alvo="largura"') == teto, (
        "a bancada deixou de endereçar a barra de brilho nos quatro lugares — "
        "o lugar que ganha um controle volta a não ter onde pousar o brilho")


def test_a_luz_e_desenho_e_nao_palavra(colunas):
    """O `.aceso` é um DESENHO; escrever nele uma palavra o APAGA."""
    col = colunas()[DO_RADIO["uniq"]]
    assert "aceso" not in col, (
        "a palavra voltou ao lugar do desenho: `textContent` num `.aceso` "
        "apaga as duas tiras e as cinco lâmpadas.")
    assert col["luz"].count('class="tira-luz') == 2, col["luz"]
    assert '<span class="luzinhas">' in col["luz"], (
        "as cinco lâmpadas do indicador não saíram no desenho vivo.")
    assert '<span class="pad"' in col["luz"], (
        "a moldura do touchpad sumiu do desenho vivo.")


def test_o_endereco_da_luz_esta_nas_duas_paginas():
    """`luz` na bancada E no publicado — **a espera acabou em 02/09/2026**.

    O QUE ESTE TESTE COBRAVA, e o próprio texto dele mandava apagar no dia em
    que acontecesse: enquanto o produto dissesse `data-campo="aceso"`, o pacote
    não podia emitir `aceso` — qualquer valor ali vira `textContent` e apaga o
    desenho. Ele exigia, com todas as letras, `'data-campo="luz"' not in
    publicado`.

    **ELA PUBLICOU** (`70b58116`, *"ela mandou publicar as sete"*), e o
    publicado passou a ter o endereço novo. A asserção da espera ficou VERMELHA
    no `dev` desde então — medido em 03/09/2026, antes de qualquer mudança
    desta frente: `grep -c 'data-campo="luz"' paginas/04-iluminacao.html` = 2.

    O que sobra é o que sempre importou, e agora dos DOIS lados: o endereço
    existe, e o nome velho não voltou.

    A MORDIDA: devolva `data-campo="aceso"` ao `coluna()` do `aba04.py`, rode
    o gerador, e a primeira asserção reprova.

    E A CONTA DEIXOU DE SER `== 2` EM 07/09/2026, pela mesma razão de
    `test_o_html_publicado_e_a_bancada_concordam_sobre_o_endereco`: a bancada e
    o publicado andam em gerações diferentes, e desde a função única do
    `aba04.py` o lugar que nasce vazio também carrega o endereço da luz. O que
    vale nos dois lados é o piso (toda coluna conectada) e o teto (a mesa).
    """
    import monta
    import onde

    piso, teto = len(monta.CONECTADOS), len(monta.MESA)
    for onde_esta, doc in (
            ("a bancada", onde.pagina("04-iluminacao.html").read_text(encoding="utf-8")),
            ("o publicado", onde.pagina("04-iluminacao.html", publicado=True)
             .read_text(encoding="utf-8"))):
        n = doc.count('data-campo="luz" data-hef-alvo="html"')
        assert piso <= n <= teto, (
            f"{onde_esta} endereça a luz em {n} lugar(es), e a mesa tem {piso} "
            f"conectado(s) de {teto}.")
        assert 'data-campo="aceso"' not in doc, (
            f"{onde_esta} voltou ao nome velho — e nele todo valor emitido "
            f"vira `textContent` e APAGA as duas tiras e as cinco lâmpadas.")


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
    #: *a régua media o mundo de ontem*.  (noqa-acento: verbo medir, imperfeito)
    #: **O ENDEREÇO MUDOU — 09/09/2026, COR-X-01.** Era um `data-campo="hex"`
    #: com `data-hef-alvo="classe"` por BOTÃO, e o alvo `classe` compara por
    assert bancada.count('data-campo="tons" data-hef-alvo="html"') == 4, (
        "a guia de cores voltou a não ter endereço de estado — ou ela deixou "
        "de nascer nos QUATRO lugares, e o P3 que ganha um controle volta a "
        "ficar sem onde trocar a cor.")
    assert bancada.count('class="tom') == 4 * len(pac.tons_da_guia()), (
        "a bancada e `tons_da_guia()` discordam sobre quantos tons a guia tem")

    from hefesto_dualsense4unix.core.led_control import player_slot_color

    for n in (1, 2):
        assert f'data-hex="{pac._hex(player_slot_color(n))}"' in bancada


def test_a_bancada_perdeu_a_dica_congelada_da_celula_de_leds():
    """A dica do `.aceso` saiu do ATRIBUTO da célula e entrou no desenho."""
    import onde

    bancada = onde.pagina("04-iluminacao.html").read_text(encoding="utf-8")
    assert '<div class="aceso" data-campo="luz" data-hef-alvo="html">' in bancada, (
        "a célula de LEDs voltou a carregar atributo cravado pelo gerador.")
    assert " aceso:" not in bancada, (
        "a palavra que ela mandou tirar voltou ao desenho.")
    import monta
    from pacotes import a04_iluminacao as pac

    for c in monta.CONECTADOS:
        esperada = pac.dica_da_luz(c["nome"], c["via"], "")
        assert bancada.count(f'title="{esperada}"') == 3, (
            f"as três peças da coluna de {c['nome']} — as duas tiras e o "
            f"indicador — deviam dizer a MESMA dica viva ({esperada!r}); a do "
            f"meio dizendo outra coisa é a botoeira de volta.")
    assert "Desenho que mandamos" not in bancada, (
        "a afirmação sobre o desenho das 5 luzes voltou ao desenho: este pacote "
        "não vê o override por-uniq que decide qual desenho está em vigor.")


def test_o_gerador_e_o_produto_desenham_a_mesma_luz():
    """Um dono, dois chamadores — o mesmo par da fileira de players."""
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
    """A barra APAGADA não pode virar um halo BRANCO — e o halo é `currentColor`."""
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


def test_a_tira_nao_acende_sob_steam_e_no_nativo_mostra_a_cor(colunas):
    """A pergunta da TIRA não é a que o segundo retorno do motor responde.

    `rotulo_lightbar` devolve `(ressalva, COR BASE DO ACCENT)`, e a base é a
    ÚLTIMA COR CONHECIDA — devolvida **também** no estado em que o próprio
    motor avisa que ela pode não estar no plástico::

        lightbar_disputada  → ("a Steam tem este controle aberto", rgb)

    Ali a base volta preenchida COM `lightbar_on` falso — o pacote lia isso
    como "está acesa" e a tira acendia. Medido em 02/09/2026, com o dublê de
    estado, ANTES da cura (saída literal da mesma sonda)::

        NATIVO + lightbar_on falso   background:#7EB8D4;color:#7EB8D4;opacity:1.0
        STEAM  + lightbar_on falso   background:#7EB8D4;color:#7EB8D4;opacity:1.0

    NOTA DATADA — 24/09/2026 (A-MIRA-NA-NAVEGACAO-01): o Nativo deixou de ser
    ressalva (`D-2409-NO-NATIVO-A-TELA-MOSTRA-A-COR`: a barra é do Hefesto no
    Nativo também). A barra apagada no Nativo é APAGADA, como em todo modo, e
    a acesa mostra a cor — a segunda metade desta régua cobra as duas.

    A MORDIDA: troque `base if recado is None else None` por `base` e a linha
    da Steam reprova — a tira volta a acender azul com a barra apagada.
    """
    apagado = dict(DO_RADIO, lightbar_on=False)
    sob_steam = colunas([dict(apagado, lightbar_disputada=True)])
    assert "color:transparent" in sob_steam[DO_RADIO["uniq"]]["luz"], (
        "com a Steam segurando o `fd` a tira acendeu com a barra apagada.")

    nativo = {"active_profile": "", "native_mode": True}
    apagada_no_nativo = colunas([apagado], nativo)[DO_RADIO["uniq"]]["luz"]
    assert "color:transparent" in apagada_no_nativo
    assert "Lightbar: apagada" in apagada_no_nativo
    acesa_no_nativo = colunas([DO_RADIO], nativo)[DO_RADIO["uniq"]]["luz"]
    assert "color:transparent" not in acesa_no_nativo, (
        "no Nativo a barra é do Hefesto, e a tira não mostrou a cor")
    assert "Nativo" not in acesa_no_nativo, acesa_no_nativo

    acesa = colunas([DO_RADIO])[DO_RADIO["uniq"]]["luz"]
    assert "color:transparent" not in acesa, (
        "a cura apagou a tira que o motor diz estar ACESA — uma régua que "
        "apaga tudo passa por qualquer defeito.")


def test_a_dica_da_luz_nao_diz_aceso_e_nomeia_quem_esta_conectado(colunas):
    """As duas decisões dela de 02/09/2026, na mesma frase."""
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
    nenhum campo do desejado por controle — `interface/aba02.py:698` já dizia
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

    backend = object.__new__(PyDualSenseController)
    backend._key_to_uniq = lambda k: k
    backend._desired_default = _DesiredOutput(
        player_leds=tuple(player_led_pattern(1)))
    backend._assentar_mesa_locked = lambda: None
    backend._auto_output_provider = lambda u: _DesiredOutput(
        player_leds=tuple(player_led_pattern(2)))
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

    from hefesto_dualsense4unix.app.actions.lightbar_actions import (
        texto_do_desenho_aceso,
    )
    dica = a04.dica_da_luz("Cosmic Red", "BT", "")
    proibidas = [
        texto_do_desenho_aceso((False,) * 5, 1),
        texto_do_desenho_aceso((False,) * 5, None),
        texto_do_desenho_aceso(tuple(player_led_pattern(2)), 1),
    ]
    for afirmacao in proibidas:
        assert afirmacao not in dica, (
            f"a dica afirma {afirmacao!r} sobre o desenho em vigor, e o pacote "
            f"não vê o override por-uniq que o decide: {dica!r}")

    assert dica == "Cosmic Red (BT)", (
        f"sobrou algo além do que o pacote mede: {dica!r}")

    luz = colunas()[DO_RADIO["uniq"]]["luz"]
    assert "automático" not in luz and "escolha sua" not in luz, luz


def test_o_coop_so_manda_quando_ha_mais_de_um_jogador():
    """`coop.enabled` NÃO responde "há mais de um jogador", e isso está medido.

    `app/actions/status_actions.texto_do_coop_derrubado` diz: *"``CoopManager.
    disable()`` não zera ``coop_enabled``, então o ``state_full`` segue
    publicando ``coop.enabled=True`` com ``coop.players=1``"*. É o estado de
    toda mesa de um controle só.

    A MORDIDA: troque a leitura por `bool(coop.get("enabled"))` e a primeira
    linha reprova — o gesto `player` pediria um `coop.sync` inútil numa mesa
    de um jogador só.
    """
    import pacotes.a04_iluminacao as a04

    parado = {"coop": {"enabled": True, "players": 1, "mesa": [{"player": 1}]}}
    assert a04.o_coop_manda(parado) is False, (
        "`enabled=True` com um jogador é a mesa de um controle só — ler o "
        "booleano faria o gesto reconciliar uma camada que não existe.")
    assert a04.o_coop_manda({"coop": {"enabled": True, "players": 3}}) is True
    assert a04.o_coop_manda({}) is False
    assert a04.o_coop_manda({"coop": None}) is False


def test_o_hex_e_o_do_dono_e_nao_um_guarda_copiado(colunas):
    """`cor_do_swatch` é o dono da leitura crua do `lightbar_rgb`."""
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
    """Os estados onde havia um: disputa, desconhecida, apagada.

    NOTA DATADA — 24/09/2026 (A-MIRA-NA-NAVEGACAO-01): eram quatro, e o
    Nativo saiu (`D-2409-NO-NATIVO-A-TELA-MOSTRA-A-COR`): com a barra acesa
    numa cor conhecida, o Nativo não tem o que ressalvar.

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
    assert "Nativo" not in dica([DO_RADIO], {"active_profile": "", "native_mode": True})
    limpa = dica()
    assert "Lightbar:" not in limpa and "Nativo" not in limpa, limpa


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


def test_o_botao_por_controle_do_automatico_saiu_com_o_widget():
    """Ela mandou tirar os três cantos que falavam de automático — 07/09/2026.

    O TESTE QUE MORAVA AQUI media o gesto do botão  # noqa-acento: verbo medir
    `Automático` de cada coluna:
    que ele largava o claim e pintava a cor do slot com o número que o MOTOR dá,
    e não com o `or 1` que era a posição disfarçada de default. O gesto saiu com
    o widget, no mesmo commit, por ordem dela — e um teste que continua
    exigindo o gesto reprovaria a ordem em vez do defeito.

    **O QUE ELE PROTEGIA NÃO SE PERDEU, e é isto que autoriza a troca:** a queda
    proibida (`player_slot or player or 1`) tinha DOIS chamadores neste pacote,
    e o outro está vivo — `_a_cor_de_agora`, que responde a cor do controle
    quando o motor não a afirma. A asserção abaixo mede ESSE, com o mesmo
    controle e a mesma pergunta: o número sai do motor, e cair em 1 é a posição
    disfarçada de default.

    A MORDIDA: troque `_numero(ctx, c)` por `1` em `_a_cor_de_agora` e esta
    linha reprova; registre de novo o gesto e a primeira reprova.
    """
    import pacotes
    from hefesto_dualsense4unix.core.led_control import player_slot_color
    from pacotes import a04_iluminacao as pac

    assert pacotes.gesto_da_pagina("04-iluminacao.html", "auto") is None, (
        "o gesto do botão POR CONTROLE voltou ao pacote sem o widget que o "
        "oferecia — ela mandou tirar os dois botões do automático em "
        "07/09/2026, e a poda acompanha a peça")

    # régua errava aí: com o `DO_CABO` inteiro ela media o SWATCH,  # noqa-acento: verbo medir
    mudo = {k: v for k, v in DO_CABO.items() if k != "lightbar_rgb"}
    ctx = pacotes.Contexto(state={"active_profile": "regua"}, mesa=list(MESA),
                           conectados=[mudo], estados={})
    assert pac._a_cor_de_agora(ctx, {}, mudo) == player_slot_color(2), (
        "a cor de queda deixou de ser a do número que o motor dá — o controle "
        "do cabo é o 2 pelo `player_slot`, e cair em 1 é a posição disfarçada "
        "de default")
    assert player_slot_color(1) != player_slot_color(2)


def test_a_conversao_do_hex_e_a_do_motor():
    """`core/led_control.hex_to_rgb` é o dono — a cópia daqui morreu em 02/09.

    A linha era `tuple(int(hexa[i:i+2], 16) for i in (0, 2, 4))`, escrita neste
    arquivo, que já importava o módulo dono ao lado (`player_slot_color`).
    """
    import inspect

    from pacotes import a04_iluminacao as pac

    p = _clicar("cor", {"uniq": DO_CABO["uniq"], "hex": "#FF8000"})
    assert p.chamadas == [("led_set_detalhado", ((255, 128, 0),),
                          {"brightness": None, "uniq": DO_CABO["uniq"]})]
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


def test_a_casa_hachurada_saiu_e_o_gesto_nao_aceita_cor_sem_tom():
    """A segunda porta do gesto `cor` morreu inteira — 11/09/2026, ordem dela."""
    import onde

    bancada = onde.pagina("04-iluminacao.html").read_text(encoding="utf-8")
    assert '<input type="color"' not in bancada, (
        "o campo de cor do sistema voltou à fileira — e o gesto dele morreu "
        "junto, então ele seria um clique sem resposta")
    assert 'class="livre"' not in bancada

    with pytest.raises(ValueError) as sem_tom:
        _clicar("cor", {"uniq": DO_CABO["uniq"], "hex": "", "valor": "#00ff80",
                        "tipo": "input", "evento": "change"})
    assert "qual tom" in str(sem_tom.value)

    p = _clicar("cor", {"uniq": DO_CABO["uniq"], "hex": "#FF8000",
                        "tipo": "button", "evento": "click"})
    assert p.chamadas == [("led_set_detalhado", ((255, 128, 0),),
                          {"brightness": None, "uniq": DO_CABO["uniq"]})]


def test_os_tres_tons_sairam_dos_quatro_controles():
    """Um azul, um rosa e o preto — 11/09/2026, e a poda é de tela, não do daemon.

    *"remover um tom de azul. um tom de rosa e o tom de preto de todas as
    cores pros 4 controles."*

    QUAL AZUL E QUAL ROSA foi MEDIDO, não escolhido a gosto: sai o tom mais
    perto do vizinho que fica (distância de matiz). O azul se decide sozinho
    — `#0080FF` a 29,88° do vizinho contra 30,12° do `#0000FF` —, e o rosa
    empata em 29,88°, com o desempate na razão de produto: o corte é na metade
    que NÃO é cor automática de jogador, porque tirar da outra deixaria um
    controle no número 4 sem tom marcado na fileira.

    O DAEMON NÃO PERDEU NADA, e é a metade que esta régua também mede: as oito
    cores automáticas continuam inteiras em `player_slot_color`, e os catorze
    tons continuam em `monta.TOM_DA_CASA`. O que encolheu foi a GUIA.

    A MORDIDA: tire um hex de `FORA_DA_GUIA` e a primeira asserção reprova
    dizendo qual voltou.
    """
    import onde

    from hefesto_dualsense4unix.core.led_control import player_slot_color

    from pacotes import a04_iluminacao as pac

    crus = ["#{:02X}{:02X}{:02X}".format(*rgb) for rgb in pac.tons_da_guia()]

    bancada = onde.pagina("04-iluminacao.html").read_text(encoding="utf-8")
    for h in ("#0080FF", "#FF00FF", "#000000"):
        assert h not in crus, f"{h} continua na guia"
        assert f'data-hex="{h}"' not in bancada, (
            f"{h} voltou à fileira da página — ela mandou os três saírem")

    assert len(crus) == 11, crus
    assert bancada.count('class="tom') == 4 * len(crus)

    for n in range(1, 9):
        assert "#{:02X}{:02X}{:02X}".format(*player_slot_color(n)) == crus[n - 1], (
            "a guia deixou de começar pelas oito cores automáticas, e "
            "`titulo_da_casa` numera as oito primeiras casas pela POSIÇÃO")


def test_a_poda_da_guia_recusa_dizendo_o_que_nao_pode_podar():
    """`FORA_DA_GUIA` sabe RECUSAR, e as duas recusas são diferentes."""
    from pacotes import a04_iluminacao as pac

    antes = pac.FORA_DA_GUIA
    try:
        pac.FORA_DA_GUIA = ("#123456",)
        with pytest.raises(ValueError) as fantasma:
            pac.tons_da_guia()
        assert "não conhece" in str(fantasma.value)

        pac.FORA_DA_GUIA = ("#FF0080",)
        with pytest.raises(ValueError) as automatica:
            pac.tons_da_guia()
        assert "automática" in str(automatica.value)
    finally:
        pac.FORA_DA_GUIA = antes
    assert len(pac.tons_da_guia()) == 11


class PonteMuda:
    """A ponte com o daemon SEM RESPONDER — e o "não respondeu" tem DUAS formas.

    `ipc_bridge._safe_call` devolve `(False, None)` para daemon offline, socket
    ausente, timeout de conexão e erro JSON-RPC do servidor. Quem traduz isso
    para o chamador são duas funções com contratos diferentes, e o dublê tem de
    imitar as duas — senão ele deixa de medir o silêncio que existe para medir:

        `led_set` / `ponte.chamar`   `bool` → `False`
        `led_set_detalhado`          `dict | None` → `None` (`_corpo_do_daemon`)

    ELE DEVOLVIA `False` PARA TUDO até 03/09/2026, e isso era certo enquanto a
    aba escrevia pela porta booleana. Com a `_detalhado`, um `False` não é
    "não respondeu": é um corpo que não é dicionário, e `frase_do_desfecho` o
    lê como *"não há resposta do daemon a ler"* e cai na heurística — que sem
    pendência nenhuma devolve a frase do APLICADO. O dublê passaria a provar o
    contrário do que promete.
    """

    def __init__(self) -> None:
        self.chamadas: list = []

    def __getattr__(self, nome):
        def guardar(*a, **kw):
            self.chamadas.append((nome, a, kw))
            return None if nome.endswith("_detalhado") else False
        return guardar


def _clicar_mudo(gesto, clique, conectados=None):
    """O mesmo clique, com o daemon calado — e a ponte volta mesmo se levantar."""
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


QUE_ESCREVEM = [("cor", {"hex": "#FF8000"}),  # (noqa-acento) chave do contrato
                ("apagar", {})]  # (noqa-acento) idem


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
    """A frase é `lightbar_actions._AVISO_HEFESTO_DESLIGADO`, LIDA do motor."""
    from hefesto_dualsense4unix.app.actions import lightbar_actions

    do_motor = lightbar_actions._AVISO_HEFESTO_DESLIGADO
    for gesto, clique in QUE_ESCREVEM:
        p = _clicar_mudo(gesto, {"uniq": DO_CABO["uniq"], **clique})
        assert do_motor in str(p.erro), (
            f"o gesto {gesto!r} recusou com {str(p.erro)!r}, e a frase do "
            f"motor para este evento é {do_motor!r}.")

    outra = "\x00o motor mudou de frase"
    monkeypatch.setattr(lightbar_actions, "_AVISO_HEFESTO_DESLIGADO", outra)
    for gesto, clique in QUE_ESCREVEM:
        p = _clicar_mudo(gesto, {"uniq": DO_CABO["uniq"], **clique})
        assert outra in str(p.erro), (
            f"o gesto {gesto!r} disse {str(p.erro)!r} com o motor dizendo "
            f"outra coisa — a frase foi COPIADA para dentro do pacote, e no "
            f"dia em que a GTK mudar a dela as duas telas divergem.")


# Ele media que o botão POR CONTROLE não pintava a cor nova  # noqa-acento: verbo medir


def test_a_coluna_que_esvazia_le_como_a_que_nasce_vazia():
    """`.vazia` e `.off` são o mesmo fato, e tinham duas leituras.

    `.vazia` é o lugar que NASCE sem controle; `.off` é o mesmo lugar depois que
    o controle SAIU — quem escreve a classe é
    `pacotes.apagar_os_lugares_sem_dono`. Medido em 03/09/2026 na página
    publicada, com UM controle no cabo: esta folha não tinha **uma** regra
    `.off` (zero ocorrências, contra 11 na Jogar e 10 na Controles), e a coluna
    do P2 ficava meio apagada — que o próprio `pacotes/__init__.py` chama de
    *"pior que aceso"*.

    O QUE FOI MEDIDO NO WEBKIT VIVO, na coluna que esvaziou:

        moldura   borderColor rgb(126,184,212)  ← Starlight Blue, do MOCKUP
        os 8 tons backgroundColor rgb(126,184,212), cursor pointer
        trilho    width 100% ao lado de um "—"
        Desligar / Automático acesos, e os dez endereços daquela coluna
                  levantam `ValueError`, que `_recusou_dizendo` NÃO leva à tela

    A MORDIDA: apague o bloco `.ctrl.off` do `CSS` da `aba04.py`, regere, e as
    quatro asserções abaixo reprovam.
    """
    import onde

    doc = onde.pagina("04-iluminacao.html").read_text(encoding="utf-8")
    assert ".ctrl.off" in doc, (
        "a folha desta aba voltou a não ter regra nenhuma para o lugar que "
        "esvazia — era o estado do defeito de 03/09/2026.")
    assert ".luz-grade .ctrl.off .moldura{color:var(--linha) !important" in doc, (
        "sem `!important` a regra não vence o `style=` INLINE do gerador, e a "
        "coluna vazia continua com a cor de um controle que não está lá.")
    # A CHAVE PASSOU DE `.off` PARA `[data-conectado="nao"]` EM 07/09/2026, e a
    for peca in ('.luz-grade .ctrl[data-conectado="nao"] .guia',
                 '.luz-grade .ctrl[data-conectado="nao"] .trilho',
                 '.luz-grade .ctrl[data-conectado="nao"] .cel-acoes .btn'):
        assert peca in doc, (
            f"{peca} voltou à tela num lugar sem controle: botões que "
            f"engolem o toque sem uma letra.")
    assert ('.luz-grade .ctrl[data-conectado="nao"] .cel-cor .hex.reenvia'
            "{pointer-events:none" in doc), (
        "a caixa do hexadecimal voltou a aceitar clique num lugar sem "
        "controle — ela leva `data-gesto=\"reenviar\"` nos quatro lugares "
        "desde 07/09/2026, e sem esta regra o clique levanta `o clique não "
        "disse em qual controle`, que o cartão do piloto não leva à tela.")
    grade = doc.split('<div class="luz-grade">', 1)[-1].split('<div class="rodape"', 1)[0]
    for coluna in re.findall(
            r'<div class="ctrl vazia"(.*?)(?=<div class="ctrl[" ]|\Z)', grade, re.S):
        # atributos (o `data-campo="plastico"` e, dentro, o bloco dos tons),
        for peca in ('class="guia"', 'class="puxador"',
                     'data-gesto="apagar"', 'data-gesto="reenviar"'):
            assert peca in coluna, (
                f"o lugar que NASCE vazio perdeu {peca!r} — o controle que "
                f"chegar ali fica sem esse gesto na tela, e só recarregar a "
                f"página desfaz.")
    assert doc.count('<span class="nada">—</span>\n          </div>') >= 2, (
        "a célula `Opções` da coluna viva perdeu o travessão escondido: quando "
        "ela esvaziar, a linha fica em BRANCO enquanto o P3 e o P4 mostram —.")
    # E O SELETOR VIROU `[data-conectado="sim"]` EM 07/09/2026: o
    # `:not(.vazia):not(.off)` media o NASCIMENTO, e o que  (noqa-acento) medir
    assert '.luz-grade .ctrl[data-conectado="sim"] .cel-acoes .nada{display:none}' in doc, (
        "a regra que esconde o travessão da coluna VIVA sumiu, ou voltou a "
        "medir o NASCIMENTO: sem ela o lugar que ganha um controle mostra o "
        "travessão ao lado dos dois botões, e sem a ressalva ela apaga o "
        "travessão do P3/P4 parados — as duas regressões, medidas em 03/09 e "
        "em 07/09/2026.")
