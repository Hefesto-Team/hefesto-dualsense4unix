"""O perfil novo nasce em «Padrão», na vibração, na háptica e no volume (04/10/2026).

O-DESLIGADO-DEIXA-O-JOGO-DECIDIR-01, item 4 da seção «A decisão dela de 04/10». «Padrão» é só o
rótulo de tela da chave `balanceado` (1,0x), e o perfil que acaba de nascer NÃO opina: a vibração
fica sem `policy` (vale a política da casa, que nasce `balanceado`) e o alto-falante fica sem a
seção `speaker` (o controle nasce nos 100% de sempre na adoção). As duas pontas são o que se
prova aqui: se uma delas mudasse, o perfil novo deixaria de nascer em Padrão sem aviso.

MORDIDAS: o default `balanceado` do `DaemonConfig`; o 1,0 do `balanceado`; os 100% da adoção.
"""

from __future__ import annotations

from types import SimpleNamespace

from hefesto_dualsense4unix.core.backend_pydualsense import VOLUME_PADRAO_DO_SOM
from hefesto_dualsense4unix.core.speaker_scale import volume_do_percentual
from hefesto_dualsense4unix.daemon.lifecycle import DaemonConfig
from hefesto_dualsense4unix.daemon.subsystems.rumble import RUMBLE_POLICY_MULT
from hefesto_dualsense4unix.profiles.manager import ProfileManager
from hefesto_dualsense4unix.profiles.schema import MatchManual, Profile


def _perfil_novo() -> Profile:
    return Profile(name="novo", match=MatchManual())


def test_o_perfil_novo_nao_opina_na_vibracao_e_a_casa_e_padrao() -> None:
    assert _perfil_novo().rumble.policy is None
    assert DaemonConfig().rumble_policy == "balanceado"
    assert RUMBLE_POLICY_MULT["balanceado"] == 1.0, "Padrão é o sinal do jogo como veio"


def test_o_perfil_novo_nao_opina_no_volume_e_a_adocao_e_cem_por_cento() -> None:
    assert _perfil_novo().speaker is None
    assert volume_do_percentual(100) == VOLUME_PADRAO_DO_SOM


def test_ativar_o_perfil_novo_nao_escreve_volume_nenhum() -> None:
    """Sem seção, o gerente não chama o applier: o 100% da adoção segue valendo."""
    chamadas: list[tuple] = []
    gerente = SimpleNamespace(speaker_applier=lambda *a, **k: chamadas.append((a, k)))
    ProfileManager.apply_speaker(gerente, _perfil_novo())  # type: ignore[arg-type]
    assert chamadas == []
