"""A TRAVA MÚTUA (29/08/2026) — os dois Hefestos não seguram o mesmo controle.

Pedido dela: *"temos que evitar estar rodando os daemon ao mesmo tempo que a
versão dev"*, com a exigência de ser ESTRUTURAL — não pode depender de ela
lembrar de desligar.

COMO ESTA RÉGUA MORDE, e por que ela não mede "outra coisa"
------------------------------------------------------------
O teste que vale é o par:

- ``test_a_segunda_casa_recusa_com_a_trava`` — dois PROCESSOS de verdade, com
  ``flock`` de verdade, em casas diferentes: o segundo **recusa**;
- ``test_arrancada_a_trava_as_duas_casas_sobem`` — o MESMO par, com a
  conferência arrancada do caminho de boot: as duas sobem.

Sem o segundo, um verde no primeiro provaria só que o driver escreve
"RECUSOU" — não que a trava é o que recusa.

E há uma terceira, que é a que protege o produto DELA:
``test_o_reinicio_da_mesma_casa_nao_e_recusado``. Uma trava ingênua ("arquivo
travado ⇒ recusa") reprovaria o ``systemctl --user restart`` de todo dia, que
é literalmente "um segundo daemon subindo com o primeiro no ar".
"""
from __future__ import annotations

import os
import signal
import subprocess
import sys
import time
from collections.abc import Iterator
from pathlib import Path

import pytest

from hefesto_dualsense4unix.utils import trava_do_aparelho as trava
from hefesto_dualsense4unix.utils.xdg_paths import (
    FAKE_ENV_VAR,
    IPC_SOCKET_ENV_VAR,
)

#: O daemon-de-mentira que segura a trava. Faz o que `run_daemon` faz e nada
#: mais: confere, toma, e fica vivo. `--sem-trava` é a ARRANCADA — pula a
#: conferência e mais nada, que é exatamente a linha que este teste mede.
DRIVER = """
import os, sys, time
from hefesto_dualsense4unix.utils import trava_do_aparelho as t

if "--sem-trava" not in sys.argv:
    try:
        t.conferir_antes_do_takeover()
    except t.OutraCasaComOAparelhoError as exc:
        print("RECUSOU", flush=True)
        sys.stderr.write(exc.recado + "\\n")
        sys.stderr.flush()
        raise SystemExit(3)
t.tomar()
print("SUBIU", flush=True)
time.sleep(float(os.environ.get("SEGURAR_S", "20")))
"""


@pytest.fixture(autouse=True)
def _runtime_isolado(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> Iterator[Path]:
    """XDG_RUNTIME_DIR próprio — o conftest NÃO isola este, de propósito.

    Sem isto, cada teste daqui sondaria (e poderia TOMAR) a trava real da
    máquina de quem roda a suíte, que é a trava do daemon dela.
    """
    runtime = tmp_path / "runtime"
    runtime.mkdir(parents=True, exist_ok=True)
    monkeypatch.setenv("XDG_RUNTIME_DIR", str(runtime))
    # A suíte inteira roda com FAKE=1 (conftest), e daemon fake NÃO trava.
    # Medir a trava exige o modo de produção.
    monkeypatch.delenv(FAKE_ENV_VAR, raising=False)
    monkeypatch.delenv(IPC_SOCKET_ENV_VAR, raising=False)
    monkeypatch.delenv(trava.VARIANTE_ENV, raising=False)
    yield runtime
    trava.soltar()


def _ambiente(runtime: Path, casa: str, segurar: str = "20") -> dict[str, str]:
    env = dict(os.environ)
    env["XDG_RUNTIME_DIR"] = str(runtime)
    env["SEGURAR_S"] = segurar
    env.pop(FAKE_ENV_VAR, None)
    env.pop(IPC_SOCKET_ENV_VAR, None)
    if casa == trava.CASA_DEV:
        env[trava.VARIANTE_ENV] = "dev"
    else:
        env.pop(trava.VARIANTE_ENV, None)
    return env


def _subir(
    runtime: Path, casa: str, *, sem_trava: bool = False
) -> subprocess.Popen[str]:
    cmd = [sys.executable, "-c", DRIVER]
    if sem_trava:
        cmd.append("--sem-trava")
    return subprocess.Popen(
        cmd,
        env=_ambiente(runtime, casa),
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE,
        text=True,
    )


def _primeira_linha(proc: subprocess.Popen[str], limite_s: float = 20.0) -> str:
    """Lê a primeira linha do stdout do driver, ou falha o teste no estouro."""
    fim = time.monotonic() + limite_s
    assert proc.stdout is not None
    while time.monotonic() < fim:
        linha = proc.stdout.readline()
        if linha:
            return linha.strip()
        if proc.poll() is not None:
            return ""
    raise AssertionError("o driver não disse nada dentro do limite")


def _encerrar(*procs: subprocess.Popen[str]) -> None:
    for p in procs:
        if p.poll() is None:
            p.kill()
        p.wait(timeout=10)


# ---------------------------------------------------------------------------
# A MORDIDA, parte 1: com a trava, a segunda casa recusa
# ---------------------------------------------------------------------------
def test_a_segunda_casa_recusa_com_a_trava(_runtime_isolado: Path) -> None:
    primeiro = _subir(_runtime_isolado, trava.CASA_ESTAVEL)
    try:
        assert _primeira_linha(primeiro) == "SUBIU"

        segundo = _subir(_runtime_isolado, trava.CASA_DEV)
        try:
            assert _primeira_linha(segundo) == "RECUSOU"
            segundo.wait(timeout=10)
            assert segundo.returncode == 3
            recado = (segundo.stderr.read() if segundo.stderr else "")
            # A frase NOMEIA o outro Hefesto, dá o pid e o gesto que libera.
            assert "Hefesto ESTÁVEL está com o aparelho" in recado
            assert f"pid {primeiro.pid}" in recado
            assert "Desligar até eu reativar" in recado
            assert "hefesto-chave.sh estavel off" in recado
        finally:
            _encerrar(segundo)
    finally:
        _encerrar(primeiro)


# ---------------------------------------------------------------------------
# A MORDIDA, parte 2: ARRANCADA a trava, as duas sobem
# ---------------------------------------------------------------------------
def test_arrancada_a_trava_as_duas_casas_sobem(_runtime_isolado: Path) -> None:
    """Se este teste falhar, a régua acima está medindo outra coisa."""
    primeiro = _subir(_runtime_isolado, trava.CASA_ESTAVEL)
    try:
        assert _primeira_linha(primeiro) == "SUBIU"
        segundo = _subir(_runtime_isolado, trava.CASA_DEV, sem_trava=True)
        try:
            assert _primeira_linha(segundo) == "SUBIU"
            assert primeiro.poll() is None, "o primeiro continua vivo"
            # Os dois daemons no ar ao mesmo tempo — a disputa que ela relatou
            # como "o controle não funciona sem explicação".
        finally:
            _encerrar(segundo)
    finally:
        _encerrar(primeiro)


# ---------------------------------------------------------------------------
# O que a trava NÃO pode quebrar: o reinício da própria casa
# ---------------------------------------------------------------------------
def test_o_reinicio_da_mesma_casa_nao_e_recusado(_runtime_isolado: Path) -> None:
    """BUG-MULTI-INSTANCE-01 preservado — senão o daemon dela nunca reinicia."""
    dono = _subir(_runtime_isolado, trava.CASA_ESTAVEL)
    try:
        assert _primeira_linha(dono) == "SUBIU"
        # Mesmo processo de teste, MESMA casa: a conferência tem de passar em
        # silêncio, para o `acquire_or_takeover` fazer o trabalho dele.
        trava.conferir_antes_do_takeover()
    finally:
        _encerrar(dono)


def test_a_sonda_ve_a_casa_e_o_pid_de_quem_segura(_runtime_isolado: Path) -> None:
    dono = _subir(_runtime_isolado, trava.CASA_DEV)
    try:
        assert _primeira_linha(dono) == "SUBIU"
        quem = trava.dono_agora()
        assert quem is not None
        assert quem.casa == trava.CASA_DEV
        assert quem.pid == dono.pid
        assert quem.nome == "Hefesto de DESENVOLVIMENTO"
    finally:
        _encerrar(dono)


# ---------------------------------------------------------------------------
# Os dois casos que separam esta trava de uma checagem de arquivo
# ---------------------------------------------------------------------------
def test_kill_9_no_dono_nao_deixa_trava_pendurada(_runtime_isolado: Path) -> None:
    """O kernel solta o flock na saída; o TEXTO fica, e não pode mentir."""
    dono = _subir(_runtime_isolado, trava.CASA_DEV)
    assert _primeira_linha(dono) == "SUBIU"
    dono.kill()
    dono.wait(timeout=10)
    # O arquivo continua lá, com o pid de um morto escrito dentro.
    assert trava.caminho_da_trava().exists()
    assert trava.dono_agora() is None
    trava.conferir_antes_do_takeover()  # não levanta


def test_dono_congelado_com_sigstop_continua_recusando(
    _runtime_isolado: Path,
) -> None:
    """O caso perigoso: o outro daemon vivo mas parado.

    É o mesmo formato do `daemon.pause`, que **não solta o aparelho** (a
    docstring de `daemon/lifecycle.py` diz: *"O daemon segue vivo: lê
    estado/bateria, publica STATE_UPDATE e atende o IPC"*). A trava é do
    PROCESSO, não do "está despachando" — por isso ela pega este caso, e uma
    sonda por IPC não pegaria.
    """
    dono = _subir(_runtime_isolado, trava.CASA_DEV)
    try:
        assert _primeira_linha(dono) == "SUBIU"
        os.kill(dono.pid, signal.SIGSTOP)
        try:
            with pytest.raises(trava.OutraCasaComOAparelhoError):
                trava.conferir_antes_do_takeover()
        finally:
            os.kill(dono.pid, signal.SIGCONT)
    finally:
        _encerrar(dono)


# ---------------------------------------------------------------------------
# Onde a trava NÃO se aplica — e isto protege o daemon dela da suíte
# ---------------------------------------------------------------------------
def test_daemon_fake_nao_trava(
    _runtime_isolado: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    """A suíte sobe daemons fake às centenas. Se eles tomassem a trava global,
    rodar pytest impediria o daemon de verdade dela de subir."""
    monkeypatch.setenv(FAKE_ENV_VAR, "1")
    assert trava.a_trava_se_aplica() is False
    assert trava.tomar() is False
    assert not trava.caminho_da_trava().exists()


def test_socket_isolado_nao_trava(
    _runtime_isolado: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    monkeypatch.setenv(IPC_SOCKET_ENV_VAR, "smoke-qualquer.sock")
    assert trava.a_trava_se_aplica() is False


def test_a_casa_fake_nao_recusa_nem_com_a_outra_no_ar(
    _runtime_isolado: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    dono = _subir(_runtime_isolado, trava.CASA_ESTAVEL)
    try:
        assert _primeira_linha(dono) == "SUBIU"
        monkeypatch.setenv(FAKE_ENV_VAR, "1")
        trava.conferir_antes_do_takeover()  # silêncio, e é de propósito
    finally:
        _encerrar(dono)


# ---------------------------------------------------------------------------
# O arquivo mora FORA do slug — que é a causa raiz que este módulo cura
# ---------------------------------------------------------------------------
def test_a_trava_nao_mora_dentro_da_casa(_runtime_isolado: Path) -> None:
    """Se o caminho voltar a ter o slug, as duas casas param de se ver — que é
    exatamente o defeito medido no `single_instance`."""
    from hefesto_dualsense4unix.utils.xdg_paths import runtime_dir

    caminho = trava.caminho_da_trava()
    assert caminho.parent == _runtime_isolado
    assert trava.SLUG_DA_CASA[trava.CASA_ESTAVEL] not in str(caminho)
    assert trava.SLUG_DA_CASA[trava.CASA_DEV] not in str(caminho)
    # E o contraste: o runtime_dir do produto TEM o slug.
    assert trava.SLUG_DA_CASA[trava.CASA_ESTAVEL] in str(runtime_dir())


def test_o_slug_da_casa_estavel_e_o_que_o_produto_usa(_runtime_isolado: Path) -> None:
    """A frase da recusa procura o `paused.flag` da OUTRA casa por este slug.
    Se ele divergir do slug real, a variante "PAUSADO" some sem avisar."""
    from hefesto_dualsense4unix.utils.xdg_paths import config_dir

    assert config_dir().name == trava.SLUG_DA_CASA[trava.CASA_ESTAVEL]


def test_a_casa_vem_da_mesma_regra_da_identidade(
    _runtime_isolado: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    """`HEFESTO_VARIANTE` decide, com a MESMA normalização de
    `utils/identidade.identidade_de` — qualquer outro valor cai no estável."""
    assert trava.casa_atual() == trava.CASA_ESTAVEL
    monkeypatch.setenv(trava.VARIANTE_ENV, "dev")
    assert trava.casa_atual() == trava.CASA_DEV
    monkeypatch.setenv(trava.VARIANTE_ENV, "  DEV  ")
    assert trava.casa_atual() == trava.CASA_DEV
    monkeypatch.setenv(trava.VARIANTE_ENV, "devv")
    assert trava.casa_atual() == trava.CASA_ESTAVEL


def test_a_frase_de_pausado_e_diferente_da_comum(
    _runtime_isolado: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    """A tela do outro app diz "pausado", e pausado ele CONTINUA com o
    aparelho. Sem esta variante, o gesto óbvio (despausar) não resolve e a
    frase não explica por quê."""
    dono = trava.Dono(casa=trava.CASA_DEV, pid=4242)
    monkeypatch.setattr(trava, "_esta_pausado", lambda _casa: False)
    comum = trava.recado_da_recusa(dono, trava.CASA_ESTAVEL)
    monkeypatch.setattr(trava, "_esta_pausado", lambda _casa: True)
    pausado = trava.recado_da_recusa(dono, trava.CASA_ESTAVEL)

    assert "brigam pelo hidraw" in comum
    assert "PAUSADO" not in comum
    assert "PAUSADO" in pausado
    assert "não solta o aparelho" in pausado
    assert "hefesto-chave.sh dev off" in pausado


# ---------------------------------------------------------------------------
# A SEGUNDA RÉGUA: o pid file da outra casa — a que funciona HOJE
# ---------------------------------------------------------------------------
#
# O `flock` só enxerga quem TOMA a trava, isto é, quem já tem este módulo.
# MEDIDO em 29/08/2026: o Hefesto de dev roda na máquina dela a partir de uma
# árvore que ainda não o tem. Sem esta régua, a trava seria uma cura escrita e
# nunca ligada até o outro lado ser atualizado.
DAEMON_DE_MENTIRA = "import time; time.sleep(60)  # hefesto daemon de mentira"


def _daemon_da_outra_casa(
    runtime: Path, casa: str, *, com_variante: bool = True, hefesto_no_nome: bool = True
) -> subprocess.Popen[str]:
    """Um processo vivo com pid file de daemon — e SEM tomar o flock."""
    codigo = (
        DAEMON_DE_MENTIRA
        if hefesto_no_nome
        else "import time; time.sleep(60)  # so um processo qualquer"
    )
    env = dict(os.environ)
    env["XDG_RUNTIME_DIR"] = str(runtime)
    env.pop(FAKE_ENV_VAR, None)
    if com_variante and casa == trava.CASA_DEV:
        env[trava.VARIANTE_ENV] = "dev"
    else:
        env.pop(trava.VARIANTE_ENV, None)
    proc = subprocess.Popen([sys.executable, "-c", codigo], env=env, text=True)
    casa_dir = runtime / trava.SLUG_DA_CASA[casa]
    casa_dir.mkdir(parents=True, exist_ok=True)
    (casa_dir / "daemon.pid").write_text(f"{proc.pid}\n", encoding="ascii")
    return proc


def test_o_pid_file_da_outra_casa_ja_conta_como_dono(_runtime_isolado: Path) -> None:
    dev = _daemon_da_outra_casa(_runtime_isolado, trava.CASA_DEV)
    try:
        quem = trava.dono_agora()
        assert quem is not None, "o daemon da outra casa não foi visto"
        assert quem.casa == trava.CASA_DEV
        assert quem.pid == dev.pid
        with pytest.raises(trava.OutraCasaComOAparelhoError):
            trava.conferir_antes_do_takeover()
        # E ninguém TOMOU a trava — é a segunda régua falando, não o flock.
        assert trava._FD_SEGURO is None
    finally:
        _encerrar(dev)


def test_arrancada_a_segunda_regua_o_pid_file_sozinho_nao_bastaria(
    _runtime_isolado: Path,
) -> None:
    """O controle: sem a régua, o flock livre diria "ninguém com o aparelho"."""
    dev = _daemon_da_outra_casa(_runtime_isolado, trava.CASA_DEV)
    try:
        alvo = trava.caminho_da_trava()
        # `_analisar` do arquivo (a primeira régua, sozinha) não vê nada.
        assert not alvo.exists()
        trava.conferir_antes_do_takeover  # noqa: B018 - existe
        # Arrancando a segunda régua, a conferência passa em silêncio.
        original = trava._outra_casa_pelo_pid_file
        trava._outra_casa_pelo_pid_file = lambda _base: None  # type: ignore[assignment]
        try:
            assert trava.dono_agora() is None
            trava.conferir_antes_do_takeover()  # não levanta
        finally:
            trava._outra_casa_pelo_pid_file = original  # type: ignore[assignment]
    finally:
        _encerrar(dev)


def test_o_pid_file_da_propria_casa_nao_e_recusa(_runtime_isolado: Path) -> None:
    """Senão o reinício de sempre — pid file da própria casa no disco — viraria
    recusa, e o daemon dela nunca mais subiria."""
    meu = _daemon_da_outra_casa(_runtime_isolado, trava.CASA_ESTAVEL)
    try:
        assert trava.dono_agora() is None
        trava.conferir_antes_do_takeover()  # não levanta
    finally:
        _encerrar(meu)


def test_pid_reciclado_por_processo_alheio_nao_recusa(_runtime_isolado: Path) -> None:
    """O pid file é de disco e sobrevive ao dono. Se o número for reaproveitado
    por um processo qualquer, recusar seria travar o daemon dela por engano."""
    intruso = _daemon_da_outra_casa(
        _runtime_isolado, trava.CASA_DEV, hefesto_no_nome=False
    )
    try:
        assert trava.dono_agora() is None
    finally:
        _encerrar(intruso)


def test_pid_file_de_dono_morto_nao_recusa(_runtime_isolado: Path) -> None:
    dev = _daemon_da_outra_casa(_runtime_isolado, trava.CASA_DEV)
    dev.kill()
    dev.wait(timeout=10)
    assert (
        _runtime_isolado / trava.SLUG_DA_CASA[trava.CASA_DEV] / "daemon.pid"
    ).exists()
    assert trava.dono_agora() is None


def test_processo_no_slug_de_dev_sem_a_variante_nao_conta(
    _runtime_isolado: Path,
) -> None:
    """A casa vem do processo, não da pasta do pid file: um pid escrito no
    slug de dev por um processo que NÃO é de dev não é dono."""
    falso = _daemon_da_outra_casa(
        _runtime_isolado, trava.CASA_DEV, com_variante=False
    )
    try:
        assert trava.dono_agora() is None
    finally:
        _encerrar(falso)
