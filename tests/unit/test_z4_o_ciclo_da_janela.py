"""Z4/T1+T2+T3 — o ciclo pela PORTA DA JANELA, com o processo morto no meio."""

from __future__ import annotations

import json
import os
import subprocess
import sys
from pathlib import Path
from typing import Any

import pytest

from tests.conftest import exigir_gi_real

exigir_gi_real("Z4 — o ciclo pela porta da janela")

RAIZ = Path(__file__).resolve().parents[2]
FIXTURES = RAIZ / "tests" / "fixtures" / "perfis_do_ciclo"
DRIVER = FIXTURES / "_driver_ciclo_janela.py"

_PERFIS_DO_CORPO_DE_PROVA: list[Any] = [
    pytest.param(caminho, id=f"{caminho.parent.name}/{caminho.stem}")
    for caminho in sorted((FIXTURES / "reais").glob("*.json"))
    + sorted((FIXTURES / "fabrica").glob("*.json"))
]


def _rodar_o_ciclo(perfil_json: Path, tmp_path: Path) -> dict[str, Any]:
    """Spawna o driver, MATA o processo ao terminar, devolve o que ele reportou."""
    xdg_home = tmp_path / "xdg"
    saida = tmp_path / "resultado.json"
    xdg_home.mkdir(parents=True, exist_ok=True)

    env = dict(os.environ)
    env["PYTHONPATH"] = f"{RAIZ / 'src'}{os.pathsep}{RAIZ}"
    env["HEFESTO_DUALSENSE4UNIX_FAKE"] = "1"

    proc = subprocess.run(
        [sys.executable, str(DRIVER), str(perfil_json), str(xdg_home), str(saida)],
        env=env,
        capture_output=True,
        text=True,
        timeout=60,
    )
    assert proc.returncode == 0, (
        f"o driver do ciclo saiu com código {proc.returncode} para "
        f"{perfil_json.name} — stderr:\n{proc.stderr}"
    )
    assert saida.exists(), (
        f"o driver terminou mas não escreveu {saida} — stderr:\n{proc.stderr}"
    )
    resultado = json.loads(saida.read_text(encoding="utf-8"))
    resultado["_xdg_home"] = str(xdg_home)
    return resultado


def _perfil_reescrito(resultado: dict[str, Any], nome_arquivo: str) -> dict[str, Any]:
    """O perfil como ficou no disco isolado do driver, relido NESTE processo."""
    caminho = (
        Path(resultado["_xdg_home"])
        / "config"
        / "hefesto-dualsense4unix"
        / "profiles"
        / nome_arquivo
    )
    assert caminho.exists(), f"o driver não deixou {caminho} no disco"
    return json.loads(caminho.read_text(encoding="utf-8"))


class TestOCicloPelaPortaDaJanela:
    """T2: abrir, tocar cada aba, Salvar, MATAR o processo, reabrir, comparar."""

    @pytest.mark.parametrize("perfil_json", _PERFIS_DO_CORPO_DE_PROVA)
    def test_o_ciclo_completo_nao_reprova(
        self, perfil_json: Path, tmp_path: Path
    ) -> None:
        """Um "Salvar Perfil" com as sete abas mexidas sobrevive ao processo morto."""
        resultado = _rodar_o_ciclo(perfil_json, tmp_path)
        assert resultado["ok"], (
            f"o driver não conseguiu completar o ciclo para {perfil_json.name}: "
            f"{resultado.get('erro')}"
        )
        assert not resultado.get("falhas_de_gesto"), (
            f"gesto(s) que lançaram durante o ciclo de {perfil_json.name}: "
            f"{resultado['falhas_de_gesto']}"
        )

    def test_matriz_pode_ler_o_perfil_reescrito(self, tmp_path: Path) -> None:
        """Sanidade da T3: o arquivo reescrito é um ``Profile`` válido."""
        from hefesto_dualsense4unix.profiles.schema import Profile

        alvo = FIXTURES / "reais" / "pragmata.json"
        resultado = _rodar_o_ciclo(alvo, tmp_path)
        assert resultado["ok"], resultado.get("erro")
        relido = _perfil_reescrito(resultado, "pragmata.json")
        Profile.model_validate(relido)


class TestAMordidaDaT4SemACura:
    """Prova, rodada AGORA, de que o ciclo REPROVAVA antes de T4/draft_config.py."""

    def test_aventura_e_corrida_sao_os_unicos_com_params_aninhado(self) -> None:
        aninhados = []
        for nome in ("aventura.json", "corrida.json"):
            dados = json.loads((FIXTURES / "fabrica" / nome).read_text())
            for lado in ("left", "right"):
                params = dados.get("triggers", {}).get(lado, {}).get("params")
                if params and isinstance(params[0], list):
                    aninhados.append(nome)
                    break
        assert sorted(set(aninhados)) == ["aventura.json", "corrida.json"], (
            f"a régua achou {aninhados!r} — a sprint mediu exatamente "
            "aventura.json e corrida.json em 24/08/2026; se a lista mudou, o "
            "corpo de prova (T1) e/ou os presets de fábrica mudaram de forma "
            "e a T4 precisa de nova medição, não desta reafirmação"
        )
