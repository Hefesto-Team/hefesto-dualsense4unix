#!/usr/bin/env python3
"""Duas unidades NUNCA mostram a mesma cor — nem no mesmo perfil e estilo."""

from __future__ import annotations

import pathlib

import pytest

from hefesto_dualsense4unix.profiles import estilos_de_jogo as estilos


def _pior(cores) -> int:
    return min(estilos._distancia(cores[i], cores[j])
               for i in range(len(cores)) for j in range(i + 1, len(cores)))


@pytest.mark.parametrize("estilo", [e for e in estilos.ESTILOS if e.chave != "personalizado"],
                         ids=lambda e: e.chave)
def test_as_quatro_saem_distintas_em_todo_estilo(estilo) -> None:
    """As quatro unidades daquele estilo, e nenhuma igual a outra."""
    cores = estilos.as_quatro(estilo)
    assert len(set(cores)) == 4, f"{estilo.rotulo}: cores repetidas em {cores}"
    assert _pior(cores) >= estilos.DISTANCIA_MINIMA, (
        f"{estilo.rotulo}: as duas mais próximas ficam a {_pior(cores)}, e o "
        f"mínimo é {estilos.DISTANCIA_MINIMA}")


def test_toda_receita_rende_quatro_sem_levantar() -> None:
    """Nenhuma família da tabela pode ser escura ou branca demais."""
    ruins = []
    for e in estilos.ESTILOS:
        if e.chave == "personalizado":
            continue
        try:
            estilos.as_quatro(e)
        except ValueError as x:
            ruins.append(f"{e.rotulo}: {x}")
    assert not ruins, "receita(s) com família que não rende quatro:\n  " + "\n  ".join(ruins)


def test_as_quatro_variam_em_matiz_e_nao_so_em_luz() -> None:
    """A variação tem de ser de COR, e não uma escala de cinza da mesma cor."""
    import colorsys

    ruins = []
    for e in estilos.ESTILOS:
        if e.chave == "personalizado":
            continue
        matizes = [colorsys.rgb_to_hls(*(c / 255 for c in cor))[0]
                   for cor in estilos.as_quatro(e)]
        espalhamento = max(
            min(abs(a - b), 1 - abs(a - b)) for a in matizes for b in matizes)
        if espalhamento < 0.02:
            ruins.append(f"{e.rotulo}: as quatro cabem em {espalhamento*360:.0f} "
                         "graus de matiz — é a mesma cor em quatro brilhos")
    assert not ruins, (
        "a variação virou escala de luminância, e num LED difuso isso não "
        "separa:\n  " + "\n  ".join(ruins))


def test_uma_familia_que_nao_rende_levanta() -> None:
    """Devolver um par colidido em silêncio seria o defeito inteiro."""
    branco = estilos.Estilo("x", "Teste", None, "balanceado", (250, 250, 250), 1.0, "")
    with pytest.raises(ValueError, match="não separa quatro unidades"):
        estilos.as_quatro(branco)


def test_o_personalizado_recusa_dizendo_por_que() -> None:
    """`Personalizado` não escolhe cor, e perguntar a dele é erro de quem chama."""
    with pytest.raises(ValueError, match="não escolhe cor"):
        estilos.as_quatro("personalizado")


@pytest.mark.parametrize("fora", [0, 5, -1])
def test_jogador_fora_da_mesa_recusa(fora: int) -> None:
    """A mesa é 1..4. Um índice fora não vira a cor do vizinho."""
    with pytest.raises(ValueError, match="fora da mesa"):
        estilos.cor_da_unidade("fps", fora)


def test_todo_gatilho_da_receita_e_um_modo_real() -> None:
    """A chave do gatilho sai da lista que a aba Gatilhos oferece."""
    import pathlib
    import re

    pagina = (pathlib.Path(__file__).resolve().parents[2]
              / "src/hefesto_dualsense4unix/interface/paginas/03-gatilhos.html")
    m = re.search(r'<select class="modo"[^>]*>(.*?)</select>',
                  pagina.read_text(encoding="utf-8"), re.S)
    assert m, "a página Gatilhos não tem lista de modo — a régua ficaria cega"
    reais = set(re.findall(r'<option value="([^"]*)"', m.group(1)))

    ruins = [f"{e.rotulo} -> {e.gatilho!r}" for e in estilos.ESTILOS
             if e.gatilho is not None and e.gatilho not in reais]
    assert not ruins, (
        "receita(s) apontando para modo de gatilho que não existe:\n  "
        + "\n  ".join(ruins) + f"\nos reais: {sorted(reais)}")


def test_todo_degrau_de_vibracao_da_receita_e_real() -> None:
    """O degrau sai de `RUMBLE_POLICY_MULT`, que é o dono deles."""
    from hefesto_dualsense4unix.daemon.subsystems.rumble import RUMBLE_POLICY_MULT

    ruins = [f"{e.rotulo} -> {e.vibracao!r}" for e in estilos.ESTILOS
             if e.vibracao and e.vibracao not in RUMBLE_POLICY_MULT]
    assert not ruins, (
        "receita(s) com degrau de vibração inexistente:\n  " + "\n  ".join(ruins)
        + f"\nos reais: {sorted(RUMBLE_POLICY_MULT)}")


def _opcoes_do_estilo(pagina: pathlib.Path) -> set[str] | None:
    """As opções do `<select>` do Estilo de Jogo numa página, sem o travessão."""
    import re

    t = pagina.read_text(encoding="utf-8")
    m = re.search(r'<select[^>]*(?:data-hef|data-campo)="editor\.estilo"[^>]*>(.*?)</select>',
                  t, re.S)
    if not m:
        return None
    da_tela = {x.strip() for x in re.findall(r'<option[^>]*>([^<]*)</option>', m.group(1))}
    da_tela.discard("—")
    return da_tela


def _a_10_esta_em_trabalho() -> bool:
    """A aba Perfis está declarada em trabalho na bancada (`mockup/DIVERGENCIAS.md`)?"""
    from hefesto_dualsense4unix.interface import onde

    arquivo = onde.BANCADA / "DIVERGENCIAS.md"
    if not arquivo.exists():
        return False
    corpo = arquivo.read_text(encoding="utf-8").split("\n---\n", 1)[-1]
    return "\n## 10-perfis.html" in f"\n{corpo}"


def test_a_lista_da_tela_e_a_das_receitas_batem() -> None:
    """Os rótulos das receitas são os que o `<select>` da aba Perfis oferece."""
    from hefesto_dualsense4unix.interface import onde

    das_receitas = {e.rotulo for e in estilos.ESTILOS}
    alvos = [onde.pagina("10-perfis.html")]
    if not _a_10_esta_em_trabalho():
        alvos.append(onde.pagina("10-perfis.html", publicado=True))
    for pagina in alvos:
        da_tela = _opcoes_do_estilo(pagina)
        assert da_tela is not None, f"o `<select>` do estilo sumiu de {pagina}"
        assert da_tela == das_receitas, (
            f"{pagina.parent.name}/{pagina.name}\n"
            f"só na tela: {sorted(da_tela - das_receitas)}\n"
            f"só nas receitas: {sorted(das_receitas - da_tela)}")
