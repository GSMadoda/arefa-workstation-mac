# Application intake — our own backend (no Formspree)

The site is static (GitHub Pages), so form submissions are handled by a small
backend **you own and control**: a Google Apps Script bound to a Google Sheet.
No third-party form service.

**Flow:** the site form POSTs to your Apps Script Web App → the script saves the
application to your Sheet, emails you, and redirects the applicant to
`thankyou.html`.

## Set up (about 5 minutes)

1. Create a **Google Sheet** (Applications will be stored here). Any Google
   account you own works.
2. In that Sheet: **Extensions → Apps Script**. Delete the placeholder code and
   paste the contents of [`Code.gs`](./Code.gs).
3. Change `NOTIFY_EMAIL` at the top of the script to the inbox that should
   receive applications. (Leave `THANK_YOU_URL` as-is.)
4. **Deploy → New deployment → Web app**:
   - *Execute as:* **Me**
   - *Who has access:* **Anyone**
   - Click **Deploy**, approve the permissions prompt, and **copy the Web app
     URL** (it ends in `/exec`).
5. Put that URL into the site form's `action`:
   - In `index.html` **and** `docs/index.html`, replace
     `PASTE_YOUR_APPS_SCRIPT_WEB_APP_URL` with your `/exec` URL, then commit.
   - Or just send the URL to Claude and it will wire it in.

That's it. Every submission then lands as a row in your Sheet **and** in your
inbox. To change the inbox or thank-you page later, edit the constants and
**Deploy → Manage deployments → Edit → New version**.

## Notes

- **Spam:** the form includes a hidden honeypot field (`company`); bots that
  fill it are dropped silently.
- **Cost:** free, within normal Google quotas (hundreds of emails/day).
- **Prefer not to use Google?** The same frontend works with a Cloudflare
  Worker or any endpoint that accepts a `POST` of
  `name, email, phone, sector, message` — swap the form `action` for that URL.
  Ask Claude for the Worker version if you'd rather host it there.
