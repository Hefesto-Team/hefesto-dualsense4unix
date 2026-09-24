"""A varredura se LÊ do BlueZ, muda o destino da ordem, e o doctor diz o preço.

RESERVA-DO-RADIO-01, 20/09/2026. A sprint queria RESERVAR um adaptador para os
controles. A medição de 20/09 derrubou a premissa — *"a varredura é do adaptador
que a PESSOA ABRE"* — e a cura que sobrou não adivinha: ela pergunta o
`Discovering` ao `org.bluez.Adapter1`.

Este arquivo prende as três peças da cura, e o barramento é de MENTIRA de
propósito: abrir varredura de verdade na máquina dela custa de 32,5% a 43,4% dos
pacotes do adaptador, com quatro DualSense de pé.

O BARRAMENTO DE MENTIRA É `busctl`, NÃO UM DUBLÊ DE FUNÇÃO
-----------------------------------------------------------
`tests/unit/barramento_de_mentira.py` põe um `busctl` de shell na frente do
`PATH`. A régua exercita o subprocesso, a saída crua (`b true`, `s "AC:…"`) e a
peneira de forma — o caminho inteiro do produto. Um dublê que devolvesse
`{"hci0": True}` seria mais frouxo que o produto e esconderia exatamente o que
mais quebra aqui: o parsing e o casamento de caixa do endereço.

AS NOVE MORDIDAS, arrancadas e conferidas em 20/09/2026
--------------------------------------------------------
1. **Trocar o endereço por `hciN`** em `quem_esta_varrendo` (pôr
   `varrendo.add(hci)` no lugar de `varrendo.add(endereco)`): reprova
   `test_o_leitor_responde_pelo_endereco_e_nunca_pelo_hci_n` **e**
   `test_o_oraculo_a_varredura_muda_o_destino_da_ordem` — o `hciN` é a VAGA,
   não o aparelho, e ele inverte entre boots. O filtro do motor compara com o
   `HID_PHYS`, que é MAC: um filtro por `hciN` nunca casa, e um filtro que não
   casa fica VERDE e MUDO enquanto a pessoa perde 43% dos pacotes.
2. **Devolver `Varredura()` no lugar de `Varredura(motivo=SEM_BUSCTL)`**:
   reprova `test_sem_busctl_a_resposta_e_nao_sei_e_nunca_nenhum`. É a assinatura
   das dez réguas que caíram em 20/09 — `set()` vazio querendo dizer as duas
   coisas opostas.
3. **Somar o adaptador que diz `Discovering=true` sem dizer `Address`** (pôr
   `hci` em `varrendo` em vez de `mudos`): reprova
   `test_quem_varre_sem_endereco_legivel_nao_entra_como_varrendo` com um
   `varrendo` que contém `hci7` — chave que plano nenhum reivindica.
4. **Ler `Discovering` ausente como `false`** (`continue` no lugar de
   `mudos.add(hci)`): reprova `test_adaptador_mudo_nao_e_adaptador_parado`.
5. **Trocar o "fim da fila" por EXCLUSÃO** em `ordem_de_redistribuicao` (filtrar
   `p.endereco not in em_busca` em vez de ordenar por isso): reprova
   `test_o_unico_destino_possivel_continua_valendo_mesmo_varrendo` com
   `ordem is None` — a máquina de dois adaptadores fica MUDA exatamente onde a
   perda é maior, e calar não é conselho.
6. **Arrancar a chave de ordenação** (voltar a `key=lambda p:
   p.agora.fracao_total`): reprova
   `test_o_destino_que_varre_desce_para_o_fim_da_fila` e o oráculo — o motor
   volta a mandar o controle para o adaptador que varre.

E AS TRÊS QUE SOBRAM
--------------------
7. **Mexer em `QUEDA_MINIMA_MEDIDA`/`QUEDA_MAXIMA_MEDIDA` sem mexer no
   `doctor.sh`**: reprova `test_o_doctor_cita_os_numeros_do_dono`. Os dois
   números viviam como PROSA em cinco arquivos e não tinham dono; agora têm um,
   e esta régua é o que impede a segunda grafia de nascer.
8. **Trocar o corpo de `varredura_recente` por `quem_esta_varrendo()`**:
   reprova `test_a_lembranca_poupa_o_barramento_dentro_da_validade` — a
   thread do GTK volta a abrir subprocesso a cada pintura, que é a forma do
   travamento de 15/09/2026.
9. As duas da FIAÇÃO moram em
   `tests/unit/test_a_conta_de_slots_por_adaptador.py`, bloco 9: a seção
   passando a varredura ao motor, e a guarda que impede a suíte de abrir
   sete processos contra o `bluetoothd` DELA.

AS DUAS QUE A CONFERÊNCIA ADVERSARIAL ACRESCENTOU (20/09/2026)
---------------------------------------------------------------
As nove acima foram arrancadas uma a uma e as nove reprovaram. O que elas não
cobriam apareceu ao pôr um `busctl` que NÃO RESPONDE na frente do `PATH` — o
barramento travado, que é o caso que a lembrança de 3 s não alcança:

10. **Arrancar o `ORCAMENTO_DA_LEITURA`** (devolver o padrão de 5,0 s a
    `_rodar`): reprova `test_o_barramento_travado_nao_segura_a_thread_do_desenho`.
    MEDIDO: com três adaptadores e o `busctl` travado a leitura segurava a
    thread por **15,1 s** — e quem a chama é `_aplicar_estado`, que o
    `ipc_bridge.call_async` reposta por `GLib.idle_add`, ou seja, a thread do
    DESENHO. A lembrança segurava a frequência e não a duração: é o travamento
    de 15/09/2026 escrito de novo, com o rádio no caminho da pintura.
11. **Arrancar o `MESA_TODA_MUDA`**: reprova
    `test_a_mesa_toda_muda_nao_e_uma_mesa_parada`. Com o barramento travado a
    leitura voltava com `sei=True` e `varrendo` vazio — o `set()` ambíguo que
    este módulo existe para matar, entrando pela porta dos fundos: ninguém foi
    ouvido, e a resposta dizia "ninguém varre".
"""

from __future__ import annotations

import os
import shutil
import time
from pathlib import Path
from typing import Any

import pytest

from hefesto_dualsense4unix.integrations import bluez_dbus, plano_de_radio, varredura_do_radio
from hefesto_dualsense4unix.integrations.radio_da_mesa import (
    PALAVRAS_DE_CULPA,
)
from tests.unit import barramento_de_mentira as bm

REPO_ROOT = Path(__file__).resolve().parents[2]
DOCTOR = (REPO_ROOT / "scripts" / "doctor.sh").read_text(encoding="utf-8")

#: Os controles da mesa de mentira. Faixa sintética da casa — nunca MAC real
#: nem mascarado em fixture.
P1 = "aa:bb:cc:00:00:11"
P2 = "aa:bb:cc:00:00:22"
P3 = "aa:bb:cc:00:00:33"
P4 = "aa:bb:cc:00:00:44"
P5 = "aa:bb:cc:00:00:55"
P6 = "aa:bb:cc:00:00:66"
P7 = "aa:bb:cc:00:00:77"
P8 = "aa:bb:cc:00:00:88"


# ---------------------------------------------------------------------------
# A bancada
# ---------------------------------------------------------------------------


def _ligar_o_barramento(
    monkeypatch: pytest.MonkeyPatch,
    tmp_path: Path,
    adaptadores: dict[str, tuple[str | None, str | None]],
) -> None:
    """Põe o `busctl` de mentira na frente do `PATH` desta corrida, e só dela."""
    raiz = bm.montar_adaptadores(tmp_path, adaptadores)
    for chave, valor in bm.ambiente_de_leitura(raiz).items():
        monkeypatch.setenv(chave, valor)


def _sem_dois_pontos(mac: str) -> str:
    """Como o `uniq` do estado do daemon chega: 12 hex, sem separador."""
    return mac.replace(":", "")


def _bancada(mapa: dict[str, str]) -> dict[str, Any]:
    """Um `/sys/class/hidraw` de mentira: `{uniq do controle: MAC do adaptador}`.

    Mesma forma de `test_a_conta_de_slots_por_adaptador._bancada`. Sem ela o
    teste mediria a bancada de quem o roda — e quem o roda é a mesa DELA, com
    quatro DualSense de pé.
    """
    nos = {f"hidraw{i}": (uniq, phys) for i, (uniq, phys) in enumerate(mapa.items())}
    textos = {
        f"/sys/class/hidraw/{no}/device/uevent": f"HID_UNIQ={uniq}\nHID_PHYS={phys}\n"
        for no, (uniq, phys) in nos.items()
    }
    return {
        "listar": lambda _raiz: sorted(nos),
        "ler": lambda caminho: textos.get(caminho, ""),
    }


def _controle(uniq: str, slot: int | None = None, *, ponte: str | None = None) -> dict[str, Any]:
    """Um controle no rádio. ``ponte`` é a ponte de som/vibração DELE de pé —
    é o que o «Equilibrar» pesa desde 23/09/2026 (MOVER-UM-POR-VEZ-01)."""
    return {
        "transport": "bt",
        "connected": True,
        "uniq": _sem_dois_pontos(uniq),
        "player_slot": slot,
        "ponte_do_radio": ponte,
    }


def _mesa_apertada_com_dois_destinos() -> dict[str, plano_de_radio.PlanoDoAdaptador]:
    """Cinco controles apertando um adaptador, e DOIS destinos que cabem.

    O ARRANJO DIFÍCIL, e ele é o ponto: **o destino mais folgado é o que
    varre**. Um com um controle (o que varre), outro com dois. Pelo critério de
    sempre — menor ocupação primeiro — o motor escolhe exatamente o errado, e é
    isso que a chave de ordenação nova tem de virar.

    Montar o contrário (o que varre já cheio) daria uma régua verde sobre nada:
    ela passaria com o filtro arrancado.

    **E um adaptador sem controle nenhum não vira plano** — quando ninguém diz
    que ele existe. `plano_por_adaptador` monta a mesa a partir dos CONTROLES;
    desde 23/09/2026 (MOVER-UM-POR-VEZ-01) o dongle vazio entra quando vem em
    ``adaptadores=`` ou no ``ar=``, e esta mesa não passa nenhum dos dois de
    propósito: o arranjo difícil é o de dois destinos OCUPADOS.

    A ordem nasce por PONTES desde 23/09/2026: três de som no adaptador parado,
    contra o limite de duas.
    """
    return plano_de_radio.plano_por_adaptador(
        [
            _controle(P1, 1, ponte="som"),
            _controle(P2, 2, ponte="som"),
            _controle(P3, 3, ponte="som"),
            _controle(P4, 4),
            _controle(P5, 5),
            _controle(P6, 6),
            _controle(P7, 7),
            _controle(P8, 8),
        ],
        com_ponte_de_mic=[_sem_dois_pontos(p) for p in (P1, P2, P3, P4, P5)],
        apelidos={
            bm.ADAPTADOR_PARADO: "Dongle da frente",
            bm.ADAPTADOR_QUE_VARRE: "Dongle de trás",
            bm.ADAPTADOR_FOLGADO: "Dongle do meio",
        },
        **_bancada(
            {
                P1: bm.ADAPTADOR_PARADO,
                P2: bm.ADAPTADOR_PARADO,
                P3: bm.ADAPTADOR_PARADO,
                P4: bm.ADAPTADOR_PARADO,
                P5: bm.ADAPTADOR_PARADO,
                # UM controle: é o mais folgado dos dois destinos, e é o que
                # varre. O critério de sempre o elege.
                P6: bm.ADAPTADOR_QUE_VARRE,
                # DOIS controles: cabe mais um, mas perde no desempate de folga.
                P7: bm.ADAPTADOR_FOLGADO,
                P8: bm.ADAPTADOR_FOLGADO,
            }
        ),
    )


# ---------------------------------------------------------------------------
# 1. O leitor — e "não sei" nunca é "nenhum"
# ---------------------------------------------------------------------------


def test_o_leitor_responde_pelo_endereco_e_nunca_pelo_hci_n(
    monkeypatch: pytest.MonkeyPatch, tmp_path: Path
) -> None:
    """MORDIDA 1. A chave é o BD Address, porque `hciN` inverte entre boots.

    O BlueZ devolve `s "AA:BB:CC:00:00:A1"` em MAIÚSCULAS e o `HID_PHYS` do
    uevent publica minúsculo. Este nó exige o casamento: devolver o que o
    `busctl` escreveu, sem normalizar, faria o filtro do motor comparar duas
    grafias do mesmo endereço e nunca casar.
    """
    _ligar_o_barramento(
        monkeypatch,
        tmp_path,
        {
            "hci7": (bm.ADAPTADOR_QUE_VARRE, "true"),
            "hci8": (bm.ADAPTADOR_PARADO, "false"),
            "hci9": (bm.ADAPTADOR_FOLGADO, "false"),
        },
    )
    leitura = varredura_do_radio.quem_esta_varrendo()

    assert leitura.sei, leitura.motivo
    assert leitura.completa
    assert leitura.varrendo == frozenset({bm.ADAPTADOR_QUE_VARRE}), (
        "o leitor tem de responder pelo ENDEREÇO minúsculo — um `hciN` aqui "
        "casaria hoje e erraria no próximo boot, calado"
    )
    assert not any(nome.startswith("hci") for nome in leitura.varrendo)


def test_sem_busctl_a_resposta_e_nao_sei_e_nunca_nenhum(
    monkeypatch: pytest.MonkeyPatch, tmp_path: Path
) -> None:
    """MORDIDA 2. Sem ferramenta para perguntar, a resposta é "não sei".

    Um `PATH` sem `busctl` e sem o Gio é o caso de um sandbox sem o `org.bluez`
    (o runtime do Flatpak não traz o `busctl`). Devolver `varrendo=set()` sem
    motivo faria a tela e o motor lerem "nenhum adaptador está varrendo" sobre
    uma máquina em que ninguém olhou — a assinatura das dez réguas de 20/09.
    """
    vazio = tmp_path / "path-sem-busctl"
    vazio.mkdir()
    monkeypatch.setenv("PATH", str(vazio))
    assert shutil.which("busctl") is None, "o cenário precisa de um PATH sem busctl"

    leitura = varredura_do_radio.quem_esta_varrendo()

    assert not leitura.sei
    assert leitura.motivo == varredura_do_radio.SEM_BUSCTL
    assert leitura.varrendo == frozenset()
    assert "não" in leitura.motivo, "a ausência tem de se declarar em português"


def test_bluez_mudo_e_nao_sei_e_nunca_uma_mesa_vazia(
    monkeypatch: pytest.MonkeyPatch, tmp_path: Path
) -> None:
    """`busctl` existe e o `org.bluez` não responde: continua sendo "não sei".

    É o `bluetoothd` parado, e o produto NÃO pode ler isso como "nenhum
    adaptador varre" — a diferença entre as duas é a diferença entre avisar e
    calar sobre 43% dos pacotes dela.
    """
    _ligar_o_barramento(monkeypatch, tmp_path, {})
    leitura = varredura_do_radio.quem_esta_varrendo()

    assert not leitura.sei
    assert leitura.motivo == varredura_do_radio.SEM_BLUEZ
    assert leitura.varrendo == frozenset()


def test_quem_varre_sem_endereco_legivel_nao_entra_como_varrendo(
    monkeypatch: pytest.MonkeyPatch, tmp_path: Path
) -> None:
    """MORDIDA 3. `Discovering=true` sem `Address` é "não sei", não um destino.

    O ARRANJO DIFÍCIL: o adaptador está mesmo varrendo, e mesmo assim não pode
    entrar em `varrendo` — porque sem endereço não há com que casar. Pôr `hci7`
    ali no lugar daria um conjunto que plano nenhum reivindica: o filtro do
    motor rodaria, não casaria com nada, e ficaria verde sobre o defeito vivo.

    Ele também não pode sumir: vai para `mudos`, que é a parte da resposta que
    não existe.
    """
    _ligar_o_barramento(
        monkeypatch,
        tmp_path,
        {
            "hci7": (None, "true"),
            "hci8": (bm.ADAPTADOR_PARADO, "false"),
        },
    )
    leitura = varredura_do_radio.quem_esta_varrendo()

    assert leitura.varrendo == frozenset(), (
        "um adaptador sem endereço legível não é destino de nada — e um `hci7` "
        "em `varrendo` é uma chave que plano nenhum reivindica"
    )
    assert leitura.mudos == frozenset({"hci7"})
    assert leitura.sei, "a leitura aconteceu; o que falta é UM adaptador"
    assert not leitura.completa, "e `completa` é o que confessa essa falta"


def test_adaptador_mudo_nao_e_adaptador_parado(
    monkeypatch: pytest.MonkeyPatch, tmp_path: Path
) -> None:
    """MORDIDA 4. `Discovering` que não responde não é `Discovering=false`.

    Adaptador em `down` ou sob `rfkill` some da propriedade e fica na árvore.
    Lê-lo como "parado" é a mesma família do `set()` ambíguo, um nível abaixo.
    """
    _ligar_o_barramento(
        monkeypatch,
        tmp_path,
        {
            "hci7": (bm.ADAPTADOR_QUE_VARRE, None),
            "hci8": (bm.ADAPTADOR_PARADO, "false"),
        },
    )
    leitura = varredura_do_radio.quem_esta_varrendo()

    assert leitura.mudos == frozenset({"hci7"})
    assert leitura.varrendo == frozenset()
    assert not leitura.completa


def test_a_mesa_inteira_parada_e_uma_resposta_de_verdade(
    monkeypatch: pytest.MonkeyPatch, tmp_path: Path
) -> None:
    """O contrapeso das quatro acima: quando NINGUÉM varre, o produto sabe.

    Sem este nó as cinco réguas de ausência passariam com um leitor que
    devolvesse "não sei" para tudo — e um leitor que nunca sabe nada é um
    leitor que nunca filtra nada.
    """
    _ligar_o_barramento(
        monkeypatch,
        tmp_path,
        {
            "hci7": (bm.ADAPTADOR_QUE_VARRE, "false"),
            "hci8": (bm.ADAPTADOR_PARADO, "false"),
        },
    )
    leitura = varredura_do_radio.quem_esta_varrendo()

    assert leitura.completa
    assert leitura.varrendo == frozenset()
    assert leitura.mudos == frozenset()


# ---------------------------------------------------------------------------
# 2. O filtro no MOTOR — fim da fila, nunca fora dela
# ---------------------------------------------------------------------------


def test_o_destino_que_varre_desce_para_o_fim_da_fila() -> None:
    """MORDIDA 6. Havendo outro destino que caiba, o que varre perde a vez.

    A mesa é montada com o adaptador que varre sendo o MAIS FOLGADO — o destino
    que o critério de sempre escolheria. Arrancar a chave de ordenação faz o
    motor voltar a mandar o controle para dentro da varredura, que é o defeito
    inteiro da sprint.
    """
    planos = _mesa_apertada_com_dois_destinos()

    sem_leitura = plano_de_radio.ordem_de_redistribuicao(planos)
    assert sem_leitura is not None
    assert sem_leitura.destino == bm.ADAPTADOR_QUE_VARRE, (
        "o cenário só morde se, SEM a leitura, o motor escolhesse o adaptador "
        "que varre — senão a régua mede o arranjo fácil"
    )

    com_leitura = plano_de_radio.ordem_de_redistribuicao(
        planos, varrendo={bm.ADAPTADOR_QUE_VARRE}
    )
    assert com_leitura is not None
    assert com_leitura.destino == bm.ADAPTADOR_FOLGADO
    assert com_leitura.destino_na_tela == "Dongle do meio"


def test_o_unico_destino_possivel_continua_valendo_mesmo_varrendo() -> None:
    """MORDIDA 5. O filtro é ORDENAÇÃO, não exclusão — e é isso que o prova.

    Numa mesa de dois adaptadores em que o único destino possível está
    varrendo, excluir devolveria `None` e a tela calaria. Calar é pior: a
    origem está apertada, o destino tem fila menor mesmo varrendo, e a pessoa
    fica sem conselho nenhum.

    *Excluir mataria a máquina de um adaptador só* — a frase é da sprint, e
    este nó é a forma medida dela.
    """
    planos = plano_de_radio.plano_por_adaptador(
        [
            _controle(P1, 1, ponte="som"),
            _controle(P2, 2, ponte="som"),
            _controle(P3, 3, ponte="som"),
            _controle(P4, 4),
            _controle(P5, 5),
            _controle(P6, 6),
        ],
        com_ponte_de_mic=[_sem_dois_pontos(p) for p in (P1, P2, P3, P4, P5)],
        apelidos={
            bm.ADAPTADOR_PARADO: "Dongle da frente",
            bm.ADAPTADOR_QUE_VARRE: "Dongle de trás",
        },
        **_bancada(
            {
                P1: bm.ADAPTADOR_PARADO,
                P2: bm.ADAPTADOR_PARADO,
                P3: bm.ADAPTADOR_PARADO,
                P4: bm.ADAPTADOR_PARADO,
                P5: bm.ADAPTADOR_PARADO,
                P6: bm.ADAPTADOR_QUE_VARRE,
            }
        ),
    )
    ordem = plano_de_radio.ordem_de_redistribuicao(
        planos, varrendo={bm.ADAPTADOR_QUE_VARRE}
    )

    assert ordem is not None, (
        "o único destino possível está varrendo, e o motor calou — excluir "
        "mataria a máquina de um adaptador só"
    )
    assert ordem.destino == bm.ADAPTADOR_QUE_VARRE


def test_sem_leitura_o_motor_escolhe_exatamente_como_escolhia() -> None:
    """"Não sei" nunca vira penalidade — a hipótese explica o que JÁ funcionava.

    `varrendo=None` é o padrão e é o caso de toda máquina sem BlueZ acessível.
    Se a ausência de leitura mudasse o destino, o produto estaria movendo
    controle por palpite.
    """
    planos = _mesa_apertada_com_dois_destinos()

    assert plano_de_radio.ordem_de_redistribuicao(
        planos
    ) == plano_de_radio.ordem_de_redistribuicao(planos, varrendo=None)
    assert plano_de_radio.ordem_de_redistribuicao(
        planos, varrendo=frozenset()
    ) == plano_de_radio.ordem_de_redistribuicao(planos)


def test_a_mesa_folgada_nao_vira_ordem_so_porque_alguem_varre() -> None:
    """Varredura não cria ordem de serviço — ela só reordena os destinos.

    Sem este nó, um filtro escrito como "se alguém varre, mande mover" passaria
    despercebido: o produto mandaria a pessoa mexer na mesa toda vez que ela
    abrisse a tela de Bluetooth, com o rádio folgado.
    """
    planos = plano_de_radio.plano_por_adaptador(
        [_controle(P1, 1), _controle(P2, 2)],
        apelidos={bm.ADAPTADOR_QUE_VARRE: "Dongle de trás"},
        **_bancada({P1: bm.ADAPTADOR_QUE_VARRE, P2: bm.ADAPTADOR_PARADO}),
    )
    assert (
        plano_de_radio.ordem_de_redistribuicao(
            planos, varrendo={bm.ADAPTADOR_QUE_VARRE}
        )
        is None
    )


# ---------------------------------------------------------------------------
# 3. O ORÁCULO — o leitor de verdade, ligado ao motor de verdade
# ---------------------------------------------------------------------------


def test_o_oraculo_a_varredura_muda_o_destino_da_ordem(
    monkeypatch: pytest.MonkeyPatch, tmp_path: Path
) -> None:
    """A prova da sprint, ponta a ponta: liga a busca e a ordem muda de destino.

    É o oráculo que a sprint pede — *"`bluetoothctl scan on` num adaptador, e a
    ordem de serviço tem de mudar de destino"* — rodado contra o barramento de
    mentira, porque ligar busca de verdade custa 43% dos pacotes dela.

    E é ele que fecha o buraco que nó nenhum dos dois blocos acima fecha
    sozinho: os do leitor passariam com um motor que ignora a leitura, e os do
    motor passariam com um leitor que devolve `hciN`. **Este exige que as duas
    metades falem a MESMA língua de endereço.** Foi assim que a régua do rótulo
    do gravador passou por semanas conferindo dois nomes que nunca colidiam.
    """
    planos = _mesa_apertada_com_dois_destinos()

    # ANTES: ninguém varre, e o motor manda para o mais folgado.
    _ligar_o_barramento(
        monkeypatch,
        tmp_path / "parado",
        {
            "hci7": (bm.ADAPTADOR_QUE_VARRE, "false"),
            "hci8": (bm.ADAPTADOR_FOLGADO, "false"),
        },
    )
    parada = varredura_do_radio.quem_esta_varrendo()
    antes = plano_de_radio.ordem_de_redistribuicao(planos, varrendo=parada.varrendo)
    assert antes is not None
    assert antes.destino == bm.ADAPTADOR_QUE_VARRE

    # DEPOIS: `scan on` naquele mesmo adaptador — e só nele.
    _ligar_o_barramento(
        monkeypatch,
        tmp_path / "varrendo",
        {
            "hci7": (bm.ADAPTADOR_QUE_VARRE, "true"),
            "hci8": (bm.ADAPTADOR_FOLGADO, "false"),
        },
    )
    varrendo = varredura_do_radio.quem_esta_varrendo()
    assert varrendo.varrendo == frozenset({bm.ADAPTADOR_QUE_VARRE})

    depois = plano_de_radio.ordem_de_redistribuicao(planos, varrendo=varrendo.varrendo)
    assert depois is not None
    assert depois.destino == bm.ADAPTADOR_FOLGADO, (
        "a busca subiu e a ordem de serviço não mudou de destino — o leitor e o "
        "motor não estão falando a mesma língua de endereço"
    )
    assert antes.origem == depois.origem, "só o destino muda; a origem é a mesma"


# ---------------------------------------------------------------------------
# 4. O doctor — o CUSTO medido, não só o estado
# ---------------------------------------------------------------------------


def test_o_doctor_cita_os_numeros_do_dono() -> None:
    """MORDIDA 7. Mexer na constante sem mexer no `doctor.sh` reprova aqui.

    Os dois números viviam como PROSA em cinco arquivos, sem dono. Esta régua
    não é tautologia: ela monta o esperado a partir do DONO em Python e o
    procura no texto BASH, que é a outra grafia — as duas só passam juntas
    quando concordam de verdade.
    """
    minimo = varredura_do_radio.QUEDA_MINIMA_MEDIDA
    maximo = varredura_do_radio.QUEDA_MAXIMA_MEDIDA
    esperado_min = f"{minimo:.1f}".replace(".", ",")
    esperado_max = f"{maximo:.1f}".replace(".", ",")

    bloco = DOCTOR.split("Discovering: yes")[1][:900]
    assert f"{esperado_min}%" in bloco, (
        f"o doctor não cita a queda mínima medida ({esperado_min}%) — o número "
        "tem dono em varredura_do_radio.QUEDA_MINIMA_MEDIDA"
    )
    assert f"{esperado_max}%" in bloco


def test_o_aviso_do_doctor_diz_o_custo_e_nao_so_o_estado() -> None:
    """O que a sprint pediu: o aviso já estava no lugar certo e calava o preço.

    Um aviso sem tamanho se lê como zelo e se ignora. Este nó exige as três
    coisas que o tornam acionável: que foi MEDIDO, o alcance (NESTE adaptador,
    porque as corridas cruzadas deram ruído) e a CAUDA de 21 segundos — sem ela
    a pessoa fecha a tela, mede na hora e conclui que o aviso mente.
    """
    bloco = DOCTOR.split("Discovering: yes")[1][:900]
    assert "MEDIDO" in bloco
    assert "NESTE adaptador" in bloco
    assert "21 s" in bloco, "a cauda de 21 s é o que impede o aviso de parecer falso"


def test_o_aviso_do_doctor_nao_culpa_ninguem() -> None:
    """Nenhuma palavra de culpa no texto que CHEGA a ela.

    Rádio ocupado não é aparelho com defeito, e a mesma varredura de
    `PALAVRAS_DE_CULPA` que o `plano_de_radio` sofre vale aqui. O aviso nomeia o
    que foi medido e para.

    **Ele mede o BASH, e não uma frase em Python, porque a frase em Python
    morreu.** Ela existiu por meia hora nesta leva e era a MESMA sentença do
    `doctor.sh` escrita duas vezes — a segunda grafia do mesmo fato, que é o
    defeito que esta casa mata por regra. Quem a matou foi o portão `casa-sabe`:
    nenhum caminho do produto a alcançava.
    """
    bloco = DOCTOR.split("Discovering: yes")[1][:900].lower()
    for palavra in PALAVRAS_DE_CULPA:
        assert palavra not in bloco, f"«{palavra}» culpa alguém pelo rádio ocupado"


# ---------------------------------------------------------------------------
# 5. A lembrança — o rádio fora do caminho do desenho
# ---------------------------------------------------------------------------


def test_a_lembranca_poupa_o_barramento_dentro_da_validade(
    monkeypatch: pytest.MonkeyPatch, tmp_path: Path
) -> None:
    """MORDIDA 8. Arrancar a validade faz a tela perguntar a cada pintura.

    `varredura_recente` é o que o produto chama. Medido em 20/09 contra o BlueZ
    vivo desta bancada, uma leitura custa 8,4 ms de mediana — barato, e não de
    graça: quem chama é a thread do GTK, redesenhada a cada resposta do daemon.
    Pôr rádio no caminho do desenho é a forma exata do travamento de 15/09/2026.

    Trocar o corpo por `return quem_esta_varrendo()` reprova aqui com
    `perguntas == [1, 1, 1]`.
    """
    monkeypatch.setattr(varredura_do_radio, "_LEMBRANCA", None)
    _ligar_o_barramento(
        monkeypatch, tmp_path, {"hci7": (bm.ADAPTADOR_QUE_VARRE, "true")}
    )
    perguntas: list[float] = []
    relogio = iter([0.0, 1.0, 2.9, 3.1])
    original = varredura_do_radio.quem_esta_varrendo

    def contar(**kwargs: Any) -> Any:
        perguntas.append(1.0)
        return original(**kwargs)

    monkeypatch.setattr(varredura_do_radio, "quem_esta_varrendo", contar)
    for _ in range(4):
        leitura = varredura_do_radio.varredura_recente(relogio=lambda: next(relogio))

    assert leitura.varrendo == frozenset({bm.ADAPTADOR_QUE_VARRE})
    assert len(perguntas) == 2, (
        "quatro chamadas em 3,1 s deviam custar DUAS perguntas ao barramento "
        f"(uma por janela de {varredura_do_radio.SEGUNDOS_DE_VALIDADE} s), e "
        f"custaram {len(perguntas)}"
    )


def test_a_lembranca_nao_congela_a_resposta_para_sempre(
    monkeypatch: pytest.MonkeyPatch, tmp_path: Path
) -> None:
    """O contrapeso: passada a validade, o produto vê a busca que SUBIU.

    Sem este nó, um cache eterno passaria na régua acima — e a tela continuaria
    mandando o controle para dentro da busca por toda a sessão.
    """
    monkeypatch.setattr(varredura_do_radio, "_LEMBRANCA", None)
    _ligar_o_barramento(
        monkeypatch, tmp_path / "antes", {"hci7": (bm.ADAPTADOR_QUE_VARRE, "false")}
    )
    relogio = iter([0.0, 100.0])
    assert (
        varredura_do_radio.varredura_recente(relogio=lambda: next(relogio)).varrendo
        == frozenset()
    )

    _ligar_o_barramento(
        monkeypatch, tmp_path / "depois", {"hci7": (bm.ADAPTADOR_QUE_VARRE, "true")}
    )
    assert varredura_do_radio.varredura_recente(
        relogio=lambda: next(relogio)
    ).varrendo == frozenset({bm.ADAPTADOR_QUE_VARRE})


# ---------------------------------------------------------------------------
# 6. O produto é de outra pessoa também
# ---------------------------------------------------------------------------


def test_o_leitor_nao_presume_bancada_nenhuma(
    monkeypatch: pytest.MonkeyPatch, tmp_path: Path
) -> None:
    """Um adaptador só, e o leitor responde igual — a ordem dela de 11/09.

    A reserva estática morreu justamente por presumir três adaptadores. O
    substituto tem de responder na máquina de UM, que é a de quase todo mundo.
    """
    _ligar_o_barramento(monkeypatch, tmp_path, {"hci7": (bm.ADAPTADOR_QUE_VARRE, "true")})
    leitura = varredura_do_radio.quem_esta_varrendo()

    assert leitura.completa
    assert leitura.varrendo == frozenset({bm.ADAPTADOR_QUE_VARRE})


def test_o_leitor_nao_toca_no_radio_de_ninguem(tmp_path: Path) -> None:
    """Ler é tudo o que se pode fazer daqui, e o fonte tem de dizer isso.

    O BlueZ conta `discovery` POR CLIENTE — medido em 19/09: `StopDiscovery` de
    terceiro devolve `No discovery started` e a busca continua. Um módulo que
    tentasse desligar a busca alheia falharia em silêncio e daria à casa a
    ilusão de uma alavanca que não existe.
    """
    fonte = Path(varredura_do_radio.__file__).read_text(encoding="utf-8")
    corpo = fonte.split('"""', 2)[2]
    for verbo in ("StartDiscovery", "StopDiscovery", "set-property", "Powered"):
        assert verbo not in corpo, f"o leitor não pode chamar {verbo}"
    # BLUEZ-UM-DONO-01: o leitor pergunta ao dono do BlueZ, e nenhuma escrita
    # do dono aparece aqui. A leitura tem de estar lá — senão esta régua passa
    # sobre um módulo que não pergunta nada.
    for escrita in bluez_dbus.ESCRITAS:
        assert f".{escrita}(" not in corpo, f"o leitor não pode chamar {escrita}"
    assert ".propriedade(" in corpo


def test_o_leitor_nao_deixa_o_locale_cegar_a_leitura(
    monkeypatch: pytest.MonkeyPatch, tmp_path: Path
) -> None:
    """`LC_ALL=C` no ambiente do subprocesso — o `pactl` já cegou dois leitores.

    Um leitor traduzido responde "não há" sobre aparelho de pé. Aqui isso
    significaria dizer "ninguém varre" enquanto ela perde 43% dos pacotes.
    """
    vistos: list[dict[str, str]] = []
    # O subprocesso mora no dono do BlueZ desde a BLUEZ-UM-DONO-01.
    original = bluez_dbus.subprocess.run

    def espiar(*args: Any, **kwargs: Any) -> Any:
        vistos.append(dict(kwargs.get("env") or {}))
        return original(*args, **kwargs)

    _ligar_o_barramento(monkeypatch, tmp_path, {"hci7": (bm.ADAPTADOR_PARADO, "false")})
    monkeypatch.setattr(bluez_dbus.subprocess, "run", espiar)
    varredura_do_radio.quem_esta_varrendo()

    assert vistos, "o leitor não abriu subprocesso nenhum"
    assert all(env.get("LC_ALL") == "C" for env in vistos)
    assert all("PATH" in env for env in vistos), (
        "o ambiente do subprocesso perdeu o PATH — o `busctl` não seria achado"
    )


def test_o_leitor_nao_levanta_quando_o_busctl_explode(
    monkeypatch: pytest.MonkeyPatch, tmp_path: Path
) -> None:
    """Nunca levanta: toda saída é uma `Varredura`, inclusive o erro do processo.

    Esta função é chamada de caminho de diagnóstico; uma exceção daqui derrubaria
    quem só queria saber se cabia mais um controle no adaptador.
    """
    raiz = bm.montar_adaptadores(tmp_path, {"hci7": (bm.ADAPTADOR_PARADO, "false")})
    quebrado = raiz / "bin" / "busctl"
    quebrado.write_text("#!/usr/bin/env bash\nexit 7\n", encoding="utf-8")
    quebrado.chmod(0o755)
    monkeypatch.setenv("PATH", f"{raiz / 'bin'}{os.pathsep}{os.environ.get('PATH', '')}")

    leitura = varredura_do_radio.quem_esta_varrendo()
    assert not leitura.sei
    assert leitura.varrendo == frozenset()


# ---------------------------------------------------------------------------
# 7. O BARRAMENTO TRAVADO — a conferência adversarial de 20/09/2026
# ---------------------------------------------------------------------------


def _busctl_que_trava(tmp_path: Path, quantos: int) -> Path:
    """Um `busctl` que LISTA a mesa e depois não responde mais nada.

    É a forma exata de um `bluetoothd` pendurado: o barramento aceita a
    chamada e nunca devolve. O `tree` responde de propósito — um `tree` mudo
    cairia no `SEM_BLUEZ` logo na porta e o cenário não chegaria a morder.
    """
    raiz = tmp_path / "barramento-travado"
    (raiz / "bin").mkdir(parents=True)
    nos = "".join(f"/org/bluez/hci{i}\n" for i in range(quantos))
    alvo = raiz / "bin" / "busctl"
    alvo.write_text(
        "#!/usr/bin/env bash\n"
        'case "${1:-}" in\n'
        f"  tree) printf '/org/bluez\\n{nos}'; exit 0 ;;\n"
        "  get-property) sleep 600 ;;\n"
        "esac\n"
        "exit 1\n",
        encoding="utf-8",
    )
    alvo.chmod(0o755)
    return raiz


def test_o_barramento_travado_nao_segura_a_thread_do_desenho(
    monkeypatch: pytest.MonkeyPatch, tmp_path: Path
) -> None:
    """MORDIDA 10. O orçamento da leitura, e ele é a thread do DESENHO que paga.

    `varredura_recente` é chamada de `_ContaDeSlots._aplicar_estado`, que o
    `ipc_bridge.call_async` reposta por `GLib.idle_add` — thread principal do
    GTK, a mesma que pinta. MEDIDO em 20/09/2026 com este mesmo cenário e o
    padrão de 5,0 s por pergunta: **15,1 s de janela presa**, três adaptadores,
    uma pergunta travada em cada.

    A lembrança de 3 s não alcança isso: ela segura quantas vezes se pergunta,
    não quanto tempo cada pergunta dura.

    TRÊS adaptadores de propósito — é a mesa dela, e é onde o defeito é maior.
    Com um só, um padrão de 5 s daria 5 s e o mesmo limite pegaria; com três,
    o arranjo difícil mostra que o corte é do ORÇAMENTO INTEIRO e não de uma
    pergunta.
    """
    raiz = _busctl_que_trava(tmp_path, 3)
    monkeypatch.setenv("PATH", f"{raiz / 'bin'}{os.pathsep}{os.environ.get('PATH', '')}")

    inicio = time.monotonic()
    leitura = varredura_do_radio.quem_esta_varrendo()
    custou = time.monotonic() - inicio

    assert custou < 2.0, (
        f"o barramento travado segurou a thread do desenho por {custou:.1f} s "
        f"— o orçamento é de {varredura_do_radio.ORCAMENTO_DA_LEITURA} s"
    )
    assert not leitura.sei, "leitura interrompida não pode dizer «ninguém varre»"
    assert leitura.motivo == varredura_do_radio.SEM_RESPOSTA_A_TEMPO
    assert leitura.varrendo == frozenset()


def test_o_orcamento_nao_corta_barramento_que_responde(
    monkeypatch: pytest.MonkeyPatch, tmp_path: Path
) -> None:
    """O contrapeso da 10: um corte que corta sempre não mede nada.

    Sem este nó, um `quem_esta_varrendo` que devolvesse
    `SEM_RESPOSTA_A_TEMPO` para tudo passaria na régua acima — e o produto
    ficaria cego para a busca que a pessoa abriu.
    """
    _ligar_o_barramento(
        monkeypatch,
        tmp_path,
        {
            "hci7": (bm.ADAPTADOR_QUE_VARRE, "true"),
            "hci8": (bm.ADAPTADOR_PARADO, "false"),
            "hci9": (bm.ADAPTADOR_FOLGADO, "false"),
        },
    )
    leitura = varredura_do_radio.quem_esta_varrendo()

    assert leitura.sei, leitura.motivo
    assert leitura.completa
    assert leitura.varrendo == frozenset({bm.ADAPTADOR_QUE_VARRE})


def test_a_mesa_toda_muda_nao_e_uma_mesa_parada(
    monkeypatch: pytest.MonkeyPatch, tmp_path: Path
) -> None:
    """MORDIDA 11. Ninguém foi ouvido — e isso não é «ninguém está varrendo».

    O ARRANJO DIFÍCIL, e é o que a régua do adaptador mudo não alcança: lá UM
    adaptador cala e o outro responde, então a leitura sabe alguma coisa. Aqui a
    mesa INTEIRA cala, e a resposta antiga voltava com `sei=True` e `varrendo`
    vazio — que é o `set()` querendo dizer as duas coisas opostas, o defeito que
    este módulo inteiro existe para matar.

    O único leitor do produto (`_ContaDeSlots._ler_a_varredura`) pega só
    `varrendo`; se `sei` não confessar sozinho, ninguém confessa.
    """
    _ligar_o_barramento(
        monkeypatch,
        tmp_path,
        {
            "hci7": (bm.ADAPTADOR_QUE_VARRE, None),
            "hci8": (bm.ADAPTADOR_PARADO, None),
        },
    )
    leitura = varredura_do_radio.quem_esta_varrendo()

    assert not leitura.sei, (
        "a mesa inteira calou e a leitura respondeu «sei» — «não ouvi ninguém» "
        "está sendo lido como «ninguém varre»"
    )
    assert leitura.motivo == varredura_do_radio.MESA_TODA_MUDA
    assert leitura.varrendo == frozenset()
    assert leitura.mudos == frozenset({"hci7", "hci8"})
