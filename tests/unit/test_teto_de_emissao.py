"""TETO-DE-EMISSÃO-01: o cap de emissão de motion ao vpad não some nem sobe.

Por que este arquivo existe
---------------------------
``MOTION_EMIT_MAX_HZ`` (``core/physical_report_reader.py``) é o único teto
entre a rajada do rádio do DualSense e o ``/dev/uhid``. Até 13/08/2026 NENHUM
teste o segurava: o grep por ``MOTION_EMIT_MAX_HZ`` em ``tests/`` voltava
vazio, e os testes de throttle que já existem
(``test_physical_report_reader.py::TestThrottle``) passam ``max_hz=250.0`` À
MÃO — apagar a constante do módulo, ou subi-la para 1000.0, deixava toda a
suíte verde.

E há um convite ESCRITO a subi-la. A remedição de 11/08/2026 registra o rádio
sustentando "entre ~55 e ~392 Hz"
(``docs/protocol/driver-hid-playstation.md:902``), o que, lido de fora,
parece dizer que um cap de 250 Hz sobrou. Não sobrou, e é por isso que este
arquivo existe junto com aquela correção: o que chega ao ``/dev/uhid`` não é
a média, é o PICO DENTRO da rajada — o p05 do intervalo é teimosamente
1255 us, ou seja ~797 Hz instantâneos
(``docs/protocol/driver-hid-playstation.md:757-758``). Com quatro vpads em
co-op (e o co-op está sempre ligado nesta casa), tirar o teto são ~3200
escritas por segundo no ``/dev/uhid``.

O que cada teste trava — e o que faz cada um reprovar:

1. a constante EXISTE e está exportada — apagá-la reprova;
2. ela é o DEFAULT do ``PhysicalReportReader`` — desamarrar reprova;
3. ela não passa de 250 Hz — subir para 1000.0 reprova;
4. quatro vpads em co-op cabem em 1000 escritas/s — subir reprova;
5. COMPORTAMENTO, e é a mordida de verdade: um segundo da rajada MEDIDA
   (1255 us entre reports, ~797 Hz) contra um reader construído SEM passar
   ``max_hz`` não vira ~797 entregas. Com 250.0 o intervalo do cap (4 ms) é
   maior que o da rajada e segura; com 1000.0 o cap (1 ms) fica MENOR que o
   intervalo da rajada (1,255 ms) e TODAS as 797 janelas passam.

Nada aqui abre hidraw, uhid ou thread: os testes chamam ``_maybe_emit``
direto, com relógio injetado e um vpad de mentira. Nenhum controle é tocado.
"""
from __future__ import annotations

import inspect

from hefesto_dualsense4unix.core import physical_report_reader as prr
from hefesto_dualsense4unix.core.physical_report_reader import (
    MOTION_EMIT_MAX_HZ,
    MOTION_WINDOW_LEN,
    PhysicalReportReader,
)

#: Intervalo do PICO medido no rádio: p05 = 1255 us (~797 Hz instantâneos),
#: ``docs/protocol/driver-hid-playstation.md:757-758``, medido em 11/08/2026.
INTERVALO_DO_PICO_S = 1255e-6

#: Quantos vpads o co-op desta casa põe no ar ao mesmo tempo.
VPADS_EM_COOP = 4

#: Orçamento de escritas por segundo no ``/dev/uhid`` com o co-op cheio. Não é
#: um limite do kernel: é o teto que esta casa aceita pagar, e ele existe para
#: que subir o cap de um controle só não passe despercebido.
ORCAMENTO_UHID_WRITES_S = 1000.0


class _VpadDeMentira:
    """Conta as janelas entregues — é só isto que o teto governa."""

    player = 7

    def __init__(self) -> None:
        self.windows: list[bytes] = []

    def forward_motion(self, window: bytes) -> None:
        self.windows.append(bytes(window))

    def set_motion_streaming(self, on: bool) -> None:
        pass


class _RelogioDeMentira:
    def __init__(self) -> None:
        self.now = 1000.0

    def __call__(self) -> float:
        return self.now


def _janela(i: int) -> bytes:
    """Janela distinta a cada chamada — o dedup por valor não interfere."""
    return i.to_bytes(2, "little") + bytes(MOTION_WINDOW_LEN - 2)


class TestAConstanteExiste:
    def test_a_constante_esta_no_modulo(self) -> None:
        assert hasattr(prr, "MOTION_EMIT_MAX_HZ"), (
            "MOTION_EMIT_MAX_HZ sumiu de core/physical_report_reader.py — é o "
            "único teto entre a rajada do radio e o /dev/uhid"
        )
        assert isinstance(MOTION_EMIT_MAX_HZ, float)
        assert MOTION_EMIT_MAX_HZ > 0.0, "cap zero DESLIGA o teto (ver _min_interval)"

    def test_a_constante_esta_exportada(self) -> None:
        assert "MOTION_EMIT_MAX_HZ" in prr.__all__, (
            "tirar MOTION_EMIT_MAX_HZ do __all__ esconde o teto de quem o importa"
        )


class TestOTetoNaoSobe:
    def test_o_teto_nao_passa_de_250_hz(self) -> None:
        assert MOTION_EMIT_MAX_HZ <= 250.0, (
            f"MOTION_EMIT_MAX_HZ subiu para {MOTION_EMIT_MAX_HZ} Hz. O sustentado "
            "medido do radio (~55 a ~392 Hz, driver-hid-playstation.md:902) NÃO "
            "autoriza isto: o /dev/uhid recebe o PICO da rajada, ~797 Hz por "
            "controle (:757-758). 250 Hz é a faixa da taxa nativa do cabo — que "
            "foi medida em 250,88 Hz, ACIMA deste teto: ver "
            "TestAFonteDoCaboColadaNoTeto."
        )

    def test_o_coop_cheio_cabe_no_orcamento_do_uhid(self) -> None:
        writes_s = VPADS_EM_COOP * MOTION_EMIT_MAX_HZ
        assert writes_s <= ORCAMENTO_UHID_WRITES_S, (
            f"{VPADS_EM_COOP} vpads a {MOTION_EMIT_MAX_HZ} Hz = {writes_s} "
            f"escritas/s no /dev/uhid, acima do orçamento de "
            f"{ORCAMENTO_UHID_WRITES_S}. O co-op desta casa está SEMPRE ligado."
        )


class TestOTetoEstaAmarradoAoReader:
    def test_o_default_do_reader_e_a_constante(self) -> None:
        default = inspect.signature(PhysicalReportReader.__init__).parameters[
            "max_hz"
        ].default
        assert default == MOTION_EMIT_MAX_HZ, (
            f"o default de max_hz ({default}) desamarrou de MOTION_EMIT_MAX_HZ "
            f"({MOTION_EMIT_MAX_HZ}) — quem constrói o reader sem argumento "
            "deixaria de herdar o teto"
        )


class TestARajadaMedidaNaoPassa:
    """A mordida: um segundo da rajada REAL contra o reader com o default."""

    def _rodar_um_segundo_de_rajada(self) -> int:
        vpad, relogio = _VpadDeMentira(), _RelogioDeMentira()
        # SEM max_hz: é o default (a constante) que tem de segurar.
        reader = PhysicalReportReader(
            path_provider=lambda: None, vpad=vpad, time_fn=relogio
        )
        reports = int(1.0 / INTERVALO_DO_PICO_S)  # 797 reports em 1 s
        for i in range(reports):
            reader._maybe_emit(_janela(i))
            relogio.now += INTERVALO_DO_PICO_S
        return len(vpad.windows)

    def test_a_rajada_de_797_hz_sai_capada(self) -> None:
        entregues = self._rodar_um_segundo_de_rajada()
        assert entregues <= 260, (
            f"{entregues} janelas entregues em 1 s de rajada medida (~797 Hz). "
            f"Com MOTION_EMIT_MAX_HZ = {MOTION_EMIT_MAX_HZ} Hz o teto deixou de "
            "segurar o pico: com 4 vpads em co-op isso é milhares de escritas "
            "por segundo no /dev/uhid."
        )

    def test_o_teto_nao_estrangula_o_fluxo(self) -> None:
        # Contraprova de que o teste acima não passa por estar tudo parado: o
        # cap DEIXA passar o que a grade de 4 ms permite dentro da rajada.
        #
        # GRADE-QUE-NAO-BATIA-01 (19/08/2026): o piso subiu de 150 para 240.
        # O 150 não era um piso escolhido — era o defeito de aliasing medido e
        # depois consagrado como se fosse o normal: com a contagem antiga a
        # rajada rendia 200/s onde a grade rende 250/s. Um piso que passa com o
        # defeito inteiro de pé não é portão, é carimbo. Medido com a cura: 250.
        entregues = self._rodar_um_segundo_de_rajada()
        assert entregues >= 240, (
            f"só {entregues} janelas em 1 s — o gyro do jogo ficaria travado; "
            "o teto existe para capar a rajada, não para estrangular o fluxo"
        )


# ---------------------------------------------------------------------------
# GRADE-QUE-NAO-BATIA-01 — a fonte do CABO, colada no teto
# ---------------------------------------------------------------------------


#: A fonte medida na máquina dela em 19/08/2026, controle NO CABO: 6272 pacotes
#: de motion em 25 s no nó evdev do físico. É 0,88 Hz ACIMA do teto — e essa
#: distância de menos de um por cento é justamente o que fazia o defeito.
FONTE_DO_CABO_HZ = 250.88
INTERVALO_DO_CABO_S = 1.0 / FONTE_DO_CABO_HZ

#: Piso de entrega no cabo. 240 é o teto (250) com 4% de folga para o jitter do
#: host — apertado de propósito: o defeito entregava 125 a 158, então qualquer
#: piso entre 170 e 249 já morderia. 240 escolhe morder cedo.
PISO_NO_CABO = 240


class TestAFonteDoCaboColadaNoTeto:
    """O par simétrico do `TestARajadaMedidaNaoPassa`: o cabo, não o rádio.

    **O defeito, medido em 19/08/2026 e confirmado por três réguas.** Ela disse
    que o giroscópio estava "meio estranho, mas dá pra ver que tá sendo lido".
    Medido: o nó do físico entregava 251 Hz e o do espelho 160 Hz — 36% das
    amostras sumindo. Os VALORES estavam perfeitos (eixo a eixo, min e max
    idênticos nos dois nós); só a cadência caía, que é exatamente o que se sente
    como mira aos saltos.

    A causa: `_maybe_emit` perguntava "já passou um período desde a ÚLTIMA
    ENTREGA?" e carimbava o instante REAL da chegada. Com o teto em 250,0 Hz e
    a fonte em 250,88, cada entrega empurrava a referência alguns microssegundos
    para a frente, e o report seguinte chegava cedo por essa mesma diferença —
    ficava retido, era sobrescrito pelo próximo, e a taxa colapsava para perto
    da metade. Aliasing puro: bastava a fonte estar do lado de cima do teto.

    E a casa já sabia sem saber: em 15/08 o mapa de canais registrou a fonte em
    "250,1 Hz" com o teto em 250,0. O número que punha a fonte do lado errado
    estava escrito havia quatro dias.

    **Por que nenhum teste pegou.** Os 34 testes do reader alimentavam ou a
    rajada do rádio (797 Hz, MUITO acima do teto) ou passos de 1 ms à mão. Entre
    249 e 260 Hz — a única faixa onde o aliasing acontece — não havia nada. O
    defeito não era sutil; era invisível para as réguas que existiam.

    **Como estes testes MORDEM:** troque a grade de volta por
    `(now - self._last_emit_at) < self._min_interval` e os dois reprovam,
    entregando 125 a 158 onde exigem 240.
    """

    def _rodar_um_segundo_de_cabo(self, jitter_s: float = 0.0) -> int:
        vpad, relogio = _VpadDeMentira(), _RelogioDeMentira()
        # SEM max_hz: quem tem de segurar é o default, como no teste do rádio.
        reader = PhysicalReportReader(
            path_provider=lambda: None, vpad=vpad, time_fn=relogio
        )
        reports = int(1.0 / INTERVALO_DO_CABO_S)
        for i in range(reports):
            reader._maybe_emit(_janela(i))
            # Jitter DETERMINÍSTICO: alternar o sinal a cada report é o pior
            # caso para uma grade, e não depende de semente — teste que sorteia
            # número vira teste que às vezes reprova, e isso é pior que não ter.
            relogio.now += INTERVALO_DO_CABO_S + (jitter_s if i % 2 else -jitter_s)
        return len(vpad.windows)

    def test_a_fonte_do_cabo_sai_inteira(self) -> None:
        entregues = self._rodar_um_segundo_de_cabo()
        assert entregues >= PISO_NO_CABO, (
            f"só {entregues} janelas em 1 s de fonte de CABO ({FONTE_DO_CABO_HZ} Hz) "
            f"— esperado ao menos {PISO_NO_CABO}. A fonte está 0,88 Hz acima do "
            f"teto de {MOTION_EMIT_MAX_HZ} Hz, e o throttle voltou a contar a "
            "partir da última ENTREGA em vez de uma grade de prazo: cada report "
            "chega microssegundos cedo, fica retido e é sobrescrito. É o "
            "giroscópio aos saltos que ela sentiu em 19/08."
        )

    def test_o_jitter_do_host_nao_derruba_a_grade(self) -> None:
        """±5 us alternados — o host real não entrega em intervalo exato."""
        entregues = self._rodar_um_segundo_de_cabo(jitter_s=5e-6)
        assert entregues >= PISO_NO_CABO, (
            f"só {entregues} janelas com jitter de 5 us. Uma grade que só "
            "funciona com relógio perfeito não serve: nenhuma máquina entrega "
            "assim."
        )

    def test_o_silencio_longo_nao_vira_avalanche(self) -> None:
        """A grade não pode represar crédito enquanto o fluxo está parado.

        O outro lado da cura, e o motivo de a grade ter rebase: se ela só somasse
        períodos, dez segundos de controle parado virariam 2500 prazos vencidos,
        e a volta do fluxo sairia toda de uma vez no /dev/uhid — trocando o gyro
        aos saltos por uma avalanche, que é pior.
        """
        vpad, relogio = _VpadDeMentira(), _RelogioDeMentira()
        reader = PhysicalReportReader(
            path_provider=lambda: None, vpad=vpad, time_fn=relogio
        )
        reader._maybe_emit(_janela(0))
        relogio.now += 10.0  # dez segundos de silêncio

        antes = len(vpad.windows)
        for i in range(int(0.25 / INTERVALO_DO_CABO_S)):
            reader._maybe_emit(_janela(i + 1))
            relogio.now += INTERVALO_DO_CABO_S
        entregues = len(vpad.windows) - antes

        teto = int(MOTION_EMIT_MAX_HZ * 0.25) + 5
        assert entregues <= teto, (
            f"{entregues} janelas em 0,25 s depois de 10 s parado (teto {teto}) "
            "— a grade represou crédito e soltou tudo de uma vez. O rebase para "
            "`now + período` existe exatamente para isto."
        )
