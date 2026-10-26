"""MODO-DE-CONEXAO-01 — o texto do modo não fala da máscara.

Desde a aba Jogar do todo (15/10/2026) a página não tem «?»: a dica de cada quadro e de
cada chip mora no `data-dica` dele.
"""
from __future__ import annotations

import html
import re
from pathlib import Path

RAIZ = Path(__file__).resolve().parents[2]
PUBLICADA = (
    RAIZ / "src" / "hefesto_dualsense4unix" / "interface"
    / "paginas"  # (noqa-acento)
    / "01-jogar.html"
)

DA_MASCARA = (
    "desenha",
    "botões do",
    "formato",
    "PlayStation",
    "Xbox 360",
    "Nintendo",
    "△ ○ ✕ ▢",
    "Y B A X",
)

O_CARTAO_GUARDA = ("desenho", "botões")

CHIPS_DE_MODO = {"modo-dualsense", "modo-xbox", "modo-steam", "modo-navegacao", "modo-nativo",
                 "modo-point-and-click"}


def _pagina() -> str:
    return PUBLICADA.read_text(encoding="utf-8")


def _texto(trecho: str) -> str:
    """Sem tags, sem entidades e com os espaços colapsados."""
    sem_tags = re.sub(r"<[^>]+>", " ", trecho)
    return re.sub(r"\s+", " ", html.unescape(sem_tags)).strip()


def _dica_do_quadro(titulo: str) -> str:
    """A dica do título do quadro cujo título é `titulo`."""
    achado = re.search(
        rf'<span class="quadro-titulo"([^>]*)>{re.escape(titulo)}</span>', _pagina())
    assert achado is not None, f"o quadro {titulo!r} sumiu da página publicada"
    dica = re.search(r'data-dica="([^"]*)"', achado.group(1))
    assert dica is not None, f"o quadro {titulo!r} ficou sem dica"
    return _texto(dica.group(1))


def _dicas_dos_chips_de_modo() -> dict[str, str]:
    """`{data-gesto: data-dica}` de cada chip de modo."""
    dicas: dict[str, str] = {}
    for tag in re.findall(r'<span[^>]*data-gesto="modo-[^"]*"[^>]*>', _pagina(), re.S):
        gesto = re.search(r'data-gesto="([^"]+)"', tag)
        titulo = re.search(r'data-dica="([^"]*)"', tag)
        assert gesto is not None
        dicas[gesto.group(1)] = html.unescape(titulo.group(1)) if titulo else ""
    return dicas


def _vocabulario_da_mascara_em(texto: str) -> list[str]:
    dobrado = texto.casefold()
    return [termo for termo in DA_MASCARA if termo.casefold() in dobrado]


def test_as_dicas_dos_chips_de_modo_nao_falam_da_mascara() -> None:
    dicas = _dicas_dos_chips_de_modo()
    assert set(dicas) == CHIPS_DE_MODO, f"a fileira de modos mudou: {sorted(dicas)}"
    sem_dica = sorted(g for g, t in dicas.items() if not t.strip())
    assert not sem_dica, f"chip de modo sem dica: {sem_dica}"
    falam = {g: _vocabulario_da_mascara_em(t) for g, t in dicas.items()}
    falam = {g: termos for g, termos in falam.items() if termos}
    assert not falam, (
        "a dica do modo voltou a falar da máscara — o texto é o do cartão: "
        + "; ".join(f"{g}: {termos} em {dicas[g]!r}" for g, termos in sorted(falam.items()))
    )


def test_a_dica_do_quadro_modo_nao_fala_da_mascara() -> None:
    dica = _dica_do_quadro("Modo")
    assert "chega ao jogo" in dica, f"a dica do Modo deixou de dizer o que é o modo: {dica!r}"
    termos = _vocabulario_da_mascara_em(dica)
    assert not termos, f"a dica do quadro Modo fala da máscara ({termos}): {dica!r}"


def test_o_assunto_da_mascara_continua_na_dica_dos_cartoes() -> None:
    dica = _dica_do_quadro("O controle é visto como:")
    faltam = [termo for termo in O_CARTAO_GUARDA if termo not in dica]
    assert not faltam, (
        f"a dica dos cartões perdeu o vocabulário da máscara ({faltam}) — tirar "
        f"o assunto do modo não pode apagá-lo da tela: {dica!r}"
    )
