# A PASTA, não /tmp: o `monta` e o `topo.html` vivem aqui, e é daqui que esta
# aba os lê. Ver o cabeçalho do aba09.py para o defeito que isso curou.
import sys, pathlib; sys.path.insert(0, str(pathlib.Path(__file__).parent))
from monta import monta, glifo, cor_da_zona, rotulo, CSS_GLIFO, MESA

# ---------------------------------------------------------------------------
# O QUE O PERFIL GUARDA DE CADA CONTROLE — e isto NÃO é escolha de desenho.
#
# `Profile.controllers` é um mapa `{ID da peça: ControllerOverrides}`
# (`profiles/schema.py:1008`), e `ControllerOverrides` tem QUATRO campos, nem um
# a mais (`profiles/schema.py:900-903`):
#
#     leds  ·  triggers  ·  rumble  ·  speaker
#
# Tudo o mais do perfil — mouse, teclado, mic, modo, modo-jogo — é do perfil
# INTEIRO, e a própria classe diz por quê, campo a campo (`:846-895`): o `mode`
# é da SESSÃO e existe um só; `mouse` e `key_bindings` esbarram no
# "INPUT vem SEMPRE do controle PRIMÁRIO"; o `mic` porque o `BUTTON_DOWN` não
# carrega o `uniq` e o microfone alvo é o PADRÃO DO SISTEMA.
#
# Campo `None` = **sem opinião**: aquele controle herda a seção global do perfil
# (merge POR CAMPO, PERFIL-01). É por isso que a coluna tem dois estados e não
# um: aceso é "este perfil guarda um ajuste só deste controle", apagado é
# "ele usa o do perfil, igual aos outros" — e apagado é a resposta certa para a
# maioria dos controles na maioria dos perfis.
#
# A lista abaixo é uma TRADUÇÃO da classe, não uma segunda verdade: se um campo
# entrar ou sair de `ControllerOverrides`, esta lista fica errada e a linha de
# comentário acima é o que aponta para onde conferir.
SECOES = [
    ("leds", ("lightbar", "led-jogador"),
     "Luz: a cor da barra e o número do jogador deste controle."),
    ("triggers", ("l2", "r2"),
     "Gatilhos: o efeito de L2 e R2 deste controle."),
    ("rumble", ("rumble_esquerdo", "rumble_direito"),
     "Vibração: a força dos dois motores deste controle."),
    ("speaker", ("alto-falante",),
     "Alto-falante: o volume e o mudo do alto-falante deste controle."),
]

# O ESTADO DESTE PERFIL, controle a controle. Um mockup que acende as quatro
# seções nos quatro controles ensina que o normal é cada peça ter tudo próprio —
# e o normal é o contrário: quem não tem opinião herda. Aqui aparecem as quatro
# gradações, inclusive a de baixo, que é a mais comum.
GUARDA = {
    "p1": {"leds", "triggers", "rumble"},
    "p2": {"leds", "rumble"},
    "p3": {"leds"},
    "p4": set(),
}

# O ID DA PEÇA é o endereço de rádio normalizado — a MESMA chave que o
# `_validate_controllers_keys` aceita e canoniza (`profiles/schema.py:1114`), e
# a mesma que a dica do "Perfil ativo" promete no esqueleto: *"pelo ID da peça —
# amanhã, em outra porta ou no rádio, ele traz de volta o que você deixou hoje"*.
# A promessa é verdadeira porque o endereço é ESTÁVEL entre USB e BT no
# DualSense — medido nesta casa e escrito no esquema (`:1002`).
#
# `AA:BB:` é o endereço DIDÁTICO da casa: nada de endereço real em arquivo
# versionado (CLAUDE.md, e os dois portões que a regra tem).
ID_DA_PECA = {"p1": "AA:BB:CC:00:00:01", "p2": "AA:BB:CC:00:00:02",
              "p3": "AA:BB:CC:00:00:03", "p4": "AA:BB:CC:00:00:04"}

CSS = CSS_GLIFO + """
  /* ---------- Perfis ---------- */
  /* UM FUNDO SÓ, com os dois blocos dentro. Eles continuam sendo dois — mesma
     largura, mesma altura, cada um com o seu título e os seus três botões — mas
     a moldura é uma, e o vão entre eles vira uma divisória fina. Pedido dela em
     27/08: "deixa um só, pra causar a ilusão de um único bloco". */
  /* A CORRENTE DA ALTURA: o quadro `estica` cresce até o rodapé, e daí para baixo
     cada elo precisa passar a altura adiante — corpo, grade, coluna, moldura,
     lista. Faltando um elo, a lista volta a parar no tamanho do conteúdo.
     `flex:1;min-height:0` e NÃO `height:100%`: a porcentagem se resolve contra a
     altura do pai, que aqui é automática — a conta fica circular, o navegador cai
     no `auto`, e o quadro cresceu 116px além do miolo levando a fileira de botões
     para fora da janela. */
  .perfis{flex:1;min-height:0;display:grid;grid-template-columns:1fr 1fr;align-items:stretch;
          border:1px solid var(--border-forte);border-radius:7px;background:var(--app-bg);
          overflow:hidden}
  /* `min-height:0` em cada elo: por padrão um filho de flex não encolhe abaixo do
     próprio conteúdo. Sem ele, a lista sem teto empurrou a coluna para baixo e a
     fileira `Ativar · Novo · Remover` saiu pela borda do quadro — sumiu da tela. */
  .perfis > div{display:flex;flex-direction:column;padding:10px 14px;min-height:0}
  .perfis > div:first-child{padding-right:7px}
  .perfis > div:last-child{padding-left:7px}

  .perfis > div > .moldura{flex:1;min-height:0;display:flex;flex-direction:column}
  .moldura{border:none;background:none;padding:0}
  .sec-rot{font-size:11px;color:var(--comment);text-transform:uppercase;letter-spacing:.5px;
           margin-bottom:10px;display:flex;align-items:center;gap:6px;height:15px}
  /* A LISTA LÊ COMO TABELA: cabeçalho com fundo próprio e linhas zebradas. Quem
     diz que há mais perfis abaixo é a barra de rolagem de verdade (ver abaixo). */
  /* SEM `max-height`. Ela tinha teto de 236px: a lista parava em sete perfis e
     meio — a linha `Faith` ficava cortada ao meio — com o bloco inteiro sobrando
     embaixo. Ela, 27/08: "pq esse bloco aqui é super capado assim? ... aqui tem
     literalmente zero necessidade de não usar ele". Agora ela ocupa o que o bloco
     tem, e o bloco ocupa até o rodapé. */
  .lista{position:relative;flex:1;display:flex;min-height:0}
  /* A BARRA É A DE VERDADE, CLÁSSICA, E OCUPA ESPAÇO — a mesma cura que a 02 já
     aplicou no `.quadro-corpo`.
     O QUE ESTAVA AQUI ESCONDIA A LISTA. `.rolo` trazia `scrollbar-width:none` e
     `::-webkit-scrollbar{display:none}`, e no lugar da barra real vinha uma
     DESENHADA — `.nav-trilho` + `.nav-polegar`, um par de spans com
     `position:absolute` e um polegar de altura fixa em `46%`. Medido em 28/08:
     dos 14 perfis a lista mostrava 11; **116px** ficavam fora (≈3,6 linhas),
     atrás de 2px que eram a BORDA do `.rolo`, não uma barra — a barra media
     zero. E o polegar desenhado mentia duas vezes: não andava ao rolar e os
     46% não tinham relação com a proporção real (359 de 475 = 75,6%).
     As regras de `width:9px` logo abaixo eram letra morta: `display:none` já
     tinha vindo antes, e `width` não desfaz `display`.
     Barra de verdade porque ela nasce só quando há o que rolar, mede a
     proporção sozinha e anda junto — os estados em que a lista cabe não pagam
     nada por ela. É por isso que ela vale mais que `scrollbar-gutter:stable`,
     que reservaria a faixa em toda tela. */
  .rolo{flex:1;overflow-y:auto;border:1px solid var(--border-sutil);border-radius:6px;
        background:var(--panel)}
  .rolo::-webkit-scrollbar{width:10px}
  .rolo::-webkit-scrollbar-track{background:transparent}
  .rolo::-webkit-scrollbar-thumb{background:var(--border-forte);border-radius:5px}
  .rolo::-webkit-scrollbar-thumb:hover{background:var(--comment)}
  .tab{width:100%;border-collapse:collapse;font-size:11.5px}
  .tab thead th{position:sticky;top:0;z-index:2;text-align:left;font-weight:600;font-size:10px;
          color:var(--purple);text-transform:uppercase;letter-spacing:.6px;
          padding:7px 10px;background:var(--elevated);
          border-bottom:1px solid var(--border-forte)}
  .tab td{padding:8px 10px;color:var(--texto-suave);cursor:pointer;
          border-bottom:1px solid var(--border-sutil)}
  .tab tbody tr:nth-child(even) td{background:rgba(255,255,255,.018)}
  .tab tbody tr:last-child td{border-bottom:none}
  .tab tr.ativo td{color:var(--green);font-weight:600}
  .tab tr.ativo td:first-child{box-shadow:inset 3px 0 0 var(--green)}
  .tab tbody tr:hover:not(.ativo) td{background:var(--sel-bg)}
  .tab .pri{font-family:'JetBrains Mono',monospace;width:46px;text-align:right}
  .tab .quando{color:var(--texto-mudo);font-weight:400}
  .conta-perfis{font-size:10.5px;color:var(--comment);margin-left:auto;text-transform:none;
                letter-spacing:0}
  /* 3 botões e 3 botões, todos da mesma largura */
  .botoes{display:grid;grid-template-columns:repeat(3,1fr);gap:7px;margin-top:auto;padding-top:12px}
  .botoes .btn{width:100%;justify-content:center;padding:0 8px;font-size:11.5px}
  /* os campos do editor, todos na mesma grade */
  /* os campos ficam sobre o MESMO fundo da tabela ao lado, e assim os três botões
     de baixo nascem na mesma base nos dois blocos. */
  /* `min-height:0` aqui é o que impede a coluna da direita de EMPURRAR a fileira
     de botões para fora da moldura: sem ele um filho de flex não encolhe abaixo do
     próprio conteúdo, e a tabela de baixo levou `Duplicar · Voltar · Recarregar`
     19px além da borda do quadro — que tem `overflow:hidden`, então os três
     simplesmente sumiam da tela. Medido em 27/08, no primeiro desenho desta tabela. */
  .campos{flex:1;min-height:0;border:1px solid var(--border-sutil);border-radius:6px;
          background:var(--panel);
          padding:10px 12px;display:flex;flex-direction:column;justify-content:flex-start}
  /* `flex-start` e não `center`: com a lista limitada a 236px o bloco era baixo e
     centrar não aparecia. Solto o teto, os campos passaram a flutuar no meio, com
     um vão em cima e a lista da esquerda começando bem mais acima. */
  .campo{display:grid;grid-template-columns:var(--rot-p) 1fr;align-items:center;gap:12px;
         height:var(--h-escolha);font-size:12px;color:var(--texto-mudo);margin-bottom:4px}
  .campo .val{display:flex;align-items:center;gap:10px}
  .campo input[type=text],.campo select{
    flex:1;min-width:0;height:var(--h-escolha);border-radius:7px;font-size:12.5px;font-family:inherit;
    padding:0 11px;border:1px solid var(--border-forte);background:var(--app-bg);color:var(--fg);
  }
  .campo select{cursor:pointer}
  .campo select.destaque{border-color:var(--purple);background:var(--sel-bg);font-weight:600}
  /* a prioridade é slicer */
  .campo .trilho{flex:1;height:5px;border-radius:3px;background:var(--border-forte);position:relative}
  .campo .cheio{position:absolute;left:0;top:0;bottom:0;border-radius:3px;background:var(--purple)}
  .campo .cheio::after{content:'';position:absolute;right:-5px;top:-4px;width:12px;height:12px;
    border-radius:50%;background:var(--purple);border:2px solid var(--app-bg)}
  .campo .n{flex:0 0 40px;text-align:right;font-family:'JetBrains Mono',monospace;color:var(--fg)}
  .campo .btn{flex:0 0 auto;white-space:nowrap}
  :root{--rot-p:104px}

  /* ---------- as QUATRO configurações que cabem dentro deste perfil ----------
     O editor mostrava CINCO campos e gravava vinte, e a única frase que dizia
     isso vivia escondida na dica do "Perfil ativo": *"cada controle guarda a sua
     configuração aqui dentro, pelo ID da peça"*. Com um controle na mesa dava
     para não reparar; com quatro, a tela que promete e não mostra vira a pergunta
     "então o que exatamente eu salvei?".

     Fica no MESMO quadro, embaixo dos campos, separado por uma linha — e não num
     quadro novo: não é outra tela, é o resto DESTE perfil. E é LEITURA: quem
     escolhe o alvo de um ajuste é a fita, que aqui continua esmaecida. */
  .guarda{flex:1;min-height:0;display:flex;flex-direction:column;overflow:hidden;
          margin-top:7px;padding-top:7px;border-top:1px solid var(--border-sutil)}
  /* `height:100%` na tabela e as quatro linhas dividem a altura que sobra — a
     cura do vão é na ALTURA, nunca `space-between`, que ela reprovou com todas
     as letras. Aqui o vão nem chega a nascer: se sobrar espaço, ele vira altura
     de linha, distribuída igual entre os quatro. */
  .guarda table{height:100%}
  /* A TABELA DE BAIXO É MIÚDA POR CONTA: o que manda no tamanho dela é a altura
     que sobra do editor, e ela tem de caber INTEIRA — quatro linhas e o cabeçalho —
     sem empurrar a fileira de botões nem um pixel. Cada valor aqui foi medido
     contra o `overflow` do quadro, não escolhido. */
  .tab.miuda thead th{padding:3px 8px;background:none;border-bottom:1px solid var(--border-sutil)}
  .tab.miuda td{padding:1px 8px;cursor:default}
  .gd-nome{display:flex;align-items:center;gap:8px;white-space:nowrap;font-size:11px}
  /* O DESENHO DE 32px SAIU, e a barrinha de plástico ficou com o trabalho.
     Ele existia para dizer QUAL controle é a linha, e não dizia: medido em
     28/08 no 1x da tela dela, com os quatro desenhos comparados pixel a pixel,
     o par mais próximo — Cosmic Red × Galactic Purple — se distinguia em
     **33 pixels de 736**, 4,5% do desenho. Os quatro liam como quatro cinzas.

     A causa é que a cor do plástico neste desenho é um TRAÇO, não um
     preenchimento: a 32px o traço vale um terço de pixel e some no
     antisserrilhado. Crescer não estava disponível — a 64px, onde o par pior
     chega a 9,1%, as quatro linhas passam a pedir 209px de altura, e a tabela
     tem 132px (o editor acima já está cheio: sobram 11px até a fileira de
     botões). Um desenho que não cabe no tamanho em que se lê não é escolha de
     layout; é um desenho que esta linha não comporta.

     Quem identifica a peça agora são as duas coisas que JÁ funcionavam e foram
     medidas: a barra de 3px de `--plastico` na primeira célula (cor cheia, sem
     antisserrilhado) e o rótulo `P1 • Cosmic Red • USB`. Se ela quiser o
     desenho de volta, é esta regra e a linha do `svg()` em `linha_do_controle`.

     Foi junto o que o desenho carregava e ninguém via: as cinco lâmpadas do
     jogador mediam **0,5 × 0,2 px** — e vinham com a classe `led-on` CERTA e
     SEM regra que a pintasse, então acesa e apagada tinham o mesmo
     `fill: rgb(107,115,133)`. É o defeito que a `aba04.py` cura com
     `.ctrl .led-on{fill:var(--led-aceso)}` e que esta aba não tinha. */
  /* AS QUATRO SEÇÕES TÊM DE SE LER COMO QUATRO. Com o mesmo vão entre todos os
     glifos, os sete viravam um borrão só e ninguém achava onde a luz acaba e o
     gatilho começa: 2px DENTRO de uma seção, 11px ENTRE elas. */
  .gd-pecas{width:150px}
  .gd-pecas .gls{gap:11px}
  /* aceso = tem ajuste só dele · apagado = usa o do perfil, como os outros */
  .gr{display:inline-flex;align-items:center;gap:2px;color:var(--border-forte)}
  .gr.on{color:var(--purple);filter:drop-shadow(0 0 4px rgba(189,147,249,.45))}
  .gr .gl{vertical-align:-3px}
  .gd-id{width:112px;text-align:right;font-family:'JetBrains Mono',monospace;font-size:10px;
         color:var(--comment)}
  /* A COR DO PLÁSTICO NA BORDA DA LINHA, pela mesma razão do chip da fita: num
     desenho de 32px o modelo mal se distingue, e é a cor que identifica a peça.
     A cor vem de `cor_da_zona()` — do `<style>` que o gerador escreveu no SVG —,
     nunca de um hexadecimal digitado. É a mesma gramática do `tr.ativo` da tabela
     ao lado: uma barra fina à esquerda diz de quem é a linha. */
  .tab.miuda td:first-child{box-shadow:inset 3px 0 0 var(--plastico,transparent)}
"""

AMBIENTES = ["Todos","Steam","Estilo de Jogo","Jogo","Jogo da Steam"]
ESTILOS = ["FPS","Corrida","Ação","Aventura","Esportes","Point-and-click","Terror","Luta",
           "Co-op na mesa","Maratona","Plataforma","Retrô/Emulador","Ritmo/Música",
           "Simulação/Voo","Personalizado"]
PERFIS = [("Mortal Kombat", 90, "Jogo · mk1.exe", True),
          ("Elden Ring", 85, "Jogo da Steam · 1245620", False),
          ("Orpheus", 82, "Jogo · mgba", False),
          ("Pragmata", 80, "Jogo da Steam · 1358160", False),
          ("Don't Scream", 78, "Jogo da Steam · 2380050", False),
          ("Reanimal", 76, "Jogo · reanimal.exe", False),
          ("Faith", 74, "Jogo · faith.exe", False),
          ("Wendigo Blue", 72, "Jogo · wendigo.exe", False),
          ("Duskfade", 70, "Jogo · duskfade.exe", False),
          ("Mina the Hollower", 68, "Jogo · mina.exe", False),
          ("Terror (os dez)", 60, "Estilo de Jogo · Terror", False),
          ("Luta", 58, "Estilo de Jogo · Luta", False),
          ("Navegação", 40, "Todos — 4 disputam", False),
          ("Universal", 0, "Todos — quando nenhum casa", False)]

def opts(lista, escolhido):
    return "\n".join(f'                <option{" selected" if o == escolhido else ""}>{o}</option>'
                     for o in lista)


def linha_do_controle(c, tem=None, id_da_peca=None, uniq=None):
    """Uma linha da tabela de baixo: o controle, o que é só dele, e o ID da peça.

    O rótulo é o encurtado — `P1 • Cosmic Red • USB` —, na ordem dela de 26/08:
    marca • player • plástico • transporte, sem a marca onde aperta. O mesmo
    rótulo do chip da fita, para os dois nunca discordarem.

    E agora ele SAI DE `monta.rotulo(c, "curta")`, não daqui. O texto era montado
    à mão nesta função com os mesmos três campos e o mesmo separador — igual ao
    do chip por coincidência, não por construção. Duas cópias da mesma gramática
    concordam até o dia em que uma muda; a fita já tinha morrido em silêncio
    assim, quando o texto do chip mudou e a âncora que o procurava deixou de
    casar. Uma fonte só, e as duas mudam juntas.

    OS TRÊS PARÂMETROS NASCERAM EM 29/08/2026, e nenhum deles muda um pixel do
    mockup: os três caem nos `GUARDA`/`ID_DA_PECA` fixos quando ninguém os passa.
    Eles existem porque a aba VIVA (`perfis_vivos.py`) usa este gerador como
    BIBLIOTECA — o que o perfil dela guarda por controle é dado de tempo de
    EXECUÇÃO, e a mesa também. Reproduzir esta linha à mão no piloto criaria a
    segunda verdade sobre o desenho, que é o defeito que esta casa mais paga.
    """
    tem = GUARDA[c["pref"]] if tem is None else tem
    id_visivel = ID_DA_PECA[c["pref"]] if id_da_peca is None else id_da_peca
    endereco = uniq if uniq is not None else c["pref"]
    grupos = []
    for campo, pecas, dica in SECOES:
        on = campo in tem
        titulo = (dica if on else
                  dica.split(":")[0] + ": usa o do perfil, igual aos outros controles.")
        gs = "".join(glifo(p, ativo=on, tam=15) for p in pecas)
        grupos.append(f'<span class="gr{" on" if on else ""}" data-hef="guarda.secao"'
                      f' data-hef-secao="{campo}" title="{titulo}">{gs}</span>')
    quantos = (f'{len(tem)} de {len(SECOES)} ajustes só deste controle'
               if tem else "nada só dele — herda os quatro ajustes do perfil")
    return f'''                  <tr data-hef-uniq="{endereco}" style="--plastico:{cor_da_zona(c['cor'])}"
                      title="{c['nome']} — {quantos}.">
                    <td class="gd-nome">
                      <span data-hef="guarda.nome">{rotulo(c, "curta")}</span>
                    </td>
                    <td class="gd-pecas"><span class="gls">{"".join(grupos)}</span></td>
                    <td class="gd-id" data-hef="guarda.id">{id_visivel}</td>
                  </tr>'''


def linha_do_perfil(nome, prioridade, quando, ativo, dica=""):
    """Uma linha da lista de perfis salvos — a MESMA para o mockup e para a viva.

    Ela era uma compreensão de lista embutida no `MIOLO`; virou função pelo mesmo
    motivo da `linha_do_controle`: a aba viva precisa do desenho, não de uma
    cópia dele. O `title` nasce vazio no mockup porque a dica é a DISPUTA, e
    disputa é dado — o mockup não tem nenhum, e um texto inventado aqui viraria
    a tela afirmando uma disputa que não existe.
    """
    return (f'                <tr class="{"ativo" if ativo else ""}" '
            f'data-hef-perfil="{nome}" title="{dica}">'
            f'<td data-hef="perfis.linha.nome">{nome}</td>'
            f'<td class="pri" data-hef="perfis.linha.prioridade">{prioridade}</td>'
            f'<td class="quando" data-hef="perfis.linha.quando">{quando}</td></tr>')


COM_AJUSTE = sum(1 for c in MESA if GUARDA[c["pref"]])

MIOLO = f'''
    <div class="quadro estica">
      <div class="quadro-topo">
        <span class="quadro-titulo">Perfis</span>
        <span class="ajuda">?<span class="dica">
          Um perfil guarda <b>tudo</b> o que você ajustou nas outras abas — gatilho, luz,
          vibração, som, sensores e máscara — e o traz de volta quando aquele jogo abre.<br><br>
          <b>Prioridade</b> decide quem ganha quando dois perfis poderiam entrar; o maior vence.
          O <b>Universal</b> fica em zero, para nunca atropelar ninguém e nunca deixar o
          controle sem nada.<br><br>
          <b>Estilo de Jogo</b> pré-aplica um perfil inteiro: escolhe FPS e gatilho, luz,
          vibração e máscara já vêm resolvidos. Os catorze de fábrica não se editam; o
          <b>Personalizado</b> usa o que você ajustou nas abas.<br><br>
          <b>E o perfil não guarda uma configuração, guarda uma por controle</b> — a tabela
          de baixo mostra, para cada um dos seus {len(MESA)} controles, quais dos quatro
          ajustes ele tem só para si e quais usa do perfil.
        </span></span>
        <span class="conta"><span data-hef="perfis.conta">{len(PERFIS)} perfis</span> <span class="sep">·</span>
          <span data-hef="perfis.com-ajuste">{COM_AJUSTE} de {len(MESA)} controles com ajuste próprio neste perfil</span></span>
      </div>
      <div class="quadro-corpo">
        <div class="perfis">

          <div>
            <div class="moldura">
              <div class="sec-rot">Perfis salvos</div>
              <div class="lista">
              <div class="rolo">
              <table class="tab">
                <thead><tr><th>Nome</th><th class="pri">Pri.</th><th>Quando usar</th></tr></thead>
                <tbody data-hef="perfis.lista">
{chr(10).join(linha_do_perfil(n, p, q, a) for n,p,q,a in PERFIS)}
                </tbody>
              </table>
              </div>
              </div>
              <div class="botoes">
                <button class="btn verde" data-hef-gesto="ativar" title="Passa a usar este perfil agora, em todas as abas.">Ativar</button>
                <button class="btn" data-hef-gesto="novo" title="Perfil em branco, já com a regra do jogo aberto agora — venha ele de onde vier.">Novo</button>
                <button class="btn vermelho" data-hef-gesto="remover" title="Apaga do disco. Pergunta antes.">Remover</button>
              </div>
            </div>
          </div>

          <div>
            <div class="moldura">
              <div class="sec-rot"></div>
              <div class="campos">

              <div class="campo">
                <span>Nome</span>
                <span class="val"><input type="text" data-hef="editor.nome" data-hef-gesto="editor.nome" value="Mortal Kombat"></span>
              </div>
              <div class="campo">
                <span>Prioridade</span>
                <span class="val" data-hef="editor.prioridade.dica" title="O maior vence a disputa quando dois perfis poderiam entrar.">
                  <span class="trilho"><span class="cheio" data-hef="editor.prioridade" style="width:90%"></span></span>
                  <span class="n" data-hef="editor.prioridade.n">90</span>
                </span>
              </div>
              <div class="campo">
                <span>Funciona em</span>
                <span class="val"><select data-hef="editor.ambiente" data-hef-gesto="editor.ambiente">
{opts(AMBIENTES, "Jogo")}
                </select></span>
              </div>
              <div class="campo">
                <span>Nome do jogo</span>
                <span class="val">
                  <input type="text" data-hef="editor.jogo" data-hef-gesto="editor.jogo" value="Mortal Kombat 1">
                  <button class="btn roxo" data-hef-gesto="detectar" title="Pega o jogo que está rodando atrás desta janela e monta a regra — funciona com jogo de qualquer lugar, não só da Steam.">Detectar</button>
                </span>
              </div>
              <div class="campo">
                <span>Estilo de Jogo</span>
                <span class="val"><select class="destaque" data-hef="editor.estilo" data-hef-gesto="editor.estilo">
{opts(ESTILOS, "Luta")}
                </select></span>
              </div>

              <div class="guarda">
                <table class="tab miuda">
                  <thead><tr>
                    <th>Controle</th>
                    <th class="gd-pecas" title="Aceso: este perfil guarda um ajuste só deste controle. Apagado: ele usa o do perfil, igual aos outros. São os quatro ajustes que o perfil sabe guardar por controle — luz, gatilhos, vibração e alto-falante.">Ajuste próprio</th>
                    <th class="gd-id" title="O endereço de rádio do controle. É por ele que o perfil reconhece a peça — e ele não muda quando você troca o cabo pelo rádio, então o que você deixou hoje volta amanhã.">ID da peça</th>
                  </tr></thead>
                  <tbody data-hef="guarda.linhas">
{chr(10).join(linha_do_controle(c) for c in MESA)}
                  </tbody>
                </table>
              </div>

              </div>
              <div class="botoes">
                <button class="btn" data-hef-gesto="duplicar" title="Copia o perfil inteiro para o editor, com &quot;(cópia)&quot; no nome.">Duplicar</button>
                <button class="btn" data-hef-gesto="voltar-a-de-ontem" title="Desfaz um perfil salvo por engano: cada gravação já guarda a anterior.">Voltar à de ontem</button>
                <button class="btn" data-hef-gesto="recarregar" title="Relê a lista do disco. Não descarta o que está no editor ao lado.">Recarregar</button>
              </div>
            </div>
          </div>

        </div>
      </div>
    </div>
'''

# A LINHA DA MÁSCARA AUTOMÁTICA SAIU DA LEGENDA — 29/08/2026.
#
# A lista "O que estava no código e nunca teve tela" anunciava, como entrega
# desta aba: «A máscara "Automático" — o produto lê a API de entrada do
# executável e decide por jogo, em vez de você escolher no escuro». Ela decidiu
# em 29/08 que essa quarta opção SAI, e a razão é a medição: a heurística que a
# moveria (`integrations/api_de_entrada.py:12-49`) erra em 13 dos 14 jogos do
# censo dela. Um automatismo que erra quase sempre é PIOR que escolher à mão,
# porque erra em silêncio — quem escolhe errado sabe que escolheu.
#
# ERAM DOIS MOCKUPS APROVADOS DISCORDANDO, e por isso isto não é ajuste de
# texto: a aba Jogar já dizia o contrário (`novo-layout/01-jogar.html:2311` e
# `:2321` — "sem Automático", com a medição junto) enquanto esta ainda o
# anunciava como entrega. A Jogar venceu, palavra dela. A decisão antiga
# (`D-A-MASCARA-GANHA-O-AUTOMATICO`, 26/08) continua em
# `docs/data/decisoes-dela.csv` com a lápide datada de 29/08 — nesta casa não se
# apaga decisão medida, e quem for executar precisa saber por que a de 26/08
# caducou em vez de tropeçar nela.
#
# O QUE NÃO SAIU, E É DE PROPÓSITO: a palavra "máscara" continua nas duas dicas
# do quadro Perfis (o que o perfil guarda; o que o Estilo de Jogo pré-aplica). A
# máscara existe e o perfil a guarda — com TRÊS opções (DualSense · Xbox 360 ·
# Nintendo Pro). O que morreu foi a quarta, não a máscara.
#
# Este comentário fica no gerador, e não como `<!-- -->` no HTML, de propósito:
# um comentário HTML manteria a palavra viva no mockup e faria o `grep` do
# mockup continuar acusando o que já saiu.
LEGENDA = f'''<div class="nota">
  <h2>O que mudou com quatro controles na mesa</h2>
  <ul>
    <li><b>O editor mostrava cinco campos e gravava vinte.</b> A tabela de baixo mostra o
      resto: <span class="marca">"cada controle guarda a sua configuração aqui dentro, pelo
      ID da peça"</span> era uma promessa que só existia na dica do <b>Perfil ativo</b>. Agora
      ela está desenhada, e são <b>{len(MESA)} configurações dentro do mesmo perfil</b>.</li>
    <li><b>Os quatro ajustes da linha não são escolha minha.</b> São os quatro campos de
      <code>ControllerOverrides</code> (<code>profiles/schema.py:900</code>) — luz, gatilhos,
      vibração e alto-falante —, e mais nenhum: modo, mouse, teclado e microfone são do
      perfil inteiro, e a classe escreve o motivo de cada um.</li>
    <li><b>Apagado não é falta, é herança.</b> Campo vazio quer dizer "sem opinião": aquele
      controle usa a seção global do perfil. O <b>White</b> está assim de propósito —
      é o caso mais comum, e uma tela que acende tudo nos quatro ensinaria o contrário.</li>
    <li><b>O desenho do controle saiu da linha, e a cor ficou.</b> Ele tinha 32px e
      <span class="marca">os quatro liam como quatro cinzas</span>: medido no 1x desta tela,
      o par mais próximo — Cosmic Red e Galactic Purple — se distinguia em <b>33 pixels de
      736</b>. A cor do plástico aqui é um traço fino, e a 32px o traço vale um terço de
      pixel. Crescer não cabia: no tamanho em que a cor se lê, as quatro linhas pedem 209px
      de altura e a tabela tem 132px. Quem diz de quem é a linha agora é a <b>barra de 3px
      na cor do plástico</b> e o rótulo <b>P1 • Cosmic Red • USB</b> — os dois já estavam lá.
      A cor continua saindo do <code>&lt;style&gt;</code> que o
      <code>gerar_cores_do_dualsense.py</code> escreveu, por <code>cor_da_zona()</code>:
      <b>nenhum hexadecimal digitado aqui</b>. Os glifos são os mesmos
      <code>assets/glyphs/</code> das outras abas.</li>
    <li><b>O cabeçalho conta a mesa</b>: {len(PERFIS)} perfis e
      {COM_AJUSTE} de {len(MESA)} controles com ajuste próprio neste perfil.</li>
  </ul>

  <h2>O que você mandou tirar, e continua fora</h2>
  <ul>
    <li><b>"◆ 2 perfis nunca vão entrar — veja quais"</b>, com o <b>?</b> — fora.</li>
    <li><b>"Salvar este perfil"</b> — fora.</li>
    <li><b>"Esconder os controles físicos neste jogo"</b> — fora.</li>
    <li><b>"◆ este jogo já sabe por onde entra"</b> — fora: <span class="marca">isso está na aba Jogar</span>, palavra sua.</li>
  </ul>

  <h2>O que estava no código e nunca teve tela</h2>
  <ul>
    <li><b>Os ajustes por controle</b> — <code>Profile.controllers</code> existe desde
      16/07 e gravava calado: nenhuma tela dizia quais controles têm ajuste próprio.
      Era a pergunta <b>4</b> do contrato desta aba, e a tabela é a resposta.</li>
    <li><b>"Voltar à de ontem"</b> — cada gravação já guarda a anterior e nenhuma tela oferecia isso (<code>profiles/loader.py:1224</code>).</li>
    <li><b>"Detectar"</b> — abra o jogo de onde for, volte e clique; o perfil nasce com a regra certa.</li>
  </ul>

  <h2>Ainda é sua a palavra</h2>
  <ul>
    <li><b>"Modo que liga" e "O jogo vê o controle como" não estão desenhados aqui.</b>
      <span class="marca">A legenda anterior dizia que ficaram, e era falso</span> — nenhum dos
      dois estava na tela. Eles moram hoje na <b>Jogar</b>; se vêm também para cá, é decisão
      sua, e a tela não decide por você.</li>
    <li><b>O conteúdo dos Estilos de Jogo</b> continua em aberto: a lista está aqui, o que
      cada um liga não.</li>
    <li><b>A tabela é leitura</b>, como a fita esmaecida diz. Se você quiser mudar o ajuste de
      um controle a partir daqui — em vez de ir à aba da peça com aquele controle escolhido
      na fita —, isso é tela nova, e eu não a inventei.</li>
  </ul>
</div>

</body>
</html>
'''

n = monta("10-perfis", "Perfis", MIOLO, CSS, fita_viva=False, legenda=LEGENDA)
print(f"10-perfis: OK, {n} divs")
