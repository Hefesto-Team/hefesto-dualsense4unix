#!/usr/bin/env python3
"""A CONFERÊNCIA DELA — a tabela de 07/09, medida no PUBLICADO, uma linha por item.

Ela mandou: *"Rodo essa conferência de novo antes do merge, com as duas levas
dentro — se alguma [ficar n]a direita, ela não passa para o dev."*

Então isto não é relatório: é o PORTÃO do merge. Sai `rc=1` se alguma linha
continuar na coluna da direita.

O que ele NÃO faz, e é de propósito: ele não olha o `mockup/`. O que decide é o
que o produto RENDERIZA — `src/hefesto_dualsense4unix/interface/paginas/`.
"""
from __future__ import annotations

import pathlib
import re
import subprocess
import sys

RAIZ = pathlib.Path(__file__).resolve().parents[1]
PAGINAS = RAIZ / "src/hefesto_dualsense4unix/interface/paginas"

ABAS = {
    "01": "01-jogar.html", "02": "02-controles.html", "03": "03-gatilhos.html",
    "04": "04-iluminacao.html", "05": "05-vibracao.html", "06": "06-navegacao.html",
    "07": "07-lancadores.html", "08": "08-conexoes.html", "09": "09-sistema.html",
    "10": "10-perfis.html",
}


def corpo_visivel(nome: str) -> str:
    """O que ELA LÊ DENTRO DA JANELA.

    Sem comentário, sem `<style>`, sem `<script>`, sem tag — e **sem a
    `.nota`**, que é a legenda do mockup e a própria folha declara *"fora da
    janela"*. Esta régua nasceu SEM esse corte, e o preço foi imediato: ela
    acusou nove vazamentos de id de sprint que estavam todos na legenda, isto é,
    no documento em que a casa conta a ela o que mudou. *Uma régua que mede o
    documento de obra junto com o produto acusa o produto pelo que o documento
    diz.*

    A LEGENDA VIAJA PARA O PUBLICADO, e isso é fato relatado em 07/09/2026: o
    produto instalado carrega o registro de obra do mockup. **Se ela deve ou
    não ir junto é decisão de tela, e a tela é dela** — por isso esta régua não
    a julga, e a pergunta fica escrita aqui em vez de virar um vermelho que
    finge ser defeito de código.
    """
    bruto = (PAGINAS / nome).read_text(encoding="utf-8")
    corte = bruto.find('<div class="nota"')
    if corte > 0:
        bruto = bruto[:corte]
    sem = re.sub(r"<!--.*?-->", " ", bruto, flags=re.S)
    sem = re.sub(r"<style\b.*?</style>", " ", sem, flags=re.S | re.I)
    sem = re.sub(r"<script\b.*?</script>", " ", sem, flags=re.S | re.I)
    return re.sub(r"<[^>]+>", " ", sem)


def html(nome: str) -> str:
    return (PAGINAS / nome).read_text(encoding="utf-8")


# ---------------------------------------------------------------- as linhas

def os_quatro_players() -> tuple[bool, str]:
    """Os quatro lugares carregam o mesmo conjunto de `data-campo`, nas dez."""
    saida = subprocess.run(
        [sys.executable, str(RAIZ / "scripts/check_os_quatro_lugares.py"), "--publicado"],
        capture_output=True, text=True, cwd=RAIZ)
    return saida.returncode == 0, (saida.stdout + saida.stderr).strip().splitlines()[-1:][0] if (saida.stdout or saida.stderr) else "sem saída"


def iluminacao_sem_automatico() -> tuple[bool, str]:
    """Os botões saíram E a prosa que os explicava saiu junto."""
    corpo = corpo_visivel(ABAS["04"])
    gestos = set(re.findall(r'data-gesto="([^"]+)"', html(ABAS["04"])))
    sobra_gesto = "auto" in gestos
    n = corpo.count("Automático")
    if sobra_gesto:
        return False, f"o gesto `auto` ainda existe na página publicada"
    if n:
        trechos = [" ".join(m.group(0).split())
                   for m in re.finditer(r".{60}Automático.{60}", corpo, flags=re.S)]
        return False, f"{n} menção(ões) a 'Automático' no CORPO VISÍVEL: " + " | ".join(trechos[:3])
    return True, "botões fora, gesto fora, prosa fora"


def a_tela_nao_narra_commit() -> tuple[bool, str]:
    """A tela não é changelog: nada de hash, de nome de commit nem de decisão interna."""
    padroes = [
        (r"\bcommit\b", "a palavra 'commit'"),
        (r"\b[0-9a-f]{8}\b(?!\d)", "um hash de commit"),
        (r"\bD-\d{4}-[A-Z]", "um id de decisão interna"),
        (r"\b[A-Z]{3,}-[A-Z0-9-]+-\d{2}\b", "um id de sprint"),
        (r"\bnoqa\b", "uma marca de régua"),
    ]
    achados = []
    for numero, nome in ABAS.items():
        corpo = corpo_visivel(nome)
        for pad, oque in padroes:
            for m in re.finditer(pad, corpo):
                volta = " ".join(corpo[max(0, m.start() - 50):m.end() + 50].split())
                achados.append(f"aba {numero}: {oque} — ...{volta}...")
    if achados:
        return False, f"{len(achados)} vazamento(s): " + " | ".join(achados[:4])
    return True, "as dez páginas não narram commit nem decisão interna"


def frases_que_confessam() -> tuple[bool, str]:
    """A regra dela de 07/09: a tela não informa os nossos defeitos."""
    saida = subprocess.run(
        [sys.executable, str(RAIZ / "scripts/check_a_tela_nao_confessa.py")],
        capture_output=True, text=True, cwd=RAIZ)
    linhas = (saida.stdout + saida.stderr).strip().splitlines()
    return saida.returncode == 0, linhas[-1] if linhas else "sem saída"


def mascara_nintendo_pro() -> tuple[bool, str]:
    """A máscara do Pro Controller existe no FLAVORS do uinput. PERGUNTA AO DONO.

    ESTA RÉGUA DEU VERDE FALSO ATÉ 08/09/2026, e o advogado do diabo a pegou.
    Ela lia o arquivo como TEXTO e procurava `nintendo.pro` — que casa no
    comentário da linha 89 e no `__all__` da 1144. Pior: ela imprimia
    *"(42 entradas indentadas)"*, contando toda linha `"chave":` indentada do
    arquivo, inclusive as DE DENTRO de cada máscara. O `FLAVORS` tem **três**
    entradas. *A régua respondia sobre o próprio texto do código, não sobre o
    produto* — a assinatura dos seis instrumentos falsos de 05/09, escrita duas
    vezes neste mesmo arquivo e repetida aqui mesmo assim.

    Agora ela IMPORTA o dicionário e confere a entrada pelos números do
    aparelho: o Pro Controller da Nintendo é `057e:2009`, e é isso que o jogo
    lê. Comentário nenhum satisfaz esta pergunta.
    """
    import sys as _sys
    _sys.path.insert(0, str(RAIZ / "src"))
    try:
        from hefesto_dualsense4unix.integrations.uinput_gamepad import FLAVORS
    except Exception as erro:
        return False, f"não consegui importar o FLAVORS ({erro!r}) — e 'não sei' não é 'está bom'"
    entrada = FLAVORS.get("nintendo")
    if not isinstance(entrada, dict):
        return False, f"o FLAVORS tem {sorted(FLAVORS)} — nenhuma máscara `nintendo`"
    vendor, product = entrada.get("vendor"), entrada.get("product")
    if (vendor, product) != (0x057E, 0x2009):
        return False, (f"a máscara `nintendo` existe mas anuncia {vendor:#06x}:{product:#06x} — "
                       "o Pro Controller é 0x057e:0x2009, e é esse par que o jogo lê")
    return True, (f"FLAVORS = {sorted(FLAVORS)}; a `nintendo` anuncia "
                  f"{vendor:#06x}:{product:#06x} — o Pro Controller")


def o_virtual_liga_o_microfone() -> tuple[bool, str]:
    """O ato dela conta como ouvinte na ponte do rádio. EXERCITA A PONTE REAL.

    ESTA RÉGUA DEU VERDE FALSO ATÉ 08/09/2026, e o advogado do diabo a pegou
    com a prova na mão: ela lia o arquivo como TEXTO e procurava
    `pedido_dela|ato_dela|…`. Das NOVE ocorrências que a faziam fechar, **três
    eram comentário e docstring** — apagar o corpo de `dizer_o_pedido_dela` e
    deixar a docstring mantinha a linha verde sobre um microfone que não liga.

    Agora ela monta a `PonteMicBluetooth` de verdade, com uma source que diz
    `SUSPENDED` (isto é: NINGUÉM gravando), diz a palavra dela, e cobra que o
    `0x32` seja PEDIDO assim mesmo. É a pergunta inteira em três linhas:
    *sem ouvinte, o ato dela liga o microfone?*

    O NEGATIVO VEM JUNTO e é o que separa medir de torcer: com a palavra dela
    em `False`, o pedido tem de cair mesmo com a source em `RUNNING` — o mudo
    dela vence um aplicativo gravando. Uma régua que só sabe dizer sim não
    distingue a cura de um `return True`.
    """
    import sys as _sys
    _sys.path.insert(0, str(RAIZ / "src"))
    try:
        from hefesto_dualsense4unix.integrations import dualsense_bt_audio as bt
    except Exception as erro:
        return False, f"não consegui importar a ponte ({erro!r}) — e 'não sei' não é 'está bom'"

    class _SourceQueDiz:
        """Uma source do PipeWire que responde o estado que eu mandar."""

        def __init__(self, estado: str) -> None:
            self._estado = estado

        def estado(self) -> str:
            return self._estado

    def pedido(estado: str, palavra: bool | None) -> bool | None:
        no = bt.NoDualSenseBT(caminho="/dev/hidraw-conferencia", uniq="aabbcc000001",
                              produto=0x0CE6)
        ponte = bt.PonteMicBluetooth(no, source=_SourceQueDiz(estado))
        ponte.dizer_o_pedido_dela(palavra)
        return ponte._talvez_seguir_a_source()

    try:
        sem_ouvinte_com_a_palavra = pedido("SUSPENDED", True)
        mudo_dela_contra_o_gravador = pedido("RUNNING", False)
        sem_palavra_o_ouvinte_manda = pedido("SUSPENDED", None)
    except Exception as erro:
        return False, f"a ponte não pôde ser exercitada: {erro!r}"

    if sem_ouvinte_com_a_palavra is not True:
        return False, ("SUSPENDED + a palavra dela LIGADA e o microfone NÃO subiu "
                       f"(pedido={sem_ouvinte_com_a_palavra!r}) — o ato dela não liga nada")
    if mudo_dela_contra_o_gravador is not False:
        return False, ("RUNNING + a palavra dela DESLIGADA e o microfone ficou no ar "
                       f"(pedido={mudo_dela_contra_o_gravador!r}) — o mudo dela não vence o gravador")
    if sem_palavra_o_ouvinte_manda is not False:
        return False, ("sem palavra dela e sem ouvinte o microfone subiu "
                       f"(pedido={sem_palavra_o_ouvinte_manda!r}) — a economia do link caiu junto")
    return True, ("a ponte foi exercitada: sem ouvinte, o ato dela LIGA; o mudo dela "
                  "vence um gravador; e sem a palavra dela quem manda é o ouvinte")


def cor_unica() -> tuple[bool, str]:
    """Dois controles na mesa não acendem a mesma cor. MEDIDO NO APARELHO.

    DUAS VERSÕES DESTA RÉGUA DERAM VERDE FALSO em 08/09/2026, e as duas pelo
    mesmo motivo: elas casavam TEXTO. A primeira achou `desempate` de ordem de
    jogador; a segunda achou `"os fundos das três colunas não são cores
    diferentes"`, que é CSS da aba Perfis. *O instrumento respondia sobre outra
    coisa que não o produto* — a assinatura dos seis instrumentos falsos que
    esta casa arrancou em 05/09.

    A régua agora PERGUNTA AO DONO: o daemon vivo diz que cor está acesa em cada
    controle da mesa (`lightbar_rgb`, com `lightbar_source` dizendo de onde veio
    a leitura). Duas iguais é vermelho. Foi assim que ELA viu o defeito — dois
    azuis lado a lado —, e é a única leitura que não pode mentir sobre o
    plástico.

    SEM DAEMON VIVO A RÉGUA NÃO INVENTA: ela devolve o que não pôde medir. "Não
    sei" nunca vira "está bom" — é a mesma regra do `_talvez_seguir_a_source`.
    """
    import asyncio
    import json

    sock = "/run/user/1000/hefesto-dualsense4unix/hefesto-dualsense4unix.sock"

    async def perguntar() -> list[dict]:
        leitor, escritor = await asyncio.open_unix_connection(sock)
        pedido = {"jsonrpc": "2.0", "id": 1, "method": "daemon.state_full", "params": {}}
        escritor.write((json.dumps(pedido) + "\n").encode())
        await escritor.drain()
        linha = await asyncio.wait_for(leitor.readline(), 15)
        escritor.close()
        return (json.loads(linha).get("result") or {}).get("controllers") or []

    try:
        mesa = asyncio.run(perguntar())
    except Exception as erro:
        return False, f"não pude perguntar ao daemon ({erro!r}) — e 'não sei' não é 'está bom'"
    if len(mesa) < 2:
        return False, f"só {len(mesa)} controle(s) na mesa — a régua precisa de dois para medir colisão"

    por_cor: dict[tuple, list[int]] = {}
    for c in mesa:
        rgb = c.get("lightbar_rgb")
        if not rgb:
            continue
        por_cor.setdefault(tuple(rgb), []).append(c.get("player"))
    colisoes = {cor: js for cor, js in por_cor.items() if len(js) > 1}
    if not colisoes:
        return True, f"os {len(mesa)} controles da mesa acendem cores distintas"

    ditas = "; ".join(
        f"jogadores {sorted(j for j in js if j is not None)} todos em #{r:02X}{g:02X}{b:02X}"
        for (r, g, b), js in colisoes.items())

    # O DAEMON VIVO É DE ANTES DO INSTALL, e essa é a única leitura desta régua
    # que NÃO fecha antes dele. A cura mora na árvore; o aparelho só muda quando
    # o daemon reinicia — e reiniciar o daemon dela é o `install.sh`, que derruba
    # os quatro controles e por isso não acontece sozinho.
    #
    # A régua NÃO fica verde por isso. Ela DIZ o que mediu e o que falta para
    # fechar, porque "curado na árvore" e "curado no plástico" são duas coisas, e
    # confundi-las é o verde falso que esta casa mais arranca. A ordem dela é
    # `dev` depois install depois conferência de novo — e é nessa terceira volta
    # que esta linha fecha.
    daqui = pathlib.Path(__file__).resolve().parents[1] / "src/hefesto_dualsense4unix/core/led_control.py"
    curado_na_arvore = daqui.exists() and "cores_sem_colisao" in daqui.read_text(encoding="utf-8")
    if curado_na_arvore:
        return False, (f"COLISÃO no aparelho: {ditas} — MAS a cura está na árvore "
                       "(`core/led_control.cores_sem_colisao`). O daemon vivo é de "
                       "ANTES do install; esta linha fecha na volta depois dele")
    return False, f"COLISÃO no aparelho: {ditas}"


LINHAS = [
    ("os 4 players nas dez abas", os_quatro_players),
    ("Iluminação sem o «Automático»", iluminacao_sem_automatico),
    ("a tela não narra commit nem decisão", a_tela_nao_narra_commit),
    ("a tela não confessa dívida nossa", frases_que_confessam),
    ("máscara Nintendo Pro no FLAVORS", mascara_nintendo_pro),
    ("o «Virtual» liga o microfone", o_virtual_liga_o_microfone),
    ("cor única entre controles", cor_unica),
]


def main() -> int:
    print("A CONFERÊNCIA DELA — medida no PUBLICADO\n")
    esquerda, direita = [], []
    for titulo, regua in LINHAS:
        try:
            ok, nota = regua()
        except Exception as erro:  # a régua que quebra é vermelha, não verde
            ok, nota = False, f"a régua quebrou: {erro!r}"
        (esquerda if ok else direita).append((titulo, nota))
        print(f"  {'✓' if ok else '✗'}  {titulo}\n       {nota}")
    print()
    print(f"  ✓ na árvore: {len(esquerda)}     falta: {len(direita)}")
    if direita:
        print("\n  NÃO PASSA PARA O DEV — ordem dela: *\"se alguma [ficar n]a direita,")
        print("  ela não passa para o dev\"*. O que falta:")
        for titulo, nota in direita:
            print(f"    · {titulo}: {nota}")
        return 1
    print("\n  A COLUNA DA DIREITA ESTÁ VAZIA. Pode mergear.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
