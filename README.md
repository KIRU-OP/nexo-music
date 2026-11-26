<p align="center">
  <img src="https://user-images.githubusercontent.com/73097560/115834477-dbab4500-a447-11eb-908a-139a6edaec5c.gif" width="100%" />
</p>

<h1 align="center">
  <img src="https://readme-typing-svg.herokuapp.com?font=Fira+Code&size=35&pause=1000&color=3DDC97&center=true&vCenter=true&width=650&lines=NEXO+MUSIC+%F0%9F%8E%A7;Next+Level+Telegram+Music+Bot;Stream.+Control.+Enjoy." alt="NEXO MUSIC" />
</h1>

<h3 align="center">
  Your Music. Your Voice Chat. Your Vibe.
</h3>

<p align="center">
  <img src="https://komarev.com/ghpvc/?username=KIRU-OP&label=PROFILE%20VIEWS&color=3DDC97&style=for-the-badge" />
</p>

<p align="center">
  <a href="https://github.com/KIRU-OP/nexo-music/stargazers">
    <img src="https://img.shields.io/github/stars/KIRU-OP/nexo-music?style=for-the-badge&color=3DDC97&labelColor=101820"/>
  </a>
  <a href="https://github.com/KIRU-OP/nexo-music/network/members">
    <img src="https://img.shields.io/github/forks/KIRU-OP/nexo-music?style=for-the-badge&color=3DDC97&labelColor=101820"/>
  </a>
  <a href="LICENSE">
    <img src="https://img.shields.io/badge/License-MIT-3DDC97?style=for-the-badge&labelColor=101820"/>
  </a>
  <a href="https://t.me/kiru_bots">
    <img src="https://img.shields.io/badge/Support-Telegram-3DDC97?style=for-the-badge&logo=telegram&logoColor=white&labelColor=101820"/>
  </a>
  <img src="https://img.shields.io/badge/Python-3.12+-3776AB?style=for-the-badge&logo=python&logoColor=white"/>
</p>

<p align="center">
  <a href="https://t.me/kiru_bots">
    <img src="https://img.shields.io/badge/💬_Join_Support_Group-3DDC97?style=for-the-badge&labelColor=101820"/>
  </a>
  <a href="https://t.me/about_deadly_venom">
    <img src="https://img.shields.io/badge/📢_Updates_Channel-3DDC97?style=for-the-badge&labelColor=101820"/>
  </a>
</p>

---

## 🎧 What is NEXO MUSIC?

**NEXO MUSIC** brings music directly into your Telegram group's voice chat. Search for tracks, stream supported audio and video, manage the queue, and control playback without leaving Telegram.

Built around Telegram voice-chat technology, NEXO focuses on a smooth listening experience, dependable assistant handling, and simple controls for group members.

<table align="center">
<tr>
<td width="50%" valign="top">

### 🔥 Music Experience

- 🎶 **Voice Chat Streaming** — Play music in group voice chats
- 🌐 **Multi-Platform Search** — Discover tracks from supported sources
- 📃 **Smart Queue** — Manage upcoming songs
- 🔁 **Loop & Shuffle** — Customize playback
- 🎬 **Video Playback** — Play supported video streams

</td>
<td width="50%" valign="top">

### ⚡ Extra Features

- 🤖 **Assistant System** — Voice-chat assistant support
- 🚀 **Playback Optimization** — Faster stream startup
- 📊 **System Statistics** — Monitor bot performance
- 🌍 **Translation Tools** — Multilingual support
- 🎨 **AI Integrations** — Optional image-generation features
- 🛠️ **Group Utilities** — Helpful management commands

</td>
</tr>
</table>

---

## 🎼 Supported Music Platforms

<p align="center">
  <img src="https://img.shields.io/badge/YouTube-FF0000?style=for-the-badge&logo=youtube&logoColor=white"/>
  <img src="https://img.shields.io/badge/Spotify-1DB954?style=for-the-badge&logo=spotify&logoColor=white"/>
  <img src="https://img.shields.io/badge/Apple_Music-FA243C?style=for-the-badge&logo=applemusic&logoColor=white"/>
  <img src="https://img.shields.io/badge/SoundCloud-FF5500?style=for-the-badge&logo=soundcloud&logoColor=white"/>
</p>

<p align="center">
  <i>Provider availability depends on the current implementation and configuration.</i>
</p>

---

## 🚀 Get It Running

<details>
<summary><b>🖥️ Deploy on a VPS — Ubuntu / Debian</b></summary>
<br>

```bash
git clone https://github.com/KIRU-OP/nexo-music
cd nexo-music

apt update
apt install -y git ffmpeg python3-venv python3-full

python3 -m venv venv
source venv/bin/activate

python -m pip install --upgrade pip setuptools wheel
pip install -r requirements.txt

cp sample.env .env
```

Fill in the required values in `.env`, then start:

```bash
bash start
```

</details>

<details>
<summary><b>🐳 Deploy with Docker</b></summary>
<br>

```bash
git clone https://github.com/KIRU-OP/nexo-music
cd nexo-music

cp sample.env .env
docker build -t nexo-music .
docker run -d --restart unless-stopped --env-file .env --name nexo-music nexo-music
```

</details>

---

## 🔑 Environment Variables

| Variable | Required | Description |
|---|:---:|---|
| `API_ID` / `API_HASH` | ✅ | Telegram API credentials |
| `BOT_TOKEN` | ✅ | Telegram bot token from [@BotFather](https://t.me/BotFather) |
| `OWNER_ID` | ✅ | Bot owner's Telegram user ID |
| `LOGGER_ID` | ✅ | Logging group chat ID |
| `STRING_SESSION` | ✅ | Assistant account session |
| `MONGO_DB_URI` | ✅ | MongoDB connection string |
| `COOKIE_URL` | ⬜ | YouTube cookies source, if required |
| `QUEUE_LIMIT` | ⬜ | Maximum queue size |
| `SPOTIFY_CLIENT_ID` / `SPOTIFY_CLIENT_SECRET` | ⬜ | Spotify integration credentials |

> 📄 Check [`sample.env`](sample.env) for the complete list of configuration options.

---

## 🎮 Command Cheat Sheet

| Command | Function |
|---|---|
| `/play` | Play a song in voice chat |
| `/vplay` | Play a supported video |
| `/skip` | Skip the current track |
| `/pause` | Pause playback |
| `/resume` | Resume playback |
| `/end` | Stop playback |
| `/queue` | View upcoming tracks |
| `/help` | View available commands |

<p align="center">
  <i>Available commands may vary according to enabled modules and bot configuration.</i>
</p>

---

## ⚙️ Technology Stack

<p align="center">
  <img src="https://skillicons.dev/icons?i=python,mongodb,docker,git,linux" />
</p>

<p align="center">
  <img src="https://img.shields.io/badge/Telegram-Voice%20Chat-229ED9?style=flat-square&logo=telegram&logoColor=white"/>
  <img src="https://img.shields.io/badge/MongoDB-Database-47A248?style=flat-square&logo=mongodb&logoColor=white"/>
  <img src="https://img.shields.io/badge/Docker-Deployment-2496ED?style=flat-square&logo=docker&logoColor=white"/>
</p>

---

## ⚡ Performance & Development

NEXO MUSIC is continuously improved with a focus on:

- Faster voice-chat playback startup.
- More efficient stream validation.
- Reliable assistant connection handling.
- Playback stability and bug fixes.
- New features and maintenance updates.

---

## 🛡️ Privacy & Security

Keep your `.env` file, bot token, assistant session, and database credentials private. Never publish secrets in issues, screenshots, or public commits.

Review the repository configuration before deploying your own instance.

---

## 🤝 Need a Hand?

<p align="center">
  <a href="https://t.me/kiru_bots">
    <img src="https://img.shields.io/badge/💬_Support_Group-229ED9?style=for-the-badge&logo=telegram&logoColor=white"/>
  </a>
  <a href="https://t.me/about_deadly_venom">
    <img src="https://img.shields.io/badge/📢_Updates_Channel-229ED9?style=for-the-badge&logo=telegram&logoColor=white"/>
  </a>
  <a href="https://t.me/ll_deadly_venom_ll">
    <img src="https://img.shields.io/badge/👤_Developer-229ED9?style=for-the-badge&logo=telegram&logoColor=white"/>
  </a>
</p>

<p align="center">
  Found a bug or have a feature idea? Reach out through our community.
</p>

---

## 📜 License

Released under the **MIT License**. See the [`LICENSE`](LICENSE) file for details.

<p align="center">
  <img src="https://user-images.githubusercontent.com/73097560/115834477-dbab4500-a447-11eb-908a-139a6edaec5c.gif" width="100%" />
</p>

<h2 align="center">🎧 NEXO MUSIC</h2>

<p align="center">
  <b>Play. Vibe. Repeat.</b>
  <br/><br/>
  <sub>Built with ❤️ for Telegram communities.</sub>
</p>
