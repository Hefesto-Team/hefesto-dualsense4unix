"""O uninstall tem de saber desfazer tudo que o install faz.

O `install.sh` descobre as regras udev por glob em `assets/*.rules`; o
`uninstall.sh` traz uma lista ESCRITA À MÃO. A assimetria é silenciosa e só
aparece muito depois: quem adiciona uma regra nova ganha a instalação de graça
e esquece a remoção, e a regra fica órfã em `/etc/udev/rules.d` depois do
uninstall — mexendo no comportamento de devices de quem já desinstalou.

Foi o que aconteceu ao acrescentar `82-nintendo-pro-nosniff.rules`.
"""
from __future__ import annotations

import re
from pathlib import Path

RAIZ = Path(__file__).resolve().parents[2]
ASSETS = RAIZ / "assets"
INSTALL = RAIZ / "install.sh"
UNINSTALL = RAIZ / "uninstall.sh"


def _regras_do_repo() -> set[str]:
    """Nomes das regras udev versionadas — as que o install instala por glob."""
    return {p.name for p in ASSETS.glob("[0-9][0-9]-*.rules")}


def _regras_removidas() -> set[str]:
    """Regras que o uninstall de fato APAGA.

    Só valem as citadas dentro de um `rm`: o script também IMPRIME caminhos numa
    seção "fora do escopo (não removido — não é do hefesto)", onde lista regras
    de terceiros (`50-system76-power.rules` do Pop!_OS, `99-storage-no-link-pm`
    do self-heal da usuária) para deixar claro que não encosta nelas. Casar o
    texto inteiro confundiria "avisa que preserva" com "remove".
    """
    linhas = UNINSTALL.read_text(encoding="utf-8").splitlines()
    removidas: set[str] = set()
    dentro_de_rm = False
    for linha in linhas:
        if re.search(r"\brm\b\s+-[a-zA-Z]*f", linha):
            dentro_de_rm = True
        if dentro_de_rm:
            removidas.update(
                re.findall(r"/etc/udev/rules\.d/([0-9]{2}-[\w.-]+\.rules)", linha)
            )
            # a lista continua enquanto a linha terminar em barra invertida
            if not linha.rstrip().endswith("\\"):
                dentro_de_rm = False
    return removidas


def test_uninstall_remove_toda_regra_que_o_install_instala() -> None:
    faltando = _regras_do_repo() - _regras_removidas()
    assert not faltando, (
        "regras que o install instala e o uninstall NÃO remove: "
        f"{sorted(faltando)}. Elas ficariam órfãs em /etc/udev/rules.d."
    )


def test_uninstall_nao_cita_regra_que_nao_existe_mais() -> None:
    """O espelho vale nos dois sentidos.

    Uma regra citada no uninstall que não existe mais no repo é um `rm -f` de
    caminho morto: inofensivo em execução, mas é rastro de renomeação
    incompleta e engana quem lê a lista para saber o que o projeto instala.
    """
    # Regras que o projeto já instalou no passado e removeu do repo continuam
    # na lista de propósito, para limpar quem atualizou de uma versão antiga.
    historicas = {
        "73-ps5-controller-hotplug.rules",
        "74-ps5-controller-hotplug-bt.rules",
    }

    fantasmas = _regras_removidas() - _regras_do_repo() - historicas
    assert not fantasmas, (
        f"o uninstall cita regras que não existem em assets/: {sorted(fantasmas)}. "
        "Se forem herança de versão antiga, declare-as em `historicas` com o motivo."
    )


def test_helpers_bt_instalados_sao_os_mesmos_removidos() -> None:
    """Mesma armadilha, outra lista: os scripts de resiliência do Bluetooth."""
    inst = INSTALL.read_text(encoding="utf-8")
    unin = UNINSTALL.read_text(encoding="utf-8")

    m = re.search(r"for _btres_s in ([^;]+); do", inst)
    assert m is not None, "a lista de helpers BT do install mudou de forma"
    instalados = {n for n in m.group(1).split() if n.endswith(".sh")}

    removidos = set(
        re.findall(r"/usr/local/lib/hefesto-dualsense4unix/([\w.-]+\.sh)", unin)
    )

    faltando = instalados - removidos
    assert not faltando, (
        f"helpers BT instalados e nunca removidos: {sorted(faltando)}"
    )
