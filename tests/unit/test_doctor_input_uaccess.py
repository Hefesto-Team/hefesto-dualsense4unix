"""OQ-6 — o doctor tem de saber dizer que o touchpad e o giroscópio não têm acesso.

A cura da OQ-6 é a regra `assets/72-hefesto-touchpad-motion-uaccess.rules`, que
dá ACL da sessão aos nós de ENTRADA do touchpad e dos sensores de movimento. A
regra do SISTEMA (`/usr/lib/udev/rules.d/70-uaccess.rules`) só marca
`ID_INPUT_JOYSTICK`, e o `input_id` do kernel classifica esses dois nós como
`ID_INPUT_TOUCHPAD` e `ID_INPUT_ACCELEROMETER` — nenhum dos dois casava.

Este módulo trava o INSTRUMENTO, não a cura: `check_input_uaccess` no
`scripts/doctor.sh`. Ele existe porque o sintoma da falta de permissão é a
AUSÊNCIA de dado — `core/evdev_reader.py:1396` engole a `PermissionError` num
`except Exception: continue`, o nó some do mapa de descoberta e o daemon relata
"esse controle não tem sensor". Sem alguém que confira a permissão e diga o
nome dela, o defeito é indistinguível de hardware sem sensor.

O QUE ESTES TESTES TRAVAM, e por quê:

- **arquivo no disco ≠ regra valendo.** Uma regra udev só age no (re)add do
  device: um controle já conectado quando a regra chegou continua sem ACL. Por
  isso o check do EFEITO é separado do check de PRESENÇA (`check_udev`);
- **ACL da sessão ≠ grupo do nó.** Os dois deixam o nó legível, e só o primeiro
  existe numa máquina limpa. A usuária desta máquina está no grupo `input` POR
  FORA do produto (`id` devolve `995(input)`), e foi esse acidente que escondeu
  a OQ-6 por meses. Legível só pelo grupo é WARN, nunca PASS;
- **o VPAD não pode responder pelo controle FÍSICO.** Este é o dente principal,
  e nasceu de um FALSO VERDE MEDIDO em 09/08/2026: a primeira versão da função
  imprimiu `[PASS] ... em 2 nó(s)` nesta máquina, e os dois nós eram
  `event259`/`event261`, ambos em
  `/sys/devices/virtual/misc/uhid/0003:054C:0DF2.008F` — o gamepad virtual que
  o próprio daemon acabara de criar. Não havia DualSense físico conectado. O
  instrumento deu verde sobre um device que nós mesmos fabricamos, calado sobre
  o que a pergunta era. `check_led_sysfs_gravavel` já resolvia isso com
  `[[ "${dev_real}" == */devices/virtual/* ]] && continue`;
- **escopo estreito.** O casamento é por fabricante (`054c` Sony / `057e`
  Nintendo) MAIS sufixo de nome, igual ao da regra. Sem a âncora de fabricante,
  o touchpad de um notebook — que a regra nunca cobre — viraria alarme;
- **confere e não cura.** A função nomeia o comando e nunca o executa: nada de
  `udevadm control`, `setfacl`, `chmod` ou `usermod`.

As cenas rodam em bash contra um `/dev`, `/sys` e `/etc` de MENTIRA, com
`getfacl` de mentira — sem hardware, sem root e sem tocar a máquina.
"""

from __future__ import annotations

import os
import re
import shutil
import subprocess
from pathlib import Path

import pytest

BASH = shutil.which("bash") or "/bin/bash"
REPO_ROOT = Path(__file__).resolve().parents[2]
DOCTOR_PATH = REPO_ROOT / "scripts" / "doctor.sh"
REGRA_NOME = "72-hefesto-touchpad-motion-uaccess.rules"
REGRA_PATH = REPO_ROOT / "assets" / REGRA_NOME

DOCTOR = DOCTOR_PATH.read_text(encoding="utf-8") if DOCTOR_PATH.exists() else ""

pytestmark = pytest.mark.skipif(not DOCTOR, reason="scripts/doctor.sh ausente")


def _extrai_funcao_bash(fonte: str, nome: str) -> str:
    match = re.search(rf"^{re.escape(nome)}\(\) \{{\n", fonte, re.MULTILINE)
    assert match is not None, f"função {nome}() não encontrada"
    fim = re.search(r"^\}$", fonte[match.end() :], re.MULTILINE)
    assert fim is not None, f"fim de {nome}() não encontrado"
    return fonte[match.start() : match.end() + fim.end() + 1]


def _sem_comentarios(texto: str) -> str:
    linhas = [re.sub(r"(^|\s)#.*$", r"\1", linha) for linha in texto.splitlines()]
    return "\n".join(linhas)


# ---------------------------------------------------------------------------
# A cena: /dev, /sys e /etc de mentira
# ---------------------------------------------------------------------------
#: Os nós que a função tem de enxergar, e os que tem de ignorar. O `nome` é o
#: que o kernel `hid_playstation`/`hid-nintendo` publica em
#: /sys/class/input/<base>/device/name.
FISICO = "/sys/devices/pci0000:00/0000:00:14.0/usb3/3-3/3-3:1.0/0003:054C:0CE6.0042"
VIRTUAL = "/sys/devices/virtual/misc/uhid/0003:054C:0DF2.008F"


def _monta_cena(
    raiz: Path,
    nos: list[tuple[str, str, str, str, int]],
    *,
    com_regra: bool = True,
    com_acl: tuple[str, ...] = (),
) -> dict[str, str]:
    """Monta a árvore falsa.

    ``nos`` é uma lista de ``(base, vendor, nome, pai_sysfs, modo)`` —
    ``pai_sysfs`` decide se o nó é FÍSICO ou VIRTUAL, e ``modo`` é o modo do
    arquivo em ``/dev/input`` (0 = ilegível).
    """
    (raiz / "dev" / "input").mkdir(parents=True, exist_ok=True)
    (raiz / "sys" / "class" / "input").mkdir(parents=True, exist_ok=True)
    if com_regra:
        alvo = raiz / "etc" / "udev" / "rules.d" / REGRA_NOME
        alvo.parent.mkdir(parents=True, exist_ok=True)
        alvo.write_text("# fake\n", encoding="utf-8")
    for base, vendor, nome, pai, modo in nos:
        dev_dir = raiz / (pai.lstrip("/")) / "input" / f"input-{base}"
        dev_dir.mkdir(parents=True, exist_ok=True)
        (dev_dir / "id").mkdir(exist_ok=True)
        (dev_dir / "id" / "vendor").write_text(f"{vendor}\n", encoding="utf-8")
        (dev_dir / "name").write_text(f"{nome}\n", encoding="utf-8")
        classe = raiz / "sys" / "class" / "input" / base
        classe.mkdir(parents=True, exist_ok=True)
        enlace = classe / "device"
        if not enlace.exists():
            enlace.symlink_to(dev_dir)
        no = raiz / "dev" / "input" / base
        no.write_text("", encoding="utf-8")
        no.chmod(modo)
    return {"COM_ACL": " ".join(com_acl)}


def _stub_getfacl(raiz: Path) -> Path:
    """`getfacl` de mentira: só diz `user:<eu>:` para quem está em COM_ACL.

    É o coração da distinção que a função faz — ACL da sessão (a cura) versus
    grupo do nó (o acidente desta máquina). Com o getfacl real não haveria como
    encenar as duas, porque a árvore falsa não tem ACL nenhuma.
    """
    binario = raiz / "bin"
    binario.mkdir(parents=True, exist_ok=True)
    stub = binario / "getfacl"
    stub.write_text(
        "#!/bin/sh\n"
        'alvo=""\n'
        'for a in "$@"; do alvo="$a"; done\n'
        'base=$(basename "$alvo")\n'
        'echo "# file: $base"\n'
        "echo 'user::rw-'\n"
        'case " $COM_ACL " in\n'
        '  *" $base "*) echo "user:$(id -un):rw-" ;;\n'
        "esac\n"
        "echo 'group::rw-'\n"
        "echo 'other::---'\n",
        encoding="utf-8",
    )
    stub.chmod(0o755)
    return binario


def _roda(raiz: Path, env_extra: dict[str, str]) -> subprocess.CompletedProcess[str]:
    """Extrai a função do doctor, reancora os caminhos na cena e roda."""
    corpo = _extrai_funcao_bash(DOCTOR, "check_input_uaccess")
    for real in (
        "/dev/input/",
        "/sys/class/input/",
        "/etc/udev/rules.d/",
        "/usr/lib/udev/rules.d/",
    ):
        corpo = corpo.replace(real, f"{raiz}{real}")
    script = raiz / "cena.sh"
    script.write_text(
        "pass() { echo \"[PASS] $*\"; }\n"
        "warn() { echo \"[WARN] $*\"; }\n"
        "fail() { echo \"[FAIL] $*\"; }\n"
        "info() { echo \"[INFO] $*\"; }\n" + corpo + "\ncheck_input_uaccess\n",
        encoding="utf-8",
    )
    env = dict(os.environ)
    env["PATH"] = f"{_stub_getfacl(raiz)}{os.pathsep}{env['PATH']}"
    env.update(env_extra)
    return subprocess.run(
        [BASH, str(script)], capture_output=True, text=True, check=False, env=env
    )


#: A cena SÃ: os dois nós auxiliares do controle FÍSICO, com ACL da sessão.
_SAUDAVEL = [
    ("event7", "054c", "DualSense Wireless Controller Motion Sensors", FISICO, 0o660),
    ("event8", "054c", "DualSense Wireless Controller Touchpad", FISICO, 0o660),
]


class TestOInstrumentoAcusa:
    def test_com_acl_da_sessao_e_pass(self, tmp_path: Path) -> None:
        env = _monta_cena(tmp_path, _SAUDAVEL, com_acl=("event7", "event8"))
        r = _roda(tmp_path, env)
        assert "[PASS]" in r.stdout, r.stdout
        assert "físico" in r.stdout

    def test_sem_a_regra_no_disco_e_fail(self, tmp_path: Path) -> None:
        """Sem a regra, o acesso só existe para quem está no grupo `input`."""
        env = _monta_cena(
            tmp_path, _SAUDAVEL, com_regra=False, com_acl=("event7", "event8")
        )
        r = _roda(tmp_path, env)
        assert "[FAIL]" in r.stdout, r.stdout
        assert REGRA_NOME in r.stdout
        assert "install_udev.sh" in r.stdout, "o FAIL tem de nomear a cura"

    def test_no_ilegivel_e_fail_e_nomeia_o_no(self, tmp_path: Path) -> None:
        """É o estado de uma máquina limpa antes da regra: `0660 root:input`."""
        cena = [
            (base, vid, nome, pai, 0o000)
            for (base, vid, nome, pai, _modo) in _SAUDAVEL
        ]
        env = _monta_cena(tmp_path, cena)
        r = _roda(tmp_path, env)
        assert "[FAIL]" in r.stdout, r.stdout
        assert "event7" in r.stdout and "event8" in r.stdout
        # A dica certa vem primeiro: a ACL nasce no (re)add do device.
        assert "reconecte" in r.stdout.lower()

    def test_legivel_so_pelo_grupo_e_warn_nunca_pass(self, tmp_path: Path) -> None:
        """O ACIDENTE desta máquina, dito com todas as letras.

        Legível sem ACL da sessão = legível pelo grupo `input`, em que a
        usuária está por fora do produto. Funciona aqui e não funciona numa
        máquina limpa — e um PASS aqui teria mantido a OQ-6 invisível.
        """
        env = _monta_cena(tmp_path, _SAUDAVEL, com_acl=())
        r = _roda(tmp_path, env)
        assert "[WARN]" in r.stdout, r.stdout
        assert "[PASS]" not in r.stdout
        assert "grupo" in r.stdout.lower()
        assert "limpa" in r.stdout.lower()

    def test_meia_cura_tambem_acusa(self, tmp_path: Path) -> None:
        """Um nó com ACL e o outro sem continua sendo defeito."""
        env = _monta_cena(tmp_path, _SAUDAVEL, com_acl=("event7",))
        r = _roda(tmp_path, env)
        assert "[WARN]" in r.stdout, r.stdout
        assert "event8" in r.stdout


class TestOVpadNaoRespondePeloFisico:
    """O dente principal — o falso verde medido em 09/08/2026."""

    def test_so_o_vpad_presente_nao_da_pass(self, tmp_path: Path) -> None:
        cena = [
            (
                "event259",
                "054c",
                "DualSense Wireless Controller (Hefesto P1) Motion Sensors",
                VIRTUAL,
                0o660,
            ),
            (
                "event261",
                "054c",
                "DualSense Wireless Controller (Hefesto P1) Touchpad",
                VIRTUAL,
                0o660,
            ),
        ]
        env = _monta_cena(tmp_path, cena, com_acl=("event259", "event261"))
        r = _roda(tmp_path, env)
        assert "[PASS]" not in r.stdout, (
            "verde sobre o gamepad que NÓS criamos, calado sobre o controle "
            "dela — foi exatamente o que a primeira versão fez nesta máquina"
        )
        assert "[INFO]" in r.stdout
        assert "virtual" in r.stdout.lower()

    def test_o_fisico_ruim_nao_e_salvo_pelo_vpad_bom(self, tmp_path: Path) -> None:
        """Com os dois presentes, quem manda no veredito é o FÍSICO."""
        cena = [
            *_SAUDAVEL,
            (
                "event259",
                "054c",
                "DualSense Wireless Controller (Hefesto P1) Motion Sensors",
                VIRTUAL,
                0o660,
            ),
        ]
        env = _monta_cena(tmp_path, cena, com_acl=("event259",))
        r = _roda(tmp_path, env)
        assert "[PASS]" not in r.stdout, r.stdout
        assert "event7" in r.stdout or "event8" in r.stdout

    def test_vpad_sem_acesso_e_fail_proprio(self, tmp_path: Path) -> None:
        """Sem ACL no vpad o JOGO não lê giroscópio nem touchpad na máscara PS.

        É defeito de outra natureza (afeta o jogo, não a interface), e por isso
        tem mensagem própria em vez de sumir dentro da contagem do físico.
        """
        cena = [
            *_SAUDAVEL,
            (
                "event261",
                "054c",
                "DualSense Wireless Controller (Hefesto P1) Touchpad",
                VIRTUAL,
                0o000,
            ),
        ]
        env = _monta_cena(tmp_path, cena, com_acl=("event7", "event8"))
        r = _roda(tmp_path, env)
        assert "[FAIL]" in r.stdout, r.stdout
        assert "VIRTUAL" in r.stdout
        assert "event261" in r.stdout


class TestOEscopoEEstreito:
    def test_touchpad_de_notebook_nao_vira_alarme(self, tmp_path: Path) -> None:
        """Sem a âncora de fabricante, o instrumento inventaria defeito.

        A regra casa `ATTRS{id/vendor}=="054c"` — um touchpad Synaptics jamais
        ganha ACL por ela, então cobrá-la nele seria alarme falso garantido.
        """
        cena = [
            ("event3", "06cb", "SynPS/2 Synaptics TouchPad", FISICO, 0o000),
        ]
        env = _monta_cena(tmp_path, cena)
        r = _roda(tmp_path, env)
        assert "[FAIL]" not in r.stdout, r.stdout
        assert "[INFO]" in r.stdout

    def test_o_gamepad_principal_nao_entra(self, tmp_path: Path) -> None:
        """O nó do gamepad já é coberto pela 70-uaccess do sistema.

        Ele casa `ID_INPUT_JOYSTICK`, nunca esteve quebrado, e não é assunto
        desta regra — incluí-lo confundiria o diagnóstico.
        """
        cena = [("event6", "054c", "DualSense Wireless Controller", FISICO, 0o000)]
        env = _monta_cena(tmp_path, cena)
        r = _roda(tmp_path, env)
        assert "[FAIL]" not in r.stdout, r.stdout

    def test_a_imu_do_nintendo_entra(self, tmp_path: Path) -> None:
        """O `hid-nintendo` publica a IMU num nó "<nome> (IMU)" — mesma lacuna."""
        cena = [("event9", "057e", "Nintendo Switch Pro Controller (IMU)", FISICO, 0o000)]
        env = _monta_cena(tmp_path, cena)
        r = _roda(tmp_path, env)
        assert "[FAIL]" in r.stdout, r.stdout
        assert "event9" in r.stdout


class TestContratoComORestoDaCasa:
    def test_bash_n_doctor(self) -> None:
        r = subprocess.run(
            ["bash", "-n", str(DOCTOR_PATH)], capture_output=True, text=True, check=False
        )
        assert r.returncode == 0, r.stderr

    def test_definida_e_chamada_no_main(self) -> None:
        assert "check_input_uaccess()" in DOCTOR
        assert re.search(r"^\s*check_input_uaccess\s*$", DOCTOR, re.MULTILINE), (
            "o check precisa ser CHAMADO no fluxo principal, não só definido"
        )

    def test_roda_junto_do_irmao_que_confere_a_outra_regra(self) -> None:
        """A 77 (nó de LED gravável) e esta fazem a MESMA pergunta.

        "A regra desta casa chegou a valer no nó vivo?" — uma para o LED, outra
        para os nós de entrada. Andam juntas para que o diagnóstico de
        permissão saia num bloco só.
        """
        assert re.search(
            r"^\s*check_led_sysfs_gravavel\n(\s*#.*\n)*\s*check_input_uaccess\s*$",
            DOCTOR,
            re.MULTILINE,
        ), "check_input_uaccess vem logo depois de check_led_sysfs_gravavel"

    def test_a_regra_entrou_na_lista_canonica_do_check_udev(self) -> None:
        """`check_udev` confere PRESENÇA; `check_input_uaccess` confere EFEITO.

        As duas são necessárias: a regra pode estar no disco sem ter pegado
        (udev só age no re-add do device). Faltar na lista canônica faria o
        doctor dar [OK] para quem instalou antes de a regra existir — o mesmo
        falso-negativo permanente que a nota de 06/08 já pagou com as 82/83/84.
        """
        corpo = _extrai_funcao_bash(DOCTOR, "check_udev")
        assert REGRA_NOME in corpo, (
            f"{REGRA_NOME} fora da lista canônica de check_udev — quem instalou "
            "antes dela fica sem, em silêncio, e o doctor diz [OK]"
        )

    def test_a_cura_apontada_existe_de_verdade(self) -> None:
        """Mensagem que manda instalar regra inexistente é pior que silêncio."""
        assert REGRA_PATH.exists(), f"a regra apontada tem de existir: {REGRA_PATH}"

    def test_confere_e_nao_cura(self) -> None:
        """Regra da casa: o doctor aponta o comando e nunca o executa."""
        corpo = _sem_comentarios(_extrai_funcao_bash(DOCTOR, "check_input_uaccess"))
        for linha in corpo.splitlines():
            nu = linha.strip()
            assert not re.match(r"^(sudo\s+)?udevadm\b", nu), (
                f"recarregar/disparar udev é cura, não diagnóstico: {nu}"
            )
            assert not re.match(r"^(sudo\s+)?(setfacl|chmod|chown|usermod|gpasswd)\b", nu), (
                f"o doctor não altera permissão nem grupo: {nu}"
            )
        assert "install_udev.sh" in corpo, "as mensagens têm de nomear a cura"

    def test_nunca_sugere_o_grupo_input_como_solucao(self) -> None:
        """Item 3.3 de `docs/history/RESPOSTAS_V1.md`: grupo `input` jamais.

        Membro de `input` lê TODOS os `/dev/input/event*` da máquina, o teclado
        dela inclusive — primitiva de keylogger para resolver um problema de
        touchpad de controle. O doctor citar o grupo como DIAGNÓSTICO é
        correto; sugeri-lo como CURA seria ensinar o defeito.
        """
        corpo = _extrai_funcao_bash(DOCTOR, "check_input_uaccess")
        assert not re.search(r"usermod\s+-aG?\s+\w*input", corpo), (
            "o doctor não pode ensinar a entrar no grupo input"
        )
        assert "adduser" not in corpo
