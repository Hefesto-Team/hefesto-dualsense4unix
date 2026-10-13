"""O broker serve quem está na frente do computador (O-BROKER-SERVE-QUEM-ESTA-NA-FRENTE-01).

A unit não grava uid nem grupo: a cada pedido o broker pergunta ao logind quem
está na frente do seat e atende SÓ essa conta. A prova é um ``loginctl`` falso
(um script de shell em ``tmp_path`` lendo o estado de um arquivo), nunca o logind
da máquina. Os pacotes levam o broker como unit de sistema e a regra do nó
FECHADA; a regra de sudo da ponte vale para o grupo ``hefesto``.
"""

from __future__ import annotations

import os
import re
import shutil
import socket
import stat
import subprocess
import sys
from collections.abc import Callable
from pathlib import Path

import pytest

from hefesto_dualsense4unix.broker import hidraw_broker as hb

REPO = Path(__file__).resolve().parents[2]
BROKER_PY = REPO / "src" / "hefesto_dualsense4unix" / "broker" / "hidraw_broker.py"
SERVICE = REPO / "assets" / "systemd" / "hefesto-hidraw-broker.service"
SOCKET = REPO / "assets" / "systemd" / "hefesto-hidraw-broker.socket"
CAMADA = REPO / "scripts" / "lib" / "camada_de_maquina.sh"
BROKER_DO_PACOTE = REPO / "scripts" / "broker_do_pacote.sh"
PONTE = REPO / "scripts" / "bt_ponte_privilegiada.sh"

PACOTES = {
    "deb": REPO / "scripts" / "build_deb.sh",
    "arch": REPO / "packaging" / "arch" / "PKGBUILD",
    "fedora": REPO / "packaging" / "fedora" / "hefesto-dualsense4unix.spec",
    "nix": REPO / "packaging" / "nix" / "package.nix",
}
LIGADORES = {
    "deb": REPO / "packaging" / "debian" / "postinst",
    "arch": REPO / "packaging" / "arch" / "hefesto-dualsense4unix.install",
    "fedora": REPO / "packaging" / "fedora" / "hefesto-dualsense4unix.spec",
    "nix": REPO / "packaging" / "nix" / "module.nix",
}

# Dois uids de conta comum; nenhum é o da máquina que roda o teste.
ELA = 4001
OUTRA = 4000


# ---------------------------------------------------------------------------
# O logind de mentira
# ---------------------------------------------------------------------------
class LogindFalso:
    """Um ``loginctl`` de shell que lê a sessão ativa de um arquivo de estado."""

    def __init__(self, raiz: Path) -> None:
        self.estado = raiz / "estado"
        self.script = raiz / "loginctl"
        self.script.write_text(
            "#!/bin/sh\n"
            f'estado="{self.estado}"\n'
            'case "$1" in\n'
            "  show-seat)\n"
            '    [ "$2" = seat0 ] || exit 1\n'
            '    sed -n "s/^sessao=//p" "$estado"\n'
            "    ;;\n"
            "  show-session)\n"
            '    sed -n "s/^user:$2=//p" "$estado"\n'
            "    ;;\n"
            "  *) exit 1 ;;\n"
            "esac\n",
            encoding="utf-8",
        )
        self.script.chmod(self.script.stat().st_mode | stat.S_IXUSR)
        self.vazio()

    def na_frente(self, sessao: str, uid: int) -> None:
        self.estado.write_text(f"sessao={sessao}\nuser:{sessao}={uid}\n", encoding="utf-8")

    def vazio(self) -> None:
        self.estado.write_text("sessao=\n", encoding="utf-8")


@pytest.fixture
def logind(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> LogindFalso:
    falso = LogindFalso(tmp_path)
    monkeypatch.setenv(hb.LOGINCTL_ENV, str(falso.script))
    return falso


# ---------------------------------------------------------------------------
# Quem está na frente
# ---------------------------------------------------------------------------
class TestUidDaSessaoAtiva:
    def test_devolve_o_uid_da_sessao_ativa(self, logind: LogindFalso) -> None:
        logind.na_frente("c2", ELA)
        assert hb.uid_da_sessao_ativa() == ELA

    def test_a_troca_de_conta_inverte_a_resposta(self, logind: LogindFalso) -> None:
        logind.na_frente("c2", ELA)
        assert hb.uid_da_sessao_ativa() == ELA
        logind.na_frente("c3", OUTRA)
        assert hb.uid_da_sessao_ativa() == OUTRA

    def test_root_nunca_e_quem_esta_na_frente(self, logind: LogindFalso) -> None:
        logind.na_frente("c1", 0)
        assert hb.uid_da_sessao_ativa() is None

    def test_seat_sem_ninguem_nao_atende(self, logind: LogindFalso) -> None:
        logind.vazio()
        assert hb.uid_da_sessao_ativa() is None

    def test_logind_ausente_nao_atende(
        self, tmp_path: Path, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        monkeypatch.setenv(hb.LOGINCTL_ENV, str(tmp_path / "nao-existe"))
        assert hb.uid_da_sessao_ativa() is None

    def test_a_recusa_do_logind_deixa_o_motivo_no_diario(
        self, logind: LogindFalso, capsys: pytest.CaptureFixture[str]
    ) -> None:
        """Sandbox que barra o loginctl, binário que some e logind parado leem-se igual."""
        logind.script.write_text("#!/bin/sh\nexit 3\n", encoding="utf-8")
        assert hb.uid_da_sessao_ativa() is None
        assert "loginctl_recusou" in capsys.readouterr().out

    def test_resposta_que_nao_e_uid_nao_atende(self, logind: LogindFalso) -> None:
        logind.estado.write_text("sessao=c2\nuser:c2=nao-e-numero\n", encoding="utf-8")
        assert hb.uid_da_sessao_ativa() is None


def _estado(logind: LogindFalso, agora: list[float]) -> hb.BrokerState:
    return hb.BrokerState(
        allowed_uid=None,
        ops=object(),
        quem_esta_na_frente=hb.uid_da_sessao_ativa,
        relogio=lambda: agora[0],
        log=lambda *a, **k: None,
    )


class TestUidAutorizado:
    def test_a_resposta_vale_um_segundo_e_depois_pergunta_de_novo(
        self, logind: LogindFalso
    ) -> None:
        agora = [100.0]
        estado = _estado(logind, agora)
        logind.na_frente("c2", ELA)
        assert estado.uid_autorizado() == ELA
        logind.na_frente("c3", OUTRA)
        agora[0] += hb.VALIDADE_DA_SESSAO_S / 2
        assert estado.uid_autorizado() == ELA, "dentro do prazo vale a resposta guardada"
        agora[0] += hb.VALIDADE_DA_SESSAO_S
        assert estado.uid_autorizado() == OUTRA

    def test_esquecer_a_resposta_forca_a_pergunta(self, logind: LogindFalso) -> None:
        agora = [100.0]
        estado = _estado(logind, agora)
        logind.na_frente("c2", ELA)
        assert estado.uid_autorizado() == ELA
        logind.na_frente("c3", OUTRA)
        estado.esquecer_a_sessao_lida()
        assert estado.uid_autorizado() == OUTRA

    def test_sem_ninguem_na_frente_o_ultimo_uid_serve_so_as_varreduras(
        self, logind: LogindFalso
    ) -> None:
        agora = [100.0]
        estado = _estado(logind, agora)
        logind.na_frente("c2", ELA)
        assert estado.uid_autorizado() == ELA
        logind.vazio()
        agora[0] += 5 * hb.VALIDADE_DA_SESSAO_S
        assert estado.uid_autorizado() is None
        assert estado.uid_para_agir() == ELA

    def test_a_varredura_do_fisico_entregue_nao_pergunta_a_cada_segundo(
        self, tmp_path: Path
    ) -> None:
        """Com o Hefesto parado o laço varre a cada segundo; o logind, não."""
        agora = [100.0]
        perguntas: list[float] = []

        def na_frente() -> int:
            perguntas.append(agora[0])
            return ELA

        vazio = tmp_path / "hidraw"
        vazio.mkdir()
        estado = hb.BrokerState(
            allowed_uid=None,
            ops=object(),
            no_nasce_fechado=True,
            dev_root=str(vazio),
            dev_input_root=str(vazio),
            sys_class_input=str(vazio),
            sys_class_hidraw=str(vazio),
            sys_class_bluetooth=str(vazio),
            quem_esta_na_frente=na_frente,
            relogio=lambda: agora[0],
            log=lambda *a, **k: None,
        )
        estado.entregar_ao_linux()
        assert estado.entregue
        for _ in range(30):
            agora[0] += 1.0
            estado.entregar_ao_linux()
        # 31 varreduras em 30 s: a primeira e uma a cada VALIDADE_NA_VARREDURA_S.
        assert len(perguntas) <= 1 + 30 / hb.VALIDADE_NA_VARREDURA_S, perguntas
        # Quem conecta segue no prazo curto.
        agora[0] += hb.VALIDADE_DA_SESSAO_S
        antes = len(perguntas)
        estado.uid_autorizado()
        assert len(perguntas) == antes + 1

    def test_uid_fixo_zero_nunca_e_atendido(self) -> None:
        estado = hb.BrokerState(allowed_uid=0, ops=object(), log=lambda *a, **k: None)
        assert estado.uid_autorizado() is None

    def test_sem_uid_e_sem_logind_o_estado_nem_nasce(self) -> None:
        with pytest.raises(ValueError):
            hb.BrokerState(allowed_uid=None, ops=object())


# ---------------------------------------------------------------------------
# A conexão: quem chega, quem fica atrás
# ---------------------------------------------------------------------------
def _broker(
    logind: LogindFalso, agora: list[float], eventos: list[tuple[str, dict[str, object]]]
) -> tuple[hb.Broker, Callable[[int], socket.socket]]:
    def log(evento: str, **campos: object) -> None:
        eventos.append((evento, campos))

    estado = hb.BrokerState(
        allowed_uid=None,
        ops=object(),
        quem_esta_na_frente=hb.uid_da_sessao_ativa,
        relogio=lambda: agora[0],
        log=log,
    )
    uids: dict[int, int] = {}

    def peercred(sock: socket.socket) -> tuple[int, int, int]:
        return (1234, uids[sock.fileno()], 0)

    broker = hb.Broker(estado, None, peercred_fn=peercred, log=log, graca_da_entrega_s=0)
    abertos: list[socket.socket] = []

    def cliente(uid: int) -> socket.socket:
        lado_broker, lado_cliente = socket.socketpair()
        uids[lado_broker.fileno()] = uid
        abertos.append(lado_cliente)
        broker.register_client(lado_broker)
        return lado_cliente

    cliente.abertos = abertos  # type: ignore[attr-defined]
    return broker, cliente


class TestRegisterClient:
    def test_atende_quem_esta_na_frente_e_recusa_a_outra_conta(self, logind: LogindFalso) -> None:
        eventos: list[tuple[str, dict[str, object]]] = []
        logind.na_frente("c2", ELA)
        broker, cliente = _broker(logind, [100.0], eventos)
        cliente(ELA)
        cliente(OUTRA)
        aceitos = [c for e, c in eventos if e == "peer_accepted"]
        recusados = [c for e, c in eventos if e == "peer_rejected"]
        assert [c["peer_uid"] for c in aceitos] == [ELA]
        assert [c["peer_uid"] for c in recusados] == [OUTRA]
        assert recusados[0]["motivo"] == "nao_e_quem_esta_na_frente"
        del broker

    def test_inverte_quando_a_outra_conta_assume_a_frente(self, logind: LogindFalso) -> None:
        eventos: list[tuple[str, dict[str, object]]] = []
        agora = [100.0]
        logind.na_frente("c2", ELA)
        broker, cliente = _broker(logind, agora, eventos)
        cliente(ELA)
        logind.na_frente("c3", OUTRA)
        agora[0] += 5 * hb.VALIDADE_DA_SESSAO_S
        cliente(ELA)
        cliente(OUTRA)
        aceitos = [c["peer_uid"] for e, c in eventos if e == "peer_accepted"]
        recusados = [c["peer_uid"] for e, c in eventos if e == "peer_rejected"]
        assert aceitos == [ELA, OUTRA]
        assert recusados == [ELA]
        del broker

    def test_quem_ficou_atras_na_troca_de_usuario_e_solta(self, logind: LogindFalso) -> None:
        eventos: list[tuple[str, dict[str, object]]] = []
        agora = [100.0]
        logind.na_frente("c2", ELA)
        broker, cliente = _broker(logind, agora, eventos)
        antiga = cliente(ELA)
        logind.na_frente("c3", OUTRA)
        agora[0] += 5 * hb.VALIDADE_DA_SESSAO_S
        cliente(OUTRA)
        soltos = [c for e, c in eventos if e == "peer_solto"]
        assert [c["peer_uid"] for c in soltos] == [ELA]
        antiga.settimeout(2.0)
        assert antiga.recv(16) == b"", "a conexão de quem ficou atrás tem de cair"
        del broker

    def test_sem_ninguem_na_frente_recusa_com_o_motivo(self, logind: LogindFalso) -> None:
        eventos: list[tuple[str, dict[str, object]]] = []
        logind.vazio()
        broker, cliente = _broker(logind, [100.0], eventos)
        cliente(ELA)
        recusados = [c for e, c in eventos if e == "peer_rejected"]
        assert [c["motivo"] for c in recusados] == ["sem_sessao_ativa"]
        del broker


# ---------------------------------------------------------------------------
# O processo de verdade (belts) com o logind de mentira
# ---------------------------------------------------------------------------
def _rodar(
    tmp_path: Path, *args: str, env_extra: dict[str, str] | None = None
) -> subprocess.CompletedProcess[str]:
    env = {"PATH": "/usr/bin:/bin"}
    env.update(env_extra or {})
    return subprocess.run(
        [sys.executable, str(BROKER_PY), *args],
        capture_output=True,
        text=True,
        cwd=str(tmp_path),
        env=env,
        timeout=30,
        check=False,
    )


class TestOsBelts:
    def test_restore_sem_sessao_ativa_sai_zero_e_diz_por_que(self, tmp_path: Path) -> None:
        r = _rodar(
            tmp_path,
            "--restore-all-and-exit",
            "--unit-path",
            str(tmp_path / "sem-unit.service"),
            env_extra={hb.LOGINCTL_ENV: str(tmp_path / "sem-loginctl")},
        )
        assert r.returncode == 0, r.stdout + r.stderr
        assert "restore_sem_sessao_ativa" in r.stdout

    def test_uid_zero_explicito_continua_recusado(self, tmp_path: Path) -> None:
        r = _rodar(
            tmp_path,
            "--restore-all-and-exit",
            env_extra={"HEFESTO_BROKER_ALLOWED_UID": "0"},
        )
        assert r.returncode == 1
        assert "allowed_uid_root_recusado" in r.stdout

    def test_fechar_tudo_sem_uid_nao_pede_uid(self, tmp_path: Path) -> None:
        r = _rodar(
            tmp_path,
            "--fechar-tudo-e-sair",
            "--unit-path",
            str(tmp_path / "sem-unit.service"),
            env_extra={hb.LOGINCTL_ENV: str(tmp_path / "sem-loginctl")},
        )
        assert "allowed_uid_missing" not in r.stdout
        assert r.returncode == 0, r.stdout + r.stderr


# ---------------------------------------------------------------------------
# As units: nada por máquina
# ---------------------------------------------------------------------------
class TestAsUnitsNaoGravamNinguem:
    def test_a_unit_nao_tem_uid(self) -> None:
        texto = SERVICE.read_text(encoding="utf-8")
        ativo = "\n".join(
            linha for linha in texto.splitlines() if not linha.lstrip().startswith("#")
        )
        assert "ALLOWED_UID" not in ativo
        assert "__SESSION_" not in ativo

    def test_o_socket_nao_tem_grupo_por_maquina(self) -> None:
        texto = SOCKET.read_text(encoding="utf-8")
        ativo = "\n".join(
            linha for linha in texto.splitlines() if not linha.lstrip().startswith("#")
        )
        assert "__SESSION_" not in ativo
        assert re.search(r"^SocketGroup=root$", ativo, re.MULTILINE)
        assert re.search(r"^SocketMode=0666$", ativo, re.MULTILINE)

    def test_o_install_nativo_nao_pergunta_uid_nem_grupo(self) -> None:
        texto = CAMADA.read_text(encoding="utf-8")
        i = texto.index("install_broker_host() {")
        corpo = texto[i : texto.index("\n}\n", i)]
        assert "_broker_uid" not in corpo
        assert "_broker_grupo" not in corpo


# ---------------------------------------------------------------------------
# Os pacotes
# ---------------------------------------------------------------------------
def _renderizar_pacote(destino: Path, binario: str) -> subprocess.CompletedProcess[str]:
    return subprocess.run(
        ["bash", str(BROKER_DO_PACOTE), str(destino), binario],
        capture_output=True,
        text=True,
        cwd=str(REPO),
        check=False,
    )


def _renderizar_install(destino: Path) -> subprocess.CompletedProcess[str]:
    corpo = CAMADA.read_text(encoding="utf-8")
    i = corpo.index("_render_broker_units() {")
    funcao = corpo[i : corpo.index("\n}\n", i) + 3]
    script = f'{funcao}\n_render_broker_units "{SERVICE}" "{SOCKET}" "{destino}" 1\n'
    return subprocess.run(["bash", "-c", script], capture_output=True, text=True, check=False)


class TestBrokerDoPacote:
    def test_escreve_o_exec_start_no_binario_do_pacote(self, tmp_path: Path) -> None:
        binario = "/usr/lib/hefesto-dualsense4unix/hefesto-hidraw-broker"
        r = _renderizar_pacote(tmp_path, binario)
        assert r.returncode == 0, r.stderr
        servico = (tmp_path / "hefesto-hidraw-broker.service").read_text(encoding="utf-8")
        assert f"ExecStart={binario}\n" in servico
        assert f"ExecStartPre={binario} --fechar-tudo-e-sair\n" in servico
        assert f"ExecStopPost={binario} --restore-all-and-exit\n" in servico
        assert "/usr/local/lib" not in servico
        assert not re.search(r"__[A-Z_]+__", servico)
        assert "Environment=HEFESTO_BROKER_NO_NASCE_FECHADO=1\n" in servico

    def test_a_unit_do_pacote_e_a_do_install_tirando_so_o_caminho(self, tmp_path: Path) -> None:
        do_pacote = tmp_path / "pacote"
        do_install = tmp_path / "install"
        do_install.mkdir()
        assert (
            _renderizar_pacote(
                do_pacote, "/usr/local/lib/hefesto-dualsense4unix/hefesto-hidraw-broker"
            ).returncode
            == 0
        )
        assert _renderizar_install(do_install).returncode == 0
        for nome in ("hefesto-hidraw-broker.service", "hefesto-hidraw-broker.socket"):
            assert (do_pacote / nome).read_text(encoding="utf-8") == (do_install / nome).read_text(
                encoding="utf-8"
            ), nome

    def test_recusa_caminho_relativo(self, tmp_path: Path) -> None:
        r = _renderizar_pacote(tmp_path, "hefesto-hidraw-broker")
        assert r.returncode != 0
        assert not (tmp_path / "hefesto-hidraw-broker.service").exists()


@pytest.mark.parametrize("forma", sorted(PACOTES))
class TestOsQuatroPacotesLevamOBroker:
    def test_leva_o_broker_como_unit_de_sistema(self, forma: str) -> None:
        texto = PACOTES[forma].read_text(encoding="utf-8")
        assert re.search(r"^\s*bash scripts/broker_do_pacote\.sh ", texto, re.MULTILINE), (
            "a receita não chama o renderizador das units do broker"
        )
        assert "hefesto-hidraw-broker" in texto

    def test_a_regra_do_no_vai_fechada(self, forma: str) -> None:
        texto = PACOTES[forma].read_text(encoding="utf-8")
        assert "bash scripts/regra_do_no_aberta.sh" not in texto

    def test_o_pacote_liga_o_broker(self, forma: str) -> None:
        texto = LIGADORES[forma].read_text(encoding="utf-8")
        if forma == "nix":
            assert "systemd.sockets.hefesto-hidraw-broker.wantedBy" in texto
            assert "systemd.services.hefesto-hidraw-broker.wantedBy" in texto
        else:
            assert re.search(r"systemctl enable hefesto-hidraw-broker\.socket", texto), (
                "o pacote instalou a unit e não a ligou"
            )


def test_o_nix_aponta_o_loginctl_do_store() -> None:
    """No NixOS não há /usr/bin/loginctl: sem a env o broker recusa todo pedido."""
    texto = PACOTES["nix"].read_text(encoding="utf-8")
    assert "HEFESTO_BROKER_LOGINCTL=${systemd}/bin/loginctl" in texto


# ---------------------------------------------------------------------------
# A regra de sudo da ponte vale para o grupo
# ---------------------------------------------------------------------------
class TestRegraSudoPorGrupo:
    def _regra(self, tmp_path: Path, principal: str) -> subprocess.CompletedProcess[str]:
        return subprocess.run(
            ["bash", str(PONTE), "regra-sudo", principal],
            capture_output=True,
            text=True,
            cwd=str(tmp_path),
            env={"PATH": "/usr/bin:/bin", "HOME": str(tmp_path)},
            check=False,
        )

    def test_grupo_hefesto_entra_na_regra(self, tmp_path: Path) -> None:
        r = self._regra(tmp_path, "%hefesto")
        assert r.returncode == 0, r.stderr
        assert re.search(r"^%hefesto ALL=\(root\) NOPASSWD:", r.stdout, re.MULTILINE)

    def test_usuaria_nominal_segue_valendo(self, tmp_path: Path) -> None:
        r = self._regra(tmp_path, "fulana")
        assert r.returncode == 0, r.stderr
        assert re.search(r"^fulana ALL=\(root\) NOPASSWD:", r.stdout, re.MULTILINE)

    @pytest.mark.parametrize("ruim", ["ALL", "%ALL", "%", "%%hefesto", "%he festo"])
    def test_todo_mundo_e_nome_torto_sao_recusados(self, tmp_path: Path, ruim: str) -> None:
        r = self._regra(tmp_path, ruim)
        assert r.returncode != 0
        assert "NOPASSWD" not in r.stdout

    def test_o_grupo_e_a_conta_saem_cada_um_na_sua_linha(self, tmp_path: Path) -> None:
        """O grupo serve a segunda conta; a conta vale já, antes do novo login."""
        r = subprocess.run(
            ["bash", str(PONTE), "regra-sudo", "%hefesto", "fulana"],
            capture_output=True,
            text=True,
            cwd=str(tmp_path),
            env={"PATH": "/usr/bin:/bin", "HOME": str(tmp_path)},
            check=False,
        )
        assert r.returncode == 0, r.stderr
        linhas = re.findall(r"^(\S+) ALL=\(root\) NOPASSWD: HEFESTO_BT_PONTE$", r.stdout, re.MULTILINE)
        assert linhas == ["%hefesto", "fulana"]
        visudo = shutil.which("visudo") or next(
            (c for c in ("/usr/sbin/visudo", "/sbin/visudo") if os.path.exists(c)), None
        )
        if visudo is not None:
            regra = tmp_path / "regra"
            regra.write_text(r.stdout, encoding="utf-8")
            v = subprocess.run([visudo, "-cqf", str(regra)], capture_output=True, text=True, check=False)
            assert v.returncode == 0, v.stdout + v.stderr

    def test_um_principal_torto_entre_bons_recusa_a_regra_inteira(self, tmp_path: Path) -> None:
        r = subprocess.run(
            ["bash", str(PONTE), "regra-sudo", "%hefesto", "ALL"],
            capture_output=True,
            text=True,
            cwd=str(tmp_path),
            env={"PATH": "/usr/bin:/bin", "HOME": str(tmp_path)},
            check=False,
        )
        assert r.returncode != 0
        assert "NOPASSWD" not in r.stdout

    def test_o_install_abre_a_ponte_ao_grupo_e_a_conta_que_instala(self) -> None:
        """Só o grupo deixava a conta que acabou de entrar nele sem a ponte até o novo login."""
        texto = CAMADA.read_text(encoding="utf-8")
        i = texto.index("install_bt_ponte_privilegiada_host() {")
        corpo = texto[i : texto.index("\n}\n", i)]
        assert re.search(r'regra-sudo "%hefesto" "\$\{_ponte_usuaria\}"', corpo), corpo

    def test_o_install_poe_a_conta_no_grupo_hefesto(self) -> None:
        texto = CAMADA.read_text(encoding="utf-8")
        i = texto.index("_garantir_a_conta_no_grupo_hefesto() {")
        corpo = texto[i : texto.index("\n}\n", i)]
        assert "groupadd" in corpo
        assert "usermod -aG hefesto" in corpo
        assert os.path.exists(PONTE)
