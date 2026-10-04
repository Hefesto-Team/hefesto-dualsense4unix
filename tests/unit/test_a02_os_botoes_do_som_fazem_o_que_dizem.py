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

MARCA_DO_JUNTO = 'data-hef-quando="junto"'


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


class TestOGuardaDaFileira:
    def test_o_valor_do_import_bate_com_a_pagina_publicada(self) -> None:
        """A constante DE VERDADE, sem monkeypatch, contra o arquivo."""
        from pacotes import a02_controles as a02

        tem = MARCA_DO_JUNTO in _pagina_publicada()
        assert a02.A_FILEIRA_TEM_TRES is tem, (
            f"a página publicada {'TEM' if tem else 'NÃO tem'} o «Ouvir junto» "
            f"e o pacote acha que {a02.A_FILEIRA_TEM_TRES}")

    def test_ele_pergunta_ao_publicado_e_nao_a_bancada(
        self, tmp_path: pathlib.Path, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        """MORDIDA: tire o `publicado=True` da leitura."""
        from hefesto_dualsense4unix.interface import onde
        from pacotes import a02_controles as a02

        mentira = tmp_path / "mockup"
        mentira.mkdir()
        (mentira / a02.PAGINA).write_text(
            "<html><body>fileira de dois</body></html>", encoding="utf-8")
        monkeypatch.setattr(onde, "BANCADA", mentira)

        assert a02._a_pagina_tem_o_ouvir_junto() is (
            MARCA_DO_JUNTO in _pagina_publicada()), (
            "o guarda leu a bancada; quem o produto renderiza é o publicado")

    def test_um_erro_de_programacao_nao_vira_fato_sobre_o_desenho(
        self, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        """MORDIDA: alargue o `except` de volta para `Exception`."""
        from hefesto_dualsense4unix.interface import onde
        from pacotes import a02_controles as a02

        def _explode(*_a: Any, **_k: Any) -> Any:
            raise RuntimeError("o nome ainda não existe neste ponto do import")

        monkeypatch.setattr(onde, "pagina", _explode)  # noqa-acento: atributo
        with pytest.raises(RuntimeError):
            a02._a_pagina_tem_o_ouvir_junto()

    def test_arquivo_que_nao_abre_continua_sendo_um_nao(
        self, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        """A outra metade: `OSError` É engolido, e vira `False`."""
        from hefesto_dualsense4unix.interface import onde
        from pacotes import a02_controles as a02

        def _sem_arquivo(*_a: Any, **_k: Any) -> Any:
            raise OSError("a página publicada não está aqui")

        monkeypatch.setattr(onde, "pagina", _sem_arquivo)  # noqa-acento: atributo
        assert a02._a_pagina_tem_o_ouvir_junto() is False


class TestOQueATelaAcende:
    def test_com_mix_a_fileira_acende_o_ouvir_junto(self) -> None:
        """O produto, sem dublê de constante nenhum."""
        from pacotes import a02_controles as a02

        if MARCA_DO_JUNTO not in _pagina_publicada():
            pytest.skip("a página publicada ainda tem dois botões")
        assert a02.aceso_da_fileira(P1, _dele(P1, fonte="mix")) == "junto"
        assert a02.aceso_da_fileira(P1, _dele(P1, fonte="sfx")) == "jogo"

    def test_a_pagina_e_o_pacote_falam_do_mesmo_botao(self) -> None:
        """O `data-hef-quando` que o pacote emite existe NA PÁGINA publicada."""
        from pacotes import a02_controles as a02

        doc = _pagina_publicada()
        if MARCA_DO_JUNTO not in doc:
            pytest.skip("a página publicada ainda tem dois botões")
        assert f'data-hef-quando="{a02.ROTA_OUVIR_JUNTO}"' in doc


class TestSairDoTodoOSomDoPC:
    def test_o_junto_vindo_do_pc_devolve_o_byte_da_rota(
        self, casa: pathlib.Path, sem_maquina_dela: dict[str, list[Any]]
    ) -> None:
        """MORDIDA: apague o ramo que reenvia `rota` no «Ouvir junto»."""
        from pacotes import a02_controles as a02

        p = Ponte()
        _gesto("rota")(_ctx(_dele(P1, rota=a02.ROTA_DO_CANAL[a02.CANAL_TODO_O_PC])),
                       {"uniq": P1, "rota": "junto"}, p)

        pedidos = p.com_byte_de_rota()
        assert pedidos, "o «Ouvir junto» não devolveu o byte da rota ao daemon"
        assert pedidos[0]["rota"] == a02.ROTA_DO_CANAL[a02.CANAL_SONS_DO_JOGO]
        assert pedidos[0]["uniq"] == P1, "o byte foi para outro controle"
        assert sem_maquina_dela["devolveu"], "a camada 1 não foi devolvida"

    def test_o_cartao_para_de_mandar_desfazer_o_clique_dela(
        self, casa: pathlib.Path, sem_maquina_dela: dict[str, list[Any]]
    ) -> None:
        """A ressalva do cartão some — é ela que ela LERIA depois do clique."""
        from hefesto_dualsense4unix.app import audio_saida
        from pacotes import a02_controles as a02

        antes = a02.ROTA_DO_CANAL[a02.CANAL_TODO_O_PC]
        assert audio_saida.recado_da_rota(antes, "sink-do-p1", "sink-da-tv"), (
            "a régua não reproduz o desacordo que ela veio medir")

        p = Ponte()
        _gesto("rota")(_ctx(_dele(P1, rota=antes)), {"uniq": P1, "rota": "junto"}, p)
        depois = p.com_byte_de_rota()[0]["rota"]
        assert audio_saida.recado_da_rota(depois, "sink-do-p1", "sink-da-tv") == ""

    def test_vindo_de_sons_do_jogo_ele_continua_calado(
        self, casa: pathlib.Path, sem_maquina_dela: dict[str, list[Any]]
    ) -> None:
        """MORDIDA: tire a condição e reenvie o byte sempre."""
        from pacotes import a02_controles as a02

        p = Ponte()
        _gesto("rota")(_ctx(_dele(P1, rota=a02.ROTA_DO_CANAL[a02.CANAL_SONS_DO_JOGO])),
                       {"uniq": P1, "rota": "junto"}, p)
        assert not p.com_byte_de_rota(), (
            f"o «Ouvir junto» mexeu no firmware sem precisar: {p.chamadas}")

    def test_sem_byte_publicado_ele_tambem_fica_calado(
        self, casa: pathlib.Path, sem_maquina_dela: dict[str, list[Any]]
    ) -> None:
        """MORDIDA: compare com `!= sons do jogo` em vez de `== todo o som`."""
        p = Ponte()
        _gesto("rota")(_ctx(_dele(P1, rota=None)), {"uniq": P1, "rota": "junto"}, p)
        assert not p.com_byte_de_rota(), (
            f"reenviou a rota sobre um byte que o daemon nunca publicou: {p.chamadas}")

    def test_o_perfil_lembra_as_duas_metades_e_so_do_dono(
        self, casa: pathlib.Path, sem_maquina_dela: dict[str, list[Any]]
    ) -> None:
        """MORDIDA: grave só a `fonte`, como antes."""
        from pacotes import a02_controles as a02

        _gesto("rota")(_ctx(_dele(P1, rota=a02.ROTA_DO_CANAL[a02.CANAL_TODO_O_PC]),
                            _dele(P2)),
                       {"uniq": P1, "rota": "junto"}, Ponte())

        dele = (_do_controle(CHAVE_P1).get("speaker") or {})
        assert dele.get("fonte") == "mix"
        assert dele.get("rota") == a02.ROTA_DO_CANAL[a02.CANAL_SONS_DO_JOGO]
        assert not _do_controle(CHAVE_P2), "a escolha de um chegou ao vizinho"

    def test_um_daemon_que_recusa_nao_deixa_o_perfil_a_meio_caminho(
        self, casa: pathlib.Path, sem_maquina_dela: dict[str, list[Any]]
    ) -> None:
        """MORDIDA: ignore o retorno de `speaker_set` no ramo do «junto»."""
        from pacotes import a02_controles as a02

        with pytest.raises(RuntimeError, match="não confirmou"):
            _gesto("rota")(
                _ctx(_dele(P1, rota=a02.ROTA_DO_CANAL[a02.CANAL_TODO_O_PC])),
                {"uniq": P1, "rota": "junto"}, Ponte(recusa=True))
        assert not _do_controle(CHAVE_P1), (
            "o perfil guardou uma escolha que o daemon recusou")


class TestOGestoEntregaAFonte:
    """O que o botão MANDA, e não só o que ele grava — 20/09/2026."""

    def test_o_botao_do_meio_diz_mix_ao_daemon(
        self, casa: pathlib.Path, sem_maquina_dela: dict[str, list[Any]]
    ) -> None:
        """MORDIDA: troque o `"mix"` do ramo do «junto» por `"sfx"`."""
        p = Ponte()
        _gesto("rota")(_ctx(_dele(P1), _dele(P2)), {"uniq": P1, "rota": "junto"}, p)

        pedidos = p.com_fonte()
        assert pedidos, (
            f"o «Efeitos do Jogo e Áudio da TV no Controle» não disse a camada "
            f"1 ao daemon — só o perfil soube: {p.nomes}")
        assert [q["fonte"] for q in pedidos] == ["mix"], (
            f"o botão do meio mandou outra fonte ao nó: {pedidos}")
        assert all(q.get("uniq") == P1 for q in pedidos), (
            f"a camada 1 de um controle foi parar noutro: {pedidos}")

    def test_sair_do_botao_do_meio_diz_sfx_ao_daemon(
        self, casa: pathlib.Path, sem_maquina_dela: dict[str, list[Any]]
    ) -> None:
        """MORDIDA: troque o `"sfx"` do ramo de saída por `"mix"`."""
        p = Ponte()
        _gesto("rota")(_ctx(_dele(P1, fonte="mix"), _dele(P2)),
                       {"uniq": P1, "rota": "jogo"}, p)

        pedidos = p.com_fonte()
        assert pedidos, (
            f"sair do botão do meio não devolveu a camada 1 ao daemon: {p.nomes}")
        assert [q["fonte"] for q in pedidos] == ["sfx"], (
            f"a saída do «junto» mandou outra fonte ao nó: {pedidos}")
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
        _gesto("rota")(_ctx(_dele(P1, rota=a02.ROTA_DO_CANAL[a02.CANAL_TODO_O_PC])),
                       {"uniq": P1, "rota": "junto"}, p)

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
        ("o", "metodo"),  # noqa-acento: nome de parametro
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
