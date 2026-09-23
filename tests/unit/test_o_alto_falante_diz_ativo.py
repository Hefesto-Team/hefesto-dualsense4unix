"""O ALTO-FALANTE DIZ ATIVO — O-ALTO-FALANTE-DIZ-ATIVO-01 (23/09/2026).

A queixa dela, com a foto da aba Controles:

    *"E pq o autofalante do controle iniciou como canal dormindo ao invés de
    ativo (esse dormindo deveria ser Desativado) tipo o termo do botão."*
    <!-- noqa-acento: citação literal dela -->

Esta régua cobra as duas metades da sprint:

0. **DESLIGADO SÓ QUANDO ELA CALOU.** Canal PARADO é ATIVO, no cabo e no
   rádio, em qualquer cartão que não seja o P1 (a MATRIZ da sprint), e a
   palavra do sono do canal não chega a campo nenhum do cartão. **As
   mordidas:** devolva o sono do canal à pílula (`or dormindo`) e a seção 0
   reprova com DESLIGADO num canal parado; devolva o `Canal dormindo` ao
   alarme e ela reprova com o alarme aceso.

1. **O PEDIDO DE VAGA NÃO DERRUBA A PONTE.** O ``pedir_vaga`` do governador roda
   o ``plano_de_radio`` sem ``try``, e o chamador em
   ``daemon/subsystems/alto_falante.py`` não protegia: a exceção subia até
   ``_reconciliar`` e nenhuma ponte da mesa subia naquela volta — nem o nó era
   publicado. **A mordida:** tire o ``try`` em volta do ``pedir_vaga`` e os dois
   testes da seção 1 reprovam com a exceção do governador.

Nada aqui abre socket de Bluetooth, fala com o servidor de som dela nem escreve
no diário dela: a ponte, a fonte e o servidor são dublês, e o governador que
levanta é o de verdade com o ``plano_de_radio`` trocado.
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any, ClassVar

import pytest

from hefesto_dualsense4unix.app import audio_saida
from hefesto_dualsense4unix.daemon.subsystems import alto_falante as mod
from hefesto_dualsense4unix.daemon.subsystems import governador_do_radio as gov
from hefesto_dualsense4unix.integrations import alto_falante_bt as af
from hefesto_dualsense4unix.integrations import plano_de_radio
from hefesto_dualsense4unix.interface import mesa_viva, onde
from hefesto_dualsense4unix.interface import pacotes as pacotes_da_tela
from hefesto_dualsense4unix.interface.pacotes import a02_controles as a02

ADAPTADOR_A = "aa:bb:cc:00:00:a1"
CONTROLE_2 = "aa:bb:cc:00:00:02"
CONTROLE_3 = "aa:bb:cc:00:00:03"
CONTROLE_4 = "aa:bb:cc:00:00:04"


# ---------------------------------------------------------------------------
# 0. a tela: DESLIGADO só quando ela calou
# ---------------------------------------------------------------------------
#: A MATRIZ DA SPRINT: um controle no cabo e dois no rádio, e nenhum no P1.
MESA_DA_MATRIZ = (
    (CONTROLE_2, 2, "usb"),
    (CONTROLE_3, 3, "bluetooth"),
    (CONTROLE_4, 4, "bluetooth"),
)


def _entrada(uniq: str, slot: int, transporte: str, *, calado: bool) -> dict[str, Any]:
    """Um controle como o `state_full` o publica — o volume é nosso, e o mudo é o
    que o ♪ lê."""
    return {
        "uniq": uniq, "player": slot, "player_slot": slot, "index": slot - 2,
        "connected": True, "is_primary": slot == 2, "battery_pct": 80,
        "transport": transporte, "inputs": {},
        "audio": {"mic_mudo": False, "mic_mudo_desejado": None},
        "speaker": {"volume": 102, "muted": calado, "rota": 0},
    }


@pytest.fixture
def canal(monkeypatch: pytest.MonkeyPatch) -> Any:
    """Escreve o sono de cada canal direto no cache — sem thread e sem `pactl`.

    É o mesmo ponto de injeção que a régua irmã usa
    (`test_o_cartao_diz_se_o_som_tem_para_onde_ir.sono_lido`), e o cache é o
    que a `_camada_1` enche em produção com o `estado_do_canal` do dono.
    """
    monkeypatch.setattr(a02, "_SONO", {})

    def por(sono: dict[str, str]) -> None:
        a02._SONO.clear()
        a02._SONO.update(sono)

    return por


def _cartoes(*, calados: frozenset[str] = frozenset()) -> dict[str, dict[str, Any]]:
    """Os cartões da 02 que o pacote monta, por `pref` — a língua da tela."""
    entradas = [
        _entrada(uniq, slot, transporte, calado=uniq in calados)
        for uniq, slot, transporte in MESA_DA_MATRIZ
    ]
    estado = {"controllers": entradas}
    mesa = mesa_viva.mesa_do_estado(estado, {})
    bruto = a02.pacote(pacotes_da_tela.Contexto(
        state=estado, mesa=mesa, conectados=entradas))
    pronto = pacotes_da_tela.normalizar(bruto, {m["uniq"]: m["pref"] for m in mesa})
    return pronto["colunas"]


def test_a_mesa_da_matriz_nao_usa_o_p1() -> None:
    """A régua mede o que a sprint pede: cabo e rádio, fora do P1."""
    cartoes = _cartoes()
    assert sorted(cartoes) == ["p2", "p3", "p4"]


@pytest.mark.parametrize("sono", [audio_saida.CANAL_DORMINDO, audio_saida.CANAL_ACORDADO])
def test_o_canal_parado_ou_tocando_e_ativo_nos_dois_transportes(canal: Any, sono: str) -> None:
    """Uma pílula só, ATIVO, com o alto-falante ligado — parado OU tocando.

    MORDIDA: devolva o `or dormindo` à pílula e o canal parado reprova com
    DESLIGADO; devolva o `Canal dormindo` ao `selo_do_som` e ele reprova com o
    alarme aceso.
    """
    canal({uniq: sono for uniq, _, _ in MESA_DA_MATRIZ})
    for pref, cartao in _cartoes().items():
        assert cartao["alto-canal"] == mesa_viva.ATIVO, (
            f"{pref}: o alto-falante ligado diz {cartao['alto-canal']!r} com o "
            f"canal {sono}")
        assert cartao["alto-selo"] == a02.NADA_A_DIZER, (
            f"{pref}: o alarme acendeu {cartao['alto-selo']!r} sobre um canal {sono}")
        assert cartao["alto-canal-porque"] == a02.NADA_A_DIZER, pref


def test_calar_pelo_som_desliga_e_soltar_ativa(canal: Any) -> None:
    """O `♪` é o único que desliga, e desliga SÓ o cartão que ela calou.

    O cabo (P2) calado e os dois do rádio ligados, e depois o contrário: é a
    matriz inteira, e a pílula segue o mudo em cada um.
    """
    canal({uniq: audio_saida.CANAL_DORMINDO for uniq, _, _ in MESA_DA_MATRIZ})
    so_o_cabo = _cartoes(calados=frozenset({CONTROLE_2}))
    assert so_o_cabo["p2"]["alto-canal"] == mesa_viva.DESLIGADO
    assert so_o_cabo["p3"]["alto-canal"] == mesa_viva.ATIVO
    assert so_o_cabo["p4"]["alto-canal"] == mesa_viva.ATIVO
    so_o_radio = _cartoes(calados=frozenset({CONTROLE_3, CONTROLE_4}))
    assert so_o_radio["p2"]["alto-canal"] == mesa_viva.ATIVO
    assert so_o_radio["p3"]["alto-canal"] == mesa_viva.DESLIGADO
    assert so_o_radio["p4"]["alto-canal"] == mesa_viva.DESLIGADO


def test_sem_canal_a_pilula_some(canal: Any) -> None:
    """Sem nó de som para o controle não há o que afirmar: o marcador de nada.

    O «não sei» continua sendo o terceiro estado — a cura não fez o ATIVO nascer
    da ausência.
    """
    canal({CONTROLE_2: audio_saida.CANAL_DORMINDO})
    cartoes = _cartoes()
    assert cartoes["p2"]["alto-canal"] == mesa_viva.ATIVO
    assert cartoes["p3"]["alto-canal"] == a02.NADA_A_DIZER
    assert cartoes["p4"]["alto-canal"] == a02.NADA_A_DIZER


def test_a_palavra_do_sono_nao_chega_a_campo_nenhum_do_cartao(canal: Any) -> None:
    """«dormindo» e «acordado» saem da tela INTEIRA, não só da pílula.

    Varre TODO valor que o pacote manda para os três cartões, e não só os três
    campos do alto-falante: o fato errado só sai se a lista for medida.
    """
    for sono in (audio_saida.CANAL_DORMINDO, audio_saida.CANAL_ACORDADO):
        canal({uniq: sono for uniq, _, _ in MESA_DA_MATRIZ})
        for pref, cartao in _cartoes().items():
            for campo, valor in cartao.items():
                texto = str(valor).lower()
                assert "dormindo" not in texto and "acordado" not in texto, (
                    f"{pref}.{campo} leva a palavra do sono: {valor!r}")


def test_o_dono_do_selo_nao_pergunta_pelo_sono() -> None:
    """O dono responde com DOIS fatos: o mudo e se há canal. O sono não entra.

    A assinatura é o contrato: um terceiro parâmetro de sono é o caminho por
    onde o `or dormindo` voltaria.
    """
    assert mesa_viva.selo_do_alto_falante(False, True) == mesa_viva.ATIVO
    assert mesa_viva.selo_do_alto_falante(True, True) == mesa_viva.DESLIGADO
    assert mesa_viva.selo_do_alto_falante(False, False) == mesa_viva.SEM_LEITOR
    import inspect

    assert list(inspect.signature(mesa_viva.selo_do_alto_falante).parameters) == [
        "mudo", "sabemos"]


def test_a_bancada_viva_nao_carrega_a_palavra_do_sono() -> None:
    """O «Dormindo» do `controles_vivos.py` saiu, e o kwarg que o carregava.

    O `estado_do_card` não pede mais o canal e não devolve mais o
    `estado_alto`; o `aba02.bloco` não o recebe. Os três lados juntos, para não
    repetir o `rota_pc` de 21/09 (a renomeação que alcançou um lado só).
    """
    import inspect

    from hefesto_dualsense4unix.interface import aba02, controles_vivos

    assert "canal" not in inspect.signature(mesa_viva.estado_do_card).parameters
    assert "estado_alto" not in inspect.signature(aba02.bloco).parameters
    entrada = _entrada(CONTROLE_2, 2, "usb", calado=False)
    assert "estado_alto" not in mesa_viva.estado_do_card(entrada)
    fonte = inspect.getsource(controles_vivos).lower()
    assert '"dormindo"' not in fonte and '"acordado"' not in fonte


def test_a_bancada_do_desenho_mostra_ativo_no_cabo_e_no_radio() -> None:
    """O mockup acompanha pelo gerador: a pílula ATIVO nos dois transportes.

    Lê a página da BANCADA (`mockup/`), que é o que ela aprova. A publicada só
    muda quando ela mandar publicar a 02. O cartão é achado pela CASCA
    (`class="ctl card…" data-controle=`), e não pelo primeiro `data-controle`
    do arquivo: a folha de estilo cita os quatro antes do primeiro cartão, e uma
    régua que achasse a folha mediria o P1 quatro vezes — foi o que a primeira
    versão desta régua fez, e a mordida pegou.

    MORDIDA: devolva a bancada de `ea4c9cd2d` (a cena de antes desta sprint) e o P2,
    que é o do rádio, reprova sem a pílula.
    """
    import re

    from hefesto_dualsense4unix.interface.monta import MESA as MESA_DO_DESENHO

    doc = onde.pagina("02-controles.html").read_text(encoding="utf-8")
    assert "dormindo" not in doc.lower()
    cascas = {m.group(1): m.start() for m in re.finditer(
        r'<div class="ctl card[^"]*" data-controle="(p[1-4])"', doc)}
    assert sorted(cascas) == ["p1", "p2", "p3", "p4"], sorted(cascas)
    ordem = [*sorted(cascas.values()), len(doc)]
    vistos = set()
    for c in MESA_DO_DESENHO:
        pref = c["pref"]
        ini = cascas[pref]
        fim_do_cartao = ordem[ordem.index(ini) + 1]
        moldura = doc.index('data-bloco="alto-falante"', ini)
        assert moldura < fim_do_cartao, f"{pref}: a moldura achada é de outro cartão"
        rotulo = doc[moldura: doc.index("</div>", moldura)]
        palavra = re.search(
            r'class="selo-palavra" data-campo="alto-canal" data-hef-alvo="html">(.*?)</span>',
            rotulo)
        assert palavra is not None, pref
        if c.get("conectado", True):
            vistos.add(c["transporte"])
            assert 'class="selo-ativo no-rotulo on"' in rotulo, pref
            assert palavra.group(1) == mesa_viva.ATIVO, (pref, palavra.group(1))
        else:
            assert palavra.group(1) == a02.NADA_A_DIZER, (pref, palavra.group(1))
    assert vistos == {"usb", "bt"}, "a cena perdeu um dos transportes"


# ---------------------------------------------------------------------------
# 1. o pedido de vaga que levanta não derruba a ponte
# ---------------------------------------------------------------------------
@dataclass
class _Controle:
    uniq: str
    caminho: str = "/dev/hidraw9"
    transporte: str = "bluetooth"


class _PonteDeMentira:
    """A ponte do rádio sem hidraw: sobe, guarda a vaga e a devolve ao descer."""

    criadas: ClassVar[list[Any]] = []

    def __init__(self, **kw: Any) -> None:
        self.uniq = kw["uniq"]
        self.vaga = kw.get("vaga")
        self.motivo = ""
        self.desceu = False
        _PonteDeMentira.criadas.append(self)

    def subir(self) -> bool:
        if self.vaga is not None:
            self.vaga.subiu("som")
        return True

    def descer(self, **_: Any) -> bool:
        self.desceu = True
        if self.vaga is not None:
            self.vaga.soltar("desceu")
        return True

    def esta_de_pe(self) -> bool:
        return not self.desceu

    def terminou_sozinha(self) -> bool:
        return False


class _GovernadorQueLevanta:
    """A régua que a sprint pede: todo pedido de vaga levanta.

    Tem a mesma assinatura do ``GovernadorDoRadio.pedir_vaga`` — e só ela,
    porque ``_casar_as_pontes`` só chama ela.
    """

    def __init__(self) -> None:
        self.pedidos: list[tuple[str, str]] = []

    def pedir_vaga(self, uniq: str, tipo: str) -> Any:
        self.pedidos.append((uniq, tipo))
        raise RuntimeError("o plano do rádio caiu")


@pytest.fixture
def som(monkeypatch: pytest.MonkeyPatch) -> Any:
    """O subsystem com todo contato com o sistema trocado por dublê."""
    from hefesto_dualsense4unix.integrations import endpoint_de_haptica as eh
    from hefesto_dualsense4unix.integrations import filho_de_som as fs

    _PonteDeMentira.criadas = []

    def _fonte(no: str, **_kw: Any) -> tuple[Any, str, str]:
        return (lambda _n: b""), f"gravador:{no}", ""

    # ALGUÉM ESTÁ TOCANDO em todo controle: é o único caso em que a ponte do som
    # sob demanda (RADIO-AFOGADO-01) chega a pedir vaga.
    monkeypatch.setattr(af, "sink_esta_tocando", lambda nome, *_a, **_k: True)
    monkeypatch.setattr(af, "PonteDeSomPorRadio", _PonteDeMentira)
    monkeypatch.setattr(af, "fonte_do_monitor_do_no", _fonte)
    monkeypatch.setattr(fs, "derrubar_leitor_de_pipe", lambda *_a, **_k: None)
    monkeypatch.setattr(eh, "ancoras", lambda *a, **k: [])
    monkeypatch.setattr(eh, "endpoints_de_pe", lambda *a, **k: {})
    monkeypatch.setattr(eh, "varrer_endpoints_orfaos", lambda *a, **k: None)
    monkeypatch.setattr(af, "sinks_com_motores", lambda *a, **k: [])
    monkeypatch.setattr(mod.AltoFalanteSubsystem, "_quem_o_jogo_le", lambda self, c: set())

    class _Ger:
        def reconciliar(self, *_a: Any, **_k: Any) -> None:
            return None

        def dormir(self, _s: float) -> bool:
            return False

        def parar(self) -> None:
            return None

    return mod.AltoFalanteSubsystem(gerenciador=_Ger(), fonte_de_controles=lambda: [])


def test_o_governador_que_levanta_nao_derruba_a_ponte(som: Any) -> None:
    """Todo pedido levanta, e as duas pontes sobem como antes do governador.

    SEM VAGA, e é o «não sei»: a ponte que sobe aqui é a mesma que subia antes
    de o governador existir — e a mesma do dublê montado por ``__new__``.

    MORDIDA: tire o ``try`` em volta do ``pedir_vaga`` e a volta levanta
    ``RuntimeError: o plano do rádio caiu``.
    """
    governador = _GovernadorQueLevanta()
    som.governador = governador
    som._casar_as_pontes([_Controle(CONTROLE_2), _Controle(CONTROLE_3)])
    assert sorted(som._pontes) == [CONTROLE_2, CONTROLE_3], (
        "o pedido de vaga que levanta derrubou a subida da ponte"
    )
    assert all(p.vaga is None for p in som._pontes.values())
    assert governador.pedidos == [(CONTROLE_2, "som"), (CONTROLE_3, "som")]
    assert som._esperando_vaga == frozenset(), "«não sei» virou espera por vaga"
    assert not som._ponte_recusada, "«não sei» virou recusa, e a recusa apaga o nó"


def test_o_plano_do_radio_que_levanta_no_governador_de_verdade(
    som: Any, monkeypatch: pytest.MonkeyPatch
) -> None:
    """O caminho REAL da exceção: o terceiro controle no mesmo adaptador.

    As duas primeiras pontes cabem no adaptador e ganham vaga sem perguntar a
    ninguém. A terceira chega ao adaptador cheio, e é aí — só aí — que o
    governador pergunta ao ``plano_de_radio`` para onde mover. Se o plano cai,
    a terceira sobe sem vaga e as duas primeiras ficam com as delas.

    MORDIDA: tire o ``try`` em volta do ``pedir_vaga`` e a volta levanta
    ``RuntimeError: o plano do rádio caiu`` no terceiro controle.
    """

    def _plano_que_cai(*_a: Any, **_k: Any) -> Any:
        raise RuntimeError("o plano do rádio caiu")

    monkeypatch.setattr(plano_de_radio, "plano_por_adaptador", _plano_que_cai)
    diario: list[tuple[Any, ...]] = []
    som.governador = gov.GovernadorDoRadio(
        medidor=None,
        adaptador_de=lambda _uniq: ADAPTADOR_A,
        registrar=lambda *a, **k: diario.append((a, k)),
        relogio=lambda: 100.0,
    )
    controles = [_Controle(u) for u in (CONTROLE_2, CONTROLE_3, CONTROLE_4)]
    som._casar_as_pontes(controles)
    assert sorted(som._pontes) == [CONTROLE_2, CONTROLE_3, CONTROLE_4], (
        "o plano do rádio que levanta derrubou a subida das pontes"
    )
    com_vaga = sorted(u for u, p in som._pontes.items() if p.vaga is not None)
    assert com_vaga == [CONTROLE_2, CONTROLE_3], (
        "as duas pontes que cabiam no adaptador perderam a vaga"
    )
    assert som._pontes[CONTROLE_4].vaga is None
