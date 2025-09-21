# 🚀 Deploying Career Advisor App to Render

This guide will walk you through deploying your Flask Career Advisor application to Render.

## 📋 Prerequisites

1. **GitHub Account**: Your code should be in a GitHub repository
2. **Render Account**: Sign up at [render.com](https://render.com)
3. **Google Gemini API Key**: Get from [Google AI Studio](https://makersuite.google.com/app/apikey)

## 🔧 Pre-deployment Setup

### 1. Update Your Config for Production

The `config.py` file is already configured to use environment variables for production. No changes needed.

### 2. Database Configuration

The app uses SQLite by default, which is perfect for small to medium applications. The database file will be stored in the `instance/` directory and persists across deployments on Render.

## 🌐 Deploy to Render

### Step 1: Create a New Web Service

1. Go to [Render Dashboard](https://dashboard.render.com)
2. Click **"New +"** → **"Web Service"**
3. Connect your GitHub repository containing this project
4. Select the repository and branch (usually `main`)

### Step 2: Configure the Service

Fill in the following settings:

**Basic Settings:**
- **Name**: `career-advisor-app` (or your preferred name)
- **Runtime**: `Python 3`
- **Build Command**: `./build.sh`
- **Start Command**: `gunicorn main:app`
- **Instance Type**: `Free` (for testing) or `Starter` (for production)

**Advanced Settings:**
- **Root Directory**: `career_advisor_app` (if your app is in a subdirectory)
- **Auto-Deploy**: `Yes` (recommended)

### Step 3: Set Environment Variables

In the **Environment Variables** section, add the following:

#### Required Variables:
```bash
SECRET_KEY=your-super-secure-secret-key-here-generate-a-random-one
GEMINI_API_KEY=your-google-gemini-api-key-here
FLASK_ENV=production
```

#### Optional Variables:
```bash
GEMINI_MODEL=gemini-1.5-flash
PORT=10000
# DATABASE_URL=custom-database-url (optional - uses SQLite by default)
```

**🔐 Important**: 
- Generate a secure `SECRET_KEY` using: `python -c "import secrets; print(secrets.token_hex(32))"`
- Get your `GEMINI_API_KEY` from [Google AI Studio](https://makersuite.google.com/app/apikey)

### Step 4: Deploy

1. Click **"Create Web Service"**
2. Render will automatically:
   - Clone your repository
   - Run the build script (`build.sh`)
   - Install dependencies
   - Create database tables
   - Start your application

## 🔍 Monitoring Your Deployment

### Check Deployment Status
- Monitor the **Logs** tab during deployment
- Look for any error messages in the build or runtime logs

### Access Your App
- Once deployed, you'll get a URL like: `https://your-app-name.onrender.com`
- Test all features to ensure everything works

## 🛠️ Troubleshooting

### Common Issues:

1. **Build Fails**:
   - Check that `build.sh` has execute permissions
   - Verify all dependencies in `requirements.txt`

2. **Database Errors**:
   - SQLite database will be created automatically
   - Check that `instance/` directory has write permissions

3. **API Errors**:
   - Verify `GEMINI_API_KEY` is valid
   - Check Google AI Studio quotas

4. **Static Files Not Loading**:
   - Ensure static files are in the correct directory
   - Check Flask static file configuration

### View Logs:
```bash
# In Render Dashboard → Your Service → Logs
# Or use Render CLI
render logs -s your-service-name
```

## 🔄 Updating Your App

With auto-deploy enabled:
1. Push changes to your GitHub repository
2. Render automatically rebuilds and deploys
3. Monitor the deployment in the Render dashboard

## 💡 Production Tips

1. **Environment Variables**: Never commit sensitive data to Git
2. **Database Persistence**: SQLite data persists in Render's disk storage
3. **Database Backups**: Consider periodic downloads of the SQLite file for backups
4. **Monitoring**: Enable Render's monitoring features
5. **Custom Domain**: Add your own domain in Service Settings
6. **SSL**: Render provides free SSL certificates

## 📱 Test Your Deployment

After deployment, test these features:
- [ ] User registration/login
- [ ] Profile creation
- [ ] AI chat functionality
- [ ] Resume upload and analysis
- [ ] Career tracker
- [ ] All static assets load correctly

## 🆘 Need Help?

- **Render Docs**: [render.com/docs](https://render.com/docs)
- **Flask Deployment**: [flask.palletsprojects.com/en/2.3.x/deploying/](https://flask.palletsprojects.com/en/2.3.x/deploying/)
- **Google Gemini API**: [ai.google.dev](https://ai.google.dev)

---

🎉 **Congratulations!** Your Career Advisor App should now be live on Render!