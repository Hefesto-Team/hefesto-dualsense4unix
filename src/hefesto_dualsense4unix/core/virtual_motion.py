"""virtual_motion.py — o interruptor de giroscópio e acelerômetro, por peça.

SENSOR-DE-VERDADE-01 / ONDA1-D3. Decisão, 04/09/2026, depois de se
recomendar a saída barata (virar leitura, um selo "no ar / parado"):

    *"ele tem que funcionar de verdade. ambos independente do modo e da
    mascara."* <!-- noqa-acento: citação literal -->

**Interruptor de verdade. Cada sensor por si. Em Nativo e em Virtual. Com ou
sem máscara.** Este módulo é a metade que faz o JOGO parar de receber — a
outra (a tela) é da aba 02, e não mora aqui.

A MEDIÇÃO QUE DECIDIU O DESENHO — 04/09/2026, um DualSense no cabo
--------------------------------------------------------------------
Instrumento: a libSDL2 2.30.0 do SISTEMA, headless (sem janela), abrindo os
controles como um jogo abre, mais a leitura direta dos nós evdev e do `hidraw`.

======================  =============================  =========================
caminho                 Nativo                         Virtual (uhid)
======================  =============================  =========================
`hidraw` do FÍSICO      ``0660`` + ACL — **o SDL       ``0600 root`` — o jogo
                        ABRE, e o giro chega POR       não abre (o daemon o
                        AQUI**: ``tem_giro=true``,     esconde)
                        192 valores distintos em 2 s
`hidraw` do VPAD        não existe                     ``0660`` + ACL, 249
                                                       relatórios/s
nó "Motion Sensors"     livre, ~1950 ev/s              livre nos DOIS (físico
                                                       **e** vpad)
o que o SDL abre        ``/dev/hidraw4`` (HIDAPI)      ``event21``/``event25``
                                                       (evdev)
======================  =============================  =========================

**O que a medição derrubou, e são três frases da sprint que a encomendou:**

1. *"agarrar ESSE nó [Motion Sensors] esconde o giro do jogo sem tocar um
   botão"* — **não para o jogo que abriu o VPAD**: o SDL casa o nó de
   movimento ao gamepad da MESMA peça pelo ``uniq`` (SENSORES-NO-JOGO-02,
   13/09/2026), e o nó do vpad só o braço do REPORT alcança. O grab no nó do
   FÍSICO alcança ``evtest``, emuladores e quem abriu o físico;
2. *"em Virtual o giro já passa pelo vpad — o interruptor já tem metade do
   motor"* — em Virtual **o nó de movimento do FÍSICO continua livre e
   publicando**, ao lado do espelho. Parar o espelho não é metade: é um
   quarto;
3. *"Nativo: o jogo lê o nó de movimento do kernel"* — o kernel publica o nó,
   mas quem entrega ao jogo é o **`hidraw`**.

DAÍ OS DOIS BRAÇOS, e por que nenhum deles sozinho serve
---------------------------------------------------------
* **o braço do REPORT** (este módulo): a janela de motion que o
  `PhysicalReportReader` copia do físico e entrega ao vpad passa por
  :func:`janela_com_sensores`, que **zera os 6 bytes do sensor desligado** e
  deixa todo o resto verbatim. Alcança quem lê o vpad — que em Virtual é o
  único caminho que o daemon controla byte a byte;
* **o braço do EVDEV** (`daemon/sensor_hub.py`): o `EVIOCGRAB` no nó "Motion
  Sensors" daquele controle. Alcança o consumidor evdev direto, nos DOIS
  modos.

**O que NENHUM dos dois alcança, e está escrito porque medir é o trabalho:**
em **Nativo**, o jogo lê o `hidraw` do físico e o daemon **não está no
caminho** — o kernel entrega o report direto. Não há byte a zerar. As saídas
seriam esconder o `hidraw` inteiro (que mata rumble e gatilhos do jogo junto)
ou um comando de firmware que desligue a IMU — e este não existe:
``docs/data/mapa-controles.csv``, chave ``movimento.imu.ligar``, diz
``existe=nao-tem`` por busca fechada em 15/08/2026. Quem chama
:func:`sensor.set` recebe esse limite ESCRITO na resposta, em vez de um
"aplicado" sobre um giro que continua chegando.

POR QUE O ESTADO MORA NUM REGISTRO POR ``uniq``, e não no objeto do vpad
------------------------------------------------------------------------
Porque o usuário pediu *"independente (…) da mascara"*, e **trocar a máscara
derruba e recria o gamepad virtual** (medido, e registrado em
``profiles/schema.py``). Estado guardado no objeto do vpad morreria em cada
troca de máscara — o sensor voltaria a ligar sozinho, em silêncio, e a tela
continuaria dizendo "desligado". O registro é do PROCESSO e chaveado pela
peça de plástico; o vpad nasce e morre por baixo dele.

O CUSTO NO CAMINHO QUENTE, medido pelo desenho e não pela esperança
--------------------------------------------------------------------
:func:`janela_com_sensores` roda a cada janela entregue (~250 Hz no cabo).
Com os dois sensores ligados — o caso normal, e o de sempre — ela devolve **o
mesmo objeto**, sem copiar um byte: um `and` e um retorno. Só quando há
sensor desligado se paga o `bytearray` de 25 bytes.
"""
from __future__ import annotations

import threading
from collections.abc import Mapping
from typing import NamedTuple

FAIXA_GIROSCOPIO = slice(0, 6)

FAIXA_ACELEROMETRO = slice(6, 12)

CONTATOS_DO_TOQUE = (17, 21)
TOQUE_INATIVO = 0x80

TAMANHO_DA_JANELA = 25


class EstadoDosSensores(NamedTuple):
    """O que está LIGADO para uma peça. Ausência = os dois ligados."""

    giroscopio: bool = True
    acelerometro: bool = True

    @property
    def tudo_ligado(self) -> bool:
        """True quando não há nada a filtrar (o caminho rápido)."""
        return self.giroscopio and self.acelerometro


def janela_com_sensores(
    janela: bytes, *, giroscopio: bool = True, acelerometro: bool = True,
    toque: bool = True,
) -> bytes:
    """A janela de motion com o sensor desligado ZERADO — o resto verbatim."""
    if giroscopio and acelerometro and toque:
        return janela
    if len(janela) != TAMANHO_DA_JANELA:
        return janela
    fora = bytearray(janela)
    if not giroscopio:
        fora[FAIXA_GIROSCOPIO] = bytes(6)
    if not acelerometro:
        fora[FAIXA_ACELEROMETRO] = bytes(6)
    if not toque:
        for contato in CONTATOS_DO_TOQUE:
            fora[contato] |= TOQUE_INATIVO
    return bytes(fora)


def sensores_vivos_na_janela(janela: bytes) -> EstadoDosSensores:
    """O que a janela AINDA carrega: `(giro tem dado, accel tem dado)`."""
    if len(janela) != TAMANHO_DA_JANELA:
        return EstadoDosSensores(True, True)
    return EstadoDosSensores(
        giroscopio=any(janela[FAIXA_GIROSCOPIO]),
        acelerometro=any(janela[FAIXA_ACELEROMETRO]),
    )


class RegistroDeSensores:
    """Quem está desligado, por peça de plástico. Sem I/O, sem disco."""

    def __init__(self) -> None:
        self._lock = threading.RLock()
        self._estado: dict[str, EstadoDosSensores] = {}
        self._roteado_sem_chip = False
        self._roteado: dict[str, bool] = {}
        self._toque_roteado_sem_chip = False
        self._toque_roteado: dict[str, bool] = {}

    def definir(
        self,
        uniq: str,
        *,
        giroscopio: bool | None = None,
        acelerometro: bool | None = None,
    ) -> EstadoDosSensores:
        """Liga/desliga um sensor. ``None`` = **não mexe naquele**."""
        chave = chave_de_sensor(uniq)
        with self._lock:
            atual = self._estado.get(chave, EstadoDosSensores())
            novo = EstadoDosSensores(
                giroscopio=atual.giroscopio if giroscopio is None else bool(giroscopio),
                acelerometro=(
                    atual.acelerometro if acelerometro is None else bool(acelerometro)
                ),
            )
            if novo.tudo_ligado:
                self._estado.pop(chave, None)
            else:
                self._estado[chave] = novo
            return novo

    def estado(self, uniq: str | None) -> EstadoDosSensores:
        """O que vale para `uniq` agora; ``(True, True)`` sem entrada."""
        if not uniq:
            return EstadoDosSensores()
        with self._lock:
            return self._estado.get(chave_de_sensor(uniq), EstadoDosSensores())

    def filtrar(self, uniq: str | None, janela: bytes) -> bytes:
        """A janela como ela deve SAIR para a peça `uniq`."""
        estado = self.estado(uniq)
        giro = estado.giroscopio and not self.roteado(uniq)
        toque = not self.toque_roteado(uniq)
        if giro and estado.acelerometro and toque:
            return janela
        return janela_com_sensores(
            janela,
            giroscopio=giro,
            acelerometro=estado.acelerometro,
            toque=toque,
        )

    def definir_roteados(
        self,
        *,
        sem_chip: bool,
        por_peca: Mapping[str, bool],
        toque_sem_chip: bool = False,
        toque_por_peca: Mapping[str, bool] | None = None,
    ) -> None:
        """Quais peças mandam o giro à MIRA em vez de ao jogo. TROCA tudo."""
        limpo = {chave_de_sensor(k): bool(v) for k, v in por_peca.items() if chave_de_sensor(k)}
        toques = {
            chave_de_sensor(k): bool(v)
            for k, v in (toque_por_peca or {}).items()
            if chave_de_sensor(k)
        }
        with self._lock:
            self._roteado_sem_chip = bool(sem_chip)
            self._roteado = limpo
            self._toque_roteado_sem_chip = bool(toque_sem_chip)
            self._toque_roteado = toques

    def toque_roteado(self, uniq: str | None) -> bool:
        """O dedo desta peça vai ao cursor ou às zonas, e não ao jogo?"""
        if not uniq:
            return False
        with self._lock:
            return self._toque_roteado.get(chave_de_sensor(uniq), self._toque_roteado_sem_chip)

    def roteado(self, uniq: str | None) -> bool:
        """Esta peça está mirando — o giro dela vai ao analógico, não ao jogo?"""
        if not uniq:
            return False
        with self._lock:
            return self._roteado.get(chave_de_sensor(uniq), self._roteado_sem_chip)

    def desligados(self) -> dict[str, EstadoDosSensores]:
        """Cópia de quem tem sensor desligado — a lista que o hub consulta."""
        with self._lock:
            return dict(self._estado)

    def limpar(self) -> None:
        """Esquece tudo (fim de sessão/teste). Idempotente."""
        with self._lock:
            self._estado.clear()
            self._roteado_sem_chip = False
            self._roteado = {}
            self._toque_roteado_sem_chip = False
            self._toque_roteado = {}


def chave_de_sensor(uniq: str) -> str:
    """Normaliza o endereço de rádio: só os dígitos hex, em minúsculas."""
    return "".join(ch for ch in str(uniq).lower() if ch in "0123456789abcdef")


REGISTRO = RegistroDeSensores()


__all__ = [
    "CONTATOS_DO_TOQUE",
    "FAIXA_ACELEROMETRO",
    "FAIXA_GIROSCOPIO",
    "REGISTRO",
    "TAMANHO_DA_JANELA",
    "TOQUE_INATIVO",
    "EstadoDosSensores",
    "RegistroDeSensores",
    "chave_de_sensor",
    "janela_com_sensores",
    "sensores_vivos_na_janela",
]
