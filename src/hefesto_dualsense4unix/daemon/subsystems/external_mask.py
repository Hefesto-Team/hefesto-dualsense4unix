"""Máscara por APARELHO: a escolha de CADA controle, externo ou DualSense (MÁSCARA-01/E1).

O dono da escolha é o perfil (``ControllerOverrides.mascara``, aplicada por
``profiles.manager.apply_controller_mascaras``); este módulo é o CACHE em memória dela e a regra de
herança (``mascara_efetiva``, com a do jogo como padrão). Arquivo próprio, versão própria, nunca
um bump do ``controllers.json``; ``normalizar_mascara`` é estrita e nunca cai em ``xbox``.
Perfil calado devolve ao padrão. A história e o que o registro não promete:
``docs/research/o-porque-dos-modulos.md``, seção «external_mask».
"""
from __future__ import annotations

import contextlib
import json
import os
import tempfile
import threading
import time
from collections.abc import Iterable
from pathlib import Path
from typing import Any, NamedTuple

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

#: O sufixo da cópia do arquivo ilegível, guardada ao lado antes da primeira escrita.
SUFIXO_DO_ILEGIVEL = ".ilegivel-"


class _ArquivoIlegivelError(ValueError):
    """O arquivo de máscaras existe e não se lê como um objeto JSON."""

    def __init__(self, caminho: Path, motivo: str) -> None:
        super().__init__(f"{caminho}: {motivo}")
        self.caminho = caminho
        self.motivo = motivo


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
        """O JSON do disco quando ele é um objeto; ``None`` sem arquivo legível.

        O arquivo que existe e não se lê (JSON quebrado, bytes que não são texto,
        documento que não é objeto) levanta :class:`_ArquivoIlegivelError`: ele não vale
        como ausente, porque a escrita seguinte o apagaria.
        """
        caminho = cls._path()
        try:
            with caminho.open(encoding="utf-8") as fh:
                bruto = json.load(fh)
        except (FileNotFoundError, OSError):
            return None
        except ValueError as exc:
            raise _ArquivoIlegivelError(caminho, type(exc).__name__) from exc
        except Exception as exc:
            logger.debug("external_mascaras_load_falhou", err=str(exc))
            return None
        if not isinstance(bruto, dict):
            raise _ArquivoIlegivelError(caminho, f"documento {type(bruto).__name__}")
        return bruto

    @staticmethod
    def _guardar_o_ilegivel(caminho: Path) -> Path:
        """Move o arquivo ilegível para o lado (``<nome>.ilegivel-<data>``)."""
        base = f"{caminho.name}{SUFIXO_DO_ILEGIVEL}{time.strftime('%Y%m%d-%H%M%S')}"
        destino = caminho.with_name(base)
        n = 2
        while destino.exists():
            destino = caminho.with_name(f"{base}-{n}")
            n += 1
        os.replace(caminho, destino)
        logger.warning(
            "external_mascaras_ilegivel_guardado",
            caminho=str(caminho),
            guardado_em=str(destino),
        )
        return destino

    def _load_locked(self) -> None:
        """Restaura as máscaras do disco, uma vez por instância (sob ``_lock``)."""
        if self._loaded:
            return
        self._loaded = True
        try:
            with MASKS_FILE_LOCK:
                data = self._ler_documento()
        except _ArquivoIlegivelError as exc:
            logger.warning(
                "external_mascaras_ilegivel", caminho=str(exc.caminho), motivo=exc.motivo
            )
            return
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
                try:
                    data = self._ler_documento()
                except _ArquivoIlegivelError as exc:
                    try:
                        self._guardar_o_ilegivel(exc.caminho)
                    except OSError as erro:
                        logger.warning(
                            "external_mascaras_ilegivel_nao_guardado",
                            caminho=str(exc.caminho),
                            err=str(erro),
                        )
                        return
                    data = None
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
    """A escolha de máscara de um aparelho, num lugar só: o chip da aba Jogar e o PS + L3.

    A ordem é o contrato: o registro vivo recebe a escolha (a fábrica do vpad a lê
    ao nascer), o aparelho veste (`Daemon.vestir_a_mascara_do_aparelho`) e o perfil
    ativo guarda só se ele concordou; senão o registro volta. Sem vpad de pé, vale
    para o próximo; `flavor` vazio limpa. O P1 que nasce pelo fio veste no tique em
    que o pad se instala, e a conferência vai para lá (`gamepad.seguir_o_p1_uma_vez`);
    a rota que pode esperar usa :func:`escolher_a_mascara_e_esperar`.
    """
    escolha = _pedir_a_mascara(daemon, uniq, flavor)
    nascendo = _o_p1_que_veste(daemon, uniq)
    if nascendo is None:
        return _fechar_a_escolha(daemon, escolha, None, store)
    from hefesto_dualsense4unix.daemon.subsystems.gamepad import seguir_o_p1_uma_vez

    def _no_desfecho(desfecho: str) -> None:
        _fechar_a_escolha(daemon, escolha, desfecho, store)

    seguir_o_p1_uma_vez(nascendo, ("mascara", uniq, escolha.alvo), _no_desfecho)
    return {"status": "ok", "uniq": uniq, "flavor": escolha.alvo,
            "mudou": bool(escolha.mudou), "perfil": None, "gravado": False,
            "motivo": "p1_nascendo", "vestiu": escolha.vestiu}


async def escolher_a_mascara_e_esperar(
    daemon: Any, uniq: str, flavor: object, *, store: Any = _SEM_STORE
) -> dict[str, Any]:
    """:func:`escolher_a_mascara` que responde quando o P1 que veste a máscara existe.

    O dono da espera é o da `gamepad.emulation.set`, `gamepad.esperar_o_p1_que_nasce`:
    o pad que não nasce responde «falhou», e o registro volta ao que era.
    """
    escolha = _pedir_a_mascara(daemon, uniq, flavor)
    nascendo = _o_p1_que_veste(daemon, uniq)
    if nascendo is None:
        return _fechar_a_escolha(daemon, escolha, None, store)
    from hefesto_dualsense4unix.daemon.subsystems.gamepad import esperar_o_p1_que_nasce

    desfecho = await esperar_o_p1_que_nasce(daemon, nascendo)
    return _fechar_a_escolha(daemon, escolha, desfecho, store)


class _AEscolha(NamedTuple):
    """O que a escolha fez antes de o aparelho responder."""

    uniq: str
    alvo: str | None
    anterior: str | None
    mudou: bool
    vestiu: str | None


def _pedir_a_mascara(daemon: Any, uniq: str, flavor: object) -> _AEscolha:
    """Os passos 1 e 2: o registro recebe a escolha, e o aparelho é chamado a vestir."""
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
    return _AEscolha(uniq, alvo, anterior, bool(mudou), vestiu)


def _o_p1_que_veste(daemon: Any, uniq: str) -> Any:
    """O pedido do P1 que nasce pelo fio vestindo a escolha de `uniq`, ou ``None``.

    O P1 de outro pedido, que nasce na máscara de antes, não confere a escolha: ela
    vale para o próximo, e a reconciliação a veste (`gamepad.reconciliar_as_mascaras`).
    """
    if not mesma_identidade(uniq, _identidade_do_primario(daemon)):
        return None
    from hefesto_dualsense4unix.daemon.subsystems.gamepad import depois_do_p1

    nascendo = depois_do_p1(daemon)
    if nascendo is None or nascendo.mascara_do_p1 != mascara_efetiva(uniq, nascendo.key):
        return None
    return nascendo


def _fechar_a_escolha(
    daemon: Any, escolha: _AEscolha, desfecho: str | None, store: Any
) -> dict[str, Any]:
    """O passo 3: confere o que o aparelho vestiu e grava no perfil só se ele concordou.

    `desfecho` é o do P1 que nasceu pelo fio (``None``: o aparelho já respondeu); o
    pad que não nasceu («falhou») não vestiu nada, e o registro volta.
    """
    from hefesto_dualsense4unix.profiles.manager import (
        chave_de_peca_que_grava,
        gravar_a_mascara_no_perfil_ativo,
        nome_do_perfil_que_grava,
    )

    uniq, alvo = escolha.uniq, escolha.alvo
    vestiu = escolha.vestiu if desfecho is None else desfecho
    vestida = mascara_vestida(daemon, uniq)
    esperada = alvo if alvo is not None else vestida
    if desfecho == "falhou" or (
        vestida is not None and esperada is not None and vestida != esperada
    ):
        registro = registro_de_mascaras()
        if registro.mask_for(uniq) == alvo:
            if escolha.anterior is None:
                registro.clear_mask(uniq)
            else:
                registro.set_mask(uniq, escolha.anterior)
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
    return {"status": "ok", "uniq": uniq, "flavor": alvo, "mudou": escolha.mudou,
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
    "escolher_a_mascara_e_esperar",
    "mascara_efetiva",
    "mascara_vestida",
    "mascaras_validas",
    "mesma_identidade",
    "normalizar_mascara",
    "registro_de_mascaras",
    "vpad_ficou_para_tras",
]
