"""A mira ganha horizontal e vertical na tela: o desenho anda até o mockup, em duas opções.

MORDIDAS: o gesto da horizontal gravar nos dois eixos reprova; o pacote pintar os campos novos
com a página de antes reprova; o `documento` sem a opção B reprova.
"""

from __future__ import annotations

import asyncio
import sys
from pathlib import Path
from typing import Any

import pytest

from hefesto_dualsense4unix.core import roteador_de_movimento as rot
from hefesto_dualsense4unix.daemon.ipc_server import IpcServer
from hefesto_dualsense4unix.daemon.lifecycle import Daemon
from hefesto_dualsense4unix.profiles import loader
from hefesto_dualsense4unix.profiles.manager import ProfileManager
from hefesto_dualsense4unix.profiles.schema import MatchAny, Profile
from hefesto_dualsense4unix.testing import FakeController

RAIZ = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(RAIZ / "src" / "hefesto_dualsense4unix" / "interface"))

P1, P2, P3, P4 = (f"aa:bb:cc:00:00:0{n}" for n in range(1, 5))


class _Ponte:
    def __init__(self) -> None:
        self.pedidos: list[dict[str, Any]] = []

    def mira_set_detalhado(self, **campos: Any) -> dict[str, Any]:
        self.pedidos.append(campos)
        return {"status": "ok"}


def _desliza(gesto: str, uniq: str, valor: int) -> list[dict[str, Any]]:
    import pacotes

    ponte = _Ponte()
    fn = pacotes.gesto_da_pagina("calibrar-sensores.html", gesto)
    assert fn is not None, gesto
    fn(None, {"uniq": uniq, "valor": str(valor), "tipo": "input",  # type: ignore[arg-type]
              "evento": "input"}, ponte)
    return ponte.pedidos


@pytest.mark.parametrize("uniq", [P1, P2, P3, P4])
@pytest.mark.parametrize(
    ("gesto", "valor", "campos"),
    [
        ("mira-sensibilidade-h", 7, {"sensibilidade_h": 7}),
        ("mira-sensibilidade-v", 0, {"sensibilidade_v": 0}),
        ("mira-inicio", 35, {"piso": 0.35}),
        ("mira-velocidade", 360, {"velocidade_do_jogo": 360.0}),
    ],
)
def test_cada_gesto_grava_o_seu_campo_na_peca_certa(
    uniq: str, gesto: str, valor: int, campos: dict[str, Any]
) -> None:
    assert _desliza(gesto, uniq, valor) == [{"uniq": uniq, **campos}]


@pytest.mark.parametrize("gesto", ["mira-sensibilidade-h", "mira-sensibilidade-v"])
def test_o_eixo_recusa_fora_de_0_a_10(gesto: str) -> None:
    with pytest.raises(ValueError, match="fora de 0-10"):
        _desliza(gesto, P2, 11)


@pytest.fixture
def perfis(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> Path:
    alvo = tmp_path / "profiles"
    alvo.mkdir()

    def _dir(ensure: bool = False) -> Path:
        return alvo

    monkeypatch.setattr(loader, "profiles_dir", _dir)
    return alvo


def _servidor(tmp_path: Path) -> IpcServer:
    loader.save_profile(Profile(name="Ensaio", match=MatchAny(type="any")))
    controle = FakeController(transport="usb")  # type: ignore[arg-type]
    controle.primary_uniq = P1  # type: ignore[attr-defined]
    daemon = Daemon(controller=controle)
    gerente = ProfileManager(controller=controle, store=daemon.store)
    servidor = IpcServer(
        controller=controle, store=daemon.store, profile_manager=gerente,
        socket_path=tmp_path / "t.sock", daemon=daemon,
    )
    daemon.store.set_active_profile("Ensaio")
    return servidor


def test_a_horizontal_do_p2_nao_muda_o_p1_e_volta_pelo_outro_transporte(
    perfis: Path, tmp_path: Path
) -> None:
    servidor = _servidor(tmp_path)
    asyncio.run(servidor._handlers["mira.set"]({"uniq": P2, "sensibilidade_h": 9}))
    assert rot.parametros_da_peca(servidor.store, P2).sensibilidade_h == 9
    assert rot.parametros_da_peca(servidor.store, P2).sensibilidade_v == rot.SENSIBILIDADE_PADRAO
    assert rot.parametros_da_peca(servidor.store, P1).sensibilidade_h == rot.SENSIBILIDADE_PADRAO
    outra_grafia = P2.replace(":", "").upper()
    assert rot.parametros_da_peca(servidor.store, outra_grafia).sensibilidade_h == 9
    gravado = loader.load_profile("Ensaio").controllers["aabbcc000002"].movimento
    assert gravado.model_fields_set == {"sensibilidade_h"}


def test_o_mockup_traz_as_duas_opcoes() -> None:
    a = (RAIZ / "mockup" / "calibrar-sensores.html").read_text(encoding="utf-8")
    b = (RAIZ / "mockup" / "escolha" / "calibrar-sensores-b.html").read_text(encoding="utf-8")
    for doc in (a, b):
        for gesto in ("mira-sensibilidade-h", "mira-sensibilidade-v", "mira-inicio",
                      "mira-velocidade", "calibrar-sinal", "calibrar-rampa"):
            assert f'data-gesto="{gesto}"' in doc, gesto
        assert 'data-gesto="mira-sensibilidade"' not in doc
    assert 'id="v-sinal"' in b and 'id="v-sinal"' not in a


def test_o_desenho_para_no_mockup() -> None:
    from hefesto_dualsense4unix.interface import onde

    publicado = onde.pagina("calibrar-sensores.html", publicado=True).read_text(encoding="utf-8")
    assert 'data-gesto="mira-sensibilidade"' in publicado
    assert 'data-gesto="mira-sensibilidade-h"' not in publicado


def _ctx(entradas: list[dict[str, Any]]) -> Any:
    import pacotes

    mesa = [{"pref": f"p{n}", "uniq": e["uniq"], "jogador": n, "cor": "cosmic-red",
             "nome": "Cosmic Red", "via": "USB"} for n, e in enumerate(entradas, 1)]
    return pacotes.Contexto(state={}, mesa=mesa, conectados=entradas, estados={})


def _entrada(uniq: str, **mira: Any) -> dict[str, Any]:
    return {"uniq": uniq, "is_primary": False, "connected": True, "inputs": {},
            "sinal": {"estado": "contrario"}, "rampa": {"subindo": True, "valor": 0.2},
            "mira": {"sensibilidade": 6, "sensibilidade_h": 0, "sensibilidade_v": 7,
                     "zona_morta_graus_s": 3.0, "gatilho": None, "piso": 0.31,
                     "velocidade_do_jogo": 240.0, **mira}}


def test_com_a_pagina_de_antes_o_pacote_nao_pinta_o_campo_novo() -> None:
    import pacotes.a11_calibrar_sensores as a11

    corpo = a11.pacote(_ctx([_entrada(P1)]))
    coluna = corpo["colunas"]["p1"]
    assert "mira-sensibilidade-h" not in coluna and "sinal-estado" not in coluna
    assert "mira-sensibilidade" in coluna
    assert 'data-gesto="mira-sensibilidade-h"' not in str(corpo["blocos"])


@pytest.mark.parametrize("desenho", ["a", "b"])
def test_publicada_a_escolha_cada_jogador_ve_os_seus_numeros(
    monkeypatch: pytest.MonkeyPatch, desenho: str
) -> None:
    import calibrar
    import pacotes.a11_calibrar_sensores as a11

    monkeypatch.setattr(a11, "_OPCAO_PUBLICADA", [desenho])
    entradas = [_entrada(P1), _entrada(P2, sensibilidade_h=8), _entrada(P3), _entrada(P4)]
    corpo = a11.pacote(_ctx(entradas))
    assert corpo["colunas"]["p1"]["mira-sensibilidade-h-num"] == "0"
    assert corpo["colunas"]["p2"]["mira-sensibilidade-h-num"] == "8"
    assert corpo["colunas"]["p1"]["mira-inicio-num"] == "31"
    assert corpo["colunas"]["p1"]["mira-velocidade-num"] == "240"
    assert corpo["colunas"]["p3"]["sinal-estado"] == "contrario"
    assert corpo["colunas"]["p4"]["rampa-estado"] == calibrar.RAMPA_SUBINDO
    assert 'data-gesto="mira-sensibilidade-h"' in str(corpo["blocos"])
