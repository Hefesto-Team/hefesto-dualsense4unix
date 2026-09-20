"""O nome do pacote tem UM dono, e os dois lados dizem o mesmo.

A-LIBOPUS-TEM-NOME-EM-CADA-CASA-01 (20/09/2026)
===============================================
A frase que pedia a libopus cravava, em TODA máquina, o nome que só o Debian
usa — e o gesto que ela dava era o de atualizar o Hefesto, não o de instalar a
biblioteca. Num Arch, quem a seguisse recebia `target not found` e concluiria
que o produto está quebrado.

O dado certo já existia, em shell, na tabela `_pkg_nome` do `install.sh`. O
lado Python não tinha contraparte — então digitou. **Esta régua é o que impede
os dois de divergirem de novo**, e o preço de não tê-la já está medido: a
frase errada atravessou a casa inteira sem ninguém ver.

POR QUE ELA **LÊ** O SHELL, E NÃO DIGITA OS NOMES
-------------------------------------------------
Uma régua que digitasse os três nomes seria a TERCEIRA cópia do mesmo dado —
exatamente o defeito que esta frente cura. Ela lê o bloco do `install.sh` e o
compara com o dicionário Python, nome por nome, **nos dois sentidos**: um lado
que ganhe um formato sem o outro reprova.

Nenhum nome de pacote é escrito neste arquivo, nem a chave canônica: tudo vem
do dono. Se você precisar digitar um nome aqui para o teste passar, a régua
parou de medir.

O QUE FALTAVA, E CUSTOU TRÊS DEFEITOS VIVOS (20/09/2026)
--------------------------------------------------------
A conferência desta mesma sprint arrancou quinze curas e **três passaram com o
defeito vivo**, pela mesma forma: *a régua se conferia contra a PRÓPRIA
SAÍDA*.

* **Os moldes de Arch e de Debian trocados** — o produto dizia `rode sudo apt
  install opus` num Arch, onde `apt` não existe. Nenhuma asserção olhava o
  GERENCIADOR: cobravam o começo da frase, o NOME do pacote e a ausência do
  conselho de atualizar. A cura é o oráculo que a régua já tinha na mão e
  jogava fora — **o nome da variável de shell de cada família É o nome do
  binário** (:data:`_FORMATO_PARA_BINARIO`).
* **O nome da biblioteca virando nome de pacote inventado** no degrau final. A
  régua montava o esperado com as MESMAS DUAS constantes que a função lê: só
  reprovaria se a função parasse de lê-las, nunca se elas dissessem besteira.
  A cura é afirmar a frase LITERAL que ela aprovou
  (:data:`FRASE_APROVADA_DO_DEGRAU_FINAL`).
* **O degrau final devolvendo o conselho de ATUALIZAR** o Hefesto para
  instalar uma biblioteca — o segundo erro do enunciado da sprint, de volta
  pela porta que ninguém vigiava.

**A frase aprovada é a ÚNICA coisa digitada aqui, e não é dado de pacote:** é
texto de tela, justamente o que nenhum dicionário desta casa é dono de
decidir. Nome de pacote continua vindo do `install.sh`, sempre.
"""
from __future__ import annotations

import re
from pathlib import Path

import pytest

from hefesto_dualsense4unix.integrations import storm_doctor as sd
from tests.unit.fonte_do_instalador import texto_do_instalador

#: A família de pacotes do `install.sh` ↔ o formato do `storm_doctor`. É a
#: ÚNICA tradução que este arquivo faz, e ela não é dado de pacote: é o nome da
#: variável de shell de cada família.
_FAMILIA_PARA_FORMATO = {
    "_apt": sd.FORMATO_DEBIAN,
    "_dnf": sd.FORMATO_FEDORA,
    "_pacman": sd.FORMATO_ARCH,
}

#: O BINÁRIO que cada formato tem de invocar, derivado do mapa acima. O nome
#: da variável de shell de cada família **é** o nome do programa que instala
#: nela — o `install.sh` batizou assim, e por isso este dado não é digitado:
#: sai de :data:`_FAMILIA_PARA_FORMATO` tirando o sublinhado.
#:
#: Sem isto, trocar o molde do Arch pelo do Debian passava verde: as asserções
#: olhavam o começo da frase e o nome do pacote, e `opus` é o mesmo nos dois.
_FORMATO_PARA_BINARIO = {
    formato: familia.removeprefix("_")
    for familia, formato in _FAMILIA_PARA_FORMATO.items()
}

#: A frase que ELA aprovou para o degrau final, palavra por palavra (passo 2 da
#: A-LIBOPUS-TEM-NOME-EM-CADA-CASA-01).
#:
#: **É texto de TELA, não dado de pacote** — por isso pode ser digitada aqui
#: sem virar a terceira cópia de nada. Montá-la a partir das constantes que a
#: própria função lê é o que a fazia passar com a biblioteca rebatizada de
#: pacote inexistente: a régua repetia a conta em vez de conferir o resultado.
FRASE_APROVADA_DO_DEGRAU_FINAL = (
    "instale a libopus pelo gerenciador de pacotes da sua distribuição"
)

#: Os formatos que NÃO têm gerenciador de pacotes assumindo o arquivo. Nestes,
#: a frase não pode nomear pacote nenhum — inventar um é o defeito curado.
_SEM_GERENCIADOR = (
    sd.FORMATO_CHECKOUT,
    sd.FORMATO_FLATPAK,
    sd.FORMATO_NIX,
    sd.FORMATO_DESCONHECIDO,
)

_SEM_MARCA_FLATPAK = Path("/nao/existe/.flatpak-info")
_FORA_DO_NIX = Path("/opt/hefesto/instalado/modulo.py")


def _argumentos_do_formato(formato: str) -> dict[str, object]:
    """Como se força CADA degrau da escada de `formato_desta_instalacao`.

    Nada de variável de ambiente: os quatro parâmetros da função existem para
    isto, e um `Path` de mentira é medição, não palpite.
    """
    if formato == sd.FORMATO_CHECKOUT:
        return {"e_checkout": True}
    if formato == sd.FORMATO_FLATPAK:
        # Um arquivo que existe em toda máquina serve de marca do sandbox.
        return {"e_checkout": False, "marca_flatpak": Path(__file__)}
    base: dict[str, object] = {
        "e_checkout": False,
        "marca_flatpak": _SEM_MARCA_FLATPAK,
    }
    if formato == sd.FORMATO_NIX:
        base["raiz_do_codigo"] = Path("/nix/store/0000-hefesto/modulo.py")
        return base
    base["raiz_do_codigo"] = _FORA_DO_NIX
    dono = None if formato == sd.FORMATO_DESCONHECIDO else formato
    base["consultar_dono"] = lambda _caminho, _dono=dono: _dono
    return base


def nomes_do_instalador(canonico: str, texto: str | None = None) -> dict[str, str]:
    """O que o `install.sh` diz que esta dependência se chama, por formato.

    Lê a arm `<canonico>)` da tabela `_pkg_nome`. `texto` existe para a
    MORDIDA — alimentar um instalador mutilado e ver esta régua reprovar sem
    tocar no arquivo de verdade.

    Família com valor vazio fica de fora: no `install.sh`, vazio quer dizer
    *"não tenho nome para isto aqui"*, e isso não é um nome.
    """
    inteiro = texto_do_instalador() if texto is None else texto
    inicio = inteiro.find("_pkg_nome() {")
    assert inicio != -1, "a tabela `_pkg_nome` sumiu do instalador"
    corpo = inteiro[inicio:]
    fim = corpo.find("\n    esac")
    assert fim != -1, "o `case` da tabela `_pkg_nome` não fecha"
    corpo = corpo[:fim]

    arm = re.search(
        rf"^[ \t]*{re.escape(canonico)}\)[ \t]*$\n(.*?);;",
        corpo,
        re.DOTALL | re.MULTILINE,
    )
    assert arm is not None, (
        f"o instalador não tem arm para {canonico!r} — o dono do nome mudou de "
        "lugar, e o lado Python ficou sozinho"
    )
    achados = dict(re.findall(r'(_apt|_dnf|_pacman)="([^"]*)"', arm.group(1)))
    return {
        _FAMILIA_PARA_FORMATO[familia]: nome
        for familia, nome in achados.items()
        if nome
    }


#: As dependências que o lado Python declara. A lista vem DO DONO: acrescentar
#: uma no `storm_doctor` põe esta régua em cima dela sem editar este arquivo.
DEPENDENCIAS = sorted(sd.PACOTE_POR_FORMATO)


def test_ha_ao_menos_uma_dependencia_a_medir() -> None:
    """Trava contra vacuidade: uma régua sobre lista vazia passa por nada."""
    assert DEPENDENCIAS, "PACOTE_POR_FORMATO está vazio — nada seria medido"


@pytest.mark.parametrize("canonico", DEPENDENCIAS)
def test_os_dois_lados_dizem_o_mesmo_nome_em_cada_formato(canonico: str) -> None:
    """O `install.sh` e o `storm_doctor` não podem divergir em nada.

    A igualdade de dicionários mede os DOIS sentidos de uma vez: formato a
    mais de um lado, formato a menos, ou o mesmo formato com nome diferente.
    """
    do_shell = nomes_do_instalador(canonico)
    do_python = sd.PACOTE_POR_FORMATO[canonico]
    assert do_python == do_shell, (
        f"os dois donos do nome de {canonico!r} divergiram — "
        f"install.sh diz {do_shell}, storm_doctor diz {do_python}"
    )


@pytest.mark.parametrize("canonico", DEPENDENCIAS)
def test_toda_dependencia_tem_nome_humano_para_o_degrau_final(canonico: str) -> None:
    """Sem nome humano, o degrau final levanta `KeyError` na cara de quem lê."""
    assert canonico in sd.NOME_DA_DEPENDENCIA


@pytest.mark.parametrize("canonico", DEPENDENCIAS)
def test_o_gesto_nomeia_o_pacote_certo_em_cada_familia(canonico: str) -> None:
    """Arch, Fedora e Debian: o gesto INSTALA, com o nome do dono e no binário
    que existe naquela máquina."""
    do_shell = nomes_do_instalador(canonico)
    for formato, esperado in do_shell.items():
        frase = sd.gesto_de_instalar(canonico, **_argumentos_do_formato(formato))
        assert frase.startswith("rode "), (
            f"{formato}: a frase tem de ser um GESTO, e veio {frase!r}"
        )
        assert re.search(rf"\b{re.escape(esperado)}\b", frase), (
            f"{formato}: o gesto não nomeia o pacote que o instalador declara "
            f"({esperado!r}) — veio {frase!r}"
        )
        assert "install.sh" not in frase and "Hefesto" not in frase, (
            f"{formato}: o gesto de INSTALAR virou o de atualizar o produto — "
            f"veio {frase!r}"
        )
        meu = _FORMATO_PARA_BINARIO[formato]
        assert re.search(rf"\b{re.escape(meu)}\b", frase), (
            f"{formato}: o gesto não chama {meu!r}, que é o único instalador "
            f"que existe nesta família — veio {frase!r}"
        )
        alheios = sorted(
            outro
            for outro_formato, outro in _FORMATO_PARA_BINARIO.items()
            if outro_formato != formato
            and re.search(rf"\b{re.escape(outro)}\b", frase)
        )
        assert not alheios, (
            f"{formato}: o gesto manda rodar {alheios!r}, de outra família — "
            f"num {formato} esse comando não existe. Veio {frase!r}"
        )


@pytest.mark.parametrize("canonico", DEPENDENCIAS)
def test_o_degrau_final_nao_inventa_nome_de_pacote(canonico: str) -> None:
    """Checkout, Flatpak, Nix e o formato que ninguém assume.

    Nenhum deles tem nome de pacote em canto nenhum desta casa. A frase nomeia
    a biblioteca e manda quem lê ao gerenciador da PRÓPRIA distribuição.
    """
    do_shell = nomes_do_instalador(canonico)
    generica = sd.FRASE_DE_INSTALAR_GENERICA.format(
        biblioteca=sd.NOME_DA_DEPENDENCIA[canonico]
    )
    for formato in _SEM_GERENCIADOR:
        frase = sd.gesto_de_instalar(canonico, **_argumentos_do_formato(formato))
        assert frase == generica, f"{formato}: veio {frase!r}"
        for nome in do_shell.values():
            assert not re.search(rf"\b{re.escape(nome)}\b", frase), (
                f"{formato}: a frase crava o pacote de outra distribuição "
                f"({nome!r}) — veio {frase!r}"
            )
        # O degrau final é onde o conselho de ATUALIZAR voltava pela porta dos
        # fundos, e as duas travas abaixo têm donos diferentes de propósito.
        assert "install.sh" not in frase and "Hefesto" not in frase, (
            f"{formato}: o degrau final manda mexer no PRODUTO em vez de "
            f"instalar a biblioteca — veio {frase!r}"
        )
        voltou = sorted(
            gesto for gesto in sd.GESTO_DE_ATUALIZAR.values() if gesto in frase
        )
        assert not voltou, (
            f"{formato}: o degrau final repete o conselho de atualizar "
            f"({voltou!r}) — quem o dita é GESTO_DE_ATUALIZAR, e ele responde "
            f"outra pergunta. Veio {frase!r}"
        )


def test_o_degrau_final_diz_a_frase_que_ela_aprovou() -> None:
    """O que CHEGA À TELA, conferido contra a frase dela — não contra a conta.

    O teste acima monta o esperado com as mesmas duas constantes que
    `gesto_de_instalar` lê, e por isso não distingue um molde certo de um
    molde que diga besteira. Aqui o esperado tem outra fonte: ela.
    """
    frases = {
        sd.gesto_de_instalar(canonico, **_argumentos_do_formato(formato))
        for canonico in DEPENDENCIAS
        for formato in _SEM_GERENCIADOR
    }
    assert FRASE_APROVADA_DO_DEGRAU_FINAL in frases, (
        "o degrau final deixou de dizer a frase aprovada — saíram "
        f"{sorted(frases)!r}"
    )


def test_os_dois_dicionarios_do_python_concordam() -> None:
    """A guarda que escolhe entre o molde e o degrau final não pode calar.

    `gesto_de_instalar` só usa o molde quando TEM molde e TEM pacote; um
    formato com nome de pacote e sem molde cairia no degrau final sem ninguém
    perceber, e um molde a mais nunca seria exercitado por régua nenhuma.
    """
    assert set(sd.GESTO_DE_INSTALAR) == set(_FAMILIA_PARA_FORMATO.values()), (
        "os moldes de instalar e as famílias do instalador divergiram — "
        f"moldes {sorted(sd.GESTO_DE_INSTALAR)}, "
        f"famílias {sorted(_FAMILIA_PARA_FORMATO.values())}"
    )
    for canonico in DEPENDENCIAS:
        sem_molde = set(sd.PACOTE_POR_FORMATO[canonico]) - set(sd.GESTO_DE_INSTALAR)
        assert not sem_molde, (
            f"{canonico!r} tem nome de pacote em {sorted(sem_molde)} e nenhum "
            "molde que o use — a frase cai calada no degrau final"
        )


def test_os_sete_formatos_sao_medidos_e_nenhum_fica_de_fora() -> None:
    """A escada inteira, e o degrau forçado é o degrau medido.

    Sem isto, um erro no forçamento faria os testes acima medirem o mesmo
    degrau sete vezes e darem verde sobre um formato só.
    """
    todos = (*_FAMILIA_PARA_FORMATO.values(), *_SEM_GERENCIADOR)
    assert len(set(todos)) == 7
    for formato in todos:
        medido = sd.formato_desta_instalacao(**_argumentos_do_formato(formato))
        assert medido == formato, f"quis forçar {formato} e caiu em {medido}"


@pytest.mark.parametrize("canonico", DEPENDENCIAS)
def test_a_regua_reprova_quando_o_instalador_perde_uma_familia(canonico: str) -> None:
    """A MORDIDA embutida, do lado do SHELL.

    Régua que só sabe reprovar o lado Python não mede divergência. Aqui o
    instalador é mutilado EM MEMÓRIA — nenhum arquivo é tocado — e o que se
    exige é que a comparação acuse.

    **A mordida também tem de morder.** Enquanto esta função pulava a família
    cuja substituição não mudava nada, um instalador que trocasse o nome das
    variáveis deixava as três passarem em branco e o teste terminava verde sem
    ter mutilado coisa alguma.
    """
    inteiro = texto_do_instalador()
    for familia in _FAMILIA_PARA_FORMATO:
        mutilado = re.sub(rf'{familia}="[^"]*"', f'{familia}=""', inteiro)
        assert mutilado != inteiro, (
            f"a mordida não mordeu: não há o que esvaziar para {familia} no "
            "instalador, e este teste passaria por nada"
        )
        assert nomes_do_instalador(canonico, texto=mutilado) != sd.PACOTE_POR_FORMATO[
            canonico
        ], f"sem {familia} no instalador, a régua continuou passando"
