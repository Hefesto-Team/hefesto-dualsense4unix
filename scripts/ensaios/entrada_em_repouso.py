#!/usr/bin/env python3
"""entrada_em_repouso.py — o que o controle PARADO diz, no fio e no vpad.

A PERGUNTA QUE ELE RESPONDE
----------------------------
*Com ninguém tocando em nada, o que sai do corpo do report de ENTRADA — em cada
transporte, em cada unidade, e no vpad que o produto publica?*

Três perguntas menores, todas na MESMA janela de leitura, que é o desenho da
mesa 2+2 (medir cabo hoje e rádio amanhã não responde nada):

1. **A deriva de repouso.** Um analógico parado não devolve um número: devolve
   um centro deslocado da unidade e um chiado de 1 LSB em volta dele. Quanto?
2. **De quem é a deriva — do APARELHO, do TRANSPORTE, ou do PRODUTO?** O físico
   e o vpad são lidos lado a lado, pelo mesmo `read()`, na mesma janela. Se o
   vpad repetir o chiado do físico byte a byte, o produto está INOCENTADO e não
   há zona morta a caçar no caminho do input.
3. **O corpo do cabo e o corpo do rádio são o mesmo corpo?** Offset a offset,
   quais bytes se mexem em cada braço. Se forem os mesmos, código que trate os
   dois transportes de forma diferente na ENTRADA é podável.

POR QUE ISTO NÃO PEDE A MÃO DELA (Lei 2)
-----------------------------------------
Nenhum degrau depende de olho, ouvido ou cronômetro humano — pelo contrário: o
ensaio EXIGE que ninguém toque. O DualSense parado já transmite em intervalo
fixo, e são esses milhares de quadros que a máquina conta. O que precisa de
dedo — *qual bit acende quando se aperta o quadrado* — está no modo
``--apertar``, que é O BLOCO DELA e sai marcado como tal no relatório.

A RÉGUA, DECLARADA — e ela é ABSOLUTA
--------------------------------------
* **Deriva** = número de valores DISTINTOS que um eixo assumiu na janela, e a
  amplitude entre o menor e o maior. Um é UM: `distintos == 1` é repouso morto,
  `distintos > 1` é chiado. Nunca "mais que o outro braço".
* **Centro** = a MODA do eixo na janela, em LSB, e o desvio dela para 128.
* **Fidelidade do vpad** = igualdade EXATA, byte a byte, entre o eixo do físico
  e o eixo do vpad que ele alimenta. Zero de diferença, ou a diferença em LSB.
* **Paridade de envelope** = diferença simétrica de CONJUNTOS (quais offsets se
  mexem; quais botões o evdev declara). Vazia ou não vazia — não há meio termo.

O CORPO, E DE ONDE SAEM OS OFFSETS
-----------------------------------
`docs/protocol/driver-hid-playstation.md` §1.1, que é leitura do fonte desta
máquina. O driver declara **um só** corpo de entrada e o ancora em endereços
diferentes conforme o transporte:

* **cabo**, report `0x01`, 64 B: o corpo começa em `data[1]`;
* **rádio**, report `0x31`, 78 B: o corpo começa em `data[2]`; o `data[1]` é
  pulado pelo driver, sem nome nem comentário, e os 4 últimos bytes são CRC-32.

Ancorar o rádio em `data[1]` — o erro de um byte — produz sticks plausíveis e
errados. Por isso o offset é escolhido pelo ID do report, nunca fixo, e há
teste que morde exatamente essa cura.

OS DOIS CONTROLES, E ELES SÃO POR NÓ
-------------------------------------
**POSITIVO — o fluxo está vivo e eu estou no offset certo.** Dois carimbos
independentes têm de ANDAR em cada nó: (a) o contador de sequência do quadro e
(b) o `sensor_timestamp` de 32 bits em `corpo[27..30]`. Um nó cujo carimbo não
anda está entregando quadro repetido, e dele não sai veredito nenhum. Um
terceiro carimbo, este de OUTRO OBSERVADOR: o `status[0]` em `corpo[52]`
decodificado pela fórmula do driver tem de bater com o que o `sysfs` publica em
`/sys/class/power_supply/ps-controller-battery-*`. Se o meu byte e o sysfs
discordam, quem está errado sou eu.

**NEGATIVO — ninguém tocou em nada.** Na MESMA janela, `corpo[7..10]` (botões e
hat) tem de ficar em `08 00 00 00` e o `status` tem de ficar parado. Se um botão
se mexeu, a janela está contaminada por uma mão e a medida de repouso não vale:
o instrumento diz isso e se recusa a emitir veredito de deriva. É o que separa
"o stick chia" de "alguém encostou na mesa".

O QUE ELE ESCREVE NO APARELHO: **NADA**
----------------------------------------
Nem um byte, em transporte nenhum. `read()` de hidraw pela porta do broker,
`EVIOCGABS`/`EVIOCGBIT` de evdev (que não é grab e não disputa nada), e
arquivos de `/sys`. Nenhuma unit é tocada, nenhum estado do sistema é sujo.

USO
    .venv/bin/python scripts/ensaios/entrada_em_repouso.py
    .venv/bin/python scripts/ensaios/entrada_em_repouso.py --segundos 60
    .venv/bin/python scripts/ensaios/entrada_em_repouso.py --bruto docs/data/ensaios-brutos/
    .venv/bin/python scripts/ensaios/entrada_em_repouso.py --apertar   # BLOCO DELA
"""

from __future__ import annotations

import argparse
import glob
import itertools
import os
import select
import sys
import time
from collections import Counter, defaultdict
from dataclasses import dataclass, field
from datetime import datetime

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

try:
    # No TOPO, e não dentro das funções: a regra da casa é que a PROCEDÊNCIA de
    # cada biblioteca saia impressa antes da primeira medição, e um import
    # preguiçoso faz o cabeçalho mentir "NÃO IMPORTADO" sobre a régua que ele
    # vai usar. "Medir contra a biblioteca errada produz alarme convincente e
    # falso" — e não saber QUAL biblioteca é o mesmo defeito, um passo antes.
    import evdev
except ImportError:  # pragma: no cover - fora do venv do projeto
    evdev = None  # type: ignore[assignment]

from comum import (
    CABO,
    RADIO,
    Aparelho,
    abrir_no_hidraw,
    cabecalho_do_instrumento,
    censo_da_mesa,
    descobrir_aparelhos,
    ler_texto,
    resumo,
    tabela,
)

# ---------------------------------------------------------------------------
# O corpo do report de entrada — driver-hid-playstation.md §1.1
# ---------------------------------------------------------------------------

ID_CABO = 0x01
TAM_CABO = 64
CORPO_CABO = 1

ID_RADIO = 0x31
TAM_RADIO = 78
CORPO_RADIO = 2

#: Tamanho do `struct dualsense_input_report`, amarrado por `static_assert` em
#: `hid-playstation.c:317` a `DS_INPUT_REPORT_USB_SIZE - 1`.
TAM_CORPO = 63

#: Os seis eixos analógicos, no offset do CORPO (não do quadro).
EIXOS: tuple[tuple[str, int], ...] = (
    ("LX", 0),
    ("LY", 1),
    ("RX", 2),
    ("RY", 3),
    ("L2", 4),
    ("R2", 5),
)
#: Só os quatro dos sticks — os gatilhos em repouso são 0 e não têm centro.
STICKS = EIXOS[:4]

SEQ = 6                    #: `seq_number`; o driver não o lê
BOTOES = (7, 8, 9, 10)     #: `buttons[4]`
TIMESTAMP = (27, 28, 29, 30)  #: `sensor_timestamp`, `__le32`, unidade 0,33 us
STATUS = (52, 53, 54)      #: `status[3]` — bateria e jack

#: O valor de `buttons[0]` com nada apertado: nibble baixo = 8 = hat NEUTRO
#: (`DS_BUTTONS0_HAT_SWITCH`), nibble alto = 0 = quadrado/xis/bola/triângulo
#: soltos. Os outros três bytes de botão em zero.
BOTOES_EM_REPOUSO = (0x08, 0x00, 0x00, 0x00)


#: O corpo inteiro, dividido pelos campos do `struct dualsense_input_report`.
#: Ler offset solto engana: o offset 22 se mexer no cabo e não no rádio parece
#: assimetria de transporte e é só o acelerômetro de uma unidade estar mais
#: quieto que o da outra. Nomeando as zonas, a pergunta certa aparece — "o
#: campo X vive nos dois braços?" — e o ruído de silício fica onde deve.
ZONAS: tuple[tuple[str, int, int, bool], ...] = (
    # (nome, primeiro, último, é ruído esperado de silício?)
    ("sticks/gatilhos", 0, 5, True),
    ("seq_number", 6, 6, False),
    ("buttons[4]", 7, 10, False),
    ("reserved[4]", 11, 14, False),
    ("gyro[3]", 15, 20, True),
    ("accel[3]", 21, 26, True),
    ("sensor_timestamp", 27, 30, False),
    ("reserved2", 31, 31, False),
    ("points[2] (toque)", 32, 39, False),
    ("reserved3[12]", 40, 51, False),
    ("status[3]", 52, 54, False),
    ("reserved4[8]", 55, 62, False),
)


class QuadroDesconhecidoError(ValueError):
    """Um quadro que não é report de entrada de DualSense."""


def corpo_do_quadro(quadro: bytes) -> tuple[bytes, int]:
    """O `struct dualsense_input_report` e o offset em que ele começa.

    **A cura que este instrumento não pode perder.** O corpo é o MESMO nos dois
    transportes; o que muda é onde ele é ancorado — `data[1]` no cabo e
    `data[2]` no rádio. Fixar o offset em 1 produz, no rádio, sticks plausíveis
    e errados: o `LX` vira o byte de sequência do envelope, e o resto anda um
    byte. O offset sai do ID do report, que é o próprio protocolo.
    """
    if not quadro:
        raise QuadroDesconhecidoError("quadro vazio")
    if quadro[0] == ID_CABO and len(quadro) >= CORPO_CABO + TAM_CORPO:
        off = CORPO_CABO
    elif quadro[0] == ID_RADIO and len(quadro) >= CORPO_RADIO + TAM_CORPO:
        off = CORPO_RADIO
    else:
        raise QuadroDesconhecidoError(
            f"report 0x{quadro[0]:02x} de {len(quadro)} B não é entrada de DualSense"
        )
    return quadro[off : off + TAM_CORPO], off


def contador_do_quadro(quadro: bytes) -> int:
    """O carimbo que TEM de andar de um quadro para o próximo, por transporte.

    No cabo é o `seq_number` do corpo. No rádio o `seq_number` do corpo fica
    congelado e quem anda é o nibble ALTO do `data[1]` — o byte que o driver
    pula sem nome. São dois lugares diferentes para a mesma função, e é por isso
    que este instrumento não pergunta "o corpo mexeu?" e sim "o carimbo andou?".
    """
    if quadro[0] == ID_RADIO:
        return (quadro[1] >> 4) & 0x0F
    return quadro[CORPO_CABO + SEQ]


def passo_do_contador(quadro: bytes) -> int:
    """De quanto em quanto o contador daquele transporte conta (o módulo)."""
    return 16 if quadro[0] == ID_RADIO else 256


def le32(corpo: bytes, offset: int) -> int:
    return int.from_bytes(corpo[offset : offset + 4], "little")


#: Os cinco estados de carga do `DS_STATUS0_CHARGING`, `hid-playstation.c:1724`.
CARGA = {
    0x0: "Discharging",
    0x1: "Charging",
    0x2: "Full",
    0xA: "fora de faixa (tensão)",
    0xB: "fora de faixa (temperatura)",
    0xF: "erro",
}


def bateria_do_status(status0: int) -> tuple[int | None, str]:
    """(capacidade em %, estado) a partir de `status[0]`, pela conta do driver.

    `nibble * 10 + 5` limitado a 100 para descarregando/carregando; `Full` é
    100 por definição; os estados de erro não publicam capacidade nenhuma, e
    devolver 0 ali seria inventar um número.
    """
    nibble = status0 & 0x0F
    estado = CARGA.get((status0 & 0xF0) >> 4, f"desconhecido 0x{status0 >> 4:x}")
    if estado == "Full":
        return 100, estado
    if estado in ("Discharging", "Charging"):
        return min(nibble * 10 + 5, 100), estado
    return None, estado


# ---------------------------------------------------------------------------
# O que se acumula por nó durante a janela
# ---------------------------------------------------------------------------


@dataclass
class Coleta:
    """Tudo o que um nó entregou na janela — e nada além do que ele entregou."""

    aparelho: Aparelho
    porta: str = ""
    quadros: int = 0
    ids: Counter = field(default_factory=Counter)
    tamanhos: Counter = field(default_factory=Counter)
    eixo: dict[str, Counter] = field(default_factory=lambda: defaultdict(Counter))
    valores_por_offset: dict[int, set[int]] = field(default_factory=lambda: defaultdict(set))
    contador_andou: int = 0
    contador_parado: int = 0
    contador_pulou: int = 0
    timestamp_andou: int = 0
    timestamp_parado: int = 0
    primeiro: bytes = b""
    ultimo: bytes = b""
    erro: str = ""

    _ultimo_contador: int | None = None
    _ultimo_ts: int | None = None

    def engole(self, quadro: bytes) -> None:
        corpo, _off = corpo_do_quadro(quadro)
        self.quadros += 1
        self.ids[quadro[0]] += 1
        self.tamanhos[len(quadro)] += 1
        if not self.primeiro:
            self.primeiro = quadro
        self.ultimo = quadro
        for nome, i in EIXOS:
            self.eixo[nome][corpo[i]] += 1
        for i in range(TAM_CORPO):
            self.valores_por_offset[i].add(corpo[i])

        atual = contador_do_quadro(quadro)
        if self._ultimo_contador is not None:
            passo = (atual - self._ultimo_contador) % passo_do_contador(quadro)
            if passo == 0:
                self.contador_parado += 1
            elif passo == 1:
                self.contador_andou += 1
            else:
                self.contador_pulou += 1
        self._ultimo_contador = atual

        ts = le32(corpo, TIMESTAMP[0])
        if self._ultimo_ts is not None:
            if ts == self._ultimo_ts:
                self.timestamp_parado += 1
            else:
                self.timestamp_andou += 1
        self._ultimo_ts = ts

    # -- as leituras que o relatório usa ------------------------------------

    @property
    def transporte(self) -> str:
        return self.aparelho.transporte

    @property
    def offsets_moveis(self) -> set[int]:
        return {i for i, vs in self.valores_por_offset.items() if len(vs) > 1}

    def centro(self, nome: str) -> int | None:
        c = self.eixo.get(nome)
        return c.most_common(1)[0][0] if c else None

    def distintos(self, nome: str) -> int:
        return len(self.eixo.get(nome, ()))

    def amplitude(self, nome: str) -> int:
        c = self.eixo.get(nome)
        return (max(c) - min(c)) if c else 0

    @property
    def assinatura(self) -> tuple[int | None, ...]:
        """O centro dos quatro sticks. É o que casa físico com vpad.

        Nada de MAC, nada de ordem de conexão, nada de número de jogador: só o
        que o silício daquela unidade entrega parado. É uma propriedade do
        APARELHO, e por isso vale em qualquer PC.
        """
        return tuple(self.centro(nome) for nome, _ in STICKS)

    @property
    def botoes_em_repouso(self) -> bool:
        for esperado, i in zip(BOTOES_EM_REPOUSO, BOTOES, strict=True):
            if self.valores_por_offset.get(i, {esperado}) != {esperado}:
                return False
        return True

    @property
    def status_parado(self) -> bool:
        return all(len(self.valores_por_offset.get(i, set())) <= 1 for i in STATUS)

    @property
    def fluxo_vivo(self) -> bool:
        return self.contador_andou > 0 and self.timestamp_andou > 0

    @property
    def bateria(self) -> tuple[int | None, str]:
        vs = self.valores_por_offset.get(STATUS[0], set())
        if len(vs) != 1:
            return None, "instável na janela"
        return bateria_do_status(next(iter(vs)))


# ---------------------------------------------------------------------------
# O casamento físico <-> vpad, sem MAC e sem ordem
# ---------------------------------------------------------------------------


@dataclass
class Casamento:
    vpad: str
    fisico: str
    discordancias: tuple[str, ...]
    unico: bool


def casar_por_assinatura(
    fisicos: dict[str, tuple[int | None, ...]],
    vpads: dict[str, tuple[int | None, ...]],
) -> tuple[list[Casamento], str]:
    """Casa cada vpad ao físico que o alimenta pelo CENTRO DOS STICKS.

    O método é uma atribuição ótima sobre todas as permutações (são no máximo
    4! = 24): o custo de um par é quantos dos quatro eixos discordam. Ele NÃO
    olha MAC, nome, número de jogador nem ordem de enumeração — dois nós com a
    mesma assinatura são indistinguíveis para ele, e é assim que tem de ser.

    **Só devolve casamento se o ótimo for ÚNICO.** Empate vira `ambíguo`, não um
    palpite: num mapa que a casa usa para decidir cura, um par errado é pior que
    um par ausente. Ambiguidade é o preço honesto de duas unidades com o mesmo
    centro, e o relatório diz qual eixo faltou para desempatar.
    """
    nomes_v = sorted(vpads)
    nomes_f = sorted(fisicos)
    if not nomes_v or not nomes_f or len(nomes_v) > len(nomes_f):
        return [], "não dá para casar: a mesa não tem um físico para cada vpad"

    def custo(v: str, f: str) -> tuple[int, tuple[str, ...]]:
        discorda = tuple(
            nome
            for (nome, _), a, b in zip(STICKS, vpads[v], fisicos[f], strict=True)
            if a != b
        )
        return len(discorda), discorda

    melhores: list[tuple[int, tuple[str, ...]]] = []
    for combo in itertools.permutations(nomes_f, len(nomes_v)):
        total = sum(custo(v, f)[0] for v, f in zip(nomes_v, combo, strict=True))
        melhores.append((total, combo))
    melhores.sort(key=lambda x: x[0])
    otimo = melhores[0][0]
    empatados = [c for t, c in melhores if t == otimo]
    unico = len(empatados) == 1

    pares = [
        Casamento(v, f, custo(v, f)[1], unico)
        for v, f in zip(nomes_v, empatados[0], strict=True)
    ]
    if unico:
        nota = f"ótimo ÚNICO (custo {otimo} eixo(s) de discordância no total)"
    else:
        nota = (
            f"AMBÍGUO: {len(empatados)} atribuições empatam no custo {otimo} — "
            "há unidades com o mesmo centro de stick, e o centro sozinho não decide"
        )
    return pares, nota


def casar_por_bateria(
    fisicos: dict[str, tuple[int | None, str]],
    vpads: dict[str, tuple[int | None, str]],
) -> dict[str, str]:
    """O MESMO casamento, por um canal que não tem nada a ver com stick.

    Por que existe: um casamento feito com uma régua sozinha é indistinguível
    de uma coincidência dela. A bateria é observação de outro campo do report
    (`status[0]`), de outra grandeza física e de outro subsistema — e o kernel
    ainda a publica em `/sys` por conta própria. Quando as duas réguas
    concordam, o par é dado; quando discordam, alguma das duas mente e o
    relatório diz isso em vez de escolher a que agrada.

    Só casa quem tem capacidade ÚNICA na mesa: dois controles a 100% não se
    separam por aqui, e inventar um desempate seria transformar a régua de
    confirmação em palpite. Quem empata sai de fora, declaradamente.
    """
    por_cap: dict[tuple[int | None, str], list[str]] = {}
    for h, chave in fisicos.items():
        por_cap.setdefault(chave, []).append(h)
    fora: dict[str, str] = {}
    for v, chave in vpads.items():
        # O vpad republica `Full` como `Charging` (medido em 15/08/2026), então
        # a capacidade é o que compara; o estado entra só como contexto.
        candidatos = [
            h for (cap, _est), hs in por_cap.items() if cap == chave[0] for h in hs
        ]
        if len(candidatos) == 1:
            fora[v] = candidatos[0]
    return fora


# ---------------------------------------------------------------------------
# Leitura
# ---------------------------------------------------------------------------


def bateria_do_sysfs() -> dict[str, tuple[str, str]]:
    """O que o KERNEL publica de bateria, por MAC. O observador independente."""
    fora: dict[str, tuple[str, str]] = {}
    for caminho in sorted(glob.glob("/sys/class/power_supply/ps-controller-battery-*")):
        mac = os.path.basename(caminho).removeprefix("ps-controller-battery-")
        fora[mac.lower()] = (
            ler_texto(os.path.join(caminho, "capacity")).strip(),
            ler_texto(os.path.join(caminho, "status")).strip(),
        )
    return fora


def capacidades_do_evdev(caminho: str) -> tuple[tuple[int, ...], tuple[int, ...]] | None:
    """(EV_KEY, EV_ABS) declarados pelo nó. Não é grab e não disputa nada."""
    if evdev is None:
        return None
    try:
        dev = evdev.InputDevice(caminho)
    except OSError:
        return None
    try:
        caps = dev.capabilities()
        return (
            tuple(sorted(caps.get(evdev.ecodes.EV_KEY, []))),
            tuple(sorted(a[0] for a in caps.get(evdev.ecodes.EV_ABS, []))),
        )
    finally:
        dev.close()


def evdev_absinfo(caminho: str) -> dict[str, int]:
    """O valor ATUAL de cada eixo, direto do kernel — a SEGUNDA régua.

    Não é enfeite: é o controle positivo do meu offset. O `EVIOCGABS` devolve o
    que o `hid_playstation` decodificou por conta própria, sem passar por
    nenhuma conta minha. Se o centro que eu tiro de `corpo[0..3]` bater com o
    que o kernel publica, meu offset está certo por um observador independente;
    se não bater, o réu sou eu, e o número da tabela de deriva não vale nada.

    O grab do co-op **não atrapalha**: `EVIOCGABS` lê estado, não consome
    evento, e nós de físico grabado respondem normalmente.
    """
    if evdev is None:
        return {}
    try:
        dev = evdev.InputDevice(caminho)
    except OSError:
        return {}
    try:
        caps = dict(dev.capabilities().get(evdev.ecodes.EV_ABS, []))
        nomes = {
            "LX": evdev.ecodes.ABS_X,
            "LY": evdev.ecodes.ABS_Y,
            "RX": evdev.ecodes.ABS_RX,
            "RY": evdev.ecodes.ABS_RY,
        }
        return {n: caps[c].value for n, c in nomes.items() if c in caps}
    finally:
        dev.close()


def coletar(aparelhos: list[Aparelho], segundos: float) -> dict[str, Coleta]:
    """Lê TODOS os nós na MESMA janela. Não há outra forma de comparar braços."""
    coletas = {a.hidraw: Coleta(a) for a in aparelhos}
    abertos = []
    por_fd: dict[int, Coleta] = {}
    for ap in aparelhos:
        try:
            no = abrir_no_hidraw(ap.caminho_hidraw, escrita=False)
        except OSError as erro:
            coletas[ap.hidraw].erro = f"não abriu: {erro}"
            continue
        abertos.append(no)
        coletas[ap.hidraw].porta = no.porta
        por_fd[no.fd] = coletas[ap.hidraw]
    try:
        fim = time.monotonic() + segundos
        while time.monotonic() < fim:
            prontos, _, _ = select.select(list(por_fd), [], [], 0.2)
            for fd in prontos:
                try:
                    quadro = os.read(fd, 512)
                except OSError as erro:
                    por_fd[fd].erro = f"leitura falhou: {erro}"
                    continue
                try:
                    por_fd[fd].engole(quadro)
                except QuadroDesconhecidoError as erro:
                    por_fd[fd].erro = str(erro)
    finally:
        for no in abertos:
            no.fechar()
    return coletas


# ---------------------------------------------------------------------------
# Relatório
# ---------------------------------------------------------------------------


def bloco_controles(
    coletas: dict[str, Coleta],
    sysfs: dict[str, tuple[str, str]],
    do_kernel_abs: dict[str, dict[str, int]],
) -> tuple[str, list[str]]:
    linhas = []
    discordam = []
    for h, c in coletas.items():
        cap, estado = c.bateria
        sys_diz = sysfs.get(c.aparelho.mac.lower(), ("?", "?"))
        bate = "—"
        if cap is not None and sys_diz[0].isdigit():
            bate = "sim" if str(cap) == sys_diz[0] else "NÃO"
            if bate == "NÃO":
                discordam.append(
                    f"{c.aparelho.apelido}: o byte diz {cap}% e o sysfs diz {sys_diz[0]}%"
                )
        # A segunda régua do OFFSET: o centro que eu tirei do corpo contra o que
        # o kernel decodificou sozinho.
        meu = {n: c.centro(n) for n, _ in STICKS}
        dele = do_kernel_abs.get(h, {})
        if dele:
            iguais = sum(1 for n in meu if meu[n] == dele.get(n))
            offset_ok = f"{iguais}/{len(meu)}"
            if iguais != len(meu):
                discordam.append(
                    f"{c.aparelho.apelido}: meu centro {meu} contra o EVIOCGABS {dele}"
                )
        else:
            offset_ok = "—"
        linhas.append(
            [
                c.aparelho.apelido,
                c.transporte,
                str(c.quadros),
                f"{c.contador_andou}/{c.contador_parado}/{c.contador_pulou}",
                "anda" if c.timestamp_andou else "PARADO",
                offset_ok,
                f"{cap}% {estado}" if cap is not None else estado,
                f"{sys_diz[0]}% {sys_diz[1]}",
                bate,
                "limpa" if (c.botoes_em_repouso and c.status_parado) else "CONTAMINADA",
            ]
        )
    return (
        tabela(
            [
                "quem",
                "transporte",
                "quadros",
                "contador +1/0/pulo",
                "timestamp",
                "meu centro = EVIOCGABS",
                "bateria do byte",
                "bateria do sysfs",
                "bate?",
                "janela",
            ],
            linhas,
        ),
        discordam,
    )


def bloco_deriva(coletas: dict[str, Coleta]) -> str:
    linhas = []
    for c in coletas.values():
        for nome, _ in STICKS:
            centro = c.centro(nome)
            if centro is None:
                continue
            vistos = sorted(c.eixo[nome])
            linhas.append(
                [
                    c.aparelho.apelido,
                    c.transporte,
                    nome,
                    str(centro),
                    f"{centro - 128:+d}",
                    str(c.distintos(nome)),
                    str(c.amplitude(nome)),
                    " ".join(str(v) for v in vistos),
                ]
            )
    return tabela(
        ["quem", "transporte", "eixo", "centro", "desvio", "distintos", "amplitude", "valores"],
        linhas,
    )


def bloco_fidelidade(
    coletas: dict[str, Coleta], pares: list[Casamento]
) -> tuple[str, list[str]]:
    """O produto repete o byte do aparelho, ou muda?

    O veredito é do CENTRO, e não do conjunto de valores vistos — de propósito.
    O vpad emite a ~160 Hz e o físico do cabo a 250 Hz: um valor raro que
    aparece 4 vezes em 5000 quadros do físico pode simplesmente não cair na
    amostra menor do vpad. Julgar por conjunto chamaria isso de infidelidade, e
    seria alarme convincente e falso — o mesmo modo de falha que já custou três
    medições nesta casa. O conjunto continua impresso, como contexto, com a
    diferença marcada como `só amostragem` quando o do vpad cabe dentro do do
    físico.
    """
    linhas = []
    notas = []
    for par in pares:
        v, f = coletas[par.vpad], coletas[par.fisico]
        for nome, _ in STICKS:
            cv, cf = v.centro(nome), f.centro(nome)
            vistos_v, vistos_f = set(v.eixo[nome]), set(f.eixo[nome])
            if cv != cf:
                veredito = "O PRODUTO MUDA"
            elif vistos_v == vistos_f:
                veredito = "idêntico"
            elif vistos_v <= vistos_f:
                veredito = "idêntico (resto é só amostragem)"
            else:
                veredito = "o vpad INVENTA valor"
            linhas.append(
                [
                    f"{v.aparelho.apelido} <- {f.aparelho.apelido}",
                    nome,
                    str(cf),
                    str(cv),
                    "0" if cv == cf else f"{(cv or 0) - (cf or 0):+d}",
                    " ".join(str(x) for x in sorted(vistos_f)),
                    " ".join(str(x) for x in sorted(vistos_v)),
                    veredito,
                ]
            )
            if cv != cf:
                notas.append(
                    f"{v.aparelho.apelido} publica {nome}={cv} onde "
                    f"{f.aparelho.apelido} entrega {cf} — {abs((cv or 0) - (cf or 0))} LSB "
                    f"de erro, e o eixo do físico teve {f.distintos(nome)} valor(es) "
                    f"distinto(s) na janela (nenhuma transição = nenhum evento EV_ABS)"
                )
    return (
        tabela(
            [
                "par",
                "eixo",
                "físico",
                "vpad",
                "erro",
                "valores no físico",
                "valores no vpad",
                "veredito",
            ],
            linhas,
        ),
        notas,
    )


def bloco_envelope(coletas: dict[str, Coleta]) -> tuple[str, list[str]]:
    """O corpo do cabo e o corpo do rádio são o mesmo corpo?

    A conta que decide é por ZONA e por BRAÇO INTEIRO: um campo só conta como
    assimetria de transporte se ele se mexe em TODAS as unidades de um braço e
    em NENHUMA do outro. Um offset que se mexe em uma unidade e não na irmã do
    mesmo braço é ruído daquele silício, e chamá-lo de assimetria seria
    exatamente o confundimento braço/unidade que a Lei 4 existe para matar.

    As zonas de sensor e de stick saem marcadas como ruído esperado: giro,
    acelerômetro e analógico VÃO variar por unidade, e a variação deles não
    fala do transporte.
    """
    fisicos = [c for c in coletas.values() if not c.aparelho.e_vpad and c.quadros]
    dos_vpads = [c for c in coletas.values() if c.aparelho.e_vpad and c.quadros]
    do_cabo = [c for c in fisicos if c.transporte == CABO]
    do_radio = [c for c in fisicos if c.transporte == RADIO]

    def quantos(grupo: list[Coleta], primeiro: int, ultimo: int) -> str:
        vivos = sum(
            1 for c in grupo if any(len(c.valores_por_offset.get(i, set())) > 1
                                    for i in range(primeiro, ultimo + 1))
        )
        return f"{vivos}/{len(grupo)}" if grupo else "—"

    linhas = []
    achados = []
    for nome, primeiro, ultimo, ruido in ZONAS:
        c_cabo, c_radio, c_vpad = (
            quantos(do_cabo, primeiro, ultimo),
            quantos(do_radio, primeiro, ultimo),
            quantos(dos_vpads, primeiro, ultimo),
        )
        veredito = "ruído de silício (esperado variar)" if ruido else ""
        if not ruido and do_cabo and do_radio:
            todos_cabo = c_cabo == f"{len(do_cabo)}/{len(do_cabo)}"
            nenhum_cabo = c_cabo == f"0/{len(do_cabo)}"
            todos_radio = c_radio == f"{len(do_radio)}/{len(do_radio)}"
            nenhum_radio = c_radio == f"0/{len(do_radio)}"
            if todos_cabo and nenhum_radio:
                veredito = "VIVO SÓ NO CABO"
                achados.append(
                    f"`{nome}` (corpo[{primeiro}..{ultimo}]) se mexe em TODAS as "
                    f"{len(do_cabo)} unidades do cabo e em NENHUMA das {len(do_radio)} do rádio"
                )
            elif todos_radio and nenhum_cabo:
                veredito = "VIVO SÓ NO RÁDIO"
                achados.append(
                    f"`{nome}` (corpo[{primeiro}..{ultimo}]) se mexe em TODAS as "
                    f"{len(do_radio)} unidades do rádio e em NENHUMA das {len(do_cabo)} do cabo"
                )
            elif todos_cabo and todos_radio:
                veredito = "vivo nos DOIS braços"
            elif nenhum_cabo and nenhum_radio:
                veredito = "parado nos dois (nada a comparar em repouso)"
            else:
                veredito = "varia por UNIDADE, não por braço"
        linhas.append([nome, f"{primeiro}..{ultimo}", c_cabo, c_radio, c_vpad, veredito])

    if not (do_cabo and do_radio):
        achados.append(
            "SÓ UM TRANSPORTE na mesa — nenhuma coluna cabo-x-rádio acima compara "
            "coisa alguma, e nenhum veredito de assimetria de envelope sai desta corrida"
        )

    # A outra pergunta da mesma tabela: o vpad é uma cópia fiel do envelope?
    for nome, primeiro, ultimo, ruido in ZONAS:
        if ruido or not fisicos or not dos_vpads:
            continue
        vivo_em_todo_fisico = all(
            any(len(c.valores_por_offset.get(i, set())) > 1 for i in range(primeiro, ultimo + 1))
            for c in fisicos
        )
        morto_em_todo_vpad = all(
            all(len(c.valores_por_offset.get(i, set())) <= 1 for i in range(primeiro, ultimo + 1))
            for c in dos_vpads
        )
        if vivo_em_todo_fisico and morto_em_todo_vpad:
            bracos = (
                "nos dois braços"
                if (do_cabo and do_radio)
                else f"todos em {CABO if do_cabo else RADIO}"
            )
            achados.append(
                f"`{nome}` (corpo[{primeiro}..{ultimo}]) está VIVO nos {len(fisicos)} "
                f"aparelhos, {bracos}, e MORTO nos {len(dos_vpads)} vpads — "
                "o produto não reproduz este campo"
            )
    return (
        tabela(
            [
                "zona do corpo",
                "offsets",
                "vivo no cabo",
                "vivo no rádio",
                "vivo no vpad",
                "leitura",
            ],
            linhas,
        ),
        achados,
    )


def bloco_capacidades(coletas: dict[str, Coleta]) -> tuple[str, bool]:
    linhas = []
    conjuntos = {}
    for c in coletas.values():
        caminho = c.aparelho.dir_device
        evdev_no = evdev_principal(caminho)
        caps = capacidades_do_evdev(evdev_no) if evdev_no else None
        if caps is None:
            linhas.append([c.aparelho.apelido, c.transporte, evdev_no or "—", "?", "?", "não li"])
            continue
        conjuntos[c.aparelho.apelido] = caps
        linhas.append(
            [c.aparelho.apelido, c.transporte, evdev_no, str(len(caps[0])), str(len(caps[1])), ""]
        )
    iguais = len(set(conjuntos.values())) <= 1
    for linha in linhas:
        if linha[5] == "":
            linha[5] = "idêntico aos demais" if iguais else "DIVERGE"
    return (
        tabela(["quem", "transporte", "nó evdev", "EV_KEY", "EV_ABS", "conjunto"], linhas),
        iguais,
    )


def evdev_principal(dir_device: str) -> str:
    """O `/dev/input/eventN` de gamepad do mesmo device HID, ou ""."""
    for caminho in sorted(glob.glob(os.path.join(dir_device, "input", "input*", "event*"))):
        nome = os.path.basename(caminho)
        if not nome.startswith("event"):
            continue
        pai = os.path.dirname(caminho)
        rotulo = ler_texto(os.path.join(pai, "name")).strip()
        if "Touchpad" in rotulo or "Motion Sensors" in rotulo:
            continue
        return f"/dev/input/{nome}"
    return ""


# ---------------------------------------------------------------------------
# O BLOCO DELA — o único degrau que precisa de dedo
# ---------------------------------------------------------------------------

TEXTO_APERTAR = """
O BLOCO DELA — e é o único pedaço deste ensaio que precisa de dedo (Lei 2)
==========================================================================
O que a máquina NÃO consegue medir sozinha é QUAL BIT acende quando se aperta
um botão. Tudo o mais deste instrumento já foi medido com a mesa parada.

O que fazer, com um controle do CABO e um do RÁDIO na mesa:

    .venv/bin/python scripts/ensaios/entrada_em_repouso.py --apertar --segundos 90

e, enquanto ele conta, apertar UM DE CADA VEZ, primeiro no controle do cabo e
depois no do rádio, esperando o instrumento imprimir a linha antes de ir para o
próximo:

    quadrado · xis · bola · triângulo · L1 · R1 · L2 · R2 · Create · Options
    L3 · R3 · PS · touchpad (clique) · mudo do microfone
    D-pad: cima · baixo · esquerda · direita

O instrumento imprime, para cada aperto, o OFFSET do corpo e a MÁSCARA que
mudou. No fim ele compara as duas listas. Se forem iguais, está MEDIDO que o
cabo e o rádio carregam os mesmos botões nos mesmos bits — e todo código que
trate os dois transportes de forma diferente na entrada é podável.
"""


# ---------------------------------------------------------------------------
# Principal
# ---------------------------------------------------------------------------


def monta_relatorio(coletas: dict[str, Coleta], segundos: float) -> tuple[str, str]:
    """(relatório inteiro, linha de resumo)."""
    fisicos = {h: c for h, c in coletas.items() if not c.aparelho.e_vpad and c.quadros}
    dos_vpads = {h: c for h, c in coletas.items() if c.aparelho.e_vpad and c.quadros}
    partes: list[str] = []

    abs_do_kernel = {
        h: evdev_absinfo(evdev_principal(c.aparelho.dir_device)) for h, c in coletas.items()
    }
    partes.append("")
    partes.append("(1) OS CONTROLES — positivo: o fluxo anda, meu offset bate com o EVIOCGABS,")
    partes.append("    e o byte de bateria bate com o sysfs. Negativo: ninguém tocou em nada.")
    tab_ctrl, discordam = bloco_controles(coletas, bateria_do_sysfs(), abs_do_kernel)
    partes.append(tab_ctrl)
    for d in discordam:
        partes.append(f"  >> RÉGUA DISCORDA — {d}")

    mortos = [c.aparelho.apelido for c in coletas.values() if c.quadros and not c.fluxo_vivo]
    sujos = [
        c.aparelho.apelido
        for c in coletas.values()
        if c.quadros and not (c.botoes_em_repouso and c.status_parado)
    ]
    if mortos:
        partes.append(
            f"  >> CONTROLE POSITIVO REPROVOU em {', '.join(mortos)}: o carimbo não anda. "
            "Nenhum veredito de deriva sai desses nós."
        )
    if sujos:
        partes.append(
            f"  >> CONTROLE NEGATIVO REPROVOU em {', '.join(sujos)}: botão ou status se "
            "mexeu na janela. Houve mão na mesa — a medida de repouso NÃO vale."
        )

    partes.append("")
    partes.append("(2) A DERIVA DE REPOUSO — centro e chiado de cada stick, com ninguém tocando")
    partes.append(bloco_deriva(coletas))

    partes.append("")
    partes.append("(3) QUEM ALIMENTA QUEM — sem MAC, sem nome, sem ordem de conexão")
    pares, nota = casar_por_assinatura(
        {h: c.assinatura for h, c in fisicos.items()},
        {h: c.assinatura for h, c in dos_vpads.items()},
    )
    por_bat = casar_por_bateria(
        {h: c.bateria for h, c in fisicos.items()},
        {h: c.bateria for h, c in dos_vpads.items()},
    )
    partes.append(f"  régua 1 — centro dos sticks: {nota}")
    partes.append(
        f"  régua 2 — capacidade da bateria (outro campo, outro subsistema): "
        f"{len(por_bat)} de {len(dos_vpads)} vpad(s) com capacidade única na mesa"
    )
    concordam = 0
    if pares:
        linhas = []
        for pr in pares:
            outra = por_bat.get(pr.vpad)
            if outra is None:
                veredito = "só a régua dos sticks (bateria empatada na mesa)"
            elif outra == pr.fisico:
                veredito = "AS DUAS RÉGUAS CONCORDAM"
                concordam += 1
            else:
                veredito = f"RÉGUAS DISCORDAM — a bateria diz {coletas[outra].aparelho.apelido}"
            linhas.append(
                [
                    coletas[pr.vpad].aparelho.apelido,
                    coletas[pr.fisico].aparelho.apelido,
                    ", ".join(pr.discordancias) or "nenhum",
                    "sim" if pr.unico else "NÃO",
                    veredito,
                ]
            )
        partes.append(
            tabela(
                [
                    "vpad",
                    "físico que o alimenta",
                    "eixos que discordam",
                    "ótimo único?",
                    "confirmação",
                ],
                linhas,
            )
        )
        partes.append(
            "  Nada aqui olha MAC, número de jogador ou ordem de enumeração: o casamento"
        )
        partes.append(
            "  sai de propriedades FÍSICAS da unidade, que ela leva para qualquer PC."
        )
        partes.append("")
        partes.append("(4) FIDELIDADE DO VPAD — o produto repete o byte do aparelho, ou muda?")
        tab, notas = bloco_fidelidade(coletas, pares)
        partes.append(tab)
        for n in notas:
            partes.append(f"  >> {n}")

    partes.append("")
    partes.append("(5) O ENVELOPE — o corpo do cabo e o corpo do rádio são o mesmo corpo?")
    tab_env, achados = bloco_envelope(coletas)
    partes.append(tab_env)
    for a in achados:
        partes.append(f"  >> {a}")

    partes.append("")
    partes.append("(6) OS BOTÕES QUE O KERNEL DECLARA — diferença simétrica de conjuntos")
    tab_caps, iguais = bloco_capacidades(coletas)
    partes.append(tab_caps)
    partes.append(
        "  conjuntos "
        + ("IDÊNTICOS em todos os nós — diferença simétrica VAZIA" if iguais else "DIVERGEM")
    )
    partes.append(
        "  Isto é o conjunto DECLARADO, não o bit que cada botão acende: para saber se o"
    )
    partes.append(
        "  quadrado é o mesmo bit nos dois braços é preciso apertar, e apertar é O BLOCO"
    )
    partes.append("  DELA — veja `--apertar`.")

    n_cabo = sum(1 for c in fisicos.values() if c.transporte == CABO)
    n_radio = sum(1 for c in fisicos.values() if c.transporte == RADIO)
    linha = (
        f"{len(fisicos)} físico(s) ({n_cabo} cabo, {n_radio} rádio) e {len(dos_vpads)} vpad(s) "
        f"lidos na MESMA janela de {segundos:.0f} s. "
    )
    if sujos:
        linha += "JANELA CONTAMINADA — veredito de repouso SUSPENSO."
    elif mortos or discordam:
        linha += "UM CONTROLE REPROVOU — veredito SUSPENSO."
    else:
        linha += (
            f"casamento vpad<->físico "
            f"{'ÚNICO' if pares and pares[0].unico else 'AMBÍGUO'}, "
            f"{concordam}/{len(pares)} confirmado(s) por uma segunda régua; "
            + (
                f"conjunto de botões {'idêntico' if iguais else 'DIVERGENTE'} entre os braços."
                if (n_cabo and n_radio)
                else "SÓ UM TRANSPORTE na mesa — nada foi comparado entre braços."
            )
        )
    return "\n".join(partes), linha


def main() -> int:
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument("--segundos", type=float, default=20.0)
    ap.add_argument("--bruto", default="", help="diretório onde gravar a saída literal")
    ap.add_argument(
        "--apertar",
        action="store_true",
        help="imprime O BLOCO DELA (o único degrau que precisa de dedo) e para",
    )
    args = ap.parse_args()

    if args.apertar:
        print(TEXTO_APERTAR)
        return 0

    aparelhos = descobrir_aparelhos()
    nos_evdev = [
        e
        for e in (evdev_principal(a.dir_device) for a in aparelhos if not a.e_vpad)
        if e
    ]
    saida: list[str] = [
        cabecalho_do_instrumento(
            "entrada_em_repouso.py",
            "o que o controle PARADO diz, no fio e no vpad?",
            bibliotecas=["os", "select", "evdev", "time"],
            escreve_no_aparelho=False,
            daemon_precisa_parar=False,
            nos_evdev=nos_evdev,
        ),
        "  régua ............ deriva = nº de valores DISTINTOS do eixo na janela e a amplitude",
        "                     entre eles. Um é UM: distintos==1 é repouso morto. Fidelidade do",
        "                     vpad = igualdade EXATA byte a byte. Paridade = diferença simétrica",
        "                     de conjuntos, vazia ou não vazia.",
        "  corpo ............ driver-hid-playstation.md §1.1 — corpo em data[1] no cabo e em",
        "                     data[2] no rádio; o offset sai do ID do report, nunca fixo.",
        "=" * 78,
        censo_da_mesa(aparelhos),
        f"  janela ........... {args.segundos:.0f} s, TODOS os nós ao mesmo tempo",
        f"  T0 (parede) ...... {datetime.now():%Y-%m-%d %H:%M:%S.%f}"[:40],
    ]
    print("\n".join(saida))

    coletas = coletar(aparelhos, args.segundos)
    relatorio, linha = monta_relatorio(coletas, args.segundos)
    print(relatorio)
    print(resumo(linha))

    if args.bruto:
        os.makedirs(args.bruto, exist_ok=True)
        alvo = os.path.join(
            args.bruto, f"{datetime.now():%Y-%m-%d}-entrada-em-repouso.txt"
        )
        with open(alvo, "w", encoding="utf-8") as fh:
            fh.write("\n".join(saida) + "\n" + relatorio + "\n" + resumo(linha) + "\n")
        print(f"\nbruto gravado em {alvo}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
