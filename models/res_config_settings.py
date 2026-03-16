from odoo import api, fields, models

class ResConfigSettings(models.TransientModel):
    _inherit = "res.config.settings"

    login_enabled = fields.Boolean(string="Enable OTP Login", config_parameter="vl_otp_auth.login_enabled")
    allow_employee_login = fields.Boolean(string="Allow Employee / Backend Login", config_parameter="vl_otp_auth.allow_employee_login", default=True)
    allow_portal_login = fields.Boolean(string="Allow Portal / Website Login", config_parameter="vl_otp_auth.allow_portal_login", default=True)
    
    # سنقوم بتعريف الحقلين لتجنب أي تعارض في الـ XML
    gateway_username = fields.Char(string="Gateway Username", config_parameter="vl_otp_auth.gateway_username")
    vl_username = fields.Char(string="VL Username", config_parameter="vl_otp_auth.vl_username")
    
    gateway_password = fields.Char(string="Gateway Password", config_parameter="vl_otp_auth.gateway_password")
    gateway_sender = fields.Char(string="Sender Name", config_parameter="vl_otp_auth.gateway_sender")
    gateway_send_url = fields.Char(string="Send API URL", config_parameter="vl_otp_auth.gateway_send_url", default="https://smsvas.vlserv.com/VLSMSPlatformResellerAPI/NewSendingAPI/api/SMSSender/SendSMS")
    gateway_credit_url = fields.Char(string="Check Credit API URL", config_parameter="vl_otp_auth.gateway_credit_url", default="https://smsvas.vlserv.com//VLSMSPlatformResellerAPI/CheckCreditApi/api/CheckCredit")
    
    default_country_code = fields.Char(string="Default Country Code", config_parameter="vl_otp_auth.default_country_code", default="20")
    otp_code_length = fields.Integer(string="OTP Length", config_parameter="vl_otp_auth.otp_code_length", default=6)
    otp_expiry_minutes = fields.Integer(string="OTP Expiry (Minutes)", config_parameter="vl_otp_auth.otp_expiry_minutes", default=5)
    otp_max_attempts = fields.Integer(string="Maximum Verification Attempts", config_parameter="vl_otp_auth.otp_max_attempts", default=5)
    otp_resend_interval_seconds = fields.Integer(string="Minimum Seconds Before Resend", config_parameter="vl_otp_auth.otp_resend_interval_seconds", default=60)
    otp_sms_template = fields.Text(string="OTP SMS Template", config_parameter="vl_otp_auth.otp_sms_template", default="Your verification code is {code}. It expires in {minutes} minutes.")
    gateway_credit_status = fields.Char(string="Gateway Credit Status", readonly=True)

    @api.onchange("otp_code_length")
    def _onchange_otp_code_length(self):
        if self.otp_code_length:
            if self.otp_code_length < 4: self.otp_code_length = 4
            if self.otp_code_length > 10: self.otp_code_length = 10

    def action_check_vl_credit(self):
        self.ensure_one()
        try:
            result = self.env["vl.sms.gateway"].check_credit()
            self.gateway_credit_status = "%s (%s)" % (result.get("status_code", ""), result.get("status_message", ""))
        except Exception as e:
            self.gateway_credit_status = "Error: %s" % str(e)
            
        return {
            "type": "ir.actions.client",
            "tag": "display_notification",
            "params": {
                "title": "Victory Link",
                "message": self.gateway_credit_status,
                "type": "info",
                "sticky": False,
            },
        }
