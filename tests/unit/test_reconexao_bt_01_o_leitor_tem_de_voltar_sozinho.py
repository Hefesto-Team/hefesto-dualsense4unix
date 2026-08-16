"""RECONEXÃO-BT-01 (16/08/2026) — o leitor tem de voltar sozinho, no nó NOVO.

**O defeito, medido com o aparelho na mão dela.** O controle cai e volta no
rádio (ou sai do cabo para o rádio) e o daemon nunca reabre os leitores::

    19:15:29  evdev_read_lost            errno 19   event25
    19:15:30  motion_reader_open_failed  errno 2    /dev/hidraw5
    19:15:30  controller_disconnected    reason=probe_offline
              … e depois disso, NADA.

O controle reconecta, o link BT fica autenticado e criptografado, o daemon diz
``connected=True`` — e os eixos ficam **congelados no último valor lido**.

**A parte cara é a mentira.** O vpad continua emitindo: 396 reports em 8 s, ID
``0x01``, sequência perfeita sem um salto — e ``LX`` travado em 128. Para o jogo
isso é um controle **vivo que nunca se mexe**; ele enumera, mostra "PlayStation"
nas opções, abre o hidraw pelo `winedevice.exe`, e nada acontece. Daí o relato
dela: *"recebeu um pouco de input e morreu"*, em três jogos diferentes.

**Por que os testes de hoje não pegaram.** Havia teste para a PERDA
(`test_read_lost_real_continua_com_warning_e_reset`) e para o estado estático.
Não havia nenhum para o **ciclo**: perde → o nó muda de número → volta. E é
exatamente aí que mora o defeito, porque na reconexão o kernel renumera: o
físico dela era ``event25`` antes e virou ``event26/27/28`` depois.

O `_locate` já procura por IDENTIDADE justamente por isso — a docstring dele
avisa que *"um externo que trocasse de eventN (replug, re-enumeração) nunca mais
era reencontrado"*. **Faltava o portão que prova que essa cura segura no ciclo
inteiro**, e é ele que este arquivo traz.

**O QUE ESTE ARQUIVO ELIMINOU** (16/08/2026, e é o resultado principal dele):
os três testes abaixo **passam** contra o código de hoje. Ou seja, o
`EvdevReader` reabre sim no nó novo, não insiste no número velho, e sobrevive a
um sumiço prolongado. **O defeito de 16/08 não está no leitor de evdev.**

Isso vale tanto quanto uma reprovação: fecha um suspeito com portão permanente e
manda a próxima investigação para o nível ACIMA. O que sobra do log daquele dia,
e ainda não tem portão:

- ``motion_reader_open_failed  errno 2  /dev/hidraw5`` — o leitor de movimento
  depende do broker devolver o fd, e o caminho dele é outro;
- ``controller_disconnected  reason=probe_offline`` (`daemon/connection.py`) —
  o daemon marcou o controle offline; se o probe não refizer, não adianta o
  leitor estar de pé;
- ``primary_grab_state = pending`` — foi o estado observado ao vivo com a
  entrada morta, e é o mais suspeito dos três.

**A regra que o dia acrescentou:** regressão que volta é regressão sem portão.
Um teste de estado estático não protege um defeito de transição.
"""
from __future__ import annotations

import sys
import threading
import time
from pathlib import Path
from typing import Any
from unittest.mock import MagicMock

import pytest

from hefesto_dualsense4unix.core import evdev_reader as er_mod
from hefesto_dualsense4unix.core.evdev_reader import EvdevReader

#: Os nós ANTES e DEPOIS da reconexão. Os números são os reais medidos na
#: máquina dela em 16/08: o físico caiu no `event25` e voltou no `event26`.
_NO_ANTES = Path("/dev/input/event25")
_NO_DEPOIS = Path("/dev/input/event26")


class _DeviceFalso:
    """Um `InputDevice` de bancada que sabe morrer e renascer noutro nó."""

    def __init__(self, caminho: str) -> None:
        self.path = caminho
        self.name = "DualSense Wireless Controller"
        self.fd = 0
        self.fechado = False

    def read(self) -> Any:
        return iter([])

    def close(self) -> None:
        self.fechado = True

    def grab(self) -> None: ...

    def ungrab(self) -> None: ...

    def capabilities(self, *_a: object, **_k: object) -> dict[int, object]:
        return {}


@pytest.fixture()
def bancada(monkeypatch: pytest.MonkeyPatch) -> dict[str, Any]:
    """Um mundo onde o nó do controle pode sumir e voltar com outro número."""
    estado: dict[str, Any] = {
        "no_atual": str(_NO_ANTES),
        "abertos": [],
        "morrer": threading.Event(),
    }

    def _abrir(caminho: str, *_a: object, **_k: object) -> _DeviceFalso:
        estado["abertos"].append(caminho)
        return _DeviceFalso(caminho)

    fake = MagicMock()
    fake.InputDevice = _abrir
    fake.ecodes = MagicMock()
    monkeypatch.setitem(sys.modules, "evdev", fake)

    # A descoberta devolve o nó VIGENTE — é o que muda quando o controle volta.
    monkeypatch.setattr(
        er_mod, "find_dualsense_evdev",
        lambda: Path(estado["no_atual"]) if estado["no_atual"] else None,
    )
    monkeypatch.setattr(er_mod, "discover_dualsense_evdevs", lambda: {})
    return estado


def _reader_com_morte(
    bancada: dict[str, Any], monkeypatch: pytest.MonkeyPatch
) -> EvdevReader:
    """Um reader cujo select morre com ENODEV assim que o flag é armado."""
    reader = EvdevReader(device_path=None)

    def _select(_dev: object) -> list[object]:
        if bancada["morrer"].is_set():
            bancada["morrer"].clear()
            raise OSError(19, "No such device")
        time.sleep(0.01)
        return []

    monkeypatch.setattr(reader, "_wait_ready", _select)
    return reader


class TestOCicloCompleto:
    def test_o_leitor_reabre_no_no_novo_depois_da_reconexao(
        self, bancada: dict[str, Any], monkeypatch: pytest.MonkeyPatch
    ) -> None:
        """A MORDIDA. É o defeito de 16/08 inteiro, em três atos.

        1. o reader abre no `event25`;
        2. o controle cai (ENODEV) e o nó SOME;
        3. o controle volta noutro número (`event26`).

        Se o reader não reabrir no nó novo, o daemon fica dizendo
        `connected=True` com os eixos congelados — que é o que aconteceu.
        """
        reader = _reader_com_morte(bancada, monkeypatch)
        assert reader.start() is True
        try:
            _esperar(lambda: str(_NO_ANTES) in bancada["abertos"], 2.0)

            # ato 2: o controle cai e o nó some do mundo
            bancada["no_atual"] = ""
            bancada["morrer"].set()
            time.sleep(0.3)

            # ato 3: volta com OUTRO número
            bancada["no_atual"] = str(_NO_DEPOIS)

            reabriu = _esperar(
                lambda: str(_NO_DEPOIS) in bancada["abertos"], 4.0
            )
        finally:
            reader.stop()

        assert reabriu, (
            "o leitor NÃO reabriu no nó novo — é o defeito de 16/08: o daemon "
            f"segue dizendo connected=True com os eixos congelados. "
            f"nós abertos: {bancada['abertos']}"
        )

    def test_o_no_velho_nao_e_reaberto_as_cegas(
        self, bancada: dict[str, Any], monkeypatch: pytest.MonkeyPatch
    ) -> None:
        """Reabrir o número antigo pegaria OUTRO aparelho.

        O kernel recicla `eventN`. Insistir no caminho memorizado, depois de um
        ENODEV, é como reabrir um fd reciclado — o reader passaria a ler o
        controle de outra pessoa na mesa, ou um teclado.
        """
        reader = _reader_com_morte(bancada, monkeypatch)
        assert reader.start() is True
        try:
            _esperar(lambda: str(_NO_ANTES) in bancada["abertos"], 2.0)
            quantos_antes = bancada["abertos"].count(str(_NO_ANTES))

            bancada["no_atual"] = ""
            bancada["morrer"].set()
            time.sleep(0.6)
        finally:
            reader.stop()

        assert bancada["abertos"].count(str(_NO_ANTES)) == quantos_antes, (
            "o reader reabriu o nó VELHO enquanto o controle estava fora — "
            "o kernel já pode ter dado esse número a outro aparelho"
        )

    def test_sumico_prolongado_nao_derruba_a_thread(
        self, bancada: dict[str, Any], monkeypatch: pytest.MonkeyPatch
    ) -> None:
        """Controle desligado por um tempo não pode matar o leitor.

        Se a thread morre no sumiço, nem a reconexão salva: não sobra ninguém
        para reabrir. É o modo de falha que produz o silêncio total no journal.
        """
        reader = _reader_com_morte(bancada, monkeypatch)
        assert reader.start() is True
        try:
            _esperar(lambda: str(_NO_ANTES) in bancada["abertos"], 2.0)
            bancada["no_atual"] = ""
            bancada["morrer"].set()
            time.sleep(1.0)

            bancada["no_atual"] = str(_NO_DEPOIS)
            voltou = _esperar(
                lambda: str(_NO_DEPOIS) in bancada["abertos"], 4.0
            )
        finally:
            reader.stop()
        assert voltou, "a thread do leitor não sobreviveu ao sumiço prolongado"


def _esperar(condicao: Any, limite_s: float) -> bool:
    """Espera ativa curta — devolve se a condição virou verdadeira a tempo."""
    fim = time.time() + limite_s
    while time.time() < fim:
        if condicao():
            return True
        time.sleep(0.02)
    return False
