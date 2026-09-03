"""A cor do plástico bate na porta do BROKER — e não no nó escondido.

A CURA ESTÁ APLICADA (29/08/2026): ``_perguntar_ao_hidraw`` entra por
``abrir_hidraw``. **A mordida se prova arrancando-a**: troque o corpo da função
pelo ``os.open(caminho, os.O_RDWR | os.O_NONBLOCK)`` de antes e as SEIS
reprovam, a mordida 1 com ``cor is None`` — que é o "Não sei" dos dois cards
que ela viu hoje.

O DEFEITO, MEDIDO NA MESA DELA EM 29/08/2026
--------------------------------------------
Palavra dela: *"fora que os controles lá em cima tão tudo Não sei ainda."*

Os dois cards da aba Controles dizem "Não sei" no lugar da cor, e não é o
aparelho que se cala. Medido, com o daemon rodando e sem parar nada::

    /dev/hidraw5  crw-------  root root   (DualSense, cabo)
    /dev/hidraw6  crw-------  root root   (DualSense, cabo)
    os.open direto ....... errno 13 (Permission denied), nos dois
    ler_pelo_cabo(uniq) .. None, nos dois
    broker (SCM_RIGHTS) .. fd O_RDWR servido, nos dois, nó `hidden`

Os nós estão 0600 root:root porque **o Hefesto os esconde do JOGO** — é o
BROKER-01 funcionando (``broker/hidraw_broker.py``, ``setfacl -b`` + ``chmod
0600``). Não é bug de udev, não é firmware, não é o rádio: é o nosso próprio
produto batendo na porta que o nosso próprio produto fechou.

A CASA JÁ TINHA A PORTA, E O ENSAIO JÁ ENTRA POR ELA
-----------------------------------------------------
``scripts/ensaios/cor_do_plastico.py:879`` chama ``abrir_no_hidraw``
(``scripts/ensaios/comum.py:401``), que é ``abrir_hidraw``
(``integrations/hidraw_broker_client.py:593``): broker primeiro, ``open()``
depois, e a porta usada sai DECLARADA no relatório.

``integrations/cor_do_plastico.py:474`` faz ``os.open(caminho, O_RDWR |
O_NONBLOCK)`` e nada mais. A ``A-PORTA-QUE-A-CASA-CONSTRUIU-01`` (15/08/2026)
fechou esse buraco em ``scripts/`` — e ``test_a_porta_que_a_casa_construiu_01``
varre só ``scripts/`` (``SCRIPTS = RAIZ / "scripts"``, linha 64). O porte da
leitura para dentro do produto, em 22/08, reabriu o buraco no lado que a régua
não olha.

AS TRÊS MORDIDAS DESTE ARQUIVO
-------------------------------
1. **a cor atravessa o nó escondido** — a principal: arrancado o caminho do
   broker, ``ler_pelo_cabo`` volta a ``None`` e o card volta a "Não sei";
2. **o ioctl sai NO fd que o broker serviu** — uma cura que peça o fd ao broker
   e depois reabra por caminho mediria de novo o EACCES, com a porta certa no
   relatório e o zero errado na tela;
3. **a trava não afrouxa** — ``conferir_pedido`` continua conferindo os dois
   bytes ANTES de qualquer porta se abrir; o par que RESETA o controle não
   chega nem a pedir fd;
A QUARTA MORDIDA NÃO ESTÁ AQUI, E O MOTIVO NÃO É PREGUIÇA
----------------------------------------------------------
A segunda metade do defeito é a MEMÓRIA: ninguém persiste o resultado, e o
``SET_FEATURE`` se repete a cada abertura de tela. Ela não entra nesta leva
porque **o campo tem outro dono**: a ``ONDA-CONEXOES-09`` (27/08) já decidiu o
arquivo e a porta — ``maquina.json``, seção ``controles``, por
``declarar_a_maquina`` — e escolheu o campo ``cor``. Há uma medição contra essa
escolha, e ela precisa ser resolvida por quem é dono daquela sprint, não por
esta:

    gravando no ``cor``, ela declara Cosmic Red -> clica "Não sei" (a entrada
    some do arquivo, como tem de sumir) -> a leitura seguinte grava Cosmic Red
    de volta. **O gesto dela é desfeito sem rastro.** A asserção "a cor lida
    não apaga a cor declarada" não pega isso, porque ``None`` não é declaração:
    é a ausência dela. Mesma classe do ``or "xbox"`` do ``external_mask.py``.

O CUSTO DE NÃO TER A MEMÓRIA, medido: o ``SET_FEATURE`` sai **uma vez por
controle por execução**, não por tique — ``mesa_viva`` e ``secao_controles``
guardam a resposta em memória (``self._cache[uniq]``). É o mesmo comando de
leitura pura que o ensaio manda nesta bancada desde 27/08, com prova de vida
antes e depois. Não é risco novo; é o comportamento que a permissão escondia.

O QUE ESTE ARQUIVO **NÃO** PROVA: que o broker devolve o fd certo. Isso tem
dono e testes próprios (``test_hidraw_broker_protocol.py``,
``test_hidraw_broker_client.py``, ``test_hidraw_broker_open_fd.py``). O que
estas mordidas provam é que **o produto pede por ali**.

AS COSTURAS QUE A CURA PRECISA ABRIR
-------------------------------------
Duas, e as duas já são padrão desta casa (``estado_do_grab`` tem as mesmas, em
``hidraw_broker_client.py:689``)::

    def _perguntar_ao_hidraw(
        caminho: str,
        pedido: bytes,
        *,
        abrir: Any = None,   # default: abrir_hidraw — a porta da casa
        ioctl: Any = None,   # default: fcntl.ioctl
    ) -> bytes | None:

``ler_pelo_cabo`` não muda: o ``perguntar=`` que ela já tem continua sendo o
ponto de injeção do transporte inteiro, e é por ele que estes testes entram.

E o módulo novo da memória (mordida 4) tem de importar ``config_dir``
**LAZY**, dentro da função, como ``identity._path`` faz e pela mesma razão: é
o que preserva o ponto de monkeypatch dos testes.
"""
from __future__ import annotations

import array
import errno
import os
from functools import partial
from pathlib import Path
from typing import Any

import pytest

from hefesto_dualsense4unix.integrations import cor_do_plastico as produto
from hefesto_dualsense4unix.integrations.cor_do_plastico import (
    PedidoRecusadoError,
    conferir_pedido,
    ler_pelo_cabo,
    montar_pedido,
)
from hefesto_dualsense4unix.integrations.hidraw_broker_client import (
    PORTA_BROKER,
    PORTA_DIRETA,
    NoAberto,
    PortaFechadaError,
    abrir_hidraw,
)

#: Serial FORJADO, com a forma real e o conteúdo de ninguém. Os caracteres 5 e
#: 6 são ``02`` = Cosmic Red. É o mesmo forjado que
#: ``test_docs_mac_anonimato.py:759`` já reconhece como ruído legítimo — nenhum
#: serial de aparelho desta bancada entra em arquivo versionado.
SERIAL_FORJADO = "ZZ9Y02Q0000000000"  # serial-de-mentira: prefixo forjado

#: O que o card mostra quando a leitura não responde (``mesa_viva.py:163``).
NAO_SEI = "Não sei"

#: O endereço do controle na bancada de mentira — máscara da casa (octetos 4 e
#: 5 zerados), e um OUI que não é de ninguém.
UNIQ = "aa:bb:cc:00:00:01"

#: O ``HID_ID`` de um DualSense no cabo: ``BARRAMENTO:VENDOR:PRODUCT``.
HID_ID_DUALSENSE_NO_CABO = "0003:0000054C:00000CE6"


# ---------------------------------------------------------------------------
# A bancada — um sysfs de mentira, um broker de mentira, um aparelho de mentira
# ---------------------------------------------------------------------------


def sysfs_de_mentira(no: str = "hidraw9") -> dict[str, Any]:
    """Os três argumentos que ``alvo_do_controle`` já aceita, prontos.

    A costura é do produto e não minha (regra F4): ``raiz``, ``listar`` e
    ``ler`` entram por argumento justamente para que a bancada não encoste em
    ``/sys``.
    """
    uevent = (
        f"HID_ID={HID_ID_DUALSENSE_NO_CABO}\n"
        "HID_NAME=Sony Interactive Entertainment DualSense Wireless Controller\n"
        "HID_PHYS=usb-0000:00:00.0-1/input3\n"
        f"HID_UNIQ={UNIQ}\n"
    )
    return {
        "raiz": "/sys/class/hidraw",
        "listar": lambda _raiz: [no],
        "ler": lambda _caminho: uevent,
    }


class BrokerDeMentira:
    """Serve um fd REAL, com o mesmo contrato do cliente de verdade.

    ``abrir_no`` devolve ``(fd | None, motivo)`` e ``motivo`` nunca é vazio —
    é o contrato de ``hidraw_broker_client.abrir_no``, e é o que
    ``abrir_hidraw`` consome. O fd é de um arquivo comum em ``tmp_path``:
    serve para provar QUAL descritor chegou ao ``ioctl``, sem aparelho nenhum
    por perto.
    """

    def __init__(self, arquivo: Path | None) -> None:
        self._arquivo = arquivo
        self.pedidos: list[str] = []
        self.servidos: list[int] = []
        self.fechado = False

    def abrir_no(self, node: str) -> tuple[int | None, str]:
        self.pedidos.append(node)
        if self._arquivo is None:
            return None, "o broker recusou: reject_not_physical_dualsense"
        fd = os.open(self._arquivo, os.O_RDWR)
        self.servidos.append(fd)
        return fd, "o broker serviu o fd (nó hidden) por /run/de/mentira.sock"

    def close(self) -> None:
        self.fechado = True


class AparelhoDeMentira:
    """O ``ioctl`` do DualSense, com a resposta boa e a trava do lado de lá.

    Ele RECUSA um descritor que não tenha vindo do broker — é assim que a
    mordida 2 pega uma cura que peça o fd pela porta certa e depois reabra o
    nó por caminho.
    """

    def __init__(self, *, fds_aceitos: Any, serial: str = SERIAL_FORJADO) -> None:
        self.fds_aceitos = fds_aceitos
        self.serial = serial
        self.escritas: list[bytes] = []
        self.fds_vistos: list[int] = []

    def __call__(self, fd: int, request: int, buffer: Any, mutate: bool) -> int:
        self.fds_vistos.append(fd)
        if fd not in self.fds_aceitos:
            # É o EACCES do nó escondido, na forma em que o kernel o entrega a
            # quem abriu por caminho: o open falha antes, e quando não falha
            # (fd de outra coisa) o ioctl é que recusa.
            raise OSError(errno.EACCES, "Permission denied")
        nr = request & 0xFF
        if nr == 0x06:  # HIDIOCSFEATURE
            pedido = bytes(buffer)
            # A trava, conferida também do lado do "aparelho": se algum dia
            # sair daqui um par que não seja o do serial, o teste morre aqui e
            # não na tela dela.
            conferir_pedido(pedido)
            self.escritas.append(pedido)
            return len(pedido)
        # HIDIOCGFEATURE: 0x81, eco do par, marca de resposta boa, 17 ASCII.
        resposta = bytes([0x81, 1, 19, 2]) + self.serial.encode("ascii")
        buffer[: len(resposta)] = array.array("B", resposta)
        return len(resposta)


def porta_do_broker(arquivo: Path) -> tuple[Any, BrokerDeMentira, AparelhoDeMentira]:
    """``(perguntar, broker, aparelho)`` — a mesa dela, com o nó ESCONDIDO.

    ``abrir_hidraw`` é o de VERDADE: quem é de mentira é o cliente que ele
    consulta (``cliente=``, o ponto de injeção que ele documenta). Assim a
    porta sob teste é a porta do produto, não uma cópia dela.
    """
    broker = BrokerDeMentira(arquivo)
    # O aparelho só aceita descritores que o broker serviu — e a lista ainda
    # está sendo preenchida quando o `ioctl` roda, daí o conjunto VIVO.
    aparelho = AparelhoDeMentira(fds_aceitos=_ConjuntoVivo(broker.servidos))
    abrir = partial(abrir_hidraw, cliente=broker)

    def perguntar(caminho: str, pedido: bytes) -> bytes | None:
        # Enquanto a cura não abre a costura `abrir=`, isto levanta TypeError
        # — e é a mordida 1 reprovando, que é o que se quer hoje.
        return produto._perguntar_ao_hidraw(
            caminho, pedido, abrir=abrir, ioctl=aparelho
        )

    return perguntar, broker, aparelho


class _ConjuntoVivo:
    """``x in conjunto`` sobre uma lista que ainda está sendo preenchida."""

    def __init__(self, fonte: list[int]) -> None:
        self._fonte = fonte

    def __contains__(self, valor: object) -> bool:
        return valor in self._fonte


# ===========================================================================
# MORDIDA 1 — a cor atravessa o nó escondido
# ===========================================================================


def test_mordida_1_com_o_no_escondido_a_cor_chega_pela_porta_do_broker(
    tmp_path: Path,
) -> None:
    """A mesa DELA: nó 0600 root:root, daemon rodando, broker de pé.

    ARRANQUE A CURA (``_perguntar_ao_hidraw`` volta a ``os.open`` direto) e
    este teste reprova com ``cor is None`` — que é o "Não sei" dos dois cards
    que ela viu hoje.
    """
    arquivo = tmp_path / "hidraw9"
    arquivo.write_bytes(b"")
    perguntar, broker, aparelho = porta_do_broker(arquivo)

    cor = ler_pelo_cabo(UNIQ, **sysfs_de_mentira(), perguntar=perguntar)

    assert cor is not None, (
        "a cor voltou None com o broker de pé — é o 'Não sei' do card dela. "
        "A porta é `abrir_hidraw` (integrations/hidraw_broker_client.py:593), "
        "a mesma que o ensaio usa (scripts/ensaios/comum.py:401)."
    )
    assert cor.codigo == "02"
    assert cor.nome == "Cosmic Red"
    assert broker.pedidos == ["/dev/hidraw9"], (
        "o produto tem de PEDIR o nó ao broker — ele pediu " + repr(broker.pedidos)
    )
    assert len(aparelho.escritas) == 1, "um SET_FEATURE, nem zero nem dois"


def test_mordida_1_sem_broker_a_porta_direta_continua_servindo(
    tmp_path: Path,
) -> None:
    """Máquina sem broker (CI, checkout, install antigo) não pode regredir.

    A cura troca a porta, não a capacidade: onde o nó é legível por caminho, a
    leitura continua acontecendo. Se a cura passar a EXIGIR o broker, este
    teste reprova.
    """
    arquivo = tmp_path / "hidraw9"
    arquivo.write_bytes(b"")
    broker = BrokerDeMentira(None)  # o broker recusa: não há broker nenhum
    fds_diretos: list[int] = []

    class AbridorDireto:
        def __contains__(self, valor: object) -> bool:
            return valor in fds_diretos

    aparelho = AparelhoDeMentira(fds_aceitos=AbridorDireto())
    abrir_real = os.open

    def abrir_espiao(caminho: str, flags: int, *resto: int) -> int:
        fd = abrir_real(caminho, flags, *resto)
        if str(caminho).endswith("hidraw9"):
            fds_diretos.append(fd)
        return fd

    def perguntar(caminho: str, pedido: bytes) -> bytes | None:
        # O caminho existe em tmp_path, então o `open()` de queda funciona.
        return produto._perguntar_ao_hidraw(
            str(arquivo),
            pedido,
            abrir=partial(abrir_hidraw, cliente=broker),
            ioctl=aparelho,
        )

    with pytest.MonkeyPatch.context() as mp:
        mp.setattr(os, "open", abrir_espiao)
        cor = ler_pelo_cabo(UNIQ, **sysfs_de_mentira(), perguntar=perguntar)

    assert cor is not None and cor.nome == "Cosmic Red", (
        "sem broker a leitura tem de cair para o open() direto — a queda é a "
        "que `abrir_hidraw` já implementa, e ela não pode ser trocada por uma "
        "exigência de broker."
    )


def test_mordida_1_as_duas_portas_fechadas_viram_nao_sei_e_nunca_levantam() -> None:
    """``ler_pelo_cabo`` nunca levanta — nem quando a porta fecha dos dois lados.

    ``abrir_hidraw`` levanta ``PortaFechadaError`` (é o contrato dele, e é bom:
    o INSTRUMENTO tem de morrer barulhento). O PRODUTO, não: aqui "Não sei" é
    resposta válida e a janela não pode cair por causa de um controle.
    """

    def abrir_que_fecha(no: str, **_: Any) -> NoAberto:
        raise PortaFechadaError(
            errno.EACCES,
            f"{no}: as duas portas falharam. "
            f"{PORTA_BROKER}: o broker não respondeu. "
            f"{PORTA_DIRETA}: Permission denied.",
        )

    def perguntar(caminho: str, pedido: bytes) -> bytes | None:
        return produto._perguntar_ao_hidraw(caminho, pedido, abrir=abrir_que_fecha)

    cor = ler_pelo_cabo(UNIQ, **sysfs_de_mentira(), perguntar=perguntar)
    assert cor is None, "porta fechada é 'Não sei', não exceção na cara dela"


# ===========================================================================
# MORDIDA 2 — o ioctl sai NO fd que o broker serviu
# ===========================================================================


def test_mordida_2_o_ioctl_usa_o_descritor_que_veio_do_broker(tmp_path: Path) -> None:
    """Pedir o fd pela porta certa e reabrir por caminho seria pior que hoje.

    Pior porque o relatório diria "broker (SCM_RIGHTS)" e a tela continuaria em
    "Não sei" — uma medição que declara a porta certa e mede pela errada é
    exatamente o alarme convincente e falso que esta casa persegue.
    """
    arquivo = tmp_path / "hidraw9"
    arquivo.write_bytes(b"")
    perguntar, broker, aparelho = porta_do_broker(arquivo)

    ler_pelo_cabo(UNIQ, **sysfs_de_mentira(), perguntar=perguntar)

    assert broker.servidos, "o broker não chegou a servir fd nenhum"
    assert aparelho.fds_vistos, "o ioctl não rodou"
    assert set(aparelho.fds_vistos) <= set(broker.servidos), (
        "o ioctl saiu num descritor que o broker não serviu: "
        f"vistos={aparelho.fds_vistos} servidos={broker.servidos}"
    )


def test_mordida_2_o_descritor_do_broker_e_fechado_ao_fim(tmp_path: Path) -> None:
    """Um fd de hidraw cedido pelo broker root, vazado, fica órfão até o processo morrer.

    A leitura roda por controle e por abertura de tela; vazar um por vez basta
    para estourar o teto de descritores numa sessão longa dela. Espiar
    ``os.close`` e não ``os.fstat``: número de fd é RECICLADO, e um fstat que
    responde pode estar respondendo por outro arquivo.
    """
    arquivo = tmp_path / "hidraw9"
    arquivo.write_bytes(b"")
    perguntar, broker, _aparelho = porta_do_broker(arquivo)
    fechados: list[int] = []
    close_real = os.close

    def close_espiao(fd: int) -> None:
        fechados.append(fd)
        close_real(fd)

    with pytest.MonkeyPatch.context() as mp:
        mp.setattr(os, "close", close_espiao)
        ler_pelo_cabo(UNIQ, **sysfs_de_mentira(), perguntar=perguntar)

    assert broker.servidos, "o broker não chegou a servir fd nenhum"
    assert set(broker.servidos) <= set(fechados), (
        "descritor servido pelo broker e NÃO fechado: "
        f"{set(broker.servidos) - set(fechados)}"
    )


# ===========================================================================
# MORDIDA 3 — a trava não afrouxa, e ela vem ANTES da porta
# ===========================================================================


def test_mordida_3_o_par_que_reseta_nao_chega_nem_a_pedir_fd(tmp_path: Path) -> None:
    """``[1, 1]`` RESETA o controle. Ele não abre porta, não pede fd, não sai.

    A cura mexe no que fica ENTRE ``conferir_pedido`` e o ``ioctl``. Esta
    mordida existe para que essa mexida não empurre a trava para depois da
    porta — o precipício continua ao lado da trilha, e ela tem quatro controles
    sem reposição.
    """
    arquivo = tmp_path / "hidraw9"
    arquivo.write_bytes(b"")
    broker = BrokerDeMentira(arquivo)
    aparelho = AparelhoDeMentira(fds_aceitos=_ConjuntoVivo(broker.servidos))

    pedido_que_destroi = bytearray(montar_pedido())
    pedido_que_destroi[1] = 1
    pedido_que_destroi[2] = 1  # (1, 1) — RESETA o controle

    with pytest.raises(PedidoRecusadoError):
        produto._perguntar_ao_hidraw(
            "/dev/hidraw9",
            bytes(pedido_que_destroi),
            abrir=partial(abrir_hidraw, cliente=broker),
            ioctl=aparelho,
        )

    assert broker.pedidos == [], (
        "a trava mordeu DEPOIS de abrir a porta — ela tem de morder antes: "
        f"o broker chegou a ser consultado {broker.pedidos}"
    )
    assert aparelho.escritas == [], "nenhum byte pode ter saído"


def test_mordida_3_a_recusa_da_trava_ainda_vira_nao_sei_na_tela() -> None:
    """Trava que mordeu é sucesso da trava e "Não sei" na tela — nunca crash."""

    def perguntar(_caminho: str, _pedido: bytes) -> bytes | None:
        raise PedidoRecusadoError("o par (1, 1) RESETA o controle")

    cor = ler_pelo_cabo(UNIQ, **sysfs_de_mentira(), perguntar=perguntar)
    assert cor is None

