"""RESTAURO-SO-COM-SINTOMA-01 — o restauro de hidraw entra no doctor, e só com sintoma."""

from __future__ import annotations

import re
import shutil
import subprocess
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[2]
DOCTOR = ROOT / "scripts" / "doctor.sh"

PDP_ESTREITA = (
    'ACTION!="remove", KERNEL=="hidraw*", ATTRS{idVendor}=="0e6f", '
    'ATTRS{idProduct}=="0185", MODE="0666", TAG+="uaccess"'
)
MANTA = 'KERNEL=="hidraw*", MODE="0666"'


def _funcao_inteira(nome: str) -> str:
    """O corpo da função shell, do cabeçalho à chave que fecha na coluna 0."""
    texto = DOCTOR.read_text(encoding="utf-8")
    i = texto.index(f"{nome}() {{")
    fim = texto.index("\n}\n", i)
    return texto[i : fim + 3]


class Ensaio:
    """Uma máquina de mentira: nós, sysfs e regras udev, todos em tmp_path."""

    def __init__(self, raiz: Path) -> None:
        self.raiz = raiz
        self.dev = raiz / "dev"
        self.sys = raiz / "sys"
        self.rules = raiz / "rules.d"
        for d in (self.dev, self.sys, self.rules):
            d.mkdir(parents=True, exist_ok=True)
        self.bin = raiz / "bin"
        self.bin.mkdir(exist_ok=True)
        sudo = self.bin / "sudo"
        sudo.write_text("#!/bin/sh\necho SUDO-CHAMADO >&2\nexit 1\n", encoding="utf-8")
        sudo.chmod(0o755)

    def no(self, nome: str, modo: int, vendor: str = "", produto: str = "") -> Path:
        """Um nó hidraw de mentira, com (ou sem) uevent que diga o aparelho."""
        p = self.dev / nome
        p.write_text("", encoding="utf-8")
        p.chmod(modo)
        if vendor:
            d = self.sys / nome / "device"
            d.mkdir(parents=True, exist_ok=True)
            (d / "uevent").write_text(
                f"DRIVER=hid-generic\nHID_ID=0003:0000{vendor.upper()}:0000{produto.upper()}\n"
                f"HID_NAME=aparelho de mentira\n",
                encoding="utf-8",
            )
        return p

    def regra(self, nome: str, conteudo: str) -> None:
        (self.rules / nome).write_text(conteudo + "\n", encoding="utf-8")

    def chama(self, corpo: str, quiet: str = "0") -> subprocess.CompletedProcess[str]:
        res = subprocess.run(
            ["bash", "-c", f'set --; source "$DOCTOR_SH"; QUIET={quiet}; {corpo}'],
            capture_output=True,
            text=True,
            timeout=60,
            check=False,
            env={
                "DOCTOR_SH": str(DOCTOR),
                "B": str(self.raiz),
                "PATH": f"{self.bin}:/usr/bin:/bin",
            },
        )
        assert "SUDO-CHAMADO" not in res.stderr, (
            "a cura gastou sudo num nó que já podia escrever:\n" + res.stderr
        )
        return res

    def plano(self) -> str:
        return self.chama('_hidraw_alvos_do_restauro "$B/dev" "$B/sys" "$B/rules.d"').stdout

    def check(self, quiet: str = "0") -> str:
        return self.chama(
            'check_perms_soft "$B/dev" "$B/sys" "$B/rules.d"', quiet=quiet
        ).stdout

    def cura(self, quiet: str = "0") -> str:
        return self.chama(
            'restaurar_hidraw_uaccess "$B/dev" "$B/sys" "$B/rules.d"', quiet=quiet
        ).stdout

    def modo(self, nome: str) -> str:
        return oct((self.dev / nome).stat().st_mode & 0o777)[2:]


@pytest.fixture()
def ensaio(tmp_path: Path) -> Ensaio:
    return Ensaio(tmp_path)


class TestOCriterioDeSintoma:
    """As duas metades do critério, uma de cada vez."""

    def test_no_orfao_aberto_e_alvo(self, ensaio: Ensaio) -> None:
        """Nada explica o nó aberto: é aqui, e só aqui, que restaurar vale."""
        ensaio.no("hidraw0", 0o666, "1234", "5678")
        assert "alvo " in ensaio.plano()

    def test_no_aberto_por_regra_estreitada_de_terceiro_nunca_e_alvo(
        self, ensaio: Ensaio
    ) -> None:
        """O lado que faz este critério existir."""
        ensaio.no("hidraw1", 0o666, "0e6f", "0185")
        ensaio.regra("71-pdp-controllers.rules", PDP_ESTREITA)
        plano = ensaio.plano()
        assert "alvo " not in plano, plano
        assert "estreita" in plano, plano
        assert "71-pdp-controllers.rules:1" in plano, plano

    def test_regra_manta_derruba_todo_alvo(self, ensaio: Ensaio) -> None:
        """A manta explica TODO nó — inclusive os que ninguém reivindicou."""
        ensaio.no("hidraw0", 0o666, "1234", "5678")
        ensaio.regra("60-openrgb.rules", MANTA)
        plano = ensaio.plano()
        assert "alvo " not in plano, plano
        assert "manta" in plano, plano

    def test_regra_de_outro_aparelho_nao_protege_este_no(
        self, ensaio: Ensaio
    ) -> None:
        """O negativo que impede o critério de virar "nunca conserta nada"."""
        ensaio.no("hidraw0", 0o666, "1234", "5678")
        ensaio.no("hidraw1", 0o666, "0e6f", "0185")
        ensaio.regra("71-pdp-controllers.rules", PDP_ESTREITA)
        plano = ensaio.plano()
        assert "hidraw0 666" in plano and "alvo " in plano, plano
        assert "pulo" in plano and "hidraw1" in plano.split("pulo", 1)[1], plano

    def test_no_fechado_nao_e_sintoma(self, ensaio: Ensaio) -> None:
        """0660 é o esperado. Diagnóstico sem sintoma não tem o que oferecer."""
        ensaio.no("hidraw0", 0o660, "1234", "5678")
        assert ensaio.plano().strip() == ""

    def test_regra_estreitada_sem_id_comparavel_e_incerta(
        self, ensaio: Ensaio
    ) -> None:
        """Quando não dá para provar que o nó está órfão, não se mexe nele."""
        ensaio.no("hidraw0", 0o666, "1234", "5678")
        ensaio.regra("65-obscura.rules", 'KERNEL=="hidraw*", KERNELS=="usb1", MODE="0666"')
        plano = ensaio.plano()
        assert "alvo " not in plano, plano
        assert "incerta" in plano, plano

    def test_no_sem_uevent_legivel_com_regra_estreitada_e_incerto(
        self, ensaio: Ensaio
    ) -> None:
        """Sem os ids do nó não há como saber se a regra é sobre ele."""
        ensaio.no("hidraw0", 0o666)
        ensaio.regra("71-pdp-controllers.rules", PDP_ESTREITA)
        plano = ensaio.plano()
        assert "alvo " not in plano, plano
        assert "incerta" in plano, plano

    def test_sem_regra_nenhuma_o_no_sem_uevent_ainda_e_alvo(
        self, ensaio: Ensaio
    ) -> None:
        """Não saber o aparelho só trava quando há decisão alheia em jogo."""
        ensaio.no("hidraw0", 0o666)
        assert "alvo " in ensaio.plano()

    def test_o_bit_de_leitura_sozinho_ja_e_sintoma(self, ensaio: Ensaio) -> None:
        """0664 deixa qualquer processo LER o nó — e é a leitura que vaza."""
        ensaio.no("hidraw0", 0o664, "1234", "5678")
        assert "alvo " in ensaio.plano()


class TestOTextoDizAntesDeAcontecer:
    """RECEITA-ERRADA-01: o doctor não pode mandar rodar o que não resolve."""

    def test_o_check_oferece_o_conserto_quando_ha_orfao(
        self, ensaio: Ensaio
    ) -> None:
        ensaio.no("hidraw0", 0o666, "1234", "5678")
        saida = ensaio.check()
        assert "--restaurar-hidraw-uaccess" in saida, saida
        assert "não roda sozinho" in saida, saida

    def test_o_check_nao_oferece_quando_a_regra_de_terceiro_explica(
        self, ensaio: Ensaio
    ) -> None:
        """A mordida que o pedido nomeia, do lado do atropelo."""
        ensaio.no("hidraw1", 0o666, "0e6f", "0185")
        ensaio.regra("71-pdp-controllers.rules", PDP_ESTREITA)
        saida = ensaio.check()
        assert "NÃO resolve este caso" in saida, saida
        assert "não roda sozinho" not in saida, saida
        assert "o que ele VAI fazer" not in saida, saida
        assert "estreitando por ele" in saida, saida
        assert "próximo evento de udev" in saida, saida

    def test_o_check_diz_o_que_o_conserto_nao_resolve(
        self, ensaio: Ensaio
    ) -> None:
        """Oferecer sem dizer o limite é a receita errada de novo."""
        ensaio.no("hidraw0", 0o666, "1234", "5678")
        saida = ensaio.check()
        assert "não IMPEDE o nó de reabrir" in saida, saida
        assert "não escreve em /etc" in saida, saida

    def test_a_cura_diz_o_plano_antes_de_agir(self, ensaio: Ensaio) -> None:
        """A ordem é o contrato: o texto tem de vir antes da linha do feito."""
        ensaio.no("hidraw0", 0o666, "1234", "5678")
        saida = ensaio.cura()
        assert "vou tirar o bit de OUTROS" in saida, saida
        assert saida.index("vou tirar o bit de OUTROS") < saida.index("[ OK ]"), saida

    def test_a_cura_fala_mesmo_com_quiet(self, ensaio: Ensaio) -> None:
        """Agir calado é o que não pode acontecer."""
        ensaio.no("hidraw0", 0o666, "1234", "5678")
        saida = ensaio.cura(quiet="1")
        assert "vou tirar o bit de OUTROS" in saida, saida

    def test_a_cura_recusada_explica_as_duas_metades(
        self, ensaio: Ensaio
    ) -> None:
        """Atropelo e inutilidade. Uma só já bastaria; as duas é que decidem."""
        ensaio.no("hidraw1", 0o666, "0e6f", "0185")
        ensaio.regra("71-pdp-controllers.rules", PDP_ESTREITA)
        saida = ensaio.cura()
        assert "decisão é de quem escreveu a regra" in saida, saida
        assert "próximo evento de udev" in saida, saida
        assert "o conserto é no arquivo, não no nó" in saida, saida


class TestACuraAge:
    def test_a_cura_tira_o_bit_de_outros_do_orfao(self, ensaio: Ensaio) -> None:
        ensaio.no("hidraw0", 0o666, "1234", "5678")
        ensaio.cura()
        assert ensaio.modo("hidraw0") == "660"

    def test_a_cura_nao_toca_no_no_de_terceiro(self, ensaio: Ensaio) -> None:
        """O outro lado da mordida que o usuário pediu, medido no nó e não no texto."""
        ensaio.no("hidraw0", 0o666, "1234", "5678")
        ensaio.no("hidraw1", 0o666, "0e6f", "0185")
        ensaio.regra("71-pdp-controllers.rules", PDP_ESTREITA)
        ensaio.cura()
        assert ensaio.modo("hidraw0") == "660", "o órfão não foi restaurado"
        assert ensaio.modo("hidraw1") == "666", "a decisão da distribuição foi atropelada"

    def test_sem_sintoma_a_cura_nao_faz_nada(self, ensaio: Ensaio) -> None:
        """Pedida a dedo, sem sintoma, a cura continua não agindo."""
        ensaio.no("hidraw0", 0o660, "1234", "5678")
        saida = ensaio.cura()
        assert "não há o que restaurar" in saida, saida
        assert ensaio.modo("hidraw0") == "660"

    @pytest.mark.skipif(
        shutil.which("setfacl") is None or shutil.which("getfacl") is None,
        reason="acl (setfacl/getfacl) ausente nesta máquina",
    )
    def test_a_cura_preserva_a_acl_do_uaccess(self, ensaio: Ensaio) -> None:
        """O uaccess do logind é uma ACL nomeada, e tem de sobreviver."""
        p = ensaio.no("hidraw0", 0o666, "1234", "5678")
        subprocess.run(["setfacl", "-m", "u:nobody:rw", str(p)], check=True, timeout=30)
        ensaio.cura()
        acl = subprocess.run(
            ["getfacl", "-p", str(p)], capture_output=True, text=True, check=True, timeout=30
        ).stdout
        assert "user:nobody:rw-" in acl, acl
        assert "mask::rw-" in acl, acl
        assert "other::---" in acl, acl

    @pytest.mark.skipif(
        shutil.which("setfacl") is None or shutil.which("getfacl") is None,
        reason="acl (setfacl/getfacl) ausente nesta máquina",
    )
    def test_a_cura_nao_alarga_a_mascara_da_acl(self, ensaio: Ensaio) -> None:
        """É por isto que o mecanismo é `chmod o=` e não `chmod 0660`."""
        p = ensaio.no("hidraw0", 0o666, "1234", "5678")
        subprocess.run(["setfacl", "-m", "u:nobody:rwx", str(p)], check=True, timeout=30)
        subprocess.run(["setfacl", "-m", "m::r", str(p)], check=True, timeout=30)
        ensaio.cura()
        acl = subprocess.run(
            ["getfacl", "-p", str(p)], capture_output=True, text=True, check=True, timeout=30
        ).stdout
        assert "mask::r--" in acl, f"a máscara foi ALARGADA pelo restauro:\n{acl}"
        assert "#effective:r--" in acl, f"nobody ganhou escrita que estava mascarada:\n{acl}"
        assert "other::---" in acl, acl


class TestAFiacao:
    """O defeito que esta sprint cura é código que existe e ninguém chama."""

    def test_a_opcao_existe_no_parser(self) -> None:
        texto = DOCTOR.read_text(encoding="utf-8")
        assert "--restaurar-hidraw-uaccess) RESTAURAR_HIDRAW=1" in texto

    def test_o_main_chama_a_cura(self) -> None:
        corpo = _funcao_inteira("main")
        assert "restaurar_hidraw_uaccess\n" in corpo, (
            "a opção existe e nada a invoca — o defeito de origem, de volta"
        )
        assert 'RESTAURAR_HIDRAW}" -eq 1' in corpo

    def test_o_apply_fixes_nao_chama_a_cura(self) -> None:
        """AUSÊNCIA DELIBERADA — decisão, 07/08/2026."""
        corpo = _funcao_inteira("apply_fixes")
        assert "restaurar_hidraw_uaccess " not in corpo
        assert "restaurar_hidraw_uaccess\n" not in corpo

    def test_o_install_nao_ganhou_a_opcao(self) -> None:
        """A outra metade da decisão de produto: no install, não entra."""
        for nome in ("install.sh", "scripts/install_udev.sh", "scripts/install-host-udev.sh"):
            alvo = ROOT / nome
            if alvo.exists():
                assert "restaurar-hidraw-uaccess" not in alvo.read_text(encoding="utf-8"), (
                    f"{nome} ganhou o restauro — o produto decidiu que ele NÃO entra no install"
                )

    def test_o_check_e_a_cura_passam_pelo_mesmo_cano(self) -> None:
        """RECEITA-ERRADA-01: dois critérios com o mesmo nome divergem."""
        chamada = '_hidraw_alvos_do_restauro "${devdir}" "${sysroot}"'
        assert chamada in _funcao_inteira("check_perms_soft"), (
            "o check voltou a calcular o critério por conta própria"
        )
        assert chamada in _funcao_inteira("restaurar_hidraw_uaccess"), (
            "a cura voltou a calcular o critério por conta própria"
        )

    def test_o_criterio_consulta_as_duas_vistas_da_varredura(self) -> None:
        """O elo do meio não pode ser um cano oco."""
        corpo = _funcao_inteira("_hidraw_alvos_do_restauro")
        assert "_udev_hidraw_rw_global " in corpo
        assert "_udev_hidraw_rw_estreitas " in corpo

    def test_a_cura_nao_escreve_regra_nem_toca_em_etc(self) -> None:
        """O que a cura promete no texto tem de ser o que pode fazer no código."""
        corpo = _funcao_inteira("restaurar_hidraw_uaccess")
        codigo = re.sub(r'"[^"]*"', "", corpo)
        assert "chmod o=" in codigo, "o mecanismo declarado sumiu do código"
        for proibido in ("udevadm", "setfacl", "install -D", "/etc/", "tee "):
            assert proibido not in codigo, (
                f"a cura passou a executar `{proibido}` — o texto promete que a cura "
                f"só tira o bit de outros:\n{codigo}"
            )
