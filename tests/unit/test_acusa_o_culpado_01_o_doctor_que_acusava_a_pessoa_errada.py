"""ACUSA-O-CULPADO-01 — o aviso do doctor culpava quem não tinha feito nada.

MEDIDO na máquina da mantenedora em 06/08/2026, entre 20h50 e 21h10. O doctor
imprimia, quatro vezes seguidas::

    [WARN] /dev/hidraw0 está 0666 (rw global) — provável ajuste manual;
           esperado é 0660+uaccess

O ajuste manual não existia. A causa era UMA linha, num arquivo de terceiro::

    /etc/udev/rules.d/60-openrgb.rules:10 -> KERNEL=="hidraw*", MODE="0666"

E o contraste medido no mesmo instante é a prova de que as regras do Hefesto
funcionavam o tempo todo:

===========================  ==============  ============================
nó                           modo            quem manda nele
===========================  ==============  ============================
hidraw0, 1, 4, 5             ``crw-rw-rw-``  ninguém (a regra de terceiro)
hidraw2, 3, 7                ``crw-rw----+`` regras do Hefesto, com ACL
hidraw6 (DualSense físico)   ``crw-------``  exclusivo do daemon
===========================  ==============  ============================

Nenhum `chmod` humano escolheria com precisão o COMPLEMENTO exato do conjunto
de regras do Hefesto, nem sobreviveria ao reboot. A frase mandava procurar onde
não estava — e os quatro nós abertos eram os receptores do TECLADO e do MOUSE
dela, que por hidraw entregam os relatórios de entrada crus.

Aqui a função shell REAL é executada (molde de
``tests/unit/test_doctor_8bitdo_cascade.py``), contra diretórios de regras
temporários. Nenhuma leitura em ``/etc`` e nenhum nó hidraw é aberto.
"""

from __future__ import annotations

import subprocess
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
DOCTOR = ROOT / "scripts" / "doctor.sh"

# A linha exata que estava em /etc/udev/rules.d/60-openrgb.rules até 06/08/2026.
BLANKET = 'KERNEL=="hidraw*", MODE="0666"'

# CONTROLE POSITIVO, copiado de /usr/lib/udev/rules.d/71-pdp-controllers.rules
# desta máquina: MODE="0666" com estreitamento por fabricante. É regra de
# distro, mira UM controle, e NÃO pode ser acusada — se aparecer, o filtro de
# estreitamento morreu e o portão vira ruído.
PDP_ESTREITA = (
    'ACTION!="remove", KERNEL=="hidraw*", ATTRS{idVendor}=="0e6f", '
    'ATTRS{idProduct}=="0185", MODE="0666", TAG+="uaccess"'
)

# O que o Hefesto instala: estreitado E sem bit para outros.
HEFESTO = (
    'KERNEL=="hidraw*", SUBSYSTEM=="hidraw", ATTRS{idVendor}=="054c", '
    'ATTRS{idProduct}=="0ce6", MODE="0660", TAG+="uaccess"'
)


def _varre(*dirs: Path) -> str:
    """Executa `_udev_hidraw_rw_global` de verdade, via source."""
    args = " ".join(f'"{d}"' for d in dirs)
    res = subprocess.run(
        ["bash", "-c", f'set --; source "$DOCTOR_SH"; _udev_hidraw_rw_global {args}'],
        capture_output=True,
        text=True,
        timeout=30,
        check=False,
        env={"DOCTOR_SH": str(DOCTOR), "PATH": "/usr/bin:/bin", "LC_ALL": "C"},
    )
    assert res.returncode == 0, res.stderr
    return res.stdout


class TestAVarreduraNomeiaOCulpado:
    def test_a_regra_sem_estreitamento_e_nomeada_com_arquivo_e_linha(
        self, tmp_path: Path
    ) -> None:
        """O que o aviso antigo não sabia dizer: o endereço."""
        d = tmp_path / "rules.d"
        d.mkdir()
        (d / "60-openrgb.rules").write_text(
            f"# OpenRGB udev rules\nKERNEL==\"i2c-[0-9]*\", MODE=\"0666\"\n{BLANKET}\n",
            encoding="utf-8",
        )
        saida = _varre(d)
        assert "60-openrgb.rules:3:" in saida, saida
        assert BLANKET in saida, saida

    def test_regra_estreitada_por_fabricante_nao_e_acusada(self, tmp_path: Path) -> None:
        """MODE="0666" mirando UM aparelho é decisão de quem escreveu a regra.

        Sem este negativo o portão acusaria meia `/usr/lib/udev/rules.d` e
        viraria ruído — falso positivo em massa torna o gate inútil.
        """
        d = tmp_path / "rules.d"
        d.mkdir()
        (d / "71-pdp-controllers.rules").write_text(
            PDP_ESTREITA + "\n", encoding="utf-8"
        )
        assert _varre(d) == "", _varre(d)

    def test_regra_do_hefesto_nao_e_acusada(self, tmp_path: Path) -> None:
        d = tmp_path / "rules.d"
        d.mkdir()
        (d / "70-ps5-controller.rules").write_text(HEFESTO + "\n", encoding="utf-8")
        assert _varre(d) == ""

    def test_linha_comentada_nao_conta(self, tmp_path: Path) -> None:
        """Regra desligada é regra que não vale — inclusive indentada."""
        d = tmp_path / "rules.d"
        d.mkdir()
        (d / "90-antigo.rules").write_text(
            f"#{BLANKET}\n   # {BLANKET}\n", encoding="utf-8"
        )
        assert _varre(d) == ""

    def test_o_bit_de_leitura_sozinho_ja_conta(self, tmp_path: Path) -> None:
        """O check antigo casava só o literal `666`.

        `0664` deixa QUALQUER processo local LER o nó — e é a leitura, não a
        escrita, que vaza o que está sendo digitado no receptor do teclado.
        `0662` e `0646` tinham o mesmo buraco.
        """
        d = tmp_path / "rules.d"
        d.mkdir()
        for i, modo in enumerate(("0664", "0662", "0646")):
            (d / f"9{i}-modo.rules").write_text(
                f'KERNEL=="hidraw*", MODE="{modo}"\n', encoding="utf-8"
            )
        saida = _varre(d)
        for modo in ("0664", "0662", "0646"):
            assert modo in saida, f"modo {modo} passou em silêncio:\n{saida}"

    def test_modo_sem_bit_para_outros_nao_conta(self, tmp_path: Path) -> None:
        d = tmp_path / "rules.d"
        d.mkdir()
        (d / "60-ok.rules").write_text(
            'KERNEL=="hidraw*", MODE="0660", TAG+="uaccess"\n', encoding="utf-8"
        )
        assert _varre(d) == ""

    def test_arquivo_em_etc_faz_sombra_no_de_usr_lib(self, tmp_path: Path) -> None:
        """É assim que o udev resolve, e é o que a regra dela exercita HOJE.

        MEDIDO em 06/08 21:20: `60-openrgb.rules` foi corrigido para
        0660+uaccess. Se a varredura ignorasse a sombra, ela continuaria
        acusando uma cópia velha do mesmo nome noutro diretório e a correção
        nunca apareceria como feita.
        """
        etc = tmp_path / "etc"
        lib = tmp_path / "lib"
        etc.mkdir()
        lib.mkdir()
        (etc / "60-openrgb.rules").write_text(
            'KERNEL=="hidraw*", MODE="0660", TAG+="uaccess"\n', encoding="utf-8"
        )
        (lib / "60-openrgb.rules").write_text(BLANKET + "\n", encoding="utf-8")
        assert _varre(etc, lib) == "", "a versão de /usr/lib venceu a de /etc"

    def test_subsystem_hidraw_tambem_casa(self, tmp_path: Path) -> None:
        """`SUBSYSTEM=="hidraw"` abre o mesmo tanto que `KERNEL=="hidraw*"`."""
        d = tmp_path / "rules.d"
        d.mkdir()
        (d / "60-outro.rules").write_text(
            'SUBSYSTEM=="hidraw", MODE="0666"\n', encoding="utf-8"
        )
        assert "60-outro.rules:1:" in _varre(d)


class TestOAvisoDeixouDeAcusarAPessoa:
    """O texto é o defeito inteiro: o grau [WARN] estava certo, a frase não."""

    def test_a_frase_provavel_ajuste_manual_saiu_do_caminho_com_causa(self) -> None:
        texto = DOCTOR.read_text(encoding="utf-8")
        i = texto.index("check_perms_soft()")
        corpo = texto[i : i + 2600]
        assert "provável ajuste manual" not in corpo.split('warn "${#abertos[@]}')[0], (
            "o aviso ainda acusa antes de olhar a causa"
        )
        # A hipótese de ajuste manual continua VÁLIDA — mas só quando nenhuma
        # regra explica. Foi para esse ramo que ela mudou de lugar.
        assert "ajuste manual é hipótese" in corpo, corpo[:800]

    def test_o_grau_continua_warn_e_nao_reprova_o_exit_code(self) -> None:
        """Decisão medida, não esquecimento.

        Só o `fail` alimenta `FAILS`, que é o código de saída do doctor. Fazer a
        configuração de um programa de TERCEIRO reprovar o portão de saúde do
        Hefesto seria dizer "estou doente" por algo que não é nosso.
        """
        texto = DOCTOR.read_text(encoding="utf-8")
        i = texto.index("check_perms_soft()")
        corpo = texto[i : i + 2600]
        assert 'fail "' not in corpo, "o check virou reprovação de exit code"
        assert 'warn "' in corpo

    def test_o_texto_diz_o_que_esta_aberto_e_de_quem_e_o_arquivo(self) -> None:
        texto = DOCTOR.read_text(encoding="utf-8")
        i = texto.index("check_perms_soft()")
        corpo = texto[i : i + 2600]
        assert "NÃO é do Hefesto" in corpo, "o aviso não diz de quem é o arquivo"
        assert "70-ps5-controller.rules" in corpo, (
            "o aviso não inocenta os aparelhos do Hefesto com prova"
        )
