"""Máscara por APARELHO dos controles externos (MÁSCARA-01 / E1, 07/08/2026).

*"Como este controle deve aparecer nos jogos?"* — a escolha é do **aparelho**,
não da configuração de jogo. É verdade sobre o plástico e sobre os rótulos
impressos nele, e não muda porque a janela em foco mudou. Há também a razão
dura: **trocar a máscara derruba e recria o gamepad virtual**; se ela morasse no
perfil, cada troca automática de perfil — cada alt-tab — faria o controle sumir
e voltar no meio da partida (sprint
``docs/process/sprints/2026-07-25-MASCARA-01-como-este-controle-aparece-nos-jogos.md``,
seção *"Onde a máscara mora"*).

Este módulo é **só o registro**: onde a escolha mora, como ela sobrevive ao
reboot e o que ela NÃO promete. Ele não adota externo, não cria gamepad virtual,
não esconde ninguém do jogo e não desenha tela — isso é a `E2`/`E3`/`E4` da
MÁSCARA-01 e a `E3` da LUGAR-À-MESA-01, que ela autorizou **depois** desta.

O ARQUIVO É PRÓPRIO, E NÃO É UM BUMP DO ``controllers.json``
-----------------------------------------------------------

A sprint de 25/07 pedia *"registro de identidade, no mesmo arquivo que já guarda
a ordem de preferência, com versão de esquema nova"*. Isso **caducou em
07/08/2026** — ver a nota datada na própria sprint. Quatro fatos MEDIDOS na
árvore fecham aquela porta, e os quatro estão registrados na
``REGRA-NAO-REGISTRO-01``:

1. ``identity.load`` (``identity.py:858``) DESCARTA a fila inteira quando a
   versão do arquivo difere — um bump renumeraria a mesa dela;
2. ``identity._save_locked`` só aproveita as entradas do outro lado quando
   ``bruto.get("version") == CONTROLLERS_SCHEMA_VERSION`` (``:940-950``): o
   primeiro save de DualSense depois de um bump APAGARIA a fila dos externos;
3. ``payload: dict[str, Any] = {}`` é montado do zero (``identity.py:951``) —
   chave nova de topo escrita pelo lado externo morre no primeiro save do outro;
4. ``merged_order_payload`` devolve exatamente ``{addr, kind, rank}``
   (``:316``) e ``order_entries`` descarta ``kind`` desconhecido (``:279``) —
   campo novo POR ENTRADA morre nos dois escritores.

Logo: **arquivo próprio** (:data:`_MASKS_FILE`) em ``config_dir()``, com
**versão própria** (:data:`MASKS_SCHEMA_VERSION`), chaveado pela identidade que
:func:`~...external_identity.identity_for_entry` já carimba. Sem bump, sem
migração, sem renumerar ninguém.

E a lição do item 3 é aplicada a ESTE arquivo, contra nós mesmos: o save é
read-modify-write e **preserva o que não entende** (chaves de topo e campos por
entrada que uma versão futura tenha escrito). Um arquivo cuja ``version`` não
seja a nossa não é lido **nem sobrescrito** — recusar a gravar é mais barato que
destruir a escolha de alguém.

O QUE ESTE REGISTRO NÃO PROMETE — os dois limites, GRAU MEDIDO
--------------------------------------------------------------

1. **Identidade volátil não atravessa a sessão.** ``dev:<instância HID>``,
   ``path:<node>`` e o endereço SINTETIZADO pelo ``usb_probe_degrade``
   (``02`` + VID + PID + bus) não identificam aparelho nenhum — ver
   ``external_identity._canonical`` (``:415-431``) e o MODO-01. Máscara
   pendurada ali vale na sessão e **não vai ao disco**: persistir seria gravar
   uma escolha em cima de uma chave que dois aparelhos diferentes podem
   dividir (CLONE-01).
2. **Máscara é por ROSTO, não por grupo.** A ``REGRA-NAO-REGISTRO-01``
   compartilha **rank**, nunca identidade: os dois endereços de hardware do
   8BitDo dividem um lugar na fila e continuam sendo duas chaves. Máscara posta
   num rosto **não vale no outro**. É o mesmo limite que aquela sprint declara
   para ``Profile.controllers`` (item 5 de *"O que esta sprint NÃO resolve"*), e
   a extensão natural — o lookup consultar os outros rostos do grupo — está
   deliberadamente fora deste desenho.

VALOR INVÁLIDO NUNCA VIRA XBOX
------------------------------

:func:`normalizar_mascara` é ESTRITA de propósito: devolve ``None`` para o que
não reconhece, em vez de cair no ``DEFAULT_FLAVOR``. O normalizador tolerante
(``uinput_gamepad.normalize_flavor``, que aceita sinônimos de CLI/IPC e cai em
``"xbox"``) é o certo para a linha de comando e o errado aqui: esta casa já
pagou o ``or "xbox"`` do editor de perfis, que transformava *"sem opinião"* em
*"exige Xbox"* e apagava giroscópio e touchpad no jogo dela sem que ninguém
pedisse (ESCOLHA-DELA-VENCE-01, E1). O catálogo de máscaras válidas é o
``FLAVORS`` do vpad — fonte única, para que uma máscara nova não precise ser
declarada em dois lugares.
"""
from __future__ import annotations

import contextlib
import json
import os
import tempfile
import threading
from pathlib import Path
from typing import Any

from hefesto_dualsense4unix.daemon.subsystems.external_identity import (
    ExternalIdentityRegistry,
    identity_for_entry,
)
from hefesto_dualsense4unix.integrations.uinput_gamepad import FLAVORS
from hefesto_dualsense4unix.utils.logging_config import get_logger

logger = get_logger(__name__)

#: Arquivo PRÓPRIO, irmão do ``controllers.json`` em ``config_dir()``. Nunca o
#: mesmo arquivo: ver o cabeçalho do módulo, itens 1 a 4.
_MASKS_FILE = "controller_masks.json"

#: Versão PRÓPRIA do esquema deste arquivo — independente do
#: ``CONTROLLERS_SCHEMA_VERSION``, que governa a FILA e cuja mudança descarta a
#: numeração da casa inteira. Separar as duas versões é o ponto: a máscara pode
#: evoluir sem renumerar ninguém, e a fila pode evoluir sem apagar máscara.
#: 1 = MÁSCARA-01/E1 (07/08/2026): lista de ``{identity, flavor}``.
MASKS_SCHEMA_VERSION = 1

#: Campos do documento. Nomes em inglês por paridade com o irmão
#: (``version``/``order``/``addr``/``kind``/``rank``) — o conteúdo é dado de
#: máquina, não texto de tela.
VERSION_FIELD = "version"
MASKS_FIELD = "masks"
IDENTITY_FIELD = "identity"
FLAVOR_FIELD = "flavor"

#: Lock de MÓDULO em volta do span read→``os.replace``, no mesmo espírito do
#: ``CONTROLLERS_FILE_LOCK``. Este arquivo tem um escritor só (o registro
#: abaixo), mas duas INSTÂNCIAS do registro no mesmo processo fariam
#: read-modify-write concorrente — e o ``RLock`` de instância não protege contra
#: o outro objeto. Nunca importar o lock do ``identity.py`` para cá: são
#: arquivos diferentes, e dividir o lock acoplaria a máscara à fila.
MASKS_FILE_LOCK = threading.Lock()


def mascaras_validas() -> frozenset[str]:
    """Os valores que uma máscara pode ter — o catálogo do vpad, não uma cópia.

    Fonte única: ``integrations.uinput_gamepad.FLAVORS``. Uma máscara nova
    (digamos, um terceiro sabor) passa a ser aceita aqui sem uma linha de
    edição — e, o que importa mais, **não existe** aqui uma lista que possa
    divergir daquela e aceitar no disco um valor que o vpad não sabe criar.

    "Como ele mesmo" NÃO está no conjunto de propósito: ela é a AUSÊNCIA de
    máscara (``None``, nenhuma entrada no arquivo), e não um terceiro valor.
    Um valor para dizer "sem valor" é a porta pela qual o default entra
    disfarçado de escolha.
    """
    return frozenset(FLAVORS)


def normalizar_mascara(valor: object) -> str | None:
    """A máscara canônica de ``valor``, ou ``None`` quando não há uma.

    ESTRITA de propósito — ver o cabeçalho do módulo. Aceita só as chaves
    canônicas do :func:`mascaras_validas`, sem espaço e sem caixa; qualquer
    outra coisa (``None``, número, ``"banana"``, ``"xbox 360"``) devolve
    ``None``, e quem chamou decide o que fazer com a recusa. O que esta função
    JAMAIS faz é escolher uma máscara por conta própria.
    """
    if not isinstance(valor, str):
        return None
    chave = valor.strip().lower()
    return chave if chave in mascaras_validas() else None


class ExternalMaskRegistry:
    """Identidade de aparelho externo → máscara escolhida para ele.

    Leitura e escrita são puras sobre um arquivo próprio; nada aqui enumera
    ``/dev/input``, abre ``hidraw`` ou fala com o kernel. É o que permite testar
    a entrega inteira **sem aparelho nenhum** — e é também o que a mantém dentro
    da `E1`: a adoção dos externos (dar-lhes gamepad virtual) é a `E3`, e ela
    vem depois.

    A chave é a que o projeto já usa para NUMERAR o externo:
    :func:`~...external_identity.identity_for_entry`, canonizada pela MESMA
    função da fila (``ExternalIdentityRegistry._canonical``). Recalcular por
    conta própria é como duas camadas divergem — e aí a máscara ficaria
    pendurada num aparelho e o número noutro.

    Thread-safety: ``RLock`` de instância (o tick do daemon e a rota IPC rodam
    em threads diferentes) + :data:`MASKS_FILE_LOCK` de módulo em volta do
    read→``os.replace``. Nunca chama o registro de identidade segurando o
    próprio lock — não há consulta cruzada aqui, e não deve passar a haver.
    """

    def __init__(self) -> None:
        self._lock = threading.RLock()
        #: identidade canônica → máscara. Só quem é MAC de HARDWARE chega ao
        #: disco; volátil vive aqui e morre com o processo (limite 1).
        self._mascaras: dict[str, str] = {}
        #: Subconjunto de ``_mascaras`` com identidade VOLÁTIL — a lista do que
        #: o save tem de pular. Espelha ``ExternalIdentityRegistry._volatile``.
        self._volateis: set[str] = set()
        self._loaded = False
        #: Arquivo de versão que não é a nossa: não se lê e **não se
        #: sobrescreve**. Escolha de alguém não se destrói para registrar outra.
        self._somente_leitura = False

    # -- chave -------------------------------------------------------------

    @staticmethod
    def _key(identity: str | None) -> tuple[str, bool] | None:
        """``(chave canônica, persistível)`` da identidade, ou ``None``.

        Delega a ``ExternalIdentityRegistry._canonical`` — a MESMA função que a
        fila usa — em vez de repetir a regra do MAC. O precedente de chamar o
        método privado do irmão já existe na árvore
        (``ExternalImuEnabler.tick``, ``external_identity.py:893``), e é
        deliberado: uma segunda implementação da canonização é uma segunda
        chance de a máscara e o número discordarem sobre quem é o aparelho.
        """
        if not identity or not isinstance(identity, str):
            return None
        chave, persistivel = ExternalIdentityRegistry._canonical(identity)
        if not chave:
            return None
        return chave, persistivel

    # -- leitura -----------------------------------------------------------

    def mask_for(self, identity: str | None) -> str | None:
        """A máscara deste aparelho, ou ``None`` = *"como ele mesmo"*.

        Leitura PURA: nunca escreve no disco, nunca cria entrada. Identidade
        vazia, malformada ou desconhecida devolve ``None`` — e ``None`` aqui não
        é erro, é a resposta honesta *"este controle aparece como ele mesmo"*.
        """
        par = self._key(identity)
        if par is None:
            return None
        with self._lock:
            self._load_locked()
            return self._mascaras.get(par[0])

    def mask_for_entry(self, entry: dict[str, Any]) -> str | None:
        """:meth:`mask_for` a partir de uma entrada do inventário de externos.

        Atalho para o consumidor não ter de lembrar de chamar
        :func:`~...external_identity.identity_for_entry` — que é justamente o
        passo cuja omissão faria a máscara ser procurada por uma chave diferente
        da que numera o aparelho.
        """
        return self.mask_for(identity_for_entry(entry))

    def snapshot(self) -> dict[str, str]:
        """Cópia do mapa identidade → máscara (presentes e ausentes). Pura."""
        with self._lock:
            self._load_locked()
            return dict(self._mascaras)

    # -- escrita -----------------------------------------------------------

    def set_mask(self, identity: str | None, flavor: object) -> bool:
        """Registra a máscara deste aparelho. ``True`` se ficou registrada.

        Recusa (``False``, e **nada muda**) quando a identidade não resolve ou
        quando ``flavor`` não é uma máscara válida. A recusa é explícita de
        propósito: um valor inválido tratado como "limpar" apagaria a escolha
        dela em silêncio, que é o mesmo defeito de um valor inválido virar
        "xbox" — só que do outro lado. Quem quer *"como ele mesmo"* chama
        :meth:`clear_mask`, e diz isso com todas as letras.

        Persiste na hora, quando a identidade é MAC de HARDWARE: é gesto dela,
        não estado de sessão, e não pode esperar um tick que talvez não venha.
        """
        par = self._key(identity)
        if par is None:
            logger.warning("external_mascara_recusada_identidade", identidade=identity)
            return False
        chave, persistivel = par
        mascara = normalizar_mascara(flavor)
        if mascara is None:
            logger.warning(
                "external_mascara_recusada_valor",
                identidade=chave,
                valor=str(flavor),
                validas=sorted(mascaras_validas()),
            )
            return False
        with self._lock:
            self._load_locked()
            anterior = self._mascaras.get(chave)
            self._mascaras[chave] = mascara
            if persistivel:
                self._volateis.discard(chave)
            else:
                self._volateis.add(chave)
            logger.info(
                "external_mascara_definida",
                identidade=chave,
                mascara=mascara,
                anterior=anterior,
                volatil=not persistivel,
            )
            if persistivel and anterior != mascara:
                self._save_locked()
            return True

    def clear_mask(self, identity: str | None) -> bool:
        """Volta este aparelho para *"como ele mesmo"*. ``True`` se havia algo.

        Remover a entrada é a forma canônica de dizer "sem máscara": não existe
        valor no arquivo para "nenhuma" (ver :func:`mascaras_validas`).
        """
        par = self._key(identity)
        if par is None:
            return False
        chave, persistivel = par
        with self._lock:
            self._load_locked()
            anterior = self._mascaras.pop(chave, None)
            volatil = chave in self._volateis
            self._volateis.discard(chave)
            if anterior is None:
                return False
            logger.info(
                "external_mascara_removida", identidade=chave, anterior=anterior
            )
            if persistivel and not volatil:
                self._save_locked()
            return True

    # -- persistência ------------------------------------------------------

    def load(self) -> None:
        """Carrega o arquivo (idempotente).

        Público por paridade com o irmão, mas **não é obrigatório**: todo
        método aqui chama :meth:`_load_locked` antes de responder. O registro
        ainda não tem fiação no daemon — a `E1` entrega o registro, e quem o
        consome é a `E3`/`E4` —, e um registro que só carrega se alguém lembrar
        de mandar carregar é um registro que responde *"sem máscara"* para uma
        escolha que está no disco. Esse é exatamente o modo de falhar que esta
        entrega existe para impedir.
        """
        with self._lock:
            self._load_locked()

    @staticmethod
    def _path() -> Path:
        """Path do arquivo de máscaras — import LAZY (monkeypatch dos testes)."""
        from hefesto_dualsense4unix.utils.xdg_paths import config_dir

        return config_dir(ensure=True) / _MASKS_FILE

    @classmethod
    def _ler_documento(cls) -> dict[str, Any] | None:
        """O JSON do disco quando ele é um objeto; ``None`` em qualquer outro caso.

        Ausente, ilegível, truncado ou não-objeto devolvem ``None`` — e ``None``
        autoriza a escrita (não há escolha de ninguém a destruir num arquivo que
        já não diz nada). Quem barra a escrita é a VERSÃO, checada por quem
        chama.
        """
        try:
            with cls._path().open(encoding="utf-8") as fh:
                bruto = json.load(fh)
        except (FileNotFoundError, json.JSONDecodeError, OSError):
            return None
        except Exception as exc:  # defensivo — leitura jamais derruba o daemon
            logger.debug("external_mascaras_load_falhou", err=str(exc))
            return None
        return bruto if isinstance(bruto, dict) else None

    def _load_locked(self) -> None:
        """Restaura as máscaras do disco, uma vez por instância (sob ``_lock``)."""
        if self._loaded:
            return
        self._loaded = True
        with MASKS_FILE_LOCK:
            data = self._ler_documento()
        if data is None:
            return
        versao = data.get(VERSION_FIELD)
        if versao != MASKS_SCHEMA_VERSION:
            self._somente_leitura = True
            logger.warning(
                "external_mascaras_schema_desconhecido",
                versao_arquivo=versao,
                versao_atual=MASKS_SCHEMA_VERSION,
            )
            return
        bruto = data.get(MASKS_FIELD)
        if not isinstance(bruto, list):
            return
        for item in bruto:
            if not isinstance(item, dict):
                continue
            par = self._key(item.get(IDENTITY_FIELD))
            if par is None:
                continue
            chave, persistivel = par
            if not persistivel:
                # Só pode ter chegado ao disco por uma versão futura ou por
                # edição à mão: identidade volátil nunca é gravada daqui.
                logger.info(
                    "external_mascara_nao_persistivel_descartada", identidade=chave
                )
                continue
            mascara = normalizar_mascara(item.get(FLAVOR_FIELD))
            if mascara is None:
                logger.warning(
                    "external_mascara_invalida_descartada",
                    identidade=chave,
                    valor=str(item.get(FLAVOR_FIELD)),
                )
                continue
            self._mascaras.setdefault(chave, mascara)
        if self._mascaras:
            logger.info(
                "external_mascaras_restauradas", mascaras=dict(self._mascaras)
            )

    def _save_locked(self) -> None:
        """Read-modify-write atômico do arquivo de máscaras (sob ``_lock``).

        Preserva o que não entende — chaves de TOPO e campos POR ENTRADA
        escritos por uma versão futura. É a lição do ``identity.py:951``
        (``payload = {}`` do zero) aplicada contra nós mesmos: quem monta o
        documento do zero destrói o que o outro escritor sabia.

        Versão diferente da nossa **aborta a escrita** e tranca o registro em
        somente-leitura. Nunca propaga exceção: perder um save custa escolher a
        máscara de novo; derrubar o tick do daemon custa a mesa inteira.
        """
        if self._somente_leitura:
            logger.warning("external_mascaras_save_recusado_schema_desconhecido")
            return
        try:
            with MASKS_FILE_LOCK:
                data = self._ler_documento()
                extras_por_entrada: dict[str, dict[str, Any]] = {}
                documento: dict[str, Any] = {}
                if data is not None:
                    if data.get(VERSION_FIELD) != MASKS_SCHEMA_VERSION:
                        self._somente_leitura = True
                        logger.warning(
                            "external_mascaras_save_recusado_schema_desconhecido",
                            versao_arquivo=data.get(VERSION_FIELD),
                        )
                        return
                    documento = {
                        campo: valor
                        for campo, valor in data.items()
                        if campo not in (VERSION_FIELD, MASKS_FIELD)
                    }
                    extras_por_entrada = self._extras_por_entrada(data)
                documento[VERSION_FIELD] = MASKS_SCHEMA_VERSION
                documento[MASKS_FIELD] = [
                    {
                        **extras_por_entrada.get(chave, {}),
                        IDENTITY_FIELD: chave,
                        FLAVOR_FIELD: self._mascaras[chave],
                    }
                    for chave in sorted(self._mascaras)
                    if chave not in self._volateis
                ]
                self._escrever(documento)
                logger.debug(
                    "external_mascaras_salvas", total=len(documento[MASKS_FIELD])
                )
        except Exception as exc:
            logger.debug("external_mascaras_save_falhou", err=str(exc))

    @classmethod
    def _extras_por_entrada(cls, data: dict[str, Any]) -> dict[str, dict[str, Any]]:
        """Campos que NÃO são nossos, por identidade canônica, do documento lido."""
        extras: dict[str, dict[str, Any]] = {}
        bruto = data.get(MASKS_FIELD)
        if not isinstance(bruto, list):
            return extras
        for item in bruto:
            if not isinstance(item, dict):
                continue
            par = cls._key(item.get(IDENTITY_FIELD))
            if par is None:
                continue
            sobra = {
                campo: valor
                for campo, valor in item.items()
                if campo not in (IDENTITY_FIELD, FLAVOR_FIELD)
            }
            if sobra:
                extras.setdefault(par[0], sobra)
        return extras

    @classmethod
    def _escrever(cls, documento: dict[str, Any]) -> None:
        """``os.replace`` de um temporário no MESMO diretório (troca atômica)."""
        path = cls._path()
        payload = json.dumps(documento, ensure_ascii=False)
        fd, tmp = tempfile.mkstemp(
            dir=os.path.dirname(os.fspath(path)), prefix=".controller_masks_"
        )
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


__all__ = [
    "FLAVOR_FIELD",
    "IDENTITY_FIELD",
    "MASKS_FIELD",
    "MASKS_FILE_LOCK",
    "MASKS_SCHEMA_VERSION",
    "VERSION_FIELD",
    "ExternalMaskRegistry",
    "mascaras_validas",
    "normalizar_mascara",
]
