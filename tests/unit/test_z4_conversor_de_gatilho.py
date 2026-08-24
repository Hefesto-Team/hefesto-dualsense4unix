"""Z4/T4+T5+T6 — o conversor de gatilho para de reprovar `aventura`/`corrida`.

Frente **Z4** da ONDA 0 (24/08/2026). Medido na sprint (§2.1): dois dos doze
presets de fábrica (`aventura.json`, `corrida.json`) não abriam no editor
porque `TriggerConfig.params` aceita `list[int] | list[list[int]]` (o disco) e
`TriggerDraft.params` só aceitava plano (o rascunho) — e o comentário de
`draft_config.py:316-318` afirmava o contrário do que o `cast` fazia.

A cura escolhida (medida contra a alternativa na seção 3 da sprint — "meça as
duas antes de escolher"): **achatar na fronteira** (`_trigger_params_para_draft`),
preservando a forma aninhada original só para o caso em que o gatilho NÃO foi
tocado entre abrir e salvar (`TriggerDraft.params_aninhado_original`). A
alternativa — alargar `TriggerDraft.params` para aceitar as duas formas —
custaria tocar `app/actions/triggers_actions.py` (que lê `params[i]` como
`int`), e esse arquivo é posse de outra frente (Z2/onda de aba); a escolha
feita não toca nele.

Este módulo é PURO (sem GTK) — mede o conversor isolado. O ciclo pela porta da
janela (com os mesmos dois perfis) está em
`tests/unit/test_z4_o_ciclo_da_janela.py`.
"""

from __future__ import annotations

import json
from pathlib import Path

import pytest

from hefesto_dualsense4unix.app.actions.trigger_specs import (
    PRESETS,
    TriggerPresetSpec,
    preset_to_positional_params,
)
from hefesto_dualsense4unix.app.draft_config import DraftConfig
from hefesto_dualsense4unix.core.trigger_effects import build_from_name
from hefesto_dualsense4unix.profiles.schema import (
    MatchCriteria,
    Profile,
    TriggerConfig,
    TriggersConfig,
)

RAIZ = Path(__file__).resolve().parents[2]
FIXTURES_FABRICA = RAIZ / "tests" / "fixtures" / "perfis_do_ciclo" / "fabrica"


def _perfil_com_trigger(left: TriggerConfig) -> Profile:
    return Profile(
        name="teste-z4-conversor",
        match=MatchCriteria(window_class=["steam_app_0"]),
        priority=1,
        triggers=TriggersConfig(left=left, right=TriggerConfig(mode="Off", params=[])),
    )


# ---------------------------------------------------------------------------
# T4 — aventura e corrida abrem no editor, e o arquivo não muda de forma
# ---------------------------------------------------------------------------


class TestAventuraECorridaAbremNoEditor:
    """T4, aceite 1: a régua da §2.1 devolve lista vazia (hoje devolve dois)."""

    @pytest.mark.parametrize("nome", ["aventura.json", "corrida.json"])
    def test_from_profile_nao_reprova(self, nome: str) -> None:
        original = json.loads((FIXTURES_FABRICA / nome).read_text())
        perfil = Profile.model_validate(original)
        DraftConfig.from_profile(perfil)  # não lança

    def test_os_doze_presets_de_fabrica_abrem_todos(self) -> None:
        mau = []
        for f in sorted(FIXTURES_FABRICA.glob("*.json")):
            perfil = Profile.model_validate(json.loads(f.read_text()))
            try:
                DraftConfig.from_profile(perfil)
            except Exception:
                mau.append(f.name)
        assert mau == [], f"presets de fábrica que não abrem no editor: {mau}"


class TestSalvarSemTocarPreservaAFormaDoArquivo:
    """A segunda metade da mordida da T4 — a que morde de verdade.

    "Salve sem tocar em nada e compare o arquivo byte a byte com o original.
    Se a forma dos params mudou, a cura está trocando um defeito por outro."
    """

    @pytest.mark.parametrize("nome", ["aventura.json", "corrida.json"])
    def test_triggers_idênticos_apos_ida_e_volta_sem_edicao(self, nome: str) -> None:
        original = json.loads((FIXTURES_FABRICA / nome).read_text())
        perfil = Profile.model_validate(original)
        draft = DraftConfig.from_profile(perfil)
        relido = draft.to_profile(perfil.name, priority=perfil.priority)
        novo = json.loads(relido.model_dump_json(exclude_none=True))
        assert novo["triggers"] == original["triggers"], (
            f"a forma de `triggers` em {nome} mudou ao salvar SEM editar nada: "
            f"era {original['triggers']!r}, virou {novo['triggers']!r}"
        )

    def test_editar_o_gatilho_aninhado_grava_plano_sem_reprovar(self) -> None:
        """Uma vez editado, o gatilho grava PLANO — não é perda, é a edição."""
        from hefesto_dualsense4unix.app.draft_config import TriggerDraft

        original = json.loads((FIXTURES_FABRICA / "aventura.json").read_text())
        perfil = Profile.model_validate(original)
        draft = DraftConfig.from_profile(perfil)

        # a mesma construção que `triggers_actions._persist_params_to_draft`
        # usa de verdade: TriggerDraft novo, sem `model_copy`.
        editado = draft.model_copy(
            update={
                "triggers": draft.triggers.model_copy(
                    update={"left": TriggerDraft(mode="Rigid", params=(5, 200))}
                )
            }
        )
        relido = editado.to_profile(perfil.name, priority=perfil.priority)
        assert relido.triggers.left.mode == "Rigid"
        assert list(relido.triggers.left.params) == [5, 200]


# ---------------------------------------------------------------------------
# T5 — o comentário falso e os casts mortos saem
# ---------------------------------------------------------------------------


class TestOComentarioFalsoSaiu:
    def test_grep_do_comentario_falso_esta_vazio(self) -> None:
        alvo = RAIZ / "src" / "hefesto_dualsense4unix" / "app" / "draft_config.py"
        texto = alvo.read_text(encoding="utf-8")
        assert "aceita ambos" not in texto and "via tuple" not in texto, (
            "o comentário falso ('TriggerDraft aceita ambos via tuple') ainda "
            "está em draft_config.py — ele foi medido falso na sprint (§2.1) "
            "e a regra da casa é substituir, não deixar ao lado do certo"
        )


# ---------------------------------------------------------------------------
# T6 — os dezenove modos entram e voltam
# ---------------------------------------------------------------------------


def _params_para_disco(nome_preset: str, flat: list[int]) -> list[int] | list[list[int]]:
    """Simula a forma que ESTES dois modos assumem no disco dela (nested)."""
    if nome_preset == "MultiPositionFeedback":
        return [[v] for v in flat]
    if nome_preset == "MultiPositionVibration":
        # corrida.json real: frequency fica de fora, só as 10 posições aninhadas.
        return [[v] for v in flat[1:]]
    return flat


class TestOsDezenoveModosEntramEVoltam:
    """Deriva a lista de `trigger_specs.PRESETS` em runtime — nunca à mão."""

    @pytest.mark.parametrize(
        "spec", PRESETS, ids=[s.name for s in PRESETS]
    )
    def test_o_modo_sobrevive_ao_ciclo_do_conversor(self, spec: TriggerPresetSpec) -> None:
        valores = {p.name: p.default for p in spec.params}
        flat = preset_to_positional_params(spec, valores)
        params_disco = _params_para_disco(spec.name, flat)

        perfil = _perfil_com_trigger(TriggerConfig(mode=spec.name, params=params_disco))
        draft = DraftConfig.from_profile(perfil)
        relido = draft.to_profile(perfil.name, priority=perfil.priority)

        # a régua não é bytes — é EFEITO: o `TriggerEffect` que o modo produz
        # antes e depois do ciclo tem de ser o mesmo, senão o gatilho mudou de
        # comportamento no controle sem ninguém editar nada.
        antes = build_from_name(spec.name, params_disco)
        depois = build_from_name(relido.triggers.left.mode, relido.triggers.left.params)
        assert antes == depois, (
            f"{spec.name}: o efeito do gatilho mudou no ciclo — "
            f"antes={antes!r} depois={depois!r}"
        )

    def test_a_lista_tem_dezenove_hoje(self) -> None:
        """Sentinela: se `trigger_specs.PRESETS` crescer, a régua acima já cobre —
        este caso só documenta o número medido em 24/08/2026."""
        assert len(PRESETS) == 19, (
            f"trigger_specs.PRESETS tem {len(PRESETS)} modos — a sprint mediu "
            "19 em 24/08/2026; se mudou, é bom, a régua acima já se adapta "
            "sozinha (parametrize deriva da lista, não de um número escrito)"
        )
