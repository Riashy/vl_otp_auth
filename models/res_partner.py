from odoo import api, fields, models


class ResPartner(models.Model):
    _inherit = "res.partner"

    otp_mobile_verified = fields.Boolean(
        string="Mobile Verified By OTP",
        default=False,
        copy=False,
    )
    otp_mobile_verified_at = fields.Datetime(copy=False)
    otp_mobile_digits = fields.Char(
        string="OTP Mobile Digits",
        compute="_compute_otp_mobile_digits",
        store=True,
        index=True,
        copy=False,
    )

    @api.depends("mobile", "phone")
    def _compute_otp_mobile_digits(self):
        gateway = self.env["vl.sms.gateway"]
        for partner in self:
            partner.otp_mobile_digits = gateway._only_digits(partner.mobile or partner.phone)
