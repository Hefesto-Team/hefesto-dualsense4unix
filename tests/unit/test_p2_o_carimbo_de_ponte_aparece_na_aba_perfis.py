"""P2 — o daemon publica o carimbo de ponte, e a janela não tinha UM leitor.

PERFIS-ABRE-O-QUE-GUARDA-01/§2.2/1 (24/08/2026). O `daemon.status` publica
`pontes_confirmadas` desde 19/08 (`daemon/ipc_handlers.py:1971`), e o
comentário ao lado diz a intenção em letra: *"para a janela dizer 'este jogo já
sabe por onde entra'"*. Medido:

    $ grep -rn "pontes_confirmadas" src/hefesto_dualsense4unix/app/
    app/draft_config.py:445:              # `manager.pontes_confirmadas()` …
    app/actions/profiles_actions.py:3771: # carimbo viaja junto …

Dois hits, os dois em COMENTÁRIO. **Zero leitores.** A aba PRESERVA o carimbo
no Salvar e nunca o mostrou — a cura escrita, o dado publicado, e a tela muda.
É a decisão dela de 19/08 (*"o produto CONSTRÓI a ponte, não só preserva"*)
parada na última perna.

**O dado é REAL, não fixture inventada.** Dois perfis dela têm carimbo hoje:
`big_walk.json` (19/08) e `duskfade.json` (22/08). O `PONTE_DO_BIG_WALK` deste
arquivo é o bloco `ponte` do primeiro, copiado byte a byte.

**Silêncio é parte da cura, não ausência dela.** Sem carimbo a linha não diz
nada — nunca "ponte desconhecida". `pontes_confirmadas` só publica os appids
COM carimbo justamente porque a ausência da chave já significa "não sei", e
escrever isso na tela transformaria falta de informação em aviso.

**MEDIDO E ABERTO** (§"o que sobrou"): `pontes_confirmadas` existe no
`daemon.status` e **não** no `daemon.state_full`, que é o payload do tique da
janela. Por isso a aba busca por GESTO. Publicá-lo também no `state_full` é o
conserto de fundo, e mora no `daemon/`.
"""
from __future__ import annotations

from typing import Any

import pytest

from hefesto_dualsense4unix.app.actions import profiles_actions as pa
from hefesto_dualsense4unix.integrations.jogos_locais import MSG_FORA_DA_MAQUINA

#: O bloco `ponte` de `big_walk.json`, do disco DELA, copiado byte a byte.
PONTE_DO_BIG_WALK: dict[str, Any] = {
    "kind": "gamepad",
    "gamepad_flavor": "dualsense",
    "steam_input": False,
    "confirmada_em": "2026-08-19T21:16:55-03:00",
    "confirmada_por": "silencio",
}
APPID_DO_BIG_WALK = "1599660"

PONTES: dict[str, Any] = {APPID_DO_BIG_WALK: PONTE_DO_BIG_WALK}


class TestAFraseDoCarimbo:
    def test_o_carimbo_real_dela_vira_uma_linha_com_data(self) -> None:
        """MORDE o leitor: sem ele, `None`, e a linha nunca aparece."""
        frase = pa.frase_da_ponte_confirmada(PONTES, APPID_DO_BIG_WALK)
        assert frase is not None
        assert "já sabe por onde entra" in frase
        assert "19/08/2026" in frase, "o QUANDO é metade do que o carimbo diz"

    def test_a_linha_fala_o_vocabulario_da_aba_inicio(self) -> None:
        """Um segundo vocabulário para o mesmo fato é como nascem os pares da F5.

        `kind` e `gamepad_flavor` viram os MESMOS rótulos de `_MODE_KIND_ITEMS`
        e `_MODE_FLAVOR_ITEMS`, que a aba Início já usa (UX-MODE-TERMS-01/02).
        Se alguém escrever "modo gamepad" aqui, este teste reprova.
        """
        frase = pa.frase_da_ponte_confirmada(PONTES, APPID_DO_BIG_WALK)
        assert frase is not None
        assert dict(pa._MODE_KIND_ITEMS)["gamepad"] in frase
        assert dict(pa._MODE_FLAVOR_ITEMS)["dualsense"] in frase

    def test_o_como_do_carimbo_chega_na_frase(self) -> None:
        """`confirmada_por: silencio` não pode virar jargão na tela."""
        frase = pa.frase_da_ponte_confirmada(PONTES, APPID_DO_BIG_WALK)
        assert frase is not None
        assert "silencio" not in frase and "silêncio" not in frase
        assert "funcionou" in frase

    def test_a_conexao_nativa_e_o_steam_input_aparecem(self) -> None:
        pontes = {
            "3357650": {
                "kind": "native",
                "gamepad_flavor": None,
                "steam_input": True,
                "confirmada_em": "2026-08-22T10:00:00-03:00",
                "confirmada_por": "escolha_dela",
            }
        }
        frase = pa.frase_da_ponte_confirmada(pontes, "3357650")
        assert frase is not None
        assert "Conexão Nativa (Sony)" in frase
        assert "Steam Input" in frase
        assert "22/08/2026" in frase

    def test_o_campo_aceita_o_appid_do_jeito_que_a_tela_o_tem(self) -> None:
        """O campo do editor guarda dígitos; o `wm_class` guarda `steam_app_<id>`.

        Quem responde "que appid é este texto?" tem um dono só
        (`normalize_appid`, da UNIFICA-PREDICADO-01) — e não pode nascer um
        segundo regex aqui.
        """
        for entrada in (APPID_DO_BIG_WALK, f"steam_app_{APPID_DO_BIG_WALK}"):
            assert pa.frase_da_ponte_confirmada(PONTES, entrada) is not None


class TestOSilencioEParteDaCura:
    def test_jogo_sem_carimbo_nao_diz_nada(self) -> None:
        """MORDE o silêncio: "ponte desconhecida" seria o alarme falso do P1."""
        assert pa.frase_da_ponte_confirmada(PONTES, "999999") is None

    def test_pontes_vazias_nao_dizem_nada(self) -> None:
        assert pa.frase_da_ponte_confirmada({}, APPID_DO_BIG_WALK) is None

    def test_daemon_calado_nao_diz_nada(self) -> None:
        """Sem resposta do daemon o cache é `None` — e `None` é silêncio."""
        assert pa.frase_da_ponte_confirmada(None, APPID_DO_BIG_WALK) is None

    def test_campo_vazio_nao_diz_nada(self) -> None:
        assert pa.frase_da_ponte_confirmada(PONTES, "") is None
        assert pa.frase_da_ponte_confirmada(PONTES, None) is None

    def test_kind_que_esta_versao_nao_conhece_cala(self) -> None:
        """Calar é melhor que inventar rótulo — o carimbo segue no disco."""
        pontes = {"1": {"kind": "teletransporte", "confirmada_em": "2026-08-19"}}
        assert pa.frase_da_ponte_confirmada(pontes, "1") is None

    def test_carimbo_com_data_ilegivel_ainda_diz_por_onde(self) -> None:
        """Perder a data não pode custar o fato — degrada, não some."""
        pontes = {"1": {"kind": "desktop", "confirmada_em": "ontem"}}
        frase = pa.frase_da_ponte_confirmada(pontes, "1")
        assert frase is not None
        assert "Confirmado em" not in frase


# ---------------------------------------------------------------------------
# A costura: a linha chega ao rótulo que já existe ao lado do campo do jogo
# ---------------------------------------------------------------------------


class _Rotulo:
    def __init__(self) -> None:
        self.markup = ""
        self.texto = ""
        self.visivel = False
        self.tooltip = ""

    def set_markup(self, m: str) -> None:
        self.markup = m

    def set_text(self, t: str) -> None:
        self.texto = t
        self.markup = t

    def set_visible(self, v: bool) -> None:
        self.visivel = v

    def set_tooltip_text(self, t: str) -> None:
        self.tooltip = t


class _Entry:
    def __init__(self, texto: str) -> None:
        self._t = texto

    def get_text(self) -> str:
        return self._t

    def set_text(self, t: str) -> None:
        self._t = t


class _Aba(pa.ProfilesActionsMixin):  # type: ignore[misc]
    def __init__(self, appid: str, escolha: str = "steam_game") -> None:
        self._escolha = escolha
        self._nomes_dos_jogos: dict[str, str] = {}
        self._widgets: dict[str, Any] = {
            "profile_jogo_reconhecido": _Rotulo(),
            "profile_simple_custom_name": _Entry(appid),
        }

    def _get(self, wid: str) -> Any:
        return self._widgets.get(wid)

    def _selected_simple_choice(self) -> str:
        return self._escolha


class TestALinhaChegaNaTela:
    def test_com_carimbo_a_linha_aparece_no_rotulo_do_jogo(self) -> None:
        """MORDE a costura: a função pura certa e o rótulo mudo não curam nada."""
        aba = _Aba(APPID_DO_BIG_WALK)
        aba._pontes_confirmadas = PONTES

        aba._atualizar_frase_do_jogo()

        rotulo = aba._get("profile_jogo_reconhecido")
        assert rotulo.visivel is True
        assert "já sabe por onde entra" in rotulo.markup
        assert "19/08/2026" in rotulo.markup

    def test_sem_carimbo_o_rotulo_diz_so_o_que_ja_dizia(self) -> None:
        """Nenhum texto NOVO na tela — o silêncio tem de chegar inteiro.

        Este rótulo **já falava** antes do P2: com um appid que não está na
        biblioteca desta bancada ele diz `MSG_FORA_DA_MAQUINA`. A prova do
        silêncio, então, não é "invisível" — é **idêntico ao de ontem**: uma
        linha só, e nenhuma palavra sobre ponte. Exigir invisibilidade aqui
        seria o teste medindo o comportamento errado.
        """
        aba = _Aba(APPID_DO_BIG_WALK)
        aba._pontes_confirmadas = {}

        aba._atualizar_frase_do_jogo()

        rotulo = aba._get("profile_jogo_reconhecido")
        assert "já sabe por onde entra" not in rotulo.markup
        assert "\n" not in rotulo.markup, "a segunda linha nasceu sem carimbo"
        assert MSG_FORA_DA_MAQUINA in rotulo.markup

    def test_campo_vazio_e_sem_carimbo_esconde_o_rotulo(self) -> None:
        """E quando não havia o que dizer, continua não havendo."""
        aba = _Aba("")
        aba._pontes_confirmadas = {}

        aba._atualizar_frase_do_jogo()

        assert aba._get("profile_jogo_reconhecido").visivel is False

    def test_fora_do_jogo_da_steam_nao_ha_carimbo_nenhum(self) -> None:
        """O carimbo é por appid: sem appid não há de qual jogo falar."""
        aba = _Aba(APPID_DO_BIG_WALK, escolha="any")
        aba._pontes_confirmadas = PONTES

        aba._atualizar_frase_do_jogo()

        assert aba._get("profile_jogo_reconhecido").visivel is False


class TestABuscaDoCarimbo:
    def test_a_aba_pede_o_carimbo_ao_daemon_status_e_nao_ao_tique(
        self, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        """MEDIDO em 25/08: `pontes_confirmadas` NÃO existe no `state_full`.

        Ele é publicado por `_handle_daemon_status` e só por ele
        (`daemon/ipc_handlers.py:1971`). Uma leitura do `state_full` — o
        payload do tique — devolveria `None` para sempre, e a linha nunca
        apareceria. Se alguém trocar o método aqui, este teste reprova.
        """
        pedidos: list[str] = []
        monkeypatch.setattr(
            pa,
            "call_async",
            lambda method, params=None, on_success=None, on_failure=None,
            **_kw: pedidos.append(method),
        )
        aba = _Aba(APPID_DO_BIG_WALK)
        aba._buscar_as_pontes_confirmadas()
        assert pedidos == ["daemon.status"]

    def test_a_resposta_do_daemon_vira_cache_e_repinta(self) -> None:
        aba = _Aba(APPID_DO_BIG_WALK)
        assert aba._ao_chegar_o_carimbo_das_pontes(
            {"pontes_confirmadas": PONTES}
        ) is False
        assert aba._pontes_confirmadas == PONTES
        assert "já sabe por onde entra" in aba._get("profile_jogo_reconhecido").markup

    def test_resposta_estranha_nao_apaga_o_que_ja_se_sabia(self) -> None:
        """Um payload inválido é ausência de resposta, nunca "não há carimbo"."""
        aba = _Aba(APPID_DO_BIG_WALK)
        aba._pontes_confirmadas = PONTES
        aba._ao_chegar_o_carimbo_das_pontes(None)
        assert aba._pontes_confirmadas == PONTES

    def test_daemon_sem_a_chave_zera_o_cache_sem_estourar(self) -> None:
        aba = _Aba(APPID_DO_BIG_WALK)
        aba._pontes_confirmadas = PONTES
        aba._ao_chegar_o_carimbo_das_pontes({"connected": True})
        assert aba._pontes_confirmadas == {}
