#!/usr/bin/env python3
"""A RÉGUA DE PRONTO de toda feature da tela — CABO-BT-PERFIL-CONTROLE-01."""
from __future__ import annotations

import csv
import pathlib
import re
import sys

RAIZ = pathlib.Path(__file__).resolve().parents[1]
PAGINAS = RAIZ / "src/hefesto_dualsense4unix/interface/paginas"
MAPA = RAIZ / "docs/data/mapa-controles.csv"
ESQUEMA = RAIZ / "src/hefesto_dualsense4unix/profiles/schema.py"
MAQUINA = RAIZ / "src/hefesto_dualsense4unix/utils/maquina.py"

_SIM = {"sim", "1", "true"}

#: deles toca o DualSense: são gestos de TELA (abrir, fechar, voltar ao
NAO_E_DO_APARELHO: dict[str, str] = {
    "escolher-na-fita": "escolhe qual controle a aba edita — não muda o aparelho",
    "fechar-definicoes": "fecha um painel da própria tela",
    "fechar-ponto": "fecha um painel da própria tela",
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
    "procurar-o-arquivo": "abre o seletor do sistema para ela apontar o "
                          "`.desktop` — é da máquina, e nada aqui toca o "
                          "controle",
    "copiar-registro": "copia o registro técnico para a área de transferência "
                       "— é leitura (o «Ver detalhes» saiu em 25/09/2026)",
    "criar-perfil-para-um-jogo": "abre a escolha do jogo para um perfil novo — "
                                 "é da tela",
    "mic-retorno": "liga e desliga o RETORNO do microfone — um `pw-loopback` "
                   "entre o nó de captura deste controle e a saída padrão. É "
                   "leitura do microfone mais uma tocada na saída, e não muda "
                   "estado nenhum: nem no aparelho, nem no perfil. **E NÃO "
                   "PERSISTE DE PROPÓSITO** — ela pediu *\"POR DEFAULT SEGUE "
                   "DESLIGADO\"* (21/09/2026), e um retorno que renascesse "
                   "ligado poria a voz dela no ar sem ninguém ter clicado. O "
                   "volume e o ganho que ele reflete são dos deslizantes ao "
                   "lado, que têm as quatro respostas por conta deles "
                   "(TESTAR-O-MICROFONE-01, 20/09/2026)",
    "hefesto": "liga e desliga o MODO do produto — é do serviço",
    "parar-ou-retomar": "para, retoma ou ativa o serviço — é systemd (o "
                        "«Parar» e o «Retomar» viraram um botão só em 25/09/2026)",
    "reiniciar": "reinicia o serviço — é systemd",
    "atualizar": "atualiza o produto — é da máquina",
    "autostart": "liga junto com o computador — é do sistema",
    "corrigir-modo": "conserta o modo de execução do serviço — é da máquina",
    "restaurar-de-fabrica": "devolve o perfil de fábrica — é do perfil",
    "aplicar-aos-jogos": "escreve a linha de inicialização na Steam — é do disco",
    "refazer-consertos": "refaz os consertos automáticos — é da máquina",
    "fixar-proton": "fixa ou solta o Proton dos jogos — é da máquina",
    "corrigir-vulkan": "tira ou devolve a sobreposição Vulkan — é da máquina",
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
    "luz-nao-acende": "declara que a luz não acende — é da máquina",
    "perfil-do-controle": "declara o Perfil de Desempenho deste controle no "
                          "`maquina.json` (`controles[uniq].economia`) — é da "
                          "máquina; o que ele faz no aparelho responde pelas "
                          "linhas do teto",
    "dono-renomear": "dá nome a quem joga com o controle, na memória dos controles "
                     "— é da máquina",
    "mapear-comecar": "o Mapear Entradas começa a olhar as portas — é da máquina",
    "mapear-gravar": "grava o nome e o lugar da porta da vez no mapa das portas do "
                     "`maquina.json` — é da máquina",
    "mapear-parar": "o Mapear Entradas para de olhar as portas — é da máquina",
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
    # `Profile.button_actions`. A classificação estava certa (é do perfil, não
    "guardar-ponto": "grava o que cada peça faz no Estilo Point-and-click — é "
                     "do perfil",
    "guardar-remapeamento": "grava o remapeamento — é do perfil",
    "guardar-teclas": "grava as teclas — é do perfil",
    "tecla-escrita": "digita uma tecla no campo — é da tela",
    "teclado": "abre o teclado virtual — é da tela",
    "linha-de-botao": "escolhe o que uma linha de botão faz — é da tela",
    "linha-de-troca": "escolhe o destino de uma linha da troca de botões — é da tela",
    "fechar-troca": "fecha um painel da própria tela",
    "acao-do-gesto": "escolhe a ação de um gesto — é do perfil",
    "navegacao-interna": "liga a navegação dentro do Hefesto — é da tela",
    "vel-cursor": "a velocidade do cursor — é da emulação de mouse, global (decisão dela)",
    "vel-rolagem": "idem",
    "pronto": "aplica o efeito já escolhido — o ATO é o do gesto `modo` da 03",
    # O desenho aprovado dela virou a cx8-3. Nenhum destes muda o DualSense:
    "abrir-adaptador": "abre um adaptador no acordeão — é da tela",
    "adaptador-reordenar": "grava a ordem em que ela arrastou as caixas dos adaptadores, "
                           "no `gui_prefs` — é da tela",
    "adaptador-historico": "abre o sino de um adaptador — é leitura do diário do rádio",
    "sugerir-alocacao": "mostra a sugestão da central para um adaptador — é da tela",
    "aceitar-sugestao": "abre a pergunta de mover a partir do balão — é da tela; "
                        "quem move é o `confirmar-mudanca`",
    "cancelar-mudanca": "fecha a pergunta de mover — é da tela",
    "escolher-adaptador": "escolhe o adaptador do próximo «Conectar» — é da tela",
    "equilibrar-radio": "abre a proposta da central de rádio — é da tela",
    "confirmar-mudanca": "move um aparelho de adaptador (`radio.mover`) — é o rádio "
                         "da máquina: o controle continua o mesmo, com o mesmo perfil",
    "conectar-aparelho": "abre o painel do «Conectar» (sem alvo, nada vai ao rádio); "
                         "com alvo, conecta um aparelho conhecido — é o rádio da máquina",
    "parear-aparelho": "pareia um aparelho achado num adaptador — é o rádio da máquina",
    "parear-o-pedido": "leva o controle conhecido que pede para parear ao adaptador que o ouve "
                       "(`radio.mover`) — é o rádio da máquina, para P1–P4",
    "tentar-de-novo": "liga a busca no mesmo adaptador da linha que não chegou "
                      "(`radio.busca.set`), ou refaz o mover do aparelho que não é "
                      "controle — é o rádio da máquina",
    "parear-de-novo": "esquece o par velho do controle que não conectou "
                      "(`esquecer_o_pareamento`) e liga a busca no mesmo adaptador — é o "
                      "rádio da máquina",
    "esquecer-aparelho": "o «Esquecer» do «⋮» abre a pergunta de esquecer — é da "
                         "tela",
    "confirmar-esquecer": "esquece o pareamento deste aparelho NESTE adaptador "
                          "(`esquecer_o_pareamento`) — é o rádio da máquina: os "
                          "outros adaptadores não se tocam",
    "radio-procurar": "liga e desliga a busca do rádio (`radio.busca.set`) — é o "
                      "rádio da máquina: o controle que já está no ar não muda",
    "aparelho-menu": "abre o «⋮» de um pareado — é da tela; quem esquece é o "
                     "`confirmar-esquecer`",
    "dispensar-linha": "tira a linha «Não Conectou» (`radio.dispensar`), lembrada "
                       "pela central — é do rádio da máquina, sem perfil nem controle",
    "ligar-mesmo-assim": "sobe a ponte de som além do limite do adaptador "
                         "(`radio.ponte.ligar_aqui`) — é do rádio da máquina, e o "
                         "som em si responde pelas linhas do `rota` e do `volume`",
    "adaptador-renomear": "dá nome ao LUGAR do adaptador no `maquina.json` — é da máquina",
    "aparelho-renomear": "dá nome a um aparelho no BlueZ (`Alias`) — é da máquina",
    "custo-som": "sem dono no produto (`a08_conexoes.SEM_GESTO`, com a razão): a "
                 "ponte sobe quando o JOGO manda som, e não há interruptor por "
                 "controle — o clique não muda nada",
    "custo-vibracao": "idem ao `custo-som`: a vibração pelo rádio viaja na mesma "
                      "ponte, e quem a sobe é o jogo",
    "custo-luz": "sem dono no produto (`a08_conexoes.SEM_GESTO`): a barra de luz "
                 "não custa rádio que se meça, e o interruptor dela é o da 04",
    "entrada-comecar": "começa o «Mapear Entrada a Entrada» — é da máquina "
                       "(as entradas do gabinete dela)",
    "entrada-face": "grava a face de uma entrada no `maquina.json` — é da máquina",
    "entrada-pular": "pula uma entrada da cerimônia — é da tela",
    "entrada-levantar": "passa a cerimônia para a fase em pé — é da tela",
    "entrada-nao-alcanco": "tira uma entrada da conta no `maquina.json` — é da máquina",
    "entrada-parar": "fecha a cerimônia — é da tela",
    "receptor-descobrir": "descobre a faixa do receptor 2.4G por eliminação e a grava no "
                          "`maquina.json` — é da máquina",
}

DO_APARELHO: dict[str, tuple[str, ...]] = {
    "mascara": ("plataforma.vpad",),
    "ganho-mic": ("audio.microfone.ganho",),
    "mudo": ("audio.microfone.mudo",),
    "volume": ("audio.microfone.volume", "audio.alto_falante.volume"),
    "rota": ("audio.alto_falante.rota",),
    "volume-padrao": ("audio.alto_falante.volume",),
    "sensor": ("movimento.giroscopio",),
    "cor": ("luz.lightbar.cor",),
    "brilho": ("luz.lightbar.cor",),
    "apagar": ("luz.lightbar.cor",),
    "reenviar": ("luz.lightbar.cor",),
    "player": ("luz.led_jogador.escrita_hefesto",),
    "brilho-luzes": ("luz.led_jogador.brilho",),
    "auto-cores": ("luz.lightbar.cor", "luz.led_jogador.escrita_hefesto"),
    "lado": ("vibracao.rumble.esquerdo", "vibracao.rumble.direito"),
    "custo-mic": ("audio.microfone.mudo",),
    "mira": ("movimento.giroscopio",),
    "inclinacao": ("movimento.acelerometro",),
    "toque": ("toque.touchpad.cursor", "toque.touchpad.dedos"),
    "haptica": ("vibracao.haptics_vcm",),
}

#: aplica na troca de perfil é `ProfileManager._aplicar_ganho_do_mic`. O campo
A_DIVIDA_CONHECIDA: dict[str, tuple[str, str]] = {
    "haptica": (  # sai com: O-FORJA-E-O-BANCO-DE-PROVA-DO-HEFESTO-01
        "2026-10-01-O-FORJA-E-O-BANCO-DE-PROVA-DO-HEFESTO-01.md",
        "a linha `vibracao.haptics_vcm@dualsense` do mapa segue em dívida nos dois "
        "transportes: o ganho grava e alcança a placa (cabo) e o conversor da ponte "
        "(rádio) com régua que morde, mas o grau do aparelho só sobe com a medida "
        "(o banco de prova, ou a mão dela nos Caminhos da Forja)",
    ),
}

NO_PERFIL: dict[str, tuple[str | None, str | None]] = {
    "mascara": ("mode", None),
    "volume": ("mic", "mic"),
    "ganho-mic": ("mic", "mic"),
    "rota": ("speaker", "speaker"),
    "volume-padrao": ("speaker", "speaker"),
    "sensor": (None, "sensores"),
    "cor": ("leds", "leds"),
    "brilho": ("leds", "leds"),
    "apagar": ("leds", "leds"),
    "reenviar": ("leds", "leds"),
    "player": ("leds", "leds"),
    "brilho-luzes": ("leds", "leds"),
    "auto-cores": ("leds", "leds"),
    "lado": ("rumble", "rumble"),
    "mira": ("movimento", "movimento"),
    "inclinacao": ("movimento", "movimento"),
    "toque": ("movimento", "movimento"),
    "haptica": (None, "rumble"),
}


NO_CONTROLE: dict[str, str] = {
    "mudo": "microfone_mudo",
    "custo-mic": "microfone_mudo",
}

_NO_CONTROLE = "no controle"


def gestos_da_tela() -> dict[str, list[str]]:
    """`{gesto: [abas]}` — LIDO das dez páginas publicadas, nunca digitado."""
    fora: dict[str, list[str]] = {}
    for pagina in sorted(PAGINAS.glob("*.html")):
        if not re.match(r"^\d\d-", pagina.name):
            continue
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


def _campos_do_esquema(classe: str, fonte: pathlib.Path = ESQUEMA) -> set[str]:
    """Os campos declarados numa classe do `schema.py` (ou de `fonte`), lidos do fonte."""
    texto = fonte.read_text(encoding="utf-8")
    corpo = texto.split(f"class {classe}(", 1)[-1].split("\nclass ", 1)[0]
    return set(re.findall(r"^    ([a-z_]+):\s", corpo, re.M))


#: vez de doze `noqa-acento` espalhados: dois agentes independentes chegaram a
NAO = "nao"  # noqa-acento: valor cru do mapa (`*_aciona`), não prosa
_SEM_LINHA = "sem linha"
_RESSALVA = "com ressalva"
_SIM_ = "sim"

_NAO_EXISTE = "nao existe no aparelho"  # noqa-acento: valor cru do mapa
_ESCADA = (_SEM_LINHA, NAO, _NAO_EXISTE, _RESSALVA, _SIM_)

#: A tela é dos quatro DualSense (decisão dela de 06/09).
_O_APARELHO_DELA = "dualsense"


def _resposta_de_transporte(linhas: list[dict[str, str]], lado: str) -> str:
    """A resposta de um transporte: uma das quatro de `_ESCADA`."""
    minhas = [l for l in linhas if l.get("controle") == _O_APARELHO_DELA]
    if not minhas:
        return _SEM_LINHA
    melhor = NAO
    for linha in minhas:
        aciona = linha.get(f"{lado}_aciona", "").strip().lower()
        porque = linha.get(f"{lado}_por_que_nao_aciona", "").strip().lower()
        if aciona not in _SIM and aciona != "parcial" and porque == "nada-a-acionar":
            resposta = _NAO_EXISTE
        elif aciona == "parcial":
            resposta = _RESSALVA
        elif aciona in _SIM:
            resposta = (_RESSALVA if linha.get(f"{lado}_ressalva", "").strip()
                        else _SIM_)
        else:
            continue
        if _ESCADA.index(resposta) > _ESCADA.index(melhor):
            melhor = resposta
    return melhor


def _pior(respostas: list[str]) -> str:
    """A pior de várias respostas — o gesto responde pela metade que falta."""
    return min(respostas, key=_ESCADA.index) if respostas else _SEM_LINHA


def tabela() -> list[tuple[str, str, str, str, str, str, str]]:
    """`(gesto, abas, cabo, radio, no_perfil, por_controle, o_que_falta)`."""
    mapa = _linhas_do_mapa()
    do_perfil = _campos_do_esquema("Profile")
    do_controle = _campos_do_esquema("ControllerOverrides")
    do_controle_declarado = _campos_do_esquema("ControleDeclarado", MAQUINA)
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
        if gesto in NO_CONTROLE:
            existe = NO_CONTROLE[gesto] in do_controle_declarado
            perfil = _NO_CONTROLE if existe else NAO
            controle = _SIM_ if existe else NAO
        else:
            campo, campo_ctrl = NO_PERFIL.get(gesto, ("", None))
            perfil = ("só por controle" if campo is None
                      else _SIM_ if campo in do_perfil else NAO)
            controle = ("global" if campo_ctrl is None
                        else (_SIM_ if campo_ctrl in do_controle else NAO))
        falta = "; ".join(
            p for p in (
                f"cabo: {cabo}" if cabo in (NAO, _SEM_LINHA) else "",
                f"rádio: {radio}" if radio in (NAO, _SEM_LINHA) else "",
                "não está no perfil" if perfil == NAO else "",
                "não é por controle" if controle == NAO else "",
            ) if p)
        fora.append((gesto, ",".join(abas), cabo, radio, perfil, controle, falta))
    return fora


def classificacao_morta() -> list[str]:
    """Gestos DECLARADOS aqui que a tela já não oferece."""
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
