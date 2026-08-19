"""MIGRACAO-BLUEZ-DEPRECIADOS-01 — o diagnóstico não pode calar quando a
ferramenta velha some.

O BlueZ DEPRECIOU ``hciconfig``, ``hcitool`` e ``sdptool``, e cada família de
distribuição os mudou de pacote (``bluez-deprecated``,
``bluez-deprecated-tools``). Os scripts desta casa os chamavam sempre no mesmo
molde::

    if command -v hciconfig >/dev/null 2>&1; then
        ... mede ...
    fi                      # <- e, sem a ferramenta, NADA acontecia

Numa máquina sem o pacote, o check inteiro sumia da saída: nenhuma linha, nenhum
aviso, e a conferência final saía verde **sem ter medido**. Mentir por omissão é
pior que não medir, porque quem lê conclui "está tudo bem".

O que este arquivo trava, por pergunta migrada:

* **quem é o adaptador** e **quem está conectado** têm sucessor VIVO — sysfs do
  kernel e D-Bus do BlueZ. Migrados, com a depreciada como plano B (quem AINDA
  a tem não pode perder leitura: isso seria regressão).
* **contadores RX/TX errors**, **link policy** (adaptador e conexão) e **browse
  SDP sob demanda** NÃO têm sucessor vivo — conferido nos ``--help`` do
  ``btmgmt`` e do ``bluetoothctl`` 5.86 desta casa em 19/08/2026. Onde a
  depreciada falta, a leitura SE PERDE e o código tem de **dizer que não sabe**.

O molde dos testes é o dos irmãos (``test_doctor_radio_pareamento.py``): fakes
no PATH, nada do sistema real é tocado. A novidade é o ``sandbox_sem_velhas``,
um PATH montado com links para tudo do sistema **menos** as três depreciadas —
sem ele não há como exercitar a máquina que não as tem, que é justamente a que
recebia o diagnóstico mudo.
"""

from __future__ import annotations

import contextlib
import os
import re
import shutil
import stat
import subprocess
from pathlib import Path

import pytest

REPO_ROOT = Path(__file__).resolve().parents[2]
DOCTOR = REPO_ROOT / "scripts" / "doctor.sh"
ACTIVE_MODE = REPO_ROOT / "scripts" / "bt_active_mode.sh"
NOSNIFF = REPO_ROOT / "scripts" / "bt_nosniff_now.sh"
WATCHDOG = REPO_ROOT / "scripts" / "bt_health_watchdog.sh"
STORM = REPO_ROOT / "scripts" / "storm_watch.sh"
MEDIR_W3 = REPO_ROOT / "scripts" / "medir_w3_coex.sh"

BASH = shutil.which("bash") or "/bin/bash"

#: Depreciadas do BlueZ — as três que a upstream aposentou.
VELHAS = ("hciconfig", "hcitool", "sdptool")

def _oui_do_pro_genuino() -> str:
    """A OUI do Pro sai do PRODUTO — nunca escrita aqui.

    Mesma guarda de `test_a_oui_separa_o_clone_do_genuino.py`: forma de MAC em
    `tests/` só nas faixas forjadas (test_anonimato_de_fixtures.py), e OUI real
    não é faixa forjada. Ler do script tem um bônus: se a fonte da verdade
    mudar, este teste segue a mudança em vez de fossilizar a antiga.
    """
    achado = re.search(
        r'^OUI_NINTENDO_REAL="([0-9A-Fa-f:]+)"', ACTIVE_MODE.read_text(encoding="utf-8"), re.M
    )
    assert achado, "bt_active_mode.sh perdeu o OUI_NINTENDO_REAL"
    return achado.group(1)


#: MAC do Pro Controller genuíno na máscara da casa (octetos 4 e 5 zerados —
#: test_docs_mac_anonimato.py é o portão dessa convenção).
MAC_PRO = f"{_oui_do_pro_genuino()}:00:00:11"
PATH_PRO = "/org/bluez/hci0/dev_" + MAC_PRO.replace(":", "_")


# ---------------------------------------------------------------------------
# Bancada
# ---------------------------------------------------------------------------
@pytest.fixture(scope="module")
def sandbox_sem_velhas(tmp_path_factory: pytest.TempPathFactory) -> Path:
    """Um PATH com TUDO do sistema menos `hciconfig`, `hcitool` e `sdptool`.

    Simula a máquina em que as depreciadas não estão instaladas — a única em
    que o defeito aparece. Links, não cópias: o teste continua rodando os
    binários de verdade (grep, awk, date...), só não enxerga as três.
    """
    alvo = tmp_path_factory.mktemp("bin-sem-velhas")
    for origem in ("/usr/bin", "/bin", "/usr/sbin", "/sbin"):
        d = Path(origem)
        if not d.is_dir():
            continue
        for entrada in d.iterdir():
            if entrada.name in VELHAS:
                continue
            destino = alvo / entrada.name
            if destino.exists() or destino.is_symlink():
                continue
            with contextlib.suppress(OSError):
                destino.symlink_to(entrada)
    for velha in VELHAS:
        assert shutil.which(velha, path=str(alvo)) is None, (
            f"o sandbox precisa NÃO ter {velha} — é o cenário sob teste"
        )
    return alvo


def _fake(dirbin: Path, nome: str, corpo: str) -> Path:
    dirbin.mkdir(parents=True, exist_ok=True)
    alvo = dirbin / nome
    alvo.write_text("#!/usr/bin/env bash\n" + corpo, encoding="utf-8")
    alvo.chmod(alvo.stat().st_mode | stat.S_IEXEC | stat.S_IXGRP | stat.S_IXOTH)
    return alvo


def _busctl_fake(
    dirbin: Path,
    *,
    alias: str = "meowsystem",
    connected: str = "false",
    uuids: str = 'as 1 "00001124-0000-1000-8000-00805f9b34fb"',
) -> Path:
    """`busctl` de mentira com UM device (o Pro genuíno) e um adaptador hci0."""
    return _fake(
        dirbin,
        "busctl",
        f"""
case "$1 $2" in
  "tree org.bluez") printf '/org/bluez/hci0\\n{PATH_PRO}\\n' ;;
  "get-property org.bluez")
    case "$3 $5" in
      "/org/bluez/hci0 Alias") echo 's "{alias}"' ;;
      *)
        case "$5" in
          Alias) echo 's "Pro Controller"' ;;
          Paired|Trusted) echo 'b true' ;;
          Connected) echo 'b {connected}' ;;
          UUIDs) echo '{uuids}' ;;
          *) echo '' ;;
        esac ;;
    esac ;;
esac
exit 0
""",
    )


def _rodar_check(check: str, *dirs: Path, **env_extra: str) -> str:
    """Roda UMA função do doctor.sh com o PATH montado pelos diretórios dados."""
    env = {
        "PATH": ":".join(str(d) for d in dirs),
        "DOCTOR_SH": str(DOCTOR),
        "HOME": env_extra.pop("HOME", "/nonexistent-hefesto"),
        **env_extra,
    }
    res = subprocess.run(
        [BASH, "-c", f'set --; source "$DOCTOR_SH"; {check}'],
        capture_output=True,
        text=True,
        timeout=60,
        check=False,
        env=env,
    )
    return res.stdout


# ---------------------------------------------------------------------------
# 1. Contadores de erro do rádio — leitura SEM sucessor vivo.
# ---------------------------------------------------------------------------
class TestContadoresDeErroDoRadio:
    """`hciconfig hciN` -> `errors:N`. Pergunta: o rádio acumulou erro?

    Não tem sucessor: os contadores são o `hci_dev_stats` do kernel, entregue só
    pelo ioctl HCIGETDEVINFO. `btmgmt` e `bluetoothctl` não têm comando para
    isso. Então o dever do doctor é DIZER que não sabe.
    """

    def test_sem_hciconfig_o_doctor_diz_que_nao_sabe(
        self, tmp_path: Path, sandbox_sem_velhas: Path
    ) -> None:
        fakes = tmp_path / "fakes"
        _busctl_fake(fakes)
        saida = _rodar_check("check_bt_radio", fakes, sandbox_sem_velhas)
        assert "NÃO SEI" in saida, (
            "sem hciconfig o doctor CALAVA: a seção de contadores sumia da "
            "saída e a conferência passava sem ter medido nada.\n" + saida
        )
        assert "bluez-deprecated" in saida, "tem de dizer COMO recuperar a medida"
        assert "adaptador BT sem erros" not in saida, (
            "não pode afirmar rádio limpo sem ter lido contador nenhum"
        )

    def test_com_hciconfig_a_leitura_antiga_continua_valendo(
        self, tmp_path: Path
    ) -> None:
        """Plano B preservado: quem TEM a ferramenta velha não perde leitura."""
        fakes = tmp_path / "fakes"
        _busctl_fake(fakes)
        _fake(
            fakes,
            "hciconfig",
            "printf 'hci0:\\tRX bytes:1 acl:0 sco:0 events:1 errors:42\\n"
            "\\tTX bytes:1 acl:0 sco:0 commands:1 errors:7\\n'\nexit 0\n",
        )
        saida = _rodar_check("check_bt_radio", fakes, "/usr/bin", "/bin")
        assert "[WARN] adaptador BT com erros acumulados (RX/TX: 42/7)" in saida, saida


# ---------------------------------------------------------------------------
# 2. Link policy — leitura SEM sucessor vivo (adaptador e conexão).
# ---------------------------------------------------------------------------
class TestLinkPolicyDoModoAtivoNintendo:
    def _systemctl_fake(self, dirbin: Path) -> Path:
        return _fake(
            dirbin,
            "systemctl",
            'case "$1 $2" in\n'
            '  "is-active hefesto-bt-bonds-snapshot.timer"|'
            '"is-active hefesto-bt-health-watchdog.timer") echo active ;;\n'
            "  *) exit 1 ;;\n"
            "esac\nexit 0\n",
        )

    def test_sem_as_velhas_nao_afirma_modo_ativo(
        self, tmp_path: Path, sandbox_sem_velhas: Path
    ) -> None:
        """Alias certo + SNIFF ilegível não é "modo ativo OK" — é meia medida.

        A link policy não existe na mgmt API, então nem btmgmt nem bluetoothctl
        a leem. Antes, sem `hciconfig`, o bloco inteiro era pulado e a ausência
        de aviso passava por saúde.
        """
        fakes = tmp_path / "fakes"
        _busctl_fake(fakes, alias="Nintendo meowsystem", connected="true")
        self._systemctl_fake(fakes)
        saida = _rodar_check("check_bt_resilience", fakes, sandbox_sem_velhas)
        assert "NÃO SEI dizer o estado do SNIFF" in saida, saida
        assert "modo ativo p/ Nintendo (nome" not in saida, (
            "não pode dar OK no modo ativo sem ter conferido a link policy"
        )
        assert "bluez-deprecated" in saida

    def test_com_as_velhas_o_veredito_medido_continua(self, tmp_path: Path) -> None:
        """Regressão: em quem TEM as depreciadas, o [ OK ] de 23/07 fica igual."""
        fakes = tmp_path / "fakes"
        _busctl_fake(fakes, alias="Nintendo meowsystem", connected="true")
        self._systemctl_fake(fakes)
        _fake(
            fakes,
            "hciconfig",
            "printf 'hci0:\\tType: Primary  Bus: USB\\n"
            "\\tLink policy: RSWITCH HOLD SNIFF PARK\\n'\nexit 0\n",
        )
        _fake(fakes, "hcitool", "echo 'Link policy: RSWITCH'\nexit 0\n")
        saida = _rodar_check("check_bt_resilience", fakes, "/usr/bin", "/bin")
        assert "[ OK ] modo ativo p/ Nintendo (nome 'Nintendo meowsystem'" in saida, saida


# ---------------------------------------------------------------------------
# 3. Quem está conectado — pergunta COM sucessor vivo (D-Bus), com plano B.
# ---------------------------------------------------------------------------
class TestQuemEstaConectado:
    def test_sai_do_dbus_sem_hcitool(
        self, tmp_path: Path, sandbox_sem_velhas: Path
    ) -> None:
        fakes = tmp_path / "fakes"
        _busctl_fake(fakes, connected="true")
        saida = _rodar_check("_bt_macs_conectados", fakes, sandbox_sem_velhas)
        assert saida.strip() == MAC_PRO, (
            "a lista de conectados tem de sair do D-Bus, que está vivo — "
            f"saiu: {saida!r}"
        )

    def test_sem_dbus_cai_no_hcitool_de_quem_o_tem(self, tmp_path: Path) -> None:
        """Plano B: com o bluetoothd fora do ar, o `hcitool con` ainda responde."""
        fakes = tmp_path / "fakes"
        _fake(fakes, "busctl", "exit 1\n")
        _fake(
            fakes,
            "hcitool",
            f"echo '> ACL {MAC_PRO.lower()} handle 12 state 1 lm SLAVE AUTH ENCRYPT'\n",
        )
        saida = _rodar_check("_bt_macs_conectados", fakes, "/usr/bin", "/bin")
        assert saida.strip() == MAC_PRO, (
            "perder a leitura em quem TEM a ferramenta velha é regressão — "
            f"saiu: {saida!r}"
        )

    def test_sem_nenhuma_das_duas_devolve_vazio_sem_estourar(
        self, tmp_path: Path, sandbox_sem_velhas: Path
    ) -> None:
        fakes = tmp_path / "fakes"
        _fake(fakes, "busctl", "exit 1\n")
        saida = _rodar_check("_bt_macs_conectados", fakes, sandbox_sem_velhas)
        assert saida.strip() == ""


# ---------------------------------------------------------------------------
# 4. Browse SDP sob demanda — leitura SEM sucessor vivo.
# ---------------------------------------------------------------------------
_INFO_HID = """[General]
Name=DualSense Wireless Controller
Services=00001124-0000-1000-8000-00805f9b34fb;

[LinkKey]
Type=4
"""
_CACHE_ENVENENADO = "[General]\nName=DualSense Wireless Controller\n"


def _arvore_bluez_falsa(raiz: Path, mac: str) -> None:
    adp = raiz / "AA:BB:CC:00:00:01"
    (adp / "cache").mkdir(parents=True)
    (adp / mac).mkdir()
    (adp / mac / "info").write_text(_INFO_HID, encoding="utf-8")
    (adp / "cache" / mac).write_text(_CACHE_ENVENENADO, encoding="utf-8")


def _sudo_fake(dirbin: Path, storage: Path) -> Path:
    """`sudo` de mentira: tira o `-n` e reaponta /var/lib/bluetooth p/ o tmpdir."""
    return _fake(
        dirbin,
        "sudo",
        f"""
args=()
for a in "$@"; do
    [[ "$a" == "-n" ]] && continue
    args+=("${{a//\\/var\\/lib\\/bluetooth/{storage}}}")
done
exec "${{args[@]}}"
""",
    )


class TestConselhoDoCacheSdpEnvenenado:
    def test_sem_sdptool_o_doctor_nao_manda_rodar_o_que_nao_existe(
        self, tmp_path: Path, sandbox_sem_velhas: Path
    ) -> None:
        storage = tmp_path / "bluetooth"
        _arvore_bluez_falsa(storage, "AA:BB:CC:00:00:11")
        fakes = tmp_path / "fakes"
        _sudo_fake(fakes, storage)
        saida = _rodar_check(
            "check_bt_sdp_cache_envenenado", fakes, sandbox_sem_velhas
        )
        assert "[FAIL] cache SDP de AA:BB:CC:00:00:11" in saida, saida
        assert "NÃO DÁ para distinguir as duas causas" in saida, (
            "sem `sdptool` não há como perguntar SDP ao controle — o doctor "
            "tem de dizer isso em vez de mandar rodar um comando ausente"
        )
        assert "sdptool browse" not in saida, (
            "mandar rodar uma ferramenta que não está na máquina é conselho morto"
        )

    def test_com_sdptool_o_discriminador_medido_continua_sendo_oferecido(
        self, tmp_path: Path
    ) -> None:
        storage = tmp_path / "bluetooth"
        _arvore_bluez_falsa(storage, "AA:BB:CC:00:00:11")
        fakes = tmp_path / "fakes"
        _sudo_fake(fakes, storage)
        _fake(fakes, "sdptool", "exit 0\n")
        saida = _rodar_check(
            "check_bt_sdp_cache_envenenado", fakes, "/usr/bin", "/bin"
        )
        assert "sdptool browse AA:BB:CC:00:00:11" in saida, saida


class TestVigiaSdpDoWatchdogNaoAfirmaOQueNaoMediu:
    """O `else` da vigia 3 dizia "o device responde ao browse direto" — também
    quando o `sdptool` não existia, ou seja, sem ter perguntado nada."""

    def _rodar_vigia(
        self, tmp_path: Path, *dirs: Path, sdptool: str | None = None
    ) -> str:
        storage = tmp_path / "bluetooth"
        _arvore_bluez_falsa(storage, "AA:BB:CC:00:00:11")
        fakes = tmp_path / "fakes"
        # Connected=true na 1ª pergunta (entra na cura) e false depois: a vigia
        # desiste no 1º tick em vez de gastar 12 s de tentativas.
        contador = tmp_path / "n"
        _fake(
            fakes,
            "busctl",
            f"""
case "$1 $2" in
  "tree org.bluez") echo '/org/bluez/hci0/dev_AA_BB_CC_00_00_11' ;;
  "get-property org.bluez")
    if [[ "$5" == "Connected" ]]; then
        n="$(cat {contador} 2>/dev/null || echo 0)"
        echo $((n + 1)) > {contador}
        if [[ "${{n}}" -eq 0 ]]; then echo 'b true'; else echo 'b false'; fi
    else
        echo ''
    fi ;;
esac
exit 0
""",
        )
        if sdptool is not None:
            _fake(fakes, "sdptool", sdptool)
        log = tmp_path / "vigia.log"
        subprocess.run(
            [BASH, str(WATCHDOG), "--sdp-cache-only"],
            capture_output=True,
            text=True,
            timeout=120,
            check=False,
            env={
                "PATH": ":".join([str(fakes), *(str(d) for d in dirs)]),
                "HOME": str(tmp_path),
                "HEFESTO_BT_SRC": str(storage),
                "HEFESTO_HIDRAW_ROOT": str(tmp_path / "hidraw-vazio"),
                "HEFESTO_BT_STAMP_DIR": str(tmp_path / "stamps"),
                "HEFESTO_BT_LOG_DEST": str(log),
            },
        )
        return log.read_text(encoding="utf-8") if log.exists() else ""

    def test_sem_sdptool_a_vigia_diz_que_nao_sabe(
        self, tmp_path: Path, sandbox_sem_velhas: Path
    ) -> None:
        saida = self._rodar_vigia(tmp_path, sandbox_sem_velhas)
        assert "NÃO SEI dizer qual das duas causas é" in saida, saida
        assert "responde ao browse direto" not in saida, (
            "afirmar que o controle respondeu SEM ter perguntado é o defeito"
        )

    def test_com_sdptool_que_responde_o_veredito_antigo_fica(
        self, tmp_path: Path
    ) -> None:
        saida = self._rodar_vigia(tmp_path, Path("/usr/bin"), Path("/bin"), sdptool="exit 0\n")
        assert "responde ao browse direto" in saida, saida

    def test_com_sdptool_que_estoura_acusa_controle_travado(
        self, tmp_path: Path
    ) -> None:
        saida = self._rodar_vigia(tmp_path, Path("/usr/bin"), Path("/bin"), sdptool="exit 1\n")
        assert "NÃO responde SDP" in saida, saida
        assert "reset de hardware" in saida


# ---------------------------------------------------------------------------
# 5. bt_active_mode.sh — a cura que sumia inteira por causa de uma ferramenta
#    que ela nem usava.
# ---------------------------------------------------------------------------
class TestModoAtivoNaoDesisteInteiro:
    def _rodar(self, tmp_path: Path, *dirs: Path, com_velhas: bool = False) -> str:
        fakes = tmp_path / "fakes"
        _fake(fakes, "id", "echo 0\n")  # o script exige root; aqui ele "é" root
        _busctl_fake(fakes, connected="true")
        if com_velhas:
            _fake(fakes, "hciconfig", "echo 'Link policy: RSWITCH HOLD PARK'\nexit 0\n")
            _fake(fakes, "hcitool", "exit 0\n")
        log = tmp_path / "active.log"
        subprocess.run(
            [BASH, str(ACTIVE_MODE), "--quiet"],
            capture_output=True,
            text=True,
            timeout=60,
            check=False,
            env={
                "PATH": ":".join([str(fakes), *(str(d) for d in dirs)]),
                "HOME": str(tmp_path),
                "HEFESTO_BT_LOG_DEST": str(log),
            },
        )
        return log.read_text(encoding="utf-8") if log.exists() else ""

    def test_sem_hciconfig_o_alias_nintendo_ainda_e_aplicado(
        self, tmp_path: Path, sandbox_sem_velhas: Path
    ) -> None:
        """A medida (1) sai pelo D-Bus e nunca precisou do `hciconfig`.

        O script saía no `command -v hciconfig` da linha 64 — e com isso perdia
        também o alias, que é a metade da cura BT-NINTENDO-ACTIVE-01 que
        funciona sem ferramenta nenhuma do pacote depreciado.
        """
        saida = self._rodar(tmp_path, sandbox_sem_velhas)
        assert "alias do adaptador -> 'Nintendo meowsystem'" in saida, saida
        assert "NÃO apliquei o SNIFF default" in saida, (
            "e o que NÃO foi aplicado tem de aparecer no diário, não sumir"
        )

    def test_com_hciconfig_a_link_policy_continua_sendo_aplicada(
        self, tmp_path: Path
    ) -> None:
        saida = self._rodar(
            tmp_path, Path("/usr/bin"), Path("/bin"), com_velhas=True
        )
        assert "RSWITCH,HOLD,SNIFF,PARK" in saida, saida
        assert f"link policy de {MAC_PRO} -> RSWITCH" in saida, (
            "o no-sniff por-conexão do Pro genuíno não pode ter se perdido"
        )


class TestNoSniffNaBordaNaoSaiCalado:
    def test_sem_hcitool_registra_o_que_deixou_de_fazer(
        self, tmp_path: Path, sandbox_sem_velhas: Path
    ) -> None:
        log = tmp_path / "borda.log"
        subprocess.run(
            [BASH, str(NOSNIFF), MAC_PRO],
            capture_output=True,
            text=True,
            timeout=30,
            check=False,
            env={
                "PATH": str(sandbox_sem_velhas),
                "HOME": str(tmp_path),
                "HEFESTO_BT_LOG_DEST": str(log),
            },
        )
        saida = log.read_text(encoding="utf-8") if log.exists() else ""
        assert "NÃO aplicado" in saida, (
            "era um `exit 0` mudo: o Pro seguia caindo sob carga e nada no "
            "diário dizia por quê"
        )
        assert "bluez-deprecated" in saida


# ---------------------------------------------------------------------------
# 6. kernel-watch: ausência de [BT-ERR] não é rádio limpo.
# ---------------------------------------------------------------------------
class TestKernelWatchSemContador:
    def test_o_hook_emite_a_marca(self, tmp_path: Path) -> None:
        res = subprocess.run(
            [BASH, str(STORM), "--test-bt-sem-contador"],
            capture_output=True,
            text=True,
            timeout=30,
            check=False,
            env={**os.environ, "XDG_STATE_HOME": str(tmp_path)},
        )
        assert "[BT-SEM-CONTADOR]" in res.stdout, res.stdout
        assert "NÃO rádio limpo" in res.stdout

    def test_o_doctor_traduz_a_marca_em_frase(self, tmp_path: Path) -> None:
        estado = tmp_path / ".local" / "state" / "hefesto-dualsense4unix"
        estado.mkdir(parents=True)
        (estado / "kernel.log").write_text(
            "2026-08-19T10:00:00-0300 [BT-SEM-CONTADOR] contadores de erro do "
            "rádio não medidos\n",
            encoding="utf-8",
        )
        saida = _rodar_check(
            "check_kernel_watch", Path("/usr/bin"), Path("/bin"), HOME=str(tmp_path)
        )
        assert "NÃO está medindo os erros do rádio" in saida, saida
        assert "é ausência de medida, não medida de ausência" in saida


# ---------------------------------------------------------------------------
# 7. O instrumento de coexistência declara a régua que perdeu.
# ---------------------------------------------------------------------------
class TestMedirW3DeclaraOBracoPerdido:
    def test_sem_hciconfig_o_plano_avisa_que_nao_mede_contador(
        self, tmp_path: Path, sandbox_sem_velhas: Path
    ) -> None:
        res = subprocess.run(
            [BASH, str(MEDIR_W3)],
            capture_output=True,
            text=True,
            timeout=30,
            check=False,
            env={"PATH": str(sandbox_sem_velhas), "HOME": str(tmp_path)},
        )
        assert "SEM o delta de contadores HCI" in res.stdout, res.stdout
        assert "medida ausente, não rádio limpo" in res.stdout
        assert "DRY-RUN" in res.stdout, "o gate humano continua no lugar"


# ---------------------------------------------------------------------------
# 8. O ensaio do byte no fio: handle -> MAC pelo kernel, e a régua declarada.
# ---------------------------------------------------------------------------
def _carregar_byte_no_fio() -> object:
    """`scripts/ensaios/` não é pacote — carrega pelo caminho, como os irmãos."""
    import importlib.util
    import sys

    caminho = REPO_ROOT / "scripts" / "ensaios" / "byte_no_fio.py"
    pasta = str(caminho.parent)
    if pasta not in sys.path:
        sys.path.insert(0, pasta)
    espec = importlib.util.spec_from_file_location("byte_no_fio_sob_ensaio", caminho)
    assert espec is not None and espec.loader is not None
    modulo = importlib.util.module_from_spec(espec)
    sys.modules[espec.name] = modulo
    espec.loader.exec_module(modulo)
    return modulo


class TestMapaDeHandlesSaiDoKernel:
    """`hcitool con` respondia "que handle ACL é de qual MAC".

    A fonte viva é o próprio kernel: cada conexão ACL vira um device
    `hciN:<handle>` em /sys/class/bluetooth, com o `address` ao lado. O
    `hcitool` fica como plano B, e o relatório DIZ de qual régua o mapa saiu —
    sem isso, um mapa vazio viraria "SEM HANDLE" em todo mundo, sem explicação.
    """

    def test_le_handle_e_mac_do_sysfs(self, tmp_path: Path) -> None:
        modulo = _carregar_byte_no_fio()
        raiz = tmp_path / "bluetooth"
        (raiz / "hci0").mkdir(parents=True)  # o adaptador, que NÃO é conexão
        conn = raiz / "hci0:256"
        conn.mkdir()
        (conn / "address").write_text(MAC_PRO.lower() + "\n", encoding="utf-8")
        assert modulo._handles_do_sysfs(str(raiz)) == {MAC_PRO.lower(): 256}

    def test_sysfs_ausente_nao_estoura(self, tmp_path: Path) -> None:
        modulo = _carregar_byte_no_fio()
        assert modulo._handles_do_sysfs(str(tmp_path / "nao-existe")) == {}

    def test_a_regua_volta_junto_com_o_mapa(self) -> None:
        modulo = _carregar_byte_no_fio()
        mapa, regua = modulo.handles_por_mac()
        assert isinstance(mapa, dict)
        assert regua, "o instrumento tem de declarar de onde tirou o mapa"
