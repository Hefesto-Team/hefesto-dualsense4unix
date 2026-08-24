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

from pydantic import BaseModel, ConfigDict, Field, ValidationError, field_validator

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


class MesaDeclarada(BaseModel):
    """Onde a antena está — o que nenhum barramento sabe.

    Corpo humano absorve 2,4 GHz, e nem a altura nem o obstáculo aparecem em
    lugar nenhum do sistema. As duas escolhas existem para que o exame da mesa
    possa explicar um alcance ruim em vez de apenas medi-lo.
    """

    model_config = ConfigDict(extra="forbid")

    altura_da_antena: Literal["acima", "abaixo"] | None = None
    linha_de_visada: Literal["livre", "com_gente"] | None = None
    radios: dict[str, RadioDeclarado] = Field(default_factory=dict)

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
    #: Informa só a mensagem de ajuda da bandeja, nunca o comportamento: no
    #: COSMIC o ícone aparece sozinho, no GNOME precisa de extensão instalada.
    ambiente: Literal["cosmic", "gnome", "outro"] | None = None

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

    Ausente, ilegível, truncado, não-objeto, de versão que não é a nossa ou com
    um valor que o schema recusa: os seis devolvem o documento vazio, com
    ``logger.debug``. Esta invariante é carregada por dois chamadores que não
    podem cair — o boot do daemon e a montagem da aba —, e por isso ela é
    asserção da bateria, não sorte.
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
        logger.debug("maquina_documento_invalido", err=str(exc))
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
    """Tira do documento o que é silêncio: ``None`` e dicionário vazio.

    ``None`` e chave ausente querem dizer a MESMA coisa aqui ("não sei"), então
    escrever os dois é escrever duas vezes. O arquivo que ela abre no editor tem
    o tamanho do que ela declarou, não o tamanho do schema.
    """
    if not isinstance(no, dict):
        return no
    podado: dict[str, Any] = {}
    for chave, valor in no.items():
        filho = _podar(valor)
        if filho is None or filho == {}:
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
