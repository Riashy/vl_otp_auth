import logging
from urllib.parse import urlencode

from odoo import _, http
from odoo.addons.auth_signup.controllers.main import AuthSignupHome
from odoo.addons.web.controllers.home import ensure_db
from odoo.addons.website_sale.controllers.main import WebsiteSale
from odoo.http import request

_logger = logging.getLogger(__name__)


class VictoryLinkOtpAuth(AuthSignupHome):
    def _gateway(self):
        return request.env["vl.sms.gateway"].sudo()

    def _otp_login_enabled(self):
        return self._gateway()._get_config()["login_enabled"]

    def _otp_signup_enabled(self):
        return self._gateway()._get_config()["signup_enabled"]

    def _request_tracking_context(self):
        return {
            "vl_otp_ip_address": request.httprequest.remote_addr,
            "vl_otp_user_agent": getattr(request.httprequest.user_agent, "string", "") or "",
        }

    def _login_response_context(self):
        return {
            "otp_login_feature_enabled": self._otp_login_enabled(),
            "otp_message": request.params.get("otp_message"),
            "otp_error": request.params.get("otp_error"),
            "otp_mobile": request.params.get("otp_mobile") or "",
            "otp_redirect": request.params.get("redirect") or "/web",
            "otp_db": request.params.get("db") or request.db,
            "otp_request_token": request.params.get("otp_request_token") or "",
        }

    def _signup_response_context(self):
        return {
            "otp_signup_feature_enabled": self._otp_signup_enabled(),
            "otp_signup_message": request.params.get("otp_signup_message"),
            "otp_signup_error": request.params.get("otp_signup_error"),
            "otp_signup_name": request.params.get("otp_signup_name") or "",
            "otp_signup_login": request.params.get("otp_signup_login") or "",
            "otp_signup_mobile": request.params.get("otp_signup_mobile") or "",
            "otp_signup_redirect": request.params.get("redirect") or "",
            "otp_signup_request_token": request.params.get("otp_signup_request_token") or "",
        }

    def _redirect_to_login(self, mobile=None, redirect=None, message=None, error=None, db=None, request_token=None):
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
        if request_token:
            params["otp_request_token"] = request_token
        query = urlencode(params)
        return request.redirect("/web/login%s" % (("?%s" % query) if query else ""))

    def _redirect_to_signup(
        self,
        name=None,
        login=None,
        mobile=None,
        redirect=None,
        message=None,
        error=None,
        request_token=None,
    ):
        params = {}
        if name:
            params["otp_signup_name"] = name
        if login:
            params["otp_signup_login"] = login
        if mobile:
            params["otp_signup_mobile"] = mobile
        if redirect:
            params["redirect"] = redirect
        if message:
            params["otp_signup_message"] = message
        if error:
            params["otp_signup_error"] = error
        if request_token:
            params["otp_signup_request_token"] = request_token
        query = urlencode(params)
        return request.redirect("/web/signup%s" % (("?%s" % query) if query else ""))

    def _finalize_session(self, user):
        request.session["pre_login"] = user.login
        request.session["pre_uid"] = user.id
        request.session.finalize(request.env)

    def _session_authenticate(self, login, password):
        credential = {"login": login, "password": password, "type": "password"}
        try:
            return request.session.authenticate(request.env, credential)
        except TypeError:
            try:
                return request.session.authenticate(request.db, credential)
            except TypeError:
                return request.session.authenticate(request.db, login, password)

    def _signup_payload_from_request(self, post):
        return {
            "name": (post.get("name") or "").strip(),
            "login": (post.get("login") or "").strip(),
            "mobile": (post.get("mobile") or "").strip(),
            "password": post.get("password") or "",
            "confirm_password": post.get("confirm_password") or "",
            "redirect": post.get("redirect") or "",
        }

    def _signup_session_key(self):
        return "vl_otp_signup_payload"

    def _signup_password_session_key(self):
        return "vl_otp_signup_password"

    def _save_signup_payload(self, payload):
        session_payload = dict(payload)
        password = session_payload.pop("password", "")
        session_payload.pop("confirm_password", None)
        request.session[self._signup_session_key()] = session_payload
        request.session[self._signup_password_session_key()] = password

    def _get_signup_payload(self):
        payload = dict(request.session.get(self._signup_session_key()) or {})
        if payload:
            payload["password"] = request.session.get(self._signup_password_session_key()) or ""
        return payload

    def _clear_signup_payload(self):
        request.session.pop(self._signup_session_key(), None)
        request.session.pop(self._signup_password_session_key(), None)

    def _validate_signup_payload(self, payload):
        if not payload["name"]:
            raise ValueError(_("Name is required."))
        if not payload["login"]:
            raise ValueError(_("Email / Login is required."))
        if not payload["mobile"]:
            raise ValueError(_("Mobile number is required."))
        if not payload["password"]:
            raise ValueError(_("Password is required."))
        if payload["password"] != payload.get("confirm_password"):
            raise ValueError(_("Password confirmation does not match."))

        users = request.env["res.users"].sudo()
        if users.search_count([("login", "=", payload["login"])]) > 0:
            raise ValueError(_("Another user already exists with the same login."))

        mobile_digits = self._gateway()._only_digits(payload["mobile"])
        if users.search_count([("active", "=", True), ("otp_mobile_digits", "=", mobile_digits)]) > 0:
            raise ValueError(_("Another user already exists with the same mobile number."))

    def _find_login_user(self, raw_mobile):
        return request.env["res.users"].sudo().find_user_for_otp(raw_mobile)[:1]

    def _find_login_user_from_request_token(self, request_token):
        if not request_token:
            return request.env["res.users"]
        otp = request.env["vl.otp.code"].sudo().search([
            ("request_token", "=", request_token),
            ("purpose", "=", "login"),
        ], order="id desc", limit=1)
        return otp.user_id[:1]

    @http.route()
    def web_login(self, *args, **kw):
        response = super().web_login(*args, **kw)
        if hasattr(response, "qcontext"):
            response.qcontext.update(self._login_response_context())
        return response

    @http.route()
    def web_auth_signup(self, *args, **kw):
        if self._otp_signup_enabled() and request.httprequest.method == "POST":
            return self._redirect_to_signup(
                name=(kw.get("name") or "").strip(),
                login=(kw.get("login") or "").strip(),
                redirect=(kw.get("redirect") or "").strip(),
                error=_("Standard signup is disabled while OTP signup is enabled. Please use the OTP signup form below."),
            )
        response = super().web_auth_signup(*args, **kw)
        if hasattr(response, "qcontext"):
            response.qcontext.update(self._signup_response_context())
        return response

    @http.route("/vl_otp/request", type="http", auth="public", methods=["POST"], website=True, sitemap=False)
    def request_login_otp(self, **post):
        ensure_db()
        redirect = post.get("redirect") or "/web"
        db = post.get("db") or request.db
        mobile = (post.get("otp_mobile") or "").strip()
        generic_message = _("If the mobile matches an active user, an OTP has been sent.")

        if not self._otp_login_enabled():
            return self._redirect_to_login(mobile=mobile, redirect=redirect, error=_("OTP login is disabled."), db=db)

        try:
            user = self._find_login_user(mobile)
            request_token = None
            if user:
                otp = request.env["vl.otp.code"].with_context(**self._request_tracking_context()).sudo().issue_code(
                    user=user, mobile=user.mobile or mobile, purpose="login"
                )
                request_token = otp.request_token
            return self._redirect_to_login(
                mobile=mobile,
                redirect=redirect,
                message=generic_message,
                db=db,
                request_token=request_token,
            )
        except Exception as exc:
            _logger.exception("OTP login request failed")
            return self._redirect_to_login(mobile=mobile, redirect=redirect, error=str(exc), db=db)

    @http.route("/vl_otp/verify", type="http", auth="public", methods=["POST"], website=True, sitemap=False)
    def verify_login_otp(self, **post):
        ensure_db()
        redirect = post.get("redirect") or "/web"
        db = post.get("db") or request.db
        mobile = (post.get("otp_mobile") or "").strip()
        code = (post.get("otp_code") or "").strip()
        request_token = (post.get("otp_request_token") or "").strip()

        if not self._otp_login_enabled():
            return self._redirect_to_login(mobile=mobile, redirect=redirect, error=_("OTP login is disabled."), db=db)

        try:
            user = self._find_login_user_from_request_token(request_token) or self._find_login_user(mobile)
            if not user:
                raise ValueError(_("Invalid or expired verification code."))
            request.env["vl.otp.code"].sudo().verify_code(
                code,
                purpose="login",
                user=user,
                raw_mobile=mobile,
                request_token=request_token or None,
            )
            self._finalize_session(user)
            return request.redirect(redirect)
        except Exception as exc:
            _logger.exception("OTP login verification failed")
            return self._redirect_to_login(
                mobile=mobile,
                redirect=redirect,
                error=str(exc),
                db=db,
                request_token=request_token,
            )

    @http.route("/vl_otp/signup/request", type="http", auth="public", methods=["POST"], website=True, sitemap=False)
    def request_signup_otp(self, **post):
        ensure_db()
        payload = self._signup_payload_from_request(post)

        if not self._otp_signup_enabled():
            return self._redirect_to_signup(
                name=payload["name"],
                login=payload["login"],
                mobile=payload["mobile"],
                redirect=payload["redirect"],
                error=_("OTP signup is disabled."),
            )

        try:
            self._validate_signup_payload(payload)
            self._save_signup_payload(payload)
            otp = request.env["vl.otp.code"].with_context(**self._request_tracking_context()).sudo().issue_code(
                mobile=payload["mobile"],
                purpose="signup",
            )
            return self._redirect_to_signup(
                name=payload["name"],
                login=payload["login"],
                mobile=payload["mobile"],
                redirect=payload["redirect"],
                message=_("OTP has been sent to your mobile number."),
                request_token=otp.request_token,
            )
        except Exception as exc:
            _logger.exception("OTP signup request failed")
            return self._redirect_to_signup(
                name=payload["name"],
                login=payload["login"],
                mobile=payload["mobile"],
                redirect=payload["redirect"],
                error=str(exc),
            )

    @http.route("/vl_otp/signup/verify", type="http", auth="public", methods=["POST"], website=True, sitemap=False)
    def verify_signup_otp(self, **post):
        ensure_db()
        request_token = (post.get("otp_signup_request_token") or "").strip()
        code = (post.get("otp_code") or "").strip()
        payload = self._get_signup_payload()
        redirect_target = (post.get("redirect") or payload.get("redirect") or "").strip()

        if not self._otp_signup_enabled():
            return self._redirect_to_signup(error=_("OTP signup is disabled."), redirect=redirect_target)

        if not payload:
            return self._redirect_to_signup(error=_("Your signup session expired. Please request a new OTP."), redirect=redirect_target)

        try:
            request.env["vl.otp.code"].sudo().verify_code(
                code,
                purpose="signup",
                raw_mobile=payload.get("mobile"),
                request_token=request_token or None,
            )
            values = {
                "name": payload["name"],
                "login": payload["login"],
                "password": payload["password"],
                "mobile": payload["mobile"],
            }
            request.env["res.users"].sudo().signup(values, token=None)
            user = request.env["res.users"].sudo().search([("login", "=", payload["login"])], limit=1)
            if not user:
                raise ValueError(_("User could not be created after OTP verification."))
            user.write({"otp_mobile_verified": True})
            if user.partner_id:
                user.partner_id.write({
                    "mobile": payload["mobile"],
                    "otp_mobile_verified": True,
                })
            self._session_authenticate(payload["login"], payload["password"])
            self._clear_signup_payload()
            return request.redirect(redirect_target or "/web")
        except Exception as exc:
            _logger.exception("OTP signup verification failed")
            return self._redirect_to_signup(
                name=payload.get("name"),
                login=payload.get("login"),
                mobile=payload.get("mobile"),
                redirect=redirect_target,
                error=str(exc),
                request_token=request_token,
            )


class VictoryLinkOtpWebsiteSale(WebsiteSale):
    def _checkout_gateway_config(self):
        return request.env["vl.sms.gateway"].sudo()._get_config()

    def _otp_checkout_enabled(self):
        return self._checkout_gateway_config()["checkout_enabled"]

    def _current_order(self):
        order = getattr(request, "cart", False)
        if order:
            return order
        return request.website.sale_get_order()

    def _payment_redirect(self, message=None, error=None, request_token=None, mobile=None):
        params = {}
        if message:
            params["otp_checkout_message"] = message
        if error:
            params["otp_checkout_error"] = error
        if request_token:
            params["otp_checkout_request_token"] = request_token
        if mobile:
            params["otp_checkout_mobile"] = mobile
        query = urlencode(params)
        return request.redirect("/shop/payment%s" % (("?%s" % query) if query else ""))

    def _order_mobile(self, order, explicit_mobile=None):
        return (
            (explicit_mobile or "").strip()
            or (order.partner_id.mobile or "").strip()
            or (order.partner_id.phone or "").strip()
        )

    def _checkout_otp_required(self, order):
        return bool(self._otp_checkout_enabled() and order and order.exists() and not order.otp_checkout_verified)

    def _checkout_context(self, order):
        render_values = {
            "website_sale_order": order,
            "order": order,
            "redirect": "/shop/payment",
            "otp_checkout_enabled": self._otp_checkout_enabled(),
            "otp_checkout_message": request.params.get("otp_checkout_message"),
            "otp_checkout_error": request.params.get("otp_checkout_error"),
            "otp_checkout_request_token": request.params.get("otp_checkout_request_token") or "",
            "otp_checkout_mobile": request.params.get("otp_checkout_mobile") or self._order_mobile(order),
            "show_navigation_button": False,
        }
        if hasattr(request.website, "_get_checkout_step_values"):
            render_values.update(request.website._get_checkout_step_values())
        return render_values

    @http.route()
    def shop_payment(self, **post):
        order = self._current_order()
        if self._checkout_otp_required(order):
            cfg = self._checkout_gateway_config()
            if not cfg["gateway_username"] or not cfg["gateway_password"] or not cfg["gateway_sender"]:
                values = self._checkout_context(order)
                values["otp_checkout_error"] = _("OTP checkout is enabled but the SMS gateway is not fully configured.")
                return request.render("vl_otp_auth.checkout_payment_otp", values)
            return request.render("vl_otp_auth.checkout_payment_otp", self._checkout_context(order))
        return super().shop_payment(**post)

    @http.route("/vl_otp/checkout/request", type="http", auth="public", methods=["POST"], website=True, sitemap=False)
    def request_checkout_otp(self, **post):
        order = self._current_order()
        if not order:
            return request.redirect("/shop/checkout")
        if not self._otp_checkout_enabled():
            return self._payment_redirect(error=_("Checkout OTP is disabled."))

        mobile = self._order_mobile(order, explicit_mobile=post.get("otp_mobile"))
        try:
            if order.partner_id and mobile and order.partner_id.mobile != mobile:
                order.partner_id.sudo().write({"mobile": mobile})
            otp = request.env["vl.otp.code"].with_context(
                vl_otp_ip_address=request.httprequest.remote_addr,
                vl_otp_user_agent=getattr(request.httprequest.user_agent, "string", "") or "",
            ).sudo().issue_code(
                partner=order.partner_id,
                mobile=mobile,
                purpose="checkout",
            )
            return self._payment_redirect(
                message=_("OTP has been sent to the checkout mobile number."),
                request_token=otp.request_token,
                mobile=mobile,
            )
        except Exception as exc:
            _logger.exception("Checkout OTP request failed")
            return self._payment_redirect(error=str(exc), mobile=mobile)

    @http.route("/vl_otp/checkout/verify", type="http", auth="public", methods=["POST"], website=True, sitemap=False)
    def verify_checkout_otp(self, **post):
        order = self._current_order()
        if not order:
            return request.redirect("/shop/checkout")
        if not self._otp_checkout_enabled():
            return self._payment_redirect(error=_("Checkout OTP is disabled."))

        mobile = self._order_mobile(order, explicit_mobile=post.get("otp_mobile"))
        code = (post.get("otp_code") or "").strip()
        request_token = (post.get("otp_checkout_request_token") or "").strip()
        try:
            request.env["vl.otp.code"].sudo().verify_code(
                code,
                purpose="checkout",
                partner=order.partner_id,
                raw_mobile=mobile,
                request_token=request_token or None,
            )
            order.sudo().write({
                "otp_checkout_verified": True,
                "otp_checkout_mobile": mobile,
                "otp_checkout_verified_at": request.env["vl.otp.code"]._now(),
            })
            return request.redirect("/shop/payment")
        except Exception as exc:
            _logger.exception("Checkout OTP verification failed")
            return self._payment_redirect(error=str(exc), request_token=request_token, mobile=mobile)

    @http.route()
    def shop_payment_validate(self, sale_order_id=None, **post):
        order = None
        if sale_order_id is None:
            order = self._current_order()
            if not order and request.session.get("sale_last_order_id"):
                order = request.env["sale.order"].sudo().browse(request.session["sale_last_order_id"]).exists()
        else:
            order = request.env["sale.order"].sudo().browse(sale_order_id).exists()

        if self._checkout_otp_required(order):
            return self._payment_redirect(error=_("Please verify the checkout OTP before continuing to payment."))
        return super().shop_payment_validate(sale_order_id=sale_order_id, **post)
