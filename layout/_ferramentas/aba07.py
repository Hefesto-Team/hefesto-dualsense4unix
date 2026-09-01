# A PASTA, não /tmp: estas três liam um `monta` de /tmp — o de 26/08 23:50 —
# que por sua vez lia um `topo.html` de /tmp parado às 10:59. Três das dez
# abas vinham de um montador e de um esqueleto de ontem, e nenhuma correção
# no topo.html desta pasta as alcançava. Achado em 27/08.
import sys, pathlib; sys.path.insert(0, str(pathlib.Path(__file__).parent))
from monta import MESA, CONECTADOS, monta

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
  .lanc-selo.off{background:var(--border-forte);color:var(--texto-suave)}
  .lanc-jogos{margin-left:auto;font-size:11px;color:var(--texto-mudo);
              font-family:'JetBrains Mono',monospace}
  /* DUAS LINHAS CRAVADAS, e é `height` — não `min-height`.
     Com `min-height:32px` o corpo de uma linha dava 32px e o de duas 33,3px, e a
     fileira de botões dos dois cartões de uma mesma linha nascia 1,3px torta. A
     escala do esqueleto tropeçou nisto uma vez (LEIA-ME, cicatriz 2): min-height
     não encolhe, e aqui também não ESTICA — quem alinha é a altura fixa.
     2,9em = 1,45 (line-height) × 2 linhas, então o número acompanha a fonte. */
  .lanc-diz{font-size:11.5px;color:var(--texto-mudo);height:2.9em;line-height:1.45}
  .lanc-diz b{color:var(--orange)}
  .lanc-diz b.roxo-txt{color:var(--purple)}
  .lanc .acoes{margin-top:8px;gap:6px}
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
"""

# O selo é o resumo de UMA palavra do corpo do cartão. Ele dizia "CHEGA" ao lado
# de um corpo que agora fala dos quatro; selo e frase discordando na mesma linha é
# exatamente o desalinho de 2 px que ela enxerga.
SELOS = {"ok": "CHEGAM", "warn": "NÃO CHEGAM", "off": "NÃO ACHEI"}


def lanc(nome, selo, cls, jogos, diz, acoes, carimbo=None):
    # O carimbo entra DENTRO da fileira de botões (ver o CSS): fora dela, ele
    # empurrava a fileira do cartão que o tem 21px abaixo da do cartão vizinho.
    c = f'\n          <span class="carimbo">◆ {carimbo}</span>' if carimbo else ""
    bs = "\n".join(f'          <button class="btn{" "+k if k else ""}">{r}</button>'
                   for r, k in acoes)
    return f'''      <div class="lanc {cls}">
        <div class="lanc-topo">
          <span class="lanc-nome">{nome}</span>
          <span class="lanc-selo {selo}">{SELOS[selo]}</span>
          <span class="lanc-jogos">{jogos}</span>
        </div>
        <div class="lanc-diz">{diz}</div>
        <div class="acoes">
{bs}{c}
        </div>
      </div>'''


# A LISTA VIROU DADO para a contagem do cabeçalho sair DELA, e não do teclado.
# O número digitado dizia "6 encontrados" contando os seis cartões — inclusive o
# `Dolphin · mGBA`, que o próprio cartão carimba **NÃO ACHEI**. A aba se
# contradizia na mesma tela, e nenhuma régua sabia dizer, porque não havia com o
# que comparar. É o mesmo defeito que o cabeçalho tinha antes de sair da MESA.
LANCADORES = [
    dict(nome="Steam", selo="ok", cls="chega", jogos="412 jogos",
         diz=f"{CHEGAM} O atalho de inicialização está no lugar em todos os "
             f"jogos marcados.",
         acoes=[("Abrir o lançador", ""), ("Criar perfil para um jogo", "")],
         carimbo="3 jogos já sabem por onde entrar"),
    dict(nome="Heroic (Epic · GOG)", selo="warn", cls="impede", jogos="28 jogos",
         diz="<b>Sem wrapper</b> — o atalho de inicialização do Hefesto não está "
             "na linha de comando destes jogos, então o perfil não entra sozinho.",
         acoes=[("Consertar", "verde"), ("Ver o que impede", ""),
                ("Abrir o lançador", "")]),
    dict(nome="Lutris", selo="ok", cls="chega", jogos="17 jogos",
         diz=f"{CHEGAM} A exceção do Steam Input está gravada para os jogos que "
             f"precisavam.",
         acoes=[("Abrir o lançador", ""), ("Criar perfil para um jogo", "")]),
    dict(nome="Flatpak", selo="ok", cls="chega", jogos="9 jogos",
         diz=f"{CHEGAM} As permissões de aparelho estão abertas para os pacotes "
             f"de jogo.",
         acoes=[("Abrir o lançador", ""), ("Criar perfil para um jogo", "")]),
    dict(nome="RetroArch", selo="ok", cls="chega", jogos="—",
         diz=f"Emulador. {CHEGAM} Este é o lugar do "
             f"<b class='roxo-txt'>Estilo Retrô/Emulador</b>, que já vem pensado "
             f"para console antigo.",
         acoes=[("Aplicar o estilo Retrô/Emulador", "roxo"),
                ("Abrir o lançador", "")]),
    dict(nome="Dolphin · mGBA", selo="off", cls="ausente", jogos="—",
         diz="Não achei nesta máquina. Se você instalar, clique em <b>Procurar "
             "de novo</b> e eles aparecem aqui.",
         acoes=[("Procurar de novo", "")]),
]

ACHADOS = sum(1 for x in LANCADORES if x["selo"] != "off")
IMPEDIDOS = sum(1 for x in LANCADORES if x["selo"] == "warn")

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
        <span class="conta">{ACHADOS} encontrados <span class="sep">·</span> {IMPEDIDOS} com impedimento</span>
      </div>
      <div class="quadro-corpo">

        <div class="acoes" style="margin-top:0;margin-bottom:12px">
          <button class="btn roxo">Detectar o jogo que está aberto</button>
          <button class="btn">Procurar de novo</button>
        </div>

        <div class="lancadores">
{chr(10).join(lanc(**x) for x in LANCADORES)}
        </div>

      </div>
    </div>
'''

LEGENDA = f'''<div class="nota">
  <h2>A aba mudou de assunto inteiro</h2>
  <ul>
    <li><b>A antiga era "Emulação" de <i>gamepad</i></b> (uinput) — termo técnico que ninguém entende. O conteúdo dela foi para os donos certos: diagnóstico e "Testar o controle virtual" para a <b>Sistema</b>, os combos para a <b>Navegação</b>, o microfone para a <b>Conexões</b>, modo e máscara para a <b>Jogar</b> e os <b>Perfis</b>.</li>
    <li><b>A nova é sobre de onde o jogo vem</b> — e existe para fechar uma lacuna medida: o produto tem <b>zero</b> menção a RetroArch, Dolphin ou mGBA no código, e o Orpheus depende de um emulador de GBC. Heroic e Lutris só aparecem em <b>comentário</b> (<code>hotkey.py:56</code>, <code>lifecycle.py:2250</code>).</li>
    <li><b>A interface diz "Steam" 689 vezes</b> para um motor que já casa por <code>process_name</code> e <code>window_class</code>. É aqui que o jogo de fora da Steam ganha porta de entrada.</li>
  </ul>

  <h2>O que os quatro controles mudaram aqui — e o que não mudaram</h2>
  <ul>
    <li><b>O desenho não mudou uma caixa.</b> Ela fechou a aba (<i>"lançadores perfeito parabéns"</i>) e a deixou placeholder (<i>"essa aba em si só vamos desenhar e deixar placeholder mesmo"</i>). Nenhum bloco andou, nenhum botão nasceu.</li>
    <li><b>O que mudou é o alcance da promessa.</b> A aba dizia <i>"O controle chega"</i>, no singular, com quatro na mesa — e a primeira pergunta de quem lê era <i>"qual deles?"</i>. Agora diz <b>"Os {N_CTRL} controles chegam"</b>, e o selo acompanha (<code>CHEGAM</code> / <code>NÃO CHEGAM</code>). O número sai da <code>MESA</code>, não do teclado.</li>
    <li><b>E os quatro chegam pelo mesmo motivo, que é medido:</b> nenhuma função de <code>prontuario_dos_jogos.py</code> recebe controle, MAC, device ou transporte. Os cinco impedimentos (<code>:139-143</code>) e as duas curas (<code>:878</code>) são fatos do jogo em disco. É por isso que a fita desta aba é esmaecida de propósito — <code>fita_viva=False</code> — e agora o "?" diz isso em português.</li>
    <li><b>O mapa de canais não tem linha para esta aba, e isso é resposta:</b> <code>mapa-controles.csv</code> responde por <i>peça</i> e por <i>transporte</i> (cabo/rádio). "O controle chega no jogo" não é canal do aparelho — é a linha de inicialização do lançador. Por isso a aba não se divide por transporte, com {N_USB} no cabo e {N_BT} no rádio na mesa.</li>
    <li><b>A contagem do quadro passou a sair da lista.</b> Estava digitada "6 encontrados", contando os seis cartões — inclusive o <code>Dolphin · mGBA</code>, que o próprio cartão carimba <b>NÃO ACHEI</b>. Agora são <b>{ACHADOS}</b>, derivados, e a aba parou de se contradizer na mesma tela.</li>
  </ul>

  <h2>O que estava no código e nunca teve tela</h2>
  <ul>
    <li><b>"Ver o que impede"</b> — <code>prontuario_dos_jogos.py:733</code> nomeia cinco impedimentos e hoje só alimenta <b>uma</b> linha do cartão de saúde.</li>
    <li><b>"Consertar"</b> — <code>prontuario_dos_jogos.py:885</code> (<code>curar_o_que_e_automatico</code>), <b>sem nenhum chamador em <code>src/</code></b>.</li>
  </ul>

  <h2>Ainda aberto</h2>
  <ul>
    <li><b>Os cinco botões de Steam da Sistema vêm para cá?</b> <b>RESPONDIDA — ficam na Sistema</b> (D-A-ABA-LANCADORES-NASCE-PLACEHOLDER). Não reabrir.</li>
    <li><b>A aba lista LANÇADORES ou também os JOGOS de fora da Steam?</b> Hoje o catálogo só enxerga Steam (<code>jogos_locais.py:119</code>) — listar jogo de Heroic é varredura nova, não é ligar o que existe.</li>
    <li><b>"Os controles chegam lá?" — como o produto mede isso?</b> Nenhuma linha mede hoje. Precisa de spec antes de virar selo, senão vira instrumento que mente. O que os quatro controles acrescentam à pergunta: a régua é <b>por lançador</b>, não por controle — o desenho já aposta nisso, e a aposta está provada no código, não medida na máquina dela.</li>
  </ul>
</div>

</body>
</html>
'''

# ---------------------------------------------------------------------------
# A RÉGUA DA PROMESSA — 31/08/2026.
#
# Esta aba existe para dizer UMA coisa: se os controles chegam ao lançador. Com
# dois lugares vazios na mesa, ela prometia isso para QUATRO em cinco cartões.
#
# ELA REFAZ A CONTA A PARTIR DA `MESA`, e não lê `N_CTRL` — ler a variável que
# escreveu o texto é comparar o produto com ele mesmo. Foi assim que uma régua
# irmã, na aba Conexões, passou por uma mordida hoje.
# ---------------------------------------------------------------------------
import re  # noqa: E402

_NA_MESA = len([c for c in MESA if c.get("conectado", True)])
_PROMESSAS = re.findall(r"Os (\d+) controles chegam", MIOLO)
if not _PROMESSAS:
    raise SystemExit("ERRO: nenhuma promessa 'Os N controles chegam' no miolo — a régua "
                     "ficou cega, e seletor que casa ZERO é erro, não silêncio.")
_ERRADAS = {n for n in _PROMESSAS if int(n) != _NA_MESA}
if _ERRADAS:
    raise SystemExit(
        f"ERRO: {len(_PROMESSAS)} cartão(ões) prometem chegar a {sorted(_ERRADAS)} "
        f"controles, e na mesa há {_NA_MESA}. Esta aba existe para dizer se os "
        "controles chegam ao lançador — prometer para quem não está é a única "
        "frase que ela não pode errar.")

n = monta("07-lancadores", "Lançadores", MIOLO, CSS, fita_viva=False, legenda=LEGENDA)
print(f"07-lancadores: OK, {n} divs · mesa {N_CTRL} ({N_USB} USB/{N_BT} BT) · "
      f"{ACHADOS} encontrados, {IMPEDIDOS} com impedimento")
