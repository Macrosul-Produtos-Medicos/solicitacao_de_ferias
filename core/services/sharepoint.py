import logging
import requests
from django.conf import settings

logger = logging.getLogger(__name__)

_site_id_cache = None


def _get_access_token():
    response = requests.post(
        f"https://login.microsoftonline.com/{settings.SHAREPOINT_TENANT_ID}/oauth2/v2.0/token",
        data={
            "grant_type": "client_credentials",
            "client_id": settings.SHAREPOINT_CLIENT_ID,
            "client_secret": settings.SHAREPOINT_CLIENT_SECRET,
            "scope": "https://graph.microsoft.com/.default",
        },
        timeout=10,
    )
    response.raise_for_status()
    return response.json()["access_token"]


def _get_site_id(token):
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
    token = _get_access_token()
    site_id = _get_site_id(token)

    inicio = solicitacao.inicio_do_descanso.isoformat()
    fim = solicitacao.fim_do_descanso.isoformat()
    nome = solicitacao.card.nome

    payload = {
        "fields": {
            "Title": f"Férias {nome}",
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
