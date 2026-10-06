"""As camadas Vulkan implícitas que moram DENTRO do prefixo Wine de cada jogo."""
from __future__ import annotations

import argparse
import contextlib
import json
import os
import re
import shutil
import sys
import time
from collections.abc import Callable, Collection
from dataclasses import dataclass
from pathlib import Path

_LIGADA = 0

_DESLIGADA_DWORD = "00000001"

_SECAO_RE = re.compile(r"^\[(?P<chave>.*?)\](?:\s|$)")

_ENTRADA_DWORD_RE = re.compile(
    r'^(?P<prefixo>"(?P<nome>(?:\\.|[^"\\])*)"=dword:)(?P<valor>[0-9a-fA-F]+)(?P<sufixo>\s*)$'
)

CHAVES_DE_CAMADAS: tuple[str, ...] = (
    r"Software\Khronos\Vulkan\ImplicitLayers",
    r"Software\Wow6432Node\Khronos\Vulkan\ImplicitLayers",
)

NOME_DO_DRIVER_DO_WINE = "winevulkan.json"

CAMADAS_PRESERVADAS: tuple[tuple[str, str], ...] = (
    ("winevulkan", "driver Vulkan do Wine"),
    ("wineopenxr", "OpenXR do Wine"),
    ("steamoverlay", "sobreposição da Steam (Shift+Tab, captura, tela de controle)"),
    ("steam_overlay", "sobreposição da Steam"),
    ("fossilize", "pré-cache de shader da Steam"),
    ("mangohud", "MangoHud — medidor de quadro"),
    ("gamescope", "gamescope — compositor da Valve"),
    ("reshade", "ReShade — filtro de imagem"),
    ("dxvk", "DXVK (HUD, config, NVAPI)"),
    ("vkd3d", "VKD3D-Proton"),
    ("obs_vkcapture", "OBS — captura de tela do jogo"),
    ("obs-vkcapture", "OBS — captura de tela do jogo"),
    ("vkbasalt", "vkBasalt — filtro de imagem"),
    ("optimus", "NVIDIA Optimus"),
    ("nvidia", "camada da NVIDIA"),
    ("amd_switchable", "AMD switchable graphics"),
)

ESTADO_BASENAME = "camadas-vulkan.json"

_BACKUP_SUFIXO = ".bak.hefesto-camadas-"


def desescapar(valor: str) -> str:
    """Desfaz o escape do `system.reg` (`\\\\` e `\\"`)."""
    return valor.replace('\\\\', '\\').replace('\\"', '"')


def _escapar(valor: str) -> str:
    """Refaz o escape do `system.reg`. Inverso exato de `desescapar`.

    **Privada de propósito, e a razão importa:** o produto NUNCA reescapa nada.
    A escrita em `_reescrever` reaproveita o texto original da entrada
    (`entrada.group("prefixo")`) e troca só os dígitos do dword, justamente
    para não depender de reproduzir byte a byte o escape que o Wine escreveu.
    Quem chama isto é o construtor de `system.reg` de mentira dos testes, que
    precisa do inverso PROVADO do parser — se fosse pública, seria promessa
    sem chamador, e o portão `portao_a_casa_sabe_e_o_produto_nao_faz.py` a
    acusaria com razão.
    """
    return valor.replace('\\', '\\\\').replace('"', '\\"')


def _e_o_driver(caminho_windows: str) -> bool:
    """`True` para o `winevulkan.json`, em qualquer caixa e qualquer pasta."""
    return _nome_do_arquivo(caminho_windows) == NOME_DO_DRIVER_DO_WINE


def _nome_do_arquivo(caminho_windows: str) -> str:
    """Último componente de um caminho do Windows, em minúsculas."""
    bruto = caminho_windows.replace("/", "\\").rsplit("\\", 1)[-1]
    return bruto.strip().lower()


def dono_preservado(caminho_windows: str) -> str | None:
    """Quem é o dono desta camada, se ela está entre as preservadas."""
    nome = _nome_do_arquivo(caminho_windows)
    for pedaco, dono in CAMADAS_PRESERVADAS:
        if pedaco in nome:
            return dono
    return None


@dataclass(frozen=True)
class Camada:
    """Uma linha de `ImplicitLayers` já interpretada."""

    caminho_windows: str
    chave: str
    valor: str
    ligada: bool
    presente: bool
    arquivo: Path | None
    preservada_por: str | None

    @property
    def nome_curto(self) -> str:
        """O nome do arquivo do manifesto, que é o que cabe numa linha de tela."""
        return self.caminho_windows.replace("/", "\\").rsplit("\\", 1)[-1]

    @property
    def e_o_driver(self) -> bool:
        """Atalho de leitura — a recusa de verdade mora em `_e_o_driver`."""
        return _e_o_driver(self.caminho_windows)

    @property
    def e_sobra(self) -> bool:
        """Sobra = candidata à cura: nem driver, nem preservada, e LIGADA."""
        return self.ligada and not self.e_o_driver and self.preservada_por is None


@dataclass(frozen=True)
class PrefixoDeJogo:
    """Um `compatdata/<appid>` com o que foi lido do `system.reg` dele."""

    appid: str
    raiz: Path
    registro: Path
    camadas: tuple[Camada, ...]
    nome: str | None = None

    @property
    def sobras(self) -> tuple[Camada, ...]:
        """As camadas que a cura desligaria."""
        return tuple(c for c in self.camadas if c.e_sobra)

    @property
    def rotulo(self) -> str:
        """`Nome do jogo (appid)` — ou só o appid quando não há manifest."""
        return f"{self.nome} ({self.appid})" if self.nome else self.appid


def caminho_no_prefixo(prefixo: Path, caminho_windows: str) -> Path | None:
    """Traduz `C:\\...` para o caminho Linux dentro do prefixo."""
    bruto = caminho_windows.replace("/", "\\")
    if len(bruto) < 2 or bruto[1] != ":":
        return None
    letra = bruto[0].lower()
    resto = bruto[2:].lstrip("\\")
    partes = [p for p in resto.split("\\") if p]
    if letra == "c":
        return prefixo.joinpath("pfx", "drive_c", *partes)
    if letra == "z":
        return Path("/").joinpath(*partes)
    return None


def ler_camadas(registro: Path, *, prefixo: Path | None = None) -> tuple[Camada, ...]:
    """Lê as duas seções `ImplicitLayers` de um `system.reg`."""
    try:
        texto = registro.read_text(encoding="utf-8", errors="replace")
    except OSError:
        return ()
    base = prefixo if prefixo is not None else registro.parent.parent
    achadas: list[Camada] = []
    chave_atual: str | None = None
    for linha in texto.splitlines():
        if linha.startswith("["):
            secao = _SECAO_RE.match(linha)
            crua = desescapar(secao.group("chave")) if secao is not None else ""
            chave_atual = crua if crua in CHAVES_DE_CAMADAS else None
            continue
        if chave_atual is None or not linha.startswith('"'):
            continue
        entrada = _ENTRADA_DWORD_RE.match(linha)
        if entrada is None:
            continue
        caminho = desescapar(entrada.group("nome"))
        arquivo = caminho_no_prefixo(base, caminho)
        try:
            presente = arquivo is not None and arquivo.exists()
        except OSError:  # pragma: no cover - permissão negada no meio do caminho
            presente = False
        achadas.append(
            Camada(
                caminho_windows=caminho,
                chave=chave_atual,
                valor=entrada.group("valor"),
                ligada=int(entrada.group("valor"), 16) == _LIGADA,
                presente=presente,
                arquivo=arquivo,
                preservada_por=dono_preservado(caminho),
            )
        )
    return tuple(achadas)


def prefixo_de_jogo(
    raiz: Path, *, appid: str | None = None, nome: str | None = None
) -> PrefixoDeJogo:
    """Monta o `PrefixoDeJogo` de um `compatdata/<appid>` já localizado."""
    registro = raiz / "pfx" / "system.reg"
    return PrefixoDeJogo(
        appid=appid if appid is not None else raiz.name,
        raiz=raiz,
        registro=registro,
        camadas=ler_camadas(registro, prefixo=raiz),
        nome=nome,
    )


def _pastas_steamapps_do_irmao() -> Callable[[Path | None], list[Path]] | None:
    """O `pastas_steamapps` do irmão, ou `None` quando ele não está alcançável."""
    try:
        from .steam_launch_options import pastas_steamapps
    except ImportError:  # pragma: no cover - cópia avulsa, sem o pacote
        try:
            from steam_launch_options import pastas_steamapps  # type: ignore[no-redef]
        except ImportError:
            return None
    return pastas_steamapps


def sabe_enumerar() -> bool:
    """Esta cópia consegue LISTAR os jogos, ou só curar um prefixo apontado?"""
    return _pastas_steamapps_do_irmao() is not None


def pastas_compatdata(home: Path | None = None) -> list[Path]:
    """Todo `steamapps/compatdata` desta máquina, biblioteca por biblioteca."""
    if not sabe_enumerar():
        return []
    pastas_steamapps = _pastas_steamapps_do_irmao()
    assert pastas_steamapps is not None
    saida: list[Path] = []
    for steamapps in pastas_steamapps(home):
        candidata = steamapps / "compatdata"
        if candidata.is_dir():
            saida.append(candidata)
    return saida


_CONFIG_DO_HEROIC = (
    ".var/app/com.heroicgameslauncher.hgl/config/heroic",
    ".config/heroic",
)

_RAIZES_DE_JOGO = (
    "Games",
    ".local/share/lutris",
    ".var/app/net.lutris.Lutris/data/lutris",
)

_MAXIMO_DE_FILHOS_POR_RAIZ = 400

_DO_XDG = ((".config/", "XDG_CONFIG_HOME"), (".local/share/", "XDG_DATA_HOME"))


def _no_lar(relativo: str, home: Path | None) -> Path:
    """O caminho de uma casa: no lar dado, ou no XDG do ambiente quando o lar é o"""
    lar = Path.home() if home is None else home
    for comeco, variavel in _DO_XDG:
        valor = os.environ.get(variavel, "").strip() if home is None else ""
        if relativo.startswith(comeco) and os.path.isabs(valor):
            return Path(valor) / relativo[len(comeco):]
    return lar / relativo


def prefixos_dos_lancadores(home: Path | None = None) -> list[Path]:
    """Todo prefixo wine de lançador que NÃO é a Steam. Read-only."""
    achados: list[Path] = []
    vistos: set[Path] = set()

    def _guardar(caminho: object) -> None:
        if not isinstance(caminho, str) or not caminho.strip():
            return
        alvo = Path(caminho.strip())
        try:
            if not (alvo / "pfx" / "system.reg").is_file():
                return
            real = alvo.resolve()
        except OSError:
            return
        if real in vistos:
            return
        vistos.add(real)
        achados.append(alvo)

    for relativo in _CONFIG_DO_HEROIC:
        pasta = _no_lar(relativo, home)
        if not pasta.is_dir():
            continue
        for arquivo in sorted((pasta / "GamesConfig").glob("*.json")):
            try:
                dado = json.loads(arquivo.read_text(encoding="utf-8"))
            except (OSError, ValueError):
                continue
            for valor in (dado or {}).values():
                if isinstance(valor, dict):
                    _guardar(valor.get("winePrefix"))
        try:
            conf = json.loads((pasta / "config.json").read_text(encoding="utf-8"))
        except (OSError, ValueError):
            continue
        padroes = (conf or {}).get("defaultSettings")
        raiz = (padroes or {}).get("defaultWinePrefix") if isinstance(
            padroes, dict) else None
        if isinstance(raiz, str) and raiz.strip():
            try:
                filhos = sorted(Path(raiz.strip()).iterdir())
            except OSError:
                continue
            for filho in filhos:
                _guardar(str(filho))

    for relativo in _RAIZES_DE_JOGO:
        raiz = _no_lar(relativo, home)
        try:
            filhos = sorted(raiz.iterdir())[:_MAXIMO_DE_FILHOS_POR_RAIZ]
        except OSError:
            continue
        for filho in filhos:
            _guardar(str(filho))
    return achados


def raizes_de_prefixo(home: Path | None = None) -> list[Path]:
    """TODO prefixo wine desta máquina — Steam e os outros lançadores."""
    saida: list[Path] = []
    for compatdata in pastas_compatdata(home):
        try:
            entradas = sorted(compatdata.iterdir())
        except OSError:
            continue
        for raiz in entradas:
            if raiz.is_dir() and (raiz / "pfx").is_dir():
                saida.append(raiz)
    saida.extend(prefixos_dos_lancadores(home))
    return saida


def _nome_do_appid(appid: str, home: Path | None = None) -> str | None:
    """Nome do jogo pelo `appmanifest`, reusando o dono do formato."""
    try:
        from .steam_launch_options import nome_do_appid
    except ImportError:  # pragma: no cover - cópia avulsa, sem o pacote
        try:
            from steam_launch_options import nome_do_appid  # type: ignore[no-redef]
        except ImportError:
            return None
    try:
        return nome_do_appid(appid, home)
    except Exception:  # pragma: no cover - tradução é conveniência, nunca gate
        return None


def censo(home: Path | None = None, *, com_nomes: bool = True) -> list[PrefixoDeJogo]:
    """Todos os prefixos, com as camadas de cada um. Read-only."""
    saida: list[PrefixoDeJogo] = []
    for raiz in raizes_de_prefixo(home):
        achado = prefixo_de_jogo(raiz)
        if not achado.camadas:
            continue
        if com_nomes:
            achado = PrefixoDeJogo(
                appid=achado.appid,
                raiz=achado.raiz,
                registro=achado.registro,
                camadas=achado.camadas,
                nome=(_nome_do_appid(achado.appid, home)
                      if achado.appid.isdigit() else raiz.name),
            )
        saida.append(achado)
    saida.sort(key=lambda p: (not p.appid.isdigit(), p.appid.zfill(12)))
    return saida


AMBIENTE_SEM_AS_CAMADAS_DA_STEAM: tuple[str, ...] = (
    "DISABLE_VK_LAYER_VALVE_steam_overlay_1=1",
    "DISABLE_VK_LAYER_VALVE_steam_fossilize_1=1",
)

ESCOLHA_RELPATH = "hefesto-dualsense4unix/camadas_da_steam_fora.env"

CARREGADOR_DA_KHRONOS = "vulkan-1.dll"

_FUNDO_DA_BUSCA = 4
_TETO_DA_BUSCA = 20_000


def caminho_da_escolha(config_home: Path | None = None) -> Path:
    """``$XDG_CONFIG_HOME/hefesto-dualsense4unix/camadas_da_steam_fora.env``."""
    if config_home is None:
        xdg = os.environ.get("XDG_CONFIG_HOME", "").strip()
        config_home = Path(xdg) if xdg else Path.home() / ".config"
    return config_home / ESCOLHA_RELPATH


def camadas_da_steam_fora(config_home: Path | None = None) -> bool:
    """O «Corrigir Vulkan» está ligado? A pergunta que o lançador também faz."""
    try:
        bruto = caminho_da_escolha(config_home).read_bytes()
    except OSError:
        return False
    presentes = set(bruto.decode("utf-8", errors="replace").split("\n"))
    return all(linha in presentes for linha in AMBIENTE_SEM_AS_CAMADAS_DA_STEAM)


def gravar_camadas_da_steam_fora(fora: bool, config_home: Path | None = None) -> None:
    """Liga (as linhas, com tmp e `os.replace`) ou desliga (o arquivo sai)."""
    alvo = caminho_da_escolha(config_home)
    if not fora:
        alvo.unlink(missing_ok=True)
        return
    alvo.parent.mkdir(parents=True, exist_ok=True)
    tmp = alvo.with_name(f"{alvo.name}.tmp")
    tmp.write_text(
        "# O «Corrigir Vulkan» da aba Sistema: o lançador entrega estas linhas ao\n"
        "# jogo. Sem este arquivo, a Steam decide.\n"
        + "".join(f"{linha}\n" for linha in AMBIENTE_SEM_AS_CAMADAS_DA_STEAM),
        encoding="utf-8",
    )
    os.replace(tmp, alvo)


def a_steam_instalou_as_camadas(home: Path | None = None) -> bool:
    """A Steam pôs as camadas dela neste computador? Read-only, nunca levanta."""
    lar = Path.home() if home is None else home
    pastas = [lar / ".local" / "share"]
    xdg = os.environ.get("XDG_DATA_HOME", "").strip()
    if xdg and home is None:
        pastas.insert(0, Path(xdg))
    for pasta in pastas:
        try:
            if any((pasta / "vulkan" / "implicit_layer.d").glob("steam*.json")):
                return True
        except OSError:
            continue
    return False


def traz_o_carregador_da_khronos(pasta_do_jogo: Path) -> bool:
    """A pasta do jogo traz o `vulkan-1.dll` da Khronos? Read-only, nunca levanta."""
    alvo = CARREGADOR_DA_KHRONOS.lower()
    fila: list[tuple[Path, int]] = [(pasta_do_jogo, 0)]
    vistas = 0
    while fila:
        pasta, fundo = fila.pop(0)
        try:
            entradas = list(os.scandir(pasta))
        except OSError:
            continue
        for entrada in entradas:
            vistas += 1
            if vistas > _TETO_DA_BUSCA:
                return False
            try:
                if entrada.is_file() and entrada.name.lower() == alvo:
                    return True
                if fundo + 1 < _FUNDO_DA_BUSCA and entrada.is_dir(follow_symlinks=False):
                    fila.append((Path(entrada.path), fundo + 1))
            except OSError:
                continue
    return False


def frase_do_estado(fora: bool) -> str:
    """*"Sobreposição Vulkan: sem a da Steam"*, ou a Steam decide."""
    if fora:
        return "Sobreposição Vulkan: sem a da Steam"
    return "Sobreposição Vulkan: a Steam decide"


def frase_do_ato(fora: bool) -> str:
    """O recibo do clique no «Corrigir Vulkan» — o ato não se vê na hora."""
    if fora:
        return ("Pronto: a sobreposição e o gravador de shaders da Steam ficam fora "
                "dos jogos, a partir do próximo que abrir.")
    return ("Pronto: a Steam volta a decidir a sobreposição e o gravador de "
            "shaders, a partir do próximo jogo que abrir.")


def ha_o_que_devolver(home: Path | None = None) -> bool:
    """O estado diz que NÓS desligamos alguma camada de algum prefixo?"""
    return any(
        registro.get("feito") == "desligada"
        for camadas in ler_estado(home).values()
        for registro in camadas.values()
    )


def caminho_do_estado(home: Path | None = None) -> Path:
    """`~/.local/state/hefesto-dualsense4unix/camadas-vulkan.json`."""
    base = home or Path.home()
    xdg = os.environ.get("XDG_STATE_HOME", "").strip()
    state_home = Path(xdg) if xdg and home is None else base / ".local/state"
    return state_home / "hefesto-dualsense4unix" / ESTADO_BASENAME


def ler_estado(home: Path | None = None) -> dict[str, dict[str, dict[str, str]]]:
    """Lê o estado local. Arquivo ausente ou torto devolve dicionário vazio."""
    try:
        dados = json.loads(caminho_do_estado(home).read_text(encoding="utf-8"))
    except (OSError, ValueError):
        return {}
    prefixos = dados.get("prefixos") if isinstance(dados, dict) else None
    if not isinstance(prefixos, dict):
        return {}
    limpo: dict[str, dict[str, dict[str, str]]] = {}
    for appid, camadas in prefixos.items():
        if not isinstance(camadas, dict):
            continue
        limpo[str(appid)] = {
            str(k): v for k, v in camadas.items() if isinstance(v, dict)
        }
    return limpo


def gravar_estado(
    prefixos: dict[str, dict[str, dict[str, str]]], home: Path | None = None
) -> None:
    """Grava o estado local (tmp + replace). Falha aqui NUNCA derruba a cura."""
    alvo = caminho_do_estado(home)
    try:
        alvo.parent.mkdir(parents=True, exist_ok=True)
        tmp = alvo.with_suffix(".json.tmp")
        tmp.write_text(
            json.dumps({"formato": 1, "prefixos": prefixos}, ensure_ascii=False, indent=2),
            encoding="utf-8",
        )
        os.replace(tmp, alvo)
    except OSError:
        return


_FEITO_CADUCO = "religada-por-fora"

_FEITO_PELA_EXCLUSAO = "religada-pela-exclusao"


def _e_escolha_dela(registro_dela: dict[str, str]) -> bool:
    """O `manter` deste registro veio de um GESTO do usuário, ou de uma inferência?"""
    if registro_dela.get("escolha") != "manter":
        return False
    return registro_dela.get("feito") != _FEITO_CADUCO


def _agora() -> str:
    """Carimbo legível, hora local, sem dependência externa."""
    return time.strftime("%Y-%m-%dT%H:%M:%S")


def chave_de_estado(chave: str, caminho_windows: str) -> str:
    """Identidade de UMA entrada no estado local: a chave do registro E o caminho."""
    return f"{chave}|{caminho_windows}"


@dataclass(frozen=True)
class Resultado:
    """O que a cura fez num prefixo — é isto que a interface transforma em frase."""

    appid: str
    desligadas: tuple[str, ...] = ()
    religadas: tuple[str, ...] = ()
    respeitadas: tuple[str, ...] = ()
    erro: str = ""

    @property
    def mexeu(self) -> bool:
        """Houve escrita? Usado para decidir se vale gravar estado e avisar."""
        return bool(self.desligadas or self.religadas)


def _reescrever(registro: Path, alvos: dict[tuple[str, str], str]) -> None:
    """Troca o dword das entradas nomeadas em `alvos`, e só delas."""
    texto = registro.read_text(encoding="utf-8", errors="replace")
    saida: list[str] = []
    chave_atual: str | None = None
    quebra = "\r\n" if "\r\n" in texto else "\n"
    for linha in texto.split(quebra):
        if linha.startswith("["):
            secao = _SECAO_RE.match(linha)
            crua = desescapar(secao.group("chave")) if secao is not None else ""
            chave_atual = crua if crua in CHAVES_DE_CAMADAS else None
            saida.append(linha)
            continue
        if chave_atual is None or not linha.startswith('"'):
            saida.append(linha)
            continue
        entrada = _ENTRADA_DWORD_RE.match(linha)
        if entrada is None:
            saida.append(linha)
            continue
        caminho = desescapar(entrada.group("nome"))
        novo = alvos.get((chave_atual, caminho))
        if novo is None:
            saida.append(linha)
            continue
        saida.append(f"{entrada.group('prefixo')}{novo}{entrada.group('sufixo')}")
    backup = registro.with_name(f"{registro.name}{_BACKUP_SUFIXO}{int(time.time())}")
    shutil.copy2(registro, backup)
    tmp = registro.with_name(f"{registro.name}.hefesto-tmp")
    tmp.write_text(quebra.join(saida), encoding="utf-8")
    os.replace(tmp, registro)


def aplicar_no_prefixo(
    prefixo: PrefixoDeJogo,
    *,
    religar: bool = False,
    forcar: bool = False,
    home: Path | None = None,
    pela_exclusao: bool = False,
) -> Resultado:
    """Desliga (ou religa) as camadas sobrando deste prefixo."""
    estado = ler_estado(home)
    memoria = dict(estado.get(prefixo.appid, {}))
    alvos: dict[tuple[str, str], str] = {}
    desligadas: list[str] = []
    religadas: list[str] = []
    respeitadas: list[str] = []

    if religar:
        for camada in prefixo.camadas:
            marca = chave_de_estado(camada.chave, camada.caminho_windows)
            registro_dela = memoria.get(marca, {})
            if camada.ligada or registro_dela.get("feito") != "desligada":
                continue
            alvos[(camada.chave, camada.caminho_windows)] = registro_dela.get(
                "valor_antes", "00000000"
            )
            religadas.append(camada.nome_curto)
            memoria[marca] = (
                {"feito": _FEITO_PELA_EXCLUSAO, "quando": _agora()}
                if pela_exclusao
                else {"feito": "religada", "escolha": "manter", "quando": _agora()}
            )
    else:
        for camada in prefixo.camadas:
            if not camada.e_sobra:
                continue
            marca = chave_de_estado(camada.chave, camada.caminho_windows)
            registro_dela = memoria.get(marca, {})
            if not forcar and _e_escolha_dela(registro_dela):
                respeitadas.append(camada.nome_curto)
                continue
            alvos[(camada.chave, camada.caminho_windows)] = _DESLIGADA_DWORD
            desligadas.append(camada.nome_curto)
            memoria[marca] = {
                "feito": "desligada",
                "valor_antes": camada.valor,
                "quando": _agora(),
            }

    if not alvos:
        if respeitadas:
            estado[prefixo.appid] = memoria
            gravar_estado(estado, home)
        return Resultado(appid=prefixo.appid, respeitadas=tuple(respeitadas))

    for _chave, caminho in alvos:
        if _e_o_driver(caminho):
            return Resultado(
                appid=prefixo.appid,
                erro=f"recusei mexer no driver do Wine ({caminho})",
            )

    try:
        _reescrever(prefixo.registro, alvos)
    except OSError as exc:
        return Resultado(appid=prefixo.appid, erro=str(exc))

    estado[prefixo.appid] = memoria
    gravar_estado(estado, home)
    return Resultado(
        appid=prefixo.appid,
        desligadas=tuple(desligadas),
        religadas=tuple(religadas),
        respeitadas=tuple(respeitadas),
    )


def curar_todos(
    home: Path | None = None,
    *,
    religar: bool = False,
    forcar: bool = True,
    excluir: Collection[str] = (),
) -> list[Resultado]:
    """Passa em todos os prefixos desta máquina. É o que o botão chama."""
    fora = {str(a).strip() for a in excluir}
    da_steam: set[Path] = set()
    for pasta in pastas_compatdata(home):
        with contextlib.suppress(OSError):
            da_steam.add(pasta.resolve())

    def pulado(p: PrefixoDeJogo) -> bool:
        try:
            pai, raiz = p.raiz.parent.resolve(), p.raiz.resolve()
        except OSError:  # pragma: no cover - caminho impossível
            return False
        return p.appid in fora if pai in da_steam else str(raiz) in fora

    return [
        aplicar_no_prefixo(p, religar=religar, forcar=forcar, home=home)
        for p in censo(home)
        if p.camadas and not pulado(p)
    ]


def curar_um_prefixo(
    raiz: Path,
    *,
    appid: str | None = None,
    home: Path | None = None,
    forcar: bool = False,
) -> Resultado:
    """Um prefixo, sem enumerar nada — o motor do gancho de lançamento."""
    prefixo = prefixo_de_jogo(raiz, appid=appid)
    if not prefixo.sobras:
        return Resultado(appid=prefixo.appid)
    return aplicar_no_prefixo(prefixo, forcar=forcar, home=home)


def _linha_de_relatorio(prefixo: PrefixoDeJogo) -> list[str]:
    """As linhas de UM prefixo no relatório de texto."""
    linhas = [f"{prefixo.rotulo}:"]
    for camada in prefixo.camadas:
        if camada.e_o_driver:
            estado = "driver do Wine — fora da mira"
        elif camada.preservada_por is not None:
            estado = f"preservada ({camada.preservada_por})"
        elif not camada.ligada:
            estado = "desligada"
        elif not camada.presente:
            estado = "registrada, mas o arquivo não está no disco — inerte"
        else:
            estado = "LIGADA — candidata"
        linhas.append(f"    {camada.nome_curto}: {estado}")
    return linhas


def main(argv: list[str] | None = None) -> int:
    """CLI stdlib. `--relatorio` é read-only; os outros escrevem."""
    parser = argparse.ArgumentParser(
        description="Camadas Vulkan implícitas nos prefixos Wine dos jogos."
    )
    grupo = parser.add_mutually_exclusive_group(required=True)
    grupo.add_argument("--relatorio", action="store_true", help="censo read-only")
    grupo.add_argument("--curar", action="store_true", help="desliga as sobras")
    grupo.add_argument("--devolver", action="store_true", help="religa o que desligamos")
    grupo.add_argument(
        "--prefixo",
        metavar="CAMINHO",
        help="cura UM compatdata/<appid> do jogo que traz o vulkan-1.dll "
        "(usado pelo gancho de lançamento, com --jogo)",
    )
    parser.add_argument(
        "--appid", default=None, help="appid, quando o caminho não o revelar"
    )
    parser.add_argument(
        "--jogo",
        metavar="PASTA",
        default="",
        help="a pasta do jogo (STEAM_COMPAT_INSTALL_PATH); sem o vulkan-1.dll "
        "da Khronos nela, o --prefixo não mexe no registro",
    )
    args = parser.parse_args(argv)

    if args.prefixo:
        if not args.jogo or not traz_o_carregador_da_khronos(Path(args.jogo)):
            return 0
        resultado = curar_um_prefixo(
            Path(args.prefixo), appid=args.appid or None, forcar=True)
        if resultado.erro:
            print(f"erro: {resultado.erro}", file=sys.stderr)
            return 1
        if resultado.desligadas:
            print("desligadas: " + ", ".join(resultado.desligadas))
        return 0

    if not sabe_enumerar():
        print(
            "esta cópia não consegue listar os jogos (falta o módulo irmão "
            "steam_launch_options); só o modo --prefixo funciona aqui",
            file=sys.stderr,
        )
        return 2

    if args.relatorio:
        achados = censo()
        if not achados:
            print("nenhum prefixo com camada Vulkan implícita registrada")
            return 0
        for prefixo in achados:
            for linha in _linha_de_relatorio(prefixo):
                print(linha)
        return 0

    resultados = curar_todos(religar=bool(args.devolver))
    mexidos = [r for r in resultados if r.mexeu or r.erro]
    if not mexidos:
        print("nada a mudar")
        return 0
    for resultado in mexidos:
        if resultado.erro:
            print(f"{resultado.appid}: erro: {resultado.erro}", file=sys.stderr)
            continue
        acao = "religadas" if args.devolver else "desligadas"
        nomes = resultado.religadas if args.devolver else resultado.desligadas
        print(f"{resultado.appid}: {acao}: " + ", ".join(nomes))
    return 0


if __name__ == "__main__":  # pragma: no cover - entrada de script avulso
    raise SystemExit(main())
