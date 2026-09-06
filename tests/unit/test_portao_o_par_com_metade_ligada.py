"""O PORTÃO DO PAR COM METADE LIGADA — ``VPAD-SUSPENSO-MORTO-01``, E3.

O DEFEITO, MEDIDO: **existe quem retoma e não existe quem suspende.** A flag
``daemon._steam_input_vpad_suspenso`` só pode andar para ``False`` desde
``d8022ea`` (09/08/2026), e o produto continua LENDO os dois valores dela. Uma
das duas respostas é impossível, e nada no produto diz isso: **é pior que
ausência de dado, é dado que mente sempre para o mesmo lado.**

O RAIO DO ESTRAGO — cinco leitores em produção, e DOIS estão na tela
--------------------------------------------------------------------
Censo de 25/08/2026. Nenhum destes cinco pode responder ``True``:

1. ``daemon/lifecycle.py:2270`` — ``CALADA_VPAD_SUSPENSO`` é a razão de calada
   do gate do desktop, e ela **nunca é devolvida**;
2. ``daemon/subsystems/hotkey.py:261`` — ramo de modo, num ``or`` cujo outro
   lado (``steam_input_excecao_ativa``) carrega a decisão sozinho;
3. ``daemon/ipc_handlers.py:2210`` — publica ``vpad_suspenso`` no ``state_full``
   sempre ``False``, e a docstring ao lado documenta um contrato de DOIS estados
   dos quais um é inalcançável;
4. ``app/actions/home_actions.py:1139`` (**Onda 2 · Início**) — a frase da
   ponte exige ``excecao_ativa and vpad_suspenso``: a aba **nunca** consegue
   dizer "pelo Steam Input";
5. ``app/actions/emulation_actions.py:529`` (**Onda 5 · Emulação**) — a frase
   *"Ligado, em pausa agora: neste jogo quem entrega o controle é a Steam, e o
   controle virtual foi recolhido"* está escrita, revisada, e é **inalcançável**:
   a chave dela É a constante do item 1.

Os três primeiros este portão nomeia sozinho (ver ``_leituras``). Os dois da
tela atravessam o dicionário do IPC, e a fronteira está declarada lá.

O QUE ESTE PORTÃO PERGUNTA, e por que não é a pergunta do irmão
---------------------------------------------------------------
``portao_a_casa_sabe_e_o_produto_nao_faz.py`` mede ALCANCE POR SÍMBOLO: *esta
função tem chamador em produção?* Ele **não pega** este caso, e não por
descuido — ele o classificou, em 12/08/2026, como LÁPIDE COM NOTA DATADA em
``_NAO_E_PROMESSA``, com a razão escrita: *"Não deve chamador: ela deve
continuar não sendo chamada."* Aquela classificação está CERTA sobre a função e
é CEGA sobre a consequência: a lápide deixou uma FLAG viva, lida em produção, e
metade dos valores dela virou inalcançável.

A pergunta daqui é outra, e é sobre o ESTADO, não sobre o símbolo:

    **existe caminho de produção que ponha esta flag em CADA um dos dois
    valores que o produto lê?**

Duas réguas independentes é o que revela — é regra desta casa, medida no
``vdf`` com três árvores ``apps`` (16/08/2026) e de novo no MAC com dois
portões de forma diferente (25/08/2026). Uma régua que respondesse às duas
perguntas de uma vez teria de escolher uma resposta para o par
``suspend``/``resume``, e as duas respostas certas são diferentes: a função
fica, o estado mente.

A CLASSE INTEIRA, não este caso
--------------------------------
O defeito é **assimetria de par**: uma metade ligada, a outra não. A varredura
não procura nome de par (``armar``/``desarmar``, ``suspend``/``resume``,
``enable``/``disable``) porque convenção de nome é CITAÇÃO, não DECLARAÇÃO — o
irmão já mediu e reprovou essa via em 12/08/2026, com 525 apelidos únicos em
``src/``. Ela procura o FATO: quem escreve ``True`` neste atributo, quem
escreve ``False``, e qual dos dois lados tem chamador em produção.

MEDIDO em 25/08/2026 na árvore inteira: 17 flags booleanas de ``daemon/`` têm
escritor dos dois lados; **uma** é assimétrica, e é a da sprint. Um portão que
acusa dezessete não é portão, é ruído; um que acusa zero é decoração. Este
acusa uma, e ela é a certa — a régua foi conferida contra resposta já
conhecida antes de valer (armadilha A5).

O QUE ESTE PORTÃO **NÃO** VIGIA, e o preço de cada escolha
-----------------------------------------------------------
- **Flag assimétrica que NINGUÉM lê.** Fica de fora de propósito: sem leitor
  ela é código morto, e código morto é assunto do irmão. O defeito daqui é o
  produto RELATAR um estado que não consegue produzir; sem leitor não há
  relato. O preço: uma flag assimétrica e muda passa por aqui em silêncio.
- **Duas classes que usam o MESMO nome de atributo** são medidas como uma flag
  só. ``_dirty`` e ``_loaded`` vivem em ``identity.py`` e
  ``external_identity.py`` ao mesmo tempo. Agrupar por módulo seria pior e foi
  medido: ``gamepad_emulation_enabled`` recebe ``True`` em ``lifecycle.py`` e
  ``False`` em ``gamepad.py``, e por módulo cada metade pareceria órfã — o
  portão gritaria com quem está certo, que é a pior coisa que um portão faz.
  O preço da escolha: um homônimo simétrico esconderia um homônimo assimétrico.
- **Valor que não é literal booleano.** ``daemon._x = alguma_coisa()`` não
  entra. Um atributo escrito por expressão não declara qual valor pretende, e
  adivinhar seria inventar medição.
- **Alcance é a RÉGUA PLANA** (existe chamada deste nome em ``src/``, fora do
  próprio corpo), não o fecho de import do irmão. Basta para a pergunta daqui:
  ela é "existe caminho", e um armador com zero chamadas em ``src/`` não tem
  caminho nenhum, alcançado ou não. O preço: um armador chamado só por um
  módulo que ninguém importa passa por aqui e é acusado lá.

AS DUAS ARMADILHAS QUE ESTA VARREDURA JÁ CAIU, e como não cai mais
------------------------------------------------------------------
As duas foram medidas em 25/08/2026, escrevendo este portão, e as duas deixavam
``suspend_vpads_for_steam_input`` parecer viva:

1. **DOCSTRING contada como chamador.** O nome aparece dezoito vezes em prosa
   dentro de ``gamepad.py`` — e a régua que lê literais de texto para pegar
   despacho por ``getattr`` engolia as dezoito. A primeira medição saiu VERDE
   com o defeito na frente dela.
2. **``__all__`` contado como chamador.** ``"suspend_vpads_for_steam_input"``
   está na lista de reexportação, que é literal de texto como qualquer outro.

Docstring e ``__all__`` são descartados, e ``test_a_regua_nao_confunde_prosa_
com_chamador`` planta os dois de propósito para provar que continuam sendo.

A MORDIDA (arranque a cura, veja reprovar, devolva)
----------------------------------------------------
- **tire a entrada de ``_steam_input_vpad_suspenso`` de ``_PAR_ACEITO``**: o
  portão reprova nomeando o armador sem chamador e os dois desarmadores vivos.
  É o defeito de hoje, medido pelo instrumento, sem plantio nenhum;
- **dê um chamador em produção a ``suspend_vpads_for_steam_input``**: o portão
  reprova pela outra direção — a entrada do registro virou lápide de um defeito
  que acabou, e registro que não se limpa vira paisagem. É esta metade que
  avisa quem coordena, sozinha, se alguma frente RELIGAR a suspensão.

Os dois lados também são exercitados por dublê em ``TestOPortaoMorde``, sobre
uma cópia de ``src/`` — régua que só sabe passar não é régua (armadilha A2).
"""

from __future__ import annotations

import ast
import re
import shutil
from dataclasses import dataclass, field
from pathlib import Path

_RAIZ = Path(__file__).resolve().parents[2]
_SRC = _RAIZ / "src" / "hefesto_dualsense4unix"

#: Onde a sprint mandou olhar. O daemon é quem tem estado de sessão em memória;
#: a janela lê o que ele publica e não guarda par nenhum.
_TERRITORIO = "daemon"


# ===========================================================================
# O registro — assimetria com razão datada
# ===========================================================================

#: Pares cuja metade desligada é DECISÃO, não descuido. A chave é o nome do
#: atributo; a razão cita a medição que a sustenta, porque "confie em mim" não
#: é razão. Uma entrada que deixa de ser verdade REPROVA — ver
#: `test_nenhuma_declaracao_ficou_obsoleta`.
_PAR_ACEITO: dict[str, str] = {
    "_steam_input_vpad_suspenso": (
        "MEDIDO em 25/08/2026 (VPAD-SUSPENSO-MORTO-01/E1). O armador "
        "`suspend_vpads_for_steam_input` (daemon/subsystems/gamepad.py:882) tem ZERO "
        "chamadores em src/; os desarmadores `resume_vpads_after_steam_input` "
        "(gamepad.py:526) e `start_gamepad_emulation_desfecho` (lifecycle.py:1635) "
        "estão vivos. NÃO é descuido: o commit `d8022ea` (09/08/2026) tirou a chamada "
        "da borda de entrada da exceção de Steam Input e pôs `esconder_o_fisico_para_o_"
        "jogo` no lugar, por decisão DELA — ESCONDER-EM-VEZ-DE-SAIR-01, *a allowlist do "
        "Steam Input NÃO tira o Hefesto da frente*. O preço que matou a suspensão foi "
        "medido na máquina dela em 08/08: o jogador 2 É um gamepad virtual, e derrubar "
        "os virtuais para curar o duplicado do P1 derrubava o P2 junto "
        "(`coop_derrubado_pela_excecao_steam_input`, 20 ocorrências num dia). "
        "A ENTRADA FICA ATÉ A DECISÃO DELA, e o que falta está escrito: são CINCO os "
        "leitores em produção, e DOIS deles estão na tela — a frase da ponte em "
        "app/actions/home_actions.py:1139 (Início) e a frase do vpad recolhido em "
        "app/actions/emulation_actions.py:529 (Emulação) são inalcançáveis. Os outros "
        "três: lifecycle.py:2270 (CALADA_VPAD_SUSPENSO), hotkey.py:261 e "
        "ipc_handlers.py:2210, e nenhuma dessas leituras pode ser verdadeira. Ou as "
        "leituras saem, ou a suspensão ganha caminho de volta — as duas mexem em "
        "arquivo de outra frente e a escolha é DELA, não deste portão."
    ),
}

#: Toda razão carrega data: razão sem idade vira paisagem. Mesmo par de réguas
#: do irmão (`portao_a_casa_sabe_e_o_produto_nao_faz._confere_razoes`).
_DATA = re.compile(r"\b\d{2}/\d{2}/\d{4}\b")

#: Abaixo disto a razão não cabe o endereço de onde a metade se perdeu.
_RAZAO_MINIMA = 120


# ===========================================================================
# A varredura
# ===========================================================================


@dataclass
class Par:
    """Uma flag booleana de sessão e as duas metades que a escrevem."""

    flag: str
    armadores: dict[str, bool] = field(default_factory=dict)
    desarmadores: dict[str, bool] = field(default_factory=dict)
    leituras: list[str] = field(default_factory=list)

    @property
    def metade_morta(self) -> str:
        """``True`` ou ``False`` — qual dos dois valores nenhum caminho alcança."""
        if not any(self.armadores.values()):
            return "True"
        return "False"

    def descreva(self) -> str:
        vivos = self.desarmadores if self.metade_morta == "True" else self.armadores
        mortos = self.armadores if self.metade_morta == "True" else self.desarmadores
        # As leituras vão INTEIRAS, uma por linha. Truncar a lista era o defeito
        # do próprio instrumento: quem lê a reprovação precisa do endereço de
        # CADA sítio que vai passar a mentir, e é essa lista que roteia o
        # conserto entre as frentes. Cortar no sexto escondia `hotkey.py`.
        enderecos = "\n".join(f"        {onde}" for onde in self.leituras)
        return (
            f"{self.flag}: nenhum caminho de produção põe {self.metade_morta}.\n"
            f"    sem chamador: {sorted(nome for nome in mortos)}\n"
            f"    vivos       : {sorted(nome for nome, ok in vivos.items() if ok)}\n"
            f"    lida em ({len(self.leituras)}):\n{enderecos}"
        )


def _prosa(arvore: ast.AST) -> set[int]:
    """Os literais que NÃO são despacho: docstring de módulo/classe/função e ``__all__``.

    As duas armadilhas do cabeçalho moram aqui. Sem este descarte, um nome
    citado dezoito vezes na própria docstring conta como dezoito chamadores — e
    foi assim que a primeira medição deste portão saiu verde com o defeito na
    frente dela.
    """
    fora: set[int] = set()
    for no in ast.walk(arvore):
        corpo = getattr(no, "body", None)
        if (
            isinstance(
                no, (ast.Module, ast.ClassDef, ast.FunctionDef, ast.AsyncFunctionDef)
            )
            and isinstance(corpo, list)
            and corpo
            and isinstance(corpo[0], ast.Expr)
            and isinstance(corpo[0].value, ast.Constant)
            and isinstance(corpo[0].value.value, str)
        ):
            fora.add(id(corpo[0].value))
        if isinstance(no, ast.Assign):
            for alvo in no.targets:
                if isinstance(alvo, ast.Name) and alvo.id == "__all__":
                    fora.update(id(sub) for sub in ast.walk(no.value))
    return fora


class _Escritas(ast.NodeVisitor):
    """Quem escreve literal booleano em atributo, e dentro de qual função."""

    def __init__(self) -> None:
        self.pilha: list[str] = []
        self.achados: list[tuple[str, bool, str]] = []

    def _funcao(self, no: ast.FunctionDef | ast.AsyncFunctionDef) -> None:
        self.pilha.append(no.name)
        self.generic_visit(no)
        self.pilha.pop()

    # O nome mixedCase é EXIGÊNCIA do `ast.NodeVisitor`, que despacha por
    # `visit_<Nome do nó>` — renomear para minúsculas desliga o visitante em
    # silêncio, e a varredura ficaria verde sem ver função nenhuma.
    visit_FunctionDef = _funcao  # type: ignore[assignment]  # noqa: N815
    visit_AsyncFunctionDef = _funcao  # type: ignore[assignment]  # noqa: N815

    def visit_Assign(self, no: ast.Assign) -> None:
        valor = no.value
        if isinstance(valor, ast.Constant) and isinstance(valor.value, bool):
            for alvo in no.targets:
                if isinstance(alvo, ast.Attribute):
                    dono = self.pilha[0] if self.pilha else "<módulo>"
                    self.achados.append((alvo.attr, valor.value, dono))
        self.generic_visit(no)


@dataclass
class _Indice:
    """O que a régua plana precisa saber sobre ``src/`` inteiro."""

    chamadas: dict[str, list[tuple[Path, int]]]
    corpos: dict[str, list[tuple[Path, int, int]]]
    palavras: set[str]


def _modulos(raiz: Path) -> list[Path]:
    return sorted(p for p in raiz.rglob("*.py") if "__pycache__" not in p.parts)


def _indexar(raiz: Path) -> _Indice:
    chamadas: dict[str, list[tuple[Path, int]]] = {}
    corpos: dict[str, list[tuple[Path, int, int]]] = {}
    palavras: set[str] = set()
    for caminho in _modulos(raiz):
        try:
            arvore = ast.parse(caminho.read_text(encoding="utf-8"))
        except SyntaxError:  # pragma: no cover - árvore em movimento
            continue
        fora = _prosa(arvore)
        for no in ast.walk(arvore):
            if isinstance(no, (ast.FunctionDef, ast.AsyncFunctionDef)):
                fim = no.end_lineno or no.lineno
                corpos.setdefault(no.name, []).append((caminho, no.lineno, fim))
            elif isinstance(no, ast.Call):
                alvo = no.func
                nome = getattr(alvo, "id", None) or getattr(alvo, "attr", None)
                if isinstance(nome, str):
                    chamadas.setdefault(nome, []).append((caminho, no.lineno))
            elif (
                isinstance(no, ast.Constant)
                and isinstance(no.value, str)
                and id(no) not in fora
                and no.value.isidentifier()
            ):
                # Despacho por string (`getattr(x, "nome")`) é caminho de produção,
                # e ignorá-lo pegou a varredura do irmão CINCO vezes numa medição só.
                #
                # O `isidentifier()` NASCEU EM 25/08/2026, e nasceu de um defeito
                # reproduzido pelo agente da aba Emulação: sem ele, a régua fazia
                # `findall` de TODA palavra de TODA string — e uma FRASE DE TELA que
                # citasse o nome do símbolo bastava para o portão declarar "tem
                # chamador" e se calar. Ele mesmo silenciou este portão sem querer,
                # escrevendo o nome numa mensagem de erro.
                #
                # Despacho por string é sempre o nome INTEIRO e sozinho
                # (`getattr(x, "meu_metodo")`, `_HANDLERS["meu_metodo"]`); prosa
                # nunca é. Descartar a prosa é o que separa uma régua que mede de
                # uma que se desliga quando alguém escreve bem.
                palavras.add(no.value)
    return _Indice(chamadas=chamadas, corpos=corpos, palavras=palavras)


def _tem_chamador(nome: str, indice: _Indice) -> bool:
    """Régua plana: alguém em ``src/`` chama este nome fora do próprio corpo?

    ``__init__`` e companhia contam sempre: quem os chama é a linguagem, e
    cobrar chamador explícito deles acusaria toda classe da árvore.
    """
    if nome.startswith("__") and nome.endswith("__"):
        return True
    if nome in indice.palavras:
        return True
    corpos = indice.corpos.get(nome, [])
    for arquivo, linha in indice.chamadas.get(nome, []):
        dentro = any(
            arquivo == outro and inicio <= linha <= fim
            for outro, inicio, fim in corpos
        )
        if not dentro:
            return True
    return False


def _le_a_flag(no: ast.AST, flag: str) -> bool:
    """Este nó lê a flag — ``daemon._x`` em ``Load`` ou ``getattr(daemon, "_x")``?"""
    if isinstance(no, ast.Attribute) and no.attr == flag and isinstance(no.ctx, ast.Load):
        return True
    if isinstance(no, ast.Call):
        alvo = no.func
        if (getattr(alvo, "id", None) or getattr(alvo, "attr", None)) == "getattr":
            return any(
                isinstance(arg, ast.Constant) and arg.value == flag for arg in no.args
            )
    return False


def _acessores(flag: str, raiz: Path) -> set[str]:
    """As funções de ``src/`` que DEVOLVEM a flag.

    ``steam_input_vpad_suspenso`` é o caso de hoje: ela envelopa
    ``getattr(daemon, "_steam_input_vpad_suspenso", False)`` num ``return``, e
    é por ela que passam TRÊS dos cinco leitores. Sem este salto o portão
    encontrava dois endereços e o defeito tinha cinco.
    """
    nomes: set[str] = set()
    for caminho in _modulos(raiz):
        texto = caminho.read_text(encoding="utf-8")
        if flag not in texto:
            continue
        try:
            arvore = ast.parse(texto)
        except SyntaxError:  # pragma: no cover - árvore em movimento
            continue
        for no in ast.walk(arvore):
            if not isinstance(no, (ast.FunctionDef, ast.AsyncFunctionDef)):
                continue
            for dentro in ast.walk(no):
                if (
                    isinstance(dentro, ast.Return)
                    and dentro.value is not None
                    and any(_le_a_flag(sub, flag) for sub in ast.walk(dentro.value))
                ):
                    nomes.add(no.name)
                    break
    return nomes


def _leituras(flag: str, raiz: Path) -> list[str]:
    """Onde ``src/`` LÊ a flag — direto, e um SALTO pelo acessor que a devolve.

    UM salto, e não mais, e a fronteira é declarada: quem lê o valor depois de
    ele virar chave de dicionário no IPC (``"vpad_suspenso"`` no ``state_full``)
    fica de fora. Seguir string por travessia de serialização seria adivinhar, e
    o cabeçalho já recusou adivinhação uma vez. **O preço, medido em 25/08/2026:
    os dois leitores da JANELA — a frase da ponte em ``app/actions/home_actions.py``
    e a frase do vpad recolhido em ``app/actions/emulation_actions.py`` — não
    aparecem nesta lista, e são justamente os dois que a pessoa lê na tela.**
    Estão escritos no relatório da sprint; o portão não os alcança sozinho.
    """
    acessores = _acessores(flag, raiz)
    achados: list[str] = []
    for caminho in _modulos(raiz):
        texto = caminho.read_text(encoding="utf-8")
        if flag not in texto and not any(nome in texto for nome in acessores):
            continue
        try:
            arvore = ast.parse(texto)
        except SyntaxError:  # pragma: no cover - árvore em movimento
            continue
        fora = _prosa(arvore)
        corpos = {
            no.name: (no.lineno, no.end_lineno or no.lineno)
            for no in ast.walk(arvore)
            if isinstance(no, (ast.FunctionDef, ast.AsyncFunctionDef))
        }
        for no in ast.walk(arvore):
            if _le_a_flag(no, flag):
                achados.append(f"{caminho.relative_to(raiz)}:{no.lineno}")
                continue
            if not isinstance(no, ast.Call):
                continue
            alvo = no.func
            nome = getattr(alvo, "id", None) or getattr(alvo, "attr", None)
            if nome not in acessores or id(no) in fora:
                continue
            faixa = corpos.get(str(nome))
            if faixa and faixa[0] <= no.lineno <= faixa[1]:
                # A chamada está DENTRO do próprio acessor: recursão, não leitor.
                continue
            achados.append(f"{caminho.relative_to(raiz)}:{no.lineno} (via {nome})")
    return sorted(set(achados))


def pares_com_metade_ligada(raiz: Path | None = None) -> dict[str, Par]:
    """As flags de ``daemon/`` que o produto lê e só consegue escrever de um lado.

    Devolve dicionário vazio quando a árvore está sã — e essa é a resposta
    esperada assim que a decisão dela fechar o caso do registro.
    """
    alvo = raiz or _SRC
    territorio = alvo / _TERRITORIO
    if not territorio.is_dir():  # pragma: no cover - cópia mutilada
        return {}

    escritas: dict[str, dict[bool, set[str]]] = {}
    for caminho in _modulos(territorio):
        try:
            arvore = ast.parse(caminho.read_text(encoding="utf-8"))
        except SyntaxError:  # pragma: no cover - árvore em movimento
            continue
        visitante = _Escritas()
        visitante.visit(arvore)
        for flag, valor, dono in visitante.achados:
            escritas.setdefault(flag, {True: set(), False: set()})[valor].add(dono)

    indice = _indexar(alvo)
    acusados: dict[str, Par] = {}
    for flag, lados in sorted(escritas.items()):
        if not lados[True] or not lados[False]:
            # Flag de mão única não é PAR: ela nunca prometeu dois estados.
            continue
        par = Par(
            flag=flag,
            armadores={nome: _tem_chamador(nome, indice) for nome in sorted(lados[True])},
            desarmadores={
                nome: _tem_chamador(nome, indice) for nome in sorted(lados[False])
            },
        )
        if any(par.armadores.values()) and any(par.desarmadores.values()):
            continue
        par.leituras = _leituras(flag, alvo)
        if not par.leituras:
            # Sem leitor não há relato, e sem relato não há mentira: é código
            # morto, e código morto é assunto do portão irmão.
            continue
        acusados[flag] = par
    return acusados


# ===========================================================================
# O portão
# ===========================================================================


class TestTodoParTemAsDuasMetadesLigadas:
    """Um estado que o produto lê e não consegue produzir é dado que mente."""

    def test_todo_par_assimetrico_esta_declarado(self) -> None:
        acusados = pares_com_metade_ligada()
        sem_declaracao = {
            flag: par for flag, par in acusados.items() if flag not in _PAR_ACEITO
        }
        assert not sem_declaracao, (
            "PAR COM METADE LIGADA — o produto LÊ um estado que nenhum caminho de "
            "produção consegue escrever:\n\n"
            + "\n\n".join(par.descreva() for par in sem_declaracao.values())
            + "\n\nOU a metade que falta ganha chamador em produção, OU as leituras "
            "saem junto com a flag. Declarar em `_PAR_ACEITO` é a terceira saída, e "
            "ela exige razão datada com o endereço de onde a metade se perdeu — "
            "não é onde se guarda dívida por preguiça de decidir."
        )

    def test_nenhuma_declaracao_ficou_obsoleta(self) -> None:
        """Registro que não se limpa vira paisagem.

        É esta metade que avisa quem coordena — sozinha, sem ninguém lembrar de
        conferir — se alguma frente religar a suspensão do vpad: o par volta a
        ser simétrico, a entrada deixa de descrever a árvore, e o portão cobra
        o apagamento dela. O irmão já fez isso uma vez, com
        `forbidden_reintroductions` (13/08/2026).
        """
        acusados = pares_com_metade_ligada()
        obsoletas = sorted(flag for flag in _PAR_ACEITO if flag not in acusados)
        assert not obsoletas, (
            f"declaração obsoleta em `_PAR_ACEITO`: {obsoletas}.\n"
            "O par voltou a ter as duas metades ligadas (ou parou de ser lido em "
            "produção). APAGUE a entrada — e, se foi a suspensão do vpad que "
            "voltou, avise a Onda 2 · Início e a Onda 5 · Emulação: as duas "
            "esperam esta resposta para escrever a frase da tela."
        )

    def test_as_razoes_tem_data_e_endereco(self) -> None:
        for flag, razao in _PAR_ACEITO.items():
            assert len(razao) > _RAZAO_MINIMA, (
                f"a razão de {flag!r} tem {len(razao)} caracteres e não diz onde a "
                "metade se perdeu. ESCREVA o endereço (arquivo:linha) e o que "
                "fecharia o par. Razão curta é isenção fingindo ser decisão."
            )
            assert _DATA.search(razao), (
                f"a razão de {flag!r} não tem data. ESCREVA a data da medição "
                "(DD/MM/AAAA): razão sem idade vira paisagem."
            )


# ===========================================================================
# O portão apontado para si mesmo
# ===========================================================================

_PLANTIO = "daemon/subsystems/plantio_da_mordida.py"

_ARMADOR_SEM_CHAMADOR = '''"""Plantio da mordida — este módulo só existe dentro de um tmp."""


def armar_o_plantio(daemon):
    """Cita `desarmar_o_plantio(daemon)` na prosa DE PROPÓSITO (armadilha 1)."""
    daemon._plantio_da_mordida = True


def desarmar_o_plantio(daemon):
    daemon._plantio_da_mordida = False


def plantio_armado(daemon):
    return bool(getattr(daemon, "_plantio_da_mordida", False))


def ciclo_do_plantio(daemon):
    """A prosa aqui diz `armar_o_plantio(daemon)`, e prosa não é chamador."""
    desarmar_o_plantio(daemon)


__all__ = ["armar_o_plantio", "ciclo_do_plantio", "desarmar_o_plantio", "plantio_armado"]
'''

_ARMADOR_COM_CHAMADOR = _ARMADOR_SEM_CHAMADOR.replace(
    "    desarmar_o_plantio(daemon)",
    "    desarmar_o_plantio(daemon)\n    armar_o_plantio(daemon)",
)


def _copia_de_src(destino: Path) -> Path:
    """Uma cópia de ``src/`` onde se fabrica defeito sem sujar a árvore viva.

    Mutilar a árvore viva contamina a medição de quem estiver trabalhando ao
    lado — e desde 25/08/2026 isso tem cicatriz própria (R5 de
    COMO-REGER-AGENTES: a mordida é destrutiva enquanto dura).
    """
    copia = destino / "src" / "hefesto_dualsense4unix"
    copia.parent.mkdir(parents=True, exist_ok=True)
    shutil.copytree(_SRC, copia, ignore=shutil.ignore_patterns("__pycache__", "*.pyc"))
    return copia


class TestOPortaoMorde:
    """Um portão que nunca reprovou é decoração com nome de portão."""

    def test_a_regua_ve_o_par_de_hoje(self) -> None:
        """A régua conferida contra resposta JÁ CONHECIDA (armadilha A5).

        Se a varredura quebrasse, devolveria vazio e o portão ficaria verde para
        sempre sem medir nada. O par de hoje é a testemunha, e ela é
        auto-renovável: se alguém religar a suspensão, este caso e o
        `test_nenhuma_declaracao_ficou_obsoleta` reprovam JUNTOS, dizendo a
        mesma coisa por dois caminhos.
        """
        acusados = pares_com_metade_ligada()
        assert "_steam_input_vpad_suspenso" in acusados, (
            "a régua deixou de ver o par que a sprint mediu. OU a suspensão do vpad "
            "ganhou chamador em produção (então apague a entrada de `_PAR_ACEITO` e "
            "avise as Ondas 2 e 5), OU a varredura quebrou."
        )
        par = acusados["_steam_input_vpad_suspenso"]
        assert par.metade_morta == "True", (
            "a metade morta deste par é a que ARMA: `suspend_vpads_for_steam_input`. "
            f"A régua disse {par.metade_morta}."
        )
        assert par.armadores == {"suspend_vpads_for_steam_input": False}, (
            f"os armadores medidos mudaram: {par.armadores}"
        )
        assert par.desarmadores.get("resume_vpads_after_steam_input") is True, (
            "a régua não vê o chamador direto de `resume_vpads_after_steam_input` "
            "(gamepad.py:526) — sem isso ela acusaria as duas metades e o portão "
            "estaria medindo ausência, não assimetria."
        )

    def test_a_lista_de_leituras_atravessa_o_acessor(self) -> None:
        """O endereço é o que roteia o conserto, e ele estava faltando.

        A flag ``_steam_input_vpad_suspenso`` é tocada DIRETO em dois lugares, e
        os leitores que decidem comportamento chamam ``steam_input_vpad_suspenso``
        — o acessor que a devolve. Medindo só o toque direto, o portão acusava o
        par e apontava dois endereços quando o defeito tinha cinco: a razão de
        calada em ``lifecycle.py`` e o ramo de modo em ``hotkey.py`` ficavam
        invisíveis para quem lesse a reprovação.
        """
        par = pares_com_metade_ligada()["_steam_input_vpad_suspenso"]
        # O NÚMERO ENVELHECEU E NINGUÉM VIU — corrigido em 31/08/2026.
        # Estava `hotkey.py:261`, e a leitura pelo acessor mora na **285**
        # (`if steam_input_excecao_ativa(daemon) or steam_input_vpad_suspenso(daemon)`);
        # a 261 virou linha de DOCSTRING quando o arquivo cresceu. O portão
        # sempre apontou a 285 — quem estava errado era esta linha.
        #
        # É a classe que o `validar-citacoes-de-linha.py` passou a cobrir hoje,
        # e ele NÃO alcança aqui: ele varre `docs/` e as planilhas de
        # `docs/data/`, não número cravado em teste.
        #
        # E O NÚMERO PAROU DE SER CRAVADO — 01/09/2026, na terceira vez que ele
        # envelheceu. A frase acima dizia "enquanto um teste citar
        # `arquivo:linha` à mão, ele envelhece calado"; ele envelheceu DUAS
        # vezes na mesma sessão, porque duas curas em `lifecycle.py` empurraram
        # a linha 12 e depois mais 9. A cura é a que a casa já usa em toda
        # parte: **derivar**. Procura-se a CHAMADA, e o número sai dela.
        #
        # A MORDIDA CONTINUA INTEIRA: se o portão parar de nomear o sítio, a
        # asserção reprova igual — o que deixou de existir é a manutenção de um
        # número que nada tinha a ver com o que o caso mede.
        for arquivo, chamada in (
            ("daemon/lifecycle.py", "if steam_input_vpad_suspenso(self):"),
            ("daemon/subsystems/hotkey.py",
             "steam_input_excecao_ativa(daemon) or steam_input_vpad_suspenso(daemon)"),
        ):
            fonte = (_RAIZ / "src" / "hefesto_dualsense4unix" / arquivo).read_text(
                encoding="utf-8").split("\n")
            numeros = [i for i, linha in enumerate(fonte, 1) if chamada in linha]
            assert len(numeros) == 1, (
                f"achei {len(numeros)} linhas com {chamada!r} em {arquivo} — a "
                f"régua precisa de UMA para saber qual endereço cobrar.")
            endereco = f"{arquivo}:{numeros[0]}"
            assert any(onde.startswith(endereco) for onde in par.leituras), (
                f"o portão não nomeia {endereco}, que LÊ a flag pelo acessor. "
                f"Ele listou: {par.leituras}"
            )
        assert any("(via " in onde for onde in par.leituras), (
            "nenhuma leitura foi marcada como indireta — o salto pelo acessor "
            "morreu e o portão voltou a medir só o toque direto"
        )

    def test_a_regua_nao_acusa_os_pares_simetricos(self) -> None:
        """Portão que grita dezessete vezes é desligado na primeira semana.

        MEDIDO em 25/08/2026: 17 flags de `daemon/` têm escritor dos dois lados.
        Se a acusação crescer sem `_PAR_ACEITO` crescer junto, é a régua
        quebrando — não a árvore.
        """
        acusados = pares_com_metade_ligada()
        assert len(acusados) <= 3, (
            f"a régua acusou {len(acusados)} pares: {sorted(acusados)}. Em "
            "25/08/2026 era UM, entre 17 pares completos. Confira o descarte de "
            "docstring/`__all__` antes de acreditar na acusação."
        )
        for indesejado in ("_native_mode", "gamepad_emulation_enabled", "_paused"):
            assert indesejado not in acusados, (
                f"a régua acusou `{indesejado}`, que tem as duas metades fiadas em "
                "produção — o detector de chamador quebrou"
            )

    def test_a_regua_ve_um_par_novo_plantado(self, tmp_path: Path) -> None:
        copia = _copia_de_src(tmp_path)
        (copia / _PLANTIO).write_text(_ARMADOR_SEM_CHAMADOR, encoding="utf-8")
        acusados = pares_com_metade_ligada(copia)
        assert "_plantio_da_mordida" in acusados, (
            "a régua não viu um par plantado com o armador sem chamador — ela "
            f"acusou {sorted(acusados)}"
        )
        assert acusados["_plantio_da_mordida"].metade_morta == "True"

    def test_a_regua_sabe_recusar(self, tmp_path: Path) -> None:
        """Régua que só sabe passar não é régua (armadilha A2).

        Mesmo plantio, com UMA linha a mais: o armador ganha chamador. O par
        fica simétrico e a acusação some — é o caminho de recusa exercido.
        """
        copia = _copia_de_src(tmp_path)
        (copia / _PLANTIO).write_text(_ARMADOR_COM_CHAMADOR, encoding="utf-8")
        acusados = pares_com_metade_ligada(copia)
        assert "_plantio_da_mordida" not in acusados, (
            "a régua acusou um par cujas DUAS metades têm chamador em produção — "
            "ela não sabe recusar, e acusaria a árvore inteira"
        )

    def test_a_regua_nao_confunde_prosa_com_chamador(self, tmp_path: Path) -> None:
        """As duas armadilhas do cabeçalho, plantadas.

        O plantio cita `armar_o_plantio(daemon)` dentro de uma docstring e
        repete o nome em `__all__`. Se qualquer um dos dois contasse como
        chamador, o caso acima ficaria verde com o defeito na frente dele — que
        é exatamente o que aconteceu na primeira medição desta varredura, em
        25/08/2026.
        """
        assert "armar_o_plantio(daemon)" in _ARMADOR_SEM_CHAMADOR, (
            "o plantio perdeu a citação em docstring e parou de exercer a armadilha 1"
        )
        assert '__all__ = ["armar_o_plantio"' in _ARMADOR_SEM_CHAMADOR, (
            "o plantio perdeu o `__all__` e parou de exercer a armadilha 2"
        )
        copia = _copia_de_src(tmp_path)
        (copia / _PLANTIO).write_text(_ARMADOR_SEM_CHAMADOR, encoding="utf-8")
        assert "_plantio_da_mordida" in pares_com_metade_ligada(copia)

    def test_a_regua_ignora_flag_que_ninguem_le(self, tmp_path: Path) -> None:
        """O preço declarado no cabeçalho, exercido: sem leitor, sem acusação."""
        copia = _copia_de_src(tmp_path)
        muda = _ARMADOR_SEM_CHAMADOR.replace(
            "def plantio_armado(daemon):\n"
            '    return bool(getattr(daemon, "_plantio_da_mordida", False))',
            "def plantio_armado(daemon):\n    return False",
        )
        assert "getattr(daemon" not in muda, "o plantio mudo ainda lê a flag"
        (copia / _PLANTIO).write_text(muda, encoding="utf-8")
        assert "_plantio_da_mordida" not in pares_com_metade_ligada(copia)

    def test_uma_frase_de_tela_nao_desliga_o_portao(self, tmp_path: Path) -> None:
        """A TERCEIRA armadilha, achada em 25/08/2026 — e a que quase passou.

        As duas do teste acima são docstring e ``__all__``, e a varredura já as
        descarta. **Esta é outra: uma FRASE COMUM.** Enquanto a régua fazia
        ``findall`` de toda palavra de toda string, bastava um texto de tela, uma
        mensagem de erro ou um comentário-em-string citar o nome do símbolo para
        a varredura declarar "tem chamador" e se calar.

        Foi um agente que a achou, e do pior jeito possível: **ele silenciou este
        portão sem querer**, escrevendo o nome do símbolo numa mensagem para o
        usuário. A régua não reprovou, e não reprovar era o defeito.

        A cura é uma linha — ``no.value.isidentifier()``. Despacho por string é
        sempre o nome INTEIRO e sozinho (``getattr(x, "meu_metodo")``); prosa
        nunca é.

        **A RECEITA DE REPRODUÇÃO, corrigida em 25/08/2026 pelo conferente da
        leva — e a correção importa.** A primeira versão desta docstring dizia
        *"arranque o ``isidentifier()`` e ele reprova"*. **Não reprova**, e quem
        escreveu não conferiu: a cura são DUAS linhas no mesmo trecho, e sozinho
        o ``isidentifier()`` não faz nada, porque a linha de baixo guarda o
        literal INTEIRO (``palavras.add(no.value)``) — e a frase inteira nunca
        casa com o nome do símbolo.

        **O defeito volta com a linha de baixo**, que era
        ``palavras.update(re.findall(r"[A-Za-z_][A-Za-z0-9_]*", no.value))``:
        é o ``findall`` que quebra a frase em palavras soltas e faz uma delas
        casar. Para reproduzir, troque as DUAS.

        Fica escrito porque receita de mordida que não morde é pior que receita
        nenhuma: ela dá a quem vier depois a confiança de que a régua está
        protegida quando não está.
        """
        frase = (
            "Não consegui aplicar: o armar_o_plantio do daemon recusou o pedido."
        )
        assert not frase.isidentifier(), "a frase de prova deixou de ser prosa"
        assert "armar_o_plantio" in frase, (
            "a frase de prova parou de citar o símbolo e não exerce mais a armadilha"
        )
        com_frase = _ARMADOR_SEM_CHAMADOR + f'\n\nAVISO_DA_TELA = {frase!r}\n'
        copia = _copia_de_src(tmp_path)
        (copia / _PLANTIO).write_text(com_frase, encoding="utf-8")
        assert "_plantio_da_mordida" in pares_com_metade_ligada(copia), (
            "uma frase de tela citando o símbolo DESLIGOU o portão — a régua "
            "voltou a contar prosa como despacho, e ela para de medir "
            "exatamente quando alguém escreve uma mensagem boa"
        )


# ===========================================================================
# A SEGUNDA RÉGUA DESTE ARQUIVO — o endereço que envelheceu sozinho
# ===========================================================================
#
# LEVA-4-B (26/08/2026). Esta casa cita endereço de linha em comentário e em
# docstring o tempo todo, e o endereço é o que ROTEIA o conserto: quem lê
# "`_handle_daemon_status` (`ipc_handlers.py:1971`)" abre a linha 1971 e
# acredita no que encontra lá.
#
# Só que endereço de linha se move sozinho. Os 164 commits da madrugada de
# 25/08 deslocaram `daemon/ipc_handlers.py` inteiro, e **nada reprovou**: o
# `scripts/validar-citacoes-de-linha.py` varre `docs/`, não `src/` — rodado no
# HEAD desta árvore, ele diz *"OK: 123 citações em 13 documentos"* com dez
# arquivos de código apontando para o vazio.
#
# O preço não é estético. Um endereço morto manda a próxima pessoa ler uma
# linha que hoje fala de outro assunto, e ela conclui o que aquela linha diz —
# foi assim que a razão do `stop_autoswitch` acabou prometendo que "a thread é
# derrubada pelo fim do processo" apontando para um `shutdown` que já a
# derrubava em linha.
#
# O QUE ESTA RÉGUA NÃO ALCANÇA, e é de propósito:
#   - endereço que caiu numa linha PLAUSÍVEL sem símbolo ao lado passa. Sem
#     âncora nomeada não há como computar o número real, e inventar um seria
#     medição falsa. O que ela pega é o que dá para PROVAR;
#   - alvo fora do repositório (`pydualsense.py`) é ignorado: não é nosso.

import tokenize

#: `arquivo.py:NNN` ou `arquivo.py:NNN-MMM`, em qualquer prosa.
_CITACAO = re.compile(r"(?P<alvo>[A-Za-z0-9_./]+\.py):(?P<ini>\d+)(?:-(?P<fim>\d+))?")

#: Símbolo em crase (simples ou dupla) na vizinhança da citação.
_EM_CRASE = re.compile(r"``?([^`\n]+?)``?")

#: A janela de prosa em que a âncora é procurada: a linha da citação e as duas
#: acima. Medido em 26/08/2026: três linhas cobrem toda citação desta árvore
#: cujo símbolo veio antes da quebra; quatro só somariam falso positivo.
_JANELA = 3

#: CITAÇÕES MEDIDAS COMO ENVELHECIDAS EM 26/08/2026 QUE ESTA FRENTE NÃO PODE
#: CONSERTAR — o arquivo citante é de outra posse (regra R-A da leva: a frente
#: escreve nos arquivos DELA e relata o resto). Não é lista de tolerância: o
#: `test_a_lista_de_pendentes_nao_vira_paisagem` exige que cada uma continue
#: QUEBRADA, então consertar uma obriga a tirá-la daqui.
#:
#: Duas famílias, e a diferença importa para quem for fechar:
#:  * **endereço deslocado** — o alvo existe e mudou de linha. Conserto: medir
#:    com `grep -n` e reescrever o número;
#:  * **endereço histórico** — o código citado FOI REMOVIDO pela própria cura
#:    que o comentário registra (as quatro listas de bases em
#:    `utils/repo_files.py`, mortas pela BG-BASES-01). Não há número novo para
#:    escrever: o conserto é a prosa dizer que o endereço é de antes da cura.
_CITACOES_PENDENTES: frozenset[str] = frozenset({
    "app/actions/config/moldura.py::test_config_a_janela_na_tela.py:262",
    "app/actions/config/secao_janela.py::desktop_notifications.py:33",
    "app/actions/footer_actions.py::home_actions.py:1050-1054",
    "app/actions/home_actions.py::daemon/lifecycle.py:84",
    "app/actions/trigger_specs.py::app/widgets/segmented_selector.py:168-180",
    "app/actions/trigger_specs.py::profiles/schema.py:161",
    "cli/cmd_test.py::app/ipc_bridge.py:341",
    "core/led_control.py::core/backend_pydualsense.py:2801",
    "daemon/ipc_handlers.py::app/actions/lightbar_actions.py:828",
    "daemon/ipc_handlers.py::core/backend_pydualsense.py:1222",
    "daemon/ipc_handlers.py::core/backend_pydualsense.py:1335",
    "daemon/ipc_handlers.py::profiles/manager.py:384-387",
    "daemon/subsystems/external_mask.py::identity.py:858",
    "daemon/subsystems/hotkey.py::daemon/protocols.py:180",
    "daemon/subsystems/hotkey.py::profiles/manager.py:384-387",
    # ONDA5-06-01 (06/09/2026) — AS QUATRO QUE O BOTÃO PS DESLOCOU, e as quatro
    # são de arquivo que a sprint declara em `nao_toca:`. A âncora de cada uma
    # CONTINUA EXISTINDO; só o número mudou, porque o PS ganhou dono em
    # `profiles/manager.py` (`_empurrar_o_ps`, `_canal_do_ps`, o campo
    # `ps_action_sink`) e em `daemon/subsystems/hotkey.py` (`definir_acao_do_ps`,
    # `_digitar_o_ps`, `_a_metade_da_maquina`).
    #
    # O NÚMERO CERTO JÁ ESTÁ MEDIDO — quem for dono do arquivo troca e apaga a
    # linha daqui (o `test_a_lista_de_pendentes_nao_vira_paisagem` cobra):
    #   a06_navegacao.py:626  `core/acoes_de_botao.py:285`  -> `:338` (`resolver`)
    #   a06_navegacao.py:1161 `profiles/manager.py:570`     -> `:617`
    #   a06_navegacao.py:1175 `profiles/manager.py:614`     -> `:673`
    #   profiles/schema.py:997 `daemon/subsystems/hotkey.py:1004` -> `:1234`
    #
    # As outras QUATRO que a mesma sprint deslocou não estão aqui porque foram
    # CORRIGIDAS no lugar (`core/rumble.py`, `a02_controles.py` e duas em
    # `a08_conexoes.py`): fora do `nao_toca:`, o número se reescreve.
    "interface/pacotes/a06_navegacao.py::core/acoes_de_botao.py:285",
    "interface/pacotes/a06_navegacao.py::manager.py:614",
    "interface/pacotes/a06_navegacao.py::profiles/manager.py:570",
    "profiles/schema.py::daemon/subsystems/hotkey.py:1004",
    # ONDA3-MOTOR-01 (06/09/2026) — AS SEIS QUE A CURA DO `— Nada —` E DA
    # HERANÇA DE `key_bindings` DESLOCOU. O deslocamento é de **+22 linhas** em
    # `profiles/manager.py` e em `integrations/uinput_mouse.py`, medido linha a
    # linha com `git show HEAD:<arquivo> | sed -n`, e as seis moram em arquivo
    # que a sprint declara em `nao_toca:` ou que é de outra posse. A âncora de
    # cada uma CONTINUA EXISTINDO — só o número mudou.
    #
    # O NÚMERO CERTO JÁ ESTÁ MEDIDO — quem for dono do arquivo troca e apaga a
    # linha daqui (o `test_a_lista_de_pendentes_nao_vira_paisagem` cobra):
    #   rumble_actions.py:417  `profiles/manager.py:1556-1567` -> `:1578-1589`
    #   aba06.py:1714          `uinput_mouse.py:486`  -> `:508` (`emit_touchpad_move`)
    #   a06_navegacao.py:2205  `uinput_mouse.py:500`  -> `:508` (`emit_touchpad_move`)
    #   a06_navegacao.py:2224  `uinput_mouse.py:466`  -> `:488` (`_emit_scroll`)
    #   a06_navegacao.py:2766  `uinput_mouse.py:446`  -> `:468`
    #   a08_conexoes.py:3868   `profiles/manager.py:2106` -> `:2128`
    #
    # As DUAS que a mesma cura deslocou dentro da minha posse não estão aqui
    # porque foram corrigidas no lugar (`core/acoes_de_botao.py`, as citações de
    # `profiles/manager.py:1856`->`:1878` e `uinput_mouse.py:355`->`:377`).
    "app/actions/rumble_actions.py::profiles/manager.py:1556-1567",
    "interface/aba06.py::integrations/uinput_mouse.py:486",
    "interface/pacotes/a06_navegacao.py::integrations/uinput_mouse.py:466",
    "interface/pacotes/a06_navegacao.py::integrations/uinput_mouse.py:500",
    "interface/pacotes/a06_navegacao.py::uinput_mouse.py:446",
    "interface/pacotes/a08_conexoes.py::profiles/manager.py:2106",
    # ONDA5-P-01 (06/09/2026) — AS TRÊS QUE A QUARTA PORTA DESLOCOU. O piloto
    # ganhou o seletor do dono, o `input` do "ao vivo" e o despacho do gesto
    # vivo; o deslocamento em `interface/hefesto_vivo.py` é de **+163 linhas**
    # antes do `_fita` e de **+297** antes do `_recusou_dizendo`. As três moram
    # em `interface/pacotes/`, que a sprint declara em `nao_toca:`. A âncora de
    # cada uma CONTINUA EXISTINDO — só o número mudou.
    #
    # O NÚMERO CERTO JÁ ESTÁ MEDIDO — quem for dono do arquivo troca e apaga a
    # linha daqui (o `test_a_lista_de_pendentes_nao_vira_paisagem` cobra):
    #   a03_gatilhos.py:1472  `hefesto_vivo.py:1515` -> `:1678` (`_fita`)
    #   a06_navegacao.py:2710 `hefesto_vivo.py:2288` -> `:2585` (`_recusou_dizendo`)
    #   a10_perfis.py:1284    `hefesto_vivo.py:2288` -> `:2585` (`_recusou_dizendo`)
    #
    # As TRÊS que a mesma cura deslocou FORA do `nao_toca:` não estão aqui
    # porque foram corrigidas no lugar (`interface/aba05.py:1601`, `:1609` e
    # `:1616` — as três citações do `data-controle` daquela aba, que já
    # apontavam para linhas erradas antes desta leva e só agora caíram numa que
    # a régua consegue ancorar).
    "interface/pacotes/a03_gatilhos.py::hefesto_vivo.py:1515",
    "interface/pacotes/a06_navegacao.py::hefesto_vivo.py:2288",
    "interface/pacotes/a10_perfis.py::hefesto_vivo.py:2288",
    "profiles/loader.py::schema.py:52",
    "utils/repo_files.py::cli/cmd_doctor.py:23",
    "utils/repo_files.py::emulation_actions.py:1200",
    "utils/repo_files.py::emulation_actions.py:1763",
})


@dataclass(frozen=True)
class CitacaoDeLinha:
    """Uma citação `arquivo.py:NNN` achada em prosa de código."""

    citante: str
    """Caminho do arquivo que cita, relativo a `src/hefesto_dualsense4unix`."""
    bruta: str
    """A citação como está escrita — `alvo.py:NNN` ou `alvo.py:NNN-MMM`."""
    linha_da_citacao: int
    alvo: Path
    ini: int
    fim: int

    @property
    def chave(self) -> str:
        return f"{self.citante}::{self.bruta}"


def _resolver_alvo(alvo: str, raiz: Path) -> Path | None:
    """O `.py` citado, dentro do repositório — ou `None` se não for nosso.

    `raiz` primeiro, e não o repositório: é o que faz o dublê medir a CÓPIA de
    `src/` em vez da árvore viva. Sem isso a régua se autoconfirmaria.
    """
    for candidato in (raiz / alvo, _RAIZ / alvo, _RAIZ / "src" / alvo):
        if candidato.is_file():
            return candidato
    if Path(alvo).name != alvo:
        return None
    achados = [p for p in raiz.rglob(alvo)] or [
        p for base in ("src", "tests", "scripts") for p in (_RAIZ / base).rglob(alvo)
    ]
    return achados[0] if len(achados) == 1 else None


def _prosa_de(modulo: Path) -> dict[int, str]:
    """As linhas do módulo que são COMENTÁRIO ou STRING, pela numeração real.

    `tokenize` e não regex: é o que separa `# ver foo.py:12` de um `foo.py:12`
    que por acaso aparecesse em código. Linha multi-token vira uma entrada só.
    """
    linhas: dict[int, str] = {}
    with modulo.open("rb") as fh:
        try:
            for tok in tokenize.tokenize(fh.readline):
                if tok.type not in (tokenize.COMMENT, tokenize.STRING):
                    continue
                for offset, texto in enumerate(tok.string.splitlines()):
                    linhas.setdefault(tok.start[0] + offset, "")
                    linhas[tok.start[0] + offset] += texto
        except (tokenize.TokenError, SyntaxError):  # módulo quebrado é de outro portão
            return {}
    return linhas


def citacoes_de_linha(raiz: Path | None = None) -> list[CitacaoDeLinha]:
    """Toda citação `arquivo.py:NNN` em comentário/docstring de `src/`."""
    raiz = raiz or _SRC
    achadas: list[CitacaoDeLinha] = []
    for modulo in _modulos(raiz):
        prosa = _prosa_de(modulo)
        for numero, texto in sorted(prosa.items()):
            for m in _CITACAO.finditer(texto):
                alvo = _resolver_alvo(m.group("alvo"), raiz)
                if alvo is None:
                    continue
                ini = int(m.group("ini"))
                achadas.append(
                    CitacaoDeLinha(
                        citante=str(modulo.relative_to(raiz)),
                        bruta=m.group(0),
                        linha_da_citacao=numero,
                        alvo=alvo,
                        ini=ini,
                        fim=int(m.group("fim")) if m.group("fim") else ini,
                    )
                )
    return achadas


def _ancoras_candidatas(modulo: Path, numero: int) -> list[str]:
    """Identificadores em crase na janela de prosa em volta da citação."""
    linhas = modulo.read_text(encoding="utf-8").splitlines()
    janela = " ".join(linhas[max(0, numero - _JANELA) : numero])
    nomes: list[str] = []
    for bruto in _EM_CRASE.findall(janela):
        pedaco = bruto.strip().split("/")[-1]
        if pedaco.endswith(".py") or ".py:" in pedaco:
            continue
        pedaco = pedaco.split(".")[-1]
        if re.fullmatch(r"[A-Za-z_][A-Za-z0-9_]*", pedaco):
            nomes.append(pedaco)
    return nomes


def _blocos_definidos(linhas: list[str], nome: str) -> list[tuple[int, int, bool]]:
    """Todo `def`/`class` chamado `nome`: `(primeira, derradeira, aninhada)`.

    Pelo `ast`, e não pelo recuo — DUAS coisas que a contagem de colunas errava,
    as duas medidas em 03/09/2026:

    * **Onde o bloco ACABA.** O laço de recuo parava na primeira linha de
      coluna zero, e numa assinatura de várias linhas isso é o `)` do
      cabeçalho: o `from_simple_choice` (`profiles/simple_match.py:203`) virava
      *"bloco 203-206"* com corpo até a 248, e a régua reprovava quem citasse a
      linha exata do comportamento — que é o que a prosa faz o tempo todo.
    * **Se é helper LOCAL.** Método de classe também é recuado e é endereço
      legítimo; `def` dentro de outra função não é. Sete comentários citavam o
      alvo `classe` do piloto (uma string do JS em `hefesto_vivo.py`) e a régua
      os mandava para um `def classe` enterrado dentro de outro método, 1.900
      linhas adiante — sem número que a calasse sem mentir.

    Módulo que não parseia devolve lista vazia: quem cobra sintaxe é outro
    portão, e acusar por causa dele seria acusar duas vezes o mesmo defeito.
    """
    try:
        arvore = ast.parse("\n".join(linhas))
    except SyntaxError:
        return []
    achadas: list[tuple[int, int, bool]] = []

    def anda(no: ast.AST, dentro_de_funcao: bool) -> None:
        for filho in ast.iter_child_nodes(no):
            eh_funcao = isinstance(filho, (ast.FunctionDef, ast.AsyncFunctionDef))
            eh_definicao = eh_funcao or isinstance(filho, ast.ClassDef)
            if eh_definicao and filho.name == nome:  # type: ignore[attr-defined]
                fim = getattr(filho, "end_lineno", None) or filho.lineno  # type: ignore[attr-defined]
                achadas.append((filho.lineno, fim, dentro_de_funcao))  # type: ignore[attr-defined]
            anda(filho, dentro_de_funcao or eh_funcao)

    anda(arvore, False)
    return achadas


def _definicao_unica(linhas: list[str], nome: str) -> tuple[int, int] | None:
    """`(primeira, derradeira)` do bloco de `def`/`class` chamado `nome`.

    Só `def` e `class`, e só quando há UMA. Atribuição simples fica de fora de
    propósito: `address = ...` casaria com meia árvore e a régua acusaria quem
    está certo — a pior coisa que um portão faz.

    E `def` ANINHADO DENTRO DE OUTRA FUNÇÃO também fica de fora, pela mesma
    razão. O porquê de cada exclusão, com o caso medido, está em
    `_blocos_definidos` — que é quem lê a árvore.
    """
    achadas = _blocos_definidos(linhas, nome)
    if len(achadas) != 1:
        return None
    inicio, fim, aninhada = achadas[0]
    return None if aninhada else (inicio, fim)


def _endereco_corroborado(linhas: list[str], cit: CitacaoDeLinha, nomes: list[str]) -> bool:
    """O trecho citado MOSTRA algum dos nomes da prosa em volta?

    Se mostra, o endereço confere e a régua se cala — mesmo que o `def` daquele
    nome more noutro lugar. Curado em 03/09/2026, e os dois casos que forçaram a
    cura estavam CERTOS e eram acusados:

    * `app/telas/vibracao.py:204` cita `controller_card.py:1511-1541` dizendo
      *"li o corpo"* do `motores_no_fisico` — e ele começa exatamente na 1511. A
      régua pegou da mesma frase o `pedido_de_vibracao_fresco`, que é o assunto
      do parágrafo, e mandou o endereço para 1554.
    * `interface/pacotes/a03_gatilhos.py:1947` cita `triggers_actions.py:597`
      dizendo *"é chamado ANTES de todo envio"* — 597 é a CHAMADA, e é o que a
      frase promete. A régua exigia a definição, na 342.

    A suposição que caiu: *toda citação aponta para o `def`*. Prosa cita o ponto
    de USO tanto quanto o de definição, e cita o símbolo que interessa, não o
    último que apareceu entre crases. Endereço envelhecido continua pego — a
    linha velha não tem traço do nome, que é o que a mordida planta.
    """
    trecho = "\n".join(linhas[cit.ini - 1 : cit.fim])
    return any(re.search(rf"\b{re.escape(nome)}\b", trecho) for nome in nomes)


def enderecos_envelhecidos(raiz: Path | None = None) -> dict[str, str]:
    """`{chave: queixa}` de toda citação que NÃO confere. Vazio é o esperado."""
    raiz = raiz or _SRC
    queixas: dict[str, str] = {}
    for cit in citacoes_de_linha(raiz):
        linhas = cit.alvo.read_text(encoding="utf-8").splitlines()
        onde = f"{cit.citante}:{cit.linha_da_citacao}"
        if cit.ini > len(linhas):
            queixas[cit.chave] = (
                f"{onde} cita a linha {cit.ini} de {cit.bruta.split(':')[0]}, "
                f"que tem {len(linhas)} linhas"
            )
            continue
        if not linhas[cit.ini - 1].strip():
            queixas[cit.chave] = (
                f"{onde} cita a linha {cit.ini}, que está EM BRANCO — "
                "âncora em linha vazia não ancora nada"
            )
            continue
        candidatas = _ancoras_candidatas(raiz / cit.citante, cit.linha_da_citacao)
        if _endereco_corroborado(linhas, cit, candidatas):
            continue
        for nome in candidatas:
            bloco = _definicao_unica(linhas, nome)
            if bloco is None:
                continue
            if cit.ini > bloco[1] or cit.fim < bloco[0]:
                queixas[cit.chave] = (
                    f"{onde} cita a linha {cit.ini}, mas a âncora `{nome}` "
                    f"está na linha {bloco[0]} (bloco {bloco[0]}-{bloco[1]})"
                )
            break
    return queixas


#: O alvo do dublê: a âncora fica na linha 4 e a linha 2 é código VIVO, não
#: espaço em branco. As duas escolhas são deliberadas — um símbolo na linha 1
#: engoliria o erro (a 2 estaria dentro do bloco dele) e uma linha 2 vazia faria
#: a queixa sair pela régua de linha em branco, sem exercer a de âncora.
_ALVO_PLANTADO = (
    "VALOR = 0\nOUTRO = 1\n\ndef ancora_plantada():\n    return 1\n"
)


def _citante_plantado(linha: int) -> str:
    """Um comentário que promete `ancora_plantada` na linha pedida."""
    return (
        f"# `ancora_plantada` mora em `utils/_alvo_da_mordida.py:{linha}`.\n"
        "VALOR = 1\n"
    )


class TestTodaCitacaoDeLinhaConfere:
    def test_toda_citacao_de_linha_em_comentario_de_codigo_confere(self) -> None:
        """O endereço escrito em `src/` tem de apontar para o que ele promete.

        A MORDIDA: envelheça um endereço de propósito — some 1 à linha citada
        em qualquer comentário que nomeie o símbolo ao lado — e este teste
        reprova nomeando OS DOIS NÚMEROS, o citado e o real.
        """
        queixas = enderecos_envelhecidos()
        vivas = {k: v for k, v in queixas.items() if k not in _CITACOES_PENDENTES}
        assert not vivas, (
            f"{len(vivas)} endereço(s) de linha em `src/` apontam para outro "
            "lugar hoje:\n"
            + "\n".join(f"  - {v}" for v in sorted(vivas.values()))
            + "\nMeça com `grep -n` e reescreva o número. Se o arquivo citante "
            "for de outra posse, ponha a chave em `_CITACOES_PENDENTES` com o "
            "motivo — nunca afrouxe a régua."
        )

    def test_a_lista_de_pendentes_nao_vira_paisagem(self) -> None:
        """Pendência consertada TEM de sair da lista — senão ela vira ruído.

        É a metade que faz a lista se limpar sozinha: quem consertar um dos
        endereços de outra posse descobre aqui que precisa apagar a linha.
        """
        queixas = enderecos_envelhecidos()
        curadas = sorted(_CITACOES_PENDENTES - set(queixas))
        assert not curadas, (
            f"{len(curadas)} citação(ões) declarada(s) como pendente(s) já "
            "conferem — apague-as de `_CITACOES_PENDENTES`:\n"
            + "\n".join(f"  - {c}" for c in curadas)
        )

    def test_a_regua_sabe_reprovar(self, tmp_path: Path) -> None:
        """Régua que só sabe passar não é régua (armadilha A2).

        Planta, numa cópia de `src/`, um comentário com o endereço ERRADO de um
        símbolo que existe — e exige que a queixa nomeie os dois números.
        """
        copia = _copia_de_src(tmp_path)
        (copia / "utils" / "_alvo_da_mordida.py").write_text(
            _ALVO_PLANTADO, encoding="utf-8"
        )
        (copia / "utils" / "_citante_da_mordida.py").write_text(
            _citante_plantado(2), encoding="utf-8"
        )
        queixas = enderecos_envelhecidos(copia)
        chave = "utils/_citante_da_mordida.py::utils/_alvo_da_mordida.py:2"
        assert chave in queixas, (
            "a régua não viu um endereço plantado fora do símbolo que ele "
            f"promete. Ela achou: {sorted(queixas)}"
        )
        queixa = queixas[chave]
        assert "linha 2" in queixa and "linha 4" in queixa, (
            f"a queixa não nomeia OS DOIS números: {queixa!r}"
        )

    def test_a_regua_nao_acusa_o_endereco_certo(self, tmp_path: Path) -> None:
        """O outro lado do dublê: o MESMO plantio, com o número certo, passa.

        Sem este caso a régua poderia estar acusando tudo — e um portão que
        acusa sempre é desligado na primeira semana, como o irmão já mediu.
        """
        copia = _copia_de_src(tmp_path)
        (copia / "utils" / "_alvo_da_mordida.py").write_text(
            _ALVO_PLANTADO, encoding="utf-8"
        )
        (copia / "utils" / "_citante_da_mordida.py").write_text(
            _citante_plantado(4), encoding="utf-8"
        )
        plantadas = [k for k in enderecos_envelhecidos(copia) if "_da_mordida" in k]
        assert not plantadas, f"a régua acusou um endereço CERTO: {plantadas}"

    def test_a_regua_ignora_alvo_que_nao_e_desta_casa(self, tmp_path: Path) -> None:
        """`pydualsense.py:610` é biblioteca de terceiro — não temos as linhas.

        Acusar um arquivo que não está no repositório seria gritar com quem
        está certo: o número pode estar perfeito para a versão instalada.
        """
        copia = _copia_de_src(tmp_path)
        (copia / "utils" / "_citante_da_mordida.py").write_text(
            "# ver `biblioteca_que_nao_existe_aqui.py:99`\nVALOR = 1\n",
            encoding="utf-8",
        )
        assert not [
            k for k in enderecos_envelhecidos(copia) if "_da_mordida" in k
        ]
