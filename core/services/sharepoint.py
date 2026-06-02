"""
Integração com o SharePoint via Microsoft Graph API.

Fluxo: autenticação OAuth2 (client_credentials) → resolução do site → criação de item
na lista de eventos. As credenciais e IDs necessários vêm das variáveis de ambiente
definidas em settings (SHAREPOINT_TENANT_ID, CLIENT_ID, CLIENT_SECRET, SITE_HOSTNAME,
EVENTS_LIST_ID).
"""

import logging
import requests
from django.conf import settings

logger = logging.getLogger(__name__)

# Cache em memória do ID interno do site SharePoint. Evita uma chamada extra à API a
# cada solicitação, já que o ID não muda durante a vida do processo.
_site_id_cache = None


def _get_access_token():
    """Obtém um token Bearer via OAuth2 client_credentials para a Microsoft Graph API."""
    response = requests.post(
        f"https://login.microsoftonline.com/{settings.SHAREPOINT_TENANT_ID}/oauth2/v2.0/token",
        data={
            "grant_type": "client_credentials",
            "client_id": settings.SHAREPOINT_CLIENT_ID,
            "client_secret": settings.SHAREPOINT_CLIENT_SECRET,
            # Escopo .default concede as permissões configuradas no registro do app no Azure AD
            "scope": "https://graph.microsoft.com/.default",
        },
        timeout=10,
    )
    response.raise_for_status()
    return response.json()["access_token"]


def _get_site_id(token):
    """Resolve o hostname do site SharePoint para o ID interno usado nos endpoints da Graph API.

    O ID é cacheado em memória (_site_id_cache) para evitar chamadas repetidas à API
    enquanto o processo estiver rodando.
    """
    global _site_id_cache
    if _site_id_cache:
        return _site_id_cache

    response = requests.get(
        f"https://graph.microsoft.com/v1.0/sites/{settings.SHAREPOINT_SITE_HOSTNAME}",
        headers={"Authorization": f"Bearer {token}"},
        timeout=10,
    )
    response.raise_for_status()
    _site_id_cache = response.json()["id"]
    return _site_id_cache


def criar_evento_sharepoint(solicitacao):
    """Cria um item de evento de férias na lista de calendário do SharePoint.

    Recebe uma instância de Solicitacao e publica um evento do tipo 'Holiday' com
    título, data de início e fim na lista configurada em SHAREPOINT_EVENTS_LIST_ID.
    O horário é fixado em 12:00:00Z e o evento é marcado como dia inteiro (fAllDayEvent).
    """
    token = _get_access_token()
    site_id = _get_site_id(token)

    inicio = solicitacao.inicio_do_descanso.isoformat()
    fim = solicitacao.fim_do_descanso.isoformat()
    nome = solicitacao.card.nome

    payload = {
        "fields": {
            "Title": f"Férias {nome}",
            # A Graph API exige o formato ISO 8601 com hora e timezone explícitos
            "EventDate": f"{inicio}T12:00:00Z",
            "EndDate": f"{fim}T12:00:00Z",
            "Category": "Holiday",
            "fAllDayEvent": True,
        }
    }

    response = requests.post(
        f"https://graph.microsoft.com/v1.0/sites/{site_id}/lists/{settings.SHAREPOINT_EVENTS_LIST_ID}/items",
        json=payload,
        headers={
            "Authorization": f"Bearer {token}",
            "Content-Type": "application/json",
        },
        timeout=10,
    )
    response.raise_for_status()
    logger.info("Evento SharePoint criado: Férias %s (%s a %s)", nome, inicio, fim)
