"""``maquina.json`` — o que a MESA é, declarado por quem a montou.

A aba Configurações pergunta o que o Hefesto **não tem como medir**: se a antena
está acima ou abaixo da linha das cabeças, se há gente na frente dela, o que é
aquele rádio vizinho, em que modo a chave física do controle genérico foi posta,
qual a cor do plástico quando a leitura do firmware falha. Nada disso muda com o
jogo aberto — logo não é configuração de PERFIL, e não cabe em ``profiles/``.

Este módulo é vizinho de ``utils/session.py`` de propósito: é a camada que GUI,
daemon e CLI importam sem inverter dependência. Não em ``daemon/`` (a GUI
passaria a importar daemon) nem em ``core/`` (que é hardware).

O ARQUIVO É PRÓPRIO, E NÃO É UM BUMP DO ``controllers.json``
------------------------------------------------------------

Os quatro fatos MEDIDOS em 07/08/2026 que fecham aquela porta estão no cabeçalho
de ``daemon/subsystems/external_mask.py`` e valem inteiros aqui: ``identity.load``
descarta a fila quando a versão do arquivo difere; o save do outro lado só
aproveita entradas de versão igual; o payload é montado do zero, então chave de
topo escrita por outro morre no primeiro save; e ``merged_order_payload`` devolve
exatamente ``{addr, kind, rank}``, então campo novo POR ENTRADA morre nos dois
escritores. Logo: **arquivo próprio**, **versão própria**, sem migração e sem
renumerar a mesa de ninguém.

E a lição do terceiro fato é aplicada contra nós mesmos: :func:`gravar_maquina`
é read-modify-write e **preserva o que não entende** (chave de topo que uma
versão futura tenha escrito). Um arquivo cuja ``version`` não é a nossa **não é
lido nem sobrescrito** — recusar a gravar é mais barato que destruir a escolha de
alguém, e é por isso que a recusa por versão volta para a tela em vez de virar
exceção.

TODO CAMPO NASCE EM "NÃO SEI"
-----------------------------

``None`` (e dicionário vazio) é o único jeito de dizer "ninguém declarou".
Nenhum campo tem um valor de catálogo para isso — um valor que significa "sem
valor" é a porta pela qual o default entra disfarçado de escolha da pessoa (a
regra é de ``external_mask.mascaras_validas``, e vale aqui palavra por palavra).

O QUE FICA DE FORA, E DE QUEM É
-------------------------------

Três campos do desenho da aba **não** moram aqui, porque já têm dono, e gravá-los
também neste arquivo criaria dois donos do mesmo valor — a classe de defeito que a
ABAS-01 curou:

* **número de jogador** → ``controllers.json``, pelo ``identity.number.set``
  (``daemon/ipc_handlers.py:1513``);
* **máscara por aparelho** → ``controller_masks.json``
  (``daemon/subsystems/external_mask.py:175``);
* **tamanho do texto** → ``gui_preferences.json`` (``app/theme.py:39-40``).

Nomes dos campos em português, com uma exceção: ``version``, em inglês por
paridade com os dois irmãos em ``config_dir()`` — é o campo que os três leem
pelo mesmo nome.

E em português **sem acento por construção**, não por descuido: o nome do campo
vira chave JSON e string literal em toda seção da aba, e o portão de acentuação
reprova palavra acentuada escrita sem acento DENTRO de string (código puro ele
mascara). Por isso ``teto`` no lugar de "política" e ``apelido`` no lugar de
"descrição": o preço da alternativa seria um ``noqa-acento`` por linha, em cinco
sprints. Ao acrescentar campo, escolha uma palavra que não peça acento.

O QUE AINDA NÃO TEM ESCRITOR (22/08/2026)
-----------------------------------------

``MesaDeclarada.radios`` nasce sem quem o preencha: a chave é o ``vid:pid`` que a
enumeração de rádios vizinhos produz, e essa enumeração é de outra frente da
mesma leva. O campo existe desde já porque o schema é o que as quatro frentes
seguintes importam — não porque alguém já grave nele.
"""
from __future__ import annotations

import contextlib
import json
import os
import re
import tempfile
import threading
from collections.abc import Mapping
from pathlib import Path
from typing import Any, Literal, NamedTuple

from pydantic import (
    BaseModel,
    ConfigDict,
    Field,
    ValidationError,
    field_validator,
    model_validator,
)

from hefesto_dualsense4unix.utils.logging_config import get_logger

logger = get_logger(__name__)

#: Arquivo PRÓPRIO em ``config_dir()``, irmão do ``controllers.json`` e do
#: ``controller_masks.json``. Nunca o mesmo arquivo — ver o cabeçalho.
_MAQUINA_FILE = "maquina.json"

#: Cópia dos bytes que o schema recusou, escrita ANTES de reescrever o arquivo.
#: Sem ela o valor recusado some sem rastro, e não há como devolver à mão o que
#: uma versão futura (ou o editor dela) tinha gravado.
_MAQUINA_INVALIDO_SUFIXO = ".invalido"

#: Versão PRÓPRIA deste esquema, independente das outras duas que vivem em
#: ``config_dir()``. Separar as versões é o ponto: a declaração da mesa pode
#: evoluir sem descartar a fila de controles, e a fila pode evoluir sem apagar o
#: que ela declarou sobre a mesa.
#: 1 = CONFIG-03 (22/08/2026): mesa, controles, orçamento e ambiente.
MAQUINA_SCHEMA_VERSION = 1

#: O único campo em inglês do documento — ver o cabeçalho.
VERSION_FIELD = "version"

#: Lock de MÓDULO em volta do span leitura→``os.replace``, no espírito do
#: ``MASKS_FILE_LOCK``. O escritor de hoje é um só (o handler ``machine.declare``),
#: mas ele roda em ``asyncio.to_thread`` e dois pedidos em sequência curta caem em
#: threads diferentes: sem o lock, o read-modify-write de um perderia o do outro.
MAQUINA_FILE_LOCK = threading.Lock()

#: A chave de ``controles`` é a SAÍDA de ``ExternalIdentityRegistry._canonical``
#: (``daemon/subsystems/external_identity.py:429``): doze hex MINÚSCULOS, sem
#: separador. Casar com a entrada ``_MAC_RE`` (``:106-108``, que aceita
#: ``aa:bb:cc:...`` também) faria o daemon gravar ``aabbcc001122`` e o schema
#: exigir outra coisa.
_CHAVE_DE_CONTROLE = re.compile(r"^[0-9a-f]{12}$")

#: Primeiro octeto do endereço que o ``usb_probe_degrade`` do nosso DKMS FORJA
#: quando não há MAC (``external_identity.py:110-138``): ``02`` mais VID, PID e
#: bus. Dois clones do mesmo modelo recebem o MESMO endereço — persistir isso
#: gravaria em disco uma FUSÃO de dois aparelhos. O critério é o octeto ``02``
#: EXATO, nunca "o bit 0x02 ligado": os BLE random-static (1º octeto ≥ 0xC0) e a
#: faixa de teste ``aa:bb:cc:*`` têm esse bit sem serem síntese nossa.
_OCTETO_SINTETIZADO = "02"

#: A chave de ``radios`` é ``vid:pid`` em hex minúsculo — a identidade que o
#: barramento USB dá ao aparelho, e a única estável entre boots (``hciN`` e o
#: número da porta invertem). ``extra="forbid"`` não protege chave de
#: DICIONÁRIO: sem este validador o disco aceitaria ``{"Fone da TV": {...}}`` e a
#: próxima versão herdaria lixo.
_CHAVE_DE_RADIO = re.compile(r"^[0-9a-f]{4}:[0-9a-f]{4}$")

#: O caminho de barramento na palavra do kernel — ``3-1.1.4`` é o barramento
#: mais a cadeia de portas até o aparelho, e é o nome do diretório em
#: ``/sys/bus/usb/devices``. É a ÂNCORA do mapa, e é ele e não o ``vid:pid``
#: por uma medição: os adaptadores Bluetooth desta bancada são todos
#: ``2357:0604``, e a pergunta "onde ele está" precisa de uma chave que os
#: separe. Mesma lição do ``_CHAVE_DE_RADIO``: chave sem validador herda lixo.
_CAMINHO_DE_BARRAMENTO = re.compile(r"^[0-9]+-[0-9]+(\.[0-9]+)*$")

#: O número que ELA escreveu no gabinete: até três dígitos, e uma letra
#: opcional para a entrada que nasce de uma extensão (``15a``). Sem o teto, um
#: arquivo torto vira uma grade de mil quadrados na tela.
_NUMERO_DE_ENTRADA = re.compile(r"^[0-9]{1,3}[a-z]?$")

#: Tetos do desenho, pelo mesmo motivo. Oito faces e 64 entradas cobrem com
#: folga o gabinete mais cheio desta casa (três faces, quinze entradas) e o
#: notebook de duas ou três entradas que é o alvo declarado.
_MAXIMO_DE_FACES = 8
_MAXIMO_DE_ENTRADAS = 64

#: O nome de kernel de um NÓ DE ENTRADA — ``usb1-port5`` (entrada de hub-raiz)
#: ou ``3-1-port2`` (entrada de hub comum). É a MESMA forma de
#: ``integrations/entradas_do_gabinete._NO_DE_ENTRADA``, e é de propósito que
#: seja outra coisa que o ``_CAMINHO_DE_BARRAMENTO``: o caminho nomeia o
#: APARELHO (``3-1.2``) e some quando ele sai; o nó nomeia o BURACO e responde
#: com o buraco vazio.
_NO_DE_ENTRADA = re.compile(r"^(?:usb[0-9]+|[0-9]+-[0-9]+(?:\.[0-9]+)*)-port[0-9]+$")

#: Teto de nós por entrada. MEDIDO em 25/08/2026 nesta bancada: o ``peer`` do
#: kernel é recíproco e sempre de DOIS — 38 nós, 19 pares, nenhuma cadeia de
#: três. O teto é 4 e não 2 de propósito: um teto colado na medição de uma placa
#: faria a gravação INTEIRA ser recusada numa placa que publique mais, e o
#: sintoma na tela seria "não consegui gravar" em vez de "valor inválido" — a
#: mesma armadilha que ``secao_mesa._ao_declarar`` documenta.
_MAXIMO_DE_NOS_POR_ENTRADA = 4

#: A chave de ``ordens_dispensadas`` é o slug da regra que produziu a ordem
#: (``radio_largo_no_mesmo_hub``), que é a mesma chave de teste do catálogo em
#: ``integrations/ordens_da_mesa.py``. ASCII com sublinhado, nunca o texto de
#: tela: o texto tem dono e muda, a chave é contrato.
_CHAVE_DE_ORDEM = re.compile(r"^[a-z][a-z0-9_]{0,63}$")

#: Só a data, nunca a hora. A hora não muda nenhuma decisão do produto e é um
#: dado a mais sobre a rotina dela num arquivo que ela cola em relato de defeito.
_DATA_ISO = re.compile(r"^[0-9]{4}-[0-9]{2}-[0-9]{2}$")

#: Teto da assinatura de arranjo. Seis pares de caminho de barramento já é uma
#: mesa mais cheia que qualquer uma desta casa.
_MAXIMO_DO_ARRANJO = 256

#: Doze hex seguidos é a forma em que serial e endereço de rádio aparecem. A
#: assinatura de arranjo é caminho de barramento (``4-1.1.2``) e nunca chega
#: perto disso — ver ``OrdemDispensada._assinatura_sem_identidade``.
_DOZE_HEX = re.compile(r"[0-9a-fA-F]{12}")


class RadioDeclarado(BaseModel):
    """Um aparelho vizinho que divide a faixa de 2,4 GHz com os controles.

    O Hefesto encontra o aparelho no barramento e não sabe para que ele serve —
    ``tipo`` é a resposta que só a pessoa tem. ``apelido`` é o texto livre do
    "Outro" ("Fone sem fio da TV"), e vale para qualquer tipo.
    """

    model_config = ConfigDict(extra="forbid")

    tipo: (
        Literal["wifi", "teclado", "mouse", "webcam", "caixa_de_som", "outro"] | None
    ) = None
    apelido: str | None = None


class OrdemDispensada(BaseModel):
    """Uma recomendação que ela mandou calar — e o arranjo em que ela calou.

    ``arranjo`` é o que faz a dispensa ser sobre um FATO, e não sobre uma
    palavra. Ela vale para a mesa que ela viu; se ela mudar os cabos e a mesma
    regra disparar com arranjo novo, é fato novo e a ordem volta. Chavear a
    dispensa só pelo nome da regra faria a decisão de ontem calar uma medição de
    hoje.

    A assinatura carrega caminho de barramento (``4-1.1.2|3-1.1.4``) e nada
    mais: nunca serial, nunca endereço. Ela precisa mudar quando os CABOS mudam,
    e o número da entrada é o desenho dela, que muda sem nenhum cabo sair do
    lugar.
    """

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
        """Teto de tamanho, e nenhuma sequência com cara de endereço.

        ``check_anonymity.sh`` diz por escrito que o serial identifica a unidade
        dela tão bem quanto o MAC, e este arquivo é gravado no ``$HOME`` dela e
        lido pelo ``doctor.sh --censo``, que ela cola em relato de defeito.
        """
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
        """A chave é o slug da regra, e ``extra="forbid"`` não protege chave.

        Mesma lição do ``_chave_de_radio_e_vid_pid``: sem este validador o disco
        aceitaria ``{"aquela recomendação chata": {...}}`` e a próxima versão
        herdaria lixo que nenhuma regra reclama.
        """
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
    """Um conjunto de entradas que a pessoa enxerga JUNTO — "Frente", "Hub".

    A ordem da lista é a ordem do desenho: os quadrados saem na tela na ordem
    em que os números estão aqui, e reordenar se faz apagando e pondo de novo.

    **Nenhuma face nasce sozinha.** O produto nunca cria "Frente" e "Traseira"
    por conta própria: um notebook declara "Esquerda" e "Direita", e ponto.
    Face inventada é a presunção que a ``ONDA0-Z7 · O AMBIENTE PRESUMIDO``
    existe para caçar.

    A entrada que nasce de uma extensão (a ``15a``) **não entra nesta lista**:
    ela desenha dentro do quadrado da entrada que a hospeda, e pô-la na fileira
    faria a fileira de sete do hub virar oito — o desenho deixaria de bater com
    o metal.

    ``perto`` E ``alto`` SÃO O FATO FÍSICO, E SÓ ELA O TEM
    ------------------------------------------------------

    O motor do arranjo (``integrations/arranjo_da_mesa``) lê os dois em
    ``Face.perto`` e ``Face.alto``, e até 25/08/2026 **nenhum dos dois tinha
    fonte**: o esquema não tinha onde guardá-los, então toda face nascia
    ``perto=False`` e ``alto=False`` e o bônus de +20 do teclado ("na frente,
    que é a mais perto de você") nunca podia disparar. Juízo montado sobre um
    fato que nunca chega é juízo otimista demais, e isso é pior que juízo
    nenhum.

    Os dois são **fato dela**, nunca leitura: o ``/sys`` desta bancada responde
    ``panel=right``, ``horizontal_position=left`` e ``vertical_position=lower``
    — idênticos — para ``usb1-port3`` e ``usb1-port6``, que ficam em faces
    DIFERENTES do metal, e a ACPI desta placa nunca diz "front" nem "back".
    Nenhuma leitura chega perto de saber se a face está virada para a pessoa ou
    se ela está acima da linha das cabeças.

    ``False`` não é "não sei", é "não": uma face que ela não marcou não ganha
    bônus nenhum, que é exatamente o que acontecia antes destes campos
    existirem. São ``bool`` e não ``bool | None`` de propósito — "não sei se a
    frente é a frente" não é uma resposta que mude alguma coisa, e um terceiro
    estado sem consumidor é campo que a próxima pessoa tem de decifrar.

    ``_podar`` **não** tira o ``False`` (ele tira ``None``, ``{}`` e ``[]``),
    então uma face declarada carrega os dois campos no disco. É barato e é
    verdade: o arquivo diz que a pergunta foi feita e a resposta foi "não".
    """

    model_config = ConfigDict(extra="forbid")

    nome: str = ""
    portas: list[str] = Field(default_factory=list)
    #: Esta é a face virada para quem está sentado — a "frente do gabinete".
    perto: bool = False
    #: Esta face fica no alto (o hub em cima do rack), com a antena de quem
    #: mora nela acima da linha das cabeças.
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
    """Uma entrada do gabinete, pelo número DELA — e o que está nela.

    ``caminho`` é o nome do kernel (``3-1.1.4``), que é determinístico pelo
    soquete físico: enquanto o cabo não mudar de buraco, ele é o mesmo em todo
    boot. É a única amarração entre o número que ela enxerga e o aparelho que o
    barramento enumera.

    ``filha_de`` é o número da entrada que hospeda a EXTENSÃO. Cabo de extensão
    passivo não tem descritor USB — o dongle na ponta enumera como se estivesse
    na entrada do hub, e nenhuma leitura de ``/sys``, hoje ou nunca, distingue
    os dois casos. Quem sabe é ela, porque ela disse; não há detecção e não há
    palpite.

    O nome é ``filha_de`` e não "mãe" por construção: "mãe" escrito sem acento
    dentro de string é exatamente o que o portão de acentuação reprova (ver o
    cabeçalho deste módulo).

    ``nos`` É O QUE ALCANÇA A ENTRADA **VAZIA**, e o ``caminho`` não alcança
    ---------------------------------------------------------------------

    ``caminho`` nomeia o APARELHO (``3-1.2``) e some do ``/sys`` quando ele sai;
    ``nos`` nomeia o BURACO (``usb1-port5``), e o nó do buraco responde
    ``state=not attached`` com o buraco vazio — MEDIDO em 25/08/2026: 38 nós de
    entrada nesta bancada, todos respondendo ``state`` e ``connect_type``, com e
    sem aparelho. É por isso que uma entrada nunca declarada some do mapa: sem
    ``nos``, "a entrada 7" só existe enquanto houver algo nela.

    A lista tem DOIS elementos quando o buraco é 3.x e o kernel publicou o
    ``peer``: um buraco USB 3.0 tem um nó no hub-raiz 2.0 e outro no 3.x, e o
    DualSense (que é 2.0) sempre enumera no lado 2.0. Sem a lista, o produto
    acha que são dois buracos e manda a pessoa se ajoelhar atrás do gabinete
    duas vezes pelo mesmo furo.

    Quem RESOLVE esta lista contra a leitura de agora é
    ``integrations/entradas_do_gabinete.furo_declarado``, e a comparação é por
    INTERSEÇÃO: um buraco declarado com dois nós continua sendo o mesmo buraco
    quando o kernel de hoje publica um só.

    **Entrada vazia não tem entrada aqui.** ``_podar`` tira ``None`` e vazio do
    documento antes de escrever, e a ausência é a resposta "aqui não tem nada"
    — a mesma gramática de "não sei" do arquivo inteiro.
    """

    model_config = ConfigDict(extra="forbid")

    caminho: str | None = None
    filha_de: str | None = None
    nos: list[str] = Field(default_factory=list)

    @field_validator("caminho")
    @classmethod
    def _caminho_e_o_nome_do_kernel(cls, valor: str | None) -> str | None:
        if valor is not None and not _CAMINHO_DE_BARRAMENTO.match(valor):
            raise ValueError(
                f"caminho {valor!r} não é o nome do kernel "
                "('3-1.1.4': barramento, traço, e a cadeia de portas)"
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


class MapaDaMesa(BaseModel):
    """O gabinete dela, desenhado por ela — o que ``/sys`` não tem como saber.

    MEDIDO em 24 e 25/08/2026, e é a prova de que o mapa tem de ser DECLARADO:
    as duas entradas da frente do gabinete desta bancada (``usb1-port3`` e
    ``usb1-port6``) respondem ``panel=right``, ``horizontal_position=left`` e
    ``vertical_position=lower`` — idênticos —, e a ACPI desta placa nunca diz
    "front" nem "back". Deduzir o mapa daria duas entradas iguais para dois
    buracos que ficam em faces diferentes do metal.

    **Um dono para cada fato.** A face lista os números; a entrada guarda a
    amarração. A face não repete o caminho e a entrada não repete a face —
    essa duplicação é a classe de defeito que a ``ABAS-01`` curou.
    """

    model_config = ConfigDict(extra="forbid")

    faces: list[FaceDeclarada] = Field(default_factory=list)
    portas: dict[str, PortaDeclarada] = Field(default_factory=dict)

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


class ControleDeclarado(BaseModel):
    """O que um controle não anuncia sobre si.

    ``modo`` é a chave física do 8BitDo e afins, escolhida ANTES de ligar e que o
    aparelho não informa. ``botoes`` é só o desenho que aparece na tela — nada é
    remapeado no controle. ``cor`` é texto livre porque a tela oferece os seis
    nomes de fábrica E um campo "Outra", para edição especial fora da lista.

    ``microfone`` é a ponte de mic por Bluetooth DAQUELE controle
    (``QUATRO-MICROFONES-01``, 22/08/2026, decisão dela: *"por controle"*). Mora
    aqui, e não no perfil, pela razão do cabeçalho de
    ``daemon/subsystems/bt_mic.py``: um microfone que liga ao trocar de jogo é
    exatamente a surpresa que aquele módulo recusa.

    **Só ``True`` chega ao disco.** Desligar escreve ``None``, porque "nunca
    pedi" e "não quero" deixam a ponte no chão do mesmo jeito — e um ``false``
    gravado seria um valor de catálogo para o silêncio, que é a porta pela qual o
    default entra disfarçado de escolha dela (a regra está no cabeçalho deste
    módulo). O campo aceita ``bool`` porque um ``false`` que já esteja em disco,
    escrito à mão, tem de ser LIDO em vez de derrubar o documento inteiro.
    """

    model_config = ConfigDict(extra="forbid")

    modo: Literal["xinput", "dinput", "switch"] | None = None
    botoes: Literal["xbox", "nintendo"] | None = None
    cor: str | None = None
    microfone: bool | None = None


class OrcamentoDeclarado(BaseModel):
    """O teto da mesa inteira — as abas seguem mandando, só não passam daqui.

    A chave é ``max``, nunca o rótulo ``"Máximo"``: o valor é o mesmo de
    ``profiles/schema.py:336``, e o rótulo de tela sai de ``_POLICY_LABEL``
    (``app/actions/rumble_actions.py:79-84``). Gravar o rótulo faria o
    ``extra="forbid"`` recusar o DOCUMENTO INTEIRO, e o sintoma na tela seria
    "não consegui gravar", não "valor inválido".
    """

    model_config = ConfigDict(extra="forbid")

    teto: Literal["economia", "balanceado", "max", "auto"] | None = None


class MaquinaConfig(BaseModel):
    """O documento inteiro. Nasce todo em "não sei", e é assim que ele é útil."""

    model_config = ConfigDict(extra="forbid")

    version: Literal[1] = 1
    mesa: MesaDeclarada = Field(default_factory=MesaDeclarada)
    controles: dict[str, ControleDeclarado] = Field(default_factory=dict)
    orcamento: OrcamentoDeclarado = Field(default_factory=OrcamentoDeclarado)
    # CONEXÕES · MAPA 2D 01 (25/08/2026): o gabinete dela, e a ``version``
    # NÃO sobe. Campo novo sem bump É a migração, e o caminho já estava
    # construído nos dois sentidos: arquivo antigo lido por código novo cai no
    # ``default_factory`` e nada se perde; arquivo novo lido por código antigo
    # tem ``mapa`` tirado da validação por ``_so_o_que_o_schema_conhece`` e
    # copiado VERBATIM de volta ao disco por ``gravar_maquina_com_descartes``.
    # Subir para ``2`` faria, em toda máquina que já declarou, a leitura
    # devolver "não sei" em mesa, controles e orçamento, e a gravação dizer
    # "não gravei" para sempre. Não há passo de migração a escrever.
    mapa: MapaDaMesa = Field(default_factory=MapaDaMesa)
    # NOTA DATADA (T2, CONFIGURAÇÕES-FECHA-01, 24/08/2026): ``ambiente`` saiu
    # do esquema. O campo nasceu na v1 sem escritor NEM leitor — quem grava a
    # correção de ambiente é ``gravar_correcao_de_ambiente``
    # (``app/ambiente.py:101``), e sempre gravou em ``gui_preferences.json``,
    # nunca aqui. Manter os dois seria dar ao mesmo fato um segundo dono
    # possível, a classe de defeito que a ABAS-01 curou (ver o cabeçalho deste
    # módulo). O campo não é reaproveitado por outro: sai, e não volta.

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


def caminho_da_maquina() -> Path:
    """Path do ``maquina.json`` — import LAZY de ``config_dir``.

    Lazy porque resolver ``config_dir()`` no topo do módulo mata o monkeypatch da
    bateria: ``app/gui_prefs.py:21`` é a cicatriz exata dessa escolha, e é por ela
    que aquele módulo é inisolável em teste.
    """
    from hefesto_dualsense4unix.utils.xdg_paths import config_dir

    return config_dir(ensure=True) / _MAQUINA_FILE


def fundir_declaracao(
    base: Mapping[str, Any] | None, declaracao: Mapping[str, Any]
) -> dict[str, Any]:
    """``base`` com ``declaracao`` por cima, fundindo dicionário com dicionário.

    É o primitivo de que as seções da aba precisam e o mesmo que
    :func:`gravar_maquina` usa contra o disco. Duas propriedades importam:

    * a fusão desce nos dicionários aninhados, então declarar
      ``{"mesa": {"altura_da_antena": "acima"}}`` **não apaga** a
      ``linha_de_visada`` que já estava lá — nem o orçamento, nem os controles;
    * ``None`` presente na declaração é uma escolha ("voltei para 'Não sei'") e
      SOBRESCREVE. Só a AUSÊNCIA da chave preserva o que havia.

    Sem a primeira, cada seção da aba precisaria mandar o documento inteiro e a
    última a gravar apagaria o que as outras quatro tinham declarado.
    """
    fundido: dict[str, Any] = _copia_funda(base or {})
    for chave, valor in declaracao.items():
        anterior = fundido.get(chave)
        if isinstance(valor, Mapping) and isinstance(anterior, Mapping):
            fundido[chave] = fundir_declaracao(anterior, valor)
        else:
            fundido[chave] = _copia_funda(valor) if isinstance(valor, Mapping) else valor
    return fundido


def carregar_maquina() -> MaquinaConfig:
    """A declaração do disco. **Nunca levanta** — no pior caso, tudo em "não sei".

    Ausente, ilegível, truncado, não-objeto ou de versão que não é a nossa:
    devolve o documento vazio, com ``logger.debug``. Esta invariante é
    carregada por dois chamadores que não podem cair — o boot do daemon e a
    montagem da aba —, e por isso ela é asserção da bateria, não sorte.

    Um CAMPO que o schema recusa (T2, CONFIGURAÇÕES-FECHA-01, 24/08/2026) NÃO
    esvazia o documento inteiro: o resgate é o mesmo campo-a-campo de
    :func:`_o_que_ainda_vale`, que ``gravar_maquina_com_descartes`` já usa
    desde `9848c41`. Sem isto, um `maquina.json` escrito por uma versão futura
    (ou por um esquema que perdeu um campo, como `ambiente` nesta mesma
    sprint) perderia mesa, controles e orçamento na LEITURA — o mesmo defeito
    que `9848c41` curou, só que do outro lado do arquivo.
    """
    try:
        bruto = _ler_documento()
        if bruto is None:
            return MaquinaConfig()
        if bruto.get(VERSION_FIELD) != MAQUINA_SCHEMA_VERSION:
            logger.debug("maquina_versao_desconhecida", versao=bruto.get(VERSION_FIELD))
            return MaquinaConfig()
        return MaquinaConfig.model_validate(_so_o_que_o_schema_conhece(bruto))
    except ValidationError as exc:
        logger.debug("maquina_documento_invalido_campo_a_campo", err=str(exc))
        if bruto is None:  # defensivo — inatingível: só o validate acima levanta
            return MaquinaConfig()
        try:
            atual, descartados = _o_que_ainda_vale(bruto)
        except Exception as exc2:  # defensivo — resgate não pode derrubar a leitura
            logger.debug("maquina_resgate_campo_a_campo_falhou", err=str(exc2))
            return MaquinaConfig()
        if descartados:
            logger.warning(
                "maquina_load_descartou_campos", descartados=list(descartados)
            )
        return atual
    except Exception as exc:  # defensivo — a leitura jamais derruba quem chama
        logger.debug("maquina_load_falhou", err=str(exc))
    return MaquinaConfig()


class ResultadoDaGravacao(NamedTuple):
    """O que a gravação fez — ``gravou`` e o que ela teve de deixar para trás.

    ``descartados`` são os campos de TOPO que estavam em disco com valor que o
    schema recusa: eles não voltam ao arquivo, e quem chama é o único que pode
    dizer isso na tela. O consumidor natural é o ``machine.declare``
    (``daemon/ipc_handlers.py``), que devolveria a lista pela ponte para a aba
    Configurações avisar "não consegui reaproveitar X" em vez de apagar calado.
    """

    gravou: bool
    descartados: tuple[str, ...]


def gravar_maquina(declaracao: Mapping[str, Any]) -> bool:
    """:func:`gravar_maquina_com_descartes` sem a lista — ``True`` = gravou."""
    return gravar_maquina_com_descartes(declaracao).gravou


def gravar_rascunho_da_mesa(declaracao: Mapping[str, Any]) -> bool:
    """Grava a seção ``mesa`` como RASCUNHO — sem o gesto de "Aplicar" atrás.

    T-07 (ONDA0-Z7 · O AMBIENTE PRESUMIDO 01, 24/08/2026). Hoje o único
    escritor de ``maquina.json`` é o botão "Aplicar" do rodapé
    (``app/actions/footer_actions.py``, via ``machine.declare``) — declarar a
    mesa e fechar o programa sem clicar nele perde tudo, sem aviso (medido em
    §3.7 da sprint). Esta função é a PRIMITIVA que a Onda 1 · Configurações
    (CONFIG-03) vai pendurar no gesto de declarar: mesma gravação atômica,
    mesmo lock (``MAQUINA_FILE_LOCK``), mesma preservação do que não entende —
    tudo herdado de :func:`gravar_maquina_com_descartes`, sem duplicar nada.

    Escopada à seção ``mesa`` de propósito: o chamador (uma seção da aba) não
    precisa conhecer o envelope do documento inteiro, só os campos de
    :class:`MesaDeclarada` que ela mesma editou. Um rascunho **nunca inventa**
    valor de catálogo — campo ausente de ``declaracao`` continua sem valor,
    porque :func:`fundir_declaracao` só sobrescreve o que veio.

    Z7-B **não chama** esta função de lugar nenhum: quem liga o gesto de
    declarar a ela é a Onda 1, em ``footer_actions.py`` ou vizinho — ver §10 da
    sprint.
    """
    return gravar_maquina({"mesa": dict(declaracao)})


def gravar_maquina_com_descartes(declaracao: Mapping[str, Any]) -> ResultadoDaGravacao:
    """Funde a declaração PARCIAL no documento do disco.

    ``gravou=False`` significa uma coisa só: **o arquivo em disco tem uma
    ``version`` que não é a nossa**, e então nada é lido nem escrito — os bytes
    ficam intactos. Escolha de alguém não se destrói para registrar outra, e uma
    versão futura é escolha de alguém.

    Levanta ``ValueError`` (``ValidationError`` herda dele) quando a declaração
    não passa no schema e ``OSError`` quando a escrita falha; quem chama traduz
    as duas para recusa com motivo, que é o contrato do ``machine.declare``.

    O que sobrevive a esta escrita: chave de TOPO que uma versão futura tenha
    escrito, copiada verbatim. O que NÃO sobrevive: o CAMPO cujo valor o schema
    recusa — um valor inválido não é escolha de ninguém, é corrupção, e
    preservá-lo travaria toda gravação futura deste arquivo para sempre. O
    estrago para no campo ruim (:func:`_o_que_ainda_vale`): antes, um único
    ``ambiente`` fora do catálogo levava junto mesa, controles e orçamento.
    """
    MaquinaConfig.model_validate(dict(declaracao))
    with MAQUINA_FILE_LOCK:
        bruto = _ler_documento() or {}
        if bruto and bruto.get(VERSION_FIELD) != MAQUINA_SCHEMA_VERSION:
            logger.warning(
                "maquina_save_recusado_schema_desconhecido",
                versao_arquivo=bruto.get(VERSION_FIELD),
            )
            return ResultadoDaGravacao(False, ())
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
        fundido = MaquinaConfig.model_validate(
            fundir_declaracao(atual.model_dump(mode="json"), declaracao)
        )
        documento = {
            campo: valor
            for campo, valor in bruto.items()
            if campo not in MaquinaConfig.model_fields
        }
        documento.update(_podar(fundido.model_dump(mode="json")))
        documento[VERSION_FIELD] = MAQUINA_SCHEMA_VERSION
        _escrever(documento)
        logger.debug("maquina_gravada", campos=sorted(declaracao))
    return ResultadoDaGravacao(True, descartados)


# ---------------------------------------------------------------------------
# Interno
# ---------------------------------------------------------------------------


def _copia_funda(no: Any) -> Any:
    """Cópia dos dicionários aninhados, para a fusão nunca escrever no de origem."""
    if isinstance(no, Mapping):
        return {chave: _copia_funda(valor) for chave, valor in no.items()}
    return no


def _so_o_que_o_schema_conhece(bruto: Mapping[str, Any]) -> dict[str, Any]:
    """O documento sem as chaves de topo que uma versão futura acrescentou.

    Elas são preservadas no disco (ver :func:`gravar_maquina`), mas não podem
    entrar na validação: ``extra="forbid"`` recusa o DOCUMENTO INTEIRO, e uma
    chave que não conhecemos derrubaria a leitura de tudo o que conhecemos.
    """
    return {
        campo: valor
        for campo, valor in bruto.items()
        if campo in MaquinaConfig.model_fields
    }


def _o_que_ainda_vale(bruto: Mapping[str, Any]) -> tuple[MaquinaConfig, tuple[str, ...]]:
    """O documento sem os CAMPOS que o schema recusa — o resto sobrevive.

    Cada campo de topo é validado sozinho, então a corrupção fica presa à sua
    subárvore: o caminho realista para chegar aqui não é edição à mão, é uma
    versão futura alargar um ``Literal`` e alguém voltar de versão, e nesse dia o
    documento inteiro sumia porque UM campo tinha um valor novo demais.
    """
    salvo = _so_o_que_o_schema_conhece(bruto)
    descartados = tuple(
        campo
        for campo in salvo
        if campo != VERSION_FIELD and not _campo_isolado_passa(campo, salvo[campo])
    )
    for campo in descartados:
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


def _guardar_os_bytes_recusados() -> None:
    """Copia o documento recusado para ``maquina.json.invalido``.

    O campo recusado não volta ao arquivo; sem esta cópia ele é irrecuperável, e
    devolver à mão um valor que ninguém mais tem é impossível.
    """
    origem = caminho_da_maquina()
    with contextlib.suppress(OSError):
        alvo = origem.parent / (origem.name + _MAQUINA_INVALIDO_SUFIXO)
        alvo.write_bytes(origem.read_bytes())


def _podar(no: Any) -> Any:
    """Tira do documento o que é silêncio: ``None``, dicionário e lista vazios.

    ``None`` e chave ausente querem dizer a MESMA coisa aqui ("não sei"), então
    escrever os dois é escrever duas vezes. O arquivo que ela abre no editor tem
    o tamanho do que ela declarou, não o tamanho do schema.

    A lista vazia entrou em 25/08/2026, com ``MapaDaMesa.faces``, e pelo mesmo
    motivo: sem ela, quem NUNCA desenhou a mesa passaria a carregar um
    ``"mapa": {"faces": []}`` em disco — silêncio escrito por extenso, que é o
    que esta função existe para não deixar acontecer. Nenhum outro campo do
    documento é lista, então a regra nova não alcança nada que já estivesse lá.
    """
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
    """O JSON do disco quando ele é um objeto; ``None`` em qualquer outro caso.

    ``None`` autoriza a escrita: não há escolha de ninguém a destruir num arquivo
    que já não diz nada. Quem barra a escrita é a VERSÃO, checada por quem chama.
    """
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
