"""O grau forte do mapa exige ensaio no caderno de bancada — ou o portão reprova.

O DEFEITO QUE ORIGINOU ESTE ARQUIVO, medido em 12/08/2026 por mutação numa cópia
da árvore: um agente escreveu a afirmação mais forte que o vocabulário da casa
permite — `cabo_ate_onde_foi = radio_ate_onde_foi = O APARELHO OBEDECEU`,
`provado_por =
olho-dela`, `provado_em` de hoje — numa linha com ZERO ensaios em
`docs/data/ensaios.csv`, e `scripts/check_paridade_transporte.py` devolveu
exatamente o mesmo número de reprovações de antes. A mentira passou inteira,
porque o portão não mencionava o caderno de bancada uma única vez.

O caso central deste arquivo é literalmente aquela mutação. E junto vem o caso
SIMÉTRICO — linha com grau forte E ensaio correspondente passa —, sem o qual a
regra viraria "grau é proibido", que é uma forma de o portão mentir ao contrário.

19/08/2026 — A ESCADA GANHOU A DIREÇÃO DE ENTRADA. Até esta data os três
degraus cobriam só a IDA (produto → aparelho), e o mapa admitia o buraco por
escrito em duas linhas suas: o vpad ENTREGA, e ninguém sabia se o jogo REAGE. A
segunda metade deste arquivo cobra os dois degraus novos — `O JOGO RECEBEU` e
`O JOGO REAGIU` — com a mesma severidade dos fortes de saída, e mais uma: o
degrau que só a mão dela fecha DERRUBA, não avisa.

PROVA DE QUE MORDEM (arrancar, ver reprovar, devolver), 12/08/2026 e
19/08/2026: está na docstring de cada teste, uma cura de cada vez, com a saída
literal do `pytest`.
"""
from __future__ import annotations

import csv
import subprocess
import sys
from pathlib import Path

# Reuso deliberado do arquivo irmão (o dos testes das regras 1 a 5, 7 e 8): o
# jeito de importar o script como módulo, o `tests/` de mentira e o cabeçalho
# mínimo já estão medidos lá, e duas cópias divergiriam no dia em que uma coluna
# entrasse. O que este arquivo acrescenta é o CADERNO — que o irmão não escreve.
from tests.unit.test_check_paridade_transporte import (
    CABECALHO as CABECALHO_DO_IRMAO,
)
from tests.unit.test_check_paridade_transporte import (
    RAIZ_REAL,
    SCRIPT,
    TESTE_FALSO,
    modulo_do_censo,
)

ENSAIOS_REAIS = RAIZ_REAL / "docs" / "data" / "ensaios.csv"
CSV_REAL = RAIZ_REAL / "docs" / "data" / "mapa-controles.csv"

#: O cabeçalho do irmão mais a coluna que a regra 11 lê. Ela fica FORA do
#: mínimo exigido de propósito — regra de aviso não derruba árvore que ainda não
#: tem a coluna —, então é aqui que ela entra.
CABECALHO = [*CABECALHO_DO_IRMAO, "mordida_provada_em"]

#: As colunas do caderno de bancada, na ordem do arquivo real. `linha_id` e
#: `transporte` são as que fazem o casamento; `resultado` e `observado_por` são
#: as que as regras 9 e 10 leem.
CABECALHO_DO_CADERNO = [
    "id",
    "linha_id",
    "transporte",
    # ENSAIO-QUE-NAO-DIZ-O-DEGRAU-01 (20/08/2026): o que ESTE ensaio mediu.
    # Junto de `transporte` porque é o mesmo tipo de eixo.
    "degrau",
    "quando",
    "suspeito",
    "presente",
    "resultado",
    "observado_por",
    "fonte",
    "nota",
]


def ensaio(
    linha_id: str,
    transporte: str,
    *,
    resultado: str = "obedece",
    observado_por: str = "olho-dela",
    identificador: str = "ensaio-de-mentira",
    degrau: str = "",
) -> dict[str, str]:
    """Uma linha do caderno, com o mínimo que o casamento e as regras leem.

    `degrau` (ENSAIO-QUE-NAO-DIZ-O-DEGRAU-01, 20/08/2026) nasce VAZIO porque é
    assim que os 177 ensaios do caderno nasceram, e é assim que a maioria dos
    testes daqui quer o dublê. Quem estiver aferindo um degrau de ENTRADA tem de
    passá-lo — que é exatamente a exigência nova, e vale para o dublê tanto
    quanto para o caderno de verdade.
    """
    return {
        "id": identificador,
        "linha_id": linha_id,
        "transporte": transporte,
        "degrau": degrau,
        "quando": "2026-08-12T10:00:00",
        "suspeito": "o suspeito de mentira deste ensaio",
        "presente": "sim",
        "resultado": resultado,
        "observado_por": observado_por,
        "fonte": "bancada de mentira",
        "nota": "escrito por um teste",
    }


def linha_com_grau(**mudancas: str) -> dict[str, str]:
    """A linha da mutação de 12/08: o degrau mais alto, nos dois transportes.

    A chave é a mesma que o agente usou (`audio.jack.deteccao@pro`), e o
    `teste_que_morde` aponta um teste REAL de outra feature — que é o que fazia
    a mentira atravessar as regras 1 e 2 sem um arranhão.
    """
    base = {
        "chave": "audio.jack.deteccao",
        "controle": "pro",
        "existe": "tem",
        "cabo_aciona": "sim",
        "radio_aciona": "sim",
        "cabo_de_onde_sei": "medido",
        "radio_de_onde_sei": "medido",
        "cabo_canal": "hidraw",
        "radio_canal": "hidraw",
        "cabo_ate_onde_foi": "O APARELHO OBEDECEU",
        "radio_ate_onde_foi": "O APARELHO OBEDECEU",
        "teste_que_morde": "tests/unit/test_exemplo.py::test_a_lightbar_acende",
        "provado_em": "2026-08-12",
        "id": "audio.jack.deteccao@pro",
    }
    base.update(mudancas)
    return base


def monta_arvore(
    tmp_path: Path,
    linhas: list[dict[str, str]],
    ensaios: list[dict[str, str]] | None,
    *,
    cabecalho: list[str] | None = None,
) -> Path:
    """Uma árvore mínima com CADERNO: o mapa, o `tests/`, o `specs.html` e os ensaios.

    `ensaios=None` significa "esta árvore não tem caderno nenhum" — que é o caso
    em que a regra 6 tem de se DESLIGAR em voz alta, e não acusar todo mundo.
    """
    colunas = cabecalho if cabecalho is not None else CABECALHO
    caminho_csv = tmp_path / "docs" / "data" / "mapa-controles.csv"
    caminho_csv.parent.mkdir(parents=True, exist_ok=True)
    with caminho_csv.open("w", encoding="utf-8", newline="") as arquivo:
        escritor = csv.DictWriter(arquivo, fieldnames=colunas)
        escritor.writeheader()
        for linha in linhas:
            escritor.writerow({coluna: linha.get(coluna, "") for coluna in colunas})

    if ensaios is not None:
        caminho_caderno = tmp_path / "docs" / "data" / "ensaios.csv"
        with caminho_caderno.open("w", encoding="utf-8", newline="") as arquivo:
            escritor = csv.DictWriter(arquivo, fieldnames=CABECALHO_DO_CADERNO)
            escritor.writeheader()
            for registro in ensaios:
                escritor.writerow(registro)

    pasta_de_testes = tmp_path / "tests" / "unit"
    pasta_de_testes.mkdir(parents=True, exist_ok=True)
    (pasta_de_testes / "test_exemplo.py").write_text(TESTE_FALSO, encoding="utf-8")

    (tmp_path / "specs.html").write_text(
        "<html><body>" + " ".join(linha.get("id", "") for linha in linhas) + "</body></html>",
        encoding="utf-8",
    )
    return caminho_csv


def rodar(caminho_csv: Path, raiz: Path) -> subprocess.CompletedProcess[str]:
    return subprocess.run(
        [sys.executable, str(SCRIPT), "--raiz", str(raiz), "--csv", str(caminho_csv)],
        capture_output=True,
        text=True,
        check=False,
    )


# --------------------------------------------------------------------------
# REGRA 6 — grau-sem-ensaio. O caso central é a mutação de 12/08.
# --------------------------------------------------------------------------
def test_o_aparelho_obedeceu_sem_um_ensaio_no_caderno_reprova(tmp_path: Path) -> None:
    """MORDIDA MEDIDA: trocado o `if not ensaios:` de `_regra_do_caderno` por
    `if False:` (o grau forte deixa de cobrar bancada). Reprovaram TRÊS testes:
    este, o do ensaio que é do outro transporte, e o
    `test_o_censo_conta_o_mesmo_que_uma_regua_independente_de_grau`, que viu a
    régua achar zero onde a contagem à mão, feita contra o mapa real na hora,
    achava quatro. Cura devolvida.

    O caderno DESTA árvore não está vazio: ele tem um ensaio de outra linha. Sem
    isso o teste passaria pelo motivo errado — o de a regra estar desligada por
    falta de caderno.
    """
    caminho = monta_arvore(
        tmp_path,
        [linha_com_grau()],
        [ensaio("luz.lightbar.cor@dualsense", "radio")],
    )
    processo = rodar(caminho, tmp_path)
    assert processo.returncode == 1, processo.stdout
    assert processo.stdout.count("FALHA grau-sem-ensaio:") == 2, processo.stdout
    assert "audio.jack.deteccao@pro" in processo.stdout
    assert "docs/data/ensaios.csv" in processo.stdout


def test_grau_forte_com_ensaio_dos_dois_lados_passa(tmp_path: Path) -> None:
    """O caso SIMÉTRICO, sem o qual a regra viraria "grau é proibido".

    Um portão que reprova toda afirmação forte não protege nada: ele só ensina a
    baixar o grau para calar o portão, que é a mesma mentira ao contrário.
    """
    caminho = monta_arvore(
        tmp_path,
        [linha_com_grau(mordida_provada_em="2026-08-12")],
        [
            ensaio("audio.jack.deteccao@pro", "cabo", identificador="ensaio-cabo"),
            ensaio("audio.jack.deteccao@pro", "radio", identificador="ensaio-radio"),
        ],
    )
    processo = rodar(caminho, tmp_path)
    assert processo.returncode == 0, processo.stdout
    assert "grau-sem-ensaio" not in processo.stdout


def test_ensaio_do_radio_nao_sustenta_o_grau_do_cabo(tmp_path: Path) -> None:
    """O casamento é por transporte, e é o coração deste mapa.

    A frase dela que fez este mapa existir foi "tínhamos algo para o cabo e na
    hora do vamos ver a versão de BT não funcionava". Aceitar ensaio de um lado
    como prova do outro seria escrever essa regressão dentro do portão.
    """
    caminho = monta_arvore(
        tmp_path,
        [linha_com_grau()],
        [ensaio("audio.jack.deteccao@pro", "radio")],
    )
    processo = rodar(caminho, tmp_path)
    assert processo.returncode == 1, processo.stdout
    assert processo.stdout.count("FALHA grau-sem-ensaio:") == 1, processo.stdout
    assert "[cabo]" in processo.stdout


def test_saiu_no_fio_se_sustenta_com_ensaio_que_nega(tmp_path: Path) -> None:
    """O degrau do meio pede que ALGUÉM tenha posto no fio — não que tenha dado certo.

    `SAIU NO FIO` é "o byte saiu, algo voltou". Um ensaio cujo resultado é `não
    obedece` é exatamente isso: o byte saiu e o aparelho não fez. Cobrar
    obediência aqui confundiria os dois degraus da escada.
    """
    caminho = monta_arvore(
        tmp_path,
        [linha_com_grau(cabo_ate_onde_foi="SAIU NO FIO", radio_ate_onde_foi="SAIU NO FIO")],
        [
            ensaio("audio.jack.deteccao@pro", "cabo", resultado="não obedece"),
            ensaio(
                "audio.jack.deteccao@pro",
                "radio",
                resultado="não obedece",
                identificador="outro",
            ),
        ],
    )
    processo = rodar(caminho, tmp_path)
    assert processo.returncode == 0, processo.stdout


def test_montou_nao_pede_ensaio_nenhum(tmp_path: Path) -> None:
    """`MONTOU` é o que a suíte prova sozinha: pedir bancada para ele seria cobrar
    aparelho por algo que o pytest já morde."""
    caminho = monta_arvore(
        tmp_path,
        [linha_com_grau(cabo_ate_onde_foi="MONTOU", radio_ate_onde_foi="MONTOU")],
        [],
    )
    processo = rodar(caminho, tmp_path)
    assert processo.returncode == 0, processo.stdout


def test_sem_caderno_a_regra_se_desliga_em_vez_de_acusar_tudo(tmp_path: Path) -> None:
    """Caderno ausente não pode virar "todo grau é mentira".

    É a mesma decisão do índice de testes por AST: um gate que reprova tudo
    quando tropeça é pior que gate nenhum. E o desligamento é DITO no resumo.
    """
    caminho = monta_arvore(tmp_path, [linha_com_grau()], None)
    processo = rodar(caminho, tmp_path)
    assert processo.returncode == 0, processo.stdout
    assert "regra DESLIGADA" in processo.stdout
    assert "grau-sem-ensaio" in processo.stdout


# --------------------------------------------------------------------------
# REGRA 4 — o domínio do grau, que é a porta lateral da mentira
# --------------------------------------------------------------------------
def test_grau_fora_da_escada_reprova(tmp_path: Path) -> None:
    """MORDIDA MEDIDA: apagada a entrada `"ate_onde_foi"` de `DOMINIO_POR_SUFIXO`.
    Reprovaram os dois casos deste teste, e mais nenhum. Cura devolvida.

    O caso minúsculo é o que importa: sem domínio, `o aparelho obedeceu` escrito
    em caixa baixa não casaria com `GRAUS_QUE_EXIGEM_ENSAIO` e sairia pela porta
    que a régua não olha — afirmação máxima, custo zero.
    """
    for valor in ("FUNCIONA", "o aparelho obedeceu"):
        caminho = monta_arvore(
            tmp_path,
            [linha_com_grau(cabo_ate_onde_foi=valor, radio_ate_onde_foi="MONTOU")],
            [],
        )
        processo = rodar(caminho, tmp_path)
        assert processo.returncode == 1, f"{valor}\n{processo.stdout}"
        assert "fora do domínio" in processo.stdout
        assert "cabo_ate_onde_foi" in processo.stdout


def test_a_coluna_de_grau_que_some_do_cabecalho_reprova(tmp_path: Path) -> None:
    """Regra dura não se desliga em silêncio: sem a coluna, não há régua."""
    cabecalho = [coluna for coluna in CABECALHO if coluna != "radio_ate_onde_foi"]
    caminho = monta_arvore(tmp_path, [linha_com_grau()], [], cabecalho=cabecalho)
    processo = rodar(caminho, tmp_path)
    assert processo.returncode == 1, processo.stdout
    assert "integridade" in processo.stdout
    assert "radio_ate_onde_foi" in processo.stdout


# --------------------------------------------------------------------------
# REGRA 9 — o resultado que nega (AVISO hoje, FALHA quando alguém mandar)
# --------------------------------------------------------------------------
def test_obedeceu_sustentado_so_por_ensaio_que_nega_avisa_e_nao_derruba(
    tmp_path: Path,
) -> None:
    """AVISO, e o motivo está no cabeçalho do portão: `resultado` é texto livre e
    a semântica dele é do SUSPEITO, não da feature.

    O caso real é o `gatilho-lado-nao-esta-invertido`: gravado como `não
    obedece` (o suspeito "o mapeamento está invertido" foi eliminado) enquanto a
    nota do mesmo ensaio diz que o R2 endureceu. Reprovar isso seria derrubar
    uma afirmação verdadeira por causa de uma coluna que responde outra
    pergunta.
    """
    caminho = monta_arvore(
        tmp_path,
        [linha_com_grau(radio_ate_onde_foi="MONTOU")],
        [ensaio("audio.jack.deteccao@pro", "cabo", resultado="não obedece")],
    )
    processo = rodar(caminho, tmp_path)
    assert processo.returncode == 0, processo.stdout
    assert "AVISO grau-sem-ensaio-que-obedeca" in processo.stdout
    assert "não obedece" in processo.stdout


def test_a_promocao_do_resultado_e_uma_constante_que_funciona(tmp_path: Path) -> None:
    """A promoção prometida no cabeçalho tem de ser real, não decorativa.

    Sem este teste, `RESULTADO_REPROVA` seria mais uma cura escrita e nunca
    ligada — o defeito mais caro desta casa.
    """
    censo = modulo_do_censo()
    caminho = monta_arvore(
        tmp_path,
        [linha_com_grau(radio_ate_onde_foi="MONTOU")],
        [ensaio("audio.jack.deteccao@pro", "cabo", resultado="não obedece")],
    )
    censo.RESULTADO_REPROVA = True
    achados, _, _ = censo.censo(caminho, tmp_path, censo.date(2026, 8, 12))
    niveis = {a.nivel for a in achados if a.regra == "grau-sem-ensaio-que-obedeca"}
    assert niveis == {censo.FALHA}


# --------------------------------------------------------------------------
# REGRA 10 — o olho dela (AVISO hoje; hoje ele custa zero reprovação)
# --------------------------------------------------------------------------
def test_ensaio_sem_o_olho_dela_avisa_e_nao_derruba(tmp_path: Path) -> None:
    """`METODO-DE-ISOLAMENTO.md` diz que só `olho-dela` sustenta o degrau mais
    alto. Ele AVISA e não reprova porque ela aprovou uma frase — "grau forte
    exige ensaio correspondente" — e cobrar QUEM observou é uma segunda regra,
    que ninguém pediu.
    """
    caminho = monta_arvore(
        tmp_path,
        [linha_com_grau(radio_ate_onde_foi="MONTOU")],
        [ensaio("audio.jack.deteccao@pro", "cabo", observado_por="bancada")],
    )
    processo = rodar(caminho, tmp_path)
    assert processo.returncode == 0, processo.stdout
    assert "AVISO grau-sem-olho-dela" in processo.stdout


def test_a_promocao_do_olho_dela_e_uma_constante_que_funciona(tmp_path: Path) -> None:
    censo = modulo_do_censo()
    caminho = monta_arvore(
        tmp_path,
        [linha_com_grau(radio_ate_onde_foi="MONTOU")],
        [ensaio("audio.jack.deteccao@pro", "cabo", observado_por="bancada")],
    )
    censo.OLHO_DELA_REPROVA = True
    achados, _, _ = censo.censo(caminho, tmp_path, censo.date(2026, 8, 12))
    niveis = {a.nivel for a in achados if a.regra == "grau-sem-olho-dela"}
    assert niveis == {censo.FALHA}


# --------------------------------------------------------------------------
# REGRA 11 — a mordida que ninguém provou (a coluna que existia e ninguém lia)
# --------------------------------------------------------------------------
def test_grau_forte_com_teste_sem_mordida_provada_avisa(tmp_path: Path) -> None:
    """MORDIDA MEDIDA: trocado o `if (linha.get("mordida_provada_em") or "").strip():`
    de `_regra_da_mordida_nao_provada` por `if True:` (nunca avisa). Reprovaram
    este teste e mais nenhum. Cura devolvida.

    Medido em 12/08/2026: `mordida_provada_em` estava vazia em 293 de 293 linhas
    e nenhuma regra a lia. Um teste apontado e nunca arrancado é a regra da casa
    escrita e não cumprida.
    """
    caminho = monta_arvore(
        tmp_path,
        [linha_com_grau()],
        [
            ensaio("audio.jack.deteccao@pro", "cabo", identificador="a"),
            ensaio("audio.jack.deteccao@pro", "radio", identificador="b"),
        ],
    )
    processo = rodar(caminho, tmp_path)
    assert processo.returncode == 0, processo.stdout
    assert "AVISO mordida-nao-provada" in processo.stdout


def test_a_data_da_mordida_silencia_o_aviso(tmp_path: Path) -> None:
    caminho = monta_arvore(
        tmp_path,
        [linha_com_grau(mordida_provada_em="2026-08-12")],
        [
            ensaio("audio.jack.deteccao@pro", "cabo", identificador="a"),
            ensaio("audio.jack.deteccao@pro", "radio", identificador="b"),
        ],
    )
    processo = rodar(caminho, tmp_path)
    # O `returncode` vem ANTES da busca no texto de propósito: sem ele, um
    # portão que estourasse devolveria stdout vazio e este teste — o único
    # negativo da regra 11 — passaria justamente quando tudo quebrou.
    assert processo.returncode == 0, processo.stdout
    assert "mordida-nao-provada" not in processo.stdout


def test_sem_a_coluna_da_mordida_a_regra_onze_se_desliga(tmp_path: Path) -> None:
    """Regra de AVISO se desliga quando falta a coluna; a DURA reprova.

    A distinção é deliberada: derrubar uma árvore inteira por causa de uma
    coluna que só alimenta aviso seria cobrar caro por pouco.
    """
    cabecalho = [coluna for coluna in CABECALHO if coluna != "mordida_provada_em"]
    caminho = monta_arvore(
        tmp_path,
        [linha_com_grau()],
        [
            ensaio("audio.jack.deteccao@pro", "cabo", identificador="a"),
            ensaio("audio.jack.deteccao@pro", "radio", identificador="b"),
        ],
        cabecalho=cabecalho,
    )
    processo = rodar(caminho, tmp_path)
    assert processo.returncode == 0, processo.stdout
    assert "regra DESLIGADA" in processo.stdout
    assert "mordida-nao-provada" in processo.stdout


# --------------------------------------------------------------------------
# A ÁRVORE REAL — a régua conferida contra uma contagem independente
# --------------------------------------------------------------------------
def test_o_censo_conta_o_mesmo_que_uma_regua_independente_de_grau() -> None:
    """O instrumento mente mais que o produto: esta é a contraprova dele.

    A contagem à mão aqui NÃO usa o `eliminacao.py` — ela relê o caderno com um
    `csv.DictReader` próprio, justamente para não repetir o mesmo erro dos dois
    lados. Nenhum número fica escrito: os dois são medidos na hora.
    """
    processo = subprocess.run(
        [sys.executable, str(SCRIPT)],
        capture_output=True,
        text=True,
        check=False,
        cwd=RAIZ_REAL,
    )
    assert processo.returncode in (0, 1), processo.stdout + processo.stderr

    with ENSAIOS_REAIS.open(encoding="utf-8", newline="") as arquivo:
        lados_com_ensaio = {
            ((registro["linha_id"] or "").strip(), (registro["transporte"] or "").strip())
            for registro in csv.DictReader(arquivo)
        }
    with CSV_REAL.open(encoding="utf-8", newline="") as arquivo:
        linhas = list(csv.DictReader(arquivo))

    esperado = sum(
        1
        for linha in linhas
        for lado in ("cabo", "radio")
        # A régua independente redigita a lista DE PROPÓSITO: importar a do
        # portão faria o instrumento conferir a si mesmo. Os dois degraus de
        # ENTRADA (19/08/2026) entram aqui pela mesma razão que os de saída —
        # eles também exigem ensaio, e a contagem tem de enxergá-los.
        if (linha[f"{lado}_ate_onde_foi"] or "").strip()
        in ("SAIU NO FIO", "O APARELHO OBEDECEU", "O JOGO RECEBEU", "O JOGO REAGIU")
        and ((linha["id"] or "").strip(), lado) not in lados_com_ensaio
    )
    achadas = processo.stdout.count("FALHA grau-sem-ensaio:")
    assert achadas == esperado, (
        f"a régua achou {achadas} grau(s) forte(s) sem ensaio e a contagem "
        f"independente achou {esperado}"
    )


# --------------------------------------------------------------------------
# A DIREÇÃO DE ENTRADA — os dois degraus de 19/08/2026
#
# Até esta data a escada cobria só a IDA (produto -> aparelho), e dá para
# conferir no dado: `O APARELHO OBEDECEU` só aparece em linha de saída. O mapa
# admitia o buraco por escrito em duas linhas suas (`toque.touchpad` e
# `movimento.giroscopio.jogo`): o vpad ENTREGA, e ninguém sabe se o jogo REAGE.
# Era possível o mapa inteiro ficar verde enquanto ela não conseguia jogar.
#
# Os casos abaixo provam três coisas, e a terceira é a que dá sentido a haver
# DOIS degraus novos em vez de um: `O JOGO RECEBEU` um instrumento fecha, `O
# JOGO REAGIU` não.
# --------------------------------------------------------------------------
DEGRAUS_DE_ENTRADA = ("O JOGO RECEBEU", "O JOGO REAGIU")


def test_os_degraus_do_jogo_sem_ensaio_reprovam_igual_aos_de_saida(
    tmp_path: Path,
) -> None:
    """MORDIDA MEDIDA (19/08/2026): trocado, em `check_paridade_transporte.py`,

        GRAUS_QUE_EXIGEM_ENSAIO = tuple(
            degrau.valor for degrau in ESCADA if degrau.fechado_por != FECHA_A_SUITE
        )

    por `... if degrau.direcao == DIRECAO_SAIDA and degrau.fechado_por != ...`
    — isto é, os degraus novos entram no vocabulário mas ninguém lhes cobra
    bancada. Saída LITERAL de `pytest -q`:

        E       AssertionError: OK: nenhuma afirmação forte sem rede em mapa-controles.csv.
        E         ...
        E           graus que a suíte não sustenta sozinha...... 0
        E                desses, SEM ensaio no caderno.......... 0
        E                desses, na direção de ENTRADA (o jogo). 0
        E       assert 0 == 1
        FAILED ...::test_os_degraus_do_jogo_sem_ensaio_reprovam_igual_aos_de_saida
        FAILED ...::test_o_jogo_reagiu_sem_o_olho_dela_derruba_e_nao_apenas_avisa
        2 failed, 20 passed in 1.65s

    A linha do resumo é a prova mais limpa: o censo dizia `graus que a suíte não
    sustenta sozinha: 0` com um `O JOGO RECEBEU` escrito na célula. Cura
    devolvida, 22 verdes.

    O caderno desta árvore NÃO está vazio: tem um ensaio de outra linha. Sem
    isso o teste passaria pelo motivo errado — o de a regra 6 estar desligada
    por falta de caderno.
    """
    for degrau in DEGRAUS_DE_ENTRADA:
        caminho = monta_arvore(
            tmp_path,
            [linha_com_grau(cabo_ate_onde_foi=degrau, radio_ate_onde_foi="MONTOU")],
            [ensaio("luz.lightbar.cor@dualsense", "radio")],
        )
        processo = rodar(caminho, tmp_path)
        assert processo.returncode == 1, f"{degrau}\n{processo.stdout}"
        assert processo.stdout.count("FALHA grau-sem-ensaio:") == 1, (
            f"{degrau}\n{processo.stdout}"
        )
        assert degrau in processo.stdout


def test_o_jogo_recebeu_fecha_com_instrumento_e_nao_pede_o_olho_dela(
    tmp_path: Path,
) -> None:
    """O degrau que um INSTRUMENTO vê, e é isto que o separa do de cima.

    "O processo do jogo abriu o nó do nosso vpad" é observável de fora: o inode
    do nó (`stat -c %i`, nunca o caminho — o minor é reciclado) aparece em
    `/proc/<pid>/fd` de um processo da árvore do jogo, que é visível do
    hospedeiro. Um ensaio de bancada fecha, e o portão TEM de deixar passar:
    exigir o olho dela aqui seria cobrar a pessoa por uma medida que a máquina
    faz — e um portão que cobra o impossível ensina a baixar o grau para calar,
    que é a mesma mentira ao contrário.
    """
    caminho = monta_arvore(
        tmp_path,
        [
            linha_com_grau(
                cabo_ate_onde_foi="O JOGO RECEBEU",
                radio_ate_onde_foi="MONTOU",
                mordida_provada_em="2026-08-19",
            )
        ],
        [
            ensaio(
                "audio.jack.deteccao@pro",
                "cabo",
                degrau=DEGRAUS_DE_ENTRADA[0],
                observado_por="bancada",
            )
        ],
    )
    processo = rodar(caminho, tmp_path)
    assert processo.returncode == 0, processo.stdout
    assert "reagiu-sem-olho-dela" not in processo.stdout
    assert "grau-sem-olho-dela" not in processo.stdout


def test_o_jogo_reagiu_sem_o_olho_dela_derruba_e_nao_apenas_avisa(
    tmp_path: Path,
) -> None:
    """MORDIDA MEDIDA (19/08/2026): trocado o `FALHA` do ramo
    `if grau in GRAUS_SEM_LEGADO:` de `_achado_sem_olho_dela` por
    `FALHA if OLHO_DELA_REPROVA else AVISO` — isto é, o degrau novo passaria a
    só avisar, como o da lightbar. Saída LITERAL de `pytest -q`:

        E       AssertionError: 1 aviso(s) — não derrubam este portão hoje:
        E           AVISO reagiu-sem-olho-dela: linha 2 (audio.jack.deteccao@pro)
        E           [cabo]: declara `cabo_ate_onde_foi = O JOGO REAGIU` no cabo com
        E           ensaio observado por ['bancada']. Este degrau NÃO tem
        E           instrumento: nenhuma régua desta casa lê o estado interno de um
        E           jogo sob Proton. Só `olho-dela` o fecha — grave o ensaio com o
        E           gesto dela, ou desça para `O JOGO RECEBEU`, que é o que um
        E           instrumento consegue ver de fora
        E
        E         OK: nenhuma afirmação forte sem rede em mapa-controles.csv.
        E       assert 0 == 1
        FAILED ...::test_o_jogo_reagiu_sem_o_olho_dela_derruba_e_nao_apenas_avisa
        1 failed, 21 passed in 1.71s

    (o AVISO acima sai numa linha só; foi quebrado aqui para caber na régua de
    100 colunas do `ruff`, e nada mais)

    Repare no `OK:` logo abaixo do aviso — é exatamente o retrato do defeito: o
    portão dizia OK sobre uma célula que afirma que ELA CONSEGUIU JOGAR, com um
    ensaio que ninguém do `olho-dela` observou. Cura devolvida.

    POR QUE DURA, e a regra 10 irmã não: é LEGADO, não princípio. A regra 10
    nasceu com células já escritas por outra régua, e reprovar retroativamente
    afirmação verdadeira é o defeito que o portão inteiro existe para não
    cometer. Este degrau nasceu em 19/08/2026 com ZERO células no CSV — não há
    afirmação antiga para machucar, e deixá-lo avisando abriria de graça a porta
    que a regra 6 fechou em 12/08.
    """
    caminho = monta_arvore(
        tmp_path,
        [
            linha_com_grau(
                cabo_ate_onde_foi="O JOGO REAGIU",
                radio_ate_onde_foi="MONTOU",
                mordida_provada_em="2026-08-19",
            )
        ],
        [
            ensaio(
                "audio.jack.deteccao@pro",
                "cabo",
                degrau=DEGRAUS_DE_ENTRADA[1],
                observado_por="bancada",
            )
        ],
    )
    processo = rodar(caminho, tmp_path)
    assert processo.returncode == 1, processo.stdout
    assert "FALHA reagiu-sem-olho-dela:" in processo.stdout
    assert "O JOGO RECEBEU" in processo.stdout, (
        "a mensagem tem de oferecer o degrau que um instrumento consegue "
        f"fechar, senão ela só diz não:\n{processo.stdout}"
    )


def test_o_jogo_reagiu_com_o_olho_dela_passa(tmp_path: Path) -> None:
    """O caso SIMÉTRICO: com o gesto dela gravado, o degrau mais alto passa.

    Sem este teste a regra 13 viraria "`O JOGO REAGIU` é proibido", que é a
    mesma mentira ao contrário — e o degrau existe justamente para ela poder
    dizer, uma vez por jogo, que aquilo funcionou.
    """
    caminho = monta_arvore(
        tmp_path,
        [
            linha_com_grau(
                cabo_ate_onde_foi="O JOGO REAGIU",
                radio_ate_onde_foi="MONTOU",
                mordida_provada_em="2026-08-19",
            )
        ],
        [
            ensaio(
                "audio.jack.deteccao@pro",
                "cabo",
                degrau=DEGRAUS_DE_ENTRADA[1],
                observado_por="olho-dela",
            )
        ],
    )
    processo = rodar(caminho, tmp_path)
    assert processo.returncode == 0, processo.stdout
    assert "reagiu-sem-olho-dela" not in processo.stdout


def test_a_escada_tem_um_dono_so(tmp_path: Path) -> None:
    """MORDIDA MEDIDA (19/08/2026): devolvido ao `DOMINIO_POR_SUFIXO` do portão o
    `frozenset` literal de antes — os três degraus da ida escritos à mão, em vez
    de `{"", *VALORES_DA_ESCADA}`. Saída LITERAL de `pytest -q`:

        E       AssertionError: o domínio do portão e a `ESCADA` divergem:
        E           só no domínio: set()
        E           só na escada: {'O JOGO RECEBEU', 'O JOGO REAGIU'}
        E       assert {'', 'MONTOU'...'SAIU NO FIO'} == {'', 'MONTOU'...'SAIU NO FIO'}
        FAILED ...::test_o_jogo_recebeu_fecha_com_instrumento_e_nao_pede_o_olho_dela
        FAILED ...::test_o_jogo_reagiu_com_o_olho_dela_passa
        FAILED ...::test_a_escada_tem_um_dono_so
        3 failed, 19 passed in 1.65s

    SEGUNDA MORDIDA, na outra ponta: apagado `<em>O JOGO REAGIU</em> (...)` da
    legenda do `specs.html` publicado — o que aconteceria se alguém voltasse a
    escrever a legenda à mão. Saída LITERAL:

        E       AssertionError: `O JOGO REAGIU` está na escada e não na legenda
        E       do specs.html — rode `python3 scripts/gerar-mapa.py`
        1 failed in 0.15s

    As duas curas devolvidas, 22 verdes.

    Uma segunda lista do mesmo vocabulário é o defeito que este teste existe
    para não deixar voltar: até 19/08 o portão tinha os degraus num `frozenset`
    e o `gerar-mapa.py` os tinha escritos à mão na legenda do `specs.html`.
    Divergir quer dizer publicar uma página que descreve um domínio diferente do
    que o portão aceita.

    O QUE ESTE TESTE AINDA NÃO COBRE, dito na cara: `bancada.py` tem um
    `GRAUS = [...]` próprio (o seletor do formulário que grava no CSV). Ele é
    território de outra frente e não foi tocado — enquanto não importar
    `VALORES_DA_ESCADA`, o portão ACEITA os dois degraus novos e o formulário
    não os OFERECE.
    """
    censo = modulo_do_censo()
    valores = tuple(censo.VALORES_DA_ESCADA)

    dominio = set(censo.DOMINIO_POR_SUFIXO["ate_onde_foi"])
    esperado = {"", *valores}
    assert dominio == esperado, (
        "o domínio do portão e a `ESCADA` divergem:\n"
        f"  só no domínio: {dominio - esperado}\n"
        f"  só na escada: {esperado - dominio}"
    )

    # Todo degrau tem critério ESCRITO. Sem isso ele é adjetivo, e adjetivo é o
    # que este mapa existe para não aceitar.
    for degrau in censo.ESCADA:
        assert degrau.criterio.strip(), degrau.valor
        assert degrau.direcao in (censo.DIRECAO_SAIDA, censo.DIRECAO_ENTRADA), degrau.valor

    # A legenda publicada sai da escada, e o método a define em prosa. Os dois
    # têm de nomear os CINCO degraus, ou a página e a régua contam histórias
    # diferentes.
    publicado = (RAIZ_REAL / "specs.html").read_text(encoding="utf-8")
    metodo = (RAIZ_REAL / "docs" / "process" / "METODO-DE-ISOLAMENTO.md").read_text(
        encoding="utf-8"
    )
    for valor in valores:
        assert f"<em>{valor}</em>" in publicado, (
            f"`{valor}` está na escada e não na legenda do specs.html — rode "
            "`python3 scripts/gerar-mapa.py`"
        )
        assert valor in metodo, (
            f"`{valor}` está na escada e não no METODO-DE-ISOLAMENTO.md, que é "
            "onde o critério de cada degrau se escreve"
        )


def test_nenhuma_celula_do_mapa_real_usa_os_degraus_novos_sem_ensaio() -> None:
    """A leva que criou os degraus NÃO preencheu célula nenhuma, de propósito.

    `◌ ninguém respondeu` é VERDADE, e preencher por analogia destrói o valor
    deste arquivo: nada do que a onda de 19/08 construiu — o aviso na lightbar
    por modo, o gesto `PS + R3`, a ponte confirmada por jogo — foi visto em
    HARDWARE. Foi tudo dublê.

    Este teste NÃO proíbe preencher: ele exige que quem preencher traga o ensaio
    junto, que é a mesma conta da regra 6 conferida por uma régua independente —
    um `csv.DictReader` próprio, sem passar pelo `eliminacao.py`.
    """
    with ENSAIOS_REAIS.open(encoding="utf-8", newline="") as arquivo:
        lados_com_ensaio = {
            ((registro["linha_id"] or "").strip(), (registro["transporte"] or "").strip())
            for registro in csv.DictReader(arquivo)
        }
    with CSV_REAL.open(encoding="utf-8", newline="") as arquivo:
        linhas = list(csv.DictReader(arquivo))

    orfas = [
        ((linha["id"] or "").strip(), lado, grau)
        for linha in linhas
        for lado in ("cabo", "radio")
        if (grau := (linha[f"{lado}_ate_onde_foi"] or "").strip()) in DEGRAUS_DE_ENTRADA
        and ((linha["id"] or "").strip(), lado) not in lados_com_ensaio
    ]
    assert not orfas, (
        "célula com degrau de ENTRADA e nenhum ensaio no caderno daquele "
        f"transporte: {orfas}"
    )
