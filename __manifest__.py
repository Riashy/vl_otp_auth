{
    "name": "Victory Link OTP Authentication",
    "summary": "OTP login, signup, and website checkout verification for Odoo using Victory Link SMS gateway",
    "version": "17.0.2.0.0",
    "category": "Authentication",
    "author": "OpenAI",
    "license": "LGPL-3",
    "depends": ["base", "web", "website", "website_sale", "auth_signup", "base_setup"],
    "data": [
        "security/ir.model.access.csv",
        "data/ir_cron.xml",
        "views/res_config_settings_views.xml",
        "views/res_users_views.xml",
        "views/vl_otp_code_views.xml",
        "views/login_templates.xml",
        "views/signup_templates.xml",
        "views/website_sale_templates.xml",
    ],
    "assets": {
        "web.assets_frontend": [
            "vl_otp_auth/static/src/css/otp_auth.css",
        ],
    },
    "installable": True,
    "application": False,
}
