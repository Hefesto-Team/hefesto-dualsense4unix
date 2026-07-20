"""Onda T — assinaturas novas do hid-nintendo no doctor.sh + storm_watch.sh.

Desenho: docs/process/estudos/2026-07-20-desenho-onda-t-patch-dkms.md
(§Doctor / kernel-watch). Premissa 7 do estudo: DUAS assinaturas que hoje
não tinham check — a morte por PROBE (`Failed to get joycon info; ret=-110`
→ `probe - fail = -110`, a morte "invisível" medida 3x) e o "exceeded"
DENSO sem cascata de timeouts (jitter/contenda, não rádio morto).

Cobertura (falha-sem/passa-com, sem journal real — funções extraídas rodam
em bash com stub de journalctl/entrada sintética):
- check_hefesto_hid_nintendo_dkms definido, chamado no main e READ-ONLY;
- detecção do módulo patchado por parameters/ + modinfo -F filename
  (NUNCA srcversion — armadilha documentada no estudo);
- as duas assinaturas disparam warn com as entradas certas e ficam em
  silêncio com journal limpo;
- storm_watch: GREP_UNION ganhou os padrões de probe e a tag nova
  [JOYCON-PROBE], com [JOYCON] intacto (a string do exceeded não mudou).
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
STORM_PATH = REPO_ROOT / "scripts" / "storm_watch.sh"
DKMS_CONF_PATH = REPO_ROOT / "assets" / "dkms" / "hid-nintendo" / "dkms.conf"

DOCTOR = DOCTOR_PATH.read_text(encoding="utf-8") if DOCTOR_PATH.exists() else ""
STORM = STORM_PATH.read_text(encoding="utf-8") if STORM_PATH.exists() else ""
DKMS_CONF = DKMS_CONF_PATH.read_text(encoding="utf-8") if DKMS_CONF_PATH.exists() else ""

INSTANCIA = "0005:057E:2009.0041"


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


class TestWiringDoCheck:
    def test_bash_n_doctor_e_storm(self) -> None:
        for caminho in (DOCTOR_PATH, STORM_PATH):
            resultado = subprocess.run(
                ["bash", "-n", str(caminho)], capture_output=True, text=True, check=False
            )
            assert resultado.returncode == 0, f"{caminho.name}: {resultado.stderr}"

    def test_check_definido_e_chamado_no_main(self) -> None:
        assert "check_hefesto_hid_nintendo_dkms()" in DOCTOR
        assert re.search(r"^\s*check_hefesto_hid_nintendo_dkms\s*$", DOCTOR, re.MULTILINE), (
            "o check precisa ser CHAMADO no fluxo principal, não só definido"
        )
        assert 'hdr "DKMS hid-nintendo' in DOCTOR

    def test_pkg_e_versao_batem_com_o_dkms_conf(self) -> None:
        pkg = re.search(r'^readonly HEFESTO_DKMS_HID_NINTENDO_PKG="([^"]+)"$', DOCTOR, re.MULTILINE)
        ver = re.search(r'^readonly HEFESTO_DKMS_HID_NINTENDO_VER="([^"]+)"$', DOCTOR, re.MULTILINE)
        assert pkg is not None and ver is not None, "constantes do doctor ausentes"
        assert f'PACKAGE_NAME="{pkg.group(1)}"' in DKMS_CONF
        assert f'PACKAGE_VERSION="{ver.group(1)}"' in DKMS_CONF, (
            "bump de versão exige atualizar os DOIS lados (doctor + dkms.conf)"
        )

    def test_assinaturas_novas_wiradas_dentro_do_check(self) -> None:
        corpo = _extrai_funcao_bash(DOCTOR, "check_hefesto_hid_nintendo_dkms")
        assert "_check_hid_nintendo_probe_death_signature" in corpo
        assert "_check_hid_nintendo_exceeded_dense_signature" in corpo


class TestCheckReadOnlyEDeteccao:
    def test_check_e_read_only_nunca_instala_nem_recarrega(self) -> None:
        corpo = _sem_comentarios(_extrai_funcao_bash(DOCTOR, "check_hefesto_hid_nintendo_dkms"))
        # `sudo apt install dkms`/`./install.sh` nas MENSAGENS são dicas de
        # cura legítimas — o proibido é o doctor EXECUTAR dkms install/build/
        # add/remove ou recarregar módulo.
        assert not re.search(r"\bdkms (install|build|add|remove)\b", corpo), (
            "doctor diagnostica; instalar/remover é do install.sh/uninstall.sh"
        )
        assert not re.search(r"\b(modprobe(?!\.d)|rmmod|insmod)\b", corpo)

    def test_modulo_carregado_detectado_por_parameters(self) -> None:
        corpo = _extrai_funcao_bash(DOCTOR, "check_hefesto_hid_nintendo_dkms")
        assert "/sys/module/hid_nintendo/parameters" in corpo, (
            "o in-tree tem ZERO params — parameters/ é o marcador do patchado"
        )
        assert "bt_probe_retries" in corpo, "mostrar o valor efetivo (esperado 3)"

    def test_proximo_carregamento_por_modinfo_filename_nunca_srcversion(self) -> None:
        corpo = _extrai_funcao_bash(DOCTOR, "check_hefesto_hid_nintendo_dkms")
        assert "modinfo -F filename hid_nintendo" in corpo
        assert "*/updates/dkms/*" in corpo
        # Nos comentários a armadilha pode (e deve) ser citada — o proibido
        # é o CÓDIGO consultar srcversion como critério.
        assert "srcversion" not in _sem_comentarios(DOCTOR), (
            "srcversion difere entre builds do MESMO source (armadilha do estudo)"
        )

    def test_in_tree_carregado_avisa_vale_no_proximo_boot(self) -> None:
        corpo = _extrai_funcao_bash(DOCTOR, "check_hefesto_hid_nintendo_dkms")
        assert "próximo boot" in corpo
        assert "derrubaria" in corpo, (
            "a razão de nunca recarregar (controles em uso) fica na mensagem"
        )

    def test_mensagem_nunca_promete_replug_para_modulo_carregado(self) -> None:
        # Achado #6 do corretor: 'próximo boot/replug' contradiz o próprio
        # desenho da onda — replug NÃO troca módulo carregado (re-liga no
        # driver residente); prometer replug induz exatamente a ação manual
        # perigosa (modprobe -r com Pro/8BitDo conectados) que o fail-safe
        # quer evitar. install.sh já dizia a verdade; o doctor divergia.
        corpo = _extrai_funcao_bash(DOCTOR, "check_hefesto_hid_nintendo_dkms")
        assert "boot/replug" not in corpo, (
            "replug NÃO ativa o patchado com o in-tree carregado — só boot"
        )
        assert "replug NÃO troca módulo carregado" in corpo, (
            "a mensagem explica POR QUE replug não ajuda (educa, não frustra)"
        )

    def test_remediacao_acionavel_tambem_sem_checkout(self) -> None:
        # Achado #9 do corretor: 'rode ./install.sh' era a única remediação
        # — inacionável p/ quem instalou por pacote (.deb/rpm/arch).
        corpo = _extrai_funcao_bash(DOCTOR, "check_hefesto_hid_nintendo_dkms")
        assert "install-host-udev.sh" in corpo, (
            "usuário de pacote precisa de um caminho de cura que ele TEM"
        )

    def test_dkms_instalado_para_outro_kernel_e_warn_de_rebase(self) -> None:
        corpo = _extrai_funcao_bash(DOCTOR, "check_hefesto_hid_nintendo_dkms")
        assert "rebase pendente" in corpo, (
            "kernel novo sem build DKMS = in-tree em uso, a cura não pode sumir "
            "em silêncio"
        )


class TestAssinaturaMortePorProbe:
    """Funcional: a função extraída roda com journalctl de mentira."""

    def _roda(
        self, tmp_path: Path, jornal: str
    ) -> subprocess.CompletedProcess[str]:
        stubs = tmp_path / "bin"
        stubs.mkdir(exist_ok=True)
        fixture = tmp_path / "jornal.txt"
        fixture.write_text(jornal, encoding="utf-8")
        stub = stubs / "journalctl"
        stub.write_text(f'#!/bin/sh\ncat "{fixture}"\n', encoding="utf-8")
        stub.chmod(0o755)
        funcao = _extrai_funcao_bash(DOCTOR, "_check_hid_nintendo_probe_death_signature")
        corpo = (
            'warn() { printf "WARN: %s\\n" "$*"; }\n'
            'info() { printf "INFO: %s\\n" "$*"; }\n'
            f"{funcao}\n"
            "_check_hid_nintendo_probe_death_signature\n"
            'printf "RC=%s\\n" "$?"\n'
        )
        return _roda_script(tmp_path, corpo, path=f"{stubs}:/usr/bin:/bin")

    def test_morte_por_probe_dispara_warn_dedicado(self, tmp_path: Path) -> None:
        jornal = (
            f"jul 20 11:56:41 meow kernel: nintendo {INSTANCIA}: "
            "Failed to get joycon info; ret=-110\n"
            f"jul 20 11:56:41 meow kernel: nintendo {INSTANCIA}: probe - fail = -110\n"
        )
        resultado = self._roda(tmp_path, jornal)
        assert "RC=0" in resultado.stdout, resultado.stderr
        assert "WARN: morte por PROBE" in resultado.stdout
        assert "sem sinal do retry" in resultado.stdout, (
            "sem o patch agindo, o doctor aponta para conferir o módulo carregado"
        )

    def test_retry_do_patch_e_reportado_quando_presente(self, tmp_path: Path) -> None:
        jornal = (
            f"jul 20 11:56:41 meow kernel: nintendo {INSTANCIA}: "
            "Failed to get joycon info; ret=-110\n"
            f"jul 20 11:56:41 meow kernel: nintendo {INSTANCIA}: probe - fail = -110\n"
            f"jul 20 11:56:43 meow kernel: nintendo {INSTANCIA}: "
            "init over bluetooth failed (-110); retrying (2 left)\n"
        )
        resultado = self._roda(tmp_path, jornal)
        assert "WARN: morte por PROBE" in resultado.stdout
        assert "INFO: o retry do patch DKMS está agindo" in resultado.stdout

    def test_journal_limpo_fica_em_silencio(self, tmp_path: Path) -> None:
        jornal = "jul 20 11:00:00 meow kernel: usb 3-3: novo device qualquer\n"
        resultado = self._roda(tmp_path, jornal)
        assert "RC=0" in resultado.stdout, resultado.stderr
        assert "WARN" not in resultado.stdout

    def test_so_info_fail_sem_probe_fail_nao_dispara(self, tmp_path: Path) -> None:
        # As DUAS pontas da assinatura são exigidas (evita falso-positivo em
        # timeout transitório que o probe sobreviveu).
        jornal = (
            f"jul 20 11:56:41 meow kernel: nintendo {INSTANCIA}: "
            "Failed to get joycon info; ret=-110\n"
        )
        resultado = self._roda(tmp_path, jornal)
        assert "WARN" not in resultado.stdout

    def test_usa_transport_kernel_nunca_journalctl_k(self) -> None:
        # Armadilha do sprint T0: `journalctl -k` implica -b e já confundiu
        # um diagnóstico — os checks NOVOS usam _TRANSPORT=kernel explícito.
        for nome in (
            "_check_hid_nintendo_probe_death_signature",
            "_check_hid_nintendo_exceeded_dense_signature",
        ):
            corpo = _extrai_funcao_bash(DOCTOR, nome)
            assert "_TRANSPORT=kernel" in corpo, f"{nome} sem _TRANSPORT=kernel"
            assert not re.search(r"journalctl\s+(-b\s+)?-k\b", corpo), (
                f"{nome} não pode usar journalctl -k"
            )


class TestAssinaturaExceededDenso:
    """Funcional: o scan é função PURA (stdin → stdout) — entrada sintética."""

    def _roda_scan(
        self, tmp_path: Path, entrada: str, arg: str = ""
    ) -> subprocess.CompletedProcess[str]:
        funcao = _extrai_funcao_bash(DOCTOR, "_hid_nintendo_dense_exceeded_scan")
        corpo = f"{funcao}\n_hid_nintendo_dense_exceeded_scan {arg}\n"
        return _roda_script(tmp_path, corpo, entrada=entrada)

    @staticmethod
    def _linhas(instancia: str, exceeded: int, timeouts: int) -> str:
        linha_exc = (
            f"kernel: nintendo {instancia}: joycon_enforce_subcmd_rate: "
            "exceeded max attempts\n"
        )
        linha_to = f"kernel: nintendo {instancia}: timeout waiting for input report\n"
        return linha_exc * exceeded + linha_to * timeouts

    def test_denso_sem_timeouts_e_flagrado(self, tmp_path: Path) -> None:
        resultado = self._roda_scan(tmp_path, self._linhas(INSTANCIA, 6, 2))
        assert resultado.returncode == 0, resultado.stderr
        assert resultado.stdout.strip() == f"{INSTANCIA} 6 2"

    def test_cascata_terminal_nao_e_deste_check(self, tmp_path: Path) -> None:
        # 12 timeouts culminando em 1 exceeded = rádio morto (check antigo);
        # aqui fica em silêncio (gate exceeded >= 5 E timeouts < exceeded).
        resultado = self._roda_scan(tmp_path, self._linhas(INSTANCIA, 1, 12))
        assert resultado.stdout.strip() == ""

    def test_empate_de_contagens_nao_dispara(self, tmp_path: Path) -> None:
        resultado = self._roda_scan(tmp_path, self._linhas(INSTANCIA, 6, 6))
        assert resultado.stdout.strip() == ""

    def test_instancias_sao_separadas(self, tmp_path: Path) -> None:
        outra = "0005:057E:2009.000F"
        entrada = self._linhas(INSTANCIA, 5, 0) + self._linhas(outra, 12, 30)
        resultado = self._roda_scan(tmp_path, entrada)
        assert resultado.stdout.strip() == f"{INSTANCIA} 5 0", (
            "só a instância densa dispara; a cascata terminal fica de fora"
        )

    def test_gate_minimo_configuravel(self, tmp_path: Path) -> None:
        resultado = self._roda_scan(tmp_path, self._linhas(INSTANCIA, 4, 0), arg="4")
        assert resultado.stdout.strip() == f"{INSTANCIA} 4 0"
        resultado_default = self._roda_scan(tmp_path, self._linhas(INSTANCIA, 4, 0))
        assert resultado_default.stdout.strip() == "", "default do gate é 5"

    def test_entrada_vazia_sai_vazio(self, tmp_path: Path) -> None:
        resultado = self._roda_scan(tmp_path, "")
        assert resultado.returncode == 0, resultado.stderr
        assert resultado.stdout.strip() == ""

    def test_warn_de_contenda_wirado_na_assinatura(self) -> None:
        corpo = _extrai_funcao_bash(DOCTOR, "_check_hid_nintendo_exceeded_dense_signature")
        assert "_hid_nintendo_dense_exceeded_scan" in corpo
        assert "interferência/contenda BT" in corpo


class TestStormWatch:
    def _grep_union(self) -> str:
        match = re.search(r'^GREP_UNION="(.+)"$', STORM, re.MULTILINE)
        assert match is not None, "GREP_UNION não encontrado no storm_watch.sh"
        return match.group(1)

    def test_union_ganhou_os_padroes_de_probe(self) -> None:
        union = self._grep_union()
        assert "probe - fail = -" in union, "morte por probe (qualquer errno)"
        assert "failed to get joycon info" in union
        assert "init over bluetooth failed" in union, "o retry do patch agindo"

    def test_union_mantem_o_padrao_antigo_do_rate_limit(self) -> None:
        assert "joycon_enforce_subcmd_rate" in self._grep_union(), (
            "[JOYCON] fica intacto — a string do exceeded não mudou no patch"
        )

    def test_tag_nova_joycon_probe_sem_mexer_na_antiga(self) -> None:
        assert 'tag = "[JOYCON-PROBE]"' in STORM
        assert 'tag = "[JOYCON]"' in STORM

    def test_doctor_sumariza_a_tag_nova_do_kernel_watch(self) -> None:
        assert re.search(r"for tag in .*\bJOYCON-PROBE\b", DOCTOR), (
            "o resumo do kernel-watch no doctor precisa contar [JOYCON-PROBE]"
        )
        assert "falhou no PROBE" in DOCTOR
