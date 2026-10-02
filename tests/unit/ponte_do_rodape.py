"""O dublê da ponte para os botões do rodapé que gravam ou mandam perfil.

Desde 02/10/2026 (O-APLICAR-E-O-SALVAR-JA-ATUALIZAM-01) o «Salvar Perfil» passa
pelo funil `perfil.gravar_e_reaplicar` (o `profile.reaplicar` do perfil que
vale e o `launch_env.refresh`) e termina com a volta (`perfil.a_volta_do_perfil`:
o `launch_env.refresh`, o `coop.sync` e o `identity.renumber`). As réguas que
chamavam o Salvar com `p=None` mediam só o disco, e o Salvar não falava com o
daemon; agora fala, e `None` não é ponte.

NÃO É MAIS FROUXO QUE A PONTE REAL (`interface/pacotes/ponte.py`): as mesmas
assinaturas, e as respostas com a forma do daemon (`profile.reaplicar` como o
`_handle_profile_reaplicar`, `coop.sync` como o `_handle_coop_sync`,
`identity.renumber` como o `_handle_identity_renumber`). Ele anota a ordem das
chamadas em :attr:`PonteDoRodape.chamadas`, e um método que a ponte não tem
levanta `AttributeError`, como na ponte de verdade.
"""
from __future__ import annotations

from typing import Any

#: O que o daemon responde a cada método cru da volta, na forma dele.
RESPOSTAS: dict[str, Any] = {
    "coop.sync": {"status": "ok", "players": 1, "active": False},
    "identity.renumber": {"ok": True, "renumbered": {}},
    "launch_env.refresh": {"status": "ok"},
}


class PonteDoRodape:
    """A ponte que anota, e responde como o daemon vivo."""

    def __init__(self) -> None:
        self.chamadas: list[str] = []

    def profile_reaplicar(self, nome: str) -> dict[str, Any] | None:
        self.chamadas.append("profile.reaplicar")
        return {"active_profile": nome, "mode_aplicado": True, "secoes": {}}

    def chamar(self, metodo: str, timeout: float | None = None, **params: Any) -> bool:
        self.chamadas.append(metodo)
        return True

    def resultado(self, metodo: str, timeout: float | None = None, **params: Any) -> Any:
        self.chamadas.append(metodo)
        return RESPOSTAS.get(metodo, {"status": "ok"})
