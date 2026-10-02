"""o_cabo_em_espera.py — o controle do rádio que ganhou cabo, e o kernel deixou esperando."""

from __future__ import annotations

import os
import re
import subprocess
from collections.abc import Callable, Iterable, Mapping
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any

from hefesto_dualsense4unix.core import formas_do_endereco as _formas
from hefesto_dualsense4unix.utils.logging_config import get_logger

logger = get_logger(__name__)

RAIZ_DO_BARRAMENTO_HID = "/sys/bus/hid/devices"

NOME_DA_REGRA = "85-hefesto-o-cabo-assume.rules"
REGRAS_QUE_RELIGAM: tuple[str, ...] = (
    f"/etc/udev/rules.d/{NOME_DA_REGRA}",
    f"/usr/lib/udev/rules.d/{NOME_DA_REGRA}",
    f"/lib/udev/rules.d/{NOME_DA_REGRA}",
)

#: O HID de um DualSense (comum ou Edge) NO CABO: barramento 0003, Sony 054C.
_FORMA_DO_CABO = re.compile(r"^0003:054C:(0CE6|0DF2)\.[0-9A-F]{4,}$")

_LINHA_DA_RECUSA = re.compile(
    r"(?P<inst>[0-9A-Fa-f]{4}:[0-9A-Fa-f]{4}:[0-9A-Fa-f]{4}\.[0-9A-Fa-f]{4,}): "
    r"Duplicate device found for MAC address (?P<mac>[0-9A-Fa-f]{2}(?::[0-9A-Fa-f]{2}){5})"
)

CARGA_DE_FORA = frozenset({"carregando", "cheio", "fora_de_faixa", "erro"})

ESPERA_PARA_SER_ORFAO_S = 5.0

JANELA_DO_PAR_PELA_CARGA_S = 60.0

TETO_POR_CONTROLE_S = 120.0

ESPERA_DEPOIS_DA_RECUSA_S = 5.0
RECUSAS_ANTES_DE_DESISTIR = 5

ESPERA_DO_DIARIO_S = 3.0

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
    """A máscara da casa para o diário: os octetos 4 e 5 zerados, sem os dois-pontos."""
    if not uniq:
        return None
    mascarado = _formas.mascarar_endereco(uniq)
    if mascarado is None:
        return _formas.mascarar(uniq)
    return mascarado.replace(":", "")


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
    """``{instância: endereço 12-hex}`` das recusas por endereço repetido. Pura."""
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
    """O texto do diário do kernel deste boot, ou ``None`` se não deu para ler."""
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
    """Por que o produto não pode derrubar o rádio agora. Vazio = pode."""
    alvos = REGRAS_QUE_RELIGAM if regras is None else regras
    if any(Path(regra).exists() for regra in alvos):
        return []
    from hefesto_dualsense4unix.utils.repo_files import como_atualizar_esta_instalacao

    return [
        f"a regra que religa o cabo ({NOME_DA_REGRA}) não está instalada — sem ela "
        f"o controle ficaria sem rádio e sem cabo; {como_atualizar_esta_instalacao()}"
    ]


def derrubar_o_radio(uniq: str, leitor: Any = None) -> tuple[bool, str]:
    """``Disconnect`` do controle ``uniq`` em todo adaptador onde ele está ligado."""
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


@dataclass
class VigiaDoCabo:
    """Guarda desde quando cada cabo espera e a borda da carga de cada controle."""

    visto_em: dict[str, float] = field(default_factory=dict)
    resolvidos: set[str] = field(default_factory=set)
    carga_de_fora_desde: dict[str, float | None] = field(default_factory=dict)
    derrubado_em: dict[str, float] = field(default_factory=dict)
    avisados: set[str] = field(default_factory=set)
    ultima_olhada: float | None = None
    recusas: dict[str, int] = field(default_factory=dict)
    tentar_de_novo_em: dict[str, float] = field(default_factory=dict)
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
            self.recusas.pop(instancia, None)
            self.tentar_de_novo_em.pop(instancia, None)
        pendentes: list[CaboEmEspera] = []
        for instancia, cabo in vivos.items():
            self.visto_em.setdefault(instancia, agora)
            if instancia in self.resolvidos:
                continue
            if agora < self.tentar_de_novo_em.get(instancia, float("-inf")):
                continue
            pendentes.append(cabo)
        return pendentes

    def quer_olhar_de_novo(self, agora: float) -> bool:
        """Algum cabo pendente ficou maduro DEPOIS da última olhada?"""
        desde = self.ultima_olhada
        if desde is None:
            return False
        return any(
            instancia not in self.resolvidos
            and desde < visto + ESPERA_PARA_SER_ORFAO_S <= agora
            for instancia, visto in self.visto_em.items()
        ) or any(
            instancia not in self.resolvidos and desde < quando <= agora
            for instancia, quando in self.tentar_de_novo_em.items()
        )

    def decidir(
        self,
        cabo: CaboEmEspera,
        *,
        diario: Mapping[str, str] | None,
        no_radio: Mapping[str, str | None],
        agora: float,
    ) -> Decisao:
        """O par do cabo no rádio. Função do estado; não escreve em nada fora dela."""
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

    def recusado(self, instancia: str, agora: float) -> bool:
        """O BlueZ não derrubou o rádio deste cabo. ``True`` = tenta de novo."""
        vezes = self.recusas.get(instancia, 0) + 1
        self.recusas[instancia] = vezes
        if vezes >= RECUSAS_ANTES_DE_DESISTIR:
            self.resolvidos.add(instancia)
            self.tentar_de_novo_em.pop(instancia, None)
            return False
        self.resolvidos.discard(instancia)
        self.tentar_de_novo_em[instancia] = agora + ESPERA_DEPOIS_DA_RECUSA_S
        return True

    def derrubou(self, uniq: str, agora: float) -> None:
        self.derrubado_em[uniq] = agora

    def observar_quem_esta_no_cabo(self, no_cabo: Iterable[str]) -> None:
        """A troca que DEU CERTO solta o teto daquele controle."""
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
    "ESPERA_DEPOIS_DA_RECUSA_S",
    "ESPERA_PARA_SER_ORFAO_S",
    "JANELA_DO_PAR_PELA_CARGA_S",
    "NOME_DA_REGRA",
    "RAIZ_DO_BARRAMENTO_HID",
    "RECUSAS_ANTES_DE_DESISTIR",
    "REGRAS_QUE_RELIGAM",
    "TETO_POR_CONTROLE_S",
    "CaboEmEspera",
    "Decisao",  # (noqa-acento): nome de classe, identificador Python
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
