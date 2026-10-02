#!/usr/bin/env python3
"""A RÉGUA DA DECISÃO 12: a tabela para de desfazer a escolha de quem clica."""
from __future__ import annotations

import pathlib
import sys

import pytest

RAIZ = pathlib.Path(__file__).resolve().parents[2]
sys.path.insert(0, str(RAIZ / "src/hefesto_dualsense4unix/interface"))

UNIQ = "aa:bb:cc:00:00:01"
FALSO = {"uniq": UNIQ, "player": 1, "connected": True, "transport": "usb",
         "battery_pct": 90, "is_primary": True, "inputs": {}, "audio": {},
         "speaker": {}}
MESA = [{"pref": "p1", "jogador": 1, "uniq": UNIQ, "nome": "Régua",
         "via": "USB", "cor": "cosmic-red", "mascara": "DualSense"}]
ESTADO = {
    "active_profile": "regua",
    "mouse_emulation": {"enabled": True, "speed": 6, "scroll_speed": 1,
                        "bloqueio": "", "despachando": True},
    "keyboard_emulation": {"enabled": True, "osk_disponivel": True},
    "controllers": [FALSO],
}


class _PonteMuda:
    """Aceita tudo e ANOTA. É o que separa "não gravou" de "não chamou"."""

    def __init__(self) -> None:
        self.chamadas: list[tuple[str, dict]] = []

    def chamar(self, metodo: str, **params: object) -> bool:
        self.chamadas.append((metodo, dict(params)))
        return True

    def __getattr__(self, _nome: str):
        return lambda *a, **k: True


class _PerfilDeMentira:
    """O mínimo de um `Profile` que o "Guardar" toca, no idioma do pydantic."""

    def __init__(self, nome, button_actions=None, key_bindings=None):
        self.name = nome
        self.button_actions = button_actions
        self.key_bindings = key_bindings

    def model_copy(self, *, update):
        novo = _PerfilDeMentira(self.name, self.button_actions, self.key_bindings)
        for k, v in update.items():
            setattr(novo, k, v)
        return novo


@pytest.fixture
def aba(monkeypatch):
    """O pacote da 06 com um perfil de mentira, e a trava sempre limpa."""
    import pacotes
    from pacotes import a06_navegacao as mod
    from pacotes import perfil

    guardadas: dict[str, str] = {}
    monkeypatch.setattr(perfil, "ativo",
                        lambda nome: ({"name": "regua",
                                       "button_actions": dict(guardadas)}
                                      if nome else {}))
    mod._MEXENDO.clear()
    monkeypatch.setattr(mod, "_ULTIMA_PINTURA", 0.0, raising=False)
    ctx = pacotes.Contexto(state=ESTADO, mesa=MESA, conectados=[FALSO], estados={})
    yield ctx, mod, guardadas
    mod._MEXENDO.clear()


def _tique(ctx, mod) -> dict[str, str]:
    """Um tique de pintura — só as 21 linhas de *o que cada botão faz*."""
    mesa = mod.pacote(ctx)["mesa"]
    return {k: v for k, v in mesa.items() if str(k).startswith(mod.PREFIXO_DA_ACAO)}


def _outra_opcao(botao: str) -> tuple[str, str]:
    """Um token e o rótulo de uma escolha DIFERENTE do de fábrica daquela linha."""
    from hefesto_dualsense4unix.core import acoes_de_botao as acoes

    de_fabrica = acoes.padrao().get(botao)
    for token in acoes.ACOES:
        if token != de_fabrica:
            return token, acoes.rotulo(token)
    raise AssertionError(f"{botao}: o produto só conhece uma ação")


def test_o_tique_seguinte_nao_desfaz_a_escolha(aba):
    """O coração da decisão dela: clicou, o tique passou, a escolha ficou."""
    ctx, mod, _ = aba
    antes = _tique(ctx, mod)
    token, rotulo = _outra_opcao("cross")
    assert antes["acao-cross"] != rotulo, "o dublê escolheu o valor que já estava"

    mod.linha_de_botao(ctx, {"linha": "cross", "valor": rotulo}, _PonteMuda())

    depois = _tique(ctx, mod)
    assert depois["acao-cross"] == rotulo, (
        f"o tique devolveu {depois['acao-cross']!r} e ela escolheu {rotulo!r} — "
        "a pintura voltou a desfazer a escolha antes do clique em Guardar.")
    del token


def test_a_trava_nao_e_omissao_as_vinte_e_uma_continuam_pintando(aba):
    """Parar de repintar não pode virar parar de pintar."""
    from hefesto_dualsense4unix.core import acoes_de_botao as acoes

    ctx, mod, _ = aba
    _, rotulo = _outra_opcao("l1")
    mod.linha_de_botao(ctx, {"linha": "l1", "valor": rotulo}, _PonteMuda())

    depois = _tique(ctx, mod)
    assert len(depois) == len(acoes.BOTOES), (
        f"o tique emitiu {len(depois)} das {len(acoes.BOTOES)} linhas com a "
        "trava posta — a tabela ficaria sem dono e a página recarregada "
        "mostraria o desenho para sempre.")


def test_o_gesto_da_linha_nao_grava_e_nao_chama_o_daemon(aba):
    """*"Não vira gravação automática"* — palavra dela, conferida no ato.

    A MORDIDA: faça `linha_de_botao` chamar `perfil.gravar_e_reaplicar` — esta
    linha reprova nomeando a chamada que apareceu.
    """
    from hefesto_dualsense4unix.profiles import loader

    ctx, mod, _ = aba
    gravados: list[object] = []
    ponte = _PonteMuda()
    antes = getattr(loader, "save_profile", None)
    try:
        loader.save_profile = lambda prof, **_: gravados.append(prof)  # type: ignore[assignment]
        _, rotulo = _outra_opcao("circle")
        mod.linha_de_botao(ctx, {"linha": "circle", "valor": rotulo}, ponte)
    finally:
        if antes is not None:
            loader.save_profile = antes  # type: ignore[assignment]
    assert not gravados, "o gesto da linha GRAVOU — o ponto de gravação é o Guardar"
    assert not ponte.chamadas, (
        f"o gesto da linha falou com o daemon: {ponte.chamadas}")


def test_escolher_de_volta_o_do_perfil_esvazia_a_trava(aba):
    """Desfazer a própria escolha não pode deixar a trava presa."""
    ctx, mod, _ = aba
    do_perfil = _tique(ctx, mod)["acao-square"]
    _, rotulo = _outra_opcao("square")

    mod.linha_de_botao(ctx, {"linha": "square", "valor": rotulo}, _PonteMuda())
    assert mod._MEXENDO, "a escolha diferente não foi anotada"
    mod.linha_de_botao(ctx, {"linha": "square", "valor": do_perfil}, _PonteMuda())
    assert not mod._MEXENDO, (
        f"ela voltou ao que o perfil guarda ({do_perfil!r}) e a trava continua "
        f"com {mod._MEXENDO} — presa por uma escolha que não é escolha.")


def test_fechar_a_tela_larga_o_que_ela_nao_guardou(aba):
    """O fechar e o "Cancelar" são o "sair" da decisão dela."""
    ctx, mod, _ = aba
    do_perfil = _tique(ctx, mod)["acao-triangle"]
    _, rotulo = _outra_opcao("triangle")
    mod.linha_de_botao(ctx, {"linha": "triangle", "valor": rotulo}, _PonteMuda())

    volta = mod.fechar_definicoes(ctx, {}, _PonteMuda())

    assert not mod._MEXENDO, "o Cancelar não largou as escolhas pendentes"
    assert volta and volta["mesa"]["acao-triangle"] == do_perfil, (
        "o Cancelar não devolveu a tabela do perfil na hora — ela veria a "
        "própria escolha fantasma ao reabrir a tela.")
    assert _tique(ctx, mod)["acao-triangle"] == do_perfil


def test_sair_da_aba_larga_o_que_ela_nao_guardou(aba, monkeypatch):
    """A quarta porta: ela trocou de aba, e o documento que volta é outro."""
    import time as _time

    ctx, mod, _ = aba
    do_perfil = _tique(ctx, mod)["acao-l3"]
    _, rotulo = _outra_opcao("l3")
    mod.linha_de_botao(ctx, {"linha": "l3", "valor": rotulo}, _PonteMuda())
    assert _tique(ctx, mod)["acao-l3"] == rotulo, "a trava nem chegou a pegar"

    salto = _time.monotonic() + mod.PAUSA_DE_OUTRA_ABA + 1.0
    monkeypatch.setattr(_time, "monotonic", lambda: salto)

    assert _tique(ctx, mod)["acao-l3"] == do_perfil, (
        "a escolha pendente atravessou a saída da aba — a tabela do documento "
        "novo mostraria uma decisão que ela abandonou.")
    assert not mod._MEXENDO


def test_uma_pausa_curta_nao_larga_nada(aba, monkeypatch):
    """E o inverso: um tique atrasado não pode ser lido como "ela saiu"."""
    import time as _time

    ctx, mod, _ = aba
    _, rotulo = _outra_opcao("r3")
    mod.linha_de_botao(ctx, {"linha": "r3", "valor": rotulo}, _PonteMuda())
    _tique(ctx, mod)

    meio = _time.monotonic() + mod.PAUSA_DE_OUTRA_ABA / 2
    monkeypatch.setattr(_time, "monotonic", lambda: meio)

    assert _tique(ctx, mod)["acao-r3"] == rotulo, (
        "meio tempo de pausa já largou a escolha dela — a trava soltaria "
        "sozinha no meio da edição.")


@pytest.fixture
def disco(monkeypatch):
    """Um disco de mentira: guarda o que o gesto mandou gravar."""
    from hefesto_dualsense4unix.profiles import loader

    from hefesto_dualsense4unix.profiles import o_padrao_do_computador as opc

    gravados: list[_PerfilDeMentira] = []
    estado: dict[str, _PerfilDeMentira] = {}
    monkeypatch.setattr(loader, "load_profile", lambda n: estado[n], raising=False)
    monkeypatch.setattr(loader, "save_profile",
                        lambda prof, **_: gravados.append(prof), raising=False)

    def _pelo_gesto(_cartao, nome, muda, **_k):
        novo = muda(estado[nome])
        if novo is not None:
            estado[nome] = novo
            loader.save_profile(novo)
        return opc.JOGO, novo

    monkeypatch.setattr(opc, "gravar_pelo_gesto", _pelo_gesto)
    return estado, gravados


def _forma_de_fabrica(**trocas):
    """As 21 linhas como o desenho as crava: o de fábrica inteiro."""
    from hefesto_dualsense4unix.core import acoes_de_botao as acoes

    forma = {b: acoes.rotulo(a) for b, a in acoes.padrao().items()}
    forma.update(trocas)
    return forma


def test_o_guardar_solta_a_trava(aba, disco):
    """Guardado é fim de edição — a outra metade de *"até guardar ou sair"*."""
    ctx, mod, _ = aba
    estado, gravados = disco
    estado["regua"] = _PerfilDeMentira("regua")
    _, rotulo = _outra_opcao("square")

    mod.linha_de_botao(ctx, {"linha": "square", "valor": rotulo}, _PonteMuda())
    assert mod._MEXENDO
    mod.guardar_definicoes(ctx, {"forma": _forma_de_fabrica(square=rotulo)},
                           _PonteMuda())

    assert len(gravados) == 1, f"gravou {len(gravados)} vez(es), esperava uma"
    assert not mod._MEXENDO, (
        "o Guardar gravou e a trava continuou posta — o tique nunca mais "
        "mandaria na tabela.")


def test_a_trava_do_apagador_so_vale_quando_ela_nao_mexeu(aba, disco):
    """A recusa que ensinava um caminho inexistente virou um caminho que existe."""
    ctx, mod, guardadas = aba
    estado, gravados = disco
    guardadas["cross"] = "KEY_ESC"
    estado["regua"] = _PerfilDeMentira("regua", button_actions=dict(guardadas))

    with pytest.raises(RuntimeError, match="não guardei"):
        mod.guardar_definicoes(ctx, {"forma": _forma_de_fabrica()}, _PonteMuda())
    assert not gravados

    from hefesto_dualsense4unix.core import acoes_de_botao as acoes

    de_fabrica = acoes.rotulo(acoes.padrao()["cross"])
    mod.linha_de_botao(ctx, {"linha": "cross", "valor": de_fabrica}, _PonteMuda())
    assert mod._MEXENDO, (
        "voltar ao de fábrica uma linha que o perfil mudou É uma escolha dela, "
        "e a trava não a anotou")
    mod.guardar_definicoes(ctx, {"forma": _forma_de_fabrica()}, _PonteMuda())
    assert len(gravados) == 1 and gravados[0].button_actions is None, (
        "ela zerou a linha de propósito e o Guardar recusou — a recusa voltou a "
        "não distinguir a escolha dela do desenho.")


def test_o_padrao_solta_a_trava(aba, disco):
    """"Voltar ao padrão" zerou o perfil: segurar escolhas por cima disso faria"""
    ctx, mod, _ = aba
    estado, gravados = disco
    estado["regua"] = _PerfilDeMentira("regua", button_actions={"cross": "KEY_ESC"})
    _, rotulo = _outra_opcao("l1")
    mod.linha_de_botao(ctx, {"linha": "l1", "valor": rotulo}, _PonteMuda())

    mod.padrao_definicoes(ctx, {}, _PonteMuda())

    assert len(gravados) == 1
    assert not mod._MEXENDO, "o Voltar ao padrão zerou o perfil e deixou a trava posta"


def test_a_linha_recusa_o_que_o_produto_nao_conhece(aba):
    """Rótulo que o produto não conhece é clique inválido, e ele DIZ qual.

    Ele só chega aqui se o desenho andou sem o gerador — a lista da tela e a do
    produto saem do mesmo `core/acoes_de_botao`.
    """
    ctx, mod, _ = aba
    with pytest.raises(ValueError, match="não é do produto"):
        mod.linha_de_botao(ctx, {"linha": "cross", "valor": "Fazer café"},
                           _PonteMuda())
    with pytest.raises(ValueError, match="não disse qual botão"):
        mod.linha_de_botao(ctx, {"valor": "Esc"}, _PonteMuda())
    assert not mod._MEXENDO, "um clique inválido sujou a trava"


def test_as_vinte_e_uma_linhas_dizem_ao_python_que_ela_esta_mexendo():
    """O endereço do `change` está NO DESENHO, e sem ele nada disto acontece."""
    import re

    import onde
    from hefesto_dualsense4unix.core import acoes_de_botao as acoes

    doc = onde.pagina("06-navegacao.html").read_text(encoding="utf-8")
    ligadas = {m.group(1) for m in re.finditer(
        r'<select[^>]*data-gesto="linha-de-botao"[^>]*data-linha="([^"]+)"', doc)}
    assert ligadas == set(acoes.BOTOES), (
        f"as linhas sem `data-gesto` são {sorted(set(acoes.BOTOES) - ligadas)} — "
        "nelas a escolha dela não chega ao Python, e o tique a desfaz.")
    assert doc.count('data-gesto="fechar-definicoes"') == 2, (
        "o fechar e o `Cancelar` da tela de definições perderam o endereço do "
        "'sair' — a trava ficaria presa depois de ela desistir.")
