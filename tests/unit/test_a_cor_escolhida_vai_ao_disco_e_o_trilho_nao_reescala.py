"""A cor que ela escolhe VAI AO DISCO — e o trilho de brilho para de reescalá-la.

**A QUEIXA DE USO, na bancada de 09/09/2026**, e o usuário contou as duas metades como
uma coisa só:

    o controle branco oscilava entre a cor escolhida e o azul, e o deslizante estava estranho.

**O QUE O DISCO DO USUÁRIO DIZIA**, medido no `personalizado.json` naquele dia — o
override do controle branco, inteiro (o endereço fica de fora: é identidade
real, e `test_anonimato_de_fixtures.py` reprova até a forma mascarada dele em
arquivo versionado)::

    <o branco>: {"leds": {"lightbar_brightness": 0.49}}

A cor que ela tinha escolhido não estava ali. Não estava em lugar nenhum:
`_escrever_a_cor` mandava ao daemon (`led_set_detalhado`) e parava. O daemon a
guarda na camada VIVA por-uniq, que some no primeiro evento que faça o
resolvedor reler o perfil — replug, `profile.switch`, reaplicação. O que sobra
embaixo é a camada automática (`player_slot_color(1)` = `#0000FF`) ou o global
dela (`#2850B4`). **Os dois são azuis**, e é o azul que ela via voltar.

**E O TRILHO ERA A MESMA RAIZ.** Sem cor no disco, o gesto `brilho` só podia
adivinhar a cor pela luz ACESA — que vem pós-escala (D8) — e `cor_escolhida` só
sabe desfazer a escala dos catorze tons da guia. Toda cor fora deles voltava
INTEIRA e era escalada por cima de si mesma. Medido no aparelho do usuário, com
`#2850B4` e o trilho SUBINDO::

    80% -> 60%   (32,64,144) -> (19,38,86)
    60% -> 70%   (19,38,86)  -> (13,26,60)     <- subiu o brilho, escureceu
    70% -> 80%   (13,26,60)  -> (10,20,48)

Em oito arrastes a barra morria no preto — e "cor desconhecida" é justamente o
estado em que `_a_cor_de_agora` cai para a cor do slot. O azul de novo, pela
outra porta.

**UMA PEDRA NAS DUAS**, e a peça já existia: `_com_a_cor_gravada` (08/09/2026)
grava a cor COM procedência e tinha UM chamador — desligar o automático.
Escolher um tom nunca passou por ele.

O LAR É DE MENTIRA — o `conftest` desvia `HOME` e os quatro `XDG_*`. Estes
testes escrevem perfil de verdade pelo `save_profile` do produto, que é a única
forma de provar que o DISCO recebeu.
"""
from __future__ import annotations

import json
import pathlib
import sys

import pytest

RAIZ = pathlib.Path(__file__).resolve().parents[2]
for _p in (str(RAIZ / "src"), str(RAIZ / "src" / "hefesto_dualsense4unix" / "interface")):
    if _p not in sys.path:
        sys.path.insert(0, _p)

UNIQ = "aa:bb:cc:00:00:01"
CHAVE = "aabbcc000001"

MESA = [{"pref": "p1", "uniq": UNIQ, "jogador": 1, "cor": "white",
         "nome": "White", "via": "USB", "transporte": "usb"}]

ACESO = {"uniq": UNIQ, "index": 0, "transport": "usb", "connected": True,
         "player": 1, "player_slot": 1, "is_primary": True,
         "lightbar_rgb": [0, 0, 255], "lightbar_on": True,
         "lightbar_source": "sysfs"}

FORA_DA_GUIA = (40, 80, 180)


@pytest.fixture
def a04():
    from pacotes import a04_iluminacao

    return a04_iluminacao


@pytest.fixture
def pac():
    import pacotes

    return pacotes


def _ctx(pac, *, perfil="regua", aceso=None):
    corpo = dict(ACESO)
    if aceso is not None:
        corpo.update(aceso)
    return pac.Contexto(state={"active_profile": perfil},
                        mesa=list(MESA), conectados=[corpo], estados={})


class PonteDeMentira:
    """Dublê da ponte: guarda o que foi chamado e devolve o corpo feliz."""

    def __init__(self) -> None:
        self.corpo = {"aplicado_em": [UNIQ], "guardado_em": []}
        self.chamadas: list[tuple[str, tuple, dict]] = []

    def __getattr__(self, nome: str):
        def registrar(*args, **kwargs):
            self.chamadas.append((nome, args, kwargs))
            return True if nome == "chamar" else self.corpo

        return registrar


def _semear(nome: str, *, campos: dict | None = None, brilho_global: float = 1.0):
    from hefesto_dualsense4unix.profiles.loader import save_profile
    from hefesto_dualsense4unix.profiles.schema import (
        ControllerOverrides,
        LedsConfig,
        MatchAny,
        Profile,
    )

    prof = Profile(
        name=nome,
        match=MatchAny(),
        leds=LedsConfig(lightbar=FORA_DA_GUIA, lightbar_brightness=brilho_global),
        controllers={CHAVE: ControllerOverrides(leds=LedsConfig(**(campos or {})))},
    )
    return save_profile(prof, origem="regua")


def _do_disco(caminho) -> dict:
    return json.loads(pathlib.Path(caminho).read_text(encoding="utf-8"))


def _cor_no_disco(caminho) -> list | None:
    dado = _do_disco(caminho)
    return ((dado.get("controllers") or {}).get(CHAVE, {}).get("leds") or {}).get("lightbar")


def test_clicar_num_tom_grava_a_cor_no_override_dela(pac, a04):
    """O estado do disco do usuário em 09/09: brilho sim, cor não. Depois do clique, as duas.

    **A MORDIDA:** tire a chamada de `_guardar_a_cor_no_perfil` do fim de
    `_escrever_a_cor` e o `lightbar` volta a ser `None` — o disco fica como
    estava na bancada, e a cor só vive na camada volátil do daemon.
    """
    caminho = _semear("regua", campos={"lightbar_brightness": 0.49})
    assert _cor_no_disco(caminho) is None, "o semeado tem de nascer SEM cor"

    a04.cor(_ctx(pac), {"uniq": UNIQ, "hex": "FF8000",
                        "tipo": "button", "evento": "click"}, PonteDeMentira())

    assert _cor_no_disco(caminho) == [255, 128, 0]


def test_a_cor_gravada_leva_a_procedencia_do_numero_de_hoje(pac, a04):
    """Sem o carimbo, a escolha do usuário nasce fóssil e `cores_sem_colisao` a desloca.

    `_e_fossil` lê `lightbar_para_o_numero`: sem ele a peça é `LEGADO` e a
    regra passa a provar pela FORMA — uma cor igual à do número de outro vira
    fóssil e volta para a cor do próprio número. O azul, mais uma vez.

    **A MORDIDA:** passe `None` no lugar de `_numero(...)` em
    `_guardar_a_cor_no_perfil` e o campo some do arquivo.
    """
    caminho = _semear("regua")
    a04.cor(_ctx(pac), {"uniq": UNIQ, "hex": "FF8000",
                        "tipo": "button", "evento": "click"}, PonteDeMentira())

    leds = _do_disco(caminho)["controllers"][CHAVE]["leds"]
    assert leds["lightbar_para_o_numero"] == 1


def test_gravar_a_cor_preserva_o_brilho_que_ja_estava(pac, a04):
    """A fusão é POR CAMPO — o override dela tinha só o brilho, e ele fica."""
    caminho = _semear("regua", campos={"lightbar_brightness": 0.49})
    a04.cor(_ctx(pac), {"uniq": UNIQ, "hex": "FF8000",
                        "tipo": "button", "evento": "click"}, PonteDeMentira())

    leds = _do_disco(caminho)["controllers"][CHAVE]["leds"]
    assert leds["lightbar_brightness"] == pytest.approx(0.49)
    assert leds["lightbar"] == [255, 128, 0]


def test_desligar_a_barra_tambem_grava(pac, a04):
    """"Desligar" é escolha do usuário, e sem gravar o perfil reaplicado a reacenderia."""
    caminho = _semear("regua", campos={"lightbar": [255, 128, 0]})
    a04.apagar(_ctx(pac), {"uniq": UNIQ}, PonteDeMentira())

    leds = _do_disco(caminho)["controllers"][CHAVE]["leds"]
    assert leds["lightbar_brightness"] == 0.0
    assert _cor_no_disco(caminho) == [255, 128, 0]


def test_o_trilho_de_brilho_nao_grava_cor(pac, a04):
    """Ele não escolhe cor, e gravar ali congelaria uma cor que ela não pediu."""
    caminho = _semear("regua", campos={"lightbar_brightness": 0.5})
    a04.brilho(_ctx(pac), {"uniq": UNIQ, "valor": "70",
                           "tipo": "input", "evento": "change"}, PonteDeMentira())

    assert _cor_no_disco(caminho) is None


def _rgb_que_saiu(ponte: PonteDeMentira) -> tuple:
    nome, args, _kwargs = ponte.chamadas[-1]
    assert nome == "led_set_detalhado", ponte.chamadas
    return tuple(args[0])


def test_o_trilho_manda_a_cor_do_disco_e_nao_a_luz_acesa(pac, a04):
    """O caso medido no aparelho do usuário: `#2850B4` a 50%, arrastando para 70%."""
    _semear("regua", campos={"lightbar": list(FORA_DA_GUIA),
                             "lightbar_brightness": 0.5})
    ponte = PonteDeMentira()
    a04.brilho(_ctx(pac, aceso={"lightbar_rgb": [20, 40, 90]}),
               {"uniq": UNIQ, "valor": "70", "tipo": "input", "evento": "change"},
               ponte)

    assert _rgb_que_saiu(ponte) == FORA_DA_GUIA
    assert ponte.chamadas[-1][2]["brightness"] == pytest.approx(0.70)


def test_arrastar_dez_vezes_nao_escurece_a_cor(pac, a04):
    """A prova do acúmulo, e ela é o que o usuário viu: a barra morrendo no preto."""
    _semear("regua", campos={"lightbar": list(FORA_DA_GUIA),
                             "lightbar_brightness": 0.5})
    aceso = [20, 40, 90]
    for _ in range(10):
        ponte = PonteDeMentira()
        a04.brilho(_ctx(pac, aceso={"lightbar_rgb": list(aceso)}),
                   {"uniq": UNIQ, "valor": "50", "tipo": "input",
                    "evento": "change"}, ponte)
        saiu = _rgb_que_saiu(ponte)
        aceso = [max(0, min(255, int(c * 0.5))) for c in saiu]

    assert saiu == FORA_DA_GUIA
    assert aceso == [20, 40, 90], "a barra escureceu de volta em volta"


def test_a_cor_guardada_le_o_cru_e_devolve_none_quando_nao_ha(a04):
    """A leitura é do CRU (`perfil.ativo`), e a ausência tem de ser `None`."""
    assert a04._a_cor_guardada({}, UNIQ) is None
    assert a04._a_cor_guardada({"controllers": {CHAVE: {"leds": {}}}}, UNIQ) is None
    assert a04._a_cor_guardada(
        {"controllers": {CHAVE: {"leds": {"lightbar_brightness": 0.5}}}}, UNIQ) is None
    assert a04._a_cor_guardada(
        {"controllers": {CHAVE: {"leds": {"lightbar": [1, 2, 3]}}}}, UNIQ) == (1, 2, 3)


def test_perfil_ativo_sem_arquivo_no_disco_nao_derruba_o_gesto(pac, a04):
    """A gravação é a SEGUNDA metade do gesto e não pode derrubar a primeira.

    O daemon pode nomear um perfil que o disco não tem
    (`FileNotFoundError: perfil não encontrado`). A cor já chegou ao plástico
    dela; levantar aqui poria um cartão de recusa sobre um ato que aconteceu.

    **A MORDIDA:** tire o `try/except OSError` de `_guardar_a_cor_no_perfil` e
    esta linha reprova com `FileNotFoundError` — foi assim que sete réguas
    vizinhas caíram no minuto em que a função nasceu.
    """
    ponte = PonteDeMentira()
    a04.cor(_ctx(pac, perfil="perfil-que-nao-existe"),
            {"uniq": UNIQ, "hex": "FF8000", "tipo": "button", "evento": "click"},
            ponte)

    assert _rgb_que_saiu(ponte) == (255, 128, 0)
