"""As faixas de endereço que NUNCA são um controle de verdade — um dono só.

**O DEFEITO QUE ISTO CURA, medido no disco do usuário em 18/09/2026.** O
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
o Hefesto lembrar dele. Aqui só entram faixas que esta casa usa como
fixture ou forja: as duas de teste e a do vpad forjado. Só as de endereço
LOCAL são, por construção, de aparelho nenhum — ver
:func:`e_endereco_sintetico`.
"""

from __future__ import annotations

FAIXAS_SINTETICAS: tuple[str, ...] = ("aabbcc", "02fe00", "e8473a")


def _canonico(addr: str) -> str:
    """O endereço em 12 hex minúsculos, sem ``:`` nem ``-``."""
    return addr.replace(":", "").replace("-", "").lower()


def _faixa_local(faixa: str) -> bool:
    """A faixa tem o bit de administração LOCAL (o ``0x02`` do primeiro octeto)?"""
    return bool(int(faixa[:2], 16) & 0x02)


def e_endereco_sintetico(addr: str | None) -> bool:
    """``True`` se este endereço é de uma faixa que nunca foi aparelho real."""
    if not addr or not isinstance(addr, str):
        return False
    chave = _canonico(addr)
    return any(
        chave.startswith(faixa) for faixa in FAIXAS_SINTETICAS if _faixa_local(faixa)
    )


__all__ = ["FAIXAS_SINTETICAS", "e_endereco_sintetico"]
