"""O-DESLIGADO-DE-ONTEM-01 — o aviso do opt-out antigo saiu da tela, com os nomes velhos dos modos.

Por pedido (29/10/2026, O-AVISO-DO-OPT-OUT-ANTIGO-SAI-COM-OS-NOMES-VELHOS-01), o aviso
«escolha “Jogar pelo Hefesto” ou “Conexão Nativa (Sony)” aqui em cima» sai: nenhum dos dois nomes
existe na tela de hoje. Com o ``gamepad_disabled.flag`` gravado e um controle ligado, a lista que a
aba Sistema recebe não o traz.
"""

from __future__ import annotations

from tests.conftest import exigir_gi_real

exigir_gi_real("test_o_desligado_de_ontem_01: importa código da janela GTK")

import pathlib
import sys
from typing import Any

RAIZ = pathlib.Path(__file__).resolve().parents[2]
INTERFACE = RAIZ / "src" / "hefesto_dualsense4unix" / "interface"
for _caminho in (str(RAIZ / "src"), str(INTERFACE)):
    if _caminho not in sys.path:
        sys.path.insert(0, _caminho)

from hefesto_dualsense4unix.app.actions import home_actions
from hefesto_dualsense4unix.app.actions.jogar import painel
from hefesto_dualsense4unix.utils import session
from pacotes import Contexto
from pacotes import a01_jogar, a09_sistema

_INERTE: dict[str, Any] = {
    "connected": True,
    "native_mode": False,
    "gamepad_emulation": {"enabled": False},
    "paused": False,
    "controllers": [{"uniq": "aa:bb:cc:00:00:01", "connected": True, "player_slot": 1}],
}

_NOMES_VELHOS = ("Jogar pelo Hefesto", "Conexão Nativa", "sessão anterior")


def test_a_lista_da_sistema_nao_traz_o_aviso_do_opt_out(monkeypatch: Any,
                                                        tmp_path: pathlib.Path) -> None:
    """Com o opt-out gravado e um controle, nenhuma linha fala do opt-out nem dos nomes velhos."""
    (tmp_path / "gamepad_disabled.flag").write_text("", encoding="utf-8")
    monkeypatch.setattr(session, "config_dir", lambda *a, **k: tmp_path)
    assert painel.modo_lembrado().ligado is False, "o opt-out não ficou gravado"
    um = _INERTE["controllers"]
    ctx = Contexto(state=_INERTE, mesa=um, conectados=um, estados={})
    linhas = a01_jogar.coluna_de_atencao(ctx)
    assert not [a for a in linhas if "opt_out" in a.get("fonte", "")], linhas
    for linha in linhas:
        for nome in _NOMES_VELHOS:
            assert nome not in linha.get("texto", ""), linha


def test_a_funcao_e_o_tema_do_aviso_sairam() -> None:
    """Sem a função no dono e sem o tema dela na aba Sistema."""
    assert not hasattr(home_actions, "aviso_de_opt_out_antigo")
    assert not [f for f in a09_sistema.TEMA_DA_FONTE if "opt_out" in f]
