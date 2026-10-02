"""O-VERDE-NAO-LEVAVA-O-SOM-01 — o "Aplicar" deixava o alto-falante para trás."""

from __future__ import annotations

from typing import Any

import pytest

from hefesto_dualsense4unix.daemon.ipc_draft_applier import DraftApplier

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


def test_o_verde_leva_o_volume_do_alto_falante() -> None:
    """A cura. Morde ao apagar a linha do `speaker` do `apply`."""
    applier, daemon = _applier()
    aplicadas = applier.apply({"speaker": {"volume": 70, "muted": False, "rota": 1}})

    assert "speaker" in aplicadas
    assert daemon.speaker_chamado == [
        {"volume": 70, "muted": False, "uniq": None, "origin": "draft", "rota": 1}
    ]


def test_a_origem_diz_que_veio_do_rascunho() -> None:
    """`origin="draft"` separa o gesto dela do autoswitch no journal."""
    applier, daemon = _applier()
    applier.apply({"speaker": {"volume": 10}})
    assert daemon.speaker_chamado[0]["origin"] == "draft"


def test_sem_a_secao_o_som_nao_e_tocado() -> None:
    """Um "Aplicar" de outra aba não pode mexer no som pelas costas dela."""
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
    """Best-effort: a seção ruim entra em `failed`, as outras seguem."""
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
    """Um caminho novo direto ao backend seria um SEGUNDO dono do áudio."""
    import ast
    import inspect
    import textwrap

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


def test_a_docstring_do_modulo_lista_as_secoes_de_verdade() -> None:
    """A promessa escrita tem de bater com a promessa cumprida."""
    import hefesto_dualsense4unix.daemon.ipc_draft_applier as mod

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
