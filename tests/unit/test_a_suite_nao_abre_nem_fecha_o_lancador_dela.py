"""A-SUITE-NAO-ABRE-NEM-FECHA-O-LANCADOR-DELA-01 — a suíte não mexe no lançador dela.

O QUE SE MEDIU (29/09/2026, diário dela, seis vezes desde 25/09): o
`test_o_reiniciar_faz_reset_failed_antes` dublava só o primeiro ato do gesto
«reiniciar» da aba Sistema. O segundo, a reposição do lançador (21/09),
perguntou à máquina dela se a Steam estava aberta, mandou `steam -shutdown` com
o HOME do lar de mentira (uma Steam nova se instalou em `/tmp`), derrubou o
webhelper da Steam dela pelo nome e reabriu `steam`. O teste passava: o produto
engole tudo nesse caminho, e o único sinal era o tempo (38 s).

A CURA MORA NO `tests/conftest.py` (bloco LANCADOR-DE-MENTIRA), e esta régua a
mede pelo LADO DE FORA: nenhuma régua compara o livro da guarda com ele mesmo.
O juiz é um ESPIÃO POR BAIXO do desvio: o `Popen.__init__` de verdade, que o
embrulho da sessão chama por último, é trocado por um que só executa lançador
que mora no diretório dos dublês (ou onde a própria régua deixou). Qualquer
outro caminho de lançador é RECUSADO, com o nome, e não roda. Por isso toda
mordida se prova sem abrir nada: cada mordida tira só a peça mordida, e o resto
da guarda fica armado.
"""

from __future__ import annotations

import contextlib
import inspect
import os
import re
import shutil
import subprocess
import sys
import textwrap
import threading
import time
from collections.abc import Callable, Iterator
from pathlib import Path
from typing import Any

import pytest

from tests import conftest

RAIZ = Path(__file__).resolve().parents[2]
SIGLA = "A-SUITE-NAO-ABRE-NEM-FECHA-O-LANCADOR-DELA-01"

#: A família que o ESPIÃO vigia. Ela é da régua, e não do conftest, de
#: propósito: a mordida tira nomes da tabela do conftest, e o espião tem de
#: continuar vendo-os.
FAMILIA_DO_ESPIAO = frozenset({
    "steam", "steam-native", "steamwebhelper", "com.valvesoftware.Steam",
    "heroic", "com.heroicgameslauncher.hgl", "lutris", "net.lutris.Lutris",
    "xdg-open", "gtk-launch", "gio", "flatpak", "wmctrl",
    "pkill", "killall", "pgrep",
})


def _duble() -> Path:
    duble = conftest.lancador_de_mentira()
    assert duble is not None, (
        "a sessão não armou os dublês dos lançadores: todo ato de lançador da "
        "suíte chega ao lançador de quem a roda"
    )
    return duble


def _executavel(caminho: Path, corpo: str) -> Path:
    caminho.parent.mkdir(parents=True, exist_ok=True)
    caminho.write_text("#!/bin/sh\n" + corpo, encoding="utf-8")
    caminho.chmod(0o755)
    return caminho


class Espiao:
    """O `Popen.__init__` de verdade, com uma porta: lançador só roda do dublê.

    `permitidos` são as pastas de onde um nome da família pode rodar — o
    diretório dos dublês da sessão e o que a régua montou para si. O resto é
    recusado com `PermissionError` e anotado em `recusados`: o produto engole
    a exceção nesses caminhos, e é a lista que reprova.
    """

    def __init__(self, real: Callable[..., None], permitidos: list[Path]) -> None:
        self.real = real
        self.assinatura = inspect.signature(real)
        self.permitidos = {os.path.realpath(p) for p in permitidos}
        self.executados: list[str] = []
        self.recusados: list[str] = []

    def __call__(self, popen: Any, *args: Any, **kwargs: Any) -> None:
        argumentos = self.assinatura.bind(popen, *args, **kwargs).arguments
        programa = argumentos.get("executable")
        if programa is None and not argumentos.get("shell"):
            bruto = argumentos.get("args")
            programa = bruto[0] if isinstance(bruto, (list, tuple)) and bruto else bruto
        if programa is not None:
            texto = os.fsdecode(programa)
            if os.path.basename(texto) in FAMILIA_DO_ESPIAO:
                env = argumentos.get("env")
                caminho = (os.environ if env is None else env).get("PATH", os.defpath)
                resolvido = (
                    texto if os.path.dirname(texto) else shutil.which(texto, path=caminho)
                ) or texto
                self.executados.append(resolvido)
                pasta = os.path.realpath(os.path.dirname(resolvido) or os.curdir)
                if pasta not in self.permitidos:
                    self.recusados.append(resolvido)
                    raise PermissionError(f"espião: {resolvido} fora dos dublês")
        self.real(popen, *args, **kwargs)


@pytest.fixture
def espiao(monkeypatch: pytest.MonkeyPatch) -> Callable[..., Espiao]:
    """Põe o espião por baixo do embrulho da sessão; devolve a fábrica."""
    assert conftest._POPEN_INIT_REAL, "o embrulho do `Popen` da sessão não foi instalado"
    real = conftest._POPEN_INIT_REAL[0]

    def _armar(*permitidos: Path) -> Espiao:
        espiao = Espiao(real, [_duble(), *permitidos])
        # o embrulho lê `_POPEN_INIT_REAL[0]` a cada chamada, pelo nome do módulo
        monkeypatch.setattr(conftest, "_POPEN_INIT_REAL", [espiao])
        return espiao

    return _armar


def _declarar_fora_da_sessao(monkeypatch: pytest.MonkeyPatch, pasta: Path) -> None:
    """`pasta` deixa de contar como temporário da sessão: é o `/usr/games` da
    régua, e funciona numa máquina sem Steam (o CI) igual à dela."""
    original = conftest._e_temporario_da_sessao
    fora = os.path.realpath(pasta)

    def _sem_a_pasta(caminho: str) -> bool:
        real = os.path.realpath(caminho or os.curdir)
        if real == fora or real.startswith(fora + os.sep):
            return False
        return original(caminho)

    monkeypatch.setattr(conftest, "_e_temporario_da_sessao", _sem_a_pasta)


def _esperar_linhas(quantas: int, prazo: float = 15.0) -> list[str]:
    """O livro com pelo menos `quantas` linhas novas — o `Popen` não espera o
    filho, e o dublê escreve quando roda."""
    limite = time.monotonic() + prazo
    while True:
        linhas, _ = conftest._ler_o_livro(conftest._LIVRO_LIDO[0])
        if len(linhas) >= quantas or time.monotonic() > limite:
            return [linha for _, linha in linhas]
        time.sleep(0.05)


# ---------------------------------------------------------------------------
# 1. O caminho medido: os dois atos do «reiniciar»
# ---------------------------------------------------------------------------


class _TempoSemEspera:
    """O `time` do `steam_launch_options` sem o `sleep`: 38 s viram nada.

    O primeiro `sleep` espera o dublê do `steam -shutdown` escrever, para a
    ordem do livro ser a do código e não a da corrida entre dois processos.
    """

    def __init__(self) -> None:
        self._primeiro = True

    def sleep(self, _segundos: float) -> None:
        if self._primeiro:
            self._primeiro = False
            _esperar_linhas(1, prazo=10.0)

    def __getattr__(self, nome: str) -> Any:
        return getattr(time, nome)


def _steam_aberta_ate_o_kill() -> bool:
    """`steam_running` como a medida o viu: de pé até a conferência depois do
    `TERM`, e «fechada» a partir da que vem depois do `KILL` (a janela das
    02:10:29 às 02:10:31, com o cliente dela ainda sem o webhelper)."""
    linhas, _ = conftest._ler_o_livro(conftest._LIVRO_LIDO[0])
    return not any(linha.startswith("pkill -KILL") for _, linha in linhas)


ATOS_DO_REINICIAR = (
    "steam -shutdown",
    "pkill -TERM -f steamrt64/steam",
    "pkill -TERM -x steamwebhelper",
    "pkill -KILL -f steamrt64/steam",
    "pkill -KILL -x steamwebhelper",
    "steam",
)


def test_o_reiniciar_chega_aos_dois_atos_so_pelo_duble(
    monkeypatch: pytest.MonkeyPatch,
    tmp_path: Path,
    espiao: Callable[..., Espiao],
    ato_de_proposito: Callable[..., Any],
    request: pytest.FixtureRequest,
) -> None:
    """O caminho de 29/09 inteiro, com a Steam «aberta» e sem jogo.

    MORDIDA: tire `steam` e `pkill` de `BINARIOS_DE_LANCADOR`. O `steam` do
    PATH passa a ser o que esta régua deixou numa pasta declarada fora da
    sessão, e o espião o recusa pelo caminho.
    """
    duble = _duble()
    fora = tmp_path / "fora"
    for nome in ("steam", "pkill"):
        _executavel(fora / nome, f"echo {nome}-de-fora >> '{tmp_path}/fora.log'\nexit 0\n")
    _declarar_fora_da_sessao(monkeypatch, fora)
    monkeypatch.setenv("PATH", os.pathsep.join([str(fora), os.environ["PATH"]]))

    sys.path.insert(0, str(RAIZ / "src/hefesto_dualsense4unix/interface"))
    import pacotes
    from pacotes import a09_sistema as mod

    from hefesto_dualsense4unix.integrations import reposicao_dos_lancadores as rl
    from hefesto_dualsense4unix.integrations import steam_launch_options as slo
    from tests.unit.test_a_09_sistema_sai_do_desenho import ESTADO, JanelaDeMentira

    janela = JanelaDeMentira()  # type: ignore[no-untyped-call]
    monkeypatch.setattr(mod, "_JANELA_ANTIGA", [janela])
    monkeypatch.setattr(mod, "_autostart", lambda: "enabled")
    monkeypatch.setattr(rl, "jogo_aberto", lambda: False)
    monkeypatch.setattr(rl, "abertos", lambda: [rl.LANCADORES[0]])
    monkeypatch.setattr(slo, "time", _TempoSemEspera())
    monkeypatch.setattr(slo, "steam_running", _steam_aberta_ate_o_kill)
    olho = espiao()

    estado: dict[str, Any] = ESTADO
    ctx = pacotes.Contexto(
        state=estado, mesa=[], conectados=list(estado["controllers"]), estados={})
    acao = pacotes.gesto_da_pagina("09-sistema.html", "reiniciar")
    with ato_de_proposito(*ATOS_DO_REINICIAR):
        acao(ctx, {}, None)
        linhas = _esperar_linhas(len(ATOS_DO_REINICIAR))
        # o espião primeiro: é ele que diz o CAMINHO que ia rodar
        assert not olho.recusados, (
            f"um lançador saiu do dublê e ia rodar de verdade: {olho.recusados}")

    assert not (tmp_path / "fora.log").exists(), "o `steam` de fora da sessão rodou"
    assert olho.executados and all(
        os.path.dirname(c) == str(duble) for c in olho.executados
    ), f"lançador executado fora do diretório dos dublês: {olho.executados}"
    assert janela.comandos[-1][0] == "restart", "o primeiro ato não aconteceu"
    quem = {conftest._partir_a_linha(linha)[1] for linha in linhas}
    assert all(q.startswith(request.node.nodeid) for q in quem), (
        f"o livro não traz o nodeid deste teste: {sorted(quem)}")


# ---------------------------------------------------------------------------
# 2 e 3. O veredito: o teste que chega a um ato reprova, e o ato sem teste
#        reprova a sessão
# ---------------------------------------------------------------------------

_NINHO_DOIS_TESTES = '''
import subprocess

PATH_DE_FORA = {path!r}


def test_chama_o_steam():
    subprocess.run(["steam", "-shutdown"], check=False)


def test_chama_o_steam_sem_o_ambiente():
    # o `env` explícito apaga o $PYTEST_CURRENT_TEST do filho
    subprocess.run(["steam", "-shutdown"], env={{"PATH": PATH_DE_FORA}}, check=False)


def test_abre_sem_esperar():
    # como o `fora_do_servico.abrir`: o `Popen` sai sem esperar o filho
    subprocess.Popen(["xdg-open", "steam://open/main"], env={{"PATH": PATH_DE_FORA}})
'''

_NINHO_DO_FIO = '''
import subprocess
import threading

PATH_DE_FORA = {path!r}


def test_deixa_um_fio(request):
    pronto = threading.Event()

    def _fio():
        pronto.wait(30)
        subprocess.run(["xdg-open", "steam://open/main"],
                       env={{"PATH": PATH_DE_FORA}}, check=False)

    fio = threading.Thread(target=_fio)
    fio.start()

    class _DepoisDoTeste:
        def pytest_runtest_logfinish(self, nodeid, location):
            if nodeid.endswith("test_deixa_um_fio"):
                pronto.set()
                fio.join(30)

    request.config.pluginmanager.register(_DepoisDoTeste(), "depois-do-fio")
'''


def _rodar_o_ninho(tmp_path: Path, nome: str, corpo: str) -> subprocess.CompletedProcess[str]:
    """Um pytest em subprocesso com a guarda desta árvore.

    O `conftest.py` entra por symlink (ver `test_g8_o_lar_de_sessao_…`). O
    subprocesso herda o PATH desta sessão, e o `env` dos testes de dentro é
    esse PATH: nada de verdade abre mesmo que a guarda de dentro falhe — o ato
    cairia no dublê DESTA sessão, e este teste reprovaria pelo veredito.
    """
    quintal = tmp_path / nome
    quintal.mkdir()
    (quintal / "conftest.py").symlink_to(RAIZ / "tests" / "conftest.py")
    (quintal / f"test_{nome}.py").write_text(
        textwrap.dedent(corpo).format(path=os.environ["PATH"]), encoding="utf-8")
    ambiente = dict(os.environ)
    ambiente["PYTHONPATH"] = str(RAIZ / "src")
    ambiente["PYTEST_ADDOPTS"] = ""
    ambiente["HEFESTO_SEM_CANARIO_FS"] = "1"
    return subprocess.run(
        [sys.executable, "-m", "pytest", "-q", "-p", "no:cacheprovider", "-rf"],
        cwd=str(quintal), env=ambiente, capture_output=True, text=True, timeout=300,
    )


def test_o_teste_que_chega_a_um_ato_reprova_alto(tmp_path: Path) -> None:
    """Os três testes de dentro terminam FAILED, cada um com a sigla, o argv
    e o próprio nodeid — inclusive o que apagou o ambiente do filho e o que
    abriu sem esperar (o dublê escreve depois de o corpo do teste acabar).

    MORDIDA 1: tire os três `pytest_runtest_*_do_lancador`. O ninho fecha com
    rc=0.
    MORDIDA 2: atribua pelo `$PYTEST_CURRENT_TEST` da linha em vez do livro
    (em `_fechar_a_fase`, só reprove a linha cujo `quem` é o teste). O
    segundo passa, e esta régua exige os três.
    MORDIDA 3: tire o `_esperar_os_filhos_no_duble()` de `_fechar_a_fase`. O
    ato do terceiro chega depois da fase e vira «fora de teste».
    """
    _duble()
    saida = _rodar_o_ninho(tmp_path, "ninho", _NINHO_DOIS_TESTES)
    texto = saida.stdout + saida.stderr
    assert saida.returncode == 1, f"rc={saida.returncode}\n{texto[-3000:]}"
    for teste in ("test_chama_o_steam", "test_chama_o_steam_sem_o_ambiente",
                  "test_abre_sem_esperar"):
        nodeid = f"test_ninho.py::{teste}"
        assert re.search(rf"^FAILED {re.escape(nodeid)}\b", texto, re.M), (
            f"{nodeid} não reprovou:\n{texto[-3000:]}")
        assert f"{SIGLA}: este teste ({nodeid}, fase call)" in texto, (
            f"a reprovação de {nodeid} não diz a sigla e o nodeid:\n{texto[-3000:]}")
    assert texto.count("`steam -shutdown`") >= 2, texto[-3000:]
    assert "FORA de qualquer teste" not in texto, texto[-3000:]


def test_o_ato_fora_de_teste_reprova_a_sessao(tmp_path: Path) -> None:
    """Um fio chama `xdg-open` depois que o teste acabou: o teste passa, e a
    SESSÃO fecha com rc=1 e o livro.

    MORDIDA: tire o `_lancador_no_fim_da_sessao(session)` de
    `_sessionfinish_das_guardas`. O ninho fecha com rc=0.
    """
    _duble()
    saida = _rodar_o_ninho(tmp_path, "fio", _NINHO_DO_FIO)
    texto = saida.stdout + saida.stderr
    assert "1 passed" in texto, texto[-3000:]
    assert saida.returncode == 1, f"rc={saida.returncode}\n{texto[-3000:]}"
    assert "chegaram FORA de qualquer teste" in texto, texto[-3000:]
    assert "`xdg-open steam://open/main`" in texto, texto[-3000:]


def test_o_fim_da_sessao_espera_o_filho_que_ninguem_esperou(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    """Um fio que abre o lançador SEM esperar, logo antes do fim da sessão: o
    dublê escreve no livro quando roda, e o fim da sessão tem de esperá-lo
    como o fim de cada fase espera. O filho aqui é de mentira e escreve na
    terceira pergunta, que é o atraso de um processo que ainda não rodou.

    MORDIDA: tire o `_esperar_os_filhos_no_duble()` de
    `_lancador_no_fim_da_sessao`. O livro é lido antes do filho, e a sessão
    fecha verde.
    """
    duble = tmp_path / "duble"
    duble.mkdir()
    livro = duble / "atos.txt"
    livro.touch()

    class _FilhoAtrasado:
        voltas = 0

        def poll(self) -> int | None:
            self.voltas += 1
            if self.voltas < 3:
                return None
            with livro.open("a", encoding="utf-8") as arquivo:
                arquivo.write("xdg-open steam://open/main\t\n")
            return 1

    class _Sessao:
        exitstatus = 0
        config = None

    sessao = _Sessao()
    escritos: list[str] = []
    with monkeypatch.context() as troca:
        troca.setattr(conftest, "_LANCADOR_DE_MENTIRA", [duble])
        troca.setattr(conftest, "_SESSAO_DO_LANCADOR", [id(sessao)])
        troca.setattr(conftest, "_LIVRO_LIDO", [0])
        troca.setattr(conftest, "_ATOS_FORA_DE_FASE", [])
        troca.setattr(conftest, "_ATOS_DE_PROPOSITO", set())
        troca.setattr(conftest, "_FILHOS_NO_DUBLE", [_FilhoAtrasado()])
        troca.setattr(conftest, "_escrever_no_terminal",
                      lambda _sessao, linhas: escritos.extend(linhas))
        conftest._lancador_no_fim_da_sessao(sessao)
    assert sessao.exitstatus == 1, "o ato do fio chegou depois da leitura do livro"
    assert any("`xdg-open steam://open/main`" in linha for linha in escritos), escritos


def test_o_ato_de_proposito_nao_e_escape(ato_de_proposito: Callable[..., Any]) -> None:
    """A declaração confere o argv EXATO: um ato diferente do declarado, ou um
    declarado que não chegou, reprova. Aberta a qualquer argv, ela viraria o
    escape que a guarda não tem.

    MORDIDA: tire o `assert chegaram == list(esperados)` de `_declarar`. Os
    dois blocos de dentro deixam de reprovar.
    """
    _duble()
    # o bloco de fora declara o ato de verdade, para o veredito da fase não
    # reprovar esta régua pelo ato que ela chama de propósito
    with (
        ato_de_proposito("steam -shutdown"),
        pytest.raises(AssertionError, match="declarou"),
        ato_de_proposito("steam"),
    ):
        subprocess.run(["steam", "-shutdown"], capture_output=True, timeout=30, check=False)
    with pytest.raises(AssertionError, match="declarou"), ato_de_proposito("steam -shutdown"):
        pass


# ---------------------------------------------------------------------------
# 4 e 5. O Popen: `/usr/games`, o PATH explícito e o dublê do próprio teste
# ---------------------------------------------------------------------------


def test_o_executable_tambem_cai_no_duble(
    monkeypatch: pytest.MonkeyPatch,
    tmp_path: Path,
    espiao: Callable[..., Espiao],
    ato_de_proposito: Callable[..., Any],
) -> None:
    """`Popen(argv, executable=…)` roda o `executable`, e não o `argv[0]`: o
    desvio vale para os dois.

    MORDIDA: em `_desviar_para_o_lancador`, ignore o `executable=` (tire o
    bloco dele). O espião recusa o `steam` de fora pelo caminho.
    """
    fora = tmp_path / "games"
    _executavel(fora / "steam", f"echo rodou >> '{tmp_path}/fora.log'\nexit 0\n")
    _declarar_fora_da_sessao(monkeypatch, fora)
    olho = espiao()
    with ato_de_proposito("steam -shutdown"):
        # o espião recusa com `PermissionError`: a asserção de baixo diz qual
        with contextlib.suppress(PermissionError):
            subprocess.run(
                ["qualquer-nome", "-shutdown"], executable=str(fora / "steam"),
                env={"PATH": f"{fora}{os.pathsep}/usr/bin"},
                capture_output=True, timeout=30, check=False)
        assert not olho.recusados, f"o `steam` de fora da sessão ia rodar: {olho.recusados}"
    assert not (tmp_path / "fora.log").exists(), "o `steam` de fora da sessão rodou"


def test_o_script_de_shell_com_path_explicito_cai_no_duble(
    monkeypatch: pytest.MonkeyPatch,
    tmp_path: Path,
    ato_de_proposito: Callable[..., Any],
) -> None:
    """O `disable_steam_input.sh` fecha a Steam por dentro de um shell, com o
    PATH que o teste lhe deu: o `Popen` só vê o `/bin/sh`, e o que salva é o
    diretório dos dublês entrar no PATH do `env`. O juiz é o `steam` de fora,
    que só escreve o registro dele se rodar.

    MORDIDA: faça `_path_com_o_lancador` devolver o PATH sem mexer. O `steam`
    de fora roda, e o registro dele aparece.
    """
    fora = tmp_path / "games"
    _executavel(fora / "steam", f"echo rodou >> '{tmp_path}/fora.log'\nexit 0\n")
    _declarar_fora_da_sessao(monkeypatch, fora)
    with ato_de_proposito("steam -shutdown"):
        subprocess.run(
            ["/bin/sh", "-c", "steam -shutdown"],
            env={"PATH": f"{fora}{os.pathsep}/usr/bin{os.pathsep}/bin"},
            capture_output=True, timeout=30, check=False)
    assert not (tmp_path / "fora.log").exists(), "o `steam` de fora da sessão rodou"


def test_o_path_explicito_e_o_caminho_absoluto_caem_no_duble(
    monkeypatch: pytest.MonkeyPatch,
    tmp_path: Path,
    espiao: Callable[..., Espiao],
    ato_de_proposito: Callable[..., Any],
) -> None:
    """`/usr/games` não é diretório de sistema para o SOM, e o `steam` desta
    máquina mora lá. Aqui a pasta «de fora» é da régua, declarada fora da
    sessão, para valer igual numa máquina sem Steam.

    MORDIDA: use o critério do SOM — em `_path_com_o_lancador` e em
    `_lancador_no_lugar_de`, só diretório de `_DIRS_DE_SISTEMA` conta. O
    `steam` de fora deixa de ser trocado, e o espião o recusa.
    """
    fora = tmp_path / "games"
    _executavel(fora / "steam", f"echo rodou >> '{tmp_path}/fora.log'\nexit 0\n")
    _declarar_fora_da_sessao(monkeypatch, fora)
    olho = espiao()
    with ato_de_proposito("steam", "steam"):
        for argv in (["steam"], [str(fora / "steam")]):
            try:
                feito = subprocess.run(
                    argv, env={"PATH": f"{fora}{os.pathsep}/usr/bin"},
                    capture_output=True, timeout=30, check=False)
            except PermissionError:
                continue  # o espião recusou: a asserção de baixo diz qual
            assert feito.returncode == 1, "o dublê de um ato sai com rc=1"
        assert not olho.recusados, f"o `steam` de fora da sessão ia rodar: {olho.recusados}"
    assert not (tmp_path / "fora.log").exists(), "o `steam` de fora da sessão rodou"


def test_o_duble_do_proprio_teste_continua_vencendo(
    tmp_path: Path, espiao: Callable[..., Espiao]
) -> None:
    """Um `steam` que o teste montou num temporário da sessão, na frente do
    PATH, é o que roda — é assim que o `disable_steam_input.sh` é medido.

    MORDIDA: em `_lancador_no_lugar_de`, troque o nome onde quer que ele
    resolva (tire a exceção do temporário da sessão). O dublê da sessão rouba
    a chamada, e o livro a acusa.
    """
    proprio = tmp_path / "bin"
    registro = tmp_path / "chamadas-do-teste.txt"
    _executavel(proprio / "steam", f"printf '%s\\n' \"steam $*\" >> '{registro}'\nexit 0\n")
    olho = espiao(proprio)
    feito = subprocess.run(
        ["steam", "-shutdown"],
        env={"PATH": f"{proprio}{os.pathsep}/usr/bin{os.pathsep}/bin"},
        capture_output=True, timeout=30, check=False,
    )
    assert feito.returncode == 0
    assert registro.read_text(encoding="utf-8").splitlines() == ["steam -shutdown"], (
        "o dublê da sessão roubou a chamada do dublê que o teste montou")
    assert olho.executados == [str(proprio / "steam")]


# ---------------------------------------------------------------------------
# 6. As leituras respondem «fechado», e só as de lançador
# ---------------------------------------------------------------------------


def test_a_leitura_de_lancador_resolve_no_duble(espiao: Callable[..., Espiao]) -> None:
    """O caminho: `pgrep`, `flatpak ps` e `wmctrl -lx` com PATH de sistema.

    MORDIDA: tire `pgrep` de `BINARIOS_DE_LANCADOR`. Ele resolve fora dos
    dublês, e o espião o recusa.
    """
    duble = _duble()
    olho = espiao()
    for argv in (["pgrep", "-x", "steamwebhelper"], ["flatpak", "ps"], ["wmctrl", "-lx"]):
        try:
            feito = subprocess.run(
                argv, env={"PATH": "/usr/bin:/bin"},
                capture_output=True, text=True, timeout=30, check=False)
        except OSError:
            continue
        assert feito.stdout == "", f"{argv}: a leitura de lançador responde vazio"
    assert not olho.recusados, f"leitura de lançador fora dos dublês: {olho.recusados}"
    assert olho.executados == [
        str(duble / "pgrep"), str(duble / "flatpak"), str(duble / "wmctrl")]


@pytest.fixture
def duble_com_reais_falsos(tmp_path: Path) -> tuple[Path, Path]:
    """Os dublês escritos num `tmp_path`, com binários «de verdade» FALSOS
    que imprimem uma marca: o juiz é a marca, que só o falso escreve."""
    falsos = tmp_path / "reais"
    reais: dict[str, str | None] = {}
    for nome in ("pgrep", "flatpak", "wmctrl", "pkill", "gio"):
        reais[nome] = str(_executavel(falsos / nome, f"echo MARCA-{nome}\nexit 0\n"))
    dubles = tmp_path / "dubles"
    dubles.mkdir()
    livro = dubles / "atos.txt"
    conftest.escrever_os_dubles_dos_lancadores(dubles, livro, reais)
    return dubles, livro


def test_a_leitura_responde_fechado_so_sobre_lancador(
    duble_com_reais_falsos: tuple[Path, Path],
) -> None:
    """A resposta: sobre lançador, «nenhum» sem perguntar a ninguém; sobre o
    resto, o binário de verdade — `pgrep -x <este processo>` diz o que o
    `pgrep` da máquina diria. Nada depende de a Steam de quem roda estar aberta.

    MORDIDA: faça o dublê `pergunta` (o `pgrep`) repassar tudo — a primeira
    chamada imprime a marca.
    """
    dubles, livro = duble_com_reais_falsos

    def _rodar(*argv: str) -> subprocess.CompletedProcess[str]:
        return subprocess.run(
            [str(dubles / argv[0]), *argv[1:]],
            capture_output=True, text=True, timeout=30, check=False)

    sobre_lancador = (
        ("pgrep", "-x", "steamwebhelper"),
        ("pgrep", "-af", "steamrt64/steam"),
        ("pgrep", "-x", "com.heroicgameslauncher.hgl"),
        ("flatpak", "ps", "--columns=application,pid"),
        ("flatpak", "list", "--app"),
        ("wmctrl", "-lx"),
    )
    for argv in sobre_lancador:
        feito = _rodar(*argv)
        assert "MARCA" not in feito.stdout, f"{argv} perguntou à máquina: {feito.stdout!r}"
        esperado = 1 if argv[0] == "pgrep" else 0
        assert feito.returncode == esperado, f"{argv}: rc={feito.returncode}"
    assert _rodar("flatpak", "info", "com.valvesoftware.Steam").returncode == 1, (
        "`flatpak info` sobre lançador responde «não instalado»")

    for argv in (("pgrep", "-x", Path(sys.executable).name),
                 ("flatpak", "--version"), ("pkill", "-x", "um-processo-qualquer"),
                 ("gio", "info", "/")):
        feito = _rodar(*argv)
        assert feito.stdout.strip() == f"MARCA-{argv[0]}", (
            f"{argv}: o que não é lançador vai ao binário de verdade: {feito.stdout!r}")
    assert livro.read_text(encoding="utf-8") == "", "leitura não é ato"


def test_o_ato_nao_chega_ao_binario_de_verdade(
    duble_com_reais_falsos: tuple[Path, Path],
) -> None:
    """`pkill` de lançador, `flatpak run`, `wmctrl -ia` e `gio open` vão ao
    livro com rc=1, e o binário de verdade nunca é chamado."""
    dubles, livro = duble_com_reais_falsos
    atos = (
        ("pkill", "-TERM", "-x", "steamwebhelper"),
        ("pkill", "-KILL", "-f", "steamrt64/steam"),
        ("flatpak", "run", "net.lutris.Lutris"),
        ("flatpak", "kill", "com.heroicgameslauncher.hgl"),
        ("wmctrl", "-ia", "0x01"),
        ("gio", "open", "steam://open/main"),
        ("xdg-open", "steam://open/main"),
        ("heroic",),
    )
    for argv in atos:
        feito = subprocess.run(
            [str(dubles / argv[0]), *argv[1:]],
            capture_output=True, text=True, timeout=30, check=False)
        assert feito.returncode == 1 and "MARCA" not in feito.stdout, argv
    anotados = [linha.split("\t")[0] for linha in livro.read_text(encoding="utf-8").splitlines()]
    assert anotados == [" ".join(a) for a in atos]


# ---------------------------------------------------------------------------
# 7. O censo: todo nome de lançador que o produto usa tem dublê
# ---------------------------------------------------------------------------

#: A família do censo, mais larga que a tabela de propósito: lançadores e
#: abridores que o produto NÃO usa hoje também entram, para que o primeiro uso
#: reprove aqui em vez de passar calado.
FAMILIA = (
    r"steam|steam-native|steamwebhelper|com\.valvesoftware\.Steam"
    r"|heroic|com\.heroicgameslauncher\.hgl|lutris|net\.lutris\.Lutris"
    r"|bottles|com\.usebottles\.bottles|legendary|minigalaxy|itch|retroarch"
    r"|xdg-open|gtk-launch|gio|kde-open\d*|kioclient\d*|exo-open|gnome-open|gvfs-open"
    r"|wmctrl|xdotool|flatpak|pkill|killall|pgrep"
)

#: `argv[0]` literal no Python: o primeiro elemento de uma lista. Tupla não
#: entra: `SemCenso("retroarch", …)` e `("legendary", "Epic", …)` são dado.
_ARGV0_PY = re.compile(rf"\[\s*[\"']({FAMILIA})[\"']")
#: E a constante de binário (`STEAM_BINARY = "steam"`).
_CONSTANTE_PY = re.compile(rf"^[A-Z_]*BINARY\s*=\s*[\"']({FAMILIA})[\"']", re.M)
#: O comando no shell: começo da linha, ou depois de `;`, `&&`, `||`, `|`,
#: `$(`, crase, ou de quem só repassa (`exec`, `nohup`, `setsid`, `sudo`).
_COMANDO_SH = re.compile(
    rf"(?:^|[;&|`(]|\$\()\s*(?:(?:exec|nohup|setsid|sudo|command)\s+(?:-\S+\s+)*)*"
    rf"({FAMILIA})(?=\s|$|;|\)|`)",
    re.M,
)


def _nomes_dos_donos() -> dict[str, str]:
    """Todo nome de lançador que as tabelas dos donos declaram, com a origem."""
    from hefesto_dualsense4unix.integrations import reposicao_dos_lancadores as rl
    from hefesto_dualsense4unix.integrations import steam_launcher as sl
    from hefesto_dualsense4unix.interface import desenho_dos_lancadores as dl

    nomes: dict[str, str] = {}
    for lancador in rl.LANCADORES:
        for nome in (*lancador.processos, lancador.flatpak, lancador.nativo):
            if nome:
                nomes[nome] = f"reposicao_dos_lancadores.LANCADORES ({lancador.chave})"
    for nome in (*dl.A_STEAM.atalhos, *dl.A_STEAM.comandos):
        nomes[nome] = "desenho_dos_lancadores.A_STEAM"
    nomes[sl.STEAM_BINARY] = "steam_launcher.STEAM_BINARY"
    nomes[sl.WMCTRL_BINARY] = "steam_launcher.WMCTRL_BINARY"
    return nomes


def _nomes_no_codigo() -> dict[str, str]:
    """Todo `argv[0]` literal da família em `src/` e `scripts/`, com o arquivo."""
    achados: dict[str, str] = {}
    arquivos = [*(RAIZ / "src").rglob("*.py"), RAIZ / "install.sh", RAIZ / "uninstall.sh"]
    arquivos += [p for p in (RAIZ / "scripts").rglob("*")
                 if p.is_file() and p.suffix in {".sh", ".py", ".bash", ""}]
    for arquivo in arquivos:
        if not arquivo.is_file():
            continue
        texto = arquivo.read_text(encoding="utf-8", errors="replace")
        relativo = str(arquivo.relative_to(RAIZ))
        if arquivo.suffix == ".py":
            nomes = _ARGV0_PY.findall(texto) + _CONSTANTE_PY.findall(texto)
        else:
            sem_comentario = "\n".join(
                linha for linha in texto.splitlines() if not linha.lstrip().startswith("#"))
            nomes = _COMANDO_SH.findall(sem_comentario)
        for nome in nomes:
            achados.setdefault(nome, relativo)
    return achados


def _fora_da_tabela() -> list[str]:
    tabela = set(conftest.BINARIOS_DE_LANCADOR)
    faltam = [
        f"{nome} (de {origem})"
        for nome, origem in {**_nomes_dos_donos(), **_nomes_no_codigo()}.items()
        if nome not in tabela
    ]
    raizes = tuple(conftest.RAIZES_DE_LANCADOR)
    sem_raiz = [
        f"{nome} (de {origem}): o `pgrep`/`pkill` de mentira não o reconhece"
        for nome, origem in _nomes_dos_donos().items()
        if origem != "steam_launcher.WMCTRL_BINARY"
        and not any(r in nome.lower() for r in raizes)
    ]
    return sorted(faltam) + sorted(sem_raiz)


def test_todo_lancador_do_produto_e_dos_scripts_tem_duble() -> None:
    """MORDIDA: tire `xdg-open` de `BINARIOS_DE_LANCADOR`; o censo reprova
    nomeando o arquivo que o usa."""
    faltam = _fora_da_tabela()
    assert not faltam, (
        "nome de lançador usado pelo produto sem dublê na sessão da suíte: "
        f"{faltam}. Acrescente-o a `BINARIOS_DE_LANCADOR` em `tests/conftest.py`."
    )


def test_o_censo_acha_os_lancadores_que_ja_se_sabe_que_existem() -> None:
    """A régua do censo não pode virar um SIM para tudo: `src/` chama `steam`,
    `xdg-open`, `pkill`, `pgrep` e `flatpak`, e os scripts de shell fecham a
    Steam (`disable_steam_input.sh`) e abrem a mesa no navegador
    (`mesa-de-medicao.sh`)."""
    no_codigo = _nomes_no_codigo()
    assert {"steam", "xdg-open", "pkill", "pgrep", "flatpak", "wmctrl"} <= set(no_codigo)
    assert {"steamwebhelper", "com.heroicgameslauncher.hgl", "net.lutris.Lutris",
            "com.valvesoftware.Steam", "steam-native"} <= set(_nomes_dos_donos())


def test_um_lancador_novo_no_dono_reprova_o_censo(monkeypatch: pytest.MonkeyPatch) -> None:
    """A mordida do censo, rodando sempre: um lançador acrescentado à tabela
    do dono aparece no censo pelo nome."""
    from hefesto_dualsense4unix.integrations import reposicao_dos_lancadores as rl

    novo = rl.Lancador("bottles", "Bottles", ("bottles",), flatpak="com.usebottles.bottles")
    monkeypatch.setattr(rl, "LANCADORES", (*rl.LANCADORES, novo))
    faltam = _fora_da_tabela()
    assert any(f.startswith("bottles ") for f in faltam), faltam
    assert any(f.startswith("com.usebottles.bottles ") for f in faltam), faltam


# ---------------------------------------------------------------------------
# O som não mudou: o embrulho é um só, e o escape do som não leva o lançador
# ---------------------------------------------------------------------------


def test_o_embrulho_do_popen_e_um_so() -> None:
    """Dois embrulhos encadeados seriam dois donos da mesma porta."""
    assert len(conftest._POPEN_INIT_REAL) == 1
    assert subprocess.Popen.__init__.__code__.co_name == "_init_da_sessao"


def test_os_dubles_dos_lancadores_moram_fora_do_som() -> None:
    """O escape do SOM (`HEFESTO_SOM_DE_VERDADE=1`) desliga só a tabela do som:
    os lançadores moram noutro diretório, e o PATH da sessão acha os deles."""
    duble = _duble()
    assert duble != conftest.som_de_mentira()
    for nome in conftest.BINARIOS_DE_LANCADOR:
        assert shutil.which(nome) == str(duble / nome), nome


@pytest.fixture(autouse=True)
def _sem_fio_pendurado() -> Iterator[None]:
    """Nenhum fio desta régua sobrevive a ela."""
    antes = set(threading.enumerate())
    yield
    for fio in set(threading.enumerate()) - antes:
        fio.join(5)
