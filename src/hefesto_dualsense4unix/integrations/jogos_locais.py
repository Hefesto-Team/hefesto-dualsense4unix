"""Os jogos que JÁ ESTÃO nesta máquina, para o campo "Nome do jogo:"."""
from __future__ import annotations

import configparser
import contextlib
import os
import re
import shlex
import unicodedata
from collections.abc import Iterable, Mapping, Sequence
from dataclasses import dataclass
from pathlib import Path

from hefesto_dualsense4unix.integrations.steam_launch_options import (
    _PAR_ACF,
    _desescapar_acf,
    pastas_steamapps,
)
from hefesto_dualsense4unix.profiles.steam_app import (
    parece_endereco,
    steam_appid_de_texto,
)

PASTAS_DE_ATALHOS: tuple[str, ...] = (
    "~/.local/share/applications",
    "/usr/share/applications",
)


def pastas_de_atalhos() -> list[Path]:
    """Os diretórios de `.desktop` DESTA máquina, na ordem da spec XDG."""
    def real(caminho: Path) -> Path:
        try:
            return caminho.resolve()
        except OSError:  # pragma: no cover - link quebrado ou permissão
            return caminho

    candidatos: list[Path] = []
    data_home = os.environ.get("XDG_DATA_HOME", "").strip()
    candidatos.append(
        Path(data_home).expanduser() / "applications"
        if data_home
        else Path("~/.local/share/applications").expanduser()
    )
    data_dirs = os.environ.get("XDG_DATA_DIRS", "").strip()
    for bruto in (data_dirs or "/usr/local/share:/usr/share").split(":"):
        limpo = bruto.strip()
        if limpo:
            candidatos.append(Path(limpo).expanduser() / "applications")
    candidatos.extend(Path(p).expanduser() for p in PASTAS_DE_ATALHOS)

    alvos: list[Path] = []
    vistos: set[Path] = set()
    for candidato in candidatos:
        if not candidato.is_dir():
            continue
        chave = real(candidato)
        if chave in vistos:
            continue
        vistos.add(chave)
        alvos.append(candidato)
    return alvos


_EXEC_RUNGAMEID_RE = re.compile(r"steam://rungameid/(\d+)", re.IGNORECASE)

_FERRAMENTA_RE = re.compile(
    r"^(?:Proton (?:Experimental|Hotfix|\d)"
    r"|Steam Linux Runtime\b"
    r"|Steamworks Common Redistributables$)",
)


@dataclass(frozen=True)
class JogoLocal:
    """Um jogo achado no disco: o número, o nome e de onde veio o nome."""

    appid: str
    nome: str
    fonte: str
    lancador: str = ""
    chave: str = ""

    @property
    def rotulo(self) -> str:
        """Como ele aparece na lista da completação: nome e endereço juntos."""
        if self.lancador:
            return f"{self.nome} ({self.lancador})"
        return f"{self.nome} (appid {self.appid})"

    @property
    def valor(self) -> str:
        """O que o CAMPO grava quando ela escolhe esta linha."""
        return self.chave or self.appid

    @property
    def forma(self) -> str:
        """A chave de `simple_match.from_simple_choice` para esta linha.

        ``"steam_game"`` guarda ``steam_app_<id>``; ``"janela"`` guarda a
        `wm_class` crua — a sexta forma, nascida na ONDA5-10-01 para o jogo de
        fora da Steam. **São o MESMO campo do perfil** (`window_class`), que é
        o que o critério de pronto desta sprint exige: *"nunca um campo novo"*.
        """
        return "janela" if self.chave else "steam_game"


def e_ferramenta_da_steam(nome: str) -> bool:
    """O `.acf` é de infraestrutura (Proton, runtime, redistribuíveis)?"""
    return _FERRAMENTA_RE.match(nome.strip()) is not None


def chave_de_busca(texto: str) -> str:
    """Texto achatado para comparar: sem acento, sem caixa, sem espaço em volta."""
    decomposto = unicodedata.normalize("NFD", texto)
    sem_acento = "".join(c for c in decomposto if not unicodedata.combining(c))
    return sem_acento.casefold().strip()


def _campos_do_acf(texto: str) -> dict[str, str]:
    """Os pares `"chave" "valor"` de PRIMEIRO nível úteis aqui (appid, name)."""
    campos: dict[str, str] = {}
    for linha in texto.splitlines():
        par = _PAR_ACF.match(linha)
        if par is None:
            continue
        chave = par.group("chave").lower()
        if chave in {"appid", "name"} and chave not in campos:
            campos[chave] = _desescapar_acf(par.group("valor")).strip()
    return campos


def jogos_da_biblioteca_steam(home: Path | None = None) -> list[JogoLocal]:
    """Os jogos dos `appmanifest_*.acf`, de toda biblioteca configurada."""
    vistas: set[Path] = set()
    achados: dict[str, JogoLocal] = {}
    for pasta in pastas_steamapps(home):
        real = pasta
        with contextlib.suppress(OSError):
            real = pasta.resolve()
        if real in vistas:
            continue
        vistas.add(real)
        try:
            manifests = sorted(real.glob("appmanifest_*.acf"))
        except OSError:
            continue
        for manifesto in manifests:
            try:
                texto = manifesto.read_text(encoding="utf-8", errors="replace")
            except OSError:
                continue
            campos = _campos_do_acf(texto)
            appid = campos.get("appid", "")
            nome = campos.get("name", "")
            if not appid.isdigit() or not nome:
                continue
            if e_ferramenta_da_steam(nome):
                continue
            achados.setdefault(appid, JogoLocal(appid=appid, nome=nome, fonte="steam"))
    return list(achados.values())


def assinatura_da_biblioteca(home: Path | None = None) -> tuple[tuple[str, int], ...]:
    """Impressão BARATA da biblioteca: ``(pasta, mtime_ns)`` de cada `steamapps`."""
    linhas: list[tuple[str, int]] = []
    for pasta in pastas_steamapps(home):
        try:
            linhas.append((str(pasta), os.stat(pasta).st_mtime_ns))
        except OSError:
            linhas.append((str(pasta), -1))
    return tuple(linhas)


def _nome_do_desktop(texto: str) -> str:
    """O `Name=` do grupo `[Desktop Entry]`, sem as variantes de idioma."""
    for linha in texto.splitlines():
        crua = linha.strip()
        if crua.startswith("Name="):
            return crua[len("Name=") :].strip()
    return ""


_CATEGORIAS_DE_LANCADOR = frozenset({"PackageManager", "Emulator"})

_NAO_E_JOGO = frozenset({"TerminalEmulator"})


def _campo_do_desktop(texto: str, campo: str) -> str:
    """O valor de `campo=` no `.desktop`, sem as variantes de idioma."""
    alvo = f"{campo}="
    for linha in texto.splitlines():
        crua = linha.strip()
        if crua.startswith(alvo):
            return crua[len(alvo):].strip()
    return ""


def _categorias(texto: str) -> frozenset[str]:
    """As `Categories` deste `.desktop`, como CONJUNTO de itens inteiros."""
    cru = _campo_do_desktop(texto, "Categories")
    return frozenset(p.strip() for p in cru.split(";") if p.strip())


def e_lancador_de_jogos(texto: str) -> bool:
    """Este `.desktop` se declara um lançador de jogos?"""
    cats = _categorias(texto)
    if cats & _NAO_E_JOGO:
        return False
    if "Game" not in cats:
        return False
    if _campo_do_desktop(texto, "NoDisplay").lower() == "true":
        return False
    return bool(cats & _CATEGORIAS_DE_LANCADOR)


def lancadores_por_conteudo(
    pastas: Sequence[Path] | None = None,
) -> dict[str, str]:
    """`{stem do .desktop: Name=}` de todo lançador de jogos DESTA máquina."""
    achados: dict[str, str] = {}
    for pasta in (pastas if pastas is not None else pastas_de_atalhos()):
        try:
            arquivos = sorted(pasta.glob("*.desktop"))
        except OSError:  # pragma: no cover - pasta some entre o listar e o ler
            continue
        for arq in arquivos:
            if arq.stem in achados:
                continue
            try:
                texto = arq.read_text(encoding="utf-8", errors="replace")
            except OSError:  # pragma: no cover
                continue
            if e_lancador_de_jogos(texto):
                achados[arq.stem] = _nome_do_desktop(texto) or arq.stem
    return achados


def jogos_dos_atalhos_desktop(
    pastas: Sequence[Path] | None = None,
) -> list[JogoLocal]:
    """Os jogos dos `.desktop` que apontam para `steam://rungameid/<id>`."""
    alvos = list(pastas) if pastas is not None else pastas_de_atalhos()
    achados: dict[str, JogoLocal] = {}
    for pasta in alvos:
        try:
            arquivos = sorted(pasta.glob("*.desktop"))
        except OSError:
            continue
        for arquivo in arquivos:
            try:
                texto = arquivo.read_text(encoding="utf-8", errors="replace")
            except OSError:
                continue
            if "NoDisplay=true" in texto:
                continue
            achado = _EXEC_RUNGAMEID_RE.search(texto)
            appid = achado.group(1) if achado is not None else ""
            if not appid:
                for linha in texto.splitlines():
                    if linha.strip().startswith("X-SteamAppId="):
                        appid = linha.split("=", 1)[1].strip()
                        break
            if not appid.isdigit():
                continue
            nome = _nome_do_desktop(texto)
            if not nome:
                continue
            achados.setdefault(
                appid, JogoLocal(appid=appid, nome=nome, fonte="desktop")
            )
    return list(achados.values())


def catalogo_de_jogos(
    home: Path | None = None,
    pastas_de_atalhos: Sequence[Path] | None = None,
) -> list[JogoLocal]:
    """As duas fontes juntas, em ordem alfabética e sem appid repetido."""
    por_appid: dict[str, JogoLocal] = {}
    for jogo in jogos_da_biblioteca_steam(home):
        por_appid.setdefault(jogo.appid, jogo)
    for jogo in jogos_dos_atalhos_desktop(pastas_de_atalhos):
        por_appid.setdefault(jogo.appid, jogo)
    return sorted(por_appid.values(), key=lambda j: (chave_de_busca(j.nome), j.appid))


def jogos_dos_lancadores(lar: Path | None = None) -> list[JogoLocal]:
    """A SEGUNDA ORIGEM — os jogos dos cinco lançadores que não são a Steam."""
    from hefesto_dualsense4unix.integrations.censo_dos_lancadores import (
        jogos_com_chave_de_janela,
    )

    achados: dict[str, JogoLocal] = {}
    for lancador, jogo in jogos_com_chave_de_janela(lar):
        classe = jogo.classe_de_janela
        achados.setdefault(classe, JogoLocal(
            appid="", nome=jogo.nome, fonte=lancador.casefold(),
            lancador=lancador, chave=classe))
    return sorted(achados.values(), key=lambda j: (chave_de_busca(j.nome), j.chave))


_CATEGORIA_QUE_NAO_E_JOGO = "packagemanager"

_CLIENTES_DE_LOJA = frozenset({"rare"})


LANCADOR_DIRETO = "Instalado aqui"


_CATEGORIAS_DE_FERRAMENTA = frozenset(
    {"utility", "network", "filetransfer", "system", "settings", "development"}
)

_PROGRAMAS_QUE_ABREM_OUTRO = frozenset(
    {"xdg-open", "gio", "gtk-launch", "kde-open", "kde-open5"}
)

_LOJAS_SEM_CLASSE = frozenset(
    {
        "steam", "steamwebhelper", "com.valvesoftware.steam",
        "heroic", "com.heroicgameslauncher.hgl",
        "lutris", "net.lutris.lutris",
        "bottles", "com.usebottles.bottles",
        "itch", "io.itch.itch", "minigalaxy", "rare",
    }
)


def _e_atalho_para_outro_programa(comando: str) -> bool:
    """O `Exec=` só pede a OUTRO programa que abra o jogo (`xdg-open heroic://…`)?"""
    try:
        partes = shlex.split(comando)
    except ValueError:
        return False
    if not partes:
        return False
    if partes[0].rsplit("/", 1)[-1] in _PROGRAMAS_QUE_ABREM_OUTRO:
        return True
    return any("://" in parte for parte in partes[1:])


def _chave_do_atalho_sem_classe(
    arquivo: Path, texto: str, categorias: frozenset[str], comando: str
) -> str:
    """A chave de janela de um jogo cujo `.desktop` NÃO traz `StartupWMClass`.

    É o **id do atalho** (o nome do arquivo sem `.desktop`): o que o compositor
    usa para casar a janela com o atalho quando o atalho não declara a classe, e
    a classe de janela é comparada sem distinguir maiúscula (`forja` casa a
    janela `FORJA`). Nunca é um nome inventado: é o que o atalho já se chama.

    Devolve `""` quando o atalho não é um jogo com janela própria: ferramenta
    (`Utility`…), lançador (`Emulator`/`PackageManager`, que têm a aba deles),
    cliente de loja ou um atalho que só manda OUTRO programa abrir o jogo.
    """
    if categorias & _CATEGORIAS_DE_FERRAMENTA:
        return ""
    if e_lancador_de_jogos(texto):
        return ""
    if _e_atalho_para_outro_programa(comando):
        return ""
    chave = arquivo.stem.strip()
    if chave.casefold() in _LOJAS_SEM_CLASSE or chave.casefold() in _CLIENTES_DE_LOJA:
        return ""
    return chave


def jogos_diretos_dos_atalhos(
    pastas: Sequence[Path] | None = None,
) -> list[JogoLocal]:
    """A TERCEIRA ORIGEM — o jogo que não é de lançador nenhum, pelo `.desktop`.

    O atalho que declara `StartupWMClass` entra com ela. O que não declara (o
    jogo nativo comum) entra com o id do atalho como chave
    (:func:`_chave_do_atalho_sem_classe`).
    """
    alvos = list(pastas) if pastas is not None else pastas_de_atalhos()
    achados: dict[str, JogoLocal] = {}
    for pasta in alvos:
        try:
            arquivos = sorted(pasta.glob("*.desktop"))
        except OSError:
            continue
        for arquivo in arquivos:
            try:
                texto = arquivo.read_text(encoding="utf-8", errors="replace")
            except OSError:
                continue
            cfg = configparser.ConfigParser(strict=False, interpolation=None)
            try:
                cfg.read_string(texto)
            except configparser.Error:
                continue
            if not cfg.has_section("Desktop Entry"):
                continue
            entrada = cfg["Desktop Entry"]
            if entrada.get("NoDisplay", "").strip().casefold() == "true":
                continue
            classe = entrada.get("StartupWMClass", "").strip()
            categorias = {c.strip().casefold()
                          for c in entrada.get("Categories", "").split(";")}
            if "game" not in categorias:
                continue
            if not classe:
                classe = _chave_do_atalho_sem_classe(
                    arquivo, texto, frozenset(categorias),
                    entrada.get("Exec", ""))
            if not classe:
                continue
            if _CATEGORIA_QUE_NAO_E_JOGO in categorias:
                continue
            if classe.casefold() in _CLIENTES_DE_LOJA:
                continue
            if steam_appid_de_texto(classe) is not None:
                continue
            nome = _nome_do_desktop(texto)
            if not nome:
                continue
            achados.setdefault(classe.casefold(), JogoLocal(
                appid="", nome=nome, fonte="desktop",
                lancador=LANCADOR_DIRETO, chave=classe))
    return sorted(achados.values(), key=lambda j: (chave_de_busca(j.nome), j.chave))


def jogos_com_janela(
    lar: Path | None = None,
    pastas: Sequence[Path] | None = None,
) -> list[JogoLocal]:
    """**AS TRÊS ORIGENS DE FORA DA STEAM, numa lista só** — o motor da sprint."""
    jogos = list(jogos_dos_lancadores(lar))
    vistos = {j.chave.casefold() for j in jogos}
    jogos += [j for j in jogos_diretos_dos_atalhos(pastas)
              if j.chave.casefold() not in vistos]
    return sorted(jogos, key=lambda j: (chave_de_busca(j.nome), j.chave))


def jogo_da_janela(
    classe: str | None,
    jogos: Iterable[JogoLocal],
) -> JogoLocal | None:
    """**A FUNÇÃO QUE O «DETECTAR» PRECISAVA**: de uma `wm_class`, QUE JOGO É."""
    alvo = (classe or "").strip().casefold()
    if not alvo or alvo == "unknown":
        return None
    for jogo in jogos:
        if jogo.chave and jogo.chave.casefold() == alvo:
            return jogo
    return None


_NOMES_DAS_JANELAS: tuple[object, list[JogoLocal], dict[str, str]] | None = None


def assinatura_das_janelas(
    lar: Path | None = None,
    pastas: Sequence[Path] | None = None,
) -> tuple[object, ...]:
    """Impressão BARATA das três origens de fora da Steam — o freio do caderno."""
    from hefesto_dualsense4unix.integrations.censo_dos_lancadores import (
        assinatura_das_bibliotecas,
    )

    linhas: list[object] = [assinatura_das_bibliotecas(lar)]
    alvos = list(pastas) if pastas is not None else pastas_de_atalhos()
    for pasta in alvos:
        try:
            linhas.append((str(pasta), os.stat(pasta).st_mtime_ns))
        except OSError:
            linhas.append((str(pasta), -1))
    return tuple(linhas)


def _caderno_das_janelas(
    lar: Path | None,
    pastas: Sequence[Path] | None,
) -> tuple[list[JogoLocal], dict[str, str]]:
    """A leitura das três origens, memoizada — a LISTA e o índice, de uma vez."""
    global _NOMES_DAS_JANELAS
    try:
        assinatura = assinatura_das_janelas(lar, pastas)
        if _NOMES_DAS_JANELAS is not None and _NOMES_DAS_JANELAS[0] == assinatura:
            return _NOMES_DAS_JANELAS[1], _NOMES_DAS_JANELAS[2]
        jogos = list(jogos_com_janela(lar, pastas))
    except Exception:  # pragma: no cover - disco hostil; ver o contrato acima
        return [], {}
    nomes = {j.chave.casefold(): j.nome for j in jogos if j.chave}
    for jogo in jogos:
        numero = steam_appid_de_texto(jogo.chave)
        if numero is not None:
            nomes.setdefault(str(numero), jogo.nome)
    _NOMES_DAS_JANELAS = (assinatura, jogos, nomes)
    return jogos, nomes


def nomes_das_janelas(
    lar: Path | None = None,
    pastas: Sequence[Path] | None = None,
) -> dict[str, str]:
    """``{wm_class: nome}`` das três origens — **o que o RÓTULO consulta**."""
    return _caderno_das_janelas(lar, pastas)[1]


def jogos_de_janela(
    lar: Path | None = None,
    pastas: Sequence[Path] | None = None,
) -> list[JogoLocal]:
    """A MESMA leitura na forma de LISTA — o que o `<datalist>` oferece."""
    return _caderno_das_janelas(lar, pastas)[0]


def ofertas_do_campo_do_jogo(
    da_steam: Iterable[JogoLocal],
    dos_lancadores: Iterable[JogoLocal],
) -> list[JogoLocal]:
    """AS DUAS ORIGENS JUNTAS — o que o campo «Nome do Jogo» oferece."""
    jogos = list(da_steam)
    vistos = {chave_de_busca(j.nome) for j in jogos}
    jogos += [j for j in dos_lancadores
              if chave_de_busca(j.nome) not in vistos]
    return sorted(jogos, key=lambda j: (chave_de_busca(j.nome), j.valor))


def nomes_por_appid(jogos: Iterable[JogoLocal]) -> dict[str, str]:
    """``{"851100": "Touhou Luna Nights"}`` — o que a frase da tela consulta."""
    return {jogo.appid: jogo.nome for jogo in jogos}


#: testável sem GTK — mesmo molde de `texto_do_processo_que_nao_casa`.
MSG_NAO_RECONHECI = "Não reconheci este endereço."

MSG_FORA_DA_MAQUINA = "Não instalado aqui (o número vale)."


def frase_do_campo_do_jogo(
    texto: str | None,
    nomes: Mapping[str, str],
    chaves: Mapping[str, str] | None = None,
) -> tuple[str, bool] | None:
    """O que fica ao lado do campo: ``(frase, é_alerta)``, ou ``None`` p/ esconder."""
    if not isinstance(texto, str) or not texto.strip():
        return None
    do_lancador = (chaves or {}).get(texto.strip().casefold())
    appid = steam_appid_de_texto(texto)
    if appid is not None:
        nome = nomes.get(str(appid))
        if nome:
            return (nome, False)
        if do_lancador:
            return (do_lancador, False)
        return (MSG_FORA_DA_MAQUINA, False)
    if do_lancador:
        return (do_lancador, False)
    if parece_endereco(texto):
        return (MSG_NAO_RECONHECI, True)
    return None


__all__ = [
    "LANCADOR_DIRETO",
    "MSG_FORA_DA_MAQUINA",
    "MSG_NAO_RECONHECI",
    "PASTAS_DE_ATALHOS",
    "JogoLocal",
    "assinatura_da_biblioteca",
    "assinatura_das_janelas",
    "catalogo_de_jogos",
    "chave_de_busca",
    "e_ferramenta_da_steam",
    "frase_do_campo_do_jogo",
    "jogo_da_janela",
    "jogos_com_janela",
    "jogos_da_biblioteca_steam",
    "jogos_de_janela",
    "jogos_diretos_dos_atalhos",
    "jogos_dos_atalhos_desktop",
    "jogos_dos_lancadores",
    "nomes_das_janelas",
    "nomes_por_appid",
    "ofertas_do_campo_do_jogo",
    "pastas_de_atalhos",
]
