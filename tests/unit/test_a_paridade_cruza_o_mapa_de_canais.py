"""A PARIDADE CRUZA O MAPA — e o mapa INFORMA, nunca VETA.

O achado que este arquivo fecha é da A-TELA-NOVA-ENTRA-NA-RÉGUA-DO-MAPA-01
(§5.4, 06/09/2026): ``docs/data/paridade-gtk-html.csv`` e
``docs/data/mapa-controles.csv`` eram lidos juntos por DOIS arquivos do produto
(``interface/aba02.py`` e ``interface/mesa_viva.py``) e por **portão nenhum**.
Uma linha podia dizer ``IGUAL`` — a tela nova faz o que a janela fazia — enquanto
o mapa dizia que o CANAL embaixo dela só aciona num transporte. Os dois números
concordavam consigo mesmos, e ninguém perguntava ao outro.

O cruzamento mora em ``scripts/check_paridade_gtk_html.py`` (regras 10, 11 e 12),
e **de propósito**: pôr um portão novo em ``scripts/`` obrigaria a mexer no
``portoes.sh`` E no ``ci.yml``, e a lista de portões desta casa tem UM dono —
``tests/unit/test_portao_a_lista_de_portoes_e_uma_so.py`` reprova quem a duplica.
O portão da paridade já roda nos dois; o cruzamento entrou nele.

ESTE ARQUIVO É O PORTÃO DO PORTÃO, e prova as duas metades:

1. **ELE SABE RECUSAR** — cada regra nova é arrancada por dublê, com um mapa e
   uma ponte forjados. Régua que reprova nada é indistinguível de régua
   desligada.
2. **ELE SABE NÃO RECUSAR** — e esta metade é a que a decisão dela exige.
   ``D-0609-O-MAPA-INFORMA-NUNCA-VETA``, palavra dela em 06/09/2026: *"Esse mapa
   é funcional e real. tá desatualizado no sentido de não ter sido medido. foi e
   tudo funciona."*  Uma célula ``nao-medido`` vira AVISO, e o ``rc`` continua
   ZERO. ``test_a_causa_nao_medido_avisa_e_nao_reprova`` é o teste mais
   importante daqui: sem ele, um portão que só sabe reprovar transformaria um
   mapa ATRASADO em freio — que foi exatamente a ordem que ela reverteu a dois
   agentes em voo no mesmo dia.
"""

from __future__ import annotations

import csv
import importlib.util
import sys
from pathlib import Path

import pytest

RAIZ = Path(__file__).resolve().parents[2]
REGUA = RAIZ / "scripts" / "check_paridade_gtk_html.py"
CSV_PARIDADE = RAIZ / "docs" / "data" / "paridade-gtk-html.csv"
CSV_MAPA = RAIZ / "docs" / "data" / "mapa-controles.csv"


def _modulo():
    espec = importlib.util.spec_from_file_location("check_paridade_cruza_o_mapa", REGUA)
    assert espec is not None and espec.loader is not None
    modulo = importlib.util.module_from_spec(espec)
    sys.modules[espec.name] = modulo
    espec.loader.exec_module(modulo)
    return modulo


@pytest.fixture(scope="module")
def regua():
    return _modulo()


@pytest.fixture(scope="module")
def linhas_reais() -> list[dict[str, str]]:
    with CSV_PARIDADE.open(encoding="utf-8", newline="") as fh:
        return list(csv.DictReader(fh))


# ---------------------------------------------------------------------------
# OS DUBLÊS — uma linha de paridade e uma célula de mapa, forjadas
# ---------------------------------------------------------------------------

_LINHA = {
    "aba": "05-vibracao",
    "feature": "dublê",
    "veredito": "IGUAL",
    "sinal": "rumble_ff",
    "sinal_espera": "PRESENTE",
    "sinal_escopo": "src/hefesto_dualsense4unix/interface/pacotes/a05_vibracao.py",
    "gtk_onde": "src/hefesto_dualsense4unix/app/actions/rumble_actions.py:773",
    "html_onde": "src/hefesto_dualsense4unix/interface/pacotes/a05_vibracao.py:332",
    "gtk_faz": "—", "html_faz": "—", "porque": "—",
}

_PONTE = {("05-vibracao", "dublê"): "canal.do.duble@dualsense"}


def _celula(**mudancas) -> dict[str, dict[str, str]]:
    """Uma célula de mapa, `sim` nos dois lados, com as mudanças pedidas."""
    base = {
        "id": "canal.do.duble@dualsense",
        "cabo_aciona": "sim", "radio_aciona": "sim",
        "cabo_por_que_nao_aciona": "", "radio_por_que_nao_aciona": "",
    }
    return {"canal.do.duble@dualsense": base | mudancas}


def _cruza(regua, *, linha=None, mapa=None, ponte=None, piso=0):
    linhas = [dict(_LINHA) | (linha or {})]
    return regua.cruzar_com_o_mapa(
        linhas, mapa if mapa is not None else _celula(),
        pontes=_PONTE if ponte is None else ponte, piso=piso)


def _familias(falhas: list[str]) -> set[str]:
    return {f.split(":", 1)[0] for f in falhas}


# ---------------------------------------------------------------------------
# 1. O DUBLÊ INTACTO PASSA — senão nada abaixo prova coisa alguma
# ---------------------------------------------------------------------------


def test_o_duble_intacto_passa(regua) -> None:
    falhas, avisos = _cruza(regua)
    assert falhas == []
    assert avisos == []


def test_o_mapa_que_sustenta_os_dois_transportes_nao_cobra_nada(regua) -> None:
    """`sim` dos dois lados: não há transporte a declarar, e a régua se cala."""
    falhas, avisos = _cruza(regua, linha={"porque": "sem uma palavra de transporte"})
    assert falhas == []
    assert avisos == []


# ---------------------------------------------------------------------------
# 2. A METADE QUE ELA MANDOU EXISTIR — `nao-medido` avisa e NÃO reprova
# ---------------------------------------------------------------------------


def test_a_causa_nao_medido_avisa_e_nao_reprova(regua) -> None:
    """`D-0609-O-MAPA-INFORMA-NUNCA-VETA`, e é o teste que segura a decisão dela.

    Célula atrasada NÃO veta trabalho: ela vira fila de bancada. Se este teste
    ficar vermelho, alguém transformou o mapa em freio.
    """
    falhas, avisos = _cruza(
        regua,
        mapa=_celula(radio_aciona="não", radio_por_que_nao_aciona="nao-medido"),
        linha={"porque": "sem uma palavra de transporte"})
    assert falhas == []
    assert len(avisos) == 1
    assert "nao-medido" in avisos[0]
    assert "SPECS-A-PROCEDENCIA-01" in avisos[0]


def test_os_dois_lados_nao_medidos_avisam_duas_vezes_e_nao_reprovam(regua) -> None:
    falhas, avisos = _cruza(
        regua,
        mapa=_celula(cabo_aciona="não", cabo_por_que_nao_aciona="nao-medido",
                     radio_aciona="não", radio_por_que_nao_aciona="nao-medido"),
        linha={"porque": "sem uma palavra de transporte"})
    assert falhas == []
    assert len(avisos) == 2


def test_um_lado_nao_medido_e_o_outro_com_causa_so_cobra_o_segundo(regua) -> None:
    """A mistura, que é o caso real: o aviso não apaga a cobrança do outro lado."""
    falhas, avisos = _cruza(
        regua,
        mapa=_celula(cabo_aciona="não", cabo_por_que_nao_aciona="nao-medido",
                     radio_aciona="parcial", radio_por_que_nao_aciona="divida"),
        linha={"porque": "sem uma palavra de transporte"})
    assert _familias(falhas) == {"transporte-nao-declarado"}
    assert len(avisos) == 1
    assert "radio=parcial (divida)" in falhas[0]
    assert "cabo" not in falhas[0].split("restringe")[1].split("\n")[0]


# ---------------------------------------------------------------------------
# 3. A REGRA 11 SABE RECUSAR — e sabe aceitar quem declara
# ---------------------------------------------------------------------------


def test_recusa_quem_afirma_paridade_sem_dizer_o_transporte(regua) -> None:
    falhas, _ = _cruza(
        regua,
        mapa=_celula(radio_aciona="não", radio_por_que_nao_aciona="divida"),
        linha={"porque": "sem uma palavra de transporte"})
    assert _familias(falhas) == {"transporte-nao-declarado"}
    assert "canal.do.duble@dualsense" in falhas[0]


@pytest.mark.parametrize("declaracao", [
    "vale no cabo, e só nele",
    "pelo rádio o aparelho não publica placa de som",
    "no RÁDIO isso depende da ponte",   # a caixa não decide
])
def test_aceita_a_linha_que_nomeia_o_transporte(regua, declaracao: str) -> None:
    """Acento e caixa não podem desligar a régua.

    É o defeito que esta casa já pagou onze vezes: *a régua desliga exatamente
    quando alguém escreve bem*. `Rádio` é a grafia correta, e ela conta.
    """
    falhas, _ = _cruza(
        regua,
        mapa=_celula(radio_aciona="não", radio_por_que_nao_aciona="divida"),
        linha={"porque": declaracao})
    assert falhas == []


def test_a_declaracao_vale_em_qualquer_coluna_da_linha(regua) -> None:
    for coluna in ("gtk_faz", "html_faz", "porque"):
        falhas, _ = _cruza(
            regua,
            mapa=_celula(cabo_aciona="não", cabo_por_que_nao_aciona="divida"),
            linha={coluna: "isto vale no cabo"})
        assert falhas == [], coluna


def test_a_declaracao_vale_no_proprio_nome_da_feature(regua) -> None:
    """É o caso REAL de `"A luz não acende" — a trava no cabo`: o nome já diz."""
    linhas = [dict(_LINHA) | {"feature": "a trava no cabo", "porque": "—"}]
    falhas, _ = regua.cruzar_com_o_mapa(
        linhas, _celula(cabo_aciona="não", cabo_por_que_nao_aciona="divida"),
        pontes={("05-vibracao", "a trava no cabo"): "canal.do.duble@dualsense"}, piso=0)
    assert falhas == []


def test_a_palavra_usb_nao_conta_como_transporte(regua) -> None:
    """O glossário da casa é cabo/rádio. `usb` na linha não declara nada."""
    falhas, _ = _cruza(
        regua,
        mapa=_celula(radio_aciona="não", radio_por_que_nao_aciona="divida"),
        linha={"porque": "só no barramento usb, pela placa do aparelho"})
    assert _familias(falhas) == {"transporte-nao-declarado"}


def test_uma_palavra_que_contem_cabo_nao_declara_nada(regua) -> None:
    """`acabou` não é `cabo`. A fronteira de palavra é o que separa os dois."""
    falhas, _ = _cruza(
        regua,
        mapa=_celula(radio_aciona="não", radio_por_que_nao_aciona="divida"),
        linha={"porque": "acabou o trabalho e o radiofônico não vale"})
    assert _familias(falhas) == {"transporte-nao-declarado"}


@pytest.mark.parametrize("veredito", ["FALTA_NO_HTML", "SO_NO_HTML", "NAO_DA_PARA_SABER"])
def test_so_quem_afirma_paridade_e_cobrado(regua, veredito: str) -> None:
    """`FALTA_NO_HTML` já é dívida declarada — cobrar transporte seria acusar duas vezes."""
    espera = "AUSENTE" if veredito == "FALTA_NO_HTML" else "PRESENTE"
    falhas, _ = _cruza(
        regua,
        mapa=_celula(radio_aciona="não", radio_por_que_nao_aciona="divida"),
        linha={"veredito": veredito, "sinal_espera": espera,
               "porque": "sem uma palavra de transporte"})
    assert falhas == []


# ---------------------------------------------------------------------------
# 4. A REGRA 10 — as duas pontas da ponte têm de existir
# ---------------------------------------------------------------------------


def test_recusa_ponte_para_feature_que_saiu_do_csv(regua) -> None:
    falhas, _ = _cruza(regua, ponte={("05-vibracao", "outra qualquer"): "canal.do.duble@dualsense"})
    assert _familias(falhas) == {"ponte-morta"}
    assert "não está mais no CSV" in falhas[0]


def test_recusa_ponte_para_id_que_nao_existe_no_mapa(regua) -> None:
    falhas, _ = _cruza(regua, ponte={("05-vibracao", "dublê"): "canal.inventado@dualsense"})
    assert _familias(falhas) == {"ponte-morta"}
    assert "canal.inventado@dualsense" in falhas[0]


# ---------------------------------------------------------------------------
# 5. A REGRA 12 — a catraca. A ponte só cresce.
# ---------------------------------------------------------------------------


def test_recusa_ponte_que_encolheu(regua) -> None:
    falhas, _ = _cruza(regua, piso=2)
    assert _familias(falhas) == {"ponte-encolheu"}
    assert "tem 1 entrada(s) e o piso é 2" in falhas[0]


def test_crescer_passa_e_o_piso_nao_pune_quem_melhora(regua) -> None:
    """Comparação por `>=`. Uma régua por igualdade puniria quem acrescenta ponte."""
    ponte = dict(_PONTE)
    ponte[("05-vibracao", "dublê 2")] = "canal.do.duble@dualsense"
    linhas = [dict(_LINHA), dict(_LINHA) | {"feature": "dublê 2"}]
    falhas, _ = regua.cruzar_com_o_mapa(linhas, _celula(), pontes=ponte, piso=1)
    assert falhas == []


# ---------------------------------------------------------------------------
# 6. O MAPA DE VERDADE — a régua não pode se desligar sozinha
# ---------------------------------------------------------------------------


def test_o_mapa_ausente_e_falha_e_nao_silencio(regua, tmp_path: Path) -> None:
    """Régua que se cala quando a fonte some é régua que dá verde sobre nada."""
    antigo = regua.MAPA
    regua.MAPA = tmp_path / "mapa-que-nao-existe.csv"
    try:
        mapa, falhas = regua.ler_mapa()
        assert mapa == {}
        assert _familias(falhas) == {"integridade"}
    finally:
        regua.MAPA = antigo


def test_o_mapa_sem_as_colunas_do_cruzamento_e_falha(regua, tmp_path: Path) -> None:
    destino = tmp_path / "mapa-controles.csv"
    destino.write_text("id,rotulo\nx@y,coisa\n", encoding="utf-8")
    antigo = regua.MAPA
    regua.MAPA = destino
    try:
        mapa, falhas = regua.ler_mapa()
        assert mapa == {}
        assert "cabo_aciona" in falhas[0]
    finally:
        regua.MAPA = antigo


def test_o_mapa_desta_arvore_abre_e_tem_as_colunas(regua) -> None:
    mapa, falhas = regua.ler_mapa()
    assert falhas == []
    assert len(mapa) > 100


# ---------------------------------------------------------------------------
# 7. NESTA ÁRVORE, AGORA
# ---------------------------------------------------------------------------


def test_a_ponte_desta_arvore_tem_as_duas_pontas_vivas(regua, linhas_reais) -> None:
    """Regra 10 contra o dado real: nenhuma ponte aponta para o vazio."""
    mapa, _ = regua.ler_mapa()
    falhas, _ = regua.cruzar_com_o_mapa(linhas_reais, mapa)
    assert [f for f in falhas if f.startswith("ponte-morta")] == []


def test_a_ponte_esta_no_piso_e_o_piso_e_o_tamanho_dela(regua) -> None:
    assert len(regua.PONTES) >= regua.PISO_DAS_PONTES
    assert regua.PISO_DAS_PONTES > 0


def test_o_cruzamento_roda_verde_nesta_arvore(regua, linhas_reais) -> None:
    """Verde AQUI, hoje. Os avisos NÃO entram nesta conta — é a decisão dela.

    E não se afirma nada sobre a QUANTIDADE de avisos de propósito: no dia em que
    a bancada medir `luz.lightbar.brilho@dualsense`, o aviso some — e um teste
    que exigisse avisos puniria quem fechou a medição.
    """
    mapa, falhas_do_mapa = regua.ler_mapa()
    falhas, _ = regua.cruzar_com_o_mapa(linhas_reais, mapa)
    assert falhas_do_mapa == []
    assert falhas == []


def test_toda_ponte_aponta_para_um_id_do_dualsense(regua) -> None:
    """A tela desta casa é do DualSense. Uma ponte para `@pro` seria erro de leitura."""
    fora = [ident for ident in regua.PONTES.values() if not ident.endswith("@dualsense")]
    assert fora == []
