"""O opt-out de co-op das versões antigas não pode sobreviver ao upgrade (LEIGO-01).

O checkbox "Cada controle é um jogador" saiu da tela — cada controle é um jogador,
sempre. Mas quem o desmarcou numa versão **já lançada** tem o `coop_disabled.flag`
gravado em disco: o co-op subiria desligado **sem nenhum caminho de volta na
interface**.

Apagar o flag é a leitura certa da decisão de produto ("ninguém conecta dois
controles no PC esperando que os dois controlem a mesma pessoa") e espelha o que o
`save_coop_enabled` já fazia com o flag legado `coop_enabled.flag`.

**NOTA DATADA (06/08/2026) — COOP-SEM-INTERRUPTOR-01.** A premissa de metade
deste arquivo CADUCOU. Até aqui `load_coop_enabled()` LIA o flag, e por isso
fazia sentido medir "o disco desligou o co-op" e "quem desligar DEPOIS da
migração é respeitado". O opt-out deixou de existir por decisão dela — *"todos
e tudo no Hefesto tem que tá com o permitir co-op ligado"* —, então o disco
deixou de governar: `load_coop_enabled()` é lápide que devolve `True`, e
`save_coop_enabled` só APAGA. A migração continua tendo trabalho (o arquivo
existe na máquina de quem atualiza, e um arquivo órfão é dívida que confunde a
próxima leitura), e é isso que as medidas abaixo passaram a travar.
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

    def test_desligar_depois_da_migracao_nao_cola_mais(
        self, config_isolado: Path
    ) -> None:
        """NOTA DATADA (06/08/2026) — lápide de
        ``test_desligar_depois_da_migracao_e_respeitado``.

        Aquele teste mediu a coisa certa enquanto desligar era uma escolha: a
        migração é one-shot com marker próprio, e quem desligasse pela CLI
        DEPOIS dela não podia ser atropelado no boot seguinte. Não há mais o que
        respeitar — o `coop off` deixou de desligar e o `save_coop_enabled` virou
        lápide. O que ficou a medir é que o escritor não RESSUSCITA o opt-out:
        um `False` que voltasse a gravar arquivo devolveria, inteiro, o defeito
        que a LEIGO-01 pagou para fechar.
        """
        session.migrate_coop_optout()

        session.save_coop_enabled(False)  # chamador antigo pedindo "desliga"

        assert not (config_isolado / "coop_disabled.flag").exists(), (
            "o escritor ressuscitou o opt-out — o co-op volta a poder morrer no disco"
        )
        assert session.load_coop_enabled() is True
        assert session.migrate_coop_optout() is False  # segue one-shot

    def test_falha_de_disco_nao_derruba_o_boot(
        self, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        def _boom(ensure: bool = False) -> Path:
            raise OSError("disco cheio")

        monkeypatch.setattr(session, "config_dir", _boom)

        assert session.migrate_coop_optout() is False  # best-effort, sem exceção


def test_o_daemon_migra_no_boot_e_nao_le_mais_a_preferencia() -> None:
    """NOTA DATADA (06/08/2026): a medida antiga era a ORDEM (migrar antes de
    ler). Não há mais leitura para vir depois — o piso do co-op tem um dono só,
    o `DaemonConfig.coop_enabled`. Sobra o que continua importando: o daemon
    apaga o flag órfão no boot, e não voltou a deixar o disco decidir.
    """
    import ast

    from hefesto_dualsense4unix.daemon import lifecycle

    fonte = Path(lifecycle.__file__).read_text(encoding="utf-8")
    assert "migrate_coop_optout()" in fonte, (
        "o daemon não migra o opt-out — o flag órfão fica no disco de quem atualiza"
    )
    # AST, não `in fonte`: a lápide CITA a linha que saiu, de propósito, e um
    # grep de texto proibiria explicar a decisão dentro do próprio arquivo.
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
    """O aceite da entrega 1, e ele é sobre o DATACLASS de propósito.

    Armadilha nomeada pela sprint: enquanto o `run()` forçava `True` logo depois
    de ler o disco, um teste de BOOT passava com a cura arrancada — havia um
    sósia da cura. Aqui não há `run()`: é o piso, cru.
    """
    from hefesto_dualsense4unix.daemon.lifecycle import DaemonConfig

    assert DaemonConfig().coop_enabled is True
