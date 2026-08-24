"""Z6-10 — a régua da população é a de hoje, e é DECLARAÇÃO, nunca FLUXO.

O achado da sprint (§2.4 e §2.5 de
docs/process/sprints/2026-08-24-ONDA0-Z6-COMUNHAO-COM-O-SPECS-01-…md):
`scripts/validar-palavra-de-tela.py` já varre `app/**.py` por AST e sabe
achar "escoadouro de tela" (`set_label`, `set_tooltip_text`, …) — mas essa
descoberta por FLUXO tem falso-negativo medido perto de 100% para constante
de módulo consumida de OUTRO arquivo: o rastreador conhece só dois nomes
(`DICA`, `TITULO`) que atravessam módulo, e `DICA_DA_COR_NO_RADIO` (o caso
que já mentiu uma vez, 17-23/08) não era um deles.

A mordida da sprint: "Fazer o portão da Z6-04 tentar descobrir a população
por FLUXO em vez de por DECLARAÇÃO → tem de deixar `external_card.py:86`
passar, e o teste que trava isso reprova." Este arquivo é esse trava: prova
que `descobre_falas` acha uma `Fala` pela PRESENÇA da chamada `Fala(...)`,
nunca por rastrear se o nome chega a um escoadouro de widget — então o caso
que a régua de fluxo não alcançava (constante de módulo, consumida por outro
arquivo, atrás de um `if` que pode nunca disparar) este continua alcançando.
"""
from __future__ import annotations

import subprocess
import sys
from pathlib import Path

RAIZ_REAL = Path(__file__).resolve().parents[2]
SCRIPT = RAIZ_REAL / "scripts" / "validar-fala-de-tela.py"
FALA_DO_MAPA_REAL = RAIZ_REAL / "src" / "hefesto_dualsense4unix" / "app" / "fala_do_mapa.py"

FATOS_DE_MENTIRA = (
    '"""de mentira."""\nfrom __future__ import annotations\nfrom typing import Final\n'
    'FATOS: Final[dict] = {"identidade.cor_do_aparelho@dualsense": '
    '{"existe": "tem", "radio": {"aciona": "não", "de_onde_sei": "medido", '
    '"por_que_nao_aciona": "o-aparelho-recusa"}, "cabo": {"aciona": "sim", '
    '"de_onde_sei": "medido", "por_que_nao_aciona": ""}}}\n'
)

#: O CASO REAL, na forma REAL: uma `Fala` de módulo, atrás de um `if` que só
#: dispara em certas condições, consumida por um MÉTODO DE OUTRO ARQUIVO (o
#: molde exato de `external_card.py:86` + `secao_controles.py`). Uma régua de
#: FLUXO teria de provar que este `if` é alcançável E que o valor atravessa
#: até um `set_label`/`set_tooltip_text` em outro módulo — exatamente o que
#: §2.5 mediu como alcance quase nulo.
ARQUIVO_COM_FALA_ATRAS_DE_CONDICIONAL = '''
from hefesto_dualsense4unix.app.fala_do_mapa import AFIRMA_NAO_ACIONA, Fala

DICA_DA_COR_NO_RADIO = Fala(
    chave="identidade.cor_do_aparelho@dualsense",
    lado="radio",
    aba="Configurações",
    texto="No rádio o controle recusa o pedido da cor. Escolha na lista.",
    afirma=AFIRMA_NAO_ACIONA,
)


def _linha_da_cor(dados):
    """Só chega aqui se `cor_lida` for verdadeiro — o `if` que a régua de
    fluxo teria de provar alcançável antes de sequer olhar o texto."""
    if not dados.cor_id and dados.cor_lida:
        dica = DICA_DA_COR_NO_RADIO  # consumida por OUTRO widget, em tese
        return dica
    return None
'''


def monta_arvore(tmp_path: Path) -> Path:
    app = tmp_path / "src" / "hefesto_dualsense4unix" / "app"
    app.mkdir(parents=True, exist_ok=True)
    (app / "fala_do_mapa.py").write_text(
        FALA_DO_MAPA_REAL.read_text(encoding="utf-8"), encoding="utf-8"
    )
    (app / "fatos_do_mapa.py").write_text(FATOS_DE_MENTIRA, encoding="utf-8")
    (app / "widgets").mkdir(exist_ok=True)
    (app / "widgets" / "external_card.py").write_text(
        ARQUIVO_COM_FALA_ATRAS_DE_CONDICIONAL, encoding="utf-8"
    )
    return tmp_path


def rodar(raiz: Path) -> subprocess.CompletedProcess[str]:
    return subprocess.run(
        [sys.executable, str(SCRIPT), "--raiz", str(raiz), "--all"],
        capture_output=True,
        text=True,
        check=False,
    )


def test_a_fala_atras_do_condicional_e_encontrada_mesmo_sem_analise_de_fluxo(
    tmp_path: Path,
) -> None:
    """A régua acha a `Fala` pela DECLARAÇÃO — nunca precisou provar que o
    `if` dispara nem que `dica` chega a um widget em outro arquivo.
    """
    raiz = monta_arvore(tmp_path)
    processo = rodar(raiz)
    assert processo.returncode == 0, processo.stdout
    assert "1 `Fala`" in processo.stdout


def test_descobre_falas_nao_depende_de_alcancabilidade_nem_de_uso() -> None:
    """Prova estrutural, direta na função: nenhuma parte de `descobre_falas`
    executa o código encontrado nem rastreia quem consome o nome — ela só
    caminha o AST procurando `ast.Call` cujo `func` é `Fala`. Ler o próprio
    código do portão é a forma mais curta de travar isto: se algum dia
    alguém acrescentar rastreamento de fluxo aqui, esta asserção denuncia.
    """
    fonte = SCRIPT.read_text(encoding="utf-8")
    # Os verbos de rastreamento por fluxo que `validar-palavra-de-tela.py`
    # usa (widget "escoadouro", resolução de variável entre atribuição e
    # uso) não têm lugar em `validar-fala-de-tela.py` — a régua daqui é mais
    # simples DE PROPÓSITO, e é essa simplicidade que a torna completa para
    # o que ela promete (achar `Fala(...)`), ao custo de exigir declaração.
    proibidos = ("escoadouro", "set_label", "set_tooltip_text", "resolve_variavel")
    for termo in proibidos:
        assert termo not in fonte, (
            f"{termo!r} em validar-fala-de-tela.py — rastreamento por fluxo "
            "reintroduziria o falso-negativo medido em §2.5 da Z6"
        )
