"""FD-ZUMBI-DO-INIT-TIMEOUT-01 — o `init()` que estoura o timeout devolve o fd."""
from __future__ import annotations

import contextlib
import os
import threading
import time
from typing import Any
from unittest.mock import patch

from hefesto_dualsense4unix.core import backend_pydualsense as bp
from hefesto_dualsense4unix.core.backend_pydualsense import PyDualSenseController
from hefesto_dualsense4unix.core.evdev_reader import EvdevReader

TIMEOUT_DE_TESTE = 0.20

ATRASO_QUE_ESTOURA = 0.60

ESPERA_PELO_EOF = 5.0


def _null_evdev() -> EvdevReader:
    """EvdevReader sem device — o backend aqui só é palco para o `_open_one`."""
    reader = EvdevReader(device_path=None)
    reader._device_path = None
    return reader


class _HandleComFdDeVerdade:
    """Dublê de `_PinnedPyDualSense` que segura um descritor real.

    Imita a ordem que importa do upstream: o fd nasce DENTRO do `init()` (como o
    `hidapi.Device(path=...)` faz), e só depois vem a parte que pode demorar. É
    essa ordem que cria o vazamento — no instante do timeout o descritor já
    existe.
    """

    def __init__(
        self,
        path: bytes,
        *,
        is_edge: bool,
        atraso: float = 0.0,
        erro: BaseException | None = None,
    ) -> None:
        self.path = path
        self.is_edge = is_edge
        self._atraso = atraso
        self._erro = erro
        self.fd_de_escrita: int | None = None
        self.fd_de_leitura: int | None = None
        self.close_chamado = False
        self.aberto = threading.Event()

    def init(self) -> None:
        leitura, escrita = os.pipe()
        os.set_blocking(leitura, False)
        self.fd_de_leitura = leitura
        self.fd_de_escrita = escrita
        self.aberto.set()
        if self._atraso:
            time.sleep(self._atraso)
        if self._erro is not None:
            raise self._erro

    def close(self) -> None:
        self.close_chamado = True
        if self.fd_de_escrita is not None:
            os.close(self.fd_de_escrita)
            self.fd_de_escrita = None

    def descartar(self) -> None:
        """Fecha as duas pontas — higiene do teste, nunca a cura."""
        self.close()
        if self.fd_de_leitura is not None:
            os.close(self.fd_de_leitura)
            self.fd_de_leitura = None


def _fd_foi_devolvido(handle: _HandleComFdDeVerdade, prazo: float) -> bool:
    """True quando a ponta de escrita fechou DE VERDADE (EOF na de leitura)."""
    assert handle.fd_de_leitura is not None
    limite = time.monotonic() + prazo
    while time.monotonic() < limite:
        try:
            if os.read(handle.fd_de_leitura, 1) == b"":
                return True
        except BlockingIOError:
            pass
        time.sleep(0.01)
    return False


class TestInitQueEstouraNaoVazaFd:
    """A mordida: o descritor da tentativa que falhou tem de voltar."""

    def _rodar(self, **kwargs: Any) -> tuple[Any, _HandleComFdDeVerdade]:
        criados: list[_HandleComFdDeVerdade] = []

        def _fabrica(path: bytes, *, is_edge: bool) -> _HandleComFdDeVerdade:
            handle = _HandleComFdDeVerdade(path, is_edge=is_edge, **kwargs)
            criados.append(handle)
            return handle

        inst = PyDualSenseController(evdev_reader=_null_evdev())
        with patch.object(bp, "_PinnedPyDualSense", _fabrica), patch.object(
            bp, "INIT_TIMEOUT_SEC", TIMEOUT_DE_TESTE
        ):
            devolvido = inst._open_one(b"/dev/hidraw-de-teste", is_edge=False)
        assert len(criados) == 1
        assert criados[0].aberto.wait(timeout=2.0)
        return devolvido, criados[0]

    def test_init_que_termina_depois_do_timeout_devolve_o_fd(self) -> None:
        """O ZUMBI: o `init()` estoura o teto e termina BEM. Sem a cura, o"""
        devolvido, handle = self._rodar(atraso=ATRASO_QUE_ESTOURA)

        assert devolvido is None, "o timeout tem de continuar devolvendo None"
        assert _fd_foi_devolvido(handle, ESPERA_PELO_EOF), (
            "o fd do handle órfão continua aberto — é o vazamento visto em "
            "/proc/<pid>/fd na máquina dela"
        )

    def test_init_que_estoura_e_depois_falha_tambem_devolve_o_fd(self) -> None:
        """O outro desfecho: o `init()` estoura o teto e termina COM ERRO. O fd"""
        devolvido, handle = self._rodar(
            atraso=ATRASO_QUE_ESTOURA, erro=OSError("hidraw sumiu")
        )

        assert devolvido is None
        assert _fd_foi_devolvido(handle, ESPERA_PELO_EOF), (
            "o fd do handle órfão que FALHOU continua aberto"
        )

    def test_init_rapido_nao_fecha_o_handle_entregue(self) -> None:
        """O contrapeso, e o teste que protege a bancada: no caminho feliz o"""
        devolvido, handle = self._rodar()

        assert devolvido is handle, "o caminho feliz tem de entregar o handle"
        assert not _fd_foi_devolvido(handle, 0.25), (
            "o fd do handle ENTREGUE foi fechado — isto arrancaria o hidraw do "
            "produto"
        )
        assert handle.close_chamado is False
        handle.descartar()

    def test_excecao_dentro_do_prazo_continua_propagando(self) -> None:
        """Regressão do contrato antigo: erro que chega DENTRO do prazo não é"""
        criados: list[_HandleComFdDeVerdade] = []

        def _fabrica(path: bytes, *, is_edge: bool) -> _HandleComFdDeVerdade:
            handle = _HandleComFdDeVerdade(
                path, is_edge=is_edge, erro=PermissionError("hidraw 0600 root")
            )
            criados.append(handle)
            return handle

        inst = PyDualSenseController(evdev_reader=_null_evdev())
        with patch.object(bp, "_PinnedPyDualSense", _fabrica), patch.object(
            bp, "INIT_TIMEOUT_SEC", TIMEOUT_DE_TESTE
        ):
            try:
                inst._open_one(b"/dev/hidraw-de-teste", is_edge=False)
            except PermissionError:
                pass
            else:  # pragma: no cover - só roda se o contrato quebrar
                raise AssertionError("a exceção dentro do prazo tem de propagar")
        assert criados[0].close_chamado is False
        criados[0].descartar()


class TestHandoffNaBorda:
    """A borda: quando o `init()` termina EXATAMENTE no teto, a posse do handle"""

    def test_handle_nunca_e_entregue_e_fechado_ao_mesmo_tempo(self) -> None:
        teto = 0.02
        criados: list[_HandleComFdDeVerdade] = []

        def _fabrica(path: bytes, *, is_edge: bool) -> _HandleComFdDeVerdade:
            handle = _HandleComFdDeVerdade(path, is_edge=is_edge, atraso=teto)
            criados.append(handle)
            return handle

        inst = PyDualSenseController(evdev_reader=_null_evdev())
        entregues = 0
        orfaos = 0
        try:
            with patch.object(bp, "_PinnedPyDualSense", _fabrica), patch.object(
                bp, "INIT_TIMEOUT_SEC", teto
            ):
                for _ in range(40):
                    antes = len(criados)
                    devolvido = inst._open_one(b"/dev/hidraw-de-teste", is_edge=False)
                    handle = criados[antes]
                    assert handle.aberto.wait(timeout=2.0)
                    if devolvido is None:
                        orfaos += 1
                        assert _fd_foi_devolvido(handle, ESPERA_PELO_EOF), (
                            "handle órfão na borda ficou com o fd aberto"
                        )
                    else:
                        entregues += 1
                        assert devolvido is handle
                        assert not _fd_foi_devolvido(handle, 0.05), (
                            "handle ENTREGUE na borda foi fechado pelo runner"
                        )
            assert entregues + orfaos == 40
        finally:
            for handle in criados:
                with contextlib.suppress(OSError):
                    handle.descartar()
