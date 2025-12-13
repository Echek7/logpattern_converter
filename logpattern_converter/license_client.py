# logpattern_converter/license_client.py
"""
License client defensivo:
 - No importa requests al nivel módulo (evita errores en import).
 - activate_license intentará usar requests si está disponible.
 - Si no hay requests, devuelve error detectado claramente.
 - Es robusto frente a respuestas no-JSON.
"""
from __future__ import annotations
import os
import json
import time
import hashlib
import uuid
import socket
from typing import Optional

DEFAULT_SERVER = "https://us-central1-logpattern-pro-999c8.cloudfunctions.net/licenseVerifier"
LOCAL_LICENSE_FILE = ".crc_license.json"

def get_machine_id() -> str:
    hostname = socket.gethostname()
    try:
        mac = uuid.getnode()
        mac_str = f"{mac:x}"
    except Exception:
        mac_str = "nomac"
    base = f"{hostname}-{mac_str}"
    return hashlib.sha256(base.encode("utf-8")).hexdigest()

def write_local_license(key: str, machine_id: str, meta: Optional[dict] = None) -> None:
    payload = {
        "active_key": key,
        "machine_id": machine_id,
        "activated": True,
        "activated_at": time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime())
    }
    if meta:
        payload.update({"meta": meta})
    # write in current working dir (CLI runs from project root)
    with open(LOCAL_LICENSE_FILE, "w", encoding="utf-8") as fh:
        json.dump(payload, fh, ensure_ascii=False, indent=2)

def _post_json(url: str, body: dict, timeout: int = 15):
    """
    Helper: import requests lazily and perform post.
    Returns (success_bool, response_object_or_text, status_code)
    """
    try:
        import requests
    except Exception as e:
        return (False, {"error": "requests_missing", "detail": str(e)}, None)
    try:
        resp = requests.post(url, json=body, headers={"Content-Type": "application/json"}, timeout=timeout)
        # try parse json
        try:
            data = resp.json()
        except Exception:
            data = {"text": resp.text}
        return (True, data, resp.status_code)
    except Exception as e:
        return (False, {"error": "request_failed", "detail": str(e)}, None)

def activate_license(license_key: str, server_url: Optional[str] = None) -> dict:
    """
    Attempts to activate license against licenseVerifier.
    Returns dict: {success: bool, activated: bool, machineId, server_response or error}
    """
    url = server_url or os.environ.get("LICENSE_SERVER_URL") or DEFAULT_SERVER
    machine_id = get_machine_id()
    body = {"licenseKey": license_key, "machineId": machine_id}

    ok, resp, status = _post_json(url, body)
    if not ok:
        return {"success": False, "error": resp.get("error", "request_error"), "detail": resp.get("detail")}

    # resp is parsed JSON or a dict with text
    if isinstance(resp, dict):
        # Common success flags
        if resp.get("activated") is True or resp.get("success") is True or str(resp.get("activated")).lower() == "true":
            try:
                write_local_license(license_key, machine_id, meta=resp)
            except Exception as e:
                return {"success": True, "activated": True, "machineId": machine_id, "server_response": resp, "warning": f"failed_write_local:{e}"}
            return {"success": True, "activated": True, "machineId": machine_id, "server_response": resp}
        # server returned 200 but not activated
        return {"success": False, "activated": False, "server_response": resp}
    else:
        return {"success": False, "error": "invalid_server_response", "server_response": str(resp)}
