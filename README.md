# Victory Link OTP Authentication for Odoo 17 / 18 / 19

## Features
- OTP login on `/web/login`
- OTP website signup on `/web/signup`
- OTP verification before website payment on `/shop/payment`
- Victory Link REST API integration for `SendSMS`
- Credit check button using `CheckCredit`
- OTP log model `vl.otp.code`
- Cleanup cron for expired and old codes

## Supported business flows
1. **Backend / Portal Login**
   - User enters mobile number
   - System sends OTP through Victory Link
   - User verifies OTP and is logged in

2. **Website Signup**
   - Visitor fills name, email, password, and mobile
   - System sends OTP to the mobile
   - Account is created only after successful OTP verification

3. **Website Checkout / Payment**
   - Customer reaches `/shop/payment`
   - If checkout OTP is enabled, payment methods are hidden until OTP is verified
   - After successful verification, the normal payment page becomes available

## Required configuration
Go to **Settings -> General Settings -> OTP Authentication** and fill:
- Gateway Username
- Gateway Password
- Sender Name
- Default Country Code (example: `20` for Egypt)
- Enable the features you need: Login / Signup / Checkout

## User setup for OTP login
For every user who should use OTP login:
- set a mobile number on the user
- keep **Allow OTP Login** enabled
- mobile number must be unique among active users

## Main routes
- `POST /vl_otp/request`
- `POST /vl_otp/verify`
- `POST /vl_otp/signup/request`
- `POST /vl_otp/signup/verify`
- `POST /vl_otp/checkout/request`
- `POST /vl_otp/checkout/verify`

## Notes
- Normal password login remains available.
- Signup OTP stores temporary signup data in the session until verification succeeds.
- Checkout OTP marks the sale order as verified before allowing the payment step.
- If your login or website templates are heavily customized, you may need minor XPath adjustments in the XML views.
