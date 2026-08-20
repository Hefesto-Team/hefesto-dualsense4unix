"""PONTE-NAO-DECLARADA-01: `uhid` medido que não diz por qual ponte mediu.

O QUE ESTA REGRA PEGA
---------------------
`uhid` é o único canal do mapa em que a PONTE decide se a feature existe. Ele só
existe sob a máscara DualSense do nosso vpad (`054c:0df2`); sob a máscara Xbox
(`045e:028e`) não há por onde a feature chegar ao jogo — o pacote do Xbox 360 é
fixo desde 2005 e o `xpad` declara sete eixos e um nó só
(`docs/protocol/pilha-steam-input-xpad-sdl.md` §1.5). É esse cálculo que põe a
DualSense no primeiro degrau de `integrations/ponte_escada.py`: *"errar para
Xbox custa dez linhas do mapa, e custa em silêncio"*.

Logo, uma célula que diz `aciona = sim` com `de_onde_sei = medido` num canal
`uhid` e deixa `ponte_alcanca` VAZIA não é uma célula incompleta: ela afirma
duas coisas contraditórias ao mesmo tempo — que a feature funciona, e nada sobre
a única condição que faz ela funcionar — e fica verde nas duas.

A regressão que a regra nomeia é reproduzível numa linha só: marcar
`luz.replica_output_jogo@pro` como forte e medida. Ela é `uhid` nos dois
transportes, tem `ponte_alcanca` vazia, e antes da regra o portão devolvia
`exit 0` com a mentira inteira dentro.

POR QUE ELA SÓ COBRA ONDE A PROMESSA É MÁXIMA
---------------------------------------------
Das 16 linhas `uhid` do mapa, quatro afirmam forte e as doze restantes calam.
`◌ ninguém respondeu` é verdade, e preencher por analogia é o que destruiria o
valor do mapa — vazio segue sendo PERGUNTA ABERTA, nunca "serve para toda
ponte". Cobrar declaração de quem não afirma nada seria reprovar afirmação
verdadeira, que é o erro que esta casa já pagou em 12/08 e 13/08.

Por isso a regra nasce VERDE: as quatro linhas fortes são justamente quatro das
dez que já declaram `gamepad/dualsense`.

COMO ESTES TESTES MORDEM
------------------------
- Apague o bloco `if lados_por_uhid_que_afirmam:` do `censo` (ou o corpo de
  `_regra_da_ponte_nao_declarada`): o primeiro teste reprova, porque a mentira
  volta a passar com `exit 0`.
- Troque `if ponte:` por `if True:` na regra: idem.
- Alargue a regra para cobrar de toda linha `uhid` (tirando a condição de
  afirmação forte): o teste da árvore intacta reprova — doze linhas honestas
  passariam a ser acusadas.
- Apague a conferência de domínio do ramo de `integridade`: o teste da
  tipografia reprova, e `gamepad/dualsense+Steam Input` volta a ser uma ponte
  que o mapa aceita e o produto não conhece.
- Mude a fórmula de `Ponte.chave` em `ponte_escada.py` sem mudar a cópia do
  portão: o teste das duas réguas reprova.
"""

from __future__ import annotations

import csv
import re
import subprocess
import sys
from pathlib import Path

import pytest

RAIZ = Path(__file__).resolve().parents[2]
MAPA = RAIZ / "docs" / "data" / "mapa-controles.csv"
CADERNO = RAIZ / "docs" / "data" / "ensaios.csv"
PONTE_ESCADA = Path("src/hefesto_dualsense4unix/integrations/ponte_escada.py")

#: A linha da regressão: `uhid` nos dois lados, `ponte_alcanca` vazia, e uma
#: feature que o Pro NÃO tem — o que a torna o pior caso possível de promover.
LINHA_SEM_PONTE = ("luz.replica_output_jogo", "pro")

#: Um nó de pytest que existe de verdade, para a promoção não reprovar pela
#: regra 1 (`sem-mordida`) e o teste medir só a regra nova.
MORDIDA_REAL = "tests/unit/test_a_ponte_nao_declarada_01.py::test_a_regra_enxerga_o_que_promete"

sys.path.insert(0, str(RAIZ / "scripts"))
sys.path.insert(0, str(RAIZ / "src"))

from check_paridade_transporte import dominio_das_pontes
from hefesto_dualsense4unix.integrations.ponte_escada import ESCADA


def _rodar(raiz: Path) -> subprocess.CompletedProcess[str]:
    return subprocess.run(
        [sys.executable, str(raiz / "scripts" / "check_paridade_transporte.py")],
        cwd=str(raiz),
        capture_output=True,
        text=True,
        check=False,
    )


@pytest.fixture
def arvore(tmp_path: Path) -> Path:
    """Cópia mínima e DESCARTÁVEL — o portão nunca roda contra a árvore real.

    Leva o `ponte_escada.py` junto, e isso não é detalhe: sem ele a conferência
    de DOMÍNIO se desliga sozinha (é o comportamento de `dominio_das_pontes`), e
    um teste de tipografia rodando com a régua desligada aprovaria qualquer
    coisa. `tests/` e `specs.html` ficam de fora de propósito — as regras 2 e 5
    se desligam, dizem isso em voz alta, e não têm nada a ver com a ponte.
    """
    for rel in ("scripts", "docs/data", str(PONTE_ESCADA.parent)):
        (tmp_path / rel).mkdir(parents=True, exist_ok=True)
    for nome in ("check_paridade_transporte.py", "eliminacao.py"):
        (tmp_path / "scripts" / nome).write_bytes((RAIZ / "scripts" / nome).read_bytes())
    for origem in (MAPA, CADERNO):
        (tmp_path / "docs" / "data" / origem.name).write_bytes(origem.read_bytes())
    (tmp_path / PONTE_ESCADA).write_bytes((RAIZ / PONTE_ESCADA).read_bytes())
    return tmp_path


def _escreve(mapa: Path, chave: tuple[str, str], campos: dict[str, str]) -> None:
    """Escreve campos numa linha do mapa, e grita se a linha tiver sumido."""
    with mapa.open(encoding="utf-8", newline="") as fh:
        linhas = list(csv.reader(fh))
    indice = {coluna: i for i, coluna in enumerate(linhas[0])}
    achou = False
    for registro in linhas[1:]:
        if registro and (registro[0], registro[1]) == chave:
            for coluna, valor in campos.items():
                registro[indice[coluna]] = valor
            achou = True
    assert achou, f"a linha {chave} sumiu do mapa — o teste ficou cego"
    with mapa.open("w", encoding="utf-8", newline="") as fh:
        csv.writer(fh, lineterminator="\n").writerows(linhas)


def _promove_sem_dizer_a_ponte(mapa: Path) -> None:
    """A mentira exata: forte e medida nos dois lados, `ponte_alcanca` vazia."""
    _escreve(
        mapa,
        LINHA_SEM_PONTE,
        {
            "cabo_aciona": "sim",
            "radio_aciona": "sim",
            "cabo_de_onde_sei": "medido",
            "radio_de_onde_sei": "medido",
            "teste_que_morde": MORDIDA_REAL,
        },
    )


def _falhas(saida: str) -> list[str]:
    return [linha for linha in saida.splitlines() if "FALHA " in linha]


def _numero_do_resumo(saida: str, rotulo: str) -> int:
    achado = re.search(rf"{re.escape(rotulo)}\.*\s+(\d+)", saida)
    assert achado is not None, f"o resumo do censo não trouxe {rotulo!r}:\n{saida}"
    return int(achado.group(1))


# --------------------------------------------------------------------------
# A MORDIDA
# --------------------------------------------------------------------------
def test_o_portao_reprova_uhid_forte_que_nao_diz_a_ponte(arvore: Path) -> None:
    """A regressão que o plano nomeia, reproduzida em cópia descartável."""
    _promove_sem_dizer_a_ponte(arvore / "docs/data/mapa-controles.csv")

    saida = _rodar(arvore)

    assert saida.returncode != 0, (
        "o portão aceitou `aciona = sim` + `de_onde_sei = medido` num canal "
        "`uhid` sem dizer por qual ponte. `uhid` só existe sob a máscara "
        "DualSense: essa célula afirma que a feature funciona E nada sobre a "
        "única condição de ela funcionar.\n" + saida.stdout[-1500:]
    )
    assert "ponte-nao-declarada" in saida.stdout, (
        "reprovou, mas por outra regra — a mensagem tem de dizer que a ponte "
        f"não foi declarada:\n{saida.stdout[-1500:]}"
    )
    intrusas = [linha for linha in _falhas(saida.stdout) if "ponte-nao-declarada" not in linha]
    assert not intrusas, (
        "a promoção derrubou outras regras junto, e aí este teste não estaria "
        f"medindo a regra nova: {intrusas}"
    )


def test_a_mordida_nomeia_os_dois_lados_e_a_linha(arvore: Path) -> None:
    """Nomear, nunca só contar: a reprovação tem de dizer ONDE e QUAL."""
    _promove_sem_dizer_a_ponte(arvore / "docs/data/mapa-controles.csv")

    saida = _rodar(arvore)
    linha = next(
        achado for achado in _falhas(saida.stdout) if "ponte-nao-declarada" in achado
    )

    assert "luz.replica_output_jogo@pro" in linha, linha
    assert "cabo" in linha and "rádio" in linha, (
        "a linha é `uhid` nos DOIS transportes e afirma forte nos dois: a "
        f"mensagem tem de nomear os dois lados.\n{linha}"
    )
    assert "ponte_alcanca" in linha, linha


# --------------------------------------------------------------------------
# A CONTRAPROVA — a regra não machuca afirmação verdadeira
# --------------------------------------------------------------------------
def test_o_portao_continua_verde_na_arvore_de_verdade(arvore: Path) -> None:
    """Dia 1 verde, sem medição nova.

    As quatro linhas `uhid` que afirmam forte estão entre as dez que já
    declaram `gamepad/dualsense`, e as doze que calam continuam podendo calar.
    Se este teste reprovar, a regra ficou larga demais — é o erro de 12/08 e
    13/08 ao contrário.
    """
    saida = _rodar(arvore)
    assert saida.returncode == 0, (
        "o portão reprovou a árvore INTACTA depois da regra nova:\n"
        + saida.stdout[-2000:]
    )


def test_a_linha_uhid_que_nao_afirma_nada_continua_podendo_calar(arvore: Path) -> None:
    """Vazio é PERGUNTA ABERTA. A regra cobra promessa máxima, não silêncio."""
    mapa = arvore / "docs/data/mapa-controles.csv"
    _escreve(mapa, LINHA_SEM_PONTE, {"cabo_de_onde_sei": "medido"})

    saida = _rodar(arvore)
    assert saida.returncode == 0, (
        "`de_onde_sei = medido` com `aciona = não` não é afirmação forte, e a "
        "regra não pode cobrar ponte de quem não promete nada:\n"
        + saida.stdout[-1500:]
    )


# --------------------------------------------------------------------------
# ELE ENXERGA? — portão que não vê nada passa sempre
# --------------------------------------------------------------------------
def test_a_regra_enxerga_o_que_promete() -> None:
    """A régua do portão contra uma contagem independente do mesmo CSV.

    Nenhum número fica ESCRITO aqui: os dois lados são medidos na hora. Se a
    regra parar de descobrir as linhas `uhid` — um `strip()` que suma, um nome
    de coluna que mude —, os números divergem neste teste, e não daqui a três
    levas. É a lição de 16/08: duas réguas independentes é o que revela.
    """
    saida = subprocess.run(
        [sys.executable, str(RAIZ / "scripts" / "check_paridade_transporte.py")],
        cwd=str(RAIZ),
        capture_output=True,
        text=True,
        check=False,
    )
    assert saida.returncode in (0, 1), saida.stdout + saida.stderr

    with MAPA.open(encoding="utf-8", newline="") as fh:
        linhas = list(csv.DictReader(fh))
    uhid = [
        linha
        for linha in linhas
        if "uhid" in ((linha["cabo_canal"] or "").strip(), (linha["radio_canal"] or "").strip())
    ]
    fortes = [
        linha
        for linha in uhid
        if any(
            (linha[f"{lado}_canal"] or "").strip() == "uhid"
            and (linha[f"{lado}_aciona"] or "").strip() == "sim"
            and (linha[f"{lado}_de_onde_sei"] or "").strip() == "medido"
            for lado in ("cabo", "radio")
        )
    ]

    assert uhid, "o mapa perdeu TODAS as linhas `uhid` — a regra ficou sem objeto"
    assert _numero_do_resumo(saida.stdout, "linhas que alcançam o jogo por `uhid`") == len(uhid)
    assert _numero_do_resumo(saida.stdout, "dessas, com afirmação forte") == len(fortes)
    assert _numero_do_resumo(saida.stdout, "dessas, SEM `ponte_alcanca`") == 0, (
        "a árvore de verdade tem afirmação forte por `uhid` sem ponte "
        "declarada — o portão devia estar vermelho"
    )


def test_o_mapa_tem_a_coluna_que_a_regra_le(arvore: Path) -> None:
    """Regra dura não se desliga em silêncio: sem a coluna, o portão GRITA."""
    mapa = arvore / "docs/data/mapa-controles.csv"
    with mapa.open(encoding="utf-8", newline="") as fh:
        linhas = list(csv.reader(fh))
    assert "ponte_alcanca" in linhas[0]

    corte = linhas[0].index("ponte_alcanca")
    with mapa.open("w", encoding="utf-8", newline="") as fh:
        csv.writer(fh, lineterminator="\n").writerows(
            [registro[:corte] + registro[corte + 1 :] for registro in linhas]
        )

    saida = _rodar(arvore)
    assert saida.returncode != 0, (
        "a coluna `ponte_alcanca` sumiu e o portão passou. Sem ela "
        "`linha.get(...)` devolve None em toda linha e a regra aprova o mapa "
        f"inteiro sem dizer uma palavra:\n{saida.stdout[-1500:]}"
    )
    assert "integridade" in saida.stdout and "ponte_alcanca" in saida.stdout


# --------------------------------------------------------------------------
# O DOMÍNIO — para "Steam Input", "steam input" e "SteamInput" não virarem três
# --------------------------------------------------------------------------
def test_tipografia_de_ponte_reprova(arvore: Path) -> None:
    """Ponte que o produto não conhece é ponte que o mapa não pode aceitar."""
    _escreve(
        arvore / "docs/data/mapa-controles.csv",
        LINHA_SEM_PONTE,
        {"ponte_alcanca": "gamepad/dualsense+Steam Input", "ponte_de_onde_sei": "medido"},
    )

    saida = _rodar(arvore)
    assert saida.returncode != 0, (
        "`gamepad/dualsense+Steam Input` não é nenhuma das pontes da ESCADA, e "
        "o portão aceitou. Sem esta régua a mesma ponte vira três, e o mapa "
        f"deixa de casar com o produto:\n{saida.stdout[-1500:]}"
    )
    assert "ponte_alcanca` fora do domínio" in saida.stdout, saida.stdout[-1500:]


def test_procedencia_da_ponte_reusa_o_dominio_que_ja_existe(arvore: Path) -> None:
    """`ponte_de_onde_sei` responde a MESMA pergunta que `de_onde_sei`."""
    _escreve(
        arvore / "docs/data/mapa-controles.csv",
        LINHA_SEM_PONTE,
        {"ponte_alcanca": "gamepad/dualsense", "ponte_de_onde_sei": "Medido"},
    )

    saida = _rodar(arvore)
    assert saida.returncode != 0, saida.stdout[-1500:]
    assert "ponte_de_onde_sei` fora do domínio" in saida.stdout, saida.stdout[-1500:]


def test_o_dominio_sai_da_escada_de_verdade() -> None:
    """As duas réguas do mesmo dado, conferidas uma contra a outra.

    O portão roda num runner PELADO (`checkout` + `setup-python`, sem `pip
    install`) e por isso não pode importar `ponte_escada`, que puxa `structlog`.
    Ele lê a `ESCADA` por AST e recalcula a `chave` numa cópia da fórmula — e
    este teste é o preço pago por essa cópia: ele importa a `ESCADA` de verdade
    e exige as MESMAS chaves. Fórmula que mude de um lado só reprova aqui.
    """
    por_ast, motivo = dominio_das_pontes(RAIZ)
    assert por_ast is not None, motivo
    assert por_ast == frozenset(degrau.ponte.chave for degrau in ESCADA), (
        "o leitor por AST do portão e a `ESCADA` importada divergiram: "
        f"AST={sorted(por_ast)} vs import="
        f"{sorted(d.ponte.chave for d in ESCADA)}"
    )


def test_sem_a_escada_so_o_dominio_se_desliga_e_a_regra_continua(arvore: Path) -> None:
    """O desligamento é DITO — e não leva a regra 15 junto.

    Este é o teste que separa "a régua do domínio sumiu" de "o portão ficou
    cego": sem `ponte_escada.py` a conferência de tipografia se desliga em voz
    alta, mas a reprovação de `uhid` forte sem ponte continua de pé, porque para
    saber se a célula está VAZIA basta o CSV.
    """
    (arvore / PONTE_ESCADA).unlink()

    verde = _rodar(arvore)
    assert verde.returncode == 0, verde.stdout[-1500:]
    assert "regra DESLIGADA neste ambiente: integridade da `ponte_alcanca`" in verde.stdout, (
        "a régua do domínio sumiu e o portão não disse nada — desligamento "
        f"calado é o defeito que este arquivo inteiro existe para evitar:\n{verde.stdout}"
    )

    _promove_sem_dizer_a_ponte(arvore / "docs/data/mapa-controles.csv")
    vermelho = _rodar(arvore)
    assert vermelho.returncode != 0 and "ponte-nao-declarada" in vermelho.stdout, (
        "sem a ESCADA a regra 15 parou de morder — o desligamento do domínio "
        f"levou a regra junto:\n{vermelho.stdout[-1500:]}"
    )
