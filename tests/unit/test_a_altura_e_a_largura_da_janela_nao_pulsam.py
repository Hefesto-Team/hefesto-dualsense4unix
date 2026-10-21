"""A altura e a largura da janela não pulsam — o instrumento `--conta-tamanho` e o teto dele.

A QUEIXA (D8, 12/10/2026): a janela do início da sessão aparecia «pulsando» em altura e largura.
Três candidatos, escritos antes de qualquer cura:

1. `100dvh` da `.janela` (`topo.html`) acompanha a vista do WebKit, que muda com a barra;
2. o repinte da barra (`_repintar_a_decoracao`, 60 e 300 ms depois de cada `window-state-event`)
   esconde e mostra a barra de título;
3. a folga do serviço mudo troca o conteúdo (estado velho, vazio, novo) com o bloco em outra altura.

O instrumento (`hefesto_vivo.py --conta-tamanho N --cenario parado|mudo|rajada`) põe um
`ResizeObserver` em `.janela`, `.miolo`, `.registro` e na vista, e conta as mudanças DE CAIXA
(a chamada de abertura não conta). Cada cenário roda num processo próprio, num Xvfb próprio e
num lar de mentira: a janela tem barra de verdade e a tela do usuário é uma só.

O QUE SE MEDIU (15/10/2026, Xvfb sem gerenciador de janelas, 09-sistema, 01-jogar, 08-conexoes):
ZERO mudança de caixa nos três cenários, em 30 s cada e em 3 min parado; a rajada de 20 estados
da janela repintou a barra 20 vezes e a altura do miolo ficou nos mesmos números. Nenhum dos três
candidatos reproduziu aqui, então NÃO há cura inventada: esta régua fica como teto (a rajada não
passa de uma mudança de altura do miolo) e como prova de que o instrumento sabe acusar.
O que faltou é o gesto real de maximizar/restaurar num compositor de verdade, que num X sem
gerenciador não existe: fica para a bancada (D8).

MORDIDA: `test_o_instrumento_acusa_a_barra_que_solta_a_altura` troca o repinte por um que MUDA
a altura da janela, de verdade, a cada chamada — e o contador tem de sair do zero. Sem essa
prova o zero dos outros testes não mediria nada.
"""

from __future__ import annotations

import json
import os
import shutil
import subprocess
import sys
import tempfile
import time
from concurrent.futures import Future, ThreadPoolExecutor
from pathlib import Path
from typing import Any

import pytest

from tests.conftest import exigir_gi_real

# O filho (`sys.executable -c _AJUDANTE`) importa o GTK e o WebKit2 de verdade: sem o PyGObject
# real o módulo pula, e sob `HEFESTO_EXIGE_GTK_REAL=1` reprova.
exigir_gi_real("o filho importa `gi` com o GTK 3 e o WebKit2 4.1 de verdade")

RAIZ = Path(__file__).resolve().parents[2]
TIQUES = 100
PAGINA = "09-sistema.html"

pytestmark = pytest.mark.skipif(
    shutil.which("xvfb-run") is None,
    reason="sem `xvfb-run` a janela com barra nasceria na tela dela",
)

#: O processo filho. Ele só roda sob o `xvfb-run` que o teste monta, com o lar de mentira.
_AJUDANTE = r"""
import argparse, json, sys

cenario, aba, tiques, mordida = sys.argv[1], sys.argv[2], int(sys.argv[3]), sys.argv[4]

import gi
gi.require_version("Gtk", "3.0")
gi.require_version("WebKit2", "4.1")
from gi.repository import GLib, Gtk

sys.path.insert(0, sys.argv[5])
import hefesto_vivo as hv
from hefesto_dualsense4unix.interface import janela as ponte_da_tela


def ctl(uniq, t, j):
    return {"uniq": uniq, "connected": True, "transport": t, "player": j, "battery": 64,
            "audio": {"mic_mudo": False}}


ESTADO = {"active_profile": "regua", "gamepad_emulation": {"flavor": "dualsense"},
          "controllers": [ctl("aa:bb:cc:00:00:01", "usb", 1), ctl("aa:bb:cc:00:00:02", "bt", 2)]}
hv.mesa_viva.estado_do_daemon = lambda *a, **k: ESTADO

if mordida:
    def repintar_soltando_a_altura(self):
        # a barra «se refaz» soltando a altura: a janela de verdade muda de tamanho
        largura, altura = self.janela.get_size()
        self.janela.resize(largura, altura + (60 if altura < 900 else -60))
        return False
    ponte_da_tela.JanelaDaAba._repintar_a_decoracao = repintar_soltando_a_altura

args = argparse.Namespace(
    oculta=False, segundos=0.0, passear=False, parada=900, foto="", abre="",
    prova_no_aparelho=False, entre=2500, espera=1200, incluir_perigosos=False,
    prova_clique="", sem_cor=True, prova_de_mockup=False, voltas_por_aba=8,
    teto_de_mockup=-1, sem_cravado=False, sem_selo=False, conta_mutacoes=0,
    conta_tamanho=tiques, cenario=cenario)
piloto = hv.Piloto(args)


def ir():
    if piloto.tela.morreu is not None:
        Gtk.main_quit()
        return False
    if not piloto.tela.na_aba:
        return True
    if aba != hv.PRIMEIRA:
        piloto._ir(aba)
    return False


GLib.timeout_add(120, ir)
GLib.timeout_add(tiques * 100 * 3 + 60000, Gtk.main_quit)
Gtk.main()
print("RESULTADO", json.dumps(piloto.tamanhos, ensure_ascii=False))
piloto.tela.janela.destroy()
"""


def _ambiente_do_lar(lar: Path) -> dict[str, str]:
    """O ambiente de um lar de mentira: sem a sessão, o barramento e o som de quem roda."""
    env = {
        k: v for k, v in os.environ.items()
        if k not in {
            "DISPLAY", "WAYLAND_DISPLAY", "DBUS_SESSION_BUS_ADDRESS", "PULSE_SERVER",
            "PIPEWIRE_REMOTE", "HEFESTO_SEM_JANELA", "HEFESTO_NA_TELA",
        }
    }
    env.update(
        HOME=str(lar), XDG_CONFIG_HOME=str(lar / "c"), XDG_DATA_HOME=str(lar / "d"),
        XDG_STATE_HOME=str(lar / "s"), XDG_CACHE_HOME=str(lar / "k"),
        XDG_RUNTIME_DIR=str(lar / "r"), GDK_BACKEND="x11",
        PYTHONPATH=str(RAIZ / "src"), PYTHONDONTWRITEBYTECODE="1",
    )
    for pasta in ("c", "d", "s", "k", "r"):
        (lar / pasta).mkdir()
    (lar / "r").chmod(0o700)
    return env


def _rodar(cenario: str, mordida: str = "", aba: str = PAGINA) -> tuple[dict[str, Any], str]:
    """Um cenário num processo próprio: Xvfb próprio, lar de mentira, nenhuma sessão do usuário."""
    lar = Path(tempfile.mkdtemp(prefix="vj-", dir="/tmp"))
    try:
        env = _ambiente_do_lar(lar)
        proc = subprocess.run(
            ["xvfb-run", "-a", "-s", "-screen 0 1920x1080x24", sys.executable, "-c", _AJUDANTE,
             cenario, aba, str(TIQUES), mordida,
             str(RAIZ / "src" / "hefesto_dualsense4unix" / "interface")],
            env=env, capture_output=True, text=True, timeout=240, check=False,
        )
    finally:
        shutil.rmtree(lar, ignore_errors=True)
    saida = proc.stdout + proc.stderr
    linhas = [x for x in proc.stdout.splitlines() if x.startswith("RESULTADO ")]
    assert linhas, f"o instrumento não devolveu tabela (rc={proc.returncode}):\n{saida[-2500:]}"
    return json.loads(linhas[-1][len("RESULTADO "):]), saida


def _mudancas(tabela: dict[str, Any], alvo: str) -> int:
    for ficha in tabela["fichas"]:
        if ficha["alvo"] == alvo:
            return int(ficha["n"])
    raise AssertionError(f"o alvo {alvo} não está na tabela: {tabela['fichas']}")


#: Os quatro cenários (os três de medir e a mordida) são independentes: cada um tem Xvfb, lar e
#: processo próprios, e a espera de cada um é de relógio de verdade (cem tiques de 100 ms para o
#: `ResizeObserver` ver se a caixa mexe). Em série eram 4 x 15 s; juntos, a parede é a do mais lento
#: (21/10/2026, A-SUITE-INTEIRA-CABE-EM-VINTE-MINUTOS-01). O teto de tiques NÃO encolheu: o tempo
#: que o instrumento observa é o mesmo, só deixou de ser esperado quatro vezes seguidas.
_CENARIOS = (("parado", ""), ("mudo", ""), ("rajada", ""), ("rajada", "barra-solta-a-altura"))

#: O `xvfb-run -a` escolhe o número da tela olhando os travões; duas escolhas no mesmo instante
#: dão o mesmo número e a segunda morre. A saída escalonada tira essa janela.
_ESCALONA_S = 0.6


@pytest.fixture(scope="module")
def _cenarios() -> dict[tuple[str, str], Future[tuple[dict[str, Any], str]]]:
    futuros: dict[tuple[str, str], Future[tuple[dict[str, Any], str]]] = {}
    with ThreadPoolExecutor(max_workers=len(_CENARIOS)) as pool:
        for nome, mordida in _CENARIOS:
            futuros[(nome, mordida)] = pool.submit(_rodar, nome, mordida)
            time.sleep(_ESCALONA_S)
    return futuros


@pytest.fixture(scope="module")
def parado(_cenarios) -> tuple[dict[str, Any], str]:
    return _cenarios[("parado", "")].result()


@pytest.fixture(scope="module")
def mudo(_cenarios) -> tuple[dict[str, Any], str]:
    return _cenarios[("mudo", "")].result()


@pytest.fixture(scope="module")
def rajada(_cenarios) -> tuple[dict[str, Any], str]:
    return _cenarios[("rajada", "")].result()


@pytest.fixture(scope="module")
def rajada_com_a_barra_solta(_cenarios) -> tuple[dict[str, Any], str]:
    return _cenarios[("rajada", "barra-solta-a-altura")].result()


def test_parada_a_caixa_nao_muda(parado: tuple[dict[str, Any], str]) -> None:
    tabela, _ = parado
    assert ".janela" not in tabela["ausentes"], "a página não tem a `.janela`"
    for alvo in (".janela", ".miolo", ".registro", "(vista)"):
        assert _mudancas(tabela, alvo) == 0, (
            f"{alvo} mudou de caixa com a mesa parada: {tabela['fichas']}")
    assert tabela["janela_gtk"] == 0, "a janela do GTK mudou de tamanho sozinha"


def test_com_o_servico_mudo_a_caixa_nao_muda(mudo: tuple[dict[str, Any], str]) -> None:
    """O cenário tem de ter acontecido (velho, vazio e novo), senão o zero é vazio."""
    tabela, saida = mudo
    for marca in ("[tela] estado velho desde", "[tela] vazio", "[tela] novo"):
        assert marca in saida, f"o cenário `mudo` não chegou a {marca!r}:\n{saida[-1500:]}"
    for alvo in (".janela", ".miolo", ".registro", "(vista)"):
        assert _mudancas(tabela, alvo) == 0, (
            f"{alvo} mudou de caixa na troca velho/vazio/novo: {tabela['fichas']}")


def test_a_rajada_de_estados_da_janela_nao_passa_de_uma_mudanca_de_altura(
    rajada: tuple[dict[str, Any], str],
) -> None:
    """TETO: vinte maximizar/restaurar seguidos repintam a barra vinte vezes, e a altura do miolo
    muda no máximo uma vez (o piso é do gerenciador, não da rajada)."""
    tabela, _ = rajada
    assert tabela["estados_simulados"] == 20, "a rajada não disparou os vinte estados"
    assert _mudancas(tabela, ".miolo") <= 1, (
        f"a rajada fez o miolo pulsar: {tabela['fichas']}")
    assert _mudancas(tabela, ".janela") <= 1
    assert _mudancas(tabela, "(vista)") <= 1


def test_o_instrumento_acusa_a_barra_que_solta_a_altura(
    rajada_com_a_barra_solta: tuple[dict[str, Any], str],
) -> None:
    # D-1510-A-JANELA-NAO-PULSOU-E-FICA-O-INSTRUMENTO
    """MORDIDA: com um repinte que muda a altura da janela de verdade, a mesma rajada sai do zero.

    Sem esta prova os zeros acima valeriam também para um contador que nunca vê nada."""
    tabela, _ = rajada_com_a_barra_solta
    assert tabela["estados_simulados"] == 20
    assert _mudancas(tabela, ".miolo") >= 2, (
        f"o contador não viu uma janela que muda de altura de verdade: {tabela['fichas']}")
    assert tabela["janela_gtk"] >= 2, "o GTK nem registrou a mudança que a mordida causou"


# --- a janela com barra do instrumento nunca nasce na tela de quem chama ----------------------

VIVO = RAIZ / "src" / "hefesto_dualsense4unix" / "interface" / "hefesto_vivo.py"

#: O `--help` sai no `parse_args`, antes de qualquer janela: o que sobra é a tela que o GTK
#: abriu ao ser importado pelo piloto chamado como programa.
_TELA_DO_PROGRAMA = r"""
import os, runpy, sys
de_fora = os.environ["DISPLAY"]
sys.argv = [sys.argv[1], "--conta-tamanho", "5", "--help"]
try:
    runpy.run_path(sys.argv[0], run_name="__main__")
except SystemExit:
    pass
from gi.repository import Gdk
print("TELA", Gdk.Display.get_default().get_name(), "DE-FORA", de_fora)
"""

#: Quem importa o piloto ANTES do desvio (o GTK já abriu a tela de quem chamou) e pede o
#: `--conta-tamanho`: o `main()` tem de recusar antes de existir janela.
_IMPORTOU_ANTES = r"""
import sys
sys.path.insert(0, sys.argv[1])
import hefesto_vivo as hv
sys.argv = ["hefesto_vivo.py", "--conta-tamanho", "5", "--sem-cor", "--sem-ondas"]
try:
    hv.main()
except SystemExit as fim:
    print("SAIU", fim.code)
else:
    print("ABRIU A JANELA")
"""


def _sob_xvfb(codigo: str, *argumentos: str) -> str:
    lar = Path(tempfile.mkdtemp(prefix="vj-", dir="/tmp"))
    try:
        proc = subprocess.run(
            ["xvfb-run", "-a", sys.executable, "-c", codigo, *argumentos],
            env=_ambiente_do_lar(lar), capture_output=True, text=True, timeout=180,
            check=False,
        )
    finally:
        shutil.rmtree(lar, ignore_errors=True)
    return proc.stdout + proc.stderr


def test_o_programa_desvia_a_tela_antes_do_gtk() -> None:
    """O X do `xvfb-run` faz o papel da sessão de quem chama: o GTK do piloto não pode abri-lo.

    MORDIDA: devolver o desvio ao `main()` (depois do `import` do GTK) — a tela aberta vira a
    de fora, que na máquina de quem usa é a tela do usuário."""
    saida = _sob_xvfb(_TELA_DO_PROGRAMA, str(VIVO))
    linha = next((x for x in saida.splitlines() if x.startswith("TELA ")), "")
    assert linha, saida[-1500:]
    _, aberta, _, de_fora = linha.split()
    assert aberta != de_fora, f"o GTK do piloto abriu a tela de quem chamou ({aberta}):\n{saida}"


def test_quem_importou_o_gtk_antes_recebe_a_recusa_e_nenhuma_janela() -> None:
    """MORDIDA: tirar `_recusar_a_tela_que_nao_foi_desviada` do `main()` — o piloto abre a
    janela com barra na tela que já estava aberta."""
    saida = _sob_xvfb(_IMPORTOU_ANTES, str(VIVO.parent))
    assert "ABRIU A JANELA" not in saida, saida[-1500:]
    assert "REPROVA: a janela do `--conta-tamanho` abriria na tela" in saida, saida[-1500:]
