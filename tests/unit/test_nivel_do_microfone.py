"""A régua do medidor de nível do microfone — LUZ-DO-MIC-01, PEÇA B.

Cada teste aqui MORDE: existe uma linha do produto que, arrancada, o faz
reprovar. As duas mordidas provadas em 03/09/2026 estão nomeadas no relatório
da peça, e são as dos dois defeitos que a sprint chama pelo nome:

* tirar o degrau de TEMPO da histerese (`Histerese.estado`) — a luz vira
  estroboscópio a cada sílaba;
* fazer `e_stream_do_medidor` não reconhecer o nosso próprio fluxo — a PEÇA A
  nos conta como ouvinte e a luz acende sozinha.
"""

from __future__ import annotations

import contextlib
import itertools
import os
import struct
from pathlib import Path

import pytest

from hefesto_dualsense4unix.integrations.nivel_do_microfone import (
    APLICACAO_ID,
    CHAVE_DO_PAPEL,
    CHAVE_DO_PICO,
    CHAVE_DO_UNIQ,
    ENTRA_S,
    LIMIAR_ENTRA,
    LIMIAR_SAI,
    MUDEZ_S,
    NOME_DO_MEDIDOR,
    PAPEL_DO_MEDIDOR,
    SEGURA_S,
    TAXA_HZ,
    VALOR_DO_PICO,
    Histerese,
    NivelDoMicrofone,
    argv_do_medidor,
    e_stream_do_medidor,
    propriedades_do_medidor,
)

#: Piso de silêncio MEDIDO no mic do DualSense pelo cabo, **605 s** (15.120
#: amostras) de sala como ela deixou, ninguém falando. Os quantis, em linear:
PISO_MEDIDO_P50 = 0.008713  # -41,20 dBFS
PISO_MEDIDO_P90 = 0.011978  # -38,43 dBFS
PISO_MEDIDO_P99 = 0.017502  # -35,14 dBFS

#: O maior pico dos mesmos 605 s: -12,93 dBFS. Ele é MAIOR que qualquer limiar
#: de amplitude utilizável — e é justamente por isso que a régua precisa de um
#: terceiro degrau. Ver `IMPULSOS_MEDIDOS`.
PISO_MEDIDO_P100 = 0.225800

#: AS DEZ RAJADAS REAIS que passaram do limiar ANTIGO (-30 dBFS) nesses 605 s,
#: com os valores medidos, na ordem medida. Dezenove amostras de 15.120.
#:
#: A FORMA delas é o achado: acima do limiar de HOJE (-24 dBFS) sobram CINCO
#: cruzamentos, e **os cinco são de uma amostra só** — 40 ms cada. Isso é
#: impulso (um clique, uma tecla, o tique de uma ventoinha), não fala. A rajada
#: mais longa que existe no piso inteiro tem 5 amostras e mora lá embaixo,
#: entre -30 e -24 dBFS.
IMPULSOS_MEDIDOS: list[list[float]] = [
    [0.054153],
    [0.061325, 0.062881, 0.054703, 0.045654, 0.048798],
    [0.117767],
    [0.068130],
    [0.061646, 0.039078],
    [0.041824],
    [0.225800, 0.042267],
    [0.073593, 0.045273],
    [0.045654, 0.039490, 0.040680],
    [0.101288],
]

PASSO_S = 1.0 / TAXA_HZ


class _Relogio:
    """Relógio dirigido. O tempo é parâmetro nesta peça justamente por isto."""

    def __init__(self, t: float = 1000.0) -> None:
        self.t = t

    def __call__(self) -> float:
        return self.t

    def anda(self, segundos: float) -> None:
        self.t += segundos


class _FluxoFalso:
    """Um cano de verdade no lugar do `parec`: fds reais, `os.read` real.

    Não é dublê de mentira: o seletor, o descritor cru e o `struct.unpack` do
    produto são exercitados como em produção. O que se troca é só quem escreve
    do outro lado.
    """

    def __init__(self) -> None:
        self.r, self.w = os.pipe()
        self.parado = False

    @property
    def fd(self) -> int:
        return self.r

    def vivo(self) -> bool:
        return not self.parado

    def parar(self) -> None:
        self.parado = True
        for fd in (self.r, self.w):
            with contextlib.suppress(OSError):
                os.close(fd)

    def escrever(self, *picos: float) -> None:
        os.write(self.w, b"".join(struct.pack("<f", p) for p in picos))

    def fechar_escrita(self) -> None:
        with contextlib.suppress(OSError):
            os.close(self.w)


class _Fabrica:
    """Abre `_FluxoFalso` e guarda o que foi pedido — e quantas vezes."""

    def __init__(self) -> None:
        self.abertos: list[_FluxoFalso] = []
        self.pedidos: list[tuple[str, str]] = []

    def __call__(self, fonte: str, uniq: str = "") -> _FluxoFalso:
        self.pedidos.append((fonte, uniq))
        fluxo = _FluxoFalso()
        self.abertos.append(fluxo)
        return fluxo


def _fala(padrao: str) -> list[float]:
    """Uma frase em passos de 40 ms: ``#`` é sílaba, ``.`` é a pausa entre elas.

    A pausa usa o PISO MEDIDO, não zero — é o que a sala dela entrega quando
    ninguém fala, e é o que separa "a luz acompanha a fala" de "a luz acompanha
    a forma de onda".
    """
    return [0.20 if ch == "#" else PISO_MEDIDO_P50 for ch in padrao]


def _transicoes(estados: list[bool | None]) -> int:
    return sum(1 for a, b in itertools.pairwise(estados) if a != b)


#: Quantas amostras seguidas o degrau de duração exige para acender.
AMOSTRAS_PARA_ACENDER = int(ENTRA_S / PASSO_S) + 1


def _acender(hist: Histerese, relogio: _Relogio, pico: float = 0.5) -> bool | None:
    """Acende a régua do jeito honesto: som SUSTENTADO por `ENTRA_S`.

    Uma amostra só não acende mais nada — é o degrau que a medição de 605 s
    exigiu, e todo teste que precisa da luz acesa passa por aqui.
    """
    estado: bool | None = None
    for _ in range(AMOSTRAS_PARA_ACENDER):
        estado = hist.aplicar(pico, relogio.t)
        relogio.anda(PASSO_S)
    return estado


def _alimentar(
    medidor: NivelDoMicrofone,
    relogio: _Relogio,
    picos: dict[int, float],
    fabrica: _Fabrica,
    voltas: int = AMOSTRAS_PARA_ACENDER + 1,
) -> None:
    """Escreve UMA amostra por volta em cada fluxo, andando o relógio.

    Uma amostra por volta é o que o `parec` faz: o degrau de duração mede o
    tempo do SINAL, então despejar quatro amostras num instante só não acende
    nada — e é assim que tem de ser.
    """
    for _ in range(voltas):
        for i, pico in picos.items():
            fabrica.abertos[i].escrever(pico)
        relogio.anda(PASSO_S)
        medidor.bombear(timeout_s=0.2)


def _escrever_ate_acender(
    fluxo: _FluxoFalso,
    medidor: NivelDoMicrofone,
    relogio: _Relogio,
    pico: float = 0.40,
) -> None:
    for _ in range(AMOSTRAS_PARA_ACENDER + 1):
        fluxo.escrever(pico)
        relogio.anda(PASSO_S)
        medidor.bombear(timeout_s=0.2)


# ---------------------------------------------------------------------------
# A HISTERESE — a mordida principal
# ---------------------------------------------------------------------------


def test_a_histerese_nao_pisca_entre_as_silabas() -> None:
    """UMA frase falada acende UMA vez e apaga UMA vez. Nunca mais que isso.

    MORDE: troque o degrau de TEMPO de `Histerese.estado` por um apagamento
    imediato (`>= self.segura_s` vira `> 0.0`) e esta frase produz 15
    transições em vez de 2 — o estroboscópio que a §PEÇA B da sprint proíbe
    com todas as letras.
    """
    # Silêncio, seis sílabas com pausas de 120 a 160 ms entre elas, e um
    # silêncio longo no fim. Cada caractere são 40 ms.
    padrao = "....###...####...##...####....###...##" + "." * 30
    relogio = _Relogio()
    hist = Histerese()
    estados: list[bool | None] = []
    for pico in _fala(padrao):
        estados.append(hist.aplicar(pico, relogio.t))
        relogio.anda(PASSO_S)

    assert estados[0] is False, "a sala quieta do começo não pode acender"
    assert True in estados, "a fala tem de acender a luz"
    assert estados[-1] is False, "o silêncio longo no fim tem de apagar"
    assert _transicoes(estados) == 2, (
        "a luz piscou no meio da fala: "
        f"{_transicoes(estados)} transições numa frase só"
    )


def test_a_histerese_ignora_o_piso_de_silencio_medido() -> None:
    """A sala quieta dela NÃO acende a luz — o piso PROPRIAMENTE DITO."""
    relogio = _Relogio()
    hist = Histerese()
    for _ in range(200):  # 8 s de sala quieta
        estado = hist.aplicar(PISO_MEDIDO_P99, relogio.t)
        relogio.anda(PASSO_S)
    assert estado is False
    assert PISO_MEDIDO_P99 < LIMIAR_SAI, (
        "o p99 do piso medido sustenta a luz acesa: ela nunca apagaria"
    )


def test_a_sala_vazia_dela_nao_acende_a_luz_nenhuma_vez() -> None:
    """As dez rajadas REAIS de 605 s de sala vazia, replicadas na ordem medida.

    Este é o teste que mudou o número desta peça. O par anterior
    (-30/-36 dBFS, SEM degrau de duração) acende a luz aqui; o de hoje não.

    MORDE, e de duas formas independentes:

    1. Apague o degrau de duração — em `Histerese.aplicar`, troque o bloco do
       `_acima_desde` por um `self._captando = True` direto — e a luz acende
       CINCO vezes numa sala onde ninguém falou.
    2. Devolva `LIMIAR_ENTRA` para 0.0316 (-30 dBFS) e ela acende de novo,
       porque a rajada de 200 ms do piso passa a valer.
    """
    relogio = _Relogio()
    hist = Histerese()
    acendeu = 0
    anterior = False
    for rajada in IMPULSOS_MEDIDOS:
        # 4 s de piso antes de cada rajada: o silêncio real que as separa.
        for _ in range(100):
            hist.aplicar(PISO_MEDIDO_P50, relogio.t)
            relogio.anda(PASSO_S)
        for pico in rajada:
            estado = hist.aplicar(pico, relogio.t)
            relogio.anda(PASSO_S)
            if estado is True and not anterior:
                acendeu += 1
            anterior = bool(estado)

    assert acendeu == 0, (
        f"a luz acendeu {acendeu} vez(es) numa sala onde ninguém falou — "
        "os impulsos do piso dela passaram pela régua"
    )


def test_o_maior_pico_da_sala_vazia_sozinho_nao_acende() -> None:
    """O p100 medido (-12,93 dBFS) é MAIOR que o limiar, e mesmo assim não
    acende: ele durou UMA amostra, e a régua pede quatro.

    É a prova de que subir a amplitude não era a cura — nenhum limiar abaixo
    de -12,93 dBFS pararia este impulso, e um limiar acima disso perderia a
    fala inteira.
    """
    assert PISO_MEDIDO_P100 > LIMIAR_ENTRA, (
        "o piso medido mudou: refaça a medição antes de mexer no limiar"
    )
    relogio = _Relogio()
    hist = Histerese()
    hist.aplicar(PISO_MEDIDO_P50, relogio.t)
    relogio.anda(PASSO_S)
    assert hist.aplicar(PISO_MEDIDO_P100, relogio.t) is False, (
        "um impulso de 40 ms acendeu a luz"
    )


def test_o_degrau_de_duracao_pede_amostras_seguidas_e_nao_soltas() -> None:
    """Quatro amostras altas espalhadas não acendem; quatro seguidas acendem.

    MORDE: tire o `self._acima_desde = None` do ramo "caiu abaixo" e a
    contagem deixa de ser contínua — as soltas passam a acender.
    """
    alto = LIMIAR_ENTRA * 2

    relogio = _Relogio()
    soltas = Histerese()
    for _ in range(6):  # alto, piso, alto, piso… seis vezes
        soltas.aplicar(alto, relogio.t)
        relogio.anda(PASSO_S)
        estado = soltas.aplicar(PISO_MEDIDO_P50, relogio.t)
        relogio.anda(PASSO_S)
    assert estado is False, "picos altos SOLTOS acenderam a luz"

    relogio = _Relogio()
    seguidas = Histerese()
    estado = None
    for _ in range(int(ENTRA_S / PASSO_S) + 1):
        estado = seguidas.aplicar(alto, relogio.t)
        relogio.anda(PASSO_S)
    assert estado is True, "picos altos SEGUIDOS não acenderam a luz"


def test_a_histerese_tem_dois_degraus_e_o_de_baixo_e_mais_baixo() -> None:
    """Um pico entre os dois limiares SUSTENTA a luz, mas não a acende."""
    meio = (LIMIAR_ENTRA + LIMIAR_SAI) / 2.0
    assert LIMIAR_SAI < LIMIAR_ENTRA

    relogio = _Relogio()
    apagada = Histerese()
    for _ in range(50):
        estado = apagada.aplicar(meio, relogio.t)
        relogio.anda(PASSO_S)
    assert estado is False, "o degrau do meio não pode ACENDER a luz"

    relogio = _Relogio()
    acesa = Histerese()
    assert _acender(acesa, relogio) is True
    for _ in range(50):  # 2 s, muito além de SEGURA_S
        estado = acesa.aplicar(meio, relogio.t)
        relogio.anda(PASSO_S)
    assert estado is True, "o degrau do meio tem de SUSTENTAR a luz acesa"


def test_a_histerese_apaga_quando_o_silencio_passa_de_segura_s() -> None:
    """Acesa, ela apaga — e apaga dentro do tempo escrito, não muito depois."""
    relogio = _Relogio()
    hist = Histerese()
    assert _acender(hist, relogio) is True

    relogio.anda(SEGURA_S * 0.5)
    assert hist.aplicar(PISO_MEDIDO_P50, relogio.t) is True, "apagou cedo demais"

    relogio.anda(SEGURA_S * 0.6)
    assert hist.aplicar(PISO_MEDIDO_P50, relogio.t) is False


def test_a_histerese_apaga_pelo_tempo_mesmo_sem_amostra_nova() -> None:
    """`estado()` reavalia o relógio: fluxo que emudece não fica aceso eterno."""
    relogio = _Relogio()
    hist = Histerese()
    assert _acender(hist, relogio) is True
    relogio.anda(SEGURA_S * 3)
    assert hist.estado(relogio.t) is False


def test_antes_da_primeira_amostra_a_histerese_diz_nao_sei() -> None:
    """`None` nunca é `False`: sem amostra não há afirmação a fazer."""
    assert Histerese().estado(1000.0) is None


def test_amostra_suja_nao_derruba_a_regua() -> None:
    """NaN e infinito não acendem nem apagam — são lixo, não medição."""
    relogio = _Relogio()
    hist = Histerese()
    assert _acender(hist, relogio) is True
    assert hist.aplicar(float("nan"), relogio.t) is True
    assert hist.aplicar(float("inf"), relogio.t) is True


# ---------------------------------------------------------------------------
# A IDENTIDADE — a outra mordida: se a PEÇA A não nos exclui, a luz mente
# ---------------------------------------------------------------------------


def test_a_peca_a_reconhece_o_nosso_fluxo_pelas_tres_marcas() -> None:
    """MORDE: faça `e_stream_do_medidor` devolver sempre False e a PEÇA A
    passa a nos contar como ouvinte — a luz acende sozinha, para sempre.
    """
    nosso = {
        "application.name": NOME_DO_MEDIDOR,
        "media.name": "luz-do-mic",
        CHAVE_DO_PICO: VALOR_DO_PICO,
        "application.id": APLICACAO_ID,
        CHAVE_DO_PAPEL: PAPEL_DO_MEDIDOR,
    }
    assert e_stream_do_medidor(nosso) is True

    # Cada marca sozinha basta: a forma do fluxo (pulse ou PipeWire nativo)
    # ainda não está fixada, e a nativa não publica PID nenhum.
    assert e_stream_do_medidor({CHAVE_DO_PICO: VALOR_DO_PICO}) is True
    assert e_stream_do_medidor({CHAVE_DO_PAPEL: PAPEL_DO_MEDIDOR}) is True
    assert e_stream_do_medidor({"application.id": APLICACAO_ID}) is True


def test_a_peca_a_nao_exclui_quem_esta_mesmo_ouvindo() -> None:
    """Um crivo largo demais apagaria a luz com alguém gravando de verdade."""
    chrome = {
        "application.name": "Google Chrome input",
        "application.process.binary": "chrome",
        "media.name": "Playback Stream",
    }
    parec_de_estranho = {
        "application.name": "parec",
        "application.process.binary": "pacat",
    }
    assert e_stream_do_medidor(chrome) is False
    assert e_stream_do_medidor(parec_de_estranho) is False
    assert e_stream_do_medidor({}) is False


def test_o_argv_liga_o_modo_de_pico_do_servidor() -> None:
    """Sem `resample.peaks` vem a onda decimada e o limiar NUNCA dispara.

    Medido em 03/09/2026, na MESMA fonte e no mesmo minuto: COM a propriedade,
    max = 0,013535 (-37,4 dBFS); SEM ela, max = 0,000245 (-72,2 dBFS), 55 vezes
    menor. E uma captura CRUA de 48 kHz aberta ao lado, no mesmo instante, deu
    max = 0,013550 — o mesmo pico do fluxo de 25 Hz, com 960 vezes mais
    tráfego. O modo de pico não aproxima o pico: ele entrega o pico.
    """
    argv = argv_do_medidor("alsa_input.exemplo", "aabbcc0000ab")
    assert f"--property={CHAVE_DO_PICO}={VALOR_DO_PICO}" in argv

    # A prova de que a ausência mataria a peça: a maior amostra medida SEM o
    # modo de pico não chega nem perto de acender a luz.
    maior_sem_pico = 0.000245
    assert maior_sem_pico < LIMIAR_ENTRA / 100

    # E o pico do modo de pico bate com a verdade de campo de 48 kHz, dentro de
    # um passo de quantização do s16 que a captura crua usa.
    pico_25hz, cru_48khz = 0.013535, 0.013550
    assert abs(pico_25hz - cru_48khz) < 1.0 / 32768


def test_o_argv_pede_a_latencia_que_a_medicao_exigiu() -> None:
    """Sem `--latency-msec` a primeira amostra chega aos 2,006 s (medido)."""
    argv = argv_do_medidor("alsa_input.exemplo")
    assert "--latency-msec=100" in argv


def test_o_argv_se_identifica_para_a_peca_a() -> None:
    """As propriedades do argv, lidas de volta, satisfazem o próprio crivo."""
    argv = argv_do_medidor("alsa_input.exemplo", "aabbcc0000ab")
    props = {}
    for arg in argv:
        if arg.startswith("--property="):
            chave, _, valor = arg[len("--property=") :].partition("=")
            props[chave] = valor
    assert e_stream_do_medidor(props) is True
    assert props[CHAVE_DO_UNIQ] == "aabbcc0000ab"
    assert f"--client-name={NOME_DO_MEDIDOR}" in argv


def test_o_argv_nao_pede_media_role() -> None:
    """Medido: `media.role` faz o servidor compartilhar o estado de
    restauração com todo fluxo de papel produção — mexer no nosso volume
    mexeria no de estranhos.
    """
    argv = argv_do_medidor("alsa_input.exemplo", "aabbcc0000ab")
    assert not any("media.role" in arg for arg in argv)


def test_sem_uniq_nao_se_publica_endereco_inventado() -> None:
    props = propriedades_do_medidor("")
    assert CHAVE_DO_UNIQ not in props
    assert props[CHAVE_DO_PICO] == VALOR_DO_PICO


def test_a_fonte_entra_como_argumento_e_nunca_como_comando() -> None:
    """Invariante do projeto: sem `shell=True`, argv fixo."""
    argv = argv_do_medidor("alsa_input.com espaço; rm -rf /")
    assert argv[0] == "parec"
    assert "--device=alsa_input.com espaço; rm -rf /" in argv


def test_o_parec_nasce_com_cano_na_saida_e_isso_e_a_trava_de_morte(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """`stdout=subprocess.PIPE` é o que mata o filho quando o pai morre.

    Medido em 03/09 matando o pai com SIGKILL: com o cano o `parec` morre
    junto; com `stdout` para `/dev/null` ele sobrevive ÓRFÃO, segurando o
    microfone dela aberto — foi assim que um `parec` deste medidor ficou 39
    minutos de pé em 03/09 às 00h36. A sessão não muda nada; o cano muda tudo.

    MORDE: troque `stdout=subprocess.PIPE` por `subprocess.DEVNULL` (ou por um
    arquivo) em `abrir_fluxo` e este teste reprova — que é exatamente a
    mudança que reabre o vazamento.
    """
    import subprocess as sp

    from hefesto_dualsense4unix.integrations import nivel_do_microfone as mod

    vistos: dict[str, object] = {}

    class _ProcFalso:
        stdout = os.fdopen(os.open(os.devnull, os.O_RDONLY), "rb")

        def poll(self) -> None:
            return None

    def _popen_espiao(argv: list[str], **kwargs: object) -> _ProcFalso:
        vistos.update(kwargs)
        vistos["argv"] = argv
        return _ProcFalso()

    monkeypatch.setattr(mod.shutil, "which", lambda _nome: "/usr/bin/parec")
    monkeypatch.setattr(mod.subprocess, "Popen", _popen_espiao)
    mod.abrir_fluxo("alsa_input.exemplo", "aabbcc0000ab")

    assert vistos["stdout"] is sp.PIPE, (
        "o `parec` nasceu SEM cano na saída: quando o daemon morrer ele fica "
        "órfão com o microfone dela aberto"
    )
    assert "start_new_session" not in vistos or not vistos["start_new_session"]


@pytest.mark.skipif(not hasattr(os, "fork"), reason="precisa de fork")
def test_o_cano_mata_o_filho_e_o_devnull_o_deixa_vazar() -> None:
    """A PREMISSA da trava de morte, exercitada com processos de verdade.

    Não é dublê: nasce um filho real, o pai leva SIGKILL, e conta-se quem
    sobreviveu. É a medição de 03/09 virada teste — se o kernel ou o Python
    mudarem esse comportamento, o desenho de `abrir_fluxo` perde o chão e é
    melhor descobrir aqui do que na mesa dela.
    """
    import signal
    import subprocess
    import sys
    import time

    # O filho escreve para sempre no stdout, como o `parec` em modo de pico.
    filho = "import sys,time\nwhile True: sys.stdout.write('x'); sys.stdout.flush(); time.sleep(0.02)"  # noqa: E501
    # O pai abre o filho e dorme. `saida` decide se há cano ou não.
    pai = (
        "import subprocess,sys,time\n"
        "alvo = subprocess.PIPE if sys.argv[1] == 'cano' else subprocess.DEVNULL\n"
        f"p = subprocess.Popen([sys.executable, '-c', {filho!r}], stdout=alvo)\n"
        "print(p.pid, flush=True)\n"
        "time.sleep(60)\n"
    )

    def _sobreviveu(modo: str) -> bool:
        proc = subprocess.Popen(
            [sys.executable, "-c", pai, modo], stdout=subprocess.PIPE, text=True
        )
        try:
            assert proc.stdout is not None
            neto = int(proc.stdout.readline().strip())
            proc.send_signal(signal.SIGKILL)
            proc.wait(timeout=10)
            for _ in range(60):  # até 6 s
                time.sleep(0.1)
                try:
                    os.kill(neto, 0)
                except OSError:
                    return False
            os.kill(neto, signal.SIGKILL)  # limpa o que vazou
            return True
        finally:
            if proc.poll() is None:  # pragma: no cover - defensivo
                proc.kill()

    assert _sobreviveu("cano") is False, (
        "o filho com CANO sobreviveu ao pai: a trava de morte de `abrir_fluxo` "
        "não vale mais nesta máquina"
    )
    assert _sobreviveu("devnull") is True, (
        "o filho com /dev/null morreu sozinho — se isto passou a valer, o "
        "vazamento de 00h36 deixou de ser possível e o desenho pode simplificar"
    )


def test_a_peca_b_nao_importa_numpy() -> None:
    """O `numpy` NÃO está no `pyproject.toml`; importá-lo repetiria a dívida
    do `playwright` e faria a luz nascer morta em toda árvore nova.
    """
    from hefesto_dualsense4unix.integrations import nivel_do_microfone

    fonte = Path(nivel_do_microfone.__file__).read_text(encoding="utf-8")
    assert "import numpy" not in fonte
    assert "from numpy" not in fonte


# ---------------------------------------------------------------------------
# O MEDIDOR — com descritores de verdade
# ---------------------------------------------------------------------------


def _medidor(fabrica: _Fabrica, relogio: _Relogio) -> NivelDoMicrofone:
    return NivelDoMicrofone(abrir=fabrica, agora=relogio, automatico=False)


def test_o_medidor_le_float32_de_um_descritor_de_verdade() -> None:
    """Ponta a ponta: cano real, seletor real, `struct.unpack` do produto."""
    fabrica, relogio = _Fabrica(), _Relogio()
    with _medidor(fabrica, relogio) as medidor:
        medidor.seguir({"aaa": "alsa_input.exemplo"})
        medidor.bombear(timeout_s=0.0)
        assert medidor.captando() == {"aaa": None}, "antes da amostra, não sei"

        _alimentar(medidor, relogio, {0: 0.30}, fabrica)
        assert medidor.captando() == {"aaa": True}

        for _ in range(int(SEGURA_S / PASSO_S) + 3):
            fabrica.abertos[0].escrever(PISO_MEDIDO_P50)
            relogio.anda(PASSO_S)
            medidor.bombear(timeout_s=0.2)
        assert medidor.captando() == {"aaa": False}


def test_sem_canal_a_resposta_e_nao_sei_e_nunca_falso() -> None:
    """O controle do RÁDIO não publica canal. `False` diria "medi e não há
    som" — a luz apagaria mentindo, e a PEÇA C não teria como saber.
    """
    fabrica, relogio = _Fabrica(), _Relogio()
    with _medidor(fabrica, relogio) as medidor:
        medidor.seguir({"radio": None})
        medidor.bombear(timeout_s=0.0)
        assert medidor.captando() == {"radio": None}
        assert medidor.captando_em("radio") is None
        assert fabrica.pedidos == [], "abriu processo para quem não tem canal"


def test_quem_nao_e_seguido_responde_nao_sei() -> None:
    fabrica, relogio = _Fabrica(), _Relogio()
    with _medidor(fabrica, relogio) as medidor:
        assert medidor.captando_em("ninguem") is None
        assert medidor.captando() == {}


def test_ninguem_ouvindo_nao_abre_processo_nenhum() -> None:
    """O degrau menor, e ele é o desenho: só se abre o que `seguir` recebe."""
    fabrica, relogio = _Fabrica(), _Relogio()
    with _medidor(fabrica, relogio) as medidor:
        medidor.seguir({})
        medidor.bombear(timeout_s=0.0)
        medidor.bombear(timeout_s=0.0)
        assert fabrica.pedidos == []


def test_quem_sai_da_lista_e_fechado_na_mesma_volta() -> None:
    """A captura não pode sobreviver ao ouvinte: ela segura o isócrono USB e o
    microfone do controle acordados, e prende o nó em RUNNING para a PEÇA A.
    """
    fabrica, relogio = _Fabrica(), _Relogio()
    with _medidor(fabrica, relogio) as medidor:
        medidor.seguir({"aaa": "alsa_input.exemplo"})
        medidor.bombear(timeout_s=0.0)
        assert len(fabrica.abertos) == 1
        assert fabrica.abertos[0].vivo()

        medidor.seguir({})
        medidor.bombear(timeout_s=0.0)
        assert fabrica.abertos[0].parado
        assert medidor.captando() == {}


def test_trocar_de_fonte_troca_o_fluxo() -> None:
    """O índice/nome da fonte muda quando o aparelho re-pluga."""
    fabrica, relogio = _Fabrica(), _Relogio()
    with _medidor(fabrica, relogio) as medidor:
        medidor.seguir({"aaa": "fonte-1"})
        medidor.bombear(timeout_s=0.0)
        medidor.seguir({"aaa": "fonte-2"})
        medidor.bombear(timeout_s=0.0)
        assert fabrica.abertos[0].parado
        assert [f for f, _ in fabrica.pedidos] == ["fonte-1", "fonte-2"]


def test_a_mesma_fonte_nao_reabre_nem_zera_a_regua() -> None:
    """`seguir` é chamado a cada volta do laço da PEÇA C. Reabrir a cada volta
    faria a luz recomeçar do escuro para sempre.
    """
    fabrica, relogio = _Fabrica(), _Relogio()
    with _medidor(fabrica, relogio) as medidor:
        medidor.seguir({"aaa": "alsa_input.exemplo"})
        medidor.bombear(timeout_s=0.0)
        _escrever_ate_acender(fabrica.abertos[0], medidor, relogio)
        assert medidor.captando() == {"aaa": True}

        for _ in range(5):
            medidor.seguir({"aaa": "alsa_input.exemplo"})
            medidor.bombear(timeout_s=0.0)
        assert len(fabrica.abertos) == 1
        assert medidor.captando() == {"aaa": True}


def test_o_fluxo_que_morre_volta_a_nao_sei() -> None:
    """`parec` morto é ausência de medição, não medição de silêncio."""
    fabrica, relogio = _Fabrica(), _Relogio()
    with _medidor(fabrica, relogio) as medidor:
        medidor.seguir({"aaa": "alsa_input.exemplo"})
        medidor.bombear(timeout_s=0.0)
        _escrever_ate_acender(fabrica.abertos[0], medidor, relogio)
        assert medidor.captando() == {"aaa": True}

        fabrica.abertos[0].fechar_escrita()
        relogio.anda(PASSO_S)
        medidor.bombear(timeout_s=0.2)
        assert medidor.captando() == {"aaa": None}


def test_o_fluxo_vivo_que_emudece_volta_a_nao_sei() -> None:
    """Um `parec` pendurado responderia `False` com toda a confiança do mundo."""
    fabrica, relogio = _Fabrica(), _Relogio()
    with _medidor(fabrica, relogio) as medidor:
        medidor.seguir({"aaa": "alsa_input.exemplo"})
        medidor.bombear(timeout_s=0.0)
        _escrever_ate_acender(fabrica.abertos[0], medidor, relogio)
        assert medidor.captando() == {"aaa": True}

        relogio.anda(MUDEZ_S + 0.5)
        assert medidor.captando() == {"aaa": None}


def test_o_fluxo_que_emudece_e_fechado_e_solta_o_microfone_dela() -> None:
    """Responder `None` não basta: o `parec` mudo continua com o microfone
    DELA aberto e a fonte presa em RUNNING.

    Este é o vazamento medido de 03/09 às 00h36 entrando por outra porta — lá
    o `parec` ficou 39 minutos órfão segurando a fonte do DualSense. O cano
    cobre a morte do pai; só este recolhimento cobre o filho vivo e mudo.

    MORDE: apague o ramo `elif (agora - canal.ultimo_dado) >= self._mudez_s`
    de `NivelDoMicrofone._reconciliar` e o fluxo fica de pé para sempre —
    `parado` continua False e o microfone dela nunca é solto.
    """
    fabrica, relogio = _Fabrica(), _Relogio()
    with _medidor(fabrica, relogio) as medidor:
        medidor.seguir({"aaa": "alsa_input.exemplo"})
        medidor.bombear(timeout_s=0.0)
        _escrever_ate_acender(fabrica.abertos[0], medidor, relogio)
        assert medidor.captando() == {"aaa": True}
        assert not fabrica.abertos[0].parado

        relogio.anda(MUDEZ_S + 0.5)
        medidor.bombear(timeout_s=0.0)
        assert fabrica.abertos[0].parado, (
            "o `parec` mudo ficou de pé com o microfone dela aberto"
        )
        assert medidor.captando() == {"aaa": None}


def test_o_fluxo_recolhido_por_mudez_nao_reabre_em_rajada() -> None:
    """Reabrir logo faria o nó da fonte piscar entre RUNNING e SUSPENDED — e é
    esse grafo que a PEÇA A lê para contar ouvintes.
    """
    fabrica, relogio = _Fabrica(), _Relogio()
    with _medidor(fabrica, relogio) as medidor:
        medidor.seguir({"aaa": "alsa_input.exemplo"})
        medidor.bombear(timeout_s=0.0)
        relogio.anda(MUDEZ_S + 0.5)
        medidor.bombear(timeout_s=0.0)
        assert len(fabrica.abertos) == 1

        for _ in range(20):  # 0,8 s de laço
            relogio.anda(PASSO_S)
            medidor.bombear(timeout_s=0.0)
        assert len(fabrica.abertos) == 1, (
            f"reabriu {len(fabrica.abertos)} vezes em 0,8 s"
        )


def test_sem_parec_na_maquina_a_resposta_e_nao_sei_sem_rajada() -> None:
    """Ausência é resposta — e não se tenta de novo 25 vezes por segundo."""
    tentativas: list[str] = []

    def sem_parec(fonte: str, uniq: str = "") -> None:
        tentativas.append(fonte)
        return None

    relogio = _Relogio()
    medidor = NivelDoMicrofone(abrir=sem_parec, agora=relogio, automatico=False)
    try:
        medidor.seguir({"aaa": "alsa_input.exemplo"})
        for _ in range(20):
            medidor.bombear(timeout_s=0.0)
            relogio.anda(PASSO_S)
        assert medidor.captando() == {"aaa": None}
        assert len(tentativas) == 1, f"tentou {len(tentativas)} vezes em 0,8 s"
    finally:
        medidor.parar()


def test_quatro_canais_ao_mesmo_tempo_sao_quatro_respostas() -> None:
    """A mesa é de QUATRO, e a luz de cada controle fala DAQUELE microfone."""
    fabrica, relogio = _Fabrica(), _Relogio()
    uniqs = ["aaa", "bbb", "ccc", "ddd"]
    with _medidor(fabrica, relogio) as medidor:
        medidor.seguir({u: f"fonte-{u}" for u in uniqs})
        medidor.bombear(timeout_s=0.0)
        assert len(fabrica.abertos) == 4

        _alimentar(
            medidor,
            relogio,
            {0: 0.40, 2: 0.45, 1: PISO_MEDIDO_P50},
            fabrica,
        )
        assert medidor.captando() == {
            "aaa": True,
            "bbb": False,
            "ccc": True,
            "ddd": None,
        }


def test_parar_e_idempotente_e_fecha_tudo() -> None:
    fabrica, relogio = _Fabrica(), _Relogio()
    medidor = _medidor(fabrica, relogio)
    medidor.seguir({"aaa": "alsa_input.exemplo"})
    medidor.bombear(timeout_s=0.0)
    medidor.parar()
    medidor.parar()
    assert fabrica.abertos[0].parado
    assert medidor.captando() == {}


@pytest.mark.parametrize(
    ("nome", "valor"),
    [
        ("TAXA_HZ", TAXA_HZ),
        ("LIMIAR_ENTRA", LIMIAR_ENTRA),
        ("LIMIAR_SAI", LIMIAR_SAI),
        ("SEGURA_S", SEGURA_S),
        ("ENTRA_S", ENTRA_S),
    ],
)
def test_os_numeros_medidos_estao_na_faixa_que_a_medicao_deixou(
    nome: str, valor: float
) -> None:
    """Guarda de faixa, não de valor: quem ajustar na bancada com ela tem
    espaço, mas não pode cair abaixo do piso de silêncio medido nem subir a
    ponto de a fala não acender.
    """
    faixas = {
        "TAXA_HZ": (10, 50),
        # O piso PROPRIAMENTE DITO é o p99; o p100 é impulso, e quem o para é
        # o degrau de DURAÇÃO, não o de amplitude.
        "LIMIAR_ENTRA": (PISO_MEDIDO_P99 * 2.0, 0.2),
        "LIMIAR_SAI": (PISO_MEDIDO_P99 * 1.2, LIMIAR_ENTRA),
        "SEGURA_S": (0.25, 2.0),
        # Abaixo de 80 ms o impulso de uma amostra volta a passar (medido);
        # acima de 240 ms a sílaba curta deixa de acender (modelado).
        "ENTRA_S": (0.08, 0.24),
    }
    baixo, alto = faixas[nome]
    assert baixo <= valor <= alto, f"{nome}={valor} saiu da faixa medida"
