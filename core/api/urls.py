from datetime import date

from ninja import NinjaAPI, Schema

from core.models.card import Card
from core.views.cards import gerar_senha_aleatoria
from core.views.emails import email_colaborador_adicionado
from django.contrib.auth.models import User

api = NinjaAPI()


class ColaboradorSchema(Schema):
    setor: str
    nome: str
    email: str
    data_de_admissao: date
    data_de_vencimento_de_ferias: date
    saldo_de_ferias: int


@api.post('add_colaborador')
def add_colaborador(request, colaborador: ColaboradorSchema):
    new_colaborador = colaborador.dict()
    senha = gerar_senha_aleatoria()
    user = User.objects.create_user(username=new_colaborador['nome'], email=new_colaborador['email'], password=senha)
    user.save()
    card = Card.objects.create(
        setor=new_colaborador['setor'],
        nome=new_colaborador['nome'],
        email=new_colaborador['email'],
        data_de_admissao=new_colaborador['data_de_admissao'],
        data_de_vencimento_de_ferias=new_colaborador['data_de_vencimento_de_ferias'],
        saldo_de_ferias=new_colaborador['saldo_de_ferias'],
        colaborador=user
    )
    card.save()
    email_colaborador_adicionado(card, senha)
    return {"message": "Colaborador adicionado com sucesso!"}
