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
import importlib
import os
import shutil
import signal
import subprocess
import sys
import tempfile
import time
from collections.abc import Iterator
from pathlib import Path
from types import ModuleType

import pytest

RAIZ = Path(__file__).resolve().parents[2]
LANCADOR = RAIZ / "scripts" / "abrir_interface.py"

#: Generoso: o filho é um interpretador novo que importa o pacote inteiro.
ESPERA_PELO_FILHO_SEC = 20.0

#: O filho que toma a vez. ``glib``: o ``main`` do lançador inteiro, com um
#: piloto que segura o laço do GLib por 20 s. ``arranque``: toma a vez e
#: DORME antes de armar a escuta (o pedido chega aí, como um segundo clique no
#: meio do arranque), depois arma e roda o laço por 3 s e sai sozinho.
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


class TestAPortaDeFrente:
    def test_o_pedido_leva_o_token_e_serve_uma_vez(
        self, berco: Path, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        from hefesto_dualsense4unix.utils import single_instance

        porta = single_instance.abrir_a_porta_de_frente("gui-t")
        monkeypatch.setenv("XDG_ACTIVATION_TOKEN", "token-x")
        single_instance.pedir_a_frente("gui-t", 4242)

        assert single_instance.ler_o_pedido(porta) == "token-x"
        assert single_instance.ler_o_pedido(porta) is False, "a fila tinha um pedido só"

    def test_sem_token_o_pedido_segue(self, berco: Path) -> None:
        from hefesto_dualsense4unix.utils import single_instance

        porta = single_instance.abrir_a_porta_de_frente("gui-t")
        single_instance.pedir_a_frente("gui-t", 4242)
        assert single_instance.ler_o_pedido(porta) is None

    def test_porta_fechada_nao_levanta(self, berco: Path) -> None:
        """Sem porta, o pedido só se registra: a janela do outro segue de pé."""
        from hefesto_dualsense4unix.utils import single_instance

        single_instance.pedir_a_frente("gui-sem-porta", 4242)

    def test_a_porta_velha_de_um_dono_morto_e_trocada(self, berco: Path) -> None:
        from hefesto_dualsense4unix.utils import single_instance

        velha = single_instance.abrir_a_porta_de_frente("gui-t")
        velha.close()
        nova = single_instance.abrir_a_porta_de_frente("gui-t")
        single_instance.pedir_a_frente("gui-t", 4242)
        assert single_instance.ler_o_pedido(nova) is None


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
        # O nome do teste não leva a palavra do formato: o `tmp_path` o repete, e
        # o crivo do produto procura a palavra no TEXTO do cache, caminhos
        # inclusive.
        from hefesto_dualsense4unix.app import arranque

        modulo = tmp_path / "libpixbufloader-png.so"
        modulo.write_bytes(b"")
        cache = self._cache(tmp_path, str(modulo), svg=False)
        monkeypatch.setenv("GDK_PIXBUF_MODULE_FILE", str(cache))
        assert arranque.sanear_loaders_do_gdk_pixbuf() is True

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
