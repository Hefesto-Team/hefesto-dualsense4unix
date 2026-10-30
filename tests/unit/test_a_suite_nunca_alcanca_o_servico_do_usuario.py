"""A suíte nunca alcança o serviço nem o ~/.config de quem a roda.

A sprint é a A-SUITE-NUNCA-ESCREVE-NO-CONFIG-DO-USUARIO-01. Medido em 30/10/2026: o conftest
desviava o
HOME e os quatro XDG_* e deixava o XDG_RUNTIME_DIR real, onde mora o socket do daemon do usuário.
O `test_o_clique_2_limpa_o_painel_antes_de_agir` deixou a marca do Parar da aba Sistema no
runtime real (13h14), e a janela dela, reaberta, não traria o serviço.

As réguas: o caso roda num runtime de mentira; a guarda do conftest recusa e anota a conexão ao
socket real e a escrita no lar real; a recusa e a escrita no ~/.config sem gesto da janela dela
reprovam a sessão com a linha `CANARIO-FS-01 PORTÃO`, e o `rodar-a-suite.sh` reprova a parte que
a traz. A mordida de cada uma está no próprio caso, ou na cópia do script sem a cura.
"""

from __future__ import annotations

import os
import socket
import subprocess
import sys
import textwrap
from dataclasses import dataclass
from pathlib import Path

import pytest

from tests import conftest as casa

RAIZ = Path(__file__).resolve().parents[2]
SUITE = RAIZ / "scripts" / "rodar-a-suite.sh"
PORTAO_NO_SCRIPT = "if grep -q '^CANARIO-FS-01 PORTÃO' \"$log\"; then"


class _SessaoFalsa:
    def __init__(self) -> None:
        self.exitstatus = 0
        self.config = None


def _runtime_desviado() -> Path:
    runtime = Path(os.environ["XDG_RUNTIME_DIR"])
    assert runtime.resolve() != casa.runtime_real().resolve(), "o caso roda no runtime real"
    return runtime


def _servidor(caminho: Path) -> socket.socket:
    if not caminho.parent.is_dir():
        caminho.parent.mkdir(parents=True)
    servidor = socket.socket(socket.AF_UNIX, socket.SOCK_STREAM)
    servidor.bind(str(caminho))
    servidor.listen(4)
    servidor.setblocking(False)
    return servidor


def _alguem_conectou(servidor: socket.socket) -> bool:
    try:
        conexao, _ = servidor.accept()
    except BlockingIOError:
        return False
    conexao.close()
    return True


def test_o_caso_roda_num_runtime_de_mentira_e_a_marca_do_parar_cai_nele() -> None:
    from hefesto_dualsense4unix.utils.marca_do_parar import lembrar_o_parar, marca_do_parar
    from hefesto_dualsense4unix.utils.xdg_paths import ipc_socket_path, runtime_dir

    real = casa.runtime_real()
    desviado = Path(os.environ["XDG_RUNTIME_DIR"])
    assert not desviado.is_relative_to(real), f"o caso roda no runtime real: {desviado}"
    for caminho in (runtime_dir(), ipc_socket_path(), marca_do_parar()):
        assert not caminho.is_relative_to(real), f"{caminho} mora no runtime real {real}"
    assert len(os.fsencode(ipc_socket_path())) < 108, ipc_socket_path()
    lembrar_o_parar(True)
    assert marca_do_parar().is_relative_to(desviado) and marca_do_parar().exists()
    sessao = casa._LAR_ENV_DEPOIS.get("XDG_RUNTIME_DIR")
    if casa.lar_de_sessao() is not None:
        assert sessao and not Path(sessao).is_relative_to(real), sessao


def test_o_espelho_leva_o_resto_do_runtime_e_deixa_o_que_e_do_hefesto(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    real = tmp_path / "real"
    for nome in ("pulse", "hefesto-dualsense4unix", "hefesto-sudo"):
        (real / nome).mkdir(parents=True)
    (real / "wayland-1").write_text("")
    (real / "hefesto-dualsense4unix-tray.pid").write_text("1\n")
    monkeypatch.setattr(casa, "_RUNTIME_REAL", [real])

    espelho = casa._espelhar_o_runtime(tmp_path / "espelho")

    assert sorted(p.name for p in espelho.iterdir()) == ["pulse", "wayland-1"]
    assert (espelho / "pulse").resolve() == real / "pulse"


@dataclass
class _DoUsuario:
    guarda: casa.GuardaDoReal
    runtime: Path
    config: Path


@pytest.fixture
def do_usuario(monkeypatch: pytest.MonkeyPatch) -> _DoUsuario:
    runtime = _runtime_desviado() / "r"
    (runtime / "hefesto-dualsense4unix").mkdir(parents=True)
    config = Path(os.environ["HOME"]) / "lar-do-usuario" / ".config" / "hefesto-dualsense4unix"
    config.mkdir(parents=True)
    (config / "perfil.json").write_text('{"kind": "gamepad"}\n')
    guarda = casa.GuardaDoReal([config], [str(runtime / "hefesto")])
    monkeypatch.setattr(casa, "_GUARDAS", [*casa._GUARDAS, guarda])
    return _DoUsuario(guarda, runtime, config)


def test_a_guarda_recusa_a_escrita_no_config_real_e_deixa_ler(do_usuario: _DoUsuario) -> None:
    perfil = do_usuario.config / "perfil.json"
    assert perfil.read_text() == '{"kind": "gamepad"}\n'
    with pytest.raises(PermissionError):
        perfil.write_text('{"kind": "native"}\n')
    with pytest.raises(PermissionError):
        (do_usuario.config / "native_mode.flag").touch()
    with pytest.raises(PermissionError):
        os.rename(perfil, perfil.with_suffix(".velho"))
    with pytest.raises(PermissionError):
        (do_usuario.config / "pasta-nova").mkdir()
    assert perfil.read_text() == '{"kind": "gamepad"}\n'
    assert sorted(p.name for p in do_usuario.config.iterdir()) == ["perfil.json"]
    recusas = do_usuario.guarda.recusas
    assert len(recusas) >= 4 and all("lar-do-usuario" in r for r in recusas)


def test_a_guarda_recusa_a_escrita_que_chega_por_um_link(
    do_usuario: _DoUsuario, tmp_path: Path,
) -> None:
    espelho = tmp_path / "runtime-quebrado"
    espelho.mkdir()
    (espelho / "hefesto-dualsense4unix").symlink_to(do_usuario.runtime / "hefesto-dualsense4unix")
    (espelho / "hefesto-de-config").symlink_to(do_usuario.config)
    marca = "servico-parado-pela-aba-sistema"
    with pytest.raises(PermissionError):
        (espelho / "hefesto-dualsense4unix" / marca).touch()
    with pytest.raises(PermissionError):
        (espelho / "hefesto-de-config" / "perfil.json").write_text("native")
    assert not (do_usuario.runtime / "hefesto-dualsense4unix" / marca).exists()
    assert (do_usuario.config / "perfil.json").read_text() == '{"kind": "gamepad"}\n'
    recusas = do_usuario.guarda.recusas
    assert len(recusas) >= 2 and all("runtime-quebrado" in r for r in recusas)


def test_a_guarda_recusa_a_conexao_ao_socket_real(do_usuario: _DoUsuario) -> None:
    servidor = _servidor(do_usuario.runtime / "hefesto-dualsense4unix" / "h.sock")
    try:
        cliente = socket.socket(socket.AF_UNIX, socket.SOCK_STREAM)
        with pytest.raises(ConnectionRefusedError):
            cliente.connect(str(do_usuario.runtime / "hefesto-dualsense4unix" / "h.sock"))
        cliente.close()
        assert not _alguem_conectou(servidor)
        recusas = do_usuario.guarda.recusas
        assert recusas and recusas[0].startswith("socket.connect ")
    finally:
        servidor.close()


def test_sem_a_guarda_a_mesma_escrita_e_a_mesma_conexao_passam(
    do_usuario: _DoUsuario, monkeypatch: pytest.MonkeyPatch
) -> None:
    monkeypatch.setattr(casa, "_GUARDAS", [g for g in casa._GUARDAS if g is not do_usuario.guarda])
    (do_usuario.config / "native_mode.flag").write_text("x")
    servidor = _servidor(do_usuario.runtime / "hefesto-dualsense4unix" / "h.sock")
    try:
        cliente = socket.socket(socket.AF_UNIX, socket.SOCK_STREAM)
        cliente.connect(str(do_usuario.runtime / "hefesto-dualsense4unix" / "h.sock"))
        cliente.close()
        assert _alguem_conectou(servidor), "sem a guarda a conexão devia chegar"
    finally:
        servidor.close()
    assert (do_usuario.config / "native_mode.flag").exists() and do_usuario.guarda.recusas == []


def test_a_recusa_reprova_a_sessao_com_a_linha_do_portao(
    monkeypatch: pytest.MonkeyPatch, capsys: pytest.CaptureFixture[str]
) -> None:
    anotada = casa.GuardaDoReal([], [])
    monkeypatch.setattr(casa, "_GUARDA_DA_SESSAO", [anotada])
    sessao = _SessaoFalsa()
    casa._guarda_no_fim_da_sessao(sessao)
    assert sessao.exitstatus == 0 and casa._GUARDA_PORTAO not in capsys.readouterr().out
    anotada.recusas.append("socket.connect /run/user/1/hefesto-dualsense4unix/h.sock (caso)")
    casa._guarda_no_fim_da_sessao(sessao)
    saida = capsys.readouterr().out
    assert sessao.exitstatus == 1
    assert any(linha.startswith("CANARIO-FS-01 PORTÃO") for linha in saida.splitlines()), saida


def _lar_vigiado(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> Path:
    lar = tmp_path / "lar"
    (lar / ".config" / "hefesto-dualsense4unix" / "profiles").mkdir(parents=True)
    (lar / ".config" / "wireplumber").mkdir(parents=True)
    (lar / ".config" / "hefesto-dualsense4unix" / "profiles" / "planeta.json").write_text(
        '{"mode": {"kind": "gamepad"}}\n'
    )
    monkeypatch.setenv("HOME", str(lar))
    monkeypatch.delenv(casa._CANARIO_DESLIGADO_ENV, raising=False)
    monkeypatch.setattr(casa, "_CANARIO_FOTO_AVISO", casa._fotografar_tudo_de_aviso())
    monkeypatch.setattr(casa, "_CANARIO_FOTO_INICIAL", casa._fotografar_tudo())
    monkeypatch.setattr(casa, "_CANARIO_ARMADO", True)
    monkeypatch.setattr(casa, "_deltas_do_congelado", lambda: [])
    monkeypatch.setattr(casa, "_GUARDA_DA_SESSAO", [])
    return lar


@pytest.mark.parametrize("gestos", [[], ["[gesto] 01-jogar.html · hefesto → aplicado"]])
def test_a_escrita_no_config_sem_gesto_do_usuario_e_portao_e_com_gesto_e_aviso(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
    capsys: pytest.CaptureFixture[str],
    gestos: list[str],
) -> None:
    lar = _lar_vigiado(tmp_path, monkeypatch)
    monkeypatch.setattr(casa, "_gestos_da_janela_do_usuario", lambda: list(gestos))
    (lar / ".config" / "hefesto-dualsense4unix" / "profiles" / "planeta.json").write_text(
        '{"mode": {"kind": "native"}}\n'
    )
    (lar / ".config" / "hefesto-dualsense4unix" / "native_mode.flag").write_text("x")
    sessao = _SessaoFalsa()
    capsys.readouterr()

    casa._sessionfinish_das_guardas(sessao)

    saida = capsys.readouterr().out
    portao = [linha for linha in saida.splitlines() if linha.startswith("CANARIO-FS-01 PORTÃO")]
    if gestos:
        assert sessao.exitstatus == 0 and portao == [], saida
        assert "gesto: [gesto] 01-jogar.html" in saida and "native_mode.flag" in saida
    else:
        assert sessao.exitstatus == 1 and len(portao) == 1, saida
        assert "native_mode.flag" in saida and "planeta.json" in saida


def test_o_gesto_do_usuario_nao_cobre_a_escrita_fora_do_config_do_produto(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch, capsys: pytest.CaptureFixture[str]
) -> None:
    lar = _lar_vigiado(tmp_path, monkeypatch)
    gesto = "[gesto] 01-jogar.html · x → aplicado"
    monkeypatch.setattr(casa, "_gestos_da_janela_do_usuario", lambda: [gesto])
    (lar / ".config" / "wireplumber" / "novo.conf").write_text("x")
    sessao = _SessaoFalsa()
    capsys.readouterr()
    casa._sessionfinish_das_guardas(sessao)
    saida = capsys.readouterr().out
    assert sessao.exitstatus == 1 and "wireplumber/novo.conf" in saida
    assert not any(linha.startswith("CANARIO-FS-01 PORTÃO") for linha in saida.splitlines())


def test_os_gestos_sao_so_os_que_a_janela_anotou_depois_do_comeco(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    diario = tmp_path / "interface.log"
    diario.write_text("[gesto] 01-jogar.html · antes → aplicado\n")
    monkeypatch.setattr(casa, "_INTERFACE_LOG_INICIO", [(diario, diario.stat().st_size)])
    with diario.open("a") as aberto:
        aberto.write("[tique] nada\n[gesto] 01-jogar.html · hefesto → aplicado\n")
    assert casa._gestos_da_janela_do_usuario() == ["[gesto] 01-jogar.html · hefesto → aplicado"]
    monkeypatch.setattr(casa, "_INTERFACE_LOG_INICIO", [(tmp_path / "nao-existe.log", 0)])
    assert casa._gestos_da_janela_do_usuario() == []


_NINHO = '''
import os
import socket


def test_alcanca_o_que_e_do_usuario():
    from hefesto_dualsense4unix.utils.marca_do_parar import lembrar_o_parar

    lembrar_o_parar(True)
    cliente = socket.socket(socket.AF_UNIX, socket.SOCK_STREAM)
    try:
        cliente.connect(os.environ["SOCKET_DO_USUARIO"])
    except OSError:
        pass
    finally:
        cliente.close()
    try:
        with open(os.environ["PERFIL_DO_USUARIO"], "w") as perfil:
            perfil.write("native")
    except OSError:
        pass
'''


def _rodar_o_ninho(
    tmp_path: Path, *, com_a_guarda: bool
) -> tuple[subprocess.CompletedProcess[str], bool, Path, Path]:
    rotulo = "com" if com_a_guarda else "sem"
    quintal = tmp_path / f"quintal-{rotulo}"
    quintal.mkdir()
    (quintal / "conftest.py").symlink_to(RAIZ / "tests" / "conftest.py")
    (quintal / "test_ninho.py").write_text(textwrap.dedent(_NINHO))
    mesa = tmp_path / f"mesa-{rotulo}"
    perfil = mesa / ".config" / "hefesto-dualsense4unix" / "planeta.json"
    perfil.parent.mkdir(parents=True)
    perfil.write_text("gamepad")
    run = _runtime_desviado() / rotulo
    produto = run / "hefesto-dualsense4unix"
    servidor = _servidor(produto / "hefesto-dualsense4unix.sock")
    ambiente = {k: v for k, v in os.environ.items() if not k.startswith(("XDG_", "PYTEST_"))}
    ambiente.update({
        "HOME": str(mesa),
        "XDG_RUNTIME_DIR": str(run),
        "PYTHONPATH": str(RAIZ / "src"),
        "SOCKET_DO_USUARIO": str(produto / "hefesto-dualsense4unix.sock"),
        "PERFIL_DO_USUARIO": str(perfil),
    })
    ambiente.pop(casa._CANARIO_DESLIGADO_ENV, None)
    ambiente.pop(casa._LAR_DESLIGADO_ENV, None)
    if com_a_guarda:
        ambiente.pop(casa._GUARDA_DESLIGADA_ENV, None)
    else:
        ambiente[casa._GUARDA_DESLIGADA_ENV] = "1"
    try:
        saida = subprocess.run(
            [sys.executable, "-m", "pytest", "-q", "-p", "no:cacheprovider", "test_ninho.py"],
            cwd=str(quintal), env=ambiente, capture_output=True, text=True, timeout=300,
        )
        conectou = _alguem_conectou(servidor)
    finally:
        servidor.close()
    return saida, conectou, perfil, produto


def test_o_ninho_com_a_guarda_nao_alcanca_o_que_e_do_usuario_e_sai_vermelho(tmp_path: Path) -> None:
    saida, conectou, perfil, produto = _rodar_o_ninho(tmp_path, com_a_guarda=True)
    texto = saida.stdout + saida.stderr
    assert "1 passed" in texto, texto
    assert not conectou, "o caso alcançou o socket do daemon real"
    assert perfil.read_text() == "gamepad", "o caso escreveu no perfil real"
    marca = produto / "servico-parado-pela-aba-sistema"
    assert not marca.exists(), "a marca do Parar caiu no runtime real"
    assert saida.returncode == 1, texto
    portao = [linha for linha in texto.splitlines() if linha.startswith("CANARIO-FS-01 PORTÃO")]
    assert portao and "socket.connect" in texto and "planeta.json" in texto, texto


def test_o_ninho_sem_a_guarda_alcanca_e_o_canario_ainda_reprova(tmp_path: Path) -> None:
    saida, conectou, perfil, _produto = _rodar_o_ninho(tmp_path, com_a_guarda=False)
    texto = saida.stdout + saida.stderr
    assert "1 passed" in texto, texto
    assert conectou and perfil.read_text() == "native", "sem a guarda o caso devia alcançar"
    assert saida.returncode == 1, texto
    linhas = texto.splitlines()
    assert any(linha.startswith("CANARIO-FS-01 PORTÃO: escrita") for linha in linhas), texto


def _arvore(tmp_path: Path, script: Path, linhas_do_py: str) -> Path:
    raiz = tmp_path / "arvore"
    (raiz / "scripts").mkdir(parents=True)
    copia = raiz / "scripts" / "rodar-a-suite.sh"
    copia.write_text(script.read_text(encoding="utf-8"), encoding="utf-8")
    unit = raiz / "tests" / "unit"
    unit.mkdir(parents=True)
    (unit / "__init__.py").write_text("")
    (unit / "test_conta.py").write_text("def test_c():\n    assert True\n")
    py = raiz / "py-de-mentira"
    py.write_text("#!/bin/bash\n" + linhas_do_py)
    py.chmod(0o755)
    (raiz / "lista").write_text("tests/unit/test_conta.py\n")
    return raiz


def _rodar_a_suite(raiz: Path) -> subprocess.CompletedProcess[str]:
    fora = {"PYTEST_ADDOPTS", "SUITE_PYTEST_ARGS", "LD_PRELOAD", "PARTES", "SAIDA", "PARTIDO",
            "LOTE", "PARTES_EM_PARALELO", "LISTAR_O_WEBKIT", "A_SECO"}
    env = {k: v for k, v in os.environ.items() if k not in fora and not k.startswith("COV_")}
    env.update({"PY": str(raiz / "py-de-mentira"), "SAIDA": str(raiz / "saida")})
    return subprocess.run(
        ["bash", str(raiz / "scripts" / "rodar-a-suite.sh"), "--lote", str(raiz / "lista")],
        cwd=raiz, capture_output=True, text=True, timeout=120, check=False, env=env,
    )


COM_PORTAO = (
    'echo "CANARIO-FS-01 PORTÃO: escrita no ~/.config do produto"\n'
    'echo "1 passed in 0.01s"\n'
)


def test_a_parte_com_a_linha_do_portao_sai_vermelha(tmp_path: Path) -> None:
    feito = _rodar_a_suite(_arvore(tmp_path / "com", SUITE, COM_PORTAO))
    assert feito.returncode == 1, feito.stdout + feito.stderr
    saida = feito.stdout
    assert "partes com vermelho: 1" in saida and "CANARIO-FS-01 PORTÃO" in saida, saida
    limpo = _rodar_a_suite(_arvore(tmp_path / "limpo", SUITE, 'echo "1 passed in 0.01s"\n'))
    assert limpo.returncode == 0, limpo.stdout + limpo.stderr


def test_a_regua_do_script_morde_sem_a_leitura_do_portao(tmp_path: Path) -> None:
    texto = SUITE.read_text(encoding="utf-8")
    assert PORTAO_NO_SCRIPT in texto, "a leitura do portão mudou de forma no script"
    sem = tmp_path / "sem-portao.sh"
    sem.write_text(texto.replace(PORTAO_NO_SCRIPT, "if false; then"), encoding="utf-8")
    feito = _rodar_a_suite(_arvore(tmp_path / "sem", sem, COM_PORTAO))
    assert feito.returncode == 0, "sem a leitura do portão a parte devia sair verde: régua vazia"
