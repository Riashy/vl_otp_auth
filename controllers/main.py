import logging
from urllib.parse import urlencode

from odoo import _, http
from odoo.addons.auth_signup.controllers.main import AuthSignupHome
from odoo.addons.web.controllers.home import ensure_db
from odoo.http import request

_logger = logging.getLogger(__name__)


class VictoryLinkOtpLogin(AuthSignupHome):
    def _otp_login_enabled(self):
        return request.env["vl.sms.gateway"].sudo()._get_config()["login_enabled"]

    def _login_response_context(self):
        return {
            "otp_login_feature_enabled": self._otp_login_enabled(),
            "otp_message": request.params.get("otp_message"),
            "otp_error": request.params.get("otp_error"),
            "otp_mobile": request.params.get("otp_mobile") or "",
            "otp_redirect": request.params.get("redirect") or "/web",
            "otp_db": request.params.get("db") or request.db,
        }

    def _redirect_to_login(self, mobile=None, redirect=None, message=None, error=None, db=None):
        params = {}
        if mobile:
            params["otp_mobile"] = mobile
        if redirect:
            params["redirect"] = redirect
        if db:
            params["db"] = db
        if message:
            params["otp_message"] = message
        if error:
            params["otp_error"] = error
        query = urlencode(params)
        return request.redirect("/web/login%s" % (("?%s" % query) if query else ""))

    def _finalize_session(self, user):
        request.session["pre_login"] = user.login
        request.session["pre_uid"] = user.id
        request.session.finalize(request.env)

    @http.route()
    def web_login(self, *args, **kw):
        response = super().web_login(*args, **kw)
        if hasattr(response, "qcontext"):
            response.qcontext.update(self._login_response_context())
        return response

    @http.route("/vl_otp/request", type="http", auth="public", methods=["POST"], sitemap=False)
    def request_login_otp(self, **post):
        ensure_db()
        redirect = post.get("redirect") or "/web"
        db = post.get("db") or request.db
        mobile = (post.get("otp_mobile") or "").strip()
        generic_message = _("If the mobile matches an active user, an OTP has been sent.")

        if not self._otp_login_enabled():
            return self._redirect_to_login(mobile=mobile, redirect=redirect, error=_("OTP login is disabled."), db=db)

        try:
            users = request.env["res.users"].sudo().find_user_for_otp(mobile)
            if users:
                request.env["vl.otp.code"].with_context(
                    vl_otp_ip_address=request.httprequest.remote_addr,
                    vl_otp_user_agent=request.httprequest.user_agent.string,
                ).sudo().issue_code(users[0], mobile=users[0].mobile or mobile, purpose="login")
        except Exception as exc:
            _logger.exception("OTP request failed")
            return self._redirect_to_login(mobile=mobile, redirect=redirect, error=str(exc), db=db)

        return self._redirect_to_login(mobile=mobile, redirect=redirect, message=generic_message, db=db)

    @http.route("/vl_otp/verify", type="http", auth="public", methods=["POST"], sitemap=False)
    def verify_login_otp(self, **post):
        ensure_db()
        redirect = post.get("redirect") or "/web"
        db = post.get("db") or request.db
        mobile = (post.get("otp_mobile") or "").strip()
        code = (post.get("otp_code") or "").strip()

        if not self._otp_login_enabled():
            return self._redirect_to_login(mobile=mobile, redirect=redirect, error=_("OTP login is disabled."), db=db)

        try:
            users = request.env["res.users"].sudo().find_user_for_otp(mobile)
            if not users:
                raise ValueError(_("Invalid or expired verification code."))
            user = users[0]
            request.env["vl.otp.code"].sudo().verify_code(user, mobile, code, purpose="login")
            self._finalize_session(user)
            return request.redirect(redirect)
        except Exception as exc:
            _logger.exception("OTP verification failed")
            return self._redirect_to_login(mobile=mobile, redirect=redirect, error=str(exc), db=db)
