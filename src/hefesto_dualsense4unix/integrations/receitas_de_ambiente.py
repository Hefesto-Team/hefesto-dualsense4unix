"""As receitas de ambiente por sinal: o jogo que só abre com uma variável a recebe pelo wrapper.

A tabela `docs/data/receitas-de-ambiente.csv` diz, por sinal no disco do jogo, qual variável vale
e que peça ela exige. Três regras que ela não quebra: sem appid embarcado (o jogo se reconhece
pelo que traz na pasta); só com a peça no lugar (sem ela o override quebraria o jogo, e o
prontuário diz «falta a peça»); só o que o wrapper aceita (letra morta calada não entra). O sinal
pode ser um caminho com curinga (`*_Data/Plugins/x86_64/X.dll`). A peça é um arquivo ao lado do
executável, o próprio sinal (`@sinal`, o caso de desligar uma DLL do jogo) ou a peça do Hefesto
(`@hefesto`, a `xgameruntime.dll` que o install põe na pasta da peça e que só conta se o sha256
bate com o `assets/gdk-runtime/pino.txt`). 100% stdlib, como o prontuário.
"""
from __future__ import annotations

import csv
import hashlib
import os
import re
from collections.abc import Iterable
from dataclasses import dataclass
from pathlib import Path

try:
    from .api_de_entrada import escolher_executavel
except ImportError:  # pragma: no cover - executado como script avulso
    from api_de_entrada import escolher_executavel  # type: ignore[no-redef]

_RAIZ = Path(__file__).resolve().parents[3]
TABELA = _RAIZ / "docs" / "data" / "receitas-de-ambiente.csv"
PINO_DA_PECA = _RAIZ / "assets" / "gdk-runtime" / "pino.txt"

#: As variáveis que o wrapper deixa passar com forma conferida. Espelho de `receita_do_jogo`.
VARIAVEIS_DO_WRAPPER = frozenset({"WINEDLLOVERRIDES", "WINEDLLPATH"})

_NOME_DE_DLL = re.compile(r"^[A-Za-z0-9_.-]+$")

#: Os modos que o wrapper deixa passar: nativa, nativa-depois-da-embutida, só a embutida e
#: desligada.
MODOS_DO_OVERRIDE = ("n", "n,b", "b", "d")

#: A peça que é o próprio arquivo do sinal (a DLL que se desliga já está no disco).
PECA_E_O_SINAL = "@sinal"

#: A peça GDK do Hefesto, na pasta que o install escreve; conta só com o sha256 do pino.
PECA_DO_HEFESTO = "@hefesto"

#: O único `WINEDLLPATH` que a tabela escreve: o wrapper o troca pela pasta da peça.
PASTA_DA_PECA = "@hefesto-wine"

#: O nome que o prontuário mostra quando a peça do Hefesto falta.
NOME_DA_PECA_DO_HEFESTO = "a peça GDK do Hefesto (xgameruntime.dll)"


def pasta_da_peca(home: Path | None = None) -> Path:
    """A pasta que o `WINEDLLPATH=@hefesto-wine` nomeia (a mesma do install e do wrapper)."""
    base = home if home is not None else Path.home()
    return base / ".local" / "share" / "hefesto-dualsense4unix" / "wine"


#: Onde a peça GDK procura o ajudante de login, em relação à casa: o login do Xbox Live é dele, a
#: peça não fabrica token. O dono do caminho é o fonte C (`compat_paths` em
#: `assets/gdk-runtime/xgameruntime.c`); uma régua lê o C e reprova se o Python divergir.
PASTA_DO_AJUDANTE = (".local", "share", "dungeons2-compat")
NOME_DO_AJUDANTE = "xauth.py"


def _casa_que_a_peca_ve() -> Path:
    """A casa que a peça enxerga: ``HOME``, ``WINE_HOST_HOME`` e, sem as duas, ``/home/<usuário>``.

    A mesma escada de `compat_paths` no fonte C, e só caminho absoluto vale em cada degrau.
    """
    for nome in ("HOME", "WINE_HOST_HOME"):
        valor = os.environ.get(nome, "")
        if valor.startswith("/"):
            return Path(valor)
    usuario = os.environ.get("USER") or os.environ.get("LOGNAME") or "steamuser"
    return Path("/home") / usuario


def caminho_do_ajudante_de_login(home: Path | None = None) -> Path:
    """Onde a peça GDK procura o ajudante de login (``…/dungeons2-compat/xauth.py``)."""
    base = home if home is not None else _casa_que_a_peca_ve()
    return base.joinpath(*PASTA_DO_AJUDANTE, NOME_DO_AJUDANTE)


def _sha256_do_pino(pino: Path | None = None) -> str | None:
    try:
        texto = (pino if pino is not None else PINO_DA_PECA).read_text(encoding="utf-8")
    except OSError:
        texto = ""  # sem pino, nenhuma peça bate: o jogo GDK abre como sempre abriu
    for linha in texto.splitlines():
        chave, igual, valor = linha.partition("=")
        if igual and chave.strip() == "sha256" and re.fullmatch(r"[0-9a-f]{64}", valor.strip()):
            return valor.strip()
    return None


def peca_do_hefesto_instalada(home: Path | None = None, pino: Path | None = None) -> bool:
    """A `xgameruntime.dll` da pasta da peça existe e o sha256 dela é o do pino."""
    esperado = _sha256_do_pino(pino)
    if esperado is None:
        return False
    dll = pasta_da_peca(home) / "x86_64-windows" / "xgameruntime.dll"
    try:
        return hashlib.sha256(dll.read_bytes()).hexdigest() == esperado
    except OSError:
        return False


def valor_valido(variavel: str, valor: str) -> bool:
    """A forma que o wrapper aceita para cada variável da tabela."""
    if variavel == "WINEDLLOVERRIDES":
        return override_valido(valor)
    if variavel == "WINEDLLPATH":
        return valor == PASTA_DA_PECA
    return False


def override_valido(valor: str) -> bool:
    """A forma que o wrapper aceita: ``nome[,nome]=n``, ``=n,b``, ``=b`` ou ``=d``, por ``;``.

    O espelho em Python de ``override_de_dll_valido`` em ``assets/hefesto-launch.sh``; uma régua
    confere as duas pontas com o mesmo vetor.
    """
    if not valor:
        return False
    entradas = [e for e in valor.split(";") if e]
    if not entradas:
        return False
    for entrada in entradas:
        nomes, igual, modo = entrada.partition("=")
        if not igual or modo not in MODOS_DO_OVERRIDE or not nomes:
            return False
        for nome in nomes.split(","):
            if not _NOME_DE_DLL.match(nome):
                return False
    return True


@dataclass(frozen=True)
class Receita:
    """Uma linha da tabela."""

    id: str
    sinais: tuple[str, ...]
    variavel: str
    valor: str
    peca: str


@dataclass(frozen=True)
class Leitura:
    """O que o disco de UM jogo diz sobre uma receita que o sinal ligou."""

    receita: Receita
    sinal: str
    #: ``True``/``False``; ``None`` quando nenhum executável se lê (não dá para saber).
    peca_presente: bool | None


def _sinal_valido(sinal: str) -> bool:
    """Um caminho relativo à pasta do jogo: sem subir, sem raiz, curinga só ``*`` num nome.

    O ``**`` fica fora: ele desceria a pasta inteira do jogo a cada censo.
    """
    if sinal.startswith(("/", ".")) or any(c in sinal for c in ("\\", "?", "[", "**")):
        return False
    return all(parte not in ("", ".", "..") for parte in sinal.split("/"))


def arquivos_do_sinal(raiz: Path, sinal: str) -> tuple[Path, ...]:
    """Os arquivos da pasta que o sinal nomeia, em ordem; pasta que não se lê não tem nenhum."""
    try:
        if "*" not in sinal:
            alvo = raiz / sinal
            return (alvo,) if alvo.is_file() else ()
        return tuple(p for p in sorted(raiz.glob(sinal)) if p.is_file())
    except OSError:
        return ()


def achar_sinal(raiz: Path, sinal: str) -> Path | None:
    """O arquivo da pasta do jogo que o sinal nomeia, ou ``None``; o caminho aceita ``*``.

    O leitor único do curinga da casa (a receita usa este): nunca sai de ``raiz`` (o sinal sem
    ``..`` nem barra inicial), nunca levanta.
    """
    if not _sinal_valido(sinal):
        return None
    return next(iter(arquivos_do_sinal(raiz, sinal)), None)


def _linha_valida(linha: dict[str, str]) -> Receita | None:
    sinais = tuple(s.strip() for s in (linha.get("sinais") or "").split("|") if s.strip())
    variavel = (linha.get("variavel") or "").strip()
    valor = (linha.get("valor") or "").strip()
    peca = (linha.get("peca") or "").strip()
    ident = (linha.get("id") or "").strip()
    if not (ident and sinais and peca):
        return None
    if not all(_sinal_valido(s) for s in sinais) or "/" in peca:
        return None
    if variavel not in VARIAVEIS_DO_WRAPPER or not valor_valido(variavel, valor):
        return None
    if variavel == "WINEDLLPATH" and peca != PECA_DO_HEFESTO:
        return None
    return Receita(ident, sinais, variavel, valor, peca)


def carregar_tabela(caminho: Path | None = None) -> tuple[Receita, ...]:
    """As receitas da tabela; tabela ausente ou linha fora da regra não derruba nada."""
    alvo = caminho if caminho is not None else TABELA
    try:
        texto = alvo.read_text(encoding="utf-8")
    except OSError:
        return ()
    corpo = (ln for ln in texto.splitlines() if ln.strip() and not ln.lstrip().startswith("#"))
    achadas: list[Receita] = []
    vistos: set[str] = set()
    for linha in csv.DictReader(corpo):
        receita = _linha_valida({k: (v or "") for k, v in linha.items() if k})
        if receita is None or receita.id in vistos:
            continue
        vistos.add(receita.id)
        achadas.append(receita)
    return tuple(achadas)


def _nomes_ao_lado_do_executavel(raiz: Path) -> frozenset[str]:
    """Os arquivos (minúsculos) da pasta do executável; vazio quando nenhum se lê.

    Vazio é sem ambiguidade: com executável lido, a pasta tem ao menos ele.
    """
    exe = escolher_executavel(raiz)
    if exe is None:
        return frozenset()
    try:
        return frozenset(p.name.lower() for p in exe.parent.iterdir() if p.is_file())
    except OSError:
        return frozenset()


def ler_jogo(
    raiz: Path | None, tabela: Iterable[Receita] | None = None, home: Path | None = None
) -> tuple[Leitura, ...]:
    """As receitas que o disco do jogo liga, cada uma com o veredito da peça."""
    if raiz is None:
        return ()
    receitas = carregar_tabela() if tabela is None else tuple(tabela)
    achadas: list[Leitura] = []
    nomes: frozenset[str] | None = None
    instalada: bool | None = None
    for receita in receitas:
        achado = next(
            ((s, p) for s in receita.sinais if (p := achar_sinal(raiz, s)) is not None), None
        )
        if achado is None:
            continue
        sinal, arquivo = achado
        if receita.peca == PECA_E_O_SINAL:
            achadas.append(Leitura(receita, sinal, arquivo.is_file()))
            continue
        if receita.peca == PECA_DO_HEFESTO:
            if instalada is None:
                instalada = peca_do_hefesto_instalada(home)
            achadas.append(Leitura(receita, sinal, instalada))
            continue
        if nomes is None:
            nomes = _nomes_ao_lado_do_executavel(raiz)
        presente = receita.peca.lower() in nomes if nomes else None
        achadas.append(Leitura(receita, sinal, presente))
    return tuple(achadas)


def ambiente_do_jogo(
    raiz: Path | None, tabela: Iterable[Receita] | None = None, home: Path | None = None
) -> dict[str, str]:
    """As variáveis que valem: só as receitas com a peça confirmada no lugar."""
    env: dict[str, str] = {}
    for leitura in ler_jogo(raiz, tabela, home):
        if leitura.peca_presente is not True:
            continue
        r = leitura.receita
        env[r.variavel] = f"{env[r.variavel]};{r.valor}" if r.variavel in env else r.valor
    return env


def pecas_que_faltam(
    raiz: Path | None, tabela: Iterable[Receita] | None = None, home: Path | None = None
) -> tuple[str, ...]:
    """Os nomes das peças que o sinal pede e o disco não tem, sem repetir (o par da peça do
    Hefesto são duas linhas e uma peça só)."""
    faltam: list[str] = []
    for leitura in ler_jogo(raiz, tabela, home):
        if leitura.peca_presente is not False:
            continue
        peca = leitura.receita.peca
        nome = NOME_DA_PECA_DO_HEFESTO if peca == PECA_DO_HEFESTO else peca
        if nome not in faltam:
            faltam.append(nome)
    return tuple(faltam)


def jogo_gdk_sem_ajudante(
    raiz: Path | None, tabela: Iterable[Receita] | None = None, home: Path | None = None
) -> bool:
    """O jogo recebe a peça GDK do Hefesto (no lugar, no sha do pino) e falta o ajudante de login.

    Sem o ajudante a peça grava «sem conta, o jogo segue local» no log dela e o jogo abre sem conta,
    amigos nem online. Jogo que não recebe a peça (sem o sinal, ou com a peça faltando, que o
    prontuário já diz em ``falta_a_peca``) nunca cai aqui.
    """
    recebe = any(
        leitura.receita.peca == PECA_DO_HEFESTO and leitura.peca_presente is True
        for leitura in ler_jogo(raiz, tabela, home)
    )
    return recebe and not caminho_do_ajudante_de_login(home).exists()


def ambientes_dos_jogos(home: Path | None = None) -> dict[str, dict[str, str]]:
    """``{appid: ambiente}`` dos jogos instalados cujo disco liga uma receita com a peça."""
    tabela = carregar_tabela()
    if not tabela:
        return {}
    try:
        from .prontuario_dos_jogos import jogos_instalados
    except ImportError:  # pragma: no cover - executado como script avulso
        from prontuario_dos_jogos import jogos_instalados  # type: ignore[no-redef]
    fora: dict[str, dict[str, str]] = {}
    for appid, _nome, raiz in jogos_instalados(home):
        env = ambiente_do_jogo(raiz, tabela, home)
        if env:
            fora[appid] = env
    return fora


__all__ = [
    "MODOS_DO_OVERRIDE",
    "NOME_DA_PECA_DO_HEFESTO",
    "NOME_DO_AJUDANTE",
    "PASTA_DA_PECA",
    "PASTA_DO_AJUDANTE",
    "PECA_DO_HEFESTO",
    "PECA_E_O_SINAL",
    "PINO_DA_PECA",
    "TABELA",
    "VARIAVEIS_DO_WRAPPER",
    "Leitura",
    "Receita",
    "achar_sinal",
    "ambiente_do_jogo",
    "ambientes_dos_jogos",
    "arquivos_do_sinal",
    "caminho_do_ajudante_de_login",
    "carregar_tabela",
    "jogo_gdk_sem_ajudante",
    "ler_jogo",
    "override_valido",
    "pasta_da_peca",
    "peca_do_hefesto_instalada",
    "pecas_que_faltam",
    "valor_valido",
]
