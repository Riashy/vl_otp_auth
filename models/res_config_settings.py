from odoo import fields, models

class ResConfigSettings(models.TransientModel):
    _inherit = 'res.config.settings'

    vl_username = fields.Char(string='VictoryLink Username', config_parameter='vl_otp.username')
    vl_password = fields.Char(string='VictoryLink Password', config_parameter='vl_otp.password')
    vl_sender_id = fields.Char(string='VictoryLink Sender ID', config_parameter='vl_otp.sender_id')
    vl_allow_registration = fields.Boolean(string='Allow OTP Registration', config_parameter='vl_otp.allow_registration', default=True)