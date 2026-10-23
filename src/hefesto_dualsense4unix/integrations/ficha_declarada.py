"""A ficha `declarado`: o que a Steam e o binário do jogo dizem sobre controle, com a fonte.

Junta a declaração do desenvolvedor (cache binário da Steam, pelo leitor do `proton_pin`), o
manifesto GDK e os sinais do binário (famílias de API, biblioteca Sony, modelos 0CE6/0DF2).
Três vereditos, cada um com a fonte: `ENTENDE_DUALSENSE` (categoria 57/58 ou biblioteca Sony),
`PREVE_TRADUCAO` (categoria 59 ou layout `controller_ps5`), `SO_XBOX_DECLARADO` (18/28 ou
`controller_support`); sem fonte, `NAO_SEI`. Nunca troca a máscara: `mascara_efetiva` não
importa este módulo. A busca de modelo é por proximidade de bytes: ausência não prova ausência.
"""
from __future__ import annotations

import logging
import mmap
import os
import re
import struct
from collections.abc import Collection, Iterable
from dataclasses import dataclass, field
from pathlib import Path

try:
    from .api_de_entrada import Evidencia, escolher_executavel
    from .proton_pin import (
        _APPINFO_CABECALHO_DA_ENTRADA,
        _APPINFO_MAGICS,
        _chave,
        _ler_vdf_binario,
        default_steam_root,
    )
except ImportError:  # pragma: no cover - executado como script avulso
    from api_de_entrada import Evidencia, escolher_executavel  # type: ignore[no-redef]
    from proton_pin import (  # type: ignore[no-redef]
        _APPINFO_CABECALHO_DA_ENTRADA,
        _APPINFO_MAGICS,
        _chave,
        _ler_vdf_binario,
        default_steam_root,
    )

logger = logging.getLogger(__name__)

ENTENDE_DUALSENSE = "entende_dualsense"
PREVE_TRADUCAO = "preve_traducao"
SO_XBOX_DECLARADO = "so_xbox_declarado"
NAO_SEI = "nao_sei"

#: As categorias da loja que dizem algo sobre controle, com o nome que a Steam dá.
CATEGORIAS: dict[int, str] = {
    18: "controle Xbox parcial",
    28: "controle Xbox completo",
    55: "DualShock por cabo",
    56: "DualShock por Bluetooth",
    57: "DualSense por cabo",
    58: "DualSense por Bluetooth",
    59: "API do Steam Input",
    60: "gamepad recomendado",
}

_DECLARAM_DUALSENSE = frozenset({57, 58})
_DECLARAM_STEAM_INPUT = frozenset({59})
_DECLARAM_XBOX = frozenset({18, 28})
_LAYOUT_DO_DUALSENSE = "controller_ps5"

_CATEGORIA_RE = re.compile(r"^category_(\d+)$", re.IGNORECASE)

def _grafias(*nomes: str) -> tuple[bytes, ...]:
    """Cada nome em ASCII e em UTF-16: o executável guarda os dois."""
    return tuple(
        dict.fromkeys(
            codificado
            for nome in nomes
            for codificado in (nome.encode("ascii"), nome.encode("utf-16-le"))
        )
    )


#: A biblioteca Sony no binário: o nome da fonte e as grafias que a denunciam.
_SINAIS_SONY: tuple[tuple[str, tuple[bytes, ...]], ...] = (
    ("libScePad", _grafias("libScePad", "libscepad")),
    ("scePad", _grafias("scePad", "ScePad")),
    ("WinDualSense", _grafias("WinDualSense")),
    ("WinDualShock", _grafias("WinDualShock")),
)
_VID_SONY = b"\x4c\x05"
_PIDS_SONY: dict[str, bytes] = {"0ce6": b"\xe6\x0c", "0df2": b"\xf2\x0d"}
_JANELA_DO_PID = 8
_PID_DO_VPAD = "0df2"
_PID_DO_DUALSENSE = "0ce6"

_MANIFESTO_GDK = "MicrosoftGame.config"
_PROFUNDIDADE_DA_PASTA = 6
_TETO_DE_ENTRADAS = 50_000
_TETO_DE_BIBLIOTECAS = 4
#: O que o jogo declara do controle fora do executável: o InControl (IL2CPP e Mono), o
#: Rewired e a SDL. Só o `a_roupa_do_jogo` lê estes; o veredito da ficha não muda.
_ARQUIVOS_DA_ROUPA = frozenset(
    {"global-metadata.dat", "incontrol.dll", "rewired_core.dll", "sdl2.dll", "sdl3.dll"}
)
_TETO_DE_ASSETS = 8


@dataclass(frozen=True)
class DeclaracaoDaSteam:
    """O que o desenvolvedor registrou na Steam para um appid."""

    categorias: frozenset[int] = frozenset()
    controller_support: str | None = None
    questionario_respondido: bool = False
    layouts: tuple[str, ...] = ()


@dataclass(frozen=True)
class SinaisDoBinario:
    """O que o executável do jogo (e a biblioteca Sony ao lado dele) mostra."""

    examinado: bool = False
    familias: tuple[str, ...] = ()
    sony: tuple[str, ...] = ()
    pids: tuple[str, ...] = ()
    gdk: bool = False


@dataclass(frozen=True)
class FichaDeclarada:
    """A ficha de UM jogo: os fatos de cada fonte, o veredito e a fonte dele."""

    appid: str
    veredito: str = NAO_SEI
    fontes: tuple[str, ...] = ()
    avisos: tuple[str, ...] = ()
    declaracao: DeclaracaoDaSteam | None = None
    binario: SinaisDoBinario = field(default_factory=SinaisDoBinario)

    @property
    def declara_dualsense(self) -> bool:
        """A Steam registra o jogo com suporte ao DualSense (categoria 57 ou 58)?"""
        return self.declaracao is not None and bool(
            self.declaracao.categorias & _DECLARAM_DUALSENSE
        )

    @property
    def declara_steam_input(self) -> bool:
        """O jogo previu a tradução do Steam Input (categoria 59 ou layout do DualSense)?"""
        decl = self.declaracao
        return decl is not None and (
            bool(decl.categorias & _DECLARAM_STEAM_INPUT)
            or _LAYOUT_DO_DUALSENSE in decl.layouts
        )

    def como_dicionario(self) -> dict[str, object]:
        decl = self.declaracao
        return {
            "veredito": self.veredito,
            "fontes": list(self.fontes),
            "avisos": list(self.avisos),
            "categorias": sorted(decl.categorias) if decl else [],
            "controller_support": decl.controller_support if decl else None,
            "questionario_respondido": decl.questionario_respondido if decl else False,
            "layouts": list(decl.layouts) if decl else [],
            "gdk": self.binario.gdk,
            "binario_examinado": self.binario.examinado,
            "familias": list(self.binario.familias),
            "sinais_sony": list(self.binario.sony),
            "pids": [p.upper() for p in self.binario.pids],
        }


# ---------------------------------------------------------------------------
# A declaração da Steam


def caminho_do_cache_da_steam(home: Path | None = None) -> Path:
    """Onde a Steam guarda o cache binário de cada app (arquivo interno dela)."""
    return default_steam_root(home) / "appcache" / "appinfo.vdf"


def _categorias(common: object) -> frozenset[int]:
    mapa = _chave(common, "category")
    if not isinstance(mapa, dict):
        return frozenset()
    achadas: set[int] = set()
    for nome in mapa:
        casou = _CATEGORIA_RE.match(str(nome))
        if casou is not None:
            achadas.add(int(casou.group(1)))
    return frozenset(achadas)


def _layouts(config: object) -> tuple[str, ...]:
    detalhes = _chave(config, "steamcontrollerconfigdetails")
    if not isinstance(detalhes, dict):
        return ()
    tipos = {
        str(tipo).strip()
        for entrada in detalhes.values()
        if isinstance(tipo := _chave(entrada, "controller_type"), str) and tipo.strip()
    }
    return tuple(sorted(tipos))


def declaracao_do_vdf(vdf: object) -> DeclaracaoDaSteam:
    """A declaração a partir do mapa já lido de UM app (a raiz ou o bloco `appinfo`)."""
    raiz = _chave(vdf, "appinfo") or vdf
    common = _chave(raiz, "common")
    suporte = _chave(common, "controller_support")
    return DeclaracaoDaSteam(
        categorias=_categorias(common),
        controller_support=(
            suporte.strip().lower() if isinstance(suporte, str) and suporte.strip() else None
        ),
        questionario_respondido=_chave(common, "controllertagwizard") == 1,
        layouts=_layouts(_chave(raiz, "config")),
    )


def declaracoes_do_cache(
    cache: Path, appids: Collection[str]
) -> dict[str, DeclaracaoDaSteam] | None:
    """A declaração de cada appid pedido que o cache tem; `None` se o cache não se lê.

    O formato é da Steam e não é prometido: qualquer coisa fora do esperado devolve
    `None` (a ficha passa a dizer que a fonte não falou), nunca um valor inventado.
    """
    procurados = {str(a) for a in appids}
    if not procurados:
        return {}
    achados: dict[str, DeclaracaoDaSteam] = {}
    try:
        with cache.open("rb") as fh:
            cabeca = fh.read(8)
            if len(cabeca) < 8:
                return None
            magia, _universo = struct.unpack("<II", cabeca)
            versao = _APPINFO_MAGICS.get(magia)
            if versao is None:
                return None
            chaves: list[str] | None = None
            if versao >= 29:
                (tabela,) = struct.unpack("<q", fh.read(8))
                inicio_das_entradas = fh.tell()
                fh.seek(tabela)
                bruto = fh.read()
                (quantas,) = struct.unpack_from("<I", bruto, 0)
                chaves = [
                    s.decode("utf-8", "replace") for s in bruto[4:].split(b"\0")[:quantas]
                ]
                fh.seek(inicio_das_entradas)
            while procurados - achados.keys():
                par = fh.read(8)
                if len(par) < 8:
                    break
                appid, tamanho = struct.unpack("<II", par)
                if appid == 0:
                    break
                if str(appid) not in procurados:
                    fh.seek(tamanho, os.SEEK_CUR)
                    continue
                entrada = fh.read(tamanho)
                if len(entrada) < tamanho:
                    return None
                vdf, _ = _ler_vdf_binario(entrada, _APPINFO_CABECALHO_DA_ENTRADA, chaves)
                achados[str(appid)] = declaracao_do_vdf(vdf)
    except (OSError, ValueError, IndexError, struct.error) as erro:
        logger.debug("o cache da Steam não se leu, a ficha cai no binário: %s", erro)
        return None
    return achados


# ---------------------------------------------------------------------------
# O que o disco do jogo mostra


def _bibliotecas_e_manifesto(
    raiz: Path, roupa: list[Path] | None = None, pastas: list[Path] | None = None
) -> tuple[list[Path], bool]:
    """As `libScePad*` e o `MicrosoftGame.config` da pasta, com teto de profundidade.

    Com `roupa`, junta nela os arquivos da roupa (`_ARQUIVOS_DA_ROUPA` e os
    primeiros `sharedassets<N>.assets`, com o `resources.assets`), na mesma volta.
    Com `pastas`, junta nela as subpastas por onde a varredura andou (a raiz não entra):
    arquivo que nasce ou some numa delas muda o `mtime` dela, e é o que o cache vigia.
    """
    bibliotecas: list[Path] = []
    assets: list[Path] = []
    gdk = False
    visitadas = 0
    pilha: list[tuple[Path, int]] = [(raiz, 0)]
    while pilha:
        pasta, fundo = pilha.pop()
        if pastas is not None and fundo > 0:
            pastas.append(pasta)
        try:
            with os.scandir(pasta) as entradas:
                for entrada in entradas:
                    visitadas += 1
                    if visitadas > _TETO_DE_ENTRADAS:
                        pilha.clear()
                        break
                    try:
                        e_pasta = entrada.is_dir(follow_symlinks=False)
                    except OSError:
                        e_pasta = False
                    if e_pasta:
                        if fundo < _PROFUNDIDADE_DA_PASTA:
                            pilha.append((Path(entrada.path), fundo + 1))
                        continue
                    nome = entrada.name.lower()
                    if nome == _MANIFESTO_GDK.lower():
                        gdk = True
                    elif nome.startswith("libscepad") and len(bibliotecas) < _TETO_DE_BIBLIOTECAS:
                        bibliotecas.append(Path(entrada.path))
                    elif roupa is None:
                        continue
                    elif nome in _ARQUIVOS_DA_ROUPA:
                        roupa.append(Path(entrada.path))
                    elif _ordem_do_asset(nome) is not None:
                        assets.append(Path(entrada.path))
        except OSError as erro:
            logger.debug("pasta do jogo ilegível, fica fora da ficha: %s: %s", pasta, erro)
    if roupa is not None:
        assets.sort(key=lambda p: _ordem_do_asset(p.name.lower()) or 0)
        roupa.extend(assets[:_TETO_DE_ASSETS])
    return bibliotecas, gdk


def _ordem_do_asset(nome: str) -> int | None:
    """`resources.assets` primeiro, depois `sharedassets<N>.assets` pelo N; o resto, `None`."""
    if nome == "resources.assets":
        return -1
    casou = re.fullmatch(r"sharedassets(\d+)\.assets", nome)
    return int(casou.group(1)) if casou else None


def _ler_o_arquivo(arquivo: Path) -> tuple[set[str], set[str]]:
    """`(sinais Sony, modelos Sony)` achados num arquivo; vazio se ele não se lê."""
    sony: set[str] = set()
    pids: set[str] = set()
    try:
        if arquivo.stat().st_size == 0:
            return sony, pids
        with (
            arquivo.open("rb") as fh,
            mmap.mmap(fh.fileno(), 0, access=mmap.ACCESS_READ) as mapa,
        ):
            for nome, agulhas in _SINAIS_SONY:
                if any(mapa.find(a) != -1 for a in agulhas):
                    sony.add(nome)
            posicao = mapa.find(_VID_SONY)
            while posicao != -1 and len(pids) < len(_PIDS_SONY):
                janela = mapa[max(0, posicao - _JANELA_DO_PID): posicao + _JANELA_DO_PID + 2]
                for nome_pid, bytes_pid in _PIDS_SONY.items():
                    if bytes_pid in janela:
                        pids.add(nome_pid)
                posicao = mapa.find(_VID_SONY, posicao + 1)
    except (OSError, ValueError):
        return set(), set()
    return sony, pids


def examinar_o_binario(raiz: Path, evidencia: Evidencia | None = None) -> SinaisDoBinario:
    """Os sinais de UM jogo, a partir da pasta (e da evidência de API, se já se tem)."""
    executavel = evidencia.executavel if evidencia is not None else escolher_executavel(raiz)
    bibliotecas, gdk = _bibliotecas_e_manifesto(raiz)
    sony: set[str] = {"libScePad"} if bibliotecas else set()
    pids: set[str] = set()
    arquivos = ([executavel] if executavel is not None else []) + bibliotecas
    for arquivo in arquivos:
        do_arquivo, dos_pids = _ler_o_arquivo(arquivo)
        sony |= do_arquivo
        pids |= dos_pids
    familias = (
        tuple(sorted(f.value for f in evidencia.familias)) if evidencia is not None else ()
    )
    return SinaisDoBinario(
        examinado=True,
        familias=familias,
        sony=tuple(sorted(sony)),
        pids=tuple(sorted(pids)),
        gdk=gdk,
    )


# ---------------------------------------------------------------------------
# O veredito


def _nomes(categorias: Iterable[int]) -> str:
    return ", ".join(f"{n} ({CATEGORIAS[n]})" for n in sorted(categorias))


def julgar(
    declaracao: DeclaracaoDaSteam | None, binario: SinaisDoBinario
) -> tuple[str, tuple[str, ...]]:
    """`(veredito, fontes)`. A primeira camada que fala decide; as fontes dizem por quê."""
    cats = declaracao.categorias if declaracao else frozenset()
    layouts = declaracao.layouts if declaracao else ()
    fontes: list[str] = []
    if cats & _DECLARAM_DUALSENSE:
        declaradas = _nomes(cats & _DECLARAM_DUALSENSE)
        fontes.append(f"a Steam registra o suporte ao DualSense: categoria {declaradas}")
    if binario.sony:
        fontes.append(
            f"o binário do jogo traz a biblioteca Sony: {', '.join(binario.sony)}"
        )
    if fontes:
        return ENTENDE_DUALSENSE, tuple(fontes)
    if cats & _DECLARAM_STEAM_INPUT:
        fontes.append("a Steam registra a API do Steam Input: categoria 59")
    if _LAYOUT_DO_DUALSENSE in layouts:
        fontes.append(
            "o jogo publica um layout do Steam Input para o DualSense (controller_ps5)"
        )
    if fontes:
        return PREVE_TRADUCAO, tuple(fontes)
    if cats & _DECLARAM_XBOX:
        declaradas = _nomes(cats & _DECLARAM_XBOX)
        fontes.append(f"a Steam registra só o controle Xbox: categoria {declaradas}")
    suporte = declaracao.controller_support if declaracao else None
    if suporte is not None:
        fontes.append(f"a Steam registra controller_support = {suporte}")
    if fontes:
        return SO_XBOX_DECLARADO, tuple(fontes)
    return NAO_SEI, ()


def _avisos(binario: SinaisDoBinario) -> tuple[str, ...]:
    if _PID_DO_DUALSENSE in binario.pids and _PID_DO_VPAD not in binario.pids:
        return (
            "o executável conhece o modelo 0CE6 do DualSense e não o 0DF2, que é o modelo "
            "do controle virtual; um jogo de tabela fixa de modelos pode não o reconhecer "
            "como DualSense",
        )
    return ()


def montar_ficha(
    appid: str,
    declaracao: DeclaracaoDaSteam | None,
    binario: SinaisDoBinario | None = None,
) -> FichaDeclarada:
    """A ficha de um jogo a partir das fontes já lidas (função pura)."""
    sinais = binario if binario is not None else SinaisDoBinario()
    veredito, fontes = julgar(declaracao, sinais)
    return FichaDeclarada(
        appid=str(appid),
        veredito=veredito,
        fontes=fontes,
        avisos=_avisos(sinais),
        declaracao=declaracao,
        binario=sinais,
    )


def fichas_dos_jogos(
    jogos: Iterable[tuple[str, Path | None, Evidencia | None]],
    *,
    home: Path | None = None,
    examinar: bool = True,
) -> dict[str, FichaDeclarada]:
    """`{appid: ficha}` de `[(appid, pasta, evidência de API)]`; lê o cache UMA vez."""
    lista = list(jogos)
    declaracoes = declaracoes_do_cache(
        caminho_do_cache_da_steam(home), [appid for appid, _, _ in lista]
    )
    fichas: dict[str, FichaDeclarada] = {}
    for appid, raiz, evidencia in lista:
        binario = (
            examinar_o_binario(raiz, evidencia)
            if examinar and raiz is not None
            else SinaisDoBinario()
        )
        decl = declaracoes.get(str(appid)) if declaracoes is not None else None
        fichas[str(appid)] = montar_ficha(appid, decl, binario)
    return fichas


# ---------------------------------------------------------------------------
# A capa da biblioteca


def explicar_a_capa(
    ficha: FichaDeclarada,
    *,
    steam_input_ligado: bool | None,
    ps_support_global: str | None,
) -> str | None:
    """Por que a capa da Steam mostra o que mostra para o DualSense, ou `None`.

    A capa só conhece dois caminhos, «o jogo declarou» ou «a Steam traduz»: mede o
    questionário que o desenvolvedor preencheu e se o Steam Input está ligado para o
    controle. Com 57/58 ou 59 declarados, ou com o Steam Input ligado, ela não diz nada
    de errado e não há o que explicar.
    """
    decl = ficha.declaracao
    if decl is None or ficha.declara_dualsense or ficha.declara_steam_input:
        return None
    if steam_input_ligado:
        return None
    if not (decl.categorias & _DECLARAM_XBOX or decl.controller_support):
        return None
    if not decl.questionario_respondido:
        return (
            "A Steam diz «Unknown Controller Support» porque o desenvolvedor do jogo "
            "não respondeu o questionário de controle."
        )
    quem = (
        "pelo Hefesto"
        if (ps_support_global or "").strip() == "0"
        else "para este jogo"
    )
    texto = (
        "A Steam diz «Device Not Supported» porque o jogo não declarou DualSense "
        f"e o Steam Input dos controles PlayStation está desligado {quem}."
    )
    if ficha.binario.sony:
        texto += (
            " O binário do jogo traz a biblioteca Sony, então ele pode entender "
            "o DualSense mesmo sem declarar."
        )
    return texto
