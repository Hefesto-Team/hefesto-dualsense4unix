"""O que a MOVER, a GOVERNADOR-02 e a ENTRADA deixaram entre si — A-COSTURA-DA-ONDA-2-01."""

from __future__ import annotations

from pathlib import Path
from typing import Any

import pytest

from hefesto_dualsense4unix.integrations import bluez_dbus as bd
from hefesto_dualsense4unix.integrations import diario_do_radio

RAIZ = Path(__file__).resolve().parents[2]


@pytest.fixture()
def diario(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> Path:
    """A trava e o diário numa pasta de teste — nunca os dela, em ``/run``."""
    monkeypatch.setenv(diario_do_radio.ENV_TRAVA, str(tmp_path / "radio.lock"))
    caminho = tmp_path / "radio-diario.jsonl"
    monkeypatch.setenv(diario_do_radio.ENV_DIARIO, str(caminho))
    return caminho


def _handlers(daemon: Any) -> Any:
    from hefesto_dualsense4unix.daemon.ipc_handlers import IpcHandlersMixin

    class _Handlers(IpcHandlersMixin):
        def __init__(self, alvo: Any) -> None:
            self.daemon = alvo

    return _Handlers(daemon)


def _chaves(no: Any, nome: str) -> list[Any]:
    """Todo valor da chave ``nome``, em qualquer fundura do publicado."""
    achados: list[Any] = []
    if isinstance(no, dict):
        for chave, valor in no.items():
            if chave == nome:
                achados.append(valor)
            achados.extend(_chaves(valor, nome))
    elif isinstance(no, list):
        for item in no:
            achados.extend(_chaves(item, nome))
    return achados


def _daemon_de_mentira() -> Any:
    """O ``Daemon`` de verdade, com o controle de mentira e nada ligado."""
    from hefesto_dualsense4unix.core.controller import ControllerState
    from hefesto_dualsense4unix.core.events import EventBus
    from hefesto_dualsense4unix.daemon.lifecycle import Daemon, DaemonConfig
    from hefesto_dualsense4unix.testing.fake_controller import FakeController

    estado = ControllerState(
        battery_pct=80, l2_raw=0, r2_raw=0, connected=True, transport="usb"
    )
    return Daemon(
        controller=FakeController(transport="usb", states=[estado]),
        bus=EventBus(),
        config=DaemonConfig(
            poll_hz=120,
            auto_reconnect=False,
            ipc_enabled=False,
            udp_enabled=False,
            autoswitch_enabled=False,
            mouse_emulation_enabled=False,
            keyboard_emulation_enabled=False,
            mic_button_toggles_system=False,
            plugins_enabled=False,
        ),
    )


def _esperar(condicao: Any, teto: float = 5.0) -> bool:
    import time

    fim = time.monotonic() + teto
    while time.monotonic() < fim:
        if condicao():
            return True
        time.sleep(0.01)
    return bool(condicao())


ADAPTADOR_A = "aa:bb:cc:00:00:a1"
ADAPTADOR_B = "aa:bb:cc:00:00:b2"
ADAPTADOR_C = "aa:bb:cc:00:00:c3"
CONTROLE_1 = "aa:bb:cc:00:00:01"
CONTROLE_2 = "aa:bb:cc:00:00:02"
CONTROLE_3 = "aa:bb:cc:00:00:03"
CONTROLE_4 = "aa:bb:cc:00:00:04"
CONTROLE_5 = "aa:bb:cc:00:00:05"
CONTROLE_6 = "aa:bb:cc:00:00:06"


class _Relogio:
    def __init__(self) -> None:
        self.agora = 100.0

    def __call__(self) -> float:
        return self.agora


class _Diario:
    def __init__(self) -> None:
        self.entradas: list[dict[str, Any]] = []

    def __call__(self, quem: str, o_que: str, por_que: str, **campos: Any) -> None:
        self.entradas.append({"quem": quem, "o_que": o_que, "por_que": por_que, **campos})


class _MedidorDaMesa:
    """O ar dos três adaptadores, com os enlaces ACL que o kernel lista em cada um."""

    def __init__(self, enlaces: dict[str, tuple[str, ...]]) -> None:
        self.enlaces = enlaces

    def amostrar(self) -> dict[str, Any]:
        from hefesto_dualsense4unix.integrations import ar_do_adaptador as ar

        return {
            endereco: ar.ArDoAdaptador(
                hci=numero,
                endereco=endereco,
                conexoes=tuple(
                    ar.Enlace(handle=i + 1, endereco=u, tipo=ar.TIPO_ACL, saida=False,
                              estado=1, link_mode=0)
                    for i, u in enumerate(self.enlaces.get(endereco, ()))
                ),
                janela_s=0.25,
            )
            for numero, endereco in enumerate((ADAPTADOR_A, ADAPTADOR_B, ADAPTADOR_C))
        }


class _DonoDoNome:
    """O ``entrada_a_entrada.nome_da_porta`` de mentira: responde «Sala» e anota."""

    def __init__(self, nomes: dict[str, str]) -> None:
        self.nomes = nomes
        self.perguntas: list[str] = []

    def __call__(self, chave: str, **_k: Any) -> str | None:
        self.perguntas.append(chave)
        return self.nomes.get(chave)


def test_o_governador_pergunta_o_nome_ao_dono_da_entrada(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """A frase da recusa diz o nome que o DONO diz — o que ela deu à porta."""
    from hefesto_dualsense4unix.daemon.subsystems import governador_do_radio as gov
    from hefesto_dualsense4unix.integrations import ar_do_adaptador as ar
    from hefesto_dualsense4unix.integrations import entrada_a_entrada as ee
    from hefesto_dualsense4unix.integrations import mesa_de_radio

    dono_do_nome = _DonoDoNome({"3-4.1.4": "Sala"})
    monkeypatch.setattr(ee, "nome_da_porta", dono_do_nome)
    monkeypatch.setattr(bd, "a_suite_esta_rodando", lambda: False)
    monkeypatch.setattr(bd, "enderecos_pelo_kernel", lambda *_a, **_k: {})
    monkeypatch.setattr(
        mesa_de_radio,
        "adaptadores_bluetooth",
        lambda **_k: [
            mesa_de_radio.Adaptador(interface="hci3", no="/x/3-4.1.4", busnum=3, devpath="4.1.4"),
            mesa_de_radio.Adaptador(interface="hci4", no="/x/3-1.4", busnum=3, devpath="1.4"),
        ],
    )
    amostra = {
        ADAPTADOR_A: ar.ArDoAdaptador(hci=3, endereco=ADAPTADOR_A),
        ADAPTADOR_B: ar.ArDoAdaptador(hci=4, endereco=ADAPTADOR_B),
    }

    assert gov.nome_da_porta(ADAPTADOR_A, amostra=amostra) == "Sala"
    assert gov.nome_da_porta(ADAPTADOR_B, amostra=amostra) == ""
    assert dono_do_nome.perguntas == ["3-4.1.4", "3-1.4"]

    recusa = gov.Recusa(
        CONTROLE_3, ADAPTADOR_A, "som", gov.MOTIVO_CHEIO, (ADAPTADOR_B,),
        nomear=lambda e: gov.nome_da_porta(e, amostra=amostra),
    )
    assert recusa.frase == (
        "A entrada Sala já tem 2 controles com som ou vibração. Há vaga em outro adaptador."
    )


#: ``utils/rotulo_da_entrada.py``, só stdlib, para as ordens compor dali sem o
_O_DONO = "utils/rotulo_da_entrada.py"
_OS_QUE_PODEM = {
    # fica: é o dono da palavra, e as duas entradas dele são a regra
    (_O_DONO, "define a palavra"): "é o dono (D-2609-O-NOME-E-DA-POSICAO)",
    (_O_DONO, "compõe com a palavra"): "é o dono (D-2609-O-NOME-E-DA-POSICAO)",
    # sai com: A-TELA-SEM-O-QUE-A-REGUA-ACEITA-01 (a cópia da palavra é um segundo dono)
    ("interface/calibracao_das_entradas.py", "define a palavra"): (
        "a cópia que o gerador da aba 08 lê por AST — não importa do dono sem "
        "quebrar o gerador; travada junto por test_entrada_a_entrada_grava.py"
    ),
    ("integrations/arranjo_da_mesa.py", "compõe uma f-string"): (
        "o porte do motor medido contra o ouro (`tests/fixtures/motor_do_arranjo_"
        "do_mockup.js`); a página do mapa tem o motor dela, que já pergunta ao "
        "dono (`naFraseDe`). CHEGA À TELA por um caminho só, o desenho do "
        "gabinete da tela «Mapear Entradas» da aba 08 (`a08_conexoes."
        "_html_do_mapa` → `mapa_da_mesa.veredito_do_quadrado` → `julgar`, o "
        "«colada no …, na entrada N»): o arquivo e o `app/widgets/` são "
        "`nao_toca` da O-MAPA-QUE-ELA-CORRIGE-01 — dívida declarada na conferência"
    ),
    ("integrations/arranjo_da_mesa.py", "tem um modelo de .format"): (
        "o mesmo porte do motor, pela mesma razão"
    ),
    ("interface/aba08.py", "tem um modelo de .format"): (
        "o gerador do desenho aprovado da aba 08, fora da posse da "
        "O-MAPA-QUE-ELA-CORRIGE-01 (a sprint manda parar e avisar): o contador "
        "da calibração e as frases do desenho — dívida declarada no relatório"
    ),
    # fica: o contador conta passos, e a mensagem do esquema cita o valor recusado
    ("interface/pacotes/a08_conexoes.py", "compõe uma f-string"): (
        "o contador da calibração («entrada 3 de 7») conta PASSOS, não nomeia uma "
        "entrada; as recusas da aba perguntam ao dono (`_a_entrada_na_frase`)"
    ),
    ("utils/maquina.py", "compõe uma f-string"): (
        "as mensagens de validação do schema citam o VALOR recusado («número de "
        "entrada '1234'»), não nomeiam uma entrada para a tela"
    ),
}


def _composicoes_da_palavra(raiz: Path) -> set[tuple[str, str]]:
    """``(arquivo, forma)`` de toda string de CÓDIGO que junta «Entrada» a um valor."""
    import ast
    import itertools
    import re

    palavra_no_fim = re.compile(r"\bEntrada\s*$", re.IGNORECASE)
    achados: set[tuple[str, str]] = set()
    for arquivo in sorted(raiz.rglob("*.py")):
        arvore = ast.parse(arquivo.read_text(encoding="utf-8"))
        docstrings = {
            id(no.body[0].value)
            for no in ast.walk(arvore)
            if isinstance(no, (ast.Module, ast.ClassDef, ast.FunctionDef, ast.AsyncFunctionDef))
            and no.body
            and isinstance(no.body[0], ast.Expr)
            and isinstance(no.body[0].value, ast.Constant)
        }
        nome = str(arquivo.relative_to(raiz))
        for no in ast.walk(arvore):
            if isinstance(no, ast.JoinedStr):
                partes = no.values
                for atual, seguinte in itertools.pairwise(partes):
                    if (
                        isinstance(atual, ast.Constant)
                        and isinstance(atual.value, str)
                        and palavra_no_fim.search(atual.value)
                        and isinstance(seguinte, ast.FormattedValue)
                    ):
                        achados.add((nome, "compõe uma f-string"))
                if any(
                    isinstance(p, ast.FormattedValue)
                    and isinstance(p.value, ast.Name)
                    and p.value.id == "PALAVRA_DA_ENTRADA"
                    for p in partes
                ):
                    achados.add((nome, "compõe com a palavra"))
            elif (
                isinstance(no, ast.Constant)
                and isinstance(no.value, str)
                and id(no) not in docstrings
                and re.search(r"\bEntrada \{", no.value, re.IGNORECASE)
            ):
                achados.add((nome, "tem um modelo de .format"))
            elif (
                isinstance(no, ast.BinOp)
                and isinstance(no.op, ast.Add)
                and isinstance(no.left, ast.Constant)
                and isinstance(no.left.value, str)
                and palavra_no_fim.search(no.left.value)
            ):
                achados.add((nome, "compõe por soma"))
            elif isinstance(no, (ast.Assign, ast.AnnAssign)):
                alvos = no.targets if isinstance(no, ast.Assign) else [no.target]
                if any(isinstance(a, ast.Name) and a.id == "PALAVRA_DA_ENTRADA" for a in alvos):
                    achados.add((nome, "define a palavra"))
    return achados


def test_o_nome_da_porta_tem_um_dono_so() -> None:
    """Um dono do nome da porta: o da ENTRADA. Havia três compositores — o"""
    achados = _composicoes_da_palavra(RAIZ / "src" / "hefesto_dualsense4unix")
    intrusos = sorted(achados - set(_OS_QUE_PODEM))
    caducos = sorted(set(_OS_QUE_PODEM) - achados)
    assert not intrusos, f"um segundo dono do nome da porta: {intrusos}"
    assert not caducos, f"a exceção deixou de existir — tire-a de _OS_QUE_PODEM: {caducos}"
