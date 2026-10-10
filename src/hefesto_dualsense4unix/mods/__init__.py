"""As modificações: código de terceiro que roda FORA do serviço (ADR-021).

Cada modificação é uma pasta com o ``hefesto-mod.json`` na raiz
(:mod:`.manifesto`), instalada de um endereço git ou de uma pasta
(:mod:`.instalador`), aberta pelo serviço como processo filho, com caixa
quando o ``bwrap`` existe (:mod:`.supervisor`), e que só fala com o serviço
pela porta própria, com as permissões que a pessoa aceitou (:mod:`.porta`).
"""
from __future__ import annotations

#: A versão da porta das modificações que este Hefesto fala. O manifesto
#: declara a faixa que aceita (``"api": ">=1,<2"``); fora dela, a modificação
#: não sobe, e a frase de :func:`.manifesto.frase_da_api` diz por quê.
API_DAS_MODIFICACOES = 1

__all__ = ["API_DAS_MODIFICACOES"]
