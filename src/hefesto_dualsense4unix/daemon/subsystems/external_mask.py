"""Máscara por APARELHO — de CADA controle, externo ou DualSense (MÁSCARA-01/E1).

*"Como este controle deve aparecer nos jogos?"* — a escolha é de CADA controle,
e desde 08/09/2026 ela mora no **perfil**.

Este módulo é **o registro e a regra de herança**: onde a escolha mora enquanto
o daemon roda, como ela sobrevive ao reboot, o que ela NÃO promete, e — desde
15/08/2026 — qual máscara um jogador recebe quando não escolheu nenhuma. Ele não
adota externo, não cria gamepad virtual, não esconde ninguém do jogo e não
desenha tela — isso é a `E2`/`E3`/`E4` da MÁSCARA-01 e a `E3` da
LUGAR-À-MESA-01, que o usuário autorizou **depois** desta.

O DONO DA MÁSCARA É O PERFIL — DESDE 08/09/2026
------------------------------------------------

**NOTA DATADA — 08/09/2026 (MASCARA-NO-PERFIL-01).** A pergunta foi *"a máscara
por controle deve entrar no perfil, junto com luz, gatilho, vibração, som, mic e
sensores — ou fica da máquina?"*; a resposta de produto foi *"pode entrar sim"*. O
campo é ``profiles.schema.ControllerOverrides.mascara``, e quem o escreve aqui é
``profiles.manager.apply_controller_mascaras``, a cada ativação de perfil.

**FATO SUBSTITUÍDO.** O cabeçalho deste módulo dizia que *"a escolha é do
aparelho, não da configuração de jogo"* e que ela não podia morar no perfil
porque *"cada troca automática de perfil — cada alt-tab — faria o controle sumir
e voltar no meio da partida"*. A primeira metade caiu por decisão de produto; a
segunda **continua medida e não some**: trocar a máscara derruba e recria o
vpad. O que a torna suportável é que ninguém repinta quem não mudou —
``apply_controller_mascaras`` escreve peça a peça e :func:`vpad_ficou_para_tras`
compara antes de derrubar, então um perfil que repete a máscara de um jogador
não o faz sumir. A sprint que fechou a porta velha é
a sprint `MASCARA-01`
(seção *"Onde a máscara mora"*), e o que valia lá vale só até esta nota.

**O QUE ESTE REGISTRO É AGORA: um CACHE do perfil ativo, não o dono.** Ele
continua existindo por uma razão medida, e não por inércia — ``mascara_efetiva``
é consultada na criação de todo vpad **e no tique do co-op**, que compara para
decidir recriar; ler o perfil do disco ali seria a tempestade de syscalls que o
``gamepad._motores_do_perfil_ativo`` já pagou uma vez. Quem grava o gesto do usuário
(``gamepad.mask.set``) escreve nos DOIS: no perfil ativo, que é o dono, e aqui,
para valer agora.

A CONSEQUÊNCIA PARA QUEM LER ESTE ARQUIVO NO DISCO: uma entrada de
``controller_masks.json`` que o perfil ativo não repita **não sobrevive à
próxima ativação** — ela é apagada por :meth:`ExternalMaskRegistry.manter_somente`,
e aquele controle volta ao padrão. Não é escolha perdida, e não é dado a
defender. Apagar o arquivo com o daemon parado também não muda máscara nenhuma
de quem o perfil declara: a próxima ativação o reescreve.

**PERFIL CALADO DEVOLVE AO PADRÃO — DECISÃO, 09/09/2026.** A pergunta
aberta na entrega de 08/09 era *"um perfil que não fala de máscara devolve todo
mundo ao padrão, ou deixa cada um como está?"*; a resposta de produto foi *"Default é
Hefesto dualsense padrão"*. Nesta seção — e só nesta — ``None`` no perfil não é
*"sem opinião"*: é *"volte ao padrão"*. O padrão é o degrau de baixo desta
ordem, ou seja o ``mode.gamepad_flavor`` do perfil e, na falta dele, o
``DaemonConfig.gamepad_flavor``, que de fábrica é ``dualsense``.

DE QUEM É A MÁSCARA — DO JOGADOR, DESDE 15/08/2026
---------------------------------------------------

**NOTA DATADA — 15/08/2026 (MÁSCARA-POR-JOGADOR-01).** Até aqui este registro
não tinha chamador nenhum em ``src/``, e a razão estava escrita em
``profiles/schema.py``: *"``mode`` e a máscara do gamepad são da SESSÃO, não da
peça"* (decisão, 10/08/2026). **Ela reescreveu essa frase em 15/08/2026**:
vale só para o ``mode``. A máscara passa a ser **do jogador**, com a máscara do
jogo como **padrão herdado** — quem não escolheu nada segue o jogo, exatamente
como um campo em branco de ``ControllerOverrides`` herda a seção global.

A medição que separou os dois casos (documento
a sprint `MASCARA-POR-JOGADOR-01`): o ``mode`` é
estado do PROCESSO — existe um só e duas unidades pedindo modos diferentes não
têm resposta. A máscara **já tem um lugar por jogador**: o co-op cria um gamepad
virtual por controle e cada um carrega o próprio ``flavor``.

**A chave serve ao DualSense também, e sempre serviu.** O módulo nasceu para os
externos, mas :meth:`ExternalMaskRegistry._key` delega a
``ExternalIdentityRegistry._canonical``, que canoniza **qualquer** MAC de
hardware; e ``core.evdev_reader.discover_dualsense_evdevs`` — a função que o
co-op usa para achar cada jogador — já devolve exatamente esse MAC normalizado.
Nada precisou mudar no armazenamento: o que mudou foi **quem pergunta**.

O QUE AINDA NÃO CHEGA AQUI (MEDIDO em 15/08/2026)
--------------------------------------------------

:func:`mascara_efetiva` é consultada na criação de todo gamepad virtual
(``uinput_gamepad.UinputGamepad.for_flavor`` e
``uhid_gamepad.UhidDualSense.for_flavor``), mas ela só tem o que responder
quando recebe uma ``identity``. **Hoje ninguém a passa**: os três degraus que
faltam moram fora deste módulo —
``integrations/virtual_pad.make_virtual_pad`` (repassar o parâmetro),
``daemon/subsystems/coop.py`` (o MAC do jogador na criação e o
:func:`vpad_ficou_para_tras` no laço de recriação) e
``daemon/subsystems/gamepad.py`` (o MAC do primário). Enquanto isso não chega,
o comportamento é **idêntico ao de antes** — máscara única, a do jogo —, o que é
de propósito: meia cura que muda comportamento é pior que nenhuma.

**A armadilha do primeiro degrau, para quem for escrevê-lo:**
``make_virtual_pad`` tem de resolver a máscara efetiva **ANTES** de escolher o
backend, e passar o resultado ao ``_try_uhid``. O gate de lá usa a máscara que recebe: se ele
continuar recebendo a do
JOGO, um jogador que escolheu ``dualsense`` numa sessão ``xbox`` tem o uhid
vetado e cai no ``uinput`` com máscara DualSense — que é o par degradado onde a
vibração do jogo morre (VPAD-05/SPRINT-GAME-RUMBLE-01). A resolução é
idempotente (``mascara_efetiva`` de uma máscara já efetiva devolve ela mesma),
então resolver na factory e repassar a ``identity`` aos dois backends é seguro.

Falta também o **lado da escrita**: quem grava a escolha do usuário é a rota IPC
(``daemon/ipc_handlers.py``), que ainda só conhece a máscara da sessão.

RISCO NÃO MEDIDO — CONTROLES HETEROGÊNEOS NA MESMA SESSÃO
----------------------------------------------------------

**NINGUÉM MEDIU** se um jogo aceita dois vpads com máscaras diferentes ao mesmo
tempo (dois vistos como Xbox 360 e dois como DualSense). É plausível que o jogo
enxergue os quatro sem reclamar — são quatro devices distintos, como sempre
foram —, e é igualmente plausível que a camada de entrada dele (Steam Input, o
``gamecontrollerdb`` da SDL, ou um motor que escolhe UM esquema de prompts para
a partida inteira) troque prompts, embaralhe a ordem dos jogadores ou ignore o
que destoa. **Não prometa que funciona.**

O que mediria, e cabe numa sessão com a mesa cheia: quatro controles, um jogo
com Steam Input aberto, P1 em ``dualsense`` e P2 em ``xbox`` — e então olhar
três coisas, nesta ordem: (1) os quatro jogadores continuam existindo no jogo;
(2) os prompts de cada um saem na máscara dele, e não na do P1; (3) o rumble
chega nos quatro. Qualquer resposta "não" transforma a escolha por jogador num
recurso com aviso na tela, não num defeito a caçar no nosso lado.

O ARQUIVO É PRÓPRIO, E NÃO É UM BUMP DO ``controllers.json``
-----------------------------------------------------------

*(Continua valendo para ONDE o cache mora — o que mudou em 08/09/2026 é quem
manda nele, e está na nota acima.)*

A sprint de 25/07 pedia *"registro de identidade, no mesmo arquivo que já guarda
a ordem de preferência, com versão de esquema nova"*. Isso **caducou em
07/08/2026** — ver a nota datada na própria sprint. Quatro fatos MEDIDOS na
árvore fecham aquela porta, e os quatro estão registrados na
``REGRA-NAO-REGISTRO-01``:

1. ``identity.load`` (``identity.py:1566``) DESCARTA a fila inteira quando a
   versão do arquivo difere — um bump renumeraria a bancada;
2. ``identity._save_locked`` só aproveita as entradas do outro lado quando
   ``bruto.get("version") == CONTROLLERS_SCHEMA_VERSION`` (``:2170-2174``): o
   primeiro save de DualSense depois de um bump APAGARIA a fila dos externos;
3. ``payload: dict[str, Any] = {}`` é montado do zero (``identity.py:1537``) —
   chave nova de topo escrita pelo lado externo morre no primeiro save do outro;
4. ``merged_order_payload`` devolve exatamente ``{addr, kind, rank}``
   (``:555``) e ``order_entries`` descarta ``kind`` desconhecido (``:521``) —
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
*"exige Xbox"* e apagava giroscópio e touchpad no jogo do usuário sem que ninguém
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
from collections.abc import Iterable
from pathlib import Path
from typing import Any

from hefesto_dualsense4unix.daemon.subsystems.external_identity import (
    ExternalIdentityRegistry,
    identity_for_entry,
)
from hefesto_dualsense4unix.integrations.uinput_gamepad import (
    FLAVORS,
    normalize_flavor,
)
from hefesto_dualsense4unix.utils.logging_config import get_logger

logger = get_logger(__name__)

_MASKS_FILE = "controller_masks.json"

MASKS_SCHEMA_VERSION = 1

VERSION_FIELD = "version"
MASKS_FIELD = "masks"
IDENTITY_FIELD = "identity"
FLAVOR_FIELD = "flavor"

MASKS_FILE_LOCK = threading.Lock()


def mascaras_validas() -> frozenset[str]:
    """Os valores que uma máscara pode ter — o catálogo do vpad, não uma cópia."""
    return frozenset(FLAVORS)


def normalizar_mascara(valor: object) -> str | None:
    """A máscara canônica de ``valor``, ou ``None`` quando não há uma."""
    if not isinstance(valor, str):
        return None
    chave = valor.strip().lower()
    return chave if chave in mascaras_validas() else None


class ExternalMaskRegistry:
    """Identidade de aparelho externo → máscara escolhida para ele."""

    def __init__(self) -> None:
        self._lock = threading.RLock()
        self._mascaras: dict[str, str] = {}
        self._volateis: set[str] = set()
        self._loaded = False
        self._somente_leitura = False


    @staticmethod
    def _key(identity: str | None) -> tuple[str, bool] | None:
        """``(chave canônica, persistível)`` da identidade, ou ``None``."""
        if not identity or not isinstance(identity, str):
            return None
        chave, persistivel = ExternalIdentityRegistry._canonical(identity)
        if not chave:
            return None
        return chave, persistivel


    def mask_for(self, identity: str | None) -> str | None:
        """A máscara deste aparelho, ou ``None`` = *"como ele mesmo"*."""
        par = self._key(identity)
        if par is None:
            return None
        with self._lock:
            self._load_locked()
            return self._mascaras.get(par[0])

    def mask_for_entry(self, entry: dict[str, Any]) -> str | None:
        """:meth:`mask_for` a partir de uma entrada do inventário de externos."""
        return self.mask_for(identity_for_entry(entry))

    def snapshot(self) -> dict[str, str]:
        """Cópia do mapa identidade → máscara (presentes e ausentes). Pura."""
        with self._lock:
            self._load_locked()
            return dict(self._mascaras)


    def set_mask(self, identity: str | None, flavor: object) -> bool:
        """Registra a máscara deste aparelho. ``True`` se ficou registrada."""
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
        """Volta este aparelho para *"como ele mesmo"*. ``True`` se havia algo."""
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

    def manter_somente(self, identidades: Iterable[str | None]) -> tuple[str, ...]:
        """Só estas ficam com máscara própria; TODA outra volta ao padrão."""
        manter: set[str] = set()
        for identidade in identidades:
            par = self._key(identidade)
            if par is not None:
                manter.add(par[0])
        with self._lock:
            self._load_locked()
            sobrando = tuple(
                chave for chave in sorted(self._mascaras) if chave not in manter
            )
            if not sobrando:
                return ()
            persistiu = False
            for chave in sobrando:
                anterior = self._mascaras.pop(chave, None)
                if chave in self._volateis:
                    self._volateis.discard(chave)
                else:
                    persistiu = True
                logger.info(
                    "external_mascara_devolvida_ao_padrao",
                    identidade=chave,
                    anterior=anterior,
                )
            if persistiu:
                self._save_locked()
            return sobrando


    def load(self) -> None:
        """Carrega o arquivo (idempotente)."""
        with self._lock:
            self._load_locked()

    @staticmethod
    def _path() -> Path:
        """Path do arquivo de máscaras — import LAZY (monkeypatch dos testes)."""
        from hefesto_dualsense4unix.utils.xdg_paths import config_dir

        return config_dir(ensure=True) / _MASKS_FILE

    @classmethod
    def _ler_documento(cls) -> dict[str, Any] | None:
        """O JSON do disco quando ele é um objeto; ``None`` em qualquer outro caso."""
        try:
            with cls._path().open(encoding="utf-8") as fh:
                bruto = json.load(fh)
        except (FileNotFoundError, json.JSONDecodeError, OSError):
            return None
        except Exception as exc:
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
        """Read-modify-write atômico do arquivo de máscaras (sob ``_lock``)."""
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


_REGISTRO: ExternalMaskRegistry | None = None

_REGISTRO_LOCK = threading.Lock()


def registro_de_mascaras() -> ExternalMaskRegistry:
    """O registro de máscaras do processo — sempre o mesmo objeto."""
    global _REGISTRO
    if _REGISTRO is None:
        with _REGISTRO_LOCK:
            if _REGISTRO is None:
                _REGISTRO = ExternalMaskRegistry()
    return _REGISTRO


def _zerar_registro_de_mascaras() -> None:
    """Descarta a instância viva. **Só para teste** — nada em produção chama."""
    global _REGISTRO
    with _REGISTRO_LOCK:
        _REGISTRO = None


def mascara_efetiva(identity: str | None, flavor_do_jogo: object) -> str:
    """A máscara DESTE aparelho: a que ele escolheu ou, sem escolha, a do jogo.

    **A ORDEM DE DECISÃO DA MÁSCARA TERMINA AQUI** (MASCARA-NO-PERFIL-01,
    08/09/2026). Três degraus, nesta ordem:

    1. ``controllers[uniq].mascara`` **do perfil ativo**;
    2. ``mode.gamepad_flavor`` do perfil — é o que chega em ``flavor_do_jogo``,
       pela config do daemon;
    3. o padrão, quando nem um nem outro disse nada.

    NOTA DATADA NO DEGRAU 2 — MODO-DE-CONEXAO-01, 13/09/2026. O degrau continua
    LIDO, e deixou de ser ESCRITO pelo modo: até aqui o chip de modo da aba
    Jogar e o PS + R3 mandavam a máscara (`gamepad.emulation.set {flavor}`) e
    gravavam ``mode.gamepad_flavor`` — e por isso o chip «Xbox» dizia
    «aplicado» sem mudar nada quando o cartão tinha máscara, porque o degrau 1
    vence este. O modo agora é o CAMINHO (``mode.caminho``), um eixo à parte.

    **CORREÇÃO DE FATO — 09/09/2026.** Esta docstring dizia *"a ordem mora
    AQUI"*, e isso é falso pela metade que mais importa: **esta função não
    executa o degrau 1.** Ela lê o registro, que é um CACHE — quem executa o
    degrau 1 é ``profiles.manager.apply_controller_mascaras``, escrevendo no
    cache a cada ativação de perfil (e apagando dele quem o perfil não declara),
    e o ``gamepad.mask.set`` no gesto do usuário. O que esta função executa são os
    degraus 2 e 3, e o que ela faz com o degrau 1 é **honrar o que já foi
    aplicado**: entrada no registro vence ``flavor_do_jogo``, sem exceção.

    Quem quiser saber se a ordem continua de pé não lê esta prosa: mede o
    comportamento, degrau a degrau, em
    ``tests/unit/test_a_mascara_mora_no_perfil.py``. Uma régua que só procurasse
    estas palavras aqui passaria com a ordem trocada no código — foi o que ela
    fazia até 09/09/2026.

    É a regra de herança da **D-5** (14/08/2026), respondida por ela em
    15/08/2026: *máscara do JOGADOR, com a do jogo como padrão herdado*. Sem
    entrada no registro não existe "sem máscara" — existe **a máscara do jogo**,
    que é o valor que o produto sempre teve. Por isso ninguém precisa escolher
    por jogador para nada mudar, e é isso que torna o recurso seguro diante do
    risco não medido do cabeçalho deste módulo.

    ``flavor_do_jogo`` passa pelo ``normalize_flavor``, que é TOLERANTE: este é
    caminho interno (config de disco, tick do co-op), e um
    caminho interno precisa de uma máscara sempre. Quem valida gesto de gente é
    o portão do IPC, com o ``resolver_flavor`` estrito. A escolha do APARELHO,
    essa, já chegou aqui validada — ``set_mask`` recusa o que
    :func:`normalizar_mascara` não reconhece.
    """
    escolhida = registro_de_mascaras().mask_for(identity)
    if escolhida is not None:
        return escolhida
    if isinstance(flavor_do_jogo, str):
        return normalize_flavor(flavor_do_jogo)
    return normalize_flavor(None)


def mesma_identidade(a: str | None, b: str | None) -> bool:
    """Os dois endereços são o MESMO aparelho? Pela chave canônica do registro.

    MODO-DE-CONEXAO-01 (13/09/2026): o `gamepad.mask.set` recebe o `uniq` que a
    tela manda, e o daemon conhece o P1 pelo `primary_uniq` do backend. Comparar
    as strings cruas faria `AA:BB:…` e `aabb…` serem dois controles — a mesma
    canonização que numera e mascara (`ExternalMaskRegistry._key`) responde.
    """
    chave_a = ExternalMaskRegistry._key(a)
    chave_b = ExternalMaskRegistry._key(b)
    return chave_a is not None and chave_b is not None and chave_a[0] == chave_b[0]


def vpad_ficou_para_tras(
    flavor_do_vpad: object,
    identity: str | None,
    flavor_do_jogo: object,
    *,
    vpad: object = None,
    caminho: object = None,
) -> bool:
    """O gamepad virtual deste jogador está com a máscara ERRADA? (recriá-lo)

    Esta função existe para que a máscara por jogador **não atropele uma cura
    medida**. O laço de ``daemon/subsystems/coop.py`` derruba e recria todo vpad
    cujo ``flavor`` divirja do desejado, e isso não é descuido: sem ele, os
    jogadores 2+ ficam **presos no flavor antigo** quando a máscara muda em
    runtime — rumble morto e prompts divergentes do P1 (SPRINT-GAME-RUMBLE-01,
    comentário de ``coop.py``).

    A cura força a IGUALDADE; a decisão de produto pede que a DIFERENÇA seja
    respeitada. As duas cabem juntas porque o alvo da comparação deixa de ser um
    valor e passa a ser uma **função do aparelho**:

    - **divergência escolhida** — o registro tem máscara para esta identidade e
      o vpad já está nela. ``mascara_efetiva`` devolve a escolhida, a comparação
      dá igual, e o vpad **sobrevive** mesmo destoando de todos os outros;
    - **flavor que ficou para trás** — a máscara deste aparelho mudou (a dele ou
      a do jogo que ele herda) e o vpad nasceu na anterior. A comparação dá
      diferente e o vpad é **recriado**, que é exatamente o que a cura fazia.

    O que NÃO é caso desta função: um vpad sem ``flavor`` legível
    (``None``/dublê) conta como ficado para trás, como já contava — a comparação
    do co-op sempre foi contra ``getattr(vpad, "flavor", None)``.

    E O CANAL TAMBÉM — MODO-DE-CONEXAO-01, 13/09/2026. O modo de conexão deixou
    de ser a máscara: com a mesma máscara, o caminho Xbox é o vpad `uinput` e o
    DualSense é o `uhid`. Quando o chamador passa o ``vpad`` e o ``caminho``
    pedido, um vpad no canal errado também ficou para trás. A comparação é
    pelo CANAL (:func:`~hefesto_dualsense4unix.integrations.virtual_pad.quer_uhid`),
    e não pelo nome do caminho: com máscara Xbox 360 os dois caminhos dão o
    mesmo aparelho, e recriá-lo seria arrancar o controle do jogo por nada. Um
    vpad que caiu no `uinput` por falta de `uhid` nasceu com o caminho
    DualSense pendurado, e por isso não entra em laço de recriação.
    """
    mascara = mascara_efetiva(identity, flavor_do_jogo)
    if flavor_do_vpad != mascara:
        return True
    if vpad is None:
        return False
    from hefesto_dualsense4unix.integrations.virtual_pad import (
        caminho_do_vpad,
        o_aparelho_mudou,
        quer_uhid,
    )

    return quer_uhid(caminho_do_vpad(vpad), mascara) != quer_uhid(
        caminho, mascara
    ) or o_aparelho_mudou(vpad, caminho, mascara)


def mascara_vestida(daemon: Any, uniq: str | None = None) -> str | None:
    """A máscara que o vpad DAQUELE aparelho veste AGORA — `None` sem vpad."""
    primario = getattr(daemon, "_gamepad_device", None)
    if uniq is None or mesma_identidade(uniq, _identidade_do_primario(daemon)):
        flavor = getattr(primario, "flavor", None)
        return flavor if isinstance(flavor, str) and flavor else None
    players = getattr(getattr(daemon, "_coop_manager", None), "_players", None)
    if isinstance(players, dict):
        for chave, player in players.items():
            if not mesma_identidade(uniq, str(chave)):
                continue
            flavor = getattr(getattr(player, "vpad", None), "flavor", None)
            return flavor if isinstance(flavor, str) and flavor else None
    return None


def _identidade_do_primario(daemon: Any) -> str | None:
    """O endereço do jogador 1, sem arrastar o `gamepad` para o import."""
    return getattr(getattr(daemon, "controller", None), "primary_uniq", None)


_SEM_STORE = object()


def escolher_a_mascara(
    daemon: Any, uniq: str, flavor: object, *, store: Any = _SEM_STORE
) -> dict[str, Any]:
    """A ESCOLHA DE MÁSCARA DE UM APARELHO — o ato, num lugar só.

    TROCA-DENTRO-DO-JOGO-01 (14/09/2026). O chip do cartão da aba Jogar e o
    gesto PS + L3 fazem a MESMA coisa, e agora pela mesma porta: até aqui o chip
    entrava pelo handler do socket (`gamepad.mask.set`) e o gesto alcançava esse
    handler privado por `daemon._ipc_server._handle_gamepad_mask_set` — um
    método achado por string, num atributo sem tipo. A casa já tinha recusado
    isso em 13/09, quando a regra de em que perfil gravar saiu do handler
    porque *"o gesto não passa pelo handler"* (`profiles/manager.py`).

    A ORDEM É O CONTRATO, e ela mudou — é a do modo, que se grava só depois de o
    aparelho trocar (`Daemon.gravar_o_modo_escolhido`):

    1. **o registro vivo** recebe a escolha, porque é dele que a fábrica do vpad
       lê a máscara ao nascer (`mascara_efetiva`). Sem esta escrita ANTES, não
       há como o aparelho vestir o que o usuário pediu;
    2. **o aparelho veste** (`Daemon.vestir_a_mascara_do_aparelho`);
    3. **o perfil ativo** guarda — SÓ SE o aparelho concordou. Antes o perfil já
       tinha a máscara nova quando a barra de luz ainda dizia falha, e a aba
       Jogar acendia um chip que o jogo não estava vendo. Quando o aparelho
       recusa, o registro VOLTA para o que era: uma escolha que não pegou não
       fica pendurada esperando o próximo vpad.

    Sem vpad de pé (a Navegação) não há o que conferir, e a escolha vale para o
    próximo — é o que o usuário pediu em 13/09 ao escolher máscara com o Hefesto
    desligado.

    `flavor` vazio LIMPA a escolha (o aparelho volta a herdar a do perfil), como
    o campo em branco de `ControllerOverrides`.

    Devolve o mesmo dicionário que a rota `gamepad.mask.set` sempre devolveu.
    """
    from hefesto_dualsense4unix.profiles.manager import (
        chave_de_peca_que_grava,
        gravar_a_mascara_no_perfil_ativo,
        nome_do_perfil_que_grava,
    )

    alvo: str | None
    if flavor is None or str(flavor).strip() == "":
        alvo = None
    else:
        alvo = normalizar_mascara(flavor)
        if alvo is None:
            aceitos = ", ".join(sorted(mascaras_validas()))
            raise ValueError(
                f"gamepad.mask.set: máscara desconhecida {flavor!r} — "
                f"aceito: {aceitos}, ou vazio para herdar a do perfil"
            )

    registro = registro_de_mascaras()
    anterior = registro.mask_for(uniq)
    mudou = registro.clear_mask(uniq) if alvo is None else registro.set_mask(uniq, alvo)

    vestiu: str | None = None
    ato = getattr(daemon, "vestir_a_mascara_do_aparelho", None)
    if callable(ato):
        try:
            vestiu = str(ato(uniq))
        except Exception as exc:
            logger.warning("gamepad_mascara_nao_vestiu", uniq=uniq, err=str(exc))

    vestida = mascara_vestida(daemon, uniq)
    esperada = alvo if alvo is not None else vestida
    if vestida is not None and esperada is not None and vestida != esperada:
        if anterior is None:
            registro.clear_mask(uniq)
        else:
            registro.set_mask(uniq, anterior)
        logger.warning(
            "gamepad_mascara_recusada_pelo_aparelho",
            uniq=uniq, pedida=alvo, vestida=vestida, vestiu=vestiu,
        )
        return {"status": "ok", "uniq": uniq, "flavor": alvo, "mudou": False,
                "perfil": None, "gravado": False,
                "motivo": "aparelho_nao_vestiu", "vestiu": vestiu}

    dono = getattr(daemon, "store", None) if store is _SEM_STORE else store
    nome = nome_do_perfil_que_grava(getattr(dono, "active_profile", None))
    perfil, gravado, motivo = gravar_a_mascara_no_perfil_ativo(
        nome, chave=chave_de_peca_que_grava(uniq), mascara=alvo
    )
    return {"status": "ok", "uniq": uniq, "flavor": alvo, "mudou": bool(mudou),
            "perfil": perfil, "gravado": gravado, "motivo": motivo,
            "vestiu": vestiu}


__all__ = [
    "FLAVOR_FIELD",
    "IDENTITY_FIELD",
    "MASKS_FIELD",
    "MASKS_FILE_LOCK",
    "MASKS_SCHEMA_VERSION",
    "VERSION_FIELD",
    "ExternalMaskRegistry",
    "escolher_a_mascara",
    "mascara_efetiva",
    "mascara_vestida",
    "mascaras_validas",
    "mesma_identidade",
    "normalizar_mascara",
    "registro_de_mascaras",
    "vpad_ficou_para_tras",
]
