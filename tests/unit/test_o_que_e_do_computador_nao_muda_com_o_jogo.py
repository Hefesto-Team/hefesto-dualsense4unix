"""O que é do computador não muda com o jogo (O-QUE-E-DO-COMPUTADOR-NAO-MUDA-COM-O-JOGO-01)."""
from __future__ import annotations

import json
from typing import Any

import pytest

from hefesto_dualsense4unix.profiles import o_padrao_do_computador as opc
from hefesto_dualsense4unix.profiles.loader import load_profile, save_profile
from hefesto_dualsense4unix.profiles.schema import (
    A_ECONOMIA_EM_CADA_PECA,
    Profile,
)
from hefesto_dualsense4unix.utils import maquina as m

P1 = "aabbcc000001"
P2 = "aabbcc000002"
P3 = "aabbcc000003"


def _perfil(nome: str = "Jogo X", **campos: Any) -> Profile:
    return Profile.model_validate(
        {"name": nome, "match": {"type": "criteria", "window_class": [nome.lower()]},
         **campos})


def _computador(documento: dict[str, Any]) -> Any:
    assert m.gravar_o_computador(documento)
    return opc.o_computador()


def test_o_computador_vai_ao_disco_so_com_o_que_foi_declarado() -> None:
    """O brilho de fábrica de UM controle não pode ir ao disco por extenso."""
    _computador({"controles": {P2: {"leds": {"lightbar": [0, 255, 0]}}}})
    bruto = json.loads(m.caminho_da_maquina().read_text(encoding="utf-8"))
    assert bruto["computador"] == {"controles": {P2: {"leds": {"lightbar": [0, 255, 0]}}}}
    relido = m.carregar_maquina().computador
    assert relido.controles[P2].leds.model_fields_set == {"lightbar"}


def test_o_computador_recusa_o_que_e_do_jogo() -> None:
    """A máscara, os gatilhos e a mira de um controle são do jogo (`DO_JOGO`)."""
    with pytest.raises(ValueError, match="do jogo"):
        m.gravar_o_computador({"controles": {P2: {"mascara": "xbox"}}})
    with pytest.raises(ValueError):
        m.gravar_o_computador({"global": {"mouse": {"speed": 99}}})


def test_o_resgate_salva_o_resto_do_computador() -> None:
    """Uma seção torta sai sozinha; a luz que ela ajustou continua."""
    _computador({"global": {"leds": {"lightbar": [1, 2, 3]}}})
    bruto = json.loads(m.caminho_da_maquina().read_text(encoding="utf-8"))
    bruto["computador"]["global"]["mouse"] = {"speed": 999}
    m.caminho_da_maquina().write_text(json.dumps(bruto), encoding="utf-8")
    relido = m.carregar_maquina().computador
    assert relido.global_.leds is not None and relido.global_.leds.lightbar == (1, 2, 3)
    assert relido.global_.mouse is None


def test_sem_computador_a_vista_e_o_mesmo_objeto() -> None:
    """Quem nunca declarou nada aplica byte a byte o que aplicava."""
    jogo = _perfil(leds={"lightbar": [9, 9, 9]})
    assert opc.perfil_que_vale(jogo, m.MaquinaConfig().computador) is jogo


def test_a_precedencia_campo_a_campo() -> None:
    """O jogo neste controle > o jogo global > o computador neste controle > o todo controle."""
    computador = _computador({
        "global": {"leds": {"lightbar": [10, 20, 200], "lightbar_brightness": 0.5},
                   "rumble": {"policy": "max"}},
        "controles": {P2: {"leds": {"lightbar": [0, 255, 0], "lightbar_brightness": 0.3},
                           "rumble": {"motor_forte_pct": 40}}},
    })
    jogo = _perfil(leds={"lightbar": [255, 0, 0]},
                   controllers={P2: {"rumble": {"motor_forte_pct": 80}}})
    vista = opc.perfil_que_vale(jogo, computador)
    assert vista.leds.lightbar == (255, 0, 0)
    assert vista.leds.lightbar_brightness == 0.5
    assert vista.rumble.policy == "max"
    p2 = vista.controllers[P2]
    assert p2.rumble.motor_forte_pct == 80
    assert p2.leds.lightbar_brightness == 0.3
    assert "lightbar" not in p2.leds.model_fields_set


def test_o_valor_de_fabrica_das_secoes_densas_segue_o_computador() -> None:
    """O `leds` que o «Salvar» antigo gravava por extenso não é escolha (a resposta 4)."""
    from hefesto_dualsense4unix.profiles.schema import LedsConfig

    computador = _computador({"global": {"leds": {"lightbar": [10, 20, 200]}}})
    for leds in ({}, LedsConfig().model_dump(mode="json")):
        jogo = _perfil(leds=leds)
        assert not opc.sobrepoe(jogo, "luz"), leds
        assert opc.perfil_que_vale(jogo, computador).leds.lightbar == (10, 20, 200)


def test_o_par_da_politica_anda_junto() -> None:
    """O jogo que escolhe a política leva o `custom_mult` junto: nada de par torto."""
    computador = _computador({"global": {"rumble": {"policy": "custom", "custom_mult": 1.7}}})
    jogo = _perfil(rumble={"policy": "max"})
    vista = opc.perfil_que_vale(jogo, computador)
    assert (vista.rumble.policy, vista.rumble.custom_mult) == ("max", None)


def test_o_controle_nunca_visto_nasce_do_computador() -> None:
    """Uma identidade nova, sem linha no perfil nem no computador, recebe o global."""
    computador = _computador({"global": {"leds": {"lightbar": [10, 20, 200]}}})
    vista = opc.perfil_que_vale(_perfil(), computador)
    assert P3 not in (vista.controllers or {})
    assert vista.leds.lightbar == (10, 20, 200)


def test_os_botoes_e_as_teclas_do_computador_por_baixo_do_jogo() -> None:
    computador = _computador({"global": {
        "button_actions": {"cross": "KEY_ENTER", "circle": "KEY_ESC"},
        "key_bindings": {"triangle": ["KEY_C"]},
        "teclado_emulado": True,
    }})
    jogo = _perfil(button_actions={"circle": "KEY_BACKSPACE"}, key_bindings={})
    vista = opc.perfil_que_vale(jogo, computador)
    assert vista.button_actions == {"cross": "KEY_ENTER", "circle": "KEY_BACKSPACE"}
    assert vista.key_bindings == {}
    assert vista.teclado_emulado is True


def test_o_clique_grava_no_computador_quando_o_jogo_nao_sobrepoe() -> None:
    """O perfil fica byte a byte; o `maquina.json` muda."""
    caminho = save_profile(_perfil())
    antes = caminho.read_bytes()
    onde = opc.gravar("luz", {"leds": {"lightbar": [1, 2, 3]}}, uniq=P2,
                      perfil_ativo="Jogo X")
    assert onde == opc.COMPUTADOR
    assert caminho.read_bytes() == antes
    assert opc.o_computador().controles[P2].leds.lightbar == (1, 2, 3)


def test_o_clique_grava_no_jogo_quando_ele_ja_sobrepoe_o_cartao() -> None:
    save_profile(_perfil(controllers={P2: {"leds": {"lightbar": [9, 9, 9]}}}))
    onde = opc.gravar("luz", {"leds": {"lightbar": [1, 2, 3]}}, uniq=P2,
                      perfil_ativo="Jogo X")
    assert onde == opc.JOGO
    assert load_profile("Jogo X").controllers[P2].leds.lightbar == (1, 2, 3)
    assert P2 not in opc.o_computador().controles


def test_o_gesto_roda_sobre_o_que_vale_e_so_a_diferenca_vai_ao_computador() -> None:
    """`gravar_pelo_gesto`: o gesto de sempre, sobre a vista; o perfil não muda."""
    save_profile(_perfil(controllers={P1: {"triggers": {"left": {"mode": "Off"}}}}))
    _computador({"controles": {P2: {"leds": {"lightbar_brightness": 0.0}}}})
    caminho_antes = load_profile("Jogo X").model_dump(mode="json")

    def religar(perfil: Profile) -> Profile:
        cru = perfil.model_dump(mode="json", exclude_unset=True)
        controles = dict(cru.get("controllers") or {})
        entrada = dict(controles.get(P2) or {})
        leds = {k: v for k, v in dict(entrada.get("leds") or {}).items()
                if k != "lightbar_brightness"}
        leds["lightbar"] = [1, 2, 3]
        entrada["leds"] = leds
        controles[P2] = entrada
        cru["controllers"] = controles
        return Profile.model_validate(cru)

    onde, _novo = opc.gravar_pelo_gesto("luz", "Jogo X", religar, uniq=P2)
    assert onde == opc.COMPUTADOR
    leds = opc.o_computador().controles[P2].leds
    assert leds.lightbar == (1, 2, 3)
    assert "lightbar_brightness" not in leds.model_fields_set
    assert load_profile("Jogo X").model_dump(mode="json") == caminho_antes


def test_o_gesto_le_o_que_vale_e_nao_o_cru() -> None:
    """O gesto que parte do valor de agora parte do que VALE (o computador), não do cru."""
    save_profile(_perfil())
    _computador({"controles": {P2: {"leds": {"lightbar": [10, 20, 30]}}}})

    def um_a_mais(perfil: Profile) -> Profile:
        cru = perfil.model_dump(mode="json", exclude_unset=True)
        controles = dict(cru.get("controllers") or {})
        entrada = dict(controles.get(P2) or {})
        leds = dict(entrada.get("leds") or {})
        leds["lightbar"] = [c + 1 for c in leds.get("lightbar") or (0, 0, 0)]
        entrada["leds"] = leds
        controles[P2] = entrada
        cru["controllers"] = controles
        return Profile.model_validate(cru)

    onde, _novo = opc.gravar_pelo_gesto("luz", "Jogo X", um_a_mais, uniq=P2)
    assert onde == opc.COMPUTADOR
    assert opc.o_computador().controles[P2].leds.lightbar == (11, 21, 31)


def test_so_neste_jogo_e_voltar_ao_do_computador() -> None:
    """O jogo copia o que vale e passa a mandar; voltar tira, e o computador volta."""
    _computador({"controles": {P2: {"leds": {"lightbar": [0, 255, 0]}}}})
    save_profile(_perfil())
    opc.so_neste_jogo("luz", P2, "Jogo X")
    jogo = load_profile("Jogo X")
    assert jogo.controllers[P2].leds.lightbar == (0, 255, 0)
    assert opc.marca("luz", jogo, P2) == "Jogo X"
    assert opc.gravar("luz", {"leds": {"lightbar": [255, 0, 0]}}, uniq=P2,
                      perfil_ativo="Jogo X") == opc.JOGO
    assert opc.o_computador().controles[P2].leds.lightbar == (0, 255, 0)
    opc.voltar_ao_do_computador("luz", P2, "Jogo X")
    jogo = load_profile("Jogo X")
    assert opc.marca("luz", jogo, P2) == "Computador"
    assert opc.perfil_que_vale(jogo, opc.o_computador()).controllers[P2].leds.lightbar == (
        0, 255, 0)


def test_o_freestyle_nao_sobrepoe_nada() -> None:
    """Com o Freestyle, o clique grava no computador e o «Só neste jogo» recusa."""
    save_profile(Profile.model_validate({"name": "Freestyle", "match": {"type": "any"},
                                         "leds": {"lightbar": [5, 5, 5]}}))
    assert opc.gravar("luz", {"leds": {"lightbar": [1, 2, 3]}},
                      perfil_ativo="Freestyle") == opc.COMPUTADOR
    with pytest.raises(opc.OFreestyleNaoSobrepoeError):
        opc.so_neste_jogo("luz", P2, "Freestyle")


def test_na_vista_o_freestyle_fica_por_baixo_do_computador() -> None:
    """O que o arquivo do Freestyle ainda guarda de um cartão do computador não vence."""
    _computador({"global": {"teclado_emulado": True, "button_actions": {"r1": "KEY_UP"}},
                 "controles": {P2: {"leds": {"lightbar": [0, 0, 255]},
                                    "rumble": {"motor_forte_pct": 40}}}})
    save_profile(Profile.model_validate({
        "name": "Freestyle", "match": {"type": "any"}, "teclado_emulado": False,
        "button_actions": {"r1": "KEY_DOWN", "l1": "KEY_LEFT"},
        "controllers": {P2: {"leds": {"lightbar": [255, 0, 0]},
                             "rumble": {"motor_forte_pct": 100}}}}))
    freestyle = load_profile("Freestyle")
    assert opc.onde_grava("luz", freestyle, P2) == opc.COMPUTADOR
    vista = opc.o_que_vale(freestyle)
    entrada = vista.controllers[opc.chave_no_perfil(vista, P2)]
    assert tuple(entrada.leds.lightbar) == (0, 0, 255)
    assert entrada.rumble.motor_forte_pct == 40
    assert vista.teclado_emulado is True
    assert vista.button_actions == {"r1": "KEY_UP", "l1": "KEY_LEFT"}
    save_profile(Profile.model_validate({
        **freestyle.model_dump(mode="json", exclude_unset=True),
        "name": "Jogo X", "match": {"type": "criteria", "window_class": ["jogox"]}}))
    jogo = opc.o_que_vale(load_profile("Jogo X"))
    entrada = jogo.controllers[opc.chave_no_perfil(jogo, P2)]
    assert tuple(entrada.leds.lightbar) == (255, 0, 0)
    assert jogo.teclado_emulado is False
    assert jogo.button_actions == {"r1": "KEY_DOWN", "l1": "KEY_LEFT"}


def test_restaurar_esvazia_o_computador_e_guarda_a_marca_da_migracao() -> None:
    _computador({"global": {"leds": {"lightbar": [1, 2, 3]}}, "migrado": True})
    assert opc.restaurar_o_computador()
    computador = opc.o_computador()
    assert computador.migrado is True
    assert computador.global_.leds is None


def test_a_economia_diz_que_corta_tambem_a_haptica() -> None:
    """A economia corta a háptica desde 29/09 (``daemon/ganho_da_haptica``)."""
    vibracao = next(p for p in A_ECONOMIA_EM_CADA_PECA if p.nome == "Vibração")
    assert vibracao.o_que_faz == "O teto da Economia, nos dois motores e na háptica."


def _gerente(**appliers: Any) -> tuple[Any, Any]:
    from hefesto_dualsense4unix.daemon.state_store import StateStore
    from hefesto_dualsense4unix.profiles.manager import ProfileManager
    from hefesto_dualsense4unix.testing import FakeController

    fc = FakeController(transport="usb")
    fc.connect()
    return ProfileManager(controller=fc, store=StateStore(), **appliers), fc


def _ultima_cor(fc: Any) -> Any:
    cores = [c.payload for c in fc.commands if c.kind == "set_led"]
    return cores[-1] if cores else None


def test_a_ativacao_aplica_o_computador_no_que_o_jogo_nao_escolheu() -> None:
    """O jogo sem cor recebe a cor do computador, igual a um perfil que a escolhesse."""
    save_profile(_perfil("Controle", leds={"lightbar": [10, 20, 200]}))
    gerente, fc = _gerente()
    gerente.activate("Controle", origin="launch")
    esperada = _ultima_cor(fc)
    assert esperada is not None

    save_profile(_perfil("Jogo X", leds={}))
    _computador({"global": {"leds": {"lightbar": [10, 20, 200]}}})
    gerente, fc = _gerente()
    gerente.activate("Jogo X", origin="launch")
    assert _ultima_cor(fc) == esperada


#: AS QUATRO PORTAS DA TROCA. O «Ativar» da aba Perfis (`profile.switch`) e o
PORTAS = ("manual", "autoswitch", "launch")
P4 = "aabbcc000004"


@pytest.mark.parametrize("transporte", ["usb", "bt"])
@pytest.mark.parametrize("porta", PORTAS)
@pytest.mark.parametrize("uniq", [P1, P2, P3, P4])
def test_a_troca_nao_leva_o_que_e_do_computador(uniq: str, porta: str, transporte: str) -> None:
    """Régua 1: B, A, B de novo — e o B volta ao computador, nunca ao que o A escolheu."""
    from hefesto_dualsense4unix.daemon.state_store import StateStore
    from hefesto_dualsense4unix.profiles.manager import ProfileManager
    from hefesto_dualsense4unix.testing import FakeController

    som: dict[str, int] = {}

    def _som(volume: int, muted: bool, *, uniq: str | None = None, **_k: Any) -> str:
        som[str(uniq)] = int(volume)
        return "aplicado"

    save_profile(_perfil("Jogo A", leds={"lightbar": [200, 10, 10]},
                         controllers={uniq: {"speaker": {"volume": 30}}}))
    save_profile(_perfil("Jogo B"))
    _computador({"global": {"leds": {"lightbar": [10, 20, 200]}},
                 "controles": {uniq: {"speaker": {"volume": 90}}}})
    fc = FakeController(transport=transporte)  # type: ignore[arg-type]
    fc.connect()
    gerente = ProfileManager(controller=fc, store=StateStore(), speaker_applier=_som)

    def _troca(nome: str) -> tuple[Any, dict[str, int]]:
        som.clear()
        gerente.activate(nome, origin=porta)
        return _ultima_cor(fc), dict(som)

    cor_b, som_b = _troca("Jogo B")
    cor_a, som_a = _troca("Jogo A")
    cor_b2, som_b2 = _troca("Jogo B")
    assert som_b == {uniq: 90}, som_b
    assert som_a == {uniq: 30}, som_a
    assert som_b2 == {uniq: 90}, f"o B ficou com o som do A: {som_b2}"
    assert cor_a != cor_b, (cor_a, cor_b)
    assert cor_b2 == cor_b, f"o B ficou com a cor do A: {cor_b2} != {cor_b}"


def test_as_velocidades_do_jogo_de_mouse_vem_do_computador() -> None:
    """O Point-and-click é do jogo; as duas velocidades, do computador."""
    recebidos: list[tuple[Any, ...]] = []
    save_profile(_perfil(mouse={"enabled": True, "speed": 6, "scroll_speed": 1}))
    _computador({"global": {"mouse": {"speed": 11, "scroll_speed": 4}}})
    gerente, _fc = _gerente(
        mouse_applier=lambda en, sp, sc, **_k: recebidos.append((en, sp, sc)) or True)
    gerente.activate("Jogo X", origin="launch")
    assert recebidos == [(True, 11, 4)]


def test_o_reinicio_nao_esquece_a_velocidade(monkeypatch: pytest.MonkeyPatch) -> None:
    """Sem a seção no perfil, a Navegação liga o mouse com a velocidade do computador."""
    from hefesto_dualsense4unix.daemon import lifecycle
    from hefesto_dualsense4unix.utils import session

    monkeypatch.setattr(session, "load_mouse_preference", lambda: (True, 3, 1))
    _computador({"global": {"mouse": {"speed": 11, "scroll_speed": 4}}})
    assert lifecycle._velocidades_ou_as_da_sessao(None, None) == (11, 4)
    assert lifecycle._velocidades_ou_as_da_sessao(7, None) == (7, 4)


def test_os_motores_do_computador_chegam_ao_jogo() -> None:
    """O mapa dos motores do FF do jogo sai da vista, com o selo do `maquina.json`."""
    from hefesto_dualsense4unix.daemon.subsystems import gamepad

    save_profile(_perfil())
    _computador({"controles": {P2: {"rumble": {"motor_forte_pct": 40, "motor_fraco_pct": 70}}}})

    class _Daemon:
        class store:  # noqa: N801 - a forma do dublê é a do daemon
            active_profile = "Jogo X"

    assert gamepad._motores_do_perfil_ativo(_Daemon())[P2] == (40, 70)


def test_o_mouse_virtual_volta_ao_de_fabrica_sem_os_botoes() -> None:
    """Perfil e computador sem `button_actions`: o device volta ao de fábrica.

    MORDIDA: tirar o `_mouse_ao_de_fabrica` deixa no device o mapa do perfil anterior.
    """
    chamadas: list[Any] = []

    class _Mouse:
        def set_button_actions(self, do_mouse: Any, calados: Any = None) -> None:
            chamadas.append(do_mouse)

    gerente, _fc = _gerente(mouse_device_provider=lambda: _Mouse())
    gerente.apply_button_actions(_perfil())
    assert chamadas == [None]


LEITORES_DO_QUE_E_DO_JOGO: dict[tuple[str, str], str] = {
    ("daemon/connection.py", "perfil_que_o_boot_restaura"):
        "o boot lê só o `match` e o `mode`, que são do jogo",
    ("profiles/manager.py", "get"): "o perfil cru, para quem edita",
    ("cli/cmd_profile.py", "cmd_show"): "mostra o arquivo cru, que é o que se edita",
}


def test_todo_leitor_le_a_vista() -> None:
    """Todo `load_profile(` do daemon, do gerente e da CLI: escritor, leitor do jogo, ou a vista."""
    import ast
    from pathlib import Path

    import hefesto_dualsense4unix

    raiz = Path(hefesto_dualsense4unix.__file__).parent
    arquivos = [*sorted((raiz / "daemon").rglob("*.py")), raiz / "profiles" / "manager.py",
                raiz / "cli" / "cmd_profile.py"]
    sem_classe: list[str] = []
    vistos: set[tuple[str, str]] = set()
    for arquivo in arquivos:
        relativo = arquivo.relative_to(raiz).as_posix()
        for funcao in ast.walk(ast.parse(arquivo.read_text(encoding="utf-8"))):
            if not isinstance(funcao, ast.FunctionDef | ast.AsyncFunctionDef):
                continue
            chamadas = [n for n in ast.walk(funcao) if isinstance(n, ast.Call)]
            nomes = {getattr(c.func, "id", None) or getattr(c.func, "attr", None)
                     for c in chamadas}
            if "load_profile" not in nomes:
                continue
            internas = [n for n in ast.walk(funcao)
                        if n is not funcao and isinstance(n, ast.FunctionDef | ast.AsyncFunctionDef)
                        and "load_profile" in {getattr(c.func, "id", None)
                                               or getattr(c.func, "attr", None)
                                               for c in ast.walk(n) if isinstance(c, ast.Call)}]
            if internas:
                continue
            chave_ = (relativo, funcao.name)
            vistos.add(chave_)
            if nomes & {"o_que_vale", "carregar_o_que_vale"} or "save_profile" in nomes:
                continue
            if chave_ not in LEITORES_DO_QUE_E_DO_JOGO:
                sem_classe.append(f"{relativo}::{funcao.name}")
    assert not sem_classe, f"leitor do perfil que não lê a vista: {sem_classe}"
    assert set(LEITORES_DO_QUE_E_DO_JOGO) <= vistos, "a lista dos leitores do jogo envelheceu"


UM = "aa:bb:cc:00:00:01"


class _Ponte:
    """Um daemon de papel que confirma tudo: o que se mede aqui é o disco."""

    def __init__(self) -> None:
        self.chamadas: list[str] = []

    def __getattr__(self, nome: str) -> Any:
        def registrar(*_a: Any, **_k: Any) -> Any:
            self.chamadas.append(nome)
            if nome == "resultado":
                return {"status": "ok"}
            if nome.endswith("_detalhado"):
                return {"status": "ok", "por_uniq": True}
            return True
        return registrar


def _pacotes() -> Any:
    import sys
    from pathlib import Path

    import hefesto_dualsense4unix

    interface = str(Path(hefesto_dualsense4unix.__file__).parent / "interface")
    if interface not in sys.path:
        sys.path.insert(0, interface)
    import pacotes
    import pacotes.a02_controles
    import pacotes.a04_iluminacao
    import pacotes.a05_vibracao
    import pacotes.a06_navegacao

    return pacotes


def _contexto(pac: Any, ativo: str) -> Any:
    um = {"uniq": UM, "connected": True, "transport": "usb", "is_primary": True,
          "inputs": {}, "audio": {"mic_mudo": False},
          "speaker": {"volume": 100, "muted": False}}
    return pac.Contexto(
        state={"active_profile": ativo, "rumble_policy": "balanceado", "rumble_ff": {},
               "mouse_emulation": {"enabled": True, "speed": 6, "scroll_speed": 1},
               "keyboard_emulation": {"enabled": True}},
        mesa=[{"pref": "p1", "jogador": 1, "uniq": UM, "nome": "Régua", "via": "USB",
               "cor": "white", "transporte": "usb"}],
        conectados=[um], estados={})


CLIQUES: list[tuple[str, str, str, dict[str, Any]]] = [
    ("som", "02-controles.html", "volume",
     {"uniq": UM, "volume": "microfone", "valor": "42"}),
    ("luz", "04-iluminacao.html", "brilho-luzes",
     {"uniq": UM, "controle": "p1", "luzes": "forte"}),
    ("vibracao", "05-vibracao.html", "forca", {"uniq": UM, "forca": "max"}),
    ("mouse", "06-navegacao.html", "vel-cursor", {"valor": "11"}),
    ("teclado", "06-navegacao.html", "guardar-teclas",
     {"forma": {"tecla-r1": "KEY_LEFTCTRL+KEY_W"}}),
]


@pytest.mark.parametrize(("cartao", "aba", "gesto", "carga"), CLIQUES,
                         ids=[c[0] for c in CLIQUES])
def test_o_clique_basta_e_o_perfil_fica(
    cartao: str, aba: str, gesto: str, carga: dict[str, Any]
) -> None:
    """Régua 6: o gesto do cartão grava no clique, sem «Salvar» nem «Aplicar»."""
    pac = _pacotes()
    caminho = save_profile(_perfil("Jogo X"))
    antes = caminho.read_bytes()
    fn = pac.gesto_da_pagina(aba, gesto)
    assert fn is not None, f"{aba}·{gesto} sem dono"
    fn(_contexto(pac, "Jogo X"), dict(carga), _Ponte())
    assert caminho.read_bytes() == antes, f"o clique em «{cartao}» mudou o perfil"
    relido = m.carregar_maquina().computador
    assert not opc.computador_vazio(relido), f"o clique em «{cartao}» não chegou ao computador"


def test_o_clique_grava_no_perfil_que_sobrepoe_o_cartao() -> None:
    """O mesmo clique, com o jogo que já escolheu a luz do P1: vai ao perfil."""
    pac = _pacotes()
    save_profile(_perfil("Jogo X", controllers={
        P1: {"leds": {"player_led_brightness": "medio"}}}))  # noqa-acento: chave ASCII
    fn = pac.gesto_da_pagina("04-iluminacao.html", "brilho-luzes")
    fn(_contexto(pac, "Jogo X"), {"uniq": UM, "controle": "p1", "luzes": "forte"}, _Ponte())
    assert load_profile("Jogo X").controllers[P1].leds.player_led_brightness == "forte"
    assert opc.computador_vazio(opc.o_computador())


def _handlers(ativo: str | None) -> Any:
    from types import SimpleNamespace

    from hefesto_dualsense4unix.daemon.ipc_handlers import IpcHandlersMixin

    class _H(IpcHandlersMixin):
        def __init__(self) -> None:
            self.store = SimpleNamespace(active_profile=ativo)  # type: ignore[assignment]
            self.controller = SimpleNamespace(  # type: ignore[assignment]
                describe_controllers=lambda: [{"connected": True, "uniq": UM}])
            self.daemon = None  # type: ignore[assignment]

    return _H()


@pytest.mark.parametrize("ativo", ["Jogo X", None], ids=["com-perfil", "sem-perfil"])
def test_o_daemon_grava_a_barra_do_motor_pelo_dono(ativo: str | None) -> None:
    """`rumble.motores.set`: o perfil sem a vibração do P1 deixa a barra no computador."""
    import asyncio

    caminho = save_profile(_perfil("Jogo X"))
    antes = caminho.read_bytes()
    h = _handlers(ativo)
    corpo = asyncio.run(h._handle_rumble_motores_set({"uniq": UM, "forte_pct": 40}))
    assert corpo["status"] == "ok" and corpo["onde"] == opc.COMPUTADOR, corpo
    assert caminho.read_bytes() == antes
    assert opc.o_computador().controles[P1].rumble.motor_forte_pct == 40


CONTROLES_DA_CASA = [f"aabbcc0000{n:02x}" for n in range(1, 5)]


def _freestyle_da_forma_dela() -> Profile:
    """O Freestyle com todas as seções, valores sintéticos."""
    return Profile.model_validate({
        "name": "Freestyle", "match": {"type": "any"},
        "leds": {"lightbar": [10, 20, 200], "lightbar_brightness": 0.6},
        "rumble": {"policy": "max"},
        "speaker": {"volume": 150, "muted": False},
        "mouse": {"enabled": False, "speed": 9, "scroll_speed": 3},
        "button_actions": {"cross": "KEY_ENTER", "ps": "__NADA__"},
        "key_bindings": {"r1": ["KEY_F11"]},
        "teclado_emulado": True,
        "controllers": {
            c: {"leds": {"lightbar": [0, 255, 0]}, "speaker": {"volume": 90},
                "mic": {"volume": 70}, "rumble": {"motor_forte_pct": 60},
                **({"sensores": {"giroscopio": False}} if i == 0 else {})}
            for i, c in enumerate(CONTROLES_DA_CASA[:2])
        },
    })


def _os_vinte_e_oito() -> list[Profile]:
    """Os outros 28 perfis, na forma das contagens da sprint (§2), valores sintéticos."""
    import random

    sorte = random.Random(110)
    perfis: list[Profile] = []
    entradas = 0
    for i in range(28):
        dados: dict[str, Any] = {"name": f"Jogo {i:02d}",
                                 "match": {"type": "criteria", "window_class": [f"j{i}"]}}
        if i < 10:
            dados["leds"] = sorte.choice([
                {"lightbar": [10, 20, 200], "lightbar_brightness": 0.6},
                {},
                {"lightbar": [255, 0, 0]},
            ])
            dados["rumble"] = sorte.choice([{"policy": "max"}, {},
                                            {"policy": "custom", "custom_mult": 1.3}])
        if 10 <= i < 18:
            dados["mouse"] = {"enabled": True, "speed": sorte.choice([9, 6, 11]),
                              "scroll_speed": sorte.choice([3, 1])}
        if i == 18:
            dados["teclado_emulado"] = True
        if 19 <= i < 28:
            controles: dict[str, Any] = {}
            quantos = 4 if i < 21 else 3
            for c in CONTROLES_DA_CASA[:quantos]:
                if entradas >= 29:
                    break
                entradas += 1
                entrada: dict[str, Any] = {"leds": sorte.choice([
                    {"lightbar": [0, 255, 0]}, {"lightbar": [9, 9, 9]},
                    {"lightbar_brightness": 0.2}])}
                if sorte.random() < 0.9:
                    entrada["speaker"] = sorte.choice([{"volume": 90}, {"volume": 40}])
                    entrada["mic"] = sorte.choice([{"volume": 70}, {"volume": 30}])
                if sorte.random() < 0.55:
                    entrada["rumble"] = sorte.choice([{"motor_forte_pct": 60},
                                                      {"motor_fraco_pct": 20}])
                if sorte.random() < 0.15:
                    entrada["sensores"] = {"giroscopio": False}
                controles[c] = entrada
            dados["controllers"] = controles
        perfis.append(Profile.model_validate(dados))
    return perfis


def test_a_migracao_nao_muda_nenhum_valor_efetivo() -> None:
    """Régua 5: depois da migração, cada perfil vale o mesmo que valia, campo a campo."""
    from hefesto_dualsense4unix.utils.xdg_paths import profiles_dir

    perfis = [_freestyle_da_forma_dela(), *_os_vinte_e_oito()]
    caminhos = {p.name: save_profile(p) for p in perfis}
    antes = {nome: caminho.read_bytes() for nome, caminho in caminhos.items()}

    saidas = opc.migrar_uma_vez()
    assert saidas is not None and saidas, "a migração não tirou nada de ninguém"
    computador = opc.o_computador()
    assert computador.migrado is True
    assert computador.global_.leds.lightbar == (10, 20, 200)
    assert computador.global_.button_actions == {"cross": "KEY_ENTER"}

    vazio = m.ComputadorDeclarado()
    for nome, caminho in caminhos.items():
        copia = caminho.with_name(caminho.name + opc.SUFIXO_DA_COPIA)
        if nome not in saidas:
            assert caminho.read_bytes() == antes[nome], f"{nome} mudou sem constar"
            continue
        assert copia.exists(), f"{nome} foi reescrito sem a cópia de antes"
        de_antes = Profile.model_validate(json.loads(copia.read_text(encoding="utf-8")))
        depois = load_profile(nome)
        valia = opc.efetivo(de_antes, vazio)
        vale = opc.efetivo(depois, computador)
        isentos = {k for k in valia if k[0] == "global" and len(k) == 3
                   and k[1] in ("leds", "rumble")
                   and k not in {("global", s, c) for s in ("leds", "rumble")
                                 for c in opc.escolhas_globais_do_jogo(de_antes, s)}}
        for k in opc._escolhas(de_antes):
            if k in isentos:
                continue
            assert vale.get(k) == valia.get(k), (
                f"{nome}: {k} valia {valia.get(k)!r}, vale {vale.get(k)!r}")
        de_antes = de_antes.model_copy(update={
            "button_actions": opc._sem_o_ps_da_tabela(de_antes.button_actions) or None})
        assert opc.efetivo(de_antes, computador) == vale, f"{nome} mudou com o mesmo computador"
    freestyle = load_profile("Freestyle")
    assert freestyle.controllers is None
    assert freestyle.button_actions is None
    assert not list(profiles_dir().glob("*.json.antes-do-computador.json"))


def test_a_migracao_roda_uma_vez() -> None:
    """A marca segura: a segunda partida não semeia nem tira de novo."""
    save_profile(_freestyle_da_forma_dela())
    assert opc.migrar_uma_vez() is not None
    assert opc.migrar_uma_vez() is None


def test_sem_freestyle_o_computador_nasce_das_velocidades_de_agora(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    from hefesto_dualsense4unix.utils import session

    monkeypatch.setattr(session, "load_mouse_preference", lambda: (True, 11, 4))
    save_profile(_perfil("Jogo X", mouse={"enabled": True, "speed": 11, "scroll_speed": 4}))
    opc.migrar_uma_vez()
    computador = opc.o_computador()
    assert (computador.global_.mouse.speed, computador.global_.mouse.scroll_speed) == (11, 4)
    jogo = load_profile("Jogo X")
    assert not opc.escolhas_globais_do_jogo(jogo, "mouse"), "a velocidade igual ficou no jogo"
    assert jogo.mouse is not None and jogo.mouse.enabled is True


def test_o_ps_da_linha_vai_para_a_tabela() -> None:
    """O ``__NADA__`` do PS na linha das Definições sai do perfil (é do ⑥)."""
    save_profile(_perfil("Jogo X", button_actions={"ps": "__STEAM__",
                                                   "cross": "KEY_BACKSPACE"}))
    opc.migrar_uma_vez()
    assert load_profile("Jogo X").button_actions == {"cross": "KEY_BACKSPACE"}


@pytest.mark.parametrize(("token", "faz"), [("__NADA__", "nada"),
                                            ("__STEAM__", "abrir_a_steam")])
def test_o_ps_do_freestyle_muda_de_dono_sem_se_perder(token: str, faz: str) -> None:
    """O PS do Freestyle na linha das Definições vira o ⑥ da tabela, e não some."""
    save_profile(Profile.model_validate({"name": "Freestyle", "match": {"type": "any"},
                                         "button_actions": {"ps": token}}))
    opc.migrar_uma_vez()
    assert m.carregar_maquina().gestos["ps"].faz == faz
    assert "ps" not in (load_profile("Freestyle").button_actions or {})


def test_o_sexto_ja_escolhido_vence_o_ps_do_freestyle() -> None:
    assert m.gravar_maquina({"gestos": {"ps": {"faz": "abrir_o_hefesto"}}})
    save_profile(Profile.model_validate({"name": "Freestyle", "match": {"type": "any"},
                                         "button_actions": {"ps": "__NADA__"}}))
    opc.migrar_uma_vez()
    assert m.carregar_maquina().gestos["ps"].faz == "abrir_o_hefesto"


def test_a_linha_do_ps_so_digita() -> None:
    """Régua 8: a lista da linha do PS não tem «Abrir a Steam» nem «— Nada —»."""
    from types import SimpleNamespace

    from hefesto_dualsense4unix.core import acoes_de_botao as acoes
    from hefesto_dualsense4unix.core import acoes_do_gesto as ag
    from hefesto_dualsense4unix.daemon.subsystems import hotkey

    do_ps = {r for _g, rotulos in acoes.por_grupo(acoes.BOTAO_PS) for r in rotulos}
    assert not do_ps & {"Abrir a Steam", "— Nada —"}, sorted(do_ps)
    assert "— Sem tecla —" in do_ps
    das_outras = {r for _g, rotulos in acoes.por_grupo() for r in rotulos}
    assert "— Sem tecla —" not in das_outras and "Abrir a Steam" in das_outras

    de_fabrica = SimpleNamespace(ps_button_action="steam")
    for antigo in (acoes.TOKEN_NADA, acoes.TOKEN_STEAM):
        assert hotkey._a_metade_da_maquina(de_fabrica, antigo) == ag.ABRIR_A_STEAM
    calado = SimpleNamespace(declarada=True, faz=ag.NADA)
    assert hotkey._a_metade_da_maquina(de_fabrica, acoes.TOKEN_STEAM, calado) == ag.NADA


def test_a_frase_fala_a_lingua_da_tela() -> None:
    """Régua 7: o que é de fábrica ou do computador não é «menos», e chave crua não sai.

    Às 19h15 de 01/10 a janela escreveu «menos: button_actions, remapeamento,
    movimento e mais 8» sobre uma troca que deu certo.

    MORDIDA: devolver o ``!= "aplicado"`` sozinho ao ``relato_da_ativacao``
    reprova na primeira frase.
    """
    from hefesto_dualsense4unix.app.actions import profiles_actions as pa

    certa = {"leds": "aplicado", "button_actions": "de_fabrica", "remapeamento": "de_fabrica",
             "movimento": "desligado", "speaker": "do_computador",
             "keyboard": "ignorado_sem_device"}
    assert pa.mensagem_de_ativacao("Jogo X", {"secoes": certa}) == "Perfil ativado: Jogo X"

    caiu = {"leds": "aplicado", "button_actions": "falhou", "remapeamento": "falhou",
            "movimento": "falhou"}
    frase = pa.mensagem_de_ativacao("Jogo X", {"secoes": caiu})
    assert "menos" in frase, frase
    for crua in ("button_actions", "remapeamento", "movimento"):
        assert crua not in frase, frase


@pytest.mark.parametrize(("cartao", "secao", "esperado"), [
    ("luz", "leds", {"lightbar": [10, 20, 200]}),
    ("sensores", "sensores", {"giroscopio": True, "acelerometro": True}),
    ("som", "speaker", {"volume": 70}),
])
def test_so_neste_jogo_num_controle_sem_entrada_copia_o_que_vale(
    cartao: str, secao: str, esperado: dict[str, Any]
) -> None:
    """O controle sem entrada vale o global da vista (ou o de fábrica): é isso que se copia."""
    _computador({"global": {"leds": {"lightbar": [10, 20, 200]},
                            "speaker": {"volume": 70}}})
    save_profile(_perfil("Jogo X"))
    opc.so_neste_jogo(cartao, UM, "Jogo X")
    perfil = load_profile("Jogo X")
    assert opc.sobrepoe(perfil, cartao, UM)
    gravado = getattr(perfil.controllers[opc.chave_no_perfil(perfil, UM)], secao)
    dados = gravado.model_dump(mode="json")
    assert {k: dados[k] for k in esperado} == esperado, dados


@pytest.mark.parametrize("porta", ["status", "chip"])
def test_entrar_na_navegacao_nao_da_ao_jogo_o_que_e_do_computador(porta: str) -> None:
    """O «Status do Modo» e a entrada à mão na Navegação gravam o liga, e só ele, no jogo."""
    from hefesto_dualsense4unix.profiles import manager

    _computador({"global": {"mouse": {"speed": 11, "scroll_speed": 3},
                            "teclado_emulado": True}})
    save_profile(_perfil("Jogo X"))
    if porta == "status":
        manager.gravar_a_navegacao_no_perfil_ativo(
            "Jogo X", ligado=False, porta="ipc", velocidades=(11, 3))
    else:
        manager.gravar_o_modo_no_perfil_ativo(
            "Jogo X", kind="desktop", porta="ipc", mouse_ligado=True, velocidades=(11, 3))
    jogo = load_profile("Jogo X")
    assert jogo.mouse is not None and jogo.mouse.enabled is (porta == "chip")
    assert not opc.sobrepoe(jogo, "mouse"), jogo.mouse
    assert not opc.sobrepoe(jogo, "teclado"), jogo.teclado_emulado
    _computador({"global": {"mouse": {"speed": 4, "scroll_speed": 2},
                            "teclado_emulado": True}})
    vista = opc.o_que_vale(load_profile("Jogo X"))
    assert (vista.mouse.speed, vista.mouse.scroll_speed) == (4, 2)
    if porta == "status":
        _computador({"global": {"teclado_emulado": True}})
        save_profile(_perfil("Jogo Y"))
        manager.gravar_a_navegacao_no_perfil_ativo(
            "Jogo Y", ligado=False, porta="ipc", velocidades=(6, 1))
        assert opc.o_computador().global_.teclado_emulado is False
        assert load_profile("Jogo Y").teclado_emulado is None


def test_o_status_no_jogo_que_ja_tem_o_teclado_grava_nele() -> None:
    """O jogo que já sobrepõe o teclado guarda o lado do teclado do «Status do Modo»."""
    from hefesto_dualsense4unix.profiles import manager

    _computador({"global": {"teclado_emulado": True}})
    save_profile(_perfil("Jogo X", teclado_emulado=True))
    manager.gravar_a_navegacao_no_perfil_ativo("Jogo X", ligado=False, porta="ipc")
    assert load_profile("Jogo X").teclado_emulado is False
    assert opc.o_computador().global_.teclado_emulado is True
