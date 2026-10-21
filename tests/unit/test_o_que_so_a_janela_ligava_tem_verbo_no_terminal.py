"""O que só a janela ligava tem verbo no terminal (sprint de 09/10/2026).

Duas réguas: a de paridade (todo método do serviço que a janela chama tem um
chamador em `cli/` ou uma isenção com a razão) e a de cada verbo, com o cliente
do IPC dublado (o método e os parâmetros certos, e o prazo vencido dizendo
«confira com `status`», nunca «nada mudou»).
"""
from __future__ import annotations

import ast
import re
from pathlib import Path
from typing import Any

import pytest
from typer.testing import CliRunner

from hefesto_dualsense4unix.app import ipc_bridge
from hefesto_dualsense4unix.app.ipc_bridge import FRASE_DO_PRAZO_VENCIDO
from hefesto_dualsense4unix.cli.app import app
from hefesto_dualsense4unix.cli.ipc_client import IpcError

RAIZ = Path(ipc_bridge.__file__).resolve().parents[1]

_PELO_PERFIL = (
    "o efeito mora no perfil, e `profile apply --file` o leva inteiro "
    "(triggers, leds, rumble, controllers[uniq].sensores)"
)
_GESTO_DA_TELA = "gesto da tela, sem sentido fora dela"

#: Método que a janela chama e a linha de comando não, com a razão de cada um.
ISENTOS: dict[str, str] = {
    "trigger.set": _PELO_PERFIL + "; o instrumento é `test trigger`",
    "trigger.reset": _PELO_PERFIL,
    "rumble.set": _PELO_PERFIL + "; o instrumento é `test rumble`",
    "rumble.stop": _PELO_PERFIL,
    "rumble.motores.set": _PELO_PERFIL,
    "led.player_set": _PELO_PERFIL,
    "led.player_brightness_set": _PELO_PERFIL,
    "sensor.set": _PELO_PERFIL,
    "profile.reaplicar": "a reaplicação do perfil ativo é o `profile activate`",
    "motion.calibrate": _GESTO_DA_TELA + " (calibrar pede o controle parado, olhando a tela)",
    "mira.set": _GESTO_DA_TELA + " (a mira se ajusta olhando o alvo)",
    "haptica.testar": _GESTO_DA_TELA + " (o teste de háptica é um clique com resposta ao vivo)",
    "navegacao.interna.set": _GESTO_DA_TELA + " (a Navegação Interna é a da própria janela)",
    "navegacao.foco": _GESTO_DA_TELA + " (o pulso de foco de cada tique da janela)",
    "navegacao.big_picture.set": _GESTO_DA_TELA + " (a Navegação da Big Picture)",
    "desktop.arranjo.apply": _GESTO_DA_TELA + " (a área de trabalho se arranja na tela)",
    "desktop.status.set": _GESTO_DA_TELA + " (o aviso da área de trabalho)",
    "keyboard.emulation.set": _GESTO_DA_TELA + " (o teclado virtual da área de trabalho)",
    "daemon.emulation.suppress": "a janela suspende a emulação enquanto está em foco",
    "mouse.emulation.restore": "o par de `daemon.emulation.suppress`, da janela",
    "radio.busca.set": _GESTO_DA_TELA + " (a busca do rádio mostra o que achou)",
    "radio.dispensar": _GESTO_DA_TELA + " (dispensar um aparelho achado pela busca)",
    "radio.mover": _GESTO_DA_TELA + " (mover o controle de adaptador)",
    "radio.ponte.ligar_aqui": _GESTO_DA_TELA + " (a ponte do rádio escolhida na tela)",
    "identity.number.set": _GESTO_DA_TELA + " (o número do jogador no cartão do controle)",
    "machine.declare": _GESTO_DA_TELA + " (a declaração da máquina é um formulário)",
    "daemon.reload": "decidido: não existe `daemon reload` na linha de comando (cli.md)",
    "mods.agora": _GESTO_DA_TELA + " (a coluna «Agora» da janela da extensão); no terminal, "
                  "`mod listar` diz se cada uma está ligada",
    "mods.parar_tudo": _GESTO_DA_TELA + " (o «Parar tudo» da janela da extensão); no terminal, "
                       "`mod desligar <id>` para o processo dela",
    "mods.jogos": _GESTO_DA_TELA + " (os jogos da extensão na aba Lançadores)",
    "sequencia.gravar": _GESTO_DA_TELA + " (a gravação segue os toques com a aba Sequência "
                        "aberta, e o controle fica com ela enquanto grava)",
    "sequencia.tocar": _GESTO_DA_TELA + " (o «Tocar para ouvir» do editor da sequência)",
}

_METODO = re.compile(r"[a-z_]+(\.[a-z_]+)+")


def _metodos_do_servico() -> set[str]:
    arvore = ast.parse((RAIZ / "daemon" / "ipc_server.py").read_text(encoding="utf-8"))
    chaves: set[str] = set()
    for no in ast.walk(arvore):
        if isinstance(no, ast.Dict):
            for chave in no.keys:
                if (
                    isinstance(chave, ast.Constant)
                    and isinstance(chave.value, str)
                    and _METODO.fullmatch(chave.value)
                ):
                    chaves.add(chave.value)
    return chaves


def _usados_em(pastas: list[str], conhecidos: set[str]) -> set[str]:
    """Os métodos citados como literal de código (docstring não conta)."""
    achados: set[str] = set()
    for pasta in pastas:
        for caminho in (RAIZ / pasta).rglob("*.py"):
            arvore = ast.parse(caminho.read_text(encoding="utf-8"))
            docstrings = {
                id(no.value)
                for no in ast.walk(arvore)
                if isinstance(no, ast.Expr) and isinstance(no.value, ast.Constant)
            }
            for no in ast.walk(arvore):
                if (
                    isinstance(no, ast.Constant)
                    and isinstance(no.value, str)
                    and id(no) not in docstrings
                    and no.value in conhecidos
                ):
                    achados.add(no.value)
    return achados


def test_todo_metodo_da_janela_tem_verbo_ou_isencao_com_razao() -> None:
    servico = _metodos_do_servico()
    assert len(servico) > 40, "a leitura da tabela de métodos do serviço falhou"
    da_janela = _usados_em(["app", "interface"], servico)
    da_cli = _usados_em(["cli"], servico)
    sem_verbo = da_janela - da_cli
    faltam = sorted(sem_verbo - set(ISENTOS))
    assert not faltam, f"a janela chama e o terminal não alcança: {faltam}"
    sobra = sorted(m for m in ISENTOS if m not in sem_verbo)
    assert not sobra, f"isenção de método que já tem verbo (ou que não existe): {sobra}"
    assert all(len(razao) > 20 for razao in ISENTOS.values())


@pytest.mark.parametrize(
    "method",
    [
        "freestyle.set",
        "rumble.policy_set",
        "rumble.policy_custom",
        "rumble.passthrough",
        "mic.canal.set",
        "mic.volume.set",
        "gamepad.mask.set",
    ],
)
def test_os_sete_metodos_do_defeito_tem_chamador_na_linha_de_comando(method: str) -> None:
    assert method in _usados_em(["cli"], {method})


class _Cliente:
    """O `_run_call` dublado: guarda o que foi pedido e devolve o que mandarem."""

    def __init__(self, resposta: Any = None, erro: BaseException | None = None) -> None:
        self.resposta = resposta
        self.erro = erro
        self.chamadas: list[tuple[str, dict[str, Any], float | None]] = []

    def __call__(
        self, method: str, params: dict[str, Any] | None = None,
        timeout: float | None = None,
    ) -> Any:
        self.chamadas.append((method, dict(params or {}), timeout))
        if self.erro is not None:
            raise self.erro
        return self.resposta


def _com_cliente(monkeypatch: pytest.MonkeyPatch, **kw: Any) -> _Cliente:
    cliente = _Cliente(**kw)
    monkeypatch.setattr(ipc_bridge, "_run_call", cliente)
    return cliente


def _rodar(*args: str) -> Any:
    return CliRunner().invoke(app, list(args))


def _prazo_vencido() -> IpcError:
    erro = IpcError(-1, "conexão timeout")
    erro.__cause__ = TimeoutError()
    return erro


CASOS: list[tuple[list[str], str, dict[str, Any], dict[str, Any]]] = [
    (["freestyle", "on"], "freestyle.set", {"ligado": True},
     {"status": "ok", "freestyle_ligado": True}),
    (["freestyle", "off"], "freestyle.set", {"ligado": False},
     {"status": "ok", "freestyle_ligado": False}),
    (["freestyle", "status"], "daemon.status", {}, {"freestyle_ligado": True}),
    (["rumble", "policy", "economia"], "rumble.policy_set", {"policy": "economia"},
     {"status": "ok", "policy": "economia"}),
    (["rumble", "policy", "auto"], "rumble.policy_set", {"policy": "auto"},
     {"status": "ok", "policy": "auto"}),
    (["rumble", "policy", "custom", "0.7"], "rumble.policy_custom", {"mult": 0.7},
     {"status": "ok", "mult": 0.7}),
    (["rumble", "passthrough", "on"], "rumble.passthrough", {"enabled": True},
     {"status": "ok", "passthrough": True}),
    (["rumble", "passthrough", "on", "--uniq", "aa:bb:cc:00:00:01"],
     "rumble.passthrough", {"enabled": True, "uniq": "aa:bb:cc:00:00:01"},
     {"status": "ok", "passthrough": True}),
    (["mic", "canal", "on"], "mic.canal.set", {"ligado": True},
     {"status": "ok", "ligado": True}),
    (["mic", "canal", "off", "--uniq", "02:fe:00:00:00:02"], "mic.canal.set",
     {"ligado": False, "uniq": "02:fe:00:00:00:02"}, {"status": "ok", "ligado": False}),
    (["mic", "volume", "60"], "mic.volume.set", {"volume": 60},
     {"status": "ok", "volume": 60}),
    (["mic", "volume", "35", "--uniq", "02:fe:00:00:00:02"], "mic.volume.set",
     {"volume": 35, "uniq": "02:fe:00:00:00:02"}, {"status": "ok", "volume": 35}),
    (["gamepad", "mask", "xbox", "--uniq", "02:fe:00:00:00:03"], "gamepad.mask.set",
     {"uniq": "02:fe:00:00:00:03", "flavor": "xbox"},
     {"status": "ok", "flavor": "xbox", "gravado": True}),
    (["gamepad", "mask", "--limpar", "--uniq", "02:fe:00:00:00:03"], "gamepad.mask.set",
     {"uniq": "02:fe:00:00:00:03", "flavor": ""},
     {"status": "ok", "flavor": None, "gravado": True}),
]


@pytest.mark.parametrize(("argv", "method", "params", "resposta"), CASOS)
def test_o_verbo_manda_o_metodo_e_os_parametros_certos(
    monkeypatch: pytest.MonkeyPatch,
    argv: list[str], method: str, params: dict[str, Any], resposta: dict[str, Any],
) -> None:
    cliente = _com_cliente(monkeypatch, resposta=resposta)
    resultado = _rodar(*argv)
    assert resultado.exit_code == 0, resultado.output
    assert [(m, p) for m, p, _ in cliente.chamadas] == [(method, params)]
    assert "Traceback" not in resultado.output


@pytest.mark.parametrize(("argv", "method", "params", "resposta"), CASOS)
def test_o_verbo_espera_o_prazo_do_metodo(
    monkeypatch: pytest.MonkeyPatch,
    argv: list[str], method: str, params: dict[str, Any], resposta: dict[str, Any],
) -> None:
    cliente = _com_cliente(monkeypatch, resposta=resposta)
    _rodar(*argv)
    assert cliente.chamadas[0][2] == ipc_bridge.teto_da_linha_de_comando(method)


def test_o_ato_do_microfone_espera_o_que_a_janela_espera() -> None:
    assert ipc_bridge.teto_da_linha_de_comando("mic.canal.set") == 6.0
    assert ipc_bridge.teto_da_linha_de_comando("mic.volume.set") == 6.0
    assert ipc_bridge.teto_da_linha_de_comando("freestyle.set") >= 3.0


@pytest.mark.parametrize(("argv", "method", "params", "resposta"), CASOS)
def test_prazo_vencido_manda_conferir_com_status_e_nunca_diz_que_nada_mudou(
    monkeypatch: pytest.MonkeyPatch,
    argv: list[str], method: str, params: dict[str, Any], resposta: dict[str, Any],
) -> None:
    _com_cliente(monkeypatch, erro=_prazo_vencido())
    resultado = _rodar(*argv)
    assert resultado.exit_code == 2
    assert "sem resposta a tempo" in resultado.output
    assert "confira com" in resultado.output
    assert FRASE_DO_PRAZO_VENCIDO.split(";")[0] in resultado.output
    assert "nada mudou" not in resultado.output
    assert "Traceback" not in resultado.output


def test_servico_fora_do_ar_sai_com_3(monkeypatch: pytest.MonkeyPatch) -> None:
    _com_cliente(monkeypatch, erro=FileNotFoundError("socket"))
    resultado = _rodar("freestyle", "on")
    assert resultado.exit_code == 3
    assert "fora do ar" in resultado.output


def test_recusa_do_servico_diz_o_motivo_e_sai_com_2(monkeypatch: pytest.MonkeyPatch) -> None:
    _com_cliente(monkeypatch, erro=IpcError(-32602, "mult fora de [0.0, 2.0]: 9.0"))
    resultado = _rodar("rumble", "policy", "custom", "9")
    assert resultado.exit_code == 2
    assert "mult fora de" in resultado.output


def test_freestyle_que_o_servico_nao_ligou_sai_com_1(monkeypatch: pytest.MonkeyPatch) -> None:
    _com_cliente(monkeypatch, resposta={"status": "ok", "freestyle_ligado": False})
    resultado = _rodar("freestyle", "on")
    assert resultado.exit_code == 1


def test_microfone_incompleto_diz_o_motivo_e_sai_com_1(monkeypatch: pytest.MonkeyPatch) -> None:
    _com_cliente(
        monkeypatch,
        resposta={"status": "incompleto", "motivo": "o rádio não publica fonte"},
    )
    resultado = _rodar("mic", "canal", "on")
    assert resultado.exit_code == 1
    assert "o rádio não publica fonte" in resultado.output


def test_volume_sem_fonte_diz_que_nao_ha_fonte(monkeypatch: pytest.MonkeyPatch) -> None:
    _com_cliente(monkeypatch, resposta={"status": "sem_fonte", "fonte": None})
    resultado = _rodar("mic", "volume", "50")
    assert resultado.exit_code == 1
    assert "fonte de captura" in resultado.output


def test_mascara_que_o_aparelho_nao_vestiu_nao_e_anunciada(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    _com_cliente(
        monkeypatch,
        resposta={"status": "ok", "flavor": "nintendo", "motivo": "aparelho_nao_vestiu"},
    )
    resultado = _rodar("gamepad", "mask", "nintendo", "--uniq", "02:fe:00:00:00:03")
    assert resultado.exit_code == 1
    assert "não vestiu" in resultado.output


@pytest.mark.parametrize(
    "argv",
    [
        ["mic", "canal"],
        ["mic", "canal", "talvez"],
        ["mic", "volume"],
        ["mic", "volume", "101"],
        ["mic", "volume", "alto"],
        ["mic", "mute", "60"],
        ["rumble", "policy", "custom"],
        ["rumble", "policy", "max", "0.5"],
        ["rumble", "passthrough", "talvez"],
        ["gamepad", "mask", "--uniq", "02:fe:00:00:00:03"],
        ["gamepad", "mask", "xbox", "--limpar", "--uniq", "02:fe:00:00:00:03"],
    ],
)
def test_pedido_mal_formado_sai_com_2_sem_falar_com_o_servico(
    monkeypatch: pytest.MonkeyPatch, argv: list[str]
) -> None:
    cliente = _com_cliente(monkeypatch, resposta={"status": "ok"})
    resultado = _rodar(*argv)
    assert resultado.exit_code == 2, resultado.output
    assert cliente.chamadas == []
    assert "Traceback" not in resultado.output


def test_o_status_do_freestyle_diz_ligado(monkeypatch: pytest.MonkeyPatch) -> None:
    _com_cliente(monkeypatch, resposta={"freestyle_ligado": True})
    resultado = _rodar("freestyle", "status")
    assert resultado.exit_code == 0
    assert "Modo Freestyle: ligado" in resultado.output


def test_a_pagina_da_linha_de_comando_cita_os_verbos_novos() -> None:
    texto = (RAIZ.parents[1] / "docs" / "usage" / "cli.md").read_text(encoding="utf-8")
    for trecho in (
        "freestyle on", "rumble policy", "rumble passthrough",
        "mic canal", "mic volume", "gamepad mask",
    ):
        assert trecho in texto, trecho
