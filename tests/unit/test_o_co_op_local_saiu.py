"""O-CO-OP-LOCAL-SAI-01 — o Estilo «Co-op local» saiu, e a tela não trata o co-op como modo."""
from __future__ import annotations

import json
import pathlib
import re
import sys
from typing import Any

import pytest

from hefesto_dualsense4unix.app.actions import trigger_specs
from hefesto_dualsense4unix.interface import onde
from hefesto_dualsense4unix.interface.frases_que_ela_baniu import (
    texto_visivel_no_produto,
)
from hefesto_dualsense4unix.profiles import estilos_de_jogo, loader
from hefesto_dualsense4unix.profiles.schema import MatchAny, Profile
from hefesto_dualsense4unix.utils.xdg_paths import profiles_dir

RAIZ = pathlib.Path(__file__).resolve().parents[2]
_INTERFACE = str(RAIZ / "src" / "hefesto_dualsense4unix" / "interface")
if _INTERFACE not in sys.path:
    sys.path.insert(0, _INTERFACE)

CO_OP = re.compile(r"(?i)\bco-?op\b")

RECEITA_QUE_SAIU = estilos_de_jogo.Estilo(
    "coop", "Co-op local", "SimpleRigid", "balanceado", (0, 0, 255), 1.0,
    "quatro na mesa: a família é a paleta canônica de jogador, que é a que ela "
    "já conhece de olhar")

MESA = [
    {"pref": f"p{n}", "uniq": f"aa:bb:cc:00:00:0{n}", "jogador": n,
     "nome": f"Controle {n}", "via": via, "transporte": via.lower()}
    for n, via in ((1, "USB"), (2, "BT"), (3, "USB"), (4, "BT"))
]


def test_o_coop_nao_volta_ao_dono_dos_estilos() -> None:
    """MORDIDA: devolva o `Estilo("coop", "Co-op local", …)` a `ESTILOS`."""
    voltaram = [f"{e.chave} / {e.rotulo}" for e in estilos_de_jogo.ESTILOS
                if CO_OP.search(e.chave) or CO_OP.search(e.rotulo)]
    assert not voltaram, (
        f"um Estilo de Jogo de co-op voltou ao motor: {voltaram}. O Hefesto dá "
        "um controle virtual a cada jogador sempre, e o co-op não é um modo que "
        "se escolhe (D-2409-O-CO-OP-LOCAL-SAI).")
    assert "coop" not in estilos_de_jogo.POR_CHAVE
    assert RECEITA_QUE_SAIU.rotulo not in estilos_de_jogo.POR_ROTULO


def test_os_de_fabrica_sao_os_que_tem_receita() -> None:
    """`DE_FABRICA` é `ESTILOS` sem o «Personalizado», na mesma ordem."""
    esperado = tuple(e for e in estilos_de_jogo.ESTILOS if e.chave != "personalizado")
    assert esperado == estilos_de_jogo.DE_FABRICA
    assert len(estilos_de_jogo.DE_FABRICA) == len(estilos_de_jogo.ESTILOS) - 1


_LIDO = {"um": 1, "dois": 2, "três": 3, "quatro": 4, "cinco": 5, "seis": 6,
         "sete": 7, "oito": 8, "nove": 9, "dez": 10, "onze": 11, "doze": 12,
         "treze": 13, "catorze": 14, "quinze": 15, "dezesseis": 16,
         "dezessete": 17, "dezoito": 18, "dezenove": 19, "vinte": 20}


def test_a_dica_da_aba_perfis_conta_pelo_dono() -> None:
    """A dica do «Estilo de Jogo» diz quantos de fábrica o MOTOR tem."""
    bancada = onde.pagina("10-perfis.html").read_text(encoding="utf-8")
    achado = re.search(r"Os (\w+) de fábrica não se editam", bancada)
    assert achado, "a dica do Estilo de Jogo não diz mais quantos são de fábrica"
    assert _LIDO.get(achado.group(1)) == len(estilos_de_jogo.DE_FABRICA), (
        f"a bancada diz «{achado.group(1)}» de fábrica e o motor tem "
        f"{len(estilos_de_jogo.DE_FABRICA)}")
    fonte = (RAIZ / "src/hefesto_dualsense4unix/interface/aba10.py").read_text(
        encoding="utf-8")
    digitada = re.search(rf"Os ({'|'.join(_LIDO)}) de fábrica", fonte)
    assert digitada is None, (
        f"a conta da dica voltou a ser digitada no gerador: «{digitada.group(0)}»")


@pytest.fixture
def primeira_carga(monkeypatch: pytest.MonkeyPatch) -> None:
    """Liga a semeadura e as migrações one-shot (o `conftest` as desliga)."""
    monkeypatch.delenv(loader.SEED_SKIP_ENV_VAR, raising=False)
    monkeypatch.setattr(loader, "_seed_attempted", False)
    monkeypatch.setattr(loader, "_DEFAULT_SEED_SOURCE_DIRS",
                        (RAIZ / "assets" / "profiles_default",))
    monkeypatch.setattr(loader, "_talvez_semear_jogos", lambda: None)


def _o_perfil_que_recebeu_o_coop() -> tuple[pathlib.Path, bytes, Profile]:
    """Um perfil de jogo que recebeu o «Co-op local» pelo caminho do produto."""
    from pacotes import a10_perfis

    antes = Profile(name="Jogo do Sofá", match=MatchAny(), priority=30)
    loader.save_profile(antes)
    com_o_coop, pintados = a10_perfis._com_o_estilo(antes, RECEITA_QUE_SAIU, MESA)
    assert pintados == len(MESA)
    arquivo = loader.save_profile(com_o_coop)
    return arquivo, arquivo.read_bytes(), com_o_coop


def test_o_perfil_que_recebeu_o_coop_fica_com_os_ajustes_e_sem_estilo(
    primeira_carga: None,
) -> None:
    """Nenhum byte do arquivo muda, e os três ajustes continuam valendo.

    O ESTILO NUNCA FOI GUARDADO — `Profile` não tem campo de estilo, e o que o
    «Co-op local» deixava no perfil eram três VALORES: o gatilho `SimpleRigid`
    com os parâmetros do dono, a vibração `balanceado` e uma cor por controle,
    com o carimbo do número. Nenhum depende do estilo existir.

    MORDIDA: acrescente a `_maybe_seed_presets` uma "migração" que reescreva o
    perfil (tirar as cores da família do co-op, por exemplo) — o arquivo deixa de
    ser byte a byte o de antes, e os ajustes dela se perdem.
    """
    arquivo, bruto, gravado = _o_perfil_que_recebeu_o_coop()

    carregados = {p.name: p for p in loader.load_all_profiles()}
    assert arquivo.read_bytes() == bruto, (
        "a primeira carga REESCREVEU o perfil que recebeu o «Co-op local» — o "
        "estilo nunca foi guardado, e não há nada a migrar nele")
    assert not CO_OP.search(bruto.decode("utf-8")), (
        "o arquivo do perfil nomeia o co-op: o estilo passou a ser guardado")

    perfil = carregados["Jogo do Sofá"]
    spec = trigger_specs.get_spec(RECEITA_QUE_SAIU.gatilho or "")
    assert spec is not None
    params = list(trigger_specs.preset_to_positional_params(spec, {}))
    for lado in ("left", "right"):
        gatilho = getattr(perfil.triggers, lado)
        assert (gatilho.mode, list(gatilho.params)) == ("SimpleRigid", params)
    assert perfil.rumble.policy == "balanceado"
    cores = estilos_de_jogo.as_quatro(RECEITA_QUE_SAIU)
    for controle in MESA:
        uniq = controle["uniq"].replace(":", "")
        leds = (perfil.controllers or {})[uniq].leds
        assert leds is not None
        assert tuple(leds.lightbar) == cores[controle["jogador"] - 1]
        assert leds.lightbar_para_o_numero == controle["jogador"]
    assert perfil == gravado


def test_a_volta_de_antes_do_estilo_continua_no_historico(primeira_carga: None) -> None:
    """A cópia do perfil de ANTES da receita está no `.historico`, e volta inteira."""
    arquivo, _bruto, _gravado = _o_perfil_que_recebeu_o_coop()
    versoes_antes = loader.listar_historico("Jogo do Sofá")
    assert versoes_antes, "o save do estilo não guardou a versão de antes"

    loader.load_all_profiles()
    assert loader.listar_historico("Jogo do Sofá") == versoes_antes

    alvo, usada = loader.restaurar_do_historico("Jogo do Sofá")
    assert alvo == arquivo
    assert alvo.read_bytes() == usada.read_bytes()
    volta = Profile.model_validate(json.loads(alvo.read_text(encoding="utf-8")))
    assert not volta.controllers and volta.rumble.policy is None, (
        "a versão guardada não é a de antes do estilo")


def test_o_gesto_recusa_o_estilo_que_saiu_sem_gravar() -> None:
    """Até a publicação da 10, a página velha ainda oferece «Co-op local»."""
    from pacotes import Contexto, a10_perfis

    pasta = profiles_dir(ensure=True)
    loader.save_profile(Profile(name="Jogo do Sofá", match=MatchAny(), priority=30))
    antes = (pasta / "jogo_do_sofa.json").read_bytes()
    ctx = Contexto(state={"active_profile": None}, mesa=list(MESA),
                   conectados=list(MESA), estados={})

    with pytest.raises(RuntimeError) as recusa:
        a10_perfis.editor_estilo(ctx, {"valor": RECEITA_QUE_SAIU.rotulo}, object())
    assert "não é um dos Estilos de Jogo" in str(recusa.value)
    assert (pasta / "jogo_do_sofa.json").read_bytes() == antes


CO_OP_QUE_PODE_FICAR: tuple[str, ...] = ()


def _em_trabalho(nome: str) -> bool:
    """A aba está declarada em trabalho em `mockup/DIVERGENCIAS.md`?"""
    arquivo = onde.BANCADA / "DIVERGENCIAS.md"
    if not arquivo.exists():
        return False
    corpo = arquivo.read_text(encoding="utf-8").split("\n---\n", 1)[-1]
    return f"\n## {nome}" in f"\n{corpo}"


def _as_dez(publicado: bool) -> list[pathlib.Path]:
    return [p for p in onde.paginas(publicado=publicado) if re.match(r"\d\d-", p.name)]


def test_nenhuma_aba_diz_co_op_no_que_o_produto_renderiza() -> None:
    """A leitura do PRODUTO (`texto_visivel_no_produto`: sem a `.nota`, sem código)."""
    bancada = _as_dez(publicado=False)
    assert len(bancada) == 10, [p.name for p in bancada]
    alvos = bancada + [p for p in _as_dez(publicado=True) if not _em_trabalho(p.name)]
    achados: list[str] = []
    for pagina in alvos:
        visivel = texto_visivel_no_produto(pagina.read_text(encoding="utf-8"))
        for n, linha in enumerate(visivel.splitlines(), 1):
            if CO_OP.search(linha) and not any(ok in linha for ok in CO_OP_QUE_PODE_FICAR):
                achados.append(f"{pagina.parent.name}/{pagina.name}:{n}: {linha.strip()[:120]}")
    assert not achados, (
        "a tela voltou a dizer «co-op»:\n  " + "\n  ".join(achados))


def _colunas_da_04(jogadores: int) -> dict[str, Any]:
    import pacotes

    conectados = [
        {"uniq": c["uniq"], "transport": c["transporte"], "connected": True,
         "player": c["jogador"], "player_slot": c["jogador"],
         "is_primary": c["jogador"] == 1, "lightbar_rgb": [0, 0, 255],
         "lightbar_on": True, "lightbar_source": "sysfs", "battery_pct": 80}
        for c in MESA
    ]
    estado = {"active_profile": "", "coop": {"enabled": True, "players": jogadores}}
    ctx = pacotes.Contexto(state=estado, mesa=list(MESA), conectados=conectados,
                           estados={})
    return dict(pacotes.pacote_da_pagina("04-iluminacao.html", ctx)["colunas"])


def test_a_dica_da_celula_leds_e_a_mesma_de_um_a_quatro_jogadores() -> None:
    """Com dois jogadores ou mais a dica somava «com o co-op ligado, é ele que…»."""
    um = _colunas_da_04(1)
    for jogadores in (2, 3, 4):
        muitos = _colunas_da_04(jogadores)
        for uniq, coluna in muitos.items():
            assert not CO_OP.search(str(coluna.get("luz", ""))), coluna.get("luz")
            assert coluna.get("luz") == um[uniq].get("luz"), (
                f"a célula LEDs de {uniq} muda com {jogadores} jogadores na mesa")


@pytest.mark.parametrize("jogadores", [1, 2, 3, 4])
def test_nenhum_dos_dez_pacotes_pinta_co_op(jogadores: int) -> None:
    """O que os DEZ pacotes pintam no tique, com a mesa de quatro, não diz «co-op»."""
    import pacotes

    conectados = [
        {"uniq": c["uniq"], "transport": c["transporte"], "connected": True,
         "player": c["jogador"], "player_slot": c["jogador"],
         "index": c["jogador"] - 1, "is_primary": c["jogador"] == 1,
         "lightbar_rgb": [0, 0, 255], "lightbar_on": True,
         "lightbar_source": "sysfs", "battery_pct": 80, "vpad_backend": "uhid"}
        for c in MESA
    ]
    estado = {"active_profile": "", "controllers": conectados,
              "coop": {"enabled": True, "players": jogadores,
                       "mesa": [{"player": n} for n in range(1, jogadores + 1)]}}
    achados: list[str] = []
    for pagina in _as_dez(publicado=False):
        ctx = pacotes.Contexto(state=estado, mesa=list(MESA),
                               conectados=list(conectados), estados={})
        pintado = json.dumps(pacotes.pacote_da_pagina(pagina.name, ctx),
                             ensure_ascii=False, default=str)
        achados += [f"{pagina.name}: …{pintado[max(0, m.start() - 80):m.end() + 60]}…"
                    for m in CO_OP.finditer(pintado)]
    assert not achados, (
        f"com {jogadores} jogador(es), o tique pinta «co-op»:\n  "
        + "\n  ".join(achados[:6]))


class _Ponte:
    """A ponte do gesto `player`: o número troca, a reconciliação não responde.

    Não é mais frouxa que a real: `identity_number_set` devolve `(ok, motivo)` e
    `chamar` devolve o `bool` do `_safe_call` — os dois contratos de
    `interface/pacotes/ponte.py`.
    """

    def __init__(self) -> None:
        self.chamadas: list[str] = []

    def identity_number_set(self, uniq: str, n: int) -> tuple[bool, str | None]:
        self.chamadas.append(f"identity_number_set:{uniq}:{n}")
        return True, None

    def chamar(self, metodo: str, timeout: float | None = None, **params: Any) -> bool:
        self.chamadas.append(f"chamar:{metodo}")
        return False


@pytest.mark.parametrize("jogadores", [2, 3, 4])
def test_a_recusa_do_jogador_diz_o_que_aconteceu(jogadores: int) -> None:
    """O número mudou e as lâmpadas não: é isso, e só."""
    import pacotes

    estado = {"active_profile": "", "coop": {"enabled": True, "players": jogadores}}
    ctx = pacotes.Contexto(state=estado, mesa=list(MESA), conectados=list(MESA),
                           estados={})
    gesto = pacotes.gesto_da_pagina("04-iluminacao.html", "player")
    assert gesto is not None
    ponte = _Ponte()
    with pytest.raises(RuntimeError) as recusa:
        gesto(ctx, {"uniq": MESA[1]["uniq"], "player": "1"}, ponte)
    frase = str(recusa.value)
    assert "chamar:coop.sync" in ponte.chamadas
    assert frase == "o número deste controle mudou para 1, mas as cinco lâmpadas não.", frase
    assert not CO_OP.search(frase)
