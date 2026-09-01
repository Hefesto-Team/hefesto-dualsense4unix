#!/usr/bin/env python3
"""O pacote da aba `03` Gatilhos — e ele nasceu ERRADO, corrigido em 01/09/2026.

O QUE ESTAVA ESCRITO AQUI, e era meu, e estava errado:

    "o modo escolhido      NÃO EXISTE no state    ← sem dono
     o efeito pronto       NÃO EXISTE no state    ← sem dono
     os ajustes do modo    NÃO EXISTEM no state   ← sem dono"

A parte factual continua verdadeira: o `state_full` do daemon **não** publica
`triggers`, e o DualSense não devolve o modo em que está — gatilho adaptativo é
comando de ida. O que estava errado era a CONCLUSÃO: dali eu tirei "não tem
dono" e pintei quatro travessões.

ELA PEGOU COM UMA PERGUNTA SÓ: *"vc tá corrigindo na origem esses problemas que
tá relatando né?"* Não estava. O dado tem dono, e são dois, os dois já no
produto que ela usa:

    profiles/schema.py       `triggers.left/right` → `mode` e `params`
    app/actions/trigger_specs.py   `PRESETS`: `name` (disco) → `label` (tela)
                                   e cada `param` com nome, faixa e padrão

MEDIDO NO DISCO DELA, perfil "Ação", em 01/09/2026::

    triggers.left  = {"mode": "Rigid",     "params": [0, 180]}
    triggers.right = {"mode": "Vibration", "params": [3, 8, 20]}

Cinco dos 33 perfis dela têm gatilho configurado. Mostrar `—` ali era apagar da
tela uma escolha que ela salvou.

O QUE AINDA NÃO TEM DONO, e agora a lista é honesta: nada desta aba. O que muda
é a NATUREZA do valor — ele é o que está **salvo no perfil**, não o que está
**aceso no plástico**, e essas são coisas diferentes. Como o aparelho não
devolve a segunda, a primeira é a melhor verdade disponível, e a tela diz de
qual está falando.
"""
from __future__ import annotations

from . import Contexto, perfil, registrar

#: Nada. E a lista vazia é uma AFIRMAÇÃO, não um esquecimento: cada valor desta
#: aba tem dono medido, e a régua de cobertura conta este zero junto com os
#: `pintados` — um pacote que pinta 0 e declara 0 é reprovado por
#: `test_o_despachante_serve_as_dez.py`, de propósito.
SEM_DONO: dict[str, str] = {}

#: O LADO NA TELA E O LADO NO DISCO. A tela usa `e`/`d` (o L2 e o R2 do
#: desenho); o perfil usa `left`/`right`. Dois vocabulários, uma tradução, num
#: lugar só — a regra da casa é que o que tem dono não se digita.
LADOS = {"e": "left", "d": "right"}


def _specs():
    """A tabela de presets do produto, ou `None` se o `src/` não abrir.

    `None` NÃO vira travessão silencioso: sem a tabela, o pacote não sabe
    traduzir `Rigid` para `Rígido` nem nomear os ajustes, e devolver rótulos
    crus seria pior que devolver nada. Quem chama trata.
    """
    try:
        perfil._com_o_src()
        from hefesto_dualsense4unix.app.actions import trigger_specs

        return trigger_specs
    except Exception:
        return None


def _do_lado(cfg: dict, specs) -> dict:
    """Um lado do gatilho, do perfil para a tela.

    `cfg` é o `{"mode": "Rigid", "params": [0, 180]}` do disco. Sai o rótulo em
    português, o nome de cada ajuste e o valor que ela salvou — que é o que as
    três linhas da aba mostram: Modo, Efeito pronto e Ajustes.
    """
    nome = str((cfg or {}).get("mode") or "Off")
    valores = list((cfg or {}).get("params") or [])
    spec = specs.get_spec(nome) if specs else None

    fora: dict[str, object] = {
        "modo": spec.label if spec else nome,
        # O `name` cru viaja junto: é o contrato de disco, e é por ele que a
        # tela sabe qual botão acender sem depender do texto traduzido.
        "modo-chave": nome,
        "pronto": "— Nenhum —",
        "ajustes": [],
    }
    if spec is None:
        return fora

    #: A CURVA, e ela é a segunda forma que o disco guarda. Medido nos 33
    #: perfis dela em 01/09/2026: `Rigid` grava `[0, 180]` — um escalar por
    #: ajuste — mas `MultiPositionFeedback` e `MultiPositionVibration` gravam
    #: `[[1], [2], ..., [8]]`, dez posições do curso, cada uma numa lista de um.
    #:
    #: São DOIS controles de tela diferentes: o primeiro é um punhado de
    #: sliders com nome, o segundo é o desenho de dez barrinhas que a aba chama
    #: de "Curva de força" e "Vibração por posição". Tratar os dois pela mesma
    #: conta foi o que quebrou este pacote na primeira execução — `[1] - 0`
    #: não é uma subtração que exista.
    if any(isinstance(v, list) for v in valores):
        fora["curva"] = [int(v[0]) if isinstance(v, list) and v else int(v or 0)
                         for v in valores]
        # A escala da curva é 0..8, a mesma dos `_RAMPA_PADRAO` do produto.
        fora["curva-pct"] = [round(max(0, min(100, x / 8 * 100))) for x in fora["curva"]]
        return fora

    #: O EFEITO PRONTO é o próprio preset quando ele não é o `Off`. A tela tinha
    #: uma linha separada para isto porque o mockup previa presets de curva; até
    #: existir um segundo eixo, o pronto É o modo, e dizer o nome dele é mais
    #: verdadeiro que dizer "Nenhum".
    if nome != "Off":
        fora["pronto"] = spec.label

    for i, p in enumerate(spec.params):
        valor = valores[i] if i < len(valores) else p.default
        largura = max(1, p.max_value - p.min_value)
        fora["ajustes"].append({
            "nome": p.label,
            "valor": valor,
            # A PORCENTAGEM É DA FAIXA DAQUELE AJUSTE, não de 0..255. Um
            # `force` vai de 0 a 255 e uma `position` de 0 a 9; dividir os dois
            # pela mesma escala pintaria a barra da posição sempre no chão.
            "pct": round(max(0, min(100, (valor - p.min_value) / largura * 100))),
            "min": p.min_value, "max": p.max_value,
        })
    return fora


@registrar("03-gatilhos.html")
def pacote(ctx: Contexto) -> dict:
    """Endereço → valor, por controle da mesa.

    O gatilho é do PERFIL, e o perfil é um só para a mesa inteira — logo as
    colunas recebem o mesmo modo. Isso não é preguiça: o `ControllerOverrides`
    do schema permite gatilho por controle, e quando ele estiver preenchido esta
    função lê o override antes do perfil. Enquanto não estiver, repetir o valor
    é o que corresponde ao que o produto faz.
    """
    specs = _specs()
    p = perfil.ativo(ctx.state.get("active_profile"))
    trig = (p.get("triggers") or {}) if p else {}
    overrides = (p.get("controllers") or {}) if p else {}

    lados = {sig: _do_lado(trig.get(disco) or {}, specs) for sig, disco in LADOS.items()}

    colunas: dict[str, dict] = {}
    pintados = 0
    for c in ctx.conectados:
        uniq = str(c.get("uniq") or "")
        entradas = c.get("inputs") or {}
        l2, r2 = entradas.get("l2_raw"), entradas.get("r2_raw")

        #: O OVERRIDE POR CONTROLE VENCE O PERFIL, e é o que o produto faz —
        #: `ControllerOverrides.triggers` existe no schema desde antes desta aba.
        meu = overrides.get(uniq) or {}
        seus = (meu.get("triggers") or {}) if isinstance(meu, dict) else {}
        deste = {sig: (_do_lado(seus[disco], specs) if seus.get(disco) else lados[sig])
                 for sig, disco in LADOS.items()}

        col: dict[str, object] = {
            "l2-raw": l2, "r2-raw": r2,
            "l2-pct": round((l2 or 0) / 255 * 100),
            "r2-pct": round((r2 or 0) / 255 * 100),
        }
        for sig, d in deste.items():
            col[f"modo-{sig}"] = d["modo"]
            col[f"modo-chave-{sig}"] = d["modo-chave"]
            col[f"pronto-{sig}"] = d["pronto"]
            for i, aj in enumerate(d["ajustes"]):
                col[f"aj-nome-{sig}-{i}"] = aj["nome"]
                col[f"aj-val-{sig}-{i}"] = aj["valor"]
                col[f"aj-pct-{sig}-{i}"] = aj["pct"]
            # A CURVA VAI JUNTO, e ela precisa entrar na CONTAGEM: sem estas
            # duas linhas o perfil "Aventura" — que é curva nos dois lados —
            # pintava 10 valores enquanto o "Ação" pintava 25, e a cobertura
            # diria que a aba está meio ligada quando ela está inteira.
            if d.get("curva"):
                col[f"curva-{sig}"] = d["curva"]
                col[f"curva-pct-{sig}"] = d["curva-pct"]
        colunas[uniq] = col
        pintados += len(col)

    return {
        "colunas": colunas,
        "perfil": ctx.state.get("active_profile") or "",
        "sem_dono": {},
        "cobertura": {"pintados": pintados, "sem_dono": len(SEM_DONO)},
    }
