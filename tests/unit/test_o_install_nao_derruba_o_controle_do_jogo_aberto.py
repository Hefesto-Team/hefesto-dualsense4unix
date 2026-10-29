"""O install com um jogo aberto não derruba o controle que o jogo lê.

O-INSTALL-NAO-DERRUBA-O-CONTROLE-DO-JOGO-ABERTO-01: em 28/10, os installs das 01:26, 02:06 e
18:02 com o Planet Lust aberto mataram o broker por SIGKILL, desmontaram o pad do jogo e
deixaram o físico visível por nove segundos, no cabo e no BT, em qualquer modo e máscara.
A cura: com o jogo em cena, o install grava os arquivos e adia a troca do broker, do daemon,
da janela e da bandeja; o daemon a dispara quando o jogo fecha.

A MORDIDA: troque o `&& jogo_em_cena` do primeiro ramo do `install_broker_host` por `&& false`
e o install com o jogo aberto volta a mandar o SIGKILL e o restart ao broker; tire o ramo do
`--ha-jogo` do `install_udev.sh` e os quatro `trigger` reenumeram o físico no meio do jogo.
"""
from __future__ import annotations

import asyncio
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


def _install_broker_host(tmp_path: Path, *, jogo: bool) -> tuple[list[str], Path]:
    texto = CAMADA.read_text(encoding="utf-8")
    diario = tmp_path / "sudo.txt"
    pendencia = tmp_path / "runtime" / "troca-no-fim-do-jogo"
    roteiro = "\n".join([
        _funcao(texto, "jogo_em_cena"),
        _funcao(texto, "adiar_para_o_fim_do_jogo"),
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


def test_a_pendencia_nao_repete_o_item(tmp_path: Path) -> None:
    texto = CAMADA.read_text(encoding="utf-8")
    pendencia = tmp_path / "rt" / "troca"
    roteiro = _funcao(texto, "adiar_para_o_fim_do_jogo") + (
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

    feitos = troca.aplicar(["recarga", "broker", "daemon"], pedir_ao_broker=broker, rodar=rodar)
    assert ordem == feitos == ["broker", "daemon", "recarga"]


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
    asyncio.run(lifecycle._a_troca_que_o_jogo_adiou())
    asyncio.run(lifecycle._a_troca_que_o_jogo_adiou())
    if jogo:
        assert disparos == []
        assert troca.troca_pendente()
    else:
        assert disparos == [["broker", "daemon"]]
        assert not troca.troca_pendente()
