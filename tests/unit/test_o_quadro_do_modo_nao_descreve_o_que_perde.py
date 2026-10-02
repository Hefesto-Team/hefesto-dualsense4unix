"""O quadro "Modo" não mora mais na aba Perfis — e as duas frases têm dono."""
from __future__ import annotations

from tests.conftest import exigir_gi_real

exigir_gi_real("test_o_quadro_do_modo_nao_descreve_o_que_perde: importa código da janela GTK")

import pytest

from hefesto_dualsense4unix.interface import onde

PAGINA = "10-perfis.html"  # (noqa-acento) nome de arquivo

_ESTADO_DO_RADIO_FRAGIL = {
    "controllers": [{"uniq": "aabbcc000001", "connected": True, "transport": "bt"}],
    "gamepad_emulation": {"enabled": True, "flavor": "dualsense"},
    "native_bt_fragil": True,
    "native_mode": {"enabled": True},
}

_MARCAS_DO_QUADRO = (
    ('<div class="campo modo">', "o bloco da fileira no editor"),
    ('data-modo="', "o atributo que dizia qual dos quatro"),
    ('data-hef="editor.modo"', "o endereço que o produto pintava"),
    (".campo.modo", "a regra de CSS da fileira"),
)


def _pagina(publicado: bool) -> str:
    return onde.pagina(PAGINA, publicado=publicado).read_text(encoding="utf-8")


@pytest.mark.parametrize("publicado", [False, True], ids=["bancada", "publicada"])
@pytest.mark.parametrize("marca,o_que_e", _MARCAS_DO_QUADRO,
                         ids=[m for m, _ in _MARCAS_DO_QUADRO])
def test_o_quadro_do_modo_nao_esta_na_aba_perfis(
    publicado: bool, marca: str, o_que_e: str
) -> None:
    """Ordem dela, 11/09/2026 — e as duas páginas respondem igual."""
    assert marca not in _pagina(publicado), (
        f"{o_que_e} voltou à aba Perfis ({'publicada' if publicado else 'bancada'}) "
        f"— {marca!r}. O quadro «Modo» saiu do editor por ordem dela em "
        f"11/09/2026: *\"em perfis ainda aparece modo. Isso deve aparecer só na "
        f"aba jogar.\"* Se a decisão mudou, ela muda aqui primeiro."
    )


