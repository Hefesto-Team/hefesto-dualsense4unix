"""AS MORDIDAS DA MEDIÇÃO — ``DECISAO-SEM-DONO-01``."""
from __future__ import annotations

import csv
import importlib.util
import pathlib
import textwrap

import pytest

PISO_MEDIDO_EM_20260920 = 29

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


def test_a_citacao_no_cabecalho_do_modulo_nao_conta_como_regua(mi, tmp_path):
    """A MEDIÇÃO 3 inteira, e é o defeito que custou treze dias."""
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
    """O degrau mais fino do furo, e ele tem gradação."""
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


def test_a_decisao_curta_nao_herda_a_regua_da_longa(mi, tmp_path):
    """Dois ids desta casa são prefixo de outro, e são DUAS travas diferentes."""
    base = _arvore_de_mentira(tmp_path, {
        "test_so_a_longa.py": '''
            def test_a_longa():
                """Mede a D-A-ABA-LANCADORES-NASCE-PLACEHOLDER."""
                assert True
        ''',
    })

    dificil, _arq, _corpo = mi.onde_cada_id_aparece(["D-A-ABA-LANCADORES"],
                                                    base)
    assert "D-A-ABA-LANCADORES" not in dificil, (
        "a curta casou dentro de um identificador mais longo — os limites da "
        "regex caíram, e o piso ganhou uma régua que não existe")

    facil, _arq, _corpo = mi.onde_cada_id_aparece(
        ["D-A-ABA-LANCADORES", "D-A-ABA-LANCADORES-NASCE-PLACEHOLDER"], base)
    assert set(facil) == {"D-A-ABA-LANCADORES-NASCE-PLACEHOLDER"}


def test_coluna_que_some_para_a_medicao_em_vez_de_contar_zero(mi, tmp_path,
                                                              capsys):
    """Zero lê-se como «nenhuma decisão sem prova» — o contrário do medido."""
    alvo = _csv_de_mentira(
        tmp_path / "sem_estado.csv",
        [{"id": "D-QUALQUER", "titulo": "t"}],
        colunas=("id", "titulo", "onde_mora", "decidida_em"),
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
    """O ``estado`` que a sprint pede — e cujo NOME é dela."""
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


def test_decisao_do_piso_que_perde_a_regua_sai_nominal(mi, tmp_path, capsys):
    """A regressão que o piso existe para pegar, e ela sai com nome."""
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
    """Piso que cita decisão fora do CSV deixa de ser catraca."""
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


def test_vocabulario_de_processo_que_engole_decisao_com_regua_reprova(
        mi, tmp_path, capsys):
    """A MEDIÇÃO 2 inteira: quem tem régua é de PRODUTO por construção."""
    base = _arvore_de_mentira(tmp_path, {
        "test_mede.py": '''
            def test_a_aba_mostra():
                """Mede a D-COM-REGUA."""
                assert True
        ''',
    })
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
    """Isenção velha isenta a colisão seguinte, que ninguém olhou."""
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
    """A razão se ESCREVE — a lista se lê. Mesma disciplina do `casa-sabe`."""
    for ident, razao in mi.COLISOES_DECLARADAS.items():
        assert len(razao) > 80, f"{ident}: a razão não explica nada"
        assert "PRODUTO" in razao, (
            f"{ident}: a declaração tem de dizer que a decisão é de produto, "
            f"que é o que o oráculo provou")


def test_o_balde_nunca_diz_implementada(mi):
    """A MEDIÇÃO 3 virada em regra de língua."""
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
    """O recado que impede a próxima pessoa de ler verde como pronto."""
    assert mi.main(["--check"]) == 0
    saida = capsys.readouterr().out
    assert "VERDE" in saida
    assert "NÃO QUER DIZER FEITO" in saida
    assert "D-AUDIO-E-GIRO-NASCEM-LIGADOS" in saida


def test_o_laudo_de_hoje_sai_com_as_tres_medicoes(mi, capsys):
    """O estado medido em 20/09/2026, e ele é o que a sprint encomendou."""
    assert mi.main([]) == 0
    saida = capsys.readouterr().out
    for cabeca in ("MEDIÇÃO 1", "MEDIÇÃO 2", "MEDIÇÃO 3",
                   "O CUSTO DE CADA DEGRAU"):
        assert cabeca in saida
    assert "D-AUDIO-E-GIRO-NASCEM-LIGADOS" in saida


def test_o_laudo_nomeia_cada_citada_so_no_cabecalho(mi, tmp_path, capsys):
    """As citadas só no cabeçalho saem NOMEADAS: é a fila mais barata.

    Numa árvore de mentira, e não na fila viva: a fila esvaziar é o trabalho
    feito, e a régua não pode reprovar por isso.
    """
    base = _arvore_de_mentira(tmp_path, {
        "test_so_no_cabecalho.py": '''
            """Nasceu da D-SO-NO-CABECALHO, e não a mede."""


            def test_a_outra():
                """Mede a D-NA-FUNCAO."""
                assert True
        ''',
    })
    alvo = _csv_de_mentira(tmp_path / "laudo.csv", [
        {"id": "D-SO-NO-CABECALHO", "estado": "decidida", "titulo": "o botão da aba"},
        {"id": "D-NA-FUNCAO", "estado": "decidida", "titulo": "o botão da aba"},
    ])
    mi.CSV_DAS_DECISOES = alvo
    mi.RAIZ = base
    try:
        assert mi.main([]) == 0
        saida = capsys.readouterr().out
    finally:
        mi.CSV_DAS_DECISOES = RAIZ / "docs" / "data" / "decisoes-dela.csv"
        mi.RAIZ = RAIZ
    medicao_3 = saida[saida.index("MEDIÇÃO 3"):saida.index("O CUSTO DE CADA DEGRAU")]
    assert "D-SO-NO-CABECALHO" in medicao_3, (
        "as citadas só no cabeçalho saem NOMEADAS — é a fila mais barata")
    assert "D-NA-FUNCAO" not in medicao_3, "a que tem régua entrou na fila do cabeçalho"


def test_o_nome_do_instrumento_e_o_do_arquivo(mi):
    """A constante é o que o faz reconhecer a si mesmo: renomear o arquivo a quebra."""
    assert pathlib.Path(mi.__file__).stem == mi.NOME_DO_INSTRUMENTO
    assert mi._e_o_proprio_instrumento(
        pathlib.Path(mi.__file__).read_text(encoding="utf-8"))


def test_o_instrumento_nao_compra_a_propria_regua_como_prova(mi, tmp_path):
    """O defeito foi REAL, e ele é deste arquivo — medido em 20/09/2026."""
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


def test_o_piso_nao_pode_ser_esvaziado_em_silencio(mi):
    """O piso é a catraca inteira, e até aqui NINGUÉM olhava para ele."""
    piso = mi.COM_REGUA_EM_20260920
    assert piso, (
        "a catraca foi esvaziada: com o piso vazio, apagar a régua de "
        "qualquer decisão dela volta a ser VERDE")

    assert len(set(piso)) == len(piso), (
        f"o piso tem nome repetido: {sorted(n for n in set(piso) if piso.count(n) > 1)}"
        f" — repetição segura a contagem e não cobre decisão nenhuma")
    assert len(set(piso)) >= PISO_MEDIDO_EM_20260920, (
        f"o piso encolheu de {PISO_MEDIDO_EM_20260920} para {len(set(piso))} "
        f"sem que este número descesse junto. Piso que encolhe calado não é "
        f"catraca: ele isenta a próxima régua apagada")

    assert "D-AUDIO-E-GIRO-NASCEM-LIGADOS" in piso, (
        "a decisão que ORIGINOU esta sprint saiu do piso — ela ficou 23 dias "
        "«decidida» com o microfone mudo, e é a última que pode perder a "
        "catraca")

    medida = mi.medir()
    fantasmas = sorted(set(piso) - set(medida["com_regua_dentro_de_teste"]))
    assert not fantasmas, (
        f"o piso cita decisão que régua nenhuma mede hoje: {fantasmas}")


def test_o_instrumento_tambem_nao_se_conta_fora_de_tests(mi, tmp_path):
    """O CHAMADOR QUE FICOU DE FORA — achado pela conferência, 20/09/2026."""
    scripts = tmp_path / "scripts"
    scripts.mkdir(parents=True, exist_ok=True)
    (scripts / "fala_do_instrumento.py").write_text(
        '"""Roda o medir_decisoes_sem_prova e confere a D-DO-INSTRUMENTO."""\n',
        encoding="utf-8")
    (scripts / "codigo_de_verdade.py").write_text(
        "# nasceu da D-DE-VERDADE, e a implementa\n", encoding="utf-8")

    fora = mi.citadas_fora_de_tests(["D-DO-INSTRUMENTO", "D-DE-VERDADE"],
                                    tmp_path)
    assert "D-DO-INSTRUMENTO" not in fora, (
        "o arquivo que fala do instrumento contou como citação de uma decisão")
    assert "D-DE-VERDADE" in fora, (
        "a exclusão engoliu script de verdade junto — ela é derivada do NOME "
        "do módulo, e não pode virar uma peneira")

    linhas = mi._linhas()
    ids = [ln["id"] for ln in linhas if ln.get("estado") == "decidida"]
    onde = mi.citadas_fora_de_tests(ids, RAIZ)
    culpados = sorted(i for i, caminhos in onde.items()
                      if any("medir_decisoes_sem_prova" in c for c in caminhos))
    assert not culpados, (
        f"o próprio instrumento aparece como prova de {len(culpados)} "
        f"decisão(ões): {culpados}")


def test_o_laudo_sem_bandeira_recusa_csv_de_forma_errada(mi, tmp_path, capsys):
    """Traceback não é resposta — achado pela conferência, 20/09/2026."""
    alvo = _csv_de_mentira(
        tmp_path / "sem_estado.csv",
        [{"id": "D-QUALQUER", "titulo": "t"}],
        colunas=("id", "titulo", "onde_mora", "decidida_em"),
    )
    mi.CSV_DAS_DECISOES = alvo
    mi.RAIZ = tmp_path
    try:
        assert mi.main([]) == 1, (
            "o laudo seco contou sobre um CSV que já não sabe ler")
    finally:
        mi.CSV_DAS_DECISOES = RAIZ / "docs" / "data" / "decisoes-dela.csv"
        mi.RAIZ = RAIZ
    saida = capsys.readouterr().out
    assert "VERMELHO" in saida and "estado" in saida
    assert "MEDIÇÃO 1" not in saida, (
        "imprimiu o laudo assim mesmo — número sobre chão que cedeu")


def test_a_medicao_de_hoje_bate_com_o_csv_de_hoje(mi):
    """O censo da sprint conferido contra o arquivo, não contra a lembrança."""
    medida = mi.medir()
    assert medida["decididas"] == medida["linhas"] - 3, (
        "o CSV tem três linhas `caduca`; se isso mudou, o laudo tem de dizer")
    assert medida["decididas"] > 0
    assert len(medida["com_regua_dentro_de_teste"]) <= medida["decididas"]
    assert set(medida["com_regua_dentro_de_teste"]).isdisjoint(
        medida["citadas_so_no_cabecalho"]), (
        "uma decisão não pode estar nos dois baldes ao mesmo tempo")
