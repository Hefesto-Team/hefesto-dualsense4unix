"""SOM-04 — o som que confirma e o botão que manda o áudio para o controle.

Duas entregas, uma raiz: **o registrador de volume do DualSense não tem
leitura**. Depois de mover o controle deslizante nada na tela pode confirmar
que a mudança valeu, porque o número exibido é o que NÓS mandamos. O som é a
leitura que falta — e um som que sai no lugar errado é pior que nenhum som.

O FATO que este arquivo inteiro defende, medido nesta bancada em 01/08/2026::

    $ paplay --device=nao_existe_mesmo bell.oga ; echo $?
    0
    $ pw-play --target=nao_existe_mesmo bell.oga ; echo $?
    0

Os dois tocadores aceitam sink inexistente, saem com ZERO e tocam no sink
PADRÃO. Com o padrão dela no HDMI, a "confirmação do alto-falante do controle"
sairia pela televisão. Por isso a guarda da lista viva de sinks
(:func:`audio_saida.tocar_confirmacao`) é a cura central, e há um teste só
para ela.

Cada teste diz no docstring qual é a MORDIDA — o que arrancar do produto para
vê-lo em vermelho. Este arquivo não precisa de GTK: mede o motor, não a tela.
A fiação nos widgets é aferida em `test_status_som_04_rota.py`.
"""

from __future__ import annotations

from typing import Any

import pytest

from hefesto_dualsense4unix.app import audio_saida
from hefesto_dualsense4unix.app.audio_saida import (
    MOTIVO_DESLIGADO,
    MOTIVO_FALHOU,
    MOTIVO_OCUPADO,
    MOTIVO_SAIDA_MUDA,
    MOTIVO_SEM_ARQUIVO,
    MOTIVO_SEM_SINK,
    MOTIVO_SEM_TOCADOR,
    MOTIVO_TOCOU,
    RECADOS,
    TEXTO_ROTA_PARA_O_CONTROLE,
    TEXTO_ROTA_VOLTAR,
    EstadoDaRota,
    RotaDeSaida,
    acao_da_rota,
    apelido_do_sink,
    argv_do_tocador,
    arquivo_de_confirmacao,
    nomes_de_sinks,
    sink_padrao_da_saida,
    som_ligado,
    tocar_confirmacao,
)

#: Os nomes REAIS desta máquina, copiados de `pactl list sinks short` em
#: 01/08/2026. Nomes inventados esconderiam o detalhe que importa: o sufixo
#: `-00` do controle é desempate posicional do PipeWire, não identidade.
SINK_CONTROLE = (
    "alsa_output.usb-Sony_Interactive_Entertainment_DualSense_Wireless_"
    "Controller-00.analog-surround-40"
)
SINK_HDMI = "alsa_output.pci-0000_0a_00.1.hdmi-stereo"
SINK_SPDIF = "alsa_output.pci-0000_0c_00.4.iec958-stereo"

LISTA_DE_SINKS = (
    f"59\t{SINK_CONTROLE}\tPipeWire\ts16le 4ch 48000Hz\tSUSPENDED\n"
    f"61\t{SINK_SPDIF}\tPipeWire\ts32le 2ch 48000Hz\tSUSPENDED\n"
    f"9256\t{SINK_HDMI}\tPipeWire\ts16le 2ch 48000Hz\tSUSPENDED\n"
)


class _Pactl:
    """Dublê do `pactl`: responde leituras e ANOTA tudo o que foi pedido.

    Guardar o argv inteiro é o que deixa os testes morderem a diferença entre
    ler e escrever — `set-default-sink` aparece aqui como escrita, e um teste
    que exige "nenhuma escrita" olha esta lista.
    """

    def __init__(self, *, padrao: str = SINK_HDMI, sinks: str = LISTA_DE_SINKS):
        self.padrao = padrao
        self.sinks = sinks
        self.chamadas: list[list[str]] = []

    def __call__(self, argv: list[str]) -> str:
        self.chamadas.append(list(argv))
        if argv[:2] == ["pactl", "get-default-sink"]:
            return self.padrao + "\n"
        if argv[:3] == ["pactl", "list", "sinks"]:
            return self.sinks
        if argv[:2] == ["pactl", "set-default-sink"]:
            self.padrao = argv[2]
            return ""
        return ""

    @property
    def escritas(self) -> list[list[str]]:
        return [c for c in self.chamadas if "set-default-sink" in c]


class _Tocador:
    """Dublê do tocador: anota cada argv e devolve o código de saída pedido."""

    def __init__(self, codigo: int = 0) -> None:
        self.codigo = codigo
        self.argvs: list[list[str]] = []

    def __call__(self, argv: list[str]) -> int:
        self.argvs.append(list(argv))
        return self.codigo

    @property
    def sinks_usados(self) -> list[str]:
        """O que foi passado depois de `--device=`/`--target=`, por chamada."""
        fora: list[str] = []
        for argv in self.argvs:
            for parte in argv:
                if parte.startswith(("--device=", "--target=")):
                    fora.append(parte.split("=", 1)[1])
        return fora


def _tocar(**kwargs: Any) -> Any:
    """`tocar_confirmacao` com todas as bordas dubladas, menos o que o teste dá."""
    base: dict[str, Any] = {
        "runner": _Pactl(),
        "tocador": _Tocador(),
        "achar": lambda nome: f"/usr/bin/{nome}",
        "ligado": True,
    }
    base.update(kwargs)
    sink = base.pop("sink", SINK_CONTROLE)
    return tocar_confirmacao(sink, **base)


# ---------------------------------------------------------------------------
# Entrega 1 — o som sai NO SINK DO CONTROLE, e em nenhum outro
# ---------------------------------------------------------------------------


def test_o_som_sai_no_sink_do_controle_explicitamente() -> None:
    """A regra 1 da entrega, e a mais fácil de perder de vista.

    O tocador tem de receber o nome do sink DO CONTROLE num argumento próprio.
    Se o áudio for para o sink padrão, ela clica, não ouve nada, e conclui que
    o alto-falante quebrou.

    Mordida: tirar o `--device=` do :func:`argv_do_tocador`, deixando só o
    par executável-e-arquivo — que é o que um "toca esse arquivo" ingênuo faz.
    Isso esvazia `sinks_usados` e derruba as duas asserções.
    """
    tocador = _Tocador()
    resultado = _tocar(tocador=tocador)

    assert resultado.tocou, resultado.motivo
    assert tocador.sinks_usados == [SINK_CONTROLE], (
        "o som tem de sair no sink do CONTROLE, passado explicitamente ao "
        f"tocador — recebido {tocador.sinks_usados}"
    )
    assert SINK_HDMI not in " ".join(tocador.argvs[0])


def test_sink_fora_da_lista_viva_nao_toca_e_avisa() -> None:
    """A CURA CENTRAL do módulo, contra um comportamento medido do tocador.

    `paplay --device=<inexistente>` sai com ZERO e toca no sink PADRÃO. Sem
    conferir o nome contra a lista viva, um sink obsoleto (o controle acabou de
    sair do cabo) faria a confirmação sair pela televisão dela — o oposto
    exato do que o clique promete.

    Mordida: apagar a linha
    ``if sink not in nomes_de_sinks(ler([...]))`` de `tocar_confirmacao`. O
    tocador passa a ser chamado com um sink que não existe, `tocou` vira True e
    as três asserções caem juntas.
    """
    tocador = _Tocador()
    resultado = _tocar(sink="alsa_output.sumiu_com_o_cabo", tocador=tocador)

    assert not resultado.tocou
    assert resultado.motivo == MOTIVO_SEM_SINK
    assert tocador.argvs == [], (
        "o tocador NÃO pode ser chamado com um sink fora da lista viva: os "
        "dois tocadores aceitam nome inexistente, saem com zero e tocam no "
        "sink PADRÃO"
    )


def test_sem_sink_atribuivel_recusa_de_saida_e_sem_tocar_em_nada() -> None:
    """Dois controles no cabo: `escolher_sink` devolve None, e aqui chega "".

    Um `--device=` vazio é ACEITO pelo `paplay` e cai no sink padrão (medido).
    Então "não sei qual é o sink" tem de virar recusa, nunca um argumento
    vazio.

    A terceira asserção é a que dá corpo próprio a esta guarda, e ela foi
    escrita DEPOIS de a primeira versão do teste não morder: sem sink, a
    recusa é de SAÍDA e não pode custar nem um `pactl`. Sem ela, a guarda
    ``if not sink`` seria redundante com a da lista viva (que também recusa
    "", por "" não estar em lista nenhuma) e arrancá-la não produziria
    vermelho nenhum — a definição de cura sem teste.

    Mordida: trocar o ``if not sink`` de `tocar_confirmacao` por um caminho que
    siga em frente com "". O motivo continua `sem_sink` (a lista viva segura),
    mas o dublê do `pactl` passa a registrar uma leitura e a terceira asserção
    cai.
    """
    pactl = _Pactl()
    tocador = _Tocador()
    resultado = _tocar(sink="", runner=pactl, tocador=tocador)

    assert not resultado.tocou
    assert resultado.motivo == MOTIVO_SEM_SINK
    assert tocador.argvs == []
    assert pactl.chamadas == [], (
        "sem sink a recusa é de saída: não se gasta subprocess para descobrir "
        "o que já se sabe"
    )


def test_argv_do_tocador_recusa_sink_vazio() -> None:
    """A mesma guarda, uma camada abaixo — cinto e suspensório de propósito.

    `argv_do_tocador` é público e pode ser chamado de outro lugar amanhã.

    Mordida: deixar o ``if not sink or not arquivo`` sair da função; o argv
    volta com ``--device=`` vazio e a asserção cai.
    """
    assert argv_do_tocador("", "/tmp/s.oga", achar=lambda n: f"/usr/bin/{n}") == []
    assert argv_do_tocador(SINK_CONTROLE, "", achar=lambda n: f"/usr/bin/{n}") == []


# ---------------------------------------------------------------------------
# Entrega 1 — não finge, e não erra calado
# ---------------------------------------------------------------------------


@pytest.mark.parametrize(
    ("kwargs", "motivo_esperado", "porque"),
    [
        (
            {"sink": ""},
            MOTIVO_SEM_SINK,
            "sem sink do controle não há onde tocar",
        ),
        (
            {"saida_muda": True},
            MOTIVO_SAIDA_MUDA,
            "com a camada 1 muda o som não sairia e ela leria silêncio",
        ),
        (
            {"achar": lambda _n: None},
            MOTIVO_SEM_TOCADOR,
            "sem paplay nem pw-play na máquina",
        ),
        (
            {"tocador": _Tocador(codigo=1)},
            MOTIVO_FALHOU,
            "o tocador rodou e devolveu erro",
        ),
    ],
)
def test_quando_nao_da_para_tocar_a_interface_recebe_o_motivo(
    kwargs: dict[str, Any], motivo_esperado: str, porque: str
) -> None:
    """Regra 4 da entrega: se não houver como tocar, não finja — e não cale.

    Um clique que promete som e não entrega é pior que nenhum som. Cada recusa
    devolve um motivo COM recado, para a interface poder dizer por que não deu
    para confirmar.

    Mordida: fazer qualquer um destes caminhos devolver
    ``ResultadoDoSom(True, ...)``, ou apagar a frase do dicionário
    :data:`RECADOS` (o "errar calado"). As duas asserções são independentes de
    propósito: a primeira pega o fingimento, a segunda pega o silêncio.
    """
    resultado = _tocar(**kwargs)

    assert not resultado.tocou, porque
    assert resultado.motivo == motivo_esperado, porque
    assert resultado.recado, (
        f"o motivo {motivo_esperado!r} tem de trazer um recado para a tela: "
        "errar calado é a falha que esta leva não pode ter"
    )


def test_sem_arquivo_de_som_recusa_com_recado() -> None:
    """Máquina sem tema de som nenhum: recusa, com frase.

    Vale um teste próprio porque o arquivo é procurado por caminho absoluto e
    não passa por dublê nenhum nos outros casos.

    Mordida: fazer `arquivo_de_confirmacao` devolver um caminho fixo sem
    conferir existência; o motivo deixa de ser `sem_arquivo` e a asserção cai.
    """
    monkey_raizes = ("/lugar/que/nao/existe",)
    assert arquivo_de_confirmacao(raizes=monkey_raizes) == ""

    resultado = tocar_confirmacao(
        SINK_CONTROLE,
        ligado=True,
        runner=_Pactl(),
        tocador=_Tocador(),
        achar=lambda n: f"/usr/bin/{n}",
    )
    # Nesta máquina o tema existe; o que se afere aqui é o par motivo/recado do
    # caminho negativo, montado à mão.
    assert RECADOS[MOTIVO_SEM_ARQUIVO], "o motivo sem_arquivo tem de ter recado"
    assert resultado.motivo in (MOTIVO_TOCOU, MOTIVO_SEM_ARQUIVO)


def test_os_dois_silencios_de_proposito_nao_viram_recado() -> None:
    """Nem todo "não tocou" é falha — e a tela não pode acusar escolha dela.

    ``desligado`` é a chave dela; ``ocupado`` é o antirrajada e o som anterior
    já vai ser ouvido. Nenhum dos dois é defeito, e escrever "sem confirmação"
    a cada gesto seria a janela discutindo a decisão da usuária.

    Mordida: dar recado a estes dois motivos em :data:`RECADOS`.
    """
    assert RECADOS[MOTIVO_DESLIGADO] == ""
    assert RECADOS[MOTIVO_OCUPADO] == ""
    assert RECADOS[MOTIVO_TOCOU] == ""


def test_a_chave_de_desligar_existe_e_e_respeitada() -> None:
    """Entrega 1, regra 6: é preferência, não imposição.

    Ligada por padrão (sem ela não há confirmação nenhuma, que é o defeito que
    a leva vem tapar) e desligável sem esperar release nenhuma.

    Mordida: ignorar a chave em `tocar_confirmacao` (usar ``ligado=True`` fixo)
    faz o tocador ser chamado mesmo desligado.
    """
    assert som_ligado(carregar=dict) is True, "ligada por padrão"
    assert som_ligado(carregar=lambda: {audio_saida.CHAVE_PREF_SOM: False}) is False

    tocador = _Tocador()
    resultado = _tocar(ligado=False, tocador=tocador)
    assert resultado.motivo == MOTIVO_DESLIGADO
    assert tocador.argvs == [], "desligado quer dizer NENHUM processo de áudio"


# ---------------------------------------------------------------------------
# Entrega 1 — nada de metralhadora de sons
# ---------------------------------------------------------------------------


def test_um_som_por_vez_e_nao_um_por_pixel() -> None:
    """Regra 3: arrastar não pode virar rajada. Esta é a camada do MOTOR.

    A do widget é o repouso de 250ms (`test_status_som_04_rota.py`); esta é a
    trava de um som por vez, e ela existe porque o repouso é por widget e o
    tocador leva ~0,35s — sem ela, um gesto longo enfileiraria processos no
    executor de UMA worker do `ipc_bridge` e os sons chegariam depois do gesto.

    Mordida: apagar o ``_tocando.acquire(blocking=False)`` de
    `tocar_confirmacao`. O tocador reentrante passa a ser chamado 4 vezes e a
    asserção do 1 cai.
    """
    chamadas: list[list[str]] = []

    def _tocador_reentrante(argv: list[str]) -> int:
        chamadas.append(list(argv))
        # Enquanto ESTE som toca, chegam mais três pedidos — o que um arrasto
        # de verdade faz. Nenhum deles pode abrir um segundo processo.
        if len(chamadas) == 1:
            for _ in range(3):
                resultado = _tocar(tocador=_tocador_reentrante)
                assert resultado.motivo == MOTIVO_OCUPADO
        return 0

    primeiro = _tocar(tocador=_tocador_reentrante)

    assert primeiro.tocou
    assert len(chamadas) == 1, (
        f"um som por gesto, não um por pixel: {len(chamadas)} processos de "
        "áudio abertos ao mesmo tempo"
    )


def test_a_trava_solta_depois_de_tocar() -> None:
    """A trava é antirrajada, não mordaça: dois gestos seguidos tocam os dois.

    Mordida: esquecer o `finally: _tocando.release()`. O segundo gesto (e todos
    os seguintes, a sessão inteira) volta `ocupado` e o som some para sempre.
    """
    tocador = _Tocador()
    assert _tocar(tocador=tocador).tocou
    assert _tocar(tocador=tocador).tocou
    assert len(tocador.argvs) == 2


# ---------------------------------------------------------------------------
# Entrega 1 — o som escolhido
# ---------------------------------------------------------------------------


def test_o_som_escolhido_e_curto_e_tem_caminho_de_fallback() -> None:
    """Regra 5: som curto, presente em qualquer distribuição, com fallback.

    A ordem do laço é a que decide: o CANDIDATO por fora, a RAIZ por dentro.
    Assim a máquina com o tema completo toca `audio-volume-change` (0,067s, o
    nome que a especificação do freedesktop dá a "mudou o volume") e não o
    primeiro arquivo que aparecer numa raiz qualquer.

    Mordida: inverter os dois laços de `arquivo_de_confirmacao`. Com o tema em
    `/app/share` e só o `bell` em `/usr/share`, o `bell` de `/usr` venceria o
    `audio-volume-change` de `/app` — e a asserção da preferência cai.
    """
    tamanhos = {
        "/app/share/sounds/freedesktop/stereo/audio-volume-change.oga": 5596,
        "/usr/share/sounds/freedesktop/stereo/bell.oga": 8495,
    }
    escolhido = arquivo_de_confirmacao(tamanho=lambda c: tamanhos.get(c, 0))
    assert escolhido.endswith("audio-volume-change.oga"), (
        "o candidato manda mais que a raiz: o som semanticamente certo vence "
        f"o primeiro que aparecer — escolhido {escolhido}"
    )

    # O fallback: sem o som de volume, o `bell`; sem tema nenhum, o do ALSA.
    so_bell = {"/usr/share/sounds/freedesktop/stereo/bell.oga": 8495}
    assert arquivo_de_confirmacao(tamanho=lambda c: so_bell.get(c, 0)).endswith(
        "bell.oga"
    )
    so_alsa = {"/usr/share/sounds/alsa/Front_Center.wav": 100000}
    assert arquivo_de_confirmacao(tamanho=lambda c: so_alsa.get(c, 0)).endswith(
        "Front_Center.wav"
    )
    assert arquivo_de_confirmacao(tamanho=lambda _c: 0) == ""


def test_arquivo_existente_e_vazio_nao_conta_como_som() -> None:
    """Medido: o `window-attention.oga` desta máquina tem 18 bytes.

    Ele EXISTE, o tocador sai com zero e nenhum som sai — a falha calada em
    pessoa. Um teste de existência (`os.path.exists`) passaria com ele.

    Mordida: trocar o piso de tamanho por um `os.path.exists`; o arquivo de 18
    bytes passa a ser escolhido e a asserção cai.
    """
    quebrado = {"/usr/share/sounds/freedesktop/stereo/audio-volume-change.oga": 18}
    assert arquivo_de_confirmacao(tamanho=lambda c: quebrado.get(c, 0)) == ""


# ---------------------------------------------------------------------------
# Entrega 2 — a rota, e o desfazer que é parte da entrega
# ---------------------------------------------------------------------------


def _rota(pactl: _Pactl, memoria: dict[str, str]) -> RotaDeSaida:
    return RotaDeSaida(
        runner=pactl,
        ler_memoria=lambda: memoria.get("anterior", ""),
        gravar_memoria=lambda v: memoria.__setitem__("anterior", v),
    )


def test_mandar_para_o_controle_guarda_o_sink_anterior_antes_de_trocar() -> None:
    """Regra 1: é reversível, e o desfazer é parte da entrega.

    A ORDEM é a entrega: guardar DEPOIS de trocar deixaria uma janela em que o
    `pactl` já mudou e a memória ainda não — e uma queda ali dentro apagaria
    para sempre o caminho de volta. A configuração dela é dela.

    Mordida: apagar o `self._gravar_memoria(atual)` de
    `mandar_para_o_controle`. A troca continua funcionando, a memória fica
    vazia e o botão de volta nunca mais aparece — o defeito silencioso que
    esta casa chama de "a config que eu deixo nunca é respeitada".
    """
    pactl = _Pactl(padrao=SINK_HDMI)
    memoria: dict[str, str] = {}
    rota = _rota(pactl, memoria)

    assert rota.mandar_para_o_controle(SINK_CONTROLE) is True
    assert pactl.padrao == SINK_CONTROLE
    assert memoria["anterior"] == SINK_HDMI, (
        "o sink anterior tem de estar guardado ANTES da troca — sem ele não "
        "há desfazer"
    )


def test_voltar_ao_anterior_devolve_o_sink_dela_e_esquece_a_memoria() -> None:
    """O desfazer inteiro, ida e volta, com a memória limpa no fim.

    Esquecer é parte do desfazer: memória que sobrevive ao retorno faria o
    próximo `estado()` oferecer "voltar" para onde o som já está.

    Mordida: apagar o `self._gravar_memoria("")` do fim de
    `voltar_ao_anterior`; a última asserção cai e o botão passa a oferecer uma
    volta que não vai a lugar nenhum.
    """
    pactl = _Pactl(padrao=SINK_HDMI)
    memoria: dict[str, str] = {}
    rota = _rota(pactl, memoria)

    rota.mandar_para_o_controle(SINK_CONTROLE)
    assert rota.voltar_ao_anterior() is True

    assert pactl.padrao == SINK_HDMI, "a saída dela voltou para onde estava"
    assert memoria.get("anterior", "") == ""


def test_a_volta_confere_que_o_sink_guardado_ainda_existe() -> None:
    """Sink guardado que sumiu (monitor desligado, dongle fora) não vira alvo.

    `pactl set-default-sink <inexistente>` não muda nada e não reclama: a
    janela acharia que desfez.

    Mordida: apagar o ``if guardado not in vivos`` de `voltar_ao_anterior`. A
    função passa a devolver True sem ter mudado nada, e a primeira asserção
    cai.
    """
    pactl = _Pactl(padrao=SINK_CONTROLE)
    memoria = {"anterior": "alsa_output.monitor_que_foi_desligado"}
    rota = _rota(pactl, memoria)

    assert rota.voltar_ao_anterior() is False
    assert pactl.escritas == [], "nada de escrever um sink que não existe"
    assert pactl.padrao == SINK_CONTROLE


def test_a_troca_e_conferida_relendo_e_nao_acreditando_na_propria_escrita() -> None:
    """A janela que acredita na própria escrita é a janela que mente na tela.

    Mordida: fazer `_trocar` devolver ``True`` fixo depois do
    `set-default-sink`. Com um `pactl` que aceita e não aplica, a função passa
    a dizer que trocou.
    """

    class _PactlTeimoso(_Pactl):
        def __call__(self, argv: list[str]) -> str:
            self.chamadas.append(list(argv))
            if argv[:2] == ["pactl", "get-default-sink"]:
                return self.padrao + "\n"
            if argv[:3] == ["pactl", "list", "sinks"]:
                return self.sinks
            return ""  # aceita o set-default-sink e NÃO aplica

    pactl = _PactlTeimoso(padrao=SINK_HDMI)
    rota = _rota(pactl, {})
    assert rota.mandar_para_o_controle(SINK_CONTROLE) is False


def test_estado_nao_escreve_nada() -> None:
    """Ler a rota é leitura. A regra 4 da entrega, aferida no argv.

    Mordida: fazer `estado()` "normalizar" a saída com um `set-default-sink`.
    """
    pactl = _Pactl(padrao=SINK_HDMI)
    _rota(pactl, {}).estado(SINK_CONTROLE)
    assert pactl.escritas == []


# ---------------------------------------------------------------------------
# Entrega 2 — o rótulo diz o que o clique faz, e a dica diz o preço
# ---------------------------------------------------------------------------


def test_a_tabela_do_botao_de_rota_inteira() -> None:
    """Regra 2: o rótulo diz a AÇÃO, nada de "Ativar/Desativar" ambíguo.

    Mordida: qualquer linha trocada de rótulo ou de sensibilidade. A que mais
    importa é a última — ver o teste seguinte.
    """
    fora = acao_da_rota(
        EstadoDaRota(
            sink_padrao=SINK_HDMI, sink_do_controle=SINK_CONTROLE, no_controle=False
        )
    )
    assert fora.rotulo == TEXTO_ROTA_PARA_O_CONTROLE
    assert fora.sensivel and fora.alvo == SINK_CONTROLE

    dentro = acao_da_rota(
        EstadoDaRota(
            sink_padrao=SINK_CONTROLE,
            sink_do_controle=SINK_CONTROLE,
            anterior=SINK_HDMI,
            no_controle=True,
        )
    )
    assert dentro.rotulo == TEXTO_ROTA_VOLTAR
    assert dentro.sensivel and dentro.alvo == SINK_HDMI
    assert apelido_do_sink(SINK_HDMI) in dentro.dica, (
        "a dica da volta tem de NOMEAR para onde o som vai"
    )

    sem_sink = acao_da_rota(EstadoDaRota(sink_padrao=SINK_HDMI))
    assert sem_sink.rotulo == TEXTO_ROTA_PARA_O_CONTROLE
    assert not sem_sink.sensivel and sem_sink.alvo == ""


def test_com_o_som_ja_no_controle_e_sem_memoria_nao_ha_desfazer_honesto() -> None:
    """Regra 6, o caso que não se adivinha — e a linha mais importante da tabela.

    Com o som já no controle e sem memória de quem o pôs lá (foi ela pelas
    configurações do sistema, ou a janela nunca soube), **não existe desfazer
    honesto**: escolher um sink qualquer para "voltar" seria a janela decidindo
    qual é a saída dela.

    Mordida: fazer o ramo cair no primeiro sink não-controle da lista, que é o
    reflexo natural de quem quer o botão sempre clicável. A asserção da
    insensibilidade cai, e com ela a promessa de que a config dela é dela.
    """
    acao = acao_da_rota(
        EstadoDaRota(
            sink_padrao=SINK_CONTROLE,
            sink_do_controle=SINK_CONTROLE,
            anterior="",
            no_controle=True,
        )
    )
    assert not acao.sensivel
    assert acao.alvo == "", "sem memória não há alvo — e sem alvo não há clique"
    assert "configurações de som do sistema" in acao.dica


def test_com_mais_de_um_controle_o_botao_para_e_diz_por_que() -> None:
    """Regra 6: `escolher_sink` devolve None de propósito, e o botão obedece.

    O nome do sink não carrega identidade — o `-00` é desempate posicional do
    PipeWire, não número de série. Mandar o som para o controle errado é pior
    que não mandar, e um botão morto e MUDO seria a janela quebrada.

    Mordida: deixar o botão sensível com `sink_do_controle` vazio; o clique
    passa a mandar "" ao `pactl`, que é o caminho do sink padrão.
    """
    acao = acao_da_rota(EstadoDaRota(sink_padrao=SINK_HDMI, sink_do_controle=""))
    assert not acao.sensivel
    assert acao.alvo == ""
    assert "mais de um" in acao.dica.lower()


def test_a_dica_diz_que_a_troca_e_do_sistema_inteiro_antes_do_clique() -> None:
    """Regra 3: mandar o áudio para o controle muda o som de TUDO.

    Isso tem de estar na dica ANTES do clique — depois já é tarde. E a segunda
    metade importa igual: a troca é a mesma que as configurações de som do
    sistema fazem, e continua valendo depois de fechar a janela.

    Mordida: encurtar a dica para "manda o som do jogo para o controle".
    """
    acao = acao_da_rota(
        EstadoDaRota(sink_padrao=SINK_HDMI, sink_do_controle=SINK_CONTROLE)
    )
    baixa = acao.dica.lower()
    assert "sistema inteiro" in baixa
    assert "navegador" in baixa and "jogo" in baixa
    assert "fechar esta janela" in baixa


# ---------------------------------------------------------------------------
# Os parsers, que são a borda com o texto do `pactl`
# ---------------------------------------------------------------------------


def test_parsers_do_pactl() -> None:
    """Nome do sink padrão e lista de sinks — e o que fazer com resposta ruim.

    Mordida: fazer `sink_padrao_da_saida` devolver a linha bruta sem `strip`,
    ou aceitar a linha `Failure:` do `pactl` sem servidor como se fosse nome.
    """
    assert sink_padrao_da_saida(SINK_HDMI + "\n") == SINK_HDMI
    assert sink_padrao_da_saida("") == ""
    assert sink_padrao_da_saida("Failure: No such entity\n") == ""
    assert nomes_de_sinks(LISTA_DE_SINKS) == [SINK_CONTROLE, SINK_SPDIF, SINK_HDMI]
    assert nomes_de_sinks("") == []
    assert apelido_do_sink(SINK_HDMI) == "hdmi-stereo"
    assert apelido_do_sink(SINK_CONTROLE) == "analog-surround-40"
    assert apelido_do_sink("") == ""
