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

LOGO_PATH = "/alphaqueb_contact_api/static/description/alphaquebdarck.png"

NOTIFY_USER_ID = 2

ACK_EMAIL_HTML = """\
<!DOCTYPE html>
<html lang="es"><head><meta charset="utf-8">
<meta name="viewport" content="width=device-width, initial-scale=1">
<meta http-equiv="X-UA-Compatible" content="IE=edge">
<title>Hemos recibido tu mensaje</title>
<style>
  @media (prefers-color-scheme: dark) {
    .aq-logo { filter: invert(1) !important; }
  }
  [data-ogsc] .aq-logo { filter: invert(1) !important; }
</style>
</head>
<body style="margin:0;padding:0;background-color:#f4f4f5;-webkit-text-size-adjust:100%;">
<div style="display:none;max-height:0;overflow:hidden;opacity:0;">Recibimos tu mensaje. Lo estamos revisando y coordinaremos una sesión contigo.</div>
<table role="presentation" width="100%" cellpadding="0" cellspacing="0" style="background-color:#f4f4f5;">
<tr><td align="center" style="padding:32px 16px;">
<table role="presentation" width="600" cellpadding="0" cellspacing="0" style="width:600px;max-width:600px;background-color:#ffffff;border:1px solid #e7e7ea;border-radius:14px;overflow:hidden;">

  <!-- Header -->
  <tr><td style="padding:34px 40px 22px 40px;text-align:center;background-color:#ffffff;">
    <img src="__LOGO_URL__" width="170" alt="Alphaqueb" class="aq-logo" style="display:inline-block;height:auto;border:0;">
  </td></tr>
  <tr><td style="padding:0 40px;"><div style="height:1px;background-color:#0c0d10;"></div></td></tr>

  <!-- Eyebrow + título -->
  <tr><td style="padding:30px 40px 0 40px;">
    <p style="margin:0 0 14px 0;font-family:'SFMono-Regular',Consolas,Menlo,monospace;font-size:11px;letter-spacing:2px;text-transform:uppercase;color:#16a34a;">
      &#9679; Recepción confirmada
    </p>
    <h1 style="margin:0;font-family:Georgia,'Times New Roman',serif;font-size:27px;line-height:1.25;color:#0c0d10;font-weight:600;">
      Hemos recibido tu mensaje.
    </h1>
  </td></tr>

  <!-- Cuerpo -->
  <tr><td style="padding:22px 40px 0 40px;font-family:Helvetica,Arial,sans-serif;font-size:15px;line-height:1.65;color:#3f3f46;">
    <p style="margin:0 0 16px 0;">__SALUDO__</p>
    <p style="margin:0 0 16px 0;">
      Gracias por escribirnos__COMPANY_BIT__. Tu mensaje ya está con nosotros y lo estamos
      revisando con atención. No es un acuse automático cualquiera: en Alphaqueb cada reto
      entra a un proceso real de evaluación.
    </p>
    <p style="margin:0 0 8px 0;">
      En breve coordinaremos una <strong style="color:#0c0d10;">sesión corta</strong> para entender tu
      operación y definir, con franqueza, si tenemos algo que aportar.
    </p>
  </td></tr>

  <!-- CTA -->
  <tr><td style="padding:28px 40px 4px 40px;" align="center">
    <table role="presentation" cellpadding="0" cellspacing="0"><tr>
      <td style="border-radius:9px;background-color:#0c0d10;">
        <a href="https://alphaqueb.com/#enfoque" target="_blank"
           style="display:inline-block;padding:13px 30px;font-family:Helvetica,Arial,sans-serif;font-size:14px;font-weight:600;color:#ffffff;text-decoration:none;border-radius:9px;">
          Conoce nuestro enfoque
        </a>
      </td>
    </tr></table>
  </td></tr>

  <tr><td style="padding:18px 40px 32px 40px;text-align:center;font-family:'SFMono-Regular',Consolas,Menlo,monospace;font-size:11px;letter-spacing:1px;color:#a1a1aa;">
    Respuesta en &lt; 24 h &middot; NDA disponible &middot; diagnóstico pagado de 30&ndash;40 h
  </td></tr>

  <!-- Footer -->
  <tr><td style="padding:28px 40px;background-color:#0c0d10;">
    <p style="margin:0 0 10px 0;font-family:Georgia,serif;font-size:15px;color:#ffffff;font-weight:600;">Alphaqueb</p>
    <p style="margin:0 0 16px 0;font-family:Helvetica,Arial,sans-serif;font-size:13px;line-height:1.6;color:#a1a1aa;">
      Construimos sistemas alrededor de tu operación, no al revés.<br>
      Datos que informan. Estrategias que transforman.
    </p>
    <p style="margin:0;font-family:'SFMono-Regular',Consolas,Menlo,monospace;font-size:11px;line-height:1.8;letter-spacing:0.5px;color:#71717a;">
      MONTERREY, NL &middot; OPERACIÓN NACIONAL<br>
      LUN&ndash;VIE &middot; 09:00&ndash;19:00 CDT<br>
      &copy; 2026 ALPHAQUEB
    </p>
  </td></tr>

</table>
</td></tr></table>
</body></html>
"""


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


def _build_full_name(data):
    first = (data.get("first_name") or "").strip()
    last = (data.get("last_name") or "").strip()
    full = " ".join(p for p in (first, last) if p).strip()
    if not full:
        full = (data.get("name") or "").strip()
    return full


def _notify_owner(env, lead, contact_name, email, phone, company, message):
    """Notifica al usuario interno (in-app + correo plano). Aislado: no rompe el alta."""
    try:
        user = env["res.users"].sudo().browse(NOTIFY_USER_ID).exists()
        if not user:
            return

        base_url = env["ir.config_parameter"].sudo().get_param(
            "web.base.url", ""
        ).rstrip("/")
        lead_url = ("%s/odoo/crm/%s" % (base_url, lead.id)) if base_url else ""

        # Suscribir y avisar dentro de Odoo (bell / inbox)
        if user.partner_id:
            try:
                lead.sudo().message_subscribe(partner_ids=[user.partner_id.id])
                lead.sudo().message_post(
                    body="Nueva oportunidad recibida desde el formulario web.",
                    partner_ids=[user.partner_id.id],
                    message_type="comment",
                    subtype_xmlid="mail.mt_comment",
                )
            except Exception:
                _logger.exception("No se pudo postear notificación in-app del lead %s", lead.id)

        # Correo plano a su buzón personal
        if user.email:
            lines = [
                "Nueva oportunidad recibida desde el formulario web.",
                "",
                "Nombre:   %s" % (contact_name or "-"),
                "Empresa:  %s" % (company or "-"),
                "Email:    %s" % (email or "-"),
                "Telefono: %s" % (phone or "-"),
                "",
                "Mensaje:",
                message or "(sin mensaje)",
            ]
            if lead_url:
                lines += ["", "Ver en Odoo: %s" % lead_url]
            text = "\n".join(lines)
            safe = text.replace("&", "&amp;").replace("<", "&lt;").replace(">", "&gt;")
            body_html = (
                "<pre style=\"font-family:Menlo,Consolas,monospace;"
                "white-space:pre-wrap;margin:0;\">%s</pre>" % safe
            )
            sender = env.company.email or "contacto@alphaqueb.com"
            mail = env["mail.mail"].sudo().create({
                "subject": "Nueva oportunidad: %s" % (contact_name or "sin nombre"),
                "email_from": "Alphaqueb CRM <%s>" % sender,
                "reply_to": email or sender,
                "email_to": user.email,
                "body_html": body_html,
                "auto_delete": True,
            })
            mail.send(raise_exception=False)
    except Exception:
        _logger.exception("No se pudo notificar al usuario %s del lead %s",
                          NOTIFY_USER_ID, getattr(lead, "id", "?"))


def _send_ack_email(env, to_email, first_name, company):
    """Envia el correo de acuse al prospecto. Aislado: nunca rompe el alta del lead."""
    if not to_email:
        return
    try:
        saludo = ("Hola %s," % first_name) if first_name else "Hola,"
        company_bit = (" desde %s" % company) if company else ""
        base_url = env["ir.config_parameter"].sudo().get_param(
            "web.base.url", "https://alphaqueb.com"
        ).rstrip("/")
        logo_url = "%s%s" % (base_url, LOGO_PATH)
        body = (ACK_EMAIL_HTML
                .replace("__LOGO_URL__", logo_url)
                .replace("__SALUDO__", saludo)
                .replace("__COMPANY_BIT__", company_bit))

        sender = env.company.email or "contacto@alphaqueb.com"
        mail = env["mail.mail"].sudo().create({
            "subject": "Hemos recibido tu mensaje — Alphaqueb Consulting",
            "email_from": "Alphaqueb Consulting <%s>" % sender,
            "reply_to": sender,
            "email_to": to_email,
            "body_html": body,
            "auto_delete": True,
        })
        mail.send(raise_exception=False)
    except Exception:
        _logger.exception("No se pudo enviar el correo de acuse a %s", to_email)


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
        if request.httprequest.method == "OPTIONS":
            return request.make_response("", headers=_cors_headers(), status=204)

        data = dict(kwargs)
        raw = request.httprequest.get_data(as_text=True)
        if raw:
            try:
                body = json.loads(raw)
                if isinstance(body, dict):
                    data.update(body)
            except (ValueError, TypeError):
                pass

        first_name = (data.get("first_name") or "").strip()
        contact_name = _build_full_name(data)
        email = (data.get("email") or "").strip()
        phone = (data.get("phone") or "").strip()
        company = (data.get("company") or data.get("company_name") or "").strip()
        message = (data.get("message") or "").strip()

        missing = []
        if not contact_name:
            missing.append("name (o first_name/last_name)")
        if not email:
            missing.append("email")
        if missing:
            return _json(
                {"status": "error", "message": "Faltan campos: %s" % ", ".join(missing)},
                status=400,
            )

        lead_title = company or contact_name

        try:
            lead = request.env["crm.lead"].sudo().create({
                "name": "Contacto web - %s" % lead_title,
                "contact_name": contact_name,
                "partner_name": company,
                "email_from": email,
                "phone": phone,
                "description": message,
                "type": "lead",
            })
        except Exception:
            _logger.exception("Error creando crm.lead desde /create_lead")
            return _json({"status": "error", "message": "Error interno al crear el lead."}, status=500)

        # Acuse al prospecto (no bloquea la respuesta)
        _send_ack_email(request.env, email, first_name, company)

        # Aviso interno (in-app + correo plano al dueño)
        _notify_owner(request.env, lead, contact_name, email, phone, company, message)

        return _json({"status": "success", "lead_id": lead.id}, status=201)