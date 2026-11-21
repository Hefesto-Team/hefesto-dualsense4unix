"""A chave privada do DKMS vale em todo caminho que constrói, e o módulo de outra chave se refaz.

Com o Secure Boot ligado e a chave pública inscrita na MOK, o ``dkms build`` do DKMS 3 (desde a
3.0.4) gera um par NOVO por cima da pública quando falta a chave privada ou o certificado, e assina
com uma chave fora da MOK: o kernel recusa o módulo no boot e o de ``updates/`` não cai para o de
fábrica. Por isso a pergunta «a chave privada existe para assinar?» vale em todo caminho que
constrói: o ``dkms_install_patched_module`` (os cinco passos do install e o doctor), o gancho
``--exclusivo`` do DKMS (o ``autoinstall`` do kernel novo) e o atualizador do root.

Tudo de mentira: ``dkms``, ``mokutil``, ``modinfo``, ``sudo`` e ``uname`` no ``PATH`` do teste, e
raízes de mentira para ``/var/lib/dkms``, as efivars, o ``/sys/module`` e o ``/boot``. A chave de
teste é gerada no próprio teste.
"""

from __future__ import annotations

import os
import shutil
import subprocess
from pathlib import Path

import pytest

from tests.unit.test_dkms_lib import (
    CINCO_PREPARADORES,
    CONFIG_QUE_ASSINA,
    CONFIG_QUE_NAO_ASSINA,
    PREPARADOR,
    _estado_do_secure_boot,
    _roda,
    _sem_mokutil,
    _stub,
)

KERNEL = "7.1.5-generic"
PROIBIDOS = ("dkms add", "dkms build", "dkms install", "dkms remove")


def _instalar(
    tmp_path: Path,
    estado: dict[str, str],
    *,
    vezes: int = 1,
    framework: str | None = None,
    extra: dict[str, str] | None = None,
    config: str | None = None,
    dubles: dict[str, str] | None = None,
) -> tuple[str, str]:
    """Roda o ``dkms_install_patched_module`` num módulo ainda não construído, com o fonte
    instalado diferente do novo: sem a guarda, o ``dkms remove --all`` tiraria o que estava."""
    bin_ = tmp_path / "bin"
    bin_.mkdir()
    chamadas = tmp_path / "chamadas.log"
    for nome in ("chown", "chmod", "depmod"):
        _stub(bin_, nome, f'echo "{nome} $*" >> "{chamadas}"')
    _stub(bin_, "sudo", f'echo "sudo $*" >> "{chamadas}"\n[ "$1" = -n ] && shift\nexec "$@"')
    _stub(bin_, "dkms", f'echo "dkms $*" >> "{chamadas}"\nexit 0')
    _stub(bin_, "modinfo", 'echo "/nao-existe/hid-teste.ko"')
    _stub(bin_, "uname", f'echo "{KERNEL}"')
    _stub(bin_, "mokutil", "exit 1")
    for nome, corpo in (dubles or {}).items():
        _stub(bin_, nome, corpo)
    modulos = tmp_path / "modules"
    (modulos / KERNEL / "build").mkdir(parents=True)
    if config is not None:
        (modulos / KERNEL / "build" / ".config").write_text(config, encoding="utf-8")
    fonte = tmp_path / "fonte"
    instalado = tmp_path / "usr-src" / "hefesto-teste-9.9.9"
    for pasta, versao in ((fonte, "novo"), (instalado, "velho")):
        pasta.mkdir(parents=True)
        (pasta / "dkms.conf").write_text('PACKAGE_VERSION="9.9.9"\n', encoding="utf-8")
        (pasta / "fonte.c").write_text(f"// {versao}\n", encoding="utf-8")
    ambiente = {
        "HEFESTO_DKMS_SRC_ROOT": str(tmp_path / "usr-src"),
        "HEFESTO_DKMS_MODULES_ROOT": str(modulos),
        "HEFESTO_DKMS_TREE": str(tmp_path / "arvore"),
        "HEFESTO_DKMS_KERNEL": KERNEL,
        "HEFESTO_DKMS_BOOT_ROOT": str(tmp_path / "boot-de-mentira"),
        **estado,
        **({"HEFESTO_DKMS_FRAMEWORK_CONFS": framework} if framework else {}),
        **(extra or {}),
    }
    chamada = f"dkms_install_patched_module hefesto-teste 9.9.9 '{fonte}' hid-teste\n"
    feito = _roda(chamada * vezes, f"{bin_}:/usr/bin:/bin", ambiente)
    assert feito.returncode == 0, feito.stderr
    lidas = chamadas.read_text(encoding="utf-8") if chamadas.exists() else ""
    return feito.stdout + feito.stderr, lidas


def _com_sudo_de_mentira(tmp_path: Path, caminho: str) -> str:
    """O ``PATH`` com um ``sudo`` que só anota e executa: o da máquina nunca roda."""
    pasta = tmp_path / "sudo-de-mentira"
    pasta.mkdir(exist_ok=True)
    _stub(pasta, "sudo", f'echo "sudo $*" >> "{tmp_path / "sudo.log"}"\nexec "$@"')
    return f"{pasta}:{caminho}"


def _sem_kernel_da_maquina(tmp_path: Path) -> dict[str, str]:
    """Raízes de mentira para o ``.config`` do kernel: a pergunta nunca lê o kernel que roda."""
    return {"HEFESTO_DKMS_MODULES_ROOT": str(tmp_path / "sem-modules"),
            "HEFESTO_DKMS_BOOT_ROOT": str(tmp_path / "sem-boot"), "HEFESTO_DKMS_KERNEL": KERNEL}


def _framework(tmp_path: Path, chave: str) -> str:
    conf = tmp_path / "framework-da-chave-privada.conf"
    conf.write_text(f'mok_signing_key="{chave}"\n', encoding="utf-8")
    return str(conf)


class TestSemAChavePrivadaNadaSeConstroi:
    """O-A-CHAVE-PRIVADA-DO-DKMS-VALE-EM-TODO-CAMINHO-QUE-CONSTROI-01.

    D-2111-SEM-A-CHAVE-PRIVADA-O-DKMS-NAO-CONSTROI: com o Secure Boot ligado e a chave inscrita,
    sem a chave privada para assinar nenhum caminho constrói, instala ou tira módulo.
    """

    def test_sem_a_privada_nada_se_constroi_nada_se_tira_e_o_aviso_sai_uma_vez(
        self, tmp_path: Path
    ) -> None:
        """D-2111-SEM-A-CHAVE-PRIVADA-O-DKMS-NAO-CONSTROI."""
        estado = _estado_do_secure_boot(
            tmp_path, ligado=True, inscrita=True, chave_privada=False)
        saida, lidas = _instalar(tmp_path, estado, vezes=2)
        for verbo in PROIBIDOS:
            assert verbo not in lidas, lidas
        assert "sudo rm" not in lidas and "sudo cp" not in lidas, lidas
        assert saida.count("falta a chave privada do DKMS (") == 1, saida
        assert str(tmp_path / "mok.key") in saida, saida
        assert "continua como estava" in saida and "./install.sh de novo" in saida, saida
        assert "mesa" not in saida.lower(), saida

    def test_com_a_privada_o_dkms_constroi(self, tmp_path: Path) -> None:
        estado = _estado_do_secure_boot(tmp_path, ligado=True, inscrita=True)
        saida, lidas = _instalar(tmp_path, estado)
        assert "dkms add" in lidas and "dkms build" in lidas, lidas
        assert "falta a chave privada" not in saida, saida

    def test_sem_secure_boot_a_falta_da_privada_nao_pesa(self, tmp_path: Path) -> None:
        estado = _estado_do_secure_boot(
            tmp_path, ligado=False, inscrita=False, chave_privada=False)
        saida, lidas = _instalar(tmp_path, estado)
        assert "dkms add" in lidas and "dkms build" in lidas, lidas
        assert "chave" not in saida, saida

    def test_a_chave_em_token_pkcs11_nao_e_falta(self, tmp_path: Path) -> None:
        estado = _estado_do_secure_boot(tmp_path, ligado=True, inscrita=True)
        framework = _framework(tmp_path, "pkcs11:token=dkms;object=chave")
        saida, lidas = _instalar(tmp_path, estado, framework=framework)
        assert "dkms build" in lidas, lidas
        assert "falta a chave privada" not in saida, saida

    @pytest.mark.skipif(os.geteuid() == 0, reason="o root lê qualquer arquivo")
    @pytest.mark.parametrize(
        ("no_cofre", "sudo_responde", "constroi", "frase"),
        [(True, True, True, ""), (False, True, False, "falta a chave privada do DKMS ("),
         (True, False, False, "não li a chave privada do DKMS (")],
        ids=["o-root-le-a-chave", "o-root-diz-que-falta", "o-sudo-nao-responde"],
    )
    def test_a_privada_na_pasta_que_so_o_root_abre_se_le_pelo_sudo_e_falha_e_nao_sei(
        self, tmp_path: Path, no_cofre: bool, sudo_responde: bool, constroi: bool, frase: str
    ) -> None:
        """D-2111-SEM-A-CHAVE-PRIVADA-O-DKMS-NAO-CONSTROI: o ``sudo`` que não responde é «não sei»,
        e o «não sei» não diz que a chave falta nem manda gerar outra: nada se mexe."""
        estado = _estado_do_secure_boot(tmp_path, ligado=True, inscrita=True)
        cofre = tmp_path / "cofre"
        cofre.mkdir()
        if no_cofre:
            (cofre / "mok.key").write_bytes(b"CHAVE-PRIVADA-DE-MENTIRA")
        cofre.chmod(0)
        chamadas = tmp_path / "chamadas.log"
        root = (
            f'echo "sudo $*" >> "{chamadas}"\n[ "$1" = -n ] && shift\n'
            f'/bin/chmod 700 "{cofre}"\n"$@"\nrc=$?\n/bin/chmod 000 "{cofre}"\nexit $rc'
        )
        calado = (f'case "$1 $2" in "-n sh") exit 1;; esac\n'
                  f'echo "sudo $*" >> "{chamadas}"\nexec "$@"')
        framework = _framework(tmp_path, str(cofre / "mok.key"))
        try:
            saida, lidas = _instalar(
                tmp_path, estado, framework=framework,
                dubles={"sudo": root if sudo_responde else calado})
            dito = _roda(
                "dkms_passo_se_a_chave_falta hid-playstation",
                f"{tmp_path / 'bin'}:/usr/bin:/bin",
                {**estado, "HEFESTO_DKMS_FRAMEWORK_CONFS": framework,
                 "HEFESTO_DKMS_MODULES_ROOT": str(tmp_path / "modules"),
                 "HEFESTO_DKMS_BOOT_ROOT": str(tmp_path / "boot-de-mentira"),
                 "HEFESTO_DKMS_KERNEL": KERNEL},
            )
        finally:
            cofre.chmod(0o700)
        assert ("dkms build" in lidas) is constroi, lidas
        if sudo_responde:
            assert "sudo -n sh -c" in lidas, lidas
        if frase:
            assert frase in saida, saida
        if not sudo_responde:
            assert "falta a chave privada" not in saida and "dkms remove" not in lidas, saida
        if sudo_responde:
            assert ("falta a chave privada" in dito.stdout) is (not constroi), dito
        else:
            assert dito.stdout == "", dito

    @pytest.mark.parametrize("estado_da_chave", ["fora", "nao-sei"])
    def test_a_chave_fora_ou_ilegivel_segue_o_caminho_de_antes(
        self, tmp_path: Path, estado_da_chave: str
    ) -> None:
        estado = _estado_do_secure_boot(
            tmp_path, ligado=True, inscrita=False,
            leitura="completa" if estado_da_chave == "fora" else "sem-lista",
            chave_privada=False)
        saida, lidas = _instalar(tmp_path, estado)
        for verbo in ("dkms add", "dkms build", "dkms install"):
            assert verbo not in lidas, lidas
        assert "falta a chave privada" not in saida, saida

    @pytest.mark.parametrize(
        ("config", "constroi"),
        [(CONFIG_QUE_ASSINA, False), (CONFIG_QUE_NAO_ASSINA, True), (None, False)],
        ids=["kernel-assina", "kernel-nao-assina", "config-ilegivel"],
    )
    def test_o_kernel_que_nao_assina_nao_pede_a_chave_privada(
        self, tmp_path: Path, config: str | None, constroi: bool
    ) -> None:
        """D-2111-O-KERNEL-SEM-ASSINATURA-DE-MODULO-NAO-REFAZ: o DKMS não assina nem gera par
        onde o kernel não assina; sem ler o ``.config``, a falta da privada segue valendo."""
        estado = _estado_do_secure_boot(
            tmp_path, ligado=True, inscrita=True, chave_privada=False)
        saida, lidas = _instalar(tmp_path, estado, config=config)
        assert ("dkms build" in lidas) is constroi, lidas
        assert ("falta a chave privada" in saida) is (not constroi), saida

    def test_o_gancho_exclusivo_e_o_atualizador_olham_o_config_do_kernel(
        self, tmp_path: Path
    ) -> None:
        """D-2111-O-KERNEL-SEM-ASSINATURA-DE-MODULO-NAO-REFAZ: o preparador diz o mesmo."""
        veredito = tmp_path / "dkms" / "pacote" / "1.0.0"
        veredito.mkdir(parents=True)
        for config, esperado, rc in ((CONFIG_QUE_ASSINA, "^/", 0), (CONFIG_QUE_NAO_ASSINA, "", 1),
                                     (None, "^/", 0)):
            raiz = tmp_path / f"c{rc}-{esperado.strip('^/') or 'x'}-{bool(config)}"
            raiz.mkdir()
            modulos = raiz / "modules"
            (modulos / KERNEL / "build").mkdir(parents=True)
            if config is not None:
                (modulos / KERNEL / "build" / ".config").write_text(config, encoding="utf-8")
            estado = _estado_do_secure_boot(
                raiz, ligado=True, inscrita=True, chave_privada=False)
            ambiente = {**os.environ, **estado, "PATH": _sem_mokutil(estado, os.environ["PATH"]),
                        "HEFESTO_DKMS_MODULES_ROOT": str(modulos),
                        "HEFESTO_DKMS_BOOT_ROOT": str(raiz / "sem-boot")}
            for preparador in CINCO_PREPARADORES:
                exclusivo = subprocess.run(
                    ["python3", str(preparador), "--exclusivo", KERNEL, str(raiz / "sem-fonte"),
                     str(veredito)], capture_output=True, text=True, check=False, timeout=60,
                    env=ambiente)
                assert exclusivo.stdout.strip() == esperado, (preparador, config, exclusivo)
            pergunta = subprocess.run(
                ["python3", str(PREPARADOR), "--sem-a-chave-privada", KERNEL], env=ambiente,
                capture_output=True, text=True, check=False, timeout=60)
            assert pergunta.returncode == (0 if esperado else 1), (config, pergunta)

    def test_o_gancho_exclusivo_dos_cinco_nao_deixa_o_dkms_construir(
        self, tmp_path: Path
    ) -> None:
        """O ``autoinstall`` do kernel novo constrói pelo ``dkms``: o gancho que o DKMS lê
        antes do build devolve o padrão que nenhum kernel casa."""
        veredito = tmp_path / "dkms" / "pacote" / "1.0.0"
        veredito.mkdir(parents=True)
        casos = [(True, False, "^/"), (True, True, ""), (False, False, "")]
        for preparador in CINCO_PREPARADORES:
            for ligado, com_privada, esperado in casos:
                raiz = tmp_path / f"{preparador.parent.name}-{ligado}-{com_privada}"
                raiz.mkdir()
                estado = _estado_do_secure_boot(
                    raiz, ligado=ligado, inscrita=ligado, chave_privada=com_privada)
                feito = subprocess.run(
                    ["python3", str(preparador), "--exclusivo", KERNEL,
                     str(tmp_path / "sem-fonte"), str(veredito)],
                    capture_output=True, text=True, check=False, timeout=60,
                    env={**os.environ, **estado, "PATH": _sem_mokutil(estado, os.environ["PATH"])},
                )
                assert feito.stdout.strip() == esperado, (preparador, ligado, com_privada, feito)

    @pytest.mark.parametrize(
        ("ligado", "com_privada", "esperado"),
        [(True, False, 0), (True, True, 1), (False, False, 1)],
        ids=["ligado-sem-privada", "ligado-com-privada", "desligado"],
    )
    def test_a_pergunta_do_python_e_a_do_bash_dizem_o_mesmo(
        self, tmp_path: Path, ligado: bool, com_privada: bool, esperado: int
    ) -> None:
        estado = {**_estado_do_secure_boot(
            tmp_path, ligado=ligado, inscrita=True, chave_privada=com_privada),
            **_sem_kernel_da_maquina(tmp_path)}
        caminho = _com_sudo_de_mentira(tmp_path, _sem_mokutil(estado))
        ambiente = {**os.environ, **estado, "PATH": caminho}
        python = subprocess.run(
            ["python3", str(PREPARADOR), "--sem-a-chave-privada"], env=ambiente,
            capture_output=True, text=True, check=False, timeout=60)
        assert python.returncode == esperado, python
        assert _roda("dkms_sem_a_chave_privada", caminho, estado).returncode == esperado

    def test_a_chave_privada_vazia_ou_em_token_no_python(self, tmp_path: Path) -> None:
        estado = _estado_do_secure_boot(tmp_path, ligado=True, inscrita=True)
        ambiente = {**os.environ, **estado, "PATH": _sem_mokutil(estado)}
        (tmp_path / "mok.key").write_bytes(b"")
        vazia = subprocess.run(
            ["python3", str(PREPARADOR), "--sem-a-chave-privada"], env=ambiente,
            capture_output=True, text=True, check=False, timeout=60)
        assert vazia.returncode == 0, vazia
        ambiente["HEFESTO_DKMS_FRAMEWORK_CONFS"] = _framework(tmp_path, "pkcs11:token=dkms")
        token = subprocess.run(
            ["python3", str(PREPARADOR), "--sem-a-chave-privada"], env=ambiente,
            capture_output=True, text=True, check=False, timeout=60)
        assert token.returncode == 1, token

    @pytest.mark.parametrize(
        ("ligado", "com_privada", "diz"),
        [(True, False, True), (True, True, False), (False, False, False)],
        ids=["ligado-sem-privada", "ligado-com-privada", "desligado"],
    )
    def test_o_doctor_diz_o_passo_quando_so_falta_a_privada(
        self, tmp_path: Path, ligado: bool, com_privada: bool, diz: bool
    ) -> None:
        estado = {**_estado_do_secure_boot(
            tmp_path, ligado=ligado, inscrita=ligado, chave_privada=com_privada),
            **_sem_kernel_da_maquina(tmp_path)}
        dito = _roda(
            "dkms_passo_se_a_chave_falta hid-playstation",
            _com_sudo_de_mentira(tmp_path, _sem_mokutil(estado)), estado)
        if diz:
            assert "falta a chave privada do DKMS" in dito.stdout, dito
            assert "./install.sh de novo" in dito.stdout, dito
        else:
            assert dito.stdout == "", dito

    @pytest.mark.parametrize("com_privada", [False, True], ids=["sem-privada", "com-privada"])
    def test_o_atualizador_do_root_nao_refaz_sem_a_privada(
        self, tmp_path: Path, com_privada: bool
    ) -> None:
        if os.geteuid() == 0:
            pytest.skip("o ajudante como root usa os caminhos de verdade")
        from tests.unit.test_o_ajudante_do_atualizador import Lar

        (tmp_path / "lar").mkdir()
        lar = Lar(tmp_path / "lar")
        pasta = lar.src / "hefesto-hid-playstation-1.0.0"
        pasta.mkdir()
        shutil.copy(PREPARADOR, pasta / "preparar-o-fonte.py")
        (pasta / "dkms.conf").write_text(
            'BUILT_MODULE_NAME[0]="hid-playstation"\n', encoding="utf-8")
        pasta.chmod(0o755)
        (pasta / "preparar-o-fonte.py").chmod(0o755)
        (pasta / "dkms.conf").chmod(0o644)
        (lar.modulos / KERNEL / "build").mkdir(parents=True)
        lar.duble("dkms", 'exit 0')
        lar.duble("mokutil", "exit 1")
        (tmp_path / "lar" / "ambiente").mkdir()
        estado = _estado_do_secure_boot(
            tmp_path / "lar" / "ambiente", ligado=True, inscrita=True, chave_privada=com_privada)
        feito = lar.rodar("dkms-refazer", **estado)
        assert feito.returncode == 0, feito.stderr
        lidas = lar.lidas()
        refez = [x for x in lidas if x.startswith(("dkms install", "dkms build"))]
        if com_privada:
            assert refez, lidas
        else:
            assert not refez and not [x for x in lidas if x.startswith("dkms remove")], lidas
            assert "falta a chave privada do DKMS" in feito.stdout, feito.stdout


GUARDA_DA_CHAVE_PRIVADA = (
    'if "${BASH_SOURCE[0]%/*}/preparar-o-fonte.py" --sem-a-chave-privada "$kernelver" '
    "2>/dev/null; then"
)
CINCO_DKMS_CONF = [preparador.parent / "dkms.conf" for preparador in CINCO_PREPARADORES]


class TestOAutoinstallNemChegaAoBuildSemAChavePrivada:
    """D-2111-SEM-A-CHAVE-PRIVADA-O-DKMS-NAO-CONSTROI, no ``autoinstall`` do kernel novo.

    Do DKMS 3.0.4 ao 3.1.6 o ``do_build`` roda o ``prepare_signing`` (que gera o par novo por cima
    da chave pública) antes de ler o ``dkms.conf`` que sai com 77: o ``--exclusivo`` chega tarde.
    O ``autoinstall`` lê o ``AUTOINSTALL`` antes do build, então o ``dkms.conf`` o zera quando falta
    a chave privada, e o DKMS nem começa o build do módulo.
    """

    def test_os_cinco_dkms_conf_perguntam_pela_chave_privada(self) -> None:
        assert len(CINCO_DKMS_CONF) == 5, CINCO_DKMS_CONF
        for conf in CINCO_DKMS_CONF:
            linhas = conf.read_text(encoding="utf-8").splitlines()
            assert GUARDA_DA_CHAVE_PRIVADA in linhas, f"{conf}: o autoinstall gera o par novo"
            depois = linhas[linhas.index(GUARDA_DA_CHAVE_PRIVADA) + 1:][:2]
            assert depois == ['    AUTOINSTALL=""', "fi"], (conf, depois)

    @pytest.mark.parametrize(
        ("ligado", "com_privada", "config", "esperado"),
        [(True, False, CONFIG_QUE_ASSINA, ""), (True, True, CONFIG_QUE_ASSINA, "yes"),
         (False, False, CONFIG_QUE_ASSINA, "yes"), (True, False, CONFIG_QUE_NAO_ASSINA, "yes")],
        ids=["ligado-sem-privada", "ligado-com-privada", "desligado", "kernel-nao-assina"],
    )
    def test_sem_a_privada_o_dkms_conf_lido_pelo_autoinstall_zera_o_autoinstall(
        self, tmp_path: Path, ligado: bool, com_privada: bool, config: str, esperado: str
    ) -> None:
        """D-2111-SEM-A-CHAVE-PRIVADA-O-DKMS-NAO-CONSTROI."""
        estado = _estado_do_secure_boot(
            tmp_path, ligado=ligado, inscrita=True, chave_privada=com_privada)
        modulos = tmp_path / "modules"
        (modulos / KERNEL / "build").mkdir(parents=True)
        (modulos / KERNEL / "build" / ".config").write_text(config, encoding="utf-8")
        ambiente = {**os.environ, **estado, "PATH": _sem_mokutil(estado, os.environ["PATH"]),
                    "HEFESTO_DKMS_MODULES_ROOT": str(modulos),
                    "HEFESTO_DKMS_BOOT_ROOT": str(tmp_path / "sem-boot")}
        for conf in CINCO_DKMS_CONF:
            lido = subprocess.run(
                ["bash", "-c",
                 'autoinstall() { [ "$s" = 77 ]; }\n'
                 f"kernelver={KERNEL}\nkernel_source_dir='{tmp_path / 'sem-fonte'}'\n"
                 f"dkms_tree='{tmp_path / 'arvore'}'\n. '{conf}'\n"
                 'printf "%s" "$AUTOINSTALL"'],
                capture_output=True, text=True, check=False, timeout=120, env=ambiente)
            assert lido.returncode == 0, (conf, lido.stderr)
            assert lido.stdout == esperado, (conf, lido.stdout, lido.stderr)
