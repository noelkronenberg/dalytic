# Dalytic

A portable analytics dashboard for the everyday.

## Showcase

https://github.com/user-attachments/assets/bddf04eb-778b-4718-8575-cab005decfe4

## Development

Clone and open the repository locally:

```bash
git clone https://github.com/noelkronenberg/dalytic.git # clone repository
cd dalytic # change directory
```

Run Vercel deployment locally:

```bash
npm i -g vercel # install Vercel CLI
vercel env pull # pull environment variables ('FLASK_SECRET_KEY')
vercel dev # start deployment server
```

Run without Vercel locally:

```bash
export FLASK_SECRET_KEY=$(openssl rand -hex 32) # set secret key
python run.py
```
