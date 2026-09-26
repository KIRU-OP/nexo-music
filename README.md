<p align="center">
  <img src="https://user-images.githubusercontent.com/73097560/115834477-dbab4500-a447-11eb-908a-139a6edaec5c.gif" width="100%" />
</p>

<h1 align="center">
  <img src="https://readme-typing-svg.herokuapp.com?font=Fira+Code&size=32&pause=1000&color=3DDC97&center=true&vCenter=true&width=600&lines=Welcome+to+Nexo+Music+%F0%9F%8E%B6;Your+Ultimate+Telegram+Music+Bot;Play.+Vibe.+Repeat." alt="Typing SVG" />
</h1>

<p align="center">
  <img src="https://komarev.com/ghpvc/?username=nexo-music&label=Repo%20Views&color=3DDC97&style=for-the-badge" />
</p>

<p align="center">
  <a href="https://github.com/KIRU-OP/nexo-music/stargazers"><img src="https://img.shields.io/github/stars/KIRU-OP/nexo-music?style=for-the-badge&color=3DDC97&labelColor=1b1c15"/></a>
  <a href="https://github.com/KIRU-OP/nexo-music/network/members"><img src="https://img.shields.io/github/forks/KIRU-OP/nexo-music?style=for-the-badge&color=3DDC97&labelColor=1b1c15"/></a>
  <a href="LICENSE"><img src="https://img.shields.io/badge/license-MIT-3DDC97?style=for-the-badge&labelColor=1b1c15"/></a>
  <a href="https://t.me/kiru_bots"><img src="https://img.shields.io/badge/support-telegram-3DDC97?style=for-the-badge&logo=telegram&logoColor=white&labelColor=1b1c15"/></a>
</p>

<p align="center">
  <a href="https://t.me/kiru_bots">
    <img src="https://img.shields.io/badge/💬%20Join%20Support%20Group-3DDC97?style=for-the-badge&labelColor=1b1c15"/>
  </a>
  <a href="https://t.me/about_deadly_venom">
    <img src="https://img.shields.io/badge/📢%20Updates%20Channel-3DDC97?style=for-the-badge&labelColor=1b1c15"/>
  </a>
</p>

---

## 🎧 What is Nexo Music?

**Nexo Music** streams crystal-clear, lag-free audio & video straight into your Telegram group's voice chat. Powered by **Pyrogram** + **PyTgCalls**, pulling from **YouTube, Spotify, Apple Music, SoundCloud & Resso** — plus a stack of AI-powered extras thrown in for good measure.

<table align="center">
<tr>
<td width="50%" valign="top">

### 🔥 Core Powers
- 🎶 **HQ Streaming** — zero lag, zero distortion
- 🌐 **Multi-Platform** — YT, Spotify, Apple Music, SoundCloud, Resso
- 📃 **Smart Queue** — playlists, skip, loop, shuffle
- 👮 **Group Management** — mute, ban, kick, promote
- 👋 **Custom Welcomes** — greet new members in style

</td>
<td width="50%" valign="top">

### ⚡ Extra Firepower
- 🖼️ **AI Image Generation** via Replicate / HF
- 🌍 **Instant Translation** across languages
- 📊 **Live Stats** — CPU, RAM, uptime, users
- 🔊 **Auto-Leave Assistant** — smart voice-chat cleanup
- 🐳 **Deploy Anywhere** — Heroku, Docker, VPS, one command

</td>
</tr>
</table>

---

## 🚀 Get It Running

<details>
<summary><b>☁️ Deploy on Heroku — one click</b></summary>
<br>

[![Deploy](https://www.herokucdn.com/deploy/button.svg)](https://heroku.com/deploy?template=https://github.com/KIRU-OP/nexo-music)

Fill in the required env vars on the Heroku form, hit deploy, and watch the build logs — you're live in minutes.

</details>

<details>
<summary><b>🐳 Deploy with Docker</b></summary>
<br>

```bash
git clone https://github.com/KIRU-OP/nexo-music
cd nexo-music
cp sample.env .env        # fill in your values
docker build -t nexo-music .
docker run -d --env-file .env --name nexo-music nexo-music
```

</details>

<details>
<summary><b>🖥️ Deploy on a VPS</b></summary>
<br>

```bash
git clone https://github.com/KIRU-OP/nexo-music
cd nexo-music
python3.12 -m venv venv && source venv/bin/activate
pip install -r requirements.txt
cp sample.env .env         # fill in your values
bash start
```

Needs `git`, `ffmpeg`, and Python 3.12+ on the host.

</details>

---

## 🔑 Environment Variables

| Variable | Required | What it's for |
|---|:---:|---|
| `API_ID` / `API_HASH` | ✅ | From [my.telegram.org](https://my.telegram.org) |
| `BOT_TOKEN` | ✅ | From [@BotFather](https://t.me/BotFather) |
| `OWNER_ID` | ✅ | Your numeric Telegram user ID |
| `LOGGER_ID` | ✅ | Log group chat ID (bot must be admin) |
| `STRING_SESSION` | ✅ | Pyrogram session string for the assistant |
| `MONGO_DB_URI` | ✅ | MongoDB connection string |
| `COOKIE_URL` | ✅ | Raw link to a YouTube `cookies.txt` |
| `QUEUE_LIMIT` | ⬜ | Max queue size (default `10`) |
| `DEEP_API` / `REPLICATE_API_TOKEN(S)` / `HF_TOKEN(S)` | ⬜ | Power the AI image & vision commands |
| `SPOTIFY_CLIENT_ID` / `SECRET` | ⬜ | From the [Spotify Dev Dashboard](https://developer.spotify.com/dashboard) |

> 📄 Full list with advanced fallback/proxy options lives in [`sample.env`](sample.env).

---

## 🎮 Command Cheat Sheet

| Command | Does what |
|---|---|
| `/play` `/vplay` | Blast a song or video into the voice chat |
| `/skip` `/pause` `/resume` `/end` | Take control of playback |
| `/queue` | Peek at what's coming up |
| `/genvid` | Conjure an AI image out of thin air |
| `/translate` | Break the language barrier |
| `/ban` `/mute` `/promote` | Keep your group in check |

Type `/help` inside the bot for the full, always-current list.

---

## 📜 Privacy & License

🔐 [**Privacy Policy**](https://claude.ai/artifact/2XFLzM4uUNi1jLrwK1hvVF) — what data flows through the bot, and why.
⚖️ Released under the **[MIT License](LICENSE)** — fork it, break it, ship it.

---

<div align="center">

### 🤝 Need a hand?

**[💬 Support Group](https://t.me/kiru_bots)** · **[📢 Channel](https://t.me/about_deadly_venom)** · **[👤 Developer @ll_deadly_venom_ll](https://t.me/ll_deadly_venom_ll)**

<sub>Built with ♪ for Telegram communities that never want the music to stop.</sub>

</div>
