import httpx
from celery.signals import worker_process_init, worker_process_shutdown

client = None

@worker_process_init.connect
def init_http_client(**kwargs):
    global client
    client = httpx.Client(
        timeout=httpx.Timeout(connect=5.0, read=20.0, write=20.0, pool=5.0),
        limits=httpx.Limits(max_connections=50, max_keepalive_connections=20),
    )

@worker_process_shutdown.connect
def close_http_client(**kwargs):
    global client
    if client:
        client.close()
        client = None

def send_whatsapp_message(sender: str, payload: dict, headers: dict, url: str) -> httpx.Response:
    global client
    if client is None:
        # fallback in case signals didn't run (rare)
        client = httpx.Client(timeout=20.0)

    resp = client.post(url, headers=headers, json=payload)
    resp.raise_for_status()
    return resp


# def send_whatsapp_message(sender: str, payload: dict, headers: dict, url: str):
#     """Helper function to send WhatsApp messages"""
#     with httpx.Client(timeout=20.0) as client:
#         resp = client.post(url, headers=headers, json=payload)
#         resp.raise_for_status()
#         return resp