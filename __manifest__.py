{
    'name': 'VictoryLink OTP Authentication',
    'version': '1.0',
    'category': 'Website',
    'summary': 'Login and Checkout using VictoryLink SMS OTP',
    'depends': ['base', 'web', 'website_sale', 'auth_signup'],
    'data': [
        'views/res_config_settings_views.xml',
        'views/templates.xml', # ملف الواجهات الجديد
    ],
    'assets': {
        'web.assets_frontend': [
            'vl_otp_auth/static/src/js/otp_auth.js', # ملف الجافاسكريبت
        ],
    },
    'installable': True,
    'application': False,
}