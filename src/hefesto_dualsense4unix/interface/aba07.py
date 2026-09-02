# A PASTA, não /tmp: estas três liam um `monta` de /tmp — o de 26/08 23:50 —
# que por sua vez lia um `topo.html` de /tmp parado às 10:59. Três das dez
# abas vinham de um montador e de um esqueleto de ontem, e nenhuma correção
# no topo.html desta pasta as alcançava. Achado em 27/08.
import sys, pathlib; sys.path.insert(0, str(pathlib.Path(__file__).parent))
# `MESA` SAIU DO IMPORT em 02/09/2026, e a razão é a mesma que mudou a régua da
# promessa: os cartões deixaram de contar controle. `CONECTADOS` fica — ele
# ainda responde pelo texto do "?" ("a resposta vale igual para os N").
from monta import CONECTADOS, monta

# O DESENHO DOS CARTÕES TEM UM DONO SÓ, e ele é o mesmo que o pacote
# `pacotes/a07_lancadores.py` usa em tempo de execução. Enquanto os cartões
# moravam AQUI, os números eram digitados — `412 jogos`, `28 jogos`, `3 jogos já
# sabem por onde entrar` — e o produto não tinha por onde contradizê-los.
# Medido em 02/09/2026 na máquina dela: 23 jogos instalados, 63 appids com o
# atalho no vdf, 0 pontes confirmadas. Quatro números, quatro contradições.
#
# `cartoes(None)` é o estado da PRIMEIRA MEIA VOLTA — o que a tela mostra antes
# de a leitura de disco voltar. É o único desenho honesto para uma página
# estática: ela não sabe nada da biblioteca dela até o produto abrir.
import desenho_dos_lancadores as dl

# ---------------------------------------------------------------------------
# A MESA RESPONDE PELO NÚMERO — aqui não se escreve "quatro".
#
# Pedido dela, 27/08: cada aba reescrita para quatro controles conectados. Nesta
# aba o que muda NÃO é o desenho (ela fechou: *"lançadores perfeito parabéns"*) e
# não é feature nova (ela: *"essa aba em si só vamos desenhar e deixar placeholder
# mesmo"*). O que muda é o ALCANCE DA PROMESSA: a aba dizia "o controle chega", no
# singular, com quatro na mesa — e a primeira pergunta de quem lê passa a ser
# *"qual deles?"*.
#
# A resposta é: os quatro, e por uma razão medida — nenhum dos cinco impedimentos
# desta aba depende de controle. `integrations/prontuario_dos_jogos.py` não tem
# UMA função que receba controle, MAC, device ou transporte: `SEM_WRAPPER`,
# `LINHA_INTOCAVEL`, `EXCECAO_INERTE`, `PONTE_DIVERGENTE` e `SEM_EXECUTAVEL` são
# fatos do jogo em disco (`:139-143`), e as duas curas de `_CURAS` (`:878`) mexem
# na linha de inicialização e na exceção do Steam Input. É o mesmo motivo pelo
# qual a fita desta aba nasce esmaecida (`fita_viva=False`, no fim do arquivo).
#
# Por isso o número sai de `MESA` e não do teclado: no dia em que a mesa mudar, o
# texto dos cartões muda junto com o cabeçalho, que já sai de lá.
# QUEM CONTA CONTROLE CONTA QUEM ESTÁ NA MESA — 31/08/2026. A `MESA` passou a ter
# um campo `conectado`, e com ele dois lugares vazios: esta aba prometia que "os 4
# controles chegam" com dois deles fora, em QUATRO cartões de lançador. A promessa
# não era pouca — ela é o que a aba existe para dizer.
#
# `MESA` continua sendo a lista dos quatro LUGARES; `CONECTADOS` é quem está neles.
N_CTRL = len(CONECTADOS)
N_USB = sum(1 for c in CONECTADOS if c["via"] == "USB")
N_BT = sum(1 for c in CONECTADOS if c["via"] == "BT")

#: A promessa de um cartão que não impede nada, no plural da mesa.
CHEGAM = f"Os {N_CTRL} controles chegam."

CSS = """
  /* ---------- Lançadores ---------- */
  .lancadores{display:grid;grid-template-columns:1fr 1fr;gap:10px}
  .lanc{border:1px solid var(--border-sutil);border-radius:8px;background:var(--app-bg);padding:11px 13px}
  .lanc.chega{border-color:rgba(80,250,123,.28)}
  .lanc.impede{border-color:var(--orange)}
  /* O CARTÃO "não achei" DEIXOU DE USAR `opacity` — 30/08/2026, mesma cura da
     `.fita.inerte` (topo.html) e pelo mesmo motivo medido: com `opacity:.5` o
     corpo caía a 2,55:1, o selo NÃO ACHEI a 1,95:1 e os dois botões a 3,37 e
     3,55:1 — e nenhuma régua que leia `color` enxergava, porque a opacidade
     estava no PAI. Este cartão não é controle desabilitado: ele é informação
     viva ("instale e clique em Procurar de novo"), e informação se lê. */
  .lanc.ausente{background:transparent}
  .lanc.ausente .lanc-nome{color:var(--texto-suave)}
  .lanc.ausente .lanc-diz,
  .lanc.ausente .lanc-jogos{color:var(--comment)}
  .lanc-topo{display:flex;align-items:center;gap:9px;margin-bottom:7px}
  .lanc-nome{font-size:12.5px;font-weight:600;color:var(--fg)}
  .lanc-selo{font-size:10px;padding:2px 7px;border-radius:4px;font-weight:600;
             font-family:'JetBrains Mono',monospace}
  .lanc-selo.ok{background:var(--green);color:var(--app-bg)}
  .lanc-selo.warn{background:var(--orange);color:var(--app-bg)}
  /* o selo apagado ficava a 3,47:1 sobre o próprio fundo — o texto claro
     dá 9,3:1 e o selo continua lendo como "desligado" pelo fundo cinza. */
  /* `nao_sei` DIVIDE O ESTILO COM `off`, e é decisão: as duas dizem "não há o
     que agir aqui", e um terceiro tom só acrescentaria uma cor para ela
     decodificar. O selo nasceu em 02/09/2026, quando a medição mostrou que
     `CHEGAM` e `NÃO CHEGAM` eram as duas afirmações que o produto NÃO pode
     fazer sobre Heroic, Lutris, RetroArch, Dolphin e mGBA — ele não tem uma
     função sequer que olhe para eles. */
  .lanc-selo.off,.lanc-selo.nao_sei{background:var(--border-forte);color:var(--texto-suave)}
  .lanc-jogos{margin-left:auto;font-size:11px;color:var(--texto-mudo);
              font-family:'JetBrains Mono',monospace}
  /* DUAS LINHAS CRAVADAS, e é `height` — não `min-height`.
     Com `min-height:32px` o corpo de uma linha dava 32px e o de duas 33,3px, e a
     fileira de botões dos dois cartões de uma mesma linha nascia 1,3px torta. A
     escala do esqueleto tropeçou nisto uma vez (LEIA-ME, cicatriz 2): min-height
     não encolhe, e aqui também não ESTICA — quem alinha é a altura fixa.
     2,9em = 1,45 (line-height) × 2 linhas, então o número acompanha a fonte. */
  /* A ALTURA FIXA CAIU — 02/09/2026, e foi a FOTO que a derrubou.
     Aqui morava `height:2.9em` ("duas linhas cravadas"), e ela existia para
     alinhar a fileira de botões dos dois cartões de uma mesma linha da grade:
     com `min-height` o corpo de uma linha dava 32px e o de duas 33,3px, e a
     fileira nascia 1,3px torta.
     Ela só funcionava porque o texto era ESCRITO À MÃO e cabia em duas linhas.
     Com o corpo vindo do produto isso acabou: a frase da sentinela — que
     nomeia o jogo e diz o que vai acontecer — tem CINCO linhas, e na primeira
     foto da aba viva ela atravessou os botões por cima. Um transbordo de 3
     linhas é muitas ordens de grandeza pior que 1,3px de desalinho.
     O ALINHAMENTO NÃO SE PERDEU, e é o ponto: quem alinha agora é o cartão,
     não o parágrafo. `.lanc` vira coluna flex, a grade já iguala a ALTURA dos
     cartões irmãos (é `grid`), e `.acoes{margin-top:auto}` empurra a fileira
     para o pé — os dois cartões da mesma linha ficam com os botões na MESMA
     altura, exatos, com corpos de tamanhos diferentes. O `min-height` continua
     para o caso curto, que é o que reservava a segunda linha. */
  .lanc{display:flex;flex-direction:column}
  .lanc-diz{font-size:11.5px;color:var(--texto-mudo);min-height:2.9em;line-height:1.45}
  .lanc-diz b{color:var(--orange)}
  .lanc-diz b.roxo-txt{color:var(--purple)}
  /* `margin-top:auto` E NÃO `8px`: é ele que empurra a fileira para o PÉ do
     cartão, e é o que substitui a altura fixa do corpo (ver acima). O vão de
     8px vira `padding-top`, para o caso do cartão curto em que o `auto` não
     tem folga para consumir. */
  .lanc .acoes{margin-top:auto;padding-top:8px;gap:6px}
  /* O BOTÃO DENTRO DO CARTÃO NÃO ENCOLHE. Aqui morava
     `.lanc .btn{font-size:11px;padding:0 11px}`, e era a ÚNICA quebra de "mesma
     família, mesma largura" das dez abas: `Procurar de novo` — o MESMO texto, a
     MESMA classe `btn` — media **130,5px** na fileira do quadro e **114,2px**  (noqa-acento: verbo medir, imperfeito)
     dentro do cartão do `Dolphin · mGBA`, porque a regra trocava a fonte (12,5
     → 11px) e o vão lateral (13 → 11px) só de um lado. Dois botões iguais em
     tamanhos diferentes na mesma tela é o que faz a janela parecer montada por
     pessoas diferentes.
     A altura já vinha certa (34px, do `--h-acao` do esqueleto): a regra não a
     tocava, e por isso a régua de alinhamento passava verde — ela mede altura,
     não largura. Sem a regra, o `.btn` do `topo.html` responde pelos onze
     botões da aba, e a fileira mais larga (o RetroArch, com `Aplicar o estilo
     Retrô/Emulador`) continua cabendo no cartão sem quebrar linha — o que
     importa porque `.acoes` tem `flex-wrap:wrap` e uma quebra devolveria a
     altura que o carimbo acabou de economizar. */
  /* O CARIMBO MORA NA FILEIRA DOS BOTÕES, à direita — e não numa linha própria
     acima dela. Medido em 28/08: como linha própria ele custava 21px (6 de
     margem + 13 de altura + 2 de arredondamento) que SÓ o cartão do Steam
     pagava, e a fileira dele nascia em y=370,3 contra y=349,3 do Heroic, ao
     lado. Os outros dois pares batiam exato, o que provava que era defeito.
     A cura é a dela: ENCOLHER O MAIS ALTO. Reservar a linha vazia nos outros
     cinco cartões alinharia igual, mas engordando a aba em 63px — o inverso da
     regra, e numa aba que já passa da dobra.
     Aqui ele também casa com `.lanc-jogos`, que é o outro texto à direita do
     cartão: um no alto, um no pé. `nowrap` porque `.acoes` quebra linha, e uma
     quebra devolveria os 21px pela porta dos fundos. */
  .carimbo{display:inline-flex;align-items:center;gap:5px;font-size:10.5px;color:var(--green);
           margin-left:auto;white-space:nowrap}
  /* A LISTA DE JOGOS DENTRO DO CARTÃO — 02/09/2026, e ela NASCE VAZIA.
     Na máquina dela, hoje, os 63 jogos com o atalho estão todos em ordem e a
     lista não ocupa um pixel: `linhas_de_jogos([])` devolve string vazia, e o
     bloco fica com altura zero. Ela só aparece quando há o que dizer — que é a
     mesma regra do carimbo, e o motivo de o cartão não engordar por existir.
     Sem ela não haveria onde pôr o "tirar/voltar a usar" POR JOGO, e a lista
     `jogos_sem_wrapper.txt` continuaria sendo um arquivo que só se edita à mão. */
  .lanc-fora:not(:empty){margin-top:8px;border-top:1px solid var(--border-sutil);padding-top:7px;
                         display:flex;flex-direction:column;gap:5px}
  .lanc-jogo{display:flex;align-items:center;gap:8px;font-size:11px}
  .lanc-jogo-nome{color:var(--fg);overflow:hidden;text-overflow:ellipsis;white-space:nowrap}
  .lanc-jogo-porque{color:var(--texto-mudo);margin-left:auto;white-space:nowrap}
  /* O `mini` é o ÚNICO botão menor da aba, e a razão é diferente da que fez o
     `.lanc .btn` ser removido: lá dois botões IGUAIS mediam diferente por
     acidente de CSS; aqui a linha de jogo é uma fileira densa, e um botão de
     34px por jogo empurraria a lista para fora do cartão. */
  .lanc-fora .btn.mini{height:24px;font-size:10.5px;padding:0 9px;flex:0 0 auto}
  .lanc-vazio{font-size:11px;color:var(--comment)}
"""

# OS CARTÕES SAEM DO DESENHO, e a lista deixou de ser digitada. Ela era seis
# dicionários com os selos e as contagens escritos à mão; agora é o que
# `dl.cartoes(None)` devolve — os mesmos seis cartões que o produto monta, no
# estado "ainda não li o disco".
#
# A CONTAGEM DO QUADRO CONTINUA DERIVADA, e agora de uma fonte que o produto
# também usa: `Quadro.achados` conta os cartões cujo selo AFIRMA algo (`ok` ou
# `warn`), e os cinco `NÃO SEI` ficam de fora pelo mesmo motivo pelo qual o
# `NÃO ACHEI` já ficava — em nenhum dos dois a aba pode dizer que o lançador
# está aqui.
QUADRO = dl.Quadro(lancadores=dl.cartoes(None))
CARTOES = dl.cartoes_html(QUADRO.lancadores)

MIOLO = f'''
    <div class="quadro">
      <div class="quadro-topo">
        <span class="quadro-titulo">De onde os seus jogos vêm</span>
        <span class="ajuda">?<span class="dica">
          O Hefesto não é só para a Steam. Ele casa o perfil pelo <b>nome do processo</b> e pela
          <b>janela</b> — o jogo pode vir de onde quiser.<br><br>
          Esta aba procura os lançadores e emuladores instalados, diz <b>se os controles chegam
          lá</b>, o que impede quando não chegam, e conserta o que dá para consertar sozinho.<br><br>
          O que impede é do <b>lançador</b>, nunca do controle — é a linha de inicialização, a
          exceção do Steam Input, a permissão de aparelho. Por isso a resposta vale igual para os
          <b>{N_CTRL}</b> ({N_USB} no cabo, {N_BT} no rádio), e por isso a fita lá em cima está
          esmaecida aqui: não há o que escolher por controle.<br><br>
          <b>Detectar o jogo que está aberto</b> é o caminho curto: abra o jogo de onde for,
          volte aqui e clique — o perfil nasce com a regra certa, sem digitar nada.
        </span></span>
        <span class="conta" data-campo="lanc-conta" data-hef-alvo="html">{dl.conta_html(QUADRO.achados, QUADRO.impedidos)}</span>
      </div>
      <div class="quadro-corpo">

        <div class="acoes" style="margin-top:0;margin-bottom:12px">
          <button class="btn roxo" data-gesto="detectar">Detectar o jogo que está aberto</button>
          <button class="btn" data-gesto="procurar">Procurar de novo</button>
        </div>

        <div class="{dl.CLASSE_DA_GRADE}">
{CARTOES}
        </div>

      </div>
    </div>
'''

LEGENDA = f'''<div class="nota">
  <h2>A aba mudou de assunto inteiro</h2>
  <ul>
    <li><b>A antiga era "Emulação" de <i>gamepad</i></b> (uinput) — termo técnico que ninguém entende. O conteúdo dela foi para os donos certos: diagnóstico e "Testar o controle virtual" para a <b>Sistema</b>, os combos para a <b>Navegação</b>, o microfone para a <b>Conexões</b>, modo e máscara para a <b>Jogar</b> e os <b>Perfis</b>.</li>
    <li><b>A nova é sobre de onde o jogo vem</b> — e existe para fechar uma lacuna medida: o produto tem <b>zero</b> menção a RetroArch, Dolphin ou mGBA no código, e o Orpheus depende de um emulador de GBC. Heroic e Lutris só aparecem em <b>comentário</b> (<code>hotkey.py:56</code>, <code>lifecycle.py:2271</code> — era <code>:2250</code>, e a linha andou).</li>
    <li><b>A interface diz "Steam" 689 vezes</b> para um motor que já casa por <code>process_name</code> e <code>window_class</code>. É aqui que o jogo de fora da Steam ganha porta de entrada.</li>
  </ul>

  <h2>02/09/2026 — a aba saiu do desenho, e três números dela caíram</h2>
  <ul>
    <li><b>Nenhuma caixa andou.</b> A grade, o CSS, os textos de ajuda e o lugar de cada botão são os que ela aprovou (<i>"lançadores perfeito parabéns"</i>). O que mudou é <b>de onde vem o que está escrito dentro deles</b>.</li>
    <li><b>Os cartões deixaram de contar controle.</b> Eles diziam <i>"Os N controles chegam"</i>, com o N saindo da <code>MESA</code>. A aba responde por <b>lançador</b>, e isto já estava medido no próprio arquivo: nenhuma função de <code>prontuario_dos_jogos.py</code> recebe controle, MAC, device ou transporte — os cinco impedimentos (<code>:139-143</code>) e as duas curas (<code>:878</code>) são fatos do <b>jogo em disco</b>. Contar controle aqui era responder com um número que a pergunta não tem. A régua do gerador virou o inverso: ela reprova se um cartão voltar a prometer para um número.</li>
    <li><b>Os números do cartão da Steam eram digitados, e o produto contradiz os quatro.</b> Medido na máquina dela em 02/09 com <code>censo_do_wrapper</code> e <code>prontuario_dos_jogos</code>: <i>412 jogos</i> → <b>23 instalados</b>; <i>3 jogos já sabem por onde entrar</i> → <b>0 pontes confirmadas</b>; <i>5 encontrados · 1 com impedimento</i> → <b>1 lançador medível</b>; e o <i>Heroic · 28 jogos · NÃO CHEGAM</i> era afirmação sobre um lançador que o produto <b>nunca olhou</b>.</li>
    <li><b>Nasceu o selo <code>NÃO SEI</code>, e ele é a cura disso.</b> Heroic, Lutris, Flatpak, RetroArch e Dolphin·mGBA passam a dizer que o produto ainda não sabe olhá-los — <code>CHEGAM</code> e <code>NÃO CHEGAM</code> seriam as duas afirmações que ele não pode fazer. Há régua que reprova no dia em que um deles ganhar fonte e continuar com o <code>NÃO SEI</code>.</li>
    <li><b>O cartão da Steam ganhou a lista dos jogos que perderam o atalho</b>, com o nome de cada um e o botão de tirar/devolver. Ela <b>nasce vazia</b> e não ocupa um pixel quando não há o que dizer — a mesma regra do carimbo.</li>
    <li><b>A contagem do quadro continua derivada</b> — hoje <b>{QUADRO.achados}</b> —, e agora dos mesmos cartões que o produto monta.</li>
  </ul>

  <h2>O que estava no código e nunca teve tela — agora tem</h2>
  <ul>
    <li><b>"Ver o que impede"</b> — <code>prontuario_dos_jogos.levantar_censo</code> nomeia cinco impedimentos e <b>não tinha chamador em <code>src/</code></b>. O botão é o chamador. Ele leva <b>13,4 s</b> (examina o executável de cada jogo), por isso é gesto e não pintura.</li>
    <li><b>"Consertar"</b> — <code>sentinela_do_wrapper.reparar_ou_adiar</code>, com os portões dele intactos: jogo aberto antes de tudo, Steam aberta depois, e só então a escrita. A recusa vai para a tela com a frase que <b>nomeia o jogo</b>.</li>
    <li><b>"Não usar neste jogo" / "Voltar a usar"</b> — o <code>jogos_sem_wrapper.txt</code> existia e <b>nenhuma tela o escrevia</b>: a única forma de tirar um jogo era editar o arquivo à mão.</li>
    <li><b>"Detectar o jogo que está aberto"</b> — <code>steam_game_running_appid</code>, a mesma fonte do lembrete do wrapper. Ele diz <b>qual</b> jogo e se ele abre pelo atalho; <b>criar o perfil continua sendo da aba Perfis</b>.</li>
  </ul>

  <h2>Ainda aberto</h2>
  <ul>
    <li><b>Os cinco botões de Steam da Sistema vêm para cá?</b> <b>RESPONDIDA — ficam na Sistema</b> (D-A-ABA-LANCADORES-NASCE-PLACEHOLDER). Não reabrir.</li>
    <li><b>"Abrir o lançador" e "Criar perfil para um jogo" continuam sem endereço</b>, e é decisão: abrir a Steam é <code>xdg-open</code>, não IPC, e criar perfil é da aba Perfis — dois caminhos para o mesmo disco é como duas telas passam a discordar.</li>
    <li><b>Quem mede Heroic, Lutris e os emuladores?</b> Ninguém, ainda. É varredura nova, não é ligar o que existe — e por isso os cinco cartões dizem <code>NÃO SEI</code> em vez de escolher um selo.</li>
  </ul>
</div>

</body>
</html>
'''

# ---------------------------------------------------------------------------
# A RÉGUA DA PROMESSA — 31/08/2026, REFEITA em 02/09/2026.
#
# O QUE ELA COBRAVA: que o "Os N controles chegam" dos cartões batesse com a
# `MESA`. Ela nasceu de um defeito real — com dois lugares vazios, cinco cartões
# prometiam a QUATRO controles.
#
# O QUE MUDOU, e é por isso que ela mudou de forma: **os cartões deixaram de
# contar controle.** O próprio arquivo já tinha medido a razão, no comentário do
# topo: nenhuma função de `prontuario_dos_jogos` recebe controle, MAC, device ou
# transporte — os cinco impedimentos são fatos do JOGO EM DISCO. Contar
# controles nesta aba era responder com um número que a pergunta não tem, e foi
# exatamente esse número que a régua velha existia para corrigir.
#
# A régua nova cobra o que sobrou, e cobra dos dois lados:
#   1. NENHUM cartão promete um número de controles (a recaída da velha);
#   2. os seis cartões existem, e cada um tem os quatro endereços que o pacote
#      pinta — um cartão sem endereço fica com o desenho para sempre, e é
#      invisível na tela.
#
# ELA LÊ O MIOLO, e não as variáveis que o escreveram: comparar o produto com
# ele mesmo é como uma régua irmã, na aba Conexões, passou por uma mordida.
# ---------------------------------------------------------------------------
import re  # noqa: E402

_PROMESSAS = re.findall(r"[Oo]s (\d+) controles chegam", MIOLO)
if _PROMESSAS:
    raise SystemExit(
        f"ERRO: {len(_PROMESSAS)} cartão(ões) voltaram a prometer para um NÚMERO "
        f"de controles {sorted(_PROMESSAS)}. Esta aba responde por LANÇADOR: "
        "nenhum dos cinco impedimentos de `prontuario_dos_jogos` recebe "
        "controle, MAC, device ou transporte. Um número aqui é uma promessa que "
        "o produto não tem como conferir.")

_ESPERADOS = [x.chave for x in QUADRO.lancadores]
if len(_ESPERADOS) != 6:
    raise SystemExit(f"ERRO: {len(_ESPERADOS)} cartões, e o desenho dela tem SEIS. "
                     "Se um lançador ganhou fonte, ele sai do `SEM_FONTE` e "
                     "entra com cartão próprio — a conta continua fechando.")
_FALTAM = [f"{k}{s}" for k in _ESPERADOS for s in dl.SUFIXOS
           if f'data-campo="{k}{s}"' not in MIOLO]
if _FALTAM:
    raise SystemExit(
        f"ERRO: {len(_FALTAM)} endereço(s) que o pacote pinta não existem no "
        f"miolo: {_FALTAM}. Um valor escrito num endereço que a página não tem "
        "é pintura perdida — `querySelector` devolve `null`, a pintura conta "
        "zero, e zero passa por 'nada mudou'.")

n = monta("07-lancadores", "Lançadores", MIOLO, CSS, fita_viva=False, legenda=LEGENDA)
print(f"07-lancadores: OK, {n} divs · mesa {N_CTRL} ({N_USB} USB/{N_BT} BT) · "
      f"{QUADRO.achados} encontrados, {QUADRO.impedidos} com impedimento · "
      f"{len(_ESPERADOS) * len(dl.SUFIXOS)} endereços em {len(_ESPERADOS)} cartões")
