"""Fixtures compartilhadas entre testes unit e integration."""

import atexit
import contextlib
import datetime
import errno
import fnmatch
import hashlib
import inspect
import os
import shlex
import shutil
import sys
import tempfile
import threading
import types
from collections.abc import Callable, Iterator
from dataclasses import dataclass
from pathlib import Path
from typing import Any

import pytest

_RAIZ_DESTA_ARVORE = Path(__file__).resolve().parents[1]
_SRC_DESTA_ARVORE = _RAIZ_DESTA_ARVORE / "src"
if _SRC_DESTA_ARVORE.is_dir():
    _caminho = str(_SRC_DESTA_ARVORE)
    while _caminho in sys.path:
        sys.path.remove(_caminho)
    sys.path.insert(0, _caminho)
    _antes = os.environ.get("PYTHONPATH", "")
    if _caminho not in _antes.split(os.pathsep):
        os.environ["PYTHONPATH"] = (
            _caminho + (os.pathsep + _antes if _antes else "")
        )

os.environ.pop("FORCE_COLOR", None)
os.environ.setdefault("NO_COLOR", "1")


from hefesto_dualsense4unix.utils.tela_de_mentira import (
    garantir_tela_de_mentira,
)

garantir_tela_de_mentira(anunciar=False)

os.environ.pop("HEFESTO_AVISO_DE_VERDADE", None)


_PREFIXO_GI = "gi"


def _e_modulo_gi(nome: str) -> bool:
    """True para ``gi`` e qualquer submódulo (``gi.repository.Gtk`` etc.)."""
    return nome == _PREFIXO_GI or nome.startswith(_PREFIXO_GI + ".")


def _gtk_e_real(gtk: Any) -> bool:
    """True quando ``gtk`` expõe widgets de VERDADE, não os do stub."""
    caixa = getattr(gtk, "Box", None)
    if caixa is None or caixa is object:
        return False
    if not isinstance(caixa, type):
        return False
    lista = getattr(gtk, "ListStore", None)
    return lista is not None and lista is not object


def gi_real_no_processo() -> bool:
    """True quando o ``gi`` JÁ CARREGADO neste processo é o PyGObject real."""
    modulo_gi = sys.modules.get(_PREFIXO_GI)
    if modulo_gi is None:
        return False
    if getattr(modulo_gi, "__spec__", None) is None:
        return False
    gtk = sys.modules.get("gi.repository.Gtk")
    if gtk is None:
        return True
    return _gtk_e_real(gtk)


def gi_stub_no_processo() -> bool:
    """True quando há um ``gi`` carregado e ele é FALSO (stub de teste)."""
    return any(_e_modulo_gi(n) for n in sys.modules) and not gi_real_no_processo()


def _remover_gi_do_processo() -> list[str]:
    """Apaga todo ``gi*`` de ``sys.modules`` e devolve os nomes removidos."""
    removidos = [n for n in list(sys.modules) if _e_modulo_gi(n)]
    for nome in removidos:
        del sys.modules[nome]
    return removidos


_FOTO_GI_REAL: dict[str, Any] = {}


def _atualizar_foto_gi_real() -> None:
    """Guarda os módulos ``gi*`` atuais — só chamar com o ``gi`` REAL no ar."""
    for nome in list(sys.modules):
        if _e_modulo_gi(nome):
            _FOTO_GI_REAL[nome] = sys.modules[nome]


def _restaurar_gi_real_da_foto() -> bool:
    """Troca o stub pelos módulos reais fotografados. False se não há foto."""
    if not _FOTO_GI_REAL:
        return False
    _remover_gi_do_processo()
    sys.modules.update(_FOTO_GI_REAL)
    return gi_real_no_processo()


def _sondar_gtk_do_ambiente() -> tuple[bool, bool]:
    """Pergunta a um SUBPROCESSO limpo o que o ambiente tem de GTK."""
    import subprocess

    codigo = (
        "import sys\n"
        "try:\n"
        "    import gi\n"
        "    try:\n"
        "        gi.require_version('Gtk', '3.0')\n"
        "    except Exception:\n"
        "        pass\n"
        "    from gi.repository import Gtk\n"
        "except Exception:\n"
        "    print('0 0')\n"
        "    sys.exit(0)\n"
        "caixa = getattr(Gtk, 'Box', None)\n"
        "lista = getattr(Gtk, 'ListStore', None)\n"
        "real = (\n"
        "    caixa is not None and caixa is not object and isinstance(caixa, type)\n"
        "    and lista is not None and lista is not object\n"
        ")\n"
        "print(('1' if real else '0'), ('1' if hasattr(Gtk, 'ResponseType') else '0'))\n"
    )
    try:
        r = subprocess.run(
            [sys.executable, "-c", codigo],
            capture_output=True,
            timeout=30,
        )
    except Exception:
        return (False, False)
    saida = r.stdout.decode("utf-8", "replace").split()
    if r.returncode != 0 or len(saida) != 2:
        return (False, False)
    return (saida[0] == "1", saida[1] == "1")


GI_REAL_DISPONIVEL, _GTK_RESPONSE_TYPE_PRESENTE = _sondar_gtk_do_ambiente()

EXIGE_GTK_REAL = os.environ.get("HEFESTO_EXIGE_GTK_REAL") == "1"

_MOTIVO_SEM_GI = (
    "GUARDA-GI-REAL-01: PyGObject real ausente (ou substituído por stub de "
    "teste). Instale python3-gi + gir1.2-gtk-3.0 para exercitar a interface."
)

skip_sem_gtk_response = pytest.mark.skipif(
    not _GTK_RESPONSE_TYPE_PRESENTE,
    reason="Gtk.ResponseType indisponível (GTK parcial — CI headless)",
)

skip_sem_gi_real = pytest.mark.skipif(not GI_REAL_DISPONIVEL, reason=_MOTIVO_SEM_GI)

_MODULOS_PULADOS_SEM_GI: list[str] = []

_MODULOS_DESPOLUIDOS: list[str] = []


def _carregar_gi_real() -> None:
    """Importa o PyGObject real (Gtk 3.0) no processo, em silêncio se não der."""
    try:
        import gi

        gi.require_version("Gtk", "3.0")
        repositorio = __import__("gi.repository", fromlist=["Gtk"])
        _ = repositorio.Gtk
    except Exception:  # pragma: no cover — ambiente degradado ou sem GTK
        pass


def exigir_gi_real(motivo: str = "") -> None:
    """Guarda de nível de módulo: exige o PyGObject REAL, reprovando o stub."""
    if gi_real_no_processo():
        return

    if GI_REAL_DISPONIVEL:
        if not _restaurar_gi_real_da_foto():
            _remover_gi_do_processo()
            _carregar_gi_real()
        if gi_real_no_processo():
            _atualizar_foto_gi_real()
            return

    texto = _MOTIVO_SEM_GI + (f" [{motivo}]" if motivo else "")
    _MODULOS_PULADOS_SEM_GI.append(motivo or "<módulo sem rótulo>")
    if EXIGE_GTK_REAL:
        pytest.fail(
            "HEFESTO_EXIGE_GTK_REAL=1 e o GTK real NÃO está disponível: " + texto,
            pytrace=False,
        )
    pytest.skip(texto, allow_module_level=True)


def instalar_stubs_gi(
    monkeypatch: pytest.MonkeyPatch,
    *,
    widgets: tuple[str, ...] = (),
) -> types.ModuleType:
    """Planta stubs de ``gi`` ISOLADOS, desfeitos ao fim do escopo do monkeypatch."""
    gi_mod = types.ModuleType("gi")
    gi_mod.require_version = lambda *_a, **_kw: None  # type: ignore[attr-defined]
    repo_mod = types.ModuleType("gi.repository")
    gtk_mod = types.ModuleType("gi.repository.Gtk")
    for nome in widgets:
        setattr(gtk_mod, nome, object)
    repo_mod.Gtk = gtk_mod  # type: ignore[attr-defined]
    monkeypatch.setitem(sys.modules, "gi", gi_mod)
    monkeypatch.setitem(sys.modules, "gi.repository", repo_mod)
    monkeypatch.setitem(sys.modules, "gi.repository.Gtk", gtk_mod)
    return gtk_mod


def pytest_collectstart(collector: Any) -> None:
    """Impede que o ``gi`` FALSO de um arquivo vaze para o arquivo seguinte."""
    if not isinstance(collector, pytest.Module):
        return
    if gi_real_no_processo():
        _atualizar_foto_gi_real()
        return
    if not gi_stub_no_processo():
        return
    if _restaurar_gi_real_da_foto():
        _MODULOS_DESPOLUIDOS.append(str(getattr(collector, "nodeid", collector)))
        return
    if _remover_gi_do_processo():
        _MODULOS_DESPOLUIDOS.append(str(getattr(collector, "nodeid", collector)))


def _falta_o_gtk(erro: BaseException | None) -> bool:
    """O erro é a falta do GTK real: o `gi` ausente, ou o stub de outro arquivo."""
    vistos: set[int] = set()
    while erro is not None and id(erro) not in vistos:
        vistos.add(id(erro))
        texto = str(erro)
        if isinstance(erro, ModuleNotFoundError) and (erro.name or "").split(".")[0] in (
            "gi",
            "cairo",
        ):
            return True
        if isinstance(erro, ImportError) and "from 'gi.repository'" in texto:
            return True
        if isinstance(erro, AttributeError) and "module 'gi.repository." in texto:
            return True
        erro = erro.__cause__ or erro.__context__
    return False


@pytest.hookimpl(hookwrapper=True)
def pytest_runtest_makereport(item: Any, call: Any) -> Any:
    """Sem o GTK real, o teste que precisa dele PULA com o motivo, e não reprova."""
    resultado = yield
    if GI_REAL_DISPONIVEL or EXIGE_GTK_REAL or call.excinfo is None:
        return
    relatorio = resultado.get_result()
    if relatorio.outcome != "failed" or not _falta_o_gtk(call.excinfo.value):
        return
    caminho, linha, _ = item.location
    relatorio.outcome = "skipped"
    relatorio.longrepr = (str(item.path), (linha or 0) + 1, f"Skipped: {_MOTIVO_SEM_GI}")
    if caminho not in _MODULOS_PULADOS_SEM_GI:
        _MODULOS_PULADOS_SEM_GI.append(caminho)


def pytest_runtest_setup(item: Any) -> None:
    """Diz à vigia QUEM está na mesa — sem isto o livro acusa sem endereço."""
    vigia = vigia_da_sessao()
    if vigia is not None:
        vigia.quem = str(getattr(item, "nodeid", item))


def pytest_report_header(config: Any) -> list[str]:
    """Diz, no cabeçalho do run, contra QUAL GTK a suíte vai rodar."""
    estado = "REAL (python3-gi + typelibs)" if GI_REAL_DISPONIVEL else "AUSENTE"
    extra = " | HEFESTO_EXIGE_GTK_REAL=1 (pulo vira reprovação)" if EXIGE_GTK_REAL else ""
    linhas = [f"guarda-gi-real-01: PyGObject {estado}{extra}"]
    if _FAIXA_NO_INICIO:
        onde = _FAIXA_DIR_REAL[0] if _FAIXA_DIR_REAL else _faixa_config_dir_real()
        arquivos = sorted({chave.split("::")[0] for chave in _FAIXA_NO_INICIO})
        linhas.append(
            f"faixa-no-berco-01: {len(_FAIXA_NO_INICIO)} endereço(s) de FIXTURE "
            f"JÁ moram em {onde}, em {len(arquivos)} arquivo(s) — "
            f"`python3 scripts/check_faixa_sintetica.py --casa` lista quais. "
            "Não é desta sessão; a suíte só reprova o que APARECER agora."
        )
    return linhas


def pytest_terminal_summary(terminalreporter: Any, exitstatus: int, config: Any) -> None:
    """Torna VISÍVEL o pulo por falta de GTK — o pulo calado é parte do defeito."""
    escrever = terminalreporter.write_line
    if _MODULOS_PULADOS_SEM_GI:
        escrever("")
        escrever(
            "GUARDA-GI-REAL-01: "
            f"{len(_MODULOS_PULADOS_SEM_GI)} módulo(s) de interface PULARAM por "
            "falta de PyGObject real:",
            bold=True,
        )
        for nome in _MODULOS_PULADOS_SEM_GI:
            escrever(f"  - {nome}")
        escrever(
            "  Isto NÃO é cobertura. Instale python3-gi + gir1.2-gtk-3.0 "
            "para exercitar a interface."
        )
    if _MODULOS_DESPOLUIDOS:
        escrever("")
        escrever(
            "GUARDA-GI-REAL-01: stub de `gi` retirado antes de "
            f"{len(_MODULOS_DESPOLUIDOS)} módulo(s) — a poluição de sys.modules "
            "NÃO vazou entre arquivos.",
            bold=True,
        )


# algo?". A fixture `_hefesto_fake_env` isola os diretórios XDG — mas NÃO isola

_CANARIO_ALVOS: tuple[str, ...] = (
    ".config/hefesto-dualsense4unix",
    ".config/wireplumber",
    ".local/share/hefesto-dualsense4unix",
)

_CANARIO_ALVOS_AVISO: tuple[str, ...] = (".local/state/hefesto-dualsense4unix",)

_CANARIO_DESLIGADO_ENV = "HEFESTO_SEM_CANARIO_FS"

_CANARIO_FOTO_INICIAL: dict[str, tuple[int, int, str]] = {}

_CANARIO_FOTO_AVISO: dict[str, tuple[int, int, str]] = {}

_CANARIO_ARMADO = False

_CANARIO_LIMITE_RESUMO = 4 * 1024 * 1024

# O teto é de TAMANHO, por filho de primeiro nível, e não de nome. Medido em
# 06/10/2026, o maior filho vigiado tem 286 entradas e 1,7 MB; o teto fica a 7x
# e a 19x disso. Em 28/09 uma pasta da casa tinha 278 mil arquivos e 7,1 GB de
# sha256 por foto: sem o teto, a foto custava isso.
_CANARIO_TETO_ENTRADAS = 2_000

_CANARIO_TETO_BYTES = 32 * 1024 * 1024

_CANARIO_PESADO = "[pesado: o canário não entrou]"

_CANARIO_LINK = "-> "

_CANARIO_LIMITE_NOMES = 3

_CANARIO_LIMITE_AVISO = 10


def _canario_ligado() -> bool:
    return os.environ.get(_CANARIO_DESLIGADO_ENV) != "1"


# DualSense REAIS; depois, só os quatro forjados.

_FAIXA_DESLIGADA_ENV = "HEFESTO_SEM_FAIXA_SINTETICA"

_FAIXA_NO_INICIO: set[str] = set()

_FAIXA_DIR_REAL: list[Path] = []

_FAIXA_ARMADA = False


def _faixa_ligada() -> bool:
    return os.environ.get(_FAIXA_DESLIGADA_ENV) != "1"


def _faixa_config_dir_real() -> Path:
    """O `config_dir()` de produção, resolvido do ambiente NA HORA da chamada."""
    base = os.environ.get("XDG_CONFIG_HOME", "").strip()
    raiz = Path(base) if base else Path(os.path.expanduser("~")) / ".config"
    return raiz / "hefesto-dualsense4unix"


def _faixa_enderecos() -> set[str]:
    """Endereços sintéticos hoje no `config_dir()` real. Vazio se algo faltar."""
    try:
        raiz_do_repo = Path(__file__).resolve().parents[1]
        pasta_de_scripts = str(raiz_do_repo / "scripts")
        if pasta_de_scripts not in sys.path:
            sys.path.insert(0, pasta_de_scripts)
        import check_faixa_sintetica

        return check_faixa_sintetica.enderecos(_faixa_config_dir_real())
    except Exception:
        return set()


def _faixa_no_fim_da_sessao(session: Any) -> None:
    """Reprova se um endereço de fixture APARECEU no `config_dir()` real."""
    if not _faixa_ligada() or not _FAIXA_ARMADA:
        return
    novos = sorted(_faixa_enderecos() - _FAIXA_NO_INICIO)
    if not novos:
        return
    _escrever_no_terminal(session, [
        "",
        "FAIXA-NO-BERCO-01: endereço de FIXTURE apareceu no config_dir REAL "
        f"durante esta sessão ({len(novos)}):",
        *[f"  - {n}" for n in novos],
        "  Isto é a mesa de produção, não um dublê. Algum teste (ou um processo",
        "  que ele acordou) resolveu o `config_dir()` verdadeiro.",
        "  As TRÊS classes que o LAR-DE-SESSAO-01 já fecha — constante de módulo",
        "  avaliada no import, escrita depois do teardown do monkeypatch e",
        f"  subprocesso — só voltam com {_LAR_DESLIGADO_ENV}=1. Se ele está",
        "  desligado, ligue-o de volta antes de procurar em qualquer outro lugar.",
        "  Com ele LIGADO e este alarme aceso, o caminho não passou por",
        "  `HOME`/`XDG_*`: procure caminho ABSOLUTO escrito à mão, `pwd`/",
        "  `getpwuid` (que ignoram o HOME) e `sudo`/`systemd-run`, que trocam de",
        "  usuário e de ambiente.",
        f"  Escotilha: {_FAIXA_DESLIGADA_ENV}=1 (e ela NÃO é a do canário).",
    ])
    session.exitstatus = 1


def _canario_raizes() -> list[Path]:
    """Os alvos resolvidos contra o ``HOME`` REAL do processo."""
    lar = Path(os.path.expanduser("~"))
    return [lar / alvo for alvo in _CANARIO_ALVOS]


def _canario_raizes_de_aviso() -> list[Path]:
    """As árvores que só AVISAM, resolvidas contra o ``HOME`` VIVO."""
    lar = Path(os.path.expanduser("~"))
    return [lar / alvo for alvo in _CANARIO_ALVOS_AVISO]


def _resumo_do_arquivo(caminho: Path, tamanho: int) -> str:
    """sha256 do conteúdo — vazio para diretórios, ilegíveis e arquivos enormes."""
    if tamanho > _CANARIO_LIMITE_RESUMO:
        return ""
    try:
        return hashlib.sha256(caminho.read_bytes()).hexdigest()
    except OSError:
        return ""


_Foto = dict[str, tuple[int, int, str]]


def _entrada_de_link(caminho: str) -> tuple[int, int, str]:
    """O link é UMA entrada, pelo `lstat`, com o alvo normalizado no lugar do resumo."""
    st = os.lstat(caminho)
    try:
        alvo = os.readlink(caminho)
    except OSError:
        alvo = ""
    absoluto = os.path.normpath(os.path.join(os.path.dirname(caminho), alvo))
    return (st.st_mtime_ns, st.st_size, _CANARIO_LINK + absoluto)


def _entrada_de_pesado() -> tuple[int, int, str]:
    """A pasta que o canário não percorre: uma entrada só, sem conteúdo."""
    return (0, 0, _CANARIO_PESADO)


def _caminhar_com_teto(raiz: str, foto: _Foto) -> bool:
    """Anda sob `raiz` sem seguir link; False quando o teto estoura (foto incompleta)."""
    pilha = [raiz]
    entradas = 0
    gastos = 0
    while pilha:
        atual = pilha.pop()
        try:
            varridas = list(os.scandir(atual))
        except OSError:
            continue
        for entrada in varridas:
            entradas += 1
            if entradas > _CANARIO_TETO_ENTRADAS:
                return False
            caminho = entrada.path
            try:
                if entrada.is_symlink():
                    foto[caminho] = _entrada_de_link(caminho)
                    continue
                st = entrada.stat(follow_symlinks=False)
                e_pasta = entrada.is_dir(follow_symlinks=False)
                e_arquivo = entrada.is_file(follow_symlinks=False)
            except OSError:
                continue
            resumo = ""
            if e_arquivo and st.st_size <= _CANARIO_LIMITE_RESUMO:
                if gastos + st.st_size > _CANARIO_TETO_BYTES:
                    return False
                gastos += st.st_size
                resumo = _resumo_do_arquivo(Path(caminho), st.st_size)
            foto[caminho] = (st.st_mtime_ns, st.st_size, resumo)
            if e_pasta:
                pilha.append(caminho)
    return True


def _primeiro_nivel(
    filhos: list[os.DirEntry[str]],
) -> tuple[_Foto, list[str]] | None:
    """O primeiro nível inteiro e as pastas dele; None quando ele sozinho passa do teto."""
    foto: _Foto = {}
    pastas: list[str] = []
    gastos = 0
    if len(filhos) > _CANARIO_TETO_ENTRADAS:
        return None
    for entrada in filhos:
        caminho = entrada.path
        try:
            if entrada.is_symlink():
                foto[caminho] = _entrada_de_link(caminho)
                continue
            st = entrada.stat(follow_symlinks=False)
            if entrada.is_dir(follow_symlinks=False):
                foto[caminho] = (st.st_mtime_ns, st.st_size, "")
                pastas.append(caminho)
                continue
            resumo = ""
            if entrada.is_file(follow_symlinks=False) and st.st_size <= _CANARIO_LIMITE_RESUMO:
                if gastos + st.st_size > _CANARIO_TETO_BYTES:
                    return None
                gastos += st.st_size
                resumo = _resumo_do_arquivo(Path(caminho), st.st_size)
            foto[caminho] = (st.st_mtime_ns, st.st_size, resumo)
        except OSError:
            continue
    return foto, pastas


def _fotografar_arvore(raiz: Path, pesados: frozenset[str] | None = None) -> _Foto:
    """{caminho: (mtime_ns, tamanho, resumo)} sob `raiz`. Ausente = dict vazio.

    O primeiro nível entra inteiro. Cada pasta de primeiro nível é andada até
    o teto (`_CANARIO_TETO_ENTRADAS` / `_CANARIO_TETO_BYTES`); estourado, ela
    vira UMA entrada `_CANARIO_PESADO`. `pesados` é a lista da foto do começo:
    esses não são andados de novo, e um pesado que encolhe não vira chuva de
    CRIADO. Link é entrada, nunca caminho.
    """
    foto: _Foto = {}
    if not raiz.exists():
        return foto
    try:
        st = raiz.stat()
    except OSError:
        return foto
    if pesados is not None and str(raiz) in pesados:
        foto[str(raiz)] = _entrada_de_pesado()
        return foto
    try:
        filhos = list(os.scandir(raiz))
    except OSError:
        return foto
    foto[str(raiz)] = (st.st_mtime_ns, st.st_size, "")
    nivel = _primeiro_nivel(filhos)
    if nivel is None:
        foto[str(raiz)] = _entrada_de_pesado()
        return foto
    foto.update(nivel[0])
    for pasta in nivel[1]:
        if pesados is not None and pasta in pesados:
            foto[pasta] = _entrada_de_pesado()
            continue
        parcial: _Foto = {}
        if _caminhar_com_teto(pasta, parcial):
            foto.update(parcial)
        else:
            foto[pasta] = _entrada_de_pesado()
    return foto


def _pesados_da_foto(foto: _Foto) -> frozenset[str]:
    """Os caminhos que a foto do começo não percorreu."""
    return frozenset(c for c, (_m, _t, r) in foto.items() if r == _CANARIO_PESADO)


def _fotografar_tudo(antes: _Foto | None = None) -> _Foto:
    """A foto das árvores que reprovam; `antes` é a do começo e fixa os pesados."""
    pesados = _pesados_da_foto(antes) if antes is not None else None
    foto: _Foto = {}
    for raiz in _canario_raizes():
        foto.update(_fotografar_arvore(raiz, pesados))
    return foto


def _fotografar_tudo_de_aviso(antes: _Foto | None = None) -> _Foto:
    """A foto das árvores que só avisam; `antes` fixa os pesados, como acima."""
    pesados = _pesados_da_foto(antes) if antes is not None else None
    foto: _Foto = {}
    for raiz in _canario_raizes_de_aviso():
        foto.update(_fotografar_arvore(raiz, pesados))
    return foto


def _relato_do_canario(foto: _Foto, raizes: list[Path]) -> list[str]:
    """Uma linha por árvore com pesado ou link para fora; vazio se não houver."""
    linhas: list[str] = []
    for raiz in raizes:
        prefixo = str(raiz)
        pesados: list[str] = []
        fora: list[str] = []
        for caminho, (_m, _t, resumo) in sorted(foto.items()):
            if caminho != prefixo and not caminho.startswith(prefixo + os.sep):
                continue
            nome = raiz.name if caminho == prefixo else os.path.relpath(caminho, prefixo)
            if resumo == _CANARIO_PESADO:
                pesados.append(nome)
            elif resumo.startswith(_CANARIO_LINK):
                alvo = resumo[len(_CANARIO_LINK):]
                if alvo != prefixo and not alvo.startswith(prefixo + os.sep):
                    fora.append(nome)
        if not pesados and not fora:
            continue
        nomes = [*pesados, *fora][:_CANARIO_LIMITE_NOMES]
        onde = os.path.relpath(prefixo, os.path.expanduser("~"))
        linhas.append(
            f"  - {onde}: {len(pesados)} pasta(s) pesada(s) e "
            f"{len(fora)} link(s) para fora ({', '.join(nomes)})"
        )
    return linhas


def _deltas_do_canario(
    antes: dict[str, tuple[int, int, str]], depois: dict[str, tuple[int, int, str]]
) -> list[str]:
    """Lista legível do que mudou entre as duas fotos (vazia = nada mudou)."""
    deltas: list[str] = []
    deltas.extend(f"CRIADO   {c}" for c in sorted(set(depois) - set(antes)))
    deltas.extend(f"APAGADO  {c}" for c in sorted(set(antes) - set(depois)))
    for caminho in sorted(set(antes) & set(depois)):
        (_mt_a, tam_a, resumo_a) = antes[caminho]
        (_mt_d, tam_d, resumo_d) = depois[caminho]
        if (tam_a, resumo_a) == (tam_d, resumo_d):
            continue
        detalhe = f"tamanho {tam_a}->{tam_d}" if tam_a != tam_d else "conteúdo"
        deltas.append(f"MUDADO   {caminho} ({detalhe})")
    return deltas


_BERCO_PREFIXO = "hefesto-berco-"

_BERCO_DESLIGADO_ENV = "HEFESTO_SEM_BERCO_TMP"

_BERCO: list[Path] = []

_TMP_REAL: list[Path] = []

_VARS_DE_TMP = ("TMPDIR", "TMP", "TEMP")

_TMP_ENV_ANTES: dict[str | None, str | None] = {}

_SESSAO_REAL: list[int] = []

_TMP_ANTES: set[str] = set()

_BERCO_LIMITE_RELATO = 8


def _berco_ligado() -> bool:
    return os.environ.get(_BERCO_DESLIGADO_ENV) != "1"


def berco() -> Path | None:
    """O berço desta sessão, ou None quando o desvio não está armado."""
    return _BERCO[0] if _BERCO else None


def _pid_vivo(pid: int) -> bool:
    """True quando existe processo com este pid."""
    try:
        os.kill(pid, 0)
    except ProcessLookupError:
        return False
    except PermissionError:
        return True
    except OSError:  # pragma: no cover — pid inválido não chega aqui
        return True
    return True


def _pid_do_berco(nome: str) -> int | None:
    """O pid gravado no nome do berço, ou None quando o nome NÃO é de berço."""
    if not nome.startswith(_BERCO_PREFIXO):
        return None
    resto = nome[len(_BERCO_PREFIXO) :]
    if not resto.isdigit():
        return None
    return int(resto)


def _bercos_orfaos(raiz: Path) -> list[Path]:
    """Berços de sessões MORTAS sob `raiz`, do mais antigo para o mais novo."""
    orfaos: list[Path] = []
    try:
        entradas = sorted(raiz.iterdir())
    except OSError:
        return orfaos
    for entrada in entradas:
        pid = _pid_do_berco(entrada.name)
        if pid is None or not entrada.is_dir() or entrada.is_symlink():
            continue
        if _pid_vivo(pid):
            continue
        orfaos.append(entrada)
    return orfaos


def _armar_berco(session: Any) -> None:
    """Cria o berço e desvia `tempfile` + `TMPDIR` para dentro dele."""
    if not _berco_ligado() or _BERCO:
        return
    _fixar_basetemp_do_pytest(session)
    raiz = Path(tempfile.gettempdir())
    _TMP_REAL.append(raiz)
    with contextlib.suppress(OSError):
        _TMP_ANTES.update(os.listdir(raiz))
    for orfao in _bercos_orfaos(raiz):
        shutil.rmtree(orfao, ignore_errors=True)
    destino = raiz / f"{_BERCO_PREFIXO}{os.getpid()}"
    if destino.exists():
        shutil.rmtree(destino, ignore_errors=True)
    try:
        destino.mkdir(mode=0o700)
    except OSError:  # pragma: no cover — /tmp sem escrita derruba a suíte antes
        return
    _BERCO.append(destino)
    _SESSAO_REAL.append(id(session))
    _TMP_ENV_ANTES[None] = tempfile.tempdir
    tempfile.tempdir = str(destino)
    for var in _VARS_DE_TMP:
        _TMP_ENV_ANTES[var] = os.environ.get(var)
        os.environ[var] = str(destino)


def _fixar_basetemp_do_pytest(session: Any) -> None:
    """Resolve (e cacheia) o `basetemp` do pytest ANTES do desvio do `TMPDIR`."""
    fabrica = getattr(getattr(session, "config", None), "_tmp_path_factory", None)
    if fabrica is None:  # pragma: no cover — pytest sempre publica a fábrica
        return
    with contextlib.suppress(Exception):
        fabrica.getbasetemp()


def _nascidos_fora_do_berco() -> list[str]:
    """Nomes de primeiro nível que apareceram no `/tmp` REAL durante a sessão."""
    if not _TMP_REAL:
        return []
    nosso = berco()
    try:
        agora = set(os.listdir(_TMP_REAL[0]))
    except OSError:  # pragma: no cover
        return []
    novos = agora - _TMP_ANTES
    if nosso is not None:
        novos.discard(nosso.name)
    lar = lar_de_sessao()
    if lar is not None:
        novos.discard(lar.name)
    for nosso in (som_de_mentira(), lancador_de_mentira()):
        if nosso is not None:
            novos.discard(nosso.name)
    return sorted(novos)


def _varrer_berco(session: Any, exitstatus: int) -> None:
    """Fim de sessão: o berço inteiro sai, e o que havia nele é relatado."""
    nosso = berco()
    if nosso is None:
        return
    if _SESSAO_REAL and id(session) not in _SESSAO_REAL:
        return
    try:
        restos = sorted(p.name for p in nosso.iterdir())
    except OSError:  # pragma: no cover
        restos = []

    if exitstatus != 0 and restos:
        _escrever_no_terminal(session, [
            "",
            f"BERCO-DE-TMP-01: sessão vermelha — o berço FICA, com {len(restos)} "
            f"entrada(s): {nosso}",
        ])
    else:
        shutil.rmtree(nosso, ignore_errors=True)
        if restos:
            mostrados = restos[:_BERCO_LIMITE_RELATO]
            restam = len(restos) - len(mostrados)
            cauda = f" (+{restam})" if restam > 0 else ""
            _escrever_no_terminal(session, [
                "",
                f"BERCO-DE-TMP-01: a suíte deixaria {len(restos)} entrada(s) em "
                f"/tmp; nasceram no berço e saíram com ele: "
                f"{', '.join(mostrados)}{cauda}",
            ])

    _BERCO.clear()
    tempfile.tempdir = _TMP_ENV_ANTES.get(None)
    for var, valor in _TMP_ENV_ANTES.items():
        if var is None:
            continue
        if valor is None:
            os.environ.pop(var, None)
        else:
            os.environ[var] = valor
    _TMP_ENV_ANTES.clear()

    fora = _nascidos_fora_do_berco()
    if fora:
        mostrados = fora[:_BERCO_LIMITE_RELATO]
        restam = len(fora) - len(mostrados)
        cauda = f" (+{restam})" if restam > 0 else ""
        _escrever_no_terminal(session, [
            f"BERCO-DE-TMP-01 (aviso, não é portão): apareceram em "
            f"{_TMP_REAL[0]} durante a sessão, FORA do berço: "
            f"{', '.join(mostrados)}{cauda}",
            "  A máquina dela também escreve em /tmp — mas se algum destes tem "
            "cara de teste,",
            "  é caminho FIXO escrito à mão num teste, e caminho fixo ignora o "
            "TMPDIR do berço.",
        ])


# postos 2 a 5 e empurrando os DualSense REAIS dela para 6, 7 e 8 — e

_LAR_DESLIGADO_ENV = "HEFESTO_SEM_LAR_DE_SESSAO"

_LAR_PREFIXO = "hefesto-lar-de-sessao-"

_LAR_DE_SESSAO: list[Path] = []

_LAR_REAL: list[Path] = []

_LAR_ENV_ANTES: dict[str, str | None] = {}

_LAR_ENV_DEPOIS: dict[str, str] = {}

_VARS_DO_LAR: tuple[tuple[str, tuple[str, ...]], ...] = (
    ("HOME", ()),
    ("XDG_CONFIG_HOME", (".config",)),
    ("XDG_DATA_HOME", (".local", "share")),
    ("XDG_CACHE_HOME", (".cache",)),
    ("XDG_STATE_HOME", (".local", "state")),
)

_NOME_DO_PRODUTO = "hefesto-dualsense4unix"

_DIRS_DO_PRODUTO: tuple[tuple[str, ...], ...] = (
    (".config", _NOME_DO_PRODUTO),
    (".local", "share", _NOME_DO_PRODUTO),
    (".local", "state", _NOME_DO_PRODUTO),
    (".cache", _NOME_DO_PRODUTO),
)

_RAMOS_DO_PRODUTO: frozenset[tuple[str, ...]] = frozenset(
    folha[:n] for folha in _DIRS_DO_PRODUTO for n in range(1, len(folha))
)

_SESSAO_DO_LAR: list[int] = []


def _lar_ligado() -> bool:
    return os.environ.get(_LAR_DESLIGADO_ENV) != "1"


def lar_real() -> Path:
    """O `$HOME` de verdade — o de antes do desvio, quando ele está armado."""
    if _LAR_REAL:
        return _LAR_REAL[0]
    return Path(os.environ.get("HOME") or os.path.expanduser("~"))


def lar_de_sessao() -> Path | None:
    """O lar de mentira desta sessão, ou None quando o desvio não está armado."""
    return _LAR_DE_SESSAO[0] if _LAR_DE_SESSAO else None


def _lares_orfaos(raiz: Path) -> list[Path]:
    """Lares de sessões MORTAS — mesmo critério por pid do `_bercos_orfaos`."""
    orfaos: list[Path] = []
    with contextlib.suppress(OSError):
        for entrada in raiz.iterdir():
            nome = entrada.name
            if not nome.startswith(_LAR_PREFIXO):
                continue
            cauda = nome[len(_LAR_PREFIXO):]
            if not cauda.isdigit():
                continue
            if not entrada.is_dir() or entrada.is_symlink():
                continue
            if _pid_vivo(int(cauda)):
                continue
            orfaos.append(entrada)
    return orfaos


def _espelhar_o_lar(
    real: Path, destino: Path, prefixo: tuple[str, ...] = ()
) -> None:
    """Espelha `real` em `destino`: symlink em tudo, menos nos quatro do produto."""
    destino.mkdir(mode=0o700, parents=True, exist_ok=True)
    with contextlib.suppress(OSError):
        for entrada in sorted(real.iterdir()):
            caminho = (*prefixo, entrada.name)
            if caminho in _DIRS_DO_PRODUTO:
                continue
            if caminho in _RAMOS_DO_PRODUTO:
                _espelhar_o_lar(entrada, destino / entrada.name, caminho)
                continue
            with contextlib.suppress(OSError):
                (destino / entrada.name).symlink_to(entrada)
    if prefixo:
        return
    for folha in _DIRS_DO_PRODUTO:
        with contextlib.suppress(OSError):
            destino.joinpath(*folha).mkdir(mode=0o700, parents=True, exist_ok=True)


def _destino_no_duble(var: str, padrao: tuple[str, ...], duble: Path) -> str:
    """Para onde `var` passa a apontar dentro do dublê."""
    real = lar_real()
    if not padrao:
        return str(duble)
    bruto = (os.environ.get(var) or "").strip()
    if not bruto:
        return str(duble.joinpath(*padrao))
    atual = Path(bruto)
    if atual.is_relative_to(real):
        return str(duble / atual.relative_to(real))
    proprio = duble / f"fora-do-lar-{var.lower()}"
    if not proprio.exists():
        proprio.mkdir(mode=0o700, parents=True, exist_ok=True)
        with contextlib.suppress(OSError):
            for entrada in sorted(atual.iterdir()):
                if entrada.name == _NOME_DO_PRODUTO:
                    continue
                with contextlib.suppress(OSError):
                    (proprio / entrada.name).symlink_to(entrada)
        with contextlib.suppress(OSError):
            (proprio / _NOME_DO_PRODUTO).mkdir(mode=0o700, exist_ok=True)
    return str(proprio)


def _aplicar_o_lar_de_sessao() -> None:
    """Aponta `HOME` e os quatro `XDG_*` para dentro do lar de mentira."""
    destino = lar_de_sessao()
    if destino is None:
        return
    for var, valor in _LAR_ENV_DEPOIS.items():
        os.environ[var] = valor


def _armar_lar_de_sessao(session: Any) -> None:
    """Cria o lar de mentira e desvia `HOME` + os quatro `XDG_*` para dentro."""
    if not _lar_ligado() or _LAR_DE_SESSAO:
        return
    raiz = _TMP_REAL[0] if _TMP_REAL else Path(tempfile.gettempdir())
    for orfao in _lares_orfaos(raiz):
        shutil.rmtree(orfao, ignore_errors=True)
    destino = raiz / f"{_LAR_PREFIXO}{os.getpid()}"
    shutil.rmtree(destino, ignore_errors=True)
    try:
        _espelhar_o_lar(lar_real(), destino)
    except OSError:  # pragma: no cover — /tmp sem escrita derruba a suíte antes
        shutil.rmtree(destino, ignore_errors=True)
        return
    _LAR_DE_SESSAO.append(destino)
    _SESSAO_DO_LAR.append(id(session))
    for var, padrao in _VARS_DO_LAR:
        _LAR_ENV_ANTES[var] = os.environ.get(var)
        _LAR_ENV_DEPOIS[var] = _destino_no_duble(var, padrao, destino)
    _aplicar_o_lar_de_sessao()
    atexit.register(_fechar_o_lar_de_sessao)


def _devolver_o_ambiente_real() -> None:
    """Repõe os cinco valores de antes do desvio. Não apaga o lar de mentira."""
    for var, valor in _LAR_ENV_ANTES.items():
        if valor is None:
            os.environ.pop(var, None)
        else:
            os.environ[var] = valor


@contextlib.contextmanager
def _com_o_ambiente_real(session: Any) -> Iterator[None]:
    """Devolve o `$HOME` real SÓ pelo tempo dos portões de fim de sessão."""
    if not _LAR_DE_SESSAO or id(session) not in _SESSAO_DO_LAR:
        yield
        return
    _devolver_o_ambiente_real()
    try:
        yield
    finally:
        _aplicar_o_lar_de_sessao()


def _fechar_o_lar_de_sessao() -> None:
    """`atexit`: devolve o ambiente de verdade e leva o lar de mentira embora."""
    with contextlib.suppress(Exception):
        _devolver_o_ambiente_real()
    _LAR_ENV_ANTES.clear()
    _LAR_ENV_DEPOIS.clear()
    destino = lar_de_sessao()
    _LAR_DE_SESSAO.clear()
    _SESSAO_DO_LAR.clear()
    if destino is not None:
        shutil.rmtree(destino, ignore_errors=True)


_MODULO_DA_IDENTIDADE = "hefesto_dualsense4unix.daemon.subsystems.identity"


def _descartar_registro_de_identidade() -> None:
    """Descarta `identity._registry`, se o módulo estiver carregado."""
    modulo = sys.modules.get(_MODULO_DA_IDENTIDADE)
    if modulo is None:
        return
    descartar = getattr(modulo, "reset_identity_registry", None)
    if descartar is None:
        return
    with contextlib.suppress(Exception):
        descartar()


def pytest_sessionstart(session: Any) -> None:
    """CANARIO-FS-01: primeira fotografia dos diretórios REAIS da usuária."""
    global _CANARIO_ARMADO, _FAIXA_ARMADA
    if not _LAR_REAL:
        _LAR_REAL.append(Path(os.environ.get("HOME") or os.path.expanduser("~")))
    _armar_berco(session)
    _armar_som_de_mentira()
    _armar_lancador_de_mentira(session)
    if _faixa_ligada():
        _FAIXA_DIR_REAL.append(_faixa_config_dir_real())
        _FAIXA_NO_INICIO.update(_faixa_enderecos())
        _FAIXA_ARMADA = True
    _armar_vigia_de_aparelho()
    _INICIO_DA_SESSAO.append(datetime.datetime.now().strftime("%Y-%m-%d %H:%M:%S"))
    if _canario_ligado():
        _CANARIO_FOTO_INICIAL.update(_fotografar_tudo())
        _CANARIO_FOTO_AVISO.update(_fotografar_tudo_de_aviso())
        _CANARIO_ARMADO = True
    _armar_lar_de_sessao(session)


def _escrever_no_terminal(session: Any, linhas: list[str]) -> None:
    """Imprime pelo terminalreporter quando ele existe; senão, no stdout."""
    relator = None
    config = getattr(session, "config", None)
    gerenciador = getattr(config, "pluginmanager", None)
    if gerenciador is not None:
        relator = gerenciador.get_plugin("terminalreporter")
    for linha in linhas:
        if relator is not None:
            relator.write_line(linha)
        else:  # pragma: no cover — pytest sempre tem terminalreporter
            print(linha)


def pytest_sessionfinish(session: Any, exitstatus: int) -> None:
    """Sob ``HEFESTO_EXIGE_GTK_REAL=1``, pulo por falta de GTK reprova o run."""
    try:
        with _com_o_ambiente_real(session):
            _sessionfinish_das_guardas(session)
    finally:
        _varrer_berco(session, getattr(session, "exitstatus", exitstatus))


_VIGIA_LIMITE_RELATO = 12


def _vigia_no_fim_da_sessao(session: Any) -> None:
    """O portão da vigia, cobrindo a sessão INTEIRA, e o aviso do kernel."""
    vigia = vigia_da_sessao()
    problemas = problemas_da_vigia(vigia)
    if problemas:
        mostrados = problemas[:_VIGIA_LIMITE_RELATO]
        restam = len(problemas) - len(mostrados)
        _escrever_no_terminal(session, [
            "",
            "VIGIA-DE-APARELHO-01: a suíte bateu na porta do kernel "
            f"({len(problemas)} vez(es)) — nó de entrada de VERDADE na máquina "
            "de quem roda:",
            *[f"  - {p}" for p in mostrados],
            *([f"  ... e mais {restam}"] if restam > 0 else []),
            "  Um teste que precisa de aparelho de entrada precisa de um DUBLÊ:",
            "  veja `_nenhum_uinput_de_verdade` neste conftest. Em 20/08/2026",
            "  isto custou 1289 nós num dia e a tela cheia dela no meio do jogo.",
        ])
        session.exitstatus = 1

    if not _INICIO_DA_SESSAO:
        return
    nascidos = nascimentos_no_journal(_INICIO_DA_SESSAO[0])
    if not nascidos:
        return
    nossos = [
        n for n in nascidos if "Hefesto" in n and n != NOME_DO_NO_DE_MORDIDA
    ]
    if not nossos:
        return
    contados = sorted({(n, nossos.count(n)) for n in nossos})
    _escrever_no_terminal(session, [
        "",
        "VIGIA-DE-APARELHO-01 (aviso, não é portão): o kernel registrou "
        f"{len(nossos)} nó(s) com nome do produto durante esta sessão:",
        *[f"  - {n} x{q}" for n, q in contados[:_VIGIA_LIMITE_RELATO]],
        "  Se nenhum teste apareceu no livro acima, quase sempre é o daemon "
        "VIVO dela criando vpad (ela joga enquanto a suíte roda).",
        "  Vale investigar quando a suíte tiver subido um processo FILHO do "
        "produto: é o único caminho que a vigia da porta não enxerga.",
    ])


def _sessionfinish_das_guardas(session: Any) -> None:
    """GUARDA-GI-REAL-01, ARVORE-CONGELADA-01, FAIXA-NO-BERCO-01, CANARIO-FS-01."""
    if EXIGE_GTK_REAL and _MODULOS_PULADOS_SEM_GI:
        session.exitstatus = 1

    deltas_produto = _deltas_do_congelado()
    if deltas_produto:
        mostrados = deltas_produto[:_CONGELADA_LIMITE_RELATO]
        restam = len(deltas_produto) - len(mostrados)
        _escrever_no_terminal(session, [
            "",
            "ARVORE-CONGELADA-01: o PRODUTO mudou durante esta sessão "
            f"({len(deltas_produto)} arquivo(s)):",
            *[f"  - {d}" for d in mostrados],
            *([f"  ... e mais {restam}"] if restam > 0 else []),
            "  A bancada mediu a foto do início; a árvore de hoje é outra. Este",
            "  run NÃO decide nada — nem o verde, nem o vermelho. Rode de novo",
            "  com a árvore parada (um mutador por vez, ou um git worktree por",
            "  agente) antes de gravar qualquer nota que dependa dele.",
        ])
        session.exitstatus = 1

    _vigia_no_fim_da_sessao(session)
    _lancador_no_fim_da_sessao(session)

    _faixa_no_fim_da_sessao(session)

    if not _canario_ligado() or not _CANARIO_ARMADO:
        return

    foto_aviso = _fotografar_tudo_de_aviso(_CANARIO_FOTO_AVISO)
    deltas_aviso = _deltas_do_canario(_CANARIO_FOTO_AVISO, foto_aviso)
    if deltas_aviso:
        mostrados = deltas_aviso[:_CANARIO_LIMITE_AVISO]
        restam = len(deltas_aviso) - len(mostrados)
        _escrever_no_terminal(session, [
            "",
            "CANARIO-FS-01 (aviso, não é portão): mudou durante a sessão, em "
            f"árvore que a suíte não devia provocar ({len(deltas_aviso)}):",
            *[f"  - {d}" for d in mostrados],
            *([f"  ... e mais {restam}"] if restam > 0 else []),
            "  Quase sempre isto NÃO é a suíte escrevendo: é o daemon VIVO dela",
            "  reagindo ao que a suíte faz em /dev/input (procure no journal por",
            "  `backend_hotplug_reconcile trigger=input_dir_change`). Ver a",
            "  SUITE-QUE-SUJA-O-JORNAL-01. Nada aqui é restaurado: escrita da",
            "  daemon dela é trabalho real, e desfazê-la seria o dano maior.",
        ])

    foto_fim = _fotografar_tudo(_CANARIO_FOTO_INICIAL)
    relato = _relato_do_canario(
        {**foto_aviso, **foto_fim},
        [*_canario_raizes(), *_canario_raizes_de_aviso()],
    )
    if relato:
        _escrever_no_terminal(session, [
            "",
            "CANARIO-FS-01 (relato, não é portão): pasta pesada ou link para fora:",
            *relato,
            "  O canário não entrou aqui: o state do produto não guarda a casa, "
            "e a casa mora em ~/.local/state/hefesto-casa/.",
        ])

    deltas = _deltas_do_canario(_CANARIO_FOTO_INICIAL, foto_fim)
    if not deltas:
        return
    linhas = [
        "",
        "CANARIO-FS-01: a suíte ESCREVEU nos diretórios reais da usuária "
        f"({len(deltas)} mudança(s)):",
        *[f"  - {d}" for d in deltas],
        "  Um teste hermético não deixa rastro em $HOME. Procure constante de",
        "  módulo com Path.home() avaliada no import (monkeypatch de HOME não a",
        "  alcança) — mova para função e injete o caminho.",
        f"  Se o daemon/GUI estava rodando ao lado, {_CANARIO_DESLIGADO_ENV}=1 "
        "desliga este canário.",
    ]
    _escrever_no_terminal(session, linhas)
    session.exitstatus = 1


_CONGELAR: tuple[str, ...] = (
    "scripts",
    "assets/bluetooth",
    "assets/bluez-backport",
    "flatpak",
    "packaging/arch",
    "packaging/debian",
    "packaging/fedora",
    "packaging/nix",
    ".github/workflows",
    "install.sh",
    "uninstall.sh",
)

_CONGELAR_IGNORAR = ("__pycache__", "target", ".flatpak-builder", "build", "*.pyc")


def _e_lixo_de_build(relativo: Path) -> bool:
    """O caminho cai em `_CONGELAR_IGNORAR`? Então não é produto, nos DOIS lados."""
    return any(
        fnmatch.fnmatch(parte, padrao)
        for parte in relativo.parts
        for padrao in _CONGELAR_IGNORAR
    )

_ARVORE_CONGELADA: list[Path] = []


def arvore_congelada() -> Path:
    """Cópia só-leitura da árvore, tirada UMA VEZ por sessão de `pytest`."""
    if _ARVORE_CONGELADA:
        return _ARVORE_CONGELADA[0]

    import atexit
    import shutil
    import tempfile

    origem_raiz = Path(__file__).resolve().parents[1]
    destino = Path(tempfile.mkdtemp(prefix="hefesto-arvore-congelada-"))
    atexit.register(shutil.rmtree, destino, True)
    ignorar = shutil.ignore_patterns(*_CONGELAR_IGNORAR)
    for relativo in _CONGELAR:
        origem = origem_raiz / relativo
        alvo = destino / relativo
        if origem.is_dir():
            alvo.parent.mkdir(parents=True, exist_ok=True)
            shutil.copytree(origem, alvo, ignore=ignorar, symlinks=True)
        elif origem.is_file():
            alvo.parent.mkdir(parents=True, exist_ok=True)
            shutil.copy2(origem, alvo)
    _ARVORE_CONGELADA.append(destino)
    return destino


_CONGELADA_LIMITE_RELATO = 20


def _deltas_do_congelado() -> list[str]:
    """O produto MUDOU entre a foto e o fim da sessão? Diga quais arquivos."""
    if not _ARVORE_CONGELADA:
        return []
    congelada = _ARVORE_CONGELADA[0]
    viva = Path(__file__).resolve().parents[1]
    deltas: list[str] = []
    for copia in sorted(congelada.rglob("*")):
        if not copia.is_file():
            continue
        relativo = copia.relative_to(congelada)
        if _e_lixo_de_build(relativo):
            continue
        atual = viva / relativo
        if not atual.is_file():
            deltas.append(f"APAGADO  {relativo}")
            continue
        try:
            if atual.read_bytes() != copia.read_bytes():
                deltas.append(f"MUDADO   {relativo}")
                continue
        except OSError:
            deltas.append(f"ILEGÍVEL {relativo}")
            continue
        if (atual.stat().st_mode & 0o777) != (copia.stat().st_mode & 0o777):
            deltas.append(f"MODO     {relativo}")
    return deltas


PORTAS_DE_APARELHO: tuple[str, ...] = ("/dev/uinput", "/dev/uhid")

FABRICAS_DE_APARELHO: tuple[tuple[str, str], ...] = (
    ("uinput", "Device"),
    ("evdev", "UInput"),
    ("evdev.uinput", "UInput"),
)

_VIGIA_DESLIGADA_ENV = "HEFESTO_SEM_VIGIA_APARELHO"


@dataclass(frozen=True)
class NascimentoDeAparelho:
    """Uma passagem pela porta: quem tentou, por onde, com que nome."""

    quem: str
    porta: str
    detalhe: str = ""

    def __str__(self) -> str:
        cauda = f" ({self.detalhe})" if self.detalhe else ""
        return f"{self.porta}{cauda} <- {self.quem}"


class AparelhoRecusadoError(PermissionError):
    """A porta fechada, e ela é ``OSError`` de propósito."""


class VigiaDeAparelho:
    """Fica nas portas do kernel: registra quem passa e, por padrão, recusa."""

    def __init__(self, *, recusar: bool = True) -> None:
        self.livro: list[NascimentoDeAparelho] = []
        self.quem = "<coleta ou fixture de sessão>"
        self.recusar = recusar
        self.originais: dict[str, Any] = {}
        self._desfazer: list[Callable[[], None]] = []


    def registrar(self, porta: str, detalhe: str = "") -> None:
        self.livro.append(NascimentoDeAparelho(self.quem, porta, detalhe))

    def envolver_fabrica(self, original: Any, porta: str) -> Callable[..., Any]:
        """A fábrica guardada. Devolve um chamável com a MESMA assinatura."""

        def _porta(*args: Any, **kwargs: Any) -> Any:
            nome = kwargs.get("name")
            if not isinstance(nome, str):
                nome = next((a for a in args[1:] if isinstance(a, str)), "")
            self.registrar(porta, f"name={nome!r}" if nome else "")
            if self.recusar:
                raise AparelhoRecusadoError(
                    errno.EACCES, f"VIGIA-DE-APARELHO-01: {porta} recusado sob teste"
                )
            return original(*args, **kwargs)

        _porta.vigia_de_aparelho = porta  # type: ignore[attr-defined]
        return _porta

    def envolver_os_open(self, original: Callable[..., int]) -> Callable[..., int]:
        """O `os.open` guardado — só olha os dois nós, o resto passa reto."""

        def _abrir(caminho: Any, flags: int, *args: Any, **kwargs: Any) -> int:
            try:
                texto = os.fsdecode(caminho)
            except (TypeError, ValueError):
                texto = ""
            if texto in PORTAS_DE_APARELHO:
                self.registrar(texto, "os.open")
                if self.recusar:
                    raise AparelhoRecusadoError(
                        errno.EACCES, f"VIGIA-DE-APARELHO-01: {texto} recusado sob teste"
                    )
            return original(caminho, flags, *args, **kwargs)

        _abrir.vigia_de_aparelho = "os.open"  # type: ignore[attr-defined]
        return _abrir


    def instalar(self) -> "VigiaDeAparelho":
        """Põe a vigia nas três portas que existirem neste ambiente."""
        self.originais["os.open"] = os.open
        os.open = self.envolver_os_open(os.open)  # type: ignore[assignment]
        self._desfazer.append(
            lambda: setattr(os, "open", self.originais["os.open"])
        )
        for modulo, atributo in FABRICAS_DE_APARELHO:
            self._instalar_fabrica(modulo, atributo)
        return self

    def _instalar_fabrica(self, modulo: str, atributo: str) -> None:
        try:
            alvo = __import__(modulo, fromlist=[atributo])
            original = getattr(alvo, atributo)
        except Exception:
            return
        porta = f"{modulo}.{atributo}"
        self.originais[porta] = original
        setattr(alvo, atributo, self.envolver_fabrica(original, porta))
        self._desfazer.append(lambda: setattr(alvo, atributo, original))

    def desinstalar(self) -> None:
        for desfazer in reversed(self._desfazer):
            with contextlib.suppress(Exception):
                desfazer()
        self._desfazer.clear()


_VIGIA: list[VigiaDeAparelho] = []

_INICIO_DA_SESSAO: list[str] = []

NOME_DO_NO_DE_MORDIDA = "Hefesto MORDIDA de teste (VIGIA-DE-APARELHO-01)"


def _vigia_ligada() -> bool:
    return os.environ.get(_VIGIA_DESLIGADA_ENV) != "1"


def vigia_da_sessao() -> VigiaDeAparelho | None:
    """A vigia desta sessão, ou None quando ela não está armada."""
    return _VIGIA[0] if _VIGIA else None


def _armar_vigia_de_aparelho() -> None:
    if not _vigia_ligada() or _VIGIA:
        return
    _VIGIA.append(VigiaDeAparelho().instalar())


def maior_no_de_entrada_vivo() -> int:
    """O maior `inputN` VIVO agora (-1 quando não há nenhum)."""
    maior = -1
    try:
        entradas = os.listdir("/sys/class/input")
    except OSError:
        return maior
    for nome in entradas:
        if not nome.startswith("input") or not nome[5:].isdigit():
            continue
        maior = max(maior, int(nome[5:]))
    return maior


def nascimentos_no_journal(desde: str) -> list[str] | None:
    """Os nomes dos aparelhos de entrada que o KERNEL registrou desde `desde`."""
    import subprocess

    try:
        saida = subprocess.run(
            ["journalctl", "-k", "--since", desde, "--no-pager"],
            capture_output=True,
            text=True,
            timeout=20,
        )
    except (OSError, subprocess.SubprocessError):
        return None
    if saida.returncode != 0:
        return None
    nomes: list[str] = []
    for linha in saida.stdout.splitlines():
        marca = "kernel: input: "
        if marca not in linha:
            continue
        nomes.append(linha.split(marca, 1)[1].split(" as ", 1)[0].strip())
    return nomes


def nomes_de_aparelhos_vivos() -> list[str]:
    """Os nomes dos aparelhos de entrada VIVOS agora, lidos do sysfs."""
    nomes: list[str] = []
    raiz = Path("/sys/class/input")
    try:
        entradas = sorted(raiz.iterdir())
    except OSError:
        return nomes
    for entrada in entradas:
        if not entrada.name.startswith("input") or not entrada.name[5:].isdigit():
            continue
        with contextlib.suppress(OSError):
            nomes.append((entrada / "name").read_text().strip())
    return nomes


def problemas_da_vigia(vigia: VigiaDeAparelho | None) -> list[str]:
    """A lista que o portão lê: uma linha por passagem na porta (vazia = limpo)."""
    if vigia is None:
        return []
    return [str(n) for n in vigia.livro]


@pytest.fixture(scope="session")
def repo_root() -> Path:
    return Path(__file__).resolve().parents[1]


def _o_produto_nao_roda_neste_ambiente(erro: ModuleNotFoundError) -> bool:
    """O job LEVE do CI: o produto não importa aqui, e não há o que blindar."""
    import importlib.util

    nome = (erro.name or "").split(".")[0]
    return bool(nome) and importlib.util.find_spec(nome) is None


@pytest.fixture(autouse=True)
def _hefesto_fake_env(monkeypatch: pytest.MonkeyPatch, tmp_path: Path) -> None:
    """Ativa HEFESTO_DUALSENSE4UNIX_FAKE=1 e ISOLA os diretórios XDG em todo teste.

    FAKE=1 — garantia defensiva: subsystems que fazem probing de hardware real
    (TouchpadReader enumerando evdev, ex.) devem pular a inicialização quando o
    flag está presente — caso contrário testes em ambiente dev com DualSense
    conectado sofrem latência extra (>60ms) que empurra janelas de teste curtas
    para fora do budget. FakeController já é o padrão nas suítes; o env var apenas
    torna esse contrato explícito para outros módulos consumirem.

    BUG-TEST-CONFIG-LEAK-01 — isola XDG_CONFIG_HOME (e data/cache/state/runtime)
    num tmp por teste. `utils.xdg_paths.config_dir()` resolve via `platformdirs`,
    que respeita `XDG_CONFIG_HOME`; sem isolamento, qualquer teste que sobe o
    Daemon lia o `~/.config/hefesto-dualsense4unix` REAL do dev e herdava as flags
    de sessão (gamepad/mouse/paused), o session.json e os profiles. Numa máquina
    com a emulação de gamepad LIGADA de verdade, o daemon de teste nascia com o
    gamepad ativo e os testes de dispatch de mouse/teclado/hotkey
    (test_poll_loop_evdev_cache, test_keyboard_wire_up) falhavam — enquanto a CI
    (HOME limpo) passava. Isolar torna a suíte hermética e independente do estado
    real do dev. Testes que precisam de config própria continuam livres para
    monkeypatchar `config_dir`/`XDG_CONFIG_HOME` por cima.
    """
    if not os.environ.get("HEFESTO_DUALSENSE4UNIX_FAKE"):
        monkeypatch.setenv("HEFESTO_DUALSENSE4UNIX_FAKE", "1")
    monkeypatch.setenv("HEFESTO_EFIVARS_ROOT", str(tmp_path / ".efivars-sem-secure-boot"))
    xdg_root = tmp_path / ".xdg"
    for var, sub in (
        ("XDG_CONFIG_HOME", "config"),
        ("XDG_DATA_HOME", "data"),
        ("XDG_CACHE_HOME", "cache"),
        ("XDG_STATE_HOME", "state"),
    ):
        target = xdg_root / sub
        target.mkdir(parents=True, exist_ok=True)
        monkeypatch.setenv(var, str(target))
    # continuavam resolvendo o `$HOME` REAL do dev em qualquer chamada que não
    # e um WirePlumber real com o DualSense fixado como mic faz todo teste que
    real_home = lar_real()
    monkeypatch.setenv("RUSTUP_HOME", str(real_home / ".rustup"))
    monkeypatch.setenv("CARGO_HOME", str(real_home / ".cargo"))
    home_dir = xdg_root / "home"
    home_dir.mkdir(parents=True, exist_ok=True)
    monkeypatch.setenv("HOME", str(home_dir))
    monkeypatch.setenv("HEFESTO_DUALSENSE4UNIX_SKIP_PRESET_SEED", "1")
    monkeypatch.setenv("HEFESTO_BROKER_SOCKET", str(xdg_root / "no-broker.sock"))
    # todo teste. A vista dos externos pula pelo sysfs o nó de DualSense antes
    # dela, e só com os controles ligados. Vazio é «não achei DualSense nenhum», a resposta de
    try:
        from hefesto_dualsense4unix.core import evdev_reader
    except ModuleNotFoundError as erro:  # pragma: no cover - só no job leve do CI
        if not _o_produto_nao_roda_neste_ambiente(erro):
            raise
    else:
        sysfs_vazio = xdg_root / "sys-class-input"
        sysfs_vazio.mkdir(parents=True, exist_ok=True)
        monkeypatch.setattr(evdev_reader, "SYS_CLASS_INPUT", str(sysfs_vazio))
    from hefesto_dualsense4unix.integrations import quem_o_jogo_le

    hidraw_vazio = xdg_root / "sys-class-hidraw"
    hidraw_vazio.mkdir(parents=True, exist_ok=True)
    monkeypatch.setattr(quem_o_jogo_le, "RAIZ_CLASS_HIDRAW", str(hidraw_vazio))
    try:
        from hefesto_dualsense4unix.integrations import conexao_zumbi
    except ModuleNotFoundError as erro:  # pragma: no cover - só no job leve do CI
        if not _o_produto_nao_roda_neste_ambiente(erro):
            raise
    else:
        monkeypatch.setattr(conexao_zumbi, "RAIZ_HIDRAW", str(hidraw_vazio))
    monkeypatch.setenv("HEFESTO_BT_LOG_DEST", str(xdg_root / "bt-log.txt"))
    monkeypatch.setenv("HEFESTO_CARONA_WRAPPER", "0")
    monkeypatch.delenv("HEFESTO_AVISO_DE_VERDADE", raising=False)


@pytest.fixture(autouse=True)
def _nenhum_registro_de_identidade_atravessa() -> Iterator[None]:
    """SINGLETON-QUE-ATRAVESSA-01 — o `identity._registry` morre com o caso."""
    _descartar_registro_de_identidade()
    yield
    _descartar_registro_de_identidade()


@pytest.fixture(autouse=True)
def _nenhum_sensor_desligado_atravessa() -> Iterator[None]:
    """O `virtual_motion.REGISTRO` morre com o caso, como o `identity._registry`.

    Medido em 04/10/2026: o `reaplicar` de um perfil com o giroscópio desligado nos
    quatro (test_o_aplicar_e_a_ativacao_sao_uma_so) deixava o registro sujo, e o
    `SensorHub` de um caso seguinte fazia uma varredura a mais pelos desligados
    (test_sensores_status::test_hub_nao_reprocura_node_inexistente_a_cada_volta,
    vermelho só no lote, verde sozinho).
    """
    try:
        from hefesto_dualsense4unix.core.virtual_motion import REGISTRO
    except ModuleNotFoundError:
        yield
        return
    REGISTRO.limpar()
    yield
    REGISTRO.limpar()


def _leitores_fisicos_vivos() -> dict[int, Any]:
    """``{ident da thread: leitor}`` de todo ``PhysicalReportReader`` rodando."""
    vivos: dict[int, Any] = {}
    for fio in threading.enumerate():
        dono = getattr(getattr(fio, "_target", None), "__self__", None)
        if type(dono).__name__ == "PhysicalReportReader" and fio.ident is not None:
            vivos[fio.ident] = dono
    return vivos


@pytest.fixture(autouse=True)
def _nenhum_leitor_fisico_atravessa() -> Iterator[None]:
    """O leitor de movimento que um caso ligou, o próprio caso desliga."""
    antes = set(_leitores_fisicos_vivos())
    yield
    for ident, leitor in _leitores_fisicos_vivos().items():
        if ident not in antes:
            with contextlib.suppress(Exception):
                leitor.stop()


_EXCECOES_DO_FILHO: dict[str, type[BaseException]] = {
    "ModuleNotFoundError": ModuleNotFoundError,
    "ImportError": ImportError,
    "AttributeError": AttributeError,
}


def repassar_a_falta_do_gtk(filho: Any) -> None:
    """O processo filho que morreu pela falta do GTK devolve a mesma exceção ao pai."""
    if filho.returncode == 0:
        return
    saida = filho.stderr
    if isinstance(saida, bytes):
        saida = saida.decode("utf-8", "replace")
    linhas = [linha for linha in (saida or "").splitlines() if linha.strip()]
    if not linhas:
        return
    tipo, _, mensagem = linhas[-1].partition(": ")
    classe = _EXCECOES_DO_FILHO.get(tipo)
    if classe is None:
        return
    texto = f"{mensagem} (no processo filho)"
    if classe is ModuleNotFoundError:
        nome = mensagem.removeprefix("No module named ").strip("'\"")
        erro: BaseException = ModuleNotFoundError(texto, name=nome)
    else:
        erro = classe(texto)
    if _falta_o_gtk(erro):
        raise erro


def pytest_itemcollected(item: Any) -> None:
    """Quem empresta fixture de um módulo que PULOU pula com o motivo dele."""
    pedidos = getattr(getattr(item, "module", None), "pytest_plugins", ())
    if isinstance(pedidos, str):
        pedidos = (pedidos,)
    pulados = dict(item.config.pluginmanager.skipped_plugins)
    for nome in pedidos:
        if nome not in pulados:
            continue
        motivo = pulados[nome]
        item.add_marker(
            pytest.mark.skip(reason=f"{motivo} [as fixtures deste arquivo vêm de `{nome}`]")
        )
        caminho = item.location[0]
        if motivo.startswith("GUARDA-GI-REAL-01") and caminho not in _MODULOS_PULADOS_SEM_GI:
            _MODULOS_PULADOS_SEM_GI.append(caminho)
        return


#: Os dois transportes que o DualSense fala, nos nomes que a casa usa (são os
TRANSPORTES: tuple[str, ...] = ("usb", "bt")


def _montar_usb(common: bytes | bytearray, *, seq: int = 0) -> bytearray:
    """Adaptador de assinatura: o 0x02 não tem sequência, e `seq` é inócuo."""
    from hefesto_dualsense4unix.core import ds_output_report as rep

    return rep.build_usb_report(common)


def _medir_deslocamento_do_common(montar: Callable[..., bytearray]) -> int:
    """Onde o common de 47 bytes CAI dentro do report que a produção monta."""
    from hefesto_dualsense4unix.core import ds_output_report as rep

    marcado = bytes(range(rep.COMMON_LEN))
    posicao = bytes(montar(marcado)).find(marcado)
    if posicao < 0:
        raise RuntimeError(
            "o builder de produção não embutiu o common marcado no report — "
            "o envelope mudou de forma e a fixture de transporte não sabe medi-lo"
        )
    return posicao


@dataclass(frozen=True)
class EnvelopeDeTransporte:
    """Tudo que separa o cabo do rádio, do report id ao CRC."""

    nome: str
    nome_do_contype: str
    report_id: int
    tamanho_do_report: int
    deslocamento_do_common: int
    tag: int | None
    semente_do_crc: int | None
    tem_nibble_de_sequencia: bool
    montar: Callable[..., bytearray]

    @property
    def tipo_de_conexao(self) -> Any:
        """O membro de `ConnectionType` da pydualsense deste transporte."""
        from pydualsense.enums import ConnectionType

        return getattr(ConnectionType, self.nome_do_contype)

    def extrair_common(self, report: bytes | bytearray | list[int]) -> bytes:
        """Os 47 bytes de payload de dentro do envelope deste transporte."""
        from hefesto_dualsense4unix.core import ds_output_report as rep

        bruto = bytes(report)
        inicio = self.deslocamento_do_common
        return bruto[inicio : inicio + rep.COMMON_LEN]

    def sequencia_de(self, report: bytes | bytearray | list[int]) -> int | None:
        """O nibble de sequência do report, ou `None` onde ele não existe."""
        if not self.tem_nibble_de_sequencia:
            return None
        return (bytes(report)[1] >> 4) & 0x0F

    def crc_do_report(self, report: bytes | bytearray | list[int]) -> int | None:
        """O CRC-32 que ESTÁ gravado no report, ou `None` sem CRC."""
        if self.semente_do_crc is None:
            return None
        return int.from_bytes(bytes(report)[-4:], "little")

    def crc_esperado(self, report: bytes | bytearray | list[int]) -> int | None:
        """O CRC-32 que a receita de produção calcula, ou `None` sem CRC."""
        from hefesto_dualsense4unix.core import ds_output_report as rep

        if self.semente_do_crc is None:
            return None
        return rep.bt_crc32(bytes(report)[:-4], seed=self.semente_do_crc)

    def problemas_do_envelope(self, report: bytes | bytearray | list[int]) -> list[str]:
        """Lista legível do que está errado no envelope (vazia = está inteiro)."""
        from hefesto_dualsense4unix.core import ds_output_report as rep

        bruto = bytes(report)
        if len(bruto) != self.tamanho_do_report:
            return [
                f"{self.nome}: tamanho {len(bruto)}, esperado {self.tamanho_do_report}"
            ]
        problemas: list[str] = []
        if bruto[0] != self.report_id:
            problemas.append(
                f"{self.nome}: report id {bruto[0]:#04x}, esperado {self.report_id:#04x}"
            )
        if self.tag is not None and bruto[2] != self.tag:
            problemas.append(
                f"{self.nome}: tag {bruto[2]:#04x}, esperado {self.tag:#04x} "
                "(o firmware descarta o 0x31 sem o tag mágico)"
            )
        fim_do_common = self.deslocamento_do_common + rep.COMMON_LEN
        fim_do_corpo = len(bruto) - (0 if self.semente_do_crc is None else 4)
        if any(bruto[fim_do_common:fim_do_corpo]):
            problemas.append(f"{self.nome}: há lixo no reservado depois do common")
        if self.semente_do_crc is not None:
            gravado = self.crc_do_report(bruto)
            esperado = self.crc_esperado(bruto)
            if gravado != esperado:
                problemas.append(
                    f"{self.nome}: CRC {gravado:#010x}, esperado {esperado:#010x}"
                )
        return problemas


_ENVELOPES: dict[str, EnvelopeDeTransporte] = {}


def _medir_os_transportes() -> dict[str, EnvelopeDeTransporte]:
    from hefesto_dualsense4unix.core import ds_output_report as rep

    return {
        "usb": EnvelopeDeTransporte(
            nome="usb",
            nome_do_contype="USB",
            report_id=rep.USB_REPORT_ID,
            tamanho_do_report=rep.USB_REPORT_LEN,
            deslocamento_do_common=_medir_deslocamento_do_common(_montar_usb),
            tag=None,
            semente_do_crc=None,
            tem_nibble_de_sequencia=False,
            montar=_montar_usb,
        ),
        "bt": EnvelopeDeTransporte(
            nome="bt",
            nome_do_contype="BT",
            report_id=rep.BT_REPORT_ID,
            tamanho_do_report=rep.BT_REPORT_LEN,
            deslocamento_do_common=_medir_deslocamento_do_common(rep.build_bt_report),
            tag=rep.BT_TAG,
            semente_do_crc=rep.BT_CRC_SEED,
            tem_nibble_de_sequencia=True,
            montar=rep.build_bt_report,
        ),
    }


def envelope_de(nome: str) -> EnvelopeDeTransporte:
    """O envelope de UM transporte pelo nome (`"usb"` / `"bt"`)."""
    if not _ENVELOPES:
        _ENVELOPES.update(_medir_os_transportes())
    return _ENVELOPES[nome]


@pytest.fixture(params=["usb", "bt"])
def transporte(request: Any) -> EnvelopeDeTransporte:
    """O transporte como DIMENSÃO do caso: todo teste que a pede roda 2x."""
    return envelope_de(str(request.param))


@pytest.fixture()
def transportes() -> tuple[EnvelopeDeTransporte, ...]:
    """Os DOIS envelopes de uma vez, para o caso que os COMPARA entre si."""
    return tuple(envelope_de(nome) for nome in TRANSPORTES)


@pytest.fixture()
def fabrica_de_bancada(monkeypatch: pytest.MonkeyPatch) -> Callable[..., Any]:
    """Fábrica de `_PinnedPyDualSense` SEM device, num transporte escolhido.

    O handle nasce pelo `__init__` de produção (que não toca em hardware) e
    ganha à mão só o que o `init()` criaria DEPOIS de achar o device — as
    quatro peças de estado (`light`, `audio`, `triggerL`, `triggerR`) e o
    `conType`. Nada de estado privado escrito à mão: `_rumble_active`,
    `_volumes_audio`, `_preamp_audio` e companhia vêm do construtor de verdade,
    e é por isso que este handle não vira uma segunda implementação do produto.

    A ARMADILHA Nº 1 DESTA CASA FICA FECHADA AQUI: `prepareReport` tem um
    `except Exception` que cai no report do UPSTREAM (cujo 0x31 é malformado).
    Um atributo faltando na bancada faria o teste medir a pydualsense e chamar
    isso de produto — instrumento brigando com o produto, medição inventada.
    Com este monkeypatch, o fallback EXPLODE em vez de mentir.

    É fábrica, e não um handle pronto, porque há afirmação que só existe no
    CRUZAMENTO: comparar o report do cabo com o do rádio exige os dois handles
    vivos no mesmo caso.
    """
    from pydualsense.pydualsense import DSAudio, DSLight, DSTrigger, pydualsense

    from hefesto_dualsense4unix.core.backend_pydualsense import _PinnedPyDualSense

    def _fallback_proibido(self: Any) -> list[int]:
        raise AssertionError(
            "prepareReport caiu no fallback do upstream: a bancada está "
            "incompleta e o teste mediria a pydualsense, não o hefesto"
        )

    monkeypatch.setattr(pydualsense, "prepareReport", _fallback_proibido)

    def _fabricar(envelope: EnvelopeDeTransporte) -> Any:
        handle = _PinnedPyDualSense(b"/dev/hidraw-de-bancada", is_edge=False)
        handle.light = DSLight()
        handle.audio = DSAudio()
        handle.triggerL = DSTrigger()
        handle.triggerR = DSTrigger()
        handle.conType = envelope.tipo_de_conexao
        handle.input_report_length = envelope.tamanho_do_report
        handle.output_report_length = envelope.tamanho_do_report
        return handle

    return _fabricar


@pytest.fixture()
def ds5_de_bancada(
    transporte: EnvelopeDeTransporte, fabrica_de_bancada: Callable[..., Any]
) -> Any:
    """O handle de bancada do transporte DESTE caso (ver `fabrica_de_bancada`)."""
    return fabrica_de_bancada(transporte)


@pytest.fixture(autouse=True, scope="session")
def _nenhuma_ancora_de_usb_viva_na_suite(tmp_path_factory: pytest.TempPathFactory) -> None:
    """A suíte não enxerga o barramento USB DELA."""
    vazio = tmp_path_factory.mktemp("sysfs-sem-usb")
    try:
        from hefesto_dualsense4unix.integrations import endpoint_de_haptica
    except ModuleNotFoundError:
        return
    endpoint_de_haptica.RAIZ_DO_SYSFS = vazio


@pytest.fixture(autouse=True, scope="session")
def _nenhum_uinput_de_verdade() -> Iterator[None]:
    """A suíte NÃO cria aparelho de entrada no kernel de quem a roda.

    **O defeito, medido em 20/08/2026, e ele saiu da máquina dela.** Ela relatou
    janelas saindo de tela cheia sozinhas e suspeitou de tecla presa. O kernel
    contava outra história: **1289 nós `Hefesto - DualSense4Unix Virtual
    Keyboard` criados naquele dia**, 51 nos últimos trinta minutos, cada um
    vivendo cerca de 0,4 ms. Eram meus: cada `pytest -q` cria centenas deles, e a
    suíte rodou quinze vezes naquela sessão.

    **Por que isso derrubava a tela cheia dela sem ninguém apertar nada:** para o
    compositor Wayland cada add/remove de teclado é um re-assentamento de seat, e
    superfície em tela cheia costuma largar o fullscreen numa troca de foco. Não
    é preciso Esc nenhum — e foi atrás do Esc que eu fui primeiro, ancorada em
    duas linhas de log que depois se provaram falsas.

    **A raiz não é a suíte ser desleixada — é a máquina dela ser a mesma.** Aqui
    a máquina de desenvolvimento é a máquina em que ela joga, trabalha e assiste.
    Uma suíte que mexe em `/dev/input` não está num ambiente isolado: está
    escrevendo entrada de verdade, por cima da sessão de uma pessoa que está
    usando o computador.

    Esta fixture cobre os dois pontos que usam o **python-uinput**:
    `integrations/uinput_keyboard.py` e `integrations/uinput_mouse.py`, ambos
    fazendo `import uinput` DENTRO da função e chamando `uinput.Device(...)`.
    Por isso a troca é em `sys.modules["uinput"].Device`: pega os dois sem que
    nenhum deles precise saber que está sendo dublado.

    **Eles NÃO são os únicos pontos de criação** (a versão de 20/08 desta
    docstring dizia que sim; medido em 22/08, está errado):
    `integrations/uinput_gamepad.py` cria o vpad com `evdev.UInput`, e
    `integrations/uhid_gamepad.py` abre `/dev/uhid` com `os.open`. Nenhum dos
    dois passa por aqui — quem fica nessas portas é a VIGIA-DE-APARELHO-01
    acima, que registra e recusa.

    Custo em produção: ZERO. Isto vive só na suíte.
    """
    try:
        import uinput  # type: ignore[import-not-found]
    except ImportError:
        yield
        return

    class _AparelhoDeMentira:
        """Aceita o que o `uinput.Device` aceita, e não fala com o kernel."""

        def __init__(self, capabilities: object, name: str = "", **_kw: object) -> None:
            self.capabilities = capabilities
            self.name = name
            self.emitidos: list[tuple[object, ...]] = []

        def emit(self, *args: object, **_kw: object) -> None:
            self.emitidos.append(args)

        def syn(self) -> None:
            pass

        def destroy(self) -> None:
            pass

        def __enter__(self) -> "_AparelhoDeMentira":
            return self

        def __exit__(self, *_exc: object) -> None:
            pass

    verdadeiro = uinput.Device
    uinput.Device = _AparelhoDeMentira  # type: ignore[misc,assignment]
    try:
        yield
    finally:
        uinput.Device = verdadeiro  # type: ignore[misc]


@pytest.fixture(autouse=True, scope="session")
def _nenhum_sysfs_vivo_na_varredura_de_vpad(
    tmp_path_factory: pytest.TempPathFactory,
) -> Iterator[None]:
    """A varredura de `/sys/class/input` do `state_full` aponta para o VAZIO.

    Irmã da `_nenhum_uinput_de_verdade` logo acima, e pela mesma razão: a
    máquina de desenvolvimento é a máquina dela, e ali há vpads de VERDADE em
    `/sys/class/input`. A `integrations/no_do_vpad.resolver_no_do_vpad` roda
    dentro do `_handle_daemon_state_full`, que dezenas de testes chamam — sem
    esta fixture, cada um deles leria o sysfs vivo e o payload sob teste
    passaria a depender de quantos controles estavam ligados no momento.

    Não é só hermetismo: um teste que casasse com o `event22` de verdade dela
    estaria afirmando sobre o aparelho dela, e afirmação sobre aparelho nesta
    casa se mede na bancada, nunca na suíte.

    Vazio, e não um dublê: quem PRECISA de uma árvore forjada a monta e
    aponta as constantes para ela com `monkeypatch` (escopo de função, que
    desfaz por cima desta). O default da suíte é "não achei nó nenhum", que é
    a resposta honesta de uma máquina sem vpad.
    """
    vazio = tmp_path_factory.mktemp("sysfs-sem-vpad")
    try:
        from hefesto_dualsense4unix.integrations import no_do_vpad
    except ModuleNotFoundError as erro:  # pragma: no cover - só no job leve do CI
        if not _o_produto_nao_roda_neste_ambiente(erro):
            raise
        yield
        return

    antes = (
        no_do_vpad.RAIZ_CLASS_INPUT,
        no_do_vpad.RAIZ_DEV_INPUT,
        no_do_vpad.RAIZ_DEV,
    )
    no_do_vpad.RAIZ_CLASS_INPUT = str(vazio / "class-input")
    no_do_vpad.RAIZ_DEV_INPUT = str(vazio / "dev-input")
    no_do_vpad.RAIZ_DEV = str(vazio / "dev")
    try:
        yield
    finally:
        (
            no_do_vpad.RAIZ_CLASS_INPUT,
            no_do_vpad.RAIZ_DEV_INPUT,
            no_do_vpad.RAIZ_DEV,
        ) = antes


@pytest.fixture(autouse=True, scope="session")
def _nenhum_hidraw_vivo_na_varredura_de_som(
    tmp_path_factory: pytest.TempPathFactory,
) -> Iterator[None]:
    """A varredura de `/sys/class/hidraw` do SOM e do MIC aponta para o VAZIO.

    IRMÃ DA `_nenhum_sysfs_vivo_na_varredura_de_vpad`, E NASCEU DE UM SUSTO
    ---------------------------------------------------------------------
    Em 10/09/2026 o `AltoFalanteSubsystem` entrou no `SUBSYSTEM_REGISTRY`
    (SOM-FIADO-01). Na primeira corrida depois disso,
    `test_o_no_de_som_nao_nasce_sumidouro` imprimiu isto::

        som_radio_ponte_de_pe   arranjo=0x35  uniq=<o DualSense dela>

    **Aquele `uniq` era o controle DELA, na mesa, ligado** — o endereço real
    saiu daqui de propósito (`scripts/check_endereco_de_radio.py` pega por
    FORMA, e está certo). A suíte tinha aberto
    o hidraw do aparelho dela e subido uma ponte de som — porque
    `controles_na_lista()` varre `/sys/class/hidraw` de verdade, e agora há
    linha de produção chamando isso dentro de todo teste que sobe um `Daemon`.

    Não é só hermetismo. Esta casa tem regra: *afirmação sobre aparelho se mede
    na bancada, nunca na suíte* — e um teste que fala com o DualSense dela
    disputa o hidraw com o daemon vivo, que é exatamente a armadilha nº 3 de
    `COMO-OLHAR-A-TELA.md`.

    Vazio, e não um dublê, pelo mesmo motivo da irmã: o default é *"não achei
    controle nenhum"*, que é a resposta honesta de uma máquina sem DualSense.
    Quem precisa de uma árvore forjada a monta e aponta a constante para ela
    com `monkeypatch` de escopo de função, que desfaz por cima desta.

    O BACKEND É O TERCEIRO LEITOR (O-BACKEND-NAO-LE-O-HIDRAW-DA-MAQUINA-NA-SUITE-01,
    28/09/2026): o dedupe do `_enumerate_device_keys` perguntava o barramento de
    cada nó ao `/sys/class/hidraw` da máquina, e o «1º vence» do
    `test_enumerate_device_keys_dedupe_e_filtra` caía conforme a ordem em que os
    aparelhos dela nasceram no boot. A `backend_pydualsense.RAIZ_CLASS_HIDRAW`
    aponta para a mesma pasta vazia.
    """
    vazio = tmp_path_factory.mktemp("sysfs-sem-hidraw")
    (vazio / "hidraw").mkdir()
    try:
        from hefesto_dualsense4unix.integrations import dualsense_bt_audio
    except ModuleNotFoundError as erro:  # pragma: no cover - só no job leve do CI
        if not _o_produto_nao_roda_neste_ambiente(erro):
            raise
        yield
        return

    backend_pydualsense: Any = None
    try:
        from hefesto_dualsense4unix.core import backend_pydualsense
    except ModuleNotFoundError as erro:  # pragma: no cover - só sem o pydualsense
        if not _o_produto_nao_roda_neste_ambiente(erro):
            raise

    antes = dualsense_bt_audio._SYSFS_HIDRAW
    dualsense_bt_audio._SYSFS_HIDRAW = str(vazio / "hidraw")
    if backend_pydualsense is not None:
        antes_do_backend = backend_pydualsense.RAIZ_CLASS_HIDRAW
        backend_pydualsense.RAIZ_CLASS_HIDRAW = str(vazio / "hidraw")
    try:
        yield
    finally:
        dualsense_bt_audio._SYSFS_HIDRAW = antes
        if backend_pydualsense is not None:
            backend_pydualsense.RAIZ_CLASS_HIDRAW = antes_do_backend


@pytest.fixture(autouse=True, scope="session")
def _nenhuma_placa_de_som_viva_no_aviso_do_ucm(
    tmp_path_factory: pytest.TempPathFactory,
) -> Iterator[None]:
    """O aviso do UCM no boot lê uma lista de placas VAZIA (HAPTICA-NATIVA-01).

    `system_check._dualsenses_no_cabo_sem_ucm` lê `/proc/asound/cards` e a
    árvore UCM da máquina. Sem esta fixture, `system_warnings() == []` passaria
    ou reprovaria conforme o DualSense estivesse no cabo e o install tivesse
    rodado — uma régua que mede a máquina, não o código. Vazio, pela razão das
    irmãs acima: *"não achei placa nenhuma"* é a resposta de quem não tem
    controle. Quem precisa de placas forjadas aponta as constantes com
    `monkeypatch` de escopo de função.
    """
    vazio = tmp_path_factory.mktemp("asound-sem-placa")
    (vazio / "cards").write_text("--- no soundcards ---\n", encoding="utf-8")
    try:
        from hefesto_dualsense4unix.core import system_check
    except ModuleNotFoundError as erro:  # pragma: no cover - só no job leve do CI
        if not _o_produto_nao_roda_neste_ambiente(erro):
            raise
        yield
        return

    antes = system_check._PROC_CARDS
    system_check._PROC_CARDS = str(vazio / "cards")
    try:
        yield
    finally:
        system_check._PROC_CARDS = antes


@pytest.fixture(autouse=True, scope="session")
def _nenhum_cabo_em_espera_vivo_na_suite(
    tmp_path_factory: pytest.TempPathFactory,
) -> Iterator[None]:
    """O barramento HID que o laço do daemon olha aponta para o VAZIO."""
    vazio = tmp_path_factory.mktemp("sysfs-sem-barramento-hid")
    try:
        from hefesto_dualsense4unix.integrations import o_cabo_em_espera
    except ModuleNotFoundError as erro:  # pragma: no cover - só no job leve do CI
        if not _o_produto_nao_roda_neste_ambiente(erro):
            raise
        yield
        return

    antes = o_cabo_em_espera.RAIZ_DO_BARRAMENTO_HID
    o_cabo_em_espera.RAIZ_DO_BARRAMENTO_HID = str(vazio)
    try:
        yield
    finally:
        o_cabo_em_espera.RAIZ_DO_BARRAMENTO_HID = antes


_NOMES_DE_VENV = (".venv", "venv")


def _raizes_de_venv() -> list[Path]:
    """A árvore de hoje, e depois a árvore PRINCIPAL do worktree."""
    raiz = Path(__file__).resolve().parents[1]
    raizes = [raiz]
    import subprocess as _sp

    with contextlib.suppress(Exception):
        saida = _sp.run(
            ["git", "-C", str(raiz), "worktree", "list", "--porcelain"],
            capture_output=True,
            text=True,
            timeout=20,
        ).stdout
        primeira = saida.splitlines()[0].split(maxsplit=1) if saida else []
        if len(primeira) == 2 and primeira[0] == "worktree":
            principal = Path(primeira[1])
            if principal != raiz:
                raizes.append(principal)
    return raizes


def binario_do_venv(nome: str) -> Path | None:
    """O caminho de `nome` no venv desta árvore, ou no da árvore principal."""
    for raiz in _raizes_de_venv():
        for venv in _NOMES_DE_VENV:
            candidato = raiz / venv / "bin" / nome
            if candidato.is_file() and os.access(candidato, os.X_OK):
                return candidato
    return None


BINARIOS_DO_SERVIDOR_DE_SOM: tuple[str, ...] = (
    "pactl", "pacmd", "pacat", "parec", "parecord", "paplay", "pamon", "pasuspender",
    "wpctl", "pw-cli", "pw-dump", "pw-metadata", "pw-record", "pw-play", "pw-cat",
    "pw-link", "pw-loopback", "pw-top", "pw-mon",
    "arecord", "aplay", "speaker-test",
)

_SOM_DE_VERDADE_ENV = "HEFESTO_SOM_DE_VERDADE"

_SOM_PREFIXO = "hefesto-som-de-mentira-"
_SOM_REGISTRO = "chamadas.txt"

_SOM_DE_MENTIRA: list[Path] = []

_DIRS_DE_SISTEMA_PADRAO: tuple[str, ...] = (
    "/usr/local/sbin", "/usr/local/bin", "/usr/sbin", "/usr/bin", "/sbin", "/bin",
)
_DIRS_DE_SISTEMA: set[str] = set()

_POPEN_INIT_REAL: list[Callable[..., None]] = []


def _som_de_verdade() -> bool:
    return os.environ.get(_SOM_DE_VERDADE_ENV) == "1"


def som_de_mentira() -> Path | None:
    """O diretório dos dublês do som desta sessão, ou None sob o escape."""
    return _SOM_DE_MENTIRA[0] if _SOM_DE_MENTIRA else None


def chamadas_ao_som_de_mentira() -> list[str]:
    """Uma linha por chamada que chegou a um dublê: ``"<nome> <argv...>"``."""
    duble = som_de_mentira()
    if duble is None:
        return []
    try:
        texto = (duble / _SOM_REGISTRO).read_text(encoding="utf-8", errors="replace")
    except OSError:
        return []
    return texto.splitlines()


def _texto_do_duble(nome: str, registro: Path) -> str:
    return (
        "#!/bin/sh\n"
        "# SOM-DE-MENTIRA (tests/conftest.py): sob a suíte, este nome não chega ao\n"
        "# servidor de som de quem a roda. Anota o argv e sai como um servidor\n"
        "# que não atende.\n"
        f"printf '%s\\n' \"{nome} $*\" >> {shlex.quote(str(registro))} 2>/dev/null\n"
        f"echo 'SOM-DE-MENTIRA: {nome} sob teste não chega ao servidor de som' >&2\n"
        "exit 1\n"
    )


def _som_orfaos(raiz: Path) -> list[Path]:
    """Diretórios de dublê de sessões MORTAS — o critério por pid do berço."""
    orfaos: list[Path] = []
    with contextlib.suppress(OSError):
        for entrada in raiz.iterdir():
            if not entrada.name.startswith(_SOM_PREFIXO):
                continue
            cauda = entrada.name[len(_SOM_PREFIXO):]
            if not cauda.isdigit() or entrada.is_symlink() or not entrada.is_dir():
                continue
            if _pid_vivo(int(cauda)):
                continue
            orfaos.append(entrada)
    return orfaos


def _dirs_de_sistema(caminho: str) -> set[str]:
    """Os diretórios de sistema de sempre, mais todo diretório em que o PATH de"""
    dirs = {os.path.realpath(d) for d in _DIRS_DE_SISTEMA_PADRAO}
    limpo = os.pathsep.join(
        e for e in caminho.split(os.pathsep)
        if not os.path.basename(e.rstrip(os.sep)).startswith(_SOM_PREFIXO)
    )
    for nome in BINARIOS_DO_SERVIDOR_DE_SOM:
        achado = shutil.which(nome, path=limpo)
        if achado:
            dirs.add(os.path.realpath(os.path.dirname(achado)))
    return dirs


def _armar_som_de_mentira() -> None:
    """Cria os dublês, põe o diretório na frente do PATH e instala o `Popen`."""
    if _som_de_verdade() or _SOM_DE_MENTIRA:
        return
    raiz = _TMP_REAL[0] if _TMP_REAL else Path(tempfile.gettempdir())
    for orfao in _som_orfaos(raiz):
        shutil.rmtree(orfao, ignore_errors=True)
    destino = raiz / f"{_SOM_PREFIXO}{os.getpid()}"
    shutil.rmtree(destino, ignore_errors=True)
    registro = destino / _SOM_REGISTRO
    try:
        destino.mkdir(mode=0o700)
        registro.touch()
        for nome in BINARIOS_DO_SERVIDOR_DE_SOM:
            duble = destino / nome
            duble.write_text(_texto_do_duble(nome, registro), encoding="utf-8")
            duble.chmod(0o755)
    except OSError:  # pragma: no cover — /tmp sem escrita derruba a suíte antes
        shutil.rmtree(destino, ignore_errors=True)
        return
    antes = os.environ.get("PATH", os.defpath)
    _DIRS_DE_SISTEMA.update(_dirs_de_sistema(antes))
    _SOM_DE_MENTIRA.append(destino)
    os.environ["PATH"] = os.pathsep.join([str(destino), antes]) if antes else str(destino)
    _instalar_popen_sem_som()


def _path_com_o_duble(caminho: str, duble: Path) -> str:
    """`caminho` com o dublê ANTES do primeiro diretório de sistema."""
    alvo = str(duble)
    entradas = caminho.split(os.pathsep)
    for i, entrada in enumerate(entradas):
        if entrada == alvo:
            return caminho
        if os.path.realpath(entrada or os.curdir) in _DIRS_DE_SISTEMA:
            return os.pathsep.join([*entradas[:i], alvo, *entradas[i:]])
    return caminho


def _duble_no_lugar_de(programa: Any, caminho: str, duble: Path) -> str | None:
    """O dublê que roda no lugar de `programa`, ou None se não há o que trocar."""
    try:
        texto = os.fsdecode(programa)
    except (TypeError, ValueError):
        return None
    nome = os.path.basename(texto)
    if nome not in BINARIOS_DO_SERVIDOR_DE_SOM:
        return None
    resolvido = texto if os.path.dirname(texto) else shutil.which(texto, path=caminho)
    if resolvido is None:
        return None
    if os.path.realpath(os.path.dirname(resolvido)) not in _DIRS_DE_SISTEMA:
        return None
    return str(duble / nome)


def _desviar_para_o_duble(argumentos: dict[str, Any], duble: Path) -> None:
    """Ajusta, no lugar, os argumentos de um `Popen` que alcançaria o servidor."""
    env = argumentos.get("env")
    base = os.environ if env is None else env
    caminho = base.get("PATH") if hasattr(base, "get") else None
    if isinstance(caminho, str):
        novo = _path_com_o_duble(caminho, duble)
        if novo != caminho:
            argumentos["env"] = {**base, "PATH": novo}
            caminho = novo
    else:
        caminho = os.defpath
    if argumentos.get("shell"):
        return
    if argumentos.get("executable") is not None:
        troca = _duble_no_lugar_de(argumentos["executable"], caminho, duble)
        if troca is not None:
            argumentos["executable"] = troca
        return
    programa = argumentos.get("args")
    if programa is None:
        return
    if isinstance(programa, (str, bytes, os.PathLike)):
        troca = _duble_no_lugar_de(programa, caminho, duble)
        if troca is not None:
            argumentos["args"] = troca
        return
    if not isinstance(programa, (list, tuple)):
        try:
            programa = list(programa)
        except TypeError:
            return
        argumentos["args"] = programa
    if not programa:
        return
    troca = _duble_no_lugar_de(programa[0], caminho, duble)
    if troca is not None:
        argumentos["args"] = type(programa)([troca, *programa[1:]])


def _instalar_popen_sem_som() -> None:
    """A camada 2: o `Popen.__init__` da sessão desvia quem não herda o PATH."""
    if not _POPEN_COM_SOM:
        _POPEN_COM_SOM.append(True)
    _instalar_popen_da_sessao()


# "Alto-falante do controle", ao lado das duas placas de DualSense de verdade.
# usando. Lá era a tela; aqui é o som — e ela está com quatro DualSense na mesa.
_VERBOS_QUE_ESCREVEM_NO_SOM = ("load-module", "unload-module")


@pytest.fixture(autouse=True, scope="session")
def _nenhum_modulo_de_som_de_verdade() -> Iterator[None]:
    """`pactl load-module`/`unload-module` da suíte não chega ao PipeWire dela."""
    try:
        from hefesto_dualsense4unix.integrations import (
            alto_falante_bt,
            dualsense_bt_audio,
        )
    except ModuleNotFoundError as erro:  # pragma: no cover — job leve do CI
        if not _o_produto_nao_roda_neste_ambiente(erro):
            raise
        yield
        return

    if _som_de_verdade():
        yield
        return

    reais = {modulo: modulo._rodar for modulo in (alto_falante_bt, dualsense_bt_audio)}
    for modulo, real in reais.items():
        modulo._rodar = _sem_escrever_no_som(real)
    try:
        yield
    finally:
        for modulo, real in reais.items():
            modulo._rodar = real


def _sem_escrever_no_som(
    real: Callable[[list[str]], str | None],
) -> Callable[[list[str]], str | None]:
    """O `_rodar` de um módulo de som com a ESCRITA recusada e a leitura passando."""

    def _sem_escrever(argv: list[str]) -> str | None:
        if any(verbo in argv for verbo in _VERBOS_QUE_ESCREVEM_NO_SOM):
            return None
        return real(argv)

    return _sem_escrever


@pytest.fixture(autouse=True)
def _recuo_do_pactl_zerado() -> Iterator[None]:
    """O recuo do `pactl` nasce ZERADO em cada teste (SOM-RECUO-01, 13/09/2026)."""
    try:
        from hefesto_dualsense4unix.integrations import dualsense_bt_audio
    except ModuleNotFoundError as erro:  # pragma: no cover — job leve do CI
        if not _o_produto_nao_roda_neste_ambiente(erro):
            raise
        yield
        return
    dualsense_bt_audio.PACTL.zerar()
    try:
        yield
    finally:
        dualsense_bt_audio.PACTL.zerar()


_MARCA_DO_INSUMO = "insumo_fora_do_git"

_GITIGNORE_POR_RAIZ: dict[str, list[tuple[int, str, bool, bool]]] = {}


@dataclass(frozen=True)
class InsumoDeclarado:
    """Um caminho que uma régua versionada lê, olhado nesta árvore."""

    relativo: str
    existe: bool
    regra: str | None

    @property
    def nao_viaja(self) -> bool:
        """Ausente **e** explicado pelo `.gitignore` — o único caso que pula."""
        return not self.existe and self.regra is not None

    @property
    def razao(self) -> str:
        return f"`{self.relativo}` (excluído por `{self.regra}`)"


def _padroes_do_gitignore(raiz: Path) -> list[tuple[int, str, bool, bool]]:
    """`(número da linha, padrão, negado, só-pasta)`, na ordem do arquivo."""
    chave = str(raiz)
    lido = _GITIGNORE_POR_RAIZ.get(chave)
    if lido is not None:
        return lido

    padroes: list[tuple[int, str, bool, bool]] = []
    arquivo = raiz / ".gitignore"
    if arquivo.is_file():
        texto = arquivo.read_text(encoding="utf-8", errors="replace")
        for numero, bruta in enumerate(texto.splitlines(), start=1):
            linha = bruta.strip()
            if not linha or linha.startswith("#"):
                continue
            negado = linha.startswith("!")
            if negado:
                linha = linha[1:]
            so_pasta = linha.endswith("/")
            padroes.append((numero, linha.strip("/"), negado, so_pasta))
    _GITIGNORE_POR_RAIZ[chave] = padroes
    return padroes


def _regra_que_exclui(raiz: Path, relativo: str) -> str | None:
    """A linha do `.gitignore` que exclui `relativo`, ou `None`."""
    alvo = relativo.strip("/")
    if not alvo:
        return None
    partes = alvo.split("/")
    candidatos = ["/".join(partes[: i + 1]) for i in range(len(partes))]

    vencedora: str | None = None
    for numero, padrao, negado, _so_pasta in _padroes_do_gitignore(raiz):
        ancorado = "/" in padrao
        casou = False
        for candidato in candidatos:
            if ancorado:
                casou = fnmatch.fnmatch(candidato, padrao)
            else:
                casou = fnmatch.fnmatch(candidato.rsplit("/", 1)[-1], padrao)
            if casou:
                break
        if casou:
            vencedora = None if negado else f".gitignore:{numero}"
    return vencedora


def olhar_insumo(relativo: str, raiz: Path | None = None) -> InsumoDeclarado:
    """Olha UM caminho nesta árvore: ele veio, e — se não veio — por quê."""
    raiz_real = _RAIZ_DESTA_ARVORE if raiz is None else Path(raiz)
    caminho = raiz_real / relativo
    existe = caminho.exists()
    return InsumoDeclarado(
        relativo=relativo,
        existe=existe,
        regra=None if existe else _regra_que_exclui(raiz_real, relativo),
    )


def motivo_do_pulo(*relativos: str, raiz: Path | None = None) -> str | None:
    """A razão de pular, ou `None` quando não há razão para pular."""
    if not relativos:
        raise ValueError(
            "INSUMO-FORA-DO-GIT-01: marcador sem caminho nenhum é pulo calado — "
            "declare o que a régua lê."
        )
    olhados = [olhar_insumo(relativo, raiz=raiz) for relativo in relativos]
    ausentes = [insumo for insumo in olhados if not insumo.existe]
    if not ausentes:
        return None
    if any(insumo.regra is None for insumo in ausentes):
        return None
    return (
        "INSUMO-FORA-DO-GIT-01: esta régua é versionada e o insumo dela não é. "
        "Não veio para esta árvore: "
        + "; ".join(insumo.razao for insumo in ausentes)
        + " — num clone limpo (o `release.yml`) a ausência é esperada; numa "
        "árvore de agente, copie-os da árvore de quem despacha antes de medir."
    )


def exigir_insumo_fora_do_git(*relativos: str, raiz: Path | None = None) -> None:
    """Pula o MÓDULO INTEIRO com a razão, quando o insumo não veio."""
    motivo = motivo_do_pulo(*relativos, raiz=raiz)
    if motivo is not None:
        pytest.skip(motivo, allow_module_level=True)


def pytest_configure(config: Any) -> None:
    """Registra o marcador — sem isto ele vira aviso e morre sob `--strict-markers`."""
    config.addinivalue_line(
        "markers",
        f"{_MARCA_DO_INSUMO}(*relativos): a régua lê insumo que o git não "
        "carrega (`docs/process/`, o despacho de leva); pula COM A RAZÃO "
        "quando ele não veio, e só quando o `.gitignore` explica a ausência.",
    )


def pytest_collection_modifyitems(config: Any, items: list[Any]) -> None:
    """Converte o marcador em `skip` com a razão, na coleta."""
    for item in items:
        marcas = list(item.iter_markers(name=_MARCA_DO_INSUMO))
        if not marcas:
            continue
        relativos = [str(alvo) for marca in marcas for alvo in marca.args]
        if not relativos:
            raise pytest.UsageError(
                f"{item.nodeid}: `{_MARCA_DO_INSUMO}` sem caminho nenhum é pulo "
                "calado — declare o que a régua lê."
            )
        motivo = motivo_do_pulo(*relativos)
        if motivo is not None:
            item.add_marker(pytest.mark.skip(reason=motivo))


os.environ.setdefault("PYTHONFAULTHANDLER", "1")


_ARQUIVO_DO_WEBKIT: dict[str, bool] = {}


def _e_arquivo_do_webkit(item: Any) -> bool:
    caminho = str(getattr(item, "path", "") or "")
    if caminho not in _ARQUIVO_DO_WEBKIT:
        try:
            _ARQUIVO_DO_WEBKIT[caminho] = "WebKit2" in Path(caminho).read_text(encoding="utf-8")
        except (OSError, UnicodeDecodeError):
            _ARQUIVO_DO_WEBKIT[caminho] = False
    return _ARQUIVO_DO_WEBKIT[caminho]


def _recolher_no_fio_do_gtk() -> None:
    import gc

    gc.collect()
    if "gi.repository.WebKit2" not in sys.modules:
        return
    gtk = sys.modules.get("gi.repository.Gtk")
    with contextlib.suppress(Exception):
        while gtk is not None and gtk.events_pending():
            gtk.main_iteration_do(False)


@pytest.hookimpl(wrapper=True, specname="pytest_runtest_teardown")
def pytest_runtest_teardown_do_webkit(item: Any, nextitem: Any) -> Iterator[None]:
    try:
        return (yield)
    finally:
        troca_de_arquivo = nextitem is None or getattr(nextitem, "path", None) != getattr(
            item, "path", None)
        if _e_arquivo_do_webkit(item) or (
                troca_de_arquivo and "gi.repository.WebKit2" in sys.modules):
            _recolher_no_fio_do_gtk()


BINARIOS_DE_LANCADOR: tuple[str, ...] = (
    "steam", "steam-native", "steamwebhelper", "com.valvesoftware.Steam",
    "heroic", "com.heroicgameslauncher.hgl",
    "lutris", "net.lutris.Lutris",
    "xdg-open", "gtk-launch", "gio",
    "flatpak", "wmctrl",
    "pkill", "killall", "pgrep",
)

RAIZES_DE_LANCADOR: tuple[str, ...] = ("steam", "heroic", "lutris")

_FORMA_DO_DUBLE: dict[str, str] = {
    "pgrep": "pergunta",
    "pkill": "mata",
    "killall": "mata",
    "flatpak": "flatpak",
    "wmctrl": "wmctrl",
    "gio": "gio",
}

_LANCADOR_PREFIXO = "hefesto-lancador-de-mentira-"
_LANCADOR_LIVRO = "atos.txt"

_LANCADOR_DE_MENTIRA: list[Path] = []

_TEMPORARIOS_DA_SESSAO: list[str] = []

_SESSAO_DO_LANCADOR: list[int] = []

_LIVRO_LIDO: list[int] = [0]
_ATOS_FORA_DE_FASE: list[str] = []
_ATOS_DE_PROPOSITO: set[int] = set()

_FILHOS_NO_DUBLE: list[Any] = []
_ESPERA_DOS_FILHOS_S = 5.0

_POPEN_COM_SOM: list[bool] = []

_SIGLA_DO_LANCADOR = "A-SUITE-NAO-ABRE-NEM-FECHA-O-LANCADOR-DELA-01"


def lancador_de_mentira() -> Path | None:
    """O diretório dos dublês dos lançadores desta sessão."""
    return _LANCADOR_DE_MENTIRA[0] if _LANCADOR_DE_MENTIRA else None


def _livro_do_lancador() -> Path | None:
    duble = lancador_de_mentira()
    return None if duble is None else duble / _LANCADOR_LIVRO


def _ler_o_livro(desde: int) -> tuple[list[tuple[int, str]], int]:
    """As linhas INTEIRAS do livro a partir do byte `desde`, com o começo de"""
    livro = _livro_do_lancador()
    if livro is None:
        return [], desde
    try:
        with livro.open("rb") as arquivo:
            arquivo.seek(desde)
            bruto = arquivo.read()
    except OSError:
        return [], desde
    linhas: list[tuple[int, str]] = []
    posicao = desde
    for pedaco in bruto.splitlines(keepends=True):
        if not pedaco.endswith(b"\n"):
            break
        linhas.append((posicao, pedaco.decode("utf-8", "replace").rstrip("\n")))
        posicao += len(pedaco)
    return linhas, posicao


def _partir_a_linha(linha: str) -> tuple[str, str]:
    """``"<argv>\\t<PYTEST_CURRENT_TEST>"`` → (argv, quem o ambiente dizia)."""
    argv, _, quem = linha.partition("\t")
    return argv, quem


def atos_no_livro() -> list[str]:
    """Todo argv que chegou a um dublê de ato nesta sessão, na ordem."""
    linhas, _ = _ler_o_livro(0)
    return [_partir_a_linha(linha)[0] for _, linha in linhas]


def _padrao_de_lancador() -> str:
    """O `case` do shell que casa uma raiz de lançador, sem diferença de caixa."""
    def _sem_caixa(raiz: str) -> str:
        return "".join(
            f"[{c.upper()}{c.lower()}]" if c.isalpha() else c for c in raiz
        )

    return "|".join(f"*{_sem_caixa(r)}*" for r in RAIZES_DE_LANCADOR)


def _texto_do_lancador(nome: str, livro: Path, real: str | None) -> str:
    """O script de um dublê. `real` é o binário de verdade para o que não é"""
    forma = _FORMA_DO_DUBLE.get(nome, "ato")
    padrao = _padrao_de_lancador()
    cabeca = (
        "#!/bin/sh\n"
        "# LANCADOR-DE-MENTIRA (tests/conftest.py): sob a suíte, este nome não\n"
        "# abre, não fecha e não traz para a frente o lançador de quem a roda.\n"
        f"LIVRO={shlex.quote(str(livro))}\n"
        f"REAL={shlex.quote(real or '')}\n"
        "ato() {\n"
        f"  if [ $# -gt 0 ]; then linha=\"{nome} $*\"; else linha={shlex.quote(nome)}; fi\n"
        "  printf '%s\\t%s\\n' \"$linha\" \"${PYTEST_CURRENT_TEST:-}\" >> \"$LIVRO\" 2>/dev/null\n"
        "  exit 1\n"
        "}\n"
        "repassa() {\n"
        "  [ -n \"$REAL\" ] && exec \"$REAL\" \"$@\"\n"
        f"  echo {shlex.quote(nome + ': não há o binário de verdade nesta máquina')} >&2\n"
        "  exit 127\n"
        "}\n"
        "primeiro() {\n"
        "  for a in \"$@\"; do case \"$a\" in -*) ;; *) printf '%s' \"$a\"; return;; esac; done\n"
        "}\n"
    )
    if forma == "pergunta":
        corpo = (
            f"for a in \"$@\"; do case \"$a\" in {padrao}) exit 1;; esac; done\n"
            "repassa \"$@\"\n"
        )
    elif forma == "mata":
        corpo = (
            f"for a in \"$@\"; do case \"$a\" in {padrao}) ato \"$@\";; esac; done\n"
            "repassa \"$@\"\n"
        )
    elif forma == "flatpak":
        corpo = (
            "case \"$(primeiro \"$@\")\" in\n"
            "  '') repassa \"$@\";;\n"
            "  ps|list) exit 0;;\n"
            "  info) exit 1;;\n"
            "  *) ato \"$@\";;\n"
            "esac\n"
        )
    elif forma == "wmctrl":
        corpo = "case \"${1:-}\" in -l*|-m|-d) exit 0;; esac\nato \"$@\"\n"
    elif forma == "gio":
        corpo = (
            "case \"$(primeiro \"$@\")\" in open|launch) ato \"$@\";; esac\n"
            "repassa \"$@\"\n"
        )
    else:
        corpo = "ato \"$@\"\n"
    return cabeca + corpo


def escrever_os_dubles_dos_lancadores(
    destino: Path, livro: Path, reais: dict[str, str | None]
) -> None:
    """Escreve em `destino` um dublê por nome de `BINARIOS_DE_LANCADOR`."""
    livro.touch()
    for nome in BINARIOS_DE_LANCADOR:
        duble = destino / nome
        duble.write_text(
            _texto_do_lancador(nome, livro, reais.get(nome)), encoding="utf-8"
        )
        duble.chmod(0o755)


def _lancador_orfaos(raiz: Path) -> list[Path]:
    """Diretórios de dublê de sessões MORTAS — o critério por pid do berço."""
    orfaos: list[Path] = []
    with contextlib.suppress(OSError):
        for entrada in raiz.iterdir():
            if not entrada.name.startswith(_LANCADOR_PREFIXO):
                continue
            cauda = entrada.name[len(_LANCADOR_PREFIXO):]
            if not cauda.isdigit() or entrada.is_symlink() or not entrada.is_dir():
                continue
            if _pid_vivo(int(cauda)):
                continue
            orfaos.append(entrada)
    return orfaos


def _reais_dos_lancadores(caminho: str) -> dict[str, str | None]:
    """Onde o PATH de ANTES do arme acha cada nome — sem o dublê de uma sessão"""
    limpo = os.pathsep.join(
        e for e in caminho.split(os.pathsep)
        if not os.path.basename(e.rstrip(os.sep)).startswith(_LANCADOR_PREFIXO)
    )
    return {nome: shutil.which(nome, path=limpo) for nome in BINARIOS_DE_LANCADOR}


def _armar_lancador_de_mentira(session: Any) -> None:
    """Cria os dublês, põe o diretório na frente do PATH e instala o `Popen`."""
    if _LANCADOR_DE_MENTIRA:
        return
    raiz = _TMP_REAL[0] if _TMP_REAL else Path(tempfile.gettempdir())
    for orfao in _lancador_orfaos(raiz):
        shutil.rmtree(orfao, ignore_errors=True)
    destino = raiz / f"{_LANCADOR_PREFIXO}{os.getpid()}"
    shutil.rmtree(destino, ignore_errors=True)
    antes = os.environ.get("PATH", os.defpath)
    try:
        destino.mkdir(mode=0o700)
        escrever_os_dubles_dos_lancadores(
            destino, destino / _LANCADOR_LIVRO, _reais_dos_lancadores(antes)
        )
    except OSError:  # pragma: no cover — /tmp sem escrita derruba a suíte antes
        shutil.rmtree(destino, ignore_errors=True)
        return
    temporarios = [berco()]
    fabrica = getattr(getattr(session, "config", None), "_tmp_path_factory", None)
    if fabrica is not None:
        with contextlib.suppress(Exception):
            temporarios.append(fabrica.getbasetemp())
    _TEMPORARIOS_DA_SESSAO.extend(
        os.path.realpath(t) for t in temporarios if t is not None
    )
    _LANCADOR_DE_MENTIRA.append(destino)
    _SESSAO_DO_LANCADOR.append(id(session))
    os.environ["PATH"] = os.pathsep.join([str(destino), antes]) if antes else str(destino)
    _instalar_popen_da_sessao()


def _e_temporario_da_sessao(caminho: str) -> bool:
    """`caminho` mora no berço ou na `basetemp` desta sessão?"""
    real = os.path.realpath(caminho or os.curdir)
    return any(
        real == t or real.startswith(t.rstrip(os.sep) + os.sep)
        for t in _TEMPORARIOS_DA_SESSAO
    )


def _path_com_o_lancador(caminho: str, duble: Path) -> str:
    """`caminho` com o dublê ANTES do primeiro diretório que não seja"""
    alvo = str(duble)
    entradas = caminho.split(os.pathsep)
    for i, entrada in enumerate(entradas):
        if entrada == alvo:
            return caminho
        if not _e_temporario_da_sessao(entrada):
            return os.pathsep.join([*entradas[:i], alvo, *entradas[i:]])
    return caminho


def _lancador_no_lugar_de(programa: Any, caminho: str, duble: Path) -> str | None:
    """O dublê que roda no lugar de `programa`, ou None se não há o que trocar."""
    try:
        texto = os.fsdecode(programa)
    except (TypeError, ValueError):
        return None
    nome = os.path.basename(texto)
    if nome not in BINARIOS_DE_LANCADOR:
        return None
    resolvido = texto if os.path.dirname(texto) else shutil.which(texto, path=caminho)
    if resolvido is not None:
        pasta = os.path.realpath(os.path.dirname(resolvido) or os.curdir)
        if pasta != os.path.realpath(duble) and _e_temporario_da_sessao(pasta):
            return None
    return str(duble / nome)


def _desviar_para_o_lancador(argumentos: dict[str, Any], duble: Path) -> None:
    """Ajusta, no lugar, os argumentos de um `Popen` que alcançaria um lançador."""
    env = argumentos.get("env")
    base = os.environ if env is None else env
    caminho = base.get("PATH") if hasattr(base, "get") else None
    if isinstance(caminho, str):
        novo = _path_com_o_lancador(caminho, duble)
        if novo != caminho:
            argumentos["env"] = {**base, "PATH": novo}
            caminho = novo
    else:
        caminho = os.defpath
    if argumentos.get("shell"):
        return
    if argumentos.get("executable") is not None:
        troca = _lancador_no_lugar_de(argumentos["executable"], caminho, duble)
        if troca is not None:
            argumentos["executable"] = troca
        return
    programa = argumentos.get("args")
    if programa is None:
        return
    if isinstance(programa, (str, bytes, os.PathLike)):
        troca = _lancador_no_lugar_de(programa, caminho, duble)
        if troca is not None:
            argumentos["args"] = troca
        return
    if not isinstance(programa, (list, tuple)):
        try:
            programa = list(programa)
        except TypeError:
            return
        argumentos["args"] = programa
    if not programa:
        return
    troca = _lancador_no_lugar_de(programa[0], caminho, duble)
    if troca is not None:
        argumentos["args"] = type(programa)([troca, *programa[1:]])


def _instalar_popen_da_sessao() -> None:
    """O embrulho ÚNICO do `Popen.__init__` da sessão, com as duas tabelas."""
    import functools
    import subprocess

    if _POPEN_INIT_REAL:
        return
    real = subprocess.Popen.__init__
    assinatura = inspect.signature(real)

    @functools.wraps(real)
    def _init_da_sessao(self: Any, *args: Any, **kwargs: Any) -> None:
        som = som_de_mentira() if _POPEN_COM_SOM else None
        lancador = lancador_de_mentira()
        if som is not None or lancador is not None:
            try:
                amarrado = assinatura.bind(self, *args, **kwargs)
            except TypeError:
                pass
            else:
                if som is not None:
                    _desviar_para_o_duble(amarrado.arguments, som)
                if lancador is not None:
                    _desviar_para_o_lancador(amarrado.arguments, lancador)
                _POPEN_INIT_REAL[0](*amarrado.args, **amarrado.kwargs)
                if lancador is not None and _vai_ao_duble(amarrado.arguments, lancador):
                    _FILHOS_NO_DUBLE.append(self)
                return None
        return _POPEN_INIT_REAL[0](self, *args, **kwargs)

    _POPEN_INIT_REAL.append(real)
    subprocess.Popen.__init__ = _init_da_sessao  # type: ignore[method-assign]


def _vai_ao_duble(argumentos: dict[str, Any], duble: Path) -> bool:
    """O programa deste `Popen` é um dublê de lançador?"""
    programa: Any = argumentos.get("executable")
    if programa is None:
        bruto = argumentos.get("args")
        programa = bruto[0] if isinstance(bruto, (list, tuple)) and bruto else bruto
    try:
        return os.path.dirname(os.fsdecode(programa)) == str(duble)
    except (TypeError, ValueError):
        return False


def _esperar_os_filhos_no_duble() -> None:
    """Espera (com teto) os dublês que ainda estão rodando escreverem no livro."""
    import time

    limite = time.monotonic() + _ESPERA_DOS_FILHOS_S
    while _FILHOS_NO_DUBLE:
        filho = _FILHOS_NO_DUBLE[0]
        with contextlib.suppress(Exception):
            if filho.poll() is None and time.monotonic() < limite:
                time.sleep(0.01)
                continue
        _FILHOS_NO_DUBLE.pop(0)


def _abrir_a_fase() -> None:
    """O que chegou ao livro ENTRE fases não é de teste nenhum."""
    linhas, ate = _ler_o_livro(_LIVRO_LIDO[0])
    _ATOS_FORA_DE_FASE.extend(
        linha for inicio, linha in linhas if inicio not in _ATOS_DE_PROPOSITO
    )
    _LIVRO_LIDO[0] = ate


def _fechar_a_fase(item: Any, fase: str) -> None:
    """Reprova a fase que chamou um ato, com o argv e o nodeid."""
    _esperar_os_filhos_no_duble()
    linhas, ate = _ler_o_livro(_LIVRO_LIDO[0])
    _LIVRO_LIDO[0] = ate
    atos = [linha for inicio, linha in linhas if inicio not in _ATOS_DE_PROPOSITO]
    if not atos:
        return
    nodeid = str(getattr(item, "nodeid", item))
    relato = []
    for linha in atos:
        argv, quem = _partir_a_linha(linha)
        dito = f" (o ambiente do filho dizia: {quem})" if quem else ""
        relato.append(f"  - `{argv}`{dito}")
    raise AssertionError("\n".join([
        f"{_SIGLA_DO_LANCADOR}: este teste ({nodeid}, fase {fase}) chamou "
        f"{len(atos)} ato(s) de lançador; sem a guarda, isso fecharia (ou "
        "abriria) o lançador de quem roda a suíte:",
        *relato,
        "  Dublê o ato no próprio teste (como `test_o_reiniciar_repoe_o_lancador.py`"
        " dubla `rl.repor`), ou declare-o pela fixture `ato_de_proposito`.",
    ]))


@contextlib.contextmanager
def _fase_vigiada(item: Any, fase: str) -> Iterator[None]:
    if lancador_de_mentira() is None:
        yield
        return
    _abrir_a_fase()
    try:
        yield
    finally:
        _fechar_a_fase(item, fase)


@pytest.hookimpl(wrapper=True, tryfirst=True, specname="pytest_runtest_setup")
def pytest_runtest_setup_do_lancador(item: Any) -> Iterator[None]:
    with _fase_vigiada(item, "setup"):
        return (yield)


@pytest.hookimpl(wrapper=True, tryfirst=True, specname="pytest_runtest_call")
def pytest_runtest_call_do_lancador(item: Any) -> Iterator[None]:
    with _fase_vigiada(item, "call"):
        return (yield)


@pytest.hookimpl(wrapper=True, tryfirst=True, specname="pytest_runtest_teardown")
def pytest_runtest_teardown_do_lancador(item: Any, nextitem: Any) -> Iterator[None]:
    with _fase_vigiada(item, "teardown"):
        return (yield)


@pytest.fixture
def ato_de_proposito() -> Callable[..., contextlib.AbstractContextManager[None]]:
    """Declara o ato que a régua chama DE PROPÓSITO, para provar a guarda."""

    @contextlib.contextmanager
    def _declarar(*esperados: str) -> Iterator[None]:
        assert lancador_de_mentira() is not None, (
            f"{_SIGLA_DO_LANCADOR}: a sessão não armou os dublês dos lançadores"
        )
        _, desde = _ler_o_livro(_LIVRO_LIDO[0])
        yield
        _esperar_os_filhos_no_duble()
        linhas, _ = _ler_o_livro(desde)
        chegaram = [_partir_a_linha(linha)[0] for _, linha in linhas]
        assert chegaram == list(esperados), (
            f"{_SIGLA_DO_LANCADOR}: o bloco declarou {list(esperados)} e o livro "
            f"trouxe {chegaram}"
        )
        _ATOS_DE_PROPOSITO.update(inicio for inicio, _ in linhas)

    return _declarar


def _lancador_no_fim_da_sessao(session: Any) -> None:
    """O ato que chegou fora de qualquer fase reprova a SESSÃO, com o livro."""
    if _SESSAO_DO_LANCADOR and id(session) not in _SESSAO_DO_LANCADOR:
        return
    if lancador_de_mentira() is None:
        return
    _esperar_os_filhos_no_duble()
    _abrir_a_fase()
    if not _ATOS_FORA_DE_FASE:
        return
    mostrados = _ATOS_FORA_DE_FASE[:_VIGIA_LIMITE_RELATO]
    restam = len(_ATOS_FORA_DE_FASE) - len(mostrados)
    linhas = []
    for linha in mostrados:
        argv, quem = _partir_a_linha(linha)
        linhas.append(f"  - `{argv}`" + (f" (o ambiente dizia: {quem})" if quem else ""))
    _escrever_no_terminal(session, [
        "",
        f"{_SIGLA_DO_LANCADOR}: {len(_ATOS_FORA_DE_FASE)} ato(s) de lançador "
        "chegaram FORA de qualquer teste (um fio, um finalizador):",
        *linhas,
        *([f"  ... e mais {restam}"] if restam > 0 else []),
        "  Sem a guarda, isso fecharia (ou abriria) o lançador de quem roda a suíte.",
    ])
    session.exitstatus = 1


# jogo, o `jogo_aberto` do «reiniciar», a recusa do `with_steam_closed`)

_MODULO_DO_JOGO = "hefesto_dualsense4unix.integrations.steam_launch_options"

_LEITOR_DO_JOGO_REAL: list[Callable[[Any], str]] = []

_PID_DA_SESSAO_DO_JOGO: list[int] = []


def _pai_de(pid: int, raiz_proc: str = "/proc") -> int | None:
    """O ppid de `pid` pelo `stat` (o 4º campo, depois do `comm` entre parênteses)."""
    try:
        with open(f"{raiz_proc}/{pid}/stat", encoding="utf-8", errors="replace") as fh:
            texto = fh.read()
    except OSError:
        return None
    _, _, resto = texto.rpartition(")")
    campos = resto.split()
    if len(campos) < 2 or not campos[1].lstrip("-").isdigit():
        return None
    return int(campos[1])


def descende_da_sessao(pid: Any, sessao: int | None = None) -> bool:
    """`pid` é esta sessão de pytest ou um processo que ela nasceu?"""
    try:
        atual: int | None = int(pid)
    except (TypeError, ValueError):
        return False
    raiz = sessao if sessao is not None else (
        _PID_DA_SESSAO_DO_JOGO[0] if _PID_DA_SESSAO_DO_JOGO else os.getpid()
    )
    for _ in range(64):
        if atual is None or atual <= 1:
            return False
        if atual == raiz:
            return True
        atual = _pai_de(atual)
    return False


def _cmdline_so_da_sessao(pid: Any) -> str:
    """O leitor que o produto vê sob a suíte: o jogo de fora some."""
    leitor = _LEITOR_DO_JOGO_REAL[0]
    cmd = leitor(pid)
    modulo = sys.modules.get(_MODULO_DO_JOGO)
    agulha = getattr(modulo, "_STEAM_LAUNCH_RE", None)
    if not cmd or agulha is None or not agulha.search(cmd):
        return cmd
    return cmd if descende_da_sessao(pid) else ""


_cmdline_so_da_sessao._so_da_sessao = True  # type: ignore[attr-defined]


def _armar_jogo_so_da_sessao() -> None:
    """Põe o embrulho no `_cmdline_of` do módulo carregado (ou o carrega)."""
    modulo = sys.modules.get(_MODULO_DO_JOGO)
    if modulo is None:
        try:
            import importlib

            modulo = importlib.import_module(_MODULO_DO_JOGO)
        except Exception:  # pragma: no cover — sem o pacote não há o que vigiar
            return
    atual = getattr(modulo, "_cmdline_of", None)
    if atual is None or getattr(atual, "_so_da_sessao", False):
        return
    if not _PID_DA_SESSAO_DO_JOGO:
        _PID_DA_SESSAO_DO_JOGO.append(os.getpid())
    _LEITOR_DO_JOGO_REAL[:] = [getattr(modulo, "cmdline_de_pid", atual)]
    setattr(modulo, "_cmdline_of", _cmdline_so_da_sessao)  # noqa: B010


@pytest.fixture(autouse=True)
def _o_jogo_de_fora_nao_entra() -> None:
    """JOGO-SO-DA-SESSAO: confere o embrulho antes de cada teste."""
    _armar_jogo_so_da_sessao()
