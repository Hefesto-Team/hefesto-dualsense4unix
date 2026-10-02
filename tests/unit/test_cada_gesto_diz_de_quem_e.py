"""Cada gesto diz de quem é (O-QUE-E-DO-COMPUTADOR-NAO-MUDA-COM-O-JOGO-01, réguas 9 a 11).

A tabela ``pacotes/camada.CAMADA`` declara, para todo ``data-gesto`` das dez
páginas, onde o clique grava; a marca de cada cartão do computador diz de quem
é o valor que o cartão mostra. Estas réguas leem as páginas (a publicada e o
desenho), o registro dos gestos e o disco de um lar de mentira (o ``conftest``
desvia os ``XDG_*``), com identidades da faixa sintética da casa.
"""
from __future__ import annotations

import html.parser
import sys
from pathlib import Path
from typing import Any

import pytest

import hefesto_dualsense4unix
from hefesto_dualsense4unix.interface import marca_da_camada as marca
from hefesto_dualsense4unix.interface import onde
from hefesto_dualsense4unix.profiles import o_padrao_do_computador as opc
from hefesto_dualsense4unix.profiles.loader import load_profile, save_profile
from hefesto_dualsense4unix.profiles.schema import Profile
from hefesto_dualsense4unix.utils import maquina as m

UM = "aa:bb:cc:00:00:01"
DOIS = "aa:bb:cc:00:00:02"


def _pacotes() -> Any:
    """Os pacotes como o piloto os importa (o `interface/` no caminho)."""
    interface = str(Path(hefesto_dualsense4unix.__file__).parent / "interface")
    if interface not in sys.path:
        sys.path.insert(0, interface)
    import pacotes

    pacotes._carregar_tudo()
    return pacotes


class _Gestos(html.parser.HTMLParser):
    """Os gestos de uma página, fora dos ``<script>``, com o nome que o piloto despacha.

    O piloto lê ``d.gesto || d.hefGesto || d.papel`` (``hefesto_vivo``,
    ``manda_do_alvo``): o ``data-gesto``, ou o ``data-hef-gesto`` da 10, ou o
    ``data-papel`` da 05. A régua lê os três, na mesma ordem.
    """

    def __init__(self) -> None:
        super().__init__()
        self.gestos: set[str] = set()
        self._no_script = False

    def handle_starttag(self, tag: str, attrs: list[tuple[str, str | None]]) -> None:
        if tag == "script":
            self._no_script = True
            return
        if self._no_script:
            return
        dados = {chave: valor for chave, valor in attrs if valor}
        for chave in ("data-gesto", "data-hef-gesto", "data-papel"):
            if chave in dados:
                self.gestos.add(str(dados[chave]))
                break

    def handle_endtag(self, tag: str) -> None:
        if tag == "script":
            self._no_script = False


def _as_dez() -> list[str]:
    pasta = onde.pagina("01-jogar.html").parent
    nomes = sorted(p.name for p in pasta.glob("[01][0-9]-*.html"))
    assert len(nomes) == 10, nomes
    return nomes


def _gestos(nome: str, *, publicado: bool) -> set[str]:
    leitor = _Gestos()
    leitor.feed(onde.pagina(nome, publicado=publicado).read_text(encoding="utf-8"))
    return leitor.gestos


def _vistos() -> set[tuple[str, str]]:
    """Todo ``(página, gesto)`` da página publicada e do desenho."""
    return {(nome, g) for nome in _as_dez() for publicado in (True, False)
            for g in _gestos(nome, publicado=publicado)}


# ---------------------------------------------------------------------------
# Régua 9: todo gesto publicado tem camada, e a camada é verdade
# ---------------------------------------------------------------------------
def test_todo_gesto_das_dez_tem_camada() -> None:
    """Cada gesto das dez (publicada e desenho) tem linha em ``CAMADA``.

    MORDIDA: apagar a linha do ``vel-cursor`` da tabela reprova.
    """
    camada = _pacotes().camada
    faltam = sorted(
        f"{p}·{g}" for p, g in _vistos()
        if (p, g) not in camada.CAMADA and ("*", g) not in camada.CAMADA)
    assert not faltam, f"gesto sem camada: {faltam}"


def test_toda_linha_da_camada_tem_gesto() -> None:
    """E toda linha tem gesto: na página, ou registrado para as dez (a marca).

    Uma linha sem gesto seria a tabela afirmando um botão que a tela não tem.
    """
    pac = _pacotes()
    camada = pac.camada
    vistos = _vistos()
    sobra = sorted(f"{p}·{g}" for p, g in camada.CAMADA if p != "*" and (p, g) not in vistos)
    assert not sobra, f"linha sem gesto na página: {sobra}"
    for p, g in camada.CAMADA:
        if p == "*":
            assert ("*", g) in pac.GESTOS, f"o coringa {g!r} não tem dono"
    assert set(camada.CAMADA.values()) <= camada.CAMADAS


def test_quem_grava_pelo_dono_e_do_computador() -> None:
    """A camada concorda com o que o gesto declara que grava.

    Todo gesto que declara ``grava="gravar_pelo_gesto"`` (o escritor do
    cartão do computador) ou volta o computador ao de fábrica está na camada
    ``computador``; os dois da marca, na ``jogo``. A declaração não se mede
    contra ela mesma: `test_todo_gesto_que_grava_esta_protegido` confere no AST
    que a função chama o escritor que declara.
    """
    pac = _pacotes()
    camada = pac.camada
    erradas = []
    for chave, escritor in pac.GESTOS_QUE_MEXEM.items():
        esperada = {"gravar_pelo_gesto": camada.COMPUTADOR,
                    "voltar_o_computador_ao_de_fabrica": camada.COMPUTADOR,
                    "so_neste_jogo": camada.JOGO,
                    "voltar_ao_do_computador": camada.JOGO}.get(escritor)
        if esperada is not None and camada.CAMADA.get(chave) != esperada:
            erradas.append(f"{chave} grava {escritor} e a camada diz {camada.CAMADA.get(chave)}")
    assert not erradas, erradas


class _Ponte:
    """Um daemon de papel que confirma tudo: o que se mede aqui é o disco."""

    def __getattr__(self, nome: str) -> Any:
        def registrar(*_a: Any, **_k: Any) -> Any:
            if nome == "resultado":
                return {"status": "ok"}
            if nome.endswith("_detalhado"):
                return {"status": "ok", "por_uniq": True}
            return True
        return registrar


def _contexto(pac: Any, ativo: str, *uniqs: str) -> Any:
    conectados = [{"uniq": u, "connected": True, "transport": "usb", "is_primary": i == 0,
                   "inputs": {}, "audio": {"mic_mudo": False},
                   "speaker": {"volume": 100, "muted": False}}
                  for i, u in enumerate(uniqs or (UM,))]
    mesa = [{"pref": f"p{i + 1}", "jogador": i + 1, "uniq": c["uniq"], "nome": "Régua",
             "via": "USB", "cor": "white", "transporte": "usb"}
            for i, c in enumerate(conectados)]
    return pac.Contexto(
        state={"active_profile": ativo, "rumble_policy": "balanceado", "rumble_ff": {},
               "mouse_emulation": {"enabled": True, "speed": 6, "scroll_speed": 1},
               "keyboard_emulation": {"enabled": True}},
        mesa=mesa, conectados=conectados, estados={})


def _perfil(nome: str, **campos: Any) -> Profile:
    return Profile.model_validate(
        {"name": nome, "match": {"type": "criteria", "window_class": [nome.lower()]},
         **campos})


#: Um clique de cada cartão do computador, com o que ela mandou.
CLIQUES: list[tuple[str, str, dict[str, Any]]] = [
    ("02-controles.html", "volume", {"uniq": UM, "volume": "microfone", "valor": "42"}),
    ("04-iluminacao.html", "brilho-luzes", {"uniq": UM, "controle": "p1", "luzes": "forte"}),
    ("05-vibracao.html", "forca", {"uniq": UM, "forca": "max"}),
    ("06-navegacao.html", "vel-cursor", {"valor": "11"}),
    ("06-navegacao.html", "vel-rolagem", {"valor": "4"}),
    ("06-navegacao.html", "guardar-teclas", {"forma": {"tecla-r1": "KEY_LEFTCTRL+KEY_W"}}),
]


@pytest.mark.parametrize(("aba", "gesto", "carga"), CLIQUES,
                         ids=[f"{a[:2]}-{g}" for a, g, _c in CLIQUES])
def test_o_gesto_do_computador_nao_toca_perfil_nenhum(
    aba: str, gesto: str, carga: dict[str, Any]
) -> None:
    """Com um jogo ativo que não sobrepõe o cartão: os perfis ficam, o ``maquina.json`` muda.

    Os três perfis do disco (o ativo, o Freestyle e um outro) ficam byte a
    byte. É a régua que reprova o dia em que um campo voltar a mudar com o
    perfil.

    MORDIDA: devolver o ``vel-cursor`` ao ``_guardar_no_perfil`` reprova.
    """
    pac = _pacotes()
    assert pac.camada.CAMADA[(aba, gesto)] == pac.camada.COMPUTADOR
    caminhos = [save_profile(_perfil(n)) for n in ("Jogo X", "Freestyle", "Jogo Y")]
    antes = [c.read_bytes() for c in caminhos]
    maquina_antes = m.carregar_maquina().computador
    fn = pac.gesto_da_pagina(aba, gesto)
    assert fn is not None, f"{aba}·{gesto} sem dono"
    fn(_contexto(pac, "Jogo X"), dict(carga), _Ponte())
    assert [c.read_bytes() for c in caminhos] == antes, f"{aba}·{gesto} mudou um perfil"
    assert m.carregar_maquina().computador != maquina_antes, (
        f"{aba}·{gesto} não chegou ao maquina.json")


# ---------------------------------------------------------------------------
# Régua 10: os sem dono só diminuem
# ---------------------------------------------------------------------------
#: Os oito de 01/10 (a 06 e a 08) menos os dois que esta leva curou: o
#: ``acao-do-gesto`` (OS-GESTOS-DO-CONTROLE-FAZEM-O-QUE-DIZEM-01) e o
#: ``padrao-da-aba`` (esta). O ``navegacao-interna`` sai com a
#: A-NAVEGACAO-INTERNA, e aí esta lista perde uma linha.
SEM_DONO_PERMITIDOS = frozenset({
    "modo-steam", "navegacao-interna",
    "custo-luz", "custo-som", "custo-vibracao", "novo-hub",
})


def test_os_sem_dono_so_diminuem() -> None:
    """Todo gesto das dez tem atendente, ou está declarado entre os sem dono de hoje.

    O da fita (``monta.GESTO_DA_FITA``) é atendido pelo piloto, que o registra
    ao subir. MORDIDA: um ``data-gesto`` novo sem atendente reprova (*«tudo na
    interface deveria funcionar»*), e uma entrada nova no ``SEM_GESTO`` também.
    """
    pac = _pacotes()
    import monta

    declarados = set(pac.a06_navegacao.SEM_GESTO) | set(pac.a08_conexoes.SEM_GESTO)
    assert declarados <= SEM_DONO_PERMITIDOS, sorted(declarados - SEM_DONO_PERMITIDOS)
    sem_atendente = sorted(
        f"{p}·{g}" for p, g in _vistos()
        if pac.gesto_da_pagina(p, g) is None
        and g not in declarados and g != monta.GESTO_DA_FITA)
    assert not sem_atendente, f"gesto sem atendente e sem declaração: {sem_atendente}"


# ---------------------------------------------------------------------------
# Régua 11: a marca pinta a verdade
# ---------------------------------------------------------------------------
def _marca_da_luz(pac: Any, ctx: Any) -> dict[str, str]:
    _da_mesa, por_controle = pac.camada.marcas("04-iluminacao.html", ctx)
    return {u: c[marca.campo("luz")] for u, c in por_controle.items()}


def test_a_marca_pinta_a_verdade() -> None:
    """O jogo que sobrepõe só a luz do P2: «PC» no P1, o nome do jogo no P2.

    Depois do «Voltar ao do PC» no P2, os dois dizem «PC» e o perfil não tem
    mais a luz do P2.

    MORDIDA: pintar pelo nome do perfil ativo, sem perguntar ao
    ``model_fields_set`` (o ``sobrepoe``), reprova no P1.
    """
    pac = _pacotes()
    _computador = {"global": {"leds": {"lightbar": [10, 20, 200]}}}
    assert m.gravar_o_computador(_computador)
    save_profile(_perfil("Jogo X", controllers={
        DOIS.replace(":", ""): {"leds": {"lightbar": [200, 10, 10]}}}))
    ctx = _contexto(pac, "Jogo X", UM, DOIS)

    luz = _marca_da_luz(pac, ctx)
    assert luz[UM] == marca.miolo("luz", jogo="Jogo X", sobrepoe=False), luz[UM]
    assert marca.COMPUTADOR in luz[UM] and marca.TEXTO_SO_NESTE_JOGO in luz[UM]
    assert luz[DOIS] == marca.miolo("luz", jogo="Jogo X", sobrepoe=True), luz[DOIS]
    assert "Jogo X" in luz[DOIS] and marca.TEXTO_VOLTAR in luz[DOIS]

    gesto = pac.gesto_da_pagina("04-iluminacao.html", marca.VOLTAR_AO_DO_COMPUTADOR)
    assert gesto is not None
    gesto(ctx, {"linha": "luz", "uniq": DOIS}, _Ponte())
    assert not opc.sobrepoe(load_profile("Jogo X"), "luz", DOIS)
    luz = _marca_da_luz(pac, ctx)
    assert luz[UM] == luz[DOIS] == marca.miolo("luz", jogo="Jogo X", sobrepoe=False)


def test_so_neste_jogo_muda_o_dono_da_marca() -> None:
    """«Só neste jogo» no P1 copia o que vale para o perfil, e a marca passa a ser do jogo."""
    pac = _pacotes()
    assert m.gravar_o_computador({"global": {"leds": {"lightbar": [10, 20, 200]}}})
    save_profile(_perfil("Jogo X"))
    ctx = _contexto(pac, "Jogo X", UM)
    gesto = pac.gesto_da_pagina("04-iluminacao.html", marca.SO_NESTE_JOGO)
    assert gesto is not None
    gesto(ctx, {"linha": "luz", "uniq": UM}, _Ponte())
    assert opc.sobrepoe(load_profile("Jogo X"), "luz", UM)
    assert _marca_da_luz(pac, ctx)[UM] == marca.miolo("luz", jogo="Jogo X", sobrepoe=True)


def test_com_o_freestyle_a_marca_e_do_pc_e_sem_botao() -> None:
    """O Freestyle não sobrepõe nada: «PC», e nenhum dos dois botões."""
    pac = _pacotes()
    save_profile(_perfil("Freestyle", controllers={
        UM.replace(":", ""): {"leds": {"lightbar": [200, 10, 10]}}}))
    luz = _marca_da_luz(pac, _contexto(pac, "Freestyle", UM))
    assert luz[UM] == marca.miolo("luz"), luz[UM]
    assert "data-gesto" not in luz[UM]


def test_sem_jogo_os_botoes_da_marca_recusam_dizendo() -> None:
    """Sem jogo ativo, o «Só neste jogo» recusa com a frase, e não grava."""
    pac = _pacotes()
    gesto = pac.gesto_da_pagina("04-iluminacao.html", marca.SO_NESTE_JOGO)
    assert gesto is not None
    with pytest.raises(RuntimeError, match="não há jogo ativo"):
        gesto(_contexto(pac, "Freestyle", UM), {"linha": "luz", "uniq": UM}, _Ponte())


def test_a_pintura_so_pousa_onde_a_pagina_tem_lugar(monkeypatch: pytest.MonkeyPatch) -> None:
    """A página publicada de antes desta leva não tem a marca: o pacote não a pinta.

    Um campo sem lugar seria um «sem dono» a mais no relatório da pintura. Com o
    lugar (a página nova), a marca entra na coluna daquele controle.
    """
    pac = _pacotes()
    save_profile(_perfil("Jogo X"))
    ctx = _contexto(pac, "Jogo X", UM)
    fora = {"colunas": {UM: {"hex": "#000000"}}}
    monkeypatch.setattr(pac, "alvos_da_pagina", lambda _p: {"hex": {"texto"}})
    assert pac.camada.com_a_camada("04-iluminacao.html", ctx, fora) == fora
    monkeypatch.setattr(pac, "alvos_da_pagina",
                        lambda _p: {"hex": {"texto"}, marca.campo("luz"): {"html"}})
    com = pac.camada.com_a_camada("04-iluminacao.html", ctx, fora)
    assert com["colunas"][UM][marca.campo("luz")] == marca.miolo("luz", jogo="Jogo X")
    assert com["colunas"][UM]["hex"] == "#000000"
    assert fora == {"colunas": {UM: {"hex": "#000000"}}}, "a pintura mexeu no pacote da aba"


# ---------------------------------------------------------------------------
# Régua 11, o botão que funciona: «Só neste jogo» muda o dono, ou não aparece
# ---------------------------------------------------------------------------
def _contexto_vivo(pac: Any, ativo: str, *, speed: int, scroll: int) -> Any:
    """O contexto da régua com o mouse em ``speed``/``scroll`` (o resto como em `_contexto`)."""
    ctx = _contexto(pac, ativo, UM)
    ctx.state["mouse_emulation"] = {"enabled": True, "speed": speed, "scroll_speed": scroll}
    return ctx


def _miolo_do(pac: Any, ctx: Any, cartao: str) -> str:
    da_mesa, por_controle = pac.camada.marcas(opc.SECOES[cartao].pagina, ctx)
    if opc.SECOES[cartao].por_controle:
        return por_controle[UM][marca.campo(cartao)]
    return da_mesa[marca.campo(cartao)]


@pytest.mark.parametrize("cartao", sorted(opc.SECOES))
def test_so_neste_jogo_de_todo_cartao_muda_o_dono_num_pc_sem_padrao(cartao: str) -> None:
    """Num computador sem padrão, o «Só neste jogo» de CADA cartão dá o cartão ao jogo.

    O que vale agora, quando nem o jogo nem o computador declaram, é o que o
    aparelho tem (o volume, a força, as velocidades, o teclado ligado). Medido
    na conferência de 02/10/2026: sem esse degrau, o clique no som, na
    vibração, no mouse e no teclado gravava o perfil igual, e a marca seguia
    «PC · Só neste jogo», um botão que aceitava o clique e não mudava nada.

    MORDIDA: tirar os ``vivos`` do gesto (``so_neste_jogo`` sem eles) reprova
    no som, na vibração, no mouse e no teclado.
    """
    pac = _pacotes()
    save_profile(_perfil("Jogo X"))
    ctx = _contexto_vivo(pac, "Jogo X", speed=9, scroll=2)
    uniq = UM if opc.SECOES[cartao].por_controle else None
    assert _miolo_do(pac, ctx, cartao) == marca.miolo(cartao, jogo="Jogo X", sobrepoe=False)
    gesto = pac.gesto_da_pagina(opc.SECOES[cartao].pagina, marca.SO_NESTE_JOGO)
    assert gesto is not None
    gesto(ctx, {"linha": cartao, "uniq": uniq or ""}, _Ponte())
    assert opc.sobrepoe(load_profile("Jogo X"), cartao, uniq), (
        f"«Só neste jogo» em {cartao} não deu o cartão ao jogo")
    assert _miolo_do(pac, ctx, cartao) == marca.miolo(cartao, jogo="Jogo X", sobrepoe=True)


def test_o_botao_que_nao_mudaria_nada_nao_aparece_e_recusa_sem_gravar() -> None:
    """As velocidades do mouse no de fábrica: a marca diz só «PC», e o clique velho recusa.

    O esquema não distingue «o jogo escolheu 6 e 1» de «ninguém escolheu», então
    copiar o de fábrica não daria o cartão ao jogo. O botão não se oferece, e o
    clique que chega de um tique velho recusa dizendo, sem tocar o arquivo.

    MORDIDA: devolver o miolo sem perguntar ao ``pode_so_neste_jogo`` reprova.
    """
    pac = _pacotes()
    caminho = save_profile(_perfil("Jogo X"))
    antes = caminho.read_bytes()
    ctx = _contexto_vivo(pac, "Jogo X", speed=6, scroll=1)
    miolo = _miolo_do(pac, ctx, "mouse")
    assert miolo == marca.miolo("mouse"), miolo
    assert "data-gesto" not in miolo
    gesto = pac.gesto_da_pagina("06-navegacao.html", marca.SO_NESTE_JOGO)
    assert gesto is not None
    with pytest.raises(RuntimeError, match="de fábrica"):
        gesto(ctx, {"linha": "mouse"}, _Ponte())
    assert caminho.read_bytes() == antes
