"""A aba Vibração ganha as duas listas por controle (sprint dos botões de efeito, V3).

Cada controle tem o seu «Efeito háptico» e o seu «Padrão dos motores», listas suspensas (15/10/2026,
«quero uma lista suspensa em cada escolha»). A primeira é «Do estilo» e a segunda «Sem efeito».
A escolha vai ao perfil pelo ``rumble.motores.set``, na peça do clique, e «Do estilo» apaga a chave.
"""

from __future__ import annotations

import asyncio
import re
import time
from pathlib import Path
from typing import Any

import pytest


from hefesto_dualsense4unix.daemon.subsystems import padroes_de_vibracao as padroes
from hefesto_dualsense4unix.interface import aba05, pacotes
from hefesto_dualsense4unix.interface.pacotes import a05_vibracao as a05
from hefesto_dualsense4unix.profiles import formas_de_haptica as formas
from hefesto_dualsense4unix.profiles import loader as loader_module
from hefesto_dualsense4unix.profiles.loader import save_profile
from hefesto_dualsense4unix.profiles.o_padrao_do_computador import o_que_vale
from hefesto_dualsense4unix.profiles.schema import (
    ControllerOverrides,
    ControllerRumbleOverride,
    MatchAny,
    Profile,
)
from hefesto_dualsense4unix.utils import xdg_paths
from tests.unit.test_cada_motor_tem_o_seu_multiplicador import BRANCO, _Handlers

RAIZ = Path(__file__).resolve().parents[2]
MOCKUP = RAIZ / "mockup/05-vibracao.html"
UNIQ = BRANCO
GESTOS = {"efeito_haptico": "efeito-haptico", "efeito_imersao": "efeito-imersao"}
LISTAS = {
    "efeito-haptico": (formas.ESCOLHAS, formas.ROTULOS, formas.DICAS),
    "efeito-imersao": (padroes.ESCOLHAS, aba05._ROTULOS_DA_IMERSAO, padroes.DICAS),
}


def _bloco(html: str, pref: str) -> str:
    inicio = html.index(f'data-controle="{pref}"')
    seguinte = html.find('data-controle="p', inicio + 10)
    return html[inicio: seguinte if seguinte > 0 else len(html)]


def _ctx(ativo: str = "") -> pacotes.Contexto:
    controle: dict[str, Any] = {"uniq": UNIQ, "connected": True, "player": 1, "transport": "usb"}
    state: dict[str, Any] = {
        "controllers": [controle], "rumble_policy": "max", "active_profile": ativo}
    item = {"uniq": UNIQ, "pref": "p1", "jogador": 1, "nome": "Prova", "cor": "",
            "transporte": "usb", "via": "cabo", "alvo": True, "mascara": "dualsense"}
    return pacotes.Contexto(state=state, mesa=[item], conectados=[controle],
                            estados={}, externos=[])


class _PonteQueGrava:
    """A ponte do app com o handler de verdade do daemon por trás (o disco é o de prova)."""

    def __init__(self, handlers: _Handlers) -> None:
        self.h = handlers
        self.pedidos: list[dict[str, Any]] = []
        self.chamadas: list[tuple[str, tuple[Any, ...], dict[str, Any]]] = []

    def rumble_motores_set(self, **k: Any) -> tuple[bool, dict[str, Any]]:
        self.pedidos.append(k)
        return True, asyncio.run(self.h._handle_rumble_motores_set(dict(k)))

    def __getattr__(self, nome: str) -> Any:
        def registrar(*a: Any, **k: Any) -> Any:
            self.chamadas.append((nome, a, k))
            com_corpo = nome.endswith("_checked") or nome == "haptica_testar"
            return (True, None) if com_corpo else True
        return registrar


@pytest.fixture
def perfis(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> Path:
    alvo = tmp_path / "profiles"
    alvo.mkdir()

    def _dir(ensure: bool = False) -> Path:
        if ensure:
            alvo.mkdir(parents=True, exist_ok=True)
        return alvo

    monkeypatch.setattr(loader_module, "profiles_dir", _dir)
    monkeypatch.setattr(xdg_paths, "profiles_dir", _dir)
    return alvo


def _rumble_do_disco() -> ControllerRumbleOverride | None:
    dele = (o_que_vale(loader_module.load_profile("Bancada")).controllers or {}).get(BRANCO)
    return dele.rumble if dele is not None else None


class TestAsLinhas:
    def test_as_nove_faixas_na_ordem_do_desenho_a(self) -> None:
        """Controle, Modelo, Força, Sensor háptico, Efeito háptico, motores, Padrão, Testar.

        MORDIDA: trocar a ordem das duas linhas no gerador reprova.

        Prova da D-1610-AS-LISTAS-DE-EFEITO-POR-CONTROLE-NA-ABA-VIBRACAO.
        """
        html = MOCKUP.read_text(encoding="utf-8")
        rotulos = re.findall(r'<span class="sec-rot"[^>]*>([^<]+)</span>',
                             html.split('<div class="rotulos">', 1)[1]
                             .split('<div class="ctrl', 1)[0])
        assert rotulos == ["Controle", "Modelo", "Força da vibração", "Sensor háptico",
                           "Efeito háptico", aba05.ESQ["rot"], aba05.DIR["rot"],
                           "Padrão dos motores", "Testar agora"]

    def test_em_cada_coluna_as_listas_ficam_ao_lado_de_quem_governam(self) -> None:
        """Na coluna: Sensor háptico, Efeito háptico, os dois motores, Padrão, Testar."""
        html = "".join(aba05._coluna(c) for c in aba05.MESA)
        for c in aba05.MESA:
            bloco = _bloco(html, c["pref"])
            ordem = [bloco.index(m) for m in (
                'data-campo="haptica-fora"', 'data-campo="haptico-escolha"',
                'data-campo="motor-e-pedido"', 'data-campo="motor-d-pedido"',
                'data-campo="imersao-escolha"', 'class="acoes-col"')]
            assert ordem == sorted(ordem), f"{c['pref']}: as faixas saíram da ordem {ordem}"

    @pytest.mark.parametrize("gesto", sorted(LISTAS))
    def test_uma_lista_por_controle_com_as_opcoes_do_produto(self, gesto: str) -> None:
        """Régua: a lista da tela é o vocabulário do produto, na ordem dele.

        «Do estilo» abre e «Sem efeito» vem logo depois (a escolha de 15/10/2026).
        """
        escolhas, rotulos, _dicas = LISTAS[gesto]
        for html in ("".join(aba05._coluna(c) for c in aba05.MESA),
                     MOCKUP.read_text(encoding="utf-8")):
            listas = re.findall(
                r'<select class="vib-efeito" data-gesto="' + gesto + r'"[^>]*>(.*?)</select>',
                html, flags=re.S)
            assert len(listas) == len(aba05.MESA) == 4
            for opcoes in listas:
                lidas = re.findall(r'<option value="([^"]+)"[^>]*>([^<]+)</option>', opcoes)
                assert [v for v, _r in lidas] == list(escolhas)
                assert [r for _v, r in lidas] == [rotulos[c] for c in escolhas]
                assert lidas[:2] == [("do_estilo", "Do estilo"), ("sem_efeito", "Sem efeito")]

    @pytest.mark.parametrize("gesto", sorted(LISTAS))
    def test_cada_opcao_tem_uma_frase_de_uma_linha(self, gesto: str) -> None:
        """Até 36 letras, para caber na coluna sem quebrar nem cortar."""
        escolhas, _rotulos, dicas = LISTAS[gesto]
        assert set(dicas) == set(escolhas)
        for chave in escolhas:
            assert 0 < len(dicas[chave]) <= 36, (chave, dicas[chave])

    def test_o_lugar_vazio_esconde_a_lista_e_a_frase(self) -> None:
        """Nada de clicável num lugar sem controle."""
        folha = aba05.CSS
        assert '.vib .ctrl[data-conectado="nao"] .efeito-lista > *' in folha

    def test_o_gesto_e_o_campo_tem_nomes_distintos(self) -> None:
        """O pintor acha o valor por `data-campo`; o clique, por `data-gesto`."""
        campos = {a05.CAMPO_DO_EFEITO_HAPTICO, a05.CAMPO_DO_EFEITO_IMERSAO,
                  a05.CAMPO_DA_DICA_DO_HAPTICO, a05.CAMPO_DA_DICA_DA_IMERSAO}
        assert campos.isdisjoint({a05.GESTO_DO_EFEITO_HAPTICO, a05.GESTO_DO_EFEITO_IMERSAO})
        assert len(campos) == 4


class TestAPintura:
    def test_sem_escolha_vale_do_estilo_e_nunca_sem_efeito(self) -> None:
        coluna = next(iter(a05.pacote(_ctx()).get("colunas", {}).values()))
        assert coluna["haptico-escolha"] == "do_estilo"
        assert coluna["imersao-escolha"] == "do_estilo"
        assert coluna["haptico-dica"] == formas.DICAS["do_estilo"]
        assert coluna["imersao-dica"] == padroes.DICAS["do_estilo"]

    def test_a_escolha_do_perfil_chega_a_lista_do_controle(self, perfis: Path) -> None:
        save_profile(Profile(
            name="Bancada", match=MatchAny(),
            controllers={BRANCO: ControllerOverrides(rumble=ControllerRumbleOverride(
                efeito_haptico="guarda", efeito_imersao="pancada_do_lado"))}))
        coluna = next(iter(a05.pacote(_ctx("Bancada"))["colunas"].values()))
        assert coluna["haptico-escolha"] == "guarda"
        assert coluna["haptico-dica"] == formas.DICAS["guarda"]
        assert coluna["imersao-escolha"] == "pancada_do_lado"
        assert coluna["imersao-dica"] == padroes.DICAS["pancada_do_lado"]

    def test_valor_que_a_lista_nao_conhece_volta_a_do_estilo(self) -> None:
        escolha = a05._escolha_da_lista(
            {BRANCO: {"rumble": {"efeito_haptico": "xpto"}}}, BRANCO, "efeito_haptico",
            formas.ESCOLHAS)
        assert escolha == "do_estilo"
        sem_rumble = a05._escolha_da_lista({BRANCO: {}}, BRANCO, "efeito_imersao", padroes.ESCOLHAS)
        assert sem_rumble == "do_estilo"


class TestOGesto:
    @pytest.mark.parametrize(("campo", "valor"), [
        ("efeito_haptico", "estalo"), ("efeito_haptico", "sem_efeito"),
        ("efeito_imersao", "coice"), ("efeito_imersao", "sem_efeito")])
    def test_escolher_grava_o_campo_no_perfil_da_peca(
            self, perfis: Path, campo: str, valor: str) -> None:
        """Do clique ao disco. MORDIDA: tirar a gravação do gesto reprova aqui."""
        save_profile(Profile(name="Bancada", match=MatchAny()))
        ponte = _PonteQueGrava(_Handlers(ativo="Bancada", primario=BRANCO))
        gesto = pacotes.gesto_da_pagina("05-vibracao.html", GESTOS[campo])
        assert gesto is not None
        gesto(_ctx("Bancada"), {"uniq": UNIQ, "valor": valor}, ponte)
        assert ponte.pedidos == [{campo: valor, "uniq": UNIQ}]
        rumble = _rumble_do_disco()
        assert rumble is not None and getattr(rumble, campo) == valor

    @pytest.mark.parametrize("campo", sorted(GESTOS))
    def test_do_estilo_apaga_a_chave_e_nao_vira_sem_efeito(
            self, perfis: Path, campo: str) -> None:
        """MORDIDA: gravar o texto `do_estilo` em vez de apagar a chave reprova.

        Prova da D-1610-DO-ESTILO-APAGA-A-CHAVE-E-SEM-EFEITO-CALA.
        """
        save_profile(Profile(
            name="Bancada", match=MatchAny(),
            controllers={BRANCO: ControllerOverrides(rumble=ControllerRumbleOverride(
                **{campo: "sem_efeito"}, motor_forte_pct=50))}))
        ponte = _PonteQueGrava(_Handlers(ativo="Bancada", primario=BRANCO))
        gesto = pacotes.gesto_da_pagina("05-vibracao.html", GESTOS[campo])
        assert gesto is not None
        gesto(_ctx("Bancada"), {"uniq": UNIQ, "valor": "do_estilo"}, ponte)
        rumble = _rumble_do_disco()
        assert rumble is not None, "apagar a escolha levou a barra junto"
        assert campo not in rumble.model_fields_set and rumble.motor_forte_pct == 50

    def test_uma_lista_nao_mexe_na_outra_nem_nas_barras(self, perfis: Path) -> None:
        save_profile(Profile(
            name="Bancada", match=MatchAny(),
            controllers={BRANCO: ControllerOverrides(rumble=ControllerRumbleOverride(
                efeito_haptico="aparo", haptica_pct=150))}))
        ponte = _PonteQueGrava(_Handlers(ativo="Bancada", primario=BRANCO))
        gesto = pacotes.gesto_da_pagina("05-vibracao.html", "efeito-imersao")
        assert gesto is not None
        gesto(_ctx("Bancada"), {"uniq": UNIQ, "valor": "onda"}, ponte)
        rumble = _rumble_do_disco()
        assert rumble is not None
        assert (rumble.efeito_haptico, rumble.efeito_imersao, rumble.haptica_pct) == (
            "aparo", "onda", 150)

    @pytest.mark.parametrize("campo", sorted(GESTOS))
    def test_valor_fora_da_lista_e_recusado_sem_pedir_ao_daemon(
            self, perfis: Path, campo: str) -> None:
        """MORDIDA: arrancar a checagem do gesto manda o lixo ao daemon, que ainda recusa."""
        save_profile(Profile(name="Bancada", match=MatchAny()))
        ponte = _PonteQueGrava(_Handlers(ativo="Bancada", primario=BRANCO))
        gesto = pacotes.gesto_da_pagina("05-vibracao.html", GESTOS[campo])
        assert gesto is not None
        with pytest.raises(RuntimeError, match="Escolha uma das opções"):
            gesto(_ctx("Bancada"), {"uniq": UNIQ, "valor": "estrondo"}, ponte)
        assert ponte.pedidos == []
        assert _rumble_do_disco() is None

    @pytest.mark.parametrize("campo", sorted(GESTOS))
    def test_o_daemon_recusa_a_chave_que_nao_existe_listando_as_que_existem(
            self, perfis: Path, campo: str) -> None:
        """A borda do daemon vale por si, para quem chega sem passar pela tela."""
        save_profile(Profile(name="Bancada", match=MatchAny()))
        h = _Handlers(ativo="Bancada", primario=BRANCO)
        with pytest.raises(ValueError, match=campo):
            asyncio.run(h._handle_rumble_motores_set({"uniq": BRANCO, campo: "estrondo"}))
        assert _rumble_do_disco() is None

    def test_sem_controle_no_clique_recusa_dizendo(self) -> None:
        gesto = pacotes.gesto_da_pagina("05-vibracao.html", "efeito-haptico")
        assert gesto is not None
        with pytest.raises(RuntimeError, match="coluna do controle"):
            gesto(_ctx(), {"valor": "toque"}, _PonteQueGrava(_Handlers(ativo=None, primario=None)))

    def test_a_recusa_do_daemon_chega_dizendo(self) -> None:
        class _P:
            def rumble_motores_set(self, **k: Any) -> tuple[bool, dict[str, str]]:
                return True, {"status": "sem_perfil", "motivo": "Ative um perfil e repita"}

        gesto = pacotes.gesto_da_pagina("05-vibracao.html", "efeito-imersao")
        assert gesto is not None
        with pytest.raises(RuntimeError, match="Ative um perfil"):
            gesto(_ctx(), {"uniq": UNIQ, "valor": "onda"}, _P())

    def test_os_dois_gestos_estao_classificados_para_cabo_e_radio(self) -> None:
        """A camada e a régua do cabo/BT conhecem os gestos novos."""
        from hefesto_dualsense4unix.interface.pacotes.camada import CAMADA

        for gesto in GESTOS.values():
            assert ("05-vibracao.html", gesto) in CAMADA


class TestOTestar:
    @pytest.fixture(autouse=True)
    def _sem_espera(self, monkeypatch: pytest.MonkeyPatch) -> Any:
        monkeypatch.setattr(a05, "_segurar", lambda _s: None)
        a05.parar_o_teste()
        yield
        a05.parar_o_teste()

    def test_com_um_padrao_escolhido_o_testar_toca_o_padrao(self, perfis: Path) -> None:
        """MORDIDA: tirar o desvio do `testar` volta ao sustentado e reprova.

        O padrão vem do perfil no disco (o `efeito_imersao` do controle), sem dublê no
        `_padrao_escolhido`: a repetição e o «Parar» têm a régua deles em
        `test_o_testar_do_efeito_imersao_repete_ate_o_parar`.

        Prova da D-1610-O-TESTAR-TOCA-O-PADRAO-ESCOLHIDO.
        """
        save_profile(Profile(
            name="Bancada", match=MatchAny(),
            controllers={BRANCO: ControllerOverrides(rumble=ControllerRumbleOverride(
                efeito_imersao="onda"))}))
        ponte = _PonteQueGrava(_Handlers(ativo="Bancada", primario=BRANCO))
        gesto = pacotes.gesto_da_pagina("05-vibracao.html", "testar")
        parar = pacotes.gesto_da_pagina("05-vibracao.html", "parar")
        assert gesto is not None and parar is not None
        onda = padroes.PADROES["onda"]
        gesto(_ctx("Bancada"), {"uniq": UNIQ}, ponte)

        def sets() -> list[tuple[Any, ...]]:
            return [c[1] for c in list(ponte.chamadas) if c[0] == "rumble_set_checked"]

        prazo = time.monotonic() + 5.0
        while len(sets()) < len(onda) and time.monotonic() < prazo:
            time.sleep(0.05)
        assert sets()[:len(onda)] == [(d, e) for _ms, e, d in onda], (
            f"o Testar não tocou a Onda do perfil: {sets()}")
        assert UNIQ in a05.em_teste(), "o padrão fica no ar até o «Parar»"
        parar(_ctx("Bancada"), {"uniq": UNIQ}, ponte)
        assert UNIQ not in a05.em_teste()

    @pytest.mark.parametrize("escolha", ["do_estilo", "sem_efeito", None])
    def test_sem_padrao_escolhido_o_testar_segue_sustentado(
            self, perfis: Path, escolha: str | None) -> None:
        rumble = ControllerRumbleOverride(efeito_imersao=escolha) if escolha else None
        save_profile(Profile(
            name="Bancada", match=MatchAny(),
            controllers={BRANCO: ControllerOverrides(rumble=rumble)} if rumble else None))
        ponte = _PonteQueGrava(_Handlers(ativo="Bancada", primario=BRANCO))
        gesto = pacotes.gesto_da_pagina("05-vibracao.html", "testar")
        assert gesto is not None
        gesto(_ctx("Bancada"), {"uniq": UNIQ}, ponte)
        sets = [c for c in ponte.chamadas if c[0] == "rumble_set_checked"]
        assert len(sets) == 1, "o sustentado é UM pedido, que fica até o Parar"
        assert UNIQ in a05.em_teste()

    def test_a_area_de_criar_lista_as_formas_do_produto(self) -> None:
        """A recusa do «Sentir» sem forma diz as formas de criar (`FORMAS_DE_CRIAR`)."""
        gesto = pacotes.gesto_da_pagina("05-vibracao.html", "criar-efeito")
        assert gesto is not None
        with pytest.raises(RuntimeError) as erro:
            pedido = {"forma": {"padrao": "", "motores": "ambos"},  # (noqa-acento)
                      "nome": "x"}
            gesto(_ctx(), pedido, _PonteQueGrava(_Handlers(ativo=None, primario=None)))
        for chave in padroes.FORMAS_DE_CRIAR:
            assert padroes.ROTULOS[chave].lower() in str(erro.value)
