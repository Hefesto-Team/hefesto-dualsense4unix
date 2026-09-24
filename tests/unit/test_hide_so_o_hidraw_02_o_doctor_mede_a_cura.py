"""HIDE-SO-O-HIDRAW-02 — o doctor mede a cura, e o install que não reiniciou.

Três instrumentos do `scripts/doctor.sh`, e cada um tem a sua mordida escrita
no teste que a cobra:

1. **o broker em memória** (`_veredito_do_broker_em_memoria`). O achado do
   install de 24/09/2026: o install copiou o binário novo e NÃO reiniciou o
   serviço, que rodava desde 22/09 com o código velho — medido no diário do
   broker (`ready` às 23:35 de 22/09, `Stopping` só às 08:18 de 24/09, depois
   de o binário ter sido trocado às 08:17). Nada acusava.
2. **o `open` do nó de ENTRADA** (`_veredito_do_open_de_entrada`): o broker de
   antes da cura responde `reject_bad_path` a `/dev/input/eventN`, e é essa a
   assinatura de «o install não reiniciou».
3. **o touchpad e o giroscópio do físico** (`check_input_uaccess`): fechados
   com o broker de pé é a cura, não a falta dela. E o controle dela pelo
   rádio, que mora em `/devices/virtual/misc/uhid/` desde o BlueZ 5.73,
   deixa de ser contado como «gamepad VIRTUAL».

As cenas rodam em bash contra um `/dev`, `/sys` e `/run` de mentira, com
`getfacl` de mentira — sem hardware, sem root e sem tocar a máquina.
"""
from __future__ import annotations

import contextlib
import getpass
import json
import os
import re
import shutil
import socket
import subprocess
import tempfile
import threading
from collections.abc import Iterator
from pathlib import Path

import pytest

BASH = shutil.which("bash") or "/bin/bash"
RAIZ = Path(__file__).resolve().parents[2]
DOCTOR = (RAIZ / "scripts" / "doctor.sh").read_text(encoding="utf-8")

_CABECALHO = (
    'pass() { echo "[PASS] $*"; }\n'
    'warn() { echo "[WARN] $*"; }\n'
    'fail() { echo "[FAIL] $*"; }\n'
    'info() { echo "[INFO] $*"; }\n'
)


def _funcao(nome: str, fonte: str = DOCTOR) -> str:
    inicio = re.search(rf"^{re.escape(nome)}\(\) \{{\n", fonte, re.MULTILINE)
    assert inicio is not None, f"{nome}() sumiu do doctor"
    fim = re.search(r"^\}$", fonte[inicio.end():], re.MULTILINE)
    assert fim is not None
    return fonte[inicio.start(): inicio.end() + fim.end() + 1]


def _gesto(fonte: str = DOCTOR) -> str:
    linha = re.search(r"^GESTO_DE_REINICIAR_O_BROKER=.*$", fonte, re.MULTILINE)
    assert linha is not None, "o gesto de reiniciar o broker sumiu do doctor"
    return linha.group(0)


def _bash(tmp_path: Path, corpo: str, env: dict[str, str] | None = None) -> str:
    script = tmp_path / "cena.sh"
    script.write_text(_CABECALHO + corpo, encoding="utf-8")
    ambiente = dict(os.environ)
    ambiente.update(env or {})
    r = subprocess.run(
        [BASH, str(script)], capture_output=True, text=True, check=False, env=ambiente
    )
    return r.stdout + r.stderr


# ---------------------------------------------------------------------------
# 1. O broker em memória
# ---------------------------------------------------------------------------


class TestOBrokerEmMemoria:
    def _roda(self, tmp_path: Path, inicio: str, binario: str, recarregar: str) -> str:
        corpo = (
            _gesto()
            + "\n"
            + _funcao("_veredito_do_broker_em_memoria")
            + f'\n_veredito_do_broker_em_memoria "{inicio}" "{binario}" "{recarregar}"\n'
        )
        return _bash(tmp_path, corpo)

    def test_o_binario_mais_novo_que_o_processo_acusa(self, tmp_path: Path) -> None:
        """A cena de 24/09: o processo de 22/09 23:35, o binário de 24/09
        08:17. A MORDIDA: troque o `>` por `<` e a cena sai verde."""
        saida = self._roda(tmp_path, "1790130901", "1790248632", "no")
        assert "[WARN]" in saida, saida
        assert "de antes do binário instalado" in saida
        assert "reinicio-sem-abrir" in saida, "o gesto tem de ser o que não abre o físico"
        assert "[PASS]" not in saida

    def test_o_processo_depois_do_binario_passa(self, tmp_path: Path) -> None:
        saida = self._roda(tmp_path, "1790248703", "1790248632", "no")
        assert "[PASS]" in saida, saida
        assert "[WARN]" not in saida

    def test_a_unit_trocada_no_disco_pede_daemon_reload(self, tmp_path: Path) -> None:
        """O `DeviceAllow=char-input` só vale depois do `daemon-reload`."""
        saida = self._roda(tmp_path, "1790248703", "1790248632", "yes")
        assert "[WARN]" in saida, saida
        assert "daemon-reload" in saida

    def test_o_gesto_nao_deixa_o_broker_velho_abrir(self) -> None:
        """O gesto cura o broker de ANTES da cura na memória, que não conhece
        o `reinicio-sem-abrir`: o SIGTERM de um `restart` puro roda o
        `restore_everything` dele e abre todo nó escondido. A MORDIDA
        (conferência): volte o gesto ao `touch && restart` e esta régua
        reprova. A ordem também é a cura: o arquivo antes do SIGKILL (o
        ExecStopPost do binário novo o lê), e o `restart` por último."""
        gesto = _gesto()
        toque = gesto.index("reinicio-sem-abrir")
        morte = gesto.index("systemctl kill -s SIGKILL hefesto-hidraw-broker.service")
        volta = gesto.index("systemctl restart hefesto-hidraw-broker.service")
        assert toque < morte < volta, gesto

    def test_o_gesto_tem_um_dono_so(self) -> None:
        """Os avisos que mandam reiniciar leem a MESMA variável — uma cópia
        escrita à mão envelheceria sozinha, como a do `_veredito_do_hide`,
        que a conferência achou com o `restart` puro."""
        assert DOCTOR.count("sudo systemctl kill -s SIGKILL hefesto-hidraw-broker") == 1
        assert "${GESTO_DE_REINICIAR_O_BROKER}" in _funcao("_veredito_do_hide")

    def test_servico_parado_nao_afirma_nada(self, tmp_path: Path) -> None:
        saida = self._roda(tmp_path, "", "1790248632", "no")
        assert "[PASS]" not in saida and "[WARN]" not in saida, saida


# ---------------------------------------------------------------------------
# 2. O open do nó de entrada
# ---------------------------------------------------------------------------


class TestOOpenDoNoDeEntrada:
    def _roda(self, tmp_path: Path, resultado: str, detalhe: str) -> str:
        corpo = (
            _gesto()
            + "\n"
            + _funcao("_veredito_do_open_de_entrada")
            + f'\n_veredito_do_open_de_entrada "{resultado}" "{detalhe}"\n'
        )
        return _bash(tmp_path, corpo)

    def test_ok_passa(self, tmp_path: Path) -> None:
        assert "[PASS]" in self._roda(tmp_path, "ok", "/dev/input/event27")

    def test_o_broker_de_antes_da_cura_e_acusado(self, tmp_path: Path) -> None:
        saida = self._roda(tmp_path, "velho", "/dev/input/event27")
        assert "[WARN]" in saida, saida
        assert "de antes da HIDE-SO-O-HIDRAW-02" in saida
        assert "reinicio-sem-abrir" in saida

    def test_a_falha_nomeia_o_device_allow(self, tmp_path: Path) -> None:
        saida = self._roda(tmp_path, "fail", "/dev/input/event27 erro=open_failed errno=1")
        assert "[FAIL]" in saida, saida
        assert "DeviceAllow=char-input rw" in saida

    def test_sem_fisico_nao_diz_nada(self, tmp_path: Path) -> None:
        assert self._roda(tmp_path, "skip", "").strip() == ""

    def test_a_sonda_existe_no_check_do_broker(self) -> None:
        """A sonda mora no python do `check_hidraw_broker` e o veredito é
        chamado com o que ela imprime. A MORDIDA: tire a chamada e este
        teste reprova — a sonda viraria texto morto."""
        corpo = _funcao("check_hidraw_broker")
        assert 'print(f"open_entrada={resultado_e}")' in corpo
        assert "_veredito_do_open_de_entrada" in corpo
        assert "_medir_o_broker_em_memoria" in corpo


# ---------------------------------------------------------------------------
# 3. A ACL que a máscara anula
# ---------------------------------------------------------------------------


def _getfacl_de_mentira(raiz: Path, linha_do_usuario: str) -> Path:
    binario = raiz / "bin"
    binario.mkdir(parents=True, exist_ok=True)
    stub = binario / "getfacl"
    stub.write_text(
        "#!/bin/sh\n"
        "echo 'user::rw-'\n"
        f"printf '%s\\n' '{linha_do_usuario}'\n"
        "echo 'group::rw-'\n"
        "echo 'mask::---'\n"
        "echo 'other::---'\n",
        encoding="utf-8",
    )
    stub.chmod(0o755)
    return binario


class TestAAclQueAMascaraAnula:
    def _alcancavel(self, tmp_path: Path, linha: str, modo: int) -> bool:
        no = tmp_path / "event27"
        no.write_text("", encoding="ascii")
        no.chmod(modo)
        # O grupo do arquivo de teste é o da própria suíte: o ramo do grupo
        # ficaria verde por outro motivo. Aqui só interessa a ACL.
        corpo = (
            _funcao("_entrada_alcancavel_pelo_jogo").replace('id -nG', 'echo nenhum-grupo')
            + f'\n_entrada_alcancavel_pelo_jogo "{no}" && echo SIM || echo NAO\n'
        )
        bin_dir = _getfacl_de_mentira(tmp_path, linha)
        saida = _bash(tmp_path, corpo, {"PATH": f"{bin_dir}{os.pathsep}{os.environ['PATH']}"})
        return "SIM" in saida

    def test_a_linha_anulada_pela_mascara_nao_abre(self, tmp_path: Path) -> None:
        """O formato é o do getfacl real (medido com a ACL nomeada e a
        máscara zerada). A MORDIDA: tire o `grep -vq '#effective:-'` e o
        nó que o broker fechou volta a contar como aberto."""
        assert not self._alcancavel(tmp_path, "user:ela:rw-\t#effective:---", 0o600)

    def test_a_linha_que_vale_abre(self, tmp_path: Path) -> None:
        assert self._alcancavel(tmp_path, "user:ela:rw-", 0o660)


# ---------------------------------------------------------------------------
# 4. O touchpad e o giroscópio do físico, fechados pelo Hefesto
# ---------------------------------------------------------------------------

#: O DualSense dela pelo RÁDIO: o BlueZ ≥5.73 o põe sob `/misc/uhid/`.
RADIO = "/sys/devices/virtual/misc/uhid/0005:054C:0CE6.0006"
CABO = "/sys/devices/pci0000:00/0000:00:14.0/usb3/3-3/3-3:1.0/0003:054C:0CE6.0042"
VPAD = "/sys/devices/virtual/misc/uhid/0003:054C:0DF2.008F"

#: (base, vendor, product, uniq, nome, pai, modo)
No = tuple[str, str, str, str, str, str, int]


def _cena(
    raiz: Path,
    nos: list[No],
    *,
    com_broker: bool,
) -> None:
    (raiz / "dev" / "input").mkdir(parents=True, exist_ok=True)
    regra = raiz / "etc" / "udev" / "rules.d" / "72-hefesto-touchpad-motion-uaccess.rules"
    regra.parent.mkdir(parents=True, exist_ok=True)
    regra.write_text("# de mentira\n", encoding="utf-8")
    if com_broker:
        sock = raiz / "run" / "hefesto-hidraw-broker" / "broker.sock"
        sock.parent.mkdir(parents=True, exist_ok=True)
        sock.write_text("", encoding="ascii")
    for base, vendor, product, uniq, nome, pai, modo in nos:
        dev_dir = raiz / pai.lstrip("/") / "input" / f"input-{base}"
        (dev_dir / "id").mkdir(parents=True, exist_ok=True)
        (dev_dir / "id" / "vendor").write_text(vendor + "\n", encoding="ascii")
        (dev_dir / "id" / "product").write_text(product + "\n", encoding="ascii")
        (dev_dir / "uniq").write_text(uniq + "\n", encoding="ascii")
        (dev_dir / "name").write_text(nome + "\n", encoding="utf-8")
        classe = raiz / "sys" / "class" / "input" / base
        classe.mkdir(parents=True, exist_ok=True)
        (classe / "device").symlink_to(dev_dir)
        no = raiz / "dev" / "input" / base
        no.write_text("", encoding="ascii")
        no.chmod(modo)


def _check(raiz: Path) -> str:
    corpo = "\n".join(
        _funcao(nome)
        for nome in (
            "_nos_de_entrada_do_hidraw",
            "_entradas_expostas_no_broker",
            "_entradas_devolvidas_pelo_nativo",
            "check_input_uaccess",
        )
    )
    for real in (
        "/dev/input/",
        "/sys/class/input/",
        "/sys/class/hidraw/",
        "/etc/udev/rules.d/",
        "/usr/lib/udev/rules.d/",
        "/run/hefesto-hidraw-broker/",
    ):
        corpo = corpo.replace(real, f"{raiz}{real}")
    # A ACL da sessão é a de quem roda o check: o getfacl de mentira a dá a
    # QUEM PERGUNTA, que é o que o `uaccess` faz no login.
    bin_dir = _getfacl_de_mentira(raiz, f"user:{getpass.getuser()}:rw-")
    return _bash(
        raiz,
        corpo + "\ncheck_input_uaccess\n",
        {"PATH": f"{bin_dir}{os.pathsep}{os.environ['PATH']}"},
    )


def _fisico(pai: str, modo: int, uniq: str = "e8:47:3a:00:00:07") -> list[No]:
    nome = "DualSense Wireless Controller"
    return [
        ("event28", "054c", "0ce6", uniq, f"{nome} Motion Sensors", pai, modo),
        ("event29", "054c", "0ce6", uniq, f"{nome} Touchpad", pai, modo),
    ]


class TestOTouchpadDoFisicoFechadoEACura:
    @pytest.mark.parametrize("pai", [RADIO, CABO], ids=["radio", "cabo"])
    def test_fechados_com_o_broker_de_pe_passam(self, tmp_path: Path, pai: str) -> None:
        """A MORDIDA: tire o ramo `fechados_pelo_hefesto` e o nó fechado cai
        no «sem permissão de leitura», um FAIL sobre a cura."""
        if os.geteuid() == 0:  # pragma: no cover - como root tudo é legível
            pytest.skip("como root o 0000 não fecha nada")
        _cena(tmp_path, _fisico(pai, 0o000), com_broker=True)
        saida = _check(tmp_path)
        assert "[PASS]" in saida, saida
        assert "fechados para todos menos o Hefesto" in saida
        assert "[FAIL]" not in saida and "VIRTUAL" not in saida

    def test_abertos_com_o_broker_de_pe_acusam(self, tmp_path: Path) -> None:
        _cena(tmp_path, _fisico(RADIO, 0o660), com_broker=True)
        saida = _check(tmp_path)
        assert "[WARN]" in saida, saida
        assert "seguem abertos" in saida
        assert "event28" in saida and "event29" in saida

    def test_sem_broker_vale_o_mundo_de_antes(self, tmp_path: Path) -> None:
        """Sem o socket a regra 72 não fecha nada, e o esperado é a ACL."""
        _cena(tmp_path, _fisico(CABO, 0o660), com_broker=False)
        saida = _check(tmp_path)
        assert "[PASS]" in saida, saida
        assert "ACL da sessão" in saida

    def test_o_radio_dela_nao_e_o_gamepad_virtual(self, tmp_path: Path) -> None:
        """FATO QUE CAIU: o físico pelo rádio mora sob `/misc/uhid/`. A
        MORDIDA: volte a classificação para só `/devices/virtual/` e o
        controle dela aparece como «gamepad VIRTUAL»."""
        if os.geteuid() == 0:  # pragma: no cover
            pytest.skip("como root o 0000 não fecha nada")
        _cena(tmp_path, _fisico(RADIO, 0o000), com_broker=False)
        saida = _check(tmp_path)
        assert "VIRTUAL" not in saida, saida
        assert "FÍSICOS" in saida

    def test_o_vpad_continua_sendo_o_vpad(self, tmp_path: Path) -> None:
        nos: list[No] = [
            ("event259", "054c", "0df2", "02:fe:00:00:00:01",
             "DualSense Wireless Controller (Hefesto P1) Motion Sensors", VPAD, 0o660),
        ]
        _cena(tmp_path, nos, com_broker=True)
        saida = _check(tmp_path)
        assert "gamepad virtual" in saida.lower(), saida
        assert "[PASS]" not in saida

    def test_o_modo_nativo_devolve_e_o_doctor_nao_acusa(self, tmp_path: Path) -> None:
        """O Nativo DEVOLVE os nós de entrada ao jogo — é o produto. O broker
        de verdade responde o `status` com `entradas_expostas`, e o doctor
        pergunta a ele antes de acusar. A MORDIDA (conferência): tire o ramo
        `devolvidos_ao_nativo` e o Nativo inteiro sai como «seguem abertos»."""
        raiz = Path(tempfile.mkdtemp(prefix="h2n-", dir="/tmp"))
        try:
            _cena(raiz, _fisico(RADIO, 0o660), com_broker=False)
            hid = raiz / RADIO.lstrip("/")
            for base in ("event28", "event29"):
                (hid / "input" / f"input-{base}" / base).mkdir()
            classe = raiz / "sys" / "class" / "hidraw" / "hidraw5"
            classe.mkdir(parents=True)
            (classe / "device").symlink_to(hid)
            with _broker_de_status(
                raiz / "run" / "hefesto-hidraw-broker" / "broker.sock",
                {"ok": True, "cmd": "status", "entradas_expostas": ["/dev/hidraw5"]},
            ):
                saida = _check(raiz)
        finally:
            shutil.rmtree(raiz, ignore_errors=True)
        assert "[WARN]" not in saida, saida
        assert "devolvidos ao jogo pelo Modo Nativo" in saida
        assert "event28" in saida and "event29" in saida

    def test_o_doctor_le_o_campo_que_o_broker_escreve(self) -> None:
        """Dois donos da mesma palavra: o `status` do broker e a pergunta do
        doctor. Renomear um lado sem o outro calaria o ramo do Nativo."""
        broker = (RAIZ / "src" / "hefesto_dualsense4unix" / "broker" / "hidraw_broker.py")
        assert '"entradas_expostas":' in broker.read_text(encoding="utf-8")
        assert 'resposta.get("entradas_expostas")' in _funcao("_entradas_expostas_no_broker")

    def test_aberto_fora_do_nativo_continua_acusado(self, tmp_path: Path) -> None:
        """O broker responde, e o nó aberto NÃO é do Nativo: segue o WARN."""
        raiz = Path(tempfile.mkdtemp(prefix="h2n-", dir="/tmp"))
        try:
            _cena(raiz, _fisico(RADIO, 0o660), com_broker=False)
            with _broker_de_status(
                raiz / "run" / "hefesto-hidraw-broker" / "broker.sock",
                {"ok": True, "cmd": "status", "entradas_expostas": []},
            ):
                saida = _check(raiz)
        finally:
            shutil.rmtree(raiz, ignore_errors=True)
        assert "[WARN]" in saida and "seguem abertos" in saida, saida


@contextlib.contextmanager
def _broker_de_status(caminho: Path, resposta: dict[str, object]) -> Iterator[None]:
    """Um broker de mentira que responde UMA linha ao `status`, num socket
    AF_UNIX de verdade — o doctor fala com ele pelo mesmo python que fala com
    o de produção. O caminho vem de um `mkdtemp` curto em /tmp porque o
    AF_UNIX não aceita mais de 107 bytes."""
    caminho.parent.mkdir(parents=True, exist_ok=True)
    servidor = socket.socket(socket.AF_UNIX, socket.SOCK_STREAM)
    servidor.bind(str(caminho))
    servidor.listen(4)
    servidor.settimeout(5.0)

    def _atende() -> None:
        with contextlib.suppress(OSError):
            conexao, _ = servidor.accept()
            with conexao:
                conexao.settimeout(5.0)
                buf = b""
                while not buf.endswith(b"\n"):
                    pedaco = conexao.recv(4096)
                    if not pedaco:
                        return
                    buf += pedaco
                if json.loads(buf).get("cmd") == "status":
                    conexao.sendall(json.dumps(resposta).encode("utf-8") + b"\n")

    fio = threading.Thread(target=_atende, daemon=True)
    fio.start()
    try:
        yield
    finally:
        servidor.close()
        fio.join(timeout=5.0)

