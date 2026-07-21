"""Recuperação do vpad do P1 que degradou para uinput (rede de segurança).

Antes de VPAD-03/BT-01 esta promoção era o CONSERTO do boot: o `lifecycle` cria
o gamepad antes do `controller.connect()`, então o vpad nascia sem hidraw de
onde copiar o blueprint e caía no uinput para sempre. Com o blueprint canônico
embutido o vpad já NASCE uhid (sem depender de físico) e a promoção virou rede
de segurança: recupera o vpad que caiu no uinput por razão transitória (ex.:
/dev/uhid ainda sem ACL na primeira sessão pós-install), chamada quando o
controle conecta.

O que trava aqui (ressalvas dos sprints):
- precheck `uhid_available()` (VPAD-01): com o uhid persistentemente quebrado,
  destruir e recriar o vpad uinput que FUNCIONA a cada conexão seria input drop
  em loop no meio do jogo;
- cooldown compartilhado com a re-seleção da GUI (VPAD-01/VPAD-02): o precheck
  não pega o uhid que aceita o CREATE2 mas nunca faz bind — sem a trava, cada
  reconexão BT derrubaria o vpad uinput dentro da mesma janela de falha;
- backend fake nunca promove (VPAD-08): o smoke não registra um Edge real.
"""
from __future__ import annotations

import time
from types import SimpleNamespace
from typing import Any

import pytest

from hefesto_dualsense4unix.daemon.subsystems import gamepad as gp
from hefesto_dualsense4unix.integrations import uhid_gamepad


class _FakeUinputPad:
    flavor = "dualsense"

    def __init__(self) -> None:
        self.parado = False

    def stop(self) -> None:
        self.parado = True


def _controller(*, backend_real: bool = True) -> Any:
    """`hidraw_path` presente = backend pydualsense; ausente = fake (VPAD-08)."""
    if backend_real:
        return SimpleNamespace(hidraw_path=lambda uniq=None: None)
    return SimpleNamespace()


class _FakeDaemon:
    def __init__(
        self, device: Any, *, backend_real: bool = True, emulacao_desejada: bool = True
    ) -> None:
        self._gamepad_device = device
        self.controller = _controller(backend_real=backend_real)
        self.config = type("_Cfg", (), {"gamepad_flavor": "dualsense",
                                        "gamepad_emulation_enabled": emulacao_desejada})()


@pytest.fixture()
def sem_efeitos(monkeypatch: pytest.MonkeyPatch) -> dict[str, Any]:
    """Neutraliza o start/stop reais; registra o que foi chamado. O uhid nasce
    DISPONÍVEL — cada teste de indisponibilidade sobrescreve."""
    chamadas: dict[str, Any] = {"stop": 0, "start": []}

    def _stop(_daemon: Any, **kwargs: Any) -> None:
        chamadas["stop"] += 1
        chamadas["stop_kwargs"] = kwargs

    def _start(_daemon: Any, flavor: str | None = None) -> bool:
        chamadas["start"].append(flavor)
        return True

    monkeypatch.setattr(gp, "stop_gamepad_emulation", _stop)
    monkeypatch.setattr(gp, "start_gamepad_emulation", _start)
    monkeypatch.setattr(uhid_gamepad, "uhid_available", lambda: True)
    return chamadas


class TestPromocao:
    def test_promove_o_vpad_degradado(self, sem_efeitos: dict[str, Any]) -> None:
        """Vpad uinput + máscara DualSense + uhid disponível = recria em uhid."""
        daemon = _FakeDaemon(_FakeUinputPad())

        assert gp.upgrade_primary_vpad_to_uhid(daemon) is True
        assert sem_efeitos["start"] == ["dualsense"]
        # Não persiste (a preferência não mudou) nem solta o grab (o controle
        # físico voltaria para o jogo no meio da troca).
        assert sem_efeitos["stop_kwargs"] == {"persist": False, "release_grab": False}

    def test_uhid_indisponivel_nao_derruba_o_vpad_que_funciona(
        self, monkeypatch: pytest.MonkeyPatch, sem_efeitos: dict[str, Any]
    ) -> None:
        """Ressalva do VPAD-01: sem o precheck, cada conexão do controle (BT
        reconecta MUITO nesta máquina) destruiria e recriaria o vpad uinput em
        loop — input drop no meio do jogo, sem nunca conseguir o uhid."""
        monkeypatch.setattr(uhid_gamepad, "uhid_available", lambda: False)
        daemon = _FakeDaemon(_FakeUinputPad())

        assert gp.upgrade_primary_vpad_to_uhid(daemon) is False
        assert sem_efeitos["stop"] == 0

    def test_backend_fake_nao_promove(self, sem_efeitos: dict[str, Any]) -> None:
        """VPAD-08: o daemon FAKE não registra um DualSense Edge real no kernel."""
        daemon = _FakeDaemon(_FakeUinputPad(), backend_real=False)

        assert gp.upgrade_primary_vpad_to_uhid(daemon) is False
        assert sem_efeitos["stop"] == 0

    def test_mascara_xbox_fica_no_uinput(self, sem_efeitos: dict[str, Any]) -> None:
        """O hid_playstation não faz bind em VID/PID da Microsoft — por design."""
        pad = _FakeUinputPad()
        pad.flavor = "xbox"
        daemon = _FakeDaemon(pad)

        assert gp.upgrade_primary_vpad_to_uhid(daemon) is False
        assert sem_efeitos["stop"] == 0

    def test_emulacao_desligada_por_escolha_nao_mexe(
        self, sem_efeitos: dict[str, Any]
    ) -> None:
        """Sem device E sem desejo na config = usuária desligou; nada a reviver."""
        daemon = _FakeDaemon(None, emulacao_desejada=False)

        assert gp.upgrade_primary_vpad_to_uhid(daemon) is False
        assert sem_efeitos["stop"] == 0
        assert sem_efeitos["start"] == []

    def test_vpad_que_ja_e_uhid_nao_e_recriado(
        self, sem_efeitos: dict[str, Any]
    ) -> None:
        """Idempotente: com VPAD-03 o vpad já nasce uhid — recriar no replug
        faria o jogo perder o device à toa. É o caso comum agora."""
        from hefesto_dualsense4unix.integrations.uhid_gamepad import UhidDualSense

        daemon = _FakeDaemon(UhidDualSense(player=1, blueprint=None))

        assert gp.upgrade_primary_vpad_to_uhid(daemon) is False
        assert sem_efeitos["stop"] == 0

    def test_cooldown_compartilhado_suprime_a_segunda_tentativa(
        self, sem_efeitos: dict[str, Any]
    ) -> None:
        """Ressalva do VPAD-01: o uhid que aceita o CREATE2 mas nunca faz bind
        passa pelo precheck `uhid_available()` — a 1ª tentativa recria o vpad
        (e volta ao uinput quando o bind falha); a borda seguinte dentro do
        cooldown NÃO pode derrubar o device que funciona outra vez."""
        daemon = _FakeDaemon(_FakeUinputPad())

        assert gp.upgrade_primary_vpad_to_uhid(daemon) is True
        # O bind falhou de novo: a factory devolveu outro uinput.
        daemon._gamepad_device = _FakeUinputPad()

        assert gp.upgrade_primary_vpad_to_uhid(daemon) is False
        assert sem_efeitos["stop"] == 1  # só a 1ª tentativa mexeu no device

    def test_cooldown_expirado_permite_nova_tentativa(
        self, sem_efeitos: dict[str, Any]
    ) -> None:
        """O cooldown é janela, não veto permanente: passada a janela, a
        próxima borda de conexão volta a tentar a promoção."""
        daemon = _FakeDaemon(_FakeUinputPad())
        daemon._last_rebackend_ts = time.monotonic() - (gp.REBACKEND_COOLDOWN_SEC + 1.0)

        assert gp.upgrade_primary_vpad_to_uhid(daemon) is True
        assert sem_efeitos["stop"] == 1


class TestReviveFalhaTotal:
    """VPAD-09: `_gamepad_device is None` com emulação desejada = o start do
    boot falhou INTEIRO (nem uhid nem uinput — ex.: a ACL uaccess chegou depois
    do daemon no login). A borda de conexão revive pela factory completa."""

    def test_revive_quando_emulacao_desejada_e_sem_device(
        self, sem_efeitos: dict[str, Any]
    ) -> None:
        daemon = _FakeDaemon(None)

        assert gp.upgrade_primary_vpad_to_uhid(daemon) is True
        # Factory completa com o flavor da config (start sem flavor explícito);
        # não há device para parar.
        assert sem_efeitos["start"] == [None]
        assert sem_efeitos["stop"] == 0

    def test_revive_nao_exige_uhid_disponivel(
        self, monkeypatch: pytest.MonkeyPatch, sem_efeitos: dict[str, Any]
    ) -> None:
        """Sem device funcionando não há o que proteger: se só o uinput voltou
        (uhid segue sem ACL), um vpad uinput é melhor que nenhum."""
        monkeypatch.setattr(uhid_gamepad, "uhid_available", lambda: False)
        daemon = _FakeDaemon(None)

        assert gp.upgrade_primary_vpad_to_uhid(daemon) is True
        assert sem_efeitos["start"] == [None]

    def test_revive_respeita_o_cooldown(self, sem_efeitos: dict[str, Any]) -> None:
        """Reconexão BT em rajada não pode virar spam de start falhando."""
        daemon = _FakeDaemon(None)

        assert gp.upgrade_primary_vpad_to_uhid(daemon) is True
        daemon._gamepad_device = None  # o start seguiu falhando

        assert gp.upgrade_primary_vpad_to_uhid(daemon) is False
        assert sem_efeitos["start"] == [None]  # só a 1ª borda tentou

    def test_backend_fake_nao_revive(self, sem_efeitos: dict[str, Any]) -> None:
        """VPAD-08 vale também para o revive: o smoke não planta device real."""
        daemon = _FakeDaemon(None, backend_real=False)

        assert gp.upgrade_primary_vpad_to_uhid(daemon) is False
        assert sem_efeitos["start"] == []


def test_o_lifecycle_promove_quando_o_controle_conecta() -> None:
    """O gancho existe no ponto certo — é a borda de recuperação da degradação."""
    from pathlib import Path

    from hefesto_dualsense4unix.daemon import lifecycle

    fonte = Path(lifecycle.__file__).read_text(encoding="utf-8")
    idx_connect = fonte.index("controller_connected")
    trecho = fonte[idx_connect:idx_connect + 700]
    assert "upgrade_primary_vpad_to_uhid" in trecho, (
        "a promoção saiu do caminho do controller_connected — o vpad degradado "
        "para uinput nunca mais volta ao uhid sem reiniciar o daemon"
    )
