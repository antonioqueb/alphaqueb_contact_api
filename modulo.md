## ./__init__.py
```py
from . import controllers
```

## ./__manifest__.py
```py
{
    'name': 'Alphaqueb Contact API',
    'version': '19.0.1.0.0',
    'summary': 'Endpoint publico /create_lead para el formulario de contacto del sitio',
    'description': 'Expone un endpoint HTTP que recibe el formulario de alphaqueb.com/#contacto y crea un crm.lead.',
    'category': 'CRM',
    'author': 'Alphaqueb Consulting SAS',
    'website': 'https://alphaqueb.com',
    'license': 'LGPL-3',
    'depends': ['crm'],
    'installable': True,
    'application': True,
    'auto_install': False,
}
```

## ./controllers/__init__.py
```py
from . import main
```

## ./controllers/main.py
```py
# -*- coding: utf-8 -*-
import json
import logging

from odoo import http
from odoo.http import request

_logger = logging.getLogger(__name__)

ALLOWED_ORIGINS = {
    "https://alphaqueb.com",
    "https://www.alphaqueb.com",
    "http://localhost:3000",
    "http://127.0.0.1:3000",
    "http://localhost:5173",
}


def _cors_headers():
    origin = request.httprequest.headers.get("Origin", "")
    allow = origin if origin in ALLOWED_ORIGINS else "https://alphaqueb.com"
    return [
        ("Access-Control-Allow-Origin", allow),
        ("Access-Control-Allow-Methods", "POST, OPTIONS"),
        ("Access-Control-Allow-Headers", "Content-Type"),
        ("Access-Control-Max-Age", "86400"),
        ("Vary", "Origin"),
        ("Content-Type", "application/json"),
    ]


def _json(payload, status=200):
    return request.make_response(json.dumps(payload), headers=_cors_headers(), status=status)


class ContactApiController(http.Controller):

    @http.route(
        "/create_lead",
        type="http",
        auth="public",
        methods=["POST", "OPTIONS"],
        csrf=False,
        save_session=False,
    )
    def create_lead(self, **kwargs):
        # Preflight CORS
        if request.httprequest.method == "OPTIONS":
            return request.make_response("", headers=_cors_headers(), status=204)

        # Datos: acepta JSON body o form-urlencoded
        data = dict(kwargs)
        raw = request.httprequest.get_data(as_text=True)
        if raw:
            try:
                body = json.loads(raw)
                if isinstance(body, dict):
                    data.update(body)
            except (ValueError, TypeError):
                pass

        contact_name = (data.get("name") or "").strip()
        email = (data.get("email") or "").strip()
        phone = (data.get("phone") or "").strip()
        company = (data.get("company") or "").strip()
        message = (data.get("message") or "").strip()

        missing = [f for f in ("name", "email") if not data.get(f)]
        if missing:
            return _json(
                {"status": "error", "message": "Faltan campos: %s" % ", ".join(missing)},
                status=400,
            )

        try:
            lead = request.env["crm.lead"].sudo().create({
                "name": "Contacto web - %s" % contact_name,
                "contact_name": contact_name,
                "email_from": email,
                "phone": phone,
                "partner_name": company,
                "description": message,
                "type": "lead",
            })
        except Exception as e:
            _logger.exception("Error creando crm.lead desde /create_lead")
            return _json({"status": "error", "message": "Error interno al crear el lead."}, status=500)

        return _json({"status": "success", "lead_id": lead.id}, status=201)
```

