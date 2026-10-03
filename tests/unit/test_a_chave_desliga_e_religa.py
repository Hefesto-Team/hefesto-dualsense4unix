"""A régua da CHAVE — desligar um Hefesto por completo, e religar."""
from __future__ import annotations

import ast
import itertools
from pathlib import Path

from hefesto_dualsense4unix.utils import chave

RAIZ = Path(__file__).resolve().parents[2]


def _por_a_chave(config_dir: Path) -> Path:
    """Escreve a chave como o `hefesto-chave.sh` escreve."""
    alvo = chave.caminho_da_chave(config_dir)
    alvo.parent.mkdir(parents=True, exist_ok=True)
    alvo.write_text(
        "desligado em 2026-08-29T21:00:00-03:00 por hefesto-chave\n"
        "para religar:  hefesto-chave on\n",
        encoding="utf-8",
    )
    return alvo


def test_a_chave_ausente_nao_muda_nada(tmp_path):
    """O estado normal, e o que ele tem de custar: nada."""
    assert chave.motivo_do_desligamento(tmp_path) is None


def test_a_chave_posta_e_lida_e_a_retirada_some(tmp_path):
    alvo = _por_a_chave(tmp_path)
    assert chave.motivo_do_desligamento(tmp_path) is not None
    alvo.unlink()
    assert chave.motivo_do_desligamento(tmp_path) is None


def test_a_chave_diz_quando_e_como_desfazer(tmp_path):
    """O dia em que ela topar com este arquivo sem lembrar do contexto, a"""
    _por_a_chave(tmp_path)
    motivo = chave.motivo_do_desligamento(tmp_path)
    assert "desligado em" in motivo
    assert "para religar:" in motivo
    assert "hefesto-chave" in motivo


def test_chave_ilegivel_conta_como_desligado(tmp_path):
    """O estado seguro é RECUSAR."""
    alvo = chave.caminho_da_chave(tmp_path)
    alvo.mkdir(parents=True)
    motivo = chave.motivo_do_desligamento(tmp_path)
    assert motivo is not None
    assert "não pôde ser lida" in motivo


def test_a_chave_e_do_config_dir_e_nao_da_pasta_vizinha(tmp_path):
    """A chave desliga o app CUJO `config_dir` a guarda, e mais nada."""
    dele = tmp_path / "hefesto-dualsense4unix"
    vizinha = tmp_path / "outro-app-qualquer"
    dele.mkdir()
    vizinha.mkdir()
    _por_a_chave(dele)
    assert chave.motivo_do_desligamento(dele) is not None
    assert chave.motivo_do_desligamento(vizinha) is None


def test_o_recado_diz_o_que_por_que_e_o_que_fazer():
    """Regra desta casa para frase de diagnóstico. Sem as três partes, a"""
    texto = chave.recado_da_recusa("desligado em 2026-08-29 por hefesto-chave")
    assert "NÃO subiu" in texto
    assert "desligado pela chave" in texto
    assert "Para religar:" in texto


def test_o_daemon_consulta_a_chave_antes_de_tomar_o_aparelho():
    """A ORDEM é o teste, não a presença."""
    fonte = (
        RAIZ / "src" / "hefesto_dualsense4unix" / "daemon" / "main.py"
    ).read_text(encoding="utf-8")
    onde_a_chave = fonte.index("chave.motivo_do_desligamento()")
    onde_o_takeover = fonte.index("acquire_or_takeover(single_instance_name())")
    assert onde_a_chave < onde_o_takeover, (
        "a chave tem de ser consultada ANTES do takeover do aparelho"
    )


def _sobe_o_daemon_fora_do_systemd(fonte: str) -> list[int]:
    """Linhas de listas `[..., "daemon", "start", ...]`: o argv que sobe o daemon."""
    achadas: list[int] = []
    for no in ast.walk(ast.parse(fonte)):
        if not isinstance(no, ast.List):
            continue
        textos = [e.value for e in no.elts
                  if isinstance(e, ast.Constant) and isinstance(e.value, str)]
        if any(a == "daemon" and b == "start" for a, b in itertools.pairwise(textos)):
            achadas.append(no.lineno)
    return achadas


def test_nenhum_botao_sobe_o_daemon_fora_do_systemd():
    """O furo que a máscara não tapa: subir o daemon por `Popen`, sem a unit.

    Só o `daemon/main.py` consulta a chave. A régua mede que nenhum módulo
    fora do daemon e da CLI monte o argv `daemon start`: o painel sobe o
    serviço pelo `systemctl`, que a unit mascarada recusa.
    """
    raiz_src = RAIZ / "src" / "hefesto_dualsense4unix"
    for arquivo in sorted(raiz_src.rglob("*.py")):
        if arquivo.relative_to(raiz_src).parts[0] in ("daemon", "cli"):
            continue
        achadas = _sobe_o_daemon_fora_do_systemd(arquivo.read_text(encoding="utf-8"))
        assert not achadas, (
            f"{arquivo.relative_to(RAIZ)}:{achadas} sobe o daemon sem passar "
            "pelo systemd, e a chave não o alcança"
        )


def test_a_regua_do_popen_morde_o_argv_do_fallback_antigo():
    """O argv exato que o painel montava antes de sair o `Popen`."""
    antigo = (
        'cmd = [sys.executable, "-m", "hefesto_dualsense4unix",\n'
        '       "daemon", "start", "--foreground"]\n'
    )
    assert _sobe_o_daemon_fora_do_systemd(antigo) == [1]
    assert _sobe_o_daemon_fora_do_systemd('cmd = ["systemctl", "start", "x"]') == []


def test_o_script_da_chave_usa_os_nomes_de_unit_que_existem():
    """Conferidos na máquina dela em 29/08 com `systemctl --user"""
    script = (RAIZ / "scripts" / "hefesto-chave.sh").read_text(encoding="utf-8")
    for unit in (
        "hefesto-dualsense4unix.service",
        "hefesto-dualsense4unix-storm-watch.service",
        "hefesto-steam-input-guard.path",
        "hefesto-steam-input-guard.timer",
    ):
        assert unit in script, unit
    assert "hefesto-dualsense4unix-steam-input-guard" not in script


def test_a_chave_nao_toca_a_camada_da_maquina():
    """Regras udev, broker e bt-agent são da MÁQUINA, não do app."""
    script = (RAIZ / "scripts" / "hefesto-chave.sh").read_text(encoding="utf-8")
    linhas_de_acao = [
        linha for linha in script.splitlines()
        if ("systemctl" in linha or "rm " in linha)
        and not linha.lstrip().startswith("#")
    ]
    proibidos = ("hidraw-broker", "bt-agent", "bt-health-watchdog",
                 "bt-bonds-snapshot", "udev")
    for linha in linhas_de_acao:
        if "is-active" in linha:
            continue
        for proibido in proibidos:
            assert proibido not in linha, linha


def test_a_chave_nao_mata_por_pgrep():
    """`pgrep -f hefesto` alcançaria este próprio script, e o mataria."""
    script = (RAIZ / "scripts" / "hefesto-chave.sh").read_text(encoding="utf-8")
    acoes = [
        linha for linha in script.splitlines()
        if not linha.lstrip().startswith("#")
    ]
    assert not any("pgrep" in linha for linha in acoes)
    assert not any("pkill" in linha for linha in acoes)
    assert ".pid" in script


def test_o_script_e_o_produto_concordam_no_nome_do_arquivo():
    """Um escritor (o script, em bash) e um leitor (o produto, em Python)."""
    script = (RAIZ / "scripts" / "hefesto-chave.sh").read_text(encoding="utf-8")
    assert chave.NOME_DO_ARQUIVO in script
    assert script.count(chave.NOME_DO_ARQUIVO) >= 3
