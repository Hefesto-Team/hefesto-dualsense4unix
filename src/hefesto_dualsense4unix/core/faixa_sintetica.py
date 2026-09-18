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
o Hefesto lembrar dele. Aqui só entram faixas que esta casa usa como
fixture ou forja: as duas de teste e a do vpad forjado. Só as de endereço
LOCAL são, por construção, de aparelho nenhum — ver
:func:`e_endereco_sintetico`.
"""

from __future__ import annotations

#: As três faixas sintéticas da casa (``CLAUDE.md``,
#: ``scripts/check_test_data.sh``). Cada uma é o prefixo de três octetos, em
#: 6 hex minúsculos e sem separador — a forma canônica do ``norm_mac``.
#:
#: * ``aabbcc`` — a faixa das fixtures da suíte (91 arquivos de teste a usam);
#: * ``02fe00`` — o MAC forjado dos vpads uhid (D9: o vpad jamais é
#:   "Controle N", e por isso jamais ocupa lugar na fila);
#: * ``e8473a`` — a faixa de exemplo da documentação. É a única UNIVERSAL das
#:   três (sem o bit de administração local), e por isso só os varredores de
#:   texto a procuram: :func:`e_endereco_sintetico` a deixa de fora.
FAIXAS_SINTETICAS: tuple[str, ...] = ("aabbcc", "02fe00", "e8473a")


def _canonico(addr: str) -> str:
    """O endereço em 12 hex minúsculos, sem ``:`` nem ``-``.

    Não valida: quem chama já filtrou a forma (``identity._MAC_RE``). O que
    esta função garante é que ``AA:BB:CC:00:00:01`` e ``aabbcc000001`` sejam
    a MESMA coisa para a pergunta abaixo — o ``controllers.json`` medido em
    23/08 usava a grafia sem ``:``, e nada impede a outra.
    """
    return addr.replace(":", "").replace("-", "").lower()


def _faixa_local(faixa: str) -> bool:
    """A faixa tem o bit de administração LOCAL (o ``0x02`` do primeiro octeto)?

    É a regra da IEEE, e não uma lista: prefixo com esse bit ligado nunca é
    atribuído a fabricante, então nenhum aparelho de fábrica o traz. Sem ele o
    prefixo é UNIVERSAL — espaço que a IEEE distribui —, e "ninguém o usa hoje"
    não é garantia de amanhã.
    """
    return bool(int(faixa[:2], 16) & 0x02)


def e_endereco_sintetico(addr: str | None) -> bool:
    """``True`` se este endereço é de uma faixa que nunca foi aparelho real.

    Vazio e ``None`` respondem ``False``: "não sei" não é "é lixo", e quem
    decide o que fazer com endereço malformado é quem chama (o
    ``order_entries`` já o descarta por outra razão).

    **SÓ AS FAIXAS DE ENDEREÇO LOCAL — INSTALL-UNIVERSAL, 18/09/2026.** Esta
    pergunta é a que o ``check_faixa_sintetica.py --limpar`` faz antes de TIRAR
    uma entrada da fila de numeração, no ``doctor --fix`` de qualquer máquina.
    ``e8473a`` é faixa universal (primeiro octeto ``e8``, bit local zero): o
    ``oui.csv`` de 2022 da bancada não a lista, e ausência numa lista velha
    não é prova de que nenhum aparelho a tenha. Um controle de verdade nessa
    faixa perderia o lugar na fila de quem rodasse o ``--fix``. As três faixas
    continuam em :data:`FAIXAS_SINTETICAS` para os varredores de TEXTO, que só
    acusam — e acusar documento não custa aparelho de ninguém.
    """
    if not addr or not isinstance(addr, str):
        return False
    chave = _canonico(addr)
    return any(
        chave.startswith(faixa) for faixa in FAIXAS_SINTETICAS if _faixa_local(faixa)
    )


__all__ = ["FAIXAS_SINTETICAS", "e_endereco_sintetico"]
