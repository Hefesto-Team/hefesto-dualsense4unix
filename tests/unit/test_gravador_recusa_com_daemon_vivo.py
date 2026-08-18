"""O gravador de capturas HID recusa rodar com o daemon de pé.

Defeito medido em 11/08/2026: `scripts/record_hid_capture.py` abre um
`PyDualSenseController` **próprio** e não perguntava nada a ninguém. Com o
daemon vivo são dois donos do mesmo hidraw, e a captura sai contaminada **sem
erro na tela** — a terceira armadilha nomeada em
`docs/process/COMO-OLHAR-A-TELA.md`, a mesma que fez `test trigger --raw`
imprimir "aplicado" sem ter aplicado.

Isto importa agora porque a captura de Bluetooth (`hid_capture_bt.bin`, que o
ADR-008 afirma existir desde sempre e nunca existiu) vai ser gravada com o
controle na mão. Uma captura contaminada é pior que captura nenhuma: ela vira
fixture, e a partir dali toda medição herda a mentira.

A MORDIDA, provada em 11/08/2026
================================
Arrancado o bloco `if daemon_vivo and not args.com_o_daemon_vivo:` do `main()`
de `scripts/record_hid_capture.py`, `test_recusa_e_nao_grava_com_o_socket_de_pe`
reprova: o processo atravessa o guarda e o código de saída deixa de ser 5.
Devolvido o bloco, verde de novo.
"""
from __future__ import annotations

import importlib.util
import os
import socket
import subprocess
import sys
from collections.abc import Iterator
from pathlib import Path

import pytest

from tests.conftest import arvore_congelada

#: Código de saída que o gravador reserva para "o daemon está de pé".
RECUSA_POR_DAEMON_VIVO = 5


def _carregar_o_gravador():
    """Importa o script pelo caminho, registrando-o em `sys.modules`.

    O registro não é detalhe: sem ele o `@dataclass` do módulo estoura em
    `_is_type`, porque `dataclasses` procura o módulo do dono pelo nome e
    encontra `None`. Custou uma medição confusa para descobrir.
    """
    caminho = arvore_congelada() / "scripts" / "record_hid_capture.py"
    spec = importlib.util.spec_from_file_location("record_hid_capture", caminho)
    assert spec is not None and spec.loader is not None
    modulo = importlib.util.module_from_spec(spec)
    sys.modules["record_hid_capture"] = modulo
    try:
        spec.loader.exec_module(modulo)
    except Exception:  # pragma: no cover - só em árvore quebrada
        del sys.modules["record_hid_capture"]
        raise
    return modulo


def _socket_de_ipc(runtime_dir: Path) -> Path:
    """Onde o daemon atenderia, com este `XDG_RUNTIME_DIR`."""
    os.environ["XDG_RUNTIME_DIR"] = str(runtime_dir)
    from hefesto_dualsense4unix.utils.xdg_paths import ipc_socket_path

    return ipc_socket_path()


@pytest.fixture
def runtime_curto() -> Iterator[Path]:
    """Um `XDG_RUNTIME_DIR` que caiba num caminho de socket AF_UNIX.

    O limite do kernel é 108 bytes, e o `tmp_path` do pytest sozinho já passa
    disso quando somado ao nome do socket. O berço de tmp da casa
    (BERCO-DE-TMP-01) é curto, e esta fixture VARRE o que criou — deixar o
    diretório para o berço varrer só funciona em sessão verde, e foi assim
    que 906 diretórios se acumularam antes.
    """
    import shutil
    import tempfile

    caminho = Path(tempfile.mkdtemp(prefix="rt-"))
    try:
        yield caminho
    finally:
        shutil.rmtree(caminho, ignore_errors=True)


def test_recusa_e_nao_grava_com_o_socket_de_pe(tmp_path, monkeypatch, runtime_curto):
    """Com alguém atendendo no socket, o gravador para ANTES de abrir o hidraw."""
    runtime = runtime_curto
    monkeypatch.setenv("XDG_RUNTIME_DIR", str(runtime))

    caminho_do_socket = _socket_de_ipc(runtime)
    caminho_do_socket.parent.mkdir(parents=True, exist_ok=True)

    servidor = socket.socket(socket.AF_UNIX, socket.SOCK_STREAM)
    servidor.bind(str(caminho_do_socket))
    servidor.listen(1)
    try:
        saida = tmp_path / "nao_deve_nascer.bin"
        processo = subprocess.run(
            [
                sys.executable,
                str(arvore_congelada() / "scripts" / "record_hid_capture.py"),
                "--transport", "bt",
                "--guided",
                "--output", str(saida),
            ],
            capture_output=True,
            text=True,
            timeout=30,
            env={**os.environ, "XDG_RUNTIME_DIR": str(runtime)},
        )
    finally:
        servidor.close()

    assert processo.returncode == RECUSA_POR_DAEMON_VIVO, (
        "o gravador atravessou o guarda e foi disputar o hidraw com o daemon; "
        f"saiu {processo.returncode}, stderr={processo.stderr!r}"
    )
    assert "daemon está de pé" in processo.stderr
    # A recusa tem de ENSINAR: sem o comando de parar e o de trazer de volta,
    # ela vira obstáculo em vez de guarda.
    assert "systemctl --user stop hefesto-dualsense4unix.service" in processo.stderr
    assert "systemctl --user start hefesto-dualsense4unix.service" in processo.stderr
    assert not saida.exists(), "recusou e mesmo assim criou o arquivo de saída"


def test_sem_ninguem_atendendo_o_guarda_nao_dispara():
    """Socket ausente não é daemon vivo — senão o guarda bloquearia sempre."""
    modulo = _carregar_o_gravador()
    assert modulo.daemon_esta_vivo() is False


def test_arquivo_de_socket_orfao_nao_conta_como_daemon(monkeypatch, runtime_curto):
    """Nó no disco não é prova: um daemon morto de forma feia deixa o arquivo.

    Quem responde é a conexão. Este caso é o que separa "existe socket" de
    "existe daemon", e é a razão de o guarda tentar conectar em vez de olhar
    o disco.
    """
    runtime = runtime_curto
    monkeypatch.setenv("XDG_RUNTIME_DIR", str(runtime))

    orfao = _socket_de_ipc(runtime)
    orfao.parent.mkdir(parents=True, exist_ok=True)
    orfao.touch()  # arquivo comum, ninguém escutando

    modulo = _carregar_o_gravador()
    assert modulo.daemon_esta_vivo() is False


def test_a_flag_de_escape_existe_e_carimba_a_captura():
    """`--com-o-daemon-vivo` desarma a recusa, e o header registra a ressalva.

    Um guarda sem escape vira obstáculo; um escape sem carimbo vira mentira
    silenciosa daqui a três meses. As duas coisas andam juntas.
    """
    fonte = (arvore_congelada() / "scripts" / "record_hid_capture.py").read_text(
        encoding="utf-8"
    )
    assert "--com-o-daemon-vivo" in fonte
    assert "daemon_vivo_na_gravacao" in fonte, (
        "o escape existe mas a captura não carrega a ressalva: quem replayar "
        "este arquivo não teria como saber que havia dois donos do hidraw"
    )


@pytest.mark.parametrize("comando_do_adr", ["--script"])
def test_o_adr_008_cita_uma_flag_que_nao_existe(comando_do_adr):
    """Lápide: o ADR-008 manda gravar com `--script`, e o gravador não tem isso.

    Fica como teste para que a nota datada do ADR não seja desfeita por
    engano — se um dia a flag passar a existir, este caso reprova e alguém
    relê a nota em vez de deixar as duas versões brigando em silêncio.
    """
    fonte = (arvore_congelada() / "scripts" / "record_hid_capture.py").read_text(
        encoding="utf-8"
    )
    assert f'"{comando_do_adr}"' not in fonte
