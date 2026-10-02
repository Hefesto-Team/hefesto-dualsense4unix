"""NUM-01 — quem está na mesa é 1..N (sprint 2026-07-25)."""
from __future__ import annotations

import json
from pathlib import Path
from types import SimpleNamespace

import pytest

from hefesto_dualsense4unix.daemon.subsystems import external_identity as ei_mod
from hefesto_dualsense4unix.daemon.subsystems import identity as id_mod
from hefesto_dualsense4unix.daemon.subsystems.external_identity import (
    ExternalIdentityRegistry,
    ExternalLedSync,
)
from hefesto_dualsense4unix.daemon.subsystems.identity import (
    ControllerIdentityRegistry,
)

#: Os dois DualSense da casa (MACs forjados — faixa aa:bb:cc).
UNIQ_A = "aabbcc000001"
UNIQ_B = "aabbcc000002"
MAC_EXTERNO = "aabbcc0000fe"

BOOT = "boot-teste-num01"


@pytest.fixture
def config_isolado(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> Path:
    """``config_dir`` em tmp + âncora fixa nos dois registros (mesmo arquivo)."""
    from hefesto_dualsense4unix.utils import xdg_paths

    def fake_config_dir(ensure: bool = False) -> Path:
        if ensure:
            tmp_path.mkdir(parents=True, exist_ok=True)
        return tmp_path

    monkeypatch.setattr(xdg_paths, "config_dir", fake_config_dir)
    monkeypatch.setattr(id_mod, "_read_boot_id", lambda: BOOT)
    monkeypatch.setattr(ei_mod, "_read_boot_id", lambda: BOOT)
    return tmp_path


def _arquivo(tmp: Path) -> dict[str, object]:
    return json.loads((tmp / "controllers.json").read_text(encoding="utf-8"))


def _fila(tmp: Path, kind: str = id_mod.KIND_DUALSENSE) -> dict[str, int]:
    """Endereço → lugar na fila, lidos do campo ``order`` (schema 3)."""
    entradas = _arquivo(tmp)[id_mod.ORDER_FIELD]
    assert isinstance(entradas, list)
    return {
        str(e["addr"]): int(e["rank"])
        for e in entradas
        if isinstance(e, dict) and e.get("kind") == kind
    }


class _Relogio:
    """Relógio monotônico de mentira — o prazo do lugar guardado sem `sleep`."""

    def __init__(self) -> None:
        self.agora = 1000.0

    def __call__(self) -> float:
        return self.agora


def _registro() -> ControllerIdentityRegistry:
    """O registro dos DualSense, com relógio de mentira."""
    return ControllerIdentityRegistry(clock=_Relogio())


def _registro_externo() -> ExternalIdentityRegistry:
    """O registro dos externos, com relógio de mentira."""
    return ExternalIdentityRegistry(clock=_Relogio())


def _passar_o_prazo(*registros: object) -> None:
    """O lugar de quem saiu deixa de estar guardado — O-ASSENTO-GUARDADO-NAO-ANDA-01."""
    for registro in registros:
        relogio = getattr(registro, "_clock", None)
        assert isinstance(relogio, _Relogio), "registro sem relógio de mentira"
        relogio.agora += id_mod.prazo_do_lugar_guardado() + 1.0


def _mesa(reg: ControllerIdentityRegistry, *uniqs: str) -> dict[str, int | None]:
    """Números EXIBIDOS depois de reconciliar a mesa com ``uniqs``."""
    antes = reg.snapshot_connected()
    reg.sync_connected(list(uniqs))
    if antes - reg.snapshot_connected():
        _passar_o_prazo(reg)
    return {uniq: reg.slot_for(uniq, assign=False) for uniq in uniqs}


class TestOsSeisCenariosDaSprint:
    """A sequência de validação da sprint, na ordem, num registro só."""

    def test_1_o_controle_sozinho_na_mesa_e_o_jogador_1(
        self, config_isolado: Path
    ) -> None:
        reg = _registro()
        assert _mesa(reg, UNIQ_B) == {UNIQ_B: 1}

    def test_2_ligar_o_outro_nao_faz_ninguem_piscar(
        self, config_isolado: Path
    ) -> None:
        """B já estava na mesa; A chega e entra ATRÁS — B continua 1."""
        reg = _registro()
        _mesa(reg, UNIQ_B)
        assert _mesa(reg, UNIQ_B, UNIQ_A) == {UNIQ_B: 1, UNIQ_A: 2}

    def test_3_desligar_o_primeiro_promove_quem_ficou(
        self, config_isolado: Path
    ) -> None:
        """A lacuna se fecha sozinha: é a "compactação automática" da sprint,"""
        reg = _registro()
        _mesa(reg, UNIQ_B, UNIQ_A)
        assert _mesa(reg, UNIQ_A) == {UNIQ_A: 1}

    def test_4_religar_devolve_a_cada_um_a_sua_colocacao(
        self, config_isolado: Path
    ) -> None:
        """A ordem de preferência não mudou em nenhum dos passos acima: com"""
        reg = _registro()
        _mesa(reg, UNIQ_B, UNIQ_A)
        _mesa(reg, UNIQ_A)
        assert _mesa(reg, UNIQ_A, UNIQ_B) == {UNIQ_A: 2, UNIQ_B: 1}
        assert reg.snapshot() == {UNIQ_B: 1, UNIQ_A: 2}, "a fila nunca mudou"

    def test_5_restart_do_daemon_mantem_a_ordem(self, config_isolado: Path) -> None:
        """Restart = instância nova + ``load()``. R-23 continua de pé."""
        reg = _registro()
        _mesa(reg, UNIQ_B, UNIQ_A)

        reiniciado = _registro()
        reiniciado.load()
        assert _mesa(reiniciado, UNIQ_A, UNIQ_B) == {UNIQ_A: 2, UNIQ_B: 1}
        assert _mesa(reiniciado, UNIQ_A) == {UNIQ_A: 1}

    def test_6_reboot_da_maquina_mantem_a_ordem(
        self, config_isolado: Path, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        """Âncora diferente = outro boot. Ela ANOTA, nunca decide (R-23)."""
        reg = _registro()
        _mesa(reg, UNIQ_B, UNIQ_A)

        monkeypatch.setattr(id_mod, "_read_boot_id", lambda: "outro-boot")
        depois_do_reboot = _registro()
        depois_do_reboot.load()
        assert depois_do_reboot.snapshot() == {UNIQ_B: 1, UNIQ_A: 2}
        assert _mesa(depois_do_reboot, UNIQ_A, UNIQ_B) == {UNIQ_A: 2, UNIQ_B: 1}


class TestOsDoisRequisitosJuntos:
    """A tabela da sprint: fila ``[A, B]`` persistida, três estados de mesa."""

    def _com_fila_ab(self, tmp: Path) -> ControllerIdentityRegistry:
        semente = _registro()
        semente.sync_connected([UNIQ_A, UNIQ_B])
        assert _fila(tmp) == {UNIQ_A: 1, UNIQ_B: 2}
        reg = _registro()
        reg.load()
        return reg

    def test_os_dois_ligados_cada_um_mantem_o_seu(
        self, config_isolado: Path
    ) -> None:
        reg = self._com_fila_ab(config_isolado)
        assert _mesa(reg, UNIQ_A, UNIQ_B) == {UNIQ_A: 1, UNIQ_B: 2}

    def test_so_o_b_ligado_ele_e_o_jogador_1(self, config_isolado: Path) -> None:
        """O caso EXATO do relato — com a fila dizendo que A vem antes."""
        reg = self._com_fila_ab(config_isolado)
        assert _mesa(reg, UNIQ_B) == {UNIQ_B: 1}
        assert reg.snapshot() == {UNIQ_A: 1, UNIQ_B: 2}, "sem mexer na fila"

    def test_os_dois_de_volta_voltam_ao_lugar(self, config_isolado: Path) -> None:
        reg = self._com_fila_ab(config_isolado)
        _mesa(reg, UNIQ_B)
        assert _mesa(reg, UNIQ_A, UNIQ_B) == {UNIQ_A: 1, UNIQ_B: 2}


class TestNuncaJogador2SemJogador1:
    """O critério que resume a sprint, inclusive na mesa MISTA.

    A contagem é da mesa inteira (DualSense + externos), então a prova tem de
    passar pelo registro dos externos também — é ele que o co-op e o LED de
    número dos aparelhos de terceiros consultam.
    """

    @staticmethod
    def _numeros(
        ds: ControllerIdentityRegistry,
        ext: ExternalIdentityRegistry,
        presentes_ds: list[str],
        presentes_ext: list[str],
    ) -> list[int]:
        saiu = ds.snapshot_connected() - set(presentes_ds)
        saiu |= ext.snapshot_connected() - set(presentes_ext)
        ds.sync_connected(presentes_ds)
        ext.sync_connected(presentes_ext)
        if saiu:
            _passar_o_prazo(ds, ext)
        piso = max(ds.snapshot().values(), default=0)
        numeros = [ds.slot_for(u, assign=False) for u in presentes_ds]
        numeros += [ext.slot_for(u, reserve=piso) for u in presentes_ext]
        return sorted(n for n in numeros if n is not None)

    def test_mesa_mista_ocupa_1_a_n_em_qualquer_combinacao(
        self, config_isolado: Path
    ) -> None:
        """Três controles registrados; toda combinação de presença exibe
        exatamente 1..N, sem buraco e sem repetição.

        Falha-sem: com o registro antigo, desligar o DualSense do lugar 1
        deixava a mesa exibindo 2 e 3 — "não existe Controle 1", medido ao
        vivo no arquivo dela.
        """
        ds = _registro()
        ext = _registro_externo()
        ds.set_external_reserve_provider(lambda: set(ext.snapshot().values()))
        ExternalLedSync(SimpleNamespace(identity_registry=ds), ext)

        # Estado inicial: os dois DualSense e o externo, todos na mesa.
        assert self._numeros(ds, ext, [UNIQ_A, UNIQ_B], [MAC_EXTERNO]) == [1, 2, 3]

        combinacoes = [
            ([UNIQ_A, UNIQ_B], [MAC_EXTERNO]),
            ([UNIQ_A], [MAC_EXTERNO]),
            ([UNIQ_B], [MAC_EXTERNO]),
            ([UNIQ_A, UNIQ_B], []),
            ([UNIQ_B], []),
            ([], [MAC_EXTERNO]),
            ([UNIQ_A, UNIQ_B], [MAC_EXTERNO]),
        ]
        for presentes_ds, presentes_ext in combinacoes:
            numeros = self._numeros(ds, ext, presentes_ds, presentes_ext)
            esperado = list(range(1, len(presentes_ds) + len(presentes_ext) + 1))
            assert numeros == esperado, (
                f"mesa {presentes_ds}+{presentes_ext} exibiu {numeros}"
            )

    def test_externo_sozinho_na_mesa_e_o_jogador_1(
        self, config_isolado: Path
    ) -> None:
        """Vale para o Pro Nintendo/8BitDo também: ninguém aceita ser o
        jogador 2 de si mesmo, nem quem não é DualSense."""
        ds = _registro()
        ext = _registro_externo()
        ExternalLedSync(SimpleNamespace(identity_registry=ds), ext)
        ds.sync_connected([UNIQ_A, UNIQ_B])
        piso = max(ds.snapshot().values())
        assert ext.slot_for(MAC_EXTERNO, reserve=piso) == 3

        ds.sync_connected([])  # os dois DualSense saíram
        ext.sync_connected([MAC_EXTERNO])
        _passar_o_prazo(ds, ext)
        assert ext.peek(MAC_EXTERNO) == 1
        assert ext.snapshot() == {MAC_EXTERNO: 3}, "o lugar na fila é o mesmo"


class TestRenumerarAgoraNaoEstragaOAusente:
    """Entrega 2 da sprint: o gesto de conserto perdeu o efeito colateral."""

    def test_o_ausente_volta_no_numero_certo_depois_do_renumerar(
        self, config_isolado: Path
    ) -> None:
        from hefesto_dualsense4unix.daemon.ipc_handlers import IpcHandlersMixin

        ds = _registro()
        ds.sync_connected([UNIQ_A, UNIQ_B])
        ds.sync_connected([UNIQ_B])

        renumerados = IpcHandlersMixin._renumber_locked(ds, None)
        assert renumerados == {UNIQ_B: 1, UNIQ_A: 2}
        assert ds.snapshot() == {UNIQ_B: 1, UNIQ_A: 2}
        assert ds.slot_for(UNIQ_B, assign=False) == 1

        assert _mesa(ds, UNIQ_A) == {UNIQ_A: 1}
        assert _mesa(ds, UNIQ_A, UNIQ_B) == {UNIQ_A: 2, UNIQ_B: 1}

    def test_renumerar_nao_dropa_a_reserva_do_ausente(
        self, config_isolado: Path
    ) -> None:
        """D2 continua de pé: o ausente perde a fila, nunca a entrada."""
        from hefesto_dualsense4unix.daemon.ipc_handlers import IpcHandlersMixin

        ds = _registro()
        ds.sync_connected([UNIQ_A, UNIQ_B])
        ds.sync_connected([UNIQ_B])
        IpcHandlersMixin._renumber_locked(ds, None)
        assert UNIQ_A in ds.snapshot()


class TestMigracaoDoArquivoReal:
    """O bump de esquema é o que devolve a casa à numeração certa."""

    def test_arquivo_schema_2_e_descartado_e_a_casa_renumera_na_chegada(
        self, config_isolado: Path
    ) -> None:
        (config_isolado / "controllers.json").write_text(
            json.dumps(
                {
                    "version": 2,
                    "boot_id": BOOT,
                    "slots": {UNIQ_A: 1, UNIQ_B: 2},
                    "externals": {MAC_EXTERNO: 3, "aabbcc0000ff": 4},
                }
            ),
            encoding="utf-8",
        )
        ds = _registro()
        ds.load()
        ext = _registro_externo()
        ext.load()
        assert ds.snapshot() == {} and ext.snapshot() == {}

        assert _mesa(ds, UNIQ_B) == {UNIQ_B: 1}
        assert _arquivo(config_isolado)["version"] == (
            id_mod.CONTROLLERS_SCHEMA_VERSION
        )
        assert _fila(config_isolado) == {UNIQ_B: 1}
        assert _fila(config_isolado, id_mod.KIND_EXTERNAL) == {}

    def test_a_casa_sem_arquivo_nenhum_nasce_no_1(
        self, config_isolado: Path
    ) -> None:
        ds = _registro()
        ds.load()
        assert _mesa(ds, UNIQ_B) == {UNIQ_B: 1}
