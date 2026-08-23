"""linhagem_nintendo.py — quem é um Pro Controller, e quem só se parece com um.

UMA-FAIXA-NÃO-É-UM-FABRICANTE-01 (22/08/2026). A casa inteira decidia "é um Pro
genuíno?" comparando o endereço com **uma** faixa OUI — a do Pro desta bancada.
Este módulo é a casa única dessa pergunta, e ele a responde POR NEGATIVA.

O DEFEITO QUE ELE MATA
-----------------------

``E0:F6:B5`` é a faixa do Pro Controller desta casa. Não é a definição de
"Nintendo". MEDIDO em 22/08/2026 contra a cópia local do registro IEEE
(``/usr/share/ieee-data/oui.csv``)::

    grep -c -i '"Nintendo Co' oui.csv   ->  82
    grep -c -i '8bitdo'       oui.csv   ->   1

Oitenta e duas faixas MA-L da ``Nintendo Co., Ltd.``; **uma** da 8BitDo. Um Pro
de outra safra, na máquina de outra pessoa, recebia em silêncio: giroscópio em
STANDBY para sempre, link caindo sob carga, e o rótulo de clone na tela.

A REGRA, E POR QUE ELA É POR NEGATIVA
--------------------------------------

**``E4:17:D8`` é clone; qualquer outra faixa com cara de Pro é genuíno.**

A inversão não é elegância — é a única forma que aguenta as duas pontas:

1. **Pelo positivo não dá.** A lista de faixas Nintendo tem 82 entradas hoje e
   ganha mais amanhã: uma lista fechada aqui envelhece calada, e o sintoma de
   estar velha é EXATAMENTE o defeito que este módulo existe para matar.
2. **Por nome sozinho, também não.** O 8BitDo em modo Switch mente VID, PID,
   serial e ``HID_NAME`` — ele se apresenta como ``057E:2009`` "Nintendo Co.,
   Ltd. Pro Controller", igual ao genuíno. A OUI é o único sinal honesto que
   ele emite. Promovê-lo a genuíno custa a probe morrendo em ``ret=-110``
   (A/B de 23/07/2026).
3. **Pela negativa, a lista fechada é COMPLETA.** A 8BitDo tem uma faixa só, e
   isso está medido acima. Uma lista de tamanho um que cobre a população
   inteira é uma definição; uma lista de tamanho um que cobre 1/82 é uma
   amostra promovida a definição, que é o defeito.

O PREÇO DA INVERSÃO, DECLARADO
-------------------------------

Um clone de OUTRO fabricante — que não a 8BitDo — que minta ``057E:2009`` e o
nome passaria por genuíno aqui. Não existe nenhum medido nesta casa, e o custo
de errar para esse lado é limitado: quem consome isto no caminho de escrita
(``ExternalImuEnabler``) já tem teto de duas tentativas, backoff e barreira de
transporte. O custo de errar para o outro lado — recusar todo Pro que não seja
o desta bancada — é o giroscópio morto de todo mundo, e esse já foi pago.

SEM MAC, A RESPOSTA É "NÃO"
----------------------------

:func:`e_pro_genuino` devolve ``False`` quando não há endereço legível: sem OUI
não há como descartar o clone, e a negativa é o lado seguro. É o mesmo
comportamento de antes da cura — nenhum caminho que já funcionava mudou por
falta de MAC.
"""

from __future__ import annotations

from collections.abc import Iterable

#: OUIs (6 hex minúsculos, sem separador) do firmware CLONE. **Lista fechada e
#: COMPLETA**, não amostra: o registro IEEE tem exatamente uma faixa MA-L da
#: "8BITDO TECHNOLOGY HK LIMITED", medido em 22/08/2026 (ver o cabeçalho). É
#: sobre esta completude que a regra por negativa se apoia — se um dia aparecer
#: uma segunda faixa da 8BitDo no registro, é AQUI que ela entra, e nada mais
#: no produto precisa saber.
OUIS_CLONE = frozenset({"e417d8"})

#: Faixas Nintendo que esta casa JÁ VIU num aparelho de verdade. É **semente,
#: não definição** — a Nintendo tem 82 faixas registradas e nenhum caminho de
#: decisão deste módulo consulta esta lista para dizer "é genuíno". Ela existe
#: para dois usos honestos: o rótulo de tela poder dizer "faixa conhecida" e o
#: portão de anonimato saber quais literais vigiar.
#:
#: O nome diz o que ela é. Uma linha aqui não vira uma definição lá fora.
OUI_PRO_DESTA_BANCADA = "e0f6b5"

OUIS_NINTENDO_VISTAS = frozenset({OUI_PRO_DESTA_BANCADA})

#: VID da Nintendo. Vocabulário de protocolo, não hardware de ninguém.
VIDS_NINTENDO = frozenset({"057e"})

#: ``vid:pid`` com que o Pro Controller se apresenta — e com que o clone MENTE
#: que se apresenta. Vocabulário de protocolo: casa os dois de propósito, que
#: é justamente por isso que ele não basta para decidir nada sozinho.
VIDPID_PRO = frozenset({"057e:2009"})

#: Pedaços de ``HID_NAME``, em minúsculas, que denunciam um Pro Controller
#: (genuíno OU clone). É o que o ``hid-nintendo`` escreve para os dois.
#:
#: NÃO casa ``"DualSense Wireless Controller"`` e NÃO casa ``"8BitDo Pro 2"``
#: em modo X-input — aquele é um gamepad comum, sem nada a ver com sniff nem
#: com subcomando de IMU.
NOMES_PRO = ("pro controller",)

#: Pedaços de ``HID_NAME`` da linhagem inteira, para quem pergunta "este
#: adaptador hospeda Nintendo?" — pergunta em que genuíno e clone respondem
#: igual, porque os DOIS leem o nome do host.
NOMES_LINHAGEM = ("pro controller", "nintendo")

_SEPARADORES = (":", "-", ".")


def normalizar_oui(uniq: str | None) -> str | None:
    """OUI em 6 hex minúsculos, ou ``None`` quando não há endereço legível.

    Aceita as duas formas que circulam nesta casa — ``e4:17:d8:00:00:03`` (o
    ``uniq`` cru do sysfs) e ``e417d800000003`` (a key canônica do registro de
    identidade) — porque ter duas normalizações é como as duas se separam.

    Devolve ``None`` para vazio, para o que não for hexadecimal e para o que
    tiver menos de três octetos: menos que isso não é uma faixa.
    """
    if not uniq:
        return None
    bruto = uniq.strip().lower()
    for sep in _SEPARADORES:
        bruto = bruto.replace(sep, "")
    if len(bruto) < 6:
        return None
    faixa = bruto[:6]
    if any(c not in "0123456789abcdef" for c in faixa):
        return None
    return faixa


def e_clone_conhecido(uniq: str | None) -> bool:
    """O endereço está numa faixa de clone conhecida (hoje: só a 8BitDo)?

    ``False`` sem endereço legível — "não sei" não é "não é". Quem precisa da
    resposta segura usa :func:`e_pro_genuino`, que exige o endereço.
    """
    faixa = normalizar_oui(uniq)
    return faixa is not None and faixa in OUIS_CLONE


def parece_pro(*, nome: str = "", vid: str = "", pid: str = "") -> bool:
    """O device SE APRESENTA como Pro Controller — genuíno ou clone.

    Não decide autenticidade: é de propósito que o clone passe aqui. Quem
    separa os dois é a OUI, em :func:`e_pro_genuino`.

    Com VID presente, ele tem de ser da Nintendo — é o que impede um DualSense
    ou um gamepad qualquer de entrar por causa do nome. Com VID ausente (o
    caminho em que só há ``HID_NAME``), o nome decide sozinho.
    """
    v = (vid or "").strip().lower()
    p = (pid or "").strip().lower()
    if v and v not in VIDS_NINTENDO:
        return False
    if v and f"{v}:{p}" in VIDPID_PRO:
        return True
    return any(marca in (nome or "").strip().lower() for marca in NOMES_PRO)


def e_pro_genuino(
    *, uniq: str | None, nome: str = "", vid: str = "", pid: str = ""
) -> bool:
    """Pro Controller da Nintendo, e não o clone — a pergunta por NEGATIVA.

    Verdadeiro quando o aparelho se apresenta como Pro (:func:`parece_pro`) e o
    endereço dele **não** está numa faixa de clone conhecida. Qualquer faixa da
    Nintendo serve, inclusive as 81 que esta bancada nunca viu.

    ``False`` sem endereço legível: sem OUI não dá para descartar o clone.
    """
    if not parece_pro(nome=nome, vid=vid, pid=pid):
        return False
    if normalizar_oui(uniq) is None:
        return False
    return not e_clone_conhecido(uniq)


def _e_da_linhagem_nintendo(*, nome: str = "", uniq: str | None = None) -> bool:
    """Este controle lê o nome Bluetooth do host? Genuíno e clone respondem sim.

    PRIVADA de propósito, e o sublinhado é uma medição, não estilo: o único
    consumidor é ``integrations/apelido_do_dongle``, e NADA em ``src/`` importa
    aquele módulo ainda — como símbolo público ela seria uma promessa sem
    caminho, que é dívida com nome. Promova-a (tire o sublinhado) no dia em que
    a ``E2`` da N-IGUAL-A-UM-01 fiar o ``apelido_do_dongle`` à aba.

    Pergunta DIFERENTE de :func:`e_pro_genuino`, e é por isso que ela mora numa
    função separada: quem dá nome a um adaptador (``BT-NINTENDO-ACTIVE-01``,
    metade 1) precisa do prefixo ``Nintendo`` sempre que houver QUALQUER um dos
    dois pendurado nele. O A/B de 23/07/2026 mediu que o nome não atrapalha o
    clone — o que atrapalha o clone é o no-sniff, que é outra metade.

    OUI **ou** nome bastam, e o nome existe aqui justamente porque OUI é lista
    fechada: um aparelho novo do mesmo firmware entra pelo nome sem ninguém
    precisar descobrir a faixa dele primeiro.
    """
    faixa = normalizar_oui(uniq)
    if faixa is not None and (faixa in OUIS_CLONE or faixa in OUIS_NINTENDO_VISTAS):
        return True
    minusculo = (nome or "").strip().lower()
    return any(marca in minusculo for marca in NOMES_LINHAGEM)


def com_dois_pontos(ouis: Iterable[str]) -> frozenset[str]:
    """``{"e417d8"}`` -> ``{"e4:17:d8"}``. Para quem casa contra ``uniq`` cru."""
    return frozenset(f"{o[0:2]}:{o[2:4]}:{o[4:6]}" for o in ouis)


#: A linhagem inteira — genuína e clone — na forma com ``:``, que é como o
#: ``uniq`` cru do sysfs chega. Derivada, nunca redigitada: uma segunda cópia
#: com outra pontuação é como as duas se separam.
OUIS_LINHAGEM_COM_DOIS_PONTOS = com_dois_pontos(OUIS_NINTENDO_VISTAS | OUIS_CLONE)


__all__ = [
    "NOMES_LINHAGEM",
    "NOMES_PRO",
    "OUIS_CLONE",
    "OUIS_LINHAGEM_COM_DOIS_PONTOS",
    "OUIS_NINTENDO_VISTAS",
    "OUI_PRO_DESTA_BANCADA",
    "VIDPID_PRO",
    "VIDS_NINTENDO",
    "com_dois_pontos",
    "e_clone_conhecido",
    "e_pro_genuino",
    "normalizar_oui",
    "parece_pro",
]
