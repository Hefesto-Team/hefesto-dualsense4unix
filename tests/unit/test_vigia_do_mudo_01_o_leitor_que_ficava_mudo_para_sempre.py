"""VIGIA-DO-MUDO-01 (17/08/2026) — o leitor mudo com o fd aberto, sem log.

**O defeito, medido duas vezes com o aparelho na mão dela.** O `EvdevReader`
para de receber eventos mantendo o **mesmo** `eventN`: o fd continua aberto, o
`select` nunca acusa nada, não há `ENODEV`, não há exceção, e **não sai uma
linha no journal**. O daemon segue publicando `connected=True` com os sticks
congelados. Só `systemctl --user restart hefesto-dualsense4unix` curava.

Sintoma publicado, e ele engana::

    o vpad emitindo 1573 reports em 10 s, cadência normal, LX travado em 129
    (16/08, no rádio: 396 reports em 8 s, LX travado em 128)

**Quem estava emitindo não era quem tinha parado.** O vpad tem dois leitores
alimentando o mesmo report: o `PhysicalReportReader` (hidraw — giro, touch) e
o `EvdevReader` (sticks, botões, gatilhos). A ~157 Hz medidos, quem emitia era
o espelho do hidraw, que estava **vivo**. O ramo evdev é que estava mudo. Por
isso "o vpad continua emitindo" nunca foi consolo: os dois ramos são
independentes, e o que o jogo joga vem do que estava parado.

**E o `LX=129` é a prova, não o ruído.** 129 não é o valor de fábrica do
snapshot — esse é 128 cravado (`EvdevSnapshot.lx`). 129 é o que a
`_semear_posicao_de_repouso` escreve no **open**, lendo do `absinfo` a posição
real daquela unidade (SEMENTE-DO-REPOUSO-01; nenhuma das quatro unidades da
mesa de 15/08 repousa em 128). Logo: **o nó foi reaberto com sucesso e, a
partir daquele open, zero `EV_ABS` chegou.**

**Por que ninguém pegou antes.** O irmão `PhysicalReportReader` tem teto de
silêncio desde a GYRO-BT-SILENCIO-01 (`_SILENCE_REOPEN_USB_S = 1.0`) — larga o
fd e re-resolve. O `EvdevReader` não tinha nada equivalente: só sabia se curar
quando o nó **trocava de número** (`is_stale`), e este modo de falha não troca.
A casa sabia se curar num leitor e não no outro.

**E copiar o teto do irmão seria um segundo defeito.** O hidraw entrega ~250 Hz
mesmo com o controle parado na mesa — lá, silêncio É link morto. O evdev só
emite quando algo MUDA: um controle em repouso fica legitimamente mudo para
sempre, e um teto de tempo puro o reabriria em laço. Por isso a régua é a
DISCORDÂNCIA com o `EVIOCGABS`, e o teste que prova essa diferença é o
`test_controle_parado_na_mesa_nao_e_mudo` — sem ele, a cura errada passa.

**A régua, provada na bancada em 17/08:** com o daemon segurando o grab do
`event25`, um segundo leitor sem grab recebe zero eventos e mesmo assim vê o
`absinfo` acompanhar o kernel. O `EVIOCGABS` lê o estado do `input_dev`, não a
nossa fila — e é essa distinção que faz o vigia possível.
"""

from __future__ import annotations

from types import SimpleNamespace
from typing import Any

import pytest

from hefesto_dualsense4unix.core.evdev_reader import (
    EixoAbsoluto,
    EvdevReader,
)

#: Os códigos evdev que o vigia consulta. Os valores são os do kernel (Linux
#: `input-event-codes.h`) — inventar números aqui faria o teste concordar com
#: um `ecodes` de mentira e discordar do produto.
_ECODES = SimpleNamespace(
    ABS_X=0x00, ABS_Y=0x01, ABS_Z=0x02, ABS_RX=0x03, ABS_RY=0x04, ABS_RZ=0x05
)

#: A faixa que o DualSense declara nos quatro sticks.
_FAIXA_STICK = EixoAbsoluto(minimo=0, maximo=255, flat=0, fuzz=0, resolucao=0)


class _DevFalso:
    """Um `InputDevice` cujo `absinfo` responde o que a bancada mandar.

    `ilegivel=True` reproduz o eixo sem `absinfo` legível — o caso "não sei
    conferir", que **não pode** ser confundido com "discorda".
    """

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
        """Valor igual ao mínimo declarado, num stick, é memória zerada.

        Mesma recusa da semeadura, pelo mesmo motivo: tratar isso como
        discordância faria o vigia reabrir em laço um nó que acabou de nascer.
        """
        reader = _reader_publicando(lx=128)
        dev = _DevFalso({_ECODES.ABS_X: 0})
        assert reader._o_kernel_discorda(dev, _ECODES) == {}

    def test_o_gatilho_tambem_e_vigiado(self) -> None:
        """`l2_raw` repousa em 0 — ali o mínimo é repouso, não extremo."""
        reader = _reader_publicando(l2_raw=0)
        dev = _DevFalso({_ECODES.ABS_Z: 200})
        assert reader._o_kernel_discorda(dev, _ECODES) == {"l2_raw": (0, 200)}


class TestOLaco:
    """`_read_until_signaled` — o vigia dentro do laço de leitura.

    Nenhum destes testes dorme: o silêncio é contado por `_SELECT_TIMEOUT_S`,
    não por relógio de parede. A casa exige relógio injetado, nunca `sleep`.
    """

    @staticmethod
    def _sempre_em_timeout(reader: EvdevReader, monkeypatch: pytest.MonkeyPatch,
                           teto: int = 400) -> dict[str, int]:
        """O select nunca fica pronto — o fd está vivo e mudo.

        O teto existe para o teste do controle parado terminar: lá o vigia
        NUNCA devolve "mudo", e sem parada o laço giraria para sempre.
        """
        contas = {"voltas": 0}

        def _wait(_dev: object) -> list[object]:
            contas["voltas"] += 1
            if contas["voltas"] > teto:
                reader._stop_flag.set()
            return []

        monkeypatch.setattr(reader, "_wait_ready", _wait)
        return contas

    def test_o_leitor_mudo_larga_o_fd(self, monkeypatch: pytest.MonkeyPatch) -> None:
        """A MORDIDA. Arranque o `_o_kernel_discorda` e este teste fica vermelho.

        Antes da VIGIA-DO-MUDO-01 este laço nunca saía: o fd vivo, o select em
        timeout para sempre, e o daemon publicando o valor do open até alguém
        reiniciar o serviço na mão.
        """
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
        """O teste que separa esta cura da cura ERRADA.

        Um teto de silêncio puro — o do `PhysicalReportReader`, que é a cura
        óbvia e a que quase se escreveu — reprovaria aqui: o controle está
        parado na mesa, o evdev não emite (é o normal dele), e o fd está
        perfeito. Reabrir seria um laço de reopen num nó saudável.
        """
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
        """Corrida benigna: o evento estava a caminho entre o ioctl e a conta.

        O kernel discorda na primeira conferência e concorda na segunda. O
        vigia tem de engolir — largar o fd por uma leitura solitária trocaria
        um defeito raro por um reopen espúrio frequente.
        """
        reader = _reader_publicando(lx=129)
        contas = self._sempre_em_timeout(reader, monkeypatch)

        class _DevQueSeCorrige(_DevFalso):
            """Discorda no `ABS_X` na 1ª conferência e concorda daí em diante.

            Conta CONFERÊNCIAS pelo `ABS_X`, não consultas: cada rodada do
            vigia consulta os seis eixos, e contar consultas faria a "primeira
            conferência" acabar no meio dela.
            """

            def __init__(self) -> None:
                super().__init__({})
                self.conferencias = 0

            def absinfo(self, code: int) -> Any:
                self.consultas += 1
                if code != _ECODES.ABS_X:
                    raise OSError(22, "Invalid argument")  # "não sei" nos outros
                self.conferencias += 1
                return SimpleNamespace(value=40 if self.conferencias == 1 else 129)

        dev = _DevQueSeCorrige()
        assert reader._read_until_signaled(dev, _ECODES) == "stop"
        assert dev.conferencias >= 2, "o vigia não chegou à segunda conferência"
        assert contas["voltas"] > 400


class TestOQueOVigiaNaoQuebra:
    """Os irmãos herdam o laço e não podem herdar um veredito que não sabem dar."""

    def test_a_base_nao_sabe_conferir_e_isso_sai_como_concordancia(self) -> None:
        """`MotionSensorReader`/`TouchpadReader` não têm eixos de stick.

        O hook da base devolve `{}` — que significa "concordamos" E "não sei".
        Os dois têm de sair iguais, senão um leitor que não sabe se conferir
        derrubaria o próprio fd a cada `_CONFERIR_MUDO_S`.
        """
        from hefesto_dualsense4unix.core.evdev_reader import _EvdevReconnectLoop

        assert _EvdevReconnectLoop._o_kernel_discorda(
            _EvdevReconnectLoop(), _DevFalso({_ECODES.ABS_X: 40}), _ECODES
        ) == {}
