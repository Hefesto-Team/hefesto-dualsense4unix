"""O opt-out de co-op das versões antigas não pode sobreviver ao upgrade (LEIGO-01).

O checkbox "Cada controle é um jogador" saiu da tela — cada controle é um jogador,
sempre. Mas quem o desmarcou numa versão **já lançada** tem o `coop_disabled.flag`
gravado em disco, e o `load_coop_enabled()` o respeita: o co-op subiria desligado
**sem nenhum caminho de volta na interface**.

Apagar o flag é a leitura certa da decisão de produto ("ninguém conecta dois
controles no PC esperando que os dois controlem a mesma pessoa") e espelha o que o
`save_coop_enabled` já fazia com o flag legado `coop_enabled.flag`.
"""
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
        """O cenário de quem atualiza: desmarcou o checkbox um dia, agora não tem
        mais onde religar."""
        (config_isolado / "coop_disabled.flag").write_text("1\n")
        assert session.load_coop_enabled() is False

        assert session.migrate_coop_optout() is True

        assert session.load_coop_enabled() is True
        assert not (config_isolado / "coop_disabled.flag").exists()

    def test_sem_flag_nao_faz_nada(self, config_isolado: Path) -> None:
        assert session.migrate_coop_optout() is False
        assert session.load_coop_enabled() is True

    def test_e_idempotente(self, config_isolado: Path) -> None:
        (config_isolado / "coop_disabled.flag").write_text("1\n")
        assert session.migrate_coop_optout() is True

        assert session.migrate_coop_optout() is False

    def test_desligar_depois_da_migracao_e_respeitado(
        self, config_isolado: Path
    ) -> None:
        """A migração é one-shot: quem desligar pela CLI DEPOIS não é atropelado.

        Sem o marker, todo boot apagaria o flag e a escolha nunca colaria.
        """
        session.migrate_coop_optout()
        session.save_coop_enabled(False)  # ex.: `hefesto-dualsense4unix coop off`

        assert session.migrate_coop_optout() is False
        assert session.load_coop_enabled() is False, (
            "a migração atropelou uma escolha feita DEPOIS dela"
        )

    def test_falha_de_disco_nao_derruba_o_boot(
        self, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        def _boom(ensure: bool = False) -> Path:
            raise OSError("disco cheio")

        monkeypatch.setattr(session, "config_dir", _boom)

        assert session.migrate_coop_optout() is False  # best-effort, sem exceção


def test_o_daemon_migra_antes_de_ler_a_preferencia() -> None:
    """A ordem importa: migrar DEPOIS da leitura não adiantaria nada no boot."""
    from hefesto_dualsense4unix.daemon import lifecycle

    fonte = Path(lifecycle.__file__).read_text(encoding="utf-8")
    assert "migrate_coop_optout()" in fonte, (
        "o daemon não migra o opt-out — quem atualiza fica sem co-op e sem UI "
        "para religar"
    )
    assert fonte.index("migrate_coop_optout()") < fonte.index("if load_coop_enabled()")
