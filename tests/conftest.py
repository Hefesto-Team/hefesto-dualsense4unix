"""Fixtures compartilhadas entre testes unit e integration.

Além das fixtures, este arquivo hospeda a GUARDA-GI-REAL-01 — a resposta ao
defeito medido em 28/07: ``pytest.importorskip("gi")`` é DERROTADO por poluição
de ``sys.modules``. Vinte e um arquivos de teste plantam um ``gi`` falso (com
``Gtk.Box = object``) no nível de módulo; quem vem depois na ORDEM ALFABÉTICA
importa esse falso, o ``importorskip`` não pula, e centenas de testes de
interface reportam PASSED contra um GTK de mentira. Cobertura falsa é pior do
que cobertura ausente. Ver ``exigir_gi_real`` e ``pytest_collectstart`` abaixo.
"""

import os
import sys
import types
from pathlib import Path
from typing import Any

import pytest

# ---------------------------------------------------------------------------
# GUARDA-GI-REAL-01 — o `gi` do processo é o de verdade, ou é um stub?
# ---------------------------------------------------------------------------

#: Nomes de módulo que os stubs de teste plantam em ``sys.modules``.
_PREFIXO_GI = "gi"


def _e_modulo_gi(nome: str) -> bool:
    """True para ``gi`` e qualquer submódulo (``gi.repository.Gtk`` etc.)."""
    return nome == _PREFIXO_GI or nome.startswith(_PREFIXO_GI + ".")


def _gtk_e_real(gtk: Any) -> bool:
    """True quando ``gtk`` expõe widgets de VERDADE, não os do stub.

    O stub canônico dos testes faz ``Gtk.Box = object`` — passa em qualquer
    ``hasattr``, e é justamente por isso que ``importorskip`` não o pega. Aqui
    o critério é o que distingue os dois: no PyGObject real ``Gtk.Box`` é uma
    classe própria (``gi.overrides.Gtk.Box``), nunca o ``object`` embutido.
    """
    caixa = getattr(gtk, "Box", None)
    if caixa is None or caixa is object:
        return False
    if not isinstance(caixa, type):
        return False
    # `types.ModuleType` puro (o stub) nunca tem `ListStore` E `Box` reais ao
    # mesmo tempo; o real tem os dois.
    lista = getattr(gtk, "ListStore", None)
    return lista is not None and lista is not object


def gi_real_no_processo() -> bool:
    """True quando o ``gi`` JÁ CARREGADO neste processo é o PyGObject real.

    Devolve False tanto para "não há ``gi``" quanto para "há um stub plantado
    por outro arquivo de teste" — é esta segunda resposta que o
    ``pytest.importorskip("gi")`` erra.
    """
    modulo_gi = sys.modules.get(_PREFIXO_GI)
    if modulo_gi is None:
        return False
    # `types.ModuleType("gi")` nasce com `__spec__` None; o pacote real tem um.
    if getattr(modulo_gi, "__spec__", None) is None:
        return False
    gtk = sys.modules.get("gi.repository.Gtk")
    if gtk is None:
        # O `gi` é real e o Gtk ainda não foi carregado — nada a reprovar.
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


#: Fotografia dos módulos ``gi*`` REAIS, mantida em dia enquanto o processo tem
#: o PyGObject de verdade carregado.
#:
#: Ela existe por uma razão medida: NÃO se desfaz um stub simplesmente apagando
#: o ``gi`` e deixando o próximo módulo reimportar. O PyGObject registra tipos
#: no GObject na primeira importação, e a segunda estoura
#: ``RuntimeError: Unable to register enum 'PyGLibUserDirectory'`` — na máquina
#: da mantenedora isso derrubou 66 testes e 39 coletas de uma vez. Devolver os
#: MESMOS objetos de módulo não reimporta nada e não registra nada de novo.
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
    """Pergunta a um SUBPROCESSO limpo o que o ambiente tem de GTK.

    Devolve ``(gi_real_disponivel, response_type_presente)``.

    Roda fora do processo de propósito: importar o Gtk aqui, no conftest
    (avaliado cedo, na coleta), competiria com a versão que outro teste já
    carregou — o repo mistura Gtk 3.0 (produção) e 4.0 (fixtures), e
    "Namespace already loaded" derruba a coleta inteira. O subprocesso não tem
    esse estado e responde só as duas perguntas que importam.
    """
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


#: Medido UMA vez, na importação do conftest (o subprocesso é barato).
GI_REAL_DISPONIVEL, _GTK_RESPONSE_TYPE_PRESENTE = _sondar_gtk_do_ambiente()

#: Quando ligado, "pular por falta de GTK real" vira REPROVAÇÃO. É o que o job
#: dedicado do CI (com `python3-gi` + typelibs + Xvfb) usa: lá, um pulo é um
#: defeito de ambiente disfarçado de sucesso, e o pulo silencioso é metade do
#: problema que esta guarda existe para curar.
EXIGE_GTK_REAL = os.environ.get("HEFESTO_EXIGE_GTK_REAL") == "1"

_MOTIVO_SEM_GI = (
    "GUARDA-GI-REAL-01: PyGObject real ausente (ou substituído por stub de "
    "teste). Instale python3-gi + gir1.2-gtk-3.0 para exercitar a interface."
)

#: Marker reusável: pula quando o GTK do ambiente não expõe os enums de widget.
skip_sem_gtk_response = pytest.mark.skipif(
    not _GTK_RESPONSE_TYPE_PRESENTE,
    reason="Gtk.ResponseType indisponível (GTK parcial — CI headless)",
)

#: Marker reusável: pula quando não há PyGObject REAL. Substitui, com critério
#: honesto, o ``pytest.importorskip("gi")`` — que aceita o stub.
skip_sem_gi_real = pytest.mark.skipif(not GI_REAL_DISPONIVEL, reason=_MOTIVO_SEM_GI)

#: Módulos que pularam por falta de GTK real, para o resumo alto no fim do run.
_MODULOS_PULADOS_SEM_GI: list[str] = []

#: Módulos cujo `gi` FALSO foi retirado antes da importação do módulo seguinte.
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
    """Guarda de nível de módulo: exige o PyGObject REAL, reprovando o stub.

    Use no lugar de ``pytest.importorskip("gi")`` em todo módulo de teste que
    só faz sentido contra o GTK de verdade. A diferença é o critério:

    - ``importorskip("gi")`` pergunta "``import gi`` funciona?" — e um stub
      plantado por OUTRO arquivo de teste responde que sim;
    - ``exigir_gi_real()`` pergunta "o ``Gtk`` deste processo tem widgets de
      verdade?" — e o stub (``Gtk.Box = object``) reprova.

    Quando há stub carregado mas o AMBIENTE tem PyGObject real, a função limpa
    o stub em vez de pular: quem mentiu foi o arquivo anterior, e a máquina de
    desenvolvimento não pode perder centenas de testes por causa disso.
    """
    if gi_real_no_processo():
        return

    if GI_REAL_DISPONIVEL:
        # Ambiente bom, processo envenenado: devolve os módulos reais (a foto)
        # ou, se ainda não há foto, importa o PyGObject pela primeira vez.
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
    """Planta stubs de ``gi`` ISOLADOS, desfeitos ao fim do escopo do monkeypatch.

    Alternativa ao ``sys.modules["gi"] = ...`` cru: o ``monkeypatch.setitem``
    devolve ``sys.modules`` ao estado anterior no teardown, então a poluição
    não vaza para o arquivo seguinte. Devolve o módulo ``gi.repository.Gtk``
    plantado, para o chamador acrescentar o que faltar.
    """
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
    """Impede que o ``gi`` FALSO de um arquivo vaze para o arquivo seguinte.

    Este é o coração da GUARDA-GI-REAL-01. A importação dos módulos de teste
    acontece toda na COLETA, antes de qualquer fixture rodar — por isso
    nenhuma fixture (nem ``monkeypatch``) chega a tempo de desfazer o plantio
    antes do próximo arquivo ser importado. Este hook chega: ele roda logo
    antes de cada módulo ser importado.

    Regra: se o ``gi`` carregado for REAL, não se mexe (é o estado desejado) e
    a fotografia dos módulos reais fica em dia. Se for um STUB, ele sai — pela
    fotografia, quando existe (máquina com GTK: o módulo seguinte recebe o
    PyGObject de verdade, sem reimportar nada), ou apagado (CI sem GTK: o
    módulo seguinte decide sozinho — importa, planta o próprio stub, ou pula).
    O que ele NÃO faz mais é herdar a mentira de quem veio antes por acaso da
    ordem alfabética.
    """
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


def pytest_report_header(config: Any) -> str:
    """Diz, no cabeçalho do run, contra QUAL GTK a suíte vai rodar."""
    estado = "REAL (python3-gi + typelibs)" if GI_REAL_DISPONIVEL else "AUSENTE"
    extra = " | HEFESTO_EXIGE_GTK_REAL=1 (pulo vira reprovação)" if EXIGE_GTK_REAL else ""
    return f"guarda-gi-real-01: PyGObject {estado}{extra}"


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


def pytest_sessionfinish(session: Any, exitstatus: int) -> None:
    """Sob ``HEFESTO_EXIGE_GTK_REAL=1``, pulo por falta de GTK reprova o run."""
    if EXIGE_GTK_REAL and _MODULOS_PULADOS_SEM_GI:
        session.exitstatus = 1


# NOTA: a sonda antiga `_gtk_response_type_ausente()` foi fundida em
# `_sondar_gtk_do_ambiente()` acima — um subprocesso responde as DUAS
# perguntas (gi real? ResponseType presente?) em vez de dois.


@pytest.fixture(scope="session")
def repo_root() -> Path:
    return Path(__file__).resolve().parents[1]


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
    # XDG_RUNTIME_DIR NÃO é isolado de propósito: os testes de single_instance
    # dependem da semântica real do runtime dir (pid/socket, permissões 0700) e
    # quebram sob um tmp. O socket IPC já é isolável por nome via
    # HEFESTO_DUALSENSE4UNIX_IPC_SOCKET_NAME quando um teste precisa.
    #
    # Os dirs ficam sob um subdir dedicado (`.xdg/`) para NÃO colidir com testes
    # que criam `tmp_path / "config"` etc. com `exist_ok=False` na própria fixture
    # (ex.: test_service_install.isolated_systemd_user) — pytest entrega o MESMO
    # tmp_path a todas as fixtures do teste. Testes que setam o próprio
    # XDG_CONFIG_HOME por cima continuam vencendo (este é só o default hermético).
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
    # FIX-PACKAGING-SEED-PARITY-01 — desliga a semeadura automática de presets
    # (profiles.loader._maybe_seed_presets). Sem isto, o PRIMEIRO teste do
    # processo a carregar perfis receberia os JSONs de assets/profiles_default/
    # do repo no seu tmp (o flag once-per-process faria só um teste, dependente
    # da ordem, quebrar asserções de listas exatas). Os testes da semeadura
    # chamam seed_default_presets() com paths injetados ou re-habilitam via
    # monkeypatch (delenv + _seed_attempted=False).
    monkeypatch.setenv("HEFESTO_DUALSENSE4UNIX_SKIP_PRESET_SEED", "1")
    # BROKER-01: aponta o cliente do broker hide-hidraw para um socket
    # INEXISTENTE em TODO teste. Na máquina da mantenedora o broker REAL está
    # de pé em /run/hefesto-hidraw-broker/broker.sock — um teste que
    # resolvesse o default esconderia/abriria hidraw DE VERDADE no meio da
    # suíte. Testes do próprio cliente passam o caminho explicitamente.
    monkeypatch.setenv("HEFESTO_BROKER_SOCKET", str(xdg_root / "no-broker.sock"))
