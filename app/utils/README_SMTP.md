# Resend SMTP Integration

This document provides information about the Resend SMTP integration for sending grant match emails.

## Overview

The application now supports sending emails via Resend's SMTP service, which is useful for testing email functionality before completing domain verification in Resend.

## Important Note About Domain Verification and Test Recipients

Even when using SMTP, Resend has two important restrictions for testing:

1. The domain in your "From" email address must be verified.
2. When using their test domain (`onboarding@resend.dev`), you can only send emails to your own verified email address.

To work around these restrictions for testing purposes:

1. The SMTP implementation automatically uses Resend's test domain (`onboarding@resend.dev`) as the sender address.
2. All test emails are sent to `charlie@quixilabs.com` regardless of the intended recipient.
3. The original intended recipient is noted in the email subject line.

For example, if your `RESEND_FROM_EMAIL` is set to `"Grant Watchers <grants@yourdomain.com>"` and you're trying to send to `user@example.com`, the actual email will:
- Be sent from `"Grant Watchers <onboarding@resend.dev>"`
- Be delivered to `charlie@quixilabs.com`
- Have the subject line appended with `(Original recipient: user@example.com)`

## Configuration

To use the Resend SMTP functionality, you need to set the following environment variables:

```
RESEND_API_KEY=your_resend_api_key
RESEND_FROM_EMAIL=your_from_email@yourdomain.com  # The name part will be preserved
```

## Testing SMTP Email Functionality

You can test the SMTP email functionality using the provided test script:

```bash
# Run the test script with a test email address
python -m app.utils.test_resend_smtp intended-recipient@example.com
```

Remember that regardless of the intended recipient, all test emails will be sent to `charlie@quixilabs.com`.

## API Endpoints

The application provides two endpoints for sending grant match emails:

1. **Regular API Endpoint** - Uses Resend's API (requires domain verification):
   ```
   POST /api/v1/organizations/send-grant-match-email/{organization_id}
   ```

2. **SMTP API Endpoint** - Uses Resend's SMTP service with test domain:
   ```
   POST /api/v1/organizations/send-grant-match-email-smtp/{organization_id}
   ```

Both endpoints accept the following query parameter:
- `min_score` (float, default: 0.5): Minimum match score to include (0.0 to 1.0)

## SMTP vs API

### SMTP Advantages
- Works without domain verification (using Resend's test domain)
- Useful for testing and development
- Simpler to set up initially

### API Advantages
- Better delivery tracking
- More features (analytics, webhooks, etc.)
- Recommended for production use
- Can use your own verified domain
- Can send to any recipient (not just your own email)

## Resend SMTP Details

- SMTP Host: `smtp.resend.com`
- SMTP Port: `465` (SMTPS - implicit SSL/TLS)
- SMTP Username: `resend`
- SMTP Password: Your Resend API key
- From Address: Uses `onboarding@resend.dev` (Resend's test domain)
- To Address: During testing, all emails go to `charlie@quixilabs.com`

## Moving to Production

When you're ready to move to production:

1. Verify your domain in Resend (https://resend.com/domains)
2. Update the code to use your verified domain in the From address
3. Remove the recipient override to allow sending to any email address
4. Switch to using the API endpoint for better tracking and features

## Troubleshooting

If you encounter issues with SMTP email sending:

1. Verify your Resend API key is correct
2. Check the application logs for detailed error messages
3. Remember that during testing, all emails are sent to `charlie@quixilabs.com`
4. Make sure you're not modifying the From address to use a non-verified domain

For more information, see the [Resend SMTP documentation](https://resend.com/docs/send-with-smtp). 