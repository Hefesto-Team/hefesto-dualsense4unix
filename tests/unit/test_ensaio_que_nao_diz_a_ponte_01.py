"""ENSAIO-QUE-NÃO-DIZ-A-PONTE-01: o caderno aprende POR ONDE a medição chegou.

Irmã da `ENSAIO-QUE-NAO-DIZ-O-DEGRAU-01`, do mesmo dia e da mesma família. O
`degrau` diz **até onde** a medição foi (o aparelho obedeceu? o jogo recebeu? o
jogo reagiu?); a `ponte` diz **por onde** ela chegou — máscara DualSense,
máscara Xbox, modo nativo, ou Steam Input.

**Por que as duas fazem falta juntas.** Metade das linhas `uhid` do
`mapa-controles.csv` — giroscópio, acelerômetro, os dois pontos do touchpad, o
clique, o rumble — só existe quando a máscara é a nossa DualSense
(`integrations/ponte_escada.py`, § *A assimetria, contada no mapa*). Uma medição
feita pela máscara Xbox não fala por nenhuma delas, e sem a coluna não havia
onde escrever essa diferença: o casamento ensaio↔célula era
`(linha_id, transporte)` e nada mais.

**Um censo, feito antes de escrever a coluna (20/08/2026):** dos 177 ensaios do
caderno, ZERO declaram a ponte. As ocorrências de "steam" nas notas falam do
cliente segurando o hidraw, não da ponte; `xbox` e `uinput` aparecem zero vezes.
Por isso a coluna nasce vazia em todas as linhas, e por isso o vazio precisa de
uma regra explícita em vez de um palpite.

A REGRA, e a razão de ela ser ASSIMÉTRICA
-----------------------------------------
`eliminacao.sustentam_a_ponte`:

- ensaio de ponte VAZIA sustenta afirmação de QUALQUER ponte;
- ensaio COM ponte sustenta só a DELA.

O primeiro braço não é generosidade: é o que impede a coluna nova de reprovar,
no dia em que nasce, toda célula de grau forte que hoje passa — os 177 ensaios
são anteriores ao campo. **Reprovar afirmação verdadeira é o erro que esta casa
já pagou em 12/08 e em 13/08**, e ele custa mais caro que o buraco que se está
fechando. O segundo braço é o que dá valor à declaração: quem disse por onde
mediu disse também por onde NÃO mediu.

"Vazio sustenta qualquer ponte" NÃO é "vazio serve para tudo". É a leitura mais
generosa de quem não declarou, e vale só enquanto ninguém declara.

COMO ESTES TESTES MORDEM
------------------------
- Troque o `in ("", alvo)` do `sustentam_a_ponte` por `== alvo`: o teste do
  braço legado reprova, porque os 177 ensaios sem declaração param de sustentar
  qualquer coisa.
- Troque-o por `True` (ou apague o filtro): o teste do braço declarado reprova,
  porque um ensaio pela máscara Xbox volta a sustentar afirmação sobre a
  DualSense.
- Ponha a `ponte` dentro da CHAVE do índice, como terceira peça da tupla: dois
  testes reprovam, porque os quatro chamadores escrevem `.get((ident, lado))`
  à mão e passariam a receber lista vazia — que o portão lê como "esta linha
  nunca foi ensaiada".
- Tire a coluna `ponte` do cabeçalho de `docs/data/ensaios.csv`: o primeiro
  teste reprova, e o portão dos escritores reprova junto.
- Redigite as pontes na `bancada.py` em vez de importá-las: o teste do dono
  único reprova, nomeando a chave copiada.
"""

from __future__ import annotations

import ast
import csv
import sys
from pathlib import Path

RAIZ = Path(__file__).resolve().parents[2]
CADERNO = RAIZ / "docs" / "data" / "ensaios.csv"
BANCADA = RAIZ / "bancada.py"

sys.path.insert(0, str(RAIZ / "scripts"))

import eliminacao

from hefesto_dualsense4unix.integrations.ponte_escada import ESCADA

#: As quatro chaves da escada, na fonte. Nada aqui é redigitado: se um degrau
#: novo entrar lá, ele entra neste teste junto.
CHAVES_DA_ESCADA = [degrau.ponte.chave for degrau in ESCADA]


def _ensaio(**campos: str) -> dict:
    base = {
        "id": "x-1",
        "linha_id": "vibracao.rumble.ff@dualsense",
        "transporte": "cabo",
        "degrau": "",
        "ponte": "",
        "quando": "2026-08-20T00:00:00",
        "suspeito": "qualquer",
        "presente": "sim",
        "resultado": "obedece",
        "resultado_da_feature": "",
        "observado_por": "olho-dela",
        "fonte": "teste",
        "nota": "",
        "linha_id_v1": "",
    }
    base.update(campos)
    return base


# ---------------------------------------------------------------------------
# O caderno tem a coluna, e ela nasce onde foi combinado
# ---------------------------------------------------------------------------


def test_o_caderno_tem_a_coluna_ponte_ao_lado_do_degrau() -> None:
    """Regra que lê coluna inexistente passa sempre, e passa calada."""
    with CADERNO.open(encoding="utf-8", newline="") as fh:
        cabecalho = next(csv.reader(fh))
    assert "ponte" in cabecalho, (
        "a coluna `ponte` sumiu do caderno. Sem ela não há o que casar, e um "
        "portão que não vê nada passa sempre — o defeito mais caro desta casa."
    )
    assert cabecalho.index("ponte") == cabecalho.index("degrau") + 1, (
        "`ponte` saiu de perto de `degrau`. Os dois são o mesmo tipo de eixo — "
        "um diz até onde a medição foi, o outro por onde ela chegou — e ficam "
        "lado a lado por isso."
    )


def test_os_ensaios_legados_nascem_sem_declarar_a_ponte() -> None:
    """O censo de 20/08, virado teste: nenhum dos 177 declara a ponte.

    Não é decoração. Se alguém preencher a coluna em massa — por migração
    automática, por palpite, por "isto obviamente foi pela DualSense" — este
    teste reprova, porque ponte declarada é MEDIÇÃO, e medição não se deduz de
    um ensaio que ninguém anotou.
    """
    with CADERNO.open(encoding="utf-8", newline="") as fh:
        ensaios = list(csv.DictReader(fh))
    declarados = [e["id"] for e in ensaios if (e.get("ponte") or "").strip()]
    assert not declarados, (
        f"{len(declarados)} ensaio(s) do caderno declaram ponte: {declarados[:5]}. "
        "Se a declaração veio de uma medição de verdade, some com este teste e "
        "diga na `nota` quem mediu. Se veio de dedução, apague a célula: "
        "ponte declarada é medição, e deduzi-la é fabricar prova."
    )


def test_toda_ponte_do_caderno_esta_na_escada() -> None:
    """Vocabulário fechado: `Steam Input`, `steam input` e `SteamInput` seriam três."""
    with CADERNO.open(encoding="utf-8", newline="") as fh:
        ensaios = list(csv.DictReader(fh))
    fora = sorted(
        {
            (e.get("ponte") or "").strip()
            for e in ensaios
            if (e.get("ponte") or "").strip()
        }
        - set(CHAVES_DA_ESCADA)
    )
    assert not fora, (
        f"o caderno tem ponte(s) fora da escada: {fora}. O vocabulário é o de "
        f"`integrations/ponte_escada.py` ({CHAVES_DA_ESCADA}); qualquer outra "
        "grafia cria uma ponte nova que ninguém consegue casar."
    )


# ---------------------------------------------------------------------------
# A regra de compatibilidade, os dois braços
# ---------------------------------------------------------------------------


def test_ensaio_sem_ponte_sustenta_qualquer_ponte() -> None:
    """O braço legado — e o que ele impede é reprovar afirmação VERDADEIRA."""
    legado = _ensaio(id="legado-1", ponte="")
    for chave in CHAVES_DA_ESCADA:
        assert eliminacao.sustentam_a_ponte([legado], chave) == [legado], (
            f"o ensaio sem declaração deixou de sustentar `{chave}`. Os 177 "
            "ensaios do caderno são anteriores à coluna: recusá-los reprova "
            "hoje toda célula de grau forte que passa, que é o erro de 12/08."
        )


def test_ensaio_com_ponte_sustenta_so_a_dela() -> None:
    """O braço declarado — sem ele a coluna não vale nada."""
    pela_xbox = _ensaio(id="xbox-1", ponte="gamepad/xbox")
    assert eliminacao.sustentam_a_ponte([pela_xbox], "gamepad/xbox") == [pela_xbox]
    assert eliminacao.sustentam_a_ponte([pela_xbox], "gamepad/dualsense") == [], (
        "um ensaio medido pela máscara Xbox sustentou afirmação sobre a "
        "máscara DualSense. Metade das linhas `uhid` do mapa — giroscópio, "
        "touchpad, rumble — só existe pela DualSense; aceitar um pelo outro é "
        "exatamente a mentira que esta coluna existe para pegar."
    )


def test_afirmacao_sem_ponte_nao_discrimina_nada() -> None:
    """Ponte vazia do lado da AFIRMAÇÃO quer dizer "também não declarei"."""
    mistura = [
        _ensaio(id="a", ponte=""),
        _ensaio(id="b", ponte="gamepad/xbox"),
        _ensaio(id="c", ponte="native/-"),
    ]
    assert eliminacao.sustentam_a_ponte(mistura, "") == mistura
    assert eliminacao.sustentam_a_ponte(mistura, "   ") == mistura


# ---------------------------------------------------------------------------
# Compatibilidade: os quatro chamadores continuam vendo o caderno inteiro
# ---------------------------------------------------------------------------


def test_carrega_por_lado_sem_ponte_nao_perde_ensaio() -> None:
    """Sem `ponte`, o comportamento é o de sempre — ninguém some.

    `bancada.py` (duas vezes), `gerar-mapa.py` e `check_paridade_transporte.py`
    chamam sem o parâmetro. Se o padrão passasse a filtrar, os quatro
    devolveriam menos ensaios calados — e lista vazia é justamente o que o
    portão lê como "não há ensaio nenhum".
    """
    with CADERNO.open(encoding="utf-8", newline="") as fh:
        total = len(list(csv.DictReader(fh)))
    por_lado = eliminacao.carrega_por_lado(CADERNO)
    assert sum(len(v) for v in por_lado.values()) == total


def test_carrega_por_lado_com_ponte_filtra_pela_regra(tmp_path: Path) -> None:
    """O terceiro eixo do casamento, ponta a ponta e a partir do disco."""
    caminho = tmp_path / "ensaios.csv"
    linhas = [
        _ensaio(id="legado", ponte=""),
        _ensaio(id="pela-xbox", ponte="gamepad/xbox"),
        _ensaio(id="pela-dualsense", ponte="gamepad/dualsense"),
    ]
    with caminho.open("w", encoding="utf-8", newline="") as fh:
        escritor = csv.DictWriter(fh, fieldnames=list(linhas[0]), lineterminator="\n")
        escritor.writeheader()
        escritor.writerows(linhas)

    chave = ("vibracao.rumble.ff@dualsense", "cabo")
    vistos = eliminacao.carrega_por_lado(caminho, "gamepad/dualsense")[chave]
    assert [e["id"] for e in vistos] == ["legado", "pela-dualsense"]

    assert eliminacao.carrega_por_lado(caminho, "native/-")[chave] == [
        e for e in vistos if e["id"] == "legado"
    ]


def test_a_chave_do_indice_continua_sendo_o_par() -> None:
    """A chave NÃO virou tripla, e isso é decisão, não esquecimento.

    Os quatro chamadores escrevem `.get((ident, lado), [])` à mão. Uma chave de
    três peças faria os quatro devolverem lista vazia sem estourar nada — e o
    portão lê lista vazia como "esta linha nunca foi ensaiada". A ponte entra
    por PARÂMETRO por isso.
    """
    for chave in eliminacao.carrega_por_lado(CADERNO):
        assert isinstance(chave, tuple) and len(chave) == 2, (
            f"a chave do índice virou {chave!r}. Quem lê o caderno espera "
            "`(linha_id, transporte)`; mudar isso quebra os quatro chamadores "
            "em silêncio."
        )
        break


# ---------------------------------------------------------------------------
# O dono do vocabulário é um só
# ---------------------------------------------------------------------------


def test_a_bancada_importa_as_pontes_em_vez_de_redigitar() -> None:
    """ESCADA-COM-UM-DONO-SO, aplicada à coluna nova.

    Em 19/08 duas listas do mesmo vocabulário divergiram: o portão ganhou dois
    degraus e o formulário da bancada não, de modo que ele os ACEITAVA e ela não
    conseguia ESCREVÊ-los. A segunda cópia é o defeito; este teste recusa que
    ela nasça.
    """
    fonte = BANCADA.read_text(encoding="utf-8")
    arvore = ast.parse(fonte)
    importa = any(
        isinstance(no, ast.ImportFrom)
        and (no.module or "").endswith("ponte_escada")
        and any(alias.name == "ESCADA" for alias in no.names)
        for no in ast.walk(arvore)
    )
    assert importa, (
        "a bancada parou de importar a `ESCADA` de `integrations/ponte_escada`. "
        "Sem o import, as opções do seletor de ponte viram uma segunda cópia do "
        "vocabulário — e duas cópias divergem no dia em que alguém mexe numa."
    )

    #: As chaves da escada NÃO podem aparecer escritas na bancada. Só os
    #: comentários podem citá-las; código, nunca.
    literais = {
        no.value
        for no in ast.walk(arvore)
        if isinstance(no, ast.Constant) and isinstance(no.value, str)
    }
    copiadas = sorted(literais & set(CHAVES_DA_ESCADA))
    assert not copiadas, (
        f"a bancada redigita a(s) ponte(s) {copiadas} como literal. O dono do "
        "vocabulário é `integrations/ponte_escada.py`, e a lista `PONTES` sai "
        "dele — nunca das teclas de quem estiver editando."
    )
