"""QUEM-E-QUEM-04 — a chave do perfil atravessa o transporte, e a parede tem nome.

O REQUISITO DELA, e ele é de produto: o mesmo controle, no cabo e no rádio, tem
de cair na MESMA memória do perfil. Se o transporte entrar na chave, trocar o
cabo pelo rádio faz o produto esquecer o ajuste que ela acabou de fazer — e o
esquecimento é silencioso, que é o pior desfecho possível para uma memória.

O QUE ESTA RÉGUA MEDE, e as duas pontas são CÓDIGO REAL
-------------------------------------------------------
* **o lado do perfil** — ``Profile._validate_controllers_keys``
  (``profiles/schema.py``), que canoniza a grafia escrita no JSON;
* **o lado da consulta** — ``PyDualSenseController.describe_controllers``, que
  publica ``uniq`` e ``transport`` como campos SEPARADOS, e
  ``daemon.ipc_handlers._norm_uniq``, com que o daemon procura no mapa.

Nenhuma das duas é reproduzida aqui: o teste monta handles dublados e chama o
``describe_controllers`` de verdade. Elas se encontram porque as DUAS pontas
chamam o mesmo ``core.sysfs_leds.norm_mac`` — não é coincidência de medição, é
o mecanismo, e é o mecanismo que se congela. *"4 de 4 numa mesa de quatro
placas não prova universalidade; o que prova é o mecanismo"*
(``docs/data/mapa-controles.csv``, ``identidade.cracha_nos_dois_transportes``).

O QUE CAIU DO ENUNCIADO, e o motivo é bom
-----------------------------------------
A §3 item 1 mandava o esquema aprender uma SEGUNDA FORMA de chave — a do
controle sem serial, "com prefixo explícito". **Ela não existe.** A
``O-CONTROLE-SEM-MAC-01`` fechou antes (``cd5ff9bc``) e mediu que dos cinco
crachás candidatos sobra o ``0x09``, que devolve **o endereço de rádio** — é de
onde o próprio ``hid_playstation`` tira o ``HID_UNIQ``. O crachá não é uma
segunda gramática; é *outra estrada para o mesmo valor*, e
``identity.resolver_crachas`` só o aceita depois de passar pelas MESMAS guardas
do serial (12 hex canônicos, não-vpad). **A porta do perfil já estava aberta**,
e a prova 4 abaixo a atravessa de ponta a ponta em vez de alargá-la.

O que NÃO caiu: as três rejeições medidas da F4 continuam de pé, e agora com
régua nomeada (prova 5) — antes elas só eram exercidas de longe, em
``test_profile_schema.py``.

NADA AQUI TOCA APARELHO, DISCO NEM ``~/.config``. Os dois controles são
sintéticos, na máscara da casa (octetos 4 e 5 zerados): ``aabbcc000002`` e
``3c9d07000007``. **O segundo não é o que a sprint escreveu**: ela pedia um
endereço de OUI ``dd:e1:1f``, que os portões ``test-data`` e ``mac-de-fixture``
recusam — não é faixa forjada desta casa. ``3c9d07`` é, e foi escolhida por
ser a SEGUNDA faixa sintética, conferida contra o registro IEEE em 22/08
(``test_uma_faixa_nao_e_um_fabricante.py``): assim os dois controles da prova
têm OUIs DIFERENTES, que é o que a mesa de dois quer dizer. O segundo existe
para que a mesa da prova nunca tenha o tamanho da mesa dela — e toda prova
roda também com **um** controle, que é a mesa mais comum do mundo e a que esta
casa nunca tem.

AS QUATRO MORDIDAS, e as quatro foram rodadas NO FONTE e desfeitas em 06/09/2026
--------------------------------------------------------------------------------
1. **arrancar ``norm_mac`` de ``_validate_controllers_keys``** (``schema.py``,
   ``mac = key``) → **26 de 40 caem**, e caem DISCRIMINANDO: os quatro
   sobreviventes de ``test_duas_grafias_dois_transportes_a_mesma_entrada`` são
   exatamente os de JSON escrito na grafia do RÁDIO, e todo caso de JSON na
   grafia do CABO deixa de achar. Uma régua que só exercitasse o rádio
   passaria com a cura fora — mediria a string, não a identidade;
2. **colar o transporte no ``uniq``** de ``describe_controllers``
   (``f"{self._key_to_uniq(key)}:{transporte}"``) → **28 de 40 caem**: a
   memória do rádio deixa de encontrar a do cabo, que é em letra o defeito que
   o requisito dela existe para impedir;
3. **soltar a guarda do OUI degenerado e a de duplicata** (``schema.py``, os
   dois ``if`` a ``False``) → **7 caem**, e
   ``test_a_mordida_das_tres_rejeicoes`` mostra duas unidades dividindo a
   MESMA memória, com uma vencendo por ordem de inserção, calada;
4. **tirar a guarda de 12 dígitos de ``_key_to_uniq``** (``backend``) → **2
   caem**: ``/dev/hidraw3`` vira o pseudo-MAC ``deda3``, e o perfil ganharia
   uma entrada que não é de controle nenhum.
"""
from __future__ import annotations

from typing import Any

import pytest
from pydantic import ValidationError

from hefesto_dualsense4unix.core.backend_pydualsense import PyDualSenseController
from hefesto_dualsense4unix.core.evdev_reader import EvdevReader
from hefesto_dualsense4unix.core.sysfs_leds import norm_mac
from hefesto_dualsense4unix.daemon.ipc_handlers import _norm_uniq
from hefesto_dualsense4unix.daemon.subsystems.identity import ControllerIdentityRegistry
from hefesto_dualsense4unix.profiles.schema import Profile

# --- os dois controles da prova, sintéticos e na máscara da casa -------------
#: Controle 1, nas duas grafias que um JSON editado à mão pode ter. A key que o
#: backend enumera É o serial do hidapi, então a grafia com ``:`` é a que o
#: aparelho no CABO entrega e a colada é a que ela digitaria no JSON.
CABO_GRAFIA = "AA:BB:CC:00:00:02"
RADIO_GRAFIA = "aabbcc000002"
CHAVE_UM = "aabbcc000002"
#: Controle 2 — a mesa de DOIS. Sem ele a prova só falaria da mesa de um.
SEGUNDO_GRAFIA = "3C:9D:07:00:00:07"
CHAVE_DOIS = "3c9d07000007"

#: Os nomes de transporte que a pydualsense publica no handle. O terceiro caso
#: — o controle DESCONECTADO, cujo ``transport`` sai ``None`` — entra por
#: ``connected=False``, não por um nome.
TRANSPORTES = ("USB", "BT")


class _Handle:
    """O mínimo de um handle pydualsense que ``describe_controllers`` lê.

    Só ``connected`` e ``conType.name`` — a bateria fica ausente de propósito
    (``battery_pct``/``battery_state`` a ``None``), porque esta régua é sobre
    IDENTIDADE e um dublê que responde demais esconde o que ela mede.
    """

    def __init__(self, *, connected: bool = True, transport_name: str = "USB") -> None:
        self.connected = connected
        self.conType = type("CT", (), {"name": transport_name})()


def _null_evdev() -> EvdevReader:
    """EvdevReader sem device — ``is_available=False``, não abre nada."""
    reader = EvdevReader(device_path=None)
    reader._device_path = None
    return reader


#: Um controlador REAL, reaproveitado entre os casos. Construir um por caso
#: custava ~0,4 s (o `EvdevReader` varre `/dev/input` ao nascer) e a suíte desta
#: casa roda em oito lotes cronometrados; `describe_controllers` só LÊ
#: `_handles`/`_primary_key`, então reaproveitar não mistura estado nenhum.
_CONTROLADOR: PyDualSenseController | None = None


def _descrever(*pares: tuple[str, str | None]) -> list[dict[str, Any]]:
    """A saída REAL de ``describe_controllers`` para uma mesa montada aqui.

    Cada par é ``(key do handle, nome do transporte)``; ``None`` no transporte
    é o controle DESCONECTADO. A key é o serial do hidapi — é o único lugar de
    onde a identidade pode sair, e é o que o ``_key_to_uniq`` normaliza.
    """
    global _CONTROLADOR
    if _CONTROLADOR is None:
        _CONTROLADOR = PyDualSenseController(evdev_reader=_null_evdev())
    _CONTROLADOR._handles = {  # type: ignore[assignment]
        key: _Handle(connected=nome is not None, transport_name=nome or "USB")
        for key, nome in pares
    }
    _CONTROLADOR._primary_key = pares[0][0]
    return _CONTROLADOR.describe_controllers()


def _chave_da_entrada(entrada: dict[str, Any]) -> str | None:
    """A chave com que o daemon procura no mapa do perfil.

    É o caminho REAL: ``ipc_handlers._norm_uniq`` sobre o ``uniq`` que
    ``describe_controllers`` publicou. O ``transport`` da entrada NÃO é lido —
    e é justamente isso que a prova 3 congela.
    """
    return _norm_uniq(entrada.get("uniq"))


def _perfil(controllers: dict[str, Any]) -> Profile:
    """Um perfil mínimo com o mapa por controle — o resto é irrelevante aqui."""
    return Profile.model_validate(
        {"name": "jogo", "match": {"type": "any"}, "controllers": controllers}
    )


def _mapa(*chaves: str) -> dict[str, Any]:
    """O mapa ``controllers`` de um perfil, com uma entrada por chave."""
    return {chave: {"rumble": {"motor_forte_pct": 40}} for chave in chaves}


# --- PROVA 1 — duas grafias, dois transportes, a MESMA entrada ---------------


@pytest.mark.parametrize("mesa_de_dois", [False, True])
@pytest.mark.parametrize("grafia_no_json", [CABO_GRAFIA, RADIO_GRAFIA])
@pytest.mark.parametrize("grafia_do_handle", [CABO_GRAFIA, RADIO_GRAFIA])
@pytest.mark.parametrize("transporte", TRANSPORTES)
def test_duas_grafias_dois_transportes_a_mesma_entrada(
    mesa_de_dois: bool, grafia_no_json: str, grafia_do_handle: str, transporte: str
) -> None:
    """F1: o perfil acha a MESMA entrada, venha o controle pelo cabo ou pelo rádio.

    As DUAS grafias variam de propósito, e as duas variações são diferentes: a
    do JSON é o que ela (ou um editor de texto) escreveu no perfil; a do handle
    é o serial que o hidapi devolveu. Roda na mesa de UM e na de DOIS (prova
    6) — o segundo controle não pode fazer o primeiro deixar de ser achado,
    nem ser achado no lugar dele.
    """
    vizinho = (SEGUNDO_GRAFIA,) if mesa_de_dois else ()
    perfil = _perfil(_mapa(grafia_no_json, *vizinho))
    assert perfil.controllers is not None

    (entrada,) = _descrever((grafia_do_handle, transporte))
    chave = _chave_da_entrada(entrada)

    # o transporte SAI da descrição — separado, e nunca dentro da chave
    assert entrada["transport"] == transporte.lower()
    assert chave == CHAVE_UM
    assert chave in perfil.controllers
    assert perfil.controllers[chave].rumble is not None
    # e não é a entrada do vizinho
    assert chave != CHAVE_DOIS


def test_a_grafia_do_json_e_canonizada_no_perfil() -> None:
    """O mapa sai do validador com a chave canônica, seja qual for a grafia escrita."""
    for grafia in (CABO_GRAFIA, RADIO_GRAFIA, "AA-BB-CC-00-00-02", "aAbBcC000002"):
        perfil = _perfil(_mapa(grafia))
        assert perfil.controllers is not None
        assert list(perfil.controllers) == [CHAVE_UM], grafia


def test_a_mesa_de_dois_nao_embaralha_as_duas_memorias() -> None:
    """Cada controle acha a SUA entrada — e o co-op é a mesa em que isso importa."""
    perfil = _perfil(
        {
            CABO_GRAFIA: {"rumble": {"motor_forte_pct": 40}},
            SEGUNDO_GRAFIA: {"rumble": {"motor_forte_pct": 90}},
        }
    )
    assert perfil.controllers is not None

    descricao = _descrever((RADIO_GRAFIA, "BT"), (SEGUNDO_GRAFIA, "USB"))
    achadas = [_chave_da_entrada(e) for e in descricao]

    assert achadas == [CHAVE_UM, CHAVE_DOIS]
    assert perfil.controllers[CHAVE_UM].rumble.motor_forte_pct == 40  # type: ignore[union-attr]
    assert perfil.controllers[CHAVE_DOIS].rumble.motor_forte_pct == 90  # type: ignore[union-attr]


# --- PROVA 2 — a mordida da normalização, e ela DISCRIMINA -------------------


@pytest.mark.parametrize("mesa_de_dois", [False, True])
def test_a_mordida_da_normalizacao(mesa_de_dois: bool) -> None:
    """F2: com a cura, as duas grafias acham; sem a cura, só a do rádio.

    **É esta assimetria que faz a régua morder.** Se os dois casos
    continuassem passando com o ``norm_mac`` de ``_validate_controllers_keys``
    fora, ela estaria medindo a string — e uma régua que mede a string dá
    verde sobre a memória perdida.
    """
    vizinho = (SEGUNDO_GRAFIA,) if mesa_de_dois else ()
    (entrada,) = _descrever((RADIO_GRAFIA, "BT"))
    uniq = _chave_da_entrada(entrada)
    assert uniq == CHAVE_UM

    # --- com a cura: as duas grafias do JSON caem na mesma entrada
    for grafia in (CABO_GRAFIA, RADIO_GRAFIA):
        perfil = _perfil(_mapa(grafia, *vizinho))
        assert perfil.controllers is not None
        assert uniq in perfil.controllers, grafia

    # --- com a cura ARRANCADA (o mapa fica com a grafia CRUA do JSON, que é o
    #     que o validador sem `norm_mac` devolveria): o CABO deixa de achar, e
    #     o RÁDIO continua achando.
    assert uniq not in _mapa(CABO_GRAFIA, *vizinho)
    assert uniq in _mapa(RADIO_GRAFIA, *vizinho)


# --- PROVA 3 — o transporte NUNCA entra na chave -----------------------------


@pytest.mark.parametrize("mesa_de_dois", [False, True])
@pytest.mark.parametrize("grafia_do_handle", [CABO_GRAFIA, RADIO_GRAFIA])
def test_o_transporte_nunca_entra_na_chave(
    mesa_de_dois: bool, grafia_do_handle: str
) -> None:
    """A chave é BYTE A BYTE a mesma no cabo, no rádio e desconectado.

    MORDIDA: faça ``describe_controllers`` publicar
    ``f"{self._key_to_uniq(key)}:{transporte}"`` e este caso cai — a memória do
    rádio deixa de encontrar a do cabo.
    """
    # o JSON aqui já está canônico DE PROPÓSITO: o assunto deste caso é o
    # transporte, e misturar a grafia faria a mordida da prova 2 derrubá-lo
    # junto, escondendo qual das duas curas caiu.
    vizinho = (SEGUNDO_GRAFIA,) if mesa_de_dois else ()
    perfil = _perfil(_mapa(RADIO_GRAFIA, *vizinho))
    assert perfil.controllers is not None

    vistas = set()
    transportes_vistos = set()
    for transporte in (*TRANSPORTES, None):
        (entrada,) = _descrever((grafia_do_handle, transporte))
        vistas.add(_chave_da_entrada(entrada))
        transportes_vistos.add(entrada["transport"])

    # a chave não se move…
    assert vistas == {CHAVE_UM}
    # …e o transporte de fato VARIOU (senão o caso acima seria vacuoso)
    assert transportes_vistos == {"usb", "bt", None}
    assert CHAVE_UM in perfil.controllers


def test_o_uniq_e_o_transporte_sao_campos_separados() -> None:
    """F1, na forma: o transporte tem campo PRÓPRIO, e nada dele vaza no ``uniq``."""
    descricao = _descrever((CABO_GRAFIA, "USB"), (SEGUNDO_GRAFIA, "BT"))
    for entrada in descricao:
        uniq = entrada["uniq"]
        assert isinstance(uniq, str)
        assert set(uniq) <= set("0123456789abcdef")
        assert len(uniq) == 12
        assert str(entrada["transport"]) not in uniq


# --- PROVA 4 — o controle sem MAC, e a parede que a O-CONTROLE-SEM-MAC-01 moveu


@pytest.mark.parametrize("mesa_de_dois", [False, True])
def test_sem_mac_nao_produz_entrada_fantasma(mesa_de_dois: bool) -> None:
    """``uniq=None`` não vira chave, e o perfil não ganha entrada de ninguém.

    MORDIDA: tire a guarda de 12 dígitos de ``_key_to_uniq`` e ``/dev/hidraw3``
    vira o pseudo-MAC ``deda3`` — um identificador que não é de controle
    nenhum, e que na GUI apareceria como se fosse um.
    """
    vizinho = (SEGUNDO_GRAFIA,) if mesa_de_dois else ()
    perfil = _perfil(_mapa(RADIO_GRAFIA, *vizinho))
    assert perfil.controllers is not None
    antes = dict(perfil.controllers)

    (entrada,) = _descrever(("/dev/hidraw3", "USB"))
    assert entrada["uniq"] is None
    assert _chave_da_entrada(entrada) is None
    assert dict(perfil.controllers) == antes

    # o que a guarda impede, medido: sem ela a key crua vira pseudo-MAC…
    assert norm_mac("/dev/hidraw3") == "deda3"
    # …e o perfil o recusa nomeando, que é a metade que sobrevive da F3
    with pytest.raises(ValidationError, match="12 dígitos"):
        _perfil(_mapa("/dev/hidraw3"))


def test_a_forma_do_cracha_e_a_de_sempre_e_o_perfil_ja_a_aceita() -> None:
    """A §3 item 1 CAIU: o crachá é um ENDEREÇO, e o perfil não aprende gramática.

    Medido de ponta a ponta com o registro REAL da ``O-CONTROLE-SEM-MAC-01``:
    o provider devolve o que o feature ``0x09`` responderia, o registro o
    canoniza para 12 hex, e ``Profile`` aceita a mesma chave — sem uma linha
    nova no validador. É a porta que a sprint ia abrir, já aberta.
    """
    registro = ControllerIdentityRegistry()
    registro.set_cracha_provider(
        lambda uniq: CABO_GRAFIA if uniq == "/dev/hidraw7" else None
    )
    registro.resolver_crachas(["/dev/hidraw7"])

    key, persistivel = registro._chave("/dev/hidraw7")
    assert (key, persistivel) == (CHAVE_UM, True)

    perfil = _perfil(_mapa(key))
    assert perfil.controllers is not None
    assert list(perfil.controllers) == [CHAVE_UM]
    # e a mesma chave é a que a consulta produz para aquele controle
    (entrada,) = _descrever((CABO_GRAFIA, "BT"))
    assert _chave_da_entrada(entrada) == key


@pytest.mark.parametrize(
    "inventada",
    ["cracha:0x09:9f2a1c04", "sem-mac:0b:9f2a1c04", "9f2a1c04", "0x09"],
)
def test_gramatica_inventada_de_cracha_continua_recusada(inventada: str) -> None:
    """O portão NÃO afrouxou: só o endereço entra, e o resto sai com motivo.

    A chave de crachá com prefixo — que a §3 item 1 mandava aceitar — nunca
    chega a existir, e continuar a recusá-la é o que impede uma segunda
    gramática de nascer por acidente numa sprint futura.
    """
    with pytest.raises(ValidationError, match="12 dígitos"):
        _perfil(_mapa(inventada))


# --- PROVA 5 — as três rejeições medidas continuam de pé ---------------------


@pytest.mark.parametrize("mesa_de_dois", [False, True])
def test_a_rejeicao_do_oui_degenerado(mesa_de_dois: bool) -> None:
    """``000000000001`` foi medido AO VIVO no Pro Controller, idêntico entre unidades.

    Aceitá-lo faria dois controles DIFERENTES dividirem a mesma memória — é a
    F4, e é o defeito pior que esta sprint poderia causar se fosse feita com
    pressa para "abrir a porta" do controle sem serial.
    """
    vizinho = {CHAVE_DOIS: {}} if mesa_de_dois else {}
    with pytest.raises(ValidationError, match="degenerado"):
        _perfil({"000000000001": {}, **vizinho})
    with pytest.raises(ValidationError, match="degenerado"):
        _perfil({"00:00:00:00:00:01": {}, **vizinho})


@pytest.mark.parametrize("mesa_de_dois", [False, True])
def test_a_rejeicao_do_broadcast(mesa_de_dois: bool) -> None:
    """``ffffffffffff`` é broadcast — não é uma unidade de plástico."""
    vizinho = {CHAVE_DOIS: {}} if mesa_de_dois else {}
    with pytest.raises(ValidationError, match="degenerado"):
        _perfil({"ffffffffffff": {}, **vizinho})


@pytest.mark.parametrize("mesa_de_dois", [False, True])
def test_a_rejeicao_da_duplicata_apos_normalizacao(mesa_de_dois: bool) -> None:
    """Duas grafias do MESMO controle no mesmo mapa — uma venceria em silêncio."""
    vizinho = {SEGUNDO_GRAFIA: {}} if mesa_de_dois else {}
    with pytest.raises(ValidationError, match="duplicadas"):
        _perfil({RADIO_GRAFIA: {}, CABO_GRAFIA: {}, **vizinho})


def test_a_mordida_das_tres_rejeicoes() -> None:
    """Solte as guardas e duas unidades diferentes dividem a MESMA memória.

    A colisão é encenada sobre o mecanismo que o validador usa — ``norm_mac``
    mais o dicionário — porque é ali que o dano acontece: sem a guarda de
    duplicata a segunda grafia SOBRESCREVE a primeira por ordem de inserção, e
    nada é dito. Ao lado, o validador real recusando, para a comparação não
    ficar abstrata.
    """
    cru = {RADIO_GRAFIA: "o ajuste dela", CABO_GRAFIA: "o ajuste de outro dia"}

    sem_guarda = {norm_mac(k): v for k, v in cru.items()}
    assert len(sem_guarda) == 1
    assert sem_guarda[CHAVE_UM] == "o ajuste de outro dia"  # a colisão calada

    with pytest.raises(ValidationError, match="duplicadas"):
        _perfil({k: {} for k in cru})

    # e o degenerado: duas grafias do MESMO endereço inútil, que sem a guarda
    # do OUI fariam dois controles distintos caírem numa memória só
    assert norm_mac("00:00:00:00:00:01") == norm_mac("000000000001") == "000000000001"
    with pytest.raises(ValidationError, match="degenerado"):
        _perfil(_mapa("000000000001"))


# --- PROVA 6 — a mesa de UM tem prova própria, e não só parametrização -------


def test_a_mesa_de_um_atravessa_o_transporte_inteira() -> None:
    """O usuário de UM controle: cabo, rádio e as duas grafias, num só perfil.

    *"Funcione como acessibilidade pra qualquer usuário simples"* — a mesa de
    um é a mais comum do mundo e a que esta casa nunca tem, então ela ganha um
    caso que se lê inteiro, sem parametrização.
    """
    perfil = _perfil({CABO_GRAFIA: {"rumble": {"motor_forte_pct": 40}}})
    assert perfil.controllers is not None
    assert list(perfil.controllers) == [CHAVE_UM]

    achadas = [
        _chave_da_entrada(_descrever((grafia, transporte))[0])
        for grafia in (CABO_GRAFIA, RADIO_GRAFIA)
        for transporte in TRANSPORTES
    ]
    assert achadas == [CHAVE_UM] * 4
    assert all(chave in perfil.controllers for chave in achadas)
