#!/usr/bin/env python3
"""O controle que o Hefesto só VÊ entra no MESMO frame dos assentos — e não vira um."""
from __future__ import annotations

import pathlib
import re
import sys
from typing import Any

RAIZ = pathlib.Path(__file__).resolve().parents[2]
INTERFACE = RAIZ / "src" / "hefesto_dualsense4unix" / "interface"

from tests.conftest import exigir_gi_real

exigir_gi_real("importa `interface.pacotes`, que carrega o GTK")

for _caminho in (str(RAIZ / "src"), str(INTERFACE)):
    if _caminho not in sys.path:
        sys.path.insert(0, _caminho)

from hefesto_dualsense4unix.interface import onde
from pacotes import Contexto
from pacotes import a01_jogar as jogar

UM_8BITDO: dict[str, Any] = {
    "name": "8BitDo Pro 2", "vid": "2dc8", "pid": "6003",
    "bus": "bluetooth", "uniq": "e4:17:d8:00:00:2f",
    "driver": "hid-generic", "player_slot": 3,
}

UM_PRO_NO_CABO: dict[str, Any] = {
    "name": "Pro Controller", "vid": "057e", "pid": "2009",
    "bus": "usb", "driver": "hid-nintendo", "player_slot": 4,
}

VIVO: dict[str, Any] = {
    "connected": True, "native_mode": False,
    "gamepad_emulation": {"enabled": True, "flavor": "dualsense"},
    "paused": False,
}


def _ctx(externos: list[dict[str, Any]]) -> Contexto:
    return Contexto(state=dict(VIVO), mesa=[], conectados=[], externos=externos)


def _bloco_equilibrado(doc: str, abertura: str) -> str:
    """O elemento que começa em ``abertura`` e o seu fechamento, contados."""
    inicio = doc.find(abertura)
    assert inicio >= 0, f"não achei {abertura!r} na página"
    profundidade, i = 0, inicio
    while i < len(doc):
        abre, fecha = doc.find("<div", i), doc.find("</div>", i)
        assert fecha >= 0, f"{abertura!r} nunca fecha"
        if 0 <= abre < fecha:
            profundidade += 1
            i = abre + 4
            continue
        profundidade -= 1
        if profundidade == 0:
            return doc[inicio:fecha + 6]
        i = fecha + 6
    raise AssertionError(f"{abertura!r} nunca fecha")


def test_o_endereco_da_aba01_mora_dentro_da_grade_dos_assentos() -> None:
    """`data-campo="externos"` está DENTRO do `<div class="pecas">`."""
    doc = onde.pagina("01-jogar.html").read_text()
    grade = _bloco_equilibrado(doc, '<div class="pecas"')
    assert 'data-campo="externos" data-hef-alvo="html"' in grade


def test_o_endereco_da_aba08_mora_dentro_do_acordeao() -> None:
    """`data-campo="externos-lista"` está DENTRO do `<div class="gc">`."""
    doc = onde.pagina("08-conexoes.html").read_text()
    moldura = _bloco_equilibrado(doc, '<div class="gc">')
    assert 'data-campo="externos-lista" data-hef-alvo="html"' in moldura


def test_a_vaga_e_transparente_nas_duas_abas() -> None:
    """`display:contents` — sem ela os cartões caem TODOS numa célula só."""
    assert (".pecas .ext-vaga{display:contents}"
            in onde.pagina("01-jogar.html").read_text())
    assert (".gc .ext-vaga{display:contents}"
            in onde.pagina("08-conexoes.html").read_text())


def test_a_vaga_vazia_nao_ocupa_uma_celula() -> None:
    """O marcador `.nada` sai por `display:none`, e não pelo `:empty` da ressalva."""
    for arquivo, seletor in (("01-jogar.html", ".pecas .ext-vaga > .nada"),
                             ("08-conexoes.html", ".gc .ext-vaga > .nada")):
        assert f"{seletor}{{display:none}}" in onde.pagina(arquivo).read_text(), arquivo


def test_nenhum_aparelho_de_exemplo_nasce_dentro_da_moldura() -> None:
    """A moldura parada tem os assentos e mais nada."""
    grade = _bloco_equilibrado(onde.pagina("01-jogar.html").read_text(),
                               '<div class="pecas"')
    assert 'class="ext-cartao"' not in grade
    moldura = _bloco_equilibrado(onde.pagina("08-conexoes.html").read_text(),
                                 '<div class="gc">')
    assert 'class="ext-linha"' not in moldura


def _html_das_duas(externos: list[dict[str, Any]]) -> list[tuple[str, str]]:
    from pacotes import a08_conexoes as conexoes

    return [("01-jogar", jogar.pacote(_ctx(externos))["externos"]),
            ("08-conexoes", conexoes._html_dos_externos(_ctx(externos)))]


def test_o_externo_nao_ganha_nenhuma_marca_de_assento() -> None:
    """Nada de `data-controle`, `data-gesto`, `data-hef-alvo` nem `data-uniq`."""
    for aba, html in _html_das_duas([UM_8BITDO, UM_PRO_NO_CABO]):
        for atributo in ("data-controle", "data-gesto", "data-hef-alvo",
                         "data-uniq"):
            assert atributo not in html, f"{aba}: {atributo}"


def test_o_seletor_do_dono_do_piloto_nao_alcanca_o_externo() -> None:
    """`SELETOR_DO_DONO` lista os quatro lugares e o `data-uniq`, e mais nada."""
    from hefesto_dualsense4unix.interface import hefesto_vivo
    from hefesto_dualsense4unix.interface import pacotes as pac

    seletor = hefesto_vivo.SELETOR_DO_DONO
    for lugar in pac.TODOS_OS_LUGARES:
        assert f'[data-controle="{lugar}"]' in seletor
    for _aba, html in _html_das_duas([UM_8BITDO, UM_PRO_NO_CABO]):
        assert "ext-cartao" not in seletor and "ext-linha" not in seletor
        assert "data-controle" not in html


def test_apagar_os_lugares_sem_dono_continua_com_quatro() -> None:
    """A conta dos lugares vazios é dos QUATRO assentos, com externo ou sem."""
    from hefesto_dualsense4unix.interface import pacotes as pac

    carga: dict[str, Any] = {"colunas": {"p1": {"bateria": "100%"}}}
    pac.apagar_os_lugares_sem_dono(carga, ["p1"])
    assert set(carga["vazios"]) == {"p2", "p3", "p4"}
    assert set(carga["colunas"]) == pac.TODOS_OS_LUGARES
    # E O `player_slot` DO EXTERNO NÃO É UM ASSENTO: o 8BitDo desta régua é o
    assert "p3" in carga["vazios"]


def test_o_externo_nao_recebe_a_fileira_de_mascaras() -> None:
    """Máscara é escolha que o Hefesto escreve num aparelho que ele ADOTOU.

    Os três chips do assento (`DualSense`, `Xbox 360`, `Nintendo Pro`) são
    gesto: clicar grava. Desenhá-los num aparelho em que o daemon não escreve
    seria a tela oferecendo um ajuste que não existe — o defeito que esta casa
    chama de *"botão que diz aplicado sem ter aplicado"*.
    """
    for aba, html in _html_das_duas([UM_8BITDO, UM_PRO_NO_CABO]):
        assert 'class="mascara"' not in html, aba
        assert "Xbox 360" not in html, aba


def test_a_marca_distingue_o_externo_nas_duas_abas() -> None:
    """8BitDo pelo OUI, Nintendo pelo VID — e as duas vindas de `brand_of`."""
    from hefesto_dualsense4unix.app.actions.external_controllers import brand_of

    assert brand_of(UM_8BITDO) == "8BitDo"
    assert brand_of(UM_PRO_NO_CABO) == "Nintendo"
    for aba, html in _html_das_duas([UM_8BITDO, UM_PRO_NO_CABO]):
        assert "8BitDo" in html and "Nintendo" in html, aba


def test_a_marca_nao_e_digitada_em_lugar_nenhum_da_interface() -> None:
    """Nem `8BitDo` nem `Nintendo` são literal dos dois pacotes nem dos geradores.

    É a regra do DONO: a marca sai de `external_controllers.brand_of`, o único
    lugar da casa que sabe desmentir o VID que um clone mente. Uma segunda
    grafia faria uma das abas dizer *"Pro Controller"* sobre um 8BitDo no dia
    em que a outra aprendesse a desmenti-lo.

    O `Nintendo Pro` dos CHIPS DE MÁSCARA fica de fora da conta: ele é o nome de
    uma MÁSCARA do produto (como o jogo vê o controle), e não a marca de um
    aparelho. São duas coisas com nomes parecidos, e a régua tem de saber a
    diferença ou reprova a página inteira sobre o texto certo.

    A RÉGUA MEDE O QUE VAI À TELA, e não o texto dos arquivos — e as duas
    primeiras voltas dela reprovaram sobre PROSA: o comentário de `aba01.py` que
    explica a sprint cita a queixa dela (*"…e um 8BitDo…"*), e a legenda de
    `aba08.py` diz, com todas as letras, que Nintendo e 8BitDo são decisão dela.
    É a armadilha nomeada no `COMO-OLHAR-A-TELA.md` — *régua que casa um token
    em qualquer lugar do texto, em vez do campo que o significa*. Citação não é
    tela, e calar a citação para calar a régua seria apagar o registro.

    Então são dois alvos, e cada um responde metade:

    * o **miolo das duas páginas** (sem comentário e sem a legenda) — o desenho
      parado não nomeia marca nenhuma, porque nenhum aparelho é dele;
    * os **literais dos dois pacotes**, pelo `ast` (docstring de fora, e o
      parser junta a concatenação implícita antes de a régua olhar) — a marca
      chega por `_format_external_title`, e nunca digitada.
    """
    import ast

    for arquivo in ("01-jogar.html", "08-conexoes.html"):
        doc = onde.pagina(arquivo).read_text()
        miolo = doc.split('<div class="miolo">', 1)[-1].split('<div class="nota">', 1)[0]
        miolo = re.sub(r"<!--[\s\S]*?-->", "", miolo)
        miolo = miolo.replace("Nintendo Pro", "")
        assert "8BitDo" not in miolo, arquivo
        assert "Nintendo" not in miolo, arquivo

    for arquivo in ("pacotes/a01_jogar.py", "pacotes/a08_conexoes.py"):
        arvore = ast.parse((INTERFACE / arquivo).read_text(encoding="utf-8"))
        docstrings = set()
        for no in ast.walk(arvore):
            corpo = getattr(no, "body", None)
            if not corpo or not isinstance(
                    no, (ast.Module, ast.ClassDef, ast.FunctionDef,
                         ast.AsyncFunctionDef)):
                continue
            primeiro = corpo[0]
            if (isinstance(primeiro, ast.Expr)
                    and isinstance(primeiro.value, ast.Constant)
                    and isinstance(primeiro.value.value, str)):
                docstrings.add(id(primeiro.value))
        for no in ast.walk(arvore):
            if not isinstance(no, ast.Constant) or not isinstance(no.value, str):
                continue
            if id(no) in docstrings:
                continue
            texto = no.value.replace("Nintendo Pro", "")
            assert "8BitDo" not in texto, f"{arquivo}:{no.lineno}"
            assert "Nintendo" not in texto, f"{arquivo}:{no.lineno}"


def test_a_palavra_mesa_nao_entra_no_cartao_do_externo() -> None:
    """Ordem dela, no mesmo fôlego da escolha do frame."""
    from hefesto_dualsense4unix.interface.frases_que_ela_baniu import (
        primeiro_trecho_banido,
    )

    for aba, html in _html_das_duas([UM_8BITDO, UM_PRO_NO_CABO]):
        assert primeiro_trecho_banido(html) is None, aba


def test_sem_externo_nenhum_as_duas_abas_devolvem_vazio() -> None:
    """Zero aparelho, zero pixel — e as duas abas dizem isso de jeitos DIFERENTES."""
    from hefesto_dualsense4unix.interface import monta

    esperado = {"01": monta.NADA_A_DIZER, "08": ""}
    for aba, html in _html_das_duas([]):
        chave = "01" if "01" in str(aba) else "08"
        assert html == esperado[chave], (
            f"a aba {chave} devolveu {html!r} com a mesa sem externo nenhum; "
            f"esperado {esperado[chave]!r}")
