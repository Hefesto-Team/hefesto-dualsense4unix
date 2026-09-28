"""O install diz «reinicie» quando algum passo deixou algo para o boot — B5.

``O-PRODUTO-EM-QUALQUER-MAQUINA-01`` (28/09/2026), a L8 do estudo
``2026-09-27-o-basico-e-os-jogos/03-qualquer-maquina.md`` corrigida pela C18:
«vale no próximo boot» estava escrito em 26 lugares, e o fecho dizia só
«instalado · Abrir · Desinstalar». O ``hid-playstation`` instalado com o de
fábrica carregado NÃO é recarregado (de propósito), e a primeira sessão depois
do install roda sem a guarda do microfone. O comentário do fecho dizia que o
install não tocava no cmdline, e o passo 3e o escreve.

A cura: cada passo que deixa algo para o boot anota
(``anotar_reinicio_pendente``, na ``scripts/lib/camada_de_maquina.sh``), e o
fecho diz «Reinicie o computador» só quando há o que esperar. O doctor faz a
MESMA pergunta (``_modulo_pede_reinicio``): o ``srcversion`` do módulo
carregado difere do arquivo em ``updates/dkms``.

Tudo de mentira: o ``/sys/module``, o ``modinfo``, o ``sudo``, o ``dkms`` e o
``/etc``. Nada lê a máquina de quem roda.

A MORDIDA, feita em 28/09/2026: devolver o fecho fixo de antes (tirar a
chamada ``dizer_o_reinicio_pendente`` do fim do ``install.sh``) faz
``test_o_fecho_do_install_diz_reinicie_com_o_modulo_staged`` reprovar; tirar a
anotação do ``install_dkms_hid_playstation_host`` faz o mesmo.
"""

from __future__ import annotations

import shutil
import subprocess
from pathlib import Path

import pytest

BASH = shutil.which("bash") or "/bin/bash"
RAIZ = Path(__file__).resolve().parents[2]
CAMADA = (RAIZ / "scripts" / "lib" / "camada_de_maquina.sh").read_text(encoding="utf-8")
DOCTOR = RAIZ / "scripts" / "doctor.sh"
INSTALL = (RAIZ / "install.sh").read_text(encoding="utf-8")
VELHO = "CFB81A3D4C7FAA41489CCBD"
NOVO = "F66BB33D24119CFDECD2834"


def _modinfo(pasta: Path, *, arquivo: str, srcversion: str) -> None:
    """`modinfo -F filename|srcversion <m>` de mentira, com o que o real publica."""
    pasta.mkdir(parents=True, exist_ok=True)
    stub = pasta / "modinfo"
    stub.write_text(
        "#!/bin/sh\n"
        'campo=""\n'
        'while [ "$#" -gt 0 ]; do case "$1" in -F) campo="$2"; shift 2;; -k) shift 2;; '
        "*) shift;; esac; done\n"
        f'[ "$campo" = filename ] && echo "{arquivo}"\n'
        f'[ "$campo" = srcversion ] && echo "{srcversion}"\n'
        "exit 0\n",
        encoding="utf-8",
    )
    stub.chmod(0o755)


def _sys_module(tmp_path: Path, carregado: str | None) -> Path:
    raiz = tmp_path / "sys-module"
    raiz.mkdir()
    if carregado is not None:
        (raiz / "hid_playstation").mkdir()
        # "" = carregado SEM `srcversion` (módulo embutido, ou um kernel sem
        # `CONFIG_MODULE_SRCVERSION_ALL`): a pasta existe e o arquivo não.
        if carregado:
            (raiz / "hid_playstation" / "srcversion").write_text(
                carregado + "\n", encoding="ascii"
            )
    return raiz


_CASOS = [
    # (carregado, arquivo que o próximo carregamento usa, srcversion dele, pede?)
    (VELHO, "/lib/modules/k/updates/dkms/hid-playstation.ko.zst", NOVO, True),
    (NOVO, "/lib/modules/k/updates/dkms/hid-playstation.ko.zst", NOVO, False),
    (None, "/lib/modules/k/updates/dkms/hid-playstation.ko.zst", NOVO, False),
    (VELHO, "/lib/modules/k/kernel/drivers/hid/hid-playstation.ko.zst", NOVO, False),
    # Sem um dos dois `srcversion` não há o que comparar, e não sei não é
    # «reinicie» (a conferência de 28/09/2026: aqui o install e o doctor
    # divergiam, e esta lista não tinha o caso).
    ("", "/lib/modules/k/updates/dkms/hid-playstation.ko.zst", NOVO, False),
    (VELHO, "/lib/modules/k/updates/dkms/hid-playstation.ko.zst", "", False),
]


@pytest.mark.parametrize(("carregado", "arquivo", "novo", "pede"), _CASOS)
def test_o_install_e_o_doctor_respondem_a_mesma_pergunta(
    tmp_path: Path, carregado: str | None, arquivo: str, novo: str, pede: bool
) -> None:
    raiz = _sys_module(tmp_path, carregado)
    _modinfo(tmp_path / "bin", arquivo=arquivo, srcversion=novo)
    env = {
        "PATH": f"{tmp_path / 'bin'}:/usr/bin:/bin",
        "HOME": str(tmp_path),
        "HEFESTO_SYS_MODULE": str(raiz),
        "HEFESTO_DOCTOR_SYS_MODULE": str(raiz),
    }
    pergunta = 'if {f} hid-playstation; then echo pede; else echo nao-pede; fi'
    install = subprocess.run(
        [BASH, "-c", f"ROOT_DIR='{RAIZ}'\nsource /dev/stdin\n"
         + pergunta.format(f="modulo_pede_reinicio")],
        input=CAMADA, capture_output=True, text=True, timeout=60, check=False, env=env,
    )
    doctor = subprocess.run(
        [BASH, "-c", f"source '{DOCTOR}'\n" + pergunta.format(f="_modulo_pede_reinicio")],
        capture_output=True, text=True, timeout=60, check=False, env=env,
    )
    esperado = "pede" if pede else "nao-pede"
    assert install.stdout.strip() == esperado, (install.stdout, install.stderr)
    assert doctor.stdout.strip() == esperado, (doctor.stdout, doctor.stderr)


def _fecho_do_install() -> str:
    """O fim do `install.sh`, do quirk do microfone até a última linha."""
    return INSTALL[INSTALL.index("# BUG-MIC-ON-SEM-QUIRK-REABRE-STORM-01"):]


def _rodar_o_passo_e_o_fecho(tmp_path: Path, carregado: str | None) -> str:
    """O passo 3k de verdade (a função da lib) e o fecho de verdade do install.

    O `/sys/module/` e o `/etc/` do texto da lib apontam para o `tmp_path`, o
    `dkms_lib.sh` é um de mentira (o DKMS já «instalou»), e o `sudo` só anota.
    """
    raiz = tmp_path / "raiz"
    (raiz / "scripts").mkdir(parents=True)
    (raiz / "assets" / "modprobe.d").mkdir(parents=True)
    shutil.copy(
        RAIZ / "assets" / "modprobe.d" / "hefesto-hid-playstation.conf",
        raiz / "assets" / "modprobe.d",
    )
    (raiz / "scripts" / "dkms_lib.sh").write_text(
        "dkms_warn_secureboot_once() { :; }\n"
        "dkms_pkg_version() { echo 1.0.0; }\n"
        "dkms_install_patched_module() { :; }\n"
        "dkms_module_from_updates() { return 0; }\n",
        encoding="utf-8",
    )
    sys_module = _sys_module(tmp_path, carregado)
    bin_ = tmp_path / "bin"
    _modinfo(bin_, arquivo="/lib/modules/k/updates/dkms/hid-playstation.ko.zst", srcversion=NOVO)
    (bin_ / "sudo").write_text(f'#!/bin/sh\necho "sudo $*" >> "{tmp_path}/sudo.log"\nexit 0\n')
    (bin_ / "sudo").chmod(0o755)
    (bin_ / "getent").write_text("#!/bin/sh\nexit 2\n")
    (bin_ / "getent").chmod(0o755)
    lib = tmp_path / "camada.sh"
    lib.write_text(
        CAMADA.replace("/sys/module/", f"{sys_module}/").replace("/etc/", f"{tmp_path}/etc/"),
        encoding="utf-8",
    )
    fecho = (
        _fecho_do_install()
        .replace("/proc/cmdline", f"{tmp_path}/cmdline")
        .replace("/sys/module/", f"{sys_module}/")
        .replace("/etc/", f"{tmp_path}/etc/")
    )
    (tmp_path / "cmdline").write_text("quiet usbcore.quirks=054c:0ce6:gn\n", encoding="ascii")
    script = "\n".join(
        (
            "set -euo pipefail",
            f"ROOT_DIR='{raiz}'",
            "NO_DKMS=0",
            'warn() { printf "WARN: %s\\n" "$*"; }',
            f"source '{lib}'",
            "install_dkms_hid_playstation_host",
            fecho,
        )
    )
    r = subprocess.run(
        [BASH, "-c", script], capture_output=True, text=True, timeout=60, check=False,
        env={
            "PATH": f"{bin_}:/usr/bin:/bin",
            "HOME": str(tmp_path),
            "USER": "jogadora",
            "LC_ALL": "C.UTF-8",
            "HEFESTO_SYS_MODULE": str(sys_module),
        },
    )
    assert r.returncode == 0, r.stderr
    return r.stdout


def test_o_fecho_do_install_diz_reinicie_com_o_modulo_staged(tmp_path: Path) -> None:
    """O patchado novo instalado, o velho carregado: «Reinicie», com o driver nomeado."""
    saida = _rodar_o_passo_e_o_fecho(tmp_path, carregado=VELHO)
    assert "Reinicie o computador" in saida, saida
    assert "o driver do DualSense (hid-playstation)" in saida, saida


def test_o_fecho_calado_quando_nada_espera_o_boot(tmp_path: Path) -> None:
    saida = _rodar_o_passo_e_o_fecho(tmp_path, carregado=NOVO)
    assert "Reinicie" not in saida, saida


def test_o_cmdline_escrito_e_o_quirk_agendado_entram_no_reinicie() -> None:
    """O 3e anota o cmdline que escreveu; o fecho anota o quirk agendado."""
    passo_3e = INSTALL[INSTALL.index('step "3e" '):INSTALL.index('step "3e-trava"')]
    assert 'anotar_reinicio_pendente "${_PENDENTE_DO_CMDLINE}"' in passo_3e
    assert 'anotar_reinicio_pendente "${_PENDENTE_DO_CMDLINE}"' in _fecho_do_install()


def test_o_comentario_velho_do_cmdline_saiu() -> None:
    """Fato errado se substitui: o 3e escreve o cmdline."""
    assert "NÃO aplicamos nem tocamos no cmdline" not in INSTALL
    assert "gerido pela toolchain pessoal" not in INSTALL


def test_os_dois_fechos_dizem_o_reinicio() -> None:
    """O nativo e o dos formatos de pacote: os módulos de kernel são os mesmos."""
    assert INSTALL.count("\ndizer_o_reinicio_pendente\n") == 1
    assert INSTALL.count("\n    dizer_o_reinicio_pendente\n") == 1


def _o_grupo(tmp_path: Path, grupos_da_sessao: str) -> str:
    """`dizer_o_reinicio_pendente` com o grupo `hefesto` recém-ganho (ou não)."""
    bin_ = tmp_path / "bin-grupo"
    bin_.mkdir()
    (bin_ / "getent").write_text(
        "#!/bin/sh\necho 'hefesto:x:990:outra,jogadora'\n", encoding="utf-8"
    )
    (bin_ / "id").write_text(
        f'#!/bin/sh\ncase "$1" in -nG) echo "{grupos_da_sessao}";; *) echo jogadora;; esac\n',
        encoding="utf-8",
    )
    for nome in ("getent", "id"):
        (bin_ / nome).chmod(0o755)
    r = subprocess.run(
        [BASH, "-c", f"ROOT_DIR='{RAIZ}'\nsource /dev/stdin\ndizer_o_reinicio_pendente"],
        input=CAMADA, capture_output=True, text=True, timeout=60, check=False,
        env={"PATH": f"{bin_}:/usr/bin:/bin", "HOME": str(tmp_path), "USER": "jogadora"},
    )
    assert r.returncode == 0, r.stderr
    return r.stdout


def test_o_grupo_ganho_agora_entra_no_reinicie(tmp_path: Path) -> None:
    """A conferência de 28/09/2026: o grupo `hefesto` entrou no fecho sem régua.

    A MORDIDA: tirar o `grupo_pede_novo_login` do `dizer_o_reinicio_pendente`
    faz este teste reprovar.
    """
    saida = _o_grupo(tmp_path, "jogadora adm")
    assert "Reinicie o computador" in saida and "o grupo hefesto" in saida, saida


def test_o_grupo_que_a_sessao_ja_tem_nao_pede_nada(tmp_path: Path) -> None:
    assert _o_grupo(tmp_path, "jogadora adm hefesto") == ""
