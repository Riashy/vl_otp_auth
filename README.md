# Victory Link OTP Authentication for Odoo 17/18/19

## What this module does
- Adds OTP login on `/web/login`
- Sends the OTP through the Victory Link REST SMS API
- Works for employees, portal users, or both, depending on settings
- Stores OTP requests in `vl.otp.code`
- Adds cleanup cron for expired/old codes
- Adds Victory Link settings in General Settings

## Required configuration
Go to **Settings -> General Settings -> OTP Authentication** and fill:
- Gateway Username
- Gateway Password
- Sender Name
- Default Country Code (example: `20` for Egypt)
- Enable OTP Login

## User setup
For every user who should use OTP login:
- set a mobile number on the user
- keep **Allow OTP Login** enabled
- mobile number must be unique among active OTP-enabled users

## Routes
- `POST /vl_otp/request` -> send OTP
- `POST /vl_otp/verify` -> verify OTP and finalize session

## Notes
- This implementation adds **passwordless mobile + OTP login**.
- Normal password login remains available.
- If you want to extend the same OTP logic to checkout or signup later, reuse model `vl.otp.code` and service `vl.sms.gateway`.
