"""A leitura em fundo da Conexões e o leitor do BlueZ, com UM dono.

O que o ``state_full`` (o BlueZ, o diário, o ``kernel.log``, o ``maquina.json``) lê é caro e
lento; a tela não espera por ele. Cada leitura roda num fio, a volta da tela devolve a última
que chegou, e um gesto que grava manda ``esquecer`` a chave para a próxima volta ler de novo.

O cache é genérico e serve a seis leitores da 08 (o censo, a máquina, o wifi, o sino, os zumbis
e o BlueZ) e ao nome do jogador, que lê o ``Alias`` do BlueZ por aqui. Este módulo não importa
a 08 nem o ``nome_do_jogador``: os dois o importam, e o ciclo (o import tardio) não existe.
"""
from __future__ import annotations

import contextlib
import threading
import time
from collections.abc import Callable, Iterator
from typing import Any

from . import fios, perfil

_FUNDO: dict[str, tuple[float, Any]] = {}
_FUNDO_EM_VOO: set[str] = set()
_TRAVA_DO_FUNDO = threading.Lock()
_GERACAO: dict[str, int] = {}
LER_NA_HORA = False
VENCIDA = float("-inf")


def em_fundo(chave: str, ler: Callable[[], Any], validade_s: float) -> Any:
    """A última leitura de `chave`; pede outra num fio quando venceu."""
    agora = time.monotonic()
    with _TRAVA_DO_FUNDO:
        visto = _FUNDO.get(chave)
        if (visto is not None and agora - visto[0] < validade_s) or chave in _FUNDO_EM_VOO:
            return None if visto is None else visto[1]
        _FUNDO_EM_VOO.add(chave)
        geracao = _GERACAO.get(chave, 0)

    def trabalhar() -> None:
        try:
            valor = ler()
        except Exception:
            valor = None
        with _TRAVA_DO_FUNDO:
            fresca = _GERACAO.get(chave, 0) == geracao
            _FUNDO[chave] = (time.monotonic() if fresca else VENCIDA, valor)
            _FUNDO_EM_VOO.discard(chave)

    if LER_NA_HORA:
        trabalhar()
        return _FUNDO[chave][1]
    fios.soltar(f"radio-{chave}", trabalhar)
    return None if visto is None else visto[1]


def esquecer(*chaves: str) -> None:
    """Depois de um gesto que grava, a próxima volta lê de novo."""
    with _TRAVA_DO_FUNDO:
        for chave in chaves:
            _GERACAO[chave] = _GERACAO.get(chave, 0) + 1
            visto = _FUNDO.get(chave)
            if visto is not None:
                _FUNDO[chave] = (VENCIDA, visto[1])


def lido(chave: str) -> Any:
    """O que a última leitura de `chave` trouxe, sem pedir outra; `None` se nunca chegou."""
    with _TRAVA_DO_FUNDO:
        visto = _FUNDO.get(chave)
    return None if visto is None else visto[1]


_ETAPAS = threading.local()


@contextlib.contextmanager
def cronometro() -> Iterator[dict[str, float]]:
    """A conta das etapas (ms por nome) da montagem que corre neste fio."""
    conta: dict[str, float] = {}
    _ETAPAS.conta = conta
    try:
        yield conta
    finally:
        _ETAPAS.conta = None


@contextlib.contextmanager
def etapa(nome: str) -> Iterator[None]:
    """Soma o tempo do bloco a `nome` na conta do cronômetro deste fio; sem cronômetro, nada."""
    conta = getattr(_ETAPAS, "conta", None)
    t0 = time.perf_counter()
    try:
        yield
    finally:
        if conta is not None:
            conta[nome] = conta.get(nome, 0.0) + (time.perf_counter() - t0) * 1000


class Montagem:
    """A carga da aba se monta num fio próprio, e o tique pega a última pronta.

    Uma montagem por vez, sempre da aba pedida. O selo anda a cada gesto (`esquecer`): a carga
    que começou antes dele não pinta por cima do que o gesto mudou, e a aba trocada também
    descarta a da aba que saiu. `avisar` roda no fio da montagem quando uma carga fica pronta.
    """

    def __init__(self, avisar: Callable[[], Any] | None = None) -> None:
        self._trava = threading.Lock()
        self._no_ar = False
        self._selo = 0
        self._pronta: tuple[str, int, Any] | None = None
        self._avisar = avisar
        self.ultima_ms = 0.0

    def esquecer(self) -> None:
        """Um gesto mudou o que se vê: a carga pronta ou no ar não pinta mais."""
        with self._trava:
            self._selo += 1
            self._pronta = None

    def no_ar(self) -> bool:
        """Uma montagem corre agora?"""
        with self._trava:
            return self._no_ar

    def pegar(self, pagina: str) -> Any:
        """A carga pronta da aba pedida, uma vez só; `None` se não há."""
        with self._trava:
            pronta, self._pronta = self._pronta, None
            selo = self._selo
        if pronta is None or pronta[0] != pagina or pronta[1] != selo:
            return None
        return pronta[2]

    def pedir(self, pagina: str, montar: Callable[[], Any]) -> bool:
        """Solta `montar` num fio se nenhuma montagem corre; `True` se soltou."""
        with self._trava:
            if self._no_ar:
                return False
            self._no_ar = True
            selo = self._selo

        def trabalhar() -> None:
            t0 = time.perf_counter()
            valor: Any = None
            try:
                valor = montar()
            finally:
                ms = (time.perf_counter() - t0) * 1000
                with self._trava:
                    self._no_ar = False
                    self.ultima_ms = ms
                    fresca = valor is not None and selo == self._selo
                    if fresca:
                        self._pronta = (pagina, selo, valor)
            if fresca and self._avisar is not None:
                self._avisar()

        fios.soltar("hefesto-pacote", trabalhar)
        return True


def ler_o_bluez() -> tuple[tuple[Any, ...], tuple[Any, ...]] | None:
    """`(adaptadores, aparelhos)` do dono do BlueZ. Sob a suíte, nada: a régua injeta."""
    perfil._com_o_src()
    from hefesto_dualsense4unix.integrations import bluez_dbus

    if bluez_dbus.a_suite_esta_rodando():
        return None
    dono = bluez_dbus.dono()
    adaptadores = dono.adaptadores()
    aparelhos = dono.aparelhos()
    if adaptadores is None:
        return None
    return tuple(adaptadores), tuple(aparelhos or ())


def e_controle_do_bluez(a: Any) -> bool:
    """Pergunta à CLASSE (o dono é `gesto_de_pareamento.e_controle`); sem a classe, ao ícone."""
    perfil._com_o_src()
    from hefesto_dualsense4unix.integrations.gesto_de_pareamento import e_controle

    classe = getattr(a, "classe", None)
    if classe is not None:
        return e_controle(classe)
    icone = str(getattr(a, "icone", "") or "")
    if icone:
        return icone == "input-gaming"
    return "V054C" in str(getattr(a, "modalias", "") or "").upper()
