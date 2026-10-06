"""O grau forte do mapa exige ensaio no caderno de bancada — ou o portão reprova."""
from __future__ import annotations

import csv
import subprocess
import sys
from pathlib import Path

from tests.unit.test_check_paridade_transporte import (
    _specs_de,
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

CABECALHO = [*CABECALHO_DO_IRMAO, "mordida_provada_em"]

CABECALHO_DO_CADERNO = [
    "id",
    "linha_id",
    "transporte",
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
    """Uma linha do caderno, com o mínimo que o casamento e as regras leem."""
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
    """A linha da mutação de 12/08: o degrau mais alto, nos dois transportes."""
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
    """Uma árvore mínima com CADERNO: o mapa, o `tests/`, o `specs.html` e os ensaios."""
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

    _specs_de(tmp_path).write_text(
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


def test_o_aparelho_obedeceu_sem_um_ensaio_no_caderno_reprova(tmp_path: Path) -> None:
    """MORDIDA MEDIDA: trocado o `if not ensaios:` de `_regra_do_caderno` por"""
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
    """O caso SIMÉTRICO, sem o qual a regra viraria "grau é proibido"."""
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
    """O casamento é por transporte, e é o coração deste mapa."""
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
    """O degrau do meio pede que ALGUÉM tenha posto no fio — não que tenha dado certo."""
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
    """`MONTOU` é o que a suíte prova sozinha: pedir bancada para ele seria cobrar"""
    caminho = monta_arvore(
        tmp_path,
        [linha_com_grau(cabo_ate_onde_foi="MONTOU", radio_ate_onde_foi="MONTOU")],
        [],
    )
    processo = rodar(caminho, tmp_path)
    assert processo.returncode == 0, processo.stdout


def test_sem_caderno_a_regra_se_desliga_em_vez_de_acusar_tudo(tmp_path: Path) -> None:
    """Caderno ausente não pode virar "todo grau é mentira"."""
    caminho = monta_arvore(tmp_path, [linha_com_grau()], None)
    processo = rodar(caminho, tmp_path)
    assert processo.returncode == 0, processo.stdout
    assert "regra DESLIGADA" in processo.stdout
    assert "grau-sem-ensaio" in processo.stdout


def test_grau_fora_da_escada_reprova(tmp_path: Path) -> None:
    """MORDIDA MEDIDA: apagada a entrada `"ate_onde_foi"` de `DOMINIO_POR_SUFIXO`."""
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


def test_obedeceu_sustentado_so_por_ensaio_que_nega_avisa_e_nao_derruba(
    tmp_path: Path,
) -> None:
    """AVISO, e o motivo está no cabeçalho do portão: `resultado` é texto livre e"""
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
    """A promoção prometida no cabeçalho tem de ser real, não decorativa."""
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


def test_ensaio_sem_o_olho_dela_avisa_e_nao_derruba(tmp_path: Path) -> None:
    """`METODO-DE-ISOLAMENTO.md` diz que só `olho-dela` sustenta o degrau mais"""
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


def test_grau_forte_com_teste_sem_mordida_provada_avisa(tmp_path: Path) -> None:
    """MORDIDA MEDIDA: trocado o `if (linha.get("mordida_provada_em") or "").strip():`"""
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
    assert processo.returncode == 0, processo.stdout
    assert "mordida-nao-provada" not in processo.stdout


def test_sem_a_coluna_da_mordida_a_regra_onze_se_desliga(tmp_path: Path) -> None:
    """Regra de AVISO se desliga quando falta a coluna; a DURA reprova."""
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


def test_o_censo_conta_o_mesmo_que_uma_regua_independente_de_grau() -> None:
    """O instrumento mente mais que o produto: esta é a contraprova dele."""
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
        if (linha[f"{lado}_ate_onde_foi"] or "").strip()
        in ("SAIU NO FIO", "O APARELHO OBEDECEU", "O JOGO RECEBEU", "O JOGO REAGIU")
        and ((linha["id"] or "").strip(), lado) not in lados_com_ensaio
    )
    achadas = processo.stdout.count("FALHA grau-sem-ensaio:")
    assert achadas == esperado, (
        f"a régua achou {achadas} grau(s) forte(s) sem ensaio e a contagem "
        f"independente achou {esperado}"
    )


DEGRAUS_DE_ENTRADA = ("O JOGO RECEBEU", "O JOGO REAGIU")


def test_os_degraus_do_jogo_sem_ensaio_reprovam_igual_aos_de_saida(
    tmp_path: Path,
) -> None:
    """MORDIDA MEDIDA (19/08/2026): trocado, em `check_paridade_transporte.py`,"""
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
    """O degrau que um INSTRUMENTO vê, e é isto que o separa do de cima."""
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
    """MORDIDA MEDIDA (19/08/2026): trocado o `FALHA` do ramo"""
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
    """O caso SIMÉTRICO: com o gesto do usuário gravado, o degrau mais alto passa."""
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
    """MORDIDA MEDIDA (19/08/2026): devolvido ao `DOMINIO_POR_SUFIXO` do portão o"""
    censo = modulo_do_censo()
    valores = tuple(censo.VALORES_DA_ESCADA)

    dominio = set(censo.DOMINIO_POR_SUFIXO["ate_onde_foi"])
    esperado = {"", *valores}
    assert dominio == esperado, (
        "o domínio do portão e a `ESCADA` divergem:\n"
        f"  só no domínio: {dominio - esperado}\n"
        f"  só na escada: {esperado - dominio}"
    )

    for degrau in censo.ESCADA:
        assert degrau.criterio.strip(), degrau.valor
        assert degrau.direcao in (censo.DIRECAO_SAIDA, censo.DIRECAO_ENTRADA), degrau.valor

    publicado = (RAIZ_REAL / censo.SPECS_RELATIVO).read_text(encoding="utf-8")
    metodo = (RAIZ_REAL / "docs" / "method" / "METODO-DE-ISOLAMENTO.md").read_text(
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
    """A leva que criou os degraus NÃO preencheu célula nenhuma, de propósito."""
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
