"""conexao_zumbi.py — o controle que conecta e NÃO vira controle.

CONEXAO-ZUMBI-01 (18/09/2026). Ela abriu o produto com dois DualSense ligados e
disse quatro coisas: *"com dois ou mais controles conectados a interface do app
para de funcionar"*, *"o lightbar tá sem a solução"*, *"a mudança dos leds e
afins não foram aplicadas pros demais controles"*, *"ambos conectados, ambos
como player 1 e ambos com lightbar azul"*.

As quatro são UMA causa só, medida às 11h55::

    hcitool con        -> dois ACL de pé
    /sys/class/hidraw  -> UM DualSense
    bluetoothctl       -> o BlueZ conhece UM

O segundo controle tinha **conexão de rádio de pé e nenhum registro no
BlueZ**: sem device, sem HID, sem ``hidraw``, sem nó de LED, sem bateria, sem
microfone, sem placa de som. O controle fica no padrão de fábrica — barra azul
e jogador 1 —, que é exatamente o que ela descreveu. E a interface estava viva
(250 voltas em 25 s): o que morreu foi o CONTROLE.

A ordem dela é o que este módulo existe para cumprir:

    *"apresentei um sintoma de algo que deve ser tratado na origem como produto
    como um todo. isso não é a ação esperada e o produto precisa ser inteligente
    pra evitar problemas como esse."*

AS TRÊS CONDIÇÕES, E AS TRÊS SÃO NECESSÁRIAS
---------------------------------------------

Um link só é ZUMBI quando, ao mesmo tempo:

1. **há um ACL de pé** naquele adaptador (:func:`links_de_pe`);
2. **nenhum ``hidraw`` tem esse endereço** em ``HID_UNIQ``
   (:func:`uniqs_com_hid`);
3. **o BlueZ não tem objeto ``org.bluez.Device1``** para esse endereço naquele
   adaptador (:func:`enderecos_que_o_bluez_conhece`).

A TERCEIRA É A TRAVA DE SEGURANÇA, e é ela que torna a cura barata. Um ACL sem
objeto no BlueZ **não serve a ninguém**: não há perfil, não há áudio, não há
entrada, não há bateria — nenhum consumidor da máquina alcança aquele link.
Derrubá-lo não pode interromper nada que esteja funcionando, porque nada está
funcionando por ele. O fone, o mouse, o celular e o teclado dela têm objeto no
BlueZ enquanto conectados, e por isso ficam FORA por construção — sem lista de
OUI, sem casar por nome, sem depender da bancada dela.

A terceira é também o que separa este defeito do **"conectado sem hidraw"** que
o ``scripts/doctor.sh`` já pega (``check_bt_connected_sem_hidraw``): lá o BlueZ
CONHECE o device, e a cura é outra — o cache SDP envenenado (SDP-CACHE-01), que
não se resolve derrubando link nenhum.

O TEMPO É PARTE DA REGRA
-------------------------

Uma régua que olha UMA vez mede um instante, não um comportamento: todo
controle passa alguns instantes com ACL de pé e sem HID enquanto o perfil sobe.
Por isso :class:`VigiaDeZumbis` só chama de zumbi o link que se mantém nas três
condições por :data:`SEGUNDOS_PARA_ZUMBI` **seguidos**, medidos em observações
sucessivas — e o relógio entra por argumento, para a régua poder viajar no
tempo sem dormir.

A CURA TEM TETO
----------------

No máximo uma derrubada por controle a cada :data:`JANELA_DO_TETO_S`. Sem teto,
um controle que não consegue parear em adaptador nenhum entra em laço de
reconexão com o produto empurrando — e um laço que o produto alimenta é pior
que o zumbi parado.

AUSÊNCIA É RESPOSTA, NUNCA AÇÃO ÀS CEGAS
-----------------------------------------

Sem leitor de ACL, sem a ponte privilegiada instalada ou sem ``sudo -n``, o
vigia **não age e diz por quê** (:class:`Veredito.impedimentos`). É a mesma
regra do resto da casa: a recusa com motivo vai ao diário, e a tela tem de
mostrar o gesto — nunca uma recusa seca.
"""

from __future__ import annotations

import os
import re
import shutil
import subprocess
from collections.abc import Iterable, Mapping, Sequence
from dataclasses import dataclass, field
from pathlib import Path

from hefesto_dualsense4unix.utils.repo_files import como_atualizar_esta_instalacao
from hefesto_dualsense4unix.utils.logging_config import get_logger

logger = get_logger(__name__)

#: Quanto tempo um link precisa ficar nas três condições para virar zumbi.
#: Generoso de propósito: o objeto do BlueZ nasce no *connect complete*, e o
#: perfil HID sobe em seguida — segundos, não dezenas. O custo de esperar é um
#: controle mudo por mais um instante; o de não esperar é derrubar quem estava
#: quase subindo.
SEGUNDOS_PARA_ZUMBI = 20.0

#: Uma derrubada por controle por janela. Ver "A CURA TEM TETO".
JANELA_DO_TETO_S = 600.0

#: Raiz do sysfs dos adaptadores. Parametrizada porque a suíte roda contra uma
#: árvore de mentira — a de verdade é a mesa dela, com quatro DualSense de pé.
RAIZ_ADAPTADORES = "/sys/class/bluetooth"

#: Raiz dos nós hidraw. Mesma fonte de ``doctor.sh:_hidraw_uniqs``.
RAIZ_HIDRAW = "/sys/class/hidraw"

#: Onde o produto instala a ponte privilegiada (``install.sh``). Na árvore de
#: desenvolvimento ela ainda não existe, e isso é um impedimento declarado.
PONTE_INSTALADA = "/usr/local/lib/hefesto-dualsense4unix/bt_ponte_privilegiada.sh"

#: MAC e nada mais — a mesma forma que a ponte valida do lado de lá.
_FORMA_MAC = re.compile(r"^[0-9a-f]{2}(:[0-9a-f]{2}){5}$")

#: ``hciN`` e nada mais.
_FORMA_HCI = re.compile(r"^hci[0-9]+$")

#: Endereço dentro de uma linha do ``hcitool con``.
_MAC_NA_LINHA = re.compile(r"\b([0-9A-Fa-f]{2}(?::[0-9A-Fa-f]{2}){5})\b")

#: ``/org/bluez/hci0/dev_AA_BB_CC_DD_EE_FF``.
_NO_DO_BLUEZ = re.compile(r"^/org/bluez/(hci[0-9]+)/dev_([0-9A-Fa-f_]{17})$")


def mac_limpo(valor: str | None) -> str | None:
    """MAC em ``aa:bb:cc:dd:ee:ff`` minúsculo, ou ``None``.

    ESTRITA DE PROPÓSITO, e não usa ``core.sysfs_leds.norm_mac``: aquela
    recolhe os dígitos hex de QUALQUER texto (``norm_mac("/dev/hidraw4")``
    devolve ``'deda4'``, medido em 04/09/2026). Aqui o valor vira argumento de
    um comando privilegiado — o que não é um endereço tem de sair como
    ``None``, não como um endereço aproximado.
    """
    if not valor:
        return None
    texto = str(valor).strip().lower()
    return texto if _FORMA_MAC.match(texto) else None


@dataclass(frozen=True)
class LinkDeRadio:
    """Um ACL de pé: em QUAL adaptador, com QUAL endereço.

    O adaptador não é decoração. O rádio é por adaptador — ``hcitool dc`` sem
    ``-i`` cai no primeiro que o kernel rotear, e numa malha de três dongles
    isso derruba o link de outro adaptador, de quem estava jogando.
    """

    hci: str
    adaptador: str
    controle: str


@dataclass(frozen=True)
class Veredito:
    """O que o vigia viu nesta volta, e o que fez — ou por que não fez."""

    #: Links que estão nas três condições AGORA (ainda sem contar o tempo).
    suspeitos: tuple[LinkDeRadio, ...] = ()
    #: Suspeitos que já completaram :data:`SEGUNDOS_PARA_ZUMBI` seguidos.
    zumbis: tuple[LinkDeRadio, ...] = ()
    #: Zumbis cuja derrubada foi de fato pedida à ponte nesta volta.
    derrubados: tuple[LinkDeRadio, ...] = ()
    #: Zumbis que o TETO segurou, para não alimentar laço de reconexão.
    segurados_pelo_teto: tuple[LinkDeRadio, ...] = ()
    #: Por que o produto não agiu. Vazio = nada impede.
    impedimentos: tuple[str, ...] = ()
    #: Uma linha por acontecimento, na língua da casa — é o que vai ao diário
    #: e o que a aba Conexões tem de mostrar em vez de uma recusa seca.
    diario: tuple[str, ...] = ()

    @property
    def agiu(self) -> bool:
        return bool(self.derrubados)


# --- leitores (I/O; cada um degrada para vazio, nunca levanta) ---------------


def adaptadores_na_mesa(
    raiz: str | os.PathLike[str] = RAIZ_ADAPTADORES,
    *,
    executor: object = None,
) -> dict[str, str]:
    """``{hciN: MAC do adaptador}``, por uma escada de duas fontes.

    **A ESCADA NÃO É ZELO — o degrau de cima NÃO EXISTE nesta máquina.** Medido
    em 20/09/2026, kernel 7.1.5: ``/sys/class/bluetooth/hci0/`` tem ``device``,
    ``power``, ``reset``, ``rfkill0``, ``subsystem`` e ``uevent``, e **nenhum
    ``address``**. Quem só lê o sysfs devolve dicionário vazio com três dongles
    de pé — e "nenhum adaptador" se lê como "nenhum zumbi", que é o pior jeito
    de errar nesta cura.

    1. **sysfs** (``<raiz>/hciN/address``) — kernel puro, sem processo e sem
       D-Bus; existe em kernel que o traga, e é por aqui que a régua injeta uma
       mesa de mentira;
    2. **``hcitool dev``** — a MESMA ferramenta que lista os links, responde
       sem root (medido: três adaptadores), e não depende do ``bluetoothd``.

    Os nós de LINK (``hci0:5``) ficam de fora pela forma: eles são as conexões,
    não os adaptadores, e o ``uevent`` deles não traz endereço nenhum (medido:
    só ``DEVTYPE=link``).
    """
    achados: dict[str, str] = {}
    try:
        entradas = sorted(Path(raiz).iterdir())
    except OSError:
        entradas = []
    for entrada in entradas:
        nome = entrada.name
        if not _FORMA_HCI.match(nome):
            continue
        try:
            bruto = (entrada / "address").read_text(encoding="utf-8", errors="ignore")
        except OSError:
            continue
        endereco = mac_limpo(bruto)
        if endereco is not None:
            achados[nome] = endereco
    if achados:
        return achados
    correr = executor if callable(executor) else _rodar
    if executor is None and shutil.which("hcitool") is None:
        return achados
    for linha in correr(["hcitool", "dev"]).splitlines():
        partes = linha.split()
        if len(partes) < 2 or not _FORMA_HCI.match(partes[0]):
            continue
        endereco = mac_limpo(partes[1])
        if endereco is not None:
            achados[partes[0]] = endereco
    return achados


def _rodar(args: Sequence[str], *, segundos: float = 5.0) -> str:
    """Executa e devolve o stdout, ou ``""``. Nunca levanta.

    ``LC_ALL=C`` não é zelo: o ``pactl`` desta casa já cegou um leitor duas
    vezes por traduzir a própria saída, e o ``hcitool`` tem o mesmo risco. Um
    leitor cego responde *"não há"* sobre aparelho de pé — que aqui significa
    "não há zumbi" sobre um controle mudo, ou pior, o contrário.
    """
    ambiente = dict(os.environ)
    ambiente["LC_ALL"] = "C"
    try:
        saida = subprocess.run(
            list(args),
            capture_output=True,
            text=True,
            timeout=segundos,
            check=False,
            env=ambiente,
        )
    except (OSError, subprocess.SubprocessError):
        return ""
    return saida.stdout or ""


def links_de_pe(
    adaptadores: Mapping[str, str],
    *,
    executor: object = None,
) -> tuple[list[LinkDeRadio], list[str]]:
    """Os ACL de pé, POR ADAPTADOR, e os impedimentos encontrados.

    A fonte é ``hcitool -i hciN con``, que responde **sem root** (medido em
    20/09/2026 na mesa dela, três links em dois adaptadores). Ele foi
    DEPRECIADO pelo BlueZ, então a ausência dele é caso normal e vira
    impedimento declarado, não exceção.

    POR QUE ``-i`` É OBRIGATÓRIO: sem ele o ``hcitool con`` lista os links de
    TODOS os adaptadores numa lista só, e o endereço do adaptador se perde. A
    cura precisa saber em qual dongle está o link, porque é nele que o
    ``desconectar`` tem de agir.

    O ``executor`` existe para a régua injetar um dublê sem tocar no rádio
    dela; em produção é ``None`` e o leitor chama o ``hcitool`` de verdade.
    """
    if not adaptadores:
        return [], ["nenhum adaptador de Bluetooth na mesa"]
    correr = executor if callable(executor) else _rodar
    if executor is None and shutil.which("hcitool") is None:
        return [], [
            "não consigo ler as conexões de rádio: o 'hcitool' foi depreciado "
            "pelo BlueZ e não está nesta máquina (pacote bluez-deprecated / "
            "bluez-deprecated-tools)"
        ]
    encontrados: list[LinkDeRadio] = []
    for hci, endereco_do_adaptador in sorted(adaptadores.items()):
        texto = correr(["hcitool", "-i", hci, "con"])
        for linha in texto.splitlines():
            achado = _MAC_NA_LINHA.search(linha)
            if achado is None:
                continue
            controle = mac_limpo(achado.group(1))
            if controle is None:
                continue
            encontrados.append(
                LinkDeRadio(hci=hci, adaptador=endereco_do_adaptador, controle=controle)
            )
    return encontrados, []


def uniqs_com_hid(raiz: str | os.PathLike[str] = RAIZ_HIDRAW) -> set[str]:
    """Os endereços que TÊM um ``hidraw`` vivo, normalizados.

    Mesma fonte de ``doctor.sh:_hidraw_uniqs`` — ``HID_UNIQ`` do ``uevent`` do
    pai HID, que existe tanto no cabo quanto no rádio.
    """
    achados: set[str] = set()
    try:
        entradas = sorted(Path(raiz).iterdir())
    except OSError:
        return achados
    for entrada in entradas:
        try:
            texto = (entrada / "device" / "uevent").read_text(
                encoding="utf-8", errors="ignore"
            )
        except OSError:
            continue
        for linha in texto.splitlines():
            if not linha.startswith("HID_UNIQ="):
                continue
            endereco = mac_limpo(linha.partition("=")[2])
            if endereco is not None:
                achados.add(endereco)
    return achados


def enderecos_que_o_bluez_conhece(*, executor: object = None) -> set[tuple[str, str]]:
    """``{(hciN, MAC)}`` dos objetos ``org.bluez.Device1`` que existem.

    É a TRAVA DE SEGURANÇA das três condições. Um endereço que aparece aqui tem
    perfil, tem serviço e tem dono — nunca é alvo desta cura, aconteça o que
    acontecer com o ``hidraw`` dele (esse caso é o do cache SDP, e a cura é
    outra).

    Conjunto VAZIO é lido como *"não sei"*, não como *"o BlueZ não conhece
    ninguém"* — quem trata disso é :func:`zumbis`, que se recusa a acusar
    ninguém sem esta leitura.
    """
    correr = executor if callable(executor) else _rodar
    if executor is None and shutil.which("busctl") is None:
        return set()
    texto = correr(["busctl", "tree", "org.bluez", "--list"])
    achados: set[tuple[str, str]] = set()
    for linha in texto.splitlines():
        achado = _NO_DO_BLUEZ.match(linha.strip())
        if achado is None:
            continue
        endereco = mac_limpo(achado.group(2).replace("_", ":"))
        if endereco is not None:
            achados.add((achado.group(1), endereco))
    return achados


# --- a regra (pura) ----------------------------------------------------------


def zumbis(
    links: Iterable[LinkDeRadio],
    uniqs_hid: Iterable[str],
    conhecidos_do_bluez: Iterable[tuple[str, str]],
) -> list[LinkDeRadio]:
    """Os links que estão nas TRÊS condições. Função PURA.

    ``conhecidos_do_bluez`` VAZIO devolve lista vazia, e isso é deliberado: sem
    a terceira leitura a trava de segurança não existe, e acusar sem ela
    derrubaria o fone dela junto com o zumbi. Ausência de leitura é *"não sei"*,
    e "não sei" nunca autoriza agir.
    """
    conhecidos = {(hci, endereco) for hci, endereco in conhecidos_do_bluez}
    if not conhecidos:
        return []
    com_hid = set(uniqs_hid)
    achados: list[LinkDeRadio] = []
    for link in links:
        if link.controle in com_hid:
            continue
        if (link.hci, link.controle) in conhecidos:
            continue
        achados.append(link)
    return achados


# --- a porta privilegiada ----------------------------------------------------


@dataclass
class PontePrivilegiada:
    """O único caminho de root desta cura — ``bt_ponte_privilegiada.sh``.

    O produto NÃO chama ``hcitool dc`` direto: derrubar link é root, e a porta
    já existe, com a entrada validada dos dois lados (regex aqui, classes de
    caractere no ``sudoers.d/49-hefesto-bt-ponte``).
    """

    caminho: str = PONTE_INSTALADA
    #: Injetável para a régua não precisar de sudo nem de ponte instalada.
    executor: object = None

    def impedimentos(self) -> list[str]:
        """Por que esta porta não pode ser usada agora. Vazio = pode."""
        if self.executor is not None:
            return []
        motivos: list[str] = []
        if not Path(self.caminho).exists():
            motivos.append(
                "a ponte privilegiada não está instalada "
                f"({self.caminho}) — {como_atualizar_esta_instalacao()}"
            )
        if shutil.which("sudo") is None:
            motivos.append("o 'sudo' não está nesta máquina")
        elif not self._sudo_sem_senha():
            motivos.append(
                "o sudo sem senha para a ponte não está no lugar "
                f"(/etc/sudoers.d/49-hefesto-bt-ponte) — "
                f"{como_atualizar_esta_instalacao()}"
            )
        return motivos

    def _sudo_sem_senha(self) -> bool:
        try:
            resultado = subprocess.run(
                ["sudo", "-n", "--", self.caminho, "--dry-run", "adaptadores"],
                capture_output=True,
                text=True,
                timeout=10,
                check=False,
            )
        except (OSError, subprocess.SubprocessError):
            return False
        return resultado.returncode == 0

    def desconectar(self, link: LinkDeRadio) -> tuple[bool, str]:
        """Pede à ponte que derrube ESTE link. ``(agiu, motivo)``."""
        argumentos = [
            "sudo",
            "-n",
            "--",
            self.caminho,
            "desconectar",
            link.adaptador,
            link.controle,
        ]
        correr = self.executor
        if callable(correr):
            return correr(argumentos, link)  # type: ignore[no-any-return]
        try:
            resultado = subprocess.run(
                argumentos,
                capture_output=True,
                text=True,
                timeout=20,
                check=False,
            )
        except (OSError, subprocess.SubprocessError) as erro:
            return False, f"a ponte não respondeu: {erro}"
        if resultado.returncode == 0:
            return True, ""
        return False, (resultado.stderr or "").strip() or f"a ponte saiu com {resultado.returncode}"


# --- o vigia (o tempo mora aqui) ---------------------------------------------


@dataclass
class VigiaDeZumbis:
    """Guarda DESDE QUANDO cada link está suspeito, e aplica o teto da cura.

    O relógio entra por argumento em :meth:`observar` — sem isso a régua teria
    de dormir 20 segundos para medir 20 segundos, e uma régua que dorme é uma
    régua que ninguém roda.
    """

    ponte: PontePrivilegiada = field(default_factory=PontePrivilegiada)
    segundos_para_zumbi: float = SEGUNDOS_PARA_ZUMBI
    janela_do_teto_s: float = JANELA_DO_TETO_S
    #: ``{(hci, controle): instante da primeira vez que vimos assim}``.
    _desde: dict[tuple[str, str], float] = field(default_factory=dict, init=False)
    #: ``{controle: instante da última derrubada}`` — o teto.
    _ultima_derrubada: dict[str, float] = field(default_factory=dict, init=False)

    def observar(
        self,
        agora: float,
        links: Sequence[LinkDeRadio],
        uniqs_hid: Iterable[str],
        conhecidos_do_bluez: Iterable[tuple[str, str]],
        *,
        impedimentos: Sequence[str] = (),
    ) -> Veredito:
        """Uma volta do vigia. Nunca levanta; devolve o que viu e o que fez."""
        suspeitos = zumbis(links, uniqs_hid, conhecidos_do_bluez)
        chaves_agora = {(link.hci, link.controle) for link in suspeitos}
        for chave in list(self._desde):
            if chave not in chaves_agora:
                # O link saiu da suspeita — ou virou controle, ou caiu sozinho.
                # O relógio dele ZERA: sem isto, um controle que oscila somaria
                # instantes separados até virar zumbi sem nunca ter ficado.
                del self._desde[chave]
        maduros: list[LinkDeRadio] = []
        for link in suspeitos:
            chave = (link.hci, link.controle)
            comeco = self._desde.setdefault(chave, agora)
            if agora - comeco >= self.segundos_para_zumbi:
                maduros.append(link)

        linhas: list[str] = []
        todos_impedimentos = list(impedimentos)
        if maduros:
            todos_impedimentos.extend(self.ponte.impedimentos())
        if maduros and todos_impedimentos:
            for link in maduros:
                linhas.append(
                    f"o controle {link.controle} conectou em {link.hci} e não virou "
                    "controle, e eu NÃO posso curar sozinho: "
                    + "; ".join(todos_impedimentos)
                )
            return Veredito(
                suspeitos=tuple(suspeitos),
                zumbis=tuple(maduros),
                impedimentos=tuple(todos_impedimentos),
                diario=tuple(linhas),
            )

        derrubados: list[LinkDeRadio] = []
        segurados: list[LinkDeRadio] = []
        for link in maduros:
            ultima = self._ultima_derrubada.get(link.controle)
            if ultima is not None and agora - ultima < self.janela_do_teto_s:
                segurados.append(link)
                linhas.append(
                    f"o controle {link.controle} voltou a conectar em {link.hci} sem "
                    "virar controle, e eu já tentei derrubar o link há pouco — não "
                    "insisto, para não alimentar um laço de reconexão. O gesto que "
                    "resta é repareá-lo neste adaptador."
                )
                continue
            agiu, motivo = self.ponte.desconectar(link)
            if agiu:
                self._ultima_derrubada[link.controle] = agora
                self._desde.pop((link.hci, link.controle), None)
                derrubados.append(link)
                linhas.append(
                    f"o controle {link.controle} conectou em {link.hci} e não virou "
                    "controle (sem hidraw e sem registro no BlueZ); derrubei o link "
                    "para ele procurar de novo o adaptador onde o pareamento está."
                )
            else:
                linhas.append(
                    f"o controle {link.controle} conectou em {link.hci} e não virou "
                    f"controle, e a tentativa de derrubar o link falhou: {motivo}"
                )
        return Veredito(
            suspeitos=tuple(suspeitos),
            zumbis=tuple(maduros),
            derrubados=tuple(derrubados),
            segurados_pelo_teto=tuple(segurados),
            impedimentos=tuple(impedimentos),
            diario=tuple(linhas),
        )


def olhar_a_mesa(
    *,
    raiz_adaptadores: str | os.PathLike[str] = RAIZ_ADAPTADORES,
    raiz_hidraw: str | os.PathLike[str] = RAIZ_HIDRAW,
    executor: object = None,
) -> tuple[list[LinkDeRadio], set[str], set[tuple[str, str]], list[str]]:
    """Uma leitura completa da mesa. Não age, não decide — só olha."""
    adaptadores = adaptadores_na_mesa(raiz_adaptadores, executor=executor)
    links, impedimentos = links_de_pe(adaptadores, executor=executor)
    com_hid = uniqs_com_hid(raiz_hidraw)
    conhecidos = enderecos_que_o_bluez_conhece(executor=executor)
    if not conhecidos and not impedimentos:
        impedimentos = [
            "não consegui perguntar ao BlueZ quais aparelhos ele conhece "
            "(busctl/bluetoothd) — sem essa leitura eu não acuso ninguém"
        ]
    return links, com_hid, conhecidos, impedimentos


__all__ = [
    "JANELA_DO_TETO_S",
    "PONTE_INSTALADA",
    "RAIZ_ADAPTADORES",
    "RAIZ_HIDRAW",
    "SEGUNDOS_PARA_ZUMBI",
    "LinkDeRadio",
    "PontePrivilegiada",
    "Veredito",
    "VigiaDeZumbis",
    "adaptadores_na_mesa",
    "enderecos_que_o_bluez_conhece",
    "links_de_pe",
    "mac_limpo",
    "olhar_a_mesa",
    "uniqs_com_hid",
    "zumbis",
]
