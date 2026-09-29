"""A linha «Háptica por áudio» na aba Vibração — A-LINHA-DA-HAPTICA-POR-AUDIO-NA-VIBRACAO-01.

Ela, 29/09/2026, com a foto da aba: *«precisamos de uma linha disso na
interface. e precisamos que isso funcione no modo bt também.»* <!-- noqa-acento: citação literal dela -->
E depois: *«temos que ter um controle da parte haptica pq tanto no cabo ficou
muito baixo»*. <!-- noqa-acento: citação literal dela -->

A linha é o interruptor, o trilho de 0 a 200 e o número, por controle, P1 a P4,
pelo mesmo gerador da coluna. O que ela grava é o `haptica_pct` do perfil, pelo
mesmo `rumble.motores.set` dos motores, e a régua relê o DISCO, e não o eco do
pedido.
"""

from __future__ import annotations

import re
from pathlib import Path
from typing import Any

import pytest

from tests.conftest import exigir_gi_real

exigir_gi_real("importa `interface.pacotes`, que carrega o GTK")

from hefesto_dualsense4unix.interface import aba05, pacotes  # noqa: E402
from hefesto_dualsense4unix.interface.pacotes import a05_vibracao as a05  # noqa: E402
from hefesto_dualsense4unix.profiles import loader as loader_module  # noqa: E402
from hefesto_dualsense4unix.profiles.loader import save_profile  # noqa: E402
from hefesto_dualsense4unix.profiles.schema import (  # noqa: E402
    HAPTICA_PCT_MAX,
    HAPTICA_PCT_PADRAO,
    MatchAny,
    Profile,
)
from tests.unit.test_cada_motor_tem_o_seu_multiplicador import (  # noqa: E402
    BRANCO,
    _Handlers,
)

RAIZ = Path(__file__).resolve().parents[2]
MOCKUP = RAIZ / "mockup/05-vibracao.html"
UNIQ = "aa:bb:cc:00:00:01"

#: Os quatro endereços da linha, por lugar.
ENDERECOS = ("barra-h", "lado-h", "barra-h-pct", "haptica-fora")


def _bloco(html: str, pref: str) -> str:
    """O HTML de UM lugar (`data-controle="pN"`) até o lugar seguinte."""
    inicio = html.index(f'data-controle="{pref}"')
    seguinte = html.find('data-controle="p', inicio + 10)
    return html[inicio: seguinte if seguinte > 0 else len(html)]


def _ctx(haptica: int | None = None, alcanca: bool | None = None,
         padrao: int | None = HAPTICA_PCT_PADRAO) -> pacotes.Contexto:
    controle: dict[str, Any] = {"uniq": UNIQ, "connected": True, "player": 1,
                                "transport": "usb"}
    if haptica is not None:
        controle["haptica_pct"] = haptica
    if alcanca is not None:
        controle["haptica_alcanca"] = alcanca
    state: dict[str, Any] = {"controllers": [controle], "rumble_policy": "balanceado"}
    if padrao is not None:
        state["haptica_pct_padrao"] = padrao
    item = {"uniq": UNIQ, "pref": "p1", "jogador": 1, "nome": "Prova",
            "cor": "", "transporte": "usb", "via": "cabo",
            "alvo": True, "mascara": "dualsense"}
    return pacotes.Contexto(state=state, mesa=[item], conectados=[controle],
                            estados={}, externos=[])


def _coluna(**kw: Any) -> dict[str, Any]:
    colunas = a05.pacote(_ctx(**kw))["colunas"]
    assert len(colunas) == 1
    return next(iter(colunas.values()))


class _PonteQueGrava:
    """A ponte do app com o handler de verdade do daemon por trás (o disco é o de prova)."""

    def __init__(self, handlers: _Handlers) -> None:
        self.h = handlers
        self.pedidos: list[dict[str, Any]] = []

    def rumble_motores_set(self, **k: Any) -> tuple[bool, dict[str, Any]]:
        import asyncio

        self.pedidos.append(k)
        return True, asyncio.run(self.h._handle_rumble_motores_set(dict(k)))


@pytest.fixture
def perfis(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> Path:
    alvo = tmp_path / "profiles"
    alvo.mkdir()

    def _dir(ensure: bool = False) -> Path:
        if ensure:
            alvo.mkdir(parents=True, exist_ok=True)
        return alvo

    monkeypatch.setattr(loader_module, "profiles_dir", _dir)
    return alvo


# ---------------------------------------------------------------------------
# 1. A linha tem endereço nos quatro lugares
# ---------------------------------------------------------------------------


class TestOEndereco:
    def test_os_quatro_lugares_tem_a_linha(self) -> None:
        """Régua 1, sobre o HTML que o GERADOR escreve, cheio e vazio.

        MORDIDA: emitir a linha só em quem tem controle → P3 e P4 reprovam.
        """
        html = "".join(aba05._coluna(c) for c in aba05.MESA)
        assert len(aba05.MESA) == 4
        for c in aba05.MESA:
            bloco = _bloco(html, c["pref"])
            for campo in ENDERECOS:
                assert bloco.count(f'data-campo="{campo}"') == 1, (
                    f"{c['pref']} sem o endereço {campo!r}")

    def test_o_mockup_escrito_pelo_gerador_tem_a_linha(self) -> None:
        html = MOCKUP.read_text(encoding="utf-8")
        for pref in ("p1", "p2", "p3", "p4"):
            bloco = _bloco(html, pref)
            for campo in ENDERECOS:
                assert f'data-campo="{campo}"' in bloco, (pref, campo)
        assert '<span class="sec-rot">Háptica por áudio' in html

    def test_o_teto_e_lido_do_esquema(self) -> None:
        """Régua 4: o `max` do trilho é o `HAPTICA_PCT_MAX`. MORDIDA: digitar 100.

        No que o gerador escreve agora E no mockup que ele escreveu.
        """
        for html in ("".join(aba05._coluna(c) for c in aba05.MESA),
                     MOCKUP.read_text(encoding="utf-8")):
            trilhos = [t for t in re.findall(r'<input class="trilho arrasta"[^>]*>', html)
                       if 'data-campo="barra-h"' in t]
            assert len(trilhos) == 4
            for tag in trilhos:
                assert f'max="{HAPTICA_PCT_MAX}"' in tag and 'data-papel="haptica"' in tag

    def test_a_grade_paga_a_linha_com_o_desenho(self) -> None:
        """Os 46 px saem de `--r-des` (124 → 78), e a grade ganha a terceira faixa."""
        css = aba05.CSS
        assert "--r-des:78px" in css
        assert "var(--r-motor) var(--r-motor) var(--r-motor) var(--r-acoes);" in css


# ---------------------------------------------------------------------------
# 2. O arraste grava onde o daemon lê
# ---------------------------------------------------------------------------


class TestOGesto:
    def test_o_arraste_grava_no_perfil(self, perfis: Path) -> None:
        """Régua 2: o trilho a 180 → o disco lido pelo esquema diz 180.

        MORDIDA: o gesto gravar só na tela (não chamar a ponte) → reprova.
        """
        save_profile(Profile(name="Bancada", match=MatchAny()))
        ponte = _PonteQueGrava(_Handlers(ativo="Bancada", primario=BRANCO))
        gesto = pacotes.gesto_da_pagina("05-vibracao.html", "haptica")
        assert gesto is not None
        gesto(_ctx(haptica=HAPTICA_PCT_PADRAO), {"uniq": BRANCO, "valor": "180"}, ponte)
        dele = (loader_module.load_profile("Bancada").controllers or {})[BRANCO]
        assert dele.rumble is not None and dele.rumble.haptica_pct == 180

    @pytest.mark.parametrize(("antes", "grava"), [(150, 0), (180, 0), (0, HAPTICA_PCT_PADRAO)])
    def test_o_interruptor_e_o_par_da_barra(self, antes: int, grava: int) -> None:
        """Régua 3: desligar grava 0, ligar grava o padrão que o `state_full` diz.

        MORDIDA: um `ligado` à parte (o clique sem mexer no número) → reprova.
        """
        pedidos: list[dict[str, Any]] = []

        class _P:
            def rumble_motores_set(self, **k: Any) -> tuple[bool, dict[str, str]]:
                pedidos.append(k)
                return True, {"status": "ok"}

        gesto = pacotes.gesto_da_pagina("05-vibracao.html", "haptica")
        assert gesto is not None
        gesto(_ctx(haptica=antes), {"uniq": UNIQ, "valor": ""}, _P())
        assert pedidos == [{"haptica_pct": grava, "uniq": UNIQ}]

    def test_ligar_devolve_o_padrao_publicado_e_nao_um_digitado(self) -> None:
        pedidos: list[dict[str, Any]] = []

        class _P:
            def rumble_motores_set(self, **k: Any) -> tuple[bool, dict[str, str]]:
                pedidos.append(k)
                return True, {"status": "ok"}

        gesto = pacotes.gesto_da_pagina("05-vibracao.html", "haptica")
        assert gesto is not None
        gesto(_ctx(haptica=0, padrao=120), {"uniq": UNIQ, "valor": ""}, _P())
        assert pedidos[0]["haptica_pct"] == 120

    def test_a_recusa_do_daemon_chega_dizendo(self) -> None:
        class _P:
            def rumble_motores_set(self, **k: Any) -> tuple[bool, dict[str, str]]:
                return True, {"status": "sem_perfil", "motivo": "Ative um perfil e repita"}

        gesto = pacotes.gesto_da_pagina("05-vibracao.html", "haptica")
        assert gesto is not None
        with pytest.raises(RuntimeError, match="Ative um perfil"):
            gesto(_ctx(haptica=150), {"uniq": UNIQ, "valor": "90"}, _P())


# ---------------------------------------------------------------------------
# 3. A pintura: o número do dono, o aceso e o cinza
# ---------------------------------------------------------------------------


class TestAPintura:
    def test_o_numero_e_o_do_dono(self) -> None:
        coluna = _coluna(haptica=180, alcanca=True)
        assert (coluna["barra-h"], coluna["barra-h-pct"], coluna["lado-h"]) == ("180", "180", "1")
        assert coluna["haptica-fora"] == ""

    def test_sem_o_numero_vale_o_padrao_publicado(self) -> None:
        coluna = _coluna(padrao=HAPTICA_PCT_PADRAO)
        assert coluna["barra-h"] == str(HAPTICA_PCT_PADRAO)

    def test_desligada_apaga_o_interruptor(self) -> None:
        assert _coluna(haptica=0)["lado-h"] == ""

    def test_cinza_onde_o_hefesto_nao_alcanca(self) -> None:
        """Régua 6: `haptica_alcanca=False` → a linha cinza e o trilho inerte.

        MORDIDA: ignorar o campo → reprova.
        """
        assert _coluna(haptica=150, alcanca=False)["haptica-fora"] == "1"
        html = MOCKUP.read_text(encoding="utf-8")
        assert 'data-campo="haptica-fora" data-hef-alvo="classe" data-hef-classe="fora"' in html
        assert ".motor.haptica.fora .trilho.arrasta" in aba05.CSS
