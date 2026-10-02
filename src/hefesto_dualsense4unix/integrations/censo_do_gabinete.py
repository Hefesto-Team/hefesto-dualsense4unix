"""censo_do_gabinete.py — o que o firmware e o kernel sabem do GABINETE dela."""

from __future__ import annotations

import json
import os
import re
from collections.abc import Callable, Sequence
from dataclasses import dataclass
from datetime import datetime, timezone

from .entradas_do_gabinete import NoDeEntrada, furos, listar_entradas


LIDO_DO_FIRMWARE = "lido-do-firmware"

LIDO_DO_KERNEL = "lido-do-kernel"

DECLARADO_POR_ELA = "declarado-por-ela"

NAO_RESPONDEU = "nao-respondeu"

SELOS = (LIDO_DO_FIRMWARE, LIDO_DO_KERNEL, DECLARADO_POR_ELA, NAO_RESPONDEU)

VERSAO_DO_CENSO = 1

NOME_DO_ARQUIVO = "gabinete.json"

RAIZ_DMI_PADRAO = "/sys/firmware/dmi/entries"

RAIZ_DMI_ID_PADRAO = "/sys/class/dmi/id"

RAIZ_USB_PADRAO = "/sys/bus/usb/devices"


_LIXO_DE_FIRMWARE = frozenset(
    {
        "",
        "-",
        "default string",
        "n/a",
        "no connection",
        "none",
        "not applicable",
        "not available",
        "not specified",
        "other",
        "system manufacturer",
        "system product name",
        "to be filled by o.e.m.",
        "to be filled by o.e.m",
        "unknown",
    }
)

_CABECALHO_DA_TABELA_8 = re.compile(r"^\s*Handle\s+0x[0-9A-Fa-f]+,\s*DMI type 8\b")

_CABECALHO_DE_BLOCO = re.compile(r"^\s*Handle\s+0x[0-9A-Fa-f]+,\s*DMI type\b")

_CAMPO = re.compile(r"^\s+([A-Z][A-Za-z0-9 /()\.-]*?):\s*(.*)$")

_HUB_RAIZ = re.compile(r"^usb[0-9]+$")

_CHASSI_MOVEL = frozenset({8, 9, 10, 11, 12, 14, 30, 31, 32})

_CHASSI_FIXO = frozenset({3, 4, 5, 6, 7, 13, 15, 16, 17, 23, 24, 28})


@dataclass(frozen=True)
class Conector:
    """Uma entrada de *Port Connector Information* que sobreviveu ao filtro."""

    designacao_externa: str = ""
    tipo_externo: str = ""
    designacao_interna: str = ""
    tipo_interno: str = ""
    tipo_de_porta: str = ""

    @property
    def externo(self) -> bool:
        """Este conector aparece na CARCAÇA? — o único que a pessoa alcança."""
        return not _lixo(self.designacao_externa) or not _lixo(self.tipo_externo)

    @property
    def e_usb(self) -> bool:
        """USB? — decidido pelos campos de TIPO, nunca pela designação."""
        return any(
            "usb" in campo.casefold()
            for campo in (self.tipo_de_porta, self.tipo_externo, self.tipo_interno)
        )

    def como_dicionario(self) -> dict[str, object]:
        return {
            "designacao_externa": self.designacao_externa,
            "tipo_externo": self.tipo_externo,
            "designacao_interna": self.designacao_interna,
            "tipo_interno": self.tipo_interno,
            "tipo_de_porta": self.tipo_de_porta,
            "externo": self.externo,
            "usb": self.e_usb,
            "de_onde_sei": LIDO_DO_FIRMWARE,
        }


def _lixo(valor: str) -> bool:
    """O firmware escreveu alguma coisa aqui, ou repetiu o gabarito?"""
    return valor.strip().casefold() in _LIXO_DE_FIRMWARE


def conector_de_verdade(conector: Conector) -> bool:
    """**A CURA.** Um bloco só é conector quando ALGUM campo foi preenchido."""
    return not all(
        _lixo(campo)
        for campo in (
            conector.designacao_externa,
            conector.tipo_externo,
            conector.designacao_interna,
            conector.tipo_interno,
            conector.tipo_de_porta,
        )
    )


def blocos_da_tabela_8(texto: str) -> int:
    """Quantos blocos ``DMI type 8`` o texto traz — **lixo incluído**."""
    return sum(1 for linha in texto.splitlines() if _CABECALHO_DA_TABELA_8.match(linha))


def conectores_do_dmidecode(texto: str) -> tuple[Conector, ...]:
    """Os conectores REAIS da tabela 8 — os de gabarito ficam de fora."""
    achados: list[Conector] = []
    for bloco in _blocos(texto):
        conector = Conector(
            designacao_externa=bloco.get("External Reference Designator", ""),
            tipo_externo=bloco.get("External Connector Type", ""),
            designacao_interna=bloco.get("Internal Reference Designator", ""),
            tipo_interno=bloco.get("Internal Connector Type", ""),
            tipo_de_porta=bloco.get("Port Type", ""),
        )
        if conector_de_verdade(conector):
            achados.append(conector)
    return tuple(achados)


def _blocos(texto: str) -> list[dict[str, str]]:
    """Os blocos de tipo 8, cada um como ``rótulo -> valor``."""
    saida: list[dict[str, str]] = []
    dentro: dict[str, str] | None = None
    for linha in texto.splitlines():
        if _CABECALHO_DE_BLOCO.match(linha):
            if dentro is not None:
                saida.append(dentro)
            dentro = {} if _CABECALHO_DA_TABELA_8.match(linha) else None
            continue
        if dentro is None:
            continue
        campo = _CAMPO.match(linha)
        if campo is not None:
            dentro[campo.group(1).strip()] = campo.group(2).strip()
    if dentro is not None:
        saida.append(dentro)
    return saida


def entradas_no_sysfs(
    *,
    raiz_dmi: str = RAIZ_DMI_PADRAO,
    listar: Callable[[str], list[str]] = os.listdir,
) -> int | None:
    """Quantas entradas de tipo 8 o kernel publica — **sem root**, e é o pulo."""
    try:
        nomes = listar(raiz_dmi)
    except OSError:
        return None
    return sum(1 for nome in nomes if nome.startswith("8-"))


def ler_a_placa(
    *,
    raiz_dmi_id: str = RAIZ_DMI_ID_PADRAO,
    ler: Callable[[str], str] | None = None,
) -> dict[str, object]:
    """Quem é esta placa — e serve para saber que o censo é DESTA máquina."""
    leitor = _ler_texto if ler is None else ler
    bruto = {
        campo: leitor(os.path.join(raiz_dmi_id, campo)).strip()
        for campo in ("board_vendor", "board_name", "bios_version", "chassis_type")
    }
    tipo = _talvez_inteiro(bruto["chassis_type"])
    movel: bool | None = None
    if tipo in _CHASSI_MOVEL:
        movel = True
    elif tipo in _CHASSI_FIXO:
        movel = False
    return {
        "fabricante": _talvez(_ou_nada(bruto["board_vendor"]), LIDO_DO_FIRMWARE),
        "modelo": _talvez(_ou_nada(bruto["board_name"]), LIDO_DO_FIRMWARE),
        "bios": _talvez(_ou_nada(bruto["bios_version"]), LIDO_DO_FIRMWARE),
        "tipo_de_chassi": _talvez(tipo, LIDO_DO_FIRMWARE),
        "movel": _talvez(movel, LIDO_DO_FIRMWARE),
    }


def serve_para_esta_placa(censo: dict[str, object], placa: dict[str, object]) -> bool:
    """**A CURA.** Este ``gabinete.json`` é DESTA máquina?"""
    gravada = censo.get("placa")
    if not isinstance(gravada, dict):
        return False
    for campo in ("fabricante", "modelo"):
        antes = _valor(gravada.get(campo))
        agora = _valor(placa.get(campo))
        if antes is None or agora is None or antes != agora:
            return False
    return True


def soquetes_de_raiz(entradas: Sequence[NoDeEntrada]) -> tuple[NoDeEntrada, ...]:
    """Só os nós pendurados num hub-RAIZ — o chassi, sem o hub da mesa."""
    return tuple(entrada for entrada in entradas if _HUB_RAIZ.match(entrada.hub))


def ler_maxchild(
    *,
    raiz_usb: str = RAIZ_USB_PADRAO,
    listar: Callable[[str], list[str]] = os.listdir,
    ler: Callable[[str], str] | None = None,
) -> dict[str, int]:
    """Quantos soquetes cada hub-raiz declara — a SEGUNDA régua da contagem."""
    leitor = _ler_texto if ler is None else ler
    try:
        nomes = sorted(listar(raiz_usb))
    except OSError:
        return {}
    saida: dict[str, int] = {}
    for nome in nomes:
        if not _HUB_RAIZ.match(nome):
            continue
        quantos = _talvez_inteiro(leitor(os.path.join(raiz_usb, nome, "maxchild")))
        if quantos is not None:
            saida[nome] = quantos
    return saida


def censo_do_kernel(
    entradas: Sequence[NoDeEntrada], maxchild: dict[str, int]
) -> dict[str, object]:
    """As contagens que o kernel dá de graça, cada uma com o que ela significa."""
    raiz = soquetes_de_raiz(entradas)
    buracos = furos(raiz) if raiz else ()
    de_encaixe = sum(1 for buraco in buracos if buraco.tipo_de_encaixe == "hotplug")
    soma = sum(maxchild.values()) if maxchild else None
    return {
        "soquetes": _talvez(len(raiz) if raiz else None, LIDO_DO_KERNEL),
        "buracos": _talvez(len(buracos) if buracos else None, LIDO_DO_KERNEL),
        "buracos_de_encaixe": _talvez(de_encaixe if buracos else None, LIDO_DO_KERNEL),
        "maxchild": _talvez(soma, LIDO_DO_KERNEL),
        "por_barramento": dict(sorted(maxchild.items())),
        "reguas_concordam": None if (soma is None or not raiz) else soma == len(raiz),
    }


def declarar_divergencia(
    *, firmware: int | None, soquetes: int | None, buracos: int | None
) -> dict[str, object]:
    """As contagens lado a lado, e a pergunta pronta para a aba fazer."""
    vistos = [n for n in (soquetes, buracos) if n is not None]
    divergem = firmware is not None and bool(vistos) and firmware not in vistos
    return {
        "firmware": _talvez(firmware, LIDO_DO_FIRMWARE),
        "kernel_soquetes": _talvez(soquetes, LIDO_DO_KERNEL),
        "kernel_buracos": _talvez(buracos, LIDO_DO_KERNEL),
        "declarado_por_ela": _fato(None, NAO_RESPONDEU),
        "divergem": divergem,
        "precisa_da_palavra_dela": True,
        "pergunta": _pergunta(firmware=firmware, buracos=buracos, divergem=divergem),
    }


def _pergunta(*, firmware: int | None, buracos: int | None, divergem: bool) -> str:
    """A frase que a aba mostra. **Provisória, e o dono dela é o léxico.**"""
    if divergem and firmware is not None and buracos is not None:
        return (
            f"A BIOS desta placa diz {firmware} conectores USB, e no barramento "
            f"eu vejo {buracos} buracos. As duas contas discordam, e nenhuma "
            "delas viu o seu gabinete. Quantos buracos a sua traseira tem?"
        )
    if firmware is None and buracos is None:
        return (
            "Não consegui contar as entradas USB desta máquina — nem a BIOS "
            "respondeu, nem o barramento. Quantos buracos a sua traseira tem?"
        )
    return (
        "Contei as entradas USB por uma fonte só, e ela não viu o seu gabinete "
        "por fora. Quantos buracos a sua traseira tem?"
    )


def montar_censo(
    *,
    dmidecode: str = "",
    entradas: Sequence[NoDeEntrada] = (),
    maxchild: dict[str, int] | None = None,
    placa: dict[str, object] | None = None,
    entradas_da_tabela_8: int | None = None,
    agora: str = "",
) -> dict[str, object]:
    """O ``gabinete.json`` inteiro, e **cada fato com o seu selo**."""
    conectores = conectores_do_dmidecode(dmidecode)
    respondeu = bool(conectores)
    usb_externos = sum(1 for c in conectores if c.e_usb and c.externo)
    brutos = blocos_da_tabela_8(dmidecode)
    kernel = censo_do_kernel(entradas, maxchild or {})
    return {
        "versao_do_censo": VERSAO_DO_CENSO,
        "gravado_em": agora or _agora(),
        "de_onde_sei": LIDO_DO_FIRMWARE if respondeu else NAO_RESPONDEU,
        "faces": [],
        "por_que_faces_vazias": (
            "O firmware dá o inventário de conectores, não a face em que cada um "
            "está — e o kernel também não: medido em 25/08/2026, o teclado e o "
            "mouse desta bancada têm physical_location idêntico. Quem sabe qual "
            "buraco é da frente é você."
        ),
        "placa": placa if placa is not None else {},
        "firmware": {
            "tabela_8_respondeu": respondeu,
            "blocos_lidos": _talvez(brutos if dmidecode.strip() else None, LIDO_DO_FIRMWARE),
            "entradas_no_sysfs": _talvez(entradas_da_tabela_8, LIDO_DO_KERNEL),
            "conectores": [c.como_dicionario() for c in conectores],
            "conectores_usb": _talvez(usb_externos if respondeu else None, LIDO_DO_FIRMWARE),
        },
        "kernel": kernel,
        "contagens": declarar_divergencia(
            firmware=usb_externos if respondeu else None,
            soquetes=_numero(kernel["soquetes"]),
            buracos=_numero(kernel["buracos"]),
        ),
    }


def ler_o_gabinete(
    *,
    dmidecode: str = "",
    raiz_usb: str = RAIZ_USB_PADRAO,
    raiz_dmi: str = RAIZ_DMI_PADRAO,
    raiz_dmi_id: str = RAIZ_DMI_ID_PADRAO,
    listar: Callable[[str], list[str]] = os.listdir,
    ler: Callable[[str], str] | None = None,
) -> dict[str, object]:
    """O censo desta máquina — a única função aqui que toca o ``/sys``."""
    return montar_censo(
        dmidecode=dmidecode,
        entradas=listar_entradas(raiz_usb=raiz_usb, listar=listar, ler=ler),
        maxchild=ler_maxchild(raiz_usb=raiz_usb, listar=listar, ler=ler),
        placa=ler_a_placa(raiz_dmi_id=raiz_dmi_id, ler=ler),
        entradas_da_tabela_8=entradas_no_sysfs(raiz_dmi=raiz_dmi, listar=listar),
    )


def caminho_padrao(*, home: str = "") -> str:
    """``~/.local/state/hefesto-dualsense4unix/gabinete.json``."""
    raiz = home or os.path.expanduser("~")
    return os.path.join(raiz, ".local", "state", "hefesto-dualsense4unix", NOME_DO_ARQUIVO)


def ler_do_disco(caminho: str = "") -> dict[str, object]:
    """O ``gabinete.json`` que já está lá — ``{}`` quando não há ou não abre."""
    try:
        with open(caminho or caminho_padrao(), encoding="utf-8") as arquivo:
            lido = json.load(arquivo)
    except (OSError, ValueError):
        return {}
    return lido if isinstance(lido, dict) else {}


def preservar_o_que_ela_disse(
    novo: dict[str, object], antigo: dict[str, object], placa: dict[str, object]
) -> dict[str, object]:
    """**A CURA.** Reinstalar não pode apagar o que ela ensinou ao produto."""
    if not antigo:
        return novo
    if not serve_para_esta_placa(antigo, placa):
        return {**novo, "substituiu_outra_placa": True}
    herdado = dict(novo)
    faces = antigo.get("faces")
    if isinstance(faces, list) and faces:
        herdado["faces"] = faces
    dela = _dela(antigo)
    contagens = herdado.get("contagens")
    if dela is not None and isinstance(contagens, dict):
        novas = dict(contagens)
        novas["declarado_por_ela"] = _fato(dela, DECLARADO_POR_ELA)
        novas["precisa_da_palavra_dela"] = False
        herdado["contagens"] = novas
    return herdado


def _dela(censo: dict[str, object]) -> object:
    contagens = censo.get("contagens")
    if not isinstance(contagens, dict):
        return None
    return _valor(contagens.get("declarado_por_ela"))


def gravar(censo: dict[str, object], caminho: str = "") -> str:
    """Grava o censo e devolve o caminho. Escrita ATÔMICA, por troca de nome."""
    alvo = caminho or caminho_padrao()
    os.makedirs(os.path.dirname(alvo), exist_ok=True)
    provisorio = f"{alvo}.novo"
    with open(provisorio, "w", encoding="utf-8") as arquivo:
        json.dump(censo, arquivo, ensure_ascii=False, indent=2, sort_keys=True)
        arquivo.write("\n")
    os.replace(provisorio, alvo)
    return alvo


def resumo(censo: dict[str, object]) -> str:
    """Uma linha para o install imprimir — o que ficou sabido, e o que não."""
    firmware = censo.get("firmware")
    contagens = censo.get("contagens")
    if not isinstance(firmware, dict) or not isinstance(contagens, dict):
        return "censo do gabinete vazio"
    usb = _valor(firmware.get("conectores_usb"))
    buracos = _valor(contagens.get("kernel_buracos"))
    partes = [
        f"BIOS: {usb} conectores USB" if usb is not None else "BIOS: não respondeu",
        f"barramento: {buracos} buracos" if buracos is not None else "barramento: mudo",
    ]
    if contagens.get("divergem"):
        partes.append("DIVERGEM — a aba vai perguntar")
    return " · ".join(partes)


FONTES_DA_CONTAGEM = ("firmware", "kernel_buracos", "declarado_por_ela")


def contagens_declaradas(censo: dict[str, object]) -> dict[str, int]:
    """``{fonte: número}`` — só as fontes que RESPONDERAM."""
    contagens = censo.get("contagens")
    if not isinstance(contagens, dict):
        return {}
    achadas = {fonte: _numero(contagens.get(fonte)) for fonte in FONTES_DA_CONTAGEM}
    return {fonte: n for fonte, n in achadas.items() if n is not None}


def pergunta_pendente(censo: dict[str, object]) -> str:
    """A pergunta que a aba tem de fazer — ``""`` quando ela já respondeu."""
    contagens = censo.get("contagens")
    if not isinstance(contagens, dict) or not contagens.get("precisa_da_palavra_dela"):
        return ""
    pergunta = contagens.get("pergunta")
    return pergunta if isinstance(pergunta, str) else ""


def _fato(valor: object, selo: str) -> dict[str, object]:
    """Todo número deste arquivo é um par ``{valor, de_onde_sei}``, sem exceção."""
    return {"valor": valor, "de_onde_sei": selo}


def _talvez(valor: object, selo: str) -> dict[str, object]:
    """Um fato que pode não existir — e a AUSÊNCIA troca o selo, não só o valor."""
    return _fato(valor, selo if valor is not None else NAO_RESPONDEU)


def _valor(fato: object) -> object:
    return fato.get("valor") if isinstance(fato, dict) else None


def _numero(fato: object) -> int | None:
    """O ``valor`` de um fato quando ele é contagem — ``None`` em todo o resto."""
    valor = _valor(fato)
    return valor if isinstance(valor, int) and not isinstance(valor, bool) else None


def _ou_nada(texto: str) -> str | None:
    """Gabarito de fabricante vira ``None`` — ``Default string`` não é o modelo."""
    return None if _lixo(texto) else texto


def _talvez_inteiro(valor: str) -> int | None:
    try:
        return int(valor.strip())
    except (AttributeError, TypeError, ValueError):
        return None


def _agora() -> str:
    return datetime.now(timezone.utc).astimezone().isoformat(timespec="seconds")


def _ler_texto(caminho: str) -> str:
    try:
        with open(caminho, encoding="utf-8", errors="ignore") as arquivo:
            return arquivo.read()
    except OSError:
        return ""
