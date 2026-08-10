"""O-VERDE-NAO-LEVAVA-O-SOM-01 — o "Aplicar" deixava o alto-falante para trás.

O PEDIDO DELA, 10/08/2026
=========================
    *"Preciso que cada feature de cada aba ao clicarmos em salvar perfil e
    aplicar (botão verde) tudo fique salvo no perfil ativo. (...) todas as
    features em cada aba, touch, giroscopio, speaker, mic, gatilho, lightbar.
    tudo."*

O QUE FOI MEDIDO
================
O botão verde manda `profile.apply_draft`, e quem o cumpre é o `DraftApplier`.
Ele aplicava **leds, triggers, controllers, rumble, mouse, keyboard e mic**.

    grep -c speaker src/hefesto_dualsense4unix/daemon/ipc_draft_applier.py
    0

Zero. O volume, o mudo e o canal do alto-falante chegavam ao PERFIL (pelo
`to_profile`) e ao hardware na ATIVAÇÃO de um perfil (`apply_profile_speaker`,
pela rota do autoswitch) — mas **nunca pelo AGORA**. Ela mexia no card, clicava
no verde, e o som só mudava na próxima troca de perfil.

O PORTÃO QUE ESTE ARQUIVO CRIA
==============================
O defeito não foi de código, foi de **lista que se desatualiza**: o `mic` já
tinha entrado sem ser citado na docstring do módulo, e o `speaker` nunca entrou.
Duas listas descrevem a mesma promessa — o que a janela EMITE (`to_ipc_dict`) e o
que o daemon APLICA (`DraftApplier`) — e nada as amarrava.

O teste `test_toda_secao_que_a_janela_emite_o_daemon_aplica` deriva as duas em
runtime e compara. No dia em que alguém acrescentar uma seção de um lado só, ele
reprova com o nome da seção órfã. É esse o "impede regressões futuras" que ela
pediu.
"""

from __future__ import annotations

from typing import Any

import pytest

from hefesto_dualsense4unix.app.draft_config import DraftConfig
from hefesto_dualsense4unix.daemon.ipc_draft_applier import DraftApplier

#: Seções que o `to_ipc_dict` emite e que NÃO são para o DraftApplier aplicar.
#: Hoje só uma: o `mode` viaja por outro caminho, e o motivo está escrito no
#: `footer_actions.on_apply_draft` — `apply_mode` dispara até três chamadas de
#: 2,0 s e não cabe no `timeout_s=1.5` do `apply_draft`. Toda entrada aqui é uma
#: exceção DECLARADA; a lista curta é o que dá valor ao portão.
_NAO_E_DO_APPLIER = {"mode"}


class _DaemonDublado:
    def __init__(self) -> None:
        self.speaker_chamado: list[dict[str, Any]] = []

    def apply_profile_speaker(
        self,
        volume: int,
        muted: bool = False,
        *,
        uniq: str | None = None,
        origin: str = "autoswitch",
        rota: int | None = None,
    ) -> str:
        self.speaker_chamado.append(
            {"volume": volume, "muted": muted, "uniq": uniq, "origin": origin, "rota": rota}
        )
        return "ok"


def _applier() -> tuple[DraftApplier, _DaemonDublado]:
    daemon = _DaemonDublado()
    return DraftApplier(controller=object(), store=_StoreDublado(), daemon=daemon), daemon


class _StoreDublado:
    def mark_manual_trigger_active(self, _categoria: str) -> None:
        return None


# ---------------------------------------------------------------------------
# A cura
# ---------------------------------------------------------------------------


def test_o_verde_leva_o_volume_do_alto_falante() -> None:
    """A cura. Morde ao apagar a linha do `speaker` do `apply`.

    Arranque para ver reprovar: tirar
    `self._apply_section(applied, params.get("speaker"), ...)`. É o estado do
    produto até 10/08/2026, e o efeito é o som não mudar até a próxima troca de
    perfil.
    """
    applier, daemon = _applier()
    aplicadas = applier.apply({"speaker": {"volume": 70, "muted": False, "rota": 1}})

    assert "speaker" in aplicadas
    assert daemon.speaker_chamado == [
        {"volume": 70, "muted": False, "uniq": None, "origin": "draft", "rota": 1}
    ]


def test_a_origem_diz_que_veio_do_rascunho() -> None:
    """`origin="draft"` separa o gesto dela do autoswitch no journal.

    Sem isso, um "Aplicar" e uma troca automática de perfil viram a mesma linha
    de log — e a próxima investigação de som perde a única pista de QUEM mexeu.
    """
    applier, daemon = _applier()
    applier.apply({"speaker": {"volume": 10}})
    assert daemon.speaker_chamado[0]["origin"] == "draft"


def test_sem_a_secao_o_som_nao_e_tocado() -> None:
    """Um "Aplicar" de outra aba não pode mexer no som pelas costas dela.

    É a mesma regra do `mouse` e do `mic`, e está escrita nos dois: o rascunho
    só emite a seção quando ela mexeu.
    """
    applier, daemon = _applier()
    aplicadas = applier.apply({"leds": None, "speaker": None})
    assert "speaker" not in aplicadas
    assert daemon.speaker_chamado == []


@pytest.mark.parametrize(
    "payload",
    [
        {"volume": "70"},
        {"volume": True},
        {"volume": -1},
        {"volume": 256},
        {"volume": 50, "muted": "sim"},
        {"volume": 50, "rota": "1"},
        "não é um objeto",
    ],
)
def test_payload_torto_falha_a_secao_e_nao_o_aplicar_inteiro(payload: Any) -> None:
    """Best-effort: a seção ruim entra em `failed`, as outras seguem.

    É a doutrina APLICAR-VERDADE-01 desta casa — e o `bool` na lista não é
    capricho: em Python `isinstance(True, int)` é verdadeiro, então sem a guarda
    explícita um `muted` mandado no lugar do `volume` viraria "volume 1".
    """
    applier, daemon = _applier()
    aplicadas = applier.apply({"speaker": payload})
    assert "speaker" not in aplicadas
    assert "speaker" in applier.failed
    assert daemon.speaker_chamado == []


def test_volume_ausente_nao_e_erro_e_nao_toca_no_som() -> None:
    """Seção sem opinião é silêncio, nunca ordem (SOM-02/E4)."""
    applier, daemon = _applier()
    aplicadas = applier.apply({"speaker": {"muted": True}})
    assert daemon.speaker_chamado == []
    assert "speaker" in aplicadas, "sem opinião não é FALHA — é nada a fazer"


def test_o_applier_reusa_a_porta_do_perfil_e_nao_o_backend_cru() -> None:
    """Um caminho novo direto ao backend seria um SEGUNDO dono do áudio.

    E seria pior que redundante: o `set_speaker_volume` do backend, medido em
    10/08/2026, **não tem gate de `_output_mute`** — em Modo Nativo ele responde
    `ok` sem mandar byte nenhum, e a tela diria que aplicou. A porta
    `apply_profile_speaker` é a mesma da ativação de perfil e já carrega a
    política.

    Morde ao trocar a chamada por `self.controller.set_speaker_volume(...)`.
    """
    import ast
    import inspect
    import textwrap

    # O CORPO, sem a docstring: a primeira versão deste teste procurava a
    # string no `getsource` inteiro e reprovava por causa da EXPLICAÇÃO que a
    # própria docstring dá sobre não usar o backend cru. Régua que não separa o
    # que o código FAZ do que ele DIZ acusa quem documentou bem.
    fonte = textwrap.dedent(inspect.getsource(DraftApplier._apply_speaker))
    arvore = ast.parse(fonte).body[0]
    assert isinstance(arvore, ast.FunctionDef)
    corpo = [n for n in arvore.body if not _e_docstring(n)]
    chamadas = {
        n.func.attr
        for bloco in corpo
        for n in ast.walk(bloco)
        if isinstance(n, ast.Call) and isinstance(n.func, ast.Attribute)
    }
    nomes = {
        n.id
        for bloco in corpo
        for n in ast.walk(bloco)
        if isinstance(n, ast.Name)
    }
    assert "apply_profile_speaker" in (chamadas | nomes | _atributos(corpo))
    assert "set_speaker_volume" not in (chamadas | _atributos(corpo)), (
        "o applier passou a falar direto com o backend — segundo dono do áudio"
    )


def _e_docstring(no: object) -> bool:
    import ast

    return (
        isinstance(no, ast.Expr)
        and isinstance(no.value, ast.Constant)
        and isinstance(no.value.value, str)
    )


def _atributos(corpo: list[object]) -> set[str]:
    import ast

    return {
        n.attr
        for bloco in corpo
        for n in ast.walk(bloco)  # type: ignore[arg-type]
        if isinstance(n, ast.Attribute)
    } | {
        n.value
        for bloco in corpo
        for n in ast.walk(bloco)  # type: ignore[arg-type]
        if isinstance(n, ast.Constant) and isinstance(n.value, str)
    }


# ---------------------------------------------------------------------------
# O portão que impede a próxima seção órfã
# ---------------------------------------------------------------------------


def test_toda_secao_que_a_janela_emite_o_daemon_aplica() -> None:
    """O portão. Duas listas descrevem a mesma promessa e nada as amarrava.

    Deriva em RUNTIME o que o `to_ipc_dict` emite e o que o `DraftApplier`
    aplica, e compara. Foi assim que o `speaker` passou despercebido: ninguém
    somou as duas colunas.

    Morde ao acrescentar uma seção só de um lado — que é exatamente o que vai
    acontecer na próxima feature.
    """
    emitidas = set(DraftConfig().to_ipc_dict()) - _NAO_E_DO_APPLIER
    aplicadas = {
        nome[len("_apply_") :]
        for nome in dir(DraftApplier)
        if nome.startswith("_apply_") and nome != "_apply_section"
    }
    orfas = emitidas - aplicadas
    assert not orfas, (
        f"a janela emite {sorted(orfas)} e o daemon não aplica. Ou o "
        "`DraftApplier` ganha um `_apply_<seção>`, ou a seção sai do "
        "`to_ipc_dict` — mas as duas listas têm de fechar."
    )


def test_a_docstring_do_modulo_lista_as_secoes_de_verdade() -> None:
    """A promessa escrita tem de bater com a promessa cumprida.

    A docstring do `ipc_draft_applier` enumera as seções, e ficou desatualizada
    DUAS vezes: o `mic` entrou sem ser citado, e o `speaker` faltava por inteiro.
    Documentação que descreve outro produto é pior que documentação nenhuma —
    foi ela que me fez procurar o defeito no lugar errado por um tempo.
    """
    import hefesto_dualsense4unix.daemon.ipc_draft_applier as mod

    # A ENUMERAÇÃO, não a docstring inteira. A primeira versão deste teste
    # procurava o nome em qualquer lugar do texto e passava com a seção fora da
    # lista — porque o parágrafo que EXPLICA o defeito também diz "speaker".
    # Teste que aceita a palavra em qualquer parágrafo não vigia a lista: vigia
    # a existência da prosa.
    doc = mod.__doc__ or ""
    i = doc.index("Cada seção (")
    enumeracao = doc[i : doc.index(")", i)].lower()
    aplicadas = {
        nome[len("_apply_") :]
        for nome in dir(DraftApplier)
        if nome.startswith("_apply_") and nome != "_apply_section"
    }
    faltando = sorted(s for s in aplicadas if s not in enumeracao)
    assert not faltando, (
        f"a enumeração da docstring do módulo não cita: {faltando}. "
        "Ela é a promessa escrita do botão verde."
    )
