"""Fechar a janela devolve o que as abas seguravam.

A sprint: FECHAR-A-JANELA-DEVOLVE-O-QUE-AS-ABAS-SEGURAVAM-01.

MEDIDO EM 10/10/2026, antes da cura: `pacotes.largar_o_que_as_abas_seguram`
tinha três chamadores no piloto (a troca de página no `_carregou`, o `_ir` e o
`_relatar`), e nenhum é o fim da janela do produto. O X da janela liga
`destroy` direto em `Gtk.main_quit` (`interface/janela.py`), e depois do
`Gtk.main()` o `_o_processo_da_janela` só desligava a leitura do perfil. O
teste de vibração e o da háptica de qualquer controle seguiam no ar até o teto
do serviço, e o `rumble_passthrough` nunca voltava pelo caminho do «Parar».

A régua entra e sai do `_o_processo_da_janela` sem o GTK, com dois controles no
teste da vibração e um no da háptica, e exige a devolução de cada um. O
`finally` é o ponto por onde todo fim da janela passa: o X, o `agendar_saida`
e o `_morrer`.
"""
from __future__ import annotations

import pathlib
import sys
from typing import Any

import pytest

RAIZ = pathlib.Path(__file__).resolve().parents[2]
sys.path.insert(0, str(RAIZ / "src"))

from tests.conftest import exigir_gi_real

exigir_gi_real("importa `interface.hefesto_vivo`, que carrega o GTK")

from hefesto_dualsense4unix.interface import hefesto_vivo as hv
from hefesto_dualsense4unix.interface.pacotes import a05_vibracao as a05

P1 = "aa:bb:cc:00:00:01"
P2 = "02:fe:00:00:00:02"
P3 = "aa:bb:cc:00:00:03"


class PonteQueAnota:
    """A ponte de mentira, com a assinatura de `app/ipc_bridge` (nada mais frouxo)."""

    def __init__(self) -> None:
        self.chamadas: list[tuple[str, tuple[Any, ...]]] = []

    def rumble_stop(self, uniq: str | None = None) -> bool:
        self.chamadas.append(("rumble_stop", (uniq,)))
        return True

    def rumble_passthrough(self, enabled: bool = True, uniq: str | None = None) -> bool:
        self.chamadas.append(("rumble_passthrough", (enabled, uniq)))
        return True

    def haptica_testar(self, uniq: str, ligado: bool) -> tuple[bool, dict[str, Any] | None]:
        self.chamadas.append(("haptica_testar", (uniq, ligado)))
        return True, {"status": "ok"}


@pytest.fixture(autouse=True)
def _mesa_limpa():
    """Nenhum caso herda as marcas do anterior: a suíte roda no MESMO processo."""
    a05.parar_o_teste()
    a05.parar_o_teste_da_haptica()
    yield
    a05.parar_o_teste()
    a05.parar_o_teste_da_haptica()


def test_sair_da_janela_devolve_cada_controle_em_teste(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """Dois na vibração e um na háptica: cada um volta ao jogo, pelo endereço dele."""
    ponte = PonteQueAnota()
    monkeypatch.setattr(hv, "ponte", ponte)
    a05._EM_TESTE.update({P1, P2})
    a05._EM_TESTE_DA_HAPTICA.add(P3)

    with hv._o_processo_da_janela():
        assert ponte.chamadas == [], "a janela largou antes de sair"

    for uniq in (P1, P2):
        assert ("rumble_stop", (uniq,)) in ponte.chamadas, (
            f"fechar a janela não parou os motores de {uniq}: {ponte.chamadas}")
        assert ("rumble_passthrough", (True, uniq)) in ponte.chamadas, (
            f"fechar a janela não devolveu a vibração de {uniq} ao jogo: "
            f"{ponte.chamadas}")
        parou = ponte.chamadas.index(("rumble_stop", (uniq,)))
        devolveu = ponte.chamadas.index(("rumble_passthrough", (True, uniq)))
        assert parou < devolveu, "o passthrough veio antes do stop: o par fixo cala o jogo"
    assert ("haptica_testar", (P3, False)) in ponte.chamadas, (
        f"fechar a janela não calou o teste da háptica de {P3}: {ponte.chamadas}")
    assert a05.em_teste() == frozenset()
    assert a05.em_teste_da_haptica() == frozenset()


def test_sair_da_janela_por_erro_tambem_devolve(monkeypatch: pytest.MonkeyPatch) -> None:
    """A janela que cai com exceção passa pelo mesmo `finally`."""
    ponte = PonteQueAnota()
    monkeypatch.setattr(hv, "ponte", ponte)
    a05._EM_TESTE.add(P1)

    with pytest.raises(RuntimeError), hv._o_processo_da_janela():
        raise RuntimeError("a janela caiu")

    assert ("rumble_passthrough", (True, P1)) in ponte.chamadas


def test_sair_sem_teste_ligado_nao_fala_com_o_servico(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """Fechar a janela sem teste no ar não mexe na vibração do jogo."""
    ponte = PonteQueAnota()
    monkeypatch.setattr(hv, "ponte", ponte)
    with hv._o_processo_da_janela():
        pass
    assert ponte.chamadas == []
