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

A ordem de produto é o que este módulo existe para cumprir:

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
funcionando por ele. O fone, o mouse, o celular e o teclado do usuário têm objeto no
BlueZ enquanto conectados, e por isso ficam FORA por construção — sem lista de
OUI, sem casar por nome, sem depender da bancada.

A terceira é também o que separa este defeito do **"conectado sem hidraw"** que
o ``scripts/doctor.sh`` já pega (``check_bt_connected_sem_hidraw``): lá o BlueZ
CONHECE o device, e a cura é outra — o pareamento sem registro SDP (o cache sem
``[ServiceRecords]``), que não se resolve derrubando link nenhum.

POR QUE SE LÊ NO KERNEL (lido no fonte do BlueZ 5.86, 07/10/2026): o zumbi é
um ACL SEM ``Device1``. O ``bluetoothd`` cria o objeto para todo ACL que o kernel
anuncia (``connected_callback``, ``src/adapter.c:9558``), e o ``Adapter1`` não tem
método que liste conexões (a tabela ``adapter_methods``, ``src/adapter.c:3945-3959``):
o link sem objeto só se lê abaixo do D-Bus, no ``HCIGETCONNLIST`` do ``LeitorDoKernel``,
o ioctl do ``hcitool con`` sem a ferramenta depreciada, que o Arch e o Fedora não instalam.

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

from hefesto_dualsense4unix.integrations.ar_do_adaptador import TIPO_ACL, LeitorDoKernel
from hefesto_dualsense4unix.integrations.usb_pai import RAIZ_HIDRAW
from hefesto_dualsense4unix.utils.logging_config import get_logger
from hefesto_dualsense4unix.utils.repo_files import como_atualizar_esta_instalacao

logger = get_logger(__name__)

SEGUNDOS_PARA_ZUMBI = 20.0

JANELA_DO_TETO_S = 600.0

RAIZ_ADAPTADORES = "/sys/class/bluetooth"

PONTE_INSTALADA = "/usr/local/lib/hefesto-dualsense4unix/bt_ponte_privilegiada.sh"

PASTA_DA_REGRA = "/etc/sudoers.d"

_FORMA_MAC = re.compile(r"^[0-9a-f]{2}(:[0-9a-f]{2}){5}$")

_FORMA_HCI = re.compile(r"^hci[0-9]+$")

def mac_limpo(valor: str | None) -> str | None:
    """MAC em ``aa:bb:cc:dd:ee:ff`` minúsculo, ou ``None``."""
    if not valor:
        return None
    texto = str(valor).strip().lower()
    return texto if _FORMA_MAC.match(texto) else None


_ENDERECOS_DO_VERBO: dict[str, int] = {
    "bonds": 1,
    "renomear": 1,
    "descobrir": 1,
    "esquecer": 2,
    "parear": 2,
    "desconectar": 2,
}


@dataclass(frozen=True)
class PedidoAPonte:
    """Um pedido à ponte root, montado por :func:`pedido_a_ponte`."""

    argv: tuple[str, ...]
    entrada: str
    sonda: tuple[str, ...]


def pedido_a_ponte(
    verbo: str,
    *enderecos: str,
    segundos: int | None = None,
    nome: str | None = None,
    caminho: str = PONTE_INSTALADA,
) -> PedidoAPonte:
    """O pedido à ponte root — o ÚNICO lugar do ``src/`` que escreve ``sudo`` para ela."""
    esperados = _ENDERECOS_DO_VERBO.get(verbo)
    if esperados is None:
        raise ValueError(f"a ponte não tem o verbo {verbo!r} com dado pelo stdin")
    limpos = [mac_limpo(endereco) for endereco in enderecos]
    if any(limpo is None for limpo in limpos):
        raise ValueError("o endereço não tem forma de endereço")
    if limpos and len(limpos) != esperados:
        raise ValueError(f"o verbo {verbo} lê {esperados} endereço(s), e vieram {len(limpos)}")
    if (segundos is not None) != (verbo == "descobrir"):
        raise ValueError("só o descobrir leva os segundos, e ele sempre os leva")
    if nome is not None and verbo != "renomear":
        raise ValueError("só o renomear leva o nome novo")
    linha: tuple[str, ...] = (caminho, verbo)
    if segundos is not None:
        linha = (*linha, str(int(segundos)))
    dados = [str(limpo) for limpo in limpos]
    if nome is not None:
        dados.append(nome)
    return PedidoAPonte(
        argv=("sudo", "-n", "--", *linha),
        entrada="".join(f"{dado}\n" for dado in dados),
        sonda=("sudo", "-n", "-l", "--", *linha),
    )


@dataclass(frozen=True)
class LinkDeRadio:
    """Um ACL de pé: em QUAL adaptador, com QUAL endereço."""

    hci: str
    adaptador: str
    controle: str


@dataclass(frozen=True)
class Veredito:
    """O que o vigia viu nesta volta, e o que fez — ou por que não fez."""

    suspeitos: tuple[LinkDeRadio, ...] = ()
    zumbis: tuple[LinkDeRadio, ...] = ()
    derrubados: tuple[LinkDeRadio, ...] = ()
    segurados_pelo_teto: tuple[LinkDeRadio, ...] = ()
    impedimentos: tuple[str, ...] = ()
    diario: tuple[str, ...] = ()

    @property
    def agiu(self) -> bool:
        return bool(self.derrubados)


def adaptadores_na_mesa(
    raiz: str | os.PathLike[str] = RAIZ_ADAPTADORES,
    *,
    leitor: LeitorDoKernel | None = None,
) -> dict[str, str]:
    """``{hciN: MAC do adaptador}``, do sysfs e, quando ele cala, do kernel."""
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
    kernel = leitor if leitor is not None else LeitorDoKernel()
    for numero in kernel.adaptadores() or ():
        leitura = kernel.ler(numero)
        if leitura is None or not leitura.ligado:
            continue
        endereco = mac_limpo(leitura.endereco)
        if endereco is not None:
            achados[f"hci{numero}"] = endereco
    return achados


def links_de_pe(
    adaptadores: Mapping[str, str],
    *,
    leitor: LeitorDoKernel | None = None,
) -> tuple[list[LinkDeRadio], list[str]]:
    """Os ACL de pé, POR ADAPTADOR, pelo ``HCIGETCONNLIST``, e os impedimentos encontrados."""
    if not adaptadores:
        return [], ["nenhum adaptador de Bluetooth na mesa"]
    kernel = leitor if leitor is not None else LeitorDoKernel()
    encontrados: list[LinkDeRadio] = []
    impedimentos: list[str] = []
    for hci, endereco_do_adaptador in sorted(adaptadores.items()):
        enlaces = kernel.conexoes(int(hci[3:]))
        if enlaces is None:
            impedimentos.append(f"o kernel não listou as conexões de rádio de {hci}")
            continue
        for enlace in enlaces:
            controle = mac_limpo(enlace.endereco)
            if enlace.tipo != TIPO_ACL or controle is None:
                continue
            encontrados.append(
                LinkDeRadio(hci=hci, adaptador=endereco_do_adaptador, controle=controle)
            )
    return encontrados, impedimentos


def uniqs_com_hid(raiz: str | os.PathLike[str] = RAIZ_HIDRAW) -> set[str]:
    """Os endereços que TÊM um ``hidraw`` vivo, normalizados; vazio quando a raiz não abre."""
    return quem_tem_hid(raiz) or set()


def quem_tem_hid(raiz: str | os.PathLike[str] | None = None) -> set[str] | None:
    """Os endereços que TÊM um ``hidraw`` vivo, normalizados, ou ``None`` = não sei."""
    achados: set[str] = set()
    try:
        entradas = sorted(Path(RAIZ_HIDRAW if raiz is None else raiz).iterdir())
    except OSError:
        return None
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
    """``{(hciN, MAC)}`` dos objetos ``org.bluez.Device1`` que existem."""
    from hefesto_dualsense4unix.integrations import bluez_dbus

    leitor = (
        bluez_dbus.pela_linha_de_comando(executor)
        if callable(executor)
        else bluez_dbus.dono()
    )
    achados: set[tuple[str, str]] = set()
    for caminho in leitor.caminhos() or ():
        hci = bluez_dbus.hci_do_aparelho(caminho)
        endereco = bluez_dbus.endereco_do_aparelho(caminho)
        if hci is not None and endereco is not None:
            achados.add((hci, endereco))
    return achados


def zumbis(
    links: Iterable[LinkDeRadio],
    uniqs_hid: Iterable[str],
    conhecidos_do_bluez: Iterable[tuple[str, str]],
) -> list[LinkDeRadio]:
    """Os links que estão nas TRÊS condições. Função PURA."""
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


@dataclass
class PontePrivilegiada:
    """O único caminho de root desta cura — ``bt_ponte_privilegiada.sh``."""

    caminho: str = PONTE_INSTALADA
    executor: object = None
    pasta_da_regra: str = PASTA_DA_REGRA

    def impedimentos(self) -> list[str]:
        """Por que esta porta não pode ser usada agora. Vazio = pode."""
        return self.impedimentos_do_pedido(pedido_a_ponte("desconectar", caminho=self.caminho))

    def firma(self) -> tuple[int, int, int, int]:
        """A firma da ponte instalada e a da pasta da regra do sudoers.

        O instalador grava a ponte e, depois do ``visudo -c``, a regra: são dois
        passos. Com a firma só da ponte, a volta que caísse entre eles guardava
        «sem a regra» com a firma nova e não perguntava mais no episódio.
        """
        return _firma_do_caminho(self.caminho) + _firma_do_caminho(self.pasta_da_regra)

    def impedimentos_do_pedido(self, *pedidos: PedidoAPonte) -> list[str]:
        """Os impedimentos, com a sonda de CADA pedido perguntada à regra."""
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
        elif not all(self._sudo_sem_senha(pedido) for pedido in pedidos):
            motivos.append(
                "o sudo sem senha para a ponte não está no lugar "
                f"(/etc/sudoers.d/49-hefesto-bt-ponte) — "
                f"{como_atualizar_esta_instalacao()}"
            )
        return motivos

    def _sudo_sem_senha(self, pedido: PedidoAPonte) -> bool:
        try:
            resultado = subprocess.run(
                list(pedido.sonda),
                stdin=subprocess.DEVNULL,
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
        try:
            pedido = pedido_a_ponte(
                "desconectar", link.adaptador, link.controle, caminho=self.caminho
            )
        except ValueError as erro:
            return False, str(erro)
        correr = self.executor
        if callable(correr):
            return correr(pedido)  # type: ignore[no-any-return]
        try:
            resultado = subprocess.run(
                list(pedido.argv),
                input=pedido.entrada,
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


def _firma_do_caminho(caminho: str) -> tuple[int, int]:
    """``(st_ino, st_ctime_ns)``; sem o arquivo, ``(0, errno)``: a ausência também é firma."""
    try:
        estado = os.stat(caminho)
    except OSError as erro:
        return 0, erro.errno or 0
    return estado.st_ino, estado.st_ctime_ns


@dataclass
class VigiaDeZumbis:
    """Guarda DESDE QUANDO cada link está suspeito, e aplica o teto da cura."""

    ponte: PontePrivilegiada = field(default_factory=PontePrivilegiada)
    segundos_para_zumbi: float = SEGUNDOS_PARA_ZUMBI
    janela_do_teto_s: float = JANELA_DO_TETO_S
    _desde: dict[tuple[str, str], float] = field(default_factory=dict, init=False)
    _ultima_derrubada: dict[str, float] = field(default_factory=dict, init=False)
    _maduros_perguntados: set[tuple[str, str]] = field(default_factory=set, init=False)
    _firma_perguntada: object = field(default=None, init=False)
    _impedimentos_da_ponte: list[str] = field(default_factory=list, init=False)

    def _impedimentos_lidos(self, maduros: Sequence[LinkDeRadio]) -> list[str]:
        """A resposta da ponte, perguntada só no episódio novo ou na firma nova."""
        chaves = {(link.hci, link.controle) for link in maduros}
        ler_firma = getattr(self.ponte, "firma", None)
        firma = ler_firma() if callable(ler_firma) else None
        if not chaves <= self._maduros_perguntados or firma != self._firma_perguntada:
            self._impedimentos_da_ponte = list(self.ponte.impedimentos())
            self._firma_perguntada = firma
        self._maduros_perguntados = chaves
        return list(self._impedimentos_da_ponte)

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
            todos_impedimentos.extend(self._impedimentos_lidos(maduros))
        else:
            self._maduros_perguntados = set()
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
                self._maduros_perguntados.discard((link.hci, link.controle))
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
    leitor: LeitorDoKernel | None = None,
) -> tuple[list[LinkDeRadio], set[str], set[tuple[str, str]], list[str]]:
    """Uma leitura completa da mesa. Não age, não decide — só olha."""
    kernel = leitor if leitor is not None else LeitorDoKernel()
    adaptadores = adaptadores_na_mesa(raiz_adaptadores, leitor=kernel)
    links, impedimentos = links_de_pe(adaptadores, leitor=kernel)
    com_hid = uniqs_com_hid(raiz_hidraw)
    conhecidos = enderecos_que_o_bluez_conhece(executor=executor)
    if not conhecidos and not impedimentos:
        impedimentos = [
            "não consegui perguntar ao BlueZ quais aparelhos ele conhece "
            "(barramento do sistema/bluetoothd) — sem essa leitura eu não acuso "
            "ninguém"
        ]
    return links, com_hid, conhecidos, impedimentos


__all__ = [
    "JANELA_DO_TETO_S",
    "PONTE_INSTALADA",
    "RAIZ_ADAPTADORES",
    "RAIZ_HIDRAW",
    "SEGUNDOS_PARA_ZUMBI",
    "LinkDeRadio",
    "PedidoAPonte",
    "PontePrivilegiada",
    "Veredito",
    "VigiaDeZumbis",
    "adaptadores_na_mesa",
    "enderecos_que_o_bluez_conhece",
    "links_de_pe",
    "mac_limpo",
    "olhar_a_mesa",
    "pedido_a_ponte",
    "quem_tem_hid",
    "uniqs_com_hid",
    "zumbis",
]
