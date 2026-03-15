/** @odoo-module **/
import publicWidget from "@web/legacy/js/public/public_widget";
import { jsonrpc } from "@web/core/network/rpc_service";

publicWidget.registry.VlOtpAuth = publicWidget.Widget.extend({
    selector: '#vl_otp_login_section',
    events: {
        'click #btn_send_otp': '_onSendOtp',
        'click #btn_verify_otp': '_onVerifyOtp',
    },

    init: function () {
        this._super.apply(this, arguments);
        console.log("VictoryLink OTP JS: Initialized and Ready");
    },

    _onSendOtp: function (ev) {
        ev.preventDefault();
        var self = this;
        var phone = this.$('#mobile_number').val();
        
        if (!phone) {
            alert("يرجى إدخال رقم الهاتف أولاً");
            return;
        }

        this.$('#otp_message').text("جاري الإرسال...").css("color", "blue");

        jsonrpc('/otp/send', {
            'phone_number': phone,
        }).then(function (result) {
            if (result.status === 'success') {
                self.$('#otp_code_container').fadeIn();
                self.$('#otp_message').text("تم إرسال الكود بنجاح").css("color", "green");
            } else {
                self.$('#otp_message').text(result.message || "فشل الإرسال").css("color", "red");
            }
        });
    },

    _onVerifyOtp: function (ev) {
        ev.preventDefault();
        var code = this.$('#otp_code').val();
        
        jsonrpc('/otp/verify', {
            'entered_otp': code,
        }).then(function (result) {
            if (result.status === 'success') {
                window.location.href = '/my'; 
            } else {
                alert("كود التحقق غير صحيح");
            }
        });
    },
});
