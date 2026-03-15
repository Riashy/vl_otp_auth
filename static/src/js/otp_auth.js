/** @odoo-module **/
import publicWidget from "@web/legacy/js/public/public_widget";
import { jsonrpc } from "@web/core/network/rpc_service";

publicWidget.registry.VlOtpAuth = publicWidget.widget.extend({
    selector: '#vl_otp_login_section',
    events: {
        'click #btn_send_otp': '_onSendOtp',
        'click #btn_verify_otp': '_onVerifyOtp',
    },

    _onSendOtp: function (ev) {
        ev.preventDefault();
        var self = this;
        var phone = this.$('#mobile_number').val();
        var $msg = this.$('#otp_message');

        if (!phone) {
            $msg.text("يرجى إدخال رقم الهاتف").css("color", "red");
            return;
        }

        $msg.text("جاري الإرسال...").css("color", "blue");

        jsonrpc('/otp/send', {
            phone_number: phone,
        }).then(function (result) {
            if (result.status === 'success') {
                $msg.text("تم إرسال الكود بنجاح!").css("color", "green");
                self.$('#otp_code_container').fadeIn();
                self.$('#btn_send_otp').text("إعادة إرسال الكود");
            } else {
                $msg.text(result.message || "خطأ في الإرسال").css("color", "red");
            }
        }).catch(function (error) {
            console.error("OTP Error:", error);
            $msg.text("حدث خطأ في الاتصال بالسيرفر").css("color", "red");
        });
    },

    _onVerifyOtp: function (ev) {
        ev.preventDefault();
        var code = this.$('#otp_code').val();
        var $msg = this.$('#otp_message');

        jsonrpc('/otp/verify', {
            entered_otp: code,
        }).then(function (result) {
            if (result.status === 'success') {
                $msg.text("جاري تسجيل الدخول...").css("color", "green");
                window.location.href = '/my'; // التوجه لصفحة الحساب
            } else {
                $msg.text("الكود غير صحيح").css("color", "red");
            }
        });
    },
});
