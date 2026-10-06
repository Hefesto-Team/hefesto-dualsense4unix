"""O PORTÃO DO PAR COM METADE LIGADA — ``VPAD-SUSPENSO-MORTO-01``, E3.

O DEFEITO, MEDIDO: **existe quem retoma e não existe quem suspende.** A flag
``daemon._steam_input_vpad_suspenso`` só pode andar para ``False`` desde
``d8022ea`` (09/08/2026), e o produto continua LENDO os dois valores dela. Uma
das duas respostas é impossível, e nada no produto diz isso: **é pior que
ausência de dado, é dado que mente sempre para o mesmo lado.**

O RAIO DO ESTRAGO — cinco leitores em produção, e DOIS estão na tela
--------------------------------------------------------------------
Censo de 25/08/2026. Nenhum destes cinco pode responder ``True``:

1. ``daemon/lifecycle.py:1272`` — ``CALADA_VPAD_SUSPENSO`` é a razão de calada
   do gate do desktop, e ela **nunca é devolvida**;
2. ``daemon/subsystems/hotkey.py:153`` — ramo de modo, num ``or`` cujo outro
   lado (``steam_input_excecao_ativa``) carrega a decisão sozinho;
3. ``daemon/ipc_handlers.py:1680`` — publica ``vpad_suspenso`` no ``state_full``
   sempre ``False``, e a docstring ao lado documenta um contrato de DOIS estados
   dos quais um é inalcançável;
4. ``app/actions/home_actions.py:695`` (**Onda 2 · Início**) — a frase da
   ponte exige ``excecao_ativa and vpad_suspenso``: a aba **nunca** consegue
   dizer "pelo Steam Input";
5. ``app/actions/emulation_actions.py:300`` (**Onda 5 · Emulação**) — a frase
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
   com o defeito na frente do usuário.
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
  avisa, sozinha, se alguma frente RELIGAR a suspensão.

Os dois lados também são exercitados por dublê em ``TestOPortaoMorde``, sobre
uma cópia de ``src/`` — régua que só sabe passar não é régua (armadilha A2).
"""

from __future__ import annotations

import ast
import functools
import io
import re
import shutil
from dataclasses import dataclass, field
from pathlib import Path

_RAIZ = Path(__file__).resolve().parents[2]
_SRC = _RAIZ / "src" / "hefesto_dualsense4unix"

_TERRITORIO = "daemon"


#: Vazio desde 02/10/2026: a única entrada (`_steam_input_vpad_suspenso`) saiu com
#: a suspensão do vpad, na O-CODIGO-SEM-CHAMADOR-LIGA-OU-SAI-01.
_PAR_ACEITO: dict[str, str] = {}

#: do irmão (`portao_a_casa_sabe_e_o_produto_nao_faz._confere_razoes`).
_DATA = re.compile(r"\b\d{2}/\d{2}/\d{4}\b")

_RAZAO_MINIMA = 120


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
        enderecos = "\n".join(f"        {onde}" for onde in self.leituras)
        return (
            f"{self.flag}: nenhum caminho de produção põe {self.metade_morta}.\n"
            f"    sem chamador: {sorted(nome for nome in mortos)}\n"
            f"    vivos       : {sorted(nome for nome, ok in vivos.items() if ok)}\n"
            f"    lida em ({len(self.leituras)}):\n{enderecos}"
        )


def _prosa(arvore: ast.AST) -> set[int]:
    """Os literais que NÃO são despacho: docstring de módulo/classe/função e ``__all__``."""
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


@functools.cache
def _arvore_do_texto(texto: str) -> ast.Module:
    """A AST de um texto, lida UMA vez por conteúdo — e SÓ para leitura.

    As quatro varreduras desta régua (e as mordidas, que repetem cada uma sobre
    uma cópia que difere em um arquivo) liam e parseavam os mesmos módulos. A
    chave é o texto: o arquivo mordido tem outro texto e, logo, outra árvore.
    Quem pede a árvore não a altera (todos só caminham por ela).
    """
    return ast.parse(texto)


@functools.cache
def _fatos_do_texto(
    texto: str,
) -> tuple[
    tuple[tuple[str, int, int], ...],
    tuple[tuple[str, int], ...],
    frozenset[str],
] | None:
    """Corpos de função, chamadas e palavras de um texto — só dependem do TEXTO.

    ``None`` é o módulo que não parseia. O índice de ``src/`` inteiro refazia
    esta caminhada por todos os nós a cada varredura; aqui ela é feita uma vez
    por conteúdo e o caminho do arquivo só entra na hora de montar o índice.
    """
    try:
        arvore = _arvore_do_texto(texto)
    except SyntaxError:  # pragma: no cover - árvore em movimento
        return None
    fora = _prosa(arvore)
    corpos: list[tuple[str, int, int]] = []
    chamadas: list[tuple[str, int]] = []
    palavras: set[str] = set()
    for no in ast.walk(arvore):
        if isinstance(no, (ast.FunctionDef, ast.AsyncFunctionDef)):
            corpos.append((no.name, no.lineno, no.end_lineno or no.lineno))
        elif isinstance(no, ast.Call):
            alvo = no.func
            nome = getattr(alvo, "id", None) or getattr(alvo, "attr", None)
            if isinstance(nome, str):
                chamadas.append((nome, no.lineno))
        elif (
            isinstance(no, ast.Constant)
            and isinstance(no.value, str)
            and id(no) not in fora
            and no.value.isidentifier()
        ):
            palavras.add(no.value)
    return tuple(corpos), tuple(chamadas), frozenset(palavras)


def _indexar(raiz: Path) -> _Indice:
    chamadas: dict[str, list[tuple[Path, int]]] = {}
    corpos: dict[str, list[tuple[Path, int, int]]] = {}
    palavras: set[str] = set()
    for caminho in _modulos(raiz):
        fatos = _fatos_do_texto(caminho.read_text(encoding="utf-8"))
        if fatos is None:  # pragma: no cover - árvore em movimento
            continue
        for nome, inicio, fim in fatos[0]:
            corpos.setdefault(nome, []).append((caminho, inicio, fim))
        for nome, linha in fatos[1]:
            chamadas.setdefault(nome, []).append((caminho, linha))
        palavras |= fatos[2]
    return _Indice(chamadas=chamadas, corpos=corpos, palavras=palavras)


def _tem_chamador(nome: str, indice: _Indice) -> bool:
    """Régua plana: alguém em ``src/`` chama este nome fora do próprio corpo?"""
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
    """As funções de ``src/`` que DEVOLVEM a flag."""
    nomes: set[str] = set()
    for caminho in _modulos(raiz):
        texto = caminho.read_text(encoding="utf-8")
        if flag not in texto:
            continue
        try:
            arvore = _arvore_do_texto(texto)
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
            arvore = _arvore_do_texto(texto)
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
                continue
            achados.append(f"{caminho.relative_to(raiz)}:{no.lineno} (via {nome})")
    return sorted(set(achados))


def pares_com_metade_ligada(raiz: Path | None = None) -> dict[str, Par]:
    """As flags de ``daemon/`` que o produto lê e só consegue escrever de um lado."""
    alvo = raiz or _SRC
    territorio = alvo / _TERRITORIO
    if not territorio.is_dir():  # pragma: no cover - cópia mutilada
        return {}

    escritas: dict[str, dict[bool, set[str]]] = {}
    for caminho in _modulos(territorio):
        try:
            arvore = _arvore_do_texto(caminho.read_text(encoding="utf-8"))
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
            continue
        acusados[flag] = par
    return acusados


_PLANTIO = "daemon/subsystems/plantio_da_mordida.py"


def _citante_plantado(linha: int) -> str:
    """Um comentário que promete `ancora_plantada` na linha pedida."""
    return (
        f"# `ancora_plantada` mora em `utils/_alvo_da_mordida.py:{linha}`.\n"
        "VALOR = 1\n"
    )


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
        """Registro que não se limpa vira paisagem."""
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
    """Uma cópia de ``src/`` onde se fabrica defeito sem sujar a árvore viva."""
    copia = destino / "src" / "hefesto_dualsense4unix"
    copia.parent.mkdir(parents=True, exist_ok=True)
    shutil.copytree(_SRC, copia, ignore=shutil.ignore_patterns("__pycache__", "*.pyc"))
    return copia


_LEITOR_DO_PLANTIO = '''"""Lê a flag plantada pelo acessor — só existe dentro de um tmp."""
from hefesto_dualsense4unix.daemon.plantio_da_mordida import plantio_armado


def quem_le_o_plantio(daemon):
    return 1 if plantio_armado(daemon) else 0
'''


def _plantar(destino: Path, armador: str) -> Path:
    """Uma cópia de ``src/`` com o par plantado em ``daemon/``."""
    copia = _copia_de_src(destino)
    (copia / "daemon" / "plantio_da_mordida.py").write_text(armador, encoding="utf-8")
    (copia / "daemon" / "leitor_do_plantio.py").write_text(
        _LEITOR_DO_PLANTIO, encoding="utf-8"
    )
    return copia


class TestOPortaoMorde:
    """Um portão que nunca reprovou é decoração com nome de portão."""

    def test_a_regua_ve_o_par_plantado(self, tmp_path: Path) -> None:
        """Armador sem chamador e desarmador vivo: a régua acusa, nas duas direções."""
        copia = _plantar(tmp_path, _ARMADOR_SEM_CHAMADOR)
        acusados = pares_com_metade_ligada(copia)
        assert "_plantio_da_mordida" in acusados, (
            "a régua não viu o par plantado — a varredura quebrou"
        )
        par = acusados["_plantio_da_mordida"]
        assert par.metade_morta == "True", par
        assert par.armadores == {"armar_o_plantio": False}, par.armadores
        assert par.desarmadores.get("desarmar_o_plantio") is True, (
            "a régua não vê o chamador direto do desarmador — sem isso ela acusaria "
            "as duas metades e mediria ausência, não assimetria"
        )

        copia_viva = _plantar(tmp_path / "viva", _ARMADOR_COM_CHAMADOR)
        assert "_plantio_da_mordida" not in pares_com_metade_ligada(copia_viva), (
            "com o armador chamado, o par tem as duas metades e não pode ser acusado"
        )

    def test_a_lista_de_leituras_atravessa_o_acessor(self, tmp_path: Path) -> None:
        """O endereço é o que roteia o conserto: a leitura pelo acessor entra na lista."""
        copia = _plantar(tmp_path, _ARMADOR_SEM_CHAMADOR)
        par = pares_com_metade_ligada(copia)["_plantio_da_mordida"]
        assert any(
            onde.startswith("daemon/leitor_do_plantio.py:") and "(via plantio_armado)" in onde
            for onde in par.leituras
        ), f"o portão não nomeia a leitura pelo acessor. Ele listou: {par.leituras}"

    def test_a_regua_nao_acusa_os_pares_simetricos(self) -> None:
        """Portão que grita dezessete vezes é desligado na primeira semana."""
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

    def test_a_regua_nao_confunde_prosa_com_chamador(self, tmp_path: Path) -> None:
        """As duas armadilhas do cabeçalho, plantadas."""
        assert "armar_o_plantio(daemon)" in _ARMADOR_SEM_CHAMADOR, (
            "o plantio perdeu a citação em docstring e parou de exercer a armadilha 1"
        )
        assert '__all__ = ["armar_o_plantio"' in _ARMADOR_SEM_CHAMADOR, (
            "o plantio perdeu o `__all__` e parou de exercer a armadilha 2"
        )
        copia = _copia_de_src(tmp_path)
        (copia / _PLANTIO).write_text(_ARMADOR_SEM_CHAMADOR, encoding="utf-8")
        assert "_plantio_da_mordida" in pares_com_metade_ligada(copia)

    def test_a_regua_sabe_recusar(self, tmp_path: Path) -> None:
        """Régua que só sabe passar não é régua (armadilha A2)."""
        copia = _copia_de_src(tmp_path)
        (copia / _PLANTIO).write_text(_ARMADOR_COM_CHAMADOR, encoding="utf-8")
        acusados = pares_com_metade_ligada(copia)
        assert "_plantio_da_mordida" not in acusados, (
            "a régua acusou um par cujas DUAS metades têm chamador em produção — "
            "ela não sabe recusar, e acusaria a árvore inteira"
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

    def test_uma_frase_de_tela_nao_desliga_o_portao(self, tmp_path: Path) -> None:
        """A TERCEIRA armadilha, achada em 25/08/2026 — e a que quase passou."""
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


import tokenize

_CITACAO = re.compile(r"(?P<alvo>[A-Za-z0-9_./]+\.py):(?P<ini>\d+)(?:-(?P<fim>\d+))?")

_EM_CRASE = re.compile(r"``?([^`\n]+?)``?")

_JANELA = 3

#: sai com: O-CODIGO-SEM-NARRADOR-01
_CITACOES_PENDENTES: frozenset[str] = frozenset({
    # `a10_perfis.py::rodape.py:101` SAIU DAQUI NO MESMO DIA (13/09/2026): a
    # reapontou o docstring de `editor_nome` pelo SÍMBOLO, `rodape._draft_do_ativo`.
    # A DE `a06_navegacao.py` -> `core/acoes_de_botao.py:203` SAIU DAQUI EM
    # `acoes_de_botao.py` e a pendência passou a "conferir" por acaso. O
    # comentário agora nomeia o símbolo (`core/acoes_de_botao.resolver`).
    #   rumble_actions.py:330  `profiles/manager.py:924-935` — REAPONTADA em
    # porque foram corrigidas no lugar (`core/acoes_de_botao.py`, as citações de
    # antes do `_fita` e de **+297** antes do `_recusou_dizendo`. As três moram
    #   a06_navegacao.py:1882 `hefesto_vivo.py:2018` -> `:2585` (`_recusou_dizendo`)
    #   a10_perfis.py:676    `hefesto_vivo.py:2018` -> `:2585` (`_recusou_dizendo`)
    #   a06_navegacao.py:1882 `hefesto_vivo.py:2476`          -> `:3307` (`_recusou_dizendo`)
    # reapontou cada uma pelo símbolo (`_fita`, `_recusou_dizendo`,
    # (endereço deslocado): o `_recusou_dizendo` que ela cita desceu com o
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
    """O `.py` citado, dentro do repositório — ou `None` se não for nosso."""
    for candidato in (raiz / alvo, _RAIZ / alvo, _RAIZ / "src" / alvo):
        if candidato.is_file():
            return candidato
    nome, sufixo = Path(alvo).name, "/" + alvo.removeprefix("./")
    achados = [p for p in raiz.rglob(nome) if p.as_posix().endswith(sufixo)] or [
        p
        for base in ("src", "tests", "scripts")
        for p in (_RAIZ / base).rglob(nome)
        if p.as_posix().endswith(sufixo)
    ]
    return achados[0] if len(achados) == 1 else None


#: reprovava só nas pernas 3.10 e 3.11 do `lint-test`, verde na bancada e no
_TOKENS_DE_PROSA: tuple[int, ...] = tuple(
    tipo
    for tipo in (tokenize.COMMENT, tokenize.STRING, getattr(tokenize, "FSTRING_MIDDLE", None))
    if tipo is not None
)


@functools.cache
def _prosa_dos_bytes(conteudo: bytes) -> tuple[tuple[int, str], ...]:
    """A prosa de um conteúdo, tokenizada UMA vez por conteúdo (a chave são os bytes)."""
    linhas: dict[int, str] = {}
    try:
        for tok in tokenize.tokenize(io.BytesIO(conteudo).readline):
            if tok.type not in _TOKENS_DE_PROSA:
                continue
            for offset, texto in enumerate(tok.string.splitlines()):
                linhas.setdefault(tok.start[0] + offset, "")
                linhas[tok.start[0] + offset] += texto
    except (tokenize.TokenError, SyntaxError):
        return ()
    return tuple(linhas.items())


def _prosa_de(modulo: Path) -> dict[int, str]:
    """As linhas do módulo que são COMENTÁRIO ou STRING, pela numeração real."""
    return dict(_prosa_dos_bytes(modulo.read_bytes()))


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
      cabeçalho: o `from_simple_choice` (`profiles/simple_match.py:137`) virava
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
    return list(_blocos_do_texto("\n".join(linhas)).get(nome, ()))


@functools.cache
def _blocos_do_texto(texto: str) -> dict[str, tuple[tuple[int, int, bool], ...]]:
    """Todo `def`/`class` do texto, por nome, numa só caminhada pela árvore.

    A régua pergunta por vários nomes do MESMO alvo, e cada pergunta refazia o
    ``ast.parse`` e a caminhada inteira; aqui o texto é lido uma vez e a
    resposta de cada nome sai da tabela, na mesma ordem em que a caminhada
    os acharia.
    """
    try:
        arvore = ast.parse(texto)
    except SyntaxError:
        return {}
    achadas: dict[str, list[tuple[int, int, bool]]] = {}

    def anda(no: ast.AST, dentro_de_funcao: bool) -> None:
        for filho in ast.iter_child_nodes(no):
            eh_funcao = isinstance(filho, (ast.FunctionDef, ast.AsyncFunctionDef))
            eh_definicao = eh_funcao or isinstance(filho, ast.ClassDef)
            if eh_definicao:
                fim = getattr(filho, "end_lineno", None) or filho.lineno  # type: ignore[attr-defined]
                achadas.setdefault(filho.name, []).append(  # type: ignore[attr-defined]
                    (filho.lineno, fim, dentro_de_funcao)  # type: ignore[attr-defined]
                )
            anda(filho, dentro_de_funcao or eh_funcao)

    anda(arvore, False)
    return {nome: tuple(blocos) for nome, blocos in achadas.items()}


def _definicao_unica(linhas: list[str], nome: str) -> tuple[int, int] | None:
    """`(primeira, derradeira)` do bloco de `def`/`class` chamado `nome`."""
    achadas = _blocos_definidos(linhas, nome)
    if len(achadas) != 1:
        return None
    inicio, fim, aninhada = achadas[0]
    return None if aninhada else (inicio, fim)


def _endereco_corroborado(linhas: list[str], cit: CitacaoDeLinha, nomes: list[str]) -> bool:
    """O trecho citado MOSTRA algum dos nomes da prosa em volta?"""
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


_ALVO_PLANTADO = (
    "VALOR = 0\nOUTRO = 1\n\ndef ancora_plantada():\n    return 1\n"
)


class TestTodaCitacaoDeLinhaConfere:
    def test_toda_citacao_de_linha_em_comentario_de_codigo_confere(self) -> None:
        """O endereço escrito em `src/` tem de apontar para o que ele promete."""
        queixas = enderecos_envelhecidos()
        vivas = {k: v for k, v in queixas.items() if k not in _CITACOES_PENDENTES}
        assert not vivas, (
            f"{len(vivas)} endereço(s) de linha em `src/` apontam para outro "
            "lugar hoje:\n"
            + "\n".join(f"  - {v}" for v in sorted(vivas.values()))
            + "\nRode `python3 scripts/reapontar-citacoes.py --escrever`: ele leva "
            "cada endereço pelo histórico do git até onde o símbolo está hoje, e "
            "só escreve o que confere. O que ele deixar «à mão», meça com "
            "`grep -n`. Se o arquivo citante for de outra posse, ponha a chave em "
            "`_CITACOES_PENDENTES` com o motivo — nunca afrouxe a régua."
        )

    def test_a_lista_de_pendentes_nao_vira_paisagem(self) -> None:
        """Pendência consertada TEM de sair da lista — senão ela vira ruído."""
        queixas = enderecos_envelhecidos()
        curadas = sorted(_CITACOES_PENDENTES - set(queixas))
        assert not curadas, (
            f"{len(curadas)} citação(ões) declarada(s) como pendente(s) já "
            "conferem — apague-as de `_CITACOES_PENDENTES`:\n"
            + "\n".join(f"  - {c}" for c in curadas)
        )


    def test_a_regua_ignora_alvo_que_nao_e_desta_casa(self, tmp_path: Path) -> None:
        """`pydualsense.py:610` é biblioteca de terceiro — não temos as linhas."""
        copia = _copia_de_src(tmp_path)
        (copia / "utils" / "_citante_da_mordida.py").write_text(
            "# ver `biblioteca_que_nao_existe_aqui.py:99`\nVALOR = 1\n",
            encoding="utf-8",
        )
        assert not [
            k for k in enderecos_envelhecidos(copia) if "_da_mordida" in k
        ]


    def test_o_caminho_parcial_ambiguo_nao_se_chuta(self, tmp_path: Path) -> None:
        """Dois arquivos com o mesmo sufixo: a régua não escolhe um por sorte."""
        copia = _copia_de_src(tmp_path)
        for base in ("utils", "core"):
            (copia / base / "fundo").mkdir()
            (copia / base / "fundo" / "_alvo_parcial_da_mordida.py").write_text(
                _ALVO_PLANTADO, encoding="utf-8"
            )
        (copia / "utils" / "_citante_da_mordida.py").write_text(
            "# `ancora_plantada` mora em `fundo/_alvo_parcial_da_mordida.py:2`.\nVALOR = 1\n",
            encoding="utf-8",
        )
        assert not [k for k in enderecos_envelhecidos(copia) if "_da_mordida" in k]

    def test_a_regua_le_a_citacao_dentro_de_f_string_em_qualquer_python(
        self, tmp_path: Path
    ) -> None:
        """A citação escrita dentro de uma f-string é prosa em todo Python."""
        copia = _copia_de_src(tmp_path)
        (copia / "utils" / "_alvo_da_mordida.py").write_text(
            _ALVO_PLANTADO, encoding="utf-8"
        )
        (copia / "utils" / "_citante_da_mordida.py").write_text(
            'NOME = "x"\n'
            'TEXTO = f"""<p>O {NOME} mora em\n'
            '`ancora_plantada` (<code>utils/_alvo_da_mordida.py:2</code>).</p>"""\n',
            encoding="utf-8",
        )
        queixas = enderecos_envelhecidos(copia)
        chave = "utils/_citante_da_mordida.py::utils/_alvo_da_mordida.py:2"
        assert chave in queixas, (
            "a régua não viu um endereço envelhecido escrito dentro de uma "
            f"f-string. Ela achou: {sorted(k for k in queixas if '_da_mordida' in k)}"
        )

    def test_a_regua_nao_acusa_o_endereco_certo(self, tmp_path: Path) -> None:
        """O outro lado do dublê: o MESMO plantio, com o número certo, passa."""
        copia = _copia_de_src(tmp_path)
        (copia / "utils" / "_alvo_da_mordida.py").write_text(
            _ALVO_PLANTADO, encoding="utf-8"
        )
        (copia / "utils" / "_citante_da_mordida.py").write_text(
            _citante_plantado(4), encoding="utf-8"
        )
        plantadas = [k for k in enderecos_envelhecidos(copia) if "_da_mordida" in k]
        assert not plantadas, f"a régua acusou um endereço CERTO: {plantadas}"

    def test_a_regua_sabe_reprovar(self, tmp_path: Path) -> None:
        """Régua que só sabe passar não é régua (armadilha A2)."""
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

    def test_o_caminho_parcial_entra_na_regua(self, tmp_path: Path) -> None:
        """`pacotes/perfil.py:134` é nosso, e até 25/09/2026 a régua não o via."""
        copia = _copia_de_src(tmp_path)
        fundo = copia / "utils" / "fundo"
        fundo.mkdir()
        (fundo / "_alvo_parcial_da_mordida.py").write_text(_ALVO_PLANTADO, encoding="utf-8")
        (copia / "utils" / "_citante_da_mordida.py").write_text(
            "# `ancora_plantada` mora em `fundo/_alvo_parcial_da_mordida.py:2`.\nVALOR = 1\n",
            encoding="utf-8",
        )
        chave = "utils/_citante_da_mordida.py::fundo/_alvo_parcial_da_mordida.py:2"
        assert chave in enderecos_envelhecidos(copia), (
            "a régua não viu o endereço plantado por caminho parcial"
        )
