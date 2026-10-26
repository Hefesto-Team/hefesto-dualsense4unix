"""O co-op sabe de quem é cada vpad, e o tradutor devolve o físico na grafia da mesa.

**NOTA DE 26/10/2026 (A-HAPTICA-E-DO-JOGO-SEM-PORTAO-DE-QUEM-MEXE-01).** A háptica
deixou de seguir o posto: o jogo toca no endpoint de cada controle e o que toca
ali chega a ele, sem votação de quem mexeu nem de quem o evdev lê. A matriz de
174 casos que provava «vibra o controle que dirige o boneco» saiu junto com o
portão que ela guardava. Ficam aqui as réguas do que o co-op ainda responde:
``CoopManager.quem_alimenta_cada_vpad``.

Nenhum endereço real: faixa forjada ``aa:bb:cc`` com os octetos 4 e 5
zerados; os ``02:fe:`` são os que o produto forja.
"""
from __future__ import annotations

from types import SimpleNamespace
from typing import Any

from hefesto_dualsense4unix.daemon.subsystems.coop import CoopManager, _SecondaryPlayer
from hefesto_dualsense4unix.integrations.uhid_gamepad import player_mac, vpad_mac

P1 = "aabbcc000001"
P2 = "aabbcc000002"
P3 = "aabbcc000003"


def com_dois_pontos(uniq: str) -> str:
    """``aabbcc000001`` → ``aa:bb:cc:00:00:01``: a grafia do ``HID_UNIQ`` no sysfs."""
    return ":".join(uniq[i : i + 2] for i in range(0, 12, 2))



class _Vpad:
    def __init__(self, mac: str | None) -> None:
        if mac is not None:
            self.mac = mac


def _coop(
    primario: str | None, posto: Any, jogadores: dict[str, _SecondaryPlayer]
) -> CoopManager:
    daemon = SimpleNamespace(
        controller=SimpleNamespace(primary_uniq=primario, _evdev=None),
        _gamepad_device=posto,
        config=SimpleNamespace(coop_enabled=True),
    )
    coop = CoopManager(daemon)  # type: ignore[arg-type]
    coop._players = jogadores
    return coop


def _jogador(identidade: str, vpad: Any, *, cedido: bool = False) -> _SecondaryPlayer:
    return _SecondaryPlayer(
        identity=identidade,
        evdev_path="/dev/input/event9",
        reader=None,  # type: ignore[arg-type]
        player_index=2,
        vpad=vpad,
        cedido_ao_primario=cedido,
    )


class TestQuemAlimentaCadaVpad:
    """``CoopManager.quem_alimenta_cada_vpad`` — o posto é do primário de AGORA."""

    def test_o_posto_e_do_primario_de_agora_e_nao_de_quem_ele_nasceu(self) -> None:
        posto = _Vpad(vpad_mac(P1, 1))
        coop = _coop(P2, posto, {P3: _jogador(P3, _Vpad(vpad_mac(P3, 3)))})
        assert coop.quem_alimenta_cada_vpad() == {vpad_mac(P1, 1): P2, vpad_mac(P3, 3): P3}

    def test_o_posto_do_boot_tambem_tem_dono(self) -> None:
        """O piso não deriva de ninguém — e o primário o dirige assim mesmo."""
        coop = _coop(P1, _Vpad(player_mac(1)), {})
        assert coop.quem_alimenta_cada_vpad() == {player_mac(1): P1}

    def test_quem_cedeu_ao_primario_e_quem_espera_o_grab_ficam_de_fora(self) -> None:
        jogadores = {
            P2: _jogador(P2, _Vpad(vpad_mac(P2, 2)), cedido=True),
            P3: _jogador(P3, None),
        }
        coop = _coop(P2, _Vpad(vpad_mac(P1, 1)), jogadores)
        assert coop.quem_alimenta_cada_vpad() == {vpad_mac(P1, 1): P2}

    def test_sem_mac_e_sem_identidade_de_aparelho_nao_ha_o_que_casar(self) -> None:
        jogadores = {
            "path:/dev/input/event9": _jogador("path:/dev/input/event9", _Vpad(vpad_mac(P3, 3))),
            P2: _jogador(P2, _Vpad(None)),
        }
        coop = _coop(None, _Vpad(player_mac(1)), jogadores)
        assert coop.quem_alimenta_cada_vpad() == {}

    def test_o_primario_sem_endereco_nao_da_dono_ao_posto(self) -> None:
        """O primário por ``path:`` (o MAC ainda não resolveu): o posto fica sem dono."""
        coop = _coop(None, _Vpad(player_mac(1)), {})
        coop._daemon.controller._evdev = SimpleNamespace(_device_path="/dev/input/event3")
        assert coop._primary_identity() == "path:/dev/input/event3"
        assert coop.quem_alimenta_cada_vpad() == {}

    def test_o_mac_sai_em_minusculas(self) -> None:
        coop = _coop(P1, _Vpad(vpad_mac(P1, 1).upper()), {})
        assert coop.quem_alimenta_cada_vpad() == {vpad_mac(P1, 1): P1}

    def test_a_mesa_que_muda_no_meio_da_pergunta_nao_derruba_a_resposta(self) -> None:
        """Quem pergunta roda fora do laço: o laço pode sentar alguém no meio."""
        jogadores: dict[str, _SecondaryPlayer] = {}

        class _VpadDoP2:
            @property
            def mac(self) -> str:
                jogadores[P3] = _jogador(P3, _Vpad(vpad_mac(P3, 3)))
                return vpad_mac(P2, 2)

        jogadores[P2] = _jogador(P2, _VpadDoP2())
        coop = _coop(P1, _Vpad(vpad_mac(P1, 1)), jogadores)
        assert coop.quem_alimenta_cada_vpad() == {vpad_mac(P1, 1): P1, vpad_mac(P2, 2): P2}
