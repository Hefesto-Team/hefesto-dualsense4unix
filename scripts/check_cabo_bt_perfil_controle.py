#!/usr/bin/env python3
"""A RÉGUA DE PRONTO de toda feature da tela — CABO-BT-PERFIL-CONTROLE-01.

**A palavra dela, 08/09/2026, à noite:**

    "Quero que vc modifique elas [as sprints] pra que tudo na interface seja
     possível os canais de audio as duas saidas as entradas, tudo funcionando
     por cabo ou bt ou tudo funcionando via perfil e dentro de cada um um
     setting pra cada controle é assim que eu queria que sua revisao nos  (noqa-acento: citação literal dela, palavra por palavra)
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
    # ---- o «Criar perfil para um jogo» (21/09/2026) ----
    # OS-LANCADORES-IGUAIS-E-A-LISTA-DE-EXCLUSAO-01. Ele só abre a escolha do
    # jogo; quem cria o perfil é o gravador da aba Perfis. Os quatro da lista
    # de exclusão NÃO entram aqui, e não por esquecimento: eles chegam pela
    # pintura do cartão, e esta régua lê a página estática — declará-los seria
    # razão sem dono, que a régua acusa.
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
    # ---- máquina e serviço: nada disso passa pelo controle ----
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
    # FATO SUBSTITUÍDO (11/09/2026, F2-POINT-AND-CLICK): esta linha dizia
    # *"grava um ponto de mira"*. Ponto de mira não existe em lugar nenhum
    # deste produto — o gesto é o "Guardar" do *Estilo Point-and-click*, e o
    # que ele grava é o que cada peça do controle faz naquele estilo, em
    # `Profile.button_actions`. A classificação estava certa (é do perfil, não
    # do aparelho); a descrição é que apontava para outra coisa.
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
    # ---- a seção «Rádio e Adaptadores» (TRANSPLANTE-DA-SECAO-01, 23/09/2026) ----
    # O desenho aprovado dela virou a cx8-3. Nenhum destes muda o DualSense:
    # ou abrem e fecham o que a tela já pintou, ou mexem no RÁDIO DA MÁQUINA
    # (qual adaptador, qual pareamento, o nome do lugar) — que é do BlueZ e do
    # `maquina.json`, não do perfil nem do controle.
    "abrir-adaptador": "abre um adaptador no acordeão — é da tela",
    "adaptador-historico": "abre o sino de um adaptador — é leitura do diário do rádio",
    "sugerir-alocacao": "mostra a sugestão da central para um adaptador — é da tela",
    "aceitar-sugestao": "abre a pergunta de mover a partir do balão — é da tela; "
                        "quem move é o `confirmar-mudanca`",
    "trazer-para-ca": "abre a lista de quem pode vir para este adaptador — é da tela",
    "cancelar-mudanca": "fecha a pergunta de mover — é da tela",
    "escolher-adaptador": "escolhe o adaptador do próximo «Conectar» — é da tela",
    "equilibrar-radio": "abre a proposta da central de rádio — é da tela",
    "confirmar-mudanca": "move um aparelho de adaptador (`radio.mover`) — é o rádio "
                         "da máquina: o controle continua o mesmo, com o mesmo perfil",
    "conectar-aparelho": "abre a janela de pareamento num adaptador (`radio.mover` "
                         "sem alvo) — é o rádio da máquina",
    "parear-aparelho": "pareia um aparelho achado num adaptador — é o rádio da máquina",
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
#: logo o que viaja no fio é `luz.lightbar.cor`.
#:
#: `luz.lightbar.brilho` é o byte de brilho do firmware, e a BRILHO-DE-HARDWARE-01
#: FECHOU na bancada dela em 09/09 derrubando a própria premissa: o `common[42]`
#: obedece nos dois transportes, mas o que ele atenua **são as lâmpadas de
#: numeração**, não a barra — palavra dela, com os quatro na mão. O mapa ganhou
#: `luz.led_jogador.brilho` por causa disso, e `luz.lightbar.brilho` continua
#: `aciona = não` agora por MEDIÇÃO, não por falta de olhar. A tela não oferece
#: nenhuma das duas.
DO_APARELHO: dict[str, tuple[str, ...]] = {
    "mascara": ("plataforma.vpad",),
    "ganho-mic": ("audio.microfone.ganho",),
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
    "brilho-luzes": ("luz.led_jogador.brilho",),
    "auto-cores": ("luz.lightbar.cor", "luz.led_jogador.escrita_hefesto"),
    # O INTERRUPTOR DE PUNHO da aba Vibração — 14/09/2026, quando ele deixou de
    # ser desenho (ordem dela: *"ele deveria ligar se > 0 no slicer dele"*).
    #
    # SÃO AS DUAS CHAVES, e não uma: o gesto é POR LADO, e cada punho tem a sua
    # linha no mapa. Declarar só uma faria o portão responder pela metade que
    # der melhor — a família do número que envelhece calado, que a nota do
    # `brilho` acima descreve.
    #
    # `vibracao.rumble.habilitar` NÃO é a chave deste gesto, e a distinção
    # importa: ela é o bit de habilitar do report (`parcial` nos dois
    # transportes). O que este interruptor mexe é a INTENSIDADE daquele motor —
    # 0 desliga, 100 devolve —, que é o mesmo trilho do `barra:motor` ao lado.
    "lado": ("vibracao.rumble.esquerdo", "vibracao.rumble.direito"),
    # O 🎙 DA LINHA DO CONTROLE na seção do rádio (TRANSPLANTE-DA-SECAO-01) é o
    # MESMO ato do `mudo` da 02 — o gesto dela, chamado (`a08_conexoes.custo_mic`).
    "custo-mic": ("audio.microfone.mudo",),
    # A MIRA VIRTUAL (A-MIRA-POR-MOVIMENTO-NA-TELA-01/02, publicada em 24/09):
    # é ARRANJO, não peça do plástico — o que ela lê do aparelho é o giro, e é
    # a linha dele que responde cabo e rádio. A matriz das duas sprints provou
    # os dois transportes, do P1 ao P4.
    "mira": ("movimento.giroscopio",),
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
#: **A LISTA ESTÁ VAZIA DESDE 09/09/2026, e a linha que saiu é o registro.** Ela
#: tinha UMA entrada, o `volume`, com esta razão: *"o trilho MEXE hoje, mas na
#: fonte do PipeWire — o byte do aparelho (`audio.microfone.volume`, output 0x02
#: common[6]) não é escrito por decisão tomada, e ninguém mediu se ele faz
#: algo"*. A bancada dela mediu (*"Deu certo. funciona"*, `docs/data/ensaios.csv`,
#: `folha-mic-volume-o-byte-age-cabo-0909`), ela mandou ligar o byte
#: (`D-0909-O-VOLUME-DO-MIC-LIGA-O-BYTE-DO-APARELHO`) e a MIC-VOLUME-02 ligou:
#: o gesto e o perfil escrevem o `common[6]` por `uniq`. **A linha sai porque
#: esta régua manda ela sair** — foi a metade "dívida que FECHOU" desta mordida
#: que reprovou a leva e cobrou o fecho, exatamente como desenhada.
#:
#: **E ELA REABRIU EM 20/09/2026, com UMA entrada e a sprint dona escrita.** O
#: **A DÍVIDA DO GANHO MORREU EM 21/09/2026, e quem a matou foi ela:** *"OS
#: DOIS SLICERS REFLETEM TANTO LÁ QUANTO NO JOGO E ISSO DEVE SER SALVO."*
#:
#: O que esta seção dizia — *"pede um leitor de placa que hoje só a interface
#: tem, e que o daemon precisaria para aplicar"* — era verdade e virou a cura:
#: o leitor saiu da aba e virou `integrations/ganho_do_microfone.py`, e quem
#: aplica na troca de perfil é `ProfileManager._aplicar_ganho_do_mic`. O campo
#: é `mic.gain`, nos dois níveis, e o gesto grava no `controllers[uniq]`.
#:
#: **A LIÇÃO FICA, porque ela é da casa:** a dívida estava escrita de forma
#: honesta e por isso não virou defeito — mas passou UM DIA declarada, e ela a
#: leu na tela antes de qualquer um de nós reler este arquivo. Dívida declarada
#: é melhor que dívida escondida; melhor ainda é a que não dura um dia.
A_DIVIDA_CONHECIDA: dict[str, tuple[str, str]] = {}

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
    "ganho-mic": ("mic", "mic"),
    "rota": ("speaker", "speaker"),
    "sensor": (None, "sensores"),
    "cor": ("leds", "leds"),
    "brilho": ("leds", "leds"),
    "apagar": ("leds", "leds"),
    "reenviar": ("leds", "leds"),
    "player": ("leds", "leds"),
    "brilho-luzes": ("leds", "leds"),
    "auto-cores": ("leds", "leds"),
    # O punho grava em `rumble` e é POR CONTROLE: `rumble.motores.set` leva o
    # `uniq`, e o valor mora em `controllers[<uniq>].rumble` — o mesmo lugar do
    # arraste da barra, porque é o mesmo número.
    "lado": ("rumble", "rumble"),
    # O 🎙 da seção do rádio grava pelo `mudo` da 02 (`_lembrar_do_som`), no
    # mesmo `controllers[<uniq>].mic` — é o mesmo gesto, chamado.
    "custo-mic": ("mic", "mic"),
    # A Mira grava em `movimento`, nos dois níveis: o default do perfil e o
    # `controllers[<uniq>].movimento` que o chip de cada cartão escreve.
    "mira": ("movimento", "movimento"),
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


#: AS QUATRO RESPOSTAS DE TRANSPORTE, e elas têm UM DONO — 09/09/2026.
#:
#: A palavra sem acento é VALOR CRU, não prosa: ela sai impressa na tabela e é
#: comparada contra o mapa. O portão de acentuação a reprova, e com razão — ele
#: não sabe distinguir dado de texto. A isenção é declarada AQUI, uma vez, em
#: vez de doze `noqa-acento` espalhados: dois agentes independentes chegaram a
#: este arquivo em 09/09 e escreveram doze marcadores CADA UM, com redações
#: diferentes — que é a assinatura do valor sem dono.
NAO = "nao"  # noqa-acento: valor cru do mapa (`*_aciona`), não prosa
_SEM_LINHA = "sem linha"
_RESSALVA = "com ressalva"
_SIM_ = "sim"
#: **«O APARELHO NÃO TEM ISSO NESTE TRANSPORTE» É RESPOSTA, NÃO DÍVIDA** —
#: 21/09/2026. O mapa já marcava esse fato em 163 linhas, no campo
#: `*_por_que_nao_aciona`, com o valor `nada-a-acionar`; esta régua não o
#: conhecia e lia todas como :data:`NAO`. O efeito era declarar dívida sobre o
#: transporte: o ganho do microfone não existe pelo rádio porque **não há placa
#: ALSA onde o elemento exista** (medido em 15/08: a placa segue o transporte),
#: e nenhuma sprint desta casa vai mudar isso.
#:
#: Ela fica ACIMA do :data:`NAO` na escada, e abaixo do `com ressalva`, porque é
#: resposta melhor do que *"não aciona e não sei dizer por quê"* e pior do que
#: *"aciona, com a dívida escrita"*. O que ela NÃO é: motivo de reprovação —
#: o filtro de falta cobra :data:`NAO` e `sem linha`, e esta não é nenhum dos
#: dois.

#: A ORDEM DAS RESPOSTAS, da pior para a melhor. Um gesto com duas chaves
#: responde pela PIOR: `min` sobre este índice.
_NAO_EXISTE = "nao existe no aparelho"  # noqa-acento: valor cru do mapa
_ESCADA = (_SEM_LINHA, NAO, _NAO_EXISTE, _RESSALVA, _SIM_)

#: O CONTROLE DESTA CASA. O mapa tem uma linha por (chave, controle) e as do
#: `pro` e do `sn30` dizem `não` em quase tudo — varrer todas e ficar com a
#: primeira que diz `sim` responderia pelo aparelho errado nos dois sentidos.
#: A tela é dos quatro DualSense (decisão dela de 06/09).
_O_APARELHO_DELA = "dualsense"


def _resposta_de_transporte(linhas: list[dict[str, str]], lado: str) -> str:
    """A resposta de um transporte: uma das quatro de `_ESCADA`.

    **`parcial` NÃO É `não`** — é o terceiro valor de `*_aciona` no mapa (24
    linhas por rádio, 22 por cabo, `docs/data/LEIA-PRIMEIRO.md`), e quer dizer
    *aciona, com a dívida escrita na ressalva*. Ler `parcial` como `não`
    reprovava em 09/09/2026 quatro features que funcionam na mesa dela — o
    microfone, o mudo e as cinco lâmpadas de jogador pelo rádio.
    """
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
