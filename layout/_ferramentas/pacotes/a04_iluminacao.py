#!/usr/bin/env python3
"""O pacote da aba `04` Iluminação — a que MAIS tem dono das dez.

O QUE O DAEMON DEVOLVE, medido em 01/09/2026 com o DualSense dela no cabo:

    lightbar_rgb       [0, 0, 255]   a cor ACESA agora            ← tem dono
    lightbar_on        bool          a barra está acesa            ← tem dono
    lightbar_source    str           quem pediu a cor              ← tem dono
    lightbar_disputada bool          a Steam abriu o controle      ← tem dono
    player             1             o número, das cinco lâmpadas  ← tem dono
    leds.lightbar_brightness   o brilho, DO PERFIL          ← tem dono

O BRILHO ESTAVA MARCADO "SEM DONO" AQUI, E ERA MEU ERRO — corrigido em
01/09/2026, depois de ela perguntar: *"vc tá corrigindo na origem esses
problemas que tá relatando né?"*. O que estava escrito:

    "o DualSense não tem brilho de barra — o que a tela chama de brilho é a
     SATURAÇÃO da cor enviada (…) um 82% ali é a tela contando uma conta que
     ninguém faz do outro lado."

A frase sobre o APARELHO pode até se sustentar; a conclusão não. O
`profiles/schema.py` tem `LedsConfig.lightbar_brightness: float = 1.0`, com
faixa declarada (`ge=0.0, le=1.0`), e **os 33 perfis dela têm o campo
preenchido**. Havia dono, em disco, o tempo todo — eu perguntei só ao
`state_full` do daemon, que não publica isto, e li a ausência como inexistência.

A distinção que FICA, porque ela muda o que a tela diz: o brilho é o que está
**salvo no perfil**, e a cor é o que está **aceso agora** (o daemon publica
`lightbar_rgb`). Quando os dois discordam, quem manda na tela é o vivo — e é por
isso que o `hex` continua vindo do daemon e só o brilho vem do disco.

A `lightbar_disputada` É O VALOR MAIS IMPORTANTE DESTA ABA, e é o que separa
esta tela de uma tela bonita: quando a Steam tem o controle aberto, a cor que o
daemon publica é a **pedida**, não a **acesa**. Pintar o hex sem dizer isso é
afirmar uma cor que pode não estar no plástico — e o produto já sabe a
diferença, é a tela que precisa contá-la.
"""
from __future__ import annotations

from . import Contexto, perfil, registrar

#: Vazio, e o vazio é uma AFIRMAÇÃO: cada valor desta aba tem dono medido. A
#: régua reprova um pacote que pinta 0 e declara 0, de propósito.
SEM_DONO: dict[str, str] = {}


def _hex(rgb) -> str:
    """`[0, 0, 255]` → `#0000FF`, e `—` quando não há cor.

    O travessão NÃO é enfeite: é a mesma marca de "não há valor" que os lugares
    vazios usam nas seis abas. Um `#000000` no lugar diria PRETO, que é uma cor.
    """
    if not rgb or len(rgb) < 3:
        return "—"
    return "#{:02X}{:02X}{:02X}".format(*(int(x) for x in rgb[:3]))


@registrar("04-iluminacao.html")
def pacote(ctx: Contexto) -> dict:
    p = perfil.ativo(ctx.state.get("active_profile"))
    leds = (p.get("leds") or {}) if p else {}
    #: O BRILHO É DO PERFIL, e é um só para a mesa — como o gatilho. O
    #: `ControllerOverrides.leds` do schema permite por controle, e quando ele
    #: estiver preenchido esta função o lê antes; enquanto não, repetir é o que
    #: corresponde ao que o produto faz.
    brilho = leds.get("lightbar_brightness")
    overrides = (p.get("controllers") or {}) if p else {}

    colunas: dict[str, dict] = {}
    for c in ctx.conectados:
        uniq = str(c.get("uniq") or "")
        rgb = c.get("lightbar_rgb") or []
        disputada = bool(c.get("lightbar_disputada"))
        meu = overrides.get(uniq) or {}
        seus = (meu.get("leds") or {}) if isinstance(meu, dict) else {}
        b = seus.get("lightbar_brightness", brilho)
        colunas[uniq] = {
            "brilho": b,
            #: A TELA MOSTRA PORCENTAGEM e o disco guarda 0..1. A conversão mora
            #: aqui, não no JS: um `0.82` chegando cru viraria "0,82%" na tela.
            "brilho-pct": None if b is None else round(float(b) * 100),
            "hex": _hex(rgb),
            "rgb": list(rgb[:3]) if len(rgb) >= 3 else [],
            "acesa": bool(c.get("lightbar_on", True)),
            "player": c.get("player"),
            "fonte": c.get("lightbar_source") or "",
            # O RECADO SÓ APARECE QUANDO A DISPUTA EXISTE. Um aviso permanente
            # vira paisagem, e paisagem ninguém lê — é a regra desta casa.
            "recado": ("A Steam tem este controle aberto: a cor publicada é a "
                       "PEDIDA, e pode não ser a acesa." if disputada else ""),
        }
    return {
        "colunas": colunas,
        "perfil": ctx.state.get("active_profile") or "",
        "sem_dono": {},
        #: SETE, não cinco: o brilho e a porcentagem entraram. Contar por uma
        #: constante escrita à mão foi o que deixou a curva da aba Gatilhos fora
        #: da cobertura na mesma leva — o número tem de sair do dicionário.
        "cobertura": {"pintados": sum(len(v) for v in colunas.values()),
                      "sem_dono": len(SEM_DONO)},
    }
