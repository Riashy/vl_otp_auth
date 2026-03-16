import hashlib
import hmac
import secrets
import uuid
from datetime import timedelta

from odoo import _, api, fields, models
from odoo.exceptions import UserError
from dateutil.relativedelta import relativedelta


class VlOtpCode(models.Model):
    _name = "vl.otp.code"
    _description = "OTP Code"
    _order = "id desc"

    user_id = fields.Many2one("res.users", required=True, index=True, ondelete="cascade")
    login = fields.Char(related="user_id.login", store=True, index=True)
    mobile = fields.Char(required=True)
    mobile_digits = fields.Char(required=True, index=True)
    purpose = fields.Selection(
        [("login", "Login"), ("signup", "Signup"), ("checkout", "Checkout")],
        default="login",
        required=True,
        index=True,
    )
    request_token = fields.Char(required=True, index=True, copy=False)
    sms_id = fields.Char(copy=False)
    code_hash = fields.Char(required=True, copy=False)
    salt = fields.Char(required=True, copy=False)
    state = fields.Selection(
        [
            ("pending", "Pending"),
            ("used", "Used"),
            ("expired", "Expired"),
            ("failed", "Failed"),
        ],
        default="pending",
        required=True,
        index=True,
    )
    expires_at = fields.Datetime(required=True, index=True)
    used_at = fields.Datetime()
    attempts = fields.Integer(default=0)
    max_attempts = fields.Integer(default=5)
    gateway_status_code = fields.Integer()
    gateway_status_message = fields.Char()
    last_error = fields.Char()
    ip_address = fields.Char()
    user_agent = fields.Char()

    def name_get(self):
        return [(rec.id, "%s [%s]" % (rec.mobile, rec.state)) for rec in self]

    @api.model
    def _hash_code(self, code, salt):
        raw = "%s:%s" % (salt, code)
        return hashlib.sha256(raw.encode("utf-8")).hexdigest()

    @api.model
    def _generate_code(self, length):
        digits = "0123456789"
        return "".join(secrets.choice(digits) for _ in range(length))

    @api.model
    def _now(self):
        return fields.Datetime.now()

    @api.model
    def _cleanup_expired_pending(self):
        expired = self.sudo().search([
            ("state", "=", "pending"),
            ("expires_at", "<", self._now()),
        ])
        if expired:
            expired.write({"state": "expired", "last_error": _("Expired automatically")})

    @api.model
    def issue_code(self, user, mobile=None, purpose="login"):
        self._cleanup_expired_pending()
        gateway = self.env["vl.sms.gateway"]
        cfg = gateway._assert_ready()
        user = user.sudo()
        if not user.exists():
            raise UserError(_("User not found."))
        if not user.otp_login_enabled:
            raise UserError(_("OTP login is disabled for this user."))

        raw_mobile = mobile or user.mobile
        mobile_digits = gateway._only_digits(raw_mobile)
        if not mobile_digits:
            raise UserError(_("This user does not have a mobile number configured."))

        wait_seconds = int(cfg["otp_resend_interval_seconds"])
        if wait_seconds > 0:
            recent = self.sudo().search([
                ("user_id", "=", user.id),
                ("purpose", "=", purpose),
                ("state", "=", "pending"),
                ("create_date", ">=", self._now() - timedelta(seconds=wait_seconds)),
            ], limit=1)
            if recent:
                remaining = max(1, wait_seconds - int((self._now() - recent.create_date).total_seconds()))
                raise UserError(_("Please wait %s seconds before requesting a new code.") % remaining)

        self.sudo().search([
            ("user_id", "=", user.id),
            ("purpose", "=", purpose),
            ("state", "=", "pending"),
        ]).write({"state": "expired", "last_error": _("Superseded by a newer OTP")})

        code = self._generate_code(int(cfg["otp_code_length"]))
        salt = uuid.uuid4().hex
        expiry_minutes = int(cfg["otp_expiry_minutes"])
        request_token = uuid.uuid4().hex
        message = cfg["otp_sms_template"].format(code=code, minutes=expiry_minutes)

        record = self.sudo().create({
            "user_id": user.id,
            "mobile": raw_mobile,
            "mobile_digits": mobile_digits,
            "purpose": purpose,
            "request_token": request_token,
            "salt": salt,
            "code_hash": self._hash_code(code, salt),
            "expires_at": self._now() + timedelta(minutes=expiry_minutes),
            "max_attempts": int(cfg["otp_max_attempts"]),
            "ip_address": self.env.context.get("vl_otp_ip_address"),
            "user_agent": self.env.context.get("vl_otp_user_agent"),
        })

        result = gateway.send_sms(raw_mobile, message)
        record.write({
            "sms_id": result["sms_id"],
            "gateway_status_code": result["status_code"],
            "gateway_status_message": result["status_message"],
        })
        if not result["ok"]:
            record.write({
                "state": "failed",
                "last_error": result["status_message"],
            })
            raise UserError(_("SMS gateway rejected the OTP request: %s") % result["status_message"])
        return record

    @api.model
    def verify_code(self, user, raw_mobile, code, purpose="login"):
        self._cleanup_expired_pending()
        gateway = self.env["vl.sms.gateway"]
        candidates = gateway.build_mobile_candidates(raw_mobile)
        if not candidates:
            raise UserError(_("Invalid or expired verification code."))

        record = self.sudo().search([
            ("user_id", "=", user.id),
            ("purpose", "=", purpose),
            ("state", "=", "pending"),
            ("mobile_digits", "in", candidates),
        ], order="id desc", limit=1)

        if not record or record.expires_at < self._now():
            if record:
                record.write({"state": "expired", "last_error": _("OTP expired")})
            raise UserError(_("Invalid or expired verification code."))

        record.attempts += 1
        if record.attempts > record.max_attempts:
            record.write({"state": "failed", "last_error": _("Too many wrong attempts")})
            raise UserError(_("Too many invalid attempts. Request a new code."))

        expected = self._hash_code(code or "", record.salt)
        if not hmac.compare_digest(expected, record.code_hash):
            if record.attempts >= record.max_attempts:
                record.write({"state": "failed", "last_error": _("Too many wrong attempts")})
                raise UserError(_("Too many invalid attempts. Request a new code."))
            raise UserError(_("Invalid or expired verification code."))

        record.write({
            "state": "used",
            "used_at": self._now(),
            "last_error": False,
        })
        user.write({"otp_mobile_verified": True})
        return record

    @api.model
    def cron_cleanup_codes(self):
        self._cleanup_expired_pending()
        cutoff = self._now() - relativedelta(days=7)
        old_records = self.sudo().search([
            ("state", "in", ["used", "expired", "failed"]),
            ("write_date", "<", cutoff),
        ])
        old_records.unlink()
        return True
