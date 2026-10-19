"""A aba Iluminação do todo: o efeito da barra, o laço que o anima e o desenho de quatro colunas.

MORDIDAS: devolver uma cor ao `FORA_DA_GUIA`, tirar o silêncio com o jogo pintando, tirar o teto
de 30 quadros por segundo, tirar o `soltar` ao parar, subir o teto do piscar, deixar o Modo
automático animar, voltar o `?` ou o «Desligar» ao desenho reprovam. E o quadro pela camada da
usuária, que apaga a cor do perfil daquele controle e o «Sem efeito», e o efeito que não espera o
pulso do tiro.
"""

from __future__ import annotations

import pathlib
import re
import sys
from itertools import pairwise
from types import SimpleNamespace
from typing import Any

import pytest

from hefesto_dualsense4unix.daemon.subsystems import luz_animada as luz
from hefesto_dualsense4unix.profiles.schema import (
    BASES_DA_LUZ,
    TETO_DE_CORES_DO_EFEITO,
    ControllerOverrides,
    EfeitoDaLuz,
    LedsConfig,
    MatchAny,
    Profile,
    escrever_o_efeito_da_luz,
    ler_o_efeito_da_luz,
)

RAIZ = pathlib.Path(__file__).resolve().parents[2]
sys.path.insert(0, str(RAIZ / "src/hefesto_dualsense4unix/interface"))

MOCKUP = RAIZ / "mockup" / "04-iluminacao.html"
CHROME = pathlib.Path("/usr/bin/google-chrome")
UNIQ = "aa:bb:cc:00:00:01"
OUTRO = "aa:bb:cc:00:00:02"
VERMELHO = (255, 0, 0)


def _doc() -> str:
    """O desenho sem estilo, script e comentário: o que a pessoa vê e o que ela aciona."""
    bruto = MOCKUP.read_text(encoding="utf-8")
    sem_comentario = re.sub(r"<!--.*?-->", "", bruto, flags=re.S)
    return re.sub(r"<(style|script)\b[^>]*>.*?</\1>", "", sem_comentario, flags=re.S)


# ---------------------------------------------------------------- o texto que o perfil guarda


@pytest.mark.parametrize("base", BASES_DA_LUZ)
def test_o_efeito_escrito_volta_igual_lido(base: str) -> None:
    cores = [] if base == "arco-iris" else ["#ff0000", "#00FF80"]  # (noqa-acento) chave ASCII
    texto = escrever_o_efeito_da_luz(base, cores, 7)
    lido = ler_o_efeito_da_luz(texto)
    assert lido == EfeitoDaLuz(base, tuple(
        (int(c[1:3], 16), int(c[3:5], 16), int(c[5:7], 16)) for c in cores), 7)


@pytest.mark.parametrize("texto", [
    None, 3, "", "respirar", "respirar;FF0000", "rodar;FF0000;4", "respirar;FF00;4",
    "respirar;ZZZZZZ;4", "respirar;;4", "piscar;FF0000;0", "piscar;FF0000;11",
    "piscar;FF0000;rapido", "respirar;" + ",".join(["FF0000"] * 9) + ";4"])
def test_texto_que_nao_e_efeito_le_none_e_o_perfil_o_descarta(texto: Any) -> None:
    assert ler_o_efeito_da_luz(texto) is None
    if isinstance(texto, str):
        assert LedsConfig(efeito=texto).efeito is None, "um enfeite ilegível derrubaria o perfil"


def test_o_teto_de_cores_do_efeito_e_oito() -> None:
    cores = ",".join(["FF0000"] * TETO_DE_CORES_DO_EFEITO)
    assert TETO_DE_CORES_DO_EFEITO == 8
    assert ler_o_efeito_da_luz(f"respirar;{cores};4") is not None
    assert ler_o_efeito_da_luz(f"respirar;{cores},00FF00;4") is None


def test_o_arco_iris_nao_precisa_de_cor_e_o_resto_precisa() -> None:
    assert ler_o_efeito_da_luz("arco-iris;;4") is not None  # (noqa-acento) chave ASCII
    assert ler_o_efeito_da_luz("piscar;;4") is None


# ---------------------------------------------------------------- a cor em cada instante


def test_o_respirar_abaixa_ate_o_fundo_e_sobe_ate_a_cor_cheia() -> None:
    efeito = EfeitoDaLuz("respirar", (VERMELHO,), 4)
    periodo = luz.periodo_do_respirar_s(4)
    fundo = luz.cor_no_instante(efeito, 0.0)
    topo = luz.cor_no_instante(efeito, periodo / 2)
    assert topo == VERMELHO
    assert 0 < fundo[0] < 40 and fundo[1] == fundo[2] == 0, "o fundo abaixa, mas não apaga"
    assert luz.cor_no_instante(efeito, periodo) == fundo, "uma respiração fecha no fundo"


def test_o_respirar_troca_de_cor_a_cada_respiracao() -> None:
    efeito = EfeitoDaLuz("respirar", (VERMELHO, (0, 0, 255)), 4)
    periodo = luz.periodo_do_respirar_s(4)
    assert luz.cor_no_instante(efeito, periodo / 2) == VERMELHO
    assert luz.cor_no_instante(efeito, periodo * 1.5) == (0, 0, 255)
    assert luz.cor_no_instante(efeito, periodo * 2.5) == VERMELHO


def test_o_piscar_acende_e_abaixa_ate_o_piso_na_cor_dele() -> None:
    """Sobe a cor cheia e desce ao piso, sem apagar (a onda quadrada saiu em 15/10)."""
    efeito = EfeitoDaLuz("piscar", (VERMELHO,), 4)
    meio = 0.5 / luz.frequencia_do_piscar_hz(4)
    assert luz.cor_no_instante(efeito, 0.0) == VERMELHO
    baixo = luz.cor_no_instante(efeito, meio + 0.01)
    assert 0 < baixo[0] < 60 and baixo[1] == baixo[2] == 0


def test_o_arco_iris_gira_o_matiz_e_fecha_a_volta() -> None:
    efeito = EfeitoDaLuz("arco-iris", (), 5)  # (noqa-acento) chave ASCII
    volta = luz.periodo_do_arco_iris_s(5)
    assert luz.cor_no_instante(efeito, 0.0) == VERMELHO
    assert luz.cor_no_instante(efeito, volta / 3) == (0, 255, 0)
    assert luz.cor_no_instante(efeito, volta) == VERMELHO


def test_o_ritmo_mais_alto_anda_mais_depressa() -> None:
    assert luz.periodo_do_respirar_s(10) < luz.periodo_do_respirar_s(1)
    assert luz.periodo_do_arco_iris_s(10) < luz.periodo_do_arco_iris_s(1)
    assert luz.frequencia_do_piscar_hz(10) > luz.frequencia_do_piscar_hz(1)


def test_o_piscar_nunca_passa_de_tres_lampejos_por_segundo() -> None:
    """WCAG 2.3.1. MORDIDA: subir o `TETO_DO_PISCAR_HZ` (a escala do ritmo para nele, e o teto é
    quem segura uma escala mais rápida)."""
    assert luz.TETO_DO_PISCAR_HZ <= 3.0
    assert max(luz.frequencia_do_piscar_hz(r) for r in range(1, 11)) <= 3.0
    efeito = EfeitoDaLuz("piscar", (VERMELHO,), 10)
    amostras = [luz.cor_no_instante(efeito, i / 1000) != (0, 0, 0) for i in range(1000)]
    subidas = sum(1 for a, b in pairwise(amostras) if b and not a)
    assert subidas <= 3, f"{subidas} lampejos em um segundo"


# ---------------------------------------------------------------- o laço, com tudo injetado


class _Barra:
    def __init__(self) -> None:
        self.escritos: list[tuple[str, tuple[int, int, int]]] = []
        self.soltos: list[str] = []

    def laco(self, **kw: Any) -> luz.LuzAnimada:
        return luz.LuzAnimada(lambda u, c: self.escritos.append((u, c)), self.soltos.append, **kw)


def _plano(efeito: EfeitoDaLuz, brilho: float = 1.0) -> dict[str, luz.PlanoDoControle]:
    return {UNIQ: luz.PlanoDoControle(efeito, brilho)}


def test_no_maximo_trinta_quadros_por_segundo_por_controle() -> None:
    """MORDIDA: tirar o corte do intervalo mínimo."""
    barra = _Barra()
    laco = barra.laco()
    plano = _plano(EfeitoDaLuz("arco-iris", (), 10))  # (noqa-acento) chave ASCII
    for ms in range(1000):
        laco.tique(ms / 1000, plano)
    assert 0 < len(barra.escritos) <= 31, len(barra.escritos)


def test_quadro_igual_ao_anterior_nao_sai() -> None:
    barra = _Barra()
    laco = barra.laco()
    plano = _plano(EfeitoDaLuz("piscar", (VERMELHO,), 1))
    for ms in range(0, 400, 40):
        laco.tique(ms / 1000, plano)
    assert len(barra.escritos) == 1, "o piscar parado em aceso repetiu o mesmo quadro"


def test_o_brilho_do_perfil_escala_o_quadro() -> None:
    barra = _Barra()
    barra.laco().tique(0.0, _plano(EfeitoDaLuz("piscar", (VERMELHO,), 4), 0.5))
    quadro = barra.escritos[0][1]
    assert quadro == luz.cor_com_o_brilho(VERMELHO, 0.5)
    assert 0 < quadro[0] < 255 and quadro[1] == quadro[2] == 0, quadro


def test_parar_solta_a_barra_uma_vez_so() -> None:
    """MORDIDA: tirar o `soltar` do `parar`: a barra fica no último quadro do efeito."""
    barra = _Barra()
    laco = barra.laco()
    laco.tique(0.0, _plano(EfeitoDaLuz("piscar", (VERMELHO,), 4)))
    assert laco.tocando == {UNIQ}
    laco.tique(0.1, {})
    laco.tique(0.2, {})
    assert barra.soltos == [UNIQ]
    assert laco.tocando == frozenset()


def test_controle_calado_para_de_escrever_e_solta() -> None:
    barra = _Barra()
    laco = barra.laco()
    plano = _plano(EfeitoDaLuz("arco-iris", (), 10))  # (noqa-acento) chave ASCII
    laco.tique(0.0, plano)
    laco.tique(0.1, plano, calados=frozenset({UNIQ}))
    laco.tique(0.2, plano, calados=frozenset({UNIQ}))
    assert len(barra.escritos) == 1 and barra.soltos == [UNIQ]
    laco.tique(0.3, plano)
    assert len(barra.escritos) == 2, "passado o silêncio, o efeito volta"


def test_um_controle_nao_atrasa_o_outro() -> None:
    barra = _Barra()
    laco = barra.laco()
    plano = {**_plano(EfeitoDaLuz("piscar", (VERMELHO,), 4)),
             OUTRO: luz.PlanoDoControle(EfeitoDaLuz("piscar", ((0, 0, 255),), 4), 1.0)}
    assert laco.tique(0.0, plano) == 2
    assert {u for u, _c in barra.escritos} == {UNIQ, OUTRO}


# ---------------------------------------------------------------- o plano que o perfil manda


def _perfil(global_: str | None = None, dele: Any = "ausente", modo: str | None = None,
            brilho: float = 1.0) -> Profile:
    leds = LedsConfig(efeito=global_, modo=modo, lightbar_brightness=brilho)
    overrides: dict[str, ControllerOverrides] = {}
    if dele != "ausente":
        overrides[UNIQ] = ControllerOverrides(leds=LedsConfig(efeito=dele))
    return Profile(name="regua", match=MatchAny(), leds=leds, controllers=overrides)


def test_o_efeito_do_perfil_vale_para_quem_nao_escolheu() -> None:
    plano = luz.plano_do_perfil(_perfil("piscar;FF0000;4"), [UNIQ, OUTRO])
    assert set(plano) == {UNIQ, OUTRO}


def test_o_efeito_do_controle_vence_o_do_perfil() -> None:
    plano = luz.plano_do_perfil(_perfil("piscar;FF0000;4", dele="respirar;00FF00;2"), [UNIQ, OUTRO])
    assert plano[UNIQ].efeito.base == "respirar"
    assert plano[OUTRO].efeito.base == "piscar"


def test_luz_fixa_escrita_no_controle_nao_cai_no_efeito_do_perfil() -> None:
    plano = luz.plano_do_perfil(_perfil("piscar;FF0000;4", dele=None), [UNIQ, OUTRO])
    assert set(plano) == {OUTRO}


def test_sem_efeito_no_perfil_nao_ha_plano_e_o_laco_nao_escreve() -> None:
    assert luz.plano_do_perfil(_perfil(None), [UNIQ]) == {}


def test_no_modo_automatico_nada_anima() -> None:
    """MORDIDA: tirar a guarda do `plano_do_perfil`."""
    assert luz.plano_do_perfil(
        _perfil("piscar;FF0000;4", modo="automatico"), [UNIQ]) == {}  # (noqa-acento) chave
    assert luz.plano_do_perfil(_perfil("piscar;FF0000;4", modo="personalizado"), [UNIQ])


def test_barra_apagada_no_brilho_zero_nao_anima() -> None:
    assert luz.plano_do_perfil(_perfil("piscar;FF0000;4", brilho=0.0), [UNIQ]) == {}


# ---------------------------------------------------------------- calar quando o jogo pinta


def _daemon(visto: dict[str, float], backend: str = "uhid", jogo: bool = True,
            sessao: bool = False) -> Any:
    pad = SimpleNamespace(backend=backend, visto_ha_s=visto, game_open=sessao)
    return SimpleNamespace(
        controller=SimpleNamespace(primary_uniq=UNIQ), _last_state=None,
        _gamepad_device=pad, display_authority="game" if jogo else "unknown",
        _coop_manager=None, store=SimpleNamespace(active_profile="regua"))


def _passo(monkeypatch: pytest.MonkeyPatch, daemon: Any) -> tuple[luz.Passo, _Barra]:
    barra = _Barra()
    monkeypatch.setattr(luz, "perfil_ativo", lambda _d: _perfil("piscar;FF0000;4"))
    return luz.Passo(daemon, barra.laco()), barra


def test_sem_jogo_o_efeito_toca(monkeypatch: pytest.MonkeyPatch) -> None:
    passo, barra = _passo(monkeypatch, _daemon({}, jogo=False))
    assert passo(10.0) == 1 and barra.escritos[0][0] == UNIQ


def test_com_o_jogo_pintando_a_barra_o_efeito_cala(monkeypatch: pytest.MonkeyPatch) -> None:
    """MORDIDA: tirar o silêncio: o efeito pintaria por cima do jogo."""
    passo, barra = _passo(monkeypatch, _daemon({"lightbar": 0.5}))
    assert passo(10.0) == 0 and barra.escritos == []


def test_com_a_sessao_do_jogo_aberta_e_a_barra_dele_o_efeito_cala(
        monkeypatch: pytest.MonkeyPatch) -> None:
    """O jogo pintou há mais de 3 s, mas a sessão dele segue aberta: a cor ainda é dele."""
    passo, _barra = _passo(monkeypatch, _daemon({"lightbar": 9.0}, sessao=True))
    assert passo(10.0) == 0


def test_com_o_jogo_calado_na_barra_o_efeito_toca(monkeypatch: pytest.MonkeyPatch) -> None:
    passo, _barra = _passo(monkeypatch, _daemon({"lightbar": 9.0}))
    assert passo(10.0) == 1


def test_no_modo_nativo_o_hefesto_nao_pinta_nada(monkeypatch: pytest.MonkeyPatch) -> None:
    passo, barra = _passo(monkeypatch, _daemon({}, backend="nenhum"))
    assert passo(10.0) == 0 and barra.escritos == []


def test_o_jogo_que_sai_devolve_o_efeito_no_tique_seguinte(monkeypatch: pytest.MonkeyPatch) -> None:
    daemon = _daemon({"lightbar": 0.5})
    passo, _barra = _passo(monkeypatch, daemon)
    passo(10.0)
    daemon._gamepad_device.visto_ha_s = {"lightbar": 9.0}
    assert passo(10.1) == 1


def test_o_perfil_so_e_relido_a_cada_meio_segundo(monkeypatch: pytest.MonkeyPatch) -> None:
    leituras: list[float] = []
    barra = _Barra()
    monkeypatch.setattr(luz, "perfil_ativo",
                        lambda _d: leituras.append(1.0) or _perfil("piscar;FF0000;4"))
    passo = luz.Passo(_daemon({}, jogo=False), barra.laco())
    for ms in range(0, 400, 33):
        passo(ms / 1000)
    assert len(leituras) == 1


def _passo_com_o_tato(monkeypatch: pytest.MonkeyPatch, efeito: str) -> tuple[Any, Any, _Barra]:
    from hefesto_dualsense4unix.daemon.subsystems.tato_vivo import TatoVivo

    daemon = _daemon({}, jogo=False)
    motor = TatoVivo()
    daemon._tato_vivo = motor
    monkeypatch.setattr(luz, "perfil_ativo", lambda _d: _perfil(efeito))
    barra = _Barra()
    return luz.Passo(daemon, barra.laco()), motor, barra


def test_o_pulso_do_tiro_segura_a_barra_e_o_efeito_espera(
        monkeypatch: pytest.MonkeyPatch) -> None:
    """MORDIDA: tirar a pausa: o quadro seguinte apaga o pulso do tiro 33 ms depois."""
    from hefesto_dualsense4unix.daemon.subsystems.tato_vivo import CANAL_LUZ

    passo, motor, barra = _passo_com_o_tato(monkeypatch, "arco-iris;;10")  # (noqa-acento) chave
    assert passo(10.0) == 1
    motor._pendentes[(UNIQ, CANAL_LUZ)] = 99.0
    assert motor.segurando(CANAL_LUZ) == {UNIQ}
    assert passo(10.1) == 0 and barra.soltos == [], "o pulso é do tato: o efeito só espera"
    del motor._pendentes[(UNIQ, CANAL_LUZ)]
    assert passo(10.2) == 1


def test_na_volta_do_pulso_o_quadro_sai_mesmo_igual_ao_ultimo(
        monkeypatch: pytest.MonkeyPatch) -> None:
    """A volta do pulso repintou a barra com a cor do perfil: o piscar parado em aceso tem de
    escrever de novo. MORDIDA: guardar o último quadro durante a pausa."""
    from hefesto_dualsense4unix.daemon.subsystems.tato_vivo import CANAL_LUZ

    passo, motor, _barra = _passo_com_o_tato(monkeypatch, "piscar;FF0000;1")
    assert passo(10.0) == 1
    motor._pendentes[(UNIQ, CANAL_LUZ)] = 99.0
    assert passo(10.1) == 0
    del motor._pendentes[(UNIQ, CANAL_LUZ)]
    assert passo(10.2) == 1


def _backend_com_o_perfil() -> tuple[Any, Any, Any]:
    """O backend real com o P2 vermelho no perfil e o global dele em outra cor."""
    from hefesto_dualsense4unix.daemon.state_store import StateStore
    from hefesto_dualsense4unix.profiles.manager import ProfileManager
    from hefesto_dualsense4unix.profiles.schema import MatchCriteria
    from tests.unit.test_backend_multi_controller import KEY_2, UNIQ_2
    from tests.unit.test_r20_camadas_de_saida import _backend

    backend, _h1, h2 = _backend()
    perfil = Profile(name="regua", match=MatchCriteria(window_class=["regua"]),
                     leds=LedsConfig(lightbar=(10, 20, 30)),
                     controllers={UNIQ_2: ControllerOverrides(leds=LedsConfig(lightbar=VERMELHO))})
    ProfileManager(controller=backend, store=StateStore()).apply(perfil, origin="autoswitch")
    assert h2.light.colors[-1] == VERMELHO
    return backend, h2, (UNIQ_2, KEY_2)


def test_o_fim_do_efeito_devolve_a_cor_do_perfil_daquele_controle(tmp_path: pathlib.Path,
        monkeypatch: pytest.MonkeyPatch) -> None:
    """MORDIDA: o quadro pela camada da usuária (`apply_output_for`) e o soltar que a limpa: o
    controle volta na cor global do perfil, não na dele."""
    from hefesto_dualsense4unix.profiles import loader

    monkeypatch.setattr(loader, "profiles_dir", lambda ensure=False: tmp_path)
    backend, h2, (uniq, key) = _backend_com_o_perfil()
    escrever, soltar = luz.escritor_de_producao(SimpleNamespace(controller=backend))
    escrever(uniq, (0, 200, 200))
    assert h2.light.colors[-1] == (0, 200, 200)
    assert backend.resolved_led_for(uniq) == VERMELHO, "o quadro não é estado desejado"
    soltar(uniq)
    assert h2.light.colors[-1] == VERMELHO
    assert backend._merged_desired_for_key(key).led == VERMELHO


def test_o_sem_efeito_fica_apagado_depois_que_o_efeito_para(tmp_path: pathlib.Path,
        monkeypatch: pytest.MonkeyPatch) -> None:
    """O «Sem efeito» manda o preto a 0% e grava; o laço relê o disco até meio segundo depois e
    para. MORDIDA: o soltar que limpa o `led` da usuária reacende a barra."""
    from hefesto_dualsense4unix.core.controller import OutputSpec
    from hefesto_dualsense4unix.profiles import loader

    monkeypatch.setattr(loader, "profiles_dir", lambda ensure=False: tmp_path)
    backend, h2, (uniq, _key) = _backend_com_o_perfil()
    escrever, soltar = luz.escritor_de_producao(SimpleNamespace(controller=backend))
    escrever(uniq, (0, 200, 200))
    backend.apply_output_for(uniq, OutputSpec(led=(0, 0, 0)), brilho_da_cor=0.0)
    soltar(uniq)
    assert h2.light.colors[-1] == (0, 0, 0)


def test_o_quadro_nao_tira_a_cor_que_o_jogo_pintou(tmp_path: pathlib.Path,
        monkeypatch: pytest.MonkeyPatch) -> None:
    """O quadro que chega antes de o laço calar não solta a camada do jogo."""
    from hefesto_dualsense4unix.profiles import loader

    monkeypatch.setattr(loader, "profiles_dir", lambda ensure=False: tmp_path)
    backend, _h2, (uniq, _key) = _backend_com_o_perfil()
    backend.set_game_output_for(uniq, led=(0, 255, 0))
    antes = backend._game_output_by_uniq.get(uniq)
    assert antes is not None and antes.led == (0, 255, 0)
    escrever, _soltar = luz.escritor_de_producao(SimpleNamespace(controller=backend))
    escrever(uniq, (0, 200, 200))
    assert backend._game_output_by_uniq.get(uniq) == antes


def test_backend_sem_a_ponte_nao_escreve() -> None:
    escrever, soltar = luz.escritor_de_producao(SimpleNamespace(controller=object()))
    assert escrever(UNIQ, VERMELHO) is False
    assert soltar(UNIQ) is None


# ---------------------------------------------------------------- o pacote da aba


def test_a_lista_de_efeitos_tem_sem_efeito_luz_fixa_e_os_seus() -> None:
    import pacotes  # noqa: F401
    from pacotes import a04_iluminacao as a04

    sozinha = a04.opcoes_do_efeito({})
    assert f'value="{a04.SEM_EFEITO}"' in sozinha and f'value="{a04.LUZ_FIXA}"' in sozinha
    # Desde 15/10/2026 a lista traz as bases em grupos; o grupo «Seus efeitos» só nasce com efeitos.
    assert 'optgroup label="Seus efeitos"' not in sozinha
    biblioteca = {"Alerta": {"nome": "Alerta", "base": "piscar",
                             "parametros": {"cores": "#FF0000", "ritmo": 6}}}
    com = a04.opcoes_do_efeito(biblioteca)
    assert 'optgroup label="Seus efeitos"' in com
    assert 'value="piscar;FF0000;6"' in com and ">Alerta<" in com
    assert "Desligar" not in com


def test_o_efeito_do_perfil_que_a_biblioteca_nao_tem_entra_com_o_nome_da_base() -> None:
    from pacotes import a04_iluminacao as a04

    html = a04.opcoes_do_efeito({}, "respirar;00FFFF;2")
    assert 'value="respirar;00FFFF;2"' in html and ">Respirar<" in html


def test_a_lista_mostra_luz_fixa_sem_efeito_e_o_que_o_controle_tem() -> None:
    from pacotes import a04_iluminacao as a04

    cru = {"leds": {"efeito": "piscar;FF0000;4"},
           "controllers": {"aabbcc000001": {"leds": {"efeito": None}}}}
    assert a04.escolha_da_lista(cru, UNIQ, 1.0) == a04.LUZ_FIXA
    assert a04.escolha_da_lista(cru, OUTRO, 1.0) == "piscar;FF0000;4"
    assert a04.escolha_da_lista(cru, OUTRO, 0.0) == a04.SEM_EFEITO


def test_o_efeito_vai_para_o_override_do_controle_e_luz_fixa_e_escrita() -> None:
    from pacotes import a04_iluminacao as a04

    base = Profile(name="regua", match=MatchAny(), leds=LedsConfig(efeito="piscar;FF0000;4"))
    com = a04._com_o_efeito_gravado(base, UNIQ, "respirar;00FFFF;2")
    assert com.controllers["aabbcc000001"].leds.efeito == "respirar;00FFFF;2"
    assert com.leds.efeito == "piscar;FF0000;4", "o efeito de um controle não vira o de todos"
    fixa = a04._com_o_efeito_gravado(com, UNIQ, None)
    leds = fixa.controllers["aabbcc000001"].leds
    assert leds.efeito is None and "efeito" in leds.model_fields_set


def test_efeito_numa_barra_apagada_religa_o_brilho() -> None:
    from pacotes import a04_iluminacao as a04

    apagado = Profile(name="regua", match=MatchAny(), leds=LedsConfig(lightbar_brightness=0.0))
    com = a04._com_o_efeito_gravado(apagado, UNIQ, "piscar;FF0000;4", religar=True)
    assert com.controllers["aabbcc000001"].leds.lightbar_brightness == 1.0


def _ctx() -> Any:
    import pacotes

    return pacotes.Contexto(
        state={"active_profile": ""},
        mesa=[{"pref": "p1", "jogador": 1, "uniq": UNIQ, "nome": "Régua", "via": "USB",
               "cor": "starlight-blue"}],
        conectados=[{"uniq": UNIQ, "connected": True, "transport": "usb", "index": 0,
                     "player": 1}],
        estados={})


@pytest.mark.parametrize("valor", ["inventado", "piscar;FF0000;99", "piscar;;4", ""])
def test_o_gesto_do_efeito_recusa_o_que_a_lista_nao_oferece(valor: str) -> None:
    import pacotes

    with pytest.raises(ValueError, match="não é um efeito"):
        pacotes.gesto_da_pagina("04-iluminacao.html", "efeito-da-luz")(
            _ctx(), {"uniq": UNIQ, "valor": valor}, None)


def test_o_gesto_do_efeito_grava_no_controle_e_o_computador_devolve() -> None:
    """A escolha chega ao disco da máquina, no controle da coluna, e o plano do laço a lê."""
    import pacotes
    from hefesto_dualsense4unix.profiles.o_padrao_do_computador import (
        o_computador,
        perfil_que_vale,
        perfil_vazio,
    )

    pacotes.gesto_da_pagina("04-iluminacao.html", "efeito-da-luz")(
        _ctx(), {"uniq": UNIQ, "valor": "respirar;00FFFF;2"}, None)
    dele = o_computador().controles["aabbcc000001"].leds
    assert dele is not None and dele.efeito == "respirar;00FFFF;2"
    vale = perfil_que_vale(perfil_vazio(), o_computador())
    assert vale.controllers["aabbcc000001"].leds.efeito == "respirar;00FFFF;2"


def test_o_gesto_do_efeito_sem_controle_recusa() -> None:
    import pacotes

    with pytest.raises(ValueError, match="em qual controle"):
        pacotes.gesto_da_pagina("04-iluminacao.html", "efeito-da-luz")(
            _ctx(), {"valor": "luz-fixa"}, None)


def _criar(forma: dict[str, Any]) -> None:
    import pacotes

    pacotes.gesto_da_pagina("04-iluminacao.html", "criar-efeito")(_ctx(), {"forma": forma}, None)


def test_criar_efeito_guarda_so_na_biblioteca_da_luz() -> None:
    from pacotes import a04_iluminacao as a04

    assert a04.meus_efeitos("luz") == {}
    _criar({"base": "piscar", "cores": "#ff0000,#00ff00", "ritmo": "6", "nome": "Alerta"})
    guardado = a04.meus_efeitos("luz")["Alerta"]
    assert guardado["base"] == "piscar"
    assert guardado["parametros"] == {"cores": "#FF0000,#00FF00", "ritmo": 6}
    assert a04.meus_efeitos("vibracao") == {} and a04.meus_efeitos("gatilhos") == {}
    assert a04.efeito_do_item(guardado) == "piscar;FF0000,00FF00;6"
    assert "Alerta" in a04.html_dos_efeitos()


def test_o_arco_iris_criado_nao_guarda_cor() -> None:
    from pacotes import a04_iluminacao as a04

    _criar({"base": "arco-iris", "cores": "#ff0000", "ritmo": "3", "nome": "Giro"})  # noqa-acento: chave ASCII
    assert a04.meus_efeitos("luz")["Giro"]["parametros"]["cores"] == ""


@pytest.mark.parametrize("forma,frase", [
    ({"base": "", "cores": "#FF0000", "ritmo": "4", "nome": "x"}, "como a luz se move"),
    ({"base": "piscar", "cores": "", "ritmo": "4", "nome": "x"}, "ao menos uma cor"),
    ({"base": "piscar", "cores": "vermelho", "ritmo": "4", "nome": "x"}, "não é válida"),
    ({"base": "piscar", "cores": ",".join(["#FF0000"] * 9), "ritmo": "4", "nome": "x"},
     "no máximo 8 cores"),
    ({"base": "piscar", "cores": "#FF0000", "ritmo": "0", "nome": "x"}, "ritmo vai de 1 a 10"),
    ({"base": "piscar", "cores": "#FF0000", "ritmo": "", "nome": "x"}, "Escolha o ritmo"),
    ({"base": "piscar", "cores": "#FF0000", "ritmo": "4", "nome": ""}, "Dê um nome"),
    ({"base": "piscar", "cores": "#FF0000", "ritmo": "4", "nome": "n" * 200}, "no máximo"),
])
def test_criar_sem_o_que_falta_recusa_dizendo_e_nao_guarda(forma: dict[str, Any],
                                                          frase: str) -> None:
    from pacotes import a04_iluminacao as a04

    with pytest.raises(RuntimeError, match=frase):
        _criar(forma)
    assert a04.meus_efeitos("luz") == {}


# ---------------------------------------------------------------- a guia: oito casas, as de jogador


def test_a_guia_tem_o_branco_e_as_cores_de_jogador_e_nenhuma_das_de_fora() -> None:
    """MORDIDA: devolver uma cor ao `FORA_DA_GUIA`, ou o ciano do Player 6 à fileira."""
    # A decisão: D-1910-A-PRIMEIRA-CASA-DA-COR-E-O-BRANCO.
    from hefesto_dualsense4unix.core.led_control import player_slot_color
    from pacotes import a04_iluminacao as a04

    jogadores = ((255, 255, 255), *(tuple(player_slot_color(n)) for n in (1, 2, 3, 4, 5, 7, 8)))
    assert a04.tons_da_guia() == jogadores
    assert len(a04.FORA_DA_GUIA) == 5
    hexes = {"#{:02X}{:02X}{:02X}".format(*t) for t in a04.tons_da_guia()}
    assert not hexes & {h.upper() for h in a04.FORA_DA_GUIA}


# ---------------------------------------------------------------- o desenho


def test_o_desenho_nao_tem_interrogacao_nem_desligar() -> None:
    """MORDIDA: voltar o `?` ou o «Desligar» ao desenho.

    O «Sem piscar» voltou em 15/10/2026 e saiu de novo em 16/10/2026, a pedido (a «Luz
    fixa» já faz isso); a ausência é medida em `test_o_sem_piscar_saiu_e_o_arquivo_velho_carrega`.
    """
    doc = _doc()
    assert 'class="ajuda' not in doc, "o `?` voltou: a dica mora no `data-dica`"
    for fora in ("Desligar", "Opções", "mesa"):
        assert fora not in doc, f"o desenho trouxe «{fora}»"
    for dito in ("Efeito", "Criar efeitos novos", "Sem efeito", "Luz fixa", "Respirar", "Piscar",
                 "Arco-íris", "Criar", "Modo automático"):
        assert dito in doc, f"o desenho perdeu «{dito}»"


def test_o_modo_automatico_governa_as_colunas_e_o_par_antigo_saiu() -> None:
    bruto = MOCKUP.read_text(encoding="utf-8")
    chaves = re.findall(r'<[^>]*class="[^"]*modo-auto[^"]*"[^>]*>', bruto)
    assert len(chaves) == 1, chaves
    assert 'data-governa=".luz-grade .ctrl"' in chaves[0]
    assert 'data-gesto="modo-da-luz"' in chaves[0]


def test_cada_coluna_viva_tem_a_lista_de_efeitos_e_o_gesto_dela() -> None:
    doc = _doc()
    listas = re.findall(r"<select[^>]*>", doc)
    efeitos = [s for s in listas if "g4-efeito" in s]
    assert len(efeitos) == 4, "uma lista por coluna, viva ou vazia"
    assert all('data-gesto="efeito-da-luz"' in s for s in efeitos), efeitos
    assert 'value="luz-fixa" selected' in doc.replace("\n", " ")
    assert doc.count('data-gesto="criar-efeito"') == 1


def test_a_vaga_sem_controle_diz_desconectado_e_nao_tem_gesto() -> None:
    doc = _doc()
    assert doc.count("Desconectado") == 2
    # desde 16/10/2026 o P3 e o P4 leem como o P1 e o P2: o número sem negrito, mesmo «•»
    assert re.search(r">P3 <span class=\"pt\">•</span> Desconectado<", doc)
    assert "<b>P3</b>" not in doc and "<b>P4</b>" not in doc


def test_a_aba_cabe_sem_rolar_a_guia_tem_oito_casas_e_o_nome_tem_a_largura_da_coluna() -> None:
    from playwright.sync_api import sync_playwright

    medir = """() => {
      const d = document.documentElement;
      const m = document.querySelector('.janela > .miolo') || d;
      const q = s => [...document.querySelectorAll(s)];
      const col = q('.luz-grade .ctrl');
      return {altura: m.scrollHeight, cabe: m.clientHeight,
              lateral: d.scrollWidth > d.clientWidth + 1,
              casas: col.map(c => c.querySelectorAll('.tom').length),
              larguras: col.map(c => Math.round(c.getBoundingClientRect().width)),
              nome: q('.ctrl-rot').map(e => e.getBoundingClientRect().width),
              moldura: q('.luz-grade .moldura').map(e => e.getBoundingClientRect().width),
              lista: q('.g4-efeito').map(e => getComputedStyle(e).display),
              criar: q('#criar-luz .criar-linha').map(e => e.scrollWidth <= e.clientWidth + 1)};
    }"""
    with sync_playwright() as pw:
        nav = pw.chromium.launch(executable_path=str(CHROME), args=["--no-sandbox"])
        pg = nav.new_page(viewport={"width": 1600, "height": 809})
        pg.goto(MOCKUP.as_uri())
        m = pg.evaluate(medir)
        nav.close()
    # O miolo é quem rola: medir contra 809 deixava passar um pixel de barra (619 em 618).
    assert m["altura"] <= m["cabe"] and not m["lateral"], m
    assert m["casas"] == [8, 8, 8, 8], f"a guia é UMA fileira de oito: {m['casas']}"
    assert max(m["larguras"]) - min(m["larguras"]) <= 1, f"as quatro colunas são iguais: {m}"
    for nome, moldura in zip(m["nome"], m["moldura"], strict=True):
        if moldura:
            assert abs(nome - moldura) < 2, (nome, moldura)
    assert sorted(m["lista"]) == ["block", "block", "none", "none"] or \
        sorted(m["lista"]) == ["inline-block", "inline-block", "none", "none"] or \
        m["lista"].count("none") == 2, m["lista"]
    assert m["criar"] and all(m["criar"]), "a linha Criar estoura a largura"
