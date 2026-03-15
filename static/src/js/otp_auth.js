/** @odoo-module **/

import publicWidget from "@web/legacy/js/public/public_widget";
import { jsonrpc } from "@web/core/network/rpc_service";

publicWidget.registry.VlOtpAuth = publicWidget.Widget.extend({
    selector: '#vl_otp_login_section, #vl_checkout_otp_section', // العناصر التي سيعمل عليها الكود
    events: {
        'click #btn_send_otp': '_onSendOtpClick',
        'click #btn_verify_otp': '_onVerifyOtpClick',
        'click #btn_send_checkout_otp': '_onSendCheckoutOtpClick',
        'click #btn_verify_checkout_otp': '_onVerifyCheckoutOtpClick',
    },

    // --- وظائف صفحة تسجيل الدخول ---
    _onSendOtpClick: function (ev) {
        var mobile = this.$('#mobile_number').val();
        var $msg = this.$('#otp_message');
        
        if (!mobile) {
            $msg.text('يرجى إدخال رقم الموبايل أولاً.').css('color', 'red');
            return;
        }

        $msg.text('جاري الإرسال...').css('color', 'blue');
        
        jsonrpc('/otp/send', { phone_number: mobile }).then(function (result) {
            if (result.status === 'success') {
                this.$('#otp_code_container').slideDown();
                $msg.text('تم إرسال رمز التحقق إلى هاتفك.').css('color', 'green');
            } else {
                $msg.text('حدث خطأ: ' + result.message).css('color', 'red');
            }
        }.bind(this));
    },

    _onVerifyOtpClick: function (ev) {
        var code = this.$('#otp_code').val();
        var $msg = this.$('#otp_message');

        if (!code) {
            $msg.text('يرجى إدخال رمز التحقق.').css('color', 'red');
            return;
        }

        $msg.text('جاري التحقق...').css('color', 'blue');

        jsonrpc('/otp/verify', { entered_otp: code }).then(function (result) {
            if (result.status === 'success') {
                $msg.text('تم التحقق بنجاح! جاري تسجيل الدخول...').css('color', 'green');
                window.location.href = '/my'; // إعادة التوجيه لصفحة حسابي
            } else {
                $msg.text('الرمز غير صحيح أو منتهي الصلاحية.').css('color', 'red');
            }
        });
    },

    // --- وظائف صفحة الدفع (Checkout) ---
    _onSendCheckoutOtpClick: function (ev) {
        var mobile = this.$('#checkout_mobile').val();
        var $msg = this.$('#checkout_otp_message');
        
        if (!mobile) {
            $msg.text('يرجى التأكد من كتابة رقم الموبايل.').css('color', 'red');
            return;
        }

        $msg.text('جاري إرسال الرمز...').css('color', 'blue');
        
        jsonrpc('/otp/send', { phone_number: mobile }).then(function (result) {
            if (result.status === 'success') {
                this.$('#checkout_otp_container').slideDown();
                $msg.text('تم الإرسال بنجاح. أدخل الكود بالأسفل.').css('color', 'green');
            } else {
                $msg.text('خطأ في الإرسال: ' + result.message).css('color', 'red');
            }
        }.bind(this));
    },

    _onVerifyCheckoutOtpClick: function (ev) {
        var code = this.$('#checkout_otp_code').val();
        var $msg = this.$('#checkout_otp_message');

        jsonrpc('/otp/verify', { entered_otp: code }).then(function (result) {
            if (result.status === 'success') {
                $msg.text('تم التحقق من الهاتف بنجاح! يمكنك الآن إتمام الدفع.').css('color', 'green');
                this.$('#is_otp_verified').val('1');
                this.$('#checkout_otp_container').slideUp();
                this.$('#checkout_mobile').prop('readonly', true);
                this.$('#btn_send_checkout_otp').hide();
                // يمكنك هنا إضافة كود لتمكين (Enable) زر الدفع الأساسي لأودو إذا كنت قد قمت بتعطيله مسبقاً
            } else {
                $msg.text('الرمز غير صحيح. حاول مرة أخرى.').css('color', 'red');
            }
        }.bind(this));
    }
});
// ... تابع للكود السابق داخل publicWidget.registry.VlOtpAuth ...

    start: function () {
        this._super.apply(this, arguments);
        // تعطيل زر الدفع عند تحميل صفحة الدفع
        this._togglePayButton(false);
        return Promise.resolve();
    },

    _togglePayButton: function (enabled) {
        var $payButton = $('#o_payment_form_pay_button'); // معرف زر الدفع الافتراضي في أودو
        if ($payButton.length > 0) {
            $payButton.prop('disabled', !enabled);
            if (!enabled) {
                $payButton.addClass('disabled').attr('title', 'يرجى التحقق من رقم الموبايل أولاً');
            } else {
                $payButton.removeClass('disabled').removeAttr('title');
            }
        }
    },

    // تحديث دالة التحقق لتفعيل الزر عند النجاح
    _onVerifyCheckoutOtpClick: function (ev) {
        var code = this.$('#checkout_otp_code').val();
        var $msg = this.$('#checkout_otp_message');

        jsonrpc('/otp/send', { entered_otp: code }).then(function (result) {
            if (result.status === 'success') {
                $msg.text('تم التحقق بنجاح!').css('color', 'green');
                this.$('#is_otp_verified').val('1');
                this._togglePayButton(true); // <--- تفعيل زر الدفع هنا
                this.$('#checkout_otp_container').slideUp();
            } else {
                $msg.text('الرمز خطأ.').css('color', 'red');
            }
        }.bind(this));
    }