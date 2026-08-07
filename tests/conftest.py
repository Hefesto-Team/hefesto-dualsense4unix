"""Fixtures compartilhadas entre testes unit e integration.

Além das fixtures, este arquivo hospeda a GUARDA-GI-REAL-01 — a resposta ao
defeito medido em 28/07: ``pytest.importorskip("gi")`` é DERROTADO por poluição
de ``sys.modules``. Vinte e um arquivos de teste plantam um ``gi`` falso (com
``Gtk.Box = object``) no nível de módulo; quem vem depois na ORDEM ALFABÉTICA
importa esse falso, o ``importorskip`` não pula, e centenas de testes de
interface reportam PASSED contra um GTK de mentira. Cobertura falsa é pior do
que cobertura ausente. Ver ``exigir_gi_real`` e ``pytest_collectstart`` abaixo.
"""

import hashlib
import os
import sys
import types
from pathlib import Path
from typing import Any

import pytest

# ---------------------------------------------------------------------------
# GUARDA-GI-REAL-01 — o `gi` do processo é o de verdade, ou é um stub?
# ---------------------------------------------------------------------------

#: Nomes de módulo que os stubs de teste plantam em ``sys.modules``.
_PREFIXO_GI = "gi"


def _e_modulo_gi(nome: str) -> bool:
    """True para ``gi`` e qualquer submódulo (``gi.repository.Gtk`` etc.)."""
    return nome == _PREFIXO_GI or nome.startswith(_PREFIXO_GI + ".")


def _gtk_e_real(gtk: Any) -> bool:
    """True quando ``gtk`` expõe widgets de VERDADE, não os do stub.

    O stub canônico dos testes faz ``Gtk.Box = object`` — passa em qualquer
    ``hasattr``, e é justamente por isso que ``importorskip`` não o pega. Aqui
    o critério é o que distingue os dois: no PyGObject real ``Gtk.Box`` é uma
    classe própria (``gi.overrides.Gtk.Box``), nunca o ``object`` embutido.
    """
    caixa = getattr(gtk, "Box", None)
    if caixa is None or caixa is object:
        return False
    if not isinstance(caixa, type):
        return False
    # `types.ModuleType` puro (o stub) nunca tem `ListStore` E `Box` reais ao
    # mesmo tempo; o real tem os dois.
    lista = getattr(gtk, "ListStore", None)
    return lista is not None and lista is not object


def gi_real_no_processo() -> bool:
    """True quando o ``gi`` JÁ CARREGADO neste processo é o PyGObject real.

    Devolve False tanto para "não há ``gi``" quanto para "há um stub plantado
    por outro arquivo de teste" — é esta segunda resposta que o
    ``pytest.importorskip("gi")`` erra.
    """
    modulo_gi = sys.modules.get(_PREFIXO_GI)
    if modulo_gi is None:
        return False
    # `types.ModuleType("gi")` nasce com `__spec__` None; o pacote real tem um.
    if getattr(modulo_gi, "__spec__", None) is None:
        return False
    gtk = sys.modules.get("gi.repository.Gtk")
    if gtk is None:
        # O `gi` é real e o Gtk ainda não foi carregado — nada a reprovar.
        return True
    return _gtk_e_real(gtk)


def gi_stub_no_processo() -> bool:
    """True quando há um ``gi`` carregado e ele é FALSO (stub de teste)."""
    return any(_e_modulo_gi(n) for n in sys.modules) and not gi_real_no_processo()


def _remover_gi_do_processo() -> list[str]:
    """Apaga todo ``gi*`` de ``sys.modules`` e devolve os nomes removidos."""
    removidos = [n for n in list(sys.modules) if _e_modulo_gi(n)]
    for nome in removidos:
        del sys.modules[nome]
    return removidos


#: Fotografia dos módulos ``gi*`` REAIS, mantida em dia enquanto o processo tem
#: o PyGObject de verdade carregado.
#:
#: Ela existe por uma razão medida: NÃO se desfaz um stub simplesmente apagando
#: o ``gi`` e deixando o próximo módulo reimportar. O PyGObject registra tipos
#: no GObject na primeira importação, e a segunda estoura
#: ``RuntimeError: Unable to register enum 'PyGLibUserDirectory'`` — na máquina
#: da mantenedora isso derrubou 66 testes e 39 coletas de uma vez. Devolver os
#: MESMOS objetos de módulo não reimporta nada e não registra nada de novo.
_FOTO_GI_REAL: dict[str, Any] = {}


def _atualizar_foto_gi_real() -> None:
    """Guarda os módulos ``gi*`` atuais — só chamar com o ``gi`` REAL no ar."""
    for nome in list(sys.modules):
        if _e_modulo_gi(nome):
            _FOTO_GI_REAL[nome] = sys.modules[nome]


def _restaurar_gi_real_da_foto() -> bool:
    """Troca o stub pelos módulos reais fotografados. False se não há foto."""
    if not _FOTO_GI_REAL:
        return False
    _remover_gi_do_processo()
    sys.modules.update(_FOTO_GI_REAL)
    return gi_real_no_processo()


def _sondar_gtk_do_ambiente() -> tuple[bool, bool]:
    """Pergunta a um SUBPROCESSO limpo o que o ambiente tem de GTK.

    Devolve ``(gi_real_disponivel, response_type_presente)``.

    Roda fora do processo de propósito: importar o Gtk aqui, no conftest
    (avaliado cedo, na coleta), competiria com a versão que outro teste já
    carregou — o repo mistura Gtk 3.0 (produção) e 4.0 (fixtures), e
    "Namespace already loaded" derruba a coleta inteira. O subprocesso não tem
    esse estado e responde só as duas perguntas que importam.
    """
    import subprocess

    codigo = (
        "import sys\n"
        "try:\n"
        "    import gi\n"
        "    try:\n"
        "        gi.require_version('Gtk', '3.0')\n"
        "    except Exception:\n"
        "        pass\n"
        "    from gi.repository import Gtk\n"
        "except Exception:\n"
        "    print('0 0')\n"
        "    sys.exit(0)\n"
        "caixa = getattr(Gtk, 'Box', None)\n"
        "lista = getattr(Gtk, 'ListStore', None)\n"
        "real = (\n"
        "    caixa is not None and caixa is not object and isinstance(caixa, type)\n"
        "    and lista is not None and lista is not object\n"
        ")\n"
        "print(('1' if real else '0'), ('1' if hasattr(Gtk, 'ResponseType') else '0'))\n"
    )
    try:
        r = subprocess.run(
            [sys.executable, "-c", codigo],
            capture_output=True,
            timeout=30,
        )
    except Exception:
        return (False, False)
    saida = r.stdout.decode("utf-8", "replace").split()
    if r.returncode != 0 or len(saida) != 2:
        return (False, False)
    return (saida[0] == "1", saida[1] == "1")


#: Medido UMA vez, na importação do conftest (o subprocesso é barato).
GI_REAL_DISPONIVEL, _GTK_RESPONSE_TYPE_PRESENTE = _sondar_gtk_do_ambiente()

#: Quando ligado, "pular por falta de GTK real" vira REPROVAÇÃO. É o que o job
#: dedicado do CI (com `python3-gi` + typelibs + Xvfb) usa: lá, um pulo é um
#: defeito de ambiente disfarçado de sucesso, e o pulo silencioso é metade do
#: problema que esta guarda existe para curar.
EXIGE_GTK_REAL = os.environ.get("HEFESTO_EXIGE_GTK_REAL") == "1"

_MOTIVO_SEM_GI = (
    "GUARDA-GI-REAL-01: PyGObject real ausente (ou substituído por stub de "
    "teste). Instale python3-gi + gir1.2-gtk-3.0 para exercitar a interface."
)

#: Marker reusável: pula quando o GTK do ambiente não expõe os enums de widget.
skip_sem_gtk_response = pytest.mark.skipif(
    not _GTK_RESPONSE_TYPE_PRESENTE,
    reason="Gtk.ResponseType indisponível (GTK parcial — CI headless)",
)

#: Marker reusável: pula quando não há PyGObject REAL. Substitui, com critério
#: honesto, o ``pytest.importorskip("gi")`` — que aceita o stub.
skip_sem_gi_real = pytest.mark.skipif(not GI_REAL_DISPONIVEL, reason=_MOTIVO_SEM_GI)

#: Módulos que pularam por falta de GTK real, para o resumo alto no fim do run.
_MODULOS_PULADOS_SEM_GI: list[str] = []

#: Módulos cujo `gi` FALSO foi retirado antes da importação do módulo seguinte.
_MODULOS_DESPOLUIDOS: list[str] = []


def _carregar_gi_real() -> None:
    """Importa o PyGObject real (Gtk 3.0) no processo, em silêncio se não der."""
    try:
        import gi

        gi.require_version("Gtk", "3.0")
        repositorio = __import__("gi.repository", fromlist=["Gtk"])
        _ = repositorio.Gtk
    except Exception:  # pragma: no cover — ambiente degradado ou sem GTK
        pass


def exigir_gi_real(motivo: str = "") -> None:
    """Guarda de nível de módulo: exige o PyGObject REAL, reprovando o stub.

    Use no lugar de ``pytest.importorskip("gi")`` em todo módulo de teste que
    só faz sentido contra o GTK de verdade. A diferença é o critério:

    - ``importorskip("gi")`` pergunta "``import gi`` funciona?" — e um stub
      plantado por OUTRO arquivo de teste responde que sim;
    - ``exigir_gi_real()`` pergunta "o ``Gtk`` deste processo tem widgets de
      verdade?" — e o stub (``Gtk.Box = object``) reprova.

    Quando há stub carregado mas o AMBIENTE tem PyGObject real, a função limpa
    o stub em vez de pular: quem mentiu foi o arquivo anterior, e a máquina de
    desenvolvimento não pode perder centenas de testes por causa disso.
    """
    if gi_real_no_processo():
        return

    if GI_REAL_DISPONIVEL:
        # Ambiente bom, processo envenenado: devolve os módulos reais (a foto)
        # ou, se ainda não há foto, importa o PyGObject pela primeira vez.
        if not _restaurar_gi_real_da_foto():
            _remover_gi_do_processo()
            _carregar_gi_real()
        if gi_real_no_processo():
            _atualizar_foto_gi_real()
            return

    texto = _MOTIVO_SEM_GI + (f" [{motivo}]" if motivo else "")
    _MODULOS_PULADOS_SEM_GI.append(motivo or "<módulo sem rótulo>")
    if EXIGE_GTK_REAL:
        pytest.fail(
            "HEFESTO_EXIGE_GTK_REAL=1 e o GTK real NÃO está disponível: " + texto,
            pytrace=False,
        )
    pytest.skip(texto, allow_module_level=True)


def instalar_stubs_gi(
    monkeypatch: pytest.MonkeyPatch,
    *,
    widgets: tuple[str, ...] = (),
) -> types.ModuleType:
    """Planta stubs de ``gi`` ISOLADOS, desfeitos ao fim do escopo do monkeypatch.

    Alternativa ao ``sys.modules["gi"] = ...`` cru: o ``monkeypatch.setitem``
    devolve ``sys.modules`` ao estado anterior no teardown, então a poluição
    não vaza para o arquivo seguinte. Devolve o módulo ``gi.repository.Gtk``
    plantado, para o chamador acrescentar o que faltar.
    """
    gi_mod = types.ModuleType("gi")
    gi_mod.require_version = lambda *_a, **_kw: None  # type: ignore[attr-defined]
    repo_mod = types.ModuleType("gi.repository")
    gtk_mod = types.ModuleType("gi.repository.Gtk")
    for nome in widgets:
        setattr(gtk_mod, nome, object)
    repo_mod.Gtk = gtk_mod  # type: ignore[attr-defined]
    monkeypatch.setitem(sys.modules, "gi", gi_mod)
    monkeypatch.setitem(sys.modules, "gi.repository", repo_mod)
    monkeypatch.setitem(sys.modules, "gi.repository.Gtk", gtk_mod)
    return gtk_mod


def pytest_collectstart(collector: Any) -> None:
    """Impede que o ``gi`` FALSO de um arquivo vaze para o arquivo seguinte.

    Este é o coração da GUARDA-GI-REAL-01. A importação dos módulos de teste
    acontece toda na COLETA, antes de qualquer fixture rodar — por isso
    nenhuma fixture (nem ``monkeypatch``) chega a tempo de desfazer o plantio
    antes do próximo arquivo ser importado. Este hook chega: ele roda logo
    antes de cada módulo ser importado.

    Regra: se o ``gi`` carregado for REAL, não se mexe (é o estado desejado) e
    a fotografia dos módulos reais fica em dia. Se for um STUB, ele sai — pela
    fotografia, quando existe (máquina com GTK: o módulo seguinte recebe o
    PyGObject de verdade, sem reimportar nada), ou apagado (CI sem GTK: o
    módulo seguinte decide sozinho — importa, planta o próprio stub, ou pula).
    O que ele NÃO faz mais é herdar a mentira de quem veio antes por acaso da
    ordem alfabética.
    """
    if not isinstance(collector, pytest.Module):
        return
    if gi_real_no_processo():
        _atualizar_foto_gi_real()
        return
    if not gi_stub_no_processo():
        return
    if _restaurar_gi_real_da_foto():
        _MODULOS_DESPOLUIDOS.append(str(getattr(collector, "nodeid", collector)))
        return
    if _remover_gi_do_processo():
        _MODULOS_DESPOLUIDOS.append(str(getattr(collector, "nodeid", collector)))


def pytest_report_header(config: Any) -> str:
    """Diz, no cabeçalho do run, contra QUAL GTK a suíte vai rodar."""
    estado = "REAL (python3-gi + typelibs)" if GI_REAL_DISPONIVEL else "AUSENTE"
    extra = " | HEFESTO_EXIGE_GTK_REAL=1 (pulo vira reprovação)" if EXIGE_GTK_REAL else ""
    return f"guarda-gi-real-01: PyGObject {estado}{extra}"


def pytest_terminal_summary(terminalreporter: Any, exitstatus: int, config: Any) -> None:
    """Torna VISÍVEL o pulo por falta de GTK — o pulo calado é parte do defeito."""
    escrever = terminalreporter.write_line
    if _MODULOS_PULADOS_SEM_GI:
        escrever("")
        escrever(
            "GUARDA-GI-REAL-01: "
            f"{len(_MODULOS_PULADOS_SEM_GI)} módulo(s) de interface PULARAM por "
            "falta de PyGObject real:",
            bold=True,
        )
        for nome in _MODULOS_PULADOS_SEM_GI:
            escrever(f"  - {nome}")
        escrever(
            "  Isto NÃO é cobertura. Instale python3-gi + gir1.2-gtk-3.0 "
            "para exercitar a interface."
        )
    if _MODULOS_DESPOLUIDOS:
        escrever("")
        escrever(
            "GUARDA-GI-REAL-01: stub de `gi` retirado antes de "
            f"{len(_MODULOS_DESPOLUIDOS)} módulo(s) — a poluição de sys.modules "
            "NÃO vazou entre arquivos.",
            bold=True,
        )


# ---------------------------------------------------------------------------
# CANARIO-FS-01 — a suíte escreveu no ~/.config DELA?
# ---------------------------------------------------------------------------
# O PORQUÊ, medido em 04/08/2026: os perfis dela foram encontrados corrompidos
# e a pergunta que ficou sem resposta foi "como sabemos se algum TESTE corrompeu
# algo?". A fixture `_hefesto_fake_env` isola os diretórios XDG — mas NÃO isola
# o ``HOME``, e há constantes de módulo avaliadas na IMPORTAÇÃO que apontam para
# arquivos reais dela por ``Path.home()``:
#
#   - `integrations/storm_doctor.py` (_ALLOWLIST_PATH, leitura);
#   - `app/actions/emulation_actions.py` (_WP_DROPIN_DIR, e este é dir de
#     ESCRITA em produção — o toggle do microfone cria e apaga drop-ins ali).
#
# Constante de módulo é avaliada ANTES de qualquer monkeypatch de ``HOME``, então
# nenhuma fixture consegue desviá-la depois.
#
# ATUALIZAÇÃO 05/08/2026 (decisão dela: *"preciso que as constantes apontem
# pros arquivos reais"*): as DUAS viraram função — `storm_doctor._allowlist_path`
# e `EmulationActionsMixin._wp_dropin_dir`. `Path.home()` dentro de função lê o
# ``HOME`` na hora da chamada, então o isolamento da suíte volta a valer e o
# comportamento em produção não muda. O canário CONTINUA, e não por desconfiança
# destas duas: ele cobre o que ninguém mapeou — subprocessos, `systemctl`,
# `uinput` e a próxima constante que alguém escrever sem pensar nisso.
#
# O canário fotografa (mtime_ns, tamanho, sha256) dos diretórios de verdade no
# início e no fim da sessão e REPROVA listando o que mudou. O hash não é zelo:
# a primeira versão comparava só (mtime_ns, size) e acusou 15 arquivos `.lock`
# na estreia — tocados pelo daemon e pela janela DELA, vivos ao lado da suíte.
# Um portão que grita no primeiro dia é um portão que alguém desliga no segundo.
#
# Isto não é hipótese: é medição. Se a suíte não escreve nada, o canário é
# invisível; se escreve, ele diz exatamente qual arquivo.

#: Diretórios REAIS que a suíte não pode tocar. Relativos ao ``HOME``.
_CANARIO_ALVOS: tuple[str, ...] = (
    ".config/hefesto-dualsense4unix",
    ".config/wireplumber",
    ".local/share/hefesto-dualsense4unix",
)

#: Escotilha de saída, para quem PRECISA rodar a suíte contra o HOME real
#: (nunca deveria ser preciso — existe para não obrigar ninguém a comentar
#: código quando o daemon está de pé e mexendo no session.json ao lado).
_CANARIO_DESLIGADO_ENV = "HEFESTO_SEM_CANARIO_FS"

#: Fotografia do início da sessão: {caminho: (mtime_ns, tamanho, resumo)}.
_CANARIO_FOTO_INICIAL: dict[str, tuple[int, int, str]] = {}

#: True só depois que a foto inicial foi tirada. Sem este selo, uma sessão que
#: começou com o canário desligado e terminou com ele ligado compararia contra
#: um dicionário vazio e acusaria TODO arquivo do ``$HOME`` de ter nascido
#: durante a suíte — o alarme mais falso que existe.
_CANARIO_ARMADO = False

#: Acima disto o arquivo não é resumido (só mtime+tamanho). Nada nos diretórios
#: vigiados chega perto — medido em 05/08: 93 arquivos, 356 KB no total.
_CANARIO_LIMITE_RESUMO = 4 * 1024 * 1024


def _canario_ligado() -> bool:
    return os.environ.get(_CANARIO_DESLIGADO_ENV) != "1"


def _canario_raizes() -> list[Path]:
    """Os alvos resolvidos contra o ``HOME`` REAL do processo.

    Lido de ``os.environ`` no momento da chamada de propósito: se um teste
    trocar o ``HOME``, as duas fotos ainda comparam a MESMA árvore, porque os
    dois hooks rodam fora de qualquer fixture.
    """
    lar = Path(os.path.expanduser("~"))
    return [lar / alvo for alvo in _CANARIO_ALVOS]


def _resumo_do_arquivo(caminho: Path, tamanho: int) -> str:
    """sha256 do conteúdo — vazio para diretórios, ilegíveis e arquivos enormes.

    O resumo existe por uma medição de 05/08: com o daemon e a janela DELA de
    pé ao lado da suíte, os `*.json.lock` do diretório de perfis mudam de mtime
    a cada poucos segundos (o `filelock` toca o arquivo a cada aquisição). Um
    canário que reprovasse por mtime acusaria a suíte do que o daemon fez, e
    seria desligado na primeira semana. Conteúdo não mente: comparar o resumo
    reprova toda ESCRITA de verdade e ignora o vaivém dos locks.
    """
    if tamanho > _CANARIO_LIMITE_RESUMO:
        return ""
    try:
        return hashlib.sha256(caminho.read_bytes()).hexdigest()
    except OSError:
        return ""


def _fotografar_arvore(raiz: Path) -> dict[str, tuple[int, int, str]]:
    """{caminho: (mtime_ns, tamanho, resumo)} sob `raiz`. Ausente = dict vazio.

    Diretórios entram na foto para que um subdiretório novo (ou sumido) apareça
    como delta. Erros de permissão são pulados em silêncio: o canário mede o que
    consegue ver, e ver menos nunca pode derrubar a suíte por si só.
    """
    foto: dict[str, tuple[int, int, str]] = {}
    if not raiz.exists():
        return foto
    for caminho in [raiz, *raiz.rglob("*")]:
        try:
            st = caminho.stat()
            e_arquivo = caminho.is_file()
        except OSError:
            continue
        resumo = _resumo_do_arquivo(caminho, st.st_size) if e_arquivo else ""
        foto[str(caminho)] = (st.st_mtime_ns, st.st_size, resumo)
    return foto


def _fotografar_tudo() -> dict[str, tuple[int, int, str]]:
    foto: dict[str, tuple[int, int, str]] = {}
    for raiz in _canario_raizes():
        foto.update(_fotografar_arvore(raiz))
    return foto


def _deltas_do_canario(
    antes: dict[str, tuple[int, int, str]], depois: dict[str, tuple[int, int, str]]
) -> list[str]:
    """Lista legível do que mudou entre as duas fotos (vazia = nada mudou).

    Delta de arquivo é MUDANÇA DE CONTEÚDO (tamanho ou resumo) — mtime sozinho
    não conta, pelo motivo medido em `_resumo_do_arquivo`.
    """
    deltas: list[str] = []
    deltas.extend(f"CRIADO   {c}" for c in sorted(set(depois) - set(antes)))
    deltas.extend(f"APAGADO  {c}" for c in sorted(set(antes) - set(depois)))
    for caminho in sorted(set(antes) & set(depois)):
        (_mt_a, tam_a, resumo_a) = antes[caminho]
        (_mt_d, tam_d, resumo_d) = depois[caminho]
        if (tam_a, resumo_a) == (tam_d, resumo_d):
            continue
        detalhe = f"tamanho {tam_a}->{tam_d}" if tam_a != tam_d else "conteúdo"
        deltas.append(f"MUDADO   {caminho} ({detalhe})")
    return deltas


def pytest_sessionstart(session: Any) -> None:
    """CANARIO-FS-01: primeira fotografia dos diretórios REAIS da usuária."""
    global _CANARIO_ARMADO
    if not _canario_ligado():
        return
    _CANARIO_FOTO_INICIAL.update(_fotografar_tudo())
    _CANARIO_ARMADO = True


def _escrever_no_terminal(session: Any, linhas: list[str]) -> None:
    """Imprime pelo terminalreporter quando ele existe; senão, no stdout."""
    relator = None
    config = getattr(session, "config", None)
    gerenciador = getattr(config, "pluginmanager", None)
    if gerenciador is not None:
        relator = gerenciador.get_plugin("terminalreporter")
    for linha in linhas:
        if relator is not None:
            relator.write_line(linha)
        else:  # pragma: no cover — pytest sempre tem terminalreporter
            print(linha)


def pytest_sessionfinish(session: Any, exitstatus: int) -> None:
    """Sob ``HEFESTO_EXIGE_GTK_REAL=1``, pulo por falta de GTK reprova o run.

    E, sempre, o CANARIO-FS-01: se a suíte mexeu em qualquer arquivo dos
    diretórios REAIS da usuária, o run REPROVA com a lista do que mudou. Um
    teste hermético não deixa rastro nenhum em ``$HOME``.
    """
    if EXIGE_GTK_REAL and _MODULOS_PULADOS_SEM_GI:
        session.exitstatus = 1

    # ARVORE-CONGELADA-01, segunda metade: o produto mudou DEBAIXO da medição?
    # Então este run não mediu uma coisa só, e nenhum verde nem vermelho dele
    # vale. Reprovar é a única saída honesta: um verde falso passa despercebido
    # para sempre, e foi assim que uma mordida real foi declarada inexistente.
    deltas_produto = _deltas_do_congelado()
    if deltas_produto:
        mostrados = deltas_produto[:_CONGELADA_LIMITE_RELATO]
        restam = len(deltas_produto) - len(mostrados)
        _escrever_no_terminal(session, [
            "",
            "ARVORE-CONGELADA-01: o PRODUTO mudou durante esta sessão "
            f"({len(deltas_produto)} arquivo(s)):",
            *[f"  - {d}" for d in mostrados],
            *([f"  ... e mais {restam}"] if restam > 0 else []),
            "  A bancada mediu a foto do início; a árvore de hoje é outra. Este",
            "  run NÃO decide nada — nem o verde, nem o vermelho. Rode de novo",
            "  com a árvore parada (um mutador por vez, ou um git worktree por",
            "  agente) antes de gravar qualquer nota que dependa dele.",
        ])
        session.exitstatus = 1

    if not _canario_ligado() or not _CANARIO_ARMADO:
        return
    deltas = _deltas_do_canario(_CANARIO_FOTO_INICIAL, _fotografar_tudo())
    if not deltas:
        return
    linhas = [
        "",
        "CANARIO-FS-01: a suíte ESCREVEU nos diretórios reais da usuária "
        f"({len(deltas)} mudança(s)):",
        *[f"  - {d}" for d in deltas],
        "  Um teste hermético não deixa rastro em $HOME. Procure constante de",
        "  módulo com Path.home() avaliada no import (monkeypatch de HOME não a",
        "  alcança) — mova para função e injete o caminho.",
        f"  Se o daemon/GUI estava rodando ao lado, {_CANARIO_DESLIGADO_ENV}=1 "
        "desliga este canário.",
    ]
    _escrever_no_terminal(session, linhas)
    session.exitstatus = 1


# NOTA: a sonda antiga `_gtk_response_type_ausente()` foi fundida em
# `_sondar_gtk_do_ambiente()` acima — um subprocesso responde as DUAS
# perguntas (gi real? ResponseType presente?) em vez de dois.


# ---------------------------------------------------------------------------
# ARVORE-CONGELADA-01 — o produto MEDIDO não pode mudar no meio da medição
# ---------------------------------------------------------------------------
#
# O DEFEITO, MEDIDO em 06/08/2026 (diagnóstico com reprodução em três braços):
# uma bancada que roda `bash /caminho/absoluto/da/arvore/scripts/x.sh` mede o
# arquivo que estiver no disco NAQUELE INSTANTE. Quando outro processo edita
# esse arquivo durante a sessão — um agente irmão fazendo "arrancar a cura ->
# rodar -> devolver", um `git checkout` noutro terminal, um editor salvando —
# a bancada mede o produto de outra pessoa. O braço de controle da reprodução:
#
#   bancada em cópia A, ninguém mutando A ......... 0 falhas / 10
#   bancada em cópia A, mutador ciclando em A ..... 5 falhas / 10 (testes
#                                                   DIFERENTES a cada rodada)
#   bancada em cópia B, mutador ciclando em A ..... 0 falhas / 10
#
# O terceiro braço é a prova de que o canal é o ARQUIVO COMPARTILHADO, e não
# carga da máquina nem concorrência entre execuções (18 `pytest` simultâneos na
# árvore real: 0 falhas / 18).
#
# E a contaminação vai nos DOIS sentidos, o que é o pior da história: mutação
# alheia viva produz VERMELHO FALSO (mordida afirmada que não existe), e um
# `cp ORIG` alheio que desfaz a sua mutação antes do `pytest` rodar produz
# VERDE FALSO (mordida real declarada inexistente). É exatamente a classe que
# a regra "teste tem de MORDER" existe para impedir.
#
# A CURA que não depende de disciplina de processo: a bancada não lê a árvore
# de trabalho — lê uma CÓPIA tirada UMA VEZ, no início da sessão. O que roda
# continua sendo o que está na árvore no instante em que o `pytest` começou
# (então arrancar uma cura ANTES de rodar continua ficando vermelho, como tem
# de ser); o que deixa de existir é a janela em que o arquivo muda DEBAIXO da
# medição.
#
# Não substitui o CANARIO-FS-01 acima: aquele vigia o `$HOME` DELA contra
# escrita da suíte; este protege a MEDIÇÃO contra escrita de terceiros.

#: O que uma bancada de shell precisa enxergar. Lista explícita de propósito:
#: `packaging/cosmic-applet/target` tem 18 GB e copiar a árvore inteira seria
#: trocar um defeito por outro.
_CONGELAR: tuple[str, ...] = (
    "scripts",
    "assets/bluetooth",
    "flatpak",
    "packaging/arch",
    "packaging/debian",
    "packaging/fedora",
    "packaging/nix",
    ".github/workflows",
    "install.sh",
    "uninstall.sh",
)

#: Lixo de build que nunca é produto.
_CONGELAR_IGNORAR = ("__pycache__", "target", ".flatpak-builder", "build", "*.pyc")

#: Preenchido na primeira chamada e nunca mais — a foto é da SESSÃO.
_ARVORE_CONGELADA: list[Path] = []


def arvore_congelada() -> Path:
    """Cópia só-leitura da árvore, tirada UMA VEZ por sessão de `pytest`.

    Use-a como raiz em toda bancada que EXECUTA um arquivo do repositório
    (``bash scripts/...``) em vez de apenas lê-lo: é o que impede que uma
    escrita de terceiro no meio da sessão vire falha (ou aprovação) inventada.
    Ver ARVORE-CONGELADA-01 acima.
    """
    if _ARVORE_CONGELADA:
        return _ARVORE_CONGELADA[0]

    import atexit
    import shutil
    import tempfile

    origem_raiz = Path(__file__).resolve().parents[1]
    destino = Path(tempfile.mkdtemp(prefix="hefesto-arvore-congelada-"))
    atexit.register(shutil.rmtree, destino, True)
    ignorar = shutil.ignore_patterns(*_CONGELAR_IGNORAR)
    for relativo in _CONGELAR:
        origem = origem_raiz / relativo
        alvo = destino / relativo
        if origem.is_dir():
            alvo.parent.mkdir(parents=True, exist_ok=True)
            shutil.copytree(origem, alvo, ignore=ignorar, symlinks=True)
        elif origem.is_file():
            alvo.parent.mkdir(parents=True, exist_ok=True)
            shutil.copy2(origem, alvo)
    _ARVORE_CONGELADA.append(destino)
    return destino


#: Teto de linhas do relatório — uma sessão contaminada de verdade muda poucos
#: arquivos; se mudou centenas, a lista inteira não ajuda ninguém.
_CONGELADA_LIMITE_RELATO = 20


def _deltas_do_congelado() -> list[str]:
    """O produto MUDOU entre a foto e o fim da sessão? Diga quais arquivos.

    Congelar torna o veredito COERENTE (uma sessão inteira mede o mesmo
    produto) — não torna a bancada imune: uma mutação que já estivesse viva no
    instante da foto é medida a sessão inteira, e é indistinguível de um defeito
    de verdade, como TEM de ser (é assim que se prova mordida). O que faltava era
    a outra metade: DIZER quando isso aconteceu, em vez de acreditar no veredito.
    Sem isto, um `cp ORIG` de terceiro no meio da sessão desfaz a sua mutação e
    a suíte declara VERDE uma mordida real — o pior dos dois erros.

    O LIMITE DESTA SONDA, MEDIDO e declarado para ninguém a tomar por garantia:
    ela compara DOIS INSTANTES (a foto e o fim), não vigia o intervalo. Numa
    reprodução de 06/08/2026 com um mutador ciclando a 2 Hz na árvore durante
    dez execuções, a sonda acusou 3 das 10 — e as 7 restantes eram sessões em
    que a árvore estava no MESMO estado nos dois instantes. O que a sonda pega
    de graça é o caso que mais engana: a árvore mexida e devolvida (ou mexida e
    deixada mexida) enquanto a suíte roda. O ganho grande da mesma reprodução é
    outro, e esse é total: as falhas deixaram de ser SORTEADAS. Antes, testes
    diferentes caíam a cada rodada; depois, TODA rodada vermelha caiu no mesmo
    conjunto de quatro — exatamente a mordida pretendida da mutação viva.
    Vermelho reproduzível é diagnosticável; vermelho sorteado não é.
    """
    if not _ARVORE_CONGELADA:
        return []
    congelada = _ARVORE_CONGELADA[0]
    viva = Path(__file__).resolve().parents[1]
    deltas: list[str] = []
    for copia in sorted(congelada.rglob("*")):
        if not copia.is_file():
            continue
        relativo = copia.relative_to(congelada)
        atual = viva / relativo
        if not atual.is_file():
            deltas.append(f"APAGADO  {relativo}")
            continue
        try:
            if atual.read_bytes() != copia.read_bytes():
                deltas.append(f"MUDADO   {relativo}")
                continue
        except OSError:
            deltas.append(f"ILEGÍVEL {relativo}")
            continue
        if (atual.stat().st_mode & 0o777) != (copia.stat().st_mode & 0o777):
            deltas.append(f"MODO     {relativo}")
    return deltas


@pytest.fixture(scope="session")
def repo_root() -> Path:
    return Path(__file__).resolve().parents[1]


@pytest.fixture(autouse=True)
def _hefesto_fake_env(monkeypatch: pytest.MonkeyPatch, tmp_path: Path) -> None:
    """Ativa HEFESTO_DUALSENSE4UNIX_FAKE=1 e ISOLA os diretórios XDG em todo teste.

    FAKE=1 — garantia defensiva: subsystems que fazem probing de hardware real
    (TouchpadReader enumerando evdev, ex.) devem pular a inicialização quando o
    flag está presente — caso contrário testes em ambiente dev com DualSense
    conectado sofrem latência extra (>60ms) que empurra janelas de teste curtas
    para fora do budget. FakeController já é o padrão nas suítes; o env var apenas
    torna esse contrato explícito para outros módulos consumirem.

    BUG-TEST-CONFIG-LEAK-01 — isola XDG_CONFIG_HOME (e data/cache/state/runtime)
    num tmp por teste. `utils.xdg_paths.config_dir()` resolve via `platformdirs`,
    que respeita `XDG_CONFIG_HOME`; sem isolamento, qualquer teste que sobe o
    Daemon lia o `~/.config/hefesto-dualsense4unix` REAL do dev e herdava as flags
    de sessão (gamepad/mouse/paused), o session.json e os profiles. Numa máquina
    com a emulação de gamepad LIGADA de verdade, o daemon de teste nascia com o
    gamepad ativo e os testes de dispatch de mouse/teclado/hotkey
    (test_poll_loop_evdev_cache, test_keyboard_wire_up) falhavam — enquanto a CI
    (HOME limpo) passava. Isolar torna a suíte hermética e independente do estado
    real do dev. Testes que precisam de config própria continuam livres para
    monkeypatchar `config_dir`/`XDG_CONFIG_HOME` por cima.
    """
    if not os.environ.get("HEFESTO_DUALSENSE4UNIX_FAKE"):
        monkeypatch.setenv("HEFESTO_DUALSENSE4UNIX_FAKE", "1")
    # XDG_RUNTIME_DIR NÃO é isolado de propósito: os testes de single_instance
    # dependem da semântica real do runtime dir (pid/socket, permissões 0700) e
    # quebram sob um tmp. O socket IPC já é isolável por nome via
    # HEFESTO_DUALSENSE4UNIX_IPC_SOCKET_NAME quando um teste precisa.
    #
    # Os dirs ficam sob um subdir dedicado (`.xdg/`) para NÃO colidir com testes
    # que criam `tmp_path / "config"` etc. com `exist_ok=False` na própria fixture
    # (ex.: test_service_install.isolated_systemd_user) — pytest entrega o MESMO
    # tmp_path a todas as fixtures do teste. Testes que setam o próprio
    # XDG_CONFIG_HOME por cima continuam vencendo (este é só o default hermético).
    xdg_root = tmp_path / ".xdg"
    for var, sub in (
        ("XDG_CONFIG_HOME", "config"),
        ("XDG_DATA_HOME", "data"),
        ("XDG_CACHE_HOME", "cache"),
        ("XDG_STATE_HOME", "state"),
    ):
        target = xdg_root / sub
        target.mkdir(parents=True, exist_ok=True)
        monkeypatch.setenv(var, str(target))
    # FIX-PACKAGING-SEED-PARITY-01 — desliga a semeadura automática de presets
    # (profiles.loader._maybe_seed_presets). Sem isto, o PRIMEIRO teste do
    # processo a carregar perfis receberia os JSONs de assets/profiles_default/
    # do repo no seu tmp (o flag once-per-process faria só um teste, dependente
    # da ordem, quebrar asserções de listas exatas). Os testes da semeadura
    # chamam seed_default_presets() com paths injetados ou re-habilitam via
    # monkeypatch (delenv + _seed_attempted=False).
    monkeypatch.setenv("HEFESTO_DUALSENSE4UNIX_SKIP_PRESET_SEED", "1")
    # BROKER-01: aponta o cliente do broker hide-hidraw para um socket
    # INEXISTENTE em TODO teste. Na máquina da mantenedora o broker REAL está
    # de pé em /run/hefesto-hidraw-broker/broker.sock — um teste que
    # resolvesse o default esconderia/abriria hidraw DE VERDADE no meio da
    # suíte. Testes do próprio cliente passam o caminho explicitamente.
    monkeypatch.setenv("HEFESTO_BROKER_SOCKET", str(xdg_root / "no-broker.sock"))
