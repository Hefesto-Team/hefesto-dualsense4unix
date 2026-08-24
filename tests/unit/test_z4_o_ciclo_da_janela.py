"""Z4/T1+T2+T3 — o ciclo pela PORTA DA JANELA, com o processo morto no meio.

Frente **Z4** da ONDA 0 (24/08/2026): "o perfil guarda tudo: sete abas chegam
ao perfil e quatro não". Este é o teste central da frente inteira (T2 da
sprint), e a diferença que ele existe para provar é uma só: **recarregar o
``DraftConfig`` no mesmo processo não vê estado que sobreviveu só em
memória.** Por isso o ciclo real é ``subprocess.run`` — abre a janela, toca os
gestos, salva, e o PROCESSO MORRE — e só então o teste, num processo NOVO,
relê do disco.

O corpo de prova (T1) é ``tests/fixtures/perfis_do_ciclo/``: os 34 perfis dela
(``reais/``, cópia literal de ``~/.config/hefesto-dualsense4unix/profiles/`` em
24/08/2026 — nenhum MAC real neles, porque nenhum tinha ``controllers``) mais
os 12 de fábrica (``fabrica/``, cópia de ``assets/profiles_default/``) mais
DOIS perfis FABRICADOS com override por controle (``z_fabricado_controllers_*``
— faixa sintética da casa, ``02:fe:``/``aa:bb:cc:``/``e8:47:3a:``), porque
nenhum dos 34 reais tem `controllers` para exercitar essa metade do ciclo.

O driver que faz o trabalho real é
``tests/fixtures/perfis_do_ciclo/_driver_ciclo_janela.py`` — leia o cabeçalho
dele antes de mexer aqui. Ele reusa ``_GESTOS``/``_janela`` de
``test_perfil_salva_tudo_ida_e_volta.py`` por decisão explícita da sprint
("reuse, não reescreva").

O QUE ESTE MÓDULO NÃO É: uma reconstrução do ``main.glade`` numa
``Gtk.OffscreenWindow`` com widgets de verdade. A sprint (T2) pede essa forma
como referência de veículo; o que este módulo prova é a mesma fronteira
(aba -> rascunho -> funil do rodapé -> disco) pelo caminho que
``test_perfil_salva_tudo_ida_e_volta.py`` já usa e mede — SOMADO ao ingrediente
que faltava (processo morto no meio). É uma redução de escopo deliberada,
registrada aqui e no relatório da leva, não escondida atrás de um nome que
prometa mais do que entrega.
"""

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

#: Um `pytest.param` por arquivo do corpo de prova inteiro (T1: 34 + 12 + 2).
_PERFIS_DO_CORPO_DE_PROVA: list[Any] = [
    pytest.param(caminho, id=f"{caminho.parent.name}/{caminho.stem}")
    for caminho in sorted((FIXTURES / "reais").glob("*.json"))
    + sorted((FIXTURES / "fabrica").glob("*.json"))
]


def _rodar_o_ciclo(perfil_json: Path, tmp_path: Path) -> dict[str, Any]:
    """Spawna o driver, MATA o processo ao terminar, devolve o que ele reportou.

    ``env`` isolado explicitamente — o subprocesso não herda o ambiente de
    quem chamou além do necessário para achar os módulos.
    """
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
        """Um "Salvar Perfil" com as sete abas mexidas sobrevive ao processo morto.

        MORDIDA (§2.1 da sprint, medida ANTES desta tarefa existir): contra
        ``aventura.json``/``corrida.json`` — os dois presets de fábrica com
        params de gatilho ANINHADOS — este ciclo reprovava com
        ``ValidationError`` nomeando o perfil e o campo ``params``, porque
        ``DraftConfig.from_profile`` não sabia abri-los. A cura é a T4
        (``draft_config.py``, ``_trigger_params_para_draft``); com ela
        presente, os 46 perfis do corpo de prova (T1) fecham o ciclo.
        """
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
        Profile.model_validate(relido)  # não lança


class TestAMordidaDaT4SemACura:
    """Prova, rodada AGORA, de que o ciclo REPROVAVA antes de T4/draft_config.py.

    Este teste não arranca a cura — arrancá-la aqui destruiria a proteção
    permanente contra a regressão dos dois presets de fábrica (é o trabalho da
    T4/T5, não deste arquivo). O que ele faz é reproduzir, na MESMA
    infraestrutura de subprocesso, a medição da seção 2.1 da sprint: os únicos
    dois perfis com params de gatilho aninhado batem no mesmo ponto de
    ``DraftConfig.from_profile`` que o ciclo completo usa — não há dois
    caminhos de leitura, um que o ciclo exercita e outro que a medição da §2.1
    exercitava.
    """

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
