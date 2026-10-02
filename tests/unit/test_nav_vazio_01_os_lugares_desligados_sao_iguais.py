"""NAV-VAZIO-01 — os lugares desligados são IGUAIS, com qualquer das duas palavras."""

from __future__ import annotations

import pathlib
import re

import pytest

from hefesto_dualsense4unix import interface


def _pasta() -> pathlib.Path:
    return pathlib.Path(interface.__file__).parent


def _folha_da_navegacao() -> str:
    """O CSS que a aba Navegação publica — do PUBLICADO, que é o que ela vê."""
    arq = _pasta() / "paginas" / "06-navegacao.html"  # noqa-acento: `paginas` é o nome da PASTA
    assert arq.is_file(), f"a página publicada não está em {arq}"
    return arq.read_text(encoding="utf-8")


def _palavra_que_o_piloto_escreve() -> str:
    """A classe que o passo ``vazios`` do piloto põe num lugar sem dono."""
    fonte = (_pasta() / "hefesto_vivo.py").read_text(encoding="utf-8")
    inicio = fonte.find("p.vazios || []")
    assert inicio > 0, (
        "não achei o passo `vazios` do piloto em `hefesto_vivo.py` — ele mudou "
        "de forma, e esta régua precisa ser reapontada POR SÍMBOLO"
    )
    janela = fonte[inicio : inicio + 2000]
    achadas = re.findall(r"classList\.add\('([a-z-]+)'\)", janela)
    assert achadas, (
        "o passo `vazios` não adiciona classe nenhuma — ou ele parou de marcar "
        "o lugar sem dono, ou a forma mudou"
    )
    return achadas[0]


def test_a_folha_conhece_a_palavra_que_o_piloto_escreve() -> None:
    """O defeito inteiro em uma asserção."""
    palavra = _palavra_que_o_piloto_escreve()
    folha = _folha_da_navegacao()
    assert f".nav-ctl.{palavra}" in folha, (
        f"o piloto marca o lugar sem dono com `.{palavra}`, e a folha da "
        f"Navegação não desenha essa classe. É o defeito de 04/09 outra vez: "
        f"duas palavras para o mesmo estado, e o lugar esvaziado em execução "
        f"fica com cara diferente do que nasceu vazio"
    )


def test_a_moldura_vale_para_as_duas_palavras() -> None:
    """A borda é o que ela viu diferente — não a cor, que já fora curada."""
    folha = _folha_da_navegacao()
    palavra = _palavra_que_o_piloto_escreve()

    regras = [
        linha for linha in folha.splitlines()
        if "border:1px solid var(--border-forte)" in linha and "nav-ctl" in linha
    ]
    assert regras, (
        "nenhuma regra da Navegação dá moldura ao lugar vazio — a borda voltou "
        "a depender de `var(--plastico)`, que num lugar sem controle é "
        "indefinido e derruba a declaração INTEIRA, em silêncio"
    )
    alcance = "\n".join(regras)
    for p in ("vazia", palavra):
        assert f".nav-ctl.{p}" in alcance, (
            f"a moldura do lugar vazio não alcança `.nav-ctl.{p}`. Os lugares "
            f"desligados têm de ficar IGUAIS — queixa dela de 17/09/2026, com "
            f"o P2 (esvaziado em execução) contra o P3 e o P4 (vazios de "
            f"nascença)"
        )


@pytest.mark.parametrize(
    "propriedade",
    ["color:var(--linha)", "border:1px solid var(--border-forte)"],
)
def test_nenhuma_regra_do_vazio_ficou_so_com_uma_palavra(propriedade: str) -> None:
    """Varredura: toda regra que desenha o vazio cobre as duas palavras."""
    folha = _folha_da_navegacao()
    palavra = _palavra_que_o_piloto_escreve()
    for linha in folha.splitlines():
        if propriedade not in linha or "nav-ctl" not in linha:
            continue
        assert f".nav-ctl.{palavra}" in linha or ".nav-ctl.vazia" not in linha, (
            f"esta regra desenha o lugar vazio só para uma das palavras:\n"
            f"  {linha.strip()[:160]}\n"
            f"o piloto escreve `.{palavra}`; a folha precisa cobrir as duas"
        )


def test_a_regua_sabe_reprovar(tmp_path: pathlib.Path) -> None:
    """A MORDIDA, sem tocar no produto."""
    folha_doente = (
        "  .nav-ctl.vazia{border:1px solid var(--border-forte);"
        "background:transparent}\n"
        "  .nav-ctl.vazia .nav-rot{color:var(--linha)}\n"
    )
    palavra = "off"

    regras = [
        linha for linha in folha_doente.splitlines()
        if "border:1px solid var(--border-forte)" in linha and "nav-ctl" in linha
    ]
    assert regras, "a folha de mentira precisa ter a moldura, senão mede outra coisa"
    alcance = "\n".join(regras)

    assert ".nav-ctl.vazia" in alcance, "controle: o `.vazia` está lá"
    assert f".nav-ctl.{palavra}" not in alcance, (
        "a folha DOENTE não pode conhecer a palavra do piloto — se conhecesse, "
        "esta mordida não estaria mordendo o defeito de 04/09"
    )

    de_verdade = "\n".join(
        linha for linha in _folha_da_navegacao().splitlines()
        if "border:1px solid var(--border-forte)" in linha and "nav-ctl" in linha
    )
    assert f".nav-ctl.{_palavra_que_o_piloto_escreve()}" in de_verdade
