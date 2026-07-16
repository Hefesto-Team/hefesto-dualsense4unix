"""DEDUP-06 — guard anti-veneno: dedup quebrada nunca mais é silenciosa.

O sprint doc exige o pacote "se DEDUP-04 entra, 06 entra junto": `dedup_ok`
agregado POR JOGADOR no `state_full` (um jogador do co-op degradado em uinput
com o IGNORE congelado é AQUELE jogador com zero controle — um `dedup_ok`
só-do-P1 mentiria), motivo legível, aviso BT+Nativo (achado novo da revisão:
o SDL pode não enxergar o físico BT nem sem launch option) e o check do
doctor via IPC. Aqui fixamos a função agregadora, a fiação no IPC/doctor e o
handler `launch_env.refresh` (gatilho "o conjunto de perfis mudou" — a GUI
salva perfil direto no disco e o daemon precisa rematerializar a antecipação
por appid).
"""
from __future__ import annotations

import asyncio
from pathlib import Path
from types import SimpleNamespace
from typing import Any

from hefesto_dualsense4unix.daemon.subsystems.gamepad import dedup_status


def _daemon(
    *,
    enabled: bool = True,
    native: bool = False,
    flavor: str = "dualsense",
    backend: str | None = "uhid",
    fallback_motivo: str | None = None,
    coop: tuple[tuple[int, str | None], ...] = (),
) -> SimpleNamespace:
    """Daemon dublado: `coop` é ((player_index, backend|None), ...)."""
    device = None
    if backend is not None:
        device = SimpleNamespace(
            flavor=flavor, backend=backend, fallback_motivo=fallback_motivo
        )
    players = {
        f"mac{i}": SimpleNamespace(
            player_index=idx,
            vpad=SimpleNamespace(backend=b) if b is not None else None,
        )
        for i, (idx, b) in enumerate(coop)
    }
    return SimpleNamespace(
        config=SimpleNamespace(
            gamepad_emulation_enabled=enabled, gamepad_flavor=flavor
        ),
        is_native_mode=lambda: native,
        _gamepad_device=device,
        _coop_manager=SimpleNamespace(_players=players) if players else None,
    )


class TestDedupStatus:
    def test_todos_uhid_e_ok(self) -> None:
        ok, motivos = dedup_status(_daemon(coop=((2, "uhid"), (3, "uhid"))))
        assert ok is True
        assert motivos == []

    def test_jogador_do_coop_degradado_quebra_com_motivo(self) -> None:
        """O critério de aceite do doc: P1 uhid + P2 uinput → dedup_ok False
        com motivo `jogador_2_uinput`."""
        ok, motivos = dedup_status(_daemon(coop=((2, "uinput"),)))
        assert ok is False
        assert motivos == ["jogador_2_uinput"]

    def test_primario_degradado_usa_o_motivo_da_factory(self) -> None:
        ok, motivos = dedup_status(
            _daemon(backend="uinput", fallback_motivo="uhid_indisponivel")
        )
        assert ok is False
        assert motivos == ["uhid_indisponivel"]

    def test_primario_degradado_sem_motivo_cai_em_sem_uhid(self) -> None:
        ok, motivos = dedup_status(_daemon(backend="uinput"))
        assert (ok, motivos) == (False, ["sem_uhid"])

    def test_emulacao_ligada_sem_vpad_nenhum_e_vpad_ausente(self) -> None:
        """Start falhou de vez (uhid E uinput inacessíveis): daemon vivo sem
        vpad — o estado exato do achado HIGH do default.env rançoso."""
        ok, motivos = dedup_status(_daemon(backend=None))
        assert (ok, motivos) == (False, ["vpad_ausente"])

    def test_mascara_xbox_e_ok_por_design(self) -> None:
        """O vpad Xbox é uinput 045e por design (invariante VPAD-06) — o
        IGNORE cirúrgico do físico Sony nunca o esconde."""
        ok, motivos = dedup_status(_daemon(flavor="xbox", backend="uinput"))
        assert (ok, motivos) == (True, [])

    def test_emulacao_desligada_e_modo_nativo_nao_alarmam(self) -> None:
        assert dedup_status(_daemon(enabled=False, backend=None)) == (True, [])
        assert dedup_status(_daemon(native=True, backend=None)) == (True, [])

    def test_jogador_com_vpad_ainda_subindo_nao_alarma(self) -> None:
        """vpad None no player = spawn em andamento (transitório real)."""
        ok, motivos = dedup_status(_daemon(coop=((2, None),)))
        assert (ok, motivos) == (True, [])

    def test_varios_motivos_agregam(self) -> None:
        ok, motivos = dedup_status(
            _daemon(backend="uinput", coop=((2, "uinput"), (3, "uhid")))
        )
        assert ok is False
        assert motivos == ["sem_uhid", "jogador_2_uinput"]


class TestFiacaoNoStateFull:
    """O state_full expõe o guard — fonte no ipc_handlers (padrão do repo
    para contratos de fiação; o handler completo exige um daemon inteiro)."""

    def test_state_full_publica_dedup_ok_e_motivo(self) -> None:
        from hefesto_dualsense4unix.daemon import ipc_handlers

        fonte = Path(ipc_handlers.__file__).read_text(encoding="utf-8")
        assert 'result["gamepad_emulation"]["dedup_ok"] = dedup_ok' in fonte
        assert '"dedup_motivo"' in fonte

    def test_state_full_publica_native_bt_fragil(self) -> None:
        from hefesto_dualsense4unix.daemon import ipc_handlers

        fonte = Path(ipc_handlers.__file__).read_text(encoding="utf-8")
        assert 'result["native_bt_fragil"]' in fonte

    def test_doctor_consulta_o_guard_via_ipc(self) -> None:
        root = Path(__file__).resolve().parents[2]
        doctor = (root / "scripts/doctor.sh").read_text(encoding="utf-8")
        assert "check_dedup_ipc" in doctor
        assert "daemon.state_full" in doctor
        assert "native_bt_fragil" in doctor


class TestLaunchEnvRefreshHandler:
    """IPC `launch_env.refresh`: a GUI avisa que o conjunto de perfis mudou."""

    def test_rematerializa_quando_ha_daemon(
        self, monkeypatch: Any, tmp_path: Path
    ) -> None:
        from hefesto_dualsense4unix.daemon import launch_env
        from hefesto_dualsense4unix.daemon.ipc_server import IpcServer

        chamadas: list[Any] = []
        monkeypatch.setattr(
            launch_env, "materialize_launch_env", lambda d: chamadas.append(d)
        )
        host = SimpleNamespace(daemon=SimpleNamespace())
        out = asyncio.run(IpcServer._handle_launch_env_refresh(host, {}))
        assert out == {"status": "ok"}
        assert chamadas == [host.daemon]

    def test_sem_daemon_responde_failed_sem_estourar(self) -> None:
        from hefesto_dualsense4unix.daemon.ipc_server import IpcServer

        host = SimpleNamespace(daemon=None)
        out = asyncio.run(IpcServer._handle_launch_env_refresh(host, {}))
        assert out == {"status": "failed"}

    def test_metodo_registrado_no_dispatcher(self) -> None:
        from hefesto_dualsense4unix.daemon import ipc_server

        fonte = Path(ipc_server.__file__).read_text(encoding="utf-8")
        assert '"launch_env.refresh": self._handle_launch_env_refresh' in fonte

    def test_gui_avisa_apos_save_delete_import_restore(self) -> None:
        """save/delete/import/restore de perfil notificam o daemon — sem isso
        o steam_app_<appid>.env fica rançoso na janela exata que ele existia
        para fechar (primeira sessão do jogo com perfil novo)."""
        from hefesto_dualsense4unix.app.actions import (
            footer_actions,
            profiles_actions,
        )

        footer = Path(footer_actions.__file__).read_text(encoding="utf-8")
        perfis = Path(profiles_actions.__file__).read_text(encoding="utf-8")
        assert footer.count("self._notify_launch_env_refresh()") >= 3
        assert perfis.count("self._notify_launch_env_refresh()") >= 2
        for fonte in (footer, perfis):
            assert '"launch_env.refresh"' in fonte or (
                "launch_env.refresh" in fonte
            )
