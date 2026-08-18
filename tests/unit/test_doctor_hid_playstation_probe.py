"""PROBE-MORTO-PS-01 — o detector do DualSense que o kernel abortou no probe.

O defeito, medido na máquina dela em 08/08/2026 (6 vezes): o driver
`playstation` aborta a probe, e o controle conecta no Bluetooth, acende a luz
do próprio firmware e NÃO existe para o sistema — sem hidraw, sem input, sem
nó de LED. A dona tinha dois controles ligados, a janela mostrava um, e nada
no produto sabia dizer por quê. O `check_hid_playstation` só conferia se o
MÓDULO tinha carregado — e módulo carregado convive com controle invisível.

O que estes testes travam, além da detecção:

- **o transitório não pode gritar.** Os 6 abortos de 08/08 recuperaram
  sozinhos em 2 a 20 min. Um FAIL por aborto que já passou vira ruído e ensina
  a ignorar o doctor: aborto sem órfão AGORA é `info`, nunca warn/fail;
- **o órfão de agora não pode calar.** Órfão em `/sys/bus/hid/devices` sem
  symlink `driver` é FAIL com a cura nomeada;
- **`journalctl -k` é proibido** — o -k implica o boot atual e devolve ZERO em
  qualquer janela que atravesse reboot, indistinguível de "não houve nada"
  (quatro medições falsas já pagas por isso; índice de 08/08, §8);
- **o escopo é estreito** — barramento 0005 (Bluetooth) e vendor 054C (Sony),
  o mesmo do `bt_rebind_orphans.sh`: o vpad do próprio hefesto nasce no
  barramento 0003 e um Nintendo órfão não é deste check;
- **o doctor confere e não cura** — a função aponta o rebind e a vigia, e não
  executa nem um nem outro.

As funções são extraídas do `doctor.sh` e rodam em bash com sysfs de mentira e
`journalctl`/`systemctl` de mentira — sem hardware, sem root, sem journal real.
"""

from __future__ import annotations

import os
import re
import shutil
import subprocess
from pathlib import Path

BASH = shutil.which("bash") or "/bin/bash"
REPO_ROOT = Path(__file__).resolve().parents[2]
DOCTOR_PATH = REPO_ROOT / "scripts" / "doctor.sh"
REBIND_PATH = REPO_ROOT / "scripts" / "bt_rebind_orphans.sh"

DOCTOR = DOCTOR_PATH.read_text(encoding="utf-8") if DOCTOR_PATH.exists() else ""

# A instância medida na máquina dela em 08/08/2026 (não é MAC, é o id do
# device HID: BUS:VID:PID.INSTANCIA).
INSTANCIA = "0005:054C:0CE6.0069"
OUTRA = "0005:054C:0CE6.006A"

# O bloco exato do journal dela — as quatro linhas, na ordem em que saíram.
JORNAL_ABORTO = "\n".join(
    (
        f"ago 08 23:36:14 maquina kernel: playstation {INSTANCIA}: "
        "Failed to retrieve feature with reportID 32: -5",
        f"ago 08 23:36:14 maquina kernel: playstation {INSTANCIA}: "
        "Failed to retrieve DualSense firmware info: -5",
        f"ago 08 23:36:14 maquina kernel: playstation {INSTANCIA}: Failed to create dualsense.",
        f"ago 08 23:36:14 maquina kernel: playstation {INSTANCIA}: "
        "probe with driver playstation failed with error -5",
    )
) + "\n"

JORNAL_LIMPO = (
    "ago 08 23:36:10 maquina kernel: playstation 0005:054C:0CE6.0068: "
    "Registered DualSense controller hw_version=0x00000710 fw_version=0x0110002a\n"
    "ago 08 23:40:00 maquina kernel: usb 3-3: novo device qualquer\n"
)

FERRAMENTAS = ("sed", "awk", "sort", "basename", "cat")


def _extrai_funcao_bash(fonte: str, nome: str) -> str:
    match = re.search(rf"^{re.escape(nome)}\(\) \{{\n", fonte, re.MULTILINE)
    assert match is not None, f"função {nome}() não encontrada"
    fim = re.search(r"^\}$", fonte[match.end() :], re.MULTILINE)
    assert fim is not None, f"fim de {nome}() não encontrado"
    return fonte[match.start() : match.end() + fim.end() + 1]


def _sem_comentarios(texto: str) -> str:
    linhas = [re.sub(r"(^|\s)#.*$", r"\1", linha) for linha in texto.splitlines()]
    return "\n".join(linhas)


def _roda_script(
    tmp_path: Path,
    corpo: str,
    entrada: str = "",
    env_extra: dict[str, str] | None = None,
    path: str | None = None,
) -> subprocess.CompletedProcess[str]:
    script = tmp_path / "cena.sh"
    script.write_text(corpo, encoding="utf-8")
    env = dict(os.environ)
    if path is not None:
        env["PATH"] = path
    env.update(env_extra or {})
    return subprocess.run(
        [BASH, str(script)],
        input=entrada,
        capture_output=True,
        text=True,
        check=False,
        env=env,
    )


def _bin_isolado(tmp_path: Path) -> Path:
    """PATH mínimo e CONTROLADO: só as ferramentas que a função usa.

    Sem isso, o teste do caso "sem journalctl" seria mentira — o journalctl
    real do sistema apareceria no PATH e o `command -v` acharia.
    """
    binario = tmp_path / "bin"
    binario.mkdir(exist_ok=True)
    for nome in FERRAMENTAS:
        alvo = shutil.which(nome)
        assert alvo is not None, f"ferramenta {nome} ausente no sistema"
        destino = binario / nome
        if not destino.exists():
            destino.symlink_to(alvo)
    return binario


def _stub(binario: Path, nome: str, corpo: str) -> None:
    caminho = binario / nome
    caminho.write_text(f"#!/bin/sh\n{corpo}\n", encoding="utf-8")
    caminho.chmod(0o755)


def _monta_sysfs(tmp_path: Path, devices: dict[str, bool]) -> Path:
    """sysfs de mentira: {id_do_device: tem_driver}."""
    raiz = tmp_path / "hid-devices"
    raiz.mkdir(exist_ok=True)
    for id_dev, tem_driver in devices.items():
        dev = raiz / id_dev
        dev.mkdir(exist_ok=True)
        if tem_driver:
            driver = tmp_path / "driver-playstation"
            driver.mkdir(exist_ok=True)
            alvo = dev / "driver"
            if not alvo.exists():
                alvo.symlink_to(driver)
    return raiz


class TestWiringDoCheck:
    def test_bash_n_doctor(self) -> None:
        resultado = subprocess.run(
            ["bash", "-n", str(DOCTOR_PATH)], capture_output=True, text=True, check=False
        )
        assert resultado.returncode == 0, resultado.stderr

    def test_check_definido_e_chamado_no_main(self) -> None:
        assert "check_hid_playstation_probe_abortado()" in DOCTOR
        assert re.search(
            r"^\s*check_hid_playstation_probe_abortado\s*$", DOCTOR, re.MULTILINE
        ), "o check precisa ser CHAMADO no fluxo principal, não só definido"

    def test_check_roda_junto_do_irmao_que_so_via_o_modulo(self) -> None:
        # check_hid_playstation dá PASS com o módulo carregado — e módulo
        # carregado convive com controle invisível. Os dois andam juntos.
        assert re.search(
            r"^\s*check_hid_playstation\n\s*check_hid_playstation_probe_abortado\s*$",
            DOCTOR,
            re.MULTILINE,
        ), "o detector de probe abortado vem logo depois do check do módulo"

    def test_usa_transport_kernel_nunca_journalctl_k(self) -> None:
        # Armadilha já paga quatro vezes nesta casa: `-k` implica o boot atual
        # e devolve ZERO em janela que atravessa reboot — e zero é
        # indistinguível de "não houve nada".
        corpo = _extrai_funcao_bash(DOCTOR, "check_hid_playstation_probe_abortado")
        assert "_TRANSPORT=kernel" in corpo
        assert not re.search(r"journalctl\s+(-b\s+)?-k\b", corpo), (
            "journalctl -k é proibido neste check"
        )
        assert "--since" in corpo, "a janela é de TEMPO — precisa atravessar reboot"

    def test_check_e_read_only_nunca_cura(self) -> None:
        # Regra da casa (o install.sh a repete): o doctor confere e não cura.
        # A cura aparece nas MENSAGENS (é dica legítima); o proibido é a
        # função EXECUTAR o rebind, mexer em serviço ou carregar módulo.
        corpo = _sem_comentarios(
            _extrai_funcao_bash(DOCTOR, "check_hid_playstation_probe_abortado")
        )
        for linha in corpo.splitlines():
            nu = linha.strip()
            assert not re.match(r"^(sudo\s+)?\S*bt_rebind_orphans\.sh", nu), (
                f"o doctor não executa a cura: {nu}"
            )
            assert not re.match(r"^(sudo\s+)?systemctl\s+(?!is-active)", nu), (
                f"o doctor não mexe em serviço: {nu}"
            )
            assert not re.match(r"^(sudo\s+)?(modprobe|rmmod|insmod)\b", nu), (
                f"recarregar hid_playstation derrubaria TODOS os DualSense: {nu}"
            )
        # E nada de escrever no sysfs (o bind é do bt_rebind_orphans.sh).
        assert "/bind" not in corpo, "escrever no bind é cura, não diagnóstico"

    def test_a_cura_apontada_existe_de_verdade(self) -> None:
        # Mensagem que manda rodar script inexistente é pior que silêncio.
        corpo = _extrai_funcao_bash(DOCTOR, "check_hid_playstation_probe_abortado")
        assert "bt_rebind_orphans.sh" in corpo
        assert REBIND_PATH.exists(), "a cura apontada tem de existir no repo"
        assert "hefesto-bt-health-watchdog.timer" in corpo, (
            "a vigia que chama o rebind de 2 em 2 min tem nome — e é ele"
        )

    def test_veredito_nomeia_a_causa_medida_e_nao_o_hardware(self) -> None:
        # Ela vetou por escrito a tese de hardware, depois de dias perdidos
        # nela. O texto do veredito não pode ressuscitá-la.
        corpo = _extrai_funcao_bash(DOCTOR, "check_hid_playstation_probe_abortado")
        assert "contenção" in corpo
        assert "assets/dkms/hid-playstation/README.md" in corpo, (
            "a cadeia medida elo a elo tem endereço — o veredito aponta para ele"
        )


class TestScanPuro:
    """Função PURA: stdin -> stdout, uma linha por instância que abortou."""

    def _roda(self, tmp_path: Path, entrada: str) -> subprocess.CompletedProcess[str]:
        funcao = _extrai_funcao_bash(DOCTOR, "_hid_playstation_probe_scan")
        return _roda_script(
            tmp_path, f"{funcao}\n_hid_playstation_probe_scan\n", entrada=entrada
        )

    def test_o_bloco_real_de_08_08_e_flagrado(self, tmp_path: Path) -> None:
        resultado = self._roda(tmp_path, JORNAL_ABORTO)
        assert resultado.returncode == 0, resultado.stderr
        assert resultado.stdout.strip() == f"{INSTANCIA} 1 1"

    def test_tres_falhas_de_feature_sao_contadas(self, tmp_path: Path) -> None:
        feature = (
            f"kernel: playstation {INSTANCIA}: Failed to retrieve feature with reportID 32: -5\n"
        )
        aborto = (
            f"kernel: playstation {INSTANCIA}: "
            "probe with driver playstation failed with error -5\n"
        )
        assert self._roda(tmp_path, feature * 3 + aborto).stdout.strip() == f"{INSTANCIA} 1 3"

    def test_aborto_sem_falha_de_feature_ainda_e_aborto(self, tmp_path: Path) -> None:
        # O gate é o ABORTO. Exigir as duas pontas esconderia um aborto por
        # outra causa — e o controle some do mesmo jeito.
        entrada = (
            f"kernel: playstation {INSTANCIA}: "
            "probe with driver playstation failed with error -110\n"
        )
        assert self._roda(tmp_path, entrada).stdout.strip() == f"{INSTANCIA} 1 0"

    def test_falha_de_feature_sem_aborto_fica_em_silencio(self, tmp_path: Path) -> None:
        # O transiente que o probe SOBREVIVEU não é notícia.
        entrada = (
            f"kernel: playstation {INSTANCIA}: Failed to retrieve feature with reportID 32: -5\n"
        )
        assert self._roda(tmp_path, entrada).stdout.strip() == ""

    def test_journal_limpo_sai_vazio(self, tmp_path: Path) -> None:
        resultado = self._roda(tmp_path, JORNAL_LIMPO)
        assert resultado.returncode == 0, resultado.stderr
        assert resultado.stdout.strip() == ""

    def test_entrada_vazia_sai_vazia(self, tmp_path: Path) -> None:
        resultado = self._roda(tmp_path, "")
        assert resultado.returncode == 0, resultado.stderr
        assert resultado.stdout.strip() == ""

    def test_instancias_sao_contadas_em_separado(self, tmp_path: Path) -> None:
        entrada = JORNAL_ABORTO + JORNAL_ABORTO.replace(INSTANCIA, OUTRA)
        assert self._roda(tmp_path, entrada).stdout.strip().splitlines() == [
            f"{INSTANCIA} 1 1",
            f"{OUTRA} 1 1",
        ]

    def test_probe_de_outro_driver_nao_e_deste_check(self, tmp_path: Path) -> None:
        # A cascata do hid-nintendo já tem check próprio; misturar os dois
        # daria veredito com a cura errada.
        entrada = (
            "kernel: nintendo 0005:057E:2009.0041: probe - fail = -110\n"
            "kernel: nintendo 0005:057E:2009.0041: Failed to get joycon info; ret=-110\n"
        )
        assert self._roda(tmp_path, entrada).stdout.strip() == ""


class TestOrfaosAgora:
    """Estado ATUAL em sysfs — é ele que decide entre FAIL e informação."""

    def _roda(
        self, tmp_path: Path, devices: dict[str, bool]
    ) -> subprocess.CompletedProcess[str]:
        raiz = _monta_sysfs(tmp_path, devices)
        funcao = _extrai_funcao_bash(DOCTOR, "_hid_playstation_orfaos_agora")
        return _roda_script(
            tmp_path,
            f"{funcao}\n_hid_playstation_orfaos_agora\n",
            env_extra={"HEFESTO_HID_DEVICES_DIR": str(raiz)},
        )

    def test_dualsense_bt_sem_driver_e_orfao(self, tmp_path: Path) -> None:
        resultado = self._roda(tmp_path, {INSTANCIA: False})
        assert resultado.returncode == 0, resultado.stderr
        assert resultado.stdout.strip() == INSTANCIA

    def test_dualsense_com_driver_nao_e_orfao(self, tmp_path: Path) -> None:
        assert self._roda(tmp_path, {INSTANCIA: True}).stdout.strip() == ""

    def test_vpad_do_proprio_hefesto_fica_de_fora(self, tmp_path: Path) -> None:
        # O vpad nasce por uhid no barramento 0003 — nunca é candidato.
        assert self._roda(tmp_path, {"0003:054C:0CE6.0007": False}).stdout.strip() == ""

    def test_orfao_nintendo_nao_e_deste_check(self, tmp_path: Path) -> None:
        assert self._roda(tmp_path, {"0005:057E:2009.0041": False}).stdout.strip() == ""

    def test_vid_minusculo_tambem_conta(self, tmp_path: Path) -> None:
        assert (
            self._roda(tmp_path, {"0005:054c:0ce6.0069": False}).stdout.strip()
            == "0005:054c:0ce6.0069"
        )

    def test_sysfs_vazio_sai_vazio(self, tmp_path: Path) -> None:
        resultado = self._roda(tmp_path, {})
        assert resultado.returncode == 0, resultado.stderr
        assert resultado.stdout.strip() == ""

    def test_so_o_orfao_sai_entre_varios(self, tmp_path: Path) -> None:
        resultado = self._roda(
            tmp_path,
            {
                "0005:054C:0CE6.0068": True,
                INSTANCIA: False,
                "0003:054C:0CE6.0007": False,
            },
        )
        assert resultado.stdout.strip() == INSTANCIA


class TestVeredito:
    """Os três casos, com sysfs, journalctl e systemctl de mentira."""

    def _roda(
        self,
        tmp_path: Path,
        jornal: str,
        devices: dict[str, bool],
        timer: str = "active",
        com_journalctl: bool = True,
        com_systemctl: bool = True,
    ) -> subprocess.CompletedProcess[str]:
        binario = _bin_isolado(tmp_path)
        raiz = _monta_sysfs(tmp_path, devices)
        if com_journalctl:
            fixture = tmp_path / "jornal.txt"
            fixture.write_text(jornal, encoding="utf-8")
            argv = tmp_path / "journalctl.argv"
            _stub(
                binario,
                "journalctl",
                f'printf "%s\\n" "$*" > "{argv}"\nexec cat "{fixture}"',
            )
        if com_systemctl:
            _stub(binario, "systemctl", f'printf "{timer}\\n"')
        corpo = "\n".join(
            (
                'pass() { printf "PASS: %s\\n" "$*"; }',
                'fail() { printf "FAIL: %s\\n" "$*"; }',
                'warn() { printf "WARN: %s\\n" "$*"; }',
                'info() { printf "INFO: %s\\n" "$*"; }',
                _extrai_funcao_bash(DOCTOR, "_hid_playstation_probe_scan"),
                _extrai_funcao_bash(DOCTOR, "_hid_playstation_orfaos_agora"),
                _extrai_funcao_bash(DOCTOR, "check_hid_playstation_probe_abortado"),
                "check_hid_playstation_probe_abortado",
                'printf "RC=%s\\n" "$?"',
            )
        )
        return _roda_script(
            tmp_path,
            corpo,
            env_extra={"HEFESTO_HID_DEVICES_DIR": str(raiz)},
            path=str(binario),
        )

    # --- caso 1: órfão AGORA -------------------------------------------------
    def test_orfao_agora_e_fail_com_a_cura_nomeada(self, tmp_path: Path) -> None:
        resultado = self._roda(tmp_path, JORNAL_ABORTO, {INSTANCIA: False})
        assert "RC=0" in resultado.stdout, resultado.stderr
        assert "FAIL: DualSense ÓRFÃO AGORA" in resultado.stdout
        assert INSTANCIA in resultado.stdout
        assert "bt_rebind_orphans.sh" in resultado.stdout
        assert "sem hidraw" in resultado.stdout, (
            "o veredito diz O QUE o usuário perdeu, não só que houve um erro"
        )

    def test_orfao_agora_cruza_com_o_aborto_do_journal(self, tmp_path: Path) -> None:
        resultado = self._roda(tmp_path, JORNAL_ABORTO, {INSTANCIA: False})
        assert "1x aborto e 1x falha de feature no journal" in resultado.stdout

    def test_orfao_agora_e_fail_mesmo_sem_journal(self, tmp_path: Path) -> None:
        # O journal pode estar ilegível (sem grupo adm). O sintoma continua
        # sendo o sysfs, e ele vale sozinho.
        resultado = self._roda(
            tmp_path, "", {INSTANCIA: False}, com_journalctl=False, com_systemctl=False
        )
        assert "FAIL: DualSense ÓRFÃO AGORA" in resultado.stdout

    def test_dois_orfaos_dao_dois_fails(self, tmp_path: Path) -> None:
        resultado = self._roda(
            tmp_path, JORNAL_ABORTO, {INSTANCIA: False, OUTRA: False}
        )
        assert resultado.stdout.count("FAIL: DualSense ÓRFÃO AGORA") == 2

    def test_vigia_ativa_promete_a_volta_sozinha(self, tmp_path: Path) -> None:
        resultado = self._roda(
            tmp_path, JORNAL_ABORTO, {INSTANCIA: False}, timer="active"
        )
        assert "INFO: a vigia hefesto-bt-health-watchdog.timer está ativa" in resultado.stdout
        assert "WARN" not in resultado.stdout, "vigia ativa não gera aviso"

    def test_vigia_parada_vira_aviso(self, tmp_path: Path) -> None:
        resultado = self._roda(
            tmp_path, JORNAL_ABORTO, {INSTANCIA: False}, timer="inactive"
        )
        assert "WARN: a vigia" in resultado.stdout
        assert "enable --now hefesto-bt-health-watchdog.timer" in resultado.stdout

    # --- caso 2: aborto RECUPERADO ------------------------------------------
    def test_aborto_recuperado_e_informacao_nunca_alarme(self, tmp_path: Path) -> None:
        # A decisão que separa diagnóstico de ruído: os 6 abortos de 08/08
        # recuperaram sozinhos em 2 a 20 min. Gritar por eles ensina a
        # ignorar o doctor.
        resultado = self._roda(tmp_path, JORNAL_ABORTO, {INSTANCIA: True})
        assert "RC=0" in resultado.stdout, resultado.stderr
        assert "FAIL" not in resultado.stdout
        assert "WARN" not in resultado.stdout
        assert "INFO: aborto de probe do hid-playstation" in resultado.stdout
        assert "JÁ RECUPERADO" in resultado.stdout

    def test_aborto_recuperado_diz_quantos_e_quais(self, tmp_path: Path) -> None:
        jornal = JORNAL_ABORTO * 3 + JORNAL_ABORTO.replace(INSTANCIA, OUTRA) * 3
        resultado = self._roda(tmp_path, jornal, {INSTANCIA: True})
        assert "6x 'probe with driver playstation failed'" in resultado.stdout
        assert INSTANCIA in resultado.stdout and OUTRA in resultado.stdout
        assert "PASS" not in resultado.stdout, (
            "houve aborto na janela — dar OK apagaria o histórico"
        )

    def test_aborto_de_um_controle_com_outro_orfao_ainda_e_fail(
        self, tmp_path: Path
    ) -> None:
        # Um controle recuperou, o outro não: manda o pior dos dois.
        resultado = self._roda(
            tmp_path, JORNAL_ABORTO, {INSTANCIA: True, OUTRA: False}
        )
        assert "FAIL: DualSense ÓRFÃO AGORA" in resultado.stdout
        assert OUTRA in resultado.stdout

    # --- caso 3: nada --------------------------------------------------------
    def test_journal_limpo_e_sem_orfao_da_pass(self, tmp_path: Path) -> None:
        resultado = self._roda(tmp_path, JORNAL_LIMPO, {INSTANCIA: True})
        assert "RC=0" in resultado.stdout, resultado.stderr
        assert "PASS: nenhum DualSense órfão agora" in resultado.stdout
        assert "FAIL" not in resultado.stdout and "WARN" not in resultado.stdout

    def test_sem_journalctl_nao_finge_ter_olhado(self, tmp_path: Path) -> None:
        # Sem journal não há PASS sobre o histórico: zero por falta de dado é
        # indistinguível de zero por ausência de defeito.
        resultado = self._roda(
            tmp_path, "", {INSTANCIA: True}, com_journalctl=False, com_systemctl=False
        )
        assert "PASS" not in resultado.stdout
        assert "sem journalctl" in resultado.stdout

    # --- a régua do journal --------------------------------------------------
    def test_o_journalctl_e_chamado_com_transport_e_since(self, tmp_path: Path) -> None:
        self._roda(tmp_path, JORNAL_LIMPO, {INSTANCIA: True})
        argv = (tmp_path / "journalctl.argv").read_text(encoding="utf-8")
        assert "_TRANSPORT=kernel" in argv
        assert "--since" in argv
        assert not re.search(r"(^|\s)-k(\s|$)", argv), (
            "-k implica o boot atual e mataria a janela que atravessa reboot"
        )
        assert not re.search(r"(^|\s)-b(\s|$)", argv), "-b prende a janela a este boot"

    def test_janela_default_e_larga_o_bastante_para_o_episodio(self) -> None:
        # MEDIDO na máquina dela em 09/08: com 24 h a consulta via 1 dos 6
        # abortos de 08/08 (o boot dela é mais velho que um dia); com 3 dias,
        # os 6. Janela curta devolve quase-zero e ensina a mesma lição errada
        # que o `-k`: "não houve nada".
        corpo = _extrai_funcao_bash(DOCTOR, "check_hid_playstation_probe_abortado")
        default = re.search(
            r'janela="\$\{HEFESTO_DOCTOR_PROBE_JANELA:-(\d+) (days?|hours?) ago\}"', corpo
        )
        assert default is not None, "a janela default precisa ser declarada e legível"
        dias = int(default.group(1)) / (1 if default.group(2).startswith("day") else 24)
        assert dias >= 3, f"janela default de {dias} dia(s) é curta demais para o episódio"

    def test_janela_e_configuravel_para_o_teste_e_para_ela(self, tmp_path: Path) -> None:
        binario = _bin_isolado(tmp_path)
        raiz = _monta_sysfs(tmp_path, {INSTANCIA: True})
        fixture = tmp_path / "jornal.txt"
        fixture.write_text(JORNAL_LIMPO, encoding="utf-8")
        argv = tmp_path / "journalctl.argv"
        _stub(
            binario,
            "journalctl",
            f'printf "%s\\n" "$*" > "{argv}"\nexec cat "{fixture}"',
        )
        _stub(binario, "systemctl", 'printf "active\\n"')
        corpo = "\n".join(
            (
                'pass() { printf "PASS: %s\\n" "$*"; }',
                'fail() { printf "FAIL: %s\\n" "$*"; }',
                'warn() { printf "WARN: %s\\n" "$*"; }',
                'info() { printf "INFO: %s\\n" "$*"; }',
                _extrai_funcao_bash(DOCTOR, "_hid_playstation_probe_scan"),
                _extrai_funcao_bash(DOCTOR, "_hid_playstation_orfaos_agora"),
                _extrai_funcao_bash(DOCTOR, "check_hid_playstation_probe_abortado"),
                "check_hid_playstation_probe_abortado",
            )
        )
        resultado = _roda_script(
            tmp_path,
            corpo,
            env_extra={
                "HEFESTO_HID_DEVICES_DIR": str(raiz),
                "HEFESTO_DOCTOR_PROBE_JANELA": "7 days ago",
            },
            path=str(binario),
        )
        assert "7 days ago" in argv.read_text(encoding="utf-8")
        assert "7 days ago" in resultado.stdout, (
            "o veredito declara a janela que mediu — instrumento que não "
            "declara a régua já produziu alarme falso nesta casa"
        )
