"""A ficha e o recibo do Proton: a versão nova só entra no lugar da fixada se passar.

A ficha é estática (o script `proton` e as strings dos binários do Wine, sem
rodar Wine) e pergunta pelo CONTRATO, não pela versão: o que sumiu reprova, o
que mudou de ramo contra a fixada vira linha do recibo. A rodada, dinâmica, é
`scripts/ensaios/a_rodada_do_proton_candidato.py`, só na VM ou no CI. O recibo
é `docs/data/proton-qualificacao.csv`; o pino sem a linha «passou» reprova, e o
`hefesto doctor` lê o mesmo recibo (`linhas_do_doctor_desta_maquina`).
O contrato das strings é o medido no GE-Proton11-7 (a `PROTON_DISABLE_HIDRAW`
mora no `winebus.sys`, em UTF-16).
"""
from __future__ import annotations

import argparse
import ast
import csv
import io
import re
import sys
from collections.abc import Callable, Iterable, Sequence
from dataclasses import dataclass, field
from pathlib import Path

from hefesto_dualsense4unix.utils.repo_files import encontrar_arquivo_do_repo

ENVS_ALEM_DA_ALLOWLIST = ("PROTON_USE_XALIA", "PROTON_SONY_AUTO_XINPUT")

_PASTAS_DO_WINE = ("files/lib/wine", "files/lib64/wine")

CONTRATO_DE_STRINGS: tuple[tuple[str, tuple[str, ...], str], ...] = (
    ("winebus", ("x86_64-unix/winebus.so", "x86_64-windows/winebus.sys"),
     "PROTON_DISABLE_HIDRAW"),
    ("winebus", ("x86_64-unix/winebus.so", "x86_64-windows/winebus.sys"),
     "SDL_GAMECONTROLLER_IGNORE_DEVICES"),
    ("winebus", ("x86_64-unix/winebus.so",), "hidraw handles native reports"),
    ("winepulse", ("x86_64-unix/winepulse.so",), "Speaker__sink"),
    ("winepulse", ("x86_64-unix/winepulse.so",), "Wireless_Controller"),
    ("winepulse", ("x86_64-unix/winepulse.so",), "PROTON_DUALSENSE_SPLIT_AUDIO"),
    ("mmdevapi", ("x86_64-windows/mmdevapi.dll",), "PROTON_ENABLE_MHWILDS_USB_AUDIO"),
    ("mmdevapi", ("x86_64-windows/mmdevapi.dll",),
     "PROTON_KEEP_SONY_AUDIO_ENDPOINT_VISIBLE"),
    ("setupapi", ("x86_64-windows/setupapi.dll",), "PROTON_ENABLE_MHWILDS_USB_AUDIO"),
    ("sechost", ("x86_64-windows/sechost.dll",), "PROTON_KEEP_SONY_AUDIO_ENDPOINT_VISIBLE"),
)

ACAO_ATRIBUI = "atribui"
ACAO_APAGA = "apaga"
ACAO_PADRAO = "padrão"

VEREDITO_PASSOU = "passou"
VEREDITO_REPROVOU = "reprovou"
RODADA_HERDADA = "herdada"

CAMINHO_DO_RECIBO = "docs/data/proton-qualificacao.csv"

TAG_OK = "[ OK ]"
TAG_INFO = "[INFO]"
TAG_WARN = "[WARN]"

CAMPOS_DO_RECIBO = ("versão", "sha256", "ficha", "rodada", "veredito", "prova", "data")

_VERSAO_GE_RE = re.compile(r"GE-Proton(\d+)-(\d+)", re.IGNORECASE)


def envs_pedidas() -> tuple[str, ...]:
    """A allowlist do lançamento mais as envs que o script do Proton decide."""
    from hefesto_dualsense4unix.daemon.launch_env import ENV_ALLOWLIST

    return (*ENV_ALLOWLIST, *ENVS_ALEM_DA_ALLOWLIST)


@dataclass(frozen=True)
class Toque:
    """Um lugar do script `proton` que mexe numa env pedida."""

    env: str
    acao: str
    ramo: tuple[str, ...]
    linha: int

    def chave(self) -> tuple[str, str, tuple[str, ...]]:
        return (self.env, self.acao, self.ramo)

    def legivel(self) -> str:
        ramo = " > ".join(self.ramo) if self.ramo else "sempre"
        return f"{self.env} {self.acao} em [{ramo}] (linha {self.linha})"


def _nome_da_env(no: ast.AST, envs: frozenset[str]) -> str | None:
    """`self.env["X"]` ou `os.environ["X"]`, com X pedida; senão `None`."""
    if not isinstance(no, ast.Subscript):
        return None
    alvo = no.value
    if not (isinstance(alvo, ast.Attribute) and alvo.attr in ("env", "environ")):
        return None
    chave = no.slice
    if isinstance(chave, ast.Constant) and isinstance(chave.value, str):
        return chave.value if chave.value in envs else None
    return None


class _Leitor(ast.NodeVisitor):
    def __init__(self, envs: frozenset[str]) -> None:
        self.envs = envs
        self.ramo: list[str] = []
        self.toques: list[Toque] = []

    def _anota(self, env: str | None, acao: str, linha: int) -> None:
        if env is not None:
            self.toques.append(Toque(env, acao, tuple(self.ramo), linha))

    def visit_FunctionDef(self, no: ast.FunctionDef) -> None:
        self.ramo.append(f"def {no.name}")
        self.generic_visit(no)
        self.ramo.pop()

    def visit_If(self, no: ast.If) -> None:
        teste = ast.unparse(no.test)
        self.ramo.append(teste)
        for filho in no.body:
            self.visit(filho)
        self.ramo.pop()
        if no.orelse:
            self.ramo.append(f"not ({teste})")
            for filho in no.orelse:
                self.visit(filho)
            self.ramo.pop()

    def visit_Assign(self, no: ast.Assign) -> None:
        for alvo in no.targets:
            self._anota(_nome_da_env(alvo, self.envs), ACAO_ATRIBUI, no.lineno)
        self.generic_visit(no)

    def visit_AugAssign(self, no: ast.AugAssign) -> None:
        self._anota(_nome_da_env(no.target, self.envs), ACAO_ATRIBUI, no.lineno)
        self.generic_visit(no)

    def visit_Delete(self, no: ast.Delete) -> None:
        for alvo in no.targets:
            self._anota(_nome_da_env(alvo, self.envs), ACAO_APAGA, no.lineno)
        self.generic_visit(no)

    def visit_Call(self, no: ast.Call) -> None:
        func = no.func
        if (
            isinstance(func, ast.Attribute)
            and func.attr in ("pop", "setdefault")
            and isinstance(func.value, ast.Attribute)
            and func.value.attr in ("env", "environ")
            and no.args
            and isinstance(no.args[0], ast.Constant)
            and no.args[0].value in self.envs
        ):
            acao = ACAO_APAGA if func.attr == "pop" else ACAO_PADRAO
            self._anota(str(no.args[0].value), acao, no.lineno)
        self.generic_visit(no)


def toques_do_script(texto: str, envs: Iterable[str]) -> list[Toque]:
    """Cada atribuição, apagamento e padrão das `envs` no script `proton`."""
    leitor = _Leitor(frozenset(envs))
    leitor.visit(ast.parse(texto))
    return leitor.toques


def _pasta_do_wine(raiz: Path) -> Path | None:
    for relativo in _PASTAS_DO_WINE:
        pasta = raiz / relativo
        if pasta.is_dir():
            return pasta
    return None


def strings_que_faltam(raiz: Path) -> list[str]:
    """As linhas do contrato das strings que a versão em `raiz` não cumpre."""
    pasta = _pasta_do_wine(raiz)
    if pasta is None:
        return [f"a pasta do Wine não existe ({' nem '.join(_PASTAS_DO_WINE)})"]
    cache: dict[str, bytes | None] = {}

    def conteudo(relativo: str) -> bytes | None:
        if relativo not in cache:
            try:
                cache[relativo] = (pasta / relativo).read_bytes()
            except OSError:
                cache[relativo] = None
        return cache[relativo]

    faltas: list[str] = []
    for componente, arquivos, texto in CONTRATO_DE_STRINGS:
        agulhas = (texto.encode("ascii"), texto.encode("utf-16-le"))
        achou = False
        for relativo in arquivos:
            dados = conteudo(relativo)
            if dados is not None and any(a in dados for a in agulhas):
                achou = True
                break
        if not achou:
            faltas.append(f"{componente}: sem {texto} ({', '.join(arquivos)})")
    return faltas


@dataclass
class Ficha:
    """O resultado da ficha de uma versão, contra a fixada quando há."""

    versao: str
    faltas: list[str] = field(default_factory=list)
    mudancas: list[str] = field(default_factory=list)

    @property
    def passou(self) -> bool:
        return not self.faltas

    def resumo(self) -> str:
        if self.faltas:
            return "reprovou: " + "; ".join(self.faltas)
        if self.mudancas:
            return "passou, com mudança de ramo para a rodada: " + "; ".join(self.mudancas)
        return VEREDITO_PASSOU


def versao_da_pasta(raiz: Path) -> str:
    """O nome da versão: o arquivo `version` (segunda palavra), ou a pasta."""
    try:
        partes = (raiz / "version").read_text(encoding="utf-8", errors="replace").split()
    except OSError:
        partes = []
    return partes[1] if len(partes) >= 2 else raiz.name


def _toques_da_pasta(raiz: Path, envs: Sequence[str]) -> list[Toque] | str:
    try:
        texto = (raiz / "proton").read_text(encoding="utf-8", errors="replace")
    except OSError:
        return "o script proton não existe"
    try:
        return toques_do_script(texto, envs)
    except SyntaxError as erro:
        return f"o script proton não se lê ({erro.msg}, linha {erro.lineno})"


def ficha(
    candidata: Path,
    fixada: Path | None = None,
    envs: Sequence[str] | None = None,
) -> Ficha:
    """A ficha da `candidata`, com as mudanças de ramo contra a `fixada`."""
    pedidas = tuple(envs) if envs is not None else envs_pedidas()
    resultado = Ficha(versao=versao_da_pasta(candidata))
    resultado.faltas.extend(strings_que_faltam(candidata))
    toques = _toques_da_pasta(candidata, pedidas)
    if isinstance(toques, str):
        resultado.faltas.append(toques)
        return resultado
    if fixada is None:
        return resultado
    da_fixada = _toques_da_pasta(fixada, pedidas)
    if isinstance(da_fixada, str):
        resultado.faltas.append(f"a fixada não se lê: {da_fixada}")
        return resultado
    conhecidos = {t.chave() for t in da_fixada}
    for toque in toques:
        if toque.chave() not in conhecidos:
            resultado.mudancas.append(toque.legivel())
    return resultado


def caminho_do_recibo(raiz_do_repo: Path | None = None) -> Path:
    """O recibo: na `raiz_do_repo` dada, ou onde esta instalação o pôs."""
    if raiz_do_repo is not None:
        return raiz_do_repo / CAMINHO_DO_RECIBO
    achado = encontrar_arquivo_do_repo(CAMINHO_DO_RECIBO)
    return achado or Path(__file__).resolve().parents[3] / CAMINHO_DO_RECIBO


def ler_recibo(texto: str) -> list[dict[str, str]]:
    """As linhas do recibo, com os campos de `CAMPOS_DO_RECIBO`."""
    linhas = [
        linha for linha in texto.splitlines() if linha.strip() and not linha.startswith("#")
    ]
    leitor = csv.DictReader(io.StringIO("\n".join(linhas)))
    if tuple(leitor.fieldnames or ()) != CAMPOS_DO_RECIBO:
        raise ValueError(f"o recibo tem de ter as colunas {', '.join(CAMPOS_DO_RECIBO)}")
    return [{k: (v or "").strip() for k, v in linha.items()} for linha in leitor]


def ordem_da_versao(versao: str) -> tuple[int, int]:
    """A ordem de uma versão do GE-Proton (``GE-Proton11-7`` vale ``(11, 7)``).

    O que não tem esse formato vale ``(-1, -1)``: não se sabe se é mais novo, então nunca vence
    uma comparação por «mais recente».
    """
    achado = _VERSAO_GE_RE.search(versao)
    return (int(achado.group(1)), int(achado.group(2))) if achado else (-1, -1)


def a_mais_recente_que_passa(recibo: Sequence[dict[str, str]]) -> str | None:
    """Entre as versões que passaram, a mais recente: é ela que se fixa (22/10/2026)."""
    passaram = [
        linha["versão"] for linha in recibo
        if linha["veredito"] == VEREDITO_PASSOU and ordem_da_versao(linha["versão"]) > (-1, -1)
    ]
    return max(passaram, key=ordem_da_versao) if passaram else None


def o_pino_sem_recibo(pino: dict[str, str], recibo: Sequence[dict[str, str]]) -> list[str]:
    """A régua do pino: o que falta para o `proton-pin.conf` valer.

    O pino nomeia uma versão com a linha «passou» e o MESMO sha256; e é a
    mais recente entre as que passaram.
    """
    nome = pino.get("name", "")
    sha = pino.get("sha256", "").lower()
    da_versao = [linha for linha in recibo if linha["versão"] == nome]
    if not da_versao:
        return [f"o pino {nome} não tem linha no recibo"]
    passou = [
        linha for linha in da_versao
        if linha["veredito"] == VEREDITO_PASSOU
        and linha["ficha"].startswith(VEREDITO_PASSOU)
        and linha["rodada"] in (VEREDITO_PASSOU, RODADA_HERDADA)
    ]
    if not passou:
        return [f"o pino {nome} não tem a linha «passou» no recibo"]
    if not any(linha["sha256"].lower() == sha for linha in passou):
        return [f"o sha256 do pino {nome} não é o que passou no recibo"]
    recente = a_mais_recente_que_passa(recibo)
    if recente != nome:
        return [f"o pino {nome} não é a mais recente que passa ({recente})"]
    return []


def linha_do_recibo(f: Ficha, sha256: str, rodada: str, data: str) -> str:
    """A linha CSV de uma versão, depois da ficha e da rodada."""
    passou = f.passou and rodada == VEREDITO_PASSOU
    saida = io.StringIO()
    csv.writer(saida, lineterminator="").writerow([
        f.versao,
        sha256,
        f.resumo(),
        rodada,
        VEREDITO_PASSOU if passou else VEREDITO_REPROVOU,
        "" if passou else ("; ".join(f.faltas) or rodada),
        data,
    ])
    return saida.getvalue()


def recibo_das_instaladas(
    compat_dir: Path, recibo: Sequence[dict[str, str]]
) -> list[tuple[str, str]]:
    """Para cada Proton em `compat_dir`: ``(tag, texto)``, o veredito do recibo e a ficha de hoje.

    A tag avisa quando o recibo reprovou, ou quando passou e a ficha de hoje não
    confere mais. Sem recibo é só informação: um Proton que o Hefesto nunca
    mediu não é defeito de quem o instalou.
    """
    vereditos = {linha["versão"]: linha for linha in recibo}
    saida: list[tuple[str, str]] = []
    if not compat_dir.is_dir():
        return saida
    for pasta in sorted(p for p in compat_dir.iterdir() if (p / "proton").is_file()):
        f = ficha(pasta)
        linha = vereditos.get(pasta.name)
        if linha is None:
            tag, no_recibo = TAG_INFO, "sem recibo"
        else:
            no_recibo = linha["veredito"] + (f" ({linha['prova']})" if linha["prova"] else "")
            passou = linha["veredito"] == VEREDITO_PASSOU and f.passou
            tag = TAG_OK if passou else TAG_WARN
        saida.append((tag, f"{pasta.name}: recibo {no_recibo}; ficha de hoje {f.resumo()}"))
    return saida


def _lista_de_jogos(nomes: Sequence[str]) -> str:
    """Até cinco nomes, e quantos mais."""
    nomes = sorted(nomes, key=str.lower)
    visiveis = ", ".join(nomes[:5])
    return visiveis + (f" e mais {len(nomes) - 5}" if len(nomes) > 5 else "")


def linhas_do_doctor(
    *,
    recibo: Sequence[dict[str, str]] | None,
    pino: dict[str, str] | None,
    compat_dir: Path,
    mapa_dos_jogos: dict[str, str],
    nome_do_jogo: Callable[[str], str],
    sem_steam: str | None = None,
    vale: str | None = None,
) -> list[tuple[str, str]]:
    """As linhas do `hefesto doctor` sobre o Proton fixado: ``(tag, texto)``.


    Pura (quem lê arquivos é `linhas_do_doctor_desta_maquina`). Diz se o Proton
    fixado tem o recibo «passou» e está no disco, o que o recibo diz de cada
    Proton instalado, e em que Proton roda cada jogo que a Steam mapeou, com o
    aviso do jogo cujo Proton de terceiros sumiu do disco. Com ``sem_steam`` (o
    motivo de não haver Steam nativa), confere só o pino contra o recibo: sem
    Steam não há disco nem jogo a conferir, e o aviso seria falso. ``vale`` é o pino mais novo.
    """
    from hefesto_dualsense4unix.integrations.proton_pin import (
        nomes_internos,
        pinned_proton_installed,
    )

    linhas: list[tuple[str, str]] = []
    if pino is None:
        linhas.append(
            (
                TAG_INFO,
                "sem assets/proton-pin.conf nesta instalação: não há Proton fixado a conferir",
            )
        )
    else:
        nome = pino.get("name", "")
        if sem_steam is None and vale and vale != nome:
            linhas.append((TAG_OK, f"o Proton fixado é o {vale}: mais recente que o {nome} do "
                                   "recibo e passa na ficha de hoje"))
            nome = vale
        if sem_steam is not None:
            linhas.append((TAG_INFO, f"{sem_steam}: o {nome} não tem onde ser conferido no disco"))
        elif not pinned_proton_installed(nome, compat_dir):
            linhas.append((TAG_WARN, f"o Proton fixado ({nome}) não está em {compat_dir}"))
        if nome != pino.get("name", ""):
            pass
        elif recibo is None:
            linhas.append(
                (
                    TAG_INFO,
                    f"o recibo dos Protons não veio nesta instalação; "
                    f"{nome} fica sem a conferência dele",
                )
            )
        else:
            problemas = o_pino_sem_recibo(pino, recibo)
            linhas.extend((TAG_WARN, problema) for problema in problemas)
            if not problemas:
                linhas.append(
                    (TAG_OK, f"o Proton fixado ({nome}) tem o recibo «passou» com o mesmo sha256")
                )
    if sem_steam is not None:
        if pino is None:
            linhas.append((TAG_INFO, sem_steam))
        return linhas
    if recibo is not None:
        linhas.extend(recibo_das_instaladas(compat_dir, recibo))

    presentes = {
        nome.lower()
        for pasta in (compat_dir.iterdir() if compat_dir.is_dir() else ())
        if pasta.is_dir()
        for nome in (pasta.name, *nomes_internos(pasta))
    }
    por_ferramenta: dict[str, list[str]] = {}
    for appid, ferramenta in mapa_dos_jogos.items():
        if appid != "0" and ferramenta:
            por_ferramenta.setdefault(ferramenta, []).append(nome_do_jogo(appid))
    for ferramenta, nomes in sorted(por_ferramenta.items()):
        de_terceiro = ferramenta.lower().startswith("ge-proton")
        if de_terceiro and ferramenta.lower() not in presentes:
            linhas.append(
                (
                    TAG_WARN,
                    f"{_lista_de_jogos(nomes)} usa(m) o {ferramenta}, que sumiu de {compat_dir}",
                )
            )
        else:
            linhas.append((TAG_INFO, f"{ferramenta}: {_lista_de_jogos(nomes)}"))
    return linhas


def linhas_do_doctor_desta_maquina(home: Path | None = None) -> list[tuple[str, str]]:
    """`linhas_do_doctor` com o que esta máquina tem: recibo, pino, Steam e mapa dos jogos."""
    from hefesto_dualsense4unix.integrations import proton_pin as pp
    from hefesto_dualsense4unix.integrations.steam_launch_options import nome_do_appid

    caminho = caminho_do_recibo()
    recibo: list[dict[str, str]] | None = None
    if caminho.is_file():
        try:
            recibo = ler_recibo(caminho.read_text(encoding="utf-8"))
        except (OSError, ValueError) as erro:
            return [(TAG_WARN, f"o recibo dos Protons ({caminho}) não se lê: {erro}")]
    conf = encontrar_arquivo_do_repo("assets/proton-pin.conf") or pp.default_pin_conf_path()
    pino: dict[str, str] | None = None
    if conf is not None:
        try:
            pino = pp.parse_pin_conf(conf.read_text(encoding="utf-8")) or None
        except OSError:
            pino = None
    try:
        texto_do_vdf = pp.default_config_vdf(home).read_text(encoding="utf-8", errors="replace")
    except OSError:
        texto_do_vdf = ""
    mapa = {a: f for a, f in pp.extract_compat_tool_mapping(texto_do_vdf).items() if f}
    return linhas_do_doctor(
        recibo=recibo,
        pino=pino,
        compat_dir=pp.default_compat_dir(home),
        mapa_dos_jogos=mapa,
        nome_do_jogo=lambda appid: nome_do_appid(appid, home) or f"appid {appid}",
        sem_steam=pp.steam_root_ou_recusa(home).motivo,
        vale=pp.pino_que_vale(pino, pp.default_compat_dir(home)) if pino else None,
    )


def main(argv: Sequence[str] | None = None) -> int:
    parser = argparse.ArgumentParser(
        prog="qualificar_proton",
        description="A ficha e o recibo de uma versão do Proton.",
    )
    sub = parser.add_subparsers(dest="cmd", required=True)
    p_ficha = sub.add_parser("ficha", help="a ficha estática de uma pasta de Proton")
    p_ficha.add_argument("pasta", type=Path)
    p_ficha.add_argument("--fixada", type=Path, default=None)
    p_rec = sub.add_parser("recibo", help="o recibo de cada Proton instalado")
    p_rec.add_argument("--compat-dir", type=Path, default=None)
    sub.add_parser("pino", help="a régua do pino contra o recibo")
    args = parser.parse_args(argv)

    if args.cmd == "ficha":
        f = ficha(args.pasta, args.fixada)
        print(f"{f.versao}: {f.resumo()}")
        return 0 if f.passou else 1
    recibo = ler_recibo(caminho_do_recibo().read_text(encoding="utf-8"))
    if args.cmd == "recibo":
        from hefesto_dualsense4unix.integrations.proton_pin import default_compat_dir

        for _tag, linha in recibo_das_instaladas(args.compat_dir or default_compat_dir(), recibo):
            print(linha)
        return 0
    from hefesto_dualsense4unix.integrations.proton_pin import (
        default_pin_conf_path,
        parse_pin_conf,
    )

    conf = default_pin_conf_path()
    if conf is None:
        print("o proton-pin.conf não existe", file=sys.stderr)
        return 1
    problemas = o_pino_sem_recibo(parse_pin_conf(conf.read_text(encoding="utf-8")), recibo)
    for problema in problemas:
        print(problema)
    return 1 if problemas else 0


if __name__ == "__main__":
    raise SystemExit(main())
