"""R-13 (auditoria 23/07) — a numeração de jogador para de colidir.

A queixa dela: *"dois 'player 2' e dois 'player 1' em vez de 1, 2, 3, 4"*.

Estado medido em 23/07: os EXTERNOS ocupam os slots 1 (Pro Nintendo) e 3
(8BitDo); o DualSense branco é slot 2. O co-op numera por conta própria — 1 no
primário, 2..N nos secundários — e escreve isso direto nos nós sysfs de
player-LED. Duas autoridades, dois espaços de numeração, mesma lâmpada.

Duas correções contidas, ambas independentes do R-20:

1. **sem secundário não há co-op** — `should_be_active()` liga pela preferência
   persistida (`coop_enabled.flag`, que é 1 aqui), NÃO pela contagem de
   controles; a docstring do módulo promete um gate de "2+ controles" que nunca
   existiu. Com um DualSense só, o co-op cravava 1 no primário — e o Pro
   Nintendo já era 1. A correção é no EFEITO: mexer no gate exigiria enumerar
   `/dev/input` por tick (o que o PERF-MULTI-CONTROLLER-01 removeu) e faria o
   co-op piscar a cada blip de link.

2. **o piso dos externos considera o alcance do co-op** — `_ds_reserve()` só
   olhava os slots do registry dos DualSense, então um externo podia receber um
   número que o co-op estava acendendo em outro controle.
"""

from __future__ import annotations

from typing import Any


class _CoopFalso:
    def __init__(self, *, ativo: bool, secundarios: int) -> None:
        self._ativo = ativo
        self._secundarios = secundarios

    def should_be_active(self) -> bool:
        return self._ativo

    def player_count(self) -> int:
        return 1 + self._secundarios


class _RegistryFalso:
    def __init__(self, slots: dict[str, int]) -> None:
        self._slots = slots

    def snapshot(self) -> dict[str, int]:
        return dict(self._slots)


def _piso(slots: dict[str, int], coop: Any) -> int:
    """Roda o `_ds_reserve` REAL sobre dublês."""
    import hefesto_dualsense4unix.daemon.subsystems.coop as coop_mod
    from hefesto_dualsense4unix.daemon.subsystems.external_identity import (
        ExternalLedSync,
    )

    daemon = type("D", (), {"identity_registry": _RegistryFalso(slots)})()
    original = coop_mod.get_coop_manager
    coop_mod.get_coop_manager = lambda _d: coop  # type: ignore[assignment]
    try:
        sync = ExternalLedSync.__new__(ExternalLedSync)
        sync._daemon = daemon  # type: ignore[attr-defined]
        return sync._ds_reserve()
    finally:
        coop_mod.get_coop_manager = original  # type: ignore[assignment]


class TestPisoDosExternos:
    def test_sem_coop_o_piso_e_so_o_maior_slot_dualsense(self) -> None:
        piso = _piso({"branco": 2}, _CoopFalso(ativo=False, secundarios=0))
        assert piso == 2

    def test_coop_com_secundarios_empurra_os_externos(self) -> None:
        """O caso dela: co-op com 2 DualSense usa 1 e 2 — externo começa em 3."""
        piso = _piso({"branco": 2, "roxo": 1}, _CoopFalso(ativo=True, secundarios=1))
        assert piso >= 2

    def test_coop_com_quatro_jogadores_reserva_ate_quatro(self) -> None:
        piso = _piso({"branco": 1}, _CoopFalso(ativo=True, secundarios=3))
        assert piso == 4, (
            "com 4 jogadores de co-op, um externo não pode receber 1..4 — "
            "seriam dois controles com o mesmo número aceso"
        )

    def test_coop_ativo_sem_secundario_nao_levanta_o_piso(self) -> None:
        """Sem secundário o co-op não acende nada (item 4) — nada a reservar."""
        piso = _piso({"branco": 1}, _CoopFalso(ativo=True, secundarios=0))
        assert piso == 1


class TestCoopSemSecundarioNaoEscreveLed:
    def test_o_guard_existe_antes_de_montar_os_alvos(self) -> None:
        from pathlib import Path

        fonte = (
            Path(__file__).resolve().parents[2]
            / "src/hefesto_dualsense4unix/daemon/subsystems/coop.py"
        ).read_text(encoding="utf-8")
        corpo = fonte.split("def _apply_coop_player_leds", 1)[1].split("\n    def ", 1)[0]
        antes_dos_alvos = corpo.split("targets: list", 1)[0]
        assert "if not self._players:" in antes_dos_alvos, (
            "sem secundário o co-op não pode cravar player-LED 1 no primário — "
            "é o que produzia 'dois player 1' com o Pro Nintendo no slot 1"
        )


# ---------------------------------------------------------------------------
# COOP-QUE-NÃO-DESMONTA-01 / E3 — o número do jogador para de trocar de dono
# ---------------------------------------------------------------------------
#
# A queixa desta metade é irmã da de cima e mais silenciosa: o número do jogador
# é REUSADO de propósito (o jogo quer P1..PN contíguos), e o MAC do vpad saía
# desse número. Com três controles e uma queda no meio, **o MAC do Jogador 2
# passava a pertencer a outra pessoa** — e um jogo que salve por slot de
# dispositivo troca os perfis de dono sem uma linha de log.
#
# A cura NÃO é parar de reusar o índice; é desacoplar o MAC dele
# (`integrations/uhid_gamepad.vpad_mac`). Estas réguas medem o desacoplamento,
# com DUBLÊ — a prova de aparelho (dois controles, o primário cai e volta) é da
# MESA-DE-QUATRO-01, por `D-0609-A-BANCADA-PROVA-NAO-BLOQUEIA`.
#
# Os endereços abaixo estão na máscara da casa (octetos 4 e 5 zerados), e os
# `02:fe:` que aparecem são endereço FABRICADO por nós — não é de ninguém.

#: Os quatro plásticos do alvo desta casa, com o endereço mascarado.
_A = "aa:bb:cc:00:00:01"
_B = "aa:bb:cc:00:00:02"
_C = "e8:47:3a:00:00:d8"
_D = "e8:47:3a:00:00:f0"


class TestOMacDoVpadSegueOAparelho:
    """O MAC do vpad é do CONTROLE, e o número do jogador é da MESA."""

    def test_o_mesmo_controle_mantem_o_mac_em_qualquer_numero(self) -> None:
        """O aceite da E3, em uma linha.

        Mordida: devolva `vpad_mac` para `return player_mac(player)` e os quatro
        números dão quatro MACs diferentes para o MESMO plástico.
        """
        from hefesto_dualsense4unix.integrations.uhid_gamepad import vpad_mac

        macs = {vpad_mac(_A, numero) for numero in (1, 2, 3, 4)}
        assert len(macs) == 1, (
            f"o mesmo controle recebeu {len(macs)} MACs de vpad ao trocar de "
            f"número de jogador: {sorted(macs)}"
        )

    def test_a_noite_dela_o_controle_cai_volta_e_o_jogo_ve_o_mesmo_device(
        self,
    ) -> None:
        """O roteiro do journal de 02/08, reduzido ao que a E3 responde.

        `t=0` A(P2) e B(P3) na mesa · `t=5` A cai e B é renumerado · `t=8` A
        volta e pega o número que sobrou. O que o JOGO enxerga tem de ser: A com
        o MAC de sempre, B com o MAC de sempre.
        """
        from hefesto_dualsense4unix.integrations.uhid_gamepad import UhidDualSense

        antes = {
            ident: UhidDualSense(player=n, identity=ident).mac
            for ident, n in ((_A, 2), (_B, 3))
        }
        # A queda de A libera o índice 2, e `_next_player_index` o entrega a B.
        depois = {
            ident: UhidDualSense(player=n, identity=ident).mac
            for ident, n in ((_B, 2), (_A, 3))
        }
        assert depois == antes, (
            "o MAC do vpad trocou de dono na renumeração — é o defeito que a E3 "
            f"cura: antes={antes} depois={depois}"
        )

    def test_quatro_na_mesa_nenhum_par_repete_o_mac(self) -> None:
        """MAC repetido mata o probe do uhid com -EEXIST (co-op de 4 vira 1)."""
        from hefesto_dualsense4unix.integrations.uhid_gamepad import vpad_mac

        macs = [vpad_mac(ident, n) for n, ident in enumerate((_A, _B, _C, _D), 1)]
        assert len(set(macs)) == 4, f"dois vpads nasceram com o mesmo MAC: {macs}"

    def test_as_duas_grafias_do_endereco_dao_o_mesmo_vpad(self) -> None:
        """`a0fa9c…` (journal/`controllers.json`) e `a0:fa:9c:…` são o MESMO."""
        from hefesto_dualsense4unix.integrations.uhid_gamepad import vpad_mac

        assert vpad_mac(_A, 2) == vpad_mac(_A.replace(":", ""), 2)
        assert vpad_mac(_A.upper(), 2) == vpad_mac(_A, 2)

    def test_o_mac_derivado_e_o_do_numero_nunca_se_cruzam(self) -> None:
        """Os dois espaços são disjuntos por CONSTRUÇÃO, não por sorte.

        Todo MAC derivado tem o bit 0x80 no terceiro octeto; todo MAC de
        fallback tem `00:00:00` ali. Sem esta reserva, um hash azarado daria
        dois vpads com o mesmo MAC — o -EEXIST de volta pela porta da cura.
        """
        from hefesto_dualsense4unix.integrations.uhid_gamepad import (
            player_mac,
            vpad_mac,
        )

        pisos = {player_mac(n) for n in range(1, 6)}
        for ident in (_A, _B, _C, _D):
            derivado = vpad_mac(ident, 2)
            assert derivado not in pisos
            assert int(derivado.split(":")[2], 16) & 0x80, derivado

    def test_identidade_instavel_recua_para_o_numero(self) -> None:
        """`dev:` e `path:` não prometem estabilidade que não têm.

        O node evdev é RENUMERADO pelo kernel a cada replug (é o que o journal
        de 02/08 mostra) e a instância HID também muda. Derivar o MAC deles
        seria trocar um MAC instável por outro, com a agravante de parecer
        curado.
        """
        from hefesto_dualsense4unix.integrations.uhid_gamepad import (
            player_mac,
            vpad_mac,
        )

        for instavel in (None, "", "path:/dev/input/event30", "dev:0003:054C:0CE6.0008"):
            assert vpad_mac(instavel, 3) == player_mac(3), instavel

    def test_a_derivacao_sobrevive_a_um_daemon_novo(self) -> None:
        """`hashlib`, nunca `hash()` — e esta régua é a que separa os dois.

        O `hash()` de `str` é salgado por processo (`PYTHONHASHSEED`): com ele o
        MAC do vpad mudaria a cada reinício do daemon, e o sintoma seria
        idêntico ao defeito curado — o jogo vendo um controle novo onde está o
        mesmo plástico. Dois interpretadores com sementes DIFERENTES têm de
        responder a mesma coisa.
        """
        import os
        import subprocess
        import sys

        codigo = (
            "from hefesto_dualsense4unix.integrations.uhid_gamepad import vpad_mac;"
            f"print(vpad_mac({_A!r}, 2))"
        )
        respostas = set()
        for semente in ("0", "1", "12345"):
            ambiente = dict(os.environ, PYTHONHASHSEED=semente)
            saida = subprocess.run(
                [sys.executable, "-c", codigo],
                capture_output=True, text=True, check=True, env=ambiente,
            )
            respostas.add(saida.stdout.strip())
        assert len(respostas) == 1, (
            f"o MAC do vpad mudou com a semente de hash do processo: {respostas}"
        )


class TestACuraChegaAoProduto:
    """De nada adianta a função certa se a identidade não chega até ela.

    O caminho é `coop._promote_player` → `virtual_pad.make_virtual_pad` →
    `_try_uhid` → o vpad. Os dois primeiros degraus já passavam `identity`
    desde a MÁSCARA-POR-JOGADOR-01; o terceiro a descartava.
    """

    def _fabrica(self, monkeypatch: Any, identity: str | None) -> Any:
        from hefesto_dualsense4unix.integrations import uhid_gamepad, virtual_pad

        monkeypatch.setattr(uhid_gamepad, "uhid_available", lambda: True)
        monkeypatch.setattr(uhid_gamepad.UhidDualSense, "start", lambda self: True)
        monkeypatch.setattr(
            uhid_gamepad.UhidDualSense, "wait_for_bind", lambda self, _t=0.0: True
        )
        return virtual_pad.make_virtual_pad(
            "dualsense", identity=identity, player=2, allow_uhid=True
        )

    def test_o_vpad_que_a_factory_entrega_traz_o_mac_do_aparelho(
        self, monkeypatch: Any
    ) -> None:
        from hefesto_dualsense4unix.integrations.uhid_gamepad import vpad_mac

        pad = self._fabrica(monkeypatch, _A)
        assert pad is not None and pad.backend == "uhid"
        assert pad.mac == vpad_mac(_A, 2), (
            "a identidade morreu na factory — o vpad nasceu com o MAC do NÚMERO "
            f"do jogador ({pad.mac}) em vez do MAC do aparelho"
        )

    def test_sem_identidade_a_factory_entrega_o_contrato_historico(
        self, monkeypatch: Any
    ) -> None:
        """Quem não sabe de quem é o vpad continua recebendo `02:fe:00:00:00:0N`."""
        from hefesto_dualsense4unix.integrations.uhid_gamepad import player_mac

        pad = self._fabrica(monkeypatch, None)
        assert pad is not None and pad.mac == player_mac(2)
