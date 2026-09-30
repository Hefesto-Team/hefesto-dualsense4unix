"""O lançador liga duas curas que estavam sem chamador (28/09/2026).

O-CODIGO-SEM-CHAMADOR-LIGA-OU-SAI-01. As duas moravam no motor e só a suíte as
chamava desde que a janela GTK saiu (06/09, `D-0609-GTK-LEVA-INTEIRA`):

1. ``utils/single_instance.acquire_or_bring_to_front`` — clicar no ícone com a
   janela já aberta abria OUTRA janela. Agora a aberta recebe o pedido pela
   porta dela (um socket no runtime) e vem para a frente, e o segundo processo
   sai com ``rc=0`` antes do GTK.
2. ``app/arranque.sanear_loaders_do_gdk_pixbuf`` — o cache de loaders herdado de
   um terminal empacotado, cujos módulos são de outro confinamento, fazia o GTK
   abortar o processo no primeiro SVG. O lançador passa a descartá-lo antes de
   qualquer ``gi.repository``.

O PEDIDO NÃO É SINAL, e há régua para isso: a primeira versão mandava
``SIGUSR1``, e a bancada de tela de 28/09 mostrou o WebKit tomando esse sinal
para o coletor de lixo do JavaScriptCore — o segundo clique DERRUBOU a janela
aberta com falha de segmentação.

NADA AQUI FALA COM A JANELA DELA. O runtime (onde moram o pid file e a porta) é
um berço 0700 curto em ``/tmp`` (o ``AF_UNIX`` aceita 108 bytes), reimportado
como em ``test_single_instance.py``; o nome do lock leva um ``WAYLAND_DISPLAY``
inventado por teste; e o único processo que recebe pedido é o filho que o
próprio teste subiu.
"""
from __future__ import annotations

import ast
import fcntl
import importlib
import os
import shutil
import signal
import subprocess
import sys
import tempfile
import threading
import time
from collections.abc import Iterator
from pathlib import Path
from types import ModuleType

import pytest

from tests.conftest import exigir_gi_real

RAIZ = Path(__file__).resolve().parents[2]
LANCADOR = RAIZ / "scripts" / "abrir_interface.py"

#: Generoso: o filho é um interpretador novo que importa o pacote inteiro.
ESPERA_PELO_FILHO_SEC = 20.0

#: O filho que toma a vez. ``glib``: o ``main`` do lançador inteiro, com um
#: piloto que segura o laço do GLib por 20 s. ``arranque``: toma a vez e
#: DORME antes de armar a escuta (o pedido chega aí, como um segundo clique no
#: meio do arranque), depois arma e roda o laço por 3 s e sai sozinho.
#: ``travada``: toma a vez e nunca arma a escuta — o laço do GTK parado.
_FILHO = """
import os, sys, time, pathlib
sys.path.insert(0, sys.argv[1])
import abrir_interface as ai
if sys.argv[2] == "glib":
    ai.achar_o_piloto = lambda: pathlib.Path(sys.argv[3])
    ai.diario_da_janela = lambda: None
    sys.exit(ai.main([]))
nome = ai.tomar_a_vez([])
print("vez:" + repr(nome), flush=True)
if sys.argv[2] == "travada":
    time.sleep(30)
    sys.exit(0)
time.sleep(2.5)
import gi
gi.require_version("Gtk", "3.0")
from gi.repository import GLib
ai.armar_a_volta_a_frente(nome)
laco = GLib.MainLoop()
GLib.timeout_add(3000, laco.quit)
laco.run()
"""

#: O piloto do primeiro processo no modo ``glib``: o ``main`` do lançador já
#: tomou a vez, vestiu a identidade e armou a escuta quando ele roda, e ele só
#: avisa que está de pé e segura o laço do GLib, como a janela das abas.
_PILOTO_QUE_FICA = """
from gi.repository import GLib
print("vez:'pronto'", flush=True)
laco = GLib.MainLoop()
GLib.timeout_add(20000, laco.quit)
laco.run()
"""


#: O MOTIVO de os dois filhos que armam a escuta pedirem o GTK de verdade.
_O_FILHO_PRECISA_DO_GLIB = (
    "o filho roda o lançador de verdade: `vestir_a_identidade` importa o Gtk e o "
    "`armar_a_volta_a_frente` põe a porta no laço do GLib"
)


def _o_filho_tem_o_glib() -> None:
    """Os modos ``glib`` e ``arranque`` do filho só existem com o PyGObject real.

    ELES REPROVAVAM NO `lint-test` COM A CAUSA ERRADA — 30/09/2026. O filho é
    um ``sys.executable -c``, e na venv sem ``gi`` do job ele morre no ``import
    gi`` (medido: ``ModuleNotFoundError: No module named 'gi'`` no
    ``vestir_a_identidade`` e depois do ``time.sleep(2.5)`` do ``arranque``).
    O pai não via isso: dizia *"o primeiro processo não tomou a vez"* ou
    ``assert '' is None`` — a porta aberta sem ninguém para ler, o ``Connection
    reset by peer`` do pedido. A falta do GTK morava num SUBPROCESSO, e a regra
    do conftest (``_falta_o_gtk``) só enxerga a do processo dele.

    A pergunta é a do dono, ``exigir_gi_real``: no job do GTK real
    (``HEFESTO_EXIGE_GTK_REAL=1``) a falta reprova, e é lá que estes dois rodam
    inteiros. O modo ``travada`` não importa o ``gi`` e não passa por aqui.
    """
    exigir_gi_real(_O_FILHO_PRECISA_DO_GLIB)


def _carregar_o_lancador() -> ModuleType:
    """O ``scripts/abrir_interface.py`` como módulo, sem o bloco de entrada."""
    sys.path.insert(0, str(LANCADOR.parent))
    try:
        sys.modules.pop("abrir_interface", None)
        return importlib.import_module("abrir_interface")
    finally:
        sys.path.remove(str(LANCADOR.parent))


@pytest.fixture
def berco(monkeypatch: pytest.MonkeyPatch) -> Iterator[Path]:
    """Runtime isolado e curto, e uma tela inventada."""
    runtime = Path(tempfile.mkdtemp(prefix="hf-", dir="/tmp"))
    runtime.chmod(0o700)
    monkeypatch.setenv("XDG_RUNTIME_DIR", str(runtime))
    monkeypatch.setenv("WAYLAND_DISPLAY", f"r{os.getpid()}")
    monkeypatch.setenv("HEFESTO_NA_TELA", "1")
    monkeypatch.setenv("GDK_BACKEND", "x11")
    monkeypatch.delenv("XDG_ACTIVATION_TOKEN", raising=False)
    monkeypatch.delenv("DESKTOP_STARTUP_ID", raising=False)
    monkeypatch.delenv("GDK_PIXBUF_MODULE_FILE", raising=False)

    from hefesto_dualsense4unix.utils import single_instance, xdg_paths

    importlib.reload(xdg_paths)
    importlib.reload(single_instance)
    assert xdg_paths.runtime_dir().parent == runtime, (
        "o runtime resolveu fora do berço: o pid file iria para o de verdade"
    )
    try:
        yield runtime
    finally:
        for nome in list(single_instance._HELD_LOCKS):
            single_instance.release(nome)
        shutil.rmtree(runtime, ignore_errors=True)


def _subir_o_primeiro(modo: str, pasta: Path) -> subprocess.Popen[str]:
    """Sobe a janela que já estava aberta e espera ela tomar a vez."""
    piloto = pasta / "piloto_que_fica.py"
    piloto.write_text(_PILOTO_QUE_FICA, encoding="utf-8")
    filho = subprocess.Popen(
        [sys.executable, "-c", _FILHO, str(LANCADOR.parent), modo, str(piloto)],
        stdout=subprocess.PIPE,
        stderr=subprocess.STDOUT,
        text=True,
        # Num cano o stdout do filho é bufferizado em bloco, e o `kill` do fim
        # jogaria fora a linha que o atendente imprimiu.
        env={**os.environ, "PYTHONUNBUFFERED": "1"},
    )
    assert filho.stdout is not None
    limite = time.monotonic() + ESPERA_PELO_FILHO_SEC
    while time.monotonic() < limite:
        linha = filho.stdout.readline()
        if linha.startswith("vez:"):
            assert linha.strip() != "vez:None", "o primeiro não tomou a vez"
            return filho
        if not linha and filho.poll() is not None:
            break
    _enterrar(filho)
    pytest.fail("o primeiro processo não tomou a vez")


def _enterrar(filho: subprocess.Popen[str]) -> str:
    """Mata pelo PID que o teste guardou e devolve o que ele disse."""
    if filho.poll() is None:
        filho.kill()
    saida, _ = filho.communicate(timeout=5)
    return saida or ""


def _piloto_que_denuncia(tmp_path: Path) -> Path:
    """Um piloto de mentira: se ele rodar, uma SEGUNDA janela teria nascido."""
    piloto = tmp_path / "piloto_de_mentira.py"
    marca = tmp_path / "o-piloto-rodou"
    piloto.write_text(
        f"from pathlib import Path\nPath({str(marca)!r}).write_text('rodou')\n",
        encoding="utf-8",
    )
    return piloto


class TestOSegundoCliqueTrazAJanela:
    def test_o_segundo_clique_nao_abre_outra_janela_e_a_primeira_vem_a_frente(
        self, berco: Path, tmp_path: Path, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        _o_filho_tem_o_glib()
        ai = _carregar_o_lancador()
        from hefesto_dualsense4unix.utils import single_instance

        # O filho é um `python -c`, e o crivo de PID reciclado procura
        # "hefesto" na linha de comando — o mesmo dublê dos testes irmãos.
        monkeypatch.setattr(single_instance, "_is_hefesto_dualsense4unix_process", lambda _p: True)
        monkeypatch.setattr(ai, "diario_da_janela", lambda: None)
        monkeypatch.setattr(ai, "achar_o_piloto", lambda: _piloto_que_denuncia(tmp_path))
        monkeypatch.setenv("XDG_ACTIVATION_TOKEN", "token-do-clique")

        primeiro = _subir_o_primeiro("glib", tmp_path)
        try:
            rc = ai.main([])
            vivo = primeiro.poll() is None
        finally:
            saida = _enterrar(primeiro)

        assert rc == 0
        assert not (tmp_path / "o-piloto-rodou").exists(), (
            "o segundo clique rodou o piloto: nasceu uma segunda janela"
        )
        assert vivo, f"o pedido derrubou a janela que já estava aberta:\n{saida}"
        assert "a janela veio para a frente" in saida, saida
        assert "com o token de quem pediu" in saida, saida

    def test_o_pedido_no_meio_do_arranque_espera_e_e_atendido(
        self, berco: Path, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        """O segundo clique antes do GTK não derruba nada e não se perde."""
        _o_filho_tem_o_glib()
        ai = _carregar_o_lancador()
        from hefesto_dualsense4unix.utils import single_instance

        monkeypatch.setattr(single_instance, "_is_hefesto_dualsense4unix_process", lambda _p: True)
        primeiro = _subir_o_primeiro("arranque", berco)
        try:
            assert ai.tomar_a_vez([]) is None
            saida, _ = primeiro.communicate(timeout=ESPERA_PELO_FILHO_SEC)
        finally:
            saida_final = _enterrar(primeiro) if primeiro.poll() is None else ""
        saida = (saida or "") + saida_final
        assert primeiro.returncode == 0, f"a janela morreu no arranque:\n{saida}"
        assert "a janela veio para a frente" in saida, saida

    def test_sem_janela_aberta_a_vez_e_deste_processo_e_nenhum_sinal_muda(
        self, berco: Path
    ) -> None:
        """A vez não mexe em sinal nenhum do processo: o WebKit usa o SIGUSR1."""
        ai = _carregar_o_lancador()
        antes = {s: signal.getsignal(s) for s in (signal.SIGUSR1, signal.SIGUSR2)}
        nome = ai.tomar_a_vez([])
        depois = {s: signal.getsignal(s) for s in (signal.SIGUSR1, signal.SIGUSR2)}

        assert nome == ai.nome_da_vez()
        pid_file = berco / "hefesto-dualsense4unix" / f"{nome}.pid"
        assert pid_file.read_text().strip() == str(os.getpid())
        porta = berco / "hefesto-dualsense4unix" / f"{nome}.porta"
        assert oct(porta.stat().st_mode & 0o777) == "0o600"
        assert depois == antes, "o lançador mexeu num sinal que o WebKit usa"
        arvore = ast.parse(LANCADOR.read_text(encoding="utf-8"))
        importados = {
            apelido.name
            for no in ast.walk(arvore) if isinstance(no, ast.Import)
            for apelido in no.names
        }
        assert "signal" not in importados, "o pedido de vir à frente voltou a ser sinal"


class TestQuemNaoTomaAVez:
    def test_a_janela_desviada_para_o_xvfb_nao_toma_lock(
        self, berco: Path, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        ai = _carregar_o_lancador()
        monkeypatch.delenv("HEFESTO_NA_TELA")
        assert ai.tomar_a_vez([]) == ""
        assert not list(berco.rglob("*.pid"))

    def test_a_janela_oculta_nao_toma_lock(self, berco: Path) -> None:
        ai = _carregar_o_lancador()
        assert ai.tomar_a_vez(["--oculta", "--segundos", "5"]) == ""
        assert not list(berco.rglob("*.pid"))

    def test_o_lock_e_por_tela(self, monkeypatch: pytest.MonkeyPatch) -> None:
        """A janela de um Xvfb de instrumento nunca chama a da tela dela."""
        ai = _carregar_o_lancador()
        monkeypatch.setenv("WAYLAND_DISPLAY", "wayland-1")
        dela = ai.nome_da_vez()
        monkeypatch.delenv("WAYLAND_DISPLAY")
        monkeypatch.setenv("DISPLAY", ":99")
        assert ai.nome_da_vez() != dela
        assert "/" not in ai.nome_da_vez()


def _pedir_em_paralelo(si: ModuleType, nome: str) -> tuple[threading.Thread, list[bool]]:
    """``pedir_a_frente`` numa thread: ele espera a resposta que só a leitura dá."""
    atendido: list[bool] = []
    fio = threading.Thread(target=lambda: atendido.append(si.pedir_a_frente(nome, 4242)))
    fio.start()
    return fio, atendido


def _ler_quando_chegar(si: ModuleType, porta: object) -> str | None | bool:
    limite = time.monotonic() + 5.0
    while time.monotonic() < limite:
        pedido = si.ler_o_pedido(porta)
        if pedido is not False:
            return pedido
        time.sleep(0.02)
    return False


class TestAPortaDeFrente:
    def test_o_pedido_leva_o_token_e_serve_uma_vez(
        self, berco: Path, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        from hefesto_dualsense4unix.utils import single_instance

        porta = single_instance.abrir_a_porta_de_frente("gui-t")
        monkeypatch.setenv("XDG_ACTIVATION_TOKEN", "token-x")
        fio, atendido = _pedir_em_paralelo(single_instance, "gui-t")

        assert _ler_quando_chegar(single_instance, porta) == "token-x"
        fio.join(timeout=5)
        assert atendido == [True], "a janela leu o pedido e não respondeu"
        assert single_instance.ler_o_pedido(porta) is False, "a fila tinha um pedido só"

    def test_sem_token_o_pedido_segue(self, berco: Path) -> None:
        from hefesto_dualsense4unix.utils import single_instance

        porta = single_instance.abrir_a_porta_de_frente("gui-t")
        fio, atendido = _pedir_em_paralelo(single_instance, "gui-t")
        assert _ler_quando_chegar(single_instance, porta) is None
        fio.join(timeout=5)
        assert atendido == [True]

    def test_porta_fechada_nao_levanta(self, berco: Path) -> None:
        """Sem porta, o pedido só se registra e diz que ninguém atendeu."""
        from hefesto_dualsense4unix.utils import single_instance

        assert single_instance.pedir_a_frente("gui-sem-porta", 4242) is False

    def test_porta_que_ninguem_le_nao_conta_como_atendida(
        self, berco: Path, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        """O kernel aceita a conexão de um laço parado; só a resposta prova a janela."""
        from hefesto_dualsense4unix.utils import single_instance

        monkeypatch.setattr(single_instance, "ESPERA_PELA_RESPOSTA_SEC", 0.3)
        single_instance.abrir_a_porta_de_frente("gui-t")
        assert single_instance.pedir_a_frente("gui-t", 4242) is False

    def test_a_porta_velha_de_um_dono_morto_e_trocada(self, berco: Path) -> None:
        from hefesto_dualsense4unix.utils import single_instance

        velha = single_instance.abrir_a_porta_de_frente("gui-t")
        velha.close()
        nova = single_instance.abrir_a_porta_de_frente("gui-t")
        fio, atendido = _pedir_em_paralelo(single_instance, "gui-t")
        assert _ler_quando_chegar(single_instance, nova) is None
        fio.join(timeout=5)
        assert atendido == [True]


class TestAInstanciaUnicaNuncaImpedeAJanela:
    """O lock é conforto; a janela é o produto. Toda falha dele abre a janela."""

    def test_a_janela_travada_nao_segura_o_clique(
        self, berco: Path, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        ai = _carregar_o_lancador()
        from hefesto_dualsense4unix.utils import single_instance

        monkeypatch.setattr(single_instance, "_is_hefesto_dualsense4unix_process", lambda _p: True)
        monkeypatch.setattr(single_instance, "ESPERA_PELA_RESPOSTA_SEC", 0.5)
        travada = _subir_o_primeiro("travada", berco)
        try:
            vez = ai.tomar_a_vez([])
            viva = travada.poll() is None
        finally:
            _enterrar(travada)

        assert vez == "", (
            "a janela aberta não respondeu e o clique ficou sem janela nenhuma"
        )
        assert viva, "o pedido derrubou a janela travada"
        assert ai.nome_da_vez() not in single_instance._HELD_LOCKS

    def test_a_porta_que_nao_abre_solta_o_lock(
        self, berco: Path, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        """Lock sem porta seria pior que nenhum: os cliques seguintes não abririam nada."""
        ai = _carregar_o_lancador()
        from hefesto_dualsense4unix.utils import single_instance

        def _sem_porta(_nome: str) -> object:
            raise OSError("runtime sem escrita (dublê)")

        monkeypatch.setattr(single_instance, "abrir_a_porta_de_frente", _sem_porta)
        assert ai.tomar_a_vez([]) == ""
        assert ai.nome_da_vez() not in single_instance._HELD_LOCKS

    def test_o_lock_preso_sem_pid_abre_a_janela_em_vez_de_quebrar(
        self, berco: Path, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        """Um duplo clique no mesmo milissegundo: o vizinho tem o lock e ainda não o PID."""
        ai = _carregar_o_lancador()
        from hefesto_dualsense4unix.utils import single_instance

        monkeypatch.setattr(single_instance, "SIGTERM_GRACE_SEC", 0.1)
        pid_file = single_instance._pid_file(ai.nome_da_vez())
        vizinho = os.open(str(pid_file), os.O_CREAT | os.O_RDWR, 0o600)
        try:
            fcntl.flock(vizinho, fcntl.LOCK_EX | fcntl.LOCK_NB)
            assert ai.tomar_a_vez([]) == ""
        finally:
            os.close(vizinho)

    def test_a_segunda_volta_acha_o_vizinho(
        self, berco: Path, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        """Na segunda volta o PID já está escrito, e o pedido vai a ele."""
        ai = _carregar_o_lancador()
        from hefesto_dualsense4unix.utils import single_instance

        voltas: list[int] = []
        real = single_instance.acquire_or_bring_to_front

        def _primeira_presa(nome: str, cb: object) -> int | None:
            voltas.append(1)
            if len(voltas) == 1:
                raise RuntimeError("lock preso pelo vizinho (dublê)")
            return real(nome, cb)  # type: ignore[arg-type]

        monkeypatch.setattr(single_instance, "acquire_or_bring_to_front", _primeira_presa)
        assert ai.tomar_a_vez([]) == ai.nome_da_vez()
        assert len(voltas) == 2


class TestOsLoadersDoGdkPixbuf:
    """A cura fina de ``app/arranque``, e o lançador que a chama antes do GTK."""

    @staticmethod
    def _cache(tmp_path: Path, *modulos: str, svg: bool = True) -> Path:
        formato = "svg" if svg else "png"
        linhas = [f'"{m}"\n"{formato}" 5 "gdk-pixbuf" "x" "LGPL"\n' for m in modulos]
        cache = tmp_path / "loaders.cache"
        cache.write_text("".join(linhas), encoding="utf-8")
        return cache

    def test_cache_de_outro_confinamento_sai(
        self, tmp_path: Path, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        from hefesto_dualsense4unix.app import arranque

        monkeypatch.delenv("SNAP", raising=False)
        cache = self._cache(tmp_path, "/snap/terminal/1/usr/lib/libpixbufloader-svg.so")
        monkeypatch.setenv("GDK_PIXBUF_MODULE_FILE", str(cache))
        assert arranque.sanear_loaders_do_gdk_pixbuf() is True
        assert "GDK_PIXBUF_MODULE_FILE" not in os.environ

    def test_cache_proprio_e_completo_fica(
        self, tmp_path: Path, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        from hefesto_dualsense4unix.app import arranque

        modulo = tmp_path / "libpixbufloader-svg.so"
        modulo.write_bytes(b"")
        cache = self._cache(tmp_path, str(modulo))
        monkeypatch.setenv("GDK_PIXBUF_MODULE_FILE", str(cache))
        assert arranque.sanear_loaders_do_gdk_pixbuf() is False
        assert os.environ["GDK_PIXBUF_MODULE_FILE"] == str(cache)

    def test_cache_que_so_le_png_sai(
        self, tmp_path: Path, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        from hefesto_dualsense4unix.app import arranque

        modulo = tmp_path / "libpixbufloader-png.so"
        modulo.write_bytes(b"")
        cache = self._cache(tmp_path, str(modulo), svg=False)
        monkeypatch.setenv("GDK_PIXBUF_MODULE_FILE", str(cache))
        assert arranque.sanear_loaders_do_gdk_pixbuf() is True

    def test_o_caminho_com_o_nome_do_formato_nao_engana_o_crivo(
        self, tmp_path: Path, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        """Um cache só de PNG numa pasta cujo nome traz o formato vetorial sai."""
        from hefesto_dualsense4unix.app import arranque

        pasta = tmp_path / "icones-svg"
        pasta.mkdir()
        modulo = pasta / "libpixbufloader-png.so"
        modulo.write_bytes(b"")
        cache = self._cache(pasta, str(modulo), svg=False)
        cache.write_text(f"# LoaderDir = {pasta}\n" + cache.read_text(), encoding="utf-8")
        monkeypatch.setenv("GDK_PIXBUF_MODULE_FILE", str(cache))
        assert arranque.sanear_loaders_do_gdk_pixbuf() is True
        assert "GDK_PIXBUF_MODULE_FILE" not in os.environ

    def test_dentro_do_proprio_snap_o_cache_serve(self, monkeypatch: pytest.MonkeyPatch) -> None:
        from hefesto_dualsense4unix.app import arranque

        monkeypatch.setenv("SNAP", "/snap/hefesto/3")
        assert arranque.de_outro_confinamento("/snap/hefesto/3/lib/x.so") is False
        monkeypatch.delenv("SNAP")
        assert arranque.de_outro_confinamento("/snap/hefesto/3/lib/x.so") is True
        assert arranque.de_outro_confinamento("/usr/lib/x.so") is False

    def test_o_lancador_saneia_antes_de_abrir_a_janela(
        self, berco: Path, tmp_path: Path, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        """A chamada de verdade: ``main`` do lançador, com o piloto de mentira."""
        ai = _carregar_o_lancador()
        monkeypatch.delenv("SNAP", raising=False)
        monkeypatch.delenv("HEFESTO_NA_TELA")  # sem lock: só a limpeza interessa
        cache = self._cache(tmp_path, "/snap/terminal/1/usr/lib/libpixbufloader-svg.so")
        monkeypatch.setenv("GDK_PIXBUF_MODULE_FILE", str(cache))
        monkeypatch.setattr(ai, "diario_da_janela", lambda: None)
        monkeypatch.setattr(ai, "achar_o_piloto", lambda: _piloto_que_denuncia(tmp_path))
        monkeypatch.setattr(ai, "vestir_a_identidade", lambda _casa: [])
        monkeypatch.setattr(sys, "argv", list(sys.argv))

        assert ai.main([]) == 0
        assert "GDK_PIXBUF_MODULE_FILE" not in os.environ
        assert (tmp_path / "o-piloto-rodou").exists()
