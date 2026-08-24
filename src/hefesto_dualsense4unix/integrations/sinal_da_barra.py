"""BARRA-MUDA-01: o sinal honesto de que a barra vai obedecer — e o que ele NÃO é.

O QUE ESTE MÓDULO NÃO FAZ, e é a primeira linha de propósito: **ele não lê a
lâmpada.** Não existe leitura da lâmpada. Isso está medido três vezes nesta casa
e nenhuma delas foi derrubada:

1. ``multi_intensity`` é a memória da última escrita que passou pela classe LED,
   nunca o aparelho — leu ``[0 255 0]`` com a barra APAGADA e ``[0 255 0]`` com
   ela VERDE (ensaio ``lightbar-sysfs-nao-sabe``, 16/08/2026);
2. o report de ENTRADA do DualSense não carrega estado de LED em campo nenhum —
   provado no fonte C, ``dualsense_parse_report`` toca sticks, botões, mudo do
   mic, jack, IMU, touchpad e bateria, e nada mais
   (``docs/protocol/driver-hid-playstation.md``);
3. dos dezessete feature reports lidos em 14-15/08/2026, **nenhum** devolve
   estado de LED (``core/escritor_cru.py``, seção "POR QUE O CONTADOR É O fd").

E a bateria não salva: o ``ps-controller-battery`` do ``hid-playstation``
registra ``capacity``, ``present``, ``scope`` e ``status``, e **mais nada** —
não há ``current_now`` nem ``voltage_now`` para inferir consumo de barra acesa
(MEDIDO 22/08/2026 nos quatro nós da bancada dela). Quem for tentar "medir a
corrente" está tentando ler um arquivo que o driver não cria.

O QUE ESTE MÓDULO FAZ ENTÃO
===========================
Ele responde a pergunta que TEM resposta, e que prevê a lâmpada:

    **esta instância de conexão nasceu com outro processo segurando o hidraw
    dela?**

MEDIDO EM 22/08/2026, na bancada dela, seis instâncias contra o olho dela, e a
concordância foi 6/6:

===========================  ===================  ==================
instância (nasceu)           escritor cru ao      barra, pelo olho
                             nascer                dela
===========================  ===================  ==================
.0028 / .0029 / .002A /      **SIM** (a Steam,    **APAGADA**, e não
.002B  (18:05-18:06)         pid morto desde)     obedece a escrita
.0033 / .0034 (19:51)        não                  **ACENDE**, e obedeceu
                                                  ciano e a volta à cor
===========================  ===================  ==================

As duas que ela reconectou (PS depois de um ``Disconnect`` pelo D-Bus) voltaram
como instâncias NOVAS, nascidas com a mesa limpa, e acenderam. As duas que
ficaram continuam com o nascimento sujo de 18:06 — e continuam travadas AGORA,
com a Steam morta e o daemon parado. **O defeito mora na instância, não no
processo que o causou:** matar a Steam não cura, porque o que ela fez foi feito
no nascimento e persiste até a reconexão (ou o power-off físico).

POR QUE ISSO EXPLICA O "FALSO POSITIVO RECORRENTE" DELA
=======================================================
O alerta dela, 12/08/2026 (``docs/data/mapa-controles.csv``,
``luz.lightbar.cor@dualsense``, ``radio_ressalva``):

    *"não é só instância de conexão, se escavar o projeto vai ver que isso é um
    falso positivo recorrente"*

Ela está certa, e agora dá para dizer POR QUÊ "reconectar cura" já foi concluído
antes e caiu depois: **reconectar só cura se a mesa estiver limpa na hora.** Com
a Steam aberta, a instância NOVA nasce suja igual à velha, e a cura parece ter
parado de funcionar. É a mesma cura e é a mesma doença — o que muda é uma
condição que ninguém estava medindo.

Daí as duas perguntas serem SEPARADAS neste arquivo, e nunca respondidas pela
mesma função:

- :func:`ler_a_mesa` — *"esta instância que já existe nasceu limpa?"*. É
  DIAGNÓSTICO, e só a responde para instâncias cujo nascimento esteja no diário.
  Sem diário, ``CONFIANCA_NAO_SEI`` — jamais ``limpa``;
- :func:`limpo_para_conectar` — *"se um controle conectar AGORA, vai nascer
  limpo?"*. É PROGNÓSTICO, e é a que tem de guardar o botão de reconectar. Um
  produto que oferece a cura sem consultar esta função entrega à pessoa o gesto
  do botão PS em troca de nada.

E uma terceira peça, que é MEMÓRIA e não pergunta:

- :class:`CartorioDoNascimento` — onde o veredito do diagnóstico fica guardado,
  POR INSTÂNCIA, carimbado no tique de hotplug em que a conexão nasce
  (``daemon/connection.py::carimbar_o_nascimento``). Sem ele o veredito só
  existe enquanto o diário ainda tem a linha, e o diário rotaciona.

A DISCIPLINA, herdada de ``integrations/exame_da_mesa.py`` e de
``core/escritor_cru.py``, linha a linha:

- **Somente leitura.** Nenhuma função deste arquivo escreve em lugar nenhum, e
  em particular **nada aqui toca o aparelho** — nem sysfs, nem hidraw, nem
  feature report. Sondar o aparelho para saber se ele está travado é o caminho
  que a ``LIGHTBAR-BT-RESET-01`` acusa de CAUSAR o travamento, e ele não foi
  eliminado por medição nenhuma;
- **Sem root, nunca.** O que exigiria ``sudo`` devolve ``CONFIANCA_NAO_SEI``;
- **"não sondado" nunca é "limpo"** — o terceiro estado é obrigatório;
- **Cada caminho entra por argumento**, com default igual ao sistema real;
- **100% stdlib**, para o doctor poder chamar pelo ``python3`` do sistema;
- **Nenhum endereço de rádio inteiro sai no relatório** — :func:`mascarar` zera
  os octetos 4 e 5, porque o retrato das abas versiona PNG do que aparece na
  tela e há portão que reprova MAC real em arquivo do repositório.
"""

from __future__ import annotations

import argparse
import contextlib
import json
import os
import re
import subprocess
import sys
import time
from collections.abc import Callable, Collection, Iterable, Mapping, Sequence
from dataclasses import dataclass, replace

#: Onde o ``hid-playstation`` pendura as instâncias de conexão. O sufixo hexa
#: (``0005:054C:0CE6.0033``) é um contador do HID core: ele NÃO se repete
#: enquanto a máquina não reinicia, e por isso é a chave estável de "esta
#: conexão", que é o que este módulo mede. O número do ``inputN`` também serve,
#: mas o sufixo é o que o log do kernel imprime.
RAIZ_UHID = "/sys/devices/virtual/misc/uhid"

#: O DualSense, e só ele. ``0CE6`` por rádio e por cabo; o ``0DF2`` do vpad
#: deste projeto fica de fora de propósito — a barra dele é desenhada na tela,
#: não existe em plástico, e incluí-lo encheria o relatório de linha sem dono.
_ID_DUALSENSE = "054C:0CE6"

#: Os três estados. O terceiro não é enfeite: é o que sai quando o nascimento
#: desta instância não está no diário — porque afirmar "limpa" sem ter olhado é
#: exatamente o erro que a leitura de ``multi_intensity`` cometia.
CONFIANCA_LIMPA = "limpa"
CONFIANCA_SUSPEITA = "suspeita"
CONFIANCA_NAO_SEI = "nao_sei"  # (noqa-acento): chave de máquina, ASCII por contrato

#: Quanto tempo depois do registro no kernel ainda conta como "no nascimento".
#: MEDIDO em 22/08/2026, nas quatro instâncias sujas da bancada: o daemon
#: detectou o escritor cru 0,64 s / 1,47 s / 1,53 s / 2,25 s depois da linha
#: ``Registered DualSense controller``. Cinco segundos cobre as quatro com
#: folga. Não é grande demais: o casamento exige TAMBÉM o mesmo nó hidraw, e
#: números de hidraw são reciclados (o ``hidraw6`` foi da ``.0028`` às 18:05 e
#: da ``.0033`` às 19:51) — é o par (nó, janela) que desambigua, nunca o nó
#: sozinho.
JANELA_DE_NASCIMENTO_S: float = 5.0

#: Teto da leitura do diário. O diário dela tem 88 mil linhas só da unit do
#: daemon; sem teto isto viraria uma pausa de segundos numa aba de interface.
ORCAMENTO_DO_DIARIO_S: float = 8.0

#: Quanto do passado o diário é lido. **Não é enfeite de desempenho: sem ele o
#: teto acima é quase alcançado.** MEDIDO em 22/08/2026, na máquina dela, com o
#: diário de quinze dias:
#:
#: ===========================================  =======
#: ``journalctl --user -u ...service -o json``  5,21 s
#: o mesmo, com ``-S`` de 6 horas               0,12 s
#: ===========================================  =======
#:
#: Seis segundos por leitura seriam pagos por um dos DOIS workers do executor
#: que o daemon divide com o ``read_state`` — o padrão que a ``HANG-01`` baniu.
#: Seis horas cobre uma sessão inteira; uma conexão mais velha que isso cai no
#: ``nao_sei`` de "mais velha que o diário desta sessão", que é resposta honesta
#: e não invenção. ``0`` ou negativo lê tudo.
JANELA_DO_DIARIO_S: float = 6 * 3600.0

_RE_UEVENT = re.compile(r"^(HID_PHYS|HID_UNIQ|HID_ID)=(.*)$", re.MULTILINE)

#: A linha que o ``hid-playstation`` imprime ao adotar uma conexão. Ela carrega
#: as três coisas que o casamento precisa: a instância, o nó hidraw e o
#: transporte (``BLUETOOTH`` ou ``USB``).
#: ATENÇÃO ao formato do ``hid``: o log do kernel imprime a forma CURTA
#: (``0005:054C:0CE6``), enquanto o ``uevent`` do mesmo aparelho traz a longa
#: (``0005:0000054C:00000CE6``). Escrever ``{8}`` aqui — que é o que o uevent
#: mostra — faz a varredura casar ZERO linhas e o módulo inteiro responder
#: "não sei" sem errar em lugar nenhum visível. Foi o primeiro defeito deste
#: arquivo, pego só porque a bancada tinha resposta conhecida para conferir.
_RE_NASCIMENTO = re.compile(
    r"playstation (?P<hid>[0-9A-Fa-f]{4}:[0-9A-Fa-f]{4,8}:[0-9A-Fa-f]{4,8})\."
    r"(?P<inst>[0-9A-Fa-f]{4}): (?P<no>hidraw\d+): (?P<via>BLUETOOTH|USB) HID"
)

#: A linha do próprio daemon, de ``ESCRITOR-CRU-01``. Ela é a segunda régua, e é
#: independente da primeira: a de cima vem do kernel e enumera dispositivos; esta
#: vem de uma varredura de ``/proc/<pid>/fd`` feita em espaço de usuário.
_RE_ESCRITOR = re.compile(r"escritor_cru_detectado.*?nos=\[(?P<nos>[^\]]*)\]")


def mascarar(mac: str) -> str:
    """Zera os octetos 4 e 5 — a máscara desta casa, e há portão que a cobra.

    ``aa:bb:cc:11:22:33`` vira ``aa:bb:cc:00:00:33``. Serve para o relatório
    poder nomear um controle sem que o endereço dela caia num PNG versionado
    pelo caminho do retrato das abas.
    """
    partes = mac.split(":")
    if len(partes) != 6:
        return mac
    partes[3] = partes[4] = "00"
    return ":".join(partes)


@dataclass(frozen=True)
class Instancia:
    """Uma conexão viva, como o sysfs a descreve — sem tocar o aparelho.

    O que muda na reconexão é o ``inputN`` e o sufixo da instância. O ``uniq``
    (o endereço do controle) e o ``hw_version`` **não** mudam, e os dois juntos
    casaram ``.0028``→``.0033`` e ``.002A``→``.0034`` na medição de 22/08/2026.

    QUAL DOS DOIS É IDENTIDADE, porque confundir isso custa caro:

    - ``uniq`` **é**. É o endereço com que o resto do produto já chama cada
      controle (``nos_hidraw_por_uniq``, o alvo de edição de
      ``app/alvo_de_edicao.py``, os perfis).
      CONFERIDO em 22/08/2026 cruzando duas tabelas independentes com uma
      semana de distância: os quatro pares ``uniq``↔``hw_version`` da canônica
      (15/08, ``dualsense-referencia-canonica.md``, *"O hardware_version do
      sysfs distingue as unidades"*) são os MESMOS quatro pares da bancada de
      22/08. Quatro de quatro;
    - ``hw_version`` **não é**. Ele é revisão de placa, e a canônica registra a
      medição: *"dois controles da mesma cor comprados juntos teriam o mesmo
      valor"*. Nos quatro aparelhos dela ele é distinto **por acaso de lote**.
      Serve de chave de DIAGNÓSTICO — e é assim que
      :meth:`CartorioDoNascimento.do_hw_version` o trata, devolvendo lista.
    """

    instancia: str
    uniq: str
    adaptador: str
    hw_version: str
    input_n: int | None
    hidraw: str | None
    transporte: str  # "bt" | "usb"

    @property
    def no_radio(self) -> bool:
        return self.transporte == "bt"

    @property
    def apelido(self) -> str:
        """Como a linha do relatório chama este controle, já mascarado."""
        return f"{mascarar(self.uniq)} (.{self.instancia})" if self.uniq else f".{self.instancia}"


@dataclass(frozen=True)
class Leitura:
    """O veredito de UMA instância. Imutável: é uma foto, não estado.

    ``porque`` é escrito para a pessoa, em português, e é o que a aba mostra.
    Ele nunca diz "acesa" nem "apagada" — este módulo não sabe isso, e há teste
    que reprova se alguma frase daqui passar a dizer.
    """

    alvo: Instancia
    confianca: str
    porque: str
    pids_do_escritor: tuple[int, ...] = ()
    nasceu_em: float | None = None

    @property
    def pede_reconexao(self) -> bool:
        """True quando a cura conhecida (Disconnect + botão PS) se aplica."""
        return self.confianca == CONFIANCA_SUSPEITA


@dataclass(frozen=True)
class Nascimento:
    """O que o diário sabe sobre o nascimento de uma instância.

    ``escritor_conhecido`` é o terceiro estado de novo, e ele não é enfeite:
    quando o kernel respondeu e o diário do DAEMON não, sabe-se QUANDO a
    instância nasceu e não se sabe QUEM segurava o nó. Sem este campo, o
    ``sujo=False`` de fábrica vira "limpa" — que é afirmar inocência sem ter
    olhado, o erro exato que este módulo existe para não cometer.
    """

    instancia: str
    quando: float
    no: str
    transporte: str
    escritor: tuple[int, ...] = ()
    sujo: bool = False
    escritor_conhecido: bool = True


@dataclass(frozen=True)
class Carimbo:
    """O veredito de nascimento de UMA instância, guardado na hora em que ela nasceu.

    Existe porque o veredito de :func:`ler_a_mesa` custa dois ``journalctl`` e
    depende de o diário AINDA ter a linha. Carimbado no nascimento, ele vira
    resposta de memória, e sobrevive à rotação do diário — a primeira das três
    fragilidades que a ``SINAL-NO-NASCIMENTO-01`` listou.

    ``firme`` diz se a janela de nascimento já fechou. Um carimbo tirado no
    mesmo tique em que a instância apareceu ainda pode ganhar prova: a linha
    ``escritor_cru_detectado`` chega de 0,64 s a 2,25 s depois do registro no
    kernel (MEDIDO 22/08/2026, quatro instâncias), e o journald leva o seu
    tempo para ingeri-la. Enquanto não é firme, o carimbo é retirado de novo no
    tique seguinte — e ele só pode PIORAR, nunca melhorar (ver
    :meth:`CartorioDoNascimento.carimbar`).
    """

    leitura: Leitura
    visto_em: float
    carimbado_em: float
    firme: bool = False
    #: True quando o cartório viu esta instância APARECER — e não quando ela já
    #: estava na mesa desde antes de o daemon subir. Só quem nasceu sob nossos
    #: olhos pode ser agravado pela sonda ao vivo: numa instância que já estava
    #: aqui, "a Steam segura o nó agora" não diz nada sobre como ela nasceu.
    nasceu_sob_nossos_olhos: bool = False

    @property
    def instancia(self) -> str:
        return self.leitura.alvo.instancia

    @property
    def uniq(self) -> str:
        """O endereço do CONTROLE — a chave por que o resto do produto o chama."""
        return self.leitura.alvo.uniq

    @property
    def hw_version(self) -> str:
        """A revisão de placa. Chave de DIAGNÓSTICO, nunca de identidade."""
        return self.leitura.alvo.hw_version

    @property
    def confianca(self) -> str:
        return self.leitura.confianca

    @property
    def porque(self) -> str:
        return self.leitura.porque

    @property
    def pede_reconexao(self) -> bool:
        return self.leitura.pede_reconexao


#: A sonda de quem segura o nó, em forma de tipo — é o que torna este módulo
#: exercitável sem ``/proc``, sem Steam e sem controle na mesa.
Sonda = Callable[[Iterable[str] | None], Mapping[str, Sequence[int]]]

#: O leitor do diário, idem. Devolve as linhas já casadas por instância.
LeitorDeDiario = Callable[[], Mapping[str, Nascimento] | None]


def instancias_dualsense(raiz_uhid: str = RAIZ_UHID) -> list[Instancia]:
    """Enumera as conexões DualSense vivas. Só leitura de sysfs, sem root.

    Nada aqui abre ``/dev/hidraw`` — a enumeração inteira sai de ``uevent``,
    ``hardware_version`` e dos nomes dos diretórios.
    """
    achadas: list[Instancia] = []
    try:
        nomes = sorted(os.listdir(raiz_uhid))
    except OSError:
        return achadas
    for nome in nomes:
        if _ID_DUALSENSE not in nome.upper():
            continue
        base = os.path.join(raiz_uhid, nome)
        campos: dict[str, str] = {}
        try:
            with open(os.path.join(base, "uevent"), encoding="utf-8") as fh:
                for chave, valor in _RE_UEVENT.findall(fh.read()):
                    campos[chave] = valor.strip()
        except OSError:
            continue
        instancia = nome.rsplit(".", 1)[-1]
        # O transporte sai do BUS do HID_ID: 0005 = Bluetooth, 0003 = USB. É a
        # mesma fonte que o kernel usa para imprimir "BLUETOOTH HID" / "USB HID",
        # e não depende de o diário existir.
        bus = campos.get("HID_ID", "").split(":")[0].lower()
        transporte = "bt" if bus == "0005" else "usb"
        achadas.append(
            Instancia(
                instancia=instancia,
                uniq=campos.get("HID_UNIQ", ""),
                adaptador=campos.get("HID_PHYS", ""),
                hw_version=_ler(os.path.join(base, "hardware_version")),
                input_n=_primeiro_input(base),
                hidraw=_primeiro_hidraw(base),
                transporte=transporte,
            )
        )
    return achadas


def _ler(caminho: str) -> str:
    try:
        with open(caminho, encoding="utf-8") as fh:
            return fh.read().strip()
    except OSError:
        return ""


def _primeiro_input(base: str) -> int | None:
    try:
        nomes = sorted(os.listdir(os.path.join(base, "input")))
    except OSError:
        return None
    for nome in nomes:
        if nome.startswith("input"):
            with contextlib.suppress(ValueError):
                return int(nome[5:])
    return None


def _primeiro_hidraw(base: str) -> str | None:
    try:
        nomes = sorted(os.listdir(os.path.join(base, "hidraw")))
    except OSError:
        return None
    return f"/dev/{nomes[0]}" if nomes else None


def nascimentos_pelo_diario(
    *,
    unidade: str = "hefesto-dualsense4unix.service",
    orcamento_s: float = ORCAMENTO_DO_DIARIO_S,
    janela_s: float = JANELA_DE_NASCIMENTO_S,
    desde_s: float = JANELA_DO_DIARIO_S,
) -> dict[str, Nascimento] | None:
    """Reconstrói, do diário, quem segurava o nó quando cada instância nasceu.

    DUAS RÉGUAS INDEPENDENTES, que é a regra desta casa desde 16/08/2026: o
    instante de nascimento vem do KERNEL (``journalctl -k``, a linha
    ``playstation ...: hidrawN: BLUETOOTH HID``) e o escritor vem do DAEMON
    (``escritor_cru_detectado``, uma varredura de ``/proc`` em espaço de
    usuário). Uma não pode confirmar a outra por construção, que é o ponto.

    Devolve ``None`` — nunca um dicionário vazio — quando o kernel não pôde ser
    lido. Vazio significaria "nenhuma instância nasceu", e isso é mentira
    diferente de "não consegui olhar".
    """
    recorte = _recorte_do_diario(desde_s)
    kernel = _linhas_do_diario(["journalctl", "-k", "-o", "json", *recorte], orcamento_s)
    if kernel is None:
        return None
    nascimentos: dict[str, Nascimento] = {}
    for quando, texto in kernel:
        achou = _RE_NASCIMENTO.search(texto)
        if not achou or _ID_DUALSENSE not in achou.group("hid").upper():
            continue
        nascimentos[achou.group("inst").lower()] = Nascimento(
            instancia=achou.group("inst").lower(),
            quando=quando,
            no=f"/dev/{achou.group('no')}",
            transporte="bt" if achou.group("via") == "BLUETOOTH" else "usb",
        )

    daemon = _linhas_do_diario(
        ["journalctl", "--user", "-u", unidade, "-o", "json", *recorte], orcamento_s
    )
    if daemon is None:
        # O kernel respondeu e o daemon não. Não dá para dizer "ninguém
        # segurava": devolve os nascimentos MARCADOS como "não olhei quem
        # segurava", e cada um vira `nao_sei` lá no `_veredito`.
        return {
            chave: replace(nasc, escritor_conhecido=False)
            for chave, nasc in nascimentos.items()
        }
    return casar_escritores(nascimentos, deteccoes_de_escritor(daemon), janela_s)


def deteccoes_de_escritor(
    linhas: Iterable[tuple[float, str]],
) -> list[tuple[float, frozenset[str], tuple[int, ...]]]:
    """Extrai ``(quando, nós, pids)`` das linhas ``escritor_cru_detectado``."""
    achadas: list[tuple[float, frozenset[str], tuple[int, ...]]] = []
    for quando, texto in linhas:
        achou = _RE_ESCRITOR.search(texto)
        if not achou:
            continue
        nos = frozenset(
            n.strip().strip("'\"") for n in achou.group("nos").split(",") if n.strip()
        )
        pids: tuple[int, ...] = ()
        if "pids=" in texto:
            pids = tuple(int(p) for p in re.findall(r"\d+", texto.split("pids=")[-1]))
        achadas.append((quando, nos, pids))
    return achadas


def casar_escritores(
    nascimentos: Mapping[str, Nascimento],
    deteccoes: Iterable[tuple[float, frozenset[str], tuple[int, ...]]],
    janela_s: float = JANELA_DE_NASCIMENTO_S,
) -> dict[str, Nascimento]:
    """Casa cada detecção de escritor com o nascimento a que ela pertence.

    Função PURA, e separada de propósito: é aqui que mora a única regra
    delicada deste arquivo, e uma regra que só se exercita com relógio de
    mentira não pode viver dentro de um ``subprocess``.

    O casamento exige as DUAS coisas — mesmo nó **e** dentro da janela. Só o nó
    contaminaria a instância viva com o pecado da morta (o ``hidraw6`` foi da
    ``.0028`` e depois da ``.0033`` no mesmo dia); só a janela contaminaria os
    irmãos que sobem juntos (a ``.0033`` e a ``.0034`` nasceram com 2,7 s de
    diferença, dentro da janela uma da outra).
    """
    casados = dict(nascimentos)
    for quando, nos, pids in deteccoes:
        for chave, nasc in list(casados.items()):
            if nasc.no in nos and -1.0 <= quando - nasc.quando <= janela_s:
                casados[chave] = Nascimento(
                    instancia=nasc.instancia,
                    quando=nasc.quando,
                    no=nasc.no,
                    transporte=nasc.transporte,
                    escritor=pids,
                    sujo=True,
                )
    return casados


def _recorte_do_diario(desde_s: float) -> list[str]:
    """O ``-S @<epoch>`` que corta o passado. Lista vazia = lê tudo.

    O ``@<segundos>`` é a forma que não passa por locale — a mesma razão pela
    qual o carimbo de tempo sai do ``__REALTIME_TIMESTAMP`` e nunca do texto
    formatado.
    """
    if desde_s <= 0:
        return []
    return ["-S", f"@{int(time.time() - float(desde_s))}"]


def _linhas_do_diario(
    argv: Sequence[str], orcamento_s: float
) -> list[tuple[float, str]] | None:
    """``journalctl -o json`` -> [(epoch, mensagem)]. ``None`` = não deu para ler.

    O timestamp sai de ``__REALTIME_TIMESTAMP`` (microssegundos, numérico) e
    NUNCA do texto formatado: o formato curto é localizado — nesta máquina o mês
    sai ``ago`` —, e uma régua que depende de locale é régua que mente em outra
    máquina.
    """
    try:
        proc = subprocess.run(
            list(argv),
            capture_output=True,
            timeout=orcamento_s,
            check=False,
            text=True,
        )
    except (OSError, subprocess.SubprocessError):
        return None
    if proc.returncode != 0:
        return None
    linhas: list[tuple[float, str]] = []
    for linha in proc.stdout.splitlines():
        try:
            evento = json.loads(linha)
        except (ValueError, TypeError):
            continue
        mensagem = evento.get("MESSAGE")
        if not isinstance(mensagem, str):
            continue
        with contextlib.suppress(TypeError, ValueError):
            linhas.append((int(evento["__REALTIME_TIMESTAMP"]) / 1e6, mensagem))
    return linhas


def ler_a_mesa(
    *,
    instancias: Sequence[Instancia] | None = None,
    nascimentos: Mapping[str, Nascimento] | None = None,
    raiz_uhid: str = RAIZ_UHID,
    leitor: LeitorDeDiario | None = None,
) -> list[Leitura]:
    """DIAGNÓSTICO: cada instância viva nasceu limpa?

    Esta é a pergunta que o produto precisa para SABER QUANDO oferecer a cura.
    Ela não prevê o futuro e não olha quem segura o nó agora — uma instância
    suja continua suja depois de a Steam morrer, que foi exatamente o estado da
    bancada dela às 20h de 22/08/2026.
    """
    alvos = list(instancias) if instancias is not None else instancias_dualsense(raiz_uhid)
    if nascimentos is None:
        nascimentos = (leitor or nascimentos_pelo_diario)()
    return [_veredito(alvo, nascimentos) for alvo in alvos]


def _veredito(
    alvo: Instancia, nascimentos: Mapping[str, Nascimento] | None
) -> Leitura:
    if not alvo.no_radio:
        # MEDIDO 03/08/2026 e reconfirmado 11/08: pelo cabo a barra sempre
        # obedeceu — "os dois do cabo acenderam branco" com o daemon parado. O
        # travamento é do claim por rádio, e o cabo não tem claim.
        return Leitura(
            alvo=alvo,
            confianca=CONFIANCA_LIMPA,
            porque="no cabo — o travamento é do rádio, e pelo cabo a barra sempre obedeceu",
        )
    if nascimentos is None:
        return Leitura(
            alvo=alvo,
            confianca=CONFIANCA_NAO_SEI,
            porque=(
                "o diário do sistema não pôde ser lido — sem ele não dá "
                "para saber como esta conexão nasceu"
            ),
        )
    nasc = nascimentos.get(alvo.instancia.lower())
    if nasc is None:
        return Leitura(
            alvo=alvo,
            confianca=CONFIANCA_NAO_SEI,
            porque=(
                "esta conexão é mais velha que o diário desta sessão — "
                "não dá para saber como ela nasceu"
            ),
        )
    if nasc.sujo:
        quantos = len(nasc.escritor)
        quem = f"{quantos} processo(s)" if quantos else "outro processo"
        return Leitura(
            alvo=alvo,
            confianca=CONFIANCA_SUSPEITA,
            porque=(
                f"nasceu com {quem} segurando o nó do controle — nesta "
                "condição a barra não obedece, e só a reconexão devolve"
            ),
            pids_do_escritor=nasc.escritor,
            nasceu_em=nasc.quando,
        )
    if not nasc.escritor_conhecido:
        # O kernel disse QUANDO ela nasceu e o diário do daemon não disse QUEM
        # segurava. Meia régua não absolve ninguém.
        return Leitura(
            alvo=alvo,
            confianca=CONFIANCA_NAO_SEI,
            porque=(
                "o kernel registrou o nascimento desta conexão, mas o diário do "
                "daemon não pôde ser lido — não dá para saber se alguém segurava "
                "o nó na hora"
            ),
            nasceu_em=nasc.quando,
        )
    return Leitura(
        alvo=alvo,
        confianca=CONFIANCA_LIMPA,
        porque="nasceu com o nó livre — nenhuma disputa registrada no nascimento",
        nasceu_em=nasc.quando,
    )


class CartorioDoNascimento:
    """Guarda, POR INSTÂNCIA, o veredito de como cada conexão nasceu.

    ``SINAL-NO-NASCIMENTO-01``. O produto já sabia responder *"esta instância
    nasceu limpa?"* e só sabia responder **enquanto o diário ainda tivesse a
    linha**. O cartório é a memória: quem carimba é o tique de hotplug, na hora
    em que a conexão nasce, e quem pergunta depois não paga ``journalctl``
    nenhum.

    A CHAVE É A INSTÂNCIA, E NÃO O CONTROLE
    =======================================
    O que foi medido em 22/08/2026 é que **o defeito é da CONEXÃO**: matar a
    Steam não cura, e a mesma peça de plástico dá uma instância travada às
    18h06 e uma sã às 19h51. Guardar o veredito por controle apagaria
    exatamente a distinção que a medição produziu. Por isso a chave primária é
    o sufixo ``.NNNN`` que o HID core atribui — que não se repete enquanto a
    máquina não reinicia.

    E o que serve de chave para ACHAR o carimbo de um controle na tela é o
    ``uniq`` (:meth:`do_uniq`), que é o endereço com que o resto do produto já
    chama cada controle (``nos_hidraw_por_uniq``, o alvo de edição de
    ``app/alvo_de_edicao.py``).
    **Não é o ``hw_version``**, e isso está medido: a canônica de 15/08/2026
    registra que ele é *revisão de placa* e que *"dois controles da mesma cor
    comprados juntos teriam o mesmo valor"* — ele separa os quatro aparelhos
    dela **por acaso de lote**. Ele fica no carimbo como chave de diagnóstico
    (:meth:`do_hw_version`, que por isso devolve uma LISTA), nunca como
    identidade.

    Não lê relógio: recebe ``agora`` de fora, como o
    ``SentinelaDeEscritorCru`` e o ``GatilhoDeFimDeSequencia``.
    """

    def __init__(self, *, janela_s: float = JANELA_DE_NASCIMENTO_S) -> None:
        self._janela_s = float(janela_s)
        self._carimbos: dict[str, Carimbo] = {}
        #: ``instancia -> (visto_em, nasceu_sob_nossos_olhos)``.
        self._vistas: dict[str, tuple[float, bool]] = {}
        self._ja_observou = False

    def observar(
        self, instancias: Iterable[Instancia], agora: float
    ) -> list[Instancia]:
        """Anota quem está na mesa e devolve **quem ainda falta carimbar firme**.

        Lista vazia é a resposta cara de produzir e barata de dar: é ela que
        autoriza o tique de hotplug a NÃO ler o diário. Mesa parada = zero
        subprocessos.

        Instância que sumiu é esquecida, e isso é o desenho: o carimbo morre
        com a conexão a que pertence, porque é dela que o defeito é.
        """
        vivas: dict[str, Instancia] = {}
        for alvo in instancias:
            vivas[alvo.instancia.lower()] = alvo
        for morta in [c for c in self._carimbos if c not in vivas]:
            del self._carimbos[morta]
        for morta in [v for v in self._vistas if v not in vivas]:
            del self._vistas[morta]
        for chave in vivas:
            if chave not in self._vistas:
                self._vistas[chave] = (float(agora), self._ja_observou)
        self._ja_observou = True
        return [
            alvo
            for chave, alvo in vivas.items()
            if not (chave in self._carimbos and self._carimbos[chave].firme)
        ]

    def carimbar(
        self,
        leituras: Iterable[Leitura],
        agora: float,
        *,
        nos_segurados: Collection[str] = (),
    ) -> list[Carimbo]:
        """Grava o veredito de cada leitura e devolve os carimbos gravados.

        Duas regras, e as duas são de uma direção só:

        - **suspeita não volta atrás.** O diário só GANHA linhas; uma leitura
          posterior que não ache a prova não absolve quem já foi condenado, e
          um carimbo suspeito nasce firme (não há o que reconferir);
        - **a sonda ao vivo só AGRAVA.** ``nos_segurados`` é a segunda régua, a
          de primeira mão: o nó desta instância está segurado AGORA. Ela só é
          aceita enquanto a janela de nascimento não fechou **e** só para quem
          o cartório viu aparecer — numa instância que já estava na mesa antes
          de o daemon subir, "alguém segura o nó agora" não diz nada sobre como
          ela nasceu, e usá-la produziria a acusação falsa que gasta o gesto do
          botão PS dela à toa.
        """
        gravados: list[Carimbo] = []
        for leitura in leituras:
            chave = leitura.alvo.instancia.lower()
            visto_em, sob_olhos = self._vistas.get(chave, (float(agora), False))
            fechou = (float(agora) - visto_em) >= self._janela_s
            final = leitura
            if (
                not final.pede_reconexao
                and sob_olhos
                and not fechou
                and leitura.alvo.hidraw
                and leitura.alvo.hidraw in nos_segurados
                and leitura.alvo.no_radio
            ):
                final = replace(
                    final,
                    confianca=CONFIANCA_SUSPEITA,
                    porque=(
                        "nasceu com outro processo segurando o nó do controle "
                        "(visto pela sonda do próprio daemon, no tique em que a "
                        "conexão apareceu) — nesta condição a barra não obedece, "
                        "e só a reconexão devolve"
                    ),
                )
            antigo = self._carimbos.get(chave)
            if antigo is not None and antigo.pede_reconexao:
                final = antigo.leitura
            carimbo = Carimbo(
                leitura=final,
                visto_em=visto_em,
                carimbado_em=float(agora),
                firme=(
                    fechou or final.pede_reconexao or not final.alvo.no_radio
                ),
                nasceu_sob_nossos_olhos=sob_olhos,
            )
            self._carimbos[chave] = carimbo
            gravados.append(carimbo)
        return gravados

    def da_instancia(self, instancia: str) -> Carimbo | None:
        """O carimbo desta conexão, ou ``None`` — que quer dizer "não carimbei"."""
        return self._carimbos.get(str(instancia).lower())

    def do_uniq(self, uniq: str) -> Carimbo | None:
        """O carimbo do controle com este endereço. É por aqui que a tela pergunta.

        Um controle só tem UMA conexão viva por vez, então não há ambiguidade —
        e as conexões mortas já foram esquecidas por :meth:`observar`.
        """
        alvo = str(uniq).lower()
        for carimbo in self._carimbos.values():
            if carimbo.uniq.lower() == alvo:
                return carimbo
        return None

    def do_hw_version(self, hw_version: str) -> list[Carimbo]:
        """Os carimbos das conexões cuja placa tem esta revisão. **Lista**, e de propósito.

        O ``hw_version`` é revisão de placa, não número de série (canônica,
        MEDIDO 15/08/2026). Devolver um só esconderia a colisão de dois
        controles do mesmo lote e faria a tela mostrar o veredito do controle
        errado.
        """
        alvo = str(hw_version).lower()
        return [c for c in self._carimbos.values() if c.hw_version.lower() == alvo]

    def todos(self) -> list[Carimbo]:
        """Todos os carimbos vivos, na ordem das instâncias."""
        return [self._carimbos[c] for c in sorted(self._carimbos)]

    def condenados(self) -> list[Carimbo]:
        """Só as conexões que nasceram condenadas — as que a cura alcança."""
        return [c for c in self.todos() if c.pede_reconexao]


def limpo_para_conectar(
    *, sonda: Sonda | None = None
) -> tuple[str, str, tuple[int, ...]]:
    """PROGNÓSTICO: se um controle conectar AGORA, ele nasce limpo?

    É esta — e não :func:`ler_a_mesa` — que tem de guardar o botão de
    reconectar. Oferecer a cura com a mesa suja gasta o gesto do botão PS dela
    para produzir outra instância travada, que é a forma exata do "falso
    positivo recorrente" que ela nomeou em 12/08/2026.

    Devolve ``(confianca, porque, pids)``. ``CONFIANCA_NAO_SEI`` quando a sonda
    não pôde rodar — e aí o produto pode até oferecer a cura, mas tem de dizer
    que não conferiu.
    """
    if sonda is None:
        try:
            from hefesto_dualsense4unix.core.escritor_cru import holders_de_hidraw
        except ImportError:
            return (
                CONFIANCA_NAO_SEI,
                "a sonda de quem segura o nó não está disponível nesta instalação",
                (),
            )
        sonda = holders_de_hidraw
    try:
        segurados = sonda(None)
    except OSError:  # a sonda é best-effort por contrato: /proc pode sumir
        return (CONFIANCA_NAO_SEI, "a sonda de quem segura o nó falhou", ())
    pids = tuple(sorted({p for lista in segurados.values() for p in lista}))
    if pids:
        return (
            CONFIANCA_SUSPEITA,
            "outro processo está segurando nó de controle agora — reconectar "
            "nesta condição faz a conexão nova nascer travada igual",
            pids,
        )
    return (
        CONFIANCA_LIMPA,
        "nenhum outro processo está segurando nó de controle — é hora boa de reconectar",
        (),
    )


def relatorio(leituras: Sequence[Leitura]) -> str:
    """O relatório de terminal. Sem endereço inteiro, por causa do retrato."""
    if not leituras:
        return "Nenhum DualSense conectado."
    marca = {
        CONFIANCA_LIMPA: "●",
        CONFIANCA_SUSPEITA: "▲",
        CONFIANCA_NAO_SEI: "○",
    }
    linhas = []
    for leitura in leituras:
        linhas.append(
            f"{marca.get(leitura.confianca, '○')} {leitura.alvo.apelido}: {leitura.porque}"
        )
    suspeitas = sum(1 for leitura in leituras if leitura.pede_reconexao)
    if suspeitas:
        linhas.append("")
        linhas.append(
            f"{suspeitas} conexão(ões) suspeita(s). A cura medida é reconectar: "
            "Disconnect pelo BlueZ (não precisa de sudo) e o botão PS — MAS só "
            "com a mesa limpa, senão a conexão nova nasce travada igual."
        )
    return "\n".join(linhas)


def main(argv: Sequence[str] | None = None) -> int:
    """CLI do sinal da barra — a mesma leitura que a aba mostraria."""
    analisador = argparse.ArgumentParser(
        prog="sinal-da-barra",
        description=(
            "Diz se cada DualSense conectado nasceu com o nó disputado. "
            "NÃO lê a lâmpada: nenhuma leitura de lâmpada existe."
        ),
    )
    analisador.add_argument("--json", action="store_true", help="saída de máquina")
    analisador.add_argument(
        "--agora",
        action="store_true",
        help="responde só 'é hora boa de reconectar?' (prognóstico)",
    )
    opcoes = analisador.parse_args(argv)

    if opcoes.agora:
        confianca, porque, pids = limpo_para_conectar()
        if opcoes.json:
            print(
                json.dumps(
                    {"confianca": confianca, "porque": porque, "pids": list(pids)},
                    ensure_ascii=False,
                )
            )
        else:
            print(f"{confianca}: {porque}")
        return 0 if confianca == CONFIANCA_LIMPA else 1

    leituras = ler_a_mesa()
    if opcoes.json:
        print(
            json.dumps(
                [
                    {
                        "instancia": leitura.alvo.instancia,
                        "uniq": mascarar(leitura.alvo.uniq),
                        "transporte": leitura.alvo.transporte,
                        "hw_version": leitura.alvo.hw_version,
                        "confianca": leitura.confianca,
                        "porque": leitura.porque,
                    }
                    for leitura in leituras
                ],
                ensure_ascii=False,
                indent=2,
            )
        )
    else:
        print(relatorio(leituras))
    return 1 if any(leitura.pede_reconexao for leitura in leituras) else 0


if __name__ == "__main__":
    sys.exit(main())
