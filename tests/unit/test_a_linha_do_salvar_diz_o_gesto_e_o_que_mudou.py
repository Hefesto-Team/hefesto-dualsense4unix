"""A linha do «salvar» diz o gesto e o que mudou, e o histórico cobre uma semana.

A-LINHA-DO-SALVAR-DIZ-O-GESTO-E-O-QUE-MUDOU-01. O `profile_salvo` não dizia o
conteúdo da mudança nem o gesto: o brilho de um controle foi de 0,49 a 0,08 em
88 gravações e o diário não fechou quem foi. Os esperados abaixo são escritos à
mão, nunca tirados da saída da função.

MORDIDAS (cada uma foi feita e viu reprovar):

* tirar a máscara de `_o_que_mudou` -> o endereço inteiro aparece na linha;
* tirar o cálculo de `_o_que_mudou` -> `mudou` vazio;
* tirar a descida da seção que nasce ou some inteira -> `mudou=controllers`;
* arrancar o `gesto_de_agora.get()` do `_registrar_gravacao` -> `gesto` vazio;
* arrancar o `gesto_de_agora.set` do `_dispatch` ou do `trabalhar` -> a régua de AST;
* tirar o `sha_antes` (ou calculá-lo do payload) -> a corrente não acusa quem
  escreveu de fora;
* devolver só `HISTORICO_MAX_VERSOES` (sem a semana) -> a semana some;
* arrancar a comparação do `save_profile` -> cinco versões iguais.
"""
from __future__ import annotations

import ast
import asyncio
import json
from pathlib import Path

import pytest

from hefesto_dualsense4unix.daemon.ipc_server import IpcServer
from hefesto_dualsense4unix.daemon.state_store import StateStore
from hefesto_dualsense4unix.profiles import loader as loader_module
from hefesto_dualsense4unix.profiles.loader import (
    gesto_de_agora,
    listar_historico,
    save_profile,
)
from hefesto_dualsense4unix.profiles.schema import (
    ControllerOverrides,
    LedsConfig,
    MatchCriteria,
    Profile,
)

RAIZ = Path(__file__).resolve().parents[2] / "src" / "hefesto_dualsense4unix"

# Faixa forjada (aa:bb:cc): a máscara zera os octetos 4 e 5.
CONTROLE = "aa:bb:cc:d1:e2:ff"
CONTROLE_MASCARADO = "aabbcc0000ff"  # o esquema guarda a chave colada


@pytest.fixture
def dir_perfis(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> Path:
    alvo = tmp_path / "profiles"
    alvo.mkdir()

    def _falso(ensure: bool = False) -> Path:
        if ensure:
            alvo.mkdir(parents=True, exist_ok=True)
        return alvo

    monkeypatch.setattr(loader_module, "profiles_dir", _falso)
    return alvo


class _Espiao:
    def __init__(self) -> None:
        self.eventos: list[tuple[str, dict[str, object]]] = []

    def info(self, evento: str, **campos: object) -> None:
        self.eventos.append((evento, campos))

    def warning(self, evento: str, **campos: object) -> None:
        self.eventos.append((evento, campos))

    def salvos(self) -> list[dict[str, object]]:
        return [c for e, c in self.eventos if e == "profile_salvo"]


@pytest.fixture
def espiao(monkeypatch: pytest.MonkeyPatch) -> _Espiao:
    espiao = _Espiao()
    monkeypatch.setattr(loader_module, "logger", espiao)
    return espiao


class _Relogio:
    def __init__(self) -> None:
        self.dia = "20260901"
        self._n = 0

    def __call__(self) -> str:
        self._n += 1
        return f"{self.dia}T{self._n // 3600:02d}{self._n // 60 % 60:02d}{self._n % 60:02d}_000000"


@pytest.fixture
def relogio(monkeypatch: pytest.MonkeyPatch) -> _Relogio:
    relogio = _Relogio()
    monkeypatch.setattr(loader_module, "_carimbo_de_versao", relogio)
    return relogio


def _perfil(
    brilho: float | None = None, *, nome: str = "freestyle", priority: int = 10
) -> Profile:
    controles = None
    if brilho is not None:
        controles = {CONTROLE: ControllerOverrides(leds=LedsConfig(lightbar_brightness=brilho))}
    return Profile(
        name=nome,
        match=MatchCriteria(window_class=["freestyle"]),
        priority=priority,
        controllers=controles,
    )


def _prioridades() -> list[int]:
    return [
        json.loads(v.read_text(encoding="utf-8"))["priority"]
        for v in listar_historico("freestyle")
    ]


# --- o que mudou -----------------------------------------------------------


def test_mudou_traz_a_folha_exata_e_a_chave_na_mascara(
    dir_perfis: Path, espiao: _Espiao
) -> None:
    save_profile(_perfil(0.49))
    save_profile(_perfil(0.08))

    linha = espiao.salvos()[-1]
    assert linha["mudou"] == (
        f"controllers.{CONTROLE_MASCARADO}.leds.lightbar_brightness:0.49->0.08"
    )
    assert linha["igual"] is False
    # Os octetos 4 e 5 do endereço de mentira não vão ao diário, em forma nenhuma.
    for forma in ("d1:e2", "d1e2", "D1:E2"):
        assert forma not in str(linha), forma


def test_a_secao_que_nasce_ou_some_inteira_diz_a_folha(
    dir_perfis: Path, espiao: _Espiao
) -> None:
    # O primeiro brilho de um controle no perfil: `controllers` vai de nada a um
    # dicionário. A linha diz o campo, não só «controllers».
    save_profile(_perfil())
    save_profile(_perfil(0.37))
    save_profile(_perfil())

    nasceu, sumiu = espiao.salvos()[-2:]
    folha = f"controllers.{CONTROLE_MASCARADO}.leds.lightbar_brightness"
    assert nasceu["mudou"] == f"{folha}:ausente->0.37"
    assert sumiu["mudou"] == f"{folha}:0.37->ausente"


def test_nome_e_texto_livre_entram_so_como_caminho(
    dir_perfis: Path, espiao: _Espiao
) -> None:
    save_profile(_perfil(nome="freestyle"))
    # O arquivo é o mesmo (slug), o nome de exibição é outro.
    antigo = _perfil(nome="freestyle")
    novo = antigo.model_copy(update={"name": "Freestyle", "priority": 11})
    save_profile(novo)

    mudou = str(espiao.salvos()[-1]["mudou"]).split(";")
    assert "name" in mudou, mudou
    assert "priority:10->11" in mudou, mudou
    assert not any("Freestyle" in m or "freestyle->" in m for m in mudou), mudou


def test_o_perfil_que_nasce_e_o_que_nao_mudou_deixam_mudou_vazio(
    dir_perfis: Path, espiao: _Espiao
) -> None:
    save_profile(_perfil(0.5))
    save_profile(_perfil(0.5))

    nasceu, igual = espiao.salvos()
    assert nasceu["mudou"] == "" and nasceu["igual"] is False
    assert igual["mudou"] == "" and igual["igual"] is True


def test_o_teto_de_folhas_conta_o_resto(dir_perfis: Path) -> None:
    antes = json.dumps({f"c{n:02d}": n for n in range(15)}).encode()
    depois = json.dumps({f"c{n:02d}": n + 1 for n in range(15)}).encode()

    mudou = loader_module._o_que_mudou(antes, depois).split(";")
    assert len(mudou) == 13
    assert mudou[0] == "c00:0->1"
    assert mudou[11] == "c11:11->12"
    assert mudou[12] == "+3"


def test_o_arquivo_ilegivel_diz_ilegivel(dir_perfis: Path, espiao: _Espiao) -> None:
    (dir_perfis / "freestyle.json").write_text("{ isto não é json", encoding="utf-8")
    save_profile(_perfil())
    assert espiao.salvos()[-1]["mudou"] == "ilegivel"


# --- o gesto ---------------------------------------------------------------


def test_o_gesto_posto_aparece_na_linha_e_sem_ele_o_campo_e_vazio(
    dir_perfis: Path, espiao: _Espiao
) -> None:
    save_profile(_perfil(0.49))
    marca = gesto_de_agora.set("04-iluminacao · brilho")
    try:
        save_profile(_perfil(0.08))
    finally:
        gesto_de_agora.reset(marca)
    save_profile(_perfil(0.3))

    sem, com, depois = espiao.salvos()
    assert sem["gesto"] == ""
    assert com["gesto"] == "04-iluminacao · brilho"
    assert depois["gesto"] == ""


def _funcao(arvore: ast.AST, nome: str) -> ast.AST:
    achadas = [
        n for n in ast.walk(arvore)
        if isinstance(n, (ast.FunctionDef, ast.AsyncFunctionDef)) and n.name == nome
    ]
    assert achadas, nome
    return achadas[0]


def _poe_o_gesto(no: ast.AST, *, com: tuple[str, ...] = ()) -> bool:
    """`gesto_de_agora.set(...)` dentro de `no`, e o argumento nasce dos nomes `com`."""
    for n in ast.walk(no):
        if not (
            isinstance(n, ast.Call)
            and isinstance(n.func, ast.Attribute)
            and n.func.attr == "set"
            and isinstance(n.func.value, ast.Name)
            and n.func.value.id == "gesto_de_agora"
        ):
            continue
        nomes = {x.id for arg in n.args for x in ast.walk(arg) if isinstance(x, ast.Name)}
        if set(com) <= nomes:
            return True
    return False


def _arvore(caminho: Path) -> ast.Module:
    return ast.parse(caminho.read_text(encoding="utf-8"))


def test_o_gesto_e_posto_no_dispatch_e_no_trabalhar_de_gesto_e_em_nenhum_gesto_de_aba() -> None:
    """Quem põe o gesto são DOIS pontos de entrada — assim todo chamador é coberto, sem lista."""
    assert _poe_o_gesto(
        _funcao(_arvore(RAIZ / "daemon/ipc_server.py"), "_dispatch"), com=("method",)
    )

    vivo = _arvore(RAIZ / "interface/hefesto_vivo.py")
    gesto = _funcao(vivo, "_gesto")
    trabalhar = _funcao(gesto, "trabalhar")
    assert _poe_o_gesto(trabalhar, com=("pagina", "nome"))  # noqa-acento: nomes de variável
    # A quarta porta só LÊ: ela não põe gesto.
    assert not _poe_o_gesto(_funcao(vivo, "_gesto_vivo"))

    donos = [
        c.name for c in sorted((RAIZ / "interface/pacotes").glob("*.py"))
        if _poe_o_gesto(_arvore(c))
    ]
    assert donos == [], f"gesto de aba não põe o gesto, o funil põe: {donos}"


def test_nenhum_handler_do_ipc_grava_por_executor_que_perde_o_gesto() -> None:
    """`run_in_executor` não leva o contexto; `asyncio.to_thread` leva.

    Medido em 08/10/2026: os handlers do IPC que gravam perfil (`mira.set` e as
    funções do `manager` que o daemon chama) rodam no próprio laço ou por
    `to_thread`, e nenhum usa o executor do daemon (`_run_blocking`).
    """
    for arquivo in ("daemon/ipc_handlers.py", "daemon/ipc_server.py"):
        texto = (RAIZ / arquivo).read_text(encoding="utf-8")
        assert "run_in_executor" not in texto, arquivo
        assert "_run_blocking(" not in texto, arquivo


def _servidor() -> IpcServer:
    return IpcServer(controller=None, store=StateStore(), profile_manager=None)  # type: ignore[arg-type]


async def test_o_dispatch_poe_ipc_metodo_e_o_gesto_atravessa_o_to_thread(
    dir_perfis: Path, espiao: _Espiao
) -> None:
    servidor = _servidor()

    async def gravar(_params: dict[str, object]) -> dict[str, object]:
        save_profile(_perfil(0.49))
        await asyncio.to_thread(save_profile, _perfil(0.08))
        return {"ok": True}

    servidor._handlers["teste.grava"] = gravar
    bruto = (json.dumps({"jsonrpc": "2.0", "id": 1, "method": "teste.grava"}) + "\n").encode()
    resposta = await servidor._dispatch(bruto)

    assert resposta is not None and json.loads(resposta)["result"] == {"ok": True}
    assert [c["gesto"] for c in espiao.salvos()] == ["ipc:teste.grava"] * 2
    assert gesto_de_agora.get() is None, "o gesto do pedido não pode vazar para o próximo"


# --- a corrente das gravações ---------------------------------------------


def test_o_sha_antes_acusa_quem_escreveu_fora_do_funil(
    dir_perfis: Path, espiao: _Espiao
) -> None:
    save_profile(_perfil(0.08))
    # Alguém escreve fora do funil: o brilho vai a 1.0 sem nenhuma linha no diário.
    alvo = dir_perfis / "freestyle.json"
    de_fora = alvo.read_text(encoding="utf-8").replace("0.08", "1.0")
    assert de_fora != alvo.read_text(encoding="utf-8")
    alvo.write_text(de_fora, encoding="utf-8")
    save_profile(_perfil(0.3))

    primeira, segunda = espiao.salvos()
    assert primeira["sha_antes"] is None
    assert segunda["sha_antes"] != primeira["sha_depois"], "alguém escreveu fora"
    assert len(str(primeira["sha_depois"])) == 16
    # A versão arquivada guarda os bytes de quem escreveu de fora.
    assert listar_historico("freestyle")[-1].read_text(encoding="utf-8") == de_fora
    assert "1.0" in de_fora


def test_a_corrente_fecha_quando_ninguem_escreve_fora(
    dir_perfis: Path, espiao: _Espiao
) -> None:
    for brilho in (0.1, 0.2, 0.3):
        save_profile(_perfil(brilho))
    a, b, c = espiao.salvos()
    assert b["sha_antes"] == a["sha_depois"]
    assert c["sha_antes"] == b["sha_depois"]


# --- o histórico cobre uma semana -----------------------------------------


def test_uma_semana_fica_inteira_e_fora_dela_so_as_dez_ultimas_e_a_primeira_do_dia(
    dir_perfis: Path, relogio: _Relogio
) -> None:
    """41 gravações em seis dias deixam as 40 versões; duas semanas depois, a poda antiga."""
    dia = 0
    for n in range(41):
        if n % 7 == 0 and dia < 6:
            dia += 1
            relogio.dia = f"2026090{dia}"
        save_profile(_perfil(priority=n))
    assert _prioridades() == list(range(40))

    relogio.dia = "20260914"
    save_profile(_perfil(priority=41))
    # a primeira versão de cada um dos seis dias (0, 6, 13, 20, 27, 34), a do dia 14 (40)
    # e as dez últimas (31 a 40).
    assert _prioridades() == [0, 6, 13, 20, 27, *range(31, 41)]


def test_o_teto_por_perfil_derruba_as_mais_velhas_da_semana(
    dir_perfis: Path, relogio: _Relogio
) -> None:
    destino = loader_module.historico_dir("freestyle", ensure=True)
    for n in range(30):
        (destino / f"20260901T0000{n:02d}_000000.json").write_text("{}", encoding="utf-8")

    loader_module._podar_historico(destino, 10, teto=15)

    restam = sorted(p.name for p in destino.glob("*.json"))
    assert len(restam) == 15
    # a primeira do dia, as dez últimas e as quatro mais novas das que sobravam
    assert restam[0] == "20260901T000000_000000.json"
    assert restam[-1] == "20260901T000029_000000.json"


def test_cinco_gravacoes_identicas_nao_arquivam_versao_nova(
    dir_perfis: Path, espiao: _Espiao
) -> None:
    for _ in range(6):
        save_profile(_perfil(0.5))

    assert listar_historico("freestyle") == []
    nascimento, *iguais = espiao.salvos()
    assert nascimento["igual"] is False
    assert [c["igual"] for c in iguais] == [True] * 5
    assert [c["mudou"] for c in iguais] == [""] * 5
    assert [c["backup"] for c in iguais] == [None] * 5
