"""SINAL-NO-NASCIMENTO-01 — o carimbo, e as cinco mentiras que ele não pode contar.

A BARRA-MUDA-01 mediu o veredito e ninguém o perguntava na hora em que a conexão
nasce; então ele só existia enquanto o diário ainda tivesse a linha. Estes testes
guardam o carimbo, e cada classe corresponde a uma coisa que já custou caro:

1. **o veredito é POR INSTÂNCIA.** Quatro condenadas e duas sãs convivem na
   bancada de 22/08/2026, e um veredito global apagaria justamente a distinção
   que a medição produziu;
2. **perguntar não pode custar diário.** Com tudo carimbado firme, o tique não
   pede mais nada — é essa a diferença entre "o produto sabe" e "o produto
   sabia enquanto o journald não rotacionou";
3. **suspeita não volta atrás, e a sonda ao vivo só AGRAVA.** O diário só ganha
   linhas; e "alguém segura o nó agora" só fala do nascimento de quem nasceu
   sob nossos olhos, dentro da janela de 5 s;
4. **o `hw_version` não é identidade.** Ele é revisão de placa (canônica,
   MEDIDO 15/08/2026: *"dois controles da mesma cor comprados juntos teriam o
   mesmo valor"*), e por isso a busca por ele devolve LISTA;
5. **o Modo Nativo não fabrica "limpa".** Ali o daemon não sonda por regra dela,
   o diário não ganha a linha, e um veredito de diário devolveria inocência sem
   ninguém ter olhado.

FIXTURES: os endereços são da faixa sintética ``aa:bb:cc`` da casa. Nenhum
endereço real entra em arquivo versionado, e há portão que reprova.
"""

from __future__ import annotations

import asyncio
from typing import Any

import pytest

from hefesto_dualsense4unix.core.escritor_cru import SentinelaDeEscritorCru
from hefesto_dualsense4unix.daemon import connection as cx
from hefesto_dualsense4unix.integrations import sinal_da_barra as sb

# ---------------------------------------------------------------------------
# A bancada de 22/08/2026, as seis instâncias, com os instantes reais do kernel.
# Quatro nasceram às 18:05-18:06 com a Steam segurando o nó (barra APAGADA pelo
# olho dela); duas nasceram às 19:51 com a mesa limpa (ACENDERAM).
# ---------------------------------------------------------------------------
_ADAPTADOR = "aa:bb:cc:99:88:77"

#: `(instância, uniq, hw_version, nó, quando, sujo)`. Os pares de `hw_version`
#: repetem de propósito: a `.0028`/`.0033` e a `.002a`/`.0034` são os dois
#: controles que ela reconectou, e é essa repetição que prova que o
#: `hw_version` não serve de identidade.
_BANCADA: tuple[tuple[str, str, str, str, float, bool], ...] = (
    ("0028", "aa:bb:cc:11:22:01", "0x00000811", "/dev/hidraw6", 64_740.852, True),
    ("0029", "aa:bb:cc:11:22:02", "0x00001111", "/dev/hidraw7", 64_762.210, True),
    ("002a", "aa:bb:cc:11:22:03", "0x00000710", "/dev/hidraw8", 64_774.901, True),
    ("002b", "aa:bb:cc:11:22:04", "0x00000711", "/dev/hidraw9", 64_793.102, True),
    ("0033", "aa:bb:cc:11:22:01", "0x00000811", "/dev/hidraw6", 71_507.534, False),
    ("0034", "aa:bb:cc:11:22:03", "0x00000710", "/dev/hidraw8", 71_510.240, False),
)


def _instancia(linha: tuple[str, str, str, str, float, bool]) -> sb.Instancia:
    instancia, uniq, hw, no, _quando, _sujo = linha
    return sb.Instancia(
        instancia=instancia,
        uniq=uniq,
        adaptador=_ADAPTADOR,
        hw_version=hw,
        input_n=None,
        hidraw=no,
        transporte="bt",
    )


def _instancias_da_bancada() -> list[sb.Instancia]:
    return [_instancia(linha) for linha in _BANCADA]


def _nascimentos_da_bancada() -> dict[str, sb.Nascimento]:
    return {
        instancia: sb.Nascimento(
            instancia=instancia,
            quando=quando,
            no=no,
            transporte="bt",
            escritor=(600105,) if sujo else (),
            sujo=sujo,
        )
        for instancia, _uniq, _hw, no, quando, sujo in _BANCADA
    }


#: `{uniq: nó}` — o que o backend diria estar segurando. É o portão que separa
#: "todo DualSense da máquina" de "os controles que o produto abriu".
_MAPA_DA_BANCADA: dict[str, str] = {
    uniq: no for _i, uniq, _hw, no, _q, _s in _BANCADA
}


def _leituras_da_bancada() -> list[sb.Leitura]:
    """O que o lado de DIAGNÓSTICO do módulo responde para a bancada inteira."""
    return sb.ler_a_mesa(
        instancias=_instancias_da_bancada(), nascimentos=_nascimentos_da_bancada()
    )


class TestOCarimboEPorInstancia:
    """A prova exigida pela sprint: quatro condenadas e duas sãs, sem diário."""

    def test_quatro_nascem_condenadas_e_duas_sas(self) -> None:
        cartorio = sb.CartorioDoNascimento()
        cartorio.observar(_instancias_da_bancada(), agora=100.0)
        cartorio.carimbar(_leituras_da_bancada(), agora=100.0)

        condenados = {c.instancia for c in cartorio.condenados()}
        assert condenados == {"0028", "0029", "002a", "002b"}
        sas = {
            c.instancia
            for c in cartorio.todos()
            if c.confianca == sb.CONFIANCA_LIMPA
        }
        assert sas == {"0033", "0034"}

    def test_a_pergunta_depois_nao_le_o_diario(self, monkeypatch) -> None:
        """Carimbado, o veredito é resposta de MEMÓRIA.

        A mordida: `nascimentos_pelo_diario` é trocado por uma bomba. Se alguma
        consulta ao cartório voltar a ler o diário, este teste estoura.
        """
        cartorio = sb.CartorioDoNascimento()
        cartorio.observar(_instancias_da_bancada(), agora=100.0)
        cartorio.carimbar(_leituras_da_bancada(), agora=100.0)

        def _bomba(**_kwargs: object) -> None:
            raise AssertionError(
                "o cartório voltou a ler o diário para responder — era ele que "
                "existia para não precisar disso"
            )

        monkeypatch.setattr(sb, "nascimentos_pelo_diario", _bomba)
        assert cartorio.da_instancia("0028").pede_reconexao is True
        assert cartorio.da_instancia("0033").pede_reconexao is False
        assert cartorio.do_uniq("aa:bb:cc:11:22:02").confianca == sb.CONFIANCA_SUSPEITA
        assert len(cartorio.todos()) == 6

    def test_a_instancia_que_some_e_esquecida(self) -> None:
        """O carimbo morre com a conexão: o defeito é dela, não do plástico."""
        cartorio = sb.CartorioDoNascimento()
        cartorio.observar(_instancias_da_bancada(), agora=100.0)
        cartorio.carimbar(_leituras_da_bancada(), agora=100.0)

        sobrou = [i for i in _instancias_da_bancada() if i.instancia == "0033"]
        cartorio.observar(sobrou, agora=200.0)
        assert [c.instancia for c in cartorio.todos()] == ["0033"]
        assert cartorio.da_instancia("0028") is None

    def test_sem_carimbo_a_resposta_e_none_e_nunca_limpa(self) -> None:
        """"Não carimbei" não pode ser confundido com "nasceu limpa"."""
        cartorio = sb.CartorioDoNascimento()
        assert cartorio.da_instancia("0033") is None
        assert cartorio.do_uniq("aa:bb:cc:11:22:01") is None


class TestSuspeitaNaoVoltaAtras:
    def test_leitura_posterior_nao_absolve(self) -> None:
        """O diário só GANHA linhas; não achar a prova depois não é inocência."""
        cartorio = sb.CartorioDoNascimento()
        alvo = _instancia(_BANCADA[0])
        cartorio.observar([alvo], agora=100.0)
        cartorio.carimbar(
            sb.ler_a_mesa(instancias=[alvo], nascimentos=_nascimentos_da_bancada()),
            agora=100.0,
        )
        assert cartorio.da_instancia("0028").pede_reconexao is True

        # Agora o diário rotacionou e a instância sumiu dele: `nao_sei`.
        cartorio.carimbar(
            sb.ler_a_mesa(instancias=[alvo], nascimentos={}), agora=101.0
        )
        assert cartorio.da_instancia("0028").confianca == sb.CONFIANCA_SUSPEITA

    def test_o_carimbo_suspeito_ja_nasce_firme(self) -> None:
        """Não há o que reconferir num veredito que não pode melhorar."""
        cartorio = sb.CartorioDoNascimento()
        alvo = _instancia(_BANCADA[0])
        cartorio.observar([alvo], agora=100.0)
        cartorio.carimbar(
            sb.ler_a_mesa(instancias=[alvo], nascimentos=_nascimentos_da_bancada()),
            agora=100.0,
        )
        assert cartorio.observar([alvo], agora=100.5) == []


class TestASondaAoVivoSoAgrava:
    """A régua de PRIMEIRA MÃO — o daemon vendo o nó segurado no tique em que a
    conexão apareceu. Ela existe porque o diário do daemon nem sempre pode ser
    lido (rodar em primeiro plano, fora da unit), e ali um "não achei a linha"
    viraria "nasceu limpa"."""

    def _limpa(self) -> tuple[sb.Instancia, list[sb.Leitura]]:
        alvo = _instancia(_BANCADA[4])  # a `.0033`, que nasceu com o nó livre
        return alvo, sb.ler_a_mesa(
            instancias=[alvo], nascimentos=_nascimentos_da_bancada()
        )

    def test_agrava_quem_nasceu_sob_nossos_olhos_dentro_da_janela(self) -> None:
        alvo, leituras = self._limpa()
        cartorio = sb.CartorioDoNascimento()
        cartorio.observar([], agora=100.0)  # a mesa vazia é a primeira passada
        cartorio.observar([alvo], agora=101.0)  # ela APARECEU aqui
        cartorio.carimbar(
            leituras, agora=101.0, nos_segurados={"/dev/hidraw6"}
        )
        assert cartorio.da_instancia("0033").pede_reconexao is True

    def test_nao_agrava_quem_ja_estava_na_mesa(self) -> None:
        """Numa conexão que já existia antes do daemon, "a Steam segura o nó
        agora" não diz nada sobre como ela NASCEU — e acusar à toa gasta o gesto
        do botão PS dela."""
        alvo, leituras = self._limpa()
        cartorio = sb.CartorioDoNascimento()
        cartorio.observar([alvo], agora=100.0)  # primeira passada: já estava aqui
        cartorio.carimbar(
            leituras, agora=100.0, nos_segurados={"/dev/hidraw6"}
        )
        assert cartorio.da_instancia("0033").confianca == sb.CONFIANCA_LIMPA

    def test_nao_agrava_depois_que_a_janela_fecha(self) -> None:
        """A Steam que abre dez minutos depois não condena o nascimento."""
        alvo, leituras = self._limpa()
        cartorio = sb.CartorioDoNascimento()
        cartorio.observar([], agora=100.0)
        cartorio.observar([alvo], agora=101.0)
        cartorio.carimbar(
            leituras,
            agora=101.0 + sb.JANELA_DE_NASCIMENTO_S,
            nos_segurados={"/dev/hidraw6"},
        )
        assert cartorio.da_instancia("0033").confianca == sb.CONFIANCA_LIMPA

    def test_o_no_do_vizinho_nao_condena(self) -> None:
        alvo, leituras = self._limpa()
        cartorio = sb.CartorioDoNascimento()
        cartorio.observar([], agora=100.0)
        cartorio.observar([alvo], agora=101.0)
        cartorio.carimbar(leituras, agora=101.0, nos_segurados={"/dev/hidraw9"})
        assert cartorio.da_instancia("0033").confianca == sb.CONFIANCA_LIMPA


class TestOHwVersionNaoEIdentidade:
    """MEDIDO na canônica, 15/08/2026: o `hardware_version` é revisão de placa,
    e *"dois controles da mesma cor comprados juntos teriam o mesmo valor"*.
    A bancada de 22/08 tem os quatro valores diferentes **por acaso de lote**."""

    def test_a_busca_por_hw_version_devolve_lista(self) -> None:
        cartorio = sb.CartorioDoNascimento()
        cartorio.observar(_instancias_da_bancada(), agora=100.0)
        cartorio.carimbar(_leituras_da_bancada(), agora=100.0)

        # A `.0028` (condenada) e a `.0033` (sã) são a MESMA peça de plástico.
        achados = cartorio.do_hw_version("0x00000811")
        assert {c.instancia for c in achados} == {"0028", "0033"}
        assert {c.pede_reconexao for c in achados} == {True, False}, (
            "duas conexões da mesma placa com vereditos OPOSTOS: devolver uma só "
            "faria a tela mostrar o veredito do controle errado"
        )

    def test_o_uniq_e_a_chave_que_a_tela_usa(self) -> None:
        """O endereço do controle é o que o resto do produto já usa por controle
        (`nos_hidraw_por_uniq`, `_edit_target_uniq`), e ele é único entre as
        conexões VIVAS."""
        vivas = [i for i in _instancias_da_bancada() if i.instancia in {"0029", "002b"}]
        cartorio = sb.CartorioDoNascimento()
        cartorio.observar(vivas, agora=100.0)
        cartorio.carimbar(
            sb.ler_a_mesa(instancias=vivas, nascimentos=_nascimentos_da_bancada()),
            agora=100.0,
        )
        assert cartorio.do_uniq("aa:bb:cc:11:22:02").instancia == "0029"
        assert cartorio.do_uniq("AA:BB:CC:11:22:04").instancia == "002b"
        assert cartorio.do_uniq("aa:bb:cc:11:22:99") is None


class TestMeiaReguaNaoAbsolve:
    """O kernel respondeu e o diário do daemon não: sabe-se QUANDO nasceu e não
    se sabe QUEM segurava. Antes desta correção o `sujo=False` de fábrica virava
    "nasceu limpa" — inocência sem ninguém ter olhado."""

    def test_escritor_desconhecido_e_nao_sei(self) -> None:
        alvo = _instancia(_BANCADA[4])
        nascimentos = {
            "0033": sb.Nascimento(
                instancia="0033",
                quando=71_507.534,
                no="/dev/hidraw6",
                transporte="bt",
                escritor_conhecido=False,
            )
        }
        (leitura,) = sb.ler_a_mesa(instancias=[alvo], nascimentos=nascimentos)
        assert leitura.confianca == sb.CONFIANCA_NAO_SEI
        assert not leitura.pede_reconexao


# ---------------------------------------------------------------------------
# O LADO DO DAEMON — o tique de hotplug carimbando.
# ---------------------------------------------------------------------------


class _ControllerFalso:
    """Só o `nos_hidraw_por_uniq`, que é por onde o carimbo sabe o que é NOSSO."""

    def __init__(self, mapa: dict[str, str]) -> None:
        self._mapa = mapa

    def nos_hidraw_por_uniq(self) -> dict[str, str]:
        return dict(self._mapa)


class _DaemonFalso:
    """O mínimo que `carimbar_o_nascimento` toca. Nada de asyncio de verdade.

    O sentinela é o de VERDADE (`core.escritor_cru.SentinelaDeEscritorCru`) com
    a sonda de `/proc` trocada — é ele que `sentinela_de_escritor_cru_de`
    aceita, e um dublê seria substituído por um sentinela vazio sem avisar.
    """

    def __init__(
        self,
        *,
        nativo: bool = False,
        nos: tuple[str, ...] = (),
        segura: dict[str, str] | None = None,
    ) -> None:
        self._nativo = nativo
        self._cartorio_do_nascimento = None
        self.controller = _ControllerFalso(
            segura if segura is not None else _MAPA_DA_BANCADA
        )
        self._sentinela_de_escritor_cru = SentinelaDeEscritorCru(
            sonda=lambda _alvos: {no: [600105] for no in nos}
        )
        if nos:
            self._sentinela_de_escritor_cru.sondar(nos, 0.0, forcar=True)

    async def _run_blocking(self, fn: Any, *args: Any) -> Any:
        return fn(*args)

    def is_native_mode(self) -> bool:
        return self._nativo


def _carimbar(daemon: Any, agora: float = 0.0) -> int:
    return asyncio.run(cx.carimbar_o_nascimento(daemon, agora=agora))


@pytest.fixture()
def bancada_no_sysfs(monkeypatch):
    """Faz o `instancias_dualsense` do daemon devolver a bancada de 22/08."""
    vivas: list[sb.Instancia] = _instancias_da_bancada()

    def _enumerar(*_a: object, **_k: object) -> list[sb.Instancia]:
        return list(vivas)

    monkeypatch.setattr(cx, "instancias_dualsense", _enumerar)
    return vivas


@pytest.fixture()
def diario_da_bancada(monkeypatch):
    """O diagnóstico do módulo, sem `journalctl`. Conta quantas vezes foi lido."""
    chamadas: list[int] = []
    real = sb.ler_a_mesa

    def _ler(**kwargs: Any) -> list[sb.Leitura]:
        chamadas.append(1)
        return real(
            instancias=kwargs.get("instancias"),
            nascimentos=_nascimentos_da_bancada(),
        )

    monkeypatch.setattr(cx, "ler_a_mesa", _ler)
    return chamadas


class TestOTiqueDeHotplugCarimba:
    def test_o_tique_carimba_as_seis_com_quatro_condenadas(
        self, bancada_no_sysfs, diario_da_bancada
    ) -> None:
        """A E1 da sprint, ponta a ponta pelo caminho que o daemon roda."""
        daemon = _DaemonFalso()
        assert _carimbar(daemon) == 6
        cartorio = cx.cartorio_do_nascimento_de(daemon)
        assert {c.instancia for c in cartorio.condenados()} == {
            "0028",
            "0029",
            "002a",
            "002b",
        }

    def test_o_segundo_tique_nao_le_o_diario_de_novo(
        self, bancada_no_sysfs, diario_da_bancada
    ) -> None:
        """Mesa parada = zero subprocessos. É o que torna o carimbo pagável a
        cada 30 s."""
        daemon = _DaemonFalso()
        _carimbar(daemon, agora=0.0)
        assert len(diario_da_bancada) == 1
        # As quatro condenadas já nasceram firmes (suspeita não volta atrás);
        # só as duas sãs voltam ao segundo tique, e a janela de 5 s já fechou
        # entre um tique de 30 s e o outro. Do terceiro em diante, nada.
        assert _carimbar(daemon, agora=30.0) == 2
        assert _carimbar(daemon, agora=60.0) == 0
        assert _carimbar(daemon, agora=90.0) == 0
        assert len(diario_da_bancada) == 2, (
            "o tique voltou a ler o diário com a mesa parada — o carimbo deixou "
            "de ser memória e virou consulta de 30 em 30 segundos"
        )

    def test_o_cartorio_e_um_so_por_daemon(self, bancada_no_sysfs, diario_da_bancada):
        daemon = _DaemonFalso()
        assert cx.cartorio_do_nascimento_de(daemon) is cx.cartorio_do_nascimento_de(
            daemon
        )

    def test_o_modo_nativo_nao_fabrica_limpa(self, bancada_no_sysfs, monkeypatch):
        """Ali o daemon não sonda (regra dela), o diário não ganha a linha, e um
        veredito de diário devolveria inocência sem ninguém ter olhado."""

        def _bomba(**_k: object) -> list[sb.Leitura]:
            raise AssertionError(
                "o Modo Nativo leu o diário — e ali o diário NÃO tem a linha do "
                "escritor, porque o produto não sonda por regra dela"
            )

        monkeypatch.setattr(cx, "ler_a_mesa", _bomba)
        daemon = _DaemonFalso(nativo=True)
        assert _carimbar(daemon) == 6
        cartorio = cx.cartorio_do_nascimento_de(daemon)
        assert {c.confianca for c in cartorio.todos()} == {sb.CONFIANCA_NAO_SEI}
        assert cartorio.condenados() == []

    def test_o_modo_nativo_nao_agrava_com_foto_velha(self, monkeypatch) -> None:
        """No Modo Nativo o vigia nem sonda: a foto do sentinela é de antes.
        Agravar com ela é a mesma desonestidade de absolver com diário
        incompleto."""
        chegada = _instancia(_BANCADA[4])
        vivas: list[sb.Instancia] = []
        monkeypatch.setattr(cx, "instancias_dualsense", lambda *_a, **_k: list(vivas))

        daemon = _DaemonFalso(
            nativo=True,
            nos=("/dev/hidraw6",),
            segura={chegada.uniq: "/dev/hidraw6"},
        )
        assert _carimbar(daemon, agora=0.0) == 0
        vivas.append(chegada)
        assert _carimbar(daemon, agora=1.0) == 1
        carimbo = cx.cartorio_do_nascimento_de(daemon).da_instancia("0033")
        assert carimbo.confianca == sb.CONFIANCA_NAO_SEI
        assert carimbo.pede_reconexao is False

    def test_a_sonda_do_daemon_condena_a_conexao_recem_chegada(
        self, monkeypatch, diario_da_bancada
    ) -> None:
        """O caminho que salva quando o daemon não consegue ler o próprio diário."""
        chegada = _instancia(_BANCADA[4])  # a `.0033`, limpa pelo diário
        vivas: list[sb.Instancia] = []
        monkeypatch.setattr(cx, "instancias_dualsense", lambda *_a, **_k: list(vivas))

        daemon = _DaemonFalso(
            nos=("/dev/hidraw6",),
            segura={chegada.uniq: "/dev/hidraw6"},
        )
        assert _carimbar(daemon, agora=0.0) == 0  # mesa vazia: a primeira passada
        vivas.append(chegada)
        assert _carimbar(daemon, agora=1.0) == 1
        carimbo = cx.cartorio_do_nascimento_de(daemon).da_instancia("0033")
        assert carimbo.pede_reconexao is True
        assert carimbo.nasceu_sob_nossos_olhos is True


class TestOCarimboSoFalaDosControlesDoProduto:
    """O sysfs enumera TODO DualSense da máquina. Carimbar um que o produto não
    abriu falaria de um controle que a tela nem lista — e faria a suíte, que
    roda na mesa dela com quatro controles ligados, pagar `journalctl`."""

    def test_sem_handle_aberto_nem_o_sysfs_e_lido(self, monkeypatch) -> None:
        # Contador, e não bomba: `carimbar_o_nascimento` é best-effort de ponta
        # a ponta e engoliria a exceção, deixando a mordida passar em branco.
        leituras: list[int] = []

        def _contar(*_a: object, **_k: object) -> list[sb.Instancia]:
            leituras.append(1)
            return []

        monkeypatch.setattr(cx, "instancias_dualsense", _contar)
        assert _carimbar(_DaemonFalso(segura={})) == 0
        assert leituras == [], (
            "o carimbo leu o sysfs sem o produto ter controle nenhum aberto"
        )

    def test_o_dualsense_do_vizinho_nao_e_carimbado(
        self, bancada_no_sysfs, diario_da_bancada
    ) -> None:
        daemon = _DaemonFalso(segura={"aa:bb:cc:11:22:02": "/dev/hidraw7"})
        assert _carimbar(daemon) == 1
        cartorio = cx.cartorio_do_nascimento_de(daemon)
        assert [c.instancia for c in cartorio.todos()] == ["0029"]


class TestOTiqueDeHotplugChamaOCarimbo:
    """A mordida da FIAÇÃO: sem esta chamada no laço, o módulo volta a ser
    enfeite — que é o estado em que a BARRA-MUDA-01 o declarou."""

    def test_o_reconnect_loop_chama_carimbar_o_nascimento(self) -> None:
        import inspect

        fonte = inspect.getsource(cx.reconnect_loop)
        assert "carimbar_o_nascimento(daemon)" in fonte, (
            "o tique de hotplug parou de carimbar o veredito. Sem isso o "
            "veredito só existe enquanto o diário ainda tem a linha, e o diário "
            "rotaciona — é exatamente o defeito da SINAL-NO-NASCIMENTO-01."
        )


class TestODiarioENoRecorte:
    """MEDIDO 22/08/2026 no diário de quinze dias dela: a leitura da unit do
    daemon custa 5,21 s sem recorte e 0,12 s com o `-S` de seis horas. Cinco
    segundos por conexão nova sairiam de um dos DOIS workers do executor que o
    daemon divide com o `read_state` — o padrão que a HANG-01 baniu."""

    def test_a_leitura_do_diario_leva_o_recorte(self, monkeypatch) -> None:
        vistos: list[list[str]] = []

        def _espiar(argv, _orcamento):  # type: ignore[no-untyped-def]
            vistos.append(list(argv))
            return []

        monkeypatch.setattr(sb, "_linhas_do_diario", _espiar)
        sb.nascimentos_pelo_diario()
        assert vistos, "nenhuma leitura de diário aconteceu"
        for argv in vistos:
            assert "-S" in argv, (
                f"o recorte sumiu de {argv!r} — a leitura voltou a varrer o "
                "diário inteiro, e são cinco segundos por conexão nova"
            )
            assert argv[argv.index("-S") + 1].startswith("@"), (
                "o recorte voltou a depender de texto formatado; o `@<epoch>` "
                "é a forma que não passa por locale"
            )

    def test_recorte_zero_le_tudo(self) -> None:
        assert sb._recorte_do_diario(0) == []
        assert sb._recorte_do_diario(-1) == []
        assert sb._recorte_do_diario(3600)[0] == "-S"


class TestOModuloContinuaSemLerALampada:
    """A regra da BARRA-MUDA-01, estendida ao que o carimbo escreve."""

    PROIBIDAS = ("acesa", "acessa", "apagada", "acendeu", "apagou")

    def test_nenhuma_frase_do_carimbo_afirma_estado_da_lampada(self) -> None:
        cartorio = sb.CartorioDoNascimento()
        cartorio.observar([], agora=100.0)
        cartorio.observar(_instancias_da_bancada(), agora=101.0)
        cartorio.carimbar(
            _leituras_da_bancada(),
            agora=101.0,
            nos_segurados={"/dev/hidraw6", "/dev/hidraw8"},
        )
        frases = [c.porque for c in cartorio.todos()]
        frases += [
            leitura.porque
            for leitura in cx._sem_sonda_no_modo_nativo(_instancias_da_bancada())
        ]
        for frase in frases:
            baixa = frase.lower()
            for proibida in self.PROIBIDAS:
                assert proibida not in baixa, (
                    f"o carimbo passou a AFIRMAR estado de lâmpada: {frase!r}. "
                    "Não existe leitura de lâmpada nesta casa."
                )
