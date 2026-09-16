# HireWise — Frontend

Static single-page app (HTML + CSS + JS, no build step).

## Running locally

Open `index.html` directly in a browser **or** serve it with any static file server:

```bash
npx serve .
# or
python -m http.server 8080
```

By default `script.js` points at the deployed Render backend. To use a local backend instead, change `API_BASE` at the top of `script.js`:

```js
const API_BASE = "http://localhost:5000";
```
