"""O medidor de rádio — a conta, o casamento controle-adaptador e a fronteira.

Este arquivo é PURO de propósito: nenhuma linha importa `gi`. A aritmética do
medidor, o casamento por `HID_PHYS` e as três palavras de ocupação não precisam
de GTK para existir, e um arquivo que exigisse PyGObject perderia a coleta
headless — que é onde a maioria das rodadas acontece. O que é de widget mora em
`app/widgets/sensor_widgets.py` e entra aqui só pela regra pura de saturação da
barra (`fatias_da_barra`), que o módulo expõe fora do ramo do GTK.

A MORDIDA, feita em 22/08/2026 e registrada aqui porque teste que passa com a
cura arrancada não testa nada:

* **arranquei** a exclusão de `transport != "bt"` de `ocupacao_por_adaptador`
  (a linha `if controle.get("transport") == "bt"` do filtro);
* **reprovaram DOIS nós**, com a mesma assinatura:
  `test_controle_no_cabo_nao_ocupa_radio_de_ninguem` e
  `test_o_controle_negativo_desta_bancada_e_o_cabo`. Os dois DualSense do cabo
  passaram a produzir uma barra de 520,8 fatias na chave de ausência — o
  produto acusando os próprios controles de encher um rádio que eles nem usam;
* **devolvi** a exclusão e os dois voltaram ao verde (21 passed).

Segunda mordida, na fronteira: troquei `PALAVRA_CHEIA` de `"Cheia"` para
`"Cheia — seu controle vai ficar ruim"` e
`test_nenhuma_palavra_do_medidor_carrega_culpa` reprovou pela palavra "ruim".
"""
from __future__ import annotations

import os
from collections.abc import Callable, Mapping

import pytest

from hefesto_dualsense4unix.app.actions.config.secao_mesa import (
    _medidores_da_mesa,
    _rotulo_do_medidor,
    _selo_da_ocupacao,
    _texto_acessivel,
)
from hefesto_dualsense4unix.app.widgets.sensor_widgets import fatias_da_barra
from hefesto_dualsense4unix.integrations.mesa_de_radio import Adaptador, Mesa
from hefesto_dualsense4unix.integrations.radio_da_mesa import (
    CORTE_APERTADA,
    CORTE_FOLGADA,
    HZ_AUDIO_COM_MIC,
    HZ_INPUT_COM_MIC,
    HZ_INPUT_SEM_MIC,
    PALAVRA_APERTADA,
    PALAVRA_CHEIA,
    PALAVRA_FOLGADA,
    PALAVRAS_DE_CULPA,
    SEM_ADAPTADOR,
    SLOTS_POR_SEGUNDO,
    Ocupacao,
    adaptador_por_uniq,
    ocupacao_por_adaptador,
    palavra_da_ocupacao,
)

#: Endereços mascarados pela regra da casa (octetos 4 e 5 zerados). Os dois
#: primeiros são os dois DualSense reais desta bancada, com a máscara aplicada;
#: os endereços de adaptador são inventados, porque não há adaptador nenhum
#: aqui para copiar (medido em 22/08/2026: `/sys/class/bluetooth` vazio).
UNIQ_A = "44:46:48:00:00:03"
UNIQ_B = "d4:2f:4b:00:00:d8"
ADAPTADOR_1 = "aa:bb:cc:00:00:33"
ADAPTADOR_2 = "aa:bb:cc:00:00:66"

#: O `HID_PHYS` REAL de um DualSense no cabo nesta máquina, lido do uevent em
#: 22/08/2026. Não é MAC: é caminho de barramento USB. É este valor que faz o
#: controle negativo da sprint ser executável sem dongle nenhum.
PHYS_DO_CABO = "usb-0000:0c:00.3-1/input3"


def _bancada(
    nos: Mapping[str, Mapping[str, str]],
) -> tuple[Callable[[str], list[str]], Callable[[str], str]]:
    """Um `/sys/class/hidraw` de mentira: `{nó: {chave do uevent: valor}}`.

    Devolve o par `(listar, ler)` que as funções do módulo aceitam por
    argumento — nenhum caminho real é aberto, e é por isso que este arquivo
    roda igual em qualquer máquina.
    """

    def listar(_raiz: str) -> list[str]:
        return sorted(nos)

    def ler(caminho: str) -> str:
        partes = caminho.split(os.sep)
        campos = nos.get(partes[-3] if len(partes) >= 3 else "")
        if campos is None:
            return ""
        return "".join(f"{chave}={valor}\n" for chave, valor in campos.items())

    return listar, ler


def _controle(uniq: str | None, transporte: str = "bt") -> dict[str, object]:
    """Um item de `state["controllers"]` no formato que o daemon publica."""
    return {"transport": transporte, "uniq": uniq, "connected": True}


def _hex(mac: str) -> str:
    """O `uniq` como o estado do daemon o escreve: 12 hex sem separador."""
    return mac.replace(":", "")


# -- o casamento controle -> adaptador ---------------------------------------


def test_o_hid_phys_de_um_controle_no_radio_e_o_endereco_do_adaptador() -> None:
    """É o casamento inteiro do medidor, e ele não custa `sudo`.

    `broker/hidraw_broker.py:281` já decide por este campo, com o comentário
    literal de que BT real tem `HID_PHYS` = MAC do adaptador.
    """
    listar, ler = _bancada(
        {"hidraw3": {"HID_UNIQ": UNIQ_A, "HID_PHYS": ADAPTADOR_1}}
    )

    assert adaptador_por_uniq([_hex(UNIQ_A)], listar=listar, ler=ler) == {
        _hex(UNIQ_A): ADAPTADOR_1
    }


def test_uniq_com_e_sem_dois_pontos_casam() -> None:
    """Os dois lados escrevem o mesmo endereço de jeitos diferentes.

    O estado do daemon dá 12 hex sem separador (`backend_pydualsense.py:4674`);
    o uevent dá MAC com dois-pontos. Sem normalizar os dois lados, o casamento
    falha em silêncio e a barra fica em zero com o rádio cheio.
    """
    listar, ler = _bancada(
        {"hidraw3": {"HID_UNIQ": UNIQ_A.upper(), "HID_PHYS": ADAPTADOR_1}}
    )

    assert adaptador_por_uniq([_hex(UNIQ_A)], listar=listar, ler=ler)[
        _hex(UNIQ_A)
    ] == ADAPTADOR_1
    assert adaptador_por_uniq([UNIQ_A], listar=listar, ler=ler)[UNIQ_A] == ADAPTADOR_1


def test_o_controle_negativo_desta_bancada_e_o_cabo() -> None:
    """Controle no fio traz caminho de barramento, e não ocupa rádio nenhum.

    É o controle negativo da sprint, e ele é executável HOJE: não há adaptador
    Bluetooth nesta máquina, e os dois DualSense do cabo trazem exatamente o
    `HID_PHYS` de :data:`PHYS_DO_CABO`. Devolver o caminho USB como se fosse
    endereço de adaptador criaria uma barra fantasma por porta USB.
    """
    listar, ler = _bancada(
        {"hidraw4": {"HID_UNIQ": UNIQ_A, "HID_PHYS": PHYS_DO_CABO}}
    )

    assert adaptador_por_uniq([_hex(UNIQ_A)], listar=listar, ler=ler) == {
        _hex(UNIQ_A): SEM_ADAPTADOR
    }

    ocupacoes = ocupacao_por_adaptador(
        [_controle(_hex(UNIQ_A), transporte="usb")], listar=listar, ler=ler
    )
    assert ocupacoes == {}


def test_o_vpad_nao_vira_adaptador() -> None:
    """O nosso vpad anuncia `hefesto-vpad` em `HID_PHYS` — não é MAC."""
    listar, ler = _bancada(
        {"hidraw5": {"HID_UNIQ": UNIQ_A, "HID_PHYS": "hefesto-vpad"}}
    )

    assert adaptador_por_uniq([_hex(UNIQ_A)], listar=listar, ler=ler) == {
        _hex(UNIQ_A): SEM_ADAPTADOR
    }


def test_sysfs_ilegivel_devolve_ausencia_e_nao_levanta() -> None:
    """Leitura falha vira "não sei", nunca um adaptador chutado.

    `broker/hidraw_broker.py:166-172` mede que o sysfs de Bluetooth é instável
    ao vivo — adaptador em down, rfkill, hci sem `address`. Uma exceção aqui
    derrubaria a troca de aba; um adaptador inventado seria pior.
    """

    def listar_que_falha(_raiz: str) -> list[str]:
        raise OSError("sysfs sumiu sob a mão")

    assert adaptador_por_uniq(
        [_hex(UNIQ_A)], listar=listar_que_falha, ler=lambda _c: ""
    ) == {_hex(UNIQ_A): SEM_ADAPTADOR}

    ocupacoes = ocupacao_por_adaptador(
        [_controle(_hex(UNIQ_A))], listar=listar_que_falha, ler=lambda _c: ""
    )
    assert list(ocupacoes) == [SEM_ADAPTADOR]
    assert ocupacoes[SEM_ADAPTADOR].controles == 1


# -- a conta ------------------------------------------------------------------


def test_controle_no_cabo_nao_ocupa_radio_de_ninguem() -> None:
    """O cabo não toca no rádio, e o vpad não tem rádio para tocar.

    Mordida: arrancar a exclusão de `transport != "bt"`. Sem ela os dois
    DualSense do cabo desta bancada apareceriam como 520,8 fatias ocupadas — o
    produto acusando os próprios controles de encher um rádio que eles nem
    usam.
    """
    listar, ler = _bancada(
        {
            "hidraw4": {"HID_UNIQ": UNIQ_A, "HID_PHYS": PHYS_DO_CABO},
            "hidraw6": {"HID_UNIQ": UNIQ_B, "HID_PHYS": PHYS_DO_CABO},
        }
    )

    ocupacoes = ocupacao_por_adaptador(
        [
            _controle(_hex(UNIQ_A), transporte="usb"),
            _controle(_hex(UNIQ_B), transporte="usb"),
        ],
        listar=listar,
        ler=ler,
    )

    assert ocupacoes == {}


def test_dois_controles_no_mesmo_adaptador_somam_na_mesma_barra() -> None:
    """Dividir o mesmo rádio é somar no mesmo teto — é o ponto do medidor."""
    listar, ler = _bancada(
        {
            "hidraw3": {"HID_UNIQ": UNIQ_A, "HID_PHYS": ADAPTADOR_1},
            "hidraw4": {"HID_UNIQ": UNIQ_B, "HID_PHYS": ADAPTADOR_1},
        }
    )

    ocupacoes = ocupacao_por_adaptador(
        [_controle(_hex(UNIQ_A)), _controle(_hex(UNIQ_B))], listar=listar, ler=ler
    )

    assert list(ocupacoes) == [ADAPTADOR_1]
    barra = ocupacoes[ADAPTADOR_1]
    assert barra.controles == 2
    assert barra.slots_input == pytest.approx(2 * HZ_INPUT_SEM_MIC)
    assert barra.slots_audio == 0.0
    assert barra.slots_teto == SLOTS_POR_SEGUNDO


def test_adaptadores_diferentes_sao_barras_diferentes() -> None:
    """Dois dongles são dois rádios: somar os dois esconderia a folga de um."""
    listar, ler = _bancada(
        {
            "hidraw3": {"HID_UNIQ": UNIQ_A, "HID_PHYS": ADAPTADOR_1},
            "hidraw4": {"HID_UNIQ": UNIQ_B, "HID_PHYS": ADAPTADOR_2},
        }
    )

    ocupacoes = ocupacao_por_adaptador(
        [_controle(_hex(UNIQ_A)), _controle(_hex(UNIQ_B))], listar=listar, ler=ler
    )

    assert sorted(ocupacoes) == [ADAPTADOR_1, ADAPTADOR_2]
    assert all(barra.controles == 1 for barra in ocupacoes.values())


def test_controle_bt_sem_endereco_nao_pega_o_adaptador_do_vizinho() -> None:
    """Um vai para a barra do endereço; o outro, para a barra de "não sei"."""
    listar, ler = _bancada(
        {
            "hidraw3": {"HID_UNIQ": UNIQ_A, "HID_PHYS": ADAPTADOR_1},
            "hidraw4": {"HID_UNIQ": UNIQ_B},
        }
    )

    ocupacoes = ocupacao_por_adaptador(
        [_controle(_hex(UNIQ_A)), _controle(_hex(UNIQ_B))], listar=listar, ler=ler
    )

    assert sorted(ocupacoes) == [SEM_ADAPTADOR, ADAPTADOR_1]
    assert ocupacoes[ADAPTADOR_1].controles == 1
    assert ocupacoes[SEM_ADAPTADOR].controles == 1


def test_uniq_nulo_cai_na_barra_de_nao_sei_sem_levantar() -> None:
    """`controllers[].uniq` pode ser `None` (`backend_pydualsense.py:4664`)."""
    listar, ler = _bancada({})

    ocupacoes = ocupacao_por_adaptador([_controle(None)], listar=listar, ler=ler)

    assert list(ocupacoes) == [SEM_ADAPTADOR]


def test_o_microfone_troca_entrada_por_audio_e_a_soma_quase_nao_se_move() -> None:
    """O comportamento MEDIDO no A/B de 25/07: o áudio divide a mesma fila.

    É o aceite da sprint escrito como invariante: com a ponte de pé a fatia de
    áudio aparece, a de entrada ENCOLHE, e o total sobe menos de 7 % —
    276,7/260,4. Um medidor que somasse o áudio por cima do input inteiro
    diria que ligar o microfone custa 41 % a mais de rádio, e mandaria a pessoa
    desligar o microfone por um custo que não existe.
    """
    listar, ler = _bancada(
        {"hidraw3": {"HID_UNIQ": UNIQ_A, "HID_PHYS": ADAPTADOR_1}}
    )
    argumentos = {"listar": listar, "ler": ler}

    sem_mic = ocupacao_por_adaptador([_controle(_hex(UNIQ_A))], **argumentos)[
        ADAPTADOR_1
    ]
    com_mic = ocupacao_por_adaptador(
        [_controle(_hex(UNIQ_A))], com_ponte_de_mic={UNIQ_A}, **argumentos
    )[ADAPTADOR_1]

    assert sem_mic.slots_audio == 0.0
    assert com_mic.slots_audio == pytest.approx(HZ_AUDIO_COM_MIC)
    assert com_mic.slots_input == pytest.approx(HZ_INPUT_COM_MIC)
    assert com_mic.slots_input < sem_mic.slots_input
    assert com_mic.com_microfone == 1

    crescimento = com_mic.slots_total / sem_mic.slots_total
    assert crescimento < 1.07, (
        "o total com microfone cresceu mais que os 6,3% medidos no A/B — "
        "alguém somou o áudio por cima do input inteiro"
    )


def test_o_conjunto_de_pontes_casa_mesmo_escrito_com_dois_pontos() -> None:
    """A ponte de mic guarda o `HID_UNIQ` CRU, com dois-pontos.

    `dualsense_bt_audio.py:387` lê o valor direto do uevent; o estado do daemon
    dá 12 hex. Sem normalizar os dois, o conjunto nunca casa e a fatia de áudio
    nunca aparece — falha silenciosa, que é a pior classe.
    """
    listar, ler = _bancada(
        {"hidraw3": {"HID_UNIQ": UNIQ_A, "HID_PHYS": ADAPTADOR_1}}
    )

    por_mac = ocupacao_por_adaptador(
        [_controle(_hex(UNIQ_A))],
        com_ponte_de_mic={UNIQ_A},
        listar=listar,
        ler=ler,
    )[ADAPTADOR_1]
    por_hex = ocupacao_por_adaptador(
        [_controle(_hex(UNIQ_A))],
        com_ponte_de_mic={_hex(UNIQ_A)},
        listar=listar,
        ler=ler,
    )[ADAPTADOR_1]

    assert por_mac == por_hex
    assert por_mac.slots_audio > 0


def test_a_fracao_crua_passa_de_um_e_quem_satura_e_a_barra() -> None:
    """Estourar o teto é o que a barra existe para saber dizer.

    Saturar a CONTA esconderia o caso: o selo diria `1600/1600` para uma mesa
    de sete controles que pede 1822. Quem satura é o desenho.
    """
    listar, ler = _bancada(
        {
            f"hidraw{i}": {"HID_UNIQ": f"aa:bb:cc:00:00:{i:02x}", "HID_PHYS": ADAPTADOR_1}
            for i in range(7)
        }
    )

    barra = ocupacao_por_adaptador(
        [_controle(f"aabbcc0000{i:02x}") for i in range(7)], listar=listar, ler=ler
    )[ADAPTADOR_1]

    assert barra.slots_total == pytest.approx(7 * HZ_INPUT_SEM_MIC)
    assert barra.fracao_total > 1.0
    assert barra.rotulo == PALAVRA_CHEIA
    assert fatias_da_barra(barra.fracao_input, barra.fracao_audio) == (1.0, 0.0)


def test_a_fatia_de_audio_comeca_onde_a_de_entrada_termina() -> None:
    """Uma trilha, duas fatias: as duas somadas nunca passam de 1,0."""
    assert fatias_da_barra(0.3, 0.2) == pytest.approx((0.3, 0.2))
    assert fatias_da_barra(0.9, 0.4) == pytest.approx((0.9, 0.1))
    assert fatias_da_barra(-1.0, -1.0) == (0.0, 0.0)


# -- as palavras, e a fronteira ----------------------------------------------


def test_as_tres_palavras_e_os_dois_cortes() -> None:
    """Folgada até 60 %, Apertada até 85 %, Cheia acima. Decisão R3."""
    assert palavra_da_ocupacao(0.0) == PALAVRA_FOLGADA
    assert palavra_da_ocupacao(CORTE_FOLGADA) == PALAVRA_FOLGADA
    assert palavra_da_ocupacao(CORTE_FOLGADA + 0.001) == PALAVRA_APERTADA
    assert palavra_da_ocupacao(CORTE_APERTADA) == PALAVRA_APERTADA
    assert palavra_da_ocupacao(CORTE_APERTADA + 0.001) == PALAVRA_CHEIA
    assert palavra_da_ocupacao(3.0) == PALAVRA_CHEIA


def test_nenhuma_palavra_do_medidor_carrega_culpa() -> None:
    """A fronteira que a tela não atravessa, como portão.

    Dois controles no MESMO adaptador diferiram por quase o dobro com a mesa
    FOLGADA (381,54 contra 191,40 Hz), a desigualdade sobreviveu à troca de
    braços e o motivo é ABERTO. O medidor pode dizer que a mesa está cheia; não
    pode dizer que por isso o controle está ruim.

    Mordida: acrescentar qualquer frase de causa às três palavras, ao rótulo ou
    ao selo.
    """
    textos = [
        PALAVRA_FOLGADA,
        PALAVRA_APERTADA,
        PALAVRA_CHEIA,
        _rotulo_do_medidor(ADAPTADOR_1),
        _rotulo_do_medidor(SEM_ADAPTADOR),
        _selo_da_ocupacao(Ocupacao(slots_input=7 * HZ_INPUT_SEM_MIC)),
        _texto_acessivel(Ocupacao(slots_input=7 * HZ_INPUT_SEM_MIC)),
    ]

    achados = [
        f"{texto!r} contém {culpa!r}"
        for texto in textos
        for culpa in PALAVRAS_DE_CULPA
        if culpa in texto.lower()
    ]

    assert not achados, (
        "o medidor fala de OCUPAÇÃO, nunca de culpa:\n  " + "\n  ".join(achados)
    )


def test_o_selo_diz_de_onde_veio_o_numero() -> None:
    """O selo é procedência, não enfeite: as 1.600 fatias são especificação."""
    barra = Ocupacao(slots_input=2 * HZ_INPUT_SEM_MIC, slots_audio=HZ_AUDIO_COM_MIC)

    assert _selo_da_ocupacao(barra) == "627/1600 · derivado da especificação"
    assert _texto_acessivel(barra) == "627 de 1600"


def test_o_rotulo_e_o_endereco_e_nunca_o_hci() -> None:
    """`hci0` inverte entre boots; endereço, não (decisão M1)."""
    assert _rotulo_do_medidor(ADAPTADOR_1) == f"Rádio em uso · {ADAPTADOR_1}"
    assert _rotulo_do_medidor(SEM_ADAPTADOR) == "Rádio em uso · Não sei"
    assert "hci" not in _rotulo_do_medidor(ADAPTADOR_1)


# -- quais barras aparecem ----------------------------------------------------


def test_sem_controle_no_radio_cada_adaptador_ganha_uma_barra_em_zero() -> None:
    """O estado desta bancada: adaptadores de pé, todos os controles no cabo.

    Barra em zero é resultado válido, e é o que a foto da aba mostra. O nome
    vem da identidade física, porque sem controle nenhum no ar não há
    `HID_PHYS` de onde tirar endereço.
    """
    mesa = Mesa(
        adaptadores=(
            Adaptador(interface="hci0", no="1-1", vid="0a12", pid="0001"),
            Adaptador(interface="hci1", no="1-2", vid="8087", pid="0033"),
        )
    )

    barras = _medidores_da_mesa(mesa, {})

    assert [nome for nome, _ in barras] == ["0a12:0001", "8087:0033"]
    assert all(barra.slots_total == 0.0 for _nome, barra in barras)
    assert all(barra.rotulo == PALAVRA_FOLGADA for _nome, barra in barras)


def test_com_controle_no_radio_a_barra_e_por_endereco() -> None:
    """Quem sabe o endereço é o `HID_PHYS`, e é ele que nomeia a barra."""
    mesa = Mesa(adaptadores=(Adaptador(interface="hci0", no="1-1"),))
    ocupacoes = {ADAPTADOR_2: Ocupacao(slots_input=HZ_INPUT_SEM_MIC, controles=1)}

    barras = _medidores_da_mesa(mesa, ocupacoes)

    assert [nome for nome, _ in barras] == [ADAPTADOR_2]


def test_sem_adaptador_e_sem_controle_nao_ha_barra_nenhuma() -> None:
    """A linha "Nenhum adaptador Bluetooth encontrado" já disse tudo.

    Uma barra vazia embaixo dela ocuparia altura para repetir a mesma resposta.
    É o estado real desta máquina em 22/08/2026.
    """
    assert _medidores_da_mesa(Mesa(), {}) == []
