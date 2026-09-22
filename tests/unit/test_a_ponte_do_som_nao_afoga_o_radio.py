"""RADIO-AFOGADO-01 — a ponte do som só existe enquanto há som. 22/09/2026.

**A QUEIXA, com as palavras dela:** *"4 controles conectados só um aparece na
interface agora"*. <!-- noqa-acento: citação literal dela -->

**O QUE FOI MEDIDO NO DIÁRIO DAQUELE DIA:**

* a ponte do som escreve **93,75 reports de 334 B por segundo, por controle**,
  e não pergunta se alguém está tocando: o monitor de um `module-null-sink`
  entrega silêncio em tempo real para sempre, e silêncio custa o mesmo byte
  que música. Uma ponte ficou de pé **44 minutos sem uma linha de som** no
  diário — 247 mil escritas, 83 MB no rádio, para não tocar nada;
* **o teto da mesa dela é DUAS.** Duas pontes viveram 63 minutos sem um único
  `EAGAIN`; as TRÊS vezes em que a terceira subiu, a mesa inteira caiu em 11,
  15 e 89 segundos;
* a corrente é: a bomba escreve → a fila do `uhid` enche (`Output queue is
  full`, 3807 vezes num minuto) → o socket L2CAP enche → `bluetoothd` leva
  `EAGAIN` em `hidp_send_message()` → a sessão HIDP cai → o daemon perde o
  `hidraw`;
* **e a escrita nunca falha.** O kernel descarta calado, `os.write` devolve
  sucesso, e por isso portão nenhum via isto: `escrita_recusada` é ZERO no
  diário inteiro enquanto o kernel descartava 400 reports.

Esta régua cobra as cinco faces da cura. A sexta — o vigia enxergar o
alto-falante, para o som dela não esperar cinco segundos — está em
``test_o_vigia_do_modo_encurta_a_espera_da_haptica.py``.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any, ClassVar

import pytest

from hefesto_dualsense4unix.daemon.subsystems import alto_falante as mod
from hefesto_dualsense4unix.integrations.alto_falante_bt import nome_do_sink

#: A faixa sintética da casa — octetos 4 e 5 zerados. A mesa dela é de quatro.
MESA = [f"aa:bb:cc:00:00:0{n}" for n in (1, 2, 3, 4)]


@dataclass
class _Controle:
    uniq: str
    caminho: str = "/dev/hidraw9"
    transporte: str = "bluetooth"


class _PonteDeMentira:
    criadas: ClassVar[list[Any]] = []
    #: Os `uniq` cujo `subir()` FALHA — é o caminho de verdade pelo qual a
    #: recusa nasce, e escrevê-la à mão no dicionário deixaria a mordida sem
    #: morder: medido nesta régua, em 22/09/2026.
    falham: ClassVar[set[str]] = set()

    def __init__(self, **kw: Any) -> None:
        self.uniq = kw["uniq"]
        self.arranjo = kw.get("arranjo")
        self.motivo = ""
        self.desceu = False
        _PonteDeMentira.criadas.append(self)

    def subir(self) -> bool:
        return self.uniq not in _PonteDeMentira.falham

    def descer(self, **_: Any) -> bool:
        self.desceu = True
        return True

    def esta_de_pe(self) -> bool:
        return not self.desceu


class _EndpointDeMentira:
    def __init__(self, *, uniq: str, ancora: Any = None, **_: Any) -> None:
        self.uniq = uniq
        #: A POSSE, e ela é lembrada de propósito: a segunda volta lê
        #: `self._endpoints[…].ancora` para não trocar a âncora de ninguém, e
        #: um dublê sem este campo derruba a volta com `AttributeError`.
        self.ancora = ancora
        self.nome = f"endpoint::{uniq}"

    @property
    def monitor(self) -> str:
        return self.nome + ".monitor"

    def iniciar(self) -> bool:
        return True

    def parar(self) -> None:
        return None


@dataclass
class _Bancada:
    sub: Any
    #: nome do nó -> está tocando. Ausente = ninguém toca.
    tocando: dict[str, bool] = field(default_factory=dict)
    #: os nomes que o servidor de som NÃO soube responder (o `pactl` mudo).
    duvida: set[str] = field(default_factory=set)
    colhidos: list[Any] = field(default_factory=list)

    def toca(self, uniq: str, sim: bool = True) -> None:
        self.tocando[nome_do_sink(uniq)] = sim

    def o_jogo_toca_no_endpoint(self, uniq: str, sim: bool = True) -> None:
        self.tocando[f"endpoint::{uniq}"] = sim

    def volta(self, *uniqs: str) -> None:
        self.sub._casar_as_pontes([_Controle(u) for u in uniqs])

    @property
    def de_pe(self) -> list[str]:
        return sorted(self.sub._pontes)


@pytest.fixture
def bancada(monkeypatch: pytest.MonkeyPatch) -> _Bancada:
    from hefesto_dualsense4unix.integrations import alto_falante_bt as af
    from hefesto_dualsense4unix.integrations import endpoint_de_haptica as eh
    from hefesto_dualsense4unix.integrations import filho_de_som as fs
    from hefesto_dualsense4unix.integrations import hidraw_broker_client as broker

    _PonteDeMentira.criadas = []
    _PonteDeMentira.falham = set()
    b = _Bancada(sub=None)  # type: ignore[arg-type]

    def _toca(nome: Any, *_a: Any, **kw: Any) -> bool:
        if str(nome) in b.duvida:
            return bool(kw.get("na_duvida", False))
        return b.tocando.get(str(nome), False)

    monkeypatch.setattr(af, "sink_esta_tocando", _toca)
    monkeypatch.setattr(af, "PonteDeSomPorRadio", _PonteDeMentira)
    monkeypatch.setattr(
        af,
        "fonte_do_monitor_do_no",
        lambda no, **kw: ((lambda _n: b""), f"gravador:{no}", ""),
    )
    monkeypatch.setattr(fs, "derrubar_leitor_de_pipe", lambda g, **_k: b.colhidos.append(g))
    monkeypatch.setattr(eh, "EndpointDeHaptica", _EndpointDeMentira)
    monkeypatch.setattr(
        eh,
        "ancoras",
        lambda *a, **k: [
            eh.Ancora(syspath=f"/d/{i}", declarado=f"/d/{i}/i:1.0") for i in range(4)
        ],
    )
    monkeypatch.setattr(broker, "abrir_hidraw", lambda no, **_: type("N", (), {"fd": 7})())
    # O SEGUNDO LADO DO GATE DA HÁPTICA, dublado pela mesma razão das réguas
    # irmãs: a máquina da suíte não tem jogo aberto, e vermelho de ambiente
    # se lê como regressão.
    monkeypatch.setattr(
        mod.AltoFalanteSubsystem,
        "_quem_o_jogo_le",
        lambda self, controles: {str(getattr(c, "uniq", "")).lower() for c in controles},
    )

    class _Ger:
        def reconciliar(self, *_a: Any, **_k: Any) -> None:
            return None

        def dormir(self, _s: float) -> bool:
            return False

        def parar(self) -> None:
            return None

    b.sub = mod.AltoFalanteSubsystem(gerenciador=_Ger(), fonte_de_controles=lambda: [])
    return b


# ---------------------------------------------------------------------------
# 1. a mesa parada — o defeito do dia
# ---------------------------------------------------------------------------
def test_a_mesa_de_quatro_parada_nao_levanta_ponte_nenhuma(bancada: _Bancada) -> None:
    """Quatro controles ociosos escreviam 375 reports por segundo no rádio dela.

    MORDIDA: tire o `if modo == "som" and not sink_esta_tocando(...)` de
    `_casar_as_pontes` e as quatro pontes voltam — com elas, o `Output queue is
    full` e a mesa caindo em menos de 90 segundos.
    """
    bancada.volta(*MESA)
    assert bancada.de_pe == [], "a ponte subiu sem ninguém tocando"
    assert _PonteDeMentira.criadas == []


def test_o_gravador_da_ponte_que_nao_sobe_nao_fica_vivo(bancada: _Bancada) -> None:
    """Desistir depois de abrir o `pw-record` deixaria um processo por volta.

    O portão é ANTES da fonte: quem não vai ter ponte não abre gravador.
    """
    bancada.volta(*MESA)
    assert bancada.colhidos == [], bancada.colhidos


# ---------------------------------------------------------------------------
# 2. o som dela continua saindo — a cura não pode calar o produto
# ---------------------------------------------------------------------------
def test_o_controle_com_som_ganha_a_ponte(bancada: _Bancada) -> None:
    """MORDIDA: faça o portão recusar sempre e o alto-falante fica mudo."""
    bancada.toca(MESA[1])
    bancada.volta(*MESA)
    assert bancada.de_pe == [MESA[1]]
    assert _PonteDeMentira.criadas[-1].arranjo is None, "o arranjo do som é o padrão"


def test_a_haptica_nao_passa_pelo_portao_do_som(bancada: _Bancada) -> None:
    """Quem vibra não precisa de alto-falante tocando — são dois nós.

    MORDIDA: aplique o portão do som ao modo háptica e a vibração some de todo
    jogo que não mande som pelo controle.
    """
    from hefesto_dualsense4unix.integrations import alto_falante_bt as af

    bancada.o_jogo_toca_no_endpoint(MESA[0])
    bancada.volta(*MESA)
    assert bancada.de_pe == [MESA[0]]
    assert _PonteDeMentira.criadas[-1].arranjo is af.ARRANJO_HAPTICA_032


# ---------------------------------------------------------------------------
# 3. o som que acaba leva a ponte junto
# ---------------------------------------------------------------------------
def test_o_som_que_acaba_derruba_a_ponte(bancada: _Bancada) -> None:
    """Sem isto a enxurrada seria só ADIADA: a primeira nota levantaria a ponte
    e ela ficaria de pé para sempre.

    MORDIDA: troque `self._descer_ponte_ociosa(uniq)` por um `continue` seco —
    a ponte fica de pé, o diário nunca diz que ela caiu, e o rádio afoga de
    novo no primeiro jogo que ela fechar.
    """
    bancada.toca(MESA[0])
    bancada.volta(*MESA)
    primeira = _PonteDeMentira.criadas[-1]

    bancada.toca(MESA[0], False)
    bancada.volta(*MESA)

    assert bancada.de_pe == []
    assert primeira.desceu is True, "a ponte ociosa continuou escrevendo"
    assert bancada.sub._modo_da_ponte == {}, "o modo ficou lembrado sem ponte"


# ---------------------------------------------------------------------------
# 4. a dúvida é assimétrica
# ---------------------------------------------------------------------------
def test_o_servidor_mudo_nao_derruba_a_ponte_de_pe(bancada: _Bancada) -> None:
    """Um `pactl` que engasgou não pode calar o som de um jogo aberto."""
    bancada.toca(MESA[0])
    bancada.volta(*MESA)
    assert bancada.de_pe == [MESA[0]]

    bancada.duvida.add(nome_do_sink(MESA[0]))
    bancada.volta(*MESA)
    assert bancada.de_pe == [MESA[0]], "a dúvida derrubou a ponte de um jogo aberto"


def test_o_servidor_mudo_nao_levanta_ponte_nova(bancada: _Bancada) -> None:
    """O outro lado, e é o que salva a mesa: `na_duvida=True` fixo devolveria a
    enxurrada inteira toda vez que o servidor de som engasgasse.

    MORDIDA: troque o `na_duvida=uniq in self._pontes` por `na_duvida=True` —
    esta régua reprova com as quatro pontes de pé.
    """
    bancada.duvida.update(nome_do_sink(u) for u in MESA)
    bancada.volta(*MESA)
    assert bancada.de_pe == []


# ---------------------------------------------------------------------------
# 5. O LAÇO FECHADO — e ele apareceu na mesa dela um minuto depois de instalar
# ---------------------------------------------------------------------------
class TestOLacoDoNoQueNaoNasce:
    """O nó de som só nasce com ROTA, e no rádio a rota era «a ponte está de pé».

    Com a ponte nascendo sob demanda isso vira um laço fechado, e o diário dela
    o escreveu a cada cinco segundos, com a frase do próprio produto:

        `som_no_sem_rota` — *"o som do PC ainda não está saindo neste controle
        pelo rádio … o que falta é a ponte deste controle subir"*

        o nó só nasce com rota → a rota só existe com a ponte de pé → a ponte
        só sobe se alguém tocar NO NÓ → o nó não existe.

    A cura é a pergunta mudar de sentido: `_ponte_do_radio_de` responde **«há
    caminho»**, e não «está de pé agora».
    """

    def _sub(self, bancada: _Bancada) -> Any:
        bancada.volta(*MESA)
        return bancada.sub

    def test_sem_ponte_de_pe_o_controle_do_radio_ainda_tem_caminho(
        self, bancada: _Bancada
    ) -> None:
        """MORDIDA: devolva `None` quando `self._pontes.get(uniq)` for `None` —
        o nó de som nunca mais nasce, e o diário dela volta a repetir
        `som_no_sem_rota` para sempre."""
        sub = self._sub(bancada)
        assert sub._pontes == {}, "a bancada precisa começar SEM ponte"
        caminho = sub._ponte_do_radio_de(MESA[0])
        assert caminho is not None and caminho() is True

    def test_a_ponte_de_pe_continua_respondendo_por_si(
        self, bancada: _Bancada
    ) -> None:
        """Quando há ponte, quem responde é ela — não uma promessa."""
        bancada.toca(MESA[0])
        sub = self._sub(bancada)
        caminho = sub._ponte_do_radio_de(MESA[0])
        assert caminho is not None and caminho() is True
        assert caminho == sub._pontes[MESA[0]].esta_de_pe

    def test_a_ponte_que_nao_subiu_tira_o_caminho_e_o_prazo_devolve(
        self, bancada: _Bancada, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        """A falha de verdade — com o som dela na mão — some com o nó.

        E **com prazo**: sem ele, uma falha passageira calaria aquele controle
        até ela reconectá-lo, porque sem nó não há como pedir de novo.

        MORDIDA: tire o `self._ponte_recusada[uniq] = time.monotonic()` do ramo
        do `else` e o nó continua publicado sobre uma ponte que não sobe —
        exatamente o sumidouro que a régua de 07/09 trava.
        """
        agora = [1000.0]
        monkeypatch.setattr(mod.time, "monotonic", lambda: agora[0])
        # O CAMINHO DE VERDADE: alguém toca, a ponte tenta e NÃO sobe.
        _PonteDeMentira.falham.add(MESA[0])
        bancada.toca(MESA[0])
        sub = self._sub(bancada)
        assert _PonteDeMentira.criadas, "a ponte nem foi tentada"
        assert sub._pontes == {}, "a ponte que não subiu ficou guardada"

        assert sub._ponte_do_radio_de(MESA[0]) is None

        agora[0] += mod.RECUSA_DA_PONTE_S + 1
        caminho = sub._ponte_do_radio_de(MESA[0])
        assert caminho is not None and caminho() is True
        assert MESA[0] not in sub._ponte_recusada, "a recusa vencida ficou no dicionário"

    def test_a_ponte_que_sobe_apaga_a_recusa_velha(
        self, bancada: _Bancada, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        """Sem isto, um controle que falhou uma vez carregaria a recusa por um
        minuto mesmo já tendo som saindo por ele.

        MORDIDA: tire o `self._ponte_recusada.pop(uniq, None)` do ramo do
        `subir()` que deu certo.
        """
        agora = [1000.0]
        monkeypatch.setattr(mod.time, "monotonic", lambda: agora[0])
        _PonteDeMentira.falham.add(MESA[0])
        bancada.toca(MESA[0])
        bancada.volta(*MESA)
        assert MESA[0] in bancada.sub._ponte_recusada

        _PonteDeMentira.falham.clear()
        bancada.volta(*MESA)
        assert bancada.sub._pontes != {}, "a ponte não subiu na segunda volta"
        assert MESA[0] not in bancada.sub._ponte_recusada

    def test_sem_gravador_na_maquina_nao_ha_caminho(
        self, bancada: _Bancada, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        """A `libopus` não é a única coisa que falta numa máquina recém-feita.

        Sem `pw-record` nem `parec`, `argv_do_gravador` devolve `[]` e a ponte
        NUNCA sobe. Sem esta pergunta o nó seria publicado assim mesmo, ela
        tocaria, a ponte falharia, o nó sumiria — e voltaria um minuto depois,
        piscando na lista de som dela para sempre.

        MORDIDA: tire o `not ha_gravador_de_monitor()` da promessa.
        """
        from hefesto_dualsense4unix.integrations import alto_falante_bt as af

        sub = self._sub(bancada)
        monkeypatch.setattr(af, "ha_gravador_de_monitor", lambda: False)
        assert sub._ponte_do_radio_de(MESA[0]) is None

    def test_sem_libopus_nao_ha_caminho(
        self, bancada: _Bancada, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        """A promessa pergunta À MÁQUINA — é isso que a separa do `lambda: True`.

        MORDIDA: devolva `lambda: True` sem consultar
        `a_ponte_do_radio_pode_subir` e esta régua reprova: o nó nasceria numa
        máquina onde a ponte não tem como subir.
        """
        from hefesto_dualsense4unix.integrations import alto_falante_bt as af

        sub = self._sub(bancada)
        monkeypatch.setattr(
            af, "a_ponte_do_radio_pode_subir", lambda: (False, "sem libopus")
        )
        assert sub._ponte_do_radio_de(MESA[0]) is None


# ---------------------------------------------------------------------------
# 6. a porta dos fundos — a háptica que cai para o som
# ---------------------------------------------------------------------------
def test_a_haptica_sem_fonte_nao_vira_som_em_silencio(
    bancada: _Bancada, monkeypatch: pytest.MonkeyPatch
) -> None:
    """A háptica que não consegue gravador cai para o modo som — e ali o portão
    tem de valer também, senão a enxurrada volta por esta porta.

    MORDIDA: tire o segundo `sink_esta_tocando` de `_casar_as_pontes` (o do
    ramo `fonte_h is None`) e a ponte nasce em silêncio.
    """
    from hefesto_dualsense4unix.integrations import alto_falante_bt as af

    def _so_o_som(no: str, **kw: Any) -> tuple[Any, Any, str]:
        if kw.get("papel") == "haptica":
            return None, None, "sem gravador para a háptica"
        return (lambda _n: b""), f"gravador:{no}", ""

    monkeypatch.setattr(af, "fonte_do_monitor_do_no", _so_o_som)
    bancada.o_jogo_toca_no_endpoint(MESA[0])
    bancada.volta(MESA[0])

    assert bancada.de_pe == []
    assert bancada.colhidos == ["gravador:hefesto_som_000001"], (
        "o gravador do som ficou vivo sem ponte — ninguém mais o colheria")
