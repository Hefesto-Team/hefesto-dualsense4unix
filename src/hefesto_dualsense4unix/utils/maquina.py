"""``maquina.json`` — o que a MESA é, declarado por quem a montou."""
from __future__ import annotations

import contextlib
import json
import os
import re
import tempfile
import threading
from collections.abc import Callable, Mapping, Sequence
from pathlib import Path
from typing import Any, Literal, NamedTuple

from pydantic import (
    BaseModel,
    ConfigDict,
    Field,
    SerializationInfo,
    SerializerFunctionWrapHandler,
    ValidationError,
    computed_field,
    field_validator,
    model_serializer,
    model_validator,
)

from hefesto_dualsense4unix.profiles.schema import (
    ControllerOverrides,
    LedsConfig,
    Profile,
    ProfileMouseConfig,
    ProfileSpeakerConfig,
    RumbleConfig,
)
from hefesto_dualsense4unix.utils.logging_config import get_logger
from hefesto_dualsense4unix.utils.lugar import (
    FORMA_DO_CAMINHO,
    FORMA_DO_NO,
    caminho_do_lado_20,
    no_do_caminho,
)
from hefesto_dualsense4unix.utils.lugar import caminho_do_no as caminho_do_no
from hefesto_dualsense4unix.utils.lugar import caminhos_do_lugar as caminhos_do_lugar
from hefesto_dualsense4unix.utils.lugar import lugar_de as lugar_de
from hefesto_dualsense4unix.utils.lugar import lugar_do_caminho as lugar_do_caminho
from hefesto_dualsense4unix.utils.lugar import lugar_do_no as lugar_do_no
from hefesto_dualsense4unix.utils.lugar import partes_do_lugar as partes_do_lugar
from hefesto_dualsense4unix.utils.rotulo_da_entrada import (
    FRASE_DO_NOME_COMPRIDO,
    MAXIMO_DO_NOME_DA_ENTRADA,
    nome_que_vale,
)

logger = get_logger(__name__)

_MAQUINA_FILE = "maquina.json"

_MAQUINA_INVALIDO_SUFIXO = ".invalido"

MAQUINA_SCHEMA_VERSION = 1

VERSION_FIELD = "version"

MAQUINA_FILE_LOCK = threading.Lock()

_CHAVE_DE_CONTROLE = re.compile(r"^[0-9a-f]{12}$")

_OCTETO_SINTETIZADO = "02"

#: próxima versão herdaria lixo.
_CHAVE_DE_RADIO = re.compile(r"^[0-9a-f]{4}:[0-9a-f]{4}$")

_CAMINHO_DE_BARRAMENTO = FORMA_DO_CAMINHO

_NUMERO_DE_ENTRADA = re.compile(r"^[0-9]{1,3}[a-z]?$")

_MAXIMO_DE_FACES = 8
_MAXIMO_DE_ENTRADAS = 64

_NO_DE_ENTRADA = FORMA_DO_NO

_MAXIMO_DE_NOS_POR_ENTRADA = 4

#: A chave de ``ordens_dispensadas`` é o slug da regra que produziu a ordem
_CHAVE_DE_ORDEM = re.compile(r"^[a-z][a-z0-9_]{0,63}$")

_DATA_ISO = re.compile(r"^[0-9]{4}-[0-9]{2}-[0-9]{2}$")

_MAXIMO_DO_ARRANJO = 256

_DOZE_HEX = re.compile(r"[0-9a-fA-F]{12}")


class RadioDeclarado(BaseModel):
    """Um aparelho vizinho que divide a faixa de 2,4 GHz com os controles."""

    model_config = ConfigDict(extra="forbid")

    tipo: (
        Literal["wifi", "teclado", "mouse", "webcam", "caixa_de_som", "outro"] | None
    ) = None
    apelido: str | None = None
    #: A faixa que o «Descobrir a faixa» MEDIU (``[ini, fim)`` nos 79 canais do Bluetooth) e o dia
    #: em que mediu. É medida, não declaração: ``voltar_ao_automatico`` não a apaga.
    banda: list[int] | None = None
    banda_em: str = ""

    @field_validator("banda")
    @classmethod
    def _banda_dentro_da_regua(cls, valor: list[int] | None) -> list[int] | None:
        if valor is None:
            return None
        if len(valor) != 2 or not 0 <= valor[0] < valor[1] <= 79:
            raise ValueError("banda é [ini, fim) dentro dos 79 canais")
        return valor

    @field_validator("banda_em")
    @classmethod
    def _banda_em_so_a_data(cls, valor: str) -> str:
        if valor and not _DATA_ISO.match(valor):
            raise ValueError(f"data {valor!r} não é AAAA-MM-DD")
        return valor


class OrdemDispensada(BaseModel):
    """Uma recomendação que ela mandou calar — e o arranjo em que ela calou."""

    model_config = ConfigDict(extra="forbid")

    quando: str = ""
    arranjo: str = ""

    @field_validator("quando")
    @classmethod
    def _so_a_data(cls, valor: str) -> str:
        """Só a data, em ISO. Hora não acrescenta nada e é um dado a mais dela."""
        if valor and not _DATA_ISO.match(valor):
            raise ValueError(f"data {valor!r} não é AAAA-MM-DD")
        return valor

    @field_validator("arranjo")
    @classmethod
    def _assinatura_sem_identidade(cls, valor: str) -> str:
        """Teto de tamanho, e nenhuma sequência com cara de endereço."""
        if len(valor) > _MAXIMO_DO_ARRANJO:
            raise ValueError("assinatura de arranjo longa demais")
        if _DOZE_HEX.search(valor):
            raise ValueError(
                "assinatura de arranjo com cara de serial ou endereço"
            )
        return valor


class MesaDeclarada(BaseModel):
    """Onde a antena está — o que nenhum barramento sabe.

    Corpo humano absorve 2,4 GHz, e nem a altura nem o obstáculo aparecem em
    lugar nenhum do sistema. As duas escolhas existem para que o exame da mesa
    possa explicar um alcance ruim em vez de apenas medi-lo.

    ``ordens_dispensadas`` mora aqui, e não no ``gui_preferences.json``, porque
    dispensar uma ordem é uma afirmação sobre a TOPOLOGIA desta casa — o mesmo
    assunto de ``radios`` e ``altura_da_antena``. O arquivo da janela é da
    JANELA, e dar dois donos possíveis ao mesmo fato é o defeito que a
    CONFIGURAÇÕES-FECHA-01 acabou de curar.
    """

    model_config = ConfigDict(extra="forbid")

    altura_da_antena: Literal["acima", "abaixo"] | None = None
    linha_de_visada: Literal["livre", "com_gente"] | None = None
    radios: dict[str, RadioDeclarado] = Field(default_factory=dict)
    ordens_dispensadas: dict[str, OrdemDispensada] = Field(default_factory=dict)

    @field_validator("ordens_dispensadas")
    @classmethod
    def _chave_de_ordem_e_o_slug_da_regra(
        cls, valor: dict[str, OrdemDispensada]
    ) -> dict[str, OrdemDispensada]:
        """A chave é o slug da regra, e ``extra="forbid"`` não protege chave."""
        for chave in valor:
            if not _CHAVE_DE_ORDEM.match(chave):
                raise ValueError(
                    f"chave de ordem {chave!r} não é o slug de uma regra "
                    "(minúsculas ASCII e sublinhado)"
                )
        return valor

    @field_validator("radios")
    @classmethod
    def _chave_de_radio_e_vid_pid(
        cls, valor: dict[str, RadioDeclarado]
    ) -> dict[str, RadioDeclarado]:
        for chave in valor:
            if not _CHAVE_DE_RADIO.match(chave):
                raise ValueError(
                    f"chave de rádio {chave!r} não é 'vid:pid' em hex minúsculo"
                )
        return valor


class FaceDeclarada(BaseModel):
    """Um conjunto de entradas que a pessoa enxerga JUNTO — "Frente", "Hub"."""

    model_config = ConfigDict(extra="forbid")

    nome: str = ""
    portas: list[str] = Field(default_factory=list)
    perto: bool = False
    alto: bool = False

    @field_validator("portas")
    @classmethod
    def _numeros_de_entrada(cls, valor: list[str]) -> list[str]:
        for numero in valor:
            if not _NUMERO_DE_ENTRADA.match(numero):
                raise ValueError(
                    f"número de entrada {numero!r} não é até três dígitos com "
                    "uma letra opcional"
                )
        return valor


class PortaDeclarada(BaseModel):
    """Uma entrada do gabinete, pelo número DELA — e tudo o que se sabe dela.

    UM REGISTRO SÓ (A-ENTRADA-TEM-UM-REGISTRO-SO-01, 28/09/2026). A entrada
    morava em dois: aqui (o ``caminho`` de barramento deste boot, os nós, o
    nome) e em ``lugares[L]`` (a amarra pelo lugar, com uma cópia do caminho
    como «testemunha»). Todo o resto (a testemunha, as três conferências da
    amarra, a migração preguiçosa do nome, a ordem da troca) existia para
    manter os dois de acordo, e em 26/09 uma troca feita fora do produto
    mexeu num e não no outro. Agora a entrada guarda o ``lugar``, e o
    ``lugares`` saiu do esquema (a migração é :func:`migrar_o_documento`).

    ``lugar`` É A IDENTIDADE, E O ``caminho`` NÃO SE GUARDA
    -------------------------------------------------------

    ``lugar`` é o controlador PCI mais a cadeia de portas (``utils/lugar``, a
    grafia do ``ID_PATH`` do udev): o lugar do metal, que não muda entre boots.
    O caminho de barramento (``3-1.1.4``) carrega o número do barramento, que
    é a ORDEM em que os controladores sobem, e muda com um kernel novo ou uma
    placa a mais. Ele se CALCULA na leitura (:func:`caminho_da_porta`, com os
    controladores deste boot). O :attr:`caminho` deste modelo é o que os nós
    dizem, para quem lê sem a leitura do barramento na mão, e nunca vai ao
    disco.

    Uma declaração que ainda fala em ``caminho`` (o rascunho do mapa da aba
    Conexões, a janela de calibração) continua valendo: o caminho vira o nó
    do buraco (:meth:`_o_caminho_vira_o_buraco`).

    ``filha_de`` é o número da entrada que hospeda a EXTENSÃO. Cabo de extensão
    passivo não tem descritor USB — o dongle na ponta enumera como se estivesse
    na entrada do hub, e nenhuma leitura de ``/sys``, hoje ou nunca, distingue
    os dois casos. Quem sabe é ela, porque ela disse; não há detecção e não há
    palpite.

    O nome é ``filha_de`` e não "mãe" por construção: "mãe" escrito sem acento
    dentro de string é exatamente o que o portão de acentuação reprova (ver o
    cabeçalho deste módulo).

    ``nos`` É O QUE ALCANÇA A ENTRADA **VAZIA**
    -------------------------------------------

    ``nos`` nomeia o BURACO (``usb1-port5``), e o nó do buraco responde
    ``state=not attached`` com o buraco vazio — MEDIDO em 25/08/2026: 38 nós de
    entrada nesta bancada, todos respondendo ``state`` e ``connect_type``, com e
    sem aparelho. Os nós carregam o número do barramento do boot em que foram
    lidos: com o ``lugar`` na mão, é ele que responde onde a entrada está.

    A lista tem DOIS elementos quando o buraco é 3.x e o kernel publicou o
    ``peer``: um buraco USB 3.0 tem um nó no hub-raiz 2.0 e outro no 3.x, e o
    DualSense (que é 2.0) sempre enumera no lado 2.0. Sem a lista, o produto
    acha que são dois buracos e manda a pessoa se ajoelhar atrás do gabinete
    duas vezes pelo mesmo furo.

    **Entrada vazia não tem entrada aqui.** ``_podar`` tira ``None`` e vazio do
    documento antes de escrever, e a ausência é a resposta "aqui não tem nada"
    — a mesma gramática de "não sei" do arquivo inteiro.
    """

    model_config = ConfigDict(extra="forbid")

    lugar: str | None = None
    filha_de: str | None = None
    nos: list[str] = Field(default_factory=list)
    liga: Literal["hub"] | None = None
    #: A CHAVE DA PORTA (O-APARELHO-SE-CORRIGE-ONDE-SE-CLICA-01, 04/10/2026): há um cabo de
    #: extensão entre este buraco e o aparelho. É da porta, separada do que está ligado nela
    #: (``liga``), e pesa no arranjo: o motor lê a entrada como esticada. Cabo passivo não tem
    #: descritor USB, e nenhuma leitura do ``/sys`` o vê — quem sabe é a pessoa.
    extensor: bool | None = None
    usb: Literal[2, 3] | None = None
    #: escreve na tela é ``utils/rotulo_da_entrada``. É o único lugar do nome
    nome: str | None = None

    @model_validator(mode="before")
    @classmethod
    def _o_extensor_de_antes_e_a_chave(cls, valor: Any) -> Any:
        """``liga: extensor`` (até 04/10/2026) é a chave ``extensor`` — a leitura aceita as duas."""
        if not isinstance(valor, Mapping) or valor.get("liga") != "extensor":
            return valor
        corpo = dict(valor)
        corpo["liga"] = None
        corpo["extensor"] = True
        return corpo

    @model_validator(mode="before")
    @classmethod
    def _o_caminho_vira_o_buraco(cls, valor: Any) -> Any:
        """``caminho`` é palavra de quem ESCREVE, e vira o nó do buraco."""
        if not isinstance(valor, Mapping) or "caminho" not in valor:
            return valor
        corpo = dict(valor)
        caminho = corpo.pop("caminho")
        nos = corpo.get("nos")
        nos = list(nos) if isinstance(nos, list) else []
        if caminho is None:
            corpo["nos"] = []
            return corpo
        if not isinstance(caminho, str) or not _CAMINHO_DE_BARRAMENTO.match(caminho):
            raise ValueError(
                f"caminho {caminho!r} não é o nome do kernel "
                "('3-1.1.4': barramento, traço, e a cadeia de portas)"
            )
        no = no_do_caminho(caminho)
        if no in nos or caminho == caminho_do_lado_20(nos):
            return corpo
        corpo["nos"] = [no]
        corpo["lugar"] = None
        return corpo

    @computed_field  # type: ignore[prop-decorator]
    @property
    def caminho(self) -> str | None:
        """O caminho do aparelho 2.0 neste buraco, PELOS NÓS — ``None`` sem nó.

        Não vai ao disco (quem grava tira os campos calculados). Quem tem a
        leitura do barramento na mão pergunta a :func:`caminho_da_porta` com os
        controladores deste boot, que é o que responde depois de um boot que
        trocou a ordem dos barramentos.
        """
        return caminho_da_porta(self) or None

    @field_validator("lugar")
    @classmethod
    def _lugar_e_o_do_metal(cls, valor: str | None) -> str | None:
        """O lugar de uma ENTRADA, com a cadeia de portas: ``pci-X`` sozinho é o"""
        if valor is None:
            return None
        partes = partes_do_lugar(valor)
        if partes is None or not partes[1]:
            raise ValueError(
                f"lugar {valor!r} não é o de uma entrada na grafia do ID_PATH do "
                "udev (o controlador PCI e as portas: utils/lugar.FORMA_DO_LUGAR)"
            )
        return valor

    @field_validator("filha_de")
    @classmethod
    def _filha_de_e_numero_de_entrada(cls, valor: str | None) -> str | None:
        if valor is not None and not _NUMERO_DE_ENTRADA.match(valor):
            raise ValueError(
                f"número de entrada {valor!r} não é até três dígitos com uma "
                "letra opcional"
            )
        return valor

    @field_validator("nome")
    @classmethod
    def _nome_aparado(cls, valor: str | None) -> str | None:
        """Espaço em volta sai; nome vazio é ``None``; até 24 caracteres."""
        if valor is None:
            return None
        limpo = valor.strip()
        if not limpo:
            return None
        if len(limpo) > MAXIMO_DO_NOME_DA_ENTRADA:
            raise ValueError(f"{FRASE_DO_NOME_COMPRIDO} ({len(limpo)} caracteres)")
        return limpo

    @field_validator("nos")
    @classmethod
    def _nos_sao_nomes_de_kernel(cls, valor: list[str]) -> list[str]:
        if len(valor) > _MAXIMO_DE_NOS_POR_ENTRADA:
            raise ValueError(
                f"{len(valor)} nós numa entrada só, e o teto é "
                f"{_MAXIMO_DE_NOS_POR_ENTRADA}"
            )
        for no in valor:
            if not _NO_DE_ENTRADA.match(no):
                raise ValueError(
                    f"nó de entrada {no!r} não é o nome do kernel "
                    "('usb1-port5' ou '3-1-port2': o hub, traço, 'port' e o "
                    "número)"
                )
        if len(set(valor)) != len(valor):
            raise ValueError(f"nó repetido na mesma entrada: {valor!r}")
        return valor


CALCULADOS_DA_ENTRADA: frozenset[str] = frozenset(PortaDeclarada.model_computed_fields)

_SEM_OS_CALCULADOS: dict[str, Any] = {
    "mapa": {"portas": {"__all__": set(CALCULADOS_DA_ENTRADA)}}
}


class MapaDaMesa(BaseModel):
    """O gabinete dela, desenhado por ela — o que ``/sys`` não tem como saber."""

    model_config = ConfigDict(extra="forbid")

    faces: list[FaceDeclarada] = Field(default_factory=list)
    portas: dict[str, PortaDeclarada] = Field(default_factory=dict)
    fora: list[str] = Field(default_factory=list)

    @field_validator("faces")
    @classmethod
    def _teto_de_faces(cls, valor: list[FaceDeclarada]) -> list[FaceDeclarada]:
        if len(valor) > _MAXIMO_DE_FACES:
            raise ValueError(
                f"{len(valor)} faces declaradas, e o teto é {_MAXIMO_DE_FACES}"
            )
        return valor

    @field_validator("portas")
    @classmethod
    def _chave_e_numero_de_entrada(
        cls, valor: dict[str, PortaDeclarada]
    ) -> dict[str, PortaDeclarada]:
        for chave in valor:
            if not _NUMERO_DE_ENTRADA.match(chave):
                raise ValueError(
                    f"número de entrada {chave!r} não é até três dígitos com "
                    "uma letra opcional"
                )
        return valor

    @field_validator("fora")
    @classmethod
    def _fora_sao_lugares_de_entrada(cls, valor: list[str]) -> list[str]:
        """Lugares de entrada, sem repetir, e com o teto das entradas."""
        vistos: list[str] = []
        for lugar in valor:
            partes = partes_do_lugar(lugar)
            if partes is None or not partes[1]:
                raise ValueError(
                    f"lugar {lugar!r} não é o de uma entrada na grafia do ID_PATH "
                    "do udev (utils/lugar.FORMA_DO_LUGAR)"
                )
            if lugar not in vistos:
                vistos.append(lugar)
        if len(vistos) > _MAXIMO_DE_ENTRADAS:
            raise ValueError(
                f"{len(vistos)} lugares fora de alcance, e o teto é {_MAXIMO_DE_ENTRADAS}"
            )
        return vistos

    @model_validator(mode="after")
    def _teto_de_entradas(self) -> MapaDaMesa:
        numeros = {numero for face in self.faces for numero in face.portas}
        numeros.update(self.portas)
        if len(numeros) > _MAXIMO_DE_ENTRADAS:
            raise ValueError(
                f"{len(numeros)} entradas declaradas, e o teto é "
                f"{_MAXIMO_DE_ENTRADAS}"
            )
        return self


_TETO_DA_ORDEM_DOS_ADAPTADORES = 63


class AdaptadorDeclarado(BaseModel):
    """Um adaptador Bluetooth pelo ENDEREÇO: o nome que ela deu a ele.

    ``D-2609-O-ADAPTADOR-TEM-NOME-PROPRIO`` (26/09/2026), pedido dela: *«temos
    o nome das entradas e o nome dos dispositivos. Eles estão se confundindo»*.
    Revoga a herança da D3: com o adaptador levando o nome da porta, as
    entradas que ela numerou no Mapear viraram adaptadores «15» e «13». O
    nome é do APARELHO e vai com ele de porta em porta; o da entrada fica em
    :class:`PortaDeclarada`. O ``Alias`` do BlueZ é a projeção deste campo, e
    quem a escreve é o ``bt_active_mode.sh`` — o escritor único do ``Alias``.

    É O ÚNICO NOME DO ADAPTADOR desde a A-ENTRADA-TEM-UM-REGISTRO-SO-01
    (28/09/2026): os nomes que o adaptador herdava da porta (a D3) ainda
    moravam em ``lugares`` («Centro», «Esquerda», «Direita», contra o «Meio»
    daqui), e saíram na migração (:func:`migrar_o_documento`).

    E A ORDEM DA CAIXA DELE também mora aqui desde então: a posição em que
    ela o arrastou na Conexões (25/09/2026, *«segurar a área do conector e
    arrastar ela pra mudar de ordem entre eles»*). Ela morava no
    ``gui_preferences.json``, pela chave do LUGAR (a D3): o terceiro registro
    do mesmo adaptador, e uma chave que mudava quando ele mudava de porta.
    <!-- noqa-acento: citação literal dela -->
    """

    model_config = ConfigDict(extra="forbid")

    nome: str | None = None
    ordem: int | None = Field(default=None, ge=0, le=_TETO_DA_ORDEM_DOS_ADAPTADORES)


class ControleDeclarado(BaseModel):
    """O que um controle não anuncia sobre si.

    ``modo`` é a chave física do 8BitDo e afins, escolhida ANTES de ligar e que o
    aparelho não informa. ``botoes`` é só o desenho que aparece na tela — nada é
    remapeado no controle. ``cor`` é texto livre porque a tela oferece os nomes
    de fábrica E um campo "Outra", para edição especial fora da lista. **Eram
    SEIS até 25/08/2026, e passaram a ser TODOS desde a LEX-5**, que trocou a fileira de
    botões por busca — ver ``app/actions/external_controllers.py``,
    ``cores_para_busca``. O número não volta a aparecer aqui de propósito: o
    dono da lista é ``integrations/cor_do_plastico.NOMES_DE_FABRICA``, que desde
    25/09/2026 LÊ o ``docs/data/cores-do-dualsense.csv`` — os sete nomes que ele
    devia ao mapa (``ONDA-CONEXOES-12``) chegaram com a
    O-CONTROLE-NUNCA-VISTO-TEM-NOME-E-COR-01.

    ``cor`` guarda a DECLARAÇÃO dela, e só ela. A cor LIDA do aparelho nunca
    chega aqui: em 29/08/2026 mediu-se que ela não é persistida em lugar nenhum
    — ``_chegou_a_cor`` a guarda em memória de sessão e a janela reaprende do
    zero a cada abertura.

    ``microfone`` é a ponte de mic por Bluetooth DAQUELE controle
    (``QUATRO-MICROFONES-01``, 22/08/2026, decisão dela: *"por controle"*). Mora
    aqui, e não no perfil, pela razão do cabeçalho de
    ``daemon/subsystems/bt_mic.py``: um microfone que liga ao trocar de jogo é
    exatamente a surpresa que aquele módulo recusa.

    **OS TRÊS VALORES MUDARAM DE SIGNIFICADO EM 18/09/2026**, por ordem dela:
    *"todos os controles tem que nascer com tudo mic, giroscopio e afins"*.

    ==========  =====================================================
    ``None``    ninguém disse nada → **o microfone LIGA**. É um
                DualSense; ter microfone é fato do aparelho.
    ``False``   ela desligou. É o ÚNICO registro de que disse não, e
                é o que impede o produto de religar no próximo boot.
    ``True``    ligado — como sempre foi, para quem já declarou.
    ==========  =====================================================

    **FATO SUBSTITUÍDO, e a razão dele continua de pé com outro nome.** Esta
    linha dizia *"Só ``True`` chega ao disco; desligar escreve ``None``, porque
    'nunca pedi' e 'não quero' deixam a ponte no chão do mesmo jeito — e um
    ``false`` gravado seria um valor de catálogo para o silêncio"*. Era verdade
    enquanto o default FOSSE o silêncio. Invertido o default, ``None`` deixou
    de ser um jeito de desligar: seria o botão que não desliga. O medo que a
    regra velha protegia — o default entrando disfarçado de escolha dela — hoje
    se protege pelo outro lado: é o ``false`` no disco que impede o produto de
    decidir sozinho por cima dela.
    """

    model_config = ConfigDict(extra="forbid")

    modo: Literal["xinput", "dinput", "switch"] | None = None
    botoes: Literal["xbox", "nintendo"] | None = None
    cor: str | None = None
    microfone: bool | None = None
    economia: bool | None = None
    microfone_mudo: bool | None = None
    #: <!-- noqa-acento: citação literal dela -->
    nome: str | None = None

    @field_validator("nome")
    @classmethod
    def _nome_aparado_e_do_tamanho_do_alias(cls, valor: str | None) -> str | None:
        """Espaço em volta sai; nome vazio é ``None`` — "ela não deu nome"."""
        if valor is None:
            return None
        limpo = valor.strip()
        if not limpo:
            return None
        if len(limpo.encode("utf-8")) > _MAXIMO_DO_NOME_DO_CONTROLE:
            raise ValueError(
                f"nome de {len(limpo.encode('utf-8'))} bytes não cabe no Alias do "
                f"Bluetooth (até {_MAXIMO_DO_NOME_DO_CONTROLE})"
            )
        return limpo


_MAXIMO_DO_NOME_DO_CONTROLE = 248


_CHAVE_DE_LANCADOR = re.compile(r"^[a-z0-9][a-z0-9_-]{0,31}$")

_MAXIMO_DE_LANCADORES = 32


class LancadorDeclarado(BaseModel):
    """Um lançador ou emulador que ELA acrescentou — ou onde um de fábrica está."""

    model_config = ConfigDict(extra="forbid")

    rotulo: str
    atalhos: tuple[str, ...] = ()
    comandos: tuple[str, ...] = ()

    @field_validator("rotulo")
    @classmethod
    def _o_rotulo_e_o_nome_do_cartao(cls, valor: str) -> str:
        limpo = valor.strip()
        if not limpo:
            raise ValueError(
                "um lançador declarado sem rótulo vira um cartão sem nome na "
                "tela, e nada nele diz de que lançador se trata"
            )
        if len(limpo) > 60:
            raise ValueError(
                f"rótulo de {len(limpo)} caracteres não cabe no topo do cartão, "
                "que divide a linha com o selo e a contagem"
            )
        return limpo

    @field_validator("atalhos", "comandos")
    @classmethod
    def _nada_de_agulha_vazia(cls, valor: tuple[str, ...]) -> tuple[str, ...]:
        limpas = tuple(dict.fromkeys(x.strip() for x in valor if x.strip()))
        if len(limpas) > 16:
            raise ValueError(
                f"{len(limpas)} agulhas para um lançador só — cada uma custa um "
                "`stat` por pasta a cada busca, e a lista existe para dizer onde "
                "ele está, não para varrer o disco"
            )
        return limpas

    @model_validator(mode="after")
    def _sem_agulha_nao_ha_o_que_procurar(self) -> LancadorDeclarado:
        """Um lançador sem ``atalhos`` **e** sem ``comandos`` é INACHÁVEL."""
        if not self.atalhos and not self.comandos:
            raise ValueError(
                f"o lançador {self.rotulo!r} não diz onde procurar: sem um "
                "`.desktop` em `atalhos` nem um comando em `comandos` a busca "
                "nunca o acha, e o cartão dele diz «não localizei» para sempre"
            )
        return self


class OrcamentoDeclarado(BaseModel):
    """O teto da mesa inteira — as abas seguem mandando, só não passam daqui.

    A chave é ``max``, nunca o rótulo ``"Máximo"``: o valor é o mesmo de
    ``profiles/schema.py:193``, e o rótulo de tela sai de ``_POLICY_LABEL``
    (``app/actions/rumble_actions.py:68-73``). Gravar o rótulo faria o
    ``extra="forbid"`` recusar o DOCUMENTO INTEIRO, e o sintoma na tela seria
    "não consegui gravar", não "valor inválido".
    """

    model_config = ConfigDict(extra="forbid")

    teto: Literal["economia", "balanceado", "max", "auto"] | None = None


class GestoDeclarado(BaseModel):
    """O que ela escolheu para UM gesto do controle (OS-GESTOS-DO-CONTROLE-01).

    ``faz`` é um token de ``core/acoes_do_gesto.ACOES``; ``script`` é o caminho
    do arquivo escolhido, e só existe com ``faz == "script"``. A forma é
    conferida aqui; a conferência do ARQUIVO (dono, permissão, ``#!``) é de
    ``acoes_do_gesto.conferir_o_script``, que a tela chama ao escolher e o
    daemon chama ao rodar — o disco muda entre as duas, e o esquema não lê
    disco.
    """

    model_config = ConfigDict(extra="forbid")

    faz: str
    script: str | None = None

    @model_validator(mode="before")
    @classmethod
    def _so_o_script_guarda_caminho(cls, valor: Any) -> Any:
        """Trocar o script por outro ato larga o caminho."""
        from hefesto_dualsense4unix.core.acoes_do_gesto import SCRIPT

        if isinstance(valor, Mapping) and valor.get("faz") != SCRIPT and "script" in valor:
            return {k: v for k, v in valor.items() if k != "script"}
        return valor

    @model_validator(mode="after")
    def _o_token_e_o_caminho_tem_forma(self) -> GestoDeclarado:
        from hefesto_dualsense4unix.core.acoes_do_gesto import (
            ACOES,
            MAXIMO_DO_CAMINHO,
            SCRIPT,
        )

        if self.faz not in ACOES:
            raise ValueError(f"o gesto não sabe fazer {self.faz!r}")
        if self.faz != SCRIPT:
            return self
        caminho = self.script or ""
        if (not caminho.startswith("/") or "\0" in caminho
                or len(caminho) > MAXIMO_DO_CAMINHO):
            raise ValueError(
                "o script precisa de um caminho absoluto, escolhido no seletor")
        return self


SECOES_DO_CONTROLE_NO_COMPUTADOR: tuple[str, ...] = (
    "leds", "speaker", "mic", "rumble", "sensores",
)


class MouseDoComputador(BaseModel):
    """As duas velocidades do mouse emulado. O liga e desliga é do jogo."""

    model_config = ConfigDict(extra="forbid")

    speed: int | None = None
    scroll_speed: int | None = None

    @model_validator(mode="after")
    def _a_faixa_e_a_do_perfil(self) -> MouseDoComputador:
        campos = {c: getattr(self, c) for c in ("speed", "scroll_speed")
                  if getattr(self, c) is not None}
        ProfileMouseConfig(enabled=False, **campos)
        return self


class ComputadorGlobal(BaseModel):
    """O «todo controle» do computador: o que vale em todo controle, e no novo."""

    model_config = ConfigDict(extra="forbid")

    leds: LedsConfig | None = None
    rumble: RumbleConfig | None = None
    speaker: ProfileSpeakerConfig | None = None
    mouse: MouseDoComputador | None = None
    button_actions: dict[str, str] | None = None
    key_bindings: dict[str, list[str]] | None = None
    teclado_emulado: bool | None = None

    @model_validator(mode="after")
    def _botoes_e_teclas_pelo_dono(self) -> ComputadorGlobal:
        """Os botões e as teclas passam pelas regras do perfil, que é o dono delas."""
        if self.button_actions is None and self.key_bindings is None:
            return self
        Profile.model_validate({
            "name": "computador",
            "match": {"type": "any"},
            "button_actions": self.button_actions,
            "key_bindings": self.key_bindings,
        })
        return self


class ComputadorDeclarado(BaseModel):
    """O padrão do computador: ``global`` e cada controle pela identidade."""

    model_config = ConfigDict(extra="forbid", populate_by_name=True)

    global_: ComputadorGlobal = Field(default_factory=ComputadorGlobal, alias="global")
    controles: dict[str, ControllerOverrides] = Field(default_factory=dict)
    migrado: bool | None = None

    @field_validator("controles", mode="before")
    @classmethod
    def _chave_e_a_identidade_e_none_esquece(cls, valor: Any) -> Any:
        if not isinstance(valor, Mapping):
            return valor
        vivos = {k: v for k, v in valor.items() if v is not None}
        if len(vivos) > _MAXIMO_DE_ENTRADAS:
            raise ValueError(
                f"{len(vivos)} controles no computador, e o teto é {_MAXIMO_DE_ENTRADAS}")
        for chave in vivos:
            if not isinstance(chave, str) or not _CHAVE_DE_CONTROLE.match(chave):
                raise ValueError(
                    f"chave de controle {chave!r} não é a identidade do controle "
                    "(doze hex minúsculos, sem separador)")
        return vivos

    @field_validator("controles")
    @classmethod
    def _so_o_que_e_do_computador(
        cls, valor: dict[str, ControllerOverrides]
    ) -> dict[str, ControllerOverrides]:
        for chave, entrada in valor.items():
            do_jogo = sorted(
                c for c in entrada.model_fields_set
                if c not in SECOES_DO_CONTROLE_NO_COMPUTADOR
                and getattr(entrada, c) is not None
            )
            if do_jogo:
                raise ValueError(
                    f"o controle {chave} traz {do_jogo}, que são do jogo e não do computador")
        return valor

    @model_serializer(mode="wrap")
    def _so_o_que_foi_declarado(
        self, handler: SerializerFunctionWrapHandler, info: SerializationInfo
    ) -> Any:
        modo = "json" if info.mode_is_json() else "python"
        saida: dict[str, Any] = {}
        do_global = self.global_.model_dump(mode=modo, exclude_unset=True)
        if do_global:
            saida["global"] = do_global
        controles = {
            chave: dados
            for chave, entrada in self.controles.items()
            if (dados := entrada.model_dump(mode=modo, exclude_unset=True))
        }
        if controles:
            saida["controles"] = controles
        if self.migrado is not None:
            saida["migrado"] = self.migrado
        return saida


class MaquinaConfig(BaseModel):
    """O documento inteiro. Nasce todo em "não sei", e é assim que ele é útil."""

    model_config = ConfigDict(extra="forbid")

    version: Literal[1] = 1
    mesa: MesaDeclarada = Field(default_factory=MesaDeclarada)
    controles: dict[str, ControleDeclarado] = Field(default_factory=dict)
    orcamento: OrcamentoDeclarado = Field(default_factory=OrcamentoDeclarado)
    mapa: MapaDaMesa = Field(default_factory=MapaDaMesa)
    lancadores: dict[str, LancadorDeclarado] = Field(default_factory=dict)
    adaptadores: dict[str, AdaptadorDeclarado] = Field(default_factory=dict)
    # seis gestos do controle faz, pela chave de ``core/acoes_do_gesto.GESTOS``.
    # ninguém declarou, e vale ``acoes_do_gesto.PADRAO``; ``{"gestos": {g:
    gestos: dict[str, GestoDeclarado] = Field(default_factory=dict)
    computador: ComputadorDeclarado = Field(default_factory=ComputadorDeclarado)

    @field_validator("controles")
    @classmethod
    def _chave_de_controle_e_mac_de_hardware(
        cls, valor: dict[str, ControleDeclarado]
    ) -> dict[str, ControleDeclarado]:
        for chave in valor:
            if not _CHAVE_DE_CONTROLE.match(chave):
                raise ValueError(
                    f"chave de controle {chave!r} não é MAC de hardware "
                    "(doze hex minúsculos, sem separador)"
                )
            if chave.startswith(_OCTETO_SINTETIZADO):
                raise ValueError(
                    f"chave de controle {chave!r} é endereço SINTETIZADO — "
                    "dois clones recebem o mesmo, e gravá-lo funde dois aparelhos"
                )
        return valor

    @field_validator("lancadores", mode="before")
    @classmethod
    def _o_none_e_o_esquecimento(cls, valor: Any) -> Any:
        """``{"lancadores": {"x": None}}`` **APAGA** o ``x``. É o único desfazer."""
        if not isinstance(valor, Mapping):
            return valor
        vivos = {k: v for k, v in valor.items() if v is not None}
        if len(vivos) > _MAXIMO_DE_LANCADORES:
            raise ValueError(
                f"{len(vivos)} lançadores declarados, e o teto é "
                f"{_MAXIMO_DE_LANCADORES}"
            )
        for chave in vivos:
            if not isinstance(chave, str) or not _CHAVE_DE_LANCADOR.match(chave):
                raise ValueError(
                    f"chave de lançador {chave!r} não serve como endereço de "
                    "tela — o cartão a usa em `data-lancador` e no prefixo de "
                    "cada `data-campo`, então ela é minúscula, sem espaço e sem "
                    "aspas (a-z, 0-9, `-` e `_`, até 32)"
                )
        return vivos

    @field_validator("adaptadores", mode="before")
    @classmethod
    def _chave_e_o_endereco_e_none_esquece(cls, valor: Any) -> Any:
        """A chave é o endereço em doze hex; ``{"adaptadores": {c: None}}`` esquece."""
        if not isinstance(valor, Mapping):
            return valor
        vivos = {k: v for k, v in valor.items() if v is not None}
        if len(vivos) > _MAXIMO_DE_ENTRADAS:
            raise ValueError(
                f"{len(vivos)} adaptadores declarados, e o teto é {_MAXIMO_DE_ENTRADAS}"
            )
        for chave in vivos:
            if not isinstance(chave, str) or not _CHAVE_DE_CONTROLE.match(chave):
                raise ValueError(
                    f"chave de adaptador {chave!r} não é endereço "
                    "(doze hex minúsculos, sem separador)"
                )
        return vivos

    @field_validator("gestos", mode="before")
    @classmethod
    def _gesto_conhecido_e_none_devolve_o_de_fabrica(cls, valor: Any) -> Any:
        """A chave é um dos seis gestos; ``{"gestos": {g: None}}`` esquece a escolha."""
        if not isinstance(valor, Mapping):
            return valor
        from hefesto_dualsense4unix.core.acoes_do_gesto import GESTOS

        vivos = {k: v for k, v in valor.items() if v is not None}
        for chave in vivos:
            if chave not in GESTOS:
                raise ValueError(f"{chave!r} não é um dos gestos do controle")
        return vivos


def entradas_do_mapa(mapa: MapaDaMesa) -> frozenset[str]:
    """Todo número de entrada do desenho — das faces e das entradas avulsas."""
    numeros = {numero for face in mapa.faces for numero in face.portas}
    numeros.update(mapa.portas)
    return frozenset(numeros)


def entrada_do_lugar(maquina: MaquinaConfig, lugar: str) -> str | None:
    """O número DELA para este lugar — ``None`` quando nenhuma entrada o guarda."""
    if not lugar:
        return None
    achadas = [numero for numero, porta in maquina.mapa.portas.items() if porta.lugar == lugar]
    return achadas[0] if len(achadas) == 1 else None


def lugar_da_entrada(maquina: MaquinaConfig, numero: str) -> str | None:
    """O lugar que a entrada ``numero`` guarda — o inverso de :func:`entrada_do_lugar`."""
    porta = maquina.mapa.portas.get(numero)
    if porta is None or not porta.lugar:
        return None
    return porta.lugar if entrada_do_lugar(maquina, porta.lugar) == numero else None


def caminho_da_porta(
    porta: PortaDeclarada, controladores: Mapping[int, str] | None = None
) -> str:
    """O caminho do aparelho 2.0 nesta entrada NESTE boot — ``""`` quando não se sabe."""
    if porta.lugar and controladores:
        do_lugar = caminhos_do_lugar(porta.lugar, controladores)
        if do_lugar:
            return do_lugar[0]
    return caminho_do_lado_20(porta.nos)


def caminhos_da_porta(
    porta: PortaDeclarada, controladores: Mapping[int, str] | None = None
) -> tuple[str, ...]:
    """Os caminhos em que um aparelho desta entrada pode estar agora."""
    principal = caminho_da_porta(porta, controladores)
    pelos_nos = [c for c in (caminho_do_no(no) for no in porta.nos) if c]
    if principal and principal != caminho_do_lado_20(porta.nos):
        return (principal,)
    return tuple(dict.fromkeys([c for c in (principal, *pelos_nos) if c]))


_ANTES_DA_MIGRACAO_SUFIXO = ".com-os-lugares"


def migrar_o_documento(bruto: Mapping[str, Any]) -> dict[str, Any]:
    """O documento com UM registro por entrada. Pura, inteira e idempotente.

    Leva o que morava em ``lugares`` para dentro do ``mapa``, e o ``caminho``
    de cada entrada para os ``nos``:

    1. A AMARRA QUE VALE: ``lugares[L].entrada = N`` vira
       ``mapa.portas[N].lugar = L`` quando o ``mapa`` concorda com ela — as
       conferências que a leitura sem controladores fazia a cada pergunta
       (``entrada_do_lugar`` até 28/09), feitas uma vez: a entrada está no
       desenho, nenhum outro lugar diz ser ela, e a entrada não tem caminho ou
       tem o da testemunha (``lugares[L].caminho``). Sem testemunha e com
       caminho, "não sei": a cadeia de portas sozinha confunde duas
       portas-raiz de mesmo número em controladores diferentes
       (ENTRADA-A-ENTRADA-02), e o Mapear reaprende o lugar.
    2. A AMARRA QUE ANDOU: a testemunha que o ``mapa`` pôs noutra entrada (o
       buraco andou sem a amarra, como na troca feita fora do produto em
       26/09) leva a amarra para ELA, que é o que o reparo à mão fez.
    3. O NOME de verdade da amarra que vale vai para ``portas[N].nome``, se a
       posição ainda não tem nome próprio (o nome é da posição,
       D-2609-O-NOME-E-DA-POSICAO) — a mesma relação que a reserva da leitura
       usava, então a tela não muda. O número usado como nome
       (``nome_que_vale`` = ``None``) não vai. Um nome de mais de 24
       caracteres BLOQUEIA a migração daquele lugar, que fica em ``lugares``
       como estava, e o log diz qual entrada: nada se trunca calado.
    4. O «NÃO ALCANÇO» (``fora``) vai para ``mapa.fora``.
    5. O NOME DE UM LUGAR SEM ENTRADA QUE VALHA sai, e o log diz quais: é o
       nome que o adaptador herdava da porta (a D3, revogada em 26/09; o dele
       mora em ``adaptadores``), ou o de uma amarra caducada, que a tela já não
       mostrava. A cópia de antes (``.com-os-lugares``) os guarda.
    6. O ``caminho`` de cada entrada vira o nó do buraco
       (``utils/lugar.no_do_caminho``) e sai: ele se calcula na leitura. O de
       forma torta fica, para o esquema o recusar com o resgate de sempre.

    Sem ``lugares`` e sem ``caminho``, devolve uma cópia igual.
    """
    documento: dict[str, Any] = _copia_funda(dict(bruto))
    lugares = documento.pop("lugares", None)
    mapa = documento.get("mapa")
    if isinstance(lugares, Mapping) and lugares:
        bloqueados = _levar_os_lugares(documento, lugares)
        if bloqueados:
            documento["lugares"] = bloqueados
        mapa = documento.get("mapa")
    if isinstance(mapa, dict) and isinstance(mapa.get("portas"), dict):
        for numero, porta in mapa["portas"].items():
            if isinstance(porta, dict) and "caminho" in porta:
                _o_caminho_vira_no(numero, porta)
        _o_extensor_vira_a_chave(mapa["portas"])
    return documento


def _o_extensor_vira_a_chave(portas: dict[str, Any]) -> None:
    """``liga: extensor`` vira ``extensor: true``, e a ponta antiga se funde na entrada.

    O extensor deixou de ser «o que tem na entrada» (04/10/2026): é uma chave da porta, e o
    aparelho que está nela continua dito nela. A entrada-filha que o desenho antigo criava
    para a ponta (``Na``, ``filha_de = N``) não tem mais o que guardar: o aparelho enumera no
    buraco da ``N``, então os nós, o lugar e a velocidade que só a ponta tinha passam para a
    ``N`` quando ela não os tem, e a ponta sai (o nome dela fica na cópia de antes). Idempotente.
    """
    for numero, porta in list(portas.items()):
        if not isinstance(porta, dict) or porta.get("liga") != "extensor":
            continue
        porta.pop("liga")
        porta["extensor"] = True
        ponta = portas.get(f"{numero}a")
        if not isinstance(ponta, dict) or ponta.get("filha_de") != numero:
            continue
        for campo in ("nos", "usb", "lugar"):
            if ponta.get(campo) and not porta.get(campo):
                porta[campo] = ponta[campo]
        del portas[f"{numero}a"]


def _levar_os_lugares(documento: dict[str, Any], lugares: Mapping[Any, Any]) -> dict[str, Any]:
    """Os passos 1 a 5 de :func:`migrar_o_documento`. Devolve os bloqueados."""
    mapa = documento.get("mapa")
    if not isinstance(mapa, dict):
        mapa = {}
    portas = mapa.get("portas")
    if not isinstance(portas, dict):
        portas = {}
    bruto_das_faces = mapa.get("faces")
    faces: list[Any] = bruto_das_faces if isinstance(bruto_das_faces, list) else []
    no_desenho = {n for n in portas if isinstance(n, str)} | {
        n
        for face in faces
        if isinstance(face, Mapping) and isinstance(face.get("portas"), list)
        for n in face["portas"]
        if isinstance(n, str)
    }

    def caminho_de(numero: str) -> str | None:
        porta = portas.get(numero)
        caminho = porta.get("caminho") if isinstance(porta, Mapping) else None
        return caminho if isinstance(caminho, str) and caminho else None

    def nome_proprio(numero: str) -> str | None:
        porta = portas.get(numero)
        nome = porta.get("nome") if isinstance(porta, Mapping) else None
        return nome_que_vale(numero, nome if isinstance(nome, str) else None)

    dos_lugares = {
        lugar: dele
        for lugar, dele in lugares.items()
        if isinstance(lugar, str) and isinstance(dele, Mapping)
    }
    pretendentes: dict[str, list[str]] = {}
    for lugar, dele in dos_lugares.items():
        entrada = dele.get("entrada")
        if isinstance(entrada, str) and entrada:
            pretendentes.setdefault(entrada, []).append(lugar)

    bloqueados: dict[str, Any] = {}
    fora = [x for x in mapa.get("fora") or [] if isinstance(x, str)] if isinstance(
        mapa.get("fora"), list) else []
    nomes: dict[str, str] = {}
    em_casa: dict[str, str] = {}
    andaram: list[tuple[str, str]] = []
    sem_entrada: list[str] = []
    for lugar, dele in dos_lugares.items():
        partes = partes_do_lugar(lugar)
        de_entrada = partes is not None and bool(partes[1])
        entrada = dele.get("entrada") if isinstance(dele.get("entrada"), str) else None
        nome = dele.get("nome") if isinstance(dele.get("nome"), str) else None
        if dele.get("fora") is True and de_entrada and lugar not in fora:
            fora.append(lugar)
        if not entrada or not de_entrada:
            if nome and nome.strip():
                sem_entrada.append(nome.strip())
            continue
        vale = nome_que_vale(entrada, nome)
        testemunha = dele.get("caminho") if isinstance(dele.get("caminho"), str) else None
        caminho = caminho_de(entrada)
        if not (
            entrada in no_desenho
            and len(pretendentes.get(entrada, ())) == 1
            and (caminho is None or caminho == testemunha)
        ):
            if vale is not None:
                sem_entrada.append(vale)
            if testemunha:
                andaram.append((lugar, testemunha))
            continue
        if vale is not None and nome_proprio(entrada) is None:
            if len(vale) > MAXIMO_DO_NOME_DA_ENTRADA:
                logger.warning(
                    "maquina_migracao_bloqueada_nome_comprido",
                    entrada=entrada,
                    caracteres=len(vale),
                    teto=MAXIMO_DO_NOME_DA_ENTRADA,
                )
                bloqueados[lugar] = _copia_funda(dict(dele))
                continue
            nomes[entrada] = vale
        em_casa[entrada] = lugar

    amarras: dict[str, list[str]] = {entrada: [lugar] for entrada, lugar in em_casa.items()}
    for lugar, testemunha in andaram:
        destinos = [n for n in sorted(portas) if caminho_de(n) == testemunha]
        if len(destinos) == 1 and destinos[0] not in em_casa:
            amarras.setdefault(destinos[0], []).append(lugar)

    mexeu = False
    for numero, dele_lugares in amarras.items():
        if len(dele_lugares) == 1 and isinstance(portas.setdefault(numero, {}), dict):
            portas[numero]["lugar"] = dele_lugares[0]
            mexeu = True
    for numero, vale in nomes.items():
        if isinstance(portas.setdefault(numero, {}), dict):
            portas[numero]["nome"] = vale
            mexeu = True
    if fora:
        mapa["fora"] = fora
        mexeu = True
    if mexeu:
        mapa["portas"] = portas
        documento["mapa"] = mapa
    if sem_entrada:
        logger.info(
            "maquina_migracao_tirou_o_nome_de_lugar_sem_entrada",
            quantos=len(sem_entrada),
            nomes=sorted(set(sem_entrada)),
        )
    return bloqueados


def _o_caminho_vira_no(numero: str, porta: dict[str, Any]) -> None:
    """O passo 6 de :func:`migrar_o_documento`, numa entrada."""
    caminho = porta.get("caminho")
    if caminho is None:
        porta.pop("caminho")
        return
    no = no_do_caminho(caminho) if isinstance(caminho, str) else ""
    if not no:
        return
    nos = porta.get("nos")
    nos = [x for x in nos if isinstance(x, str)] if isinstance(nos, list) else []
    if no not in nos:
        if len(nos) >= _MAXIMO_DE_NOS_POR_ENTRADA:
            logger.warning("maquina_migracao_caminho_sem_vaga_nos_nos", entrada=numero)
        else:
            porta["nos"] = [*nos, no]
    porta.pop("caminho")


def caminho_da_maquina() -> Path:
    """Path do ``maquina.json`` — import LAZY de ``config_dir``.

    Lazy porque resolver ``config_dir()`` no topo do módulo mata o monkeypatch da
    bateria: ``app/gui_prefs.py:13`` é a cicatriz exata dessa escolha, e é por ela
    que aquele módulo é inisolável em teste.
    """
    from hefesto_dualsense4unix.utils.xdg_paths import config_dir

    return config_dir(ensure=True) / _MAQUINA_FILE


def fundir_declaracao(
    base: Mapping[str, Any] | None, declaracao: Mapping[str, Any]
) -> dict[str, Any]:
    """``base`` com ``declaracao`` por cima, fundindo dicionário com dicionário."""
    fundido: dict[str, Any] = _copia_funda(base or {})
    for chave, valor in declaracao.items():
        anterior = fundido.get(chave)
        if isinstance(valor, Mapping) and isinstance(anterior, Mapping):
            fundido[chave] = fundir_declaracao(anterior, valor)
        else:
            fundido[chave] = _copia_funda(valor) if isinstance(valor, Mapping) else valor
    return fundido


def carregar_maquina() -> MaquinaConfig:
    """A declaração do disco. **Nunca levanta** — no pior caso, tudo em "não sei"."""
    try:
        bruto = _ler_documento()
        if bruto is None:
            return MaquinaConfig()
        if bruto.get(VERSION_FIELD) != MAQUINA_SCHEMA_VERSION:
            logger.debug("maquina_versao_desconhecida", versao=bruto.get(VERSION_FIELD))
            return MaquinaConfig()
        bruto = _migrar_no_disco(bruto)
        return MaquinaConfig.model_validate(_so_o_que_o_schema_conhece(bruto))
    except ValidationError as exc:
        logger.debug("maquina_documento_invalido_campo_a_campo", err=str(exc))
        if bruto is None:
            return MaquinaConfig()
        try:
            atual, descartados = _o_que_ainda_vale(bruto)
        except Exception as exc2:
            logger.debug("maquina_resgate_campo_a_campo_falhou", err=str(exc2))
            return MaquinaConfig()
        if descartados:
            logger.warning(
                "maquina_load_descartou_campos", descartados=list(descartados)
            )
        return atual
    except Exception as exc:
        logger.debug("maquina_load_falhou", err=str(exc))
    return MaquinaConfig()


class ResultadoDaGravacao(NamedTuple):
    """O que a gravação fez — ``gravou`` e o que ela teve de deixar para trás."""

    gravou: bool
    descartados: tuple[str, ...]


def gravar_maquina(declaracao: Mapping[str, Any]) -> bool:
    """:func:`gravar_maquina_com_descartes` sem a lista — ``True`` = gravou."""
    return gravar_maquina_com_descartes(declaracao).gravou


def gravar_o_computador(computador: Mapping[str, Any]) -> bool:
    """Troca o padrão do computador INTEIRO pelo ``computador`` dado."""
    return gravar_maquina_com_descartes(
        {"computador": dict(computador)}, substituir=("computador",)
    ).gravou


def gravar_rascunho_da_mesa(declaracao: Mapping[str, Any]) -> bool:
    """Grava a seção ``mesa`` como RASCUNHO — sem o gesto de "Aplicar" atrás."""
    return gravar_maquina({"mesa": dict(declaracao)})


def gravar_maquina_com_descartes(
    declaracao: Mapping[str, Any], *, substituir: Sequence[str] = ()
) -> ResultadoDaGravacao:
    """Funde a declaração PARCIAL no documento do disco."""
    MaquinaConfig.model_validate(dict(declaracao))
    with MAQUINA_FILE_LOCK:
        bruto = _ler_documento() or {}
        if bruto and bruto.get(VERSION_FIELD) != MAQUINA_SCHEMA_VERSION:
            logger.warning(
                "maquina_save_recusado_schema_desconhecido",
                versao_arquivo=bruto.get(VERSION_FIELD),
            )
            return ResultadoDaGravacao(False, ())
        if bruto:
            migrado = migrar_o_documento(bruto)
            if migrado != bruto:
                _guardar_a_copia_de_antes_da_migracao()
                bruto = migrado
        descartados: tuple[str, ...] = ()
        try:
            atual = MaquinaConfig.model_validate(_so_o_que_o_schema_conhece(bruto))
        except ValidationError as exc:
            _guardar_os_bytes_recusados()
            atual, descartados = _o_que_ainda_vale(bruto)
            logger.warning(
                "maquina_documento_em_disco_invalido",
                err=str(exc),
                descartados=list(descartados),
            )
        base = atual.model_dump(mode="json", exclude=_SEM_OS_CALCULADOS)
        for campo in substituir:
            base.pop(campo, None)
        fundido = MaquinaConfig.model_validate(fundir_declaracao(base, declaracao))
        documento = {
            campo: valor
            for campo, valor in bruto.items()
            if campo not in MaquinaConfig.model_fields
        }
        documento.update(
            _podar(fundido.model_dump(mode="json", exclude=_SEM_OS_CALCULADOS))
        )
        documento[VERSION_FIELD] = MAQUINA_SCHEMA_VERSION
        _escrever(documento)
        logger.debug("maquina_gravada", campos=sorted(declaracao))
    return ResultadoDaGravacao(True, descartados)


def chave_do_controle(endereco: object) -> str | None:
    """``aa:bb:…`` ou doze hex → a chave de ``controles`` (doze hex minúsculos)."""
    if not isinstance(endereco, str):
        return None
    chave = endereco.strip().lower().replace(":", "").replace("-", "")
    if not _CHAVE_DE_CONTROLE.match(chave) or chave.startswith(_OCTETO_SINTETIZADO):
        return None
    return chave


def chave_do_adaptador(endereco: object) -> str | None:
    """``AA:BB:…`` → a chave de ``adaptadores`` (doze hex minúsculos), ou ``None``."""
    if not isinstance(endereco, str):
        return None
    chave = endereco.strip().lower().replace(":", "").replace("-", "")
    return chave if _CHAVE_DE_CONTROLE.match(chave) else None


def nome_dado_ao_adaptador(maquina: MaquinaConfig | None, endereco: object) -> str:
    """O nome que ela deu a este adaptador — ``""`` quando não deu."""
    chave = chave_do_adaptador(endereco)
    if maquina is None or chave is None:
        return ""
    declarado = (maquina.adaptadores or {}).get(chave)
    return str(getattr(declarado, "nome", "") or "")


def ordem_dos_adaptadores(maquina: MaquinaConfig | None) -> list[str]:
    """As chaves dos adaptadores na ordem que ela arrastou, de cima para baixo."""
    if maquina is None:
        return []
    postos = [
        (declarado.ordem, chave)
        for chave, declarado in (maquina.adaptadores or {}).items()
        if declarado.ordem is not None
    ]
    return [chave for _ordem, chave in sorted(postos)]


def guardar_ordem_dos_adaptadores(enderecos: Sequence[str]) -> list[str]:
    """Grava a ordem que ela arrastou, pelo ENDEREÇO de cada adaptador."""
    novas: list[str] = []
    for endereco in enderecos:
        chave = chave_do_adaptador(endereco)
        if chave is not None and chave not in novas:
            novas.append(chave)
    for chave in ordem_dos_adaptadores(carregar_maquina()):
        if chave not in novas:
            novas.append(chave)
    novas = novas[: _TETO_DA_ORDEM_DOS_ADAPTADORES + 1]
    if not novas:
        return []
    declaracao = {"adaptadores": {chave: {"ordem": i} for i, chave in enumerate(novas)}}
    try:
        gravou = gravar_maquina(declaracao)
    except (ValueError, OSError) as exc:
        logger.warning("maquina_ordem_dos_adaptadores_nao_gravou", err=str(exc)[:200])
        return []
    return novas if gravou else []


def nomes_dos_controles(maquina: MaquinaConfig) -> dict[str, str]:
    """``{chave de controle: o nome que ela deu}`` — só quem tem nome."""
    return {
        chave: declarado.nome
        for chave, declarado in (maquina.controles or {}).items()
        if declarado.nome
    }


def gravar_o_nome_do_controle(endereco: str, nome: str | None) -> bool:
    """Grava (ou, com ``None``/vazio, esquece) o nome que ela deu. **Nunca levanta.**"""
    chave = chave_do_controle(endereco)
    if chave is None:
        return False
    valor = (nome or "").strip() or None
    try:
        return gravar_maquina({"controles": {chave: {"nome": valor}}})
    except (ValueError, OSError) as exc:
        logger.warning("maquina_nome_do_controle_nao_gravou", err=str(exc)[:200])
        return False


def mudo_do_microfone(
    endereco: object, maquina: MaquinaConfig | None = None
) -> bool | None:
    """O mudo que ela deixou no microfone DESTE controle. **Nunca levanta.**"""
    chave = chave_do_controle(endereco)
    if chave is None:
        return None
    if maquina is None:
        maquina = carregar_maquina()
    declarado = (maquina.controles or {}).get(chave)
    valor = getattr(declarado, "microfone_mudo", None)
    return valor if isinstance(valor, bool) else None


def gravar_o_mudo_do_microfone(endereco: object, mudo: bool) -> bool:
    """Grava o mudo do microfone deste controle. **Nunca levanta.**"""
    chave = chave_do_controle(endereco)
    if chave is None:
        return False
    try:
        if mudo_do_microfone(chave) is bool(mudo):
            return True
        return gravar_maquina({"controles": {chave: {"microfone_mudo": bool(mudo)}}})
    except (ValueError, OSError) as exc:
        logger.warning("maquina_mudo_do_microfone_nao_gravou", err=str(exc)[:200])
        return False


def _copia_funda(no: Any) -> Any:
    """Cópia dos dicionários aninhados, para a fusão nunca escrever no de origem."""
    if isinstance(no, Mapping):
        return {chave: _copia_funda(valor) for chave, valor in no.items()}
    return no


def _so_o_que_o_schema_conhece(bruto: Mapping[str, Any]) -> dict[str, Any]:
    """O documento sem as chaves de topo que uma versão futura acrescentou."""
    return {
        campo: valor
        for campo, valor in bruto.items()
        if campo in MaquinaConfig.model_fields
    }


def _o_que_ainda_vale(bruto: Mapping[str, Any]) -> tuple[MaquinaConfig, tuple[str, ...]]:
    """O documento sem os CAMPOS que o schema recusa — o resto sobrevive."""
    salvo = _so_o_que_o_schema_conhece(bruto)
    descartados = tuple(
        campo
        for campo in salvo
        if campo != VERSION_FIELD and not _campo_isolado_passa(campo, salvo[campo])
    )
    for campo in descartados:
        resgatado = _O_RESGATE_POR_DENTRO.get(campo, _nada_se_resgata)(salvo[campo])
        if resgatado is not None and _campo_isolado_passa(campo, resgatado):
            salvo[campo] = resgatado
        else:
            del salvo[campo]
    return MaquinaConfig.model_validate(salvo), descartados


def _campo_isolado_passa(campo: str, valor: Any) -> bool:
    try:
        MaquinaConfig.model_validate(
            {VERSION_FIELD: MAQUINA_SCHEMA_VERSION, campo: valor}
        )
    except ValidationError:
        return False
    return True


def _nada_se_resgata(_valor: Any) -> Any:
    return None


def _passa(modelo: type[BaseModel], valor: Any) -> bool:
    try:
        modelo.model_validate(valor)
    except ValidationError:
        return False
    return True


def _so_os_campos_que_passam(
    modelo: type[BaseModel], valor: Mapping[str, Any]
) -> dict[str, Any]:
    """Cada campo validado sozinho no ``modelo``: o torto e o desconhecido saem."""
    return {
        chave: dado
        for chave, dado in valor.items()
        if isinstance(chave, str) and _passa(modelo, {chave: dado})
    }


def _a_entrada_que_ainda_vale(porta: Any) -> Any:
    """A entrada sem o campo torto; ``None`` quando nada dela sobra de pé."""
    if _passa(PortaDeclarada, porta):
        return porta
    if not isinstance(porta, Mapping):
        return None
    limpa = _so_os_campos_que_passam(PortaDeclarada, porta)
    return limpa if limpa and _passa(PortaDeclarada, limpa) else None


def _a_face_que_ainda_vale(face: Any) -> Any:
    """A face sem o campo torto e sem o número de entrada torto."""
    if _passa(FaceDeclarada, face):
        return face
    if not isinstance(face, Mapping):
        return None
    limpa = _so_os_campos_que_passam(FaceDeclarada, face)
    numeros = face.get("portas")
    if isinstance(numeros, list):
        limpa["portas"] = [
            n for n in numeros if isinstance(n, str) and _NUMERO_DE_ENTRADA.match(n)
        ]
    return limpa if limpa and _passa(FaceDeclarada, limpa) else None


def _o_mapa_que_ainda_vale(mapa: Any) -> dict[str, Any] | None:
    """O ``mapa`` com cada entrada e cada face resgatadas uma a uma."""
    if not isinstance(mapa, Mapping):
        return None
    saida: dict[str, Any] = {}
    faces = mapa.get("faces")
    if isinstance(faces, list):
        saida["faces"] = [
            vale for face in faces if (vale := _a_face_que_ainda_vale(face)) is not None
        ]
    portas = mapa.get("portas")
    if isinstance(portas, Mapping):
        saida["portas"] = {
            numero: vale
            for numero, porta in portas.items()
            if isinstance(numero, str)
            and _NUMERO_DE_ENTRADA.match(numero)
            and (vale := _a_entrada_que_ainda_vale(porta)) is not None
        }
    return saida


_O_RESGATE_POR_DENTRO: dict[str, Callable[[Any], Any]] = {
    "mapa": _o_mapa_que_ainda_vale,
    "gestos": lambda gestos: (
        {k: v for k, v in gestos.items() if _campo_isolado_passa("gestos", {k: v})}
        if isinstance(gestos, Mapping) else None
    ),
    "computador": lambda computador: _o_computador_que_ainda_vale(computador),
}


def _o_computador_que_ainda_vale(computador: Any) -> dict[str, Any] | None:
    """O ``computador`` com cada seção global e cada controle validados sozinhos."""
    if not isinstance(computador, Mapping):
        return None
    saida: dict[str, Any] = {}
    do_global = computador.get("global")
    if isinstance(do_global, Mapping):
        saida["global"] = _so_os_campos_que_passam(ComputadorGlobal, do_global)
    controles = computador.get("controles")
    if isinstance(controles, Mapping):
        saida["controles"] = {
            chave: entrada
            for chave, entrada in controles.items()
            if _campo_isolado_passa("computador", {"controles": {chave: entrada}})
        }
    if isinstance(computador.get("migrado"), bool):
        saida["migrado"] = computador["migrado"]
    return saida


def _migrar_no_disco(bruto: dict[str, Any]) -> dict[str, Any]:
    """:func:`migrar_o_documento` na leitura, e o arquivo regravado migrado."""
    migrado = migrar_o_documento(bruto)
    if migrado == bruto:
        return bruto
    try:
        with MAQUINA_FILE_LOCK:
            agora = _ler_documento()
            if agora is None or agora.get(VERSION_FIELD) != MAQUINA_SCHEMA_VERSION:
                return migrado
            migrado = migrar_o_documento(agora)
            if migrado != agora:
                _guardar_a_copia_de_antes_da_migracao()
                _escrever(migrado)
                logger.info("maquina_migrada_para_um_registro_por_entrada")
    except Exception as exc:
        logger.warning("maquina_migracao_nao_gravou", err=str(exc)[:200])
    return migrado


def _guardar_a_copia_de_antes_da_migracao() -> None:
    """Copia o arquivo de antes da migração para ``maquina.json.com-os-lugares``."""
    origem = caminho_da_maquina()
    alvo = origem.parent / (origem.name + _ANTES_DA_MIGRACAO_SUFIXO)
    with contextlib.suppress(OSError):
        if not alvo.exists():
            alvo.write_bytes(origem.read_bytes())


def _guardar_os_bytes_recusados() -> None:
    """Copia o documento recusado para ``maquina.json.invalido``."""
    origem = caminho_da_maquina()
    with contextlib.suppress(OSError):
        alvo = origem.parent / (origem.name + _MAQUINA_INVALIDO_SUFIXO)
        alvo.write_bytes(origem.read_bytes())


def _podar(no: Any) -> Any:
    """Tira do documento o que é silêncio: ``None``, dicionário e lista vazios."""
    if not isinstance(no, dict):
        return no
    podado: dict[str, Any] = {}
    for chave, valor in no.items():
        filho = _podar(valor)
        if filho is None or filho == {} or filho == []:
            continue
        podado[chave] = filho
    return podado


def _ler_documento() -> dict[str, Any] | None:
    """O JSON do disco quando ele é um objeto; ``None`` em qualquer outro caso."""
    try:
        with caminho_da_maquina().open(encoding="utf-8") as fh:
            bruto = json.load(fh)
    except (FileNotFoundError, json.JSONDecodeError, OSError):
        return None
    return bruto if isinstance(bruto, dict) else None


def _escrever(documento: dict[str, Any]) -> None:
    """``os.replace`` de um temporário no MESMO diretório (troca atômica)."""
    path = caminho_da_maquina()
    payload = json.dumps(documento, ensure_ascii=False, indent=2, sort_keys=True)
    fd, tmp = tempfile.mkstemp(dir=os.path.dirname(os.fspath(path)), prefix=".maquina_")
    try:
        try:
            os.write(fd, payload.encode())
        finally:
            os.close(fd)
        os.replace(tmp, path)
    except Exception:
        with contextlib.suppress(OSError):
            os.unlink(tmp)
        raise
