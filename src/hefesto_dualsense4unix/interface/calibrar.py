#!/usr/bin/env python3
"""A página de calibração dos sensores de movimento — `mockup/calibrar-sensores.html`.

PEDIDO DELA, 31/08/2026, e é o segundo botão que ela mandou nascer na Controles:

    "Preciso que crie uma nova página que abre e mostra os svgs dos controles
     conectados e o procedimento igual o da steam pra calibrar os controles.
     São os 4 ao mesmo tempo."

OS TRÊS ESTADOS SÃO CLICÁVEIS, e isso é decisão de instrumento. Um mockup é
estático: ele desenha UM estado. Um procedimento tem TRÊS (parado, medindo,
pronto), e desenhar só um esconde dois terços do que ela precisa julgar. A saída
é a mesma gramática que a Jogar já usa no interruptor e a Controles no cartão que
abre — `<input type=radio>` escondido mais `:checked` no CSS. Ela clica e vê o
procedimento inteiro, sem uma linha de JavaScript.

O QUE "OS 4 AO MESMO TEMPO" QUER DIZER, e vale escrever porque é o ponto do
pedido: a calibração é de TODOS de uma vez, não um controle por vez. Quem tem
quatro na mesa não repete o gesto quatro vezes. A tela mostra os que estão
conectados — hoje dois, pela decisão dela do mesmo dia de deixar dois fora.

POR QUE O PROCEDIMENTO DA STEAM: é o que ela nomeou, e ele é o mínimo honesto —
o giroscópio zera medindo o repouso, então a única coisa que a pessoa precisa
fazer é **não mexer**. Toda instrução a mais é ruído.

A PALETA E O ESQUELETO SÃO OS DO `mapa.py`, copiados de propósito: as duas são
páginas que abrem POR FORA das dez abas, e uma segunda gramática de página
avulsa na mesma janela seria uma a mais.
"""
import pathlib
import re
import sys

sys.path.insert(0, str(pathlib.Path(__file__).resolve().parent))
import onde  # noqa: E402
import monta  # noqa: E402

#: Quanto tempo a medição leva. NÃO é chute: é o que o `--calibrate` do
#: `hefesto-dualsense4unix` já usa como janela de repouso. Escrito aqui uma vez,
#: e lido pelos dois lugares da página que o citam.
SEGUNDOS = 5

#: As leituras de cada controle na tela, em repouso. Os números do P1 são
#: MEDIDOS no daemon vivo (o mesmo par que a aba Controles mostra); o do P2 é o
#: mesmo repouso com o controle na outra mão. |v| ~ 1 g é a gravidade.
REPOUSO = {
    "p1": {"giro": ("+0.2", "-0.1", "+0.0"), "accel": ("+0.105", "+0.976", "+0.170")},
    "p2": {"giro": ("-0.1", "+0.3", "+0.1"), "accel": ("+0.088", "+0.981", "+0.152")},
    "p3": {"giro": ("+0.0", "+0.1", "-0.2"), "accel": ("+0.112", "+0.969", "+0.181")},
    "p4": {"giro": ("+0.1", "-0.2", "+0.0"), "accel": ("+0.097", "+0.978", "+0.164")},
}

CSS = """
  :root{
    --app-bg:#21222c; --panel:#282a36; --elevated:#2b2d3a;
    --border-sutil:#343746; --border-forte:#44475a; --linha:#53576f;
    --fg:#f8f8f2; --texto-suave:#c8ccda; --texto-mudo:#9a9eb8; --comment:#8896c4;
    --cyan:#8be9fd; --green:#50fa7b; --orange:#ffb86c;
    --pink:#ff79c6; --purple:#bd93f9; --red:#ff5555;
    --sel-bg:rgba(189,147,249,.16);
    --f:ui-sans-serif,system-ui,"Cantarell","Segoe UI",Roboto,sans-serif;
    --m:ui-monospace,"JetBrains Mono","Fira Mono","DejaVu Sans Mono",monospace;
  }
  *{box-sizing:border-box;margin:0;padding:0}
  body{background:#11121a;color:var(--fg);font-family:var(--f);padding:22px;
       display:flex;flex-direction:column;align-items:center;gap:16px}
  .mono{font-family:var(--m)}
  .cx{width:1180px;max-width:100%;background:var(--app-bg);border-radius:11px;
      border:1px solid var(--border-sutil);overflow:hidden}
  .topo{padding:15px 20px;border-bottom:1px solid var(--border-sutil);
        position:relative;padding-left:132px}
  h1{font-size:18px;font-weight:700}
  h1 .p{color:var(--pink)}
  .sub{font-size:12.5px;color:var(--texto-mudo);margin-top:3px}
  .voltar{position:absolute;left:20px;top:17px;display:inline-flex;align-items:center;
          gap:6px;padding:5px 11px;border-radius:7px;text-decoration:none;
          border:1px solid var(--border-forte);background:var(--panel);
          color:var(--texto-suave);font-size:12px}
  .voltar:hover{border-color:var(--comment);color:var(--fg)}

  .corpo{padding:18px 20px 20px;display:flex;flex-direction:column;gap:14px}

  /* ---------- OS TRÊS ESTADOS ----------
     Os rádios vêm ANTES de tudo o que reage a eles: o `~` do CSS só enxerga
     irmão POSTERIOR. É a mesma armadilha que o interruptor da aba Jogar
     documenta, e a mesma cura. */
  .et{position:absolute;width:0;height:0;opacity:0;pointer-events:none}

  .passos{display:flex;gap:9px}
  .passo{flex:1;display:flex;gap:10px;align-items:flex-start;
         padding:11px 13px;border-radius:9px;border:1px solid var(--border-sutil);
         background:var(--panel);cursor:pointer}
  .passo .n{flex:0 0 22px;height:22px;border-radius:50%;display:flex;
            align-items:center;justify-content:center;font-family:var(--m);
            font-size:11px;border:1px solid var(--border-forte);color:var(--texto-mudo)}
  .passo b{display:block;font-size:13px;font-weight:600;margin-bottom:2px}
  .passo span.d{font-size:12px;color:var(--texto-mudo);line-height:16px}
  /* O PASSO EM QUE ELA ESTÁ. Cor explícita, nada de `opacity` — a lição medida
     da `.fita.inerte`: a opacidade tira contraste E peso do traço ao mesmo
     tempo, e o que sobra deixa de comunicar o que foi desenhado. */
  #e-parado:checked  ~ .passos .passo:nth-child(1),
  #e-medindo:checked ~ .passos .passo:nth-child(2),
  #e-pronto:checked  ~ .passos .passo:nth-child(3){
    border-color:var(--purple);background:var(--sel-bg)}
  #e-parado:checked  ~ .passos .passo:nth-child(1) .n,
  #e-medindo:checked ~ .passos .passo:nth-child(2) .n,
  #e-pronto:checked  ~ .passos .passo:nth-child(3) .n{
    border-color:var(--purple);color:var(--fg)}

  .mesa{display:flex;gap:11px}
  .ctr{flex:1;border:2px solid var(--plastico,var(--border-forte));border-radius:9px;
       background:var(--panel);padding:11px 12px 12px;display:flex;
       flex-direction:column;gap:8px;min-width:0}
  .ctr-topo{display:flex;align-items:center;gap:9px;min-width:0}
  .ctr .nome{font-size:12.5px;color:var(--texto-mudo);line-height:15px;white-space:nowrap;
             overflow:hidden;text-overflow:ellipsis}
  .ctr .nome b{color:var(--fg);font-weight:600}
  /* `height:auto` NÃO É DETALHE: o SVG nasce com `width="1160" height="800"`
     nos atributos (é o tamanho que o rasterizador do ícone usa), e sem esta
     linha o `width:74px` do CSS encolhe SÓ a largura — a altura fica em 800 e
     estica o cartão inteiro. Medido: cada cartão saía com ~900px de vazio.
     As dez abas não sofrem disto porque o `topo.html` traz a regra no esqueleto
     comum; esta página tem folha própria, e por isso precisa dizê-la. */
  .ds-svg{width:74px;height:auto;flex:0 0 74px}
  .selo{margin-left:auto;flex:0 0 auto;font-size:11px;padding:2px 8px;border-radius:6px;
        border:1px solid var(--border-forte);color:var(--texto-mudo);white-space:nowrap}
  #e-medindo:checked ~ .mesa .selo{border-color:var(--orange);color:var(--orange)}
  #e-pronto:checked  ~ .mesa .selo{border-color:var(--green);color:var(--green)}
  .selo .t2,.selo .t3{display:none}
  #e-medindo:checked ~ .mesa .selo .t1,
  #e-medindo:checked ~ .mesa .selo .t3,
  #e-pronto:checked  ~ .mesa .selo .t1,
  #e-pronto:checked  ~ .mesa .selo .t2{display:none}
  #e-medindo:checked ~ .mesa .selo .t2,
  #e-pronto:checked  ~ .mesa .selo .t3{display:inline}

  .leitura{border-top:1px solid var(--border-sutil);padding-top:7px;
           display:flex;flex-direction:column;gap:5px}
  .lin{display:flex;align-items:center;gap:7px;font-family:var(--m);font-size:11px}
  .lin > .r{flex:0 0 80px;color:var(--texto-mudo)}
  .lin > .v{flex:0 0 52px;text-align:right;color:var(--texto-suave)}
  .lin > .g{flex:1;height:4px;border-radius:2px;background:var(--border-sutil);
            position:relative;overflow:hidden}
  .lin > .g > i{position:absolute;top:0;bottom:0;left:50%;width:2px;
                background:var(--comment);transform:translateX(-1px)}
  /* NO REPOUSO A BARRA É UM RISCO NO MEIO, e é isso que a tela precisa mostrar:
     o eixo parado marca o CENTRO. É a mesma leitura da aba Controles, com a
     mesma forma — o que muda aqui é que ela responde a uma pergunta só. */
  #e-pronto:checked ~ .mesa .lin > .g > i{background:var(--green)}

  .barra{height:6px;border-radius:3px;background:var(--border-sutil);overflow:hidden}
  .barra > i{display:block;height:100%;width:0;background:var(--purple)}
  #e-medindo:checked ~ .rodape .barra > i{width:58%}
  #e-pronto:checked  ~ .rodape .barra > i{width:100%;background:var(--green)}

  .rodape{display:flex;align-items:center;gap:13px}
  .rodape .barra{flex:1}
  .btn{height:34px;padding:0 15px;border-radius:8px;font-size:13px;cursor:pointer;
       border:1px solid var(--border-forte);background:var(--panel);color:var(--texto-suave);
       display:inline-flex;align-items:center;text-decoration:none;white-space:nowrap}
  .btn:hover{border-color:var(--comment);color:var(--fg)}
  .btn.fazer{border-color:var(--green);color:var(--green)}
  .btn .t2,.btn .t3{display:none}
  #e-medindo:checked ~ .rodape .btn.fazer .t1,
  #e-medindo:checked ~ .rodape .btn.fazer .t3,
  #e-pronto:checked  ~ .rodape .btn.fazer .t1,
  #e-pronto:checked  ~ .rodape .btn.fazer .t2{display:none}
  #e-medindo:checked ~ .rodape .btn.fazer .t2,
  #e-pronto:checked  ~ .rodape .btn.fazer .t3{display:inline}
  #e-medindo:checked ~ .rodape .btn.fazer{border-color:var(--orange);color:var(--orange)}

  .aviso{font-size:12px;color:var(--texto-mudo);line-height:17px}
  .aviso b{color:var(--texto-suave);font-weight:600}
"""


def _svg(c):
    """O desenho do controle, na cor do plástico dele, sem as lâmpadas.

    As lâmpadas do jogador saem pelo mesmo motivo medido na aba Jogar: com 74px
    de desenho elas mediriam ~1,3 x 0,4 px. Abaixo de um pixel não é lâmpada
    apagada — é lâmpada que não cabe.
    """
    return re.sub(r"<\?xml[^>]*\?>\s*", "",
                  monta.svg(f'cal-{c["pref"]}', c["cor"], lampadas=False))


def _eixos(pref):
    """As seis linhas de leitura de um controle: três de giro, três de aceleração."""
    r = REPOUSO[pref]
    linhas = []
    for fam, rot, vals in (("giro", "Giroscópio", r["giro"]), ("accel", "Acelerômetro", r["accel"])):
        for i, e in enumerate("XYZ"):
            linhas.append(
                f'              <div class="lin" data-eixo="{fam}-{e.lower()}">'
                f'<span class="r">{rot if i == 0 else ""}</span>'
                f'<span class="v">{vals[i]}</span>'
                f'<span class="g"><i></i></span></div>')
    return "\n".join(linhas)


def _controle(c):
    return f'''          <div class="ctr" style="--plastico:{monta.cor_da_zona(c["cor"])}"
               data-controle="{c["pref"]}">
            <div class="ctr-topo">
              {_svg(c)}
              <span class="nome">Sony <span class="pt">•</span> <b>Player {c["jogador"]}</b><br>{c["nome"]} <span class="pt">•</span> {c["via"]}</span>
              <span class="selo"><span class="t1">Parado</span><span class="t2">Medindo…</span><span class="t3">Calibrado</span></span>
            </div>
            <div class="leitura">
{_eixos(c["pref"])}
            </div>
          </div>'''


def main():
    quem = monta.CONECTADOS
    n = len(quem)
    plural = "dos dois" if n == 2 else f"dos {n}"
    html = f'''<!doctype html>
<html lang="pt-BR">
<head>
<meta charset="utf-8">
<title>Hefesto — calibrar sensores de movimento</title>
<style>{CSS}</style>
</head>
<body>

<div class="cx">
  <div class="topo">
    <!-- O VOLTAR VOLTA PARA DE ONDE VEIO, com a Controles como fallback de quem
         abre o arquivo com duplo clique — que é como ela abre. É a mesma cura do
         `mapa.py`, e pelo mesmo motivo: uma página avulsa não sabe quem a chamou. -->
    <a class="voltar" href="02-controles.html"
       onclick="if (document.referrer) {{ history.back(); return false }}"
       title="Volta para a aba de onde você veio.">← Voltar</a>
    <h1><span class="p">Calibrar sensores de movimento</span></h1>
    <div class="sub">O giroscópio e o acelerômetro {plural} controles conectados, numa passada só.</div>
  </div>

  <div class="corpo">

    <!-- OS TRÊS ESTADOS, CLICÁVEIS. Os rádios vêm antes de tudo o que reage a
         eles — o `~` só enxerga irmão posterior. -->
    <input class="et" type="radio" name="etapa" id="e-parado" checked>
    <input class="et" type="radio" name="etapa" id="e-medindo">
    <input class="et" type="radio" name="etapa" id="e-pronto">

    <div class="passos">
      <label class="passo" for="e-parado">
        <span class="n">1</span>
        <span><b>Deixe os controles parados</b>
          <span class="d">Numa superfície plana, com os analógicos livres. Não precisa desconectar nada.</span></span>
      </label>
      <label class="passo" for="e-medindo">
        <span class="n">2</span>
        <span><b>Não toque neles</b>
          <span class="d">São {SEGUNDOS} segundos de leitura. Encostar no controle recomeça a conta dele.</span></span>
      </label>
      <label class="passo" for="e-pronto">
        <span class="n">3</span>
        <span><b>Pronto</b>
          <span class="d">O zero de cada eixo fica gravado no controle e vale para todo jogo.</span></span>
      </label>
    </div>

    <div class="mesa">
{chr(10).join(_controle(c) for c in quem)}
    </div>

    <div class="rodape">
      <button class="btn fazer"><span class="t1">Começar</span><span class="t2">Medindo…</span><span class="t3">Calibrar de novo</span></button>
      <div class="barra"><i></i></div>
      <a class="btn" href="02-controles.html">Fechar</a>
    </div>

    <!-- O QUE ELA PRECISA SABER, E SÓ ISSO. A calibração não muda ajuste nenhum
         do perfil: ela zera a leitura de repouso do aparelho. Escrever mais que
         isto seria a mesma prosa que ela mandou cortar dos tooltips. -->
    <div class="aviso">
      A calibração <b>não muda os seus ajustes</b> — ela só ensina ao controle qual é o zero dele.
      Se o cursor anda sozinho com o controle parado, é isto que resolve.
    </div>

  </div>
</div>

</body>
</html>
'''
    saida = onde.pagina("calibrar-sensores.html")
    saida.write_text("\n".join(l.rstrip() for l in html.split("\n")))
    print(f"calibrar-sensores.html: {n} controle(s) conectado(s) · 3 estados clicáveis")


if __name__ == "__main__":
    main()
