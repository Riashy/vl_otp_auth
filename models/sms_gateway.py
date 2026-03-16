import json
import logging
import re
import uuid
from urllib.parse import urlparse

import requests

from odoo import _, api, models
from odoo.exceptions import UserError

_logger = logging.getLogger(__name__)


class VlSmsGateway(models.AbstractModel):
    _name = "vl.sms.gateway"
    _description = "Victory Link SMS Gateway"

    DEFAULT_SEND_URL = "https://smsvas.vlserv.com/VLSMSPlatformResellerAPI/NewSendingAPI/api/SMSSender/SendSMS"
    DEFAULT_CREDIT_URL = "https://smsvas.vlserv.com//VLSMSPlatformResellerAPI/CheckCreditApi/api/CheckCredit"

    @api.model
    def _icp(self):
        return self.env["ir.config_parameter"].sudo()

    @api.model
    def _get_config(self):
        icp = self._icp()
        return {
            "login_enabled": icp.get_param("vl_otp_auth.login_enabled", "False") == "True",
            "allow_employee_login": icp.get_param("vl_otp_auth.allow_employee_login", "True") == "True",
            "allow_portal_login": icp.get_param("vl_otp_auth.allow_portal_login", "True") == "True",
            "gateway_username": (icp.get_param("vl_otp_auth.gateway_username") or "").strip(),
            "gateway_password": (icp.get_param("vl_otp_auth.gateway_password") or "").strip(),
            "gateway_sender": (icp.get_param("vl_otp_auth.gateway_sender") or "").strip(),
            "gateway_send_url": (icp.get_param("vl_otp_auth.gateway_send_url") or self.DEFAULT_SEND_URL).strip(),
            "gateway_credit_url": (icp.get_param("vl_otp_auth.gateway_credit_url") or self.DEFAULT_CREDIT_URL).strip(),
            "default_country_code": re.sub(r"\D", "", icp.get_param("vl_otp_auth.default_country_code") or "20"),
            "otp_expiry_minutes": int(icp.get_param("vl_otp_auth.otp_expiry_minutes") or 5),
            "otp_code_length": int(icp.get_param("vl_otp_auth.otp_code_length") or 6),
            "otp_max_attempts": int(icp.get_param("vl_otp_auth.otp_max_attempts") or 5),
            "otp_resend_interval_seconds": int(icp.get_param("vl_otp_auth.otp_resend_interval_seconds") or 60),
            "otp_sms_template": icp.get_param(
                "vl_otp_auth.otp_sms_template",
                default="Your verification code is {code}. It expires in {minutes} minutes.",
            )
            or "Your verification code is {code}. It expires in {minutes} minutes.",
        }

    @api.model
    def _is_configured(self):
        cfg = self._get_config()
        return bool(cfg["gateway_username"] and cfg["gateway_password"] and cfg["gateway_sender"])

    @api.model
    def _assert_ready(self):
        cfg = self._get_config()
        if not cfg["login_enabled"]:
            raise UserError(_("OTP login is disabled from settings."))
        missing = []
        if not cfg["gateway_username"]:
            missing.append(_("Gateway Username"))
        if not cfg["gateway_password"]:
            missing.append(_("Gateway Password"))
        if not cfg["gateway_sender"]:
            missing.append(_("Sender Name"))
        if missing:
            raise UserError(_("Missing SMS gateway settings: %s") % ", ".join(missing))
        return cfg

    @api.model
    def _status_messages(self):
        return {
            0: _("Success"),
            -1: _("Invalid credentials"),
            -2: _("Invalid account IP"),
            -3: _("Invalid ANI black list"),
            -5: _("Out of credit"),
            -6: _("Database down"),
            -7: _("Inactive account"),
            -11: _("Account is expired"),
            -12: _("SMS text is empty"),
            -13: _("Invalid sender with connection"),
            -14: _("SMS sending failed, try again"),
            -16: _("User cannot send with DLR"),
            -18: _("Invalid ANI"),
            -19: _("SMS ID already exists"),
            -21: _("Invalid account"),
            -22: _("SMS not validated yet"),
            -23: _("Invalid account operator connection"),
            -26: _("Invalid user SMS ID"),
            -29: _("Empty user name or password"),
            -30: _("Invalid sender"),
            -31: _("Invalid start time"),
            -32: _("Invalid SMS template or items"),
            -100: _("Other error"),
            1: _("Delivered to phone / or 1 credit on CheckCredit"),
            2: _("Not delivered to phone / or 2 credits on CheckCredit"),
            3: _("Queued / or 3 credits on CheckCredit"),
            4: _("Sent without receiving DLR / or 4 credits on CheckCredit"),
            5: _("Failed / or 5 credits on CheckCredit"),
        }

    @api.model
    def describe_status(self, code):
        try:
            code = int(code)
        except Exception:
            return _("Unknown status")
        return self._status_messages().get(code, _("Unknown status"))

    @api.model
    def _only_digits(self, value):
        return re.sub(r"\D", "", value or "")

    @api.model
    def build_mobile_candidates(self, raw_mobile):
        cfg = self._get_config()
        cc = self._only_digits(cfg["default_country_code"])
        digits = self._only_digits(raw_mobile)
        candidates = set()
        if not digits:
            return []
        candidates.add(digits)
        if digits.startswith("00") and len(digits) > 2:
            candidates.add(digits[2:])
        if cc:
            if digits.startswith("0") and len(digits) > 1:
                candidates.add(cc + digits[1:])
            if digits.startswith(cc) and len(digits) > len(cc):
                candidates.add("0" + digits[len(cc):])
            if digits.startswith("00" + cc) and len(digits) > len(cc) + 2:
                candidates.add(cc + digits[len(cc) + 2 :])
        return [item for item in candidates if item]

    @api.model
    def normalize_mobile_for_gateway(self, raw_mobile):
        cfg = self._get_config()
        cc = self._only_digits(cfg["default_country_code"])
        digits = self._only_digits(raw_mobile)
        if not digits:
            return ""
        if digits.startswith("00"):
            digits = digits[2:]
        if cc and digits.startswith("0"):
            digits = cc + digits[1:]
        return digits

    @api.model
    def guess_sms_lang(self, text):
        return "A" if re.search(r"[\u0600-\u06FF]", text or "") else "E"

    @api.model
    def _parse_status_code(self, response):
        text = (response.text or "").strip()
        try:
            data = response.json()
        except Exception:
            data = None

        if isinstance(data, int):
            return data
        if isinstance(data, str) and re.fullmatch(r"-?\d+", data.strip()):
            return int(data.strip())
        if isinstance(data, dict):
            for key in ("status", "statusCode", "code", "result", "SendSMSResult", "CheckCreditResult"):
                value = data.get(key)
                if isinstance(value, int):
                    return value
                if isinstance(value, str) and re.fullmatch(r"-?\d+", value.strip()):
                    return int(value.strip())
        if re.fullmatch(r"-?\d+", text):
            return int(text)
        raise UserError(
            _("Unexpected SMS gateway response: %s") % (text[:250] or response.reason or _("empty response"))
        )

    @api.model
    def _validate_url(self, url):
        parsed = urlparse(url)
        if parsed.scheme not in ("http", "https") or not parsed.netloc:
            raise UserError(_("Invalid SMS gateway URL: %s") % url)
        return url

    @api.model
    def send_sms(self, to_mobile, message, sms_id=None):
        cfg = self._assert_ready()
        url = self._validate_url(cfg["gateway_send_url"])
        mobile = self.normalize_mobile_for_gateway(to_mobile)
        if not mobile:
            raise UserError(_("Mobile number is empty."))
        sms_id = sms_id or str(uuid.uuid4())
        payload = {
            "UserName": cfg["gateway_username"],
            "Password": cfg["gateway_password"],
            "SMSText": message,
            "SMSLang": self.guess_sms_lang(message),
            "SMSSender": cfg["gateway_sender"],
            "SMSReceiver": mobile,
            "SMSID": sms_id,
        }
        _logger.info("Sending OTP SMS through Victory Link to %s", mobile)
        try:
            response = requests.post(url, json=payload, timeout=20)
            response.raise_for_status()
        except requests.RequestException as exc:
            raise UserError(_("Could not reach the SMS gateway: %s") % str(exc)) from exc

        status_code = self._parse_status_code(response)
        return {
            "sms_id": sms_id,
            "mobile": mobile,
            "status_code": status_code,
            "status_message": self.describe_status(status_code),
            "ok": status_code == 0,
            "raw_response": (response.text or "")[:1000],
        }

    @api.model
    def check_credit(self):
        cfg = self._assert_ready()
        url = self._validate_url(cfg["gateway_credit_url"])
        payload = {
            "UserName": cfg["gateway_username"],
            "Password": cfg["gateway_password"],
        }
        try:
            response = requests.post(url, json=payload, timeout=20)
            response.raise_for_status()
        except requests.RequestException as exc:
            raise UserError(_("Could not check SMS credit: %s") % str(exc)) from exc
        code = self._parse_status_code(response)
        return {
            "status_code": code,
            "status_message": self.describe_status(code),
            "raw_response": (response.text or "")[:1000],
        }
