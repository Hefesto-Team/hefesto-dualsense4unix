"""O brilho viaja com a cor, e a tela deixa de mostrar uma cor que ela não pediu.

TRÊS DEFEITOS, UMA RAIZ — medidos em 03/09/2026. A raiz é o contrato do daemon,
e ele estava escrito o tempo todo em `daemon/ipc_handlers.py`, no bloco
"Contrato de cor (D8)" de `_enrich_controllers_per_controller`::

    expõe-se UMA cor, a efetiva conhecida (PÓS-ESCALA DE BRILHO — o
    `_DesiredOutput.led` já é pós-escala; o manager pré-escala na borda)

A aba `04` lia esse `lightbar_rgb` como se fosse a cor ESCOLHIDA. Com o brilho
em 50% e o azul do P1, o daemon publica `#00007F`, e a mesma coluna::

    a caixa `#RRGGBB`   dizia `#00007F`, uma cor que ela nunca pediu
    a marca dos 8 tons  APAGAVA em todos — os `data-hef-quando` do HTML são os
                        oito CHEIOS (`#0000FF`…), e nenhum casa com `#00007F`
    a tira              pintava o hex CRU (o `tom_da_casa` só conhece os oito
                        cheios) e ainda aplicava `opacity:0.5` por cima

E O QUARTO, que é de ESCRITA e o pior deles: o gesto `cor` chamava
`p.led_set(rgb, uniq=uniq)` **sem `brightness`**. O `_payload_led_set` só põe o
campo quando ele é passado, e o `led.set` do daemon diz *"Ausente ou inválido ->
assume 1.0"*. Ou seja: a coluna mostrava `50%` e o fio levava 100% — um clique
num tom DESFAZIA o brilho que ela tinha escolhido na janela GTK, sem uma palavra
na tela. A GTK manda o brilho em toda escrita (`lightbar_actions.py:944`).

O QUE ESTES TESTES COBREM, cada um com a mordida escrita:

1. `brilho_do_controle` lê o override antes do global, e `None` é "não sei";
2. `cor_escolhida` devolve os OITO tons da guia em qualquer brilho — a marca
   sobrevive; e devolve a EFETIVA quando ninguém sabe de que pedido ela veio;
3. a tira volta ao tom da casa em vez do hex cru;
4. o gesto `cor` manda o `brightness` — a mordida do defeito de escrita;
5. o `apagar` e o `auto` mandam pela mesma porta, e o `auto` na ordem certa;
6. o desfecho sai do CORPO do daemon: calado quando aplicou, com a frase do
   produto no cartão quando NÃO aplicou;
7. o `pacote()` inteiro emite a cor pedida no `hex`, com o brilho reduzido.
"""
from __future__ import annotations

import pathlib
import sys

import pytest

RAIZ = pathlib.Path(__file__).resolve().parents[2]
for _p in (str(RAIZ / "src"), str(RAIZ / "src" / "hefesto_dualsense4unix" / "interface")):
    if _p not in sys.path:
        sys.path.insert(0, _p)

#: MAC da faixa sintética da casa — há dois portões de anonimato nesta árvore.
UNIQ = "aa:bb:cc:00:00:01"

MESA = [
    {"pref": "p1", "uniq": UNIQ, "jogador": 1, "cor": "white",
     "nome": "White", "via": "USB", "transporte": "usb"},
]

ACESO = {"uniq": UNIQ, "index": 0, "transport": "usb", "connected": True,
         "player": 1, "player_slot": 1, "is_primary": True,
         "lightbar_rgb": [0, 0, 255], "lightbar_on": True,
         "lightbar_source": "sysfs"}


@pytest.fixture
def a04():
    from pacotes import a04_iluminacao

    return a04_iluminacao


@pytest.fixture
def ctx():
    import pacotes

    return pacotes.Contexto(state={"active_profile": "regua"}, mesa=list(MESA),
                            conectados=[dict(ACESO)], estados={})


class PonteDeMentira:
    """Um dublê da ponte que devolve o CORPO que o teste mandar.

    Ele é irmão do `PonteDeMentira` de `test_os_botoes_tem_dono.py`, e a
    diferença é a razão de existir: aquele responde `True` a qualquer nome, o
    que basta para provar QUE função foi chamada. Aqui a pergunta é outra — o
    que o gesto FAZ com a resposta —, e para isso o corpo precisa ser o do
    daemon: `aplicado_em`/`guardado_em`, como o `led.set` os publica.
    """

    def __init__(self, corpo=None):
        self.corpo = corpo
        self.chamadas: list[tuple[str, tuple, dict]] = []

    def __getattr__(self, nome: str):
        def registrar(*args, **kwargs):
            self.chamadas.append((nome, args, kwargs))
            if nome == "chamar":
                return True
            return self.corpo

        return registrar


def _com_o_perfil(monkeypatch, a04, perfil_falso):
    """Faz o pacote ler ESTE perfil, sem tocar o disco dela.

    O `perfil.ativo` abre o JSON do perfil ativo, e escrever um em disco só para
    a régua faria o teste depender do lar de mentira do `conftest` — que existe,
    mas prova outra coisa. O que se mede aqui é o que a aba FAZ com o número.
    """
    monkeypatch.setattr(a04.perfil, "ativo", lambda _nome: perfil_falso)


# ---------------------------------------------------------------------------
# 1. o brilho tem UM dono, e ele lê o override antes do global
# ---------------------------------------------------------------------------
def test_o_brilho_le_o_override_antes_do_global(a04):
    """A ordem é a do merge do `profiles/schema.py`, e `None` é "não sei".

    A MORDIDA: troque a ordem — leia o global antes do override — e a primeira
    linha reprova. Faça `None` virar `1.0` e a última reprova, que é a diferença
    entre *"ela escolheu cheio"* e *"ninguém escolheu nada"*: o `led.set` OMITE
    o campo ausente, e omitir é o retrocompatível.
    """
    p = {"leds": {"lightbar_brightness": 0.4},
         "controllers": {UNIQ: {"leds": {"lightbar_brightness": 0.9}}}}
    assert a04.brilho_do_controle(p, UNIQ) == pytest.approx(0.9)
    assert a04.brilho_do_controle(p, "aa:bb:cc:00:00:02") == pytest.approx(0.4)
    assert a04.brilho_do_controle({"leds": {}}, UNIQ) is None
    assert a04.brilho_do_controle({}, UNIQ) is None
    assert a04.brilho_do_controle(None, UNIQ) is None
    assert a04.brilho_do_controle({"leds": {"lightbar_brightness": "xis"}},
                                  UNIQ) is None


# ---------------------------------------------------------------------------
# 2. a cor pedida volta dos oito tons, em qualquer brilho
# ---------------------------------------------------------------------------
def test_os_oito_tons_voltam_inteiros_em_qualquer_brilho(a04):
    """A marca da cor escolhida sobrevive ao brilho — e é isso que ela vê.

    A MORDIDA: faça `cor_escolhida` devolver a efetiva sempre (que é o que a aba
    fazia até hoje) e as quatro faixas de brilho reprovam de uma vez. Troque a
    varredura por uma DIVISÃO (`round(canal / brilho)`) e o `0.5` reprova: o
    `#00007F` dividido dá 254, e a marca continuaria apagada por UM.
    """
    for brilho in (0.9, 0.82, 0.5, 0.25, 0.1):
        for tom in a04.tons_da_guia():
            acesa = a04._com_o_brilho(tom, brilho)
            assert a04.cor_escolhida(acesa, brilho) == tom, (
                f"a {brilho:.0%} o tom {a04._hex(tom)} acende "
                f"{a04._hex(acesa)} e a tela não soube voltar dele — a marca "
                f"dos oito botões apaga, e ela deixa de ver qual cor escolheu.")


def test_a_cor_livre_volta_como_esta_no_plastico(a04):
    """Sem casamento, a EFETIVA volta inteira — inventar um pedido seria pior.

    A MORDIDA: faça o `return` final devolver o primeiro tom da guia em vez da
    efetiva e esta linha reprova. A tela passaria a afirmar uma escolha que
    ninguém fez, que é a família de defeito que esta aba inteira persegue.
    """
    livre = (0x12, 0xAB, 0x34)
    acesa = a04._com_o_brilho(livre, 0.82)
    assert acesa not in a04.tons_da_guia()
    assert a04.cor_escolhida(acesa, 0.82) == acesa


def test_a_cem_por_cento_e_sem_brilho_nada_se_mexe(a04):
    """As duas escalas são a mesma a 100%, e `None` quer dizer "não sei"."""
    assert a04.cor_escolhida((1, 2, 3), 1.0) == (1, 2, 3)
    assert a04.cor_escolhida((1, 2, 3), None) == (1, 2, 3)
    assert a04.cor_escolhida(None, 0.5) is None


def test_a_conta_do_brilho_e_a_do_produto(a04):
    """`_com_o_brilho` é `LedSettings.apply_brightness`, e não uma cópia dela.

    A MORDIDA: troque o corpo por `round(c * b)` — que é a conta "natural" que
    alguém escreveria — e esta linha reprova, porque o produto TRUNCA. É a mesma
    conta do `_handle_led_set` do daemon, e é dela que depende a varredura ser
    exata.
    """
    from hefesto_dualsense4unix.core.led_control import LedSettings

    for brilho in (0.82, 0.5, 0.33):
        for tom in a04.tons_da_guia():
            assert a04._com_o_brilho(tom, brilho) == tuple(
                LedSettings(lightbar=tom).apply_brightness(brilho).lightbar)


# ---------------------------------------------------------------------------
# 3. a tira volta ao tom da casa
# ---------------------------------------------------------------------------
def test_a_tira_volta_ao_tom_da_casa_com_o_brilho_reduzido(a04):
    """Com o hex cru a tira acendia uma cor que a guia não mostra em lugar nenhum.

    A MORDIDA: pinte a tira com `_tinta(acesa)` — o que a aba fazia até hoje — e
    a segunda linha reprova, porque `tom_da_casa` devolve o desconhecido COMO
    VEIO e `#00007F` não está na tabela dos oito.
    """
    acesa = a04._com_o_brilho((0, 0, 255), 0.5)
    assert a04._tinta(acesa) == a04._hex(acesa), (
        "a premissa deste teste caiu: `tom_da_casa` passou a conhecer a cor "
        "escurecida, e o defeito que ele mede mudou de forma.")
    assert a04._tinta(a04.cor_escolhida(acesa, 0.5)) != a04._hex(acesa)


# ---------------------------------------------------------------------------
# 4. O GESTO MANDA O BRILHO — a mordida do defeito de escrita
# ---------------------------------------------------------------------------
def test_o_gesto_da_cor_manda_o_brilho_do_perfil(a04, ctx, monkeypatch):
    """O número que a coluna MOSTRA é o que vai no fio.

    A MORDIDA: apague o `brightness=brilho` da chamada em `_escrever_a_cor` e
    esta linha reprova. Foi exatamente esse o defeito: o `_payload_led_set` só
    inclui o campo quando ele é passado, e o daemon assume 1.0 na ausência —
    a barra ia a 100% com a tela dizendo 50%.
    """
    import pacotes

    _com_o_perfil(monkeypatch, a04, {"leds": {"lightbar_brightness": 0.5}})
    p = PonteDeMentira({"status": "ok", "aplicado_em": [UNIQ], "guardado_em": []})
    fn = pacotes.gesto_da_pagina("04-iluminacao.html", "cor")
    fn(ctx, {"controle": "p1", "uniq": UNIQ, "hex": "#FF8000"}, p)

    nome, args, kw = p.chamadas[0]
    assert nome == "led_set_detalhado"
    assert args == ((255, 128, 0),)
    assert kw.get("brightness") == pytest.approx(0.5), (
        f"a cor saiu com brightness={kw.get('brightness')!r}. Sem o campo, o "
        f"`led.set` assume 1.0 e o clique DESFAZ o brilho que ela escolheu.")
    assert kw.get("uniq") == UNIQ


def test_o_brilho_do_override_e_o_que_viaja(a04, ctx, monkeypatch):
    """O override por controle vence o global também na ESCRITA, não só na tela.

    A MORDIDA: faça `_escrever_a_cor` ler `p["leds"]["lightbar_brightness"]`
    direto em vez de chamar `brilho_do_controle` e esta linha reprova — que é a
    segunda leitura do mesmo par de campos, e a divergência entre o que a coluna
    mostra e o que o fio leva.
    """
    import pacotes

    _com_o_perfil(monkeypatch, a04, {
        "leds": {"lightbar_brightness": 0.4},
        "controllers": {UNIQ: {"leds": {"lightbar_brightness": 0.9}}}})
    p = PonteDeMentira({"status": "ok", "aplicado_em": [UNIQ], "guardado_em": []})
    fn = pacotes.gesto_da_pagina("04-iluminacao.html", "cor")
    fn(ctx, {"controle": "p1", "uniq": UNIQ, "hex": "#0000FF"}, p)
    assert p.chamadas[0][2].get("brightness") == pytest.approx(0.9)


def test_sem_brilho_no_perfil_o_campo_nao_viaja(a04, ctx, monkeypatch):
    """`None` OMITE o campo, e omitir é o retrocompatível do `_payload_led_set`.

    A MORDIDA: devolva `1.0` no lugar do `None` em `brilho_do_controle` e esta
    linha reprova. Mandar `1.0` diria *"ela escolheu cheio"* onde ninguém
    escolheu nada — e um perfil sem seção `leds` deixaria de poder herdar o
    default do schema.
    """
    import pacotes

    _com_o_perfil(monkeypatch, a04, {})
    p = PonteDeMentira({"status": "ok", "aplicado_em": [UNIQ], "guardado_em": []})
    fn = pacotes.gesto_da_pagina("04-iluminacao.html", "cor")
    fn(ctx, {"controle": "p1", "uniq": UNIQ, "hex": "#0000FF"}, p)
    assert p.chamadas[0][2].get("brightness") is None


# ---------------------------------------------------------------------------
# 5. os três gestos escrevem pela MESMA porta
# ---------------------------------------------------------------------------
@pytest.mark.parametrize(("nome", "clique", "espera"), [
    ("cor", {"hex": "#FF8000"}, ["led_set_detalhado"]),
    ("apagar", {}, ["led_set_detalhado"]),
    ("auto", {}, ["chamar", "led_set_detalhado"]),
])
def test_os_tres_gestos_de_cor_passam_pela_porta_detalhada(
        a04, ctx, monkeypatch, nome, clique, espera):
    """Um caminho de escrita só — e ele é o que carrega os destinos do daemon.

    A MORDIDA: devolva qualquer um deles a `p.led_set(...)` e a linha dele
    reprova. Duas rotas para a mesma cor é como o brilho some numa e não na
    outra, que é o defeito de origem desta frente.
    """
    import pacotes

    _com_o_perfil(monkeypatch, a04, {"leds": {"lightbar_brightness": 0.5}})
    p = PonteDeMentira({"status": "ok", "aplicado_em": [UNIQ], "guardado_em": []})
    fn = pacotes.gesto_da_pagina("04-iluminacao.html", nome)
    fn(ctx, {"controle": "p1", "uniq": UNIQ, **clique}, p)
    assert [c[0] for c in p.chamadas] == espera


def test_o_apagar_manda_preto_e_o_brilho_nao_o_altera(a04, ctx, monkeypatch):
    """`int(0 * b)` é `0` para qualquer `b` — o preto sai preto com o campo junto."""
    import pacotes

    _com_o_perfil(monkeypatch, a04, {"leds": {"lightbar_brightness": 0.5}})
    p = PonteDeMentira({"status": "ok", "aplicado_em": [UNIQ], "guardado_em": []})
    fn = pacotes.gesto_da_pagina("04-iluminacao.html", "apagar")
    fn(ctx, {"controle": "p1", "uniq": UNIQ}, p)
    assert p.chamadas[0][1] == ((0, 0, 0),)
    assert a04._com_o_brilho((0, 0, 0), 0.5) == (0, 0, 0)


# ---------------------------------------------------------------------------
# 6. o desfecho sai do CORPO do daemon
# ---------------------------------------------------------------------------
def test_aplicou_e_o_gesto_cala(a04, ctx, monkeypatch):
    """`aplicado_em` com alguém dentro é o caminho feliz, e o feliz é calado."""
    import pacotes

    _com_o_perfil(monkeypatch, a04, {"leds": {"lightbar_brightness": 1.0}})
    p = PonteDeMentira({"status": "ok", "aplicado_em": [UNIQ], "guardado_em": []})
    fn = pacotes.gesto_da_pagina("04-iluminacao.html", "cor")
    assert fn(ctx, {"controle": "p1", "uniq": UNIQ, "hex": "#0000FF"}, p) is None


def test_guardado_vira_frase_no_cartao_dela(a04, ctx, monkeypatch):
    """O clique que NÃO acendeu nada tem de dizer isso — e a frase é do produto.

    ESTE É O DEFEITO MAIS CARO DESTA CASA, e ele estava vivo aqui: com o Modo
    Nativo ligado o backend muta toda escrita de output, o daemon responde
    `guardado_em: [uniq]` e o `bool` do `led_set` volta `True`. O gesto calava,
    o piloto anotava "aplicou", e o segundo clique parecia o primeiro.

    A MORDIDA: volte a `p.led_set(...)` (ou compare `frase` com `""` em vez de
    com `enviado`) e este teste reprova — o gesto passa a não levantar. A frase
    NÃO é digitada aqui: sai de `textos_de_aplicacao.guardado_ate_o_nativo_sair`,
    que é quem a GTK usa no mesmo evento.
    """
    import pacotes

    from hefesto_dualsense4unix.app.textos_de_aplicacao import _MOTIVO_NATIVO

    _com_o_perfil(monkeypatch, a04, {"leds": {"lightbar_brightness": 1.0}})
    ctx.state["native_mode"] = True
    p = PonteDeMentira({"status": "ok", "aplicado_em": [], "guardado_em": [UNIQ]})
    fn = pacotes.gesto_da_pagina("04-iluminacao.html", "cor")
    with pytest.raises(RuntimeError) as erro:
        fn(ctx, {"controle": "p1", "uniq": UNIQ, "hex": "#0000FF"}, p)
    assert _MOTIVO_NATIVO in str(erro.value), (
        f"a frase foi {str(erro.value)!r}, e ela tem de ser a do produto — a "
        f"mesma que a janela GTK diz neste mesmo evento.")


def test_nada_aconteceu_tambem_fala(a04, ctx, monkeypatch):
    """As DUAS listas vazias significam que nada foi escrito e nada foi guardado.

    É o caso que a bancada mediu em 23/08 — a tela dizendo "aplicado" com o
    corpo dizendo ZERO destino. A MORDIDA é a mesma do teste acima.
    """
    import pacotes

    _com_o_perfil(monkeypatch, a04, {"leds": {"lightbar_brightness": 1.0}})
    p = PonteDeMentira({"status": "ok", "aplicado_em": [], "guardado_em": []})
    fn = pacotes.gesto_da_pagina("04-iluminacao.html", "cor")
    with pytest.raises(RuntimeError):
        fn(ctx, {"controle": "p1", "uniq": UNIQ, "hex": "#0000FF"}, p)


def test_o_daemon_mudo_continua_dizendo_a_frase_de_sempre(a04, ctx, monkeypatch):
    """Corpo `None` é *"não houve resposta"*, e a frase é a do Hefesto desligado.

    Ela não muda com esta frente, e o teste está aqui para provar que não mudou:
    trocar a porta por `_detalhado` não pode transformar "o daemon não respondeu"
    em "o daemon respondeu e nada entrou" — são diagnósticos diferentes, e
    mandam olhar em lugares diferentes.
    """
    import pacotes

    _com_o_perfil(monkeypatch, a04, {})
    p = PonteDeMentira(None)
    fn = pacotes.gesto_da_pagina("04-iluminacao.html", "cor")
    with pytest.raises(RuntimeError) as erro:
        fn(ctx, {"controle": "p1", "uniq": UNIQ, "hex": "#0000FF"}, p)
    assert str(erro.value) == a04.sem_resposta_do_daemon()


# ---------------------------------------------------------------------------
# 7. a aba inteira, com o brilho reduzido
# ---------------------------------------------------------------------------
def test_o_pacote_emite_a_cor_pedida_e_nao_a_escurecida(a04, monkeypatch):
    """A coluna inteira, montada como o produto a monta, com o brilho em 50%.

    A MORDIDA: volte `"hex"` a `_hex(crua)` e a primeira asserção reprova — a
    caixa mostra `#00007F` e os oito botões da guia perdem a marca, porque o
    `data-hef-quando` deles é `#0000FF`.
    """
    import pacotes

    _com_o_perfil(monkeypatch, a04, {"leds": {"lightbar_brightness": 0.5}})
    escurecida = list(a04._com_o_brilho((0, 0, 255), 0.5))
    ctx = pacotes.Contexto(
        state={"active_profile": "regua"}, mesa=list(MESA),
        conectados=[dict(ACESO, lightbar_rgb=escurecida)], estados={})
    carga = pacotes.pacote_da_pagina("04-iluminacao.html", ctx)
    coluna = carga["colunas"][UNIQ]

    assert coluna["hex"] == "#0000FF", (
        f'a caixa diz {coluna["hex"]!r}, que é a cor PÓS-brilho do daemon — '
        f"uma cor que ela nunca pediu, e que nenhum dos oito tons casa.")
    assert coluna["brilho"] == "50%"
    assert "background:#7EB8D4" in coluna["luz"], (
        "a tira não voltou ao tom da casa: com o hex cru ela acende uma cor "
        "que a guia não mostra em lugar nenhum.")
    assert "opacity:0.5" in coluna["luz"], (
        "o brilho sumiu do desenho. Ele entra UMA vez, na opacidade — e a "
        "tinta é a cor PEDIDA, que é o modelo da prévia da GTK.")
