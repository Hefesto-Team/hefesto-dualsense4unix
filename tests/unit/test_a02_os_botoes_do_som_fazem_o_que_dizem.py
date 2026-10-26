"""SOM-BOTOES-01 — os botões do som fazem o que dizem? Medido, em 11/09/2026."""

from __future__ import annotations

import pathlib
import sys
from typing import Any

import pytest

RAIZ = pathlib.Path(__file__).resolve().parents[2]
sys.path.insert(0, str(RAIZ / "src/hefesto_dualsense4unix/interface"))

P1 = "aa:bb:cc:00:00:01"
P2 = "aa:bb:cc:00:00:02"
CHAVE_P1 = P1.replace(":", "")
CHAVE_P2 = P2.replace(":", "")
NOME = "Regua-Dos-Botoes-Do-Som"

class Ponte:
    """O daemon de papel. `recusa` faz `speaker_set` dizer não, uma vez."""

    def __init__(self, recusa: bool = False) -> None:
        self.chamadas: list[tuple[str, dict[str, Any]]] = []
        self.recusa = recusa

    def __getattr__(self, nome: str) -> Any:
        def registrar(*a: Any, **k: Any) -> Any:
            self.chamadas.append((nome, dict(k)))
            if nome == "speaker_set" and self.recusa:
                return False
            if nome.endswith("_detalhado"):
                return {"status": "ok", "por_uniq": True}
            return True

        return registrar

    @property
    def nomes(self) -> list[str]:
        return [c[0] for c in self.chamadas]

    def so(self, nome: str) -> list[dict[str, Any]]:
        return [p for n, p in self.chamadas if n == nome]

    def com_byte_de_rota(self) -> list[dict[str, Any]]:
        """Os `speaker.set` que escrevem no FIRMWARE, e só eles."""
        return [p for p in self.so("speaker_set") if "rota" in p]

    def com_fonte(self) -> list[dict[str, Any]]:
        """Os `speaker.set` que escolhem a CAMADA 1, e só eles."""
        return [p for p in self.so("speaker_set") if "fonte" in p]


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
def casa(tmp_path: pathlib.Path, monkeypatch: pytest.MonkeyPatch) -> pathlib.Path:
    """Um lar de mentira com um perfil ativo. Nada dela é tocado."""
    monkeypatch.setenv("XDG_CONFIG_HOME", str(tmp_path))
    from hefesto_dualsense4unix.profiles import loader
    from hefesto_dualsense4unix.profiles.schema import MatchManual, Profile
    from hefesto_dualsense4unix.utils.xdg_paths import profiles_dir

    profiles_dir().mkdir(parents=True, exist_ok=True)
    loader.save_profile(Profile(name=NOME, match=MatchManual()), origem="regua")
    return profiles_dir()


@pytest.fixture
def sem_maquina_dela(monkeypatch: pytest.MonkeyPatch) -> dict[str, list[Any]]:
    """A camada 1 e o tocador viram dublê. NADA sai desta régua para o PipeWire."""
    from hefesto_dualsense4unix.app import audio_saida
    from pacotes import a02_controles as a02

    visto: dict[str, list[Any]] = {"mandou": [], "devolveu": []}
    monkeypatch.setattr(
        a02.audio_saida, "mandar_o_som_do_pc",
        lambda u, m=(), **k: (visto["mandou"].append(u)
                              or audio_saida.DesfechoDaRota(True, "", "sink-falso")))
    monkeypatch.setattr(
        a02.audio_saida, "devolver_o_som_do_pc",
        lambda **k: (visto["devolveu"].append(True)
                     or audio_saida.DesfechoDaRota(True)))
    monkeypatch.setattr(a02.audio_saida, "tocar_confirmacao",
                        lambda *a, **k: None)
    return visto


def _dele(uniq: str, *, rota: int | None = 2, fonte: str | None = None,
          volume: int = 100) -> dict[str, Any]:
    speaker: dict[str, Any] = {"volume": volume, "muted": False}
    if rota is not None:
        speaker["rota"] = rota
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

def _pagina_publicada() -> str:
    from hefesto_dualsense4unix.interface import onde
    from pacotes import a02_controles as a02

    return onde.pagina(a02.PAGINA, publicado=True).read_text(encoding="utf-8")


class TestOJuntoSaiuDaTela:
    """O «Ouvir junto» saiu da fileira com o desenho do todo (15/10/2026): três botões."""

    def test_o_gesto_recusa_o_junto(
        self, casa: pathlib.Path, sem_maquina_dela: dict[str, list[Any]]
    ) -> None:
        """MORDIDA: devolva `junto` aos botões da fileira e isto reprova."""
        p = Ponte()
        with pytest.raises(ValueError, match="não conheço a rota"):
            _gesto("rota")(_ctx(_dele(P1)), {"uniq": P1, "rota": "junto"}, p)
        assert not p.chamadas, f"o «junto» recusado ainda falou com o daemon: {p.chamadas}"
        assert not _do_controle(CHAVE_P1), "o «junto» recusado gravou no perfil"

    def test_o_perfil_em_mix_acende_o_botao_da_rota(self) -> None:
        """Um perfil com `fonte: mix` e a rota 2 acende «jogo»: o PC segue tocando (23/10/2026)."""
        from pacotes import a02_controles as a02

        assert a02.aceso_da_fileira(P1, _dele(P1, fonte="mix")) == "jogo"
        assert a02.aceso_da_fileira(P1, _dele(P1, fonte="sfx")) == "jogo"


class TestOGestoEntregaAFonte:
    """O que o botão MANDA, e não só o que ele grava — 20/09/2026."""

    def test_sair_do_mix_diz_sfx_ao_daemon(
        self, casa: pathlib.Path, sem_maquina_dela: dict[str, list[Any]]
    ) -> None:
        """Um perfil antigo em `mix` sai dele no primeiro clique.

        MORDIDA: troque o `"sfx"` do ramo de saída por `"mix"`.
        """
        p = Ponte()
        _gesto("rota")(_ctx(_dele(P1, fonte="mix"), _dele(P2)),
                       {"uniq": P1, "rota": "jogo"}, p)

        pedidos = p.com_fonte()
        assert pedidos, (
            f"sair do `mix` não devolveu a camada 1 ao daemon: {p.nomes}")
        assert [q["fonte"] for q in pedidos] == ["sfx"], (
            f"a saída do `mix` mandou outra fonte ao nó: {pedidos}")
        assert all(q.get("uniq") == P1 for q in pedidos), (
            f"a camada 1 de um controle foi parar noutro: {pedidos}")

    def test_quem_ja_estava_em_sfx_nao_reescreve_a_camada_1(
        self, casa: pathlib.Path, sem_maquina_dela: dict[str, list[Any]]
    ) -> None:
        """MORDIDA: tire a guarda `== "mix"` e diga `sfx` em todo clique."""
        p = Ponte()
        _gesto("rota")(_ctx(_dele(P1, fonte="sfx")), {"uniq": P1, "rota": "jogo"}, p)

        assert not p.com_fonte(), (
            f"reescreveu a camada 1 sem ninguém a ter mudado: {p.com_fonte()}")

    def test_a_camada_1_e_a_2_nao_viajam_no_mesmo_pedido(
        self, casa: pathlib.Path, sem_maquina_dela: dict[str, list[Any]]
    ) -> None:
        """Um `speaker.set` leva a `fonte` OU o byte — nunca os dois."""
        from pacotes import a02_controles as a02

        p = Ponte()
        _gesto("rota")(_ctx(_dele(P1, rota=a02.ROTA_DO_CANAL[a02.CANAL_SONS_DO_JOGO],
                                  fonte="mix")),
                       {"uniq": P1, "rota": "pc"}, p)

        assert p.com_fonte() and p.com_byte_de_rota(), (
            "a cena não reproduz o clique que manda as DUAS camadas")
        misturados = [q for q in p.so("speaker_set") if "fonte" in q and "rota" in q]
        assert not misturados, (
            f"a camada 1 e o byte do firmware viajaram no mesmo pedido: "
            f"{misturados}")


class TestATabelaDosBotoes:
    DA_COLUNA_DO_SOM = ("mudo", "volume", "rota")

    def test_todo_gesto_de_som_da_pagina_tem_dono(self) -> None:
        """MORDIDA: apague um `@gesto` da coluna de som."""
        import pacotes
        import pacotes.a02_controles

        doc = _pagina_publicada()
        for nome in self.DA_COLUNA_DO_SOM:
            assert f'data-gesto="{nome}"' in doc, (
                f"a régua fala de um gesto que a página não tem: {nome}")
            assert pacotes.gesto_da_pagina("02-controles.html", nome) is not None, (
                f"a página tem `data-gesto={nome}` e ninguém o atende")

    @pytest.mark.parametrize(
        ("o", "metodo"),  # (noqa-acento)
        [
            ({"mudo": "microfone"}, "mic_canal_set_detalhado"),
            ({"mudo": "alto-falante"}, "speaker_set"),
            ({"volume": "microfone", "valor": "42"}, "mic_volume_set_detalhado"),
            ({"volume": "alto-falante", "valor": "42"}, "speaker_set"),
            ({"rota": "jogo"}, "speaker_set"),
            ({"rota": "pc"}, "speaker_set"),
        ],
    )
    def test_cada_botao_do_som_so_mexe_no_controle_da_coluna(
        self, o: dict[str, Any], metodo: str, casa: pathlib.Path,
        sem_maquina_dela: dict[str, list[Any]],
    ) -> None:
        """Pergunta 3 da sprint, botão a botão: **vale só para aquele controle?**"""
        nome = next(k for k in ("mudo", "volume", "rota") if k in o)
        p = Ponte()
        _gesto(nome)(_ctx(_dele(P1), _dele(P2)), {"uniq": P1, **o}, p)

        pedidos = p.so(metodo)
        assert pedidos, f"{o} não chamou {metodo}: {p.nomes}"
        assert all(q.get("uniq") == P1 for q in pedidos), (
            f"{o} mexeu em outro controle: {pedidos}")
        assert not _do_controle(CHAVE_P2), "o perfil do vizinho foi tocado"
