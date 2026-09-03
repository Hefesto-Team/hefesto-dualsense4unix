"""O canal do RÁDIO obedece ao mesmo invariante do cabo — CANAL-POR-CONTROLE-02.

O invariante é o da MONITOR-QUE-VENCE-01 (08/08/2026), e ele cabe numa linha:
**um microfone de verdade nunca pode perder para um monitor.** Monitor é o laço
de retorno do que SAI; eleger um como microfone padrão é gravar o áudio do jogo
no lugar da voz dela.

Em 08/08 esse invariante foi aplicado ao microfone do CABO, pelo drop-in 51 do
WirePlumber (``priority.session = 1500``). O canal do RÁDIO ficou de fora — e
não por descuido de leitura, mas porque ele é INALCANÇÁVEL por ali:
``monitor.alsa.rules`` só enxerga nós criados pelo monitor de ALSA, e a source
da ponte de mic por Bluetooth é um ``module-pipe-source``, nó virtual criado
pelo servidor. O único sítio onde a prioridade dela pode ser escrita é o
``load-module`` da própria ponte.

Lá ela ficou em **200** por catorze dias depois da medição, com um comentário
dizendo espelhar o drop-in 51 — espelhando a versão de 25/07, que rebaixava
para 50 e foi substituída.

MEDIDO NA MÁQUINA DELA EM 03/09/2026, com um DualSense no cabo e a webcam
plugada (``LC_ALL=C pactl list sources``)::

    alsa_output.pci-…hdmi-stereo.monitor                  696
    alsa_output.pci-…iec958-stereo.monitor                736
    alsa_output…DualSense…analog-surround-40.monitor     1109
    alsa_input…DualSense…iec958-stereo   (o CABO)        1500
    alsa_input.pci-…analog-stereo        (placa do PC)   2009
    alsa_input…HD_Pro_Webcam_C920        (a webcam)      2109

Com 200, o canal do controle no rádio nascia abaixo dos TRÊS monitores —
inclusive abaixo do monitor do alto-falante do OUTRO controle, que é a mesa 2+2
dela. O aparelho aceita e publica o canal; quem o punha em último lugar era um
literal nosso.

O QUE ESTE ARQUIVO TRAVA: o invariante e a FAIXA, não o número mágico; que o
número escrito na constante é o que de fato viaja no ``pactl load-module``; e
que os DOIS sítios do mesmo número — a constante Python e o drop-in `.conf` —
não podem divergir em silêncio, já que um `.conf` do WirePlumber não importa
Python e um dono único é impossível.
"""

from __future__ import annotations

import re
from pathlib import Path

from hefesto_dualsense4unix.integrations import dualsense_bt_audio as bt

RAIZ = Path(__file__).resolve().parents[2]
DROPIN = RAIZ / "assets" / "wireplumber" / "51-hefesto-dualsense-no-default-source.conf"

#: MEDIDO em 08/08/2026 e RECONFERIDO em 03/09/2026 na máquina dela: o monitor
#: mais alto que existe lá é o do alto-falante do próprio DualSense. É o piso
#: que o canal do rádio precisa vencer.
MONITOR_MAIS_ALTO_MEDIDO = 1109

#: MEDIDO no mesmo instante: a captura REAL da placa do PC. É o teto — acima
#: disto o controle voltaria a roubar o posto de um microfone de verdade, que é
#: a queixa que criou o drop-in 51.
CAPTURA_REAL_MEDIDA = 2009


class _RunnerQueSoAnota:
    """Guarda a linha de comando em vez de rodar `pactl`. Nada sai daqui."""

    def __init__(self) -> None:
        self.chamadas: list[list[str]] = []

    def __call__(self, argv: list[str]) -> str | None:
        self.chamadas.append(list(argv))
        # `42` é o id de módulo que o `pactl load-module` devolveria; o
        # `iniciar()` segue em frente e falha no fifo, que é o que se quer.
        return "42\n"


def _prioridade_da_entrada_no_dropin() -> int | None:
    """A `priority.session` que o drop-in 51 dá à entrada do controle no cabo."""
    texto = DROPIN.read_text(encoding="utf-8")
    for bloco in re.split(r"\n\s*\{\s*\n", texto):
        corpo = "\n".join(
            ln for ln in bloco.splitlines() if not ln.lstrip().startswith("#")
        )
        if "alsa_input" not in corpo:
            continue
        achado = re.search(r"priority\.session\s*=\s*(\d+)", corpo)
        if achado:
            return int(achado.group(1))
    return None


def test_o_canal_do_radio_vence_qualquer_monitor() -> None:
    """A voz dela, pelo rádio, nunca pode perder para o laço do que sai.

    ARRANQUE A CURA (devolva `PRIORIDADE_SESSAO_DA_PONTE` para 200) e este
    teste REPROVA — é o estado em que a ponte viveu de 25/07 a 03/09/2026.
    """
    assert bt.PRIORIDADE_SESSAO_DA_PONTE > MONITOR_MAIS_ALTO_MEDIDO, (
        f"a source da ponte nasce em {bt.PRIORIDADE_SESSAO_DA_PONTE}, e o "
        f"monitor mais alto desta bancada foi MEDIDO em "
        f"{MONITOR_MAIS_ALTO_MEDIDO}. Um monitor vencendo um microfone "
        "significa que o que qualquer app gravar é o áudio de SAÍDA, não a voz "
        "dela — o defeito MONITOR-QUE-VENCE-01 inteiro, agora no rádio."
    )


def test_o_canal_do_radio_nao_rouba_de_um_microfone_de_verdade() -> None:
    """O contrapeso: curar não pode virar pôr o controle no topo.

    Sem esta asserção, a cura viraria a queixa original de volta — *"o controle
    fica mexendo no microfone"* —, agora com o produto tendo escolhido isso.
    """
    assert bt.PRIORIDADE_SESSAO_DA_PONTE < CAPTURA_REAL_MEDIDA, (
        f"a source da ponte nasce em {bt.PRIORIDADE_SESSAO_DA_PONTE}, acima da "
        f"captura real medida ({CAPTURA_REAL_MEDIDA}). O controle voltaria a "
        "virar microfone padrão sozinho."
    )


def test_a_faixa_do_radio_e_a_mesma_faixa_do_cabo() -> None:
    """Os dois sítios do mesmo número não podem divergir em silêncio.

    O `.conf` do WirePlumber não importa Python, e a source virtual da ponte é
    invisível para `monitor.alsa.rules` — então o número tem de existir duas
    vezes. Duas cópias sem portão é como esta casa fabrica divergência
    silenciosa; o portão é este teste.
    """
    do_cabo = _prioridade_da_entrada_no_dropin()
    assert do_cabo is not None, (
        "nenhuma regra do drop-in 51 casa `alsa_input.*DualSense` com "
        "`priority.session` — não há mais contra o que comparar o rádio."
    )
    assert do_cabo == bt.PRIORIDADE_SESSAO_DA_PONTE, (
        f"o canal do rádio nasce em {bt.PRIORIDADE_SESSAO_DA_PONTE} e o do cabo "
        f"em {do_cabo}. É o MESMO microfone, do MESMO controle, da MESMA pessoa: "
        "dois números querem dizer que a política de microfone depende do fio."
    )


def test_a_prioridade_viaja_de_verdade_no_load_module() -> None:
    """A constante não pode ser decorativa: ela tem de estar no argv do `pactl`.

    Sem esta asserção, alguém poderia corrigir a constante e deixar o literal
    velho na chamada — a régua ficaria verde sobre um canal que continua em
    último lugar. É a mesma classe de defeito do `--prova-gesto` que dava verde
    sobre dois botões que ele nunca clicava.
    """
    runner = _RunnerQueSoAnota()
    fonte = bt.SourceVirtualPipeWire(
        nome="hefesto_dualsense_bt_aabbcc",
        descricao="Microfone do controle",
        runner=runner,
    )
    # Sem PipeWire de verdade o `_abrir_fifo` falha e o `iniciar()` recua — o
    # que interessa já foi anotado: a linha de comando do `load-module`.
    fonte.iniciar()
    carregas = [c for c in runner.chamadas if len(c) > 1 and c[1] == "load-module"]
    assert carregas, "a ponte não chegou a pedir o `module-pipe-source`"
    argv = carregas[0]
    props = [a for a in argv if a.startswith("source_properties=")]
    assert props, "o `load-module` foi montado sem `source_properties`"
    assert f"priority.session={bt.PRIORIDADE_SESSAO_DA_PONTE}" in props[0], (
        f"o argv leva {props[0]!r}, e a constante diz "
        f"{bt.PRIORIDADE_SESSAO_DA_PONTE}. A régua estaria medindo uma constante "
        "que o produto não usa."
    )


def test_o_porque_esta_junto_do_numero() -> None:
    """Os números medidos moram junto da regra que eles justificam.

    Sem eles, `1500` é número mágico — e número mágico é o primeiro a ser
    "simplificado" de volta para 200 por quem leu só o nome da constante. Foi
    exatamente assim que o 200 sobreviveu catorze dias à medição que o derrubou.
    """
    fonte = Path(bt.__file__).read_text(encoding="utf-8")
    assert "MONITOR-QUE-VENCE-01" in fonte, (
        "sumiu do módulo o registro de qual medição fixou esta faixa"
    )
    for numero in (str(MONITOR_MAIS_ALTO_MEDIDO), str(CAPTURA_REAL_MEDIDA)):
        assert numero in fonte, (
            f"o valor medido {numero} sumiu do módulo — sem ele a faixa vira "
            "opinião, e a próxima pessoa não sabe contra o que ela foi calibrada."
        )
