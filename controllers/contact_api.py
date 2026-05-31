import json
import hmac
import logging
import re

from odoo import http
from odoo.http import request, Response

_logger = logging.getLogger(__name__)

EMAIL_RE = re.compile(r"^[^@\s]+@[^@\s]+\.[^@\s]+$")

API_KEY_PARAM = "alphaqueb_contact_api.api_key"
ALLOWED_ORIGIN_PARAM = "alphaqueb_contact_api.allowed_origin"
DEFAULT_USER_ID_PARAM = "alphaqueb_contact_api.default_user_id"
DEFAULT_COMPANY_ID_PARAM = "alphaqueb_contact_api.default_company_id"
DEFAULT_TEAM_ID_PARAM = "alphaqueb_contact_api.default_team_id"


class AlphaquebContactAPI(http.Controller):
    def _get_param(self, key, default=None):
        return request.env["ir.config_parameter"].sudo().get_param(key, default)

    def _get_int_param(self, key, default=None):
        value = self._get_param(key)
        if not value:
            return default
        try:
            return int(value)
        except Exception:
            _logger.warning("Invalid integer system parameter: %s=%s", key, value)
            return default

    def _cors_headers(self):
        allowed_origin = self._get_param(ALLOWED_ORIGIN_PARAM, "*")
        return [
            ("Access-Control-Allow-Origin", allowed_origin),
            ("Access-Control-Allow-Methods", "POST, OPTIONS, GET"),
            ("Access-Control-Allow-Headers", "Content-Type, X-API-Key, Authorization"),
            ("Access-Control-Max-Age", "86400"),
        ]

    def _json_response(self, payload, status=200):
        return Response(
            json.dumps(payload, ensure_ascii=False),
            status=status,
            headers=[
                ("Content-Type", "application/json; charset=utf-8"),
                *self._cors_headers(),
            ],
        )

    def _preflight_response(self):
        return Response("", status=204, headers=self._cors_headers())

    def _read_json_body(self):
        raw = request.httprequest.get_data(as_text=True) or "{}"
        try:
            data = json.loads(raw)
        except Exception:
            return None
        return data if isinstance(data, dict) else None

    def _extract_api_key(self, data=None):
        api_key = request.httprequest.headers.get("X-API-Key")

        if not api_key:
            auth = request.httprequest.headers.get("Authorization", "")
            if auth.lower().startswith("bearer "):
                api_key = auth[7:].strip()

        # Fallback compatible con integraciones simples.
        # Recomendado: enviar la API key por header X-API-Key.
        if not api_key and data:
            api_key = data.get("api_key")

        return api_key or ""

    def _validate_api_key(self, data=None):
        expected_key = self._get_param(API_KEY_PARAM)

        if not expected_key:
            return False, self._json_response(
                {
                    "ok": False,
                    "error": "api_key_not_configured",
                    "message": "API Key no configurada en parámetros del sistema de Odoo.",
                },
                status=500,
            )

        received_key = self._extract_api_key(data)

        if not received_key or not hmac.compare_digest(str(received_key), str(expected_key)):
            return False, self._json_response(
                {
                    "ok": False,
                    "error": "invalid_api_key",
                    "message": "API Key inválida o faltante.",
                },
                status=401,
            )

        return True, None

    def _get_assignment_values(self):
        vals = {}

        user_id = self._get_int_param(DEFAULT_USER_ID_PARAM, default=2)
        company_id = self._get_int_param(DEFAULT_COMPANY_ID_PARAM, default=1)
        team_id = self._get_int_param(DEFAULT_TEAM_ID_PARAM)

        if user_id and request.env["res.users"].sudo().browse(user_id).exists():
            vals["user_id"] = user_id

        if company_id and request.env["res.company"].sudo().browse(company_id).exists():
            vals["company_id"] = company_id

        if team_id and request.env["crm.team"].sudo().browse(team_id).exists():
            vals["team_id"] = team_id

        return vals

    def _client_context_text(self, data):
        ip = request.httprequest.headers.get(
            "X-Forwarded-For",
            request.httprequest.remote_addr or "",
        )
        user_agent = request.httprequest.headers.get("User-Agent", "")

        lines = []

        optional_fields = [
            ("Empresa", "company"),
            ("Vertical", "vertical"),
            ("Origen", "source_url"),
            ("UTM Source", "utm_source"),
            ("UTM Medium", "utm_medium"),
            ("UTM Campaign", "utm_campaign"),
        ]

        for label, key in optional_fields:
            if data.get(key):
                lines.append(f"{label}: {data.get(key)}")

        if ip:
            lines.append(f"IP: {ip}")

        if user_agent:
            lines.append(f"User-Agent: {user_agent}")

        return "\n".join(lines)

    @http.route(
        ["/api/contact/health"],
        type="http",
        auth="public",
        methods=["GET"],
        csrf=False,
    )
    def health(self, **kwargs):
        return self._json_response(
            {
                "ok": True,
                "service": "alphaqueb_contact_api",
                "api_key_configured": bool(self._get_param(API_KEY_PARAM)),
            },
            status=200,
        )

    @http.route(
        ["/create_lead", "/api/contact/create_lead"],
        type="http",
        auth="public",
        methods=["POST", "OPTIONS"],
        csrf=False,
    )
    def create_lead(self, **kwargs):
        if request.httprequest.method == "OPTIONS":
            return self._preflight_response()

        data = self._read_json_body()

        if data is None:
            return self._json_response(
                {
                    "ok": False,
                    "error": "invalid_json",
                    "message": "El cuerpo de la petición debe ser JSON válido.",
                },
                status=400,
            )

        valid_key, error_response = self._validate_api_key(data)
        if not valid_key:
            return error_response

        name = (data.get("name") or "").strip()
        email = (data.get("email") or "").strip()
        message = (data.get("message") or "").strip()
        phone = (data.get("phone") or data.get("phone_number") or "").strip()
        company = (data.get("company") or "").strip()

        if not name:
            return self._json_response(
                {
                    "ok": False,
                    "error": "missing_name",
                    "message": "El nombre es obligatorio.",
                },
                status=400,
            )

        if not email:
            return self._json_response(
                {
                    "ok": False,
                    "error": "missing_email",
                    "message": "El correo electrónico es obligatorio.",
                },
                status=400,
            )

        if not EMAIL_RE.match(email):
            return self._json_response(
                {
                    "ok": False,
                    "error": "invalid_email",
                    "message": "El correo electrónico no tiene un formato válido.",
                },
                status=400,
            )

        if not message:
            return self._json_response(
                {
                    "ok": False,
                    "error": "missing_message",
                    "message": "El mensaje es obligatorio.",
                },
                status=400,
            )

        context_text = self._client_context_text(data)

        description_parts = [
            "Mensaje recibido desde sitio web:",
            "",
            message,
        ]

        if context_text:
            description_parts.extend(["", "Contexto:", context_text])

        vals = {
            "name": data.get("subject") or f"Lead web · {name}",
            "type": "lead",
            "contact_name": name,
            "email_from": email,
            "phone": phone or False,
            "partner_name": company or False,
            "description": "\n".join(description_parts),
        }

        vals.update(self._get_assignment_values())

        try:
            lead = request.env["crm.lead"].sudo().create(vals)
        except Exception as e:
            _logger.exception("Error creating CRM lead from API")
            return self._json_response(
                {
                    "ok": False,
                    "error": "lead_create_failed",
                    "message": "No se pudo crear el lead en Odoo.",
                    "detail": str(e),
                },
                status=500,
            )

        return self._json_response(
            {
                "ok": True,
                "message": "Lead creado correctamente.",
                "lead_id": lead.id,
                "lead_name": lead.name,
            },
            status=201,
        )

    @http.route(
        ["/create_contact_phone", "/api/contact/create_contact_phone"],
        type="http",
        auth="public",
        methods=["POST", "OPTIONS"],
        csrf=False,
    )
    def create_contact_phone(self, **kwargs):
        if request.httprequest.method == "OPTIONS":
            return self._preflight_response()

        data = self._read_json_body()

        if data is None:
            return self._json_response(
                {
                    "ok": False,
                    "error": "invalid_json",
                    "message": "El cuerpo de la petición debe ser JSON válido.",
                },
                status=400,
            )

        valid_key, error_response = self._validate_api_key(data)
        if not valid_key:
            return error_response

        name = (data.get("name") or "").strip()
        phone = (data.get("phone_number") or data.get("phone") or "").strip()
        company = (data.get("company") or "").strip()

        if not name:
            return self._json_response(
                {
                    "ok": False,
                    "error": "missing_name",
                    "message": "El nombre es obligatorio.",
                },
                status=400,
            )

        if not phone:
            return self._json_response(
                {
                    "ok": False,
                    "error": "missing_phone",
                    "message": "El teléfono es obligatorio.",
                },
                status=400,
            )

        context_text = self._client_context_text(data)

        description_parts = [
            "Contacto telefónico recibido desde sitio web.",
            "",
            f"Nombre: {name}",
            f"Teléfono: {phone}",
        ]

        if company:
            description_parts.append(f"Empresa: {company}")

        if context_text:
            description_parts.extend(["", "Contexto:", context_text])

        vals = {
            "name": f"Contacto web · {name}",
            "type": "lead",
            "contact_name": name,
            "phone": phone,
            "partner_name": company or False,
            "description": "\n".join(description_parts),
        }

        vals.update(self._get_assignment_values())

        try:
            lead = request.env["crm.lead"].sudo().create(vals)
        except Exception as e:
            _logger.exception("Error creating phone CRM lead from API")
            return self._json_response(
                {
                    "ok": False,
                    "error": "lead_create_failed",
                    "message": "No se pudo crear el contacto telefónico en Odoo.",
                    "detail": str(e),
                },
                status=500,
            )

        return self._json_response(
            {
                "ok": True,
                "message": "Contacto telefónico creado correctamente.",
                "lead_id": lead.id,
                "lead_name": lead.name,
            },
            status=201,
        )
