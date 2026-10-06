#!/usr/bin/env python3
"""A régua que O usuário pediu: um campo que continua exibindo o valor do mockup."""
from __future__ import annotations

import pathlib
import re
import sys

import pytest

RAIZ = pathlib.Path(__file__).resolve().parents[2]
sys.path.insert(0, str(RAIZ / "src"))

from hefesto_dualsense4unix.interface import (
    onde,
    regua_do_mockup as regua,
)

GATILHOS = "03-gatilhos.html"


def _texto(pagina: str) -> str:
    return onde.pagina(pagina, publicado=True).read_text(encoding="utf-8")


def _paginas() -> list[str]:
    return [p.name for p in onde.paginas(publicado=True) if p.name[:2].isdigit()]


def test_as_dez_paginas_publicadas_tem_endereco_de_campo():
    """Nenhuma das dez pode voltar vazia — vazio aqui seria a régua cega."""
    for pagina in _paginas():
        campos = regua._campos_cravados(_texto(pagina))
        assert campos, (
            f"{pagina} não devolveu endereço de campo nenhum. Ou a página perdeu "
            f"os `data-campo`, ou o parser parou de enxergá-los — e nos dois "
            f"casos a régua do mockup passa a medir o vácuo.")


def test_os_quatro_numeros_congelados_da_gatilhos_estao_no_arquivo():
    """Os valores do caso, lidos do HTML publicado — não digitados aqui."""
    campos = {c.endereco: c.valor for c in regua._campos_cravados(_texto(GATILHOS))}
    assert campos["p1·aj-nome-e-0"] == "Força"
    assert campos["p1·aj-val-e-0"] == "7"
    assert campos["p1·aj-nome-e-1"] == "Frequência"
    assert campos["p1·aj-val-e-1"] == "4"
    assert campos["p1·aj-val-e-2"] == "25"
    assert campos["p1·aj-val-e-3"] == "230"


def test_o_mesmo_endereco_em_colunas_diferentes_nao_se_confunde():
    """`aj-val-e-0` vale 7 na coluna do P1 e 3 na do P2 — são campos distintos."""
    campos = {c.endereco: c.valor for c in regua._campos_cravados(_texto(GATILHOS))}
    assert campos["p1·aj-val-e-0"] == "7"
    assert campos["p2·aj-val-e-0"] == "3"


def test_uma_option_sem_value_vale_o_texto_dela():
    """Contrato do HTML, e ignorá-lo custou uma cegueira medida em 02/09/2026."""
    campos = regua._campos_cravados(
        '<select data-campo="x" data-hef-alvo="valor">'
        '<option>Wi-Fi</option><option>Teclado</option></select>')
    assert [c.valor for c in campos] == ["Wi-Fi"]


def test_a_largura_e_lida_como_o_navegador_a_devolve():
    """`width:100.0%` no arquivo é `100%` no `el.style.width` — e 66.7% fica."""
    campos = regua._campos_cravados(
        '<span data-campo="a" data-hef-alvo="largura" style="width:100.0%"></span>'
        '<span data-campo="b" data-hef-alvo="largura" style="width:66.7%"></span>')
    assert [c.valor for c in campos] == ["100%", "66.7%"]


def test_a_gatilhos_congelada_e_acusada():
    """A TELA IGUAL AO ARQUIVO, e nenhum pacote declarando: é MOCKUP."""
    cravados = regua._campos_cravados(_texto(GATILHOS))
    vereditos = regua._classificar(cravados, [c.valor for c in cravados], {})
    contas = regua._contar(vereditos)
    assert contas[regua.PRODUTO] == 0, (
        "com a tela idêntica ao arquivo e pacote nenhum declarando, NADA pode "
        "aparecer como PRODUTO. Se aparece, a régua não está comparando com o "
        "arquivo — e é exatamente esse o defeito que ela existe para pegar.")
    assert contas[regua.MOCKUP] == len(cravados)

    presos = {v.campo.endereco for v in vereditos if v.classe == regua.MOCKUP}
    for endereco in ("p1·aj-val-e-0", "p1·aj-val-e-1",
                     "p1·aj-val-e-2", "p1·aj-val-e-3"):
        assert endereco in presos, (
            f"{endereco} tinha de ser acusado: é um dos quatro números que a aba "
            f"Gatilhos mostra com o perfil dela dizendo modo='Off' params=[].")


def test_um_campo_que_a_tela_mudou_e_produto():
    cravados = regua._campos_cravados('<span data-campo="bateria">64%</span>')
    (v,) = regua._classificar(cravados, ["85%"], {})
    assert v.classe == regua.PRODUTO
    assert "64%" in v.nota and "85%" in v.nota


def test_o_pacote_declarar_o_mesmo_valor_da_indecidivel():
    """O limite honesto do instrumento, e ele é DITO em vez de disfarçado."""
    cravados = regua._campos_cravados('<span data-campo="bateria">85%</span>')
    (v,) = regua._classificar(cravados, ["85%"], {("", "bateria"): "85%"})
    assert v.classe == regua.INDECIDIVEL
    assert "não separa" in v.nota


def test_o_pacote_declarar_outro_valor_e_endereco_morto():
    """O pior dos casos: o pacote monta o valor e escreve onde a página não tem."""
    cravados = regua._campos_cravados('<span data-campo="bateria">64%</span>')
    (v,) = regua._classificar(cravados, ["64%"], {("", "bateria"): "85%"})
    assert v.classe == regua.MOCKUP
    assert "ENDEREÇO MORTO" in v.nota


def test_o_vazio_declarado_vira_travessao_como_na_tela():
    """`escrever()` põe travessão no vazio; a régua tem de saber disso."""
    assert regua._como_a_tela_escreveria(None) == regua.TRAVESSAO
    assert regua._como_a_tela_escreveria("") == regua.TRAVESSAO
    assert regua._como_a_tela_escreveria(85) == "85"


def test_listas_de_tamanhos_diferentes_nao_se_comparam():
    with pytest.raises(ValueError, match="tamanhos diferentes"):
        regua._classificar(regua._campos_cravados('<b data-campo="x">1</b>'), [], {})


def test_um_bloco_trocado_pelo_produto_nao_vira_medicao_errada():
    """A pintura troca blocos inteiros — e alinhar por posição casaria vizinhos."""
    cravados = regua._campos_cravados(
        '<b data-campo="nome">Um</b><b data-campo="nome">Dois</b>'
        '<b data-campo="nome">Três</b>')
    vivos = [("nome", "", "texto", "Mortal Kombat"), ("nome", "", "texto", "Universal")]
    alinhados, nasceram = regua._alinhar(cravados, vivos)
    assert alinhados == ["Mortal Kombat", "Universal", regua.SUMIU]
    assert nasceram == []
    vereditos = regua._classificar(cravados, alinhados, {})
    assert [v.classe for v in vereditos] == [regua.PRODUTO] * 3
    assert "TROCADO" in vereditos[-1].nota


def test_um_endereco_que_nasce_na_tela_e_relatado():
    cravados = regua._campos_cravados('<b data-campo="nome">Um</b>')
    _, nasceram = regua._alinhar(
        cravados, [("nome", "", "texto", "A"), ("nome", "", "texto", "B")])
    assert nasceram == [("nome", "")]


def test_a_lista_de_cliques_alcanca_o_botao_que_ninguem_ligou():
    """O defeito de 29/08/2026, e ele é o motivo de a lista ser a UNIÃO."""
    da_pagina = [regua._Gesto("botao-novo", "p1")]
    alvos, pulados = regua._alvos_a_clicar(da_pagina, set(), "x.html", set())
    assert alvos == ["botao-novo"]
    assert regua._cobertura_dos_gestos(da_pagina, set(), alvos, pulados) == []


def test_a_lista_de_cliques_alcanca_o_gesto_que_a_pagina_enderecou_por_papel():
    """A outra metade da união, e sem ela a aba Vibração fica sem um clique."""
    registrados = {"forca", "testar", "parar"}
    alvos, pulados = regua._alvos_a_clicar([], registrados, "05-vibracao.html", set())
    assert sorted(alvos) == ["forca", "parar", "testar"]
    assert regua._cobertura_dos_gestos([], registrados, alvos, pulados) == []


def test_um_gesto_que_ficou_de_fora_reprova_a_cobertura():
    """Zero é a única saída aceitável — e a régua tem de saber acusar a si mesma."""
    da_pagina = [regua._Gesto("a", ""), regua._Gesto("b", "")]
    assert regua._cobertura_dos_gestos(da_pagina, set(), ["a"], []) == ["b"]


def test_os_perigosos_saem_da_lista_mas_contam_como_cobertos():
    """Pular não é esquecer: quem pula DIZ que pulou, e por quê."""
    da_pagina = [regua._Gesto("desligar", ""), regua._Gesto("retomar", "")]
    alvos, pulados = regua._alvos_a_clicar(
        da_pagina, set(), "09-sistema.html", {("09-sistema.html", "desligar")})
    assert alvos == ["retomar"]
    assert pulados == ["desligar"]
    assert regua._cobertura_dos_gestos(da_pagina, set(), alvos, pulados) == []


def test_a_vibracao_publicada_nao_tem_data_gesto_e_a_regua_sabe():
    """A afirmação acima, conferida contra o ARQUIVO e não contra a memória."""
    texto = _texto("05-vibracao.html")
    do_html = {g.nome for g in regua._gestos_cravados(texto)}
    assert not (do_html - {"aplicar", "salvar", "importar", "exportar",
                           "lado", "haptica"}), (
        f"a 05-vibracao passou a ter `data-gesto` próprio: {sorted(do_html)}. "
        f"Se isso é intencional, esta régua fica mais fácil — mas o teste tem "
        f"de saber, porque a união com os registrados existe por causa disto.")
    papeis = {g.nome for g in regua._papeis_cravados(texto)}
    assert {"forca", "testar", "parar"} <= papeis


def test_a_regua_le_os_mesmos_enderecos_do_bootstrap():
    """O Python e o JS têm de procurar os MESMOS atributos."""
    piloto = (RAIZ / "src/hefesto_dualsense4unix/interface/hefesto_vivo.py"
              ).read_text(encoding="utf-8")
    for atributo in regua.ATRIBUTOS_DE_CAMPO:
        assert f'[{atributo}=' in piloto or f"'{atributo}'" in piloto or \
               f'querySelectorAll(\'[{atributo}]' in piloto or atributo in piloto, (
            f"{atributo} é procurado pela régua e não aparece no piloto")
    leitor = re.search(r"LER_CAMPOS = r\"\"\"(.*?)\"\"\"", piloto, re.S)
    assert leitor, "o piloto perdeu o LER_CAMPOS — a régua ficou sem o lado da tela"
    for atributo in regua.ATRIBUTOS_DE_CAMPO:
        assert f"[{atributo}]" in leitor.group(1), (
            f"o LER_CAMPOS do piloto não procura {atributo}, e a régua procura")
