# Deploy PlainSight on DigitalOcean

PlainSight needs a machine that can run Ollama, so use a **GPU Droplet** (fast) or a large CPU Droplet (works, but slow).
App Platform and other managed containers have no GPU, so they cannot host the model.

1. Create a GPU Droplet (Ubuntu, "AI/ML ready" image if offered) and add your SSH key. Check the GPU Droplets pricing page for current rates and billing; Droplets bill until you destroy them.
2. Copy the project over: `scp -r plainsight root@<droplet-ip>:/root/`
3. SSH in and run:
   ```bash
   cd /root/plainsight
   APP_PASS='pick-a-password' MODEL=gemma4:e4b bash deploy/setup-droplet.sh
   ```
   Leave `MODEL` off to pick by RAM. On a GPU Droplet, choose by GPU memory instead, and prefer a smaller model for faster demos.
4. Open the HTTPS address it prints (`<ip>.sslip.io`, or set `DOMAIN=yourname.example.com` with a DNS A record). Sign in with user `demo` and your password.
5. Check the header: it shows the model and whether the expected speed is Fast, Medium, or Slow (it reads Ollama to see whether the model is on the GPU).

Logs: `journalctl -u plainsight -f`. Restart: `systemctl restart plainsight`. When the hackathon ends, destroy the Droplet.

Notes
- Keep Ollama on localhost and open only ports 22, 80, 443 (the script does this).
- Documents are processed on your Droplet, not by a third-party AI API, but they now travel over the internet to it. HTTPS and the password protect that; it is still an unaudited prototype, so use synthetic or consented documents in the demo.
- Browser voice input needs HTTPS, which the Caddy setup provides.

## Showing it off at the hackathon

- The setup script sets `DEPLOY_HOST`, so the live site shows a **DigitalOcean** badge in the header and a "Hosted on" panel with the real model, GPU/CPU, speed, and API round trip.
- Pre-pull the models you want to demo (for example `ollama pull gemma3n:e4b`, `gemma4:e4b`, `gemma3:4b`, `gemma2:9b`). In the "Pick your Gemma" section, installed sizes have a green dot and switch the live model with one click; others show the pull command.
- Demo flow: open the HTTPS link on a phone, photograph a sample bill, switch language, ask Pip, then switch from Gemma 2 (text only) to Gemma 3n E4B live.
- Put the Droplet and its sslip.io/domain link, plus a screenshot of the badge, in your submission. Destroy the Droplet when judging ends.
