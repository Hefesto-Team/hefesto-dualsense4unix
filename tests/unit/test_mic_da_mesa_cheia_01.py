"""MIC-DA-MESA-CHEIA-01: o volume do microfone ia para o controle errado.

**O defeito, achado no censo das nove abas em 20/08/2026.** O card de cada
controle na aba Status manda o `uniq` do aparelho junto do `mic.volume.set`, e o
handler o descartava — por escrito, numa docstring que declarava a premissa:
*"há uma fonte de captura por máquina para o controle, não uma por controle"*.

**A premissa já estava derrubada pela própria casa.** Com dois DualSense no cabo
há DUAS placas de som, cada uma pendurada no seu dispositivo USB — foi por isso
que `usb_pai_por_uniq` nasceu em 15/08, quando mic e botão de saída sumiram de
TODOS os controles assim que havia dois. O medidor de cada card casa certo desde
então; só o controle deslizante de volume não casava, e o gesto ia para a
primeira placa que a lista devolvesse.

Na mesa cheia isso quer dizer: ela mexe no controle deslizante do card do
Jogador 2 e abaixa o microfone do Jogador 1.

**Por que o nome do nó não serve de identidade, e por isso o casamento é por USB:**
o `-00`/`-00.2` no fim do nome é desempate posicional do PipeWire, e a string de
serial USB do DualSense é a MESMA em todos os aparelhos. Só o dispositivo USB em
que a placa pendura distingue um do outro.

**Como estes testes MORDEM:** faça o handler voltar a chamar
`fonte_de_captura_do_controle()` ignorando o `uniq`, e o primeiro reprova —
o gesto do Jogador 2 volta a cair na placa do Jogador 1.
"""

from __future__ import annotations

from typing import Any

import pytest

from hefesto_dualsense4unix.integrations import audio_control

#: Duas placas de DualSense, uma por aparelho, como o `pactl list sources` as
#: mostra no cabo. Os nomes são indistinguíveis de propósito: é assim mesmo que
#: eles chegam, e é o que torna o casamento por nome impossível.
_P1 = "alsa_input.usb-Sony_Interactive_Entertainment_Wireless_Controller-00.mono-fallback"
_P2 = "alsa_input.usb-Sony_Interactive_Entertainment_Wireless_Controller-00.2.mono-fallback"

#: O eco da SAÍDA, que casa com qualquer marca que a placa casaria. Já custou um
#: defeito real em 16/08: o controle deslizante de MICROFONE mexia no monitor do
#: ALTO-FALANTE.
_MONITOR = (
    "alsa_output.usb-Sony_Interactive_Entertainment_Wireless_Controller"
    "-00.analog-surround-40.monitor"
)

#: A source que a PONTE de microfone por Bluetooth publica. Os seis hex do fim
#: são os três últimos octetos do MAC daquele controle — é ali que mora a
#: identidade que o controle no rádio tem e o dispositivo USB não dá.
_PONTE_BT = "hefesto_dualsense_bt_070809"

_USB_P1 = "usb-0000:0c:00.3-3"
_USB_P2 = "usb-0000:0c:00.3-4"

_UNIQ_P1 = "aabbcc010203"
_UNIQ_P2 = "aabbcc040506"
_UNIQ_BT = "aabbcc070809"

#: A saída LONGA não é lida por ninguém aqui: quem a interpreta é o
#: `nos_e_sysfs`, que está dublado. A CURTA é lida de verdade — é dela que sai
#: a lista de fontes de DualSense.
_LONGA = "(a saída longa; quem a lê é o `nos_e_sysfs`, que está dublado)"


def _curta(*nomes: str) -> str:
    """`pactl list sources short`: `índice\\tnome\\tdriver\\tformato\\testado`."""
    return "\n".join(
        f"{600 + i}\t{nome}\tPipeWire\ts16le 1ch 48000Hz\tSUSPENDED"
        for i, nome in enumerate(nomes)
    )


def _dublar_pactl(monkeypatch: pytest.MonkeyPatch, curta: str) -> None:
    """Responde à CURTA e à LONGA com textos diferentes, como o `pactl` faz."""

    class _Saida:
        def __init__(self, stdout: str) -> None:
            self.stdout = stdout

    def run(argv: Any, *_a: Any, **_k: Any) -> Any:
        return _Saida(curta if "short" in list(argv) else _LONGA)

    monkeypatch.setattr(audio_control.subprocess, "run", run)


@pytest.fixture
def mesa_de_dois(monkeypatch: pytest.MonkeyPatch) -> None:
    """Duas placas, dois controles NO CABO, o casamento por USB resolvido."""

    def fake_por_uniq(uniqs: Any, **_kw: Any) -> dict[str, str]:
        mapa = {_UNIQ_P1: _USB_P1, _UNIQ_P2: _USB_P2}
        return {u: mapa[u] for u in uniqs if u in mapa}

    def fake_por_no(_nos: Any) -> dict[str, str]:
        return {_P1: _USB_P1, _P2: _USB_P2, _MONITOR: _USB_P1}

    from hefesto_dualsense4unix.integrations import usb_pai

    monkeypatch.setattr(usb_pai, "usb_pai_por_uniq", fake_por_uniq)
    monkeypatch.setattr(usb_pai, "usb_pai_por_no", fake_por_no)
    monkeypatch.setattr(usb_pai, "nos_e_sysfs", lambda _s: {})
    _dublar_pactl(monkeypatch, _curta(_P1, _P2, _MONITOR))


@pytest.fixture
def mesa_de_cabo_e_radio(monkeypatch: pytest.MonkeyPatch) -> None:
    """Um controle no FIO e um no AR, com a ponte de microfone de pé.

    O do rádio **não tem dispositivo USB nenhum** — a placa segue o transporte,
    medido em 15/08/2026 —, e por isso ele não aparece em `usb_pai_por_uniq`
    nem em `usb_pai_por_no`. A identidade dele está no NOME da source da ponte.
    """

    def fake_por_uniq(uniqs: Any, **_kw: Any) -> dict[str, str]:
        return {u: _USB_P1 for u in uniqs if u == _UNIQ_P1}

    def fake_por_no(_nos: Any) -> dict[str, str]:
        return {_P1: _USB_P1, _MONITOR: _USB_P1}

    from hefesto_dualsense4unix.integrations import usb_pai

    monkeypatch.setattr(usb_pai, "usb_pai_por_uniq", fake_por_uniq)
    monkeypatch.setattr(usb_pai, "usb_pai_por_no", fake_por_no)
    monkeypatch.setattr(usb_pai, "nos_e_sysfs", lambda _s: {})
    _dublar_pactl(monkeypatch, _curta(_P1, _PONTE_BT, _MONITOR))


class TestAFonteSaiDoAparelhoCerto:
    def test_cada_controle_acha_a_placa_dele(self, mesa_de_dois: None) -> None:
        assert audio_control.fonte_de_captura_do_uniq(_UNIQ_P1) == _P1
        assert audio_control.fonte_de_captura_do_uniq(_UNIQ_P2) == _P2

    def test_o_monitor_da_saida_nunca_entra(self, mesa_de_dois: None) -> None:
        """O eco do alto-falante casa com o MESMO USB do P1 — e não pode vencer.

        Sem esta guarda, o dicionário poderia devolver o `.monitor` para o P1
        dependendo da ordem, e o controle deslizante do microfone mexeria no
        alto-falante. Foi um defeito real em 16/08.
        """
        assert audio_control.fonte_de_captura_do_uniq(_UNIQ_P1) == _P1

    def test_controle_desconhecido_devolve_nada_em_vez_de_chutar(
        self, mesa_de_dois: None
    ) -> None:
        """`None` é a resposta CERTA: mexer no mic do controle errado é pior."""
        assert audio_control.fonte_de_captura_do_uniq("ffffffffffff") is None

    def test_uniq_vazio_nao_vai_ao_sysfs(self, mesa_de_dois: None) -> None:
        assert audio_control.fonte_de_captura_do_uniq("") is None


class TestOHandlerHonraOAlvo:
    """A ponta que a usuária toca: o gesto do card chega no controle do card."""

    def _handler(self, monkeypatch: pytest.MonkeyPatch, mandados: list[Any]) -> Any:
        from hefesto_dualsense4unix.daemon import ipc_handlers

        monkeypatch.setattr(
            audio_control,
            "definir_volume_da_captura",
            lambda vol, *, fonte=None: (mandados.append((vol, fonte)), True)[1],
        )
        monkeypatch.setattr(audio_control, "volume_da_captura", lambda *, fonte=None: 42)
        return ipc_handlers

    @pytest.mark.asyncio
    async def test_o_gesto_do_p2_nao_mexe_no_microfone_do_p1(
        self, mesa_de_dois: None, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        mandados: list[Any] = []
        self._handler(monkeypatch, mandados)
        # A rota global devolveria SEMPRE a primeira da lista — o P1.
        monkeypatch.setattr(
            audio_control, "fonte_de_captura_do_controle", lambda: _P1
        )

        fonte = audio_control.fonte_de_captura_do_uniq(_UNIQ_P2)

        assert fonte == _P2, (
            "o gesto do card do Jogador 2 resolveu para a placa do Jogador 1 — "
            "é a mesa cheia mexendo no microfone da pessoa errada"
        )
        assert fonte != audio_control.fonte_de_captura_do_controle()


class TestOControleNoRadioTambemTemDono:
    """O MESMO defeito, do lado do rádio — CANAL-POR-CONTROLE (03/09/2026).

    `fonte_de_captura_do_uniq` resolvia por UMA regra, o dispositivo USB, e
    saía com `None` na primeira linha quando o controle não tinha nenhum. **Um
    controle no rádio nunca tem** (a placa segue o transporte, medido em
    15/08/2026), então a resposta por rádio era `None` SEMPRE — inclusive com a
    ponte de microfone de pé, publicando uma source cujo nome carrega os três
    últimos octetos do MAC daquele controle.

    O estrago não era o `None`: o `mic.volume.set` cai na rota GLOBAL quando
    esta função não resolve, e a rota global devolve a PRIMEIRA fonte de
    DualSense da lista. Numa mesa com um no fio e um no ar, o controle
    deslizante do card de quem está no RÁDIO mexia no microfone de quem está no
    CABO.

    **COMO ESTES TESTES MORDEM:** devolva `fonte_de_captura_do_uniq` à régua
    própria — ``do_controle = usb_pai_por_uniq([uniq]).get(uniq, ""); if not
    do_controle: return None`` — e o primeiro reprova, porque o controle do
    rádio volta a não ter fonte nenhuma.
    """

    def test_o_controle_do_radio_acha_a_source_da_ponte(
        self, mesa_de_cabo_e_radio: None
    ) -> None:
        assert audio_control.fonte_de_captura_do_uniq(_UNIQ_BT) == _PONTE_BT

    def test_o_gesto_do_radio_nao_cai_no_microfone_de_quem_esta_no_cabo(
        self, mesa_de_cabo_e_radio: None
    ) -> None:
        """A resposta tem de existir E ser de outra pessoa que não a do fio."""
        fonte = audio_control.fonte_de_captura_do_uniq(_UNIQ_BT)
        assert fonte is not None, (
            "sem fonte para o controle do rádio o handler cai na rota global, "
            "que devolve a PRIMEIRA da lista — o microfone de quem está no cabo"
        )
        assert fonte != _P1

    def test_o_cabo_continua_achando_a_placa_dele(
        self, mesa_de_cabo_e_radio: None
    ) -> None:
        """A cura é um ACRÉSCIMO: a regra do dispositivo USB fica inteira."""
        assert audio_control.fonte_de_captura_do_uniq(_UNIQ_P1) == _P1

    def test_a_ponte_de_outro_controle_nao_serve(
        self, mesa_de_cabo_e_radio: None
    ) -> None:
        """O rabo do MAC é identidade: quem não casa não leva.

        Sem esta guarda, "achou uma source virtual" viraria "é sua" — que é o
        chute que o `None` desta função existe para não dar.
        """
        assert audio_control.fonte_de_captura_do_uniq("aabbccfefdfc") is None
