# -*- coding: utf-8 -*-
import random
import logging
from odoo import http, _
from odoo.http import request

_logger = logging.getLogger(__name__)

class VictoryLinkOtpController(http.Controller):

    @http.route('/otp/send', type='json', auth='public', website=True)
    def send_otp(self, phone_number):
        """
        توليد وإرسال كود OTP
        """
        if not phone_number:
            return {'status': 'error', 'message': _('يرجى إدخال رقم الموبايل')}

        # 1. توليد كود عشوائي من 6 أرقام
        otp_code = str(random.randint(100000, 999999))
        
        # 2. حفظ الكود ورقم الهاتف في جلسة المستخدم (Session) بشكل مؤقت
        request.session['vl_otp_code'] = otp_code
        request.session['vl_otp_phone'] = phone_number

        # 3. استدعاء موديل الإرسال الذي قمنا ببرمجته
        success = request.env['victorylink.sms'].sudo().send_otp_sms(phone_number, otp_code)
        
        if success:
            # ملاحظة للمطور: في بيئة التجربة يمكنك طباعة الكود في الـ Log
            _logger.info(f"OTP for {phone_number} is {otp_code}")
            return {'status': 'success', 'message': _('تم إرسال كود التحقق بنجاح')}
        else:
            return {'status': 'error', 'message': _('فشل في إرسال الرسالة، يرجى المحاولة لاحقاً')}

    @http.route('/otp/verify', type='json', auth='public', website=True)
    def verify_otp(self, entered_otp):
        """
        التحقق من الكود وتسجيل الدخول أو الإنشاء
        """
        session_otp = request.session.get('vl_otp_code')
        phone_number = request.session.get('vl_otp_phone')

        # 1. التأكد من صحة الكود
        if not session_otp or str(entered_otp) != session_otp:
            return {'status': 'error', 'message': _('كود التحقق غير صحيح')}

        # 2. البحث عن المستخدم برقم الهاتف (المسجل كـ login)
        user = request.env['res.users'].sudo().search([('login', '=', phone_number)], limit=1)
        
        # جلب إعدادات السماح بالتسجيل
        ICP = request.env['ir.config_parameter'].sudo()
        allow_registration = ICP.get_param('vl_otp.allow_registration')

        if not user:
            if allow_registration:
                # 3. إنشاء مستخدم جديد إذا كان غير موجود والتسجيل مسموح
                user = self._create_otp_user(phone_number)
            else:
                return {'status': 'error', 'message': _('هذا الرقم غير مسجل لدينا، والتسجيل الجديد مغلق')}

        # 4. تسجيل الدخول يدوياً
        # نقوم بتحديث الجلسة بمعرف المستخدم
        request.session.uid = user.id
        # مسح بيانات OTP من الجلسة للأمان
        request.session.pop('vl_otp_code', None)
        
        return {
            'status': 'success', 
            'message': _('تم التحقق بنجاح'),
            'redirect': '/my' # التوجيه لصفحة الحساب
        }

    def _create_otp_user(self, phone):
        """
        دالة مساعدة لإنشاء مستخدم جديد برقم الموبايل
        """
        # جلب مجموعة "Portal" ليكون المستخدم عميل موقع
        portal_group = request.env.ref('base.group_portal')
        
        user_vals = {
            'name': _('عميل موبايل: %s') % phone,
            'login': phone,
            'mobile': phone,
            'email': f"{phone}@otp.user", # بريد وهمي لأن الحقل مطلوب أحياناً
            'groups_id': [(6, 0, [portal_group.id])],
            'active': True,
        }
        # إنشاء المستخدم بصلاحيات السوبر أدمن
        new_user = request.env['res.users'].sudo().create(user_vals)
        return new_user