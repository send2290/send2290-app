# Google reCAPTCHA Setup Guide

This guide will help you set up Google reCAPTCHA for your Form 2290 application to prevent spam and bot submissions.

## Step 1: Create a Google reCAPTCHA Account

1. Go to [Google reCAPTCHA Admin Console](https://www.google.com/recaptcha/admin/create)
2. Sign in with your Google account
3. Click "Create" to add a new site

## Step 2: Configure Your reCAPTCHA Site

Fill out the form with the following information:

- **Label**: Give your site a name (e.g., "Form 2290 Website")
- **reCAPTCHA type**: Select "reCAPTCHA v2" → "I'm not a robot" Checkbox
- **Domains**: Add your domains:
  - For development: `localhost`
  - For production: `your-domain.com` (replace with your actual domain)
  
- **Owners**: Add additional Google accounts that should have access (optional)
- **Accept the Terms of Service**

## Step 3: Get Your Keys

After creating the site, you'll receive two keys:

1. **Site key** (public key) - This goes in your frontend
2. **Secret key** (private key) - This goes in your backend

## Step 4: Configure Your Application

### Frontend Configuration

1. Open `frontend/.env.local`
2. Replace `your_recaptcha_site_key_here` with your actual site key:
   ```
   NEXT_PUBLIC_RECAPTCHA_SITE_KEY=6LcXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXX
   ```

### Backend Configuration

1. Open `backend/.env`
2. Replace `your_recaptcha_secret_key_here` with your actual secret key:
   ```
   RECAPTCHA_SECRET_KEY=6LcXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXX
   ```

## Step 5: Test Your Setup

1. Start your development servers:
   ```bash
   # Frontend
   cd frontend
   npm run dev
   
   # Backend
   cd backend
   python app.py
   ```

2. Visit your application
3. Try to submit the form - you should see the reCAPTCHA checkbox
4. Complete the CAPTCHA and submit the form
5. Check the browser console and backend logs for any errors

## Security Notes

- **Never expose your secret key** - it should only be used on the server
- The site key is public and can be seen in your frontend code
- reCAPTCHA v2 provides good protection against bots while being user-friendly
- The CAPTCHA will automatically reset after each submission

## Troubleshooting

### CAPTCHA Not Showing
- Check that `NEXT_PUBLIC_RECAPTCHA_SITE_KEY` is set correctly
- Ensure your domain is added to the reCAPTCHA configuration
- Check browser console for errors

### CAPTCHA Verification Failing
- Verify `RECAPTCHA_SECRET_KEY` is set correctly in backend
- Check backend logs for detailed error messages
- Ensure the secret key corresponds to the same site as the site key

### Development vs Production
- For localhost development, add `localhost` to your reCAPTCHA domains
- For production, add your actual domain (e.g., `yoursite.com`)
- You can use the same reCAPTCHA site for both by adding both domains

## Additional Security Features

The implementation includes:

- ✅ CAPTCHA verification before form submission
- ✅ Automatic CAPTCHA reset after successful submission
- ✅ Visual feedback for users (disabled submit button until CAPTCHA complete)
- ✅ Server-side verification to prevent bypass attempts
- ✅ Graceful fallback if CAPTCHA is not configured (development mode)
- ✅ Clear error messages for users
