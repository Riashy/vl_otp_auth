from odoo import _, api, fields, models
from odoo.exceptions import ValidationError


class ResUsers(models.Model):
    _inherit = "res.users"

    otp_login_enabled = fields.Boolean(
        string="Allow OTP Login",
        default=True,
        help="If enabled, this user can log in with mobile + OTP.",
    )
    otp_mobile_verified = fields.Boolean(
        string="Mobile Verified By OTP",
        default=False,
        readonly=True,
        copy=False,
    )
    otp_mobile_digits = fields.Char(
        string="OTP Mobile Digits",
        compute="_compute_otp_mobile_digits",
        store=True,
        index=True,
        copy=False,
    )

    @api.depends("mobile")
    def _compute_otp_mobile_digits(self):
        gateway = self.env["vl.sms.gateway"]
        for user in self:
            user.otp_mobile_digits = gateway._only_digits(user.mobile)

    @api.constrains("otp_mobile_digits", "otp_login_enabled", "active")
    def _check_unique_otp_mobile(self):
        for user in self:
            if not user.active or not user.otp_login_enabled or not user.otp_mobile_digits:
                continue
            duplicate = self.sudo().search([
                ("id", "!=", user.id),
                ("active", "=", True),
                ("otp_login_enabled", "=", True),
                ("otp_mobile_digits", "=", user.otp_mobile_digits),
            ], limit=1)
            if duplicate:
                raise ValidationError(
                    _("The mobile number used for OTP must be unique across active OTP-enabled users.")
                )

    @api.model
    def _otp_login_domain(self):
        cfg = self.env["vl.sms.gateway"]._get_config()
        domain = [("active", "=", True), ("otp_login_enabled", "=", True)]
        allow_employee = cfg["allow_employee_login"]
        allow_portal = cfg["allow_portal_login"]
        if allow_employee and not allow_portal:
            domain.append(("share", "=", False))
        elif allow_portal and not allow_employee:
            domain.append(("share", "=", True))
        elif not allow_employee and not allow_portal:
            domain.append(("id", "=", 0))
        return domain

    @api.model
    def find_user_for_otp(self, raw_mobile):
        candidates = self.env["vl.sms.gateway"].build_mobile_candidates(raw_mobile)
        if not candidates:
            return self.browse()

        users = self.sudo().search(self._otp_login_domain() + [("otp_mobile_digits", "in", candidates)])
        if not users:
            return users
        exact = users.filtered(lambda user: user.otp_mobile_digits == self.env["vl.sms.gateway"]._only_digits(raw_mobile))
        return exact[:1] or users[:1]
