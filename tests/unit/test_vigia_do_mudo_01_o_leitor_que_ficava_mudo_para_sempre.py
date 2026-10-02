"""VIGIA-DO-MUDO-01 (17/08/2026) — o leitor mudo com o fd aberto, sem log."""

from __future__ import annotations

from types import SimpleNamespace
from typing import Any

import pytest

from hefesto_dualsense4unix.core.evdev_reader import (
    EixoAbsoluto,
    EvdevReader,
)

_ECODES = SimpleNamespace(
    ABS_X=0x00, ABS_Y=0x01, ABS_Z=0x02, ABS_RX=0x03, ABS_RY=0x04, ABS_RZ=0x05
)

#: A faixa que o DualSense declara nos quatro sticks.
_FAIXA_STICK = EixoAbsoluto(minimo=0, maximo=255, flat=0, fuzz=0, resolucao=0)


class _DevFalso:
    """Um `InputDevice` cujo `absinfo` responde o que a bancada mandar."""

    def __init__(self, valores: dict[int, int], *, ilegivel: bool = False) -> None:
        self.valores = valores
        self.ilegivel = ilegivel
        self.fd = 0
        self.consultas = 0

    def absinfo(self, code: int) -> Any:
        self.consultas += 1
        if self.ilegivel:
            raise OSError(19, "No such device")
        if code not in self.valores:
            raise OSError(22, "Invalid argument")
        return SimpleNamespace(value=self.valores[code])

    def read(self) -> Any:
        return iter([])

    def close(self) -> None: ...


def _reader_publicando(**campos: int) -> EvdevReader:
    """Um reader que já publica `campos` e conhece a faixa dos seis eixos."""
    reader = EvdevReader(device_path=None)
    reader._eixos = {
        code: _FAIXA_STICK
        for code in (
            _ECODES.ABS_X, _ECODES.ABS_Y, _ECODES.ABS_RX,
            _ECODES.ABS_RY, _ECODES.ABS_Z, _ECODES.ABS_RZ,
        )
    }
    if campos:
        reader._snapshot = reader._with(**campos)
    return reader


class TestARegua:
    """`_o_kernel_discorda` — a pergunta, isolada do laço."""

    def test_kernel_concorda_nao_e_discordancia(self) -> None:
        reader = _reader_publicando(lx=127, ly=126)
        dev = _DevFalso({_ECODES.ABS_X: 127, _ECODES.ABS_Y: 126})
        assert reader._o_kernel_discorda(dev, _ECODES) == {}

    def test_kernel_andou_e_nos_nao_e_nomeia_o_campo(self) -> None:
        """A MORDIDA da régua: é este o estado do defeito medido."""
        reader = _reader_publicando(lx=129)
        dev = _DevFalso({_ECODES.ABS_X: 40})
        divergencia = reader._o_kernel_discorda(dev, _ECODES)
        assert divergencia == {"lx": (129, 40)}, (
            "o vigia não viu o kernel andar enquanto o leitor publicava o "
            "valor semeado no open — é o defeito de 16-17/08 inteiro"
        )

    def test_absinfo_ilegivel_e_nao_sei_e_nao_discorda(self) -> None:
        """Não saber conferir nunca pode derrubar o fd."""
        reader = _reader_publicando(lx=129)
        assert reader._o_kernel_discorda(_DevFalso({}, ilegivel=True), _ECODES) == {}

    def test_ruido_de_um_lsb_nao_e_discordancia(self) -> None:
        """Todo stick em repouso chia nessa ordem de grandeza."""
        reader = _reader_publicando(lx=128)
        dev = _DevFalso({_ECODES.ABS_X: 129})
        assert reader._o_kernel_discorda(dev, _ECODES) == {}

    def test_talo_fantasma_nao_e_discordancia(self) -> None:
        """Valor igual ao mínimo declarado, num stick, é memória zerada."""
        reader = _reader_publicando(lx=128)
        dev = _DevFalso({_ECODES.ABS_X: 0})
        assert reader._o_kernel_discorda(dev, _ECODES) == {}

    def test_o_gatilho_tambem_e_vigiado(self) -> None:
        """`l2_raw` repousa em 0 — ali o mínimo é repouso, não extremo."""
        reader = _reader_publicando(l2_raw=0)
        dev = _DevFalso({_ECODES.ABS_Z: 200})
        assert reader._o_kernel_discorda(dev, _ECODES) == {"l2_raw": (0, 200)}


class TestOLaco:
    """`_read_until_signaled` — o vigia dentro do laço de leitura."""

    @staticmethod
    def _sempre_em_timeout(reader: EvdevReader, monkeypatch: pytest.MonkeyPatch,
                           teto: int = 400) -> dict[str, int]:
        """O select nunca fica pronto — o fd está vivo e mudo."""
        contas = {"voltas": 0}

        def _wait(_dev: object) -> list[object]:
            contas["voltas"] += 1
            if contas["voltas"] > teto:
                reader._stop_flag.set()
            return []

        monkeypatch.setattr(reader, "_wait_ready", _wait)
        return contas

    def test_o_leitor_mudo_larga_o_fd(self, monkeypatch: pytest.MonkeyPatch) -> None:
        """A MORDIDA. Arranque o `_o_kernel_discorda` e este teste fica vermelho."""
        reader = _reader_publicando(lx=129)
        self._sempre_em_timeout(reader, monkeypatch)
        dev = _DevFalso({_ECODES.ABS_X: 40})

        assert reader._read_until_signaled(dev, _ECODES) == "mudo", (
            "o laço não saiu com o fd vivo e o kernel discordando — o leitor "
            "ficaria mudo até o próximo restart do daemon"
        )

    def test_controle_parado_na_mesa_nao_e_mudo(
        self, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        """O teste que separa esta cura da cura ERRADA."""
        reader = _reader_publicando(lx=127, ly=126)
        contas = self._sempre_em_timeout(reader, monkeypatch)
        dev = _DevFalso({_ECODES.ABS_X: 127, _ECODES.ABS_Y: 126})

        assert reader._read_until_signaled(dev, _ECODES) == "stop"
        assert contas["voltas"] > 400, "o laço saiu cedo demais para ter vigiado"
        assert dev.consultas > 0, (
            "o vigia nunca perguntou ao kernel — o teste não provou nada"
        )

    def test_uma_conferencia_so_nao_basta(
        self, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        """Corrida benigna: o evento estava a caminho entre o ioctl e a conta."""
        reader = _reader_publicando(lx=129)
        contas = self._sempre_em_timeout(reader, monkeypatch)

        class _DevQueSeCorrige(_DevFalso):
            """Discorda no `ABS_X` na 1ª conferência e concorda daí em diante."""

            def __init__(self) -> None:
                super().__init__({})
                self.conferencias = 0

            def absinfo(self, code: int) -> Any:
                self.consultas += 1
                if code != _ECODES.ABS_X:
                    raise OSError(22, "Invalid argument")
                self.conferencias += 1
                return SimpleNamespace(value=40 if self.conferencias == 1 else 129)

        dev = _DevQueSeCorrige()
        assert reader._read_until_signaled(dev, _ECODES) == "stop"
        assert dev.conferencias >= 2, "o vigia não chegou à segunda conferência"
        assert contas["voltas"] > 400


class TestOQueOVigiaNaoQuebra:
    """Os irmãos herdam o laço e não podem herdar um veredito que não sabem dar."""

    def test_a_base_nao_sabe_conferir_e_isso_sai_como_concordancia(self) -> None:
        """`MotionSensorReader`/`TouchpadReader` não têm eixos de stick."""
        from hefesto_dualsense4unix.core.evdev_reader import _EvdevReconnectLoop

        assert _EvdevReconnectLoop._o_kernel_discorda(
            _EvdevReconnectLoop(), _DevFalso({_ECODES.ABS_X: 40}), _ECODES
        ) == {}
