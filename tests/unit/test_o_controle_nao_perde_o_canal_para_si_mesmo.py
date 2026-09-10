"""O controle não perde o microfone para SI MESMO — e o defeito era de FORMA.

MEDIDO NA BANCADA DELA, 10/09/2026, com o DualSense do rádio na mão. Ela pedia
o canal do microfone e o daemon o derrubava sozinho 49 ms depois::

    01:57:08.255  bt_mic_palavra_dela            ligado=True
    01:57:08.256  bt_mic_pedido                  ligar=True  seq=4
    01:57:08.304  bt_mic_palavra_dela_esquecida        <- 49 ms
    01:57:09.376  bt_mic_pedido                  ligar=False seq=5

O sintoma que ela viu foi o nó `hefesto_mic_<hex6>` nascendo, sumindo e
voltando — *"algo tava bugando"* —, e o microfone do rádio nunca ficava no ar.
<!-- noqa-acento: citação literal dela -->

A CAUSA está numa linha do log, e ela se lê sozinha::

    mic_da_mesa_luz_do_ex_dono_apagada
        ex_dono      = aa:bb:cc:dd:ee:d8      <- com os dois-pontos
        por          = aabbccddeed8           <- normalizado
        eleito_agora = aabbccddeed8

**É o MESMO controle nos três campos.** `_apagar_a_luz_de_quem_perdeu_o_canal`
tem duas guardas para não tocar em quem não perdeu nada — `dono_antes ==
quem_tocou` e `eleitor.eleito == dono_antes` —, e as duas comparavam as strings
CRUAS. Com formatos diferentes dos dois lados, nenhuma disparava: o controle
perdia o canal para si mesmo e `esquecer_a_palavra` apagava o pedido dela.

**As guardas existiam e estavam certas na intenção.** O que faltava era comparar
a mesma coisa dos dois lados — é a família de defeito que esta casa já nomeia:
*a régua pergunta pelo campo certo, no formato errado.*

A MORDIDA: devolver a comparação crua (`dono_antes == quem_tocou`) faz os dois
primeiros testes reprovarem.
"""
from __future__ import annotations

import pytest

from hefesto_dualsense4unix.daemon.subsystems import hotkey


class _EleitorDeMentira:
    def __init__(self, eleito: str | None) -> None:
        self.eleito = eleito


class _DaemonDeMentira:
    def __init__(self) -> None:
        self.acendeu: list[tuple[bool, str]] = []

    async def _run_blocking(self, fn, acender, aceso, uniq):
        self.acendeu.append((aceso, uniq))


#: O MESMO controle, nas duas escritas que o daemon usa de verdade. O da
#: esquerda é o que `dono_antes` traz; o da direita, o que `quem_tocou` traz.
COM_DOIS_PONTOS = "aa:bb:cc:dd:ee:d8"
NORMALIZADO = "aabbccddeed8"


@pytest.mark.asyncio
async def test_nao_esquece_a_palavra_de_quem_acabou_de_pedir(monkeypatch):
    """O caso EXATO da bancada dela: os três campos são o mesmo aparelho."""
    esquecidos: list[str] = []
    monkeypatch.setattr(hotkey, "esquecer_a_palavra", esquecidos.append)
    daemon = _DaemonDeMentira()

    await hotkey._apagar_a_luz_de_quem_perdeu_o_canal(
        daemon,
        acender=lambda *a, **k: None,
        dono_antes=COM_DOIS_PONTOS,
        quem_tocou=NORMALIZADO,
        eleitor=_EleitorDeMentira(NORMALIZADO),
    )

    assert esquecidos == [], (
        "o controle perdeu o canal para SI MESMO — é o defeito de 10/09/2026, e "
        f"ele apaga o pedido dela 49 ms depois de ela o fazer (esquecidos={esquecidos})"
    )
    assert daemon.acendeu == [], "e a luz dele não pode ser apagada tampouco"


@pytest.mark.asyncio
async def test_nao_apaga_quando_o_eleito_continua_sendo_o_ex_dono(monkeypatch):
    """A segunda guarda, pelo mesmo motivo: a posse NÃO saiu dele."""
    esquecidos: list[str] = []
    monkeypatch.setattr(hotkey, "esquecer_a_palavra", esquecidos.append)
    daemon = _DaemonDeMentira()

    await hotkey._apagar_a_luz_de_quem_perdeu_o_canal(
        daemon,
        acender=lambda *a, **k: None,
        dono_antes=COM_DOIS_PONTOS,
        quem_tocou="aa:bb:cc:00:00:11",   # outro controle tocou…
        eleitor=_EleitorDeMentira(NORMALIZADO),  # …mas a posse ficou com o ex-dono
    )

    assert esquecidos == [], (
        "a posse continuou com o ex-dono — mexer na luz dele fabricaria a "
        "mentira ao contrário, que é o que esta função existe para evitar"
    )


@pytest.mark.asyncio
async def test_APAGA_quando_a_posse_de_fato_mudou_de_dono(monkeypatch):  # noqa: N802
    """E o positivo: quem perdeu o canal de verdade PERDE a luz e a palavra.

    Sem este teste a cura acima poderia ser um `return` no topo da função, que
    passaria nos dois primeiros e mataria o comportamento inteiro.
    """
    esquecidos: list[str] = []
    monkeypatch.setattr(hotkey, "esquecer_a_palavra", esquecidos.append)
    daemon = _DaemonDeMentira()
    outro = "aa:bb:cc:00:00:11"

    await hotkey._apagar_a_luz_de_quem_perdeu_o_canal(
        daemon,
        acender=lambda *a, **k: None,
        dono_antes=COM_DOIS_PONTOS,
        quem_tocou=outro,
        eleitor=_EleitorDeMentira("aabbcc000011"),
    )

    assert esquecidos == [COM_DOIS_PONTOS], (
        "quem REALMENTE perdeu o canal tem de sair do ar junto com a luz — "
        "senão o plástico diz «saí do ar» com o microfone ainda transmitindo"
    )
    assert daemon.acendeu == [(False, COM_DOIS_PONTOS)]
