# Dalytic

A portable analytics dashboard for the everyday.

## Showcase

> The app is live and hosted on Vercel: [dalytic.vercel.app](https://dalytic.vercel.app/)

https://github.com/user-attachments/assets/bddf04eb-778b-4718-8575-cab005decfe4

## Set-up

Clone and open the repository:

```bash
git clone https://github.com/noelkronenberg/dalytic.git # clone repository
cd dalytic # change directory
```

Run the app locally:

```bash
pip install -r requirements.txt # install dependencies
export FLASK_SECRET_KEY=$(openssl rand -hex 32) # set secret key
python run.py # start deployment server
```

Alternatively, run a Vercel deployment locally (Vercel account and project needed):

```bash
npm i -g vercel # install Vercel CLI
vercel link # link to Vercel project
vercel env pull # pull environment variables ('FLASK_SECRET_KEY')
vercel dev # start deployment server
```
