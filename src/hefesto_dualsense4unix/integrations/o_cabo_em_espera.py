"""o_cabo_em_espera.py — o controle do rádio que ganhou cabo, e o kernel deixou esperando.

O-CABO-ASSUME-DO-RADIO-01 (25/09/2026). Ela plugou no USB um controle que
estava pelo rádio, e ele *«segue conectado no modo bt mas agora segue
carregando»*. <!-- noqa-acento: citação literal dela -->

POR QUE O RÁDIO FICAVA — medido na mesa dela, 25/09/2026, 19:42
----------------------------------------------------------------

O daemon nunca escolheu o rádio: ele nem chegou a ver o cabo. O kernel
enumerou o aparelho USB, o ``hid-playstation`` leu o endereço do controle e
recusou o segundo registro do MESMO endereço::

    usb 3-4.1.3: New USB device found, idVendor=054c, idProduct=0ce6
    playstation 0003:054C:0CE6.001B: hidraw1: USB HID v1.11 Gamepad [...]
    playstation 0003:054C:0CE6.001B: Duplicate device found for MAC address …
    playstation 0003:054C:0CE6.001B: probe with driver playstation failed with error -17

O ``-17`` é ``-EEXIST``, de ``ps_devices_list_add`` (o comentário do próprio
driver: *"which can happen if the same device is connected using both
Bluetooth and USB"*). O HID do cabo fica em ``/sys/bus/hid/devices`` SEM
driver — sem ``hidraw``, sem ``input``, sem LED —, o áudio do cabo sobe
(``snd-usb-audio`` nas interfaces 0 a 2) e a bateria passa a carregar pelo
rádio. É exatamente o que ela viu.

A CURA, EM TRÊS MÃOS
--------------------

1. **este módulo** acha o cabo que espera (:func:`cabos_em_espera`) e o par
   dele no rádio — pela linha do kernel, que traz o endereço
   (:func:`enderecos_recusados`), ou, quando o diário não se deixa ler, pela
   borda da carga (:meth:`VigiaDoCabo.decidir`);
2. **o laço do daemon** (``daemon/connection.vigiar_o_cabo_em_espera``) marca a
   troca no backend e derruba o RÁDIO daquele controle (``Disconnect``, o
   pareamento fica) — medido, é o único jeito de o controle falar pelo cabo;
3. **a regra udev** ``assets/85-hefesto-o-cabo-assume.rules`` religa, como
   root, o HID que esperava, no instante em que o gêmeo sai do barramento.

Nenhum recado na tela, nenhum botão: o controle passa a dizer USB na aba
Conexões, com o mesmo número. Tirou o cabo, ele volta pelo rádio sozinho, no
adaptador de sempre (o pareamento nunca saiu), e o lugar espera por ele
(``backend_pydualsense._segurar_a_volta_pelo_radio_locked``).

AUSÊNCIA É RESPOSTA
-------------------

Sem a regra que religa o cabo, derrubar o rádio deixaria o controle em lugar
nenhum. Então o produto não derruba, e diz por quê (:func:`impedimentos_da_troca`).
Sem o diário do kernel e sem uma borda de carga que aponte UM controle, ele
também não age: derrubar o rádio de outra pessoa é o pior erro possível, e
ficar no rádio carregando é o comportamento de antes.
"""

from __future__ import annotations

import os
import re
import subprocess
from collections.abc import Callable, Iterable, Mapping
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any

from hefesto_dualsense4unix.utils.logging_config import get_logger

logger = get_logger(__name__)

#: Onde o kernel lista os aparelhos HID. Resolvido NA CHAMADA: a suíte o aponta
#: para uma pasta vazia (``tests/conftest.py``), e sem isso ela enxergaria o
#: cabo que espera na mesa dela.
RAIZ_DO_BARRAMENTO_HID = "/sys/bus/hid/devices"

#: A regra udev que religa o cabo quando o gêmeo sai (``assets/``). Os três
#: lugares onde um instalador a põe: o ``install_udev.sh`` e o pacote.
NOME_DA_REGRA = "85-hefesto-o-cabo-assume.rules"
REGRAS_QUE_RELIGAM: tuple[str, ...] = (
    f"/etc/udev/rules.d/{NOME_DA_REGRA}",
    f"/usr/lib/udev/rules.d/{NOME_DA_REGRA}",
    f"/lib/udev/rules.d/{NOME_DA_REGRA}",
)

#: O HID de um DualSense (comum ou Edge) NO CABO: barramento 0003, Sony 054C.
_FORMA_DO_CABO = re.compile(r"^0003:054C:(0CE6|0DF2)\.[0-9A-F]{4}$")

#: A linha do kernel que diz QUEM esperava: a instância e o endereço recusado.
_LINHA_DA_RECUSA = re.compile(
    r"(?P<inst>[0-9A-Fa-f]{4}:[0-9A-Fa-f]{4}:[0-9A-Fa-f]{4}\.[0-9A-Fa-f]{4}): "
    r"Duplicate device found for MAC address (?P<mac>[0-9A-Fa-f]{2}(?::[0-9A-Fa-f]{2}){5})"
)

#: Os estados de carga que só existem com energia de fora (``ESTADO_DE_CARGA``
#: do backend, a tabela do kernel). ``descarregando`` é bateria pura.
CARGA_DE_FORA = frozenset({"carregando", "cheio", "fora_de_faixa", "erro"})

#: Quanto um HID do cabo precisa ficar sem driver para ser chamado de órfão
#: quando o diário não fala. A probe do ``hid-playstation`` no cabo leva menos
#: de um segundo (os retries do DKMS no cabo são de 100 ms); cinco segundos
#: separam "ainda subindo" de "recusado" sem deixar ninguém esperando à toa.
ESPERA_PARA_SER_ORFAO_S = 5.0

#: A borda da carga (descarregando → energia de fora) e o cabo que aparece são
#: o MESMO gesto — plugar. Medido em 25/09/2026: o USB enumerou às 19:42:14 e o
#: HID recusado nasceu às 19:42:28. Um minuto cabe os dois com folga e deixa de
#: fora o controle que está na base de carga desde antes.
JANELA_DO_PAR_PELA_CARGA_S = 60.0

#: Uma derrubada de rádio por controle nesta janela. Sem teto, um cabo que o
#: kernel recusasse por outro motivo faria o produto derrubar o rádio em laço.
TETO_POR_CONTROLE_S = 120.0

#: O teto do ``journalctl``. Medido na mesa dela: 0,18 s para o boot inteiro.
ESPERA_DO_DIARIO_S = 3.0

#: Quem assina a escrita no BlueZ (a trava e o diário do rádio).
QUEM = "o-cabo-assume"


@dataclass(frozen=True)
class CaboEmEspera:
    """Um HID de DualSense no cabo, sem driver: o que o kernel deixou esperando."""

    instancia: str


@dataclass(frozen=True)
class Decisao:
    """O par de um cabo no rádio — ou por que não há par."""

    par: str | None = None
    fonte: str = ""
    motivo: str = ""
    #: ``True`` quando não adianta tentar de novo (o cabo não é um gêmeo).
    desistir: bool = False


def mac_de_12(valor: object) -> str | None:
    """O endereço em 12 hex minúsculos (a forma do backend), ou ``None``."""
    if not isinstance(valor, str):
        return None
    hexa = re.sub(r"[^0-9a-fA-F]", "", valor).lower()
    return hexa if len(hexa) == 12 else None


def mac_com_dois_pontos(uniq: str) -> str:
    """``aabbcc0000ff`` → ``aa:bb:cc:00:00:ff`` (a forma do BlueZ)."""
    return ":".join(uniq[i : i + 2] for i in range(0, 12, 2))


def mascarar(uniq: str | None) -> str | None:
    """A máscara da casa para o diário: os octetos 4 e 5 zerados."""
    if not uniq or len(uniq) != 12:
        return None
    return uniq[:6] + "0000" + uniq[10:]


# --- as leituras (I/O; cada uma degrada para vazio, nunca levanta) ------------


def cabos_em_espera(raiz: str | os.PathLike[str] | None = None) -> list[CaboEmEspera]:
    """Os HID de DualSense no cabo que estão SEM driver agora.

    Custo: um ``listdir`` e um ``stat`` por HID da Sony no cabo — microssegundos.
    O vpad do produto nasce por ``uhid`` com barramento 0003 também, mas mora em
    ``/devices/virtual/`` e fica fora por construção: ele não tem cabo nenhum.
    """
    base = Path(RAIZ_DO_BARRAMENTO_HID if raiz is None else raiz)
    try:
        nomes = sorted(os.listdir(base))
    except OSError:
        return []
    achados: list[CaboEmEspera] = []
    for nome in nomes:
        if not _FORMA_DO_CABO.match(nome):
            continue
        caminho = base / nome
        if (caminho / "driver").exists():
            continue
        if "/devices/virtual/" in os.path.realpath(caminho):
            continue
        achados.append(CaboEmEspera(instancia=nome))
    return achados


def enderecos_recusados(texto: str) -> dict[str, str]:
    """``{instância: endereço 12-hex}`` das recusas por endereço repetido. Pura.

    A ÚLTIMA linha de cada instância vale: a mesma instância recusada duas
    vezes (uma religada que também recusou) diz o mesmo endereço.
    """
    achados: dict[str, str] = {}
    for linha in texto.splitlines():
        casou = _LINHA_DA_RECUSA.search(linha)
        if casou is None:
            continue
        endereco = mac_de_12(casou.group("mac"))
        if endereco is not None:
            achados[casou.group("inst").upper()] = endereco
    return achados


def ler_o_diario_do_kernel(
    executor: Callable[[list[str]], str | None] | None = None,
) -> str | None:
    """O texto do diário do kernel deste boot, ou ``None`` se não deu para ler.

    ``journalctl -k`` lê o diário do SISTEMA, e a usuária só o lê quando está no
    grupo que o systemd libera (``adm``, ``systemd-journal`` ou ``wheel``). Sem
    permissão ele não falha: devolve vazio. Por isso vazio também é ``None`` —
    todo boot tem linha de kernel, e "não achei a recusa" num diário que não se
    deixou ler seria mentira.
    """
    comando = ["journalctl", "-k", "-b", "-o", "cat", "--no-pager"]
    if executor is not None:
        texto = executor(comando)
        return texto or None
    ambiente = dict(os.environ)
    ambiente["LC_ALL"] = "C"
    try:
        feito = subprocess.run(
            comando,
            capture_output=True,
            text=True,
            timeout=ESPERA_DO_DIARIO_S,
            check=False,
            env=ambiente,
        )
    except (OSError, subprocess.SubprocessError):
        return None
    return feito.stdout or None


def impedimentos_da_troca(regras: Iterable[str] | None = None) -> list[str]:
    """Por que o produto não pode derrubar o rádio agora. Vazio = pode.

    ``None`` lê ``REGRAS_QUE_RELIGAM`` NA CHAMADA, e não na definição: um
    default amarrado à tupla de quando o módulo carregou não deixaria a régua
    apontar para a regra de mentira, e ela mediria o ``/etc`` da máquina.
    """
    alvos = REGRAS_QUE_RELIGAM if regras is None else regras
    if any(Path(regra).exists() for regra in alvos):
        return []
    from hefesto_dualsense4unix.utils.repo_files import como_atualizar_esta_instalacao

    return [
        f"a regra que religa o cabo ({NOME_DA_REGRA}) não está instalada — sem ela "
        f"o controle ficaria sem rádio e sem cabo; {como_atualizar_esta_instalacao()}"
    ]


def derrubar_o_radio(uniq: str, leitor: Any = None) -> tuple[bool, str]:
    """``Disconnect`` do controle ``uniq`` em todo adaptador onde ele está ligado.

    O pareamento FICA: é ele que traz o controle de volta pelo rádio, no mesmo
    adaptador, quando o cabo sair. ``(feito, motivo)``; nunca levanta. O leitor
    é o dono do BlueZ (``bluez_dbus.dono()``), que já traz a trava do rádio, o
    diário comum e a recusa quando a suíte está no ar.
    """
    if leitor is None:
        from hefesto_dualsense4unix.integrations import bluez_dbus

        leitor = bluez_dbus.dono()
    try:
        aparelhos = leitor.aparelhos()
    except Exception as erro:
        return False, f"o BlueZ não respondeu: {erro}"
    if aparelhos is None:
        return False, "não deu para perguntar ao BlueZ"
    endereco = mac_com_dois_pontos(uniq)
    ligados = [a for a in aparelhos if a.endereco == endereco and a.conectado]
    if not ligados:
        return False, "o BlueZ não tem este controle conectado"
    motivos: list[str] = []
    feito = False
    for aparelho in ligados:
        try:
            escrita = leitor.desconectar(aparelho.caminho, quem=QUEM)
        except Exception as erro:
            motivos.append(str(erro))
            continue
        if escrita.feita:
            feito = True
        else:
            motivos.append(escrita.mensagem or escrita.erro or "o BlueZ recusou")
    return feito, "; ".join(motivos)


# --- a regra (o tempo mora aqui) --------------------------------------------


@dataclass
class VigiaDoCabo:
    """Guarda desde quando cada cabo espera e a borda da carga de cada controle.

    Uma por daemon (``connection.vigia_do_cabo_de``). O relógio entra por
    argumento: a régua viaja no tempo sem dormir.
    """

    #: instância -> quando o cabo foi visto esperando pela primeira vez.
    visto_em: dict[str, float] = field(default_factory=dict)
    #: instâncias já resolvidas (tentadas ou desistidas) — não se olha de novo.
    resolvidos: set[str] = field(default_factory=set)
    #: uniq -> quando a energia de fora chegou (``None`` = já estava quando
    #: começamos a olhar: não é borda, é a base de carga de sempre).
    carga_de_fora_desde: dict[str, float | None] = field(default_factory=dict)
    #: uniq -> quando o produto derrubou o rádio dele pela última vez.
    derrubado_em: dict[str, float] = field(default_factory=dict)
    #: as frases já ditas ao diário, para cada uma sair UMA vez.
    avisados: set[str] = field(default_factory=set)
    #: quando o laço olhou os cabos pela última vez (``None`` = nunca).
    ultima_olhada: float | None = None
    _cargas_vistas: dict[str, str | None] = field(default_factory=dict)

    def observar_a_carga(self, no_radio: Mapping[str, str | None], agora: float) -> None:
        """Anota a borda da energia de fora de cada controle no rádio."""
        for uniq, estado in no_radio.items():
            de_fora = estado in CARGA_DE_FORA
            if not de_fora:
                self.carga_de_fora_desde.pop(uniq, None)
            elif uniq not in self.carga_de_fora_desde:
                anterior = self._cargas_vistas.get(uniq, "nunca visto")
                self.carga_de_fora_desde[uniq] = agora if anterior == "descarregando" else None
            self._cargas_vistas[uniq] = estado
        for uniq in [u for u in self._cargas_vistas if u not in no_radio]:
            self._cargas_vistas.pop(uniq, None)
            self.carga_de_fora_desde.pop(uniq, None)

    def observar_os_cabos(self, cabos: Iterable[CaboEmEspera], agora: float) -> list[CaboEmEspera]:
        """Os cabos a decidir agora. Quem sumiu é esquecido; quem já foi resolvido, pulado."""
        vivos = {cabo.instancia: cabo for cabo in cabos}
        self.ultima_olhada = agora
        for instancia in [i for i in self.visto_em if i not in vivos]:
            self.visto_em.pop(instancia, None)
            self.resolvidos.discard(instancia)
        pendentes: list[CaboEmEspera] = []
        for instancia, cabo in vivos.items():
            self.visto_em.setdefault(instancia, agora)
            if instancia not in self.resolvidos:
                pendentes.append(cabo)
        return pendentes

    def quer_olhar_de_novo(self, agora: float) -> bool:
        """Algum cabo pendente ficou maduro DEPOIS da última olhada?

        É o que encurta a espera do laço: sem isto, o cabo visto no tique do
        hotplug só seria decidido no fallback de 30 s. Responde sim UMA vez por
        cabo — a olhada seguinte já o vê maduro.
        """
        desde = self.ultima_olhada
        if desde is None:
            return False
        return any(
            instancia not in self.resolvidos
            and desde < visto + ESPERA_PARA_SER_ORFAO_S <= agora
            for instancia, visto in self.visto_em.items()
        )

    def decidir(
        self,
        cabo: CaboEmEspera,
        *,
        diario: Mapping[str, str] | None,
        no_radio: Mapping[str, str | None],
        agora: float,
    ) -> Decisao:
        """O par do cabo no rádio. Função do estado; não escreve em nada fora dela.

        - o diário do kernel deu o endereço: é ele, se estiver no rádio;
        - o diário se deixou ler e não fala deste cabo: ou a probe ainda está
          correndo (espera), ou ele não é gêmeo de ninguém (desiste);
        - o diário não se deixou ler: depois da espera, a borda da carga, se
          ela apontar UM controle só.
        """
        maduro = agora - self.visto_em.get(cabo.instancia, agora) >= ESPERA_PARA_SER_ORFAO_S
        if diario is not None:
            endereco = diario.get(cabo.instancia.upper())
            if endereco is None:
                if not maduro:
                    return Decisao(motivo="a probe do cabo ainda pode estar correndo")
                return Decisao(
                    motivo="o kernel não recusou este cabo por endereço repetido", desistir=True
                )
            if endereco not in no_radio:
                return Decisao(
                    motivo="o gêmeo deste cabo não é um controle do rádio na mesa", desistir=True
                )
            return self._com_teto(Decisao(par=endereco, fonte="diario_do_kernel"), agora)
        if not maduro:
            return Decisao(motivo="sem o diário do kernel, o cabo espera ficar órfão")
        visto = self.visto_em.get(cabo.instancia, agora)
        candidatos = [
            uniq
            for uniq, desde in self.carga_de_fora_desde.items()
            if uniq in no_radio
            and desde is not None
            and abs(desde - visto) <= JANELA_DO_PAR_PELA_CARGA_S
        ]
        if len(candidatos) != 1:
            return Decisao(
                motivo=(
                    "sem o diário do kernel, e a borda da carga aponta "
                    f"{len(candidatos)} controles no rádio"
                ),
                desistir=True,
            )
        return self._com_teto(Decisao(par=candidatos[0], fonte="borda_da_carga"), agora)

    def _com_teto(self, decisao: Decisao, agora: float) -> Decisao:
        par = decisao.par
        ultima = self.derrubado_em.get(par, float("-inf")) if par is not None else None
        if ultima is not None and agora - ultima < TETO_POR_CONTROLE_S:
            return Decisao(motivo="o rádio deste controle já foi derrubado há pouco", desistir=True)
        return decisao

    def resolver(self, instancia: str) -> None:
        self.resolvidos.add(instancia)

    def derrubou(self, uniq: str, agora: float) -> None:
        self.derrubado_em[uniq] = agora

    def observar_quem_esta_no_cabo(self, no_cabo: Iterable[str]) -> None:
        """A troca que DEU CERTO solta o teto daquele controle.

        O teto existe para o laço — o rádio derrubado e o cabo que não sobe. O
        controle que aparece na mesa pelo cabo é a prova do contrário: a troca
        assumiu, e o próximo cabo plugado nele é gesto novo dela, não laço.
        Sem isto, tirar o cabo e pôr de novo dentro de dois minutos deixava o
        controle no rádio carregando — a queixa de 25/09, de volta pela porta
        da própria cura (conferência de 25/09/2026).
        """
        for uniq in no_cabo:
            self.derrubado_em.pop(uniq, None)

    def primeira_vez(self, frase: str) -> bool:
        """``True`` só na primeira vez que a frase aparece — o diário não vira tapete."""
        if frase in self.avisados:
            return False
        self.avisados.add(frase)
        return True


__all__ = [
    "CARGA_DE_FORA",
    "ESPERA_PARA_SER_ORFAO_S",
    "JANELA_DO_PAR_PELA_CARGA_S",
    "NOME_DA_REGRA",
    "RAIZ_DO_BARRAMENTO_HID",
    "REGRAS_QUE_RELIGAM",
    "TETO_POR_CONTROLE_S",
    "CaboEmEspera",
    "Decisao",
    "VigiaDoCabo",
    "cabos_em_espera",
    "derrubar_o_radio",
    "enderecos_recusados",
    "impedimentos_da_troca",
    "ler_o_diario_do_kernel",
    "mac_com_dois_pontos",
    "mac_de_12",
    "mascarar",
]
