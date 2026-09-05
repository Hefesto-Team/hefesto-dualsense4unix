"""virtual_motion.py — o interruptor de giroscópio e acelerômetro, por peça.

SENSOR-DE-VERDADE-01 / ONDA1-D3. Decisão dela, 04/09/2026, depois de eu
recomendar a saída barata (virar leitura, um selo "no ar / parado"):

    *"ele tem que funcionar de verdade. ambos independente do modo e da
    mascara."* <!-- noqa-acento: citação literal dela -->

**Interruptor de verdade. Cada sensor por si. Em Nativo e em Virtual. Com ou
sem máscara.** Este módulo é a metade que faz o JOGO parar de receber — a
outra (a tela) é da aba 02, e não mora aqui.

A MEDIÇÃO QUE DECIDIU O DESENHO — 04/09/2026, um DualSense no cabo
--------------------------------------------------------------------
Instrumento: SDL 2.30.0 headless (sem janela), abrindo os controles como um
jogo abre, mais a leitura direta dos nós evdev e do `hidraw`.

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
   botão"* — **falso para o SDL**: ele não enumera o nó de movimento
   (``SDL_NumJoysticks`` devolve só os controles; o nó carrega
   ``ID_INPUT_ACCELEROMETER`` e o SDL o pula). O grab alcança o consumidor
   evdev DIRETO (``evtest``, emuladores que leem o nó), não o SDL;
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
Porque ela pediu *"independente (…) da mascara"*, e **trocar a máscara
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
from typing import NamedTuple

#: Faixa do GIROSCÓPIO dentro da janela de 25 B (``payload[15:40]`` do report
#: 0x01): ``gyro[3] __le16`` são os bytes absolutos 15-20, logo 0..5 aqui.
#: A fonte é o `struct dualsense_input_report` do `hid-playstation.c`, já
#: fossilizada em `integrations/uhid_gamepad._MOTION_WINDOW_START`.
FAIXA_GIROSCOPIO = slice(0, 6)

#: Faixa do ACELERÔMETRO: ``accel[3] __le16``, bytes absolutos 21-26.
FAIXA_ACELEROMETRO = slice(6, 12)

#: Tamanho da janela. Repetido aqui de propósito: importar o
#: `uhid_gamepad` puxaria o backend uhid inteiro (e o `/dev/uhid`) para dentro
#: de um módulo que é PURO — e é justamente essa pureza que deixa a régua
#: exercitar o filtro sem hardware nenhum. Há teste que compara as duas
#: constantes e reprova se elas divergirem.
TAMANHO_DA_JANELA = 25


class EstadoDosSensores(NamedTuple):
    """O que está LIGADO para uma peça. Ausência = os dois ligados.

    ``D-AUDIO-E-GIRO-NASCEM-LIGADOS`` (25/08/2026): giroscópio nasce ligado em
    todo jogo. Um controle sem entrada no registro não é "não sei" — é o
    default dela, e por isso :meth:`RegistroDeSensores.estado` devolve
    ``(True, True)`` em vez de ``None``.
    """

    giroscopio: bool = True
    acelerometro: bool = True

    @property
    def tudo_ligado(self) -> bool:
        """True quando não há nada a filtrar (o caminho rápido)."""
        return self.giroscopio and self.acelerometro


def janela_com_sensores(
    janela: bytes, *, giroscopio: bool = True, acelerometro: bool = True
) -> bytes:
    """A janela de motion com o sensor desligado ZERADO — o resto verbatim.

    Zera SÓ os 6 bytes daquele sensor. O que fica intocado, e cada um por uma
    razão medida:

    * o ``sensor_timestamp`` (bytes 12-15 da janela) — é o ``dt`` com que o
      SDL integra o giro. Zerá-lo não desligaria nada e faria o jogo dividir
      por um intervalo que anda para trás;
    * o ``reserved2`` (byte 16) e os DOIS pontos de toque (17-24) — o touchpad
      viaja na mesma janela, e desligar o giroscópio não pode apagar o dedo
      dela da tela. É a decisão dela de 04/09: *"pedi pra tirar o texto não o
      touch mostrando os toques"*. <!-- noqa-acento: citação literal dela -->

    Janela de tamanho errado volta **verbatim**: quem a recusa é o vpad
    (`forward_motion` descarta e registra), e uma segunda política aqui daria
    duas respostas para o mesmo report torto.

    Com os dois ligados devolve **o mesmo objeto** — ver o custo no cabeçalho.
    """
    if giroscopio and acelerometro:
        return janela
    if len(janela) != TAMANHO_DA_JANELA:
        return janela
    fora = bytearray(janela)
    if not giroscopio:
        fora[FAIXA_GIROSCOPIO] = bytes(6)
    if not acelerometro:
        fora[FAIXA_ACELEROMETRO] = bytes(6)
    return bytes(fora)


def sensores_vivos_na_janela(janela: bytes) -> EstadoDosSensores:
    """O que a janela AINDA carrega: `(giro tem dado, accel tem dado)`.

    É a régua do ensaio de bancada, e ela lê o que SAIU em vez de perguntar ao
    produto o que ele acha que fez — a disciplina de 04/09, quando quatro
    réguas deram verde sobre defeito vivo.

    Cuidado que ela **não** resolve, e está escrito para ninguém confundir:
    um controle absolutamente parado num sensor de 16 bits também pode
    entregar seis zeros por um instante. Zero num quadro é indício; a prova é
    zero em TODOS os quadros de uma janela de tempo com o aparelho se mexendo
    — que é como o ensaio a usa.
    """
    if len(janela) != TAMANHO_DA_JANELA:
        return EstadoDosSensores(True, True)
    return EstadoDosSensores(
        giroscopio=any(janela[FAIXA_GIROSCOPIO]),
        acelerometro=any(janela[FAIXA_ACELEROMETRO]),
    )


class RegistroDeSensores:
    """Quem está desligado, por peça de plástico. Sem I/O, sem disco.

    Dono único do estado VIVO dos sensores dentro do processo do daemon. O
    disco é do perfil (`profiles/schema.ControllerSensoresOverride`); aqui é o
    que vale AGORA, e é o que o caminho quente consulta.

    Thread-safe porque os dois lados batem em threads diferentes: quem escreve
    é o event loop do IPC, quem lê é a thread do `PhysicalReportReader`, a
    ~250 Hz.
    """

    def __init__(self) -> None:
        self._lock = threading.RLock()
        self._estado: dict[str, EstadoDosSensores] = {}

    def definir(
        self,
        uniq: str,
        *,
        giroscopio: bool | None = None,
        acelerometro: bool | None = None,
    ) -> EstadoDosSensores:
        """Liga/desliga um sensor. ``None`` = **não mexe naquele**.

        Mesmo contrato de `rumble.motores.set`: campo omitido não é campo
        zerado. Sem isso, desligar o giroscópio ligaria o acelerômetro de
        volta pelas costas dela.

        Volta a ``(True, True)`` apaga a entrada: o default dela não ocupa
        lugar, e o caminho quente vê um dicionário vazio no caso normal.
        """
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
        """A janela como ela deve SAIR para a peça `uniq`.

        O caminho quente inteiro: um `dict.get` sob lock e, no caso normal, o
        mesmo objeto de volta.
        """
        estado = self.estado(uniq)
        if estado.tudo_ligado:
            return janela
        return janela_com_sensores(
            janela,
            giroscopio=estado.giroscopio,
            acelerometro=estado.acelerometro,
        )

    def desligados(self) -> dict[str, EstadoDosSensores]:
        """Cópia de quem tem sensor desligado — a lista que o hub consulta.

        É por ela que o `SensorHub` sabe que precisa manter vivo o reader do
        nó de movimento MESMO sem a GUI aberta: sem isso o TTL de 5 s mataria
        o reader e, com ele, o `EVIOCGRAB` — o interruptor se desligaria
        sozinho cinco segundos depois de ela fechar a janela.
        """
        with self._lock:
            return dict(self._estado)

    def limpar(self) -> None:
        """Esquece tudo (fim de sessão/teste). Idempotente."""
        with self._lock:
            self._estado.clear()


def chave_de_sensor(uniq: str) -> str:
    """Normaliza o endereço de rádio: só os dígitos hex, em minúsculas.

    **ESTA LINHA É UM DEFEITO QUE A RÉGUA PEGOU**, e vale escrever por quê.
    A primeira versão só fazia `strip().lower()`, e passou em tudo até o teste
    do perfil: a mesma peça de plástico tem DUAS grafias nesta casa — o
    `uniq` do evdev/hidraw vem com dois-pontos (`aa:bb:cc:00:00:01`) e a chave
    do perfil vem sem (`aabbcc000001`, por `core.sysfs_leds.norm_mac`). Com a
    normalização fraca, ela desligava o giro pela tela e o perfil gravava sob
    outra chave: o interruptor valia até o replug e voltava calado.

    Mesma peneira do `norm_mac`, escrita aqui e não importada dele porque este
    módulo é PURO e o `sysfs_leds` puxa o caminho de LED. Há régua comparando
    as duas — se elas divergirem, é a mesma peça com dois donos outra vez.
    """
    return "".join(ch for ch in str(uniq).lower() if ch in "0123456789abcdef")


#: O registro do processo. Um só, e por isso é módulo e não injeção: o
#: `PhysicalReportReader` (thread), o `SensorHub` (outra thread) e o
#: `ipc_handlers` (event loop) precisam ver o MESMO estado, e passar a
#: instância por cinco camadas de construtor foi o que fez a barra de motor
#: precisar de um `esquecer_motores_do_perfil` para valer agora.
REGISTRO = RegistroDeSensores()


__all__ = [
    "FAIXA_ACELEROMETRO",
    "FAIXA_GIROSCOPIO",
    "REGISTRO",
    "TAMANHO_DA_JANELA",
    "EstadoDosSensores",
    "RegistroDeSensores",
    "chave_de_sensor",
    "janela_com_sensores",
    "sensores_vivos_na_janela",
]
