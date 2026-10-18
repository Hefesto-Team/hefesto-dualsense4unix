"""O desfazer do Proton fixado e do Vulkan não é da tela e segue vivo fora dela.

OS-GESTOS-SEM-ELEMENTO-DAS-ABAS-SISTEMA-E-CONEXOES-SAEM-01 (17/10/2026): os gestos `fixar-proton`
e `corrigir-vulkan` destravavam e devolviam; o interruptor das correções não desfaz nenhum dos
dois (o desenho do todo, mudança 8). A volta mora em `integrations/`: o `proton_pin.py --unlock`,
que o `uninstall.sh` chama, e `gravar_camadas_da_steam_fora(False)`.

MORDIDA: tire o `--unlock` do `uninstall.sh`, o `add_argument("--unlock")` do `proton_pin.py` ou o
`unlink` do ramo `False` do `camadas_vulkan.py` e a prova respectiva reprova.
"""
from __future__ import annotations

import re
from pathlib import Path

from hefesto_dualsense4unix.integrations import camadas_vulkan as cv
from hefesto_dualsense4unix.integrations import proton_pin

RAIZ = Path(__file__).resolve().parents[2]


def test_o_uninstall_chama_o_unlock_do_proton_pin() -> None:
    """Sem a tela, o `uninstall.sh` é quem destrava o Proton pinado."""
    texto = (RAIZ / "uninstall.sh").read_text(encoding="utf-8")
    assert re.search(r'python3 "\$\{PROTON_PIN_PY\}" --unlock', texto), (
        "o uninstall.sh perdeu o `proton_pin.py --unlock`: o Proton pinado ficaria travado")


def test_o_proton_pin_tem_o_unlock_e_ele_chega_ao_destravador() -> None:
    """A opção existe e o comando dela chama `unlock_games_from_pinned_proton`."""
    fonte = Path(proton_pin.__file__).read_text(encoding="utf-8")
    assert '"--unlock"' in fonte, "o `proton_pin.py` perdeu a opção `--unlock`"
    corpo = fonte[fonte.index("def _cmd_unlock("):]
    corpo = corpo[:corpo.index("\ndef ", 10)]
    assert "unlock_games_from_pinned_proton(" in corpo, (
        "o `_cmd_unlock` deixou de chamar o destravador")
    assert callable(proton_pin.unlock_games_from_pinned_proton)


def test_a_volta_das_camadas_apaga_a_escolha_e_a_steam_volta_a_decidir(tmp_path: Path) -> None:
    """`gravar_camadas_da_steam_fora(False)` desfaz o que o interruptor gravou com `True`."""
    cv.gravar_camadas_da_steam_fora(True, config_home=tmp_path)
    assert cv.camadas_da_steam_fora(tmp_path), "a escolha não ficou gravada"
    cv.gravar_camadas_da_steam_fora(False, config_home=tmp_path)
    assert not cv.camadas_da_steam_fora(tmp_path), (
        "a volta das camadas não desfez a escolha: o caminho de volta quebrou")
    assert not cv.caminho_da_escolha(tmp_path).exists()
