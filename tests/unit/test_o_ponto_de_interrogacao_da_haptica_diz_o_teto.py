"""O «?» da sensor háptico avisa o teto do perfil de bateria (A-TELA-PERGUNTA-AO-DONO-01, opção a).

Desde 02/10/2026 a Economia corta a háptica como corta a Força, e só o «?» da Força dizia a
frase do dono. O usuário escolheu (08/10/2026) a opção a: a frase vem logo depois do risco no
meio, antes do «Cinza quando…». A frase NÃO é digitada aqui: vem de
``app.telas.vibracao.DICA_DO_TETO_DA_MESA``.

A régua lê a FONTE (o gerador) e o ``mockup/05-vibracao.html``, que ele reescreve; não depende
do ``--publicar``, que é da costura.

Mordidas (09/10/2026, md5 antes e depois): tirar a frase da dica da sensor háptico no
``mockup/05-vibracao.html`` reprova a primeira; pô-la depois do «Cinza quando» reprova a ordem;
digitar a frase no ``aba05.py`` reprova a terceira. E a régua do próprio gerador (régua 10 do
``aba05.py``) recusa regerar a 05 sem a frase, de modo que o desenho nem chega a mudar.
"""
from __future__ import annotations

import pathlib
import re

from hefesto_dualsense4unix.app.telas.vibracao import DICA_DO_TETO_DA_MESA

RAIZ = pathlib.Path(__file__).resolve().parents[2]
MOCKUP = RAIZ / "mockup" / "05-vibracao.html"
GERADOR = RAIZ / "src" / "hefesto_dualsense4unix" / "interface" / "aba05.py"


def _dica(rotulo: str) -> str:
    """A dica de uma linha da 05: o ``data-dica`` do rótulo (a tela nova não tem «?»)."""
    html = MOCKUP.read_text(encoding="utf-8")
    achou = re.search(
        rf'<span class="sec-rot" data-dica="([^"]*)">{re.escape(rotulo)}</span>', html)
    assert achou, f"a dica de {rotulo!r} não está na 05"
    return re.sub(r"\s+", " ", achou.group(1))


def test_o_ponto_da_haptica_diz_o_teto_logo_depois_do_risco_no_meio() -> None:
    texto = _dica("Sensor háptico")
    assert DICA_DO_TETO_DA_MESA in texto
    assert (texto.index("O risco no meio é 50%")
            < texto.index(DICA_DO_TETO_DA_MESA) < texto.index("Cinza quando")), texto


def test_o_ponto_da_forca_segue_dizendo_o_teto() -> None:
    assert DICA_DO_TETO_DA_MESA in _dica("Força da vibração")


def test_a_frase_vem_do_dono_e_o_gerador_nao_a_digita() -> None:
    fonte = GERADOR.read_text(encoding="utf-8")
    assert "{DICA_DO_TETO_DA_MESA}" in fonte
    assert "pode impor um teto" not in fonte, "a frase do teto foi digitada no gerador"
