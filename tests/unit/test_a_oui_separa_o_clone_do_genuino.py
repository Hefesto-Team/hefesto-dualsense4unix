"""Por RÁDIO, o único discriminador entre o clone e o genuíno é a OUI do MAC."""

from __future__ import annotations

import re
from pathlib import Path

from hefesto_dualsense4unix.app.actions.external_controllers import (
    _BRAND_BY_OUI,
    brand_of,
)
from hefesto_dualsense4unix.core.linhagem_nintendo import OUIS_NINTENDO_VISTAS
from hefesto_dualsense4unix.daemon.subsystems.external_identity import (
    NINTENDO_REAL_OUI,
)

REPO_ROOT = Path(__file__).resolve().parents[2]
SCRIPT_MODO_ATIVO = REPO_ROOT / "scripts" / "bt_active_mode.sh"
SCRIPT_BORDA = REPO_ROOT / "scripts" / "bt_nosniff_now.sh"
REGRA_NOSNIFF = REPO_ROOT / "assets" / "82-nintendo-pro-nosniff.rules"

OUI_DO_CLONE = next(iter(_BRAND_BY_OUI))


def _mac_mascarado(oui: str, ultimo: int) -> str:
    """`OUI:00:00:NN` — a máscara da casa, montada a partir da OUI dada."""
    return ":".join((oui[0:2], oui[2:4], oui[4:6], "00", "00", f"{ultimo:02x}"))


def _oui_colada(texto: str) -> str:
    """Só os dígitos hex, minúsculos: `E0:F6:B5` e `e0f6b5` viram a mesma coisa."""
    return "".join(ch for ch in texto.lower() if ch in "0123456789abcdef")


def test_a_marca_do_clone_vence_o_vid_que_ele_mente() -> None:
    """Em modo DS4 o clone é Sony por VID e por nome; só o MAC o entrega."""
    clone_em_modo_ds4 = {
        "vid": "054c",
        "pid": "05c4",
        "name": "Wireless Controller",
        "uniq": _mac_mascarado(OUI_DO_CLONE, 1),
        "bus": "bluetooth",
    }
    assert brand_of(clone_em_modo_ds4) == _BRAND_BY_OUI[OUI_DO_CLONE], (
        "o clone voltou a passar por Sony: por rádio o VID é mentira do "
        "firmware e a OUI do MAC é o único sinal que separa os dois"
    )


def test_sem_oui_conhecida_a_marca_cai_no_vid_como_sempre() -> None:
    """Não-regressão: quem não é clone continua sendo lido pelo VID."""
    pelo_cabo = {"vid": "057e", "pid": "2009", "name": "Pro Controller", "uniq": ""}
    assert brand_of(pelo_cabo) == "Nintendo"


def test_as_tres_reguas_da_casa_apontam_para_a_mesma_oui_do_genuino() -> None:
    """NOME HERDADO — o mapa de canais aponta para ESTE nó do pytest."""
    test_os_dois_scripts_de_no_sniff_concordam_sobre_quem_e_o_clone()
    test_a_faixa_desta_bancada_nao_voltou_a_ser_a_definicao_de_pro()


def test_os_dois_scripts_de_no_sniff_concordam_sobre_quem_e_o_clone() -> None:
    """Quem recusa o no-sniff é a faixa do CLONE, e ela é a mesma nos dois."""
    for script in (SCRIPT_MODO_ATIVO, SCRIPT_BORDA):
        texto = script.read_text(encoding="utf-8")
        achado = re.search(r"^OUIS_CLONE=\(([^)]*)\)", texto, re.MULTILINE)
        assert achado, f"`{script.name}` não declara mais `OUIS_CLONE`"
        faixas = {_oui_colada(m) for m in re.findall(r'"([^"]*)"', achado.group(1))}
        assert faixas == {OUI_DO_CLONE}, (
            f"`{script.name}` conhece as faixas de clone {sorted(faixas)} e o "
            f"produto conhece {{'{OUI_DO_CLONE}'}}"
        )


def test_a_faixa_desta_bancada_nao_voltou_a_ser_a_definicao_de_pro() -> None:
    """O fato substituído não pode voltar por uma constante nova."""
    for script in (SCRIPT_MODO_ATIVO, SCRIPT_BORDA):
        texto = script.read_text(encoding="utf-8")
        assert not re.search(r"^[ \t]*OUI_NINTENDO_REAL=", texto, re.MULTILINE), (
            f"`{script.name}` voltou a decidir 'quem é um Pro' por UMA faixa. A "
            "Nintendo tem 82 faixas MA-L registradas: uma amostra de tamanho um "
            "vira a definição, e o Pro de quem não mora aqui perde a cura"
        )


def test_a_regra_82_so_escopa_por_endereco_as_faixas_ja_vistas() -> None:
    """A rota que dispensa o nome cobre exatamente o que a casa já viu."""
    texto_regra = REGRA_NOSNIFF.read_text(encoding="utf-8")
    prefixos = {
        _oui_colada(m)
        for m in re.findall(r'ENV\{HID_UNIQ\}=="([0-9A-Fa-f:]+):\*"', texto_regra)
    }
    assert prefixos == set(OUIS_NINTENDO_VISTAS), (
        f"a regra udev 82 escopa {sorted(prefixos)} por endereço e o produto já "
        f"viu {sorted(OUIS_NINTENDO_VISTAS)} — a rota que não depende do nome "
        "tem de cobrir exatamente essas"
    )


def test_o_tratamento_do_genuino_nunca_alcanca_a_oui_do_clone() -> None:
    """O clone PRECISA do sniff — receber o no-sniff quebra a probe dele."""
    do_codigo = _oui_colada(NINTENDO_REAL_OUI)
    assert do_codigo != OUI_DO_CLONE, (
        "a OUI do genuíno virou a do clone: o tratamento de no-sniff passaria a "
        "matar a probe do 8BitDo (4 falhas / 0 sucessos, A/B de 23/07)"
    )
    texto_regra = REGRA_NOSNIFF.read_text(encoding="utf-8")
    assert OUI_DO_CLONE not in _oui_colada(
        "\n".join(
            ln for ln in texto_regra.splitlines() if not ln.lstrip().startswith("#")
        )
    ), "a regra 82 passou a casar a OUI do clone — é o veneno dele, não a cura"
