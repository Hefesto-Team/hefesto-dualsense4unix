"""Plano de merge do cmdline de kernel para o install (PLAT-03 item 2).

Núcleo TESTÁVEL e PURO (zero I/O, zero root): dado o cmdline atual (string do
/proc/cmdline ou a lista de kernel_options do /etc/kernelstub/configuration),
produz o PLANO de mudanças que a lane de wiring executa via
`kernelstub --delete-options/--add-options` (fallback GRUB). Este módulo NUNCA
chama kernelstub — quem toca o sistema é o install.

REGRAS (estudo 2026-07-18-estudo-kernel-hardening.md §1, provadas ao vivo):

- O kernel respeita SÓ UM token ``usbcore.quirks=`` no cmdline. O plano NUNCA
  produz um segundo token: se já existe QUALQUER ``usbcore.quirks=``, ele FUNDE
  (entradas existentes + IDs nossos que faltarem, sem duplicar) num único token
  — delete dos antigos + add do fundido.
- Registro de dono (estado local ``cmdline.<param>=<dono>``): já presente =
  "terceiro" (Aurora/manual — o uninstall NÃO remove); ausente = "hefesto"
  (nosso — o uninstall remove); token fundido = "compartilhado" (o uninstall
  remove SÓ os IDs nossos, via :func:`strip_quirks_token`, re-fundindo o resto).
  O dono reportado pelo plano vale para a PRIMEIRA instalação: a lane de wiring
  preserva o registro anterior (o que um install passado marcou como "hefesto"
  continua "hefesto" num re-install).
- NUNCA reintroduzir ``054c:0ce6:k`` (NO_LPM), ``processor.max_cstate`` nem
  ``threadirqs`` — removidos DE PROPÓSITO pela Aurora v3.24.
"""
from __future__ import annotations

from collections.abc import Iterable, Sequence
from dataclasses import dataclass

# Parâmetros de interesse do hefesto (PLAT-03).
AUTOSUSPEND_PARAM = "usbcore.autosuspend"
AUTOSUSPEND_TOKEN = "usbcore.autosuspend=-1"
QUIRKS_PARAM = "usbcore.quirks"
HEFESTO_QUIRK_IDS: tuple[str, ...] = ("054c:0ce6:gn", "054c:0df2:gn")

# Donos possíveis do registro de estado.
OWNER_HEFESTO = "hefesto"
OWNER_TERCEIRO = "terceiro"
OWNER_COMPARTILHADO = "compartilhado"

# Operações do plano.
OP_NONE = "none"
OP_ADD = "add"
OP_REPLACE = "replace"

# Removidos de propósito pela Aurora (v3.24) — o plano jamais os recria.
NEVER_REINTRODUCE: tuple[str, ...] = (
    "054c:0ce6:k",
    "processor.max_cstate",
    "threadirqs",
)


@dataclass(frozen=True)
class CmdlineAction:
    """Uma decisão do plano para um parâmetro do cmdline.

    A lane de wiring traduz assim:
    - ``op == "none"``: nada a fazer (só registrar o dono);
    - ``op == "add"``: ``kernelstub --add-options token``;
    - ``op == "replace"``: ``kernelstub --delete-options`` de CADA item de
      ``remove_tokens`` e depois ``--add-options token``.
    """

    param: str
    op: str
    token: str
    remove_tokens: tuple[str, ...] = ()
    owner: str = OWNER_HEFESTO
    reason: str = ""


def parse_cmdline(cmdline: str) -> list[str]:
    """Tokens do cmdline (split por whitespace; suficiente para nossos params)."""
    return cmdline.split()


def tokens_for_param(tokens: Sequence[str], param: str) -> list[str]:
    """Todos os tokens ``param`` ou ``param=...`` presentes (na ordem)."""
    prefix = param + "="
    return [t for t in tokens if t == param or t.startswith(prefix)]


def _entry_key(entry: str) -> str:
    """Chave VID:PID (minúscula) de uma entrada ``vvvv:pppp:flags`` do quirks."""
    parts = entry.split(":")
    if len(parts) >= 2:
        return f"{parts[0]}:{parts[1]}".lower()
    return entry.lower()


def _quirks_entries(token: str) -> list[str]:
    """Entradas (``vvvv:pppp:flags``) de um token ``usbcore.quirks=...``."""
    if "=" not in token:
        return []
    value = token.split("=", 1)[1]
    return [e for e in value.split(",") if e]


def merge_quirks_token(
    existing_tokens: Sequence[str],
    desired_ids: Sequence[str] = HEFESTO_QUIRK_IDS,
) -> tuple[str, bool]:
    """Funde os IDs desejados no token ÚNICO ``usbcore.quirks=``.

    ``existing_tokens``: todos os tokens ``usbcore.quirks=...`` já no cmdline
    (0, 1 ou — caso patológico — vários; TODOS são fundidos num só, porque o
    kernel só respeita um). Entradas de terceiros são preservadas NA ORDEM.
    Entrada com o MESMO VID:PID e flags diferentes (ex.: o ``:k`` morto) é
    substituída pelas flags provadas — nunca duplicada.

    Retorna ``(token_fundido, mudou)``; ``mudou=False`` significa que o token
    existente já contém tudo (e era um só).
    """
    result: list[str] = []
    keys: dict[str, int] = {}
    for token in existing_tokens:
        for entry in _quirks_entries(token):
            key = _entry_key(entry)
            if key not in keys:
                keys[key] = len(result)
                result.append(entry)
    changed = len(existing_tokens) > 1
    for want in desired_ids:
        key = _entry_key(want)
        if key in keys:
            index = keys[key]
            if result[index] != want:
                result[index] = want  # flags divergentes → as provadas (gn)
                changed = True
        else:
            keys[key] = len(result)
            result.append(want)
            changed = True
    return f"{QUIRKS_PARAM}=" + ",".join(result), changed


def strip_quirks_token(
    existing_token: str,
    ids_to_remove: Sequence[str] = HEFESTO_QUIRK_IDS,
) -> tuple[str | None, bool]:
    """Inverso do merge, para o UNINSTALL de um token "compartilhado".

    Remove SÓ as entradas EXATAMENTE iguais às nossas (se alguém alterou as
    flags depois, a entrada deixou de ser nossa — fica). Retorna
    ``(token_restante, mudou)``; ``token_restante=None`` = o token ficou vazio
    e deve ser deletado por inteiro.
    """
    ours = set(ids_to_remove)
    remaining = [e for e in _quirks_entries(existing_token) if e not in ours]
    changed = len(remaining) != len(_quirks_entries(existing_token))
    if not remaining:
        return None, changed
    return f"{QUIRKS_PARAM}=" + ",".join(remaining), changed


def _plan_autosuspend(tokens: Sequence[str]) -> CmdlineAction:
    present = tokens_for_param(tokens, AUTOSUSPEND_PARAM)
    if AUTOSUSPEND_TOKEN in present:
        return CmdlineAction(
            param=AUTOSUSPEND_PARAM,
            op=OP_NONE,
            token=AUTOSUSPEND_TOKEN,
            owner=OWNER_TERCEIRO,
            reason="já provido por terceiro (Aurora/manual) — não tocar; uninstall não remove",
        )
    if present:
        return CmdlineAction(
            param=AUTOSUSPEND_PARAM,
            op=OP_REPLACE,
            token=AUTOSUSPEND_TOKEN,
            remove_tokens=tuple(present),
            owner=OWNER_HEFESTO,
            reason=f"valor divergente ({', '.join(present)}) → -1 (nunca suspender)",
        )
    return CmdlineAction(
        param=AUTOSUSPEND_PARAM,
        op=OP_ADD,
        token=AUTOSUSPEND_TOKEN,
        owner=OWNER_HEFESTO,
        reason="ausente — USB nunca dorme (PLAT-03)",
    )


def _plan_quirks(
    tokens: Sequence[str], desired_ids: Sequence[str]
) -> CmdlineAction:
    present = tokens_for_param(tokens, QUIRKS_PARAM)
    merged, changed = merge_quirks_token(present, desired_ids)
    if not present:
        return CmdlineAction(
            param=QUIRKS_PARAM,
            op=OP_ADD,
            token=merged,
            owner=OWNER_HEFESTO,
            reason="ausente — quirk anti-storm gn (preserva mic/fone)",
        )
    if not changed:
        return CmdlineAction(
            param=QUIRKS_PARAM,
            op=OP_NONE,
            token=present[0],
            owner=OWNER_TERCEIRO,
            reason="token único já contém os IDs do hefesto — não tocar",
        )
    return CmdlineAction(
        param=QUIRKS_PARAM,
        op=OP_REPLACE,
        token=merged,
        remove_tokens=tuple(present),
        owner=OWNER_COMPARTILHADO,
        reason=(
            "o kernel respeita SÓ UM token usbcore.quirks= — fundido com o(s) "
            f"existente(s) ({', '.join(present)}); uninstall remove só os IDs do hefesto"
        ),
    )


def plan_tokens(
    tokens: Sequence[str],
    desired_quirk_ids: Sequence[str] = HEFESTO_QUIRK_IDS,
) -> list[CmdlineAction]:
    """O plano completo (autosuspend + quirks) a partir dos tokens atuais."""
    return [_plan_autosuspend(tokens), _plan_quirks(tokens, desired_quirk_ids)]


def plan_cmdline(
    cmdline: str,
    desired_quirk_ids: Sequence[str] = HEFESTO_QUIRK_IDS,
) -> list[CmdlineAction]:
    """Como :func:`plan_tokens`, recebendo a string crua (/proc/cmdline)."""
    return plan_tokens(parse_cmdline(cmdline), desired_quirk_ids)


def apply_plan(tokens: Sequence[str], actions: Iterable[CmdlineAction]) -> list[str]:
    """SIMULA o plano sobre os tokens (para testes e para o doctor comparar).

    Não toca sistema nenhum: remove os ``remove_tokens`` e apensa o ``token``
    de cada ação add/replace, preservando a ordem do resto.
    """
    result = list(tokens)
    for action in actions:
        if action.op == OP_NONE:
            continue
        result = [t for t in result if t not in action.remove_tokens]
        result.append(action.token)
    return result


def ownership_record(actions: Iterable[CmdlineAction]) -> dict[str, str]:
    """Registro de dono p/ o estado local: ``{"cmdline.<param>": "<dono>"}``."""
    return {f"cmdline.{a.param}": a.owner for a in actions}


def forbidden_reintroductions(actions: Iterable[CmdlineAction]) -> list[str]:
    """Violações da regra "nunca reintroduzir" nos tokens que o plano ADICIONA.

    Lista vazia = plano seguro. Guarda de teste (e a wiring pode re-checar).
    """
    violations: list[str] = []
    for action in actions:
        if action.op == OP_NONE:
            continue
        for banned in NEVER_REINTRODUCE:
            if banned in action.token:
                violations.append(f"{action.token} contém {banned}")
    return violations
