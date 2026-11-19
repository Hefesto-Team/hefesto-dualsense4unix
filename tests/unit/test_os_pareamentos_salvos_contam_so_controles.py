"""OS-PAREAMENTOS-SALVOS-CONTAM-SO-CONTROLES-01 — o fone pela metade não é controle pela metade."""

from __future__ import annotations

from collections.abc import Sequence

from hefesto_dualsense4unix.integrations.exame_da_mesa import (
    ESTADO_CERTO,
    ESTADO_PROBLEMA,
    pareamentos,
)

FONE = "/org/bluez/hci0/dev_AA_BB_CC_00_00_31"
DUALSENSE = "/org/bluez/hci0/dev_AA_BB_CC_00_00_32"
CLASSE_DO_FONE = 0x240404
CLASSE_DO_DUALSENSE = 0x002508


def _bluez(aparelhos: dict[str, dict[str, str]]):  # type: ignore[no-untyped-def]
    """Um ``busctl`` de mentira que responde por aparelho e por propriedade."""
    arvore = "/\n/org/bluez\n/org/bluez/hci0\n" + "".join(f"{c}\n" for c in aparelhos)

    def rodar(argumentos: Sequence[str]) -> str | None:
        if argumentos[0] == "tree":
            return arvore
        return aparelhos.get(argumentos[2], {}).get(argumentos[-1])

    return rodar


def _pela_metade(classe: int) -> dict[str, str]:
    return {"Paired": "b true", "Bonded": "b false", "Class": f"u {classe}"}


def test_o_fone_pela_metade_nao_acusa_controle() -> None:
    """D-1911-O-CHECK-UP-CONTA-SO-PAREAMENTO-DE-CONTROLE: só um fone pela metade."""
    item = pareamentos(executar=_bluez({FONE: _pela_metade(CLASSE_DO_FONE)}))
    assert item.estado == ESTADO_CERTO, item.porque
    assert "Nenhum controle" in item.porque


def test_o_dualsense_pela_metade_acusa_e_o_fone_nao_entra_na_conta() -> None:
    """O DualSense no mesmo estado acusa um, e o fone ao lado não vira o segundo."""
    item = pareamentos(executar=_bluez({
        FONE: _pela_metade(CLASSE_DO_FONE),
        DUALSENSE: _pela_metade(CLASSE_DO_DUALSENSE),
    }))
    assert item.estado == ESTADO_PROBLEMA
    assert item.porque.startswith("1 pareamento"), item.porque
