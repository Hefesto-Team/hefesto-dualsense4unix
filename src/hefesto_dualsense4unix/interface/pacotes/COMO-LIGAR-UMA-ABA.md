# Como ligar os botões de uma aba

O que você vai fazer: os botões daquela aba **agem**. O clique sai da tela,
atravessa a ponte e chega ao aparelho dela.

**Leia o exemplo antes de escrever uma linha:** `a04_iluminacao.py`, o bloco
`OS GESTOS`. Ele está comentado para ser copiado.

---

## A regra número um: NADA SE REESCREVE

Pergunta dela, 01/09/2026: *"não estamos refazendo do zero né?"* — *"em todas as
abas temos praticamente tudo pronto."* Está mesmo. Três degraus, **nesta ordem**:

| onde | o que tem | como usar |
| --- | --- | --- |
| `pacotes/ponte.py` | as 36 funções do `app/ipc_bridge.py` — a MESMA camada que a GUI estável usa | `p.led_set((r,g,b), uniq=…)` |
| `cli/cmd_*.py` | os métodos que o bridge não expõe (`native.mode.set`, `coop.set`) — puros | importe a função de lá |
| `p.chamar(metodo, …)` | o degrau cru, **só** para o que não tem nenhum dos dois | `p.chamar("lightbar.reset", uniq=…)` |

**Nunca** monte payload à mão nem abra socket. O bridge já traz o payload, o
timeout e a recusa do daemon traduzida em frase de tela.

**Não** tente reusar `app/actions/*.py`: são mixins GTK (`self._get`,
`self._toast_light`), a camada da janela antiga.

## O nome do método não diz o que ele faz

`lightbar.reset` se apresenta como *"INSTRUMENTO de medição"* — e é o que
devolve a luz ao jogo. **Leia o handler** em `daemon/ipc_handlers.py` antes de
ligar qualquer botão. `pacotes/daemon.py` te dá o mapa:

```python
from . import daemon
daemon.metodos()              # os 39 que o daemon atende, lidos do ipc_server
daemon.parametros("led.set")  # ('rgb', 'brightness', 'uniq')
```

## Os quatro passos

**1. Marque os botões no gerador** (`layout/_ferramentas/abaNN.py`), se ainda não
tiverem endereço:

```python
f'<button data-gesto="cor" data-hex="{t}" …>'
```

O piloto capta `data-gesto`, `data-hef-gesto`, `data-papel`, `data-modo`,
`data-forca`, `data-player`, `data-sensor`, `data-rota`, `data-mudo`,
`data-mic-modo`, `data-v`. Se a aba já usa um deles, **não invente um novo**.

Depois: `python3 abaNN.py` e `python3 scripts/check_o_desenho_aprovado.py --publicar NN`.

**2. Escreva os gestos** no fim do seu `aNN_*.py`:

```python
from . import gesto  # noqa: E402


@gesto("NN-x.html", "nome-do-gesto")
def algo(ctx: Contexto, o: dict, p) -> None:
    """Uma linha dizendo o que o botão faz, e o porquê do método escolhido."""
    uniq = str(o.get("uniq") or "")
    if not uniq:
        raise ValueError("algo: o clique não disse em qual controle")
    p.trigger_set("left", "Rigid", [0, 180])


PONTE = {"trigger_set"}      # as funções da ponte que você usa
METODOS: set[str] = set()    # os métodos crus, se usar `p.chamar`
```

* `ctx` — a mesa e o estado do daemon (`ctx.conectados`, `ctx.por_uniq(uniq)`)
* `o` — o clique: `uniq` (já traduzido de `pref`), `texto`, `hex`, `player`,
  `lado`, `campo`, `modo`, `forca`, `sensor`, `rota`, `mudo`, `v` — e, desde
  01/09/2026, **o valor de campos e listas**:

  | campo | o que traz |
  | --- | --- |
  | `valor` | o `value` de um `<input>` ou `<select>` — o que ela digitou ou escolheu |
  | `rotulo` | o texto VISÍVEL da opção escolhida num `<select>` |
  | `tipo` | `input`, `select`, `button`… |
  | `evento` | `click` ou `change` |

  **`texto` num `<input>` é VAZIO** — foi a causa de metade dos botões que a
  primeira leva não conseguiu ligar. Para campo e lista, use `valor`.
* `p` — a ponte

**3. Declare o piso e as provas NO SEU PACOTE** — nunca no arquivo de teste.
Ele é lido por ele, e é o que dá território exclusivo a cada aba:

```python
PAGINA = "NN-x.html"
PISO_DA_ABA = 3          # quantos gestos esta aba tem. Só sobe.
PROVAS = [
    {"pagina": PAGINA, "gesto": "nome-do-gesto",
     "clique": {"lado": "e"},                       # o que o botão manda
     "chama": [("trigger_set", ["left", "Rigid", [0, 180]], {})]},
]
```

`chama` é a lista **na ordem**: um botão pode precisar de duas chamadas — o
"Automático" da Iluminação larga o claim e SÓ ENTÃO pinta a cor padrão, e
invertidas o reset apagaria a cor que acabou de ir.

O `uniq` do clique de prova é sempre `aa:bb:cc:00:00:01` (faixa sintética da
casa — há dois portões de anonimato nesta árvore).

**4. Prove clicando**, com a janela OCULTA — ela tem UMA tela:

```bash
HEFESTO_VARIANTE=dev .venv/bin/python -u layout/_ferramentas/hefesto_vivo.py \
    --oculta --abre NN-x.html --segundos 9 --prova-clique "nome-do-gesto"
```

Tem de sair `[gesto] NN-x.html · nome → aplicado`. E leia o estado do daemon
antes e depois: se o botão promete mudar algo, o número tem de mudar.

## O que NÃO tem dono não vira botão que finge

Se o daemon não faz aquilo, **não ligue**. Deixe sem gesto: o piloto o recusa
dizendo o nome, e ele sai no relato como inventário do que falta. Um botão que
responde calado é pior que um que recusa — quem clicou conclui que funcionou.

Sete gestos da aba Sistema estão assim de propósito (`reiniciar`, `desligar`,
`autostart`, `refazer-consertos`…): são `systemctl`, não IPC.

## Duas decisões dela que valem para todas as abas

1. **Clicar já aplica.** Ação imediata, não rascunho à espera de um "Aplicar".
2. **Nada fica num estado morto.** Se largar um recurso (como a luz volta para o
   jogo), deixe um valor padrão do produto — nunca preto, nunca vazio. A paleta,
   os presets e os padrões já existem: `core/led_control.player_slot_color`,
   `app/actions/trigger_specs.PRESETS`.

## Antes de dizer que terminou

```bash
source .envrc-voo
.venv/bin/ruff check layout/_ferramentas/pacotes/ tests/
HEFESTO_VARIANTE=dev .venv/bin/python -m pytest tests/unit/test_os_botoes_tem_dono.py -q
```

E **morda a própria cura**: troque a chamada por `pass` e veja a régua reprovar.
Régua que passa com a cura arrancada não mede nada.

## Território

Você toca **só**: o seu `aNN_*.py`, o seu `layout/_ferramentas/abaNN.py`, e as
suas linhas no `PISO`/`parametrize` do teste. Não toque em `ponte.py`,
`daemon.py`, `__init__.py`, `hefesto_vivo.py` nem no pacote de outra aba.
