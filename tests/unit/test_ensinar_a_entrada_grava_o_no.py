"""Ensinar grava o nó — O-MAPA-QUE-ELA-CORRIGE-01, passo 7 (D-2609-ENSINAR-GRAVA-O-NO).

Pedido dela: *«corrigir quando for 2.0 e tal. até agora não entendi pq
identificou errado»*. O «ensinar» da página (o aparelho «fora do mapa» posto
na mão e clicado numa entrada) guardava o que ela dizia só na MEMÓRIA da
página: a releitura o mostrava pendente de novo. Agora o nó em que o aparelho
está (e o ``peer`` dele, se houver) passa a ser da entrada, no disco dela — é
a cura universal da pista que o firmware da placa não liga.
<!-- noqa-acento: citação literal dela -->

A MORDIDA: devolva à página o ``MAPA[n]`` só na memória (tire o ``if
(doProduto()) return;`` do clique no plugue e o gesto do
``ensinaNaEntrada``) — o clique não chega ao disco, e a releitura mostra o
pendrive fora do mapa de novo (``test_o_clique_no_plugue_ensina_pelo_disco``).

TUDO AQUI É DE MENTIRA E DE NINGUÉM: a máquina sintética de 15 entradas de
``test_o_nome_da_entrada_e_da_posicao``, um pendrive a 5000M em ``2-3`` (o nó
``usb2-port3``, sem ``peer`` e de entrada nenhuma) e o ``maquina.json`` no
``tmp_path`` que o ``conftest`` desvia.
"""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any

import pytest

from hefesto_dualsense4unix.integrations import censo_do_barramento, mapa_das_portas
from hefesto_dualsense4unix.integrations import entrada_a_entrada as ee
from hefesto_dualsense4unix.integrations.censo_do_barramento import (
    Aparelho,
    Barramento,
    Censo,
)
from hefesto_dualsense4unix.integrations.entradas_do_gabinete import NoDeEntrada
from hefesto_dualsense4unix.integrations.lugar_declarado import declarar_a_maquina
from hefesto_dualsense4unix.interface import arranjo_desta_maquina
from hefesto_dualsense4unix.utils.maquina import (
    MaquinaConfig,
    caminho_da_maquina,
    carregar_maquina,
)
from tests.unit.test_a_entrada_declarada_vence_o_firmware import _clicar, _na_pagina
from tests.unit.test_o_nome_da_entrada_e_da_posicao import _a_maquina_dela

#: A velocidade dos quatro barramentos: o ``usb2`` e o ``usb4`` são os rápidos.
_BARRAMENTOS = {"usb1": 480.0, "usb2": 10000.0, "usb3": 480.0, "usb4": 10000.0}

#: O pendrive: 5000M no nó ``usb2-port3``, que nenhuma entrada declara.
_PENDRIVE = "2-3"


def _aparelho(caminho: str, mbps: float = 5000.0, classe: str = "08") -> Aparelho:
    return Aparelho(
        no=f"/sys/{caminho}", nome_do_kernel=caminho, produto="Pendrive de prova",
        especie="Armazenamento", classe=classe, velocidade_mbps=mbps,
    )


def _censo(*aparelhos: Aparelho) -> Censo:
    return Censo(
        aparelhos=aparelhos,
        barramentos=tuple(
            Barramento(no=f"/sys/{nome}", nome_do_kernel=nome, velocidade_mbps=mbps)
            for nome, mbps in _BARRAMENTOS.items()),
    )


def _lidas(documento: MaquinaConfig, **plugados: str) -> tuple[NoDeEntrada, ...]:
    """Os nós do ``/sys``: os das entradas, mais o ``usb2-port3`` do pendrive.

    ``plugados`` é ``{nó: caminho do aparelho nele}``; o pendrive está no dele.
    """
    dentro = {"usb2-port3": _PENDRIVE, **plugados}
    nos = [no for porta in documento.mapa.portas.values() for no in porta.nos]
    lidas = []
    for no in dict.fromkeys([*nos, "usb2-port3"]):
        hub, _, numero = no.rpartition("-port")
        aparelho = dentro.get(no, "")
        lidas.append(NoDeEntrada(
            no=no, caminho_sysfs=f"/sys/{no}", hub=hub, numero=int(numero),
            estado="" if aparelho else "not attached", aparelho=aparelho,
            velocidade_mbps=_BARRAMENTOS.get(hub, 480.0)))
    return tuple(lidas)


def _arranjo(censo: Censo) -> dict[str, Any]:
    dado = arranjo_desta_maquina.arranjo(
        carregar=carregar_maquina, ler_o_barramento=lambda: censo,
        ler_o_serial=lambda _no: "")
    assert dado is not None
    return dado


def _usb(dado: dict[str, Any], numero: str) -> tuple[int, str]:
    usb = next(p["usb"] for f in dado["faces"] for p in f["portas"] if p["n"] == numero)
    return usb, dado["usbDe"][numero]


def _pendente(dado: dict[str, Any], caminho: str = _PENDRIVE) -> bool:
    """O aparelho neste caminho está «fora do mapa»? — a pergunta do ``semEntrada``."""
    lidos = dado["leituras"]["agora"]["caminho"].values()
    return caminho in lidos and caminho not in dado["mapa"].values()


@pytest.fixture()
def disco(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> Path:
    """A máquina sintética no ``tmp_path``, e o barramento de mentira com o
    pendrive: o gesto relê a máquina depois de gravar, e lê os nós do ``/sys``
    — aqui, os de mentira."""
    alvo = caminho_da_maquina()
    assert alvo.is_relative_to(tmp_path), f"o maquina.json da régua não está desviado: {alvo}"
    assert declarar_a_maquina(_a_maquina_dela()).gravou
    documento = carregar_maquina()
    monkeypatch.setattr(censo_do_barramento, "ler_o_barramento",
                        lambda: _censo(_aparelho(_PENDRIVE)))
    monkeypatch.setattr(mapa_das_portas, "serial_do_no", lambda _no: "")
    monkeypatch.setattr(ee, "_listar_as_entradas", lambda: _lidas(documento))
    return alvo


# ── 1. o gravador ─────────────────────────────────────────────────────────


def test_o_pendrive_ensinado_na_2_e_lido_na_2(disco: Path) -> None:
    """Pendente → ensinado na 2 → o nó é da 2, e o arranjo o lê lá."""
    com_ele = _censo(_aparelho(_PENDRIVE))
    antes = _arranjo(com_ele)
    assert _pendente(antes), "o pendrive de fora do mapa não aparece pendente"
    def amarras() -> dict[str, tuple[str | None, str | None]]:
        # o NOME que morava no lugar muda de casa na primeira gravação (D1);
        # a amarra (entrada e testemunha) é do Mapear e não se mexe
        return {lugar: (dele.entrada, dele.caminho)
                for lugar, dele in carregar_maquina().lugares.items()}

    antes_das_amarras = amarras()
    documento = carregar_maquina()
    assert ee.ensinar_a_entrada("2", _PENDRIVE, lidas=_lidas(documento)).gravou
    porta = carregar_maquina().mapa.portas["2"]
    assert porta.nos == ["usb1-port3", "usb2-port3"], porta.nos
    assert porta.caminho == "1-3", "o caminho que a entrada já tinha mudou"
    assert amarras() == antes_das_amarras, "o ensinar mexeu na amarra, que é do Mapear"

    depois = _arranjo(com_ele)
    assert not _pendente(depois), "ensinado, o pendrive continua fora do mapa"
    assert _usb(depois, "2") == (3, mapa_das_portas.USB_PELO_APARELHO)
    sem_ele = _arranjo(_censo())
    assert _usb(sem_ele, "2") == (3, mapa_das_portas.USB_PELA_PLACA), (
        "sem o pendrive, a 2 é azul pela placa: o hub do usb2 é 10000M")


def test_a_entrada_sem_caminho_ganha_o_do_lado_20() -> None:
    """Uma entrada do desenho sem nada gravado: o pendrive tem ``peer`` agora
    (``usb1-port9``), os dois nós vão juntos, e o caminho é o do lado 2.0."""
    from dataclasses import replace

    from hefesto_dualsense4unix.integrations.lugar_declarado import Recibo

    dado = _a_maquina_dela()
    dado["mapa"]["faces"][1]["portas"].append("16")
    documento = MaquinaConfig.model_validate(dado)
    gravado: list[dict[str, Any]] = []

    def gravar(declaracao: Any) -> Recibo:
        gravado.append(json.loads(json.dumps(declaracao)))
        return Recibo(True)

    par = NoDeEntrada(no="usb1-port9", caminho_sysfs="/sys/usb1-port9", hub="usb1",
                      numero=9, par="usb2-port3", velocidade_mbps=480.0,
                      estado="not attached")
    lidas = (
        *(replace(e, par="usb1-port9") if e.no == "usb2-port3" else e
          for e in _lidas(documento)),
        par,
    )
    assert ee.ensinar_a_entrada("16", _PENDRIVE, maquina=documento, lidas=lidas,
                                gravar=gravar).gravou
    campos = gravado[-1]["mapa"]["portas"]["16"]
    assert sorted(campos["nos"]) == ["usb1-port9", "usb2-port3"], "o peer não veio junto"
    assert campos["caminho"] == "1-9", "sem caminho, a entrada ganha o do lado 2.0"


@pytest.mark.parametrize(
    ("numero", "caminho", "plugados", "frase"),
    [
        ("99", _PENDRIVE, {}, ee.RECUSA_FORA_DO_MAPA),
        ("5.1", _PENDRIVE, {}, ee.RECUSA_FORA_DO_MAPA),
        ("2", "2-9", {}, ee.RECUSA_O_APARELHO_SAIU),
        ("2", "1-4", {"usb1-port4": "1-4"}, ee.RECUSA_O_APARELHO_JA_TEM_ENTRADA),
        ("2", _PENDRIVE, {"usb1-port3": "1-3"}, ee.RECUSA_A_ENTRADA_OCUPADA),
    ],
)
def test_as_recusas_dizem_a_frase_do_dono(
    disco: Path, numero: str, caminho: str, plugados: dict[str, str], frase: str
) -> None:
    antes = disco.read_bytes()
    with pytest.raises(ValueError, match=frase):
        ee.ensinar_a_entrada(numero, caminho, lidas=_lidas(carregar_maquina(), **plugados))
    assert disco.read_bytes() == antes, "uma recusa escreveu no disco dela"


def test_ligacoes_demais_recusa(disco: Path) -> None:
    """O teto de nós é do ``PortaDeclarada``: a quinta ligação recusa."""
    dado = _a_maquina_dela()
    dado["mapa"]["portas"]["2"]["nos"] = ["usb1-port3", "usb1-port7", "usb1-port8",
                                          "usb1-port9"]
    documento = MaquinaConfig.model_validate(dado)
    with pytest.raises(ValueError, match=ee.RECUSA_LIGACOES_DEMAIS):
        ee.ensinar_a_entrada("2", _PENDRIVE, maquina=documento, lidas=_lidas(documento),
                             gravar=lambda _d: pytest.fail("gravou além do teto"))


def test_o_gesto_grava_e_devolve_o_arranjo_relido(disco: Path) -> None:
    from tests.conftest import exigir_gi_real

    exigir_gi_real("importa `interface.pacotes`, que carrega o GTK")
    from hefesto_dualsense4unix.interface import pacotes

    dono = pacotes.gesto_da_pagina(arranjo_desta_maquina.PAGINA, "entrada-ensinar")
    assert dono is not None, "o ensinar não tem dono"
    volta = dono(None, {"entrada": "2", "caminho": _PENDRIVE}, None)
    assert "usb2-port3" in carregar_maquina().mapa.portas["2"].nos
    relido = volta[arranjo_desta_maquina.CHAVE_DEPOIS_DE_GRAVAR]
    assert not _pendente(relido), "o arranjo relido ainda mostra o pendrive fora do mapa"
    with pytest.raises(ValueError):
        dono(None, {"entrada": "2"}, None)


# ── 2. o clique na página chega ao disco (WebKit, pela ponte do piloto) ──────

_LER = r"""
(function(){
  const plugs = {};
  for (const p of document.querySelectorAll('.plug[data-porta]')) {
    plugs[p.dataset.porta] = (p.dataset.gesto || '') + '|' + (p.dataset.caminho || '');
  }
  const painel = document.getElementById('painel');
  const chip = document.querySelector('#bandeja .chip[data-segurando]');
  const alocados = {};
  for (const c of document.querySelectorAll('#bandeja .chip[data-alocado]')) {
    alocados[c.dataset.ap] = c.querySelector('.num').textContent.trim();
  }
  return JSON.stringify({plugs: plugs, painel: painel ? painel.textContent : '',
                         segurando: chip ? chip.dataset.ap : null, alocados: alocados});
})()
"""


def _entregar(censo: Censo) -> str:
    return arranjo_desta_maquina.js_da_entrega(_arranjo(censo))


def test_o_clique_no_plugue_ensina_pelo_disco(disco: Path) -> None:
    """Chip do pendrive na mão → plugue 2: a mensagem vai ao dono, e a página
    não ensina na memória; relida do disco, o pendrive está na 2."""
    from tests.conftest import exigir_gi_real

    exigir_gi_real("importa `interface.pacotes`, que carrega o GTK")
    from hefesto_dualsense4unix.interface import pacotes

    com_ele = _censo(_aparelho(_PENDRIVE))
    dado = _arranjo(com_ele)
    pendrive = next(i for i, c in dado["leituras"]["agora"]["caminho"].items()
                    if c == _PENDRIVE)
    respostas, mensagens = _na_pagina([
        _entregar(com_ele),
        _LER,
        _clicar(f'#bandeja .chip[data-ap="{pendrive}"]'),
        _LER,
        _clicar('.plug[data-porta="2"]'),
        _LER,
    ])
    solto, segurado, depois_do_clique = (json.loads(respostas[i]) for i in (1, 3, 5))
    assert "fora do mapa" in solto["painel"].lower(), solto["painel"]
    assert pendrive not in solto["alocados"], solto["alocados"]
    assert not any(v.startswith("entrada-ensinar") for v in solto["plugs"].values()), (
        "sem nada na mão, um plugue já leva o gesto de ensinar")
    assert segurado["segurando"] == pendrive, "o chip do pendrive não foi para a mão"
    assert segurado["plugs"]["2"] == f"entrada-ensinar|{_PENDRIVE}", segurado["plugs"]
    assert depois_do_clique["segurando"] == pendrive and (
        pendrive not in depois_do_clique["alocados"]), (
        "a página ensinou na memória antes de o disco responder")

    pedidos = [m for m in mensagens if m.get("gesto") == "entrada-ensinar"]
    assert [(m.get("entrada"), m.get("caminho")) for m in pedidos] == [("2", _PENDRIVE)], (
        f"o clique no plugue não chegou ao piloto: {mensagens}")
    dono = pacotes.gesto_da_pagina(pedidos[0]["pagina"], "entrada-ensinar")  # noqa-acento: chave
    assert dono is not None
    dono(None, pedidos[0], None)

    respostas, _ = _na_pagina([_entregar(com_ele), _LER])
    relida = json.loads(respostas[1])
    assert "fora do mapa" not in relida["painel"].lower(), (
        "relida do disco, a página mostra o pendrive fora do mapa de novo: "
        + relida["painel"])
    assert relida["alocados"].get(pendrive) == "2", relida["alocados"]
