from odoo import fields, models


class SaleOrder(models.Model):
    _inherit = "sale.order"

    otp_checkout_verified = fields.Boolean(copy=False, default=False)
    otp_checkout_mobile = fields.Char(copy=False)
    otp_checkout_verified_at = fields.Datetime(copy=False)
