"""A janela registra o próprio fim, o tamanho e o que a tela pinta quando o serviço cala.

Os sintomas de 12/10/2026 (abre e fecha sozinho, altura e largura pulsam, o «cache fantasma»)
não deixavam rastro: em 60 aberturas do `interface.log` não havia uma só linha de fim, de
tamanho ou de estado velho. Cada linha nasce no ponto de código que faz a coisa:

- o fim: `[janela] fechou: <motivo> · aberta há <s> s`, em todo caminho que sai do laço;
- o tamanho: `[janela] tamanho: LxA · monitor n · escala e · estado x`, no máximo uma por segundo;
- a folga do serviço mudo: `[tela] estado velho desde <hora>`, `[tela] vazio`, `[tela] novo`.

MORDIDAS (cada uma reprova um caso): voltar o `destroy` a `Gtk.main_quit` direto; tirar o
`configure-event`; tirar o teto de uma linha por segundo; tirar a anotação das transições da
folga; tirar `fechar_por_sinal` do `main()`; ligar o SIGHUP que o `nohup` deixou ignorado.

A janela de verdade (com barra) só nasce num filho sob `xvfb-run` e sem o `WAYLAND_DISPLAY`
(`na_janela_de_verdade`): no processo do pytest ela iria ao compositor de quem roda.
"""

from __future__ import annotations

import ast
import os
import pathlib
import re
import shutil
import signal
import subprocess
import sys
import textwrap
import time
from types import SimpleNamespace
from typing import Any

import pytest

from tests.conftest import exigir_gi_real

exigir_gi_real("A-JANELA-REGISTRA-O-PROPRIO-TAMANHO-E-O-MOTIVO-DE-FECHAR-01")

from gi.repository import GLib

from hefesto_dualsense4unix.interface import hefesto_vivo as hv
from hefesto_dualsense4unix.interface import janela as jn

RAIZ = pathlib.Path(__file__).resolve().parents[2]
VIVO = RAIZ / "src" / "hefesto_dualsense4unix" / "interface" / "hefesto_vivo.py"
TITULO = "Prova do fim"
PAGINA = f"<!doctype html><html><head><title>{TITULO}</title></head><body>oi</body></html>"
FIM = re.compile(r"\[janela\] fechou: (?P<motivo>.+) · aberta há (?P<s>\d+) s")
TAMANHO = re.compile(
    r"\[janela\] tamanho: (?P<l>\d+)x(?P<a>\d+) · monitor (?P<m>\S+) · escala (?P<e>\d+)"
    r" · estado (?P<estado>[a-zç ]+)"
)


def bombear(ate: Any, prazo: float = 10.0) -> bool:
    contexto = GLib.MainContext.default()
    fim = time.monotonic() + prazo
    while True:
        while contexto.pending():
            contexto.iteration(False)
        if ate():
            return True
        if time.monotonic() >= fim:
            return False
        time.sleep(0.004)


@pytest.fixture
def pagina(tmp_path: pathlib.Path) -> pathlib.Path:
    alvo = tmp_path / "prova.html"
    alvo.write_text(PAGINA, encoding="utf-8")
    return alvo


class Diario:
    """O que a janela escreveu no `stderr` (o `interface.log` de quem usa)."""

    def __init__(self, capsys: pytest.CaptureFixture[str]) -> None:
        self._capsys = capsys
        self.texto = ""

    def linhas(self) -> list[str]:
        self.texto += self._capsys.readouterr().err
        return self.texto.splitlines()

    def com(self, padrao: re.Pattern[str]) -> list[re.Match[str]]:
        return [m for linha in self.linhas() if (m := padrao.search(linha))]


@pytest.fixture
def diario(capsys: pytest.CaptureFixture[str]) -> Diario:
    return Diario(capsys)


def abrir(pagina: pathlib.Path, monkeypatch: pytest.MonkeyPatch, **kwargs: Any) -> jn.JanelaDaAba:
    """A janela OCULTA da casa sobre uma página mínima, neste processo."""
    monkeypatch.delenv(jn.SEM_JANELA_NA_TELA, raising=False)
    return jn.JanelaDaAba(
        arquivo=pagina, titulo_esperado=TITULO, ao_carregar=lambda: None, oculta=True, **kwargs
    )


#: O começo de todo filho de janela de verdade: a página, a janela com barra e a bomba do laço.
PRELUDIO_DO_FILHO = textwrap.dedent(
    """
    import pathlib, sys, time
    from gi.repository import GLib
    from hefesto_dualsense4unix.interface import janela as jn
    tela = jn.JanelaDaAba(
        arquivo=pathlib.Path(sys.argv[1]), titulo_esperado="Prova do fim",
        ao_carregar=lambda: None, oculta=False,
    )
    assert not tela.oculta, "a janela de verdade não abriu"

    def bombear(ate, prazo):
        contexto = GLib.MainContext.default()
        fim = time.monotonic() + prazo
        while not ate() and time.monotonic() < fim:
            while contexto.pending():
                contexto.iteration(False)
            time.sleep(0.004)
        return ate()
    """
)


def na_janela_de_verdade(corpo: str, pagina: pathlib.Path) -> str:
    """Roda `corpo` num filho com a janela de verdade (barra, `configure-event`, `destroy`).

    Sempre num Xvfb próprio e sem o `WAYLAND_DISPLAY`: com ele no ambiente o GTK fala com o
    compositor de quem roda, e a janela com barra nasceria na tela da pessoa, que é uma só.
    Devolve a saída do filho, onde está o diário da janela (o `xvfb-run` junta o `stderr` do
    comando ao `stdout`)."""
    if shutil.which("xvfb-run") is None:  # pragma: no cover — máquina sem xvfb
        pytest.skip("sem `xvfb-run` a janela de verdade nasceria na tela de quem roda")
    script = pagina.parent / "filho_de_janela.py"
    script.write_text(PRELUDIO_DO_FILHO + textwrap.dedent(corpo), encoding="utf-8")
    ambiente = dict(os.environ, PYTHONPATH=str(RAIZ / "src"), GDK_BACKEND="x11")
    for nome in ("WAYLAND_DISPLAY", "DISPLAY", jn.SEM_JANELA_NA_TELA, "HEFESTO_NA_TELA"):
        ambiente.pop(nome, None)
    proc = subprocess.run(
        ["xvfb-run", "-a", sys.executable, str(script), str(pagina)],
        env=ambiente, capture_output=True, text=True, timeout=120, check=False,
    )
    assert proc.returncode == 0, (proc.returncode, proc.stdout[-800:], proc.stderr[-1500:])
    assert "FILHO-OK" in proc.stdout, proc.stdout[-800:]
    return proc.stdout + proc.stderr


# --- 1. o fim ------------------------------------------------------------------------


def test_o_x_da_janela_deixa_a_linha_de_fim(pagina: pathlib.Path) -> None:
    """MORDIDA: ligar o `destroy` direto a `Gtk.main_quit` — a janela fecha calada."""
    erro = na_janela_de_verdade(
        """
        tela.janela.destroy()
        print("FILHO-OK")
        """,
        pagina,
    )
    achadas = [m for linha in erro.splitlines() if (m := FIM.search(linha))]
    assert len(achadas) == 1, erro[-1500:]
    assert achadas[0]["motivo"].startswith("destroy sem pedido")


def test_o_botao_fechar_da_barra_diz_que_foi_o_fechar_e_escreve_uma_vez_so(
    pagina: pathlib.Path,
) -> None:
    """O CLIQUE: o botão «Fechar» da barra, de verdade; o `destroy` que vem depois não repete."""
    erro = na_janela_de_verdade(
        """
        tela._botoes_da_barra["fechar"].clicked()
        bombear(lambda: False, 0.3)
        print("FILHO-OK")
        """,
        pagina,
    )
    achadas = [m for linha in erro.splitlines() if (m := FIM.search(linha))]
    assert [m["motivo"] for m in achadas] == ["Fechar da barra ou do menu do botão direito"], (
        erro[-1500:]
    )


def test_o_fechar_da_janela_oculta_tambem_diz(
    pagina: pathlib.Path, monkeypatch: pytest.MonkeyPatch, diario: Diario
) -> None:
    tela = abrir(pagina, monkeypatch)
    tela.fechar("o menu")
    assert [m["motivo"] for m in diario.com(FIM)] == ["o menu"]
    tela.fechar("de novo")
    assert len(diario.com(FIM)) == 1, "o fim foi dito duas vezes"


def test_a_carga_que_falha_sem_quem_trate_diz_o_motivo(
    pagina: pathlib.Path, monkeypatch: pytest.MonkeyPatch, diario: Diario
) -> None:
    tela = abrir(pagina, monkeypatch)
    tela._morrer("a página não respondeu: teste")
    assert [m["motivo"] for m in diario.com(FIM)] == [
        "a carga falhou (a página não respondeu: teste)"
    ]


def test_o_prazo_agendado_diz_que_foi_o_prazo(
    pagina: pathlib.Path, monkeypatch: pytest.MonkeyPatch, diario: Diario
) -> None:
    tela = abrir(pagina, monkeypatch)
    tela.agendar_saida(0.05)
    assert bombear(lambda: bool(diario.com(FIM)), 3.0), diario.texto
    assert "o prazo de 0.05 s acabou" in diario.texto


def test_a_pagina_que_nao_volta_diz_a_idade_da_janela(
    pagina: pathlib.Path, monkeypatch: pytest.MonkeyPatch, diario: Diario
) -> None:
    """Sem recarga a janela segue aberta, sem página: a linha não é «fechou»."""
    tela = abrir(pagina, monkeypatch)
    tela.recargas = jn.RECARGAS_SEGUIDAS
    tela._viva_desde = time.monotonic()
    tela._morreu_a_pagina(None, SimpleNamespace(value_nick="crashed"))
    assert re.search(
        r"\[janela\] sem recarga: o processo web terminou \(crashed\) · aberta há \d+ s",
        diario.texto + "\n".join(diario.linhas()),
    )
    assert diario.com(FIM) == []


SCRIPT_DO_SINAL = textwrap.dedent(
    """
    import pathlib, sys
    from hefesto_dualsense4unix.interface import janela as jn
    from gi.repository import Gtk
    tela = jn.JanelaDaAba(
        arquivo=pathlib.Path(sys.argv[1]), titulo_esperado="Prova do fim",
        ao_carregar=lambda: None, oculta=True,
    )
    tela.fechar_por_sinal()
    print("pronto", flush=True)
    Gtk.main()
    print("saiu do laco", flush=True)
    """
)


def test_o_sigterm_real_escreve_o_fim_e_sai_pelo_caminho_normal(
    pagina: pathlib.Path, tmp_path: pathlib.Path
) -> None:
    """Num processo filho, com o SIGTERM de verdade: a linha sai e o laço termina (rc 0)."""
    script = tmp_path / "filho.py"
    script.write_text(SCRIPT_DO_SINAL, encoding="utf-8")
    ambiente = dict(os.environ, PYTHONPATH=str(RAIZ / "src"), PYTHONUNBUFFERED="1")
    ambiente.pop(jn.SEM_JANELA_NA_TELA, None)
    filho = subprocess.Popen(
        [sys.executable, str(script), str(pagina)],
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE,
        text=True,
        env=ambiente,
    )
    try:
        assert filho.stdout is not None
        assert filho.stdout.readline().strip() == "pronto"
        filho.send_signal(signal.SIGTERM)
        saida, erro = filho.communicate(timeout=30)
    finally:
        if filho.poll() is None:
            filho.kill()
    assert filho.returncode == 0, (filho.returncode, erro[-800:])
    assert "saiu do laco" in saida
    achadas = [m for linha in erro.splitlines() if (m := FIM.search(linha))]
    assert [m["motivo"] for m in achadas] == ["sinal SIGTERM"], erro[-800:]


def test_os_sinais_de_fim_sao_o_sigterm_e_o_sighup() -> None:
    assert set(jn.SINAIS_DE_FIM) == {signal.SIGTERM, signal.SIGHUP}


SCRIPT_DO_NOHUP = textwrap.dedent(
    """
    import os, pathlib, signal, sys, time
    signal.signal(signal.SIGHUP, signal.SIG_IGN)  # o que o `nohup` do lançador entrega
    from hefesto_dualsense4unix.interface import janela as jn
    from gi.repository import GLib
    tela = jn.JanelaDaAba(
        arquivo=pathlib.Path(sys.argv[1]), titulo_esperado="Prova do fim",
        ao_carregar=lambda: None, oculta=True,
    )
    print("fontes", len(tela.fechar_por_sinal()), flush=True)
    os.kill(os.getpid(), signal.SIGHUP)
    contexto = GLib.MainContext.default()
    fim = time.monotonic() + 0.5
    while time.monotonic() < fim:
        while contexto.pending():
            contexto.iteration(False)
        time.sleep(0.01)
    print("de pe depois do SIGHUP", flush=True)
    """
)


def test_o_sighup_que_o_nohup_ignorou_continua_ignorado(
    pagina: pathlib.Path, tmp_path: pathlib.Path
) -> None:
    """O lançador nasce com `nohup`: o SIGHUP chega ignorado e a janela tem de seguir de pé.

    MORDIDA: ligar todo sinal de `SINAIS_DE_FIM` sem olhar o que o processo herdou — o
    SIGHUP passa a fechar a janela que o `nohup` pediu de pé."""
    script = tmp_path / "nohup.py"
    script.write_text(SCRIPT_DO_NOHUP, encoding="utf-8")
    ambiente = dict(os.environ, PYTHONPATH=str(RAIZ / "src"), PYTHONUNBUFFERED="1")
    ambiente.pop(jn.SEM_JANELA_NA_TELA, None)
    proc = subprocess.run(
        [sys.executable, str(script), str(pagina)],
        env=ambiente, capture_output=True, text=True, timeout=60, check=False,
    )
    assert proc.returncode == 0, (proc.returncode, proc.stderr[-800:])
    assert "fontes 1" in proc.stdout, proc.stdout
    assert "de pe depois do SIGHUP" in proc.stdout, proc.stdout
    assert not [linha for linha in proc.stderr.splitlines() if FIM.search(linha)], proc.stderr


def test_o_piloto_liga_os_sinais_e_a_rede_do_fim_em_volta_do_laco() -> None:
    """MORDIDA: tirar `fechar_por_sinal()` ou a rede do `main()` — o processo da janela
    volta a morrer por SIGTERM, ou a sair do laço, sem uma linha."""
    arvore = ast.parse(VIVO.read_text(encoding="utf-8"))
    main = next(n for n in ast.walk(arvore) if isinstance(n, ast.FunctionDef) and n.name == "main")
    chamadas = [
        n.func.attr
        for n in ast.walk(main)
        if isinstance(n, ast.Call) and isinstance(n.func, ast.Attribute)
    ]
    assert "fechar_por_sinal" in chamadas, "o main() não liga o SIGTERM à linha de fim"
    assert "anotar_o_fim" in chamadas, "o main() perdeu a rede do fim do laço"


# --- 2. o tamanho --------------------------------------------------------------------


def test_o_tamanho_real_da_janela_vira_linha_pelo_configure_event(pagina: pathlib.Path) -> None:
    """MORDIDA: tirar o `connect("configure-event")` — redimensionar a janela fica calado."""
    largura = jn.LARGURA_DO_DESENHO + 137
    erro = na_janela_de_verdade(
        f"""
        bombear(lambda: False, jn.SEGUNDOS_ENTRE_LINHAS_DE_TAMANHO + 0.5)
        tela.janela.resize({largura}, jn.PISO_DA_VISTA + jn.ALTURA_DA_BARRA + 73)
        bombear(lambda: tela.mudancas_de_tamanho >= 2, 8.0)
        bombear(lambda: False, jn.SEGUNDOS_ENTRE_LINHAS_DE_TAMANHO + 0.3)
        print("FILHO-OK")
        """,
        pagina,
    )
    linhas = [m for linha in erro.splitlines() if (m := TAMANHO.search(linha))]
    assert any(int(m["l"]) == largura for m in linhas), (
        "o tamanho novo não chegou ao diário", erro[-1500:])


def test_uma_rajada_de_cinquenta_mudancas_vira_uma_linha_e_a_ultima_no_fim_do_segundo(
    pagina: pathlib.Path, monkeypatch: pytest.MonkeyPatch, diario: Diario
) -> None:
    """MORDIDA: tirar o teto — 50 linhas. Tirar o resto do segundo — o ponto onde a rajada
    parou nunca aparece."""
    tela = abrir(pagina, monkeypatch)
    for i in range(50):
        tela.anotar_o_tamanho(1000 + i, 800)
    linhas = diario.com(TAMANHO)
    assert len(linhas) == 1, diario.texto
    assert (linhas[0]["l"], linhas[0]["a"]) == ("1000", "800")
    assert tela.mudancas_de_tamanho == 50
    assert bombear(
        lambda: len(diario.com(TAMANHO)) >= 2, jn.SEGUNDOS_ENTRE_LINHAS_DE_TAMANHO + 2.0
    ), diario.texto
    bombear(lambda: False, 0.3)
    linhas = diario.com(TAMANHO)
    assert len(linhas) == 2, diario.texto
    assert (linhas[1]["l"], linhas[1]["a"]) == ("1049", "800")


def test_mover_a_janela_sem_mudar_o_tamanho_nao_escreve(
    pagina: pathlib.Path, monkeypatch: pytest.MonkeyPatch, diario: Diario
) -> None:
    tela = abrir(pagina, monkeypatch)
    assert tela.anotar_o_tamanho(1212, 848) is True
    assert len(diario.com(TAMANHO)) == 1
    assert tela.anotar_o_tamanho(1212, 848) is False
    assert len(diario.com(TAMANHO)) == 1
    assert tela.mudancas_de_tamanho == 1


def test_o_estado_da_janela_tem_nome() -> None:
    from gi.repository import Gdk

    assert jn.nome_do_estado(0) == "normal"
    assert jn.nome_do_estado(int(Gdk.WindowState.MAXIMIZED)) == "maximizada"
    assert jn.nome_do_estado(int(Gdk.WindowState.FULLSCREEN)) == "tela cheia"
    assert jn.nome_do_estado(int(Gdk.WindowState.ICONIFIED)) == "minimizada"


def test_o_contador_de_mudancas_vai_ao_tique_lento() -> None:
    texto = VIVO.read_text(encoding="utf-8")
    trecho = texto[texto.index('print(f"[tique lento]') :][:700]
    assert "mudancas_de_tamanho" in trecho


# --- 3. a folga do serviço mudo (o instrumento do «cache fantasma») ---------------------


ESTADO_BOM = {"controles": [{"slot": "a"}]}


def test_a_folga_escreve_cada_transicao_uma_vez_e_nao_muda_o_que_a_tela_mostra() -> None:
    """MORDIDA: tirar a anotação de `_passar_a` — as três transições somem do diário."""
    linhas: list[str] = []
    folga = hv.FolgaDoServicoMudo(anotar=linhas.append)
    demora = TimeoutError("timed out")

    folga.respondeu(ESTADO_BOM)
    assert linhas == [], "a primeira resposta boa não é uma transição"

    for _ in range(folga.folga):
        assert folga.mudo(demora) is ESTADO_BOM
    assert len(linhas) == 1 and re.fullmatch(
        r"\[tela\] estado velho desde \d\d:\d\d:\d\d", linhas[0]
    )

    assert folga.mudo(demora) == {}
    assert folga.mudo(demora) == {}
    assert linhas[1:] == ["[tela] vazio"]

    folga.respondeu(ESTADO_BOM)
    folga.respondeu(ESTADO_BOM)
    assert linhas[2:] == ["[tela] novo"]


def test_o_servico_fora_do_ar_vai_direto_ao_vazio_e_a_linha_sai_no_diario(
    diario: Diario,
) -> None:
    folga = hv.FolgaDoServicoMudo()
    folga.mudo(FileNotFoundError(2, "sem socket"))
    folga.mudo(FileNotFoundError(2, "sem socket"))
    assert [linha for linha in diario.linhas() if linha.startswith("[tela]")] == ["[tela] vazio"]


# --- 4. escondida e à vista ----------------------------------------------------------


def test_a_janela_escondida_diz_quanto_tempo_ficou(
    monkeypatch: pytest.MonkeyPatch, diario: Diario
) -> None:
    estado = SimpleNamespace(
        pausar=lambda: None, retomar=lambda: None, ultimo=lambda: (None, None, 7)
    )
    piloto = SimpleNamespace(_escondida=False, _estado_vivo=estado, _pintada=None)
    monkeypatch.setattr(hv, "_soltar_as_ondas", lambda: None)
    hv.Piloto._a_janela_mudou(piloto, True)  # type: ignore[arg-type]
    piloto._escondida_desde -= 12
    hv.Piloto._a_janela_mudou(piloto, False)  # type: ignore[arg-type]
    linhas = diario.linhas()
    assert "[janela] escondida: o tique parou" in linhas
    assert any(
        re.fullmatch(r"\[janela\] à vista: o tique voltou · escondida por 1[23] s", linha)
        for linha in linhas
    ), linhas
