"""A extensão desligada ainda não publicou ``presentes``: a janela mostra a opção com ``@presente``.

Mordida: sem o ``None`` dos presentes que ninguém publicou, a janela da extensão desligada abre com
a aba Efeitos vazia, e ``test_sem_estado_publicado_a_linha_do_presente_aparece`` reprova.
"""

from __future__ import annotations

from typing import Any

from hefesto_dualsense4unix.mods import opcoes
from hefesto_dualsense4unix.mods.manifesto import Manifesto
from tests.unit.test_a_aba_lancadores_ganha_as_modificacoes import ctx, lar  # noqa: F401
from tests.unit.test_a_janela_da_extensao_age_e_gere_os_aparelhos import _manifesto, _Ponte
from tests.unit.test_a_janela_da_extensao_mostra_o_que_o_modo_imersao_pede import (  # noqa: F401
    PULSO,
    _linhas_das_opcoes,
    janela,
)


def test_presentes_sem_publicar_mostram_e_lista_publicada_decide() -> None:
    m = Manifesto.model_validate(_manifesto(opcoes=[PULSO]))
    assert opcoes.aparecem(m, {}, None) == {"efeito-pulso"}
    assert opcoes.aparecem(m, {}, ["pulso"]) == {"efeito-pulso"}
    assert opcoes.aparecem(m, {}, []) == frozenset()


def test_sem_estado_publicado_a_linha_do_presente_aparece(janela: Any) -> None:  # noqa: F811
    _a07, abrir = janela
    assert "efeito-pulso" in _linhas_das_opcoes(abrir(_Ponte({}))), \
        "a extensão desligada abriu a janela sem a opção do efeito"
    assert "efeito-pulso" not in _linhas_das_opcoes(abrir(_Ponte({"ligado": True,
                                                                   "presentes": []})))
