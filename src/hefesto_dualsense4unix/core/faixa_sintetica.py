"""As faixas de endereço que NUNCA são um controle de verdade — um dono só.

**O DEFEITO QUE ISTO CURA, medido no disco dela em 18/09/2026.** O
``controllers.json`` de produção tinha OITO entradas na fila de numeração, e
quatro eram endereços de fixture (``aa:bb:cc:00:00:0{1..4}``) escritos por uma
corrida da suíte em 22/08/2026. Os três DualSense reais ficaram com os postos
1, 2 e 3; o quarto — o de casca branca — foi empurrado para o **oitavo**.

**A CASA JÁ SABIA, E A CURA PAROU NA PREVENÇÃO.** O ``tests/conftest.py``
diagnosticou o vazamento em 25/08 e fechou a porta (o lar de mentira de
sessão, LAR-DE-SESSAO-01); ``scripts/check_faixa_sintetica.py`` nasceu para
ACUSAR. Nenhum dos dois LIMPA — e o script diz por quê, com todas as letras:
*"a decisão sobre o que já está no disco é de quem é dono da máquina"*. A
decisão veio em 18/09/2026, dela: *"corrige essa paridade sobrescrevendo a
info errada"*.

**POR QUE O DONO É AQUI e não o script.** A lista das três faixas morava
dentro de ``scripts/``, que não é pacote — o daemon não tem como importá-la, e
quem precisasse dela do lado do produto teria de DIGITAR os seis dígitos de
novo. Uma quarta grafia da mesma verdade é como esta casa perde um dia: a
régua e o produto discordando sobre o que é lixo. O script agora pergunta
aqui.

**O QUE NÃO ENTRA NESTA LISTA:** endereço real que ela não usa mais. Um
DualSense que dormiu seis meses continua tendo lugar na fila — é isso que faz
o Hefesto lembrar dele. Aqui só entram faixas que, por construção, NENHUM
aparelho do mundo tem: as duas de teste desta casa e a do vpad forjado.
"""

from __future__ import annotations

#: As três faixas sintéticas da casa (``CLAUDE.md``,
#: ``scripts/check_test_data.sh``). Cada uma é o prefixo de três octetos, em
#: 6 hex minúsculos e sem separador — a forma canônica do ``norm_mac``.
#:
#: * ``aabbcc`` — a faixa das fixtures da suíte (91 arquivos de teste a usam);
#: * ``02fe00`` — o MAC forjado dos vpads uhid (D9: o vpad jamais é
#:   "Controle N", e por isso jamais ocupa lugar na fila);
#: * ``e8473a`` — a faixa de exemplo da documentação.
FAIXAS_SINTETICAS: tuple[str, ...] = ("aabbcc", "02fe00", "e8473a")


def _canonico(addr: str) -> str:
    """O endereço em 12 hex minúsculos, sem ``:`` nem ``-``.

    Não valida: quem chama já filtrou a forma (``identity._MAC_RE``). O que
    esta função garante é que ``AA:BB:CC:00:00:01`` e ``aabbcc000001`` sejam
    a MESMA coisa para a pergunta abaixo — o ``controllers.json`` medido em
    23/08 usava a grafia sem ``:``, e nada impede a outra.
    """
    return addr.replace(":", "").replace("-", "").lower()


def e_endereco_sintetico(addr: str | None) -> bool:
    """``True`` se este endereço é de uma faixa que nunca foi aparelho real.

    Vazio e ``None`` respondem ``False``: "não sei" não é "é lixo", e quem
    decide o que fazer com endereço malformado é quem chama (o
    ``order_entries`` já o descarta por outra razão).
    """
    if not addr or not isinstance(addr, str):
        return False
    chave = _canonico(addr)
    return any(chave.startswith(faixa) for faixa in FAIXAS_SINTETICAS)


__all__ = ["FAIXAS_SINTETICAS", "e_endereco_sintetico"]
