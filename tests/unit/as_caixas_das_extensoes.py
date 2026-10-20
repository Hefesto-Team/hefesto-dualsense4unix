"""As extensões de lançador com caixa do Flatpak, ligadas, para as réguas da carona.

Os lançadores com caixa além do Heroic (Lutris, RetroArch, Dolphin, mGBA) viraram extensões em
19/10/2026 (OS-LANCADORES-ALEM-DA-STEAM-E-DO-HEROIC-VIRAM-EXTENSOES-01). A carona só escreve na
caixa de uma extensão LIGADA (``cura_por_estrada._extensoes_com_caixa``). As réguas que provam a
escrita, o desfazer e a camada do jogo seguem as mesmas: o que muda é que o lançador entra pela
extensão. Este módulo liga as quatro, com os ``id`` e os app ids dos repositórios delas.

Nenhum código de ``src/`` importa este módulo.
"""

from __future__ import annotations

import pytest

from hefesto_dualsense4unix.integrations import cura_por_estrada as cpe

CAIXAS = (
    ("lutris", "Lutris", ("net.lutris.Lutris",)),
    ("retroarch", "RetroArch", ("org.libretro.RetroArch",)),
    ("dolphin", "Dolphin", ("org.DolphinEmu.dolphin-emu",)),
    ("mgba", "mGBA", ("io.mgba.mGBA",)),
)


def ligar(monkeypatch: pytest.MonkeyPatch) -> None:
    """As quatro extensões ligadas, para a carona deste teste."""
    monkeypatch.setattr(cpe, "_extensoes_com_caixa", lambda: CAIXAS)
