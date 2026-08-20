"""PONTE-NO-MAPA-01: as dez linhas `uhid` dizem, no dado, por qual ponte chegam.

O QUE ESTE ARQUIVO GUARDA
------------------------
Desde 19/08/2026 o `integrations/ponte_escada.py` afirma, POR ESCRITO, que dez
linhas do `mapa-controles.csv` só chegam ao JOGO pela máscara DualSense — é a
afirmação que põe a DualSense no primeiro degrau da escada, e ela vale dinheiro:
*"errar para Xbox custa dez linhas do mapa, e custa em silêncio"*.

Até 20/08/2026 essa afirmação vivia só na prosa de um módulo Python. O mapa —
que é a memória externa desta casa, e o portão que reprova regressão de canal —
não tinha onde guardá-la: `transporte` diz por qual FIO a feature chega ao
Hefesto, e não existia coluna para dizer por qual PONTE ela chega ao jogo.

As colunas `ponte_alcanca` e `ponte_de_onde_sei` são essa gaveta. Elas nasceram
com DEZ células preenchidas e nenhuma medição nova: mover uma afirmação já
escrita e já testada para o lugar onde ela é conferível não é medir.

POR QUE AS DUAS COLUNAS SÃO GLOBAIS, E NÃO UM PAR `cabo_`/`radio_`
------------------------------------------------------------------
Porque a ponte não é uma pergunta de transporte. O `pares_de_transporte()` do
`check_paridade_transporte.py` descobre os pares pelo SUFIXO, lendo o cabeçalho:
qualquer coluna chamada `cabo_ponte_alcanca` viraria par no ato, e o portão
passaria a cobrar paridade cabo↔rádio de um dado que não fala de fio nenhum. As
dez linhas são `uhid` nos DOIS transportes — não há assimetria a declarar.

COMO ESTES TESTES MORDEM
------------------------
- Apague o `gamepad/dualsense` de qualquer uma das dez células: o primeiro teste
  reprova nomeando a chave que ficou muda.
- Preencha `ponte_alcanca` sem preencher `ponte_de_onde_sei` (ou o contrário): o
  segundo teste reprova nomeando a linha — uma afirmação sem procedência é o que
  esta casa chama de fato órfão.
- Renomeie as colunas para `cabo_ponte_alcanca`/`radio_ponte_alcanca`: o
  terceiro teste reprova, porque `pares_de_transporte()` passa a enxergar um par
  novo.
- Troque o valor das dez por uma ponte que não seja a do primeiro degrau da
  `ESCADA` (por exemplo `gamepad/xbox`): o primeiro teste reprova, porque o
  valor esperado é IMPORTADO de `integrations/ponte_escada`, nunca redigitado.
"""

from __future__ import annotations

import csv
import sys
from pathlib import Path

RAIZ = Path(__file__).resolve().parents[2]
MAPA = RAIZ / "docs" / "data" / "mapa-controles.csv"

sys.path.insert(0, str(RAIZ / "scripts"))
sys.path.insert(0, str(RAIZ / "src"))

from check_paridade_transporte import pares_de_transporte
from hefesto_dualsense4unix.integrations.ponte_escada import ESCADA

#: A ponte do PRIMEIRO degrau — a nossa máscara DualSense. Vem da `ESCADA`
#: porque a lista tem um dono só: redigitar `"gamepad/dualsense"` aqui criaria a
#: segunda cópia que a `ESCADA-COM-UM-DONO-SO` existe para impedir.
PONTE_DA_DUALSENSE = ESCADA[0].ponte.chave

#: `plataforma.vpad` é `uhid` e fica de fora: é o MECANISMO (o gamepad virtual
#: em si), não uma feature que o jogo perca ao trocar de máscara. A mesma
#: exclusão, com a mesma justificativa, está em `test_ponte_escada.py`.
NAO_E_FEATURE = {"plataforma.vpad"}


def _linhas() -> list[dict[str, str]]:
    with MAPA.open(encoding="utf-8", newline="") as fh:
        return list(csv.DictReader(fh))


def _cabecalho() -> list[str]:
    with MAPA.open(encoding="utf-8", newline="") as fh:
        return next(csv.reader(fh))


def _as_dez(linhas: list[dict[str, str]]) -> list[dict[str, str]]:
    """As features do DualSense que só chegam ao jogo por `uhid`.

    Derivadas do DADO, nunca de uma lista copiada: no dia em que uma feature
    nova nascer `uhid` no DualSense, ela entra nesta conta sozinha — e o teste
    passa a cobrar dela a declaração da ponte, que é exatamente o que se quer.
    """
    return [
        lin
        for lin in linhas
        if lin["controle"] == "dualsense"
        and lin["chave"] not in NAO_E_FEATURE
        and "uhid" in (lin["cabo_canal"], lin["radio_canal"])
    ]


class TestAsDezDizemAPonte:
    def test_toda_linha_uhid_do_dualsense_declara_a_ponte(self) -> None:
        """A afirmação que sustenta o primeiro degrau está no dado, não só na prosa."""
        mudas = [
            lin["id"]
            for lin in _as_dez(_linhas())
            if (lin["ponte_alcanca"] or "").strip() != PONTE_DA_DUALSENSE
        ]
        assert not mudas, (
            "estas linhas chegam ao jogo por `uhid`, que só existe sob a máscara "
            f"DualSense, e não declaram `ponte_alcanca = {PONTE_DA_DUALSENSE}`: "
            f"{mudas} — é a afirmação do primeiro degrau de "
            "`integrations/ponte_escada.py` ficando sem lugar no mapa"
        )

    def test_sao_dez_e_elas_tem_nome(self) -> None:
        """Nomeia, nunca só conta (WRAPPER-EM-TODOS-01)."""
        chaves = sorted(lin["chave"] for lin in _as_dez(_linhas()))
        assert chaves == [
            "audio.jack.deteccao",
            "energia.bateria.jogo",
            "luz.replica_output_jogo",
            "movimento.acelerometro.jogo",
            "movimento.giroscopio.jogo",
            "movimento.giroscopio.taxa",
            "toque.touchpad",
            "toque.touchpad.clique",
            "vibracao.rumble.ff",
            "vibracao.rumble.passthrough",
        ], (
            "a lista de dez linhas `uhid` do DualSense mudou; o cabeçalho de "
            "`integrations/ponte_escada.py` conta DEZ e é essa conta que "
            "justifica a ordem da escada — as duas têm de mudar juntas"
        )


class TestAfirmacaoNaoNasceOrfa:
    def test_quem_declara_a_ponte_declara_de_onde_sabe(self) -> None:
        """Ponte sem procedência é fato órfão — o mapa já tem coluna para isso."""
        orfas = [
            lin["id"]
            for lin in _linhas()
            if bool((lin["ponte_alcanca"] or "").strip())
            != bool((lin["ponte_de_onde_sei"] or "").strip())
        ]
        assert not orfas, (
            "`ponte_alcanca` e `ponte_de_onde_sei` andam juntas — uma afirmação "
            f"sem procedência (ou o contrário) ficou nestas linhas: {orfas}"
        )


class TestAPonteNaoEPerguntaDeTransporte:
    def test_as_duas_colunas_ficam_fora_do_pareamento(self) -> None:
        """Nenhuma das duas pode virar par `cabo_`/`radio_`."""
        cabecalho = _cabecalho()
        assert "ponte_alcanca" in cabecalho and "ponte_de_onde_sei" in cabecalho, (
            "o mapa perdeu a gaveta da ponte; sem ela a afirmação do primeiro "
            "degrau volta a viver só na prosa de `ponte_escada.py`"
        )
        sufixos = pares_de_transporte(cabecalho)
        intrusos = [s for s in sufixos if "ponte" in s]
        assert not intrusos, (
            f"`pares_de_transporte()` passou a enxergar {intrusos} como par de "
            "transporte: o portão cobraria paridade cabo↔rádio de um dado que "
            "não fala de fio nenhum, e as dez linhas são `uhid` nos DOIS"
        )

    def test_a_ponte_fica_ao_lado_do_transporte(self) -> None:
        """`transporte` diz por qual fio; `ponte_alcanca`, por qual ponte."""
        cabecalho = _cabecalho()
        assert cabecalho.index("ponte_alcanca") == cabecalho.index("transporte") + 1
        assert cabecalho.index("ponte_de_onde_sei") == cabecalho.index("ponte_alcanca") + 1
