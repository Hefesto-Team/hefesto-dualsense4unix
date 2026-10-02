"""Plano de merge do cmdline de kernel para o install (PLAT-03 item 2)."""
from __future__ import annotations

from collections.abc import Iterable, Sequence
from dataclasses import dataclass

AUTOSUSPEND_PARAM = "usbcore.autosuspend"
AUTOSUSPEND_TOKEN = "usbcore.autosuspend=-1"
QUIRKS_PARAM = "usbcore.quirks"
HEFESTO_QUIRK_IDS: tuple[str, ...] = ("054c:0ce6:gn", "054c:0df2:gn")

OWNER_HEFESTO = "hefesto"
OWNER_TERCEIRO = "terceiro"
OWNER_COMPARTILHADO = "compartilhado"

OP_NONE = "none"
OP_ADD = "add"
OP_REPLACE = "replace"

NEVER_REINTRODUCE: tuple[str, ...] = (
    "054c:0ce6:k",
    "processor.max_cstate",
    "threadirqs",
)


@dataclass(frozen=True)
class CmdlineAction:
    """Uma decisão do plano para um parâmetro do cmdline."""

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
    """Funde os IDs desejados no token ÚNICO ``usbcore.quirks=``."""
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
                result[index] = want
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
    """Inverso do merge, para o UNINSTALL de um token "compartilhado"."""
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
    """SIMULA o plano sobre os tokens (para testes e para o doctor comparar)."""
    result = list(tokens)
    for action in actions:
        if action.op == OP_NONE:
            continue
        result = [t for t in result if t not in action.remove_tokens]
        result.append(action.token)
    return result


def forbidden_reintroductions(actions: Iterable[CmdlineAction]) -> list[str]:
    """Violações da regra "nunca reintroduzir" nos tokens que o plano ADICIONA."""
    violations: list[str] = []
    for action in actions:
        if action.op == OP_NONE:
            continue
        for banned in NEVER_REINTRODUCE:
            if banned in action.token:
                violations.append(f"{action.token} contém {banned}")
    return violations
