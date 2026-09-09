#!/usr/bin/env python3
"""A RÉGUA DE PRONTO de toda feature da tela — CABO-BT-PERFIL-CONTROLE-01.

**A palavra dela, 08/09/2026, à noite:**

    "Quero que vc modifique elas [as sprints] pra que tudo na interface seja
     possível os canais de audio as duas saidas as entradas, tudo funcionando
     por cabo ou bt ou tudo funcionando via perfil e dentro de cada um um
     setting pra cada controle é assim que eu queria que sua revisao nos
     auxiliasse."
    (noqa-acento: citação literal dela, palavra por palavra)

É a definição de pronto dita como RÉGUA. **Toda feature que a tela oferece
responde QUATRO perguntas:**

1. funciona pelo **cabo**?
2. funciona pelo **rádio**?
3. fica **no perfil**?
4. e, dentro do perfil, é **por controle**?

Uma feature que não responde as quatro não está pronta.

O QUE ESTE PORTÃO LÊ, E O QUE ELE NÃO DIGITA
---------------------------------------------

**A LISTA DE FEATURES É LIDA DA TELA** — os `data-gesto` das dez páginas
publicadas. Digitá-la aqui faria a tabela envelhecer no dia em que nascer a
próxima feature, que é o defeito que esta casa nomeia dezenas de vezes.

O que se DECLARA (e não se adivinha) é a **classificação** de cada gesto: qual
linha do mapa responde por ele, ou por que ele não é feature de aparelho. É o
mesmo desenho do `_NAO_E_PROMESSA` do `casa-sabe`: *a lista se lê, a razão se
escreve*.

As três fontes das respostas:

===============  ===================================================
cabo / rádio     `docs/data/mapa-controles.csv` (`cabo_aciona`,
                 `radio_aciona`, e a ressalva de cada transporte)
no perfil        `profiles/schema.py` — o campo existe em `Profile`?
por controle     `profiles/schema.py` — existe em `ControllerOverrides`?
===============  ===================================================

    scripts/check_cabo_bt_perfil_controle.py            # reprova o que falta
    scripts/check_cabo_bt_perfil_controle.py --tabela   # imprime a tabela
"""
from __future__ import annotations

import csv
import pathlib
import re
import sys

RAIZ = pathlib.Path(__file__).resolve().parents[1]
PAGINAS = RAIZ / "src/hefesto_dualsense4unix/interface/paginas"
MAPA = RAIZ / "docs/data/mapa-controles.csv"
ESQUEMA = RAIZ / "src/hefesto_dualsense4unix/profiles/schema.py"

_SIM = {"sim", "1", "true"}

#: OS GESTOS QUE NÃO SÃO FEATURE DE APARELHO, com a razão de cada um. Nenhum
#: deles toca o DualSense: são gestos de TELA (abrir, fechar, voltar ao
#: padrão), de MÁQUINA (o serviço, o hub, o Proton) ou de PERFIL (salvar).
#:
#: **A RAZÃO SE ESCREVE, e "confie em mim" não é razão** — é a mesma
#: disciplina do `_NAO_E_PROMESSA`. Um gesto novo que não estiver aqui nem no
#: mapa REPROVA, e é essa a mordida que importa: a próxima feature nasce com a
#: régua em cima dela.
NAO_E_DO_APARELHO: dict[str, str] = {
    # ---- tela: navegar, abrir, fechar, voltar ao padrão ----
    "escolher-na-fita": "escolhe qual controle a aba edita — não muda o aparelho",
    "fechar-definicoes": "fecha um painel da própria tela",
    "fechar-teclas": "fecha um painel da própria tela",
    "padrao-da-aba": "devolve a aba ao desenho — é da tela",
    "padrao-da-tecla": "devolve UMA tecla ao padrão — é do mapeamento, não do aparelho",
    "padrao-definicoes": "devolve as definições ao padrão — é do perfil",
    "padrao-remapeamento": "devolve o remapeamento ao padrão — é do perfil",
    "vizinho-o-que-e": "abre a explicação de um vizinho de porta — é texto",
    "detectar": "detecta o jogo aberto — é leitura da máquina",
    "procurar": "reprocura os lançadores — é leitura do disco",
    "abrir-lancador": "abre um programa da máquina dela",
    "adicionar-lancador": "registra onde um lançador está — é da máquina",
    "ver-detalhes": "joga o registro técnico no painel — é leitura",
    "ver-plugins": "lista os plugins do daemon — é leitura",
    # ---- máquina e serviço: nada disso passa pelo controle ----
    "hefesto": "liga e desliga o MODO do produto — é do serviço",
    "desligar": "para o serviço — é systemd",
    "retomar": "retoma o serviço — é systemd",
    "reiniciar": "reinicia o serviço — é systemd",
    "atualizar": "atualiza o produto — é da máquina",
    "autostart": "liga junto com o computador — é do sistema",
    "corrigir-modo": "conserta o modo de execução do serviço — é da máquina",
    "restaurar-de-fabrica": "devolve o perfil de fábrica — é do perfil",
    "aplicar-aos-jogos": "escreve a linha de inicialização na Steam — é do disco",
    "refazer-consertos": "refaz os consertos automáticos — é da máquina",
    "refazer-proton": "refixa o Proton — é da máquina",
    "procurar-camadas": "procura camadas Vulkan — é da máquina",
    "perfil-da-mesa": "escolhe o perfil de energia — é do daemon",
    "examinar-portas": "examina as portas USB — é leitura do barramento",
    "escolher-aparelho": "escolhe o aparelho da aba Conexões — é da tela",
    "escolher-entrada": "escolhe a entrada — é da tela",
    "nova-entrada": "declara uma entrada nova — é da máquina",
    "nova-extensao": "declara uma extensão nova — é da máquina",
    "nova-face": "declara uma face do gabinete — é da máquina",
    "novo-hub": "declara um hub — é da máquina",
    "sala-altura": "a altura do gabinete no desenho — é da máquina",
    "sala-visada": "a visada do desenho — é da tela",
    "tirar-daqui": "tira uma declaração da máquina",
    "ignorar": "ignora um aparelho — é da máquina",
    "alvo": "escolhe o alvo do exame — é da tela",
    "mic-existe": "declara que o microfone existe — é da máquina",
    "luz-nao-acende": "declara que a luz não acende — é da máquina",
    "todos": "aplica a todos os aparelhos da aba Conexões — é da máquina",
    "teto-da-vibracao": "o teto do orçamento do cabo — é do barramento, não do controle",
    # ---- perfil e modo: decididos por ela como GLOBAIS ----
    "modo": "o efeito do gatilho (03) e o modo de navegação (06) — o gesto tem "
            "dois donos, e os dois caem em linhas do mapa por outro gesto",
    "modo-dualsense": "o modo é UM para todos — decisão dela de 08/09 "
                      "(`D-0809-O-MODO-E-UM-PARA-TODOS-OS-CONTROLES`)",
    "modo-navegacao": "idem",
    "modo-steam": "idem",
    "modo-xbox": "idem",
    "cadeado": "trava o perfil ativo — é do perfil",
    "reconectar": "reconcilia os jogadores — é da mesa, não de um controle",
    "guardar": "guarda o efeito no perfil — o ATO já é medido pelo gesto do efeito",
    "em-todos": "espalha o efeito — o ATO é o mesmo do gesto do efeito",
    "guardar-definicoes": "grava no perfil — é do perfil",
    "guardar-ponto": "grava um ponto de mira — é do perfil",
    "guardar-remapeamento": "grava o remapeamento — é do perfil",
    "guardar-teclas": "grava as teclas — é do perfil",
    "tecla-escrita": "digita uma tecla no campo — é da tela",
    "teclado": "abre o teclado virtual — é da tela",
    "linha-de-botao": "escolhe a linha do botão a remapear — é da tela",
    "acao-do-gesto": "escolhe a ação de um gesto — é do perfil",
    "navegacao-interna": "liga a navegação dentro do Hefesto — é da tela",
    "vel-cursor": "a velocidade do cursor — é da emulação de mouse, global (decisão dela)",
    "vel-rolagem": "idem",
    "pronto": "aplica o efeito já escolhido — o ATO é o do gesto `modo` da 03",
}

#: OS GESTOS QUE SÃO FEATURE DE APARELHO, e as linhas do mapa que respondem
#: por eles. A CHAVE do mapa não se adivinha do nome do gesto: `cor` responde
#: por `luz.lightbar.cor`, e nenhuma regra de string liga os dois.
#:
#: **SÃO VÁRIAS CHAVES POR GESTO, e a resposta é a PIOR delas.** Um gesto com
#: dois atos no aparelho só está pronto quando os dois chegam: o `volume` da 02
#: mexe no microfone OU no alto-falante conforme o `data-qual`, e o `auto-cores`
#: da 04 governa a paleta E a numeração. Responder pela melhor metade é a
#: família do número que envelhece calado.
#:
#: **O `brilho` NÃO É `luz.lightbar.brilho`** — e a distinção custou uma
#: reprovação falsa em 09/09/2026. O trilho da tela termina em
#: `_escrever_a_cor` (`a04_iluminacao.py:2909`): ele manda RGB JÁ ESCALADO,
#: logo o que viaja no fio é `luz.lightbar.cor`. `luz.lightbar.brilho` é o BYTE
#: de brilho do firmware, que a tela não oferece e cujo caminho ninguém conhece
#: — é o objeto da BRILHO-DE-HARDWARE-01, sprint de bancada aberta.
DO_APARELHO: dict[str, tuple[str, ...]] = {
    "mascara": ("plataforma.vpad",),
    "mic-modo": ("audio.microfone",),
    "mudo": ("audio.microfone.mudo",),
    "volume": ("audio.microfone.volume", "audio.alto_falante.volume"),
    "rota": ("audio.alto_falante.rota",),
    "sensor": ("movimento.giroscopio",),
    "cor": ("luz.lightbar.cor",),
    "brilho": ("luz.lightbar.cor",),
    "apagar": ("luz.lightbar.cor",),
    "reenviar": ("luz.lightbar.cor",),
    "player": ("luz.led_jogador.escrita_hefesto",),
    "auto-cores": ("luz.lightbar.cor", "luz.led_jogador.escrita_hefesto"),
}

#: A DÍVIDA CONHECIDA — o gesto que HOJE não responde as quatro, com a sprint
#: que é dona dela. Ela não deixa o portão vermelho para sempre, e **morde nos
#: DOIS sentidos**:
#:
#: * dívida NOVA (gesto que falta e não está aqui) reprova;
#: * dívida que FECHOU (está aqui e já responde as quatro) reprova TAMBÉM,
#:   pedindo que a linha saia. Sem isso a lista vira propaganda no dia seguinte
#:   à primeira cura — é a mesma régua do `divida-fechada` do
#:   `check_paridade_gtk_html.py`.
A_DIVIDA_CONHECIDA: dict[str, tuple[str, str]] = {
    "volume": (
        "2026-09-09-MIC-VOLUME-02-o-byte-do-aparelho-medido-e-ligado-ao-campo.md",
        "o trilho MEXE hoje, mas na fonte do PipeWire — o byte do aparelho "
        "(`audio.microfone.volume`, output 0x02 common[6]) não é escrito por "
        "decisão tomada, e ninguém mediu se ele faz algo. A bancada de "
        "MIC-VOLUME-02 decide: byte que o aparelho não obedece não ganha campo",
    ),
}

#: ONDE CADA FEATURE MORA NO PERFIL — `(campo do Profile, campo do
#: ControllerOverrides)`.
#:
#: `None` NA SEGUNDA POSIÇÃO é *"decidido como global"*, e a razão fica no
#: `NAO_E_DO_APARELHO` ou na sprint.
#:
#: `None` NA PRIMEIRA é **"só por controle, sem default global"**, e é uma
#: resposta legítima: `ControllerOverrides.sensores` existe desde 04/09
#: (SENSOR-DE-VERDADE-01) e `Profile` NÃO tem `sensores` — o giroscópio é do
#: aparelho, e não faz sentido um default para a mesa toda. Medido no fonte em
#: 09/09/2026; sem esta distinção a régua reprovava o sensor por "não está no
#: perfil", quando ele está — no lugar certo.
NO_PERFIL: dict[str, tuple[str | None, str | None]] = {
    "mascara": ("mode", None),
    "mic-modo": ("mic", "mic"),
    "mudo": ("mic", "mic"),
    "volume": ("mic", "mic"),
    "rota": ("speaker", "speaker"),
    "sensor": (None, "sensores"),
    "cor": ("leds", "leds"),
    "brilho": ("leds", "leds"),
    "apagar": ("leds", "leds"),
    "reenviar": ("leds", "leds"),
    "player": ("leds", "leds"),
    "auto-cores": ("leds", "leds"),
}


def gestos_da_tela() -> dict[str, list[str]]:
    """`{gesto: [abas]}` — LIDO das dez páginas publicadas, nunca digitado."""
    fora: dict[str, list[str]] = {}
    for pagina in sorted(PAGINAS.glob("*.html")):
        if not re.match(r"^\d\d-", pagina.name):
            continue  # os desenhos auxiliares não são aba
        texto = pagina.read_text(encoding="utf-8")
        for gesto in sorted(set(re.findall(r'data-gesto="([a-z0-9_@:.-]+)"', texto))):
            fora.setdefault(gesto, []).append(pagina.stem[:2])
    return fora


def _linhas_do_mapa() -> dict[str, list[dict[str, str]]]:
    with MAPA.open(newline="", encoding="utf-8") as f:
        linhas = list(csv.DictReader(f))
    fora: dict[str, list[dict[str, str]]] = {}
    for linha in linhas:
        fora.setdefault(linha.get("chave", ""), []).append(linha)
    return fora


def _campos_do_esquema(classe: str) -> set[str]:
    """Os campos declarados numa classe do `schema.py`, lidos do fonte.

    LÊ O FONTE E NÃO IMPORTA O MÓDULO: o `pydantic` do produto puxa metade do
    motor, e este portão roda na camada rápida.
    """
    texto = ESQUEMA.read_text(encoding="utf-8")
    corpo = texto.split(f"class {classe}(", 1)[-1].split("\nclass ", 1)[0]
    return set(re.findall(r"^    ([a-z_]+):\s", corpo, re.M))


#: A ORDEM DAS RESPOSTAS DE TRANSPORTE, da pior para a melhor. Um gesto com
#: duas chaves responde pela PIOR: `min` sobre este índice.
_ESCADA = ("sem linha", "nao", "com ressalva", "sim")

#: O CONTROLE DESTA CASA. O mapa tem uma linha por (chave, controle) e as do
#: `pro` e do `sn30` dizem `não` em quase tudo — varrer todas e ficar com a
#: primeira que diz `sim` responderia pelo aparelho errado nos dois sentidos.
#: A tela é dos quatro DualSense (decisão dela de 06/09).
_O_APARELHO_DELA = "dualsense"


def _resposta_de_transporte(linhas: list[dict[str, str]], lado: str) -> str:
    """`sim`, `com ressalva`, `nao` ou `sem linha` para aquele transporte.

    **`parcial` NÃO É `não`** — é o terceiro valor de `*_aciona` no mapa (24
    linhas por rádio, 22 por cabo, `docs/data/LEIA-PRIMEIRO.md`), e quer dizer
    *aciona, com a dívida escrita na ressalva*. Ler `parcial` como `não`
    reprovava em 09/09/2026 quatro features que funcionam na mesa dela — o
    microfone, o mudo e as cinco lâmpadas de jogador pelo rádio.
    """
    minhas = [l for l in linhas if l.get("controle") == _O_APARELHO_DELA]
    if not minhas:
        return "sem linha"
    melhor = "nao"
    for linha in minhas:
        aciona = linha.get(f"{lado}_aciona", "").strip().lower()
        if aciona == "parcial":
            resposta = "com ressalva"
        elif aciona in _SIM:
            resposta = ("com ressalva" if linha.get(f"{lado}_ressalva", "").strip()
                        else "sim")
        else:
            continue
        if _ESCADA.index(resposta) > _ESCADA.index(melhor):
            melhor = resposta
    return melhor


def _pior(respostas: list[str]) -> str:
    """A pior de várias respostas — o gesto responde pela metade que falta."""
    return min(respostas, key=_ESCADA.index) if respostas else "sem linha"


def tabela() -> list[tuple[str, str, str, str, str, str, str]]:
    """`(gesto, abas, cabo, radio, no_perfil, por_controle, o_que_falta)`."""
    mapa = _linhas_do_mapa()
    do_perfil = _campos_do_esquema("Profile")
    do_controle = _campos_do_esquema("ControllerOverrides")
    fora = []
    for gesto, abas in sorted(gestos_da_tela().items()):
        if gesto in NAO_E_DO_APARELHO:
            continue
        chaves = DO_APARELHO.get(gesto)
        if chaves is None:
            fora.append((gesto, ",".join(abas), "?", "?", "?", "?",
                         "gesto sem classificação — nem feature de aparelho "
                         "nem gesto de tela"))
            continue
        cabo = _pior([_resposta_de_transporte(mapa.get(c, []), "cabo")
                      for c in chaves])
        radio = _pior([_resposta_de_transporte(mapa.get(c, []), "radio")
                       for c in chaves])
        campo, campo_ctrl = NO_PERFIL.get(gesto, ("", None))
        perfil = ("só por controle" if campo is None
                  else "sim" if campo in do_perfil else "nao")
        controle = ("global" if campo_ctrl is None
                    else ("sim" if campo_ctrl in do_controle else "nao"))
        falta = "; ".join(
            p for p in (
                f"cabo: {cabo}" if cabo in ("nao", "sem linha") else "",
                f"rádio: {radio}" if radio in ("nao", "sem linha") else "",
                "não está no perfil" if perfil == "nao" else "",
                "não é por controle" if controle == "nao" else "",
            ) if p)
        fora.append((gesto, ",".join(abas), cabo, radio, perfil, controle, falta))
    return fora


def classificacao_morta() -> list[str]:
    """Gestos DECLARADOS aqui que a tela já não oferece.

    A terceira mordida, e ela fecha o ciclo: a lista de features se LÊ da tela,
    mas a classificação se ESCREVE — e escrita envelhece. Um gesto que saiu da
    tela e ficou aqui é uma razão a explicar coisa nenhuma, que a próxima
    pessoa lê como se ainda valesse.
    """
    na_tela = set(gestos_da_tela())
    return sorted((set(NAO_E_DO_APARELHO) | set(DO_APARELHO)) - na_tela)


def main() -> int:
    linhas = tabela()
    mortas = classificacao_morta()
    if "--tabela" in sys.argv:
        print(f"{'gesto':18} {'abas':6} {'cabo':13} {'rádio':13} "
              f"{'perfil':16} {'controle':9} o que falta")
        print("-" * 110)
        for g, abas, cabo, radio, perfil, ctrl, falta in linhas:
            print(f"{g:18} {abas:6} {cabo:13} {radio:13} {perfil:16} "
                  f"{ctrl:9} {falta}")
        print()

    if mortas:
        print(f"VERMELHO: {len(mortas)} gesto(s) classificados aqui que a tela "
              f"já não oferece — a razão ficou sem dono:")
        for gesto in mortas:
            print(f"  {gesto}")
        return 1

    faltando = {linha[0]: linha[6] for linha in linhas if linha[6]}
    nova = {g: f for g, f in faltando.items() if g not in A_DIVIDA_CONHECIDA}
    fechou = [g for g in A_DIVIDA_CONHECIDA if g not in faltando]

    if nova:
        print(f"VERMELHO: {len(nova)} feature(s) da tela sem as quatro "
              f"respostas, e nenhuma delas está declarada:")
        for gesto, falta in sorted(nova.items()):
            abas = next(l[1] for l in linhas if l[0] == gesto)
            print(f"  [{abas}] {gesto}: {falta}")
        print()
        print("Toda feature que a tela oferece responde: cabo? rádio? no "
              "perfil? por controle? Quem não responde as quatro não está "
              "pronta — é a régua dela de 08/09/2026. Cure, ou declare em "
              "`A_DIVIDA_CONHECIDA` com a sprint que é dona.")
        return 1

    if fechou:
        print(f"VERMELHO: {len(fechou)} dívida(s) declarada(s) já respondem as "
              f"quatro — a declaração ficou velha e vira propaganda:")
        for gesto in sorted(fechou):
            sprint, _razao = A_DIVIDA_CONHECIDA[gesto]
            print(f"  {gesto}: tire a linha de `A_DIVIDA_CONHECIDA` e feche a "
                  f"{sprint}")
        return 1

    print(f"VERDE: {len(linhas)} feature(s) de aparelho na tela · "
          f"{len(linhas) - len(faltando)} com as quatro respostas · "
          f"{len(faltando)} em dívida declarada · "
          f"{len(NAO_E_DO_APARELHO)} gesto(s) que não são do aparelho")
    for gesto, falta in sorted(faltando.items()):
        sprint, razao = A_DIVIDA_CONHECIDA[gesto]
        print(f"  dívida: {gesto} — {falta} · {razao} · dona: {sprint}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
