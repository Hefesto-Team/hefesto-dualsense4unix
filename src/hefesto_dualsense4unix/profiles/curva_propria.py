"""Formato do efeito de gatilho próprio — o dado e a origem não se separam.

Entrega da sprint CR-02
(``docs/process/sprints/2026-07-25-CR-02-formato-e-proveniencia.md``), sob o
processo de sala limpa de ``docs/process/CLEAN-ROOM.md``.

A regra R3 diz: *"Todo valor entra no projeto com o registro de como nasceu
(...). Valor sem proveniência não entra."* Este módulo transforma essa frase em
propriedade do formato. Não é aviso, não é convenção de revisão: um efeito sem
``medido_por``, sem ``controle`` ou sem ``nota`` **não instancia**.

A fronteira R4, explícita, porque este arquivo mistura os dois lados:

  - **fato do protocolo** — o comprimento da curva. São sete bytes porque o
    campo ``forces`` do ``TriggerEffect`` do HID do DualSense tem sete
    posições. Medido, não escolhido: ``PRESET_FACTORIES["Rigid"](5, 200)``
    devolve ``forces=(5, 200, 0, 0, 0, 0, 0)``. Isso é do hardware da Sony;

  - **criação nossa** — os valores dentro daqueles sete bytes, e os campos de
    proveniência que os acompanham. É o que a CR-04 vai produzir com a mão da
    mantenedora no gatilho, e é o que este formato protege.

Onde os efeitos moram — a decisão de projeto que a CR-02 pedia
--------------------------------------------------------------

A sprint deixou em aberto: efeito próprio dentro de cada perfil, ou num catálogo
compartilhado que os perfis referenciam? Escolhido o **catálogo compartilhado**
(:class:`CatalogoCurvasProprias`), pelo motivo que a própria sprint dá — dois
perfis com o mesmo nome e proveniências diferentes é exatamente a divergência
que o processo quer impedir.

O custo que a sprint temia (migração de esquema) é **zero hoje**: não existe
nenhuma curva própria no repositório, então não há nada para migrar. Em seis
meses existiria. Decidido agora porque agora é de graça.

Por isso o formato mora aqui e não em ``profiles/schema.py``: o catálogo é um
documento à parte, não um campo do perfil v1. ``Profile`` fica intocado —
nenhuma mudança de disco, de IPC ou de compatibilidade com binário antigo.
"""
from __future__ import annotations

from datetime import date

from pydantic import (
    BaseModel,
    ConfigDict,
    Field,
    ValidationInfo,
    field_validator,
    model_validator,
)

#: Comprimento da curva, em bytes. **Fato do protocolo, medido** (fronteira R4):
#: o ``TriggerEffect.forces`` do ``core.trigger_effects`` é uma tupla de sete
#: posições para todos os 19 presets. Não é preferência nossa — é a largura do
#: campo no report de saída do DualSense.
CURVA_BYTES = 7

#: Primeiro dia em que uma medição pode ter acontecido sob este processo: a data
#: de vigência do ``CLEAN-ROOM.md``. Uma curva que se declara medida antes disso
#: não nasceu sob o processo, e o registro dela não sustenta o que precisa
#: sustentar.
#:
#: O limite é uma data FIXA de propósito. Comparar com o relógio de hoje
#: (recusar data no futuro) faria o mesmo trabalho e traria de volta a
#: armadilha desta casa: portão que depende do relógio reprova sozinho, em
#: máquina com fuso ou data diferente, sem que nada tenha mudado.
DATA_MINIMA_DE_MEDICAO = date(2026, 7, 25)

#: Piso de tamanho da nota de proveniência. A R3 pede *"o que a pessoa sentiu e
#: por que parou nesses valores"* — e um campo obrigatório preenchido com "ok"
#: satisfaz "não vazio" sem satisfazer a regra. O número é uma escolha de
#: julgamento, não uma medição: é curto o bastante para não atrapalhar quem
#: está medindo e longo o bastante para recusar preenchimento cerimonial.
NOTA_MINIMA_DE_CARACTERES = 20

#: Campos cuja ausência é, sozinha, motivo de recusa. Ficam numa lista só para
#: que a mensagem de erro e o teste falem da mesma fonte.
CAMPOS_DE_PROVENIENCIA = ("medido_por", "medido_em", "controle", "nota")


def _nomes_recusados_do_dsx() -> frozenset[str]:
    """Os doze nomes de modo "pronto" do DSX, dobrados para comparação.

    Import tardio de propósito: ``daemon.udp_server`` abre socket e puxa o
    daemon inteiro, e ``profiles`` não deve depender disso só para ler uma
    constante. É o mesmo motivo do import tardio em ``schema.TriggerConfig``.

    A fonte única é o ``DSX_CANNED_TRIGGER_MODES`` — a lista de recusa não é
    transcrita aqui, para não existirem duas listas que possam divergir.
    """
    from hefesto_dualsense4unix.daemon.udp_server import DSX_CANNED_TRIGGER_MODES

    return frozenset(nome.casefold() for nome in DSX_CANNED_TRIGGER_MODES.values())


class CurvaPropria(BaseModel):
    """Um efeito de gatilho da casa, com a proveniência grudada nele.

    Todo campo é obrigatório. Não há default para nenhum dos quatro campos de
    proveniência, e isso é o ponto: um default transformaria "não informado" em
    "informado como vazio", que é o buraco que a R3 fecha.
    """

    model_config = ConfigDict(extra="forbid")

    #: Nome do efeito, em português (regra R2). Nunca um dos doze nomes do DSX.
    nome: str
    #: Os sete bytes efetivamente enviados ao controle.
    curva: list[int]
    #: Quem sentou com o controle e sentiu o gatilho.
    medido_por: str
    #: Quando, em ISO ``AAAA-MM-DD``.
    medido_em: str
    #: Modelo e transporte — a resposta do gatilho varia entre aparelhos.
    controle: str
    #: O que a pessoa sentiu e por que parou nesses valores.
    nota: str

    @field_validator("nome", "medido_por", "medido_em", "controle", "nota", mode="before")
    @classmethod
    def _recusa_nao_texto(cls, value: object) -> object:
        """Recusa ``None`` e números onde se espera texto, com a razão certa.

        Sem isto, ``medido_por=None`` levanta o erro genérico de tipo do
        pydantic, que não explica nada a quem está tentando gravar uma curva.
        """
        if value is None:
            raise ValueError(
                "campo de proveniência ausente (None). A regra R3 do "
                "CLEAN-ROOM.md não admite valor sem origem: veja "
                "docs/process/CLEAN-ROOM.md"
            )
        return value

    @field_validator("medido_por", "controle", mode="after")
    @classmethod
    def _proveniencia_nao_vazia(cls, value: str, info: ValidationInfo) -> str:
        campo = info.field_name or "campo"
        if not value.strip():
            raise ValueError(
                f"{campo} vazio. Curva sem proveniência não entra (regra R3 do "
                "CLEAN-ROOM.md): sem registro de quem mediu e com que controle, "
                "a tabela inteira perde a defesa, não só esta linha"
            )
        return value.strip()

    @field_validator("nota", mode="after")
    @classmethod
    def _nota_diz_alguma_coisa(cls, value: str) -> str:
        limpa = value.strip()
        if not limpa:
            raise ValueError(
                "nota vazia. A regra R3 pede o que a pessoa sentiu e por que "
                "parou nesses valores — é esse texto que distingue uma curva "
                "medida de um número inventado"
            )
        if len(limpa) < NOTA_MINIMA_DE_CARACTERES:
            raise ValueError(
                f"nota curta demais ({len(limpa)} caracteres, mínimo "
                f"{NOTA_MINIMA_DE_CARACTERES}). Descreva a sensação e o motivo "
                "de parar nesses valores; um preenchimento cerimonial não "
                "sustenta a proveniência"
            )
        return limpa

    @field_validator("medido_em", mode="after")
    @classmethod
    def _data_valida_e_sob_o_processo(cls, value: str) -> str:
        limpa = value.strip()
        if not limpa:
            raise ValueError(
                "medido_em vazio. A proveniência é DATADA (regra R3): sem data "
                "não há como mostrar que o valor nasceu antes de qualquer "
                "comparação com material de terceiro"
            )
        try:
            quando = date.fromisoformat(limpa)
        except ValueError as exc:
            raise ValueError(
                f"medido_em inválido: {value!r}. Use ISO AAAA-MM-DD"
            ) from exc
        if quando < DATA_MINIMA_DE_MEDICAO:
            raise ValueError(
                f"medido_em {limpa} é anterior a "
                f"{DATA_MINIMA_DE_MEDICAO.isoformat()}, data de vigência do "
                "processo de sala limpa. Medição anterior ao processo não "
                "carrega o registro que o processo exige"
            )
        return limpa

    @field_validator("nome", mode="after")
    @classmethod
    def _nome_proprio_e_nao_do_dsx(cls, value: str) -> str:
        limpo = value.strip()
        if not limpo:
            raise ValueError("nome vazio")
        if limpo.casefold() in _nomes_recusados_do_dsx():
            raise ValueError(
                f"nome {limpo!r} é um dos doze modos \"prontos\" do DSX e não "
                "pode nomear um efeito nosso. Regra R2 do CLEAN-ROOM.md: "
                "efeitos nossos usam vocabulário nosso, em português "
                "(\"Pesado\", \"Macio\", \"Trepidante\"). O motivo não é "
                "cosmético — nome igual convida à comparação byte a byte, e é a "
                "comparação que cria o problema, inclusive quando não houve "
                "cópia. Nome diferente e curva medida por você não têm o que "
                "comparar"
            )
        return limpo

    @field_validator("curva", mode="before")
    @classmethod
    def _byte_nao_e_booleano(cls, value: object) -> object:
        """Recusa ``True``/``False`` ANTES de o pydantic virá-los 1 e 0.

        Restrição que o código não mostra: em ``list[int]`` o pydantic converte
        booleano para inteiro em modo permissivo, então um validador que rode
        depois já recebe ``1`` e não tem como saber que veio um ``True``. Num
        campo de byte de report HID, booleano é sinal de dado corrompido, não
        de valor.
        """
        if isinstance(value, list):
            for idx, byte in enumerate(value):
                if isinstance(byte, bool):
                    raise ValueError(
                        f"curva[{idx}] é booleano ({byte!r}); um byte de curva "
                        "é número de 0 a 255"
                    )
        return value

    @field_validator("curva", mode="after")
    @classmethod
    def _curva_com_a_largura_do_hardware(cls, value: list[int]) -> list[int]:
        """Sete bytes de 0 a 255 — fronteira R4, lado do fato do protocolo."""
        if len(value) != CURVA_BYTES:
            raise ValueError(
                f"curva precisa de exatamente {CURVA_BYTES} bytes (recebeu "
                f"{len(value)}): é a largura do campo `forces` do report de "
                "saída do DualSense, não uma escolha nossa"
            )
        for idx, byte in enumerate(value):
            if isinstance(byte, bool) or not isinstance(byte, int):
                raise ValueError(
                    f"curva[{idx}] deve ser int, recebeu "
                    f"{type(byte).__name__}"
                )
            if not 0 <= byte <= 255:
                raise ValueError(
                    f"curva[{idx}] = {byte} fora da faixa de um byte (0-255)"
                )
        return value

    @property
    def medido_em_data(self) -> date:
        """A data de medição já convertida — o campo guarda a forma ISO."""
        return date.fromisoformat(self.medido_em)


class CatalogoCurvasProprias(BaseModel):
    """O catálogo compartilhado. Um nome, uma proveniência, sem exceção."""

    model_config = ConfigDict(extra="forbid")

    versao: int = 1
    curvas: list[CurvaPropria] = Field(default_factory=list)

    @model_validator(mode="after")
    def _sem_nome_repetido(self) -> CatalogoCurvasProprias:
        """Recusa o mesmo nome duas vezes, ignorando a caixa.

        É o defeito que a CR-02 nomeia como razão de existir do catálogo: dois
        registros do mesmo nome com proveniências diferentes deixam quem lê sem
        saber qual das duas defende o valor que está no hardware.
        """
        vistos: dict[str, int] = {}
        for idx, curva in enumerate(self.curvas):
            chave = curva.nome.casefold()
            if chave in vistos:
                raise ValueError(
                    f"nome duplicado no catálogo: {curva.nome!r} aparece nos "
                    f"índices {vistos[chave]} e {idx}. Um nome tem uma "
                    "proveniência só — duas proveniências para o mesmo nome é "
                    "a divergência que este catálogo existe para impedir"
                )
            vistos[chave] = idx
        return self


def gerar_tabela_markdown(catalogo: CatalogoCurvasProprias) -> str:
    """Devolve a tabela de ``docs/protocol/curvas-proprias.md``, gerada do dado.

    A CR-02 é explícita sobre isto: a tabela é **gerada a partir dos perfis, não
    escrita à mão**. Registro mantido à mão desatualiza, e registro desatualizado
    não defende ninguém.

    Catálogo vazio devolve a linha que o documento já tem hoje, para que o
    arquivo continue legível antes de a CR-04 medir o primeiro efeito.
    """
    if not catalogo.curvas:
        return "_(nenhum ainda — ver CR-04)_"

    linhas = [
        "| Nome | Medido por | Medido em | Controle | Curva | Nota |",
        "|---|---|---|---|---|---|",
    ]
    for curva in sorted(catalogo.curvas, key=lambda c: c.nome.casefold()):
        bytes_formatados = ", ".join(str(b) for b in curva.curva)
        nota = curva.nota.replace("|", r"\|").replace("\n", " ")
        linhas.append(
            f"| {curva.nome} | {curva.medido_por} | {curva.medido_em} "
            f"| {curva.controle} | `[{bytes_formatados}]` | {nota} |"
        )
    return "\n".join(linhas)
