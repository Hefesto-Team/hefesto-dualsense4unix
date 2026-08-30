#!/usr/bin/env python3
"""Gera a aba JOGAR — `layout/01-jogar.html`.

POR QUE ELA PASSOU A TER GERADOR — 29/08/2026, e o custo foi MEDIDO nos dois
sentidos antes de escrever uma linha.

**O preço de não ter, e ele já foi pago quatro vezes.** A 01 era a única das dez
escrita à mão, e a divergência não é hipótese — está contada:

1. **A cura do logotipo de 28/08 chegou a UMA das dez páginas.** Ela mandou tirar
   os quatro `<title>` minúsculos do logo (passar o mouse na bolinha rosa escrevia
   "bolinha-rosa" na tela dela). Quem curou editou o arquivo que tinha na frente —
   a 01, à mão — e não o `topo.html`, que é a fonte das outras nove. Medido em
   29/08, antes desta volta: `grep -c` dos quatro rótulos dava **0 na 01-jogar e 4
   em cada uma das outras nove**. Trinta e seis instâncias vivas do defeito que ela
   mandou caçar.
2. **Trinta linhas do esqueleto compartilhado não existem na 01.** Contadas contra
   o `topo.html`: as outras abas deixam de fora 4 a 6 linhas (as que o `monta()`
   substitui — título, fita, tira); a 01 deixa **34**, e **30** delas estão nas
   outras nove.
3. **A folha de estilo tem duas cópias mantidas à mão, e elas divergiram em nove
   blocos** — 18 linhas do `topo.html` trocadas por 107 da 01. Duas dessas
   divergências não são inofensivas, porque a classe é COMPARTILHADA: `.pecas` é
   usada pela 01 e pela **10-perfis** (5 vezes), e `.cartao` pela 01 e pela
   **08-conexoes** (3 vezes). A mesma classe quer dizer duas coisas em dois
   arquivos, e quem corrigir uma corrige metade.
4. **O rodapé era declaradamente uma cópia gêmea.** O comentário dele dizia, com
   todas as letras: *"Esta aba é mantida à MÃO: a cópia gêmea está no
   `_ferramentas/fim.html`, e as duas mudam juntas."* Duas versões vivas, com o
   aviso escrito ao lado.

E um fato errado que a 01 carregava e o `topo.html` já tinha corrigido: o
comentário dos SVGs dizia *"32 peças nomeadas e as cinco cores de plástico"*.
Medido nos CSVs donos: **28 peças** (`docs/data/pecas-do-dualsense.csv`) e **28
modelos de cor** (`docs/data/cores-do-dualsense.csv`).

**O preço de ter, e ele é baixo.** O miolo da 01, com os nove `<svg>` trocados
por um marcador, tem **181 linhas** — os SVGs são 66% do arquivo e já eram
gerados (o `regerar.py` chamava `monta.svg()` para os quatro cartões). O que
sobra é: 83 linhas antes dos cartões, os quatro cartões (que viram um laço de
uma função de 14 linhas) e 32 depois. O `monta()` já escrevia o esqueleto, a
tira, a fita, a contagem do cabeçalho, o rodapé e a legenda — de graça, porque
as outras nove já o usam.

Este arquivo tem menos linhas que o `aba04.py` e mais que o `aba07.py`, que é o
menor dos nove (225).

**O que a `regerar.jogar()` fazia, e onde foi parar.** Ela existia para trocar
NA MÃO o que num gerador não precisa de troca: o desenho dos quatro cartões, a
caixa de máscara de cada um e a frase da legenda. As três coisas nascem aqui
agora, e a `jogar()` sai do `regerar.py` — remendar um arquivo escrito à mão era
o preço de ele ser escrito à mão.

Uso:  aba01.py
"""
import pathlib
import re
import sys

sys.path.insert(0, str(pathlib.Path(__file__).resolve().parent))
import monta  # noqa: E402
from monta import MASCARAS, MESA, glifo, monta as montar, rotulo, svg  # noqa: E402

# ---------------------------------------------------------------------------
# A CENA
# ---------------------------------------------------------------------------
#: A bateria de cada controle — **o único dado inventado desta aba**, e a
#: legenda o declara desde 26/08. Tudo o mais sai da `monta.MESA` (quem está na
#: mesa, o número, a cor, o transporte, a máscara) ou do desenho (o hexadecimal
#: do plástico). Na mesa viva dela agora há DOIS controles, com 85% e 95%.
BATERIA = {"p1": 100, "p2": 64, "p3": 41, "p4": 87}

#: O aviso da coluna Atenção. Também cena, e também declarado na legenda: o
#: `state_full` não publica contagem nem texto de aviso, e a frase
#: *"Dois rádios da bancada estão em portas vizinhas"* é da aba Conexões
#: (`aba08.py`), não do produto.
AVISOS = [("RÁDIO", "Dois rádios da bancada estão em portas vizinhas.")]

#: O modo escolhido e o degrau aceso da escada.
#:
#: A CHAVE DE CADA UM É ENDEREÇO, e ela casa com o vocabulário do produto —
#: `app/actions/jogar/painel.MODOS_DA_TELA` e `.CHIPS_DA_ESCADA`, que viajam em
#: worktree. As três primeiras chaves de modo são as de
#: `mode_transition.MODES`; a quarta ("desligado") **não existe lá**, e é o
#: buraco que a MIGRA-JOGAR-06 leva à mesa dela. Quem confere que os dois lados
#: não divergiram é `tests/unit/test_regua_de_tela_a_aba_jogar.py`, LENDO os
#: dois — nunca digitando a lista.
MODOS = [("desligado", "Desligado"), ("desktop", "Controlar o PC"),
         ("gamepad", "Jogar pelo Hefesto"), ("native", "Conexão Nativa (Sony)")]
MODO_ACESO = "gamepad"
ESCADA = [("automatico", "A", "Automático"), ("hefesto", "1", "Hefesto"),
          ("sony", "2", "Sony (nativo)"), ("steam", "3", "Steam Input"),
          ("desktop", "4", "Teclado + Mouse")]
DEGRAU_ACESO = "automatico"

#: A pendência da faixa de baixo — o rascunho que espera o Aplicar.
PENDENTE = "Conexão Nativa (Sony)"


# ---------------------------------------------------------------------------
# O CSS QUE É SÓ DESTA ABA
#
# Ele entra DEPOIS do `<style>` do esqueleto (é o que o `monta()` faz com o
# `css_extra`), então cada regra daqui vence a homônima de lá pela cascata — que
# é como as outras nove abas já fazem. A alternativa era editar o `topo.html`, e
# ela é o defeito: `.pecas` e `.cartao` são de mais de uma aba, e mudar a regra
# compartilhada para servir a esta mudaria a 10-perfis e a 08-conexoes junto.
# ---------------------------------------------------------------------------
CSS = """
  /* ---------- A ABA JOGAR ---------- */

  /* OS QUATRO NUMA FILEIRA SÓ, E TODOS DA MESMA LARGURA. Era `flex`, e os dois
     cartões mediam 228.8 e 225.2 px — a largura vinha do nome do plástico. */
  .pecas{display:grid;grid-template-columns:repeat(4,1fr);gap:7px}

  /* O CARTÃO VIROU COLUNA em 28/08, e o motivo é a decisão dela: a máscara
     passou a ser POR CONTROLE, e o seletor dela mora aqui dentro. Em cima a
     peça (desenho + rótulo), embaixo as três máscaras.
     A BORDA É A COR DO PLÁSTICO, E ELA VEM DO DESENHO
     (D-A-BORDA-E-A-IDENTIDADE-DA-PECA). Eram duas classes, `.c-red` e
     `.c-blue`, lendo dois hexadecimais do `:root`. Com quatro controles na mesa
     faltariam duas; com os 28 do CSV de cores, vinte e seis. O `--plastico` é o
     mesmo mecanismo do chip da fita, e o valor sai de `monta.cor_da_zona`, que
     lê o `<style>` que o gerador escreveu no SVG. */
  .cartao{
    display:flex;flex-direction:column;align-items:stretch;gap:7px;
    padding:5px 6px 6px;
    border-color:var(--plastico, var(--border-forte));
  }
  .peca-topo{display:flex;align-items:center;gap:6px}
  /* A ENTRELINHA É A CURA DO VÃO, e ela é na ALTURA — encolher o mais alto.
     Com `1.45` o cartão media 67,5px e a coluna de avisos ao lado, 55: doze e
     meio de vão. Em pixel, e não em múltiplo, porque o rótulo tem três linhas
     e cada pixel aqui vale três. */
  .cartao .rotulo{color:var(--texto-mudo);line-height:15px;white-space:nowrap}
  .cartao .rotulo b{color:var(--fg);font-weight:500}
  .cartao .bat{color:var(--green);font-family:'JetBrains Mono',monospace;font-size:11px;
               display:inline-flex;align-items:center;gap:3px;
               line-height:1;vertical-align:-2px}
  /* o glifo da bateria é o MESMO arquivo da aba Controles: assets/glyphs/bateria.svg */
  .cartao .gl{display:inline-block;flex:0 0 auto}
  .cartao .ds-svg{width:62px;flex:0 0 62px}
  /* AS CINCO LÂMPADAS DO JOGADOR NÃO EXISTEM NESTE CARTÃO — decisão dela, 28/08:
     elas saem dos desenhos pequenos e ficam só nos grandes, da Iluminação. Aqui
     o desenho tem 62px e cada lâmpada media 1,06 × 0,36 px; passar de 1px de
     altura pediria ~340px de desenho, um cartão de ~460px, e os quatro somariam
     1840px numa fileira que tem 1163px.
     Quem diz o número do jogador aqui é o rótulo: `Sony • Player 1 • …`.
     NÃO HÁ REGRA DE COR PORQUE NÃO HÁ O QUE PINTAR: o grupo inteiro sai do SVG
     por `svg(lampadas=False)`. A volta anterior parou no meio — deixou as vinte
     no DOM pintadas de `--border-forte` e chamou isso de remédio. Marcação sem
     tinta foi o defeito da Perfis; desenho sem função é este, e a cura das duas
     é a mesma: as duas metades andam juntas. */

  /* ---------- A MÁSCARA, POR CONTROLE ----------
     Decisão dela, 28/08/2026: a máscara vira por controle, na aba Jogar, com
     TRÊS opções e **sem "Automático"** — DualSense · Xbox 360 · Nintendo Pro.
     Era um seletor único no quadro de cima, e ele saiu de lá.

     POR QUE EM COLUNA, e não na fileira que o `.seg` usa em toda a janela: o
     cartão mede 208px, e só "Nintendo Pro" pede ~104px — três lado a lado
     precisariam de ~326px. A alternativa media era pôr dois cartões por fileira
     (423px cada), e o preço disso é desfazer "os quatro numa fileira só", que é
     o que deixa a mesa inteira num relance.

     O botão é `--panel` sobre o cartão `--app-bg` — o inverso do `.seg`, que é
     `--app-bg` sobre o quadro `--panel`. Nos dois casos o que se clica é o tom
     que se destaca do fundo em que está. */
  .mascara{display:flex;flex-direction:column;gap:4px}
  /* É O CHIP, e não o botão de 36px — e a escolha tem preço medido dos dois lados.
     Com `.seg button` (o `--h-escolha` de 36px) as três máscaras somam 116px por
     cartão, o miolo pede 560px e a janela oferece 542: o quadro "Conectado agora"
     passava a rolar POR DENTRO, com 18px do "Reconectar Controles" fora da tela.
     O chip tem 28px, e a mesma conta fecha em 502 — 40px de folga.
     E ele não é uma altura NOVA nesta janela: o chip da fita, três linhas acima,
     JÁ é o seletor por controle desta casa, na mesma altura e com o mesmo
     `.on`. O que muda aqui é só a direção — a fita deita, o cartão empilha. */
  .mascara .chip{
    display:flex;align-items:center;justify-content:center;
    cursor:pointer;background:var(--panel);
  }
  .mascara .chip:hover:not(.on){border-color:var(--comment);color:var(--texto-suave)}

  /* O CARTÃO DO ALVO DA FITA. A fita desta aba está VIVA, e até 28/08 ela
     apontava para lugar nenhum — a legenda declarava a contradição em aberto.
     Com a máscara por controle ela tem alvo de verdade, e o cartão dele leva o
     MESMO realce do chip escolhido, para os dois lerem como a mesma escolha. */
  .cartao.alvo{background:var(--sel-bg)}

  /* O CABEÇALHO DAS DUAS COLUNAS TEM UMA ALTURA SÓ. O da esquerda ganhou o
     ícone de ajuda (17px) e o da direita é só texto (14,4px): sem isto a
     fileira de cartões e a lista de avisos começariam 2,6px fora de registro.
     A cura é na ALTURA, e quem manda é o mais alto. */
  .cab-col{display:flex;align-items:center;height:17px;margin-bottom:7px}

  /* A MESA FICA COM A SOBRA. Eram `1fr 1fr`: metade para dois cartões, metade
     para um aviso de uma linha. Com quatro cartões a metade não cabe, e o
     aviso não precisa dela — a coluna de avisos vale o que o texto pede.
     A LARGURA TEM UM DONO SÓ, e é este `--col-avisos`: ela decide duas coisas
     — onde a mesa acaba e onde o botão da faixa de baixo começa —, e as duas
     têm de bater, senão a barra vertical da coluna de avisos desce e erra a
     borda do botão por 85px, que é o que aconteceu quando eram dois números. */
  .quadro-corpo{--col-avisos:245px}
  .dupla{display:grid;grid-template-columns:1fr var(--col-avisos);gap:14px;align-items:start}

  /* A MESMA GRADE DA DUPLA, e o mesmo `gap`: é isso que faz a borda esquerda do
     botão cair exatamente sob a barra vertical da coluna de avisos. Com `flex`
     o botão parava 85px à direita dela — perto o bastante para ler como erro. */
  .faixa-final{display:grid;grid-template-columns:1fr var(--col-avisos);gap:14px;
               align-items:center;margin-top:12px}
  .faixa-final .pendente{margin-top:0}
  .faixa-final .btn{justify-self:start}
  /* A BARRA VERTICAL VAI ATÉ EMBAIXO. Com `align-items:start` no `.dupla` a
     coluna media a altura do seu conteúdo — 56px de um aviso ao lado de 158px de
     cartões —, e a barra que separa os dois blocos virava um toco de um terço.
     `stretch` faz dela a divisória inteira. O espaço que sobra abaixo do aviso é
     RESERVADO de propósito (P8): é onde o segundo e o terceiro aviso entram sem
     empurrar a tela. */
  .col-atencao{border-left:1px solid var(--border-sutil);padding-left:16px;
               align-self:stretch}
"""


# ---------------------------------------------------------------------------
# OS CARTÕES — um por controle da MESA
# ---------------------------------------------------------------------------
#: O GLIFO DA BATERIA VAI SEM `<title>`, e a linha existe para não desfazer
#: calado o que ela pediu. O `monta.glifo()` põe o nome da peça no `<title>` de
#: propósito (é como um SVG diz o nome dele, e foi a cura do `title="cross"` que
#: a Controles mostrava 64 vezes). Aqui ele sai, porque este glifo está DENTRO
#: da frase `100%` — o rótulo já diz o que é, e o tooltip repetiria "Bateria" em
#: cima de um número que se lê sozinho. Medido: nenhuma das dez páginas tem
#: `<title>Bateria</title>` hoje. **É decisão dela reverter**, não minha: pôr o
#: `<title>` de volta é apagar `.replace(...)` desta linha.
_BATERIA_GLIFO = glifo("bateria", tam=13).replace("<title>Bateria</title>", "")


def _desenho(c):
    """O desenho de um controle da MESA, pronto para o cartão.

    **O PRÓLOGO XML SAI.** `svg()` devolve o arquivo inteiro, e ele começa com
    `<?xml ...?>`; empilhado a cada volta ele dava quinze prólogos por cartão na
    versão à mão, e o navegador os engolia calado.

    **E O CARTÃO NÃO TEM AS CINCO LÂMPADAS DO JOGADOR** — decisão dela, 28/08,
    com o número no CSS acima.
    """
    return re.sub(r"<\?xml[^>]*\?>\s*", "",
                  svg(f'jg-{c["pref"]}', c["cor"], lampadas=False))


def cartao(c, bateria=None):
    """Um cartão da fileira: desenho na cor do plástico, rótulo e as máscaras.

    `bateria` é o único argumento, e existe porque a carga é o **único dado
    inventado** desta aba (a legenda o declara desde 26/08): no mockup ela vem
    da tabela `BATERIA`, e na aba viva vem do `state_full`. Sem este argumento
    a mesa viva de cinco controles levantaria `KeyError` no `p5` — no meio da
    remontagem, com a tela dela na frente.


    A MÁSCARA NÃO É DIGITADA. Ela sai de `monta.MESA[...]["mascara"]`, que é a
    mesma fonte que a Controles e a Conexões leem — e foi a divergência que a
    versão à mão criou: a 01 mostrava `P2 = DualSense` e `P3 = Xbox 360` contra
    o `P2 = Xbox 360` / `P3 = DualSense` da MESA, porque a fonte única existia e
    a tela de referência ficava de fora dela.

    OS ENDEREÇOS (29/08/2026, e o vocabulário é o do `aba02.py:484`)
    ----------------------------------------------------------------
    `data-controle` é o `uniq` do aparelho quando há um (a mesa viva) e o `pref`
    quando não há (o mockup, cuja mesa é escrita à mão) — a MESMA linha do
    `aba02.py:769`, e não uma segunda regra.

    **Os três `data-campo` do rótulo existem porque o rótulo TEM FILHOS.**
    Escrever `textContent` num elemento com filho apaga os filhos e força
    layout: era a armadilha medida do piloto da Controles. Cada valor que muda
    de segundo a segundo ganha aqui a sua própria FOLHA, e a folha é um `<span>`
    inline sem estilo — que é o que permite endereçar sem mover um pixel, que é
    a promessa desta mudança.
    """
    chips = "\n".join(
        f'                  <span class="chip{" on" if m == c["mascara"] else ""}"'
        f' data-mascara="{m}">{m}</span>'
        for m in MASCARAS)
    return f'''              <div class="cartao{" alvo" if c["alvo"] else ""}" style="--plastico:{monta.cor_da_zona(c["cor"])}"
                   data-controle="{c.get("uniq") or c["pref"]}"
                   title="{rotulo(c, "completa").replace('<span class="pt">•</span>', '•')}">
                <div class="peca-topo">
                {_desenho(c)}
                <span class="rotulo">Sony <span class="pt">•</span> <b data-campo="jogador">Player {c["jogador"]}</b><br><span data-campo="identidade">{c["nome"]} <span class="pt">•</span> {c["via"]}</span><br><span class="bat">{_BATERIA_GLIFO} <span data-campo="bateria">{bateria if bateria is not None else BATERIA.get(c["pref"], "— ")}%</span></span></span>
                </div>
                <div class="mascara">
{chips}
                </div>
              </div>'''


def frase_das_mascaras():
    """"P1 e P3 em DualSense, o P2 em Xbox 360 e o P4 em Nintendo Pro" — da MESA.

    A frase estava digitada na legenda e repetia o erro dos chips. Escrita aqui,
    ela não tem como discordar deles.
    """
    partes = []
    for m in MASCARAS:
        ps = [f'P{c["jogador"]}' for c in MESA if c["mascara"] == m]
        if not ps:
            continue
        quem = " e ".join([", ".join(ps[:-1]), ps[-1]] if len(ps) > 2 else ps)
        partes.append(f"{quem} em {m}" if len(ps) > 1 else f"o {quem} em {m}")
    return ", ".join(partes[:-1]) + " e " + partes[-1]


CARTOES = "\n".join(cartao(c) for c in MESA)

_MODOS = "\n".join(
    f'          <button{" class=\"on\"" if k == MODO_ACESO else ""}'
    f' data-modo="{k}">{m}</button>'
    for k, m in MODOS)
_ESCADA = "\n".join(
    f'            <span class="degrau{" auto" if n == "A" else ""}'
    f'{" on" if k == DEGRAU_ACESO else ""}" data-degrau="{k}"><i>{n}</i>{r}</span>'
    for k, n, r in ESCADA)


def aviso(selo, texto):
    """Uma linha da coluna Atenção.

    Ela vira FUNÇÃO em 29/08/2026 porque a coluna viva monta de zero a N: no
    mockup a cena tem um aviso, e na máquina dela o número muda a cada tique.
    O piloto chama esta mesma função, e por isso não há um segundo HTML de
    aviso escrito à mão em lugar nenhum.
    """
    return f'''            <div class="aviso-item" data-aviso>
              <span class="selo alerta" data-campo="aviso-selo">{selo}</span>
              <span data-campo="aviso-texto">{texto}</span>
            </div>'''


_AVISOS = "\n".join(aviso(selo, texto) for selo, texto in AVISOS)
_CONTA = f"{len(AVISOS)} aviso" + ("s" if len(AVISOS) != 1 else "")


MIOLO = f'''
    <!-- ---------- QUANDO O JOGO ABRIR ---------- -->
    <div class="quadro">
      <div class="quadro-topo">
        <span class="quadro-titulo">Quando o jogo abrir</span>
        <span class="ajuda">?<span class="dica">
          <b>Controlar o PC</b> — o controle vira mouse e teclado do computador.<br><br>
          <b>Jogar pelo Hefesto</b> — escolha certa para quase todos os jogos: o Hefesto acende as luzes, faz o controle vibrar e dá um jogador para cada controle.<br><br>
          <b>Conexão Nativa (Sony)</b> — só para jogos feitos para o PlayStation 5: os gatilhos ficam duros como no PS5. Alguns jogos derrubam o controle no meio da partida neste modo.<br><br>
          <b>Desligado</b> — o Hefesto para de agir. O controle continua funcionando como um controle comum do Linux.
        </span></span>
      </div>
      <div class="quadro-corpo">

        <div class="linha-rot">O que o controle faz agora:</div>
        <div class="seg">
{_MODOS}
        </div>

        <!-- O SELETOR DE MÁSCARA SAIU DAQUI em 28/08. Decisão dela: a máscara é
             POR CONTROLE, e o seletor mora dentro do cartão de cada um, no quadro
             "Conectado agora". O que fica aqui é o que é da MÁQUINA INTEIRA: o
             modo é estado do processo — existe um só (`app/actions/mode_transition.py`),
             e por isso ele não podia descer para o cartão junto com a máscara. -->

        <div class="sub-secao" title="Esta seção só aparece com &quot;Jogar pelo Hefesto&quot; escolhido.">
          <div class="linha-rot">
            <b style="color:var(--texto-suave)">Modo de conexão</b>
            <span class="ajuda" style="display:inline-block;vertical-align:-3px;margin-left:3px">?<span class="dica">
              <b>Automático</b> — o Hefesto tenta na ordem abaixo e <b>para quando acerta</b>; depois não pergunta mais para aquele jogo.<br><br>
              A ordem tem razão medida: dez recursos do controle (giroscópio, acelerômetro, os dois pontos do touchpad, o clique, a vibração) <b>só chegam ao jogo pelo primeiro degrau</b>. Errar ali custa os dez, e custa em silêncio.<br><br>
              <b>Segurando PS + R3</b> você pula para o próximo sem largar o controle — útil quando o jogo não responde e você não quer sair dele.
            </span></span>
          </div>
          <div class="escada">
{_ESCADA}
          </div>
        </div>


      </div>
    </div>

    <!-- ---------- UM BLOCO SÓ: Conectado agora | Atenção ---------- -->
    <div class="quadro">
      <div class="quadro-topo">
        <span class="quadro-titulo">Conectado agora</span>
        <span class="ajuda">?<span class="dica">
          O detalhe de cada controle — entradas, sensores, áudio, o que o jogo está
          recebendo — está na aba <b>Controles</b>.<br><br>
          <b>Reconectar Controles</b> traz de volta quem caiu do co-op no meio da partida e
          arruma a numeração para 1..N. Pode clicar com o jogo aberto: só a numeração espera.
        </span></span>
      </div>
      <div class="quadro-corpo">

        <div class="dupla">
          <div>
            <div class="linha-rot cab-col">
              O jogo vê cada controle como:
              <span class="ajuda" style="margin-left:5px">?<span class="dica">
                A máscara é <b>por controle</b>: cada um pode aparecer de um jeito
                para o jogo.<br><br>
                Ela muda <b>o que o jogo vê</b> — e por isso os botões que ele desenha
                na tela. O controle na sua mão continua o mesmo: a luz, o gatilho e o
                giroscópio seguem por conta do Hefesto em qualquer máscara.<br><br>
                <b>DualSense</b> — o jogo desenha os botões do PlayStation:
                △ ○ ✕ ▢.<br>
                <b>Xbox 360</b> — o jogo desenha os do Xbox: Y B A X.<br>
                <b>Nintendo Pro</b> — o jogo desenha os da Nintendo: X A B Y, com
                <b>ZL</b> e <b>ZR</b> nos gatilhos e <b>−</b> <b>+</b> no lugar de
                Criar e Opções.<br><br>
                Clicar num cartão leva a fita de cima para ele.
              </span></span>
            </div>
            <div class="pecas" data-lista="cartoes">
{CARTOES}
            </div>
          </div>

          <div class="col-atencao" data-lista="avisos">
            <div class="linha-rot cab-col">
              <b style="color:var(--orange)">Atenção</b>
              <span class="conta-avisos" data-campo="atencao-conta">{_CONTA}</span>
            </div>
{_AVISOS}
          </div>
        </div>

        <div class="faixa-final">
          <!-- MAIÚSCULA NO COMEÇO — 28/08/2026. A frase é uma linha inteira,
               isolada na caixa tracejada, e o `●` que vem antes é MARCADOR, não
               palavra: a frase começa aqui. Era o mesmo defeito que ela apontou
               na Conexões ("• o rádio de cada adaptador, em fatias") e mandou
               procurar em todas as abas. O "quando você clicar em" continua
               minúsculo porque é meio da MESMA frase. -->
          <div class="pendente" data-campo="pendente">
            <span>●</span>
            <span>Vai mudar para <b data-campo="pendente-alvo">{PENDENTE}</b> quando você clicar em <b>Aplicar</b></span>
          </div>
          <button class="btn" data-gesto="reconectar">Reconectar Controles</button>
        </div>

      </div>
    </div>
'''


#: A LEGENDA. A frase das máscaras NÃO É DIGITADA — ela sai da `MESA`, pela
#: `frase_das_mascaras()`. Era escrita à mão aqui e repetia o erro dos chips:
#: quando a MESA passou a mandar na máscara de cada cartão, a legenda ficou
#: dizendo o contrário do que a tela mostrava.
LEGENDA = f'''<div class="nota">
  <h2>O que mudou, e por quê</h2>
  <ul>
    <li><b>A máscara virou POR CONTROLE</b> — decisão sua, 28/08. Três opções e
      <b>sem "Automático"</b>: DualSense · Xbox 360 · Nintendo Pro. O seletor mora dentro
      do cartão de cada controle. O que era um seletor único lá em cima
      (<span class="marca">"O jogo vê o controle como:"</span>) saiu do quadro
      <b>Quando o jogo abrir</b> — e o rótulo veio junto, no plural.</li>
    <li><b>Nenhum aviso do que se perde</b> — não há "você perde giro", "perde touchpad"
      nem "perde microfone" em máscara nenhuma. A dica diz o que muda de verdade: a máscara
      muda <b>o que o jogo vê</b>, e por isso os botões que ele desenha. O controle na sua
      mão continua o mesmo — a luz, o gatilho e o giroscópio seguem por conta do Hefesto
      em qualquer máscara (<code>docs/usage/modos.md</code>). O microfone segue o
      <b>transporte</b>, não a máscara.</li>
    <li><b>"Automático" saiu da máscara</b> — substitui a <code>D-A-MASCARA-GANHA-O-AUTOMATICO</code>
      de 26/08, que o queria como terceira opção ligada. A heurística que o moveria
      (<code>api_de_entrada.py</code>) errou em <b>13 dos 14</b> jogos do seu censo.</li>
    <li><b>A fita ficou viva, e agora ela tem alvo</b> — era a contradição que esta legenda
      declarava em aberto: a fita dizia <span class="marca">"vai para o controle escolhido
      aqui"</span> numa aba em que nada era por controle. A máscara resolveu isso. O cartão
      do alvo leva o <b>mesmo realce do chip escolhido</b>, para os dois lerem como uma
      escolha só.</li>
    <li><b>O modo continua da máquina inteira</b>, e não desceu para o cartão junto com a
      máscara. Não é descuido: o modo é <b>estado do processo</b> — existe um só
      (<code>app/actions/mode_transition.py</code>), e duas peças pedindo modos diferentes
      não têm resposta. Máscara é do <b>aparelho</b>; modo é da <b>máquina</b>.</li>
    <li><b>Quatro modos, não três</b> — <span class="marca">Desligado</span> entra na fileira como você decidiu; a Sistema fica com "Encerrar o serviço".</li>
    <li><b>Quatro controles na mesa, um cartão cada</b> — a lista é a <code>MESA</code> do <code>monta.py</code>: não há "quatro" escrito num laço, e o número do jogador é campo, não a posição na fila. Continua sendo só a peça, com o <b>SVG pequeno na cor do plástico</b> — o card completo é da aba Controles.</li>
    <li><b>A borda e a cor vêm do mapa</b> — a cor do plástico sai do <code>cores-do-dualsense.csv</code> pela folha que o gerador escreveu dentro do desenho. Não está digitada aqui.</li>
    <li><b>As cinco lâmpadas do jogador ficam apagadas neste cartão</b> — medido de novo hoje,
      no 1× da sua tela: cada lâmpada mede <b>1,06 × 0,36 px</b> no desenho de 62px, e acender
      as dez mudava <b>de 2 a 7 pixels de 2666</b> por cartão. Para se lerem, o cartão
      precisaria de ~460px — os quatro somariam 1840px numa fileira que tem 1163px. Quem diz
      o número aqui é o rótulo <b>Player N</b>; o padrão das luzes, desenhado grande, está na
      <b>Iluminação</b>.</li>
    <li><b>A caixa "Não trocar de perfil sozinho" saiu</b> — o perfil ativo já diz isso.</li>
    <li><b>"Reconciliar jogadores" virou "Reconectar Controles"</b>.</li>
    <li><b>A área de avisos tem espaço reservado</b> e <b>conta quantos são</b>. Antes, três banners disputavam a linha e o primeiro escondia os outros. A barra vertical que a separa dos cartões agora vai até embaixo — era um toco de um terço, porque a coluna media a altura do único aviso.</li>
    <li><b>32 frases viraram 12</b> — o resto está nos três ícones <b>?</b>. Passe o mouse neles.</li>
  </ul>

  <h2>O que eu decidi por conta, e você pode derrubar</h2>
  <ul>
    <li><b>As três máscaras são chip, e não o botão de 36px do resto da janela</b>, e o preço
      está medido dos dois lados. Com o botão, as três somam 116px por cartão: o miolo pede
      <b>560px</b> e a janela oferece <b>542</b> — o quadro "Conectado agora" passava a rolar
      por dentro, com 18px do <b>Reconectar Controles</b> fora da tela. Com o chip a conta
      fecha em <b>502</b>. E não é uma altura nova: o <b>chip da fita</b>, três linhas acima,
      já é o seletor por controle desta casa, na mesma altura e com o mesmo destaque — o que
      muda é a direção, a fita deita e o cartão empilha.</li>
    <li><b>Empilhadas, e não lado a lado</b> — o cartão tem 208px e só "Nintendo Pro" pede
      ~104px; três na horizontal precisariam de ~326px. A saída seria dois cartões por
      fileira (423px cada), e o preço disso é desfazer <b>os quatro numa fileira só</b>, que é
      o que deixa a mesa inteira num relance. Se você preferir a horizontal, é esse o troco.</li>
    <li><b>As máscaras que aparecem escolhidas</b> — {frase_das_mascaras()}. É para você <b>ver</b> que a escolha é por controle; a sua mesa hoje
      é DualSense nos quatro.</li>
    <li><b>Clicar num cartão leva a fita para ele</b> — é a mesma gramática que você fixou hoje
      para o acordeão da Controles ("clicar num card muda a fita").</li>
    <li><b>A ordem dos modos</b> — pus Desligado primeiro (é o "menos"), depois Controlar o PC, Jogar pelo Hefesto e Nativa. Pode ser o inverso.</li>
    <li><b>A linha laranja tracejada</b> é a prova de que o Aplicar ainda deve. Ela só aparece com escolha pendente — e o espaço dela é reservado, para a tela não pular.</li>
    <li><b>A carga de cada bateria é o único dado inventado desta aba</b> — 100, 64, 41 e 87%. Bateria é estado do momento, e o mockup mostra um momento; todo o resto (cor, nome, transporte, jogador, desenho) sai de arquivo.</li>
    <li><b>O recibo do rodapé nomeia o perfil</b> — é onde a mudança vai cair, que era a informação que faltava e te custou semanas.</li>
  </ul>

  <h2>O que isto encomenda ao código</h2>
  <ul>
    <li><b>A máscara Nintendo Pro não existe hoje</b>, e entra assim mesmo — isto é mockup, e
      mockup desenha o produto que vai existir. O catálogo do produto
      (<code>integrations/uinput_gamepad.py</code>, <code>FLAVORS</code>) tem <b>duas</b>
      entradas: <code>dualsense</code> e <code>xbox</code>. A terceira nasce como
      <b>MÁSCARA-NINTENDO-01</b>, com um invariante duro: o PID <b>não</b> pode ser o
      <code>0x2009</code> do Pro físico (VPAD-04 — vpad e aparelho real com o mesmo VID/PID
      somem juntos da Steam, e o jogo fica com zero controles). Boa parte já está pronta:
      <code>mascaras_validas()</code> deriva do catálogo, então o terceiro sabor passa a valer
      no disco e no portão do IPC <b>sem uma linha de edição</b>.</li>
    <li><b>A máscara já é por aparelho no código</b> (<code>daemon/subsystems/external_mask.py</code>,
      desde 15/08) — o registro por MAC e a herança existem. O que falta é <b>passar a
      identidade</b> em três lugares: <code>virtual_pad.make_virtual_pad</code>,
      <code>coop.py</code> e <code>gamepad.py</code>. Hoje ninguém a passa, e por isso a
      máscara viva é uma só para a mesa toda — que é exatamente o que esta tela deixa de
      mostrar.</li>
    <li><b>Um fato do specs, para a sprint não prometer o que o aparelho não tem:</b> o
      Pro Controller <b>não tem</b> microfone, alto-falante, touchpad, lightbar RGB, gatilho
      adaptativo nem gatilho analógico (ZL/ZR são digitais) — 99 linhas do
      <code>mapa-controles.csv</code>. Nada disso é aviso para esta tela: máscara não é
      adoção. A máscara Nintendo Pro faz o <b>seu DualSense</b> aparecer como um Pro para o
      jogo; ela não faz o Hefesto adotar um Pro.</li>
  </ul>

  <h2>Ainda é sua a palavra</h2>
  <ul>
    <li><b>O microfone quando a máscara é Xbox 360 ou Nintendo Pro.</b> A ONDA-CONEXOES-06
      escreve que nessas máscaras o jogo não pergunta pelo microfone e por isso ele
      <b>some do jogo</b>, e cria o estado <b>Emulado</b> para tapar o buraco — uma fonte de
      captura virtual que qualquer jogo enxerga. É por isso que esta tela não escreve aviso
      nenhum. <b>Mas essa afirmação não tem medição</b>: não há uma linha de microfone ×
      máscara no <code>ensaios.csv</code>, e a régua que a provaria está escrita na própria
      sprint <b>sem dono</b>. Hoje quem entrega o mic ao jogo é a prioridade do WirePlumber,
      que é cega à máscara — o que <b>estreita</b> o buraco e ninguém sabe quanto. É uma
      sprint de bancada, e ela não está na fila.</li>
  </ul>
</div>

</body>
</html>
'''


if __name__ == "__main__":
    n = montar("01-jogar", "Jogar", MIOLO, CSS, fita_viva=True, legenda=LEGENDA)
    print(f"01-jogar: OK, {n} divs · mesa de {len(MESA)} · "
          f"máscaras {frase_das_mascaras()}")
