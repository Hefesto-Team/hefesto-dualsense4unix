"""D-TROCA-DE-PERFIL-CEGA — o XWayland morto que prendia o detector."""
from __future__ import annotations

from typing import Any

import pytest

from hefesto_dualsense4unix.integrations import window_detect
from hefesto_dualsense4unix.integrations.window_backends.xlib import XlibBackend

DISPLAY_MORTO = ":9"


def _reader_xlib_com_conexao_provada_morta(
    monkeypatch: pytest.MonkeyPatch, *, wayland_depois: bool
) -> window_detect.WindowReaderDiag:
    """Constrói o leitor no estado exato da máquina dela: xlib, X recusando."""
    monkeypatch.setenv("DISPLAY", DISPLAY_MORTO)
    monkeypatch.delenv("WAYLAND_DISPLAY", raising=False)
    reader = window_detect.build_window_reader()
    assert reader.backend_name == "xlib"
    assert isinstance(reader._backend, XlibBackend)
    reader()
    if wayland_depois:
        monkeypatch.setenv("WAYLAND_DISPLAY", "wayland-0")
    return reader


class TestOResgateSoDisparaComProva:
    """`precisa_de_resgate` responde as três perguntas separadamente."""

    def test_xlib_recem_nascido_nao_precisa_de_resgate(
        self, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        """Sem nenhuma tentativa, `conexao_provada()` é None — e None não é prova."""
        monkeypatch.setenv("DISPLAY", DISPLAY_MORTO)
        monkeypatch.delenv("WAYLAND_DISPLAY", raising=False)
        reader = window_detect.build_window_reader()
        monkeypatch.setenv("WAYLAND_DISPLAY", "wayland-0")

        backend = reader._backend
        assert isinstance(backend, XlibBackend)
        assert backend.conexao_provada() is None
        assert reader.precisa_de_resgate() is False

    def test_xlib_provado_morto_com_wayland_que_apareceu_precisa_de_resgate(
        self, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        """As três condições juntas — e a terceira chegou depois do nascimento."""
        reader = _reader_xlib_com_conexao_provada_morta(monkeypatch, wayland_depois=True)

        backend = reader._backend
        assert isinstance(backend, XlibBackend)
        assert backend.conexao_provada() is False
        assert reader.precisa_de_resgate() is True

    def test_x11_puro_nao_tem_para_onde_ser_resgatado(
        self, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        """Sem `WAYLAND_DISPLAY` não há cascata: insistir no xlib é o certo."""
        reader = _reader_xlib_com_conexao_provada_morta(monkeypatch, wayland_depois=False)

        assert reader._backend.conexao_provada() is False  # type: ignore[union-attr]
        assert reader.precisa_de_resgate() is False
        assert reader.maybe_recover() is False
        assert reader.backend_name == "xlib"


class TestEmXWaylandOResgateNaoPrecisaExistir:
    """JANELA-WAYLAND-CEGA-01: a queda virou de LEITURA, e por isso some daqui."""

    def test_a_factory_ja_devolve_o_composto_e_ele_nao_pede_resgate(
        self, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        """MORDIDA: devolver `XlibBackend()` puro no ramo XWayland da factory —"""
        monkeypatch.setenv("DISPLAY", DISPLAY_MORTO)
        monkeypatch.setenv("WAYLAND_DISPLAY", "wayland-0")
        reader = window_detect.build_window_reader()
        assert type(reader._backend).__name__ == "_XlibComCosmicBackend"
        reader()

        assert reader.conexao_provada() is False
        assert reader.precisa_de_resgate() is False

    def test_o_composto_cai_para_o_wayland_quando_o_x_esta_morto(
        self, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        """A saída que o resgate dava, agora sem trocar backend nenhum."""
        from hefesto_dualsense4unix.integrations.window_backends.base import WindowInfo

        monkeypatch.setenv("DISPLAY", DISPLAY_MORTO)
        monkeypatch.setenv("WAYLAND_DISPLAY", "wayland-0")
        composto = window_detect.detect_window_backend()
        composto._wayland = _CascataDeMentira(  # type: ignore[attr-defined]
            WindowInfo(wm_class="com.system76.CosmicTerm", app_id="com.system76.CosmicTerm")
        )

        info = composto.get_active_window_info()
        assert info is not None
        assert info.wm_class == "com.system76.CosmicTerm"
        assert composto.backend_name == "cosmic"


class _CascataDeMentira:
    """Cascata Wayland de mentira: responde sempre a mesma janela."""

    backend_name = "cosmic"
    last_failure_reason: str | None = None

    def __init__(self, info: Any) -> None:
        self._info = info

    def get_active_window_info(self) -> Any:
        return self._info


class TestOResgateTrocaOBackendEmPlace:
    def test_maybe_recover_troca_xlib_morto_pelo_composto(
        self, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        """O conserto em uma linha: o detector deixa de ficar preso no X morto."""
        reader = _reader_xlib_com_conexao_provada_morta(monkeypatch, wayland_depois=True)
        xlib_de_antes = reader._backend

        assert reader.maybe_recover() is True
        assert type(reader._backend).__name__ == "_XlibComCosmicBackend"
        assert reader._backend.xlib is xlib_de_antes  # type: ignore[union-attr]

    def test_o_resgate_nao_se_repete_depois_de_trocado(
        self, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        """Trocado uma vez, `precisa_de_resgate` cala — não fica em laço."""
        reader = _reader_xlib_com_conexao_provada_morta(monkeypatch, wayland_depois=True)
        assert reader.maybe_recover() is True

        assert reader.precisa_de_resgate() is False
        assert reader.maybe_recover() is False

    def test_o_resgate_guarda_o_mesmo_xlib_em_vez_de_criar_outro(
        self, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        """Por que o resgate NÃO chama a factory."""
        reader = _reader_xlib_com_conexao_provada_morta(monkeypatch, wayland_depois=True)
        xlib_de_antes = reader._backend
        assert xlib_de_antes.conexao_provada() is False  # type: ignore[union-attr]

        da_factory = window_detect.detect_window_backend()
        assert type(da_factory).__name__ == "_XlibComCosmicBackend"
        assert da_factory.xlib is not xlib_de_antes  # type: ignore[union-attr]
        assert da_factory.xlib.conexao_provada() is None  # type: ignore[union-attr]


class _FakeStore:
    """Dublê do `StateStore` com a assinatura real dos dois métodos usados."""

    def __init__(self) -> None:
        self.seeds: list[tuple[Any, bool]] = []
        self.reads: list[tuple[Any, Any, Any]] = []

    def set_window_detect_backend(self, name: Any, healthy: bool) -> None:
        self.seeds.append((name, healthy))

    def record_window_detect_read(
        self, name: Any, wm_class: Any, *, reason: Any = None
    ) -> None:
        self.reads.append((name, wm_class, reason))


class TestASaudeNaoVoltaAMentirNoResgate:
    """A metade barata: `window_detect_healthy` para de afirmar sem prova."""

    def test_resgate_para_xlib_morto_nao_semeia_saudavel(
        self, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        """A mordida da correção pela metade."""
        from hefesto_dualsense4unix.daemon.subsystems.autoswitch import (
            _build_diag_window_reader,
        )

        monkeypatch.delenv("DISPLAY", raising=False)
        monkeypatch.delenv("WAYLAND_DISPLAY", raising=False)
        store = _FakeStore()
        read = _build_diag_window_reader(store)  # type: ignore[arg-type]
        assert store.seeds == [("null", False)]

        monkeypatch.setenv("DISPLAY", DISPLAY_MORTO)
        read()

        assert ("xlib", True) not in store.seeds, (
            "healthy=True sem prova de conexão é a mentira da "
            "D-TROCA-DE-PERFIL-CEGA voltando pelo caminho do resgate"
        )
        assert store.seeds[-1] == ("xlib", False)

    def test_o_motivo_da_cegueira_chega_ao_store(
        self, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        """`sem_conexao_x` — o motivo que a aba Sistema pinta em laranja."""
        from hefesto_dualsense4unix.daemon.subsystems.autoswitch import (
            _build_diag_window_reader,
        )
        from hefesto_dualsense4unix.integrations.window_backends.xlib import (
            MOTIVO_SEM_CONEXAO,
        )

        monkeypatch.setenv("DISPLAY", DISPLAY_MORTO)
        monkeypatch.delenv("WAYLAND_DISPLAY", raising=False)
        store = _FakeStore()
        read = _build_diag_window_reader(store)  # type: ignore[arg-type]
        read()

        assert store.seeds[0] == ("xlib", False)
        assert store.reads[-1] == ("xlib", "unknown", MOTIVO_SEM_CONEXAO)
