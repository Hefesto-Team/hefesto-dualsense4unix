"""O ciclo de verdade, num PROCESSO À PARTE (Z4/T2, 24/08/2026).

Não é chamado por importação — é invocado via ``subprocess.run([sys.executable,
__file__, ...])`` pelo teste ``tests/unit/test_z4_o_ciclo_da_janela.py``. É por
isso que existe: recarregar o mesmo ``DraftConfig`` no mesmo processo não vê
estado que sobreviveu só em memória (o passo que falta em toda a suíte
``test_perfil_salva_tudo_ida_e_volta.py``, que é do mesmo processo do início ao
fim). Este driver ABRE o perfil, toca CADA gesto que ``_GESTOS`` já sabe tocar
(reusado daquele módulo, não reescrito — a sprint pede isso por nome), salva
pelo funil real do rodapé (``on_save_profile``) e **termina o processo aqui**.
Quem compara o antes/depois é o teste, num processo NOVO, relendo do disco.

Argumentos posicionais:
    1. caminho do perfil de origem (JSON, lido só para achar o ``name``)
    2. diretório XDG_CONFIG_HOME isolado (a "casa" deste ciclo)
    3. caminho de saída (JSON): ``{"ok": bool, "erro": str|null, "aplicados":
       [...]}`` — aplicados é a lista de campos cujo gesto rodou sem lançar.

Sai com código 0 sempre que o driver TERMINOU (mesmo que o gesto de um campo
tenha lançado — isso vai no JSON, não no exit code); código != 0 só numa
falha do próprio driver (perfil não carrega, import falhou).
"""

from __future__ import annotations

import json
import os
import sys
from pathlib import Path

_ORIGEM, _XDG_HOME, _SAIDA = sys.argv[1], sys.argv[2], sys.argv[3]

# ISOLAMENTO — antes de qualquer import hefesto. platformdirs lê o env a cada
# chamada (não há cache de módulo), mas o hábito da casa (conftest) é setar
# antes de importar, e aqui não há fixture para fazer isso por nós.
os.environ["HEFESTO_DUALSENSE4UNIX_FAKE"] = "1"
os.environ["XDG_CONFIG_HOME"] = str(Path(_XDG_HOME) / "config")
os.environ["XDG_DATA_HOME"] = str(Path(_XDG_HOME) / "data")
os.environ["XDG_CACHE_HOME"] = str(Path(_XDG_HOME) / "cache")
os.environ["XDG_STATE_HOME"] = str(Path(_XDG_HOME) / "state")
for _sub in ("config", "data", "cache", "state"):
    (Path(_XDG_HOME) / _sub).mkdir(parents=True, exist_ok=True)
# Desliga a semeadura automática de presets de fábrica — o mesmo motivo do
# conftest (FIX-PACKAGING-SEED-PARITY-01): este processo só deve enxergar o
# ÚNICO perfil que a T2 plantou.
os.environ["HEFESTO_DUALSENSE4UNIX_SKIP_PRESET_SEED"] = "1"

from unittest.mock import MagicMock, patch  # noqa: E402

from hefesto_dualsense4unix.app.actions import footer_actions  # noqa: E402
from hefesto_dualsense4unix.app.draft_config import DraftConfig  # noqa: E402
from hefesto_dualsense4unix.profiles.loader import save_profile  # noqa: E402
from hefesto_dualsense4unix.profiles.schema import Profile  # noqa: E402

# Reuso deliberado — a sprint T2 pede por nome: "a lista de gestos já existe:
# `_GESTOS` em test_perfil_salva_tudo_ida_e_volta.py — reuse, não reescreva".
from tests.unit.test_perfil_salva_tudo_ida_e_volta import (  # noqa: E402
    SECOES_COBERTAS,
    _gesto_de,
    _janela,
)


class _MonkeypatchDeProcessoUnico:
    """``.setattr`` sem desfazer — o processo morre no fim, não precisa devolver.

    Só ``_gesto_rumble`` usa isto (troca ``rumble_actions.rumble_policy_set_checked``
    por um dublê que aceita sempre). O ``pytest.MonkeyPatch`` real também não
    seria desfeito a tempo aqui — o processo acaba antes de qualquer teardown.
    """

    def setattr(self, obj: object, nome: str, valor: object) -> None:
        setattr(obj, nome, valor)


def _run_in_thread_sincrono(fn: object, on_success: object, on_failure: object = None) -> None:
    try:
        resultado = fn()  # type: ignore[operator]
    except Exception as exc:  # espelha o run_in_thread real
        if on_failure is not None:
            on_failure(exc)  # type: ignore[operator]
        return
    on_success(resultado)  # type: ignore[operator]


def main() -> int:
    resultado: dict[str, object] = {"ok": False, "erro": None, "aplicados": []}
    try:
        origem = json.load(open(_ORIGEM, encoding="utf-8"))
        perfil = Profile.model_validate(origem)
        save_profile(perfil, origem="Z4/T2:driver-ciclo-janela")

        footer_actions.ipc_bridge.run_in_thread = _run_in_thread_sincrono  # type: ignore[assignment]

        draft = DraftConfig.from_profile(perfil)
        janela = _janela(draft, perfil.name)
        mp = _MonkeypatchDeProcessoUnico()

        aplicados: list[str] = []
        falhas: dict[str, str] = {}
        # `controllers` por último — o mesmo motivo do teste irmão: o gesto
        # deixa um controle selecionado no seletor, e uma seção posterior
        # cairia no override em vez do global.
        ordem = [c for c in SECOES_COBERTAS if c != "controllers"] + ["controllers"]
        for campo in ordem:
            try:
                _gesto_de(campo, janela, mp)  # type: ignore[arg-type]
                aplicados.append(campo)
            except Exception as exc:  # o driver REGISTRA, não esconde
                falhas[campo] = f"{type(exc).__name__}: {exc}"

        dialogos = MagicMock()
        dialogos.prompt_profile_name.return_value = perfil.name
        dialogos.prompt_overwrite_existing.return_value = True
        with patch(
            "hefesto_dualsense4unix.app.actions.footer_actions.gui_dialogs", dialogos
        ):
            janela.on_save_profile()

        resultado["ok"] = True
        resultado["aplicados"] = aplicados
        resultado["falhas_de_gesto"] = falhas
    except Exception as exc:  # falha do PRÓPRIO driver, não do produto
        resultado["ok"] = False
        resultado["erro"] = f"{type(exc).__name__}: {exc}"

    Path(_SAIDA).write_text(json.dumps(resultado), encoding="utf-8")
    return 0


if __name__ == "__main__":
    sys.exit(main())
