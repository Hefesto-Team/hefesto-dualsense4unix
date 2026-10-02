"""O opt-out de co-op das versões antigas não pode sobreviver ao upgrade (LEIGO-01)."""
from __future__ import annotations

from pathlib import Path

import pytest

from hefesto_dualsense4unix.utils import session


@pytest.fixture()
def config_isolado(monkeypatch: pytest.MonkeyPatch, tmp_path: Path) -> Path:
    monkeypatch.setattr(session, "config_dir", lambda ensure=False: tmp_path)
    return tmp_path


class TestMigracaoDoOptOut:
    def test_flag_antigo_e_apagado_e_o_coop_volta(self, config_isolado: Path) -> None:
        """O cenário de quem atualiza: desmarcou o checkbox um dia, agora não tem"""
        (config_isolado / "coop_disabled.flag").write_text("1\n")

        assert session.migrate_coop_optout() is True

        assert not (config_isolado / "coop_disabled.flag").exists()

    def test_sem_flag_nao_faz_nada(self, config_isolado: Path) -> None:
        assert session.migrate_coop_optout() is False

    def test_e_idempotente(self, config_isolado: Path) -> None:
        (config_isolado / "coop_disabled.flag").write_text("1\n")
        assert session.migrate_coop_optout() is True

        assert session.migrate_coop_optout() is False

    def test_desligar_depois_da_migracao_nao_cola_mais(
        self, config_isolado: Path
    ) -> None:
        """NOTA DATADA (06/08/2026) — lápide de"""
        session.migrate_coop_optout()

        session.save_coop_enabled(False)

        assert not (config_isolado / "coop_disabled.flag").exists(), (
            "o escritor ressuscitou o opt-out — o co-op volta a poder morrer no disco"
        )
        assert session.migrate_coop_optout() is False

    def test_falha_de_disco_nao_derruba_o_boot(
        self, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        def _boom(ensure: bool = False) -> Path:
            raise OSError("disco cheio")

        monkeypatch.setattr(session, "config_dir", _boom)

        assert session.migrate_coop_optout() is False


def test_o_daemon_migra_no_boot_e_nao_le_mais_a_preferencia() -> None:
    """NOTA DATADA (06/08/2026): a medida antiga era a ORDEM (migrar antes de"""
    import ast

    from hefesto_dualsense4unix.daemon import lifecycle

    fonte = Path(lifecycle.__file__).read_text(encoding="utf-8")
    assert "migrate_coop_optout()" in fonte, (
        "o daemon não migra o opt-out — o flag órfão fica no disco de quem atualiza"
    )
    chamadas = {
        no.func.id
        for no in ast.walk(ast.parse(fonte))
        if isinstance(no, ast.Call) and isinstance(no.func, ast.Name)
    }
    assert "load_coop_enabled" not in chamadas, (
        "o boot voltou a ler o opt-out do disco — o piso do co-op tem UM dono, "
        "o default do DaemonConfig (COOP-SEM-INTERRUPTOR-01)"
    )


def test_o_piso_do_coop_nasce_ligado_no_dataclass() -> None:
    """O aceite da entrega 1, e ele é sobre o DATACLASS de propósito."""
    from hefesto_dualsense4unix.daemon.lifecycle import DaemonConfig

    assert DaemonConfig().coop_enabled is True
