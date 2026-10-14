"""A porta USB virtual de cada pad, de mentira (TODO-PAD-TEM-PORTA-PROPRIA-01, 14/10/2026).

Desde 14/10 o endpoint de háptica só nasce na interface do gadget do PRÓPRIO
pad (``pad_usb.registrar_gadget``), e nunca numa âncora emprestada. O caso que
quer um endpoint de pé registra a porta de cada aparelho por aqui, pelo mesmo
dono que o daemon usa; o autouse ``_nenhum_gadget_a_caminho_atravessa`` do
``tests/conftest.py`` limpa o registro entre os casos.
"""

from __future__ import annotations

from collections.abc import Iterable

import pytest

from hefesto_dualsense4unix.integrations import pad_usb


def interface_da_porta(n: int) -> str:
    """A interface do gadget na porta ``n`` do ``vhci_hcd`` (a forma do kernel)."""
    return f"/devices/platform/vhci_hcd.0/usb3/3-{n}/3-{n}:1.0"


def dar_porta(uniq: str, n: int) -> str:
    """O aparelho ``uniq`` ganha a porta ``n``; devolve a interface registrada."""
    interface = interface_da_porta(n)
    pad_usb.registrar_gadget(uniq, interface)
    return interface


def dar_portas(uniqs: Iterable[str]) -> dict[str, str]:
    """Cada aparelho ganha a porta dele, na ordem, a partir da 1."""
    return {u: dar_porta(u, i) for i, u in enumerate(uniqs, start=1)}


def tirar_porta(uniq: str) -> None:
    """O gadget do aparelho desceu."""
    pad_usb.esquecer_gadget(uniq)


class _UmaPortaParaCadaUm(dict[str, str]):
    """O registro em que todo aparelho perguntado já tem a porta dele, uma por aparelho."""

    def get(self, chave: str, default: str | None = None) -> str | None:  # type: ignore[override]
        if not chave:
            return default
        if chave not in self:
            self[chave] = interface_da_porta(len(self) + 1)
        return self[chave]


def todo_pad_tem_porta(monkeypatch: pytest.MonkeyPatch) -> None:
    """Todo aparelho que o som perguntar já tem o gadget dele, cada um numa porta.

    Para o caso cujo assunto não é a porta: é o contrato do produto
    (o pad de cada aparelho tem a porta USB virtual dele), e não um atalho.
    """
    monkeypatch.setattr(pad_usb, "_INTERFACE_DO_APARELHO", _UmaPortaParaCadaUm())
