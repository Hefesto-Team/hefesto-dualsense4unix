"""A frase do `--dry-run` não é quem instala — a paridade não a aceita como dono.

INSTALL-E-UNINSTALL-DO-RADIO-01 (23/09/2026), o P-17 que a conferência da
O-QUE-E-DO-HEFESTO-SAI-DO-ZSH-01 achou: a seção «artefato de sistema sem dono»
do `check_packaging_parity.sh` lia como dono qualquer linha de código que citasse
o artefato — e o `_faria_root "instalar …hefesto-wifi-usb-vigia.service…"` do
ensaio do install é uma FRASE sobre a instalação. Medido: com a lib
`camada_de_maquina.sh` (quem instala de verdade) arrancada da lista de donos, a
seção seguia verde.

A régua roda o portão numa árvore sintética (a da família do vigia) com a lib
fora da lista de donos, e exige que o vigia apareça órfão. Na árvore inteira
não dá para medir: o `install-host-udev.sh` procura as units numa lista de
pastas que inclui `assets/systemd`, e a seção lê a pasta como cópia de
diretório — é o furo que fica declarado na sprint.

A MORDIDA, medida: tirar o filtro das linhas que só falam (`_faria*`, `log`,
`echo`…) do `_dono_codigo` deixa o vigia «com dono» pela frase, e o teste
reprova.
"""

from __future__ import annotations

from pathlib import Path

from tests.unit.test_o_que_era_do_zsh_mora_no_hefesto import _paridade_numa_arvore

_DONOS_COM_A_LIB = "    for _dono_cand in install.sh scripts/lib/camada_de_maquina.sh \\\n"
_DONOS_SEM_A_LIB = "    for _dono_cand in install.sh \\\n"


def test_com_a_lib_o_vigia_tem_dono(tmp_path: Path) -> None:
    saida = _paridade_numa_arvore(tmp_path)
    assert "[ OK ] artefatos de sistema:" in saida, saida


def test_sem_a_lib_a_frase_do_ensaio_nao_segura_o_vigia(tmp_path: Path) -> None:
    saida = _paridade_numa_arvore(
        tmp_path,
        {"scripts/check_packaging_parity.sh": (_DONOS_COM_A_LIB, _DONOS_SEM_A_LIB)},
    )
    assert (
        "[FAIL] assets/systemd/hefesto-wifi-usb-vigia.service: artefato de sistema que "
        "nenhum caminho de instalação alcança"
    ) in saida, (
        "sem a lib entre os donos, o vigia seguiu «com dono» — a frase do ensaio do "
        "install passou por instalação:\n" + saida
    )
