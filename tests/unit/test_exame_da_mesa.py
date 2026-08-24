"""O exame da mesa mede o que diz medir — e não deixa o selo mentir.

Sem GTK, sem root e sem encostar em `/sys`: cada checagem recebe as raízes por
argumento, e é isso que estes testes injetam. A última função deste arquivo é a
que protege a foto — ela prova que, com as raízes injetadas, NENHUM caminho
real do sistema é aberto.

A MORDIDA QUE IMPORTA é `test_um_unico_problema_derruba_o_selo_verde`: trocar um
item para `problema` tem de derrubar o topo de verde para vermelho. Sem ela o
arquivo seria carimbo, porque tudo o mais aqui é aritmética de estado.
"""
from __future__ import annotations

from collections.abc import Sequence
from pathlib import Path

from hefesto_dualsense4unix.integrations import exame_da_mesa as exame_mod
from hefesto_dualsense4unix.integrations.exame_da_mesa import (
    ESTADO_ATENCAO,
    ESTADO_CERTO,
    ESTADO_NAO_SEI,
    ESTADO_PROBLEMA,
    Item,
    energia_das_portas,
    energia_do_radio,
    exame,
    pareamentos,
    suporte_ao_controle,
    veredito,
    vizinhanca_das_portas,
)

#: Um endereço de rádio mascarado no padrão da casa — octetos 4 e 5 zerados,
#: e o prefixo na faixa de documentação que o `scripts/check_test_data.sh`
#: reconhece.
#: Ele existe aqui para PROVAR que não vaza para a frase de tela — e é por isso
#: que ele não pode ser um MAC de verdade nem no teste.
MAC_DE_MENTIRA = "AA:BB:CC:00:00:FF"


def _bancada_do_radio(tmp_path: Path, valor: str | None, *, com_conf: bool) -> dict:
    """Monta a bancada da checagem de energia do rádio em `tmp_path`."""
    parametro = tmp_path / "enable_autosuspend"
    if valor is not None:
        parametro.write_text(valor + "\n", encoding="utf-8")
    conf = tmp_path / "hefesto-btusb-no-autosuspend.conf"
    if com_conf:
        conf.write_text("options btusb enable_autosuspend=0\n", encoding="utf-8")
    return {"parametro": parametro, "conf": conf}


def _porta(raiz: Path, nome: str, controle: str) -> None:
    """Cria uma porta USB de mentira, com `power/control` e `idVendor`."""
    no = raiz / nome
    (no / "power").mkdir(parents=True)
    (no / "power" / "control").write_text(controle + "\n", encoding="utf-8")
    (no / "idVendor").write_text("054c\n", encoding="utf-8")


# --- energia do rádio -------------------------------------------------------


def test_energia_do_radio_fica_certa_com_o_autosuspend_desligado(
    tmp_path: Path,
) -> None:
    """`enable_autosuspend=N` é o estado que o conf do Hefesto produz."""
    item = energia_do_radio(**_bancada_do_radio(tmp_path, "N", com_conf=True))

    assert item.estado == ESTADO_CERTO
    assert item.cura is None


def test_energia_do_radio_pede_atencao_sem_a_regra_no_lugar(tmp_path: Path) -> None:
    """Módulo com autosuspend LIGADO e sem o conf: o rádio pode dormir.

    Mordida: trocar o `return` deste ramo por `ESTADO_CERTO` faz o teste
    reprovar em `estado == ESTADO_ATENCAO` — e é o ramo que o doctor marca
    com `warn` (`scripts/doctor.sh:2355`).
    """
    item = energia_do_radio(**_bancada_do_radio(tmp_path, "Y", com_conf=False))

    assert item.estado == ESTADO_ATENCAO
    assert item.cura is not None
    assert "sudo" not in (item.cura + item.porque).lower()


def test_energia_do_radio_avisa_que_a_regra_so_vale_no_proximo_encaixe(
    tmp_path: Path,
) -> None:
    """Conf no disco e módulo com o valor antigo: a cura existe e não vale AINDA.

    Este é o ramo que engana. Verde aqui diria que o rádio não dorme enquanto
    ele ainda dorme — e é o que o doctor evita chamando de `info`.
    """
    item = energia_do_radio(**_bancada_do_radio(tmp_path, "Y", com_conf=True))

    assert item.estado == ESTADO_ATENCAO
    assert "encaixe" in (item.cura or "")


def test_energia_do_radio_nao_sabe_sem_adaptador_ligado(tmp_path: Path) -> None:
    """Sem o parâmetro no sysfs não há módulo carregado — logo, nada medido."""
    item = energia_do_radio(**_bancada_do_radio(tmp_path, None, com_conf=True))

    assert item.estado == ESTADO_NAO_SEI


# --- energia das portas -----------------------------------------------------


def test_energia_das_portas_fica_certa_com_todas_em_on(tmp_path: Path) -> None:
    _porta(tmp_path, "1-1", "on")
    _porta(tmp_path, "1-2", "on")

    item = energia_das_portas(raiz=tmp_path)

    assert item.estado == ESTADO_CERTO
    assert "2" in item.porque


def test_energia_das_portas_pede_atencao_com_uma_em_auto(tmp_path: Path) -> None:
    """Uma porta em `auto` é queda na certa para o que estiver nela.

    E a frase conta QUANTAS, nunca QUAIS: o doctor imprime `idVendor` e nome do
    produto (`scripts/doctor.sh:2250-2252`), e isto aqui vai para uma tela que o
    retrato das abas versiona.
    """
    _porta(tmp_path, "1-1", "on")
    _porta(tmp_path, "1-2", "auto")

    item = energia_das_portas(raiz=tmp_path)

    assert item.estado == ESTADO_ATENCAO
    assert "054c" not in item.porque
    assert "1-2" not in item.porque


def test_energia_das_portas_nao_sabe_sem_porta_legivel(tmp_path: Path) -> None:
    """Zero portas legíveis não é "está tudo bem": é não ter medido nada."""
    item = energia_das_portas(raiz=tmp_path / "nao-existe")

    assert item.estado == ESTADO_NAO_SEI


def test_energia_das_portas_ignora_interface_usb(tmp_path: Path) -> None:
    """`1-3:1.0` é interface, não aparelho — ela não tem `idVendor`.

    Sem este filtro o denominador dobraria ou triplicaria, e a frase "nenhuma
    das N portas" passaria a contar o que não é porta.
    """
    _porta(tmp_path, "1-1", "on")
    interface = tmp_path / "1-1:1.0" / "power"
    interface.mkdir(parents=True)
    (interface / "control").write_text("auto\n", encoding="utf-8")

    item = energia_das_portas(raiz=tmp_path)

    assert item.estado == ESTADO_CERTO
    assert "1 portas" in item.porque or "das 1" in item.porque


# --- suporte ao controle ----------------------------------------------------


def test_suporte_ao_controle_le_o_modulo_carregado(tmp_path: Path) -> None:
    modulos = tmp_path / "modules"
    modulos.write_text(
        "hid_sony 40960 0 - Live 0x0000\nhid_playstation 45056 0 - Live 0x0000\n",
        encoding="utf-8",
    )

    item = suporte_ao_controle(
        modulos=modulos, diretorio_do_modulo=tmp_path / "nao-existe"
    )

    assert item.estado == ESTADO_CERTO


def test_suporte_ao_controle_aceita_o_kernel_com_o_driver_embutido(
    tmp_path: Path,
) -> None:
    """Driver embutido não aparece em `/proc/modules` e mesmo assim funciona."""
    embutido = tmp_path / "hid_playstation"
    embutido.mkdir()

    item = suporte_ao_controle(
        modulos=tmp_path / "modules-vazio", diretorio_do_modulo=embutido
    )

    assert item.estado == ESTADO_CERTO


def test_suporte_ao_controle_nao_confunde_prefixo(tmp_path: Path) -> None:
    """`hid_playstation_x` não é o `hid_playstation`.

    Mordida verificada em 22/08/2026: tirei o espaço de
    `linha.startswith("hid_playstation ")` e este teste reprovou — era assim que
    um módulo homônimo daria verde. A saída do pytest foi
    `assert 'certo' == 'atencao'`.  # (noqa-acento): saída literal do pytest
    """
    modulos = tmp_path / "modules"
    modulos.write_text("hid_playstation_falso 4096 0 - Live 0x0\n", encoding="utf-8")

    item = suporte_ao_controle(
        modulos=modulos, diretorio_do_modulo=tmp_path / "nao-existe"
    )

    assert item.estado == ESTADO_ATENCAO


# --- pareamentos ------------------------------------------------------------


def _busctl_de_mentira(
    respostas: dict[str, str | None],
) -> tuple[list[Sequence[str]], object]:
    """Um `busctl` falso que devolve o que o teste mandar, e anota as chamadas."""
    chamadas: list[Sequence[str]] = []

    def _rodar(argumentos: Sequence[str]) -> str | None:
        chamadas.append(list(argumentos))
        if argumentos[0] == "tree":
            return respostas.get("tree")
        return respostas.get(argumentos[-1])

    return chamadas, _rodar


def test_pareamentos_nao_sabe_sem_a_ferramenta_e_nunca_reprova() -> None:
    """Sem `busctl` no caminho, o exame diz que não sabe — nunca `problema`.

    É o precedente do próprio doctor, que devolve `info` (não falha) quando o
    `busctl` falta (`scripts/doctor.sh:3214`).
    """
    item = pareamentos(executar=lambda _argumentos: None)

    assert item.estado == ESTADO_NAO_SEI
    assert item.estado != ESTADO_PROBLEMA


def test_pareamentos_sem_nenhum_dispositivo_nao_tem_meio_salvo() -> None:
    """Árvore do BlueZ sem device: não há pareamento pela metade possível."""
    _chamadas, rodar = _busctl_de_mentira({"tree": "/\n/org\n/org/bluez\n"})

    item = pareamentos(executar=rodar)

    assert item.estado == ESTADO_CERTO


def test_pareamentos_acha_o_pela_metade_e_nao_mostra_o_endereco() -> None:
    """`Paired: yes` com `Bonded: no` é problema — e o MAC NÃO vai para a tela.

    Mordida verificada em 22/08/2026: pus o endereço dentro do `porque`, que é
    o que o `fail` do doctor faz em `scripts/doctor.sh:3227`, e este teste
    reprovou com `'AA:BB:CC:00:00:FF' not in ...`. Sem ele o endereço dela iria
    para a tela e, pelo retrato das abas, para um PNG versionado.
    """
    caminho = "/org/bluez/hci0/dev_" + MAC_DE_MENTIRA.replace(":", "_")
    _chamadas, rodar = _busctl_de_mentira(
        {"tree": f"/\n/org/bluez\n{caminho}\n", "Paired": "b true", "Bonded": "b false"}
    )

    item = pareamentos(executar=rodar)

    assert item.estado == ESTADO_PROBLEMA
    texto = item.porque + (item.cura or "")
    assert MAC_DE_MENTIRA not in texto
    assert "AA_BB" not in texto
    assert "sudo" not in texto.lower()


def test_pareamentos_inteiro_fica_certo() -> None:
    caminho = "/org/bluez/hci0/dev_" + MAC_DE_MENTIRA.replace(":", "_")
    _chamadas, rodar = _busctl_de_mentira(
        {"tree": f"/\n{caminho}\n", "Paired": "b true", "Bonded": "b true"}
    )

    item = pareamentos(executar=rodar)

    assert item.estado == ESTADO_CERTO


def test_pareamentos_ignora_os_filhos_do_dispositivo_na_arvore() -> None:
    """`.../dev_XX/sep1` é endpoint de áudio, não é controle.

    O BlueZ pendura filhos sob cada dispositivo, e eles não têm `Paired` nem
    `Bonded`. Contá-los como dispositivos faria um pareamento INTEIRO sair como
    "não deu para conferir", porque os filhos entrariam todos em `sem_resposta`.

    Mordida verificada em 22/08/2026: troquei o recorte por
    `"/dev_" in linha and linha.startswith("/org/bluez/hci")`, que é a versão
    sem âncora de fim, e este teste reprovou com `assert 'nao_sei' == 'certo'`.
    """
    caminho = "/org/bluez/hci0/dev_" + MAC_DE_MENTIRA.replace(":", "_")
    _chamadas, rodar = _busctl_de_mentira(
        {
            "tree": f"/\n{caminho}\n{caminho}/sep1\n{caminho}/fd0\n",
            "Paired": "b true",
            "Bonded": "b true",
        }
    )

    item = pareamentos(executar=rodar)

    assert item.estado == ESTADO_CERTO
    assert "1 pareamento" in item.porque or "dos 1" in item.porque


def test_pareamentos_nao_sabe_quando_o_bluez_nao_tem_bonded() -> None:
    """Em BlueZ anterior ao 5.65 a propriedade `Bonded` NEM EXISTE.

    `scripts/doctor.sh:3157-3158` documenta isso. Ausência dela não é "está
    tudo bem": é esta máquina não saber responder.
    """
    caminho = "/org/bluez/hci0/dev_" + MAC_DE_MENTIRA.replace(":", "_")
    _chamadas, rodar = _busctl_de_mentira(
        {"tree": f"/\n{caminho}\n", "Paired": "b true", "Bonded": None}
    )

    item = pareamentos(executar=rodar)

    assert item.estado == ESTADO_NAO_SEI


# --- vizinhança das portas --------------------------------------------------


def test_vizinhanca_nao_sabe_quando_a_leitura_da_mesa_falha() -> None:
    """Leitura quebrada vira "não sei", nunca verde.

    Mordida: trocar o `except` por um `return` de `ESTADO_CERTO` faria a tela
    afirmar ausência de ruído sem ter olhado.
    """

    def _quebrada() -> Sequence[object]:
        raise OSError("sysfs fora do ar")

    item = vizinhanca_das_portas(leitura=_quebrada)

    assert item.estado == ESTADO_NAO_SEI


def test_vizinhanca_apertada_e_laranja_e_nao_vermelha() -> None:
    """Porta vizinha ruim atrapalha e tem volta — vermelho é para o que destrói."""
    item = vizinhanca_das_portas(leitura=lambda: [("a", "b"), ("c", "d")])

    assert item.estado == ESTADO_ATENCAO
    assert "2 par" in item.porque


def test_vizinhanca_livre_fica_certa() -> None:
    item = vizinhanca_das_portas(leitura=list)

    assert item.estado == ESTADO_CERTO


def test_vizinhanca_apertada_pede_a_declaracao_quando_a_mesa_esta_vazia() -> None:
    """T3, CONFIGURAÇÕES-FECHA-01: laranja + declaração vazia = a linha PEDE.

    Mordida: comente a leitura de `altura_da_antena`/`linha_de_visada` dentro
    de `vizinhanca_das_portas` (force `nada_declarado = True` sempre) e as duas
    curas abaixo viram byte a byte iguais — é o que este teste reprova.
    """
    vazio = vizinhanca_das_portas(leitura=lambda: [("a", "b")])
    declarado = vizinhanca_das_portas(
        leitura=lambda: [("a", "b")], altura_da_antena="abaixo"
    )

    assert vazio.cura != declarado.cura
    assert vazio.cura is not None and "declare a altura da antena" in vazio.cura
    assert declarado.cura is not None and "declare" not in declarado.cura


def test_exame_repassa_a_declaracao_da_mesa_para_a_vizinhanca(tmp_path: Path) -> None:
    """`exame()` não lê o `maquina.json` (é 100% stdlib) — só repassa."""
    itens = exame(
        leitura_da_vizinhanca=lambda: [("a", "b")],
        altura_da_antena=None,
        linha_de_visada="livre",
        raiz_usb=tmp_path,
    )
    vizinhanca = next(i for i in itens if i.chave == "vizinhanca_das_portas")

    assert vizinhanca.cura is not None
    assert "declare" not in vizinhanca.cura


# --- o veredito, que é o selo do topo ---------------------------------------


def _itens(*estados: str) -> list[Item]:
    return [
        Item(chave=f"c{i}", rotulo=f"Linha {i}", estado=estado, porque="—")
        for i, estado in enumerate(estados)
    ]


def test_veredito_verde_so_com_tudo_certo() -> None:
    assert veredito(_itens(ESTADO_CERTO, ESTADO_CERTO)) == ESTADO_CERTO


def test_um_unico_problema_derruba_o_selo_verde() -> None:
    """A MORDIDA. Um item em `problema` derruba o topo de verde para vermelho.

    Esta é a resposta escrita ao `6c86e295` e à cicatriz de
    `scripts/doctor.sh:1586-1590`: *"o dano não é errar um diagnóstico: é a tela
    ensinar que verde-e-vermelho juntos são normais por aqui"*. A casa pagou
    duas vezes em agosto.

    Mordida verificada em 22/08/2026: troquei o laço de `veredito()` para
    devolver `ESTADO_CERTO` quando a MAIORIA dos itens está certa — que é
    exatamente o raciocínio que produz verde sobre vermelho — e este teste
    reprovou com `assert 'certo' == 'problema'`. Devolvi a escada de gravidade.
    """
    verdes = _itens(*[ESTADO_CERTO] * 5)
    assert veredito(verdes) == ESTADO_CERTO

    com_um_problema = [*verdes[:-1], Item("x", "Linha X", ESTADO_PROBLEMA, "—")]
    assert veredito(com_um_problema) == ESTADO_PROBLEMA


def test_uma_atencao_impede_o_verde() -> None:
    assert veredito(_itens(ESTADO_CERTO, ESTADO_ATENCAO)) == ESTADO_ATENCAO


def test_um_nao_sei_tambem_impede_o_verde() -> None:
    """"Está tudo certo" sobre uma linha não medida é a mesma mentira.

    Mordida verificada em 22/08/2026: tirei `ESTADO_NAO_SEI` da escada de
    `veredito()` e este teste reprovou com `assert 'certo' == 'nao_sei'`.
    """
    assert veredito(_itens(ESTADO_CERTO, ESTADO_NAO_SEI)) == ESTADO_NAO_SEI


def test_problema_vence_atencao_e_nao_sei() -> None:
    assert (
        veredito(_itens(ESTADO_NAO_SEI, ESTADO_ATENCAO, ESTADO_PROBLEMA))
        == ESTADO_PROBLEMA
    )


def test_exame_vazio_nao_e_verde() -> None:
    assert veredito([]) == ESTADO_NAO_SEI


# --- o exame inteiro --------------------------------------------------------


def test_o_exame_devolve_as_cinco_linhas_na_ordem_da_tela(tmp_path: Path) -> None:
    """A ordem é a do desenho aprovado, e trocar aqui troca a tela."""
    itens = exame(
        **_radio_e_portas(tmp_path),
        executar_busctl=lambda _a: None,
        leitura_da_vizinhanca=list,
    )

    assert [item.chave for item in itens] == [
        "energia_do_radio",
        "energia_das_portas",
        "pareamentos",
        "suporte_ao_controle",
        "vizinhanca_das_portas",
    ]


def test_o_censo_carrega_o_veredito_e_sobrevive_ao_json(tmp_path: Path) -> None:
    """A forma que o `doctor.sh` consome: itens mais o veredito, já derivado."""
    import json

    itens = exame(
        **_radio_e_portas(tmp_path),
        executar_busctl=lambda _a: None,
        leitura_da_vizinhanca=list,
    )
    censo = json.loads(json.dumps(exame_mod.censo(itens), ensure_ascii=False))

    assert censo["veredito"] == veredito(itens)
    assert len(censo["itens"]) == 5
    assert set(censo["itens"][0]) == {"chave", "rotulo", "estado", "porque", "cura"}


def _radio_e_portas(tmp_path: Path) -> dict:
    """Bancada mínima para `exame()` — todas as raízes dentro de `tmp_path`."""
    bancada = _bancada_do_radio(tmp_path / "radio", None, com_conf=False)
    (tmp_path / "radio").mkdir(parents=True, exist_ok=True)
    portas = tmp_path / "usb"
    portas.mkdir()
    _porta(portas, "1-1", "on")
    return {
        "parametro_do_radio": bancada["parametro"],
        "conf_do_radio": bancada["conf"],
        "raiz_usb": portas,
        "modulos": tmp_path / "modules-vazio",  # (noqa-acento): nome de argumento
        "diretorio_do_modulo": tmp_path / "sem-modulo",
    }


def test_com_as_raizes_injetadas_nada_do_sistema_real_e_lido(
    tmp_path: Path, monkeypatch
) -> None:
    """A proteção da foto: com bancada falsa, `/sys`, `/etc` e `/proc` ficam intactos.

    O `scripts/gui-captura/retratar_abas.py` gera PNGs que entram em
    `docs/usage/assets/` sem revisão humana, e nenhum portão de anonimato varre
    imagem. A defesa por construção é esta: se toda leitura entra por argumento,
    a foto injeta bancada e não há como a máquina dela aparecer.

    Mordida verificada em 22/08/2026: troquei o default de `raiz_usb` dentro de
    `energia_das_portas` por uma constante de módulo apontando para
    `/sys/bus/usb/devices` e ignorando o argumento — este teste reprovou
    listando `/sys/bus/usb/devices` entre os caminhos abertos.
    """
    abertos: list[str] = []
    original_texto = Path.read_text
    original_lista = Path.iterdir
    original_dir = Path.is_dir
    original_arquivo = Path.is_file
    original_existe = Path.exists

    def _anotar(caminho: Path) -> None:
        abertos.append(str(caminho))

    monkeypatch.setattr(
        Path,
        "read_text",
        lambda self, *a, **k: (_anotar(self), original_texto(self, *a, **k))[1],
    )
    monkeypatch.setattr(
        Path, "iterdir", lambda self: (_anotar(self), original_lista(self))[1]
    )
    monkeypatch.setattr(
        Path, "is_dir", lambda self: (_anotar(self), original_dir(self))[1]
    )
    monkeypatch.setattr(
        Path, "is_file", lambda self: (_anotar(self), original_arquivo(self))[1]
    )
    monkeypatch.setattr(
        Path, "exists", lambda self: (_anotar(self), original_existe(self))[1]
    )

    exame(
        **_radio_e_portas(tmp_path),
        executar_busctl=lambda _a: None,
        leitura_da_vizinhanca=list,
    )

    intrusos = [
        c for c in abertos if c.startswith(("/sys", "/etc", "/proc", "/var/lib"))
    ]
    assert not intrusos, f"o exame leu a máquina real: {intrusos}"


def test_as_chaves_da_tela_sao_exatamente_as_do_exame() -> None:
    """As cinco linhas desenhadas casam com as cinco que o exame devolve.

    `PainelDoExame.aplicar` pinta cada item procurando a linha PELA CHAVE, e
    quando não acha ela simplesmente pula (`if etiqueta is None: continue`).
    A tolerância está certa — um item a mais não pode derrubar a aba —, mas ela
    também engole erro de digitação: a linha fica no estado "ainda não olhei",
    cinza, para sempre, sem erro e sem log.

    Aconteceu em 22/08/2026, e não no produto: o `retratar_abas.py` montou o
    exame de bancada com `chave="vizinhanca"` em vez de
    `chave="vizinhanca_das_portas"`, e a foto que ia para a documentação saiu
    com quatro linhas verdes e a quinta apagada. As chaves vivem em dois
    arquivos e nada as amarrava.

    Mordida: troquei `vizinhanca_das_portas` por `vizinhanca` na lista da tela e
    o teste reprovou nomeando as duas diferenças.
    """
    from hefesto_dualsense4unix.app.actions.config.secao_exame import PainelDoExame

    da_tela = {chave for chave, _rotulo in PainelDoExame._linhas_do_desenho()}
    do_exame = {
        item.chave
        for item in exame_mod.exame(
            parametro_do_radio=Path("/bancada/nao-existe"),
            conf_do_radio=Path("/bancada/nao-existe"),
            raiz_usb=Path("/bancada/nao-existe"),
            modulos=Path("/bancada/nao-existe"),
            diretorio_do_modulo=Path("/bancada/nao-existe"),
            executar_busctl=lambda _argumentos: None,
            leitura_da_vizinhanca=list,
        )
    }

    assert da_tela == do_exame, (
        "as chaves da tela e as do exame divergiram — a linha órfã fica cinza "
        f"para sempre. Só na tela: {sorted(da_tela - do_exame)}; só no exame: "
        f"{sorted(do_exame - da_tela)}"
    )
