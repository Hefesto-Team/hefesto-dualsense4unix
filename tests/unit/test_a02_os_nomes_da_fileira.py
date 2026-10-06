"""O-BOTAO-ENTREGA-O-QUE-PROMETE-01 — os nomes da fileira do som são DELA."""
from __future__ import annotations

import pathlib
import re
import sys

import pytest

RAIZ = pathlib.Path(__file__).resolve().parents[2]
sys.path.insert(0, str(RAIZ / "src/hefesto_dualsense4unix/interface"))

DELA: dict[str, str] = {
    "jogo": "Efeitos do Jogo no Controle, Áudio do PC no PC",
    "junto": "Efeitos do Jogo e Áudio do PC no Controle",
    "nada": "Tudo no PC e Nada no Controle",
    "pc": "Tudo no Controle e Nada no PC",
}

DE_ONTEM = ("Efeitos do Jogo no Controle, Áudio da TV na TV",
            "Efeitos do Jogo e Áudio da TV no Controle",
            "Tudo na TV e Nada no Controle")

PALAVRAS_DA_TV = re.compile(r"\b(?:TV|televis[ãa]o)\b", re.I)

EM_ESPERA = "Só no controle"

NOMES_INTERNOS = ("sfx", "mix", "HDMI", "hdmi")

BOTAO = r'<button[^>]*data-rota="{rota}"[^>]*>([^<]*)</button>'


def _bancada() -> str:
    """O DESENHO que ela aprovou, pelo dono do caminho — nunca digitado."""
    from hefesto_dualsense4unix.interface import onde

    return (onde.BANCADA / "02-controles.html").read_text(encoding="utf-8")


def _rotulos(doc: str, rota: str) -> list[str]:
    return re.findall(BOTAO.format(rota=rota), doc)


@pytest.mark.parametrize("rota", sorted(DELA))
def test_o_desenho_diz_a_palavra_dela_em_todos_os_cartoes(rota: str) -> None:
    """Todo cartão da mesa, e não só o primeiro."""
    vistos = _rotulos(_bancada(), rota)

    assert vistos, (
        f"o botão `{rota}` sumiu do desenho: nenhum `data-rota={rota}` com "
        f"rótulo na bancada")
    assert set(vistos) == {DELA[rota]}, (
        f"o botão `{rota}` diz {sorted(set(vistos))} e a palavra dela de "
        f"20/09 é {DELA[rota]!r}")


def test_o_botao_de_espera_nao_voltou() -> None:
    """O rótulo de espera saiu com o ato que o justificava."""
    doc = _bancada()

    assert set(_rotulos(doc, "pc")) <= {DELA["pc"]}, (
        f"o botão `pc` diz {sorted(set(_rotulos(doc, 'pc')))} — o nome dele é "
        f"{DELA['pc']!r}, o espelho do terceiro")
    vivo = re.sub(r"<!--.*?-->|/\*.*?\*/", "", doc, flags=re.S)
    assert EM_ESPERA not in vivo, (
        f"o rótulo de espera {EM_ESPERA!r} voltou à TELA; o ato mudou e o "
        f"nome dela é {DELA['nada']!r}")


def test_os_nomes_de_ontem_sairam_da_tela() -> None:
    """«TV» virou «PC» — e a troca vale para os TRÊS nomes de ontem."""
    vivo = re.sub(r"<!--.*?-->|/\*.*?\*/", "", _bancada(), flags=re.S)
    vivo = vivo.split('<div class="nota">', 1)[0]
    voltaram = [nome for nome in DE_ONTEM if nome in vivo]
    assert not voltaram, f"o nome de ontem voltou à tela: {voltaram}"


def test_a_moldura_do_alto_falante_nao_diz_tv() -> None:
    """Nada que a moldura do alto-falante MOSTRA diz «TV» — rótulo, dica de"""
    doc = re.sub(r"<!--.*?-->", "", _bancada(), flags=re.S)
    molduras = re.findall(
        r'<div class="moldura"[^>]*data-bloco="alto-falante".*?<div class="rota quatro">.*?</div>',
        doc, flags=re.S)
    assert molduras, "o desenho perdeu a moldura do alto-falante (ou a fileira)"
    for moldura in molduras:
        lido = " ".join(re.findall(r'title="([^"]*)"', moldura))
        lido += " " + re.sub(r"<[^>]+>", " ", moldura)
        achado = PALAVRAS_DA_TV.search(lido)
        assert achado is None, (
            f"a moldura do alto-falante diz {achado.group(0)!r}: "
            f"…{lido[max(0, achado.start() - 60):achado.end() + 20]}…")


def test_a_fileira_tem_os_quatro_botoes_no_mesmo_numero_de_cartoes() -> None:
    """Os quatro são UM estado: nenhum pode faltar num cartão que tem os outros."""
    doc = _bancada()
    quantos = {rota: len(_rotulos(doc, rota)) for rota in DELA}

    assert len(set(quantos.values())) == 1, (
        f"a fileira do som não tem os quatro botões nos mesmos cartões: {quantos}")
    assert all(quantos.values()), f"a fileira do som sumiu do desenho: {quantos}"


@pytest.mark.parametrize("rota", ["jogo", "junto", "nada", "pc"])
def test_o_nome_interno_nao_chega_ao_botao(rota: str) -> None:
    """A tela nunca diz «sfx» nem «mix» — é metade da correção dela."""
    for rotulo in _rotulos(_bancada(), rota):
        for interno in NOMES_INTERNOS:
            assert interno not in rotulo, (
                f"o botão `{rota}` diz {rotulo!r}, e {interno!r} é nome "
                f"interno — a tela fala a língua dela")


@pytest.mark.parametrize("rota", sorted(DELA))
def test_o_gerador_guarda_a_palavra_dela(rota: str) -> None:
    """A constante que o `abaNN.py` emite, contra a palavra dela DIGITADA."""
    import aba02

    das_constantes = {
        "jogo": aba02.ROTULO_SO_OS_EFEITOS,
        "junto": aba02.ROTULO_EFEITOS_MAIS_O_PC,
        "nada": aba02.ROTULO_NADA_NO_CONTROLE,
        "pc": aba02.ROTULO_TUDO_NO_CONTROLE,
    }
    assert das_constantes[rota] == DELA[rota], (
        f"o gerador emite {das_constantes[rota]!r} para o botão `{rota}` e a "
        f"palavra dela é {DELA[rota]!r}")


def test_o_gerador_e_o_desenho_nao_divergiram() -> None:
    """A bancada é o que o gerador escreveu — e as duas envelhecem juntas."""
    import aba02

    doc = _bancada()
    for rota, constante in (("jogo", aba02.ROTULO_SO_OS_EFEITOS),
                            ("junto", aba02.ROTULO_EFEITOS_MAIS_O_PC),
                            ("nada", aba02.ROTULO_NADA_NO_CONTROLE),
                            ("pc", aba02.ROTULO_TUDO_NO_CONTROLE)):
        assert set(_rotulos(doc, rota)) == {constante}, (
            f"o gerador diz {constante!r} para o botão `{rota}` e o desenho "
            f"aprovado diz {sorted(set(_rotulos(doc, rota)))}")
