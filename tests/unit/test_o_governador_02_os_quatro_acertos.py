"""Os cinco acertos que a conferência deixou — GOVERNADOR-DO-RADIO-02 (23/09/2026).

A GOVERNADOR-DO-RADIO-01 foi aprovada com quatro decisões de produto e um
resíduo da O-DIARIO. Uma régua por item, e cada uma MORDE:

1. **«Ligar aqui» vale enquanto a ponte estiver de pé.** A R3 é *sempre pedir
   mover*: a ponte desceu, a próxima subida no adaptador cheio pergunta de
   novo. E a vaga que nunca subiu não gasta a resposta dela.
2. **A marca «além do limite» sai quando o adaptador volta a caber** — a tela
   não pode dizer «além do limite» com 2 de 2.
3. **Num 2B longo, a religação espera cada vez mais** (5 → 10 → 20 → 40 → 60 s)
   e volta a 5 s quando a fila anda; o diário diz a espera, não cada tentativa.
4. **A frase da recusa diz o nome, nunca o endereço.**
5. **Ponte fantasma não conta:** o daemon que morreu sem ``stop()`` não deixa
   ponte de pé no fato da próxima queda.

Nada aqui abre socket de Bluetooth, lê o sysfs dela ou escreve no diário dela:
o medidor é um dublê, os donos do nome são trocados por ``monkeypatch``, e o
diário mora em ``tmp_path``.
"""

from __future__ import annotations

import functools
import itertools
import math
import re
import time
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any

import pytest

from hefesto_dualsense4unix.daemon.subsystems import governador_do_radio as gov
from hefesto_dualsense4unix.integrations import alto_falante_bt as af
from hefesto_dualsense4unix.integrations import ar_do_adaptador as ar
from hefesto_dualsense4unix.integrations import bluez_dbus, mesa_de_radio, storm_doctor
from hefesto_dualsense4unix.integrations import diario_do_radio as diario
from hefesto_dualsense4unix.utils import maquina

ADAPTADOR_A = "aa:bb:cc:00:00:a1"
ADAPTADOR_B = "aa:bb:cc:00:00:b2"
CONTROLE_1 = "aa:bb:cc:00:00:01"
CONTROLE_2 = "aa:bb:cc:00:00:02"
CONTROLE_3 = "aa:bb:cc:00:00:03"
CONTROLE_4 = "aa:bb:cc:00:00:04"

#: Qualquer endereço de rádio, com dois-pontos, em qualquer caixa.
ENDERECO = re.compile(r"(?i)[0-9a-f]{2}(?::[0-9a-f]{2}){5}")


class _Relogio:
    def __init__(self) -> None:
        self.agora = 100.0

    def __call__(self) -> float:
        return self.agora


@dataclass
class _Diario:
    entradas: list[dict[str, Any]] = field(default_factory=list)

    def __call__(self, quem: str, o_que: str, por_que: str, **campos: Any) -> None:
        self.entradas.append({"quem": quem, "o_que": o_que, "por_que": por_que, **campos})

    def de(self, o_que: str) -> list[dict[str, Any]]:
        return [e for e in self.entradas if e["o_que"] == o_que]


def _governador(
    relogio: _Relogio,
    registro: _Diario,
    onde: dict[str, str],
    *,
    medidor: Any = None,
    nomear: Any = None,
) -> gov.GovernadorDoRadio:
    return gov.GovernadorDoRadio(
        medidor=medidor,
        adaptador_de=lambda uniq: onde.get(uniq, ADAPTADOR_A),
        registrar=registro,
        relogio=relogio,
        nomear=nomear,
    )


def _subir(governador: gov.GovernadorDoRadio, uniq: str) -> gov.Vaga:
    vaga = governador.pedir_vaga(uniq, "som")
    assert isinstance(vaga, gov.Vaga), f"{uniq} ouviu {vaga!r}"
    vaga.subiu("som")
    return vaga


def _alem(governador: gov.GovernadorDoRadio, adaptador: str) -> dict[str, bool]:
    return {
        p["uniq"]: p["alem_do_limite"] for p in governador.publicar()[adaptador]["pontes"]
    }


# ---------------------------------------------------------------------------
# 1. «Ligar aqui» vale enquanto a ponte estiver de pé
# ---------------------------------------------------------------------------
def _a_terceira_no_a_com_vaga_no_b(
    relogio: _Relogio, registro: _Diario
) -> gov.GovernadorDoRadio:
    """Dois no A, um no B: a terceira do A tem para onde ir, e por isso pergunta."""
    onde = {
        CONTROLE_1: ADAPTADOR_A, CONTROLE_2: ADAPTADOR_A, CONTROLE_3: ADAPTADOR_A,
        CONTROLE_4: ADAPTADOR_B,
    }
    governador = _governador(relogio, registro, onde)
    for uniq in (CONTROLE_1, CONTROLE_2, CONTROLE_4):
        _subir(governador, uniq)
    return governador


def test_a_ponte_que_desceu_gasta_o_ligar_aqui_e_a_proxima_pergunta_de_novo() -> None:
    """A R3 é *sempre pedir mover*: a resposta dela valia para AQUELA ponte.

    Até a GOVERNADOR-DO-RADIO-02 o «Ligar aqui» valia por (controle, adaptador)
    até o daemon reiniciar: o jogo fechava, a ponte descia, e a próxima subida
    no adaptador cheio vinha sem pergunta nenhuma, dias depois.

    MORDIDA: tire do ``_soltar`` o ``self._autorizados.discard(...)`` e a
    segunda subida passa sem perguntar.
    """
    relogio, registro = _Relogio(), _Diario()
    governador = _a_terceira_no_a_com_vaga_no_b(relogio, registro)
    assert isinstance(governador.pedir_vaga(CONTROLE_3, "som"), gov.Recusa)
    assert governador.ligar_aqui(CONTROLE_3) is True

    vaga = _subir(governador, CONTROLE_3)
    assert vaga.alem_do_limite is True and vaga.por_escolha_dela is True
    relogio.agora += 60.0  # o jogo tocou um minuto
    vaga.soltar("a fonte do som secou")

    relogio.agora += 1.0
    de_novo = governador.pedir_vaga(CONTROLE_3, "som")
    assert isinstance(de_novo, gov.Recusa), (
        "a ponte desceu e a próxima subida no adaptador cheio não perguntou"
    )
    assert de_novo.motivo == gov.MOTIVO_CHEIO
    [pedido] = governador.publicar()[ADAPTADOR_A]["pedidos"]
    assert pedido["uniq"] == CONTROLE_3, "a pergunta de novo não chegou à tela"


def test_a_vaga_que_nunca_subiu_nao_gasta_a_resposta_dela() -> None:
    """Ela respondeu, e a ponte ainda não esteve no ar: não se pergunta de novo.

    O subsystem pede a vaga ANTES do gravador. Se o gravador não sobe («o som
    não teve fonte»), a vaga volta sem a ponte ter subido — e perguntar de novo
    ali seria cobrar dela uma resposta que ela já deu.

    MORDIDA: gaste a autorização em toda soltura (sem olhar ``subiu``) e a
    segunda vaga vira recusa.
    """
    relogio, registro = _Relogio(), _Diario()
    governador = _a_terceira_no_a_com_vaga_no_b(relogio, registro)
    assert isinstance(governador.pedir_vaga(CONTROLE_3, "som"), gov.Recusa)
    assert governador.ligar_aqui(CONTROLE_3) is True

    sem_fonte = governador.pedir_vaga(CONTROLE_3, "som")
    assert isinstance(sem_fonte, gov.Vaga)
    sem_fonte.soltar("o som não teve fonte")

    vaga = governador.pedir_vaga(CONTROLE_3, "som")
    assert isinstance(vaga, gov.Vaga), "a vaga que nunca subiu gastou a resposta dela"
    assert vaga.alem_do_limite is True and vaga.por_escolha_dela is True


# ---------------------------------------------------------------------------
# 2. a marca «além do limite» sai quando o adaptador volta a caber
# ---------------------------------------------------------------------------
def test_a_marca_alem_do_limite_sai_de_quem_voltou_a_caber() -> None:
    """Quatro pontes num adaptador só (R4: não há outro), e elas descem.

    A cada descida, as duas primeiras que chegaram cabem; só o resto segue
    marcado. Sem isto a tela mostraria «além do limite» com 2 de 2 — laranja
    sobre um adaptador que está no limite, não além dele.

    MORDIDA: tire do ``_soltar`` a chamada a ``_recalcular_o_limite`` e as
    marcas ficam onde a admissão as pôs.
    """
    relogio, registro = _Relogio(), _Diario()
    governador = _governador(relogio, registro, {})
    vagas = {u: _subir(governador, u) for u in (CONTROLE_1, CONTROLE_2, CONTROLE_3, CONTROLE_4)}
    assert _alem(governador, ADAPTADOR_A) == {
        CONTROLE_1: False, CONTROLE_2: False, CONTROLE_3: True, CONTROLE_4: True,
    }

    vagas[CONTROLE_1].soltar("a fonte do som secou")
    assert _alem(governador, ADAPTADOR_A) == {
        CONTROLE_2: False, CONTROLE_3: False, CONTROLE_4: True,
    }, "três pontes com limite 2: só a que chegou por último segue além"

    vagas[CONTROLE_2].soltar("a fonte do som secou")
    publicado = governador.publicar()[ADAPTADOR_A]
    assert len(publicado["pontes"]) == publicado["n_max"] == 2
    assert _alem(governador, ADAPTADOR_A) == {CONTROLE_3: False, CONTROLE_4: False}, (
        "a tela diria «além do limite» com 2 de 2"
    )


# ---------------------------------------------------------------------------
# 3. num 2B longo, a religação espera cada vez mais
# ---------------------------------------------------------------------------
def _a_tentativa_que_cai(governador: gov.GovernadorDoRadio) -> gov.Vaga | None:
    """A ponte sob demanda: pede, sobe, e o uhid devolve EAGAIN até o teto."""
    vaga = governador.pedir_vaga(CONTROLE_1, "som")
    if isinstance(vaga, gov.Recusa):
        assert vaga.motivo == gov.MOTIVO_PARADO, vaga
        return None
    vaga.subiu("som")
    vaga.fila_parada(af.TETO_DE_CEDER_S + 0.05)  # o teto, pelo kernel
    vaga.soltar(af.MOTIVO_FILA_PARADA)
    return vaga


def test_um_2b_longo_espera_cada_vez_mais_e_o_diario_diz_a_espera() -> None:
    """O ``bluetoothd`` não drena por dez minutos (o 22/09 teve 4.019 linhas).

    Antes: uma tentativa a cada ~7 a 12 s, sem fim, com ~4 linhas de diário
    por volta — o diário de meio mega girava e levava o resto. Agora a espera
    dobra até o teto, o diário ganha uma linha por DEGRAU, e as tentativas do
    meio são contadas, não escritas.

    MORDIDAS:
    * espera que não cresce (``episodio.espera_s = anterior``): as tentativas
      voltam a cada 5 s;
    * tentativa que não é calada (tire o ``return`` do ramo do episódio no
      ``_subiu``): um SUBIU e um DESCEU por tentativa.
    """
    relogio, registro = _Relogio(), _Diario()
    governador = _governador(relogio, registro, {})
    tentativas: list[float] = []
    fim = relogio.agora + 600.0
    while relogio.agora < fim:
        if _a_tentativa_que_cai(governador) is not None:
            tentativas.append(relogio.agora)
        relogio.agora += 1.0

    intervalos = [round(b - a) for a, b in itertools.pairwise(tentativas)]
    assert intervalos[:5] == [5, 10, 20, 40, 60], intervalos
    assert set(intervalos[5:]) == {60}, f"a espera passou do teto: {intervalos}"

    paradas = registro.de(gov.FILA_PARADA)
    assert [p["depois"]["espera_s"] for p in paradas] == [5.0, 10.0, 20.0, 40.0, 60.0], (
        "o diário tem de dizer a ESPERA, uma linha por degrau"
    )
    assert len(registro.de(diario.PONTE_SUBIU)) == 1, "cada tentativa virou um PONTE_SUBIU"
    assert len(registro.de(diario.PONTE_DESCEU)) == 1, "cada tentativa virou um PONTE_DESCEU"
    assert len(registro.entradas) == 7, (
        f"{len(registro.entradas)} linhas para {len(tentativas)} tentativas"
    )


def test_quando_a_fila_anda_a_espera_volta_a_cinco_e_a_ponte_entra_no_diario() -> None:
    """A prova pelo kernel: a tentativa passou das escritas que a fila do uhid
    comporta — o ``bluetoothd`` voltou a ler.

    A ponte que estava calada ganha AGORA o ``PONTE_SUBIU`` (o fato da próxima
    queda tem de contá-la), o diário diz quantas tentativas ficaram no meio, e
    a próxima queda volta a esperar 5 s.

    MORDIDA: faça o ``_a_fila_andou`` não tirar o episódio e a próxima queda
    espera 60 s — a espera de um 2B que já acabou.
    """
    relogio, registro = _Relogio(), _Diario()
    governador = _governador(relogio, registro, {})
    feitas = 0
    while len(registro.de(gov.FILA_PARADA)) < 5:  # até o teto de 60 s
        feitas += _a_tentativa_que_cai(governador) is not None
        relogio.agora += 1.0
    relogio.agora += gov.TETO_DA_ESPERA_DA_FILA_S

    vaga = _subir(governador, CONTROLE_1)
    assert vaga._calada, "a tentativa depois do teto entrou no diário"
    subidas = len(registro.de(diario.PONTE_SUBIU))
    for _ in range(gov.ESCRITAS_QUE_PROVAM_QUE_A_FILA_ANDA):
        vaga.contar_escrita()

    [andou] = registro.de(gov.FILA_ANDOU)
    assert andou["adaptador"] == ADAPTADOR_A
    # As caladas: todas as que caíram menos a primeira (que abriu o episódio e
    # entrou no diário), mais a que provou a fila.
    assert andou["depois"]["tentativas"] == (feitas - 1) + 1, (
        "tentativa calada que o diário não contou"
    )
    assert len(registro.de(diario.PONTE_SUBIU)) == subidas + 1, (
        "a ponte está no ar e o diário não a conta"
    )
    vaga.soltar("a fonte do som secou")
    assert registro.de(diario.PONTE_DESCEU)[-1]["controle"] == CONTROLE_1

    _a_tentativa_que_cai(governador)
    assert registro.de(gov.FILA_PARADA)[-1]["depois"]["espera_s"] == gov.ESPERA_DA_FILA_PARADA_S


@dataclass
class _MedidorDoAdaptador:
    """O ar de um adaptador, com a saída da janela na mão da régua."""

    saida_por_janela: float = 0.0

    def amostrar(self) -> dict[str, ar.ArDoAdaptador]:
        return {
            ADAPTADOR_A: ar.ArDoAdaptador(
                hci=0, endereco=ADAPTADOR_A, entrada_por_s=700.0,
                saida_por_s=self.saida_por_janela / gov.PERIODO_S,
                janela_s=gov.PERIODO_S, conexoes=(),
            )
        }


def test_a_janela_medida_que_poe_no_ar_acaba_a_espera() -> None:
    """A prova pelo medidor: o adaptador pôs no ar o que a tentativa escreveu.

    Chega antes das 64 escritas — uma janela de 250 ms basta —, e é a que vale
    quando o uhid não tem voz (sem o DKMS, ele aceita e descarta calado).

    MORDIDA: faça o ``_medir`` devolver ``False`` sempre e a espera nunca
    acaba pela janela.
    """
    relogio, registro = _Relogio(), _Diario()
    medidor = _MedidorDoAdaptador()
    governador = _governador(relogio, registro, {}, medidor=medidor)
    vaga = _subir(governador, CONTROLE_1)
    for _ in range(20):  # até cinco segundos MEDIDOS sem nada no ar
        for _ in range(23):
            if not vaga.cedendo:
                vaga.contar_escrita()
        relogio.agora += gov.PERIODO_S
        governador.tique()
        if vaga.derrubar:
            break
    assert vaga.derrubar is True, "o adaptador parado pelo governador não caiu no teto"
    vaga.soltar(af.MOTIVO_FILA_PARADA)  # a bomba devolve a vaga no mesmo quadro
    [parada] = registro.de(gov.FILA_PARADA)
    assert parada["depois"]["espera_s"] == gov.ESPERA_DA_FILA_PARADA_S

    relogio.agora += gov.ESPERA_DA_FILA_PARADA_S
    governador.tique()  # a espera tem tiques: sem ponte, o estado do adaptador sai
    tentativa = _subir(governador, CONTROLE_1)
    assert tentativa._calada
    for _ in range(23):  # uma janela, e o adaptador pôs tudo no ar
        tentativa.contar_escrita()
    medidor.saida_por_janela = 23.0
    relogio.agora += gov.PERIODO_S
    governador.tique()

    [andou] = registro.de(gov.FILA_ANDOU)
    assert andou["depois"]["tentativas"] == 1
    assert tentativa._calada is False
    assert tentativa.escritas < gov.ESCRITAS_QUE_PROVAM_QUE_A_FILA_ANDA, (
        "a régua mediu a prova do kernel, e não a da janela"
    )


# ---------------------------------------------------------------------------
# 4. a frase da recusa diz o nome, nunca o endereço
# ---------------------------------------------------------------------------
NOMES = {ADAPTADOR_A: "Entrada 4.1.4", ADAPTADOR_B: "Entrada 1.4"}


def test_a_frase_da_recusa_diz_o_nome_e_nunca_o_endereco() -> None:
    """O sino lê a frase do diário: endereço de rádio não vai para a tela.

    As palavras são as da pergunta do desenho aprovado (R3), e o nome é o que o
    dono diz — aqui um dublê dele.

    MORDIDA: volte a frase para ``', '.join(self.vagas)`` e o endereço do B
    aparece na tela.
    """
    relogio, registro = _Relogio(), _Diario()
    onde = {
        CONTROLE_1: ADAPTADOR_A, CONTROLE_2: ADAPTADOR_A, CONTROLE_3: ADAPTADOR_A,
        CONTROLE_4: ADAPTADOR_B,
    }
    governador = _governador(relogio, registro, onde, nomear=NOMES.get)
    for uniq in (CONTROLE_1, CONTROLE_2, CONTROLE_4):
        _subir(governador, uniq)
    recusa = governador.pedir_vaga(CONTROLE_3, "som")
    assert isinstance(recusa, gov.Recusa)
    assert recusa.frase == (
        "A Entrada 4.1.4 já tem 2 controles com som ou vibração. Há vaga na Entrada 1.4."
    )
    [cheio] = registro.de(gov.ADAPTADOR_CHEIO)
    assert cheio["frase"] == recusa.frase
    for frase in (recusa.frase, cheio["frase"]):
        assert not ENDERECO.search(frase), f"endereço de rádio na frase de tela: {frase!r}"
    # O endereço segue como DADO — é por ele que a tela endereça a pergunta.
    assert recusa.vagas == (ADAPTADOR_B,)


def test_sem_nome_a_frase_diz_este_adaptador_e_nunca_o_endereco() -> None:
    """Quem não sabe o nome diz «este adaptador» — e um nome que traga um
    endereço é «não sei», venha de quem vier.

    MORDIDA: tire do ``Recusa.nome_de`` a guarda do ``_ENDERECO_DE_RADIO`` e o
    dono que devolve o endereço o leva à tela.
    """
    base = gov.Recusa(CONTROLE_3, ADAPTADOR_A, "som", gov.MOTIVO_CHEIO, (ADAPTADOR_B,))
    esperada = "Este adaptador já tem 2 controles com som ou vibração. Há vaga em outro adaptador."
    for nomear in (None, lambda _e: "", lambda e: e, lambda e: f"Adaptador {e.upper()}"):
        recusa = gov.Recusa(
            base.uniq, base.adaptador, base.tipo, base.motivo, base.vagas, nomear=nomear
        )
        assert recusa.frase == esperada, (nomear, recusa.frase)
    com_nome = gov.Recusa(
        CONTROLE_3, ADAPTADOR_A, "som", gov.MOTIVO_CHEIO, (ADAPTADOR_B, "aa:bb:cc:00:00:c3"),
        nomear={ADAPTADOR_A: "Sala", "aa:bb:cc:00:00:c3": "Entrada 9"}.get,
    )
    assert com_nome.frase == (
        "O Sala já tem 2 controles com som ou vibração. Há vaga na Entrada 9."
    )


def test_o_nome_da_porta_pergunta_aos_donos(monkeypatch: pytest.MonkeyPatch) -> None:
    """``nome_da_porta``: o ``hciN`` do kernel (a amostra), o ``devpath`` do
    ``mesa_de_radio`` e o número que ELA declarou (``mapa_das_portas``).

    MORDIDA: troque o ``porta_de(...)`` por ``None`` e a entrada que ela
    declarou volta a se chamar pelo ``devpath``.
    """
    # Sob a suíte, o dono não lê a mesa dela: «não sei».
    assert gov.nome_da_porta(ADAPTADOR_A) == ""

    monkeypatch.setattr(bluez_dbus, "a_suite_esta_rodando", lambda: False)
    monkeypatch.setattr(bluez_dbus, "enderecos_pelo_kernel", lambda *_a, **_k: {})
    monkeypatch.setattr(
        mesa_de_radio,
        "adaptadores_bluetooth",
        lambda **_k: [
            mesa_de_radio.Adaptador(interface="hci3", no="/x/3-4.1.4", busnum=3, devpath="4.1.4"),
            mesa_de_radio.Adaptador(interface="hci5"),  # embutido: sem USB
        ],
    )
    monkeypatch.setattr(maquina, "carregar_maquina", maquina.MaquinaConfig)
    amostra = {
        ADAPTADOR_A: ar.ArDoAdaptador(hci=3, endereco=ADAPTADOR_A),
        ADAPTADOR_B: ar.ArDoAdaptador(hci=5, endereco=ADAPTADOR_B),
    }
    assert gov.nome_da_porta(ADAPTADOR_A, amostra=amostra) == "Entrada 4.1.4"
    assert gov.nome_da_porta(ADAPTADOR_A.upper(), amostra=amostra) == "Entrada 4.1.4"
    assert gov.nome_da_porta(ADAPTADOR_B, amostra=amostra) == "", "o embutido ganhou entrada"
    assert gov.nome_da_porta("aa:bb:cc:00:00:ee", amostra=amostra) == ""

    declarada = maquina.MaquinaConfig(
        mapa=maquina.MapaDaMesa(portas={"9": maquina.PortaDeclarada(caminho="3-4.1.4")})
    )
    monkeypatch.setattr(maquina, "carregar_maquina", lambda: declarada)
    assert gov.nome_da_porta(ADAPTADOR_A, amostra=amostra) == "Entrada 9", (
        "ela declarou a entrada 9 e a frase inventou outro nome"
    )


# ---------------------------------------------------------------------------
# 5. a ponte fantasma não conta
# ---------------------------------------------------------------------------
def _queda_agora() -> storm_doctor.EventoDoRadio:
    return storm_doctor.EventoDoRadio(
        quando="agora", carimbo=time.time() + 1, tag="[BT-SOCKET]", familia="2A",
        ocorrencias=1, borda=True, texto="BT socket write error",
    )


def _o_daemon_que_morreu(caminho: Path) -> None:
    """Duas pontes de pé, e nenhum ``stop()``: o ``SIGKILL`` não escreve nada."""
    for uniq in (CONTROLE_1, CONTROLE_2):
        diario.registrar(
            gov.QUEM, diario.PONTE_SUBIU, "há som para mandar", caminho=caminho,
            adaptador=ADAPTADOR_A, controle=uniq, tipo="som",
        )


def test_o_arranque_fecha_as_pontes_que_o_daemon_morto_deixou(tmp_path: Path) -> None:
    """O fato de uma queda depois do reinício não conta ponte que não existe.

    MORDIDA: faça ``fechar_as_pontes_fantasmas`` devolver ``0`` sem escrever e
    o sino diz «2 controles com som (limite 2)» sobre um adaptador sem ponte.
    """
    caminho = tmp_path / "diario.jsonl"
    _o_daemon_que_morreu(caminho)
    antes = storm_doctor.o_fato_da_queda(_queda_agora(), diario.ler(caminhos=[caminho]))
    assert antes == "2 controles com som (limite 2)", "o dublê do daemon morto não pegou"

    governador = gov.GovernadorDoRadio(
        adaptador_de=lambda _u: ADAPTADOR_A,
        registrar=functools.partial(diario.registrar, caminho=caminho),
        ler_o_diario=functools.partial(diario.ler, caminhos=[caminho]),
    )
    assert governador.fechar_as_pontes_fantasmas() == 2
    assert governador.fechar_as_pontes_fantasmas() == 0, "o arranque fechou duas vezes"

    entradas = diario.ler(caminhos=[caminho])
    descidas = [e for e in entradas if e["o_que"] == diario.PONTE_DESCEU]
    assert [(e["controle"], e["por_que"]) for e in descidas] == [
        (CONTROLE_1, gov.MOTIVO_DO_REINICIO),
        (CONTROLE_2, gov.MOTIVO_DO_REINICIO),
    ]
    assert all(e["adaptador"] == ADAPTADOR_A and e["tipo"] == "som" for e in descidas)
    assert diario.pontes_de_pe(entradas, math.inf) == {}
    assert storm_doctor.o_fato_da_queda(_queda_agora(), entradas) is None, (
        "a ponte fantasma entrou no fato da queda"
    )


def test_o_arranque_nao_fecha_a_ponte_que_o_daemon_novo_tem(tmp_path: Path) -> None:
    caminho = tmp_path / "diario.jsonl"
    _o_daemon_que_morreu(caminho)
    governador = gov.GovernadorDoRadio(
        adaptador_de=lambda _u: ADAPTADOR_A,
        registrar=functools.partial(diario.registrar, caminho=caminho),
        ler_o_diario=functools.partial(diario.ler, caminhos=[caminho]),
    )
    _subir(governador, CONTROLE_1)  # a mesma ponte, de pé no daemon novo
    assert governador.fechar_as_pontes_fantasmas() == 1
    de_pe = diario.pontes_de_pe(diario.ler(caminhos=[caminho]), math.inf)
    assert de_pe == {ADAPTADOR_A: {(CONTROLE_1, "som")}}


def test_quem_fecha_e_o_iniciar_do_governador_de_producao(tmp_path: Path) -> None:
    """O ``iniciar()`` fecha — e só com medidor.

    Sem medidor é o modo falso: o smoke rodando ao lado do daemon dela veria as
    pontes VIVAS dele como fantasmas e as desceria no diário.

    MORDIDA: tire a chamada do ``iniciar()`` e o arranque deixa a fantasma; ou
    ponha-a antes da guarda do medidor e o modo falso fecha pontes vivas.
    """
    caminho = tmp_path / "diario.jsonl"
    _o_daemon_que_morreu(caminho)

    def novo(medidor: Any) -> gov.GovernadorDoRadio:
        return gov.GovernadorDoRadio(
            medidor=medidor,
            adaptador_de=lambda _u: ADAPTADOR_A,
            registrar=functools.partial(diario.registrar, caminho=caminho),
            ler_o_diario=functools.partial(diario.ler, caminhos=[caminho]),
            periodo_s=60.0,
        )

    falso = novo(None)
    falso.iniciar()
    assert diario.pontes_de_pe(diario.ler(caminhos=[caminho]), math.inf), (
        "o modo falso fechou as pontes do diário"
    )

    producao = novo(_MedidorDoAdaptador())
    producao.iniciar()
    try:
        assert diario.pontes_de_pe(diario.ler(caminhos=[caminho]), math.inf) == {}
    finally:
        producao.parar()


def test_o_governador_de_regua_nao_le_o_diario_dela(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    """Com ``registrar`` injetado e sem leitor, não há diário para ler: um
    governador de régua nunca desce, no diário de ninguém, ponte que viu lá."""
    caminho = tmp_path / "diario-padrao.jsonl"
    monkeypatch.setenv(diario.ENV_DIARIO, str(caminho))
    _o_daemon_que_morreu(caminho)
    registro = _Diario()
    governador = gov.GovernadorDoRadio(adaptador_de=lambda _u: ADAPTADOR_A, registrar=registro)
    assert governador.fechar_as_pontes_fantasmas() == 0
    assert registro.entradas == []
