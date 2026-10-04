"""O controle já pareado se pareia de novo num clique (O-CONTROLE-JA-PAREADO-...-01).

O dublê do BlueZ tem um par antigo e o aparelho em modo de pareamento (a chave dele foi
apagada): a linha diz «Parear de Novo», e o gesto esquece o par velho ANTES de abrir a
busca. O «Procurar» com o serviço lento responde sem «não respondeu», e o «⋮» abre com a
busca ligada.
"""

from __future__ import annotations

import re
from pathlib import Path
from types import SimpleNamespace
from typing import Any

import pytest

from tests.conftest import exigir_gi_real

exigir_gi_real("importa `interface.pacotes.a08_conexoes`, que carrega o GTK")

from hefesto_dualsense4unix.integrations import central_do_radio as cr
from hefesto_dualsense4unix.interface import pacotes
from hefesto_dualsense4unix.interface.pacotes import a08_conexoes as a08
from hefesto_dualsense4unix.interface.pacotes import ponte

RAIZ = Path(__file__).resolve().parents[2]
MOCKUP = RAIZ / "mockup/08-conexoes.html"
PAGINA = "08-conexoes.html"

#: o endereço que a cena guarda é o de 12 hexa (`a08._mac`)
ADAPTADORES = {"/org/bluez/hci0": "AABBCC000001", "/org/bluez/hci1": "AABBCC000002",
               "/org/bluez/hci2": "AABBCC000003"}
#: P1 a P4, endereços da faixa forjada
CONTROLES = ("AA:BB:CC:00:00:11", "AA:BB:CC:00:00:12", "AA:BB:CC:00:00:13", "AA:BB:CC:00:00:14")


def _bz(endereco: str, adaptador: str, *, pareado: bool, rssi: int | None = -50) -> Any:
    return SimpleNamespace(endereco=endereco, adaptador=adaptador, conectado=False,
                           pareado=pareado, rssi=rssi, classe=0x002508, icone="input-gaming",
                           nome="Wireless Controller", modalias="", alias="")


def _com_dois_pontos(hexa: str) -> str:
    return ":".join(hexa[i:i + 2] for i in range(0, 12, 2))


def _adaptador(caminho: str) -> Any:
    return SimpleNamespace(caminho=caminho, endereco=_com_dois_pontos(ADAPTADORES[caminho]))


class _Ponte:
    """O `p` do gesto: guarda o que foi pedido ao serviço, e responde como ele."""

    def __init__(self) -> None:
        self.pedidos: list[tuple[str, dict[str, Any]]] = []

    def resultado(self, metodo: str, **parametros: Any) -> Any:
        self.pedidos.append((metodo, parametros))
        if metodo == "radio.busca.set":
            return {"status": "ok",
                    "busca": {"adaptador": parametros["destino"]} if parametros["ligada"] else None}
        return {"status": "ok", "dispensado": True}


def _linha_que_nao_conectou(
    destino: str, aparelho: str, pareados: frozenset[Any]
) -> dict[str, Any]:
    ctx = pacotes.Contexto(state={}, mesa=[], conectados=[], estados={})
    movimento = {"aparelho": _com_dois_pontos(aparelho),
                 "destino": _com_dois_pontos(destino), "estado": "nao_chegou",
                 "motivo": "prazo", "quando": 1000.0, "e_controle": True}
    linhas = a08._os_que_nao_conectaram(ctx, [movimento], 1001.0, [destino], frozenset(), pareados)
    assert len(linhas) == 1
    return linhas[0]


def _par(adaptador: str, controle: str) -> tuple[str, str]:
    return ADAPTADORES[adaptador], a08._mac(controle)


# --- 1. na lista do «+ Conectar», o pareado fora do ar tem «Conectar» --------------------

def test_o_pareado_fora_do_ar_aparece_com_conectar_e_o_novo_com_parear() -> None:
    antigo, novo = CONTROLES[0], CONTROLES[1]
    aparelhos = (_bz(antigo, "/org/bluez/hci0", pareado=True),
                 _bz(novo, "/org/bluez/hci0", pareado=False))
    perto = a08._perto(aparelhos, (_adaptador("/org/bluez/hci0"),), [])
    por_id = {a["id"]: a for a in perto}
    assert por_id[a08._mac(antigo)]["conhecido"] is True
    assert por_id[a08._mac(novo)]["conhecido"] is False
    cena = {"lugares": [{"id": ADAPTADORES["/org/bluez/hci0"], "sabido": True}], "aparelhos": [],
            "perto": perto, "destino_do_conectar": ADAPTADORES["/org/bluez/hci0"]}
    html = a08.html_dos_moldes(cena)
    botoes = {alvo: gesto for gesto, alvo in re.findall(
        r'data-gesto="(conectar-aparelho|parear-aparelho)" data-alvo="([^"]+)"', html)}
    assert botoes == {a08._mac(antigo): "conectar-aparelho", a08._mac(novo): "parear-aparelho"}
    assert re.search(r'conectar-aparelho" data-alvo="[^"]+">Conectar</button>', html)


# --- 2. a linha diz «Parear de Novo» quando o par velho ainda está aqui -------------------

@pytest.mark.parametrize("controle", CONTROLES)
@pytest.mark.parametrize("adaptador", list(ADAPTADORES))
def test_a_linha_do_pareado_que_nao_conectou_diz_parear_de_novo(
    controle: str, adaptador: str
) -> None:
    destino = ADAPTADORES[adaptador]
    linha = _linha_que_nao_conectou(destino, a08._mac(controle),
                                    frozenset({_par(adaptador, controle)}))
    assert linha["pareado_aqui"] is True
    html = a08.html_da_linha(linha, {"lugares": [], "aparelhos": [linha]})
    assert f">{a08.PAREAR_DE_NOVO}<" in html and 'data-gesto="parear-de-novo"' in html
    assert a08.TENTAR_DE_NOVO not in html


def test_o_botao_da_linha_fala_como_o_irmao_tentar_de_novo() -> None:
    """Os dois botões moram no mesmo lugar da linha «Não Conectou» e se escrevem do mesmo
    jeito: cada palavra com maiúscula, menos as miúdas («Tentar de Novo», «Parear de Novo»)."""
    for rotulo in (a08.TENTAR_DE_NOVO, a08.PAREAR_DE_NOVO):
        assert a08._em_titulo(rotulo) == rotulo, rotulo


def test_sem_par_velho_aqui_a_linha_continua_tentar_de_novo() -> None:
    linha = _linha_que_nao_conectou(ADAPTADORES["/org/bluez/hci0"], a08._mac(CONTROLES[0]),
                                    frozenset({_par("/org/bluez/hci1", CONTROLES[0])}))
    assert linha["pareado_aqui"] is False
    html = a08.html_da_linha(linha, {"lugares": [], "aparelhos": [linha]})
    assert f">{a08.TENTAR_DE_NOVO}<" in html and 'data-gesto="tentar-de-novo"' in html


@pytest.mark.parametrize("adaptador", list(ADAPTADORES))
def test_a_cena_marca_o_par_velho_pelo_que_o_bluez_diz(
    monkeypatch: pytest.MonkeyPatch, adaptador: str
) -> None:
    """A cena INTEIRA, do BlueZ de mentira até a linha: o par velho é o `Paired` daquele
    aparelho NAQUELE adaptador, e o pareado noutro adaptador não conta."""
    import time

    from hefesto_dualsense4unix.integrations.bluez_dbus import (
        AdaptadorDoBluez,
        AparelhoDoBluez,
    )
    from hefesto_dualsense4unix.integrations.mesa_de_radio import Mesa
    from hefesto_dualsense4unix.utils.maquina import MaquinaConfig

    for nome in ("_FUNDO", "_ABERTO", "_CENA_NA_TELA", "_NIVEL_NA_TELA"):
        monkeypatch.setattr(a08, nome, {})
    monkeypatch.setattr(a08, "LER_NA_HORA", True)
    monkeypatch.setattr(a08, "_mesa_do_radio", lambda recarregar=False: Mesa())
    adaptadores = tuple(AdaptadorDoBluez(caminho, caminho.rsplit("/", 1)[1],
                                         _com_dois_pontos(hexa), varrendo=False)
                        for caminho, hexa in ADAPTADORES.items())
    outro = next(c for c in ADAPTADORES if c != adaptador)

    def _aparelho(controle: str, onde: str, pareado: bool) -> Any:
        return AparelhoDoBluez(f"{onde}/dev_{controle.replace(':', '_')}", onde, controle,
                               nome="Wireless Controller", conectado=False, pareado=pareado,
                               classe=0x002508)

    aparelhos = (_aparelho(CONTROLES[0], adaptador, True),
                 _aparelho(CONTROLES[1], adaptador, False),
                 _aparelho(CONTROLES[2], outro, True))
    monkeypatch.setattr(a08, "_ler_o_bluez", lambda: (adaptadores, aparelhos))
    monkeypatch.setattr(a08, "_ler_a_maquina", lambda: (MaquinaConfig(), {}))
    monkeypatch.setattr(a08, "_ler_o_historico", lambda: {})
    monkeypatch.setattr(a08, "_ler_o_wifi", lambda: None)
    monkeypatch.setattr(a08, "_ler_os_zumbis", lambda: {})
    destino = _com_dois_pontos(ADAPTADORES[adaptador])
    movimentos = [{"aparelho": c, "destino": destino, "estado": "nao_chegou", "motivo": "prazo",
                   "quando": time.time() - 1.0, "e_controle": True} for c in CONTROLES[:3]]
    estado = {"controllers": [], "radio_central": {"movimentos": movimentos, "proposta": None}}
    cena = a08.cena_do_radio(pacotes.Contexto(state=estado, mesa=[], conectados=[]))
    linhas = {a["aparelho"]: a["pareado_aqui"] for a in cena["aparelhos"] if a.get("nao_conectou")}
    assert linhas == {a08._mac(CONTROLES[0]): True, a08._mac(CONTROLES[1]): False,
                      a08._mac(CONTROLES[2]): False}


def _na_tela(monkeypatch: pytest.MonkeyPatch, linha: dict[str, Any], **cena: Any) -> None:
    lugar = {"id": linha["lugar"], "sabido": True}
    monkeypatch.setattr(a08, "_CENA_NA_TELA", {
        "lugares": [lugar], "aparelhos": [linha], "procurando": a08.PROCURAR_DESLIGADO,
        "ocupado": False, **cena})
    monkeypatch.setattr(a08, "_esquecer", lambda *a, **k: None)


@pytest.mark.parametrize("controle", CONTROLES)
@pytest.mark.parametrize("adaptador", list(ADAPTADORES))
def test_o_clique_esquece_o_par_velho_antes_de_abrir_a_busca(
    monkeypatch: pytest.MonkeyPatch, controle: str, adaptador: str
) -> None:
    destino = ADAPTADORES[adaptador]
    linha = _linha_que_nao_conectou(destino, a08._mac(controle),
                                    frozenset({_par(adaptador, controle)}))
    _na_tela(monkeypatch, linha)
    ordem: list[str] = []
    ponte_de_mentira = _Ponte()
    monkeypatch.setattr(a08, "_esquecer_o_pareamento", lambda lugar, aparelho: (
        ordem.append(f"esqueceu {lugar} {aparelho}"), SimpleNamespace(deu=True, porque=""))[1])
    original = ponte_de_mentira.resultado
    ponte_de_mentira.resultado = lambda m, **k: (ordem.append(m), original(m, **k))[1]  # type: ignore[method-assign]
    gesto = pacotes.gesto_da_pagina(PAGINA, "parear-de-novo")
    assert gesto is not None, "parear-de-novo perdeu o dono"
    ctx = pacotes.Contexto(state={}, mesa=[], conectados=[], estados={})

    gesto(ctx, {"alvo": destino, "linha": linha["id"], "evento": "click"}, ponte_de_mentira)

    assert ordem[0] == f"esqueceu {destino} {a08._mac(controle)}"
    assert "radio.busca.set" in ordem and ordem.index("radio.busca.set") > 0
    busca = next(p for m, p in ponte_de_mentira.pedidos if m == "radio.busca.set")
    assert busca == {"ligada": True, "destino": destino}


def test_a_linha_sem_par_velho_nao_tem_o_que_refazer(monkeypatch: pytest.MonkeyPatch) -> None:
    destino = ADAPTADORES["/org/bluez/hci0"]
    linha = _linha_que_nao_conectou(destino, a08._mac(CONTROLES[0]), frozenset())
    _na_tela(monkeypatch, linha)
    escreveu: list[Any] = []
    monkeypatch.setattr(a08, "_esquecer_o_pareamento", lambda *a: escreveu.append(a))
    gesto = pacotes.gesto_da_pagina(PAGINA, "parear-de-novo")
    assert gesto is not None
    ctx = pacotes.Contexto(state={}, mesa=[], conectados=[], estados={})
    with pytest.raises(ValueError):
        gesto(ctx, {"alvo": destino, "linha": linha["id"]}, _Ponte())
    assert escreveu == []


# --- 3. a janelinha do «Esquecer» ---------------------------------------------------------

def _cena_do_menu(**extra: Any) -> dict[str, Any]:
    destino = ADAPTADORES["/org/bluez/hci0"]
    ap = {"id": a08._mac(CONTROLES[0]), "tipo": "controle", "lugar": destino, "nome": "Pedro",
          "rotulo": "DualSense", "aparelho": a08._mac(CONTROLES[0]), "esperando": False,
          "fixo": False, "mic": False, "ponte": None, "cor": "#7eb8d4"}
    return {"lugares": [{"id": destino, "sabido": True, "nome": "Direita"}], "aparelhos": [ap],
            "procurando": a08.PROCURAR_DESLIGADO, "ocupado": False, **extra}


def test_a_janelinha_do_esquecer_tem_o_nome_uma_frase_e_o_botao() -> None:
    html = a08.html_dos_moldes(_cena_do_menu())
    menu = re.search(r'<template class="painel-molde" data-painel="menu"[^>]*data-titulo="([^"]*)">'
                     r"(.*?)</template>", html, re.S)
    assert menu, "o molde do «⋮» sumiu"
    titulo, corpo = menu.groups()
    assert "Pedro" in titulo
    assert re.findall(r'<p class="explica">([^<]*)</p>', corpo) == [a08.ESQUECER_FAZ]
    assert len(re.findall(r"<button ", corpo)) == 1 and a08.ESQUECER in corpo
    assert "Procurar" not in corpo


def test_o_procurar_so_mora_no_painel_do_conectar() -> None:
    pagina = MOCKUP.read_text(encoding="utf-8")
    assert '.radio .painel:not([data-tipo="conectar"]) .cadeado{display:none}' in pagina
    assert "p.setAttribute('data-tipo', tipo)" in pagina


# --- 5. o «⋮» abre com o que se sabe ------------------------------------------------------

def test_o_menu_abre_com_a_busca_ligada(monkeypatch: pytest.MonkeyPatch) -> None:
    cena = _cena_do_menu(ocupado=True, procurando=a08.PROCURAR_LIGADO)
    monkeypatch.setattr(a08, "_CENA_NA_TELA", cena)
    ap = cena["aparelhos"][0]
    html = a08.html_dos_moldes(cena)
    assert 'data-painel="menu"' in html and 'data-esquecer="1"' in html
    ctx = pacotes.Contexto(state={}, mesa=[], conectados=[], estados={})
    for nome in ("aparelho-menu", "esquecer-aparelho"):
        gesto = pacotes.gesto_da_pagina(PAGINA, nome)
        assert gesto is not None
        assert gesto(ctx, {"alvo": ap["id"], "lugar": ap["lugar"]}, _Ponte()) == {"armou": True}


def test_confirmar_o_esquecer_com_a_busca_ligada_diz_o_que_fazer_e_nao_escreve(
    monkeypatch: pytest.MonkeyPatch
) -> None:
    cena = _cena_do_menu(ocupado=True, procurando=a08.PROCURAR_LIGADO)
    monkeypatch.setattr(a08, "_CENA_NA_TELA", cena)
    escreveu: list[Any] = []
    monkeypatch.setattr(a08, "_esquecer_o_pareamento", lambda *a: escreveu.append(a))
    gesto = pacotes.gesto_da_pagina(PAGINA, "confirmar-esquecer")
    assert gesto is not None
    ap = cena["aparelhos"][0]
    ctx = pacotes.Contexto(state={}, mesa=[], conectados=[], estados={})
    with pytest.raises(RuntimeError, match=a08.DESLIGUE_O_PROCURAR):
        gesto(ctx, {"alvo": ap["id"], "lugar": ap["lugar"]}, _Ponte())
    assert escreveu == []


# --- 4. o «Procurar» com o serviço lento --------------------------------------------------

DEMORA_MEDIDA_S = 0.366  # a maior de 03/10 no diário do serviço (`ipc_lento`)


def test_o_prazo_do_procurar_cobre_o_que_o_servico_leva() -> None:
    assert ponte.teto("radio.busca.set") > DEMORA_MEDIDA_S
    assert ponte.teto("radio.busca.set") >= cr.PRAZO_DA_TRAVA_DO_GESTO_S + 1.0


def test_o_procurar_com_o_servico_lento_nao_diz_que_o_daemon_nao_respondeu(
    monkeypatch: pytest.MonkeyPatch
) -> None:
    destino = ADAPTADORES["/org/bluez/hci0"]
    monkeypatch.setattr(a08, "_CENA_NA_TELA", {
        "lugares": [{"id": destino}], "aparelhos": [], "procurando": a08.PROCURAR_DESLIGADO,
        "destino_do_conectar": destino})
    monkeypatch.setattr(a08, "_abrir_na_tela", lambda *a: None)

    def servico_lento(metodo: str, params: dict[str, Any], *, timeout: float) -> tuple[bool, Any]:
        if timeout < DEMORA_MEDIDA_S:
            return False, None
        return True, {"status": "ok", "busca": {"adaptador": destino}}

    monkeypatch.setattr(ponte._b, "_safe_call", servico_lento)
    gesto = pacotes.gesto_da_pagina(PAGINA, "radio-procurar")
    assert gesto is not None
    ctx = pacotes.Contexto(state={}, mesa=[], conectados=[], estados={})
    assert gesto(ctx, {"evento": "click"}, ponte) == {"armou": True}
