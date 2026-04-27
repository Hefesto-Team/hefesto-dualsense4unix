"""Testes de `hefesto_dualsense4unix.profiles.slug.slugify` — tabela canônica da sprint."""
from __future__ import annotations

import pytest

from hefesto_dualsense4unix.profiles.slug import slugify


def test_slug_acao_acentuado():  # slug literal ASCII (noqa-acento)
    assert slugify("Ação") == "acao"  # slug literal ASCII (noqa-acento)


def test_slug_navegacao():
    assert slugify("Navegação") == "navegacao"


def test_slug_fps_maiusculas():
    assert slugify("FPS") == "fps"


def test_slug_meu_perfil_espaco():
    assert slugify("Meu Perfil") == "meu_perfil"


def test_slug_corrida_maxima():
    assert slugify("Corrida Máxima") == "corrida_maxima"


def test_slug_sao_jose():
    assert slugify("São José") == "sao_jose"


def test_slug_umlaut_alemao():
    assert slugify("über") == "uber"


def test_slug_remove_barra():
    assert slugify("a/b") == "ab"


def test_slug_vazio_falha():
    with pytest.raises(ValueError):
        slugify("")


def test_slug_so_espacos_falha():
    with pytest.raises(ValueError):
        slugify("   ")


def test_slug_so_simbolos_falha():
    with pytest.raises(ValueError):
        slugify("???")


def test_slug_trim_underscores_borda():
    assert slugify("_foo_bar_") == "foo_bar"


def test_slug_colapsa_underscores():
    assert slugify("a__b") == "a_b"


def test_slug_traco_vira_underscore():
    assert slugify("meu-perfil") == "meu_perfil"


def test_slug_mistura_espaco_e_traco():
    assert slugify("meu - perfil") == "meu_perfil"


def test_slug_emojis_produzem_vazio_falha():
    # Emojis gráficos isolados não têm decomposição NFKD para ASCII.
    with pytest.raises(ValueError):
        slugify("\U0001F680\U0001F3AE")


def test_slug_preserva_digitos():
    assert slugify("Perfil 2024") == "perfil_2024"
