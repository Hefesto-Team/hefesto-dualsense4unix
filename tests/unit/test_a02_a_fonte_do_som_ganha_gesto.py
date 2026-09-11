"""SOM-NA-TELA-01 (A3) — a `fonte` de cada controle ganhou gesto e leitura.

**O DEFEITO, medido em 10/09/2026 e escrito na própria sprint:** a
SFX-POR-CONTROLE-01 fiou o produto para OBEDECER a `speaker.fonte` — `mix` põe
o monitor da saída padrão TAMBÉM no nó daquele controle (o som do PC chega ao
plástico **sem sair da televisão**), `sfx` deixa o nó só para o que o jogo
mandar. E **nenhuma aba gravava aquele campo**:

    grep -rn '"fonte"' interface/ app/   →  zero escritor de speaker.fonte

*O efeito pronto e sem escolha* — o defeito-mãe desta casa virado do avesso.

## O QUE ESTA RÉGUA TRAVA

1. o daemon PUBLICA a fonte, pelo dono que já a conhece (gancho), e `""`
   quando ninguém sabe — nunca o padrão disfarçado de escolha;
2. a aba LÊ do estado, e não abre perfil por conta própria;
3. o gesto GRAVA, pelo escritor único do som, e o de um controle não encosta
   no vizinho;
4. «Ouvir junto» DESLIGA a camada 1, porque «Todo o som do PC» tira o som da
   televisão e ele não tira;
5. sair do «junto» apaga o `mix` — os três botões são um estado só;
6. **e o pacote se limita ao que a página PUBLICADA tem**, que é a régua do
   `check_o_desenho_aprovado` virada em código: emitir `"junto"` para uma
   página de dois botões apagaria a fileira inteira, sem uma palavra.

**A MORDIDA de cada teste está na sua docstring.**
"""

from __future__ import annotations

import json
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


@pytest.fixture
def fileira_de_tres(monkeypatch: pytest.MonkeyPatch) -> None:
    """A página publicada COM o terceiro botão — o mundo depois do `--publicar`.

    Sem esta fixture as réguas de leitura mediriam o mundo de hoje (a página de
    dois), e passariam por acidente no dia em que a aba for publicada.
    """
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
    import pacotes.a02_controles  # importar é registrar

    fn = pacotes.gesto_da_pagina("02-controles.html", nome)
    assert fn is not None, f"02-controles.html:{nome} não tem dono"
    return fn


def _do_controle(chave: str) -> dict[str, Any]:
    from hefesto_dualsense4unix.utils.xdg_paths import profiles_dir

    # O NOME DO ARQUIVO É DO LOADER, e não desta régua: ele troca hífen por
    # `_`. Digitar o nome aqui foi o que fez as duas primeiras versões deste
    # arquivo lerem `{}` e acusarem a cura de não gravar — a régua medindo a
    # própria aritmética em vez do disco.
    alvo = profiles_dir() / f"{NOME.lower().replace('-', '_')}.json"
    if not alvo.exists():
        return {}
    dos = (json.loads(alvo.read_text(encoding="utf-8")).get("controllers") or {})
    bloco = dos.get(chave)
    return bloco if isinstance(bloco, dict) else {}


# ===========================================================================
# 1. O daemon publica — e `""` não é `sfx`
# ===========================================================================


class TestOQueODaemonPublica:
    def test_o_gancho_responde_e_o_padrao_e_nao_sei(self) -> None:
        """MORDIDA: faça `fonte_publicada` devolver `FONTE_PADRAO` sem dizedor.

        Aí a tela acenderia «Sons do jogo» para todo mundo como se ela tivesse
        escolhido — uma escolha inventada é pior que nenhuma.
        """
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
        """MORDIDA: devolva o que o dizedor disser, sem conferir.

        Um `None`, um `""` ou um `"MIX"` do perfil viraria um campo que a tela
        não sabe pintar — e a fileira apagaria inteira.
        """
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


# ===========================================================================
# 2. A aba lê o que o daemon publicou
# ===========================================================================


class TestOQueATelaLe:
    def test_a_fonte_sai_do_estado_e_nao_do_disco(self) -> None:
        """MORDIDA: faça `fonte_do_controle` abrir o perfil ativo.

        Seriam dois leitores da mesma escolha dela, e o da aba rodaria a cada
        tique — a tempestade de syscalls que o mapa de motores já pagou.
        """
        from pacotes import a02_controles as a02

        assert a02.fonte_do_controle(_dele(P1, "mix")) == "mix"
        assert a02.fonte_do_controle(_dele(P1, "sfx")) == "sfx"
        assert a02.fonte_do_controle(_dele(P1)) == ""

    def test_todo_o_som_do_pc_vence_o_mix(
        self, fileira_de_tres: None, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        """MORDIDA: perguntar pelo `mix` ANTES de olhar a camada 1.

        «Todo o som do PC» é o único estado em que a saída padrão do sistema
        mudou de lugar — um fato que ela OUVE. Contradizê-lo na tela é o
        defeito de 03/09, com o botão aceso e o som saindo na televisão.
        """
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
        """MORDIDA: tire o `A_FILEIRA_TEM_TRES` de `aceso_da_fileira`.

        Enquanto ela não aprova a aba, a página publicada tem DOIS botões.
        Emitir `"junto"` ali não acende nenhum: a fileira apaga inteira, sem
        uma palavra — pior que o estado anterior, e invisível para quem
        escreveu o pacote.
        """
        from pacotes import a02_controles as a02

        monkeypatch.setattr(a02, "A_FILEIRA_TEM_TRES", False)
        assert a02.aceso_da_fileira(P1, _dele(P1, "mix")) == "jogo"


# ===========================================================================
# 3. O gesto grava — e não encosta no vizinho
# ===========================================================================


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
        """MORDIDA: apague o `devolver_o_som_do_pc()` do ramo do «junto».

        «Todo o som do PC» TIRA o som da televisão; «Ouvir junto» o deixa lá.
        Sem devolver a saída padrão, a televisão fica muda com a tela dizendo
        "junto" — o desacordo de 03/09 pela outra porta.
        """
        from hefesto_dualsense4unix.app import audio_saida
        from pacotes import a02_controles as a02

        devolveu: list[bool] = []
        monkeypatch.setattr(
            a02.audio_saida, "devolver_o_som_do_pc",
            lambda **_k: devolveu.append(True) or audio_saida.DesfechoDaRota(True))

        _gesto("rota")(_ctx(), {"uniq": P1, "rota": "junto"}, Ponte())
        assert devolveu, "o «Ouvir junto» não devolveu a saída padrão do sistema"

    def test_sair_do_junto_apaga_o_mix(self, casa: pathlib.Path) -> None:
        """MORDIDA: apague o ramo que grava `fonte: sfx` ao sair do «junto».

        Os três botões são UM estado. Um `mix` esquecido embaixo de «Sons do
        jogo» faz o controle continuar ouvindo o PC com a tela dizendo que
        não — e ela não teria botão nenhum que o desligasse.
        """
        p = Ponte()
        _gesto("rota")(_ctx(), {"uniq": P1, "rota": "junto"}, p)
        assert (_do_controle(CHAVE_P1).get("speaker") or {}).get("fonte") == "mix"

        _gesto("rota")(_ctx(_dele(P1, "mix")), {"uniq": P1, "rota": "jogo"}, p)
        assert (_do_controle(CHAVE_P1).get("speaker") or {}).get("fonte") == "sfx"

    def test_o_junto_nao_manda_byte_de_rota_ao_daemon(
        self, casa: pathlib.Path
    ) -> None:
        """MORDIDA: deixe o «junto» cair no `speaker_set(rota=…)` dos outros dois.

        A `fonte` é do NÓ (camada 1, PipeWire); a rota é do FIRMWARE (camada
        2). Mandar um byte de rota aqui escreveria no aparelho uma escolha que
        ela não fez — e apagaria a que estava valendo.
        """
        p = Ponte()
        _gesto("rota")(_ctx(), {"uniq": P1, "rota": "junto"}, p)
        assert "speaker_set" not in p.nomes, (
            f"o «Ouvir junto» mexeu no firmware: {p.nomes}")

    def test_uma_rota_que_a_pagina_nao_manda_e_recusada(
        self, casa: pathlib.Path
    ) -> None:
        """MORDIDA: aceite qualquer string em `rota`.

        O gesto é a fronteira entre a página e o perfil dela: um valor que
        ninguém reconhece tem de parar aqui, com nome, e não virar um campo
        estranho no disco.
        """
        with pytest.raises(ValueError, match="não conheço a rota"):
            _gesto("rota")(_ctx(), {"uniq": P1, "rota": "tudo"}, Ponte())
