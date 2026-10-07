#!/usr/bin/env python3
"""Os contratos de fora: todo ponto de contato com o mundo do outro tem linha no censo.

O Hefesto conversa com o BlueZ, o PipeWire, o systemd, a Steam, o Proton, o kernel e
o COSMIC. Quando um deles evolui, o que quebra é o ponto de contato que ninguém sabia
que existia. O censo é ``docs/data/contratos-de-fora.csv``, uma linha por
(arquivo, alvo); esta régua mede o código e reprova a divergência nos dois sentidos.

O que ela conta, por AST em ``src/`` (comentário e docstring não contam):

* ``cmd:<ferramenta>``  uma ferramenta do outro como argumento (``pactl``, ``busctl``…),
  e ``cmd:<dinâmico>`` quando o arquivo lança processo e nenhuma ferramenta aparece nele.
* ``path:<caminho>``    um caminho de ``/sys``, ``/proc``, ``/var``, ``/etc``, ``/run``, ``/dev``…
* ``dbus:<nome>``      um nome do barramento (``org.bluez``, ``org.freedesktop.login1``…).
* ``cfg:<arquivo>``     o arquivo de configuração de outro dono (``.vdf``, ``wireplumber``…).
* ``lib:<módulo>``      uma biblioteca de dispositivo (``evdev``, ``pyudev``…).
* ``cmd:pactl-list-longo``  ``pactl list sources|cards|sinks`` sem ``short``: o formato de
  texto que a ferramenta não promete.

Fora de ``src/`` (``scripts/``, ``assets/``, ``install.sh``…), por texto, só a lista curta
das formas que já quebraram: ``/var/lib/bluetooth``, ``.vdf`` e o ``pactl list`` longo.

A régua reprova: contato sem linha; linha cujo contato sumiu (ou cujo símbolo não existe
mais); linha ``interna``/``versão``/``comando`` sem ``motivo`` e sem ``sprint_filha`` que
exista; ``como_o_doctor_ve`` que cita um contrato do doctor que não existe. E há UMA
catraca, que só desce: o número de linhas frágeis (``interna``, ``versão`` ou ``comando``).
O teto mora em ``docs/data/os-contratos-de-fora.json``.
"""

from __future__ import annotations

import ast
import csv
import re
import subprocess
import sys
from collections.abc import Iterable
from dataclasses import dataclass
from pathlib import Path

RAIZ = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(Path(__file__).resolve().parent))

from catraca import (  # noqa: E402
    Catraca,
    CatracaTorta,
    Censo,
    Medida,
    executar,
    montar_argumentos,
)

PACOTE = Path("src") / "hefesto_dualsense4unix"
CENSO = Path("docs/data/contratos-de-fora.csv")
CADERNO = Path("docs/data/os-contratos-de-fora.json")
SPRINTS = Path("docs/process/sprints")
MODULO_DO_DOCTOR = Path("src/hefesto_dualsense4unix/integrations/contratos_de_fora.py")

COLUNAS = (
    "dono", "arquivo", "alvo", "onde", "porta", "pergunta", "forma",
    "o_que_quebra_se_mudar", "como_o_doctor_ve", "motivo", "sprint_filha",
)
PORTAS = {"oficial", "interna"}
PERGUNTAS = {"capacidade", "versão"}
FORMAS = {"converge", "comando"}
SEM_DOCTOR = "-"
FRAGEIS = "linhas-frageis"

# ---------------------------------------------------------------------------
# O vocabulário do outro lado.

FERRAMENTAS = (
    "pactl", "wpctl", "pw-dump", "pw-cli", "pw-cat", "pw-play", "pw-record", "pw-loopback",
    "pw-top", "parec", "parecord", "paplay", "amixer", "aplay", "arecord",
    "systemctl", "journalctl", "loginctl", "busctl", "bluetoothctl", "btmgmt", "hciconfig",
    "hcitool", "steam", "gio", "xdg-open", "xdg-mime", "flatpak", "dpkg", "apt", "curl",
    "wmctrl", "xdotool", "xprop", "sudo", "pkexec", "udevadm", "setfacl", "modprobe",
    "rfkill", "nmcli", "iw", "lsusb", "lutris", "heroic", "google-chrome", "wlr-randr",
    "cosmic-comp", "gdbus", "dbus-send", "upower", "uname", "ffmpeg", "wlrctl", "systemd-run",
    "xdg-desktop-portal",
)
#: nomes que também são palavras do domínio (a loja ``steam``, o ``gio`` do GLib, o ``flatpak`` do
#: pacote): só contam como ferramenta quando são o argv[0] de uma lista ou o argumento do ``which``.
_AMBIGUAS = frozenset({"steam", "gio", "flatpak", "sudo", "apt", "curl", "dpkg", "iw", "uname"})
_FERRAMENTA_RX = re.compile(
    r"^(" + "|".join(re.escape(f) for f in FERRAMENTAS) + r")(\s+[\w\-./=@:%{}\[\]*]+)*$"
)
_CAMINHO_RX = re.compile(r"^/(sys|proc|var|etc|run|dev|lib)/|^/usr/lib/")
#: caminho que é do próprio Hefesto ou do lugar onde ele se instala não é contrato de fora.
_CAMINHO_PROPRIO_RX = re.compile(r"hefesto|^/usr/(local|share|bin)/|/tmp/|^/sys/usb/|^/var/lib/?$")
_DBUS_RX = re.compile(r"^(org\.(bluez|freedesktop|gnome|kde)|com\.system76|net\.hadess)(\.[A-Za-z0-9_]+)*$")
_CFG_RX = re.compile(
    r"(^[\w.<>*/-]+\.vdf$|^steamapps$|^compatibilitytools\.d$|^\.steam$|^wireplumber$|"
    r"^wireplumber\.conf\.d$|^pipewire$|^pipewire\.conf\.d$|^cosmic$|^lutris$|^heroic$)"
)
_BIBLIOTECAS = frozenset({
    "evdev", "pyudev", "pydualsense", "pulsectl", "dbus", "dbus_next", "dbus_fast", "pydbus",
    "hid", "usb", "uinput", "jeepney",
})
_PROCESSO_ATRIBUTOS = {
    "subprocess": {"run", "Popen", "check_output", "check_call", "call", "getoutput",
                   "getstatusoutput"},
    "os": {"system", "popen"},
    "asyncio": {"create_subprocess_exec", "create_subprocess_shell"},
}
_LISTAGENS_DO_PACTL = frozenset({"sources", "cards", "sinks", "source-outputs", "sink-inputs"})

# Fora de src/: só o que já quebrou.
_PASTAS_DE_TEXTO = ("scripts", "assets", "packaging", "flatpak")
_SOLTOS_DE_TEXTO = ("install.sh", "uninstall.sh", "run.sh")
_NAO_SE_VARRE = {
    "scripts/check_os_contratos_de_fora.py",
}
_TEXTO_RX = {
    "path:/var/lib/bluetooth": re.compile(r"/var/lib/bluetooth"),
    "cfg:.vdf": re.compile(r"\.vdf\b"),
    "cmd:pactl-list-longo": re.compile(
        r"pactl\s+list\s+(sources|cards|sinks|source-outputs|sink-inputs)(?!\s+short)\b"
    ),
}
_EXTENSOES_BINARIAS = {".png", ".svg", ".ico", ".gz", ".zst", ".woff", ".woff2", ".jpg", ".tar"}


@dataclass(frozen=True)
class Contato:
    arquivo: str
    alvo: str
    simbolos: tuple[str, ...]


def normaliza_caminho(texto: str) -> str:
    """``/sys/class/bluetooth/hci0/x`` -> ``/sys/class/bluetooth``; o número do nó não conta."""
    partes = [p for p in texto.split("/") if p][:3]
    partes = [re.sub(r"\d+$", "N", p) if i == len(partes) - 1 else p for i, p in enumerate(partes)]
    partes = [p.split("%")[0].split("{")[0].rstrip(":") for p in partes]
    return "/" + "/".join(p for p in partes if p)


def normaliza_dbus(nome: str) -> str:
    partes = nome.split(".")
    corte = 3 if partes[1] == "freedesktop" else 2
    return ".".join(partes[:corte])


def _docstrings(arvore: ast.AST) -> set[int]:
    ids: set[int] = set()
    for no in ast.walk(arvore):
        if isinstance(no, (ast.Module, ast.ClassDef, ast.FunctionDef, ast.AsyncFunctionDef)):
            corpo = getattr(no, "body", [])
            if (corpo and isinstance(corpo[0], ast.Expr) and isinstance(corpo[0].value, ast.Constant)
                    and isinstance(corpo[0].value.value, str)):
                ids.add(id(corpo[0].value))
    return ids


def _e_processo(no: ast.Call) -> bool:
    f = no.func
    return (isinstance(f, ast.Attribute) and isinstance(f.value, ast.Name)
            and f.attr in _PROCESSO_ATRIBUTOS.get(f.value.id, ()))


def _referencia_a_processo(no: ast.AST) -> bool:
    """``subprocess.Popen`` passado como valor (``popen=subprocess.Popen``) também lança processo."""
    return (isinstance(no, ast.Attribute) and isinstance(no.value, ast.Name)
            and no.attr in _PROCESSO_ATRIBUTOS.get(no.value.id, ()))


class _Percorredor(ast.NodeVisitor):
    def __init__(self, docstrings: set[int]) -> None:
        self.docstrings = docstrings
        self.pilha: list[str] = []
        self.achados: dict[str, list[str]] = {}
        self.lanca_processo = False

    def _anota(self, alvo: str) -> None:
        simbolo = ".".join(self.pilha) or "<módulo>"
        lista = self.achados.setdefault(alvo, [])
        if simbolo not in lista:
            lista.append(simbolo)

    def _entra(self, no: ast.AST, nome: str) -> None:
        self.pilha.append(nome)
        self.generic_visit(no)
        self.pilha.pop()

    def visit_FunctionDef(self, no: ast.FunctionDef) -> None:
        self._entra(no, no.name)

    def visit_AsyncFunctionDef(self, no: ast.AsyncFunctionDef) -> None:
        self._entra(no, no.name)

    def visit_ClassDef(self, no: ast.ClassDef) -> None:
        self._entra(no, no.name)

    def visit_Import(self, no: ast.Import) -> None:
        for a in no.names:
            if a.name.split(".")[0] in _BIBLIOTECAS:
                self._anota(f"lib:{a.name.split('.')[0]}")

    def visit_ImportFrom(self, no: ast.ImportFrom) -> None:
        if no.module and no.level == 0 and no.module.split(".")[0] in _BIBLIOTECAS:
            self._anota(f"lib:{no.module.split('.')[0]}")

    def visit_Call(self, no: ast.Call) -> None:
        if _e_processo(no):
            self.lanca_processo = True
        f = no.func
        if (isinstance(f, ast.Attribute) and f.attr == "which" and no.args
                and isinstance(no.args[0], ast.Constant) and no.args[0].value in _AMBIGUAS):
            self._anota(f"cmd:{no.args[0].value}")
        self.generic_visit(no)

    def visit_Attribute(self, no: ast.Attribute) -> None:
        if _referencia_a_processo(no):
            self.lanca_processo = True
        self.generic_visit(no)

    def _lista_do_pactl(self, no: ast.List | ast.Tuple) -> None:
        textos = [e.value for e in no.elts if isinstance(e, ast.Constant) and isinstance(e.value, str)]
        if ("list" in textos and "short" not in textos
                and any(t in _LISTAGENS_DO_PACTL for t in textos)
                and "pactl" in textos):
            self._anota("cmd:pactl-list-longo")

    def _argv_zero(self, no: ast.List | ast.Tuple) -> None:
        """O argv[0] de uma lista conta como ferramenta mesmo quando o nome é ambíguo."""
        if no.elts and isinstance(no.elts[0], ast.Constant) and isinstance(no.elts[0].value, str):
            nome = no.elts[0].value.split()[0] if no.elts[0].value.split() else ""
            if nome in _AMBIGUAS:
                self._anota(f"cmd:{nome}")

    def visit_List(self, no: ast.List) -> None:
        self._lista_do_pactl(no)
        self._argv_zero(no)
        self.generic_visit(no)

    def visit_Tuple(self, no: ast.Tuple) -> None:
        self._lista_do_pactl(no)
        self._argv_zero(no)
        self.generic_visit(no)

    def visit_Constant(self, no: ast.Constant) -> None:
        valor = no.value
        if not isinstance(valor, str) or id(no) in self.docstrings or "\n" in valor:
            return
        if _FERRAMENTA_RX.match(valor):
            if valor.split()[0] not in _AMBIGUAS or len(valor.split()) > 1:
                self._anota(f"cmd:{valor.split()[0]}")
        elif _CAMINHO_RX.match(valor):
            if not _CAMINHO_PROPRIO_RX.search(valor):
                self._anota(f"path:{normaliza_caminho(valor)}")
        elif _DBUS_RX.match(valor):
            self._anota(f"dbus:{normaliza_dbus(valor)}")
        elif _CFG_RX.search(valor):
            self._anota(f"cfg:{valor.rsplit('/', 1)[-1]}")


def contatos_do_codigo(fonte: str, arquivo: str) -> list[Contato]:
    """Os contatos de UM arquivo de Python. Erro de sintaxe estoura: arquivo ilegível não é limpo."""
    arvore = ast.parse(fonte)
    p = _Percorredor(_docstrings(arvore))
    p.visit(arvore)
    achados = dict(p.achados)
    if p.lanca_processo and not any(a.startswith("cmd:") for a in achados):
        achados["cmd:<dinâmico>"] = ["<módulo>"]
    return [Contato(arquivo, alvo, tuple(simbolos)) for alvo, simbolos in sorted(achados.items())]


def contatos_do_texto(texto: str, arquivo: str) -> list[Contato]:
    """Fora de ``src/``: a lista curta das formas que já quebraram, por texto."""
    achados: list[Contato] = []
    # comentário não é contato: a linha que começa em `#` fica de fora.
    texto = "\n".join(li for li in texto.splitlines() if not li.lstrip().startswith("#"))
    for alvo, rx in _TEXTO_RX.items():
        if rx.search(texto):
            achados.append(Contato(arquivo, alvo, ("*",)))
    return achados


def _arquivos_versionados(raiz: Path) -> list[str]:
    saida = subprocess.run(
        ["git", "ls-files", "-z", "--cached", "--others", "--exclude-standard"],
        cwd=raiz, capture_output=True, check=False)
    if saida.returncode == 0 and saida.stdout:
        return sorted(p for p in saida.stdout.decode("utf-8").split("\0") if p)
    return sorted(str(p.relative_to(raiz)) for p in raiz.rglob("*") if p.is_file())


def varrer(raiz: Path) -> list[Contato]:
    """Todos os contatos da árvore. Universo vazio é erro do chamador (a catraca recusa)."""
    achados: list[Contato] = []
    for rel in _arquivos_versionados(raiz):
        caminho = raiz / rel
        if not caminho.is_file() or rel in _NAO_SE_VARRE:
            continue
        if rel.startswith(str(PACOTE) + "/") and rel.endswith(".py"):
            achados.extend(contatos_do_codigo(caminho.read_text(encoding="utf-8"), rel))
        elif (rel.split("/")[0] in _PASTAS_DE_TEXTO or rel in _SOLTOS_DE_TEXTO) \
                and caminho.suffix not in _EXTENSOES_BINARIAS and not rel.startswith("scripts/ensaios/"):
            try:
                texto = caminho.read_text(encoding="utf-8")
            except UnicodeDecodeError:
                continue
            achados.extend(contatos_do_texto(texto, rel))
    return achados


# ---------------------------------------------------------------------------
# O censo (o CSV).


def ler_censo(raiz: Path) -> list[dict[str, str]]:
    caminho = raiz / CENSO
    if not caminho.exists():
        raise CatracaTorta(f"{CENSO} não existe: sem censo a régua não tem o que conferir.")
    with caminho.open(encoding="utf-8", newline="") as fh:
        leitor = csv.DictReader(fh)
        if tuple(leitor.fieldnames or ()) != COLUNAS:
            raise CatracaTorta(f"{CENSO}: colunas {leitor.fieldnames} != {list(COLUNAS)}")
        return [{k: (v or "").strip() for k, v in linha.items()} for linha in leitor]


def e_fragil(linha: dict[str, str]) -> bool:
    return linha["porta"] == "interna" or linha["pergunta"] == "versão" or linha["forma"] == "comando"


def _simbolos_do_arquivo(raiz: Path, arquivo: str) -> set[str] | None:
    caminho = raiz / arquivo
    if not caminho.is_file() or caminho.suffix != ".py":
        return None
    nomes: set[str] = set()

    def anda(no: ast.AST, pilha: list[str]) -> None:
        for filho in ast.iter_child_nodes(no):
            if isinstance(filho, (ast.FunctionDef, ast.AsyncFunctionDef, ast.ClassDef)):
                nova = [*pilha, filho.name]
                nomes.add(".".join(nova))
                anda(filho, nova)
            else:
                anda(filho, pilha)

    anda(ast.parse(caminho.read_text(encoding="utf-8")), [])
    return nomes


def contratos_do_doctor(raiz: Path) -> set[str]:
    """Os ids declarados no módulo do doctor (``id="…"`` da tabela), lidos por AST."""
    caminho = raiz / MODULO_DO_DOCTOR
    if not caminho.exists():
        return set()
    ids: set[str] = set()
    for no in ast.walk(ast.parse(caminho.read_text(encoding="utf-8"))):
        if isinstance(no, ast.Call) and getattr(no.func, "id", "") == "Contrato":
            for kw in no.keywords:
                if kw.arg == "id" and isinstance(kw.value, ast.Constant):
                    ids.add(str(kw.value.value))
    return ids


def julgar(raiz: Path, contatos: Iterable[Contato] | None = None) -> list[str]:
    """As queixas, nomeadas. Lista vazia = o censo diz o que o código faz."""
    contatos = list(varrer(raiz) if contatos is None else contatos)
    linhas = ler_censo(raiz)
    queixas: list[str] = []
    achados = {(c.arquivo, c.alvo): c for c in contatos}
    no_censo: dict[tuple[str, str], dict[str, str]] = {}
    for linha in linhas:
        chave = (linha["arquivo"], linha["alvo"])
        if chave in no_censo:
            queixas.append(f"linha DUPLICADA no censo: {chave[0]} {chave[1]}")
        no_censo[chave] = linha

    for (arquivo, alvo), c in sorted(achados.items()):
        if (arquivo, alvo) not in no_censo:
            queixas.append(
                f"contato SEM LINHA: {arquivo} toca `{alvo}` (em {', '.join(c.simbolos[:3])}). "
                f"Acrescente a linha em {CENSO}: dono, porta, pergunta, forma e o que quebra.")
    for (arquivo, alvo), linha in sorted(no_censo.items()):
        if (arquivo, alvo) not in achados:
            queixas.append(
                f"linha MORTA: {arquivo} já não toca `{alvo}` (ou o arquivo saiu). "
                "Fato errado se substitui: tire a linha.")
            continue
        queixas.extend(_julgar_a_linha(raiz, linha))
    return queixas


def _julgar_a_linha(raiz: Path, linha: dict[str, str]) -> list[str]:
    rotulo = f"{linha['arquivo']} `{linha['alvo']}`"
    q: list[str] = []
    for campo, validos in (("porta", PORTAS), ("pergunta", PERGUNTAS), ("forma", FORMAS)):
        if linha[campo] not in validos:
            q.append(f"{rotulo}: {campo}={linha[campo]!r} não é um de {sorted(validos)}")
    for campo in ("dono", "o_que_quebra_se_mudar", "como_o_doctor_ve"):
        if not linha[campo]:
            q.append(f"{rotulo}: `{campo}` vazio")
    simbolos = _simbolos_do_arquivo(raiz, linha["arquivo"])
    for onde in linha["onde"].split():
        if onde in ("*", "<módulo>"):
            continue
        if simbolos is None:
            q.append(f"{rotulo}: `onde` {onde!r} num arquivo que não é Python; use `*`")
        elif onde not in simbolos:
            q.append(f"{rotulo}: o símbolo {onde!r} não existe mais em {linha['arquivo']}")
    if not linha["onde"]:
        q.append(f"{rotulo}: `onde` vazio")
    if e_fragil(linha):
        if not linha["motivo"]:
            q.append(f"{rotulo}: linha frágil (interna, versão ou comando) sem `motivo`")
        filha = linha["sprint_filha"]
        # `docs/process/` é ignorado pelo git: num clone limpo (o CI) a pasta não existe, e a
        # filha só se confere onde ela mora. A coluna vazia reprova em toda parte.
        tem_sprints = any((raiz / SPRINTS).glob("*.md")) if (raiz / SPRINTS).is_dir() else False
        if not filha or (tem_sprints and not list((raiz / SPRINTS).glob(f"*{filha}*.md"))):
            q.append(f"{rotulo}: linha frágil sem `sprint_filha` que exista em {SPRINTS} ({filha!r})")
    doctor = linha["como_o_doctor_ve"]
    if doctor.startswith("contrato:") and doctor.split(":", 1)[1] not in contratos_do_doctor(raiz):
        q.append(f"{rotulo}: o doctor não declara {doctor!r} em {MODULO_DO_DOCTOR}")
    return q


# ---------------------------------------------------------------------------
# A catraca: as linhas frágeis só descem.


def censo_das_frageis(raiz: Path) -> Censo:
    linhas = ler_censo(raiz)
    por_dono: dict[str, int] = {}
    for linha in linhas:
        if e_fragil(linha):
            por_dono[linha["dono"]] = por_dono.get(linha["dono"], 0) + 1
    return Censo(
        numero=sum(por_dono.values()),
        universo=len(linhas),
        por_item=por_dono,
        nomes=tuple(f"{li['arquivo']} {li['alvo']}" for li in linhas if e_fragil(li)),
    )


MEDIDAS = (
    Medida(
        FRAGEIS,
        "linhas do censo de contratos de fora com porta interna, pergunta por versão ou forma por comando",
        censo_das_frageis,
        "linhas",
    ),
)


def main(argv: list[str] | None = None) -> int:
    p = montar_argumentos(__doc__.split("\n", 1)[0])
    p.add_argument("--listar", action="store_true", help="imprime os contatos medidos no código")
    a = p.parse_args(argv)
    raiz = Path(a.raiz) if a.raiz else RAIZ
    if a.listar:
        for c in varrer(raiz):
            print(f"{c.arquivo}\t{c.alvo}\t{' '.join(c.simbolos)}")
        return 0
    catraca = Catraca(raiz / CADERNO, MEDIDAS, raiz)
    if a.aceitar is not None or a.forcar_piso:
        return executar(catraca, a, "Os contratos de fora")
    try:
        queixas = julgar(raiz)
        vereditos = catraca.comparar()
    except CatracaTorta as erro:
        print(f"RECUSADO: {erro}", file=sys.stderr)
        return 2
    rc = 0
    for v in vereditos:
        agora = "—" if v.numero is None else v.numero
        piso = "(sem piso)" if not v.piso.existe else v.piso.numero
        print(f"  [{v.estado:<10}] {v.medida.nome:<20} hoje={agora} piso={piso}")
        if not v.passa:
            rc = 1
            for q in v.queixas:
                print(f"      {q}")
            for linha in v.entrou[:30]:
                print(f"      {linha}")
    if queixas:
        rc = 1
        print(f"\n{len(queixas)} divergência(s) entre o código e {CENSO}:")
        for q in queixas[:60]:
            print(f"  - {q}")
    if rc:
        print("\nOs contratos de fora REPROVARAM: ponto de contato novo se declara no censo, "
              "com a porta oficial e a pergunta por capacidade.")
    else:
        for v in vereditos:
            if v.estado == "VERDE" and v.numero is not None and v.piso.numero is not None \
                    and v.numero < v.piso.numero:
                catraca.aceitar([v.medida.nome], "o teto desceu sozinho com o número")
                print(f"  o teto de «{v.medida.nome}» desceu e foi regravado")
    return rc


if __name__ == "__main__":
    raise SystemExit(main())
