"""A régua do portão e a legenda da tela têm de ser a MESMA peça.

P-01 da PAREAMENTO-01 escreveu essa regra para o VOCABULÁRIO — o gerador
importa ``DOMINIO_POR_SUFIXO`` e ``ESCADA`` do portão que já é dono deles, em
vez de redigitar, porque *"régua e legenda divergirem quer dizer publicar uma
página que descreve um domínio diferente do que o portão aceita"*.

Este arquivo prova que ela vale igual para o **FORMATO**. Até 25/08/2026
``valida_numeros`` (``scripts/validar-fala-de-tela.py``) trazia a própria
cópia de ``f"{v:.1f}".replace(".", ",")``, e era a QUARTA da árvore. Com a
cópia, mudar ``app/fala_do_mapa.formata_pt_br`` para duas casas deixava o
portão conferindo UMA casa: ele seguiria verde sobre uma divergência entre a
constante medida e a célula do mapa — exatamente o que ele existe para pegar.

A MORDIDA É DESTRUTIVA E MEDE O QUE PROMETE
--------------------------------------------
Não basta afirmar que a cópia sumiu do texto do roteiro: uma quinta cópia
escrita de outro jeito (``format()``, ``locale``, ``str.translate``) passaria
por essa régua. Aqui o teste TROCA ``formata_pt_br`` na árvore de mentira e
exige que o portão mude de veredito junto. Se o portão tiver qualquer cópia
própria, ``test_o_portao_segue_o_formato_da_tela_e_nao_o_seu`` reprova.
"""
from __future__ import annotations

import csv
import subprocess
import sys
from pathlib import Path

RAIZ_REAL = Path(__file__).resolve().parents[2]
SCRIPT = RAIZ_REAL / "scripts" / "validar-fala-de-tela.py"
FALA_DO_MAPA_REAL = RAIZ_REAL / "src" / "hefesto_dualsense4unix" / "app" / "fala_do_mapa.py"

#: A linha exata de ``app/fala_do_mapa.py`` que este teste troca. Se ela mudar
#: de forma, a troca não casa e ``_com_formato`` FALHA em voz alta em vez de
#: rodar uma mordida que não morde.
_FORMATO_DE_UMA_CASA = 'return f"{valor:.1f}".replace(".", ",")'

RADIO_DA_MESA_MENTIROSA = '''\
"""radio_da_mesa.py de MENTIRA — só para teste."""
from __future__ import annotations

HZ_INPUT_SEM_MIC = 260.4

NUMEROS_MEDIDOS_NO_MAPA: tuple[tuple[str, float, str, str], ...] = (
    ("HZ_INPUT_SEM_MIC", HZ_INPUT_SEM_MIC, "audio.microfone@dualsense", "radio_ressalva"),
)
'''


def _com_formato(casas: int) -> str:
    """O ``fala_do_mapa.py`` real, com ``formata_pt_br`` em `casas` decimais."""
    fonte = FALA_DO_MAPA_REAL.read_text(encoding="utf-8")
    assert fonte.count(_FORMATO_DE_UMA_CASA) == 1, (
        f"{_FORMATO_DE_UMA_CASA!r} não está mais em fala_do_mapa.py como uma "
        "linha só: sem ela esta mordida rodaria sem trocar nada e passaria "
        "sempre"
    )
    novo = f'return f"{{valor:.{casas}f}}".replace(".", ",")'
    return fonte.replace(_FORMATO_DE_UMA_CASA, novo)


def monta_arvore(tmp_path: Path, *, casas: int, ressalva: str) -> Path:
    app = tmp_path / "src" / "hefesto_dualsense4unix" / "app"
    integracoes = tmp_path / "src" / "hefesto_dualsense4unix" / "integrations"
    app.mkdir(parents=True, exist_ok=True)
    integracoes.mkdir(parents=True, exist_ok=True)
    (app / "fala_do_mapa.py").write_text(_com_formato(casas), encoding="utf-8")
    (app / "fatos_do_mapa.py").write_text(
        '"""de mentira."""\nfrom __future__ import annotations\n'
        "from typing import Final\nFATOS: Final[dict] = {}\n",
        encoding="utf-8",
    )
    (integracoes / "radio_da_mesa.py").write_text(RADIO_DA_MESA_MENTIROSA, encoding="utf-8")
    dados = tmp_path / "docs" / "data"
    dados.mkdir(parents=True, exist_ok=True)
    with (dados / "mapa-controles.csv").open("w", encoding="utf-8", newline="") as arquivo:
        escritor = csv.DictWriter(arquivo, fieldnames=["id", "radio_ressalva"])
        escritor.writeheader()
        escritor.writerow({"id": "audio.microfone@dualsense", "radio_ressalva": ressalva})
    return tmp_path


def _roda(raiz: Path) -> subprocess.CompletedProcess[str]:
    return subprocess.run(
        [sys.executable, str(SCRIPT), "--raiz", str(raiz), "--all"],
        capture_output=True,
        text=True,
        check=False,
    )


def test_uma_casa_e_a_celula_de_uma_casa_passa(tmp_path: Path) -> None:
    """O caso de hoje, para a mordida abaixo ter contra o que ser lida."""
    raiz = monta_arvore(tmp_path, casas=1, ressalva="mic desligado 260,4 Hz de input")
    processo = _roda(raiz)
    assert processo.returncode == 0, processo.stdout


def test_o_portao_segue_o_formato_da_tela_e_nao_o_seu(tmp_path: Path) -> None:
    """A MORDIDA: `formata_pt_br` vira duas casas, e o portão tem de virar junto.

    A célula segue dizendo ``260,4``, que era o que a tela escrevia ontem. Com
    a tela escrevendo ``260,40``, a célula ficou para trás — e é isso que o
    portão existe para dizer. Um portão com cópia própria de uma casa seguiria
    verde aqui, calado sobre a divergência.
    """
    raiz = monta_arvore(tmp_path, casas=2, ressalva="mic desligado 260,4 Hz de input")
    processo = _roda(raiz)
    assert processo.returncode == 1, processo.stdout
    assert "260,40" in processo.stdout, processo.stdout
    assert "HZ_INPUT_SEM_MIC" in processo.stdout, processo.stdout


def test_duas_casas_com_a_celula_atualizada_passa(tmp_path: Path) -> None:
    """O outro lado da mordida: acompanhar a tela devolve o verde.

    Sem este, `test_o_portao_segue_o_formato_da_tela_e_nao_o_seu` passaria
    também num portão que simplesmente reprova tudo.
    """
    raiz = monta_arvore(tmp_path, casas=2, ressalva="mic desligado 260,40 Hz de input")
    processo = _roda(raiz)
    assert processo.returncode == 0, processo.stdout
