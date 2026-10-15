"""HAPTICA-POR-RADIO — a âncora que não se repete e a ponte que volta ao som.

INSTALL-UNIVERSAL (18/09/2026). Dois defeitos do endpoint de háptica pelo
rádio que não dependem da máquina do usuário, e por isso chegariam a qualquer outra:

1. **A ÂNCORA REPETIDA.** A distribuição (de 18/09 a 14/10) ordenava TODOS os controles vivos e
   dava a i-ésima âncora ao i-ésimo; quem já tinha endpoint era só pulado. B
   conecta sozinho e fica com a âncora 0; A chega depois, com A < B, e a
   ordenação dá a âncora 0 a A também. Dois nós com o mesmo ``ContainerId``: a
   háptica de um jogador vai para o outro. O mesmo com o adaptador que cai e
   devolve os controles em outra ordem — e, depois de cada restart do daemon, a
   ordenação desfazia as âncoras que o servidor tinha de pé e recarregava nós
   vivos.

2. **A PONTE QUE NÃO VOLTAVA AO SOM.** O modo háptica era decidido pelo
   ``RUNNING`` do sink, e no modo háptica a própria ponte lê o monitor do
   endpoint — um leitor segura o nó em ``RUNNING``. Fechado o jogo, a ponte
   seguia no arranjo da háptica, que não leva áudio, e o alto-falante do
   controle ficava mudo. Quem toca no sink é um sink-input; o nosso gravador
   não é um.

As réguas de subsystem usam o ``EndpointDeHaptica`` DE VERDADE contra um
servidor de som de mentira: é o ``sysfs.path`` que chega ao servidor que o jogo
lê, e é ele que se mede. Nada toca o PipeWire dela; os ``uniq`` são da faixa
sintética ``aa:bb:cc``.

LIMITE DECLARADO: é fiação e conta. A prova com o jogo aberto e o escritor
único é bancada, e está pendente.

**POR APARELHO DESDE 02/10/2026** (A-HAPTICA-E-POR-APARELHO-01): de 28/09 a
02/10 o endpoint foi um por LUGAR (P1 a P4), e voltou a ser um por DualSense,
agora pela marca do aparelho (``dualsense_bt_audio.marca_do_aparelho``) e não
pelo rabo do endereço.

**A PORTA PRÓPRIA DESDE 14/10/2026** (TODO-PAD-TEM-PORTA-PROPRIA-01): a
distribuição de âncoras emprestadas saiu do produto. A âncora de cada aparelho
é a interface do gadget do pad DELE, e por isso não se repete por construção;
as réguas de mesa abaixo seguem valendo, com a porta de cada um no registro do
``pad_usb`` (``tests/unit/porta_de_mentira.py``).
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any, ClassVar

import pytest

from hefesto_dualsense4unix.daemon.subsystems import alto_falante as mod
from hefesto_dualsense4unix.integrations import alto_falante_bt as af
from hefesto_dualsense4unix.integrations import endpoint_de_haptica as eh
from tests.unit import porta_de_mentira as porta

_A = "aa:bb:cc:00:00:01"
_B = "aa:bb:cc:00:00:02"
_C = "aa:bb:cc:00:00:03"
_D = "aa:bb:cc:00:00:04"
_MENOR, _MAIOR = sorted((_A, _B), key=eh.marca_do_aparelho)


def _ancora(i: int) -> eh.Ancora:
    """A porta ``i + 1`` do ``vhci_hcd``: a do ``_A`` é a ``_QUATRO[0]``, a do ``_B`` a ``[1]``…"""
    ancora = eh.ancora_da_interface(porta.interface_da_porta(i + 1))
    assert ancora is not None
    return ancora


_QUATRO = [_ancora(i) for i in range(4)]
#: a porta para onde o gadget de um aparelho volta quando desce e sobe de novo.
_A_QUINTA = _ancora(4)


class _Servidor:
    """Um servidor de som de mentira, na forma das respostas do `pipewire-pulse`."""

    def __init__(self) -> None:
        self.modulos: dict[str, tuple[str, str]] = {}
        self.cargas: list[str] = []
        self.quedas: list[str] = []
        self.jogo_em: set[str] = set()
        self.som_de: set[str] = set()
        self._proximo = 500

    def por(self, uniq: str, ancora: eh.Ancora) -> str:
        """Um nó que um processo ANTERIOR deixou de pé."""
        self._proximo += 1
        self.modulos[str(self._proximo)] = (eh.nome_do_endpoint(uniq), ancora.declarado)
        return str(self._proximo)

    def caminho_de(self, uniq: str) -> list[str]:
        nome = eh.nome_do_endpoint(uniq)
        return [c for n, c in self.modulos.values() if n == nome]

    def __call__(self, argv: list[str]) -> str | None:
        if argv[:4] == ["pactl", "list", "short", "modules"]:
            return "\n".join(
                f"{mid}\tmodule-null-sink\tsink_name={nome} format=float32le "
                f'sink_properties="device.bus=usb sysfs.path={caminho} '
                f'priority.session=0"\t'
                for mid, (nome, caminho) in self.modulos.items()
            )
        if argv[:2] == ["pactl", "load-module"]:
            nome = next(a.split("=", 1)[1] for a in argv if a.startswith("sink_name="))
            props = next(a for a in argv if a.startswith("sink_properties="))
            caminho = next(
                p.split("=", 1)[1] for p in props.split() if p.startswith("sysfs.path=")
            )
            self._proximo += 1
            self.modulos[str(self._proximo)] = (nome, caminho)
            self.cargas.append(nome)
            return f"{self._proximo}\n"
        if argv[:2] == ["pactl", "unload-module"]:
            self.modulos.pop(argv[2], None)
            self.quedas.append(argv[2])
            return ""
        if argv[:4] == ["pactl", "list", "short", "sinks"]:
            linhas = [
                f"{mid}\t{nome}\tPipeWire\tfloat32le 4ch 48000Hz\tRUNNING"
                for mid, (nome, _c) in self.modulos.items()
            ]
            linhas += [
                f"8{i}\t{nome}\tPipeWire\tfloat32le 2ch 48000Hz\tRUNNING"
                for i, nome in enumerate(sorted(self.som_de))
            ]
            return "\n".join(linhas)
        if argv[:4] == ["pactl", "list", "short", "sink-inputs"]:
            linhas = [
                f"9{mid}\t{mid}\t12\tprotocol-native.c\tfloat32le 4ch 48000Hz"
                for mid, (nome, _c) in self.modulos.items()
                if nome in self.jogo_em
            ]
            linhas += [
                f"98{i}\t8{i}\t12\tprotocol-native.c\tfloat32le 2ch 48000Hz"
                for i, nome in enumerate(sorted(self.som_de))
            ]
            return "\n".join(linhas)
        return None


class _PonteDeMentira:
    criadas: ClassVar[list[Any]] = []

    def __init__(self, **kw: Any) -> None:
        self.uniq = kw["uniq"]
        self.kw = kw
        self.desceu = False
        self.motivo = ""
        _PonteDeMentira.criadas.append(self)

    def subir(self) -> bool:
        return True

    def descer(self, **_: Any) -> bool:
        self.desceu = True
        return True

    def esta_de_pe(self) -> bool:
        return not self.desceu

    @property
    def leva(self) -> bool:
        """O bloco da háptica vai ao fio agora (o ``leva_a_haptica`` que a ponte lê)."""
        leva = self.kw.get("leva_a_haptica", False)
        return bool(leva() if callable(leva) else leva)


@dataclass
class _Controle:
    uniq: str
    caminho: str = "/dev/hidraw9"
    transporte: str = "bluetooth"


@dataclass
class _Mesa:
    sub: Any
    servidor: _Servidor

    def a_porta_muda(self, uniq: str) -> None:
        """O gadget do aparelho desceu e voltou noutra porta do ``vhci``."""
        porta.dar_porta(uniq, 5)

    def casar(self, *uniqs: str) -> None:
        """A volta do daemon, com o alto-falante de cada um TOCANDO."""
        for u in uniqs:
            nome = af.nome_do_sink(u)
            if nome:
                self.servidor.som_de.add(nome)
        self.sub._casar_as_pontes([_Controle(u) for u in uniqs])


@pytest.fixture
def mesa(monkeypatch: pytest.MonkeyPatch) -> _Mesa:
    from hefesto_dualsense4unix.integrations import hidraw_broker_client as broker

    _PonteDeMentira.criadas = []
    servidor = _Servidor()
    porta.dar_portas((_A, _B, _C, _D))
    monkeypatch.setattr(eh, "rodar_pactl", servidor)
    monkeypatch.setattr(af, "rodar_pactl", servidor)
    monkeypatch.setattr(
        af, "fonte_do_monitor_do_no", lambda no, **kw: ((lambda _n: b""), f"gravador:{no}", "")
    )
    monkeypatch.setattr(af, "PonteDeSomPorRadio", _PonteDeMentira)
    monkeypatch.setattr(broker, "abrir_hidraw", lambda no, **_: type("N", (), {"fd": 7})())
    monkeypatch.setattr(
        mod.AltoFalanteSubsystem, "_quem_o_jogo_le", lambda self, controles: set()
    )
    monkeypatch.setattr(mod.AltoFalanteSubsystem, "_ha_jogo_aberto", lambda self: False)
    monkeypatch.setattr(
        mod.AltoFalanteSubsystem, "_quem_mexeu_na_partida",
        lambda self, controles: {
            str(getattr(c, "uniq", "")).lower() for c in controles},
    )

    class _Ger:
        def reconciliar(self, *_a: Any, **_k: Any) -> None:
            return None

        def dormir(self, _s: float) -> bool:
            return False

        def parar(self) -> None:
            return None

    sub = mod.AltoFalanteSubsystem(gerenciador=_Ger(), fonte_de_controles=list)
    return _Mesa(sub=sub, servidor=servidor)


def test_quem_chega_depois_nao_herda_a_ancora_de_quem_estava(mesa: _Mesa) -> None:
    """O de marca maior chega sozinho; o menor chega depois e ganha OUTRA âncora."""
    mesa.casar(_MAIOR)
    antes = mesa.servidor.caminho_de(_MAIOR)
    mesa.casar(_MENOR, _MAIOR)
    assert len(mesa.servidor.modulos) == 2
    caminhos = [c for _n, c in mesa.servidor.modulos.values()]
    assert len(set(caminhos)) == 2, f"dois nós com o mesmo ContainerId: {caminhos}"
    assert mesa.servidor.caminho_de(_MAIOR) == antes
    assert mesa.servidor.quedas == []


def test_a_queda_e_a_volta_em_outra_ordem_nao_repete(mesa: _Mesa) -> None:
    """O adaptador cai, leva os dois, e eles voltam na ordem inversa."""
    mesa.casar(_A, _B)
    mesa.casar()
    assert mesa.servidor.modulos == {}, "sem DualSense e sem jogo, os endpoints ficaram"
    mesa.casar(_MAIOR)
    antes = mesa.servidor.caminho_de(_MAIOR)
    quedas = len(mesa.servidor.quedas)
    mesa.casar(_MENOR, _MAIOR)
    caminhos = [c for _n, c in mesa.servidor.modulos.values()]
    assert len(caminhos) == 2
    assert len(set(caminhos)) == 2, caminhos
    assert mesa.servidor.caminho_de(_MAIOR) == antes
    assert len(mesa.servidor.quedas) == quedas, "a volta do menor derrubou o nó do maior"


def test_o_restart_com_os_nos_de_pe_nao_recarrega_nada(mesa: _Mesa) -> None:
    """O daemon novo nasce sem memória; o servidor ainda tem os nós do anterior."""
    mesa.servidor.por(_A, _QUATRO[0])
    mesa.servidor.por(_B, _QUATRO[1])
    mesa.casar(_A, _B)
    assert mesa.servidor.cargas == [], "recarregou nó que estava de pé"
    assert mesa.servidor.quedas == []
    assert mesa.servidor.caminho_de(_A) == [_QUATRO[0].declarado]
    assert mesa.servidor.caminho_de(_B) == [_QUATRO[1].declarado]


def test_os_nos_que_o_defeito_deixou_repetidos_se_separam(mesa: _Mesa) -> None:
    """Quem atualiza o produto herda o servidor com dois nós na porta do ``_A``.

    O do ``_B`` estava na porta alheia: cai e renasce na dele
    (TODO-PAD-TEM-PORTA-PROPRIA-01).
    """
    mesa.servidor.por(_A, _QUATRO[0])
    mesa.servidor.por(_B, _QUATRO[0])
    mesa.casar(_A, _B)
    assert mesa.servidor.caminho_de(_A) == [_QUATRO[0].declarado]
    assert mesa.servidor.caminho_de(_B) == [_QUATRO[1].declarado]


def test_a_ancora_cujo_aparelho_saiu_e_trocada_fora_do_jogo(mesa: _Mesa) -> None:
    mesa.casar(_A)
    antes = mesa.servidor.caminho_de(_A)
    mesa.a_porta_muda(_A)
    mesa.casar(_A)
    depois = mesa.servidor.caminho_de(_A)
    assert depois == [_A_QUINTA.declarado] != antes


def test_com_o_jogo_tocando_a_ancora_nao_troca(mesa: _Mesa) -> None:
    """Trocar derrubaria o nó com o jogo tocando nele — a partida perde a háptica."""
    mesa.casar(_A)
    antes = mesa.servidor.caminho_de(_A)
    mesa.servidor.jogo_em.add(eh.nome_do_endpoint(_A))
    mesa.casar(_A)
    mesa.a_porta_muda(_A)
    mesa.casar(_A)
    assert mesa.servidor.caminho_de(_A) == antes


def test_o_servidor_mudo_numa_volta_nao_reancora_quem_ja_estava(
    mesa: _Mesa, monkeypatch: pytest.MonkeyPatch
) -> None:
    """A memória do processo segura o nó na volta em que o servidor não responde."""
    mesa.casar(_MAIOR)
    antes = mesa.servidor.caminho_de(_MAIOR)
    servidor = mesa.servidor
    monkeypatch.setattr(
        eh,
        "rodar_pactl",
        lambda argv: None if argv[:4] == ["pactl", "list", "short", "modules"] else servidor(argv),
    )
    mesa.casar(_MENOR, _MAIOR)
    assert mesa.servidor.caminho_de(_MAIOR) == antes, "o nó do maior trocou de âncora"
    assert mesa.servidor.quedas == []
    caminhos = [c for _n, c in mesa.servidor.modulos.values()]
    assert len(set(caminhos)) == 2, caminhos


def test_o_endpoint_tirado_por_fora_sobe_de_novo_na_volta_seguinte(mesa: _Mesa) -> None:
    """O servidor de som é a verdade: o módulo que sumiu por fora volta, e um só."""
    mesa.casar(_MENOR, _MAIOR)
    nome = eh.nome_do_endpoint(_MAIOR)
    (antigo,) = [m for m, (n, _c) in mesa.servidor.modulos.items() if n == nome]
    del mesa.servidor.modulos[antigo]  # `pactl unload-module` na mão de alguém
    mesa.casar(_MENOR, _MAIOR)
    depois = mesa.servidor.caminho_de(_MAIOR)
    assert len(depois) == 1, f"o endpoint não voltou, ou voltou duplicado: {depois}"
    assert len(mesa.servidor.caminho_de(_MENOR)) == 1


def _o_aparelho_da_ancora_sai(mesa: _Mesa, antes: list[str]) -> None:
    assert antes != [_A_QUINTA.declarado]
    mesa.a_porta_muda(_A)


def test_o_jogo_que_abre_na_mesma_volta_segura_o_no(mesa: _Mesa) -> None:
    """O jogo abre o nó na volta em que o aparelho da âncora sai do barramento."""
    mesa.casar(_A)
    antes = mesa.servidor.caminho_de(_A)
    mesa.servidor.jogo_em.add(eh.nome_do_endpoint(_A))
    _o_aparelho_da_ancora_sai(mesa, antes)
    mesa.casar(_A)
    assert mesa.servidor.caminho_de(_A) == antes, "o nó caiu com o jogo tocando nele"
    assert mesa.servidor.quedas == []


def test_a_fonte_da_haptica_que_nao_sobe_nao_derruba_o_no(
    mesa: _Mesa, monkeypatch: pytest.MonkeyPatch
) -> None:
    """Sem a fonte da háptica, a ponte fica no som com o jogo tocando no nó."""

    def _fonte(no: str, **kw: Any) -> tuple[Any, Any, str]:
        if kw.get("canais") == af.CANAIS_DA_HAPTICA:
            return None, None, "sem_monitor"
        return (lambda _n: b""), f"gravador:{no}", ""

    monkeypatch.setattr(af, "fonte_do_monitor_do_no", _fonte)
    mesa.casar(_A)
    antes = mesa.servidor.caminho_de(_A)
    mesa.servidor.jogo_em.add(eh.nome_do_endpoint(_A))
    mesa.casar(_A)
    assert _PonteDeMentira.criadas[-1].kw.get("fonte_de_haptica") is None, (
        "sem a fonte da háptica, a ponte devia ter ficado só com o som"
    )
    _o_aparelho_da_ancora_sai(mesa, antes)
    mesa.casar(_A)
    assert mesa.servidor.caminho_de(_A) == antes, "o nó caiu com o jogo tocando nele"
    assert mesa.servidor.quedas == []


def test_o_controle_sem_ponte_nao_perde_o_no_com_o_jogo_aberto(mesa: _Mesa) -> None:
    """Sem ponte (hidraw que não abre, sem `caminho`), o nó continua do jogo."""
    sem_ponte = [_Controle(_A, caminho="")]
    mesa.sub._casar_as_pontes(sem_ponte)
    assert _PonteDeMentira.criadas == []
    antes = mesa.servidor.caminho_de(_A)
    assert len(antes) == 1
    mesa.servidor.jogo_em.add(eh.nome_do_endpoint(_A))
    _o_aparelho_da_ancora_sai(mesa, antes)
    mesa.sub._casar_as_pontes(sem_ponte)
    assert mesa.servidor.caminho_de(_A) == antes, "o nó caiu com o jogo tocando nele"
    assert mesa.servidor.quedas == []


def test_o_servidor_mudo_nao_e_ninguem_tocando(
    mesa: _Mesa, monkeypatch: pytest.MonkeyPatch
) -> None:
    """Na volta em que o servidor não responde, o nó fica e a troca espera."""
    mesa.casar(_A)
    antes = mesa.servidor.caminho_de(_A)
    mesa.servidor.jogo_em.add(eh.nome_do_endpoint(_A))
    _o_aparelho_da_ancora_sai(mesa, antes)
    with monkeypatch.context() as mudo:
        mudo.setattr(eh, "rodar_pactl", lambda _argv: None)
        mudo.setattr(af, "rodar_pactl", lambda _argv: None)
        mesa.casar(_A)
    assert mesa.servidor.caminho_de(_A) == antes, "o nó caiu na volta muda"
    assert mesa.servidor.quedas == []
    mesa.casar(_A)
    assert mesa.servidor.caminho_de(_A) == antes
    mesa.servidor.jogo_em.clear()
    mesa.casar(_A)
    mesa.casar(_A)
    assert mesa.servidor.caminho_de(_A) == [_A_QUINTA.declarado] != antes


def test_na_duvida_e_resposta_so_do_servidor_mudo() -> None:
    """Resposta VAZIA é resposta: sem sink ou sem stream, ninguém toca."""
    servidor = _Servidor()
    servidor.por(_A, _QUATRO[0])
    nome = eh.nome_do_endpoint(_A)
    assert af.sink_esta_tocando(nome, lambda _argv: None) is False
    assert af.sink_esta_tocando(nome, lambda _argv: None, na_duvida=True) is True
    assert af.sink_esta_tocando(nome, servidor, na_duvida=True) is False
    assert af.sink_esta_tocando(nome, lambda _argv: "", na_duvida=True) is False

    def _sem_resposta_das_entradas(argv: list[str]) -> str | None:
        return None if argv[:4] == ["pactl", "list", "short", "sink-inputs"] else servidor(argv)

    assert af.sink_esta_tocando(nome, _sem_resposta_das_entradas, na_duvida=True) is True


def test_o_leitor_do_monitor_nao_conta_como_jogo() -> None:
    """Sink em RUNNING sem sink-input é o NOSSO gravador segurando o nó."""
    servidor = _Servidor()
    servidor.por(_A, _QUATRO[0])
    assert af.sink_esta_tocando(eh.nome_do_endpoint(_A), servidor) is False
    servidor.jogo_em.add(eh.nome_do_endpoint(_A))
    assert af.sink_esta_tocando(eh.nome_do_endpoint(_A), servidor) is True


def test_o_stream_de_outro_sink_nao_e_deste() -> None:
    servidor = _Servidor()
    servidor.por(_A, _QUATRO[0])
    servidor.por(_B, _QUATRO[1])
    servidor.jogo_em.add(eh.nome_do_endpoint(_B))
    assert af.sink_esta_tocando(eh.nome_do_endpoint(_A), servidor) is False


def test_o_jogo_que_fecha_tira_a_haptica_do_fio_e_o_som_segue(mesa: _Mesa) -> None:
    """O defeito inteiro: fechado o jogo, o alto-falante do controle segue de pé."""
    mesa.casar(_A)
    assert _PonteDeMentira.criadas[-1].leva is False
    mesa.servidor.jogo_em.add(eh.nome_do_endpoint(_A))
    mesa.casar(_A)
    assert _PonteDeMentira.criadas[-1].leva is True
    mesa.servidor.jogo_em.clear()
    mesa.casar(_A)
    assert _PonteDeMentira.criadas[-1].leva is False, "a ponte ficou presa na háptica"
    assert _PonteDeMentira.criadas[-1].kw.get("fonte_de_haptica") is None, (
        "a ponte segue lendo o endpoint que o jogo fechou, e ele não se reancora"
    )
    assert _PonteDeMentira.criadas[-1].desceu is False, "o jogo fechado derrubou o som"
    assert len(_PonteDeMentira.criadas) == 3, "uma subida para ganhar a háptica, uma para soltá-la"
