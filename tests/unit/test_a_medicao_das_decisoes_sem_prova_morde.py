"""AS MORDIDAS DA MEDIÇÃO — ``DECISAO-SEM-DONO-01``.

O instrumento é ``scripts/medir_decisoes_sem_prova.py``, e ele existe porque
uma decisão dela de 25/08/2026 ficou 23 dias registrada, ``estado: decidida``,
sem chegar ao produto — até ela abrir a aba Controles em 17/09 e achar o
microfone mudo pela terceira vez.

**O QUE ESTAS RÉGUAS PROTEGEM, e é uma coisa só:** que a medição não dê um
número mais bonito do que a realidade. As três medições da sprint viram um
portão depois, e um portão que nasce sobre um piso inflado é pior do que
portão nenhum — ele fecha a sprint sobre um defeito vivo.

**OITO MORDIDAS**, e cada uma arranca uma parte diferente do instrumento:

1. o furo — a citação no cabeçalho do módulo não é régua;
2. a herança por prefixo — ``D-A-ABA-LANCADORES`` dentro de
   ``D-A-ABA-LANCADORES-NASCE-PLACEHOLDER``;
3. o chão — coluna que some faz a contagem devolver zero em silêncio;
4. o degrau novo — um ``estado`` que ninguém declarou;
5. a catraca — decisão do piso que perdeu a régua;
6. o oráculo — vocabulário de processo que engole decisão com régua;
7. a declaração órfã — a isenção que sobrevive ao próprio caso;
8. o vocabulário — nenhum balde pode dizer «implementada»;
9. **o instrumento comprando a própria régua** — e este defeito foi real: ESTE
   arquivo cita ``D-COSTURA-BLUEZ`` e ``D-GESTO-DO-MAPA`` dentro de funções
   ``test_*``, e antes da cura o piso subiu de 29 para 31 sem que uma linha do
   produto mudasse.
"""
from __future__ import annotations

import csv
import importlib.util
import pathlib
import textwrap

import pytest

RAIZ = pathlib.Path(__file__).resolve().parents[2]
INSTRUMENTO = RAIZ / "scripts" / "medir_decisoes_sem_prova.py"


def _carregar():
    spec = importlib.util.spec_from_file_location("_medir_decisoes", INSTRUMENTO)
    assert spec and spec.loader
    modulo = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(modulo)
    return modulo


@pytest.fixture(scope="module")
def mi():
    return _carregar()


def _csv_de_mentira(destino: pathlib.Path, linhas, colunas=None):
    """Escreve um CSV com a forma do de verdade, mas com as linhas pedidas."""
    colunas = colunas or ("id", "titulo", "a_pergunta", "caminhos",
                          "recomendacao", "preco_do_outro_lado",
                          "por_que_espera", "onde_mora", "foto_antes",
                          "foto_depois", "custo", "aberta_em", "estado",
                          "escolha", "decidida_em", "nasceu_de",
                          "quem_decidiu", "revoga")
    with destino.open("w", encoding="utf-8", newline="") as fp:
        escritor = csv.DictWriter(fp, fieldnames=list(colunas))
        escritor.writeheader()
        for linha in linhas:
            escritor.writerow({c: linha.get(c, "") for c in colunas})
    return destino


def _arvore_de_mentira(base: pathlib.Path, arquivos: dict[str, str]):
    """Monta um ``tests/`` de mentira; a medição varre ``raiz/tests``."""
    pasta = base / "tests" / "unit"
    pasta.mkdir(parents=True, exist_ok=True)
    for nome, fonte in arquivos.items():
        (pasta / nome).write_text(textwrap.dedent(fonte), encoding="utf-8")
    return base


# ---------------------------------------------------------------------------
# 1 — O FURO: citação no cabeçalho do módulo NÃO é régua.
# ---------------------------------------------------------------------------
def test_a_citacao_no_cabecalho_do_modulo_nao_conta_como_regua(mi, tmp_path):
    """A MEDIÇÃO 3 inteira, e é o defeito que custou treze dias.

    O QUE A MORDIDA ARRANCA: troque o passeio de AST por um casamento de texto
    no arquivo — que é como um portão ingênuo contaria — e o arquivo que só
    cita o id na docstring do MÓDULO passa a contar como régua. O piso sobe de
    mentira, e a decisão aparece provada sem que função nenhuma a meça.

    Medido no produto: das 39 decisões citadas em ``tests/`` hoje, DEZ estão
    exatamente nessa situação.
    """
    base = _arvore_de_mentira(tmp_path, {
        "test_so_no_cabecalho.py": '''
            """Este módulo nasceu da D-SO-CABECALHO, e não a mede."""


            def test_qualquer_coisa():
                assert True
        ''',
        "test_dentro_da_funcao.py": '''
            """Um módulo sem id nenhum no cabeçalho."""


            def test_a_decisao_chegou():
                """Mede a D-DENTRO-DA-FUNCAO."""
                assert True
        ''',
    })
    ids = ["D-SO-CABECALHO", "D-DENTRO-DA-FUNCAO"]
    dentro, no_arquivo, _corpo = mi.onde_cada_id_aparece(ids, base)

    assert set(no_arquivo) == {"D-SO-CABECALHO", "D-DENTRO-DA-FUNCAO"}, (
        "casar por texto no arquivo enxerga as duas — é esse o piso inflado")
    assert set(dentro) == {"D-DENTRO-DA-FUNCAO"}, (
        "só a que está DENTRO de uma função de teste conta como régua")


def test_o_corpo_e_a_docstring_do_teste_se_separam(mi, tmp_path):
    """O degrau mais fino do furo, e ele tem gradação.

    Nesta casa a docstring do teste é contrato — *"escreva no docstring o que a
    mordida arranca"* —, então o piso fica na função inteira. Mas o id só no
    CORPO é o único caso em que a decisão participa do que a função executa, e
    a medição publica os dois números para dizer de quanto é a folga.

    O QUE A MORDIDA ARRANCA: apague a subtração da docstring
    (``trecho.replace(doc, " ")``) e os dois números viram o mesmo; a folga
    desaparece da saída e ninguém mais vê que 2 das 29 só citam na docstring.
    """
    base = _arvore_de_mentira(tmp_path, {
        "test_dois_degraus.py": '''
            def test_so_na_docstring():
                """Nasceu da D-SO-DOC."""
                assert True


            def test_no_corpo():
                """Sem id aqui."""
                assert "D-NO-CORPO" != ""
        ''',
    })
    ids = ["D-SO-DOC", "D-NO-CORPO"]
    dentro, _arq, corpo = mi.onde_cada_id_aparece(ids, base)

    assert set(dentro) == {"D-SO-DOC", "D-NO-CORPO"}
    assert set(corpo) == {"D-NO-CORPO"}, (
        "a docstring da função sai do corpo; se não sair, os dois degraus "
        "viram um e a folga some do laudo")


# ---------------------------------------------------------------------------
# 2 — A HERANÇA POR PREFIXO.
# ---------------------------------------------------------------------------
def test_a_decisao_curta_nao_herda_a_regua_da_longa(mi, tmp_path):
    """Dois ids desta casa são prefixo de outro, e são DUAS travas diferentes.

    ``D-A-ABA-LANCADORES`` está inteiro dentro de
    ``D-A-ABA-LANCADORES-NASCE-PLACEHOLDER``, e
    ``D-0609-UM-NO-DE-SOM-POR-CONTROLE`` dentro de outro.

    **O ARRANJO FÁCIL** é as duas estarem na lista: a alternação ordenada por
    tamanho já resolve, porque a longa casa primeiro e consome o texto. Medido
    em 20/09/2026: arrancar os limites da regex NÃO faz este caso falhar — a
    primeira versão desta régua olhava só isso e passava com a cura
    arrancada.

    **O ARRANJO DIFÍCIL**, que é o que os limites existem para pegar: a longa
    NÃO está na lista de decisões — foi renomeada, ou é um apelido de sprint
    parecido — e o texto que a cita é o único que existe. Aí não há alternação
    nenhuma para proteger a curta.

    O QUE A MORDIDA ARRANCA: tire ``(?<![A-Za-z0-9_-])`` /
    ``(?![A-Za-z0-9_-])`` de ``_regex_dos_ids`` e a curta passa a casar dentro
    de qualquer texto mais longo que a contenha — o piso ganha uma decisão
    para a qual ninguém escreveu régua.
    """
    base = _arvore_de_mentira(tmp_path, {
        "test_so_a_longa.py": '''
            def test_a_longa():
                """Mede a D-A-ABA-LANCADORES-NASCE-PLACEHOLDER."""
                assert True
        ''',
    })

    # O arranjo DIFÍCIL: só a curta é decisão; o texto cita o nome comprido.
    dificil, _arq, _corpo = mi.onde_cada_id_aparece(["D-A-ABA-LANCADORES"],
                                                    base)
    assert "D-A-ABA-LANCADORES" not in dificil, (
        "a curta casou dentro de um identificador mais longo — os limites da "
        "regex caíram, e o piso ganhou uma régua que não existe")

    # O arranjo fácil, guardado ao lado para dizer quem o protege: a ordem.
    facil, _arq, _corpo = mi.onde_cada_id_aparece(
        ["D-A-ABA-LANCADORES", "D-A-ABA-LANCADORES-NASCE-PLACEHOLDER"], base)
    assert set(facil) == {"D-A-ABA-LANCADORES-NASCE-PLACEHOLDER"}


# ---------------------------------------------------------------------------
# 3 e 4 — O CHÃO: a forma do CSV, e o degrau que é dela nomear.
# ---------------------------------------------------------------------------
def test_coluna_que_some_para_a_medicao_em_vez_de_contar_zero(mi, tmp_path,
                                                              capsys):
    """Zero lê-se como «nenhuma decisão sem prova» — o contrário do medido.

    O QUE A MORDIDA ARRANCA: faça ``problemas_de_forma`` devolver sempre
    ``[]``. O CSV sem a coluna ``estado`` passa a render ZERO decisões
    decididas, o ``--check`` fica VERDE, e o laudo anuncia um piso perfeito
    sobre um arquivo que a medição já não sabe ler.
    """
    alvo = _csv_de_mentira(
        tmp_path / "sem_estado.csv",
        [{"id": "D-QUALQUER", "titulo": "t"}],
        colunas=("id", "titulo", "onde_mora", "decidida_em"),  # sem `estado`
    )
    medida = mi.medir(raiz=tmp_path, csv_path=alvo)
    assert medida["problemas_de_forma"], "a falta da coluna passou batida"
    assert any("estado" in p for p in medida["problemas_de_forma"])

    mi.CSV_DAS_DECISOES = alvo
    mi.RAIZ = tmp_path
    try:
        assert mi.main(["--check"]) == 1
    finally:
        mi.CSV_DAS_DECISOES = RAIZ / "docs" / "data" / "decisoes-dela.csv"
        mi.RAIZ = RAIZ
    saida = capsys.readouterr().out
    assert "VERMELHO" in saida and "estado" in saida
    assert "zero" in saida, "a saída tem de dizer POR QUE zero engana"


def test_o_degrau_novo_nao_entra_calado(mi, tmp_path):
    """O ``estado`` que a sprint pede — e cujo NOME é dela.

    A sprint quer ``aberta → decidida → IMPLEMENTADA → (caduca)``, e diz com
    todas as letras que o nome do degrau novo é dela: *"`implementada`?
    `feita`? `no ar`? É palavra do vocabulário desta casa e ela tem dono."*
    Quando ele chegar, a medição tem de ser avisada — senão ela conta as
    implementadas como não-decididas e o piso DESABA sem que nada tenha
    piorado.

    O QUE A MORDIDA ARRANCA: tire a checagem de ``ESTADOS_CONHECIDOS`` e um
    estado novo entra em silêncio, mudando todas as contagens de uma vez.
    """
    alvo = _csv_de_mentira(tmp_path / "estado_novo.csv", [
        {"id": "D-UMA", "estado": "decidida"},
        {"id": "D-OUTRA", "estado": "implementada"},
    ])
    medida = mi.medir(raiz=tmp_path, csv_path=alvo)
    ruins = medida["problemas_de_forma"]
    assert ruins, "o estado novo passou sem uma palavra"
    assert any("implementada" in p for p in ruins)
    assert any("dela" in p or "nome" in p for p in ruins), (
        "o recado tem de lembrar que o nome do degrau é dela")


# ---------------------------------------------------------------------------
# 5 — A CATRACA: o piso só desce quando alguém GANHA régua.
# ---------------------------------------------------------------------------
def test_decisao_do_piso_que_perde_a_regua_sai_nominal(mi, tmp_path, capsys):
    """A regressão que o piso existe para pegar, e ela sai com nome.

    O QUE A MORDIDA ARRANCA: esvazie ``COM_REGUA_EM_20260920``. Apagar o
    teste que apontava para uma decisão dela passa a ser VERDE — que é exatamente o
    estado em que esta casa esteve entre 25/08 e 17/09, com a diferença de
    que agora alguém teria escrito a régua e outra pessoa a teria apagado.

    A catraca NÃO pega decisão nova sem régua: isso seria o portão da sprint,
    e o portão da sprint espera duas palavras dela.
    """
    base = _arvore_de_mentira(tmp_path, {
        "test_mede_uma.py": '''
            def test_a_primeira():
                """Mede a D-FICA."""
                assert True
        ''',
    })
    alvo = _csv_de_mentira(tmp_path / "piso.csv", [
        {"id": "D-FICA", "estado": "decidida", "titulo": "o botão da aba"},
        {"id": "D-SUMIU", "estado": "decidida", "titulo": "o botão da aba"},
        {"id": "D-NOVINHA", "estado": "decidida", "titulo": "o botão da aba"},
    ])
    guarda = mi.COM_REGUA_EM_20260920
    mi.COM_REGUA_EM_20260920 = ("D-FICA", "D-SUMIU")
    mi.CSV_DAS_DECISOES = alvo
    mi.RAIZ = base
    try:
        medida = mi.medir(raiz=base, csv_path=alvo)
        assert medida["regua_perdida"] == ["D-SUMIU"]
        assert mi.main(["--check"]) == 1
        saida = capsys.readouterr().out
        assert "D-SUMIU" in saida, "a regressão sai nominal, nunca em silêncio"
        assert "D-NOVINHA" not in saida, (
            "decisão NOVA sem régua não é regressão — a catraca não pode "
            "barrá-la, ou ela deixa de poder registrar o que decidiu")
        assert "REGRESSÃO" in saida
    finally:
        mi.COM_REGUA_EM_20260920 = guarda
        mi.CSV_DAS_DECISOES = RAIZ / "docs" / "data" / "decisoes-dela.csv"
        mi.RAIZ = RAIZ


def test_o_piso_que_aponta_para_linha_que_nao_existe_reprova(mi, tmp_path,
                                                             capsys):
    """Piso que cita decisão fora do CSV deixa de ser catraca.

    **ESTA RÉGUA ACHOU UM DEFEITO NO INSTRUMENTO — 20/09/2026.** Na primeira
    versão ela passava com a cura arrancada, e a causa era do instrumento, não
    dela: uma decisão que caducava aparecia nas DUAS listas pela mesma causa,
    e ``regua_perdida`` reprovava no lugar de ``piso_que_sumiu_do_csv``. Mas a
    régua não «se perdeu» — a decisão é que saiu do vocabulário de decidida.
    Curado na raiz: ``regua_perdida`` passou a olhar só decisão AINDA decidida,
    e as duas checagens ficaram disjuntas.

    O QUE A MORDIDA ARRANCA: tire a checagem ``piso_que_sumiu_do_csv``. Uma
    decisão do piso que caduque some da conta em silêncio, e o número do piso
    passa a valer menos do que diz.
    """
    base = _arvore_de_mentira(
        tmp_path, {"test_vazio.py": "def test_x():\n    assert True\n"})
    alvo = _csv_de_mentira(tmp_path / "caducou.csv", [
        {"id": "D-VIVA", "estado": "decidida", "titulo": "o botão da aba"},
        {"id": "D-CADUCOU", "estado": "caduca", "titulo": "o botão da aba"},
    ])
    guarda = mi.COM_REGUA_EM_20260920
    mi.COM_REGUA_EM_20260920 = ("D-CADUCOU",)
    mi.CSV_DAS_DECISOES = alvo
    mi.RAIZ = base
    try:
        medida = mi.medir(raiz=base, csv_path=alvo)
        assert medida["piso_que_sumiu_do_csv"] == ["D-CADUCOU"]
        assert medida["regua_perdida"] == [], (
            "as duas checagens do piso são disjuntas: decisão que CADUCOU não "
            "é régua perdida, e enquanto era, esta mordida olhava a trava "
            "errada e passava com a cura arrancada")
        assert mi.main(["--check"]) == 1
    finally:
        mi.COM_REGUA_EM_20260920 = guarda
        mi.CSV_DAS_DECISOES = RAIZ / "docs" / "data" / "decisoes-dela.csv"
        mi.RAIZ = RAIZ
    assert "D-CADUCOU" in capsys.readouterr().out


# ---------------------------------------------------------------------------
# 6 e 7 — O ORÁCULO da MEDIÇÃO 2, e a isenção que não pode sobreviver ao caso.
# ---------------------------------------------------------------------------
def test_vocabulario_de_processo_que_engole_decisao_com_regua_reprova(
        mi, tmp_path, capsys):
    """A MEDIÇÃO 2 inteira: quem tem régua é de PRODUTO por construção.

    O oráculo não é opinião e não é tautologia — ele não sai do CSV, sai de
    ``tests/``: se alguém conseguiu apontar uma função de teste para a
    decisão, existe produto ali para medir. O classificador é TRIAGEM, e
    quando ele discorda do oráculo é ele que está errado.

    Isto importa porque o portão da sprint vai usar a triagem para TIRAR as
    decisões de processo do escopo. Um vocabulário largo demais tira do escopo
    decisão de produto — e a decisão sai da fila sem nunca ter sido feita, que
    é o defeito-mãe desta sprint acontecendo de novo, pela porta da cura.

    O QUE A MORDIDA ARRANCA: apague o cruzamento ``oraculo & processo`` e o
    ``--check`` fica VERDE com o vocabulário engolindo o que quiser.
    """
    base = _arvore_de_mentira(tmp_path, {
        "test_mede.py": '''
            def test_a_aba_mostra():
                """Mede a D-COM-REGUA."""
                assert True
        ''',
    })
    # «sprint» é palavra de processo; nenhuma palavra de produto aparece.
    alvo = _csv_de_mentira(tmp_path / "colisao.csv", [
        {"id": "D-COM-REGUA", "estado": "decidida",
         "titulo": "o que a sprint decidiu sobre a ordem"},
    ])
    guarda_piso, guarda_col = mi.COM_REGUA_EM_20260920, mi.COLISOES_DECLARADAS
    mi.COM_REGUA_EM_20260920 = ()
    mi.COLISOES_DECLARADAS = {}
    mi.CSV_DAS_DECISOES = alvo
    mi.RAIZ = base
    try:
        medida = mi.medir(raiz=base, csv_path=alvo)
        assert medida["triagem"].get("processo") == ["D-COM-REGUA"]
        assert medida["colisoes_nao_declaradas"] == ["D-COM-REGUA"]
        assert mi.main(["--check"]) == 1
        saida = capsys.readouterr().out
        assert "D-COM-REGUA" in saida and "PRODUTO" in saida
    finally:
        mi.COM_REGUA_EM_20260920 = guarda_piso
        mi.COLISOES_DECLARADAS = guarda_col
        mi.CSV_DAS_DECISOES = RAIZ / "docs" / "data" / "decisoes-dela.csv"
        mi.RAIZ = RAIZ


def test_a_declaracao_que_sobrevive_ao_proprio_caso_reprova(mi, tmp_path,
                                                            capsys):
    """Isenção velha isenta a colisão seguinte, que ninguém olhou.

    O QUE A MORDIDA ARRANCA: tire a checagem ``declaracoes_orfas``. Uma
    declaração escrita para um caso que já passou fica no arquivo e cala a
    próxima colisão do mesmo id — o instrumento passa a comprar a própria
    isenção como prova.
    """
    base = _arvore_de_mentira(tmp_path, {"test_vazio.py": "def test_x():\n    assert True\n"})
    alvo = _csv_de_mentira(tmp_path / "orfa.csv", [
        {"id": "D-QUALQUER", "estado": "decidida", "titulo": "o botão da aba"},
    ])
    guarda_piso, guarda_col = mi.COM_REGUA_EM_20260920, mi.COLISOES_DECLARADAS
    mi.COM_REGUA_EM_20260920 = ()
    mi.COLISOES_DECLARADAS = {"D-QUE-JA-PASSOU": "razão de ontem"}
    mi.CSV_DAS_DECISOES = alvo
    mi.RAIZ = base
    try:
        medida = mi.medir(raiz=base, csv_path=alvo)
        assert medida["declaracoes_orfas"] == ["D-QUE-JA-PASSOU"]
        assert mi.main(["--check"]) == 1
    finally:
        mi.COM_REGUA_EM_20260920 = guarda_piso
        mi.COLISOES_DECLARADAS = guarda_col
        mi.CSV_DAS_DECISOES = RAIZ / "docs" / "data" / "decisoes-dela.csv"
        mi.RAIZ = RAIZ
    assert "D-QUE-JA-PASSOU" in capsys.readouterr().out


def test_toda_colisao_declarada_diz_por_que_e_de_produto(mi):
    """A razão se ESCREVE — a lista se lê. Mesma disciplina do `casa-sabe`.

    O QUE A MORDIDA ARRANCA: deixe uma declaração com a razão em branco e a
    isenção vira uma linha que ninguém pode conferir.
    """
    for ident, razao in mi.COLISOES_DECLARADAS.items():
        assert len(razao) > 80, f"{ident}: a razão não explica nada"
        assert "PRODUTO" in razao, (
            f"{ident}: a declaração tem de dizer que a decisão é de produto, "
            f"que é o que o oráculo provou")


# ---------------------------------------------------------------------------
# 8 — O VOCABULÁRIO: verde não quer dizer feito.
# ---------------------------------------------------------------------------
def test_o_balde_nunca_diz_implementada(mi):
    """A MEDIÇÃO 3 virada em regra de língua.

    A sprint manda dizer isto em voz alta: *"o portão mede a EXISTÊNCIA da
    prova, não a qualidade dela; diga isso em voz alta no script, para ninguém
    confundir verde com feito."* Este instrumento sabe onde o id APARECE. Ele
    não sabe se a decisão está no produto — e a prova de que não sabe tem
    data: ``D-AUDIO-E-GIRO-NASCEM-LIGADOS`` esteve citada dentro de ``tests/``
    desde 04/09, e em 17/09 o microfone dela ainda nascia mudo.

    O QUE A MORDIDA ARRANCA: renomeie qualquer balde para «implementada»,
    «feita» ou «no ar» e esta régua reprova. O nome do degrau que significa
    FEITO é dela, e nenhum balde deste instrumento pode tomá-lo emprestado.
    """
    baldes = (mi.BALDE_DENTRO, mi.BALDE_CABECALHO, mi.BALDE_SEM)
    proibidas = ("implementada", "implementado", "feita", "feito", "no ar",
                 "pronta", "pronto", "entregue")
    for balde in baldes:
        for palavra in proibidas:
            assert palavra not in balde.lower(), (
                f"o balde «{balde}» promete FEITO, e o instrumento só sabe "
                f"onde o id aparece")
    assert "citada" in mi.BALDE_DENTRO and "citada" in mi.BALDE_CABECALHO, (
        "os baldes dizem «citada», que é o que a medição enxerga")


def test_o_verde_do_check_avisa_que_nao_quer_dizer_feito(mi, capsys):
    """O recado que impede a próxima pessoa de ler verde como pronto.

    O QUE A MORDIDA ARRANCA: apague o parágrafo final do ``--check``. O
    instrumento passa a imprimir VERDE seco sobre 208 decisões sem régua — e
    verde seco é exatamente o que fez esta casa achar, por treze dias, que a
    decisão do microfone estava resolvida.
    """
    assert mi.main(["--check"]) == 0
    saida = capsys.readouterr().out
    assert "VERDE" in saida
    assert "NÃO QUER DIZER FEITO" in saida
    assert "D-AUDIO-E-GIRO-NASCEM-LIGADOS" in saida


def test_o_laudo_de_hoje_sai_com_as_tres_medicoes(mi, capsys):
    """O estado medido em 20/09/2026, e ele é o que a sprint encomendou.

    O QUE A MORDIDA ARRANCA: deixe o laudo imprimir só os totais. As dez
    decisões citadas SÓ no cabeçalho somem da saída, e elas são o degrau mais
    barato da sprint inteira — o único que já está nomeado.
    """
    assert mi.main([]) == 0
    saida = capsys.readouterr().out
    for cabeca in ("MEDIÇÃO 1", "MEDIÇÃO 2", "MEDIÇÃO 3",
                   "O CUSTO DE CADA DEGRAU"):
        assert cabeca in saida
    assert "D-COSTURA-BLUEZ" in saida, (
        "as citadas só no cabeçalho saem NOMEADAS — é a fila mais barata")
    assert "D-AUDIO-E-GIRO-NASCEM-LIGADOS" in saida


def test_o_instrumento_nao_compra_a_propria_regua_como_prova(mi, tmp_path):
    """O defeito foi REAL, e ele é deste arquivo — medido em 20/09/2026.

    Este módulo cita ``D-COSTURA-BLUEZ`` e ``D-GESTO-DO-MAPA`` dentro de
    funções ``test_*``, porque confere que as duas saem nomeadas no laudo.
    Antes da cura isso bastava: o piso subia de 29 para 31 e as «citadas só no
    cabeçalho» caíam de 10 para 8 — **sem que uma linha do produto mudasse**.
    O instrumento estava se contando.

    O QUE A MORDIDA ARRANCA: faça ``_e_o_proprio_instrumento`` devolver sempre
    ``False``. A régua do instrumento volta a valer como régua das decisões que
    ela apenas nomeia, e o piso infla pelo tamanho desta suíte — que é a única
    coisa que ele nunca pode medir.
    """
    assert mi._e_o_proprio_instrumento(
        pathlib.Path(__file__).read_text(encoding="utf-8")), (
        "a régua do instrumento tem de ser reconhecida como régua DELE")

    base = _arvore_de_mentira(tmp_path, {
        "test_mede_o_instrumento.py": '''
            """Régua do medir_decisoes_sem_prova."""


            def test_o_laudo_nomeia():
                assert "D-ALVO" in "D-ALVO"
        ''',
        "test_mede_a_decisao.py": '''
            def test_o_produto_obedece():
                """Mede a D-OUTRA."""
                assert True
        ''',
    })
    dentro, _arq, _corpo = mi.onde_cada_id_aparece(["D-ALVO", "D-OUTRA"], base)
    assert "D-ALVO" not in dentro, (
        "o arquivo que mede o instrumento contou como régua de uma decisão")
    assert "D-OUTRA" in dentro, (
        "a exclusão não pode engolir régua de verdade junto")


def test_a_medicao_de_hoje_bate_com_o_csv_de_hoje(mi):
    """O censo da sprint conferido contra o arquivo, não contra a lembrança.

    A sprint mediu 239 linhas / 237 decididas em 17/09. Se essa conta mudar, a
    prosa do instrumento envelheceu junto — e número errado nesta casa se
    SUBSTITUI, em todos os lugares onde aparece.

    O QUE A MORDIDA ARRANCA: troque ``estado == "decidida"`` por um contador
    de todas as linhas e a conta passa a incluir as caducas — duas decisões
    que ninguém tem de provar entram na fila.
    """
    medida = mi.medir()
    assert medida["decididas"] == medida["linhas"] - 2, (
        "o CSV tem duas linhas `caduca`; se isso mudou, o laudo tem de dizer")
    assert medida["decididas"] > 0
    assert len(medida["com_regua_dentro_de_teste"]) <= medida["decididas"]
    assert set(medida["com_regua_dentro_de_teste"]).isdisjoint(
        medida["citadas_so_no_cabecalho"]), (
        "uma decisão não pode estar nos dois baldes ao mesmo tempo")
