"""A-ABA-PERFIS-APAGA-E-ESQUECE-A-ESCOLHA-01 (21/10/2026).

O «Remover» da aba Perfis apagava o arquivo e deixava a escolha do boot e o último jogo apontando
para o perfil que não existe mais; a linha de comando já os esquecia (`esquecer_o_perfil_apagado`,
O-PERFIL-ATIVO-APAGADO-SOLTA-O-REMAP-E-O-ROTEADOR-01).
O disco é o de verdade, no lar isolado da suíte.

A MORDIDA: tire o `esquecer_o_perfil_apagado` do `remover` (a10), e as duas lembranças ficam.
"""
from __future__ import annotations

from typing import Any

import pytest


from hefesto_dualsense4unix.interface.pacotes import Contexto, a10_perfis
from hefesto_dualsense4unix.utils import session


class _Ponte:
    def __init__(self) -> None:
        self.chamadas: list[str] = []

    def chamar(self, metodo: str, *_a: Any, **_k: Any) -> bool:
        self.chamadas.append(metodo)
        return True


@pytest.fixture(autouse=True)
def _memoria_limpa(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr(a10_perfis, "_ESCOLHIDO", "", raising=False)
    monkeypatch.setattr(a10_perfis, "_ARMADO", None, raising=False)


def _no_disco(*nomes: str) -> None:
    from hefesto_dualsense4unix.profiles.loader import save_profile
    from hefesto_dualsense4unix.profiles.schema import MatchAny, Profile

    for i, nome in enumerate(nomes):
        save_profile(Profile(name=nome, match=MatchAny(), priority=100 - i))


def _remover_duas_vezes(monkeypatch: pytest.MonkeyPatch, nome: str, valendo: str) -> _Ponte:
    from hefesto_dualsense4unix.profiles.loader import load_profile

    monkeypatch.setattr(a10_perfis, "_ESCOLHIDO", nome)
    ctx = Contexto(state={"active_profile": valendo}, mesa=[], conectados=[], estados={})
    ponte = _Ponte()
    with pytest.raises(RuntimeError, match=f"Apagar “{nome}”"):
        a10_perfis.remover(ctx, {}, ponte)
    a10_perfis.remover(ctx, {}, ponte)
    with pytest.raises(FileNotFoundError):
        load_profile(nome)
    return ponte


def test_apagar_pela_aba_esquece_a_escolha_e_o_ultimo_jogo(monkeypatch) -> None:
    """A prova da D-2110-A-ABA-PERFIS-APAGA-PELO-DONO-DA-LINHA-DE-COMANDO."""
    _no_disco("Pragmata", "Sackboy")
    session.gravar_a_escolha("Sackboy")
    session.lembrar_o_ultimo_jogo("Sackboy")
    assert session.load_last_profile() == "Sackboy" and session._ultimo_jogo_cru() == "Sackboy"

    ponte = _remover_duas_vezes(monkeypatch, "Sackboy", valendo="Pragmata")

    assert session.load_last_profile() is None, "a escolha do boot segue no perfil apagado"
    assert session._ultimo_jogo_cru() is None, "o último jogo segue no perfil apagado"
    assert ponte.chamadas == ["launch_env.refresh"]


def test_apagar_outro_perfil_nao_toca_as_lembrancas(monkeypatch) -> None:
    _no_disco("Pragmata", "Sackboy", "Lure")
    session.gravar_a_escolha("Sackboy")
    session.lembrar_o_ultimo_jogo("Sackboy")

    _remover_duas_vezes(monkeypatch, "Lure", valendo="Pragmata")

    assert session.load_last_profile() == "Sackboy" and session._ultimo_jogo_cru() == "Sackboy"


def test_a_aba_e_a_linha_de_comando_esquecem_pelo_mesmo_dono() -> None:
    """Um dono só para esquecer o apagado: a aba e o `profile delete` chamam o mesmo."""
    import inspect

    from hefesto_dualsense4unix.cli import cmd_profile

    for quem in (a10_perfis.remover, cmd_profile.cmd_delete):
        assert "esquecer_o_perfil_apagado(" in inspect.getsource(quem), quem.__qualname__
