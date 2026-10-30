"""O install traz as extensões de fábrica de endereço depois do link; o ensaio só diz que faria."""
from __future__ import annotations

import re
from pathlib import Path

INSTALL = Path(__file__).resolve().parents[2] / "install.sh"


def _texto() -> str:
    return INSTALL.read_text(encoding="utf-8")


def test_o_install_chama_o_de_fabrica_pelo_binario_instalado() -> None:
    texto = _texto()
    assert re.search(r'"\$\{BIN_DIR\}/hefesto-dualsense4unix" mod de-fabrica', texto)


def test_o_de_fabrica_vem_depois_do_link_do_binario() -> None:
    texto = _texto()
    link = texto.index('ln -sf "${VENV_DIR}/bin/hefesto-dualsense4unix" "${BIN_DIR}/')
    chamada = texto.index("mod de-fabrica;")
    assert link < chamada


def test_o_ensaio_nao_traz_nada_e_a_falha_vira_aviso() -> None:
    texto = _texto()
    passo = texto[texto.index('step "5b"'):texto.index('step "6/11"')]
    assert '_faria "trazer e ligar as extensões de fábrica' in passo
    assert 'if [[ "${DRY_RUN:-0}" -eq 1 ]]' in passo.split("mod de-fabrica")[0]
    assert "warn " in passo
