"""O install com um jogo aberto não derruba o controle que o jogo lê.

O-INSTALL-NAO-DERRUBA-O-CONTROLE-DO-JOGO-ABERTO-01: em 28/10, os installs das 01:26, 02:06 e
18:02 com o Planet Lust aberto mataram o broker por SIGKILL, desmontaram o pad do jogo e
deixaram o físico visível por nove segundos, no cabo e no BT, em qualquer modo e máscara.
A cura: com o jogo em cena, o install grava os arquivos e adia a troca do broker, do daemon,
da janela e da bandeja; o daemon a dispara quando o jogo fecha.

A MORDIDA: troque o `&& jogo_em_cena` do primeiro ramo do `install_broker_host` por `&& false`
e o install com o jogo aberto volta a mandar o SIGKILL e o restart ao broker; tire o ramo do
`--ha-jogo` do `install_udev.sh` e os quatro `trigger` reenumeram o físico no meio do jogo;
tire o `jogo_aberto()` do laço do `aplicar` e o jogo que abriu depois da colheita perde o
controle; zere a `EsperaSemJogo` e a troca sai no intervalo entre dois jogos.
"""
from __future__ import annotations

import asyncio
import fcntl
import hashlib
import os
import re
import subprocess
from pathlib import Path
from typing import Any

import pytest

from hefesto_dualsense4unix.app.actions import troca_no_fim_do_jogo as troca
from hefesto_dualsense4unix.broker.hidraw_broker import BrokerState
from hefesto_dualsense4unix.daemon import lifecycle
from hefesto_dualsense4unix.integrations import quem_o_jogo_le, uhid_gamepad

RAIZ = Path(__file__).resolve().parents[2]
CAMADA = RAIZ / "scripts/lib/camada_de_maquina.sh"
UDEV = RAIZ / "scripts/install_udev.sh"
INSTALL = RAIZ / "install.sh"


def _funcao(texto: str, nome: str) -> str:
    inicio = texto.index(f"{nome}() {{")
    fim = texto.index("\n}\n", inicio) + 3
    return texto[inicio:fim]


def _proc(tmp_path: Path, *, jogo: bool) -> Path:
    raiz = tmp_path / ("proc-com-jogo" if jogo else "proc-sem-jogo")
    (raiz / "42").mkdir(parents=True)
    ambiente = b"HOME=/x\0"
    if jogo:
        ambiente += quem_o_jogo_le.ENV_DO_JOGO.encode() + b"=/compat/1234\0"
    (raiz / "42" / "environ").write_bytes(ambiente)
    (raiz / "self").mkdir()
    return raiz


def _install_broker_host(
    tmp_path: Path, *, jogo: bool, ja_pendente: str = ""
) -> tuple[list[str], Path]:
    texto = CAMADA.read_text(encoding="utf-8")
    diario = tmp_path / "sudo.txt"
    pendencia = tmp_path / "runtime" / "troca-no-fim-do-jogo"
    if ja_pendente:
        pendencia.parent.mkdir(parents=True, exist_ok=True)
        pendencia.write_text(ja_pendente, encoding="utf-8")
    roteiro = "\n".join([
        _funcao(texto, "jogo_em_cena"),
        _funcao(texto, "arquivo_da_troca_adiada"),
        _funcao(texto, "adiar_para_o_fim_do_jogo"),
        _funcao(texto, "cumprir_a_troca"),
        _funcao(texto, "install_broker_host"),
        f'sudo() {{ printf "%s\\n" "$*" >> "{diario}"; return 0; }}',
        "warn() { :; }",
        "_render_broker_units() { return 0; }",
        "SKIP_UDEV=0",
        "install_broker_host",
    ])
    ambiente = {
        **os.environ,
        "ROOT_DIR": str(RAIZ),
        "HOME": str(tmp_path / "lar"),
        "HEFESTO_RAIZ_PROC": str(_proc(tmp_path, jogo=jogo)),
        "HEFESTO_TROCA_NO_FIM_DO_JOGO": str(pendencia),
    }
    feito = subprocess.run(["bash", "-c", roteiro], env=ambiente, capture_output=True,
                           text=True, check=False, timeout=60)
    assert feito.returncode == 0, feito.stderr
    linhas = diario.read_text(encoding="utf-8").splitlines() if diario.exists() else []
    return linhas, pendencia


def test_com_jogo_aberto_o_broker_nao_morre_e_a_troca_espera(tmp_path: Path) -> None:
    """D-2810-O-INSTALL-COM-JOGO-ABERTO-ESPERA-O-JOGO-PARA-TROCAR.

    MORDIDA: troque o `&& jogo_em_cena` por `&& false` — o SIGKILL volta.
    """
    chamadas, pendencia = _install_broker_host(tmp_path, jogo=True)
    assert not [c for c in chamadas if "SIGKILL" in c or "restart" in c], chamadas
    assert any("install -Dm755" in c for c in chamadas), "o binário novo vai ao disco igual"
    assert pendencia.read_text(encoding="utf-8").split() == ["broker"]


def test_sem_jogo_o_broker_troca_na_hora_como_antes(tmp_path: Path) -> None:
    chamadas, pendencia = _install_broker_host(tmp_path, jogo=False)
    assert any("kill -s SIGKILL hefesto-hidraw-broker.service" in c for c in chamadas)
    assert any("restart hefesto-hidraw-broker.service" in c for c in chamadas)
    assert not pendencia.exists()


def test_o_install_sem_jogo_cumpre_a_troca_que_um_anterior_adiou(tmp_path: Path) -> None:
    """O broker trocado agora sai da pendência; o daemon, que este passo não trocou, fica."""
    chamadas, pendencia = _install_broker_host(tmp_path, jogo=False, ja_pendente="broker\ndaemon\n")
    assert any("restart hefesto-hidraw-broker.service" in c for c in chamadas)
    assert pendencia.read_text(encoding="utf-8").split() == ["daemon"]


def test_cumprir_o_ultimo_item_apaga_a_pendencia(tmp_path: Path) -> None:
    texto = CAMADA.read_text(encoding="utf-8")
    pendencia = tmp_path / "rt" / "troca"
    roteiro = "".join(_funcao(texto, f) for f in (
        "arquivo_da_troca_adiada", "adiar_para_o_fim_do_jogo", "cumprir_a_troca",
    )) + "adiar_para_o_fim_do_jogo daemon\ncumprir_a_troca recarga\ncumprir_a_troca daemon\n"
    subprocess.run(["bash", "-c", roteiro], check=True, timeout=30,
                   env={**os.environ, "HEFESTO_TROCA_NO_FIM_DO_JOGO": str(pendencia)})
    assert not pendencia.exists()


def test_a_pendencia_nao_repete_o_item(tmp_path: Path) -> None:
    texto = CAMADA.read_text(encoding="utf-8")
    pendencia = tmp_path / "rt" / "troca"
    roteiro = "".join(_funcao(texto, f) for f in (
        "arquivo_da_troca_adiada", "adiar_para_o_fim_do_jogo",
    )) + (
        "adiar_para_o_fim_do_jogo broker\nadiar_para_o_fim_do_jogo daemon\n"
        "adiar_para_o_fim_do_jogo broker\n"
    )
    subprocess.run(["bash", "-c", roteiro], check=True, timeout=30,
                   env={**os.environ, "HEFESTO_TROCA_NO_FIM_DO_JOGO": str(pendencia)})
    assert pendencia.read_text(encoding="utf-8").split() == ["broker", "daemon"]


@pytest.mark.parametrize("jogo", [True, False])
def test_a_pergunta_do_install_e_a_do_produto(tmp_path: Path, jogo: bool) -> None:
    """O install pergunta ao mesmo dono do «jogo em cena» que o daemon, sem o venv."""
    raiz = _proc(tmp_path, jogo=jogo)
    assert quem_o_jogo_le.main(["--ha-jogo", "--proc", str(raiz)]) == (0 if jogo else 1)
    feito = subprocess.run(
        ["python3", "-I", str(RAIZ / "src/hefesto_dualsense4unix/integrations/quem_o_jogo_le.py"),
         "--ha-jogo", "--proc", str(raiz)],
        capture_output=True, check=False, timeout=30,
    )
    assert feito.returncode == (0 if jogo else 1), feito.stderr


def test_o_udev_nao_reenumera_o_controle_com_jogo_aberto() -> None:
    """MORDIDA: devolva os quatro `trigger` para fora do `else` — o físico reenumera no jogo."""
    texto = UDEV.read_text(encoding="utf-8")
    ramo = texto[texto.index("--ha-jogo"):]
    ramo = ramo[:ramo.index("\nfi\n")]
    com_jogo, sem_jogo = ramo.split("\nelse\n")
    assert "udevadm trigger" not in com_jogo
    for alvo in ("--subsystem-match=hidraw", "idVendor=054c", "--subsystem-match=input"):
        assert alvo in sem_jogo
    fora = texto.replace(ramo, "")
    assert not re.search(r"trigger[^\n]*(hidraw|054c|subsystem-match=input)", fora)


def test_o_daemon_a_janela_e_a_bandeja_esperam_o_jogo() -> None:
    texto = INSTALL.read_text(encoding="utf-8")
    passo = texto[texto.index('step "7a/11"'):]
    adiado = passo.index('if [[ "${_TROCA_ADIADA}" -eq 1 ]]; then')
    restart = passo.index('systemctl --user restart "${DAEMON_UNIT_NAME}"')
    assert adiado < restart
    bloco = passo[adiado:restart]
    assert "adiar_para_o_fim_do_jogo daemon" in bloco
    assert "adiar_para_o_fim_do_jogo recarga" in bloco
    assert 'elif [[ "${_TROCA_ADIADA:-0}" -eq 1 ]]; then' in texto
    assert passo.count("cumprir_a_troca daemon") == 2
    recarga = passo.index("cumprir_a_troca recarga")
    assert recarga < passo.index("recarga_do_install 2>/dev/null")
    vigia = passo.index('vigiar_o_fim_do_jogo "${VENV_DIR}/bin/python"')
    assert recarga < vigia < passo.index('step "7b/11"')


def test_a_vigia_sobe_numa_unidade_propria_so_com_pendencia(tmp_path: Path) -> None:
    """Fora do cgroup do daemon e com nome fixo: o restart do daemon não a mata, e há uma só."""
    texto = CAMADA.read_text(encoding="utf-8")
    pendencia = tmp_path / "rt" / "troca"
    bin_ = tmp_path / "bin"
    bin_.mkdir()
    diario = tmp_path / "systemd-run.txt"
    (bin_ / "systemd-run").write_text(f'#!/bin/sh\nprintf "%s\\n" "$*" >> "{diario}"\n')
    (bin_ / "systemd-run").chmod(0o755)
    python = tmp_path / "python"
    python.write_text("#!/bin/sh\n")
    python.chmod(0o755)
    roteiro = "".join(_funcao(texto, f) for f in (
        "arquivo_da_troca_adiada", "adiar_para_o_fim_do_jogo", "vigiar_o_fim_do_jogo",
    )) + (
        f'vigiar_o_fim_do_jogo "{python}"\n'
        "adiar_para_o_fim_do_jogo daemon\n"
        f'vigiar_o_fim_do_jogo "{python}"\n'
    )
    subprocess.run(["bash", "-c", roteiro], check=True, timeout=30, env={
        **os.environ, "PATH": f"{bin_}:{os.environ['PATH']}",
        "HEFESTO_TROCA_NO_FIM_DO_JOGO": str(pendencia),
    })
    chamadas = diario.read_text(encoding="utf-8").splitlines()
    assert len(chamadas) == 1, chamadas
    assert "--user" in chamadas[0] and "--unit=hefesto-troca-no-fim-do-jogo" in chamadas[0]
    assert f"--setenv=HEFESTO_TROCA_NO_FIM_DO_JOGO={pendencia}" in chamadas[0]
    assert chamadas[0].endswith("hefesto_dualsense4unix.app.actions.troca_no_fim_do_jogo --esperar")


def _estado(tmp_path: Path, binario: Path) -> BrokerState:
    return BrokerState(
        allowed_uid=os.getuid(),
        ops=object(),
        validator=lambda _n: None,
        dev_root="/dev",
        log=lambda *_a, **_k: None,
        sleep_fn=lambda _s: None,
        binario=str(binario),
        marca_do_reinicio=str(tmp_path / "run" / "reinicio-sem-abrir"),
    )


def test_o_broker_com_o_mesmo_binario_nao_troca(tmp_path: Path) -> None:
    binario = tmp_path / "hefesto-hidraw-broker"
    binario.write_text("velho", encoding="utf-8")
    estado = _estado(tmp_path, binario)
    assert estado._cmd_trocar_se_mudou()["troca"] is False
    assert not estado.trocar
    assert not (tmp_path / "run" / "reinicio-sem-abrir").exists()


def test_o_broker_com_binario_novo_sai_sem_abrir_os_nos(tmp_path: Path) -> None:
    binario = tmp_path / "hefesto-hidraw-broker"
    binario.write_text("velho", encoding="utf-8")
    estado = _estado(tmp_path, binario)
    binario.write_text("novo", encoding="utf-8")
    assert hashlib.sha256(b"novo").hexdigest() != estado._sha_do_binario
    resposta = estado._cmd_trocar_se_mudou()
    assert resposta["ok"] and resposta["troca"] is True
    assert estado.trocar
    assert (tmp_path / "run" / "reinicio-sem-abrir").is_file()


def test_a_troca_colhe_na_ordem_e_ignora_o_estranho() -> None:
    troca.arquivo_da_troca().parent.mkdir(parents=True, exist_ok=True)
    troca.arquivo_da_troca().write_text("recarga\nlixo\ndaemon\nbroker\n", encoding="utf-8")
    assert troca.colher_a_troca() == ["broker", "daemon", "recarga"]
    assert not troca.troca_pendente()


def test_a_troca_aplica_o_broker_antes_do_daemon() -> None:
    ordem: list[str] = []

    def rodar(cmd: Any) -> bool:
        ordem.append("daemon" if "restart" in cmd else "recarga")
        return True

    def broker() -> bool:
        ordem.append("broker")
        return True

    feitos = troca.aplicar(["recarga", "broker", "daemon"], pedir_ao_broker=broker, rodar=rodar,
                           jogo_aberto=lambda: False)
    assert ordem == feitos == ["broker", "daemon", "recarga"]


def test_o_jogo_que_abre_depois_da_colheita_fica_com_o_controle() -> None:
    """O broker trocou; o jogo abriu antes do daemon: o daemon e a tela voltam à pendência."""
    respostas = iter([False, True])
    ordem: list[str] = []
    feitos = troca.aplicar(
        ["broker", "daemon", "recarga"],
        pedir_ao_broker=lambda: ordem.append("broker") is None,
        rodar=lambda cmd: ordem.append(" ".join(cmd)) is None,
        jogo_aberto=lambda: next(respostas),
    )
    assert feitos == ordem == ["broker"]
    assert troca.arquivo_da_troca().read_text(encoding="utf-8").split() == ["daemon", "recarga"]


def test_a_espera_conta_o_jogo_fechado_de_vez() -> None:
    espera = troca.EsperaSemJogo(espera_s=10.0)
    assert not espera.fechou_de_vez(False, 0.0)
    assert not espera.fechou_de_vez(False, 9.0)
    assert not espera.fechou_de_vez(True, 9.5)
    assert not espera.fechou_de_vez(False, 12.0)
    assert not espera.fechou_de_vez(False, 21.0)
    assert espera.fechou_de_vez(False, 22.0)


def test_a_colheita_e_de_um_so() -> None:
    troca.arquivo_da_troca().parent.mkdir(parents=True, exist_ok=True)
    troca.arquivo_da_troca().write_text("daemon\n", encoding="utf-8")
    assert troca.colher_a_troca() == ["daemon"]
    assert troca.colher_a_troca() == []
    assert not list(troca.arquivo_da_troca().parent.glob(".*colhida*"))


def test_a_vigia_espera_o_jogo_fechar_de_vez_troca_e_sai() -> None:
    """A vigia do install, que vale com o daemon de antes da cura, parado ou caído."""
    troca.arquivo_da_troca().parent.mkdir(parents=True, exist_ok=True)
    troca.arquivo_da_troca().write_text("broker\ndaemon\n", encoding="utf-8")
    agora = [0.0]
    jogo = {0.0: True, 2.0: True, 4.0: False, 6.0: True}
    aplicados: list[list[str]] = []

    def aplicar_os(itens: Any) -> list[str]:
        aplicados.append(list(itens))
        return list(itens)

    rc = troca.esperar(
        jogo_aberto=lambda: jogo.get(agora[0], False),
        aplicar_os=aplicar_os,
        relogio=lambda: agora[0],
        dormir=lambda s: agora.__setitem__(0, agora[0] + s),
        prazo_s=600.0,
    )
    assert rc == 0
    assert aplicados == [["broker", "daemon"]]
    assert agora[0] >= 8.0 + troca.ESPERA_SEM_JOGO_S
    assert not troca.troca_pendente()


def test_a_vigia_sai_no_prazo_e_deixa_a_pendencia() -> None:
    troca.arquivo_da_troca().parent.mkdir(parents=True, exist_ok=True)
    troca.arquivo_da_troca().write_text("daemon\n", encoding="utf-8")
    agora = [0.0]
    rc = troca.esperar(
        jogo_aberto=lambda: True,
        aplicar_os=lambda itens: pytest.fail("trocou com o jogo aberto"),
        relogio=lambda: agora[0],
        dormir=lambda s: agora.__setitem__(0, agora[0] + s),
        prazo_s=60.0,
    )
    assert rc == 0
    assert troca.troca_pendente()


def test_a_segunda_vigia_sai_sem_tocar_em_nada() -> None:
    troca.arquivo_da_troca().parent.mkdir(parents=True, exist_ok=True)
    troca.arquivo_da_troca().write_text("daemon\n", encoding="utf-8")
    trava = troca.arquivo_da_troca().with_name(f".{troca.ARQUIVO}.vigia")
    with open(trava, "w") as primeira:
        fcntl.flock(primeira, fcntl.LOCK_EX)
        rc = troca.esperar(
            jogo_aberto=lambda: pytest.fail("a segunda vigia perguntou pelo jogo"),
            aplicar_os=lambda itens: pytest.fail("a segunda vigia trocou"),
            dormir=lambda s: pytest.fail("a segunda vigia esperou"),
        )
    assert rc == 0
    assert troca.troca_pendente()


@pytest.mark.parametrize("jogo", [True, False])
def test_o_daemon_dispara_a_troca_so_com_o_jogo_fechado(
    monkeypatch: pytest.MonkeyPatch, jogo: bool
) -> None:
    """D-2810-O-INSTALL-COM-JOGO-ABERTO-ESPERA-O-JOGO-PARA-TROCAR.

    A troca adiada sai sozinha quando o jogo fecha.
    """
    troca.arquivo_da_troca().parent.mkdir(parents=True, exist_ok=True)
    troca.arquivo_da_troca().write_text("broker\ndaemon\n", encoding="utf-8")
    disparos: list[list[str]] = []
    monkeypatch.setattr(uhid_gamepad, "JOGO_ABERTO", lambda: jogo)
    monkeypatch.setattr(troca, "disparar", lambda itens: disparos.append(list(itens)))
    daemon = type("Daemon", (), {})()
    for instante in (0.0, 2.0, 4.0):
        asyncio.run(lifecycle._a_troca_que_o_jogo_adiou(daemon, relogio=lambda i=instante: i))
    assert disparos == []
    for instante in (10.0, 12.0):
        asyncio.run(lifecycle._a_troca_que_o_jogo_adiou(daemon, relogio=lambda i=instante: i))
    if jogo:
        assert disparos == []
        assert troca.troca_pendente()
    else:
        assert disparos == [["broker", "daemon"]]
        assert not troca.troca_pendente()


def test_o_disparo_que_falha_devolve_a_pendencia(monkeypatch: pytest.MonkeyPatch) -> None:
    troca.arquivo_da_troca().parent.mkdir(parents=True, exist_ok=True)
    troca.arquivo_da_troca().write_text("daemon\nrecarga\n", encoding="utf-8")
    monkeypatch.setattr(uhid_gamepad, "JOGO_ABERTO", lambda: False)

    def falha(itens: Any) -> None:
        raise OSError("sem systemd-run")

    monkeypatch.setattr(troca, "disparar", falha)
    daemon = type("Daemon", (), {})()
    for instante in (0.0, 10.0):
        asyncio.run(lifecycle._a_troca_que_o_jogo_adiou(daemon, relogio=lambda i=instante: i))
    assert troca.arquivo_da_troca().read_text(encoding="utf-8").split() == ["daemon", "recarga"]
