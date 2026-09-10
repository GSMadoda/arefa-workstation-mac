/**
 * LEEMA Technology Incubation — application intake backend (Google Apps Script).
 * Our own form processor: no third-party form service.
 *
 * What it does on each submission:
 *   1. Appends the application as a row in your Google Sheet.
 *   2. Emails you a notification (reply goes straight to the applicant).
 *   3. Silently drops obvious bots (honeypot field).
 *   4. Redirects the applicant to the thank-you page.
 *
 * SET UP (5 minutes):
 *   1. Create a Google Sheet (this is where applications are stored).
 *   2. In that Sheet: Extensions → Apps Script. Delete any code, paste this file.
 *   3. Set NOTIFY_EMAIL below to the inbox that should receive applications.
 *   4. Deploy → New deployment → type "Web app".
 *        - Execute as: Me
 *        - Who has access: Anyone
 *      Click Deploy, authorise, and copy the Web app URL (ends in /exec).
 *   5. Paste that URL into the site form's `action` (index.html + docs/index.html),
 *      replacing PASTE_YOUR_APPS_SCRIPT_WEB_APP_URL — or send it to Claude to wire in.
 *
 * To change the notification inbox or thank-you page later, edit the constants
 * below and Deploy → Manage deployments → edit → deploy a new version.
 */

const NOTIFY_EMAIL  = 'you@example.com'; // <-- CHANGE: where applications are emailed
const THANK_YOU_URL = 'https://gsmadoda.github.io/arefa-workstation-mac/thankyou.html';
const SHEET_NAME    = 'Applications';

function doPost(e) {
  try {
    const p = (e && e.parameter) || {};
    // Honeypot: real people never fill the hidden "company" field; bots do.
    if (p.company) return redirect_(THANK_YOU_URL);

    getSheet_().appendRow([
      new Date(), p.name || '', p.email || '', p.phone || '', p.sector || '', p.message || ''
    ]);
    notify_(p);
    return redirect_(THANK_YOU_URL);
  } catch (err) {
    return HtmlService.createHtmlOutput(
      'Sorry — something went wrong submitting your application. Please email us instead. (' + err + ')'
    );
  }
}

function doGet() {
  return HtmlService.createHtmlOutput('LEEMA application intake is running.');
}

function getSheet_() {
  const ss = SpreadsheetApp.getActiveSpreadsheet();
  let s = ss.getSheetByName(SHEET_NAME);
  if (!s) {
    s = ss.insertSheet(SHEET_NAME);
    s.appendRow(['Received', 'Name', 'Email', 'Phone', 'Sector', 'Message']);
    s.getRange('1:1').setFontWeight('bold');
  }
  return s;
}

function notify_(p) {
  if (!NOTIFY_EMAIL || NOTIFY_EMAIL === 'you@example.com') return; // not configured yet
  const body =
    'New application via leema.\n\n' +
    'Name:    ' + (p.name || '') + '\n' +
    'Email:   ' + (p.email || '') + '\n' +
    'Phone:   ' + (p.phone || '') + '\n' +
    'Sector:  ' + (p.sector || '') + '\n\n' +
    'Message:\n' + (p.message || '') + '\n';
  MailApp.sendEmail({
    to: NOTIFY_EMAIL,
    subject: 'New LEEMA application — ' + (p.name || 'applicant'),
    body: body,
    replyTo: p.email || NOTIFY_EMAIL
  });
}

function redirect_(url) {
  const safe = JSON.stringify(url);
  return HtmlService
    .createHtmlOutput(
      '<!doctype html><meta http-equiv="refresh" content="0;url=' + url + '">' +
      '<script>location.replace(' + safe + ')</script>Redirecting…'
    )
    .setXFrameOptionsMode(HtmlService.XFrameOptionsMode.ALLOWALL);
}
