"""O jogo com kit de brinquedo se reconhece pela pasta, e a escolha salva diz se alcança a ponte.

A tabela `docs/data/kits-de-brinquedo.csv` diz, por forma de kit (sem appid), qual arquivo na pasta
do jogo o entrega e onde o jogo guarda a escolha de endereço e porta. O módulo só LÊ: acha o kit,
lê a configuração salva quando a forma tem leitura e devolve uma classe, nunca o endereço. O
endereço que a pessoa digitou no jogo é dela (pode ser o IP do telefone na rede): ele vira só a
classe, não entra no veredito, no `repr` nem em log. O Hefesto não escreve no arquivo do jogo; a
correção é da pessoa, no menu do jogo. 100% stdlib, como o prontuário.
"""
from __future__ import annotations

import csv
import json
import xml.etree.ElementTree as ET
from collections.abc import Callable, Iterable
from dataclasses import dataclass, field
from pathlib import Path

try:
    from .receitas_de_ambiente import achar_sinal, arquivos_do_sinal
except ImportError:  # pragma: no cover - executado como script avulso
    from receitas_de_ambiente import achar_sinal, arquivos_do_sinal  # type: ignore[no-redef]

TABELA = Path(__file__).resolve().parents[3] / "docs" / "data" / "kits-de-brinquedo.csv"

#: As portas em que a ponte do Game Mode escuta, em `127.0.0.1`, em qualquer esquema.
PORTAS_DA_PONTE = (20010, 30010)
#: A porta que o Planet Lust usa quando a escolha não foi gravada (o padrão do jogo).
PORTA_PADRAO_DO_JJ = 30010

ALCANCA_A_PONTE = "alcanca_a_ponte"
PORTA_QUE_NADA_ATENDE = "porta_que_nada_atende"
APONTA_PARA_OUTRA_MAQUINA = "aponta_para_outra_maquina"
DESLIGADO = "desligado"
NAO_LIDO = "nao_lido"

UNITY_SETTINGS_JSON = "unity-settings-json"
SKULLGEAR_CONFIG_XML = "skullgear-config-xml"
NENHUMA = "nenhuma"

#: O teto do que se lê de um arquivo do jogo; o que passa disto não é a configuração.
_TETO_DA_CONFIGURACAO = 2 * 1024 * 1024
_FATIA = 1024 * 1024

_ENDERECOS_DA_PONTE = frozenset({"127.0.0.1", "localhost"})
_ENDERECOS_LOCAIS = frozenset({"::1", "[::1]", "0:0:0:0:0:0:0:1"})


@dataclass(frozen=True)
class Kit:
    """Uma linha da tabela: uma forma de kit."""

    kit: str
    sinais: tuple[str, ...]
    #: A cadeia exigida dentro do arquivo do sinal; vazia quando o nome basta.
    contem: str
    config: str
    fonte: str


@dataclass(frozen=True)
class KitDoJogo:
    """O que a pasta de UM jogo diz sobre o kit. O endereço nunca entra aqui."""

    kit: str
    veredito: str
    porta: int | None = None
    #: ``http``, ``https`` ou ``None`` quando a configuração não diz.
    esquema: str | None = None

    def como_dicionario(self) -> dict[str, object]:
        return {
            "kit": self.kit,
            "veredito": self.veredito,
            "porta": self.porta,
            "esquema": self.esquema,
        }


@dataclass(frozen=True)
class _Lido:
    """A configuração salva, de passagem: o endereço vive só até virar classe."""

    ligado: bool | None = None
    endereco: str = field(default="", repr=False)
    porta: int | None = None
    esquema: str | None = None


def _kit_valido(linha: dict[str, str]) -> Kit | None:
    ident = (linha.get("kit") or "").strip()
    sinais = tuple(s.strip() for s in (linha.get("sinais") or "").split("|") if s.strip())
    config = (linha.get("config") or "").strip()
    if not (ident and sinais) or config not in _LEITORES:
        return None
    return Kit(ident, sinais, (linha.get("contem") or "").strip(), config,
               (linha.get("fonte") or "").strip())


def carregar_tabela(caminho: Path | None = None) -> tuple[Kit, ...]:
    """Os kits da tabela; tabela ausente ou linha fora da regra não derruba nada."""
    alvo = caminho if caminho is not None else TABELA
    try:
        texto = alvo.read_text(encoding="utf-8")
    except OSError:
        return ()
    corpo = (ln for ln in texto.splitlines() if ln.strip() and not ln.lstrip().startswith("#"))
    achados: list[Kit] = []
    vistos: set[str] = set()
    for linha in csv.DictReader(corpo):
        kit = _kit_valido({k: (v or "") for k, v in linha.items() if k})
        if kit is None or kit.kit in vistos:
            continue
        vistos.add(kit.kit)
        achados.append(kit)
    return tuple(achados)


def _arquivo_contem(arquivo: Path, cadeia: str) -> bool:
    """A cadeia (sem diferenciar caixa) está no arquivo; lê em fatias, sem carregá-lo todo."""
    alvo = cadeia.lower().encode("utf-8")
    cauda = b""
    try:
        with arquivo.open("rb") as fonte:
            while fatia := fonte.read(_FATIA):
                janela = (cauda + fatia).lower()
                if alvo in janela:
                    return True
                cauda = janela[-(len(alvo) - 1):] if len(alvo) > 1 else b""
    except OSError:
        return False
    return False


def reconhecer(
    raiz: Path | None, tabela: Iterable[Kit] | None = None
) -> tuple[Kit, Path] | None:
    """O kit que a pasta traz e o arquivo do sinal que o provou, ou ``None``."""
    if raiz is None:
        return None
    for kit in carregar_tabela() if tabela is None else tabela:
        for sinal in kit.sinais:
            arquivo = achar_sinal(raiz, sinal)
            if arquivo is None:
                continue
            if kit.contem and not _arquivo_contem(arquivo, kit.contem):
                continue
            return kit, arquivo
    return None


# --- a leitura da configuração salva -------------------------------------------------------


def _ler_texto(arquivo: Path) -> str:
    """O texto do arquivo; vazio quando não se lê ou passa do teto (vazio não é configuração)."""
    try:
        if arquivo.stat().st_size > _TETO_DA_CONFIGURACAO:
            return ""
        return arquivo.read_text(encoding="utf-8-sig", errors="replace")
    except OSError:
        return ""


def _json_ou_vazio(texto: str) -> dict[str, object]:
    """O objeto JSON do texto; texto que não é objeto JSON dá vazio."""
    try:
        dados = json.loads(texto)
    except ValueError:
        return {}
    return dados if isinstance(dados, dict) else {}


def _customs_do_xml(texto: str) -> dict[str, str]:
    """``{name: value}`` dos ``<custom>`` do xml; xml que não se lê dá vazio."""
    try:
        arvore = ET.fromstring(texto)
    except ET.ParseError:
        return {}
    return {(c.get("name") or ""): (c.get("value") or "") for c in arvore.iter("custom")}


def _porta(valor: object) -> int | None:
    texto = "" if isinstance(valor, bool) else str(valor).strip()
    if not (texto.isascii() and texto.isdigit()):
        return None
    porta = int(texto)
    return porta if 0 < porta < 65536 else None


def _como_booleano(valor: object) -> bool | None:
    if isinstance(valor, bool):
        return valor
    texto = str(valor).strip().lower()
    if texto in ("1", "true", "yes", "on"):
        return True
    if texto in ("0", "false", "no", "off"):
        return False
    return None


def _pasta_do_unity(raiz: Path, arquivo_do_sinal: Path, appid: str) -> Path | None:
    """`.../AppData/LocalLow/<empresa>/<produto>` do prefixo do Proton, pelo `app.info` do jogo."""
    dentro = arquivo_do_sinal.is_relative_to(raiz)
    partes = arquivo_do_sinal.relative_to(raiz).parts if dentro else ()
    info = _ler_texto(raiz / partes[0] / "app.info") if len(partes) > 1 else ""
    if not info or not appid.isdigit() or raiz.parent.name != "common":
        return None
    nomes = [ln.strip() for ln in info.splitlines() if ln.strip()]
    if len(nomes) < 2 or any(n.startswith(".") or "/" in n or "\\" in n for n in nomes[:2]):
        return None
    return (
        raiz.parent.parent / "compatdata" / appid / "pfx" / "drive_c" / "users" / "steamuser"
        / "AppData" / "LocalLow" / nomes[0] / nomes[1]
    )


def _ler_unity(raiz: Path, arquivo_do_sinal: Path, appid: str) -> _Lido | None:
    pasta = _pasta_do_unity(raiz, arquivo_do_sinal, appid)
    dados = _json_ou_vazio(_ler_texto(pasta / "Settings.sav")) if pasta is not None else {}
    if "Lovense: Enabled" not in dados:
        return None
    usa_http = _como_booleano(dados.get("Lovense: Use HTTP"))
    return _Lido(
        ligado=_como_booleano(dados.get("Lovense: Enabled")),
        endereco=str(dados.get("Lovense: Local IP") or "").strip(),
        porta=_porta(dados.get("Lovense: Port")),
        # O «Use HTTP» do jogo vai direto ao parâmetro `isUseHttps` do kit: ligado = https.
        esquema=None if usa_http is None else ("https" if usa_http else "http"),
    )


def _ler_skullgear(raiz: Path, arquivo_do_sinal: Path, appid: str) -> _Lido | None:
    if not appid.isdigit() or raiz.parent.name != "common":
        return None
    base = (
        raiz.parent.parent / "compatdata" / appid / "pfx" / "drive_c" / "users" / "steamuser"
        / "AppData" / "Roaming" / "Skullgear"
    )
    for candidato in arquivos_do_sinal(base, "*/CONFIG.xml"):
        customs = _customs_do_xml(_ler_texto(candidato))
        valores = {n: v for n, v in customs.items() if n.startswith("lovense_")}
        if "lovense_enabled" not in valores:
            continue
        conexao = valores.get("lovense_connection", "").strip().lower()
        # O que não está gravado vale o padrão do jogo: https e a porta 30010.
        esquema = "http" if conexao and "https" not in conexao else "https"
        porta = _porta(valores["lovense_port"]) if "lovense_port" in valores else PORTA_PADRAO_DO_JJ
        return _Lido(
            ligado=_como_booleano(valores["lovense_enabled"]),
            endereco=valores.get("lovense_ip", "").strip(),
            porta=porta,
            esquema=esquema,
        )
    return None


_LEITORES: dict[str, Callable[[Path, Path, str], _Lido | None] | None] = {
    UNITY_SETTINGS_JSON: _ler_unity,
    SKULLGEAR_CONFIG_XML: _ler_skullgear,
    NENHUMA: None,
}


def _classificar(lido: _Lido) -> str:
    """A classe do que o jogo guardou; o endereço morre aqui."""
    if lido.ligado is False:
        return DESLIGADO
    endereco = lido.endereco.lower()
    if lido.ligado is None or not endereco or lido.porta is None:
        return NAO_LIDO
    if endereco in _ENDERECOS_DA_PONTE:
        return ALCANCA_A_PONTE if lido.porta in PORTAS_DA_PONTE else PORTA_QUE_NADA_ATENDE
    if endereco in _ENDERECOS_LOCAIS or endereco.startswith("127."):
        return PORTA_QUE_NADA_ATENDE
    return APONTA_PARA_OUTRA_MAQUINA


def kit_do_jogo(
    raiz: Path | None, appid: str, tabela: Iterable[Kit] | None = None
) -> KitDoJogo | None:
    """O kit do jogo e o veredito da configuração salva; ``None`` quando a pasta não traz kit."""
    achado = reconhecer(raiz, tabela)
    if achado is None or raiz is None:
        return None
    kit, arquivo = achado
    leitor = _LEITORES.get(kit.config)
    lido = leitor(raiz, arquivo, appid) if leitor is not None else None
    if lido is None:
        return KitDoJogo(kit.kit, NAO_LIDO)
    return KitDoJogo(kit.kit, _classificar(lido), lido.porta, lido.esquema)


__all__ = [
    "ALCANCA_A_PONTE",
    "APONTA_PARA_OUTRA_MAQUINA",
    "DESLIGADO",
    "NAO_LIDO",
    "NENHUMA",
    "PORTAS_DA_PONTE",
    "PORTA_QUE_NADA_ATENDE",
    "SKULLGEAR_CONFIG_XML",
    "TABELA",
    "UNITY_SETTINGS_JSON",
    "Kit",
    "KitDoJogo",
    "carregar_tabela",
    "kit_do_jogo",
    "reconhecer",
]
