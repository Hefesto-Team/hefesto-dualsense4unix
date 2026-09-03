"""O TERCEIRO NÚMERO tem régua, e a régua sabe RECUSAR.

O portão ``scripts/check_paridade_gtk_html.py`` confere
``docs/data/paridade-gtk-html.csv`` — 396 features medidas em 03/09/2026 — contra
o CÓDIGO DE HOJE. Este arquivo é o portão do portão, e ele existe por uma razão
medida: **régua que só sabe passar não é régua** (armadilha A2 desta casa).

O que ele prova, em três blocos:

1. **O DADO É ÍNTEGRO.** Cabeçalho, domínios, `(aba, feature)` sem repetição, e
   o par veredito↔``sinal_espera`` que é o coração da medição.
2. **O PORTÃO ESTÁ VERDE NESTA ÁRVORE.** Um portão que ninguém roda é arquivo;
   um portão que roda vermelho por dias é ruído. Aqui ele roda.
3. **O PORTÃO SABE RECUSAR** — e isto é o bloco que importa. Cada uma das oito
   regras é exercitada por DUBLÊ, com um CSV forjado em ``tmp_path``. Uma régua
   que reprova nada é indistinguível de uma régua desligada, e a única forma de
   separar as duas é arrancar a cura de propósito.

A MORDIDA DE VERDADE, provada à mão em 03/09 e reproduzida aqui pelos dublês:
  - apagar o ``html_onde`` de uma linha ``IGUAL``    -> ``sem-endereco``
  - apontar um endereço para além do fim do arquivo  -> ``endereco-morto``
  - criar, no lado HTML, o símbolo que uma linha ``FALTA_NO_HTML`` diz faltar
    -> ``divida-fechada``, que é a regra que impede o número de envelhecer calado
"""

from __future__ import annotations

import csv
import importlib.util
import subprocess
import sys
from collections import Counter
from pathlib import Path

import pytest

RAIZ = Path(__file__).resolve().parents[2]
REGUA = RAIZ / "scripts" / "check_paridade_gtk_html.py"
CSV = RAIZ / "docs" / "data" / "paridade-gtk-html.csv"
DOC = RAIZ / "docs" / "process" / "2026-09-03-O-TERCEIRO-NUMERO-a-paridade-com-a-gtk.md"


def _modulo():
    """A régua, importada do caminho — ela mora em ``scripts/``, não no pacote."""
    espec = importlib.util.spec_from_file_location("check_paridade_gtk_html_sob_ensaio", REGUA)
    assert espec is not None and espec.loader is not None
    modulo = importlib.util.module_from_spec(espec)
    sys.modules[espec.name] = modulo
    espec.loader.exec_module(modulo)
    return modulo


@pytest.fixture(scope="module")
def regua():
    return _modulo()


@pytest.fixture(scope="module")
def linhas() -> list[dict[str, str]]:
    with CSV.open(encoding="utf-8", newline="") as fh:
        return list(csv.DictReader(fh))


# ---------------------------------------------------------------------------
# 1. O DADO É ÍNTEGRO
# ---------------------------------------------------------------------------


def test_os_tres_arquivos_da_entrega_existem() -> None:
    for p in (REGUA, CSV, DOC):
        assert p.is_file(), f"{p.relative_to(RAIZ)} sumiu — a entrega são os três juntos."


def test_o_cabecalho_do_csv_e_o_que_a_regua_espera(regua, linhas) -> None:
    with CSV.open(encoding="utf-8", newline="") as fh:
        cabecalho = list(csv.DictReader(fh).fieldnames or [])
    assert cabecalho == regua.COLUNAS


def test_o_veredito_manda_no_sinal_espera(regua, linhas) -> None:
    """O par veredito↔espera é o que torna cada linha uma afirmação sobre o código.

    Se ele afrouxar, uma linha ``FALTA_NO_HTML`` poderia declarar ``PRESENTE`` e
    passar a conferir o contrário do que afirma.
    """
    for n, lin in enumerate(linhas, 2):
        assert lin["veredito"] in regua.VEREDITOS, f"linha {n}: veredito '{lin['veredito']}'"
        assert lin["sinal_espera"] == regua.VEREDITOS[lin["veredito"]], (
            f"linha {n}: {lin['veredito']} pede {regua.VEREDITOS[lin['veredito']]}, "
            f"e o CSV diz '{lin['sinal_espera']}'")


def test_toda_linha_tem_sinal_e_escopo(linhas) -> None:
    """Sem sinal a linha não é conferível — vira prosa dentro de um CSV."""
    sem = [lin["feature"] for lin in linhas
           if not lin["sinal"] or not lin["sinal_escopo"]]
    assert not sem, f"{len(sem)} linha(s) sem sinal: {sem[:5]}"


def test_nenhuma_feature_repetida_na_mesma_aba(linhas) -> None:
    contas = Counter((lin["aba"], lin["feature"]) for lin in linhas)
    repetidas = [c for c, n in contas.items() if n > 1]
    assert not repetidas, f"features repetidas: {repetidas[:5]}"


def test_as_dez_abas_estao_todas_medidas(regua, linhas) -> None:
    medidas = {lin["aba"] for lin in linhas}
    assert medidas == set(regua.ABAS), f"faltou: {set(regua.ABAS) - medidas}"


# ---------------------------------------------------------------------------
# 2. O PORTÃO ESTÁ VERDE NESTA ÁRVORE
# ---------------------------------------------------------------------------


def test_o_portao_roda_verde_nesta_arvore() -> None:
    """Portão vermelho por dias ensina a próxima pessoa a ignorá-lo."""
    r = subprocess.run([sys.executable, str(REGUA)], capture_output=True, text=True, cwd=RAIZ)
    assert r.returncode == 0, f"o portão reprovou:\n{r.stdout}\n{r.stderr}"
    assert "OK:" in r.stdout


def test_a_tabela_publicada_e_a_contagem_do_csv(regua, linhas) -> None:
    """A §2 do documento sai do mesmo dado que a régua confere."""
    assert regua.conferir_o_documento(linhas) == []


# ---------------------------------------------------------------------------
# 3. O PORTÃO SABE RECUSAR — os dublês
# ---------------------------------------------------------------------------

_MODELO = {
    "aba": "05-vibracao",
    "feature": "dublê",
    "veredito": "IGUAL",
    "sinal": "rumble_policy_set_checked",
    "sinal_espera": "PRESENTE",
    "sinal_escopo": "src/hefesto_dualsense4unix/interface/pacotes/a05_vibracao.py",
    "gtk_onde": "src/hefesto_dualsense4unix/app/actions/rumble_actions.py:773",
    "html_onde": "src/hefesto_dualsense4unix/interface/pacotes/a05_vibracao.py:332",
    "gtk_faz": "—", "html_faz": "—", "porque": "—",
}


def _com(regua, tmp_path: Path, **mudancas) -> list[str]:
    """Escreve um CSV de UMA linha, com as mudanças pedidas, e devolve as falhas."""
    linha = dict(_MODELO) | mudancas
    destino = tmp_path / "paridade-gtk-html.csv"
    with destino.open("w", encoding="utf-8", newline="") as fh:
        w = csv.DictWriter(fh, fieldnames=regua.COLUNAS, lineterminator="\n")
        w.writeheader()
        w.writerow(linha)
    antigo = regua.CSV
    regua.CSV = destino
    try:
        linhas, falhas = regua.ler_csv()
        if linhas:
            falhas += regua.conferir(linhas, regua.Arvore())
        return falhas
    finally:
        regua.CSV = antigo


def _familias(falhas: list[str]) -> set[str]:
    return {f.split(":", 1)[0] for f in falhas}


def test_o_dublê_intacto_passa(regua, tmp_path) -> None:
    """A linha-modelo tem de passar, senão os testes abaixo não provam nada."""
    assert _com(regua, tmp_path) == []


def test_recusa_endereco_de_arquivo_que_nao_existe(regua, tmp_path) -> None:
    falhas = _com(regua, tmp_path,
                  gtk_onde="src/hefesto_dualsense4unix/app/actions/inventado.py:10")
    assert "endereco-morto" in _familias(falhas), falhas


def test_recusa_linha_alem_do_fim_do_arquivo(regua, tmp_path) -> None:
    falhas = _com(regua, tmp_path,
                  gtk_onde="src/hefesto_dualsense4unix/app/actions/rumble_actions.py:999999")
    assert "endereco-morto" in _familias(falhas), falhas


def test_recusa_endereco_da_gtk_na_coluna_do_html(regua, tmp_path) -> None:
    """É o que impede este portão de virar a régua que se compara consigo mesma."""
    falhas = _com(regua, tmp_path,
                  html_onde="src/hefesto_dualsense4unix/app/actions/rumble_actions.py:773")
    assert "lado-trocado" in _familias(falhas), falhas


def test_recusa_endereco_do_html_na_coluna_da_gtk(regua, tmp_path) -> None:
    falhas = _com(regua, tmp_path,
                  gtk_onde="src/hefesto_dualsense4unix/interface/pacotes/a05_vibracao.py:332")
    assert "lado-trocado" in _familias(falhas), falhas


def test_recusa_linha_igual_sem_dizer_onde_no_html(regua, tmp_path) -> None:
    """A MORDIDA A1 — apagar o `html_onde` de uma linha que afirma existência."""
    falhas = _com(regua, tmp_path, html_onde="")
    assert "sem-endereco" in _familias(falhas), falhas


def test_recusa_linha_sem_sinal(regua, tmp_path) -> None:
    falhas = _com(regua, tmp_path, sinal="")
    assert "sem-endereco" in _familias(falhas), falhas


def test_recusa_sinal_que_sumiu_do_escopo(regua, tmp_path) -> None:
    """Uma feature IGUAL pode ter sido removida do HTML sem ninguém ver."""
    falhas = _com(regua, tmp_path, sinal="funcao_que_nunca_existiu_neste_repositorio")
    assert "sinal-sumiu" in _familias(falhas), falhas


def test_recusa_divida_que_fechou(regua, tmp_path) -> None:
    """A MORDIDA B, e é a regra que impede o número de virar propaganda.

    Uma linha ``FALTA_NO_HTML`` cujo símbolo APARECEU no lado HTML reprova: se a
    dívida fechou, o veredito daquela linha mudou e o dado tem de ser reescrito.
    O dublê usa um símbolo que já vive no lado HTML — é a mesma situação de
    alguém ter acabado de portar a função.
    """
    falhas = _com(regua, tmp_path, veredito="FALTA_NO_HTML", sinal_espera="AUSENTE",
                  sinal="rumble_policy_set_checked", sinal_escopo="LADO-HTML")
    assert "divida-fechada" in _familias(falhas), falhas


def test_recusa_sinal_que_nunca_poderia_aparecer(regua, tmp_path) -> None:
    """A régua se auditando: um sinal AUSENTE que não existe em lugar nenhum e
    não tem forma de endereço de tela nunca morderia — regra desligada em
    silêncio é pior que regra nenhuma."""
    falhas = _com(regua, tmp_path, veredito="FALTA_NO_HTML", sinal_espera="AUSENTE",
                  sinal="simbolo_que_nao_existe_em_lugar_nenhum", sinal_escopo="LADO-HTML")
    assert "sinal-morto" in _familias(falhas), falhas


def test_aceita_endereco_de_tela_que_ainda_vai_nascer(regua, tmp_path) -> None:
    """O contrário do de cima, e é a outra forma legítima de a dívida fechar.

    ``data-campo="fragil"`` não existe em lado nenhum HOJE — é o endereço que a
    página vai ganhar. Se a régua o recusasse, as faltas de LEITURA AO VIVO (a
    maior parte das 176) ficariam sem sinal nenhum.
    """
    falhas = _com(regua, tmp_path, veredito="FALTA_NO_HTML", sinal_espera="AUSENTE",
                  sinal='data-campo="um-campo-que-ninguem-escreveu-ainda"',
                  sinal_escopo="LADO-HTML")
    assert falhas == [], falhas


def test_recusa_veredito_fora_do_dominio(regua, tmp_path) -> None:
    falhas = _com(regua, tmp_path, veredito="TALVEZ")
    assert "integridade" in _familias(falhas), falhas


def test_recusa_espera_que_contradiz_o_veredito(regua, tmp_path) -> None:
    falhas = _com(regua, tmp_path, veredito="FALTA_NO_HTML")  # espera segue PRESENTE
    assert "integridade" in _familias(falhas), falhas


def test_recusa_documento_sem_a_tabela(regua, tmp_path, linhas) -> None:
    """A regra 8: o número publicado sai do CSV, ou o documento vira folheto."""
    falso = tmp_path / "sem-tabela.md"
    falso.write_text("# um documento sem o bloco da tabela\n", encoding="utf-8")
    antigo = regua.DOC
    regua.DOC = falso
    try:
        falhas = regua.conferir_o_documento(linhas)
    finally:
        regua.DOC = antigo
    assert falhas and "numero-publicado" in _familias(falhas), falhas


def test_recusa_tabela_publicada_que_diverge_do_csv(regua, tmp_path, linhas) -> None:
    falso = tmp_path / "tabela-torta.md"
    corpo = ["<!-- TABELA-DA-PARIDADE -->", ""]
    for aba in regua.ABAS:
        deste = [lin for lin in linhas if lin["aba"] == aba]
        c = Counter(lin["veredito"] for lin in deste)
        corpo.append(f"| {aba} | {len(deste)} | {c['IGUAL']} | {c['DIFERENTE']} | "
                     f"{c['FALTA_NO_HTML']} | {c['SO_NO_HTML']} | {c['NAO_DA_PARA_SABER']} | "
                     f"{round(100 * c['IGUAL'] / len(deste))}% |")
    corpo.append("| TODAS | 1 | 1 | 1 | 1 | 1 | 1 | 100% |")   # <- a mentira
    corpo += ["", "<!-- /TABELA-DA-PARIDADE -->"]
    falso.write_text("\n".join(corpo), encoding="utf-8")
    antigo = regua.DOC
    regua.DOC = falso
    try:
        falhas = regua.conferir_o_documento(linhas)
    finally:
        regua.DOC = antigo
    assert any("TODAS" in f for f in falhas), falhas
