"""SOM-NA-TELA-01 (A3) — a `fonte` de cada controle ganhou gesto e leitura."""

from __future__ import annotations

import pathlib
import sys
from typing import Any

import pytest

RAIZ = pathlib.Path(__file__).resolve().parents[2]
sys.path.insert(0, str(RAIZ / "src/hefesto_dualsense4unix/interface"))

P1 = "aa:bb:cc:00:00:01"
P2 = "aa:bb:cc:00:00:02"
CHAVE_P1 = P1.replace(":", "").lower()
CHAVE_P2 = P2.replace(":", "").lower()
NOME = "Regua-Da-Fonte"


class Ponte:
    """O daemon de papel que confirma tudo — o mesmo dublê das réguas vizinhas."""

    def __init__(self) -> None:
        self.chamadas: list[tuple[str, dict[str, Any]]] = []

    def __getattr__(self, nome: str) -> Any:
        def registrar(*a: Any, **k: Any) -> Any:
            self.chamadas.append((nome, dict(k)))
            if nome.endswith("_detalhado"):
                return {"status": "ok", "por_uniq": True}
            return True

        return registrar

    @property
    def nomes(self) -> list[str]:
        return [c[0] for c in self.chamadas]


@pytest.fixture
def casa(tmp_path: pathlib.Path, monkeypatch: pytest.MonkeyPatch) -> pathlib.Path:
    monkeypatch.setenv("XDG_CONFIG_HOME", str(tmp_path))
    from hefesto_dualsense4unix.profiles import loader
    from hefesto_dualsense4unix.profiles.schema import MatchManual, Profile
    from hefesto_dualsense4unix.utils.xdg_paths import profiles_dir

    profiles_dir().mkdir(parents=True, exist_ok=True)
    loader.save_profile(Profile(name=NOME, match=MatchManual()), origem="regua")
    return profiles_dir()


@pytest.fixture(autouse=True)
def _o_cache_da_camada_1_comeca_vazio() -> Any:
    """Esta régua mede o MÓDULO, então ela garante o estado do módulo."""
    from pacotes import a02_controles as a02

    antes = dict(a02._CAMADA_1)
    a02._CAMADA_1.clear()
    quando, em_voo = a02._CAMADA_1_QUANDO[0], a02._CAMADA_1_EM_VOO[0]
    a02._CAMADA_1_QUANDO[0] = 0.0
    a02._CAMADA_1_EM_VOO[0] = False
    yield
    a02._CAMADA_1.clear()
    a02._CAMADA_1.update(antes)
    a02._CAMADA_1_QUANDO[0] = quando
    a02._CAMADA_1_EM_VOO[0] = em_voo


@pytest.fixture
def fileira_de_tres(monkeypatch: pytest.MonkeyPatch) -> None:
    """A página publicada COM o terceiro botão — o mundo depois do `--publicar`."""
    from pacotes import a02_controles as a02

    monkeypatch.setattr(a02, "A_FILEIRA_TEM_TRES", True)


def _dele(uniq: str, fonte: str | None = None) -> dict[str, Any]:
    speaker: dict[str, Any] = {"volume": 100, "muted": False, "rota": 2}
    if fonte is not None:
        speaker["fonte"] = fonte
    return {"uniq": uniq, "transport": "usb", "connected": True, "inputs": {},
            "audio": {"mic_mudo": False}, "speaker": speaker}


def _ctx(*entradas: dict[str, Any]) -> Any:
    import pacotes

    return pacotes.Contexto(state={"active_profile": NOME}, mesa=[],
                            conectados=list(entradas) or [_dele(P1)], estados={})


def _gesto(nome: str) -> Any:
    import pacotes
    import pacotes.a02_controles

    fn = pacotes.gesto_da_pagina("02-controles.html", nome)
    assert fn is not None, f"02-controles.html:{nome} não tem dono"
    return fn


def _do_controle(chave: str) -> dict[str, Any]:
    """O bloco que VALE daquele controle: o do perfil por cima do do computador."""
    from hefesto_dualsense4unix.profiles.o_padrao_do_computador import (
        carregar_o_que_vale,
    )

    try:
        vista = carregar_o_que_vale(NOME)
    except FileNotFoundError:
        return {}
    bloco = (vista.controllers or {}).get(chave)
    return bloco.model_dump(mode="json", exclude_unset=True) if bloco is not None else {}


class TestOQueODaemonPublica:
    def test_o_gancho_responde_e_o_padrao_e_nao_sei(self) -> None:
        """MORDIDA: faça `fonte_publicada` devolver `FONTE_PADRAO` sem dizedor."""
        from hefesto_dualsense4unix.integrations import alto_falante_bt as af

        anterior = af.registrar_dizedor_da_fonte(None)
        try:
            assert af.fonte_publicada(P1) == ""
            af.registrar_dizedor_da_fonte(lambda u: "mix" if u == P1 else "sfx")
            assert af.fonte_publicada(P1) == "mix"
            assert af.fonte_publicada(P2) == "sfx"
        finally:
            af.registrar_dizedor_da_fonte(anterior)

    def test_valor_estranho_vale_como_nao_sei(self) -> None:
        """MORDIDA: devolva o que o dizedor disser, sem conferir."""
        from hefesto_dualsense4unix.integrations import alto_falante_bt as af

        anterior = af.registrar_dizedor_da_fonte(lambda _u: "MIX")
        try:
            assert af.fonte_publicada(P1) == ""
        finally:
            af.registrar_dizedor_da_fonte(anterior)

    def test_um_dizedor_que_explode_nao_derruba_o_estado(self) -> None:
        """MORDIDA: tire o `try`. Quem chama é o `state_full`, a cada tique."""
        from hefesto_dualsense4unix.integrations import alto_falante_bt as af

        def _explode(_u: str) -> str:
            raise RuntimeError("perfil ilegível")

        anterior = af.registrar_dizedor_da_fonte(_explode)
        try:
            assert af.fonte_publicada(P1) == ""
        finally:
            af.registrar_dizedor_da_fonte(anterior)


class TestOQueATelaLe:
    def test_a_fonte_sai_do_estado_e_nao_do_disco(self) -> None:
        """MORDIDA: faça `fonte_do_controle` abrir o perfil ativo."""
        from pacotes import a02_controles as a02

        assert a02.fonte_do_controle(_dele(P1, "mix")) == "mix"
        assert a02.fonte_do_controle(_dele(P1, "sfx")) == "sfx"
        assert a02.fonte_do_controle(_dele(P1)) == ""

    def test_todo_o_som_do_pc_vence_o_mix(
        self, fileira_de_tres: None, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        """MORDIDA: perguntar pelo `mix` ANTES de olhar a camada 1."""
        from pacotes import a02_controles as a02

        monkeypatch.setattr(a02, "aceso_da_rota", lambda _u, _e: "pc")
        assert a02.aceso_da_fileira(P1, _dele(P1, "mix")) == "pc"

    def test_com_mix_acende_o_botao_do_meio(self, fileira_de_tres: None) -> None:
        """MORDIDA: devolva sempre `aceso_da_rota`, ignorando a fonte."""
        from pacotes import a02_controles as a02

        assert a02.aceso_da_fileira(P1, _dele(P1, "mix")) == "junto"
        assert a02.aceso_da_fileira(P1, _dele(P1, "sfx")) == "jogo"

    def test_a_pagina_de_dois_botoes_nunca_ouve_junto(
        self, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        """MORDIDA: tire o `A_FILEIRA_TEM_TRES` de `aceso_da_fileira`."""
        from pacotes import a02_controles as a02

        monkeypatch.setattr(a02, "A_FILEIRA_TEM_TRES", False)
        assert a02.aceso_da_fileira(P1, _dele(P1, "mix")) == "jogo"


class TestOGesto:
    def test_ouvir_junto_grava_mix_no_perfil_daquele_controle(
        self, casa: pathlib.Path
    ) -> None:
        """MORDIDA: apague o `_lembrar_do_som(..., speaker={"fonte": "mix"})`.

        Sem ele o botão acende, o som não muda e a escolha some no recarregar
        — os dezesseis botões que ela nomeou em 02/09.
        """
        p = Ponte()
        _gesto("rota")(_ctx(_dele(P1), _dele(P2)), {"uniq": P1, "rota": "junto"}, p)

        assert (_do_controle(CHAVE_P1).get("speaker") or {}).get("fonte") == "mix"
        assert (_do_controle(CHAVE_P2).get("speaker") or {}).get("fonte") is None, (
            "a escolha de um controle chegou ao perfil do vizinho")

    def test_ouvir_junto_devolve_a_saida_padrao(
        self, casa: pathlib.Path, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        """MORDIDA: apague o `devolver_o_som_do_pc()` do ramo do «junto»."""
        from hefesto_dualsense4unix.app import audio_saida
        from pacotes import a02_controles as a02

        devolveu: list[bool] = []
        monkeypatch.setattr(
            a02.audio_saida, "devolver_o_som_do_pc",
            lambda **_k: devolveu.append(True) or audio_saida.DesfechoDaRota(True))

        _gesto("rota")(_ctx(), {"uniq": P1, "rota": "junto"}, Ponte())
        assert devolveu, "o «Ouvir junto» não devolveu a saída padrão do sistema"

    def test_sair_do_junto_apaga_o_mix(self, casa: pathlib.Path) -> None:
        """MORDIDA: apague o ramo que grava `fonte: sfx` ao sair do «junto»."""
        p = Ponte()
        _gesto("rota")(_ctx(), {"uniq": P1, "rota": "junto"}, p)
        assert (_do_controle(CHAVE_P1).get("speaker") or {}).get("fonte") == "mix"

        _gesto("rota")(_ctx(_dele(P1, "mix")), {"uniq": P1, "rota": "jogo"}, p)
        assert (_do_controle(CHAVE_P1).get("speaker") or {}).get("fonte") == "sfx"

    def test_o_junto_nao_manda_byte_de_rota_ao_daemon(
        self, casa: pathlib.Path
    ) -> None:
        """MORDIDA: deixe o «junto» cair no `speaker_set(rota=…)` dos outros dois."""
        p = Ponte()
        _gesto("rota")(_ctx(), {"uniq": P1, "rota": "junto"}, p)
        com_rota = [c for c in p.chamadas if c[0] == "speaker_set" and "rota" in c[1]]
        assert not com_rota, (
            f"o «Ouvir junto» mexeu no firmware: {com_rota}")

    def test_uma_rota_que_a_pagina_nao_manda_e_recusada(
        self, casa: pathlib.Path
    ) -> None:
        """MORDIDA: aceite qualquer string em `rota`."""
        with pytest.raises(ValueError, match="não conheço a rota"):
            _gesto("rota")(_ctx(), {"uniq": P1, "rota": "tudo"}, Ponte())
