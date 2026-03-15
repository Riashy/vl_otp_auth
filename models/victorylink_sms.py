# -*- coding: utf-8 -*-
import requests
import uuid
import logging
from odoo import models, api, _

_logger = logging.getLogger(__name__)

class VictoryLinkSMS(models.AbstractModel):
    _name = 'victorylink.sms'
    _description = 'VictoryLink SMS Gateway Service'

    @api.model
    def send_otp_sms(self, phone_number, otp_code):
        """
        إرسال رسالة OTP عبر بوابة VictoryLink
        :param phone_number: رقم الموبايل (يجب أن يشمل كود الدولة بدون +)
        :param otp_code: الكود المراد إرساله
        :return: True في حالة النجاح، False في حالة الفشل
        """
        
        # 1. جلب بيانات الإعدادات المخزنة في النظام
        ICP = self.env['ir.config_parameter'].sudo()
        username = ICP.get_param('vl_otp.username')
        password = ICP.get_param('vl_otp.password')
        sender_id = ICP.get_param('vl_otp.sender_id')

        # التحقق من وجود الإعدادات
        if not all([username, password, sender_id]):
            _logger.error("VictoryLink: الإعدادات غير مكتملة. يرجى إدخال اسم المستخدم وكلمة المرور وSender ID.")
            return False

        # 2. تجهيز بيانات الرسالة والـ API
        # الرابط المذكور في الدكيومنتيشن للـ SendSMS
        url = "https://smsvas.vlserv.com/VLSMSPlatformResellerAPI/NewSendingAPI/api/SMSSender/SendSMS"
        
        # تنظيف رقم الهاتف (إزالة أي مسافات أو علامة +)
        clean_phone = phone_number.replace('+', '').replace(' ', '')
        
        # نص الرسالة (يمكنك تعديله)
        message_text = _("Your verification code is: %s") % otp_code

        # البيانات المطلوبة حسب صفحة 5 في المستند
        payload = {
            "UserName": username,
            "Password": password,
            "SMSText": message_text,
            "SMSLang": "e",         # "e" للإنجليزية، "a" للعربية
            "SMSSender": sender_id,
            "SMSReceiver": clean_phone,
            "SMSID": str(uuid.uuid4()) # معرف فريد لكل رسالة لمنع التكرار
        }

        # 3. تنفيذ طلب الإرسال
        try:
            _logger.info(f"VictoryLink: Sending SMS to {clean_phone}")
            response = requests.post(url, json=payload, timeout=15)
            
            if response.status_code == 200:
                result_code = int(response.json())
                return self._handle_response_code(result_code)
            else:
                _logger.error(f"VictoryLink: Connection Error. HTTP Status: {response.status_code}")
                return False

        except Exception as e:
            _logger.error(f"VictoryLink: Exception occurred: {str(e)}")
            return False

    def _handle_response_code(self, code):
        """
        التعامل مع أكواد الرد الخاصة بـ VictoryLink (صفحة 26 من الدكيومنتيشن)
        """
        error_mapping = {
            0: "تم الإرسال بنجاح",
            -1: "خطأ: اسم المستخدم أو كلمة المرور غير صحيحة",
            -5: "خطأ: رصيدك غير كافٍ لإرسال الرسالة",
            -10: "خطأ: رقم المستلم غير صحيح",
            -11: "خطأ: اسم المرسل (Sender ID) غير مفعل أو غير صحيح",
            -12: "خطأ: المعاملات المفقودة (Missing Parameters)",
            -13: "خطأ: لغة الرسالة غير مدعومة",
            -25: "خطأ: معرف الرسالة (SMSID) مكرر"
        }

        if code == 0:
            _logger.info("VictoryLink: SMS sent successfully.")
            return True
        else:
            msg = error_mapping.get(code, f"خطأ غير معروف برقم: {code}")
            _logger.warning(f"VictoryLink Error: {msg}")
            return False