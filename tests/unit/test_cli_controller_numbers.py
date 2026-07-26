"""PLAYER-LED-01 (entrega 5) — `controller numbers`, o diagnóstico honesto.

O comando existe porque, com quatro controles na mesa, era IMPOSSÍVEL
distinguir a olho os quatro números em jogo: o nosso, o do jogo, o do kernel e
o padrão aceso. A tabela de padrões do `hid-playstation` é IDÊNTICA à nossa em
1..4, então o LED aceso não identifica quem o escreveu — e foi exatamente essa
leitura que produziu uma conclusão errada durante a investigação de 25/07.

Os testes aqui travam as três coisas que fazem o comando ser honesto:

1. cada coluna declara a procedência (nosso x jogo x sysfs x kernel);
2. a ordem do barramento HID é lida pelo CONTADOR HEXADECIMAL, nunca pelo nome
   — o nome começa pelo barramento (`0003:` USB antes de `0005:` BT) e mente
   sobre a cronologia (segundo erro de análise da mesma noite);
3. o aviso sobre `/sys/class/leds` sai em TODA execução, não escondido atrás
   de uma opção.
"""
from __future__ import annotations

import json
from pathlib import Path
from typing import Any

import pytest
from typer.testing import CliRunner

from hefesto_dualsense4unix.cli import cmd_controller
from hefesto_dualsense4unix.cli.app import app

runner = CliRunner()

UNIQ_1 = "aabbcc000001"
UNIQ_2 = "aabbcc000002"
P1 = [False, False, True, False, False]
P4 = [True, True, False, True, True]


@pytest.fixture
def mock_ipc(monkeypatch: pytest.MonkeyPatch) -> dict[str, Any]:
    registry: dict[str, Any] = {"calls": [], "response": {}}

    def fake_run_call(
        method: str, params: dict[str, Any] | None = None, timeout: float | None = None
    ) -> Any:
        registry["calls"].append((method, dict(params or {})))
        return registry["response"]

    import hefesto_dualsense4unix.app.ipc_bridge as bridge

    monkeypatch.setattr(bridge, "_run_call", fake_run_call)
    return registry


def _state(**extra: Any) -> dict[str, Any]:
    controle: dict[str, Any] = {
        "index": 0,
        "connected": True,
        "transport": "usb",
        "uniq": UNIQ_1,
        "player_slot": 1,
        "player": 1,
        "player_leds_game": P4,
        "game_output_retido": ["led"],
    }
    controle.update(extra)
    return {
        "controllers": [controle],
        "game_signal": {"authority": "daemon"},
    }


class TestColunasDeclaramProcedencia:
    def test_json_separa_nosso_numero_do_numero_do_jogo(
        self, mock_ipc: dict[str, Any], monkeypatch: pytest.MonkeyPatch
    ) -> None:
        monkeypatch.setattr(cmd_controller, "_padroes_acesos", lambda: {UNIQ_1: (True,) * 5})
        monkeypatch.setattr(cmd_controller, "_numeros_do_kernel", lambda: {UNIQ_1: 3})
        mock_ipc["response"] = _state()

        result = runner.invoke(app, ["controller", "numbers", "--json"])

        assert result.exit_code == 0, result.output
        dados = json.loads(result.output)
        (linha,) = dados["controles"]
        assert linha["nosso_numero"] == 1
        assert linha["numero_do_jogo"] == "4"
        assert linha["retido_pelo_gate"] == ["led"]
        assert linha["numero_do_kernel_inferido"] == 3
        assert linha["padrao_aceso_sysfs"] == [True] * 5

    def test_sem_camada_de_jogo_o_numero_do_jogo_e_none_nao_zero(
        self, mock_ipc: dict[str, Any], monkeypatch: pytest.MonkeyPatch
    ) -> None:
        """"O jogo não escreveu" é diferente de "o jogo escreveu apagado" — a
        interface admite em vez de inventar."""
        monkeypatch.setattr(cmd_controller, "_padroes_acesos", dict)
        monkeypatch.setattr(cmd_controller, "_numeros_do_kernel", dict)
        mock_ipc["response"] = _state(player_leds_game=None, game_output_retido=[])

        result = runner.invoke(app, ["controller", "numbers", "--json"])

        dados = json.loads(result.output)
        (linha,) = dados["controles"]
        assert linha["numero_do_jogo"] is None
        assert linha["padrao_aceso_sysfs"] is None

    def test_o_aviso_do_sysfs_sai_sempre(
        self, mock_ipc: dict[str, Any], monkeypatch: pytest.MonkeyPatch
    ) -> None:
        """Falha-sem: sem o aviso impresso, quem lê a coluna do sysfs conclui
        autoria a partir de um padrão que é ambíguo por construção."""
        monkeypatch.setattr(cmd_controller, "_padroes_acesos", dict)
        monkeypatch.setattr(cmd_controller, "_numeros_do_kernel", dict)
        mock_ipc["response"] = _state()

        result = runner.invoke(app, ["controller", "numbers"])

        assert result.exit_code == 0, result.output
        texto = result.output.replace("\n", " ")
        assert "identifica quem o escreveu" in texto

    def test_o_padrao_e_traduzido_pela_tabela_nao_contando_leds(self) -> None:
        """No DualSense o jogador 1 acende o LED do MEIO. Contar LEDs acesos
        (ou usar a posição do único aceso) diria "3" para o jogador 1 — que é
        a mesma classe de erro que a leitura crua do sysfs produziu."""
        assert cmd_controller._numero_do_padrao(P1) == "1"
        assert cmd_controller._numero_do_padrao(P4) == "4"

    def test_padrao_fora_da_tabela_nao_vira_numero_inventado(self) -> None:
        aceso, apagado = chr(0x25CF), chr(0x25CB)
        assert cmd_controller._numero_do_padrao([True, False, False, False, False]) == (
            aceso + apagado * 4
        )
        assert cmd_controller._numero_do_padrao(None) == "—"

    def test_o_desenho_nao_pode_virar_string_vazia(self) -> None:
        """Regressão do ADR-011, e desta vez com um culpado com nome.

        No commit `d1177c2` o higienizador de emojis do fluxo de commit apagou
        BLACK CIRCLE e WHITE CIRCLE do código E do valor esperado do teste
        acima: `_padrao` passou a devolver `""` para qualquer entrada e a suíte
        continuou verde, porque o assert virou `== ""`. O ADR-011 já registrava
        esse mesmo modo de falha de 21/04/2026.

        Este teste não compara com literal nenhum — ele cobra as PROPRIEDADES
        que qualquer apagamento de glifo quebra: cinco posições, e aceso
        diferente de apagado. Um higienizador que esvazie os dois lados derruba
        aqui, mesmo que esvazie o teste anterior junto.
        """
        desenho = cmd_controller._padrao([True, False, False, False, False])
        assert len(desenho) == 5, f"esperava 5 posições, veio {desenho!r}"
        assert len(set(desenho)) == 2, f"aceso e apagado colidiram: {desenho!r}"
        assert desenho.strip() != "", "o desenho não pode ser espaço nem vazio"


class TestOrdemDoBarramentoHid:
    """Regra de método de 25/07: ordenar `/sys/bus/hid/devices` pelo CONTADOR
    hexadecimal, nunca pelo nome."""

    def _arvore(self, tmp_path: Path, nomes: dict[str, str]) -> Path:
        raiz = tmp_path / "hid"
        raiz.mkdir()
        drivers = tmp_path / "drivers" / "playstation"
        drivers.mkdir(parents=True)
        for nome, uniq in nomes.items():
            dev = raiz / nome
            dev.mkdir()
            (dev / "driver").symlink_to(drivers)
            (dev / "uevent").write_text(f"HID_UNIQ={uniq}\n", encoding="utf-8")
        return raiz

    def test_ordena_pelo_contador_e_nao_pelo_nome(
        self, tmp_path: Path, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        """Falha-sem: por NOME, o `0003:` (USB) viria antes do `0005:` (BT) e a
        numeração inferida sairia invertida — a conclusão confiante e falsa que
        a sessão de 25/07 quase transformou em desenho."""
        raiz = self._arvore(
            tmp_path,
            {
                "0005:054C:0CE6.000E": "AA:BB:CC:00:00:02",  # chegou primeiro
                "0003:054C:0CE6.0015": "AA:BB:CC:00:00:01",  # chegou depois
            },
        )
        monkeypatch.setattr(cmd_controller, "_HID_BUS_ROOT", str(raiz))

        assert cmd_controller._numeros_do_kernel() == {UNIQ_2: 1, UNIQ_1: 2}

    def test_ignora_dispositivo_de_outro_driver(
        self, tmp_path: Path, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        raiz = self._arvore(tmp_path, {"0003:054C:0CE6.0007": "AA:BB:CC:00:00:01"})
        outro_driver = tmp_path / "drivers" / "hid-generic"
        outro_driver.mkdir(parents=True)
        intruso = raiz / "0003:057E:2009.0002"
        intruso.mkdir()
        (intruso / "driver").symlink_to(outro_driver)
        (intruso / "uevent").write_text("HID_UNIQ=AA:BB:CC:00:00:09\n", encoding="utf-8")
        monkeypatch.setattr(cmd_controller, "_HID_BUS_ROOT", str(raiz))

        assert cmd_controller._numeros_do_kernel() == {UNIQ_1: 1}

    def test_conta_o_vpad_junto_com_os_fisicos(
        self, tmp_path: Path, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        """O contador do kernel aloca o menor identificador livre contando
        FÍSICOS E VIRTUAIS juntos — é por isso que o número do sysfs pode não
        ser nem o nosso nem o do jogo."""
        raiz = self._arvore(
            tmp_path,
            {
                "0003:054C:0DF2.0007": "02:FE:00:00:00:01",  # nosso vpad
                "0003:054C:0CE6.0009": "AA:BB:CC:00:00:01",
            },
        )
        monkeypatch.setattr(cmd_controller, "_HID_BUS_ROOT", str(raiz))

        ordem = cmd_controller._hid_devices_por_ordem_de_registro()

        assert [nosso for _nome, _uniq, nosso in ordem] == [True, False]
        assert cmd_controller._numeros_do_kernel()[UNIQ_1] == 2

    def test_sem_barramento_devolve_vazio_sem_estourar(
        self, tmp_path: Path, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        monkeypatch.setattr(cmd_controller, "_HID_BUS_ROOT", str(tmp_path / "nao-existe"))
        assert cmd_controller._numeros_do_kernel() == {}
