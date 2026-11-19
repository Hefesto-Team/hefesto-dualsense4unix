"""O vigia e o install só apagam do ``compatibilitytools.d`` o Proton que o Hefesto extraiu.

A pasta sem o manifesto do Hefesto (um GE antigo, um tkg ou um cachyos de outro programa) não é
sobra e fica, com a Steam fechada e todo jogo no pino.
"""
from __future__ import annotations

from pathlib import Path

from hefesto_dualsense4unix.integrations import proton_pin as pp
from tests.unit.test_o_fixar_proton_desinstala_as_que_sobram import _ferramenta, _vdf

PINO = "GE-Proton11-7-x86_64"
VELHA = "GE-Proton10-34"
DE_FORA = "GE-Proton9-20"
DO_JOGO_DE_FORA = "GE-Proton10-1"


def _casa(tmp_path: Path) -> Path:
    casa = tmp_path / "casa"
    raiz = casa / ".steam" / "steam"
    (raiz / "config").mkdir(parents=True)
    (raiz / "steamapps").mkdir()
    compat = raiz / "compatibilitytools.d"
    for pasta in (PINO, VELHA, DO_JOGO_DE_FORA, DE_FORA):
        _ferramenta(compat, pasta)
    (compat / DE_FORA / pp.MANIFEST_BASENAME).unlink()
    (raiz / "config" / "config.vdf").write_text(
        _vdf({"1": PINO, "2": PINO, "3": DO_JOGO_DE_FORA}), encoding="utf-8")
    return casa


def test_so_a_versao_extraida_pelo_hefesto_sai_e_a_de_fora_fica(tmp_path: Path) -> None:
    """D-1911-O-VIGIA-SO-APAGA-O-PROTON-DO-HEFESTO: a pasta sem o manifesto não é sobra."""
    casa = _casa(tmp_path)
    sobras = pp.versoes_que_sobram(casa, pino=PINO)
    assert [s.pasta.name for s in sobras] == [VELHA]
    saiu, recusadas = pp.desinstalar_as_que_sobram(
        sobras, em_uso=lambda _p: False, steam_barra=lambda: None)
    compat = casa / ".steam" / "steam" / "compatibilitytools.d"
    assert [s.pasta.name for s in saiu] == [VELHA] and not recusadas
    assert sorted(p.name for p in compat.iterdir()) == sorted([PINO, DE_FORA, DO_JOGO_DE_FORA])
