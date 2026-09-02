#!/usr/bin/env python3
"""A régua que ELA pediu: um campo que continua exibindo o valor do mockup.

    *"um portão que, com o daemon vivo e a mesa real, reprove quando um campo
    continua exibindo o valor do mockup. Hoje nada acusa isso."*  — 02/09/2026

O CASO QUE NOMEIA O DEFEITO, e está no HTML publicado de hoje: a aba Gatilhos
mostra ``Força 7 · Frequência 4 · Início do curso 25 · Fim do curso 230`` com o
perfil dela dizendo ``modo='Off' params=[]``. Nenhum daqueles quatro números
saiu do aparelho — são o desenho de 26/08, cravado no arquivo e nunca repintado.

POR QUE ESTA RÉGUA É DIFERENTE DAS ANTERIORES, e é a lição-mãe do dia: as outras
contavam se o NOME de um campo aparecia no código do pacote. Foi assim que se
reportou **77% de paridade** onde o produto entregava 36%, e assim que a segunda
medição do mesmo dia disse **61%** contando `data-campo` em arquivo.
**Presença de string não é funcionamento.** Aqui a pergunta é outra: o que a
TELA mostra é igual ao que o ARQUIVO crava?

O QUE ESTE TESTE COBRE, sem abrir janela nenhuma (o cérebro da régua é puro):

1. o parser lê o que está cravado nas DEZ páginas publicadas de verdade;
2. tela igual ao cravado e sem pacote nenhum declarando → ``MOCKUP``;
3. tela diferente → ``PRODUTO``;
4. pacote declara o MESMO valor → ``INDECIDIVEL``, e a régua diz por quê;
5. pacote declara OUTRO valor e a tela não mudou → ``ENDEREÇO MORTO``;
6. um bloco trocado inteiro pelo produto não vira medição errada;
7. a lista de cliques cobre o que a PÁGINA tem, e não só o que o código registra.

A MORDIDA: arranque a comparação em ``_classificar()`` — faça-a devolver
``PRODUTO`` sempre — e ``test_a_gatilhos_congelada_e_acusada`` reprova. É o
mesmo arranque que o piloto oferece vivo, com ``--sem-cravado``.
"""
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

#: A aba do caso que nomeia o defeito.
GATILHOS = "03-gatilhos.html"


def _texto(pagina: str) -> str:
    return onde.pagina(pagina, publicado=True).read_text(encoding="utf-8")


def _paginas() -> list[str]:
    return [p.name for p in onde.paginas(publicado=True) if p.name[:2].isdigit()]


# -- o parser ------------------------------------------------------------
def test_as_dez_paginas_publicadas_tem_endereco_de_campo():
    """Nenhuma das dez pode voltar vazia — vazio aqui seria a régua cega."""
    for pagina in _paginas():
        campos = regua._campos_cravados(_texto(pagina))
        assert campos, (
            f"{pagina} não devolveu endereço de campo nenhum. Ou a página perdeu "
            f"os `data-campo`, ou o parser parou de enxergá-los — e nos dois "
            f"casos a régua do mockup passa a medir o vácuo.")


def test_os_quatro_numeros_congelados_da_gatilhos_estao_no_arquivo():
    """Os valores do caso, lidos do HTML publicado — não digitados aqui.

    Digitá-los faria este teste dizer o que ele mesmo escreveu. Ele LÊ do
    arquivo, e o que ele afirma é que aqueles quatro ajustes do P1 são texto
    cravado, não dado — que é o defeito inteiro.
    """
    campos = {c.endereco: c.valor for c in regua._campos_cravados(_texto(GATILHOS))}
    assert campos["p1·aj-nome-e-0"] == "Força"
    assert campos["p1·aj-val-e-0"] == "7"
    assert campos["p1·aj-nome-e-1"] == "Frequência"
    assert campos["p1·aj-val-e-1"] == "4"
    assert campos["p1·aj-val-e-2"] == "25"
    assert campos["p1·aj-val-e-3"] == "230"


def test_o_mesmo_endereco_em_colunas_diferentes_nao_se_confunde():
    """`aj-val-e-0` vale 7 na coluna do P1 e 3 na do P2 — são campos distintos.

    Sem o dono no endereço, a régua casaria o campo de um controle com o do
    vizinho e chamaria isso de medição. É o mesmo cuidado que a pintura toma ao
    procurar `data-campo` DENTRO do bloco de `data-controle`.
    """
    campos = {c.endereco: c.valor for c in regua._campos_cravados(_texto(GATILHOS))}
    assert campos["p1·aj-val-e-0"] == "7"
    assert campos["p2·aj-val-e-0"] == "3"


def test_uma_option_sem_value_vale_o_texto_dela():
    """Contrato do HTML, e ignorá-lo custou uma cegueira medida em 02/09/2026.

    Os `<select>` da aba Conexões escrevem `<option>Wi-Fi</option>` sem `value`.
    A régua os lia como vazios e depois acusava a página VIRGEM de já ter sido
    pintada, porque o navegador devolvia `Wi-Fi` onde ela esperava `''`.
    """
    campos = regua._campos_cravados(
        '<select data-campo="x" data-hef-alvo="valor">'
        '<option>Wi-Fi</option><option>Teclado</option></select>')
    assert [c.valor for c in campos] == ["Wi-Fi"]


def test_a_largura_e_lida_como_o_navegador_a_devolve():
    """`width:100.0%` no arquivo é `100%` no `el.style.width` — e 66.7% fica.

    O gerador do desenho escreve `100.0%` porque o número vem de um `float` do
    Python. Comparar as duas formas cruas dizia que a barra da Vibração tinha
    sido pintada quando ninguém a tocou.
    """
    campos = regua._campos_cravados(
        '<span data-campo="a" data-hef-alvo="largura" style="width:100.0%"></span>'
        '<span data-campo="b" data-hef-alvo="largura" style="width:66.7%"></span>')
    assert [c.valor for c in campos] == ["100%", "66.7%"]


# -- a classificação -----------------------------------------------------
def test_a_gatilhos_congelada_e_acusada():
    """A TELA IGUAL AO ARQUIVO, e nenhum pacote declarando: é MOCKUP.

    É o caso que ela viu. Se este teste passar a dar `PRODUTO`, a régua deixou
    de comparar com o arquivo — é a mordida.
    """
    cravados = regua._campos_cravados(_texto(GATILHOS))
    # NADA MUDOU NA TELA: o vivo é o próprio cravado.
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
    """O pior dos casos: o pacote monta o valor e escreve onde a página não tem.

    A tela continua no desenho, o pacote continua "cobrindo" o campo, e portão
    nenhum via. É a forma exata do defeito que deixou a `06-navegacao` publicar
    sete campos e pintar três.
    """
    cravados = regua._campos_cravados('<span data-campo="bateria">64%</span>')
    (v,) = regua._classificar(cravados, ["64%"], {("", "bateria"): "85%"})
    assert v.classe == regua.MOCKUP
    assert "ENDEREÇO MORTO" in v.nota


def test_o_vazio_declarado_vira_travessao_como_na_tela():
    """`escrever()` põe travessão no vazio; a régua tem de saber disso.

    Sem esta tradução, um lugar VAZIO da mesa — que a pintura preenche com `—` —
    seria lido como campo não declarado, e a régua acusaria de mockup um
    travessão que o produto acabou de escrever.
    """
    assert regua._como_a_tela_escreveria(None) == regua.TRAVESSAO
    assert regua._como_a_tela_escreveria("") == regua.TRAVESSAO
    assert regua._como_a_tela_escreveria(85) == "85"


def test_listas_de_tamanhos_diferentes_nao_se_comparam():
    with pytest.raises(ValueError, match="tamanhos diferentes"):
        regua._classificar(regua._campos_cravados('<b data-campo="x">1</b>'), [], {})


# -- o bloco trocado inteiro ---------------------------------------------
def test_um_bloco_trocado_pelo_produto_nao_vira_medicao_errada():
    """A pintura troca blocos inteiros — e alinhar por posição casaria vizinhos.

    Medido na primeira execução desta régua: a `10-perfis` acabou o passeio com
    55 endereços onde o arquivo tem 81, porque o produto trocou a tabela de
    perfis do desenho pela dela. Aquilo não é cegueira; é o produto trabalhando.
    """
    cravados = regua._campos_cravados(
        '<b data-campo="nome">Um</b><b data-campo="nome">Dois</b>'
        '<b data-campo="nome">Três</b>')
    # A TELA FICOU COM DUAS LINHAS: o bloco foi trocado por um mais curto.
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


# -- a cobertura dos gestos ----------------------------------------------
def test_a_lista_de_cliques_alcanca_o_botao_que_ninguem_ligou():
    """O defeito de 29/08/2026, e ele é o motivo de a lista ser a UNIÃO.

    O `--prova-gesto` da aba Controles clicava o que o CÓDIGO registrava, deu
    VERDE, e nunca tocou os dois botões que só existiam na PÁGINA. *Uma
    validação de interface que não cobre o botão novo é uma validação que
    mente.*
    """
    da_pagina = [regua._Gesto("botao-novo", "p1")]
    alvos, pulados = regua._alvos_a_clicar(da_pagina, set(), "x.html", set())
    assert alvos == ["botao-novo"]
    assert regua._cobertura_dos_gestos(da_pagina, set(), alvos, pulados) == []


def test_a_lista_de_cliques_alcanca_o_gesto_que_a_pagina_enderecou_por_papel():
    """A outra metade da união, e sem ela a aba Vibração fica sem um clique.

    O HTML da `05-vibracao` não tem um único `data-gesto`: os três gestos
    daquela aba — `forca`, `testar`, `parar` — são endereçados por `data-papel`,
    que a régua não clica às cegas porque ali ele endereça 28 CAMPOS.
    """
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
    # O rodapé (`.r-<nome>`) mora no esqueleto das dez e aparece aqui também.
    assert not (do_html - {"aplicar", "salvar", "importar", "exportar"}), (
        f"a 05-vibracao passou a ter `data-gesto` próprio: {sorted(do_html)}. "
        f"Se isso é intencional, esta régua fica mais fácil — mas o teste tem "
        f"de saber, porque a união com os registrados existe por causa disto.")
    papeis = {g.nome for g in regua._papeis_cravados(texto)}
    assert {"forca", "testar", "parar"} <= papeis


# -- a régua contra o BOOTSTRAP ------------------------------------------
def test_a_regua_le_os_mesmos_enderecos_do_bootstrap():
    """O Python e o JS têm de procurar os MESMOS atributos.

    Este módulo repete, do lado Python, a lista que a função `achar()` do
    BOOTSTRAP usa no DOM. Duas listas com o mesmo dever divergem em silêncio —
    e uma régua que procura menos atributos que a pintura mede menos campos do
    que existem, sem uma linha de erro.
    """
    piloto = (RAIZ / "src/hefesto_dualsense4unix/interface/hefesto_vivo.py"
              ).read_text(encoding="utf-8")
    for atributo in regua.ATRIBUTOS_DE_CAMPO:
        assert f'[{atributo}=' in piloto or f"'{atributo}'" in piloto or \
               f'querySelectorAll(\'[{atributo}]' in piloto or atributo in piloto, (
            f"{atributo} é procurado pela régua e não aparece no piloto")
    # O LEITOR DO DOM tem de listar os três — é ele que traz o outro lado da
    # comparação, e um atributo a menos ali some com campos inteiros.
    leitor = re.search(r"LER_CAMPOS = r\"\"\"(.*?)\"\"\"", piloto, re.S)
    assert leitor, "o piloto perdeu o LER_CAMPOS — a régua ficou sem o lado da tela"
    for atributo in regua.ATRIBUTOS_DE_CAMPO:
        assert f"[{atributo}]" in leitor.group(1), (
            f"o LER_CAMPOS do piloto não procura {atributo}, e a régua procura")
