/** @odoo-module **/
import publicWidget from "@web/legacy/js/public/public_widget";
import { jsonrpc } from "@web/core/network/rpc_service";

publicWidget.registry.VlOtpAuth = publicWidget.Widget.extend({
    selector: '#vl_otp_login_section', // تأكد أن هذا الـ ID موجود في ملف templates.xml
    events: {
        'click #btn_send_otp': '_onSendOtp',
        'click #btn_verify_otp': '_onVerifyOtp',
    },

    init: function () {
        this._super.apply(this, arguments);
        console.log("VictoryLink OTP JS Initialized"); // ستظهر في الـ Console إذا اشتغل الملف
    },

    _onSendOtp: function (ev) {
        ev.preventDefault();
        var phone = this.$('#mobile_number').val();
        var $msg = this.$('#otp_message');

        if (!phone) {
            alert("يرجى إدخال رقم الهاتف");
            return;
        }

        $msg.text("جاري إرسال الكود...").css("color", "blue");

        jsonrpc('/otp/send', {
            'phone_number': phone,
        }).then((result) => {
            if (result.status === 'success') {
                this.$('#otp_code_container').show();
                $msg.text("تم الإرسال").css("color", "green");
            } else {
                $msg.text(result.message || "خطأ في الإرسال").css("color", "red");
            }
        });
    },

    _onVerifyOtp: function (ev) {
        ev.preventDefault();
        var code = this.$('#otp_code').val();
        jsonrpc('/otp/verify', {
            'entered_otp': code,
        }).then((result) => {
            if (result.status === 'success') {
                window.location.reload();
            } else {
                alert("الكود غير صحيح");
            }
        });
    },
});
