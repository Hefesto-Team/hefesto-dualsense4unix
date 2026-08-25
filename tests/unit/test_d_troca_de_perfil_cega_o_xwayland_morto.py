"""D-TROCA-DE-PERFIL-CEGA — o XWayland morto que prendia o detector.

Medido na máquina dela em 23/08/2026 às 22h21: **60 `x11_connect_failed` em
30 minutos** no journal, `err=Can't connect to display :1`, numa sessão
COSMIC/Wayland. A troca de perfil ao abrir o jogo ficou cega a sessão inteira.

O defeito NÃO era o backend `xlib` ser preferido — ele é o único que resolve
`exe_basename` (PROCESSO-CEGO-01), e com o XWayland vivo a preferência está
certa. O defeito era não haver **saída**: `detect_window_backend()` escolhe
`xlib` sempre que `DISPLAY` existe, `maybe_recover()` só resgatava o
`NullBackend`, e a cascata Wayland — que o COSMIC atende por `wlrctl` —
ficava ao lado, nunca tentada.

E havia uma segunda metade, mais barata e mais perigosa: a T-01 da ONDA0-Z7
curou a semeadura de `window_detect_healthy` para exigir PROVA de conexão, e
deixou intacta a **re-semeadura** do resgate (AUTOSWITCH-HEAL-01), 40 linhas
abaixo no mesmo arquivo, que seguia fazendo `healthy=(nome == "xlib")`. Com
isso a aba Sistema podia afirmar saúde sobre um detector cego — que é a
mentira que a decisão de 25/08 mandou matar primeiro.

Os dois consertos estão em
`integrations/window_detect.py` (`precisa_de_resgate` / `maybe_recover`) e em
`daemon/subsystems/autoswitch.py` (`_saude_com_prova`, e o gate do resgate).
"""
from __future__ import annotations

from typing import Any

import pytest

from hefesto_dualsense4unix.integrations import window_detect
from hefesto_dualsense4unix.integrations.window_backends.xlib import XlibBackend

#: DISPLAY que não existe em bancada nenhuma: o connect falha com
#: `[Errno 111] Connection refused`, que é a MESMA classe de falha do
#: `Can't connect to display :1` medido na máquina dela.
DISPLAY_MORTO = ":9"


def _reader_xlib_com_conexao_provada_morta(
    monkeypatch: pytest.MonkeyPatch, *, wayland: bool
) -> window_detect.WindowReaderDiag:
    """Constrói o leitor no estado exato da máquina dela: xlib, X recusando.

    Uma leitura é feita de propósito — é ela que dispara `_ensure_connected()`
    e transforma "ainda não tentei" (`conexao_provada() is None`) em PROVA de
    recusa (`is False`). Sem essa leitura não há prova, e o resgate não deve
    disparar: presunção é o que este arquivo inteiro existe para proibir.
    """
    monkeypatch.setenv("DISPLAY", DISPLAY_MORTO)
    if wayland:
        monkeypatch.setenv("WAYLAND_DISPLAY", "wayland-0")
    else:
        monkeypatch.delenv("WAYLAND_DISPLAY", raising=False)
    reader = window_detect.build_window_reader()
    assert reader.backend_name == "xlib"
    reader()
    return reader


class TestOResgateSoDisparaComProva:
    """`precisa_de_resgate` responde as três perguntas separadamente."""

    def test_xlib_recem_nascido_nao_precisa_de_resgate(
        self, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        """Sem nenhuma tentativa, `conexao_provada()` é None — e None não é prova.

        Este é o caso normal do arranque: o daemon sobe, escolhe `xlib`, e o
        XWayland está perfeitamente vivo. Resgatar aqui trocaria um backend
        bom por um cego ao nome do processo.
        """
        monkeypatch.setenv("DISPLAY", DISPLAY_MORTO)
        monkeypatch.setenv("WAYLAND_DISPLAY", "wayland-0")
        reader = window_detect.build_window_reader()

        backend = reader._backend
        assert isinstance(backend, XlibBackend)
        assert backend.conexao_provada() is None
        assert reader.precisa_de_resgate() is False

    def test_xlib_provado_morto_em_wayland_precisa_de_resgate(
        self, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        """As três condições da máquina dela, juntas."""
        reader = _reader_xlib_com_conexao_provada_morta(monkeypatch, wayland=True)

        backend = reader._backend
        assert isinstance(backend, XlibBackend)
        assert backend.conexao_provada() is False
        assert reader.precisa_de_resgate() is True

    def test_x11_puro_nao_tem_para_onde_ser_resgatado(
        self, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        """Sem `WAYLAND_DISPLAY` não há cascata: insistir no xlib é o certo.

        Numa sessão X11 de verdade, o servidor caído é episódio transitório e
        o backoff do `XlibBackend` já cobre a volta. Trocar para uma cascata
        que não tem compositor Wayland para conversar seria trocar cegueira
        por cegueira, e ainda perder o `exe_basename` quando o X voltasse.
        """
        reader = _reader_xlib_com_conexao_provada_morta(monkeypatch, wayland=False)

        assert reader._backend.conexao_provada() is False  # type: ignore[union-attr]
        assert reader.precisa_de_resgate() is False
        assert reader.maybe_recover() is False
        assert reader.backend_name == "xlib"


class TestOResgateTrocaOBackendEmPlace:
    def test_maybe_recover_troca_xlib_morto_pela_cascata_wayland(
        self, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        """O conserto em uma linha: o detector deixa de ficar preso no X morto.

        Antes de 25/08 este `maybe_recover()` devolvia False sempre — o ramo
        só conhecia o `NullBackend` —, e o autoswitch seguia sondando um
        XWayland morto pelo resto da sessão.
        """
        reader = _reader_xlib_com_conexao_provada_morta(monkeypatch, wayland=True)

        assert reader.maybe_recover() is True
        assert type(reader._backend).__name__ == "_WaylandCascadeBackend"
        assert reader.backend_name in ("portal", "wlrctl", "null")
        assert reader.backend_name != "xlib"

    def test_o_resgate_nao_se_repete_depois_de_trocado(
        self, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        """Trocado uma vez, `precisa_de_resgate` cala — não fica em laço."""
        reader = _reader_xlib_com_conexao_provada_morta(monkeypatch, wayland=True)
        assert reader.maybe_recover() is True

        assert reader.precisa_de_resgate() is False
        assert reader.maybe_recover() is False

    def test_detect_window_backend_sozinha_devolveria_xlib_de_novo(
        self, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        """Por que o resgate NÃO pode chamar a factory.

        `DISPLAY` continua no ambiente — o servidor é que morreu —, então a
        factory devolveria `xlib` outra vez e o resgate seria um no-op caro.
        Esta é a razão de `maybe_recover` construir a cascata direto, e o
        teste existe para que ninguém "simplifique" de volta para a factory.
        """
        monkeypatch.setenv("DISPLAY", DISPLAY_MORTO)
        monkeypatch.setenv("WAYLAND_DISPLAY", "wayland-0")

        assert isinstance(window_detect.detect_window_backend(), XlibBackend)


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
        """A mordida da correção pela metade.

        O caminho: daemon nasce sem env (backend `null`), o env aparece com um
        `DISPLAY` MORTO, o resgate re-detecta `xlib`. Antes de 25/08 o store
        era semeado `healthy=True` por presunção — exatamente a mentira que a
        T-01 tinha arrancado da semeadura inicial e esquecido aqui.
        """
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
        """`sem_conexao_x` — o motivo que a aba Sistema pinta em laranja.

        A frase da tela (`descrever_deteccao_de_janela`) já estava certa em
        23/08 e continua sendo o modelo: quem mentia era o campo `healthy`,
        não ela. Este teste trava o par motivo+leitura de que ela depende.
        """
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
